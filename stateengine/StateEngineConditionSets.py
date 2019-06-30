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
from . import StateEngineConditionSet
from . import StateEngineTools
from collections import OrderedDict

# Class representing a list of condition sets
class SeConditionSets(StateEngineTools.SeItemChild):

    # Initialize the list of condition sets
    # abitem: parent SeItem instance
    def __init__(self, abitem):
        super().__init__(abitem)
        self.__condition_sets = OrderedDict()

    # Return number of condition sets in list
    def count(self):
        return len(self.__condition_sets)

    # Add/update a condition set
    # name: Name of condition set
    # item: item containing settings for condition set
    # grandparent_item: grandparent item of item (containing the definition if items and evals)
    def update(self, name, item, grandparent_item):
        # Add condition set if not yet existing
        if name not in self.__condition_sets:
            self.__condition_sets[name] = StateEngineConditionSet.SeConditionSet(self._abitem, name, item)
        # Update this condition set
        self.__condition_sets[name].update(item, grandparent_item)

    # Check the condition sets, optimize and complete them
    # item_state: item to read from
    def complete(self, item_state):
        for name in self.__condition_sets:
            self.__condition_sets[name].complete(item_state)

    # Write all condition sets to logger
    def write_to_logger(self):
        for name in self.__condition_sets:
            self._log_info("Condition Set '{0}':", name)
            self._log_increase_indent()
            self.__condition_sets[name].write_to_logger()
            self._log_decrease_indent()

    # check if one of the conditions sets in the list is matching.
    # returns: True = one condition set is matching or no condition sets are defined, False: no condition set matching
    def one_conditionset_matching(self):
        if self.count() == 0:
            self._log_debug("No condition sets defined -> matching")
            self._abitem.lastconditionset_set('', '')
            return True
        for name in self.__condition_sets:
            if self.__condition_sets[name].all_conditions_matching():
                return True

        return False
