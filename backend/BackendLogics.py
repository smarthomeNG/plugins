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
from lib.utils import Utils

from lib.model.smartplugin import SmartPlugin

from .utils import *

import lib.item_conversion

class BackendLogics:

    # -----------------------------------------------------------------------------------
    #    LOGICS
    # -----------------------------------------------------------------------------------

    @cherrypy.expose
    def logics_html(self, logic=None, trigger=None, reload=None, enable=None, disable=None, savereload=None, unload=None, configload=None, add=None):
        """
        returns information to display a list of all known logics
        """
        # process actions triggerd by buttons on the web page
        self.process_logics_action(logic, trigger, reload, enable, disable, savereload, None, unload, configload, add)

        # find out if blockly plugin is loaded
        if self.blockly_plugin_loaded == None:
            self.blockly_plugin_loaded = False
            for x in self._sh._plugins:
                try:
                    if x.get_shortname() == 'blockly':
                        self.blockly_plugin_loaded = True
                except:
                    pass

        # create a list of dicts, where each dict contains the information for one logic
        logics = []
        import time
        for ln in Logics.return_loaded_logics():
            anfangfor = time.time()
            thislogic = Logics.return_logic(ln)
#            self.logger.info("logics_html: name {} Start".format(thislogic.name))
            logic = dict()
            logic['name'] = thislogic.name
#            logic['enabled'] = thislogic.enabled
            logic['enabled'] = Logics.is_logic_enabled(thislogic.name)
            logic['logictype'] = Logics.return_logictype(logic['name'])
            if logic['logictype'] == 'Python':
                logic['filename'] = thislogic.pathname
            elif logic['logictype'] == 'Blockly':
                logic['filename'] = os.path.splitext(thislogic.pathname)[0] + '.blockly'
            else:
                logic['filename'] = ''
            logic['userlogic'] = Logics.is_userlogic(thislogic.name)
            logic['crontab'] = thislogic.crontab
            logic['cycle'] = thislogic.cycle
            logic['watch_items'] = []
            if hasattr(thislogic, 'watch_item'):
                logic['watch_items'] = thislogic.watch_item
            logics.append(logic)
#            self.logger.info("logics_html: name {} Start".format(thislogic.name))
            self.logger.debug("Backend: logics_html: - logic = {}, enabled = {}, , logictype = {}, filename = {}, userlogic = {}, watch_items = {}".format(str(logic['name']), str(logic['enabled']), str(logic['logictype']), str(logic['filename']), str(logic['userlogic']), str(logic['watch_items'])) )

        newlogics = sorted(self.logic_findnew(logics), key=lambda k: k['name'])

        logics_sorted = sorted(logics, key=lambda k: k['name'])
        return self.render_template('logics.html', updates=self.updates_allowed, logics=logics_sorted, newlogics=newlogics, 
                                                   blockly_loaded=self.blockly_plugin_loaded)


    @cherrypy.expose
    def logics_view_html(self, file_path, logicname, trigger=None, reload=None, enable=None, disable=None, savereload=None, logics_code=None, cycle=None, crontab=None, watch=None):
        """
        returns information to display a logic in an editor window
        """
        # process actions triggerd by buttons on the web page
        self.process_logics_action(logicname, trigger, reload, enable, disable, savereload, logics_code, None, None, None, cycle, crontab, watch)

        mylogic = dict()
        mylogic['name'] = Logics.return_logic(logicname).name
        mylogic['enabled'] = Logics.return_logic(logicname).enabled
        mylogic['filename'] = Logics.return_logic(logicname).filename
        mylogic['cycle'] = ''
        mylogic['next_exec'] = ''
        if self._sh.scheduler.return_next(Logics.return_logic(logicname).name):
            mylogic['next_exec'] = self._sh.scheduler.return_next(Logics.return_logic(logicname).name).strftime('%Y-%m-%d %H:%M:%S%z')

        if hasattr(Logics.return_logic(logicname), 'cycle'):
            mylogic['cycle'] = Logics.return_logic(logicname).cycle
            if mylogic['cycle'] == None:
                mylogic['cycle'] = ''

        mylogic['crontab'] = ''
        if hasattr(Logics.return_logic(logicname), 'crontab'):
            mylogic['crontab'] = str(Logics.return_logic(logicname).crontab)
            if mylogic['crontab'][0] == '[':
                if mylogic['crontab'][-1] == ']':
                    mylogic['crontab'] = mylogic['crontab'][1:-1]  # remove square brackets

        mylogic['watch_item'] = ''
        if hasattr(Logics.return_logic(logicname), 'watch_item'):
            mylogic['watch_item'] = str(Logics.return_logic(logicname).watch_item)
            if mylogic['watch_item'][0] == '[':
                if mylogic['watch_item'][-1] == ']':
                    mylogic['watch_item'] = mylogic['watch_item'][1:-1]  # remove square brackets
        
        fobj = open(file_path)
        file_lines = []
        for line in fobj:
            file_lines.append(self.html_escape(line))
        fobj.close()

        if os.path.splitext(file_path)[1] == '.blockly':
            return self.render_template('logics_view.html', logicname=logicname, thislogic=mylogic, logic_lines=file_lines, file_path=file_path,
                                        updates=False, 
                                        yaml_updates=(Logics.return_config_type() == '.yaml'),
                                        mode='xml')
        else:
            return self.render_template('logics_view.html', logicname=logicname, thislogic=mylogic, logic_lines=file_lines, file_path=file_path,
                                        updates=self.updates_allowed, 
                                        yaml_updates=(Logics.return_config_type() == '.yaml'),
                                        mode='python')

    # -----------------------------------------------------------------------------------

    def process_logics_action(self, logicname=None, trigger=None, reload=None, enable=None, disable=None, savereload=None, logics_code=None, unload=None, configload=None, add=None,
                              cycle=None, crontab=None, watch=None):

        self.logger.debug(
            "logics_html -> process_logics_action: trigger = '{}', reload = '{}', enable='{}', disable='{}', savereload='{}', cycle='{}', crontab='{}', watch='{}'".format(trigger, reload,
                                                                                                     enable, disable, savereload, cycle, crontab, watch))
        logic = logicname
        if enable is not None:
            Logics.enable_logic(logic)

        if disable is not None:
            Logics.disable_logic(logic)
        
        if trigger is not None:
            Logics.trigger_logic(logic)
        
        if reload is not None:
            Logics.unload_logic(logic)
            Logics.load_logic(logic)
            Logics.trigger_logic(logic)

        if unload is not None:
            Logics.unload_logic(logic)

        if configload is not None:
            Logics.load_logic(logic)

        if add is not None:
            Logics.load_logic(logic)

        if savereload is not None:
            self.logic_save(logic, logics_code)

            # -------
#            self.logger.warning("process_logics_action: self.mylogic = {}".format(str(self.mylogic)))
            config_list = []
            thislogic = Logics.return_logic(logic)
            thislogic.filename
            config_list.append(['filename', thislogic.filename, ''])
            if Utils.is_int(cycle):
                cycle = int(cycle)
            config_list.append(['cycle', cycle, ''])

            if crontab != None:
                l1 = crontab.split(',')
                l2 = []
                for s in l1:
                    l2.append(Utils.strip_quotes(s.strip()))
                crontab = l2
                config_list.append(['crontab', str(crontab), ''])

            if watch != None:
                l1 = watch.split(',')
                l2 = []
                for s in l1:
                    l2.append(Utils.strip_quotes(s.strip()))
                watch = l2
                config_list.append(['watch_item', str(watch), ''])

            self.logger.warning("process_logics_action: config_list = {}".format(str(config_list)))
            Logics.update_config_section(True, logic, config_list)

            # reload and trigger logic
            Logics.unload_logic(logic)
            Logics.load_logic(logic)
            Logics.trigger_logic(logic)
        return


    def logic_save(self, logic, logics_code):
        self.logger.warning("Backend: logics_view_html: Save logic = '{0}'".format(logic))

        if self.updates_allowed:
            if logic in Logics.return_loaded_logics():
                mylogic = Logics.return_logic(logic)

                f = open(mylogic.pathname, 'w')
                f.write(logics_code)
                f.close()


    def logic_findnew(self, loadedlogics):

        _config = {}
        _config.update(self._sh._logics._read_logics(self._sh._logic_conf_basename, self._sh._logic_dir))

        self.logger.info("Backend (logic_findnew): _config = '{}'".format(_config))
        newlogics = []
        for configlogic in _config:
            found = False
            for l in loadedlogics:
                if configlogic == str(l['name']):
                    found = True
            if not found:
                self.logger.info("Backend (logic_findnew): name = {}".format(configlogic))
                if _config[configlogic] != 'None':
                    newlogics.append({'name': configlogic, 'filename': _config[configlogic]['filename'] })
#        self.logger.info("Backend (logic_findnew): newlogics = '{}'".format(newlogics))
        return newlogics


