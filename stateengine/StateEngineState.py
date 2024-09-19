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
from copy import copy, deepcopy


# Class representing an object state, consisting of name, conditions to be met and configured actions for state
class SeState(StateEngineTools.SeItemChild):
    # Return id of state (= id of defining item)
    @property
    def id(self):
        return self.__id

    @property
    def path(self):
        return self.__id

    @property
    def use(self):
        return self.__use

    @property
    def state_item(self):
        return self.__item

    # Return name of state
    @property
    def name(self):
        return self.__name

    # Return leave actions
    @property
    def actions_leave(self):
        return self.__actions_leave

    @property
    def actions_enter(self):
        return self.__actions_enter

    @property
    def actions_enter_or_stay(self):
        return self.__actions_enter_or_stay

    @property
    def actions_stay(self):
        return self.__actions_stay

    @property
    def actions_pass(self):
        return self.__actions_pass

    # Return text of state
    @property
    def text(self):
        return self.__text.get(self.__name)

    # Return conditions
    @property
    def conditionsets(self):
        return self.__conditionsets

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
        self.__releasedby.set(value, "", True, False)

    @property
    def order(self):
        return self.__order.get()

    @order.setter
    def order(self, value):
        self.__order.set(value, "", True, False)

    @property
    def can_release(self):
        return self.__can_release.get()

    @can_release.setter
    def can_release(self, value):
        self.__can_release.set(value, "", True, False)

    @property
    def has_released(self):
        return self.__has_released.get()

    @has_released.setter
    def has_released(self, value):
        self.__has_released.set(value, "", True, False)

    @property
    def was_releasedby(self):
        return self.__was_releasedby.get()

    @was_releasedby.setter
    def was_releasedby(self, value):
        self.__was_releasedby.set(value, "", True, False)

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
        self.__is_copy_for.set(value, "", True, False)

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
        self.__action_status = {"enter": {}, "enter_or_stay": {}, "stay": {}, "pass": {}, "leave": {}}
        self.__use_done = []
        self.__use_list = []
        self.__use_ignore_list = []
        self.__conditionsets = StateEngineConditionSets.SeConditionSets(self._abitem)
        self.__actions_enter_or_stay = StateEngineActions.SeActions(self._abitem)
        self.__actions_enter = StateEngineActions.SeActions(self._abitem)
        self.__actions_stay = StateEngineActions.SeActions(self._abitem)
        self.__actions_leave = StateEngineActions.SeActions(self._abitem)
        self.__actions_pass = StateEngineActions.SeActions(self._abitem)
        self.__order = StateEngineValue.SeValue(self._abitem, "State Order", False, "num")
        self._log_increase_indent()
        try:
            self.__initialize_se_use(self, 0)
            self.__fill(self, 0, "reinit")
        finally:
            self._log_decrease_indent()

    def __repr__(self):
        return "SeState item: {}, id {}".format(self.__item, self.__id)

    # Check conditions if state can be entered
    # returns: True = At least one enter condition set is fulfilled, False = No enter condition set is fulfilled
    def can_enter(self):
        self._log_decrease_indent(10)
        self._log_info("Check if state '{0}' ('{1}') can be entered:", self.id, self.name)
        self._log_increase_indent()
        self.__is_copy_for.write_to_logger()
        self.__releasedby.write_to_logger()
        self.__can_release.write_to_logger()
        result, conditionset = self.__conditionsets.one_conditionset_matching(self)
        self._log_decrease_indent()
        if result:
            self._log_info("State {} can be entered based on conditionset {}", self.id, conditionset)
        else:
            self._log_info("State {} can not be entered", self.id)
        return result, conditionset

    # log state data
    def write_to_log(self):
        self._abitem.initstate = self
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
                                            'conditionsets': {},
                                            'actions_enter': {},
                                            'actions_enter_or_stay': {},
                                            'actions_stay': {},
                                            'actions_leave': {},
                                            'actions_pass': {},
                                            'leave': False, 'enter': False, 'stay': False,
                                            'is_copy_for': None, 'releasedby': None})
        self._log_decrease_indent()
        self._log_info("Finished Web Interface Update")

        if self.__conditionsets.count() > 0:
            self._log_info("Condition sets to enter state:")
            self._log_increase_indent()
            self.__conditionsets.write_to_logger()
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
            self._log_info("Actions to perform on leave (instant leave: {})", self._abitem.instant_leaveaction)
            self._log_increase_indent()
            self.__actions_leave.write_to_logger()
            self._log_decrease_indent()

        if self.__actions_pass.count() > 0:
            self._log_info("Actions to perform on pass / transit:")
            self._log_increase_indent()
            self.__actions_pass.write_to_logger()
            self._log_decrease_indent()

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
            _, _, _, _issue, _ = self.__order.set_from_attr(self.__item, "se_stateorder")
        elif value is not None:
            _, _, _issue, _ = self.__order.set(value, "", True, False)
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
        _key_pass = ['{}'.format(self.id), 'pass']
        self._abitem.update_webif(_key_leave, False)
        self._abitem.update_webif(_key_stay, False)
        self._abitem.update_webif(_key_enter, True)
        self._abitem.update_webif(_key_pass, False)
        self.__actions_enter.execute(False, allow_item_repeat, self, self.__actions_enter_or_stay)
        self._log_decrease_indent(50)

    # run actions when staying at the state
    # item_allow_repeat: Is repeating actions generally allowed for the item?
    def run_stay(self, allow_item_repeat: bool):
        self._log_increase_indent()
        _key_leave = ['{}'.format(self.id), 'leave']
        _key_stay = ['{}'.format(self.id), 'stay']
        _key_enter = ['{}'.format(self.id), 'enter']
        _key_pass = ['{}'.format(self.id), 'pass']
        self._abitem.update_webif(_key_leave, False)
        self._abitem.update_webif(_key_stay, True)
        self._abitem.update_webif(_key_enter, False)
        self._abitem.update_webif(_key_pass, False)
        self.__actions_stay.execute(True, allow_item_repeat, self, self.__actions_enter_or_stay)
        self._log_decrease_indent(50)

    # run actions when passing the state
    # item_allow_repeat: Is repeating actions generally allowed for the item?
    def run_pass(self, is_repeat: bool, allow_item_repeat: bool):
        self._log_info("Passing state {}, running pass actions.", self.id)
        self._log_increase_indent()
        _key_leave = ['{}'.format(self.id), 'leave']
        _key_stay = ['{}'.format(self.id), 'stay']
        _key_enter = ['{}'.format(self.id), 'enter']
        _key_pass = ['{}'.format(self.id), 'pass']
        self._abitem.update_webif(_key_leave, False)
        self._abitem.update_webif(_key_stay, False)
        self._abitem.update_webif(_key_enter, False)
        self._abitem.update_webif(_key_pass, True)
        self.__actions_pass.execute(is_repeat, allow_item_repeat, self)
        self._log_decrease_indent(50)

    # run actions when leaving the state
    # item_allow_repeat: Is repeating actions generally allowed for the item?
    def run_leave(self, allow_item_repeat: bool):
        self._log_increase_indent()
        for elem in self._abitem.webif_infos:
            _key_leave = ['{}'.format(elem), 'leave']
            self._abitem.update_webif(_key_leave, False)
        self.__actions_leave.execute(False, allow_item_repeat, self)
        self._log_decrease_indent(50)

    def refill(self):
        cond_refill = not self.__use.is_empty() and ("eval" in self.__use.get_type() or "item" in self.__use.get_type())
        if cond_refill:
            self._log_debug("State {}: se_use attribute including item or eval "
                            "- updating state conditions and actions", self.__name)
            self._log_increase_indent()
            self.__fill(self, 0, "reinit")
            self._log_decrease_indent()

    def update_releasedby_internal(self, states=None):
        if states == []:
            _returnvalue, _returntype, _issue, _ = self.__releasedby.set([None], "", True, False)
        elif states:
            self._log_develop("Setting releasedby to {}", states)
            _returnvalue, _returntype, _issue, _ = self.__releasedby.set(states, "", True, False)
            self._log_develop("returnvalue {}", _returnvalue)
        else:
            _returnvalue, _returntype, _, _issue, _ = self.__releasedby.set_from_attr(self.__item, "se_released_by")
        return _returnvalue, _returntype, _issue

    def update_can_release_internal(self, states):
        if states == []:
            _returnvalue, _returntype, _issue, _ = self.__can_release.set([None], "", True, False)
        elif states:
            _returnvalue, _returntype, _issue, _ = self.__can_release.set(states, "", True, False)
        else:
            _returnvalue, _returntype, _issue = [None], [None], None
        return _returnvalue, _returntype, _issue

    def update_name(self, item_state, recursion_depth=0):
        # if an item name is given, or if we do not have a name after returning from all recursions,
        # use item name as state name
        if "se_name" in item_state.conf:
            self.__text.set_from_attr(item_state, "se_name")
            self._log_develop("Updated name of state {} to {} based on se_name.", item_state, self.__name)
        elif str(item_state) != item_state.property.path or (self.__name == "" and recursion_depth == 0):
            _name = str(item_state).split('.')[-1]
            self.__text.set(_name)
            self._log_develop("Updated name of state {} to {} based on item name (recursion_depth = {}).",
                              item_state, self.__name, recursion_depth)
        elif self.__text.is_empty() and recursion_depth == 0:
            self.__text.set("value:" + self.__name)
            self._log_develop("Set name of state {} to {} as it was empty.", item_state, self.__name)
        self.__name = self.text
        return self.__name

    def __fill_list(self, item_states, recursion_depth, se_use=None, use=None):
        for i, element in enumerate(item_states):
            if element == self.state_item:
                self._log_info("Use element {} is same as current state - Ignoring.", element)
            elif element is not None and element not in self.__use_done:
                if isinstance(se_use, list):
                    se_use = se_use[i]
                try:
                    se_use = element.property.path
                except Exception:
                    se_use = element
                self.__use_done.append(element)
                self.__fill(element, recursion_depth, se_use, use)

    def __initialize_se_use(self, state, recursion_depth):
        # Import data from other item if attribute "use" is found
        if isinstance(state, SeState):
            item_state = state.state_item
            state_type = "state"
        elif isinstance(state, Item):
            item_state = state
            state_type = "item"
        elif isinstance(state, list):
            for item in state:
                item_state = item
                self.__initialize_se_use(item_state, recursion_depth + 1)
        else:
            item_state = state
            state_type = "struct"
        if recursion_depth > 5:
            self._log_error("{0}/{1}: too many levels of 'use'", self.id, item_state)
            return
        if "se_use" in item_state.conf:
            _returnvalue, _returntype, _, _issue, _origvalue = self.__use.set_from_attr(
                item_state, "se_use", None, True, None,
                self.__use_list + self.__use_ignore_list)
            _configvalue = copy(_returnvalue)
            _configvalue = [_configvalue] if not isinstance(_configvalue, list) else _configvalue
            _configorigvalue = copy(_origvalue)
            _configorigvalue = [_configorigvalue] if not isinstance(_configorigvalue, list) else _configorigvalue
            self._abitem.update_issues('config', {state.id: {'issue': _issue, 'attribute': 'se_use'}})
            _use = self.__use.get()
            if self.__use.is_empty() or _use is None:
                _issue = "se_use {} is set up in a wrong way".format(_use)
                self._abitem.update_issues('config', {state.id: {'issue': _issue, 'attribute': 'se_use', 'origin': state_type}})
                self._log_warning("{} - ignoring.", _issue)
            else:
                _use = [_use] if not isinstance(_use, list) else _use
                _returntype = [_returntype] if not isinstance(_returntype, list) else _returntype
                cleaned_use_list = []
                for i, element in enumerate(_use):
                    try:
                        _name = element.id
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
                            self.__use_ignore_list.append(_path)
                        elif _configvalue and _configvalue[i] not in cleaned_use_list:
                            cleaned_use_list.append(_configvalue[i])
                    elif isinstance(element, self.__itemClass):
                        _path = element.property.path
                        if element.return_parent() == Items.get_instance():
                            valid1 = " most likely NOT"
                            valid3 = ""
                            valid2 = ", because it has no parent item!"
                        else:
                            valid2 = ""
                            valid1 = " NOT" if _fill is False else " most likely"
                            valid3 = " Ignoring." if _fill is False else ""
                        text1 = "Reading Item {0}. It is{1} a valid item for the state configuration{2}.{3}"
                        self._log_info(text1, _path, valid1, valid2, valid3)
                        if _fill is False:
                            _issue = "Item {} is not a valid item for the state configuration.".format(_path)
                            self._abitem.update_issues('config',
                                                       {state.id: {'issue': _issue, 'attribute': 'se_use', 'origin': state_type}})
                            self.__use_ignore_list.append(_path)
                        elif _configorigvalue and _configorigvalue[i] not in cleaned_use_list:
                            cleaned_use_list.append(_configorigvalue[i])
                    if _returntype[i] == 'value':
                        _issues = self.__use.get_issues()
                        for item in _issues.get('cast_item'):
                            if (_configorigvalue[i] is not None and isinstance(_configorigvalue[i], str) and
                                    (StateEngineTools.partition_strip(_configorigvalue[i], ":")[1] in item or
                                     _configorigvalue[i] in item)):
                                _issue_list = [item for key, value in _issues.items() if value for item in value]
                                self._log_warning("se_use {} points to invalid item. Ignoring.", _configorigvalue[i])
                                self._abitem.update_issues('config', {state.id: {'issue': _issue_list,
                                                                                 'attribute': 'se_use', 'origin': state_type}})
                                self.__use_ignore_list.append(_configorigvalue[i])
                                _path = None
                    elif _returntype[i] in ['item', 'eval']:
                        _path = _configvalue[i]
                        _issues = self.__use.get_issues()
                        for list_key in ['cast_item', 'eval', 'item']:
                            if list_key in _issues:
                                for item in _issues[list_key]:
                                    if (_path is not None and isinstance(_path, str) and
                                            StateEngineTools.partition_strip(_path, ":")[1] in item):

                                        _issue_list = [item for key, value in _issues.items() if value for item in value]
                                        self._log_warning("se_use {} defined by invalid item/eval. Ignoring.", _path)
                                        self._abitem.update_issues('config', {state.id: {'issue': _issue_list,
                                                                                         'attribute': 'se_use', 'origin': state_type}})
                                        self.__use_ignore_list.append(_path)
                                        _path = None
                        if _path is None:
                            pass

                        elif _path is not None and _configorigvalue[i] not in cleaned_use_list:
                            self._log_info("se_use {} defined by item/eval {}. Even if current result is not valid, "
                                           "entry will be re-evaluated on next state evaluation. element: {}", _path, _configorigvalue[i], element)
                            cleaned_use_list.append(_configorigvalue[i])
                            #self.__use_done.append(_path)
                    if _path is None:
                        pass
                    elif element == self.state_item:
                        self._log_info("Use element {} is same as current state - Ignoring.", _name)
                        self.__use_ignore_list.append(element)
                    elif _fill and element is not None and _configorigvalue[i] not in self.__use_list:

                        if isinstance(_name, list):
                            self._log_develop(
                                "Adding list element {} to state fill function. path is {}, name is {}. configvalue {}",
                                element, _path, _name, _configorigvalue[i])
                            self.__use_list.append(_configorigvalue[i])
                            for item in _name:
                                self.__initialize_se_use(item, recursion_depth + 1)
                        else:
                            self._log_develop(
                                "Adding element {} to state fill function. path is {}, name is {}.",
                                _configorigvalue[i], _path, _name)
                            self.__use_list.append(_configorigvalue[i])
                            self.__initialize_se_use(element, recursion_depth + 1)
                    elif _fill and element is not None and _configorigvalue[i] in self.__use_list:
                        self._log_debug("Ignoring element {} as it is already added. cleaned use {}", element, cleaned_use_list)
                self.__use_list.extend(cleaned_use_list)
                seen = set()
                self.__use_list = [x for x in self.__use_list if not (x in seen or seen.add(x))]
        self.__use.set(self.__use_list)

    # Read configuration from item and populate data in class
    # item_state: item to read from
    # recursion_depth: current recursion_depth (recursion is canceled after five levels)
    # se_use: If se_use Attribute is used or not
    def __fill(self, state, recursion_depth, se_use=None, use=None):

        def update_unused(used_attributes, attrib_type, attrib_name):
            #filtered_dict = {key: value for key, value in self.__unused_attributes.items() if key not in used_attributes}
            #self.__unused_attributes = copy(filtered_dict)

            for nested_entry, nested_dict in self.__unused_attributes.items():
                if nested_entry in used_attributes.keys():
                    used_attributes[nested_entry].update({attrib_type: attrib_name})
                    used_attributes[nested_entry].update(nested_dict)
                    self.__used_attributes.update(used_attributes)

        def update_action_status(actn_type, action_status):
            def filter_issues(input_dict):
                return {
                    key: {sub_key: sub_value for sub_key, sub_value in value.items() if
                          sub_value.get('issue') not in (None, [], [None])}
                    for key, value in input_dict.items()
                }

            if action_status is None:
                return
            action_status = StateEngineTools.flatten_list(action_status)
            if isinstance(action_status, list):
                for e in action_status:
                    update_action_status(actn_type, e)
                return
            for itm, dct in action_status.items():
                if itm not in self.__action_status[actn_type]:
                    self.__action_status[actn_type].update({itm: dct})

            for (itm, dct) in action_status.items():
                issues = dct.get('issue')
                attributes = dct.get('attribute')
                if issues:
                    if isinstance(issues, list):
                        for i, issue in enumerate(issues):
                            if issue not in self.__action_status[actn_type][itm]['issue']:
                                self.__action_status[actn_type][itm]['issue'].append(issue)
                                self.__action_status[actn_type][itm]['attribute'].append(attributes[i])

            flattened_dict = {}
            for key, action_type_dict in self.__action_status.items():
                # Iterate through the inner dictionaries
                for inner_key, nested_dict in action_type_dict.items():
                    # Initialize the entry in the flattened dictionary
                    if inner_key not in flattened_dict:
                        flattened_dict[inner_key] = {}
                    # Add 'used in' and update with existing data
                    flattened_dict[inner_key]['used in'] = key
                    flattened_dict[inner_key].update(nested_dict)
            self.__used_attributes = deepcopy(flattened_dict)
            self.__action_status = filter_issues(self.__action_status)

        if isinstance(state, SeState):
            item_state = state.state_item
        else:
            item_state = state
        self._log_develop("Fill state {} type {}, called by {}, recursion {}", item_state, type(item_state), se_use, recursion_depth)
        if se_use == "reinit":
            self._log_develop("Resetting conditions and actions at re-init use is {}", use)
            self.__conditionsets.reset()
            self.__actions_enter_or_stay.reset()
            self.__actions_enter.reset()
            self.__actions_stay.reset()
            self.__actions_leave.reset()
            self.__actions_pass.reset()
            self.__use_done = []

            use = self.__use.get()

            if use is not None:
                use = use if isinstance(use, list) else [use]
                use = [u for u in use if u is not None]
                use = StateEngineTools.flatten_list(use)
                self.__fill_list(use, recursion_depth, se_use, use)
        # Get action sets and condition sets
        parent_item = item_state.return_parent()
        if parent_item == Items.get_instance():
            parent_item = None
        child_items = item_state.return_children()
        _conditioncount = 0
        _action_counts = {"enter": 0, "stay": 0, "enter_or_stay": 0, "leave": 0, "pass": 0}
        _unused_attributes = {}
        _used_attributes = {}
        _action_status = {}
        # first check all conditions
        for child_item in child_items:
            child_name = StateEngineTools.get_last_part_of_item_id(child_item)
            try:
                if child_name == "enter" or child_name.startswith("enter_"):
                    _conditioncount += 1
                    _unused_attributes, _used_attributes = self.__conditionsets.update(child_name, child_item, parent_item)
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

        if _conditioncount == 0 and parent_item:
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
                action_mapping = {
                    "on_enter": ("enter", "actions_enter", self.__actions_enter),
                    "on_stay": ("stay", "actions_stay", self.__actions_stay),
                    "on_enter_or_stay": ("enter_or_stay", "actions_enter_or_stay", self.__actions_enter_or_stay),
                    "on_leave": ("leave", "actions_leave", self.__actions_leave),
                    "on_pass": ("pass", "actions_pass", self.__actions_pass)
                }

                if child_name in action_mapping:
                    action_name, action_type, action_method = action_mapping[child_name]
                    for attribute in child_item.conf:
                        self._log_develop("Filling state with {} action named {} for state {} with config {}", child_name, attribute, state.id, child_item.conf)
                        action_method.update_action_details(self, action_type)
                        _action_counts[action_name] += 1
                        _, _action_status = action_method.update(attribute, child_item.conf.get(attribute))
                        if _action_status:
                            update_action_status(action_name, _action_status)
                            self._abitem.update_action_status(self.__action_status)
                        update_unused(_used_attributes, 'action', child_name)

            except ValueError as ex:
                raise ValueError("Condition {0} check for actions error: {1}".format(child_name, ex))

        self._abitem.update_attributes(self.__unused_attributes, self.__used_attributes)
        # Actions defined directly in the item go to "enter_or_stay"
        for attribute in item_state.conf:
            self.__actions_enter_or_stay.update_action_details(self, "actions_enter_or_stay")
            _result = self.__actions_enter_or_stay.update(attribute, item_state.conf.get(attribute))
            _action_counts["enter_or_stay"] += _result[0] if _result else 0
            _action_status = _result[1]
            if _action_status:
                update_action_status("enter_or_stay", _action_status)
                self._abitem.update_action_status(self.__action_status)

        _total_actioncount = _action_counts["enter"] + _action_counts["stay"] + _action_counts["enter_or_stay"] + _action_counts["leave"]

        self.update_name(item_state, recursion_depth)
        # Complete condition sets and actions at the end

        if recursion_depth == 0:
            self.__conditionsets.complete(self, use)
            _action_status = self.__actions_enter.complete(self.__conditionsets.evals_items, use)
            if _action_status:
                update_action_status("enter", _action_status)
                self._abitem.update_action_status(self.__action_status)
            _action_status = self.__actions_stay.complete(self.__conditionsets.evals_items, use)
            if _action_status:
                update_action_status("stay", _action_status)
                self._abitem.update_action_status(self.__action_status)
            _action_status = self.__actions_enter_or_stay.complete(self.__conditionsets.evals_items, use)
            if _action_status:
                update_action_status("enter_or_stay", _action_status)
                self._abitem.update_action_status(self.__action_status)
            _action_status = self.__actions_pass.complete(self.__conditionsets.evals_items, use)
            if _action_status:
                update_action_status("pass", _action_status)
                self._abitem.update_action_status(self.__action_status)
            _action_status = self.__actions_leave.complete(self.__conditionsets.evals_items, use)
            if _action_status:
                update_action_status("leave", _action_status)
                self._abitem.update_action_status(self.__action_status)
            self._abitem.update_action_status(self.__action_status)
            self._abitem.update_attributes(self.__unused_attributes, self.__used_attributes)
        _summary = "{} on_enter, {} on_stay , {} on_enter_or_stay, {} on_leave, {} on_pass"
        if self.__action_status:
            _ignore_list = [entry for entry in self.__action_status if self.__action_status[entry].get('ignore') is True]
            if _ignore_list:
                self._log_info("Ignored {} action(s) due to errors: {}", len(_ignore_list), _ignore_list)
        if se_use is not None:
            self._log_debug("Added {} action(s) based on se_use {}. " + _summary, _total_actioncount, se_use,
                            _action_counts["enter"], _action_counts["stay"], _action_counts["enter_or_stay"], _action_counts["leave"], _action_counts["pass"])
            self._log_debug("Added {} condition set(s) based on se_use: {}", _conditioncount, se_use)
        else:
            self._log_debug("Added {} action(s) based on item configuration: " + _summary, _total_actioncount,
                            _action_counts["enter"], _action_counts["stay"], _action_counts["enter_or_stay"], _action_counts["leave"], _action_counts["pass"])
            self._log_debug("Added {} condition set(s) based on item configuration", _conditioncount)
