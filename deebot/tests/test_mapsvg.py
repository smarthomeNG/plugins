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
Post-processing of the map SVG of deebot-client; the fixture has the structure of a real N20 Pro Plus map (floor,
rooms, outlines, one long cleaning trace path, robot, charger, trailing style element) with a shortened trace.
"""

import os
import xml.etree.ElementTree as ET

import pytest

from plugins.deebot.mapsvg import parse_map_css, process_map_svg

with open(os.path.join(os.path.dirname(__file__), 'fixtures', 'map.svg')) as file:
    SVG = file.read()


def test_without_options_the_svg_is_unchanged():
    assert process_map_svg(SVG) == SVG


class TestTrace:
    def test_trace_can_be_removed(self):
        result = process_map_svg(SVG, trace=False)

        assert 'stroke="#fff" stroke-linejoin' not in result
        assert result.count('<path') == SVG.count('<path') - 1

    def test_removal_keeps_everything_else(self):
        result = process_map_svg(SVG, trace=False)

        for part in ('class="u"', 'class="r0"', 'class="r1"', '<use href="#d"', '<use href="#c"', '<style>'):
            assert part in result

    def test_result_is_well_formed_xml(self):
        ET.fromstring(process_map_svg(SVG, trace=False))

    def test_the_removed_path_is_the_long_one(self):
        assert len(process_map_svg(SVG, trace=False)) < len(SVG) - 100


class TestCss:
    def test_css_is_added_at_the_end_of_the_style_element(self):
        result = process_map_svg(SVG, css='.u{fill: transparent}')

        assert result.endswith('.s2 path{stroke-width: 2}.u{fill: transparent}</style></svg>')

    def test_result_is_well_formed_xml(self):
        root = ET.fromstring(process_map_svg(SVG, css='.u{fill: transparent}'))

        style = root.find('{http://www.w3.org/2000/svg}style')
        assert style is not None and style.text is not None and style.text.endswith('.u{fill: transparent}')

    def test_svg_without_style_element_is_left_alone(self):
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><g/></svg>'

        assert process_map_svg(svg, css='.u{fill: transparent}') == svg

    def test_both_options_combine(self):
        result = process_map_svg(SVG, css='.u{fill: none}', trace=False)

        assert '.u{fill: none}</style>' in result
        ET.fromstring(result)


class TestParseCss:
    def test_plain_css_is_accepted(self):
        assert parse_map_css(' .u{fill: transparent} ') == '.u{fill: transparent}'

    def test_empty_is_accepted(self):
        assert parse_map_css('') == ''

    @pytest.mark.parametrize('css', ['</style><script>x</script>', '.u{fill: red}<'])
    def test_markup_is_rejected(self, css):
        with pytest.raises(ValueError, match='<'):
            parse_map_css(css)
