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

class BackendVisu:


    # -----------------------------------------------------------------------------------
    #    VISU
    # -----------------------------------------------------------------------------------

    @cherrypy.expose
    def visu_html(self):
        """
        display a list of all connected visu clients
        """
        clients = []
        if self.visu_plugin is not None:
            if self.visu_plugin_build == '2':
                for c in self.visu_plugin.return_clients():
                    client = dict()
                    deli = c.find(':')
                    client['ip'] = c[0:c.find(':')]
                    client['port'] = c[c.find(':') + 1:]
                    try:
                        client['name'] = socket.gethostbyaddr(client['ip'])[0]
                    except:
                        client['name'] = client['ip']
                    clients.append(client)

            if self.visu_plugin_build > '2':
                # self.logger.warning("BackendServer: Language '{0}' not found, using standard language instead".format(language))
                # yield client.addr, client.sw, client.swversion, client.hostname, client.browser, client.browserversion
                # for c, sw, swv, ch in self.visu_plugin.return_clients():
                for clientinfo in self.visu_plugin.return_clients():
                    c = clientinfo.get('addr', '')
                    client = dict()
                    deli = c.find(':')
                    client['ip'] = c[0:c.find(':')]
                    client['port'] = c[c.find(':') + 1:]
                    try:
                        client['name'] = socket.gethostbyaddr(client['ip'])[0]
                    except:
                        client['name'] = client['ip']
                    client['sw'] = clientinfo.get('sw', '')
                    client['swversion'] = clientinfo.get('swversion', '')
                    client['hostname'] = clientinfo.get('hostname', '')
                    client['browser'] = clientinfo.get('browser', '')
                    client['browserversion'] = clientinfo.get('browserversion', '')
                    clients.append(client)

        clients_sorted = sorted(clients, key=lambda k: k['name'])

        self.find_visu_plugin()
        return self.render_template('visu.html', 
                                    visu_plugin_build=self.visu_plugin_build,
                                    clients=clients_sorted)


