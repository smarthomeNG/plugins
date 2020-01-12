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
from collections import OrderedDict


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
        self.__eval = None
        self.__value = StateEngineValue.SeValue(self._abitem, "value", True)
        self.__min = StateEngineValue.SeValue(self._abitem, "min")
        self.__max = StateEngineValue.SeValue(self._abitem, "max")
        self.__negate = False
        self.__agemin = StateEngineValue.SeValue(self._abitem, "agemin")
        self.__agemax = StateEngineValue.SeValue(self._abitem, "agemax")
        self.__agenegate = None
        self.__error = None

    def __repr__(self):
        return "'item': {}, 'eval': {}, 'value': {}".format(self.__item, self.__eval, self.__value)

    # set a certain function to a given value
    # func: Function to set ('item', 'eval', 'value', 'min', 'max', 'negate', 'agemin', 'agemax' or 'agenegate')
    # value: Value for function
    def set(self, func, value):
        if func == "se_item":
            if ":" in value:
                self._log_warning("Your item configuration '{0}' is wrong! Define a plain (relative) item!", value)
                _, _, value = value.partition(":")
            self.__item = self._abitem.return_item(value)
        elif func == "se_eval":
            if ":" in value:
                self._log_warning("Your eval configuration '{0}' is wrong! Define a plain eval term!", value)
                _, _, value = value.partition(":")
            self.__eval = value
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
        elif func == "se_negate":
            self.__negate = value
        elif func == "se_agenegate":
            self.__agenegate = value
        elif func != "se_item" and func != "se_eval":
            self._log_warning("Function '{0}' is no valid function! Please check item attribute.", func)

    def get(self):
        eval_result = str(self.__eval)
        if 'SeItem' in eval_result:
            eval_result = eval_result.split('SeItem.')[1].split(' ')[0]
        if 'SeCurrent' in eval_result:
            eval_result = eval_result.split('SeCurrent.')[1].split(' ')[0]
        value_result = str(self.__value.get_for_webif())
        result = {'item': str(self.__item), 'eval': eval_result, 'value': value_result, 'min': str(self.__min),
                  'max': str(self.__max), 'agemin': str(self.__agemin), 'agemax': str(self.__agemax),
                  'negate': str(self.__negate), 'agenegate': str(self.__agenegate)}
        return result

    # Complete condition (do some checks, cast value, min and max based on item or eval data types)
    # item_state: item to read from
    # abitem_object: Related SeItem instance for later determination of current age and current delay
    def complete(self, item_state):
        # check if it is possible to complete this condition
        if self.__min.is_empty() and self.__max.is_empty() and self.__value.is_empty() \
                and self.__agemin.is_empty() and self.__agemax.is_empty():
            return False

        # set 'eval' for some known conditions if item and eval are not set, yet
        if self.__item is None and self.__eval is None:
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
            elif self.__name == "laststate":
                self.__eval = self._abitem.get_laststate_id
            elif self.__name == "lastconditionset" or self.__name == "lastconditionset_id":
                self.__eval = self._abitem.get_lastconditionset_id
            elif self.__name == "lastconditionset_name":
                self.__eval = self._abitem.get_lastconditionset_name
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

        # missing item in condition: Try to find it
        if self.__item is None:
            result = StateEngineTools.find_attribute(self._sh, item_state, "se_item_" + self.__name)
            if result is not None:
                self.__item = self._abitem.return_item(result)

        # missing eval in condition: Try to find it
        if self.__eval is None:
            result = StateEngineTools.find_attribute(self._sh, item_state, "se_eval_" + self.__name)
            if result is not None:
                self.__eval = result

        # no we should have either 'item' or 'eval' set. If not, raise ValueError
        if self.__item is None and self.__eval is None:
            raise ValueError("Condition {}: Neither 'item' nor 'eval' given!".format(self.__name))

        # cast stuff
        try:
            if self.__item is not None:
                self.__cast_all(self.__item.cast)
            elif self.__name in ("weekday", "sun_azimut", "sun_altitude", "age", "delay", "random", "month"):
                self.__cast_all(StateEngineTools.cast_num)
            elif self.__name in (
                    "laststate", "lastconditionset", "lastconditionset_id", "lastconditionset_name",
                    "trigger_item", "trigger_caller", "trigger_source", "trigger_dest", "original_item",
                    "original_caller", "original_source"):
                self.__cast_all(StateEngineTools.cast_str)
            elif self.__name == "time":
                self.__cast_all(StateEngineTools.cast_time)
        except Exception as ex:
            raise ValueError("Condition {0}: Error when casting: {1}".format(self.__name, ex))

        # 'agemin' and 'agemax' can only be used for items
        cond_min_max = self.__agemin.is_empty() and self.__agemax.is_empty()
        try:
            cond_evalitem = self.__eval and ("get_relative_item(" in self.__eval or "return_item(" in self.__eval)
        except Exception:
            cond_evalitem = False
        if self.__item is None and not cond_min_max and not cond_evalitem:
            raise ValueError("Condition {}: 'agemin'/'agemax' can not be used for eval!".format(self.__name))

        return True

    # Check if condition is matching
    def check(self):
        # Ignore if no current value can be determined (should not happen as we check this earlier, but to be sure ...)
        if self.__item is None and self.__eval is None:
            self._log_info("Condition '{0}': No item or eval found! Considering condition as matching!", self.__name)
            return True
        self._log_debug("Condition '{0}': Checking all relevant stuff", self.__name)
        self._log_increase_indent()
        if not self.__check_value():
            self._log_decrease_indent()
            return False
        if not self.__check_age():
            self._log_decrease_indent()
            return False
        self._log_decrease_indent()
        return True

    # Write condition to logger
    def write_to_logger(self):
        if self.__error is not None:
            self._log_debug("error: {0}", self.__error)
        if self.__item is not None:
            if isinstance(self.__item, list):
                for i in self.__item:
                    self._log_debug("item: {0} ({1})", self.__name, i.property.path)
            else:
                self._log_debug("item: {0} ({1})", self.__name, self.__item.property.path)
        if self.__eval is not None:
            if isinstance(self.__item, list):
                for e in self.__item:
                    self._log_debug("eval: {0}", StateEngineTools.get_eval_name(e))
            else:
                self._log_debug("eval: {0}", StateEngineTools.get_eval_name(self.__eval))
        self.__value.write_to_logger()
        self.__min.write_to_logger()
        self.__max.write_to_logger()
        if self.__negate is not None:
            self._log_debug("negate: {0}", self.__negate)
        self.__agemin.write_to_logger()
        self.__agemax.write_to_logger()
        if self.__agenegate is not None:
            self._log_debug("age negate: {0}", self.__agenegate)

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
        if self.__agenegate is not None:
            self.__agenegate = StateEngineTools.cast_bool(self.__agenegate)

    # Check if value conditions match
    def __check_value(self):
        def __convert(value, current):
            _oldvalue = value
            if isinstance(current, bool):
                value = StateEngineTools.cast_bool(value)
            elif isinstance(current, int):
                value = int(StateEngineTools.cast_num(value))
            elif isinstance(current, float):
                value = StateEngineTools.cast_num(value) * 1.0
            elif isinstance(current, list):
                value = StateEngineTools.cast_list(value)
            else:
                value = str(value)
                current = str(current)
            if not type(_oldvalue) == type(value):
                self._log_info("Value {} was type {} and therefore not the same type as item value {}. It got converted to {}.",
                               _oldvalue, type(_oldvalue), current, type(value))
            return value, current

        current = self.__get_current()
        try:
            cond_min_max = self.__min.is_empty() and self.__max.is_empty()
            if not self.__value.is_empty():
                # 'value' is given. We ignore 'min' and 'max' and check only for the given value
                value = self.__value.get()
                value = StateEngineTools.flatten_list(value)

                if isinstance(value, list):
                    text = "Condition '{0}': value={1} negate={2} current={3}"
                    self._log_debug(text, self.__name, value, self.__negate, current)
                    self._log_increase_indent()

                    for element in value:
                        if type(element) != type(current) and current is not None:
                            element, current = __convert(element, current)
                        if self.__negate:
                            if current == element:
                                self._log_debug("{0} found but negated -> not matching", element)
                                return False
                        else:
                            if current == element:
                                self._log_debug("{0} found -> matching", element)
                                return True

                    if self.__negate:
                        self._log_debug("{0} not in list -> matching", current)
                        return True
                    else:
                        self._log_debug("{0} not in list -> not matching", current)
                        return False

                else:
                    # If current and value have different types, convert both to string
                    if type(value) != type(current) and current is not None:
                        value, current = __convert(value, current)
                    text = "Condition '{0}': value={1} negate={2} current={3}"
                    self._log_debug(text, self.__name, value, self.__negate, current)
                    self._log_increase_indent()

                    if self.__negate:
                        if current != value:
                            self._log_debug("not OK but negated -> matching")
                            return True
                    else:
                        if current == value:
                            self._log_debug("OK -> matching")
                            return True

                    self._log_debug("not OK -> not matching")
                    return False

            elif not cond_min_max:
                min_get_value = self.__min.get()
                max_get_value = self.__max.get()
                min_value = [min_get_value] if not isinstance(min_get_value, list) else min_get_value
                max_value = [max_get_value] if not isinstance(max_get_value, list) else max_get_value
                min_value = StateEngineTools.flatten_list(min_value)
                max_value = StateEngineTools.flatten_list(max_value)
                diff_len = len(min_value) - len(max_value)
                min_value = min_value + [None] * abs(diff_len) if diff_len < 0 else min_value
                max_value = max_value + [None] * diff_len if diff_len > 0 else max_value
                text = "Condition '{0}': min={1} max={2} negate={3} current={4}"
                self._log_debug(text, self.__name, min_value, max_value, self.__negate, current)
                if diff_len != 0:
                    self._log_debug("Min and max are always evaluated as valuepairs. If needed you can also provide 'novalue' as a list value")
                self._log_increase_indent()
                _notmatching = 0
                for i, _ in enumerate(min_value):
                    min = None if min_value[i] == 'novalue' else min_value[i]
                    max = None if max_value[i] == 'novalue' else max_value[i]
                    self._log_debug("Checking minvalue {} and maxvalue {}", min, max)
                    if min is not None and max is not None and min > max:
                        min, max = max, min
                        self._log_warning("Condition {}: min must not be greater than max! "
                                          "Values got switched: min is now {}, max is now {}", self.__name, min, max)
                    if min is None and max is None:
                        self._log_debug("no limit given -> matching")
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
                            return True

                if _notmatching == len(min_value):
                    return False
                else:
                    self._log_debug("given limits ok -> matching")
                    return True
            else:
                self._log_warning("Neither value nor min/max given. This might result in unexpected evalutions. Min {}, max {}, value {}",
                                  self.__min.get(), self.__max.get(), self.__value.get())
                self._log_increase_indent()
                return True

        except Exception as ex:
            self._log_warning("Problem checking value {}", ex)
        finally:
            self._log_decrease_indent()

    # Check if age conditions match
    def __check_age(self):
        # No limits given -> OK
        if self.__agemin.is_empty() and self.__agemax.is_empty():
            self._log_info("Age of '{0}': No limits given", self.__name)
            return True

        # Ignore if no current value can be determined
        if self.__item is None and self.__eval is None:
            self._log_info("Age of '{0}': No item found! Considering condition as matching!", self.__name)
            return True

        try:
            cond_evalitem = self.__eval and ("get_relative_item(" in self.__eval or "return_item(" in self.__eval)
        except Exception:
            cond_evalitem = False
        if self.__item is None and cond_evalitem is False:
            self._log_info("Make sure your se_eval '{}' really contains an item and not an ID. If the age "
                           "condition does not work though, please check your eval!", self.__eval)

        try:
            current = self.__get_current(type='age')
        except Exception as ex:
            self._log_info("Age of '{0}': Not possible to get age from eval {1}! "
                           "Considering condition as matching: {2}", self.__name, self.__eval, ex)
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
            self._log_debug(text, self.__name, agemin, agemax, self.__agenegate, current)
            if diff_len != 0:
                self._log_debug("Min and max age are always evaluated as valuepairs. If needed you can also provide 'novalue' as a list value")
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
                        return True

            if _notmatching == len(agemin):
                return False
            else:
                self._log_debug("given limits ok -> matching")
                return True
        finally:
            self._log_decrease_indent()

    # Current value of condition (based on item or eval)
    def __get_current(self, type='value'):
        if self.__item is not None:
            return self.__item.property.value if type == 'value' else self.__item.property.last_change_age
        if self.__eval is not None:
            # noinspection PyUnusedLocal
            self._log_debug("Trying to get {} of eval {}", type, self.__eval)
            sh = self._sh
            if isinstance(self.__eval, str):
                # noinspection PyUnusedLocal
                if "stateengine_eval" in self.__eval or "se_eval" in self.__eval:
                    # noinspection PyUnusedLocal
                    stateengine_eval = se_eval = StateEngineEval.SeEval(self._abitem)
                try:
                    value = eval(self.__eval).property.value if type == 'value' else eval(self.__eval).property.last_change_age
                except Exception as ex:
                    text = "Condition {}: problem evaluating {}: {}"
                    raise ValueError(text.format(self.__name, self.__eval, ex))
                else:
                    return value
            else:
                return self.__eval()
        raise ValueError("Condition {}: Neither 'item' nor eval given!".format(self.__name))
