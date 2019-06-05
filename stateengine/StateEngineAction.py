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
from . import StateEngineValue
from . import StateEngineDefaults
import datetime
from lib.shtime import Shtime
from lib.item import Items


# Base class from which all action classes are derived
class SeActionBase(StateEngineTools.SeItemChild):
    # Cast function for delay
    # value: value to cast
    @staticmethod
    def __cast_delay(value):
        if isinstance(value, str):
            delay = value.strip()
            if delay.endswith('m'):
                return int(delay.strip('m')) * 60
            else:
                return int(delay)
        elif isinstance(value, int):
            return value
        elif isinstance(value, float):
            return int(value)
        else:
            raise ValueError("Can not cast delay value {0} to int!".format(value))

    # Initialize the action
    # abitem: parent SeItem instance
    # name: Name of action
    def __init__(self, abitem, name: str):
        super().__init__(abitem)
        self._parent = abitem
        self.shtime = Shtime.get_instance()
        self.items = Items.get_instance()
        self._name = name
        self.__delay = StateEngineValue.SeValue(self._abitem, "delay")
        self.__repeat = None
        self.__order = StateEngineValue.SeValue(self._abitem, "order", False, "num")
        self._scheduler_name = None

    def update_delay(self, value):
        self.__delay.set(value)
        self.__delay.set_cast(SeActionBase.__cast_delay)

    def update_repeat(self, value):
        if self.__repeat is None:
            self.__repeat = StateEngineValue.SeValue(self._abitem, "repeat", False, "bool")
        self.__repeat.set(value)

    def update_order(self, value):
        self.__order.set(value)

    def get_order(self):
        return self.__order.get(1)

    # Write action to logger
    def write_to_logger(self):
        self.__delay.write_to_logger()
        if self.__repeat is not None:
            self.__repeat.write_to_logger()
        self.__order.write_to_logger()

    # Execute action (considering delay, etc)
    # is_repeat: Inidicate if this is a repeated action without changing the state
    # item_allow_repeat: Is repeating actions generally allowed for the item?
    def execute(self, is_repeat: bool, allow_item_repeat: bool):
        if not self._can_execute():
            return

        if is_repeat:
            if self.__repeat is None:
                if allow_item_repeat:
                    repeat_text = " Repeat allowed by item configuration."
                else:
                    self._log_info("Action '{0}': Repeat denied by item configuration.", self._name)
                    return
            elif self.__repeat.get():
                repeat_text = " Repeat allowed by action configuration."
            else:
                self._log_info("Action '{0}': Repeat denied by action configuration.", self._name)
                return
        else:
            repeat_text = ""

        plan_next = self._sh.scheduler.return_next(self._scheduler_name)
        if plan_next is not None and plan_next > self.shtime.now():
            self._log_info("Action '{0}: Removing previous delay timer '{1}'.", self._name, self._scheduler_name)
            self._sh.scheduler.remove(self._scheduler_name)

        delay = 0 if self.__delay.is_empty() else self.__delay.get()
        actionname = "Action '{0}'".format(self._name) if delay == 0 else "Delay Timer '{0}'".format(
            self._scheduler_name)
        if delay == 0:
            self._execute(actionname, repeat_text)
        elif delay is None:
            self._log_warning("Action'{0}: Ignored because of errors while determining the delay!", self._name)
        elif delay < 0:
            self._log_warning("Action'{0}: Ignored because of delay is negative!", self._name)
        else:
            self._log_info("Action '{0}: Add {1} second timer '{2}' for delayed execution. {3}", self._name, delay,
                           self._scheduler_name, repeat_text)
            next_run = self.shtime.now() + datetime.timedelta(seconds=delay)
            self._sh.scheduler.add(self._scheduler_name, self._execute, value={'actionname': actionname}, next=next_run)

    # set the action based on a set_(action_name) attribute
    # value: Value of the set_(action_name) attribute
    def update(self, value):
        raise NotImplementedError("Class %s doesn't implement update()" % self.__class__.__name__)

    # Complete action
    # item_state: state item to read from
    def complete(self, item_state):
        raise NotImplementedError("Class %s doesn't implement complete()" % self.__class__.__name__)

    # Check if execution is possible
    def _can_execute(self):
        return True

    # Really execute the action (needs to be implemented in derived classes)
    def _execute(self, actionname: str, repeat_text: str = ""):
        raise NotImplementedError("Class %s doesn't implement _execute()" % self.__class__.__name__)


# Class representing a single "se_set" action
class SeActionSetItem(SeActionBase):
    # Initialize the action
    # abitem: parent SeItem instance
    # name: Name of action
    def __init__(self, abitem, name: str):
        super().__init__(abitem, name)
        self.__item = None
        self.__value = StateEngineValue.SeValue(self._abitem, "value")
        self.__mindelta = StateEngineValue.SeValue(self._abitem, "mindelta")
        self.__caller = StateEngineDefaults.plugin_identification

    # set the action based on a set_(action_name) attribute
    # value: Value of the set_(action_name) attribute
    def update(self, value):
        self.__value.set(value)

    # Complete action
    # item_state: state item to read from
    def complete(self, item_state):
        # missing item in action: Try to find it.
        if self.__item is None:
            item = StateEngineTools.find_attribute(self._sh, item_state, "se_item_" + self._name)
            if item is not None:
                self.__item = self._abitem.return_item(item)

        if self.__mindelta.is_empty():
            mindelta = StateEngineTools.find_attribute(self._sh, item_state, "se_mindelta_" + self._name)
            if mindelta is not None:
                self.__mindelta.set(mindelta)

        if self.__item is not None:
            self.__value.set_cast(self.__item.cast)
            self.__mindelta.set_cast(self.__item.cast)
            self._scheduler_name = self.__item.property.path + "-SeItemDelayTimer"
            if self._abitem.id == self.__item.property.path:
                self.__caller += '_self'

    # Write action to logger
    def write_to_logger(self):
        SeActionBase.write_to_logger(self)
        if self.__item is not None:
            self._log_debug("item: {0}", self.__item.property.path)
        self.__mindelta.write_to_logger()
        self.__value.write_to_logger()

    # Check if execution is possible
    def _can_execute(self):
        if self.__item is None:
            self._log_info("Action '{0}': No item defined. Ignoring.", self._name)
            return False

        if self.__value.is_empty():
            self._log_info("Action '{0}': No value defined. Ignoring.", self._name)
            return False

        return True

    # Really execute the action (needs to be implemented in derived classes)
    def _execute(self, actionname: str, repeat_text: str = ""):
        value = self.__value.get()
        if value is None:
            return

        if not self.__mindelta.is_empty():
            mindelta = self.__mindelta.get()
            # noinspection PyCallingNonCallable
            delta = float(abs(self.__item() - value))
            if delta < mindelta:
                text = "{0}: Not setting '{1}' to '{2}' because delta '{3:.2}' is lower than mindelta '{4}'"
                self._log_debug(text, actionname, self.__item.property.path, value, delta, mindelta)
                return

        self._log_debug("{0}: Set '{1}' to '{2}'.{3}", actionname, self.__item.property.path, value, repeat_text)
        # noinspection PyCallingNonCallable
        self.__item(value, caller='{} {}'.format(StateEngineDefaults.plugin_identification, self._parent))


# Class representing a single "se_setbyattr" action
class SeActionSetByattr(SeActionBase):
    # Initialize the action
    # abitem: parent SeItem instance
    # name: Name of action
    def __init__(self, abitem, name: str):
        super().__init__(abitem, name)
        self.__byattr = None

    # set the action based on a set_(action_name) attribute
    # value: Value of the set_(action_name) attribute
    def update(self, value):
        self.__byattr = value

    # Complete action
    # item_state: state item to read from
    def complete(self, item_state):
        self._scheduler_name = self.__byattr + "-SeByAttrDelayTimer"

    # Write action to logger
    def write_to_logger(self):
        SeActionBase.write_to_logger(self)
        if self.__byattr is not None:
            self._log_debug("set by attriute: {0}", self.__byattr)

    # Really execute the action
    def _execute(self, actionname: str, repeat_text: str = ""):
        self._log_info("{0}: Setting values by attribute '{1}'.{2}", actionname, self.__byattr, repeat_text)
        for item in self.items.find_items(self.__byattr):
            self._log_info("\t{0} = {1}", item.property.path, item.conf[self.__byattr])
            item(item.conf[self.__byattr], caller='{} {}'.format(StateEngineDefaults.plugin_identification, self._parent))


# Class representing a single "se_trigger" action
class SeActionTrigger(SeActionBase):
    # Initialize the action
    # abitem: parent SeItem instance
    # name: Name of action
    def __init__(self, abitem, name: str):
        super().__init__(abitem, name)
        self.__logic = None
        self.__value = None

    # set the action based on a set_(action_name) attribute
    # value: Value of the set_(action_name) attribute
    def update(self, value):
        logic, value = StateEngineTools.partition_strip(value, ":")
        self.__logic = logic
        self.__value = None if value == "" else value

    # Complete action
    # item_state: state item to read from
    def complete(self, item_state):
        self._scheduler_name = self.__logic + "-SeLogicDelayTimer"

    # Write action to logger
    def write_to_logger(self):
        SeActionBase.write_to_logger(self)
        if self.__logic is not None:
            self._log_debug("trigger logic: {0}", self.__logic)
        if self.__value is not None:
            self._log_debug("value: {0}", self.__value)

    # Really execute the action
    def _execute(self, actionname: str, repeat_text: str = ""):
        # Trigger logic
        self._log_info("{0}: Triggering logic '{1}' using value '{2}'.{3}", actionname, self.__logic, self.__value, repeat_text)
        by = StateEngineDefaults.plugin_identification
        add_logics = 'logics.{}'.format(self.__logic) if not self.__logic.startswith('logics.') else self.__logic
        self._sh.trigger(add_logics, by=by, source=self._name, value=self.__value)


# Class representing a single "se_run" action
class SeActionRun(SeActionBase):
    # Initialize the action
    # abitem: parent SeItem instance
    # name: Name of action
    def __init__(self, abitem, name: str):
        super().__init__(abitem, name)
        self.__eval = None

    # set the action based on a set_(action_name) attribute
    # value: Value of the set_(action_name) attribute
    def update(self, value):
        func, value = StateEngineTools.partition_strip(value, ":")
        if value == "":
            value = func
            func = "eval"

        if func == "eval":
            self.__eval = value

    # Complete action
    # item_state: state item to read from
    def complete(self, item_state):
        self._scheduler_name = StateEngineTools.get_eval_name(self.__eval) + "-SeRunDelayTimer"

    # Write action to logger
    def write_to_logger(self):
        SeActionBase.write_to_logger(self)
        if self.__eval is not None:
            self._log_debug("eval: {0}", StateEngineTools.get_eval_name(self.__eval))

    # Really execute the action
    def _execute(self, actionname: str, repeat_text: str = ""):
        if isinstance(self.__eval, str):
            # noinspection PyUnusedLocal
            sh = self._sh
            if "stateengine_eval" in self.__eval or "se_eval" in self.__eval:
                # noinspection PyUnusedLocal
                stateengine_eval = se_eval = StateEngineEval.SeEval(self._abitem)
            try:
                eval(self.__eval)
            except Exception as ex:
                text = "{0}: Problem evaluating '{1}': {2}."
                self._log_error(text.format(actionname, StateEngineTools.get_eval_name(self.__eval), ex))
        else:
            try:
                # noinspection PyCallingNonCallable
                self.__eval()
            except Exception as ex:
                text = "{0}: Problem calling '{0}': {1}."
                self._log_error(text.format(actionname, StateEngineTools.get_eval_name(self.__eval), ex))


# Class representing a single "se_force" action
class SeActionForceItem(SeActionBase):
    # Initialize the action
    # abitem: parent SeItem instance
    # name: Name of action
    def __init__(self, abitem, name: str):
        super().__init__(abitem, name)
        self.__item = None
        self.__value = StateEngineValue.SeValue(self._abitem, "value")
        self.__mindelta = StateEngineValue.SeValue(self._abitem, "mindelta")

    # set the action based on a set_(action_name) attribute
    # value: Value of the set_(action_name) attribute
    def update(self, value):
        self.__value.set(value)

    # Complete action
    # item_state: state item to read from
    def complete(self, item_state):
        # missing item in action: Try to find it.
        if self.__item is None:
            item = StateEngineTools.find_attribute(self._sh, item_state, "se_item_" + self._name)
            if item is not None:
                self.__item = self._abitem.return_item(item)

        if self.__mindelta.is_empty():
            mindelta = StateEngineTools.find_attribute(self._sh, item_state, "se_mindelta_" + self._name)
            if mindelta is not None:
                self.__mindelta.set(mindelta)

        if self.__item is not None:
            self.__value.set_cast(self.__item.cast)
            self.__mindelta.set_cast(self.__item.cast)
            self._scheduler_name = self.__item.property.path + "-SeItemDelayTimer"

    # Write action to logger
    def write_to_logger(self):
        SeActionBase.write_to_logger(self)
        if self.__item is not None:
            self._log_debug("item: {0}", self.__item.property.path)
        self.__mindelta.write_to_logger()
        self.__value.write_to_logger()
        self._log_debug("force update: yes")

    # Check if execution is possible
    def _can_execute(self):
        if self.__item is None:
            self._log_info("Action '{0}': No item defined. Ignoring.", self._name)
            return False

        if self.__value.is_empty():
            self._log_info("Action '{0}': No value defined. Ignoring.", self._name)
            return False

        return True

    # Really execute the action (needs to be implemented in derived classes)
    # noinspection PyProtectedMember
    def _execute(self, actionname: str, repeat_text: str = ""):
        value = self.__value.get()
        if value is None:
            return

        if not self.__mindelta.is_empty():
            mindelta = self.__mindelta.get()
            # noinspection PyCallingNonCallable
            delta = float(abs(self.__item() - value))
            if delta < mindelta:
                text = "{0}: Not setting '{1}' to '{2}' because delta '{3:.2}' is lower than mindelta '{4}'"
                self._log_debug(text, actionname, self.__item.property.path, value, delta, mindelta)
                return

        # Set to different value first ("force")
        _caller = '{} {}'.format(StateEngineDefaults.plugin_identification, self._parent)
        if self.__item() == value:
            if self.__item._type == 'bool':
                self._log_debug("{0}: Set '{1}' to '{2}' (Force)", actionname, self.__item.property.path, not value)
                self.__item(not value, caller=_caller)
            elif self.__item._type == 'str':
                if value != '':
                    self._log_debug("{0}: Set '{1}' to '{2}' (Force)", actionname, self.__item.property.path, '')
                    self.__item('', caller=_caller)
                else:
                    self._log_debug("{0}: Set '{1}' to '{2}' (Force)", actionname, self.__item.property.path, '-')
                    self.__item('-', caller=_caller)
            elif self.__item._type == 'num':
                if value != 0:
                    self._log_debug("{0}: Set '{1}' to '{2}' (Force)", actionname, self.__item.property.path, 0)
                    self.__item(0, caller=_caller)
                else:
                    self._log_debug("{0}: Set '{1}' to '{2}' (Force)", actionname, self.__item.property.path, 1)
                    self.__item(1, caller=_caller)
            else:
                self._log_warning("{0}: Force not implemented for item type '{1}'", actionname, self.__item._type)
        else:
            self._log_debug("{0}: New value differs from old value, no force required.", actionname)

        self._log_debug("{0}: Set '{1}' to '{2}'.{3}", actionname, self.__item.property.path, value, repeat_text)
        # noinspection PyCallingNonCallable
        self.__item(value, caller=_caller)


# Class representing a single "se_special" action
class SeActionSpecial(SeActionBase):
    # Initialize the action
    # abitem: parent SeItem instance
    # name: Name of action
    def __init__(self, abitem, name: str):
        super().__init__(abitem, name)
        self.__special = None
        self.__value = None

    # set the action based on a set_(action_name) attribute
    # value: Value of the set_(action_name) attribute
    def update(self, value):
        special, value = StateEngineTools.partition_strip(value, ":")
        if special == "suspend":
            self.__value = self.suspend_get_value(value)
        else:
            raise ValueError("Action {0}: Unknown special value '{1}'!".format(self._name, special))
        self.__special = special

    # Complete action
    # item_state: state item to read from
    def complete(self, item_state):
        self._scheduler_name = self.__special + "-SeSpecialDelayTimer"

    # Write action to logger
    def write_to_logger(self):
        SeActionBase.write_to_logger(self)
        self._log_debug("Special Action: {0}", self.__special)
        if self.__value is not None:
            self._log_debug("value: {0}", self.__value)

    # Really execute the action
    def _execute(self, actionname: str, repeat_text: str = ""):
        # Trigger logic
        self._log_info("{0}: Executing special action '{1}' using value '{2}'.{3}", actionname, self.__special, self.__value, repeat_text)
        self._log_increase_indent()
        if self.__special == "suspend":
            self.suspend_execute()
        else:
            self._log_decrease_indent()
            raise ValueError("{0}: Unknown special value '{1}'!".format(actionname, self.__special))
        self._log_decrease_indent()

    def suspend_get_value(self, value):
        if value is None:
            raise ValueError("Action {0}: Special action 'suspend' requires arguments!", self._name)

        suspend, manual = StateEngineTools.partition_strip(value, ",")
        if suspend is None or manual is None:
            raise ValueError("Action {0}: Special action 'suspend' requires two arguments (separated by a comma)!", self._name)

        suspend_item = self._abitem.return_item(suspend)
        if suspend_item is None:
            raise ValueError("Action {0}: Suspend item '{1}' not found!", self._name, suspend)

        manual_item = self._abitem.return_item(manual)
        if manual_item is None:
            raise ValueError("Action {0}: Manual item '{1}' not found!", self._name, manual)

        return [suspend_item, manual_item.property.path]

    def suspend_execute(self):
        suspend_item = self.__value[0]
        if self._abitem.get_update_trigger_source() == self.__value[1]:
            # triggered by manual-item: Update suspend item
            if suspend_item():
                self._log_debug("Set '{0}' to '{1}' (Force)", suspend_item.property.path, False)
                suspend_item(False)
            self._log_debug("Set '{0}' to '{1}'.", suspend_item.property.path, True)
            suspend_item(True)
        else:
            self._log_debug("Leaving '{0}' untouched.", suspend_item.property.path)

        # determine remaining suspend time and write to variable item.suspend_remaining
        suspend_time = self._abitem.get_variable("item.suspend_time")
        suspend_over = suspend_item.age()
        suspend_remaining = int(suspend_time - suspend_over + 0.5)   # adding 0.5 causes round up ...
        self._abitem.set_variable("item.suspend_remaining", suspend_remaining)
        self._log_debug("Updated variable 'item.suspend_remaining' to {0}", suspend_remaining)
