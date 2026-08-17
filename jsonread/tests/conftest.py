"""
Pytest configuration and fixtures for the jsonread plugin tests.

Patches lib.item to expose Item at the top-level namespace.

Background: lib/item/__init__.py only re-exports Items (the container),
not Item (the individual item class).  The shared SmartHomeNG test mock
(tests/mock/core.py) still uses lib.item.Item, which causes an
AttributeError on current shng code.  Until that mock is fixed upstream,
we patch it here so this test suite can run without a modified shng
checkout. Same workaround as plugins/database/tests/conftest.py.
"""

import lib.item
import lib.item.item

if not hasattr(lib.item, 'Item'):
    lib.item.Item = lib.item.item.Item
