#!/usr/bin/env python3
# -*- coding: utf8 -*-
#########################################################################
# Copyright 2016-       Martin Sinn                         m.sinn@gmx.de
#                       René Frieß                  rene.friess@gmail.com
#                       Dirk Wallmeier                dirk@wallmeier.info
#########################################################################
#  Blockly plugin for SmartHomeNG
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

import logging
import socket
import time

import collections
import ast

import lib.config
from lib.model.smartplugin import SmartPlugin
from lib.utils import Utils
from lib.logic import Logics          # für update der /etc/logic.yaml
from lib.logic import Logic           # für reload (bytecode)
#import lib.logic as logics

from .utils import *

import lib.shyaml as shyaml
#from lib.constants import (YAML_FILE, CONF_FILE)


class Blockly(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """
    
    ALLOW_MULTIINSTANCE = False
    PLUGIN_VERSION='1.4.0'


    def __init__(self, sh, *args, **kwargs):
        """
        Initalizes the plugin. The parameters describe for this method are pulled from the entry in plugin.conf.

        :param sh:  **Deprecated**: The instance of the smarthome object. For SmartHomeNG versions **beyond** 1.3: **Don't use it**! Use the method self.get_sh() instead
        """
#        self.logger = SmartPluginLogger(__name__, self)
        self.logger = logging.getLogger(__name__)
        self.logger.debug('Blockly.__init__')
        
        # attention:
        # if your plugin runs standalone, sh will likely be None so do not rely on it later or check it within your code
        
#        self._init_complete = False
#        return

        # Initialization code goes here

        self.init_webinterface()


    def run(self):
        """
        Run method for the plugin
        """        
        self.logger.debug("Plugin '{}': run method called".format(self.get_shortname()))
        self.alive = True
        # if you want to create child threads, do not make them daemon = True!
        # They will not shutdown properly. (It's a python bug)


    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Plugin '{}': stop method called".format(self.get_shortname()))
        self.alive = False


    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        The plugin can, corresponding to its attribute keywords, decide what to do with
        the item in future, like adding it to an internal array for future reference
        :param item:    The item to process.
        :return:        If the plugin needs to be informed of an items change you should return a call back function
                        like the function update_item down below. An example when this is needed is the knx plugin
                        where parse_item returns the update_item function when the attribute knx_send is found.
                        This means that when the items value is about to be updated, the call back function is called
                        with the item, caller, source and dest as arguments and in case of the knx plugin the value
                        can be sent to the knx with a knx write function within the knx plugin.
        """
        if self.has_iattr(item.conf, 'foo_itemtag'):
            self.logger.debug("Plugin '{}': parse item: {}".format(self.get_shortname(), item))

        # todo
        # if interesting item for sending values:
        #   return update_item


    def parse_logic(self, logic):
        """
        Default plugin parse_logic method
        """
        if 'xxx' in logic.conf:
            # self.function(logic['name'])
            pass


    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Write items values
        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        # todo 
        # change 'foo_itemtag' into your attribute name
        if item():
            if self.has_iattr(item.conf, 'foo_itemtag'):
                self.logger.debug("Plugin '{}': update_item ws called with item '{}' from caller '{}', source '{}' and dest '{}'".format(self.get_shortname(), item, caller, source, dest))
            pass

        # PLEASE CHECK CODE HERE. The following was in the old skeleton.py and seems not to be 
        # valid any more 
        # # todo here: change 'plugin' to the plugin name
        # if caller != 'plugin':  
        #    logger.info("update item: {0}".format(item.id()))


    def init_webinterface(self):
        """"
        Initialize the web interface for this plugin

        This method is only needed if the plugin is implementing a web interface
        """
        self.mod_http = self.get_module('http')
        if self.mod_http == None:
            self.logger.error("Not initializing the web interface")
            return
        self.logger.info("Using http-module for web interface")
        
        # set application configuration for cherrypy
        webif_dir = self.path_join(self.get_plugin_dir(), 'webif')
        self.logger.info("webif_dir = '{}'".format(webif_dir))
        config = {
            '/': {
                'tools.staticdir.root': webif_dir,
            },
            '/static': {
                'tools.staticdir.on': True,
                'tools.staticdir.dir': 'static'
            }
        }
        
        # Register the web interface as a cherrypy app
        self.mod_http.register_webif(WebInterface(webif_dir, self), 
                                     self.get_shortname(), 
                                     config, 
                                     self.get_classname(), self.get_instance_name(),
                                     description='Blockly graphical logics editor for SmartHomeNG',
                                     webifname='')
                                   
        return True


# ------------------------------------------
#    Webinterface of the plugin
# ------------------------------------------

import cherrypy
from cherrypy.lib.static import serve_file
from jinja2 import Environment, FileSystemLoader

class WebInterface:

    logicname = ''
    logic_filename = ''
        
    
    def __init__(self, webif_dir, plugin):
        """
        Initialization of instance of class WebInterface
        
        :param webif_dir: directory where the webinterface of the plugin resides
        :param plugin: instance of the plugin
        :type webif_dir: str
        :type plugin: object
        """
        self.logger = logging.getLogger(__name__)
        self.webif_dir = webif_dir
        self.plugininstance = plugin
        self._sh = self.plugininstance.get_sh()
        self._sh_dir = self._sh.base_dir
        self._section_prefix = self.plugininstance._parameters.get('section_prefix','')
        self.logger.debug("WebInterface: section_prefix = {}".format(self._section_prefix))

        self.logger.info('Blockly Webif.__init__')

        self.tplenv = Environment(loader=FileSystemLoader(self.plugininstance.path_join( self.webif_dir, 'templates' ) ))
        self.tplenv.globals['_'] = translate
        
        self.logicname = ''
        self.logic_filename = ''


    def html_escape(self, str):
        return html_escape(str)


    @cherrypy.expose
    def index(self):

        return self.index_html()


#     @cherrypy.expose
#     def index_html(self, cmd='', filename='', logicname='', v=0):
# 
#         self.cmd = cmd.lower()
#         self.logger.info("index_html: cmd = {}, filename = {}, logicname = {}".format(cmd, filename, logicname))
#         if self.cmd == '':
#             self.logic_filename = ''
#             self.logicname = ''
#         elif self.cmd == 'new':
#             self.logic_filename = 'new'
#             self.logicname = ''
#         elif self.cmd == 'edit':
#             self.logic_filename = filename
#             self.logicname = logicname
#         
#         language = self._sh.get_defaultlanguage()
#         if language != get_translation_lang():
#             self.logger.debug("Blockly: Language = '{}' get_translation_lang() = '{}'".format(language,get_translation_lang()))
#             if not load_translation(language):
#                 self.logger.warning("Blockly: Language '{}' not found, using standard language instead".format(language))
# 
#         tmpl = self.tplenv.get_template('blockly.html')
#         return tmpl.render(smarthome=self._sh,
#                            dyn_sh_toolbox=self._DynToolbox(self._sh), 
#                            cmd=self.cmd,
#                            logicname=logicname,
#                            lang=translation_lang)


    @cherrypy.expose
    def index_html(self, cmd='', filename='', logicname='', v=0):

        cherrypy.lib.caching.expires(0)

        if cmd == '' and filename == '' and logicname == '':
            cmd = self.cmd
        self.cmd = cmd.lower()
        self.logger.info("edit_html: cmd = {}, filename = {}, logicname = {}".format(cmd, filename, logicname))
        if self.cmd == '':
            self.logic_filename = ''
            self.logicname = ''
        elif self.cmd == 'new':
            self.logic_filename = 'new'
            self.logicname = ''
        elif self.cmd == 'edit':
            self.logic_filename = filename
            self.logicname = logicname
        self.logger.info("edit_html: self.logicname = '{}', self.logic_filename = '{}'".format(self.logicname, self.logic_filename))

        language = self._sh.get_defaultlanguage()
        if language != get_translation_lang():
            self.logger.debug("Blockly: Language = '{}' get_translation_lang() = '{}'".format(language,get_translation_lang()))
            if not load_translation(language):
                self.logger.warning("Blockly: Language '{}' not found, using standard language instead".format(language))

        tmpl = self.tplenv.get_template('blockly.html')
        return tmpl.render(smarthome=self._sh,
                           dyn_sh_toolbox=self._DynToolbox(self._sh), 
                           cmd=self.cmd,
                           logicname=logicname,
                           timestamp=str(time.time()),
                           lang=translation_lang)


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
    def blockly_load_logic(self):
        self.logger.warning("blockly_load_logic: self.logicname = '{}', self.logic_filename = '{}'".format(self.logicname, self.logic_filename))
        if self.logicname == '':
            if self.logic_filename == 'new':
                fn_xml = self.plugininstance.path_join( self.webif_dir, 'templates') + '/' + "new.blockly"
            else:
                fn_xml = self._sh._logic_dir + "blockly_logics.blockly"
        else:
            fn_xml = self._sh._logic_dir + self.logic_filename
        self.logger.warning("blockly_load_logic: fn_xml = {}".format(fn_xml))
        return serve_file(fn_xml, content_type='application/xml')


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
            else:
                break

        if section == '':
            section = name
        if self._section_prefix != '':
            section = self._section_prefix + section
        self.logger.info("blockly_update_config: section = '{}'".format(section))

        Logics.update_config_section(active, section, config_list)
    
    
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
        fn_py = self._sh._logic_dir + name + ".py"
        fn_xml = self._sh._logic_dir + name + ".blockly"
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
        
        Logics.load_logic(section)
        
