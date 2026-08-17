#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Unit tests for mapping.py's pure translation logic - no network, no shng
item/plugin framework involved, so these run against the real
implementation rather than a mock of it.
"""

from plugins.matter.mapping import (
    VALUE_PLACEHOLDER,
    AttributeMapping,
    CommandMapping,
    alias_availability_mapping_key,
    alias_mapping_key,
    attribute_path,
    availability_mapping_key,
    report_mapping_key,
)


def test_attribute_path_format():
    # confirmed against a live matter-server: endpoint 1, OnOff cluster (6),
    # OnOff attribute (0) -> "1/6/0"
    assert attribute_path(1, 6, 0) == '1/6/0'
    assert attribute_path(0, 40, 14) == '0/40/14'  # Basic Information / ProductName


def test_report_mapping_key_format():
    assert report_mapping_key(2, '1/6/0') == '2:1/6/0'


def test_availability_mapping_key_format():
    assert availability_mapping_key(2) == '2:available'


def test_availability_mapping_key_never_collides_with_a_real_report_key():
    # A real attribute path is always three ints joined by '/'
    # (attribute_path()'s format) and can never literally be the string
    # 'available', so the two lookup namespaces safely share
    # get_items_for_mapping()'s single dict without risk of collision.
    assert availability_mapping_key(2) != report_mapping_key(2, attribute_path(0, 0, 0))


def test_attribute_mapping_path_and_report_key_properties():
    mapping = AttributeMapping(node_id=2, endpoint_id=1, cluster_id=6, attribute_id=0)
    assert mapping.path == '1/6/0'
    assert mapping.report_key == '2:1/6/0'


def test_attribute_mapping_alias_defaults_to_none():
    mapping = AttributeMapping(node_id=2, endpoint_id=1, cluster_id=6, attribute_id=0)
    assert mapping.alias is None


def test_command_mapping_alias_defaults_to_none():
    mapping = CommandMapping(node_id=2, endpoint_id=1, cluster_id=6, command_name='toggle')
    assert mapping.alias is None


def test_alias_mapping_key_format():
    assert alias_mapping_key('kitchen_socket', '1/6/0') == 'kitchen_socket:1/6/0'


def test_alias_availability_mapping_key_format():
    assert alias_availability_mapping_key('kitchen_socket') == 'kitchen_socket:available'


def test_command_mapping_no_params():
    mapping = CommandMapping(node_id=2, endpoint_id=1, cluster_id=6, command_name='toggle')
    assert mapping.resolve_params(True) == {}


def test_command_mapping_fixed_params_untouched():
    mapping = CommandMapping(
        node_id=2, endpoint_id=1, cluster_id=6, command_name='moveToLevel', params={'transitionTime': 0}
    )
    assert mapping.resolve_params(50) == {'transitionTime': 0}


def test_command_mapping_value_placeholder_substitution():
    mapping = CommandMapping(
        node_id=2,
        endpoint_id=1,
        cluster_id=8,
        command_name='moveToLevel',
        params={'level': VALUE_PLACEHOLDER, 'transitionTime': 0},
    )
    assert mapping.resolve_params(200) == {'level': 200, 'transitionTime': 0}


def test_command_mapping_multiple_value_placeholders():
    mapping = CommandMapping(
        node_id=2,
        endpoint_id=1,
        cluster_id=257,
        command_name='goToLiftPercentage',
        params={'liftPercent100thsValue': VALUE_PLACEHOLDER, 'liftPercentageValue': VALUE_PLACEHOLDER},
    )
    assert mapping.resolve_params(75) == {'liftPercent100thsValue': 75, 'liftPercentageValue': 75}


def test_command_mapping_resolve_command_name_without_false_variant():
    # unchanged behaviour: every write invokes the same command, regardless
    # of value - correct for value-independent actions like toggle.
    mapping = CommandMapping(node_id=2, endpoint_id=1, cluster_id=6, command_name='toggle')
    assert mapping.resolve_command_name(True) == 'toggle'
    assert mapping.resolve_command_name(False) == 'toggle'


def test_command_mapping_resolve_command_name_with_false_variant():
    mapping = CommandMapping(node_id=2, endpoint_id=1, cluster_id=6, command_name='on', command_name_false='off')
    assert mapping.resolve_command_name(True) == 'on'
    assert mapping.resolve_command_name(False) == 'off'
    assert mapping.resolve_command_name(0) == 'off'
    assert mapping.resolve_command_name(1) == 'on'


def test_should_fire_without_false_variant_ignores_falsy_write():
    # value-independent command (toggle): a falsy write is autotimer's own
    # reset, not a real trigger - must not fire again, or a device where
    # toggle really flips state would see two toggles and appear to do
    # nothing (the exact bug this guards against).
    mapping = CommandMapping(node_id=2, endpoint_id=1, cluster_id=6, command_name='toggle')
    assert mapping.should_fire(True) is True
    assert mapping.should_fire(False) is False
    assert mapping.should_fire(0) is False
    assert mapping.should_fire(1) is True


def test_should_fire_with_false_variant_always_fires():
    # a real on/off pair: a falsy write is a genuine "off", not an artifact,
    # so both values must fire.
    mapping = CommandMapping(node_id=2, endpoint_id=1, cluster_id=6, command_name='on', command_name_false='off')
    assert mapping.should_fire(True) is True
    assert mapping.should_fire(False) is True
