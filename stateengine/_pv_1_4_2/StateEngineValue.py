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
from . import StateEngineTools
from . import StateEngineEval


# Class representing a value for a condition (either value or via item/eval)
class SeValue(StateEngineTools.SeItemChild):
    # Constructor
    # abitem: parent SeItem instance
    # name: Name of value
    # allow_value_list: Flag: list of values allowed
    # value_type: Type of value to preset the cast function (allowed: str, num, bool, time)
    def __init__(self, abitem, name, allow_value_list=False, value_type=None):
        super().__init__(abitem)
        self.__name = name
        self.__allow_value_list = allow_value_list
        self.__value = None
        self.__item = None
        self.__eval = None
        self.__varname = None

        if value_type == "str":
            self.__cast_func = StateEngineTools.cast_str
        elif value_type == "num":
            self.__cast_func = StateEngineTools.cast_num
        elif value_type == "bool":
            self.__cast_func = StateEngineTools.cast_bool
        elif value_type == "time":
            self.__cast_func = StateEngineTools.cast_time
        else:
            self.__cast_func = None

    # Indicate of object is empty (neither value nor item nor eval set)
    def is_empty(self):
        return self.__value is None and self.__item is None and self.__eval is None and self.__varname is None

    # Set value directly from attribute
    # item: item containing the attribute
    # attribute_name: name of attribute to use
    # value_type: type of value for casting (allowed: str, num ,bool, time)
    # default_value: default value to be used if item contains no such attribute
    def set_from_attr(self, item, attribute_name, default_value=None):
        value = item.conf[attribute_name] if attribute_name in item.conf else default_value
        self.set(value)

    # Set value
    # value: string indicating value or source of value
    # name: name of object ("time" is being handeled different)
    def set(self, value, name=""):
        if isinstance(value, list):
            source, field_value = StateEngineTools.partition_strip(value[0], ":")
            if field_value == "":
                source = "value"
                field_value = value
            else:
                value[0] = field_value
                field_value = value
        elif isinstance(value, str):
            source, field_value = StateEngineTools.partition_strip(value, ":")
            if name == "time" and source.isdigit() and field_value.isdigit():
                field_value = value
                source = "value"
            elif field_value == "":
                field_value = source
                source = "value"
        else:
            source = "value"
            field_value = value

        if source == "value":
            if isinstance(field_value, list) and not self.__allow_value_list:
                raise ValueError("{0}: value_in is not allowed".format(self.__name))
            self.__value = self.__do_cast(field_value)
        else:
            self.__value = None
        self.__item = None if source != "item" else self._abitem.return_item(field_value)
        self.__eval = None if source != "eval" else field_value
        self.__varname = None if source != "var" else field_value

    # Set cast function
    # cast_func: cast function
    def set_cast(self, cast_func):
        self.__cast_func = cast_func
        self.__value = self.__do_cast(self.__value)

    # determine and return value
    def get(self, default=None):
        if self.__value is not None:
            return self.__value
        elif self.__eval is not None:
            return self.__get_eval()
        elif self.__item is not None:
            return self.__get_from_item()
        elif self.__varname is not None:
            return self.__get_from_variable()
        else:
            return default

    def get_type(self):
        if self.__value is not None:
            return "value"
        elif self.__item is not None:
            return "item"
        elif self.__eval is not None:
            return "eval"
        elif self.__varname is not None:
            return "var"
        else:
            return None

    # Write condition to logger
    def write_to_logger(self):
        if self.__value is not None:
            self._log_debug("{0}: {1}", self.__name, self.__value)
        elif self.__item is not None:
            self._log_debug("{0} from item: {1}", self.__name, self.__item.id())
        elif self.__eval is not None:
            self._log_debug("{0} from eval: {1}", self.__name, self.__eval)
        elif self.__varname is not None:
            self._log_debug("{0} from variable: {1}", self.__name, self.__varname)

    # Get Text (similar to logger text)
    # prefix: Prefix for text
    # suffix: Suffix for text
    def get_text(self, prefix=None, suffix=None):
        if self.__value is not None:
            value = "{0}: {1}".format(self.__name, self.__value, prefix, suffix)
        elif self.__item is not None:
            value = "{0} from item: {1}".format(self.__name, self.__item.id())
        elif self.__eval is not None:
            value = "{0} from eval: {1}".format(self.__name, self.__eval)
        elif self.__varname is not None:
            value = "{0} from variable: {1}".format(self.__name, self.__varname)
        else:
            value = "{0}: (undefined)".format(self.__name)

        value = value if prefix is None else prefix + value
        value = value if suffix is None else value + suffix
        return value

    # Cast given value, if cast-function is set
    # value: value to cast
    def __do_cast(self, value):
        if value is not None and self.__cast_func is not None:
            try:
                if type(value) == list:
                    # noinspection PyCallingNonCallable
                    value = [self.__cast_func(element) for element in value]
                else:
                    # noinspection PyCallingNonCallable
                    value = self.__cast_func(value)
            except Exception as ex:
                self._log_info("Problem casting value '{0}': {1}.", value, str(ex))
                return None

        return value

    # Determine value by executing eval-function
    def __get_eval(self):
        if isinstance(self.__eval, str):
            # noinspection PyUnusedLocal
            sh = self._sh
            if "stateengine_eval" in self.__eval:
                # noinspection PyUnusedLocal
                stateengine_eval = StateEngineEval.SeEval(self._abitem)
            try:
                value = eval(self.__eval)
            except Exception as ex:
                self._log_info("Problem evaluating '{0}': {1}.", StateEngineTools.get_eval_name(self.__eval), str(ex))
                return None
        else:
            try:
                # noinspection PyCallingNonCallable
                value = self.__eval()
            except Exception as ex:
                self._log_info("Problem calling '{0}': {1}.", StateEngineTools.get_eval_name(self.__eval), str(ex))
                return None

        return self.__do_cast(value)

    # Determine value from item
    def __get_from_item(self):
        try:
            # noinspection PyCallingNonCallable
            value = self.__item()
        except Exception as ex:
            self._log_info("Problem while reading item '{0}': {1}.", self.__item.id(), str(ex))
            return None

        return self.__do_cast(value)

    # Fetermine value from variable
    def __get_from_variable(self):
        try:
            value = self._abitem.get_variable(self.__varname)
        except Exception as ex:
            self._log_info("Problem while reading variable '{0}': {1}.", self.__varname, str(ex))
            return None

        return self.__do_cast(value)
