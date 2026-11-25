#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-  Sebastian Helms                 Morg @ knx-user-forum
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#
#  SmartHomeNG is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHomeNG is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHomeNG. If not, see <http://www.gnu.org/licenses/>.
#
#########################################################################

"""
smartVISU widgets: the macros address items of the plugin's structs and the scripts use the plugin's values.

smartVISU itself is not available here; the macros are rendered with Jinja2 (their syntax is the common subset with
Twig) and the pure functions of deebot.js run in Node.js.
"""

import json
import os
import re
import shutil
import subprocess

import jinja2
import pytest
from ruamel.yaml import YAML
from deebot_client.events import FanSpeedLevel

from plugins.deebot.features import FEATURES

WIDGET_DIR = os.path.join(os.path.dirname(__file__), '..', 'sv_widgets')
JS_PATH = os.path.join(WIDGET_DIR, 'deebot.js')

with open(os.path.join(os.path.dirname(__file__), '..', 'plugin.yaml')) as file:
    STRUCTS = YAML(typ='safe').load(file)['item_structs']
with open(JS_PATH) as file:
    JS_SOURCE = file.read()


needs_node = pytest.mark.skipif(shutil.which('node') is None, reason='Node.js not installed')


# stands in for smartVISU's basic.html, which is not available here
BASIC_STUB = (
    '{% macro select(id, item, type, value, icon, text) %}'
    '<select data-item="{{ item }}" data-values="{{ value|join(",") }}" data-texts="{{ text|join(",") }}"></select>'
    '{% endmacro %}'
)


def render(macro, *args):
    with open(os.path.join(WIDGET_DIR, 'deebot.html')) as file:
        loader = jinja2.DictLoader({'@widgets/basic.html': BASIC_STUB, 'deebot.html': file.read()})
    env = jinja2.Environment(loader=loader)
    env.globals['uid'] = lambda page, id: f'{page}-{id}'
    env.globals['page'] = 'p'
    env.globals['implode'] = lambda items: ', '.join(items)  # twig_implode() of smartVISU
    return str(getattr(env.get_template('deebot.html').make_module(), macro)(*args))


def search(pattern, text, flags=0):
    match = re.search(pattern, text, flags)
    assert match is not None, pattern
    return match


def attribute(html, name):
    return search(rf'{name}="([^"]*)"', html).group(1)


def node(expression):
    """Evaluate a JavaScript expression using deebot.js and return its JSON value."""
    script = f'const w = require({json.dumps(os.path.abspath(JS_PATH))}); console.log(JSON.stringify({expression}));'
    return json.loads(subprocess.run(['node', '-e', script], capture_output=True, text=True, check=True).stdout)


class TestPanelMacro:
    def html(self, parts=None):
        args = ('x', 'saugroboter') if parts is None else ('x', 'saugroboter', parts)
        return render('panel', *args)

    def locate(self, path):
        """(group, name) of the struct item a ``saugroboter.<group>.<name>`` path addresses."""
        base, group, name = path.split('.')
        assert base == 'saugroboter'
        return group, name

    @needs_node
    def test_listened_items_follow_the_script_order_below_the_base_item(self):
        paths = attribute(self.html(['brush', 'filter']), 'data-item').split(', ')
        names = [self.locate(path)[1] for path in paths]

        assert names == node('w.DEEBOT_PANEL_FIELDS') + ['lifespan_brush', 'lifespan_filter']

    def test_every_listened_item_is_an_item_of_the_struct_at_that_path(self):
        for path in attribute(self.html(), 'data-item').split(', '):
            group, name = self.locate(path)
            assert STRUCTS[group][name]['deebot@instance'] == name

    @needs_node
    def test_every_write_target_of_the_script_is_passed_as_item(self):
        html = self.html()

        for name in node('w.DEEBOT_PANEL_TARGETS'):
            group, item = self.locate(attribute(html, 'data-item-' + name.replace('_', '-')))
            assert item == name
            assert STRUCTS[group][name]['visu_acl'] == 'rw'

    def test_items_are_separated_by_comma_and_space(self):
        # smartVISU finds the widgets of an item with [data-item~="item"], [data-item~="item,"]: whitespace-separated words
        items = attribute(self.html(['brush', 'filter']), 'data-item')

        assert len(items.split()) == len(items.split(', '))
        assert all(word.endswith(',') for word in items.split()[:-1])

    @pytest.mark.parametrize(
        ('feature', 'values'),
        [('fan_speed', [level.name.lower() for level in FanSpeedLevel]), ('water_amount', ['low', 'medium', 'high'])],
    )
    def test_dropdowns_offer_the_plugins_values_for_the_settings_items(self, feature, values):
        select = search(
            rf'<select data-item="([^"]*{feature})" data-values="([^"]*)" data-texts="([^"]*)"', self.html()
        )
        path, offered, texts = select.groups()

        group, name = self.locate(path)
        assert name == feature
        assert STRUCTS[group][name]['visu_acl'] == 'rw'
        assert set(offered.split(',')) <= set(values)
        assert len(texts.split(',')) == len(offered.split(','))

    def test_no_popup_by_default(self):
        html = self.html()

        assert 'data-rel="popup"' not in html
        assert 'deebot.map' not in html

    def test_popup_button_opens_a_popup_holding_the_map_widget(self):
        html = render('panel', 'x', 'saugroboter', ['brush'], '', True)

        target = search(r'href="#([^"]*)" data-rel="popup"', html).group(1)
        popup = search(rf'<div id="{target}" data-role="popup".*?</div>\s*</div>', html, re.S).group(0)
        assert 'data-widget="deebot.map"' in popup
        assert attribute(popup, 'data-item') == 'saugroboter.map.map_svg'

    def test_wear_parts_are_configurable(self):
        html = self.html(['brush'])

        assert attribute(html, 'data-parts') == 'brush'
        assert attribute(html, 'data-item').endswith(', saugroboter.lifespan.lifespan_brush')
        assert 'lifespan_filter' not in html

    def test_default_wear_parts_are_known_features(self):
        for part in attribute(self.html(), 'data-parts').split(','):
            assert f'lifespan_{part}' in FEATURES


def test_map_macro_uses_the_map_item():
    assert attribute(render('map', 'x', 'saugroboter'), 'data-item') == 'saugroboter.map.map_svg'


class TestScriptAgreesWithPlugin:
    def test_state_labels_cover_all_plugin_states(self):
        from deebot_client.models import State

        labels = search(r'DEEBOT_STATE_LABELS = \{(.*?)\};', JS_SOURCE, re.S).group(1)

        assert {s.name.lower() for s in State} == set(re.findall(r'^\s+(\w+):', labels, re.M))


@needs_node
class TestScriptFunctions:
    @pytest.mark.parametrize(
        ('state', 'cmd'),
        [
            ('cleaning', 'cmd_pause'),
            ('returning', 'cmd_pause'),
            ('paused', 'cmd_resume'),
            ('docked', 'cmd_start'),
            ('idle', 'cmd_start'),
            ('error', 'cmd_start'),
            (None, 'cmd_start'),
        ],
    )
    def test_primary_button_follows_state(self, state, cmd):
        assert node(f'w.deebotPrimaryAction({json.dumps(state)}).cmd') == cmd

    def test_unreachable_vacuum_is_labelled_so(self):
        assert node("w.deebotStateLabel('cleaning', false)") == 'nicht erreichbar'

    @pytest.mark.parametrize(
        ('state', 'available', 'css'),
        [
            ('cleaning', 'true', 'deebot-state-cleaning'),
            ('error', 'true', 'deebot-state-error'),
            ('docked', 'true', ''),
            ('cleaning', 'false', 'deebot-state-unavailable'),
        ],
    )
    def test_state_css_class(self, state, available, css):
        assert node(f"w.deebotStateClass('{state}', {available})") == css

    def test_state_label(self):
        assert node("w.deebotStateLabel('docked', true)") == 'in der Station'

    def test_rooms_from_list(self):
        assert node("w.deebotRooms([{id: 3, name: 'Küche', preselect: true}, {id: '4'}])") == [
            {'id': 3, 'name': 'Küche', 'preselect': True},
            {'id': 4, 'name': '4', 'preselect': False},
        ]

    def test_rooms_are_ordered_by_id(self):
        rooms = "[{id: 8, name: 'a'}, {id: 1, name: 'b'}, {id: 2, name: 'c'}]"

        assert [room['id'] for room in node(f'w.deebotRooms({rooms})')] == [1, 2, 8]

    def test_rooms_from_json_text(self):
        assert node("""w.deebotRooms('[{"id": 3, "name": "Küche"}]')""") == [
            {'id': 3, 'name': 'Küche', 'preselect': False}
        ]

    @pytest.mark.parametrize(('seconds', 'text'), [(5280, '88 min'), (0, '0 min'), (29, '0 min'), (90, '2 min')])
    def test_duration_in_minutes(self, seconds, text):
        assert node(f'w.deebotMinutes({seconds})') == text

    def test_room_labels_add_the_id_only_to_shared_names(self):
        rooms = "[{id: 3, name: 'Default'}, {id: 4, name: 'Default'}, {id: 5, name: 'Küche'}]"

        assert node(f'w.deebotRoomLabels({rooms})') == ['Default (3)', 'Default (4)', 'Küche']

    @pytest.mark.parametrize('value', ['null', "'not json'", '5', '[null, {}]'])
    def test_rooms_from_garbage_are_empty(self, value):
        assert node(f'w.deebotRooms({value})') == []

    @pytest.mark.parametrize(
        ('value', 'expected'), [('55', 55), ("'12.5'", 12.5), ('150', 100), ('-3', 0), ('null', None)]
    )
    def test_percent_is_clamped(self, value, expected):
        assert node(f'w.deebotPercent({value})') == expected
