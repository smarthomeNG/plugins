#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2016-     Oliver Hinckel                  github@ollisnet.de
#########################################################################
#  This file is part of SmartHomeNG.
#
#  database plugin — per-item database_maxage_action/database_maxage_interval resolution
#########################################################################

"""
Resolves database_maxage_action/database_maxage_interval for an item, and the item list
relevant to native-mode aggregation.

Shared by query.py (native cagg routing), maintenance.py (plugin-side compaction), and
timescale.py (native aggregation setup) - all three need to resolve the same per-item
config, which is why this lives in its own module rather than any one of them (see
doc/dev/database/database.md §2 for the split's overall rationale).
"""


class MaxageResolver:
    """Resolves an item's effective database_maxage_action/database_maxage_interval,
    falling back to the plugin-level default_maxage_action/default_maxage_interval, and
    the item list native-mode aggregation must consider.

    Takes a back-reference to the Database plugin instance (*plugin*) rather than
    individual parameters - it needs has_iattr()/get_iattr_value() (SmartPlugin
    framework methods) plus several plugin-level config attributes, and a
    back-reference is far less churn than threading each of those through
    individually. See database.md §2's "Dependency wiring" note.
    """

    # database_maxage_action: value expressions, one scalar per compaction
    # interval. Deliberately mirrors (not DRY-shares) the fragments in
    # _single()'s `queries` dict - reusing the exact same SQL text without
    # refactoring _single()/_series() themselves, to avoid touching the
    # already-working on-demand query path while adding this feature.
    # 'diff'/'count' are intentionally left out for now ('diff' has two
    # conflicting meanings between _single/_series; parameterised 'count'
    # would need database_maxage_action to carry an expression, not just a
    # bare function name). 'first'/'last' are handled separately below
    # (_MAXAGE_EDGE_ACTIONS) - they pick a raw stored value rather than
    # computing a scalar over val_num/val_bool, so str-typed items can be
    # compacted too (nothing else here works for str).
    _MAXAGE_AGGREGATE_EXPR = {
        'avg': 'AVG(val_num * duration) / AVG(duration)',
        'sum': 'SUM(val_num)',
        'min': 'MIN(val_num)',
        'max': 'MAX(val_num)',
        'integrate': 'SUM(val_num * duration)',
        'duty_cycle': 'SUM(val_bool * duration) / SUM(duration)',
        'countall': 'COUNT(*)',
    }

    # 'first'/'last': keep the oldest/newest raw value in the interval as-is
    # (via LogStore.edge_value's ORDER BY ... LIMIT 1), instead of computing
    # anything over it. Maps action name -> SQL ORDER BY direction.
    _MAXAGE_EDGE_ACTIONS = {'first': 'ASC', 'last': 'DESC'}

    # item types each database_maxage_action is valid for. None = any type.
    # Grounded in utils.encode_value(): val_num is populated for 'num' and
    # 'bool' (bool encodes as float(value)), so avg/sum/min/max/integrate/
    # duty_cycle (which read val_num/val_bool) do not work for str -
    # duty_cycle would additionally store its float on-fraction back as the
    # item's string value. first/last just read back whatever encode_value()
    # already stored, so they work for every type, str included.
    _MAXAGE_ACTION_VALID_TYPES = {
        'avg': ('num', 'bool'),
        'sum': ('num', 'bool'),
        'min': ('num', 'bool'),
        'max': ('num', 'bool'),
        'integrate': ('num', 'bool'),
        'duty_cycle': ('bool',),
        'countall': None,
        'first': None,
        'last': None,
    }

    def __init__(self, plugin):
        self._plugin = plugin

    def action_for(self, item):
        """
        Resolve database_maxage_action for *item*, falling back to the
        plugin-level default_maxage_action when the item doesn't set its
        own. The item attribute deliberately has no schema default in
        plugin.yaml, so has_iattr() can distinguish "unset" from
        "explicitly delete" - mirrors the existing default_maxage pattern.

        Also the single enforcement point for the type-compatibility check
        (see _MAXAGE_ACTION_VALID_TYPES): an invalid action for this item's
        type always resolves to 'delete' here, regardless of whether
        parse_item()'s startup validation ran, so a bad config can never
        reach _compact_maxage() and run e.g. SUM(val_num) against a str
        item (val_num is always NULL there).

        :param item: item to resolve the action for
        :return: one of _MAXAGE_AGGREGATE_EXPR's or _MAXAGE_EDGE_ACTIONS' keys, or 'delete'
        """
        plugin = self._plugin
        if plugin.has_iattr(item.conf, 'database_maxage_action'):
            action = plugin.get_iattr_value(item.conf, 'database_maxage_action').lower()
        else:
            action = plugin._default_maxage_action

        if action == 'on':
            # Legacy alias for 'duty_cycle' - kept for configs that already
            # quote it (unquoted 'on' is YAML bool True and never reaches
            # here as this string in the first place).
            action = 'duty_cycle'

        if action == 'delete':
            return 'delete'

        known = action in self._MAXAGE_AGGREGATE_EXPR or action in self._MAXAGE_EDGE_ACTIONS
        valid_types = self._MAXAGE_ACTION_VALID_TYPES.get(action)
        if not known or (valid_types is not None and item.type() not in valid_types):
            return 'delete'
        return action

    def interval_seconds_for(self, item):
        """
        Resolve database_maxage_interval for *item* in seconds, falling
        back to the plugin-level default_maxage_interval. Same format as
        cycle/autotimer (lib.shtime.Shtime.to_seconds) - no 'd' (days)
        suffix supported.

        :param item: item to resolve the interval for
        :return: interval in seconds (int), never 0 or negative
        """
        plugin = self._plugin
        if plugin.has_iattr(item.conf, 'database_maxage_interval'):
            interval = plugin.get_iattr_value(item.conf, 'database_maxage_interval')
        else:
            interval = plugin._default_maxage_interval

        seconds = plugin.shtime.to_seconds(interval, test=True)
        if not seconds or seconds <= 0:
            plugin.logger.warning(
                f"Item {item.property.path}: invalid database_maxage_interval '{interval}', using 86400s (24h)"
            )
            return 86400
        return int(seconds)

    def native_relevant_items(self):
        """Items native-mode aggregation must consider - mirrors
        remove_older_than_maxage()'s own worklist-fill precedent exactly
        (all handled items if default_maxage is set instance-wide,
        otherwise only items with their own database_maxage)."""
        plugin = self._plugin
        return list(plugin._handled_items) if plugin._default_maxage > 0 else list(plugin._items_with_maxage)
