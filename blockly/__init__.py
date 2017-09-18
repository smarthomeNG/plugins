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

import lib.config
from lib.model.smartplugin import SmartPlugin
from lib.utils import Utils
from lib.logic import Logic

from .utils import *


class Blockly(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """
    
    ALLOW_MULTIINSTANCE = False
    PLUGIN_VERSION='1.3a.0'


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

        self.logger.warning('Blockly Webif.__init__')

        self.tplenv = Environment(loader=FileSystemLoader(self.plugininstance.path_join( self.webif_dir, 'templates' ) ))
        self.tplenv.globals['_'] = translate


    def html_escape(self, str):
        return html_escape(str)


    @cherrypy.expose
    def index(self):
        language = self._sh.get_defaultlanguage()
        if language != get_translation_lang():
            self.logger.debug("Blockly: Language = '{}' get_translation_lang() = '{}'".format(language,get_translation_lang()))
            if not load_translation(language):
                self.logger.warning("Blockly: Language '{}' not found, using standard language instead".format(language))

        tmpl = self.tplenv.get_template('blockly.html')
        return tmpl.render(smarthome=self._sh,
                           dyn_sh_toolbox=self._DynToolbox(self._sh), lang=translation_lang)


    @cherrypy.expose
    def index_html(self):

        return self.index()


    def _DynToolbox(self, sh):
        mytree = self._build_tree()
        return mytree + "<sep>-</sep>\n"


    def _build_tree(self):
        # Get top level items
        toplevelitems = []
        allitems = sorted(self._sh.return_items(), key=lambda k: str.lower(k['_path']), reverse=False)
        for item in allitems:
            if item._path.find('.') == -1:
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
                xml += ''.ljust(3*(level)) + '<category name="{0} ({1})">\n'.format(name, len(childitems)+1)
                xml += self._build_leaf(name, item, level+1)
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
        n = item._path.title().replace('.','_')
        xml = ''.ljust(3*(level)) + '<block type="sh_item_obj" name="' + name + '">\n'
        xml += ''.ljust(3*(level+1)) + '<field name="N">' + n + '</field>>\n'
        xml += ''.ljust(3*(level+1)) + '<field name="P">' + item._path + '</field>>\n'
        xml += ''.ljust(3*(level+1)) + '<field name="T">' + item.type() + '</field>>\n'
        xml += ''.ljust(3*(level)) + '</block>\n'
        return xml
        

    @cherrypy.expose
    def logics_blockly_load(self):
        fn_xml = self._sh._logic_dir + "blockly_logics.xml"
        self.logger.warning("logics_blockly_load: fn_xml = {}".format(fn_xml))
        return serve_file(fn_xml, content_type='application/xml')

    @cherrypy.expose
    def logics_blockly_save(self, py, xml):
        self._pycode = py
        self._xmldata = xml
        fn_py = self._sh._logic_dir + "blockly_logics.py"
        fn_xml = self._sh._logic_dir + "blockly_logics.xml"
        self.logger.debug(
            "Blockly: logics_html: SAVE PY blockly logic = {0}\n '{1}'".format(fn_py, py))
        with open(fn_py, 'w') as fpy:
            fpy.write(py)
        self.logger.debug(
            "Blockly: logics_html: SAVE XML blockly logic = {0}\n '{1}'".format(fn_xml, xml))
        with open(fn_xml, 'w') as fxml:
            fxml.write(xml)

        code = self._pycode
        bytecode = compile(code, '<string>', 'exec')
        s = []
        for name in self._sh.scheduler:
            if name.startswith('blockly_runner'):
                # logger.info('Blockly Logics: remove '+ name)
                s.append(name)
        for name in s:
            self._sh.scheduler.remove(name)

        for line in code.splitlines():
            if line and line.startswith('#?#'):
                id, __, trigger = line[3:].partition(':')
                by, __, val = trigger.partition('=')
                by = by.strip()
                val = val.strip()
                # logger.info('Blockly Logics: {} => {} :: {}'.format(id, by, val))
                logic = Logic(self._sh, 'blockly_runner_' + id,
                              {'bytecode': bytecode, })
                if by == 'cycle':
                    self._sh.scheduler.add(
                        'blockly_runner_' + id, logic, prio=3, cron=None, cycle=val)
                    # logger.info('Blockly Logics: cycles     => '+ val)
                elif by == 'crontab':
                    self._sh.scheduler.add(
                        'blockly_runner_' + id, logic, prio=3, cron=val, cycle=None)
                    # logger.info('Blockly Logics: crontabs   => '+ val)
                elif by == 'watchitem':
                    logic.watch_item = val
                    # item = self._sh.return_item(val)
                    # item.add_logic_trigger(logic)
                    # logger.info('Blockly Logics: watchitems => '+ val)
