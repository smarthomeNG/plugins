"""Effective item access resolution."""

from fnmatch import fnmatchcase

from .types import Access, Entitlement, ItemNode, is_access, lower_access

ACCESS_ATTRIBUTE = 'mcp_access'


class AccessResolver:
    """Resolves the effective access of items for one entitlement."""

    def __init__(self, entitlement: Entitlement):
        self._entitlement = entitlement

    def effective_access(self, item: ItemNode) -> Access:
        """
        Return the access level the entitlement grants on the item.

        Walks from the item up through its parents; the first node carrying an explicit
        ``mcp_access`` decides:

        - ``none`` / ``ro`` apply to the node and all its descendants;
        - ``rw`` applies to the node itself; descendants get ``ro`` unless the entitlement
          has ``inherit_rw_access``;
        - an unknown value fails closed (``none``);
        - without any explicit value the entitlement's ``default_access`` applies.

        The entitlement's ``max_access`` caps the result, and ``rw`` is reduced to ``ro`` on a path outside its
        ``write_paths``.
        """
        access = lower_access(self._granted_access(item), self._entitlement.max_access)
        if access == 'rw' and not self._may_write(item.id()):
            return 'ro'
        return access

    def _may_write(self, path: str) -> bool:
        """Return True if the entitlement's ``write_paths`` allow writing the path."""
        patterns = self._entitlement.write_paths
        return patterns is None or any(fnmatchcase(path, pattern) for pattern in patterns)

    def _granted_access(self, item: ItemNode) -> Access:
        """Return the access the item tree grants before the entitlement's ceiling applies."""
        node: object = item
        while isinstance(node, ItemNode):
            explicit = node.conf.get(ACCESS_ATTRIBUTE)
            if explicit is not None:
                if not is_access(explicit):
                    return 'none'
                if explicit == 'rw' and node is not item and not self._entitlement.inherit_rw_access:
                    return 'ro'
                return explicit
            node = node.return_parent()
        return self._entitlement.default_access
