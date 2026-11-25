from datetime import datetime

import pytest

from plugins.mcp.clients import ClientRegistry
from plugins.mcp.types import Access, Entitlement

LOCAL = Entitlement('local', 'none', False, frozenset(), 30)
TOKEN = 'desktop-token-0123456789'
SETTINGS = {'token': TOKEN, 'default_access': 'ro', 'max_access': 'ro', 'elevate_to': 'rw', 'elevate_minutes': 10}


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def clock():
    return Clock()


def registry(clock, settings=SETTINGS):
    return ClientRegistry.build('local-token-0123456789', LOCAL, {'desktop': settings}, clock=clock)


def granted(clients: ClientRegistry) -> Entitlement:
    entitlement = clients.entitlement_for('desktop')
    assert entitlement is not None
    return entitlement


def ceiling(clients: ClientRegistry) -> Access:
    return granted(clients).max_access


class TestElevation:
    def test_a_client_is_not_elevated_by_default(self, clock):
        assert ceiling(registry(clock)) == 'ro'

    def test_elevating_raises_the_ceiling_until_the_time_is_up(self, clock):
        clients = registry(clock)
        clients.elevate('desktop')
        assert ceiling(clients) == 'rw'
        clock.now += 9 * 60
        assert ceiling(clients) == 'rw'
        clock.now += 61
        assert ceiling(clients) == 'ro'

    def test_revoking_ends_the_elevation_at_once(self, clock):
        clients = registry(clock)
        clients.elevate('desktop')
        clients.revoke('desktop')
        assert ceiling(clients) == 'ro'

    def test_elevating_again_restarts_the_time(self, clock):
        clients = registry(clock)
        clients.elevate('desktop')
        clock.now += 9 * 60
        clients.elevate('desktop')
        clock.now += 9 * 60
        assert ceiling(clients) == 'rw'

    def test_only_the_ceiling_changes_while_elevated(self, clock):
        clients = registry(clock, {**SETTINGS, 'write_paths': ['lights.*']})
        before = granted(clients)
        clients.elevate('desktop')
        after = granted(clients)
        assert after == Entitlement(
            before.token_id,
            before.default_access,
            before.inherit_rw_access,
            before.expose,
            before.write_rate_limit,
            'rw',
            ('lights.*',),
        )

    @pytest.mark.parametrize('name', ['local', 'unknown'])
    def test_a_client_that_may_not_be_elevated_is_refused(self, clock, name):
        with pytest.raises(ValueError):
            registry(clock).elevate(name)

    def test_a_client_without_elevate_to_may_not_be_elevated(self, clock):
        clients = registry(clock, {'token': TOKEN})
        with pytest.raises(ValueError):
            clients.elevate('desktop')

    @pytest.mark.parametrize(
        'extra',
        [
            {'elevate_to': 'ro'},
            {'elevate_to': 'all'},
            {'elevate_minutes': 0},
            {'elevate_minutes': 'long'},
            {'elevate_minutes': 2000},
        ],
    )
    def test_invalid_elevation_settings_are_rejected(self, clock, extra):
        with pytest.raises(ValueError):
            registry(clock, {**SETTINGS, **extra})

    def test_elevate_minutes_without_elevate_to_is_rejected(self, clock):
        with pytest.raises(ValueError):
            registry(clock, {'token': TOKEN, 'elevate_minutes': 5})


class TestStatus:
    def test_status_lists_every_client_with_its_elevation(self, clock):
        clients = registry(clock)
        clients.elevate('desktop')
        clock.now += 60
        rows = {row['name']: row for row in clients.status()}
        assert set(rows) == {'local', 'desktop'}
        assert rows['desktop']['elevated_for'] == 9 * 60
        assert rows['desktop']['effective_max_access'] == 'rw'
        assert rows['desktop']['max_access'] == 'ro'
        assert rows['desktop']['elevate_to'] == 'rw'
        assert rows['local']['elevate_to'] is None
        assert rows['local']['elevated_for'] is None

    def test_status_counts_authenticated_requests(self, clock):
        clients = registry(clock)
        assert clients.authenticate(TOKEN) == 'desktop'
        assert clients.authenticate(TOKEN) == 'desktop'
        assert clients.authenticate('nope') is None
        rows = {row['name']: row for row in clients.status()}
        assert rows['desktop']['requests'] == 2
        assert isinstance(rows['desktop']['last_seen'], datetime)
        assert rows['local']['requests'] == 0
        assert rows['local']['last_seen'] is None
