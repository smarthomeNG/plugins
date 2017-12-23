#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2016-       René Frieß                  rene.friess@gmail.com
#                       Martin Sinn                         m.sinn@gmx.de
#                       Bernd Meiners
#                       Christian Strassburg          c.strassburg@gmx.de
#########################################################################
#  Backend plugin for SmartHomeNG
#
#  It runs with SmartHomeNG version 1.4 and upwards.
#
#  This plugin is free software: you can redistribute it and/or modify
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

import logging

from lib.model.smartplugin import SmartPlugin

from .utils import *

from .BackendSysteminfo import BackendSysteminfo
from .BackendServices import BackendServices
from .BackendItems import BackendItems
from .BackendLogics import BackendLogics
from .BackendSchedulers import BackendSchedulers
from .BackendPlugins import BackendPlugins
from .BackendScenes import BackendScenes
from .BackendThreads import BackendThreads
from .BackendLogging import BackendLogging
from .BackendVisu import BackendVisu



class BackendServer(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """
    
    PLUGIN_VERSION='1.4.9'


    def __init__(self, sh, updates_allowed='True', developer_mode="no", pypi_timeout=5):
        """
        Initalizes the plugin. The parameters describe for this method are pulled from the entry in plugin.conf.

        :param sh:  **Deprecated**: The instance of the smarthome object. For SmartHomeNG versions **beyond** 1.3: **Don't use it**! 
        :param *args: **Deprecated**: Old way of passing parameter values. For SmartHomeNG versions **beyond** 1.3: **Don't use it**!
        :param **kwargs:**Deprecated**: Old way of passing parameter values. For SmartHomeNG versions **beyond** 1.3: **Don't use it**!
        
        If you need the sh object at all, use the method self.get_sh() to get it. There should be almost no need for
        a reference to the sh object any more.
        
        The parameters *args and **kwargs are the old way of passing parameters. They are deprecated. They are imlemented
        to support oder plugins. Plugins for SmartHomeNG v1.4 and beyond should use the new way of getting parameter values:
        use the SmartPlugin method get_parameter_value(parameter_name) instead. Anywhere within the Plugin you can get
        the configured (and checked) value for a parameter by calling self.get_parameter_value(parameter_name). It
        returns the value in the datatype that is defined in the metadata.
        """
        self.logger = logging.getLogger(__name__)

        self.updates_allowed = self.get_parameter_value('updates_allowed')
        self.developer_mode = self.get_parameter_value('developer_mode')
        self.pypi_timeout = self.get_parameter_value('pypi_timeout')
        
        self.language = self.get_sh().get_defaultlanguage()
        if self.language != '':
            if not load_translation(self.language):
                self.logger.warning("Language '{}' not found, using standard language instead".format(self.language))

        if not self.init_webinterface():
            self._init_complete = False
            
        return


    def run(self):
        """
        Run method for the plugin
        """        
        self.logger.debug("Plugin '{}': run method called".format(self.get_fullname()))
        self.alive = True
        # if you want to create child threads, do not make them daemon = True!
        # They will not shutdown properly. (It's a python bug)


    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Plugin '{}': stop method called".format(self.get_fullname()))
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
        pass


    def parse_logic(self, logic):
        """
        Default plugin parse_logic method
        """
        pass


    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Write items values
        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        pass


    def init_webinterface(self):
        """"
        Initialize the web interface for this plugin

        This method is only needed if the plugin is implementing a web interface
        """
        try:
            self.mod_http = self.get_module('http')   # try/except to handle running in a core version that does not support modules
        except:
             self.mod_http = None

        if self.mod_http == None:
            self.logger.error("Plugin '{}': Not initializing the web interface".format(self.get_fullname()))
            return False
        
        # set application configuration for cherrypy
        webif_dir = self.path_join(self.get_plugin_dir(), 'webif')
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
                                     description='Administrationsoberfläche für SmartHomeNG',
                                     webifname='')
                                   
        return True


# ------------------------------------------
#    Webinterface of the plugin
# ------------------------------------------

import os

import cherrypy
from jinja2 import Environment, FileSystemLoader

from lib.logic import Logics
import lib.item_conversion

class WebInterface(BackendSysteminfo, BackendServices, BackendItems, BackendLogics, 
                   BackendSchedulers, BackendPlugins, BackendScenes, BackendThreads, 
                   BackendLogging, BackendVisu):

    blockly_plugin_loaded = None    # None = load state is unknown

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
        self.plugin = plugin
        self.logger.info("{}: Running from '{}'".format(self.__class__.__name__, self.webif_dir))
        
        self.tplenv = Environment(loader=FileSystemLoader(self.plugin.path_join( self.webif_dir, 'templates' ) ))   
        from os.path import basename as get_basename
        self.tplenv.globals['get_basename'] = get_basename
        self.tplenv.globals['is_userlogic'] = Logics.is_userlogic
        self.tplenv.globals['_'] = translate

        self.env = self.tplenv    # because the new naming isn't globally implemented
        
        self.logger = logging.getLogger(__name__)
        self._bs = plugin
        self._sh = plugin.get_sh()
        self.language = plugin.language
        self.updates_allowed = plugin.updates_allowed
        self.developer_mode = plugin.developer_mode
        self.pypi_timeout = plugin.pypi_timeout

        self._sh_dir = self._sh.base_dir
        self.visu_plugin = None
        self.visu_plugin_version = '1.0.0'
        

    def html_escape(self, str):
        """
        escape characters in html
        """
        return html_escape(str)


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
                    "Visu protocol plugin v{} is too old to support backend, please update".format(
                        self.visu_plugin_version))


    def render_template(self, tmpl_name, **kwargs):
        """

        Render a template and add vars needed gobally (for navigation, etc.)
    
        :param tmpl_name: Name of the template file to be rendered
        :param **kwargs: keyworded arguments to use while rendering
        
        :return: contents of the template after beeing rendered 

        """
        self.find_visu_plugin()
        tmpl = self.tplenv.get_template(tmpl_name)
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
        """
        display index page
        """
        return self.render_template('index.html')

    @cherrypy.expose
    def main_html(self):

        return self.render_template('main.html')


    # -----------------------------------------------------------------------------------
    #    DISCLOSURE
    # -----------------------------------------------------------------------------------

    @cherrypy.expose
    def disclosure_html(self):
        """
        display disclosure
        """
        return self.render_template('disclosure.html')

