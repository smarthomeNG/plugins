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
import datetime
from collections import OrderedDict
from . import StateEngineTools
from .StateEngineLogger import SeLogger
from . import StateEngineState
from . import StateEngineDefaults
from . import StateEngineCurrent
from . import StateEngineValue
from . import StateEngineStruct
from . import StateEngineStructs
from lib.item import Items
from lib.shtime import Shtime
from lib.item.item import Item
import threading
import queue


# Class representing a blind item
# noinspection PyCallingNonCallable
class SeItem:
    # return item id
    @property
    def id(self):
        return self.__id

    @property
    def variables(self):
        return self.__variables

    @property
    def templates(self):
        return self.__templates

    @property
    def webif_infos(self):
        return self.__webif_infos

    # return instance of shtime class
    @property
    def shtime(self):
        return self.__shtime

    # return instance of smarthome.py class
    @property
    def sh(self):
        return self.__sh

    # return instance of smartplugin class
    @property
    def se_plugin(self):
        return self.__se_plugin

    # return instance of queue
    @property
    def queue(self):
        return self.__queue

    # return all schedulers for item
    @property
    def schedulers(self):
        return self.__active_schedulers

    # return instance of logger class
    @property
    def logger(self):
        return self.__logger

    @property
    def instant_leaveaction(self):
        return self.__instant_leaveaction

    @property
    def laststate(self):
        return self.__laststate_item_id.property.value

    @property
    def previousstate(self):
        return self.__previousstate_item_id.property.value

    @property
    def lastconditionset(self):
        return None if self.__lastconditionset_item_id is None else self.__lastconditionset_item_id.property.value

    @property
    def previousconditionset(self):
        return self.__previousconditionset_item_id.property.value

    @property
    def previousstate_conditionset(self):
        return self.__previousstate_conditionset_item_id.property.value

    @property
    def laststate_name(self):
        return self.__laststate_item_name.property.value

    @property
    def previousstate_name(self):
        return self.__previousstate_item_name.property.value

    @property
    def lastconditionset_name(self):
        return None if self.__lastconditionset_item_name is None else self.__lastconditionset_item_name.property.value

    @property
    def previousconditionset_name(self):
        return self.__previousconditionset_item_name.property.value

    @property
    def previousstate_conditionset_name(self):
        return self.__previousstate_conditionset_item_name.property.value

    @property
    def ab_alive(self):
        return self.__ab_alive

    @ab_alive.setter
    def ab_alive(self, value):
        self.__ab_alive = value

    # Constructor
    # smarthome: instance of smarthome.py
    # item: item to use
    # se_plugin: smartplugin instance
    def __init__(self, smarthome, item, se_plugin):
        self.__item = item
        self.__logger = SeLogger.create(self.__item)
        self.itemsApi = Items.get_instance()
        self.update_lock = threading.Lock()
        self.__ab_alive = False
        self.__queue = queue.Queue()
        self.__sh = smarthome
        self.__shtime = Shtime.get_instance()
        self.__se_plugin = se_plugin
        self.__active_schedulers = []
        self.__all_releasedby = {}
        #self.__all_torelease = {}
        try:
            self.__id = self.__item.property.path
        except Exception:
            self.__id = item
        self.__name = str(self.__item)
        self.__itemClass = Item
        # initialize logging

        self.__log_level = StateEngineValue.SeValue(self, "Log Level", False, "num")
        self.__log_level.set_from_attr(self.__item, "se_log_level", StateEngineDefaults.log_level)
        self.__logger.header("")
        self.__logger.header("Initialize Item {0} (Log Level set"
                             " to {1})".format(self.id, self.__log_level))
        self.__logger.override_loglevel(self.__log_level, self.__item)
        # get startup delay
        self.__startup_delay = StateEngineValue.SeValue(self, "Startup Delay", False, "num")
        self.__startup_delay.set_from_attr(self.__item, "se_startup_delay", StateEngineDefaults.startup_delay)
        self.__startup_delay_over = False

        # Init suspend settings
        self.__suspend_time = StateEngineValue.SeValue(self, "Suspension time on manual changes", False, "num")
        self.__suspend_time.set_from_attr(self.__item, "se_suspend_time", StateEngineDefaults.suspend_time)

        # Init laststate and previousstate items/values
        self.__laststate_item_id = self.return_item_by_attribute("se_laststate_item_id")
        self.__laststate_internal_id = "" if self.__laststate_item_id is None else self.__laststate_item_id.property.value
        self.__laststate_item_name = self.return_item_by_attribute("se_laststate_item_name")
        self.__laststate_internal_name = "" if self.__laststate_item_name is None else self.__laststate_item_name.property.value
        self.__previousstate_item_id = self.return_item_by_attribute("se_previousstate_item_id")
        self.__previousstate_internal_id = "" if self.__previousstate_item_id is None else self.__previousstate_item_id.property.value
        self.__previousstate_item_name = self.return_item_by_attribute("se_previousstate_item_name")
        self.__previousstate_internal_name = "" if self.__previousstate_item_name is None else self.__previousstate_item_name.property.value

        # Init releasedby items/values
        self.___shouldnotrelease_item = self.return_item_by_attribute("se_shouldnotrelease_item")
        self.__hasreleased_item = self.return_item_by_attribute("se_hasreleased_item")
        self.__has_released = {} if self.__hasreleased_item is None else self.__hasreleased_item.property.value
        self.__logger.develop("has released = {}", self.__has_released)
        self.__should_not_release = {} if self.___shouldnotrelease_item is None else self.___shouldnotrelease_item.property.value

        # Init lastconditionset items/values
        self.__lastconditionset_item_id = self.return_item_by_attribute("se_lastconditionset_item_id")
        self.__lastconditionset_internal_id = "" if self.__lastconditionset_item_id is None else \
            self.__lastconditionset_item_id.property.value
        self.__lastconditionset_item_name = self.return_item_by_attribute("se_lastconditionset_item_name")
        self.__lastconditionset_internal_name = "" if self.__lastconditionset_item_name is None else \
            self.__lastconditionset_item_name.property.value

        # Init previousconditionset items/values
        self.__previousconditionset_item_id = self.return_item_by_attribute("se_previousconditionset_item_id")
        self.__previousconditionset_internal_id = "" if self.__previousconditionset_item_id is None else \
            self.__previousconditionset_item_id.property.value
        self.__previousconditionset_item_name = self.return_item_by_attribute("se_previousconditionset_item_name")
        self.__previousconditionset_internal_name = "" if self.__previousconditionset_item_name is None else \
            self.__previousconditionset_item_name.property.value

        self.__previousstate_conditionset_item_id = self.return_item_by_attribute("se_previousstate_conditionset_item_id")
        self.__previousstate_conditionset_internal_id = "" if self.__previousstate_conditionset_item_id is None else \
            self.__previousstate_conditionset_item_id.property.value
        self.__previousstate_conditionset_item_name = self.return_item_by_attribute("se_previousstate_conditionset_item_name")
        self.__previousstate_conditionset_internal_name = "" if self.__previousstate_conditionset_item_name is None else \
            self.__previousstate_conditionset_item_name.property.value

        self.__states = []
        self.__state_ids = {}
        self.__conditionsets = {}
        self.__templates = {}
        self.__webif_infos = OrderedDict()
        self.__instant_leaveaction = StateEngineValue.SeValue(self, "Instant Leave Action", False, "bool")
        self.__instant_leaveaction.set_from_attr(self.__item, "se_instant_leaveaction", StateEngineDefaults.instant_leaveaction)
        self.__repeat_actions = StateEngineValue.SeValue(self, "Repeat actions if state is not changed", False, "bool")
        self.__repeat_actions.set_from_attr(self.__item, "se_repeat_actions", True)

        self._initstate = None
        self._initactionname = None
        self.__update_trigger_item = None
        self.__update_trigger_caller = None
        self.__update_trigger_source = None
        self.__update_trigger_dest = None
        self.__update_original_item = None
        self.__update_original_caller = None
        self.__update_original_source = None

        # Check item configuration
        self.__check_item_config()

        # Init variables
        self.__variables = {
            "item.suspend_time": self.__suspend_time.get(),
            "item.suspend_remaining": 0,
            "item.instant_leaveaction": self.__instant_leaveaction.get(),
            "current.state_id": "",
            "current.state_name": "",
            "current.conditionset_id": "",
            "current.conditionset_name": "",
            "current.action_name": "",
            "previous.state_id": "",
            "previous.state_name": "",
            "previous.conditionset_id": "",
            "previous.conditionset_name": "",
            "previous.state_conditionset_id": "",
            "previous.state_conditionset_name": ""
        }

        # initialize states
        for item_state in self.__item.return_children():
            try:
                _state = StateEngineState.SeState(self, item_state)
                self.__states.append(_state)
                self.__state_ids.update({item_state.property.path: _state})
            except ValueError as ex:
                self.__logger.error("Ignoring state {0} because:  {1}".format(item_state.property.path, ex))

        if len(self.__states) == 0:
            raise ValueError("{0}: No states defined!".format(self.id))

        # Write settings to log
        self.__write_to_log()
        try:
            self.__has_released.pop('initial')
        except Exception:
            pass
        self.__logger.develop("ALL RELEASEDBY: {}", self.__all_releasedby)
        self.__logger.develop("HAS RELEASED: {}", self.__has_released)

        # start timer with startup-delay
        _startup_delay_param = self.__startup_delay.get()
        startup_delay = 1 if self.__startup_delay.is_empty() or _startup_delay_param == 0 else _startup_delay_param
        if startup_delay > 0:
            first_run = self.__shtime.now() + datetime.timedelta(seconds=startup_delay)
            scheduler_name = self.__id + "-Startup Delay"
            value = {"item": self.__item, "caller": "Init"}
            self.__se_plugin.scheduler_add(scheduler_name, self.__startup_delay_callback, value=value, next=first_run)
        elif startup_delay == -1:
            self.__startup_delay_over = True
            self.__add_triggers()
        else:
            self.__startup_delay_callback(self.__item, "Init", None, None)

    def __repr__(self):
        return self.__id

    def updatetemplates(self, template, value):
        if value is None:
            self.__templates.pop(template)
        else:
            self.__templates[template] = value

    def add_scheduler_entry(self, name):
        if name not in self.__active_schedulers:
            self.__active_schedulers.append(name)

    def remove_scheduler_entry(self, name):
        self.__active_schedulers.remove(name)

    def remove_all_schedulers(self):
        for entry in self.__active_schedulers:
            self.__se_plugin.scheduler_remove('{}'.format(entry))

    # region Updatestate ***********************************************************************************************
    # run queue
    def run_queue(self):
        if not self.__ab_alive:
            self.__logger.debug("{} not running (anymore). Queue not activated.", StateEngineDefaults.plugin_identification)
            return
        self.update_lock.acquire(True, 10)
        while not self.__queue.empty() and self.__ab_alive:
            job = self.__queue.get()
            if job is None or self.__ab_alive is False:
                self.__logger.debug("No jobs in queue left or plugin not active anymore")
                break
            elif job[0] == "delayedaction":
                self.__logger.debug("Job {}", job)
                (_, action, actionname, namevar, repeat_text, value, current_condition, previous_condition, previousstate_condition) = job
                self.__logger.info("Running delayed action: {0} based on current condition {1} or previous condition {2}",
                                   actionname, current_condition, previous_condition)
                action.real_execute(actionname, namevar, repeat_text, value, False, current_condition)
            else:
                (_, item, caller, source, dest) = job
                item_id = item.property.path if item is not None else "(no item)"
                self.__logger.update_logfile()
                self.__logger.header("Update state of item {0}".format(self.__name))
                if caller:
                    self.__logger.debug("Update triggered by {0} (item={1} source={2} dest={3})", caller, item_id, source, dest)

                # Find out what initially caused the update to trigger if the caller is "Eval"
                orig_caller, orig_source, orig_item = StateEngineTools.get_original_caller(self.__logger, caller, source, item)
                if orig_caller != caller:
                    text = "{0} initially triggered by {1} (item={2} source={3} value={4})."
                    self.__logger.debug(text, caller, orig_caller, orig_item.property.path,
                                        orig_source, orig_item.property.value)
                cond1 = orig_caller == StateEngineDefaults.plugin_identification
                cond2 = caller == StateEngineDefaults.plugin_identification
                cond1_2 = orig_source == item_id
                cond2_2 = source == item_id
                if (cond1 and cond1_2) or (cond2 and cond2_2):
                    self.__logger.debug("Ignoring changes from {0}", StateEngineDefaults.plugin_identification)
                    continue

                self.__update_trigger_item = item.property.path
                self.__update_trigger_caller = caller
                self.__update_trigger_source = source
                self.__update_trigger_dest = dest
                self.__update_original_item = orig_item.property.path
                self.__update_original_caller = orig_caller
                self.__update_original_source = orig_source

                # Update current values
                StateEngineCurrent.update()
                self.__variables["item.suspend_time"] = self.__suspend_time.get()
                self.__variables["item.suspend_remaining"] = -1
                self.__variables["item.instant_leaveaction"] = self.__instant_leaveaction.get()

                # get last state
                last_state = self.__laststate_get()
                if last_state is not None:
                    self.__logger.info("Last state: {0} ('{1}')", last_state.id, last_state.name)

                _last_conditionset_id = self.__lastconditionset_internal_id #self.__lastconditionset_get_id()
                _last_conditionset_name = self.__lastconditionset_internal_name # self.__lastconditionset_get_name()
                if _last_conditionset_id not in ['', None]:
                    self.__logger.info("Last Conditionset: {0} ('{1}')", _last_conditionset_id, _last_conditionset_name)
                else:
                    self.__logger.info("Last Conditionset is empty")
                _original_conditionset_id = _last_conditionset_id
                _original_conditionset_name = _last_conditionset_name
                if self.__previousconditionset_internal_id not in ['', None]:
                    self.__logger.info("Previous Conditionset: {0} ('{1}')", self.__previousconditionset_internal_id, self.__previousconditionset_internal_name)
                else:
                    self.__logger.info("Previous Conditionset is empty")
                _previous_conditionset_id = _last_conditionset_id
                _previous_conditionset_name = _last_conditionset_name
                # get previous state
                if self.__previousstate_internal_id not in ['', None]:
                    self.__logger.info("Previous state: {0} ('{1}')", self.__previousstate_internal_id, self.__previousstate_internal_name)

                if self.__previousstate_conditionset_internal_id not in ['', None]:
                    self.__logger.info("Previous state's Conditionset: {0} ('{1}')", self.__previousstate_conditionset_internal_id, self.__previousstate_conditionset_internal_name)
                else:
                    self.__logger.info("Previous state's Conditionset is empty")

                # find new state
                new_state = None
                _leaveactions_run = False

                # for releasedby functionality
                _releasedby_active = True if self.__all_releasedby else False
                if _releasedby_active:
                    _wouldenter = None
                    _wouldnotenter = []
                    _flagged = []
                    _checked_states = []
                    _possible_states = []

                _releasedby = []
                for state in self.__states:
                    if not self.__ab_alive:
                        self.__logger.debug("StateEngine Plugin not running (anymore). Stop state evaluation.")
                        return
                    state.update_name(state.state_item)
                    _key_name = ['{}'.format(state.id), 'name']
                    self.update_webif(_key_name, state.name)

                    if _releasedby_active:
                        _checked_states.append(state)
                        if _wouldenter and not _releasedby:
                            new_state = self.__state_ids[_wouldenter]
                            _last_conditionset_id = self.__conditionsets[_wouldenter][0]
                            _last_conditionset_name = self.__conditionsets[_wouldenter][1]
                            if new_state.conditions.count() == 0:
                                self.lastconditionset_set('', '')
                                _last_conditionset_id = ''
                                _last_conditionset_name = ''
                            else:
                                self.lastconditionset_set(_last_conditionset_id, _last_conditionset_name)
                            self.__logger.debug("No release states True - Going back to {}. Condition set: {} ('{}')", new_state, _last_conditionset_id, _last_conditionset_name)
                            break
                    result = self.__update_check_can_enter(state)
                    _previousstate_conditionset_id = _last_conditionset_id
                    _previousstate_conditionset_name = _last_conditionset_name
                    _last_conditionset_id = self.__lastconditionset_internal_id
                    _last_conditionset_name = self.__lastconditionset_internal_name
                    if state is not None and result is True:
                        self.__conditionsets.update({state.state_item.property.path: [_last_conditionset_id, _last_conditionset_name]})
                    if _releasedby_active:
                        _todo, _releasedby, _wouldenter, _wouldnotenter, new_state, _possible_state, _flagged = self.__check_releasedby(
                            state, _checked_states, _releasedby, _wouldenter, _wouldnotenter, _flagged, last_state, _possible_states, result)
                        if self.__hasreleased_item is not None:
                            self.__hasreleased_item(self.__has_released, StateEngineDefaults.plugin_identification, "StateEvaluation")

                        if self.___shouldnotrelease_item is not None:
                            self.___shouldnotrelease_item(self.__should_not_release, StateEngineDefaults.plugin_identification,
                                                          "StateEvaluation")
                        if _possible_state:
                            _possible_states.append(_possible_state)
                            self.__logger.info("Possible states: {}", _possible_states)
                        if _todo == 'continue':
                            continue
                        if _todo == 'break':
                            break

                    if not _releasedby:
                        # New state is different from last state
                        if result is False and last_state == state and self.__instant_leaveaction.get() is True:
                            self.__logger.info("Leaving {0} ('{1}'). Running actions immediately.", last_state.id, last_state.name)
                            last_state.run_leave(self.__repeat_actions.get())
                            _leaveactions_run = True
                        if result is True:
                            new_state = state
                            break

                # no new state -> stay
                if new_state is None:
                    if last_state is None:
                        self.__logger.info("No matching state found, no previous state available. Doing nothing.")
                    else:
                        _last_conditionset_id = self.__conditionsets[_wouldenter][0]
                        _last_conditionset_name = self.__conditionsets[_wouldenter][1]
                        if last_state.conditions.count() == 0:
                            self.lastconditionset_set('', '')
                            _last_conditionset_id = ''
                            _last_conditionset_name = ''
                        else:
                            self.lastconditionset_set(_last_conditionset_id, _last_conditionset_name)
                        if _last_conditionset_id in ['', None]:
                            text = "No matching state found, staying at {0} ('{1}')"
                            self.__logger.info(text, last_state.id, last_state.name)
                        else:
                            text = "No matching state found, staying at {0} ('{1}') based on conditionset {2} ('{3}')"
                            self.__logger.info(text, last_state.id, last_state.name, _last_conditionset_id, _last_conditionset_name)
                        last_state.run_stay(self.__repeat_actions.get())
                    if self.update_lock.locked():
                        self.update_lock.release()
                    self.__logger.debug("State evaluation finished")
                    self.__logger.info("State evaluation queue empty.")
                    return

                _last_conditionset_id = self.__lastconditionset_internal_id
                _last_conditionset_name = self.__lastconditionset_internal_name

                if new_state.conditions.count() == 0:
                    self.lastconditionset_set('', '')
                    _last_conditionset_id = ''
                    _last_conditionset_name = ''
                self.previousconditionset_set(_previous_conditionset_id, _previous_conditionset_name)
                #endblock
                # get data for new state
                if last_state is not None and new_state.id == last_state.id:
                    if _last_conditionset_id in ['', None]:
                        self.__logger.info("Staying at {0} ('{1}')", new_state.id, new_state.name)
                    else:
                        self.__logger.info("Staying at {0} ('{1}') based on conditionset {2} ('{3}')",
                                           new_state.id, new_state.name, _last_conditionset_id, _last_conditionset_name)

                    new_state.run_stay(self.__repeat_actions.get())
                    if self.__laststate_internal_name != new_state.name:
                        self.__laststate_set(new_state)
                        self.__previousstate_set(last_state)

                else:
                    if last_state is not None and _leaveactions_run is True:
                        self.__logger.info("Left {0} ('{1}')", last_state.id, last_state.name)
                        if last_state.leaveactions.count() > 0:
                            self.__logger.info("Maybe some actions were performed directly after leave - see log above.")
                    elif last_state is not None:
                        self.lastconditionset_set(_original_conditionset_id, _original_conditionset_name)
                        self.__logger.info("Leaving {0} ('{1}'). Condition set was: {2}.",
                                           last_state.id, last_state.name, _original_conditionset_id)
                        last_state.run_leave(self.__repeat_actions.get())
                        _leaveactions_run = True
                    if new_state.conditions.count() == 0:
                        self.lastconditionset_set('', '')
                        _last_conditionset_id = ''
                        _last_conditionset_name = ''
                    else:
                        self.lastconditionset_set(_last_conditionset_id, _last_conditionset_name)
                    self.previousstate_conditionset_set(_previousstate_conditionset_id, _previousstate_conditionset_name)
                    if _last_conditionset_id in ['', None]:
                        self.__logger.info("Entering {0} ('{1}')", new_state.id, new_state.name)
                    else:
                        self.__logger.info("Entering {0} ('{1}') based on conditionset {2} ('{3}')",
                                           new_state.id, new_state.name, _last_conditionset_id, _last_conditionset_name)

                    new_state.run_enter(self.__repeat_actions.get())
                    self.__laststate_set(new_state)
                    self.__previousstate_set(last_state)
                if _leaveactions_run is True and self.__ab_alive:
                    _key_leave = ['{}'.format(last_state.id), 'leave']
                    _key_stay = ['{}'.format(last_state.id), 'stay']
                    _key_enter = ['{}'.format(last_state.id), 'enter']

                    self.update_webif(_key_leave, True)
                    self.update_webif(_key_stay, False)
                    self.update_webif(_key_enter, False)

                self.__logger.debug("State evaluation finished")
        self.__logger.info("State evaluation queue empty.")
        if self.update_lock.locked():
            self.update_lock.release()

    def update_webif(self, key, value):
        def _nested_set(dic, keys, val):
            for nestedkey in keys[:-1]:
                dic = dic.setdefault(nestedkey, {})
            dic[keys[-1]] = val

        def _nested_test(dic, keys):
            for nestedkey in keys[:-2]:
                dic = dic.setdefault(nestedkey, {})
            return dic[keys[-2]]

        if isinstance(key, list):
            try:
                _nested_test(self.__webif_infos, key)
                _nested_set(self.__webif_infos, key, value)
                return True
            except Exception:
                return False
        else:
            self.__webif_infos[key] = value
            return True

    def update_releasedby(self, state):
        # create dependencies
        _id = state.id
        _returnvalue, _returntype, _releasedby = state.update_releasedby_internal()
        _releasedby = _releasedby if isinstance(_releasedby, list) else \
            [_releasedby] if _releasedby is not None else []
        _convertedlist = []
        for entry in _releasedby:
            try:
                if entry is not None:
                    _convertedlist.append(entry.property.path)
                else:
                    self.__logger.warning("Found invalid state in se_released_by attribute. Ignoring {}", entry)
            except Exception as ex:
                self.__logger.error("Issue with {} for released_by check: {}", entry, ex)
        if _releasedby:
            self.__all_releasedby.update({_id: _convertedlist})
            self.__logger.debug("Updated releasedby for state {}: {}. All releasedby: {}", state, _releasedby, self.__all_releasedby)
            if self.__hasreleased_item is None or self.__has_released.get('initial'):
                self.__has_released.update({_id: _convertedlist})
                self.__logger.develop("Added to hasreleased: {} for state {}", self.__has_released, state)

        '''
        for i in _releasedby:
            if i.property.path not in self.__all_torelease.keys():
                self.__all_torelease.update({i: [_id]})
            elif state.id not in self.__all_torelease.get(i):
                self.__all_torelease[i].append(_id)
        '''

    def __check_releasedby(self, state, _checked_states, _releasedby, _wouldenter, _wouldnotenter,
                           _flagged, _laststate, _possible_states, result):
        self.__logger.develop("Self ID {}, flagged: {}, wouldnotenter {}", state.id, _flagged, _wouldnotenter)
        cond1 = state.id in _releasedby
        cond2 = self.__has_released.get(_wouldenter) and state.id in self.__has_released.get(_wouldenter)
        cond3 = self.__should_not_release.get(_wouldenter) and state.id in self.__should_not_release.get(_wouldenter)
        if cond1 and cond2:
            _releasedby.remove(state.id)
            self.__logger.develop("State {} has already released, removed from _releasedby {}. has_released = {}",
                                  state.id, _releasedby, self.__has_released)
            if cond3:
                self.__should_not_release.get(_wouldenter).remove(state.id)
                self.__logger.develop("State {} removed from shouldnotrelease {}", state.id, self.__should_not_release)
            if result is False:
                self.__has_released[_wouldenter].remove(state.id)
                self.__logger.develop("State {} removed from hasreleased because it got FALSE. {}", state.id,
                                      self.__has_released)
                _possible_state = None
            else:
                _possible_state = state
                self.__logger.debug("State {} added to possible_states as it is true", state.id)
            self.__logger.develop("Skipping rest of evaluation")
            return 'continue', _releasedby, _wouldenter, _wouldnotenter, None, _possible_state, _flagged
        if result is False and state.id in self.__all_releasedby.keys():
            _flagged = list(self.__all_releasedby.get(state.id))
            if state.id not in _wouldnotenter:
                _wouldnotenter.append(state.id)
            self.__logger.develop("FLAGGED {}, wouldnot {}", _flagged, _wouldnotenter)
        cond4 = result is True and _laststate == state and state.id in self.__all_releasedby.keys()
        if cond4:
            self.__logger.develop("State {} cond4. wouldenter: {}, releasedby {}.", state.id, _wouldenter, _releasedby)
            if _wouldenter:
                self.logger.debug("State {} could be released, too. Prevent layered releaseby", state.id)
            else:
                _releasedby = list(self.__all_releasedby.get(state.id))
                _wouldenter = state.id
                self.__logger.debug("State {} could be entered but can be released by {}.", state.id, _releasedby)
        elif result is True and not cond1 and not state.id == _wouldenter:
            _possible_state = state
            self.__logger.develop("State {} has nothing to do with release, writing down "
                                  "as possible candidate to enter", state.id)
            return 'nothing', _releasedby, _wouldenter, _wouldnotenter, None, _possible_state, _flagged
        if result is True and state.id in _flagged:
            self.__logger.develop("State {} should get added to shouldnotrelease {}. wouldnotenter = {}.",
                                  state.id, self.__should_not_release, _wouldnotenter)
            for entry in _wouldnotenter:
                if self.__should_not_release.get(entry):
                    if state.id not in self.__should_not_release[entry]:
                        self.__should_not_release[entry].append(state.id)
                else:
                    self.__should_not_release.update({entry: [state.id]})
                self.__logger.develop("State {} added to should not release of {}.", state.id, entry)
        if result is True and state.id in _releasedby:
            if self.__has_released.get(_wouldenter) and state.id in self.__has_released.get(_wouldenter):
                _releasedby.remove(state.id)
                self.__logger.develop("State {} has already released, removed from _releasedby {}. has_released = {}",
                                      state.id, _releasedby, self.__has_released)
            else:
                self.__logger.develop("shouldnotrelease: {}, wouldenter: {}", self.__should_not_release,
                                      _wouldenter)
                if self.__should_not_release.get(_wouldenter) and state.id in self.__should_not_release.get(
                        _wouldenter):
                    _releasedby.remove(state.id)
                    self.__logger.develop("State {} has not released yet, but it is in shouldnotrelease. "
                                          "Removed from releasedby {}.", state.id, _releasedby)
                    return 'continue', _releasedby, _wouldenter, _wouldnotenter, None, None, _flagged
                if self.__has_released.get(_wouldenter):
                    if state.id not in self.__has_released.get(_wouldenter):
                        self.__has_released[_wouldenter].append(state.id)
                        self.__logger.develop("State {} in releasedby, not released yet, appended to hasreleased {}",
                                              state.id, self.__has_released)
                else:
                    self.__has_released.update({_wouldenter: [state.id]})
                    self.__logger.develop("State {} in releasedby, created hasreleased {}",
                                          state.id, self.__has_released)
                self.__logger.develop("State {} has not released yet, could set as new state.", state.id)
                if _possible_states:
                    self.logger.develop("However, higher ranked state could be entered - entering that: {}",
                                        _possible_states)
                    new_state = _possible_states[0]
                else:
                    new_state = state
                return 'break', _releasedby, _wouldenter, _wouldnotenter, new_state, None, _flagged

        elif result is False:
            self.__logger.develop("State {} FALSE, has_released {}, _releasedby list {}, _wouldenter {}",
                               state.id, self.__has_released, _releasedby, _wouldenter)
            if _wouldenter is None:
                for entry in self.__has_released.keys():
                    if state.id in self.__has_released.get(entry):
                        self.__has_released[entry].remove(state.id)
                        self.__logger.develop("State {} removed from hasreleased because wouldenter is None. {}",
                                              state.id, self.__has_released)
                for entry in self.__should_not_release.keys():
                    if state.id in self.__should_not_release.get(entry):
                        self.__should_not_release[entry].remove(state.id)
                        self.__logger.develop("State {} removed from shouldnotrelease because wouldenter is None. {}",
                                              state.id, self.__has_released)
            if self.__has_released.get(_wouldenter) and state.id in self.__has_released.get(_wouldenter):
                self.__has_released[_wouldenter].remove(state.id)
                self.__should_not_release[_wouldenter].remove(state.id)
                self.__logger.develop("State {} in releasedby but FALSE, removed from hasreleased {} and shouldnot {}",
                                      state.id, self.__has_released, self.__should_not_release)
                if state.id in _releasedby:
                    _releasedby.remove(state.id)
                    self.__logger.develop("State {} removed from _releasedby {} because FALSE and hasreleased",
                                          state.id, _releasedby)
                    new_state = self.__state_ids[_wouldenter]
                    self.__logger.develop("State {} - Going back to {}", state.id, _wouldenter)
                    return 'break', _releasedby, _wouldenter, _wouldnotenter, new_state, None, _flagged
            elif state.id in _releasedby:
                _releasedby.remove(state.id)
                if self.__should_not_release.get(_wouldenter) and state.id in self.__should_not_release.get(
                        _wouldenter):
                    self.__should_not_release[_wouldenter].remove(state.id)
                    self.__logger.develop("State {} removed from shouldnotrelease FALSE", state.id,
                                          self.__should_not_release)
                self.__logger.develop("State {} removed from _releasedby {} because FALSE", state.id, _releasedby)
        if cond4 and _releasedby == self.__has_released.get(_wouldenter):
            _checked = True
            for entry in _checked_states:
                if entry not in _releasedby:
                    _checked = False
            if _checked is True:
                self.__logger.info("State {} could be releaed by {}, but those states already have released it",
                                   state.id, _releasedby)
                new_state = state
                return 'break', _releasedby, _wouldenter, _wouldnotenter, new_state, None, _flagged
            else:
                self.__logger.debug( "State {} still could be releaed by {}, have to check that value", state.id, _releasedby)
        return 'nothing', _releasedby, _wouldenter, _wouldnotenter, None, None, _flagged

    # Find the state, matching the current conditions and perform the actions of this state
    # caller: Caller that triggered the update
    # noinspection PyCallingNonCallable,PyUnusedLocal
    def update_state(self, item, caller=None, source=None, dest=None):
        if not self.__startup_delay_over:
            self.__logger.debug("Startup delay not over yet. Skipping state evaluation")
            return
        self.__queue.put(["stateevaluation", item, caller, source, dest])
        if not self.update_lock.locked():
            self.__logger.debug("Run queue to update state. Item: {}, caller: {}, source: {}".format(item, caller, source))
            self.run_queue()

    # check if state can be entered after setting state-specific variables
    # state: state to check
    def __update_check_can_enter(self, state):
        try:
            self.__variables["previous.state_id"] = self.__previousstate_internal_id
            self.__variables["previous.state_name"] = self.__previousstate_internal_name
            self.__variables["current.state_id"] = state.id
            self.__variables["current.state_name"] = state.name
            self.__variables["current.conditionset_id"] = self.__lastconditionset_internal_id
            self.__variables["current.conditionset_name"] = self.__lastconditionset_internal_name
            self.__variables["previous.conditionset_id"] = self.__previousconditionset_internal_id
            self.__variables["previous.conditionset_name"] = self.__previousconditionset_internal_name
            self.__variables["previous.state_conditionset_id"] = self.__previousstate_conditionset_internal_id
            self.__variables["previous.state_conditionset_name"] = self.__previousstate_conditionset_internal_name
            state.refill()
            return state.can_enter()
        except Exception as ex:
            self.__logger.warning("Problem with currentstate {0}. Error: {1}", state.id, ex)
        finally:
            self.__variables["current.state_id"] = ""
            self.__variables["current.state_name"] = ""
            self.__variables["current.conditionset_id"] = ""
            self.__variables["current.conditionset_name"] = ""
            self.__variables["previous.state_id"] = ""
            self.__variables["previous.state_name"] = ""
            self.__variables["previous.conditionset_id"] = ""
            self.__variables["previous.conditionset_name"] = ""
            self.__variables["previous.state_conditionset_id"] = ""
            self.__variables["previous.state_conditionset_name"] = ""

    # endregion

    # region Laststate *************************************************************************************************
    # Set laststate
    # new_state: new state to be used as laststate
    def __laststate_set(self, new_state):
        self.__laststate_internal_id = '' if new_state is None else new_state.id
        if self.__laststate_item_id is not None:
            # noinspection PyCallingNonCallable
            self.__laststate_item_id(self.__laststate_internal_id, StateEngineDefaults.plugin_identification, "StateEvaluation")

        self.__laststate_internal_name = '' if new_state is None else new_state.text
        if self.__laststate_item_name is not None:
            # noinspection PyCallingNonCallable
            self.__laststate_item_name(self.__laststate_internal_name, StateEngineDefaults.plugin_identification, "StateEvaluation")
        self.__logger.develop("Setting last state to {0} ('{1}')", self.__laststate_internal_id, self.__laststate_internal_name)

    # get last state object based on laststate_id
    # returns: SeState instance of last state or "None" if no last state could be found
    def __laststate_get(self):
        for state in self.__states:
            if state.id == self.__laststate_internal_id:
                return state
        return None

    # return id of last conditionset
    def __lastconditionset_get_id(self):
        _lastconditionset_item_id = self.return_item_by_attribute("se_lastconditionset_item_id")
        _lastconditionset_item_id = "" if _lastconditionset_item_id is None else _lastconditionset_item_id.property.value
        return _lastconditionset_item_id

    # return name of last conditionset
    def __lastconditionset_get_name(self):
        _lastconditionset_item_name = self.return_item_by_attribute("se_lastconditionset_item_name")
        _lastconditionset_item_name = "" if _lastconditionset_item_name is None else _lastconditionset_item_name.property.value
        return _lastconditionset_item_name

    def lastconditionset_set(self, new_id, new_name):
        self.__lastconditionset_internal_id = new_id
        if self.__lastconditionset_item_id is not None:
            # noinspection PyCallingNonCallable
            self.__lastconditionset_item_id(self.__lastconditionset_internal_id, StateEngineDefaults.plugin_identification, "StateEvaluation")

        self.__lastconditionset_internal_name = new_name
        if self.__lastconditionset_item_name is not None:
            # noinspection PyCallingNonCallable
            self.__lastconditionset_item_name(self.__lastconditionset_internal_name, StateEngineDefaults.plugin_identification, "StateEvaluation")
        self.__logger.develop("Setting current Conditionset to {0} ('{1}')", self.__lastconditionset_internal_id, self.__lastconditionset_internal_name)

    # endregion

    # region Previousstate *************************************************************************************************
    # Set previousstate
    # last_state: last state to be used as previousstate
    def __previousstate_set(self, last_state):
        self.__previousstate_internal_id = 'None' if last_state is None else last_state.id
        if self.__previousstate_item_id is not None:
            # noinspection PyCallingNonCallable
            self.__previousstate_item_id(self.__previousstate_internal_id, StateEngineDefaults.plugin_identification, "StateEvaluation")

        self.__previousstate_internal_name = 'None' if last_state is None else last_state.text
        if self.__previousstate_item_name is not None:
            # noinspection PyCallingNonCallable
            self.__previousstate_item_name(self.__previousstate_internal_name, StateEngineDefaults.plugin_identification, "StateEvaluation")

    # get previous state object based on previousstate_id
    # returns: SeState instance of last state or "None" if no last state could be found
    def __previousstate_get(self):
        for state in self.__states:
            if state.id == self.__previousstate_internal_id:
                return state
        return None

    # return id of last conditionset
    def __previousconditionset_get_id(self):
        _previousconditionset_item_id = self.return_item_by_attribute("se_previousconditionset_item_id")
        _previousconditionset_item_id = "" if _previousconditionset_item_id is None else _previousconditionset_item_id.property.value
        return _previousconditionset_item_id

    # return name of last conditionset
    def __previousconditionset_get_name(self):
        _previousconditionset_item_name = self.return_item_by_attribute("se_previousconditionset_item_name")
        _previousconditionset_item_name = "" if _previousconditionset_item_name is None else _previousconditionset_item_name.property.value
        return _previousconditionset_item_name

    # return id of conditionset of last state
    def __previousstate_conditionset_get_id(self):
        _previousconditionset_item_id = self.return_item_by_attribute("se_previousstate_conditionset_item_id")
        _previousconditionset_item_id = "" if _previousstate_conditionset_item_id is None else _previousstate_conditionset_item_id.property.value
        return _previousconditionset_item_id

    # return name of conditionset of last state
    def __previousstate_conditionset_get_name(self):
        _previousconditionset_item_name = self.return_item_by_attribute("se_previousstate_conditionset_item_name")
        _previousconditionset_item_name = "" if _previousstate_conditionset_item_name is None else _previousstate_conditionset_item_name.property.value
        return _previousconditionset_item_name

    def previousconditionset_set(self, last_id, last_name):
        self.__previousconditionset_internal_id = last_id
        if self.__previousconditionset_item_id is not None:
            # noinspection PyCallingNonCallable
            self.__previousconditionset_item_id(self.__previousconditionset_internal_id, StateEngineDefaults.plugin_identification, "StateEvaluation")

        self.__previousconditionset_internal_name = last_name
        if self.__previousconditionset_item_name is not None:
            # noinspection PyCallingNonCallable
            self.__previousconditionset_item_name(self.__previousconditionset_internal_name, StateEngineDefaults.plugin_identification, "StateEvaluation")
        self.__logger.develop("Setting previous Conditionset to {0} ('{1}')", self.__previousconditionset_internal_id, self.__previousconditionset_internal_name)

    def previousstate_conditionset_set(self, last_id, last_name):
        self.__previousstate_conditionset_internal_id = last_id
        if self.__previousstate_conditionset_item_id is not None:
            # noinspection PyCallingNonCallable
            self.__previousstate_conditionset_item_id(self.__previousstate_conditionset_internal_id, StateEngineDefaults.plugin_identification, "StateEvaluation")

        self.__previousstate_conditionset_internal_name = last_name
        if self.__previousstate_conditionset_item_name is not None:
            # noinspection PyCallingNonCallable
            self.__previousstate_conditionset_item_name(self.__previousstate_conditionset_internal_name, StateEngineDefaults.plugin_identification, "StateEvaluation")
        self.__logger.develop("Setting Conditionset of previous state to {0} ('{1}')", self.__previousstate_conditionset_internal_id, self.__previousstate_conditionset_internal_name)

    # endregion

    # region Helper methods ********************************************************************************************
    # add all required triggers
    def __add_triggers(self):
        # add item trigger
        self.__item.add_method_trigger(self.update_state)

    # Check item settings and update if required
    # noinspection PyProtectedMember
    def __check_item_config(self):
        # set "enforce updates" for item
        self.__item._enforce_updates = True

        # Update item from grandparent_item
        for attribute in self.__item.conf:
            func, name = StateEngineTools.partition_strip(attribute, "_")
            if name == "":
                continue

            # update item/eval in this condition
            if func == "se_template":
                if name not in self.__templates:
                    self.__templates[name] = self.__item.conf[attribute]

        # set "eval" for item if initial
        if self.__item._trigger and self.__item._eval is None:
            self.__item._eval = "1"

        # Check scheduler settings and update if required

        job = self.__sh.scheduler._scheduler.get("items.{}".format(self.id))
        if job is None:
            # We do not have a scheduler job so there is nothing to check and update
            return

        changed = False

        # inject value into cycle if required
        if "cycle" in job and job["cycle"] is not None:
            cycle = list(job["cycle"].keys())[0]
            old_cycle = cycle
            value = job["cycle"][cycle]
            if value is None:
                value = "1"
                changed = True
            new_cycle = {cycle: value}
        else:
            old_cycle = None
            new_cycle = None

        # inject value into cron if required
        if "cron" in job and job["cron"] is not None:
            new_cron = {}
            old_cron = job["cron"]
            for entry, value in job['cron'].items():
                if value is None:
                    value = 1
                    changed = True
                new_cron[entry] = value
        else:
            old_cron = None
            new_cron = None
        self.__logger.info("Old cycle '{}' updated to '{}'. Old cron '{}' updated to '{}'",
                           old_cycle, new_cycle, old_cron, new_cron)
        # change scheduler settings if cycle or cron have been changed
        if changed:
            self.__sh.scheduler.change("items.{}".format(self.id), cycle=new_cycle, cron=new_cron)

    # get triggers in readable format
    def __verbose_triggers(self):
        # noinspection PyProtectedMember
        if not self.__item._trigger:
            return "Inactive"

        triggers = ""
        # noinspection PyProtectedMember
        for trigger in self.__item._trigger:
            if triggers != "":
                triggers += ", "
            triggers += trigger
        return triggers

    # get crons and cycles in readable format
    def __verbose_crons_and_cycles(self):
        # get crons and cycles
        cycles = ""
        crons = ""

        # noinspection PyProtectedMember
        job = self.__sh.scheduler._scheduler.get("items.{}".format(self.id))

        if job is not None:
            if "cycle" in job and job["cycle"] is not None:
                cycle = list(job["cycle"].keys())[0]
                cycles = "every {0} seconds".format(cycle)

            # inject value into cron if required
            if "cron" in job and job["cron"] is not None:
                for entry in job['cron']:
                    if crons != "":
                        crons += ", "
                    crons += entry

        if cycles == "":
            cycles = "Inactive"
        if crons == "":
            crons = "Inactive"
        return crons, cycles

    # log item data
    def __write_to_log(self):
        # get crons and cycles
        crons, cycles = self.__verbose_crons_and_cycles()
        triggers = self.__verbose_triggers()

        # log general config
        self.__logger.info("".ljust(80, "_"))
        self.__logger.header("Configuration of item {0}".format(self.__id))
        self.__startup_delay.write_to_logger()
        self.__suspend_time.write_to_logger()
        self.__instant_leaveaction.write_to_logger()
        for t in self.__templates:
            self.__logger.info("Template {0}: {1}", t, self.__templates.get(t))
        self.__logger.info("Cycle: {0}", cycles)
        self.__logger.info("Cron: {0}", crons)
        self.__logger.info("Trigger: {0}".format(triggers))
        self.__repeat_actions.write_to_logger()

        # log laststate settings
        if self.__laststate_item_id is not None:
            self.__logger.info("Item 'Laststate Id': {0}", self.__laststate_item_id.property.path)
        if self.__laststate_item_name is not None:
            self.__logger.info("Item 'Laststate Name': {0}", self.__laststate_item_name.property.path)

        # log previousstate settings
        if self.__previousstate_item_id is not None:
            self.__logger.info("Item 'Previousstate Id': {0}", self.__previousstate_item_id.property.path)
        if self.__previousstate_item_name is not None:
            self.__logger.info("Item 'Previousstate Name': {0}", self.__previousstate_item_name.property.path)

        # log releasedby settings
        if self.___shouldnotrelease_item is not None:
            self.__logger.info("Item 'Should not release': {0}", self.___shouldnotrelease_item.property.path)
        if self.__hasreleased_item is not None:
            self.__logger.info("Item 'Has released': {0}", self.__hasreleased_item.property.path)

        # log lastcondition settings
        _conditionset_id = self.return_item_by_attribute("se_lastconditionset_item_id")
        _conditionset_name = self.return_item_by_attribute("se_lastconditionset_item_name")
        if _conditionset_id is not None:
            self.__logger.info("Item 'Lastcondition Id': {0}", _conditionset_id.property.path)
        if _conditionset_name is not None:
            self.__logger.info("Item 'Lastcondition Name': {0}", _conditionset_name.property.path)

        # log previouscondition settings
        _previousconditionset_id = self.return_item_by_attribute("se_previousconditionset_item_id")
        _previousconditionset_name = self.return_item_by_attribute("se_previousconditionset_item_name")
        if _previousconditionset_id is not None:
            self.__logger.info("Item 'Previouscondition Id': {0}", _previousconditionset_id.property.path)
        if _previousconditionset_name is not None:
            self.__logger.info("Item 'Previouscondition Name': {0}", _previousconditionset_name.property.path)

        _previousstate_conditionset_id = self.return_item_by_attribute("se_previousstate_conditionset_item_id")
        _previousstate_conditionset_name = self.return_item_by_attribute("se_previousstate_conditionset_item_name")
        if _previousstate_conditionset_id is not None:
            self.__logger.info("Item 'Previouscondition Id': {0}", _previousstate_conditionset_id.property.path)
        if _previousstate_conditionset_name is not None:
            self.__logger.info("Item 'Previouscondition Name': {0}", _previousstate_conditionset_name.property.path)

        # log states
        for state in self.__states:
            # Update Releasedby Dict
            self.update_releasedby(state)
            state.write_to_log()
            self._initstate = None

    # endregion

    # region Methods for CLI commands **********************************************************************************
    def cli_list(self, handler):
        handler.push("{0}: {1}\n".format(self.id, self.__laststate_internal_name))

    def cli_detail(self, handler):
        # get data
        crons, cycles = self.__verbose_crons_and_cycles()
        triggers = self.__verbose_triggers()
        handler.push("AutoState Item {0}:\n".format(self.id))
        handler.push("\tCurrent state: {0} ('{1}')\n".format(self.get_laststate_id(), self.get_laststate_name()))
        handler.push("\tCurrent conditionset: {0} ('{1}')\n".format(self.get_lastconditionset_id(), self.get_lastconditionset_name()))
        handler.push("\tPrevious state: {0} ('{1}')\n".format(self.get_previousstate_id(), self.get_previousstate_name()))
        handler.push("\tPrevious state conditionset: {0} ('{1}')\n".format(self.get_previousstate_conditionset_id(), self.get_previousstate_conditionset_name()))
        handler.push("\tPrevious conditionset: {0} ('{1}')\n".format(self.get_previousconditionset_id(), self.get_previousconditionset_name()))
        handler.push(self.__startup_delay.get_text("\t", "\n"))
        handler.push("\tCycle: {0}\n".format(cycles))
        handler.push("\tCron: {0}\n".format(crons))
        handler.push("\tTrigger: {0}\n".format(triggers))
        handler.push(self.__repeat_actions.get_text("\t", "\n"))

    # endregion

    # region Getter methods for "special" conditions *******************************************************************
    # return age of item
    def get_age(self):
        if self.__laststate_item_id is not None:
            return self.__laststate_item_id.property.last_change_age
        else:
            self.__logger.warning('No item for last state id given. Can not determine age!')
            return 0

    def get_condition_age(self):
        if self.__lastconditionset_item_id is not None:
            return self.__lastconditionset_item_id.property.last_change_age
        else:
            self.__logger.warning('No item for last condition id given. Can not determine age!')
            return 0

    # return id of last state
    def get_laststate_id(self):
        return self.__laststate_internal_id

    # return name of last state
    def get_laststate_name(self):
        return self.__laststate_internal_name

    # return id of last conditionset
    def get_lastconditionset_id(self):
        return self.__lastconditionset_internal_id

    # return name of last conditionset
    def get_lastconditionset_name(self):
        return self.__lastconditionset_internal_name

    # return id of previous state
    def get_previousstate_id(self):
        return self.__previousstate_internal_id

    # return name of last state
    def get_previousstate_name(self):
        return self.__previousstate_internal_name

    # return id of last conditionset
    def get_previousconditionset_id(self):
        return self.__previousconditionset_internal_id

    # return name of last conditionset
    def get_previousconditionset_name(self):
        return self.__previousconditionset_internal_name

    # return id of last state's conditionset
    def get_previousstate_conditionset_id(self):
        return self.__previousstate_conditionset_internal_id

    # return name of last state's conditionset
    def get_previousstate_conditionset_name(self):
        return self.__previousstate_conditionset_internal_name

    # return update trigger item
    def get_update_trigger_item(self):
        return self.__update_trigger_item

    # return update trigger caller
    def get_update_trigger_caller(self):
        return self.__update_trigger_caller

    # return update trigger source
    def get_update_trigger_source(self):
        return self.__update_trigger_source

    # return update trigger dest
    def get_update_trigger_dest(self):
        return self.__update_trigger_dest

    # return update original item
    def get_update_original_item(self):
        return self.__update_original_item

    # return update original caller
    def get_update_original_caller(self):
        return self.__update_original_caller

    # return update original source
    def get_update_original_source(self):
        return self.__update_original_source

    # return value of variable
    def get_variable(self, varname):
        return self.__variables[varname] if varname in self.__variables else "(Unknown variable '{0}'!)".format(varname)

    # set value of variable
    def set_variable(self, varname, value):
        if varname not in self.__variables:
            raise ValueError("Unknown variable '{0}!".format(varname))
        self.__variables[varname] = value

    # endregion

    # callback function that is called after the startup delay
    # noinspection PyUnusedLocal
    def __startup_delay_callback(self, item, caller=None, source=None, dest=None):
        scheduler_name = self.__id + "-Startup Delay"
        if not self.__ab_alive and self.__se_plugin.scheduler_get(scheduler_name):
            next_run = self.__shtime.now() + datetime.timedelta(seconds=3)
            self.__logger.debug(
                "Startup Delay over but StateEngine Plugin not running yet. Will try again at {}".format(next_run))
            self.__se_plugin.scheduler_change(scheduler_name, next=next_run)
            self.__se_plugin.scheduler_trigger(scheduler_name)
        else:
            self.__startup_delay_over = True
            if self.__se_plugin.scheduler_get(scheduler_name):
                self.__se_plugin.scheduler_remove(scheduler_name)
                self.__logger.debug('Startup Delay over. Removed scheduler {}', scheduler_name)
            self.update_state(item, "Startup Delay", source, dest)
            self.__add_triggers()

    # Return an item related to the StateEngine Object Item
    # item_id: Id of item to return
    #
    # With this function it is possible to provide items relative to the current StateEngine object item.
    # If an item_id starts with one or more ".", the item is relative to the StateEngine object item. One "." means
    # that the given item Id is relative to the current level of the StateEngine object item. Every additional "."
    # removes one level of the StateEngine object item before adding the item_id.
    # Examples (based on StateEngine object item "my.stateengine.objectitem":
    # - item_id = "not.prefixed.with.dots" will return item "not.prefixed.with.dots"
    # - item_id = ".onedot" will return item "my.stateengine.objectitem.onedot"
    # - item_id = "..twodots" will return item "my.stateengine.twodots"
    # - item_id = "..threedots" will return item "my.threedots"
    # - item_id = "..threedots.further.down" will return item "my.threedots.further.down"
    def return_item(self, item_id):
        if isinstance(item_id, (StateEngineStruct.SeStruct, self.__itemClass)):
            return item_id
        if isinstance(item_id, StateEngineState.SeState):
            return self.itemsApi.return_item(item_id.id)
        if item_id is None:
            return None
        if not isinstance(item_id, str):
            self.__logger.info("'{0}' should be defined as string. Check your item config! "
                               "Everything might run smoothly, nevertheless.".format(item_id))
            return item_id
        item_id = item_id.strip()
        if item_id.startswith("struct:"):
            item = None
            _, item_id = StateEngineTools.partition_strip(item_id, ":")
            try:
                #self.__logger.debug("Creating struct for id {}".format(item_id))
                item = StateEngineStructs.create(self, item_id)
            except Exception as e:
                self.__logger.error("struct {} creation failed. Error: {}".format(item_id, e))
            if item is None:
                self.__logger.warning("Item '{0}' not found!".format(item_id))
            return item
        if not item_id.startswith("."):
            item = self.itemsApi.return_item(item_id)
            if item is None:
                self.__logger.warning("Item '{0}' not found!".format(item_id))
            return item
        self.__logger.debug("Testing for relative item declaration {}".format(item_id))
        parent_level = 0
        for c in item_id:
            if c != '.':
                break
            parent_level += 1

        levels = self.id.split(".")
        use_num_levels = len(levels) - parent_level + 1
        if use_num_levels < 0:
            text = "Item '{0}' can not be determined. Parent item '{1}' has only {2} levels!"
            raise ValueError(text.format(item_id, self.id, len(levels)))
        result = ""
        for level in levels[0:use_num_levels]:
            result += level if result == "" else "." + level
        rel_item_id = item_id[parent_level:]
        if rel_item_id != "":
            result += "." + rel_item_id
        item = self.itemsApi.return_item(result)
        if item is None:
            self.__logger.warning("Determined item '{0}' does not exist.".format(result))
        else:
            self.__logger.develop("Determined item '{0}' for id {1}.".format(item.id, item_id))
        return item

    # Return an item related to the StateEngine object item
    # attribute: Name of the attribute of the StateEngine object item, which contains the item_id to read
    def return_item_by_attribute(self, attribute):
        if attribute not in self.__item.conf:
            self.__logger.warning("Problem with attribute '{0}'.".format(attribute))
            return None
        return self.return_item(self.__item.conf[attribute])
