from plugins.mcp.logs import LogReader
from plugins.mcp.tools import get_access_info
from plugins.mcp.types import Entitlement


def test_access_info_reports_the_effective_entitlement():
    ent = Entitlement('local', 'ro', True, frozenset({'system', 'logs'}), 5, 'ro', ('lights.*',))
    assert get_access_info(ent, LogReader('/nonexistent')) == {
        'token_id': 'local',
        'default_access': 'ro',
        'inherit_rw_access': True,
        'max_access': 'ro',
        'write_paths': ['lights.*'],
        'expose': ['logs', 'system'],
        'write_rate_limit': 5,
        'log_files': [],
    }
