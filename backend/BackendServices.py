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
#import pwd
import html
import subprocess
import socket
import sys
import threading
import os

import lib.config
import lib.daemon
from lib.logic import Logics
import lib.logic   # zum Test (für generate bytecode -> durch neues API ersetzen)
from lib.model.smartplugin import SmartPlugin
from .utils import *

import lib.item_conversion

class BackendServices:


    def __init__(self):

        self.logger.info("BackendServices __init__ {}".format(''))        


    # -----------------------------------------------------------------------------------
    #    SERVICES
    # -----------------------------------------------------------------------------------

    @cherrypy.expose
    def services_html(self):
        """
        shows a page with info about some services needed by smarthome
        """
        knxd_service = get_process_info("systemctl status knxd.service")
        smarthome_service = get_process_info("systemctl status smarthome.service")
        knxd_socket = get_process_info("systemctl status knxd.socket")

        knxdeamon = ''
        if get_process_info("ps cax|grep eibd") != '':
            knxdeamon = 'eibd'
        if get_process_info("ps cax|grep knxd") != '':
            if knxdeamon != '':
                knxdeamon += ' and '
            knxdeamon += 'knxd'

        sql_plugin = False
        database_plugin = []

        if self._sh.plugins is not None:
            # Only, if plugins are in initialized
            for x in self._sh.plugins:  # TO DO: umstellen auf plugin api
                if x.__class__.__name__ == "SQL":
                    sql_plugin = True
                    break
                elif x.__class__.__name__ == "Database":
                    database_plugin.append(x.get_instance_name())

        service_ctrl = os_service_controllable()
        shng_service = False
        if service_ctrl:
            shng_service = os_service_status('smarthome')

        return self.render_template('services.html',
                                    service_ctrl=service_ctrl, shng_service=shng_service,
                                    knxd_service=knxd_service, knxd_socket=knxd_socket, knxdeamon=knxdeamon,
                                    smarthome_service=smarthome_service, lang=get_translation_lang(), 
                                    sql_plugin=sql_plugin, database_plugin=database_plugin)


    @cherrypy.expose
    def services_shng_restart_html(self):
        """
        Restart shNG service and reshow services page
        """
        if os_service_status('smarthome'):
            os_service_restart('smarthome')
            result = "<strong>" + translate('Restart des Service sollte erfolgen - Bitte warten') + "</strong>"
        else:
            if os.name != 'nt':
                pid = lib.daemon.read_pidfile(self.plugin.get_sh()._pidfile)
                os_restart_shng(pid)
                result = "<strong>" + translate('Restart des Prozesses sollte erfolgen - Bitte warten') + "</strong>"
            else:
                result = "<strong>" + translate('Unter Windows kann derzeit nicht neu gestartet werden') + "</strong>"

        result = result.replace('\n', '<br>')
        return self.render_template('services_shng_restart.html',
                                    msg=result)
        # return '<meta http-equiv="Refresh" content="0; url=./services.html/" />'


    @cherrypy.expose
    def reload_translation_html(self, lang=''):
        if lang != '':
            load_translation(lang)
            self.plugin.get_sh().set_defaultlanguage(lang)
        else:
            load_translation(get_translation_lang())
        return self.main_html()

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

    # -----------------------------------------------------------------------------------

    def strip_empty_lines(self, txt):
        """
        Remove \r from text and remove exessive empty lines from end
        """
        txt = txt.replace('\r','').rstrip()
        while txt.endswith('\n'):
            txt = txt[:-1].rstrip()
        txt += '\n\n'
#        self.logger.warning("strip_empty_lines: txt = {}".format(txt))
        return txt
        

    def append_empty_lines(self, txt, lines):
        """
        Append empty lines until text is 'lines' long
        """
        if len(txt.split('\n')) < lines:
            txt += '\n' * (lines - len(txt.split('\n')) +1)
        return txt

         
    @cherrypy.expose
    def conf_yaml_converter_html(self, convert=None, conf_code=None, yaml_code=None):
        if convert is not None:
            conf_code = self.strip_empty_lines(conf_code)
            yaml_code = ''
            ydata = lib.item_conversion.parse_for_convert(conf_code=conf_code)
            if ydata != None:
                yaml_code = lib.item_conversion.convert_yaml(ydata)

            conf_code = self.append_empty_lines(conf_code, 15)
            yaml_code = self.append_empty_lines(yaml_code, 15)
        else:
            conf_code = self.append_empty_lines('', 15)
            yaml_code = self.append_empty_lines('', 15)
        return self.render_template('conf_yaml_converter.html', conf_code=conf_code, yaml_code=yaml_code)


    # -----------------------------------------------------------------------------------

    @cherrypy.expose
    def yaml_syntax_checker_html(self, check=None, check2=None, yaml_code=None, check_result=None):
        check_result = ''
        output_format = 'yaml'
        if check is not None:
            yaml_code = self.strip_empty_lines(yaml_code)
                
            import lib.shyaml as shyaml
            ydata, estr = shyaml.yaml_load_fromstring(yaml_code, True)

            if estr != '':
                check_result = 'ERROR: \n\n'+ estr
            if ydata != None:
                check_result += lib.item_conversion.convert_yaml(ydata).replace('\n\n', '\n')

            yaml_code = self.append_empty_lines(yaml_code, 15)
            check_result = self.append_empty_lines(check_result, 15)
        elif check2 is not None:
            yaml_code = self.strip_empty_lines(yaml_code)

            import lib.shyaml as shyaml
            ydata, estr = shyaml.yaml_load_fromstring(yaml_code, False)

            if estr != '':
                check_result = 'ERROR: \n\n'+ estr
            if ydata != None:
                import pprint
                check_result += pprint.pformat(ydata)

            yaml_code = self.append_empty_lines(yaml_code, 15)
            check_result = self.append_empty_lines(check_result, 15)
            output_format = 'python'
        else:
            yaml_code = self.append_empty_lines('', 15)
            check_result = self.append_empty_lines('', 15)
        return self.render_template('yaml_syntax_checker.html', yaml_code=yaml_code, check_result=check_result, output_format=output_format)


    # -----------------------------------------------------------------------------------

    @cherrypy.expose
    def eval_syntax_checker_html(self, check=None, eval_code=None, relative_to=''):
        expanded_code = ''
        if check is not None:
            sh = self._sh
            eval_code = eval_code.replace('\r', '').replace('\n', ' ').replace('  ', ' ').strip()
            if relative_to == '':
                expanded_code = eval_code
            else:
                rel_to_item = sh.return_item(relative_to)
                if rel_to_item is not None:
                    expanded_code = rel_to_item.get_stringwithabsolutepathes(eval_code, 'sh.', '(')
                else:
                    expanded_code = "Error: Item {} does not exist!".format(relative_to)
            try:
                value = eval(expanded_code)
            except Exception as e:
                check_result = "Problem evaluating {}: &nbsp; {}".format(expanded_code, e)
            else:
                check_result = value
            eval_code = self.append_empty_lines(eval_code, 5)
        else:
            eval_code = self.append_empty_lines('', 5)
            check_result = ''
        return self.render_template('eval_syntax_checker.html', eval_code=eval_code, expanded_code=expanded_code, relative_to=relative_to, check_result=check_result)


    @cherrypy.expose
    def create_hash_json_html(self, plaintext):
        return json.dumps(create_hash(plaintext))

