#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2022-         Michael Wenzel           wenzel_michael@web.de
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  This plugin provides additional functionality to mysql database
#  connected via database plugin
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

import sqlvalidator
import datetime
import time
import re
import queue
from dateutil.relativedelta import relativedelta
from typing import Union
import threading

from lib.model.smartplugin import SmartPlugin
from lib.item import Items
from lib.item.item import Item
from lib.shtime import Shtime
from lib.plugin import Plugins
from .webif import WebInterface
import lib.db

DAY = 'day'
WEEK = 'week'
MONTH = 'month'
YEAR = 'year'


class DatabaseAddOn(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides the update functions for the items
    """

    PLUGIN_VERSION = '1.1.0'

    def __init__(self, sh):
        """
        Initializes the plugin.
        """

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        # get item and shtime instance
        self.shtime = Shtime.get_instance()
        self.items = Items.get_instance()
        self.plugins = Plugins.get_instance()

        # define cache dicts
        self.current_values = {}                     # Dict to hold min and max value of current day / week / month / year for items
        self.previous_values = {}                    # Dict to hold value of end of last day / week / month / year for items
        self.item_cache = {}                         # Dict to hold item_id, oldest_log_ts and oldest_entry for items

        # define variables for database, database connection, working queue and status
        self.item_queue = queue.Queue()              # Queue containing all to be executed items
        self.work_item_queue_thread = None           # Working Thread for queue
        self._db_plugin = None                       # object if database plugin
        self._db = None                              # object of database
        self.connection_data = None                  # connection data list of database
        self.db_driver = None                        # driver of the used database
        self.db_instance = None                      # instance of the used database
        self.item_attribute_search_str = 'database'  # attribute, on which an item configured for database can be identified
        self.last_connect_time = 0                   # mechanism for limiting db connection requests
        self.alive = None                            # Is plugin alive?
        self.startup_finished = False                # Startup of Plugin finished
        self.suspended = False                       # Is plugin activity suspended
        self.active_queue_item: str = '-'            # String holding item path of currently executed item

        # define debug logs
        self.parse_debug = False                     # Enable / Disable debug logging for method 'parse item'
        self.execute_debug = False                   # Enable / Disable debug logging for method 'execute items'
        self.sql_debug = False                       # Enable / Disable debug logging for sql stuff
        self.onchange_debug = False                  # Enable / Disable debug logging for method 'handle_onchange'
        self.prepare_debug = False                   # Enable / Disable debug logging for query preparation

        # define default mysql settings
        self.default_connect_timeout = 60
        self.default_net_read_timeout = 60

        # define variables from plugin parameters
        self.db_configname = self.get_parameter_value('database_plugin_config')
        self.startup_run_delay = self.get_parameter_value('startup_run_delay')
        self.ignore_0 = self.get_parameter_value('ignore_0')
        self.use_oldest_entry = self.get_parameter_value('use_oldest_entry')

        # init cache dicts
        self._init_cache_dicts()

        # activate debug logger
        if self.log_level == 10:  # info: 20  debug: 10
            self.parse_debug = True
            self.execute_debug = True
            self.sql_debug = True
            self.onchange_debug = True
            self.prepare_debug = True

        # init webinterface
        self.init_webinterface(WebInterface)

    def run(self):
        """
        Run method for the plugin
        """

        self.logger.debug("Run method called")

        # check existence of db-plugin, get parameters, and init connection to db
        if not self._check_db_existence():
            self.logger.error(f"Check of existence of database plugin incl connection check failed. Plugin not loaded")
            return self.deinit()

        self._db = lib.db.Database("DatabaseAddOn", self.db_driver, self.connection_data)
        if not self._db.api_initialized:
            self.logger.error("Initialization of database API failed")
            return self.deinit()

        self.logger.debug("Initialization of database API successful")

        # init db
        if not self._initialize_db():
            return self.deinit()

        # check db connection settings
        if self.db_driver is not None and self.db_driver.lower() == 'pymysql':
            self._check_db_connection_setting()

        # add scheduler for cyclic trigger item calculation
        self.scheduler_add('cyclic', self.execute_due_items, prio=3, cron='5 0 0 * * *', cycle=None, value=None, offset=None, next=None)

        # add scheduler to trigger items to be calculated at startup with delay
        dt = self.shtime.now() + datetime.timedelta(seconds=(self.startup_run_delay + 3))
        self.logger.info(f"Set scheduler for calculating startup-items with delay of {self.startup_run_delay + 3}s to {dt}.")
        self.scheduler_add('startup', self.execute_startup_items, next=dt)

        # update database_items in item config, where path was given
        self._update_database_items()

        # set plugin to alive
        self.alive = True

        # start the queue consumer thread
        self._work_item_queue_thread_startup()

    def stop(self):
        """
        Stop method for the plugin
        """

        self.logger.debug("Stop method called")
        self.alive = False
        self.scheduler_remove('cyclic')
        self._work_item_queue_thread_shutdown()

    def parse_item(self, item: Item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.

        The plugin can, corresponding to its attribute keywords, decide what to do with the item in the future, like adding it to an internal array for future reference
        :param item:    The item to process.
        :return:        If the plugin needs to be informed of an items change you should return a call back function
                        like the function update_item down below. An example when this is needed is the knx plugin
                        where parse_item returns the update_item function when the attribute knx_send is found.
                        This means that when the items value is about to be updated, the call back function is called
                        with the item, caller, source and dest as arguments and in case of the knx plugin the value
                        can be sent to the knx with a knx write function within the knx plugin.
        """

        def get_database_item() -> Item:
            """
            Returns item from shNG config which is an item with database attribut valid for current db_addon item
            """

            _lookup_item = item.return_parent()

            for i in range(2):
                if self.has_iattr(_lookup_item.conf, self.item_attribute_search_str):
                    self.logger.debug(f"Attribut '{self.item_attribute_search_str}' has been found for item={item.path()} {i + 1} level above item.")
                    return _lookup_item
                else:
                    _lookup_item = _lookup_item.return_parent()

        def has_db_addon_item() -> bool:
            """Returns item from shNG config which is item with db_addon attribut valid for database item"""

            for child in item.return_children():
                if check_db_addon_fct(child):
                    return True

                for child_child in child.return_children():
                    if check_db_addon_fct(child_child):
                        return True

                    for child_child_child in child_child.return_children():
                        if check_db_addon_fct(child_child_child):
                            return True

            return False

        def check_db_addon_fct(check_item) -> bool:
            """
            Check if item has db_addon_fct and is onchange
            """
            if self.has_iattr(check_item.conf, 'db_addon_fct'):
                if self.get_iattr_value(check_item.conf, 'db_addon_fct').lower() in ALL_ONCHANGE_ATTRIBUTES:
                    self.logger.debug(f"db_addon item for database item {item.path()} found.")
                    return True
            return False

        # handle all items with db_addon_fct
        if self.has_iattr(item.conf, 'db_addon_fct'):

            if self.parse_debug:
                self.logger.debug(f"parse item: {item.path()} due to 'db_addon_fct'")

            # get db_addon_fct attribute value
            db_addon_fct = self.get_iattr_value(item.conf, 'db_addon_fct').lower()

            # get attribute value if item should be calculated at plugin startup
            db_addon_startup = bool(self.get_iattr_value(item.conf, 'db_addon_startup'))

            # get attribute if certain value should be ignored at db query
            if self.has_iattr(item.conf, 'database_ignore_value'):
                db_addon_ignore_value = self.get_iattr_value(item.conf, 'database_ignore_value')
            elif any(x in str(item.id()) for x in self.ignore_0):
                db_addon_ignore_value = 0
            else:
                db_addon_ignore_value = None

            # get database item and return if not available
            database_item_path = self.get_iattr_value(item.conf, 'db_addon_database_item')
            if database_item_path is not None:
                database_item = database_item_path
            else:
                database_item = get_database_item()
            if database_item is None:
                self.logger.warning(f"No database item found for {item.path()}: Item ignored. Maybe you should check instance of database plugin.")
                return

            # return if mandatory params for ad_addon_fct not given.
            if db_addon_fct in ALL_NEED_PARAMS_ATTRIBUTES and not self.has_iattr(item.conf, 'db_addon_params'):
                self.logger.warning(f"Item '{item.path()}' with db_addon_fct={db_addon_fct} ignored, since parameter using 'db_addon_params' not given. Item will be ignored.")
                return

            # create standard items config
            item_config_data_dict = {'db_addon': 'function', 'db_addon_fct': db_addon_fct, 'database_item': database_item, 'ignore_value': db_addon_ignore_value}
            if database_item_path is not None:
                item_config_data_dict.update({'database_item_path': True})
            else:
                database_item_path = database_item.path()

            if self.parse_debug:
                self.logger.debug(f"Item '{item.path()}' added with db_addon_fct={db_addon_fct} and database_item={database_item_path}")

            # handle daily items
            if db_addon_fct in ALL_DAILY_ATTRIBUTES:
                item_config_data_dict.update({'cycle': 'daily'})

            # handle weekly items
            elif db_addon_fct in ALL_WEEKLY_ATTRIBUTES:
                item_config_data_dict.update({'cycle': 'weekly'})

            # handle monthly items
            elif db_addon_fct in ALL_MONTHLY_ATTRIBUTES:
                item_config_data_dict.update({'cycle': 'monthly'})

            # handle yearly items
            elif db_addon_fct in ALL_YEARLY_ATTRIBUTES:
                item_config_data_dict.update({'cycle': 'yearly'})

            # handle static items
            elif db_addon_fct in ALL_GEN_ATTRIBUTES:
                item_config_data_dict.update({'cycle': 'static'})

            # handle on-change items
            elif db_addon_fct in ALL_ONCHANGE_ATTRIBUTES:
                item_config_data_dict.update({'cycle': 'on-change'})

            # handle all functions with 'summe' like waermesumme, kaeltesumme, gruenlandtemperatursumme
            if 'summe' in db_addon_fct:
                db_addon_params = params_to_dict(self.get_iattr_value(item.conf, 'db_addon_params'))
                if db_addon_params is None or 'year' not in db_addon_params:
                    self.logger.info(f"No 'year' for evaluation via 'db_addon_params' of item {item.path()} for function {db_addon_fct} given. Default with 'current year' will be used.")
                    db_addon_params = {'year': 'current'}
                item_config_data_dict.update({'params': db_addon_params})

            # handle wachstumsgradtage function
            elif db_addon_fct == 'wachstumsgradtage':
                DEFAULT_THRESHOLD = 10
                db_addon_params = params_to_dict(self.get_iattr_value(item.conf, 'db_addon_params'))
                if db_addon_params is None or 'year' not in db_addon_params:
                    self.logger.info(f"No 'year' for evaluation via 'db_addon_params' of item {item.path()} for function {db_addon_fct} given. Default with 'current year' will be used.")
                    db_addon_params = {'year': 'current'}
                if 'threshold' not in db_addon_params:
                    self.logger.info(f"No 'threshold' for evaluation via 'db_addon_params' of item {item.path()} for function {db_addon_fct} given. Default with {DEFAULT_THRESHOLD} will be used.")
                    db_addon_params.update({'threshold': DEFAULT_THRESHOLD})
                if not isinstance(db_addon_params['threshold'], int):
                    threshold = to_int(db_addon_params['threshold'])
                    db_addon_params['threshold'] = DEFAULT_THRESHOLD if threshold is None else threshold
                item_config_data_dict.update({'params': db_addon_params})

            # handle tagesmitteltemperatur
            elif db_addon_fct == 'tagesmitteltemperatur':
                if not self.has_iattr(item.conf, 'db_addon_params'):
                    self.logger.warning(f"Item '{item.path()}' with db_addon_fct={db_addon_fct} ignored, since parameter using 'db_addon_params' not given. Item will be ignored.")
                    return

                db_addon_params = params_to_dict(self.get_iattr_value(item.conf, 'db_addon_params'))
                if db_addon_params is None:
                    self.logger.warning(f"Error occurred during parsing of item attribute 'db_addon_params' of item {item.path()}. Item will be ignored.")
                    return
                item_config_data_dict.update({'params': db_addon_params})

            # handle db_request
            elif db_addon_fct == 'db_request':
                if not self.has_iattr(item.conf, 'db_addon_params'):
                    self.logger.warning(f"Item '{item.path()}' with db_addon_fct={db_addon_fct} ignored, since parameter using 'db_addon_params' not given. Item will be ignored")
                    return

                db_addon_params = params_to_dict(self.get_iattr_value(item.conf, 'db_addon_params'))
                if db_addon_params is None:
                    self.logger.warning(f"Error occurred during parsing of item attribute 'db_addon_params' of item {item.path()}. Item will be ignored.")
                    return

                if self.parse_debug:
                    self.logger.debug(f"parse_item: {db_addon_fct=} for item={item.path()}, {db_addon_params=}")

                if not any(param in db_addon_params for param in ('func', 'timeframe')):
                    self.logger.warning(f"Item '{item.path()}' with {db_addon_fct=} ignored, not all mandatory parameters in {db_addon_params=} given. Item will be ignored.")
                    return

                TIMEFRAMES_2_UPDATECYCLE = {'day': 'daily',
                                            'week': 'weekly',
                                            'month': 'monthly',
                                            'year': 'yearly'}

                _timeframe = db_addon_params.get('group', None)
                if not _timeframe:
                    _timeframe = db_addon_params.get('timeframe', None)
                update_cycle = TIMEFRAMES_2_UPDATECYCLE.get(_timeframe)
                if update_cycle is None:
                    self.logger.warning(f"Item '{item.path()}' with {db_addon_fct=} ignored. Not able to detect update cycle.")
                    return

                item_config_data_dict.update({'params': db_addon_params, 'cycle': update_cycle})

            # debug log item cycle
            if self.parse_debug:
                self.logger.debug(f"Item '{item.path()}' added to be run {item_config_data_dict['cycle']}.")

            # handle item to be run on startup (onchange_items shall not be run at startup, but at first noticed change of item value; therefore remove for list of items to be run at startup)
            if (db_addon_startup and db_addon_fct not in ALL_ONCHANGE_ATTRIBUTES) or db_addon_fct in ALL_GEN_ATTRIBUTES:
                if self.parse_debug:
                    self.logger.debug(f"Item '{item.path()}' added to be run on startup")
                item_config_data_dict.update({'startup': True})
            else:
                item_config_data_dict.update({'startup': False})

            # add item to plugin item dict
            self.add_item(item, config_data_dict=item_config_data_dict)

        # handle all items with db_addon_info
        elif self.has_iattr(item.conf, 'db_addon_info'):
            if self.parse_debug:
                self.logger.debug(f"parse item: {item.path()} due to used item attribute 'db_addon_info'")
            self.add_item(item, config_data_dict={'db_addon': 'info', 'db_addon_fct': f"info_{self.get_iattr_value(item.conf, 'db_addon_info').lower()}", 'database_item': None, 'startup': True})

        # handle all items with db_addon_admin
        elif self.has_iattr(item.conf, 'db_addon_admin'):
            if self.parse_debug:
                self.logger.debug(f"parse item: {item.path()} due to used item attribute 'db_addon_admin'")
            self.add_item(item, config_data_dict={'db_addon': 'admin', 'db_addon_fct': f"admin_{self.get_iattr_value(item.conf, 'db_addon_admin').lower()}", 'database_item': None})
            return self.update_item

        # Reference to 'update_item' für alle Items mit Attribut 'database', um die on_change Items zu berechnen
        elif self.has_iattr(item.conf, self.item_attribute_search_str) and has_db_addon_item():
            self.logger.debug(f"reference to update_item for item '{item.path()}' will be set due to on-change")
            self.add_item(item, config_data_dict={'db_addon': 'database'})
            return self.update_item

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Handle updated item
        This method is called, if the value of an item has been updated by SmartHomeNG.
        It should write the changed value out to the device (hardware/interface) that is managed by this plugin.

        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """

        if self.alive and caller != self.get_shortname():
            # handle database items
            if item in self._database_items():
                # self.logger.debug(f"update_item was called with item {item.property.path} with value {item()} from caller {caller}, source {source} and dest {dest}")
                if not self.startup_finished:
                    self.logger.info(f"Handling of 'on-change' is paused for startup. No updated will be processed.")
                elif self.suspended:
                    self.logger.info(f"Plugin is suspended. No updated will be processed.")
                else:
                    self.logger.info(f"+ Updated item '{item.path()}' with value {item()} will be put to queue for processing. {self.item_queue.qsize() + 1} items to do.")
                    self.item_queue.put((item, item()))

            # handle admin items
            elif self.has_iattr(item.conf, 'db_addon_admin'):
                self.logger.debug(f"update_item was called with item {item.property.path} from caller {caller}, source {source} and dest {dest}")
                if self.get_iattr_value(item.conf, 'db_addon_admin') == 'suspend':
                    self.suspend(item())
                elif self.get_iattr_value(item.conf, 'db_addon_admin') == 'recalc_all':
                    self.execute_all_items()
                    item(False, self.get_shortname())
                elif self.get_iattr_value(item.conf, 'db_addon_admin') == 'clean_cache_values':
                    self._init_cache_dicts()
                    item(False, self.get_shortname())

    def execute_due_items(self) -> None:
        """
        Execute all items, which are due
        """

        if self.execute_debug:
            self.logger.debug("execute_due_items called")

        if not self.suspended:
            _todo_items = self._create_due_items()
            self.logger.info(f"{len(_todo_items)} items are due and will be calculated.")
            [self.item_queue.put(i) for i in _todo_items]
        else:
            self.logger.info(f"Plugin is suspended. No items will be calculated.")

    def execute_startup_items(self) -> None:
        """
        Execute all startup_items
        """
        if self.execute_debug:
            self.logger.debug("execute_startup_items called")

        if not self.suspended:
            self.logger.info(f"{len(self._startup_items())} items will be calculated at startup.")
            [self.item_queue.put(i) for i in self._startup_items()]
            self.startup_finished = True
        else:
            self.logger.info(f"Plugin is suspended. No items will be calculated.")

    def execute_static_items(self) -> None:
        """
        Execute all static items
        """
        if self.execute_debug:
            self.logger.debug("execute_static_item called")

        if not self.suspended:
            self.logger.info(f"{len(self._static_items())} items will be calculated.")
            [self.item_queue.put(i) for i in self._static_items()]
        else:
            self.logger.info(f"Plugin is suspended. No items will be calculated.")

    def execute_info_items(self) -> None:
        """
        Execute all info items
        """
        if self.execute_debug:
            self.logger.debug("execute_info_items called")

        if not self.suspended:
            self.logger.info(f"{len(self._info_items())} items will be calculated.")
            [self.item_queue.put(i) for i in self._info_items()]
        else:
            self.logger.info(f"Plugin is suspended. No items will be calculated.")

    def execute_all_items(self) -> None:
        """
        Execute all ondemand items
        """

        if not self.suspended:
            self.logger.info(f"Values for all {len(self._ondemand_items())} items with 'db_addon_fct' attribute, which are not 'on-change', will be calculated!")
            [self.item_queue.put(i) for i in self._ondemand_items()]
        else:
            self.logger.info(f"Plugin is suspended. No items will be calculated.")

    def work_item_queue(self) -> None:
        """
        Handles item queue were all to be executed items were be placed in.
        """

        while self.alive:
            try:
                queue_entry = self.item_queue.get(True, 10)
                self.logger.info(f"     Queue Entry: '{queue_entry}' received.")
            except queue.Empty:
                self.active_queue_item = '-'
                pass
            else:
                if isinstance(queue_entry, tuple):
                    item, value = queue_entry
                    self.logger.info(f"# {self.item_queue.qsize() + 1} item(s) to do. || 'on-change' item '{item.path()}' with {value=} will be processed.")
                    self.active_queue_item = str(item.path())
                    self.handle_onchange(item, value)
                else:
                    self.logger.info(f"# {self.item_queue.qsize() + 1} item(s) to do. || 'on-demand' item '{queue_entry.path()}' will be processed.")
                    self.active_queue_item = str(queue_entry.path())
                    self.handle_ondemand(queue_entry)

    def handle_ondemand(self, item: Item) -> None:
        """
        Calculate value for requested item, fill cache dicts and set item value.

        :param item: Item for which value will be calculated
        """

        # set/get parameters
        item_config = self.get_item_config(item)
        db_addon = item_config['db_addon']
        db_addon_fct = item_config['db_addon_fct']
        database_item = item_config['database_item']
        ignore_value = item_config.get('ignore_value')
        result = None
        self.logger.debug(f"handle_ondemand: Item={item.path()} with {item_config=}")

        # handle info functions
        if db_addon == 'info':
            # handle info_db_version
            if db_addon_fct == 'info_db_version':
                result = self._get_db_version()
                self.logger.debug(f"handle_ondemand: info_db_version {result=}")
            else:
                self.logger.warning(f"No handling for attribute {db_addon_fct=} for Item {item.path()} defined.")

        # handle general functions
        elif db_addon_fct in ALL_GEN_ATTRIBUTES:
            # handle oldest_value
            if db_addon_fct == 'general_oldest_value':
                result = self._get_oldest_value(database_item)

            # handle oldest_log
            elif db_addon_fct == 'general_oldest_log':
                result = self._get_oldest_log(database_item)

            else:
                self.logger.warning(f"No handling for attribute {db_addon_fct=} for Item {item.path()} defined.")

        # handle item starting with 'verbrauch_'
        elif db_addon_fct in ALL_VERBRAUCH_ATTRIBUTES:
            if self.execute_debug:
                self.logger.debug(f"handle_ondemand: 'verbrauch' detected.")

            result = self._handle_verbrauch(database_item, db_addon_fct, ignore_value)

            if result and result < 0:
                self.logger.warning(f"Result of item {item.path()} with {db_addon_fct=} was negative. Something seems to be wrong.")

        # handle item starting with 'zaehlerstand_' of format 'zaehlerstand_timeframe_timedelta' like 'zaehlerstand_woche_minus1'
        elif db_addon_fct in ALL_ZAEHLERSTAND_ATTRIBUTES:
            if self.execute_debug:
                self.logger.debug(f"handle_ondemand: 'zaehlerstand' detected.")

            result = self._handle_zaehlerstand(database_item, db_addon_fct, ignore_value)

        # handle item starting with 'minmax_'
        elif db_addon_fct in ALL_HISTORIE_ATTRIBUTES:
            if self.execute_debug:
                self.logger.debug(f"handle_ondemand: 'minmax' detected.")

            result = self._handle_min_max(database_item, db_addon_fct, ignore_value)[0][1]

        # handle item starting with 'tagesmitteltemperatur_'
        elif db_addon_fct in ALL_TAGESMITTEL_ATTRIBUTES:
            if self.execute_debug:
                self.logger.debug(f"handle_ondemand: 'tagesmitteltemperatur' detected.")

            result = self._handle_tagesmitteltemperatur(database_item, db_addon_fct, ignore_value)[0][1]

        # handle item starting with 'serie_'
        elif db_addon_fct in ALL_SERIE_ATTRIBUTES:
            if 'minmax' in db_addon_fct:
                if self.execute_debug:
                    self.logger.debug(f"handle_ondemand: 'serie_minmax' detected.")

                result = self._handle_min_max(database_item, db_addon_fct, ignore_value)

            elif 'verbrauch' in db_addon_fct:
                if self.execute_debug:
                    self.logger.debug(f"handle_ondemand: 'serie_verbrauch' detected.")

                result = self._handle_verbrauch(database_item, db_addon_fct, ignore_value)

            elif 'zaehlerstand' in db_addon_fct:
                if self.execute_debug:
                    self.logger.debug(f"handle_ondemand: 'serie_zaehlerstand' detected.")

                result = self._handle_zaehlerstand(database_item, db_addon_fct, ignore_value)

            elif 'tagesmitteltemperatur' in db_addon_fct:
                if self.execute_debug:
                    self.logger.debug(f"handle_ondemand: 'serie_tagesmittelwert' detected.")

                result = self._handle_tagesmitteltemperatur(database_item, db_addon_fct, ignore_value)
            else:
                self.logger.warning(f"No handling for attribute {db_addon_fct=} for Item {item.path()} defined.")

        # handle kaeltesumme
        elif db_addon_fct == 'kaeltesumme':
            db_addon_params = item_config.get('params')
            if self.execute_debug:
                self.logger.debug(f"handle_ondemand: {db_addon_fct=} detected; {db_addon_params=}")

            if db_addon_params:
                db_addon_params.update({'database_item': item_config['database_item']})
                result = self._handle_kaeltesumme(**db_addon_params)

        # handle waermesumme
        elif db_addon_fct == 'waermesumme':
            db_addon_params = item_config.get('params')
            if self.execute_debug:
                self.logger.debug(f"handle_ondemand: {db_addon_fct=} detected; {db_addon_params=}")

            if db_addon_params:
                db_addon_params.update({'database_item': item_config['database_item']})
                result = self._handle_waermesumme(**db_addon_params)

        # handle gruenlandtempsumme
        elif db_addon_fct == 'gruenlandtempsumme':
            db_addon_params = item_config.get('params')
            if self.execute_debug:
                self.logger.debug(f"handle_ondemand: {db_addon_fct=} detected; {db_addon_params=}")

            if db_addon_params:
                db_addon_params.update({'database_item': item_config['database_item']})
                result = self._handle_gruenlandtemperatursumme(**db_addon_params)

        # handle wachstumsgradtage
        elif db_addon_fct == 'wachstumsgradtage':
            db_addon_params = item_config.get('params')
            if self.execute_debug:
                self.logger.debug(f"handle_ondemand: {db_addon_fct=} detected; {db_addon_params}")

            if db_addon_params:
                db_addon_params.update({'database_item': item_config['database_item']})
                result = self._handle_wachstumsgradtage(**db_addon_params)

        # handle tagesmitteltemperatur
        elif db_addon_fct == 'tagesmitteltemperatur':
            db_addon_params = item_config.get('params')
            if self.execute_debug:
                self.logger.debug(f"handle_ondemand: {db_addon_fct=} detected; {db_addon_params=}")

            if db_addon_params:
                result = self._handle_tagesmitteltemperatur(database_item, db_addon_fct, ignore_value, db_addon_params)

        # handle db_request
        elif db_addon_fct == 'db_request':
            db_addon_params = item_config.get('params')
            if self.execute_debug:
                self.logger.debug(f"handle_ondemand: {db_addon_fct=} detected with {db_addon_params=}")

            if db_addon_params:
                db_addon_params.update({'database_item': item_config['database_item']})
                if db_addon_params.keys() & {'func', 'item', 'timeframe'}:
                    result = self._query_item(**db_addon_params)
                else:
                    self.logger.error(f"Attribute 'db_addon_params' not containing needed params for Item {item.id} with {db_addon_fct=}.")

        # handle everything else
        else:
            self.logger.warning(f"handle_ondemand: Function '{db_addon_fct}' for item {item.path()} not defined or found.")
            return

        # log result
        if self.execute_debug:
            self.logger.debug(f"handle_ondemand: result is {result} for item '{item.path()}' with '{db_addon_fct=}'")

        if result is None:
            self.logger.info(f"  Result was None; No item value will be set.")
            return

        # set item value and put data into plugin_item_dict
        self.logger.info(f"  Item value for '{item.path()}' will be set to {result}")
        item_config = self.get_item_config(item)
        item_config.update({'value': result})
        item(result, self.get_shortname())

    def handle_onchange(self, updated_item: Item, value: float) -> None:
        """
        Get item and item value for which an update has been detected, fill cache dicts and set item value.

        :param updated_item: Item which has been updated
        :param value: Value of updated item
        """

        if self.onchange_debug:
            self.logger.debug(f"handle_onchange called with updated_item={updated_item.path()} and value={value}.")

        relevant_item_list = self.get_item_list('database_item', updated_item)
        if self.onchange_debug:
            self.logger.debug(f"Following items where identified for update: {relevant_item_list}.")

        for item in relevant_item_list:
            item_config = self.get_item_config(item)
            _database_item = item_config['database_item']
            _db_addon_fct = item_config['db_addon_fct']
            _ignore_value = item_config['ignore_value']
            _var = _db_addon_fct.split('_')

            # handle minmax on-change items like minmax_heute_max, minmax_heute_min, minmax_woche_max, minmax_woche_min.....
            if _db_addon_fct.startswith('minmax') and len(_var) == 3 and _var[2] in ['min', 'max']:
                _timeframe = convert_timeframe(_var[1])
                _func = _var[2]
                _cache_dict = self.current_values[_timeframe]
                if not _timeframe:
                    return

                if self.onchange_debug:
                    self.logger.debug(f"handle_onchange: 'minmax' item {updated_item.path()} with {_func=} detected. Check for update of _cache_dicts and item value.")

                _initial_value = False
                _new_value = None

                # make sure, that database item is in cache dict
                if _database_item not in _cache_dict:
                    _cache_dict[_database_item] = {}
                if _cache_dict[_database_item].get(_func) is None:
                    _query_params = {'func': _func, 'item': _database_item, 'timeframe': _timeframe, 'start': 0, 'end': 0, 'ignore_value': _ignore_value}
                    _cached_value = self._query_item(**_query_params)[0][1]
                    _initial_value = True
                    if self.onchange_debug:
                        self.logger.debug(f"handle_onchange: Item={updated_item.path()} with _func={_func} and _timeframe={_timeframe} not in cache dict. recent value={_cached_value}.")
                else:
                    _cached_value = _cache_dict[_database_item][_func]

                if _cached_value:
                    # check value for update of cache dict
                    if _func == 'min' and value < _cached_value:
                        _new_value = value
                        if self.onchange_debug:
                            self.logger.debug(f"handle_onchange: new value={_new_value} lower then current min_value={_cached_value}. _cache_dict will be updated")
                    elif _func == 'max' and value > _cached_value:
                        _new_value = value
                        if self.onchange_debug:
                            self.logger.debug(f"handle_onchange: new value={_new_value} higher then current max_value={_cached_value}. _cache_dict will be updated")
                    else:
                        if self.onchange_debug:
                            self.logger.debug(f"handle_onchange: new value={_new_value} will not change max/min for period.")
                else:
                    _cached_value = value

                if _initial_value and not _new_value:
                    _new_value = _cached_value
                    if self.onchange_debug:
                        self.logger.debug(f"handle_onchange: initial value for item will be set with value {_new_value}")

                if _new_value:
                    _cache_dict[_database_item][_func] = _new_value
                    self.logger.info(f"Item value for '{item.path()}' with func={_func} will be set to {_new_value}")
                    item_config = self.get_item_config(item)
                    item_config.update({'value': _new_value})
                    item(_new_value, self.get_shortname())
                else:
                    self.logger.info(f"Received value={value} is not influencing min / max value. Therefore item {item.path()} will not be changed.")

            # handle verbrauch on-change items ending with heute, woche, monat, jahr
            elif _db_addon_fct.startswith('verbrauch') and len(_var) == 2 and _var[1] in ['heute', 'woche', 'monat', 'jahr']:
                _timeframe = convert_timeframe(_var[1])
                _cache_dict = self.previous_values[_timeframe]
                if _timeframe is None:
                    return

                # make sure, that database item is in cache dict
                if _database_item not in _cache_dict:
                    _query_params = {'func': 'max', 'item': _database_item, 'timeframe': _timeframe, 'start': 1, 'end': 1, 'ignore_value': _ignore_value}
                    _cached_value = self._query_item(**_query_params)[0][1]
                    _cache_dict[_database_item] = _cached_value
                    if self.onchange_debug:
                        self.logger.debug(f"handle_onchange: Item={updated_item.path()} with {_timeframe=} not in cache dict. Value {_cached_value} has been added.")
                else:
                    _cached_value = _cache_dict[_database_item]

                # calculate value, set item value, put data into plugin_item_dict
                if _cached_value is not None:
                    _new_value = round(value - _cached_value, 1)
                    self.logger.info(f"Item value for '{item.path()}' will be set to {_new_value}")
                    item_config = self.get_item_config(item)
                    item_config.update({'value': _new_value})
                    item(_new_value, self.get_shortname())
                else:
                    self.logger.info(f"Value for end of last {_timeframe} not available. No item value will be set.")

    def _update_database_items(self):
        for item in self._database_item_path_items():
            item_config = self.get_item_config(item)
            database_item_path = item_config.get('database_item')
            database_item = self.items.return_item(database_item_path)

            if database_item is None:
                self.logger.warning(f"Database-Item for Item with config item path for Database-Item {database_item_path!r} not found. Item '{item.path()}' will be removed from plugin.")
                self.remove_item(item)
            else:
                item_config.update({'database_item': database_item})

    @property
    def log_level(self):
        return self.logger.getEffectiveLevel()

    def queue_backlog(self):
        return self.item_queue.qsize()

    def db_version(self):
        return self._get_db_version()

    def _startup_items(self) -> list:
        return self.get_item_list('startup', True)

    def _onchange_items(self) -> list:
        return self.get_item_list('cycle', 'on-change')

    def _daily_items(self) -> list:
        return self.get_item_list('cycle', 'daily')

    def _weekly_items(self) -> list:
        return self.get_item_list('cycle', 'weekly')

    def _monthly_items(self) -> list:
        return self.get_item_list('cycle', 'monthly')

    def _yearly_items(self) -> list:
        return self.get_item_list('cycle', 'yearly')

    def _static_items(self) -> list:
        return self.get_item_list('cycle', 'static')

    def _admin_items(self) -> list:
        return self.get_item_list('db_addon', 'admin')

    def _info_items(self) -> list:
        return self.get_item_list('db_addon', 'info')

    def _database_items(self) -> list:
        return self.get_item_list('db_addon', 'database')

    def _database_item_path_items(self) -> list:
        return self.get_item_list('database_item_path', True)

    def _ondemand_items(self) -> list:
        return self._daily_items() + self._weekly_items() + self._monthly_items() + self._yearly_items() + self._static_items()

    ##############################
    #   Public functions / Using item_path
    ##############################

    def gruenlandtemperatursumme(self, item_path: str, year: Union[int, str]) -> Union[int, None]:
        """
        Query database for gruenlandtemperatursumme for given year or year
        https://de.wikipedia.org/wiki/Gr%C3%BCnlandtemperatursumme

        Beim Grünland wird die Wärmesumme nach Ernst und Loeper benutzt, um den Vegetationsbeginn und somit den Termin von Düngungsmaßnahmen zu bestimmen.
        Dabei erfolgt die Aufsummierung der Tagesmitteltemperaturen über 0 °C, wobei der Januar mit 0.5 und der Februar mit 0.75 gewichtet wird.
        Bei einer Wärmesumme von 200 Grad ist eine Düngung angesagt.

        :param item_path: item object or item_id for which the query should be done
        :param year: year the gruenlandtemperatursumme should be calculated for

        :return: gruenlandtemperatursumme
        """

        item = self.items.return_item(item_path)
        if item:
            return self._handle_gruenlandtemperatursumme(item, year)

    def waermesumme(self, item_path: str, year, month: Union[int, str] = None, threshold: int = 0) -> Union[int, None]:
        """
        Query database for waermesumme for given year or year/month
        https://de.wikipedia.org/wiki/W%C3%A4rmesumme

        :param item_path: item object or item_id for which the query should be done
        :param year: year the waermesumme should be calculated for
        :param month: month the waermesumme should be calculated for
        :param threshold: threshold for temperature

        :return: waermesumme
        """
        item = self.items.return_item(item_path)
        if item:
            return self._handle_waermesumme(item, year, month, threshold)

    def kaeltesumme(self, item_path: str, year, month: Union[int, str] = None) -> Union[int, None]:
        """
        Query database for kaeltesumme for given year or year/month
        https://de.wikipedia.org/wiki/K%C3%A4ltesumme

        :param item_path: item object or item_id for which the query should be done
        :param year: year the kaeltesumme should be calculated for
        :param month: month the kaeltesumme should be calculated for

        :return: kaeltesumme
        """
        item = self.items.return_item(item_path)
        if item:
            return self._handle_kaeltesumme(item, year, month)

    def tagesmitteltemperatur(self, item_path: str, timeframe: str = None, count: int = None) -> list:
        """
        Query database for tagesmitteltemperatur
        https://www.dwd.de/DE/leistungen/klimadatendeutschland/beschreibung_tagesmonatswerte.html

        :param item_path: item object or item_id for which the query should be done
        :param timeframe: timeincrement for determination
        :param count: number of time increments starting from now to the left (into the past)

        :return: tagesmitteltemperatur
        """

        if not timeframe:
            timeframe = 'day'

        if not count:
            count = 0

        item = self.items.return_item(item_path)
        if item:
            return self._handle_tagesmitteltemperatur(database_item=item, db_addon_fct='tagesmitteltemperatur', params={'timeframe': timeframe, 'count': count})

    def wachstumsgradtage(self, item_path: str, year: Union[int, str], threshold: int) -> Union[int, None]:
        """
        Query database for wachstumsgradtage
        https://de.wikipedia.org/wiki/Wachstumsgradtag

        :param item_path: item object or item_id for which the query should be done
        :param year: year the wachstumsgradtage should be calculated for
        :param threshold: Temperature in °C as threshold: Ein Tage mit einer Tagesdurchschnittstemperatur oberhalb des Schellenwertes gilt als Wachstumsgradtag
        :return: wachstumsgradtage
        """

        item = self.items.return_item(item_path)
        if item:
            return self._handle_wachstumsgradtage(item, year, threshold)

    def query_item(self, func: str, item_path: str, timeframe: str, start: int = None, end: int = 0, group: str = None, group2: str = None, ignore_value=None) -> list:
        item = self.items.return_item(item_path)
        if item is None:
            return []

        return self._query_item(func, item, timeframe, start, end, group, group2, ignore_value)

    def fetch_log(self, func: str, item_path: str, timeframe: str, start: int = None, end: int = 0, count: int = None, group: str = None, group2: str = None, ignore_value=None) -> list:
        """
        Query database, format response and return it

        :param func: function to be used at query
        :param item_path: item str or item_id for which the query should be done
        :param timeframe: time increment für definition of start, end, count (day, week, month, year)
        :param start: start of timeframe (oldest) for query given in x time increments (default = None, meaning complete database)
        :param end: end of timeframe (newest) for query given in x time increments (default = 0, meaning today, end of last week, end of last month, end of last year)
        :param count: start of timeframe defined by number of time increments starting from end to the left (into the past)
        :param group: first grouping parameter (default = None, possible values: day, week, month, year)
        :param group2: second grouping parameter (default = None, possible values: day, week, month, year)
        :param ignore_value: value of val_num, which will be ignored during query

        :return: formatted query response
        """
        item = self.items.return_item(item_path)

        if count:
            start, end = count_to_start(count)

        if item and start and end:
            return self._query_item(func=func, item=item, timeframe=timeframe, start=start, end=end, group=group, group2=group2, ignore_value=ignore_value)
        else:
            return []

    def fetch_raw(self, query: str, params: dict = None) -> Union[list, None]:
        """
        Fetch database with given query string and params

        :param query: database query to be executed
        :param params: query parameters

        :return: result of database query
        """

        if params is None:
            params = {}

        formatted_sql = sqlvalidator.format_sql(query)
        sql_query = sqlvalidator.parse(formatted_sql)

        if not sql_query.is_valid():
            self.logger.error(f"fetch_raw: Validation of query failed with error: {sql_query.errors}")
            return

        return self._fetchall(query, params)

    def suspend(self, state: bool = False) -> bool:
        """
        Will pause value evaluation of plugin

        """

        if state:
            self.logger.warning("Plugin is set to 'suspended'. Queries to database will not be made until suspension is cancelled.")
            self.suspended = True
            self._clear_queue()
        else:
            self.logger.warning("Plugin suspension cancelled. Queries to database will be resumed.")
            self.suspended = False

        # write back value to item, if one exists
        for item in self.get_item_list('db_addon', 'admin'):
            item_config = self.get_item_config(item)
            if item_config['db_addon_fct'] == 'suspend':
                item(self.suspended, self.get_shortname())

        return self.suspended

    ##############################
    #   Support stuff / Using Item Object
    ##############################

    def _handle_min_max(self, database_item: Item, db_addon_fct: str, ignore_value=None) -> Union[list, None]:
        """
        Handle execution of min/max calculation
        """
        # handle all on_change functions of format 'minmax_timeframe_function' like 'minmax_heute_max'
        if db_addon_fct in ALL_ONCHANGE_ATTRIBUTES:
            if self.execute_debug:
                self.logger.debug(f"on-change function with 'min/max' detected; will be calculated by next change of database item")
            return

        _var = db_addon_fct.split('_')
        group = None
        group2 = None

        # handle all 'last' functions in format 'minmax_last_window_function' like 'minmax_last_24h_max'
        if len(_var) == 4 and _var[1] == 'last':
            func = _var[3]
            timeframe = convert_timeframe(_var[2][-1:])
            start = to_int(_var[2][:-1])
            end = 0
            log_text = 'minmax_last'
            if timeframe is None or start is None:
                return

        # handle all functions 'min/max/avg' in format 'minmax_timeframe_timedelta_func' like 'minmax_heute_minus2_max'
        elif len(_var) == 4 and _var[2].startswith('minus'):
            func = _var[3]  # min, max, avg
            timeframe = convert_timeframe(_var[1])  # day, week, month, year
            start = to_int(_var[2][-1])  # 1, 2, 3, ...
            end = start
            log_text = 'minmax'
            if timeframe is None or start is None:
                return

        # handle all functions 'serie_min/max/avg' in format 'serie_minmax_timeframe_func_count_group' like 'serie_minmax_monat_min_15m'
        elif _var[0] == 'serie' and _var[1] == 'minmax':
            timeframe = convert_timeframe(_var[2])
            func = _var[3]
            start = to_int(_var[4][:-1])
            end = 0
            group = convert_timeframe(_var[4][len(_var[4]) - 1])
            log_text = 'serie_min/max/avg'
            if timeframe is None or start is None or group is None:
                return
        else:
            self.logger.info(f"_handle_min_max: No adequate function for {db_addon_fct=} found.")
            return

        if func not in ALLOWED_MINMAX_FUNCS:
            self.logger.info(f"_handle_min_max: Called {func=} not in allowed functions={ALLOWED_MINMAX_FUNCS}.")
            return

        query_params = {'item': database_item, 'ignore_value': ignore_value, 'func': func, 'timeframe': timeframe, 'start': start, 'end': end, 'group': group, 'group2': group2}

        if self.execute_debug:
            self.logger.debug(f"_handle_min_max: db_addon_fct={log_text} function detected. {query_params=}")

        return self._query_item(**query_params)

    def _handle_zaehlerstand(self, database_item: Item, db_addon_fct: str, ignore_value=None) -> Union[list, None]:
        """
        Handle execution of Zaehlerstand calculation
        """
        # handle all on_change functions
        if db_addon_fct in ALL_ONCHANGE_ATTRIBUTES:
            if self.execute_debug:
                self.logger.debug(f"on-change function with 'zaehlerstand' detected; will be calculated by next change of database item")
            return

        _var = db_addon_fct.split('_')
        group = None
        group2 = None

        # handle functions starting with 'zaehlerstand' like 'zaehlerstand_heute_minus1'
        if len(_var) == 3 and _var[1] == 'zaehlerstand':
            func = 'max'
            timeframe = convert_timeframe(_var[1])
            start = to_int(_var[2][-1])
            end = start
            log_text = 'zaehlerstand'
            if timeframe is None or start is None:
                return

        # handle all functions 'serie_min/max/avg' in format 'serie_minmax_timeframe_func_count_group' like 'serie_zaehlerstand_tag_30d'
        elif _var[0] == 'serie' and _var[1] == 'zaehlerstand':
            func = 'max'
            timeframe = convert_timeframe(_var[2])
            start = to_int(_var[3][:-1])
            end = 0
            group = convert_timeframe(_var[3][len(_var[3]) - 1])
            log_text = 'serie_min/max/avg'
            if timeframe is None or start is None or group is None:
                return
        else:
            self.logger.info(f"_handle_zaehlerstand: No adequate function for {db_addon_fct=} found.")
            return

        query_params = {'item': database_item, 'ignore_value': ignore_value, 'func': func, 'timeframe': timeframe, 'start': start, 'end': end, 'group': group, 'group2': group2}

        if self.execute_debug:
            self.logger.debug(f"_handle_zaehlerstand: db_addon_fct={log_text} function detected. {query_params=}")

        return self._query_item(**query_params)

    def _handle_verbrauch(self, database_item: Item, db_addon_fct: str, ignore_value=None):
        """
        Handle execution of verbrauch calculation
        """

        self.logger.debug(f"_handle_verbrauch called with {database_item=} and {db_addon_fct=}")

        def consumption_calc(c_start, c_end) -> Union[float, None]:
            """
            Handle query for Verbrauch

            :param c_start:     beginning of timeframe
            :param c_end:       end of timeframe
            """

            if self.prepare_debug:
                self.logger.debug(f"_consumption_calc called with {database_item=}, {timeframe=}, {c_start=}, {c_end=}")

            _result = None
            _query_params = {'item': database_item, 'timeframe': timeframe}

            # get value for end and check it;
            _query_params.update({'func': 'max', 'start': c_end, 'end': c_end})
            value_end = self._query_item(**_query_params)[0][1]

            if self.prepare_debug:
                self.logger.debug(f"_consumption_calc {value_end=}")

            if value_end is None:  # if None (Error) return
                return
            elif value_end == 0:  # wenn die Query "None" ergab, was wiederum bedeutet, dass zum Abfragezeitpunkt keine Daten vorhanden sind, ist der value hier gleich 0 → damit der Verbrauch für die Abfrage auch Null
                return 0

            # get value for start and check it;
            _query_params.update({'func': 'min', 'start': c_end, 'end': c_end})
            value_start = self._query_item(**_query_params)[0][1]
            if self.prepare_debug:
                self.logger.debug(f"_consumption_calc {value_start=}")

            if value_start is None:  # if None (Error) return
                return

            if value_start == 0:  # wenn der Wert zum Startzeitpunkt 0 ist, gab es dort keinen Eintrag (also keinen Verbrauch), dann frage den nächsten Eintrag in der DB ab.
                self.logger.info(f"No DB Entry found for requested start date. Looking for next DB entry.")
                _query_params.update({'func': 'next', 'start': c_start, 'end': c_end})
                value_start = self._query_item(**_query_params)[0][1]
                if self.prepare_debug:
                    self.logger.debug(f"_consumption_calc: next available value is {value_start=}")

            # calculate result
            if value_start is not None:
                return round(value_end - value_start, 1)

        # handle all on_change functions of format 'verbrauch_timeframe' like 'verbrauch_heute'
        if db_addon_fct in ALL_ONCHANGE_ATTRIBUTES:
            if self.execute_debug:
                self.logger.debug(f"on_change function with 'verbrauch' detected; will be calculated by next change of database item")
            return

        _var = db_addon_fct.split('_')

        # handle all functions 'verbrauch' in format 'verbrauch_timeframe_timedelta' like 'verbrauch_heute_minus2'
        if len(_var) == 3 and _var[1] in ['heute', 'woche', 'monat', 'jahr'] and _var[2].startswith('minus'):
            timeframe = convert_timeframe(_var[1])
            timedelta = to_int(_var[2][-1])
            if timedelta is None or timeframe is None:
                return

            if self.execute_debug:
                self.logger.debug(f"_handle_verbrauch: '{db_addon_fct}' function detected. {timeframe=}, {timedelta=}")

            return consumption_calc(c_start=timedelta + 1, c_end=timedelta)

        # handle all functions of format 'verbrauch_function_window_timeframe_timedelta' like 'verbrauch_rolling_12m_woche_minus1'
        elif len(_var) == 5 and _var[1] == 'rolling' and _var[4].startswith('minus'):
            func = _var[1]
            window = _var[2]  # 12m
            window_inc = to_int(window[:-1])  # 12
            window_dur = convert_timeframe(window[-1])  # day, week, month, year
            timeframe = convert_timeframe(_var[3])  # day, week, month, year
            timedelta = to_int(_var[4][-1])  # 1
            endtime = timedelta

            if window_inc is None or window_dur is None or timeframe is None or timedelta is None:
                return

            if self.execute_debug:
                self.logger.debug(f"_handle_verbrauch: '{func}' function detected. {window=}, {timeframe=}, {timedelta=}")

            if window_dur in ['day', 'week', 'month', 'year']:
                starttime = convert_duration(timeframe, window_dur) * window_inc
                return consumption_calc(c_start=starttime, c_end=endtime)

        # handle all functions of format 'verbrauch_timeframe_timedelta' like 'verbrauch_jahreszeitraum_minus1'
        elif len(_var) == 3 and _var[1] == 'jahreszeitraum' and _var[2].startswith('minus'):
            timeframe = convert_timeframe(_var[1])  # day, week, month, year
            timedelta = to_int(_var[2][-1])  # 1 oder 2 oder 3
            if timedelta is None or timeframe is None:
                return

            if self.execute_debug:
                self.logger.debug(f"_handle_verbrauch: '{db_addon_fct}' function detected. {timeframe=}, {timedelta=}")

            today = datetime.date.today()
            year = today.year - timedelta
            start_date = datetime.date(year, 1, 1) - relativedelta(days=1)  # Start ist Tag vor dem 1.1., damit Abfrage den Maximalwert von 31.12. 00:00:00 bis 1.1. 00:00:00 ergibt
            end_date = today - relativedelta(years=timedelta)
            start = (today - start_date).days
            end = (today - end_date).days

            return consumption_calc(c_start=start, c_end=end)

        # handle all functions of format 'serie_verbrauch_timeframe_countgroup' like 'serie_verbrauch_tag_30d'
        elif db_addon_fct.startswith('serie_') and len(_var) == 4:
            self.logger.debug(f"_handle_verbrauch serie reached")
            func = 'diff_max'
            timeframe = convert_timeframe(_var[2])
            start = to_int(_var[3][:-1])
            group = convert_timeframe(_var[3][len(_var[3]) - 1])
            group2 = None
            if timeframe is None or start is None or group is None:
                self.logger.warning(f"For calculating '{db_addon_fct}' not all mandatory parameters given. {timeframe=}, {start=}, {group=}")
                return

            query_params = {'func': func, 'item': database_item, 'timeframe': timeframe, 'start': start, 'end': 0, 'group': group, 'group2': group2, 'ignore_value': ignore_value}

            if self.execute_debug:
                self.logger.debug(f"_handle_verbrauch: 'serie_verbrauch_timeframe_countgroup' function detected. {query_params=}")

            return self._query_item(**query_params)

        else:
            self.logger.info(f"_handle_verbrauch: No adequate function for {db_addon_fct=} found.")
            return

    def _handle_tagesmitteltemperatur(self, database_item: Item, db_addon_fct: str, ignore_value=None, params: dict = None) -> list:
        """
        Query database for tagesmitteltemperatur

        :param database_item: item object or item_id for which the query should be done
        :param db_addon_fct
        :param ignore_value
        :param params:
        :return: tagesmitteltemperatur
        """

        # handle all on_change functions
        if db_addon_fct in ALL_ONCHANGE_ATTRIBUTES:
            if self.execute_debug:
                self.logger.debug(f"on_change function with 'tagesmitteltemperatur' detected; will be calculated by next change of database item")
            return []

        _var = db_addon_fct.split('_')
        group = None
        group2 = None

        # handle tagesmitteltemperatur
        if db_addon_fct == 'tagesmitteltemperatur':
            if not params:
                return []

            func = 'max'
            timeframe = convert_timeframe(params.get('timeframe'))
            log_text = 'tagesmitteltemperatur'
            count = to_int(params.get('count'))
            if timeframe is None or not count:
                return []

            start, end = count_to_start(count)

        # handle 'tagesmittelwert_timeframe_timedelta' like 'tagesmittelwert_heute_minus1'
        elif len(_var) == 3 and _var[2].startswith('minus'):
            func = 'max'
            timeframe = convert_timeframe(_var[1])
            start = to_int(_var[2][-1])
            end = start
            log_text = 'tagesmittelwert_timeframe_timedelta'
            if timeframe is None or start is None:
                return []

        # handle 'serie_tagesmittelwert_countgroup' like 'serie_tagesmittelwert_0d'
        elif db_addon_fct.startswith('serie_') and len(_var) == 3:
            # 'serie_tagesmittelwert_0d':             {'func': 'max',         'timeframe': 'year',  'start': 0,    'end': 0,    'group': 'day'},
            func = 'max'
            timeframe = 'year'
            log_text = 'serie_tagesmittelwert_countgroup'
            start = to_int(_var[2][:-1])
            end = 0
            group = convert_timeframe(_var[2][len(_var[2]) - 1])
            if group is None or start is None:
                return []

        # handle 'serie_tagesmittelwert_group2_count_group' like 'serie_tagesmittelwert_stunde_0d'
        elif db_addon_fct.startswith('serie_') and len(_var) == 4:
            # 'serie_tagesmittelwert_stunde_0d':      {'func': 'avg1',        'timeframe': 'day',   'start': 0,    'end': 0,    'group': 'hour', 'group2': 'day'},
            # 'serie_tagesmittelwert_stunde_30d':     {'func': 'avg1',        'timeframe': 'day',   'start': 30,   'end': 0,    'group': 'hour', 'group2': 'day'},
            func = 'avg1'
            timeframe = 'day'
            log_text = 'serie_tagesmittelwert_group2_countgroup'
            start = to_int(_var[3][:-1])
            end = 0
            group = 'hour'
            group2 = convert_timeframe(_var[3][len(_var[3]) - 1])
            if group2 is None or start is None:
                return []

        # handle 'serie_tagesmittelwert_group2_start_endgroup' like 'serie_tagesmittelwert_stunde_30_0d'
        elif db_addon_fct.startswith('serie_') and len(_var) == 5:
            func = 'avg1'
            timeframe = 'day'
            log_text = 'serie_tagesmittelwert_group2_start_endgroup'
            start = to_int(_var[3])
            end = to_int(_var[4][:-1])
            group = 'hour'
            group2 = convert_timeframe(_var[4][len(_var[4]) - 1])
            if group2 is None or start is None or end is None:
                return []

        # handle everything else
        else:
            self.logger.info(f"_handle_tagesmitteltemperatur: No adequate function for {db_addon_fct=} found.")
            return []

        query_params = {'item': database_item, 'ignore_value': ignore_value, 'func': func, 'timeframe': timeframe, 'start': start, 'end': end, 'group': group, 'group2': group2}

        if self.execute_debug:
            self.logger.debug(f"_handle_tagesmitteltemperatur: db_addon_fct={log_text} function detected. {query_params=}")

        return self._query_item(**query_params)

    def _handle_kaeltesumme(self, database_item: Item, year: Union[int, str], month: Union[int, str] = None) -> Union[int, None]:
        """
        Query database for kaeltesumme for given year or year/month
        https://de.wikipedia.org/wiki/K%C3%A4ltesumme

        :param database_item: item object or item_id for which the query should be done
        :param year: year the kaeltesumme should be calculated for
        :param month: month the kaeltesumme should be calculated for
        :return: kaeltesumme
        """

        self.logger.debug(f"_handle_kaeltesumme called with {database_item=}, {year=}, {month=}")

        # check validity of given year
        if not valid_year(year):
            self.logger.error(f"_handle_kaeltesumme: Year for item={database_item.path()} was {year}. This is not a valid year. Query cancelled.")
            return

        # define year
        if year == 'current':
            if datetime.date.today() < datetime.date(int(datetime.date.today().year), 9, 21):
                year = datetime.date.today().year - 1
            else:
                year = datetime.date.today().year

        # define start_date and end_date
        if month is None:
            start_date = datetime.date(int(year), 9, 21)
            end_date = datetime.date(int(year) + 1, 3, 22)
        elif valid_month(month):
            start_date = datetime.date(int(year), int(month), 1)
            end_date = start_date + relativedelta(months=+1) - datetime.timedelta(days=1)
        else:
            self.logger.error(f"_handle_kaeltesumme: Month for item={database_item.path()} was {month}. This is not a valid month. Query cancelled.")
            return

        # define start / end
        today = datetime.date.today()
        if start_date > today:
            self.logger.error(f"_handle_kaeltesumme: Start time for query of item={database_item.path()} is in future. Query cancelled.")
            return

        start = (today - start_date).days
        end = (today - end_date).days if end_date < today else 0
        if start < end:
            self.logger.error(f"_handle_kaeltesumme: End time for query of item={database_item.path()} is before start time. Query cancelled.")
            return

        # get raw data as list
        self.logger.debug("_handle_kaeltesumme: Try to get raw data")
        raw_data = self._prepare_temperature_list(database_item=database_item, start=start, end=end, version='raw')
        if self.execute_debug:
            self.logger.debug(f"_handle_kaeltesumme: raw_value_list={raw_data=}")

        # calculate value
        if raw_data and isinstance(raw_data, list):
            if raw_data == [[None, None]]:
                return

            # akkumulieren alle negativen Werte
            ks = 0
            for entry in raw_data:
                if entry[1] < 0:
                    ks -= entry[1]
            return int(round(ks, 0))

    def _handle_waermesumme(self, database_item: Item, year: Union[int, str], month: Union[int, str] = None, threshold: int = 0) -> Union[int, None]:
        """
        Query database for waermesumme for given year or year/month
        https://de.wikipedia.org/wiki/W%C3%A4rmesumme

        :param database_item: item object or item_id for which the query should be done
        :param year: year the waermesumme should be calculated for; "current" for current year
        :param month: month the waermesumme should be calculated for
        :return: waermesumme
        """

        # start: links / älterer Termin          end: rechts / jüngerer Termin

        # check validity of given year
        if not valid_year(year):
            self.logger.error(f"_handle_waermesumme: Year for item={database_item.path()} was {year}. This is not a valid year. Query cancelled.")
            return

        # define year
        if year == 'current':
            year = datetime.date.today().year

        # define start_date, end_date
        if month is None:
            start_date = datetime.date(int(year), 1, 1)
            end_date = datetime.date(int(year), 9, 21)
        elif valid_month(month):
            start_date = datetime.date(int(year), int(month), 1)
            end_date = start_date + relativedelta(months=+1) - datetime.timedelta(days=1)
        else:
            self.logger.error(f"_handle_waermesumme: Month for item={database_item.path()} was {month}. This is not a valid month. Query cancelled.")
            return

        # check start_date
        today = datetime.date.today()
        if start_date > today:
            self.logger.info(f"_handle_waermesumme: Start time for query of item={database_item.path()} is in future. Query cancelled.")
            return

        # define start / end
        start = (today - start_date).days
        end = (today - end_date).days if end_date < today else 0

        # check end
        if start < end:
            self.logger.error(f"_handle_waermesumme: End time for query of item={database_item.path()} is before start time. Query cancelled.")
            return

        # get raw data as list
        raw_data = self._prepare_temperature_list(database_item=database_item, start=start, end=end, version='raw')
        if self.execute_debug:
            self.logger.debug(f"_handle_waermesumme: raw_value_list={raw_data=}")

        # set threshold to min 0
        threshold = min(0, threshold)

        # calculate value
        if raw_data and isinstance(raw_data, list):
            if raw_data == [[None, None]]:
                return

            # akkumulieren alle Werte, größer/gleich Schwellenwert
            ws = 0
            for entry in raw_data:
                if entry[1] >= threshold:
                    ws += entry[1]
            return int(round(ws, 0))

    def _handle_gruenlandtemperatursumme(self, database_item: Item, year: Union[int, str]) -> Union[int, None]:
        """
        Query database for gruenlandtemperatursumme for given year or year/month
        https://de.wikipedia.org/wiki/Gr%C3%BCnlandtemperatursumme

        :param database_item: item object for which the query should be done
        :param year: year the gruenlandtemperatursumme should be calculated for
        :return: gruenlandtemperatursumme
        """

        if not valid_year(year):
            self.logger.error(f"_handle_gruenlandtemperatursumme: Year for item={database_item.path()} was {year}. This is not a valid year. Query cancelled.")
            return

        # define year
        if year == 'current':
            year = datetime.date.today().year

        # define start_date, end_date
        start_date = datetime.date(int(year), 1, 1)
        end_date = datetime.date(int(year), 9, 21)

        # check start_date
        today = datetime.date.today()
        if start_date > today:
            self.logger.info(f"_handle_gruenlandtemperatursumme: Start time for query of item={database_item.path()} is in future. Query cancelled.")
            return

        # define start / end
        start = (today - start_date).days
        end = (today - end_date).days if end_date < today else 0

        # check end
        if start < end:
            self.logger.error(f"_handle_gruenlandtemperatursumme: End time for query of item={database_item.path()} is before start time. Query cancelled.")
            return

        # get raw data as list
        raw_data = self._prepare_temperature_list(database_item=database_item, start=start, end=end, version='raw')
        if self.execute_debug:
            self.logger.debug(f"_handle_gruenlandtemperatursumme: raw_value_list={raw_data}")

        # calculate value
        if raw_data and isinstance(raw_data, list):
            if raw_data == [[None, None]]:
                return

            # akkumulieren alle Werte, größer/gleich Schwellenwert, im Januar gewichtet mit 50%, im Februar mit 75%
            try:
                gts = 0
                for entry in raw_data:
                    timestamp, value = entry
                    dt = datetime.datetime.fromtimestamp(timestamp / 1000)
                    if dt.month == 1:
                        value = value * 0.5
                    elif dt.month == 2:
                        value = value * 0.75
                    gts += value
                return int(round(gts, 0))
            except Exception as e:
                self.logger.error(f"Error {e} occurred during calculation of gruenlandtemperatursumme with {raw_data=} for {database_item.path()=}")

    def _handle_wachstumsgradtage(self, database_item: Item, year: Union[int, str], method: int = 0, threshold: int = 10):
        """
        Calculate "wachstumsgradtage" for given year with temperature thershold
        https://de.wikipedia.org/wiki/Wachstumsgradtag

        :param database_item: item object or item_id for which the query should be done
        :param year: year the wachstumsgradtage should be calculated for
        :param threshold: temperature in °C as threshold for evaluation
        :return: wachstumsgradtage
        """

        if not valid_year(year):
            self.logger.error(f"_handle_wachstumsgradtage: Year for item={database_item.path()} was {year}. This is not a valid year. Query cancelled.")
            return

        # define year
        if year == 'current':
            year = datetime.date.today().year

        # define start_date, end_date
        start_date = datetime.date(int(year), 1, 1)
        end_date = datetime.date(int(year), 9, 21)

        # check start_date
        today = datetime.date.today()
        if start_date > today:
            self.logger.info(f"_handle_wachstumsgradtage: Start time for query of item={database_item.path()} is in future. Query cancelled.")
            return

        # define start / end
        start = (today - start_date).days
        end = (today - end_date).days if end_date < today else 0

        # check end
        if start < end:
            self.logger.error(f"_handle_wachstumsgradtage: End time for query of item={database_item.path()} is before start time. Query cancelled.")
            return

        # get raw data as list
        raw_data = self._prepare_temperature_list(database_item=database_item, start=start, end=end, version='minmax')
        if self.execute_debug:
            self.logger.debug(f"_handle_wachstumsgradtage: raw_value_list={raw_data}")

        # calculate value
        if raw_data and isinstance(raw_data, list):
            if raw_data == [[None, None]]:
                return

        # Die Berechnung des einfachen Durchschnitts // akkumuliere positive Differenz aus Mittelwert aus Tagesminimaltemperatur und Tagesmaximaltemperatur limitiert auf 30°C und Schwellenwert
        wgte = 0
        wgte_list = []
        if method == 0 or method == 10:
            self.logger.info(f"Caluclate 'Wachstumsgradtag' according to 'Berechnung des einfachen Durchschnitts'.")
            for entry in raw_data:
                timestamp, min_val, max_val = entry
                wgt = (((min_val + min(30, max_val)) / 2) - threshold)
                if wgt > 0:
                    wgte += wgt
                wgte_list.append([timestamp, int(round(wgte, 0))])
            if method == 0:
                return int(round(wgte, 0))
            else:
                return wgte_list

        # Die modifizierte Berechnung des einfachen Durchschnitts. // akkumuliere positive Differenz aus Mittelwert aus Tagesminimaltemperatur mit mind Schwellentemperatur und Tagesmaximaltemperatur limitiert auf 30°C und Schwellenwert
        elif method == 1 or method == 11:
            self.logger.info(f"Caluclate 'Wachstumsgradtag' according to 'Modifizierte Berechnung des einfachen Durchschnitts'.")
            for entry in raw_data:
                timestamp, min_val, max_val = entry
                wgt = (((max(threshold, min_val) + min(30.0, max_val)) / 2) - threshold)
                if wgt > 0:
                    wgte += wgt
                wgte_list.append([timestamp, int(round(wgte, 0))])
            if method == 1:
                return int(round(wgte, 0))
            else:
                return wgte_list
        else:
            self.logger.info(f"Method for 'Wachstumsgradtag' calculation not defined.'")

    def _prepare_temperature_list(self, database_item: Item, start: int, end: int = 0, ignore_value=None, version: str = 'hour') -> list:

        self.logger.debug(f"_prepare_temperature_list called with {database_item=}, {start=}, {end=}, {ignore_value=}, {version=}")

        def _create_temp_dict() -> dict:
            """create dict based on database query result like {'date1': {'hour1': [temp values], 'hour2': [temp values], ...}, 'date2': {'hour1': [temp values], 'hour2': [temp values], ...}, ...}"""
            _temp_dict = {}
            for _entry in raw_value_list:
                dt = datetime.datetime.utcfromtimestamp(_entry[0] / 1000)
                date = dt.strftime('%Y-%m-%d')
                hour = dt.strftime('%H')
                if date not in _temp_dict:
                    _temp_dict[date] = {}
                if hour not in _temp_dict[date]:
                    _temp_dict[date][hour] = []
                _temp_dict[date][hour].append(_entry[1])
            return _temp_dict

        def _calculate_hourly_average():
            """ calculate hourly average based on list of temperatures and update temp_dict"""
            for _date in temp_dict:
                for hour in temp_dict[_date]:
                    hour_raw_value_list = temp_dict[_date][hour]
                    # hour_value = round(sum(hour_raw_value_list) / len(hour_raw_value_list), 1)  # Durchschnittsbildung über alle Werte der Liste
                    hour_value = hour_raw_value_list[0]  # Nehme den ersten Wert der Liste als Stundenwert (kommt am nächsten an die Definition, den Wert exakt zur vollen Stunden zu nehmen)
                    temp_dict[_date][hour] = [hour_value]

        def _create_list_timestamp_avgtemp() -> list:
            """Create list of list with [[timestamp1, value1], [timestamp2, value2], ...] based on temp_dict"""
            _temp_list = []
            for _date in temp_dict:

                # wenn mehr als 20 Stundenwerte vorliegen, berechne den Tagesdurchschnitt über alle Werte
                if len(temp_dict[_date]) >= 20:
                    _values = sum(list(temp_dict[_date].values()), [])
                    _values_avg = round(sum(_values) / len(_values), 1)

                # wenn für 00, 06, 12 und 18 Uhr Werte vorliegen, berechne den Tagesdurchschnitt über diese Werte
                elif '00' in temp_dict[_date] and '06' in temp_dict[_date] and '12' in temp_dict[_date] and '18' in temp_dict[_date]:
                    _values_avg = round((temp_dict[_date]['00'][0] + temp_dict[_date]['06'][0] + temp_dict[_date]['12'][0] + temp_dict[_date]['18'][0]) / 4, 1)

                # sonst berechne den Tagesdurchschnitt über alle Werte
                else:
                    _values = sum(list(temp_dict[_date].values()), [])
                    _values_avg = round(sum(_values) / len(_values), 1)

                _timestamp = datetime_to_timestamp(datetime.datetime.strptime(_date, '%Y-%m-%d'))
                _temp_list.append([_timestamp, _values_avg])
            return _temp_list

        def _create_list_timestamp_minmaxtemp() -> list:
            """Create list of list with [[timestamp1, min value1, max_value1], [timestamp2, min value2, max_value2], ...] based on temp_dict"""
            _temp_list = []
            for _date in temp_dict:
                _timestamp = datetime_to_timestamp(datetime.datetime.strptime(_date, '%Y-%m-%d'))
                _day_values = sum(list(temp_dict[_date].values()), [])
                _temp_list.append([_timestamp, min(_day_values), max(_day_values)])
            return _temp_list

        if version == 'hour':
            raw_value_list = self._query_item(func='avg', item=database_item, timeframe='day', start=start, end=end, group='hour', ignore_value=ignore_value)
            self.logger.debug(f"{raw_value_list=}")

            # create nested dict with temps
            temp_dict = _create_temp_dict()

            # create list of list like database query response
            temp_list = _create_list_timestamp_avgtemp()
            self.logger.debug(f"{temp_list=}")
            return temp_list

        elif version == 'raw':
            raw_value_list = self._query_item(func='raw', item=database_item, timeframe='day', start=start, end=end, ignore_value=ignore_value)
            self.logger.debug(f"{raw_value_list=}")

            # create nested dict with temps
            temp_dict = _create_temp_dict()
            self.logger.debug(f"raw: {temp_dict=}")

            # calculate 'tagesdurchschnitt' and create list of list like database query response
            _calculate_hourly_average()
            self.logger.debug(f"raw: {temp_dict=}")

            # create list of list like database query response
            temp_list = _create_list_timestamp_avgtemp()
            self.logger.debug(f"{temp_list=}")
            return temp_list

        elif version == 'minmax':
            raw_value_list = self._query_item(func='raw', item=database_item, timeframe='day', start=start, end=end, ignore_value=ignore_value)
            self.logger.debug(f"{raw_value_list=}")

            # create nested dict with temps
            temp_dict = _create_temp_dict()
            self.logger.debug(f"raw: {temp_dict=}")

            # create list of list like database query response
            temp_list = _create_list_timestamp_minmaxtemp()
            self.logger.debug(f"{temp_list=}")
            return temp_list

        else:
            return []

    def _create_due_items(self) -> list:
        """
        Create set of items which are due and resets cache dicts

        :return: set of items, which need to be processed

        """

        # täglich zu berechnende Items zur Action Liste hinzufügen
        _todo_items = set()
        _todo_items.update(set(self._daily_items()))
        self.current_values[DAY] = {}
        self.previous_values[DAY] = {}

        # wenn Wochentag == Montag, werden auch die wöchentlichen Items berechnet
        if self.shtime.now().hour == 0 and self.shtime.now().minute == 0 and self.shtime.weekday(self.shtime.today()) == 1:
            _todo_items.update(set(self._weekly_items()))
            self.current_values[WEEK] = {}
            self.previous_values[WEEK] = {}

        # wenn der erste Tage eines Monates ist, werden auch die monatlichen Items berechnet
        if self.shtime.now().hour == 0 and self.shtime.now().minute == 0 and self.shtime.now().day == 1:
            _todo_items.update(set(self._monthly_items()))
            self.current_values[MONTH] = {}
            self.previous_values[MONTH] = {}

        # wenn der erste Tage des ersten Monates eines Jahres ist, werden auch die jährlichen Items berechnet
        if self.shtime.now().hour == 0 and self.shtime.now().minute == 0 and self.shtime.now().day == 1 and self.shtime.now().month == 1:
            _todo_items.update(set(self._yearly_items()))
            self.current_values[YEAR] = {}
            self.previous_values[YEAR] = {}

        return list(_todo_items)

    def _check_db_existence(self) -> bool:
        """
        Check existence of database plugin with given config name

        :return: Status of db existence
        """

        try:
            _db_plugin = self.plugins.return_plugin(self.db_configname)
        except Exception as e:
            self.logger.error(f"Database plugin not loaded, Error was {e}. No need for DatabaseAddOn Plugin.")
            return False
        else:
            if not _db_plugin:
                self.logger.error(f"Database plugin not loaded or given ConfigName {self.db_configname} not correct. No need for DatabaseAddOn Plugin.")
                return False
            else:
                self.logger.debug(f"Corresponding plugin 'database' with given config name '{self.db_configname}' found.")
                self._db_plugin = _db_plugin
                return self._get_db_parameter()

    def _get_db_parameter(self) -> bool:
        """
        Get driver of database and connection parameter

        :return: Status of db connection parameters
        """

        try:
            self.db_driver = self._db_plugin.get_parameter_value('driver')
        except Exception as e:
            self.logger.error(f"Error {e} occurred during getting database plugin parameter 'driver'. DatabaseAddOn Plugin not loaded.")
            return False
        else:
            if self.db_driver.lower() == 'pymysql':
                self.logger.debug(f"Database is of type 'mysql' found.")
            if self.db_driver.lower() == 'sqlite3':
                self.logger.debug(f"Database is of type 'sqlite' found.")

        # get database plugin parameters
        try:
            db_instance = self._db_plugin.get_instance_name()
            if db_instance != "":
                self.db_instance = db_instance
                self.item_attribute_search_str = f"{self.item_attribute_search_str}@{self.db_instance}"
            self.connection_data = self._db_plugin.get_parameter_value('connect')  # pymsql ['host:localhost', 'user:smarthome', 'passwd:smarthome', 'db:smarthome', 'port:3306']
            self.logger.debug(f"Database Plugin available with instance={self.db_instance} and connection={self.connection_data}")
        except Exception as e:
            self.logger.error(f"Error {e} occurred during getting database plugin parameters. DatabaseAddOn Plugin not loaded.")
            return False
        else:
            return True

    def _initialize_db(self) -> bool:
        """
        Initializes database connection

        :return: Status of initialization
        """

        try:
            if not self._db.connected():
                # limit connection requests to 20 seconds.
                current_time = time.time()
                time_delta_last_connect = current_time - self.last_connect_time
                # self.logger.debug(f"DEBUG: delta {time_delta_last_connect}")
                if time_delta_last_connect > 20:
                    self.last_connect_time = time.time()
                    self._db.connect()
                else:
                    self.logger.error(f"_initialize_db: Database reconnect suppressed: Delta time: {time_delta_last_connect}")
                    return False
        except Exception as e:
            self.logger.critical(f"_initialize_db: Database: Initialization failed: {e}")
            return False
        else:
            return True

    def _check_db_connection_setting(self) -> None:
        """
        Check Setting of DB connection for stable use.
        """
        try:
            connect_timeout = int(self._get_db_connect_timeout()[1])
            if connect_timeout < self.default_connect_timeout:
                self.logger.warning(f"DB variable 'connect_timeout' should be adjusted for proper working to {self.default_connect_timeout}. Current setting is {connect_timeout}. You need to insert adequate entries into /etc/mysql/my.cnf within section [mysqld].")
        except Exception:
            pass

        try:
            net_read_timeout = int(self._get_db_net_read_timeout()[1])
            if net_read_timeout < self.default_net_read_timeout:
                self.logger.warning(f"DB variable 'net_read_timeout' should be adjusted for proper working to {self.default_net_read_timeout}. Current setting is {net_read_timeout}. You need to insert adequate entries into /etc/mysql/my.cnf within section [mysqld].")
        except Exception:
            pass

    def _get_oldest_log(self, item: Item) -> int:
        """
        Get timestamp of the oldest entry of item from cache dict or get value from db and put it to cache dict

        :param item: Item, for which query should be done
        :return: timestamp of the oldest log
        """

        _oldest_log = self.item_cache.get(item, {}).get('oldest_log', None)

        if _oldest_log is None:
            item_id = self._get_itemid(item)
            _oldest_log = self._read_log_oldest(item_id)
            if item not in self.item_cache:
                self.item_cache[item] = {}
            self.item_cache[item]['oldest_log'] = _oldest_log

        if self.prepare_debug:
            self.logger.debug(f"_get_oldest_log for item {item.path()} = {_oldest_log}")

        return _oldest_log

    def _get_oldest_value(self, item: Item) -> Union[int, float, bool]:
        """
        Get value of the oldest log of item from cache dict or get value from db and put it to cache dict

        :param item: Item, for which query should be done
        :return: oldest value
        """

        _oldest_entry = self.item_cache.get(item, {}).get('_oldest_entry', None)

        if _oldest_entry is not None:
            _oldest_value = _oldest_entry[0][4]
        else:
            item_id = self._get_itemid(item)
            validity = False
            i = 0
            _oldest_value = -999999999
            while validity is False:
                oldest_entry = self._read_log_timestamp(item_id, self._get_oldest_log(item))
                i += 1
                if isinstance(oldest_entry, list) and isinstance(oldest_entry[0], tuple) and len(oldest_entry[0]) >= 4:
                    if item not in self.item_cache:
                        self.item_cache[item] = {}
                    self.item_cache[item]['oldest_entry'] = oldest_entry
                    _oldest_value = oldest_entry[0][4]
                    validity = True
                elif i == 10:
                    validity = True
                    self.logger.error(f"oldest_value for item {item.path()} could not be read; value is set to -999999999")

        if self.prepare_debug:
            self.logger.debug(f"_get_oldest_value for item {item.path()} = {_oldest_value}")

        return _oldest_value

    def _get_itemid(self, item: Item) -> int:
        """
        Returns the ID of the given item from cache dict or request it from database

        :param item: Item to get the ID for
        :return: id of the item within the database
        """

        # self.logger.debug(f"_get_itemid called with item={item.path()}")
        _item_id = self.item_cache.get(item, {}).get('id', None)

        if _item_id is None:
            row = self._read_item_table(item_path=str(item.path()))
            if row and len(row) > 0:
                _item_id = int(row[0])
                if item not in self.item_cache:
                    self.item_cache[item] = {}
                self.item_cache[item]['id'] = _item_id

        return _item_id

    def _get_itemid_for_query(self, item: Union[Item, str, int]) -> Union[int, None]:
        """
        Get DB item id for query

        :param item: item, the query should be done for

        """

        if isinstance(item, Item):
            item_id = self._get_itemid(item)
        elif isinstance(item, str) and item.isdigit():
            item_id = int(item)
        elif isinstance(item, int):
            item_id = item
        else:
            item_id = None
        return item_id

    def _query_item(self, func: str, item: Item, timeframe: str, start: int = None, end: int = 0, group: str = None, group2: str = None, ignore_value=None) -> list:
        """
        Do diverse checks of input, and prepare query of log by getting item_id, start / end in timestamp etc.

        :param func: function to be used at query
        :param item: item object or item_id for which the query should be done
        :param timeframe: time increment für definition of start, end (day, week, month, year)
        :param start: start of timeframe (oldest) for query given in x time increments (default = None, meaning complete database)
        :param end: end of timeframe (newest) for query given in x time increments (default = 0, meaning end of today, end of last week, end of last month, end of last year)
        :param group: first grouping parameter (default = None, possible values: day, week, month, year)
        :param group2: second grouping parameter (default = None, possible values: day, week, month, year)
        :param ignore_value: value of val_num, which will be ignored during query

        :return: query response / list for value pairs [[None, None]] for errors, [[0,0]] for
        """

        def _handle_query_result(query_result) -> list:
            """
            Handle query result containing list
            """

            # if query delivers None, abort
            if query_result is None:
                # if query delivers None, abort
                self.logger.error(f"Error occurred during _query_item. Aborting...")
                _result = [[None, None]]
            elif len(query_result) == 0:
                _result = [[0, 0]]
                self.logger.info(f" No values for item in requested timeframe in database found.")
            else:
                _result = []
                for element in query_result:
                    timestamp = element[0]
                    value = element[1]
                    if timestamp and value is not None:
                        _result.append([timestamp, round(value, 1)])
                if not _result:
                    _result = [[None, None]]

            return _result

        if self.prepare_debug:
            self.logger.debug(f"_query_item called with {func=}, item={item.path()}, {timeframe=}, {start=}, {end=}, {group=}, {group2=}, {ignore_value=}")

        # set default result
        result = [[None, None]]

        # check correctness of timeframe
        if timeframe not in ALLOWED_QUERY_TIMEFRAMES:
            self.logger.error(f"_query_item: Requested {timeframe=} for item={item.path()} not defined; Need to be 'year' or 'month' or 'week' or 'day' or 'hour''. Query cancelled.")
            return result

        # check start / end for being int
        if isinstance(start, str) and start.isdigit():
            start = int(start)
        if isinstance(end, str) and end.isdigit():
            end = int(end)
        if not isinstance(start, int) and not isinstance(end, int):
            return result

        # check correctness of start / end
        if start < end:
            self.logger.warning(f"_query_item: Requested {start=} for item={item.path()} is not valid since {start=} < {end=}. Query cancelled.")
            return result

        # define item_id
        item_id = self._get_itemid(item)
        if not item_id:
            self.logger.error(f"_query_item: ItemId for item={item.path()} not found. Query cancelled.")
            return result

        # define start and end of query as timestamp in microseconds
        ts_start, ts_end = get_start_end_as_timestamp(timeframe, start, end)
        oldest_log = int(self._get_oldest_log(item))

        if start is None:
            ts_start = oldest_log

        if self.prepare_debug:
            self.logger.debug(f"_query_item: Requested {timeframe=} with {start=} and {end=} resulted in start being timestamp={ts_start} / {timestamp_to_timestring(ts_start)} and end being timestamp={ts_end} / {timestamp_to_timestring(ts_end)}")

        # check if values for end time and start time are in database
        if ts_end < oldest_log:  # (Abfrage abbrechen, wenn Endzeitpunkt in UNIX-timestamp der Abfrage kleiner (und damit jünger) ist, als der UNIX-timestamp des ältesten Eintrages)
            self.logger.info(f"_query_item: Requested end time timestamp={ts_end} / {timestamp_to_timestring(ts_end)} of query for Item='{item.path()}' is prior to oldest entry with timestamp={oldest_log} / {timestamp_to_timestring(oldest_log)}. Query cancelled.")
            return result

        if ts_start < oldest_log:
            if not self.use_oldest_entry:
                self.logger.info(f"_query_item: Requested start time timestamp={ts_start} / {timestamp_to_timestring(ts_start)} of query for Item='{item.path()}' is prior to oldest entry with timestamp={oldest_log} / {timestamp_to_timestring(oldest_log)}. Query cancelled.")
                return result
            else:
                self.logger.info(f"_query_item: Requested start time timestamp={ts_start} / {timestamp_to_timestring(ts_start)} of query for Item='{item.path()}' is prior to oldest entry with timestamp={oldest_log} / {timestamp_to_timestring(oldest_log)}. Oldest available entry will be used.")
                ts_start = oldest_log

        query_params = {'func': func, 'item_id': item_id, 'ts_start': ts_start, 'ts_end': ts_end, 'group': group, 'group2': group2, 'ignore_value': ignore_value}
        result = _handle_query_result(self._query_log_timestamp(**query_params))

        if self.prepare_debug:
            self.logger.debug(f"_query_item: value for item={item.path()} with {timeframe=}, {func=}: {result}")

        return result

    def _init_cache_dicts(self) -> None:
        """
        init all cache dicts
        """

        self.logger.info(f"All cache_dicts will be initiated.")

        self.item_cache = {}

        self.current_values = {
            DAY: {},
            WEEK: {},
            MONTH: {},
            YEAR: {}
        }

        self.previous_values = {
            DAY: {},
            WEEK: {},
            MONTH: {},
            YEAR: {}
        }

    def _clear_queue(self) -> None:
        """
        Clear working queue
        """

        self.logger.info(f"Working queue will be cleared. Calculation run will end.")
        self.item_queue.queue.clear()

    def _work_item_queue_thread_startup(self):
        """
        Start a thread to work item queue
        """

        try:
            _name = 'plugins.' + self.get_fullname() + '.work_item_queue'
            self.work_item_queue_thread = threading.Thread(target=self.work_item_queue, name=_name)
            self.work_item_queue_thread.daemon = False
            self.work_item_queue_thread.start()
            self.logger.debug("Thread for 'work_item_queue_thread' has been started")
        except threading.ThreadError:
            self.logger.error("Unable to launch thread for 'work_item_queue_thread'.")
            self.work_item_queue_thread = None

    def _work_item_queue_thread_shutdown(self):
        """
        Shut down the thread to work item queue
        """

        if self.work_item_queue_thread:
            self.work_item_queue_thread.join()
            if self.work_item_queue_thread.is_alive():
                self.logger.error("Unable to shut down 'work_item_queue_thread' thread")
            else:
                self.logger.info("Thread 'work_item_queue_thread' has been terminated.")
                self.work_item_queue_thread = None

    ##############################
    #   Database Query Preparation
    ##############################

    def _query_log_timestamp(self, func: str, item_id: int, ts_start: int, ts_end: int, group: str = None, group2: str = None, ignore_value=None) -> Union[list, None]:
        """
        Assemble a mysql query str and param dict based on given parameters, get query response and return it

        :param func: function to be used at query
        :param item_id: database item_id for which the query should be done
        :param ts_start: start for query given in timestamp in microseconds
        :param ts_end: end for query given in timestamp in microseconds
        :param group: first grouping parameter (default = None, possible values: day, week, month, year)
        :param group2: second grouping parameter (default = None, possible values: day, week, month, year)
        :param ignore_value: value of val_num, which will be ignored during query

        :return: query response

        """

        # do debug log
        if self.prepare_debug:
            self.logger.debug(f"_query_log_timestamp: Called with {func=}, {item_id=}, {ts_start=}, {ts_end=}, {group=}, {group2=}, {ignore_value=}")

        # define query parts
        _select = {
            'avg':         'time, ROUND(AVG(val_num * duration) / AVG(duration), 1) as value ',
            'avg1':        'time, ROUND(AVG(value), 1) as value FROM (SELECT time, ROUND(AVG(val_num), 1) as value ',
            'min':         'time, ROUND(MIN(val_num), 1) as value ',
            'max':         'time, ROUND(MAX(val_num), 1) as value ',
            'max1':        'time, ROUND(MAX(value), 1) as value FROM (SELECT time, ROUND(MAX(val_num), 1) as value ',
            'sum':         'time, ROUND(SUM(val_num), 1) as value ',
            'on':          'time, ROUND(SUM(val_bool * duration) / SUM(duration), 1) as value ',
            'integrate':   'time, ROUND(SUM(val_num * duration),1) as value ',
            'sum_max':     'time, ROUND(SUM(value), 1) as value FROM (SELECT time, ROUND(MAX(val_num), 1) as value ',
            'sum_avg':     'time, ROUND(SUM(value), 1) as value FROM (SELECT time, ROUND(AVG(val_num * duration) / AVG(duration), 1) as value ',
            'sum_min_neg': 'time, ROUND(SUM(value), 1) as value FROM (SELECT time, IF(min(val_num) < 0, ROUND(MIN(val_num), 1), 0) as value ',
            'diff_max':    'time, value1 - LAG(value1) OVER (ORDER BY time) AS value FROM (SELECT time, ROUND(MAX(val_num), 1) as value1 ',
            'next':        'time, val_num as value ',
            'raw':         'time, val_num as value '
        }

        _table_alias = {
            'avg': '',
            'avg1': ') AS table1 ',
            'min': '',
            'max': '',
            'max1': ') AS table1 ',
            'sum': '',
            'on': '',
            'integrate': '',
            'sum_max': ') AS table1 ',
            'sum_avg': ') AS table1 ',
            'sum_min_neg': ') AS table1 ',
            'diff_max': ') AS table1 ',
            'next': '',
            'raw': '',
        }

        _order = "time DESC LIMIT 1 " if func == "next" else "time ASC "

        _where = "item_id = :item_id AND time < :ts_start" if func == "next" else "item_id = :item_id AND time BETWEEN :ts_start AND :ts_end "

        _db_table = 'log '

        _group_by_sql = {
            "year":  "GROUP BY YEAR(FROM_UNIXTIME(time/1000)) ",
            "month": "GROUP BY FROM_UNIXTIME((time/1000),'%Y%m') ",
            "week":  "GROUP BY YEARWEEK(FROM_UNIXTIME(time/1000), 5) ",
            "day":   "GROUP BY DATE(FROM_UNIXTIME(time/1000)) ",
            "hour":  "GROUP BY FROM_UNIXTIME((time/1000),'%Y%m%d%H') ",
            None: ''
        }

        _group_by_sqlite = {
            "year":  "GROUP BY strftime('%Y', date((time/1000),'unixepoch')) ",
            "month": "GROUP BY strftime('%Y%m', date((time/1000),'unixepoch')) ",
            "week":  "GROUP BY strftime('%Y%W', date((time/1000),'unixepoch')) ",
            "day":   "GROUP BY date((time/1000),'unixepoch') ",
            "hour":  "GROUP BY strftime('%Y%m%d%H', datetime((time/1000),'unixepoch')) ",
            None: ''
        }

        # select query parts depending in db driver
        if self.db_driver.lower() == 'pymysql':
            _group_by = _group_by_sql
        elif self.db_driver.lower() == 'sqlite3':
            _group_by = _group_by_sqlite
        else:
            self.logger.error('DB Driver unknown')
            return

        # check correctness of func
        if func not in _select:
            self.logger.error(f"_query_log_timestamp: Requested {func=} for {item_id=} not defined. Query cancelled.")
            return

        # check correctness of group and group2
        if group not in _group_by:
            self.logger.error(f"_query_log_timestamp: Requested {group=} for item={item_id=} not defined. Query cancelled.")
            return
        if group2 not in _group_by:
            self.logger.error(f"_query_log_timestamp: Requested {group2=} for item={item_id=} not defined. Query cancelled.")
            return

        # handle ignore values
        if func in ['min', 'max', 'max1', 'sum_max', 'sum_avg', 'sum_min_neg', 'diff_max']:  # extend _where statement for excluding boolean values == 0 for defined functions
            _where = f'{_where}AND val_bool = 1 '
        if ignore_value:  # if value to be ignored are defined, extend _where statement
            _where = f'{_where}AND val_num != {ignore_value} '

        # set params
        params = {'item_id': item_id, 'ts_start': ts_start}
        if func != "next":
            params.update({'ts_end': ts_end})

        # assemble query
        query = f"SELECT {_select[func]}FROM {_db_table}WHERE {_where}{_group_by[group]}ORDER BY {_order}{_table_alias[func]}{_group_by[group2]}".strip()

        if self.db_driver.lower() == 'sqlite3':
            query = query.replace('IF', 'IIF')

        # do debug log
        if self.prepare_debug:
            self.logger.debug(f"_query_log_timestamp: {query=}, {params=}")

        # request database and return result
        return self._fetchall(query, params)

    def _read_log_all(self, item_id: int):
        """
        Read the oldest log record for given item

        :param item_id: item_id to read the record for
        :return: Log record for item_id
        """

        if self.prepare_debug:
            self.logger.debug(f"_read_log_all: Called for {item_id=}")

        query = "SELECT * FROM log WHERE (item_id = :item_id) AND (time = None OR 1 = 1)"
        params = {'item_id': item_id}
        result = self._fetchall(query, params)
        return result

    def _read_log_oldest(self, item_id: int, cur=None) -> int:
        """
        Read the oldest log record for given database ID

        :param item_id: Database ID of item to read the record for
        :type item_id: int
        :param cur: A database cursor object if available (optional)

        :return: Log record for the database ID
        """

        params = {'item_id': item_id}
        query = "SELECT min(time) FROM log WHERE item_id = :item_id;"
        return self._fetchall(query, params, cur=cur)[0][0]

    def _read_log_timestamp(self, item_id: int, timestamp: int, cur=None) -> Union[list, None]:
        """
        Read database log record for given database ID

        :param item_id: Database ID of item to read the record for
        :type item_id: int
        :param timestamp: timestamp for the given value
        :type timestamp: int
        :param cur: A database cursor object if available (optional)

        :return: Log record for the database ID at given timestamp
        """

        params = {'item_id': item_id, 'timestamp': timestamp}
        query = "SELECT * FROM log WHERE item_id = :item_id AND time = :timestamp;"
        return self._fetchall(query, params, cur=cur)

    def _read_item_table(self, item_id: int = None, item_path: str = None):
        """
        Read item table

        :param item_id: unique ID for item within database
        :param item_path: item_path for Item within the database

        :return: Data for the selected item
        :rtype: tuple
        """

        columns_entries = ('id', 'name', 'time', 'val_str', 'val_num', 'val_bool', 'changed')
        columns = ", ".join(columns_entries)

        if item_id is None and item_path is None:
            return

        if item_id:
            query = f"SELECT {columns} FROM item WHERE id = {item_id}"
        else:
            query = f"SELECT {columns} FROM item WHERE name = '{item_path}'"

        return self._fetchone(query)

    def _get_db_version(self) -> str:
        """
        Query the database version and provide result
        """

        query = 'SELECT sqlite_version()' if self.db_driver.lower() == 'sqlite3' else 'SELECT VERSION()'
        return self._fetchone(query)[0]

    def _get_db_connect_timeout(self) -> list:
        """
        Query database timeout
        """

        query = "SHOW GLOBAL VARIABLES LIKE 'connect_timeout'"
        return self._fetchone(query)

    def _get_db_net_read_timeout(self) -> list:
        """
        Query database timeout net_read_timeout
        """

        query = "SHOW GLOBAL VARIABLES LIKE 'net_read_timeout'"
        return self._fetchone(query)

    ##############################
    #   Database Queries
    ##############################

    def _execute(self, query: str, params: dict = None, cur=None) -> list:
        if params is None:
            params = {}

        return self._query(self._db.execute, query, params, cur)

    def _fetchone(self, query: str, params: dict = None, cur=None) -> list:
        if params is None:
            params = {}

        return self._query(self._db.fetchone, query, params, cur)

    def _fetchall(self, query: str, params: dict = None, cur=None) -> list:
        if params is None:
            params = {}

        return self._query(self._db.fetchall, query, params, cur)

    def _query(self, fetch, query: str, params: dict = None, cur=None) -> Union[None, list]:
        if params is None:
            params = {}

        if self.sql_debug:
            self.logger.debug(f"_query: Called with {query=}, {params=}, {cur=}")

        if not self._initialize_db():
            return None

        if cur is None:
            if self._db.verify(5) == 0:
                self.logger.error("_query: Connection to database not recovered.")
                return None
            # if not self._db.lock(300):
            #    self.logger.error("_query: Can't query due to fail to acquire lock.")
            #     return None

        query_readable = re.sub(r':([a-z_]+)', r'{\1}', query).format(**params)

        try:
            tuples = fetch(query, params, cur=cur)
        except Exception as e:
            self.logger.error(f"_query: Error for query '{query_readable}': {e}")
        else:
            if self.sql_debug:
                self.logger.debug(f"_query: Result of '{query_readable}': {tuples}")
            return tuples
        # finally:
        #    if cur is None:
        #         self._db.release()


##############################
#   Helper functions
##############################


def params_to_dict(string: str) -> Union[dict, None]:
    """
    Parse a string with named arguments and comma separation to dict; (e.g. string = 'year=2022, month=12')
    """

    try:
        res_dict = dict((a.strip(), b.strip()) for a, b in (element.split('=') for element in string.split(', ')))
    except Exception:
        return None
    else:
        # convert to int and remove possible double quotes
        for key in res_dict:
            if isinstance(res_dict[key], str):
                res_dict[key] = res_dict[key].replace('"', '')
                res_dict[key] = res_dict[key].replace("'", "")
            if res_dict[key].isdigit():
                res_dict[key] = int(float(res_dict[key]))

        # check correctness if known key values (func=str, item, timeframe=str, start=int, end=int, count=int, group=str, group2=str, year=int, month=int):
        for key in res_dict:
            if key in ('func', 'timeframe', 'group', 'group2') and not isinstance(res_dict[key], str):
                return None
            elif key in ('start', 'end', 'count') and not isinstance(res_dict[key], int):
                return None
            elif key in 'year':
                if not valid_year(res_dict[key]):
                    return None
            elif key in 'month':
                if not valid_month(res_dict[key]):
                    return None
        return res_dict


def valid_year(year: Union[int, str]) -> bool:
    """
    Check if given year is digit and within allowed range
    """

    if ((isinstance(year, int) or (isinstance(year, str) and year.isdigit())) and (
            1980 <= int(year) <= datetime.date.today().year)) or (isinstance(year, str) and year == 'current'):
        return True
    else:
        return False


def valid_month(month: Union[int, str]) -> bool:
    """
    Check if given month is digit and within allowed range
    """

    if (isinstance(month, int) or (isinstance(month, str) and month.isdigit())) and (1 <= int(month) <= 12):
        return True
    else:
        return False


def timestamp_to_timestring(timestamp: int) -> str:
    """
    Parse timestamp from db query to string representing date and time
    """

    return datetime.datetime.utcfromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')


def convert_timeframe(timeframe: str) -> str:
    """
    Convert timeframe

    """

    convertion = {
        'tag': 'day',
        'heute': 'day',
        'woche': 'week',
        'monat': 'month',
        'jahr': 'year',
        'vorjahreszeitraum': 'day',
        'jahreszeitraum': 'day',
        'h': 'hour',
        'd': 'day',
        'w': 'week',
        'm': 'month',
        'y': 'year'
    }

    return convertion.get(timeframe)


def convert_duration(timeframe: str, window_dur: str) -> int:
    """
    Convert duration

    """

    _d_in_y = 365
    _d_in_w = 7
    _m_in_y = 12
    _w_in_y = _d_in_y / _d_in_w
    _w_in_m = _w_in_y / _m_in_y
    _d_in_m = _d_in_y / _m_in_y

    conversion = {
        'day': {'day': 1,
                'week': _d_in_w,
                'month': _d_in_m,
                'year': _d_in_y,
                },
        'week': {'day': 1 / _d_in_w,
                 'week': 1,
                 'month': _w_in_m,
                 'year': _w_in_y
                 },
        'month': {'day': 1 / _d_in_m,
                  'week': 1 / _w_in_m,
                  'month': 1,
                  'year': _m_in_y
                  },
        'year': {'day': 1 / _d_in_y,
                 'week': 1 / _w_in_y,
                 'month': 1 / _m_in_y,
                 'year': 1
                 }
    }

    return round(int(conversion[timeframe][window_dur]), 0)


def count_to_start(count: int = 0, end: int = 0):
    """
    Converts given count and end ot start and end
    """

    return end + count, end


def get_start_end_as_timestamp(timeframe: str, start: int, end: int) -> tuple:
    """
    Provides start and end as timestamp in microseconds from timeframe with start and end

    :param timeframe: timeframe as week, month, year
    :param start: beginning timeframe in x timeframes from now
    :param end: end of timeframe in x timeframes from now

    :return: start time in timestamp in microseconds, end time in timestamp in microseconds

    """

    return datetime_to_timestamp(get_start(timeframe, start)) * 1000, datetime_to_timestamp(get_end(timeframe, end)) * 1000


def get_start(timeframe: str, start: int) -> datetime:
    """
    Provides start as datetime

    :param timeframe: timeframe as week, month, year
    :param start: beginning timeframe in x timeframes from now

    """

    if start is None:
        start = 0

    if timeframe == 'week':
        _dt_start = week_beginning(start)
    elif timeframe == 'month':
        _dt_start = month_beginning(start)
    elif timeframe == 'year':
        _dt_start = year_beginning(start)
    else:
        _dt_start = day_beginning(start)

    return _dt_start


def get_end(timeframe: str, end: int) -> datetime:
    """
    Provides end as datetime

    :param timeframe: timeframe as week, month, year
    :param end: end of timeframe in x timeframes from now

    """

    if timeframe == 'week':
        _dt_end = week_end(end)
    elif timeframe == 'month':
        _dt_end = month_end(end)
    elif timeframe == 'year':
        _dt_end = year_end(end)
    else:
        _dt_end = day_end(end)

    return _dt_end


def year_beginning(delta: int = 0) -> datetime:
    """
    provides datetime of beginning of year of today minus x years
    """

    _dt = datetime.datetime.combine(datetime.date.today(), datetime.datetime.min.time())
    return _dt.replace(month=1, day=1) - relativedelta(years=delta)


def year_end(delta: int = 0) -> datetime:
    """
    provides datetime of end of year of today minus x years
    """

    return year_beginning(delta) + relativedelta(years=1)


def month_beginning(delta: int = 0) -> datetime:
    """
    provides datetime of beginning of month minus x month
    """

    _dt = datetime.datetime.combine(datetime.date.today(), datetime.datetime.min.time())
    return _dt.replace(day=1) - relativedelta(months=delta)


def month_end(delta: int = 0) -> datetime:
    """
    provides datetime of end of month minus x month
    """

    return month_beginning(delta) + relativedelta(months=1)


def week_beginning(delta: int = 0) -> datetime:
    """
    provides datetime of beginning of week minus x weeks
    """

    _dt = datetime.datetime.combine(datetime.date.today(), datetime.datetime.min.time())
    return _dt - relativedelta(days=(datetime.date.today().weekday() + (delta * 7)))


def week_end(delta: int = 0) -> datetime:
    """
    provides datetime of end of week minus x weeks
    """

    return week_beginning(delta) + relativedelta(days=6)


def day_beginning(delta: int = 0) -> datetime:
    """
    provides datetime of beginning of today minus x days
    """

    return datetime.datetime.combine(datetime.date.today(), datetime.datetime.min.time()) - relativedelta(days=delta)


def day_end(delta: int = 0) -> datetime:
    """
    provides datetime of end of today minus x days
    """

    return day_beginning(delta) + relativedelta(days=1)


def datetime_to_timestamp(dt: datetime) -> int:
    """
    Provides timestamp from given datetime
    """

    return int(dt.replace(tzinfo=datetime.timezone.utc).timestamp())


def to_int(arg) -> Union[int, None]:
    try:
        return int(arg)
    except (ValueError, TypeError):
        return None


ALLOWED_QUERY_TIMEFRAMES = ['year', 'month', 'week', 'day', 'hour']
ALLOWED_MINMAX_FUNCS = ['min', 'max', 'avg']
ALL_ONCHANGE_ATTRIBUTES = ['verbrauch_heute', 'verbrauch_woche', 'verbrauch_monat', 'verbrauch_jahr', 'minmax_heute_min', 'minmax_heute_max', 'minmax_woche_min', 'minmax_woche_max', 'minmax_monat_min', 'minmax_monat_max', 'minmax_jahr_min', 'minmax_jahr_max', 'tagesmitteltemperatur_heute']
ALL_DAILY_ATTRIBUTES = ['verbrauch_heute_minus1', 'verbrauch_heute_minus2', 'verbrauch_heute_minus3', 'verbrauch_heute_minus4', 'verbrauch_heute_minus5', 'verbrauch_heute_minus6', 'verbrauch_heute_minus7', 'verbrauch_rolling_12m_heute_minus1', 'verbrauch_jahreszeitraum_minus1', 'verbrauch_jahreszeitraum_minus2', 'verbrauch_jahreszeitraum_minus3', 'zaehlerstand_heute_minus1', 'zaehlerstand_heute_minus2', 'zaehlerstand_heute_minus3', 'minmax_last_24h_min', 'minmax_last_24h_max', 'minmax_last_24h_avg', 'minmax_last_7d_min', 'minmax_last_7d_max', 'minmax_last_7d_avg', 'minmax_heute_minus1_min', 'minmax_heute_minus1_max', 'minmax_heute_minus1_avg', 'minmax_heute_minus2_min', 'minmax_heute_minus2_max', 'minmax_heute_minus2_avg', 'minmax_heute_minus3_min', 'minmax_heute_minus3_max', 'minmax_heute_minus3_avg', 'tagesmitteltemperatur_heute_minus1', 'tagesmitteltemperatur_heute_minus2', 'tagesmitteltemperatur_heute_minus3', 'serie_minmax_tag_min_30d', 'serie_minmax_tag_max_30d', 'serie_minmax_tag_avg_30d', 'serie_verbrauch_tag_30d', 'serie_zaehlerstand_tag_30d', 'serie_tagesmittelwert_stunde_0d', 'serie_tagesmittelwert_tag_stunde_30d', 'kaeltesumme', 'waermesumme', 'gruenlandtempsumme', 'tagesmitteltemperatur', 'wachstumsgradtage']
ALL_WEEKLY_ATTRIBUTES = ['verbrauch_woche_minus1', 'verbrauch_woche_minus2', 'verbrauch_woche_minus3', 'verbrauch_woche_minus4', 'verbrauch_rolling_12m_woche_minus1', 'zaehlerstand_woche_minus1', 'zaehlerstand_woche_minus2', 'zaehlerstand_woche_minus3', 'minmax_woche_minus1_min', 'minmax_woche_minus1_max', 'minmax_woche_minus1_avg', 'minmax_woche_minus2_min', 'minmax_woche_minus2_max', 'minmax_woche_minus2_avg', 'serie_minmax_woche_min_30w', 'serie_minmax_woche_max_30w', 'serie_minmax_woche_avg_30w', 'serie_verbrauch_woche_30w', 'serie_zaehlerstand_woche_30w']
ALL_MONTHLY_ATTRIBUTES = ['verbrauch_monat_minus1', 'verbrauch_monat_minus2', 'verbrauch_monat_minus3', 'verbrauch_monat_minus4', 'verbrauch_monat_minus12', 'verbrauch_rolling_12m_monat_minus1', 'zaehlerstand_monat_minus1', 'zaehlerstand_monat_minus2', 'zaehlerstand_monat_minus3', 'minmax_monat_minus1_min', 'minmax_monat_minus1_max', 'minmax_monat_minus1_avg', 'minmax_monat_minus2_min', 'minmax_monat_minus2_max', 'minmax_monat_minus2_avg', 'serie_minmax_monat_min_15m', 'serie_minmax_monat_max_15m', 'serie_minmax_monat_avg_15m', 'serie_verbrauch_monat_18m', 'serie_zaehlerstand_monat_18m', 'serie_waermesumme_monat_24m', 'serie_kaeltesumme_monat_24m']
ALL_YEARLY_ATTRIBUTES = ['verbrauch_jahr_minus1', 'verbrauch_jahr_minus2', 'verbrauch_rolling_12m_jahr_minus1', 'zaehlerstand_jahr_minus1', 'zaehlerstand_jahr_minus2', 'zaehlerstand_jahr_minus3', 'minmax_jahr_minus1_min', 'minmax_jahr_minus1_max', 'minmax_jahr_minus1_avg']
ALL_NEED_PARAMS_ATTRIBUTES = ['kaeltesumme', 'waermesumme', 'gruenlandtempsumme', 'tagesmitteltemperatur', 'wachstumsgradtage', 'db_request']
ALL_VERBRAUCH_ATTRIBUTES = ['verbrauch_heute', 'verbrauch_woche', 'verbrauch_monat', 'verbrauch_jahr', 'verbrauch_heute_minus1', 'verbrauch_heute_minus2', 'verbrauch_heute_minus3', 'verbrauch_heute_minus4', 'verbrauch_heute_minus5', 'verbrauch_heute_minus6', 'verbrauch_heute_minus7', 'verbrauch_woche_minus1', 'verbrauch_woche_minus2', 'verbrauch_woche_minus3', 'verbrauch_woche_minus4', 'verbrauch_monat_minus1', 'verbrauch_monat_minus2', 'verbrauch_monat_minus3', 'verbrauch_monat_minus4', 'verbrauch_monat_minus12', 'verbrauch_jahr_minus1', 'verbrauch_jahr_minus2', 'verbrauch_rolling_12m_heute_minus1', 'verbrauch_rolling_12m_woche_minus1', 'verbrauch_rolling_12m_monat_minus1', 'verbrauch_rolling_12m_jahr_minus1', 'verbrauch_jahreszeitraum_minus1', 'verbrauch_jahreszeitraum_minus2', 'verbrauch_jahreszeitraum_minus3']
ALL_ZAEHLERSTAND_ATTRIBUTES = ['zaehlerstand_heute_minus1', 'zaehlerstand_heute_minus2', 'zaehlerstand_heute_minus3', 'zaehlerstand_woche_minus1', 'zaehlerstand_woche_minus2', 'zaehlerstand_woche_minus3', 'zaehlerstand_monat_minus1', 'zaehlerstand_monat_minus2', 'zaehlerstand_monat_minus3', 'zaehlerstand_jahr_minus1', 'zaehlerstand_jahr_minus2', 'zaehlerstand_jahr_minus3']
ALL_HISTORIE_ATTRIBUTES = ['minmax_last_24h_min', 'minmax_last_24h_max', 'minmax_last_24h_avg', 'minmax_last_7d_min', 'minmax_last_7d_max', 'minmax_last_7d_avg', 'minmax_heute_min', 'minmax_heute_max', 'minmax_heute_minus1_min', 'minmax_heute_minus1_max', 'minmax_heute_minus1_avg', 'minmax_heute_minus2_min', 'minmax_heute_minus2_max', 'minmax_heute_minus2_avg', 'minmax_heute_minus3_min', 'minmax_heute_minus3_max', 'minmax_heute_minus3_avg', 'minmax_woche_min', 'minmax_woche_max', 'minmax_woche_minus1_min', 'minmax_woche_minus1_max', 'minmax_woche_minus1_avg', 'minmax_woche_minus2_min', 'minmax_woche_minus2_max', 'minmax_woche_minus2_avg', 'minmax_monat_min', 'minmax_monat_max', 'minmax_monat_minus1_min', 'minmax_monat_minus1_max', 'minmax_monat_minus1_avg', 'minmax_monat_minus2_min', 'minmax_monat_minus2_max', 'minmax_monat_minus2_avg', 'minmax_jahr_min', 'minmax_jahr_max', 'minmax_jahr_minus1_min', 'minmax_jahr_minus1_max', 'minmax_jahr_minus1_avg']
ALL_TAGESMITTEL_ATTRIBUTES = ['tagesmitteltemperatur_heute', 'tagesmitteltemperatur_heute_minus1', 'tagesmitteltemperatur_heute_minus2', 'tagesmitteltemperatur_heute_minus3']
ALL_SERIE_ATTRIBUTES = ['serie_minmax_monat_min_15m', 'serie_minmax_monat_max_15m', 'serie_minmax_monat_avg_15m', 'serie_minmax_woche_min_30w', 'serie_minmax_woche_max_30w', 'serie_minmax_woche_avg_30w', 'serie_minmax_tag_min_30d', 'serie_minmax_tag_max_30d', 'serie_minmax_tag_avg_30d', 'serie_verbrauch_tag_30d', 'serie_verbrauch_woche_30w', 'serie_verbrauch_monat_18m', 'serie_zaehlerstand_tag_30d', 'serie_zaehlerstand_woche_30w', 'serie_zaehlerstand_monat_18m', 'serie_waermesumme_monat_24m', 'serie_kaeltesumme_monat_24m', 'serie_tagesmittelwert_stunde_0d', 'serie_tagesmittelwert_tag_stunde_30d']
ALL_GEN_ATTRIBUTES = ['general_oldest_value', 'general_oldest_log']
ALL_COMPLEX_ATTRIBUTES = ['kaeltesumme', 'waermesumme', 'gruenlandtempsumme', 'tagesmitteltemperatur', 'wachstumsgradtage', 'db_request']


"""
    'serie_minmax_monat_min_15m':           {'func': 'min',         'timeframe': 'month', 'start': 15,   'end': 0,    'group': 'month'},
    'serie_minmax_monat_max_15m':           {'func': 'max',         'timeframe': 'month', 'start': 15,   'end': 0,    'group': 'month'},
    'serie_minmax_monat_avg_15m':           {'func': 'avg',         'timeframe': 'month', 'start': 15,   'end': 0,    'group': 'month'},
    'serie_minmax_woche_min_30w':           {'func': 'min',         'timeframe': 'week',  'start': 30,   'end': 0,    'group': 'week'},
    'serie_minmax_woche_max_30w':           {'func': 'max',         'timeframe': 'week',  'start': 30,   'end': 0,    'group': 'week'},
    'serie_minmax_woche_avg_30w':           {'func': 'avg',         'timeframe': 'week',  'start': 30,   'end': 0,    'group': 'week'},
    'serie_minmax_tag_min_30d':             {'func': 'min',         'timeframe': 'day',   'start': 30,   'end': 0,    'group': 'day'},
    'serie_minmax_tag_max_30d':             {'func': 'max',         'timeframe': 'day',   'start': 30,   'end': 0,    'group': 'day'},
    'serie_minmax_tag_avg_30d':             {'func': 'avg',         'timeframe': 'day',   'start': 30,   'end': 0,    'group': 'day'},
    'serie_verbrauch_tag_30d':              {'func': 'diff_max',    'timeframe': 'day',   'start': 30,   'end': 0,    'group': 'day'},
    'serie_verbrauch_woche_30w':            {'func': 'diff_max',    'timeframe': 'week',  'start': 30,   'end': 0,    'group': 'week'},
    'serie_verbrauch_monat_18m':            {'func': 'diff_max',    'timeframe': 'month', 'start': 18,   'end': 0,    'group': 'month'},
    'serie_zaehlerstand_tag_30d':           {'func': 'max',         'timeframe': 'day',   'start': 30,   'end': 0,    'group': 'day'},
    'serie_zaehlerstand_woche_30w':         {'func': 'max',         'timeframe': 'week',  'start': 30,   'end': 0,    'group': 'week'},
    'serie_zaehlerstand_monat_18m':         {'func': 'max',         'timeframe': 'month', 'start': 18,   'end': 0,    'group': 'month'},
    'serie_waermesumme_monat_24m':          {'func': 'sum_max',     'timeframe': 'month', 'start': 24,   'end': 0,    'group': 'day',  'group2': 'month'},
    'serie_kaeltesumme_monat_24m':          {'func': 'sum_min_neg', 'timeframe': 'month', 'start': 24,   'end': 0,    'group': 'day',  'group2': 'month'},
    'serie_tagesmittelwert_0d':             {'func': 'max',         'timeframe': 'year',  'start': 0,    'end': 0,    'group': 'day'},
    'serie_tagesmittelwert_stunde_0d':      {'func': 'avg1',        'timeframe': 'day',   'start': 0,    'end': 0,    'group': 'hour', 'group2': 'day'},
    'serie_tagesmittelwert_stunde_30d':     {'func': 'avg1',        'timeframe': 'day',   'start': 30,   'end': 0,    'group': 'hour', 'group2': 'day'},
    'gts':                                  {'func': 'max',         'timeframe': 'year',  'start': None, 'end': None, 'group': 'day'},
"""
