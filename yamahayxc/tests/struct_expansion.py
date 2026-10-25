"""The plugin's item structs, resolved with SmartHomeNG's own struct code (nested `struct:` references expanded)."""

import collections
import copy
import pathlib

from ruamel.yaml import YAML

from lib.item.structs import Structs

PLUGIN_YAML = pathlib.Path(__file__).parent.parent / 'plugin.yaml'


class _Quiet:
    """logger stand-in: Structs calls dbg* levels the stdlib logger does not have"""

    def __getattr__(self, level):
        return lambda *args, **kwargs: None


def expanded_structs() -> dict:
    """return {struct name: resolved definition} for every item struct of plugin.yaml"""
    definitions = YAML(typ='safe').load(PLUGIN_YAML.read_text())['item_structs']
    structs = Structs.__new__(Structs)
    structs.logger = _Quiet()
    structs._sh = None
    Structs._struct_definitions = collections.OrderedDict()
    Structs._finalized_structs = []
    for name, definition in definitions.items():
        structs.add_struct_definition(
            'yamahayxc', name, collections.OrderedDict(copy.deepcopy(definition)), from_dir='plugins'
        )
    resolving = True
    while resolving:
        resolving = False
        for name in list(Structs._struct_definitions):
            if name not in Structs._finalized_structs:
                if structs.traverse_struct(name):
                    resolving = True
                else:
                    Structs._finalized_structs.append(name)
    return {name.removeprefix('yamahayxc.'): definition for name, definition in Structs._struct_definitions.items()}


def item_paths(node: dict, prefix: str = '') -> set[str]:
    """dotted paths of all child items in a resolved struct"""
    paths = set()
    for key, value in node.items():
        if isinstance(value, dict):
            paths.add(prefix + key)
            paths |= item_paths(value, prefix + key + '.')
    return paths
