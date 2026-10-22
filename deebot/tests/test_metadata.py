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

"""plugin.yaml and the feature registry describe the same set of ``deebot`` attribute values."""

import os

from ruamel.yaml import YAML

from plugins.deebot.features import FEATURES
from plugins.deebot.mapsvg import parse_map_css, process_map_svg

with open(os.path.join(os.path.dirname(__file__), '..', 'plugin.yaml')) as file:
    METADATA = YAML(typ='safe').load(file)
with open(os.path.join(os.path.dirname(__file__), 'fixtures', 'map.svg')) as file:
    MAP_SVG = file.read()


def struct_items():
    """(struct, item name, item definition) for every item in the structs that carries the attribute."""
    for struct, definition in METADATA['item_structs'].items():
        for name, item in definition.items():
            if isinstance(item, dict) and 'deebot@instance' in item:
                yield struct, name, item


def test_valid_list_matches_registry():
    assert METADATA['item_attributes']['deebot']['valid_list'] == list(FEATURES)


def test_every_struct_item_uses_a_known_feature_of_matching_type():
    for struct, name, item in struct_items():
        feature = FEATURES[item['deebot@instance']]
        assert item['type'] == feature.item_type, f'{struct}.{name}'


def test_struct_item_names_equal_feature_names():
    for struct, name, item in struct_items():
        assert name == item['deebot@instance'], f'{struct}.{name}'


def test_every_feature_is_in_a_struct():
    assert {item['deebot@instance'] for _, _, item in struct_items()} == set(FEATURES)


def test_visu_acl_follows_writability():
    for struct, name, item in struct_items():
        expected = 'rw' if FEATURES[name].writable else 'ro'
        assert item['visu_acl'] == expected, f'{struct}.{name}'


def test_version_matches_plugin():
    from plugins.deebot import Deebot

    assert METADATA['plugin']['version'] == Deebot.PLUGIN_VERSION


def test_every_struct_item_has_a_remark():
    for struct, name, item in struct_items():
        assert item.get('remark'), f'{struct}.{name}'


def test_struct_names_are_plain_text():
    for struct, definition in METADATA['item_structs'].items():
        assert isinstance(definition['name'], str), struct


def test_map_css_default_makes_the_floor_transparent():
    default = METADATA['parameters']['map_css']['default']

    assert parse_map_css(default) == default
    assert default in process_map_svg(MAP_SVG, css=default)
    assert '.u{fill: transparent}' in default
