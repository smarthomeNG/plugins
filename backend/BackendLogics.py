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
#import collections
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

    logics = None
    _logicname_prefix = 'logics.'     # prefix for scheduler names

    def __init__(self):

        self.logics = Logics.get_instance()
        self.logger.warning("BackendLogics __init__ self.logics = {}".format(str(self.logics)))
        
        
    def logics_initialize(self):
        """
        Initialize access to logics API and test if Blockly plugin is loaded
        
        This can't be done during __init__, since not all components are loaded/initialized
        at that time.
        """
        if self.logics is not None:
            return
            
        self.logics = Logics.get_instance()
        self.yaml_updates=(self.logics.return_config_type() == '.yaml')

        # find out if blockly plugin is loaded
        if self.blockly_plugin_loaded == None:
            self.blockly_plugin_loaded = False
            for x in self._sh._plugins:
                try:
                    if x.get_shortname() == 'blockly':
                        self.blockly_plugin_loaded = True
                except:
                    pass
        return
        

    # -----------------------------------------------------------------------------------
    #    LOGICS
    # -----------------------------------------------------------------------------------

    def fill_logicdict(self, logicname):
        """
        Returns a dict filled with information of the specified loaded logic
        """
        mylogic = dict()
        loaded_logic = self.logics.return_logic(logicname)
        if loaded_logic is not None:
            mylogic['name'] = loaded_logic.name
            mylogic['enabled'] = loaded_logic.enabled
            mylogic['logictype'] = self.logics.return_logictype(loaded_logic.name)
            mylogic['userlogic'] = self.logics.is_userlogic(loaded_logic.name)
            mylogic['filename'] = loaded_logic.filename
            mylogic['pathname'] = loaded_logic.pathname
            mylogic['cycle'] = ''
            if hasattr(self.logics.return_logic(logicname), 'cycle'):
                mylogic['cycle'] = loaded_logic.cycle
                if mylogic['cycle'] == None:
                    mylogic['cycle'] = ''

            mylogic['crontab'] = ''
            if hasattr(loaded_logic, 'crontab'):
                if loaded_logic.crontab is not None:
#                    mylogic['crontab'] = Utils.strip_quotes_fromlist(str(loaded_logic.crontab))
                    mylogic['crontab'] = Utils.strip_quotes_fromlist(self.list_to_editstring(loaded_logic.crontab))

                mylogic['crontab'] = Utils.strip_square_brackets(mylogic['crontab'])

            mylogic['watch_item'] = ''
            mylogic['watch_item_list'] = []
            if hasattr(loaded_logic, 'watch_item'):
                # Attention: watch_items are always stored as a list in logic object
                mylogic['watch_item'] = Utils.strip_quotes_fromlist(str(loaded_logic.watch_item))
                mylogic['watch_item_list'] = loaded_logic.watch_item

            mylogic['next_exec'] = ''
            if self._sh.scheduler.return_next(self._logicname_prefix+loaded_logic.name):
                mylogic['next_exec'] = self._sh.scheduler.return_next(self._logicname_prefix+loaded_logic.name).strftime('%Y-%m-%d %H:%M:%S%z')
                
            mylogic['last_run'] = ''
            if loaded_logic.last_run():
                mylogic['last_run'] = loaded_logic.last_run().strftime('%Y-%m-%d %H:%M:%S%z')

            mylogic['visu_acl'] = ''
            if hasattr(loaded_logic, 'visu_acl'):
                if loaded_logic.visu_acl != 'None':
                    mylogic['visu_acl'] = Utils.strip_quotes_fromlist(str(loaded_logic.visu_acl))

        return mylogic


    @cherrypy.expose
    def logics_html(self, logic=None, trigger=None, reload=None, enable=None, disable=None, unload=None, add=None, delete=None):
        """
        returns information to display a list of all known logics
        """
        self.logics_initialize()

        # process actions triggerd by buttons on the web page
        logicname=logic
        if trigger is not None:
            self.logics.trigger_logic(logicname)
        elif reload is not None:
            self.logics.load_logic(logicname)            # implies unload_logic()
            self.logics.trigger_logic(logicname)
        elif enable is not None:
            self.logics.enable_logic(logicname)
        elif disable is not None:
            self.logics.disable_logic(logicname)
        elif unload is not None:
            self.logics.unload_logic(logicname)

        elif add is not None:
            self.logics.load_logic(logicname)
            
        elif delete is not None:
            self.logics.delete_logic(logicname)

        # create a list of dicts, where each dict contains the information for one logic
        logics_list = []
        import time
        for ln in self.logics.return_loaded_logics():
            logic = self.fill_logicdict(ln)
            if logic['logictype'] == 'Blockly':
                logic['pathname'] = os.path.splitext(logic['pathname'])[0] + '.blockly'
            logics_list.append(logic)
            self.logger.debug("Backend: logics_html: - logic = {}, enabled = {}, , logictype = {}, filename = {}, userlogic = {}, watch_item = {}".format(str(logic['name']), str(logic['enabled']), str(logic['logictype']), str(logic['filename']), str(logic['userlogic']), str(logic['watch_item'])) )

        newlogics = sorted(self.logic_findnew(logics_list), key=lambda k: k['name'])
        logics_sorted = sorted(logics_list, key=lambda k: k['name'])
        return self.render_template('logics.html', updates=self.updates_allowed, yaml_updates=self.yaml_updates, logics=logics_sorted, newlogics=newlogics, 
                                                   blockly_loaded=self.blockly_plugin_loaded)


    def logic_findnew(self, loadedlogics):
        """
        Find new logics (logics defined in /etc/logic.yaml but not loaded)
        """
        _config = {}
        _config.update(self._sh._logics._read_logics(self._sh._logic_conf_basename, self._sh._logic_dir))

        self.logger.info("logic_findnew: _config = '{}'".format(_config))
        newlogics = []
        for configlogic in _config:
            found = False
            for l in loadedlogics:
                if configlogic == str(l['name']):
                    found = True
            if not found:
                self.logger.info("Backend (logic_findnew): name = {}".format(configlogic))
                if _config[configlogic] != 'None':
                    mylogic = {}
                    mylogic['name'] = configlogic
                    mylogic['userlogic'] = True
                    mylogic['logictype'] = self.logics.return_logictype(mylogic['name'])
                    if mylogic['logictype'] == 'Python':
                        mylogic['filename'] = _config[configlogic]['filename']
                        mylogic['pathname'] = self.logics.get_logics_dir() + mylogic['filename']
                    elif mylogic['logictype'] == 'Blockly':
                        mylogic['filename'] = _config[configlogic]['filename']
                        mylogic['pathname'] = os.path.splitext(self.logics.get_logics_dir() + _config[configlogic]['filename'])[0] + '.blockly'
#                        mylogic['pathname'] = os.path.splitext(_config[configlogic]['filename'])[0] + '.blockly'
                    else:
                        mylogic['filename'] = ''
                    
                    newlogics.append(mylogic)
#        self.logger.info("Backend (logic_findnew): newlogics = '{}'".format(newlogics))
        return newlogics


    # -----------------------------------------------------------------------------------
    #    LOGICS - VIEW
    # -----------------------------------------------------------------------------------

    @cherrypy.expose
    def logics_view_html(self, file_path, logicname, 
                               trigger=None, enable=None, disable=None, save=None, savereload=None, savereloadtrigger=None, 
                               logics_code=None, cycle=None, crontab=None, watch=None, visu_acl=None):
        """
        returns information to display a logic in an editor window
        """
        self.logics_initialize()
        
#        self.logger.info("logics_view_html: logicname = {}, trigger = {}, enable = {}, disable = {}, save = {},  savereload = {},  savereloadtrigger = {}".format( logicname, trigger, enable, disable, save, savereload, savereloadtrigger ))
#        self.logger.info("logics_view_html: logicname = {}, cycle = {}, crontab = {}, watch = {}".format( logicname, cycle, crontab, watch ))

        # process actions triggerd by buttons on the web page
        if trigger is not None:
            self.logics.trigger_logic(logicname)
        elif enable is not None:
            self.logics.enable_logic(logicname)
        elif disable is not None:
            self.logics.disable_logic(logicname)
        elif save is not None:
            self.logic_save_code(logicname, logics_code)
            self.logic_save_config(logicname, cycle, crontab, watch, visu_acl)
        elif savereload is not None:
            self.logic_save_code(logicname, logics_code)
            self.logic_save_config(logicname, cycle, crontab, watch, visu_acl)
            self.logics.load_logic(logicname)
        elif savereloadtrigger is not None:
            self.logic_save_code(logicname, logics_code)
            self.logic_save_config(logicname, cycle, crontab, watch, visu_acl)
            self.logics.load_logic(logicname)
            self.logics.trigger_logic(logicname)

        # assemble data for displaying/editing of a logic
        mylogic = self.fill_logicdict(logicname)

        config_list = self.logics.read_config_section(logicname)
        for config in config_list:
            if config[0] == 'cycle':
                mylogic['cycle'] = config[1]
            if config[0] == 'crontab':
#                mylogic['crontab'] = config[1]
                self.logger.info("logics_view_html: crontab = >{}<".format(config[1]))
                edit_string = self.list_to_editstring(config[1])
                mylogic['crontab'] = Utils.strip_quotes_fromlist(edit_string)
            if config[0] == 'watch_item':
                # Attention: watch_items are always stored as a list in logic object
                edit_string = self.list_to_editstring(config[1])
                mylogic['watch'] = Utils.strip_quotes_fromlist(edit_string)
                mylogic['watch_item'] = Utils.strip_quotes_fromlist(edit_string)
                mylogic['watch_item_list'] = config[1]
            if config[0] == 'visu_acl':
                mylogic['visu_acl'] = config[1]

        if os.path.splitext(file_path)[1] == '.blockly':
            mode = 'xml'
            updates = False
        else:
            mode = 'python'
            updates=self.updates_allowed
            if not 'userlogic' in mylogic:
                mylogic['userlogic'] = True
            if mylogic['userlogic'] == False:
                updates = False
        file_lines = []
        if mylogic != {}:
            file_lines = self.logic_load_code(logicname, os.path.splitext(file_path)[1])

        return self.render_template('logics_view.html', logicname=logicname, thislogic=mylogic, logic_lines=file_lines, file_path=file_path,
                                    updates=updates, yaml_updates=self.yaml_updates, mode=mode)


    # -----------------------------------------------------------------------------------
    #    LOGICS - NEW
    # -----------------------------------------------------------------------------------

    @cherrypy.expose
    def logics_new_html(self, create=None, filename='', logicname=''):
        """
        returns information to display a logic in an editor window
        """
        self.logics_initialize()
        
        self.logger.info("logics_new_html: create = {}, filename = '{}', logicname = '{}'".format(create, filename, logicname))
        
        # process actions triggerd by buttons on the web page
        message = ''
        if create is not None:
            if filename != '':
                if logicname == '':
                    logicname = filename
                filename = filename.lower() + '.py'
                
                if logicname in self.logics.return_defined_logics():
                    message = translate("Der Logikname wird bereits verwendet")
                else:
                    logics_code = '#!/usr/bin/env python3\n' + '# ' + filename + '\n\n'
                    if self.logic_create_codefile(filename, logics_code):
                        self.logic_create_config(logicname, filename)
                        self.logics.load_logic(logicname)
#                        self.logics.disable_logic(logicname)
                        redir = '<meta http-equiv="refresh" content="0; url=logics_view.html?file_path={}&logicname={}" />'.format(self.logics.get_logics_dir()+filename, logicname)
                        return redir
                        
                    else:
                        message = translate("Logik-Datei")+" '"+filename+"' "+translate("existiert bereits")
            else:
                message = translate('Bitte Dateinamen angeben')
                
        filename = os.path.splitext(filename)[0]
        return self.render_template('logics_new.html', message=message, filename=filename, logicname=logicname,
                                    updates=self.updates_allowed, yaml_updates=self.yaml_updates)


    # -----------------------------------------------------------------------------------


    def list_to_editstring(self, l):
        """
        """
        if type(l) is str:
            self.logger.info("list_to_editstring: >{}<  -->  >{}<".format(l, l))
            return l
        
        edit_string = ''
        for entry in l:
            if edit_string != '':
                edit_string += ' | '
            edit_string += str(entry)
        self.logger.info("list_to_editstring: >{}<  -->  >{}<".format(l, edit_string))
        return edit_string
        

    def editstring_to_list(self, param_string):

        if param_string is None:
            return ''
        else:
            l1 = param_string.split('|')
            if len(l1) > 1:
                # string contains a list
                l2 = []
                for s in l1:
                    l2.append(Utils.strip_quotes(s.strip()))
                param_string = l2
            else:
                # string contains a single entry
                param_string = Utils.strip_quotes(param_string)
        return param_string


    def logic_create_config(self, logicname, filename):
        """
        Create a new configuration for a logic
        """
        config_list = []
        config_list.append(['filename', filename, ''])
        config_list.append(['enabled', False, ''])
        self.logics.update_config_section(True, logicname, config_list)
#        self.logics.set_config_section_key(logicname, 'visu_acl', False)
        return
         

    def logic_save_config(self, logicname, cycle, crontab, watch, visu_acl):
        """
        Save configuration data of a logic
        
        Convert input strings to lists (if necessary) and write configuration to /etc/logic.yaml 
        """
        config_list = []
        thislogic = self.logics.return_logic(logicname)
        config_list.append(['filename', thislogic.filename, ''])
        if Utils.is_int(cycle):
            cycle = int(cycle)
            if cycle > 0:
                config_list.append(['cycle', cycle, ''])

        crontab = self.editstring_to_list(crontab)
        if crontab != '':
            config_list.append(['crontab', str(crontab), ''])
                
        watch = self.editstring_to_list(watch)
        if watch != '':
            config_list.append(['watch_item', str(watch), ''])

        self.logics.update_config_section(True, logicname, config_list)
        if visu_acl == '':
            visu_acl = None
#            visu_acl = 'false'
        self.logics.set_config_section_key(logicname, 'visu_acl', visu_acl)
        return
         

    def logic_load_code(self, logicname, code_type='.python'):

        file_lines = []
        if logicname in self.logics.return_loaded_logics():
            mylogic = self.logics.return_logic(logicname)

            if code_type == '.blockly':
                pathname = os.path.splitext(mylogic.pathname)[0] + '.blockly'
            else:
                pathname = mylogic.pathname
                
            fobj = open(pathname)
            for line in fobj:
                file_lines.append(html.escape(line))
            fobj.close()
        return file_lines


    def logic_save_code(self, logicname, logics_code):

        self.logger.info("logic_save_code: type(logics_code) = {}".format(str(type(logics_code))))
        if self.updates_allowed:
            if logicname in self.logics.return_loaded_logics():
                mylogic = self.logics.return_logic(logicname)

                f = open(mylogic.pathname, 'w')
                f.write(logics_code)
                f.close()
        return


    def logic_create_codefile(self, filename, logics_code):

        pathname = self.logics.get_logics_dir() + filename
        if os.path.isfile(pathname):
            return False

        f = open(pathname, 'w')
        f.write(logics_code)
        f.close()

        return True
        
