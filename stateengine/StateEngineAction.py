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

    @property
    def function(self):
        return self._function

    @property
    def action_status(self):
        return self._action_status

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
        self.previousconditionset = StateEngineValue.SeValue(self._abitem, "previousconditionset", True, "str")
        self.previousstate_conditionset = StateEngineValue.SeValue(self._abitem, "previousstate_conditionset", True, "str")
        self.__mode = StateEngineValue.SeValue(self._abitem, "mode", True, "str")
        self.__order = StateEngineValue.SeValue(self._abitem, "order", False, "num")
        self._scheduler_name = None
        self._function = None
        self.__template = None
        self._action_status = {}
        self._retrigger_issue = None
        self._suspend_issue = None
        self.__queue = abitem.queue

    def update_delay(self, value):
        _issue_list = []
        _, _, _issue = self.__delay.set(value)
        if _issue:
            _issue = {self._name: {'issue': _issue, 'attribute': 'delay',
                                   'issueorigin': [{'state': 'unknown', 'action': self._function}]}}
            _issue_list.append(_issue)
        _issue = self.__delay.set_cast(SeActionBase.__cast_delay)
        if _issue:
            _issue = {self._name: {'issue': _issue, 'attribute': 'delay',
                                   'issueorigin': [{'state': 'unknown', 'action': self._function}]}}
            _issue_list.append(_issue)
        _issue_list = StateEngineTools.flatten_list(_issue_list)
        return _issue_list

    def update_instanteval(self, value):
        if self.__instanteval is None:
            self.__instanteval = StateEngineValue.SeValue(self._abitem, "instanteval", False, "bool")
        _, _, _issue = self.__instanteval.set(value)
        _issue = {self._name: {'issue': _issue, 'attribute': 'instanteval',
                               'issueorigin': [{'state': 'unknown', 'action': self._function}]}}
        return _issue

    def update_repeat(self, value):
        if self.__repeat is None:
            self.__repeat = StateEngineValue.SeValue(self._abitem, "repeat", False, "bool")
        _, _, _issue = self.__repeat.set(value)
        _issue = {self._name: {'issue': _issue, 'attribute': 'repeat',
                               'issueorigin': [{'state': 'unknown', 'action': self._function}]}}
        return _issue

    def update_order(self, value):
        _, _, _issue = self.__order.set(value)
        _issue = {self._name: {'issue': _issue, 'attribute': 'order',
                               'issueorigin': [{'state': 'unknown', 'action': self._function}]}}
        return _issue

    def update_conditionset(self, value):
        _, _, _issue = self.conditionset.set(value)
        _issue = {self._name: {'issue': _issue, 'attribute': 'conditionset',
                               'issueorigin': [{'state': 'unknown', 'action': self._function}]}}
        return _issue

    def update_previousconditionset(self, value):
        _, _, _issue = self.previousconditionset.set(value)
        _issue = {self._name: {'issue': _issue, 'attribute': 'previousconditionset',
                               'issueorigin': [{'state': 'unknown', 'action': self._function}]}}
        return _issue

    def update_previousstate_conditionset(self, value):
        _, _, _issue = self.previousstate_conditionset.set(value)
        _issue = {self._name: {'issue': _issue, 'attribute': 'previousstate_conditionset',
                               'issueorigin': [{'state': 'unknown', 'action': self._function}]}}
        return _issue

    def update_mode(self, value):
        _value, _, _issue = self.__mode.set(value)
        _issue = {self._name: {'issue': _issue, 'attribute': 'mode',
                               'issueorigin': [{'state': 'unknown', 'action': self._function}]}}
        return _value[0], _issue

    def get_order(self):
        order = self.__order.get(1)
        if not isinstance(order, int):
            self._log_warning("Order is currently {} but must be an integer. Setting it to 1.", order)
            order = 1
        return order

    def update_webif_actionstatus(self, state, name, success, issue=None):
        try:
            if self._abitem.webif_infos[state.id].get('actions_stay'):
                _key = ['{}'.format(state.id), 'actions_stay', '{}'.format(name), 'actionstatus', 'success']
                self._abitem.update_webif(_key, success)
                _key = ['{}'.format(state.id), 'actions_stay', '{}'.format(name), 'actionstatus', 'issue']
                self._abitem.update_webif(_key, issue)
        except Exception:
            pass
        try:
            if self._abitem.webif_infos[state.id].get('actions_enter'):
                _key = ['{}'.format(state.id), 'actions_enter', '{}'.format(name), 'actionstatus', 'success']
                self._abitem.update_webif(_key, success)
                _key = ['{}'.format(state.id), 'actions_enter', '{}'.format(name), 'actionstatus', 'issue']
                self._abitem.update_webif(_key, issue)
        except Exception:
            pass
        try:
            if self._abitem.webif_infos[state.id].get('actions_enter_or_stay'):
                _key = ['{}'.format(state.id), 'actions_enter_or_stay', '{}'.format(name), 'actionstatus', 'success']
                self._abitem.update_webif(_key, success)
                _key = ['{}'.format(state.id), 'actions_enter_or_stay', '{}'.format(name), 'actionstatus', 'issue']
                self._abitem.update_webif(_key, issue)
        except Exception:
            pass
        try:
            state.update_name(state.state_item)
            _key_name = ['{}'.format(state.id), 'name']
            self._abitem.update_webif(_key_name, state.name)
            if self._abitem.webif_infos[state.id].get('actions_leave'):
                _key = ['{}'.format(state.id), 'actions_leave', '{}'.format(name), 'actionstatus', 'success']
                self._abitem.update_webif(_key, success)
                _key = ['{}'.format(state.id), 'actions_leave', '{}'.format(name), 'actionstatus', 'issue']
                self._abitem.update_webif(_key, issue)
        except Exception:
            pass

    # Write action to logger
    def write_to_logger(self):
        self._log_info("function: {}", self._function)
        self.__delay.write_to_logger()
        if self.__repeat is not None:
            self.__repeat.write_to_logger()
        if self.__instanteval is not None:
            self.__instanteval.write_to_logger()
        if self.conditionset is not None:
            self.conditionset.write_to_logger()
        if self.previousconditionset is not None:
            self.previousconditionset.write_to_logger()
        if self.previousstate_conditionset is not None:
            self.previousstate_conditionset.write_to_logger()
        if self.__mode is not None:
            self.__mode.write_to_logger()
        self.__order.write_to_logger()

    def set_source(self, current_condition, previous_condition, previousstate_condition):
        source = []
        if current_condition in [[], None] and previous_condition in [[], None] and previousstate_condition in [[], None]:
            source = self._parent
        else:
            if current_condition != []:
                source.append("condition={}".format(current_condition))
            if previous_condition != []:
                source.append("previouscondition={}".format(previous_condition))
            if previousstate_condition != []:
                source.append("previousstate_condition={}".format(previousstate_condition))
            source = ", ".join(source)
        return source

    # If se_item_<name> starts with eval: the eval expression is getting evaluated
    # check_item: the eval entry as a string
    # check_value: current value of an action, will get newly cast based on eval (optional)
    # check_mindelta: current mindelta of an action, will get newly cast based on eval (optional)
    # returns: evaluated expression
    # newly evaluated value
    # newly evaluated mindelta
    # Any issue that might have occured as a dict
    def check_getitem_fromeval(self, check_item, check_value=None, check_mindelta=None):
        _issue = {self._name: {'issue': None, 'issueorigin': [{'state': 'unknown', 'action': self._function}]}}
        if isinstance(check_item, str):
            item = None
            #self._log_develop("Get item from eval on {} {}", self._function, check_item)
            if "stateengine_eval" in check_item or "se_eval" in check_item:
                # noinspection PyUnusedLocal
                stateengine_eval = se_eval = StateEngineEval.SeEval(self._abitem)
            try:
                item = check_item.replace('sh', 'self._sh')
                item = item.replace('shtime', 'self._shtime')
                if item.startswith("eval:"):
                    _text = "If you define an item by se_eval_<name> you should use a "\
                            "plain eval expression without a preceeding eval. "\
                            "Please update your config of {}"
                    _issue = {
                        self._name: {'issue': _text.format(check_item), 'issueorigin': [{'state': 'unknown', 'action': self._function}]}}
                    self._log_warning(_text, check_item)
                    _, _, item = item.partition(":")
                elif re.match(r'^.*:', item):
                    _text = "se_eval/item attributes have to be plain eval expression. Please update your config of {}"
                    _issue = {
                        self._name: {'issue': _text.format(check_item),
                                     'issueorigin': [{'state': 'unknown', 'action': self._function}]}}
                    self._log_warning(_text, check_item)
                    _, _, item = item.partition(":")
                item = eval(item)
                if item is not None:
                    check_item, _issue = self._abitem.return_item(item)
                    _issue = {
                        self._name: {'issue': _issue, 'issueorigin': [{'state': 'unknown', 'action': self._function}]}}
                    if check_value:
                        check_value.set_cast(check_item.cast)
                    if check_mindelta:
                        check_mindelta.set_cast(check_item.cast)
                    self._scheduler_name = "{}-SeItemDelayTimer".format(check_item.property.path)
                    if self._abitem.id == check_item.property.path:
                        self._caller += '_self'
                    #self._log_develop("Got item from eval on {} {}", self._function, check_item)
                else:
                    self._log_develop("Got no item from eval on {} with initial item {}", self._function, self.__item)
            except Exception as ex:
                _issue = {self._name: {'issue': ex, 'issueorigin': [{'state': 'unknown', 'action': self._function}]}}
                # raise Exception("Problem evaluating item '{}' from eval: {}".format(check_item, ex))
                self._log_error("Problem evaluating item '{}' from eval: {}", check_item, ex)
                check_item = None
            if item is None:
                _issue = {self._name: {'issue': ['Item {} from eval not existing'.format(check_item)],
                                       'issueorigin': [{'state': 'unknown', 'action': self._function}]}}
                # raise Exception("Problem evaluating item '{}' from eval. It does not exist.".format(check_item))
                self._log_error("Problem evaluating item '{}' from eval. It does not exist", check_item)
                check_item = None
        elif check_item is None:
            _issue = {self._name: {'issue': ['Item is None'],
                                   'issueorigin': [{'state': 'unknown', 'action': self._function}]}}
        return check_item, check_value, check_mindelta, _issue

    def check_complete(self, item_state, check_item, check_status, check_mindelta, check_value, action_type, evals_items=None):
        _issue = {self._name: {'issue': None,
                               'issueorigin': [{'state': item_state.property.path, 'action': self._function}]}}
        self._log_develop("Check item {} status {} value {} evals_items {}", check_item, check_status, check_value, evals_items)
        try:
            _name = evals_items.get(self.name)
            if _name is not None:
                _item = _name.get('item')
                _eval = str(_name.get('eval'))
                _selfitem = check_item if check_item not in (None, "None") else None
                _item = _item if _item not in (None, "None") else None
                _eval = _eval if _eval not in (None, "None") else None
                check_item = _selfitem or _eval
                if check_item is None:
                    _returnitem, _returnissue = self._abitem.return_item(_item)
                    check_item = _returnitem
                else:
                    _returnissue = None
                _issue = {self._name: {'issue': _returnissue,
                                       'issueorigin': [{'state': item_state.property.path, 'action': self._function}]}}
                self._log_debug("Check item {} status {} value {} _returnissue {}", check_item, check_status, check_value,
                        _returnissue)
        except Exception as ex:
            self._log_info("No valid item info for action {}, trying to get differently. Problem: {}", self._name, ex)
        # missing item in action: Try to find it.
        if check_item is None:
            item = StateEngineTools.find_attribute(self._sh, item_state, "se_item_" + self._name)
            if item is not None:
                check_item, _issue = self._abitem.return_item(item)
                _issue = {self._name: {'issue': _issue,
                                       'issueorigin': [{'state': item_state.property.path, 'action': self._function}]}}
            else:
                item = StateEngineTools.find_attribute(self._sh, item_state, "se_eval_" + self._name)
                if item is not None:
                    check_item = str(item)

        if check_item is None and _issue[self._name].get('issue') is None:
            _issue = {self._name: {'issue': ['Item not defined in rules section'],
                                   'issueorigin': [{'state': item_state.property.path, 'action': self._function}]}}
        # missing status in action: Try to find it.
        if check_status is None:
            status = StateEngineTools.find_attribute(self._sh, item_state, "se_status_" + self._name)
            if status is not None:
                check_status, _issue = self._abitem.return_item(status)
                _issue = {self._name: {'issue': _issue,
                                       'issueorigin': [{'state': item_state.property.path, 'action': self._function}]}}
            elif check_status is not None:
                check_status = str(status)

        if check_mindelta.is_empty():
            mindelta = StateEngineTools.find_attribute(self._sh, item_state, "se_mindelta_" + self._name)
            if mindelta is not None:
                check_mindelta.set(mindelta)

        if check_status is not None:
            check_value.set_cast(check_status.cast)
            check_mindelta.set_cast(check_status.cast)
            self._scheduler_name = "{}-SeItemDelayTimer".format(check_status.property.path)
            if self._abitem.id == check_status.property.path:
                self._caller += '_self'
        elif check_status is None:
            if isinstance(check_item, str):
                pass
            elif check_item is not None:
                check_value.set_cast(check_item.cast)
                check_mindelta.set_cast(check_item.cast)
                self._scheduler_name = "{}-SeItemDelayTimer".format(check_item.property.path)
                if self._abitem.id == check_item.property.path:
                    self._caller += '_self'
        if _issue[self._name].get('issue') not in [[], [None], None]:
            self._log_develop("Issue with {} action {}", action_type, _issue)
        else:
            _issue = {self._name: {'issue': None,
                                   'issueorigin': [{'state': item_state.property.path, 'action': self._function}]}}

        return check_item, check_status, check_mindelta, check_value, _issue

    # Execute action (considering delay, etc)
    # is_repeat: Indicate if this is a repeated action without changing the state
    # item_allow_repeat: Is repeating actions generally allowed for the item?
    # state: state item that triggered the action
    def execute(self, is_repeat: bool, allow_item_repeat: bool, state):
        # check if any conditiontype is met or not
        # condition: type of condition 'conditionset'/'previousconditionset'/'previousstate_conditionset'
        def _check_condition(condition: str):
            _conditions_met_count = 0
            _conditions_necessary_count = 0
            _condition_to_meet = None
            _updated__current_condition = None
            if condition == 'conditionset':
                _condition_to_meet = None if self.conditionset.is_empty() else self.conditionset.get()
                _current_condition = self._abitem.get_lastconditionset_id()
                _updated__current_condition = self._abitem.get_variable("current.state_id") if _current_condition == '' else _current_condition
            elif condition == 'previousconditionset':
                _condition_to_meet = None if self.previousconditionset.is_empty() else self.previousconditionset.get()
                _current_condition = self._abitem.get_previousconditionset_id()
                _updated__current_condition = self._abitem.get_previousstate_id() if _current_condition == '' else _current_condition
            elif condition == 'previousstate_conditionset':
                _condition_to_meet = None if self.previousstate_conditionset.is_empty() else self.previousstate_conditionset.get()
                _current_condition = self._abitem.get_previousstate_conditionset_id()
                _updated__current_condition = self._abitem.get_previousstate_id() if _current_condition == '' else _current_condition
            _condition_to_meet = _condition_to_meet if isinstance(_condition_to_meet, list) else [_condition_to_meet]
            _condition_met = []
            for cond in _condition_to_meet:
                if cond is not None:
                    _conditions_necessary_count += 1
                    _orig_cond = cond
                    try:
                        cond = re.compile(cond)
                        _matching = cond.fullmatch(_updated__current_condition)
                        if _matching:
                            self._log_debug("Given {} {} matches current one: {}", condition, _orig_cond, _updated__current_condition)
                            _condition_met.append(_updated__current_condition)
                            _conditions_met_count +=1
                        else:
                            self._log_debug("Given {} {} not matching current one: {}", condition, _orig_cond, _updated__current_condition)
                    except Exception as ex:
                        if cond is not None:
                            self._log_warning("Given {} {} is not a valid regex: {}", condition, _orig_cond, ex)
            return _condition_met, _conditions_met_count, _conditions_necessary_count

        # update web interface with delay info
        # action_type: 'actions_enter', etc.
        # delay_info: delay information
        def _update_delay_webif(action_type: str, delay_info: str):
            try:
                _key = ['{}'.format(state.id), '{}'.format(action_type), '{}'.format(self._name), 'delay']
                self._abitem.update_webif(_key, delay_info)
            except Exception:
                pass

        # update web interface with repeat info
        # value: bool type True or False for repeat value
        def _update_repeat_webif(value: bool):
            _key1 = ['{}'.format(state.id), 'actions_stay', '{}'.format(self._name), 'repeat']
            _key2 = ['{}'.format(state.id), 'actions_enter_or_stay', '{}'.format(self._name), 'repeat']
            result = self._abitem.update_webif(_key1, value)
            if result is False:
                self._abitem.update_webif(_key2, value)

        self._log_decrease_indent(50)
        self._log_increase_indent()
        self._log_info("Action '{0}': Preparing", self._name)
        self._log_increase_indent()
        try:
            self._getitem_fromeval()
            self._log_decrease_indent()
            _validitem = True
        except Exception as ex:
            _validitem = False
            self._log_decrease_indent()
        if not self._can_execute(state):
            self._log_decrease_indent()
            return
        conditions_met = 0
        condition_necessary = 0
        current_condition_met, cur_conditions_met, cur_condition_necessary = _check_condition('conditionset')
        conditions_met += cur_conditions_met
        condition_necessary += cur_condition_necessary
        previous_condition_met, prev_conditions_met, prev_condition_necessary = _check_condition('previousconditionset')
        conditions_met += prev_conditions_met
        condition_necessary += prev_condition_necessary
        previousstate_condition_met, prevst_conditions_met, prevst_condition_necessary = _check_condition('previousstate_conditionset')
        conditions_met += prevst_conditions_met
        condition_necessary += prevst_condition_necessary
        self._log_develop("Action '{0}': conditions met: {1}, necessary {2}.", self._name, conditions_met, condition_necessary)
        if conditions_met < condition_necessary:
            self._log_info("Action '{0}': Skipping because not all conditions are met.", self._name)
            return

        if is_repeat:
            if self.__repeat is None:
                if allow_item_repeat:
                    repeat_text = " Repeat allowed by item configuration."
                    _update_repeat_webif(True)
                else:
                    self._log_info("Action '{0}': Repeat denied by item configuration.", self._name)
                    _update_repeat_webif(False)
                    return
            elif self.__repeat.get():
                repeat_text = " Repeat allowed by action configuration."
                _update_repeat_webif(True)
            else:
                self._log_info("Action '{0}': Repeat denied by action configuration.", self._name)
                _update_repeat_webif(False)
                return
        else:
            repeat_text = ""
        self._log_increase_indent()
        if _validitem:
            delay = 0 if self.__delay.is_empty() else self.__delay.get()
            plan_next = self._se_plugin.scheduler_return_next(self._scheduler_name)
            if plan_next is not None and plan_next > self.shtime.now() or delay == -1:
                self._log_info("Action '{0}: Removing previous delay timer '{1}'.", self._name, self._scheduler_name)
                self._se_plugin.scheduler_remove(self._scheduler_name)
                try:
                    self._abitem.remove_scheduler_entry(self._scheduler_name)
                except Exception:
                    pass

            actionname = "Action '{0}'".format(self._name) if delay == 0 else "Delayed Action ({0} seconds) '{1}'".format(
                delay, self._scheduler_name)
            _delay_info = 0
            if delay is None:
                self._log_increase_indent()
                self._log_warning("Action '{0}': Ignored because of errors while determining the delay!", self._name)
                self._log_decrease_indent()
                _delay_info = -1
            elif delay == -1:
                self._log_increase_indent()
                self._log_info("Action '{0}': Ignored because delay is set to -1.", self._name)
                self._log_decrease_indent()
                _delay_info = -1
            elif delay < -1:
                self._log_increase_indent()
                self._log_warning("Action '{0}': Ignored because delay is negative!", self._name)
                self._log_decrease_indent()
                _delay_info = -1
            else:
                self._waitforexecute(state, actionname, self._name, repeat_text, delay, current_condition_met, previous_condition_met, previousstate_condition_met)

            _update_delay_webif('actions_stay', _delay_info)
            _update_delay_webif('actions_enter', _delay_info)
            _update_delay_webif('actions_enter_or_stay', _delay_info)
            try:
                state.update_name(state.state_item)
                _key_name = ['{}'.format(state.id), 'name']
                self._abitem.update_webif(_key_name, state.name)
                _update_delay_webif('actions_leave', _delay_info)
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
    def _can_execute(self, state):
        return True

    def get(self):
        return True

    def _waitforexecute(self, state, actionname: str, namevar: str = "", repeat_text: str = "", delay: int = 0, current_condition: str = "", previous_condition: str = "", previousstate_condition: str = ""):
        self._log_decrease_indent(50)
        self._log_increase_indent()
        if delay == 0:
            self._log_info("Action '{}': Running.", namevar)
            self.real_execute(state, actionname, namevar, repeat_text, None, False, current_condition, previous_condition, previousstate_condition)
        else:
            instanteval = None if self.__instanteval is None else self.__instanteval.get()
            self._log_info("Action '{0}': Add {1} second timer '{2}' "
                           "for delayed execution.{3} Instant Eval: {4}", self._name, delay,
                           self._scheduler_name, repeat_text, instanteval)
            next_run = self.shtime.now() + datetime.timedelta(seconds=delay)
            if instanteval is True:
                self._log_increase_indent()
                self._log_debug("Evaluating value for delayed action '{}'.", namevar)
                value = self.real_execute(state, actionname, namevar, repeat_text, None, True, current_condition, previous_condition, previousstate_condition)
                self._log_debug("Value for delayed action is going to be '{}'.", value)
                self._log_decrease_indent()
            else:
                value = None
            self._abitem.add_scheduler_entry(self._scheduler_name)
            self.update_webif_actionstatus(state, self._name, 'Scheduled')
            self._se_plugin.scheduler_add(self._scheduler_name, self._delayed_execute,
                                          value={'actionname': actionname, 'namevar': self._name,
                                                 'repeat_text': repeat_text, 'value': value,
                                                 'current_condition': current_condition,
                                                 'previous_condition': previous_condition,
                                                 'previousstate_condition': previousstate_condition,
                                                 'state': state}, next=next_run)

    def _delayed_execute(self, actionname: str, namevar: str = "", repeat_text: str = "", value=None, current_condition=None, previous_condition=None, previousstate_condition=None, state=None, caller=None):
        if state:
            self._log_debug("Putting delayed action '{}' from state '{}' into queue. Caller: {}", namevar, state, caller)
            self.__queue.put(["delayedaction", self, actionname, namevar, repeat_text, value, current_condition, previous_condition, previousstate_condition, state])
        else:
            self._log_debug("Putting delayed action '{}' into queue. Caller: {}", namevar, caller)
            self.__queue.put(["delayedaction", self, actionname, namevar, repeat_text, value, current_condition, previous_condition, previousstate_condition])
        if not self._abitem.update_lock.locked():
            self._log_debug("Running queue")
            self._abitem.run_queue()

    # Really execute the action (needs to be implemented in derived classes)
    def real_execute(self, state, actionname: str, namevar: str = "", repeat_text: str = "", value=None, returnvalue=False, current_condition=None, previous_condition=None, previousstate_condition=None):
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
        self.__status = None
        self.__delta = 0
        self.__value = StateEngineValue.SeValue(self._abitem, "value")
        self.__mindelta = StateEngineValue.SeValue(self._abitem, "mindelta")
        self._function = "set"

    def __repr__(self):
        return "SeAction Set {}".format(self._name)

    def _getitem_fromeval(self):
        if self.__item is None:
            return
        self.__item, self.__value, self.__mindelta, _issue = self.check_getitem_fromeval(self.__item, self.__value,
                                                                                         self.__mindelta)
        if self.__item is None:
            self._action_status = _issue
            raise Exception("Problem evaluating item '{}' from eval.".format(self.__item))

    # set the action based on a set_(action_name) attribute
    # value: Value of the set_(action_name) attribute
    def update(self, value):
        _, _, _issue = self.__value.set(value)
        _issue = {self._name: {'issue': _issue, 'issueorigin': [{'state': 'unknown', 'action': self._function}]}}
        return _issue

    # Complete action
    # item_state: state item to read from
    def complete(self, item_state, evals_items=None):
        self.__item, self.__status, self.__mindelta, self.__value, _issue = self.check_complete(
            item_state, self.__item, self.__status, self.__mindelta, self.__value, "set", evals_items)
        self._action_status = _issue
        return _issue

    # Write action to logger
    def write_to_logger(self):
        SeActionBase.write_to_logger(self)
        if isinstance(self.__item, str):
            try:
                self._log_debug("item from eval: {0}", self.__item)
                self._log_increase_indent()
                current, _, _, _ = self.check_getitem_fromeval(self.__item)
                self._log_debug("Currently eval results in {}", current)
                self._log_decrease_indent()
            except Exception as ex:
                self._log_warning("Issue while getting item from eval {}", ex)
        elif self.__item is not None:
            self._log_debug("item: {0}", self.__item.property.path)
        else:
            self._log_debug("item is not defined! Check log file.")
        if self.__status is not None:
            self._log_debug("status: {0}", self.__status.property.path)
        self.__mindelta.write_to_logger()
        self.__value.write_to_logger()

    # Check if execution is possible
    def _can_execute(self, state):
        if self.__item is None:
            self._log_increase_indent()
            self._log_warning("Action '{0}': No item defined. Ignoring.", self._name)
            self._log_decrease_indent()
            self.update_webif_actionstatus(state, self._name, 'False', 'No item defined')
            return False

        if self.__value.is_empty():
            self._log_increase_indent()
            self._log_warning("Action '{0}': No value for item {1} defined. Ignoring.", self._name, self.__item)
            self._log_decrease_indent()
            self.update_webif_actionstatus(state, self._name, 'False', 'No value for item {}'.format(self.__item))
            return False
        self.update_webif_actionstatus(state, self._name, 'True')
        return True

    # Really execute the action (needs to be implemented in derived classes)
    def real_execute(self, state, actionname: str, namevar: str = "", repeat_text: str = "", value=None, returnvalue=False, current_condition=None, previous_condition=None, previousstate_condition=None):
        self._abitem.set_variable('current.action_name', namevar)
        self._log_increase_indent()
        if value is None:
            value = self.__value.get()

        if value is None:
            self._log_debug("{0}: Value is None", actionname)
            pat = "(?:[^,\(]*)\'(.*?)\'"
            self.update_webif_actionstatus(state, re.findall(pat, actionname)[0], 'False', 'Value is None')
            return

        if returnvalue:
            self._log_decrease_indent()
            return value

        if not self.__mindelta.is_empty():
            mindelta = self.__mindelta.get()
            if self.__status is not None:
                # noinspection PyCallingNonCallable
                delta = float(abs(self.__status() - value))
                additionaltext = "of statusitem "
            else:
                delta = float(abs(self.__item() - value))
                additionaltext = ""

            self.__delta = delta
            if delta < mindelta:
                text = "{0}: Not setting '{1}' to '{2}' because delta {3}'{4:.2}' is lower than mindelta '{5}'"
                self._log_debug(text, actionname, self.__item.property.path, value, additionaltext, delta, mindelta)
                self.update_webif_actionstatus(state, self._name, 'False')
                return

        self._execute_set_add_remove(state, actionname, namevar, repeat_text, self.__item, value, current_condition, previous_condition, previousstate_condition)

    def _execute_set_add_remove(self, state, actionname, namevar, repeat_text, item, value, current_condition, previous_condition, previousstate_condition):
        self._log_decrease_indent()
        self._log_debug("{0}: Set '{1}' to '{2}'{3}", actionname, item.property.path, value, repeat_text)
        source = self.set_source(current_condition, previous_condition, previousstate_condition)
        pat = "(?:[^,\(]*)\'(.*?)\'"
        self.update_webif_actionstatus(state, re.findall(pat, actionname)[0], 'True')
        # noinspection PyCallingNonCallable
        item(value, caller=self._caller, source=source)

    def get(self):
        orig_item = self.__item
        try:
            self._getitem_fromeval()
        except Exception as ex:
            self._log_warning("Issue while getting item from eval {}", ex)
        item_from_eval = orig_item if orig_item != self.__item else False
        try:
            if self.__item is not None:
                item = str(self.__item.property.path)
            else:
                item = None
        except Exception as ex:
            item = None
        try:
            val = self.__value.get()
            if val is not None:
                value = str(val)
            else:
                value = None
        except Exception:
            value = None
        mindelta = self.__mindelta.get()
        if mindelta is None:
            result = {'function': str(self._function), 'item': item, 'item_from_eval': item_from_eval,
                     'value': value, 'conditionset': str(self.conditionset.get()),
                     'previousconditionset': str(self.previousconditionset.get()),
                     'previousstate_conditionset': str(self.previousstate_conditionset.get()), 'actionstatus': {}}
        else:
            result = {'function': str(self._function), 'item': item, 'item_from_eval': item_from_eval,
                     'value': value, 'conditionset': str(self.conditionset.get()),
                     'previousconditionset': str(self.previousconditionset.get()),
                     'previousstate_conditionset': str(self.previousstate_conditionset.get()), 'actionstatus': {},
                     'delta': str(self.__delta), 'mindelta': str(mindelta)}
        return result


# Class representing a single "se_setbyattr" action
class SeActionSetByattr(SeActionBase):
    # Initialize the action
    # abitem: parent SeItem instance
    # name: Name of action
    def __init__(self, abitem, name: str):
        super().__init__(abitem, name)
        self.__byattr = None
        self._function = "set by attribute"

    def __repr__(self):
        return "SeAction SetByAttr {}".format(self._name)

    # set the action based on a set_(action_name) attribute
    # value: Value of the set_(action_name) attribute
    def update(self, value):
        self.__byattr = value
        _issue = {self._name: {'issue': None, 'attribute': self.__byattr,
                               'issueorigin': [{'state': 'unknown', 'action': self._function}]}}
        return _issue

    # Complete action
    # item_state: state item to read from
    def complete(self, item_state, evals_items=None):
        self._scheduler_name = "{}-SeByAttrDelayTimer".format(self.__byattr)
        _issue = {self._name: {'issue': None, 'attribute': self.__byattr,
                               'issueorigin': [{'state': 'unknown', 'action': self._function}]}}
        return _issue

    # Write action to logger
    def write_to_logger(self):
        SeActionBase.write_to_logger(self)
        if self.__byattr is not None:
            self._log_debug("set by attribute: {0}", self.__byattr)

    # Really execute the action
    def real_execute(self, state, actionname: str, namevar: str = "", repeat_text: str = "", value=None, returnvalue=False, current_condition=None, previous_condition=None, previousstate_condition=None):
        self._abitem.set_variable('current.action_name', namevar)
        if returnvalue:
            return value
        self._log_info("{0}: Setting values by attribute '{1}'.{2}", actionname, self.__byattr, repeat_text)
        self.update_webif_actionstatus(state, self._name, 'True')
        source = self.set_source(current_condition, previous_condition, previousstate_condition)
        for item in self.itemsApi.find_items(self.__byattr):
            self._log_info("\t{0} = {1}", item.property.path, item.conf[self.__byattr])
            item(item.conf[self.__byattr], caller=self._caller, source=source)

    def get(self):
        result = {'function': str(self._function), 'byattr': str(self.__byattr),
                 'conditionset': str(self.conditionset.get()), 'previousconditionset': str(self.previousconditionset.get()),
                 'previousstate_conditionset': str(self.previousstate_conditionset.get()), 'actionstatus': {}}
        return result


# Class representing a single "se_trigger" action
class SeActionTrigger(SeActionBase):
    # Initialize the action
    # abitem: parent SeItem instance
    # name: Name of action
    def __init__(self, abitem, name: str):
        super().__init__(abitem, name)
        self.__logic = None
        self.__value = StateEngineValue.SeValue(self._abitem, "value")
        self._function = "trigger"

    def __repr__(self):
        return "SeAction Trigger {}".format(self._name)

    # set the action based on a set_(action_name) attribute
    # value: Value of the set_(action_name) attribute
    def update(self, value):
        logic, value = StateEngineTools.partition_strip(value, ":")
        self.__logic = logic
        value = None if value == "" else value
        _, _, _issue = self.__value.set(value)
        _issue = {self._name: {'issue': _issue, 'logic': self.__logic,
                               'issueorigin': [{'state': 'unknown', 'action': self._function}]}}
        return _issue

    # Complete action
    # item_state: state item to read from
    def complete(self, item_state, evals_items=None):
        self._scheduler_name = "{}-SeLogicDelayTimer".format(self.__logic)
        _issue = {self._name: {'issue': None, 'logic': self.__logic,
                               'issueorigin': [{'state': 'unknown', 'action': self._function}]}}
        return _issue

    # Write action to logger
    def write_to_logger(self):
        SeActionBase.write_to_logger(self)
        if self.__logic is not None:
            self._log_debug("trigger logic: {0}", self.__logic)
        if self.__value is not None:
            self._log_debug("value: {0}", self.__value)

    # Really execute the action
    def real_execute(self, state, actionname: str, namevar: str = "", repeat_text: str = "", value=None, returnvalue=False, current_condition=None, previous_condition=None, previousstate_condition=None):
        self._abitem.set_variable('current.action_name', namevar)
        if value is None:
            try:
                value = self.__value.get()
            except Exception:
                value = self.__value

        if returnvalue:
            return value
        self.update_webif_actionstatus(state, self._name, 'True')
        self._log_info("{0}: Triggering logic '{1}' using value '{2}'.{3}", actionname, self.__logic, value, repeat_text)
        add_logics = 'logics.{}'.format(self.__logic) if not self.__logic.startswith('logics.') else self.__logic
        self._sh.trigger(add_logics, by=self._caller, source=self._name, value=value)

    def get(self):
        try:
            val = self.__value.get()
            if val is not None:
                value = str(val)
            else:
                value = None
        except Exception:
            value = None
        result = {'function': str(self._function), 'logic': str(self.__logic),
                 'value': value,
                 'conditionset': str(self.conditionset.get()), 'previousconditionset': str(self.previousconditionset.get()),
                 'previousstate_conditionset': str(self.previousstate_conditionset.get()), 'actionstatus': {}}
        return result

# Class representing a single "se_run" action
class SeActionRun(SeActionBase):
    # Initialize the action
    # abitem: parent SeItem instance
    # name: Name of action
    def __init__(self, abitem, name: str):
        super().__init__(abitem, name)
        self.__eval = None
        self._function = "run"

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
        _issue = {self._name: {'issue': None, 'eval': StateEngineTools.get_eval_name(self.__eval),
                               'issueorigin': [{'state': 'unknown', 'action': self._function}]}}
        return _issue

    # Complete action
    # item_state: state item to read from
    def complete(self, item_state, evals_items=None):
        self._scheduler_name = "{}-SeRunDelayTimer".format(StateEngineTools.get_eval_name(self.__eval))
        _issue = {self._name: {'issue': None, 'eval': StateEngineTools.get_eval_name(self.__eval),
                               'issueorigin': [{'state': 'unknown', 'action': self._function}]}}
        return _issue

    # Write action to logger
    def write_to_logger(self):
        SeActionBase.write_to_logger(self)
        if self.__eval is not None:
            self._log_debug("eval: {0}", StateEngineTools.get_eval_name(self.__eval))

    # Really execute the action
    def real_execute(self, state, actionname: str, namevar: str = "", repeat_text: str = "", value=None, returnvalue=False, current_condition=None, previous_condition=None, previousstate_condition=None):
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
                if current_condition:
                    self._log_debug("Running eval {0} based on conditionset {1}", self.__eval, current_condition)
                if previous_condition:
                    self._log_debug("Running eval {0} based on previous conditionset {1}", self.__eval, previous_condition)
                if previousstate_condition:
                    self._log_debug("Running eval {0} based on previous state's conditionset {1}", self.__eval, previousstate_condition)
                eval(self.__eval)
                self.update_webif_actionstatus(state, self._name, 'True')
                self._log_decrease_indent()
            except Exception as ex:
                self._log_decrease_indent()
                text = "{0}: Problem evaluating '{1}': {2}."
                self.update_webif_actionstatus(state, self._name, 'False', 'Problem evaluating: {}'.format(ex))
                self._log_error(text.format(actionname, StateEngineTools.get_eval_name(self.__eval), ex))
        else:
            try:
                if returnvalue:
                    self._log_decrease_indent()
                    return self.__eval()
                if current_condition:
                    self._log_debug("Running eval {0} based on conditionset {1}", self.__eval, current_condition)
                if previous_condition:
                    self._log_debug("Running eval {0} based on previous conditionset {1}", self.__eval, previous_condition)
                if previousstate_condition:
                    self._log_debug("Running eval {0} based on previous state's conditionset {1}", self.__eval, previousstate_condition)
                self.__eval()
                self.update_webif_actionstatus(state, self._name, 'True')
                self._log_decrease_indent()
            except Exception as ex:
                self._log_decrease_indent()
                self.update_webif_actionstatus(state, self._name, 'False', 'Problem calling: {}'.format(ex))
                text = "{0}: Problem calling '{0}': {1}."
                self._log_error(text.format(actionname, StateEngineTools.get_eval_name(self.__eval), ex))

    def get(self):
        result = {'function': str(self._function), 'eval': str(self.__eval),
                 'conditionset': str(self.conditionset.get()), 'previousconditionset': str(self.previousconditionset.get()),
                 'previousstate_conditionset': str(self.previousstate_conditionset.get()), 'actionstatus': {}}
        return result


# Class representing a single "se_force" action
class SeActionForceItem(SeActionBase):
    # Initialize the action
    # abitem: parent SeItem instance
    # name: Name of action
    def __init__(self, abitem, name: str):
        super().__init__(abitem, name)
        self.__item = None
        self.__status = None
        self.__value = StateEngineValue.SeValue(self._abitem, "value")
        self.__mindelta = StateEngineValue.SeValue(self._abitem, "mindelta")
        self._function = "force set"

    def __repr__(self):
        return "SeAction Force {}".format(self._name)

    # set the action based on a set_(action_name) attribute
    # value: Value of the set_(action_name) attribute
    def update(self, value):
        _, _, _issue = self.__value.set(value)
        _issue = {self._name: {'issue': _issue, 'issueorigin': [{'state': 'unknown', 'action': self._function}]}}
        return _issue

    # Complete action
    # item_state: state item to read from
    def complete(self, item_state, evals_items=None):
        self.__item, self.__status, self.__mindelta, self.__value, _issue = self.check_complete(
            item_state, self.__item, self.__status, self.__mindelta, self.__value, "force", evals_items)
        self._action_status = _issue
        return _issue

    # Write action to logger
    def write_to_logger(self):
        SeActionBase.write_to_logger(self)
        if isinstance(self.__item, str):
            try:
                self._log_debug("item from eval: {0}", self.__item)
                self._log_increase_indent()
                current, _, _, _ = self.check_getitem_fromeval(self.__item)
                self._log_debug("Currently eval results in {}", current)
                self._log_decrease_indent()
            except Exception as ex:
                self._log_warning("Issue while getting item from eval {}", ex)
        elif self.__item is not None:
            self._log_debug("item: {0}", self.__item.property.path)
        else:
            self._log_debug("item is not defined! Check log file.")
        if self.__status is not None:
            self._log_debug("status: {0}", self.__status.property.path)
        self.__mindelta.write_to_logger()
        self.__value.write_to_logger()
        self._log_debug("force update: yes")

    # Check if execution is possible
    def _can_execute(self, state):
        if self.__item is None:
            self._log_increase_indent()
            self._log_warning("Action '{0}': No item defined. Ignoring.", self._name)
            self._log_decrease_indent()
            self.update_webif_actionstatus(state, self._name, 'False', 'No item defined')
            return False

        if self.__value.is_empty():
            self._log_increase_indent()
            self._log_warning("Action '{0}': No value defined for item {1}. Ignoring.", self._name, self.__item)
            self._log_decrease_indent()
            self.update_webif_actionstatus(state, self._name, 'False', 'No value defined for item {}'.format(self.__item))
            return False
        self.update_webif_actionstatus(state, self._name, 'True')
        return True

    def _getitem_fromeval(self):
        if self.__item is None:
            return
        self.__item, self.__value, self.__mindelta, _issue = self.check_getitem_fromeval(self.__item, self.__value,
                                                                                         self.__mindelta)
        if self.__item is None:
            self._action_status = _issue
            raise Exception("Problem evaluating item '{}' from eval.".format(self.__item))

    # Really execute the action (needs to be implemented in derived classes)
    # noinspection PyProtectedMember
    def real_execute(self, state, actionname: str, namevar: str = "", repeat_text: str = "", value=None, returnvalue=False, current_condition=None, previous_condition=None, previousstate_condition=None):
        self._abitem.set_variable('current.action_name', namevar)
        self._log_increase_indent()
        if value is None:
            value = self.__value.get()

        if value is None:
            self._log_debug("{0}: Value is None", actionname)
            self.update_webif_actionstatus(state, self._name, 'False', 'Value is None')
            return

        if returnvalue:
            self._log_decrease_indent()
            return value

        if not self.__mindelta.is_empty():
            mindelta = self.__mindelta.get()
            # noinspection PyCallingNonCallable
            delta = float(abs(self.__item() - value))
            if delta < mindelta:
                self.update_webif_actionstatus(state, self._name, 'False')
                text = "{0}: Not setting '{1}' to '{2}' because delta '{3:.2}' is lower than mindelta '{4}'"
                self._log_debug(text, actionname, self.__item.property.path, value, delta, mindelta)
                return
        source = self.set_source(current_condition, previous_condition, previousstate_condition)
        # Set to different value first ("force")
        current_value = self.__item()
        if current_value == value:
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
                self._log_debug("{0}: Set '{1}' to '{2}' (Force)", actionname, self.__item.property.path, current_value+0.1)
                self.__item(current_value+0.1, caller=self._caller, source=source)
            else:
                self._log_warning("{0}: Force not implemented for item type '{1}'", actionname, self.__item._type)
        else:
            self._log_debug("{0}: New value differs from old value, no force required.", actionname)
        self._log_decrease_indent()
        self._log_debug("{0}: Set '{1}' to '{2}'.{3}", actionname, self.__item.property.path, value, repeat_text)
        self.update_webif_actionstatus(state, self._name, 'True')
        # noinspection PyCallingNonCallable
        self.__item(value, caller=self._caller, source=source)

    def get(self):
        orig_item = self.__item
        try:
            self._getitem_fromeval()
        except Exception as ex:
            self._log_warning("Issue while getting item from eval {}", ex)
        item_from_eval = orig_item if orig_item != self.__item else False
        try:
            if self.__item is not None:
                item = str(self.__item.property.path)
            else:
                item = None
        except Exception:
            item = None
        try:
            val = self.__value.get()
            if val is not None:
                value = str(val)
            else:
                value = None
        except Exception:
            value = None
        result = {'function': str(self._function), 'item': item, 'item_from_eval': item_from_eval, 'value': value,
                 'conditionset': str(self.conditionset.get()), 'previousconditionset': str(self.previousconditionset.get()),
                 'previousstate_conditionset': str(self.previousstate_conditionset.get()), 'actionstatus': {}}
        return result


# Class representing a single "se_special" action
class SeActionSpecial(SeActionBase):
    # Initialize the action
    # abitem: parent SeItem instance
    # name: Name of action
    def __init__(self, abitem, name: str):
        super().__init__(abitem, name)
        self.__special = None
        self.__value = None
        self._function = "special"

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
        _issue = {self._name: {'issue': None, 'special': self.__value, 'issueorigin': [{'state': 'unknown', 'action': self._function}]}}
        return _issue

    # Complete action
    # item_state: state item to read from
    def complete(self, item_state, evals_items=None):
        if isinstance(self.__value, list):
            item = self.__value[0].property.path
        else:
            item = self.__value.property.path
        self._scheduler_name = "{}_{}-SeSpecialDelayTimer".format(self.__special, item)
        _issue = {self._name: {'issue': None, 'special': item, 'issueorigin': [{'state': 'unknown', 'action': self._function}]}}
        return _issue

    # Write action to logger
    def write_to_logger(self):
        SeActionBase.write_to_logger(self)
        self._log_debug("Special Action: {0}", self.__special)
        if isinstance(self.__value, list):
            self._log_debug("value: {0}", self.__value)
        else:
            self._log_debug("Retrigger item: {0}", self.__value.property.path)

    # Really execute the action
    def real_execute(self, state, actionname: str, namevar: str = "", repeat_text: str = "", value=None, returnvalue=False, current_condition=None, previous_condition=None, previousstate_condition=None):
        self._abitem.set_variable('current.action_name', namevar)
        if returnvalue:
            return None
        try:
            _log_value = self.__value.property.path
        except Exception:
            _log_value = self.__value
        self._log_info("{0}: Executing special action '{1}' using item '{2}' based on '{3}/{4}/{5}'.{6}",
                       actionname, self.__special, _log_value, current_condition, previous_condition, previousstate_condition, repeat_text)
        self._log_increase_indent()
        if self.__special == "suspend":
            self.suspend_execute(state, current_condition, previous_condition, previousstate_condition)
            if self._suspend_issue in ["", [], None, [None]]:
                self.update_webif_actionstatus(state, self._name, 'True')
            else:
                self.update_webif_actionstatus(state, self._name, 'False', self._suspend_issue)
            self._log_decrease_indent()
        elif self.__special == "retrigger":
            if self._retrigger_issue in ["", [], None, [None]]:
                self.update_webif_actionstatus(state, self._name, 'True')
            else:
                self.update_webif_actionstatus(state, self._name, 'False', self._retrigger_issue)
            # noinspection PyCallingNonCallable
            self._abitem.update_state(self.__value, self._caller)
            #self.__value(True, caller=self._caller)
            self._log_decrease_indent()
        else:
            self._log_decrease_indent()
            self.update_webif_actionstatus(state, self._name, 'False', 'Unknown special value {}'.format(self.__special))
            raise ValueError("{0}: Unknown special value '{1}'!".format(actionname, self.__special))
        self._log_debug("Special action {0}: done", self.__special)

    def suspend_get_value(self, value):
        _issue = {self._name: {'issue': None, 'issueorigin': [{'state': 'suspend', 'action': 'suspend'}]}}
        if value is None:
            text = 'Special action suspend requires arguments'
            _issue = {self._name: {'issue': text, 'issueorigin': [{'state': 'suspend', 'action': 'suspend'}]}}
            self._action_status = _issue
            self._suspend_issue = text
            raise ValueError("Action {0}: {1}".format(self._name, text))

        suspend, manual = StateEngineTools.partition_strip(value, ",")
        if suspend is None or manual is None:
            text = "Special action 'suspend' requires two arguments (separated by a comma)!"
            _issue = {self._name: {'issue': text, 'issueorigin': [{'state': 'suspend', 'action': 'suspend'}]}}
            self._action_status = _issue
            self._suspend_issue = text
            raise ValueError("Action {0}: {1}".format(self._name, text))

        suspend_item, _issue = self._abitem.return_item(suspend)
        _issue = {self._name: {'issue': _issue, 'issueorigin': [{'state': 'suspend', 'action': 'suspend'}]}}
        if suspend_item is None:
            text = "Suspend item '{}' not found!".format(suspend)
            _issue = {self._name: {'issue': text, 'issueorigin': [{'state': 'suspend', 'action': 'suspend'}]}}
            self._action_status = _issue
            self._suspend_issue = text
            raise ValueError("Action {0}: {1}".format(self._name, text))

        manual_item, _issue = self._abitem.return_item(manual)
        self._suspend_issue = _issue
        _issue = {self._name: {'issue': _issue, 'issueorigin': [{'state': 'suspend', 'action': 'suspend'}]}}
        if manual_item is None:
            text = 'Manual item {} not found'.format(manual)
            _issue = {self._name: {'issue': text, 'issueorigin': [{'state': 'suspend', 'action': 'suspend'}]}}
            self._action_status = _issue
            self._suspend_issue = text
            raise ValueError("Action {0}: {1}".format(self._name, text))
        self._action_status = _issue
        return [suspend_item, manual_item.property.path]

    def retrigger_get_value(self, value):
        if value is None:
            text = 'Special action retrigger requires item'
            _issue = {self._name: {'issue': text, 'issueorigin': [{'state': 'retrigger', 'action': 'retrigger'}]}}
            self._action_status = _issue
            self._retrigger_issue = text
            raise ValueError("Action {0}: {1}".format(self._name, text))

        se_item, __ = StateEngineTools.partition_strip(value, ",")

        se_item, _issue = self._abitem.return_item(se_item)
        self._retrigger_issue = _issue
        _issue = {self._name: {'issue': _issue, 'issueorigin': [{'state': 'retrigger', 'action': 'retrigger'}]}}
        self._action_status = _issue
        if se_item is None:
            text = 'Retrigger item {} not found'.format(se_item)
            _issue = {self._name: {'issue': text, 'issueorigin': [{'state': 'retrigger', 'action': 'retrigger'}]}}
            self._action_status = _issue
            self._retrigger_issue = text
            raise ValueError("Action {0}: {1}".format(self._name, text))
        return se_item

    def suspend_execute(self, state=None, current_condition=None, previous_condition=None, previousstate_condition=None):
        suspend_item, _issue = self._abitem.return_item(self.__value[0])
        _issue = {self._name: {'issue': _issue, 'issueorigin': [{'state': state.id, 'action': 'suspend'}]}}
        source = "SuspendAction, {}".format(self.set_source(current_condition, previous_condition, previousstate_condition))
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
        self._action_status = _issue

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
        result = {'function': str(self._function), 'special': str(self.__special),
                 'value': str(value_result), 'conditionset': str(self.conditionset.get()),
                 'previousconditionset': str(self.previousconditionset.get()),
                 'previousstate_conditionset': str(self.previousstate_conditionset.get()), 'actionstatus': {}}
        return result


# Class representing a single "se_add" action
class SeActionAddItem(SeActionSetItem):
    # Initialize the action
    # abitem: parent SeItem instance
    # name: Name of action
    def __init__(self, abitem, name: str):
        super().__init__(abitem, name)
        self._function = "add to list"

    def __repr__(self):
        return "SeAction Add {}".format(self._name)

    def write_to_logger(self):
        SeActionSetItem.write_to_logger(self)
        SeActionBase.write_to_logger(self)

    def _execute_set_add_remove(self, state, actionname, namevar, repeat_text, item, value, current_condition=None, previous_condition=None, previousstate_condition=None):
        value = value if isinstance(value, list) else [value]
        self._log_debug("{0}: Add '{1}' to '{2}'.{3}", actionname, value, item.property.path, repeat_text)
        value = item.property.value + value
        source = self.set_source(current_condition, previous_condition, previousstate_condition)
        self.update_webif_actionstatus(state, self._name, 'True')
        # noinspection PyCallingNonCallable
        item(value, caller=self._caller, source=source)

    def get(self):
        try:
            if self.__item is not None:
                item = str(self.__item.property.path)
            else:
                item = None
        except Exception:
            item = None
        try:
            val = self.__value.get()
            if val is not None:
                value = str(val)
            else:
                value = None
        except Exception:
            value = None
        result = {'function': str(self._function), 'item': item,
                 'value': value, 'conditionset': str(self.conditionset.get()),
                 'previousconditionset': str(self.previousconditionset.get()),
                 'previousstate_conditionset': str(self.previousstate_conditionset.get()), 'actionstatus': {}}
        return result


# Class representing a single "se_remove" action
class SeActionRemoveFirstItem(SeActionSetItem):
    # Initialize the action
    # abitem: parent SeItem instance
    # name: Name of action
    def __init__(self, abitem, name: str):
        super().__init__(abitem, name)
        self._function = "remove first from list"

    def __repr__(self):
        return "SeAction RemoveFirst {}".format(self._name)

    def write_to_logger(self):
        SeActionSetItem.write_to_logger(self)
        SeActionBase.write_to_logger(self)

    def _execute_set_add_remove(self, state, actionname, namevar, repeat_text, item, value, current_condition=None, previous_condition=None, previousstate_condition=None):
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
        source = self.set_source(current_condition, previous_condition, previousstate_condition)
        self.update_webif_actionstatus(state, self._name, 'True')
        item(currentvalue, caller=self._caller, source=source)

    def get(self):
        try:
            if self.__item is not None:
                item = str(self.__item.property.path)
            else:
                item = None
        except Exception:
            item = None
        try:
            val = self.__value.get()
            if val is not None:
                value = str(val)
            else:
                value = None
        except Exception:
            value = None
        result = {'function': str(self._function), 'item': item,
                 'value': value, 'conditionset': str(self.conditionset.get()),
                 'previousconditionset': str(self.previousconditionset.get()),
                 'previousstate_conditionset': str(self.previousstate_conditionset.get()), 'actionstatus': {}}
        return result


# Class representing a single "se_remove" action
class SeActionRemoveLastItem(SeActionSetItem):
    # Initialize the action
    # abitem: parent SeItem instance
    # name: Name of action
    def __init__(self, abitem, name: str):
        super().__init__(abitem, name)
        self._function = "remove last from list"

    def __repr__(self):
        return "SeAction RemoveLast {}".format(self._name)

    def write_to_logger(self):
        SeActionSetItem.write_to_logger(self)
        SeActionBase.write_to_logger(self)

    def _execute_set_add_remove(self, state, actionname, namevar, repeat_text, item, value, current_condition=None, previous_condition=None, previousstate_condition=None):
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
        source = self.set_source(current_condition, previous_condition, previousstate_condition)
        self.update_webif_actionstatus(state, self._name, 'True')
        item(currentvalue, caller=self._caller, source=source)

    def get(self):
        try:
            if self.__item is not None:
                item = str(self.__item.property.path)
            else:
                item = None
        except Exception:
            item = None
        try:
            val = self.__value.get()
            if val is not None:
                value = str(val)
            else:
                value = None
        except Exception:
            value = None
        result = {'function': str(self._function), 'item': item,
                 'value': value, 'conditionset': str(self.conditionset.get()),
                 'previousconditionset': str(self.previousconditionset.get()),
                 'previousstate_conditionset': str(self.previousstate_conditionset.get()), 'actionstatus': {}}
        return result


# Class representing a single "se_removeall" action
class SeActionRemoveAllItem(SeActionSetItem):
    # Initialize the action
    # abitem: parent SeItem instance
    # name: Name of action
    def __init__(self, abitem, name: str):
        super().__init__(abitem, name)
        self._function = "remove all from list"

    def __repr__(self):
        return "SeAction RemoveAll {}".format(self._name)

    def write_to_logger(self):
        SeActionSetItem.write_to_logger(self)
        SeActionBase.write_to_logger(self)

    def _execute_set_add_remove(self, state, actionname, namevar, repeat_text, item, value, current_condition=None, previous_condition=None, previousstate_condition=None):
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
        source = self.set_source(current_condition, previous_condition, previousstate_condition)
        self.update_webif_actionstatus(state, self._name, 'True')
        item(currentvalue, caller=self._caller, source=source)

    def get(self):
        try:
            if self.__item is not None:
                item = str(self.__item.property.path)
            else:
                item = None
        except Exception:
            item = None
        try:
            val = self.__value.get()
            if val is not None:
                value = str(val)
            else:
                value = None
        except Exception:
            value = None
        result = {'function': str(self._function), 'item': item,
                 'value': value, 'conditionset': str(self.conditionset.get()),
                 'previousconditionset': str(self.previousconditionset.get()),
                 'previousstate_conditionset': str(self.previousstate_conditionset.get()), 'actionstatus': {}}
        return result
