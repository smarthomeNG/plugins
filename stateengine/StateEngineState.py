#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2014-2018 Thomas Ernst                       offline@gmx.net
#  Copyright 2019- Onkel Andy                       onkelandy@hotmail.com
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
from lib.item.item import Item
from . import StateEngineTools
from . import StateEngineConditionSets
from . import StateEngineActions
from . import StateEngineValue
from . import StateEngineStruct
from lib.item import Items


# Class representing an object state, consisting of name, conditions to be met and configured actions for state
class SeState(StateEngineTools.SeItemChild):
    # Return id of state (= id of defining item)
    @property
    def id(self):
        return self.__id

    @property
    def state_item(self):
        return self.__item

    # Return name of state
    @property
    def name(self):
        return self.__name

    # Return leave actions
    @property
    def leaveactions(self):
        return self.__actions_leave

    # Return text of state
    @property
    def text(self):
        return self.__text.get(self.__name)

    # Return conditions
    @property
    def conditions(self):
        return self.__conditions

    @property
    def releasedby(self):
        return self.__release.get()

    # Constructor
    # abitem: parent SeItem instance
    # item_state: item containing configuration of state
    def __init__(self, abitem, item_state):
        super().__init__(abitem)
        self.itemsApi = Items.get_instance()
        self.__item = item_state
        self.__itemClass = Item
        try:
            self.__id = self.__item.property.path
            self._log_info("Init state {}", self.__id)
        except Exception as err:
            self.__id = None
            self._log_info("Problem init state ID of Item {}. {}", self.__item, err)
        self.__text = StateEngineValue.SeValue(self._abitem, "State Name", False, "str")
        self.__use = StateEngineValue.SeValue(self._abitem, "State configuration extension", True, "item")
        self.__release = StateEngineValue.SeValue(self._abitem, "State released by", True, "item")
        self.__name = ''
        self.__use_done = []
        self.__conditions = StateEngineConditionSets.SeConditionSets(self._abitem)
        self.__actions_enter_or_stay = StateEngineActions.SeActions(self._abitem)
        self.__actions_enter = StateEngineActions.SeActions(self._abitem)
        self.__actions_stay = StateEngineActions.SeActions(self._abitem)
        self.__actions_leave = StateEngineActions.SeActions(self._abitem)
        self._log_increase_indent()
        try:
            self.__fill(self.__item, 0)
        finally:
            self._log_decrease_indent()

    def __repr__(self):
        return "SeState item: {}, id {}.".format(self.__item, self.__id)

    # Check conditions if state can be entered
    # returns: True = At least one enter condition set is fulfilled, False = No enter condition set is fulfilled
    def can_enter(self):
        self._log_decrease_indent(10)
        self._log_info("Check if state '{0}' ('{1}') can be entered:", self.id, self.name)
        self._log_increase_indent()
        result = self.__conditions.one_conditionset_matching()
        self._log_decrease_indent()
        if result:
            self._log_info("State {} can be entered", self.id)
        else:
            self._log_info("State {} can not be entered", self.id)
        return result

    # log state data
    def write_to_log(self):
        self._abitem._initstate = self
        self._log_info("State {0}:", self.id)
        self._log_increase_indent()
        self.update_name(self.__item)
        self.__text.write_to_logger()
        self._log_info("Updating Web Interface...")
        self._log_increase_indent()
        self._abitem.update_webif(self.id, {'name': self.name,
                                            'conditionsets': self.__conditions.get(),
                                            'actions_enter': {},
                                            'actions_enter_or_stay': {},
                                            'actions_stay': {},
                                            'actions_leave': {},
                                            'leave': False, 'enter': False, 'stay': False})
        self._log_decrease_indent()
        self._log_info("Finished Web Interface Update")
        if self.__use_done:
            _log_se_use = self.__use_done[0] if len(self.__use_done) == 1 else self.__use_done
            self._log_info("State configuration extended by se_use: {}", _log_se_use)
        self.__release.write_to_logger()
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
            self._abitem.update_webif([self.id, 'actions_enter'], self.__actions_enter.dict_actions)

        if self.__actions_stay.count() > 0:
            self._log_info("Actions to perform on stay:")
            self._log_increase_indent()
            self.__actions_stay.write_to_logger()
            self._log_decrease_indent()
            self._abitem.update_webif([self.id, 'actions_stay'], self.__actions_stay.dict_actions)

        if self.__actions_enter_or_stay.count() > 0:
            self._log_info("Actions to perform on enter or stay:")
            self._log_increase_indent()
            self.__actions_enter_or_stay.write_to_logger()
            self._log_decrease_indent()
            self._abitem.update_webif([self.id, 'actions_enter_or_stay'], self.__actions_enter_or_stay.dict_actions)

        if self.__actions_leave.count() > 0:
            self._log_info("Actions to perform on leave (instant leave: {})", self._abitem.instant_leaveaction)
            self._log_increase_indent()
            self.__actions_leave.write_to_logger()
            self._log_decrease_indent()
            self._abitem.update_webif([self.id, 'actions_leave'], self.__actions_leave.dict_actions)

        self._log_decrease_indent()

    # run actions when entering the state
    # item_allow_repeat: Is repeating actions generally allowed for the item?
    def run_enter(self, allow_item_repeat: bool):
        self._log_increase_indent()
        _key_leave = ['{}'.format(self.id), 'leave']
        _key_stay = ['{}'.format(self.id), 'stay']
        _key_enter = ['{}'.format(self.id), 'enter']
        self._abitem.update_webif(_key_leave, False)
        self._abitem.update_webif(_key_stay, False)
        self._abitem.update_webif(_key_enter, True)
        self.__actions_enter.execute(False, allow_item_repeat, self, self.__actions_enter_or_stay)
        self._log_decrease_indent(50)
        self._log_increase_indent()
        self._log_debug("Update web interface enter {}", self.id)
        self._log_increase_indent()
        self._abitem.update_webif([self.id, 'actions_enter_or_stay'], self.__actions_enter_or_stay.dict_actions)
        self._abitem.update_webif([self.id, 'actions_enter'], self.__actions_enter.dict_actions)
        self._log_decrease_indent()
        self._log_decrease_indent()

    # run actions when staying at the state
    # item_allow_repeat: Is repeating actions generally allowed for the item?
    def run_stay(self, allow_item_repeat: bool):
        self._log_increase_indent()
        _key_leave = ['{}'.format(self.id), 'leave']
        _key_stay = ['{}'.format(self.id), 'stay']
        _key_enter = ['{}'.format(self.id), 'enter']
        self._abitem.update_webif(_key_leave, False)
        self._abitem.update_webif(_key_stay, True)
        self._abitem.update_webif(_key_enter, False)
        self.__actions_stay.execute(True, allow_item_repeat, self, self.__actions_enter_or_stay)
        self._log_decrease_indent(50)
        self._log_increase_indent()
        self._log_debug("Update web interface stay {}", self.id)
        self._log_increase_indent()
        self._abitem.update_webif([self.id, 'actions_enter_or_stay'], self.__actions_enter_or_stay.dict_actions)
        self._abitem.update_webif([self.id, 'actions_stay'], self.__actions_stay.dict_actions)
        self._log_decrease_indent()
        self._log_decrease_indent()

    # run actions when leaving the state
    # item_allow_repeat: Is repeating actions generally allowed for the item?
    def run_leave(self, allow_item_repeat: bool):
        self._log_increase_indent()
        for elem in self._abitem.webif_infos:
            _key_leave = ['{}'.format(elem), 'leave']
            self._abitem.update_webif(_key_leave, False)
            #self._log_debug('set leave for {} to false', elem)
        self.__actions_leave.execute(False, allow_item_repeat, self)
        self._log_decrease_indent(50)
        self._log_increase_indent()
        self._log_debug("Update web interface leave {}", self.id)
        self._log_increase_indent()
        self._abitem.update_webif([self.id, 'actions_leave'], self.__actions_leave.dict_actions)
        self._log_decrease_indent()
        self._log_decrease_indent()

    def refill(self):
        cond1 = not self.__use.is_empty() and "eval" in self.__use.get_type()
        cond2 = not self.__release.is_empty() and ("eval" in self.__release.get_type() or "item" in self.__release.get_type())
        if cond1 and cond2:
            self._log_debug("State {}: se_use attribute including eval and se_released_by "
                            "attribute including item or eval - updating state conditions and actions", self.__name)
            self._log_increase_indent()
            self.__fill(self.__item, 0, "refill")
            self._log_decrease_indent()
        elif cond1:
            self._log_debug("State {}: se_use attribute including eval "
                            "- updating state conditions and actions", self.__name)
            self._log_increase_indent()
            self.__fill(self.__item, 0, "refill")
            self._log_decrease_indent()
        elif cond2:
            self._log_debug("State {}: se_released_by attribute including eval or item "
                            "- updating released by states", self.__name)
            self._log_increase_indent()
            self._abitem.update_releasedby(self)
            self._log_decrease_indent()

    def update_releasedby_internal(self):
        _returnvalue, _returntype = self.__release.set_from_attr(self.__item, "se_released_by")
        return _returnvalue, _returntype, self.releasedby

    def update_name(self, item_state, recursion_depth=0):
        # if an item name is given, or if we do not have a name after returning from all recursions,
        # use item name as state name
        if "se_name" in item_state.conf:
            self.__text.set_from_attr(item_state, "se_name")
        elif str(item_state) != item_state.property.path or (self.__name == "" and recursion_depth == 0):
            _name = str(item_state).split('.')[-1]
            self.__text.set(_name)
        elif self.__text.is_empty() and recursion_depth == 0:
            self.__text.set("value:" + self.__name)
        self.__name = self.text
        return self.__name

    # Read configuration from item and populate data in class
    # item_state: item to read from
    # recursion_depth: current recursion_depth (recursion is canceled after five levels)
    # item_stateengine: StateEngine-Item defining items for conditions
    # abitem_object: Related SeItem instance for later determination of current age and current delay
    def __fill(self, item_state, recursion_depth, se_use=None):
        if recursion_depth > 5:
            self._log_error("{0}/{1}: too many levels of 'use'", self.id, item_state.property.path)
            return
        # Import data from other item if attribute "use" is found
        if "se_use" in item_state.conf:
            self.__use.set_from_attr(item_state, "se_use")
            _use = self.__use.get()
            if self.__use.is_empty() or _use is None:
                self._log_warning("se_use is set up in a wrong way - ignoring {}", _use)
            else:
                _use = [_use] if not isinstance(_use, list) else StateEngineTools.flatten_list(_use)

                for loop, element in enumerate(_use):
                    try:
                        _name = element.property.path
                    except Exception:
                        _name = element
                    _fill = True
                    _path = None
                    if isinstance(element, StateEngineStruct.SeStruct):
                        _path = element.property.path
                        text1 = "Reading struct {0}. It is{1} a valid struct for the state configuration.{2}"
                        _fill = element.property.valid_se_use
                        valid1 = " NOT" if _fill is False else ""
                        valid2 = " Ignoring." if _fill is False else ""
                        self._log_info(text1, _path, valid1, valid2)
                    elif isinstance(element, self.__itemClass):
                        _path = element.property.path
                        text1 = "Reading Item {0}. It is{1} a valid item for the state configuration.{2}"
                        valid1 = " NOT" if _fill is False else " most likely"
                        valid2 = " Ignoring." if _fill is False else ""
                        self._log_info(text1, _path, valid1, valid2)

                    if _path is None:
                        if not isinstance(element, str):
                            self._log_warning("se_use {} is not valid.", element)
                    elif _fill and element not in self.__use_done:
                        #self._log_debug("Adding {} again to state fill function.", _name)
                        self.__use_done.append(element)
                        self.__fill(element, recursion_depth + 1, _name)
        if "se_released_by" in item_state.conf:
            #_release_by_value, _release_by_type = self.__release.set_from_attr(item_state, "se_released_by")
            _release_result = self.releasedby
            self._log_debug("(fill) State {} has released attribute result: {}", item_state.property.path, _release_result)

        # Get action sets and condition sets
        parent_item = item_state.return_parent()
        child_items = item_state.return_children()
        _conditioncount = 0
        _enter_actioncount = 0
        _enter_stay_actioncount = 0
        _leave_actioncount = 0
        _stay_actioncount = 0
        for child_item in child_items:
            child_name = StateEngineTools.get_last_part_of_item_id(child_item)
            try:
                if child_name == "on_enter":
                    for attribute in child_item.conf:
                        _enter_actioncount += 1
                        self.__actions_enter.update(attribute, child_item.conf[attribute])
                elif child_name == "on_stay":
                    for attribute in child_item.conf:
                        _stay_actioncount += 1
                        self.__actions_stay.update(attribute, child_item.conf[attribute])
                elif child_name == "on_enter_or_stay":
                    for attribute in child_item.conf:
                        _enter_stay_actioncount += 1
                        self.__actions_enter_or_stay.update(attribute, child_item.conf[attribute])
                elif child_name == "on_leave":
                    for attribute in child_item.conf:
                        _leave_actioncount += 1
                        self.__actions_leave.update(attribute, child_item.conf[attribute])
                elif child_name == "enter" or child_name.startswith("enter_"):
                    _conditioncount += 1
                    self.__conditions.update(child_name, child_item, parent_item)
            except ValueError as ex:
                raise ValueError("Condition {0} error: {1}".format(child_name, ex))
        # Actions defined directly in the item go to "enter_or_stay"
        for attribute in item_state.conf:
            _enter_stay_actioncount += self.__actions_enter_or_stay.update(attribute, item_state.conf[attribute]) or 0

        _total_actioncount = _enter_actioncount + _stay_actioncount + _enter_stay_actioncount + _leave_actioncount

        self.update_name(item_state, recursion_depth)

        # Complete condition sets and actions at the end
        if recursion_depth == 0:
            self.__conditions.complete(item_state)

            self.__actions_enter.complete(item_state, self.__conditions.evals_items)
            self.__actions_stay.complete(item_state, self.__conditions.evals_items)
            self.__actions_enter_or_stay.complete(item_state, self.__conditions.evals_items)
            self.__actions_leave.complete(item_state, self.__conditions.evals_items)

        _summary = "{} on_enter, {} on_stay , {} on_enter_or_stay, {} on_leave"
        if se_use is not None:
            self._log_debug("Added {} action(s) based on se_use {}. " + _summary, _total_actioncount, se_use,
                           _enter_actioncount, _stay_actioncount, _enter_stay_actioncount, _leave_actioncount)
            self._log_debug("Added {} condition set(s) based on se_use: {}", _conditioncount, se_use)
        else:
            self._log_debug("Added {} action(s) based on item configuration: " + _summary, _total_actioncount,
                           _enter_actioncount, _stay_actioncount, _enter_stay_actioncount, _leave_actioncount)
            self._log_debug("Added {} condition set(s) based on item configuration", _conditioncount)
