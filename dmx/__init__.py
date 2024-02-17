#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2011-2013 Marcus Popp                         marcus@popp.mx
#  Copyright 2017 smaugs
#  Copyright 2019 Bernd Meiners                     Bernd.Meiners@mail.de
#########################################################################
#  This file is part of SmartHomeNG.
#
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
import threading

try:
    import serial
    REQUIRED_PACKAGE_IMPORTED = True
except:
    REQUIRED_PACKAGE_IMPORTED = False

# _dim = 10^((n-1)/(253/3)-1) by JNK from KNX UF
#_dim = [ 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 5, 5, 5, 5, 5, 5, 5, 6, 6, 6, 6, 6, 6, 7, 7, 7, 7, 7, 8, 8, 8, 8, 8, 9, 9, 9, 9, 10, 10, 10, 10, 11, 11, 11, 12, 12, 12, 13, 13, 13, 14, 14, 14, 15, 15, 16, 16, 17, 17, 18, 18, 19, 19, 20, 20, 21, 21, 22, 22, 23, 24, 24, 25, 26, 26, 27, 28, 29, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 46, 47, 48, 50, 51, 52, 54, 55, 57, 58, 60, 62, 63, 65, 67, 69, 71, 73, 75, 77, 79, 81, 83, 86, 88, 90, 93, 95, 98, 101, 104, 106, 109, 112, 115, 119, 122, 125, 129, 132, 136, 140, 144, 148, 152, 156, 160, 165, 169, 174, 179, 184, 189, 194, 199, 205, 211, 216, 222, 228, 235, 241, 248, 255 ]


class DMX(SmartPlugin):
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

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        # If an package import with try/except is done, handle an import error like this:

        # Exit if the required package(s) could not be imported
        if not REQUIRED_PACKAGE_IMPORTED:
            self.logger.error("Unable to import Python package 'serial'")
            self._init_complete = False
            return

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        self._serialport = self.get_parameter_value('serialport')
        self._interface = self.get_parameter_value('interface')

        # Initialization code goes here
        self._dmx_items = []
        self._is_connected = False
        self._lock = threading.Lock()

        if self._interface == 'development_only':
            self._is_connected = True
            self.send = self._send_development_only
        else:
            try:
                self._port = serial.Serial(self._serialport, 38400, timeout=1)
            except:
                self.logger.error("Could not open {}.".format(self._serialport))
                self._init_complete = False
                return
            else:
                self._is_connected = True


            if self._interface == 'nanodmx':
                self.send = self.send_nanodmx
                if not self._send_nanodmx("C?"):
                    self.logger.warning("Could not communicate with dmx adapter.")
                    self._is_connected = False
            elif self._interface == 'enttec':
                self._enttec_data = bytearray(512)
                self.send = self.send_enttec
            else:
                self.logger.error("Unknown interface: {0}".format(self._interface))


        # The following part of the __init__ method is only needed, if a webinterface is being implemented:

        # if plugin should start even without web interface
        self.init_webinterface()

    def _send_development_only(self, channel, value):
        self.logger.warning("sending value '{}' to channel '{}' on development dummy interface.".format(value, channel))

    def _send_nanodmx(self, data):
        if not self._is_connected:
            return False
        self._lock.acquire()
        try:
            self._port.write(data.encode())
            ret = self._port.read(1)
        except:
            self.logger.warning("Problem sending data to dmx adapter.")
            ret = False
        finally:
            self._lock.release()
        if ret == b'G':
            return True
        else:
            return False

    def _send_enttec(self, data):
        if not self._is_connected:
            return False
        self._lock.acquire()
        self._port.write(data)
        self._lock.release()
        return True

    def send_nanodmx(self, channel, value):
        self._send_nanodmx("C{0:03d}L{1:03d}".format(int(channel), int(value)))

    def send_enttec(self, channel, value):
        START_VAL = 0x7E
        END_VAL = 0xE7

        LABELS = {
           'GET_WIDGET_PARAMETERS' :3,  #unused
           'SET_WIDGET_PARAMETERS' :4,  #unused
           'RX_DMX_PACKET'         :5,  #unused
           'TX_DMX_PACKET'         :6,
           'TX_RDM_PACKET_REQUEST' :7,  #unused
           'RX_DMX_ON_CHANGE'      :8,  #unused
        }

        START_DATA = 0x00

        self._enttec_data[channel] = int(value);

        packet = bytearray()
        packet.append(START_VAL)
        packet.append(LABELS['TX_DMX_PACKET'])
        packet.append(len(self._enttec_data) & 0xFF)
        packet.append((len(self._enttec_data) >> 8) & 0xFF)
        packet.append(START_DATA)
        packet.extend(self._enttec_data)
        packet.append(END_VAL)

        self._send_enttec(packet)


    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        self.alive = True
        # if you need to create child threads, do not make them daemon = True!
        # They will not shutdown properly. (It's a python bug)

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
        :return:        If the plugin needs to be informed of an items change you should return a call back function
                        like the function update_item down below. An example when this is needed is the knx plugin
                        where parse_item returns the update_item function when the attribute knx_send is found.
                        This means that when the items value is about to be updated, the call back function is called
                        with the item, caller, source and dest as arguments and in case of the knx plugin the value
                        can be sent to the knx with a knx write function within the knx plugin.
        """
        if self.has_iattr(item.conf, 'dmx_ch'):
            self.logger.debug("parse item found item: {}".format(item))
            self._dmx_items.append(item)
            channels = self.get_iattr_value(item.conf, 'dmx_ch')
            if isinstance(channels, str):
                channels = [channels, ]
            channels = list(map(int, channels))
            item.conf['dmx_ch'] = channels
            return self.update_item
        else:
            return None

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
            # code to execute, only if the item has not been changed by this plugin:
            self.logger.info("Update item: {}, item has been changed outside this plugin".format(item.property.path))

            if self.has_iattr(item.conf, 'dmx_ch'):
                self.logger.debug(
                    "update_item was called with item '{}' from caller '{}', source '{}' and dest '{}'".format(item,
                                                                                                               caller,
                                                                                                               source,
                                                                                                               dest))
                channels = self.get_iattr_value(item.conf, 'dmx_ch')
                for channel in channels:
                    self.send(channel, int(item()))


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
        return tmpl.render(p=self.plugin, serialport=self.plugin._serialport, interface = self.plugin._interface, item_count = len(self.plugin._dmx_items), items = self.plugin._dmx_items)


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
