#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2018-      Martin Sinn                         m.sinn@gmx.de
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

import logging

from pyhomematic import HMConnection

from lib.module import Modules
from lib.model.smartplugin import SmartPlugin

from time import sleep


class Homematic(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """
    
    PLUGIN_VERSION = '1.5.0'
#    ALLOW_MULTIINSTANCE = False
    
    connected = False
    

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
        
        # Initialization code goes here
        self.username = self.get_parameter_value('username')
        self.password = self.get_parameter_value('password')
        self.host = self.get_parameter_value('host')
        self.port = self.get_parameter_value('port')

        # build dict identifier for the homematic ccu of this plugin instance
        self.hm_id = 'rf'
        if self.get_instance_name() != '':
            self.hm_id += '_' + self.get_instance_name()
            self.log_instance_str = ' ('+self.get_instance_name()+')'
        else:
            self.log_instance_str = ''
        # create HomeMatic object
        try:
             self.hm = HMConnection(interface_id="myserver", autostart=False, 
                                    eventcallback=self.eventcallback, systemcallback=self.systemcallback, 
                                    remotes={self.hm_id:{"ip": self.host,"port": self.port}})
        except:
            self.logger.error("{}: Unable to create HomeMatic object".format(self.get_fullname()))
            self._init_complete = False
            return

        # set the name of the thread that got created by pyhomematic to something meaningfull 
        self.hm._server.name = self.get_fullname()

        # start communication with HomeMatic ccu
        try:
            self.hm.start()
            self.connected = True
        except:
            self.logger.error("{}: Unable to start HomeMatic object - SmartHomeNG will be unable to terminate the thread vor this plugin (instance)".format(self.get_fullname()))
            self.connected = False
#            self._init_complete = False
            # stop the thread that got created by initializing pyhomematic 
#            self.hm.stop()
#            return

        if self.connected:
            # TO DO: sleep besser lösen!
            sleep(20)
#            self.logger.warning("Plugin '{}': self.hm.devices".format(self.hm.devices))
            if self.hm.devices.get(self.hm_id,{}) == {}:
                self.logger.error("{}: Connection to ccu failed".format(self.get_fullname()))
#                self._init_complete = False
                # stop the thread that got created by initializing pyhomematic 
#                self.hm.stop()
#                return
        
        self.hm_items = []           

        if not self.init_webinterface():
#            self._init_complete = False
            pass

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
        self.hm.stop()


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
        if self.has_iattr(item.conf, 'hm_address'):
            init_error = False
#            self.logger.debug("parse_item{}: {}".format(self.log_instance_str, item))
            dev_id = self.get_iattr_value(item.conf, 'hm_address')
            dev = self.hm.devices[self.hm_id].get(dev_id)

            hm_address = self.get_iattr_value(item.conf, 'hm_address')
            hm_channel = self.get_iattr_value(item.conf, 'hm_channel')
            hm_function = self.get_iattr_value(item.conf, 'hm_function')
            hm_node = ''
            if dev is None:
                self.logger.error("parse_item{}: No HomeMatic device found with address '{}' for {}".format(self.log_instance_str, dev_id, item))
#                return

            else:
                hm_devicetype = self.get_hmdevicetype( dev_id )

#                self.logger.warning("{}, parse_item {}: type='{}', hm_address='{}', hm_channel='{}', hm_function='{}', hm_devicetype='{}'".format(self.get_fullname(), item, item.type(), hm_address, hm_channel, hm_function, hm_devicetype))

                # Lookup hm_node and hm_channel for the configured hm_function
                if hm_function is None:
                    hm_function = 'STATE'
                hm_channel, hm_node = self.get_hmchannelforfunction(hm_function, hm_channel, dev.ACTIONNODE, 'AC', item)
                if hm_node == '':
                    hm_channel, hm_node = self.get_hmchannelforfunction(hm_function, hm_channel, dev.ATTRIBUTENODE, 'AT', item)
                if hm_node == '':
                    hm_channel, hm_node = self.get_hmchannelforfunction(hm_function, hm_channel, dev.BINARYNODE, 'BI', item)
                if hm_node == '':
                    hm_channel, hm_node = self.get_hmchannelforfunction(hm_function, hm_channel, dev.EVENTNODE, 'EV', item)
                if hm_node == '':
                    hm_channel, hm_node = self.get_hmchannelforfunction(hm_function, hm_channel, dev.SENSORNODE, 'SE', item)
                if hm_node == '':
                    hm_channel, hm_node = self.get_hmchannelforfunction(hm_function, hm_channel, dev.WRITENODE, 'WR', item)
                        
#                self.logger.warning("{}, parse_item {}: dev.ELEMENT='{}'".format(self.get_fullname(), item, dev.ELEMENT))
            
                self.logger.debug("parse_item{}: {}, type='{}', address={}:{}, function='{}', devicetype='{}'".format(self.log_instance_str, item, item.type(), hm_address, hm_channel, hm_function, hm_devicetype))
                
            if hm_node == '':
                hm_node = None
                
            # store item and device information for plugin instance
            self.hm_items.append( [str(item), item, hm_address, hm_channel, hm_function, hm_node] )
            
            # Initialize item from HomeMatic
            if dev is not None:
                value = None
                if hm_node == 'AC':
                    pass     # actionNodeData can not be read for initialization
                    init_error = True
                elif hm_node == 'AT':
                    value = dev.getAttributeData(hm_function)
                elif hm_node == 'BI':
                    value = dev.getBinaryData(hm_function)
                elif hm_node == 'EV':
                    value = dev.event(hm_function)
                elif hm_node == 'SE':
                    value = dev.getSensorData(hm_function)
                elif hm_node == 'WR':
                    value = dev.getWriteData(hm_function)
                else:
                    init_error = True
                    self.logger.error("parse_item{}: Not initializing {}: Unknown hm_node='{}' for address={}:{}, function={}".format(self.log_instance_str, item, hm_node, hm_address, hm_channel, hm_function))

                if value is not None:
                    self.logger.warning("parse_item{}: Initializing {} with '{}' from address={}:{}, function={}".format(self.log_instance_str, item, value, hm_address, hm_channel, hm_function))
                    item(value, 'HomeMatic', 'Init')
                else:
                    if not init_error:
                        self.logger.error("parse_item{}: Not initializing {} from address={}:{}, function='{}'".format(self.log_instance_str, item, hm_node, hm_address, hm_channel, hm_function))
                
            return self.update_item


    def parse_logic(self, logic):
        """
        Default plugin parse_logic method
        """
        if 'xxx' in logic.conf:
            # self.function(logic['name'])
            pass


    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Write items values
        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        if caller != 'HomeMatic':
            if self.has_iattr(item.conf, 'hm_address'):
#               self.hm_items[] = [str(item), item, hm_address, hm_channel, hm_function, hm_node]
                myitem = None
                for i in self.hm_items:
                    if item == i[1]:
                        myitem = i
                        self.logger.warning("update_item{}: Test: item='{}', caller='{}', hm_function={}, itemvalue='{}'".format(self.log_instance_str, item, caller, i[4], item()))
                
                self.logger.warning("update_item{}: Todo: Called with value '{}' for item '{}' from caller '{}', source '{}' and dest '{}'".format(self.log_instance_str, item(), item, caller, source, dest))

                dev_id = self.get_iattr_value(item.conf, 'hm_address')
                dev = self.hm.devices[self.hm_id].get(dev_id)

                # Write item value to HomeMatic device
                if dev is not None:
                    hm_node = myitem[5]
                    hm_channel = myitem[3]
                    hm_function = myitem[4]
                    dev.CHANNELS[int(hm_channel)].setValue(hm_function, item())
                    self.logger.warning("{}, update_item: Called with value '{}' for item '{}' from caller '{}', source '{}' and dest '{}'".format(self.get_fullname(), item(), item, caller, source, dest))
                 

                # ACTIONNODE: PRESS_LONG (action), PRESS_SHORT (action), [LEVEL (float 0.0-1.0)]
                # LEVEL (float: 0.0-1.0), STOP (action), INHIBIT (bool), INSTALL_TEST (action), 
                #   OLD_LEVEL (action), RAMP_TIME (float 0.0-85825945.6 s), RAMP_STOP (action) 
                #
                # Heizkörperthermostat (HM-CC-RT-DN):
                # SET_TEMPERATURE (float -10.0-50.0), AUTO_MODE (action), MANU_MODE (float 4.5-30.5), BOOST_MODE (action), COMFORT_MODE (action), LOWERING_MODE (action),
                # PARTY_MODE_SUBMIT (string), PARTY_TEMPERATURE (float 5.0-30.0), PARTY_START_TIME (int 0-1410), PARTY_START_DAY (int 0-31), PARTY_START_MONTH (int 1-12), PARTY_START_YEAR (int 0-99),
                # PARTY_STOP_TIME (int), PARTY_STOP_DAY (int), PARTY_STOP_MONTH (int), PARTY_STOP_YEAR (int)
                #
                # Heizkörperthermostat (HM-CC-RT-DN-BoM): 
                # CLEAR_WINDOW_OPEN_SYMBOL (int 0-1), SET_SYMBOL_FOR_HEATING_PHASE (int 0-1), ...
                #
                # Funk- Wandthermostat ab V2.0 (CLIMATECONTROL_REGULATOR)
                # SETPOINT (float 6.0-30.0)
                #
                # KeyMatic:
                # RELOCK_DELAY (float 0.0-65535.0)
                #
                # Statusanzeige 16Kanal LED
                # LED_STATUS (option 0=OFF, 1=RED, 2=GREEN, 3=ORANGE), ALL_LEDS (string), LED_SLEEP_MODE (option 0=OFF, 1=ON)
                #
                # Funk- Fernbedienung 19 Tasten mit Display
                # TEXT (string), BULB (action), SWITCH (action), WINDOW (action), DOOR (action), BLIND (action), SCENE (action), PHONE (action),
                # BELL (action), CLOCK (action), ARROW_UP (action), ARROW_DOWN (action), UNIT (option 0=NONE, 1=PERCENT, 2=WATT, 3=CELSIUS, 4=FAHRENHEIT),
                # BEEP (option 0=NONE, 1-3=TONE1-3), BACKLIGHT (option 0=OFF, 1=ON, 2=BLINK_SLOW, 3=BLINK_FAST), 
                # SUBMIT (action), ALARM_COUNT (int 0-255), SERVICE_COUNT (int 0-255)
                #
                # ON_TIME (float 0.0-85825945.6 s), SUBMIT (string)
                    
                # STATE, LEVEL, STOP (action)


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



# ---------------------------------------------------------
#    Methods of the plugin class for the external device
# ---------------------------------------------------------

    def get_hmdevicetype(self, dev_id):
        """
        get the devicetype for the given device id
        
        :param dev_id: HomeMatic device id
        :param type: str
        
        :return: device type
        :rtype: str
        """
        dev = self.hm.devices[self.hm_id].get(dev_id)
        if dev is not None:
            d_type = str(dev.__class__).replace("<class '"+dev.__module__+'.', '').replace("'>",'')
            return d_type
        return ''


    def get_hmchannelforfunction(self, hm_function, hm_channel, node, hm_node, item):
        """
        Returns the HomeMatic Channel of the deivce for the wanted function
        
        :param hm_function: Configured function (or STATE)
        :param hm_channel: Preconfigured channel or None
        :param node: the node attribute of the Homematic device (e.g. dev.BINARYNODE)
        :param hm_node: short string for the nodename (AT, AC, BI, EV, SE, WR)
        """
        if hm_function in node.keys():
            if hm_channel is None:
                hm_channel = node[hm_function][0]
            else:
                if not int(hm_channel) in node[hm_function]:

                    hm_node = ''
                    self.logger.error("get_hmchannelforfunction{}: Invalid channel '{}' specified for {}".format(self.log_instance_str, hm_channel, item))
        else:
            hm_node = ''
        return hm_channel, hm_node
        

    def systemcallback(self, src, *args):
        self.logger.info("systemcallback{}: src = '{}', args = '{}'".format(self.log_instance_str, src, args))


    def eventcallback(self, interface_id, address, value_key, value):
        """
        Callback method for HomeMatic events

        This method is called whenever the HomeMatic ccu processs an event 
        """
        defined = False
        for i in self.hm_items:
            if address == i[2]+':'+str(i[3]):
                if value_key == i[4]:
                    self.logger.info("eventcallback{}: address={}, {}='{}' -> {}".format(self.log_instance_str, address, value_key, value, i[0]))
#                    i[1](value, 'HomeMatic', address)
                    i[1](value, 'HomeMatic')
                    defined = True

        if not defined:
            self.logger.debug("eventcallback{}: Ohne item Zuordnung: interface_id = '{}', address = '{}', {} = '{}'".format(self.log_instance_str, interface_id, address, value_key, value))
                    
            
# ------------------------------------------
#    Webinterface of the plugin
# ------------------------------------------

import cherrypy
from jinja2 import Environment, FileSystemLoader
from jinja2.utils import open_if_exists

class WebInterface:


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
#        self.tplenv = Environment(loader=FileSystemLoader(self.plugin.path_join( self.webif_dir, 'templates' ) ))
        mytemplates = self.plugin.path_join( self.webif_dir, 'templates' )
        globaltemplates = self.plugin.mod_http.gtemplates_dir
        self.tplenv = Environment(loader=FileSystemLoader([mytemplates,globaltemplates]))

        self.tplenv.globals['isfile'] = self.my_isfile

        self.hm_id = self.plugin.hm_id

#        self.logger.warning("WebInterface __init__: instance = '{}', full name = '{}'".format(self.plugin.get_instance_name(), self.plugin.get_fullname()))
#        self.logger.warning("WebInterface __init__: self.hm.devices = {}".format(self.plugin.hm.devices))



    def my_isfile(self, path):
        if path.startswith('/gstatic/'):
            complete_path = self.plugin.path_join(Modules.get_instance().get_module('http')._gstatic_dir, path[len('/gstatic/'):])
            self.logger.warning("my_isfile(g): path={}, _gstatic_dir={}".format(path, Modules.get_instance().get_module('http')._gstatic_dir))
        else:
            complete_path = self.plugin.path_join(self.webif_dir, path)
        from os.path import isfile as isfile
        result = isfile(complete_path)
        self.logger.warning("my_isfile: path={}, complete_path={}, result={}, _gstatic_dir={}".format(path, complete_path, result, Modules.get_instance().get_module('http')._gstatic_dir))
        return result
        

    @cherrypy.expose
    def index(self, learn=None, reload=None):
        """
        Build index.html for cherrypy
        
        Render the template and return the html file to be delivered to the browser
            
        :return: contents of the template after beeing rendered 
        """
        if learn == 'on':
            self.plugin.hm.setInstallMode(self.plugin.hm_id)

        username = self.plugin.username
        host = self.plugin.host
        devices = []
        
        try:
            interface = self.plugin.hm.listBidcosInterfaces(self.hm_id)[0]
            # [{'DEFAULT': True, 'DESCRIPTION': '', 'ADDRESS': 'OEQ1658621', 'TYPE': 'CCU2', 'DUTY_CYCLE': 1, 'CONNECTED': True, 'FIRMWARE_VERSION': '2.8.5'}]
        except:
            interface = None
        
        for dev_id in self.plugin.hm.devices[self.hm_id]:
            dev = self.plugin.hm.devices[self.hm_id][dev_id]
#            d_type = str(dev.__class__).replace("<class '"+dev.__module__+'.', '').replace("'>",'')
            d_type = self.plugin.get_hmdevicetype(dev_id)
            d = {}
            d['name'] = dev._name
            d['address'] = dev_id
            d['hmtype'] = dev._TYPE
            d['type'] = d_type
            d['firmware'] = dev._FIRMWARE
            d['version'] = dev._VERSION
            if d_type in ['Switch','SwitchPowermeter','ShutterContact']:
                try:
                    d['value'] = dev.getValue('STATE')
                except: pass

            devices.append(d)
            	
            d['dev'] = dev
        device_count = len(devices)
        
        tmpl = self.tplenv.get_template('index.html')
        # The first paramter for the render method has to be specified. the base template 
        # for the web interface relys on the instance of the plugin to be passed as p
        return tmpl.render(p=self.plugin, 
                           interface=interface,
                           devices=devices, device_count=device_count, 
                           items=sorted(self.plugin.hm_items), item_count=len(self.plugin.hm_items),
                           hm=self.plugin.hm, hm_id=self.plugin.hm_id )

