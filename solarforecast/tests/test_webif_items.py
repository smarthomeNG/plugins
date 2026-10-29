"""The item list of the web interface shows the items the plugin has registered per solarforecast_attribute."""

import datetime
import pathlib
import unittest

import jinja2

from plugins.solarforecast import Solarforecast, webif


class StubItem:
    """Item stand-in with the properties the template reads."""

    def __init__(self, path, value):
        stamp = datetime.datetime(2026, 10, 29, 14, 22, 54)
        self.property = type('Property', (), {'path': path, 'type': 'num', 'last_update': stamp, 'last_change': stamp})
        self._value = value

    def __call__(self):
        return self._value


def make_plugin(**lookup):
    plugin = Solarforecast.__new__(Solarforecast)
    plugin._item_lookup_dict = lookup
    return plugin


def render_item_tab(plugin):
    """Render the first tab of the real index.html into a bare base template."""
    templates = pathlib.Path(webif.__file__).parent / 'templates'
    base = jinja2.DictLoader({'base_plugin.html': '{% block bodytab1 %}{% endblock %}'})
    env = jinja2.Environment(
        loader=jinja2.ChoiceLoader([base, jinja2.FileSystemLoader(templates)]), extensions=['jinja2.ext.i18n']
    )
    env.install_null_translations()
    return env.get_template('index.html').render(p=plugin)


class TestWebifItems(unittest.TestCase):
    def test_get_items_returns_the_registered_items_per_attribute(self):
        energy = StubItem('solar.energy_today', 12.5)
        plugin = make_plugin(energy_today=[energy])

        self.assertEqual({'energy_today': [energy]}, plugin.get_items())

    def test_item_tab_lists_every_registered_item(self):
        plugin = make_plugin(
            energy_today=[StubItem('solar.energy_today', 12.5)],
            energy_tomorrow=[StubItem('solar.energy_tomorrow', 7.0)],
        )

        html = render_item_tab(plugin)

        self.assertIn('solar.energy_today', html)
        self.assertIn('solar.energy_tomorrow', html)
        self.assertIn('(2)', html)

    def test_item_tab_without_items(self):
        self.assertIn('(0)', render_item_tab(make_plugin()))
