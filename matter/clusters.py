#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-      <AUTHOR>                                  <EMAIL>
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#
#  Human-readable names for Matter cluster/attribute IDs, for the webif's
#  discovery browser and item-generator (Phase 2). Deliberately small and
#  grown incrementally as clusters are actually encountered/validated
#  against real or example devices - not a transcription of the whole
#  Application Cluster spec. Unknown IDs fall back to their raw number,
#  which is a perfectly usable (if less friendly) matter_cluster/
#  matter_attribute value.
#
#  Attribute IDs/units below are taken from the actual spec tables in
#  dev/matter/23-27350-010_Matter-1.6-Application-Cluster-Specification.txt
#  (core repo), not guessed - see that file's section references in each
#  cluster's comment.
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
    # Core Spec, Basic Information cluster (0x0028) - not exhaustively covered,
    # only what's been seen so far.
    0x28: ('BasicInformation', {1: AttributeInfo('VendorName', 'str'), 3: AttributeInfo('ProductName', 'str')}),
    # Application Cluster Spec, chapter on Descriptor (Core spec really, but
    # encountered on every endpoint) - name only, not worth decoding attributes.
    0x1D: ('Descriptor', {}),
    # Application Cluster Spec 3.8, On/Off Cluster.
    0x06: ('OnOff', {0: AttributeInfo('OnOff', 'bool')}),
    # Application Cluster Spec 2.13, Electrical Power Measurement Cluster (attribute
    # IDs/units per that section's table - validated live against a real device,
    # see dev/matter/matter-integration-plan.md's "ElectricalPowerMeasurement /
    # struct-cluster validation" section).
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
    # Application Cluster Spec 2.12, Electrical Energy Measurement Cluster - cluster
    # name only so far, attribute struct fields not yet decoded (see plan doc).
    0x91: ('ElectricalEnergyMeasurement', {}),
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


# cluster_id -> (state attribute_id, command-when-true, command-when-false).
# Only clusters where a single bool item can fully describe both state and
# actuation via a canonical two-command pair - the `matter_switch` item
# attribute's whole point. Small and validated incrementally, same
# philosophy as CLUSTERS above: an unregistered cluster is a real gap, not
# a bug - use matter_attribute/matter_command/matter_command_false directly
# for it instead (that lower-level mechanism stays available for exactly
# this reason - it has to work for devices/clusters this table hasn't
# caught up with yet).
SWITCH_CLUSTERS: dict[int, tuple[int, str, str]] = {
    0x06: (0x00, 'on', 'off')  # OnOff: OnOff attribute, On/Off commands - verified on real hardware
}


def switch_info(cluster_id: int) -> tuple[int, str, str] | None:
    """(attribute_id, command_true, command_false) for a switch-shaped cluster, or None if unregistered."""
    return SWITCH_CLUSTERS.get(cluster_id)


# Device Library Spec device type IDs -> human name. Small and grown
# incrementally like everything else here - unregistered types fall back to
# their raw number via device_type_name() below.
DEVICE_TYPES: dict[int, str] = {
    0x010A: 'On/Off Plug-in Unit'  # 266 - verified against real Shelly Plug M Gen3
}


def device_type_name(device_type_id: int) -> str:
    return DEVICE_TYPES.get(device_type_id, f'type_{device_type_id}')
