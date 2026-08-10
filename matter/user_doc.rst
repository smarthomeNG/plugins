.. index:: Plugins; matter
.. index:: matter

======
matter
======

Matter controller plugin for SmartHomeNG. Commissions and controls Matter devices directly - no
separate hub/bridge/app needed. See ``dev/matter/matter-integration-plan.md`` in the core repo for
the full architecture background and the Phase 0 spike findings this plugin is built on.

Requirements
============

This is currently the only shng plugin with a non-Python runtime dependency: a Node.js sidecar
(`matter-server <https://github.com/matter-js/matterjs-server>`_, the actively maintained successor
to the now-archived python-matter-server) that speaks Matter's actual protocol stack.

1. Install a supported Node.js version. matter-server 1.3.3 requires
   ``>=20.19.0 <22.0.0 || >=22.13.0`` - not just "any modern Node". Using ``nvm``::

       nvm install lts/jod
       nvm use lts/jod

2. Install the sidecar dependency (one-time, not done automatically by the plugin)::

       cd plugins/matter/sidecar
       npm install

If either step is skipped, the plugin logs a clear error on startup and stays idle rather than
crashing shng.

Configuration
=============

See plugin.yaml for the full parameter list (node binary path, sidecar port, storage path,
``enable_test_net_dcl``). Defaults work for a standard install with the sidecar set up as above.

Item attributes
================

``matter_node``, ``matter_endpoint``, ``matter_cluster`` address a specific cluster instance. These
three only need to be set once, on a device's "master" item - every child item inherits whichever
one it doesn't set itself from the nearest ancestor that does, via shng's own
``Item.find_attribute()``. Only override one (usually ``matter_cluster``) on a child that actually
addresses a different cluster than its parent - see ``dev/matter/spike/sample_matter_items.yaml``
(core repo) for a worked example (a switch item with power-measurement children on a different
cluster). Nothing is inherited beyond these three - ``matter_switch``/``matter_attribute``/
``matter_command`` always have to be set on the item they apply to, so an item always explicitly
opts in to its own mapping.

For a bool on/off-shaped item (e.g. OnOff), use ``matter_switch: true`` - the plugin derives the
state attribute and both commands from a small internal per-cluster table, so the item config
doesn't need to know Matter's attribute/command names at all. Logs a clear error instead of a
silent no-op if the cluster isn't in that table yet.

For anything else (or a cluster ``matter_switch`` doesn't cover yet), use the low-level attributes
directly: ``matter_attribute`` (int) makes the item a read/subscribe mirror of that attribute.
``matter_command`` (str, optionally with ``matter_command_params``) makes an item write invoke that
command; use the placeholder ``"$value"`` in a param value to substitute the item's written value
(e.g. for ``MoveToLevel``'s ``level`` parameter). ``matter_attribute`` and ``matter_command`` may
both be set on the same item (mirrors state via subscription, drives it via command on write) -
add ``matter_command_false`` to route a falsy write to a different command than a truthy one (e.g.
``matter_command: on``, ``matter_command_false: off``) rather than a fixed command that fires on
every write regardless of value.

A command-only item with no matching state attribute (e.g. ``toggle``) is a momentary trigger, not
a value - give it ``enforce_updates: true`` (otherwise writing the same value twice in a row gets
deduped away and the second write never fires) and an ``autotimer`` that resets it back to falsy
(e.g. ``autotimer: 1 = 0``). This is general shng item modeling advice, not Matter-specific - any
trigger-only item needs it, and the webif's Item-Generator already includes both for the ``toggle``
item it suggests.

``matter_available`` (bool, read-only) mirrors matter-server's own node-level reachability tracking
- the same information the webif's Devices tab already shows in its "verfügbar" column, exposed
here as a real item for your own logic/struct/visu. Only needs ``matter_node`` resolved (via the
same ancestor inheritance as above), not an endpoint or cluster - availability isn't attached to
either.

Item structs
============

``item_structs`` in ``plugin.yaml`` is meant as a growing collection of ready-made templates for
known, tested devices - not generic per-cluster templates. So far: ``matter.shelly_plug_m_3gen_simple``
(OnOff switch/toggle + availability, cluster/endpoint baked in since they're fixed for this exact
device model - only ``matter_node`` needs setting on the attaching item) and
``matter.shelly_plug_m_3gen`` (adds power/voltage/current on top, via ``struct:
.shelly_plug_m_3gen_simple`` referencing the first one in the same namespace). Both convert the raw
milli-units (mW/mV/mA) to base units via a child item + ``eval``, since the plugin itself passes
attribute values through unconverted (see ``dev/matter/matter-integration-plan.md``'s
"ElectricalPowerMeasurement" sections for why).

RMSVoltage in particular is not guaranteed to ever report a live update on a given device, even
though its sibling attributes on the same cluster do - see
``dev/matter/matter-integration-plan.md``'s "RMSVoltage never reports" section before relying on it
for anything time-sensitive.

Phase 2 scope
=============

Sidecar supervision, WS client, item mapping (generic attribute/command, plus ``matter_switch``
shorthand for bool on/off clusters), endpoint/cluster discovery browser and copy-paste
item-generator YAML in the webif. No broadened cluster-specific handling for
ColorControl/Thermostat/etc. (Phase 3), no DoorLock user/schedule management (Phase 4/5, only if
demanded).
