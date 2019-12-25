#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2013 Niko Will             2ndsky @ http://knx-user-forum.de
#  Copyright 2019 Bernd Meiners					    Bernd.Meiners@mail.de
#########################################################################
#  This file is part of SmartHomeNG.
#
#  Sample plugin for new plugins to run with SmartHomeNG version 1.4 and
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
from lib.model.smartplugin import *
import re
import logging

from lib.shtime import Shtime
shtime = Shtime.get_instance()


class SolarLog(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    PLUGIN_VERSION = '1.6.0'

    def __init__(self, sh, *args, **kwargs):
        """
        Initalizes the plugin. The parameters describe for this method are pulled from the entry in plugin.conf.

        :param sh:  **Deprecated**: The instance of the smarthome object. For SmartHomeNG versions 1.4 and up: **Don't use it**!
        :param *args: **Deprecated**: Old way of passing parameter values. For SmartHomeNG versions 1.4 and up: **Don't use it**!
        :param **kwargs:**Deprecated**: Old way of passing parameter values. For SmartHomeNG versions 1.4 and up: **Don't use it**!

        If you need the sh object at all, use the method self.get_sh() to get it. There should be almost no need for
        a reference to the sh object any more.

        The parameters *args and **kwargs are the old way of passing parameters. They are deprecated. They are imlemented
        to support oder plugins. Plugins for SmartHomeNG v1.4 and beyond should use the new way of getting parameter values:
        use the SmartPlugin method get_parameter_value(parameter_name) instead. Anywhere within the Plugin you can get
        the configured (and checked) value for a parameter by calling self.get_parameter_value(parameter_name). It
        returns the value in the datatype that is defined in the metadata.
        """
        from bin.smarthome import VERSION
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        self.host = self.get_parameter_value('host')
        self.cycle = self.get_parameter_value('cycle')

        # Initialization code goes here

        self._count_inverter = 0
        self._count_strings = []
        self._items = {}
        self._last_datetime = None
        self._is_online = True
        self.first_poll = True

        # if plugin should start even without web interface
        self.init_webinterface()

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        # setup scheduler for device poll loop
        self.scheduler_add(self.get_shortname(), self.poll_device, cycle=self.cycle, next=shtime.now())
        self.alive = True

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called")
        self.alive = False

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        The plugin can, corresponding to its attribute keywords, decide what to do with
        the item in future, like adding it to an internal array for future reference
        :param item:    The item to process.
        :return:        always None as no update from SmartHomeNG core is needed
        """
        if self.has_iattr(item.conf, 'solarlog'):
            self.logger.debug("parse item: {}".format(item))
            index = get_iattr_value(item.conf, 'solarlog')
            self._items[ index ] = item
        
        return None

    def poll_device(self):
        """
        Polls for updates of the SolarLog device
        """
        now = self._sh.now()

        try:
            if not first_poll:
                time_start = int(vars(self)['time_start'][now.month - 1])
                time_end = int(vars(self)['time_end'][now.month - 1])

                # reset all out values at midnight
                if now.hour is 0:
                    for name in list(self._items.keys()):
                        if 'out_' in name:
                            self._items[name](0)

                # we start refreshing one hour earlier as set by the device
                if now.hour < (time_start - 1):
                    return

                # in the evening we stop refreshing when the device is offline
                if now.hour >= time_end and not self._is_online:
                    return

            self._read_base_vars()

            if first_poll:
                self._count_inverter = int(vars(self)['AnzahlWR'])
                for x in range(0, self._count_inverter):
                    self._count_strings.append(int(vars(self)['WRInfo'][x][5]))

            self._read_min_cur()

            # set state and error messages
            for x in range(0, self._count_inverter):
                if 'curStatusCode_{0}'.format(x) in self._items:
                    item = self._items['curStatusCode_{0}'.format(x)]
                    status = int(vars(self)['curStatusCode'][x])
                    if isinstance(item(), str):
                        if status is 255:
                            item('Offline')
                        elif status >= len(vars(self)['StatusCodes'][x]):
                            item('unbekannt')
                        else:
                            item(vars(self)['StatusCodes'][x][status])
                    else:
                        item(status)
                if 'curFehlerCode_{0}'.format(x) in self._items:
                    item = self._items['curFehlerCode_{0}'.format(x)]
                    error = int(vars(self)['curFehlerCode'][x])
                    if isinstance(item(), str):
                        if error >= len(vars(self)['FehlerCodes'][x]):
                            item('unbekannt')
                        else:
                            item(vars(self)['FehlerCodes'][x][error])
                    else:
                        item(error)

            self._is_online = vars(self)['isOnline'] == 'true'

            groups = self._read_min_day()
            if groups:
                for name in list(groups.keys()):
                    if name in self._items:
                        if not self._is_online and ('pdc_' in name or 'udc_' in name or 'pac_' in name):
                            self._items[name](0)
                        elif now.hour is 0 and 'out_' in name:
                            self._items[name](0)
                        else:
                            self._items[name](groups[name])

            for name in list(vars(self).keys()):
                if name in self._items:
                    self._items[name](vars(self)[name])
        except Exception as e:
            self.logger.error("An error '{}' occurred while polling data from host '{}'".format(e, self.host))
        finally:
            self.first_poll = False

    def _read_base_vars(self):
        self._read_javascript('base_vars.js')

    def _read_min_cur(self):
        self._read_javascript('min_cur.js')

    def _read_javascript(self, filename):
        re_var = re.compile(
            r'^var\s+(?P<varname>\w+)\s*=\s*"?(?P<varvalue>[^"]+)"?;?')
        re_array = re.compile(
            r'^var\s+(?P<varname>\w+)\s*=\s*new\s*Array\s*\((?P<arrayvalues>.*)\)')
        re_array_1st_level = re.compile(
            r'\s*(?P<varname>\w+)\[(?P<idx1>[0-9]+)\]((\s*=\s*(?:new\s*Array)?\((?P<arrayvalues>.*)\))|(\s*=\s*(?P<arraystring>.*)))')
        re_array_2nd_level = re.compile(
            r'\s*(?P<varname>\w+)\[(?P<idx1>[0-9]+)\]\s*\[(?P<idx2>[0-9]+)\]\s*=\s*new\s*Array\s*\((?P<arrayvalues>.*)\)')

        f = self._read(filename)

        if f:
            for line in f.splitlines():
                matches = re_array.match(line)

                if matches:
                    name, value = matches.groups()

                    vars(self)[name] = []

                    if value in vars(self):
                        vars(self)[name] = [None] * int(vars(self)[value])
                    else:
                        try:
                            vars(self)[name] = [None] * int(value)
                        except:
                            vars(self)[name] = [x.strip(' "')
                                                for x in value.split(',')]
                    continue

                matches = re_var.match(line)

                if matches:
                    name, value = matches.groups()
                    vars(self)[name] = value
                    continue

                matches = re_array_1st_level.match(line)

                if matches:
                    name = matches.group('varname')
                    idx1 = int(matches.group('idx1'))

                    if name in vars(self):
                        values = matches.group('arrayvalues')
                        if not values:
                            values = matches.group('arraystring')
                        if ',' in values:
                            vars(self)[name][idx1] = [x.strip(' "')
                                                      for x in values.split(',')]
                        else:
                            vars(self)[name][idx1] = values
                    continue

                matches = re_array_2nd_level.match(line)

                if matches:
                    name, idx1, idx2, value = matches.groups()

                    if name in vars(self):
                        vars(self)[name][int(idx1)][int(idx2)] = [x.strip(' "')
                                                                  for x in value.split(',')]
                    continue

    def _read_years(self):
        pattern = r'ye\[yx\+\+\]=.(?P<day>\d{2})\.(?P<month>\d{2})\.(?P<year>\d{2})'

        for x in range(0, self._count_inverter):
            pattern += '\|(?P<out_{0}>[0-9]*)'.format(x)

        pattern += '\"'
        re_entry = re.compile(pattern)

        years = self._read('years.js')

        if years:
            for line in years.splitlines():
                matches = re_entry.match(line)

                if matches:
                    logger.debug(matches.groups())

    def _read_months(self):
        pattern = r'mo\[mx\+\+\]=.(?P<day>\d{2})\.(?P<month>\d{2})\.(?P<year>\d{2})'

        for x in range(0, self._count_inverter):
            pattern += '\|(?P<out_{0}>[0-9]*)'.format(x)

        pattern += '\"'
        re_entry = re.compile(pattern)

        months = self._read('months.js')

        if months:
            for line in months.splitlines():
                matches = re_entry.match(line)

                if matches:
                    logger.debug(matches.groups())

    def _read_days(self, history=False):
        pattern = r'da\[dx\+\+\]=.(?P<day>\d{2})\.(?P<month>\d{2})\.(?P<year>\d{2})'

        for x in range(0, self._count_inverter):
            pattern += '\|(?P<out_{0}>[0-9]*);(?P<pac_max_{0}>[0-9]*)'.format(x)

        pattern += '\"'
        re_entry = re.compile(pattern)

        if history:
            days = self._read('days_hist.js')
        else:
            days = self._read('days.js')

        if days:
            for line in days.splitlines():
                matches = re_entry.match(line)

                if matches:
                    logger.debug(matches.groups())

    def _read_min_day(self, date=None, read_all=False):
        pattern = r'm\[mi\+\+\]=.(?P<day>\d{2})\.(?P<month>\d{2})\.(?P<year>\d{2})\s(?P<hour>\d{2})\:(?P<minute>\d{2})\:(?P<second>\d{2})'

        # TODO: add a pattern that matches sensor boxes
        # ATM only inverters and strings supported
        for x in range(0, self._count_inverter):
            pattern += '\|(?P<pac_{0}>[0-9]*)'.format(x)

            for y in range(0, self._count_strings[x]):
                pattern += ';(?P<pdc_{0}_{1}>[0-9]*)'.format(x, y)

            pattern += ';(?P<out_{0}>[0-9]*)'.format(x)

            for y in range(0, self._count_strings[x]):
                pattern += ';(?P<udc_{0}_{1}>[0-9]*)'.format(x, y)

            if len(vars(self)['WRInfo'][x]) > 12:
                if vars(self)['WRInfo'][x][12] == '1':
                    pattern += ';(?P<tmp_{0}>[0-9]*)'.format(x)

        pattern += '\"'
        re_entry = re.compile(pattern)

        if date:
            min_day = self._read('min{0}.js'.format(date.strftime('%y%m%d')))
        else:
            min_day = self._read('min_day.js')

        groups = []

        if min_day:
            for line in min_day.splitlines():
                matches = re_entry.match(line)

                if matches:
                    if read_all:
                        groups.append(matches.groupdict())
                    else:
                        return matches.groupdict()

        return groups if read_all else None

    def _read(self, filename):
        url = self._host + filename
        return self._sh.tools.fetch_url(url).decode(encoding='latin_1')



    def init_webinterface(self):
        """"
        Initialize the web interface for this plugin

        This method is only needed if the plugin is implementing a web interface
        """
        try:
            self.mod_http = Modules.get_instance().get_module(
                'http')  # try/except to handle running in a core version that does not support modules
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
            #self.plugin.beodevices.update_devices_info()

            # return it as json the the web page
            #return json.dumps(self.plugin.beodevices.beodeviceinfo)
            pass
        return