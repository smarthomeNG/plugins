#########################################################################
#  Ported by toggle, 2014
#########################################################################
#  This software is based on the FHEM implementation
#  https://github.com/mhop/fhem-mirror/blob/master/fhem/FHEM/00_THZ.pm
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

# This file implements the low level protocol of the THZ serial port.
#

import serial
import threading
import select
import multiprocessing
import time
import sys
import logging

logger = logging.getLogger('THZ')

# control characters
STX = b'\x02'
ETX = b'\x03'
DLE = b'\x10'
CAN = b'\x18'
CODE_2B = b'\x2B'

# state enumeration
IDLE = 0
MSG_BODY = 1
ESCAPING_DLE = 2
ESCAPING_2B = 3

###############################################################################
#
# This worker thread handles the serial port communication.
# The serial communication with the THZ/LWZ is time critical.
# Therefore, the code has to be executed in a separate thread.
#
###############################################################################
class PortHandler(threading.Thread):
  def __init__(self, serial_port, baudrate):
    threading.Thread.__init__(self, name='THZ PortHandler')
    try:
      self._fd = serial.Serial(serial_port, baudrate, timeout=5)
      logger.info('thz: Connected to serial port - {}'.format(serial_port))
    except:
      self._fd = None
      logger.error('thz: Failed to open serial port - {}'.format(sys.exc_info()))
    self._state = IDLE
    self._rxFrm = b''
    self._alive = True
    self._rxQueue = multiprocessing.Queue(maxsize = 0)
    self._txQueue = multiprocessing.Queue(maxsize = 0)
    self.rxFramingErrorCount = 0

###############################################################################
#
# processRxData() implements a state machine handling the received bytes
# according to the low-level protocol (message start/end, escaping of special
# characters).
#
###############################################################################
  def _processRxData(self):
    data = b'';
    while self._fd.inWaiting():
      data = self._fd.read(1);
      #logger.debug('{}'.format(data))
      if self._state == IDLE:
        self._rxFrm = b''
        if data == DLE:
          # discard
          #logger.debug("Discard DLE")
          pass
        elif data == STX:
          # acknowledge with DLE
          self._fd.write(DLE);

          # start new frame and switch state
          self._state = MSG_BODY
          #logger.debug("Ack STX")
        else:
          logger.warning("IDLE: Unexpected data {}".format(data))
          self._state = IDLE
          self.rxFramingErrorCount += 1

      elif self._state == MSG_BODY:
        if data == DLE:
          # escaping DLE
          self._state = ESCAPING_DLE
          #logger.debug("Escaping DLE")
        elif data == CODE_2B:
          # escaping 2B
          self._state = ESCAPING_2B
          #logger.debug("Escaping 2B")
          self._rxFrm += data;
        else:
          self._rxFrm += data;

      elif self._state == ESCAPING_2B:
        if data == CAN:
          # discard the CAN byte
          # return to collecting message bytes
          self._state = MSG_BODY
        else:
          logger.warning("ESCAPING_2B: Unexpected data {}".format(data))
          self._state = IDLE
          self.rxFramingErrorCount += 1

      elif self._state == ESCAPING_DLE:
        if data == DLE:
          self._rxFrm += data
          # return to collecting message bytes
          self._state = MSG_BODY
        elif data == ETX:
          # message end received
          self._rxQueue.put(self._rxFrm)
          #logger.debug ('Message received')
          #logger.debug ('Rx:' + ' '.join(format(x, '02x') for x in self._rxFrm))
          self._state = IDLE
          # acknowledge with DLE
          self._fd.write(DLE)
        else:
          logger.warning("ESCAPING_DLE: Unexpected data {}".format(data))
          self._rxFrm = b''
          self._state = IDLE
          self.rxFramingErrorCount += 1

###############################################################################
#
# processTxData() implements the low-level protocol encoding (message start/end,
# escaping of special characters).
#
###############################################################################
  def _processTxData(self):
    while not self._txQueue.empty():
      frm = self._txQueue.get()
      #logger.debug ('Tx:' + ' '.join(format(x, '02x') for x in frm))

      # escape DLE bytes
      prevIndex = 0
      while 1:
        index = frm.find(DLE, prevIndex)
        if index != -1:
          # insert a DLE (insert requires an integer ?!)
          frm.insert(index, ord(DLE))
          prevIndex = index + 2
        else:
          break

      # escape 0x2B bytes
      prevIndex = 0
      while 1:
        index = frm.find(CODE_2B, prevIndex)
        if index != -1:
          # insert a CAN code (insert requires an integer ?!)
          frm.insert(index+1, ord(CAN))
          prevIndex = index + 2
        else:
          break

      # add header and trailer
      frm = STX + frm + DLE + ETX
      logger.debug ('Tx: ' + ' '.join(format(x, '02x') for x in frm))

      # and finally send the message
      self._fd.write(frm)

###############################################################################
#
# run() implements the main loop.
#
###############################################################################
  def run(self):
    logger.info("PortHandler started")
    while self._alive:
      if not self._fd == None:
        try:
          # use select to implement a timeout, otherwise it is not
          # possible to stop the thread
          ready,_,_ = select.select([self._fd, self._txQueue._reader],[],[], 1)
          try:
            for event in ready:
              if event is self._fd:
                self._processRxData()

              if event is self._txQueue._reader:
                self._processTxData()
          except:
            logger.error("Data processing failed - {}".format(sys.exc_info()))
            if not self._fd == None:
              self._fd.close();
              self._fd = None

        except:
          logger.error("select failed - {}".format(sys.exc_info()))
          if not self._fd == None:
            self._fd.close();
            self._fd = None
      else:
        # discard tx messages
        while not self._txQueue.empty():
          self._txQueue.get()
        time.sleep(1)

###############################################################################
#
# stop() posts a request to stop the port handler thread.
#
###############################################################################
  def stop(self):
    logger.debug("PortHandler.stop() called")
    self._alive = False

###############################################################################
#
# sendData() puts a messages into the transmission queue to be processed in
# the main loop
#
###############################################################################
  def sendData(self, data):
    self._txQueue.put(data)

###############################################################################
#
# readData() reads a received message from the message queue.
#
###############################################################################
  def readData(self):
    try: 
      frm = self._rxQueue.get(block = True, timeout = 1)
    except multiprocessing.queues.Empty:
      frm = None
    return frm

###############################################################################
#
# isPortOpen() returns the state of the serial port.
#
###############################################################################
  def isPortOpen(self):
    if self._fd == None:
      return False
    else:
      return True

###############################################################################
#
# openPort() attempts to open the serial port
#
###############################################################################
  def openPort(self, serial_port, baudrate):
    try:
      self._fd = serial.Serial(serial_port, baudrate, timeout=5)
      logger.info('Reconnected to serial port - {}'.format(serial_port))
      return True
    except:
      self._fd = None
      return False
