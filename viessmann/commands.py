#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab

"""commands for dev viessmann

Assembles the per-model command/lookup definitions from plugins/viessmann/models/.
Each module in that package is expected to define:
    MODEL: str                     -- the model identifier, or 'ALL' for generic entries
    commands: dict[str, dict]      -- optional, opcode/reply definitions for MODEL
    lookups: dict[str, dict]       -- optional, value-lookup tables for MODEL

A module missing MODEL, or defining neither commands nor lookups, is skipped
with a logged error/warning rather than aborting the whole plugin -- this
lets a user drop in their own model module without risking the others.

models defined:

V200KW2
V200KO1B
V200WO1C
V200HO1C
VScotHO1_200_11
"""

import importlib
import logging
import pkgutil

from . import models as _models_pkg

logger = logging.getLogger(__name__)

# top-level dict attributes recognized by the SDP command loader
# (lib/model/sdp/commands.py / lib/model/smartdeviceplugin.py)
commands: dict = {}
lookups: dict = {}
structs: dict = {}

_MERGE_TARGETS = {'commands': commands, 'lookups': lookups, 'structs': structs}

for _finder, _modname, _ispkg in sorted(pkgutil.iter_modules(_models_pkg.__path__)):
    if _ispkg or _modname.startswith('_'):
        continue

    try:
        _mod = importlib.import_module(f'.models.{_modname}', __package__)
    except Exception as e:
        logger.error(f'viessmann: model module "{_modname}" failed to import, skipping. Error was: {e}')
        continue

    _model = getattr(_mod, 'MODEL', None)
    if not isinstance(_model, str) or not _model:
        logger.error(f'viessmann: model module "{_modname}" defines no valid MODEL string, skipping')
        continue

    _found_any = False
    for _attr, _target in _MERGE_TARGETS.items():
        _val = getattr(_mod, _attr, None)
        if _val is None:
            continue
        if not isinstance(_val, dict):
            logger.warning(
                f'viessmann: model module "{_modname}" defines "{_attr}" but it is not a dict '
                f'({type(_val).__name__}), ignoring this attribute'
            )
            continue
        if _val and not all(isinstance(v, dict) for v in _val.values()):
            logger.warning(
                f'viessmann: model module "{_modname}", "{_attr}" has non-dict values at the top '
                'level, this does not look like a valid commands/lookups table - loading anyway, '
                'expect parse errors'
            )
        if _model in _target:
            logger.warning(
                f'viessmann: model "{_model}" "{_attr}" already defined by another module, "{_modname}" overwrites it'
            )
        _target[_model] = _val
        _found_any = True

    if not _found_any:
        logger.warning(
            f'viessmann: model module "{_modname}" (MODEL={_model!r}) defines none of {list(_MERGE_TARGETS)}, ignoring'
        )
