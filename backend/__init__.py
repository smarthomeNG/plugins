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
import json
import subprocess
import socket
import sys
import threading
from lib.model.smartplugin import SmartPlugin

from jinja2 import Environment, FileSystemLoader


class BackendServer(SmartPlugin):
    ALLOW_MULTIINSTANCE = False
    PLUGIN_VERSION='1.1.2'

    def my_to_bool(self, value, attr='', default=False):
        try:
            result = self.to_bool(value)
        except:
            result = default
            self.logger.error("BackendServer: Invalid value '"+str(value)+"' configured for attribute "+attr+" in plugin.conf, using '"+str(result)+"' instead")
        return result


    def get_local_ip_address(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.10.10.10", 80))
        return s.getsockname()[0]

    def __init__(self, sh, port=None, threads=8, ip='', updates_allowed='True', user="admin", password=""):
        self.logger = logging.getLogger(__name__)
        self._user = user
        self._password = password
        if self._password is not None and self._password != "":
            self._basic_auth = True
        else:
            self._basic_auth = False
        self._sh = sh

        if self.is_int(port):
        	self.port = int(port)
        else:
            self.port = 8383
            if port != None:
                self.logger.error("BackendServer: Invalid value '"+str(port)+"' configured for attribute 'port' in plugin.conf, using '"+str(self.port)+"' instead")

        if self.is_int(threads):
        	self.threads = int(threads)
        else:
            self.threads = 8
            self.logger.error("BackendServer: Invalid value '"+str(threads)+"' configured for attribute 'thread' in plugin.conf, using '"+str(self.threads)+"' instead")

        if ip == '':
            ip = self.get_local_ip_address()
            self.logger.debug("BackendServer: Using local ip address '{0}'".format(ip))
        else:
            pass
#        if not self.is_ip(ip):
#            self.logger.error("BackendServer: Invalid value '"+str(ip)+"' configured for attribute ip in plugin.conf, using '"+str('0.0.0.0')+"' instead")
#            ip = '0.0.0.0'

        self.updates_allowed = self.my_to_bool(updates_allowed, 'updates_allowed', True)

        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.logger.debug("BackendServer running from '{}'".format(current_dir))

        userpassdict = {self._user : self._password}
        checkpassword = cherrypy.lib.auth_basic.checkpassword_dict(userpassdict)

        config = {'global' : {
            'server.socket_host' : ip,
            'server.socket_port' : self.port,
            'server.thread_pool' : self.threads,
    
            'engine.autoreload.on' : False,
        
            'tools.staticdir.debug' : True,
            'tools.trailing_slash.on' : False
              },
             '/':
                {
                    'tools.auth_basic.on': self._basic_auth,
                    'tools.auth_basic.realm': 'earth',
                    'tools.auth_basic.checkpassword': checkpassword,
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
        self._cherrypy.tree.mount(Backend(self, self.updates_allowed), '/', config = config )


    def run(self):
        self.logger.debug("BackendServer: rest run")
        #server.start()
        self._cherrypy.engine.start()
        self.logger.debug("BackendServer: engine started")
        #cherrypy.engine.block()
        self.alive = True

    def stop(self):
        self.logger.debug("BackendServer: shutting down")
        self._cherrypy.engine.exit()
        self.logger.debug("BackendServer: engine exited")
        self.alive = False

    def parse_item(self, item):
        pass

    def parse_logic(self, logic):
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        pass


class Backend:
    env = Environment(loader=FileSystemLoader(os.path.dirname(os.path.abspath(__file__))+'/templates'))

    def __init__(self, backendserver=None, updates_allowed=True):
        self.logger = logging.getLogger(__name__)
        self._bs = backendserver
        self._sh = backendserver._sh
        self.updates_allowed = updates_allowed

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
            try:
                vers = self.visu_plugin.get_version()
            except:
                vers = '1.0.0'
            if vers < '1.1.2':
                self.visu_plugin = None
                self.logger.warning("Backend: visu plugin v{0} is too old to support BackendServer, please update".format(vers))
                
    
    @cherrypy.expose
    def index(self):
        self.find_visu_plugin()

        tmpl = self.env.get_template('main.html')
        return tmpl.render( visu_plugin=(self.visu_plugin != None) )

    @cherrypy.expose
    def main_html(self):
        self.find_visu_plugin()

        tmpl = self.env.get_template('main.html')
        return tmpl.render( visu_plugin=(self.visu_plugin != None) )

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

#        try:
#            myip = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#            myip.connect(('8.8.8.8', 80))
#            ip = myip.getsockname()[0]
#            myip.close()
#        except StandardError:
#            ip = "IP nicht erkannt"
        ip = self._bs.get_local_ip_address()
        
        space = os.statvfs(self._sh_dir)
        freespace = space.f_frsize * space.f_bavail/1024/1024

        get_uptime = subprocess.Popen('uptime', stdout=subprocess.PIPE)
        uptime = get_uptime.stdout.read().decode()
        # return SmarthomeNG runtime
        hours, minutes, seconds = [float(val) for val in str(self._sh.runtime()).split(':')]
        if hours > 23:
            days = int(hours / 24)
            hours = hours - 24 * days
            sh_uptime = str(int(days))+" Tage, "+str(int(hours))+" Stunden, "+str(int(minutes))+" Minuten, "+str("%.2f" % seconds)+" Sekunden"
        elif hours > 0:
            sh_uptime = str(int(hours))+" Stunden, "+str(int(minutes))+" Minuten, "+str("%.2f" % seconds)+" Sekunden"
        elif minutes > 0:
            sh_uptime = str(int(minutes))+" Minuten, "+str("%.2f" % seconds)+" Sekunden"
        else:
            sh_uptime = str("%.2f" % seconds)+" Sekunden"
        pyversion = "{0}.{1}.{2} {3}".format(sys.version_info[0], sys.version_info[1], sys.version_info[2], sys.version_info[3])

        tmpl = self.env.get_template('system.html')
        return tmpl.render( now=now, system=system, vers=vers, node=node, arch=arch, user=user,
                                freespace=freespace, uptime=uptime, sh_uptime=sh_uptime, pyversion=pyversion,
                                ip=ip, python_packages=python_packages, visu_plugin=(self.visu_plugin != None))


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
            try:
                package['version_available'] = available[0]
            except:
                package['version_available'] = '-'
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
        return tmpl.render(knxd_service=knxd_service, smarthome_service=smarthome_service, knxd_socket=knxd_socket, sql_plugin=sql_plugin, visu_plugin=(self.visu_plugin != None))

    @cherrypy.expose
    def disclosure_html(self):
        """
        display disclosure
        """
        self.find_visu_plugin()

        tmpl = self.env.get_template('disclosure.html')
        return tmpl.render(smarthome=self._sh, visu_plugin=(self.visu_plugin != None))

    @cherrypy.expose
    def db_dump_html(self):
        """
        returns the smarthomeNG sqlite database as download
        """
        mime = 'application/octet-stream'
        return cherrypy.lib.static.serve_file("%s/var/db/smarthome.db"%self._sh_dir, mime, "%s/var/db/"%self._sh_dir)

    @cherrypy.expose
    def log_dump_html(self):
        """
        returns the smarthomeNG logfile as download
        """
        mime = 'application/octet-stream'
        return cherrypy.lib.static.serve_file("%s/var/log/smarthome.log" % self._sh_dir, mime,
                                              "%s/var/log/" % self._sh_dir)

    @cherrypy.expose
    def log_view_html(self):
        """
        returns the smarthomeNG logfile as view
        """
        self.find_visu_plugin()

        fobj = open("%s/var/log/smarthome.log" % self._sh_dir)
        log_lines = []
        for line in fobj:
            log_lines.append(line.rstrip())
        fobj.close()
        tmpl = self.env.get_template('log_view.html')
        return tmpl.render(smarthome=self._sh, log_lines=log_lines, visu_plugin=(self.visu_plugin != None) )


    @cherrypy.expose
    def items_html(self):
        """
        display a list of items
        """
        self.find_visu_plugin()
        
        tmpl = self.env.get_template('items.html')
        return tmpl.render( smarthome = self._sh, items=sorted(self._sh.return_items(),key=lambda k: str.lower(k['_path']), reverse=False), visu_plugin=(self.visu_plugin != None) )

    @cherrypy.expose
    def items_json_html(self):
        """
        returns a list of items as json structure
        """
        items_sorted = sorted(self._sh.return_items(),key=lambda k: str.lower(k['_path']), reverse=False)
        parent_items_sorted = []
        last_parent_item = None
        for item in items_sorted:
            if last_parent_item is None or last_parent_item._path not in item._path:
                parent_items_sorted.append(item)
                last_parent_item = item

        item_data = self._build_item_tree(items_sorted)

        return json.dumps(item_data)

    def _build_item_tree(self, parent_items_sorted):
        item_data = []

        for item in parent_items_sorted:
            item_data.append({'path': item._path, 'name': item._name, 'nodes': self._build_item_tree(item.return_children())})

        return item_data

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
    def logics_html(self, logic=None, trigger=None, reload=None):
        """
        display a list of all known logics
        """
        self.find_visu_plugin()

        self.logger.warning("Backend: logics_html: trigger = '{0}', reload = '{1}'".format(trigger, reload))
        if trigger != None:
            self.logger.warning("Backend: logics_html: Trigger logic = '{0}'".format(logic))
            if self.updates_allowed:
                if logic in self._sh.return_logics():
                    self._sh.trigger(logic, by='Backend')
                else:
                    self.logger.warning("Backend: Logic '{0}' not found".format(logic))
            else:
                self.logger.warning("Backend: Logic triggering is not allowed. (Change 'updates_allowed' in plugin.conf")

        if reload != None:
            self.logger.warning("Backend: logics_html: Reload logic = '{0}'".format(logic))
            if self.updates_allowed:
                if logic in self._sh.return_logics():
                    mylogic = self._sh.return_logic(logic)
                    mylogic.generate_bytecode()
                    self._sh.trigger(logic, by='Backend', value="Init")
                else:
                    self.logger.warning("Backend: Logic '{0}' not found".format(logic))
            else:
                self.logger.warning("Backend: Logic reloads are not allowed. (Change 'updates_allowed' in plugin.conf")

        tmpl = self.env.get_template('logics.html')
        return tmpl.render( smarthome = self._sh, updates = self.updates_allowed, visu_plugin=(self.visu_plugin != None) )


    @cherrypy.expose
    def schedules_html(self):
        """
        display a list of all known schedules
        """
        self.find_visu_plugin()
        
        tmpl = self.env.get_template('schedules.html')
        return tmpl.render( smarthome = self._sh, visu_plugin=(self.visu_plugin != None) )

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
        return tmpl.render( smarthome = self._sh, plugins=plugins, visu_plugin=(self.visu_plugin != None) )
        
        
    @cherrypy.expose
    def threads_html(self):
        """
        display a list of all threads
        """
        self.find_visu_plugin()
        
        threads = []
        for t in threading.enumerate():
            thread = dict()
            thread['sort'] = str(t.name).lower()
            thread['name'] = t.name
            thread['id'] = t.ident
            thread['alive'] = t.is_alive()
            threads.append(thread)
        threads_sorted = sorted(threads, key=lambda k: k['sort']) 
        threads_count = len(threads_sorted)
            
        tmpl = self.env.get_template('threads.html')
        return tmpl.render( smarthome = self._sh, threads=threads_sorted, threads_count=threads_count, visu_plugin=(self.visu_plugin != None),  )


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
                clients.append(client)
        clients_sorted = sorted(clients, key=lambda k: k['name']) 
        
        tmpl = self.env.get_template('visu.html')
        return tmpl.render( visu_plugin=(self.visu_plugin != None), clients = clients_sorted )


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
