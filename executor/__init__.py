#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2019-2022 Bernd Meiners                Bernd.Meiners@mail.de
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  This is the executor plugin to run with SmartHomeNG version 1.9 and
#  upwards.
#
#  SmartHomeNG is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHomeNG is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHomeNG. If not, see <http://www.gnu.org/licenses/>.
#
#########################################################################

import os

from lib.module import Modules
from lib.item import Items
from lib.model.smartplugin import SmartPlugin

from .webif import WebInterface


class Executor(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    PLUGIN_VERSION = '1.1.0'

    def __init__(self, sh):
        """
        Initalizes the plugin. The parameters describe for this method are pulled from the entry in plugin.conf.

        """
        # Call init code of parent class (SmartPlugin)
        super().__init__()

        self._init_complete = False

        # If an package import with try/except is done, handle an import error like this:
        self.logger.debug("init {}".format(__name__))

        self._scripts = self.get_parameter_value('scripts')    #default is *executor_scripts*
        self._script_entries = self.get_parameter_value('script_entries')    #default is 6
        self.logger.debug(f"{self._scripts=}, {self._script_entries=}")
        try:
            vardir = sh.get_vardir()
            self.logger.debug(f"{vardir=}")
            self.executor_scripts = os.path.join(vardir, self._scripts)
            self.logger.debug(f"{self.executor_scripts=}")
            os.makedirs(self.executor_scripts, exist_ok=True)
        except Exception as e:
            self.logger.warning(f"Exception {e}: could not access {self._scripts}, executor plugin will not be able to load or save scripts")
            self._scripts = None
            self.executor_scripts = None

        # no start without web interface
        if not self.init_webinterface():
            self.logger.warning(f"could not init webinterface")
            return

        self.logger.debug("init done")
        self._init_complete = True

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug(f"Plugin '{self.get_fullname()}': run method called")
        self.alive = True

    def stop(self):
        """
        Stop method for the plugin
        """
        self.alive = False
        self.logger.debug(f"Plugin '{self.get_fullname()}': stop method called")

    def parse_item(self, item):
        pass

    def parse_logic(self, logic):
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        pass

    def poll_device(self):
        pass

    def init_webinterface(self):
        """"
        Initialize the web interface for this plugin

        This method is only needed if the plugin is implementing a web interface
        """
        try:
            self.mod_http = Modules.get_instance().get_module('http')
        except:
            self.mod_http = None
        if self.mod_http == None:
            self.logger.error("Not initializing the web interface")
            return False

        import sys
        if not "SmartPluginWebIf" in list(sys.modules['lib.model.smartplugin'].__dict__):
            self.logger.warning("Web interface needs SmartHomeNG v1.9 and up. Not initializing the web interface")
            return False

        # set application configuration for cherrypy
        webif_dir = self.path_join(self.get_plugin_dir(), 'webif')
        config = {
            '/': {
                'tools.staticdir.root': webif_dir,
            },
            '/static': {
                'tools.staticdir.on': True,
                'tools.staticdir.dir': 'static'
            }
        }

        # Register the web interface as a cherrypy app
        self.mod_http.register_webif(WebInterface(webif_dir, self),
                                     self.get_shortname(),
                                     config,
                                     self.get_classname(), self.get_instance_name(),
                                     description='')

        return True

