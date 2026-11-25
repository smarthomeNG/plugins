"""The web interface lists the items registered with a jsonread_filter and reports their current values."""

import json
import os
import pathlib
import unittest

import jinja2

import tests.common as common
from tests.mock.core import MockSmartHome

from plugins.jsonread import JSONREAD, webif

from .base import JsonreadTestBase

common.register_shng_log_levels()

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')
FILTERED_ITEMS = 4


class TestWebInterface(JsonreadTestBase, unittest.TestCase):
    def setUp(self):
        self.sh = MockSmartHome()
        self.sh.with_items_from(os.path.join(FIXTURES_DIR, 'test_items.yaml'))
        JSONREAD._parameters = {
            'url': f'file://{FIXTURES_DIR}/fronius.json',
            'cycle': 30,
            'jq_syntax': True,
            'webif_pagelength': 100,
        }
        self.plg = JSONREAD(self.sh)
        for item in self.sh.items.return_items():
            self.plg.parse_item(item)
        self.plg.poll_device()

        templates = pathlib.Path(webif.__file__).parent / 'templates'
        base = jinja2.DictLoader({'base_plugin.html': '{{ tab2title }}{% block bodytab2 %}{% endblock %}'})
        env = jinja2.Environment(
            loader=jinja2.ChoiceLoader([base, jinja2.FileSystemLoader(templates)]), extensions=['jinja2.ext.i18n']
        )
        env.install_null_translations()
        self.webif = webif.WebInterface.__new__(webif.WebInterface)
        self.webif.plugin = self.plg
        self.webif.logger = self.plg.logger
        self.webif.tplenv = env

    def test_index_lists_the_items_with_filter_and_value(self):
        html = self.webif.index()

        self.assertIn('fronius_smartmeter.current_phase_1', html)
        self.assertIn('.Body.Data["0"].Current_AC_Phase_1', html)
        self.assertIn('0.455', html)

    def test_index_counts_the_items(self):
        self.assertIn(f'{FILTERED_ITEMS} Items definiert', self.webif.index())

    def test_data_update_reports_the_item_values(self):
        data = json.loads(self.webif.get_data_html())

        self.assertEqual(0.455, data['items']['fronius_smartmeter.current_phase_1'])
        self.assertEqual('Fronius', data['items']['fronius_smartmeter.manufacturer'])
        self.assertEqual(FILTERED_ITEMS, len(data['items']))


if __name__ == '__main__':
    unittest.main()
