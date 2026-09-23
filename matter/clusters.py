#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-  Sebastian Helms                 Morg @ knx-user-forum
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#
#  Registry of the Matter clusters this plugin knows by name: attribute
#  names/types/units for the discovery browser, the matter_switch shorthand,
#  and the plugin.yaml struct used for item suggestions. Grown as clusters
#  are validated against real devices, not a transcription of the spec -
#  unknown IDs fall back to their raw number.
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

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class AttributeInfo:
    name: str
    item_type: str  # shng item type (bool/num/str)
    divisor: int | None = None  # raw value / divisor -> base physical unit
    unit: str | None = None


@dataclass(frozen=True)
class SwitchSpec:
    """How the matter_switch shorthand maps a bool item onto a cluster."""

    attribute_id: int
    command_true: str
    command_false: str


@dataclass(frozen=True)
class StructSpec:
    """Generic plugin.yaml struct (without the 'matter.' prefix) suggested for a cluster, and its remark label."""

    name: str
    label: str


@dataclass(frozen=True)
class ClusterSpec:
    id: int
    name: str
    attributes: Mapping[int, AttributeInfo] = field(default_factory=dict)
    switch: SwitchSpec | None = None
    struct: StructSpec | None = None


_CLUSTER_SPECS = (
    # Core Spec, Basic Information cluster.
    ClusterSpec(
        0x28, 'BasicInformation', {1: AttributeInfo('VendorName', 'str'), 3: AttributeInfo('ProductName', 'str')}
    ),
    # Core Spec, Descriptor cluster - present on every endpoint.
    ClusterSpec(0x1D, 'Descriptor'),
    # Application Cluster Spec 1.5, On/Off cluster - switch verified on real hardware.
    ClusterSpec(
        0x06,
        'OnOff',
        {0: AttributeInfo('OnOff', 'bool')},
        switch=SwitchSpec(0x00, 'on', 'off'),
        struct=StructSpec('switch', 'Schalter'),
    ),
    # Application Cluster Spec 2.13, Electrical Power Measurement - validated against a real device.
    ClusterSpec(
        0x90,
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
        struct=StructSpec('electrical_power_measurement', 'Energiemessung'),
    ),
    # Application Cluster Spec 2.12, Electrical Energy Measurement - attribute structs not decoded.
    ClusterSpec(0x91, 'ElectricalEnergyMeasurement'),
    # Core Spec, Bridged Device Basic Information - on every bridge-role endpoint; NodeLabel carries matter_expose_name.
    ClusterSpec(
        0x39,
        'BridgedDeviceBasicInformation',
        {
            3: AttributeInfo('ProductName', 'str'),
            5: AttributeInfo('NodeLabel', 'str'),
            15: AttributeInfo('SerialNumber', 'str'),
            17: AttributeInfo('Reachable', 'bool'),
        },
    ),
    # Application Cluster Spec 2.4, Boolean State.
    ClusterSpec(
        0x45, 'BooleanState', {0: AttributeInfo('StateValue', 'bool')}, struct=StructSpec('contact', 'Kontakt')
    ),
    # Application Cluster Spec 2.3, Temperature Measurement - int16 hundredths of a degree C.
    ClusterSpec(
        0x402,
        'TemperatureMeasurement',
        {0: AttributeInfo('MeasuredValue', 'num', 100, '°C')},
        struct=StructSpec('temperature_sensor', 'Temperatursensor'),
    ),
    # Application Cluster Spec 2.6, Relative Humidity Measurement - divisor validated on a real device.
    ClusterSpec(
        0x405,
        'RelativeHumidityMeasurement',
        {0: AttributeInfo('MeasuredValue', 'num', 100, '%')},
        struct=StructSpec('humidity_sensor', 'Feuchtesensor'),
    ),
    # Core Spec, Power Source cluster (root endpoint) - validated on a real device.
    ClusterSpec(
        0x2F,
        'PowerSource',
        {11: AttributeInfo('BatVoltage', 'num', 1000, 'V'), 12: AttributeInfo('BatPercentRemaining', 'num', 2, '%')},
        struct=StructSpec('battery', 'Batterie'),
    ),
)

CLUSTERS: dict[int, ClusterSpec] = {spec.id: spec for spec in _CLUSTER_SPECS}

# Device Library Spec device type IDs -> human name; unregistered types fall back to their raw number.
DEVICE_TYPES: dict[int, str] = {0x010A: 'On/Off Plug-in Unit', 0x0302: 'Temperature Sensor', 0x0307: 'Humidity Sensor'}


def cluster_name(cluster_id: int) -> str:
    spec = CLUSTERS.get(cluster_id)
    return spec.name if spec else f'cluster_{cluster_id}'


def attribute_info(cluster_id: int, attribute_id: int) -> AttributeInfo:
    spec = CLUSTERS.get(cluster_id)
    info = spec.attributes.get(attribute_id) if spec else None
    return info if info is not None else AttributeInfo(f'attr_{attribute_id}', 'num')


def decode_value(cluster_id: int, attribute_id: int, raw_value: Any) -> Any:
    """Apply an attribute's known unit divisor to a raw value; non-numeric values and None pass through."""
    info = attribute_info(cluster_id, attribute_id)
    if (
        info.divisor is None
        or raw_value is None
        or isinstance(raw_value, bool)
        or not isinstance(raw_value, (int, float))
    ):
        return raw_value
    return raw_value / info.divisor


def switch_info(cluster_id: int) -> SwitchSpec | None:
    """matter_switch mapping for a cluster, or None if the cluster has none registered."""
    spec = CLUSTERS.get(cluster_id)
    return spec.switch if spec else None


def cluster_struct(cluster_id: int) -> StructSpec | None:
    """Suggested generic struct for a cluster, or None if the cluster has none."""
    spec = CLUSTERS.get(cluster_id)
    return spec.struct if spec else None


def device_type_name(device_type_id: int) -> str:
    return DEVICE_TYPES.get(device_type_id, f'type_{device_type_id}')
