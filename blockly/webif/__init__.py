#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2016-     Oliver Hinckel                  github@ollisnet.de
#  Based on ideas of sqlite plugin by Marcus Popp marcus@popp.mx
#########################################################################
#  This file is part of SmartHomeNG.
#
#  Sample Web Interface for new plugins to run with SmartHomeNG version 1.4
#  and upwards.
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

import datetime
import time
import os
import json

from lib.item import Items
from lib.model.smartplugin import SmartPluginWebIf
from lib.logic import Logics          # für update der /etc/logic.yaml
from lib.logic import Logic           # für reload (bytecode)
from lib.utils import Utils
from ..utils import *

# ------------------------------------------
#    Webinterface of the plugin
# ------------------------------------------

import cherrypy
import csv
from jinja2 import Environment, FileSystemLoader

class WebInterface(SmartPluginWebIf):
    logics = None

    logicname = ''
    logic_filename = ''
    cmd = ''
    edit_redirect = ''

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
        self.plugininstance = plugin
        self._sh = self.plugininstance.get_sh()
        self._sh_dir = self._sh.base_dir
        self._section_prefix = self.plugininstance._parameters.get('section_prefix','')
        self.logger.debug("WebInterface: section_prefix = {}".format(self._section_prefix))
        self.logicname = ''
        self.logic_filename = ''

        self.tplenv = self.init_template_environment()

    def html_escape(self, str):
        return html_escape(str)


    @cherrypy.expose
    def index(self):

        return self.index_html()

    @cherrypy.expose
    def index_html(self, cmd='', filename='', logicname='', v=0):

        self.logger.info("index_html: cmd = '{}', filename = '{}', logicname = '{}'".format(cmd, filename, logicname))
        if self.edit_redirect != '':
            self.edit_html(cmd='edit', logicname=self.edit_redirect)

        if self.logics is None:
            self.logics = Logics.get_instance()

        cherrypy.lib.caching.expires(0)

        if cmd == '' and filename == '' and logicname == '':
            cmd = self.cmd
            if cmd == '':
                cmd = 'new'

        self.cmd = cmd.lower()
        self.logger.info("index_html: cmd = {}, filename = {}, logicname = {}".format(cmd, filename, logicname))
        if self.cmd == '':
#            self.logic_filename = ''
            self.logicname = ''
        elif self.cmd == 'new':
            self.logic_filename = 'new'
            self.logicname = ''
        elif self.cmd == 'edit' and filename != '':
            self.logic_filename = filename
            self.logicname = logicname
        self.logger.info("index_html: self.logicname = '{}', self.logic_filename = '{}'".format(self.logicname, self.logic_filename))
        language = self._sh.get_defaultlanguage()

        tmpl = self.tplenv.get_template('blockly.html')
        return tmpl.render(smarthome=self._sh,
                           p=self.plugin,
                           dyn_sh_toolbox=self._DynToolbox(self._sh),
                           cmd=self.cmd,
                           logicname=logicname,
                           lang=language,
                           timestamp=str(time.time()))


    @cherrypy.expose
    def edit_html(self, cmd='', filename='', logicname='', v=0):

        if self.logics is None:
            self.logics = Logics.get_instance()

        cherrypy.lib.caching.expires(0)

        if cmd == '' and filename == '' and logicname == '':
            cmd = self.cmd
            if cmd == '':
                cmd = 'new'

        self.cmd = cmd.lower()
        self.logger.info("edit_html: cmd = {}, filename = {}, logicname = {}".format(cmd, filename, logicname))
        if self.cmd == '':
#            self.logic_filename = ''
            self.logicname = ''
        elif self.cmd == 'new':
            self.logic_filename = 'new'
            self.logicname = ''
        elif self.cmd == 'edit' and filename != '':
            self.logic_filename = filename
            self.logicname = logicname
        self.logger.info("edit_html: self.logicname = '{}', self.logic_filename = '{}'".format(self.logicname, self.logic_filename))
        language = self._sh.get_defaultlanguage()

        tmpl = self.tplenv.get_template('blockly.html')
        return tmpl.render(smarthome=self._sh,
                           p=self.plugin,
                           dyn_sh_toolbox=self._DynToolbox(self._sh),
                           cmd=self.cmd,
                           logicname=logicname,
                           lang=language,
                           timestamp=str(time.time()))


    def _DynToolbox(self, sh):
        mytree = self._build_tree()
        return mytree + "<sep>-</sep>\n"


    def _build_tree(self):
        # Get top level items
        toplevelitems = []
        allitems = sorted(self._sh.return_items(), key=lambda k: str.lower(k['_path']), reverse=False)
        for item in allitems:
            if item._path.find('.') == -1:
                if item._path not in ['env_daily', 'env_init', 'env_loc', 'env_stat']:
                    toplevelitems.append(item)

        xml = '\n'
        for item in toplevelitems:
            xml += self._build_treelevel(item)
#        self.logger.info("log_tree #  xml -> '{}'".format(str(xml)))
        return xml


    def _build_treelevel(self, item, parent='', level=0):
        """
        Builds one tree level of the items

        This methods calls itself recursively while there are further child items
        """
        childitems = sorted(item.return_children(), key=lambda k: str.lower(k['_path']), reverse=False)

        name = remove_prefix(item._path, parent+'.')
        if childitems != []:
            xml = ''
            if (item.type() != 'foo') or (item() != None):
#                self.logger.info("item._path = '{}', item.type() = '{}', item() = '{}', childitems = '{}'".format(item._path, item.type(), str(item()), childitems))
                xml += self._build_leaf(name, item, level+1)
                xml += ''.ljust(3*(level)) + '<category name="{0} ({1})">\n'.format(name, len(childitems)+1)
            else:
                xml += ''.ljust(3*(level)) + '<category name="{0} ({1})">\n'.format(name, len(childitems))
            for grandchild in childitems:
                xml += self._build_treelevel(grandchild, item._path, level+1)

            xml += ''.ljust(3*(level)) + '</category>  # name={}\n'.format(item._path)
        else:
            xml = self._build_leaf(name, item, level)
        return xml


    def _build_leaf(self, name, item, level=0):
        """
        Builds the leaf information for an entry in the item tree
        """
#        n = item._path.title().replace('.','_')
        n = item._path
        xml = ''.ljust(3*(level)) + '<block type="sh_item_obj" name="' + name + '">\n'
        xml += ''.ljust(3*(level+1)) + '<field name="N">' + n + '</field>>\n'
        xml += ''.ljust(3*(level+1)) + '<field name="P">' + item._path + '</field>>\n'
        xml += ''.ljust(3*(level+1)) + '<field name="T">' + item.type() + '</field>>\n'
        xml += ''.ljust(3*(level)) + '</block>\n'
        return xml


    @cherrypy.expose
    def blockly_close_editor(self, content=''):
        self.logger.warning("blockly_close_editor: content = '{}'".format(content))

        self.logic_filename = ''
        return


    @cherrypy.expose
    def blockly_load_logic(self, uniq_param=''):
        self.logger.info("blockly_load_logic: self.logicname = '{}', self.logic_filename = '{}'".format(self.logicname, self.logic_filename))
        if self.logicname == '' and self.edit_redirect == '':
            if self.logic_filename == 'new':
                fn_xml = self.plugininstance.path_join( self.webif_dir, 'templates') + '/' + "new.blockly"
            else:
                fn_xml = self._sh._logic_dir + "blockly_logics.blockly"
        else:
            if self.logic_filename == '':
                fn_xml = self.plugininstance.path_join( self.webif_dir, 'templates') + '/' + "new.blockly"
            else:
                fn_xml = self._sh._logic_dir + self.logic_filename
        self.logger.info("blockly_load_logic: fn_xml = {}".format(fn_xml))
        return cherrypy.lib.static.serve_file(fn_xml, content_type='application/xml')


    def blockly_update_config(self, code, name=''):
        """
        Fill configuration section in /etc/logic.yaml from header lines in generated code

        Method is called from blockly_save_logic()

        :param code: Python code of the logic
        :param name: name of configuration section, if ommited, the section name is read from the source code
        :type code: str
        :type name: str
        """
        section = ''
        active = False
        config_list = []
        for line in code.splitlines():
            if (line.startswith('#comment#')):
                if config_list == []:
                    sc, fn, ac, fnco = line[9:].split('#')
                    fnk, fnv = fn.split(':')
                    ack, acv = ac.split(':')
                    active = Utils.to_bool(acv.strip(), False)
                    if section == '':
                        section = sc;
                        self.logger.info("blockly_update_config: #comment# section = '{}'".format(section))
                    config_list.append([fnk.strip(), fnv.strip(), fnco])
            elif line.startswith('#trigger#'):
                sc, fn, tr, co = line[9:].split('#')
                trk, trv = tr.split(':')
                if config_list == []:
                    fnk, fnv = fn.split(':')
                    fnco = ''
                    config_list.append([fnk.strip(), fnv.strip(), fnco])
                if section == '':
                    section = sc;
                    self.logger.info("blockly_update_config: #trigger# section = '{}'".format(section))
                config_list.append([trk.strip(), trv.strip(),co])
            elif line.startswith('"""'):    # initial .rst-comment reached, stop scanning
                break
            else:                           # non-metadata lines between beginning of code and initial .rst-comment
                pass

        if section == '':
            section = name
        if self._section_prefix != '':
            section = self._section_prefix + section
        self.logger.info("blockly_update_config: section = '{}'".format(section))

        self.logics.update_config_section(active, section, config_list)


    def pretty_print_xml(self, xml_in):
        import xml.dom.minidom

        xml = xml.dom.minidom.parseString(xml_in)
        xml_out = xml.toprettyxml()
        return xml_out


    @cherrypy.expose
    def blockly_save_logic(self, py, xml, name):
        """
        Save the logic - Saves the Blocky xml and the Python code

        :param py:
        :param xml:
        :param name:
        :type py:
        :type xml:
        :type name:
        """
        self._pycode = py
        self._xmldata = xml
        fn_py = self._sh._logic_dir + name.lower() + ".py"
        self.logic_filename = name.lower() + ".blockly"
        fn_xml = self._sh._logic_dir + self.logic_filename
        self.logger.info("blockly_save_logic: saving blockly logic {} as file {}".format(name, fn_py))
        self.logger.debug("blockly_save_logic: SAVE PY blockly logic {} = {}\n '{}'".format(name, fn_py, py))
        with open(fn_py, 'w') as fpy:
            fpy.write(py)
        self.logger.debug("blockly_save_logic: SAVE XML blockly logic {} = {}\n '{}'".format(name, fn_xml, xml))
        xml = self.pretty_print_xml(xml)
        with open(fn_xml, 'w') as fxml:
            fxml.write(xml)

        self.blockly_update_config(self._pycode, name)

        section = name
        if self._section_prefix != '':
            section = self._section_prefix + section

        self.logics.load_logic(section)
        self.edit_redirect = name
