#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Ported and Copyright 2014 toggle
#########################################################################
#  This software is based on the FHEM implementation
#  https://github.com/mhop/fhem-mirror/blob/master/fhem/FHEM/00_THZ.pm
#
#  THZ plugin for SmartHomeNG
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
from lib.shtime import Shtime
shtime = Shtime.get_instance()

import logging
import time
import sys
import datetime
from . import ThzProtocol
import socket as socket
from select import select
import threading

# Module Serial is not needed in this module, but will be used later and
# SmartHomeNG core should know if serial module is present so we need to test it here
try:
    import serial
    REQUIRED_PACKAGE_IMPORTED = True
except:
    REQUIRED_PACKAGE_IMPORTED = False


specialRequests = ['logFullScan', 'logRegister', 'setRegiter']
CLIENT_TIMEOUT = 60
POLL_INTERVAL = 10

class THZ(SmartPlugin):
    """
    Class THZ implements main control instance
    """
    PLUGIN_VERSION = "0.2.2"

    def __init__(self, sh, *args, **kwargs):
        """
        old: smarthome, 
        serial_port='/dev/ttyUSB0', 
        baudrate=115200, 
        poll_period=300, 
        min_update_period=86400, 
        max_update_period=300
        server_host = '0.0.0.0'
        server_port = 57483
        """
        from bin.smarthome import VERSION
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        self.logger.debug("init {}".format(__name__))
        self._init_complete = False

        # Exit if the required package(s) could not be imported
        if not REQUIRED_PACKAGE_IMPORTED:
            self.logger.error("{}: Unable to import Python package 'pyserial'".format(self.get_fullname()))
            return

        # Get Parameters
        self._poll_period = self.get_parameter_value('poll_period')
        
        min_update_period = self.get_parameter_value('min_update_period')
        self._min_update_period = datetime.timedelta(seconds=int(min_update_period))

        max_update_period = self.get_parameter_value('max_update_period')
        self._max_update_period = datetime.timedelta(seconds=int(max_update_period))
        
        self._serial_port = self.get_parameter_value('serial_port')
        self._baudrate = self.get_parameter_value('baudrate')
        
        self._server_host = self.get_parameter_value('server_host')
        self._server_port = self.get_parameter_value('server_port')

        self._params = {}
        
        # pass the own logger on
        self._thzProtocol = ThzProtocol.ThzProtocol(self._serial_port, self._baudrate, self.logger)
        self._msgList = {}
        self._logRegisterId = None
        
        # pass the own logger on
        self._thzServer = ThzServer(self, self._server_host, self._server_port, self.logger)
        self._curData = {}
        self._extMsgList = {}

        self.init_webinterface()

        self.logger.debug("init done")
        self._init_complete = True

    def _update_values(self):
        """retrieves the values from the heat pump and updates the corresponding items"""
        # request all messages
        msgList = self._msgList.copy()
        msgList.update(self._extMsgList)
        newData = self._thzProtocol.requestData(msgList)

        now = datetime.datetime.now()

        # update status info
        stats = self._thzProtocol.getStats()
        for param in stats.keys():
            if param in self._params:
                # notify smarthome.py
                for item in self._params[param]['item']:
                    item(stats[param], source='thzRefresh')

        # parse new data and update items
        for param in newData:
            # make sure that the parameter exists
            if param in self._params:
                update = False

                # check for changes to reduce the update rate
                if not self._params[param]['lastValue'] == newData[param]:
                  # value changed
                  # update discrete values on every change
                  if (self._params[param]['lastValue'] in (0,1,2,3) and
                               newData[param] in (0,1,2,3)):
                      update = True
                      self.logger.debug('Discrete value changed - {0}: {1} => {2}'.format(param, self._params[param]['lastValue'], newData[param]))
                  else:
                    # the value is not discrete, check the minimum period
                    if self._params[param]['lastUpdate'] + self._min_update_period < now:
                      update = True
                      self.logger.debug('minimum period expired {0}: {1} => {2}'.format(param, self._params[param]['lastValue'], newData[param]))
                else:
                  # no change
                  # check the maximum update period
                  if self._params[param]['lastUpdate'] + self._max_update_period < now:
                      update = True
                      self.logger.debug('maximum period expired {0}: {1} => {2}'.format(param, self._params[param]['lastValue'], newData[param]))
                      
                if update:
                    # update the history
                    self._params[param]['lastUpdate'] = now
                    self._params[param]['lastValue'] = newData[param]

                    # notify smarthome.py
                    for item in self._params[param]['item']:
                        item(newData[param], source='thzRefresh')

        # provide the new data to the server instance
        self._curData = newData.copy()
        self._curData.update(stats)
        self._thzServer.updateData(self._curData)

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        self.alive = True
        try:
            self.scheduler_add('THZ', self._update_values, prio=5, cycle=self._poll_period)
            self._update_values()
            self._thzServer.start()
            self.logger.info("plugin started")
        except:
            self.logger.error(
                "thz: plugin start failed - {}".format(sys.exc_info()))

    def _logFullScan(self):
        """requests logging a full scan of the heat pump registers"""
        #self.logger.info('logFullScan started')
        self._thzProtocol.logFullScan()
        self._params['logFullScan']['item'][0]('done', source = 'thzRefresh')
        #self.logger.info('logFullScan completed')

    def _logRegister(self):
        """requests logging the specified heat pump register"""
        #self.logger.info('logRegister started')
        self._thzProtocol.logRegister(self._logRegisterId)
        self._params['logRegister']['item'][0]('done', source = 'thzRefresh')
        #self.logger.info('logRegister completed')

    #def _setRegister(self):
        """requests writing the hex value to the specified register"""
        #self.logger.info('logFullScan started')
        #self._thzProtocol.sendRawSetRequest()
        #self._params['logFullScan']['item'][0]('done', source = 'thzRefresh')
        #self.logger.info('logFullScan completed')

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called")
        self.alive = False
        try:
            self.scheduler_remove('THZ')
        except:
            self.logger.error("removing 'thz.update' from scheduler failed - {}".format(sys.exc_info()))
        try:
            self.scheduler_remove('ThzRegister')
        except:
            self.logger.error("removing 'ThzRegister' from scheduler failed - {}".format(sys.exc_info()))
        try:
            self.scheduler_remove('ThzScan')
        except:
            self.logger.error("removing 'ThzScan' from scheduler failed - {}".format(sys.exc_info()))
        self._thzProtocol.stop()
        self._thzServer.stop()

    def update_item(self, item, caller=None, source=None, dest=None):
        """forwards a new item value to the heat pump"""
        #self.logger.info('{}: caller={}, source={}'.format(item.conf['thz'], caller, source))
        # skip updates triggered by own refresh
        if source == 'thzRefresh':
          return

        try:
            if not self._thzProtocol.getMsgFromParameter(item.conf['thz']) == None:
              self._thzProtocol.sendSetRequest(item.conf['thz'], item())
            elif item.conf['thz'] == 'logFullScan':
              # request logging a full register scan
              # update the item status
              item('processing', source = 'thzRefresh')
              try:
                  self.scheduler_add('ThzScan', self._logFullScan, next=shtime.now() + datetime.timedelta(milliseconds=10))
                  #self.logger.info('logFullScan requested')
              except:
                  self.logger.error( "thz: scheduling logFullScan failed - {}".format(sys.exc_info()))
            elif item.conf['thz'] == 'logRegister':
              # request logging a register
              self._logRegisterId = item()
              # update the item status
              item('processing', source = 'thzRefresh')
              try:
                  self.scheduler_add('ThzRegister', self._logRegister, next=shtime.now() + datetime.timedelta(milliseconds=10))
                  #self.logger.info('logRegister requested')
              except:
                  self.logger.error( "thz: scheduling logRegister failed - {}".format(sys.exc_info()))
            else:
              self.logger.warning('thz: Invalid parameter name - {}'.format(item.conf['thz']))
        except:
            self.logger.warning(
                "thz: Setting parameter failed - {}".format(sys.exc_info()))

    def parse_item(self, item):
        """implements parsing the items associated with plugin parameters"""
        if 'thz' in item.conf:
            # validate the parameter name

            try:
              msgName = self._thzProtocol.getMsgFromParameter(item.conf['thz'])
            except:
              self.logger.error('thz: ### parse_item - {}'.format(sys.exc_info()))
            try:
              if msgName:
                  # a message parameter
                  # add the message name to the list
                  self._msgList[msgName] = 1

                  if not item.conf['thz'] in self._params:
                      # new parameter
                      self._params[item.conf['thz']] = {'lastValue': 0,
                                                        'lastUpdate': datetime.datetime.min,
                                                        'item': [item]}
                  else:
                      # parameter exists, associate the new item with it
                      self._params[item.conf['thz']]['item'].append(item)

                  if self._thzProtocol.isParameterWritable(item.conf['thz']):
                    return self.update_item
                  else:
                    return None
              elif (item.conf['thz'] in self._thzProtocol.getStats() or
                    item.conf['thz'] in specialRequests):
                # a plugin parameter
                if not item.conf['thz'] in self._params:
                    # new parameter
                    self._params[item.conf['thz']] = {'lastValue': 0,
                                                      'lastUpdate': datetime.datetime.min,
                                                      'item': [item]}
                else:
                    # parameter exists, associate the new item with it
                    self._params[item.conf['thz']]['item'].append(item)

                # provide the update function for special requests
                if item.conf['thz'] in specialRequests:
                    return self.update_item
              else:
                self.logger.warning('thz: No such parameter - {}'.format(item.conf['thz']))
            except:
              self.logger.error('thz: ### parse_item - {}'.format(sys.exc_info()))
 
        return None

    def subscribe(self, itemList):
        """implements a subscription mechanism for the ThzServer"""
        self._extMsgList = {}
        for item in itemList:
            self.logger.debug( "subscribing to {0}".format(item))
            msgName = None
            try:
                msgName = self._thzProtocol.getMsgFromParameter(item)
                if msgName:
                    # a message parameter
                    # add the message name to the list
                    self._extMsgList[msgName] = 1
            except:
                self.logger.error('thz: ### parse_item - {}'.format(sys.exc_info()))

        return self._curData


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



"""
Class ThzServer implements a UDP server.
"""
class ThzServer(threading.Thread):
    def __init__(self, thzDispatcher, host, port, logger):
        threading.Thread.__init__(self, name='THZ Server')

        self.alive = True
        self._thzDispatcher = thzDispatcher
        self._clients = {}
        self.logger = logger
        self.logger.info("Thz Server initialized")

        self._server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind((host, port))
        self._server.setblocking(0)


    def updateClient(self, client, data):
        try:
            msg = ""
            #self.logger.info("Updating client {0}".format(client))
            for item in self._clients[client]['itemList']:
              if item in data:
                # append to the list
                msg = msg + "{0}:{1};".format(item, data[item])
            if len(msg) > 0:
                #self.logger.info("Notify '{0}' sent to {1}".format(msg, client))
                msg = 'notify ' + msg
                self._server.sendto(msg.encode('ascii'), self._clients[client]['addr'])
        except:
            self.logger.error("Exception: {0}".format(sys.exc_info()))
            pass

    def updateData(self, data):
        for client in self._clients.keys():
            self.updateClient(client, data)

    def run(self):
        self.logger.debug("Thz Server entered run() method")
        while self.alive:
            try:
                now = datetime.datetime.now()
                #print now
                purgeList = []
                for addr,client in self._clients.items():
                    if client['lastContact'] + datetime.timedelta(seconds=CLIENT_TIMEOUT) < now:
                        # client connection timed out
                        purgeList.append(addr)
                for addr in purgeList:
                    self.logger.debug( "Removing client {0}".format(addr))
                    del self._clients[addr]

                inputs = [self._server]
                rready, wready, eready = select(inputs, [], [], POLL_INTERVAL)
                if rready == []:
                    time.sleep(1)
                    continue

                buf, remoteAddr  = self._server.recvfrom(10000)
                self.logger.debug("Received *{0}* from {1}:{2}".format(buf, remoteAddr[0], remoteAddr[1]))

                addr = "{0}:{1}".format(remoteAddr[0], remoteAddr[1])
            except:
                self.logger.error("Exception: {0}".format(sys.exc_info()))
                continue

            # parse the request
            try:
                try:
                    buf = buf.decode('ascii')
                    cmd, params = buf.split(' ')
                except:
                   cmd = buf

                if cmd == 'subscribe':
                    # update subscription
                    self._clients[addr] = { 'addr': remoteAddr, 'itemList': params.split(';') }
                    
                    #self.logger.info("item list {0}".format(self._clients[addr]['itemList']))
                    data = self._thzDispatcher.subscribe(self._clients[addr]['itemList'])
                    self.updateClient(addr, data)
                    self._clients[addr]['lastContact'] = datetime.datetime.now()

                elif cmd == 'set':
                    # set the parameters to the provided values
                    pass

                elif cmd == 'alive':
                    # update the timestamp
                    #self.logger.info("alive from {0}".format(addr))
                    self._clients[addr]['lastContact'] = datetime.datetime.now()

            except:
                self.logger.error("Exception: {0}".format(sys.exc_info()))

        self.logger.debug("Thz Server ends run() method")


    def stop(self):
        self.alive = False

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

