"""The maintenance tab of the web interface lists the devices found on the bridge and the devices addressed by items."""

import pathlib

import jinja2

from plugins.zigbee2mqtt import webif

from .base import Zigbee2MqttTestBase


def render_maintenance_tab(plugin) -> str:
    """Render the maintenance tab of the real index.html into a bare base template."""
    templates = pathlib.Path(webif.__file__).parent / 'templates'
    base = jinja2.DictLoader({'base_plugin.html': '{% block bodytab4 %}{% endblock %}'})
    env = jinja2.Environment(
        loader=jinja2.ChoiceLoader([base, jinja2.FileSystemLoader(templates)]), extensions=['jinja2.ext.i18n']
    )
    env.install_null_translations()
    return env.get_template('index.html').render(p=plugin, plugin_shortname='zigbee2mqtt')


def table(html: str, table_id: str) -> str:
    """The part of ``html`` from the table with ``table_id`` to the end of that table."""
    start = html.index(f'id="{table_id}"')
    return html[start : html.index('</table>', start)]


class TestMaintenanceTab(Zigbee2MqttTestBase):
    def setUp(self):
        self.zigbee = self.plugin()
        self.zigbee._devices['dev1']['meta'] = {'friendly_name': 'dev1', 'vendor': 'IKEA'}
        self.zigbee._devices['dev1']['data'] = {'linkquality': 87}
        self.zigbee._devices['dev2'] = {'meta': {'friendly_name': 'dev2'}, 'data': {'linkquality': 12}}
        self.html = render_maintenance_tab(self.zigbee)

    def test_found_devices_are_listed_with_meta_and_data(self):
        found = table(self.html, 'mtable1')

        self.assertIn('dev1', found)
        self.assertIn('IKEA', found)
        self.assertIn("'linkquality': 87", found)
        self.assertIn('dev2', found)
        self.assertIn("'linkquality': 12", found)

    def test_devices_addressed_by_items_are_listed_with_their_items(self):
        addressed = table(self.html, 'mtable2')

        self.assertIn('dev1', addressed)
        self.assertIn('temperature', addressed)
        self.assertIn('dev1.temp', addressed)

    def test_devices_without_items_are_not_listed_as_addressed(self):
        self.assertNotIn('dev2', table(self.html, 'mtable2'))
