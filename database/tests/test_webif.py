import os
from unittest import mock

from plugins.database.tests.base import TestDatabaseBase
from plugins.database.webif import WebInterface


class TestDatabaseWebifItemCsv(TestDatabaseBase):
    def _webif(self, plugin):
        # Bypass WebInterface.__init__() (it wires up the Jinja2 template
        # environment via self.plugin.mod_http, which the lightweight test
        # plugin fixture doesn't set up) - item_csv() itself never touches
        # the template environment, only self.plugin.
        webif = WebInterface.__new__(WebInterface)
        webif.logger = plugin.logger
        webif.webif_dir = ''
        webif.plugin = plugin
        webif.items = plugin.items
        return webif

    def test_item_csv_rejects_non_numeric_item_id(self):
        plugin = self.plugin()
        webif = self._webif(plugin)
        # A malformed/malicious item_id must not reach the filesystem at all.
        traversal_target = os.path.join(self.sh.base_dir, 'var', 'db', '_item_../../../../../../tmp/pwned.csv')
        self.assertFalse(os.path.exists(traversal_target))

        result = webif.item_csv('../../../../../../tmp/pwned')

        self.assertIsNone(result)
        self.assertFalse(os.path.exists(traversal_target))

    def test_item_csv_accepts_numeric_item_id(self):
        plugin = self.plugin()
        webif = self._webif(plugin)
        id = self.create_item(plugin, 'main.num')
        plugin.insertLog(id, time=0, duration=3600, val=10, it='num')

        # item_csv() writes to <base_dir>/var/db/, which is gitignored and
        # not present on a fresh checkout (e.g. CI). Ensure it exists rather
        # than relying on ambient state left behind by a real shng run.
        os.makedirs(os.path.join(self.sh.base_dir, 'var', 'db'), exist_ok=True)

        with (
            mock.patch('cherrypy.request'),
            mock.patch('cherrypy.lib.static.serve_download', return_value='served') as fake_serve,
        ):
            result = webif.item_csv(str(id))

        self.assertEqual('served', result)
        csv_path = fake_serve.call_args[0][0]
        self.addCleanup(lambda: os.path.exists(csv_path) and os.unlink(csv_path))
        self.assertTrue(os.path.isfile(csv_path))
