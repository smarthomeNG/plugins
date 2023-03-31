#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2016- Martin Sinn                              m.sinn@gmx.de
#  Parts Copyright 2012-2013 Marcus Popp                   marcus@popp.mx
#########################################################################
#  This file is part of SmartHomeNG.
#  Visit:  https://github.com/smarthomeNG/
#          https://knx-user-forum.de/forum/supportforen/smarthome-py
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

import logging
import struct

import os
import shutil

import lib.shyaml as shyaml
from lib.utils import Utils
from lib.module import Modules
from lib.model.smartplugin import SmartPlugin

from .webif import WebInterface

from .svgenerator import SmartVisuGenerator
from .svinstallwidgets import SmartVisuInstallWidgets

# to do: copy tplNG files
# implement config parameter to copy/not to copy tplNG files (if dir exist in smartVISU)


#########################################################################

class SmartVisu(SmartPlugin):
    PLUGIN_VERSION="1.8.10"
    ALLOW_MULTIINSTANCE = True

    visu_definition = None
    deprecated_widgets = []
    removed_widgets = []
    deprecated_plugin_widgets = []       # List of plugin-widgets that use deprecated widgets
    removed_plugin_widgets = []          # List of plugin-widgets that use removed widgets
    d_usage = {}
    r_usage = {}


    def __init__(self, sh):

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        #self.logger = logging.getLogger(__name__)
        self._sh = sh

        self.default_acl = self.get_parameter_value('default_acl')
        self.smartvisu_dir = self.get_parameter_value('smartvisu_dir')
        self._generate_pages = self.get_parameter_value('generate_pages')
        self.overwrite_templates = self.get_parameter_value('overwrite_templates')
        self.visu_style = self.get_parameter_value('visu_style').lower()
        if not self.visu_style in ['std','blk']:
            self.visu_style = 'std'
            self.logger.error("smartVISU: Invalid value '" + self.get_parameter_value('visu_style') + "' configured for attribute visu_style in plugin.conf, using '" + str(self.visu_style) + "' instead")
        self._handle_widgets = self.get_parameter_value('handle_widgets')
        self._create_masteritem_file = self.get_parameter_value('create_masteritem_file')
        self.list_deprecated_warnings = self.get_parameter_value('list_deprecated_warnings')
        self.protocol_over_reverseproxy = False
        #self.protocol_over_reverseproxy = self.get_parameter_value('protocol_over_reverseproxy')

        self.smartvisu_version = self.get_smartvisu_version()
        if self.smartvisu_version == '':
            self.logger.error("Could not determine smartVISU version!")
        self.smartvisu_is_configured = self.sv_is_configured()
        self.logger.info(f"sv version={self.smartvisu_version}, sv_is_configured={self.smartvisu_is_configured}")

        self.deprecated_widgets = []
        self.removed_widgets = []
        self.deprecated_plugin_widgets = []  # List of plugin-widgets that use deprecated widgets
        self.removed_plugin_widgets = []  # List of plugin-widgets that use removed widgets
        self.d_usage = {}
        self.r_usage = {}

        self.read_visu_definition()
        self.load_deprecated_info()

        # get instance of websocket module (to enable sv-protocol support)
        try:
            self.mod_websocket = Modules.get_instance().get_module('websocket')
        except:
            self.mod_websocket = None
            self.logger.info("Module 'websocket' could not be initialized.")

        self.payload_smartvisu = None
        if self.mod_websocket is not None:
            self.payload_smartvisu = self.mod_websocket.get_payload_protocol_by_id('sv')
            try:
                self.payload_smartvisu.set_smartvisu_support(protocol_enabled=True, default_acl=self.default_acl, query_definitions=False, series_updatecycle=0, protocol_over_reverseproxy=self.protocol_over_reverseproxy)
            except:
                self.logger.exception("Payload protocol 'smartvisu' of module 'websocket' could not be found.")

        self.port = ''
        self.tls_port = ''
        if self.mod_websocket is not None:
            self.port = str(self.mod_websocket.get_port())
            if self.mod_websocket.get_use_tls():
                self.tls_port = self.mod_websocket.get_tls_port()

        self.init_webinterface(WebInterface)

        return


    def run(self):
        self.alive = True
        if self.smartvisu_dir != '':
            if not os.path.isdir(os.path.join(self.smartvisu_dir, 'pages')):
                self.logger.error("Could not find valid smartVISU directory: {}".format(self.smartvisu_dir))
            else:
                self.logger.info(f"Starting smartVISU v{self.smartvisu_version} handling for visu in {self.smartvisu_dir}")
                if self._handle_widgets:
                    try:
                        sv_iwdg = SmartVisuInstallWidgets(self)
                    except Exception as e:
                        self.logger.exception("SmartVisuInstallWidgets v{}: Exception: {}".format(self.get_smartvisu_version(), e))
                    if self.removed_plugin_widgets != []:
                        self.logger.error("Plugin widgets that need an update now: {}".format(self.removed_plugin_widgets))
                    if self.deprecated_plugin_widgets != []:
                        self.logger.warning("Plugin widgets that should get an update: {}".format(self.deprecated_plugin_widgets))

                # generate pages for smartvisu, if configured to do so and smartvisu is already configured
                if self._generate_pages:
                    if self.smartvisu_is_configured:
                        try:
                            svgen = SmartVisuGenerator(self, self.visu_definition)
                        except Exception as e:
                            self.logger.exception("SmartVisuGenerator: Exception: {}".format(e))

                        wid_list = list(self.r_usage.keys())
                        for wid in wid_list:
                            if self.r_usage[wid] == 0:
                                del (self.r_usage[wid])
                        wid_list = list(self.d_usage.keys())
                        for wid in wid_list:
                            if self.d_usage[wid] == 0:
                                del (self.d_usage[wid])
                        if self.r_usage != {}:
                            self.logger.error("Removed widget usage (used in # sv_widgets): {}".format(self.r_usage))
                        if self.d_usage != {}:
                            self.logger.warning("Deprecated widget usage (used in # sv_widgets): {}".format(self.d_usage))
                    else:
                        self.logger.warning(f"Not generating pages because smartVISU v{self.smartvisu_version} in directory {self.smartvisu_dir} is not yet configured")

                if self._create_masteritem_file:
                    if self.smartvisu_is_configured:
                        self.write_masteritem_file()
                        self.logger.info("Finished smartVISU v{} handling".format(self.smartvisu_version))
                    else:
                        self.logger.warning(f"Not generating item-masterfile because smartVISU v{self.smartvisu_version} in directory {self.smartvisu_dir} is not yet configured")
        # self.stop()


    def stop(self):
        self.alive = False


    def parse_item(self, item):
        # Relative path support (release 1.3 and up)
        item.expand_relativepathes('sv_widget', "'", "'")
        item.expand_relativepathes('sv_widget2', "'", "'")
        item.expand_relativepathes('sv_nav_aside', "'", "'")
        item.expand_relativepathes('sv_nav_aside2', "'", "'")


    def parse_logic(self, logic):
        pass


    def update_item(self, item, caller=None, source=None, dest=None):
        pass


    def read_version_info_php(self):
        v = '?'
        v_major = '?'
        v_minor = '?'
        v_rev = '?'

        if os.path.isfile(os.path.join(self.smartvisu_dir, 'version-info.php')):
            with open(os.path.join(self.smartvisu_dir, 'version-info.php'), 'r') as content_file:
                content = content_file.readlines()
            for l in content:
                line = l.strip('( defin\n;)')
                if line.find('//') > -1:
                    line = line[:line.find('//')]
                if line.startswith("'config_version'"):
                    v = line[len("'config_version'"):].strip(", ';)")
                elif line.startswith("'config_version_major'"):
                    v_major = line[len("'config_version_major'"):].strip(", ';)")
                elif line.startswith("'config_version_minor'"):
                    v_minor = line[len("'config_version_minor'"):].strip(", ';)")
                elif line.startswith("'config_version_revision'"):
                    v_rev = line[len("'config_version_revision'"):].strip(", ';)")

        full_version = v_major + '.' + v_minor + '.' + v_rev
        return full_version

    def get_smartvisu_version(self):
        """
        Determine which smartVISU version is installed in 'smartvisu_dir'

        :return: version
        :rtype: str
        """
        full_version = self.read_version_info_php()
        if full_version != '':
            return full_version

        if os.path.isfile(os.path.join(self.smartvisu_dir, 'version-info.php')):
            content = ''
            with open(os.path.join(self.smartvisu_dir, 'version-info.php'), 'r') as content_file:
                content = content_file.read()
            if content.find('self.full_version') > -1:
                return '2.9'
            if content.find('2.8') > -1:
                return '2.8'

        if os.path.isdir(os.path.join(self.smartvisu_dir, 'dropins')):
            return '2.9 dropins'

        if os.path.isdir(os.path.join(self.smartvisu_dir, 'pages')):
            return '2.7'
        return ''


    def load_deprecated_info(self):
        """
        Load info from smartVISU which widgets have been deprecated or removed
        """
        self.deprecated_widgets = []
        self.removed_widgets = []
        self.deprecated_plugin_widgets = []
        filename = os.path.join(self.smartvisu_dir, 'widgets', 'deprecated.yaml')
        dep_warnings = shyaml.yaml_load(filename, ordered=False, ignore_notfound=True)
        if dep_warnings is None:
            #load deprecated warnings for older versions of smartvisu
            if self.smartvisu_version.startswith('2.9'):
                filename = os.path.join(self.get_plugin_dir(), 'deprecated_29.yaml')
                dep_warnings = shyaml.yaml_load(filename, ordered=False, ignore_notfound=True)
        if dep_warnings is not None:
            self.logger.info("Using deprecated info from file '{}' for smartVISU v{}".format(filename, self.smartvisu_version))
            self.deprecated_widgets = dep_warnings.get('deprecated', [])
            self.removed_widgets = dep_warnings.get('removed', [])

    def test_widget_for_deprecated_widgets(self, filename):
        """
        Method tests if a widget file (of a plugin) uses deprecated/removed widgets
        :param filename: Name of the widget file
        """
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                widget_code = f.read()
                widget_code = widget_code.lstrip('\ufeff')  # remove BOM
        except Exception as e:
            self.logger.error("Could not widget code file '{}': {}".format(filename, e))
            return

        plugin = filename[:filename.find('/sv_widgets')]
        plugin = plugin[plugin.find('/plugins/') + 9:]
        widget = filename[filename.find('/sv_widgets') + 12:]
        if widget.endswith('.html'):
            widget = widget[:-5]

        used_widgets = []
        if self.removed_widgets is not None:
            for widget_name in self.removed_widgets:
                if widget_code.find(widget_name) > -1:
                    used_widgets.append(widget_name)
            if used_widgets != []:
                self.removed_plugin_widgets.append(widget)
                if self.list_deprecated_warnings:
                    self.logger.error("deprecated_widgets ({}): Removed widget(s) {} used in plugin-widget '{}' of plugin '{}'".format(self.smartvisu_version, used_widgets, widget, plugin))

        used_widgets2 = []
        if self.deprecated_widgets is not None:
            for widget_name in self.deprecated_widgets:
                if widget_code.find(widget_name) > -1:
                    used_widgets2.append(widget_name)
            if used_widgets2 != []:
                self.deprecated_plugin_widgets.append(widget)
                if self.list_deprecated_warnings:
                    self.logger.warning("deprecated_widgets ({}): Deprecate widget(s) {} used in plugin-widget '{}' of plugin '{}'".format(self.smartvisu_version, used_widgets2, widget, plugin))

        used_widgets = []
        if self.deprecated_widgets is not None:
            for widget_name in self.deprecated_widgets:
                if widget_code.find(widget_name) > -1:
                    self.deprecated_plugin_widgets.append(widget)
                    used_widgets.append(widget_name)
            if used_widgets != []:
                self.logger.warning("test_widget_for_deprecated_widgets ({}): Deprecated widget(s) {} used in plugin-widget '{}' of plugin '{}'".format(self.smartvisu_version, used_widgets, widget, plugin))
        return

    def test_item_for_deprecated_widgets(self, item):
        """
        Test if a deprecated or removed widget is used in an item
        """
        if self.removed_widgets is not None:
            for widget in self.removed_widgets:
                if self.r_usage.get(widget, None) is None:
                    self.r_usage[widget] = 0
                self.test_item_widget_attribute(item, 'sv_widget', widget, self.r_usage, 'removed')
                self.test_item_widget_attribute(item, 'sv_widget2', widget, self.r_usage, 'removed')
                self.test_item_widget_attribute(item, 'sv_nav_aside', widget, self.r_usage, 'removed')
                self.test_item_widget_attribute(item, 'sv_nav_aside2', widget, self.r_usage, 'removed')

        if self.deprecated_widgets is not None:
            for widget in self.deprecated_widgets:
                if self.d_usage.get(widget, None) is None:
                    self.d_usage[widget] = 0
                self.test_item_widget_attribute(item, 'sv_widget', widget, self.d_usage)
                self.test_item_widget_attribute(item, 'sv_widget2', widget, self.d_usage)
                self.test_item_widget_attribute(item, 'sv_nav_aside', widget, self.d_usage)
                self.test_item_widget_attribute(item, 'sv_nav_aside2', widget, self.d_usage)

        if self.deprecated_plugin_widgets is not None:
            for widget in self.deprecated_plugin_widgets:
                self.test_item_widget_attribute(item, 'sv_widget', widget+'.', None, 'plugin-widget')
                self.test_item_widget_attribute(item, 'sv_widget2', widget+'.', None, 'plugin-widget')
                self.test_item_widget_attribute(item, 'sv_nav_aside', widget+'.', None, 'plugin-widget')
                self.test_item_widget_attribute(item, 'sv_nav_aside2', widget+'.', None, 'plugin-widget')

        return

    def test_item_widget_attribute(self, item, widget_name, dep_widget, usage, level='deprecated'):
        """
        Test if a deprecated or removed widget is used in an item attribute
        """
        if item.conf.get(widget_name, '').find(dep_widget) > -1:
            if usage is not None:
                usage[dep_widget] += 1
            if self.list_deprecated_warnings:
                if level == 'deprecated':
                    self.logger.warning("Deprecated widget used in item {} '{}': '{}'".format(item.id(), widget_name, dep_widget))
                elif level == 'removed':
                    self.logger.error("Removed widget used in item {} '{}': '{}'".format(item.id(), widget_name, dep_widget))
                else:
                    self.logger.error("Plugin-widget that needs update is used in item {} '{}': '{}'".format(item.id(), widget_name, dep_widget))
        return


    def read_visu_definition(self):

        from pprint import pformat

        self.etc_dir = self._sh._etc_dir

        filename = os.path.join(self.etc_dir, 'visu.yaml')
        self.visu_definition = shyaml.yaml_load(filename, ordered=False, ignore_notfound=True)
        return


    def read_from_sv_configini(self, key):
        """
        Read a value from the configuration file of smartVISU

        :param key: key to read from config.ini
        :return: value of the key read
        """
        from configparser import ConfigParser
        #config = ConfigParser()
        #config.read('test.ini')

        filename = os.path.join(self.smartvisu_dir, 'config.ini')
        config_parser = ConfigParser()
        try:
            with open(filename) as stream:
                config_parser.read_string("[dummy_section]\n" + stream.read())
        except Exception as e:

            self.logger.info("smartVISU is not configured (no 'config.ini' file found)")
            return ''

        try:
            value = config_parser.get('dummy_section', key)
        except:
            self.logger.info("smartVISU is not configured (no entry 'pages' in 'config.ini' file found)")
            return ''
        value = Utils.strip_quotes(value)
        self.logger.debug(f"read_from_sv_configini: key={key} -> value={value}")
        return value


    def sv_is_configured(self):
        """
        Test if the smartvisu is configured

        The test is only performed for smartvisu v2.9 abd above

        :return: True, if the smartvisu is configured or the sv-version is v2.8 or below
        """

        if self.smartvisu_version.startswith('2.7') or self.smartvisu_version.startswith('2.8'):
            # Do not perform test on old sv versions
            result = True
            self.logger.warning("Old version, configuration not really tested")
        elif self.smartvisu_version.startswith('2.9') or self.smartvisu_version.startswith('3.'):
            # Test for sv v2.9 and up
            # read config.ini to get the name of the pages directory
            dirname = self.read_from_sv_configini('pages')
            result = (dirname != '')
        else:
            self.logger.warning("Could not determine version of smartVISU in configured directory {self.smartvisu_dir}")
            result = False

        return result


    def write_masteritem_file(self):
        """
        create_master_item.py in smartVISU
        """
        import json
        from lib.item import Items

        # get a list with only the pathes of the items
        items = Items.get_instance()
        items_sorted = sorted(items.return_items(), key=lambda k: str.lower(k['_path']), reverse=False)
        item_list = []
        for item in items_sorted:
            item_list.append(item.property.path + '|' + item.property.type)
        # read config.ini to get the name of the pages directory
        dirname = self.read_from_sv_configini('pages')

        if dirname != '':
            # write json file with list of item pathes
            pagedir_name = os.path.join(self.smartvisu_dir, 'pages', dirname)
            filename = os.path.join(pagedir_name, 'masteritem.json')
            self.logger.debug(f"write_masteritem_file: filename='{filename}'")
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(item_list, f, ensure_ascii=False, indent=4)
                self.logger.info(f"master-itemfile written to smartVISU (to directory {pagedir_name})")
            except:
                self.logger.warning(f"Could not write master-itemfile to smartVISU (to directory {pagedir_name})")
        else:
            self.logger.warning("Master-itemfile not written, because the name of the pages directory could not be read from smartVISU")
        return


    def url(self, url, clientip=''):
        """
        Tell the websocket client (visu) to load a specific url
        """
        if self.mod_websocket is None:
            self.logger.error("Cannot send url to visu because websocket module is not loaded")
            return False

        try:
            result = self.payload_smartvisu.set_visu_url(url, clientip)
        except:
            self.logger.notice("Payload protocol 'smartvisu' of module 'websocket' could not be found.")

        return result


    def return_clients(self):
        """
        Returns connected clients

        :return: list of dicts with client information
        """
        if self.mod_websocket is None:
            return {}

        try:
            client_info = self.payload_smartvisu.get_visu_client_info()
            self.logger.info(f"client_info = {client_info}")
        except:
            self.logger.notice("Payload protocol 'smartvisu' of module 'websocket' could not be found.")
            client_info = {}

        return client_info
