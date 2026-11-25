import lib.config
import pytest

from plugins.mcp.clients import ClientRegistry, parse_clients
from plugins.mcp.types import Entitlement

LOCAL = Entitlement('local', 'none', False, frozenset({'system'}), 30)
LOCAL_TOKEN = 'local-token-0123456789'
DESKTOP_TOKEN = 'desktop-token-0123456789'


def registry(clients=None):
    return ClientRegistry.build(LOCAL_TOKEN, LOCAL, clients or {})


class TestAuthentication:
    def test_the_local_token_authenticates_as_local(self):
        assert registry().authenticate(LOCAL_TOKEN) == 'local'

    def test_a_client_token_authenticates_as_its_client(self):
        assert registry({'desktop': {'token': DESKTOP_TOKEN}}).authenticate(DESKTOP_TOKEN) == 'desktop'

    @pytest.mark.parametrize('presented', ['', 'nope', LOCAL_TOKEN + 'x', LOCAL_TOKEN[:-1]])
    def test_any_other_token_is_refused(self, presented):
        assert registry({'desktop': {'token': DESKTOP_TOKEN}}).authenticate(presented) is None


class TestEntitlements:
    def test_the_local_entitlement_is_the_one_given(self):
        assert registry().entitlement_for('local') == LOCAL

    def test_an_unknown_client_has_no_entitlement(self):
        assert registry().entitlement_for('desktop') is None

    def test_a_client_without_settings_is_read_only_and_sees_nothing_by_default(self):
        entitlement = registry({'desktop': {'token': DESKTOP_TOKEN}}).entitlement_for('desktop')
        assert entitlement == Entitlement('desktop', 'none', False, frozenset(), 30, 'ro')

    def test_a_client_takes_its_own_settings(self):
        settings = {
            'token': DESKTOP_TOKEN,
            'default_access': 'ro',
            'inherit_rw_access': True,
            'expose': ['logs', 'system'],
            'max_access': 'rw',
            'write_rate_limit': 5,
            'write_paths': ['lights.*', 'heating.setpoint'],
        }
        entitlement = registry({'desktop': settings}).entitlement_for('desktop')
        assert entitlement == Entitlement(
            'desktop', 'ro', True, frozenset({'logs', 'system'}), 5, 'rw', ('lights.*', 'heating.setpoint')
        )


class TestValidation:
    @pytest.mark.parametrize(
        'clients',
        [
            {'desktop': {}},
            {'desktop': {'token': ''}},
            {'desktop': {'token': 'short'}},
            {'desktop': {'token': 123456789012345678}},
            {'desktop': 'token'},
            {'local': {'token': DESKTOP_TOKEN}},
            {'desktop': {'token': LOCAL_TOKEN}},
            {'a': {'token': DESKTOP_TOKEN}, 'b': {'token': DESKTOP_TOKEN}},
            {'desktop': {'token': DESKTOP_TOKEN, 'typo': 1}},
            {'desktop': {'token': DESKTOP_TOKEN, 'default_access': 'rw'}},
            {'desktop': {'token': DESKTOP_TOKEN, 'max_access': 'all'}},
            {'desktop': {'token': DESKTOP_TOKEN, 'expose': ['cpu']}},
            {'desktop': {'token': DESKTOP_TOKEN, 'expose': 'logs'}},
            {'desktop': {'token': DESKTOP_TOKEN, 'write_rate_limit': 'many'}},
            {'desktop': {'token': DESKTOP_TOKEN, 'inherit_rw_access': 'yes'}},
            {'desktop': {'token': DESKTOP_TOKEN, 'write_paths': 'lights.*'}},
            {'desktop': {'token': DESKTOP_TOKEN, 'write_paths': ['']}},
            {'desktop': {'token': DESKTOP_TOKEN, 'write_paths': [1]}},
        ],
    )
    def test_an_invalid_client_definition_is_rejected(self, clients):
        with pytest.raises(ValueError):
            registry(clients)

    def test_parse_clients_names_the_offending_client(self):
        with pytest.raises(ValueError, match="client 'desktop'"):
            parse_clients({'desktop': {'token': 'short'}}, default_rate_limit=30)


class TestValuesFromPluginYaml:
    """shng's config loader turns every scalar inside the clients parameter into text."""

    YAML = """\
mcp:
    clients:
        desktop:
            token: desktop-token-0123456789
            default_access: ro
            inherit_rw_access: true
            expose: [system]
            max_access: ro
            write_rate_limit: 7
            write_paths: ['lights.*']
            elevate_to: rw
            elevate_minutes: 10
"""

    def clients(self, tmp_path, yaml=YAML):
        path = tmp_path / 'plugin.yaml'
        path.write_text(yaml)
        return lib.config.parse(str(path))['mcp']['clients']

    def test_text_values_are_read_as_numbers_and_flags(self, tmp_path):
        entitlement = ClientRegistry.build(LOCAL_TOKEN, LOCAL, self.clients(tmp_path)).entitlement_for('desktop')
        assert entitlement == Entitlement('desktop', 'ro', True, frozenset({'system'}), 7, 'ro', ('lights.*',))

    def test_the_elevation_settings_survive_the_loader(self, tmp_path):
        row = ClientRegistry.build(LOCAL_TOKEN, LOCAL, self.clients(tmp_path)).status()[1]
        assert (row['elevate_to'], row['elevate_minutes']) == ('rw', 10)

    @pytest.mark.parametrize(
        ('key', 'value'), [('inherit_rw_access', 'maybe'), ('write_rate_limit', '7x'), ('elevate_minutes', 'soon')]
    )
    def test_text_that_is_no_number_or_flag_is_rejected(self, tmp_path, key, value):
        yaml = self.YAML.replace(
            f'{key}: ' + {'inherit_rw_access': 'true', 'write_rate_limit': '7', 'elevate_minutes': '10'}[key],
            f'{key}: {value}',
        )
        with pytest.raises(ValueError):
            ClientRegistry.build(LOCAL_TOKEN, LOCAL, self.clients(tmp_path, yaml))


class TestAllowedNetworks:
    def clients(self, networks):
        return registry({'desktop': {'token': DESKTOP_TOKEN, 'allowed_networks': networks}})

    def test_without_networks_a_client_may_connect_from_anywhere(self):
        clients = registry({'desktop': {'token': DESKTOP_TOKEN}})
        assert clients.permits('desktop', '203.0.113.9')
        assert clients.permits('desktop', None)

    @pytest.mark.parametrize(
        ('peer', 'permitted'),
        [
            ('192.168.1.20', True),
            ('192.168.2.20', False),
            ('::1', True),
            ('::ffff:192.168.1.20', True),
            ('2001:db8::1', False),
            ('not an address', False),
            (None, False),
        ],
    )
    def test_a_client_with_networks_may_connect_only_from_them(self, peer, permitted):
        assert self.clients(['192.168.1.0/24', '::1']).permits('desktop', peer) is permitted

    def test_a_single_address_counts_as_a_network(self):
        assert self.clients(['10.0.0.5']).permits('desktop', '10.0.0.5')
        assert not self.clients(['10.0.0.5']).permits('desktop', '10.0.0.6')

    def test_the_local_client_is_not_restricted(self):
        assert registry().permits('local', '203.0.113.9')

    def test_an_unknown_client_is_not_permitted(self):
        assert not registry().permits('nobody', '127.0.0.1')

    @pytest.mark.parametrize('networks', ['192.168.1.0/24', ['300.0.0.0/8'], ['lan'], [1]])
    def test_invalid_networks_are_rejected(self, networks):
        with pytest.raises(ValueError):
            self.clients(networks)
