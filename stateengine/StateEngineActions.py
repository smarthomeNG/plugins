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
from . import StateEngineAction
from . import StateEngineTools

import ast
import threading
import queue


# Class representing a list of actions
class SeActions(StateEngineTools.SeItemChild):

    # Initialize the set of actions
    # abitem: parent SeItem instance
    def __init__(self, abitem):
        super().__init__(abitem)
        self.__actions = {}
        self.__unassigned_delays = {}
        self.__unassigned_repeats = {}
        self.__unassigned_instantevals = {}
        self.__unassigned_orders = {}
        self.__unassigned_conditionsets = {}
        self.__unassigned_previousconditionsets = {}
        self.__unassigned_previousstate_conditionsets = {}
        self.__unassigned_modes = {}
        self.__queue = queue.Queue()
        self._action_lock = threading.Lock()
        self.__ab_alive = self._abitem.ab_alive

    def __repr__(self):
        return "SeActions, count {}".format(self.count())

    def dict_actions(self, type, state):
        result = {}
        for name in self.__actions:
            self._abitem._initactionname = name
            result.update({name: self.__actions[name].get()})
            try:
                result[name].update({'actionstatus': self._abitem.webif_infos[state][type][name].get('actionstatus')})
            except Exception:
                pass
            self._abitem._initactionname = None
        return result

    def reset(self):
        self.__actions = {}

    # Return number of actions in list
    def count(self):
        return len(self.__actions)

    # update action
    # attribute: name of attribute that defines action
    # value: value of the attribute
    def update(self, attribute, value):
        # Split attribute in function and action name
        func, name = StateEngineTools.partition_strip(attribute, "_")
        _count = 0
        _issue = None
        try:
            if func == "se_delay":
                # set delay
                if name not in self.__actions:
                    # If we do not have the action yet (delay-attribute before action-attribute), ...
                    self.__unassigned_delays[name] = value
                else:
                    _issue = self.__actions[name].update_delay(value)
                return _count, _issue
            elif func == "se_instanteval":
                # set instant calculation
                if name not in self.__actions:
                    # If we do not have the action yet (repeat-attribute before action-attribute), ...
                    self.__unassigned_instantevals[name] = value
                else:
                    _issue = self.__actions[name].update_instanteval(value)
                return _count, _issue
            elif func == "se_repeat":
                # set repeat
                if name not in self.__actions:
                    # If we do not have the action yet (repeat-attribute before action-attribute), ...
                    self.__unassigned_repeats[name] = value
                else:
                    _issue = self.__actions[name].update_repeat(value)
                return _count, _issue
            elif func == "se_conditionset":
                # set conditionset
                if name not in self.__actions:
                    # If we do not have the action yet (conditionset-attribute before action-attribute), ...
                    self.__unassigned_conditionsets[name] = value
                else:
                    _issue = self.__actions[name].update_conditionset(value)
                return _count, _issue
            elif func == "se_previousconditionset":
                # set conditionset
                if name not in self.__actions:
                    # If we do not have the action yet (conditionset-attribute before action-attribute), ...
                    self.__unassigned_previousconditionsets[name] = value
                else:
                    _issue = self.__actions[name].update_previousconditionset(value)
                return _count, _issue
            elif func == "se_previousstate_conditionset":
                # set conditionset
                if name not in self.__actions:
                    # If we do not have the action yet (conditionset-attribute before action-attribute), ...
                    self.__unassigned_previousstate_conditionsets[name] = value
                else:
                    _issue = self.__actions[name].update_previousstate_conditionset(value)
                return _count, _issue
            elif func == "se_mode":
                # set remove mode
                _issue_list = []
                if name not in self.__actions:
                    # If we do not have the action yet (mode-attribute before action-attribute), ...
                    self.__unassigned_modes[name] = value
                else:
                    _val, _issue = self.__actions[name].update_mode(value)
                    if _issue:
                        _issue_list.append(_issue)
                    _issue, _action = self.__check_mode_setting(name, _val, self.__actions[name].function, self.__actions[name])
                    if _issue:
                        _issue_list.append(_issue)
                    if _action:
                        self.__actions[name] = _action
                return _count, _issue_list
            elif func == "se_order":
                # set order
                if name not in self.__actions:
                    # If we do not have the action yet (order-attribute before action-attribute), ...
                    self.__unassigned_orders[name] = value
                else:
                    _issue = self.__actions[name].update_order(value)
                return _count, _issue
            elif func == "se_action":  # and name not in self.__actions:
                _issue = self.__handle_combined_action_attribute(name, value)
                _count += 1
            else:
                _issue_list = []
                _ensure_action, _issue = self.__ensure_action_exists(func, name)
                if _issue:
                    _issue_list.append(_issue)
                if _ensure_action:
                    # update action
                    _issue = self.__actions[name].update(value)
                    if _issue:
                        _issue_list.append(_issue)
                    _count += 1
                _issue = StateEngineTools.flatten_list(_issue_list)
        except ValueError as ex:
            if name in self.__actions:
                del self.__actions[name]
            _issue = {name: {'issue': ex, 'issueorigin': [{'state': 'unknown', 'action': self.__actions[name].function}]}}
            self._log_warning("Ignoring action {0} because: {1}", attribute, ex)
        return _count, _issue

    def __check_force_setting(self, name, value, function):
        _issue = None
        _returnfunction = function
        if value is not None:
            # Parameter force is supported only for type "set" and type "force"
            if function not in ["set", "force"]:
                _issue = {
                    name: {'issue': ['Parameter force not supported for this function'],
                           'attribute': 'force', 'issueorigin': [{'state': 'unknown', 'action': function}]}}
                _issue = "Parameter 'force' not supported for this function"
                self._log_warning("Attribute 'se_action_{0}': Parameter 'force' not supported "
                                  "for function '{1}'", name, function)
            elif value and function == "set":
                # Convert type "set" with force=True to type "force"
                self._log_info("Attribute 'se_action_{0}': Parameter 'function' changed from 'set' to 'force', "
                               "because parameter 'force' is 'True'!", name)
                _returnfunction = "force"
            elif not value and function == "force":
                # Convert type "force" with force=False to type "set"
                self._log_info("Attribute 'se_action_{0}': Parameter 'function' changed from 'force' to 'set', "
                               "because parameter 'force' is 'False'!", name)
                _returnfunction = "set"
        return _issue, _returnfunction
    def __check_mode_setting(self, name, value, function, action):
        if value is not None:
            possible_mode_list = ['first', 'last', 'all']
            _issue = None
            # Parameter mode is supported only for type "remove"
            if not "remove" in function:
                _issue = {name: {'issue': ['Parameter mode not supported for this function'], 'attribute': 'mode',
                                 'issueorigin': [{'state': 'unknown', 'action': function}]}}
                self._log_warning("Attribute 'se_action_{0}': Parameter 'mode' not supported for function '{1}'",
                                  name, function)
            elif function in ["remove", "remove all from list"]:
                # Convert type "remove" with mode to specific remove type
                if value in possible_mode_list:
                    if value == "all":
                        action = StateEngineAction.SeActionRemoveAllItem(self._abitem, name)
                    elif value == "first":
                        action = StateEngineAction.SeActionRemoveFirstItem(self._abitem, name)
                    elif value == "last":
                        action = StateEngineAction.SeActionRemoveLastItem(self._abitem, name)
                    self._log_info("Attribute 'se_action_{0}': Function 'remove' changed to '{1}'", name, value)
                else:
                    _issue = {
                        name: {'issue': ['Parameter {} not allowed for mode!'.format(value)], 'attribute': 'mode',
                               'issueorigin': [{'state': 'unknown', 'action': function}]}}
                    self._log_warning(
                        "Attribute 'se_action_{0}': Parameter '{1}' for 'mode' is wrong - can only be {2}",
                        name, value, possible_mode_list)
            return _issue, action
        return None, None

    # ensure that action exists and create if missing
    # func: action function
    # name: action name
    def __ensure_action_exists(self, func, name):
        # Check if action exists
        _issue = None
        if name in self.__actions:
            return True, _issue

        # Create action depending on function
        if func == "se_set":
            action = StateEngineAction.SeActionSetItem(self._abitem, name)
        elif func == "se_force":
            action = StateEngineAction.SeActionForceItem(self._abitem, name)
        elif func == "se_byattr":
            action = StateEngineAction.SeActionSetByattr(self._abitem, name)
        elif func == "se_trigger":
            action = StateEngineAction.SeActionTrigger(self._abitem, name)
        elif func == "se_run":
            action = StateEngineAction.SeActionRun(self._abitem, name)
        elif func == "se_special":
            action = StateEngineAction.SeActionSpecial(self._abitem, name)
        elif func == "se_add":
            action = StateEngineAction.SeActionAddItem(self._abitem, name)
        elif func == "se_remove" or func == "se_removeall":
            action = StateEngineAction.SeActionRemoveAllItem(self._abitem, name)
        elif func == "se_removefirst":
            action = StateEngineAction.SeActionRemoveFirstItem(self._abitem, name)
        elif func == "se_removelast":
            action = StateEngineAction.SeActionRemoveLastItem(self._abitem, name)
        else:
            return False, _issue
        _issue_list = []
        if name in self.__unassigned_delays:
            _issue = action.update_delay(self.__unassigned_delays[name])
            if _issue:
                _issue_list.append(_issue)
            del self.__unassigned_delays[name]

        if name in self.__unassigned_instantevals:
            _issue = action.update_instanteval(self.__unassigned_instantevals[name])
            if _issue:
                _issue_list.append(_issue)
            del self.__unassigned_instantevals[name]

        if name in self.__unassigned_repeats:
            _issue = action.update_repeat(self.__unassigned_repeats[name])
            if _issue:
                _issue_list.append(_issue)
            del self.__unassigned_repeats[name]

        if name in self.__unassigned_modes:
            _val, _issue = action.update_mode(self.__unassigned_modes[name])
            if _issue:
                _issue_list.append(_issue)
            _issue, action = self.__check_mode_setting(name, _val, func.replace("se_", ""), action)
            if _issue:
                _issue_list.append(_issue)
            del self.__unassigned_modes[name]

        if name in self.__unassigned_orders:
            _issue = action.update_order(self.__unassigned_orders[name])
            if _issue:
                _issue_list.append(_issue)
            del self.__unassigned_orders[name]

        if name in self.__unassigned_conditionsets:
            _issue = action.update_conditionset(self.__unassigned_conditionsets[name])
            if _issue:
                _issue_list.append(_issue)
            del self.__unassigned_conditionsets[name]

        if name in self.__unassigned_previousconditionsets:
            _issue = action.update_previousconditionset(self.__unassigned_previousconditionsets[name])
            if _issue:
                _issue_list.append(_issue)
            del self.__unassigned_previousconditionsets[name]

        if name in self.__unassigned_previousstate_conditionsets:
            _issue = action.update_previousconditionset(self.__unassigned_previousstate_conditionsets[name])
            if _issue:
                _issue_list.append(_issue)
            del self.__unassigned_previousstate_conditionsets[name]

        self.__actions[name] = action
        return True, _issue_list

    def __handle_combined_action_attribute(self, name, value_list):
        # value_list needs to be string or list
        if isinstance(value_list, str):
            value_list = [value_list, ]
        elif not isinstance(value_list, list):
            raise ValueError("Attribute 'se_action_{0}': Value must be a string or a list!".format(name))

        # parse parameters
        parameter = {'function': None, 'force': None, 'repeat': None, 'delay': 0, 'order': None, 'conditionset': None,
                     'previousconditionset': None, 'previousstate_conditionset': None, 'mode': None, 'instanteval': None}
        for entry in value_list:
            if isinstance(entry, dict):
                entry = list("{!s}:{!s}".format(k, v) for (k, v) in entry.items())[0]
            key, val = StateEngineTools.partition_strip(entry, ":")
            val = ":".join(map(str.strip, val.split(":")))
            if val[:1] == '[' and val[-1:] == ']':
                val = ast.literal_eval(val)
            if key == "function":
                parameter[key] = StateEngineTools.cast_str(val)
            elif key == "force":
                parameter[key] = StateEngineTools.cast_bool(val)
            else:
                parameter[key] = val
        parameter['action'] = name
        _issue_list = []
        # function given and valid?
        if parameter['function'] is None:
            raise ValueError("Attribute 'se_action_{0}: Parameter 'function' must be set!".format(name))
        if parameter['function'] not in ('set', 'force', 'run', 'byattr', 'trigger', 'special',
                                         'add', 'remove', 'removeall', 'removefirst', 'removelast'):
            raise ValueError("Attribute 'se_action_{0}: Invalid value '{1}' for parameter "
                             "'function'!".format(name, parameter['function']))

        _issue = None
        _issue, parameter['function'] = self.__check_force_setting(name, parameter['force'], parameter['function'])
        if _issue:
            _issue_list.append(_issue)
        _issue, _action = self.__check_mode_setting(name, parameter['mode'], parameter['function'], parameter['action'])
        if _issue:
            _issue_list.append(_issue)
        if _action:
            self.__actions[name] = _action
        # create action based on function
        exists = False
        try:
            if parameter['function'] == "set":
                _action_exists, _issue = self.__ensure_action_exists("se_set", name)
                if _issue:
                    _issue_list.append(_issue)
                if _action_exists:
                    self.__raise_missing_parameter_error(parameter, 'to')
                    self.__actions[name].update(parameter['to'])
                    exists = True
            elif parameter['function'] == "force":
                _action_exists, _issue = self.__ensure_action_exists("se_force", name)
                if _issue:
                    _issue_list.append(_issue)
                if _action_exists:
                    self.__raise_missing_parameter_error(parameter, 'to')
                    self.__actions[name].update(parameter['to'])
                    exists = True
            elif parameter['function'] == "run":
                _action_exists, _issue = self.__ensure_action_exists("se_run", name)
                if _issue:
                    _issue_list.append(_issue)
                if _action_exists:
                    self.__raise_missing_parameter_error(parameter, 'eval')
                    self.__actions[name].update(parameter['eval'])
                    exists = True
            elif parameter['function'] == "byattr":
                _action_exists, _issue = self.__ensure_action_exists("se_byattr", name)
                if _issue:
                    _issue_list.append(_issue)
                if _action_exists:
                    self.__raise_missing_parameter_error(parameter, 'attribute')
                    self.__actions[name].update(parameter['attribute'])
                    exists = True
            elif parameter['function'] == "trigger":
                _action_exists, _issue = self.__ensure_action_exists("se_trigger", name)
                if _issue:
                    _issue_list.append(_issue)
                if _action_exists:
                    self.__raise_missing_parameter_error(parameter, 'logic')
                    if 'value' in parameter and parameter['value'] is not None:
                        self.__actions[name].update(parameter['logic'] + ':' + parameter['value'])
                    else:
                        self.__actions[name].update(parameter['logic'])
                    exists = True
            elif parameter['function'] == "special":
                _action_exists, _issue = self.__ensure_action_exists("se_special", name)
                if _issue:
                    _issue_list.append(_issue)
                if _action_exists:
                    self.__raise_missing_parameter_error(parameter, 'value')
                    self.__actions[name].update(parameter['value'])
                    exists = True
            elif parameter['function'] == "add":
                _action_exists, _issue = self.__ensure_action_exists("se_add", name)
                if _issue:
                    _issue_list.append(_issue)
                if _action_exists:
                    self.__raise_missing_parameter_error(parameter, 'value')
                    self.__actions[name].update(parameter['value'])
                    exists = True
            elif parameter['function'] == "remove":
                _action_exists, _issue = self.__ensure_action_exists("se_remove", name)
                if _issue:
                    _issue_list.append(_issue)
                if _action_exists:
                    self.__raise_missing_parameter_error(parameter, 'value')
                    self.__actions[name].update(parameter['value'])
                    exists = True
            elif parameter['function'] == "removeall":
                _action_exists, _issue = self.__ensure_action_exists("se_removeall", name)
                if _issue:
                    _issue_list.append(_issue)
                if _action_exists:
                    self.__raise_missing_parameter_error(parameter, 'value')
                    self.__actions[name].update(parameter['value'])
                    exists = True
            elif parameter['function'] == "removefirst":
                _action_exists, _issue = self.__ensure_action_exists("se_removefirst", name)
                if _issue:
                    _issue_list.append(_issue)
                if _action_exists:
                    self.__raise_missing_parameter_error(parameter, 'value')
                    self.__actions[name].update(parameter['value'])
                    exists = True
            elif parameter['function'] == "removelast":
                _action_exists, _issue = self.__ensure_action_exists("se_removelast", name)
                if _issue:
                    _issue_list.append(_issue)
                if _action_exists:
                    self.__raise_missing_parameter_error(parameter, 'value')
                    self.__actions[name].update(parameter['value'])
                    exists = True

        except ValueError as ex:
            exists = False
            if name in self.__actions:
                del self.__actions[name]
            _issue = {name: {'issue': ex, 'issueorigin': [{'state': 'unknown', 'action': parameter['function']}]}}
            _issue_list.append(_issue)
            self._log_warning("Ignoring action {0} because: {1}", name, ex)

        # add additional parameters
        if exists:
            if parameter['instanteval'] is not None:
                _issue = self.__actions[name].update_instanteval(parameter['instanteval'])
                if _issue:
                    _issue_list.append(_issue)
            if parameter['repeat'] is not None:
                _issue = self.__actions[name].update_repeat(parameter['repeat'])
                if _issue:
                    _issue_list.append(_issue)
            if parameter['delay'] != 0:
                _issue = self.__actions[name].update_delay(parameter['delay'])
                if _issue:
                    _issue_list.append(_issue)
            if parameter['order'] is not None:
                _issue = self.__actions[name].update_order(parameter['order'])
                if _issue:
                    _issue_list.append(_issue)
            if parameter['conditionset'] is not None:
                _issue = self.__actions[name].update_conditionset(parameter['conditionset'])
                if _issue:
                    _issue_list.append(_issue)
            if parameter['previousconditionset'] is not None:
                _issue = self.__actions[name].update_previousconditionset(parameter['previousconditionset'])
                if _issue:
                    _issue_list.append(_issue)
            if parameter['previousstate_conditionset'] is not None:
                _issue = self.__actions[name].update_previousstate_conditionset(parameter['previousstate_conditionset'])
                if _issue:
                    _issue_list.append(_issue)
            if parameter['mode'] is not None:
                _val, _issue = self.__actions[name].update_mode(parameter['mode'])
                if _issue:
                    _issue_list.append(_issue)
                _issue, _action = self.__check_mode_setting(name, _val, parameter['function'], self.__actions[name])
                if _issue:
                    _issue_list.append(_issue)
                if _action:
                    self.__actions[name] = _action
        return _issue_list

    # noinspection PyMethodMayBeStatic
    def __raise_missing_parameter_error(self, parameter, param_name):
        if param_name not in parameter or parameter[param_name] is None:
            raise ValueError("Attribute 'se_action_{0}: Parameter '{1}' must be set for "
                             "function '{2}'!".format(parameter['action'], param_name, parameter['function']))

    # Check the actions optimize and complete them
    # item_state: item to read from
    def complete(self, item_state, evals_items=None):
        _status = {}
        for name in self.__actions:
            try:
                _status.update(self.__actions[name].complete(item_state, evals_items))
            except ValueError as ex:
                _status.update({name: {'issue': ex, 'issueorigin': {'state': item_state.property.path, 'action': 'unknown'}}})
                raise ValueError("State '{0}', Action '{1}': {2}".format(item_state.property.path, name, ex))
        return _status

    def set(self, value):
        for name in self.__actions:
            try:
                self.__actions[name].update(value)
            except ValueError as ex:
                raise ValueError("State '{0}', Action '{1}': {2}".format(value.property.path, name, ex))

    # Execute all actions
    # is_repeat: Indicate if this is a repeated action without changing the state
    # item_allow_repeat: Is repeating actions generally allowed for the item?
    # state: state item triggering the action
    # additional_actions: SeActions-Instance containing actions which should be executed, too
    def execute(self, is_repeat: bool, allow_item_repeat: bool, state, additional_actions=None):
        actions = []
        for name in self.__actions:
            self._log_develop("Append action {}", self.__actions[name])
            actions.append((self.__actions[name].get_order(), self.__actions[name]))
        if additional_actions is not None:
            for name in additional_actions.__actions:
                self._log_develop("Append additional action {}", additional_actions.__actions[name])
                actions.append((additional_actions.__actions[name].get_order(), additional_actions.__actions[name]))
        for order, action in sorted(actions, key=lambda x: x[0]):
            self.__queue.put([action, is_repeat, allow_item_repeat, state])
        self.__ab_alive = self._abitem.ab_alive
        if not self.__ab_alive:
            self._log_debug("StateEngine Plugin not running (anymore). Action queue not activated.")
            return
        self._action_lock.acquire()
        while not self.__queue.empty() and self.__ab_alive:
            job = self.__queue.get()
            self.__ab_alive = self._abitem.ab_alive
            if job is None or self.__ab_alive is False:
                self._log_debug("No jobs in action queue left or plugin not active anymore.")
                break
            (action, is_repeat, allow_item_repeat, state) = job
            action.execute(is_repeat, allow_item_repeat, state)

        if self._action_lock.locked():
            self._action_lock.release()

    def get(self):
        actions = []
        for name in self.__actions:
            actions.append((self.__actions[name].get_order(), {name: self.__actions[name].func}))
        finalactions = []
        for order, action in sorted(actions, key=lambda x: x[0]):
            finalactions.append(action)
        return finalactions

    # log all actions
    def write_to_logger(self):
        actions = []
        for name in self.__actions:
            actions.append((self.__actions[name].get_order(), self.__actions[name]))
        for order, action in sorted(actions, key=lambda x: x[0]):
            # noinspection PyProtectedMember
            self._log_info("Action '{0}':", action.name)
            self._log_increase_indent()
            self._abitem._initactionname = action.name
            action.write_to_logger()
            self._abitem._initactionname = None
            self._log_decrease_indent()
