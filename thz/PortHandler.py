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

"""
This file provides the class PortHandler which 
implements the low level protocol of the THZ serial port.
The serial communication with the THZ/LWZ is time critical therefor the
handling is done with a seperate worker thread.
"""

import serial
import threading
import select
import multiprocessing
import time
import sys
import logging

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


class PortHandler(threading.Thread):
    def __init__(self, serial_port, baudrate, logger):
        threading.Thread.__init__(self, name='THZ PortHandler')
        self.logger = logger
        try:
          self._fd = serial.Serial(serial_port, baudrate, timeout=5)
          self.logger.info('thz: Connected to serial port - {}'.format(serial_port))
        except:
          self._fd = None
          self.logger.error('thz: Failed to open serial port - {}'.format(sys.exc_info()))
        self._state = IDLE
        self._rxFrm = b''
        self._alive = True
        self._rxQueue = multiprocessing.Queue(maxsize = 0)
        self._txQueue = multiprocessing.Queue(maxsize = 0)
        self.rxFramingErrorCount = 0

    def _processRxData(self):
        """
        processRxData() implements a state machine handling the received bytes
        according to the low-level protocol (message start/end, escaping of special
        characters).
        """
        data = b'';
        while self._fd.inWaiting():
          data = self._fd.read(1);
          #self.logger.debug('{}'.format(data))
          if self._state == IDLE:
            self._rxFrm = b''
            if data == DLE:
              # discard
              #self.logger.debug("Discard DLE")
              pass
            elif data == STX:
              # acknowledge with DLE
              self._fd.write(DLE);

              # start new frame and switch state
              self._state = MSG_BODY
              #self.logger.debug("Ack STX")
            else:
              self.logger.warning("IDLE: Unexpected data {}".format(data))
              self._state = IDLE
              self.rxFramingErrorCount += 1

          elif self._state == MSG_BODY:
            if data == DLE:
              # escaping DLE
              self._state = ESCAPING_DLE
              #self.logger.debug("Escaping DLE")
            elif data == CODE_2B:
              # escaping 2B
              self._state = ESCAPING_2B
              #self.logger.debug("Escaping 2B")
              self._rxFrm += data;
            else:
              self._rxFrm += data;

          elif self._state == ESCAPING_2B:
            if data == CAN:
              # discard the CAN byte
              # return to collecting message bytes
              self._state = MSG_BODY
            else:
              self.logger.warning("ESCAPING_2B: Unexpected data {}".format(data))
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
              #self.logger.debug ('Message received')
              #self.logger.debug ('Rx:' + ' '.join(format(x, '02x') for x in self._rxFrm))
              self._state = IDLE
              # acknowledge with DLE
              self._fd.write(DLE)
            else:
              self.logger.warning("ESCAPING_DLE: Unexpected data {}".format(data))
              self._rxFrm = b''
              self._state = IDLE
              self.rxFramingErrorCount += 1

    def _processTxData(self):
        """implements the low-level protocol encoding (message start/end, escaping of special characters"""
        while not self._txQueue.empty():
          frm = self._txQueue.get()
          #self.logger.debug ('Tx:' + ' '.join(format(x, '02x') for x in frm))

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
          self.logger.debug ('Tx: ' + ' '.join(format(x, '02x') for x in frm))

          # and finally send the message
          self._fd.write(frm)

    def run(self):
        """implements the main loop of the port handler"""
        self.logger.info("PortHandler started")
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
                self.logger.error("Data processing failed - {}".format(sys.exc_info()))
                if not self._fd == None:
                  self._fd.close();
                  self._fd = None

            except:
              self.logger.error("select failed - {}".format(sys.exc_info()))
              if not self._fd == None:
                self._fd.close();
                self._fd = None
          else:
            # discard tx messages
            while not self._txQueue.empty():
              self._txQueue.get()
            time.sleep(1)

    def stop(self):
        """posts a request to stop the port handler thread"""
        self.logger.debug("PortHandler.stop() called")
        self._alive = False

    def sendData(self, data):
        """puts a messages into the transmission queue to be processed in the main loop"""
        self._txQueue.put(data)

    def readData(self):
        """reads a received message from the message queue."""
        try: 
          frm = self._rxQueue.get(block = True, timeout = 1)
        except multiprocessing.queues.Empty:
          frm = None
        return frm

    def isPortOpen(self):
        """returns the state of the serial port"""
        if self._fd == None:
            return False
        else:
            return True

    def openPort(self, serial_port, baudrate):
        """attempts to open the serial port"""
        try:
            self._fd = serial.Serial(serial_port, baudrate, timeout=5)
            self.logger.info('Reconnected to serial port - {}'.format(serial_port))
            return True
        except:
            self._fd = None
            return False
