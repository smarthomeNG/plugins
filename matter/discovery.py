#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-      <AUTHOR>                                  <EMAIL>
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#
#  Phase 2: turn a matter-server node's cached attribute dump (from
#  get_nodes(), already fetched during commissioning's device interview)
#  into (a) flat rows for the webif's discovery browser table and
#  (b) a suggested item tree, rendered as copy-paste YAML.
#
#  Deliberately does NOT use shng's item_structs mechanism here: struct
#  templates are static (resolved once at plugin-load time, lib/item/
#  structs.py) with no "repeat N times" directive, so they can't fit a
#  device whose endpoint/cluster count is only known after commissioning.
#  (plugin.yaml does define real item_structs for specific known/tested
#  device models - a different, complementary use case.) The proven
#  pattern for this dynamic case is the `unifi` plugin's "Item-Generator"
#  tab: build a dict from live data, yaml.dump it, show as copy-paste
#  text - no plugin writes item config files itself. Followed here for
#  consistency.
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

import re
from collections import defaultdict
from typing import Any

import yaml

from .clusters import attribute_info, cluster_name, decode_value, device_type_name

# BasicInformation cluster (Core Spec 11.1), attributes used for the device
# table: VendorName, ProductName, NodeLabel (user-settable, RW - see
# dev/matter/matter-integration-plan.md's write_attribute verification).
BASIC_INFORMATION_CLUSTER = 0x28
VENDOR_NAME_ATTR = 0x01
PRODUCT_NAME_ATTR = 0x03
NODE_LABEL_ATTR = 0x05

# Descriptor cluster (Core Spec 9.5), DeviceTypeList attribute - present on
# every endpoint; endpoint 0's entry is the RootNode type (not useful for
# display), so the device table uses the first non-root endpoint's primary
# device type instead.
DESCRIPTOR_CLUSTER = 0x1D
DEVICE_TYPE_LIST_ATTR = 0x00

# OnOff's universal, always-present commands. Deliberately not generalized
# into a per-cluster command table - every other cluster's meaningful
# commands need real cluster-specific knowledge (params, semantics) that
# isn't available from an attribute dump alone. This one cluster is common
# and simple enough to be worth the small special case.
ONOFF_CLUSTER_ID = 0x06
ONOFF_ATTRIBUTE_ID = 0x00

# Global attributes present on every cluster (Core Spec Data Model chapter):
# GeneratedCommandList, AcceptedCommandList, EventList, AttributeList,
# FeatureMap, ClusterRevision. Cluster metadata, never meaningful device
# state - real, useful for the browser (discovery_rows), pure noise for the
# item-generator (one of these six on every single cluster otherwise).
GLOBAL_ATTRIBUTE_IDS = frozenset({0xFFF8, 0xFFF9, 0xFFFA, 0xFFFB, 0xFFFC, 0xFFFD})

# Standard two-pass camelCase -> snake_case conversion. A single lookahead
# regex (insert '_' before every uppercase letter) breaks on acronym runs
# like "RMSVoltage" -> "r_m_s_voltage" instead of "rms_voltage" - this
# two-pass version keeps acronym runs together.
_FIRST_CAP = re.compile(r'(.)([A-Z][a-z]+)')
_ALL_CAP = re.compile(r'([a-z0-9])([A-Z])')


def _slug(name: str) -> str:
    """CamelCase cluster/attribute name -> lower_snake_case item key."""
    step1 = _FIRST_CAP.sub(r'\1_\2', name)
    return _ALL_CAP.sub(r'\1_\2', step1).lower()


def _split_path(path: str) -> tuple[int, int, int]:
    endpoint_id, cluster_id, attribute_id = path.split('/')
    return int(endpoint_id), int(cluster_id), int(attribute_id)


def discovery_rows(node: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten one node's cached attribute dump into sorted discovery-table rows."""
    node_id = node['node_id']
    rows = []
    for path, value in node['attributes'].items():
        endpoint_id, cluster_id, attribute_id = _split_path(path)
        info = attribute_info(cluster_id, attribute_id)
        rows.append(
            {
                'node_id': node_id,
                'endpoint_id': endpoint_id,
                'cluster_id': cluster_id,
                'cluster_name': cluster_name(cluster_id),
                'attribute_id': attribute_id,
                'attribute_name': info.name,
                'value': decode_value(cluster_id, attribute_id, value),
                'unit': info.unit or '',
                'path': path,
            }
        )
    rows.sort(key=lambda r: (r['endpoint_id'], r['cluster_id'], r['attribute_id']))
    return rows


def generate_item_yaml(node: dict[str, Any]) -> str:
    """Suggested item tree for one node, as copy-paste YAML (unifi's Item-Generator pattern)."""
    node_id = node['node_id']

    by_endpoint_cluster: dict[tuple[int, int], dict[int, Any]] = defaultdict(dict)
    for path, value in node['attributes'].items():
        endpoint_id, cluster_id, attribute_id = _split_path(path)
        by_endpoint_cluster[(endpoint_id, cluster_id)][attribute_id] = value

    root: dict[str, Any] = {}
    for (endpoint_id, cluster_id), attrs in sorted(by_endpoint_cluster.items()):
        attribute_ids = [a for a in attrs if a not in GLOBAL_ATTRIBUTE_IDS]
        if not attribute_ids and cluster_id != ONOFF_CLUSTER_ID:
            continue  # nothing but cluster metadata (and not OnOff, which still gets command items below)

        endpoint_block = root.setdefault(f'endpoint_{endpoint_id}', {})
        cluster_block = endpoint_block.setdefault(_slug(cluster_name(cluster_id)), {})

        for attribute_id in attribute_ids:
            if cluster_id == ONOFF_CLUSTER_ID and attribute_id == ONOFF_ATTRIBUTE_ID:
                # matter_switch derives the attribute + both commands from
                # SWITCH_CLUSTERS - no need to spell out matter_attribute/
                # matter_command/matter_command_false here at all.
                cluster_block['on_off'] = {
                    'type': 'bool',
                    'matter_node': node_id,
                    'matter_endpoint': endpoint_id,
                    'matter_cluster': cluster_id,
                    'matter_switch': True,
                }
                continue
            info = attribute_info(cluster_id, attribute_id)
            cluster_block[_slug(info.name)] = {
                'type': info.item_type,
                'matter_node': node_id,
                'matter_endpoint': endpoint_id,
                'matter_cluster': cluster_id,
                'matter_attribute': attribute_id,
            }

        if cluster_id == ONOFF_CLUSTER_ID:
            # toggle has no "false" counterpart - value-independent by
            # nature, a pure trigger not a state mirror. Needs
            # enforce_updates (repeated same-value writes get deduped and
            # never re-fire otherwise) and autotimer resetting it falsy
            # (else it just sits at whatever was last written, not
            # behaving like a momentary trigger).
            cluster_block['toggle'] = {
                'type': 'bool',
                'matter_node': node_id,
                'matter_endpoint': endpoint_id,
                'matter_cluster': cluster_id,
                'matter_command': 'toggle',
                'enforce_updates': True,
                'autotimer': '1 = 0',
            }

    return yaml.dump(
        {f'matter_node_{node_id}': root},
        Dumper=yaml.SafeDumper,
        indent=4,
        width=768,
        allow_unicode=True,
        default_flow_style=False,
    )


def node_summary(node: dict[str, Any]) -> dict[str, Any]:
    """One row's worth of device-table info: name/vendor/product/device type, from the cached interview."""
    node_id = node['node_id']
    attrs = node['attributes']

    vendor = attrs.get(f'0/{BASIC_INFORMATION_CLUSTER}/{VENDOR_NAME_ATTR}') or ''
    product = attrs.get(f'0/{BASIC_INFORMATION_CLUSTER}/{PRODUCT_NAME_ATTR}') or ''
    node_label = attrs.get(f'0/{BASIC_INFORMATION_CLUSTER}/{NODE_LABEL_ATTR}') or ''
    # NodeLabel is user-settable (client.py's write_attribute) and empty on
    # most devices out of the box - 'label' with the product/node_id
    # fallback is only for contexts needing *some* readable text (e.g. the
    # unlink confirm dialog). The device table itself shows raw node_label,
    # blank rather than a duplicate of Produkt when nothing's been set.
    label = node_label or product or f'Node {node_id}'

    device_type = ''
    endpoint_ids = sorted({_split_path(path)[0] for path in attrs if _split_path(path)[1] == DESCRIPTOR_CLUSTER})
    for endpoint_id in endpoint_ids:
        if endpoint_id == 0:
            continue  # RootNode type, not useful for display
        device_types = attrs.get(f'{endpoint_id}/{DESCRIPTOR_CLUSTER}/{DEVICE_TYPE_LIST_ATTR}')
        if device_types:
            device_type = device_type_name(device_types[0]['0'])
            break

    return {
        'node_id': node_id,
        'available': node.get('available'),
        'label': label,
        'node_label': node_label,
        'vendor': vendor,
        'product': product,
        'device_type': device_type,
    }
