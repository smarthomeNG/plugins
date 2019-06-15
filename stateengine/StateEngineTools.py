#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2014-     Thomas Ernst                       offline@gmx.net
#########################################################################
#  Finite state machine plugin for SmartHomeNG
#
#  This plugin is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This plugin is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this plugin. If not, see <http://www.gnu.org/licenses/>.
#########################################################################
import datetime
from ast import literal_eval
# import logging

#
# Some general tool functions
#
# logger = logging.getLogger(__name__)


# Find a certain item below a given item.
# item: Item to search below
# child_id: Id of child item to search (without prefixed id of "item")
# returns: child item if found, otherwise None
def get_child_item(item, child_id):
    search_id = item.property.path + "." + child_id
    for child in item.return_children():
        if child.property.path == search_id:
            return child
    return None


# Returns the last part of the id of an item (everythig behind last .)
# item: Item for which the last part of the id should be returned
# returns: last part of item id
def get_last_part_of_item_id(item):
    return item.property.path.rsplit(".", 1)[1]


# Flatten list of values
# changelist: list to make flat
def flatten_list(changelist):
    if isinstance(changelist, list):
        flat_list = []
        for sublist in changelist:
            if isinstance(sublist, list):
                for item in sublist:
                    flat_list.append(item)
            else:
                flat_list.append(sublist)
    else:
        flat_list = changelist
    return flat_list


# cast a value as numeric. Throws ValueError if cast not possible
# Taken from smarthome.py/lib/item.py
# value: value to cast
# returns: value as num or float
# noinspection PyBroadException
def cast_num(value):
    if isinstance(value, float):
        return value
    try:
        return int(value)
    except Exception:
        pass
    try:
        return float(value)
    except Exception:
        pass
    try:
        return literal_eval(value)
    except Exception:
        pass
    raise ValueError("Can't cast {0} to int!".format(value))


# cast a value as boolean. Throws ValueError or TypeError if cast is not possible
# Taken from smarthome.py/lib/item.py
# value: value to cast
# returs: value as boolean
def cast_bool(value):
    if type(value) in [bool, int, float]:
        if value in [False, 0]:
            return False
        elif value in [True, 1]:
            return True
        else:
            raise ValueError("Can't cast {0} to bool!".format(value))
    elif type(value) in [str, str]:
        if value.lower() in ['0', 'false', 'no', 'off']:
            return False
        elif value.lower() in ['1', 'true', 'yes', 'on']:
            return True
        else:
            raise ValueError("Can't cast {0} to bool!".format(value))
    else:
        raise ValueError("Can't cast {0} to bool!".format(value))


# cast a value as string. Throws ValueError if cast is not possible
# Taken from smarthome.py/lib/item.py
# value: value to cast
# returns: value as string
def cast_str(value):
    if isinstance(value, str):
        return value
    else:
        raise ValueError("Can't cast {0} to str!".format(value))


# cast a value as list. Throws ValueError if cast is not possible
# Taken from smarthome.py/lib/item.py
# value: value to cast
# returns: value as string
def cast_list(value):
    if isinstance(value, str):
        try:
            value = literal_eval(value)
        except Exception:
            pass
    if isinstance(value, list):
        return value
    else:
        value = [value]
        return value


# cast value as datetime.time. Throws ValueError if cast is not possible
# value: value to cast
# returns: value as datetime.time
def cast_time(value):
    if isinstance(value, datetime.time):
        return value

    orig_value = value
    value = value.replace(",", ":")
    value_parts = value.split(":")
    if len(value_parts) != 2:
        raise ValueError("Can not cast '{0}' to data type 'time' due to incorrect format!".format(orig_value))
    else:
        try:
            hour = int(value_parts[0])
            minute = int(value_parts[1])
        except ValueError:
            raise ValueError("Can not cast '{0}' to data type 'time' due to non-numeric parts!".format(orig_value))
        if hour > 24 or minute > 59:
            raise ValueError("Can not cast '{0}' to data type 'time'. Hour or minute values too high!".format(orig_value))
        elif hour == 24 and minute >= 0:
            return datetime.time(23, 59, 59)
        else:
            return datetime.time(hour, minute)


# find a certain attribute for a generic condition. If an "use"-attribute is found, the "use"-item is searched
# recursively
# smarthome: instance of smarthome.py base class
# base_item: base item to search in
# attribute: name of attribute to find
def find_attribute(smarthome, base_item, attribute, recursion_depth=0):
    # 1: parent of given item could have attribute
    parent_item = base_item.return_parent()
    if parent_item is not None and attribute in parent_item.conf:
        return parent_item.conf[attribute]

    # 2: if item has attribute "se_use", get the item to use and search this item for required attribute
    if "se_use" in base_item.conf:
        if recursion_depth > 5:
            return None
        use_item = smarthome.return_item(base_item.conf["se_use"])
        if use_item is not None:
            result = find_attribute(smarthome, use_item, attribute, recursion_depth + 1)
            if result is not None:
                return result

    # 3: nothing found
    return None


# partition value at splitchar and strip resulting parts
# value: what to split
# splitchar: where to split
# returns: Parts before and after split, whitespaces stripped
def partition_strip(value, splitchar):
    if isinstance(value, list):
        raise ValueError("You can not use list entries!")
    elif value.startswith("se_") and splitchar == "_":
        part1, __, part2 = value[3:].partition(splitchar)
        return "se_" + part1.strip(), part2.strip()
    else:
        part1, __, part2 = value.partition(splitchar)
        return part1.strip(), part2.strip()


# return string representation of eval function
# eval_func: eval function
# returns: string representation
def get_eval_name(eval_func):
    if eval_func is None:
        return None
    if eval_func is not None:
        if isinstance(eval_func, list):
            functionnames = []
            for func in eval_func:
                if isinstance(func, str):
                    functionnames.append(func)
                else:
                    functionnames.append(func.__module__ + "." + func.__name__)
            return functionnames
        else:
            if isinstance(eval_func, str):
                return eval_func
            else:
                return eval_func.__module__ + "." + eval_func.__name__


# determine original caller/source
# smarthome: instance of smarthome.py
# caller: caller
# source: source
def get_original_caller(smarthome, caller, source, item=None):
    original_caller = caller
    original_source = source
    original_item = item
    while original_caller == "Eval":
        original_item = smarthome.return_item(original_source)
        if original_item is None:
            break
        original_changed_by = original_item.changed_by()
        if ":" not in original_changed_by:
            break
        original_caller, __, original_source = original_changed_by.partition(":")
    if item is None:
        return original_caller, original_source
    else:
        return original_caller, original_source, original_item


# General class for everything that is below the SeItem Class
# This class provides some general stuff:
# - Protected wrapper-methods for logging
# - abitem and smarthome Instances
class SeItemChild:
    # Constructor
    # abitem: parent SeItem instance
    def __init__(self, abitem):
        self._abitem = abitem
        self._sh = abitem.sh

    # wrapper method for logger.info
    def _log_info(self, text, *args):
        self._abitem.logger.info(text, *args)

    # wrapper method for logger.debug
    def _log_debug(self, text, *args):
        self._abitem.logger.debug(text, *args)

    # wrapper method for logger.warning
    def _log_warning(self, text, *args):
        self._abitem.logger.warning(text, *args)

    # wrapper method for logger.error
    def _log_error(self, text, *args):
        self._abitem.logger.error(text, *args)

    # wrapper method for logger.exception
    def _log_exception(self, msg, *args, **kwargs):
        self._abitem.logger.exception(msg, *args, **kwargs)

    # wrapper method for logger.increase_indent
    def _log_increase_indent(self, by=1):
        self._abitem.logger.increase_indent(by)

    # wrapper method for logger.decrease_indent
    def _log_decrease_indent(self, by=1):
        self._abitem.logger.decrease_indent(by)
