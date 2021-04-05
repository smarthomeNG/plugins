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
import re


# Base class from which all action classes are derived
class SeActionBase(StateEngineTools.SeItemChild):
    @property
    def name(self):
        return self._name

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
        self._se_plugin = abitem.se_plugin
        self._parent = self._abitem.id
        self._caller = StateEngineDefaults.plugin_identification
        self.shtime = Shtime.get_instance()
        self.itemsApi = Items.get_instance()
        self._name = name
        self.__delay = StateEngineValue.SeValue(self._abitem, "delay")
        self.__repeat = None
        self.__instanteval = None
        self.conditionset = StateEngineValue.SeValue(self._abitem, "conditionset", True, "str")
        self.__mode = StateEngineValue.SeValue(self._abitem, "mode", True, "str")
        self.__order = StateEngineValue.SeValue(self._abitem, "order", False, "num")
        self._scheduler_name = None
        self.__function = None
        self.__template = None
        self._state = None
        self.__queue = abitem.queue

    def update_delay(self, value):
        self.__delay.set(value)
        self.__delay.set_cast(SeActionBase.__cast_delay)

    def update_instanteval(self, value):
        if self.__instanteval is None:
            self.__instanteval = StateEngineValue.SeValue(self._abitem, "instanteval", False, "bool")
        self.__instanteval.set(value)

    def update_repeat(self, value):
        if self.__repeat is None:
            self.__repeat = StateEngineValue.SeValue(self._abitem, "repeat", False, "bool")
        self.__repeat.set(value)

    def update_order(self, value):
        self.__order.set(value)

    def update_conditionsets(self, value):
        self.conditionset.set(value)

    def update_modes(self, value):
        self.__mode.set(value)

    def get_order(self):
        return self.__order.get(1)

    # Write action to logger
    def write_to_logger(self):
        self._log_debug("name: {}", self._name)
        self.__delay.write_to_logger()
        if self.__repeat is not None:
            self.__repeat.write_to_logger()
        if self.__instanteval is not None:
            self.__instanteval.write_to_logger()
        if self.conditionset is not None:
            self.conditionset.write_to_logger()
        if self.__mode is not None:
            self.__mode.write_to_logger()
        self.__order.write_to_logger()

    # Execute action (considering delay, etc)
    # is_repeat: Indicate if this is a repeated action without changing the state
    # item_allow_repeat: Is repeating actions generally allowed for the item?
    # state: state item that triggered the action
    def execute(self, is_repeat: bool, allow_item_repeat: bool, state):
        self._state = state
        if not self._can_execute():
            return
        condition_to_meet = None if self.conditionset.is_empty() else self.conditionset.get()
        condition_met = True if condition_to_meet is None else False
        condition_to_meet = condition_to_meet if isinstance(condition_to_meet, list) else [condition_to_meet]
        current_condition = self._abitem.get_lastconditionset_id()
        current_condition = self._abitem.get_laststate_id() if current_condition == '' else current_condition
        for cond in condition_to_meet:
            try:
                cond = re.compile(cond)
                matching = cond.fullmatch(current_condition)
                if matching:
                    self._log_debug("Given conditionset matches current one: {}", matching)
                    condition_met = True
            except Exception as ex:
                if cond is not None:
                    self._log_warning("Given conditionset {} is not a valid regex: {}", cond, ex)
        if condition_met is False:
            self._log_info("Action '{0}': Conditionset {1} not matching {2}. Skipping.",
                           self._name, condition_to_meet, current_condition)
            return

        if is_repeat:
            _key1 = ['{}'.format(state.id), 'actions_stay', '{}'.format(self._name), 'repeat']
            _key2 = ['{}'.format(state.id), 'actions_enter_or_stay', '{}'.format(self._name), 'repeat']
            if self.__repeat is None:
                if allow_item_repeat:
                    repeat_text = " Repeat allowed by item configuration."
                    result = self._abitem.update_webif(_key1, True)
                    if result is False:
                        self._abitem.update_webif(_key2, True)
                else:
                    self._log_info("Action '{0}': Repeat denied by item configuration.", self._name)
                    result = self._abitem.update_webif(_key1, False)
                    if result is False:
                        self._abitem.update_webif(_key2, False)
                    return
            elif self.__repeat.get():
                repeat_text = " Repeat allowed by action configuration."
                result = self._abitem.update_webif(_key1, True)
                if result is False:
                    self._abitem.update_webif(_key2, True)
            else:
                self._log_info("Action '{0}': Repeat denied by action configuration.", self._name)
                result = self._abitem.update_webif(_key1, False)
                if result is False:
                    self._abitem.update_webif(_key2, False)
                return
        else:
            repeat_text = ""

        try:
            self._getitem_fromeval()
            _validitem = True
        except Exception as ex:
            _validitem = False
            self._log_error("Action '{0}': Ignored because {1}", self._name, ex)
        if _validitem:
            plan_next = self._se_plugin.scheduler_return_next(self._scheduler_name)
            if plan_next is not None and plan_next > self.shtime.now():
                self._log_info("Action '{0}: Removing previous delay timer '{1}'.", self._name, self._scheduler_name)
                self._se_plugin.scheduler_remove(self._scheduler_name)
                try:
                    self._abitem.remove_scheduler_entry(self._scheduler_name)
                except Exception:
                    pass

            delay = 0 if self.__delay.is_empty() else self.__delay.get()
            actionname = "Action '{0}'".format(self._name) if delay == 0 else "Delayed Action ({0} seconds) '{1}'".format(
                delay, self._scheduler_name)
            _delay_info = 0
            if delay is None:
                self._log_warning("Action'{0}: Ignored because of errors while determining the delay!", self._name)
                _delay_info = -1
            elif delay < 0:
                self._log_warning("Action'{0}: Ignored because of delay is negative!", self._name)
                _delay_info = -1
            else:
                self._waitforexecute(actionname, self._name, repeat_text, delay, current_condition)

            try:
                _key = ['{}'.format(state.id), 'actions_stay', '{}'.format(self._name), 'delay']
                self._abitem.update_webif(_key, _delay_info)
            except Exception:
                pass
            try:
                _key = ['{}'.format(state.id), 'actions_enter', '{}'.format(self._name), 'delay']
                self._abitem.update_webif(_key, _delay_info)
            except Exception:
                pass
            try:
                _key = ['{}'.format(state.id), 'actions_enter_or_stay', '{}'.format(self._name), 'delay']
                self._abitem.update_webif(_key, _delay_info)
            except Exception:
                pass
            try:
                state.update_name(state.state_item)
                _key_name = ['{}'.format(state.id), 'name']
                self.update_webif(_key_name, state.name)
                _key = ['{}'.format(state.id), 'actions_leave', '{}'.format(self._name), 'delay']
                self._abitem.update_webif(_key, _delay_info)
            except Exception:
                pass

    # set the action based on a set_(action_name) attribute
    # value: Value of the set_(action_name) attribute
    def update(self, value):
        raise NotImplementedError("Class {} doesn't implement update()".format(self.__class__.__name__))

    # Complete action
    # item_state: state item to read from
    def complete(self, item_state, evals_items=None):
        raise NotImplementedError("Class {} doesn't implement complete()".format(self.__class__.__name__))

    # Check if execution is possible
    def _can_execute(self):
        return True

    def get(self):
        return True

    def _waitforexecute(self, actionname: str, namevar: str = "", repeat_text: str = "", delay: int = 0, current_condition: str = ""):
        self._log_decrease_indent(50)
        self._log_increase_indent()
        if delay == 0:
            self._log_info("Running action '{}'.", namevar)
            self.real_execute(actionname, namevar, repeat_text, None, False, current_condition)
        else:
            instanteval = None if self.__instanteval is None else self.__instanteval.get()
            self._log_info("Action '{0}': Add {1} second timer '{2}' "
                           "for delayed execution.{3} Instant Eval: {4}", self._name, delay,
                           self._scheduler_name, repeat_text, instanteval)
            next_run = self.shtime.now() + datetime.timedelta(seconds=delay)
            if instanteval is True:
                self._log_increase_indent()
                self._log_debug("Evaluating value for delayed action '{}'.", namevar)
                value = self.real_execute(actionname, namevar, repeat_text, None, True, current_condition)
                self._log_debug("Value for delayed action is going to be '{}'.", value)
                self._log_decrease_indent()
            else:
                value = None
            self._abitem.add_scheduler_entry(self._scheduler_name)
            self._se_plugin.scheduler_add(self._scheduler_name, self._delayed_execute,
                                          value={'actionname': actionname, 'namevar': self._name,
                                                 'repeat_text': repeat_text, 'value': value,
                                                 'current_condition': current_condition}, next=next_run)

    def _delayed_execute(self, actionname: str, namevar: str = "", repeat_text: str = "", value=None, current_condition=None):
        self._log_debug("Putting delayed action '{}' into queue.", namevar)
        self.__queue.put(["delayedaction", self, actionname, namevar, repeat_text, value, current_condition])
        if not self._abitem.update_lock.locked():
            self._log_debug("Running queue")
            self._abitem.run_queue()

    # Really execute the action (needs to be implemented in derived classes)
    def real_execute(self, actionname: str, namevar: str = "", repeat_text: str = "", value=None, returnvalue=False, current_condition=None):
        raise NotImplementedError("Class {} doesn't implement real_execute()".format(self.__class__.__name__))

    def _getitem_fromeval(self):
        return


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
        self.__function = "set"

    def __repr__(self):
        return "SeAction Set {}".format(self._name)

    def _getitem_fromeval(self):
        if isinstance(self.__item, str):
            item = None
            if "stateengine_eval" in self.__item or "se_eval" in self.__item:
                # noinspection PyUnusedLocal
                stateengine_eval = se_eval = StateEngineEval.SeEval(self._abitem)
            try:
                item = self.__item.replace('sh', 'self._sh')
                item = item.replace('shtime', 'self._shtime')
                item = eval(item)
                if item is not None:
                    self.__item = self._abitem.return_item(item)
                    self.__value.set_cast(self.__item.cast)
                    self.__mindelta.set_cast(self.__item.cast)
                    self._scheduler_name = "{}-SeItemDelayTimer".format(self.__item.property.path)
                    if self._abitem.id == self.__item.property.path:
                        self._caller += '_self'
            except Exception as ex:
                raise Exception("Problem evaluating item '{}' from eval: {}".format(self.__item, ex))
            if item is None:
                raise Exception("Problem evaluating item '{}' from eval. It does not exist.".format(self.__item))

    # set the action based on a set_(action_name) attribute
    # value: Value of the set_(action_name) attribute
    def update(self, value):
        self.__value.set(value)

    # Complete action
    # item_state: state item to read from
    def complete(self, item_state, evals_items=None):
        try:
            _name = evals_items.get(self.name)
            if _name is not None:
                _item = _name.get('item')
                _eval = str(_name.get('eval'))
                _selfitem = self.__item if self.__item is not None and self.__item != "None" else None
                _item = _item if _item is not None and _item != "None" else None
                _eval = _eval if _eval is not None and _eval != "None" else None
                self.__item = _selfitem or self._abitem.return_item(_item) or _eval
        except Exception as ex:
            self._log_error("No valid item info for action {}, trying to get differently. Problem: {}", self.name, ex)
        # missing item in action: Try to find it.
        if self.__item is None:
            item = StateEngineTools.find_attribute(self._sh, item_state, "se_item_" + self._name)

            if item is not None:
                self.__item = self._abitem.return_item(item)
            else:
                item = StateEngineTools.find_attribute(self._sh, item_state, "se_eval_" + self._name)
                self.__item = str(item)

        if self.__mindelta.is_empty():
            mindelta = StateEngineTools.find_attribute(self._sh, item_state, "se_mindelta_" + self._name)
            if mindelta is not None:
                self.__mindelta.set(mindelta)

        if isinstance(self.__item, str):
            pass
        elif self.__item is not None:
            self.__value.set_cast(self.__item.cast)
            self.__mindelta.set_cast(self.__item.cast)
            self._scheduler_name = "{}-SeItemDelayTimer".format(self.__item.property.path)
            if self._abitem.id == self.__item.property.path:
                self._caller += '_self'

    # Write action to logger
    def write_to_logger(self):
        SeActionBase.write_to_logger(self)
        if isinstance(self.__item, str):
            self._log_debug("item from eval: {0}", self.__item)
        elif self.__item is not None:
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
    def real_execute(self, actionname: str, namevar: str = "", repeat_text: str = "", value=None, returnvalue=False, current_condition=None):
        self._abitem.set_variable('current.action_name', namevar)
        self._log_increase_indent()
        if value is None:
            value = self.__value.get()

        if value is None:
            self._log_debug("{0}: Value is None", actionname)
            return

        if returnvalue:
            self._log_decrease_indent()
            return value

        if not self.__mindelta.is_empty():
            mindelta = self.__mindelta.get()
            # noinspection PyCallingNonCallable
            delta = float(abs(self.__item() - value))
            if delta < mindelta:
                text = "{0}: Not setting '{1}' to '{2}' because delta '{3:.2}' is lower than mindelta '{4}'"
                self._log_debug(text, actionname, self.__item.property.path, value, delta, mindelta)
                return

        self._execute_set_add_remove(actionname, namevar, repeat_text, self.__item, value, current_condition)

    def _execute_set_add_remove(self, actionname, namevar, repeat_text, item, value, current_condition):
        self._log_decrease_indent()
        self._log_debug("{0}: Set '{1}' to '{2}'{3}", actionname, item.property.path, value, repeat_text)
        source = self._parent if current_condition is None else current_condition
        # noinspection PyCallingNonCallable
        item(value, caller=self._caller, source=source)

    def get(self):
        try:
            item = str(self.__item.property.path)
        except Exception:
            item = str(self.__item)
        return {'function': str(self.__function), 'item': item,
                'value': str(self.__value.get()), 'conditionset': str(self.conditionset.get())}


# Class representing a single "se_setbyattr" action
class SeActionSetByattr(SeActionBase):
    # Initialize the action
    # abitem: parent SeItem instance
    # name: Name of action
    def __init__(self, abitem, name: str):
        super().__init__(abitem, name)
        self.__byattr = None
        self.__function = "set by attribute"

    def __repr__(self):
        return "SeAction SetByAttr {}".format(self._name)

    # set the action based on a set_(action_name) attribute
    # value: Value of the set_(action_name) attribute
    def update(self, value):
        self.__byattr = value

    # Complete action
    # item_state: state item to read from
    def complete(self, item_state, evals_items=None):
        self._scheduler_name = "{}-SeByAttrDelayTimer".format(self.__byattr)

    # Write action to logger
    def write_to_logger(self):
        self._log_debug("function: {}", self.__function)
        SeActionBase.write_to_logger(self)
        if self.__byattr is not None:
            self._log_debug("set by attribute: {0}", self.__byattr)

    # Really execute the action
    def real_execute(self, actionname: str, namevar: str = "", repeat_text: str = "", value=None, returnvalue=False, current_condition=None):
        self._abitem.set_variable('current.action_name', namevar)
        if returnvalue:
            return value
        self._log_info("{0}: Setting values by attribute '{1}'.{2}", actionname, self.__byattr, repeat_text)
        source = self._parent if current_condition is None else current_condition
        for item in self.itemsApi.find_items(self.__byattr):
            self._log_info("\t{0} = {1}", item.property.path, item.conf[self.__byattr])
            item(item.conf[self.__byattr], caller=self._caller, source=source)

    def get(self):
        return {'function': str(self.__function), 'byattr': str(self.__byattr), 'conditionset': str(self.conditionset.get())}


# Class representing a single "se_trigger" action
class SeActionTrigger(SeActionBase):
    # Initialize the action
    # abitem: parent SeItem instance
    # name: Name of action
    def __init__(self, abitem, name: str):
        super().__init__(abitem, name)
        self.__logic = None
        self.__value = StateEngineValue.SeValue(self._abitem, "value")
        self.__function = "trigger"

    def __repr__(self):
        return "SeAction Trigger {}".format(self._name)

    # set the action based on a set_(action_name) attribute
    # value: Value of the set_(action_name) attribute
    def update(self, value):
        logic, value = StateEngineTools.partition_strip(value, ":")
        self.__logic = logic
        value = None if value == "" else value
        self.__value.set(value)

    # Complete action
    # item_state: state item to read from
    def complete(self, item_state, evals_items=None):
        self._scheduler_name = "{}-SeLogicDelayTimer".format(self.__logic)

    # Write action to logger
    def write_to_logger(self):
        self._log_debug("function: {}", self.__function)
        SeActionBase.write_to_logger(self)
        if self.__logic is not None:
            self._log_debug("trigger logic: {0}", self.__logic)
        if self.__value is not None:
            self._log_debug("value: {0}", self.__value)

    # Really execute the action
    def real_execute(self, actionname: str, namevar: str = "", repeat_text: str = "", value=None, returnvalue=False, current_condition=None):
        self._abitem.set_variable('current.action_name', namevar)
        if value is None:
            try:
                value = self.__value.get()
            except Exception:
                value = self.__value

        if returnvalue:
            return value
        self._log_info("{0}: Triggering logic '{1}' using value '{2}'.{3}", actionname, self.__logic, value, repeat_text)
        add_logics = 'logics.{}'.format(self.__logic) if not self.__logic.startswith('logics.') else self.__logic
        self._sh.trigger(add_logics, by=self._caller, source=self._name, value=value)

    def get(self):
        return {'function': str(self.__function), 'logic': str(self.__logic),
                'value': str(self.__value.get()), 'conditionset': str(self.conditionset.get())}


# Class representing a single "se_run" action
class SeActionRun(SeActionBase):
    # Initialize the action
    # abitem: parent SeItem instance
    # name: Name of action
    def __init__(self, abitem, name: str):
        super().__init__(abitem, name)
        self.__eval = None
        self.__function = "run"

    def __repr__(self):
        return "SeAction Run {}".format(self._name)

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
    def complete(self, item_state, evals_items=None):
        self._scheduler_name = "{}-SeRunDelayTimer".format(StateEngineTools.get_eval_name(self.__eval))

    # Write action to logger
    def write_to_logger(self):
        self._log_debug("function: {}", self.__function)
        SeActionBase.write_to_logger(self)
        if self.__eval is not None:
            self._log_debug("eval: {0}", StateEngineTools.get_eval_name(self.__eval))

    # Really execute the action
    def real_execute(self, actionname: str, namevar: str = "", repeat_text: str = "", value=None, returnvalue=False, current_condition=None):
        self._abitem.set_variable('current.action_name', namevar)
        self._log_increase_indent()
        if isinstance(self.__eval, str):
            # noinspection PyUnusedLocal
            sh = self._sh
            shtime = self._shtime
            if "stateengine_eval" in self.__eval or "se_eval" in self.__eval:
                # noinspection PyUnusedLocal
                stateengine_eval = se_eval = StateEngineEval.SeEval(self._abitem)
            try:
                if returnvalue:
                    self._log_decrease_indent()
                    return eval(self.__eval)
                self._log_debug("Running eval {0} based on conditionset {1}", self.__eval, current_condition)
                eval(self.__eval)
                self._log_decrease_indent()
            except Exception as ex:
                self._log_decrease_indent()
                text = "{0}: Problem evaluating '{1}': {2}."
                self._log_error(text.format(actionname, StateEngineTools.get_eval_name(self.__eval), ex))
        else:
            try:
                if returnvalue:
                    self._log_decrease_indent()
                    return self.__eval()
                self._log_debug("Running eval {0} based on conditionset {1}", self.__eval, current_condition)
                self.__eval()
                self._log_decrease_indent()
            except Exception as ex:
                self._log_decrease_indent()
                text = "{0}: Problem calling '{0}': {1}."
                self._log_error(text.format(actionname, StateEngineTools.get_eval_name(self.__eval), ex))

    def get(self):
        return {'function': str(self.__function), 'eval': str(self.__eval),
                'conditionset': str(self.conditionset.get())}


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
        self.__function = "force set"

    def __repr__(self):
        return "SeAction Force {}".format(self._name)

    # set the action based on a set_(action_name) attribute
    # value: Value of the set_(action_name) attribute
    def update(self, value):
        self.__value.set(value)

    # Complete action
    # item_state: state item to read from
    def complete(self, item_state, evals_items=None):
        # missing item in action: Try to find it.
        if self.__item is None:
            item = StateEngineTools.find_attribute(self._sh, item_state, "se_item_" + self._name)
            if item is not None:
                self.__item = self._abitem.return_item(item)
            else:
                item = StateEngineTools.find_attribute(self._sh, item_state, "se_eval_" + self._name)
                self.__item = str(item)

        if self.__mindelta.is_empty():
            mindelta = StateEngineTools.find_attribute(self._sh, item_state, "se_mindelta_" + self._name)
            if mindelta is not None:
                self.__mindelta.set(mindelta)

        if isinstance(self.__item, str):
            pass
        elif self.__item is not None:
            self.__value.set_cast(self.__item.cast)
            self.__mindelta.set_cast(self.__item.cast)
            self._scheduler_name = "{}-SeItemDelayTimer".format(self.__item.property.path)

    # Write action to logger
    def write_to_logger(self):
        self._log_debug("function: {}", self.__function)
        self._log_debug("value: {}", self.__value)
        SeActionBase.write_to_logger(self)
        if isinstance(self.__item, str):
            self._log_debug("item from eval: {0}", self.__item)
        elif self.__item is not None:
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

    def _getitem_fromeval(self):
        if isinstance(self.__item, str):
            if "stateengine_eval" in self.__item or "se_eval" in self.__item:
                # noinspection PyUnusedLocal
                stateengine_eval = se_eval = StateEngineEval.SeEval(self._abitem)
            try:
                item = self.__item.replace('sh', 'self._sh')
                item = item.replace('shtime', 'self._shtime')
                item = eval(item)
                if item is not None:
                    self.__item = self._abitem.return_item(item)
                    self.__value.set_cast(self.__item.cast)
                    self.__mindelta.set_cast(self.__item.cast)
                    self._scheduler_name = "{}-SeItemDelayTimer".format(self.__item.property.path)
                    if self._abitem.id == self.__item.property.path:
                        self._caller += '_self'
                else:
                    self._log_error("Problem evaluating item '{}' from eval. It is None.", item)
                    return
            except Exception as ex:
                self._log_error("Problem evaluating item '{}' from eval: {}.", self.__item, ex)
                return

    # Really execute the action (needs to be implemented in derived classes)
    # noinspection PyProtectedMember
    def real_execute(self, actionname: str, namevar: str = "", repeat_text: str = "", value=None, returnvalue=False, current_condition=None):
        self._abitem.set_variable('current.action_name', namevar)
        self._log_increase_indent()
        if value is None:
            value = self.__value.get()

        if value is None:
            self._log_debug("{0}: Value is None", actionname)
            return

        if returnvalue:
            self._log_decrease_indent()
            return value

        if not self.__mindelta.is_empty():
            mindelta = self.__mindelta.get()
            # noinspection PyCallingNonCallable
            delta = float(abs(self.__item() - value))
            if delta < mindelta:
                text = "{0}: Not setting '{1}' to '{2}' because delta '{3:.2}' is lower than mindelta '{4}'"
                self._log_debug(text, actionname, self.__item.property.path, value, delta, mindelta)
                return

        # Set to different value first ("force")
        source = self._parent if current_condition is None else current_condition
        if self.__item() == value:
            if self.__item._type == 'bool':
                self._log_debug("{0}: Set '{1}' to '{2}' (Force)", actionname, self.__item.property.path, not value)
                self.__item(not value, caller=self._caller, source=source)
            elif self.__item._type == 'str':
                if value != '':
                    self._log_debug("{0}: Set '{1}' to '{2}' (Force)", actionname, self.__item.property.path, '')
                    self.__item('', caller=self._caller, source=source)
                else:
                    self._log_debug("{0}: Set '{1}' to '{2}' (Force)", actionname, self.__item.property.path, '-')
                    self.__item('-', caller=self._caller, source=source)
            elif self.__item._type == 'num':
                if value != 0:
                    self._log_debug("{0}: Set '{1}' to '{2}' (Force)", actionname, self.__item.property.path, 0)
                    self.__item(0, caller=self._caller, source=source)
                else:
                    self._log_debug("{0}: Set '{1}' to '{2}' (Force)", actionname, self.__item.property.path, 1)
                    self.__item(1, caller=self._caller, source=source)
            else:
                self._log_warning("{0}: Force not implemented for item type '{1}'", actionname, self.__item._type)
        else:
            self._log_debug("{0}: New value differs from old value, no force required.", actionname)
        self._log_decrease_indent()
        self._log_debug("{0}: Set '{1}' to '{2}'.{3}", actionname, self.__item.property.path, value, repeat_text)
        # noinspection PyCallingNonCallable
        self.__item(value, caller=self._caller, source=source)

    def get(self):
        try:
            item = str(self.__item.property.path)
        except Exception:
            item = str(self.__item)
        return {'function': str(self.__function), 'item': item, 'value': str(self.__value.get()),
                'conditionset': str(self.conditionset.get())}


# Class representing a single "se_special" action
class SeActionSpecial(SeActionBase):
    # Initialize the action
    # abitem: parent SeItem instance
    # name: Name of action
    def __init__(self, abitem, name: str):
        super().__init__(abitem, name)
        self.__special = None
        self.__value = None
        self.__function = "special"

    def __repr__(self):
        return "SeAction Special {}".format(self._name)

    # set the action based on a set_(action_name) attribute
    # value: Value of the set_(action_name) attribute
    def update(self, value):
        special, value = StateEngineTools.partition_strip(value, ":")
        if special == "suspend":
            self.__value = self.suspend_get_value(value)
        elif special == "retrigger":
            self.__value = self.retrigger_get_value(value)
        else:
            raise ValueError("Action {0}: Unknown special value '{1}'!".format(self._name, special))
        self.__special = special

    # Complete action
    # item_state: state item to read from
    def complete(self, item_state, evals_items=None):
        if isinstance(self.__value, list):
            item = self.__value[0].property.path
        else:
            item = self.__value.property.path
        self._scheduler_name = "{}_{}-SeSpecialDelayTimer".format(self.__special, item)

    # Write action to logger
    def write_to_logger(self):
        self._log_debug("function: {}", self.__function)
        SeActionBase.write_to_logger(self)
        self._log_debug("Special Action: {0}", self.__special)
        if isinstance(self.__value, list):
            self._log_debug("value: {0}", self.__value)
        else:
            self._log_debug("Retrigger item: {0}", self.__value.property.path)

    # Really execute the action
    def real_execute(self, actionname: str, namevar: str = "", repeat_text: str = "", value=None, returnvalue=False, current_condition=None):
        self._abitem.set_variable('current.action_name', namevar)
        if returnvalue:
            return None
        try:
            _log_value = self.__value.property.path
        except Exception:
            _log_value = self.__value
        self._log_info("{0}: Executing special action '{1}' using item '{2}' based on '{3}'.{4}",
                       actionname, self.__special, _log_value, current_condition, repeat_text)
        self._log_increase_indent()
        if self.__special == "suspend":
            self.suspend_execute(current_condition)
            self._log_decrease_indent()
        elif self.__special == "retrigger":
            # noinspection PyCallingNonCallable
            self._abitem.update_state(self.__value, self._caller)
            #self.__value(True, caller=self._caller)
            self._log_decrease_indent()
        else:
            self._log_decrease_indent()
            raise ValueError("{0}: Unknown special value '{1}'!".format(actionname, self.__special))
        self._log_debug("Special action {0}: done", self.__special)

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

    def retrigger_get_value(self, value):
        if value is None:
            raise ValueError("Action {0}: Special action 'retrigger' requires item", self._name)

        se_item, __ = StateEngineTools.partition_strip(value, ",")

        se_item = self._abitem.return_item(se_item)
        if se_item is None:
            raise ValueError("Action {0}: Retrigger item '{1}' not found!", self._name, se_item)
        return se_item

    def suspend_execute(self, current_condition=None):
        suspend_item = self._abitem.return_item(self.__value[0])
        source = "SuspendAction, {}".format(self._parent if current_condition is None else current_condition)
        if self._abitem.get_update_trigger_source() == self.__value[1]:
            # triggered by manual-item: Update suspend item
            if suspend_item.property.value:
                self._log_debug("Set '{0}' to '{1}' (Force)", suspend_item.property.path, False)
                suspend_item(False, caller=self._caller, source=source)
            self._log_debug("Set '{0}' to '{1}'.", suspend_item.property.path, True)
            suspend_item(True, caller=self._caller, source=source)
        else:
            self._log_debug("Leaving '{0}' untouched.", suspend_item.property.path)

        # determine remaining suspend time and write to variable item.suspend_remaining
        suspend_time = self._abitem.get_variable("item.suspend_time")
        suspend_over = suspend_item.property.last_change_age
        suspend_remaining = int(suspend_time - suspend_over + 0.5)   # adding 0.5 causes round up ...
        self._abitem.set_variable("item.suspend_remaining", suspend_remaining)
        self._log_debug("Updated variable 'item.suspend_remaining' to {0}", suspend_remaining)

    def get(self):
        try:
            value_result = self.__value.property.path
        except Exception:
            value_result = self.__value
        if isinstance(value_result, list):
            for i, val in enumerate(value_result):
                try:
                    value_result[i] = val.property.path
                except Exception:
                    pass
        return {'function': str(self.__function), 'special': str(self.__special),
                'value': str(value_result), 'conditionset': str(self.conditionset.get())}


# Class representing a single "se_add" action
class SeActionAddItem(SeActionSetItem):
    # Initialize the action
    # abitem: parent SeItem instance
    # name: Name of action
    def __init__(self, abitem, name: str):
        super().__init__(abitem, name)
        self.__function = "add to list"

    def __repr__(self):
        return "SeAction Add {}".format(self._name)

    def write_to_logger(self):
        self._log_debug("function: {}", self.__function)
        SeActionSetItem.write_to_logger(self)
        SeActionBase.write_to_logger(self)

    def _execute_set_add_remove(self, actionname, namevar, repeat_text, item, value, current_condition=None):
        value = value if isinstance(value, list) else [value]
        self._log_debug("{0}: Add '{1}' to '{2}'.{3}", actionname, value, item.property.path, repeat_text)
        value = item.property.value + value
        source = self._parent if current_condition is None else current_condition
        # noinspection PyCallingNonCallable
        item(value, caller=self._caller, source=source)

    def get(self):
        try:
            item = str(self.__item.property.path)
        except Exception:
            item = str(self.__item)
        return {'function': str(self.__function), 'item': item,
                'value': str(self.__value.get()), 'conditionset': str(self.conditionset.get())}


# Class representing a single "se_remove" action
class SeActionRemoveFirstItem(SeActionSetItem):
    # Initialize the action
    # abitem: parent SeItem instance
    # name: Name of action
    def __init__(self, abitem, name: str):
        super().__init__(abitem, name)
        self.__function = "remove first from list"

    def __repr__(self):
        return "SeAction RemoveFirst {}".format(self._name)

    def write_to_logger(self):
        self._log_debug("function: {}", self.__function)
        SeActionSetItem.write_to_logger(self)
        SeActionBase.write_to_logger(self)

    def _execute_set_add_remove(self, actionname, namevar, repeat_text, item, value, current_condition=None):
        currentvalue = item.property.value
        value = value if isinstance(value, list) else [value]
        for v in value:
            try:
                currentvalue.remove(v)
                self._log_debug("{0}: Remove first entry '{1}' from '{2}'.{3}",
                                actionname, v, item.property.path, repeat_text)
            except Exception as ex:
                self._log_warning("{0}: Remove first entry '{1}' from '{2}' failed: {3}",
                                  actionname, value, item.property.path, ex)
        source = self._parent if current_condition is None else current_condition
        item(currentvalue, caller=self._caller, source=source)

    def get(self):
        try:
            item = str(self.__item.property.path)
        except Exception:
            item = str(self.__item)
        return {'function': str(self.__function), 'item': item,
                'value': str(self.__value.get()), 'conditionset': str(self.conditionset.get())}


# Class representing a single "se_remove" action
class SeActionRemoveLastItem(SeActionSetItem):
    # Initialize the action
    # abitem: parent SeItem instance
    # name: Name of action
    def __init__(self, abitem, name: str):
        super().__init__(abitem, name)
        self.__function = "remove last from list"

    def __repr__(self):
        return "SeAction RemoveLast {}".format(self._name)

    def write_to_logger(self):
        self._log_debug("function: {}", self.__function)
        SeActionSetItem.write_to_logger(self)
        SeActionBase.write_to_logger(self)

    def _execute_set_add_remove(self, actionname, namevar, repeat_text, item, value, current_condition=None):
        currentvalue = item.property.value
        value = value if isinstance(value, list) else [value]
        for v in value:
            try:
                currentvalue.reverse()
                currentvalue.remove(v)
                currentvalue.reverse()
                self._log_debug("{0}: Remove last entry '{1}' from '{2}'.{3}",
                                actionname, v, item.property.path, repeat_text)
            except Exception as ex:
                self._log_warning("{0}: Remove last entry '{1}' from '{2}' failed: {3}",
                                  actionname, value, item.property.path, ex)
        source = self._parent if current_condition is None else current_condition
        item(currentvalue, caller=self._caller, source=source)

    def get(self):
        try:
            item = str(self.__item.property.path)
        except Exception:
            item = str(self.__item)
        return {'function': str(self.__function), 'item': item,
                'value': str(self.__value.get()), 'conditionset': str(self.conditionset.get())}


# Class representing a single "se_removeall" action
class SeActionRemoveAllItem(SeActionSetItem):
    # Initialize the action
    # abitem: parent SeItem instance
    # name: Name of action
    def __init__(self, abitem, name: str):
        super().__init__(abitem, name)
        self.__function = "remove all from list"

    def __repr__(self):
        return "SeAction RemoveAll {}".format(self._name)

    def write_to_logger(self):
        self._log_debug("function: {}", self.__function)
        SeActionSetItem.write_to_logger(self)
        SeActionBase.write_to_logger(self)

    def _execute_set_add_remove(self, actionname, namevar, repeat_text, item, value, current_condition=None):
        currentvalue = item.property.value
        value = value if isinstance(value, list) else [value]
        for v in value:
            try:
                currentvalue = [i for i in currentvalue if i != v]
                self._log_debug("{0}: Remove all '{1}' from '{2}'.{3}",
                                actionname, v, item.property.path, repeat_text)
            except Exception as ex:
                self._log_warning("{0}: Remove all '{1}' from '{2}' failed: {3}",
                                  actionname, value, item.property.path, ex)
        source = self._parent if current_condition is None else current_condition
        item(currentvalue, caller=self._caller, source=source)

    def get(self):
        try:
            item = str(self.__item.property.path)
        except Exception:
            item = str(self.__item)
        return {'function': str(self.__function), 'item': item,
                'value': str(self.__value.get()), 'conditionset': str(self.conditionset.get())}
