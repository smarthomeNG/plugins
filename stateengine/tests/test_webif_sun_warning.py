import os
import unittest
from types import SimpleNamespace

from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), '..', 'webif', 'templates')
BASE_STUB = '{% block headtable %}{% endblock %}'
WARNING_TITLE = 'Sonnenstand nicht verfügbar'


def render_headtable(sun_available):
    """Render the real index.html, with only the base template's headtable block stubbed."""
    env = Environment(
        loader=ChoiceLoader([DictLoader({'base_plugin.html': BASE_STUB}), FileSystemLoader(TEMPLATE_DIR)])
    )
    env.globals['_'] = lambda text: text
    plugin = SimpleNamespace(sun_available=sun_available, get_parameter_value_for_display=lambda name: '')
    return env.get_template('index.html').render(p=plugin, item_count=0)


class TestWebifSunWarning(unittest.TestCase):
    def test_warning_shown_without_sun(self):
        self.assertIn(WARNING_TITLE, render_headtable(sun_available=False))

    def test_no_warning_with_sun(self):
        self.assertNotIn(WARNING_TITLE, render_headtable(sun_available=True))
