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
from .StateEngineLogger import SeLogger
from . import StateEngineItem
from . import StateEngineCurrent
from . import StateEngineDefaults
from . import StateEngineTools
from . import StateEngineCliCommands
from . import StateEngineFunctions
import logging
import os
from lib.model.smartplugin import SmartPlugin
from bin.smarthome import VERSION


class StateEngine(SmartPlugin):
    PLUGIN_VERSION = '1.4.1'

    # Constructor
    # noinspection PyUnusedLocal,PyMissingConstructor
    def __init__(self, sh):

        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)
        self.__items = {}
        self.alive = False
        self.__cli = None

        log_level = self.get_parameter_value("log_level")
        log_directory = self.get_parameter_value("log_directory")
        self.logger.info("Init StateEngine (log_level={0}, log_directory={1})".format(log_level, log_directory))

        StateEngineDefaults.startup_delay = self.get_parameter_value("startup_delay_default")
        StateEngineDefaults.suspend_time = self.get_parameter_value("suspend_time_default")
        StateEngineDefaults.write_to_log(self.logger)

        StateEngineCurrent.init(self.get_sh())

        if log_level > 0:
            if log_directory[0] != "/":
                base = self.get_sh().get_basedir()
                if base[-1] != "/":
                    base += "/"
                log_directory = base + log_directory
            if not os.path.exists(log_directory):
                os.makedirs(log_directory)
            SeLogger.set_loglevel(log_level)
            SeLogger.set_logdirectory(log_directory)
            text = "StateEngine extended logging is active. Logging to '{0}' with loglevel {1}."
            self.logger.info(text.format(log_directory, log_level))
        log_maxage = self.get_parameter_value("log_maxage")
        if log_level > 0 and log_maxage > 0:
            self.logger.info("StateEngine extended log files will be deleted after {0} days.".format(log_maxage))
            SeLogger.set_logmaxage(log_maxage)
            cron = ['init', '30 0 * *']
            self.scheduler_add('StateEngine: Remove old logfiles', SeLogger.remove_old_logfiles, cron=cron, offset=0)

        self.get_sh().stateengine_plugin_functions = StateEngineFunctions.SeFunctions(self.get_sh(), self.logger)

    # Parse an item
    # noinspection PyMethodMayBeStatic
    def parse_item(self, item):
        if "se_manual_include" in item.conf or "se_manual_exclude" in item.conf:
            item._eval = "sh.stateengine_plugin_functions.manual_item_update_eval('" + item.id() + "', caller, source)"
        elif "se_manual_invert" in item.conf:
            item._eval = "not sh." + item.id() + "()"

        return None

    # Initialization of plugin
    def run(self):
        # Initialize
        self.logger.info("Init StateEngine items")
        for item in self.get_sh().find_items("se_plugin"):
            if item.conf["se_plugin"] == "active":
                try:
                    ab_item = StateEngineItem.SeItem(self.get_sh(), item)
                    self.__items[ab_item.id] = ab_item
                except ValueError as ex:
                    self.logger.error("Item: {0}: {1}".format(item.id(), str(ex)))

        if len(self.__items) > 0:
            self.logger.info("Using StateEngine for {} items".format(len(self.__items)))
        else:
            self.logger.info("StateEngine deactivated because no items have been found.")

        self.__cli = StateEngineCliCommands.SeCliCommands(self.get_sh(), self.__items, self.logger)

        self.alive = True
        self.get_sh().stateengine_plugin_functions.ab_alive = True

    # Stopping of plugin
    def stop(self):
        self.alive = False

    # Determine if caller/source are contained in changed_by list
    # caller: Caller to check
    # source: Source to check
    # changed_by: List of callers/source (element format <caller>:<source>) to check against
    def is_changed_by(self, caller, source, changed_by):
        original_caller, original_source = StateEngineTools.get_original_caller(self.get_sh(), caller, source)
        for entry in changed_by:
            entry_caller, __, entry_source = entry.partition(":")
            if (entry_caller == original_caller or entry_caller == "*") and (
                            entry_source == original_source or entry_source == "*"):
                return True
        return False

    # Determine if caller/source are not contained in changed_by list
    # caller: Caller to check
    # source: Source to check
    # changed_by: List of callers/source (element format <caller>:<source>) to check against
    def not_changed_by(self, caller, source, changed_by):
        original_caller, original_source = StateEngineTools.get_original_caller(self.get_sh(), caller, source)
        for entry in changed_by:
            entry_caller, __, entry_source = entry.partition(":")
            if (entry_caller == original_caller or entry_caller == "*") and (
                            entry_source == original_source or entry_source == "*"):
                return False
        return True
