"""
Shared test setup for the bark plugin: a local push server and a plugin loaded by the real SmartHomeNG loader.
"""

import json
import tempfile
import threading
import unittest
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import tests.common as common
from tests.sdp_harness import load_plugin

common.register_shng_log_levels()

DEVICE_KEY = 'test-device-key'

# the harness needs at least one item
NO_ITEMS = """
unused:
    type: bool
"""


@dataclass(frozen=True)
class ReceivedPush:
    """One request received by :class:`PushServer`."""

    path: str
    payload: dict[str, str]


class PushServer(ThreadingHTTPServer):
    """HTTP server on a free local port that records pushes and answers with :attr:`status`."""

    def __init__(self) -> None:
        super().__init__(('127.0.0.1', 0), _PushHandler)
        self.pushes: list[ReceivedPush] = []
        self.status = 200

    @property
    def url(self) -> str:
        """Base URL of the server."""
        return f'http://127.0.0.1:{self.server_port}'


class _PushHandler(BaseHTTPRequestHandler):
    server: PushServer

    def do_POST(self) -> None:
        raw = self.rfile.read(int(self.headers['Content-Length']))
        self.server.pushes.append(ReceivedPush(self.path, json.loads(raw)))
        self.send_response(self.server.status)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        pass


class BarkTestBase(unittest.TestCase):
    """Base class providing :attr:`server` and :meth:`load_plugin`."""

    def setUp(self) -> None:
        self.server = PushServer()
        thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': 0.01})
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def load_plugin(self, server_url: str | None = None, items: str = NO_ITEMS):
        """
        Load the plugin through ``lib.plugin``, create the items and run the plugin.

        The rig holding the SmartHomeNG instance and the captured log records is stored as ``self.rig``.

        :param server_url: ``server_url`` plugin parameter, defaults to the URL of :attr:`server`
        :param items: item tree as YAML text
        :return: the plugin instance
        """
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        params = {'server_url': server_url or self.server.url, 'device_key': DEVICE_KEY}
        self.rig = load_plugin(directory.name, 'plugins.bark', 'Bark', items, params=params, section='bark')
        self.rig.plugin.run()
        self.addCleanup(self.rig.plugin.stop)
        return self.rig.plugin

    def payloads(self) -> list[dict[str, str]]:
        """Payloads of all received pushes."""
        return [push.payload for push in self.server.pushes]
