"""Shared type definitions of the mcp plugin."""

from dataclasses import dataclass
from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Literal, Protocol, TypeGuard, runtime_checkable

# pydantic builds tool schemas from these and rejects typing.TypedDict below Python 3.12
from typing_extensions import TypedDict

Access = Literal['none', 'ro', 'rw']
DefaultAccess = Literal['none', 'ro']
ACCESS_VALUES: tuple[Access, ...] = ('none', 'ro', 'rw')
ExposeGroup = Literal['logs', 'scheduler', 'plugins', 'logics', 'threads', 'system', 'history']
DEFAULT_ACCESS_VALUES: tuple[DefaultAccess, ...] = ('none', 'ro')
EXPOSE_GROUPS: tuple[ExposeGroup, ...] = ('logs', 'scheduler', 'plugins', 'logics', 'threads', 'system', 'history')


def lower_access(first: Access, second: Access) -> Access:
    """Return the more restrictive of two access levels."""
    return ACCESS_VALUES[min(ACCESS_VALUES.index(first), ACCESS_VALUES.index(second))]


def is_access(value: object) -> TypeGuard[Access]:
    """Return True if the value is a valid access level."""
    return value in ACCESS_VALUES


def is_default_access(value: object) -> TypeGuard[DefaultAccess]:
    """Return True if the value is a valid plugin-wide default access level."""
    return value in DEFAULT_ACCESS_VALUES


def is_expose_group(value: object) -> TypeGuard[ExposeGroup]:
    """Return True if the value names a diagnostic group."""
    return value in EXPOSE_GROUPS


@dataclass(frozen=True)
class Entitlement:
    """
    What a token may see and do.

    ``max_access`` caps the access any item grants. ``write_paths``, if not None, lists the item path patterns
    (``fnmatch`` syntax, ``*`` also matches dots) that may stay ``rw``; every other item is read-only.
    """

    token_id: str
    default_access: DefaultAccess
    inherit_rw_access: bool
    expose: frozenset[ExposeGroup]
    write_rate_limit: int
    max_access: Access = 'rw'
    write_paths: tuple[str, ...] | None = None


class TokenAuthenticator(Protocol):
    """Maps a presented bearer token to the client that owns it and tells where that client may connect from."""

    def authenticate(self, presented: str) -> str | None: ...

    def permits(self, client: str, peer: str | None) -> bool: ...


class ClientStatus(TypedDict):
    """One client as the status page shows it."""

    name: str
    default_access: DefaultAccess
    max_access: Access
    effective_max_access: Access
    inherit_rw_access: bool
    expose: list[ExposeGroup]
    write_rate_limit: int
    write_paths: list[str] | None
    elevate_to: Access | None
    elevate_minutes: int | None
    allowed_networks: list[str] | None
    elevated_for: float | None
    requests: int
    last_seen: datetime | None


class EntitlementProvider(Protocol):
    """Maps a token id to its entitlement; None if the token is unknown."""

    def entitlement_for(self, token_id: str) -> Entitlement | None: ...


@runtime_checkable
class ItemNode(Protocol):
    """The part of a shng Item that access resolution reads; the root container does not match."""

    conf: dict[str, object]

    def id(self) -> str: ...

    def return_parent(self) -> object: ...


ErrorCode = Literal[
    'unauthorized',
    'unavailable',
    'not_found',
    'forbidden',
    'invalid_value',
    'rate_limited',
    'not_exposed',
    'bad_request',
    'timeout',
    'internal',
]


class ToolFailure(Exception):
    """A tool call that fails with a machine-readable code; the transport layer maps it to an MCP tool error."""

    def __init__(self, code: ErrorCode, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.code: ErrorCode = code
        self.message = message
        self.retry_after = retry_after


class ItemSummary(TypedDict):
    """Compact item view returned by ``list_items`` and ``get_item``."""

    path: str
    type: str
    value: object
    access: Access


class ItemDetail(ItemSummary):
    """Full item view returned by ``get_item(detail='full')``."""

    name: str
    description: str | None
    previous_value: object
    last_update: str | None
    last_change: str | None
    last_update_by: str
    last_change_by: str
    parent: str | None
    children: list[str]
    triggers: dict[str, list[str]]
    attributes: dict[str, object]


class AccessInfo(TypedDict):
    """Effective entitlement as reported by ``get_access_info``."""

    token_id: str
    default_access: DefaultAccess
    inherit_rw_access: bool
    max_access: Access
    write_paths: list[str] | None
    expose: list[ExposeGroup]
    write_rate_limit: int
    log_files: list[str]


class WriteResult(TypedDict):
    """Outcome of ``set_item``; ``value`` is read back right after the write and is best effort."""

    previous: object
    value: object
    changed: bool


class WaitResult(TypedDict):
    """Outcome of ``wait_for_change``; ``previous`` is the value when the wait began."""

    changed: bool
    value: object
    previous: object
    timed_out: bool


class ListItemsResult(TypedDict):
    """One page of ``list_items``; ``cursor`` is None on the last page."""

    items: list[ItemSummary]
    cursor: str | None


class ItemProperty(Protocol):
    """The part of a shng Item's ``property`` object the item tools read."""

    name: str
    description: str | None
    prev_value: object
    last_update: datetime | None
    last_change: datetime | None
    last_update_by: str
    last_change_by: str
    eval: str
    trigger: Sequence[str]
    on_update: Sequence[str]
    on_change: Sequence[str]


@runtime_checkable
class ReadableItem(ItemNode, Protocol):
    """The part of a shng Item the item tools read."""

    property: ItemProperty

    def return_children(self) -> Iterable['ReadableItem']: ...

    def type(self) -> str: ...

    def __call__(
        self, value: object = ..., caller: str = ..., source: str | None = ..., strict: bool = ...
    ) -> object: ...

    def cast(self, value: object, /) -> object: ...


class ItemSource(Protocol):
    """The part of the shng Items container the item tools use."""

    def return_item(self, path: str, /) -> ReadableItem | None: ...

    def return_items(self, ordered: bool = False) -> Iterable[ReadableItem]: ...


class PluginSummary(TypedDict):
    """One loaded plugin instance as listed by ``list_plugins``."""

    config_name: str
    plugin: str
    instance: str
    version: str
    running: bool


class PluginInfo(PluginSummary):
    """Status of one plugin instance as returned by ``get_plugin_info``; ``item_count`` is the number of items bound to it."""

    classname: str
    description: str
    multi_instance_capable: bool
    item_count: int


class WorkerInfo(TypedDict):
    """Scheduler worker thread counts."""

    total: int
    idle: int


class RunningTaskInfo(TypedDict):
    """A scheduler task currently executing."""

    name: str
    task_type: str
    started_at: str
    runtime_seconds: float


class SchedulerEntryInfo(TypedDict):
    """A registered scheduler entry; the called object and the value it passes are never included."""

    name: str
    active: bool
    prio: int
    next: str | None
    cycle: list[str]
    cron: list[str]


class SchedulerInfo(TypedDict):
    """Scheduler state as returned by ``list_schedulers``."""

    workers: WorkerInfo
    running_tasks: list[RunningTaskInfo]
    entries: list[SchedulerEntryInfo]


class LogicSummary(TypedDict):
    """One logic as listed by ``list_logics``; the source is never included."""

    name: str
    enabled: bool
    next_exec: str | None
    last_run: str | None
    cycle: str | None
    crontab: str | None
    watch_item: list[str]


class ThreadInfo(TypedDict):
    """One Python thread of the shng process."""

    name: str
    ident: int | None
    daemon: bool
    alive: bool


class SystemInfo(TypedDict):
    """Basic facts about the running instance."""

    version: str
    status: str
    python: str
    platform: str
    pid: int
    uptime_seconds: float


class ListPluginsResult(TypedDict):
    """One page of ``list_plugins``."""

    plugins: list[PluginSummary]
    cursor: str | None


class ListLogicsResult(TypedDict):
    """One page of ``list_logics``."""

    logics: list[LogicSummary]
    cursor: str | None


class GetThreadsResult(TypedDict):
    """One page of ``get_threads``."""

    threads: list[ThreadInfo]
    cursor: str | None


class LogEntryInfo(TypedDict):
    """One logical logfile entry; ``ts``, ``level`` and ``logger`` are None if the line does not match the format of the handler writing the file."""

    line: int
    ts: str | None
    level: str | None
    logger: str | None
    message: str


class GetLogsResult(TypedDict):
    """One page of ``get_logs``, newest entry first."""

    entries: list[LogEntryInfo]
    cursor: str | None


class HistoryPoint(TypedDict):
    """One logged value of an item as a history source reports it; ``valid`` is False for gaps and flagged rows."""

    time_ms: int
    value: object
    valid: bool


class HistoryEntry(TypedDict):
    """One logged value as ``get_item_history`` returns it; ``time`` is ISO 8601 in UTC."""

    time: str
    value: object
    valid: bool


class GetItemHistoryResult(TypedDict):
    """One page of ``get_item_history``, newest entry first."""

    path: str
    entries: list[HistoryEntry]
    cursor: str | None


class HistorySource(Protocol):
    """Where the logged values of items come from."""

    def read(self, path: str, after_ms: int, before_ms: int) -> list[HistoryPoint] | None:
        """
        Return the item's logged values with ``after_ms < time < before_ms`` (milliseconds since the epoch).

        :return: None if the item has no history
        :raises ToolFailure: ``unavailable`` if the source is not running
        """
        ...


class DiagnosticsSource(Protocol):
    """Read-only runtime facts of the shng instance."""

    def list_plugins(self) -> list[PluginSummary]: ...

    def get_plugin_info(self, config_name: str) -> PluginInfo | None: ...

    def get_scheduler_info(self) -> SchedulerInfo: ...

    def list_logics(self) -> list[LogicSummary]: ...

    def get_threads(self) -> list[ThreadInfo]: ...

    def get_system_info(self) -> SystemInfo: ...
