"""
Pytest configuration for the mcp plugin tests.

Exposes Item at the top level of lib.item; the shared test mock (tests/mock/core.py) expects
it there while lib/item/__init__.py only re-exports Items. Same workaround as
plugins/jsonread/tests/conftest.py.
"""

import lib.item
import lib.item.item

if not hasattr(lib.item, 'Item'):
    setattr(lib.item, 'Item', lib.item.item.Item)
