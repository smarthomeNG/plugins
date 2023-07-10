#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2019-2022 Bernd Meiners                Bernd.Meiners@mail.de
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  This is the executor plugin to run with SmartHomeNG version 1.9 and
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


import urllib
import time
import datetime
import random
import pprint
import json
import logging
import os

from lib.item import Items
from lib.model.smartplugin import SmartPluginWebIf
from lib.model.smartplugin import SmartPlugin


# ------------------------------------------
#    Webinterface of the plugin
# ------------------------------------------

import cherrypy
import csv
from jinja2 import Environment, FileSystemLoader

import sys

class PrintCapture:
    """this class overwrites stdout and stderr temporarily to capture output"""
    def __init__(self):
        self.data = []
    def write(self, s):
        self.data.append(s)
    def __enter__(self):
        sys.stdout = self
        sys.stderr = self
        return self
    def __exit__(self, ext_type, exc_value, traceback):
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

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
        self.logger = plugin.logger
        self.webif_dir = webif_dir
        self.plugin = plugin
        self.items = Items.get_instance()

        self.tplenv = self.init_template_environment()


    @cherrypy.expose
    def index(self, reload=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        tmpl = self.tplenv.get_template('index.html')
        # Setting pagelength (max. number of table entries per page) for web interface
        try:
            pagelength = self.plugin.webif_pagelength
        except Exception:
            pagelength = 100
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        return tmpl.render(p=self.plugin,
                           webif_pagelength=pagelength,
                           items=sorted(self.items.return_items(), key=lambda k: str.lower(k['_path'])),
                           item_count=0)


    @cherrypy.expose
    def get_data_html(self, dataSet=None):
        """
        Return data to update the webpage

        For the standard update mechanism of the web interface, the dataSet to return the data for is None

        :param dataSet: Dataset for which the data should be returned (standard: None)
        :return: dict with the data needed to update the web page.
        """
        if dataSet is None:
            # get the new data
            data = {}

            # data['item'] = {}
            # for i in self.plugin.items:
            #     data['item'][i]['value'] = self.plugin.getitemvalue(i)
            #
            # return it as json the the web page
            # try:
            #     return json.dumps(data)
            # except Exception as e:
            #     self.logger.error("get_data_html exception: {}".format(e))
        return {}


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
    def eval_statement(self, eline, path, reload=None):
        """
        evaluate expression in eline and return the result

        :return: result of the evaluation
        """
        result = ""

        g = {}
        l = { 'sh': self.plugin.get_sh() }
        self.logger.debug(f"eval {eline} (raw) for item path {path}")
        eline = urllib.parse.unquote(eline)
        if path != '':
            try:
                path = self.items.return_item(path)
                eline = path.get_stringwithabsolutepathes(eline, 'sh.', '(')
                eline = path.get_stringwithabsolutepathes(eline, 'sh.', '.property')
                self.logger.debug(f"eval {eline} (unquoted) for item path {path}")
            except Exception as e:
                res = f"Error '{e}' while evaluating"
                result = f"{res}"
                return result

        try:
            if eline:
                res = eval(eline,g,l)
            else:
                res = "Nothing to do"
        except Exception as e:
            res = f"Error '{e}' while evaluating"

        result = f"{res}"
        self.logger.debug(f"{result=}")
        return result

    @cherrypy.expose
    def exec_code(self, eline, reload=None):
        """
        evaluate a whole python block in eline

        :return: result of the evaluation
        """
        result = ""
        stub_logger = Stub(warning=print, info=print, debug=print, error=print, criticl=print, notice=print, dbghigh=print, dbgmed=print, dbglow=print)

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
        self.logger.debug(f"Got request to evaluate {eline} (raw)")
        eline = urllib.parse.unquote(eline)
        self.logger.debug(f"Got request to evaluate {eline} (unquoted)")
        with PrintCapture() as p:
            try:
                if eline:
                    exec(eline,g,l)
                res = ""
            except Exception as e:
                res = f"Error '{e}' while evaluating"

        result = ''.join(p.data) + res
        self.logger.debug(f"{result=}")
        return result

    @cherrypy.expose
    def get_code(self, filename=''):
        """loads and returns the given filename from the defined script path"""
        self.logger.debug(f"get_code called with {filename=}")
        try:
            if (self.plugin.executor_scripts is not None and filename != '') or filename.startswith('examples/'):
                if filename.startswith('examples/'):
                    filepath = os.path.join(self.plugin.get_plugin_dir(),filename)
                    self.logger.debug(f"Getting file from example path {filepath=}")
                else:
                    filepath = os.path.join(self.plugin.executor_scripts,filename)
                    self.logger.debug(f"Getting file from script path {filepath=}")
                code_file = open(filepath)
                data = code_file.read()
                code_file.close()
                return data
        except Exception as e:
            self.logger.error(f"{filepath} could not be read: {e}")
        return f"### {filename} could not be read ###"

    @cherrypy.expose
    def save_code(self, filename='', code=''):
        """save the given code at filename from the defined script path"""
        self.logger.debug(f"save_code called with {filename=}")
        try:
            if self.plugin.executor_scripts is not None and filename != '' and code != '':
                if '/' in filename or '\\' in filename or '..' in filename:
                    raise ValueError("Special Characters not allowed in filename")
                if (filename[-3:] != '.py'):
                    filename += '.py'
                filepath = os.path.join(self.plugin.executor_scripts,filename)
                self.logger.debug(f"{filepath=}")
                with open(filepath, "w") as code_file:
                    code_file.write(code)
                return f"{filename} was saved"
        except Exception as e:
            self.logger.error(f"{filepath} could not be saved, {e}")
        return f"{filename} could not be saved"

    @cherrypy.expose
    def delete_file(self, filename=''):
        """deletes the file with given filename from the defined script path"""
        self.logger.debug(f"delete_file called with {filename=}")
        try:
            if self.plugin.executor_scripts is not None and filename != '':
                filepath = os.path.join(self.plugin.executor_scripts,filename)
                if os.path.exists(filepath) and os.path.isfile(filepath):
                    os.remove(filepath)
                    self.logger.debug(f"{filepath} successfully deleted")
                    return f"{filepath} successfully deleted"
                else:
                    self.logger.debug(f"{filepath} was not deleted")
        except Exception as e:
            self.logger.error(f"{e}: {filepath} could not be deleted")
        return f"### {filename} could not be deleted ###"


    @cherrypy.expose
    def get_filelist(self):
        """returns all filenames from the defined script path with suffix ``.py``, newest first"""
        files = []
        files2 = []
        subdir = "{}/examples".format(self.plugin.get_plugin_dir())
        self.logger.debug(f"list files in plugin examples {subdir}")
        mtime = lambda f: os.stat(os.path.join(subdir, f)).st_mtime
        files = list(reversed(sorted(os.listdir(subdir), key=mtime)))
        files = [f for f in files if os.path.isfile(os.path.join(subdir,f))]
        files = ["examples/{}".format(f) for f in files if f.endswith(".py")]
        #files = '\n'.join(f for f in files)
        self.logger.debug(f"Examples Scripts {files}")
        if self.plugin.executor_scripts is not None:
            subdir = self.plugin.executor_scripts
            self.logger.debug(f"list files in {subdir}")
            files2 = list(reversed(sorted(os.listdir(subdir), key=mtime)))
            files2 = [f for f in files2 if os.path.isfile(os.path.join(subdir,f))]
            files2 = [f for f in files2 if f.endswith(".py")]
            #files = '\n'.join(f for f in files)
            self.logger.debug(f"User scripts {files2}")

        return json.dumps(files2 + files)


    @cherrypy.expose
    def get_autocomplete(self):
        _sh = self.plugin.get_sh()
        plugins = _sh.plugins.get_instance()
        plugin_list = []
        for x in plugins.return_plugins():
          if isinstance(x, SmartPlugin):
            plugin_config_name = x.get_configname()
            if x.metadata is not None:
              api = x.metadata.get_plugin_function_defstrings(with_type=True, with_default=True)
              if api is not None:
                for function in api:
                  plugin_list.append("sh."+plugin_config_name + "." + function)


        myItems = _sh.return_items()
        itemList = []
        for item in myItems:
          itemList.append("sh."+str(item.property.path)+"()")
        retValue = {'items':itemList,'plugins':plugin_list}
        return (json.dumps(retValue))
