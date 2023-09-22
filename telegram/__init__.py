#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2017 Markus Garscha                 http://knx-user-forum.de/
#           2018-2023 Ivan De Filippis
#           2018-2021 Bernd Meiners                 Bernd.Meiners@mail.de
#########################################################################
#
#  This file is part of SmartHomeNG.
#
#  Telegram Plugin for querying and updating items or sending messages via Telegram
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

import datetime
import time
import logging
import asyncio
import queue
import re
import requests
import traceback
from io import BytesIO

from queue import Queue
from lib.logic import Logics
from lib.model.smartplugin import SmartPlugin

from .webif import WebInterface

try:
    from telegram import Update
    from telegram.ext import Updater, Application, CommandHandler, ContextTypes, MessageHandler, filters
    from telegram.error import TelegramError
    REQUIRED_PACKAGE_IMPORTED = True
except Exception as e:
    REQUIRED_PACKAGE_IMPORTED = e

ITEM_ATTR_MESSAGE         = 'telegram_message'            # Send message on item change
ITEM_ATTR_CONDITION       = 'telegram_condition'          # when to send the message, if not given send any time,
                                                          #   if on_change_only then just if the item's current value differs from the previous value
ITEM_ATTR_INFO            = 'telegram_info'               # read items with specific item-values
ITEM_ATTR_TEXT            = 'telegram_text'               # write message-text into the item
ITEM_ATTR_MATCHREGEX      = 'telegram_value_match_regex'  # check a value against a condition before sending a message
ITEM_ATTR_CHAT_IDS        = 'telegram_chat_ids'           # specifying chat IDs and write access
ITEM_ATTR_MSG_ID          = 'telegram_message_chat_id'    # chat_id the message should be sent to
ITEM_ATTR_CONTROL         = 'telegram_control'            # control(=change) item-values (bool/num)

MESSAGE_TAG_ID            = '[ID]'
MESSAGE_TAG_NAME          = '[NAME]'
MESSAGE_TAG_VALUE         = '[VALUE]'
MESSAGE_TAG_CALLER        = '[CALLER]'
MESSAGE_TAG_SOURCE        = '[SOURCE]'
MESSAGE_TAG_DEST          = '[DEST]'

class Telegram(SmartPlugin):

    PLUGIN_VERSION = "2.0.1"

    _items = []               # all items using attribute ``telegram_message``
    _items_info = {}          # dict used whith the info-command: key = attribute_value, val= item_list telegram_info
    _items_text_message = []  # items in which the text message is written ITEM_ATTR_TEXT
    _items_control = {}       # dict used whith the control-command:
    _chat_ids_item = {}       # an item with a dict of chat_id and write access
    _waitAnswer = None        # wait a specific answer Yes/No - or num (change_item)
    _queue = None             # queue for the messages to be sent

    def __init__(self, sh):
        """
        Initializes the Telegram plugin
        The params are documented in ``plugin.yaml`` and values will be obtained through get_parameter_value(parameter_name)
        """

        self.logger.info('Init telegram plugin')

        # Call init code of parent class (SmartPlugin or MqttPlugin)
        super().__init__()
        if not self._init_complete:
            return

        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"init {__name__}")
        self._init_complete = False

        # Exit if the required package(s) could not be imported
        if REQUIRED_PACKAGE_IMPORTED is not True:
            self.logger.error(f"{self.get_fullname()}: Unable to import Python package 'python-telegram-bot' [{REQUIRED_PACKAGE_IMPORTED}]")
            return

        self._loop = asyncio.new_event_loop()   # new_event is required for multi-instance
        asyncio.set_event_loop(self._loop)

        self.alive = False
        self._name = self.get_parameter_value('name')
        self._token = self.get_parameter_value('token')

        self._welcome_msg = self.get_parameter_value('welcome_msg')
        self._bye_msg = self.get_parameter_value('bye_msg')
        self._no_access_msg = self.get_parameter_value('no_access_msg')
        self._no_write_access_msg = self.get_parameter_value('no_write_access_msg')
        self._long_polling_timeout = self.get_parameter_value('long_polling_timeout')
        self._pretty_thread_names = self.get_parameter_value('pretty_thread_names')
        self._resend_delay = self.get_parameter_value('resend_delay')
        self._resend_attemps = self.get_parameter_value('resend_attemps')

        self._bot =  None
        self._queue = Queue()

        self._application = Application.builder().token(self._token).build()

        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("adding command handlers to application")

        self._application.add_error_handler(self.eHandler)
        self._application.add_handler(CommandHandler('time', self.cHandler_time))
        self._application.add_handler(CommandHandler('help', self.cHandler_help))
        self._application.add_handler(CommandHandler('hide', self.cHandler_hide))
        self._application.add_handler(CommandHandler('list', self.cHandler_list))
        self._application.add_handler(CommandHandler('info', self.cHandler_info))
        self._application.add_handler(CommandHandler('start', self.cHandler_start))
        self._application.add_handler(CommandHandler('lo', self.cHandler_lo))
        self._application.add_handler(CommandHandler('tr', self.cHandler_tr))
        self._application.add_handler(CommandHandler('control', self.cHandler_control))
        # Filters.text includes also commands, starting with ``/`` so it is needed to exclude them.
        self._application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self.mHandler))

        self.init_webinterface()
        if not self.init_webinterface(WebInterface):
            self.logger.error("Unable to start Webinterface")
            self._init_complete = False
        else:
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug("Init complete")

        self._init_complete = True

    def __call__(self, msg, chat_id=None):
        """
        Provide a way to use the plugin to easily send a message
        """
        if self.alive:
            if chat_id is None:
                self.msg_broadcast(msg)
            else:
                self.msg_broadcast(msg, chat_id)

    def run(self):
        """
        This is called when the plugins thread is about to run
        """
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("Run method called")

        self.logics = Logics.get_instance()  # Returns the instance of the Logics class, to be used to access the logics-api

        self.alive = True

        self._loop.run_until_complete(self.run_coros())
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"Run method ended")

    def stop(self):
        """
        This is called when the plugins thread is about to stop
        """
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("stop telegram plugin")

        try:
            if self._bye_msg:
                cids = [key for key, value in self._chat_ids_item().items() if value == 1]
                self.msg_broadcast(self._bye_msg, chat_id=cids)
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug("sent bye message")
        except Exception as e:
            self.logger.error(f"could not send bye message [{e}]")

        time.sleep(1)
        self.alive = False  # Clears the infiniti loop in sendQueue
        try:
            asyncio.gather(self._taskConn,  self._taskQueue)
            self.disconnect()

            if self._loop.is_running():
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug("stop telegram _loop.is_running")
                while self._loop.is_running():
                    asyncio.sleep(0.1)
            self._loop.close()
        except Exception as e:
            self.logger.error(f"An error occurred while stopping the plugin [{e}]")

        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("stop telegram plugin finished")

    async def run_coros(self):
        """
        This method run multiple coroutines concurrently using asyncio
        """
        self._taskConn = asyncio.create_task(self.connect())
        self._taskQueue = asyncio.create_task(self.sendQueue())
        await asyncio.gather(self._taskConn, self._taskQueue)

    async def connect(self):
        """
        Connects
        """
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("connect method called")
        try:
            await self._application.initialize()
            await self._application.start()
            self._updater = self._application.updater

            q = await self._updater.start_polling(timeout=self._long_polling_timeout, error_callback=self.error_handler)

            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug(f"started polling the updater, Queue is {q}")

            self._bot = self._updater.bot
            self.logger.info(f"Telegram bot is listening: {await self._updater.bot.getMe()}")
            if self._welcome_msg:
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug(f"sent welcome message {self._welcome_msg}")
                cids = [key for key, value in self._chat_ids_item().items() if value == 1]
                self.msg_broadcast(self._welcome_msg, chat_id=cids)

        except TelegramError as e:
            # catch Unauthorized errors due to an invalid token
            self.logger.error(f"Unable to start up Telegram conversation. Maybe an invalid token? {e}")
            return False
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("connect method end")

    def error_handler(self, update, context):
        """
        Just logs an error in case of a problem
        """
        try:
            self.logger.warning(f'Update {update} caused error {context.error}')
        except Exception:
            pass

    async def sendQueue(self):
        """
        Waiting for messages to be sent in the queue and sending them to Telegram.
        The queue expects a dictionary with various parameters
        dict txt:   {"msgType":"Text", "msg":msg, "chat_id":chat_id, "reply_markup":reply_markup, "parse_mode":parse_mode }
        dict photo: {"msgType":"Photo", "photofile_or_url":photofile_or_url, "chat_id":chat_id, "caption":caption, "local_prepare":local_prepare}
        """
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"sendQueue called - queue: [{self._queue}]")
        while self.alive:           # infinite loop until self.alive = False
            try:
                message = self._queue.get_nowait()
            except queue.Empty:     # no message to send in the queue
                await asyncio.sleep(1)
            except Exception as e:
                self.logger.debug(f"messageQueue Exception [{e}]")
            else:                   # message to be sent in the queue
                resendDelay = 0
                resendAttemps = 0
                if "resendDelay" in message:
                    resendDelay = message["resendDelay"]
                if "resendAttemps" in message:
                    resendAttemps =  message["resendAttemps"]

                if resendDelay <= 0:
                    if self.logger.isEnabledFor(logging.DEBUG):
                        self.logger.debug(f"message queue {message}")
                    if message["msgType"] == "Text":
                        result = await self.async_msg_broadcast(message["msg"], message["chat_id"], message["reply_markup"], message["parse_mode"])
                    elif message["msgType"] == "Photo":
                        result = await self.async_photo_broadcast(message["photofile_or_url"], message["caption"], message["chat_id"], message["local_prepare"])

                    # An error occurred while sending - result: list containing the dic of the failed send attempt
                    if result:
                        for res in result:
                            resendAttemps+=1
                            if resendAttemps > self._resend_attemps:
                                if self.logger.isEnabledFor(logging.DEBUG):
                                    self.logger.debug(f"don't initiate any further send attempts for: {res}")
                                break
                            else:
                                resendDelay =  self._resend_delay

                            # Including the sendDelay and sendAttempts in the queue message for the next send attempt.
                            res["resendDelay"] = resendDelay
                            res["resendAttemps"] = resendAttemps

                            if self.logger.isEnabledFor(logging.DEBUG):
                                self.logger.debug(f"new send attempt by placing it in the queue. sendAttemps:{resendAttemps} sendDelay:{resendDelay} [{res}]")
                            self._queue.put(res) # new send attempt by replacing the message in the queue
                else:
                    message["resendDelay"] = resendDelay - 1
                    await asyncio.sleep(1)
                    self._queue.put(message)    # new send attempt by replacing the message in the queue

        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("sendQueue method end")

    async def disconnect(self):
        """
        Stop listening to push updates and shutdown
        """
        self.logger.info(f"disconnecting")

        await self._application.updater.stop()
        await self._application.stop()
        await self._application.shutdown()

        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"disconnect end")

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        :param item: The item to process.
        """
        if self.has_iattr(item.conf, ITEM_ATTR_CHAT_IDS):
            if self._chat_ids_item:
                self.logger.warning(f"Item: {item.id()} declares chat_id for telegram plugin which are already defined, aborting!")
            else:
                self._chat_ids_item = item

        if self.has_iattr(item.conf, ITEM_ATTR_MESSAGE):
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug(f"parse item: {item}")
            self._items.append(item)
            return self.update_item

        """
        For valid commands also see https://core.telegram.org/bots#commands
        In general they are allowed to have 32 characters, use latin letters, numbers or an underscore
        """
        if self.has_iattr(item.conf, ITEM_ATTR_INFO):
            key = self.get_iattr_value(item.conf, ITEM_ATTR_INFO)
            if self.is_valid_command(key):
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug(f"parse item: {item} with command: {key}")
                if key in self._items_info:
                    self._items_info[key].append(item)
                    if self.logger.isEnabledFor(logging.DEBUG):
                        self.logger.debug(f"Append a new item '{item}' to command '{key}'")
                else:
                    self._items_info[key] = [item]  # dem dict neue Liste hinzufuegen
                    if self.logger.isEnabledFor(logging.DEBUG):
                        self.logger.debug(f"Register new command '{key}', add item '{item}' and register a handler")
                    # add a handler for each info-attribute
                    self._application.add_handler(CommandHandler(key, self.cHandler_info_attr))
                return self.update_item
            else:
                self.logger.error(f"Command '{key}' chosen for item '{item}' is invalid for telegram botfather")

        if self.has_iattr(item.conf, ITEM_ATTR_TEXT):
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug(f"parse item: {item.id()}")
            value = self.get_iattr_value(item.conf, ITEM_ATTR_TEXT)
            if value in ['true', 'True', '1']:
                self._items_text_message.append(item)
            return self.update_item

        if self.has_iattr(item.conf, ITEM_ATTR_CONTROL):
            attr = self.get_iattr_value(item.conf, ITEM_ATTR_CONTROL)

            key = item.id()     # default
            changeType = 'toggle'
            question = ''
            timeout = 20
            min = None
            max = None

            par_list = attr.split(',')  # Parameter from attr example: 'name:test, changeType:toggle, question:wirklich umnschalten?'
            for par in par_list:
                k,v = par.split(':')
                if 'name' in k:
                    key = v
                if 'type' in k:
                    changeType = v
                if 'question' in k:
                    question = v
                if 'timeout' in k:
                    timeout = v
                if 'min' in k:
                    min = v
                if 'max' in k:
                    max = v

            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug(f"parse control-item: {item} with command: {key}")

            dicCtl = {'name': key, 'type': changeType, 'item': item, 'question': question, 'timeout': timeout, 'min': min, 'max': max}

            if key not in self._items_control:
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug(f"Append a new control-item '{item}' to command '{key}'")
                self._items_control[key] = dicCtl  # add to dict
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug(f"Register new command '{key}', add item '{item}' and register a handler")
                # add a handler for each control-attribute
                self._application.add_handler(CommandHandler(key, self.cHandler_control_attr))
            return self.update_item

        return None

    def is_valid_command(self, cmd):
        if not isinstance(cmd, str):
            return False
        if len(cmd) > 32:
            return False
        rec = re.compile(r'[^A-Za-z0-9_]')
        return not bool(rec.search(cmd))

    # def parse_logic(self, logic):
    #    if 'xxx' in logic.conf:
    #        # self.function(logic['name'])
    #        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Called each time an item changed in SmartHomeNG
        """
        if caller != self.get_fullname():
            self.logger.info(f"update item: {item.id()}")

        if self.has_iattr(item.conf, ITEM_ATTR_CHAT_IDS):
            if self._chat_ids_item:
                self.logger.info(f"Item: {item.id()} declares chat_id for telegram plugin which are already defined, will be overwritten!")
            self._chat_ids_item = item

        if self.has_iattr(item.conf, ITEM_ATTR_MESSAGE):
            msg_txt_tmpl = self.get_iattr_value(item.conf, ITEM_ATTR_MESSAGE)

            item_id = item.id()
            if item.property.type == 'bool':
                item_value = item()
                item_value = '1' if item_value is True else '0' if item_value is False else None
            else:
                item_value = f"{item()}"

            if self.has_iattr(item.conf, ITEM_ATTR_MATCHREGEX):
                val_match = self.get_iattr_value(item.conf, ITEM_ATTR_MATCHREGEX)
                self.logger.info(f"val_match: {val_match}")

                # TO_TEST: ITEM_ATTR_MATCHREGEX
                p = re.compile(val_match)
                m = p.match(item_value)
                if m:
                    self.logger.info(f"Match found: {m.group()}")
                else:
                    self.logger.info(f"No match: {val_match} in: {item_value}")
                    return

            caller = "None" if caller is None else str(caller)
            source = "None" if source is None else str(source)
            dest = "None" if dest is None else str(dest)

            if self.has_iattr(item.conf, 'name'):
                item_name = self.get_iattr_value(item.conf, 'name')
            else:
                item_name = 'NONAME'

            # replace Tags with id,value,caller,source,dest,...
            msg_txt = msg_txt_tmpl.replace(MESSAGE_TAG_ID, item_id)
            msg_txt = msg_txt.replace(MESSAGE_TAG_NAME, item_name)
            msg_txt = msg_txt.replace(MESSAGE_TAG_VALUE, item_value)
            msg_txt = msg_txt.replace(MESSAGE_TAG_CALLER, caller)
            msg_txt = msg_txt.replace(MESSAGE_TAG_SOURCE, source)
            msg_txt = msg_txt.replace(MESSAGE_TAG_DEST, dest)

            # checking, if message should be send to specific chat-id
            if self.has_iattr(item.conf, ITEM_ATTR_MSG_ID):
                msg_chat_id = self.get_iattr_value(item.conf, ITEM_ATTR_MSG_ID)
                msg_chat_id_txt = str(msg_chat_id)
            else:
                msg_chat_id = None
                msg_chat_id_txt = 'all'

            # restricing send by a condition set
            if self.has_iattr(item.conf, ITEM_ATTR_CONDITION):
                cond = self.get_iattr_value(item.conf, ITEM_ATTR_CONDITION).lower()
                if cond == "on_change":
                    if item.property.value != item.property.last_value and item.property.last_update <= item.property.last_change:
                        if self.logger.isEnabledFor(logging.DEBUG):
                            self.logger.debug(f"condition {cond} met: {item.property.value}!={item.property.last_value}, last_update_age {item.property.last_update}, last_change_age {item.property.last_change}")
                    else:
                        if self.logger.isEnabledFor(logging.DEBUG):
                            self.logger.debug(f"condition {cond} not met: {item.property.value}=={item.property.last_value}, last_update_age {item.property.last_update}, last_change_age {item.property.last_change}")
                        return
                elif cond == "on_update":
                    # this is standard behaviour
                    pass
                else:
                    if self.logger.isEnabledFor(logging.DEBUG):
                        self.logger.debug(f"ignoring unknown condition {cond}")

            # sending the message
            # if self.logger.isEnabledFor(logging.DEBUG):
                # self.logger.debug(f"send Message: {msg_txt} to Chat_ID {msg_chat_id_txt}")
            self.msg_broadcast(msg_txt, msg_chat_id)

    async def async_msg_broadcast(self, msg, chat_id=None, reply_markup=None, parse_mode=None):
        """
        Send a message to the given chat_id

        :param msg: message to send
        :param chat_id: a chat id or a list of chat ids to identificate the chat(s)
        :param reply_markup:
        :param parse_mode:
        """
        sendResult = []
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"async msg_broadcast called")

        for cid in self.get_chat_id_list(chat_id):
            try:
                response = await self._bot.send_message(chat_id=cid, text=msg, reply_markup=reply_markup, parse_mode=parse_mode)
                if response:
                    if self.logger.isEnabledFor(logging.DEBUG):
                        self.logger.debug(f"Message sent:[{msg}] to Chat_ID:[{cid}] Bot:[{self._bot.bot}] response:[{response}]")
                else:
                    sendResult.append({"msgType":"Text", "msg":msg, "chat_id":cid, "reply_markup":reply_markup, "parse_mode":parse_mode })
                    self.logger.error(f"could not broadcast to chat id [{cid}] response: {response}")
            except TelegramError as e:
                sendResult.append({"msgType":"Text", "msg":msg, "chat_id":cid, "reply_markup":reply_markup, "parse_mode":parse_mode })
                self.logger.error(f"could not broadcast to chat id [{cid}] due to error {e}")
            except Exception as e:
                sendResult.append({"msgType":"Text", "msg":msg, "chat_id":cid, "reply_markup":reply_markup, "parse_mode":parse_mode })
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug(f"Exception '{e}' occurred, please inform plugin maintainer!")
        if not sendResult:
            return None
        else:
            return sendResult


    def msg_broadcast(self, msg, chat_id=None, reply_markup=None, parse_mode=None):
        if self.alive:
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug(f"msg_broadcast called")
            q_msg= {"msgType":"Text", "msg":msg, "chat_id":chat_id, "reply_markup":reply_markup, "parse_mode":parse_mode }
            try:
                self._queue.put(q_msg)
            except Exception as e:
                self.logger.debug(f"Exception '{e}' occurred, please inform plugin maintainer!")

    async def async_photo_broadcast(self, photofile_or_url, caption=None, chat_id=None, local_prepare=True):
        """
        Send an image to the given chat

        :param photofile_or_url: either a local file or a URL with a link to an image resource
        :param local_prepare: Image will be prepared locally instead of passing a link to Telegram. Needed if an image e.g. of a local network webcam is to be sent.
        :param caption: caption of image to send
        :param chat_id: a chat id or a list of chat ids to identificate the chat(s)
        """
        sendResult = []
        for cid in self.get_chat_id_list(chat_id):
            try:
                if photofile_or_url.startswith("http"):
                    if local_prepare:
                        photo_raw = requests.get(photofile_or_url)
                        photo_data = BytesIO(photo_raw.content)
                        response = await self._bot.send_photo(chat_id=cid, photo=photo_data, caption=caption)
                    else:
                        response = await self._bot.send_photo(chat_id=cid, photo=photofile_or_url, caption=caption)
                else:
                    response = await self._bot.send_photo(chat_id=cid, photo=open(str(photofile_or_url), 'rb'), caption=caption)
                if response:
                    if self.logger.isEnabledFor(logging.DEBUG):
                        self.logger.debug(f"Photo sent to Chat_ID:[{cid}] Bot:[{self._bot.bot}] response:[{response}]")
                else:
                    sendResult.append({"msgType":"Photo", "photofile_or_url":photofile_or_url, "chat_id":cid, "caption":caption, "local_prepare":local_prepare })
                    self.logger.error(f"could not broadcast to chat id [{cid}] response: {response}")
            except Exception as e:
                sendResult.append({"msgType":"Photo", "photofile_or_url":photofile_or_url, "chat_id":cid, "caption":caption, "local_prepare":local_prepare })
                self.logger.error(f"Error '{e}' could not send image {photofile_or_url} to chat id {cid}")
        if not sendResult:
            return None
        else:
            return sendResult

    def photo_broadcast(self, photofile_or_url, caption=None, chat_id=None, local_prepare=True):
        """
        Send an image to the given chat

        :param photofile_or_url: either a local file or a URL with a link to an image resource
        :param local_prepare: Image will be prepared locally instead of passing a link to Telegram. Needed if an image e.g. of a local network webcam is to be sent.
        :param caption: caption of image to send
        :param chat_id: a chat id or a list of chat ids to identificate the chat(s)
        """
        if self.alive:
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug(f"photo_broadcast called")
            q_msg= {"msgType":"Photo", "photofile_or_url":photofile_or_url, "chat_id":chat_id, "caption":caption, "local_prepare":local_prepare }
            try:
                self._queue.put(q_msg)
            except Exception as e:
                self.logger.debug(f"Exception '{e}' occurred, please inform plugin maintainer!")

    def get_chat_id_list(self, att_chat_id):
        chat_ids_to_send = []                           # new list
        if att_chat_id is None:                         # no attribute specified
            if self._chat_ids_item:
                chat_ids_to_send = [l for l in self._chat_ids_item()]  # chat_ids from chat_ids item
        else:
            if isinstance(att_chat_id, list):           # if attribute is a list
                chat_ids_to_send = att_chat_id
            else:                                       # if attribute is a single chat_id
                chat_ids_to_send.append(att_chat_id)    # append to list
        return chat_ids_to_send

    def has_access_right(self, user_id):
        """
        if given chat id is not in list of trusted chat ids then reject with a message
        """
        if self._chat_ids_item:
            if user_id in self._chat_ids_item():
                return True
            else:
                self._bot.send_message(chat_id=user_id, text=self._no_access_msg)

        return False

    def has_write_access_right(self, user_id):
        """
        if given chat id is not in list of trusted chat ids then reject with a message
        """
        if self._chat_ids_item:
            if user_id in self._chat_ids_item():
                return self._chat_ids_item()[user_id]
            else:
                self._bot.send_message(chat_id=user_id, text=self._no_write_access_msg)

        return False

        """
        Arguments to all CommandHandler callback functions are update and context

        update is a telegram.Update Object described at https://python-telegram-bot.readthedocs.io/en/latest/telegram.update.html
        When expressed as a dict, the structure of update Object is similar to the following:
        ```python
        'update_id': 081512345
        'message':
            'message_id': 16719
            'date': 1601107823
            'chat':
                'id': 471112345
                'type': 'private'
                'first_name': 'John'
                'last_name': 'Doe'
            'text': '/help'
            'entities':
                - 'type': 'bot_command'
                - 'offset': 0
                - 'length': 5
            'caption_entities': []
            'photo': []
            'new_chat_members': []
            'new_chat_photo': []
            'delete_chat_photo': False
            'group_chat_created': False
            'supergroup_chat_created': False
            'channel_chat_created': False
            'from':                             # this is essentially from_user, not from since from is reserved in Python
                'id': 471112345
                'first_name': 'John'
                'is_bot': False
                'last_name': 'Doe'
                'language_code': 'de'
        ```
        context is a CallbackContext described at https://python-telegram-bot.readthedocs.io/en/latest/telegram.ext.callbackcontext.html

        it contains the following objects:
        args
        bot         context.bot is the target for send_message() function
        bot_data
        chat_data
        dispatcher
        error
        from_error
        from_job
        from_update
        job
        job_queue
        match
        matches
        update
        update_queue
        user_data
        """

    async def eHandler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Just logs an error in case of a problem
        """
        try:
            self.logger.warning(f'Update {update} caused error {context.error}')
        except Exception:
            pass

    async def mHandler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        write the content (text) of the message in an SH-item
        """
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"write the content (text) of the message in an SH-item for update={update}, chat_id={update.message.chat.id} and context={dir(context)}")
        if self.has_write_access_right(update.message.chat.id):

                try:
                    if self._waitAnswer is None:    # keine Antwort erwartet (control-Item/question)
                        if self.logger.isEnabledFor(logging.DEBUG):
                            self.logger.debug(f"update.message.from_user.name={update.message.from_user.name}")
                        text = update.message.from_user.name + ": "
                        text += str(update.message.chat.id) + ": "              # add the message.chat.id
                        text += update.message.text                             # add the message.text
                        for item in self._items_text_message:
                            if self.logger.isEnabledFor(logging.DEBUG):
                                self.logger.debug(f"write item: {item.id()} value: {text}")
                            item(text, caller=self.get_fullname())      # write text to SH-item
                    else:   # Antwort von control-Item/question wird erwartet
                        text = update.message.text
                        dicCtl = self._waitAnswer   # _waitAnswer enthält dict mit weiteren Parametern
                        valid = True                # für Prüfung des Wertebereiches bei num
                        if self.logger.isEnabledFor(logging.DEBUG):
                            self.logger.debug(f"update.message.from_user.name={update.message.from_user.name} answer={text} name={dicCtl['name']}")
                        if text == 'On':
                            if dicCtl['type'] == 'onoff':
                                item = dicCtl['item']
                                msg = f"{dicCtl['name']} \n change to:On(True)"
                                self._bot.sendMessage(chat_id=update.message.chat.id, text=msg)
                                item(True)
                                self._waitAnswer = None
                                self._bot.send_message(chat_id=update.message.chat.id, text=self.translate("Control/Change item-values:"), reply_markup={"keyboard":self.create_control_reply_markup()})
                        elif text == 'Off':
                            if dicCtl['type'] == 'onoff':
                                item = dicCtl['item']
                                msg = f"{dicCtl['name']} \n change to:Off(False)"
                                self._bot.sendMessage(chat_id=update.message.chat.id, text=msg)
                                item(False)
                                self._waitAnswer = None
                                self._bot.send_message(chat_id=update.message.chat.id, text=self.translate("Control/Change item-values:"), reply_markup={"keyboard":self.create_control_reply_markup()})
                        elif text == 'Yes':
                            if self.scheduler_get('telegram_change_item_timeout'):
                                self.scheduler_remove('telegram_change_item_timeout')
                            dicCtlCopy = dicCtl.copy()
                            dicCtlCopy['question'] = ''
                            self.change_item(update, context, dicCtlCopy['name'], dicCtlCopy)
                            self._waitAnswer = None
                            self._bot.send_message(chat_id=update.message.chat.id, text=self.translate("Control/Change item-values:"), reply_markup={"keyboard":self.create_control_reply_markup()})
                        elif dicCtl['type'] == 'num':
                            if type(text) == int or float:
                                if self.logger.isEnabledFor(logging.DEBUG):
                                    self.logger.debug(f"control-item: answer is num ")
                                item = dicCtl['item']
                                newValue = text
                                if dicCtl['min'] is not None:
                                    if float(newValue) < float(dicCtl['min']):
                                        valid = False
                                        if self.logger.isEnabledFor(logging.DEBUG):
                                            self.logger.debug(f"control-item: value:{newValue} to low:{dicCtl['min']}")
                                if dicCtl['max'] is not None:
                                    if float(newValue) > float(dicCtl['max']):
                                        valid = False
                                        if self.logger.isEnabledFor(logging.DEBUG):
                                            self.logger.debug(f"control-item: value:{newValue} to high:{dicCtl['max']}")
                                if valid:
                                    msg = f"{dicCtl['name']} \n change from:{item()} to:{newValue}"
                                    await context.bot.sendMessage(chat_id=update.message.chat.id, text=msg)
                                    item(newValue)
                                    if self.scheduler_get('telegram_change_item_timeout'):
                                        self.scheduler_remove('telegram_change_item_timeout')
                                    self._waitAnswer = None
                                else:
                                    msg = f"{dicCtl['name']} \n out off range"
                                    await context.bot.sendMessage(chat_id=update.message.chat.id, text=msg)
                        else:
                            await context.bot.send_message(chat_id=update.message.chat.id, text=self.translate("Control/Change item-values:"), reply_markup={"keyboard": self.create_control_reply_markup()})
                            self._waitAnswer = None
                except Exception as e:
                    if self.logger.isEnabledFor(logging.DEBUG):
                        self.logger.debug(f"Exception '{e}' occurred, traceback '{traceback.format_exc()}' Please inform plugin maintainer!")

    async def cHandler_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        /time: return server time
        """
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"/time: return server time for update={update}, chat_id={update.message.chat.id} and context={dir(context)}")
        if self.has_access_right(update.message.chat.id):
            await context.bot.send_message(chat_id=update.message.chat.id, text=str(datetime.datetime.now()))

    async def cHandler_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        /help: show available commands as keyboard
        """
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"/help: show available commands as keyboard for update={update}, chat_id={update.message.chat.id} and context={dir(context)}")
        if self.has_access_right(update.message.chat.id):
            await context.bot.send_message(chat_id=update.message.chat.id, text=self.translate("choose"), reply_markup={"keyboard": [["/hide","/start"], ["/time","/list"], ["/lo","/info"], ["/control", "/tr <logicname>"]]})

    async def cHandler_hide(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        /hide: hide keyboard
        """
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"/hide: hide keyboard for bot={context.bot} and chat_id={update.message.chat.id}")
        if self.has_access_right(update.message.chat.id):
            hide_keyboard = {'hide_keyboard': True}
            await context.bot.send_message(chat_id=update.message.chat.id, text=self.translate("I'll hide the keyboard"), reply_markup=hide_keyboard)

    async def cHandler_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        /list: show registered items and value
        """
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"/list: show registered items and value for chat_id={update.message.chat.id}")
        if self.has_access_right(update.message.chat.id):
            await context.bot.send_message(chat_id=update.message.chat.id, text=self.list_items())
            #self.list_items(update.message.chat.id)

    async def cHandler_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        /info: show item-menu with registered items with specific attribute
        """
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"/info: show item-menu with registered items with specific attribute for chat_id={update.message.chat.id}")
        if self.has_access_right(update.message.chat.id):
            if len(self._items_info) > 0:
                await context.bot.send_message(chat_id=update.message.chat.id, text=self.translate("Infos from the items:"), reply_markup={"keyboard": self.create_info_reply_markup()})
            else:
                await context.bot.send_message(chat_id=update.message.chat.id, text=self.translate("no items have attribute telegram_info!"), reply_markup={"keyboard": self.create_info_reply_markup()})

    async def cHandler_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        /start: show a welcome together with asking to add chat id to trusted chat ids
        """
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"/start: show a welcome together with asking to add chat id to trusted chat ids for chat_id={update.message.chat.id}")
        text = ""
        if self._chat_ids_item:
            ids = self._chat_ids_item()
            text = self.translate(f"Your chat id is:") + f" {update.message.chat.id}"
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug(f'update.message.chat.id={update.message.chat.id} with type={type(update.message.chat.id)}')
                self.logger.debug(f'ids dict={ids}')
            if update.message.chat.id in ids:
                if ids[update.message.chat.id]:
                    text += ", " + self.translate("you have write access")
                else:
                    text += ", " + self.translate("you have read access")
            else:
                text = text + ", " + self.translate("please add it to the list of trusted chat ids to get access")
        else:
            self.logger.warning('No chat_ids defined')

        await context.bot.send_message(chat_id=update.message.chat.id, text=text)

    async def cHandler_info_attr(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        /command show registered items and value with specific attribute/key
        where ``command`` is the value from an item with ``telegram_info`` attribute
        """
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("Enter cHandler_info_attr")
        if self.has_access_right(update.message.chat.id):
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug(f"Gathering items to fulfill command {update.message.text}")
            c_key = update.message.text.replace("/", "", 1)
            if c_key in self._items_info:
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug(f"info-command: {c_key}")
                #self.list_items_info(update.message.chat.id, c_key)
                await context.bot.sendMessage(chat_id=update.message.chat.id, text=self.list_items_info(c_key))
            else:
                await context.bot.sendMessage(chat_id=update.message.chat.id, text=self.translate("unknown command %s") % c_key)
        else:
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug(f"Chat with id {update.message.chat.id} has no right to use command {update.message.text}")
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("Leave cHandler_info_attr")

    async def cHandler_lo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        /lo: show all logics with next scheduled execution time
        """
        if self.has_access_right(update.message.chat.id):
            tmp_msg = "Logics:\n"
            for logic in sorted(self.logics.return_defined_logics()):    # list with the names of all logics that are currently loaded
                data = []
                info = self.logics.get_logic_info(logic)
                # self.logger.debug(f"logic_info: {info}")
                if len(info) == 0 or not info['enabled']:
                    data.append("disabled")
                if 'next_exec' in info:
                    data.append(f"scheduled for {info['next_exec']}")
                tmp_msg += f"{logic}"
                if len(data):
                    tmp_msg += f" ({', '.join(data)})"
                tmp_msg += "\n"
            self.logger.info(f"send Message: {tmp_msg}")
            await context.bot.sendMessage(chat_id=update.message.chat.id, text=tmp_msg)

    async def cHandler_tr(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Trigger a logic with command ``/tr xx`` where xx is the name of the logic to trigger
        """
        if self.has_access_right(update.message.chat.id):
            logicname = context.args[0]
            try:
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug(f"trigger_logic: {context.args}")
                self.logics.trigger_logic(logicname, by=self.get_shortname())      # Trigger a logic
            except Exception as e:
                tmp_msg = f"could not trigger logic {logicname} due to error {e}"
                self.logger.warning(tmp_msg)
                await context.bot.sendMessage(chat_id=update.message.chat.id, text=tmp_msg)

    async def cHandler_control(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        /control: Change values of items with specific attribute
        """
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"/control: show item-menu with registered items with specific attribute for chat_id={update.message.chat.id}")
        if self.has_write_access_right(update.message.chat.id):
            if len(self._items_control) > 0:
                await context.bot.send_message(chat_id=update.message.chat.id, text=self.translate("Control/Change item-values:"), reply_markup={"keyboard":self.create_control_reply_markup()})
                await context.bot.send_message(chat_id=update.message.chat.id, text=self.list_items_control())
                #self.list_items_control(update.message.chat.id)
            else:
                await context.bot.send_message(chat_id=update.message.chat.id, text=self.translate("no items have attribute telegram_control!"), reply_markup={"keyboard": self.create_control_reply_markup()})

    async def cHandler_control_attr(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        /xx change value from registered items
        """
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("Enter cHandler_control_attr")
        if self.has_write_access_right(update.message.chat.id):
            c_key = update.message.text.replace("/", "", 1)
            if c_key in self._items_control:
                dicCtl = self._items_control[c_key]   #{'type':type,'item':item}
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug(f"control-command: name:{c_key} dictCtl:{dicCtl}")
                await self.change_item(update=update, context=context, name=c_key, dicCtl=dicCtl)
            else:
                await context.bot.sendMessage(chat_id=update.message.chat.id, text=self.translate("unknown control-command %s") % (c_key))

    # helper functions
    def list_items(self):
        """
        Send a message with all items that are marked with an attribute ``telegram_message``
        """
        text = ""
        for item in self._items:
            if item.type():
                text += f"{item.id()} = {item()}\n"
            else:
                text += f"{item.id()}\n"
        if not text:
            text = "no items found with the attribute:" + ITEM_ATTR_MESSAGE
        return text

    def list_items_info(self, key):
        """
        Show registered items and value with specific attribute/key
        """
        text = ""
        for item in self._items_info[key]:
            if item.type():
                text += f"{item.id()} = {item()}\n"
            else:
                text += f"{item.id()}\n"
        if not text:
            text = self.translate("no items found with the attribute %s") % ITEM_ATTR_INFO
        return text

    def create_info_reply_markup(self):
        """
        Creates a keyboard with all items having a ``telegram_info`` attribute
        """
        # reply_markup={"keyboard":[["/roll","/hide"], ["/time","/list"], ["/lo","/info"]]})
        button_list = []
        for key, value in self._items_info.items():
            button_list.append("/"+key)
        # self.logger.debug(f"button_list: {button_list}")
        header = ["/help"]
        # self.logger.debug(f"header: {header}")
        keyboard = self.build_menu(button_list, n_cols=3, header_buttons=header)
        # self.logger.debug(f"keyboard: {keyboard}")
        return keyboard

    def create_control_reply_markup(self):
        """
        Creates a keyboard with all items having a ``telegram_control`` attribute
        """
        button_list = []
        for key, value in sorted(self._items_control.items()):
            button_list.append("/"+key)

        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"button_list: {button_list}")
        header = ["/help"]
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"header: {header}")
        keyboard = self.build_menu(button_list, n_cols=3, header_buttons=header)
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"keyboard: {keyboard}")
        return keyboard

    def build_menu(self, buttons, n_cols, header_buttons=None, footer_buttons=None):
        """
        create a bot-menu
        """
        menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
        if header_buttons:
            menu.insert(0, header_buttons)
        if footer_buttons:
            menu.append(footer_buttons)
        return menu

    def list_items_control(self):
        """
        Show registered items and value with specific attribute ITEM_ATTR_CONTROL
        """
        for key, value in sorted(self._items_control.items()):  # {'type':type,'item':item}
            item = value['item']
            if item.type():
                text += f"{key} = {item()}\n"
            else:
                text += f"{key}\n"
        if not text:
            text = self.translate("no items found with the attribute %s") % ITEM_ATTR_CONTROL
        #self._bot.sendMessage(chat_id=chat_id, text=text)
        return text

    async def change_item(self, update, context, name, dicCtl):
        """
        util to change a item-value
        name:bla, type:toggle/on/off/onoff/trigger/num question:'wirklich einschalten?'
        """
        chat_id = update.message.chat.id
        item = dicCtl['item']
        changeType = dicCtl['type']
        question = dicCtl['question']
        timeout = dicCtl['timeout']
        text = ""
        if changeType == 'toggle':
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug(f"control-item: type:toggle")
            if question != '':
                nd = (datetime.datetime.now()+ datetime.timedelta(seconds=timeout)).replace(tzinfo=self._sh.tzinfo())
                self._waitAnswer = dicCtl
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug(f"control-item: add scheduler for answer-timout")
                self.scheduler_add('telegram_change_item_timeout', self.telegram_change_item_timeout, value={'update': update, 'context': context}, next=nd)
                text = question
                await context.bot.sendMessage(chat_id=update.message.chat.id, text=text, reply_markup={"keyboard": [['Yes', 'No']]})
            else:
                value = item()
                if item.type() == "bool":
                    newValue = not value
                    text += f"{name} \n change from:{value} to:{newValue}\n"
                else:
                    newValue = value
                    text += f"{name}: {value}\n"
                self._bot.sendMessage(chat_id=chat_id, text=text)
                item(newValue)
                text = f"{name}: {item()}\n"
                await context.bot.sendMessage(chat_id=chat_id, text=text)
        if changeType == 'on':
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug(f"control-item: type:on")
            if question != '':
                nd = (datetime.datetime.now() + datetime.timedelta(seconds=timeout)).replace(tzinfo=self._sh.tzinfo())
                self._waitAnswer = dicCtl
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug(f"control-item: add scheduler for answer-timout")
                self.scheduler_add('telegram_change_item_timeout', self.telegram_change_item_timeout, value={'update': update, 'context': context}, next=nd)
                text = question
                await context.bot.sendMessage(chat_id=update.message.chat.id, text=text, reply_markup={"keyboard": [['Yes', 'No']]})
            else:
                if item.type() == "bool":
                    item(True)
                    text = f"{name}: {item()}\n"
                    self._bot.sendMessage(chat_id=chat_id, text=text)
        if changeType == 'off':
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug(f"control-item: type:off")
            if question != '':
                nd = (datetime.datetime.now() + datetime.timedelta(seconds=timeout)).replace(tzinfo=self._sh.tzinfo())
                self._waitAnswer = dicCtl
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug(f"control-item: add scheduler for answer-timout")
                self.scheduler_add('telegram_change_item_timeout', self.telegram_change_item_timeout, value={'update': update, 'context': context}, next=nd)
                text = question
                await context.bot.sendMessage(chat_id=update.message.chat.id, text=text, reply_markup={"keyboard": [['Yes', 'No']]})
            else:
                if item.type() == "bool":
                    item(False)
                    text = f"{name}: {item()}\n"
                    await context.bot.sendMessage(chat_id=chat_id, text=text)
        if changeType == 'onoff':
            nd = (datetime.datetime.now() + datetime.timedelta(seconds=timeout)).replace(tzinfo=self._sh.tzinfo())
            self._waitAnswer = dicCtl
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug(f"control-item: add scheduler for answer-timout")
            self.scheduler_add('telegram_change_item_timeout', self.telegram_change_item_timeout, value={'update': update, 'context': context}, next=nd)
            if question == '':
                text = self.translate("choose")
            else:
                text = question
            await context.bot.sendMessage(chat_id=update.message.chat.id, text=text, reply_markup={"keyboard": [['On', 'Off']]})
        if changeType == 'num':
            text = self.translate("insert a value")
            nd = (datetime.datetime.now() + datetime.timedelta(seconds=timeout)).replace(tzinfo=self._sh.tzinfo())
            self._waitAnswer = dicCtl
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug(f"control-item: add scheduler for answer-timout")
            self.scheduler_add('telegram_change_item_timeout', self.telegram_change_item_timeout, value={'update': update, 'context': context}, next=nd)
            await context.bot.sendMessage(chat_id=chat_id, text=text)
        if not text:
            text = self.translate("no items found with the attribute %s") % ITEM_ATTR_CONTROL
            await context.bot.sendMessage(chat_id=chat_id, text=text)

    async def telegram_change_item_timeout(self, **kwargs):
        update = None
        context = None
        if 'update' in kwargs:
            update = kwargs['update']
        if 'context' in kwargs:
            context = kwargs['context']
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"Answer control_item timeout update:{update} context:{context}")
        if self._waitAnswer is not None:
            self._waitAnswer = None
            # self._bot.send_message(chat_id=update.message.chat.id, text=self.translate("Control/Change item-values:"), reply_markup={"keyboard": self.create_control_reply_markup()})
            await context.bot.sendMessage(chat_id=update.message.chat.id, text=self.translate("Control/Change item-values:"), reply_markup={"keyboard": self.create_control_reply_markup()})
