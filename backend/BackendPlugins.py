#!/usr/bin/env python3
# -*- coding: utf8 -*-
#########################################################################
# Copyright 2016-       René Frieß                  rene.friess@gmail.com
#                       Martin Sinn                         m.sinn@gmx.de
#                       Bernd Meiners
#                       Christian Strassburg          c.strassburg@gmx.de
#########################################################################
#  Backend plugin for SmartHomeNG
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

import cherrypy

import lib.config
from lib.plugin import Plugins
from lib.model.smartplugin import SmartPlugin

from .utils import *

#import lib.item_conversion

class BackendPlugins:

    plugins = None

    def __init__(self):

        self.plugins = Plugins.get_instance()
        self.logger.info("BackendPlugins __init__ self.plugins = {}".format(str(self.plugins)))
        
        

    # -----------------------------------------------------------------------------------
    #    PLUGINS
    # -----------------------------------------------------------------------------------

    @cherrypy.expose
    def plugins_html(self, configname=None, shortname=None, instancename=None, enable=None, disable=None, unload=None):
        """
        display a list of all known plugins
        """
        # process actions triggerd by buttons on the web page
        if enable is not None:
            myplg = self.plugins.return_plugin(configname)
            myplg2 = self.plugins.get_pluginthread(configname)
            myplg.run()
            self.logger.warning("disable: configname = {}, myplg = {}, myplg.alive = {}, myplg2 = {}".format(configname, myplg, myplg.alive, myplg2))
        elif disable is not None:
            myplg = self.plugins.return_plugin(configname)
            myplg2 = self.plugins.get_pluginthread(configname)
            myplg.stop()
            self.logger.warning("disable: configname = {}, myplg = {}, myplg.alive = {}, myplg2 = {}".format(configname, myplg, myplg.alive, myplg2))
        elif unload is not None:
            result = self.plugins.unload_plugin(configname)

        # get data for display of page
        conf_plugins = {}
        _conf = lib.config.parse(self.plugins._get_plugin_conf_filename())

        for plugin in _conf:
            conf_plugins[plugin] = {}
            conf_plugins[plugin] = _conf[plugin]

        plugin_list = []
        for x in self.plugins.return_plugins():
            plugin = dict()
            plugin['stopped'] = False
            plugin['metadata'] = x._metadata
            if isinstance(x, SmartPlugin):
                if bool(x._parameters):
                    plugin['attributes'] = x._parameters
                else:
                    plugin['attributes'] = conf_plugins.get(x.get_configname(), {})
                plugin['smartplugin'] = True
                plugin['instancename'] = x.get_instance_name()
                plugin['instance'] = x
                plugin['multiinstance'] = x.is_multi_instance_capable()
                plugin['version'] = x.get_version()
                plugin['configname'] = x.get_configname()
                plugin['shortname'] = x.get_shortname()
                plugin['classpath'] = x._classpath
                plugin['classname'] = x.get_classname()
            else:
                plugin['attributes'] = {}
                plugin['smartplugin'] = False
                plugin['instance'] = x
                plugin['configname'] = x._configname
                plugin['shortname'] = x._shortname
                plugin['classpath'] = x._classpath
                plugin['classname'] = x._classname
                plugin['stopped'] = False
                
            try:
                plugin['stopped'] = not x.alive
                plugin['stoppable'] = True
            except:
                plugin['stopped'] = False
                plugin['stoppable'] = False
            if plugin['shortname'] == 'backend':
                plugin['stoppable'] = False
            
            
            plugin_list.append(plugin)
        plugins_sorted = sorted(plugin_list, key=lambda k: k['classpath'])

        return self.render_template('plugins.html', plugins=plugins_sorted, lang=get_translation_lang(), mod_http=self._bs.mod_http)


