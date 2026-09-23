#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-  Sebastian Helms                 Morg @ knx-user-forum
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#
#  Web interface for the Matter plugin: a server view (devices, items,
#  discovery, aliases) and a bridge view. Every POST runs the actions its
#  fields select, stores their results as a one-shot flash for that view,
#  and redirects to a plain GET (Post-Redirect-Get).
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

import html
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Literal, Mapping

import cherrypy
import segno

from lib.model.smartplugin import SmartPluginWebIf

from ..server import NodesSnapshot, ServerRole
from ..server.discovery import discovery_rows, node_summary

if TYPE_CHECKING:
    from .. import Matter
    from ..bridge import BridgeRole

View = Literal['server', 'bridge']
Flash = dict[str, Any]
TEMPLATES: dict[View, str] = {'server': 'index.html', 'bridge': 'bridge.html'}


@dataclass(frozen=True)
class WebifAction:
    """A POST field that triggers an action on one view; run() returns the flash entries to show."""

    trigger: str
    view: View
    run: Callable[[WebInterface, Mapping[str, str]], Flash]


def _attempt(logger, error_key: str, label: str, action: Callable[[], Flash | None]) -> Flash:
    """Run an action; an exception becomes an error flash entry (and a log line) instead of a failed page."""
    try:
        return action() or {}
    except Exception as ex:
        logger.error(f'{label} failed: {ex}')
        return {error_key: str(ex) or type(ex).__name__}


def _escaped(value: Any) -> Any:
    """Strings HTML-escaped for the auto-update poll, which inserts values as HTML."""
    return html.escape(value) if isinstance(value, str) else value


class WebInterface(SmartPluginWebIf):
    def __init__(self, webif_dir, plugin: Matter):
        self.logger = plugin.logger
        self.webif_dir = webif_dir
        self.plugin = plugin
        self.tplenv = self.init_template_environment(autoescape_templates=tuple(TEMPLATES.values()))
        # One shared slot per view - a single-admin tool; two tabs posting at once may swap results.
        self._flash: dict[View, Flash] = {}

    # -- role access --

    def _server(self) -> ServerRole:
        if self.plugin.server is None:
            raise ValueError('the server role is disabled (server_enabled)')
        return self.plugin.server

    def _bridge(self) -> BridgeRole:
        if self.plugin.bridge is None:
            raise ValueError('the bridge role is disabled (bridge_enabled)')
        return self.plugin.bridge

    def _nodes(self) -> NodesSnapshot:
        server = self.plugin.server
        if server is None:
            return NodesSnapshot(error='the server role is disabled')
        return server.nodes_snapshot()

    # -- actions --

    def _commission(self, params: Mapping[str, str]) -> Flash:
        code = params['pairing_code'].strip()
        if not code:
            return {}

        def commission() -> None:
            self._server().start_commission(code)

        return _attempt(self.logger, 'commission_error', 'commissioning', commission)

    def _thread_dataset(self, params: Mapping[str, str]) -> Flash:
        dataset = params['thread_dataset'].strip()
        if not dataset:
            return {}
        server = self._server()
        if server.thread_dataset_is_set():
            return {'thread_dataset_error': 'already set - clear it first'}
        return _attempt(
            self.logger, 'thread_dataset_error', 'setting thread dataset', lambda: server.set_thread_dataset(dataset)
        )

    def _thread_dataset_fetch(self, params: Mapping[str, str]) -> Flash:
        server = self._server()
        if server.thread_dataset_is_set():
            return {'thread_dataset_error': 'already set - clear it first'}

        def fetch() -> None:
            server.fetch_thread_dataset_from_otbr()

        return _attempt(self.logger, 'thread_dataset_error', 'fetching thread dataset from OTBR', fetch)

    def _thread_dataset_clear(self, params: Mapping[str, str]) -> Flash:
        return _attempt(
            self.logger,
            'thread_dataset_error',
            'clearing thread dataset',
            lambda: self._server().clear_thread_dataset(),
        )

    def _unlink(self, params: Mapping[str, str]) -> Flash:
        node_id = int(params['unlink_node_id'])
        return _attempt(
            self.logger, 'unlink_error', f'removing node {node_id}', lambda: self._server().remove_node(node_id)
        )

    def _share(self, params: Mapping[str, str]) -> Flash:
        node_id = int(params['share_node_id'])

        def share() -> Flash:
            result = {'node_id': node_id, **self._server().open_commissioning_window(node_id)}
            result['qr_svg'] = self._qr_svg(result['setup_qr_code'])
            return {'share_result': result}

        return _attempt(self.logger, 'share_error', f'opening commissioning window for node {node_id}', share)

    def _remove_fabric(self, params: Mapping[str, str]) -> Flash:
        node_id = int(params['remove_fabric_node_id'])
        fabric_index = int(params['remove_fabric_index'])
        flash = _attempt(
            self.logger,
            'fabrics_error',
            f'removing fabric {fabric_index} from node {node_id}',
            lambda: self._server().remove_matter_fabric(node_id, fabric_index),
        )
        return flash or self._fabrics({'fabrics_node_id': str(node_id)})

    def _fabrics(self, params: Mapping[str, str]) -> Flash:
        node_id = int(params['fabrics_node_id'])
        return _attempt(
            self.logger,
            'fabrics_error',
            f'listing fabrics for node {node_id}',
            lambda: {'fabrics_result': {'node_id': node_id, 'fabrics': self._server().matter_fabrics(node_id)}},
        )

    def _interview(self, params: Mapping[str, str]) -> Flash:
        node_id = int(params['interview_node_id'])
        return _attempt(
            self.logger,
            'interview_error',
            f'interviewing node {node_id}',
            lambda: self._server().interview_node(node_id),
        )

    def _ip_addresses(self, params: Mapping[str, str]) -> Flash:
        node_id = int(params['ip_addresses_node_id'])
        return _attempt(
            self.logger,
            'ip_addresses_error',
            f'getting IP addresses for node {node_id}',
            lambda: {
                'ip_addresses_result': {'node_id': node_id, 'addresses': self._server().node_ip_addresses(node_id)}
            },
        )

    def _alias_create(self, params: Mapping[str, str]) -> Flash:
        name = params['alias_create_name'].strip()
        node_id = params.get('alias_create_node_id')
        if not name or not node_id:
            return {}
        return _attempt(
            self.logger,
            'alias_error',
            f"creating alias '{name}'",
            lambda: self._server().create_alias(name, int(node_id)),
        )

    def _alias_repoint(self, params: Mapping[str, str]) -> Flash:
        name = params['alias_repoint_name']
        node_id = params.get('alias_repoint_node_id')
        if not node_id:
            return {}
        return _attempt(
            self.logger,
            'alias_error',
            f"repointing alias '{name}'",
            lambda: self._server().repoint_alias(name, int(node_id)),
        )

    def _alias_remove(self, params: Mapping[str, str]) -> Flash:
        name = params['alias_remove_name']
        return _attempt(
            self.logger, 'alias_error', f"removing alias '{name}'", lambda: self._server().remove_alias(name)
        )

    def _suggest_item(self, params: Mapping[str, str]) -> Flash:
        node_id = int(params['suggest_item_node_id'])
        return _attempt(
            self.logger,
            'suggested_item_error',
            f'suggesting an item for node {node_id}',
            lambda: {
                'suggested_item_result': {'node_id': node_id, 'yaml': self._server().suggested_item_yaml(node_id)}
            },
        )

    def _create_item(self, params: Mapping[str, str]) -> Flash:
        node_id = int(params['create_item_node_id'])
        return _attempt(
            self.logger,
            'create_item_error',
            f'creating item(s) for node {node_id}',
            lambda: {'created_item_paths': self._server().create_suggested_items(node_id)},
        )

    def _open_bridge_window(self, params: Mapping[str, str]) -> Flash:
        return _attempt(
            self.logger,
            'open_bridge_window_error',
            'opening bridge commissioning window',
            lambda: self._bridge().open_commissioning_window(),
        )

    def _remove_bridge_fabric(self, params: Mapping[str, str]) -> Flash:
        fabric_index = int(params['remove_bridge_fabric_index'])
        return _attempt(
            self.logger,
            'remove_bridge_fabric_error',
            f'removing bridge fabric {fabric_index}',
            lambda: self._bridge().remove_fabric(fabric_index),
        )

    ACTIONS: tuple[WebifAction, ...] = (
        WebifAction('pairing_code', 'server', _commission),
        WebifAction('thread_dataset_clear', 'server', _thread_dataset_clear),
        WebifAction('thread_dataset', 'server', _thread_dataset),
        WebifAction('thread_dataset_fetch', 'server', _thread_dataset_fetch),
        WebifAction('unlink_node_id', 'server', _unlink),
        WebifAction('share_node_id', 'server', _share),
        WebifAction('remove_fabric_node_id', 'server', _remove_fabric),
        WebifAction('fabrics_node_id', 'server', _fabrics),
        WebifAction('interview_node_id', 'server', _interview),
        WebifAction('ip_addresses_node_id', 'server', _ip_addresses),
        WebifAction('alias_create_name', 'server', _alias_create),
        WebifAction('alias_repoint_name', 'server', _alias_repoint),
        WebifAction('alias_remove_name', 'server', _alias_remove),
        WebifAction('suggest_item_node_id', 'server', _suggest_item),
        WebifAction('create_item_node_id', 'server', _create_item),
        WebifAction('open_bridge_window', 'bridge', _open_bridge_window),
        WebifAction('remove_bridge_fabric_index', 'bridge', _remove_bridge_fabric),
    )

    def run_actions(self, view: View, params: Mapping[str, str]) -> Flash:
        """Run every action of *view* whose trigger field is present, in ACTIONS order; returns the merged flash."""
        flash: Flash = {}
        for action in self.ACTIONS:
            if action.view == view and action.trigger in params:
                try:
                    flash.update(action.run(self, params))
                except (KeyError, ValueError) as ex:
                    self.logger.error(f'webif action {action.trigger}: invalid request ({ex})')
                    flash['request_error'] = f'invalid request: {ex}'
        return flash

    # -- pages --

    @cherrypy.expose
    def index(self, view: str | None = None, **params: str):
        """
        Server view by default, bridge view with view=bridge. A POST runs the
        selected actions and redirects to a GET of the same view, which shows
        their results once.
        """
        page: View = 'bridge' if view == 'bridge' else 'server'
        if cherrypy.request.method == 'POST':
            self._flash[page] = self.run_actions(page, params)
            raise cherrypy.HTTPRedirect('index?view=bridge' if page == 'bridge' else 'index')

        flash = self._flash.pop(page, {})
        if page == 'bridge':
            return self._render_bridge(flash)
        return self._render_server(flash)

    def _render_server(self, flash: Flash):
        snapshot = self._nodes()
        server = self.plugin.server
        return self.tplenv.get_template(TEMPLATES['server']).render(
            p=self.plugin,
            server=server,
            items=self.plugin.mapped_items(),
            devices=[node_summary(node) for node in snapshot.nodes],
            nodes_error=snapshot.error,
            discovery_rows=[row for node in snapshot.nodes for row in discovery_rows(node)],
            aliases=server.aliases.snapshot() if server else {},
            thread_dataset_is_set=server.thread_dataset_is_set() if server else False,
            commission_jobs=server.commission_jobs() if server else [],
            flash=flash,
        )

    def _render_bridge(self, flash: Flash):
        bridge = self.plugin.bridge
        status = bridge.bridge_status() if bridge else {'available': False}
        qr_svg = self._qr_svg(status['qr_pairing_code']) if status.get('available') else None
        return self.tplenv.get_template(TEMPLATES['bridge']).render(
            p=self.plugin,
            bridge=bridge,
            bridge_status=status,
            bridge_qr_svg=qr_svg,
            bridge_fabrics=bridge.bridge_fabrics() if bridge else [],
            bridge_items=bridge.bridged_items() if bridge else [],
            flash=flash,
        )

    @cherrypy.expose
    def get_data_html(self, dataSet=None, params=None):
        """
        Periodic auto-update data: item values (Items tab), device availability
        (Devices tab), cached discovery values keyed '<node_id>_<path>'
        (Discovery tab), and commissioning job states. matter-server's
        get_nodes() is a local cache read, fetched once per poll.
        """
        if dataSet is not None:
            return json.dumps({})
        snapshot = self._nodes()
        server = self.plugin.server
        data = {
            'items': {item.property.path: _escaped(item()) for item in self.plugin.mapped_items()},
            'devices': {node['node_id']: node['available'] for node in snapshot.nodes},
            'discovery': {
                f'{row["node_id"]}_{row["path"]}': _escaped(row['value'])
                for node in snapshot.nodes
                for row in discovery_rows(node)
            },
            'commission_jobs': server.commission_jobs() if server else [],
        }
        return json.dumps(data, default=str)

    def _qr_svg(self, text: str) -> str:
        """Inline SVG (no XML declaration) of a Matter QR pairing code, for embedding with |safe."""
        return segno.make(text).svg_inline(scale=4, border=2)
