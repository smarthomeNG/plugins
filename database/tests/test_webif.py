import datetime
import json
import os
from unittest import mock

from plugins.database.constants import QUALITY_INVALID
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

    def test_item_csv_formats_time_as_local_datetime_string(self):
        plugin = self.plugin()
        webif = self._webif(plugin)
        id = self.create_item(plugin, 'main.num')
        now_ms = int(plugin.shtime.now().timestamp() * 1000)
        plugin.insertLog(id, time=now_ms, duration=3600, val=10, it='num', changed=now_ms)

        os.makedirs(os.path.join(self.sh.base_dir, 'var', 'db'), exist_ok=True)

        with mock.patch('cherrypy.request'), mock.patch('cherrypy.lib.static.serve_download', return_value='served'):
            webif.item_csv(str(id))

        csv_path = os.path.join(self.sh.base_dir, 'var', 'db', f'{plugin.get_instance_name()}_item_{id}.csv')
        self.addCleanup(lambda: os.path.exists(csv_path) and os.unlink(csv_path))
        with open(csv_path, encoding='utf-8') as f:
            lines = f.read().splitlines()
        row = lines[1].split(',')
        expected_time = datetime.datetime.fromtimestamp(now_ms / 1000, tz=plugin.shtime.tzinfo()).isoformat(
            sep=' ', timespec='milliseconds'
        )
        # time is the first column, changed is the second-to-last (before val_quality)
        self.assertEqual(expected_time, row[0])
        self.assertEqual(expected_time, row[-2])

    def test_item_csv_formats_time_as_utc_when_requested(self):
        plugin = self.plugin()
        webif = self._webif(plugin)
        id = self.create_item(plugin, 'main.num')
        now_ms = int(plugin.shtime.now().timestamp() * 1000)
        plugin.insertLog(id, time=now_ms, duration=3600, val=10, it='num', changed=now_ms)

        os.makedirs(os.path.join(self.sh.base_dir, 'var', 'db'), exist_ok=True)

        with mock.patch('cherrypy.request'), mock.patch('cherrypy.lib.static.serve_download', return_value='served'):
            webif.item_csv(str(id), tz='utc')

        csv_path = os.path.join(self.sh.base_dir, 'var', 'db', f'{plugin.get_instance_name()}_item_{id}.csv')
        self.addCleanup(lambda: os.path.exists(csv_path) and os.unlink(csv_path))
        with open(csv_path, encoding='utf-8') as f:
            lines = f.read().splitlines()
        row = lines[1].split(',')
        expected_time = datetime.datetime.fromtimestamp(now_ms / 1000, tz=datetime.timezone.utc).isoformat(
            sep=' ', timespec='milliseconds'
        )
        self.assertEqual(expected_time, row[0])

    def test_item_csv_filters_by_time_range(self):
        plugin = self.plugin()
        webif = self._webif(plugin)
        id = self.create_item(plugin, 'main.num')
        plugin.insertLog(id, time=0, duration=1000, val=1, it='num', changed=0)
        plugin.insertLog(id, time=5000, duration=1000, val=2, it='num', changed=5000)
        plugin.insertLog(id, time=10000, duration=1000, val=3, it='num', changed=10000)

        os.makedirs(os.path.join(self.sh.base_dir, 'var', 'db'), exist_ok=True)

        with mock.patch('cherrypy.request'), mock.patch('cherrypy.lib.static.serve_download', return_value='served'):
            webif.item_csv(str(id), time_start='4000', time_end='9000')

        csv_path = os.path.join(self.sh.base_dir, 'var', 'db', f'{plugin.get_instance_name()}_item_{id}.csv')
        self.addCleanup(lambda: os.path.exists(csv_path) and os.unlink(csv_path))
        with open(csv_path, encoding='utf-8') as f:
            lines = f.read().splitlines()
        # header + exactly the one row inside [4000, 9000]
        self.assertEqual(2, len(lines))
        self.assertEqual(2.0, float(lines[1].split(',')[4]))  # val_num column

    def test_item_csv_ignores_malformed_time_range(self):
        plugin = self.plugin()
        webif = self._webif(plugin)
        id = self.create_item(plugin, 'main.num')
        plugin.insertLog(id, time=0, duration=1000, val=1, it='num', changed=0)

        os.makedirs(os.path.join(self.sh.base_dir, 'var', 'db'), exist_ok=True)

        with mock.patch('cherrypy.request'), mock.patch('cherrypy.lib.static.serve_download', return_value='served'):
            result = webif.item_csv(str(id), time_start='not-a-number')

        self.assertEqual('served', result)
        csv_path = os.path.join(self.sh.base_dir, 'var', 'db', f'{plugin.get_instance_name()}_item_{id}.csv')
        self.addCleanup(lambda: os.path.exists(csv_path) and os.unlink(csv_path))
        with open(csv_path, encoding='utf-8') as f:
            lines = f.read().splitlines()
        # malformed time_start is ignored, not fatal - row still exported unbounded
        self.assertEqual(2, len(lines))

    def test_item_csv_includes_val_quality_column(self):
        plugin = self.plugin()
        webif = self._webif(plugin)
        id = self.create_item(plugin, 'main.num')
        plugin.insertLog(id, time=0, duration=3600, val=10, it='num')
        plugin.markLogInvalid(id, time=0)

        os.makedirs(os.path.join(self.sh.base_dir, 'var', 'db'), exist_ok=True)

        with mock.patch('cherrypy.request'), mock.patch('cherrypy.lib.static.serve_download', return_value='served'):
            webif.item_csv(str(id))

        csv_path = os.path.join(self.sh.base_dir, 'var', 'db', f'{plugin.get_instance_name()}_item_{id}.csv')
        self.addCleanup(lambda: os.path.exists(csv_path) and os.unlink(csv_path))
        with open(csv_path, encoding='utf-8') as f:
            lines = f.read().splitlines()
        self.assertEqual('time,item_id,duration,val_str,val_num,val_bool,changed,val_quality', lines[0])
        self.assertTrue(lines[1].endswith(str(QUALITY_INVALID)))


class TestDatabaseWebifItemDetails(TestDatabaseBase):
    def _webif(self, plugin):
        # Same bypass as TestDatabaseWebifItemCsv - get_data_html() never
        # touches the template environment either, only self.plugin.
        webif = WebInterface.__new__(WebInterface)
        webif.logger = plugin.logger
        webif.webif_dir = ''
        webif.plugin = plugin
        webif.items = plugin.items
        return webif

    def test_get_data_html_item_details_includes_val_quality(self):
        plugin = self.plugin()
        webif = self._webif(plugin)
        id = self.create_item(plugin, 'main.num')
        now_ms = int(plugin.shtime.now().timestamp() * 1000)
        plugin.insertLog(id, time=now_ms, duration=3600, val=10, it='num', changed=now_ms)
        plugin.markLogInvalid(id, time=now_ms)

        data = json.loads(webif.get_data_html(dataSet='item_details', params=str(id)))

        self.assertEqual(1, len(data))
        # dict keys become JSON strings on the wire - same as the existing
        # numeric-index keys (e.g. '4' for val_num) this endpoint already emits.
        self.assertEqual(QUALITY_INVALID, data[0]['7'])  # val_quality column
        self.assertEqual(10, data[0]['4'])  # val_num still present alongside the flag


class TestDatabaseWebifIndexDispatch(TestDatabaseBase):
    def _webif(self, plugin):
        # index() DOES reach the template environment once dispatch falls
        # through to the item_details render - stub it out (unlike the
        # item_csv/get_data_html bypass, which never touches it at all) so
        # the dispatch logic itself can still be exercised for real.
        webif = WebInterface.__new__(WebInterface)
        webif.logger = plugin.logger
        webif.webif_dir = ''
        webif.plugin = plugin
        webif.items = plugin.items
        webif.tplenv = mock.MagicMock()
        return webif

    def test_invalidate_log_action_flags_row_and_renders_item_details(self):
        plugin = self.plugin()
        webif = self._webif(plugin)
        id = self.create_item(plugin, 'main.num')
        plugin.insertLog(id, time=0, duration=3600, val=10, it='num', changed=0)

        webif.index(action='invalidate_log', item_id=id, item_path='main.num', time_orig=0, changed_orig=0)

        res = plugin.readLog(id, time=0)
        self.assertEqual(QUALITY_INVALID, res[0][7])
        self.assertEqual(10, res[0][4])  # value preserved, not deleted
        render_kwargs = webif.tplenv.get_template.return_value.render.call_args.kwargs
        self.assertEqual('item_details', render_kwargs['action'])
        self.assertTrue(render_kwargs['invalidate_triggered'])

    def test_restore_log_action_clears_invalid_flag(self):
        plugin = self.plugin()
        webif = self._webif(plugin)
        id = self.create_item(plugin, 'main.num')
        plugin.insertLog(id, time=0, duration=3600, val=10, it='num', changed=0)
        plugin.markLogInvalid(id, time=0)

        webif.index(action='restore_log', item_id=id, item_path='main.num', time_orig=0, changed_orig=0)

        res = plugin.readLog(id, time=0)
        self.assertEqual(0, res[0][7])  # QUALITY_VALID
        render_kwargs = webif.tplenv.get_template.return_value.render.call_args.kwargs
        self.assertTrue(render_kwargs['restore_triggered'])

    def test_item_details_render_exposes_day_range_for_csv_export(self):
        plugin = self.plugin()
        webif = self._webif(plugin)
        id = self.create_item(plugin, 'main.num')
        plugin.insertLog(id, time=0, duration=3600, val=10, it='num', changed=0)

        webif.index(action='item_details', item_id=id, item_path='main.num', day=1, month=1, year=2026)

        render_kwargs = webif.tplenv.get_template.return_value.render.call_args.kwargs
        self.assertEqual('item_details', render_kwargs['action'])
        # a full calendar day in ms, matching the day/month/year requested
        self.assertEqual(24 * 60 * 60 * 1000, render_kwargs['csv_time_end'] - render_kwargs['csv_time_start'])
        self.assertIsInstance(render_kwargs['csv_time_start'], int)
        self.assertIsInstance(render_kwargs['csv_time_end'], int)

    def test_delete_log_bulk_action_still_hard_deletes(self):
        """The bulk 'clear entire history' action (no time_orig/changed_orig) must
        remain a real delete - only the single-row path became reversible."""
        plugin = self.plugin()
        webif = self._webif(plugin)
        id = self.create_item(plugin, 'main.num')
        plugin.insertLog(id, time=0, duration=3600, val=10, it='num', changed=0)

        webif.index(action='delete_log', item_id=id, item_path='main.num')

        res = plugin.readLog(id, time=0)
        self.assertEqual(0, len(res))
