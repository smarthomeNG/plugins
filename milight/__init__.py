#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2014 Stephan Schaade           http://knx-user-forum.de/ shs2
# Copyright 2019 Bernd Meiners                      Bernd.Meiners@mail.de
#########################################################################
#  This file is part of SmartHomeNG.    https://github.com/smarthomeNG//
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

import logging
#import threading
import socket
import time
import colorsys

from lib.module import Modules
from lib.model.smartplugin import *

MILIGHT_SW          = 'milight_sw'
MILIGHT_DIM         = 'milight_dim'
MILIGHT_COL         = 'milight_col'
MILIGHT_WHITE       = 'milight_white'
MILIGHT_DISCO       = 'milight_disco'
MILIGHT_DISCO_UP    = 'milight_disco_up'
MILIGHT_DISCO_DOWN  = 'milight_disco_down'
MILIGHT_RGB         = 'milight_rgb'


class Milight(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    PLUGIN_VERSION = '1.6.1'
    
    # tags this plugin handles
    ITEM_TAGS = [MILIGHT_SW,MILIGHT_DIM,MILIGHT_COL, MILIGHT_WHITE, MILIGHT_DISCO, MILIGHT_DISCO_UP, MILIGHT_DISCO_DOWN, MILIGHT_RGB]

    def __init__(self, sh, *args, **kwargs):
        """
        Initalizes the plugin. The parameters describe for this method are pulled from the entry in plugin.conf.

        :param sh:  **Deprecated**: The instance of the smarthome object. For SmartHomeNG versions 1.4 and up: **Don't use it**!
        :param *args: **Deprecated**: Old way of passing parameter values. For SmartHomeNG versions 1.4 and up: **Don't use it**!
        :param **kwargs:**Deprecated**: Old way of passing parameter values. For SmartHomeNG versions 1.4 and up: **Don't use it**!

        If you need the sh object at all, use the method self.get_sh() to get it. There should be almost no need for
        a reference to the sh object any more.

        """
        from bin.smarthome import VERSION
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        #   self.param1 = self.get_parameter_value('param1')
        self.udp_ip = self.get_parameter_value('udp_ip')
        self.udp_port = self.get_parameter_value('udp_port')

        self.hue_calibrate = self.get_parameter_value('hue_calibrate')
        self.white_calibrate = self.get_parameter_value('white_calibrate')
        
        # old:  True will change color and brightness --> 'HUE_AND_LUM' (default)
        #       False will change only color --> 'HUE'
        self.bricontrol = False if self.get_parameter_value('bricontrol') == 'HUE' else True
        
        self.cutoff = self.get_parameter_value('cutoff')

        # Initialization code goes here

        self.color_map = {             # for reference and future use
            'violet': 0x00,
            'royal_blue': 0x10,
            'baby_blue': 0x20,
            'aqua': 0x30,
            'mint': 0x40,
            'seafoam_green': 0x50,
            'green': 0x60,
            'lime_green': 0x70,
            'yellow': 0x80,
            'yellow_orange': 0x90,
            'orange': 0xA0,
            'red': 0xB0,
            'pink': 0xC0,
            'fusia': 0xD0,
            'lilac': 0xE0,
            'lavendar': 0xF0
        }

        self.on_all = bytearray([0x42, 0x00, 0x55])
        self.on_ch1 = bytearray([0x45, 0x00, 0x55])
        self.on_ch2 = bytearray([0x47, 0x00, 0x55])
        self.on_ch3 = bytearray([0x49, 0x00, 0x55])
        self.on_ch4 = bytearray([0x4B, 0x00, 0x55])

        self.off_all = bytearray([0x41, 0x00, 0x55])
        self.off_ch1 = bytearray([0x46, 0x00, 0x55])
        self.off_ch2 = bytearray([0x48, 0x00, 0x55])
        self.off_ch3 = bytearray([0x4A, 0x00, 0x55])
        self.off_ch4 = bytearray([0x4C, 0x00, 0x55])

        self.white_ch1 = bytearray([0xC5, 0x00, 0x55])
        self.white_ch2 = bytearray([0xC7, 0x00, 0x55])
        self.white_ch3 = bytearray([0xC9, 0x00, 0x55])
        self.white_ch4 = bytearray([0xCB, 0x00, 0x55])

        self.brightness = bytearray([0x4E, 0x00, 0x55])
        self.color = bytearray([0x40, 0x00, 0x55])

        self.max_bright = bytearray([0x4E, 0x3B, 0x55])
        self.discoon = bytearray([0x4D, 0x00, 0x55])
        self.discoup = bytearray([0x44, 0x00, 0x55])
        self.discodown = bytearray([0x43, 0x00, 0x55])

        # if plugin should start even without web interface
        self.init_webinterface()

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        self.alive = True

    def send(self, data_s):
        """
        Sends data given via UDP without further encoding
        """
        self.logger.debug("use UDP {}:{} to send data {}".format(self.udp_ip, self.udp_port, data_s))
        try:
            family, type, proto, canonname, sockaddr = socket.getaddrinfo(
                self.udp_ip, self.udp_port)[0]
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            if self.udp_ip == '255.255.255.255':
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(data_s, (sockaddr[0], sockaddr[1]))
            sock.close()
            del(sock)
        except Exception as e:
            self.logger.warning(
                "miLight UDP: Problem '{}' sending data to {}:{}".format(e, self.udp_ip, self.udp_port))
            pass
        else:
            self.logger.debug("miLight UDP: Sending data to {}:{}:{} ".format(
                self.udp_ip, self.udp_port, data_s))

    # on/off switch function  - to switch on off anused before update  brightness / color / disco
    def switch(self, group, value):

        if group == 0:             # group 0 represents all groups
            if value == 0:
                data_s = self.off_all
            else:
                data_s = self.on_all

        if group == 1:
            if value == 0:
                data_s = self.off_ch1
            else:
                data_s = self.on_ch1

        if group == 2:
            if value == 0:
                data_s = self.off_ch2
            else:
                data_s = self.on_ch2

        if group == 3:
            if value == 0:
                data_s = self.off_ch3
            else:
                data_s = self.on_ch3

        if group == 4:
            if value == 0:
                data_s = self.off_ch4
            else:
                data_s = self.on_ch4

        self.send(data_s)           # call UDP send
        
    # dimmer function  - 2nd command after switch (on)
    def dim(self, group, value):

        time.sleep(0.1)             # wait 100 ms
        self.logger.info(value)
        value = int(value / 8.0)    # for compliance with KNX DPT5
        self.logger.info(value)
        data_s = self.brightness
        data_s[1] = value           # set Brightness
        self.send(data_s)           # call UDP to send WHITE if switched on
        
    # color function  
    def col(self, group, value):

        if group == 0:              # group 0 represents all groups
            data_s = self.on_all

        if group == 1:
            data_s = self.on_ch1

        if group == 2:
            data_s = self.on_ch2

        if group == 3:
            data_s = self.on_ch3

        if group == 4:
            data_s = self.on_ch4

        self.send(data_s)           # call UDP send   to switch on/off

        time.sleep(0.1)             # wait 100 ms

        data_s = self.color
        data_s[1] = value           # set Color
        self.send(data_s)           # call UDP to send WHITE if switched on
        
    # white function  - 2nd command after switch (on)
    def white(self, group, value):

        time.sleep(0.1)               # wait 100 ms

        if value == 1:
            if group == 1:
                data_s = self.white_ch1
            if group == 2:
                data_s = self.white_ch2
            if group == 3:
                data_s = self.white_ch3
            if group == 4:
                data_s = self.white_ch4
            self.send(data_s)        # call UDP to send WHITE if switched on

    # disco function  - 2nd command after switch (on)
    def disco(self, group, value):
        value = 1                     # Avoid switch off
        self.logger.info("disco")
        time.sleep(0.1)               # wait 100 ms

        data_s = self.discoon
        self.logger.info(data_s)
        self.send(data_s)
        
    # disco speed up  - 2nd command after switch (on)
    def disco_up(self, group, value):
        value = 1                      # Avoid switch off
        self.logger.info("disco up")
        time.sleep(0.1)               # wait 100 ms

        data_s = self.discoup
        self.logger.info(data_s)
        self.send(data_s) 
        
    # disco speed down - 2nd command after switch (on)
    def disco_down(self, group, value):
        value = 1
        self.logger.info("disco down")      # Avoid switch off

        time.sleep(0.1)               # wait 100 ms

        data_s = self.discodown
        self.logger.info(data_s)
        self.send(data_s)

    # rgb calculation
    def huecalc(self, value):
        offset = 0.3 + float(self.hue_calibrate)

        re= value[0] / (255.0)
        gn= value[1] / (255.0)
        bl= value[2] / (255.0)


        # trying HLS model for brightnes optimization
        hls =  colorsys.rgb_to_hls(re, gn, bl)
        self.hue =  hls[0]+offset
        if self.hue > 1:
            self.hue = self.hue - 1
           
        self.hue = ((1-self.hue)*255)
        if re != gn:
            self.hue =self.hue+0.001
        self.lum = hls[1] *255
        self.sat =  hls[1]

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
        for elem in [MILIGHT_SW, MILIGHT_DIM, MILIGHT_COL, MILIGHT_WHITE, MILIGHT_DISCO, MILIGHT_DISCO_UP, MILIGHT_DISCO_DOWN, MILIGHT_RGB]:
            if self.has_iattr(item.conf, elem):
                return self.update_item

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
            # code to execute, only if the item has not been changed by this this plugin:
            self.logger.info("Update item: {}, item has been changed outside this plugin".format(item.property.path))

            if self.has_iattr(item.conf, MILIGHT_SW):
                channels=self.get_iattr_value(item.conf, MILIGHT_SW)
                for channel in channels:
                    self.logger.info("miLight switching channel: {0}".format(channel))
                    group = int(channel)
                    #logger.info(item())
                    self.switch(group, item())

            if self.has_iattr(item.conf, MILIGHT_DIM):
                channels=self.get_iattr_value(item.conf, MILIGHT_DIM)
                for channel in channels:
                    self.logger.info("miLight dimming channel: {0}".format(channel))
                    group = int(channel)
                    #logger.info(item())
                    self.switch(group, item())
                    self.dim(group, item())

            if self.has_iattr(item.conf, MILIGHT_COL):
                channels=self.get_iattr_value(item.conf, MILIGHT_COL)
                for channel in channels:
                    self.logger.info("miLight HUE channel: {0}".format(channel))
                    group = int(channel)
                    #logger.info(item())
                    self.col(group, item())

            if self.has_iattr(item.conf, MILIGHT_WHITE):
                channels=self.get_iattr_value(item.conf, MILIGHT_WHITE)
                for channel in channels:
                    self.logger.info("miLight set white channel: {0}".format(channel))
                    group = int(channel)
                    #logger.info(item())
                    self.switch(group, item())
                    self.white(group, item())

            if self.has_iattr(item.conf, MILIGHT_DISCO):
                channels=self.get_iattr_value(item.conf, MILIGHT_DISCO)
                for channel in channels:
                    self.logger.info("miLight disco channel: {0}".format(channel))
                    group = int(channel)
                    #logger.info(item())
                    self.switch(group, item())
                    self.disco(group, item())

            if self.has_iattr(item.conf, MILIGHT_DISCO_UP):
                channels=self.get_iattr_value(item.conf, MILIGHT_DISCO_UP)
                for channel in channels:
                    self.logger.info("miLight increase disco speed channel: {0}".format(channel))
                    group = int(channel)
                    #logger.info(item())
                    self.switch(group, item())
                    self.disco_up(group, item())

            if self.has_iattr(item.conf, MILIGHT_DISCO_DOWN):
                channels=self.get_iattr_value(item.conf, MILIGHT_DISCO_DOWN)
                for channel in channels:
                    self.logger.info("miLight decrease disco speed channel: {0}".format(channel))
                    group = int(channel)
                    #logger.info(item())
                    self.switch(group, item())
                    self.disco_down(group, item())

            if self.has_iattr(item.conf, MILIGHT_RGB):
                channels=self.get_iattr_value(item.conf, MILIGHT_RGB)
                for channel in channels:
                    self.logger.info("miLight RGB input for  channel: {0}".format(channel))
                    group = int(channel)
                    #logger.info(item())

                    self.switch(group, 1)
                    self.huecalc (item())
                    self.logger.info("miLight HUE: {0}".format(self.hue))
                    self.logger.info("miLight LUM: {0}".format(self.lum))
                    calibrate = 178.5 + int(self.white_calibrate)
                    if self.hue == calibrate:
                            self.white (group,1)
                    else: 
                            self.hue=int(self.hue)
                            self.col(group, self.hue)
                    if self.bricontrol:
                        if self.lum <= float(self.cutoff):
                            self.switch(group, 0)
                        else:
                            self.switch(group, 1)
                            self.dim(group, self.lum)


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
