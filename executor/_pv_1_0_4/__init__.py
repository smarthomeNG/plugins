#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2019 Bernd Meiners                     Bernd.Meiners@mail.de
#########################################################################
#  This file is part of SmartHomeNG.
#
#  This is the executor plugin to run with SmartHomeNG version 1.4 and
#  upwards.
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

from lib.module import Modules
from lib.item import Items
from lib.model.smartplugin import *
import urllib
import time
import datetime
import random
import pprint
import json

# If a needed package is imported, which might be not installed in the Python environment,
# add it to a requirements.txt file within the plugin's directory


class Executor(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    PLUGIN_VERSION = '1.0.4'

    def __init__(self, sh):
        """
        Initalizes the plugin. The parameters describe for this method are pulled from the entry in plugin.conf.

        """
        from bin.smarthome import VERSION
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        # If an package import with try/except is done, handle an import error like this:

        self.logger.debug("init {}".format(__name__))

        self._init_complete = False

        # Exit if the required package(s) could not be imported
        # if not REQUIRED_PACKAGE_IMPORTED:
        #     self.logger.error("Unable to import Python package '<exotic package>'")
        #     self._init_complete = False
        #     return

        # if plugin should not start without web interface
        if not self.init_webinterface():
            self._init_complete = False
            return

        self.logger.debug("init done")
        self._init_complete = True

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Plugin '{}': run method called".format(self.get_fullname()))
        self.alive = True

    def stop(self):
        """
        Stop method for the plugin
        """
        self.alive = False
        self.logger.debug("Plugin '{}': stop method called".format(self.get_fullname()))

    def parse_item(self, item):
        pass

    def parse_logic(self, logic):
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        pass

    def poll_device(self):
        pass

    def init_webinterface(self):
        """"
        Initialize the web interface for this plugin

        This method is only needed if the plugin is implementing a web interface
        """
        try:
            self.mod_http = Modules.get_instance().get_module('http')
        except:
            self.mod_http = None
        if self.mod_http == None:
            self.logger.error("Not initializing the web interface")
            return False

        import sys
        if not "SmartPluginWebIf" in list(sys.modules['lib.model.smartplugin'].__dict__):
            self.logger.warning("Web interface needs SmartHomeNG v1.5 and up. Not initializing the web interface")
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

import sys

class PrintCapture:
    def __init__(self):
        self.data = []
    def write(self, s):
        self.data.append(s)
    def __enter__(self):
        sys.stdout = self
        return self
    def __exit__(self, ext_type, exc_value, traceback):
        sys.stdout = sys.__stdout__

class Stub():
    def __init__(self, *args, **kwargs):
        print(args)
        print(kwargs)
        for k,v in kwargs.items():
            setattr(self, k, v)

# e.g. logger = Stub(warning=print, info=print, debug=print)


class WebInterface(SmartPluginWebIf):

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
        self.itemsApi = Items.get_instance()
        self.tplenv = self.init_template_environment()

    @cherrypy.expose
    def index(self, reload=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        tmpl = self.tplenv.get_template('index.html')
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        return tmpl.render(p=self.plugin)

    """
    According to SmartHomeNG documentation the following modules are loaded for the
    logic environment:
    - sys
    - os
    - time
    - datetime
    - random
    - ephem
    - Queue
    - subprocess

    The usage of sys and os is a potential risk for eval and exec as they can remove files in reach of SmartHomeNG user.
    There should be however no need for ephem, Queue or subprocess
    """


    @cherrypy.expose
    def evaluate(self, eline, path, reload=None):
        """
        evaluate expression in eline and return the result

        :return: result of the evaluation
        """
        result = ""

        g = {}
        l = { 'sh': self.plugin.get_sh() }
        self.logger.debug("Got request to evaluate {} (raw) for item path {}".format(eline, path))
        eline = urllib.parse.unquote(eline)
        if path != '':
            try:
                path = self.itemsApi.return_item(path)
                eline = path.get_stringwithabsolutepathes(eline, 'sh.', '(')
                eline = path.get_stringwithabsolutepathes(eline, 'sh.', '.property')
                self.logger.debug("Got request to evaluate {} (unquoted)".format(eline))
            except Exception as e:
                res = "Error '{}' while evaluating".format(e)
                result = "{}".format(res)
                return result

        try:
            if eline:
                res = eval(eline,g,l)
            else:
                res = "Nothing to do"
        except Exception as e:
            res = "Error '{}' while evaluating".format(e)

        #result = "{} returns {}".format(eline,res)
        result = "{}".format(res)
        return result

    @cherrypy.expose
    def evaluatetext(self, eline, reload=None):
        """
        evaluate a whole python block in eline

        :return: result of the evaluation
        """
        result = ""
        import json
        import pprint
        stub_logger = Stub(warning=print, info=print, debug=print, error=print)

        g = {}
        l = { 'sh': self.plugin.get_sh(),
            'time': time,
            'datetime': datetime,
            'random': random,
            'json': json,
            'pprint': pprint,
            'logger': stub_logger,
            'logging': logging
            }
        self.logger.warning("Got request to evaluate {} (raw)".format(eline))
        eline = urllib.parse.unquote(eline)
        self.logger.warning("Got request to evaluate {} (unquoted)".format(eline))
        with PrintCapture() as p:
            try:
                if eline:
                    exec(eline,g,l)
                res = ""
            except Exception as e:
                res = "Error '{}' while evaluating".format(e)

        return ''.join(p.data) + res
