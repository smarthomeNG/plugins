#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2015 KNX-User-Forum e.V.            http://knx-user-forum.de/
# By Skender Haxhimolla 2015
# By Oliver Hinckel 2020-
#########################################################################
#  This file is part of SmartHomeNG.   https://github.com/smarthomeNG/
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
#  along with SmartHomeNG.  If not, see <http://www.gnu.org/licenses/>.
#  Skender Haxhimolla
#########################################################################

import asyncio
import functools
import logging

try:
    import slixmpp
except ImportError:
    slixmpp = None

from lib.plugin import Plugins
from lib.model.smartplugin import SmartPlugin


class XMPP(SmartPlugin):
    PLUGIN_VERSION = '2.0.0'
    ALLOW_MULTIINSTANCE = False

    def __init__(self, smarthome, jid, password, logic='XMPP'):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        if slixmpp is None:
            self.logger.error("Unable to import Python package 'slixmpp'")
            self._init_complete = False
            return
        server = self.get_parameter_value('server')

        # Check server parameter and default to port 5222
        if server is None:
            address = None
        elif ':' in server:
            parts = server.split(':')
            address = (parts[0].strip(), int(parts[1].strip()))
        else:
            address = (server, 5222)

        self._setup(jid, password, address, self.get_parameter_value('plugins'), self.get_parameter_value('join'))
        self.xmpp.use_ipv6 = self.get_parameter_value('use_ipv6')
        self._logic = logic
        self._sh = smarthome

    def _setup(self, jid, password, server, plugins, joins):
        """
        Create the slixmpp client on an event loop of its own, which run() drives in the plugin thread

        :param server: (host, port) to connect to, None for a DNS SRV lookup of the JID's domain
        :param plugins: names of the slixmpp plugins (XEPs) to register
        :param joins: chat rooms to join; registers xep_0045 if needed
        """
        self._server = server
        self._join = joins
        self._connected = 0
        self.alive = False

        # Enable MUC in case account should join channels
        if len(joins) and 'xep_0045' not in plugins:
            plugins.append('xep_0045')

        self._loop = asyncio.new_event_loop()
        self.set_asyncio_executor_names(self._loop)
        self.xmpp = slixmpp.ClientXMPP(jid, password, loop=self._loop)
        for plugin in plugins:
            self.xmpp.register_plugin(plugin)
        self.xmpp.add_event_handler('session_start', self.handleXMPPConnected)
        self.xmpp.add_event_handler('session_end', self.handleXMPPDisconnected)
        self.xmpp.add_event_handler('message', self.handleIncomingMessage)

    def run(self):
        """Connect and run the plugin's event loop until stop(); reconnect after a lost connection."""
        self.alive = True
        asyncio.set_event_loop(self._loop)
        while self.alive:
            self._connected = 1
            if self._server is not None:
                self.xmpp.connect(*self._server)
            else:
                self.xmpp.connect()
            self._loop.run_until_complete(self.xmpp.disconnected)
            self._connected = 0
            if self.alive:
                self._loop.run_until_complete(asyncio.sleep(5))
        self._loop.close()

    def stop(self):
        self.alive = False
        self.logger.info('Shutting Down XMPP Client')
        if self._loop.is_running():
            self._loop.call_soon_threadsafe(self._disconnect)

    def _disconnect(self):
        """Leave the chat rooms and close the connection; runs in the plugin's event loop."""
        if self._connected > 1:
            for chat in self._join:
                self.xmpp.plugin['xep_0045'].leave_muc(chat, self.xmpp.boundjid.bare)
        self.xmpp.disconnect()

    def parse_item(self, item):
        return None

    def parse_logic(self, logic):
        pass

    def __call__(self, to, msgsend):
        try:
            self.send(to, msgsend, mt='chat')
        except Exception as e:
            self.logger.error('XMPP: Could not send message {} to {}: {}'.format(msgsend, to, e))
        finally:
            try:
                pass
            except Exception:
                pass

    def is_connected(self):
        return self._connected > 1

    def handleXMPPConnected(self, event):
        self._connected = 2
        try:
            self.xmpp.send_presence(pstatus='Send me a message')
            self.xmpp.get_roster()
            for chat in self._join:
                self.xmpp.plugin['xep_0045'].join_muc(chat, self.xmpp.boundjid.bare)
        except Exception as e:
            self.logger.error('XMPP: Reconnecting, because can not set/get presence/roster: {}'.format(e))
            self.xmpp.reconnect()

    def handleXMPPDisconnected(self, event):
        self._connected = 0

    def handleIncomingMessage(self, msg):
        """
        Process incoming message stanzas. Be aware that this also
        includes MUC messages and error messages. It is usually
        a good idea to check the messages's type before processing
        or sending replies.

        Arguments:
            msg -- The received message stanza. See the documentation
                   for stanza objects and the Message stanza to see
                   how it may be used.
        """
        pass

    #       if msg['type'] in ('chat', 'normal'):
    #           msg.reply("Thanks for sending\n%(body)s" % msg).send()

    def update_item(self, item, caller=None, source=None, dest=None):
        pass

    def send(self, to, msgsend, mt='chat'):
        """
        Send a message via xmpp
        Requires:
                 mto = To whom eg 'skender@haxhimolla.im'
                 msgsend->mbody = body of the message eg 'Hello world'
                 mt->mtype = message type, could be 'chat' or 'groupchat'
        """
        self.logger.info('Sending message via XMPP. To: {0}\t Message: {1}'.format(to, msgsend))
        self._loop.call_soon_threadsafe(functools.partial(self.xmpp.send_message, mto=to, mbody=str(msgsend), mtype=mt))


class XMPPLogHandler(logging.Handler):
    _errors = {}

    def __init__(self, xmpp_plugin, xmpp_receiver, xmpp_receiver_type='chat'):
        logging.Handler.__init__(self)
        self._plugin = None
        self._xmpp_plugin = xmpp_plugin
        self._xmpp_receiver = xmpp_receiver
        self._xmpp_receiver_type = xmpp_receiver_type

    def emit(self, record):
        if self._plugin is None and Plugins.get_instance() is not None:
            self._plugin = Plugins.get_instance().return_plugin(self._xmpp_plugin)

        if self._plugin is not None and self._plugin.is_connected():
            self._plugin.send(self._xmpp_receiver, self.format(record), self._xmpp_receiver_type)


def main():
    bot = XMPP('skender@haxhimolla.im', 'mypassword')
    bot.run()


if __name__ == '__main__':
    main()
