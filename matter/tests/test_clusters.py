#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""Unit tests for clusters.py's name/unit lookups - pure data, no network."""

from plugins.matter.clusters import attribute_info, cluster_name, decode_value, device_type_name, switch_info


def test_known_cluster_name():
    assert cluster_name(0x06) == 'OnOff'
    assert cluster_name(0x90) == 'ElectricalPowerMeasurement'


def test_unknown_cluster_name_falls_back_to_numeric():
    assert cluster_name(9999) == 'cluster_9999'


def test_bridge_expose_type_cluster_names():
    """The bridge role's own contact/temperature_sensor expose_types - added after a real
    gap where a bridge's non-switch endpoints showed as unreadable cluster_N rows on the
    Discovery tab, with no way to tell them apart."""
    assert cluster_name(0x39) == 'BridgedDeviceBasicInformation'
    assert cluster_name(0x45) == 'BooleanState'
    assert cluster_name(0x402) == 'TemperatureMeasurement'


def test_bridged_device_node_label_is_the_readable_identifier():
    """NodeLabel is what actually answers "which bridged item is this endpoint" - it
    carries matter_expose_name, set per-endpoint by bridge.js's
    BridgedDeviceBasicInformationServer."""
    info = attribute_info(0x39, 5)
    assert info.name == 'NodeLabel'
    assert info.item_type == 'str'


def test_temperature_measurement_divisor_matches_bridge_js_scaling():
    # Core Spec 1.6 7.19.2.9: int16 hundredths of a degree C - same scaling bridge.js's
    # own applyValue() uses (Math.round(value * 100)).
    assert decode_value(0x402, 0, 2150) == 21.5


def test_relative_humidity_measurement_cluster_name():
    assert cluster_name(0x405) == 'RelativeHumidityMeasurement'


def test_relative_humidity_measurement_divisor():
    # verified against a real IKEA TIMMERFLOTTE: raw 2681 -> 26.81%
    assert decode_value(0x405, 0, 2681) == 26.81


def test_power_source_cluster_name():
    assert cluster_name(0x2F) == 'PowerSource'


def test_power_source_bat_voltage_divisor():
    # verified against a real IKEA TIMMERFLOTTE: raw 3039 (mV) -> 3.039V
    assert decode_value(0x2F, 11, 3039) == 3.039


def test_power_source_bat_percent_remaining_divisor():
    # verified against a real IKEA TIMMERFLOTTE: raw 200 (half-percent units) -> 100%
    assert decode_value(0x2F, 12, 200) == 100.0


def test_known_attribute_info():
    info = attribute_info(0x06, 0)
    assert info.name == 'OnOff'
    assert info.item_type == 'bool'


def test_unknown_attribute_falls_back_to_numeric():
    info = attribute_info(0x06, 42)
    assert info.name == 'attr_42'
    assert info.item_type == 'num'


def test_decode_value_applies_divisor():
    # confirmed against a real device: raw 240623 -> 240.623 V
    assert decode_value(0x90, 11, 240623) == 240.623


def test_decode_value_passes_through_when_no_divisor():
    assert decode_value(0x06, 0, True) is True


def test_decode_value_passes_through_none():
    assert decode_value(0x90, 17, None) is None


def test_switch_info_known_cluster():
    # verified against real hardware: OnOff attribute 0, On/Off commands
    assert switch_info(0x06) == (0x00, 'on', 'off')


def test_switch_info_unknown_cluster_returns_none():
    assert switch_info(9999) is None


def test_device_type_name_known():
    # verified against real hardware: Shelly Plug M Gen3 reports device type 266
    assert device_type_name(0x010A) == 'On/Off Plug-in Unit'


def test_device_type_name_temperature_and_humidity_sensor():
    # verified against real hardware: IKEA TIMMERFLOTTE reports 770/775 on its two endpoints
    assert device_type_name(0x0302) == 'Temperature Sensor'
    assert device_type_name(0x0307) == 'Humidity Sensor'


def test_device_type_name_unknown_falls_back_to_numeric():
    assert device_type_name(9999) == 'type_9999'
