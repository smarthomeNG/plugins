#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-  Sebastian Helms                 Morg @ knx-user-forum
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#
#  Human-readable names for Matter cluster/attribute IDs, for the webif's
#  discovery browser and item-generator. Deliberately small and grown
#  incrementally as clusters are actually encountered/validated against
#  real or example devices - not a transcription of the whole Application
#  Cluster spec. Unknown IDs fall back to their raw number, which is a
#  perfectly usable (if less friendly) matter_cluster/matter_attribute value.
#
#  Attribute IDs/units below are taken from the actual Matter spec tables,
#  not guessed - see each cluster's own comment for its section reference.
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

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AttributeInfo:
    name: str
    item_type: str  # shng item type (bool/num/str) for the item-generator
    divisor: int | None = None  # raw value / divisor -> base physical unit
    unit: str | None = None


# cluster_id -> (cluster name, {attribute_id: AttributeInfo})
CLUSTERS: dict[int, tuple[str, dict[int, AttributeInfo]]] = {
    # Core Spec, Basic Information cluster (0x0028) - only what's been seen so far, not exhaustive.
    0x28: ('BasicInformation', {1: AttributeInfo('VendorName', 'str'), 3: AttributeInfo('ProductName', 'str')}),
    # Descriptor (Core spec, encountered on every endpoint) - name only, not worth decoding attributes.
    0x1D: ('Descriptor', {}),
    # Application Cluster Spec 3.8, On/Off Cluster.
    0x06: ('OnOff', {0: AttributeInfo('OnOff', 'bool')}),
    # Application Cluster Spec 2.13, Electrical Power Measurement Cluster - IDs/units per that
    # section's table, validated against a real device.
    0x90: (
        'ElectricalPowerMeasurement',
        {
            0: AttributeInfo('PowerMode', 'num'),
            1: AttributeInfo('NumberOfMeasurementTypes', 'num'),
            8: AttributeInfo('ActivePower', 'num', 1000, 'W'),
            11: AttributeInfo('RMSVoltage', 'num', 1000, 'V'),
            12: AttributeInfo('RMSCurrent', 'num', 1000, 'A'),
            14: AttributeInfo('Frequency', 'num', 1000, 'Hz'),
            17: AttributeInfo('PowerFactor', 'num', 100, None),
        },
    ),
    # Application Cluster Spec 2.12, Electrical Energy Measurement Cluster - name only so
    # far, attribute struct fields not yet decoded.
    0x91: ('ElectricalEnergyMeasurement', {}),
    # Core Spec, Bridged Device Basic Information cluster (0x0039) - present on every bridge-role
    # endpoint (bridge.js's BridgedDeviceBasicInformationServer). NodeLabel/ProductName carry
    # matter_expose_name - the only way to tell bridged endpoints apart on the Discovery tab.
    0x39: (
        'BridgedDeviceBasicInformation',
        {
            3: AttributeInfo('ProductName', 'str'),
            5: AttributeInfo('NodeLabel', 'str'),
            15: AttributeInfo('SerialNumber', 'str'),
            17: AttributeInfo('Reachable', 'bool'),
        },
    ),
    # Application Cluster Spec 2.4, Boolean State Cluster - the bridge role's own
    # "contact" expose_type (bridge.js's ContactSensorDevice).
    0x45: ('BooleanState', {0: AttributeInfo('StateValue', 'bool')}),
    # Application Cluster Spec 2.3, Temperature Measurement Cluster - the bridge role's own
    # "temperature_sensor" expose_type. MeasuredValue is int16 hundredths of a degree C (Core
    # Spec 1.6 7.19.2.9) - divisor 100 converts to plain degrees C, same pattern as
    # ElectricalPowerMeasurement above.
    0x402: ('TemperatureMeasurement', {0: AttributeInfo('MeasuredValue', 'num', 100, '°C')}),
}


def cluster_name(cluster_id: int) -> str:
    entry = CLUSTERS.get(cluster_id)
    return entry[0] if entry else f'cluster_{cluster_id}'


def attribute_info(cluster_id: int, attribute_id: int) -> AttributeInfo:
    entry = CLUSTERS.get(cluster_id)
    if entry:
        info = entry[1].get(attribute_id)
        if info is not None:
            return info
    return AttributeInfo(f'attr_{attribute_id}', 'num')


def decode_value(cluster_id: int, attribute_id: int, raw_value):
    """Apply an attribute's known unit divisor to a raw value, if any. Passes non-numeric/None through unchanged."""
    info = attribute_info(cluster_id, attribute_id)
    if info.divisor is None or raw_value is None or not isinstance(raw_value, (int, float)):
        return raw_value
    return raw_value / info.divisor


# cluster_id -> (state attribute_id, command-when-true, command-when-false) - the `matter_switch`
# item attribute's whole point. Same incremental-registry philosophy as CLUSTERS above; an
# unregistered cluster falls back to matter_attribute/matter_command/matter_command_false directly.
SWITCH_CLUSTERS: dict[int, tuple[int, str, str]] = {
    0x06: (0x00, 'on', 'off')  # OnOff: OnOff attribute, On/Off commands - verified on real hardware
}


def switch_info(cluster_id: int) -> tuple[int, str, str] | None:
    """(attribute_id, command_true, command_false) for a switch-shaped cluster, or None if unregistered."""
    return SWITCH_CLUSTERS.get(cluster_id)


# cluster_id -> name of a matching generic struct under plugin.yaml's item_structs (e.g.
# 'matter.switch') - the webif's item-suggestion feature uses this instead of a raw per-attribute
# dump, for clusters with a real, curated struct. Same registry philosophy as CLUSTERS/
# SWITCH_CLUSTERS above; missing here just means no suggestion (Discovery tab still has raw data).
CLUSTER_STRUCTS: dict[int, str] = {
    0x06: 'switch',  # OnOff
    0x90: 'electrical_power_measurement',  # ElectricalPowerMeasurement
    0x45: 'contact',  # BooleanState
    0x402: 'temperature_sensor',  # TemperatureMeasurement
}


def cluster_struct_name(cluster_id: int) -> str | None:
    """Name of the generic plugin.yaml struct (without the 'matter.' plugin prefix) for this cluster, if any."""
    return CLUSTER_STRUCTS.get(cluster_id)


# struct_name -> human-readable function label for a generated item's remark. German, hardcoded -
# matches every other generated/hand-written remark in this plugin; no i18n mechanism exists for
# plugin-generated item config text anywhere in this codebase.
CLUSTER_STRUCT_LABELS: dict[str, str] = {
    'switch': 'Schalter',
    'electrical_power_measurement': 'Energiemessung',
    'contact': 'Kontakt',
    'temperature_sensor': 'Temperatursensor',
}


def cluster_struct_label(struct_name: str) -> str:
    """Human-readable function label for a struct name - falls back to the bare name if unregistered."""
    return CLUSTER_STRUCT_LABELS.get(struct_name, struct_name)


# Device Library Spec device type IDs -> human name; unregistered types fall back to their raw number.
DEVICE_TYPES: dict[int, str] = {
    0x010A: 'On/Off Plug-in Unit'  # 266 - verified against real Shelly Plug M Gen3
}


def device_type_name(device_type_id: int) -> str:
    return DEVICE_TYPES.get(device_type_id, f'type_{device_type_id}')
