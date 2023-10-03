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

from . import StateEngineTools
from . import StateEngineConditionSets
from . import StateEngineActions
from . import StateEngineValue
from . import StateEngineStruct

from lib.item import Items
from lib.item.item import Item
from copy import copy


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

    # Return orphaned definitions
    @property
    def unused_attributes(self):
        return self.__unused_attributes

    # Return used definitions
    @property
    def used_attributes(self):
        return self.__used_attributes

    # Return used definitions
    @property
    def action_status(self):
        return self.__action_status

    # Return releasedby information
    @property
    def releasedby(self):
        return self.__releasedby.get()

    @releasedby.setter
    def releasedby(self, value):
        self.__releasedby.set(value, "", True, None, False)

    @property
    def order(self):
        return self.__order.get()

    @order.setter
    def order(self, value):
        self.__order.set(value, "", True, None, False)

    @property
    def can_release(self):
        return self.__can_release.get()

    @can_release.setter
    def can_release(self, value):
        self.__can_release.set(value, "", True, None, False)

    @property
    def has_released(self):
        return self.__has_released.get()

    @has_released.setter
    def has_released(self, value):
        self.__has_released.set(value, "", True, None, False)

    @property
    def was_releasedby(self):
        return self.__was_releasedby.get()

    @was_releasedby.setter
    def was_releasedby(self, value):
        self.__was_releasedby.set(value, "", True, None, False)

    @property
    def is_copy_for(self):
        return self.__is_copy_for.get()

    @is_copy_for.setter
    def is_copy_for(self, value):
        if value:
            webif_id = value.id
        else:
            webif_id = None
        _key_copy = ['{}'.format(self.id), 'is_copy_for']
        self._abitem.update_webif(_key_copy, webif_id)
        self.__is_copy_for.set(value, "", True, None, False)

    # Constructor
    # abitem: parent SeItem instance
    # item_state: item containing configuration of state
    def __init__(self, abitem, item_state):
        super().__init__(abitem)
        self.itemsApi = Items.get_instance()
        self.__item = item_state
        self.__itemClass = Item
        self.__is_copy_for = StateEngineValue.SeValue(self._abitem, "State is a copy to release")
        try:
            self.__id = self.__item.property.path
            self._log_info("Init state {}", self.__id)
        except Exception as ex:
            self.__id = None
            self._log_info("Problem init state ID of Item {}. {}", self.__item, ex)
        self.__text = StateEngineValue.SeValue(self._abitem, "State Name", False, "str")
        self.__use = StateEngineValue.SeValue(self._abitem, "State configuration extension", True, "item")
        self.__releasedby = StateEngineValue.SeValue(self._abitem, "State can be released by", True, "str")
        self.__can_release = StateEngineValue.SeValue(self._abitem, "State can release")
        self.__has_released = StateEngineValue.SeValue(self._abitem, "State has released")
        self.__was_releasedby = StateEngineValue.SeValue(self._abitem, "State was released by")
        self.__name = ''
        self.__unused_attributes = {}
        self.__used_attributes = {}
        self.__action_status = {}
        self.__use_done = []
        self.__conditions = StateEngineConditionSets.SeConditionSets(self._abitem)
        self.__actions_enter_or_stay = StateEngineActions.SeActions(self._abitem)
        self.__actions_enter = StateEngineActions.SeActions(self._abitem)
        self.__actions_stay = StateEngineActions.SeActions(self._abitem)
        self.__actions_leave = StateEngineActions.SeActions(self._abitem)
        self.__order = StateEngineValue.SeValue(self._abitem, "State Order", False, "num")
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
        self.__is_copy_for.write_to_logger()
        self.__releasedby.write_to_logger()
        self.__can_release.write_to_logger()
        result = self.__conditions.one_conditionset_matching(self)
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
        self._abitem.set_variable("current.state_name", self.name)
        self._abitem.set_variable("current.state_id", self.id)
        self.__text.write_to_logger()
        self.__order.write_to_logger()
        self.__is_copy_for.write_to_logger()
        self.__releasedby.write_to_logger()
        self.__can_release.write_to_logger()
        self.__use.write_to_logger()

        self._log_info("Updating Web Interface...")
        self._log_increase_indent()
        self._abitem.update_webif(self.id, {'name': self.name,
                                            'conditionsets': self.__conditions.get(),
                                            'actions_enter': {},
                                            'actions_enter_or_stay': {},
                                            'actions_stay': {},
                                            'actions_leave': {},
                                            'leave': False, 'enter': False, 'stay': False,
                                            'is_copy_for': None, 'releasedby': None})
        self._log_decrease_indent()
        self._log_info("Finished Web Interface Update")

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
            self._abitem.update_webif([self.id, 'actions_enter'], self.__actions_enter.dict_actions('actions_enter', self.id))

        if self.__actions_stay.count() > 0:
            self._log_info("Actions to perform on stay:")
            self._log_increase_indent()
            self.__actions_stay.write_to_logger()
            self._log_decrease_indent()
            self._abitem.update_webif([self.id, 'actions_stay'], self.__actions_stay.dict_actions('actions_stay', self.id))

        if self.__actions_enter_or_stay.count() > 0:
            self._log_info("Actions to perform on enter or stay:")
            self._log_increase_indent()
            self.__actions_enter_or_stay.write_to_logger()
            self._log_decrease_indent()
            self._abitem.update_webif([self.id, 'actions_enter_or_stay'], self.__actions_enter_or_stay.dict_actions('actions_enter_or_stay', self.id))

        if self.__actions_leave.count() > 0:
            self._log_info("Actions to perform on leave (instant leave: {})", self._abitem.instant_leaveaction)
            self._log_increase_indent()
            self.__actions_leave.write_to_logger()
            self._log_decrease_indent()
            self._abitem.update_webif([self.id, 'actions_leave'], self.__actions_leave.dict_actions('actions_leave', self.id))
        self._abitem.set_variable("current.state_name", "")
        self._abitem.set_variable("current.state_id", "")
        self._log_decrease_indent()

    def update_order(self, value=None):
        if isinstance(value, list):
            if len(value) > 1:
                _default_value = self.__order.get()
                self._log_warning("se_stateorder for item {} can not be defined as a list"
                                  " ({}). Using default value {}.", self.id, value, _default_value)
                value = _default_value
            elif len(value) == 1:
                value = value[0]
        if value is None and "se_stateorder" in self.__item.conf:
            _, _, _, _issue = self.__order.set_from_attr(self.__item, "se_stateorder")
        elif value is not None:
            _, _, _issue = self.__order.set(value, "", True, None, False)
        else:
            _issue = [None]

        return _issue

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
        if self.__actions_enter_or_stay.count() > 0:
            self._abitem.update_webif([self.id, 'actions_enter_or_stay'], self.__actions_enter_or_stay.dict_actions('actions_enter_or_stay', self.id))
        if self.__actions_enter.count() > 0:
            self._abitem.update_webif([self.id, 'actions_enter'], self.__actions_enter.dict_actions('actions_enter', self.id))
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
        if self.__actions_enter_or_stay.count() > 0:
            self._abitem.update_webif([self.id, 'actions_enter_or_stay'], self.__actions_enter_or_stay.dict_actions('actions_enter_or_stay', self.id))
        if self.__actions_stay.count() > 0:
            self._abitem.update_webif([self.id, 'actions_stay'], self.__actions_stay.dict_actions('actions_stay', self.id))
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
        if self.__actions_leave.count() > 0:
            self._abitem.update_webif([self.id, 'actions_leave'], self.__actions_leave.dict_actions('actions_leave', self.id))
        self._log_decrease_indent()
        self._log_decrease_indent()

    def refill(self):
        cond_refill = not self.__use.is_empty() and ("eval" in self.__use.get_type() or "item" in self.__use.get_type())
        if cond_refill:
            self._log_debug("State {}: se_use attribute including item or eval "
                            "- updating state conditions and actions", self.__name)
            self._log_increase_indent()
            self.__fill(self.__item, 0, "reinit")
            self._log_decrease_indent()

    def update_releasedby_internal(self, states=None):
        if states == []:
            _returnvalue, _returntype, _issue = self.__releasedby.set([None], "", True, None, False)
        elif states:
            self._log_develop("Setting releasedby to {}", states)
            _returnvalue, _returntype, _issue = self.__releasedby.set(states, "", True, None, False)
            self._log_develop("returnvalue {}", _returnvalue)
        else:
            _returnvalue, _returntype, _, _issue = self.__releasedby.set_from_attr(self.__item, "se_released_by")
        return _returnvalue, _returntype, _issue

    def update_can_release_internal(self, states):
        if states == []:
            _returnvalue, _returntype, _issue = self.__can_release.set([None], "", True, None, False)
        elif states:
            _returnvalue, _returntype, _issue = self.__can_release.set(states, "", True, None, False)
        else:
            _returnvalue, _returntype, _issue = [None], [None], None
        return _returnvalue, _returntype, _issue

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

    def __fill_list(self, item_states, recursion_depth, se_use=None):
        for i, element in enumerate(item_states):
            if element == self.state_item:
                self._log_info("Use element {} is same as current state - Ignoring.", element)
            elif element is not None and element not in self.__use_done:
                try:
                    _use = se_use[i]
                except Exception:
                    _use = element
                self.__fill(element, recursion_depth, _use)
                self.__use_done.append(element)

    # Read configuration from item and populate data in class
    # item_state: item to read from
    # recursion_depth: current recursion_depth (recursion is canceled after five levels)
    # se_use: If se_use Attribute is used or not
    def __fill(self, item_state, recursion_depth, se_use=None):
        def update_unused(used_attributes, type, name):
            #filtered_dict = {key: value for key, value in self.__unused_attributes.items() if key not in used_attributes}
            #self.__unused_attributes = copy(filtered_dict)

            for item, nested_dict in self.__unused_attributes.items():
                if item in used_attributes.keys():
                    used_attributes[item].update({type: name})
                    used_attributes[item].update(nested_dict)
                    self.__used_attributes.update(used_attributes)

        def update_action_status(action_status, actiontype):
            if action_status is None:
                return
            action_status = StateEngineTools.flatten_list(action_status)
            if isinstance(action_status, list):
                for e in action_status:
                    update_action_status(e, actiontype)
                return
            for itm, dct in action_status.items():
                if itm not in self.__action_status:
                    self.__action_status.update({itm: dct})

            for (itm, dct) in action_status.items():
                issues = dct.get('issue')
                if issues:
                    if isinstance(issues, list):
                        self.__action_status[itm]['issue'].extend(
                            [issue for issue in issues if issue not in self.__action_status[itm]['issue']])
                    origin_list = self.__action_status[itm].get('issueorigin', [])
                    new_list = origin_list.copy()
                    for i, listitem in enumerate(origin_list):
                        entry_unknown = {'state': 'unknown', 'action': listitem.get('action')}
                        entry_unknown2 = {'state': 'unknown', 'action': 'unknown'}
                        entry_notype = {'state': self.id, 'action': listitem.get('action')}
                        entry_final = {'state': self.id, 'action': listitem.get('action'), 'type': actiontype}

                        if listitem in (entry_unknown, entry_unknown2, entry_notype):
                            new_list[i] = entry_final
                        elif entry_final not in origin_list:
                            new_list.append(entry_final)

                    self.__action_status[itm]['issueorigin'] = new_list

            filtered_dict = {}
            for key, nested_dict in self.__action_status.items():
                filtered_dict.update({key: {}})
                filtered_dict[key].update({'used in': actiontype})
                filtered_dict[key].update(nested_dict)
                #self._log_develop("Add {} to used {}", key, filtered_dict)
            self.__used_attributes = copy(filtered_dict)
            filtered_dict = {key: value for key, value in self.__action_status.items()
                             if value.get('issue') not in [[], [None], None]}
            self.__action_status = filtered_dict
            #self._log_develop("Updated action status: {}, updated used {}", self.__action_status, self.__used_attributes)

        if se_use == "reinit":
            self._log_develop("Resetting conditions and actions at re-init")
            self.__conditions.reset()
            self.__actions_enter_or_stay.reset()
            self.__actions_enter.reset()
            self.__actions_stay.reset()
            self.__actions_leave.reset()
            self.__use_done = []
        if recursion_depth > 5:
            self._log_error("{0}/{1}: too many levels of 'use'", self.id, item_state.property.path)
            return
        # Import data from other item if attribute "use" is found
        if "se_use" in item_state.conf:
            _returnvalue, _returntype, _, _issue = self.__use.set_from_attr(item_state, "se_use")
            _configvalue = copy(_returnvalue)
            _configvalue = [_configvalue] if not isinstance(_configvalue, list) else _configvalue
            self._abitem.update_issues('config', {item_state.property.path: {'issue': _issue, 'attribute': 'se_use'}})
            _use = self.__use.get()
            if self.__use.is_empty() or _use is None:
                _issue = "se_use {} is set up in a wrong way".format(_use)
                self._abitem.update_issues('config',
                                           {item_state.property.path: {'issue': _issue, 'attribute': 'se_use'}})
                self._log_warning("{} - ignoring.", _issue)
            else:
                _use = [_use] if not isinstance(_use, list) else _use
                _returntype = [_returntype] if not isinstance(_returntype, list) else _returntype
                cleaned_use_list = []
                for i, element in enumerate(_use):
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
                        if _fill is False:
                            _issue = "Not valid. Ensure it is addressed by <structpath>.rules.<state>."
                            self._abitem.update_issues('struct', {_path: {'issue': _issue}})
                        elif _configvalue and _configvalue[i] not in cleaned_use_list:
                            cleaned_use_list.append(_configvalue[i])
                    elif isinstance(element, self.__itemClass):
                        _path = element.property.path
                        text1 = "Reading Item {0}. It is{1} a valid item for the state configuration.{2}"
                        valid1 = " NOT" if _fill is False else " most likely"
                        valid2 = " Ignoring." if _fill is False else ""
                        self._log_info(text1, _path, valid1, valid2)
                        if _fill is False:
                            _issue = "Item {} is not a valid item for the state configuration.".format(_path)
                            self._abitem.update_issues('config',
                                                       {item_state.property.path: {'issue': _issue,
                                                                                   'attribute': 'se_use'}})
                        elif _configvalue and _configvalue[i] not in cleaned_use_list:
                            cleaned_use_list.append(_configvalue[i])
                    if _returntype[i] in ['item', 'eval']:
                        _path = _configvalue[i]
                        self._log_info("se_use {} defined by item/eval. Even if current result is not valid, "
                                       "entry will be re-evaluated on next state evaluation.", _path)
                        if _path is not None and _path not in cleaned_use_list:
                            cleaned_use_list.append(_path)
                            self.__use_done.append(_path)
                    if _path is None:
                        pass
                    elif element == self.state_item:
                        self._log_info("Use element {} is same as current state - Ignoring.", _name)
                    elif _fill and element is not None and element not in self.__use_done:
                        self._log_develop("Adding element {} to state fill function.", _name)
                        if isinstance(_name, list):
                            self.__fill_list(element, recursion_depth + 1, _name)
                        else:
                            self.__use_done.append(element)
                            self.__fill(element, recursion_depth + 1, _name)
                self.__use.set(cleaned_use_list)

        # Get action sets and condition sets
        parent_item = item_state.return_parent()
        child_items = item_state.return_children()
        _conditioncount = 0
        _enter_actioncount = 0
        _enter_stay_actioncount = 0
        _leave_actioncount = 0
        _stay_actioncount = 0
        _actioncount = 0
        _unused_attributes = {}
        _used_attributes = {}
        # first check all conditions
        for child_item in child_items:
            child_name = StateEngineTools.get_last_part_of_item_id(child_item)
            try:
                if child_name == "enter" or child_name.startswith("enter_"):
                    _conditioncount += 1
                    _unused_attributes, _used_attributes = self.__conditions.update(child_name, child_item, parent_item)
                    self.__unused_attributes = copy(_unused_attributes)
                    self.__used_attributes = copy(_used_attributes)
                    for item in self.__unused_attributes.keys():
                        if 'issue' in self.__unused_attributes[item].keys():
                            if not self.__unused_attributes[item].get('issueorigin'):
                                self.__unused_attributes[item].update({'issueorigin': []})
                            entry = {'state': self.id, 'conditionset': child_name}
                            if entry not in self.__unused_attributes[item].get('issueorigin'):
                                self.__unused_attributes[item]['issueorigin'].append(entry)
                    self._abitem.update_attributes(self.__unused_attributes, self.__used_attributes)
            except ValueError as ex:
                raise ValueError("Condition {0} error: {1}".format(child_name, ex))

        if _conditioncount == 0:
            for attribute in parent_item.conf:
                func, name = StateEngineTools.partition_strip(attribute, "_")
                cond1 = name and name not in self.__used_attributes
                cond2 = func == "se_item" or func == "se_eval" or func == "se_status_eval" or func == "se_status"
                cond3 = name not in self.__unused_attributes.keys()

                if cond1 and cond2 and cond3:
                    self.__unused_attributes.update({name: {}})

        child_items = item_state.return_children()
        for child_item in child_items:
            child_name = StateEngineTools.get_last_part_of_item_id(child_item)
            try:
                if child_name == "on_enter":
                    _actioncount += 1
                    for attribute in child_item.conf:
                        _enter_actioncount += 1
                        _, _action_status = self.__actions_enter.update(attribute, child_item.conf[attribute])
                        if _action_status:
                            update_action_status(_action_status, 'enter')
                            self._abitem.update_action_status(self.__action_status)
                        update_unused(_used_attributes, 'action', child_name)
                elif child_name == "on_stay":
                    _actioncount += 1
                    for attribute in child_item.conf:
                        _stay_actioncount += 1
                        _, _action_status = self.__actions_stay.update(attribute, child_item.conf[attribute])
                        if _action_status:
                            update_action_status(_action_status, 'stay')
                            self._abitem.update_action_status(self.__action_status)
                        update_unused(_used_attributes, 'action', child_name)
                elif child_name == "on_enter_or_stay":
                    _actioncount += 1
                    for attribute in child_item.conf:
                        _enter_stay_actioncount += 1
                        _, _action_status = self.__actions_enter_or_stay.update(attribute, child_item.conf[attribute])
                        if _action_status:
                            update_action_status(_action_status, 'enter_or_stay')
                            self._abitem.update_action_status(self.__action_status)
                        update_unused(_used_attributes, 'action', child_name)
                elif child_name == "on_leave":
                    _actioncount += 1
                    for attribute in child_item.conf:
                        _leave_actioncount += 1
                        _, _action_status = self.__actions_leave.update(attribute, child_item.conf[attribute])
                        if _action_status:
                            update_action_status(_action_status, 'leave')
                            self._abitem.update_action_status(self.__action_status)
                        update_unused(_used_attributes, 'action', child_name)
            except ValueError as ex:
                raise ValueError("Condition {0} check for actions error: {1}".format(child_name, ex))
        self._abitem.update_attributes(self.__unused_attributes, self.__used_attributes)
        # Actions defined directly in the item go to "enter_or_stay"
        for attribute in item_state.conf:
            _result = self.__actions_enter_or_stay.update(attribute, item_state.conf[attribute])
            _enter_stay_actioncount += _result[0] if _result else 0
            _action_status = _result[1]
            if _action_status:
                update_action_status(_action_status, 'enter_or_stay')
                self._abitem.update_action_status(self.__action_status)

        _total_actioncount = _enter_actioncount + _stay_actioncount + _enter_stay_actioncount + _leave_actioncount

        self.update_name(item_state, recursion_depth)
        # Complete condition sets and actions at the end
        if recursion_depth == 0:
            self.__conditions.complete(item_state)
            _action_status = self.__actions_enter.complete(item_state, self.__conditions.evals_items)
            if _action_status:
                update_action_status(_action_status, 'enter')
                self._abitem.update_action_status(self.__action_status)
            _action_status = self.__actions_stay.complete(item_state, self.__conditions.evals_items)
            if _action_status:
                update_action_status(_action_status, 'stay')
                self._abitem.update_action_status(self.__action_status)
            _action_status = self.__actions_enter_or_stay.complete(item_state, self.__conditions.evals_items)
            if _action_status:
                update_action_status(_action_status, 'enter_or_stay')
                self._abitem.update_action_status(self.__action_status)
            _action_status = self.__actions_leave.complete(item_state, self.__conditions.evals_items)
            if _action_status:
                update_action_status(_action_status, 'leave')
                self._abitem.update_action_status(self.__action_status)
            self._abitem.update_action_status(self.__action_status)
            self._abitem.update_attributes(self.__unused_attributes, self.__used_attributes)
        _summary = "{} on_enter, {} on_stay , {} on_enter_or_stay, {} on_leave"
        if se_use is not None:
            self._log_debug("Added {} action(s) based on se_use {}. " + _summary, _total_actioncount, se_use,
                           _enter_actioncount, _stay_actioncount, _enter_stay_actioncount, _leave_actioncount)
            self._log_debug("Added {} condition set(s) based on se_use: {}", _conditioncount, se_use)
        else:
            self._log_debug("Added {} action(s) based on item configuration: " + _summary, _total_actioncount,
                           _enter_actioncount, _stay_actioncount, _enter_stay_actioncount, _leave_actioncount)
            self._log_debug("Added {} condition set(s) based on item configuration", _conditioncount)
