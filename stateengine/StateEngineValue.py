#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2014-2018 Thomas Ernst                       offline@gmx.net
#  Copyright 2019- Onkel Andy                       onkelandy@hotmail.com
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
from . import StateEngineStruct
from . import StateEngineStructs
from lib.item import Items
from lib.item.item import Item
import re
import ast
import collections.abc
import copy


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
        self.__regex = None
        self.__struct = None
        self.__varname = None
        self.__template = None
        self._additional_sources = []
        self.itemsApi = Items.get_instance()
        self.__itemClass = Item
        self.__listorder = []
        self.__type_listorder = []
        self.__valid_valuetypes = ["value", "regex", "eval", "var", "item", "template", "struct"]
        if value_type == "str":
            self.__cast_func = StateEngineTools.cast_str
        elif value_type == "num":
            self.__cast_func = StateEngineTools.cast_num
        elif value_type == "item":
            self.__cast_func = self.cast_item
        elif value_type == "bool":
            self.__cast_func = StateEngineTools.cast_bool
        elif value_type == "time":
            self.__cast_func = StateEngineTools.cast_time
        elif value_type == "list":
            self.__cast_func = StateEngineTools.cast_list
        else:
            self.__cast_func = None

    def __repr__(self):
        return "{}".format(self.get())

    # Indicate if object is empty (neither value nor item nor eval set)
    def is_empty(self):
        return self.__value is None and self.__item is None and self.__eval is None and \
               self.__varname is None and self.__regex is None and self.__struct is None

    # Set value directly from attribute
    # item: item containing the attribute
    # attribute_name: name of attribute to use
    # default_value: default value to be used if item contains no such attribute
    def set_from_attr(self, item, attribute_name, default_value=None, reset=True, attr_type=None):
        value = copy.deepcopy(item.conf.get(attribute_name)) or default_value
        if value is not None:
            self._log_develop("Processing value {0} from attribute name {1}, reset {2}", value, attribute_name, reset)
        value_list = []
        if value is not None and isinstance(value, list) and attr_type is not None:
            for i, entry in enumerate(value):
                if isinstance(attr_type, list):
                    value_list.append("{}:{}".format(attr_type[i], entry))
                else:
                    value_list.append("{}:{}".format(attr_type, entry))
            value = value_list
        # Convert weird string representation of OrderedDict correctly
        if isinstance(value, str) and value.startswith("["):
            value = re.split('(, (?![^(]*\)))', value.strip(']['))
            value = [s for s in value if s != ', ']
            result = []
            for s in value:
                m = re.match(r'^OrderedDict\((.+)\)$', s)
                if m:
                    result.append(dict(ast.literal_eval(m.group(1))))
                else:
                    result.append(ast.literal_eval(s))
            value = result
        try:
            value = ast.literal_eval(value)
        except Exception as ex:
            pass
        if value is not None:
            self._log_develop("Setting value {0}, attribute name {1}, reset {2}", value, attribute_name, reset)
        _returnvalue, _returntype = self.set(value, attribute_name, reset, item)
        return _returnvalue, _returntype

    def _set_additional(self, _additional_sources):
        for _use in _additional_sources:
            self._additional_sources.remove(_use)
            _, _struct_name = StateEngineTools.partition_strip(_use, ":")
            StateEngineStructs.create(self._abitem, _struct_name)

    def __resetvalue(self):
        self.__value = None
        self.__item = None
        self.__eval = None
        self.__regex = None
        self.__struct = None
        self.__varname = None
        self.__template = None
        self._additional_sources = []
        self.__listorder = []
        self.__type_listorder = []

    # Set value
    # value: string indicating value or source of value
    # name: name of object ("time" is being handled differently)
    def set(self, value, name="", reset=True, item=None):
        if reset:
            self.__resetvalue()
        if isinstance(value, list):
            source = []
            field_value = []
            for i, val in enumerate(value):
                if isinstance(val, collections.abc.Mapping):
                    val = list("{!s}:{!s}".format(k, v) for (k, v) in val.items())[0]
                if isinstance(val, tuple):
                    val = ':'.join(val)
                if isinstance(val, str):
                    s, f = StateEngineTools.partition_strip(val, ":")
                else:
                    s = "value"
                    f = val
                source.append(s)
                field_value.append(f)
                self.__listorder.append("{}:{}".format(s, f))
                if field_value[i] == "":
                    source[i] = "value"
                    field_value[i] = value[i]
                else:
                    value[i] = field_value[i]
                    field_value[i] = value[i]
                if source[i] not in self.__valid_valuetypes:
                    self._log_warning("{0} is not a valid value type. Use one of {1} instead. Value '{2}' "
                                      "will be handled the same as the item type, e.g. string, bool, etc.",
                                      source[i], self.__valid_valuetypes, field_value[i])
                    source[i] = "value"
                self.__type_listorder.append(source[i])
                if source[i] == "value":
                    self.__listorder[i] = value[i]
                if source[i] == "template":
                    if self.__template is None:
                        self.__template = []
                    self.__template.append(field_value[i])
                    _template = self._abitem.templates.get(field_value[i])
                    if _template is not None:
                        try:
                            source[i], field_value[i] = StateEngineTools.partition_strip(_template, ":")
                            if val in self.__listorder and field_value[i] in self._abitem.templates:
                                self.__listorder[self.__listorder.index(val)] = self._abitem.templates.get(field_value[i])
                        except Exception as ex:
                            self._abitem.updatetemplates(field_value[i], None)
                            self.__listorder = [i for i in self.__listorder if i != val]
                            self._log_warning("Removing template {}: {}", field_value[i], ex)
                            val, field_value[i], source[i] = None, None, None
                    else:
                        self._log_warning("Template with name '{}' does not exist for this SE Item!", field_value[i])
                        self.__listorder = [i for i in self.__listorder if i != val]
                        source[i], field_value[i], val = None, None, None
            try:
                if isinstance(self.__template, list) and len(self.__template) == 1:
                    self.__template = self.__template[0]
            except Exception:
                pass

        elif isinstance(value, str):
            source, field_value = StateEngineTools.partition_strip(value, ":")
            self.__listorder.append("{}{}{}".format(source, ":" if field_value else "", field_value))
            if source == "template":
                self.__template = field_value
                _template = self._abitem.templates.get(self.__template)
                if _template is not None:
                    try:
                        source, field_value = StateEngineTools.partition_strip(_template, ":")
                        if value in self.__listorder and field_value in self._abitem.templates:
                            self.__listorder[self.__listorder.index(value)] = self._abitem.templates[self.__template]
                    except Exception as ex:
                        self.__listorder = [i for i in self.__listorder if i != value]
                        source, field_value, value = None, None, None
                        self._abitem.updatetemplates(self.__template, None)
                        self._log_warning("Removing template {}: {}", self.__template, ex)
                else:
                    self._log_warning("Template with name '{}' does not exist for this SE Item!", self.__template)
                    self.__listorder = [i for i in self.__listorder if i != value]
                    source, field_value, value = None, None, None
            try:
                cond1 = source.isdigit()
                cond2 = field_value.isdigit()
            except Exception:
                cond1 = False
                cond2 = False
            if name == "time" and cond1 and cond2:
                field_value = value
                source = "value"
            elif field_value == "":
                field_value = source
                source = "value"
            if source not in self.__valid_valuetypes:
                self._log_warning("{0} is not a valid value type. Use one of {1} instead. Value '{2}' "
                                  "will be handled the same as the item type, e.g. string, bool, etc.",
                                  source, self.__valid_valuetypes, field_value)
                source = "value"
            if source == "value":
                self.__listorder = [field_value]
            self.__type_listorder.append(source)
        else:
            source = "value"
            field_value = value

        if isinstance(source, list):
            for i, s in enumerate(source):
                if isinstance(field_value[i], list) and not self.__allow_value_list:
                    raise ValueError("{0}: value_in is not allowed. Field_value: {1} ({2})".format(
                        self.__name, field_value[i], self.__allow_value_list))
                else:
                    if s == "template":
                        if isinstance(self.__template, list):
                            for t in self.__template:
                                _template = self._abitem.templates.get(t)
                                if _template is not None:
                                    self._log_debug("Template {} exchanged with {}", self.__template,
                                                    self._abitem.templates[field_value[i]])
                                    s, field_value[i] = StateEngineTools.partition_strip(
                                        self._abitem.templates[field_value[i]], ":")
                                else:
                                    self._log_warning("Template with name '{}' does not exist for this SE Item!",
                                                      self.__template)
                                    s = None
                    try:
                        cond1 = s.isdigit()
                        cond2 = field_value[i].isdigit()
                    except Exception:
                        cond1 = False
                        cond2 = False
                    if name == "time" and cond1 and cond2:
                        field_value[i] = '{}:{}'.format(source[i], field_value[i])
                        s = "value"
                    elif field_value[i] == "":
                        field_value[i] = s
                        s = "value"
                    self.__value = [] if self.__value is None else [self.__value] if not isinstance(self.__value, list) else self.__value
                    self.__value.append(None if s != "value" else self.__do_cast(field_value[i]))
                self.__item = [] if self.__item is None else [self.__item] if not isinstance(self.__item, list) else self.__item
                self.__item.append(None if s != "item" else self.__absolute_item(self._abitem.return_item(field_value[i]), field_value[i]))
                self.__eval = [] if self.__eval is None else [self.__eval] if not isinstance(self.__eval, list) else self.__eval
                self.__eval.append(None if s != "eval" else field_value[i])
                self.__regex = [] if self.__regex is None else [self.__regex] if not isinstance(self.__regex, list) else self.__regex
                self.__regex.append(None if s != "regex" else field_value[i])
                self.__struct = [] if self.__struct is None else [self.__struct] if not isinstance(self.__struct, list) else self.__struct
                self.__struct.append(None if s != "struct" else StateEngineStructs.create(self._abitem, field_value[i]))
                self.__varname = [] if self.__varname is None else [self.__varname] if not isinstance(self.__varname, list) else self.__varname
                self.__varname.append(None if s != "var" else field_value[i])
            self.__item = [i for i in self.__item if i is not None]
            self.__eval = [i for i in self.__eval if i is not None]
            self.__regex = [i for i in self.__regex if i is not None]
            self.__struct = [i for i in self.__struct if i is not None]
            self.__varname = [i for i in self.__varname if i is not None]
            self.__value = [i for i in self.__value if i is not None]
            self.__value = self.__value[0] if len(self.__value) == 1 else None if len(self.__value) == 0 else self.__value
            self.__item = self.__item[0] if len(self.__item) == 1 else None if len(self.__item) == 0 else self.__item
            self.__eval = self.__eval[0] if len(self.__eval) == 1 else None if len(self.__eval) == 0 else self.__eval
            self.__regex = self.__regex[0] if len(self.__regex) == 1 else None if len(self.__regex) == 0 else self.__regex
            self.__struct = None if len(self.__struct) == 0 else self.__struct
            self.__varname = self.__varname[0] if len(self.__varname) == 1 else None if len(self.__varname) == 0 else self.__varname

        else:
            self.__item = None if source != "item" else self.__absolute_item(self._abitem.return_item(field_value), field_value)
            self.__eval = None if source != "eval" else field_value
            self.__regex = None if source != "regex" else field_value
            self.__struct = None if source != "struct" else StateEngineStructs.create(self._abitem, field_value)
            self.__varname = None if source != "var" else field_value
            if source == "value":
                if isinstance(field_value, list) and not self.__allow_value_list:
                    raise ValueError("{0}: value_in is not allowed, problem with {1}. Allowed = {2}".format(
                                     self.__name, field_value, self.__allow_value_list))
                self.__value = self.__do_cast(field_value)
            else:
                self.__value = None
        self.__listorder = StateEngineTools.flatten_list(self.__listorder)
        self.__type_listorder = StateEngineTools.flatten_list(self.__type_listorder)
        return self.__listorder, self.__type_listorder

    # Set cast function
    # cast_func: cast function
    def set_cast(self, cast_func):
        self.__cast_func = cast_func
        self.__value = self.__do_cast(self.__value)

    # determine and return value
    def get(self, default=None, originalorder=True):
        returnvalues = []
        try:
            _original_listorder = copy.copy(self.__listorder)
        except Exception as ex:
            self._log_error("Can not read listorder. Error: {}", ex)
            originalorder = False
        if self.__value is not None:
            returnvalues.append(self.__value)
        if self.__eval is not None:
            returnvalues.append(self.__get_eval())
        if self.__regex is not None:
            returnvalues.append(self.__get_from_regex())
        if self.__struct is not None:
            returnvalues.append(self.__get_from_struct())
        if self.__item is not None:
            returnvalues.append(self.__get_from_item())
        if self.__varname is not None:
            returnvalues.append(self.__get_from_variable())

        returnvalues = StateEngineTools.flatten_list(returnvalues)
        returnvalues = returnvalues if len(self.__listorder) <= 1 or originalorder is False \
            else StateEngineTools.flatten_list(self.__listorder)
        if originalorder:
            self.__listorder = _original_listorder
        if len(returnvalues) == 0:
            return default
        elif len(returnvalues) == 1:
            return returnvalues[0]
        else:
            return returnvalues

    def get_for_webif(self):
        returnvalues = self.get()
        returnvalues = self.__varname if returnvalues == '' else returnvalues
        return returnvalues

    def get_type(self):
        if len(self.__listorder) <= 1:
            if self.__value is not None:
                return "value"
            if self.__item is not None:
                return "item"
            if self.__eval is not None:
                return "eval"
            if self.__regex is not None:
                return "regex"
            if self.__struct is not None:
                return "struct"
            if self.__varname is not None:
                return "var"
        else:
            return self.__type_listorder

    # Write condition to logger
    def write_to_logger(self):
        if self.__template is not None:
            self._log_debug("{0}: Using template(s) {1}", self.__name, self.__template)
        if self.__value is not None:
            if isinstance(self.__value, list):
                for i in self.__value:
                    if i is not None:
                        self._log_debug("{0}: {1}", self.__name, i)
            else:
                self._log_debug("{0}: {1}", self.__name, self.__value)
        if self.__regex is not None:
            if isinstance(self.__regex, list):
                for i in self.__regex:
                    if i is not None:
                        self._log_debug("{0} from regex: {1}", self.__name, i)
            else:
                self._log_debug("{0} from regex: {1}", self.__name, self.__regex)
        if self.__struct is not None:
            if isinstance(self.__struct, list):
                for i in self.__struct:
                    if i is not None:
                        self._log_debug("{0} from struct: {1}", self.__name, i.property.path)
            else:
                self._log_debug("{0} from struct: {1}", self.__name, self.__struct.property.path)
        if self.__item is not None:
            if isinstance(self.__item, list):
                for i in self.__item:
                    if i is not None:
                        self._log_debug("{0} from item: {1}", self.__name, i.property.path)
            else:
                self._log_debug("{0} from item: {1}", self.__name, self.__item.property.path)
        if self.__eval is not None:
            self._log_debug("{0} from eval: {1}", self.__name, self.__eval)
            _original_listorder = copy.copy(self.__listorder)
            self._log_debug("Currently eval results in {}", self.__get_eval())
            self.__listorder = _original_listorder
        if self.__varname is not None:
            if isinstance(self.__varname, list):
                for i in self.__varname:
                    if i is not None:
                        self._log_debug("{0} from variable: {1}", self.__name, i)
            else:
                self._log_debug("{0} from item: {1}", self.__name, self.__varname)

    # Get Text (similar to logger text)
    # prefix: Prefix for text
    # suffix: Suffix for text
    def get_text(self, prefix=None, suffix=None):
        if self.__value is not None:
            value = "{0}: {1}. Prefix: {2}, Suffix: {3}".format(self.__name, self.__value, prefix, suffix)
        elif self.__regex is not None:
            value = "{0} from regex: {1}".format(self.__name, self.__regex)
        elif self.__struct is not None:
            value = "{0} from struct: {1}".format(self.__name, self.__struct)
        elif self.__item is not None:
            value = "{0} from item: {1}".format(self.__name, self.__item)
        elif self.__eval is not None:
            value = "{0} from eval: {1}".format(self.__name, self.__eval)
        elif self.__varname is not None:
            value = "{0} from variable: {1}".format(self.__name, self.__varname)
        else:
            value = "{0}: (undefined)".format(self.__name)

        value = value if prefix is None else prefix + value
        value = value if suffix is None else value + suffix
        return value

    # cast a value as item. Throws ValueError if cast is not possible
    # value: value to cast
    # returns: value as item or struct
    def cast_item(self, value):
        try:
            return self._abitem.return_item(value)
        except Exception as e:
            self._log_error("Can't cast {0} to item/struct! {1}".format(value, e))
            return value

    def __update_item_listorder(self, value, newvalue, id=None):
        if value is None:
            _id_value = "item:{}".format(id)
            self.__listorder[self.__listorder.index(_id_value)] = newvalue
        if value in self.__listorder:
            self.__listorder[self.__listorder.index(value)] = newvalue
        if isinstance(value, self.__itemClass):
            _item_value = "item:{}".format(value.property.path)
            if _item_value in self.__listorder:
                self.__listorder[self.__listorder.index(_item_value)] = newvalue
            if id:
                _item_value = "item:{}".format(id)
                if _item_value in self.__listorder:
                    self.__listorder[self.__listorder.index(_item_value)] = "item:{}".format(newvalue.property.path)
                    self._log_develop("Updated relative declaration {} with absolute item path {}. Listorder is now: {}",
                                      _item_value, newvalue.property.path, self.__listorder)

    def __absolute_item(self, value, id=None):
        if isinstance(value, list):
            valuelist = []
            idlist = [] if id is None else [id] if not isinstance(id, list) else id
            for i, element in enumerate(value):
                element = self.cast_item(element)
                self.__update_item_listorder(value, element, id[i])
            value = valuelist
        else:
            _newvalue = self.cast_item(value)
            self.__update_item_listorder(value, _newvalue, id)
            value = _newvalue
        return value

    # Cast given value, if cast-function is set
    # value: value to cast
    def __do_cast(self, value, id=None):
        if value is not None and self.__cast_func is not None:
            try:
                if isinstance(value, list):
                    valuelist = []
                    idlist = [] if id is None else [id] if not isinstance(id, list) else id
                    for i, element in enumerate(value):
                        try:
                            _newvalue = element if element == 'novalue' else self.__cast_func(element)
                        except Exception as ex:
                            _newvalue = None
                            self._log_warning("Problem casting element '{0}' to {1}: {2}.", element, self.__cast_func, ex)
                        valuelist.append(_newvalue)
                        if element in self.__listorder:
                            self.__listorder[self.__listorder.index(element)] = _newvalue
                        if isinstance(element, self.__itemClass):
                            self.__update_item_listorder(value, _newvalue, id[i])

                        if isinstance(element, StateEngineStruct.SeStruct):
                            _item_value = "struct:{}".format(element.property.path)
                            if _item_value in self.__listorder:
                                self.__listorder[self.__listorder.index(_item_value)] = _newvalue
                    value = valuelist
                else:
                    try:
                        _newvalue = self.__cast_func(value)
                        if value in self.__listorder:
                            self.__listorder[self.__listorder.index(value)] = _newvalue
                        if isinstance(value, self.__itemClass):
                            self.__update_item_listorder(value, _newvalue, id)

                        if isinstance(value, StateEngineStruct.SeStruct):
                            _item_value = "struct:{}".format(value.property.path)
                            if _item_value in self.__listorder:
                                self.__listorder[self.__listorder.index(_item_value)] = _newvalue
                    except Exception as ex:
                        if any(x in value for x in ['sh.', '_eval', '(']):
                            raise ValueError("You most likely forgot to prefix your expression with 'eval:'")
                        else:
                            raise ValueError("Not possible to cast: {}".format(ex))
                    if value in self.__listorder:
                        self.__listorder[self.__listorder.index(value)] = _newvalue
                    value = _newvalue
            except Exception as ex:
                self._log_warning("Problem casting '{0}' to {1}: {2}.", value, self.__cast_func, ex)
                if '_cast_list' in self.__cast_func.__globals__ and self.__cast_func == self.__cast_func.__globals__['_cast_list']:
                    try:
                        _newvalue = StateEngineTools.cast_num(value)
                        if value in self.__listorder:
                            self.__listorder[self.__listorder.index(value)] = _newvalue
                        value = _newvalue
                    except Exception:
                        pass
                    value = [value]
                    self._log_debug("Original casting of {} to {} failed. New cast is now: {}.",
                                    value, self.__cast_func, type(value))
                    return value
                return None
        return value

    # Determine value by using a struct
    def __get_from_struct(self):
        values = []
        if isinstance(self.__struct, list):
            for val in self.__struct:
                if val is not None:
                    _newvalue = self.__do_cast(val)
                    values.append(_newvalue)
                    if 'struct:{}'.format(val.property.path) in self.__listorder:
                        self.__listorder[self.__listorder.index('struct:{}'.format(val.property.path))] = _newvalue
        else:
            if self.__struct is not None:
                _newvalue = self.__do_cast(self.__struct)
                if 'struct:{}'.format(self.__regex) in self.__listorder:
                    self.__listorder[self.__listorder.index('struct:{}'.format(self.__struct))] = _newvalue
                values = _newvalue
        if values:
            return values

        try:
            _newvalue = self.__do_cast(self.__struct)
            if 'struct:{}'.format(self.__struct) in self.__listorder:
                self.__listorder[self.__listorder.index('struct:{}'.format(self.__struct))] = _newvalue
            values = _newvalue
        except Exception as ex2:
            values = self.__struct
            self._log_info("Problem while getting from struct '{0}': {1}.", values, ex2)

        return values

    # Determine value by regular expression
    def __get_from_regex(self):
        if isinstance(self.__regex, list):
            values = []
            for val in self.__regex:
                _newvalue = re.compile(val, re.IGNORECASE)
                values.append(_newvalue)
                if 'regex:{}'.format(val) in self.__listorder:
                    self.__listorder[self.__listorder.index('regex:{}'.format(val))] = _newvalue
        else:
            _newvalue = re.compile(self.__regex, re.IGNORECASE)
            if 'regex:{}'.format(self.__regex) in self.__listorder:
                self.__listorder[self.__listorder.index('regex:{}'.format(self.__regex))] = _newvalue
            values = _newvalue
        if values is not None:
            return values

        try:
            _newvalue = re.compile(self.__regex, re.IGNORECASE)
            if 'regex:{}'.format(self.__regex) in self.__listorder:
                self.__listorder[self.__listorder.index('regex:{}'.format(self.__regex))] = _newvalue
            values = _newvalue
        except Exception as ex2:
            values = self.__regex
            self._log_info("Problem while creating regex '{0}': {1}.", values, ex2)
        return values

    # Determine value by executing eval-function
    def __get_eval(self):
        # noinspection PyUnusedLocal
        sh = self._sh
        shtime = self._shtime
        if isinstance(self.__eval, str):
            self.__eval = StateEngineTools.parse_relative(self.__eval, 'sh.', ['()', '.property.'])
            if "stateengine_eval" in self.__eval or "se_eval" in self.__eval:
                # noinspection PyUnusedLocal
                stateengine_eval = se_eval = StateEngineEval.SeEval(self._abitem)
            self._log_debug("Checking eval: {0} from list {1}", self.__eval, self.__listorder)
            self._log_increase_indent()
            try:
                _newvalue = self.__do_cast(eval(self.__eval))
                if 'eval:{}'.format(self.__eval) in self.__listorder:
                    self.__listorder[self.__listorder.index('eval:{}'.format(self.__eval))] = _newvalue
                values = _newvalue
                self._log_decrease_indent()
                self._log_debug("Eval result: {0}.", values)
                self._log_increase_indent()
            except Exception as ex:
                self._log_decrease_indent()
                self._log_warning("Problem evaluating '{0}': {1}.", StateEngineTools.get_eval_name(self.__eval), ex)
                self._log_increase_indent()
                values = None
            finally:
                self._log_decrease_indent()
        else:
            if isinstance(self.__eval, list):
                values = []
                for val in self.__eval:
                    try:
                        val = val.replace("\n", "")
                    except Exception:
                        pass
                    self._log_debug("Checking eval from list: {0}.", val)
                    self._log_increase_indent()
                    if isinstance(val, str):
                        if "stateengine_eval" in val or "se_eval" in val:
                            # noinspection PyUnusedLocal
                            stateengine_eval = se_eval = StateEngineEval.SeEval(self._abitem)
                        try:
                            _newvalue = self.__do_cast(eval(val))
                            if 'eval:{}'.format(val) in self.__listorder:
                                self.__listorder[self.__listorder.index('eval:{}'.format(val))] = _newvalue
                            value = _newvalue
                            self._log_decrease_indent()
                            self._log_debug("Eval result from list: {0}.", value)
                            self._log_increase_indent()
                        except Exception as ex:
                            self._log_decrease_indent()
                            self._log_warning("Problem evaluating from list '{0}': {1}.",
                                              StateEngineTools.get_eval_name(val), ex)
                            self._log_increase_indent()
                            value = None
                    else:
                        try:
                            _newvalue = self.__do_cast(val())
                            if 'eval:{}'.format(val) in self.__listorder:
                                self.__listorder[self.__listorder.index('eval:{}'.format(val))] = _newvalue
                            value = _newvalue
                        except Exception as ex:
                            self._log_decrease_indent()
                            self._log_info("Problem evaluating '{0}': {1}.", StateEngineTools.get_eval_name(val), ex)
                            value = None
                    if value is not None:
                        values.append(self.__do_cast(value))
                    self._log_decrease_indent()
            else:
                self._log_debug("Checking eval (no str, no list): {0}.", self.__eval)
                try:
                    self._log_increase_indent()
                    _newvalue = self.__do_cast(self.__eval())
                    if 'eval:{}'.format(self.__eval) in self.__listorder:
                        self.__listorder[self.__listorder.index('eval:{}'.format(self.__eval))] = _newvalue
                    values = _newvalue
                    self._log_decrease_indent()
                    self._log_debug("Eval result (no str, no list): {0}.", values)
                    self._log_increase_indent()
                except Exception as ex:
                    self._log_decrease_indent()
                    self._log_warning("Problem evaluating '{0}': {1}.", StateEngineTools.get_eval_name(self.__eval), ex)
                    self._log_increase_indent()
                    return None

        return values

    # Determine value from item
    def __get_from_item(self):
        if isinstance(self.__item, list):
            values = []
            for val in self.__item:
                if val is None:
                    _newvalue = None
                else:
                    _newvalue = self.__do_cast(val.property.value)
                values.append(_newvalue)
                if 'item:{}'.format(val) in self.__listorder:
                    self.__listorder[self.__listorder.index('item:{}'.format(val))] = _newvalue
        else:
            if self.__item is None:
                return None
            _newvalue = self.__do_cast(self.__item.property.value)
            if 'item:{}'.format(self.__item) in self.__listorder:
                self.__listorder[self.__listorder.index('item:{}'.format(self.__item))] = _newvalue
            values = _newvalue
        if values is not None:
            return values

        try:
            _newvalue = self.__item.property.path
            if 'item:{}'.format(self.__item) in self.__listorder:
                self.__listorder[self.__listorder.index('item:{}'.format(self.__item))] = _newvalue
            values = _newvalue
        except Exception as ex2:
            values = self.__item
            self._log_info("Problem while reading item '{0}' path: {1}.", values, ex2)
        return self.__do_cast(values)

    # Determine value from variable
    def __get_from_variable(self):
        if isinstance(self.__varname, list):
            values = []
            for var in self.__varname:
                value = self._abitem.get_variable(var)
                _newvalue = self.__do_cast(value)
                _newvalue = 'var:{}'.format(self.__varname) if _newvalue == '' else _newvalue
                if isinstance(_newvalue, str) and 'Unknown variable' in _newvalue:
                    self._log_warning("There is a problem with your variable: {}", _newvalue)
                    _newvalue = ''
                values.append(_newvalue)
                if 'var:{}'.format(var) in self.__listorder:
                    self._log_debug("Checking variable in loop '{0}', value {1} from list {2}",
                                    self.__varname, _newvalue, self.__listorder)
                    self.__listorder[self.__listorder.index('var:{}'.format(var))] = _newvalue
        else:
            _newvalue = self._abitem.get_variable(self.__varname)
            _newvalue = 'var:{}'.format(self.__varname) if _newvalue == '' else _newvalue
            if isinstance(_newvalue, str) and 'Unknown variable' in _newvalue:
                self._log_warning("There is a problem with your variable: {}", _newvalue)
                _newvalue = ''
            self._log_debug("Checking variable '{0}', value {1} from list {2}",
                            self.__varname, _newvalue, self.__listorder)
            if 'var:{}'.format(self.__varname) in self.__listorder:
                self.__listorder[self.__listorder.index('var:{}'.format(self.__varname))] = _newvalue
            values = _newvalue
            self._log_debug("Variable result: {0}", values)

        return values
