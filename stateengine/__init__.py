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
from .StateEngineLogger import SeLogger
from . import StateEngineItem
from . import StateEngineCurrent
from . import StateEngineDefaults
from . import StateEngineTools
from . import StateEngineCliCommands
from . import StateEngineFunctions
from . import StateEngineWebif
from . import StateEngineStructs
import logging
import os
import copy
from lib.model.smartplugin import *
from lib.item import Items
from .webif import WebInterface

logging.addLevelName(StateEngineDefaults.VERBOSE, 'DEVELOP')


class StateEngine(SmartPlugin):
    PLUGIN_VERSION = '1.9.5'

    # Constructor
    # noinspection PyUnusedLocal,PyMissingConstructor
    def __init__(self, sh):
        super().__init__()
        StateEngineDefaults.logger = self.logger
        self.itemsApi = Items.get_instance()
        self._items = self.abitems = {}
        self.mod_http = None
        self.__sh = sh
        self.alive = False
        self.__cli = None
        self.init_webinterface(WebInterface)
        self.__log_directory = self.get_parameter_value("log_directory")
        try:
            log_level = self.get_parameter_value("log_level")
            StateEngineDefaults.log_level = log_level
            log_directory = self.__log_directory
            self.logger.info("Init StateEngine (log_level={0}, log_directory={1})".format(log_level, log_directory))
            StateEngineDefaults.startup_delay = self.get_parameter_value("startup_delay_default")
            StateEngineDefaults.suspend_time = self.get_parameter_value("suspend_time_default")
            StateEngineDefaults.instant_leaveaction = self.get_parameter_value("instant_leaveaction")
            StateEngineDefaults.suntracking_offset = self.get_parameter_value("lamella_offset")
            StateEngineDefaults.lamella_open_value = self.get_parameter_value("lamella_open_value")
            StateEngineDefaults.write_to_log(self.logger)
            self.get_sh().stateengine_plugin_functions = StateEngineFunctions.SeFunctions(self.get_sh(), self.logger)
            StateEngineCurrent.init(self.get_sh())

            base = self.get_sh().get_basedir()
            log_directory = SeLogger.create_logdirectory(base, log_directory)

            if log_level > 0:
                text = "StateEngine extended logging is active. Logging to '{0}' with log level {1}."
                self.logger.info(text.format(log_directory, log_level))
            log_maxage = self.get_parameter_value("log_maxage")
            if log_maxage > 0:
                self.logger.info("StateEngine extended log files will be deleted after {0} days.".format(log_maxage))
                SeLogger.set_logmaxage(log_maxage)
                cron = ['init', '30 0 * *']
                self.scheduler_add('StateEngine: Remove old logfiles', SeLogger.remove_old_logfiles, cron=cron, offset=0)
            SeLogger.set_loglevel(log_level)
            SeLogger.set_logdirectory(log_directory)

        except Exception as ex:
            self._init_complete = False
            self.logger.warning("Problem loading Stateengine plugin: {}".format(ex))
            return

    # Parse an item
    # noinspection PyMethodMayBeStatic
    def parse_item(self, item):
        item.expand_relativepathes('se_manual_logitem', '', '')
        try:
            item.expand_relativepathes('se_item_*', '', '')
        except Exception:
            pass
        if self.has_iattr(item.conf, "se_manual_include") or self.has_iattr(item.conf, "se_manual_exclude"):
            item._eval = "sh.stateengine_plugin_functions.manual_item_update_eval('" + item.id() + "', caller, source)"
        elif self.has_iattr(item.conf, "se_manual_invert"):
            item._eval = "not sh." + item.id() + "()"
        if self.has_iattr(item.conf, "se_log_level"):
            base = self.get_sh().get_basedir()
            SeLogger.create_logdirectory(base, self.__log_directory)
        return None

    # Initialization of plugin
    def run(self):
        # Initialize
        StateEngineStructs.global_struct = copy.deepcopy(self.itemsApi.return_struct_definitions())
        self.logger.info("Init StateEngine items")
        for item in self.itemsApi.find_items("se_plugin"):
            if item.conf["se_plugin"] == "active":
                try:
                    abitem = StateEngineItem.SeItem(self.get_sh(), item, self)
                    abitem.ab_alive = True
                    self._items[abitem.id] = abitem
                except ValueError as ex:
                    self.logger.error("Problem with Item: {0}: {1}".format(item.property.path, ex))

        if len(self._items) > 0:
            self.logger.info("Using StateEngine for {} items".format(len(self._items)))
        else:
            self.logger.info("StateEngine deactivated because no items have been found.")

        self.__cli = StateEngineCliCommands.SeCliCommands(self.get_sh(), self._items, self.logger)
        self.alive = True
        self.get_sh().stateengine_plugin_functions.ab_alive = True

    # Stopping of plugin
    def stop(self):
        self.logger.debug("stop method called")
        self.scheduler_remove('StateEngine: Remove old logfiles')
        for item in self._items:
            self._items[item].ab_alive = False
            self.scheduler_remove('{}'.format(item))
            self.scheduler_remove('{}-Startup Delay'.format(item))
            self._items[item].remove_all_schedulers()

        self.alive = False
        self.get_sh().stateengine_plugin_functions.ab_alive = False
        self.logger.debug("stop method finished")

    # Determine if caller/source are contained in changed_by list
    # caller: Caller to check
    # source: Source to check
    # changed_by: List of callers/source (element format <caller>:<source>) to check against
    def is_changed_by(self, caller, source, changed_by):
        original_caller, original_source = StateEngineTools.get_original_caller(self.logger, caller, source)
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
        original_caller, original_source = StateEngineTools.get_original_caller(self.logger, caller, source)
        for entry in changed_by:
            entry_caller, __, entry_source = entry.partition(":")
            if (entry_caller == original_caller or entry_caller == "*") and (
                            entry_source == original_source or entry_source == "*"):
                return False
        return True

    def get_items(self):
        """
        Getting a sorted item list with active SE

        :return:        sorted itemlist
        """
        sortedlist = sorted([k for k in self._items.keys()])

        finallist = []
        for i in sortedlist:
            finallist.append(self._items[i])
        return finallist

    def get_graph(self, abitem, graphtype='link'):
        if isinstance(abitem, str):
            abitem = self._items[abitem]
        webif = StateEngineWebif.WebInterface(self.__sh, abitem)
        try:
            os.makedirs(self.path_join(self.get_plugin_dir(), 'webif/static/img/visualisations/'))
        except OSError:
            pass
        vis_file = self.path_join(self.get_plugin_dir(), 'webif/static/img/visualisations/{}.svg'.format(abitem))
        #self.logger.debug("Getting graph: {}, {}".format(abitem, webif))
        try:
            if graphtype == 'link':
                return '<a href="static/img/visualisations/{}.svg"><img src="static/img/vis.png" width="30"></a>'.format(abitem)
            else:
                webif.drawgraph(vis_file)
                return '<object type="image/svg+xml" data="static/img/visualisations/{0}.svg"\
                        style="max-width: 100%; height: auto; width: auto\9; ">\
                        <iframe src="static/img/visualisations/{0}.svg">\
                        <img src="static/img/visualisations/{0}.svg"\
                        style="max-width: 100%; height: auto; width: auto\9; ">\
                        </iframe></object>'.format(abitem)
        except Exception as ex:
            self.logger.error("Problem getting graph for {}. Error: {}".format(abitem, ex))
            return '<h4>Can not show visualization. Most likely GraphViz is missing.</h4> ' \
                   'Please download and install <a href="https://graphviz.org/download/" target="_new">' \
                   'https://graphviz.org/download/</a><br/>' \
                   'on Windows add install path to your environment path AND run dot -c.' \
                   'Additionally copy dot.exe to fdp.exe!'
