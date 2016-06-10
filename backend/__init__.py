#!/usr/bin/env python3
# -*- coding: utf8 -*-
#########################################################################
#  Copyright 2016 Bernd Meiners, 
#                 Christian Strassburg            c.strassburg@gmx.de
#                 René Frieß                      rene.friess@gmail.com
#                 Martin Sinn                     m.sinn@gmx.de
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
import logging
import platform
import datetime
import pwd
import os
import subprocess
import socket
import sys
from lib.model.smartplugin import SmartPlugin
import plugins.visu_websocket as Visu

from jinja2 import Environment, FileSystemLoader


class BackendServer(SmartPlugin):
    ALLOW_MULTIINSTANCE = False
    PLUGIN_VERSION='1.1.1'

    def __init__(self, sh, port=8080, threads=8, ip='127.0.0.1'):
        self.logger = logging.getLogger(__name__)
        self._sh = sh
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.logger.debug("BackendServer running from '{}'".format(current_dir))
        config = {'global' : {
            'server.socket_host' : ip,
            'server.socket_port' : int(port),
            'server.thread_pool' : threads,
    
            'engine.autoreload.on' : False,
        
            'tools.staticdir.debug' : True,
            'tools.trailing_slash.on' : False
              },
             '/':
                        {
                            'tools.staticdir.root' : current_dir,
                        },
                    '/static':
                        {
                            'tools.staticdir.on': True,
                            'tools.staticdir.dir': os.path.join(current_dir, 'static')
                        }
            }
        self._cherrypy = cherrypy
        self._cherrypy.config.update(config)
        self._cherrypy.tree.mount(Backend(self._sh), '/', config = config )

    def run(self):
        self.logger.debug("rest run")
        #server.start()
        self._cherrypy.engine.start()
        self.logger.debug("engine started")
        #cherrypy.engine.block()
        self.alive = True

    def stop(self):
        self.logger.debug("shutting down")
        self._cherrypy.engine.exit()
        self.logger.debug("engine exited")
        self.alive = False

    def parse_item(self, item):
        pass

    def parse_logic(self, logic):
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        pass


class Backend:
#    logger = logging.getLogger(__name__)
    env = Environment(loader=FileSystemLoader(os.path.dirname(os.path.abspath(__file__))+'/templates'))

    def __init__(self, sh=None):
        self.logger = logging.getLogger(__name__)
        self._sh = sh
        self._sh_dir = self._sh.base_dir

        self.visu_plugin = None
    
    
    def find_visu_plugin(self):
        """
        look for the configured instance of the visu protocol plugin.
        """
        if self.visu_plugin != None:
            return
            
        for p in self._sh._plugins:
            if p.__class__.__name__ == "WebSocket":
                self.visu_plugin = p
        if self.visu_plugin != None:
            self.logger.warning("Backend.find_visu_plugin found visu plugin = '{}'".format(self.visu_plugin))
            try:
                vers = self.visu_plugin.get_version()
            except:
                vers = '0.0.0'
            self.logger.warning("Backend.find_visu_plugin plugin version = '{}'".format(vers))
            if vers < '1.1.2':
                self.visu_plugin = None
                self.logger.warning("Backend: visu plugin is too old to support BackendServer, please update")
                
    
    @cherrypy.expose
    def index(self):
        self.find_visu_plugin()

        tmpl = self.env.get_template('main.html')
        return tmpl.render()

    @cherrypy.expose
    def main_html(self):
        self.find_visu_plugin()

        tmpl = self.env.get_template('main.html')
        return tmpl.render()

    @cherrypy.expose
    def system_html(self):
        self.find_visu_plugin()
        now = datetime.datetime.now().strftime('%d.%m.%Y %H:%M')
        system = platform.system()
        vers = platform.version()
        node = platform.node()
        arch = platform.machine()
        user = pwd.getpwuid(os.geteuid()).pw_name  #os.getlogin()
        node = platform.node()
        python_packages = self.getpackages()

        try:
            myip = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            myip.connect(('8.8.8.8', 80))
            ip = myip.getsockname()[0]
            myip.close()
        except StandardError:
            ip = "IP nicht erkannt"

        space = os.statvfs(self._sh_dir)
        freespace = space.f_frsize * space.f_bavail/1024/1024

        get_uptime = subprocess.Popen('uptime', stdout=subprocess.PIPE)
        uptime = get_uptime.stdout.read().decode()
        pyversion = "{0}.{1}.{2} {3}".format(sys.version_info[0], sys.version_info[1], sys.version_info[2], sys.version_info[3])

        tmpl = self.env.get_template('system.html')
        return tmpl.render( now=now, system=system, vers=vers, node=node, arch=arch, user=user,
                                freespace=freespace, uptime=uptime, pyversion=pyversion,
                                ip=ip, python_packages=python_packages)

    def get_process_info(self, command):
        """
        returns output from executing a given command via the shell.
        """
        self.find_visu_plugin()
        ## get subprocess module
        import subprocess

        ## call date command ##
        p = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)

        # Talk with date command i.e. read data from stdout and stderr. Store this info in tuple ##
        # Interact with process: Send data to stdin. Read data from stdout and stderr, until end-of-file is reached.
        # Wait for process to terminate. The optional input argument should be a string to be sent to the child process, or None, if no data should be sent to the child.
        (result, err) = p.communicate()

        ## Wait for date to terminate. Get return returncode ##
        p_status = p.wait()
        return str(result, encoding='utf-8', errors='strict')

    def getpackages(self):
        """
        returns a list with the installed python packages and its versions
        """
        self.find_visu_plugin()
        import pip
        import xmlrpc
        installed_packages = pip.get_installed_distributions()
        pypi = xmlrpc.client.ServerProxy('http://pypi.python.org/pypi')
        packages = []
        for dist in installed_packages:
            package = {}
            available = pypi.package_releases(dist.project_name)
            package['key'] = dist.key
            package['version_installed'] = dist.version
            package['version_available'] = available[0]
            packages.append(package)

        sorted_packages = sorted([(i['key'], i['version_installed'], i['version_available']) for i in packages])
        return sorted_packages


    @cherrypy.expose
    def services_html(self):
        """
        shows a page with info about some services needed by smarthome
        """
        self.find_visu_plugin()
        knxd_service = self.get_process_info("systemctl status knxd.service")
        smarthome_service = self.get_process_info("systemctl status smarthome.service")
        knxd_socket = self.get_process_info("systemctl status knxd.socket")

        sql_plugin = False
        for x in self._sh._plugins:
            if x.__class__.__name__ == "SQL":
                sql_plugin = True
                break

        tmpl = self.env.get_template('services.html')
        return tmpl.render(knxd_service=knxd_service, smarthome_service=smarthome_service, knxd_socket=knxd_socket, sql_plugin=sql_plugin)

    @cherrypy.expose
    def disclosure_html(self):
        """
        display disclosure
        """
        self.find_visu_plugin()

        tmpl = self.env.get_template('disclosure.html')
        return tmpl.render(smarthome=self._sh)

    @cherrypy.expose
    def db_dump_html(self):
        """
        returns the smarthome.py sqlite database as download
        """
        mime = 'application/octet-stream'
        return cherrypy.lib.static.serve_file("%s/var/db/smarthome.db"%self._sh_dir, mime, "%s/var/db/"%self._sh_dir)
        return db_file_value

    @cherrypy.expose
    def items_html(self):
        """
        display a list of items
        """
        self.find_visu_plugin()
        
        tmpl = self.env.get_template('items.html')
        self.logger.warning("backend items_html: self._sh.return_items() = {0}".format(self._sh.return_items()))
        return tmpl.render( smarthome = self._sh )

    #def dump(self, path, match=True):
    #    if match:
    #        items = self.sh.match_items(path)
    #    else:
    #        items = [self.sh.return_item(path)]
    #    if len(items):
    #        for item in items:
    #            if hasattr(item, 'id') and item._type:
    #                self.push("Item {} ".format(item.id()))
    #                self.push("{\n")
    #                self.push("  type = {}\n".format(item.type()))
    #                self.push("  value = {}\n".format(item()))
    #                self.push("  age = {}\n".format(item.age()))
    #                self.push("  last_change = {}\n".format(item.last_change()))
    #                self.push("  changed_by = {}\n".format(item.changed_by()))
    #                self.push("  previous_value = {}\n".format(item.prev_value()))
    #                self.push("  previous_age = {}\n".format(item.prev_age()))
    #                self.push("  previous_change = {}\n".format(item.prev_change()))
    #                if hasattr(item, 'conf'):
    #                    self.push("  config = {\n")
    #                    for name in item.conf:
    #                        self.push("    {} = {}\n".format(name, item.conf[name]))
    #                    self.push("  }\n")
    #                self.push("  logics = [\n")
    #                for trigger in item.get_logic_triggers():
    #                    self.push("    {}\n".format(trigger))
    #                self.push("  ]\n")
    #                self.push("  triggers = [\n")
    #                for trigger in item.get_method_triggers():
    #                    self.push("    {}\n".format(trigger))
    #                self.push("  ]\n")
    #                self.push("}\n")
    #    else:
    #        self.push("Nothing found\n")        
        
    @cherrypy.expose
    def logics_html(self):
        """
        display a list of all known logics
        """
        self.find_visu_plugin()
        
        tmpl = self.env.get_template('logics.html')
        return tmpl.render( smarthome = self._sh )


    @cherrypy.expose
    def schedules_html(self):
        """
        display a list of all known schedules
        """
        self.find_visu_plugin()
        
        tmpl = self.env.get_template('schedules.html')
        return tmpl.render( smarthome = self._sh )

    @cherrypy.expose
    def plugins_html(self):
        """
        display a list of all known plugins
        """
        self.find_visu_plugin()
        plugins = []
        for x in self._sh._plugins:
            plugin = dict()
            plugin['classname'] = x.__class__.__name__
            if isinstance(x, SmartPlugin):
                plugin['smartplugin'] = True
                plugin['instancename'] = x.get_instance_name()
                plugin['multiinstance'] = x.is_multi_instance_capable()
                plugin['version'] = x.get_version()
            else:
                plugin['smartplugin'] = False
            plugins.append(plugin)

        tmpl = self.env.get_template('plugins.html')
        return tmpl.render( smarthome = self._sh, plugins = plugins )
        
        
    @cherrypy.expose
    def visu_html(self):
        """
        display a list of all connected visu clients
        """
        self.find_visu_plugin()
            
        clients = []
        if self.visu_plugin != None:
            for c in self.visu_plugin.return_clients():
                client = dict()
                deli = c.find(':')
                client['ip'] = c[0:c.find(':')]
                client['port'] = c[c.find(':')+1:]
                client['name'] = socket.gethostbyaddr(client['ip'])[0]
                self.logger.warning("BackendServer ip = '{0}', port = '{1}', deli = '{2}', name = '{3}'".format(client['ip'], client['port'], deli, client['name']))
                clients.append(client)
            self.logger.warning("BackendServer clients = '{0}'".format(clients))
        clients_sorted = sorted(clients, key=lambda k: k['name']) 
        
        tmpl = self.env.get_template('visu.html')
        return tmpl.render( visu_plugin = self.visu_plugin, clients = clients_sorted )


    @cherrypy.expose
    def reboot(self):
        passwd = request.form['password']
        rbt1 = subprocess.Popen(["echo", passwd], stdout=subprocess.PIPE)
        rbt2 = subprocess.Popen(["sudo", "-S", "reboot"], stdin=rbt1.
                                stdout, stdout=subprocess.PIPE)
        print(rbt2.communicate()[0])
        return redirect('/services.html')

#if __name__ == "__main__":
#    server = BackendServer( None, port=8080, ip='0.0.0.0')
#    server.run()
