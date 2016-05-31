#!/usr/bin/env python3
# -*- coding: utf8 -*-
#########################################################################
#  Copyright 2016 Bernd Meiners, 
#                 Christian Strassburg            c.strassburg@gmx.de
#                 René Frieß                      rene.friess@gmail.com
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
from lib.model.smartplugin import SmartPlugin

from jinja2 import Environment, FileSystemLoader


class BackendServer(SmartPlugin):
    ALLOW_MULTIINSTANCE = False
    PLUGIN_VERSION='1.1.1'

    def __init__(self, sh, port=8080, threads=8, ip='127.0.0.1', sh_dir='/home/'):
        self.logger = logging.getLogger(__name__)
        self._sh = sh
        #if self.to_bool(sh_dir):
        #    self._sh_dir = "/home/"
        #else:
        self._sh_dir = sh_dir

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
        self._cherrypy.tree.mount(Backend(self._sh_dir, sh), '/', config = config)

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
    logger = logging.getLogger(__name__)
    env = Environment(loader=FileSystemLoader(os.path.dirname(os.path.abspath(__file__))+'/templates'))

    def __init__(self, sh_dir, sh=None):
        self._sh = sh
        self._sh_dir = sh_dir
    
    @cherrypy.expose
    def index(self):
        tmpl = self.env.get_template('main.html')
        return tmpl.render()

    @cherrypy.expose
    def main_html(self):
        tmpl = self.env.get_template('main.html')
        return tmpl.render()

    @cherrypy.expose
    def system_html(self):
        today = datetime.date.today()
        system = platform.system()
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
        freespace = (space.f_frsize * space.f_bavail)/1024/1024

        get_uptime = subprocess.Popen('uptime', stdout=subprocess.PIPE)
        uptime = get_uptime.stdout.read()

        tmpl = self.env.get_template('system.html')
        return tmpl.render( today=today, system= \
                                system, node=node, arch=arch, user=user, \
                                freespace=freespace, uptime=uptime,
                                ip=ip, python_packages=python_packages)

    def get_process_info(self, command):
        """
        returns output from executing a given command via the shell.
        """
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
        import pip
        installed_packages = pip.get_installed_distributions()
        sorted_installed_packages = sorted([(i.key, i.version) for i in installed_packages])
        return sorted_installed_packages


    @cherrypy.expose
    def services_html(self):
        """
        shows a page with info about some services needed by smarthome
        """
        knxd_service = self.get_process_info("systemctl status knxd.service")
        smarthome_service = self.get_process_info("systemctl status smarthome.service")
        knxd_socket = self.get_process_info("systemctl status knxd.socket")
        python_packages = self.getpackages()

        tmpl = self.env.get_template('services.html')
        return tmpl.render(knxd_service=knxd_service, smarthome_service=smarthome_service, knxd_socket=knxd_socket, python_packages=python_packages)

        
    @cherrypy.expose
    def items_html(self):
        """
        display a list of items
        """
        
        tmpl = self.env.get_template('items.html')
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
        
        tmpl = self.env.get_template('logics.html')
        return tmpl.render( smarthome = self._sh )


    @cherrypy.expose
    def schedules_html(self):
        """
        display a list of all known schedules
        """
        
        tmpl = self.env.get_template('schedules.html')
        return tmpl.render( smarthome = self._sh )

    @cherrypy.expose
    def plugins_html(self):
        """
        display a list of all known plugins
        """
        plugins = []
        for x in self._sh._plugins:
            plugin = dict()
            plugin['classname'] = x.__class__.__name__
            if isinstance(x, SmartPlugin):
                plugin['smartplugin'] = True
                plugin['instancename'] = x.get_instance_name()
                plugin['multiinstance'] = x.is_multi_instance()
                plugin['version'] = x.get_version()
            else:
                plugin['smartplugin'] = False
            plugins.append(plugin)

        tmpl = self.env.get_template('plugins.html')
        return tmpl.render( smarthome = self._sh, plugins = plugins )
        
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
