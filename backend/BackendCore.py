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
import pwd
import html
import subprocess
import socket
import sys
import threading
import os
import lib.config
from lib.logic import Logics
import lib.logic   # zum Test (für generate bytecode -> durch neues API ersetzen)
from lib.model.smartplugin import SmartPlugin
from .utils import *

import lib.item_conversion

class BackendCore:

    def find_visu_plugin(self):
        """
        look for the configured instance of the visu protocol plugin.
        """
        if self.visu_plugin is not None:
            return

        for p in self._sh._plugins:
            if p.__class__.__name__ == "WebSocket":
                self.visu_plugin = p
        if self.visu_plugin is not None:
            try:
                self.visu_plugin_version = self.visu_plugin.get_version()
            except:
                self.visu_plugin_version = '1.0.0'
            self.visu_plugin_build = self.visu_plugin_version[4:]
            if self.visu_plugin_build < '2':
                self.visu_plugin = None
                self.logger.warning(
                    "Backend: visu protocol plugin v{0} is too old to support BackendServer, please update".format(
                        self.visu_plugin_version))


    def render_template(self, tmpl_name, **kwargs):
        """

        Render a template and add vars needed gobally (for navigation, etc.)
    
        :param tmpl_name: Name of the template file to be rendered
        :param **kwargs: keyworded arguments to use while rendering
        
        :return: contents of the template after beeing rendered 

        """
        self.find_visu_plugin()
        tmpl = self.env.get_template(tmpl_name)
        return tmpl.render(develop=self.developer_mode,
                           smarthome=self._sh, 
                           visu_plugin=(self.visu_plugin is not None), 
                           yaml_converter=lib.item_conversion.is_ruamelyaml_installed(),
                           **kwargs)


    # -----------------------------------------------------------------------------------
    #    MAIN
    # -----------------------------------------------------------------------------------

    @cherrypy.expose
    def index(self):

        return self.render_template('main.html')

    @cherrypy.expose
    def main_html(self):

        return self.render_template('main.html')


    # -----------------------------------------------------------------------------------
    #    SERVICES
    # -----------------------------------------------------------------------------------

    @cherrypy.expose
    def services_html(self):
        """
        shows a page with info about some services needed by smarthome
        """
        knxd_service = self.get_process_info("systemctl status knxd.service")
        smarthome_service = self.get_process_info("systemctl status smarthome.service")
        knxd_socket = self.get_process_info("systemctl status knxd.socket")

        knxdeamon = ''
        if self.get_process_info("ps cax|grep eibd") != '':
            knxdeamon = 'eibd'
        if self.get_process_info("ps cax|grep knxd") != '':
            if knxdeamon != '':
                knxdeamon += ' and '
            knxdeamon += 'knxd'

        sql_plugin = False
        database_plugin = []

        for x in self._sh._plugins:
            if x.__class__.__name__ == "SQL":
                sql_plugin = True
                break
            elif x.__class__.__name__ == "Database":
                database_plugin.append(x.get_instance_name())

        return self.render_template('services.html', 
                                    knxd_service=knxd_service, knxd_socket=knxd_socket, knxdeamon=knxdeamon,
                                    smarthome_service=smarthome_service, lang=get_translation_lang(), 
                                    sql_plugin=sql_plugin, database_plugin=database_plugin)


    @cherrypy.expose
    def reload_translation_html(self, lang=''):
        if lang != '':
            load_translation(lang)
        else:
            load_translation(get_translation_lang())
        return self.index()

    @cherrypy.expose
    def reboot(self):
        passwd = request.form['password']
        rbt1 = subprocess.Popen(["echo", passwd], stdout=subprocess.PIPE)
        rbt2 = subprocess.Popen(["sudo", "-S", "reboot"], stdin=rbt1.
                                stdout, stdout=subprocess.PIPE)
        print(rbt2.communicate()[0])
        return redirect('/services.html')

    def validate_date(self, date_text):
        try:
            datetime.datetime.strptime(date_text, '%Y-%m-%d')
            return True
        except ValueError:
            return False

    @cherrypy.expose
    def db_dump_html(self, plugin):
        """
        returns the smarthomeNG sqlite database as download
        """
        if (plugin == "sqlite_old"):
            self._sh.sql.dump('%s/var/db/smarthomedb.dump' % self._sh_dir)
            mime = 'application/octet-stream'
            return cherrypy.lib.static.serve_file("%s/var/db/smarthomedb.dump" % self._sh_dir, mime,
                                                  "%s/var/db/" % self._sh_dir)
        elif plugin != "":
            for x in self._sh._plugins:
                if isinstance(x, SmartPlugin):
                    if x.get_instance_name() == plugin:
                        x.dump('%s/var/db/smarthomedb_%s.dump' % (self._sh_dir, plugin))
                        mime = 'application/octet-stream'
                        return cherrypy.lib.static.serve_file("%s/var/db/smarthomedb_%s.dump" % (self._sh_dir, plugin),
                                                              mime, "%s/var/db/" % self._sh_dir)
        return

    # -----------------------------------------------------------------------------------

    @cherrypy.expose
    def conf_yaml_converter_html(self, convert=None, conf_code=None, yaml_code=None):
        if convert is not None:
            ydata = lib.item_conversion.parse_for_convert(conf_code=conf_code)
            if ydata != None:
                yaml_code = lib.item_conversion.convert_yaml(ydata)
        else:
            conf_code = '\n\n\n\n\n\n\n\n'
            yaml_code = '\n\n\n\n\n\n\n\n'
        return self.render_template('conf_yaml_converter.html', conf_code=conf_code, yaml_code=yaml_code)


    # -----------------------------------------------------------------------------------
    #    SCHEDULERS
    # -----------------------------------------------------------------------------------

    @cherrypy.expose
    def schedules_html(self):
        """
        display a list of all known schedules
        """
        
        schedule_list = []
        for entry in self._sh.scheduler._scheduler:
            schedule = dict()
            s = self._sh.scheduler._scheduler[entry]
            if s['next'] != None and s['cycle'] != '' and s['cron'] != '':
                schedule['fullname'] = entry
                schedule['name'] = entry
                schedule['group'] = ''
                schedule['next'] = s['next'].strftime('%Y-%m-%d %H:%M:%S%z')
                schedule['cycle'] = s['cycle']
                schedule['cron'] = s['cron']
                
                if schedule['cycle'] == None:
                    schedule['cycle'] = ''
                if schedule['cron'] == None:
                    schedule['cron'] = ''
                
                nl = entry.split('.')
                if nl[0].lower() in ['items','logics','plugins']:
                    schedule['group'] = nl[0].lower()
                    del nl[0]
                    schedule['name'] = '.'.join(nl)
                    
                schedule_list.append(schedule)
                    
        schedule_list_sorted = sorted(schedule_list, key=lambda k: k['fullname'].lower())
        return self.render_template('schedules.html', schedule_list=schedule_list_sorted)


    # -----------------------------------------------------------------------------------
    #    THREADS
    # -----------------------------------------------------------------------------------

    def thread_sum(self, name, count):
        thread = dict()
        if count > 0:
            thread['name'] = name
            thread['sort'] = str(thread['name']).lower()
            thread['id'] = "(" + str(count) + " threads" + ")"
            thread['alive'] = True
        return thread

    @cherrypy.expose
    def threads_html(self):
        """
        display a list of all threads
        """
        threads_count = 0
        cp_threads = 0
        http_threads = 0
        idle_threads = 0
        for thread in threading.enumerate():
            if thread.name.find("CP Server") == 0:
                cp_threads += 1
            if thread.name.find("HTTPServer") == 0:
                http_threads +=1
            if thread.name.find("idle") == 0:
                idle_threads +=1

        threads = []
        for t in threading.enumerate():
            if t.name.find("CP Server") != 0 and t.name.find("HTTPServer") != 0 and t.name.find("idle") != 0:
                thread = dict()
                thread['name'] = t.name
                thread['sort'] = str(t.name).lower()
                thread['id'] = t.ident
                thread['alive'] = t.is_alive()
                threads.append(thread)
                threads_count += 1
        
        if cp_threads > 0:
            threads.append(self.thread_sum("CP Server", cp_threads))
            threads_count += cp_threads
        if http_threads > 0:
            threads.append(self.thread_sum("HTTPServer", http_threads))
            threads_count += http_threads
        if idle_threads > 0:
            threads.append(self.thread_sum("idle", idle_threads))
            threads_count += idle_threads
        
        threads_sorted = sorted(threads, key=lambda k: k['sort'])
        return self.render_template('threads.html', threads=threads_sorted, threads_count=threads_count)


    # -----------------------------------------------------------------------------------
    #    LOGGING
    # -----------------------------------------------------------------------------------

    @cherrypy.expose
    def logging_html(self):
        """
        display a list of all loggers
        """
        loggerDict = {}
        # Filter to get only active loggers
        for l in logging.Logger.manager.loggerDict:
            if (logging.getLogger(l).level > 0) or (logging.getLogger(l).handlers != []):
                loggerDict[l] = logging.Logger.manager.loggerDict[l]
        

        # get information about active loggers
        loggerList_sorted = sorted(loggerDict)
        loggerList_sorted.insert(0, "root")      # Insert information about root logger at the beginning of the list
        loggers = []
        for ln in loggerList_sorted:
            if ln == 'root':
                logger = logging.root
            else:
                logger = logging.getLogger(ln)
            l = dict()
            l['name'] = logger.name
            l['disabled'] = logger.disabled
            
            # get information about loglevels
            if logger.level == 0:
                l['level'] = ''
            elif logger.level in logging._levelToName:
                l['level'] = logging._levelToName[logger.level]
            else:
                l['level'] = logger.level

            l['filters'] = logger.filters

            # get information about handlers and filenames
            l['handlers'] = list()
            l['filenames'] = list()
            for h in logger.handlers:
                l['handlers'].append(h.__class__.__name__)
                try:
                    fn = str(h.baseFilename)
                except:
                    fn = ''
                l['filenames'].append(fn)

            loggers.append(l)

        return self.render_template('logging.html', loggers=loggers)


    @cherrypy.expose
    def log_view_html(self, text_filter='', log_level_filter='ALL', page=1, logfile='smarthome.log'):
        """
        returns the smarthomeNG logfile as view
        """
        log = '/var/log/' + os.path.basename(logfile)
        log_name = self._sh_dir + log
        fobj = open(log_name)
        log_lines = []
        start = (int(page) - 1) * 1000
        end = start + 1000
        counter = 0
        log_level_hit = False
        total_counter = 0
        for line in fobj:
            line_text = html.escape(line)
            if log_level_filter != "ALL" and not self.validate_date(line_text[0:10]) and log_level_hit:
                if start <= counter < end:
                    log_lines.append(line_text)
                counter += 1
            else:
                log_level_hit = False
            if (log_level_filter == "ALL" or line_text.find(log_level_filter) in [19, 20, 21, 22,
                                                                                  23]) and text_filter in line_text:
                if start <= counter < end:
                    log_lines.append(line_text)
                    log_level_hit = True
                counter += 1
        fobj.close()
        num_pages = -(-counter // 1000)
        if num_pages == 0:
            num_pages = 1
        return self.render_template('log_view.html', 
                                    current_page=int(page), pages=num_pages, 
                                    logfile=os.path.basename(log_name), log_lines=log_lines, text_filter=text_filter)


    @cherrypy.expose
    def log_dump_html(self, logfile='smarthome.log'):
        """
        returns the smarthomeNG logfile as download
        """
        log = '/var/log/' + os.path.basename(logfile)
        log_name = self._sh_dir + log
        mime = 'application/octet-stream'
        return cherrypy.lib.static.serve_file(log_name, mime, log_name)

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


    # -----------------------------------------------------------------------------------
    #    DISCLOSURE
    # -----------------------------------------------------------------------------------

    @cherrypy.expose
    def disclosure_html(self):
        """
        display disclosure
        """
        return self.render_template('disclosure.html')

