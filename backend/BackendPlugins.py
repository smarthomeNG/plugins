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
from lib.model.smartplugin import SmartPlugin

from .utils import *

#import lib.item_conversion

class BackendPlugins:


    # -----------------------------------------------------------------------------------
    #    PLUGINS
    # -----------------------------------------------------------------------------------

    @cherrypy.expose
    def plugins_html(self):
        """
        display a list of all known plugins
        """
        conf_plugins = {}
        _conf = lib.config.parse(self._sh._plugin_conf)
        for plugin in _conf:
            conf_plugins[plugin] = {}
            conf_plugins[plugin] = _conf[plugin]

        plugins = []
        for x in self._sh._plugins:
            plugin = dict()
            if bool(x._parameters):
                plugin['attributes'] = x._parameters
            else:
                plugin['attributes'] = conf_plugins[x._config_section]
            plugin['metadata'] = x._metadata
            if isinstance(x, SmartPlugin):
                plugin['smartplugin'] = True
                plugin['instancename'] = x.get_instance_name()
                plugin['multiinstance'] = x.is_multi_instance_capable()
                plugin['version'] = x.get_version()
                plugin['shortname'] = x.get_shortname()
                plugin['classpath'] = x._classpath
                plugin['classname'] = x.get_classname()
            else:
                plugin['smartplugin'] = False
                plugin['shortname'] = x._shortname
                plugin['classpath'] = x._classpath
                plugin['classname'] = x._classname
            plugins.append(plugin)
        plugins_sorted = sorted(plugins, key=lambda k: k['classpath'])

        return self.render_template('plugins.html', plugins=plugins_sorted, lang=get_translation_lang(), mod_http=self._bs.mod_http)


