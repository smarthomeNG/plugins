"""Entitlement providers."""

from collections.abc import Iterable

from .types import Entitlement, ExposeGroup, is_default_access, is_expose_group

LOCAL_TOKEN_ID = 'local'


class StaticEntitlementProvider:
    """Serves one entitlement, built from the plugin parameters, for the single local token."""

    def __init__(self, default_access: str, inherit_rw_access: bool, expose: Iterable[str], write_rate_limit: int):
        """
        Validate the parameters and build the entitlement.

        :raises ValueError: ``default_access`` is not ``none`` or ``ro``, or ``expose`` names an unknown group
        """
        if not is_default_access(default_access):
            raise ValueError(f"default_access must be 'none' or 'ro', got {default_access!r}")
        groups: set[ExposeGroup] = set()
        for name in expose:
            if not is_expose_group(name):
                raise ValueError(f'expose contains unknown group {name!r}')
            groups.add(name)
        self._entitlement = Entitlement(
            token_id=LOCAL_TOKEN_ID,
            default_access=default_access,
            inherit_rw_access=inherit_rw_access,
            expose=frozenset(groups),
            write_rate_limit=write_rate_limit,
        )

    def entitlement_for(self, token_id: str) -> Entitlement | None:
        """Return the entitlement of the local token, None for any other token id."""
        return self._entitlement if token_id == LOCAL_TOKEN_ID else None
