#!/usr/bin/env python3
"""
End-to-end tests for the NUT plugin against a real TCP server speaking the
NUT ``LIST VAR`` protocol; the plugin's polling goes through a real socket.
"""

import socketserver
import threading
import unittest

import tests.common as common
from tests.mock.core import MockSmartHome

common.register_shng_log_levels()

UPS = 'myups'
LIST_REPLY = (
    f'BEGIN LIST VAR {UPS}\n'
    f'VAR {UPS} battery.charge "100"\n'
    f'VAR {UPS} ups.status "OL CHRG"\n'
    f'VAR {UPS} device.model "Back-UPS RS 900"\n'
    f'END LIST VAR {UPS}\n'
)


class _NutHandler(socketserver.StreamRequestHandler):
    def handle(self):
        request = self.rfile.readline().decode('ascii')
        self.server.requests.append(request)
        self.wfile.write(self.server.reply.encode('ascii'))
        self.wfile.flush()


class _NutServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, reply=LIST_REPLY):
        super().__init__(('127.0.0.1', 0), _NutHandler)
        self.reply = reply
        self.requests = []


class _FakeItem:
    """Minimal item: ``conf`` dict, callable to record the written value."""

    def __init__(self, nut_var):
        self.conf = {'nut_var': nut_var}
        self.values = []

    def __call__(self, value=None):
        self.values.append(value)

    def __str__(self):
        return f'fake.{self.conf["nut_var"]}'


class TestNutPoll(unittest.TestCase):
    def setUp(self):
        self.server = _NutServer()
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self._shutdown)

    def _shutdown(self):
        self.server.shutdown()
        self.server.server_close()

    def _plugin(self):
        from plugins.nut import NUT

        NUT._parameters = {
            'ups': UPS,
            'cycle': 60,
            'host': '127.0.0.1',
            'port': self.server.server_address[1],
            'timeout': 2,
        }
        return NUT(MockSmartHome())

    def test_module_imports_without_telnetlib(self):
        import plugins.nut

        self.assertTrue(hasattr(plugins.nut, 'NUT'))

    def test_poll_updates_bound_items(self):
        plg = self._plugin()
        charge, status, unbound = _FakeItem('battery.charge'), _FakeItem('ups.status'), _FakeItem('no.such.var')
        for item in (charge, status, unbound):
            plg.parse_item(item)

        plg._read_ups()

        self.assertEqual(charge.values, ['100'])
        self.assertEqual(status.values, ['OL CHRG'])
        self.assertEqual(unbound.values, [])

    def test_poll_sends_list_var_request(self):
        plg = self._plugin()

        plg._read_ups()

        self.assertEqual(self.server.requests, [f'LIST VAR {UPS}\n'])

    def test_poll_connection_refused_is_swallowed(self):
        plg = self._plugin()
        plg._port = 1
        item = _FakeItem('battery.charge')
        plg.parse_item(item)

        plg._read_ups()

        self.assertEqual(item.values, [])

    def test_poll_times_out_without_end_marker(self):
        self.server.reply = f'BEGIN LIST VAR {UPS}\nVAR {UPS} battery.charge "100"\n'
        plg = self._plugin()
        plg._timeout = 0.3
        item = _FakeItem('battery.charge')
        plg.parse_item(item)

        plg._read_ups()

        self.assertEqual(item.values, ['100'])
