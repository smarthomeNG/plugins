"""Read-only runtime facts of the shng instance, taken from the public core API."""

import os
import platform
import threading
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import datetime
from typing import Protocol

from .types import (
    LogicSummary,
    PluginInfo,
    PluginSummary,
    RunningTaskInfo,
    SchedulerEntryInfo,
    SchedulerInfo,
    SystemInfo,
    ThreadInfo,
)


class PluginLike(Protocol):
    """The part of a loaded plugin instance the diagnostics read."""

    @property
    def alive(self) -> bool: ...

    def get_configname(self) -> str: ...

    def get_shortname(self) -> str: ...

    def get_instance_name(self) -> str: ...

    def get_version(self, extended: bool = False) -> str: ...

    def get_classname(self) -> str: ...

    def get_info(self) -> str: ...

    def is_multi_instance_capable(self) -> bool: ...

    def get_item_path_list(self, filter_key: str = '', filter_value: str = '', mode: str = '') -> list: ...


class PluginsLike(Protocol):
    """The part of the plugin registry the diagnostics read."""

    def return_plugins(self) -> Iterable[PluginLike]: ...


class RunningTaskLike(Protocol):
    """The part of a running scheduler task the diagnostics read."""

    @property
    def name(self) -> str: ...

    @property
    def task_type(self) -> str: ...

    @property
    def started_at(self) -> datetime: ...

    @property
    def runtime(self) -> float: ...


class SchedulerEntryLike(Protocol):
    """The part of a registered scheduler entry the diagnostics read."""

    @property
    def name(self) -> str: ...

    @property
    def prio(self) -> int: ...

    @property
    def active(self) -> bool: ...

    @property
    def next(self) -> datetime | None: ...

    @property
    def cycle(self) -> Mapping[object, object] | None: ...

    @property
    def cron(self) -> Mapping[object, object] | None: ...


class SchedulerLike(Protocol):
    """The part of the scheduler the diagnostics read."""

    def get_worker_count(self) -> int: ...

    def get_idle_worker_count(self) -> int: ...

    def get_running_tasks(self) -> Sequence[RunningTaskLike]: ...

    def get_entries(self) -> Sequence[SchedulerEntryLike]: ...


class LogicLike(Protocol):
    """The part of a logic the diagnostics read."""

    def last_run(self) -> datetime | None: ...


class LogicsLike(Protocol):
    """The part of the logics registry the diagnostics read."""

    def return_logics(self) -> Iterable[str]: ...

    def get_logic_info(self, name: str, ordered: bool = False) -> dict[str, object]: ...

    def return_logic(self, name: str) -> LogicLike | None: ...


class NoLogics:
    """Logics registry stand-in for an instance without loaded logics."""

    def return_logics(self) -> Iterable[str]:
        return []

    def get_logic_info(self, name: str, ordered: bool = False) -> dict[str, object]:
        return {}

    def return_logic(self, name: str) -> LogicLike | None:
        return None


class CoreDiagnostics:
    """Reads plugin, scheduler, logic, thread and system facts from the core objects."""

    def __init__(
        self,
        plugins: PluginsLike,
        scheduler: SchedulerLike,
        logics: LogicsLike,
        version: str,
        status: Callable[[], str],
        uptime: Callable[[], float],
    ):
        self._plugins = plugins
        self._scheduler = scheduler
        self._logics = logics
        self._version = version
        self._status = status
        self._uptime = uptime

    def list_plugins(self) -> list[PluginSummary]:
        """Return every loaded plugin instance."""
        return [self._plugin_summary(plugin) for plugin in self._plugins.return_plugins()]

    def get_plugin_info(self, config_name: str) -> PluginInfo | None:
        """Return the plugin instance with the given ``plugin.yaml`` section name, None if not loaded."""
        for plugin in self._plugins.return_plugins():
            if plugin.get_configname() == config_name:
                return {
                    **self._plugin_summary(plugin),
                    'classname': plugin.get_classname(),
                    'description': plugin.get_info(),
                    'multi_instance_capable': plugin.is_multi_instance_capable(),
                    'item_count': len(plugin.get_item_path_list()),
                }
        return None

    def get_scheduler_info(self) -> SchedulerInfo:
        """Return the worker thread counts, the tasks running right now and the registered entries."""
        tasks: list[RunningTaskInfo] = [
            {
                'name': task.name,
                'task_type': task.task_type,
                'started_at': task.started_at.isoformat(),
                'runtime_seconds': task.runtime,
            }
            for task in self._scheduler.get_running_tasks()
        ]
        entries: list[SchedulerEntryInfo] = [
            {
                'name': entry.name,
                'active': entry.active,
                'prio': entry.prio,
                'next': entry.next.isoformat() if entry.next is not None else None,
                'cycle': [str(seconds) for seconds in entry.cycle or ()],
                'cron': [str(expression) for expression in entry.cron or ()],
            }
            for entry in self._scheduler.get_entries()
        ]
        return {
            'workers': {'total': self._scheduler.get_worker_count(), 'idle': self._scheduler.get_idle_worker_count()},
            'running_tasks': tasks,
            'entries': entries,
        }

    def list_logics(self) -> list[LogicSummary]:
        """Return every loaded logic with its schedule; never the logic source."""
        summaries: list[LogicSummary] = []
        for name in self._logics.return_logics():
            info = self._logics.get_logic_info(name)
            logic = self._logics.return_logic(name)
            last_run = logic.last_run() if logic is not None else None
            summaries.append(
                {
                    'name': name,
                    'enabled': bool(info.get('enabled')),
                    'next_exec': _optional_text(info.get('next_exec')),
                    'last_run': last_run.isoformat() if last_run else None,
                    'cycle': _optional_text(info.get('cycle')),
                    'crontab': _optional_text(info.get('crontab')),
                    'watch_item': _text_list(info.get('watch_item')),
                }
            )
        return summaries

    def get_threads(self) -> list[ThreadInfo]:
        """Return the threads of the process, ordered by name."""
        threads = sorted(threading.enumerate(), key=lambda thread: thread.name)
        return [
            {'name': thread.name, 'ident': thread.ident, 'daemon': thread.daemon, 'alive': thread.is_alive()}
            for thread in threads
        ]

    def get_system_info(self) -> SystemInfo:
        """Return version, status, Python, platform, pid and uptime."""
        return {
            'version': self._version,
            'status': self._status(),
            'python': platform.python_version(),
            'platform': platform.platform(),
            'pid': os.getpid(),
            'uptime_seconds': self._uptime(),
        }

    @staticmethod
    def _plugin_summary(plugin: PluginLike) -> PluginSummary:
        return {
            'config_name': plugin.get_configname(),
            'plugin': plugin.get_shortname(),
            'instance': plugin.get_instance_name(),
            'version': plugin.get_version(),
            'running': bool(plugin.alive),
        }


def _optional_text(value: object) -> str | None:
    """Return the value as text, None if it is absent or empty."""
    return str(value) if value not in (None, '') else None


def _text_list(value: object) -> list[str]:
    """Return a single value or a collection of values as a list of texts; empty for absent or empty values."""
    if value in (None, ''):
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(entry) for entry in value]
    return [str(value)]
