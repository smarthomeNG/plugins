import os

from plugins.mcp.access import AccessResolver
from plugins.mcp.types import Access, DefaultAccess, Entitlement
from tests.mock.core import MockSmartHome

FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures', 'access_items.yaml')


def entitlement(
    default_access: DefaultAccess = 'none',
    inherit_rw_access: bool = False,
    max_access: Access = 'rw',
    write_paths: tuple[str, ...] | None = None,
) -> Entitlement:
    return Entitlement(
        token_id='local',
        default_access=default_access,
        inherit_rw_access=inherit_rw_access,
        expose=frozenset(),
        write_rate_limit=30,
        max_access=max_access,
        write_paths=write_paths,
    )


class TestEffectiveAccess:
    def setup_method(self):
        sh = MockSmartHome()
        sh.with_items_from(FIXTURE)
        assert sh.items is not None
        self.items = sh.items

    def access(
        self,
        path: str,
        default_access: DefaultAccess = 'none',
        inherit_rw_access: bool = False,
        max_access: Access = 'rw',
    ):
        item = self.items.return_item(path)
        assert item is not None
        return AccessResolver(entitlement(default_access, inherit_rw_access, max_access)).effective_access(item)

    def test_item_without_attribute_gets_default_access(self):
        assert self.access('unmarked') == 'none'

    def test_ro_is_inherited_by_descendants(self):
        assert self.access('house') == 'ro'
        assert self.access('house.living.temp') == 'ro'

    def test_none_carves_out_a_subtree_inside_a_ro_tree(self):
        assert self.access('house.alarm') == 'none'
        assert self.access('house.alarm.siren') == 'none'

    def test_rw_on_the_item_itself_grants_write(self):
        assert self.access('house.living.lamp') == 'rw'

    def test_ancestor_rw_is_ro_for_descendants_by_default(self):
        assert self.access('house.living.lamp.dimmer') == 'ro'
        assert self.access('house.garage.door') == 'ro'

    def test_ancestor_rw_is_inherited_when_enabled(self):
        assert self.access('house.living.lamp.dimmer', inherit_rw_access=True) == 'rw'
        assert self.access('house.garage.door', inherit_rw_access=True) == 'rw'

    def test_default_access_ro_applies_to_unmarked_items(self):
        assert self.access('unmarked', default_access='ro') == 'ro'
        assert self.access('unmarked.child', default_access='ro') == 'ro'

    def test_explicit_none_beats_default_ro(self):
        assert self.access('house.alarm', default_access='ro') == 'none'

    def test_unknown_access_value_fails_closed(self):
        assert self.access('typo', default_access='ro') == 'none'
        assert self.access('typo.child', default_access='ro') == 'none'


class TestCeiling:
    def setup_method(self):
        sh = MockSmartHome()
        sh.with_items_from(FIXTURE)
        assert sh.items is not None
        self.items = sh.items

    def access(self, path, max_access, **kwargs):
        item = self.items.return_item(path)
        assert item is not None
        return AccessResolver(entitlement(max_access=max_access, **kwargs)).effective_access(item)

    def test_a_ro_ceiling_turns_rw_into_ro(self):
        assert self.access('house.living.lamp', 'ro') == 'ro'

    def test_a_ceiling_does_not_raise_lower_access(self):
        assert self.access('house', 'rw') == 'ro'
        assert self.access('house.alarm', 'rw') == 'none'

    def test_a_none_ceiling_hides_everything(self):
        assert self.access('house.living.lamp', 'none') == 'none'
        assert self.access('house', 'none', default_access='ro') == 'none'

    def test_the_ceiling_also_caps_the_default_access(self):
        assert self.access('unmarked', 'none', default_access='ro') == 'none'


class TestWritePaths:
    def setup_method(self):
        sh = MockSmartHome()
        sh.with_items_from(FIXTURE)
        assert sh.items is not None
        self.items = sh.items

    def access(self, path, write_paths, **kwargs):
        item = self.items.return_item(path)
        assert item is not None
        return AccessResolver(entitlement(write_paths=write_paths, **kwargs)).effective_access(item)

    def test_without_write_paths_every_rw_item_stays_writable(self):
        assert self.access('house.living.lamp', None) == 'rw'

    def test_rw_survives_only_on_a_matching_path(self):
        assert self.access('house.living.lamp', ('house.living.*',)) == 'rw'
        assert self.access('house.garage', ('house.living.*',)) == 'ro'

    def test_a_glob_matches_the_whole_subtree_below_a_dot(self):
        assert self.access('house.living.lamp.dimmer', ('house.living.*',), inherit_rw_access=True) == 'rw'

    def test_any_of_several_globs_may_match(self):
        assert self.access('house.garage', ('house.living.*', 'house.garage')) == 'rw'

    def test_empty_write_paths_allow_no_write(self):
        assert self.access('house.living.lamp', ()) == 'ro'

    def test_write_paths_never_raise_read_access(self):
        assert self.access('house', ('house',)) == 'ro'
        assert self.access('house.alarm', ('house.*',)) == 'none'
