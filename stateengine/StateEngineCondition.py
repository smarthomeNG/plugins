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
from . import StateEngineCurrent
from . import StateEngineValue
from . import StateEngineEval

from lib.item.item import Item
import datetime
import re


# Class representing a single condition
class SeCondition(StateEngineTools.SeItemChild):
    # Name of condition
    @property
    def name(self):
        return self.__name

    # Initialize the condition
    # abitem: parent SeItem instance
    # name: Name of condition
    def __init__(self, abitem, name: str):
        super().__init__(abitem)
        self.__name = name
        self.__item = None
        self.__status = None
        self.__eval = None
        self.__status_eval = None
        self.__value = StateEngineValue.SeValue(self._abitem, "value", True)
        self.__min = StateEngineValue.SeValue(self._abitem, "min")
        self.__max = StateEngineValue.SeValue(self._abitem, "max")
        self.__negate = False
        self.__agemin = StateEngineValue.SeValue(self._abitem, "agemin")
        self.__agemax = StateEngineValue.SeValue(self._abitem, "agemax")
        self.__changedby = StateEngineValue.SeValue(self._abitem, "changedby", True)
        self.__updatedby = StateEngineValue.SeValue(self._abitem, "updatedby", True)
        self.__triggeredby = StateEngineValue.SeValue(self._abitem, "triggeredby", True)
        self.__changedbynegate = None
        self.__updatedbynegate = None
        self.__triggeredbynegate = None
        self.__agenegate = None
        self.__error = None
        self.__itemClass = Item

    def __repr__(self):
        return "SeCondition 'item': {}, 'status': {}, 'eval': {}, " \
               "'status_eval': {}, 'value': {}".format(self.__item, self.__status, self.__eval, self.__status_eval, self.__value)

    def check_items(self, check, value=None, item_state=None):
        item_issue, status_issue, eval_issue, status_eval_issue = None, None, None, None
        item_value, status_value, eval_value, status_eval_value = None, None, None, None
        if check == "se_item" or (check == "attribute" and self.__item is None and self.__eval is None):
            if value is None:
                value = StateEngineTools.find_attribute(self._sh, item_state, "se_item_" + self.__name)
            if value is not None:
                match = re.match(r'^(.*):', value)
                if isinstance(value, str) and value.startswith("eval:"):
                    _, _, value = value.partition(":")
                    self.__eval = value
                    self.__item = None
                elif match:
                    self._log_warning("Your item configuration '{0}' is wrong! Define a plain (relative) "
                                      "item without {1} at the beginning!", value, match.group(1))
                    item_issue = "Your eval configuration '{0}' is wrong, remove {1}".format(value, match.group(1))
                    self.__item = None
                else:
                    value, issue = self._abitem.return_item(value)
                    self.__item = value
                item_value = value
        if check == "se_status" or (check == "attribute" and self.__status is None and self.__status_eval is None):
            if value is None:
                value = StateEngineTools.find_attribute(self._sh, item_state, "se_status_" + self.__name)
            if value is not None:
                match = re.match(r'^(.*):', value)
                if isinstance(value, str) and value.startswith("eval:"):
                    _, _, value = value.partition(":")
                    self.__status_eval = value
                    self.__status = None
                elif match:
                    self._log_warning("Your item configuration '{0}' is wrong! Define a plain (relative) "
                                      "item without {1} at the beginning!", value, match.group(1))
                    status_issue = "Your eval configuration '{0}' is wrong, remove {1}".format(value, match.group(1))
                    self.__status = None
                    value = None
                else:
                    value, issue = self._abitem.return_item(value)
                    self.__status = value
            status_value = value
        if check == "se_eval" or (check == "attribute" and self.__eval is None):
            if value is None:
                value = StateEngineTools.find_attribute(self._sh, item_state, "se_eval_" + self.__name)
            if value is not None:
                match = re.match(r'^(.*):', value)
                if value.startswith("eval:"):
                    _, _, value = value.partition("eval:")
                elif match:
                    self._log_warning("Your eval configuration '{0}' is wrong! You have to define "
                                      "a plain eval expression", value)
                    eval_issue = "Your eval configuration '{0}' is wrong!".format(value)
                    value = None
                self.__eval = value
            eval_value = value
        if check == "se_status_eval" or (check == "attribute" and self.__status_eval is None):
            if value is None:
                value = StateEngineTools.find_attribute(self._sh, item_state, "se_status_eval_" + self.__name)
            if value is not None:
                match = re.match(r'^(.*):', value)
                if value.startswith("eval:"):
                    _, _, value = value.partition("eval:")
                elif match:
                    self._log_warning("Your status eval configuration '{0}' is wrong! You have to define "
                                      "a plain eval expression", value)
                    status_eval_issue = "Your status eval configuration '{0}' is wrong!".format(value)
                    value = None
                self.__status_eval = value
            status_eval_value = value
        return item_value, status_value, eval_value, status_eval_value, item_issue, status_issue, eval_issue, status_eval_issue

    # set a certain function to a given value
    # func: Function to set ('item', 'eval', 'status_eval', 'value', 'min', 'max', 'negate', 'changedby', 'updatedby',
    # 'triggeredby','changedbynegate', 'updatedbynegate', 'triggeredbynegate','agemin', 'agemax' or 'agenegate')
    # value: Value for function
    def set(self, func, value):
        issue = None
        if func == "se_item":
            value, _, _, _, issue, _, _, _ = self.check_items("se_item", value)
        elif func == "se_status":
            _, value, _, _, _, issue, _, _ = self.check_items("se_status", value)
        elif func == "se_eval":
            _, _, value, _, _, _, issue, _ = self.check_items("se_eval", value)
        elif func == "se_status_eval":
            _, _, _, value, _, _, _, issue = self.check_items("se_status_eval", value)

        if func == "se_value":
            self.__value.set(value, self.__name)
        elif func == "se_min":
            self.__min.set(value, self.__name)
        elif func == "se_max":
            self.__max.set(value, self.__name)
        elif func in ["se_agemin", "se_minage"]:
            self.__agemin.set(value, self.__name)
        elif func in ["se_agemax", "se_maxage"]:
            self.__agemax.set(value, self.__name)
        elif func == "se_changedby":
            self.__changedby.set(value, self.__name)
        elif func == "se_updatedby":
            self.__updatedby.set(value, self.__name)
        elif func == "se_triggeredby":
            self.__triggeredby.set(value, self.__name)
        elif func == "se_changedbynegate":
            self.__changedbynegate = value
        elif func == "se_updatedbynegate":
            self.__updatedbynegate = value
        elif func == "se_triggeredbynegate":
            self.__triggeredbynegate = value
        elif func == "se_negate":
            self.__negate = value
        elif func == "se_agenegate":
            self.__agenegate = value
        elif func != "se_item" and func != "se_eval" and func != "se_status_eval" and func != "se_status":
            self._log_warning("Function '{0}' is no valid function! Please check item attribute.", func)
            issue = "Function '{0}' is no valid function!".format(func)
        return issue

    def get(self):
        _eval_result = str(self.__eval)
        _status_eval_result = str(self.__status_eval)
        if 'SeItem' in _eval_result:
            _eval_result = _eval_result.split('SeItem.')[1].split(' ')[0]
        if 'SeCurrent' in _eval_result:
            _eval_result = _eval_result.split('SeCurrent.')[1].split(' ')[0]
        if 'SeItem' in _status_eval_result:
            _status_eval_result = _status_eval_result.split('SeItem.')[1].split(' ')[0]
        if 'SeCurrent' in _status_eval_result:
            _status_eval_result = _status_eval_result.split('SeCurrent.')[1].split(' ')[0]
        _value_result = self.__value.get_for_webif()
        try:
            _item = self.__item.property.path
        except Exception:
            _item = self.__item
        try:
            _status = self.__status.property.path
        except Exception:
            _status = self.__status
        result = {'item': _item, 'status': _status, 'eval': _eval_result, 'status_eval': _status_eval_result,
                  'value': _value_result,
                  'min': str(self.__min),
                  'max': str(self.__max), 'agemin': str(self.__agemin), 'agemax': str(self.__agemax),
                  'negate': str(self.__negate), 'agenegate': str(self.__agenegate),
                  'changedby': str(self.__changedby), 'updatedby': str(self.__updatedby),
                  'triggeredby': str(self.__triggeredby), 'triggeredbynegate': str(self.__triggeredbynegate),
                  'changedbynegate': str(self.__changedbynegate),
                  'updatedbynegate': str(self.__updatedbynegate),
                  'current': {}, 'match': {}}
        return result

    # Complete condition (do some checks, cast value, min and max based on item or eval data types)
    # item_state: item to read from
    # abitem_object: Related SeItem instance for later determination of current age and current delay
    def complete(self, item_state):
        # check if it is possible to complete this condition
        if self.__min.is_empty() and self.__max.is_empty() and self.__value.is_empty() \
                and self.__agemin.is_empty() and self.__agemax.is_empty() \
                and self.__changedby.is_empty() and self.__updatedby.is_empty() and self.__triggeredby.is_empty():
            return False

        # set 'eval' for some known conditions if item and eval are not set, yet
        if all(item is None for item in [self.__item, self.__status, self.__eval, self.__status_eval]):
            if self.__name == "weekday":
                self.__eval = StateEngineCurrent.values.get_weekday
            elif self.__name == "sun_azimut":
                self.__eval = StateEngineCurrent.values.get_sun_azimut
            elif self.__name == "sun_altitude":
                self.__eval = StateEngineCurrent.values.get_sun_altitude
            elif self.__name == "age":
                self.__eval = self._abitem.get_age
            elif self.__name == "condition_age":
                self.__eval = self._abitem.get_condition_age
            elif self.__name == "time":
                self.__eval = StateEngineCurrent.values.get_time
            elif self.__name == "random":
                self.__eval = StateEngineCurrent.values.get_random
            elif self.__name == "month":
                self.__eval = StateEngineCurrent.values.get_month
            elif self.__name == "laststate" or self.__name == "laststate_id":
                self.__eval = self._abitem.get_laststate_id
            elif self.__name == "laststate_name":
                self.__eval = self._abitem.get_laststate_name
            elif self.__name == "lastconditionset" or self.__name == "lastconditionset_id":
                self.__eval = self._abitem.get_lastconditionset_id
            elif self.__name == "lastconditionset_name":
                self.__eval = self._abitem.get_lastconditionset_name
            elif self.__name == "previousstate" or self.__name == "previousstate_id":
                self.__eval = self._abitem.get_previousstate_id
            elif self.__name == "previousstate_name":
                self.__eval = self._abitem.get_previousstate_name
            elif self.__name == "previousconditionset" or self.__name == "previousconditionset_id":
                self.__eval = self._abitem.get_previousconditionset_id
            elif self.__name == "previousconditionset_name":
                self.__eval = self._abitem.get_previousconditionset_name
            elif self.__name == "previousstate_conditionset" or self.__name == "previousstate_conditionset_id":
                self.__eval = self._abitem.get_previousstate_conditionset_id
            elif self.__name == "previousstate_conditionset_name":
                self.__eval = self._abitem.get_previousstate_conditionset_name
            elif self.__name == "trigger_item":
                self.__eval = self._abitem.get_update_trigger_item
            elif self.__name == "trigger_caller":
                self.__eval = self._abitem.get_update_trigger_caller
            elif self.__name == "trigger_source":
                self.__eval = self._abitem.get_update_trigger_source
            elif self.__name == "trigger_dest":
                self.__eval = self._abitem.get_update_trigger_dest
            elif self.__name == "original_item":
                self.__eval = self._abitem.get_update_original_item
            elif self.__name == "original_caller":
                self.__eval = self._abitem.get_update_original_caller
            elif self.__name == "original_source":
                self.__eval = self._abitem.get_update_original_source

        self.check_items("attribute", None, item_state)

        # now we should have either 'item' or '(status)eval' set. If not, raise ValueError
        if all(item is None for item in [self.__item, self.__status, self.__eval, self.__status_eval]):
            raise ValueError("Neither 'item' nor 'status' nor '(status)eval' given!")

        if any(item is not None for item in [self.__item, self.__status, self.__eval, self.__status_eval])\
           and not self.__changedby.is_empty() and self.__changedbynegate is None:
            self.__changedbynegate = False
        if any(item is not None for item in [self.__item, self.__status, self.__eval, self.__status_eval])\
           and not self.__updatedby.is_empty() and self.__updatedbynegate is None:
            self.__updatedbynegate = False
        if any(item is not None for item in [self.__item, self.__status, self.__eval, self.__status_eval])\
           and not self.__triggeredby.is_empty() and self.__triggeredbynegate is None:
            self.__triggeredbynegate = False

        # cast stuff
        try:
            if self.__item is not None:
                self.__cast_all(self.__item.cast)
            elif self.__status is not None:
                self.__cast_all(self.__status.cast)
            elif self.__name in ("weekday", "sun_azimut", "sun_altitude", "age", "delay", "random", "month"):
                self.__cast_all(StateEngineTools.cast_num)
            elif self.__name in (
                    "laststate", "laststate_id", "laststate_name", "lastconditionset", "lastconditionset_id", "lastconditionset_name",
                    "previousstate", "previousstate_name", "previousstate_id", "previousconditionset", "previousconditionset_id", "previousconditionset_name",
                    "previousstate_conditionset", "previousstate_conditionset_id", "previousstate_conditionset_name",
                    "trigger_item", "trigger_caller", "trigger_source", "trigger_dest", "original_item",
                    "original_caller", "original_source"):
                self.__cast_all(StateEngineTools.cast_str)
            elif self.__name == "time":
                self.__cast_all(StateEngineTools.cast_time)
        except Exception as ex:
            raise ValueError("Error when casting: {0}".format(ex))

        # 'agemin' and 'agemax' can only be used for items
        cond_min_max = self.__agemin.is_empty() and self.__agemax.is_empty()
        try:
            cond_evalitem = self.__eval and ("get_relative_item(" in self.__eval or "return_item(" in self.__eval)
        except Exception:
            cond_evalitem = False
        try:
            cond_status_evalitem = self.__status_eval and \
                                   ("get_relative_item(" in self.__status_eval or "return_item(" in self.__status_eval)
        except Exception:
            cond_status_evalitem = False
        if self.__item is None and self.__status is None and \
                not cond_min_max and not cond_evalitem and not cond_status_evalitem:
            raise ValueError("Condition {}: 'agemin'/'agemax' can not be used for eval!".format(self.__name))
        return True

    # Check if condition is matching
    def check(self, state):
        # Ignore if no current value can be determined (should not happen as we check this earlier, but to be sure ...)
        if all(item is None for item in [self.__item, self.__status, self.__eval, self.__status_eval]):
            self._log_info("Condition '{0}': No item, status or (status)eval found! "
                           "Considering condition as matching!", self.__name)
            return True
        self._log_debug("Condition '{0}': Checking all relevant stuff", self.__name)
        self._log_increase_indent()
        if not self.__check_value(state):
            self._log_decrease_indent()
            return False
        if not self.__check_updatedby(state):
            self._log_decrease_indent()
            return False
        if not self.__check_triggeredby(state):
            self._log_decrease_indent()
            return False
        if not self.__check_changedby(state):
            self._log_decrease_indent()
            return False
        if not self.__check_age(state):
            self._log_decrease_indent()
            return False
        self._log_decrease_indent()
        return True

    # Write condition to logger
    def write_to_logger(self):
        if self.__error is not None:
            self._log_warning("error: {0}", self.__error)
        if self.__item is not None:
            if isinstance(self.__item, list):
                for i in self.__item:
                    self._log_info("item: {0} ({1})", self.__name, i.property.path)
            else:
                self._log_info("item: {0} ({1})", self.__name, self.__item.property.path)
        if self.__status is not None:
            if isinstance(self.__status, list):
                for i in self.__status:
                    self._log_info("status item: {0} ({1})", self.__name, i.property.path)
            else:
                self._log_info("status item: {0} ({1})", self.__name, self.__status.property.path)
        if self.__eval is not None:
            if isinstance(self.__eval, list):
                for e in self.__eval:
                    self._log_info("eval: {0}", StateEngineTools.get_eval_name(e))
            else:
                self._log_info("eval: {0}", StateEngineTools.get_eval_name(self.__eval))
        if self.__status_eval is not None:
            if isinstance(self.__status_eval, list):
                for e in self.__status_eval:
                    self._log_info("status eval: {0}", StateEngineTools.get_eval_name(e))
            else:
                self._log_info("status eval: {0}", StateEngineTools.get_eval_name(self.__status_eval))
        self.__value.write_to_logger()
        self.__min.write_to_logger()
        self.__max.write_to_logger()
        if self.__negate is not None:
            self._log_info("negate: {0}", self.__negate)
        self.__agemin.write_to_logger()
        self.__agemax.write_to_logger()
        if self.__agenegate is not None:
            self._log_info("age negate: {0}", self.__agenegate)
        self.__changedby.write_to_logger()
        if self.__changedbynegate is not None and not self.__changedby.is_empty():
            self._log_info("changedby negate: {0}", self.__changedbynegate)
        self.__updatedby.write_to_logger()
        if self.__updatedbynegate is not None and not self.__updatedby.is_empty():
            self._log_info("updatedby negate: {0}", self.__updatedbynegate)
        self.__triggeredby.write_to_logger()
        if self.__updatedbynegate is not None and not self.__triggeredby.is_empty():
            self._log_info("triggeredby negate: {0}", self.__triggeredbynegate)

    # Cast 'value', 'min' and 'max' using given cast function
    # cast_func: cast function to use
    def __cast_all(self, cast_func):
        self.__value.set_cast(cast_func)
        self.__min.set_cast(cast_func)
        self.__max.set_cast(cast_func)
        if self.__negate is not None:
            self.__negate = StateEngineTools.cast_bool(self.__negate)
        self.__agemin.set_cast(StateEngineTools.cast_num)
        self.__agemax.set_cast(StateEngineTools.cast_num)
        self.__changedby.set_cast(StateEngineTools.cast_str)
        if self.__changedbynegate is not None:
            self.__changedbynegate = StateEngineTools.cast_bool(self.__changedbynegate)
        self.__updatedby.set_cast(StateEngineTools.cast_str)
        if self.__updatedbynegate is not None:
            self.__updatedbynegate = StateEngineTools.cast_bool(self.__updatedbynegate)
        self.__triggeredby.set_cast(StateEngineTools.cast_str)
        if self.__triggeredbynegate is not None:
            self.__triggeredbynegate = StateEngineTools.cast_bool(self.__triggeredbynegate)
        if self.__agenegate is not None:
            self.__agenegate = StateEngineTools.cast_bool(self.__agenegate)

    def __change_update_value(self, value, valuetype, state):
        def __convert(convert_value, convert_current):
            if convert_value is None:
                self._log_develop("Ignoring value None for conversion")
                return convert_value, convert_current
            _oldvalue = convert_value
            try:
                if isinstance(convert_value, re._pattern_type):
                    return convert_value, convert_current
            except Exception:
                if isinstance(convert_value, re.Pattern):
                    return convert_value, convert_current
            if isinstance(convert_current, bool):
                self.__value.set_cast(StateEngineTools.cast_bool)
                convert_value = StateEngineTools.cast_bool(convert_value)
            elif isinstance(convert_current, int):
                self.__value.set_cast(StateEngineTools.cast_num)
                convert_value = int(StateEngineTools.cast_num(convert_value))
            elif isinstance(convert_current, float):
                self.__value.set_cast(StateEngineTools.cast_num)
                convert_value = StateEngineTools.cast_num(convert_value) * 1.0
            elif isinstance(convert_current, list):
                self.__value.set_cast(StateEngineTools.cast_list)
                convert_value = StateEngineTools.cast_list(convert_value)
            elif isinstance(convert_current, datetime.time):
                self.__value.set_cast(StateEngineTools.cast_time)
                convert_value = StateEngineTools.cast_time(convert_value)
            else:
                self.__value.set_cast(StateEngineTools.cast_str)
                convert_value = StateEngineTools.cast_str(convert_value)
                convert_current = StateEngineTools.cast_str(convert_value)
            if not type(_oldvalue) == type(convert_value):
                self._log_debug("Value {} was type {} and therefore not the same"
                                " type as item value {}. It got converted to {}.",
                                _oldvalue, type(_oldvalue), convert_current, type(convert_value))
            return convert_value, convert_current

        current = self.__get_current(eval_type='changedby') if valuetype == "changedby" else\
            self.__get_current(eval_type='updatedby') if valuetype == "updatedby" else\
            self.__get_current(eval_type='triggeredby') if valuetype == "triggeredby" else\
            self.__get_current(eval_type='value')
        negate = self.__changedbynegate if valuetype == "changedby" else\
            self.__updatedbynegate if valuetype == "updatedby" else\
            self.__triggeredbynegate if valuetype == "triggeredby" else\
            self.__negate

        if isinstance(value, list):
            text = "Condition '{0}': {1}={2} negate={3} current={4}"
            _key = ['{}'.format(state.id), 'conditionsets', '{}'.format(self._abitem.get_variable('current.conditionset_name')), '{}'.format(self.__name), 'current', '{}'.format(valuetype)]
            self._abitem.update_webif(_key, str(current))
            self._log_info(text, self.__name, valuetype, value, negate, current)
            self._log_increase_indent()
            for i, element in enumerate(value):
                regex_result = None
                regex_check = False
                if valuetype == "value" and type(element) != type(current) and current is not None:
                    element, current = __convert(element, current)
                try:
                    if isinstance(element, re._pattern_type):
                        regex_result = element.fullmatch(str(current))
                        regex_check = True
                except Exception:
                    if isinstance(element, re.Pattern):
                        regex_result = element.fullmatch(str(current))
                        regex_check = True
                if negate:
                    if (regex_result is not None and regex_check is True)\
                       or (current == element and regex_check is False):
                        self._log_debug("{0} found but negated -> not matching", element)
                        _key = ['{}'.format(state.id), 'conditionsets', '{}'.format(self._abitem.get_variable('current.conditionset_name')), '{}'.format(self.__name), 'match', '{}'.format(valuetype)]
                        self._abitem.update_webif(_key, 'no')
                        return False
                else:
                    if (regex_result is not None and regex_check is True)\
                       or (current == element and regex_check is False):
                        self._log_debug("{0} found -> matching", element)
                        _key = ['{}'.format(state.id), 'conditionsets', '{}'.format(self._abitem.get_variable('current.conditionset_name')), '{}'.format(self.__name), 'match', '{}'.format(valuetype)]
                        self._abitem.update_webif(_key, 'yes')
                        return True
                if regex_check is True:
                    self._log_debug("Regex '{}' result: {}, element {}", element, regex_result)

            if negate:
                self._log_debug("{0} not in list -> matching", current)
                _key = ['{}'.format(state.id), 'conditionsets', '{}'.format(self._abitem.get_variable('current.conditionset_name')), '{}'.format(self.__name), 'match', '{}'.format(valuetype)]
                self._abitem.update_webif(_key, 'yes')
                return True
            else:
                self._log_debug("{0} not in list -> not matching", current)
                _key = ['{}'.format(state.id), 'conditionsets', '{}'.format(self._abitem.get_variable('current.conditionset_name')), '{}'.format(self.__name), 'match', '{}'.format(valuetype)]
                self._abitem.update_webif(_key, 'no')
                return False
        else:
            regex_result = None
            regex_check = False
            # If current and value have different types, convert both to string
            if valuetype == "value" and type(value) != type(current) and current is not None:
                value, current = __convert(value, current)
            text = "Condition '{0}': {1}={2} negate={3} current={4}"
            _key = ['{}'.format(state.id), 'conditionsets', '{}'.format(self._abitem.get_variable('current.conditionset_name')), '{}'.format(self.__name), 'current', valuetype]
            self._abitem.update_webif(_key, str(current))
            self._log_info(text, self.__name, valuetype, value, negate, current)
            self._log_increase_indent()
            try:
                if isinstance(value, re._pattern_type):
                    regex_result = value.fullmatch(str(current))
                    regex_check = True
            except Exception:
                if isinstance(value, re.Pattern):
                    regex_result = value.fullmatch(str(current))
                    regex_check = True
            if negate:
                if (regex_result is None and regex_check is True)\
                   or (current != value and regex_check is False):
                    self._log_debug("not OK but negated -> matching")
                    _key = ['{}'.format(state.id), 'conditionsets', '{}'.format(self._abitem.get_variable('current.conditionset_name')), '{}'.format(self.__name), 'match', '{}'.format(valuetype)]
                    self._abitem.update_webif(_key, 'yes')
                    return True
            else:
                if (regex_result is not None and regex_check is True)\
                   or (current == value and regex_check is False):
                    self._log_debug("OK -> matching")
                    _key = ['{}'.format(state.id), 'conditionsets', '{}'.format(self._abitem.get_variable('current.conditionset_name')), '{}'.format(self.__name), 'match', '{}'.format(valuetype)]
                    self._abitem.update_webif(_key, 'yes')
                    return True
            self._log_debug("not OK -> not matching")
            _key = ['{}'.format(state.id), 'conditionsets', '{}'.format(self._abitem.get_variable('current.conditionset_name')), '{}'.format(self.__name), 'match', '{}'.format(valuetype)]
            self._abitem.update_webif(_key, 'no')
            return False

    # Check if value conditions match
    def __check_value(self, state):
        try:
            cond_min_max = self.__min.is_empty() and self.__max.is_empty()
            if not self.__value.is_empty():
                # 'value' is given. We ignore 'min' and 'max' and check only for the given value
                value = self.__value.get()
                value = StateEngineTools.flatten_list(value)
                return self.__change_update_value(value, "value", state)

            elif not cond_min_max:
                min_get_value = self.__min.get()
                max_get_value = self.__max.get()
                current = self.__get_current()
                try:
                    if isinstance(min_get_value, re._pattern_type) or isinstance(max_get_value, re._pattern_type):
                        self._log_warning("You can not use regular expression with min/max -> ignoring")
                        _key = ['{}'.format(state.id), 'conditionsets', '{}'.format(self._abitem.get_variable('current.conditionset_name')), '{}'.format(self.__name), 'match', 'value']
                        self._abitem.update_webif(_key, 'You can not use regular expression with min or max')
                        return True
                except Exception:
                    if isinstance(min_get_value, re.Pattern) or isinstance(max_get_value, re.Pattern):
                        self._log_warning("You can not use regular expression with min/max -> ignoring")
                        _key = ['{}'.format(state.id), 'conditionsets', '{}'.format(self._abitem.get_variable('current.conditionset_name')), '{}'.format(self.__name), 'match', 'value']
                        self._abitem.update_webif(_key, 'You can not use regular expression with min or max')
                        return True
                min_value = [min_get_value] if not isinstance(min_get_value, list) else min_get_value
                max_value = [max_get_value] if not isinstance(max_get_value, list) else max_get_value
                min_value = StateEngineTools.flatten_list(min_value)
                max_value = StateEngineTools.flatten_list(max_value)
                diff_len = len(min_value) - len(max_value)
                min_value = min_value + [None] * abs(diff_len) if diff_len < 0 else min_value
                max_value = max_value + [None] * diff_len if diff_len > 0 else max_value
                text = "Condition '{0}': min={1} max={2} negate={3} current={4}"
                _key = ['{}'.format(state.id), 'conditionsets', '{}'.format(self._abitem.get_variable('current.conditionset_name')), '{}'.format(self.__name), 'current', 'value']
                self._abitem.update_webif(_key, str(current))
                self._log_info(text, self.__name, min_value, max_value, self.__negate, current)
                if diff_len != 0:
                    self._log_debug("Min and max are always evaluated as valuepairs. "
                                    "If needed you can also provide 'novalue' as a list value")
                self._log_increase_indent()
                _notmatching = 0
                for i, _ in enumerate(min_value):
                    min = None if min_value[i] == 'novalue' else min_value[i]
                    max = None if max_value[i] == 'novalue' else max_value[i]
                    self._log_debug("Checking minvalue {} ({}) and maxvalue {} ({}) against current {} ({})", min, type(min), max, type(max), current, type(current))
                    if min is not None and max is not None and min > max:
                        min, max = max, min
                        self._log_warning("Condition {}: min must not be greater than max! "
                                          "Values got switched: min is now {}, max is now {}", self.__name, min, max)
                    if min is None and max is None:
                        self._log_debug("no limit given -> matching")
                        _key = ['{}'.format(state.id), 'conditionsets', '{}'.format(self._abitem.get_variable('current.conditionset_name')), '{}'.format(self.__name), 'match', 'value']
                        self._abitem.update_webif(_key, 'yes')
                        return True

                    if not self.__negate:
                        if min is not None and current < min:
                            self._log_debug("too low -> not matching")
                            _notmatching += 1

                        elif max is not None and current > max:
                            self._log_debug("too high -> not matching")
                            _notmatching += 1

                        else:
                            self._log_debug("given limits ok -> matching")
                            _key = ['{}'.format(state.id), 'conditionsets', '{}'.format(self._abitem.get_variable('current.conditionset_name')), '{}'.format(self.__name), 'match', 'value']
                            self._abitem.update_webif(_key, 'yes')
                            return True
                    else:
                        if min is not None and current > min and (max is None or current < max):
                            self._log_debug("not lower than min -> not matching")
                            _notmatching += 1

                        elif max is not None and current < max and (min is None or current > min):
                            self._log_debug("not higher than max -> not matching")
                            _notmatching += 1

                        else:
                            self._log_debug("given limits ok -> matching")
                            _key = ['{}'.format(state.id), 'conditionsets', '{}'.format(self._abitem.get_variable('current.conditionset_name')), '{}'.format(self.__name), 'match', 'value']
                            self._abitem.update_webif(_key, 'yes')
                            return True

                if _notmatching == len(min_value):
                    _key = ['{}'.format(state.id), 'conditionsets', '{}'.format(self._abitem.get_variable('current.conditionset_name')), '{}'.format(self.__name), 'match', 'value']
                    self._abitem.update_webif(_key, 'no')
                    return False
                else:
                    self._log_debug("given limits ok -> matching")
                    _key = ['{}'.format(state.id), 'conditionsets', '{}'.format(self._abitem.get_variable('current.conditionset_name')), '{}'.format(self.__name), 'match', 'value']
                    self._abitem.update_webif(_key, 'yes')
                    return True

            elif self.__value.is_empty() and cond_min_max:
                self._log_warning("Condition {}: Neither value nor min/max given."
                                  " This might result in unexpected"
                                  " evalutions. Min {}, max {}, value {}", self.__name,
                                  self.__min.get(), self.__max.get(), self.__value.get())
                self._log_increase_indent()
                _key = ['{}'.format(state.id), 'conditionsets', '{}'.format(self._abitem.get_variable('current.conditionset_name')), '{}'.format(self.__name), 'match', 'value']
                self._abitem.update_webif(_key, 'Neither value nor min/max given.')
                return True

        except Exception as ex:
            self._log_warning("Problem checking value: {}", ex)
            _key = ['{}'.format(state.id), 'conditionsets', '{}'.format(self._abitem.get_variable('current.conditionset_name')), '{}'.format(self.__name), 'match', 'value']
            self._abitem.update_webif(_key, 'Problem checking value: {}'.format(ex))
        finally:
            self._log_decrease_indent()

    # Check if changedby conditions match
    def __check_changedby(self, state):
        try:
            if not self.__changedby.is_empty():
                # 'changedby' is given.
                changedby = self.__changedby.get()
                changedby = StateEngineTools.flatten_list(changedby)
                return self.__change_update_value(changedby, "changedby", state)

            else:
                self._log_increase_indent()
                return True

        except Exception as ex:
            self._log_warning("Problem checking changedby {}", ex)
        finally:
            self._log_decrease_indent()

    # Check if triggeredby conditions match
    def __check_triggeredby(self, state):
        try:
            if not self.__triggeredby.is_empty():
                # 'updatedby' is given.
                triggeredby = self.__triggeredby.get()
                triggeredby = StateEngineTools.flatten_list(triggeredby)
                return self.__change_update_value(triggeredby, "triggeredby", state)
            else:
                self._log_increase_indent()
                return True

        except Exception as ex:
            self._log_warning("Problem checking triggeredby {}", ex)
        finally:
            self._log_decrease_indent()

    # Check if updatedby conditions match
    def __check_updatedby(self, state):
        try:
            if not self.__updatedby.is_empty():
                # 'updatedby' is given.
                updatedby = self.__updatedby.get()
                updatedby = StateEngineTools.flatten_list(updatedby)
                return self.__change_update_value(updatedby, "updatedby", state)
            else:
                self._log_increase_indent()
                return True

        except Exception as ex:
            self._log_warning("Problem checking updatedby {}", ex)
        finally:
            self._log_decrease_indent()

    # Check if age conditions match
    def __check_age(self, state):
        # No limits given -> OK
        if self.__agemin.is_empty() and self.__agemax.is_empty():
            self._log_debug("Age of '{0}': No limits given", self.__name)
            return True

        # Ignore if no current value can be determined
        if all(item is None for item in [self.__item, self.__status, self.__eval, self.__status_eval]):
            self._log_warning("Age of '{0}': No item/eval found! Considering condition as matching!", self.__name)
            return True

        try:
            cond_evalitem = self.__eval and ("get_relative_item(" in self.__eval or "return_item(" in self.__eval)
        except Exception:
            cond_evalitem = False
        try:
            cond_status_evalitem = self.__status_eval and \
                                   ("get_relative_item(" in self.__status_eval or "return_item(" in self.__status_eval)
        except Exception:
            cond_status_evalitem = False
        if self.__item is None and cond_evalitem is False:
            self._log_warning("Make sure your se_eval/se_item: eval:<..> '{}' really returns an item and not an ID. "
                              "If the age condition does not work, please check your eval!", self.__eval)
        if self.__status is None and cond_status_evalitem is False:
            self._log_warning("Make sure your se_status: eval:<..> '{}' really returns an item and not an ID. "
                              "If the age condition does not work, please check your eval!", self.__status_eval)
        try:
            current = self.__get_current(eval_type='age')
        except Exception as ex:
            _key = ['{}'.format(state.id), 'conditionsets', '{}'.format(self._abitem.get_variable('current.conditionset_name')), '{}'.format(self.__name), 'match', 'age']
            self._abitem.update_webif(_key, 'Not possible to get age from eval {} '
                                            'or status_eval {}'.format(self.__eval, self.__status_eval))
            self._log_warning("Age of '{0}': Not possible to get age from eval {1} or status_eval {2}! "
                              "Considering condition as matching: {3}", self.__name, self.__eval, self.__status_eval, ex)

            return True
        agemin = None if self.__agemin.is_empty() else self.__agemin.get()
        agemax = None if self.__agemax.is_empty() else self.__agemax.get()
        try:
            # We check 'min' and 'max' (if given)
            agemin = [agemin] if not isinstance(agemin, list) else agemin
            agemax = [agemax] if not isinstance(agemax, list) else agemax
            agemin = StateEngineTools.flatten_list(agemin)
            agemax = StateEngineTools.flatten_list(agemax)
            diff_len = len(agemin) - len(agemax)
            agemin = agemin + [None] * abs(diff_len) if diff_len < 0 else agemin
            agemax = agemax + [None] * diff_len if diff_len > 0 else agemax
            text = "Age of '{0}': min={1} max={2} negate={3} current={4}"
            _key = ['{}'.format(state.id), 'conditionsets', '{}'.format(self._abitem.get_variable('current.conditionset_name')), '{}'.format(self.__name), 'current', 'age']
            self._abitem.update_webif(_key, str(current))
            self._log_info(text, self.__name, agemin, agemax, self.__agenegate, current)
            if diff_len != 0:
                self._log_warning("Min and max age are always evaluated as valuepairs."
                                  " If needed you can also provide 'novalue' as a list value")
            self._log_increase_indent()
            _notmatching = 0
            for i, _ in enumerate(agemin):
                min = None if agemin[i] == 'novalue' else agemin[i]
                max = None if agemax[i] == 'novalue' else agemax[i]
                self._log_debug("Testing valuepair min {} and max {}", min, max)
                if not self.__agenegate:
                    if min is not None and current < min:
                        self._log_debug("too young -> not matching")
                        _notmatching += 1

                    elif max is not None and current > max:
                        self._log_debug("too old -> not matching")
                        _notmatching += 1

                    else:
                        self._log_debug("given limits ok -> matching")
                        _key = ['{}'.format(state.id), 'conditionsets', '{}'.format(self._abitem.get_variable('current.conditionset_name')), '{}'.format(self.__name), 'match', 'age']
                        self._abitem.update_webif(_key, 'yes')
                        return True
                else:
                    if min is not None and current > min and (max is None or current < max):
                        self._log_debug("not younger than min -> not matching")
                        _notmatching += 1

                    elif max is not None and current < max and (min is None or current > min):
                        self._log_debug("not older than max -> not matching")
                        _notmatching += 1

                    else:
                        self._log_debug("given limits ok -> matching")
                        _key = ['{}'.format(state.id), 'conditionsets', '{}'.format(self._abitem.get_variable('current.conditionset_name')), '{}'.format(self.__name), 'match', 'age']
                        self._abitem.update_webif(_key, 'yes')
                        return True

            if _notmatching == len(agemin):
                _key = ['{}'.format(state.id), 'conditionsets', '{}'.format(self._abitem.get_variable('current.conditionset_name')), '{}'.format(self.__name), 'match', 'age']
                self._abitem.update_webif(_key, 'no')
                return False
            else:
                self._log_debug("given limits ok -> matching")
                _key = ['{}'.format(state.id), 'conditionsets', '{}'.format(self._abitem.get_variable('current.conditionset_name')), '{}'.format(self.__name), 'match', 'age']
                self._abitem.update_webif(_key, 'yes')
                return True
        finally:
            self._log_decrease_indent()

    # Current value of condition (based on item or eval)
    def __get_current(self, eval_type='value'):
        def check_eval(eval_or_status_eval):
            if isinstance(eval_or_status_eval, str):
                sh = self._sh
                shtime = self._shtime
                # noinspection PyUnusedLocal
                if "stateengine_eval" in eval_or_status_eval or "se_eval" in eval_or_status_eval:
                    # noinspection PyUnusedLocal
                    stateengine_eval = se_eval = StateEngineEval.SeEval(self._abitem)
                try:
                    eval_result = eval(eval_or_status_eval)
                    if isinstance(eval_result, self.__itemClass):
                        value = eval_result.property.last_change_age if eval_type == 'age' else \
                                eval_result.property.last_change_by if eval_type == 'changedby' else \
                                eval_result.property.last_update_by if eval_type == 'updatedby' else \
                                eval_result.property.last_trigger_by if eval_type == 'triggeredby' else \
                                eval_result.property.value
                    else:
                        value = eval_result
                except Exception as ex:
                    text = "Condition {}: problem evaluating {}: {}"
                    raise ValueError(text.format(self.__name, eval_or_status_eval, ex))
                else:
                    return value
            else:
                return eval_or_status_eval()

        if self.__status is not None:
            # noinspection PyUnusedLocal
            self._log_debug("Trying to get {} of status item {}", eval_type, self.__status)
            return self.__status.property.last_change_age if eval_type == 'age' else\
                   self.__status.property.last_change_by if eval_type == 'changedby' else\
                   self.__status.property.last_update_by if eval_type == 'updatedby' else\
                   self.__status.property.last_trigger_by if eval_type == 'triggeredby' else\
                   self.__status.property.value
        elif self.__item is not None:
            # noinspection PyUnusedLocal
            self._log_debug("Trying to get {} of item {}", eval_type, self.__item)
            return self.__item.property.last_change_age if eval_type == 'age' else\
                   self.__item.property.last_change_by if eval_type == 'changedby' else\
                   self.__item.property.last_update_by if eval_type == 'updatedby' else\
                   self.__item.property.last_trigger_by if eval_type == 'triggeredby' else\
                   self.__item.property.value
        if self.__status_eval is not None:
            self._log_debug("Trying to get {} of statuseval {}", eval_type, self.__status_eval)
            return_value = check_eval(self.__status_eval)
            return return_value
        elif self.__eval is not None:
            self._log_debug("Trying to get {} of statuseval {}", eval_type, self.__eval)
            return_value = check_eval(self.__eval)
            return return_value

        raise ValueError("Condition {}: Neither 'item' nor 'status' nor '(status)eval' given!".format(self.__name))
