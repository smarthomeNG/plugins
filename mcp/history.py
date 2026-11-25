"""Item history read from the database plugin."""

from collections.abc import Iterable
from typing import Protocol, TypeGuard

from .types import HistoryPoint, ItemSource, ToolFailure

DATABASE_SHORT_NAME = 'database'


class DatabasePluginLike(Protocol):
    """The part of the database plugin the history uses (its public API)."""

    @property
    def alive(self) -> bool: ...

    def get_configname(self) -> str: ...

    def get_shortname(self) -> str: ...

    def id(self, item: object, create: bool = ...) -> int | None: ...

    def readLogs(self, id: int, time_start: int | None = ..., time_end: int | None = ...) -> Iterable[tuple]: ...


class PluginRegistryLike(Protocol):
    """The part of the plugin registry the history reads."""

    def return_plugins(self) -> Iterable[object]: ...


class DatabaseHistory:
    """
    Reads item history from a running database plugin.

    The plugin is looked up on every call, so the history follows the plugin being started or stopped. A log row is
    ``(time, item_id, duration, val_str, val_num, val_bool, changed, val_quality)`` with times in milliseconds.
    """

    def __init__(self, plugins: PluginRegistryLike, items: ItemSource, config_name: str | None):
        """
        :param config_name: ``plugin.yaml`` section of the database plugin instance; None takes the first running
            instance of the ``database`` plugin
        """
        self._plugins = plugins
        self._items = items
        self._config_name = config_name or None

    def available(self) -> bool:
        """Return True if a running database plugin offers the calls the history needs."""
        return self._database() is not None

    def read(self, path: str, after_ms: int, before_ms: int) -> list[HistoryPoint] | None:
        """
        Return the item's logged values with ``after_ms < time < before_ms``, oldest first.

        :return: None if the item does not exist or the database does not log it
        :raises ToolFailure: ``unavailable`` if no database plugin is running
        """
        database = self._database()
        if database is None:
            raise ToolFailure('unavailable', 'no running database plugin')
        item = self._items.return_item(path)
        if item is None:
            return None
        db_id = database.id(item, create=False)
        if db_id is None:
            return None
        item_type = item.type() if hasattr(item, 'type') else ''
        rows = database.readLogs(db_id, time_start=after_ms, time_end=before_ms)
        return [_point(row, item_type) for row in sorted(rows, key=lambda row: row[0])]

    def _database(self) -> DatabasePluginLike | None:
        """Return the database plugin instance to read from, None if there is none that runs and offers the API."""
        for plugin in self._plugins.return_plugins():
            if not _offers_api(plugin):
                continue
            wanted = (
                plugin.get_configname() == self._config_name
                if self._config_name
                else plugin.get_shortname() == DATABASE_SHORT_NAME
            )
            if wanted and plugin.alive:
                return plugin
        return None


def _point(row: tuple, item_type: str) -> HistoryPoint:
    """Map a log row to a history point, taking the value from the column that belongs to the item's type."""
    time_ms, _item, _duration, text, number, boolean = row[:6]
    quality = row[7] if len(row) > 7 else 0
    if item_type == 'bool':
        value: object = None if boolean is None else bool(boolean)
    elif item_type == 'num':
        value = number
    elif item_type == 'str':
        value = text
    else:
        value = next((candidate for candidate in (number, boolean, text) if candidate is not None), None)
    return {'time_ms': int(time_ms), 'value': value, 'valid': quality == 0}


def _offers_api(plugin: object) -> TypeGuard[DatabasePluginLike]:
    """Return True if the plugin has the calls the history needs."""
    return all(callable(getattr(plugin, name, None)) for name in ('id', 'readLogs', 'get_configname', 'get_shortname'))
