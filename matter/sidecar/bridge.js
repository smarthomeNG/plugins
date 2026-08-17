#!/usr/bin/env node
/**
 * Matter bridge role: a long-running @matter/node application that hosts
 * shng items as bridged Matter accessories for other Matter controllers
 * (Apple Home, Google Home, ...). Endpoints are added/removed live, driven
 * by bridge/client.py over a local control WebSocket - not matter-server,
 * which plays no part in this role (see dev/matter/matter-integration-plan.md's
 * "Bridge role" sections in the core repo for the full design and the
 * dynamic-add validation this is built on, including a real live test
 * against Apple Home).
 *
 * Derived from dev/matter/spike/bridge/bridge_spike.js (Phase 0 bridge
 * spike, both the initial static-device pass and the later dynamic-add/
 * SIGUSR1 rounds) - same @matter/node APIs, no longer hardcoded to one
 * fixed device.
 *
 * Control protocol (Python <-> Node, one JSON message per WebSocket frame):
 *   Python -> Node request:  {"id": <int>, "command": <str>, "args": {...}}
 *   Node -> Python response: {"id": <int>, "result": {...}}
 *                          or {"id": <int>, "error": <str>}
 *   Node -> Python event:    {"event": <str>, "data": {...}}
 *
 * Commands:
 *   add_endpoint {item_path, expose_type, name} -> {endpoint_id}
 *     endpoint_id is stable per item_path across bridge restarts - see
 *     persistedEndpointIds/nextFreeEndpointNumber() below for why plain
 *     sequential auto-assignment isn't enough on its own (a real live bug:
 *     matter-server's re-interview of the bridge threw a ConstraintError
 *     after a restart reshuffled numbers out from under its own cache).
 *   remove_endpoint {endpoint_id} -> {}
 *   set_attribute {endpoint_id, value} -> {}
 *     (v1 expose_types each have exactly one state attribute - see
 *     EXPOSE_TYPES below - so the command carries a bare value, not a
 *     cluster/attribute pair; revisit only if a type with more than one
 *     attribute is ever added)
 *   get_status {} -> {passcode, discriminator, manual_pairing_code,
 *     qr_pairing_code, commissioned, fabric_count, commissioning_window_open,
 *     commissioning_window_closes_in_seconds}
 *     The window fields are tracked here, not read back from matter.js -
 *     DeviceCommissioner's own #windowStatus is private with no public
 *     getter, and the AdministratorCommissioning cluster's own WindowStatus
 *     attribute is only updated by that cluster's OWN command handlers
 *     (openBasicCommissioningWindow/openCommissioningWindow), which this
 *     script deliberately bypasses (see open_commissioning_window below) -
 *     so that attribute would never reflect either of the two window-opens
 *     this script actually performs. Tracked instead as a plain
 *     windowOpenUntilMs timestamp, set at the two points this script
 *     controls (initial boot when uncommissioned - mirrors the exact gate
 *     CommissioningServer.enterCommissionableMode() itself uses - and every
 *     open_commissioning_window call), cleared early the instant a fabric is
 *     actually added (a real controller can finish pairing well before the
 *     window's own timeout, closing it early - STANDARD_COMMISSIONING_TIMEOUT
 *     alone would overstate how long it's still open).
 *   open_commissioning_window {} -> {}
 *     Reopens the BASIC commissioning window using the bridge's existing
 *     static passcode/discriminator (agent.commissioning.enterCommissionableMode() -
 *     NOT allowBasicCommissioning(), which CommissioningServer never exposes
 *     under that name, only calls internally; enterCommissionableMode() is
 *     the real public entry point, see handleOpenCommissioningWindow() below
 *     for the full story), works even with fabrics already present - no
 *     guard against that in enterCommissionableMode() itself. Deliberately
 *     not the ENHANCED window
 *     (AdministratorCommissioning.openCommissioningWindow, random passcode) -
 *     reusing the one static code already shown in the UI is simpler and
 *     sufficient until that's proven insufficient for something real.
 *   get_fabrics {} -> {fabrics: [{fabric_index, vendor_id, fabric_label, fabric_id}]}
 *   remove_fabric {fabric_index} -> {}
 *     Both fabric commands go through FabricManager directly
 *     (server.env.get(FabricManager)), NOT the OperationalCredentials
 *     cluster's own removeFabric() - that one asserts an authenticated
 *     REMOTE session (AccessControl.js's assertRemoteActor), meant for a
 *     real controller invoking RemoveFabric on itself over the wire, and
 *     throws if called locally like this. FabricManager is the same
 *     lower-level primitive the cluster handler itself uses internally
 *     (fabric.leave()) - the correct layer for a local/administrative
 *     removal, not a simulated remote command.
 *
 * Events:
 *   command_received {endpoint_id, value}
 *     Fired only for expose_type "switch", only from the device's own
 *     on()/off() command handlers (see SwitchOnOffServer below) - never
 *     from this script's own set_attribute() calls, which use state
 *     writes that do not route through those handlers. Using the
 *     onOff$Changed *attribute* event instead (as the throwaway spike did,
 *     for its own console logging only) would also fire on our own writes,
 *     creating a write-back loop through shng - deliberately avoided.
 */

import { createHash } from 'node:crypto';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { WebSocketServer } from 'ws';
import { Endpoint, Environment, ServerNode, VendorId } from '@matter/main';
import { FabricManager } from '@matter/protocol';
// The real spec-mandated basic-commissioning-window duration (15 minutes,
// @matter/types/src/commissioning/CommissioningConstants.ts) - imported
// rather than hardcoded so this can never silently drift from what
// DeviceCommissioner.allowBasicCommissioning() actually enforces.
import { STANDARD_COMMISSIONING_TIMEOUT } from '@matter/types';
import { BridgedDeviceBasicInformationServer } from '@matter/main/behaviors/bridged-device-basic-information';
import { OnOffServer } from '@matter/main/behaviors/on-off';
import { OnOffPlugInUnitDevice } from '@matter/main/devices/on-off-plug-in-unit';
import { ContactSensorDevice } from '@matter/main/devices/contact-sensor';
import { TemperatureSensorDevice } from '@matter/main/devices/temperature-sensor';
import { AggregatorEndpoint } from '@matter/main/endpoints/aggregator';

function argValue(name, fallback) {
    const i = process.argv.indexOf(`--${name}`);
    return i >= 0 && i + 1 < process.argv.length ? process.argv[i + 1] : fallback;
}

// --storage-path specifically arrives as one --key=value token (see
// sidecar.py's _build_args() for why - matter.js's own env mapping requires
// that exact form, the two-token form silently drops the value), so argValue()
// above can't find it - it only handles "--name value" as two separate argv
// elements. Read directly here too (matter.js's own Node environment maps it
// to storage.path automatically for its own use - this is a second,
// independent read of the same value, for this script's own endpoint_ids.json
// persistence below).
function argEqualsValue(name, fallback) {
    const prefix = `--${name}=`;
    const arg = process.argv.find(a => a.startsWith(prefix));
    return arg ? arg.slice(prefix.length) : fallback;
}

const MATTER_PORT = parseInt(argValue('matter-port', '5560'), 10);
const CONTROL_PORT = parseInt(argValue('control-port', '5561'), 10);
const STORAGE_PATH = argEqualsValue('storage-path', null);
const PASSCODE = parseInt(argValue('passcode', '20202021'), 10);
const DISCRIMINATOR = parseInt(argValue('discriminator', '3840'), 10);
const VENDOR_ID = parseInt(argValue('vendor-id', '65521'), 10);
const PRIMARY_INTERFACE = argValue('primary-interface', null);

// Not part of matter.js's own argv-to-env auto-mapping - matter-server sets
// this the same explicit way (env.vars.set('mdns.networkInterface', ...) in
// its own MatterServer.js, triggered by its --primary-interface flag), not
// via a CLI-flag-name convention this plugin could otherwise just forward.
// Must run before ServerNode.create() - matter.js reads this when its own
// mDNS/network stack initializes, not on demand later.
if (PRIMARY_INTERFACE) {
    Environment.default.vars.set('mdns.networkInterface', PRIMARY_INTERFACE);
}

/**
 * expose_type -> device construction recipe. Each entry names the base
 * @matter/node device type, whether it accepts commands from controllers
 * (only "switch" does in v1), and how to translate this plugin's own
 * set_attribute(value) into that device's state.
 */
const EXPOSE_TYPES = {
    switch: {
        deviceType: OnOffPlugInUnitDevice,
        commandable: true,
        applyValue: (endpoint, value) => endpoint.set({ onOff: { onOff: !!value } }),
    },
    contact: {
        deviceType: ContactSensorDevice,
        commandable: false,
        applyValue: (endpoint, value) => endpoint.set({ booleanState: { stateValue: !!value } }),
    },
    temperature_sensor: {
        deviceType: TemperatureSensorDevice,
        commandable: false,
        // Matter's "temperature" datatype is int16, hundredths of a degree C
        // (Core Spec 1.6 7.19.2.9) - value = (temperature in C) x 100. shng
        // items carry plain degrees C; the x100 scaling happens here, at the
        // Matter boundary, the same place server/mapping.py's cluster tables
        // would apply a unit conversion (compare the milli-unit handling
        // noted for ElectricalPowerMeasurement in the plan doc).
        applyValue: (endpoint, value) => endpoint.set({ temperatureMeasurement: { measuredValue: Math.round(value * 100) } }),
    },
};

/**
 * OnOffServer override for bridged switches: reports every actually-invoked
 * on()/off() command back to Python as a command_received event, in
 * addition to performing the normal state change. Not reused for toggle()
 * since OnOffBaseServer's own default toggle() implementation already
 * calls this.on()/this.off() internally (see OnOffServer.ts) - overriding
 * it too would double-report.
 */
function makeSwitchOnOffServer(onCommand) {
    return class SwitchOnOffServer extends OnOffServer {
        async on() {
            await super.on();
            onCommand(true);
        }

        async off() {
            await super.off();
            onCommand(false);
        }
    };
}

const server = await ServerNode.create({
    id: 'shng-bridge',
    network: { port: MATTER_PORT },
    commissioning: { passcode: PASSCODE, discriminator: DISCRIMINATOR },
    productDescription: {
        name: 'SmartHomeNG',
        deviceType: AggregatorEndpoint.deviceType,
    },
    basicInformation: {
        vendorName: 'SmartHomeNG',
        vendorId: VendorId(VENDOR_ID),
        nodeLabel: 'SmartHomeNG',
        productName: 'SmartHomeNG Bridge',
        productLabel: 'SmartHomeNG Bridge',
        productId: 0x8006,
        serialNumber: 'shng-matter-bridge-0001',
        uniqueId: 'shng-matter-bridge-0001',
    },
});

const aggregator = new Endpoint(AggregatorEndpoint, { id: 'aggregator' });
await server.add(aggregator);

// endpoint_id (the Matter-assigned endpoint number) -> {endpoint, exposeType}
const endpoints = new Map();
let wsClient = null; // the one control connection expected (bridge/client.py)

/**
 * item_path -> endpoint number, persisted to disk so the SAME shng item gets
 * the SAME Matter endpoint number across bridge restarts - matter.js's own
 * Aggregator.add() assigns endpoint numbers sequentially per session with
 * nothing persisted (confirmed by reading Endpoint.ts - "if you omit the
 * endpoint number the node assigns a sequential one for you", no memory of
 * past assignments), so which number a given item got used to depend purely
 * on how many other items had already been added first that particular
 * session. Caught live: matter-server's own re-interview of the bridge
 * failed with a real ConstraintError ("Cannot initialize ... because it is
 * already active") after a restart reshuffled numbers out from under its own
 * persisted node cache. A stable number is also just correct behavior for a
 * bridge in general - Apple/Google Home expect a bridged accessory's
 * identity to survive a bridge restart without a fresh pairing.
 *
 * Stored flat at <storage_path>/endpoint_ids.json, not inside matter.js's own
 * <storage_path>/shng-bridge/ subdirectory (confirmed via a live repro this
 * script's own storage never writes loose files at the storage_path root,
 * only under that node-id-named subdirectory) - no collision with anything
 * matter.js itself manages there. Entries are never removed on
 * remove_endpoint - re-exposing the same item_path later should get its old
 * number back, not a new one; the file only grows, negligible for a JSON map
 * this small.
 */
const ENDPOINT_IDS_FILE = STORAGE_PATH ? join(STORAGE_PATH, 'endpoint_ids.json') : null;

function loadPersistedEndpointIds() {
    if (!ENDPOINT_IDS_FILE || !existsSync(ENDPOINT_IDS_FILE)) {
        return new Map();
    }
    try {
        return new Map(Object.entries(JSON.parse(readFileSync(ENDPOINT_IDS_FILE, 'utf8'))));
    } catch (ex) {
        console.warn(`[bridge] could not read ${ENDPOINT_IDS_FILE} (${ex.message}), starting with no persisted endpoint IDs`);
        return new Map();
    }
}

function savePersistedEndpointIds() {
    if (!ENDPOINT_IDS_FILE) {
        return;
    }
    try {
        writeFileSync(ENDPOINT_IDS_FILE, JSON.stringify(Object.fromEntries(persistedEndpointIds), null, 2));
    } catch (ex) {
        console.warn(`[bridge] could not write ${ENDPOINT_IDS_FILE} (${ex.message}) - endpoint numbers won't survive a restart`);
    }
}

const persistedEndpointIds = loadPersistedEndpointIds();

/**
 * Lowest number not currently in use AND not already reserved for some other
 * item_path that hasn't been (re-)added yet this session - the second half
 * matters because add_endpoint calls arrive one at a time, in whatever order
 * Python's own item dict iterates in, not "known items first": without also
 * excluding not-yet-arrived persisted numbers, an early brand-new item could
 * get auto-assigned a number a later, already-known item is about to request
 * explicitly, which then fails outright (Endpoint.ts's own allocation guard
 * throws "number N is allocated to another endpoint", not a silent
 * reassignment) - matter.js's own auto-assignment only ever avoids
 * numbers already active *right now*, never numbers reserved for the future
 * on its behalf.
 */
function nextFreeEndpointNumber() {
    const reserved = new Set([0, 1, ...endpoints.keys(), ...persistedEndpointIds.values()]);
    let candidate = 2;
    while (reserved.has(candidate)) {
        candidate += 1;
    }
    return candidate;
}

// Epoch ms the current basic commissioning window closes at, or 0 if none is
// open - see the module comment above ("get_status" entry) for why this is
// tracked here rather than read back from matter.js. Set below, once the
// initial post-server.start() window state is known, and again on every
// open_commissioning_window call.
let windowOpenUntilMs = 0;

// A successful pairing can close the window well before its own timeout -
// closing it early here keeps commissioning_window_open accurate rather than
// optimistically reporting "open" for the rest of the 15 minutes.
server.env.get(FabricManager).events.added.on(() => {
    windowOpenUntilMs = 0;
});

function sendEvent(name, data) {
    if (wsClient && wsClient.readyState === wsClient.OPEN) {
        wsClient.send(JSON.stringify({ event: name, data }));
    }
}

/**
 * BridgedDeviceBasicInformation's SerialNumber is spec-capped at 32 chars
 * (Core Spec, Basic Information cluster) and quality:F (fixed once set) -
 * a raw `shng-${itemPath}` blew past that for any item path over ~27 chars,
 * failing the whole endpoint's construction with a matter.js ConstraintError.
 * Item path length isn't something a user should have to think about
 * just to bridge an item, unlike matter_expose_name (validated in Python's
 * parse_item(), since that one IS user-visible and user-controlled) - so this
 * is unconditionally hash-derived rather than truncated: deterministic (same
 * item -> same serial across restarts, required by quality:F), collision-safe
 * regardless of path length or similarity, and always well under the cap.
 */
function serialNumberFor(itemPath) {
    return 'shng-' + createHash('sha256').update(itemPath).digest('hex').slice(0, 24);
}

async function handleAddEndpoint(args) {
    const spec = EXPOSE_TYPES[args.expose_type];
    if (!spec) {
        throw new Error(`unknown expose_type ${args.expose_type}`);
    }

    const behaviors = spec.commandable
        ? [
              BridgedDeviceBasicInformationServer,
              // endpoint.number is read at call time (the callback only fires
              // once a controller has actually invoked on()/off(), long after
              // aggregator.add() below has assigned it) - not available yet
              // at this point, only after construction.
              makeSwitchOnOffServer(value => sendEvent('command_received', { endpoint_id: endpoint.number, value })),
          ]
        : [BridgedDeviceBasicInformationServer];

    let number = persistedEndpointIds.get(args.item_path);
    if (number === undefined) {
        number = nextFreeEndpointNumber();
        persistedEndpointIds.set(args.item_path, number);
        savePersistedEndpointIds();
    }

    const endpoint = new Endpoint(spec.deviceType.with(...behaviors), {
        // Endpoint id rejects "." (Endpoint.ts), which every shng item path
        // contains (e.g. "test.switch1") - only used internally by matter.js
        // for its own bookkeeping/logging, Python only ever sees the numeric
        // endpoint.number below, so a lossy substitution is fine.
        id: args.item_path.replace(/\./g, '_'),
        number,
        bridgedDeviceBasicInformation: {
            nodeLabel: args.name,
            productName: args.name,
            productLabel: args.name,
            serialNumber: serialNumberFor(args.item_path),
            reachable: true,
        },
    });
    await aggregator.add(endpoint);

    endpoints.set(endpoint.number, { endpoint, exposeType: args.expose_type });
    return { endpoint_id: endpoint.number };
}

async function handleRemoveEndpoint(args) {
    const entry = endpoints.get(args.endpoint_id);
    if (!entry) {
        throw new Error(`no endpoint ${args.endpoint_id}`);
    }
    await entry.endpoint.delete();
    endpoints.delete(args.endpoint_id);
    return {};
}

async function handleSetAttribute(args) {
    const entry = endpoints.get(args.endpoint_id);
    if (!entry) {
        throw new Error(`no endpoint ${args.endpoint_id}`);
    }
    await EXPOSE_TYPES[entry.exposeType].applyValue(entry.endpoint, args.value);
    return {};
}

async function handleGetStatus() {
    const status = await server.act(agent => {
        const state = agent.commissioning.state;
        return {
            passcode: state.passcode,
            discriminator: state.discriminator,
            manual_pairing_code: state.pairingCodes.manualPairingCode,
            qr_pairing_code: state.pairingCodes.qrPairingCode,
            commissioned: state.commissioned,
        };
    });
    status.fabric_count = server.env.get(FabricManager).fabrics.length;
    status.commissioning_window_open = Date.now() < windowOpenUntilMs;
    status.commissioning_window_closes_in_seconds = status.commissioning_window_open
        ? Math.round((windowOpenUntilMs - Date.now()) / 1000)
        : 0;
    return status;
}

async function handleOpenCommissioningWindow() {
    // NOT agent.commissioning.allowBasicCommissioning() - that throws
    // "... is not a function". The CommissioningServer *behavior* (what
    // `agent.commissioning` exposes) never wraps
    // DeviceCommissioner.allowBasicCommissioning() under that name - only
    // enterCommissionableMode() calls it internally, and that's the actual
    // public entry point. enterCommissionableMode() itself has no "already
    // commissioned" guard (that check lives one level up, in
    // CommissioningServer's own boot-time #enterOnlineMode(), not in this
    // method), so this reopens the window correctly whether or not a fabric
    // already exists, same as the doc comment above always intended.
    await server.act(agent => agent.commissioning.enterCommissionableMode());
    windowOpenUntilMs = Date.now() + STANDARD_COMMISSIONING_TIMEOUT;
    return {};
}

async function handleGetFabrics() {
    const fabrics = [...server.env.get(FabricManager)].map(fabric => ({
        fabric_index: fabric.fabricIndex,
        vendor_id: fabric.rootVendorId,
        fabric_label: fabric.label,
        // fabricId is a bigint (Matter's 64-bit FabricId) - JSON.stringify() throws on a raw
        // bigint, stringified here rather than leaving the caller to discover that.
        fabric_id: String(fabric.fabricId),
    }));
    return { fabrics };
}

async function handleRemoveFabric(args) {
    const fabric = server.env.get(FabricManager).maybeFor(args.fabric_index);
    if (!fabric) {
        throw new Error(`no fabric ${args.fabric_index}`);
    }
    await fabric.leave();
    return {};
}

const COMMANDS = {
    add_endpoint: handleAddEndpoint,
    remove_endpoint: handleRemoveEndpoint,
    set_attribute: handleSetAttribute,
    get_status: handleGetStatus,
    open_commissioning_window: handleOpenCommissioningWindow,
    get_fabrics: handleGetFabrics,
    remove_fabric: handleRemoveFabric,
};

const wss = new WebSocketServer({ port: CONTROL_PORT, host: '127.0.0.1' });
wss.on('connection', ws => {
    wsClient = ws;
    ws.on('message', async raw => {
        let message;
        try {
            message = JSON.parse(raw.toString());
        } catch {
            return;
        }
        const handler = COMMANDS[message.command];
        if (!handler) {
            ws.send(JSON.stringify({ id: message.id, error: `unknown command ${message.command}` }));
            return;
        }
        try {
            const result = await handler(message.args || {});
            ws.send(JSON.stringify({ id: message.id, result }));
        } catch (ex) {
            ws.send(JSON.stringify({ id: message.id, error: String(ex && ex.message ? ex.message : ex) }));
        }
    });
    ws.on('close', () => {
        if (wsClient === ws) {
            wsClient = null;
        }
    });
});

console.log(`[bridge] control WS listening on 127.0.0.1:${CONTROL_PORT}`);
await server.start();
// Mirrors CommissioningServer.#enterOnlineMode()'s own gate for calling
// enterCommissionableMode() at boot (uncommissioned, i.e. no fabrics yet) -
// that internal call already opened a real 15-minute basic commissioning
// window as part of server.start() above; this just records it happened,
// since matter.js exposes no public getter for that window's own state.
if (server.env.get(FabricManager).fabrics.length === 0) {
    windowOpenUntilMs = Date.now() + STANDARD_COMMISSIONING_TIMEOUT;
}
console.log(`[bridge] Matter node started on port ${MATTER_PORT}`);
