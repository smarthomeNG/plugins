#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Shared test helpers and mock objects for stateengine tests.

Usage
-----
Import at the top of each test module *before* importing any stateengine code:

    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    import tests.common as common
    common.register_shng_log_levels()
    from plugins.stateengine.tests.mock_helper import (
        make_sh, MockAbItem, MockSePlugin, MockItem,
    )
"""

import logging
import os
import sys
import datetime
import threading
from queue import Queue

# ---------------------------------------------------------------------------
# Bootstrap: add shng base to path so imports work from plugin test dirs
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(__file__)
_SHNG_BASE = os.path.abspath(os.path.join(_HERE, '..', '..', '..'))
if _SHNG_BASE not in sys.path:
    sys.path.insert(0, _SHNG_BASE)

from tests.mock.core import MockSmartHome
import lib.item.item
import lib.item.items
from lib.item.items import Items
from lib.shtime import Shtime


# ---------------------------------------------------------------------------
# Reset helpers
# ---------------------------------------------------------------------------


def reset_items():
    """Clear all item singletons so each test starts clean."""
    lib.item.items._items_instance = None
    lib.item.item._items_instance = None
    Items._Items__items = []
    Items._Items__item_dict = {}
    Items._children = []
    Items.plugin_attributes = {}
    Items.plugin_attribute_prefixes = {}
    Items.plugin_prefixes_tuple = None


def make_sh():
    """Return a fresh MockSmartHome with clean item state."""
    reset_items()
    return MockSmartHome()


# ---------------------------------------------------------------------------
# Mock items
# ---------------------------------------------------------------------------


class MockItem:
    """Minimal stand-in for a shng Item, usable in stateengine tests."""

    def __init__(self, path, value=False):
        self._path = path
        self._value = value
        self.conf = {}
        self.property = _MockItemProperty(path)

    # make it callable like a real Item
    def __call__(self, *args, **kwargs):
        if args:
            self._value = args[0]
        return self._value

    def __repr__(self):
        return f'MockItem({self._path!r}={self._value!r})'


class _MockItemProperty:
    def __init__(self, path):
        self.path = path
        self.last_update_by = ''
        self.last_change_by = ''
        self.last_trigger_by = ''
        self.value = None


# ---------------------------------------------------------------------------
# Mock stateengine plugin
# ---------------------------------------------------------------------------


class MockSePlugin:
    """Minimal stand-in for the StateEngine SmartPlugin."""

    def __init__(self):
        self._scheduled = {}

    def scheduler_add(self, name, callback, cron=None, cycle=None, value=None, offset=None, next=None, **kwargs):
        self._scheduled[name] = {'callback': callback, 'value': value, 'next': next}

    def scheduler_remove(self, name):
        self._scheduled.pop(name, None)

    def scheduler_remove_all(self):
        self._scheduled.clear()

    def scheduler_get(self, name):
        return self._scheduled.get(name)

    def scheduler_change(self, name, **kwargs):
        if name in self._scheduled:
            self._scheduled[name].update(kwargs)

    def scheduler_trigger(self, name, **kwargs):
        pass

    def scheduler_return_next(self, name):
        entry = self._scheduled.get(name)
        return entry['next'] if entry else None

    def get_fullname(self):
        return 'StateEngine Plugin'

    def get_shortname(self):
        return 'stateengine'


# ---------------------------------------------------------------------------
# Mock SeLogger (dummy that captures calls)
# ---------------------------------------------------------------------------


class MockSeLogger:
    """Captures stateengine log calls so tests can assert on them."""

    def __init__(self):
        self.records = []
        # attributes accessed by stateengine internals
        self.log_level_as_num = 0
        self.default_log_level = _ConstValue(0)
        self.startup_log_level = _ConstValue(0)
        self.log_directory = ''

    def _record(self, level, text, args):
        try:
            msg = text.format(*args) if args else text
        except Exception:
            msg = text
        self.records.append((level, msg))

    def header(self, text):
        self._record('header', text, ())

    def info(self, text, *args):
        self._record('info', text, args)

    def debug(self, text, *args):
        self._record('debug', text, args)

    def warning(self, text, *args):
        self._record('warning', text, args)

    def error(self, text, *args):
        self._record('error', text, args)

    def develop(self, text, *args):
        self._record('develop', text, args)

    def dbghigh(self, text, *args):
        self._record('dbghigh', text, args)

    def increase_indent(self, by=1):
        pass

    def decrease_indent(self, by=1):
        pass

    def manage_logdirectory(self, *args, **kwargs):
        pass

    def update_logfile(self):
        pass

    def has_level(self, level):
        return False


class _ConstValue:
    """Return a constant from .get()."""

    def __init__(self, v):
        self._v = v

    def get(self):
        return self._v


# ---------------------------------------------------------------------------
# Mock AbItem (the SeItem proxy that SeItemChild / SeCondition / SeValue /
# SeAction all receive as their first constructor argument)
# ---------------------------------------------------------------------------


class MockAbItem:
    """
    Minimal stand-in for SeItem to satisfy SeItemChild.__init__.

    Fields accessed by SeItemChild:
        abitem.sh         → the SmartHomeNG instance
        abitem.shtime     → Shtime instance
        abitem.se_plugin  → the StateEngine plugin (SmartPlugin)
        abitem.logger     → SeLogger-like object
    """

    def __init__(self, sh=None):
        if sh is None:
            sh = make_sh()
        self._sh = sh
        self._shtime = Shtime.get_instance()
        self._se_plugin = MockSePlugin()
        self._logger = MockSeLogger()
        # variables dict used by SeItem.set_variable / .get_variable
        self._variables = {}
        # cache used by SeValue.__get_eval (dict with update() setter semantics)
        self._cache = {}
        # templates used by SeValue.set()
        self._templates = {}
        # queue used by SeActionBase.__init__
        self._queue = Queue()
        # last_run used by SeActionBase.eval_minagedelta
        self._last_run = {}
        # webif_infos stub (SeAction calls update_webif in some paths)
        self._webif_infos = {}
        # update_lock used by SeActionBase._delayed_execute
        self.update_lock = threading.Lock()

    # ── properties matching SeItem interface ──────────────────────────────

    @property
    def sh(self):
        return self._sh

    @property
    def shtime(self):
        return self._shtime

    @property
    def se_plugin(self):
        return self._se_plugin

    @property
    def logger(self):
        return self._logger

    @property
    def id(self):
        return 'mock.abitem'

    @property
    def path(self):
        return 'mock.abitem'

    def set_variable(self, key, value):
        self._variables[key] = value

    def get_variable(self, key):
        return self._variables.get(key)

    # cache property: SeValue writes via "self._abitem.cache = {key: val}" which
    # triggers the setter, expected to call dict.update().
    @property
    def cache(self):
        return self._cache

    @cache.setter
    def cache(self, value):
        self._cache.update(value)

    @property
    def templates(self):
        return self._templates

    @property
    def queue(self):
        return self._queue

    @property
    def last_run(self):
        return self._last_run

    @last_run.setter
    def last_run(self, value):
        self._last_run.update(value)

    # webif_infos property used by update_webif_actionstatus
    @property
    def webif_infos(self):
        return self._webif_infos

    def update_webif(self, key, value, flag=False):
        pass

    def run_queue(self):
        """No-op — used by _delayed_execute after enqueueing."""
        pass

    def return_item(self, path):
        """Look up item in MockSmartHome; return (item, issue) like SeItem does."""
        item = self._sh.items.return_item(path)
        if item is None:
            return None, "Item '{}' not found".format(path)
        return item, None

    def update_attributes(self, unused, used):
        """Called by SeConditionSet.complete() on error — no-op."""
        pass

    def update_issues(self, category, issues):
        """Called by SeConditionSet.complete() on error — no-op."""
        pass

    def updatetemplates(self, key, value):
        if value is None:
            self._templates.pop(key, None)
        else:
            self._templates[key] = value

    def get_age(self):
        return 0

    def get_condition_age(self):
        return 0

    # scheduler tracking methods added by PR #1041
    def add_scheduler_entry(self, name):
        pass

    def remove_scheduler_entry(self, name):
        pass

    # condition-set tracking (SeConditionSet calls this after all conditions match)
    def lastconditionset_set(self, conditionset_id, conditionset_name):
        self._variables['lastconditionset_id'] = conditionset_id
        self._variables['lastconditionset_name'] = conditionset_name
