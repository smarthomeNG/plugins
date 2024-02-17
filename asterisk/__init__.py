#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2012-2013 Marcus Popp                         marcus@popp.mx
#  Copyright 2020 Bernd Meiners                     Bernd.Meiners@mail.de
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
#########################################################################

import threading
import logging
import datetime

import lib.log
from lib.model.smartplugin import SmartPlugin
from lib.network import Tcp_client


class Asterisk(SmartPlugin):

    PLUGIN_VERSION = "1.4.2"

    DB = 'ast_db'
    DEV = 'ast_dev'
    BOX = 'ast_box'
    USEREVENT = 'ast_userevent'
    # use e.g. as Asterisk.BOX to keep in namespace

    def __init__(self, sh):
        """
        Initalizes the plugin.

        If you need the sh object at all, use the method self.get_sh() to get it. There should be almost no need for
        a reference to the sh object any more.

        Plugins have to use the new way of getting parameter values:
        use the SmartPlugin method get_parameter_value(parameter_name). Anywhere within the Plugin you can get
        the configured (and checked) value for a parameter by calling self.get_parameter_value(parameter_name). It
        returns the value in the datatype that is defined in the metadata.
        """

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        from bin.smarthome import VERSION
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        self.host = self.get_parameter_value('host')
        self.port = self.get_parameter_value('port')
        self.username = self.get_parameter_value('username')
        self.password = self.get_parameter_value('password')

        self.terminator = b'\r\n\r\n'
        self._client = Tcp_client(self.host, self.port, terminator=self.terminator)
        self._client.set_callbacks(connected=self.handle_connect, data_received=self.found_terminator)
        self._init_cmd = {'Action': 'Login', 'Username': self.username, 'Secret': self.password, 'Events': 'call,user,cdr'}
        self._reply_lock = threading.Condition()
        self._cmd_lock = threading.Lock()
        self._aid = 0
        self._devices = {}
        self._mailboxes = {}
        self._trigger_logics = {}
        self._log_in = lib.log.Log(self.get_sh(), 'env.asterisk.log.in', ['start', 'name', 'number', 'duration', 'direction'])

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        if self._client.connect():
            self.alive = True
        else:
            self.logger.error(f'Connection to {self.host}:{self.port} not possible, plugin not starting')

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called")
        if self._client.connected():
            self._client.close()
        self.alive = False
        self._reply_lock.acquire()
        self._reply_lock.notify()
        self._reply_lock.release()


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
        if self.has_iattr(item.conf, Asterisk.DEV):
            self._devices[self.get_iattr_value(item.conf, Asterisk.DEV)] = item
        if self.has_iattr(item.conf, Asterisk.BOX):
            self._mailboxes[self.get_iattr_value(item.conf, Asterisk.BOX)] = item
        if self.has_iattr(item.conf, Asterisk.DB):
            return self.update_item


    def parse_logic(self, logic):
        """
        Default plugin parse_logic method
        """
        if Asterisk.USEREVENT in logic.conf:
            event = logic.conf[Asterisk.USEREVENT]
            if event not in self._trigger_logics:
                self._trigger_logics[event] = [logic]
            else:
                self._trigger_logics[event].append(logic)


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
            self.logger.debug("Update item: {}, item has been changed outside this plugin".format(item.property.path))
            if self.has_iattr(item.conf, Asterisk.DB):
                value = item()
                if isinstance(value, bool):
                    value = int(item())
                self.db_write(self.get_iattr_value(item.conf, Asterisk.DB), value)


    def handle_connect(self, client):
        self._command(self._init_cmd, reply=False)
        for mb in self._mailboxes:
            mbc = self.mailbox_count(mb)
            if mbc is not None:
                self._mailboxes[mb](mbc[1])


    def _command(self, d, reply=True):
        """
        This function sends a command to the Asterisk Server
        """
        if not self._client.connected():
            return
        self._cmd_lock.acquire()
        if self._aid > 100:
            self._aid = 0
        self._aid += 1
        self._reply = None
        self._error = False
        if reply:
            d['ActionID'] = self._aid
        # self.logger.debug("Request {0} - sending: {1}".format(self._aid, d))
        self._reply_lock.acquire()
#
        # self.send(('\r\n'.join(['{0}: {1}'.format(key, value) for (key, value) in list(d.items())]) + '\r\n\r\n').encode())
        self._client.send(('\r\n'.join(['{0}: {1}'.format(key, value) for (key, value) in list(d.items())]) + '\r\n\r\n').encode())
#
        if reply:
            self._reply_lock.wait(2)
        self._reply_lock.release()
        reply = self._reply
        # self.logger.debug("Request {0} - reply: {1}".format(self._aid, reply))
        error = self._error
        self._cmd_lock.release()
        if error:
            raise Exception(error)
        return reply

    def db_read(self, key):
        """ Read from Asterisk database """
        fam, sep, key = key.partition('/')
        try:
            return self._command({'Action': 'DBGet', 'Family': fam, 'Key': key})
        except Exception:
            self.logger.warning("Asterisk: Problem reading {0}/{1}.".format(fam, key))

    def db_write(self, key, value):
        """ Write to Asterisk database """
        fam, sep, key = key.partition('/')
        try:
            return self._command({'Action': 'DBPut', 'Family': fam, 'Key': key, 'Val': value})
        except Exception as e:
            self.logger.warning("Asterisk: Problem updating {0}/{1} to {2}: {3}.".format(fam, key, value, e))

    def mailbox_count(self, mailbox, context='default'):
        """ get mailbox count tuple """
        try:
            return self._command({'Action': 'MailboxCount', 'Mailbox': mailbox + '@' + context})
        except Exception as e:
            self.logger.warning("Asterisk: Problem reading mailbox count {0}@{1}: {2}.".format(mailbox, context, e))
            return (0, 0)

    def call(self, source, dest, context, callerid=None):
        cmd = {'Action': 'Originate', 'Channel': source, 'Exten': dest, 'Context': context, 'Priority': '1', 'Async': 'true'}
        if callerid:
            cmd['Callerid'] = callerid
        try:
            self._command(cmd, reply=False)
        except Exception as e:
            self.logger.warning("Asterisk: Problem calling {0} from {1} with context {2}: {3}.".format(dest, source, context, e))

    def hangup(self, hang):
        active_channels = self._command({'Action': 'CoreShowChannels'})
        if active_channels is None:
            active_channels = []
        for channel in active_channels:
            device = self._get_device(channel)
            if device == hang:
                self._command({'Action': 'Hangup', 'Channel': channel}, reply=False)

    def found_terminator(self, client, data):
        """called then terminator is found 

        :param client: tcp client which is used for the connection
        :param str data: the response from asterisk server
        :return : None
        """
        if isinstance(data, bytes):
            data = data.decode()

        """
        the response will be normally like ``key: value``
        exception is start of communication which presents e.g.
        ```
        Asterisk Call Manager/5.0.4
        Response: Success
        Message: Authentication accepted
        ```
        The following code puts everything into the dict ``event``
        It only implements a very basic inspection of the response
        """ 
        self.logger.debug(f"data to inspect: {data}")
        event = {}
        for line in data.splitlines():
            key, sep, value = line.partition(': ')
            event[key] = value
        if 'ActionID' in event:
            aid = int(event['ActionID'])
            if aid != self._aid:
                return  # old request
            if 'Response' in event:
                if event['Response'] == 'Error':
                    self._error = event['Message']
                    self._reply_lock.acquire()
                    self._reply_lock.notify()
                    self._reply_lock.release()
                elif event['Message'] == 'Updated database successfully':
                    self._reply_lock.acquire()
                    self._reply_lock.notify()
                    self._reply_lock.release()
                elif event['Message'] == 'Mailbox Message Count':
                    self._reply = [int(event['OldMessages']), int(event['NewMessages'])]
                    self._reply_lock.acquire()
                    self._reply_lock.notify()
                    self._reply_lock.release()
        if 'Event' not in event:  # ignore
            return
        if event['Event'] == 'Newchannel':  # or data.startswith('Event: Newstate') ) and 'ChannelStateDesc: Ring' in data:
            device = self._get_device(event['Channel'])
            if device in self._devices:
                self._devices[device](True, 'Asterisk')
        elif event['Event'] == 'Hangup':
            self.scheduler_trigger('Ast.UpDev', self._update_devices, by='Asterisk')
        elif event['Event'] == 'CoreShowChannel':
            if self._reply is None:
                self._reply = [event['Channel']]
            else:
                self._reply.append(event['Channel'])
        elif event['Event'] == 'CoreShowChannelsComplete':
            self._reply_lock.acquire()
            self._reply_lock.notify()
            self._reply_lock.release()
        elif event['Event'] == 'UserEvent':
            if 'Source' in event:
                source = event['Source']
            else:
                source = None
            if 'Value' in data:
                value = event['Value']
            else:
                value = None
            if 'Destination' in data:
                destination = event['Destination']
            else:
                destination = None
            if event['UserEvent'] in self._trigger_logics:
                for logic in self._trigger_logics[event['UserEvent']]:
                    logic.trigger('Asterisk', source, value, destination)
        elif event['Event'] == 'DBGetResponse':
            self._reply = event['Val']
            self._reply_lock.acquire()
            self._reply_lock.notify()
            self._reply_lock.release()
        elif event['Event'] == 'MessageWaiting':
            mb = event['Mailbox'].split('@')[0]
            if mb in self._mailboxes:
                if 'New' in event:
                    self._mailboxes[mb](event['New'])
                else:
                    self._mailboxes[mb](0)
        elif event['Event'] == 'Cdr':
            end = self.get_sh().now()
            start = end - datetime.timedelta(seconds=int(event['Duration']))
            duration = event['BillableSeconds']
            if len(event['Source']) <= 4:
                direction = '=>'
                number = event['Destination']
            else:
                direction = '<='
                number = event['Source']
                name = event['CallerID'].split('<')[0].strip('" ')
                self._log_in.add([start, name, number, duration, direction])

    def _update_devices(self):
        active_channels = self._command({'Action': 'CoreShowChannels'})
        if active_channels is None:
            active_channels = []
        active_devices = list(map(self._get_device, active_channels))
        for device in self._devices:
            if device not in active_devices:
                self._devices[device](False, 'Asterisk')

    def _get_device(self, channel):
        channel, s, d = channel.rpartition('-')
        a, b, channel = channel.partition('/')
        return channel
