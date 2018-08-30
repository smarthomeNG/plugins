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
from . import AutoBlindCondition
from . import AutoBlindTools


# Class representing a set of conditions
class AbConditionSet(AutoBlindTools.AbItemChild):
    # Name of condition set
    @property
    def name(self):
        return self.__name

    # List of conditions that are part of this condition set
    @property
    def conditions(self):
        return self.__conditions

    # Initialize the condition set
    # abitem: parent AbItem instance
    # name: Name of condition set
    def __init__(self, abitem, name):
        super().__init__(abitem)
        self.__name = name
        self.__conditions = {}

    # Update condition set
    # item: item containing settings for condition set
    # grandparent_item: grandparent item of item (containing the definition if items and evals)
    def update(self, item, grandparent_item):
        # Update conditions in condition set
        if item is not None:
            for attribute in item.conf:
                func, name = AutoBlindTools.partition_strip(attribute, "_")
                if name == "":
                    continue

                try:
                    # update this condition
                    if name not in self.__conditions:
                        self.__conditions[name] = AutoBlindCondition.AbCondition(self._abitem, name)
                    self.__conditions[name].set(func, item.conf[attribute])

                except ValueError as ex:
                    raise ValueError("Condition {0}: {1}".format(name, str(ex)))

        # Update item from grandparent_item
        for attribute in grandparent_item.conf:
            func, name = AutoBlindTools.partition_strip(attribute, "_")
            if name == "":
                continue

            # update item/eval in this condition
            if func == "as_item" or func == "as_eval":
                if name not in self.__conditions:
                    self.__conditions[name] = AutoBlindCondition.AbCondition(self._abitem, name)
                try:
                    self.__conditions[name].set(func, grandparent_item.conf[attribute])
                except ValueError as ex:
                    text = "Item '{0}', Attribute '{1}': {2}"
                    raise ValueError(text.format(grandparent_item.id(), attribute, str(ex)))

    # Check the condition set, optimize and complete it
    # item_state: item to read from
    def complete(self, item_state):
        conditions_to_remove = []
        # try to complete conditions
        for name in self.conditions:
            try:
                if not self.__conditions[name].complete(item_state):
                    conditions_to_remove.append(name)
                    continue
            except ValueError as ex:
                text = "State '{0}', Condition Set '{1}', Condition '{2}': {3}"
                raise ValueError(text.format(item_state.id(), self.name, name, str(ex)))

        # Remove incomplete conditions
        for name in conditions_to_remove:
            del self.conditions[name]

    # Write the whole condition set to the logger
    def write_to_logger(self):
        for name in self.__conditions:
            self._log_info("Condition '{0}':", name)
            self._log_increase_indent()
            self.__conditions[name].write_to_logger()
            self._log_decrease_indent()

    # Check all conditions in the condition set. Return
    # returns: True = all conditions in set are matching, False = at least one condition is not matching
    def all_conditions_matching(self):
        try:
            self._log_info("Check condition set '{0}':", self.__name)
            self._log_increase_indent()
            for name in self.__conditions:
                if not self.__conditions[name].check():
                    return False
            return True
        finally:
            self._log_decrease_indent()
