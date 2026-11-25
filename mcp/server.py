"""MCP server assembly: registers the tools on the SDK server."""

import functools
import json
import threading
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal, ParamSpec, TypeVar

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ResourceNotFoundError, ToolError
from mcp.server.subscriptions import SubscriptionBus
from pydantic import JsonValue

from .events import ITEM_URI_PREFIX
from .identity import current_client
from .logs import LogReader
from .ratelimit import SlidingWindowLimiter
from .tools import DEFAULT_MAX_WINDOW_DAYS, DiagnosticsTools, HistoryTools, ItemTools, LogTools, get_access_info
from .types import (
    AccessInfo,
    DiagnosticsSource,
    GetItemHistoryResult,
    GetLogsResult,
    HistorySource,
    GetThreadsResult,
    ListLogicsResult,
    ListPluginsResult,
    PluginInfo,
    SchedulerInfo,
    SystemInfo,
    Entitlement,
    EntitlementProvider,
    ItemDetail,
    ItemSource,
    ItemSummary,
    ListItemsResult,
    ToolFailure,
    WaitResult,
    WriteResult,
)

P = ParamSpec('P')
R = TypeVar('R')

SERVER_NAME = 'shng'


def _failure_text(failure: ToolFailure) -> str:
    """Serialize a failure as the JSON text a client reads from an error result."""
    payload: dict[str, object] = {'code': failure.code, 'message': failure.message}
    if failure.retry_after is not None:
        payload['retry_after'] = failure.retry_after
    return json.dumps(payload)


def _as_tool_error(function: Callable[P, R]) -> Callable[P, R]:
    """Wrap a tool function so a ToolFailure becomes an MCP tool error carrying the JSON failure."""

    @functools.wraps(function)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return function(*args, **kwargs)
        except ToolFailure as failure:
            raise ToolError(_failure_text(failure)) from failure

    return wrapper


def _as_async_tool_error(function: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    """Async counterpart of :func:`_as_tool_error`."""

    @functools.wraps(function)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return await function(*args, **kwargs)
        except ToolFailure as failure:
            raise ToolError(_failure_text(failure)) from failure

    return wrapper


@dataclass(frozen=True)
class ToolSet:
    """The tool implementations of one client, built for one entitlement."""

    entitlement: Entitlement
    items: ItemTools
    diagnostics: DiagnosticsTools
    logs: LogTools
    history: HistoryTools | None


class ToolSets:
    """Serves the tool implementations of the client behind the running request."""

    def __init__(
        self,
        access: Entitlement | EntitlementProvider,
        items: ItemSource,
        logs: LogReader,
        diagnostics: DiagnosticsSource,
        default_page_size: int,
        max_page_size: int,
        wait_max_seconds: float,
        history: HistorySource | None = None,
        max_history_days: int = DEFAULT_MAX_WINDOW_DAYS,
    ):
        """
        :param access: the entitlement every caller has, or the provider that maps the current client to its own
        :param history: where ``get_item_history`` reads from; None offers no history
        """
        self._access = access
        self._items = items
        self._log_reader = logs
        self._diagnostics = diagnostics
        self._default_page_size = default_page_size
        self._max_page_size = max_page_size
        self._wait_max_seconds = wait_max_seconds
        self._history = history
        self._max_history_days = max_history_days
        self._cache: dict[str, ToolSet] = {}
        self._limiters: dict[str, SlidingWindowLimiter] = {}
        self._lock = threading.Lock()

    def entitlement(self) -> Entitlement:
        """
        Return the entitlement of the client behind the running request.

        :raises ToolFailure: ``unauthorized`` if the request has no client or the client no longer exists
        """
        if isinstance(self._access, Entitlement):
            return self._access
        client = current_client()
        entitlement = self._access.entitlement_for(client) if client is not None else None
        if entitlement is None:
            raise ToolFailure('unauthorized', 'no authorized client')
        return entitlement

    def current(self) -> ToolSet:
        """
        Return the tools of the client behind the running request.

        The set is rebuilt when the client's entitlement changed; its write budget survives that.
        """
        entitlement = self.entitlement()
        with self._lock:
            cached = self._cache.get(entitlement.token_id)
            if cached is None or cached.entitlement != entitlement:
                limiter = self._limiters.setdefault(entitlement.token_id, SlidingWindowLimiter())
                cached = self._cache[entitlement.token_id] = ToolSet(
                    entitlement,
                    ItemTools(
                        self._items,
                        entitlement,
                        self._default_page_size,
                        self._max_page_size,
                        wait_max_seconds=self._wait_max_seconds,
                        write_limiter=limiter,
                    ),
                    DiagnosticsTools(self._diagnostics, entitlement, self._default_page_size, self._max_page_size),
                    LogTools(self._log_reader, entitlement, self._default_page_size, self._max_page_size),
                    None
                    if self._history is None
                    else HistoryTools(
                        self._history,
                        self._items,
                        entitlement,
                        self._default_page_size,
                        self._max_page_size,
                        self._max_history_days,
                    ),
                )
            return cached


def create_mcp_server(
    items: ItemSource,
    access: Entitlement | EntitlementProvider,
    diagnostics: DiagnosticsSource,
    logs: LogReader,
    default_page_size: int = 50,
    max_page_size: int = 200,
    wait_max_seconds: float = 30.0,
    subscriptions: SubscriptionBus | None = None,
    history: HistorySource | None = None,
    max_history_days: int = DEFAULT_MAX_WINDOW_DAYS,
) -> MCPServer:
    """
    Build the MCP server with all tools registered.

    :param access: a fixed entitlement for every caller, or a provider that gives each authenticated client its
        own; a request without an authenticated client is refused with ``unauthorized`` in the latter case
    :param subscriptions: the bus ``subscriptions/listen`` streams read; the SDK's in-process bus if not given
    :param history: where ``get_item_history`` reads from; the tool is only registered if given
    """
    server = MCPServer(SERVER_NAME, subscriptions=subscriptions)
    tools = ToolSets(
        access, items, logs, diagnostics, default_page_size, max_page_size, wait_max_seconds, history, max_history_days
    )

    @server.tool(
        name='get_access_info',
        description="Report this connection's effective access: default access, rw inheritance, exposed groups.",
    )
    @_as_tool_error
    def access_info() -> AccessInfo:
        return get_access_info(tools.entitlement(), logs)

    @server.tool(
        description='List items visible to this connection, ordered by path, one page at a time. '
        'Pass the returned cursor to get the next page.'
    )
    @_as_tool_error
    def list_items(
        prefix: str | None = None,
        type: str | None = None,
        has_attr: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> ListItemsResult:
        return tools.current().items.list_items(prefix, type, has_attr, limit, cursor)

    @server.tool(description="Get one item. detail='value' returns path, type, value and access; 'full' adds metadata.")
    @_as_tool_error
    def get_item(path: str, detail: Literal['value', 'full'] = 'value') -> ItemSummary | ItemDetail:
        return tools.current().items.get_item(path, detail)

    @server.tool(
        description='Write a value to an item with rw access. The value is cast to the item type; null cannot be '
        'written. The result reports the previous value, the value read back right after the write (it can '
        'differ, for example through an eval) and whether the item changed.'
    )
    @_as_tool_error
    def set_item(path: str, value: JsonValue) -> WriteResult:
        return tools.current().items.set_item(path, value)

    @server.tool(
        description='Wait until an item changes value, for at most timeout seconds (capped by the server). '
        'Returns changed=false and timed_out=true if nothing changed; an update that keeps the value is not a change.'
    )
    @_as_async_tool_error
    async def wait_for_change(path: str, timeout: float = 10.0) -> WaitResult:
        return await tools.current().items.wait_for_change(path, timeout)

    @server.tool(
        description='List the loaded plugin instances, ordered by plugin.yaml section name, one page at a time.'
    )
    @_as_tool_error
    def list_plugins(limit: int | None = None, cursor: str | None = None) -> ListPluginsResult:
        return tools.current().diagnostics.list_plugins(limit, cursor)

    @server.tool(description='Get the status of one plugin instance by its plugin.yaml section name.')
    @_as_tool_error
    def get_plugin_info(name: str) -> PluginInfo:
        return tools.current().diagnostics.get_plugin_info(name)

    @server.tool(
        description='Report the scheduler: worker thread counts, the tasks running right now and the registered '
        'entries with next run, cycle and crontab.'
    )
    @_as_tool_error
    def list_schedulers() -> SchedulerInfo:
        return tools.current().diagnostics.list_schedulers()

    @server.tool(
        description='List the loaded logics with enabled state, next and last run, cycle, crontab and watch items. '
        'Never includes the logic source.'
    )
    @_as_tool_error
    def list_logics(limit: int | None = None, cursor: str | None = None) -> ListLogicsResult:
        return tools.current().diagnostics.list_logics(limit, cursor)

    @server.tool(description='List the threads of the shng process.')
    @_as_tool_error
    def get_threads(limit: int | None = None, cursor: str | None = None) -> GetThreadsResult:
        return tools.current().diagnostics.get_threads(limit, cursor)

    @server.tool(description='Report shng version, status, Python version, platform, pid and uptime.')
    @_as_tool_error
    def get_system_info() -> SystemInfo:
        return tools.current().diagnostics.get_system_info()

    @server.tool(
        description='Read a logfile (see log_files in get_access_info), newest entry first, one page at a time. '
        'level is a minimum level name, since an ISO timestamp and contains a case-insensitive text; level and since '
        "need lines in the format of the file's logging handler. Entries are "
        'logical: a traceback belongs to the entry before it. Secrets in messages are replaced by ***.'
    )
    @_as_tool_error
    def get_logs(
        file: str,
        level: str | None = None,
        since: str | None = None,
        contains: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> GetLogsResult:
        return tools.current().logs.get_logs(file, level, since, contains, limit, cursor)

    if history is not None:

        @server.tool(
            description='Read the logged values of an item from the database plugin, newest first, one page at a '
            'time. since is inclusive, until exclusive (ISO 8601; without them the last 24 hours); a time without an '
            "offset is the instance's local time and entries are in UTC. valid is false for gaps and flagged rows. "
            'Pass the returned cursor to continue.'
        )
        @_as_tool_error
        def get_item_history(
            path: str,
            since: str | None = None,
            until: str | None = None,
            limit: int | None = None,
            cursor: str | None = None,
        ) -> GetItemHistoryResult:
            history_tools = tools.current().history
            assert history_tools is not None
            return history_tools.get_item_history(path, since, until, limit, cursor)

    @server.resource(
        ITEM_URI_PREFIX + '{path}',
        name='item',
        description='One item with its metadata, as get_item(detail=full) returns it. Subscribe to it with '
        'subscriptions/listen to be told when it changes.',
        mime_type='application/json',
    )
    def item_resource(path: str) -> str:
        try:
            return json.dumps(tools.current().items.get_item(path, 'full'), default=str)
        except ToolFailure as failure:
            raise ResourceNotFoundError(_failure_text(failure)) from failure

    return server
