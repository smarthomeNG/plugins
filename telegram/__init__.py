#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2017 Markus Garscha                 http://knx-user-forum.de/
#           2018 Ivan De Filippis
#           2018-2021 Bernd Meiners                 Bernd.Meiners@mail.de
#########################################################################
#
#  This file is part of SmartHomeNG.
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
import logging
import re
import requests
import sys              # get line number in case of errors
import traceback
from io import BytesIO

from lib.logic import Logics
from lib.model.smartplugin import SmartPlugin
from lib.item import Items

from .webif import WebInterface

try:
    import telegram
    import telegram.ext
    from telegram.error import TelegramError
    from telegram.ext import Updater
    from telegram.ext import CommandHandler
    from telegram.ext import MessageHandler, Filters
    REQUIRED_PACKAGE_IMPORTED = True
except:
    REQUIRED_PACKAGE_IMPORTED = False

ITEM_ATTR_MESSAGE         = 'telegram_message'            # Send message on item change
ITEM_ATTR_CONDITION       = 'telegram_condition'          # when to send the message, if not given send any time,
                                                          #   if on_change_only then just if the item's current value differs from the previous value
ITEM_ATTR_INFO            = 'telegram_info'               # read items with specific item-values
ITEM_ATTR_TEXT            = 'telegram_text'               # write message-text into the item
ITEM_ATTR_MATCHREGEX      = 'telegram_value_match_regex'  # check a value against a condition before sending a message
ITEM_ATTR_CHAT_IDS        = 'telegram_chat_ids'
ITEM_ATTR_MSG_ID          = 'telegram_message_chat_id'    # chat_id the message should be sent to

MESSAGE_TAG_ID            = '[ID]'
MESSAGE_TAG_NAME          = '[NAME]'
MESSAGE_TAG_VALUE         = '[VALUE]'
MESSAGE_TAG_CALLER        = '[CALLER]'
MESSAGE_TAG_SOURCE        = '[SOURCE]'
MESSAGE_TAG_DEST          = '[DEST]'


class Telegram(SmartPlugin):

    PLUGIN_VERSION = "1.6.7"

    _items = []               # all items using attribute ``telegram_message``
    _items_info = {}          # dict used whith the info-command: key = attribute_value, val= item_list telegram_info
    _items_text_message = []  # items in which the text message is written ITEM_ATTR_TEXT
    _chat_ids_item = {}       # an item with a dict of chat_id and write access

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

        from bin.smarthome import VERSION
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        self.logger.debug("init {}".format(__name__))
        self._init_complete = False

        # Exit if the required package(s) could not be imported
        if not REQUIRED_PACKAGE_IMPORTED:
            self.logger.error("{}: Unable to import Python package 'python-telegram-bot'".format(self.get_fullname()))
            return

        # self._instance = self.get_parameter_value('instance')    # the instance of the plugin
        self._name = self.get_parameter_value('name')
        self._token = self.get_parameter_value('token')

        self._welcome_msg = self.get_parameter_value('welcome_msg')
        self._bye_msg = self.get_parameter_value('bye_msg')
        self._no_access_msg = self.get_parameter_value('no_access_msg')
        self._no_write_access_msg = self.get_parameter_value('no_write_access_msg')
        self._long_polling_timeout = self.get_parameter_value('long_polling_timeout')
        self._pretty_thread_names =  self.get_parameter_value('pretty_thread_names')

        # the Updater class continuously fetches new updates from telegram and passes them on to the Dispatcher class.
        try:
            self._updater = Updater(token=self._token, use_context=True)
            self._bot = self._updater.bot
            self.logger.info("Telegram bot is listening: {0}".format(self._bot.getMe()))
        except TelegramError as e:
            # catch Unauthorized errors due to an invalid token
            self.logger.error("Unable to start up Telegram conversation. Maybe an invalid token? {}".format(e))
        else:
            self.logger.debug("adding command handlers to dispatcher")

            # Dispatcher that handles the updates and dispatches them to the handlers.
            dispatcher = self._updater.dispatcher
            dispatcher.add_error_handler(self.eHandler)
            dispatcher.add_handler(CommandHandler('time', self.cHandler_time))
            dispatcher.add_handler(CommandHandler('help', self.cHandler_help))
            dispatcher.add_handler(CommandHandler('hide', self.cHandler_hide))
            dispatcher.add_handler(CommandHandler('list', self.cHandler_list))
            dispatcher.add_handler(CommandHandler('info', self.cHandler_info))
            dispatcher.add_handler(CommandHandler('start', self.cHandler_start))
            dispatcher.add_handler(CommandHandler('lo', self.cHandler_lo))
            dispatcher.add_handler(CommandHandler('tr', self.cHandler_tr, pass_args=True))

            # Filters.text includes also commands, starting with ``/`` so it is needed to exclude them.
            # This came with lib version 12.4
            dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), self.mHandler))
            self.init_webinterface()

            if not self.init_webinterface(WebInterface):
                self.logger.error("Unable to start Webinterface")
                self._init_complete = False
            else:
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
        self.alive = True
        self.logics = Logics.get_instance()  # Returns the instance of the Logics class, to be used to access the logics-api
        q = self._updater.start_polling(timeout=self._long_polling_timeout)   # (poll_interval=0.0, timeout=10, network_delay=None, clean=False, bootstrap_retries=0, read_latency=2.0, allowed_updates=None)
        if self._pretty_thread_names:
            self.logger.debug("Changing Telegrams thread names to pretty thread names")
            try:
                for t in self._updater._Updater__threads:
                    if 'dispatcher' in t.name:
                        t.name = 'Telegram Dispatcher'
                    if 'updater' in t.name:
                        t.name = 'Telegram Updater'

                for t in self._updater.dispatcher._Dispatcher__async_threads:
                    *_, num = t.name.split('_')
                    t.name = 'Telegram Worker {}'.format(num) if num.isnumeric() else num

                # from telegram.jobqueue.py @ line 301 thread is named
                # name="Bot:{}:job_queue".format(self._dispatcher.bot.id)
                if hasattr(self._updater.job_queue, '_JobQueue__thread'):
                    t = self._updater.job_queue._JobQueue__thread
                    if t.name.startswith('Bot'):
                        _, id, _ = t.name.split(':')
                        self._updater.job_queue._JobQueue__thread.name = "Telegram JobQueue for id {}".format(id)
                else:
                    # model in telegram.ext.jobqueue.py might be changed now
                    pass
            except Exception as e:
                self.logger.warning("Error '{}' occurred. Could not assign pretty names to Telegrams threads, maybe object model of python-telegram-bot module has changed? Please inform the author of plugin!".format(e))
        self.logger.debug("started polling the updater, Queue is {}".format(q))
        if self._welcome_msg:
            self.msg_broadcast(self._welcome_msg)
            self.logger.debug("sent welcome message {}")

    def stop(self):
        """
        This is called when the plugins thread is about to stop
        """
        self.alive = False
        self.logger.debug("stop telegram plugin")
        try:
            if self._bye_msg:
                self.msg_broadcast(self._bye_msg)
                self.logger.debug("sent bye message")
        except:
            self.logger.debug("could not send bye message")
        self._updater.stop()
        self.logger.debug("stop telegram plugin finished")

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        :param item: The item to process.
        """
        if self.has_iattr(item.conf, ITEM_ATTR_CHAT_IDS):
            if self._chat_ids_item:
                self.logger.warning("Item: {} declares chat_id for telegram plugin which are already defined, aborting!")
            else:
                self._chat_ids_item = item

        if self.has_iattr(item.conf, ITEM_ATTR_MESSAGE):
            self.logger.debug("parse item: {0}".format(item))
            self._items.append(item)
            return self.update_item

        """
        For valid commands also see https://core.telegram.org/bots#commands
        In general they are allowed to have 32 characters, use latin letters, numbers or an underscore
        """
        if self.has_iattr(item.conf, ITEM_ATTR_INFO):
            key = self.get_iattr_value(item.conf, ITEM_ATTR_INFO)
            if self.is_valid_command(key):
                self.logger.debug("parse item: {0} {1}".format(item, key))
                if key in self._items_info:
                    self._items_info[key].append(item)
                    self.logger.debug("Append a new item '{}' to command {}".format(item, key))
                else:
                    self._items_info[key] = [item]  # dem dict neue Liste hinzufuegen
                    self.logger.debug("Register new command '{}', add item '{}' and register a handler".format(key, item))
                    # add a handler for each info-attribute
                    self._updater.dispatcher.add_handler(CommandHandler(key, self.cHandler_info_attr))
                return self.update_item
            else:
                self.logger.error("Command '{}' chosen for item '{}' is invalid for telegram botfather".format(key, item))

        if self.has_iattr(item.conf, ITEM_ATTR_TEXT):
            self.logger.debug("parse item: {0}".format(item))
            value = self.get_iattr_value(item.conf, ITEM_ATTR_TEXT)
            if value in ['true', 'True', '1']:
                self._items_text_message.append(item)
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
            self.logger.info("update item: {0}".format(item.id()))

        if self.has_iattr(item.conf, ITEM_ATTR_MESSAGE):
            msg_txt_tmpl = self.get_iattr_value(item.conf, ITEM_ATTR_MESSAGE)

            item_id = item.id()
            if item.property.type == 'bool':
                item_value = item()
                item_value = '1' if item_value is True else '0' if item_value is False else None
            else:
                item_value = "{0}".format(item())

            if self.has_iattr(item.conf, ITEM_ATTR_MATCHREGEX):
                val_match = self.get_iattr_value(item.conf, ITEM_ATTR_MATCHREGEX)
                self.logger.info("val_match: {0}".format(val_match))

                # TO_TEST: ITEM_ATTR_MATCHREGEX
                p = re.compile(val_match)
                m = p.match(item_value)
                if m:
                    self.logger.info("Match found: {0}".format(m.group()))
                else:
                    self.logger.info("No match: {0} in: {1}".format(val_match, item_value))
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
                        self.logger.debug("condition {} met: {}!={}, last_update_age {}, last_change_age {}".format(cond, item.property.value, item.property.last_value, item.property.last_update, item.property.last_change))
                    else:
                        self.logger.debug("condition {} not met: {}=={}, last_update_age {}, last_change_age {}".format(cond, item.property.value, item.property.last_value, item.property.last_update, item.property.last_change))
                        return
                elif cond == "on_update":
                    # this is standard behaviour
                    pass
                else:
                    self.logger.debug("ignoring unknown condition {}".format(cond))

            self.logger.debug(f"send Message: {msg_txt} to Chat_ID {msg_chat_id_txt}")
            self.msg_broadcast(msg_txt, msg_chat_id)

    def _msg_broadcast(self, msg, chat_id=None):
        self.logger.warning("deprecated, please use msg_broadcast instead")
        self.msg_broadcast(msg, chat_id)

    def msg_broadcast(self, msg, chat_id=None, reply_markup=None, parse_mode=None):
        """
        Send a message to the given chat_id

        :param msg: message to send
        :param chat_id: a chat id or a list of chat ids to identificate the chat(s)
        """
        for cid in self.get_chat_id_list(chat_id):
            try:
                self._bot.send_message(chat_id=cid, text=msg, reply_markup=reply_markup, parse_mode=parse_mode)
            except TelegramError as e:
                self.logger.error("could not broadcast to chat id [{}] due to error {}".format(cid, e))
            except Exception as e:
                self.logger.debug("Exception '{0}' occurred, please inform plugin maintainer!".format(e))

    def photo_broadcast(self, photofile_or_url, caption=None, chat_id=None, local_prepare=True):
        """
        Send an image to the given chat

        :param photofile_or_url: either a local file or a URL with a link to an image resource
        :param local_prepare: Image will be prepared locally instead of passing a link to Telegram. Needed if an image e.g. of a local network webcam is to be sent.
        :param caption: caption of image to send
        :param chat_id: a chat id or a list of chat ids to identificate the chat(s)
        """
        for cid in self.get_chat_id_list(chat_id):
            try:
                if photofile_or_url.startswith("http"):
                    if local_prepare:
                        photo_raw = requests.get(photofile_or_url)
                        photo_data = BytesIO(photo_raw.content)
                        self._bot.send_photo(chat_id=cid, photo=photo_data, caption=caption)
                    else:
                        self._bot.send_photo(chat_id=cid, photo=photofile_or_url, caption=caption)
                else:
                    self._bot.send_photo(chat_id=cid, photo=open(str(photofile_or_url), 'rb'), caption=caption)
            except Exception as e:
                self.logger.error("Error '{}' could not send image {} to chat id {}".format(e, photofile_or_url, cid))

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

    def eHandler(self, update, context):
        """
        Just logs an error in case of a problem
        """
        try:
            self.logger.warning('Update {} caused error {}'.format(update, context.error))
        except:
            pass

    def mHandler(self, update, context):
        """
        write the content (text) of the message in an SH-item
        """
        self.logger.debug("write the content (text) of the message in an SH-item for update={}, chat_id={} and context={}".format(update, update.message.chat.id, dir(context)))
        if self.has_write_access_right(update.message.chat.id):
            try:
                self.logger.debug("update.message.from_user.name={}".format(update.message.from_user.name))
                text = update.message.from_user.name + ": "
                text += str(update.message.chat_id) + ": "              # add the message.chat_id
                text += update.message.text                             # add the message.text
                for item in self._items_text_message:
                    self.logger.debug("write item: {0} value: {1}".format(item.id(), text))
                    item(text, caller=self.get_fullname())      # write text to SH-item
            except Exception as e:
                self.logger.debug("Exception '{0}' occurred, traceback '{1}'please inform plugin maintainer!".format(e, traceback.format_exc()))

    def cHandler_time(self, update, context):
        """
        /time: return server time
        """
        self.logger.debug("/time: return server time for update={}, chat_id={} and context={}".format(update, update.message.chat.id, dir(context)))
        if self.has_access_right(update.message.chat.id):
            context.bot.send_message(chat_id=update.message.chat.id, text=str(datetime.datetime.now()))

    def cHandler_help(self, update, context):
        """
        /help: show available commands as keyboard
        """
        self.logger.debug("/help: show available commands as keyboard for update={}, chat_id={} and context={}".format(update, update.message.chat.id, dir(context)))
        if self.has_access_right(update.message.chat.id):
            context.bot.send_message(chat_id=update.message.chat.id, text=self.translate("choose"), reply_markup={"keyboard": [["/hide","/start"], ["/time","/list"], ["/lo","/info"], ["/tr <logicname>"]]})

    def cHandler_hide(self, update, context):
        """
        /hide: hide keyboard
        """
        self.logger.debug("/hide: hide keyboard for bot={} and chat_id={}".format(context.bot, update.message.chat.id))
        if self.has_access_right(update.message.chat.id):
            hide_keyboard = {'hide_keyboard': True}
            context.bot.send_message(chat_id=update.message.chat.id, text=self.translate("I'll hide the keyboard"), reply_markup=hide_keyboard)

    def cHandler_list(self, update, context):
        """
        /list: show registered items and value
        """
        self.logger.debug("/list: show registered items and value for chat_id={}".format(update.message.chat.id))
        if self.has_access_right(update.message.chat.id):
            self.list_items(update.message.chat.id)

    def cHandler_info(self, update, context):
        """
        /info: show item-menu with registered items with specific attribute
        """
        self.logger.debug("/info: show item-menu with registered items with specific attribute for chat_id={}".format(update.message.chat.id))
        if self.has_access_right(update.message.chat.id):
            if len(self._items_info) > 0:
                context.bot.send_message(chat_id=update.message.chat.id, text=self.translate("Infos from the items:"), reply_markup={"keyboard": self.create_info_reply_markup()})
            else:
                context.bot.send_message(chat_id=update.message.chat.id, text=self.translate("No items have attribute telegram_info!"), reply_markup={"keyboard": self.create_info_reply_markup()})

    def cHandler_start(self, update, context):
        """
        /start: show a welcome together with asking to add chat id to trusted chat ids
        """
        self.logger.debug("/start: show a welcome together with asking to add chat id to trusted chat ids for chat_id={}".format(update.message.chat.id))
        text = ""
        if self._chat_ids_item:
            ids = self._chat_ids_item()
            text = self.translate("Your chat id is")+' {}'.format(update.message.chat.id)
            self.logger.debug('update.message.chat_id={} with type={}'.format(update.message.chat.id, type(update.message.chat.id)))
            self.logger.debug('ids dict={}'.format(ids))
            if update.message.chat.id in ids:
                if ids[update.message.chat_id]:
                    text = text+", you have write access"
                else:
                    text = text+", you have read access"
            else:
                text = text+self.translate(", please add it to the list of trusted chat ids to get access")
        else:
            self.logger.warning('No chat_ids defined')

        context.bot.send_message(chat_id=update.message.chat.id, text=text)

    def cHandler_info_attr(self, update, context):
        """
        /command show registered items and value with specific attribute/key
        where ``command`` is the value from an item with ``telegram_info`` attribute
        """
        self.logger.debug("Enter cHandler_info_attr")
        if self.has_access_right(update.message.chat.id):
            self.logger.debug("Gathering items to fulfill command {}".format(update.message.text))
            c_key = update.message.text.replace("/", "", 1)
            if c_key in self._items_info:
                self.logger.debug("info-command: {0}".format(c_key))
                self.list_items_info(update.message.chat_id, c_key)
            else:
                self._bot.sendMessage(chat_id=update.message.chat.id, text=self.translate("unknown command %s") % (c_key))
        else:
            self.logger.debug("Chat with id {} has no right to use command {}".format(update.message.chat.id, update.message.text))
        self.logger.debug("Leave cHandler_info_attr")

    def cHandler_lo(self, update, context):
        """
        /lo: show all logics with next scheduled execution time
        """
        if self.has_access_right(update.message.chat.id):
            tmp_msg = "Logics:\n"
            for logic in sorted(self.logics.return_defined_logics()):    # list with the names of all logics that are currently loaded
                data = []
                info = self.logics.get_logic_info(logic)
                if not info['enabled']:
                    data.append("disabled")
                if 'next_exec' in info:
                    data.append("scheduled for {0}".format(info['next_exec']))
                tmp_msg += ("{0}".format(logic))
                if len(data):
                    tmp_msg += (" ({0})".format(", ".join(data)))
                tmp_msg += ("\n")
            self.logger.info("send Message: {0}".format(tmp_msg))
            self._bot.sendMessage(chat_id=update.message.chat.id, text=tmp_msg)

    def cHandler_tr(self, update, context):
        """
        Trigger a logic with command ``/tr xx`` where xx is the name of the logic to trigger
        """
        if self.has_access_right( update.message.chat.id ):
            try:
                self.logger.debug("trigger_logic: {0}".format(context.args))
                logicname = context.args[0]
                self.logics.trigger_logic(logicname, by=self.get_shortname())      # Trigger a logic
            except Exception as e:
                tmp_msg = ("could not trigger logic %s error %s" % (logicname, e))
                self.logger.warning(tmp_msg)
                self._bot.sendMessage(chat_id=self._chat_id, text=tmp_msg)

    # helper functions
    def list_items(self, chat_id):
        """
        Send a message with all items that are marked with an attribute ``telegram_message``
        """
        if self.has_access_right( chat_id ):
            text = ""
            for item in self._items:
                if item.type():
                    text += "{0} = {1}\n".format(item.id(), item())
                else:
                    text += "{0}\n".format(item.id())
            if not text:
                text = "no items found with the attribute:" + ITEM_ATTR_MESSAGE
            self._bot.sendMessage(chat_id=chat_id, text=text)

    def list_items_info(self, chat_id, key):
        """
        Show registered items and value with specific attribute/key
        """
        if self.has_access_right( chat_id ):
            text = ""
            for item in self._items_info[key]:
                if item.type():
                    text += "{0} = {1}\n".format(item.id(), item())
                else:
                    text += "{0}\n".format(item.id())
            if not text:
                text = self.translate("no items found with the attribute %s") % ITEM_ATTR_INFO
            self._bot.sendMessage(chat_id=chat_id, text=text)
        else:
            self.logger.debug("Chat with id {} has no right to list items with key {}".format(chat_id,key))

    def create_info_reply_markup(self):
        """
        Creates a keyboard with all items having a ``telegram_info`` attribute
        """
        # reply_markup={"keyboard":[["/roll","/hide"], ["/time","/list"], ["/lo","/info"]]})
        button_list = []
        for key, value in self._items_info.items():
            button_list.append("/"+key)
        # self.logger.debug("button_list: {0}".format(button_list))
        header = ["/help"]
        # self.logger.debug("header: {0}".format(header))
        keyboard = self.build_menu(button_list, n_cols=3, header_buttons=header)
        # self.logger.debug("keyboard: {0}".format(keyboard))
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