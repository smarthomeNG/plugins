#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2015 KNX-User-Forum e.V.            http://knx-user-forum.de/
# By Skender Haxhimolla 2015
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

import logging
import sleekxmpp

from lib.plugin import Plugins
from lib.model.smartplugin import *

class XMPP(SmartPlugin):

    PLUGIN_VERSION = "1.4.0"
    ALLOW_MULTIINSTANCE = False

    def __init__(self, smarthome, jid, password, logic='XMPP'):
        self.logger = logging.getLogger(__name__)
        server = self.get_parameter_value('server')
        plugins = self.get_parameter_value('plugins')
        joins = self.get_parameter_value('join')

        # Check server parameter and default to port 5222
        if server is None:
            self._server = None
        elif ':' in server:
            parts = server.split(':')
            self._server = (parts[0].strip(), parts[1].strip())
        else:
            self._server = (server, 5222)

        # Enable MUC in case account should join channels
        if len(joins) and 'xep_0045' not in plugins:
            plugins.append('xep_0045')

        self.xmpp = sleekxmpp.ClientXMPP(jid, password)
        for plugin in plugins:
            self.xmpp.register_plugin(plugin)
        self.xmpp.use_ipv6 = self.get_parameter_value('use_ipv6')
        self.xmpp.add_event_handler("session_start", self.handleXMPPConnected)
        self.xmpp.add_event_handler("message", self.handleIncomingMessage)
        self._logic = logic
        self._sh = smarthome
        self._join = joins

    def run(self):
        self.alive = True
        if self._server is not None:
            self.xmpp.connect(address=self._server)
        else:
            self.xmpp.connect()
        self.xmpp.process(threaded=True)

    def stop(self):
        self._run = False
        self.alive = False
        for chat in self._join:
            self.xmpp.plugin['xep_0045'].leaveMUC(chat, self.xmpp.boundjid.bare)
        self.logger.info("Shutting Down XMPP Client")
        self.xmpp.disconnect(wait=False)

    def parse_item(self, item):
        return None

    def parse_logic(self, logic):
        pass

    def __call__(self, to, msgsend):
        try:
            self.send(to, msgsend, mt='chat')
        except Exception as e:
            self.logger.error("XMPP: Could not send message {} to {}: {}".format(msgsend, to, e))
        finally:
            try:
                pass
            except:
                pass

    def handleXMPPConnected(self, event):
        try:
            self.xmpp.sendPresence(pstatus="Send me a message")
            self.xmpp.get_roster()
            for chat in self._join:
                self.xmpp.plugin['xep_0045'].joinMUC(chat, self.xmpp.boundjid.bare, wait=True)
        except Exception as e:
            self.logger.error("XMPP: Reconnecting, because can not set/get presence/roster: {}".format(e))
            self.xmpp.reconnect()

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
        self.logger.info("Sending message via XMPP. To: {0}\t Message: {1}".format(to, msgsend))
        self.xmpp.send_message(mto=to, mbody=str(msgsend), mtype=mt)


class XMPPLogHandler(logging.Handler):

    _errors = []

    def __init__(self, xmpp_plugin, xmpp_receiver, xmpp_receiver_type='chat'):
        logging.Handler.__init__(self)
        self._plugin = None
        self._xmpp_plugin = xmpp_plugin
        self._xmpp_receiver = xmpp_receiver
        self._xmpp_receiver_type = xmpp_receiver_type

    def emit(self, record):
        if self._plugin is None and Plugins.get_instance() is not None:
            self._plugin = Plugins.get_instance().return_plugin(self._xmpp_plugin)
            if self._plugin is None:
                if self._xmpp_plugin not in self._errors:
                    self._errors.append(self._xmpp_plugin)
                    logging.getLogger(__name__).error('Can not get XMPP plugin \'{}\' used to log messages via XMPP - trying later!'.format(self._xmpp_plugin))
            else:
                logging.getLogger(__name__).info('Configured XMPP logging using pluing {}'.format(self._xmpp_plugin))

        if self._plugin is not None:
            self._plugin.send(self._xmpp_receiver, self.format(record), self._xmpp_receiver_type)


def main():
    bot = XMPP("skender@haxhimolla.im", "mypassword")
    bot.run()

if __name__ == "__main__":
    main()
