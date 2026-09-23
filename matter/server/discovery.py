#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-  Sebastian Helms                 Morg @ knx-user-forum
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#
#  Turns matter-server's cached node dump (get_nodes()) into flat rows for
#  the webif's discovery table, device table summaries, and suggested item
#  configs built on the generic plugin.yaml structs. The structs carry
#  matter_cluster/matter_attribute; a suggestion only adds matter_node and
#  matter_endpoint, inherited by every descendant item. Clusters without a
#  struct are not suggested - the discovery table covers their raw data.
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

import logging
from collections import defaultdict
from typing import Any, TypedDict

import ruamel.yaml as yaml

from ..clusters import attribute_info, cluster_name, cluster_struct, decode_value, device_type_name

# BasicInformation cluster (Core Spec 11.1): VendorName, ProductName, NodeLabel (user-settable).
BASIC_INFORMATION_CLUSTER = 0x28
VENDOR_NAME_ATTR = 0x01
PRODUCT_NAME_ATTR = 0x03
NODE_LABEL_ATTR = 0x05

# Descriptor cluster (Core Spec 9.5) DeviceTypeList - endpoint 0 only carries the RootNode type.
DESCRIPTOR_CLUSTER = 0x1D
DEVICE_TYPE_LIST_ATTR = 0x00


class MatterNode(TypedDict):
    """One node of matter-server's get_nodes()/start_listening() answer, as far as this plugin reads it."""

    node_id: int
    available: bool
    attributes: dict[str, Any]


class NodeSummary(TypedDict):
    node_id: int
    available: bool
    label: str
    node_label: str
    vendor: str
    product: str
    device_type: str


def parse_nodes(raw: Any, logger: logging.Logger | None = None) -> list[MatterNode]:
    """
    Validate matter-server's node list at the boundary: malformed entries
    are skipped with a warning instead of failing every consumer later.
    """
    if not isinstance(raw, list):
        if logger is not None:
            logger.warning(f'unexpected node list from matter-server: {raw!r}')
        return []
    nodes: list[MatterNode] = []
    for entry in raw:
        node_id = entry.get('node_id') if isinstance(entry, dict) else None
        attributes = entry.get('attributes') if isinstance(entry, dict) else None
        if not isinstance(node_id, int) or not isinstance(attributes, dict):
            if logger is not None:
                logger.warning(f'skipping malformed node from matter-server: {entry!r}')
            continue
        nodes.append(MatterNode(node_id=node_id, available=bool(entry.get('available')), attributes=attributes))
    return nodes


def _split_path(path: str) -> tuple[int, int, int] | None:
    parts = path.split('/')
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return None
    endpoint_id, cluster_id, attribute_id = (int(part) for part in parts)
    return endpoint_id, cluster_id, attribute_id


def discovery_rows(node: MatterNode) -> list[dict[str, Any]]:
    """Flatten one node's cached attribute dump into sorted discovery-table rows."""
    node_id = node['node_id']
    rows = []
    for path, value in node['attributes'].items():
        split = _split_path(path)
        if split is None:
            continue
        endpoint_id, cluster_id, attribute_id = split
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


def _clusters_by_endpoint(node: MatterNode) -> dict[int, set[int]]:
    clusters: dict[int, set[int]] = defaultdict(set)
    for path in node['attributes']:
        split = _split_path(path)
        if split is not None:
            clusters[split[0]].add(split[1])
    return clusters


class _OrderPreservingSafeDumper(yaml.SafeDumper):
    """SafeDumper that keeps dict insertion order - ruamel's SafeDumper sorts plain dict keys by default."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sort_base_mapping_type_on_output = False


def _dump_yaml(data: dict[str, Any]) -> str:
    return yaml.dump(
        data, Dumper=_OrderPreservingSafeDumper, indent=4, width=768, allow_unicode=True, default_flow_style=False
    )


def _instance_attr(attr: str, instance: str) -> str:
    return f'{attr}@{instance}' if instance else attr


def build_suggested_items(
    node: MatterNode, device_label: str | None = None, instance: str = ''
) -> dict[str, Any] | None:
    """
    Suggested item config for one node, keyed by item name - one block per
    endpoint that has at least one cluster with a generic struct, None if no
    endpoint has one. A single block is keyed `matter_node_<id>`, several are
    `matter_node_<id>_ep<endpoint>` (e.g. a bridge exposing one sensor per
    endpoint).

    Key order is remark, struct, matter_node, matter_endpoint - what the
    item is first, Matter plumbing last. For a named plugin *instance* the
    struct reference and the matter_* attributes carry `@<instance>`, which
    shng's struct expansion propagates to the struct's own
    `<attr>@instance` attributes.
    """
    node_id = node['node_id']
    structs_by_endpoint: dict[int, list] = {}
    for endpoint_id, cluster_ids in sorted(_clusters_by_endpoint(node).items()):
        structs = [spec for spec in (cluster_struct(cluster_id) for cluster_id in sorted(cluster_ids)) if spec]
        if structs:
            structs_by_endpoint[endpoint_id] = structs

    if not structs_by_endpoint:
        return None

    multi = len(structs_by_endpoint) > 1
    suffix = f'@{instance}' if instance else ''
    items: dict[str, Any] = {}
    for endpoint_id, structs in structs_by_endpoint.items():
        remark = ', '.join(spec.label for spec in structs)
        if device_label:
            remark += f' - {device_label}'
        struct_refs = [f'matter.{spec.name}{suffix}' for spec in structs]
        key = f'matter_node_{node_id}_ep{endpoint_id}' if multi else f'matter_node_{node_id}'
        items[key] = {
            'remark': remark,
            'struct': struct_refs[0] if len(struct_refs) == 1 else struct_refs,
            _instance_attr('matter_node', instance): node_id,
            _instance_attr('matter_endpoint', instance): endpoint_id,
        }
    return items


def generate_suggested_item(node: MatterNode, device_label: str | None = None, instance: str = '') -> str | None:
    """build_suggested_items() as copy-paste YAML text (or None)."""
    items = build_suggested_items(node, device_label, instance)
    return _dump_yaml(items) if items is not None else None


def _first_device_type(attrs: dict[str, Any]) -> str:
    endpoints = sorted(
        {split[0] for split in (_split_path(path) for path in attrs) if split and split[1] == DESCRIPTOR_CLUSTER}
    )
    for endpoint_id in endpoints:
        if endpoint_id == 0:
            continue
        device_types = attrs.get(f'{endpoint_id}/{DESCRIPTOR_CLUSTER}/{DEVICE_TYPE_LIST_ATTR}')
        if isinstance(device_types, list) and device_types and isinstance(device_types[0], dict):
            device_type_id = device_types[0].get('0')
            if isinstance(device_type_id, int):
                return device_type_name(device_type_id)
    return ''


def node_summary(node: MatterNode) -> NodeSummary:
    """
    Device-table row for a node. 'label' (node_label > product > "Node N")
    is for contexts needing some readable text; the table itself shows the
    raw node_label, blank when unset.
    """
    node_id = node['node_id']
    attrs = node['attributes']
    vendor = str(attrs.get(f'0/{BASIC_INFORMATION_CLUSTER}/{VENDOR_NAME_ATTR}') or '')
    product = str(attrs.get(f'0/{BASIC_INFORMATION_CLUSTER}/{PRODUCT_NAME_ATTR}') or '')
    node_label = str(attrs.get(f'0/{BASIC_INFORMATION_CLUSTER}/{NODE_LABEL_ATTR}') or '')
    return NodeSummary(
        node_id=node_id,
        available=node['available'],
        label=node_label or product or f'Node {node_id}',
        node_label=node_label,
        vendor=vendor,
        product=product,
        device_type=_first_device_type(attrs),
    )


def device_label(summary: NodeSummary) -> str:
    """
    Which physical device a suggestion belongs to, for its remark: vendor and
    product, plus node_label in parentheses if set and different from product.
    """
    base = f'{summary["vendor"]} {summary["product"]}'.strip() or f'Node {summary["node_id"]}'
    if summary['node_label'] and summary['node_label'] != summary['product']:
        return f'{base} ({summary["node_label"]})'
    return base
