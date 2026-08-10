#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Unit tests for discovery.py - pure data transforms, no network. Fixture below
is a trimmed-down version of the real attribute shape returned by
matter-server's get_nodes() (see dev/matter/matter-integration-plan.md's
"ElectricalPowerMeasurement / struct-cluster validation" section for the
real device this was captured from), not a fabricated shape.
"""

import yaml

from plugins.matter.discovery import discovery_rows, generate_item_yaml, node_summary

SAMPLE_NODE = {
    'node_id': 1,
    'available': True,
    'attributes': {
        '0/40/1': 'Shelly',
        '0/40/3': 'Shelly Plug M Gen3',
        '0/40/5': '',  # NodeLabel, unset - falls back to product name
        # global/metadata attributes present on real clusters - should show
        # up in discovery_rows() but never in generate_item_yaml().
        '0/40/65533': 3,
        '0/29/0': [{'0': 22, '1': 1}],  # RootNode device type on endpoint 0 - skipped for device_type
        '1/29/0': [{'0': 266, '1': 1}],  # On/Off Plug-in Unit device type on endpoint 1
        '1/6/0': False,
        '1/6/65528': [],
        '1/144/8': 0,
        '1/144/11': 240623,
        '1/144/17': None,
        '1/144/65533': 1,
        # a cluster with ONLY global attributes - should be dropped entirely
        # from the generated item tree, not left as an empty block.
        '1/999/65533': 2,
    },
}


def test_discovery_rows_sorted_by_endpoint_cluster_attribute():
    rows = discovery_rows(SAMPLE_NODE)
    assert [(r['endpoint_id'], r['cluster_id'], r['attribute_id']) for r in rows] == [
        (0, 29, 0),
        (0, 40, 1),
        (0, 40, 3),
        (0, 40, 5),
        (0, 40, 65533),
        (1, 6, 0),
        (1, 6, 65528),
        (1, 29, 0),
        (1, 144, 8),
        (1, 144, 11),
        (1, 144, 17),
        (1, 144, 65533),
        (1, 999, 65533),
    ]


def test_discovery_rows_decode_names_and_units():
    rows = {(r['cluster_id'], r['attribute_id']): r for r in discovery_rows(SAMPLE_NODE)}
    assert rows[(6, 0)]['cluster_name'] == 'OnOff'
    assert rows[(6, 0)]['attribute_name'] == 'OnOff'
    assert rows[(144, 11)]['attribute_name'] == 'RMSVoltage'
    assert rows[(144, 11)]['value'] == 240.623
    assert rows[(144, 11)]['unit'] == 'V'


def test_discovery_rows_preserve_null_values():
    rows = {(r['cluster_id'], r['attribute_id']): r for r in discovery_rows(SAMPLE_NODE)}
    assert rows[(144, 17)]['value'] is None


def test_generate_item_yaml_is_valid_yaml():
    text = generate_item_yaml(SAMPLE_NODE)
    parsed = yaml.safe_load(text)
    assert 'matter_node_1' in parsed


def test_generate_item_yaml_shape_for_onoff():
    # single item using matter_switch - mirrors state AND drives it, plugin
    # derives attribute/commands internally. Not separate on/off/state
    # items (could disagree) and not spelled-out matter_attribute/
    # matter_command/matter_command_false (that's what matter_switch saves
    # the item config from needing to know).
    parsed = yaml.safe_load(generate_item_yaml(SAMPLE_NODE))
    onoff_cluster = parsed['matter_node_1']['endpoint_1']['on_off']
    on_off_item = onoff_cluster['on_off']
    assert on_off_item['matter_node'] == 1
    assert on_off_item['matter_endpoint'] == 1
    assert on_off_item['matter_cluster'] == 6
    assert on_off_item['type'] == 'bool'
    assert on_off_item['matter_switch'] is True
    assert 'matter_attribute' not in on_off_item
    assert 'matter_command' not in on_off_item


def test_generate_item_yaml_onoff_toggle_stays_separate():
    # toggle has no "false" counterpart - value-independent by nature, so
    # it's still its own command-only item, not merged into on_off.
    parsed = yaml.safe_load(generate_item_yaml(SAMPLE_NODE))
    onoff_cluster = parsed['matter_node_1']['endpoint_1']['on_off']
    assert onoff_cluster['toggle']['matter_command'] == 'toggle'
    assert onoff_cluster['toggle']['matter_cluster'] == 6
    assert 'matter_attribute' not in onoff_cluster['toggle']
    assert 'on' not in onoff_cluster
    assert 'off' not in onoff_cluster


def test_generate_item_yaml_toggle_is_a_proper_trigger():
    # a pure command trigger needs enforce_updates (repeated same-value
    # writes aren't deduped away) and autotimer (resets back to falsy) to
    # actually behave like a momentary trigger rather than a static value.
    parsed = yaml.safe_load(generate_item_yaml(SAMPLE_NODE))
    toggle_item = parsed['matter_node_1']['endpoint_1']['on_off']['toggle']
    assert toggle_item['enforce_updates'] is True
    assert toggle_item['autotimer'] == '1 = 0'


def test_generate_item_yaml_non_onoff_cluster_gets_no_command_items():
    parsed = yaml.safe_load(generate_item_yaml(SAMPLE_NODE))
    power_cluster = parsed['matter_node_1']['endpoint_1']['electrical_power_measurement']
    assert 'on' not in power_cluster
    assert power_cluster['active_power']['matter_attribute'] == 8
    assert power_cluster['rms_voltage']['matter_attribute'] == 11


def test_generate_item_yaml_excludes_global_attributes():
    parsed = yaml.safe_load(generate_item_yaml(SAMPLE_NODE))
    onoff_cluster = parsed['matter_node_1']['endpoint_1']['on_off']
    power_cluster = parsed['matter_node_1']['endpoint_1']['electrical_power_measurement']
    assert 'attr_65528' not in onoff_cluster
    assert 'attr_65533' not in power_cluster


def test_generate_item_yaml_drops_cluster_with_only_global_attributes():
    parsed = yaml.safe_load(generate_item_yaml(SAMPLE_NODE))
    # cluster 999 on endpoint 1 has only a global attribute (65533) - should
    # not appear as an empty block, or at all.
    assert 'cluster_999' not in parsed['matter_node_1']['endpoint_1']


def test_node_summary_basics():
    summary = node_summary(SAMPLE_NODE)
    assert summary['node_id'] == 1
    assert summary['available'] is True
    assert summary['vendor'] == 'Shelly'
    assert summary['product'] == 'Shelly Plug M Gen3'


def test_node_summary_label_falls_back_to_product_when_node_label_unset():
    # NodeLabel ('0/40/5') is '' in the fixture - real devices default it empty
    assert node_summary(SAMPLE_NODE)['label'] == 'Shelly Plug M Gen3'


def test_node_summary_label_prefers_node_label_when_set():
    node = {**SAMPLE_NODE, 'attributes': {**SAMPLE_NODE['attributes'], '0/40/5': 'Kitchen Plug'}}
    assert node_summary(node)['label'] == 'Kitchen Plug'


def test_node_summary_device_type_from_non_root_endpoint():
    # endpoint 0's device type (22, RootNode) must be skipped in favour of
    # endpoint 1's real device type (266, On/Off Plug-in Unit)
    assert node_summary(SAMPLE_NODE)['device_type'] == 'On/Off Plug-in Unit'


def test_node_summary_missing_basic_information_is_empty_not_error():
    node = {'node_id': 2, 'available': False, 'attributes': {'1/6/0': True}}
    summary = node_summary(node)
    assert summary['vendor'] == ''
    assert summary['product'] == ''
    assert summary['device_type'] == ''
    assert summary['label'] == 'Node 2'
