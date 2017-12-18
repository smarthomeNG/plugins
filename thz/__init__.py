#!/usr/bin/env python3
#########################################################################
#  Copyright 2014 toggle
#########################################################################
#
#  THZ plugin for SmartHome.py.   http://mknx.github.com/smarthome/
#
#  This plugin is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This plugin is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this plugin. If not, see <http://www.gnu.org/licenses/>.
#########################################################################

import logging
import time
import sys
import datetime
from . import ThzProtocol
import socket as socket
from select import select
import threading

logger = logging.getLogger('THZ')

specialRequests = ['logFullScan', 'logRegister', 'setRegiter']
host = '0.0.0.0'
port = 57483
CLIENT_TIMEOUT = 60
POLL_INTERVAL = 10

###############################################################################
#
# Class THZ implements main control instance
#
###############################################################################
class THZ():

    def __init__(self, smarthome, serial_port='/dev/ttyUSB0', baudrate=115200, poll_period=300, min_update_period=86400, max_update_period=300):
        self._sh = smarthome
        self._poll_period = int(poll_period)
        self._min_update_period = datetime.timedelta(seconds=int(min_update_period))
        self._max_update_period = datetime.timedelta(seconds=int(max_update_period))
        self._params = {}
        self._thzProtocol = ThzProtocol.ThzProtocol(serial_port, int(baudrate))
        self._msgList = {}
        self._logRegisterId = None
        self._thzServer = ThzServer(self, host, port)
        self._curData = {}
        self._extMsgList = {}

###############################################################################
#
# _update_values() retrieves the values from the heat pump and
#                  updates the corresponding items
#
###############################################################################

    def _update_values(self):
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
                      logger.debug('Discrete value changed - {0}: {1} => {2}'.format(param, self._params[param]['lastValue'], newData[param]))
                  else:
                    # the value is not discrete, check the minimum period
                    if self._params[param]['lastUpdate'] + self._min_update_period < now:
                      update = True
                      logger.debug('minimum period expired {0}: {1} => {2}'.format(param, self._params[param]['lastValue'], newData[param]))
                else:
                  # no change
                  # check the maximum update period
                  if self._params[param]['lastUpdate'] + self._max_update_period < now:
                      update = True
                      logger.debug('maximum period expired {0}: {1} => {2}'.format(param, self._params[param]['lastValue'], newData[param]))
                      
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

###############################################################################
#
# run() main function
#
###############################################################################
    def run(self):
        self.alive = True
        try:
            self._sh.scheduler.add('THZ', self._update_values,
                               prio=5, cycle=self._poll_period)
            self._update_values()
            self._thzServer.start()
            logger.info("plugin started")
        except:
            logger.error(
                "thz: plugin start failed - {}".format(sys.exc_info()))

###############################################################################
#
# _logFullScan() requests logging a full scan of the heat pump registers
#
###############################################################################
    def _logFullScan(self):
        #logger.info('logFullScan started')
        self._thzProtocol.logFullScan()
        self._params['logFullScan']['item'][0]('done', source = 'thzRefresh')
        #logger.info('logFullScan completed')

###############################################################################
#
# _logRegister() requests logging the specified heat pump register
#
###############################################################################
    def _logRegister(self):
        #logger.info('logRegister started')
        self._thzProtocol.logRegister(self._logRegisterId)
        self._params['logRegister']['item'][0]('done', source = 'thzRefresh')
        #logger.info('logRegister completed')

###############################################################################
#
# _setRegister() requests writing the hex value to the specified register
#
###############################################################################
    #def _setRegister(self):
        #logger.info('logFullScan started')
        #self._thzProtocol.sendRawSetRequest()
        #self._params['logFullScan']['item'][0]('done', source = 'thzRefresh')
        #logger.info('logFullScan completed')

###############################################################################
#
# stop() stops the plugin execution
#
###############################################################################
    def stop(self):
        self.alive = False
        self._thzProtocol.stop()
        try:
            self._sh.scheduler.remove('THZ')
        except:
            logger.error(
                "thz: removing thz.update from scheduler failed - {}".format(sys.exc_info()))

###############################################################################
#
# update_item() forwards a new item value to the heat pump
#
###############################################################################
    def update_item(self, item, caller=None, source=None, dest=None):
        #logger.info('{}: caller={}, source={}'.format(item.conf['thz'], caller, source))
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
                  self._sh.scheduler.add('ThzScan', self._logFullScan, next=self._sh.now() + datetime.timedelta(milliseconds=10))
                  #logger.info('logFullScan requested')
              except:
                  logger.error( "thz: scheduling logFullScan failed - {}".format(sys.exc_info()))
            elif item.conf['thz'] == 'logRegister':
              # request logging a register
              self._logRegisterId = item()
              # update the item status
              item('processing', source = 'thzRefresh')
              try:
                  self._sh.scheduler.add('ThzRegister', self._logRegister, next=self._sh.now() + datetime.timedelta(milliseconds=10))
                  #logger.info('logRegister requested')
              except:
                  logger.error( "thz: scheduling logRegister failed - {}".format(sys.exc_info()))
            else:
              logger.warning('thz: Invalid parameter name - {}'.format(item.conf['thz']))
        except:
            logger.warning(
                "thz: Setting parameter failed - {}".format(sys.exc_info()))

###############################################################################
#
# parse_item() implements parsing the items associated with plugin parameters
#
###############################################################################
    def parse_item(self, item):
        if 'thz' in item.conf:
            # validate the parameter name

            try:
              msgName = self._thzProtocol.getMsgFromParameter(item.conf['thz'])
            except:
              logger.error('thz: ### parse_item - {}'.format(sys.exc_info()))
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
                logger.warning('thz: No such parameter - {}'.format(item.conf['thz']))
            except:
              logger.error('thz: ### parse_item - {}'.format(sys.exc_info()))
 
        return None

###############################################################################
#
# subscribe() implements a subscription mechanism for the ThzServer
#
###############################################################################
    def subscribe(self, itemList):
      self._extMsgList = {}
      for item in itemList:
        logger.debug( "subscribing to {0}".format(item))
        msgName = None
        try:
          msgName = self._thzProtocol.getMsgFromParameter(item)
          if msgName:
              # a message parameter
              # add the message name to the list
              self._extMsgList[msgName] = 1
        except:
          logger.error('thz: ### parse_item - {}'.format(sys.exc_info()))

      return self._curData

###############################################################################
#
# Class ThzServer implements a UDP server.
#
###############################################################################
class ThzServer(threading.Thread):
  def __init__(self, thzDispatcher, host, port):
    threading.Thread.__init__(self, name='thzServer')

    self._thzDispatcher = thzDispatcher
    self._clients = {}
    logger.info("ThzServer initialized")

    self._server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    self._server.bind((host, port))
    self._server.setblocking(0)


  def updateClient(self, client, data):
    try:
      msg = ""
      #logger.info("Updating client {0}".format(client))
      for item in self._clients[client]['itemList']:
        if item in data:
          # append to the list
          msg = msg + "{0}:{1};".format(item, data[item])
      if len(msg) > 0:
        #logger.info("Notify '{0}' sent to {1}".format(msg, client))
        msg = 'notify ' + msg
        self._server.sendto(msg.encode('ascii'), self._clients[client]['addr'])
    except:
      logger.error("Exception: {0}".format(sys.exc_info()))
      pass

  def updateData(self, data):
      for client in self._clients.keys():
        self.updateClient(client, data)

  def run(self):
    logger.info("ThzServer started")
    while 1:

      try:
        now = datetime.datetime.now()
        #print now
        purgeList = []
        for addr,client in self._clients.items():
          if client['lastContact'] + datetime.timedelta(seconds=CLIENT_TIMEOUT) < now:
            # client connection timed out
            purgeList.append(addr)
        for addr in purgeList:
          #logger.info( "Removing client {0}".format(addr))
          del self._clients[addr]

        inputs = [self._server]
        rready, wready, eready = select(inputs, [], [], POLL_INTERVAL)
        if rready == []:
          time.sleep(1)
          continue

        buf, remoteAddr  = self._server.recvfrom(10000)
        #logger.info("Received *{0}* from {1}:{2}".format(buf, remoteAddr[0], remoteAddr[1]))

        addr = "{0}:{1}".format(remoteAddr[0], remoteAddr[1])
      except:
        logger.error("Exception: {0}".format(sys.exc_info()))
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

          #logger.info("item list {0}".format(self._clients[addr]['itemList']))
          data = self._thzDispatcher.subscribe(self._clients[addr]['itemList'])
          self.updateClient(addr, data)
          self._clients[addr]['lastContact'] = datetime.datetime.now()

        elif cmd == 'set':
          # set the parameters to the provided values
          pass

        elif cmd == 'alive':
          # update the timestamp
          #logger.info("alive from {0}".format(addr))
          self._clients[addr]['lastContact'] = datetime.datetime.now()

      except:
        logger.error("Exception: {0}".format(sys.exc_info()))

