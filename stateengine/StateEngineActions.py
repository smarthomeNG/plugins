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


# Class representing a list of actions
class SeActions(StateEngineTools.SeItemChild):
    # Initialize the set of actions
    # abitem: parent SeItem instance
    def __init__(self, abitem):
        super().__init__(abitem)
        self.__actions = {}
        self.__unassigned_delays = {}
        self.__unassigned_repeats = {}
        self.__unassigned_orders = {}

    # Return number of actions in list
    def count(self):
        return len(self.__actions)

    # update action
    # attribute: name of attribute that defines action
    # value: value of the attribute
    def update(self, attribute, value):
        # Split attribute in function and action name
        func, name = StateEngineTools.partition_strip(attribute, "_")
        try:
            if func == "se_delay":
                # set delay
                if name not in self.__actions:
                    # If we do not have the action yet (delay-attribute before action-attribute), ...
                    self.__unassigned_delays[name] = value
                else:
                    self.__actions[name].update_delay(value)
                return
            elif func == "se_repeat":
                # set repeat
                if name not in self.__actions:
                    # If we do not have the action yet (repeat-attribute before action-attribute), ...
                    self.__unassigned_repeats[name] = value
                else:
                    self.__actions[name].update_repeat(value)
                return
            elif func == "se_order":
                # set order
                if name not in self.__actions:
                    # If we do not have the action yet (order-attribute before action-attribute), ...
                    self.__unassigned_orders[name] = value
                else:
                    self.__actions[name].update_order(value)
                return
            elif func == "se_action":  # and name not in self.__actions:
                self.__handle_combined_action_attribute(name, value)
            elif self.__ensure_action_exists(func, name):
                # update action
                self.__actions[name].update(value)
        except ValueError as ex:
            if name in self.__actions:
                del self.__actions[name]
            self._log_warning("Ignoring action {0} because: {1} (2)".format(attribute, str(ex)))
            #raise ValueError("Action {0}: {1}".format(attribute, str(ex)))

    # ensure that action exists and create if missing
    # func: action function
    # name: action name
    def __ensure_action_exists(self, func, name):
        # Check if action exists
        if name in self.__actions:
            return True

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
        else:
            return False

        if name in self.__unassigned_delays:
            action.update_delay(self.__unassigned_delays[name])
            del self.__unassigned_delays[name]

        if name in self.__unassigned_repeats:
            action.update_repeat(self.__unassigned_repeats[name])
            del self.__unassigned_repeats[name]

        if name in self.__unassigned_orders:
            action.update_order(self.__unassigned_orders[name])
            del self.__unassigned_orders[name]

        self.__actions[name] = action
        return True

    def __handle_combined_action_attribute(self, name, value_list):
        # value_list needs to be string or list
        if isinstance(value_list, str):
            value_list = [value_list, ]
        elif not isinstance(value_list, list):
            raise ValueError("Attribute 'se_action_{0}': Value must be a string or a list!".format(name))

        # parse parameters
        parameter = {'function': None, 'force': None, 'repeat': None, 'delay': 0, 'order': None}
        for entry in value_list:
            key, val = StateEngineTools.partition_strip(entry, ":")
            if key == "function":
                parameter[key] = StateEngineTools.cast_str(val)
            elif key == "force":
                parameter[key] = StateEngineTools.cast_bool(val)
            else:
                parameter[key] = val
        parameter['action'] = name

        # function given and valid?
        if parameter['function'] is None:
            raise ValueError("Attribute 'se_action_{0}: Parameter 'function' must be set!".format(name))
        if parameter['function'] not in ('set', 'force', 'run', 'byattr', 'trigger', 'special'):
            raise ValueError("Attribute 'se_action_{0}: Invalid value '{1}' for parameter 'function'!".format(name, parameter['function']))

        # handle force
        if parameter['force'] is not None:
            # Parameter force is supported only for type "set" and type "force"
            if parameter['function'] != "set" and parameter['function'] != "force":
                self._log_warning("Attribute 'se_action_{0}': Parameter 'force' not supported for function '{1}'".format(name, parameter['function']))
            elif parameter['force'] and parameter['function'] == "set":
                # Convert type "set" with force=True to type "force"
                self._log_info("Attribute 'se_action_{0}': Parameter 'function' changed from 'set' to 'force', because parameter 'force' is 'True'!".format(name))
                parameter['function'] = "force"
            elif not parameter['force'] and parameter['function'] == "force":
                # Convert type "force" with force=False to type "set"
                self._log_info("Attribute 'se_action_{0}': Parameter 'function' changed from 'force' to 'set', because parameter 'force' is 'False'!".format(name))
                parameter['function'] = "set"

        # create action based on function
        exists = False
        try:
            if parameter['function'] == "set":
                if self.__ensure_action_exists("se_set", name):
                    self.__raise_missing_parameter_error(parameter, 'to')
                    self.__actions[name].update(parameter['to'])
                    exists = True
            elif parameter['function'] == "force":
                if self.__ensure_action_exists("se_force", name):
                    self.__raise_missing_parameter_error(parameter, 'to')
                    self.__actions[name].update(parameter['to'])
                    exists = True
            elif parameter['function'] == "run":
                if self.__ensure_action_exists("se_run", name):
                    self.__raise_missing_parameter_error(parameter, 'eval')
                    self.__actions[name].update(parameter['eval'])
                    exists = True
            elif parameter['function'] == "byattr":
                if self.__ensure_action_exists("se_byattr", name):
                    self.__raise_missing_parameter_error(parameter, 'attribute')
                    self.__actions[name].update(parameter['attribute'])
                    exists = True
            elif parameter['function'] == "trigger":
                if self.__ensure_action_exists("se_trigger", name):
                    self.__raise_missing_parameter_error(parameter, 'logic')
                    if 'value' in parameter and parameter['value'] is not None:
                        self.__actions[name].update(parameter['logic'] + ':' + parameter['value'])
                    else:
                        self.__actions[name].update(parameter['logic'])
                    exists = True
            elif parameter['function'] == "special":
                if self.__ensure_action_exists("se_special", name):
                    self.__raise_missing_parameter_error(parameter, 'value')
                    self.__actions[name].update(parameter['value'])
                    exists = True
        except ValueError as ex:
            exists = False
            if name in self.__actions:
                del self.__actions[name]
            self._log_warning("Ignoring action {0} because: {1}".format(name, str(ex)))


        # add additional parameters
        if exists:
            if parameter['repeat'] is not None:
                self.__actions[name].update_repeat(parameter['repeat'])
            if parameter['delay'] != 0:
                self.__actions[name].update_delay(parameter['delay'])
            if parameter['order'] is not None:
                self.__actions[name].update_order(parameter['order'])

    # noinspection PyMethodMayBeStatic
    def __raise_missing_parameter_error(self, parameter, param_name):
        if param_name not in parameter or parameter[param_name] is None:
            raise ValueError("Attribute 'se_action_{0}: Parameter '{1}' must be set for function '{2}'!".format(parameter['action'], param_name, parameter['function']))

    # Check the actions optimize and complete them
    # item_state: item to read from
    def complete(self, item_state):
        for name in self.__actions:
            try:
                self.__actions[name].complete(item_state)
            except ValueError as ex:
                raise ValueError("State '{0}', Action '{1}': {2}".format(item_state.property.path, name, str(ex)))

    # Execute all actions
    # is_repeat: Inidicate if this is a repeated action without changing the state
    # item_allow_repeat: Is repeating actions generally allowed for the item?
    # additional_actions: SeActions-Instance containing actions which should be executed, too
    def execute(self, is_repeat: bool, allow_item_repeat: bool, additional_actions=None):
        actions = []
        for name in self.__actions:
            actions.append((self.__actions[name].get_order(), self.__actions[name]))
        if additional_actions is not None:
            for name in additional_actions.__actions:
                actions.append((additional_actions.__actions[name].get_order(), additional_actions.__actions[name]))
        for order, action in sorted(actions, key=lambda x: x[0]):
            action.execute(is_repeat, allow_item_repeat)

    # log all actions
    def write_to_logger(self):
        actions = []
        for name in self.__actions:
            actions.append((self.__actions[name].get_order(), self.__actions[name]))
        for order, action in sorted(actions, key=lambda x: x[0]):
            # noinspection PyProtectedMember
            self._log_info("Action '{0}':", action._name)
            self._log_increase_indent()
            action.write_to_logger()
            self._log_decrease_indent()
