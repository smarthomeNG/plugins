#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Unit tests for discovery.py - pure data transforms, no network. Fixture below
is a trimmed-down version of the real attribute shape returned by
matter-server's get_nodes() (see dev/matter/matter-integration-plan.md's
"ElectricalPowerMeasurement / struct-cluster validation" section for the
real device this was captured from), not a fabricated shape.
"""

import ruamel.yaml as yaml  # not pyyaml - see discovery.py's import comment

from plugins.matter.server.discovery import discovery_rows, generate_suggested_item, node_summary

SAMPLE_NODE = {
    'node_id': 1,
    'available': True,
    'attributes': {
        '0/40/1': 'Shelly',
        '0/40/3': 'Shelly Plug M Gen3',
        '0/40/5': '',  # NodeLabel, unset - falls back to product name
        # global/metadata attributes present on real clusters - should show
        # up in discovery_rows() but never in generate_suggested_item().
        '0/40/65533': 3,
        '0/29/0': [{'0': 22, '1': 1}],  # RootNode device type on endpoint 0 - skipped for device_type
        '1/29/0': [{'0': 266, '1': 1}],  # On/Off Plug-in Unit device type on endpoint 1
        '1/6/0': False,
        '1/6/65528': [],
        '1/144/8': 0,
        '1/144/11': 240623,
        '1/144/17': None,
        '1/144/65533': 1,
        # a cluster with no CLUSTER_STRUCTS entry - should never appear in a suggestion, whatever
        # its own attributes look like (see clusters.py's own docstring: unregistered = real gap,
        # covered by the Discovery tab instead, not something generate_suggested_item() tries to
        # approximate).
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


def test_generate_suggested_item_combined_device_lists_both_structs_in_cluster_id_order():
    # SAMPLE_NODE has both OnOff (cluster 6) and ElectricalPowerMeasurement (cluster 144) on the
    # same endpoint - both are CLUSTER_STRUCTS-covered, so both belong in the struct list, lower
    # cluster_id first.
    text = generate_suggested_item(SAMPLE_NODE)
    parsed = yaml.safe_load(text)
    item = parsed['matter_node_1']
    assert item['struct'] == ['matter.switch', 'matter.electrical_power_measurement']
    assert item['matter_node'] == 1
    assert item['matter_endpoint'] == 1


def test_generate_suggested_item_ignores_uncovered_cluster():
    # cluster 999 has no CLUSTER_STRUCTS entry - must never show up in the struct list, regardless
    # of what attributes it has.
    text = generate_suggested_item(SAMPLE_NODE)
    parsed = yaml.safe_load(text)
    assert 'matter.cluster_999' not in parsed['matter_node_1']['struct']
    assert all('999' not in ref for ref in parsed['matter_node_1']['struct'])


def test_generate_suggested_item_single_covered_cluster_is_a_bare_string_not_a_list():
    node = {'node_id': 2, 'available': True, 'attributes': {'1/6/0': False}}
    parsed = yaml.safe_load(generate_suggested_item(node))
    assert parsed['matter_node_2']['struct'] == 'matter.switch'


def test_generate_suggested_item_key_order_is_remark_struct_node_endpoint():
    # Real user feedback: remark should be immediately identifiable (which physical device),
    # struct: next (what kind of item this is, self-explanatory via naming), matter_node/
    # matter_endpoint last (Matter-internal plumbing, least relevant to a human scanning the
    # block) - not incidental/alphabetical ordering.
    text = generate_suggested_item(SAMPLE_NODE, device_label='Shelly Plug M Gen3 (Küche)')
    parsed = yaml.safe_load(text)
    assert list(parsed['matter_node_1'].keys()) == ['remark', 'struct', 'matter_node', 'matter_endpoint']


def test_generate_suggested_item_remark_leads_with_function_labels_then_device_label():
    # Real feedback: a bare device-name remark didn't say what a given suggestion actually does
    # once there was more than one device/suggestion on the page - function label(s) first, then
    # the device name for disambiguation.
    parsed = yaml.safe_load(generate_suggested_item(SAMPLE_NODE, device_label='Shelly Plug M Gen3 (Küche)'))
    assert parsed['matter_node_1']['remark'] == 'Schalter, Energiemessung - Shelly Plug M Gen3 (Küche)'


def test_generate_suggested_item_no_device_label_still_has_function_label_remark():
    # remark is no longer conditional on device_label - the function label(s) are always known
    # here, so remark is always set, just without the trailing device name.
    parsed = yaml.safe_load(generate_suggested_item(SAMPLE_NODE))
    assert parsed['matter_node_1']['remark'] == 'Schalter, Energiemessung'


def test_generate_suggested_item_no_covered_clusters_returns_none():
    node = {'node_id': 3, 'available': True, 'attributes': {'1/999/65533': 2}}
    assert generate_suggested_item(node) is None


def test_generate_suggested_item_covered_clusters_on_different_endpoints_produce_one_block_each():
    # OnOff on endpoint 1, ElectricalPowerMeasurement on endpoint 2 - two separate physical signals
    # on two separate endpoints (unlike SAMPLE_NODE's single-endpoint combined device). Real need:
    # the bridge role routinely exposes one cluster per endpoint (see the temperature_sensor/contact/
    # switch bridge fixture below) - each covered endpoint gets its own item block, keyed uniquely
    # since matter_node_4 alone would collide.
    node = {'node_id': 4, 'available': True, 'attributes': {'1/6/0': False, '2/144/8': 0}}
    parsed = yaml.safe_load(generate_suggested_item(node))
    assert set(parsed.keys()) == {'matter_node_4_ep1', 'matter_node_4_ep2'}
    assert parsed['matter_node_4_ep1']['struct'] == 'matter.switch'
    assert parsed['matter_node_4_ep1']['matter_endpoint'] == 1
    assert parsed['matter_node_4_ep2']['struct'] == 'matter.electrical_power_measurement'
    assert parsed['matter_node_4_ep2']['matter_endpoint'] == 2


def test_generate_suggested_item_bridge_with_three_single_cluster_endpoints():
    # Real live shape: a bridge exposing a switch, a contact sensor, and a temperature sensor, each
    # on its own endpoint (bridge.js's BridgedDeviceBasicInformationServer + one device-type cluster
    # per endpoint) - matches what a real matter2 bridge test instance produced.
    node = {'node_id': 14, 'available': True, 'attributes': {'2/6/0': False, '3/69/0': False, '4/1026/0': 2150}}
    parsed = yaml.safe_load(generate_suggested_item(node))
    assert set(parsed.keys()) == {'matter_node_14_ep2', 'matter_node_14_ep3', 'matter_node_14_ep4'}
    assert parsed['matter_node_14_ep2']['struct'] == 'matter.switch'
    assert parsed['matter_node_14_ep3']['struct'] == 'matter.contact'
    assert parsed['matter_node_14_ep4']['struct'] == 'matter.temperature_sensor'
    for key in parsed:
        assert list(parsed[key].keys()) == ['remark', 'struct', 'matter_node', 'matter_endpoint']


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
