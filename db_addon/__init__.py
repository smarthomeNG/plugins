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
from .item_attributes import *
import lib.db

DAY = 'day'
WEEK = 'week'
MONTH = 'month'
YEAR = 'year'


class DatabaseAddOn(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides the update functions for the items
    """

    PLUGIN_VERSION = '1.2.1'

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
        self.parse_debug = False                      # Enable / Disable debug logging for method 'parse item'
        self.execute_debug = False                    # Enable / Disable debug logging for method 'execute items'
        self.sql_debug = False                       # Enable / Disable debug logging for sql stuff
        self.ondemand_debug = False                   # Enable / Disable debug logging for method 'handle_ondemand'
        self.onchange_debug = False                  # Enable / Disable debug logging for method 'handle_onchange'
        self.prepare_debug = True                   # Enable / Disable debug logging for query preparation

        # define default mysql settings
        self.default_connect_timeout = 60
        self.default_net_read_timeout = 60

        # define variables from plugin parameters
        self.db_configname = self.get_parameter_value('database_plugin_config')
        self.startup_run_delay = self.get_parameter_value('startup_run_delay')
        self.ignore_0 = self.get_parameter_value('ignore_0')
        self.value_filter = self.get_parameter_value('value_filter')
        self.optimize_value_filter = self.get_parameter_value('optimize_value_filter')
        self.use_oldest_entry = self.get_parameter_value('use_oldest_entry')

        # init cache dicts
        self._init_cache_dicts()

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

        def get_query_parameters_from_db_addon_fct() -> Union[dict, None]:

            # get parameter
            db_addon_fct_vars = db_addon_fct.split('_')
            func = timeframe = timedelta = start = end = group = group2 = method = log_text = None
            required_params = None

            if db_addon_fct in HISTORIE_ATTRIBUTES_ONCHANGE:
                # handle functions 'minmax on-change' in format 'minmax_timeframe_func' items like 'minmax_heute_max', 'minmax_heute_min', 'minmax_woche_max', 'minmax_woche_min'
                timeframe = convert_timeframe(db_addon_fct_vars[1])
                func = db_addon_fct_vars[2] if db_addon_fct_vars[2] in ALLOWED_MINMAX_FUNCS else None
                start = end = 0
                log_text = 'minmax_timeframe_func'
                required_params = [func, timeframe, start, end]

            elif db_addon_fct in HISTORIE_ATTRIBUTES_LAST:
                # handle functions 'minmax_last' in format 'minmax_last_timedelta|timeframe_function' like 'minmax_last_24h_max'
                func = db_addon_fct_vars[3]
                timeframe = convert_timeframe(db_addon_fct_vars[2][-1:])
                start = to_int(db_addon_fct_vars[2][:-1])
                end = 0
                log_text = 'minmax_last_timedelta|timeframe_function'
                required_params = [func, timeframe, start, end]

            elif db_addon_fct in HISTORIE_ATTRIBUTES_TIMEFRAME:
                # handle functions 'min/max/avg' in format 'minmax_timeframe_timedelta_func' like 'minmax_heute_minus2_max'
                func = db_addon_fct_vars[3]  # min, max, avg
                timeframe = convert_timeframe(db_addon_fct_vars[1])  # day, week, month, year
                start = to_int(db_addon_fct_vars[2][-1])  # 1, 2, 3, ...
                end = start
                log_text = 'minmax_timeframe_timedelta_func'
                required_params = [func, timeframe, start, end]

            elif db_addon_fct in ZAEHLERSTAND_ATTRIBUTES_TIMEFRAME:
                # handle functions 'zaehlerstand' in format 'zaehlerstand_timeframe_timedelta' like 'zaehlerstand_heute_minus1'
                # func = 'max'
                timeframe = convert_timeframe(db_addon_fct_vars[1])
                start = to_int(db_addon_fct_vars[2][-1])
                end = start
                log_text = 'zaehlerstand_timeframe_timedelta'
                required_params = [timeframe, start, end]

            elif db_addon_fct in VERBRAUCH_ATTRIBUTES_ONCHANGE:
                # handle functions 'verbrauch on-change' items in format 'verbrauch_timeframe' like 'verbrauch_heute', 'verbrauch_woche', 'verbrauch_monat', 'verbrauch_jahr'
                timeframe = convert_timeframe(db_addon_fct_vars[1])
                start = end = 0
                log_text = 'verbrauch_timeframe'
                required_params = [timeframe, start, end]

            elif db_addon_fct in VERBRAUCH_ATTRIBUTES_TIMEFRAME:
                # handle functions 'verbrauch on-demand' in format 'verbrauch_timeframe_timedelta' like 'verbrauch_heute_minus2'
                timeframe = convert_timeframe(db_addon_fct_vars[1])
                start = to_int(db_addon_fct_vars[2][-1]) + 1
                end = to_int(db_addon_fct_vars[2][-1])
                log_text = 'verbrauch_timeframe_timedelta'
                required_params = [timeframe, start, end]

            elif db_addon_fct in VERBRAUCH_ATTRIBUTES_ROLLING:
                # handle functions 'verbrauch_on-demand' in format 'verbrauch_rolling_window_timeframe_timedelta' like 'verbrauch_rolling_12m_woche_minus1'
                func = db_addon_fct_vars[1]
                window_inc = to_int(db_addon_fct_vars[2][:-1])  # 12
                window_dur = convert_timeframe(db_addon_fct_vars[2][-1])  # day, week, month, year
                timeframe = convert_timeframe(db_addon_fct_vars[3])  # day, week, month, year
                if window_dur in ALLOWED_QUERY_TIMEFRAMES and window_inc and timeframe:
                    start = convert_duration(timeframe, window_dur) * window_inc
                end = to_int(db_addon_fct_vars[4][-1])  # 1
                log_text = 'verbrauch_rolling_window_timeframe_timedelta'
                required_params = [func, timeframe, start, end]

            elif db_addon_fct in VERBRAUCH_ATTRIBUTES_JAHRESZEITRAUM:
                # handle functions of format 'verbrauch_jahreszeitraum_timedelta' like 'verbrauch_jahreszeitraum_minus1'
                timeframe = convert_timeframe(db_addon_fct_vars[1])  # day, week, month, year
                timedelta = to_int(db_addon_fct_vars[2][-1])  # 1 oder 2 oder 3
                log_text = 'verbrauch_jahreszeitraum_timedelta'
                required_params = [timeframe, timedelta]

            elif db_addon_fct in TAGESMITTEL_ATTRIBUTES_ONCHANGE:
                # handle functions 'tagesmitteltemperatur on-change' items in format 'tagesmitteltemperatur_timeframe' like 'tagesmitteltemperatur_heute', 'tagesmitteltemperatur_woche', 'tagesmitteltemperatur_monat', 'tagesmitteltemperatur_jahr'
                timeframe = convert_timeframe(db_addon_fct_vars[1])
                func = 'max'
                start = end = 0
                log_text = 'tagesmitteltemperatur_timeframe'
                required_params = [timeframe, start, end]

            elif db_addon_fct in TAGESMITTEL_ATTRIBUTES_TIMEFRAME:
                # handle 'tagesmitteltemperatur_timeframe_timedelta' like 'tagesmitteltemperatur_heute_minus1'
                func = 'max'
                timeframe = convert_timeframe(db_addon_fct_vars[1])
                start = to_int(db_addon_fct_vars[2][-1])
                end = start
                log_text = 'tagesmitteltemperatur_timeframe_timedelta'
                required_params = [func, timeframe, start, end]

            elif db_addon_fct in SERIE_ATTRIBUTES_MINMAX:
                # handle functions 'serie_minmax' in format 'serie_minmax_timeframe_func_start|group' like 'serie_minmax_monat_min_15m'
                func = db_addon_fct_vars[3]
                timeframe = convert_timeframe(db_addon_fct_vars[2])
                start = to_int(db_addon_fct_vars[4][:-1])
                end = 0
                group = convert_timeframe(db_addon_fct_vars[4][len(db_addon_fct_vars[4]) - 1])
                log_text = 'serie_minmax_timeframe_func_start|group'
                required_params = [func, timeframe, start, end, group]

            elif db_addon_fct in SERIE_ATTRIBUTES_ZAEHLERSTAND:
                # handle functions 'serie_zaehlerstand' in format 'serie_zaehlerstand_timeframe_start|group' like 'serie_zaehlerstand_tag_30d'
                func = 'max'
                timeframe = convert_timeframe(db_addon_fct_vars[2])
                start = to_int(db_addon_fct_vars[3][:-1])
                group = convert_timeframe(db_addon_fct_vars[3][len(db_addon_fct_vars[3]) - 1])
                log_text = 'serie_zaehlerstand_timeframe_start|group'
                required_params = [timeframe, start, group]

            elif db_addon_fct in SERIE_ATTRIBUTES_VERBRAUCH:
                # handle all functions of format 'serie_verbrauch_timeframe_start|group' like 'serie_verbrauch_tag_30d'
                func = 'diff_max'
                timeframe = convert_timeframe(db_addon_fct_vars[2])
                start = to_int(db_addon_fct_vars[3][:-1])
                group = convert_timeframe(db_addon_fct_vars[3][len(db_addon_fct_vars[3]) - 1])
                log_text = 'serie_verbrauch_timeframe_start|group'
                required_params = [timeframe, start, group]

            elif db_addon_fct in SERIE_ATTRIBUTES_SUMME:
                # handle all summe in format 'serie_xxsumme_timeframe_count|group' like serie_waermesumme_monat_24m
                func = 'sum_max'
                timeframe = 'month'
                start = to_int(db_addon_fct_vars[3][:-1])
                end = 0
                group = 'day',
                group2 = 'month'
                log_text = 'serie_xxsumme_timeframe_count|group'
                required_params = [func, timeframe, start, end, group, group2]

            elif db_addon_fct in SERIE_ATTRIBUTES_MITTEL_D:
                # handle 'serie_tagesmittelwert_count|group' like 'serie_tagesmittelwert_0d' => Tagesmittelwert der letzten 0 Tage (also heute)
                func = 'max'
                timeframe = 'year'
                start = to_int(db_addon_fct_vars[2][:-1])
                end = 0
                group = convert_timeframe(db_addon_fct_vars[2][len(db_addon_fct_vars[2]) - 1])
                log_text = 'serie_tagesmittelwert_count|group'
                required_params = [func, timeframe, start, end, group]

            elif db_addon_fct in SERIE_ATTRIBUTES_MITTEL_H:
                # handle 'serie_tagesmittelwert_group2_count|group' like 'serie_tagesmittelwert_stunde_0d' => Stundenmittelwerte der letzten 0 Tage (also heute)
                func = 'avg1'
                timeframe = 'day'
                start = to_int(db_addon_fct_vars[3][:-1])
                end = 0
                group = 'hour'
                group2 = convert_timeframe(db_addon_fct_vars[3][len(db_addon_fct_vars[3]) - 1])
                log_text = 'serie_tagesmittelwert_group2_count|group'
                required_params = [func, timeframe, start, end, group, group2]

            elif db_addon_fct in SERIE_ATTRIBUTES_MITTEL_H1:
                # handle 'serie_tagesmittelwert_stunde_start_end|group' like 'serie_tagesmittelwert_stunde_30_0d' => Stundenmittelwerte von vor 30 Tage bis vor 0 Tagen (also heute)
                timeframe = 'day'
                method = 'raw'
                start = to_int(db_addon_fct_vars[3])
                end = to_int(db_addon_fct_vars[4][:-1])
                log_text = 'serie_tagesmittelwert_stunde_start_end|group'
                required_params = [timeframe, method, start, end]

            elif db_addon_fct in SERIE_ATTRIBUTES_MITTEL_D_H:
                # handle 'serie_tagesmittelwert_tag_stunde_end|group' like 'serie_tagesmittelwert_tag_stunde_30d' => Tagesmittelwert auf Basis des Mittelwerts pro Stunden für die letzten 30 Tage
                timeframe = 'day'
                method = 'raw'
                start = to_int(db_addon_fct_vars[4][:-1])
                end = 0
                log_text = 'serie_tagesmittelwert_tag_stunde_end|group'
                required_params = [timeframe, method, start, end]

            elif db_addon_fct in ALL_GEN_ATTRIBUTES:
                log_text = 'all_gen_attributes'
                required_params = []

            if required_params is None:
                self.logger.warning(f"ERROR: For calculating '{db_addon_fct}' at Item '{item.path()}' no mandatory parameters given.")
                return

            if required_params and None in required_params:
                self.logger.warning(f"ERROR: For calculating '{db_addon_fct}' at Item '{item.path()}' not all mandatory parameters given. Definitions are: {func=}, {timeframe=}, {timedelta=}, {start=}, {end=}, {group=}, {group2=}, {method=}")
                return

            # create dict and reduce dict to keys with value != None
            param_dict = {'func': func, 'timeframe': timeframe, 'timedelta': timedelta, 'start': start, 'end': end, 'group': group, 'group2': group2, 'method': method}

            # return reduced dict w keys with value != None
            return {k: v for k, v in param_dict.items() if v is not None}

        def get_query_parameters_from_db_addon_params() -> Union[dict, None]:
            """get query parameters from item attribute db_addon_params"""

            db_addon_params = params_to_dict(self.get_iattr_value(item.conf, 'db_addon_params'))

            if not db_addon_params:
                db_addon_params = self.get_iattr_value(item.conf, 'db_addon_params_dict')

            new_db_addon_params = {}
            possible_params = required_params = []

            if db_addon_params is None:
                self.logger.warning(f"ERROR: Definition for Item '{item.path()}' with db_addon_fct={db_addon_fct} incomplete, since parameters via 'db_addon_params' not given. Item will be ignored.")
                return

            # create item config for all functions with 'summe' like waermesumme, kaeltesumme, gruenlandtemperatursumme
            if 'summe' in db_addon_fct:
                possible_params = ['year', 'month']

            # create item config for wachstumsgradtage function
            elif db_addon_fct == 'wachstumsgradtage':
                possible_params = ['year', 'method', 'threshold']

            # create item config for tagesmitteltemperatur
            elif db_addon_fct == 'tagesmitteltemperatur':
                possible_params = ['timeframe', 'count']

            # create item config for minmax
            elif db_addon_fct == 'minmax':
                required_params = ['func', 'timeframe', 'start']

            # create item config for minmax_last
            elif db_addon_fct == 'minmax_last':
                required_params = ['func', 'timeframe', 'start', 'end']

            # create item config for verbrauch
            elif db_addon_fct == 'verbrauch':
                required_params = ['timeframe', 'start', 'end']

            # create item config for zaehlerstand
            elif db_addon_fct == 'zaehlerstand':
                required_params = ['timeframe', 'start']

            # create item config for db_request and everything else (get_query_parameters_from_db_addon_fct)
            else:
                required_params = ['func', 'timeframe']
                possible_params = ['start', 'end', 'group', 'group2', 'ignore_value_list', 'use_oldest_entry']

            if required_params and not any(param in db_addon_params for param in required_params):
                self.logger.warning(f"ERROR: Item '{item.path()}' with {db_addon_fct=} ignored, since not all mandatory parameters in {db_addon_params=} are given. Item will be ignored.")
                return

            # reduce dict to possible keys + required_params
            for key in possible_params + required_params:
                value = db_addon_params.get(key)
                if value:
                    new_db_addon_params[key] = value

            if new_db_addon_params:
                return new_db_addon_params

        def get_database_item_path() -> tuple:
            """
            Returns item_path from shNG config which is an item with database attribut valid for current db_addon item
            """

            _lookup_item = item

            for i in range(3):
                if self.has_iattr(_lookup_item.conf, 'db_addon_database_item'):
                    if self.parse_debug:
                        self.logger.debug(f"Attribut 'db_addon_database_item' for item='{item.path()}' has been found {i + 1} level above item at '{_lookup_item.path()}'.")
                    _database_item_path = self.get_iattr_value(_lookup_item.conf, 'db_addon_database_item')
                    _startup = bool(self.get_iattr_value(_lookup_item.conf, 'db_addon_startup'))
                    return _database_item_path, _startup
                else:
                    _lookup_item = _lookup_item.return_parent()

            return None, None

        def get_database_item() -> Item:
            """
            Returns item from shNG config which is an item with database attribut valid for current db_addon item
            """

            _lookup_item = item.return_parent()

            for i in range(2):
                if self.has_iattr(_lookup_item.conf, self.item_attribute_search_str):
                    if self.parse_debug:
                        self.logger.debug(f"Attribut '{self.item_attribute_search_str}' for item='{item.path()}'  has been found {i + 1} level above item at '{_lookup_item.path()}'.")
                    return _lookup_item
                else:
                    _lookup_item = _lookup_item.return_parent()

            return None, None

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
                    return True
            return False

        def format_db_addon_ignore_value_list(optimize: bool = self.optimize_value_filter):
            """ Check of list of comparison operators is formally valid """

            max_values = {'!=': [], '>=': [], '<=': [], '>': [], '<': []}
            db_addon_ignore_value_list_formatted = []

            for _entry in db_addon_ignore_value_list:
                _entry = _entry.strip()
                for op in max_values.keys():
                    if op in _entry:
                        var = _entry.split(op, 1)
                        value = var[1].strip()
                        value = to_int_float(value)
                        if value is None:
                            continue
                        db_addon_ignore_value_list_formatted.append(f"{op} {value}")
                        max_values[op].append(value)

            if self.parse_debug:
                self.logger.debug(f"Summarized 'ignore_value_list' for item {item.path()}: {db_addon_ignore_value_list_formatted}")

            if not db_addon_ignore_value_list_formatted:
                return

            if not optimize:
                return db_addon_ignore_value_list_formatted

            if self.parse_debug:
                self.logger.debug(f"Optimizing 'ignore_value_list' for item {item.path()} active.")

            # find low
            lower_value_list = max_values['<'] + max_values['<=']
            if lower_value_list:
                max_lower_value = max(lower_value_list)
                lower_op = '<' if max_lower_value in max_values['<'] else '<='
                lower_end = (lower_op, max_lower_value)
            else:
                lower_end = (None, None)
            # find high
            upper_value_list = max_values['>'] + max_values['>=']
            if upper_value_list:
                min_upper_value = min(upper_value_list)
                upper_op = '>' if min_upper_value in max_values['>'] else '>='
                upper_end = (upper_op, min_upper_value)
            else:
                upper_end = (None, None)

            # generate comp_list
            db_addon_ignore_value_list_optimized = []
            if lower_end[0]:
                db_addon_ignore_value_list_optimized.append(f"{lower_end[0]} {lower_end[1]}")
            if upper_end[0]:
                db_addon_ignore_value_list_optimized.append(f"{upper_end[0]} {upper_end[1]}")
            if max_values['!=']:
                for v in max_values['!=']:
                    if (not lower_end[0] or (lower_end[0] and v >= lower_end[1])) or (not upper_end[0] or (upper_end[0] and v <= upper_end[1])):
                        db_addon_ignore_value_list_optimized.append(f'!= {v}')

            if self.parse_debug:
                self.logger.debug(f"Optimized 'ignore_value_list' for item {item.path()}: {db_addon_ignore_value_list_optimized}")

            return db_addon_ignore_value_list_optimized

        # handle all items with db_addon_fct
        if self.has_iattr(item.conf, 'db_addon_fct'):

            if self.parse_debug:
                self.logger.debug(f"parse item: {item.path()} due to 'db_addon_fct'")

            # get db_addon_fct attribute value
            db_addon_fct = self.get_iattr_value(item.conf, 'db_addon_fct').lower()

            # get query parameters from db_addon_fct or db_addon_params
            if db_addon_fct in ALL_NEED_PARAMS_ATTRIBUTES:
                query_params = get_query_parameters_from_db_addon_params()
            else:
                query_params = get_query_parameters_from_db_addon_fct()
            if not query_params:
                return

            # get database item (and attribute value if item should be calculated at plugin startup) and return if not available
            database_item, db_addon_startup = get_database_item_path()
            if database_item is None:
                database_item = get_database_item()
                db_addon_startup = bool(self.get_iattr_value(item.conf, 'db_addon_startup'))
            if database_item is None:
                self.logger.warning(f"No database item found for {item.path()}: Item ignored. Maybe you should check instance of database plugin.")
                return

            # get/create list of comparison operators and check it
            db_addon_ignore_value_list = self.get_iattr_value(item.conf, 'db_addon_ignore_value_list')  # ['> 0', '< 35']
            db_addon_ignore_value = self.get_iattr_value(item.conf, 'db_addon_ignore_value')   # num

            if not db_addon_ignore_value_list:
                db_addon_ignore_value_list = []

            if db_addon_ignore_value:
                db_addon_ignore_value_list.append(f"!= {db_addon_ignore_value}")

            if any(x in str(item.path()) for x in self.ignore_0):
                db_addon_ignore_value_list.append("!= 0")

            if self.value_filter:
                for entry in list(self.value_filter.keys()):
                    if entry in str(item.path()):
                        db_addon_ignore_value_list.extend(self.value_filter[entry])

            if db_addon_ignore_value_list:
                db_addon_ignore_value_list_final = format_db_addon_ignore_value_list()
                if self.parse_debug:
                    self.logger.debug(f"{db_addon_ignore_value_list_final=}")
                query_params.update({'ignore_value_list': db_addon_ignore_value_list_final})

            # create standard items config
            item_config_data_dict = {'db_addon': 'function', 'db_addon_fct': db_addon_fct, 'database_item': database_item, 'query_params': query_params}
            if isinstance(database_item, str):
                item_config_data_dict.update({'database_item_path': True})
            else:
                database_item = database_item.path()

            # do logging
            if self.parse_debug:
                self.logger.debug(f"Item '{item.path()}' added with db_addon_fct={db_addon_fct} and database_item={database_item}")

            # add cycle for item groups
            if db_addon_fct in ALL_DAILY_ATTRIBUTES:
                item_config_data_dict.update({'cycle': 'daily'})
            elif db_addon_fct in ALL_WEEKLY_ATTRIBUTES:
                item_config_data_dict.update({'cycle': 'weekly'})
            elif db_addon_fct in ALL_MONTHLY_ATTRIBUTES:
                item_config_data_dict.update({'cycle': 'monthly'})
            elif db_addon_fct in ALL_YEARLY_ATTRIBUTES:
                item_config_data_dict.update({'cycle': 'yearly'})
            elif db_addon_fct in ALL_GEN_ATTRIBUTES:
                item_config_data_dict.update({'cycle': 'static'})
            elif db_addon_fct in ALL_ONCHANGE_ATTRIBUTES:
                item_config_data_dict.update({'cycle': 'on-change'})
            elif db_addon_fct == 'db_request':
                cycle = item_config_data_dict['query_params'].get('group')
                if not cycle:
                    cycle = item_config_data_dict['query_params'].get('timeframe')
                item_config_data_dict.update({'cycle': f"{timeframe_to_updatecyle(cycle)}"})
            elif db_addon_fct == 'minmax':
                cycle = item_config_data_dict['query_params']['timeframe']
                item_config_data_dict.update({'cycle': f"{timeframe_to_updatecyle(cycle)}"})

            # do logging
            if self.parse_debug:
                self.logger.debug(f"Item '{item.path()}' added to be run {item_config_data_dict['cycle']}.")

            # create item config for item to be run on startup
            if db_addon_startup or db_addon_fct in ALL_GEN_ATTRIBUTES:
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
            if self.parse_debug:
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

        if self.suspended:
            self.logger.info(f"Plugin is suspended. No items will be calculated.")
            return

        relevant_item_list = self._startup_items()
        self.logger.info(f"{len(relevant_item_list)} items will be calculated at startup.")

        for item in relevant_item_list:
            self.item_queue.put(item)

        self.startup_finished = True

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
                # self.logger.info(f"     Queue Entry: '{queue_entry}' received.")
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

        # get parameters
        item_config = self.get_item_config(item)
        if self.ondemand_debug:
            self.logger.debug(f"Item={item.path()} with {item_config=}")
        db_addon_fct = item_config['db_addon_fct']
        database_item = item_config['database_item']
        query_params = item_config.get('query_params')
        if query_params:
            params = dict(query_params)
            params.update({'database_item': database_item})
        else:
            params = {}

        if self.ondemand_debug:
            self.logger.debug(f"{db_addon_fct=} will _query_item with {params=}.")

        # handle item starting with 'verbrauch_'
        if db_addon_fct in ALL_VERBRAUCH_ATTRIBUTES:
            result = self._handle_verbrauch(params)

            if result and result < 0:
                self.logger.warning(f"Result of item {item.path()} with {db_addon_fct=} was negative. Something seems to be wrong.")

        # handle item starting with 'zaehlerstand_'
        elif db_addon_fct in ALL_ZAEHLERSTAND_ATTRIBUTES:
            result = self._handle_zaehlerstand(params)

        # handle 'serie_zaehlerstand'
        elif db_addon_fct in SERIE_ATTRIBUTES_ZAEHLERSTAND:
            result = self._handle_zaehlerstand_serie(params)

        # handle 'serie_verbrauch'
        elif db_addon_fct in SERIE_ATTRIBUTES_VERBRAUCH:
            result = self._handle_verbrauch_serie(params)

        # handle 'serie_tagesmittelwert_stunde_30_0d' and 'serie_tagesmittelwert_tag_stunde_30d'
        elif db_addon_fct in SERIE_ATTRIBUTES_MITTEL_H1 + SERIE_ATTRIBUTES_MITTEL_D_H:
            result = self._prepare_temperature_list(**params)

        # handle info functions
        elif db_addon_fct == 'info_db_version':
            result = self._get_db_version()

        # handle general functions
        elif db_addon_fct == 'general_oldest_value':
            result = self._get_oldest_value(database_item)

        # handle oldest_log
        elif db_addon_fct == 'general_oldest_log':
            result = self._get_oldest_log(database_item)

        # handle kaeltesumme
        elif db_addon_fct == 'kaeltesumme':
            result = self._handle_kaeltesumme(database_item=database_item, year=params.get('year'), month=params.get('month'))

        # handle waermesumme
        elif db_addon_fct == 'waermesumme':
            result = self._handle_waermesumme(database_item=database_item, year=params.get('year'), month=params.get('month'))

        # handle gruenlandtempsumme
        elif db_addon_fct == 'gruenlandtempsumme':
            result = self._handle_gruenlandtemperatursumme(database_item=database_item, year=params.get('year'))

        # handle wachstumsgradtage
        elif db_addon_fct == 'wachstumsgradtage':
            result = self._handle_wachstumsgradtage(database_item=database_item, year=params.get('year'))

        else:
            result = self._query_item(**params)[0][1]

        # log result
        if self.ondemand_debug:
            self.logger.debug(f"result is {result} for item '{item.path()}' with '{db_addon_fct=}'")

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

        def handle_minmax():
            cache_dict = self.current_values[timeframe]
            init = False

            if self.onchange_debug:
                self.logger.debug(f"'minmax' Item={updated_item.path()} with {func=} and {timeframe=} detected. Check for update of cache_dicts {cache_dict=} and item value.")

            # make sure, that database item is in cache dict
            if database_item not in cache_dict:
                cache_dict[database_item] = {}

            # get _recent_value; if not already cached, create cache
            cached_value = cache_dict[database_item].get(func)
            if cached_value is None:
                if self.onchange_debug:
                    self.logger.debug(f"Item={updated_item.path()} with {func=} and {timeframe=} not in cache dict. Query database.")

                query_params = {'func': func, 'database_item': database_item, 'timeframe': timeframe, 'start': 0, 'end': 0, 'ignore_value_list': ignore_value_list, 'use_oldest_entry': True}
                cached_value = self._query_item(**query_params)[0][1]

                if cached_value is None:
                    if self.onchange_debug:
                        self.logger.debug(f"no values available:{cached_value=}, {value}. Abort...")
                    return

                init = True

            # if value not given -> read
            if init:
                if self.onchange_debug:
                    self.logger.debug(f"initial {func} value for {timeframe=} of Item={item.path()} with will be set to {cached_value}")
                cache_dict[database_item][func] = cached_value
                return cached_value

            # check value for update of cache dict min
            elif func == 'min' and value < cached_value:
                if self.onchange_debug:
                    self.logger.debug(f"new value={value} lower then current min_value={cached_value} for {timeframe=}. cache_dict will be updated")
                cache_dict[database_item][func] = value
                return value

            # check value for update of cache dict max
            elif func == 'max' and value > cached_value:
                if self.onchange_debug:
                    self.logger.debug(f"new value={value} higher then current max_value={cached_value} for {timeframe=}. cache_dict will be updated")
                cache_dict[database_item][func] = value
                return value

            # no impact
            if self.onchange_debug:
                self.logger.debug(f"new value={value} will not change max/min for period={timeframe}.")
            return None

        def handle_verbrauch():
            cache_dict = self.previous_values[timeframe]

            if self.onchange_debug:
                self.logger.debug(f"'verbrauch' item {updated_item.path()} with {func=} and {value=} detected. Check for update of cache_dicts {cache_dict=} and item value.")

            # get _cached_value for value at end of last period; if not already cached, create cache
            cached_value = cache_dict.get(database_item)
            if cached_value is None:
                if self.onchange_debug:
                    self.logger.debug(f"Item={updated_item.path()} with _func={func} and timeframe={timeframe} not in cache dict.")

                # try to get most recent value of last timeframe, assuming that this is the value at end of last timeframe
                query_params = {'database_item': database_item, 'timeframe': timeframe, 'start': 1, 'end': 1, 'ignore_value_list': ignore_value_list, 'use_oldest_entry': True}
                cached_value = self._handle_zaehlerstand(query_params)

                if cached_value is None:
                    self.logger.info(f"Most recent value for last {timeframe} not available in database. Abort calculation.")
                    return

                cache_dict[database_item] = cached_value
                if self.onchange_debug:
                    self.logger.debug(f"Value for Item={updated_item.path()} at end of last {timeframe} not in cache dict. Value={cached_value} has been added.")

            # calculate value, set item value, put data into plugin_item_dict
            _new_value = value - cached_value
            return _new_value if isinstance(_new_value, int) else round(_new_value, 1)

        def handle_tagesmitteltemp():
            self.logger.info(f"Onchange handling of 'tagesmitteltemperatur' not implemented, yet.")
            # ToDo: Implement tagesmitteltemperatur onchange
            return

        if self.onchange_debug:
            self.logger.debug(f"called with updated_item={updated_item.path()} and value={value}.")

        relevant_item_list = set(self.get_item_list('database_item', updated_item)) & set(self.get_item_list('cycle', 'on-change'))

        if self.onchange_debug:
            self.logger.debug(f"Following items where identified for update: {relevant_item_list}.")

        for item in relevant_item_list:
            item_config = self.get_item_config(item)
            self.logger.debug(f"handle_onchange: Item={item.path()} with {item_config=}")
            db_addon_fct = item_config['db_addon_fct']
            database_item = item_config['database_item']
            timeframe = item_config['query_params']['timeframe']
            func = item_config['query_params'].get('func')
            ignore_value_list = item_config['query_params'].get('ignore_value_list')
            new_value = None

            # handle all on_change functions
            if db_addon_fct not in ALL_ONCHANGE_ATTRIBUTES:
                if self.onchange_debug:
                    self.logger.debug(f"non on-change function detected. Skip update.")
                continue

            # handle minmax on-change items like minmax_heute_max, minmax_heute_min, minmax_woche_max, minmax_woche_min.....
            if db_addon_fct.startswith('minmax'):
                new_value = handle_minmax()

            # handle verbrauch on-change items ending with heute, woche, monat, jahr
            elif db_addon_fct.startswith('verbrauch'):
                new_value = handle_verbrauch()

            # handle tagesmitteltemperatur on-change items ending with heute, woche, monat, jahr
            elif db_addon_fct.startswith('tagesmitteltemperatur'):
                new_value = handle_tagesmitteltemp()

            if new_value is None:
                continue

            self.logger.info(f"  Item value for '{item.path()}' with func={func} will be set to {new_value}")
            item_config = self.get_item_config(item)
            item_config.update({'value': new_value})
            item(new_value, self.get_shortname())

    def _update_database_items(self) -> None:
        for item in self._database_item_path_items():
            item_config = self.get_item_config(item)
            database_item_path = item_config.get('database_item')
            database_item = self.items.return_item(database_item_path)

            if database_item is None:
                self.logger.warning(f"Database-Item for Item with config item path for Database-Item {database_item_path!r} not found. Item '{item.path()}' will be removed from plugin.")
                self.remove_item(item)
            else:
                item_config.update({'database_item': database_item})
                db_addon_startup = bool(self.get_iattr_value(database_item.conf, 'db_addon_startup'))
                if db_addon_startup:
                    item_config.update({'startup': True})

    @property
    def log_level(self):
        return self.logger.getEffectiveLevel()

    def queue_backlog(self) -> int:
        return self.item_queue.qsize()

    def db_version(self) -> str:
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

    #########################################
    #   Public functions / Using item_path
    #########################################

    def gruenlandtemperatursumme(self, item_path: str, year: Union[int, str] = None) -> Union[int, None]:
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

    def waermesumme(self, item_path: str, year: Union[int, str] = None, month: Union[int, str] = None, threshold: int = 0) -> Union[int, None]:
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

    def kaeltesumme(self, item_path: str, year: Union[int, str] = None, month: Union[int, str] = None) -> Union[int, None]:
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
        :param timeframe: time increment for determination
        :param count: number of time increments starting from now to the left (into the past)
        :return: tagesmitteltemperatur
        """

        if not timeframe:
            timeframe = 'day'

        if not count:
            count = 0

        item = self.items.return_item(item_path)
        if item:
            count = to_int(count)
            start, end = count_to_start(count)
            query_params = {'database_item': item, 'func': 'max', 'timeframe': convert_timeframe(timeframe), 'start': start, 'end': end}
            return self._handle_tagesmitteltemperatur(**query_params)

    def wachstumsgradtage(self, item_path: str, year: Union[int, str] = None, method: int = 0, threshold: int = 10) -> Union[int, None]:
        """
        Query database for wachstumsgradtage
        https://de.wikipedia.org/wiki/Wachstumsgradtag

        :param item_path: item object or item_id for which the query should be done
        :param year: year the wachstumsgradtage should be calculated for
        :param method: method to be used
        :param threshold: Temperature in °C as threshold: Ein Tage mit einer Tagesdurchschnittstemperatur oberhalb des Schwellenwertes gilt als Wachstumsgradtag
        :return: wachstumsgradtage
        """

        item = self.items.return_item(item_path)
        if item:
            return self._handle_wachstumsgradtage(database_item=item, year=year, method=method, threshold=threshold)

    def temperaturserie(self, item_path: str, year: Union[int, str] = None, method: str = 'raw') -> Union[list, None]:
        """
        Query database for wachstumsgradtage
        https://de.wikipedia.org/wiki/Wachstumsgradtag

        :param item_path: item object or item_id for which the query should be done
        :param year: year the wachstumsgradtage should be calculated for
        :param method: Calculation method
        :return: wachstumsgradtage
        """

        item = self.items.return_item(item_path)
        if item:
            return self._handle_temperaturserie(item, year, method)

    def query_item(self, func: str, item_path: str, timeframe: str, start: int = None, end: int = 0, group: str = None, group2: str = None, ignore_value_list=None) -> list:
        item = self.items.return_item(item_path)
        if item is None:
            return []

        return self._query_item(func, item, timeframe, start, end, group, group2, ignore_value_list)

    def fetch_log(self, func: str, item_path: str, timeframe: str, start: int = None, end: int = 0, count: int = None, group: str = None, group2: str = None, ignore_value_list=None) -> list:
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
        :param ignore_value_list: list of comparison operators for val_num, which will be applied during query

        :return: formatted query response
        """
        item = self.items.return_item(item_path)

        if count:
            start, end = count_to_start(count)

        if item and start and end:
            return self._query_item(func=func, database_item=item, timeframe=timeframe, start=start, end=end, group=group, group2=group2, ignore_value_list=ignore_value_list)
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

    ##############################################
    #   Calculation methods / Using Item Object
    ##############################################

    def _handle_verbrauch(self, query_params: dict) -> Union[None, float]:
        """
        Ermittlung des Verbrauches innerhalb eines Zeitraumes

        Die Vorgehensweise ist:
            - Endwert: Abfrage des letzten Eintrages im Zeitraum
                - Ergibt diese Abfrage einen Wert, gab eines einen Eintrag im Zeitraum in der DB, es wurde also etwas verbraucht, dann entspricht dieser dem Endzählerstand
                - Ergibt diese Abfrage keinen Wert, gab eines keinen Eintrag im Zeitraum in der DB, es wurde also nichts verbraucht -> Rückgabe von 0
            - Startwert: Abfrage des letzten Eintrages im Zeitraum vor dem Abfragezeitraum
                - Ergibt diese Abfrage einen Wert, entspricht dieser dem Zählerstand am Ende des Zeitraumes vor dem Abfragezeitraum
                - Ergibt diese Abfrage keinen Wert, wurde in Zeitraum, vor dem Abfragezeitraum nichts verbraucht, der Anfangszählerstand kann so nicht ermittelt werden.
                    - Abfrage des nächsten Wertes vor dem Zeitraum
                    - Ergibt diese Abfrage einen Wert, entspricht dieser dem Anfangszählerstand
                    - Ergibt diese Abfrage keinen Wert, Anfangszählerstand = 0
        """

        # define start, end for verbrauch_jahreszeitraum_timedelta
        if 'timedelta' in query_params:
            timedelta = query_params.pop('timedelta')
            today = datetime.date.today()
            year = today.year - timedelta
            start_date = datetime.date(year, 1, 1) - relativedelta(days=1)  # Start ist Tag vor dem 1.1., damit Abfrage den Maximalwert von 31.12. 00:00:00 bis 1.1. 00:00:00 ergibt
            end_date = today - relativedelta(timedelta)
            start = (today - start_date).days
            end = (today - end_date).days
        else:
            start = query_params['start']
            end = query_params['end']

        # calculate consumption
        if self.prepare_debug:
            self.logger.debug(f"called with {query_params=}")

        # get value for end and check it;
        query_params.update({'func': 'last', 'start': end, 'end': end})
        value_end = self._query_item(**query_params)[0][1]

        if self.prepare_debug:
            self.logger.debug(f"{value_end=}")

        if value_end is None or value_end == 0:
            return value_end

        # get value for start and check it;
        query_params.update({'func': 'last', 'start': start, 'end': start})
        value_start = self._query_item(**query_params)[0][1]
        if self.prepare_debug:
            self.logger.debug(f"{value_start=}")

        if value_start is None:
            if self.prepare_debug:
                self.logger.debug(f"Error occurred during query. Return.")
            return

        if not value_start:
            self.logger.info(f"No DB Entry found for requested start date. Looking for next recent DB entry.")
            query_params.update({'func': 'next'})
            value_start = self._query_item(**query_params)[0][1]
            if self.prepare_debug:
                self.logger.debug(f"next recent value is {value_start=}")

        if not value_start:
            value_start = 0
            if self.prepare_debug:
                self.logger.debug(f"No start value available. Will be set to 0 as default")

        # calculate consumption
        consumption = value_end - value_start
        if self.prepare_debug:
            self.logger.debug(f"{consumption=}")

        if isinstance(consumption, float):
            if consumption.is_integer():
                consumption = int(consumption)
            else:
                consumption = round(consumption, 1)

        return consumption

    def _handle_verbrauch_serie(self, query_params: dict) -> list:
        """Ermittlung einer Serie von Verbräuchen in einem Zeitraumes für x Zeiträume"""

        series = []
        database_item = query_params['database_item']
        timeframe = query_params['timeframe']
        start = query_params['start']

        for i in range(1, start):
            value = self._handle_verbrauch({'database_item': database_item, 'timeframe': timeframe, 'start': i + 1, 'end': i})
            ts_start, ts_end = get_start_end_as_timestamp(timeframe, i, i + 1)
            series.append([ts_end, value])

        return series

    def _handle_zaehlerstand(self, query_params: dict) -> Union[float, int, None]:
        """
        Ermittlung des Zählerstandes zum Ende eines Zeitraumes

        Die Vorgehensweise ist:
            - Abfrage des letzten Eintrages im Zeitraum
            - Ergibt diese Abfrage einen Wert, entspricht dieser dem Zählerstand
            - Ergibt diese Abfrage keinen Wert, dann
                - Abfrage des nächsten Wertes vor dem Zeitraum
                - Ergibt diese Abfrage einen Wert, entspricht dieser dem Zählerstand
                - Ergibt diese Abfrage keinen Wert, dann Rückgabe von None
        """

        if self.prepare_debug:
            self.logger.debug(f"called with {query_params=}")

        # get last value of timeframe
        query_params.update({'func': 'last'})
        last_value = self._query_item(**query_params)[0][1]
        if self.prepare_debug:
            self.logger.debug(f"{last_value=}")

        if last_value is None:
            if self.prepare_debug:
                self.logger.debug(f"Error occurred during query. Return.")
            return

        if not last_value:
            # get last value (next) before timeframe
            self.logger.info(f"No DB Entry found for requested start date. Looking for next recent DB entry.")
            query_params.update({'func': 'next'})
            last_value = self._query_item(**query_params)[0][1]
            if self.prepare_debug:
                self.logger.debug(f"next recent value is {last_value=}")

        if isinstance(last_value, float):
            if last_value.is_integer():
                last_value = int(last_value)
            else:
                last_value = round(last_value, 1)

        return last_value

    def _handle_zaehlerstand_serie(self, query_params: dict) -> list:
        """Ermittlung einer Serie von Zählerständen zum Ende eines Zeitraumes für x Zeiträume"""

        series = []
        database_item = query_params['database_item']
        timeframe = query_params['timeframe']
        start = query_params['start']

        for i in range(1, start):
            value = self._handle_zaehlerstand({'database_item': database_item, 'timeframe': timeframe, 'start': i, 'end': i})
            ts_start = get_start_end_as_timestamp(timeframe, i, i)[0]
            series.append([ts_start, value])

        return series

    def _handle_kaeltesumme(self, database_item: Item, year: Union[int, str] = None, month: Union[int, str] = None) -> Union[int, None]:
        """
        Query database for kaeltesumme for given year or year/month
        https://de.wikipedia.org/wiki/K%C3%A4ltesumme

        :param database_item: item object or item_id for which the query should be done
        :param year: year the kaeltesumme should be calculated for
        :param month: month the kaeltesumme should be calculated for
        :return: kaeltesumme
        """

        if self.prepare_debug:
            self.logger.debug(f"called with {database_item=}, {year=}, {month=}")

        # check validity of given year
        if not valid_year(year):
            self.logger.error(f"Year for item={database_item.path()} was {year}. This is not a valid year. Query cancelled.")
            return

        # set default year
        if not year:
            year = 'current'

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
            self.logger.error(f"Month for item={database_item.path()} was {month}. This is not a valid month. Query cancelled.")
            return

        # define start / end
        today = datetime.date.today()
        if start_date > today:
            self.logger.error(f"Start time for query of item={database_item.path()} is in future. Query cancelled.")
            return

        start = (today - start_date).days
        end = (today - end_date).days if end_date < today else 0
        if start < end:
            self.logger.error(f"End time for query of item={database_item.path()} is before start time. Query cancelled.")
            return

        # get raw data as list
        if self.prepare_debug:
            self.logger.debug("try to get raw data")
        raw_data = self._prepare_temperature_list(database_item=database_item, timeframe='day', start=start, end=end, method='raw')
        if self.execute_debug:
            self.logger.debug(f"raw_value_list={raw_data=}")

        # calculate value
        if raw_data is None:
            return
        elif isinstance(raw_data, list):
            # akkumulieren alle negativen Werte
            ks = 0
            for entry in raw_data:
                if entry[1] < 0:
                    ks -= entry[1]
            return int(round(ks, 0))

    def _handle_waermesumme(self, database_item: Item, year: Union[int, str] = None, month: Union[int, str] = None, threshold: int = 0) -> Union[int, None]:
        """
        Query database for waermesumme for given year or year/month
        https://de.wikipedia.org/wiki/W%C3%A4rmesumme

        :param database_item: item object or item_id for which the query should be done
        :param year: year the waermesumme should be calculated for; "current" for current year
        :param month: month the waermesumme should be calculated for
        :return: waermesumme
        """

        # get raw data as list
        raw_data = self._prepare_waermesumme(database_item=database_item, year=year, month=month)
        if self.execute_debug:
            self.logger.debug(f"raw_value_list={raw_data=}")

        # set threshold to min 0
        threshold = max(0, threshold)

        # calculate value
        if raw_data is None:
            return
        elif isinstance(raw_data, list):
            # akkumulieren alle Werte, größer/gleich Schwellenwert
            ws = 0
            for entry in raw_data:
                if entry[1] >= threshold:
                    ws += entry[1]
            return int(round(ws, 0))

    def _handle_gruenlandtemperatursumme(self, database_item: Item, year: Union[int, str] = None) -> Union[int, None]:
        """
        Query database for gruenlandtemperatursumme for given year or year/month
        https://de.wikipedia.org/wiki/Gr%C3%BCnlandtemperatursumme

        :param database_item: item object for which the query should be done
        :param year: year the gruenlandtemperatursumme should be calculated for
        :return: gruenlandtemperatursumme
        """

        # get raw data as list
        raw_data = self._prepare_waermesumme(database_item=database_item, year=year)
        if self.execute_debug:
            self.logger.debug(f"raw_data={raw_data}")

        # calculate value
        if raw_data is None:
            return

        elif isinstance(raw_data, list):
            # akkumulieren alle positiven Tagesmitteltemperaturen, im Januar gewichtet mit 50%, im Februar mit 75%
            gts = 0
            for entry in raw_data:
                timestamp, value = entry
                if value > 0:
                    dt = datetime.datetime.fromtimestamp(timestamp / 1000)
                    if dt.month == 1:
                        value = value * 0.5
                    elif dt.month == 2:
                        value = value * 0.75
                    gts += value
            return int(round(gts, 0))

    def _handle_wachstumsgradtage(self, database_item: Item, year: Union[int, str] = None, method: int = 0, threshold: int = 10) -> Union[list, float, None]:
        """
        Calculate "wachstumsgradtage" for given year with temperature threshold
        https://de.wikipedia.org/wiki/Wachstumsgradtag

        :param database_item: item object or item_id for which the query should be done
        :param year: year the wachstumsgradtage should be calculated for
        :param method: calculation method to be used
        :param threshold: temperature in °C as threshold for evaluation
        :return: wachstumsgradtage
        """

        # set default year
        if not year:
            year = 'current'

        if not valid_year(year):
            self.logger.error(f"Year for item={database_item.path()} was {year}. This is not a valid year. Query cancelled.")
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
            self.logger.info(f"Start time for query of item={database_item.path()} is in future. Query cancelled.")
            return

        # define start / end
        start = (today - start_date).days
        end = (today - end_date).days if end_date < today else 0

        # check end
        if start < end:
            self.logger.error(f"End time for query of item={database_item.path()} is before start time. Query cancelled.")
            return

        # get raw data as list
        raw_data = self._prepare_temperature_list(database_item=database_item, timeframe='day',  start=start, end=end, method='minmax')
        if self.execute_debug:
            self.logger.debug(f"raw_value_list={raw_data}")

        # calculate value
        if raw_data is None:
            return

        if isinstance(raw_data, list):
            # Die Berechnung des einfachen Durchschnitts // akkumuliere positive Differenz aus Mittelwert aus Tagesminimaltemperatur und Tagesmaximaltemperatur limitiert auf 30°C und Schwellenwert
            wgte = 0
            wgte_list = []
            if method == 0 or method == 10:
                self.logger.info(f"Calculate 'Wachstumsgradtag' according to 'Berechnung des einfachen Durchschnitts'.")
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
                self.logger.info(f"Calculate 'Wachstumsgradtag' according to 'Modifizierte Berechnung des einfachen Durchschnitts'.")
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

            # Zähle Tage, bei denen die Tagesmitteltemperatur oberhalb des Schwellenwertes lag
            elif method == 2 or method == 12:
                self.logger.info(f"Calculate 'Wachstumsgradtag' according to 'Anzahl der Tage, bei denen die Tagesmitteltemperatur oberhalb des Schwellenwertes lag'.")
                for entry in raw_data:
                    timestamp, min_val, max_val = entry
                    wgt = (((min_val + min(30, max_val)) / 2) - threshold)
                    if wgt > 0:
                        wgte += 1
                    wgte_list.append([timestamp, wgte])
                if method == 0:
                    return wgte
                else:
                    return wgte_list

            else:
                self.logger.info(f"Method for 'Wachstumsgradtag' calculation not defined.'")

    def _handle_temperaturserie(self, database_item: Item, year: Union[int, str] = None, method: str = 'raw') -> Union[list, None]:
        """
        provide list of lists having timestamp and temperature(s) per day

        :param database_item: item object or item_id for which the query should be done
        :param year: year the wachstumsgradtage should be calculated for
        :param method: calculation method to be used
        :return: list of temperatures
        """

        # set default year
        if not year:
            year = 'current'

        if not valid_year(year):
            self.logger.error(f"Year for item={database_item.path()} was {year}. This is not a valid year. Query cancelled.")
            return

        # define year
        if year == 'current':
            year = datetime.date.today().year

        # define start_date, end_date
        start_date = datetime.date(int(year), 1, 1)
        end_date = datetime.date(int(year), 12, 31)

        # check start_date
        today = datetime.date.today()
        if start_date > today:
            self.logger.info(f"Start time for query of item={database_item.path()} is in future. Query cancelled.")
            return

        # define start / end
        start = (today - start_date).days
        end = (today - end_date).days if end_date < today else 0

        # check end
        if start < end:
            self.logger.error(f"End time for query of item={database_item.path()} is before start time. Query cancelled.")
            return

        # check method
        if method not in ['hour', 'raw', 'minmax']:
            self.logger.error(f"Calculation method {method!r} unknown. Need to be 'hour', 'raw' or 'minmax'. Query cancelled.")
            return

        # get raw data as list
        temp_list = self._prepare_temperature_list(database_item=database_item, timeframe='day',  start=start, end=end, method=method)
        if self.execute_debug:
            self.logger.debug(f"{temp_list=}")

        return temp_list

    def _prepare_waermesumme(self, database_item: Item, year: Union[int, str] = None, month: Union[int, str] = None) -> Union[list, None]:
        """Prepares raw data for waermesumme"""

        # check validity of given year
        if not valid_year(year):
            self.logger.error(f"Year for item={database_item.path()} was {year}. This is not a valid year. Query cancelled.")
            return

        # set default year
        if not year:
            year = 'current'

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
            self.logger.error(f"Month for item={database_item.path()} was {month}. This is not a valid month. Query cancelled.")
            return

        # check start_date
        today = datetime.date.today()
        if start_date > today:
            self.logger.info(f"Start time for query of item={database_item.path()} is in future. Query cancelled.")
            return

        # define start / end
        start = (today - start_date).days
        end = (today - end_date).days if end_date < today else 0

        # check end
        if start < end:
            self.logger.error(f"End time for query of item={database_item.path()} is before start time. Query cancelled.")
            return

        # return raw data as list
        return self._prepare_temperature_list(database_item=database_item, timeframe='day',  start=start, end=end, method='raw')

    def _prepare_temperature_list(self, database_item: Item, timeframe: str, start: int, end: int = 0, ignore_value_list=None, method: str = 'hour') -> Union[list, None]:
        """
        returns list of lists having timestamp and temperature(s) per day

        :param database_item: item object or item_id for which the query should be done
        :param timeframe: timeframe for query
        :param start: increments for timeframe from now to start
        :param end: increments for timeframe from now to end
        :param ignore_value_list: list of comparison operators for val_num, which will be applied during query
        :param method:  Calculation method
        :return: list of temperatures
        """

        def _create_temp_dict() -> dict:
            """create dict based on database query result like {'date1': {'hour1': [temp values], 'hour2': [temp values], ...}, 'date2': {'hour1': [temp values], 'hour2': [temp values], ...}, ...}"""

            _temp_dict = {}
            for _entry in raw_data:
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

        # temp_list = [[timestamp1, avg-value1], [timestamp2, avg-value2], [timestamp3, avg-value3], ...]  Tagesmitteltemperatur pro Stunde wird in der Datenbank per avg ermittelt
        if method == 'hour':
            raw_data = self._query_item(func='avg', database_item=database_item, timeframe=timeframe, start=start, end=end, group='hour', ignore_value_list=ignore_value_list)
            if self.prepare_debug:
                self.logger.debug(f"{raw_data=}")

            if raw_data and isinstance(raw_data, list):
                if raw_data == [[None, None]]:
                    return

                # create nested dict with temps
                temp_dict = _create_temp_dict()

                # create list of list like database query response
                temp_list = _create_list_timestamp_avgtemp()
                if self.prepare_debug:
                    self.logger.debug(f"{temp_list=}")
                return temp_list

        # temp_list = [[timestamp1, avg-value1], [timestamp2, avg-value2], [timestamp3, avg-value3], ...]  Tagesmitteltemperatur pro Stunde wird hier im Plugin ermittelt ermittelt
        elif method == 'raw':
            raw_data = self._query_item(func='raw', database_item=database_item, timeframe=timeframe, start=start, end=end, ignore_value_list=ignore_value_list)

            if raw_data and isinstance(raw_data, list):
                if raw_data == [[None, None]]:
                    return

                # create nested dict with temps
                temp_dict = _create_temp_dict()

                # calculate 'tagesdurchschnitt' and create list of list like database query response
                _calculate_hourly_average()
                if self.prepare_debug:
                    self.logger.debug(f"raw: {temp_dict=}")

                # create list of list like database query response
                temp_list = _create_list_timestamp_avgtemp()
                if self.prepare_debug:
                    self.logger.debug(f"{temp_list=}")
                return temp_list

        # temp_list = [[timestamp1, min-value1, max-value1], [timestamp2, min-value2, max-value2], [timestamp3, min-value3, max-value3], ...]
        elif method == 'minmax':
            raw_data = self._query_item(func='raw', database_item=database_item, timeframe=timeframe, start=start, end=end, ignore_value_list=ignore_value_list)

            if raw_data and isinstance(raw_data, list):
                if raw_data == [[None, None]]:
                    return

                # create nested dict with temps
                temp_dict = _create_temp_dict()
                if self.prepare_debug:
                    self.logger.debug(f"raw: {temp_dict=}")

                # create list of list like database query response
                temp_list = _create_list_timestamp_minmaxtemp()
                if self.prepare_debug:
                    self.logger.debug(f"{temp_list=}")
                return temp_list

    ####################
    #   Support stuff
    ####################

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

    def _query_item(self, func: str, database_item: Item, timeframe: str, start: int = None, end: int = 0, group: str = None, group2: str = None, ignore_value_list=None, use_oldest_entry: bool = False) -> list:
        """
        Do diverse checks of input, and prepare query of log by getting item_id, start / end in timestamp etc.

        :param func: function to be used at query
        :param database_item: item object or item_id for which the query should be done
        :param timeframe: time increment für definition of start, end (day, week, month, year)
        :param start: start of timeframe (oldest) for query given in x time increments (default = None, meaning complete database)
        :param end: end of timeframe (newest) for query given in x time increments (default = 0, meaning end of today, end of last week, end of last month, end of last year)
        :param group: first grouping parameter (default = None, possible values: day, week, month, year)
        :param group2: second grouping parameter (default = None, possible values: day, week, month, year)
        :param ignore_value_list: list of comparison operators for val_num, which will be applied during query
        :param use_oldest_entry: if start is prior to oldest entry, oldest entry will be used

        :return: query response / list for value pairs [[None, None]] for errors, [[0,0]] for no-data in DB
        """

        if self.prepare_debug:
            self.logger.debug(f"called with {func=}, item={database_item.path()}, {timeframe=}, {start=}, {end=}, {group=}, {group2=}, {ignore_value_list=}")

        # called with func='min', item=env.host_rpi.temperature, timeframe='day', start=0, end=0, group=None, group2=None, ignore_value_list=['!= 0']

        # set default result
        default_result = [[None, None]]

        # check correctness of timeframe
        if timeframe not in ALLOWED_QUERY_TIMEFRAMES:
            self.logger.error(f"Requested {timeframe=} for item={database_item.path()} not defined; Need to be 'year' or 'month' or 'week' or 'day' or 'hour''. Query cancelled.")
            return default_result

        # define start and end of query as timestamp in microseconds
        ts_start, ts_end = get_start_end_as_timestamp(timeframe, start, end)
        oldest_log = int(self._get_oldest_log(database_item))

        # check correctness of ts_start / ts_end
        if ts_start is None:
            ts_start = oldest_log
        if ts_end is None or ts_start > ts_end:
            if self.prepare_debug:
                self.logger.debug(f"{ts_start=}, {ts_end=}")
            self.logger.warning(f"Requested {start=} for item={database_item.path()} is not valid since {start=} < {end=} or end not given. Query cancelled.")
            return default_result

        # define item_id
        item_id = self._get_itemid(database_item)
        if not item_id:
            self.logger.error(f"ItemId for item={database_item.path()} not found. Query cancelled.")
            return default_result

        if self.prepare_debug:
            self.logger.debug(f"Requested {timeframe=} with {start=} and {end=} resulted in start being timestamp={ts_start} / {timestamp_to_timestring(ts_start)} and end being timestamp={ts_end} / {timestamp_to_timestring(ts_end)}")

        # check if values for end time and start time are in database
        if ts_end < oldest_log:  # (Abfrage abbrechen, wenn Endzeitpunkt in UNIX-timestamp der Abfrage kleiner (und damit jünger) ist, als der UNIX-timestamp des ältesten Eintrages)
            self.logger.info(f"Requested end time timestamp={ts_end} / {timestamp_to_timestring(ts_end)} of query for Item='{database_item.path()}' is prior to oldest entry with timestamp={oldest_log} / {timestamp_to_timestring(oldest_log)}. Query cancelled.")
            return default_result

        if ts_start < oldest_log:
            if self.use_oldest_entry or use_oldest_entry:
                self.logger.info(f"Requested start time timestamp={ts_start} / {timestamp_to_timestring(ts_start)} of query for Item='{database_item.path()}' is prior to oldest entry with timestamp={oldest_log} / {timestamp_to_timestring(oldest_log)}. Oldest available entry will be used.")
                ts_start = oldest_log
            else:
                self.logger.info(f"Requested start time timestamp={ts_start} / {timestamp_to_timestring(ts_start)} of query for Item='{database_item.path()}' is prior to oldest entry with timestamp={oldest_log} / {timestamp_to_timestring(oldest_log)}. Query cancelled.")
                return default_result

        # prepare and do query
        query_params = {'func': func, 'item_id': item_id, 'ts_start': ts_start, 'ts_end': ts_end, 'group': group, 'group2': group2, 'ignore_value_list': ignore_value_list}
        query_result = self._query_log_timestamp(**query_params)

        # post process query_result
        if query_result is None:
            self.logger.error(f"Error occurred during _query_item. Aborting...")
            return default_result

        if len(query_result) == 0:
            self.logger.info(f"No values for item in requested timeframe in database found.")
            return [[0, 0]]

        result = []
        for element in query_result:
            timestamp, value = element
            if timestamp and value is not None:
                if isinstance(value, float):
                    value = round(value, 1)
                result.append([timestamp, value])

        if self.prepare_debug:
            self.logger.debug(f"value for item={database_item.path()} with {query_params=}: {result}")

        if not result:
            self.logger.info(f"No values for item in requested timeframe in database found.")
            return default_result

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

    #################################
    #   Database Query Preparation
    #################################

    def _query_log_timestamp(self, func: str, item_id: int, ts_start: int, ts_end: int, group: str = None, group2: str = None, ignore_value_list=None) -> Union[list, None]:
        """
        Assemble a mysql query str and param dict based on given parameters, get query response and return it

        :param func: function to be used at query
        :param item_id: database item_id for which the query should be done
        :param ts_start: start for query given in timestamp in microseconds
        :param ts_end: end for query given in timestamp in microseconds
        :param group: first grouping parameter (default = None, possible values: day, week, month, year)
        :param group2: second grouping parameter (default = None, possible values: day, week, month, year)
        :param ignore_value_list: list of comparison operators for val_num, which will be applied during query

        :return: query response

        """

        # do debug log
        if self.prepare_debug:
            self.logger.debug(f"Called with {func=}, {item_id=}, {ts_start=}, {ts_end=}, {group=}, {group2=}, {ignore_value_list=}")

        # define query parts
        _select = {
            'avg':         'time, AVG(val_num * duration) / AVG(duration) as value ',
            'avg1':        'time, AVG(value) as value FROM (SELECT time, ROUND(AVG(val_num), 1) as value ',
            'min':         'time, MIN(val_num) as value ',
            'max':         'time, MAX(val_num) as value ',
            'max1':        'time, MAX(value) as value FROM (SELECT time, ROUND(MAX(val_num), 1) as value ',
            'sum':         'time, SUM(val_num) as value ',
            'on':          'time, SUM(val_bool * duration) / SUM(duration) as value ',
            'integrate':   'time, SUM(val_num * duration) as value ',
            'sum_max':     'time, SUM(value) as value FROM (SELECT time, ROUND(MAX(val_num), 1) as value ',
            'sum_avg':     'time, SUM(value) as value FROM (SELECT time, ROUND(AVG(val_num * duration) / AVG(duration), 1) as value ',
            'sum_min_neg': 'time, SUM(value) as value FROM (SELECT time, IF(min(val_num) < 0, ROUND(MIN(val_num), 1), 0) as value ',
            'diff_max':    'time, value1 - LAG(value1) OVER (ORDER BY time) AS value FROM (SELECT time, ROUND(MAX(val_num), 1) as value1 ',
            'next':        'time, val_num as value ',
            'raw':         'time, val_num as value ',
            'first':       'time, val_num as value ',
            'last':        'time, val_num as value ',
        }

        _table_alias = {
            'avg':         '',
            'avg1':        ') AS table1 ',
            'min':         '',
            'max':         '',
            'max1':        ') AS table1 ',
            'sum':         '',
            'on':          '',
            'integrate':   '',
            'sum_max':     ') AS table1 ',
            'sum_avg':     ') AS table1 ',
            'sum_min_neg': ') AS table1 ',
            'diff_max':    ') AS table1 ',
            'next':        '',
            'raw':         '',
            'first':       '',
            'last':        '',
        }

        _order = {
            'avg':         'time ASC ',
            'avg1':        'time ASC ',
            'min':         'time ASC ',
            'max':         'time ASC ',
            'max1':        'time ASC ',
            'sum':         'time ASC ',
            'on':          'time ASC ',
            'integrate':   'time ASC ',
            'sum_max':     'time ASC ',
            'sum_avg':     'time ASC ',
            'sum_min_neg': 'time ASC ',
            'diff_max':    'time ASC ',
            'next':        'time DESC LIMIT 1 ',
            'raw':         'time ASC ',
            'first':       'time ASC LIMIT 1 ',
            'last':        'time DESC LIMIT 1 ',
        }

        _where = "item_id = :item_id AND time < :ts_start " if func == "next" else "item_id = :item_id AND time BETWEEN :ts_start AND :ts_end "

        _db_table = 'log '

        _group_by_sql = {
            "year":  "GROUP BY YEAR(FROM_UNIXTIME(time/1000)) ",
            "month": "GROUP BY FROM_UNIXTIME((time/1000),'%Y%m') ",
            "week":  "GROUP BY YEARWEEK(FROM_UNIXTIME(time/1000), 5) ",
            "day":   "GROUP BY DATE(FROM_UNIXTIME(time/1000)) ",
            "hour":  "GROUP BY FROM_UNIXTIME((time/1000),'%Y%m%d%H') ",
            None:    "",
        }

        _group_by_sqlite = {
            "year":  "GROUP BY strftime('%Y', date((time/1000),'unixepoch')) ",
            "month": "GROUP BY strftime('%Y%m', date((time/1000),'unixepoch')) ",
            "week":  "GROUP BY strftime('%Y%W', date((time/1000),'unixepoch')) ",
            "day":   "GROUP BY date((time/1000),'unixepoch') ",
            "hour":  "GROUP BY strftime('%Y%m%d%H', datetime((time/1000),'unixepoch')) ",
            None:    "",
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
            self.logger.error(f"Requested {func=} for {item_id=} not defined. Query cancelled.")
            return

        # check correctness of group and group2
        if group not in _group_by:
            self.logger.error(f"Requested {group=} for item={item_id=} not defined. Query cancelled.")
            return
        if group2 not in _group_by:
            self.logger.error(f"Requested {group2=} for item={item_id=} not defined. Query cancelled.")
            return

        # handle ignore values
        if func in ['min', 'max', 'max1', 'sum_max', 'sum_avg', 'sum_min_neg', 'diff_max']:  # extend _where statement for excluding boolean values == 0 for defined functions
            _where = f'{_where}AND val_bool = 1 '
        if ignore_value_list:  # if comparison to be applied during query, extend _where statement
            for entry in ignore_value_list:
                _where = f'{_where}AND val_num {entry.strip()} '

        # set params
        params = {'item_id': item_id, 'ts_start': ts_start}
        if func != "next":
            params.update({'ts_end': ts_end})

        # assemble query
        query = f"SELECT {_select[func]}FROM {_db_table}WHERE {_where}{_group_by[group]}ORDER BY {_order[func]}{_table_alias[func]}{_group_by[group2]}".strip()

        if self.db_driver.lower() == 'sqlite3':
            query = query.replace('IF', 'IIF')

        # do debug log
        if self.prepare_debug:
            self.logger.debug(f"{query=}, {params=}")

        # request database and return result
        return self._fetchall(query, params)

    def _read_log_all(self, item_id: int):
        """
        Read the oldest log record for given item

        :param item_id: item_id to read the record for
        :return: Log record for item_id
        """

        if self.prepare_debug:
            self.logger.debug(f"called for {item_id=}")

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

    #######################
    #   Database Queries
    #######################

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
            self.logger.debug(f"Called with {query=}, {params=}, {cur=}")

        if not self._initialize_db():
            return None

        if cur is None:
            if self._db.verify(5) == 0:
                self.logger.error("Connection to database not recovered.")
                return None
            if not self._db.lock(300):
                self.logger.error("Can't query due to fail to acquire lock.")
                return None

        query_readable = re.sub(r':([a-z_]+)', r'{\1}', query).format(**params)

        try:
            tuples = fetch(query, params, cur=cur)
        except Exception as e:
            self.logger.error(f"Error for query '{query_readable}': {e}")
        else:
            if self.sql_debug:
                self.logger.debug(f"Result of '{query_readable}': {tuples}")
            return tuples
        finally:
            if cur is None:
                self._db.release()


#######################
#   Helper functions
#######################


def params_to_dict(string: str) -> Union[dict, None]:
    """Parse a string with named arguments and comma separation to dict; (e.g. string = 'year=2022, month=12')"""

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
    """Check if given year is digit and within allowed range"""

    if ((isinstance(year, int) or (isinstance(year, str) and year.isdigit())) and (
            1980 <= int(year) <= datetime.date.today().year)) or (isinstance(year, str) and year == 'current'):
        return True
    else:
        return False


def valid_month(month: Union[int, str]) -> bool:
    """Check if given month is digit and within allowed range"""

    if (isinstance(month, int) or (isinstance(month, str) and month.isdigit())) and (1 <= int(month) <= 12):
        return True
    else:
        return False


def timestamp_to_timestring(timestamp: int) -> str:
    """Parse timestamp from db query to string representing date and time"""

    return datetime.datetime.utcfromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')


def convert_timeframe(timeframe: str) -> str:
    """Convert timeframe"""

    lookup = {
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

    return lookup.get(timeframe)


def convert_duration(timeframe: str, window_dur: str) -> int:
    """Convert duration"""

    _h_in_d = 24
    _d_in_y = 365
    _d_in_w = 7
    _m_in_y = 12
    _w_in_y = _d_in_y / _d_in_w
    _w_in_m = _w_in_y / _m_in_y
    _d_in_m = _d_in_y / _m_in_y

    lookup = {
        'hour': {'hour': 1,
                 'day': _h_in_d,
                 'week': _h_in_d * _d_in_w,
                 'month': _h_in_d * _d_in_m,
                 'year': _h_in_d * _d_in_y,
                 },
        'day': {'hour': 1 / _h_in_d,
                'day': 1,
                'week': _d_in_w,
                'month': _d_in_m,
                'year': _d_in_y,
                },
        'week': {'hour': 1 / (_h_in_d * _d_in_w),
                 'day': 1 / _d_in_w,
                 'week': 1,
                 'month': _w_in_m,
                 'year': _w_in_y
                 },
        'month': {'hour': 1 / (_h_in_d * _d_in_m),
                  'day': 1 / _d_in_m,
                  'week': 1 / _w_in_m,
                  'month': 1,
                  'year': _m_in_y
                  },
        'year': {'hour': 1 / (_h_in_d * _d_in_y),
                 'day': 1 / _d_in_y,
                 'week': 1 / _w_in_y,
                 'month': 1 / _m_in_y,
                 'year': 1
                 }
    }

    return to_int(lookup[timeframe][window_dur])


def count_to_start(count: int = 0, end: int = 0):
    """Converts given count and end ot start and end"""

    return end + count, end


def get_start_end_as_timestamp(timeframe: str, start: Union[int, str, None], end: Union[int, str, None]) -> tuple:
    """
    Provides start and end as timestamp in microseconds from timeframe with start and end

    :param timeframe: timeframe as week, month, year
    :param start: beginning timeframe in x timeframes from now
    :param end: end of timeframe in x timeframes from now

    :return: start time in timestamp in microseconds, end time in timestamp in microseconds

    """

    def get_start() -> datetime:
        if timeframe == 'week':
            return _week_beginning()
        elif timeframe == 'month':
            return _month_beginning()
        elif timeframe == 'year':
            return _year_beginning()
        else:
            return _day_beginning()

    def get_end() -> datetime:
        if timeframe == 'week':
            return _week_end()
        elif timeframe == 'month':
            return _month_end()
        elif timeframe == 'year':
            return _year_end()
        else:
            return _day_end()

    def _year_beginning(delta: int = start) -> datetime:
        """provides datetime of beginning of year of today minus x years"""

        _dt = datetime.datetime.combine(datetime.date.today(), datetime.datetime.min.time())
        return _dt.replace(month=1, day=1) - relativedelta(years=delta)

    def _year_end(delta: int = end) -> datetime:
        """provides datetime of end of year of today minus x years"""

        return _year_beginning(delta) + relativedelta(years=1)

    def _month_beginning(delta: int = start) -> datetime:
        """provides datetime of beginning of month minus x month"""

        _dt = datetime.datetime.combine(datetime.date.today(), datetime.datetime.min.time())
        return _dt.replace(day=1) - relativedelta(months=delta)

    def _month_end(delta: int = end) -> datetime:
        """provides datetime of end of month minus x month"""

        return _month_beginning(delta) + relativedelta(months=1)

    def _week_beginning(delta: int = start) -> datetime:
        """provides datetime of beginning of week minus x weeks"""

        _dt = datetime.datetime.combine(datetime.date.today(), datetime.datetime.min.time())
        return _dt - relativedelta(days=(datetime.date.today().weekday() + (delta * 7)))

    def _week_end(delta: int = end) -> datetime:
        """provides datetime of end of week minus x weeks"""

        return _week_beginning(delta) + relativedelta(days=7)

    def _day_beginning(delta: int = start) -> datetime:
        """provides datetime of beginning of today minus x days"""

        return datetime.datetime.combine(datetime.date.today(), datetime.datetime.min.time()) - relativedelta(days=delta)

    def _day_end(delta: int = end) -> datetime:
        """provides datetime of end of today minus x days"""

        return _day_beginning(delta) + relativedelta(days=1)

    if isinstance(start, str) and start.isdigit():
        start = int(start)
    if isinstance(start, int):
        ts_start = datetime_to_timestamp(get_start()) * 1000
    else:
        ts_start = None

    if isinstance(end, str) and end.isdigit():
        end = int(end)
    if isinstance(end, int):
        ts_end = datetime_to_timestamp(get_end()) * 1000
    else:
        ts_end = None

    return ts_start, ts_end


def datetime_to_timestamp(dt: datetime) -> int:
    """Provides timestamp from given datetime"""

    return int(dt.replace(tzinfo=datetime.timezone.utc).timestamp())


def to_int(arg) -> Union[int, None]:
    try:
        return int(arg)
    except (ValueError, TypeError):
        return None


def to_float(arg) -> Union[float, None]:
    try:
        return float(arg)
    except (ValueError, TypeError):
        return None


def to_int_float(arg):
    try:
        return int(arg)
    except (ValueError, TypeError):
        return to_float(arg)


def timeframe_to_updatecyle(timeframe):

    lookup = {'day': 'daily',
              'week': 'weekly',
              'month': 'monthly',
              'year': 'yearly'}

    return lookup.get(timeframe)


ALLOWED_QUERY_TIMEFRAMES = ['year', 'month', 'week', 'day', 'hour']
ALLOWED_MINMAX_FUNCS = ['min', 'max', 'avg']


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
