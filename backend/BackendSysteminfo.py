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
import platform
import collections
import datetime
import time
import pwd
import html
import subprocess
import socket
import sys
import threading
import os
import psutil

import bin.shngversion as shngversion
import lib.config
from lib.logic import Logics
import lib.logic   # zum Test (für generate bytecode -> durch neues API ersetzen)
from lib.model.smartplugin import SmartPlugin
from lib.utils import Utils
from .utils import *

import lib.item_conversion

class BackendSysteminfo:

    # -----------------------------------------------------------------------------------
    #    SYSTEMINFO
    # -----------------------------------------------------------------------------------

    @cherrypy.expose
    def system_html(self):
        now = datetime.datetime.now().strftime('%d.%m.%Y %H:%M')
        system = platform.system()
        vers = platform.version()
        # node = platform.node()
        node = socket.getfqdn()
        arch = platform.machine()
        user = pwd.getpwuid(os.geteuid()).pw_name  # os.getlogin()

        ip = Utils.get_local_ipv4_address()
        ipv6 = Utils.get_local_ipv6_address()

        space = os.statvfs(self._sh_dir)
        freespace = space.f_frsize * space.f_bavail / 1024 / 1024

        # return host uptime
        uptime = time.mktime(datetime.datetime.now().timetuple()) - psutil.boot_time()
        days = uptime // (24 * 3600)
        uptime = uptime % (24 * 3600)
        hours = uptime // 3600
        uptime %= 3600
        minutes = uptime // 60
        uptime %= 60
        seconds = uptime
        uptime = self.age_to_string(days, hours, minutes, seconds)

        # return SmarthomeNG runtime
        rt = str(self._sh.runtime())
        daytest = rt.split(' ')
        if len(daytest) == 3:
            days = int(daytest[0])
            hours, minutes, seconds = [float(val) for val in str(daytest[2]).split(':')]
        else:
            days = 0
            hours, minutes, seconds = [float(val) for val in str(daytest[0]).split(':')]
        sh_uptime = self.age_to_string(days, hours, minutes, seconds)

        pyversion = "{0}.{1}.{2} {3}".format(sys.version_info[0], sys.version_info[1], sys.version_info[2],
                                             sys.version_info[3])

        #python_packages = self.getpackages()
        self.logger.info("system_html: calling get_requirements_info()")
        #req_dict = self.get_requirements_info()

        return self.render_template('system.html', 
                                    now=now, system=system, sh_vers=shngversion.get_shng_version(), plg_vers=shngversion.get_plugins_version(), sh_dir=self._sh_dir,
                                    vers=vers, node=node, arch=arch, user=user, freespace=freespace, 
                                    uptime=uptime, sh_uptime=sh_uptime, pyversion=pyversion,
                                    ip=ip, ipv6=ipv6)


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


    def get_requirements_info(self):
        """
        """
        req_dict = {}
        req_dict_base = parse_requirements("%s/requirements/base.txt" % self._sh_dir)

        # parse loaded plugins and look for requirements
        _conf = lib.config.parse(self._sh._plugin_conf)
        plugin_names = []
        for plugin in _conf:
            plugin_name = _conf[plugin].get('class_path', '').strip()
            if plugin_name == '':
                plugin_name = 'plugins.' + _conf[plugin].get('plugin_name', '').strip() 
            if not plugin_name in plugin_names:  # only unique plugin names, e.g. if multiinstance is used
                plugin_names.append(plugin_name)

        req_dict = req_dict_base.copy()
        for plugin_name in plugin_names:
            file_path = "%s/%s/requirements.txt" % (self._sh_dir, plugin_name.replace("plugins.", "plugins/"))
            if os.path.isfile(file_path):
                plugin_dict = parse_requirements(file_path)
                for key in plugin_dict:
                    if key not in req_dict:
                        req_dict[key] = plugin_dict[key] + ' (' + plugin_name.replace('plugins.', '') + ')'
                    else:
                        req_dict[key] = req_dict[key] + '<br/>' + plugin_dict[key] + ' (' + plugin_name.replace(
                            'plugins.', '') + ')'

            self.logger.info("get_requirements_info: req_dict = {}".format(req_dict))
        return req_dict
        

    def check_requirement(self, package, req):
    
        pyversion = "{0}.{1}".format(sys.version_info[0], sys.version_info[1])
        req_templist = req.split('<br/>')
        
        req_list = []
        for req in req_templist:
            if '|' in req:
                reqo = req.split('|')
            else:
                reqo = [req]
            req_list.append(reqo)
            
        self.logger.info("check_requirement: package {}, pyversion {}: required, req_list = {}".format(package, pyversion, req_list))

    
    @cherrypy.expose
    def pypi_json(self):
        """
        returns a list of python package information dicts as json structure

        """

        # check if pypi service is reachable
        if self.pypi_timeout <= 0:
            pypi_available = False
            pypi_unavailable_message = translate('PyPI Prüfung deaktiviert')
        else:
            pypi_available = True
            try:
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.pypi_timeout)
                sock.connect(('pypi.python.org', 443))
                sock.close()
            except:
                pypi_available = False
                pypi_unavailable_message = translate('PyPI nicht erreichbar')

        import pip
        import xmlrpc
        installed_packages = pip.get_installed_distributions()
        pypi = xmlrpc.client.ServerProxy('https://pypi.python.org/pypi')

        req_dict = self.get_requirements_info()

        package_list = []

        for dist in installed_packages:
            package = dict()
            package['name'] = dist.key
            package['vers_installed'] = dist.version

            package['pypi_version'] = ''
            package['pypi_version_available'] = ''
            package['pypi_forreq_ok'] = True
            if pypi_available:
                try:
                    available = pypi.package_releases(dist.project_name)
                    try:
                        package['pypi_version'] = available[0]
                    except:
                        package['pypi_version_available'] = '-'
                except:
                    package['pypi_version_available'] = [translate('Keine Antwort von PyPI')]
            else:
                package['pypi_version_available'] = pypi_unavailable_message

            package['required'] = False
            if req_dict.get(package['name'], '') != '':
                package['required'] = True
                # tests for min, max versions
                self.check_requirement(package['name'], req_dict.get(package['name'], ''))
                
            package['vers_req_min'] = ''
            package['vers_req_max'] = ''
            package['vers_ok'] = False
            package['pypi_forreq_ok'] = True


            if package['required']:
                package['sort'] = '1'
            else:
                package['sort'] = '2'
            package['sort'] += package['name']
            package_list.append(package)

        if 1 == 2:
            package = dict()
#            package['name'] = ''
#            package['required'] = False
#            package['vers_installed'] = ''
            package['vers_req_min'] = ''
            package['vers_req_max'] = ''
            package['vers_ok'] = False
#            package['pypi_version'] = ''
            package['pypi_forreq_ok'] = True
#            package['pypi_version_available'] = ''
#            if package['required']:
#                package['sort'] = '1'
#            else
#                package['sort'] = '2'
#            package['sort'] += package['name']
#            package_list.append(package)
    
#        sorted_package_list = sorted([(i['name'], i['version_installed'], i['version_available']) for i in package_list])
        sorted_package_list = sorted(package_list, key=lambda k: k['sort'], reverse=False)
        self.logger.info("pypi_json: sorted_package_list = {}".format(sorted_package_list))
        self.logger.info("pypi_json: json.dumps(sorted_package_list) = {}".format(json.dumps(sorted_package_list)))
        
        return json.dumps(sorted_package_list)


    def getpackages(self):
        """
        returns a list with the installed python packages and its versions
        """
        self.find_visu_plugin()

        # check if pypi service is reachable
        if self.pypi_timeout <= 0:
            pypi_available = False
            pypi_unavailable_message = translate('PyPI Prüfung deaktiviert')
        else:
            pypi_available = True
            try:
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.pypi_timeout)
                sock.connect(('pypi.python.org', 443))
                sock.close()
            except:
                pypi_available = False
                pypi_unavailable_message = translate('PyPI nicht erreichbar')

        import pip
        import xmlrpc
        installed_packages = pip.get_installed_distributions()
        pypi = xmlrpc.client.ServerProxy('https://pypi.python.org/pypi')
        packages = []
        for dist in installed_packages:
            package = {}
            package['key'] = dist.key
            package['version_installed'] = dist.version
            if pypi_available:
                try:
                    available = pypi.package_releases(dist.project_name)
                    try:
                        package['version_available'] = available[0]
                    except:
                        package['version_available'] = '-'
                except:
                    package['version_available'] = [translate('Keine Antwort von PyPI')]
            else:
                package['version_available'] = pypi_unavailable_message
            packages.append(package)

        sorted_packages = sorted([(i['key'], i['version_installed'], i['version_available']) for i in packages])
        return sorted_packages


