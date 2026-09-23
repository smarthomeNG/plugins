#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Tests for plugins/matter/webif: pages rendered through the real Jinja
environment (plugin templates extending the http module's global
templates), the action table, and the auto-update payload - with device
data from a WsPeer standing in for matter-server.
"""

import json
import os
import unittest

import lib.module
from plugins.matter.tests.support import PluginHarness, connect_client
from plugins.matter.tests.test_server_role import NODE_3, MatterServerPeer
from plugins.matter.webif import WebInterface

GTEMPLATES = os.path.join(os.path.dirname(lib.module.__file__), '..', 'modules', 'http', 'webif', 'gtemplates')
HOSTILE = '<script>alert(1)</script>\'"'

ITEMS = """
matter:
    aliases:
        kitchen:
            type: num
            value: 3
dev:
    matter_node: 3
    matter_endpoint: 1
    label:
        type: str
        matter_cluster: 40
        matter_attribute: 5
"""


class _NoModules:
    def get_module(self, name):
        return None


class _WebifTest(unittest.TestCase):
    def setUp(self):
        saved = lib.module._modules_instance
        lib.module._modules_instance = _NoModules()
        self.addCleanup(setattr, lib.module, '_modules_instance', saved)

        self.harness = PluginHarness(ITEMS)
        self.addCleanup(self.harness.close)
        self.plugin = self.harness.plugin
        self.plugin.mod_http = type('ModHttp', (), {'gtemplates_dir': os.path.abspath(GTEMPLATES)})()
        self.webif = WebInterface(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'webif'), self.plugin)

        self.peer = MatterServerPeer().start()
        self.addCleanup(self.peer.stop)
        hostile_node = {**NODE_3, 'attributes': {**NODE_3['attributes'], '0/40/5': HOSTILE, '0/40/3': HOSTILE}}
        self.peer.nodes = [hostile_node]
        self.harness.start_loop()
        connect_client(self.harness, self.plugin.server, self.peer.url + '/ws')


class TestEscaping(_WebifTest):
    def test_device_strings_are_escaped_in_html_and_never_inlined_into_js(self):
        html = self.webif._render_server({})

        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', html)
        self.assertIn('onclick="unlinkDevice(this)"', html)
        self.assertNotIn("unlinkDevice(3, '", html)

    def test_missing_label_placeholder_is_visible_text(self):
        self.peer.nodes = [NODE_3]

        html = self.webif._render_server({})

        self.assertIn('&lt;nicht gesetzt&gt;', html)

    def test_global_template_markup_stays_unescaped(self):
        html = self.webif._render_server({})

        self.assertIn('<strong>', html)
        self.assertNotIn('&lt;strong&gt;', html)

    def test_poll_payload_carries_raw_values(self):
        self.harness.item('dev.label')(HOSTILE, 'test')

        data = json.loads(self.webif.get_data_html())

        self.assertEqual(data['items']['dev.label'], HOSTILE)
        self.assertEqual(data['devices'], {'3': True})

    def test_page_inserts_polled_values_as_text(self):
        with open(os.path.join(self.webif.webif_dir, 'templates', 'index.html')) as f:
            calls = [line for line in f if 'shngInsertText(' in line]

        self.assertTrue(calls)
        self.assertFalse([line for line in calls if 'true' in line.split('shngInsertText(', 1)[1]])


class TestActions(_WebifTest):
    def test_actions_of_the_view_run_and_report_errors_as_flash(self):
        self.peer.error_for.add('interview_node')

        flash = self.webif.run_actions('server', {'interview_node_id': '3', 'fabrics_node_id': '3'})

        self.assertIn('interview_node rejected', flash['interview_error'])
        self.assertEqual(flash['fabrics_result']['node_id'], 3)
        self.assertEqual(self.peer.commands('get_matter_fabrics')[0]['args'], {'node_id': 3})

    def test_bridge_actions_do_not_run_on_the_server_view(self):
        flash = self.webif.run_actions('server', {'open_bridge_window': '1'})

        self.assertEqual(flash, {})

    def test_malformed_request_is_a_flash_error(self):
        flash = self.webif.run_actions('server', {'unlink_node_id': 'x'})

        self.assertIn('invalid request', flash['request_error'])
        self.assertEqual(self.peer.commands('remove_node'), [])

    def test_repoint_action_changes_the_alias(self):
        self.webif.run_actions('server', {'alias_repoint_name': 'kitchen', 'alias_repoint_node_id': '7'})

        self.assertEqual(self.plugin.server.aliases.snapshot()['kitchen'], 7)

    def test_commission_action_starts_a_job_shown_by_the_poll(self):
        flash = self.webif.run_actions('server', {'pairing_code': 'MT:ABC'})

        jobs = json.loads(self.webif.get_data_html())['commission_jobs']
        self.assertEqual(flash, {})
        self.assertEqual(len(jobs), 1)
        self.assertIn(jobs[0]['state'], ('pending', 'succeeded'))

    def test_bridge_view_renders_with_the_bridge_disconnected(self):
        html = self.webif._render_bridge({})

        self.assertIn('Bridge nicht verbunden', html)


if __name__ == '__main__':
    unittest.main()
