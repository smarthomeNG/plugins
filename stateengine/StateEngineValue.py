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
        elif value_type == "list":
            self.__cast_func = StateEngineTools.cast_list
        else:
            self.__cast_func = None

    def __repr__(self):
        return "SeValue item: {}, function {}, value {}.".format(self._abitem, self.__name, self.get())

    # Indicate of object is empty (neither value nor item nor eval set)
    def is_empty(self):
        return self.__value is None and self.__item is None and self.__eval is None and self.__varname is None

    # Set value directly from attribute
    # item: item containing the attribute
    # attribute_name: name of attribute to use
    # default_value: default value to be used if item contains no such attribute
    def set_from_attr(self, item, attribute_name, default_value=None):
        value = item.conf[attribute_name] if attribute_name in item.conf else default_value
        self.set(value)

    # Set value
    # value: string indicating value or source of value
    # name: name of object ("time" is being handeled different)
    def set(self, value, name=""):
        if isinstance(value, list):
            source = []
            field_value = []
            for i, val in enumerate(value):
                if isinstance(val, dict) or isinstance(val, tuple):
                    val = list("{!s}:{!s}".format(k, v) for (k, v) in val.items())[0]
                if isinstance(val, str):
                    s, f = StateEngineTools.partition_strip(val, ":")
                else:
                    s = "value"
                    f = val
                source.append(s)
                field_value.append(f)
                if field_value[i] == "":
                    source[i] = "value"
                    field_value[i] = value[i]
                else:
                    value[i] = field_value[i]
                    field_value[i] = value[i]
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

        if isinstance(source, list):
            for i, s in enumerate(source):
                if isinstance(field_value[i], list) and not self.__allow_value_list:
                    raise ValueError("{0}: value_in is not allowed. Field_value: {1} ({2})".format(self.__name, field_value[i], self.__allow_value_list))
                else:
                    self.__value = [] if self.__value is None else self.__value
                    self.__value.append(None if s != "value" else self.__do_cast(field_value[i]))
                self.__item = [] if self.__item is None else self.__item
                self.__item.append(None if s != "item" else self._abitem.return_item(field_value[i]))
                self.__eval = [] if self.__eval is None else self.__eval
                self.__eval.append(None if s != "eval" else field_value[i])
                self.__varname = [] if self.__varname is None else self.__varname
                self.__varname.append(None if s != "var" else field_value[i])
            self.__item = [i for i in self.__item if i]
            self.__eval = [i for i in self.__eval if i]
            self.__varname = [i for i in self.__varname if i]
            self.__value = [i for i in self.__value if i]
            self.__value = self.__value[0] if len(self.__value) == 1 else None if len(self.__value) == 0 else self.__value
            self.__item = self.__item[0] if len(self.__item) == 1 else None if len(self.__item) == 0 else self.__item
            self.__eval = self.__eval[0] if len(self.__eval) == 1 else None if len(self.__eval) == 0 else self.__eval
            self.__varname = self.__varname[0] if len(self.__varname) == 1 else None if len(self.__varname) == 0 else self.__varname
        else:
            self.__item = None if source != "item" else self._abitem.return_item(field_value)
            self.__eval = None if source != "eval" else field_value
            self.__varname = None if source != "var" else field_value
            if source == "value":
                if isinstance(field_value, list) and not self.__allow_value_list:
                    raise ValueError("{0}: value_in is not allowed".format(self.__name))
                self.__value = self.__do_cast(field_value)
            else:
                self.__value = None

    # Set cast function
    # cast_func: cast function
    def set_cast(self, cast_func):
        self.__cast_func = cast_func
        self.__value = self.__do_cast(self.__value)

    # determine and return value
    def get(self, default=None):
        returnvalues = []
        if self.__value is not None:
            returnvalues.append(self.__value)
        if self.__eval is not None:
            returnvalues.append(self.__get_eval())
        if self.__item is not None:
            returnvalues.append(self.__get_from_item())
        if self.__varname is not None:
            returnvalues.append(self.__get_from_variable())
        if len(returnvalues) == 0:
            return default
        elif len(returnvalues) == 1:
            return returnvalues[0]
        else:
            return returnvalues

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
        if self.__item is not None:
            if isinstance(self.__item, list):
                for i in self.__item:
                    self._log_debug("{0} from item: {1}", self.__name, i.property.path)
            else:
                self._log_debug("{0} from item: {1}", self.__name, self.__item.property.path)
        if self.__eval is not None:
            self._log_debug("{0} from eval: {1}", self.__name, self.__eval)
        if self.__varname is not None:
            self._log_debug("{0} from variable: {1}", self.__name, self.__varname)

    # Get Text (similar to logger text)
    # prefix: Prefix for text
    # suffix: Suffix for text
    def get_text(self, prefix=None, suffix=None):
        if self.__value is not None:
            value = "{0}: {1}".format(self.__name, self.__value, prefix, suffix)
        elif self.__item is not None:
            if isinstance(self.__item, list):
                for i in self.__item:
                    self._log_debug("{0} from item: {1}", self.__name, i.property.path)
            else:
                self._log_debug("{0} from item: {1}", self.__name, self.__item.property.path)
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
                if isinstance(value, list):
                    valuelist = []
                    for element in value:
                        valuelist.append(element if element == 'novalue' else self.__cast_func(element))
                    value = valuelist
                else:
                    value = self.__cast_func(value)
            except Exception as ex:
                if self.__cast_func == self.__cast_func.__globals__['_cast_list']:
                    try:
                        value = StateEngineTools.cast_num(value)
                    except Exception:
                        pass
                    value = [value]
                    return value
                self._log_info("Problem casting value '{0}' to {1}: {2}.", value, self.__cast_func, ex)
                return None
        return value

    # Determine value by executing eval-function
    def __get_eval(self):
        # noinspection PyUnusedLocal
        sh = self._sh
        if isinstance(self.__eval, str):
            if "stateengine_eval" in self.__eval or "se_eval" in self.__eval:
                # noinspection PyUnusedLocal
                stateengine_eval = se_eval = StateEngineEval.SeEval(self._abitem)
            try:
                values = eval(self.__eval)
            except Exception as ex:
                self._log_info("Problem evaluating '{0}': {1}.", StateEngineTools.get_eval_name(self.__eval), ex)
                return None
        else:
            if isinstance(self.__eval, list):
                values = []
                for val in self.__eval:
                    self._log_info("Checking eval: {0}.", val.replace("\n", ""))
                    self._log_increase_indent()
                    if isinstance(val, str):
                        if "stateengine_eval" in val or "se_eval" in val:
                            # noinspection PyUnusedLocal
                            stateengine_eval = se_eval = StateEngineEval.SeEval(self._abitem)
                        try:
                            value = eval(val)
                        except Exception as ex:
                            self._log_info("Problem evaluating from list '{0}': {1}.", StateEngineTools.get_eval_name(val), ex)
                            value = None
                    else:
                        try:
                            value = val()
                        except Exception as ex:
                            self._log_info("Problem calling '{0}': {1}.", StateEngineTools.get_eval_name(val), ex)
                            value = None
                    if value is not None:
                        values.append(self.__do_cast(value))
                    self._log_decrease_indent()
            else:
                try:
                    self._log_increase_indent()
                    values = self.__eval()
                    self._log_decrease_indent()
                except Exception as ex:
                    self._log_info("Problem calling '{0}': {1}.", StateEngineTools.get_eval_name(self.__eval), ex)
                    return None

        return self.__do_cast(values)

    # Determine value from item
    def __get_from_item(self):
        try:
            if isinstance(self.__item, list):
                values = []
                for val in self.__item:
                    self._log_info("Checking item '{0}': {1}.", self.__item, val)
                    value = val.property.value
                    values.append(self.__do_cast(value))
            else:
                values = self.__item.property.value
        except Exception as ex:
            self._log_info("Problem while reading item '{0}': {1}.", self.__item.property.path, ex)
            return None

        return self.__do_cast(values)

    # Determine value from variable
    def __get_from_variable(self):
        try:
            if isinstance(self.__varname, list):
                values = []
                for var in self.__varname:
                    self._log_info("Checking variable '{0}': {1}.", self.__varname, var)
                    value = self._abitem.get_variable(var)
                    values.append(self.__do_cast(value))
            else:
                values = self._abitem.get_variable(self.__varname)
        except Exception as ex:
            self._log_info("Problem while reading variable '{0}': {1}.", self.__varname, ex)
            return None

        return values
