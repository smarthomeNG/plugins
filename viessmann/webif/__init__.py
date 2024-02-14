#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020-      Sebastian Helms             Morg @ knx-user-forum
#########################################################################
#  This file aims to become part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  MultiDevice plugin for handling arbitrary devices via network or serial
#  connection.
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

import json

from lib.item import Items
from lib.model.smartplugin import SmartPluginWebIf
from lib.model.sdp.globals import *
import cherrypy


#############################################################################################################################################################################################################################################
#
# class WebInterface
#
#############################################################################################################################################################################################################################################

class WebInterface(SmartPluginWebIf):

    def __init__(self, webif_dir, plugin):
        """
        Initialization of instance of class WebInterface

        :param webif_dir: directory where the webinterface of the plugin resides
        :param plugin: instance of the plugin
        :type webif_dir: str
        :type plugin: object
        """
        self.logger = plugin.logger
        self.webif_dir = webif_dir
        self.plugin = plugin
        self.items = Items.get_instance()
        self._last_read = {'last': {'addr': None, 'val': None, 'cmd': None}}

        self.tplenv = self.init_template_environment()

    @cherrypy.expose
    def index(self, reload=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        tmpl = self.tplenv.get_template('index.html')
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)

        plgitems = []
        for item in self.plugin._plg_item_dict:
            if item != self.plugin._suspend_item_path and not item.endswith('.read'):
                plgitems.append(self.plugin._plg_item_dict[item]['item'])

#                           items=sorted(self.items.return_items(), key=lambda k: str.lower(k['_path'])),
#                           cmds=self.cmdset,
#                           units=sorted(list(self.plugin._unitset.keys())),
#                           last_read_addr=self._last_read['last']['addr'],
#                           last_read_value=self._last_read['last']['val'],
#                           last_read_cmd=self._last_read['last']['cmd']

        return tmpl.render(p=self.plugin,
                           items=sorted(plgitems, key=lambda k: str.lower(k.property.path)),
                           cmds=self.plugin._commands.get_commandlist(),
                           running=self.plugin.alive,
                           lookups=self.plugin._commands._lookups,
                           units=self.plugin._commands.get_dtlist(),
                           last_read_addr=self._last_read['last']['addr'],
                           last_read_value=self._last_read['last']['val'],
                           last_read_cmd=self._last_read['last']['cmd'])

    @cherrypy.expose
    def submit(self, button='', addr='', unit='', length='', clear=False):
        '''
        Submit handler for Ajax
        '''
        if button:

            read_val = self.plugin.read_addr(button)
            if read_val is None:
                self.logger.debug(f'Error trying to read addr {button} submitted by WebIf')
                read_val = 'Fehler beim Lesen'
            else:
                try:
                    read_cmd = self.plugin._commands.get_commands_from_reply(button)[0]
                except Exception:
                    read_cmd = '(unknown)'
                if read_cmd is not None:
                    self._last_read[button] = {'addr': button, 'cmd': read_cmd, 'val': read_val}
                    self._last_read['last'] = self._last_read[button]

        elif addr is not None and unit is not None and length.isnumeric():

            read_val = self.plugin.read_temp_addr(addr, int(length), unit)
            if read_val is None:
                self.logger.debug(f'Error trying to read custom addr {button} submitted by WebIf')
                read_val = 'Fehler beim Lesen'
            else:
                self._last_read[addr] = {'addr': addr, 'cmd': f'custom ({addr})', 'val': read_val}
                self._last_read['last'] = self._last_read[addr]

        elif clear:
            for addr in self._last_read:
                self._last_read[addr]['val'] = ''
            self._last_read['last'] = {'addr': None, 'val': '', 'cmd': ''}

        cherrypy.response.headers['Content-Type'] = 'application/json'
        return json.dumps(self._last_read).encode('utf-8')
