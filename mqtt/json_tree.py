"""
Mirror a JSON payload as an item tree.

Every scalar of the payload becomes an item whose ``mqtt_select_in`` selects it by JMESPath, so the items can
share the topic of an ancestor item (see ``mqtt_select_in`` in plugin.yaml).
"""

import json
import keyword
import re
from collections.abc import Callable
from typing import Any

JsonContainer = dict | list
"""Parsed JSON object or array"""

ItemTree = dict[str, Any]
"""Item definitions as in an item yaml file: child name -> attributes and nested child items"""

_INVALID_NAME_CHARS = re.compile(r'[^A-Za-z0-9_]')
_JMESPATH_IDENTIFIER = re.compile(r'[A-Za-z_][A-Za-z0-9_]*$')
_CORE_RESERVED_NAMES = {'set', 'get', 'property'}


def parse_json_value(value: Any) -> JsonContainer:
    """
    Return the JSON object or array held by an item value

    :param value: dict or list, or a str containing a JSON object or array
    :raises ValueError: if the value is neither
    """
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as e:
            raise ValueError(f'value is not valid JSON: {e}') from e
    if not isinstance(value, dict | list):
        raise ValueError('value is not a JSON object or array')
    return value


def sanitize_item_name(key: str) -> str:
    """Turn a JSON key into a name the item loader accepts: ``[A-Za-z0-9_]``, not starting with a digit or 'comment'"""
    name = _INVALID_NAME_CHARS.sub('_', key)
    if not name or name[0].isdigit() or name.startswith('comment'):
        name = 'n_' + name
    return name


def item_file_name(item_path: str) -> str:
    """File name of the item file generated for the item at ``item_path``"""
    return f'{item_path}.yaml'


def nest_under_path(item_path: str, tree: ItemTree) -> ItemTree:
    """Wrap ``tree`` as the children of the item at ``item_path``, as an item file defines them"""
    for name in reversed(item_path.split('.')):
        tree = {name: tree}
    return tree


def build_item_tree(payload: JsonContainer, is_reserved: Callable[[str], bool] = lambda name: False) -> ItemTree:
    """
    Build the item tree mirroring a JSON payload

    Objects and non-empty arrays become branch items, array elements are named ``item_<index>``. Scalars, empty
    objects/arrays and null become leaf items carrying ``type`` and ``mqtt_select_in``.

    :param payload:     parsed JSON object or array
    :param is_reserved: tells names that must not be used as item name, e.g. because the parent item already has
                        an attribute of that name
    """
    return _build_children(payload, '', is_reserved)


def _build_children(container: JsonContainer, expression: str, is_reserved: Callable[[str], bool]) -> ItemTree:
    entries = (
        [(f'item_{i}', f'{expression}[{i}]', value) for i, value in enumerate(container)]
        if isinstance(container, list)
        else [
            (key, f'{expression}.{_key_expression(key)}' if expression else _key_expression(key), value)
            for key, value in container.items()
        ]
    )
    tree: ItemTree = {}
    for name, child_expression, value in entries:
        name = _free_name(sanitize_item_name(name), tree, is_reserved)
        if isinstance(value, dict | list) and value:
            tree[name] = _build_children(value, child_expression, is_reserved)
        else:
            tree[name] = {'type': _item_type(value), 'mqtt_select_in': child_expression}
    return tree


def _key_expression(key: str) -> str:
    """JMESPath for an object key, quoted unless it is a plain identifier"""
    return key if _JMESPATH_IDENTIFIER.match(key) else json.dumps(key)


def _item_type(value: Any) -> str:
    if isinstance(value, bool):
        return 'bool'
    if isinstance(value, int | float):
        return 'num'
    if isinstance(value, dict):
        return 'dict'
    if isinstance(value, list):
        return 'list'
    return 'str'


def _free_name(name: str, siblings: ItemTree, is_reserved: Callable[[str], bool]) -> str:
    """Append ``_`` to ``name`` until the item loader accepts it and no sibling uses it"""
    while name in siblings or name in _CORE_RESERVED_NAMES or keyword.iskeyword(name) or is_reserved(name):
        name += '_'
    return name
