"""The sample config in sample_config/ behaves as its comments and README claim."""

import os

import pytest
from ruamel.yaml import YAML

from plugins.mcp.access import AccessResolver
from plugins.mcp.tools import ItemTools
from plugins.mcp.types import DefaultAccess, Entitlement, ToolFailure
from tests.mock.core import MockSmartHome

SAMPLE = os.path.join(os.path.dirname(__file__), '..', 'sample_config')
ITEMS = os.path.join(SAMPLE, 'items', 'mcp_demo.yaml')


def load_yaml(*parts):
    with open(os.path.join(SAMPLE, *parts), encoding='UTF-8') as f:
        return YAML(typ='safe').load(f)


def make_items():
    sh = MockSmartHome()
    sh.with_items_from(ITEMS)
    assert sh.items is not None
    return sh.items


def tools(default_access: DefaultAccess = 'none', inherit_rw_access=False, write_rate_limit=30, clock=None):
    items = make_items()
    entitlement = Entitlement('local', default_access, inherit_rw_access, frozenset(), write_rate_limit)
    kwargs = {'clock': clock} if clock is not None else {}
    return ItemTools(items, entitlement, **kwargs)


def access_of(path, default_access: DefaultAccess = 'none', inherit_rw_access=False):
    item = make_items().return_item(path)
    assert item is not None
    entitlement = Entitlement('local', default_access, inherit_rw_access, frozenset(), 30)
    return AccessResolver(entitlement).effective_access(item)


ACCESS = [
    ('mcpdemo', 'ro'),
    ('mcpdemo.counter', 'ro'),
    ('mcpdemo.house.temperature', 'ro'),
    ('mcpdemo.house.humidity', 'ro'),
    ('mcpdemo.house.lamp', 'rw'),
    ('mcpdemo.house.dimmer', 'rw'),
    ('mcpdemo.house.setpoint', 'rw'),
    ('mcpdemo.house.mode', 'rw'),
    ('mcpdemo.zone', 'rw'),
    ('mcpdemo.private', 'none'),
    ('mcpdemo.private.secret_level', 'none'),
    ('mcpdemo.private.exception', 'rw'),
    ('mcpdemo.typo', 'none'),
]


@pytest.mark.parametrize(('path', 'expected'), ACCESS)
def test_access_of_each_item(path, expected):
    assert access_of(path) == expected


@pytest.mark.parametrize('path', ['mcpdemo.house.lamp.brightness_note', 'mcpdemo.zone.a', 'mcpdemo.zone.b'])
def test_children_of_an_rw_item_are_ro_unless_rw_is_inherited(path):
    assert access_of(path) == 'ro'
    assert access_of(path, inherit_rw_access=True) == 'rw'


def test_an_unmarked_item_follows_default_access():
    assert access_of('unmarked', 'none') == 'none'
    assert access_of('unmarked', 'ro') == 'ro'


def test_a_read_only_item_refuses_writes():
    with pytest.raises(ToolFailure) as failure:
        tools().set_item('mcpdemo.house.temperature', 1)
    assert failure.value.code == 'forbidden'


def test_a_hidden_item_looks_like_a_missing_one():
    with pytest.raises(ToolFailure) as hidden:
        tools().get_item('mcpdemo.private.secret_level')
    with pytest.raises(ToolFailure) as missing:
        tools().get_item('mcpdemo.private.nothing_here')
    assert (hidden.value.code, hidden.value.message) == (missing.value.code, missing.value.message)


def test_a_value_of_the_wrong_type_is_invalid():
    with pytest.raises(ToolFailure) as failure:
        tools().set_item('mcpdemo.house.lamp', 'maybe')
    assert failure.value.code == 'invalid_value'


def test_the_lamp_allows_five_writes_a_minute_and_the_setpoint_any_number():
    both = tools()
    for value in (True, False, True, False, True):
        both.set_item('mcpdemo.house.lamp', value)
    with pytest.raises(ToolFailure) as failure:
        both.set_item('mcpdemo.house.lamp', False)
    assert failure.value.code == 'rate_limited'
    for value in range(100):
        both.set_item('mcpdemo.house.setpoint', value)


def test_secret_looking_attributes_are_not_shown():
    detail = tools().get_item('mcpdemo.house.setpoint', 'full')
    assert 'api_token' not in detail['attributes']
    assert 'knx_password' not in detail['attributes']
    assert detail['attributes']['mcp_access'] == 'rw'


def test_the_sample_plugin_configuration_uses_only_declared_parameters():
    declared = load_yaml('..', 'plugin.yaml')['parameters']
    sample = load_yaml('plugin.yaml')['mcp']
    assert set(sample) - {'plugin_name'} <= set(declared)
    assert sample['token'] == '__TOKEN__'


def test_a_number_written_to_the_text_item_is_cast_to_text():
    assert tools().set_item('mcpdemo.house.mode', 5)['value'] == '5'
