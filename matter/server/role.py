#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-  Sebastian Helms                 Morg @ knx-user-forum
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#
#  Matter controller ("server") role: commissions and controls real Matter
#  devices through the matter-server sidecar, mirrors cluster attributes
#  and commands onto shng items, and manages the matter_alias
#  node_id-indirection layer.
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

import collections
import functools
import itertools
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar

import lib.shyaml as shyaml

from ..aliases import AliasRegistry
from ..clusters import switch_info
from ..mapping import (
    AVAILABILITY,
    AliasNode,
    AttributeMapping,
    CommandMapping,
    DirectNode,
    ItemIndex,
    NodeTarget,
    dispatch_key,
)
from ..role import ItemRegistration, RoleHost
from ..rpc import TRANSIENT_ERRORS, describe_error
from ..sidecar_role import SidecarRole
from .client import MatterServerClient
from .discovery import (
    MatterNode,
    build_suggested_items,
    device_label,
    generate_suggested_item,
    node_summary,
    parse_nodes,
)
from .sidecar import MatterServerSidecar

if TYPE_CHECKING:
    from lib.item.item import Item

# Keys of this role's entries in SmartPlugin's per-item config data.
ATTRIBUTE_MAPPING_KEY = 'matter_attribute_mapping'
COMMAND_MAPPING_KEY = 'matter_command_mapping'
ALIAS_NAME_KEY = 'matter_alias_name'
AVAILABILITY_TARGET_KEY = 'matter_availability_target'

DEFAULT_ALIAS_BASE_REMARK = 'matter alias base item, child items are alias definitions, do not change'
OTBR_REQUEST_TIMEOUT = 5
COMMISSION_JOBS_KEPT = 10


@dataclass(frozen=True)
class ServerSettings:
    """Server role settings from plugin.yaml's server_* parameters."""

    alias_base_item: str = ''
    generated_items_file: str = 'matter_devices.yaml'
    generated_items_base: str = 'matter_devices'
    commission_timeout: float = 300.0
    otbr_rest_url: str = ''


class CommissionState(Enum):
    PENDING = 'pending'
    SUCCEEDED = 'succeeded'
    FAILED = 'failed'


@dataclass
class CommissionJob:
    """One commissioning attempt started from the webif, finished in the background."""

    job_id: int
    started_at: float
    state: CommissionState = CommissionState.PENDING
    detail: str = ''

    def finish(self, state: CommissionState, detail: str) -> None:
        self.detail = detail
        self.state = state

    def as_dict(self) -> dict[str, Any]:
        return {'job_id': self.job_id, 'started_at': self.started_at, 'state': self.state.value, 'detail': self.detail}


@dataclass(frozen=True)
class NodesSnapshot:
    """matter-server's node list for one webif render/poll, or why it could not be read."""

    nodes: tuple[MatterNode, ...] = ()
    error: str | None = None


class ServerRole(SidecarRole[MatterServerClient]):
    """
    Maps items to Matter devices via matter_node/matter_alias,
    matter_endpoint and matter_cluster (resolved up the item tree, instance
    aware) plus one of matter_attribute/matter_command/matter_switch/
    matter_available. Direct children of the alias base item define aliases.
    """

    name: ClassVar[str] = 'server'
    ITEM_ATTRIBUTES: ClassVar[tuple[str, ...]] = (
        'matter_attribute',
        'matter_command',
        'matter_switch',
        'matter_available',
    )

    def __init__(self, host: RoleHost, sidecar: MatterServerSidecar, settings: ServerSettings, url: str):
        super().__init__(host, sidecar)
        self.settings = settings
        self.url = url
        self.aliases = AliasRegistry()
        self._index = ItemIndex()
        self._jobs_lock = threading.Lock()
        self._jobs: collections.deque[CommissionJob] = collections.deque(maxlen=COMMISSION_JOBS_KEPT)
        self._job_ids = itertools.count(1)

    def own_caller(self) -> str:
        """
        Caller of this role's own item writes. Distinct from the bridge role's
        so an item carrying both roles' attributes still propagates a device
        report to the bridge (and vice versa); includes the instance name so
        instances don't suppress each other's writes.
        """
        return f'{self.host.get_fullname()}:server'

    # -- lifecycle --

    def _make_client(self) -> MatterServerClient:
        return MatterServerClient(self.url, on_event=self._on_event, logger=self.host.logger)

    async def _on_connected(self, client: MatterServerClient) -> None:
        """Push every node's cached values into items - unchanged state produces no later event."""
        for node in parse_nodes(await client.start_listening(), self.host.logger):
            self._seed_node(node)

    def _seed_node(self, node: MatterNode) -> None:
        """Push a node's cached attribute values and availability into its items."""
        for path, value in node['attributes'].items():
            self._apply(node['node_id'], path, value)
        self._apply(node['node_id'], AVAILABILITY, node['available'])

    def prepare(self) -> None:
        self._ensure_alias_base_item()
        for path, alias in self.aliases.unknown_references():
            self.host.logger.error(
                f"{path}: matter_alias '{alias}' is not a known alias - check it exists "
                f'as an item under {self.settings.alias_base_item}'
            )

    # -- incoming events --

    def _on_event(self, message: dict[str, Any]) -> None:
        event = message.get('event')
        if event == 'attribute_updated':
            try:
                node_id, path, value = message['data']
            except (KeyError, TypeError, ValueError):
                self.host.logger.warning(f'malformed attribute_updated event: {message}')
                return
            self._apply(node_id, path, value)
        elif event == 'node_updated':
            data = message.get('data') or {}
            node_id = data.get('node_id')
            available = data.get('available')
            if node_id is None or available is None:
                self.host.logger.warning(f'malformed node_updated event: {message}')
                return
            self._apply(node_id, AVAILABILITY, available)

    def _apply(self, node_id: int, report: str, value: Any) -> None:
        for target in self.aliases.targets_for(node_id):
            for item in self._index.items_for(dispatch_key(target, report)):
                item(value, self.own_caller())

    # -- item handling --

    def parse_item(self, item: Item) -> ItemRegistration | None:
        """
        Checked in order: alias definition > matter_available > matter_switch
        > matter_attribute/matter_command. Addressing attributes are resolved
        up the ancestor chain, so a child only states what differs from its
        device item; matter_alias wins over matter_node.
        """
        if self._is_alias_definition(item):
            return self._parse_alias_definition(item)
        if self.host.has_iattr(item.conf, 'matter_available'):
            return self._parse_availability(item)
        if self.host.has_iattr(item.conf, 'matter_switch'):
            return self._parse_switch(item)
        has_attribute = self.host.has_iattr(item.conf, 'matter_attribute')
        has_command = self.host.has_iattr(item.conf, 'matter_command')
        if not has_attribute and not has_command:
            return None

        addressing = self._resolve_addressing(item)
        if addressing is None:
            return None
        target, endpoint_id, cluster_id = addressing

        config: dict[str, Any] = {}
        if has_attribute:
            attribute_id = self._int_attr(
                item, 'matter_attribute', self.host.get_iattr_value(item.conf, 'matter_attribute')
            )
            if attribute_id is None:
                return None
            attribute_mapping = AttributeMapping(target, endpoint_id, cluster_id, attribute_id)
            config[ATTRIBUTE_MAPPING_KEY] = attribute_mapping
            self._index.add(dispatch_key(target, attribute_mapping.path), item)
        if has_command:
            config[COMMAND_MAPPING_KEY] = CommandMapping(
                target,
                endpoint_id,
                cluster_id,
                command_name=self.host.get_iattr_value(item.conf, 'matter_command'),
                params=self.host.get_iattr_value(item.conf, 'matter_command_params', {}) or {},
                command_name_false=self.host.get_iattr_value(item.conf, 'matter_command_false', None),
            )
        self._bind_target(item, target)
        return ItemRegistration(config)

    def _parse_availability(self, item: Item) -> ItemRegistration | None:
        target = self._resolve_target(item)
        if target is None:
            return None
        self._index.add(dispatch_key(target, AVAILABILITY), item)
        self._bind_target(item, target)
        return ItemRegistration({AVAILABILITY_TARGET_KEY: target}, updating=False)

    def _parse_switch(self, item: Item) -> ItemRegistration | None:
        addressing = self._resolve_addressing(item)
        if addressing is None:
            return None
        target, endpoint_id, cluster_id = addressing
        switch = switch_info(cluster_id)
        if switch is None:
            self.host.logger.error(
                f'{item.property.path}: matter_switch is set but no switch mapping is known for cluster {cluster_id} - '
                'use matter_attribute/matter_command/matter_command_false directly instead'
            )
            return None
        attribute_mapping = AttributeMapping(target, endpoint_id, cluster_id, switch.attribute_id)
        command_mapping = CommandMapping(
            target, endpoint_id, cluster_id, switch.command_true, command_name_false=switch.command_false
        )
        self._index.add(dispatch_key(target, attribute_mapping.path), item)
        self._bind_target(item, target)
        return ItemRegistration({ATTRIBUTE_MAPPING_KEY: attribute_mapping, COMMAND_MAPPING_KEY: command_mapping})

    def _bind_target(self, item: Item, target: NodeTarget) -> None:
        if isinstance(target, AliasNode):
            self.aliases.bind_item(item.property.path, target.name)

    def _resolve_addressing(self, item: Item) -> tuple[NodeTarget, int, int] | None:
        target = self._resolve_target(item)
        if target is None:
            return None
        values = []
        for attr in ('matter_endpoint', 'matter_cluster'):
            raw = item.find_attribute_with_instance(attr, default=None, plugin=self.host)
            if raw is None or raw == '':
                self.host.logger.error(f'{item.property.path}: {attr} not set on this item or any ancestor')
                return None
            value = self._int_attr(item, attr, raw)
            if value is None:
                return None
            values.append(value)
        return target, values[0], values[1]

    def _resolve_target(self, item: Item) -> NodeTarget | None:
        alias = item.find_attribute_with_instance('matter_alias', default=None, plugin=self.host)
        if alias:
            return AliasNode(str(alias))
        raw = item.find_attribute_with_instance('matter_node', default=None, plugin=self.host)
        if raw is None or raw == '':
            self.host.logger.error(
                f'{item.property.path}: matter_node or matter_alias not set on this item or any ancestor'
            )
            return None
        node_id = self._int_attr(item, 'matter_node', raw)
        return DirectNode(node_id) if node_id is not None else None

    def _int_attr(self, item: Item, attr: str, raw: Any) -> int | None:
        try:
            return int(raw)
        except (TypeError, ValueError):
            self.host.logger.error(f'{item.property.path}: {attr} must be an integer, got {raw!r}')
            return None

    def unparse_item(self, item: Item) -> bool:
        path = item.property.path
        handled = self._index.remove(path)
        handled = self.aliases.unbind_item(path) is not None or handled
        if self._is_alias_definition(item):
            name = path.rpartition('.')[2]
            if self.aliases.remove(name) is not None:
                dependents = self.aliases.dependents(name)
                if dependents:
                    self.host.logger.warning(
                        f"matter alias '{name}' removed while still referenced by: {', '.join(dependents)} - "
                        'writes to those items are dropped until the alias exists again'
                    )
            handled = True
        return handled

    def update_item(self, item: Item, caller: str | None, source: str | None, dest: str | None) -> None:
        if not self.host.alive or caller == self.own_caller():
            return
        config = self.host.get_item_config(item)
        if ALIAS_NAME_KEY in config:
            self._set_alias_from_item(item, config[ALIAS_NAME_KEY])
            return
        command_mapping: CommandMapping | None = config.get(COMMAND_MAPPING_KEY)
        attribute_mapping: AttributeMapping | None = config.get(ATTRIBUTE_MAPPING_KEY)
        mapping = command_mapping or attribute_mapping
        if mapping is None:
            return

        path = item.property.path
        value = item()
        if command_mapping is not None and not command_mapping.should_fire(value):
            return
        node_id = self.aliases.resolve(mapping.target)
        if node_id is None:
            self.host.logger.error(f"{path}: matter_alias '{mapping.target.name}' is not defined - write dropped")
            return
        client = self.client
        if client is None or not client.connected:
            self.host.logger.warning(f'cannot write {path}: not connected to matter server sidecar')
            return

        if command_mapping is not None:
            coro = client.device_command(
                node_id,
                command_mapping.endpoint_id,
                command_mapping.cluster_id,
                command_mapping.resolve_command_name(value),
                command_mapping.resolve_params(value),
            )
        else:
            coro = client.write_attribute(node_id, attribute_mapping.path, value)
        self.host.submit_asyncio_coro(coro, on_error=functools.partial(self._log_write_error, path))

    def _log_write_error(self, path: str, ex: BaseException) -> None:
        if isinstance(ex, TRANSIENT_ERRORS):
            self.host.logger.error(f'writing {path} to Matter failed: {describe_error(ex)}')
        else:
            self.host.logger.error(f'writing {path} to Matter failed: {ex!r}', exc_info=ex)

    def describe_item(self, item: Item) -> str | None:
        """Resolved addressing for the Items tab; '*' marks a value inherited from an ancestor."""
        config = self.host.get_item_config(item)
        attribute_mapping: AttributeMapping | None = config.get(ATTRIBUTE_MAPPING_KEY)
        command_mapping: CommandMapping | None = config.get(COMMAND_MAPPING_KEY)
        if ALIAS_NAME_KEY in config:
            return f'alias definition {config[ALIAS_NAME_KEY]}'
        if AVAILABILITY_TARGET_KEY in config:
            return ', '.join(['availability', *self._describe_target(item, config[AVAILABILITY_TARGET_KEY])])
        mapping = attribute_mapping or command_mapping
        if mapping is None:
            return None

        parts = self._describe_target(item, mapping.target)
        parts += [
            f'endpoint={self._mark(item, "matter_endpoint", mapping.endpoint_id)}',
            f'cluster={self._mark(item, "matter_cluster", mapping.cluster_id)}',
        ]
        if attribute_mapping is not None:
            parts.append(f'attribute={attribute_mapping.attribute_id}')
        if command_mapping is not None:
            parts.append(f'command={command_mapping.command_name}')
            if command_mapping.command_name_false is not None:
                parts.append(f'command_false={command_mapping.command_name_false}')
        return ', '.join(parts)

    def _mark(self, item: Item, attr: str, value: Any) -> str:
        return f'{value}' if self.host.has_iattr(item.conf, attr) else f'{value}*'

    def _describe_target(self, item: Item, target: NodeTarget) -> list[str]:
        if isinstance(target, AliasNode):
            node_id = self.aliases.resolve(target)
            return [
                f'alias={self._mark(item, "matter_alias", target.name)}',
                f'node={node_id if node_id is not None else "?"}',
            ]
        return [f'node={self._mark(item, "matter_node", target.node_id)}']

    # -- alias definitions --

    def _is_alias_definition(self, item: Item) -> bool:
        """True for a direct child of the configured alias base item."""
        base = self.settings.alias_base_item
        if not base:
            return False
        parent_path, sep, _name = item.property.path.rpartition('.')
        return sep != '' and parent_path == base

    def _parse_alias_definition(self, item: Item) -> ItemRegistration | None:
        """Every rule is checked, so one error message names everything wrong at once."""
        path = item.property.path
        errors = []
        if item._type != 'num':
            errors.append(f"type is '{item._type}', must be 'num'")
        elif not _is_node_id(item()):
            errors.append('no explicit (positive integer) value: set')
        if item._cache:
            errors.append('cache is set - the node_id must live in the item definition (etc/), not var/ cache')
        if 'database' in item.conf:
            errors.append('database is set - not appropriate for an alias definition')
        if item.property.eval:
            errors.append('eval is set - an alias value must be a plain literal, not computed')
        if errors:
            self.host.logger.error(f'{path}: not a valid matter alias definition - {"; ".join(errors)}')
            return None

        name = path.rpartition('.')[2]
        self._set_alias(name, int(item()))
        return ItemRegistration({ALIAS_NAME_KEY: name})

    def _set_alias_from_item(self, item: Item, name: str) -> None:
        value = item()
        if not _is_node_id(value):
            self.host.logger.error(f"{item.property.path}: {value!r} is not a valid node_id - alias '{name}' unchanged")
            return
        self._set_alias(name, int(value))

    def _set_alias(self, name: str, node_id: int) -> None:
        if self.aliases.set(name, node_id):
            self.host.logger.info(f"matter alias '{name}' -> node_id {node_id}")

    def _ensure_alias_base_item(self) -> None:
        """Give the (user-created) alias base item a default remark if it has none; never creates it."""
        base_path = self.settings.alias_base_item
        if not base_path:
            self.host.logger.info('alias_base_item is empty - matter_alias support disabled')
            return
        base_item = self.host.items.return_item(base_path)
        if base_item is None:
            example = '\n'.join(f'{"    " * i}{part}:' for i, part in enumerate(base_path.split('.')))
            self.host.logger.info(
                f"alias base item '{base_path}' not found - matter_alias support stays inactive until it exists. "
                f'Create it yourself, e.g.:\n{example}'
            )
            return
        if base_item.property.remark is None:
            config = _core_config(base_item)
            config['remark'] = DEFAULT_ALIAS_BASE_REMARK
            # only the remark changes, which no plugin registers
            self.host.items.edit_item(base_item, config, notify_plugins=False)
            self.host.logger.info(f"set default remark on alias base item '{base_path}'")

    # -- alias CRUD (webif) --

    def create_alias(self, name: str, node_id: int, remark: str = '') -> None:
        base_item = self._alias_base_item()
        path = f'{self.settings.alias_base_item}.{name}'
        if self.host.items.return_item(path) is not None:
            raise ValueError(f"'{name}' already exists")
        config: dict[str, Any] = {'type': 'num', 'value': node_id}
        if remark:
            config['remark'] = remark
        self.host.items.create_item(path, config, parent=base_item, filename=base_item.property.defined_in)

    def repoint_alias(self, name: str, node_id: int) -> None:
        alias_item = self._alias_item(name)
        config = _core_config(alias_item)
        config['value'] = node_id
        # alias items are this role's own node_id table - edit_item(notify_plugins=False) re-parses nothing
        self.host.items.edit_item(alias_item, config, notify_plugins=False)
        self._set_alias(name, node_id)

    def remove_alias(self, name: str) -> None:
        self.host.items.remove_item(self._alias_item(name))

    def _alias_base_item(self) -> Item:
        if not self.settings.alias_base_item:
            raise ValueError('alias_base_item is not configured')
        base_item = self.host.items.return_item(self.settings.alias_base_item)
        if base_item is None:
            raise ValueError(f"alias base item '{self.settings.alias_base_item}' does not exist - create it first")
        return base_item

    def _alias_item(self, name: str) -> Item:
        alias_item = self.host.items.return_item(f'{self.settings.alias_base_item}.{name}')
        if alias_item is None:
            raise ValueError(f"alias '{name}' does not exist")
        return alias_item

    # -- commissioning (webif) --

    def start_commission(self, code: str) -> CommissionJob:
        """
        Start commissioning in the background and return its job right away -
        the attempt can take minutes. The job's state is polled by the webif.
        """
        client = self._require_client()
        job = CommissionJob(next(self._job_ids), time.time())
        with self._jobs_lock:
            self._jobs.append(job)
        future = self.host.submit_asyncio_coro(self._commission(client, job, code))
        if future is None:
            job.finish(CommissionState.FAILED, 'plugin event loop is not running')
        return job

    async def _commission(self, client: MatterServerClient, job: CommissionJob, code: str) -> None:
        try:
            result = await client.commission_with_code(code, timeout=self.settings.commission_timeout)
        except TRANSIENT_ERRORS as ex:
            self.host.logger.error(f'commissioning failed: {describe_error(ex)}')
            job.finish(CommissionState.FAILED, describe_error(ex))
            return
        node_id = result.get('node_id') if isinstance(result, dict) else None
        self.host.logger.info(f'commissioned node_id={node_id}')
        job.finish(CommissionState.SUCCEEDED, f'node_id={node_id}')

    def commission_jobs(self) -> list[dict[str, Any]]:
        """Recent commissioning jobs, newest last."""
        with self._jobs_lock:
            return [job.as_dict() for job in self._jobs]

    # -- Thread network credentials (webif) --

    def set_thread_dataset(self, dataset: str) -> None:
        """Register the border router's active operational dataset (hex TLV) - once per Thread network."""
        client = self._require_client()
        self._call(client.set_thread_dataset(dataset))

    def clear_thread_dataset(self) -> None:
        client = self._require_client()
        self._call(client.remove_thread_dataset())

    def thread_dataset_is_set(self) -> bool:
        """False, not an error, while not connected."""
        client = self.client
        if client is None or client.server_info is None:
            return False
        return bool(client.server_info.get('thread_credentials_set'))

    def fetch_thread_dataset_from_otbr(self) -> str:
        """
        Read the active dataset from the border router's REST API
        (GET /node/dataset/active, Accept: text/plain returns hex TLV) and
        register it via set_thread_dataset().
        """
        if not self.settings.otbr_rest_url:
            raise ValueError('server_otbr_rest_url is not configured')
        url = self.settings.otbr_rest_url.rstrip('/') + '/node/dataset/active'
        request = urllib.request.Request(url, headers={'Accept': 'text/plain'})
        try:
            with urllib.request.urlopen(request, timeout=OTBR_REQUEST_TIMEOUT) as response:
                dataset = response.read().decode('utf-8').strip()
        except (urllib.error.URLError, OSError, ValueError) as ex:
            raise ValueError(f"could not reach the border router's REST API at {url}: {ex}") from ex
        if not dataset:
            raise ValueError(f'no active Thread dataset set on the border router at {url}')
        self.set_thread_dataset(dataset)
        return dataset

    # -- devices (webif) --

    def nodes_snapshot(self) -> NodesSnapshot:
        """Node list for one render/poll - an unreachable sidecar yields an error message, not an exception."""
        client = self.client
        if client is None or not client.connected:
            return NodesSnapshot(error='not connected to matter server sidecar')
        try:
            raw = self._call(client.get_nodes())
        except TRANSIENT_ERRORS as ex:
            return NodesSnapshot(error=describe_error(ex))
        return NodesSnapshot(tuple(parse_nodes(raw, self.host.logger)))

    def suggested_item_yaml(self, node_id: int) -> str | None:
        """Copy-paste YAML suggestion for one node, None if no cluster of it has a generic struct."""
        node = self._node(node_id)
        return generate_suggested_item(node, device_label(node_summary(node)), self.host.get_instance_name())

    def create_suggested_items(self, node_id: int) -> list[str]:
        """
        Create the suggestion for one node as real items under the configured
        base item (missing parents are created), persisted to the configured
        items file, and fill them with the node's cached values. Returns the
        created paths. Raises ValueError if there is
        nothing to suggest or a target path already exists.
        """
        node = self._node(node_id)
        items = build_suggested_items(node, device_label(node_summary(node)), self.host.get_instance_name())
        if items is None:
            raise ValueError('no suggested item for this device')
        filename = shyaml.strip_yaml_extension(self.settings.generated_items_file)
        paths = {f'{self.settings.generated_items_base}.{key}': config for key, config in items.items()}
        for path in paths:
            if self.host.items.return_item(path) is not None:
                raise ValueError(f"'{path}' already exists")
        for path, config in paths.items():
            self.host.items.create_item(path, config, filename=filename, create_missing_parents=True)
        self._seed_node(node)
        return list(paths)

    def _node(self, node_id: int) -> MatterNode:
        snapshot = self.nodes_snapshot()
        if snapshot.error is not None:
            raise ConnectionError(snapshot.error)
        node = next((n for n in snapshot.nodes if n['node_id'] == node_id), None)
        if node is None:
            raise ValueError(f'node {node_id} not found')
        return node

    def remove_node(self, node_id: int) -> None:
        client = self._require_client()
        self._call(client.remove_node(node_id))

    def open_commissioning_window(self, node_id: int) -> dict:
        client = self._require_client()
        return self._call(client.open_commissioning_window(node_id))

    def matter_fabrics(self, node_id: int) -> list:
        client = self._require_client()
        return self._call(client.get_matter_fabrics(node_id))

    def remove_matter_fabric(self, node_id: int, fabric_index: int) -> None:
        client = self._require_client()
        self._call(client.remove_matter_fabric(node_id, fabric_index))

    def interview_node(self, node_id: int) -> None:
        client = self._require_client()
        self._call(client.interview_node(node_id))

    def node_ip_addresses(self, node_id: int) -> list[str]:
        client = self._require_client()
        return self._call(client.get_node_ip_addresses(node_id))


def _is_node_id(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0 and int(value) == value


def _core_config(item: Item) -> dict[str, Any]:
    """
    Complete config dict for Items.edit_item(). type and remark are applied
    as attributes, not kept in item.conf, so they are added back explicitly.
    """
    config = {key: value for key, value in item.conf.items() if not key.startswith('_')}
    config['type'] = item._type
    if item.property.remark is not None:
        config['remark'] = item.property.remark
    return config
