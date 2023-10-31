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
from collections import OrderedDict, defaultdict

import lib.item.item
from . import StateEngineTools
from .StateEngineLogger import SeLogger
from . import StateEngineState
from . import StateEngineDefaults
from . import StateEngineCurrent
from . import StateEngineValue
from . import StateEngineStruct
from . import StateEngineStructs
from . import StateEngineEval

from lib.item import Items
from lib.shtime import Shtime
from lib.item.item import Item
import copy
import threading
import queue
import re
from ast import literal_eval


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
    def firstrun(self):
        return self.__first_run

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
        return self.__instant_leaveaction.get()

    @property
    def default_instant_leaveaction(self):
        return self.__default_instant_leaveaction.get()

    @default_instant_leaveaction.setter
    def default_instant_leaveaction(self, value):
        self.__default_instant_leaveaction.set(value)

    @property
    def laststate(self):
        _returnvalue = None if self.__laststate_item_id is None else self.__laststate_item_id.property.value
        return _returnvalue

    @property
    def laststate_releasedby(self):
        _returnvalue = None if self.__laststate_item_id is None \
                       else self.__release_info.get(self.__laststate_item_id.property.value)
        return _returnvalue

    @property
    def previousstate(self):
        _returnvalue = None if self.__previousstate_item_id is None else self.__previousstate_item_id.property.value
        return _returnvalue

    @property
    def lastconditionset(self):
        _returnvalue = None if self.__lastconditionset_item_id is None else self.__lastconditionset_item_id.property.value
        return _returnvalue

    @property
    def previousconditionset(self):
        _returnvalue = None if self.__previousconditionset_item_id is None else self.__previousconditionset_item_id.property.value
        return _returnvalue

    @property
    def previousstate_conditionset(self):
        _returnvalue = None if self.__previousstate_conditionset_item_id is None else self.__previousstate_conditionset_item_id.property.value
        return _returnvalue

    @property
    def laststate_name(self):
        _returnvalue = None if self.__laststate_item_name is None else self.__laststate_item_name.property.value
        return _returnvalue

    @property
    def previousstate_name(self):
        _returnvalue = None if self.__previousstate_item_name is None else self.__previousstate_item_name.property.value
        return _returnvalue

    @property
    def lastconditionset_name(self):
        _returnvalue = None if self.__lastconditionset_item_name is None else self.__lastconditionset_item_name.property.value
        return _returnvalue

    @property
    def previousconditionset_name(self):
        _returnvalue = None if self.__previousconditionset_item_name is None else self.__previousconditionset_item_name.property.value
        return _returnvalue

    @property
    def previousstate_conditionset_name(self):
        _returnvalue = None if self.__previousstate_conditionset_item_name is None else self.__previousstate_conditionset_item_name.property.value
        return _returnvalue

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
        self.__release_info = {}
        self.__default_instant_leaveaction = StateEngineValue.SeValue(self, "Default Instant Leave Action", False, "bool")
        self.__instant_leaveaction = StateEngineValue.SeValue(self, "Instant Leave Action", False, "num")
        try:
            self.__id = self.__item.property.path
        except Exception:
            self.__id = item
        self.__name = str(self.__item)
        self.__itemClass = Item
        # initialize logging

        self.__log_level = StateEngineValue.SeValue(self, "Log Level", False, "num")

        _default_log_level = SeLogger.default_log_level.get()
        _returnvalue, _returntype, _using_default, _issue = self.__log_level.set_from_attr(self.__item, "se_log_level",
                                                                                           _default_log_level)
        self.__using_default_log_level = _using_default
        _returnvalue = self.__log_level.get()
        if isinstance(_returnvalue, list) and len(_returnvalue) == 1:
            _returnvalue = _returnvalue[0]
        self.__logger.log_level_as_num = 2
        self.__logger.header("")

        _startup_log_level = SeLogger.startup_log_level.get()

        if _startup_log_level > 0:
            base = self.__sh.get_basedir()
            SeLogger.manage_logdirectory(base, SeLogger.log_directory, True)
        self.__logger.log_level_as_num = _startup_log_level
        self.__logger.info("Set log level to startup log level {}", _startup_log_level)

        if isinstance(_returnvalue, list) and len(_returnvalue) > 1:
            self.__logger.warning("se_log_level for item {} can not be defined as a list"
                                  " ({}). Using default value {}.", self.id, _returnvalue, _default_log_level)
            self.__log_level.set(_default_log_level)
        elif _returnvalue is None:
            self.__log_level.set(_default_log_level)
            self.__logger.header("Initialize Item {0} (Log {1}, Level set"
                                 " to {2} based on default log level"
                                 " because se_log_level has issues)".format(self.id, self.__logger.name,
                                                                            _default_log_level))
        elif _using_default:
            self.__logger.header("Initialize Item {0} (Log {1}, Level set"
                                 " to {2} based on default log level {3})".format(self.id, self.__logger.name,
                                                                                  _returnvalue, _default_log_level))
        else:
            self.__logger.header("Initialize Item {0} (Log {1}, Level set"
                                 " to {2}, default log level is {3})".format(self.id, self.__logger.name,
                                                                             _returnvalue, _default_log_level))

        # get startup delay
        self.__startup_delay = StateEngineValue.SeValue(self, "Startup Delay", False, "num")
        self.__startup_delay.set_from_attr(self.__item, "se_startup_delay", StateEngineDefaults.startup_delay)
        self.__startup_delay_over = False

        # Init suspend settings
        self.__default_suspend_time = StateEngineDefaults.suspend_time.get()
        self.__suspend_time = StateEngineValue.SeValue(self, "Suspension time on manual changes", False, "num")
        self.__suspend_time.set_from_attr(self.__item, "se_suspend_time", self.__default_suspend_time)

        # Init laststate and previousstate items/values
        self.__config_issues = {}
        self.__laststate_item_id, _issue = self.return_item_by_attribute("se_laststate_item_id")
        self.__laststate_internal_id = "" if self.__laststate_item_id is None else self.__laststate_item_id.property.value
        self.__config_issues.update(_issue)
        self.__laststate_item_name, _issue = self.return_item_by_attribute("se_laststate_item_name")
        self.__laststate_internal_name = "" if self.__laststate_item_name is None else self.__laststate_item_name.property.value
        self.__config_issues.update(_issue)
        self.__previousstate_item_id, _issue = self.return_item_by_attribute("se_previousstate_item_id")
        self.__previousstate_internal_id = "" if self.__previousstate_item_id is None else self.__previousstate_item_id.property.value
        self.__config_issues.update(_issue)
        self.__previousstate_item_name, _issue = self.return_item_by_attribute("se_previousstate_item_name")
        self.__previousstate_internal_name = "" if self.__previousstate_item_name is None else self.__previousstate_item_name.property.value
        self.__config_issues.update(_issue)

        # Init lastconditionset items/values
        self.__lastconditionset_item_id, _issue = self.return_item_by_attribute("se_lastconditionset_item_id")
        self.__lastconditionset_internal_id = "" if self.__lastconditionset_item_id is None else \
            self.__lastconditionset_item_id.property.value
        self.__config_issues.update(_issue)
        self.__lastconditionset_item_name, _issue = self.return_item_by_attribute("se_lastconditionset_item_name")
        self.__lastconditionset_internal_name = "" if self.__lastconditionset_item_name is None else \
            self.__lastconditionset_item_name.property.value
        self.__config_issues.update(_issue)

        # Init previousconditionset items/values
        self.__previousconditionset_item_id, _issue = self.return_item_by_attribute("se_previousconditionset_item_id")
        self.__previousconditionset_internal_id = "" if self.__previousconditionset_item_id is None else \
            self.__previousconditionset_item_id.property.value
        self.__config_issues.update(_issue)
        self.__previousconditionset_item_name, _issue = self.return_item_by_attribute("se_previousconditionset_item_name")
        self.__previousconditionset_internal_name = "" if self.__previousconditionset_item_name is None else \
            self.__previousconditionset_item_name.property.value
        self.__config_issues.update(_issue)

        self.__previousstate_conditionset_item_id, _issue = self.return_item_by_attribute(
            "se_previousstate_conditionset_item_id")
        self.__previousstate_conditionset_internal_id = "" if self.__previousstate_conditionset_item_id is None else \
            self.__previousstate_conditionset_item_id.property.value
        self.__config_issues.update(_issue)
        self.__previousstate_conditionset_item_name, _issue = self.return_item_by_attribute(
            "se_previousstate_conditionset_item_name")
        self.__previousstate_conditionset_internal_name = "" if self.__previousstate_conditionset_item_name is None else \
            self.__previousstate_conditionset_item_name.property.value
        self.__config_issues.update(_issue)
        filtered_dict = {key: value for key, value in self.__config_issues.items() if value.get('issue') not in [[], [None], None]}
        self.__config_issues = filtered_dict

        self.__states = []
        self.__state_ids = {}
        self.__conditionsets = {}
        self.__templates = {}
        self.__unused_attributes = {}
        self.__used_attributes = {}
        self.__action_status = {}
        self.__state_issues = {}
        self.__struct_issues = {}
        self.__webif_infos = OrderedDict()

        self.__repeat_actions = StateEngineValue.SeValue(self, "Repeat actions if state is not changed", False, "bool")
        self.__repeat_actions.set_from_attr(self.__item, "se_repeat_actions", True)
        self.__first_run = None
        self._initstate = None
        self._initactionname = None
        self.__update_trigger_item = None
        self.__update_trigger_caller = None
        self.__update_trigger_source = None
        self.__update_trigger_dest = None
        self.__update_original_item = None
        self.__update_original_caller = None
        self.__update_original_source = None
        self.__using_default_instant_leaveaction = False
        self.__using_default_suspendtime = False

        # Check item configuration
        self.__check_item_config()

        # Init variables
        self.__variables = {
            "item.suspend_time": self.__suspend_time.get(),
            "item.suspend_remaining": 0,
            "item.instant_leaveaction": 0,
            "release.can_release": "",
            "release.can_be_released_by": "",
            "release.has_released": "",
            "release.was_released_by": "",
            "release.will_release": "",
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
        try:
            _statecount = 1
            for item_state in self.__item.return_children():
                _statecount = self.__initialize_state(item_state, _statecount)
        except Exception as ex:
            self.__logger.error("Ignoring stateevaluation for {} because {}", self.__id, ex)
        self.__reorder_states()
        try:
            self.__finish_states()
        except Exception as ex:
            self.__logger.error("Issue finishing states because {}", ex)
            return


    def __repr__(self):
        return self.__id

    def startup(self):
        self.__logger.info("".ljust(80, "_"))
        # start timer with startup-delay
        _startup_delay_param = self.__startup_delay.get()
        startup_delay = 1 if self.__startup_delay.is_empty() or _startup_delay_param == 0 else _startup_delay_param
        if startup_delay > 0:
            first_run = self.__shtime.now() + datetime.timedelta(seconds=startup_delay)
            self.__first_run = first_run.strftime('%H:%M:%S, %d.%m.')
            self.__logger.info("Will start stateengine evaluation at {}", self.__first_run)
            scheduler_name = self.__id + "-Startup Delay"
            value = {"item": self.__item, "caller": "Init"}
            self.__se_plugin.scheduler_add(scheduler_name, self.__startup_delay_callback, value=value, next=first_run)
        elif startup_delay == -1:
            self.__startup_delay_over = True
            self.__first_run = None
            self.__add_triggers()
        else:
            self.__startup_delay_callback(self.__item, "Init", None, None)
        _log_level = self.__log_level.get()
        self.__logger.info("Reset log level to {}", _log_level)
        self.__logger.log_level_as_num = _log_level

    def show_issues_summary(self):
        # show issues summary
        filtered_dict = {key: value for key, value in self.__unused_attributes.items() if
                         key not in self.__used_attributes or 'issue' in value.keys()}
        self.__unused_attributes = filtered_dict

        self.__logger.info("".ljust(80, "_"))
        issues = 0
        if self.__config_issues:
            issues += 1
            self.__log_issues('config entries')
        if self.__unused_attributes:
            issues += 1
            self.__log_issues('attributes')
        if self.__action_status:
            issues += 1
            self.__log_issues('actions')
        if self.__state_issues:
            issues += 1
            self.__log_issues('states')
        if self.__struct_issues:
            issues += 1
            self.__log_issues('structs')
        if issues == 0:
            self.__logger.info("No configuration issues found. Congratulations ;)")

    def update_leave_action(self, default_instant_leaveaction):
        default_instant_leaveaction_value = default_instant_leaveaction.get()
        self.__default_instant_leaveaction = default_instant_leaveaction

        _returnvalue_leave, _returntype_leave, _using_default_leave, _issue = self.__instant_leaveaction.set_from_attr(
            self.__item, "se_instant_leaveaction", default_instant_leaveaction)

        if len(_returnvalue_leave) > 1:
            self.__logger.warning("se_instant_leaveaction for item {} can not be defined as a list"
                                  " ({}). Using default value {}.", self.id, _returnvalue_leave,
                                  default_instant_leaveaction_value)
            self.__instant_leaveaction = default_instant_leaveaction
            self.__variables.update({"item.instant_leaveaction": default_instant_leaveaction_value})
        elif len(_returnvalue_leave) == 1 and _returnvalue_leave[0] is None:
            self.__instant_leaveaction = default_instant_leaveaction
            self.__variables.update({"item.instant_leaveaction": default_instant_leaveaction_value})
            self.__logger.info("Using default instant_leaveaction {0} "
                               "as no se_instant_leaveaction is set.".format(default_instant_leaveaction_value))
        elif _using_default_leave:
            self.__variables.update({"item.instant_leaveaction": default_instant_leaveaction_value})
            self.__logger.info("Using default instant_leaveaction {0} "
                               "as no se_instant_leaveaction is set.".format(default_instant_leaveaction_value))
        else:
            self.__variables.update({"item.instant_leaveaction": _returnvalue_leave})
            self.__logger.info("Using instant_leaveaction {0} "
                               "from attribute se_instant_leaveaction. "
                               "Default value is {1}".format(_returnvalue_leave, default_instant_leaveaction_value))

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
            self.__logger.debug("{} not running (anymore). Queue not activated.",
                                StateEngineDefaults.plugin_identification)
            return
        _current_log_level = self.__log_level.get()
        _default_log_level = SeLogger.default_log_level.get()

        if _current_log_level <= -1:
            self.__using_default_log_level = True
            value = SeLogger.default_log_level.get()
        else:
            value = _current_log_level
            self.__using_default_log_level = False
        self.__logger.log_level_as_num = value

        if _current_log_level > 0:
            base = self.__sh.get_basedir()
            SeLogger.manage_logdirectory(base, SeLogger.log_directory, True)
        additional_text = ", currently using default" if self.__using_default_log_level is True else ""
        self.__logger.info("Current log level {} ({}), default {}{}",
                            _current_log_level, type(self.__logger.log_level), _default_log_level, additional_text)
        _instant_leaveaction = self.__instant_leaveaction.get()
        _default_instant_leaveaction_value = self.__default_instant_leaveaction.get()
        if _instant_leaveaction <= -1:
            self.__using_default_instant_leaveaction = True
            additional_text = ", currently using default"
        elif _instant_leaveaction > 1:
            self.__logger.info("Current se_instant_leaveaction {} is invalid. "
                               "It has to be set to -1, 0 or 1. Setting it to 1 instead.", _instant_leaveaction)
            _instant_leaveaction = 1
            self.__using_default_instant_leaveaction = False
            additional_text = ""
        else:
            self.__using_default_instant_leaveaction = False
            additional_text = ""
        self.__logger.debug("Current instant leave action {}, default {}{}",
                            _instant_leaveaction, _default_instant_leaveaction_value, additional_text)
        _suspend_time = self.__suspend_time.get()
        if _suspend_time < 0:
            self.__using_default_suspendtime = True
            additional_text = ", currently using default"
        else:
            self.__using_default_suspendtime = False
            additional_text = ""
        self.__logger.debug("Current suspend time {}, default {}{}",
                            _suspend_time, self.__default_suspend_time, additional_text)
        self.update_lock.acquire(True, 10)
        self.__reorder_states(init=False)
        all_released_by = {}
        new_state = None
        if self.__using_default_instant_leaveaction:
            _instant_leaveaction = _default_instant_leaveaction_value
        else:
            _instant_leaveaction = True if _instant_leaveaction == 1 else False
        while not self.__queue.empty() and self.__ab_alive:
            job = self.__queue.get()
            new_state = None
            if job is None or self.__ab_alive is False:
                self.__logger.debug("No jobs in queue left or plugin not active anymore")
                break
            elif job[0] == "delayedaction":
                self.__logger.debug("Job {}", job)
                (_, action, actionname, namevar, repeat_text, value, current_condition, previous_condition,
                 previousstate_condition, state) = job
                self.__logger.info(
                    "Running delayed action: {0} based on current condition {1} or previous condition {2}",
                    actionname, current_condition, previous_condition)
                action.real_execute(state, actionname, namevar, repeat_text, value, False, current_condition)
            else:
                (_, item, caller, source, dest) = job
                item_id = item.property.path if item is not None else "(no item)"
                self.__logger.update_logfile()
                self.__logger.header("Update state of item {0}".format(self.__name))
                if caller:
                    self.__logger.debug("Update triggered by {0} (item={1} source={2} dest={3})", caller, item_id,
                                        source, dest)

                # Find out what initially caused the update to trigger if the caller is "Eval"
                orig_caller, orig_source, orig_item = StateEngineTools.get_original_caller(self.__logger, caller,
                                                                                           source, item)
                if orig_item is None:
                    orig_item = item
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
                self.__variables["item.suspend_time"] = self.__default_suspend_time \
                    if self.__using_default_suspendtime is True else _suspend_time
                self.__variables["item.suspend_remaining"] = -1
                self.__variables["item.instant_leaveaction"] = _default_instant_leaveaction_value \
                    if self.__using_default_instant_leaveaction is True else _instant_leaveaction
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
                    self.__logger.info("Previous Conditionset: {0} ('{1}')", self.__previousconditionset_internal_id,
                                       self.__previousconditionset_internal_name)
                else:
                    self.__logger.info("Previous Conditionset is empty")
                _previous_conditionset_id = _last_conditionset_id
                _previous_conditionset_name = _last_conditionset_name
                # get previous state
                if self.__previousstate_internal_id not in ['', None]:
                    self.__logger.info("Previous state: {0} ('{1}')", self.__previousstate_internal_id,
                                       self.__previousstate_internal_name)

                if self.__previousstate_conditionset_internal_id not in ['', None]:
                    self.__logger.info("Previous state's Conditionset: {0} ('{1}')",
                                       self.__previousstate_conditionset_internal_id,
                                       self.__previousstate_conditionset_internal_name)
                else:
                    self.__logger.info("Previous state's Conditionset is empty")

                # find new state
                _leaveactions_run = False

                if _instant_leaveaction >= 1 and caller != "Released_by Retrigger":
                    evaluated_instant_leaveaction = True
                else:
                    evaluated_instant_leaveaction = False
                for state in self.__states:
                    if not self.__ab_alive:
                        self.__logger.debug("StateEngine Plugin not running (anymore). Stop state evaluation.")
                        return
                    state.update_name(state.state_item)
                    _key_name = ['{}'.format(state.id), 'name']
                    self.update_webif(_key_name, state.name)

                    result = self.__update_check_can_enter(state, _instant_leaveaction)
                    _previousstate_conditionset_id = _last_conditionset_id
                    _previousstate_conditionset_name = _last_conditionset_name
                    _last_conditionset_id = self.__lastconditionset_internal_id
                    _last_conditionset_name = self.__lastconditionset_internal_name
                    if state is not None and result is True:
                        self.__conditionsets.update(
                            {state.state_item.property.path: [_last_conditionset_id, _last_conditionset_name]})
                    # New state is different from last state

                    if result is False and last_state == state and evaluated_instant_leaveaction is True:
                        self.__logger.info("Leaving {0} ('{1}'). Running actions immediately.", last_state.id,
                                           last_state.name)
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
                            self.__logger.info(text, last_state.id, last_state.name, _last_conditionset_id,
                                               _last_conditionset_name)
                        last_state.run_stay(self.__repeat_actions.get())
                    if self.update_lock.locked():
                        self.update_lock.release()
                    self.__logger.debug("State evaluation finished")
                    self.__logger.info("State evaluation queue empty.")
                    self.__handle_releasedby(new_state, last_state, _instant_leaveaction)

                    return

                if new_state.is_copy_for:
                    new_state.has_released = new_state.is_copy_for
                    last_state.was_releasedby = new_state
                    self.__logger.info(
                        "State is a copy and therefore just releasing {}. Skipping state actions, running leave actions "
                        "of last state, then retriggering.", new_state.is_copy_for.id)
                    if last_state is not None and self.__ab_alive:
                        #self.lastconditionset_set(_original_conditionset_id, _original_conditionset_name)
                        self.__logger.info("Leaving {0} ('{1}'). Condition set was: {2}.",
                                           last_state.id, last_state.name, _original_conditionset_id)
                        self.__update_check_can_enter(last_state, _instant_leaveaction, False)
                        last_state.run_leave(self.__repeat_actions.get())
                        _key_leave = ['{}'.format(last_state.id), 'leave']
                        _key_stay = ['{}'.format(last_state.id), 'stay']
                        _key_enter = ['{}'.format(last_state.id), 'enter']

                        self.update_webif(_key_leave, True)
                        self.update_webif(_key_stay, False)
                        self.update_webif(_key_enter, False)
                    self.__handle_releasedby(new_state, last_state, _instant_leaveaction)

                    if self.update_lock.locked():
                        self.update_lock.release()
                    self.update_state(self.__item, "Released_by Retrigger", state.id)
                    return

                _last_conditionset_id = self.__lastconditionset_internal_id
                _last_conditionset_name = self.__lastconditionset_internal_name

                if new_state.conditions.count() == 0:
                    self.lastconditionset_set('', '')
                    _last_conditionset_id = ''
                    _last_conditionset_name = ''
                self.previousconditionset_set(_previous_conditionset_id, _previous_conditionset_name)
                # endblock
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
                    if caller == "Released_by Retrigger":
                        self.__logger.info("Leave actions already run during state release.")
                    elif last_state is not None and _leaveactions_run is True:
                        self.__logger.info("Left {0} ('{1}')", last_state.id, last_state.name)
                        if last_state.leaveactions.count() > 0:
                            self.__logger.info(
                                "Maybe some actions were performed directly after leave - see log above.")
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
                    self.previousstate_conditionset_set(_previousstate_conditionset_id,
                                                        _previousstate_conditionset_name)
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
                all_released_by = self.__handle_releasedby(new_state, last_state, _instant_leaveaction)

        self.__logger.info("State evaluation queue empty.")
        if new_state:
            self.__logger.develop("States {}, Current state released by {}", self.__states, all_released_by.get(new_state))

        if self.update_lock.locked():
            self.update_lock.release()

    def __update_release_item_value(self, value, state):
        if state is None:
            return value
        if isinstance(value, Item):
            value = value.property.value
        if isinstance(value, str) and value.startswith(".."):
            _returnvalue_issue = "Relative state {} defined by value in se_released_by attribute of " \
                                 "state {} has to be defined with one '.' only.".format(value, state.id)
            self.__logger.warning("{} Changing it accordingly.", _returnvalue_issue)
            value = re.sub(r'\.+', '.', value)
        if isinstance(value, list):
            new_value = []
            for v in value:
                if isinstance(v, str) and v.startswith("."):
                    v = "{}{}".format(state.id.rsplit(".", 1)[0], v)
                new_value.append(v)
            value = new_value
        if isinstance(value, str) and value.startswith("."):
            value = "{}{}".format(state.id.rsplit(".", 1)[0], value)
        return value

    def __update_can_release(self, can_release, new_state=None):
        state_dict = {state.id: state for state in self.__states}
        for entry, release_list in can_release.items():  # Iterate through the dictionary items
            entry = self.__update_release_item_value(entry, new_state)
            entry = entry if isinstance(entry, list) else [entry]
            for en in entry:
                if en in state_dict:
                    state = state_dict.get(en)
                    if state.is_copy_for:
                        self.__logger.develop("State {} is a copy.", state.id)
                    can_release_list = []
                    _stateindex = list(state_dict.keys()).index(state.id)
                    for e in release_list:
                        _valueindex = list(state_dict.keys()).index(e) if e in state_dict else -1
                        self.__logger.develop("Testing entry in canrelease {}, state {} stateindex {}, "\
                                              "valueindex {}", e, state.id, _stateindex, _valueindex)
                        if e == state.id:
                            self.__logger.info("Value in se_released_by must not be identical to state. Ignoring {}", e)
                        elif _stateindex < _valueindex and not state.is_copy_for:
                            self.__logger.info("Value {} in se_released_by must have lower priority "\
                                               "than state. Ignoring {}", state.id, e)
                        else:
                            can_release_list.append(e)
                            self.__logger.develop("Value added to possible can release states {}", e)

                    state.update_can_release_internal(can_release_list)
                    self.__logger.develop("Updated 'can_release' property of state {} to {}", state.id, state.can_release)

                else:
                    self.__logger.info("Entry {} in se_released_by of state(s) is not a valid state.", entry)

    def __handle_releasedby(self, new_state, last_state, instant_leaveaction):
        def update_can_release_list():
            for e in _returnvalue:
                e = self.__update_release_item_value(e, new_state)
                e = e if isinstance(e, list) else [e]
                for entry in e:
                    if entry and state.id not in can_release.setdefault(entry, [state.id]):
                        can_release[entry].append(state.id)

        self.__logger.info("".ljust(80, "_"))
        self.__logger.info("Handling released_by attributes")
        can_release = {}
        all_released_by = {}
        skip_copy = True
        for state in self.__states:
            if state.is_copy_for and skip_copy:
                self.__logger.develop("Skipping {} because it is a copy", state.id)
                skip_copy = False
                continue
            _returnvalue = state.releasedby
            _returnvalue = _returnvalue if isinstance(_returnvalue, list) else [_returnvalue]
            _returnvalue = StateEngineTools.flatten_list(_returnvalue)
            all_released_by.update({state: _returnvalue})

            if _returnvalue not in [[], None, [None]]:
                update_can_release_list()

        self.__update_can_release(can_release, new_state)

        if last_state and new_state and last_state != new_state and last_state.is_copy_for:
            self.__states.remove(last_state)
            last_state.is_copy_for = None
            self.__logger.debug("Removed state copy {} because it was just left.", last_state.id)
        elif last_state and new_state and last_state != new_state and new_state.is_copy_for:
            self.__states.remove(new_state)
            new_state.is_copy_for = None
            new_state.has_released = last_state
            self.__logger.debug("Removed state copy {} because it has just released {}.", new_state.id, last_state.id)
        if last_state and new_state and last_state != new_state:
            new_states = self.__states.copy()
            for entry in new_states:
                if entry.is_copy_for and last_state == entry.is_copy_for:
                    self.__states.remove(entry)
                    entry.is_copy_for = None
                    if entry != new_state:
                        self.__logger.debug("Removed state copy {} (is copy for {}) because "
                                            "state was released by other possible state.", entry.id, last_state.id)
                    else:
                        new_state.has_released = last_state
                        self.__logger.debug("Removed state copy {} because "
                                            "it has already released state {}.", entry.id, last_state.id)

        if new_state:
            new_state.was_releasedby = None
            _can_release_list = []
            releasedby = all_released_by.get(new_state)
            if releasedby not in [[], None, [None]]:
                self.__logger.develop("releasedby {}", releasedby)
                state_dict = {item.id: item for item in self.__states}
                _stateindex = list(state_dict.keys()).index(new_state.id)
                releasedby = releasedby if isinstance(releasedby, list) else [releasedby]
                _checkedentries = []
                for i, entry in enumerate(releasedby):
                    entry = self.__update_release_item_value(entry, new_state)
                    entry = entry if isinstance(entry, list) else [entry]
                    for e in entry:
                        if e in _checkedentries:
                            self.__logger.develop("Entry {} defined by {} already checked, skipping", e, releasedby[i])
                            continue
                        cond_copy_for = e in state_dict.keys()
                        if cond_copy_for and new_state == state_dict.get(e).is_copy_for:
                            if e not in _can_release_list:
                                _can_release_list.append(e)
                            self.__logger.develop("Entry {} defined by {} is a copy, skipping", e, releasedby[i])
                            continue
                        _entryindex = list(state_dict.keys()).index(e) if e in state_dict else -1
                        self.__logger.develop("Testing if entry {} should become a state copy. "\
                                              "stateindex {}, entryindex {}", e, _stateindex, _entryindex)
                        if e == new_state.id:
                            self.__logger.warning("Value in se_released_by must no be identical to state. Ignoring {}",
                                                  e)
                        elif _entryindex == -1:
                            self.__logger.warning("State in se_released_by does not exist. Ignoring {}", e)
                        elif _stateindex > _entryindex:
                            self.__logger.warning("Value in se_released_by must have lower priority than state. Ignoring {}",
                                                  e)
                        elif e in state_dict.keys():
                            relevant_state = state_dict.get(e)
                            index = self.__states.index(new_state)
                            cond_index = relevant_state in self.__states and self.__states.index(relevant_state) != index - 1
                            if cond_index or relevant_state not in self.__states:
                                current_log_level = self.__log_level.get()
                                if current_log_level < 3:
                                    self.__logger.log_level_as_num = 0
                                can_enter = self.__update_check_can_enter(relevant_state, instant_leaveaction)
                                self.__logger.log_level_as_num = current_log_level
                                if relevant_state == last_state:
                                    self.__logger.debug("Possible release state {} = last state {}, "\
                                                        "not copying", relevant_state.id, last_state.id)
                                elif can_enter:
                                    self.__logger.debug("Relevant state {} could enter, not copying", relevant_state.id)
                                elif not can_enter:
                                    relevant_state.is_copy_for = new_state
                                    self.__states.insert(index, relevant_state)
                                    if relevant_state.id not in _can_release_list:
                                        _can_release_list.append(relevant_state.id)
                                    self.__logger.debug("Inserted copy of state {}", relevant_state.id)
                        _checkedentries.append(e)
                self.__logger.info("State {} can currently get released by: {}", new_state.id, _can_release_list)
                self.__release_info = {new_state.id: _can_release_list}
                _key_releasedby = ['{}'.format(new_state.id), 'releasedby']
                self.update_webif(_key_releasedby, _can_release_list)

        self.__logger.info("".ljust(80, "_"))
        return all_released_by

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

    def update_action_status(self, action_status):
        def combine_dicts(dict1, dict2):
            combined_dict = dict1.copy()

            for key, value in dict2.items():
                if key in combined_dict:
                    for k, v in combined_dict.items():
                        v['issueorigin'].extend(
                            [item for item in v['issueorigin'] if item not in combined_dict[k]['issueorigin']])
                        v['issue'].extend([item for item in v['issue'] if item not in combined_dict[k]['issue']])

                else:
                    combined_dict[key] = value

            return combined_dict

        combined_dict = combine_dicts(action_status, self.__action_status)
        self.__action_status = combined_dict

    def update_issues(self, issue_type, issues):
        def combine_dicts(dict1, dict2):
            combined_dict = dict1.copy()

            for key, value in dict2.items():
                if key in combined_dict and combined_dict[key].get('issueorigin'):
                    combined_dict[key]['issueorigin'].extend(value['issueorigin'])
                else:
                    combined_dict[key] = value

            return combined_dict

        if issue_type == "state":
            combined_dict = combine_dicts(issues, self.__state_issues)
            self.__state_issues = combined_dict
        elif issue_type == "config":
            combined_dict = combine_dicts(issues, self.__config_issues)
            self.__config_issues = combined_dict
        elif issue_type == "struct":
            combined_dict = combine_dicts(issues, self.__struct_issues)
            self.__struct_issues = combined_dict

    def update_attributes(self, unused_attributes, used_attributes):
        combined_unused_dict = unused_attributes.copy()  # Create a copy of dict1
        for key, value in self.__unused_attributes.items():
            if key in combined_unused_dict:
                if unused_attributes.get(key):
                    existing_issue = unused_attributes[key].get('issueorigin')
                else:
                    existing_issue = None
                combined_unused_dict[key].update(value)  # Update nested dictionaries
                if existing_issue:
                    try:
                        combined_dict = defaultdict(set)
                        for entry in existing_issue + combined_unused_dict[key].get('issueorigin'):
                            combined_dict[entry['state']].add(entry['conditionset'])

                        combined_entries = [{'state': state, 'conditionset': ', '.join(conditionsets)} for
                                            state, conditionsets in combined_dict.items()]
                        combined_unused_dict[key]['issueorigin'] = combined_entries
                    except Exception as ex:
                        pass

        self.__unused_attributes = combined_unused_dict

        combined_dict = self.__used_attributes.copy()  # Create a copy of dict1
        for key, value in used_attributes.items():
            if key in combined_dict:
                combined_dict[key].update(value)  # Update nested dictionaries
            else:
                combined_dict[key] = value  # Add new key-value pairs
        self.__used_attributes = combined_dict

    def __log_issues(self, issue_type):
        def list_issues(v):
            _issuelist = StateEngineTools.flatten_list(v.get('issue'))
            if isinstance(_issuelist, list) and len(_issuelist) > 1:
                self.__logger.info("has the following issues:")
                self.__logger.increase_indent()
                for e in _issuelist:
                    self.__logger.info("- {}", e)
                self.__logger.decrease_indent()
            elif isinstance(_issuelist, list) and len(_issuelist) == 1:
                self.__logger.info("has the following issue: {}", _issuelist[0])
            else:
                self.__logger.info("has the following issue: {}", _issuelist)

        if issue_type == 'actions':
            to_check = self.__action_status.items()
            warn = ', '.join(key for key in self.__action_status.keys())
        elif issue_type == 'structs':
            to_check = self.__struct_issues.items()
            warn = ', '.join(key for key in self.__struct_issues.keys())
        elif issue_type == 'states':
            to_check = self.__state_issues.items()
            warn = ', '.join(key for key in self.__state_issues.keys())
        elif issue_type == 'config entries':
            to_check = self.__config_issues.items()
            warn = ', '.join(key for key in self.__config_issues.keys())
        else:
            to_check = self.__unused_attributes.items()
            warn_unused = ', '.join(key for key, value in self.__unused_attributes.items() if 'issue' not in value)
            warn_issues = ', '.join(key for key, value in self.__unused_attributes.items() if 'issue' in value)
        self.__logger.info("")
        if issue_type == 'attributes':
            if warn_unused:
                self.__logger.info("These attributes are not used: {}. Please check extended "
                                   "log file for details.", warn_unused)
            if warn_issues:
                self.__logger.warning("There are attribute issues: {}. Please check extended "
                                      "log file for details.", warn_issues)
        else:
            self.__logger.warning("There are {} issues: {}. Please check extended "
                                  "log file for details.", issue_type, warn)
        self.__logger.info("")
        self.__logger.info("The following {} have issues:", issue_type)
        self.__logger.increase_indent()
        for entry, value in to_check:
            if 'issue' in value:
                origin_text = ''
                origin_list = value.get('issueorigin') or []
                if issue_type == 'states':
                    self.__logger.info("State {} is ignored because", entry)
                elif issue_type == 'config entries':
                    if value.get('attribute'):
                        self.__logger.info("Attribute {}", value.get('attribute'))
                        self.__logger.increase_indent()
                        self.__logger.info("defined in state {}", entry)
                        self.__logger.decrease_indent()
                        list_issues(value)
                    else:
                        self.__logger.info("Attribute {} has an issue: {}", entry, value.get('issue'))
                    self.__logger.info("")
                    continue
                elif issue_type == 'structs':
                    self.__logger.info("Struct {} has an issue: {}", entry, value.get('issue'))
                    self.__logger.info("")
                    continue
                else:
                    additional = " used in" if origin_list else ""
                    self.__logger.info("Definition {}{}", entry, additional)
                self.__logger.increase_indent()
                for origin in origin_list:
                    if issue_type == 'actions':
                        origin_text = 'state {}, action {}, on_{}'.format(origin.get('state'), origin.get('action'),
                                                                          origin.get('type'))
                    elif issue_type == 'states':
                        if origin.get('condition') == 'GeneralError' and len(origin_list) == 1:
                            origin_text = 'there was a general error. The state'
                        elif origin.get('condition') == 'ValueError' and len(origin_list) == 1:
                            origin_text = 'there was a value error. The state'
                        else:
                            if origin.get('condition') in ['GeneralError', 'ValueError']:
                                continue
                            origin_text = 'condition {} defined in conditionset {}'.format(origin.get('condition'),
                                                                                           origin.get('conditionset'))
                    else:
                        origin_text = 'state {}, conditionset {}'.format(origin.get('state'),
                                                                         origin.get('conditionset'))
                    self.__logger.info("{}", origin_text)
                self.__logger.decrease_indent()
                list_issues(value)
                self.__logger.info("")
        for entry, value in to_check:
            if 'issue' not in value:
                text = "Definition {} not used in any action or condition.".format(entry)
                self.__logger.info("{}", text)
        self.__logger.decrease_indent()

    def __reorder_states(self, init=True):
        _reordered_states = []
        self.__logger.info("".ljust(80, "_"))
        self.__logger.info("Recalculating state order. Current order: {}", self.__states)
        _copied_states = {}
        _add_order = 0
        _changed_orders = []
        for i, state in enumerate(self.__states, 1):
            try:
                _original_order = state.order
                _issue = None
                if state.is_copy_for and state not in _copied_states:
                    _order = i - 0.01
                    _copied_states[state] = _order
                    self.__logger.develop("State {} is copy, set to {}", state, _order)
                else:
                    _issue = state.update_order()
                    _order = state.order
                    if _order != _original_order:
                        _changed_orders.append(_order)
                        _add_order -= 1
                        self.__logger.develop("State {} changed order: {},"
                                              " i: {} add order: {}.",
                                              state, _order, i, _add_order)
                    elif any(_order < value for value in _changed_orders):
                        _order = i + _add_order
                        _issue = state.update_order(_order)
                        self.__logger.develop("State {} smaller, order: {},"
                                              " i: {} add order: {}.",
                                              state, _order, i, _add_order)
                    elif any(_order == value for value in _changed_orders):
                        _order = i + _add_order
                        _issue = state.update_order(_order)
                        self.__logger.develop("State {} equal, order: {},"
                                              " i: {} add order: {}.",
                                              state, _order, i, _add_order)
                        _add_order += 1
                    else:
                        self.__logger.develop("State {} order: {},"
                                              " i: {} add order: {}.",
                                              state, _order, i, _add_order)
                if _issue not in [[], None, [None]]:
                    self.__config_issues.update({state.id: {'issue': _issue, 'attribute': 'se_stateorder'}})
                    self.__logger.warning("Issue while getting state order: {},"
                                          " using original order {}", _issue, _original_order)
                    _order = _original_order
                    state.update_order(_original_order)
                elif _copied_states.get(state) and _copied_states.get(state) > _order:
                    _reordered_states.remove((_copied_states.get(state), state))
                    state.is_copy_for = None
                    _add_order -= 1
                elif state not in _copied_states and init is False:
                    _order += _add_order
                _reordered_states.append((_order, state))
            except Exception as ex:
                self.__logger.error("Problem setting order of state {0}: {1}", state.id, ex)
                self.__config_issues.update({state.id: {'issue': ex, 'attribute': 'se_stateorder'}})
        self.__states = []
        for order, state in sorted(_reordered_states, key=lambda x: x[0]):
            self.__states.append(state)
        if init is False:
            _reorder_webif = OrderedDict()
            _copied_states = []
            for state in self.__states:
                if state.is_copy_for and state not in _copied_states:
                    _copied_states.append(state)
                else:
                    _reorder_webif[state.id] = self.__webif_infos[state.id]
            self.__webif_infos = _reorder_webif
        self.__logger.info("Recalculated state order. New order: {}", self.__states)
        self.__logger.info("".ljust(80, "_"))

    def __initialize_state(self, item_state, _statecount):
        try:
            _state = StateEngineState.SeState(self, item_state)
            _issue = _state.update_order(_statecount)
            if _issue:
                self.__config_issues.update({item_state.property.path:
                                            {'issue': _issue, 'attribute': 'se_stateorder'}})
                self.__logger.error("Issue with state {0} while setting order: {1}",
                                    item_state.property.path, _issue)
            self.__states.append(_state)
            self.__state_ids.update({item_state.property.path: _state})
            self.__logger.info("Appended state {}", item_state.property.path)
            self.__unused_attributes = _state.unused_attributes.copy()
            filtered_dict = {key: value for key, value in self.__unused_attributes.items() if
                             key not in _state.used_attributes}
            self.__unused_attributes = filtered_dict
            return _statecount + 1
        except ValueError as ex:
            self.update_issues('state', {item_state.property.path: {'issue': ex, 'issueorigin':
                [{'conditionset': 'None', 'condition': 'ValueError'}]}})
            self.__logger.error("Ignoring state {0} because ValueError: {1}",
                                item_state.property.path, ex)
            return _statecount
        except Exception as ex:
            self.update_issues('state', {item_state.property.path: {'issue': ex, 'issueorigin':
                [{'conditionset': 'None', 'condition': 'GeneralError'}]}})
            self.__logger.error("Ignoring state {0} because: {1}",
                                item_state.property.path, ex)
            return _statecount

    def __finish_states(self):
        # initialize states
        if len(self.__states) == 0:
            raise ValueError("{0}: No states defined!".format(self.id))

    # Find the state, matching the current conditions and perform the actions of this state
    # caller: Caller that triggered the update
    # noinspection PyCallingNonCallable,PyUnusedLocal
    def update_state(self, item, caller=None, source=None, dest=None):
        if not self.__startup_delay_over:
            self.__logger.debug("Startup delay not over yet. Skipping state evaluation")
            return
        self.__queue.put(["stateevaluation", item, caller, source, dest])
        if not self.update_lock.locked():
            self.__logger.debug("Run queue to update state. Item: {}, caller: {}, source: {}", item.property.path, caller, source)
            self.run_queue()

    # check if state can be entered after setting state-specific variables
    # state: state to check
    def __update_check_can_enter(self, state, instant_leaveaction, refill=True):
        try:
            wasreleasedby = state.was_releasedby.id
        except:
            wasreleasedby = state.was_releasedby
        try:
            iscopyfor = state.is_copy_for.id
        except:
            iscopyfor = state.is_copy_for
        try:
            hasreleased = state.has_released.id
        except:
            hasreleased = state.has_released
        try:
            canrelease = state.can_release.id
        except:
            canrelease = state.can_release
        try:
            self.__variables["release.can_release"] = canrelease
            self.__variables["release.can_be_released_by"] = state.releasedby
            self.__variables["release.has_released"] = hasreleased
            self.__variables["release.was_released_by"] = wasreleasedby
            self.__variables["release.will_release"] = iscopyfor
            self.__variables["previous.state_id"] = self.__previousstate_internal_id
            self.__variables["previous.state_name"] = self.__previousstate_internal_name
            self.__variables["item.instant_leaveaction"] = instant_leaveaction
            self.__variables["current.state_id"] = state.id
            self.__variables["current.state_name"] = state.name
            self.__variables["current.conditionset_id"] = self.__lastconditionset_internal_id
            self.__variables["current.conditionset_name"] = self.__lastconditionset_internal_name
            self.__variables["previous.conditionset_id"] = self.__previousconditionset_internal_id
            self.__variables["previous.conditionset_name"] = self.__previousconditionset_internal_name
            self.__variables["previous.state_conditionset_id"] = self.__previousstate_conditionset_internal_id
            self.__variables["previous.state_conditionset_name"] = self.__previousstate_conditionset_internal_name
            self.__logger.develop("Current variables: {}", self.__variables)
            if refill:
                state.refill()
                return state.can_enter()
        except Exception as ex:
            self.__logger.warning("Problem with currentstate {0}. Error: {1}", state.id, ex)
            # The variables where originally reset in a finally: statement. No idea why... ;)
            self.__variables["release.can_release"] = ""
            self.__variables["release.can_be_released_by"] = ""
            self.__variables["release.has_released"] = ""
            self.__variables["release.was_released_by"] = ""
            self.__variables["release.will_release"] = ""
            self.__variables["item.instant_leaveaction"] = ""
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
            self.__laststate_item_id(self.__laststate_internal_id, StateEngineDefaults.plugin_identification,
                                     "StateEvaluation")

        self.__laststate_internal_name = '' if new_state is None else new_state.text
        if self.__laststate_item_name is not None:
            # noinspection PyCallingNonCallable
            self.__laststate_item_name(self.__laststate_internal_name, StateEngineDefaults.plugin_identification,
                                       "StateEvaluation")
        self.__logger.develop("Setting last state to {0} ('{1}')", self.__laststate_internal_id,
                              self.__laststate_internal_name)

    # get last state object based on laststate_id
    # returns: SeState instance of last state or "None" if no last state could be found
    def __laststate_get(self):
        for state in self.__states:
            if state.id == self.__laststate_internal_id:
                return state
        return None

    # return id of last conditionset
    def __lastconditionset_get_id(self):
        _lastconditionset_item_id, _ = self.return_item_by_attribute("se_lastconditionset_item_id")
        _lastconditionset_item_id = "" if _lastconditionset_item_id is None else _lastconditionset_item_id.property.value
        return _lastconditionset_item_id

    # return name of last conditionset
    def __lastconditionset_get_name(self):
        _lastconditionset_item_name, _ = self.return_item_by_attribute("se_lastconditionset_item_name")
        _lastconditionset_item_name = "" if _lastconditionset_item_name is None else _lastconditionset_item_name.property.value
        return _lastconditionset_item_name

    def lastconditionset_set(self, new_id, new_name):
        self.__lastconditionset_internal_id = new_id
        if self.__lastconditionset_item_id is not None:
            # noinspection PyCallingNonCallable
            self.__lastconditionset_item_id(self.__lastconditionset_internal_id,
                                            StateEngineDefaults.plugin_identification, "StateEvaluation")

        self.__lastconditionset_internal_name = new_name
        if self.__lastconditionset_item_name is not None:
            # noinspection PyCallingNonCallable
            self.__lastconditionset_item_name(self.__lastconditionset_internal_name,
                                              StateEngineDefaults.plugin_identification, "StateEvaluation")
        self.__logger.develop("Setting current Conditionset to {0} ('{1}')", self.__lastconditionset_internal_id,
                              self.__lastconditionset_internal_name)

    # endregion

    # region Previousstate *************************************************************************************************
    # Set previousstate
    # last_state: last state to be used as previousstate
    def __previousstate_set(self, last_state):
        self.__previousstate_internal_id = 'None' if last_state is None else last_state.id
        if self.__previousstate_item_id is not None:
            # noinspection PyCallingNonCallable
            self.__previousstate_item_id(self.__previousstate_internal_id, StateEngineDefaults.plugin_identification,
                                         "StateEvaluation")

        self.__previousstate_internal_name = 'None' if last_state is None else last_state.text
        if self.__previousstate_item_name is not None:
            # noinspection PyCallingNonCallable
            self.__previousstate_item_name(self.__previousstate_internal_name,
                                           StateEngineDefaults.plugin_identification, "StateEvaluation")

    # get previous state object based on previousstate_id
    # returns: SeState instance of last state or "None" if no last state could be found
    def __previousstate_get(self):
        for state in self.__states:
            if state.id == self.__previousstate_internal_id:
                return state
        return None

    # return id of last conditionset
    def __previousconditionset_get_id(self):
        _previousconditionset_item_id, _ = self.return_item_by_attribute("se_previousconditionset_item_id")
        _previousconditionset_item_id = "" if _previousconditionset_item_id is None else _previousconditionset_item_id.property.value
        return _previousconditionset_item_id

    # return name of last conditionset
    def __previousconditionset_get_name(self):
        _previousconditionset_item_name, _ = self.return_item_by_attribute("se_previousconditionset_item_name")
        _previousconditionset_item_name = "" if _previousconditionset_item_name is None else _previousconditionset_item_name.property.value
        return _previousconditionset_item_name

    # return id of conditionset of last state
    def __previousstate_conditionset_get_id(self):
        _previousstate_conditionset_item_id, _ = self.return_item_by_attribute("se_previousstate_conditionset_item_id")
        _previousstate_conditionset_item_id = "" if _previousstate_conditionset_item_id is None else _previousstate_conditionset_item_id.property.value
        return _previousstate_conditionset_item_id

    # return name of conditionset of last state
    def __previousstate_conditionset_get_name(self):
        _previousstate_conditionset_item_name, _ = self.return_item_by_attribute("se_previousstate_conditionset_item_name")
        _previousstate_conditionset_item_name = "" if _previousstate_conditionset_item_name is None else _previousstate_conditionset_item_name.property.value
        return _previousstate_conditionset_item_name

    def previousconditionset_set(self, last_id, last_name):
        self.__previousconditionset_internal_id = last_id
        if self.__previousconditionset_item_id is not None:
            # noinspection PyCallingNonCallable
            self.__previousconditionset_item_id(self.__previousconditionset_internal_id,
                                                StateEngineDefaults.plugin_identification, "StateEvaluation")

        self.__previousconditionset_internal_name = last_name
        if self.__previousconditionset_item_name is not None:
            # noinspection PyCallingNonCallable
            self.__previousconditionset_item_name(self.__previousconditionset_internal_name,
                                                  StateEngineDefaults.plugin_identification, "StateEvaluation")
        self.__logger.develop("Setting previous Conditionset to {0} ('{1}')", self.__previousconditionset_internal_id,
                              self.__previousconditionset_internal_name)

    def previousstate_conditionset_set(self, last_id, last_name):
        self.__previousstate_conditionset_internal_id = last_id
        if self.__previousstate_conditionset_item_id is not None:
            # noinspection PyCallingNonCallable
            self.__previousstate_conditionset_item_id(self.__previousstate_conditionset_internal_id,
                                                      StateEngineDefaults.plugin_identification, "StateEvaluation")

        self.__previousstate_conditionset_internal_name = last_name
        if self.__previousstate_conditionset_item_name is not None:
            # noinspection PyCallingNonCallable
            self.__previousstate_conditionset_item_name(self.__previousstate_conditionset_internal_name,
                                                        StateEngineDefaults.plugin_identification, "StateEvaluation")
        self.__logger.develop("Setting Conditionset of previous state to {0} ('{1}')",
                              self.__previousstate_conditionset_internal_id,
                              self.__previousstate_conditionset_internal_name)

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

    def __init_releasedby(self):
        def process_returnvalue(value):
            self.__logger.debug("Testing value {}", value)
            _returnvalue_issue = None
            if value is None:
                return _returnvalue_issue
            try:
                original_value = value
                value = self.__update_release_item_value(_evaluated_returnvalue[i], state)
                value = value if isinstance(value, list) else [value]
                v_list = []
                for v in value:
                    _stateindex = list(state_dict.keys()).index(state.id)
                    _valueindex = list(state_dict.keys()).index(v) if v in state_dict else -1
                    if _returntype[i] == 'value' and _valueindex == - 1:
                        _returnvalue_issue = "State {} defined by value in se_released_by attribute of state {} " \
                                             "does not exist.".format(v, state.id)
                        self.__logger.warning("{} Removing it.", _returnvalue_issue)
                    elif _returntype[i] == 'value' and _valueindex < _stateindex:
                        _returnvalue_issue = "State {} defined by value in se_released_by attribute of state {} " \
                                             "must be lower priority than actual state.".format(v, state.id)
                        self.__logger.warning("{} Removing it.", _returnvalue_issue)
                    elif _returntype[i] == 'value' and v == state.id:
                        _returnvalue_issue = "State {} defined by value in se_released_by attribute of state {} " \
                                             "must not be identical.".format(v, state.id)
                        self.__logger.warning("{} Removing it.", _returnvalue_issue)
                    elif _returntype[i] == 'item':
                        if v == state.id:
                            _returnvalue_issue = "State {} defined by {} in se_released_by attribute of state {} " \
                                                 "must not be identical.".format(v, _returnvalue[i], state.id)
                        elif _valueindex == - 1: #not any(value == test.id for test in self.__states):
                            _returnvalue_issue = "State {} defined by {} in se_released_by attribute of state {} " \
                                                 "does currently not exist.".format(v, _returnvalue[i], state.id)
                        elif _valueindex < _stateindex:
                            _returnvalue_issue = "State {} defined by value in se_released_by attribute of state {} " \
                                                 "must be lower priority than actual state.".format(v, state.id)
                        if _returnvalue_issue:
                            self.__logger.warning("{} Make sure to change item value.", _returnvalue_issue)
                        if original_value not in _convertedlist:
                            _convertedlist.append(original_value)
                            self.__logger.develop("Adding {} from item as releasedby for state {}", original_value,
                                                  state.id)
                        v_list.append(v)
                        _converted_typelist.append(_returntype[i])

                    elif _returntype[i] == 'regex':
                        matches = [test.id for test in self.__states if _evaluated_returnvalue[i].match(test.id)]
                        self.__logger.develop("matches {}", matches)
                        _returnvalue_issue_list = []
                        for match in matches:
                            _valueindex = list(state_dict.keys()).index(match) if match in state_dict else -1
                            if _valueindex == _stateindex:
                                _returnvalue_issue = "State {} defined by {} in se_released_by attribute of state {} " \
                                                     "must not be identical.".format(match, _returnvalue[i], state.id)
                                self.__logger.warning("{} Removing it.", _returnvalue_issue)
                                if _returnvalue_issue not in _returnvalue_issue_list:
                                    _returnvalue_issue_list.append(_returnvalue_issue)
                            elif _valueindex < _stateindex:
                                _returnvalue_issue = "State {} defined by {} in se_released_by " \
                                                     "attribute of state {} must be lower priority "\
                                                     "than actual state.".format(match, _returnvalue[i], state.id)
                                self.__logger.warning("{} Removing it.", _returnvalue_issue)
                                if _returnvalue_issue not in _returnvalue_issue_list:
                                    _returnvalue_issue_list.append(_returnvalue_issue)
                            else:
                                if match not in _convertedlist:
                                    _convertedlist.append(match)
                                    self.__logger.develop("Adding {} from regex as releasedby for state {}", match,
                                                          state.id)
                                v_list.append(value)
                                _converted_typelist.append(_returntype[i])

                            _returnvalue_issue = _returnvalue_issue_list
                        if not matches:
                            _returnvalue_issue = "No states match regex {} defined in "\
                                                 "se_released_by attribute of state {}.".format(value, state.id)
                            self.__logger.warning("{} Removing it.", _returnvalue_issue)
                    elif _returntype[i] == 'eval':
                        if v == state.id:
                            _returnvalue_issue = "State {} defined by {} in se_released_by attribute of state {} " \
                                                 "must not be identical.".format(v, _returnvalue[i], state.id)
                            self.__logger.warning("{} Make sure eval will result in a useful value later on.",
                                                  _returnvalue_issue)
                        elif _valueindex < _stateindex:
                            _returnvalue_issue = "State {} defined by value in se_released_by attribute of state {} " \
                                                 "must be lower priority than actual state.".format(v, state.id)
                            self.__logger.warning("{} Make sure eval will result in a useful value later on.",
                                                  _returnvalue_issue)
                        elif v is None:
                            _returnvalue_issue = "Eval defined by {} in se_released_by attribute of state {} " \
                                                 "does currently return None.".format(_returnvalue[i], state.id)
                            self.__logger.warning("{} Make sure eval will result in a useful value later on.",
                                                  _returnvalue_issue)
                        if _returnvalue[i] not in _convertedlist:
                            _convertedlist.append(_returnvalue[i])
                            self.__logger.develop("Adding {} from eval as releasedby for state {}", _returnvalue[i],
                                                  state.id)
                        v_list.append(v)
                        _converted_typelist.append(_returntype[i])

                    elif v and v == state.id:
                        _returnvalue_issue = "State {} defined by {} in se_released_by attribute of state {} " \
                                             "must not be identical.".format(v, _returnvalue[i], state.id)
                        self.__logger.warning("{} Removing it.", _returnvalue_issue)
                    elif v and v not in _convertedlist:
                        if value not in _convertedlist:
                            _convertedlist.append(value)
                            self.__logger.develop("Adding {} as releasedby for state {}", value, state.id)
                        v_list.append(v)
                        _converted_typelist.append(_returntype[i])
                    else:
                        _returnvalue_issue = "Found invalid definition in se_released_by attribute "\
                                             "of state {}, original {}.".format(state.id, v, original_value)
                        self.__logger.warning("{} Removing it.", _returnvalue_issue)
                _converted_evaluatedlist.append(v_list)
            except Exception as ex:
                _returnvalue_issue = "Issue with {} for released_by of state {} check: {}".format(value, state.id, ex)
                self.__logger.error(_returnvalue_issue)
            return _returnvalue_issue

        def update_can_release_list():
            for i, value in enumerate(_convertedlist):
                if _converted_typelist[i] == 'item':
                    value = self.__update_release_item_value(_converted_evaluatedlist[i], state)
                elif _converted_typelist[i] == 'eval':
                    value = _converted_evaluatedlist[i]
                value = value if isinstance(value, list) else [value]
                for v in value:
                    if v and can_release.get(v) and state.id not in can_release.get(v):
                        can_release[v].append(state.id)
                    elif v:
                        can_release.update({v: [state.id]})

        self.__logger.info("".ljust(80, "_"))
        self.__logger.info("Initializing released_by attributes")
        can_release = {}
        state_dict = {state.id: state for state in self.__states}
        for state in self.__states:
            _issuelist = []
            _returnvalue, _returntype, _issue = state.update_releasedby_internal()
            _returnvalue = copy.copy(_returnvalue)
            _issuelist.append(_issue)
            if _returnvalue:
                _convertedlist = []
                _converted_evaluatedlist = []
                _converted_typelist = []
                _returnvalue = _returnvalue if isinstance(_returnvalue, list) else [_returnvalue]
                _evaluated_returnvalue = state.releasedby
                _evaluated_returnvalue = _evaluated_returnvalue if isinstance(_evaluated_returnvalue, list) else [_evaluated_returnvalue]
                for i, entry in enumerate(_returnvalue):
                    _issue = process_returnvalue(entry)
                    if _issue is not None and _issue not in _issuelist:
                        _issuelist.append(_issue)
                update_can_release_list()
                _issuelist = StateEngineTools.flatten_list(_issuelist)
                _issuelist = [issue for issue in _issuelist if issue is not None and issue != []]
                _issuelist = None if len(_issuelist) == 0 else _issuelist[0] if len(_issuelist) == 1 else _issuelist
                self.__config_issues.update({state.id: {'issue': _issuelist, 'attribute': 'se_released_by'}})
                state.update_releasedby_internal(_convertedlist)
                self.__update_can_release(can_release, state)

        self.__logger.info("".ljust(80, "_"))

    # log item data
    def write_to_log(self):
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
        self.__logger.info("Trigger: {0}", triggers)
        self.__repeat_actions.write_to_logger()

        # log laststate settings
        if self.__laststate_item_id is not None:
            self.__logger.debug("Item 'Laststate Id': {0}", self.__laststate_item_id.property.path)
        if self.__laststate_item_name is not None:
            self.__logger.debug("Item 'Laststate Name': {0}", self.__laststate_item_name.property.path)

        # log previousstate settings
        if self.__previousstate_item_id is not None:
            self.__logger.debug("Item 'Previousstate Id': {0}", self.__previousstate_item_id.property.path)
        if self.__previousstate_item_name is not None:
            self.__logger.debug("Item 'Previousstate Name': {0}", self.__previousstate_item_name.property.path)

        # log lastcondition settings
        if self.__lastconditionset_item_id is not None:
            self.__logger.debug("Item 'Lastcondition Id': {0}", self.__lastconditionset_item_id.property.path)
        if self.__lastconditionset_item_name is not None:
            self.__logger.debug("Item 'Lastcondition Name': {0}", self.__lastconditionset_item_name.property.path)

        # log previouscondition settings
        if self.__previousconditionset_item_id is not None:
            self.__logger.debug("Item 'Previouscondition Id': {0}", self.__previousconditionset_item_id.property.path)
        if self.__previousconditionset_item_name is not None:
            self.__logger.debug("Item 'Previouscondition Name': {0}", self.__previousconditionset_item_name.property.path)

        if self.__previousstate_conditionset_item_id is not None:
            self.__logger.debug("Item 'Previousstate condition Id': {0}", self.__previousstate_conditionset_item_id.property.path)
        if self.__previousstate_conditionset_item_name is not None:
            self.__logger.debug("Item 'Previousstate condition Name': {0}",
                               self.__previousstate_conditionset_item_name.property.path)

        self.__init_releasedby()

        for state in self.__states:
            # log states
            state.write_to_log()
            self._initstate = None

        filtered_dict = {key: value for key, value in self.__config_issues.items() if value.get('issue') not in [[], [None], None]}
        self.__config_issues = filtered_dict

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
        handler.push("\tCurrent conditionset: {0} ('{1}')\n".format(self.get_lastconditionset_id(),
                                                                    self.get_lastconditionset_name()))
        handler.push(
            "\tPrevious state: {0} ('{1}')\n".format(self.get_previousstate_id(), self.get_previousstate_name()))
        handler.push("\tPrevious state conditionset: {0} ('{1}')\n".format(self.get_previousstate_conditionset_id(),
                                                                           self.get_previousstate_conditionset_name()))
        handler.push("\tPrevious conditionset: {0} ('{1}')\n".format(self.get_previousconditionset_id(),
                                                                     self.get_previousconditionset_name()))
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
                "Startup Delay over but StateEngine Plugin not running yet. Will try again at {}", next_run)
            self.__se_plugin.scheduler_change(scheduler_name, next=next_run)
            self.__se_plugin.scheduler_trigger(scheduler_name)
        else:
            self.__startup_delay_over = True
            if self.__se_plugin.scheduler_get(scheduler_name):
                self.__se_plugin.scheduler_remove(scheduler_name)
                self.__logger.debug('Startup Delay over. Removed scheduler {}', scheduler_name)
            self.__first_run = None
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
        _issue = None
        if isinstance(item_id, (StateEngineStruct.SeStruct, self.__itemClass)):
            return item_id, None
        if isinstance(item_id, StateEngineState.SeState):
            return self.itemsApi.return_item(item_id.id), None
        if item_id is None:
            _issue = "item_id is None"
            return None, [_issue]
        if not isinstance(item_id, str):
            _issue = "'{0}' is not defined as string.".format(item_id)
            self.__logger.info("{0} Check your item config!", _issue, item_id)
            return None, [_issue]
        item_id = item_id.strip()
        if item_id.startswith("struct:"):
            item = None
            _, item_id = StateEngineTools.partition_strip(item_id, ":")
            try:
                # self.__logger.debug("Creating struct for id {}".format(item_id))
                item = StateEngineStructs.create(self, item_id)
            except Exception as e:
                _issue = "Struct {} creation failed. Error: {}".format(item_id, e)
                self.__logger.error(_issue)
            if item is None:
                _issue = "Item '{0}' in struct not found.".format(item_id)
                self.__logger.warning(_issue)
            return item, [_issue]
        if not item_id.startswith("."):
            match = re.match(r'^(.*):', item_id)
            if item_id.startswith("eval:"):
                if "stateengine_eval" in item_id or "se_eval" in item_id:
                    # noinspection PyUnusedLocal
                    stateengine_eval = se_eval = StateEngineEval.SeEval(self)
                item = item_id.replace('sh', 'self._sh')
                item = item.replace('shtime', 'self._shtime')
                _, _, item = item.partition(":")
                return item, None
            elif match:
                _issue = "Item '{0}' has to be defined as an item path or eval expression without {}.".format(match.group(1), item_id)
                self.__logger.warning(_issue)
                return None, [_issue]
            else:
                item = self.itemsApi.return_item(item_id)
            if item is None:
                _issue = "Item '{0}' not found.".format(item_id)
                self.__logger.warning(_issue)
            return item, [_issue]
        self.__logger.debug("Testing for relative item declaration {}", item_id)
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
            _issue = "Determined item '{0}' does not exist.".format(item_id)
            self.__logger.warning(_issue)
        else:
            self.__logger.develop("Determined item '{0}' for id {1}.", item.property.path, item_id)
        return item, [_issue]

    # Return an item related to the StateEngine object item
    # attribute: Name of the attribute of the StateEngine object item, which contains the item_id to read
    def return_item_by_attribute(self, attribute):
        if attribute not in self.__item.conf:
            _issue = {attribute: {'issue': ['Attribute missing in stateeninge configuration.']}}
            self.__logger.warning("Attribute '{0}' missing in stateeninge configuration.", attribute)
            return None, _issue
        _returnvalue, _issue = self.return_item(self.__item.conf[attribute])
        _issue = {attribute: {'issue': _issue}}
        return _returnvalue, _issue
