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
import datetime
from . import StateEngineTools
from .StateEngineLogger import SeLogger
from . import StateEngineState
from . import StateEngineDefaults
from . import StateEngineCurrent
from . import StateEngineValue
from lib.item import Items
from lib.shtime import Shtime


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

    # return instance of smarthome.py class
    @property
    def sh(self):
        return self.__sh

    # return instance of logger class
    @property
    def logger(self):
        return self.__logger

    # Constructor
    # smarthome: instance of smarthome.py
    # item: item to use
    def __init__(self, smarthome, item):
        self.items = Items.get_instance()
        self.shtime = Shtime.get_instance()
        self.__sh = smarthome
        self.__item = item
        try:
            self.__id = self.__item.property.path
        except Exception as err:
            self._log_info("Problem initializing ID of item {}. {}", self.__item, err)
            self.__id = item
        self.__name = str(self.__item)
        # initialize logging
        self.__logger = SeLogger.create(self.__item)
        self.__logger.header("Initialize Item {0}".format(self.id))

        # get startup delay
        self.__startup_delay = StateEngineValue.SeValue(self, "Startup Delay", False, "num")
        self.__startup_delay.set_from_attr(self.__item, "se_startup_delay", StateEngineDefaults.startup_delay)
        self.__startup_delay_over = False

        # Init suspend settings
        self.__suspend_time = StateEngineValue.SeValue(self, "Suspension time on manual changes", False, "num")
        self.__suspend_time.set_from_attr(self.__item, "se_suspend_time", StateEngineDefaults.suspend_time)

        # Init laststate items/values
        self.__laststate_item_id = self.return_item_by_attribute("se_laststate_item_id")
        self.__laststate_internal_id = "" if self.__laststate_item_id is None else self.__laststate_item_id.property.value
        self.__laststate_item_name = self.return_item_by_attribute("se_laststate_item_name")
        self.__laststate_internal_name = "" if self.__laststate_item_name is None else self.__laststate_item_name.property.value

        # Init lastconditionset items/values
        self.__lastconditionset_item_id = self.return_item_by_attribute("se_lastconditionset_item_id")
        self.__lastconditionset_internal_id = "" if self.__lastconditionset_item_id is None else self.__lastconditionset_item_id.property.value
        self.__lastconditionset_item_name = self.return_item_by_attribute("se_lastconditionset_item_name")
        self.__lastconditionset_internal_name = "" if self.__lastconditionset_item_name is None else self.__lastconditionset_item_name.property.value

        self.__states = []
        self.__templates = {}
        self.__repeat_actions = StateEngineValue.SeValue(self, "Repeat actions if state is not changed", False, "bool")
        self.__repeat_actions.set_from_attr(self.__item, "se_repeat_actions", True)

        self.__update_trigger_item = None
        self.__update_trigger_caller = None
        self.__update_trigger_source = None
        self.__update_trigger_dest = None
        self.__update_in_progress = False
        self.__update_original_item = None
        self.__update_original_caller = None
        self.__update_original_source = None

        # Check item configuration
        self.__check_item_config()

        # Init variables
        self.__variables = {
            "item.suspend_time": self.__suspend_time.get(),
            "item.suspend_remaining": 0,
            "current.state_id": "",
            "current.state_name": "",
            "current.conditionset_id": "",
            "current.conditionset_name": ""
        }

        # initialize states
        for item_state in self.__item.return_children():
            try:
                self.__states.append(StateEngineState.SeState(self, item_state))
            except ValueError as ex:
                self.__logger.error("Ignoring state {0} because:  {1}".format(item_state.property.path, ex))

        if len(self.__states) == 0:
            raise ValueError("{0}: No states defined!".format(self.id))

        # Write settings to log
        self.__write_to_log()

        # start timer with startup-delay
        startup_delay = 0 if self.__startup_delay.is_empty() else self.__startup_delay.get()
        if startup_delay > 0:
            first_run = self.shtime.now() + datetime.timedelta(seconds=startup_delay)
            scheduler_name = self.__id + "-Startup Delay"
            value = {"item": self.__item, "caller": "Init"}
            self.__sh.scheduler.add(scheduler_name, self.__startup_delay_callback, value=value, next=first_run)
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

    # Find the state, matching the current conditions and perform the actions of this state
    # caller: Caller that triggered the update
    # noinspection PyCallingNonCallable,PyUnusedLocal
    def update_state(self, item, caller=None, source=None, dest=None):
        if self.__update_in_progress or not self.__startup_delay_over:
            return

        self.__update_in_progress = True

        self.__logger.update_logfile()
        self.__logger.header("Update state of item {0}".format(self.__name))
        if caller:
            item_id = item.property.path if item is not None else "(no item)"
            self.__logger.debug("Update triggered by {0} (item={1} source={2} dest={3})", caller, item_id, source, dest)

        # Find out what initially caused the update to trigger if the caller is "Eval"
        orig_caller, orig_source, orig_item = StateEngineTools.get_original_caller(self.sh, caller, source, item)
        if orig_caller != caller:
            text = "Eval initially triggered by {0} (item={1} source={2})"
            self.__logger.debug(text, orig_caller, orig_item.property.path, orig_source)
        cond1 = orig_caller == '{} {}'.format(StateEngineDefaults.plugin_identification, item_id)
        cond2 = caller == '{} {}'.format(StateEngineDefaults.plugin_identification, item_id)
        if cond1 or cond2:
            self.__logger.debug("Ignoring changes from {0}", StateEngineDefaults.plugin_identification)
            self.__update_in_progress = False
            return

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

        # get last state
        last_state = self.__laststate_get()
        if last_state is not None:
            self.__logger.info("Last state: {0} ('{1}')", last_state.id, last_state.name)

        _last_conditionset_id = self.__lastconditionset_get_id()
        _last_conditionset_name = self.__lastconditionset_get_name()
        if _last_conditionset_id not in ['', None]:
            self.__logger.info("Last Conditionset: {0} ('{1}')", _last_conditionset_id, _last_conditionset_name)

        # find new state
        new_state = None
        for state in self.__states:
            if self.__update_check_can_enter(state):
                new_state = state
                break

        # no new state -> stay
        if new_state is None:
            if last_state is None:
                self.__logger.info("No matching state found, no previous state available. Doing nothing.")
            else:
                text = "No matching state found, staying at {0} ('{1}')"
                self.__logger.info(text, last_state.id, last_state.name)
                last_state.run_stay(self.__repeat_actions.get())
            self.__update_in_progress = False
            return

        # get data for new state
        if last_state is not None and new_state.id == last_state.id:
            self.__logger.info("Staying at {0} ('{1}')", new_state.id, new_state.name)
            # New state is last state
            if self.__laststate_internal_name != new_state.name:
                self.__laststate_set(new_state)
            new_state.run_stay(self.__repeat_actions.get())

        else:
            # New state is different from last state
            if last_state is not None:
                self.__logger.info("Leaving {0} ('{1}')", last_state.id, last_state.name)
                last_state.run_leave(self.__repeat_actions.get())

            self.__logger.info("Entering {0} ('{1}')", new_state.id, new_state.name)
            self.__laststate_set(new_state)
            new_state.run_enter(self.__repeat_actions.get())

        self.__update_in_progress = False

    # check if state can be entered after setting state-specific variables
    # state: state to check
    def __update_check_can_enter(self, state):
        try:
            self.__variables["current.state_id"] = state.id
            self.__variables["current.state_name"] = state.name
            return state.can_enter()
        except Exception as ex:
            self.__logger.warning("Problem with currentstate {0}. Error: {1}", state, ex)
        finally:
            self.__variables["current.state_id"] = ""
            self.__variables["current.state_name"] = ""
            self.__variables["current.conditionset_id"] = ""
            self.__variables["current.conditionset_name"] = ""

    # region Laststate *************************************************************************************************
    # Set laststate
    # new_state: new state to be used as laststate
    def __laststate_set(self, new_state):
        self.__laststate_internal_id = new_state.id
        if self.__laststate_item_id is not None:
            # noinspection PyCallingNonCallable
            self.__laststate_item_id(self.__laststate_internal_id)

        self.__laststate_internal_name = new_state.text
        if self.__laststate_item_name is not None:
            # noinspection PyCallingNonCallable
            self.__laststate_item_name(self.__laststate_internal_name)

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
            self.__lastconditionset_item_id(self.__lastconditionset_internal_id)

        self.__lastconditionset_internal_name = new_name
        if self.__lastconditionset_item_name is not None:
            # noinspection PyCallingNonCallable
            self.__lastconditionset_item_name(self.__lastconditionset_internal_name)

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

        # Check scheduler settings and update if requred
        job = self.__sh.scheduler._scheduler.get(self.id)
        if job is None:
            # We do not have an scheduler job so there is nothing to check and update
            return

        changed = False

        # inject value into cycle if required
        if "cycle" in job and job["cycle"] is not None:
            cycle = list(job["cycle"].keys())[0]
            value = job["cycle"][cycle]
            if value is None:
                value = "1"
                changed = True
            new_cycle = {cycle: value}
        else:
            new_cycle = None

        # inject value into cron if required
        if "cron" in job and job["cron"] is not None:
            new_cron = {}
            for entry, value in job['cron'].items():
                if value is None:
                    value = 1
                    changed = True
                new_cron[entry] = value
        else:
            new_cron = None

        # change scheduler settings if cycle or cron have been changed
        if changed:
            self.__sh.scheduler.change(self.id, cycle=new_cycle, cron=new_cron)

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
        job = self.__sh.scheduler._scheduler.get(self.__item.id)
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
        self.__logger.header("Configuration of item {0}".format(self.__name))
        self.__startup_delay.write_to_logger()
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

        # log lastcondition settings
        _conditionset_id = self.return_item_by_attribute("se_lastconditionset_item_id")
        _conditionset_name = self.return_item_by_attribute("se_lastconditionset_item_name")
        if _conditionset_id is not None:
            self.__logger.info("Item 'Lastcondition Id': {0}", _conditionset_id.property.path)
        if _conditionset_name is not None:
            self.__logger.info("Item 'Lastcondition Name': {0}", _conditionset_name.property.path)

        # log states
        for state in self.__states:
            state.write_to_log()

    # endregion

    # region Methods for CLI commands **********************************************************************************
    def cli_list(self, handler):
        handler.push("{0}: {1}\n".format(self.id, self.__laststate_internal_name))

    def cli_detail(self, handler):
        # get data
        crons, cycles = self.__verbose_crons_and_cycles()
        triggers = self.__verbose_triggers()
        handler.push("AutoState Item {0}:\n".format(self.id))
        handler.push("\tCurrent state: {0}\n".format(self.get_laststate_name()))
        handler.push("\tCurrent conditionset: {0}\n".format(self.get_lastconditionset_name()))
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
        self.__startup_delay_over = True
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
    def return_item(self, item_id: str):
        if not item_id.startswith("."):
            item = self.items.return_item(item_id)
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
        item = self.items.return_item(result)
        if item is None:
            self.__logger.warning("Determined item '{0}' does not exist.".format(result))
        return item

    # Return an item related to the StateEngine object item
    # attribute: Name of the attribute of the StateEngine object item, which contains the item_id to read
    def return_item_by_attribute(self, attribute):
        if attribute not in self.__item.conf:
            self.__logger.warning("Problem with attribute '{0}'.".format(attribute))
            return None
        return self.return_item(self.__item.conf[attribute])
