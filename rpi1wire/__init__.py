#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2015 R.Rauer                              software@rrauer.de
#  Copyright 2020 Bernd Meiners                     Bernd.Meiners@mail.de
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
#from lib.model.mqttplugin import *
from lib.item import Items

import logging
import os

class Rpi1Wire(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    PLUGIN_VERSION = '1.7.0'

    def __init__(self, sh, *args, **kwargs):
        """
        Initalizes the plugin. The parameters describe for this method are pulled from the entry in plugin.conf.

        self.get_parameter_value(parameter_name)
        """

        # Call init code of parent class (SmartPlugin or MqttPlugin)
        super().__init__()

        from bin.smarthome import VERSION
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        self.logger.info('Init rpi1wire')
        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        try:
            self.dirname = self.get_parameter_value('dirname')
            if self.get_parameter_value('cycle') != None:
                self.cycle = self.get_parameter_value('cycle')
            else:
                self.cycle = 120
        except KeyError as e:
            self.logger.critical(
                "Plugin '{}': Inconsistent plugin (invalid metadata definition: {} not defined)".format(self.get_shortname(), e))
            self._init_complete = False
            return

        # Initialization code goes here
        self.sensors = {}
        self._sensordaten = {}
        self.values = {}
        self.sysitems = {}
        self.update = False
        self.get_sensors()
        self.anz_sensors = len(self.sensors)
        self.logger.info("rpi1wire find {0} sensors".format(self.anz_sensors))
        self.logger.info(self.sensors)

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
        self.logger.debug("Run method called")
        # setup scheduler for device poll loop   (disable the following line, if you don't need to poll the device. Rember to comment the self_cycle statement in __init__ as well)
        self.scheduler_add('rpi1wire', self.update_values, prio=3, cycle=self.cycle)

        self.alive = True
        self.update_values()
        self.update_basics()

    def update_basics(self):
        anz = self.get_sh().return_item(self.sysitems['count'])
        ids = self.get_sh().return_item(self.sysitems['list'])
        if anz != None:
            anz(int(self.anz_sensors),'rpi1wire')
            self.logger.debug("rpi1wire-item sensors value = {0}".format(self.anz_sensors))
        if ids != None:
            ids(str(self.sensors).replace("\'",""),'rpi1wire')
            self.logger.debug("rpi1wire-item sensor_list value = {0}".format(self.sensors))

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
            
        if self.has_iattr(item.conf, 'rpi1wire_sys'):
            type = self.get_iattr_value( item.conf, 'rpi1wire_sys')
            if type == 'update':
                self.logger.info("parse item: {}".format(item))
                return self.update_item
            try:
                sitem = item._path
                self.sysitems[type] = str(sitem)
                self.logger.info("Item {0} assignment on Item {1} successful".format(item,sitem))
            except:
                self.logger.warning("Item {0} assignment on Item {1} not successful".format(item,sitem))
            return None

        if not self.has_iattr(item.conf, 'rpi1wire_id'):
            if not self.has_iattr(item.conf, 'rpi1wire_name'):
                return None

        not_found = False
        if self.has_iattr(item.conf, 'rpi1wire_id'):
            addr = self.get_iattr_value( item.conf,'rpi1wire_id')
            try:
                for sn, sid in self.sensors.items():
                    if sid == self.get_iattr_value( item.conf,'rpi1wire_id'):
                        name = sn
                        break
            except:
                self.logger.warning("Sensor {0} as Item defined but Hardware not found".format(self.get_iattr_value( item.conf,'rpi1wire_id')))
                not_found = True
        else:
            if self.has_iattr(item.conf, 'rpi1wire_name'):
                name = self.get_iattr_value( item.conf,'rpi1wire_name')
                try:
                    addr = self.sensors[self.get_iattr_value( item.conf, 'rpi1wire_name')]
                except:
                    self.logger.warning("Sensor {0} Hardware not found".format(self.get_iattr_value( item.conf, 'rpi1wire_name')))
                    not_found = True
        if not_found == False:
            self._sensordaten[addr]['item'] = item

    def parse_logic(self, logic):
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
        if self.update == True:
            return None

        if self.alive and caller != self.get_shortname():
            # code to execute if the plugin is not stopped
            # and only, if the item has not been changed by this this plugin:
            self.logger.info("Update item: {}, item has been changed outside this plugin".format(item.id()))

            if self.has_iattr(item.conf, 'rpi1wire_update'):
                self.logger.info("rpi1wire_update wurde angefordert")
                self.update_sensors()
                return None

    def update_values(self):
         for sensor in self.sensors:
            id = self.sensors[sensor]
            value = self.getvalue(id)
            #if value != 99999:
            text = sensor +"=" + sensor[0] +": " + str(round(value/float(1000),1)) + " (" + str(value)+")"
            self.logger.debug(text)
            self.values[sensor] = round(value/float(1000),1)
            try:
                rpix = self._sensordaten[id]
                temp = rpix['item']
                temp(round(value/float(1000),1), "rpi1wire")
                self._sensordaten[id]['value'] = round(value/float(1000),1)
            except:
                self.logger.info("Sensor {0} has no item".format(id))

    def get_sensors(self): #Hier werden die angeschlossenen Sensoren gesucht und in self.sensors, self.values und self._sensordaten eingetragen
        """
        If successful returns a list of sensors starting at given param dirname
        """
        objects = self.folder_objects(self.dirname)
        i=1
        if objects:
            # walking through the path objects
            for sensor in objects:
                if 'w1_bus' in sensor:
                    continue
                typ = sensor.rsplit("-",1)
                # only proceed if filename starts with known sensor ID
                if typ[0] in ['10', '22', '28']:
                    value = self.getvalue(sensor)
                    if value == 99999:
                        self.logger.warning("rpi1wire {0} - has no value".format(sensor))
                    else:
                        text = "rpi_temp"+str(i)+"=" + sensor +": " + str(round(value/float(1000),1)) + " (" + str(value)+")"
                        self.logger.info(text)
                        self.sensors["rpi_temp"+str(i)] = sensor
                        self.values["rpi_temp"+str(i)] = round(value/float(1000),1)
                        self._sensordaten[sensor]= {'name' : "rpi_temp"+str(i), 'value' : round(value/float(1000),1)}
                        i+=1
        else:
            self.logger.warning("rpi1wire plugin did not find directory at {0}".format(self.dirname))

    def folder_objects(self, dirname, otype="all"):  # Sucht im übergebenen Verzeichnis nach Sensoren und übergibt diese als object
        """
        If successful returns a list of sensors starting at given param dirname
        """
        if (os.path.exists(dirname) == False or
            os.path.isdir(dirname) == False or
            os.access(dirname, os.R_OK) == False):
            return None
        else:
            objects = os.listdir(dirname)
            result = []
            for objectname in objects:
                objectpath = dirname + "/" + objectname
                if (otype == "all" or
                    (otype == "dir" and os.path.isdir(objectpath)  == True) or
                    (otype == "file" and os.path.isfile(objectpath) == True) or
                    (otype == "link" and os.path.islink(objectpath) == True)):
                    result.append(objectname)
            result.sort()
            return result


    def getvalue(self, id): #Liest den Wert des Sensors mit der übergebenen id
        """
        reads a single sensor for a given id
        Source like here https://www.raspberrypi-spy.co.uk/2013/03/raspberry-pi-1-wire-digital-thermometer-sensor/
        """
        try:
            mytemp = ''
            filename = 'w1_slave'
            f = open('/' + self.dirname + '/' + id + '/' + filename, 'r')
            line = f.readline() # read 1st line
            crc = line.rsplit(' ',1)
            crc = crc[1].replace('\n', '')
            if crc=='YES':
                line = f.readline() # read 2nd line
                mytemp = line.rsplit('t=',1)
            else:
                self.logger.warning("rpi1wire {0} - return no value".format(id))
                mytemp = '99999'
            f.close()
            return int(mytemp[1])
        except:
            self.logger.warning("can not read sensor {}".format(id))
            return 99999

    def update_sensors(self):
        self.update = True
        self.sensors = {}
        self.anz_sensors = 0
        self.get_sensors()
        self.anz_sensors = len(self.sensors)
        self.search_item()
        self.update_basics()
        self.update_values()
        upd = self.get_sh().return_item(self.sysitems['update']) # Item zum Updaten der Sensoren
        if upd != None:
            upd(False,'rpi1wire')
            self.logger.warning("{0} update value done, {1} sensors found".format(self.sysitems['update'],self.anz_sensors))
        self.update = False

    def search_item(self): #Durchsucht die items nach den Attributen des Plugins
        items = self.get_sh().return_items()
        for item in items:
            if self.has_iattr(item.conf, 'rpi1wire_id'):
                addr = self.get_iattr_value(item.conf, 'rpi1wire_id')
                try:
                    for sn, sid in self.sensors.items():
                        if sid == addr:
                            name = sn
                            self._sensordaten[addr]['item'] = item
                            break
                except:
                    self.logger.warning("Sensor {0} Hardware not found".format(addr))
                    not_found = True
            if self.has_iattr(item.conf, 'rpi1wire_name'):
                name = self.get_iattr_value( item.conf, 'rpi1wire_name')
                try:
                    addr = self.sensors[name]
                    self._sensordaten[addr]['item'] = item
                except:
                    self.logger.warning("Sensor {0} Hardware not found".format(name))
            if self.has_iattr(item.conf, 'rpi1wire_sys'):
                type = self.get_iattr_value( item.conf, 'rpi1wire_sys')
                try:
                    sitem = item._path
                    self.sysitems[type] = str(sitem)
                    self.logger.warning("Item {0} zuweisung erfolgt auf {1}".format(item,sitem))
                except:
                    self.logger.warning("Item {0} zuweisung fehlgeschlgen auf {1}".format(item,sitem))
        self.logger.info("{0} rpi1wire-items registriert".format(len(self._sensordaten)))



    def save_sysitems(item):
        type = self.get_iattr_value( item.conf, 'rpi1wire_sys')
        try:
            path = item._path
            self.sysitems[type]['item'] = path
        except:
            self.logger.warning("Item {0} zuweisung fehlgeschlgen".format(item))


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
        plgitems = []
        
        for item in self.items.return_items():
            if any(elem in item.property.attributes  for elem in ["rpi1wire_id","rpi1wire_name","rpi1wire_sys"]):
                plgitems.append(item)
        return tmpl.render(p=self.plugin, items=sorted(plgitems, key=lambda k: str.lower(k['_path'])),
                           sensors = self.plugin.sensors,
                           classname = self.plugin._classname,
                           cycle = self.plugin.cycle,
                           dirname = self.plugin.dirname)

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

