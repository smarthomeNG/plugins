#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2017 Markus Garscha                 http://knx-user-forum.de/
#########################################################################
#  This file is part of SmartHome.py.    http://mknx.github.io/smarthome/
#
#  SmartHome.py is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHome.py is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHome.py. If not, see <http://www.gnu.org/licenses/>.
#########################################################################

#### Setup Phyton lib for telegram
# apt-get install python-pip
# pip install telepot

import time
import random
import datetime
import logging
import telepot
from lib.model.smartplugin import SmartPlugin

PLUGIN_ATTR_TOKEN		= 'token'
PLUGIN_ATTR_CHAT_IDS	= 'trusted_chat_ids'
ITEM_ATTR_MESSAGE		= 'telegram_message'

class Telegram(SmartPlugin):
    PLUGIN_VERSION = "1.1.2"
    ALLOW_MULTIINSTANCE = False

    # Storage Array for all items using telegram attributes
    _items = []
    _chat_ids = []

    # called, before items are loaded
    def __init__(self, smarthome, token='dummy', trusted_chat_ids='none'):
        self._sh = smarthome
        self.logger = logging.getLogger(__name__)

        self._bot = telepot.Bot(token)
        self.logger.info("Telegram bot is listening: {0}".format(self._bot.getMe()))

        self._bot.message_loop(self.message_handler)

        self._chat_ids = list(map(int, trusted_chat_ids.split(',')))

        if len(self._chat_ids) < 1:
            self.logger.info("No trusted chat ids configured!")
        self._name = "GAMA HOME"

    # triggered by sh.telegram(msg)
    def __call__(self, msg):
        self._bot.sendMessage(self._chat_id, msg)

    # called once at startup after all items are loaded
    def run(self):
        self.alive = True
        # if you want to create child threads, do not make them daemon = True!
        # They will not shutdown properly. (It's a python bug)

    def stop(self):
        self._bot.close()
        self.alive = False
	# close files and data connections

    # called for each item during startup, "item.conf" contains the attibute=value tuples
    def parse_item(self, item):
        if ITEM_ATTR_MESSAGE in item.conf:
            self.logger.debug("parse item: {0}".format(item))
            value = item.conf[ITEM_ATTR_MESSAGE]
            self._items.append(item)
            return self.update_item
        else:
            return None

    def parse_logic(self, logic):
        if 'xxx' in logic.conf:
            # self.function(logic['name'])
            pass

    # called each time an item changes.
    def update_item(self, item, caller=None, source=None, dest=None):
        if caller != 'smarthome-telegram':
            self.logger.info("update item: {0}".format(item.id()))

        if ITEM_ATTR_MESSAGE in item.conf:
            msg = item.conf[ITEM_ATTR_MESSAGE]
            self.logger.info("send Message: {}".format(msg))
            for cid in self._chat_ids:
                self._bot.sendMessage(cid, msg)

    def _broadcast(msg):
        for cid in self._chat_ids:
            self._bot.sendMessage(cid, msg)

    def message_handler(self, msg):
        self._chat_id = msg['chat']['id']
        tmp_chat_id = msg['chat']['id']
        command = msg['text']

        self.logger.info("[%d] command received: %s" % (self._chat_id, command))

        # /roll: just a dummy to test interaction
        if command == '/roll':
                self._bot.sendMessage(self._chat_id, random.randint(1,6))

	# /time: return server time
        elif command == '/time':
                self._bot.sendMessage(self._chat_id, str(datetime.datetime.now()))

        # /help: show available commands als keyboard
        elif command == '/help':
	        self._bot.sendMessage(self._chat_id, "choose", reply_markup={"keyboard":[["/roll","/hide"], ["/time","/list"]]})

        # /hide: hide keyboard
        elif command == '/hide':
                hide_keyboard = {'hide_keyboard': True}
                self._bot.sendMessage(self._chat_id, "I'll hide the keyboard", reply_markup=hide_keyboard)

        # /list: show registered items and value
        elif command == '/list':
            self.list_items()
            # self._bot.sendMessage(self._chat_id, "<b>bold</b> and <i>italic</i>", parse_mode='HTML')
            # self._bot.sendMessage(self._chat_id, "|ABC|DEF|\n|abc|def|", parse_mode='Markdown')
            # self._bot.sendMessage(self._chat_id, "*bold* _italic_ ~deleted~ `code` ````code\nblock```  [link](http://www.google.com)", parse_mode='Markdown')

        # /subscribe: TODO: subscribe to bot
        elif command == '/subscribe':
            tmp_chat_id = msg['chat']['id']
            if tmp_chat_id in self._chat_ids:
                self.logger.info("found [%d] in registered IDs" % (tmp_chat_id))
                pos = self._chat_ids.index(tmp_chat_id)
            else:
                self.logger.info("[%d] NOT found in registered IDs: [%s]" % (tmp_chat_id, ''.join(map(str, self._chat_ids))))
                pos = -1 
            if pos >= 0: # registered chat_id
                self._bot.sendMessage(tmp_chat_id, "Welcome at %s! Your are signed up already" % self._name)
            else:
                self._bot.sendMessage(tmp_chat_id, "Welcome at %s. Please register your ID: [%d]" % (self._name, tmp_chat_id))
        elif command == '/test':
            self._bot.sendMessage(tmp_chat_id, "not implemented yet")
        else:
            self._bot.sendMessage(tmp_chat_id, "unkown command %s" % (command))

    def list_items(self):
        text = ""
        for item in self._items:
            if item.type():
                text += "{0} = {1}\n".format(item.id(), item())
            else:
                text += "{0}\n".format(item.id())

        self._bot.sendMessage(self._chat_id, text)

# if __name__ == '__main__':
#     logging.basicConfig(level=logging.DEBUG)
#     myplugin = PluginName('smarthome-telegram')
#     myplugin.run()
