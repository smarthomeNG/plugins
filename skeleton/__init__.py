#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2013 KNX-User-Forum e.V.            http://knx-user-forum.de/
#########################################################################
#  This file is part of SmartHomeNG
#
#  Basic Skeleton for new plugins to run with SmartHomeNG version 1.1
#  upwards.
#
#  SmartHomeNG is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHome.py is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHome.py (NG). If not, see <http://www.gnu.org/licenses/>.
#
#########################################################################

import logging
from lib.model.smartplugin import SmartPlugin

class PluginName(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """
    ALLOW_MULTIINSTANCE = False
    PLUGIN_VERSION = "1.2.1"

    def __init__(self, smarthome):
        """
        Initalizes the plugin. The parameters describe for this method are pulled from the entry in plugin.conf.

        :param smarthome:           The instance of the smarthome object, save it for later references
        """
        self._sh = smarthome
        self.logger = logging.getLogger(__name__)   # get a unique logger for the plugin and provide it internally

        # todo:
        # put any initialization for your plugin here
        

    def run(self):
        """
        Run method for the plugin
        """        
        self.alive = True
        # if you want to create child threads, do not make them daemon = True!
        # They will not shutdown properly. (It's a python bug)


    def stop(self):
        """
        Stop method for the plugin
        """
        self.alive = False


    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        Selects each item corresponding to its attribute keywords and adds it to an internal array

        :param item: The item to process.
        """
        if 'plugin_attr' in item.conf:
            logger.debug("parse item: {0}".format(item))
            return self.update_item
        else:
            return None


    def parse_logic(self, logic):
        """
        Default plugin parse_logic method
        """
        if 'xxx' in logic.conf:
            # self.function(logic['name'])
            pass

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Write items values

        :param item: item to be updated towards the plugin
        :param caller: if given it represents the caller
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        # todo here: change 'plugin' to the plugin name
        if caller != 'plugin':  
            logger.info("update item: {0}".format(item.id()))

"""
If the plugin is run standalone e.g. for test purposes the follwing code will be executed
"""
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    # todo change the PluginName to the real name and set the argument to a valid one
    myplugin = PluginName('smarthome-dummy')
    myplugin.run()
