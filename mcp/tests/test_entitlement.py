import pytest

from plugins.mcp.entitlement import LOCAL_TOKEN_ID, StaticEntitlementProvider


def provider(**overrides):
    params = {'default_access': 'none', 'inherit_rw_access': False, 'expose': [], 'write_rate_limit': 30}
    params.update(overrides)
    return StaticEntitlementProvider(**params)


class TestStaticEntitlementProvider:
    def test_local_token_gets_the_configured_entitlement(self):
        ent = provider(
            default_access='ro', inherit_rw_access=True, expose=['logs', 'system'], write_rate_limit=5
        ).entitlement_for(LOCAL_TOKEN_ID)
        assert ent is not None
        assert ent.default_access == 'ro'
        assert ent.inherit_rw_access is True
        assert ent.expose == frozenset({'logs', 'system'})
        assert ent.write_rate_limit == 5
        assert ent.token_id == LOCAL_TOKEN_ID

    def test_unknown_token_has_no_entitlement(self):
        assert provider().entitlement_for('someone-else') is None

    def test_rw_is_not_a_valid_default_access(self):
        with pytest.raises(ValueError, match='default_access'):
            provider(default_access='rw')

    def test_unknown_expose_group_is_rejected(self):
        with pytest.raises(ValueError, match='expose'):
            provider(expose=['logs', 'config'])
