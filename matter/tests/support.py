#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Shared real-component harnesses for the matter plugin tests (not collected
by pytest - no test_ prefix):

- WsPeer: an in-process WebSocket server on 127.0.0.1 speaking the
  sidecars' JSON request/response protocol, in its own thread and loop.
- PluginHarness: a real Matter plugin instance on MockSmartHome with real
  Items, parameters taken from plugin.yaml's defaults, and the plugin's
  real asyncio loop thread (roles are not started - no sidecar processes).
"""

from __future__ import annotations

import asyncio
import collections
import json
import os
import sys
import tempfile
import threading
from typing import Any, Callable

import websockets

import tests.common as common

common.register_shng_log_levels()

import lib.config  # noqa: E402
import lib.shyaml as shyaml  # noqa: E402
from lib.item.items import Items  # noqa: E402
from lib.item.structs import Structs  # noqa: E402
from lib.plugin import Plugins  # noqa: E402
from tests.mock.core import MockSmartHome  # noqa: E402

from plugins.matter import Matter  # noqa: E402

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

Responder = Callable[[dict[str, Any]], 'dict[str, Any] | None']


def wait_for(condition: Callable[[], bool], timeout: float = 5.0) -> bool:
    """Poll *condition* until true or *timeout* passes; returns its last result."""
    event = threading.Event()
    for _ in range(int(timeout / 0.01)):
        if condition():
            return True
        event.wait(0.01)
    return condition()


def plugin_yaml() -> dict[str, Any]:
    return shyaml.yaml_load(os.path.join(PLUGIN_DIR, 'plugin.yaml'), ordered=True)


def default_parameters() -> dict[str, Any]:
    return {name: spec.get('default') for name, spec in plugin_yaml()['parameters'].items()}


class WsPeer:
    """
    WebSocket server standing in for a sidecar. Every request is recorded;
    responder(request) returns the answer (without the id field, which is
    added) or None for no answer at all. greeting is sent unframed right
    after a client connects (matter-server's ServerInfoMessage).
    """

    def __init__(self, id_field: str, responder: Responder | None = None, greeting: dict[str, Any] | None = None):
        self.id_field = id_field
        self.responder = responder or (lambda request: {'result': {}})
        self.greeting = greeting
        self.received: list[dict[str, Any]] = []
        self.port = 0
        self._connections: set = set()
        self._loop = asyncio.new_event_loop()
        self._ready = threading.Event()
        self._server = None
        self._thread = threading.Thread(target=self._run, name='ws-peer', daemon=True)

    def start(self) -> WsPeer:
        self._thread.start()
        self._ready.wait(5)
        return self

    def stop(self) -> None:
        asyncio.run_coroutine_threadsafe(self._shutdown(), self._loop).result(5)
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(5)

    @property
    def url(self) -> str:
        return f'ws://127.0.0.1:{self.port}'

    def commands(self, name: str) -> list[dict[str, Any]]:
        return [message for message in list(self.received) if message.get('command') == name]

    def push(self, message: dict[str, Any]) -> None:
        """Send an unsolicited message to every connected client."""
        asyncio.run_coroutine_threadsafe(self._broadcast(json.dumps(message)), self._loop).result(5)

    def drop_connections(self) -> None:
        asyncio.run_coroutine_threadsafe(self._close_all(), self._loop).result(5)

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._serve())
        self._ready.set()
        self._loop.run_forever()

    async def _serve(self) -> None:
        self._server = await websockets.serve(self._handle, '127.0.0.1', 0)
        self.port = next(iter(self._server.sockets)).getsockname()[1]

    async def _handle(self, websocket, path: str | None = None) -> None:
        self._connections.add(websocket)
        try:
            if self.greeting is not None:
                await websocket.send(json.dumps(self.greeting))
            async for raw in websocket:
                request = json.loads(raw)
                self.received.append(request)
                answer = self.responder(request)
                if asyncio.iscoroutine(answer):
                    answer = await answer
                if answer is not None:
                    await websocket.send(json.dumps({self.id_field: request[self.id_field], **answer}))
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self._connections.discard(websocket)

    async def _broadcast(self, raw: str) -> None:
        for websocket in list(self._connections):
            await websocket.send(raw)

    async def _close_all(self) -> None:
        for websocket in list(self._connections):
            await websocket.close()

    async def _shutdown(self) -> None:
        await self._close_all()
        self._server.close()
        await self._server.wait_closed()


class PluginHarness:
    """
    A real Matter plugin on MockSmartHome. items_yaml is loaded into real
    Items and parsed by the plugin; start_loop() runs the plugin's real
    asyncio loop thread (without starting the roles' sidecars).
    """

    def __init__(self, items_yaml: str, instance: str = '', **parameter_overrides: Any):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = self._tmp.name
        # Items/Structs keep their registries in class attributes - reset them so harnesses don't share items
        Items._Items__items = []
        Items._Items__item_dict = {}
        Structs._struct_definitions = collections.OrderedDict()
        Structs._finalized_structs = []
        self.sh = MockSmartHome()
        self.sh._items_dir = os.path.join(self.tmp_dir, 'items')
        os.makedirs(self.sh._items_dir)
        with open(os.path.join(self.sh._items_dir, 'test_items.yaml'), 'w') as f:
            f.write(items_yaml)

        parameters = default_parameters()
        parameters.update(
            storage_path=os.path.join(self.tmp_dir, 'storage'),
            bridge_storage_path=os.path.join(self.tmp_dir, 'bridge_storage'),
        )
        parameters.update(parameter_overrides)

        plugin = Matter.__new__(Matter)
        plugin._set_sh(self.sh)
        plugin._parameters = parameters
        plugin._set_shortname('matter')
        plugin._set_instance_name(instance)
        plugin._plugin_dir = PLUGIN_DIR
        plugin.__init__(self.sh)
        plugin.alive = True
        self.plugin = plugin

        # registered like a loaded plugin, so Item construction/edits call parse_item and wire update_item
        self._plugins = Plugins.get_instance()._plugins
        self._plugins.append(plugin)
        self._load_items()

    def _load_items(self) -> None:
        """Same path as Items.load_itemdefinitions(): plugin structs registered, then items linked under Items."""
        items = self.sh.items
        for name, struct in plugin_yaml()['item_structs'].items():
            items.add_struct_definition('matter', name, struct)
        structs = items.structs
        while any(structs.traverse_struct(name) for name in list(structs._struct_definitions)):
            pass
        item_conf = lib.config.parse_itemsdir(
            os.path.join(self.sh._items_dir, ''),
            collections.OrderedDict(),
            addfilenames=True,
            struct_dict=items.structs._struct_definitions,
        )
        for path, config in item_conf.items():
            if isinstance(config, dict):
                items._construct_and_link(path, config)

    def item(self, path: str):
        return self.sh.return_item(path)

    def start_loop(self) -> None:
        self.plugin.start_asyncio(self.plugin.wait_for_asyncio_termination())
        assert wait_for(lambda: self.plugin._asyncio_state == 'running')

    def run(self, coro) -> Any:
        return self.plugin.run_asyncio_coro(coro, timeout=10)

    def close(self) -> None:
        loop = self.plugin._asyncio_loop
        if loop is not None:
            for role in self.plugin.roles:
                if role.client is not None:
                    asyncio.run_coroutine_threadsafe(role.client.close(), loop).result(5)
            asyncio.run_coroutine_threadsafe(self.plugin._run_queue.put('STOP'), loop)
            self.plugin.pluginThread.join(5)
        self._plugins.remove(self.plugin)
        self._tmp.cleanup()


def connect_client(harness: PluginHarness, role, url: str) -> None:
    """Point a role at a WsPeer and connect its real client on the plugin loop."""
    role.url = url
    client = role._make_client()
    harness.run(client.connect())
    role.client = client


def python_node() -> str:
    """Interpreter standing in for the node binary: sidecar entry files in tests are Python scripts."""
    return sys.executable
