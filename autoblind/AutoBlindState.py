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
from . import AutoBlindTools
from . import AutoBlindConditionSets
from . import AutoBlindActions
from . import AutoBlindValue


# Class representing an object state, consisting of name, conditions to be met and configured actions for state
class AbState(AutoBlindTools.AbItemChild):
    # Return id of state (= id of defining item)
    @property
    def id(self):
        return self.__id

    # Return name of state
    @property
    def name(self):
        return self.__name

    # Return text of state
    @property
    def text(self):
        return self.__text.get(self.__name)

    # Constructor
    # abitem: parent AbItem instance
    # item_state: item containing configuration of state
    def __init__(self, abitem, item_state):
        super().__init__(abitem)
        self.__item = item_state
        self.__id = self.__item.id()
        self.__name = ""
        self.__text = AutoBlindValue.AbValue(self._abitem, "State Name", False, "str")
        self.__conditions = AutoBlindConditionSets.AbConditionSets(self._abitem)
        self.__actions_enter_or_stay = AutoBlindActions.AbActions(self._abitem)
        self.__actions_enter = AutoBlindActions.AbActions(self._abitem)
        self.__actions_stay = AutoBlindActions.AbActions(self._abitem)
        self.__actions_leave = AutoBlindActions.AbActions(self._abitem)
        self._log_info("Init state {}", item_state.id())
        self._log_increase_indent()
        try:
            self.__fill(self.__item, 0)
        finally:
            self._log_decrease_indent()

    # Check conditions if state can be entered
    # returns: True = At least one enter condition set is fulfulled, False = No enter condition set is fulfilled
    def can_enter(self):
        self._log_info("Check if state '{0}' ('{1}') can be entered:", self.id, self.name)
        self._log_increase_indent()
        result = self.__conditions.one_conditionset_matching()
        self._log_decrease_indent()
        if result:
            self._log_info("State can be entered")
        else:
            self._log_info("State can not be entered")
        return result

    # log state data
    def write_to_log(self):
        self._log_info("State {0}:", self.id)
        self._log_increase_indent()
        self._log_info("Name: {0}", self.name)
        self.__text.write_to_logger()
        if self.__conditions.count() > 0:
            self._log_info("Condition sets to enter state:")
            self._log_increase_indent()
            self.__conditions.write_to_logger()
            self._log_decrease_indent()
        if self.__actions_enter.count() > 0:
            self._log_info("Actions to perform on enter:")
            self._log_increase_indent()
            self.__actions_enter.write_to_logger()
            self._log_decrease_indent()
        if self.__actions_stay.count() > 0:
            self._log_info("Actions to perform on stay:")
            self._log_increase_indent()
            self.__actions_stay.write_to_logger()
            self._log_decrease_indent()
        if self.__actions_enter_or_stay.count() > 0:
            self._log_info("Actions to perform on enter or stay:")
            self._log_increase_indent()
            self.__actions_enter_or_stay.write_to_logger()
            self._log_decrease_indent()
        if self.__actions_leave.count() > 0:
            self._log_info("Actions to perform on leave:")
            self._log_increase_indent()
            self.__actions_leave.write_to_logger()
            self._log_decrease_indent()
        self._log_decrease_indent()

    # run actions when entering the state
    # item_allow_repeat: Is repeating actions generally allowed for the item?
    def run_enter(self, allow_item_repeat: bool):
        self._log_increase_indent()
        self.__actions_enter.execute(False, allow_item_repeat, self.__actions_enter_or_stay)
        self._log_decrease_indent()

    # run actions when staying at the state
    # item_allow_repeat: Is repeating actions generally allowed for the item?
    def run_stay(self, allow_item_repeat: bool):
        self._log_increase_indent()
        self.__actions_stay.execute(True, allow_item_repeat, self.__actions_enter_or_stay)
        self._log_decrease_indent()

    # run actions when leaving the state
    # item_allow_repeat: Is repeating actions generally allowed for the item?
    def run_leave(self, allow_item_repeat: bool):
        self._log_increase_indent()
        self.__actions_leave.execute(False, allow_item_repeat)
        self._log_decrease_indent()

    # Read configuration from item and populate data in class
    # item_state: item to read from
    # recursion_depth: current recursion_depth (recursion is canceled after five levels)
    # item_autoblind: AutoBlind-Item defining items for conditions
    # abitem_object: Related AbItem instance for later determination of current age and current delay
    def __fill(self, item_state, recursion_depth):
        if recursion_depth > 5:
            self._log_error("{0}/{1}: to many levels of 'use'", self.id, item_state.id())
            return

        # Import data from other item if attribute "use" is found
        if "as_use" in item_state.conf:
            use_item = self._abitem.return_item(item_state.conf["as_use"])
            if use_item is not None:
                self.__fill(use_item, recursion_depth + 1)
            else:
                self._log_error("{0}: Referenced item '{1}' not found!", item_state.id(), item_state.conf["as_use"])

        # Get action sets and condition sets
        parent_item = item_state.return_parent()
        child_items = item_state.return_children()
        for child_item in child_items:
            child_name = AutoBlindTools.get_last_part_of_item_id(child_item)
            try:
                if child_name == "on_enter":
                    for attribute in child_item.conf:
                        self.__actions_enter.update(attribute, child_item.conf[attribute])
                elif child_name == "on_stay":
                    for attribute in child_item.conf:
                        self.__actions_stay.update(attribute, child_item.conf[attribute])
                elif child_name == "on_enter_or_stay":
                    for attribute in child_item.conf:
                        self.__actions_enter_or_stay.update(attribute, child_item.conf[attribute])
                elif child_name == "on_leave":
                    for attribute in child_item.conf:
                        self.__actions_leave.update(attribute, child_item.conf[attribute])
                elif child_name == "enter" or child_name.startswith("enter_"):
                    self.__conditions.update(child_name, child_item, parent_item)
            except ValueError as ex:
                raise ValueError("Condition {0}: {1}".format(child_name, str(ex)))

        # Actions defined directly in the item go to "enter_or_stay"
        for attribute in item_state.conf:
            self.__actions_enter_or_stay.update(attribute, item_state.conf[attribute])

        # if an item name is given, or if we do not have a name after returning from all recursions,
        # use item name as state name
        if str(item_state) != item_state.id() or (self.__name == "" and recursion_depth == 0):
            self.__name = str(item_state)
        if "as_name" in item_state.conf:
            self.__text.set_from_attr(item_state, "as_name", self.__text.get(None))
        elif self.__text.is_empty() and recursion_depth == 0:
            self.__text.set("value:" + self.__name)

        # Complete condition sets and actions at the end
        if recursion_depth == 0:
            self.__conditions.complete(item_state)
            self.__actions_enter.complete(item_state)
            self.__actions_stay.complete(item_state)
            self.__actions_enter_or_stay.complete(item_state)
            self.__actions_leave.complete(item_state)
