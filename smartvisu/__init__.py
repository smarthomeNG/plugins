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
from lib.model.smartplugin import SmartPlugin

from .svgenerator import SmartVisuGenerator
from .svinstallwidgets import SmartVisuInstallWidgets

# to do: copy tplNG files
# implement config parameter to copy/not to copy tplNG files (if dir exist in smartVISU)


#########################################################################

class SmartVisu(SmartPlugin):
    PLUGIN_VERSION="1.8.0"
    ALLOW_MULTIINSTANCE = True

    visu_definition = None
    deprecated_widgets = []
    removed_widgets = []
    deprecated_plugin_widgets = []       # List of plugin-widgets that use deprecated widgets
    removed_plugin_widgets = []          # List of plugin-widgets that use removed widgets
    d_usage = {}
    r_usage = {}


    def __init__(self, sh):
        self.logger = logging.getLogger(__name__)
        self._sh = sh

        self.smartvisu_dir = self.get_parameter_value('smartvisu_dir')
        self._generate_pages = self.get_parameter_value('generate_pages')
        self.overwrite_templates = self.get_parameter_value('overwrite_templates')
        self.visu_style = self.get_parameter_value('visu_style').lower()
        if not self.visu_style in ['std','blk']:
            self.visu_style = 'std'
            self.logger.error("smartVISU: Invalid value '" + self.get_parameter_value('visu_style') + "' configured for attribute visu_style in plugin.conf, using '" + str(self.visu_style) + "' instead")
        self._handle_widgets = self.get_parameter_value('handle_widgets')
        self.list_deprecated_warnings = self.get_parameter_value('list_deprecated_warnings')

        self.smartvisu_version = self.get_smartvisu_version()
        if self.smartvisu_version == '':
            self.logger.error("Could not determine smartVISU version!")

        self.deprecated_widgets = []
        self.removed_widgets = []
        self.deprecated_plugin_widgets = []  # List of plugin-widgets that use deprecated widgets
        self.removed_plugin_widgets = []  # List of plugin-widgets that use removed widgets
        self.d_usage = {}
        self.r_usage = {}

        self.read_visu_definition()
        self.load_deprecated_info()


    def run(self):
        self.alive = True
        if self.smartvisu_dir != '':
            if not os.path.isdir(os.path.join(self.smartvisu_dir, 'pages')):
                self.logger.error("Could not find valid smartVISU directory: {}".format(self.smartvisu_dir))
            else:
                self.logger.warning("Starting smartVISU v{} handling for visu in {}".format(self.smartvisu_version, self.smartvisu_dir))
                if self._handle_widgets:
                    try:
                        sv_iwdg = SmartVisuInstallWidgets(self)
                    except Exception as e:
                        self.logger.exception("SmartVisuInstallWidgets v{}: Exception: {}".format(self.get_smartvisu_version(), e))
                    if self.removed_plugin_widgets != []:
                        self.logger.error("Plugin widgets that need an update now: {}".format(self.removed_plugin_widgets))
                    if self.deprecated_plugin_widgets != []:
                        self.logger.warning("Plugin widgets that should get an update: {}".format(self.deprecated_plugin_widgets))

                if self._generate_pages:
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
                        self.logger.error("Removed widget usage={}".format(self.r_usage))
                    if self.d_usage != {}:
                        self.logger.warning("Deprecated widget usage={}".format(self.d_usage))

                self.logger.info("Finished smartVISU v{} handling".format(self.smartvisu_version))


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
        if dep_warnings is not None:
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
        for widget_name in self.removed_widgets:
            if widget_code.find(widget_name) > -1:
                used_widgets.append(widget_name)
        if used_widgets != []:
            self.removed_plugin_widgets.append(widget)
            if self.list_deprecated_warnings:
                self.logger.error("deprecated_widgets ({}): Removed widget(s) {} used in plugin-widget '{}' of plugin '{}'".format(self.smartvisu_version, used_widgets, widget, plugin))

        used_widgets2 = []
        for widget_name in self.deprecated_widgets:
            if widget_code.find(widget_name) > -1:
                used_widgets2.append(widget_name)
        if used_widgets2 != []:
            self.deprecated_plugin_widgets.append(widget)
            if self.list_deprecated_warnings:
                self.logger.warning("deprecated_widgets ({}): Deprecate widget(s) {} used in plugin-widget '{}' of plugin '{}'".format(self.smartvisu_version, used_widgets2, widget, plugin))

        used_widgets = []
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
        for widget in self.removed_widgets:
            if self.r_usage.get(widget, None) is None:
                self.r_usage[widget] = 0
            self.test_item_widget_attribute(item, 'sv_widget', widget, self.r_usage, 'removed')
            self.test_item_widget_attribute(item, 'sv_widget2', widget, self.r_usage, 'removed')
            self.test_item_widget_attribute(item, 'sv_nav_aside', widget, self.r_usage, 'removed')
            self.test_item_widget_attribute(item, 'sv_nav_aside2', widget, self.r_usage, 'removed')

        for widget in self.deprecated_widgets:
            if self.d_usage.get(widget, None) is None:
                self.d_usage[widget] = 0
            self.test_item_widget_attribute(item, 'sv_widget', widget, self.d_usage)
            self.test_item_widget_attribute(item, 'sv_widget2', widget, self.d_usage)
            self.test_item_widget_attribute(item, 'sv_nav_aside', widget, self.d_usage)
            self.test_item_widget_attribute(item, 'sv_nav_aside2', widget, self.d_usage)

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
