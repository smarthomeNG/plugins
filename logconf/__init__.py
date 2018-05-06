#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2018-       Martin Sinn                         m.sinn@gmx.de
#########################################################################
#  Free for non-commercial use
#
#  Plugin for the software SmartHomeNG, which allows to get weather
#  information from wunderground.com.
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
#########################################################################

from lib.module import Modules
from lib.item import Items
from lib.logic import Logics
from lib.model.smartplugin import *


class Logconf(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """
    
    PLUGIN_VERSION='1.5.0'

    def __init__(self, sh, *args, **kwargs):
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

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        #   self.param1 = self.get_parameter_value('param1')
        
        # cycle time in seconds, only needed, if hardware/interface needs to be 
        # polled for value changes (maybe you want to make it a plugin parameter?)
        self._cycle = 60

        # Initialization code goes here

        # On initialization error use:
        #   self._init_complete = False
        #   return

        # The following part of the __init__ method is only needed, if a webinterface is being implemented:
        
        # if plugin should start even without web interface
        self.init_webinterface()

        # if plugin should not start without web interface
        # if not self.init_webinterface():
        #     self._init_complete = False
            
        return


    def run(self):
        """
        Run method for the plugin
        """        
        self.logger.debug("Plugin '{}': run method called".format(self.get_fullname()))
        # setup scheduler for device poll loop
        self.scheduler_add(__name__, self.poll_device, cycle=self._cycle)
        # self.sh.scheduler.add(__name__, self.poll_device, cycle=self._cycle)   # for shNG before v1.4

        self.alive = True
        # if you need to create child threads, do not make them daemon = True!
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
        if self.has_iattr(item.conf, 'foo_itemtag'):
            self.logger.debug("Plugin '{}': parse item: {}".format(self.get_fullname(), item))

        # todo
        # if interesting item for sending values:
        #   return self.update_item


    def parse_logic(self, logic):
        """
        Default plugin parse_logic method
        """
        if 'xxx' in logic.conf:
            # self.function(logic['name'])
            pass


    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Item has been updated
        
        This method is called, if the value of an item has been updated by SmartHomeNG.
        It should write the changed value out to the device (hardware/interface) that 
        is managed by this plugin.
        
        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        if caller != self.get_shortname():
            # code to execute, only if the item has not been changed by this this plugin:
            logger.info("Update item: {}, item has been changed outside this plugin".format(item.id()))



            if self.has_iattr(item.conf, 'foo_itemtag'):
                self.logger.debug("Plugin '{}': update_item was called with item '{}' from caller '{}', source '{}' and dest '{}'".format(self.get_fullname(), item, caller, source, dest))
            pass


    def poll_device(self):
        """
        Polls for updates of the device
        
        This method is only needed, if the device (hardware/interface) does not propagate
        changes on it's own, but has to be polled to get the actual status.
        It is called by the scheduler.
        """
        # # get the value from the device
        # device_value = ...
        #
        # # find the item(s) to update:
        # for item in self.sh.find_items('...'):
        #
        #     # update the item
        #     item(device_value, self.get_shortname())
        pass


    def init_webinterface(self):
        """"
        Initialize the web interface for this plugin

        This method is only needed if the plugin is implementing a web interface
        """
        try:
            self.mod_http = Modules.get_instance().get_module('http')   # try/except to handle running in a core version that does not support modules
        except:
             self.mod_http = None
        if self.mod_http == None:
            self.logger.error("Plugin '{}': Not initializing the web interface".format(self.get_shortname()))
            return False
        
        import sys
        if not "SmartPluginWebIf" in list(sys.modules['lib.model.smartplugin'].__dict__):
            self.logger.warning("Plugin '{}': Web interface needs SmartHomeNG v1.5 and up. Not initializing the web interface".format(self.get_shortname()))
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
                                     description='')
                                   
        return True


# ------------------------------------------
#    Webinterface of the plugin
# ------------------------------------------

import cherrypy
from jinja2 import Environment, FileSystemLoader

import shutil

import lib.shyaml as shyaml
from lib.constants import YAML_FILE


class WebInterface(SmartPluginWebIf):

    logging_config = None
    

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
        self.tplenv = self.init_template_environment()

        # try to get API handles
        self.items = Items.get_instance()
        self.logics = Logics.get_instance()

        self._etc_dir = self.plugin.get_sh()._etc_dir
        

    def create_backupfile(self, filename):

        count = 0
        scount = ''
        
        self.logger.warning("create_backupfile: filename={}".format(filename+YAML_FILE))
        if os.path.isfile(filename+YAML_FILE):
            while os.path.isfile(filename+YAML_FILE+'.backup'+scount) and count <50:
                self.logger.warning("create_backupfile: filename={}".format(filename+YAML_FILE))
                count += 1
                scount = str(count+100)[1:]
            shutil.copy2(filename+YAML_FILE, filename+YAML_FILE+'.backup'+scount)
        return
        

    def save_logging_config(self):
        """
        Save dict to logging.yaml
        """
        if self.logging_config is not None:
            conf_filename = os.path.join(self._etc_dir, 'logging') 
            shyaml.yaml_save_roundtrip(conf_filename, self.logging_config, create_backup=False)
        return
        
        
    def load_logging_config(self):
        """
        Load config from logging.yaml to a dict
        
        If logging.yaml does not contain a 'shng_version' key, a backup is created
        """
        conf_filename = os.path.join(self._etc_dir, 'logging') 
        self.logging_config = shyaml.yaml_load_roundtrip(conf_filename)
        self.logger.warning("load_logging_config: shng_version={}".format(self.logging_config.get('shng_version', None)))

        if self.logging_config.get('shng_version', None) is None:
            self.create_backupfile(conf_filename)
            self.logging_config['shng_version'] = 'x'
            self.save_logging_config()

        return
        
    
    @cherrypy.expose
    def index(self, reload=None):
        """
        Build index for cherrypy
        
        Render the template and return the html file to be delivered to the browser
            
        :return: contents of the template after beeing rendered 
        """
        return '<meta http-equiv="refresh" content="0; url=index.html" />'

        

    @cherrypy.expose
    def index_html(self, reload=None, logger=None, level=None, fromtab=None):
        """
        Build index.html for cherrypy
        
        Render the template and return the html file to be delivered to the browser
            
        :return: contents of the template after beeing rendered 
        """
        if self.logging_config is None:
            self.load_logging_config()

        if level is not None:
            self.logger.warning("index.html: reload={}; logger={}, level={}".format(reload, logger, level))
            lg = logging.getLogger(logger)
            try:
                oldlevel = self.logging_config['loggers'][logger]['level']
            except:
                oldlevel = None
            if oldlevel != None:
                lg.setLevel(level)
                self.logger.warning(" - old level={}".format(oldlevel))
                self.logging_config['loggers'][logger]['level'] = level
                self.save_logging_config()
        
        if fromtab is not None:
            starttab=int(fromtab)
        else:
            starttab=1
            

        # get API handles that were unavailable during __init__
        if self.items is None:
            self.items = Items.get_instance()
        if self.logics is None:
            self.logics = Logics.get_instance()

        logging_config = self.logging_config

        logging_config = shyaml.yaml_dump_roundtrip(logging_config)
        logging_config = logging_config.replace('\n','<br>').replace(' ','&nbsp;')


         
        plgitems = []
        for item in self.items.return_items():
            if ('visu_acl' in item.conf):
                plgitems.append(item)

        plglogics = []
        for logic in self.logics.return_logics():
            plglogics.append(self.logics.get_logic_info(logic))
        
        tmpl = self.tplenv.get_template('index.html')
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        return tmpl.render(p=self.plugin, sh=self.plugin.get_sh(), logging=logging,
                           start_tab=starttab,
                           logging_config=logging_config,
                           items=sorted(plgitems, key=lambda k: str.lower(k['_path'])),
                           logics=sorted(plglogics, key=lambda k: str.lower(k['name'])),
                          )




        tmpl = self.tplenv.get_template('index.html')
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        return tmpl.render(p=self.plugin)

