import os
import platform
import threading
import time
from datetime import datetime, timezone

from lib.scheduler import RunningTask, Scheduler, SchedulerEntry

from plugins.mcp.diagnostics import CoreDiagnostics, NoLogics
from tests.mock.core import MockSmartHome


UPTIME_SECONDS = 12.5


def make_diagnostics():
    sh = MockSmartHome()
    assert sh.plugins is not None
    diagnostics = CoreDiagnostics(
        sh.plugins, Scheduler(sh), NoLogics(), sh.version, lambda: 'Running', lambda: UPTIME_SECONDS
    )
    return diagnostics, sh


class TestPlugins:
    def test_loaded_plugins_are_listed_with_name_instance_and_version(self):
        diagnostics, sh = make_diagnostics()
        listed = {entry['config_name']: entry for entry in diagnostics.list_plugins()}
        assert sh.plugins is not None
        expected = {plugin.get_configname(): plugin for plugin in sh.plugins.return_plugins()}
        assert listed.keys() == expected.keys()
        wol = listed['wol']
        assert wol['plugin'] == 'wol'
        assert wol['instance'] == ''
        assert wol['version'] == expected['wol'].get_version()
        assert wol['running'] is False

    def test_plugin_info_adds_class_and_description(self):
        diagnostics, sh = make_diagnostics()
        assert sh.plugins is not None
        info = diagnostics.get_plugin_info('wol')
        assert info is not None
        assert (
            info['classname']
            == type(next(p for p in sh.plugins.return_plugins() if p.get_configname() == 'wol')).__name__
        )
        assert info['multi_instance_capable'] in (True, False)
        assert info['item_count'] == 0

    def test_unknown_plugin_has_no_info(self):
        diagnostics, _ = make_diagnostics()
        assert diagnostics.get_plugin_info('does_not_exist') is None


class TestThreadsAndSystem:
    def test_threads_lists_running_threads_by_name(self):
        diagnostics, _ = make_diagnostics()
        stop = threading.Event()
        worker = threading.Thread(target=stop.wait, name='mcp-test-worker', daemon=True)
        worker.start()
        try:
            listed = {entry['name']: entry for entry in diagnostics.get_threads()}
        finally:
            stop.set()
            worker.join()
        assert listed['mcp-test-worker'] == {
            'name': 'mcp-test-worker',
            'ident': worker.ident,
            'daemon': True,
            'alive': True,
        }

    def test_system_info_reports_version_python_platform_and_pid(self):
        diagnostics, sh = make_diagnostics()
        info = diagnostics.get_system_info()
        assert info['version'] == sh.version
        assert info['status'] == 'Running'
        assert info['python'] == platform.python_version()
        assert info['platform'] == platform.platform()
        assert info['pid'] == os.getpid()
        assert info['uptime_seconds'] == UPTIME_SECONDS


class SchedulerStub:
    """Counts and tasks as the core's Scheduler reports them (real RunningTask objects)."""

    def __init__(self, tasks, entries=()):
        self._tasks = tasks
        self._entries = list(entries)

    def get_worker_count(self):
        return 4

    def get_idle_worker_count(self):
        return 3

    def get_running_tasks(self):
        return self._tasks

    def get_entries(self):
        return self._entries


class LogicsStub:
    """Logics as the core's Logics reports them: get_logic_info dicts and logic objects."""

    class Logic:
        def __init__(self, last_run):
            self._last_run = last_run

        def last_run(self):
            return self._last_run

    def __init__(self, infos, last_runs):
        self._infos = infos
        self._last_runs = last_runs

    def return_logics(self):
        return iter(self._infos)

    def get_logic_info(self, name, ordered=False):
        return self._infos[name]

    def return_logic(self, name):
        return self.Logic(self._last_runs.get(name))


def diagnostics_with(scheduler=None, logics=None):
    sh = MockSmartHome()
    assert sh.plugins is not None
    return CoreDiagnostics(
        sh.plugins, scheduler or SchedulerStub([]), logics or NoLogics(), sh.version, lambda: '', lambda: 0.0
    )


class TestScheduler:
    def test_workers_and_running_tasks_are_reported(self):
        started_at = datetime(2026, 11, 10, 12, 0, 0, tzinfo=timezone.utc)
        task = RunningTask(
            thread_ident=1,
            task_type='logic',
            name='logics.heating',
            started=time.monotonic() - 5,
            started_at=started_at,
        )
        info = diagnostics_with(scheduler=SchedulerStub([task])).get_scheduler_info()
        assert info['workers'] == {'total': 4, 'idle': 3}
        assert len(info['running_tasks']) == 1
        running = info['running_tasks'][0]
        assert running['name'] == 'logics.heating'
        assert running['task_type'] == 'logic'
        assert running['started_at'] == started_at.isoformat()
        assert running['runtime_seconds'] >= 5

    def test_scheduled_entries_are_reported_without_objects_or_values(self):
        next_run = datetime(2026, 11, 10, 13, 0, 0, tzinfo=timezone.utc)
        entries = [
            SchedulerEntry('logics.heating', object(), 2, True, next_run, {60: 'secret'}, None, 'secret'),
            SchedulerEntry('items.house.light', object(), 3, False, None, None, {'0 6 * * *': None, 'sunrise': 1}, 1),
        ]
        info = diagnostics_with(scheduler=SchedulerStub([], entries)).get_scheduler_info()
        assert info['entries'] == [
            {
                'name': 'logics.heating',
                'active': True,
                'prio': 2,
                'next': next_run.isoformat(),
                'cycle': ['60'],
                'cron': [],
            },
            {
                'name': 'items.house.light',
                'active': False,
                'prio': 3,
                'next': None,
                'cycle': [],
                'cron': ['0 6 * * *', 'sunrise'],
            },
        ]


class TestLogics:
    def test_logics_are_listed_with_their_schedule_and_never_their_source(self):
        infos = {
            'heating': {
                'name': 'heating',
                'enabled': True,
                'next_exec': '2026-11-10 13:00:00+0100',
                'cycle': 60,
                'crontab': None,
                'watch_item': ['house.temp'],
                'filename': 'heating.py',
                'pathname': '/etc/logics/heating.py',
                'description': 'secret-looking text',
            },
            'idle': {'name': 'idle', 'enabled': False, 'cycle': None, 'crontab': '', 'watch_item': ''},
            'single': {'name': 'single', 'enabled': True, 'watch_item': 'house.door'},
        }
        last_run = datetime(2026, 11, 10, 12, 0, 0, tzinfo=timezone.utc)
        listed = diagnostics_with(logics=LogicsStub(infos, {'heating': last_run})).list_logics()
        assert listed == [
            {
                'name': 'heating',
                'enabled': True,
                'next_exec': '2026-11-10 13:00:00+0100',
                'last_run': last_run.isoformat(),
                'cycle': '60',
                'crontab': None,
                'watch_item': ['house.temp'],
            },
            {
                'name': 'idle',
                'enabled': False,
                'next_exec': None,
                'last_run': None,
                'cycle': None,
                'crontab': None,
                'watch_item': [],
            },
            {
                'name': 'single',
                'enabled': True,
                'next_exec': None,
                'last_run': None,
                'cycle': None,
                'crontab': None,
                'watch_item': ['house.door'],
            },
        ]
