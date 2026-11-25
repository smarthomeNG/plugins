"""Shared test doubles for the mcp plugin tests."""

from plugins.mcp.types import LogicSummary, PluginInfo, PluginSummary, SchedulerInfo, SystemInfo, ThreadInfo

PLUGIN: PluginSummary = {'config_name': 'knx', 'plugin': 'knx', 'instance': '', 'version': '1.0', 'running': True}
SYSTEM: SystemInfo = {
    'version': 'v2',
    'status': 'Running',
    'python': '3.14',
    'platform': 'x',
    'pid': 1,
    'uptime_seconds': 2.0,
}
SCHEDULER: SchedulerInfo = {'workers': {'total': 4, 'idle': 4}, 'running_tasks': [], 'entries': []}


class StaticSource:
    """A DiagnosticsSource returning fixed data."""

    def __init__(self, plugin_count=1):
        self._plugin_count = plugin_count

    def list_plugins(self) -> list[PluginSummary]:
        return [{**PLUGIN, 'config_name': f'plugin{i:03d}'} for i in range(self._plugin_count)]

    def get_plugin_info(self, config_name: str) -> PluginInfo | None:
        if config_name != 'knx':
            return None
        return {**PLUGIN, 'classname': 'Knx', 'description': 'd', 'multi_instance_capable': False, 'item_count': 3}

    def get_scheduler_info(self) -> SchedulerInfo:
        return SCHEDULER

    def list_logics(self) -> list[LogicSummary]:
        return [
            {
                'name': 'b',
                'enabled': True,
                'next_exec': None,
                'last_run': None,
                'cycle': None,
                'crontab': None,
                'watch_item': [],
            }
        ]

    def get_threads(self) -> list[ThreadInfo]:
        return [{'name': 'main', 'ident': 1, 'daemon': False, 'alive': True}]

    def get_system_info(self) -> SystemInfo:
        return SYSTEM
