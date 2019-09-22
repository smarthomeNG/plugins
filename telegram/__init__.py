#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2017 Markus Garscha                 http://knx-user-forum.de/
#           2018 Ivan De Filippis
#           2018-2019 Bernd Meiners                 Bernd.Meiners@mail.de
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

#### Setup Phyton lib for telegram manually
# apt-get install python-pip
# pip install python-telegram-bot
# or use requirements.txt file
# sudo pip install -r requirements.txt    or    pip install -r requirements.txt

import time
import datetime
import logging
import re
import requests
from io import BytesIO

from lib.model.smartplugin import *
from lib.logic import Logics

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
ITEM_ATTR_INFO            = 'telegram_info'               # read items with specific item-values 
ITEM_ATTR_TEXT            = 'telegram_text'               # write message-text into the item
ITEM_ATTR_MATCHREGEX      = 'telegram_value_match_regex'  # check a value against a condition before sending a message
ITEM_ATTR_CHAT_IDS        = 'telegram_chat_ids'

MESSAGE_TAG_ID            = '[ID]'
MESSAGE_TAG_NAME          = '[NAME]'
MESSAGE_TAG_VALUE         = '[VALUE]'
MESSAGE_TAG_CALLER        = '[CALLER]'
MESSAGE_TAG_SOURCE        = '[SOURCE]'
MESSAGE_TAG_DEST          = '[DEST]'


class Telegram(SmartPlugin):
    PLUGIN_VERSION = "1.6.0"

    _items = []              # Storage Array for all items using telegram attributes ITEM_ATTR_MESSAGE
    _items_info = {}         # dict used whith the info-command: key = attribute_value, val= item_list ITEM_ATTR_INFO
    _items_text_message = [] # items in which the text message is written ITEM_ATTR_TEXT
    _chat_ids_item = {}           # an item with a dict of chat_id and write access

    def __init__(self, sh, *args, **kwargs):
        """
        Initializes the Telegram plugin
        The params are documented in ``plugin.yaml`` and values will be obtained through get_parameter_value(parameter_name)
        """
        
        from bin.smarthome import VERSION
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        self.logger.debug("init {}".format(__name__))
        self._init_complete = False

        # Exit if the required package(s) could not be imported
        if not REQUIRED_PACKAGE_IMPORTED:
            self.logger.error("{}: Unable to import Python package 'python-telegram-bot'".format(self.get_fullname()))
            return

        #self._instance = self.get_parameter_value('instance')    # the instance of the plugin
        self._name = self.get_parameter_value('name')
        self._token = self.get_parameter_value('token')

        self._welcome_msg = self.get_parameter_value('welcome_msg')
        self._bye_msg = self.get_parameter_value('bye_msg')
        self._no_access_msg = self.get_parameter_value('no_access_msg')
        self._no_write_access_msg = self.get_parameter_value('no_write_access_msg')
        self._long_polling_timeout = self.get_parameter_value('long_polling_timeout')
        self._pretty_thread_names =  self.get_parameter_value('pretty_thread_names')


        # the Updater class continuously fetches new updates from telegram and passes them on to the Dispatcher class.
        self._updater = Updater(token=self._token) 
        self._bot = self._updater.bot

        self.logger.info("Telegram bot is listening: {0}".format(self._bot.getMe()))
        
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

        dispatcher.add_handler( MessageHandler(Filters.text, self.mHandler))
        self.init_webinterface()

        self.logger.debug("init done")
        self._init_complete = True

    def __call__(self, msg, chat_id=None):
        """
        Provide a way to use the plugin to easily send a message
        """

        if chat_id == None:
            self.msg_broadcast(msg)
        else:
            self.msg_broadcast(msg, chat_id)

    def run(self):
        """
        This is called when the plugins thread is about to run
        """
        self.alive = True
        self.logics = Logics.get_instance() # Returns the instance of the Logics class, to be used to access the logics-api
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

            except:
                self.logger.warning("Could not assign pretty names to Telegrams threads, maybe object model of python-telegram-bot module has changed? Please inform the author of plugin!")
        self.logger.debug("started polling the updater, Queue is {}".format(q))
        self.msg_broadcast(self._welcome_msg)
        self.logger.debug("sent welcome message {}")

    def stop(self):
        self.alive = False
        """
        This is called when the plugins thread is about to stop
        """
        try:
            self.logger.debug("stop telegram plugin")
            self.msg_broadcast(self._bye_msg)
            self.logger.debug("sent bye message")
            self._updater.stop()
            self.logger.debug("telegram plugin stopped")
        except:
            pass
        
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

        if self.has_iattr(item.conf, ITEM_ATTR_INFO):
            key = self.get_iattr_value(item.conf, ITEM_ATTR_INFO)
            self.logger.debug("parse item: {0} {1}".format(item, key))
            if key in self._items_info:
                self._items_info[key].append(item)
            else:
                self._items_info[key] = [item]  # dem dict neue Liste hinzufuegen
                # add a handler for each info-attribute
                self._updater.dispatcher.add_handler(CommandHandler(key, self.cHandler_info_attr))
            return self.update_item

        if self.has_iattr(item.conf, ITEM_ATTR_TEXT):
            self.logger.debug("parse item: {0}".format(item))
            value = self.get_iattr_value(item.conf, ITEM_ATTR_TEXT)
            if value in ['true', 'True', '1']:
                self._items_text_message.append(item)
            return self.update_item

        return None

    #def parse_logic(self, logic):
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
            item_value = "{0}".format(item())
            
            if self.has_iattr(item.conf, ITEM_ATTR_MATCHREGEX):
                val_match = self.get_iattr_value(item.conf, ITEM_ATTR_MATCHREGEX)

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

            # DEBUG
            # msg_txt = msg_txt_tmpl

            self.logger.info("send Message: {}".format(msg_txt))

            self.msg_broadcast(msg_txt)

    def _msg_broadcast(self, msg, chat_id=None):
        self.logger.warning("deprecated, please use msg_broadcast instead")
        self.msg_broadcast(msg, chat_id)
    
    def msg_broadcast(self, msg, chat_id=None):
        """
        Send a message to the given chat_id

        :param msg: message to send
        :param chat_id: a chat id or a list of chat ids to identificate the chat(s)
        """
        for cid in self.get_chat_id_list(chat_id):
            try:
                self._bot.send_message(chat_id=cid, text=msg)
            except TelegramError as e:
                self.logger.error("could not broadcast to chat id [{}] due to error {}".format(cid,e))
            except Exception as e:
                    self.logger.debug("Exception '{0}' occurred, please inform plugin author!".format(e))


    def photo_broadcast(self, photofile_or_url, caption=None, chat_id=None, local_prepare=True):
        """
        Send an image to the given chat

        :param photofile_or_url: either a local file or a URL with a link to an image resource
        :param local_prepare: Image will be prepared locally instead of passing a link to Telegram. Needed if an image e.g. of a local network webcam is to be sent.
        :param title: caption of image to send
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
                    self._bot.send_photo(chat_id=cid, photo=open(str(photofile_or_url),'rb'), caption=caption)
            except Exception as e:
                self.logger.error("Error '{}' could not send image {} to chat id {}".format(e,photofile_or_url,cid))
                
    def get_chat_id_list(self, att_chat_id):
        chat_ids_to_send = []                           # new list
        if att_chat_id is None:                         # no attribute specified
            if self._chat_ids_item:
                chat_ids_to_send = [l for l in self._chat_ids_item()] # chat_ids from chat_ids item
        else:
            if isinstance(att_chat_id, list):           # if attribute is a list
                chat_ids_to_send = att_chat_id
            else:                                       # if attribute is a single chat_id
                chat_ids_to_send.append(att_chat_id)    # append to list
        return chat_ids_to_send

    def has_access_right( self, user_id):
        """
        if given chat id is not in list of trusted chat ids then reject with a message
        """
        if self._chat_ids_item:
            if user_id in self._chat_ids_item():
                return True
            else:
                self._bot.send_message(chat_id=user_id, text=self._no_access_msg)

        return False

    def has_write_access_right( self, user_id):
        """
        if given chat id is not in list of trusted chat ids then reject with a message
        """
        if self._chat_ids_item:
            if user_id in self._chat_ids_item():
                return self._chat_ids_item()[user_id]
            else:
                self._bot.send_message(chat_id=user_id, text=self._no_write_access_msg)

        return False
            
    def eHandler(self, bot, update, error):
        """
        Just logs an error in case of a problem
        """
        try:
            self.logger.warning('Update {} caused error {}'.format(update, error))
        except:
            pass
        
    def mHandler(self, bot, update):
        """
        write the content (text) of the message in an SH-item
        """
        if self.has_write_access_right( update.message.chat_id ):
            text = update.message.from_user.name + ": "     # add username
            text += update.message.text                     # add the message.text
            for item in self._items_text_message:
                self.logger.debug("write item: {0} value: {1}".format(item.id(), text))
                item(text, caller=self.get_fullname())      # write text to SH-item

    
    def cHandler_time(self, bot, update):
        """
        /time: return server time
        """
        if self.has_access_right( update.message.chat_id ):
            bot.send_message(chat_id=update.message.chat_id, text=str(datetime.datetime.now()))

    def cHandler_help(self, bot, update):
        """
        /help: show available commands as keyboard
        """
        if self.has_access_right( update.message.chat_id ):
            bot.send_message(chat_id=update.message.chat_id, text=self.translate("choose"), reply_markup={"keyboard":[["/hide","/start"], ["/time","/list"], ["/lo","/info"]]})

    def cHandler_hide(self, bot, update):
        """
        /hide: hide keyboard
        """
        if self.has_access_right( update.message.chat_id ):         
            hide_keyboard = {'hide_keyboard': True}
            bot.send_message(chat_id=update.message.chat_id, text=self.translate("I'll hide the keyboard"), reply_markup=hide_keyboard)
    
    
    def cHandler_list(self, bot, update):
        """
        /list: show registered items and value
        """
        if self.has_access_right( update.message.chat_id ):
            self.list_items(update.message.chat_id)

    def cHandler_info(self, bot, update):
        """
        /info: show item-menu with registered items with specific attribute
        """
        if self.has_access_right( update.message.chat_id ):
            bot.send_message(chat_id=update.message.chat_id, text=self.translate("Infos from the items:"), reply_markup={"keyboard":self.create_info_reply_markup()})

    def cHandler_start(self, bot, update):
        """
        /start: show a welcome together with asking to add chat id to trusted chat ids
        """
        text=""
        if self._chat_ids_item:
            ids = self._chat_ids_item()
            text=self.translate("Your chat id is")+' {}'.format( update.message.chat_id)
            if update.message.chat_id in ids:
                if ids[update.message.chat_id]:
                    text=text+", you have write access"
                else:
                    text=text+", you have read access"
            else:
                text=text+self.translate(", please add it to the list of trusted chat ids to get access")
        else:
            self.logger.warning('No chat_ids defined')
        
        bot.send_message(chat_id=update.message.chat_id, text=text)
       
        

    def cHandler_info_attr(self, bot, update):
        """
        /xx show registered items and value with specific attribute/key
        where xx is the value from an item with ``telegram_info`` attribute
        """
        if self.has_access_right( update.message.chat_id ):
            c_key = update.message.text.replace("/", "", 1)
            if c_key in self._items_info:
                self.logger.debug("info-command: {0}".format(c_key))
                self.list_items_info(update.message.chat_id, c_key)
            else:    
                self._bot.sendMessage(chat_id=update.message.chat_id, text=self.translate("unknown command %s") % (c_key))

    def cHandler_lo(self, bot, update):
        """
        /lo: show all logics with next scheduled execution time
        """
        if self.has_access_right( update.message.chat_id ):
            tmp_msg="Logics:\n"
            for logic in sorted(self.logics.return_defined_logics()):    # list with the names of all logics that are currently loaded
                data = []
                info = self.logics.get_logic_info(logic)
                if not info['enabled']:
                    data.append("disabled")
                if 'next_exec' in info:
                    data.append("scheduled for {0}".format(info['next_exec']))
                tmp_msg+=("{0}".format(logic))
                if len(data):
                    tmp_msg+=(" ({0})".format(", ".join(data)))
                tmp_msg+=("\n")
            self.logger.info("send Message: {0}".format(tmp_msg))
            self._bot.sendMessage(chat_id=update.message.chat_id, text=tmp_msg)
            
    
    def cHandler_tr(self, bot, update, args):
        """
        Trigger a logic with command ``/tr xx`` where xx is the name of the logic to trigger
        """
        if self.has_access_right( update.message.chat_id ):
            try:
                self.logger.debug("trigger_logic: {0}".format(args))
                logicname = args[0]
                self.logics.trigger_logic(logicname, by='telegram')      # Trigger a logic
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
        

    def create_info_reply_markup(self):
        """
        Creates a keyboard with all items having a ``telegram_info`` attribute
        """
        # reply_markup={"keyboard":[["/roll","/hide"], ["/time","/list"], ["/lo","/info"]]})
        button_list = []
        for key, value in self._items_info.items():
            button_list.append("/"+key)
        #self.logger.debug("button_list: {0}".format(button_list))
        header = ["/help"]
        #self.logger.debug("header: {0}".format(header))
        keyboard = self.build_menu(button_list, n_cols=3, header_buttons=header)
        #self.logger.debug("keyboard: {0}".format(keyboard))
        return keyboard

    # util to create a bot-menu    
    def build_menu(self, buttons, n_cols, header_buttons=None, footer_buttons=None):
        menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
        if header_buttons:
            menu.insert(0, header_buttons)
        if footer_buttons:
            menu.append(footer_buttons)
        return menu


    def init_webinterface(self):
        """
        Initialize the web interface for this plugin

        This method is only needed if the plugin is implementing a web interface
        """
        try:
            self.mod_http = Modules.get_instance().get_module('http')   # try/except to handle running in a core version that does not support modules
        except:
             self.mod_http = None
        if self.mod_http == None:
            self.logger.error("Plugin '{}': Not initializing the web interface".format(self.get_shortname()))
            return False
        
        import sys
        if not "SmartPluginWebIf" in list(sys.modules['lib.model.smartplugin'].__dict__):
            self.logger.warning("Plugin '{}': Web interface needs SmartHomeNG v1.5 and up. Not initializing the web interface".format(self.get_shortname()))
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
        return tmpl.render(p=self.plugin, )

