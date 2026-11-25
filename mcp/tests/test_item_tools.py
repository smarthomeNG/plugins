import os

import pytest

from plugins.mcp.tools import ItemTools
from plugins.mcp.types import DefaultAccess, Entitlement, ToolFailure
from tests.mock.core import MockSmartHome

FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures', 'access_items.yaml')


def entitlement(default_access: DefaultAccess = 'none', inherit_rw_access: bool = False) -> Entitlement:
    return Entitlement('local', default_access, inherit_rw_access, frozenset(), 30)


class TestGetItem:
    def setup_method(self):
        sh = MockSmartHome()
        sh.with_items_from(FIXTURE)
        assert sh.items is not None
        self.tools = ItemTools(sh.items, entitlement())

    def test_visible_item_returns_summary(self):
        assert self.tools.get_item('house.living.temp') == {
            'path': 'house.living.temp',
            'type': 'num',
            'value': 21.5,
            'access': 'ro',
        }

    def test_invisible_and_missing_items_are_indistinguishable(self):
        with pytest.raises(ToolFailure) as invisible:
            self.tools.get_item('unmarked')
        with pytest.raises(ToolFailure) as missing:
            self.tools.get_item('does.not.exist')
        assert invisible.value.code == 'not_found'
        assert (invisible.value.code, invisible.value.message) == (missing.value.code, missing.value.message)


VISIBLE_PATHS = [
    'house',
    'house.garage',
    'house.garage.door',
    'house.living',
    'house.living.lamp',
    'house.living.lamp.dimmer',
    'house.living.temp',
]


class TestListItems:
    def setup_method(self):
        sh = MockSmartHome()
        sh.with_items_from(FIXTURE)
        assert sh.items is not None
        self.items = sh.items

    def tools(self, **kwargs):
        return ItemTools(self.items, entitlement(), **kwargs)

    def test_lists_only_visible_items_ordered_by_path(self):
        result = self.tools().list_items()
        assert [entry['path'] for entry in result['items']] == VISIBLE_PATHS
        assert result['cursor'] is None
        assert result['items'][-1] == {'path': 'house.living.temp', 'type': 'num', 'value': 21.5, 'access': 'ro'}

    def test_prefix_selects_the_item_and_its_descendants_only(self):
        result = self.tools().list_items(prefix='house.living')
        assert [entry['path'] for entry in result['items']] == [
            'house.living',
            'house.living.lamp',
            'house.living.lamp.dimmer',
            'house.living.temp',
        ]

    def test_prefix_matches_whole_path_segments(self):
        assert self.tools().list_items(prefix='house.liv')['items'] == []

    def test_type_filter(self):
        result = self.tools().list_items(type='num')
        assert [entry['path'] for entry in result['items']] == ['house.living.lamp.dimmer', 'house.living.temp']

    def test_pages_cover_all_items_exactly_once(self):
        tools = self.tools()
        paths: list[str] = []
        cursor = None
        pages = 0
        while True:
            result = tools.list_items(limit=3, cursor=cursor)
            assert len(result['items']) <= 3
            paths += [entry['path'] for entry in result['items']]
            pages += 1
            cursor = result['cursor']
            if cursor is None:
                break
        assert paths == VISIBLE_PATHS
        assert pages == 3

    def test_page_size_is_capped(self):
        result = self.tools(max_page_size=2).list_items(limit=50)
        assert len(result['items']) == 2
        assert result['cursor'] is not None

    def test_default_limit_applies(self):
        assert self.tools(default_page_size=4).list_items()['cursor'] is not None

    @pytest.mark.parametrize('limit', [0, -1])
    def test_non_positive_limit_is_rejected(self, limit):
        with pytest.raises(ToolFailure) as failure:
            self.tools().list_items(limit=limit)
        assert failure.value.code == 'bad_request'

    def test_invalid_cursor_is_rejected(self):
        with pytest.raises(ToolFailure) as failure:
            self.tools().list_items(cursor='!!not-a-cursor!!')
        assert failure.value.code == 'bad_request'

    def test_has_attr_selects_items_carrying_the_attribute(self):
        result = self.tools().list_items(has_attr='mcp_access')
        assert [entry['path'] for entry in result['items']] == ['house', 'house.garage', 'house.living.lamp']


class TestGetItemDetail:
    def setup_method(self):
        sh = MockSmartHome()
        sh.with_items_from(FIXTURE)
        assert sh.items is not None
        self.tools = ItemTools(sh.items, entitlement())

    def test_value_detail_is_the_default_summary(self):
        assert self.tools.get_item('house.living.temp', detail='value') == self.tools.get_item('house.living.temp')

    def test_full_detail_extends_the_summary(self):
        detail = self.tools.get_item('house.living.temp', detail='full')
        assert detail['path'] == 'house.living.temp'
        assert detail['value'] == 21.5
        assert detail['access'] == 'ro'
        assert detail['name'] == 'Living temperature'
        assert detail['description'] == 'Temperature in the living room'
        assert detail['parent'] == 'house.living'
        assert detail['children'] == []

    def test_full_detail_lists_visible_children_only(self):
        assert self.tools.get_item('house', detail='full')['children'] == ['house.garage', 'house.living']

    def test_full_detail_exposes_triggers_and_timestamps(self):
        detail = self.tools.get_item('house.living.temp', detail='full')
        assert detail['triggers']['eval'] == ['value * 1']
        assert detail['triggers']['eval_trigger'] == ['house.living.lamp']
        assert detail['last_update'] is None or 'T' in detail['last_update']
        assert 'last_change_by' in detail and 'last_update_by' in detail and 'previous_value' in detail

    def test_attributes_hide_secret_looking_names(self):
        attributes = self.tools.get_item('house.living.temp', detail='full')['attributes']
        assert attributes['knx_dpt'] == '9.001'
        assert 'knx_password' not in attributes

    def test_unknown_detail_is_rejected(self):
        with pytest.raises(ToolFailure) as failure:
            self.tools.get_item('house', detail='everything')
        assert failure.value.code == 'bad_request'

    def test_invisible_item_stays_not_found_in_full_detail(self):
        with pytest.raises(ToolFailure) as failure:
            self.tools.get_item('house.alarm', detail='full')
        assert failure.value.code == 'not_found'
