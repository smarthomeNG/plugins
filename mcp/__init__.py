#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
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
#########################################################################

import os
from ipaddress import ip_address

from lib.item import Items
from lib.logic import Logics
from lib.model.smartplugin import SmartPlugin
from lib.plugin import Plugins
from lib.scheduler import Scheduler
from lib.shtime import Shtime

from .access import ACCESS_ATTRIBUTE
from .clients import ClientRegistry
from .diagnostics import CoreDiagnostics, NoLogics
from .entitlement import LOCAL_TOKEN_ID, StaticEntitlementProvider
from .events import ItemEvents
from .history import DatabaseHistory
from .logs import LogReader
from .server import create_mcp_server
from .transport import McpHttpServer, TransportSettings
from .types import ClientStatus
from .webif import WebInterface

TOKEN_HINT = 'python -c "import secrets; print(secrets.token_urlsafe(32))"'


class Mcp(SmartPlugin):
    """Serves items and diagnostics to MCP clients over bearer-protected streamable HTTP."""

    PLUGIN_VERSION = '0.1.0'
    ALLOW_MULTIINSTANCE = False
    STOP_ON_ITEM_CHANGE = False

    def __init__(self, sh):
        super().__init__()
        self._smarthome = sh
        self._http: McpHttpServer | None = None
        self._events: ItemEvents | None = None
        self._bind_address: str = self.get_parameter_value('bind_address')
        self._port: int = self.get_parameter_value('port')
        self._token: str = self.get_parameter_value('token') or ''
        self._inherit_rw_access: bool = self.get_parameter_value('inherit_rw_access')
        self._max_page_size: int = self.get_parameter_value('max_page_size')
        self._wait_max_seconds: float = self.get_parameter_value('wait_max_seconds')

        if not self._token:
            self.logger.error(f'Parameter token is required, plugin not started. Generate one with: {TOKEN_HINT}')
            self._init_complete = False
            return
        try:
            local = StaticEntitlementProvider(
                self.get_parameter_value('default_access'),
                self._inherit_rw_access,
                self.get_parameter_value('expose'),
                self.get_parameter_value('write_rate_limit'),
            ).entitlement_for(LOCAL_TOKEN_ID)
            assert local is not None
            self._clients = ClientRegistry.build(self._token, local, self.get_parameter_value('clients'))
            self._transport = self._transport_settings()
            self._logs = LogReader(os.path.join(sh.get_vardir(), 'log'), self.get_parameter_value('log_redact'))
        except ValueError as e:
            self.logger.error(f'Invalid configuration, plugin not started: {e}')
            self._init_complete = False
            return
        self.init_webinterface(WebInterface)

    def _history_source(self, items: Items) -> DatabaseHistory | None:
        """Return the history source if a database plugin is running, None if get_item_history cannot be offered."""
        plugins = Plugins.get_instance()
        source = DatabaseHistory(plugins, items, self.get_parameter_value('history_plugin')) if plugins else None
        if source is not None and source.available():
            self.logger.info('a database plugin is running: get_item_history is offered')
            return source
        self.logger.info('no running database plugin: get_item_history is not offered')
        return None

    def _transport_settings(self) -> TransportSettings:
        """
        Read the exposure parameters.

        :raises ValueError: only one of the TLS files is set, or one of them is not a file
        """
        certfile = self.get_parameter_value('tls_certfile')
        keyfile = self.get_parameter_value('tls_keyfile')
        if bool(certfile) != bool(keyfile):
            raise ValueError('tls_certfile and tls_keyfile must be set together')
        for name, path in (('tls_certfile', certfile), ('tls_keyfile', keyfile)):
            if path and not os.path.isfile(path):
                raise ValueError(f'{name} {path!r} is not a file')
        return TransportSettings(
            tls_certfile=certfile or None,
            tls_keyfile=keyfile or None,
            allowed_hosts=tuple(self.get_parameter_value('allowed_hosts')),
            allowed_origins=tuple(self.get_parameter_value('allowed_origins')),
            auth_failure_limit=self.get_parameter_value('auth_failure_limit'),
        )

    def client_status(self) -> list[ClientStatus]:
        """Return the clients with their access, elevation and activity, for the web interface."""
        return self._clients.status()

    def elevate_client(self, name: str) -> None:
        """
        Raise a client's access ceiling for the time its settings allow.

        :raises ValueError: the client is unknown or cannot be elevated
        """
        self._clients.elevate(name)
        self.logger.warning(f'client {name!r} elevated through the web interface')

    def revoke_client(self, name: str) -> None:
        """End a client's elevation."""
        self._clients.revoke(name)
        self.logger.info(f'elevation of client {name!r} ended through the web interface')

    def endpoint_url(self) -> str:
        """Return the URL clients connect to; ``<host>`` stands for a bind address that is not a single host."""
        host = '<host>' if ip_address(self._bind_address).is_unspecified else self._bind_address
        port = self._http.port if self._http is not None else self._port
        return f'http://{host}:{port}/mcp'

    def parse_item(self, item):
        """
        Bind the item to the plugin if it carries an explicit ``mcp_access``.

        Binding lists the item for the plugin; access is resolved on every request from the item tree. A bound item
        reports its changes to ``subscriptions/listen`` streams through :meth:`update_item`.
        """
        if ACCESS_ATTRIBUTE in item.conf:
            self.add_item(item)
            return self.update_item
        return None

    def update_item(self, item, caller=None, source=None, dest=None):
        """Tell the open subscription streams that a bound item changed."""
        if self._events is not None:
            self._events.item_changed(item.property.path)

    @property
    def port(self) -> int:
        """Return the port the MCP server is bound to; only valid while running."""
        if self._http is None:
            raise RuntimeError('plugin is not running')
        return self._http.port

    def run(self) -> None:
        """Start the MCP server; warns about settings that widen access."""
        if self._inherit_rw_access:
            self.logger.warning('inherit_rw_access is enabled: child items inherit rw access from their parent')
        if not ip_address(self._bind_address).is_loopback:
            self.logger.warning(f'MCP server is bound to {self._bind_address}, reachable from the network')
            if self._transport.tls_certfile is None:
                self.logger.warning(
                    'no TLS configured: every token travels in clear text unless a TLS proxy is in front'
                )
            if not self._transport.allowed_hosts:
                self.logger.warning('allowed_hosts is empty: the Host and Origin headers are not checked')
        items = Items.get_instance()
        if items is None:
            self.logger.error('Item tree is not available, MCP server not started')
            return
        self._events = ItemEvents(items, self._clients)
        history = self._history_source(items)
        mcp_server = create_mcp_server(
            items,
            self._clients,
            self._build_diagnostics(),
            self._logs,
            max_page_size=self._max_page_size,
            wait_max_seconds=self._wait_max_seconds,
            subscriptions=self._events,
            history=history,
            max_history_days=self.get_parameter_value('history_max_days'),
        )
        self._http = McpHttpServer(mcp_server, self._clients, self._bind_address, self._port, self._transport)
        self._http.start()
        self.alive = True
        self.logger.info(f'MCP endpoint ready at http://{self._bind_address}:{self._http.port}/mcp')

    def _build_diagnostics(self) -> CoreDiagnostics:
        """Wire the diagnostics to the core registries that exist now."""
        plugins, scheduler, shtime = Plugins.get_instance(), Scheduler.get_instance(), Shtime.get_instance()
        if plugins is None or scheduler is None or shtime is None:
            raise RuntimeError('core registries are not available')
        logics = Logics.get_instance()
        if logics is None:
            self.logger.warning('Logics are not available, list_logics reports no logics')
        sh = self._smarthome
        return CoreDiagnostics(
            plugins,
            scheduler,
            logics or NoLogics(),
            sh.version,
            lambda: str(sh.shng_status.get('text', '')),
            lambda: float(shtime.runtime_as_dict()['total_seconds']),
        )

    def stop(self) -> None:
        """Stop the MCP server."""
        self.alive = False
        if self._http is not None:
            self._http.stop()
