#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2012 Niko Will                     http://knx-user-forum.de/
#  Copyright 2019-2020 Bernd Meiners                Bernd.Meiners@mail.de
#########################################################################
#  This file is part of SmartHomeNG.
#
#  Russound plugin for network enabled Multiroom devices
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
from lib.model.smartplugin import SmartPlugin, SmartPluginWebIf
from lib.item import Items
from lib.network import Tcp_client

import logging
import sys
import cherrypy

REQ_DELIMITER = b'\r'
RESP_DELIMITER = b'\r\n'


class Russound(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    PLUGIN_VERSION = '1.7.2'

    def __init__(self, sh, *args, **kwargs):
        """
        Initalizes the plugin. The parameters describe for this method are pulled from the entry in plugin.conf.
        """
        from bin.smarthome import VERSION
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        super().__init__(sh, args, kwargs)
        try:
            # sh = self.get_sh() to get it.
            self.host = self.get_parameter_value('host')
            self.port = self.get_parameter_value('port')
        except KeyError as e:
            self.logger.critical(
                "Plugin '{}': Inconsistent plugin (invalid metadata definition: {} not defined)".format(self.get_shortname(), e))
            self._init_complete = False
            return

        # Initialization code goes here
        self.terminator = RESP_DELIMITER
        self._client = Tcp_client(self.host, self.port, terminator=self.terminator)
        self._client.set_callbacks(data_received=self.found_terminator)
        self.params = {}
        self.sources = {}
        self.suspended = False
        
        self.init_webinterface()
        return

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        if not self._client.connect():
            self.logger.debug(f'Connection to {self.host}:{self.port} not possible. Plugin deactivated.')
            return
        self.alive = True

    def activate(self):
        self.logger.debug("Activate method called, queries to russound will be resumes and data will be written again")
        self.resume()
        
    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called")
        self.alive = False
        self._client.close()

    def connect(self):
        self._client.open()

    def disconnect(self):
        self._client.close()

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
        # if self.has_iattr(item.conf, 'rus_src'):
        #     s = int(self.get_iattr_value(item.conf, 'rus_src'))
        #     self.sources[s] = {'s': s, 'item':item}
        #     self.logger.debug("Source {0} added".format(s))
        #     return None

        if item.path() == self._suspend_item_path:
            self._suspend_item = item
            self.logger.info(f'set suspend_item to {item.path()}')
            return

        if self.has_iattr(item.conf, 'rus_path'):
            self.logger.debug("parse item: {}".format(item))

            path = self.get_iattr_value(item.conf, 'rus_path')
            parts = path.split('.', 2)

            if len(parts) != 3:
                self.logger.warning(
                    "Invalid Russound path with value {0}, format should be 'c.z.p' c = controller, z = zone, p = parameter name.".format(path))
                return None

            c = parts[0]
            z = parts[1]
            param = parts[2]

        else:
            if self.has_iattr(item.conf, 'rus_controller'):
                c = self.get_iattr_value(item.conf, 'rus_controller')
                path = c + '.'
            else:
                return None

            if self.has_iattr(item.conf, 'rus_zone'):
                z = self.get_iattr_value(item.conf, 'rus_zone')
                path += z + '.'
            else:
                self.logger.warning(
                    "No zone specified for controller {0} in config of item {1}".format(c, item))
                return None

            if self.has_iattr(item.conf, 'rus_parameter'):
                param = self.get_iattr_value(item.conf, 'rus_parameter')
                path += param
            else:
                self.logger.warning(
                    "No parameter specified for zone {0} on controller {1} in config of item {2}".format(z, c, item))
                return None

            if param == 'relativevolume':
                # item._enforce_updates = True
                item.property.enforce_updates = True

            self.set_attr_value(item.conf, 'rus_path', path)

        param = param.lower()
        self.params[path] = {'c':
                             int(c), 'z': int(z), 'param': param, 'item': item}
        self.logger.debug("Parameter {0} with path {1} added".format(item, path))

        return self.update_item

    def parse_logic(self, logic):
        pass

    def _restrict(self, val, minval, maxval):
        if val < minval:
            return minval
        if val > maxval:
            return maxval
        return val

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
        if self.alive and caller != self.get_shortname():
            # code to execute if the plugin is not stopped
            # and only, if the item has not been changed by this this plugin:
            self.logger.info("Update item: {}, item has been changed outside this plugin (caller={}, source={}, dest={})".format(item.id(), caller, source, dest))

            if item.path() == self._suspend_item_path:
                if self._suspend_item is not None:
                    if item():
                        self.suspend(f'suspend item {item.path()}')
                    else:
                        self.resume(f'suspend item {item.path()}')
                return

            if self.has_iattr(item.conf, 'rus_path'):
                path = self.get_iattr_value(item.conf, 'rus_path')
                p = self.params[path]
                cmd = p['param']
                c = p['c']
                z = p['z']

                if cmd == 'bass':
                    self.send_set(c, z, cmd, self._restrict(item(), -10, 10))
                elif cmd == 'treble':
                    self.send_set(c, z, cmd, self._restrict(item(), -10, 10))
                elif cmd == 'balance':
                    self.send_set(c, z, cmd, self._restrict(item(), -10, 10))
                elif cmd == 'loudness':
                    self.send_set(c, z, cmd, 'ON' if item() else 'OFF')
                elif cmd == 'turnonvolume':
                    self.send_set(c, z, cmd, self._restrict(item(), 0, 50))
                elif cmd == 'status':
                    self.send_event(c, z, 'ZoneOn' if item() else 'ZoneOff')
                elif cmd == 'partymode':
                    self.send_event(c, z, cmd, item().lower())
                elif cmd == 'donotdisturb':
                    self.send_event(c, z, cmd, 'on' if item() else 'off')
                elif cmd == 'volume':
                    self.send_event(c, z, 'KeyPress', 'Volume',
                                    self._restrict(item(), 0, 50))
                elif cmd == 'currentsource':
                    self.send_event(c, z, 'SelectSource', item())
                elif cmd == 'relativevolume':
                    self.send_event(c, z, 'KeyPress',
                                    'VolumeUp' if item() else 'VolumeDown')
                elif cmd == 'name':
                    return
                else:
                    self.key_release(c, z, cmd)

    def send_set(self, c, z, cmd, value):
        self._send_cmd(
            'SET C[{0}].Z[{1}].{2}="{3}"\r'.format(c, z, cmd, value))

    def send_event(self, c, z, cmd, value1=None, value2=None):
        if value1 is None and value2 is None:
            self._send_cmd('EVENT C[{0}].Z[{1}]!{2}\r'.format(c, z, cmd))
        elif value2 is None:
            self._send_cmd(
                'EVENT C[{0}].Z[{1}]!{2} {3}\r'.format(c, z, cmd, value1))
        else:
            self._send_cmd(
                'EVENT C[{0}].Z[{1}]!{2} {3} {4}\r'.format(c, z, cmd, value1, value2))

    def key_release(self, c, z, key_code):
        self.send_event(c, z, 'KeyRelease', key_code)

    def key_hold(self, c, z, key_code, hold_time):
        self.send_event(c, z, 'KeyHold', key_code, hold_time)

    def _watch_zone(self, controller, zone):
        self._send_cmd('WATCH C[{0}].Z[{1}] ON\r'.format(controller, zone))

    def _watch_source(self, source):
        self._send_cmd('WATCH S[{0}] ON\r'.format(source))

    def _watch_system(self):
        self._send_cmd('WATCH System ON\r')

    def _send_cmd(self, cmd):
        if not self.alive:
            self.logger.error('Trying to send data but plugin is not running')
            return
        
        if self.suspended:
            self.logger.debug('Plugin is suspended, data will not be written')
            return

        self.logger.debug("Sending request: {0}".format(cmd))

        # if connection is closed we don't wait for sh.con to reopen it
        # instead we reconnect immediatly
#
        # if not self.connected:
        #     self.connect()
        if not self._client.connected:
            self._client.connect()

        # self.send(cmd.encode())
        self._client.send(cmd.encode())
#

    def found_terminator(self, resp):
        try:
            resp = resp.decode()
        except Exception as e:
            self.logger.error("found_terminator: exception in decode: {}".format(e))
            return

        try:
            self.logger.debug("Parse response: {0}".format(resp))
            if resp[0] == 'S':
                return
            if resp[0] == 'E':
                self.logger.debug("Received response error: {0}".format(resp))
            elif resp[0] == 'N':
                resp = resp[2:]

                if resp[0] == 'C':
                    resp = resp.split('.', 2)
                    c = int(resp[0][2])
                    z = int(resp[1][2])
                    resp = resp[2]
                    cmd = resp.split('=')[0].lower()
                    value = resp.split('"')[1]

                    path = '{0}.{1}.{2}'.format(c, z, cmd)
                    if path in list(self.params.keys()):
                        self.params[path]['item'](
                            self._decode(cmd, value), self.get_shortname())
                elif resp.startswith('System.status'):
                    return
                elif resp[0] == 'S':
                    resp = resp.split('.', 1)
#                   s = int(resp[0][2])
                    resp = resp[1]
                    cmd = resp.split('=')[0].lower()
                    value = resp.split('"')[1]

#                    if s in self.sources.keys():
#                        for child in self.sources[s]['item'].return_children():
#                            if str(child).lower() == cmd.lower():
#                                child(unicode(value, 'utf-8'), self.get_shortname())
                    return
        except Exception as e:
            self.logger.error(e)

    def _decode(self, cmd, value):
        cmd = cmd.lower()
        if cmd in ['bass', 'treble', 'balance', 'turnonvolume', 'volume']:
            return int(value)
        elif cmd in ['loudness', 'status', 'mute']:
            return value == 'ON'
        elif cmd in ['partymode', 'donotdisturb']:
            return value.lower()
        elif cmd == 'currentsource':
            return value
        elif cmd == 'name':
            return str(value)

    def handle_connect(self):
        self.discard_buffers()
        self.terminator = RESP_DELIMITER
        self._watch_system()

        zones = []
        for path in self.params:
            p = self.params[path]
            key = '{0}.{1}'.format(p['c'], p['z'])
            if key not in zones:
                zones.append(key)
                self._watch_zone(p['c'], p['z'])

        for s in self.sources:
            self._watch_source(s)

    def poll_device(self):
        """
        Polls for updates of the device

        This method is only needed, if the device (hardware/interface) does not propagate
        changes on it's own, but has to be polled to get the actual status.
        It is called by the scheduler which is set within run() method.
        """
        # # get the value from the device
        # device_value = ...
        #
        # # find the item(s) to update:
        # for item in self.sh.find_items('...'):
        #
        #     # update the item by calling item(value, caller, source=None, dest=None)
        #     # - value and caller must be specified, source and dest are optional
        #     #
        #     # The simple case:
        #     item(device_value, self.get_shortname())
        #     # if the plugin is a gateway plugin which may receive updates from several external sources,
        #     # the source should be included when updating the the value:
        #     item(device_value, self.get_shortname(), source=device_source_id)
        pass

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
        if self.mod_http is None:
            self.logger.error("Not initializing the web interface")
            return False

        if "SmartPluginWebIf" not in list(sys.modules['lib.model.smartplugin'].__dict__):
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

        self.items = Items.get_instance()

    @cherrypy.expose
    def index(self, reload=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        tmpl = self.tplenv.get_template('index.html')
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        return tmpl.render(p=self.plugin, items=sorted(self.items.return_items(), key=lambda k: str.lower(k['_path'])))

    @cherrypy.expose
    def get_data_html(self, dataSet=None):
        """
        Return data to update the webpage

        For the standard update mechanism of the web interface, the dataSet to return the data for is None

        :param dataSet: Dataset for which the data should be returned (standard: None)
        :return: dict with the data needed to update the web page.
        """
        if dataSet is None:
            pass
            # get the new data
            # data = {}

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
