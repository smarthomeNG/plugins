#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-  Sebastian Helms                 Morg @ knx-user-forum
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#
#  Turn a matter-server node's cached attribute dump (from get_nodes(),
#  already fetched during commissioning's device interview) into (a) flat
#  rows for the webif's discovery browser table and (b) a suggested item
#  config, as copy-paste YAML, for clusters with a real curated
#  plugin.yaml struct (clusters.py's CLUSTER_STRUCTS).
#
#  Earlier versions of this module dynamically re-derived a full raw
#  per-attribute item tree instead of using shng's own item_structs
#  mechanism, reasoning that struct templates are static (resolved once at
#  plugin-load time) with no "repeat N times" directive, so they couldn't
#  fit a device whose endpoint/cluster layout is only known after
#  commissioning. That reasoning only actually blocks baking matter_node/
#  matter_endpoint into a struct (genuinely per-device, only known at
#  runtime) - it says nothing about matter_cluster (spec-defined,
#  universal) or matter_attribute (same). Structs can be, and now are,
#  written device-agnostically at the cluster level; matter_node/
#  matter_endpoint are supplied once by the tiny suggestion this module
#  generates, then inherited by every descendant item via this plugin's
#  own Item.find_attribute() ancestor-walk - see plugin.yaml's own
#  `switch`/`electrical_power_measurement` structs.
#
#  Clusters with no curated struct are deliberately not suggested at all -
#  the Discovery tab (discovery_rows() below) already shows every raw
#  attribute for exactly that "not curated yet" case, and the low-level
#  matter_attribute/matter_command item attributes remain the documented
#  fallback. Building a second, item-generator-flavored copy of that data
#  would just duplicate Discovery, not add anything.
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

from collections import defaultdict
from typing import Any

import ruamel.yaml as yaml

from ..clusters import (
    attribute_info,
    cluster_name,
    cluster_struct_label,
    cluster_struct_name,
    decode_value,
    device_type_name,
)

# BasicInformation cluster (Core Spec 11.1), attributes used for the device
# table: VendorName, ProductName, NodeLabel (user-settable, RW).
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


def _group_by_endpoint_cluster(node: dict[str, Any]) -> dict[tuple[int, int], dict[int, Any]]:
    by_endpoint_cluster: dict[tuple[int, int], dict[int, Any]] = defaultdict(dict)
    for path, value in node['attributes'].items():
        endpoint_id, cluster_id, attribute_id = _split_path(path)
        by_endpoint_cluster[(endpoint_id, cluster_id)][attribute_id] = value
    return by_endpoint_cluster


class _OrderPreservingSafeDumper(yaml.SafeDumper):
    """
    yaml.SafeDumper unconditionally sorts plain-dict keys alphabetically on output
    (ruamel.yaml.representer.BaseRepresenter.__init__ hardcodes
    sort_base_mapping_type_on_output = True, not exposed as a yaml.dump() kwarg) - key order came
    back alphabetical instead of the intended remark/struct/matter_node/matter_endpoint order.
    Overridden here rather than switching to collections.OrderedDict, which dumps as an ugly
    !!omap-tagged sequence instead of plain YAML mappings - not what a copy-paste suggestion
    should look like.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sort_base_mapping_type_on_output = False


def _dump_yaml(data: dict[str, Any]) -> str:
    return yaml.dump(
        data, Dumper=_OrderPreservingSafeDumper, indent=4, width=768, allow_unicode=True, default_flow_style=False
    )


def generate_suggested_item(node: dict[str, Any], device_label: str | None = None) -> str | None:
    """
    Suggested item config for one node, as a copy-paste struct reference - not a per-attribute
    dump. Only clusters with a real, curated plugin.yaml struct (clusters.py's CLUSTER_STRUCTS)
    are suggested; everything else is intentionally left out (see this module's own docstring for
    why - the Discovery tab already covers "raw, uncurated data").

    Returns None when the device has no CLUSTER_STRUCTS-covered cluster at all. Otherwise emits one
    item block per covered endpoint - real need, not speculative: the bridge role routinely exposes
    several single-cluster endpoints under one node (e.g. a switch, a contact sensor, and a
    temperature sensor each on their own endpoint), unlike a single real device's several clusters
    usually sharing one endpoint (the shelly_plug_m_3gen case this function originally targeted).
    A single covered endpoint keeps the original bare `matter_node_<id>` key (unchanged, still what
    most real single-purpose devices produce); more than one gets `matter_node_<id>_ep<endpoint_id>`
    per block instead, since YAML mapping keys must be unique.

    Key order within each item block is deliberate: remark first (fastest way to identify which
    physical device this is), struct: second (what kind of item this is, self-explanatory via
    naming), matter_node/matter_endpoint last (Matter-internal plumbing, least relevant to a human
    scanning the block) - real user feedback on the previous per-attribute output, not an arbitrary
    choice. _dump_yaml()'s ruamel dumper preserves dict insertion order, so this is enforced simply
    by building each dict in this exact key order.
    """
    node_id = node['node_id']
    by_endpoint_cluster = _group_by_endpoint_cluster(node)

    by_endpoint: dict[int, list[str]] = defaultdict(list)
    for endpoint_id, cluster_id in sorted(by_endpoint_cluster):
        struct_name = cluster_struct_name(cluster_id)
        if struct_name is not None:
            by_endpoint[endpoint_id].append(struct_name)

    if not by_endpoint:
        return None

    multi = len(by_endpoint) > 1
    items: dict[str, Any] = {}
    for endpoint_id, struct_names in sorted(by_endpoint.items()):
        # remark leads with what the item IS (function label(s), e.g. "Schalter"), then which
        # physical device it belongs to - a bare device name told the user nothing about what a
        # given suggestion actually does once there was more than one device on the page (real
        # feedback: "the remark still only copies the name of the bridge"). Always set now (used
        # to be conditional on device_label alone) - the function label is always known here,
        # unlike device_label which the caller may not have.
        item: dict[str, Any] = {}
        function_labels = [cluster_struct_label(name) for name in struct_names]
        remark = ', '.join(function_labels)
        if device_label:
            remark += f' - {device_label}'
        item['remark'] = remark
        struct_refs = [f'matter.{name}' for name in struct_names]
        item['struct'] = struct_refs[0] if len(struct_refs) == 1 else struct_refs
        item['matter_node'] = node_id
        item['matter_endpoint'] = endpoint_id
        key = f'matter_node_{node_id}_ep{endpoint_id}' if multi else f'matter_node_{node_id}'
        items[key] = item

    return _dump_yaml(items)


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
