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

import os
import sqlvalidator
import datetime
import time
import re
import queue
import pickle
import operator
from dateutil.relativedelta import relativedelta
from typing import Union
from dataclasses import dataclass, InitVar
from collections import deque

from lib.model.smartplugin import SmartPlugin
from lib.item import Items
from lib.item.item import Item
from lib.shtime import Shtime
from lib.plugin import Plugins
from .webif import WebInterface
from .item_attributes import *
from .item_attributes_master import ITEM_ATTRIBUTES
import lib.db

HOUR = 'hour'
DAY = 'day'
WEEK = 'week'
MONTH = 'month'
YEAR = 'year'


class DatabaseAddOn(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides the update functions for the items
    """

    PLUGIN_VERSION = '1.2.9'

    def __init__(self, sh):
        """
        Initializes the plugin.
        """

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        self.logger.debug(f'Start of {self.get_shortname()} Plugin.')

        # get item and shtime instance
        self.shtime = Shtime.get_instance()
        self.items = Items.get_instance()
        self.plugins = Plugins.get_instance()

        # define cache dicts
        self.pickle_data_validity_time = 600        # seconds after which the data saved in pickle are not valid anymore
        self.current_values = {}                    # Dict to hold min and max value of current day / week / month / year for items
        self.previous_values = {}                   # Dict to hold value of end of last day / week / month / year for items
        self.item_cache = {}                        # Dict to hold item_id, oldest_log_ts and oldest_entry for items
        self.value_list_raw_data = {}               # List to hold raw data

        # define variables for database, database connection, working queue and status
        self.item_queue = queue.Queue()              # Queue containing all to be executed items
        self.update_item_delay_deque = deque()       # Deque for delay working of updated item values
        self._db_plugin = None                       # object if database plugin
        self._db = None                              # object of database
        self.connection_data = None                  # connection data list of database
        self.db_driver = None                        # driver of the used database
        self.db_instance = None                      # instance of the used database
        self.item_attribute_search_str = 'database'  # attribute, on which an item configured for database can be identified
        self.last_connect_time = 0                   # mechanism for limiting db connection requests
        self.alive = None                            # Is plugin alive?
        self.active_queue_item: str = '-'            # String holding item path of currently executed item
        self.onchange_delay_time = 30                # delay time in seconds between change of database item start of reevaluation of db_addon item
        self.database_item_list = []                 # list of needed database items

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
        self.lock_db_for_query = self.get_parameter_value('lock_db_for_query')

        # path and filename for data storage
        data_storage_file = 'db_addon_data'
        self.data_storage_path = f"{os.getcwd()}/var/plugin_data/{self.get_shortname()}/{data_storage_file}.pkl"

        # get debug log options
        self.debug_log = DebugLogOptions(self.log_level)

        # init cache data
        self.init_cache_data()

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
            return

        # create db object
        self._db = lib.db.Database("DatabaseAddOn", self.db_driver, self.connection_data)
        if not self._db.api_initialized:
            self.logger.error("Initialization of database API failed")
            return
        self.logger.debug("Initialization of database API successful")

        # check initialization of db
        if not self._initialize_db():
            self.logger.error("Connection to database failed")
            return
        self._db.close()

        # check db connection settings
        if self.db_driver.lower() == 'pymysql':
            self._check_db_connection_setting()

        # add scheduler for cyclic trigger item calculation
        self.scheduler_add('cyclic', self.execute_due_items, prio=3, cron='10 * * * *', cycle=None, value=None, offset=None, next=None)

        # add scheduler to trigger items to be calculated at startup with delay
        dt = self.shtime.now() + relativedelta(seconds=(self.startup_run_delay + 3))
        self.logger.info(f"Set scheduler for calculating startup-items with delay of {self.startup_run_delay + 3}s to {dt}.")
        self.scheduler_add('startup', self.execute_startup_items, next=dt)

        # update database_items in item config, where path was given
        self._update_database_items()

        # create list if all relevant database items
        self._create_list_of_relevant_database_items()

        # set plugin to alive
        self.alive = True

        # work item queue
        self.work_item_queue()

    def stop(self):
        """
        Stop method for the plugin
        """

        self.logger.debug("Stop method called")
        self.alive = False
        self.scheduler_remove('cyclic')
        self.scheduler_remove('onchange_delay')
        if self._db:
            self._db.close()
        self.save_cache_data()

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
            """ derived parameters from given db_addon_fct"""

            # get parameter
            db_addon_fct_vars = db_addon_fct.split('_')
            func = timeframe = timedelta = start = end = group = group2 = data_con_func = log_text = None
            required_params = None

            if db_addon_fct in HISTORIE_ATTRIBUTES_ONCHANGE:
                # handle functions 'minmax onchange' in format 'minmax_timeframe_func' items like 'minmax_heute_max', 'minmax_heute_min', 'minmax_woche_max', 'minmax_woche_min'
                timeframe = translate_timeframe(db_addon_fct_vars[1])
                func = db_addon_fct_vars[2] if db_addon_fct_vars[2] in ALLOWED_MINMAX_FUNCS else None
                start = end = 0
                log_text = 'minmax_timeframe_func'
                required_params = [func, timeframe, start, end]

            elif db_addon_fct in HISTORIE_ATTRIBUTES_LAST:
                # handle functions 'minmax_last' in format 'minmax_last_timedelta|timeframe_function' like 'minmax_last_24h_max'
                func = db_addon_fct_vars[3]
                start, timeframe = split_sting_letters_numbers(db_addon_fct_vars[2])
                start = to_int(start)
                timeframe = translate_timeframe(timeframe)
                end = 0
                log_text = 'minmax_last_timedelta|timeframe_function'
                required_params = [func, timeframe, start, end]

            elif db_addon_fct in HISTORIE_ATTRIBUTES_TIMEFRAME:
                # handle functions 'min/max/avg' in format 'minmax_timeframe_timedelta_func' like 'minmax_heute_minus2_max'
                func = db_addon_fct_vars[3]  # min, max, avg
                timeframe = translate_timeframe(db_addon_fct_vars[1])  # day, week, month, year
                start = end = to_int(split_sting_letters_numbers(db_addon_fct_vars[2])[1])
                log_text = 'minmax_timeframe_timedelta_func'
                required_params = [func, timeframe, start, end]

            elif db_addon_fct in ZAEHLERSTAND_ATTRIBUTES_TIMEFRAME:
                # handle functions 'zaehlerstand' in format 'zaehlerstand_timeframe_timedelta' like 'zaehlerstand_heute_minus1'
                func = 'last'
                timeframe = translate_timeframe(db_addon_fct_vars[1])
                start = end = to_int(split_sting_letters_numbers(db_addon_fct_vars[2])[1])
                log_text = 'zaehlerstand_timeframe_timedelta'
                required_params = [timeframe, start, end]

            elif db_addon_fct in VERBRAUCH_ATTRIBUTES_ONCHANGE:
                # handle functions 'verbrauch onchange' items in format 'verbrauch_timeframe' like 'verbrauch_heute', 'verbrauch_woche', 'verbrauch_monat', 'verbrauch_jahr'
                timeframe = translate_timeframe(db_addon_fct_vars[1])
                start = end = 0
                log_text = 'verbrauch_timeframe'
                required_params = [timeframe, start, end]

            elif db_addon_fct in VERBRAUCH_ATTRIBUTES_TIMEFRAME:
                # handle functions 'verbrauch on-demand' in format 'verbrauch_timeframe_timedelta' like 'verbrauch_heute_minus2'
                timeframe = translate_timeframe(db_addon_fct_vars[1])
                start = end = to_int(split_sting_letters_numbers(db_addon_fct_vars[2])[1])
                log_text = 'verbrauch_timeframe_timedelta'
                required_params = [timeframe, start, end]

            elif db_addon_fct in VERBRAUCH_ATTRIBUTES_LAST:
                # handle functions 'verbrauch_last' in format 'verbrauch_last_timedelta|timeframe' like 'verbrauch_last_24h'
                start, timeframe = split_sting_letters_numbers(db_addon_fct_vars[2])
                start = to_int(start)
                timeframe = translate_timeframe(timeframe)
                end = 0
                log_text = 'verbrauch_last_timedelta|timeframe'
                required_params = [timeframe, start, end]

            elif db_addon_fct in VERBRAUCH_ATTRIBUTES_ROLLING:
                # handle functions 'verbrauch_on-demand' in format 'verbrauch_rolling_window_timeframe_timedelta' like 'verbrauch_rolling_12m_woche_minus1'
                func = db_addon_fct_vars[1]
                window_inc, window_dur = split_sting_letters_numbers(db_addon_fct_vars[2])
                window_inc = to_int(window_inc)  # 12
                window_dur = translate_timeframe(window_dur)  # day, week, month, year
                timeframe = translate_timeframe(db_addon_fct_vars[3])  # day, week, month, year
                end = to_int(split_sting_letters_numbers(db_addon_fct_vars[4])[1])
                if window_dur in ALLOWED_QUERY_TIMEFRAMES and window_inc and timeframe and end:
                    start = to_int(timeframe_to_timeframe(timeframe, window_dur) * window_inc) + end
                log_text = 'verbrauch_rolling_window_timeframe_timedelta'
                required_params = [func, timeframe, start, end]

            elif db_addon_fct in VERBRAUCH_ATTRIBUTES_JAHRESZEITRAUM:
                # handle functions of format 'verbrauch_jahreszeitraum_timedelta' like 'verbrauch_jahreszeitraum_minus1'
                timeframe = translate_timeframe(db_addon_fct_vars[1])  # day, week, month, year
                timedelta = to_int(split_sting_letters_numbers(db_addon_fct_vars[2])[1])
                log_text = 'verbrauch_jahreszeitraum_timedelta'
                required_params = [timeframe, timedelta]

            elif db_addon_fct in TAGESMITTEL_ATTRIBUTES_ONCHANGE:
                # handle functions 'tagesmitteltemperatur onchange' items in format 'tagesmitteltemperatur_timeframe' like 'tagesmitteltemperatur_heute', 'tagesmitteltemperatur_woche', 'tagesmitteltemperatur_monat', 'tagesmitteltemperatur_jahr'
                timeframe = translate_timeframe(db_addon_fct_vars[1])
                func = 'max'
                start = end = 0
                log_text = 'tagesmitteltemperatur_timeframe'
                required_params = [timeframe, start, end]

            elif db_addon_fct in TAGESMITTEL_ATTRIBUTES_TIMEFRAME:
                # handle 'tagesmitteltemperatur_timeframe_timedelta' like 'tagesmitteltemperatur_heute_minus1'
                func = 'max'
                timeframe = translate_timeframe(db_addon_fct_vars[1])
                start = end = to_int(split_sting_letters_numbers(db_addon_fct_vars[2])[1])
                data_con_func = 'first_hour_avg_day'
                log_text = 'tagesmitteltemperatur_timeframe_timedelta'
                required_params = [func, timeframe, start, end, data_con_func]

            elif db_addon_fct in SERIE_ATTRIBUTES_MINMAX:
                # handle functions 'serie_minmax' in format 'serie_minmax_timeframe_func_start|group' like 'serie_minmax_monat_min_15m'
                func = db_addon_fct_vars[3]
                timeframe = translate_timeframe(db_addon_fct_vars[2])
                start, group = split_sting_letters_numbers(db_addon_fct_vars[4])
                start = to_int(start)
                group = translate_timeframe(group)
                end = 0
                log_text = 'serie_minmax_timeframe_func_start|group'
                required_params = [func, timeframe, start, end, group]

            elif db_addon_fct in SERIE_ATTRIBUTES_ZAEHLERSTAND:
                # handle functions 'serie_zaehlerstand' in format 'serie_zaehlerstand_timeframe_start|group' like 'serie_zaehlerstand_tag_30d'
                timeframe = translate_timeframe(db_addon_fct_vars[2])
                start, group = split_sting_letters_numbers(db_addon_fct_vars[3])
                start = to_int(start)
                group = translate_timeframe(group)
                log_text = 'serie_zaehlerstand_timeframe_start|group'
                required_params = [timeframe, start, group]

            elif db_addon_fct in SERIE_ATTRIBUTES_VERBRAUCH:
                # handle all functions of format 'serie_verbrauch_timeframe_start|group' like 'serie_verbrauch_tag_30d'
                timeframe = translate_timeframe(db_addon_fct_vars[2])
                start, group = split_sting_letters_numbers(db_addon_fct_vars[3])
                start = to_int(start)
                group = translate_timeframe(group)
                log_text = 'serie_verbrauch_timeframe_start|group'
                required_params = [timeframe, start, group]

            elif db_addon_fct in SERIE_ATTRIBUTES_SUMME:
                # handle all summe in format 'serie_xxsumme_timeframe_count|group' like serie_waermesumme_monat_24m
                func = 'sum_max'
                start, timeframe = split_sting_letters_numbers(db_addon_fct_vars[3])
                start = to_int(start)
                timeframe = translate_timeframe(timeframe)
                end = 0
                group = 'day',
                group2 = 'month'
                log_text = 'serie_xxsumme_timeframe_count|group'
                required_params = [func, timeframe, start, end, group, group2]

            elif db_addon_fct in SERIE_ATTRIBUTES_MITTEL_D:
                # handle 'serie_tagesmittelwert_count|group' like 'serie_tagesmittelwert_0d' => Tagesmittelwert der letzten 0 Tage (also heute)
                func = 'max'
                timeframe = 'year'
                start, group = split_sting_letters_numbers(db_addon_fct_vars[2])
                start = to_int(start)
                group = translate_timeframe(group)
                end = 0
                log_text = 'serie_tagesmittelwert_count|group'
                required_params = [func, timeframe, start, end, group]

            elif db_addon_fct in SERIE_ATTRIBUTES_MITTEL_H:
                # handle 'serie_tagesmittelwert_group2_count|group' like 'serie_tagesmittelwert_stunde_0d' => Stundenmittelwerte der letzten 0 Tage (also heute)
                func = 'avg1'
                timeframe = 'day'
                end = 0
                group = 'hour'
                start, group2 = split_sting_letters_numbers(db_addon_fct_vars[3])
                start = to_int(start)
                group2 = translate_timeframe(group2)
                log_text = 'serie_tagesmittelwert_group2_count|group'
                required_params = [func, timeframe, start, end, group, group2]

            elif db_addon_fct in SERIE_ATTRIBUTES_MITTEL_H1:
                # handle 'serie_tagesmittelwert_stunde_start_end|group' like 'serie_tagesmittelwert_stunde_30_0d' => Stundenmittelwerte von vor 30 Tagen bis vor 0 Tagen (also heute)
                data_con_func = 'avg_hour'
                start = to_int(db_addon_fct_vars[3])
                end, timeframe = split_sting_letters_numbers(db_addon_fct_vars[4])
                end = to_int(end)
                timeframe = translate_timeframe(timeframe)
                log_text = 'serie_tagesmittelwert_stunde_start_end|group'
                required_params = [timeframe, data_con_func, start, end]

            elif db_addon_fct in SERIE_ATTRIBUTES_MITTEL_D_H:
                # handle 'serie_tagesmittelwert_tag_stunde_end|group' like 'serie_tagesmittelwert_tag_stunde_30d' => Tagesmittelwert auf Basis des Mittelwerts pro Stunden für die letzten 30 Tage
                data_con_func = 'first_hour_avg_day'
                end = 0
                start, timeframe = split_sting_letters_numbers(db_addon_fct_vars[4])
                start = to_int(start)
                timeframe = translate_timeframe(timeframe)
                log_text = 'serie_tagesmittelwert_tag_stunde_end|group'
                required_params = [timeframe, data_con_func, start, end]

            elif db_addon_fct in ALL_GEN_ATTRIBUTES:
                log_text = 'all_gen_attributes'
                required_params = []

            if required_params is None:
                self.logger.warning(f"For calculating '{db_addon_fct}' at Item '{item.property.path}' no mandatory parameters given.")
                return

            if required_params and None in required_params:
                self.logger.warning(f"For calculating '{db_addon_fct}' at Item '{item.property.path}' not all mandatory parameters given. Definitions are: {func=}, {timeframe=}, {timedelta=}, {start=}, {end=}, {group=}, {group2=}, {data_con_func=}")
                return

            # create dict and reduce dict to keys with value != None
            param_dict = {'func': func, 'timeframe': timeframe, 'timedelta': timedelta, 'start': start, 'end': end, 'group': group, 'group2': group2, 'data_con_func': data_con_func}

            # return reduced dict w keys with value != None
            return {k: v for k, v in param_dict.items() if v is not None}

        def get_query_parameters_from_db_addon_params() -> Union[dict, None]:
            """derives parameters from item attribute db_addon_params, if parameter for db_addon_fct are not sufficient

                possible_params may be given, if not, default value is used
                required_params must be given
            """

            db_addon_params = params_to_dict(self.get_iattr_value(item.conf, 'db_addon_params'))

            if not db_addon_params:
                db_addon_params = self.get_iattr_value(item.conf, 'db_addon_params_dict')

            if not db_addon_params:
                db_addon_params = {}

            new_db_addon_params = {}
            possible_params = required_params = []

            # create item config for all functions with 'summe' like waermesumme, kaeltesumme, gruenlandtemperatursumme
            if db_addon_fct in ('kaeltesumme', 'waermesumme', 'gruenlandtempsumme'):
                possible_params = ['year', 'month']

            # create item config for wachstumsgradtage attributes
            elif db_addon_fct == 'wachstumsgradtage':
                possible_params = ['year', 'variant', 'threshold', 'result']

            # create item config for kenntage attributes
            elif db_addon_fct in ('wuestentage', 'heisse_tage', 'tropennaechte', 'sommertage', 'heiztage', 'vegetationstage', 'frosttage', 'eistage'):
                possible_params = ['year', 'month']

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
                self.logger.warning(f"Item '{item.property.path}' with {db_addon_fct=} ignored, since not all mandatory parameters in {db_addon_params=} are given. Item will be ignored.")
                return

            # reduce dict to possible keys + required_params
            for key in possible_params + required_params:
                value = db_addon_params.get(key)
                if value:
                    new_db_addon_params[key] = value

            return new_db_addon_params

        def get_database_item_path() -> tuple:
            """
            Returns item_path from shNG config which is an item with database attribut valid for current db_addon item
            """

            _lookup_item = item

            for i in range(3):
                if self.has_iattr(_lookup_item.conf, 'db_addon_database_item'):
                    if self.debug_log.parse:
                        self.logger.debug(f"Attribut 'db_addon_database_item' for item='{item.property.path}' has been found {i} level above item at '{_lookup_item.property.path}'.")
                    _database_item_path = self.get_iattr_value(_lookup_item.conf, 'db_addon_database_item')
                    if self.debug_log.parse:
                        self.logger.debug(f"{_database_item_path=}, {_lookup_item.property.path}")
                    return _database_item_path, _lookup_item
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
                    if self.debug_log.parse:
                        self.logger.debug(f"Attribut '{self.item_attribute_search_str}' for item='{item.property.path}'  has been found {i + 1} level above item at '{_lookup_item.property.path}'.")
                    return _lookup_item
                else:
                    _lookup_item = _lookup_item.return_parent()

            return None, None

        def check_db_addon_fct(check_item) -> bool:
            """
            Check if item has db_addon_fct and is onchange
            """
            if self.has_iattr(check_item.conf, 'db_addon_fct'):
                if self.get_iattr_value(check_item.conf, 'db_addon_fct').lower() in ONCHANGE_ATTRIBUTES:
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

            if self.debug_log.parse:
                self.logger.debug(f"Summarized 'ignore_value_list' for item {item.property.path}: {db_addon_ignore_value_list_formatted}")

            if not db_addon_ignore_value_list_formatted:
                return

            if not optimize:
                return db_addon_ignore_value_list_formatted

            if self.debug_log.parse:
                self.logger.debug(f"Optimizing 'ignore_value_list' for item {item.property.path} active.")

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

            if self.debug_log.parse:
                self.logger.debug(f"Optimized 'ignore_value_list' for item {item.property.path}: {db_addon_ignore_value_list_optimized}")

            return db_addon_ignore_value_list_optimized

        # handle all items with db_addon_fct
        if self.has_iattr(item.conf, 'db_addon_fct'):

            if self.debug_log.parse:
                self.logger.debug(f"parse item: {item.property.path} due to 'db_addon_fct'")

            # get db_addon_fct attribute value
            db_addon_fct = self.get_iattr_value(item.conf, 'db_addon_fct').lower()

            # read item_attribute_dict aus item_attributes_master
            item_attribute_dict = ITEM_ATTRIBUTES['db_addon_fct'].get(db_addon_fct)

            # get query parameters from db_addon_fct or db_addon_params
            if item_attribute_dict['params']:
                query_params = get_query_parameters_from_db_addon_params()
            else:
                query_params = get_query_parameters_from_db_addon_fct()
            if query_params is None:
                return

            # get database item (and attribute value if item should be calculated at plugin startup) and return if not available
            database_item, database_item_definition_item = get_database_item_path()
            if database_item is None:
                database_item = get_database_item()
                database_item_definition_item = item
            db_addon_startup = self.get_iattr_value(database_item_definition_item.conf, 'db_addon_startup')
            db_addon_ignore_value_list = self.get_iattr_value(database_item_definition_item.conf, 'db_addon_ignore_value_list')  # ['> 0', '< 35']
            db_addon_ignore_value = self.get_iattr_value(database_item_definition_item.conf, 'db_addon_ignore_value')  # num
            if database_item is None:
                self.logger.warning(f"No database item found for item={item.property.path}: Item ignored. Maybe you should check instance of database plugin.")
                return
            else:
                if self.debug_log.parse:
                    self.logger.debug(f"{database_item=}, {db_addon_startup=}, {db_addon_ignore_value_list=}, {db_addon_ignore_value=}")

            # create list of comparison operators and check it
            if not db_addon_ignore_value_list:
                db_addon_ignore_value_list = []

            if db_addon_ignore_value:
                db_addon_ignore_value_list.append(f"!= {db_addon_ignore_value}")

            if any(x in str(item.property.path) for x in self.ignore_0):
                db_addon_ignore_value_list.append("!= 0")

            if self.value_filter:
                for entry in list(self.value_filter.keys()):
                    if entry in str(item.property.path):
                        db_addon_ignore_value_list.extend(self.value_filter[entry])

            if db_addon_ignore_value_list:
                db_addon_ignore_value_list_final = format_db_addon_ignore_value_list()
                if self.debug_log.parse:
                    self.logger.debug(f"{db_addon_ignore_value_list_final=}")
                query_params.update({'ignore_value_list': db_addon_ignore_value_list_final})

            # create standard items config
            item_config_data_dict = {'db_addon': 'function', 'db_addon_fct': db_addon_fct, 'database_item': database_item, 'query_params': query_params, 'suspended': False}
            if isinstance(database_item, str):
                item_config_data_dict.update({'database_item_path': True})
            else:
                database_item = database_item.property.path

            # do logging
            if self.debug_log.parse:
                self.logger.debug(f"Item={item.property.path} added with db_addon_fct={db_addon_fct} and database_item={database_item}")

            # add cycle for item groups
            cycle = item_attribute_dict['cycle']
            on = 'demand'
            if cycle == 'group':
                cycle = item_config_data_dict['query_params'].get('group')
                if not cycle:
                    cycle = item_config_data_dict['query_params'].get('timeframe')
                    cycle = f"{timeframe_to_updatecyle(cycle)}"
            elif cycle == 'timeframe':
                cycle = item_config_data_dict['query_params'].get('timeframe')
                cycle = f"{timeframe_to_updatecyle(cycle)}"
            elif not cycle:
                on = 'change'
            item_config_data_dict.update({'cycle': cycle, 'on': on})

            # do logging
            if self.debug_log.parse:
                if cycle:
                    self.logger.debug(f"Item '{item.property.path}' added to be run {item_config_data_dict['cycle']}.")
                else:
                    self.logger.debug(f"Item '{item.property.path}' added but will not be run cyclic.")

                if on == 'change':
                    self.logger.debug(f"Item '{item.property.path}' added and will be run on-change of {database_item}.")

            # create item config for item to be run on startup
            if db_addon_startup or item_attribute_dict['cat'] == 'gen':
                item_config_data_dict.update({'startup': True})
            else:
                item_config_data_dict.update({'startup': False})

            # add item to plugin item dict
            if self.debug_log.parse:
                self.logger.debug(f"Item '{item.property.path}' completely parsed: {item_config_data_dict=}.")
            self.add_item(item, config_data_dict=item_config_data_dict)

        # handle all items with db_addon_info
        elif self.has_iattr(item.conf, 'db_addon_info'):
            if self.debug_log.parse:
                self.logger.debug(f"parse item={item.property.path} due to used item attribute 'db_addon_info'")
            self.add_item(item, config_data_dict={'db_addon': 'info', 'db_addon_fct': f"info_{self.get_iattr_value(item.conf, 'db_addon_info').lower()}", 'database_item': None, 'startup': True})

        # handle all items with db_addon_admin
        elif self.has_iattr(item.conf, 'db_addon_admin'):
            if self.debug_log.parse:
                self.logger.debug(f"parse item={item.property.path} due to used item attribute 'db_addon_admin'")
            self.add_item(item, config_data_dict={'db_addon': 'admin', 'db_addon_fct': f"admin_{self.get_iattr_value(item.conf, 'db_addon_admin').lower()}", 'database_item': None})
            return self.update_item

        # Reference to 'update_item' for all database items to trigger calculation of on-change items
        elif self.has_iattr(item.conf, self.item_attribute_search_str):
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
                self.logger.debug(f" Updated Item {item.property.path} with value {item()} will be put to queue in approx. {self.onchange_delay_time}s resp. after startup.")
                self.update_item_delay_deque.append([item, item(), int(time.time() + self.onchange_delay_time)])

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

    def _save_pickle(self, data) -> None:
        """Saves received data as pickle to given file"""

        if data and len(data) > 0:
            self.logger.debug(f"Start writing {data=} to '{self.data_storage_path}'")
            os.makedirs(os.path.dirname(self.data_storage_path), exist_ok=True)
            try:
                with open(self.data_storage_path, "wb") as output:
                    try:
                        pickle.dump(data, output, pickle.HIGHEST_PROTOCOL)
                        self.logger.debug(f"Successfully wrote data to '{self.data_storage_path}'")
                    except Exception as e:
                        self.logger.debug(f"Unable to write data to '{self.data_storage_path}': {e}")
                        pass
            except OSError as e:
                self.logger.debug(f"Unable to write data to '{self.data_storage_path}': {e}")
                pass

    def _read_pickle(self):
        """read a pickle file to gather data"""

        self.logger.debug(f"Start reading data from '{self.data_storage_path}'")

        if os.path.exists(self.data_storage_path):
            with open(self.data_storage_path, 'rb') as data:
                try:
                    data = pickle.load(data)
                    self.logger.debug(f"Successfully read data from {self.data_storage_path}")
                    return data
                except Exception as e:
                    self.logger.debug(f"Unable to read data from {self.data_storage_path}: {e}")
                    return None

        self.logger.debug(f"Unable to read data from {self.data_storage_path}: 'File/Path not existing'")
        return None

    def init_cache_data(self):
        """init cache dicts by reading pickle"""

        def create_items_1(d):
            n_d = {}
            for item_str in d:
                item = self.items.return_item(item_str)
                if item:
                    n_d[item] = d[item_str]
            return n_d

        def create_items_2(d):
            n_d = {}
            for timeframe in d:
                n_d[timeframe] = {}
                for item_str in d[timeframe]:
                    item = self.items.return_item(item_str)
                    if item:
                        n_d[timeframe][item] = d[timeframe][item_str]
            return n_d

        # init cache dicts
        self._init_cache_dicts()

        # read pickle and set data
        raw_data = self._read_pickle()

        if not isinstance(raw_data, dict):
            self.logger.info("Unable to extract db_addon data from pickle file. Start with empty cache.")
            return

        current_values = raw_data.get('current_values')
        previous_values = raw_data.get('previous_values')
        item_cache = raw_data.get('item_cache')
        stop_time = raw_data.get('stop_time')

        if not stop_time or (int(time.time()) - stop_time) > self.pickle_data_validity_time:
            self.logger.info("Data for db_addon read from pickle are expired. Start with empty cache.")
            return

        if isinstance(current_values, dict):
            self.current_values = create_items_2(current_values)
        if isinstance(previous_values, dict):
            self.previous_values = create_items_2(previous_values)
        if isinstance(item_cache, dict):
            self.item_cache = create_items_1(item_cache)

    def save_cache_data(self):
        """save all relevant data to survive restart, transform items in item_str"""

        def clean_items_1(d):
            n_d = {}
            for item in d:
                n_d[item.property.path] = d[item]
            return n_d

        def clean_items_2(d):
            n_d = {}
            for timeframe in d:
                n_d[timeframe] = {}
                for item in d[timeframe]:
                    n_d[timeframe][item.property.path] = d[timeframe][item]
            return n_d

        self._save_pickle({'current_values': clean_items_2(self.current_values),
                           'previous_values': clean_items_2(self.previous_values),
                           'item_cache': clean_items_1(self.item_cache),
                           'stop_time': int(time.time())})

    #########################################
    #           Item Handling
    #########################################

    def execute_due_items(self) -> None:
        """Execute all items, which are due"""

        self.execute_items()

    def execute_startup_items(self) -> None:
        """Execute all startup_items and set scheduler for delaying onchange items"""

        # execute item calculation
        self.execute_items(option='startup')

        # add scheduler for delayed working if onchange items
        self.scheduler_add('onchange_delay', self.work_update_item_delay_deque, prio=3, cron=None, cycle=30, value=None, offset=None, next=None)

    def execute_items(self, option: str = 'due', item: str = None):
        """Execute all items per option"""

        def _create_due_items() -> list:
            """Create list of items which are due and reset cache dicts"""

            # set für zu berechnende Items erstellen
            _todo_items = set()
            _reset_items = set()

            # stündlich zu berechnende Items hinzufügen
            _todo_items.update(set(self._ondemand_hourly_items()))
            # cache dict leeren
            self.current_values[HOUR] = {}
            self.previous_values[HOUR] = {}

            # wenn aktuelle Stunde == 0, werden auch die täglichen Items berechnet
            if self.shtime.now().hour == 0:
                # item zur Aufgabeliste hinzufügen
                _todo_items.update(set(self._ondemand_daily_items()))
                # cache dict leeren
                self.current_values[DAY] = {}
                self.previous_values[DAY] = {}
                self.value_list_raw_data = {}
                # reset Item-Wert alle onchange
                _reset_items.update(set(self._onchange_daily_items()))

                # wenn zusätzlich der Wochentag == Montag, werden auch die wöchentlichen Items berechnet
                if self.shtime.weekday(self.shtime.today()) == 1:
                    # item zur Aufgabeliste hinzufügen
                    _todo_items.update(set(self._ondemand_weekly_items()))
                    # cache dict leeren
                    self.current_values[WEEK] = {}
                    self.previous_values[WEEK] = {}
                    # reset Item-Wert alle onchange
                    _reset_items.update(set(self._onchange_weekly_items()))

                # wenn zusätzlich der erste Tage eines Monates ist, werden auch die monatlichen Items berechnet
                if self.shtime.now().day == 1:
                    # item zur Aufgabeliste hinzufügen
                    _todo_items.update(set(self._ondemand_monthly_items()))
                    # cache dict leeren
                    self.current_values[MONTH] = {}
                    self.previous_values[MONTH] = {}
                    # reset Item-Wert alle onchange
                    _reset_items.update(set(self._onchange_monthly_items()))

                    # wenn zusätzlich der erste Monat ist, werden auch die jährlichen Items berechnet
                    if self.shtime.now().month == 1:
                        # item zur Aufgabeliste hinzufügen
                        _todo_items.update(set(self._ondemand_yearly_items()))
                        # cache dict leeren
                        self.current_values[YEAR] = {}
                        self.previous_values[YEAR] = {}
                        # reset Item-Wert alle onchange
                        _reset_items.update(set(self._onchange_yearly_items()))

            # reset der onchange items
            [_item(0, self.get_shortname()) for _item in _reset_items]

            return list(_todo_items)

        if self.debug_log.execute:
            self.logger.debug(f"execute_items called with {option=}")

        suspended_items = self._suspended_items()
        if len(suspended_items) > 0:
            self.logger.info(f"{len(suspended_items)} are suspended and will not be calculated.")

        todo_items = []
        if option == 'startup':
            todo_items = self._startup_items()
        elif option == 'static':
            todo_items = self._static_items()
        elif option == 'info':
            todo_items = self._info_items()
        elif option == 'ondemand':
            todo_items = self._ondemand_items()
        elif option == 'onchange':
            todo_items = self._onchange_items()
        elif option == 'all':
            todo_items = self._all_items()
        elif option == 'due':
            todo_items = _create_due_items()
        elif option == 'item':
            if isinstance(item, str):
                item = self.items.return_item(item)
            if isinstance(item, Item):
                todo_items = [item]

        # remove suspended items
        if option != 'item':
            todo_items = list(set(todo_items) - set(suspended_items))

        # put to queue
        self.logger.info(f"{len(todo_items)} items will be calculated for {option=}.")
        if self.debug_log.execute:
            self.logger.debug(f"Items to be calculated: {todo_items=}")
        [self.item_queue.put(i) for i in todo_items]
        return True

    def work_item_queue(self) -> None:
        """Handles item queue were all to be executed items were be placed in."""

        while self.alive:
            try:
                queue_entry = self.item_queue.get(True, 10)
                self.logger.debug(f"{queue_entry=}")
            except queue.Empty:
                self.active_queue_item = '-'
                pass
            else:
                if isinstance(queue_entry, tuple):
                    item, value = queue_entry
                    self.logger.info(f"# {self.item_queue.qsize() + 1} item(s) to do. || 'onchange' item={item.property.path} with {value=} will be processed.")
                    self.active_queue_item = str(item.property.path)
                    self.handle_onchange(item, value)
                else:
                    self.logger.info(f"# {self.item_queue.qsize() + 1} item(s) to do. || 'on-demand' item={queue_entry.property.path} will be processed.")
                    self.active_queue_item = str(queue_entry.property.path)
                    self.handle_ondemand(queue_entry)

    def work_update_item_delay_deque(self):
        """check if entries in update_item_delay_deque are due, if so put it to working queue"""

        while self.update_item_delay_deque:
            update_time = self.update_item_delay_deque[0][2]
            if update_time <= int(time.time()):
                [item, value, *_] = self.update_item_delay_deque.popleft()
                self.logger.info(f"+ Updated item '{item.property.path}' with value {item()} is now due to be put to queue for processing. {self.item_queue.qsize() + 1} items to do.")
                self.item_queue.put((item, value))
            else:
                self.logger.debug(f"Remaining {len(self.update_item_delay_deque)} items in deque are not due, yet.")
                break

    def handle_ondemand(self, item: Item) -> None:
        """
        Calculate value for requested item, fill cache dicts and set item value.

        :param item: Item for which value will be calculated
        """

        # get parameters
        item_config = self.get_item_config(item)
        if self.debug_log.ondemand:
            self.logger.debug(f"Item={item.property.path} with {item_config=}")
        db_addon_fct = item_config['db_addon_fct']
        database_item = item_config['database_item']
        query_params = item_config.get('query_params')
        if query_params:
            params = dict(query_params)
            params.update({'database_item': database_item})
        else:
            params = {}

        if self.debug_log.ondemand:
            self.logger.debug(f"{db_addon_fct=} will _query_item with {params=}.")

        # handle item starting with 'verbrauch_'
        if db_addon_fct in ALL_VERBRAUCH_ATTRIBUTES:
            result = self._handle_verbrauch(params)

            if result and result < 0:
                self.logger.info(f"Result of item {item.property.path} with {db_addon_fct=} was negative. Something seems to be wrong.")

        # handle 'serie_verbrauch'
        elif db_addon_fct in SERIE_ATTRIBUTES_VERBRAUCH:
            result = self._handle_verbrauch_serie(params)

        # handle item starting with 'zaehlerstand_'
        elif db_addon_fct in ALL_ZAEHLERSTAND_ATTRIBUTES:
            result = self._handle_zaehlerstand(params)

        # handle 'serie_zaehlerstand'
        elif db_addon_fct in SERIE_ATTRIBUTES_ZAEHLERSTAND:
            result = self._handle_zaehlerstand_serie(params)

        # handle 'serie_tagesmittelwert_stunde_30_0d' and 'serie_tagesmittelwert_tag_stunde_30d'
        elif db_addon_fct in SERIE_ATTRIBUTES_MITTEL_H1 + SERIE_ATTRIBUTES_MITTEL_D_H:
            result = self._prepare_value_list(**params)

        # handle TAGESMITTEL_ATTRIBUTES_TIMEFRAME like tagesmitteltemperatur_heute_minus1
        elif db_addon_fct in TAGESMITTEL_ATTRIBUTES_TIMEFRAME:

            params.update({'data_con_func': 'first_hour_avg_day'})
            _result = self._prepare_value_list(**params)

            if isinstance(_result, list):
                result = _result[0][1]
            else:
                result = None

        # handle all functions using temperature sums
        elif db_addon_fct in ALL_SUMME_ATTRIBUTES:
            new_params = {}
            for entry in ('threshold', 'variant', 'result', 'data_con_func'):
                if entry in params:
                    new_params.update({entry: params[entry]})
            result = self._handle_temp_sums(func=db_addon_fct, database_item=database_item, year=params.get('year'), month=params.get('month'), ignore_value_list=params.get('ignore_value_list'),  params=new_params)

        # handle info functions
        elif db_addon_fct == 'info_db_version':
            result = self._get_db_version()

        # handle general functions
        elif db_addon_fct == 'general_oldest_value':
            result = self._get_oldest_value(database_item)

        # handle oldest_log
        elif db_addon_fct == 'general_oldest_log':
            result = self._get_oldest_log(database_item)

        # handle everything else
        else:
            result = self._query_item(**params)[0][1]

        # log result
        if self.debug_log.ondemand:
            self.logger.debug(f"result is {result} for item '{item.property.path}' with '{db_addon_fct=}'")

        if result is None:
            self.logger.info(f"  Result was None; No item value will be set.")
            return

        # set item value and put data into plugin_item_dict
        self.logger.info(f"  Item value for '{item.property.path}' will be set to {result}")
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

            if self.debug_log.onchange:
                self.logger.debug(f"'minmax' Item={updated_item.property.path} with {func=} and {timeframe=} detected. Check for update of cache_dicts {cache_dict=} and item value.")

            # make sure, that database item is in cache dict
            if database_item not in cache_dict:
                cache_dict[database_item] = {}

            # get _recent_value; if not already cached, create cache
            cached_value = cache_dict[database_item].get(func)
            if cached_value is None:
                if self.debug_log.onchange:
                    self.logger.debug(f"{func} value for {timeframe=} of item={updated_item.property.path} not in cache dict. Query database.")

                query_params = {'func': func, 'database_item': database_item, 'timeframe': timeframe, 'start': 0, 'end': 0, 'ignore_value_list': ignore_value_list, 'use_oldest_entry': True}
                cached_value = self._query_item(**query_params)[0][1]

                if cached_value is None:
                    if self.debug_log.onchange:
                        self.logger.debug(f"{func} value for {timeframe=} of item={updated_item.property.path} not available in database. Abort calculation.")
                    return

                init = True

            # if value not given
            if init:
                if self.debug_log.onchange:
                    self.logger.debug(f"initial {func} value for {timeframe=} of item={item.property.path} with will be set to {cached_value}")
                cache_dict[database_item][func] = cached_value
                return cached_value

            # check value for update of cache dict min
            elif func == 'min' and value < cached_value:
                if self.debug_log.onchange:
                    self.logger.debug(f"new value={value} lower then current min_value={cached_value} for {timeframe=}. cache_dict will be updated")
                cache_dict[database_item][func] = value
                return value

            # check value for update of cache dict max
            elif func == 'max' and value > cached_value:
                if self.debug_log.onchange:
                    self.logger.debug(f"new value={value} higher then current max_value={cached_value} for {timeframe=}. cache_dict will be updated")
                cache_dict[database_item][func] = value
                return value

            # no impact
            if self.debug_log.onchange:
                self.logger.debug(f"new value={value} will not change max/min for period={timeframe}.")
            return None

        def handle_verbrauch():
            cache_dict = self.previous_values[timeframe]

            if self.debug_log.onchange:
                self.logger.debug(f"'verbrauch' item {updated_item.property.path} with {func=} and {value=} detected. Check for update of cache_dicts {cache_dict=} and item value.")

            # get _cached_value for value at end of last period; if not already cached, create cache
            cached_value = cache_dict.get(database_item)
            if cached_value is None:
                if self.debug_log.onchange:
                    self.logger.debug(f"Most recent value for last {timeframe=} of item={updated_item.property.path} not in cache dict. Query database.")

                # try to get most recent value of last timeframe, assuming that this is the value at end of last timeframe
                query_params = {'database_item': database_item, 'timeframe': timeframe, 'start': 1, 'end': 1, 'ignore_value_list': ignore_value_list, 'use_oldest_entry': True}
                cached_value = self._handle_zaehlerstand(query_params)

                if cached_value is None:
                    self.logger.info(f"Most recent value for last {timeframe} of item={updated_item.property.path} not available in database. Abort calculation.")
                    return

                cache_dict[database_item] = cached_value
                if self.debug_log.onchange:
                    self.logger.debug(f"Value for Item={updated_item.property.path} at end of last {timeframe} not in cache dict. Value={cached_value} has been added.")

            # calculate value, set item value, put data into plugin_item_dict
            _new_value = value - cached_value
            return _new_value if isinstance(_new_value, int) else round(_new_value, 2)

        def handle_tagesmittel():
            result = self._prepare_value_list(database_item=database_item, timeframe='day', start=0, end=0, ignore_value_list=ignore_value_list, data_con_func='first_hour')

            if isinstance(result, list):
                return result[0][1]

        if self.debug_log.onchange:
            self.logger.debug(f"called with updated_item={updated_item.property.path} and value={value}.")

        relevant_item_list = set(self.get_item_list('database_item', updated_item)) & set(self.get_item_list('on', 'change'))

        if self.debug_log.onchange:
            self.logger.debug(f"Following items where identified for update: {relevant_item_list}.")

        for item in relevant_item_list:
            item_config = self.get_item_config(item)
            if self.debug_log.onchange:
                self.logger.debug(f"Item={item.property.path} with {item_config=}")
            db_addon_fct = item_config['db_addon_fct']
            database_item = item_config['database_item']
            timeframe = item_config['query_params']['timeframe']
            func = item_config['query_params'].get('func')
            ignore_value_list = item_config['query_params'].get('ignore_value_list')
            new_value = None

            # handle all non on_change functions
            if db_addon_fct not in ONCHANGE_ATTRIBUTES:
                if self.debug_log.onchange:
                    self.logger.debug(f"non onchange function detected. Skip update.")
                continue

            # handle minmax onchange items tagesmitteltemperatur_heute, minmax_heute_avg
            if db_addon_fct in TAGESMITTEL_ATTRIBUTES_ONCHANGE:
                new_value = handle_tagesmittel()

            # handle minmax onchange items like minmax_heute_max, minmax_heute_min, minmax_woche_max, minmax_woche_min.....
            elif db_addon_fct.startswith('minmax'):
                new_value = handle_minmax()

            # handle verbrauch onchange items ending with heute, woche, monat, jahr
            elif db_addon_fct.startswith('verbrauch'):
                new_value = handle_verbrauch()

            if new_value is None:
                continue

            self.logger.info(f"  Item value for '{item.property.path}' with func={func} will be set to {new_value}")
            item_config = self.get_item_config(item)
            item_config.update({'value': new_value})
            item(new_value, self.get_shortname())

    def _update_database_items(self) -> None:
        """Turns given as database_item path into database_items"""
        for item in self._database_item_path_items():
            item_config = self.get_item_config(item)
            database_item_path = item_config.get('database_item')
            database_item = self.items.return_item(database_item_path)

            if database_item is None:
                self.logger.warning(f"Database-Item for Item with config item path for Database-Item {database_item_path!r} not found. Item '{item.property.path}' will be removed from plugin.")
                self.remove_item(item)
            else:
                item_config.update({'database_item': database_item})
                db_addon_startup = bool(self.get_iattr_value(database_item.conf, 'db_addon_startup'))
                if db_addon_startup:
                    item_config.update({'startup': True})

    def _suspend_item_calculation(self, item: Union[str, Item], suspended: bool = False) -> Union[bool, None]:
        """suspend calculation od dedicated item"""
        if isinstance(item, str):
            item = self.items.return_item(item)

        if not isinstance(item, Item):
            return

        item_config = self.get_item_config(item)
        item_config['suspended'] = suspended
        return suspended

    def _create_list_of_relevant_database_items(self):
        """creates list of all relevant database items for further reference"""
        _database_items = set()
        for item in self.get_item_list('database_item'):
            item_config = self.get_item_config(item)
            database_item = item_config.get('database_item')
            if database_item is not None:
                _database_items.add(database_item)
        self.database_item_list = list(_database_items)

    @property
    def log_level(self) -> int:
        return self.logger.getEffectiveLevel()

    def queue_backlog(self) -> int:
        return self.item_queue.qsize()

    def db_version(self) -> str:
        return self._get_db_version()

    def _startup_items(self) -> list:
        return self.get_item_list('startup', True)

    def _onchange_items(self) -> list:
        return self.get_item_list('on', 'change')

    def _onchange_hourly_items(self) -> list:
        return list(set(self._onchange_items()) & set(self._hourly_items()))

    def _onchange_daily_items(self) -> list:
        return list(set(self._onchange_items()) & set(self._daily_items()))

    def _onchange_weekly_items(self) -> list:
        return list(set(self._onchange_items()) & set(self._weekly_items()))

    def _onchange_monthly_items(self) -> list:
        return list(set(self._onchange_items()) & set(self._monthly_items()))

    def _onchange_yearly_items(self) -> list:
        return list(set(self._onchange_items()) & set(self._yearly_items()))

    def _ondemand_items(self) -> list:
        return self.get_item_list('on', 'demand')

    def _ondemand_hourly_items(self) -> list:
        return list(set(self._ondemand_items()) & set(self._hourly_items()))

    def _ondemand_daily_items(self) -> list:
        return list(set(self._ondemand_items()) & set(self._daily_items()))

    def _ondemand_weekly_items(self) -> list:
        return list(set(self._ondemand_items()) & set(self._weekly_items()))

    def _ondemand_monthly_items(self) -> list:
        return list(set(self._ondemand_items()) & set(self._monthly_items()))

    def _ondemand_yearly_items(self) -> list:
        return list(set(self._ondemand_items()) & set(self._yearly_items()))

    def _hourly_items(self) -> list:
        return self.get_item_list('cycle', 'hourly')

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
        return self.database_item_list

    def _database_item_path_items(self) -> list:
        return self.get_item_list('database_item_path', True)

    def _suspended_items(self) -> list:
        return self.get_item_list('suspended', True)

    def _all_items(self) -> list:
        # return self._ondemand_items() + self._onchange_items() + self._static_items() + self._admin_items() + self._info_items()
        return self.get_item_list('db_addon', 'function')

    #########################################
    #   Public functions / Using item_path
    #########################################

    def gruenlandtemperatursumme(self, item_path: str, year: Union[int, str] = None, ignore_value_list: list = None) -> Union[int, None]:
        """
        Query database for gruenlandtemperatursumme for given year or year
        https://de.wikipedia.org/wiki/Gr%C3%BCnlandtemperatursumme

        Beim Grünland wird die Wärmesumme nach Ernst und Loeper benutzt, um den Vegetationsbeginn und somit den Termin von Duengemaßnahmen zu bestimmen.
        Dabei erfolgt die Aufsummierung der Tagesmitteltemperaturen über 0 °C, wobei der Januar mit 0.5 und der Februar mit 0.75 gewichtet wird.
        Bei einer Wärmesumme von 200 Grad ist eine Düngung angesagt.

        :param item_path: item object or item_id for which the query should be done
        :param year: year the gruenlandtemperatursumme should be calculated for
        :param ignore_value_list: list of comparison operators for val_num, which will be applied during query
        :return: gruenlandtemperatursumme
        """

        item = self.items.return_item(item_path)
        if item:
            return self._handle_temp_sums(func='gruendlandtempsumme', database_item=item, year=year, ignore_value_list=ignore_value_list)

    def waermesumme(self, item_path: str, year: Union[int, str] = None, month: Union[int, str] = None, ignore_value_list: list = None, threshold: int = 0) -> Union[int, None]:
        """
        Query database for waermesumme for given year or year/month
        https://de.wikipedia.org/wiki/W%C3%A4rmesumme

        :param item_path: item object or item_id for which the query should be done
        :param year: year the waermesumme should be calculated for
        :param month: month the waermesumme should be calculated for
        :param ignore_value_list: list of comparison operators for val_num, which will be applied during query
        :param threshold: threshold for temperature
        :return: waermesumme
        """

        item = self.items.return_item(item_path)
        if item:
            return self._handle_temp_sums(func='waermesumme', database_item=item, year=year, month=month, ignore_value_list=ignore_value_list, params={'threshold': threshold})

    def kaeltesumme(self, item_path: str, year: Union[int, str] = None, month: Union[int, str] = None, ignore_value_list: list = None) -> Union[int, None]:
        """
        Query database for kaeltesumme for given year or year/month
        https://de.wikipedia.org/wiki/K%C3%A4ltesumme

        :param item_path: item object or item_id for which the query should be done
        :param year: year the kaeltesumme should be calculated for
        :param month: month the kaeltesumme should be calculated for
        :param ignore_value_list: list of comparison operators for val_num, which will be applied during query
        :return: kaeltesumme
        """

        item = self.items.return_item(item_path)
        if item:
            return self._handle_temp_sums(func='kaeltesumme', database_item=item, year=year, month=month, ignore_value_list=ignore_value_list)

    def wachstumsgradtage(self, item_path: str, year: Union[int, str] = None, ignore_value_list: list = None, variant: int = 0, threshold: int = 10) -> Union[int, None]:
        """
        Query database for wachstumsgradtage
        https://de.wikipedia.org/wiki/Wachstumsgradtag

        :param item_path: item object or item_id for which the query should be done
        :param year: year the wachstumsgradtage should be calculated for
        :param ignore_value_list: list of comparison operators for val_num, which will be applied during query
        :param variant: variant to be used
        :param threshold: Temperature in °C as threshold: Ein Tage mit einer Tagesdurchschnittstemperatur oberhalb des Schwellenwertes gilt als Wachstumsgradtag
        :return: wachstumsgradtage
        """

        item = self.items.return_item(item_path)
        if item:
            return self._handle_temp_sums(func='wachstumsgradtage', database_item=item, year=year, ignore_value_list=ignore_value_list, params={'threshold': threshold, 'variant': variant})

    def temperaturserie(self, item_path: str, year: Union[int, str] = None, ignore_value_list: list = None, data_con_func: str = 'first_hour_avg_day') -> Union[list, None]:
        """
        Query database for temperaturserie

        :param item_path: item object or item_id for which the query should be done
        :param year: year the wachstumsgradtage should be calculated for
        :param ignore_value_list: list of comparison operators for val_num, which will be applied during query
        :param data_con_func: data concentration function
        :return: temperature series
        """

        item = self.items.return_item(item_path)
        if item:
            return self._handle_temp_sums(func='temperaturserie', database_item=item, year=year, ignore_value_list=ignore_value_list, params={'data_con_func': data_con_func})

    def query_item(self, func: str, item_path: str, timeframe: str, start: int = None, end: int = 0, group: str = None, group2: str = None, ignore_value_list=None) -> list:
        """
        Query database, format response and return it

        :param func: function, defined in query_item method to be used at query
        :param item_path: item str or item_id for which the query should be done
        :param timeframe: time increment für definition of start, end, count (day, week, month, year)
        :param start: start of timeframe (oldest) for query given in x time increments (default = None, meaning complete database)
        :param end: end of timeframe (newest) for query given in x time increments (default = 0, meaning today, end of last week, end of last month, end of last year)
        :param group: first grouping parameter (default = None, possible values: day, week, month, year)
        :param group2: second grouping parameter (default = None, possible values: day, week, month, year)
        :param ignore_value_list: list of comparison operators for val_num, which will be applied during query

        :return: formatted query response
        """

        item = self.items.return_item(item_path)
        if item is None:
            return []

        return self._query_item(func, item, timeframe, start, end, group, group2, ignore_value_list)

    def fetch_log(self, func: str, item_path: str, timeframe: str, start: int = None, end: int = 0, count: int = None, group: str = None, group2: str = None, ignore_value_list=None) -> list:
        """
        Query database, format response and return it

        :param func: sql function to be used at query
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
            start = end + count

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

    ##############################################
    #   Calculation methods / Using Item Object
    ##############################################

    def _handle_verbrauch(self, query_params: dict) -> Union[None, float]:
        """
        Ermittlung des Verbrauches innerhalb eines Zeitraumes

        Die Vorgehensweise ist:
            - Endwert / Endzählerstand: Abfrage des letzten Eintrages (Zählerstandes) im Zeitraum
                - Ergibt diese Abfrage keinen Wert, gab eines keinen Eintrag im Zeitraum in der DB, es wurde also nichts verbraucht -> Rückgabe von 0
            - Startwert / Anfangszählerstand: Abfrage des letzten Eintrages (Zählerstandes) vor dem Abfragezeitraum
                - Ergibt diese Abfrage einen Wert, entspricht dieser dem Anfangszählerstand
                - Ergibt diese Abfrage keinen Wert, Anfangszählerstand = 0
        """

        # define start, end for verbrauch_jahreszeitraum_timedelta
        if 'timedelta' in query_params:
            timedelta = query_params.pop('timedelta')
            today = self.shtime.today(offset=0)
            start_date = self.shtime.beginning_of_year(offset=-timedelta)
            end_date = today - relativedelta(years=timedelta)
            start = (today - start_date).days
            end = (today - end_date).days
        else:
            start = query_params['start']
            end = query_params['end']

        # calculate consumption
        if self.debug_log.prepare:
            self.logger.debug(f"called with {query_params=}")

        # get value for end and check it;
        query_params.update({'func': 'last', 'start': start, 'end': end})
        value_end = self._query_item(**query_params)[0][1]

        if self.debug_log.prepare:
            self.logger.debug(f"{value_end=}")

        if value_end is None or value_end == 0:
            return value_end

        # get value for start and check it;
        query_params.update({'func': 'next', 'start': start, 'end': start})
        value_start = self._query_item(**query_params)[0][1]
        if self.debug_log.prepare:
            self.logger.debug(f"{value_start=}")

        if not value_start:
            value_start = 0
            if self.debug_log.prepare:
                self.logger.debug(f"No start value available. Will be set to 0 as default")

        # calculate consumption
        consumption = value_end - value_start

        if isinstance(consumption, float):
            if consumption.is_integer():
                consumption = int(consumption)
            else:
                consumption = round(consumption, 2)

        if self.debug_log.prepare:
            self.logger.debug(f"{consumption=}")

        return consumption

    def _handle_verbrauch_serie(self, query_params: dict) -> list:
        """Ermittlung einer Serie von Verbräuchen in einem Zeitraum für x Zeiträume"""

        series = []
        database_item = query_params['database_item']
        timeframe = query_params['timeframe']
        start = query_params['start']

        for i in range(start, 1, -1):
            value = self._handle_verbrauch({'database_item': database_item, 'timeframe': timeframe, 'start': i + 1, 'end': i})
            ts_start, ts_end = self._get_start_end_as_timestamp(timeframe, i, i + 1)
            series.append([ts_end, value])

        return series

    def _handle_verbrauch_serie_new(self, query_params: dict) -> list:
        """Ermittlung einer Serie von Verbräuchen in einem Zeitraum für x Zeiträume"""

        # ToDo: Test method

        query_params.update({'data_con_func': 'max_day', 'cache': True})
        raw_data = self._prepare_value_list(**query_params)

        new_dict = {k[0]: k[1:][0] for k in raw_data}
        consumption_list = []
        start_ts = min(new_dict)
        start_val = new_dict[start_ts]

        for i in range(query_params['start']):
            end_ts = int(start_ts + 24 * 60 * 60)
            end_val = new_dict.get(end_ts, None)
            if not end_val:
                end_val = start_val
            consumption_list.append([end_ts, round((end_val - start_val), 2)])
            start_ts = end_ts
            start_val = end_val

        return consumption_list

    def _handle_zaehlerstand(self, query_params: dict) -> Union[float, int, None]:
        """
        Ermittlung des Zählerstandes zu Beginn des Zeitraumes

        Die Vorgehensweise ist:
            - Abfrage des letzten Eintrages vor dem Beginn des Zeitraums
        """

        if self.debug_log.prepare:
            self.logger.debug(f"called with {query_params=}")

        # get last value of timeframe
        query_params.update({'func': 'next'})
        last_value = self._query_item(**query_params)[0][1]
        if self.debug_log.prepare:
            self.logger.debug(f"{last_value=}")

        if last_value is None:
            self.logger.info('No entry in database found. Maybe item was just created. Setting last_value to 0.')
            last_value = 0

        if isinstance(last_value, float):
            if last_value.is_integer():
                last_value = int(last_value)
            else:
                last_value = round(last_value, 2)

        return last_value

    def _handle_zaehlerstand_serie(self, query_params: dict) -> list:
        """Ermittlung einer Serie von Zählerständen zum Ende eines Zeitraumes für x Zeiträume"""

        series = []
        database_item = query_params['database_item']
        timeframe = query_params['timeframe']
        start = query_params['start']

        for i in range(start, 1, -1):
            value = self._handle_zaehlerstand({'database_item': database_item, 'timeframe': timeframe, 'start': i, 'end': i})
            ts_start = self._get_start_end_as_timestamp(timeframe, i, i)[0]
            series.append([ts_start, value])

        return series

    def _handle_zaehlerstand_serie_new(self, query_params: dict) -> list:
        """Ermittlung einer Serie von Zählerständen zum Ende eines Zeitraumes für x Zeiträume"""

        # ToDo: Test method

        query_params.update({'data_con_func': 'max_day', 'cache': True})
        raw_data = self._prepare_value_list(**query_params)

        new_dict = {k[0]: k[1:][0] for k in raw_data}
        zaehler_list = []
        start_ts = min(new_dict)
        start_val = new_dict[start_ts]

        for i in range(query_params['start']):
            end_ts = int(start_ts + 24 * 60 * 60)
            end_val = new_dict.get(end_ts, None)
            if not end_val:
                end_val = start_val
            zaehler_list.append([end_ts, round(end_val, 2)])
            start_ts = end_ts
            start_val = end_val

        return zaehler_list

    def _handle_temp_sums(self, func: str, database_item: Item, year: Union[int, str] = None, month: Union[int, str] = None, ignore_value_list: list = None, params: dict = None) -> Union[list, None]:
        """
        Calculates diverse temperature sums and day counts
        
        :param func: defines which temperature sum or count should be calculated
        :param database_item: item object or item_id for which the query should be done
        :param year: year the temperature should be calculated for
        :param month: month the temperature should be calculated for
        :param params: params to be used for executing function (see below)
        :return: temperature sum or day count
        
        - kaeltesumme: Kältesumme nach https://de.wikipedia.org/wiki/K%C3%A4ltesumme
        - waermesumme: Wärmesumme https://de.wikipedia.org/wiki/W%C3%A4rmesumme
                params: threshold
        - gruenlandtempsumme: Grünlandtemperatursumme: https://de.wikipedia.org/wiki/Gr%C3%BCnlandtemperatursumme
        - wachstumsgradtage: Wachstumsgradtage https://de.wikipedia.org/wiki/Wachstumsgradtag
                params: threshold, variant, result 
        - temperaturserie: Temperaturserie provide list of lists having timestamp and temperature(s) per day
                params: data_con_func
        - wuestentage: Wüstentage, Anzahl der Tage  mit Tmax ≥ 35 °C
        - heisse_tage: Heiße Tage, Anzahl der Tage  mit Tmax ≥ 30 °C
        - tropennaechte: Tropennächte, Anzahl der Tage  mit Tmin ≥ 20 °C
        - sommertage: Sommertage, Anzahl der Tage  mit Tmax ≥ 25 °C
        - heiztage: Heiztage, Anzahl der Tage  mit Tmed < 15 °C / 12 °C
        - vegetationstage: Vegetationstage, Anzahl der Tage  mit Tmed ≥ 5 °C
        - frosttage: Frosttage, Anzahl der Tage mit Tmin < 0 °C
        - eistage: Eistage, Anzahl der Tage  mit Tmax < 0 °C
        """

        timeframe = {1: ((0, 9, 21), (1, 3, 22)),
                     2: ((0, 1, 1), (0, 9, 21)),
                     3: ((0, 1, 1), (0, 12, 31))}

        defaults = {'kaeltesumme':         {'start_end': timeframe[1], 'data_con_func': 'first_hour_avg_day'},
                    'waermesumme':         {'start_end': timeframe[2], 'data_con_func': 'first_hour_avg_day'},
                    'gruenlandtempsumme':  {'start_end': timeframe[2], 'data_con_func': 'first_hour_avg_day'},
                    'wachstumsgradtage':   {'start_end': timeframe[2], 'data_con_func': 'minmax_day'},
                    'temperaturserie':     {'start_end': timeframe[2], 'data_con_func': params.get('data_con_func', 'avg_hour')},
                    'wuestentage':         {'start_end': timeframe[3], 'data_con_func': 'minmax_day'},
                    'heisse_tage':         {'start_end': timeframe[3], 'data_con_func': 'minmax_day'},
                    'tropennaechte':       {'start_end': timeframe[3], 'data_con_func': 'minmax_day'},
                    'sommertage':          {'start_end': timeframe[3], 'data_con_func': 'minmax_day'},
                    'heiztage':            {'start_end': timeframe[3], 'data_con_func': 'first_hour_avg_day'},
                    'vegetationstage':     {'start_end': timeframe[3], 'data_con_func': 'first_hour_avg_day'},
                    'frosttage':           {'start_end': timeframe[3], 'data_con_func': 'minmax_day'},
                    'eistage':             {'start_end': timeframe[3], 'data_con_func': 'minmax_day'},
                    }

        if not params:
            params = dict()

        def kaeltesumme() -> float:
            """Berechnung der Kältesumme durch Akkumulieren aller negativen Tagesdurchschnittstemperaturen im Abfragezeitraum

            :return: value of kaeltesumme
            """

            # akkumulieren alle Werte, kleiner 0
            ks = 0
            for entry in raw_data:
                if entry[1] < 0:
                    ks -= entry[1]
            return int(round(ks, 0))

        def waermesumme() -> float:
            """Berechnung der Wärmesumme durch Akkumulieren aller Tagesdurchschnittstemperaturen im Abfragezeitraum, die größer/gleich dem Schwellenwert sind

            :return: value of waermesumme
            """
        
            # get threshold and set to min 0
            threshold = params.get('threshold', 10)
            threshold = max(0, threshold)

            # akkumulieren alle Werte, größer/gleich Schwellenwert
            ws = 0
            for entry in raw_data:
                if entry[1] >= threshold:
                    ws += entry[1]
            return int(round(ws, 0))

        def gruenlandtempsumme() -> float:
            """Berechnung der Grünlandtemperatursumme durch Akkumulieren alle positiven Tagesmitteltemperaturen, im Januar gewichtet mit 50%, im Februar mit 75%

            :return: value of gruenlandtempsumme
            """
            
            gts = 0
            for entry in raw_data:
                timestamp, value = entry
                if value > 0:
                    dt = self._timestamp_to_datetime(timestamp / 1000)
                    if dt.month == 1:
                        value = value * 0.5
                    elif dt.month == 2:
                        value = value * 0.75
                    gts += value
            return int(round(gts, 0))

        def wachstumsgradtage() -> Union[list, float, None]:
            """Berechnet die Wachstumsgradtage noch 2 möglichen Varianten und gibt entweder den Gesamtwert oder eine Liste mit kumulierten Werten pro Tag zurück
                
                variant 0: Berechnungsmethode "Berechnung des einfachen Durchschnitts" mit Vergleich des Durchschnitts der täglichen Minimal- und Maximaltemperatur mit Schwellenwert.
                           Maximaltemperaturen werden bei 30 °C gekappt.
                variant 1: Berechnungsmethode "modifizierte Berechnung des einfachen Durchschnitts" mit Vergleich des Durchschnitts der täglichen Minimal- und Maximaltemperatur mit Schwellenwert.
                           Vor der Berechnung des Durchschnittes wird jede Temperatur, die den Schwellenwert unterschreitet, auf den Schwellenwert geändert.
                           Maximaltemperaturen werden bei 30 °C gekappt.

                result 'value': Rückgabe als Gesamtwert
                result 'series: Rückgabe als Liste mit kumulierten Werten pro Tag zurück [['timestamp1', 'kumulierter Wert am Ende von Tag1'], ['timestamp2', ''kumulierter Wert am Ende von Tag2', [...], ...]
            """

            # define defaults
            wgte = 0
            wgte_list = []
            upper_limit = 30
            
            # get threshold and set to min 0
            threshold = params.get('threshold', 10)
            threshold = max(0, threshold)

            # get variant
            variant = params.get('variant', 0)
            
            # get result type
            result = params.get('result', 'value')

            # variant handling
            if variant == 0:
                self.logger.info(f"Calculate 'Wachstumsgradtage' according to 'Berechnung des einfachen Durchschnitts'.")
                min_val_c = 'min_val'
            elif variant == 1:
                self.logger.info(f"Calculate 'Wachstumsgradtage' according to 'Modifizierte Berechnung des einfachen Durchschnitts'.")
                min_val_c = 'max(threshold, min_val)'
            else:
                self.logger.warning(f"Requested variant of 'Wachstumsgradtage' not defined. Aborting...")
                return

            # accumulate values
            for entry in raw_data:
                timestamp, min_val, max_val = entry
                wgt = ((eval(min_val_c) + min(upper_limit, max_val)) / 2 ) - threshold
                if wgt > 0:
                    wgte += wgt
                wgte_list.append([timestamp, int(round(wgte, 0))])

            # return result
            return wgte_list if result == 'series' else int(round(wgte, 0))

        def temperaturserie() -> list:
            """provide list of lists having timestamp and temperature(s) per day"""

            return raw_data

        def wuestentage() -> int:
            """provide number day counted as Wüstentag with Tmax ≥ 35°C"""
            return _count(operator.ge, 'max', 35)

        def heisse_tage() -> int:
            """provide number day counted as heißer Tag with Tmax ≥ 30°C"""
            return _count(operator.ge, 'max', 30)

        def tropennaechte() -> int:
            """provide number day counted as Tropnenacht with Tmin ≥ 20 °C"""
            return _count(operator.ge, 'min', 20)

        def sommertage() -> int:
            """provide number day counted as Sommertag with Tmax ≥ 25°C"""
            return _count(operator.ge, 'max', 25)

        def frosttage() -> int:
            """provide number day counted as Frosttag with Tmin < 0°C"""
            return _count(operator.lt, 'min', 0)

        def eistage() -> int:
            """provide number day counted as Frosttag with Tmax < 0°C"""
            return _count(operator.lt, 'max', 0)

        def heiztage() -> int:
            """provide number day counted as Frosttag with Tavg < 15°C"""
            return _count(operator.lt, 'avg', 15)

        def vegetationstage() -> int:
            """provide number day counted as Frosttag with Tavg > 5°C"""
            return _count(operator.ge, 'avg', 5)

        def _count(op, minmax: str, limit: int) -> int:
            count = 0
            for entry in raw_data:
                value = entry[2] if minmax == 'max' else entry[1]
                if op(value, limit):
                    count += 1
            return count

        self.logger.debug(f"{func=}, {database_item=}, {year=}, {month=}, {params=}")

        # check if func is defined
        if func not in defaults:
            self.logger.warning(f"_handle_temp_sums called with {func=}, which is not defined. Aborting...")
            return

        # get datetime of today
        today = self.shtime.today(offset=0)

        # define year or check validity of given year
        if not year or year == 'current':
            year = today.year
        elif not self._valid_year(year):
            self.logger.error(f"Year for item={database_item.property.path} was {year}. This is not a valid year. Aborting...")
            return
        if func == 'kaeltesumme' and 1 <= today.month <= 9:
            year -= 1

        # define start_date, end_date
        if month is None:
            ((s_y, s_m, s_d), (e_y, e_m, e_d)) = defaults.get(func, {}).get('start_end', timeframe[3])
            start_date = datetime.date(int(year) + s_y, s_m, s_d)
            end_date = datetime.date(int(year) + e_y, e_m, e_d)
        elif self._valid_month(month):
            start_date = datetime.date(int(year), int(month), 1)
            end_date = start_date + relativedelta(months=+1) - datetime.timedelta(days=1)
        else:
            self.logger.error(f"Month for item={database_item.property.path} was {month}. This is not a valid month. Aborting...")
            return

        # check start_date
        if start_date > today:
            self.logger.info(f"Start time for query of item={database_item.property.path} is in future. Aborting...")
            return

        # define start / end
        start = (today - start_date).days
        end = (today - end_date).days if end_date < today else 0

        # check end
        if start < end:
            self.logger.error(f"End time for query of item={database_item.property.path} is before start time. Aborting...")
            return
            
        # get raw data as list
        if self.debug_log.prepare:
            self.logger.debug("try to get raw data")
        data_con_func = defaults.get(func, {}).get('data_con_func')
        raw_data = self._prepare_value_list(database_item=database_item, timeframe='day', start=start, end=end, ignore_value_list=ignore_value_list, data_con_func=data_con_func, cache=True)
        if self.debug_log.prepare:
            self.logger.debug(f"raw_value_list={raw_data}")

        # return None, if now raw data
        if raw_data is None or not isinstance(raw_data, list):
            return

        # calculate value and return it
        return locals()[func]()

    def _prepare_value_list(self, database_item: Item, timeframe: str, start: int, end: int = 0, ignore_value_list=None, data_con_func: str = 'avg_day', cache: bool = False) -> Union[list, None]:
        """
        returns list of lists having timestamp and values(s) per day / hour in format of regular database query

        :param database_item:       item object or item_id for which the query should be done
        :param timeframe:           timeframe for query
        :param start:               increments for timeframe from now to start
        :param end:                 increments for timeframe from now to end
        :param ignore_value_list:   list of comparison operators for val_num, which will be applied during query
        :param data_con_func:       data concentration function
                                    - avg_day: determines average value per day of values within plugin
                                    - avg_hour: determines average value per hour of values within plugin
                                    - first_day: determines first value per day of values within plugin
                                    - first_hour: determines first value per hour of values within plugin
                                    - minmax_day: determines min and max value per day of values within plugin
                                    - minmax_hour: determines min and max value per hour of values within plugin
                                    - min_day: determines min value per day of values within plugin
                                    - max_hour: determines max value per hour of values within plugin
                                    - min_day: determines min value per day of values within plugin
                                    - max_hour: determines max value per hour of values within plugin
                                    - first_hour_avg_day: 2-step concentration: 1) concentrate values within an hour by using first value 2) concentrate values by average for first value of each hour
        :return:                    list of list with [timestamp, value]
        """

        def _group_value_by_datetime_block(block: str) -> dict:
            """
            create dict of datetimes (per day or hour) and values based on database query result in format {'datetime1': [values]}, 'datetime1': [values], ..., 'datetimex': [values]}
            :param block:   defined the increment of datetime, default is min, further possible is 'day' and 'hour'
            """

            _value_dict = {}
            for _entry in raw_data:
                ts = _entry[0]
                if len(str(ts)) > 10:
                    ts = ts / 1000
                dt = self._timestamp_to_datetime(ts)
                dt = dt.replace(second=0, microsecond=0, tzinfo=None)
                if block == 'hour':
                    dt = dt.replace(minute=0)
                if block == 'day':
                    dt = dt.replace(minute=0, hour=0)
                if dt not in _value_dict:
                    _value_dict[dt] = []
                _value_dict[dt].append(_entry[1])
            return dict(sorted(_value_dict.items()))

        def _concentrate_values(option: str) -> list:
            """
            Create list of list with [[timestamp1, value1], [timestamp2, value2], ...] based on value_dict in format of database query result
            values given in the list will be concentrated as per given option

            :param option       defines option to be used to determine the concentrated values, possible are 'first', 'avg', minmax
                                    'first' will take first entry of list per datetime to get as close to value at full hour as possible
                                    'avg' will use the calculated average of values in list per datetime
                                    'minmax' will get min and max value of list per datetime
                                    'min' will get the min value of list per datetime
                                    'max' will get the min value of list per datetime
            """

            _value_list = []
            # create nested list with timestamp, avg_value or minmax per hour/day
            for entry in value_dict:
                _timestamp = self._datetime_to_timestamp(entry)
                if option == 'first':
                    _value_list.append([_timestamp, value_dict[entry][0]])
                elif option == 'avg':
                    _value_list.append([_timestamp, round(sum(value_dict[entry]) / len(value_dict[entry]), 2)])
                elif option == 'minmax':
                    _value_list.append([_timestamp, min(value_dict[entry]), max(value_dict[entry])])
                elif option == 'max':
                    _value_list.append([_timestamp, max(value_dict[entry])])
                elif option == 'min':
                    _value_list.append([_timestamp, min(value_dict[entry])])
            return _value_list

        if self.debug_log.prepare:
            self.logger.debug(f'called with database_item={database_item.property.path}, {timeframe=}, {start=}, {end=}, {ignore_value_list=}, {data_con_func=}')

        if data_con_func not in ('min', 'max', 'avg', 'minmax', 'first', 'avg_day', 'avg_hour', 'minmax_day', 'minmax_hour', 'first_day', 'first_hour', 'first_hour_avg_day', 'avg_hour_avg_day', 'min_hour', 'min_day', 'max_hour', 'max_day'):
            self.logger.warning(f"defined {data_con_func=} for _prepare_value_list unknown. Need to be 'avg', 'minmax', 'first', 'avg_day', 'avg_hour', 'minmax_day', 'minmax_hour', 'first_day','first_hour', 'first_hour_avg_day' or 'avg_hour_avg_day'. Aborting...")
            return

        # define defaults
        _data_con1 = _block1 = _data_con2 = _block2 = result = None

        # check data_con_func
        data_con_func_list = data_con_func.split('_')
        if len(data_con_func_list) == 1:
            _data_con1 = data_con_func_list
            _block = 'hour'
        elif len(data_con_func_list) == 2:
            _data_con1, _block1 = data_con_func_list
        elif len(data_con_func_list) == 4:
            _data_con1, _block1, _data_con2, _block2 = data_con_func_list

        # define quere params
        _query_params = {'func': 'raw', 'database_item': database_item, 'timeframe': timeframe, 'start': start, 'end': end, 'ignore_value_list': ignore_value_list}

        # get raw data from database
        if not cache or str(_query_params) not in self.value_list_raw_data:
            raw_data = self._query_item(**_query_params)

            if raw_data == [[None, None]] or raw_data == [[0, 0]]:
                self.logger.info(f"no valid data from database query for item={database_item.property.path} received during _prepare_value_list. Aborting...")
                return

            if cache:
                self.logger.debug(f"raw_data for {_query_params=} put to cache.")
                self.value_list_raw_data[str(_query_params)] = raw_data
        else:
            self.logger.debug(f"raw_data for {_query_params=} read from cache.")
            raw_data = self.value_list_raw_data[str(_query_params)]

        if _data_con1 and _block1:
            # create nested dict with values
            value_dict = _group_value_by_datetime_block(block=_block1)
            if self.debug_log.prepare:
                self.logger.debug(f"{_block1=}, {value_dict=}")

            # return value list
            result = _concentrate_values(option=_data_con1)
            if self.debug_log.prepare:
                self.logger.debug(f"{_data_con1=}, {result=}")

        if _data_con2 and _block2:
            # create nested dict with values
            value_dict = _group_value_by_datetime_block(block=_block2)
            if self.debug_log.prepare:
                self.logger.debug(f"{_block2=}, {value_dict=}")

            # return value list
            result = _concentrate_values(option=_data_con2)
            if self.debug_log.prepare:
                self.logger.debug(f"{_data_con2=}, {result=}")

        return result

    ####################
    #   Support stuff
    ####################

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

    def _check_db_connection_setting(self) -> None:
        """
        Check Setting of mysql connection for stable use.
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

    def _get_oldest_log(self, item: Item) -> Union[None, int]:
        """
        Get timestamp of the oldest entry of item from cache dict or get value from db and put it to cache dict

        :param item: Item, for which query should be done
        :return: timestamp of the oldest log
        """

        oldest_log = self.item_cache.get(item, {}).get('oldest_log')

        if oldest_log is None:
            item_id = self._get_itemid(item)
            oldest_log = self._read_log_oldest(item_id)

            if isinstance(oldest_log, int):
                if item not in self.item_cache:
                    self.item_cache[item] = {}
                self.item_cache[item]['oldest_log'] = oldest_log

        if self.debug_log.prepare:
            self.logger.debug(f"_get_oldest_log for item={item.property.path} = {oldest_log}")

        return oldest_log

    def _get_oldest_value(self, item: Item) -> Union[int, float, bool]:
        """
        Get value of the oldest log of item from cache dict or get value from db and put it to cache dict

        :param item: Item, for which query should be done
        :return: oldest value
        """

        _oldest_entry = self.item_cache.get(item, {}).get('oldest_entry', None)

        if _oldest_entry is not None:
            _oldest_value = _oldest_entry[0][4]
        else:
            item_id = self._get_itemid(item)
            validity = False
            i = 0
            _oldest_value = -999999999
            while validity is False:
                oldest_log = self._get_oldest_log(item)
                if oldest_log is None:
                    validity = True
                    self.logger.error(f"oldest_log for item={item.property.path} could not be read; value is set to -999999999")
                oldest_entry = self._read_log_timestamp(item_id, oldest_log)
                i += 1
                if isinstance(oldest_entry, list) and isinstance(oldest_entry[0], tuple) and len(oldest_entry[0]) >= 4:
                    if item not in self.item_cache:
                        self.item_cache[item] = {}
                    self.item_cache[item]['oldest_entry'] = oldest_entry
                    _oldest_value = oldest_entry[0][4]
                    validity = True
                elif i == 10:
                    validity = True
                    self.logger.error(f"oldest_value for item={item.property.path} could not be read; value is set to -999999999")

        if self.debug_log.prepare:
            self.logger.debug(f"_get_oldest_value for item={item.property.path} = {_oldest_value}")

        return _oldest_value

    def _get_itemid(self, item: Item) -> int:
        """
        Returns the ID of the given item from cache dict or request it from database

        :param item: Item to get the ID for
        :return: id of the item within the database
        """

        _item_id = self.item_cache.get(item, {}).get('id', None)

        if _item_id is None:
            row = self._read_item_table(item_path=str(item.property.path))
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

    def _query_item(self, func: str, database_item: Item, timeframe: str, start: int = None, end: int = 0, group: str = "", group2: str = "", ignore_value_list=None, use_oldest_entry: bool = False) -> list:
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

        if self.debug_log.prepare:
            self.logger.debug(f"  called with {func=}, item={database_item.property.path}, {timeframe=}, {start=}, {end=}, {group=}, {group2=}, {ignore_value_list=}, {use_oldest_entry=}")

        # set default result
        error_result = [[None, None]]
        nodata_result = [[0, 0]]

        # check correctness of timeframe
        if timeframe not in ALLOWED_QUERY_TIMEFRAMES:
            self.logger.error(f"Requested {timeframe=} for item={database_item.property.path} not defined; Need to be 'year' or 'month' or 'week' or 'day' or 'hour''. Query cancelled.")
            return error_result

        # define start and end of query as timestamp in microseconds
        ts_start, ts_end = self._get_start_end_as_timestamp(timeframe, start, end)
        oldest_log = self._get_oldest_log(database_item)
        if oldest_log is None:
            return error_result

        # check correctness of ts_start / ts_end
        if ts_start is None:
            ts_start = oldest_log
        if ts_end is None or ts_start > ts_end:
            if self.debug_log.prepare:
                self.logger.debug(f"{ts_start=}, {ts_end=}")
            self.logger.warning(f"Requested {start=} for item={database_item.property.path} is not valid since {start=} > {end=} or end not given. Query cancelled.")
            return error_result

        # define item_id
        item_id = self._get_itemid(database_item)
        if not item_id:
            self.logger.error(f"DB ItemId for item={database_item.property.path} not found. Query cancelled.")
            return error_result

        if self.debug_log.prepare:
            self.logger.debug(f"  Requested {timeframe=} with {start=} and {end=} resulted in start being timestamp={ts_start}/{self._timestamp_to_timestring(ts_start)} and end being timestamp={ts_end}/{self._timestamp_to_timestring(ts_end)}")

        # check if values for end time and start time are in database
        if ts_end < oldest_log:  # (Abfrage abbrechen, wenn Endzeitpunkt in UNIX-timestamp der Abfrage kleiner (und damit jünger) ist, als der UNIX-timestamp des ältesten Eintrages)
            self.logger.info(f"  Requested end time timestamp={ts_end}/{self._timestamp_to_timestring(ts_end)} of query for item={database_item.property.path} is prior to oldest entry with timestamp={oldest_log}/{self._timestamp_to_timestring(oldest_log)}. Query cancelled.")
            return error_result

        if ts_start < oldest_log:
            if self.use_oldest_entry or use_oldest_entry:
                self.logger.info(f"  Requested start time timestamp={ts_start}/{self._timestamp_to_timestring(ts_start)} of query for item={database_item.property.path} is prior to oldest entry with timestamp={oldest_log}/{self._timestamp_to_timestring(oldest_log)}. Oldest available entry will be used.")
                ts_start = oldest_log
            else:
                self.logger.info(f"  Requested start time timestamp={ts_start}/{self._timestamp_to_timestring(ts_start)} of query for item={database_item.property.path} is prior to oldest entry with timestamp={oldest_log}/{self._timestamp_to_timestring(oldest_log)}. Query cancelled.")
                return error_result

        # prepare and do query
        query_params = {'func': func, 'item_id': item_id, 'ts_start': ts_start, 'ts_end': ts_end, 'group': group, 'group2': group2, 'ignore_value_list': ignore_value_list}
        query_result = self._query_log_timestamp(**query_params)

        if self.debug_log.prepare:
            self.logger.debug(f"  result of '_query_log_timestamp' {query_result=}")

        # post process query_result
        if query_result is None:
            self.logger.error(f"Error occurred during '_query_log_timestamp' of item={database_item.property.path}. Aborting...")
            return error_result

        if len(query_result) == 0:
            self.logger.info(f"  No values for item={database_item.property.path} in requested timeframe between {ts_start}/{self._timestamp_to_timestring(ts_start)} and {ts_end}/{self._timestamp_to_timestring(ts_end)} in database found.")
            return nodata_result

        result = []
        for element in query_result:
            timestamp, value = element
            if timestamp is not None and value is not None:
                if isinstance(value, float):
                    value = round(value, 2)
                result.append([timestamp, value])

        if self.debug_log.prepare:
            self.logger.debug(f"  value for item={database_item.property.path} with {query_params=}: {result}")

        if not result:
            self.logger.info(f"  No values for item={database_item.property.path} in requested timeframe between {ts_start}/{self._timestamp_to_timestring(ts_start)} and {ts_end}/{self._timestamp_to_timestring(ts_end)} in database found.")
            return nodata_result

        return result

    def _init_cache_dicts(self) -> None:
        """
        init all cache dicts
        """

        self.logger.info(f"All cache_dicts will be initiated.")

        self.item_cache = {}

        self.current_values = {
            HOUR: {},
            DAY: {},
            WEEK: {},
            MONTH: {},
            YEAR: {}
        }

        self.previous_values = {
            HOUR: {},
            DAY: {},
            WEEK: {},
            MONTH: {},
            YEAR: {}
        }

        self.value_list_raw_data = {}

    def _clean_item_cache(self, item: Union[str, Item]) -> bool:
        """set cached values for item to None"""

        if isinstance(item, str):
            item = self.items.return_item(item)

        if not isinstance(item, Item):
            return False

        database_item = self.get_item_config(item).get('database_item')

        if database_item:
            for timeframe in self.previous_values:
                for cached_item in self.previous_values[timeframe]:
                    if cached_item == database_item:
                        self.previous_values[timeframe][cached_item] = None

            for timeframe in self.current_values:
                for cached_item in self.current_values[timeframe]:
                    if cached_item == database_item:
                        self.current_values[timeframe][cached_item] = {}

            return True
        return False

    def _clear_queue(self) -> None:
        """
        Clear working queue
        """

        self.logger.info(f"Working queue will be cleared. Calculation run will end.")
        self.item_queue.queue.clear()

    def _get_start_end_as_timestamp(self, timeframe: str, start: Union[int, str, None], end: Union[int, str, None]) -> tuple:
        """
        Provides start and end as timestamp in microseconds from timeframe with start and end

        :param timeframe: timeframe as week, month, year
        :param start: beginning timeframe in x timeframes from now
        :param end: end of timeframe in x timeframes from now

        :return: start time in timestamp in microseconds, end time in timestamp in microseconds

        """

        ts_start = ts_end = None

        def get_query_timestamp(_offset) -> int:
            if timeframe == 'hour':
                dt = self.shtime.now().replace(microsecond=0, second=0, minute=0) - datetime.timedelta(hours=_offset)
                return self._datetime_to_timestamp(dt) * 1000
            elif timeframe == 'week':
                _date = self.shtime.beginning_of_week(offset=-_offset)
            elif timeframe == 'month':
                _date = self.shtime.beginning_of_month(offset=-_offset)
            elif timeframe == 'year':
                _date = self.shtime.beginning_of_year(offset=-_offset)
            else:
                _date = self.shtime.today(offset=-_offset)

            return self._datetime_to_timestamp(datetime.datetime.combine(_date, datetime.datetime.min.time())) * 1000

        if isinstance(start, str) and start.isdigit():
            start = int(start)
        if isinstance(start, int):
            ts_start = get_query_timestamp(start)

        if isinstance(end, str) and end.isdigit():
            end = int(end)
        if isinstance(end, int):
            if timeframe == 'hour':
                ts_end = get_query_timestamp(end)
            else:
                ts_end = get_query_timestamp(end - 1)

        return ts_start, ts_end

    def _datetime_to_timestamp(self, dt: datetime) -> int:
        """Provides timestamp from given datetime"""

        return int(dt.replace(tzinfo=self.shtime.tzinfo()).timestamp())

    def _timestamp_to_datetime(self, timestamp: float) -> datetime:
        """Parse timestamp from db query to datetime"""

        return datetime.datetime.fromtimestamp(timestamp, tz=self.shtime.tzinfo())

    def _timestamp_to_timestring(self, timestamp: int) -> str:
        """Parse timestamp from db query to string representing date and time"""

        return self._timestamp_to_datetime(timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')

    def _valid_year(self, year: Union[int, str]) -> bool:
        """Check if given year is digit and within allowed range"""

        if ((isinstance(year, int) or (isinstance(year, str) and year.isdigit())) and (
                1980 <= int(year) <= self.shtime.today(offset=0).year)) or (isinstance(year, str) and year == 'current'):
            return True
        else:
            return False

    @staticmethod
    def _valid_month(month: Union[int, str]) -> bool:
        """Check if given month is digit and within allowed range"""

        if (isinstance(month, int) or (isinstance(month, str) and month.isdigit())) and (1 <= int(month) <= 12):
            return True
        else:
            return False

    #################################
    #   Database Query Preparation
    #################################

    def _query_log_timestamp(self, func: str, item_id: int, ts_start: int, ts_end: int, group: str = "", group2: str = "", ignore_value_list=None) -> Union[list, None]:
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
        if self.debug_log.prepare:
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
            'avg1':        ') AS table1 ',
            'max1':        ') AS table1 ',
            'sum_max':     ') AS table1 ',
            'sum_avg':     ') AS table1 ',
            'sum_min_neg': ') AS table1 ',
            'diff_max':    ') AS table1 ',
        }

        _order = {
            'avg1':        'ORDER BY time ASC ',
            'max1':        'ORDER BY time ASC ',
            'on':          'ORDER BY time ASC ',
            'sum_max':     'ORDER BY time ASC ',
            'sum_min_neg': 'ORDER BY time ASC ',
            'diff_max':    'ORDER BY time ASC ',
            'next':        'ORDER BY time DESC ',
            'raw':         'ORDER BY time ASC ',
            'first':       'ORDER BY time ASC ',
            'last':        'ORDER BY time DESC ',
        }

        _limit = {
            'next':        'LIMIT 1 ',
            'first':       'LIMIT 1 ',
            'last':        'LIMIT 1 ',
        }

        _where = "item_id = :item_id AND time <= :ts_start " if func == "next" else "item_id = :item_id AND time BETWEEN :ts_start AND :ts_end "

        _db_table = 'log '

        _group_by_sql = {
            "year":  "GROUP BY YEAR(FROM_UNIXTIME(time/1000)) ",
            "month": "GROUP BY FROM_UNIXTIME((time/1000),'%Y%m') ",
            "week":  "GROUP BY YEARWEEK(FROM_UNIXTIME(time/1000), 5) ",
            "day":   "GROUP BY DATE(FROM_UNIXTIME(time/1000)) ",
            "hour":  "GROUP BY FROM_UNIXTIME((time/1000),'%Y%m%d%H') ",
        }

        _group_by_sqlite = {
            "year":  "GROUP BY strftime('%Y', date((time/1000),'unixepoch')) ",
            "month": "GROUP BY strftime('%Y%m', date((time/1000),'unixepoch')) ",
            "week":  "GROUP BY strftime('%Y%W', date((time/1000),'unixepoch')) ",
            "day":   "GROUP BY date((time/1000),'unixepoch') ",
            "hour":  "GROUP BY strftime('%Y%m%d%H', datetime((time/1000),'unixepoch')) ",
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
        if group and group not in _group_by:
            self.logger.error(f"Requested {group=} for item={item_id=} not defined. Query cancelled.")
            return
        if group2 and group2 not in _group_by:
            self.logger.error(f"Requested {group2=} for item={item_id=} not defined. Query cancelled.")
            return

        # handle ignore values
        if func in ['min', 'max', 'max1', 'sum_max', 'sum_avg', 'sum_min_neg', 'diff_max']:  # extend _where statement for excluding boolean values == 0 for defined functions
            _where = f'{_where}AND val_bool = 1 '
        if ignore_value_list:  # if comparison to be applied during query, extend _where statement
            for entry in ignore_value_list:
                _where = f'{_where}AND val_num {entry.strip()} '

        # set params
        params = {'item_id': item_id, 'ts_start': ts_start, 'ts_end': ts_end}
        if func == "next":
            params.pop('ts_end', None)

        # assemble query
        query = f"SELECT {_select[func]}FROM {_db_table}WHERE {_where}{_group_by.get(group, '')}{_order.get(func, '')}{_limit.get(func, '')}{_table_alias.get(func, '')}{_group_by.get(group2, '')}".strip()

        if self.db_driver.lower() == 'sqlite3':
            query = query.replace('IF', 'IIF')

        # do debug log
        if self.debug_log.prepare:
            self.logger.debug(f"{query=}, {params=}")

        # request database and return result
        return self._fetchall(query, params)

    def _read_log_oldest(self, item_id: int) -> int:
        """
        Read the oldest log record for given database ID

        :param item_id: Database ID of item to read the record for
        :return: timestamp of oldest log entry of given item_id
        """

        params = {'item_id': item_id}
        query = "SELECT min(time) FROM log WHERE item_id = :item_id;"
        result = self._fetchall(query, params)
        return None if result is None else result[0][0]

    def _read_log_newest(self, item_id: int) -> int:
        """
        Read the oldest log record for given database ID

        :param item_id: Database ID of item to read the record for
        :return: timestamp of newest log entry of given item_id
        """

        params = {'item_id': item_id}
        query = "SELECT max(time) FROM log WHERE item_id = :item_id;"
        result = self._fetchall(query, params)
        return None if result is None else result[0][0]

    def _read_log_timestamp(self, item_id: int, timestamp: int) -> Union[list, None]:
        """
        Read database log record for given database ID

        :param item_id: Database ID of item to read the record for
        :param timestamp: timestamp for the given value
        :return: Log record for the database ID at given timestamp
        """

        params = {'item_id': item_id, 'timestamp': timestamp}
        query = "SELECT * FROM log WHERE item_id = :item_id AND time = :timestamp;"
        return self._fetchall(query, params)

    def _read_item_table(self, item_id: int = None, item_path: str = None) -> Union[list, None]:
        """
        Read item table

        :param item_id: unique ID for item within database
        :param item_path: item_path for Item within the database
        :return: Data for the selected item
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

    ###############################
    #   Database specific stuff
    ###############################

    def _initialize_db(self) -> bool:
        """
        Initializes database connection

        :return: Status of initialization
        """

        try:
            if not self._db.connected():
                # limit connection requests to 20 seconds.
                time_since_last_connect = time.time() - self.last_connect_time
                if time_since_last_connect > 20:
                    self.last_connect_time = time.time()
                    self.logger.debug(f"Connect to database.")
                    self._db.connect()
                else:
                    self.logger.warning(f"Database reconnect suppressed since last connection is less then 20sec ago.")
                    return False

        except Exception as e:
            self.logger.critical(f"Initialization of Database Connection failed: {e}")
            return False

        return True

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

        tuples = self._query(self._db.fetchall, query, params, cur)
        return None if tuples is None else list(tuples)

    def _query(self, fetch, query: str, params: dict = None, cur=None) -> Union[None, list]:
        """query using commit to get latest data from db"""

        if params is None:
            params = {}

        if self.debug_log.sql:
            self.logger.debug(f"Called with {query=}, {params=}, {cur=}")

        if not self._initialize_db():
            return None

        if cur is None:
            verify_conn = self._db.verify(retry=5)
            if verify_conn == 0:
                self.logger.error("Connection to database NOT recovered.")
                return None

        if self.lock_db_for_query and not self._db.lock(300):
            self.logger.error("Can't query database due to fail to acquire lock.")
            return None

        query_readable = re.sub(r':([a-z_]+)', r'{\1}', query).format(**params)

        # do commit to get latest data during fetch
        self._db.commit()

        # fetch data
        try:
            tuples = fetch(query, params, cur=cur)
        except Exception as e:
            self.logger.error(f"Error '{e}' for query={query_readable} occurred.")
            tuples = None
            pass

        if cur is None and self.lock_db_for_query:
            self._db.release()

        if self.debug_log.sql:
            self.logger.debug(f"Result of query={query_readable}: {tuples}")

        return tuples

    # ToDo: Check if still needed.
    def _query_with_close(self, fetch, query: str, params: dict = None, cur=None) -> Union[None, list]:
        """query open and close connection for each query to get latest data from db"""

        if params is None:
            params = {}

        if self.debug_log.sql:
            self.logger.debug(f"Called with {query=}, {params=}, {cur=}")

        # recovery connection to database
        if cur is None or not self._db.connected:
            verify_conn = self._db.verify(retry=5)
            if verify_conn == 0:
                self.logger.error("Connection to database NOT recovered.")
                return None
            else:
                if self.debug_log.sql:
                    self.logger.debug("Connection to database recovered.")

        # lock database if required
        if cur is None and self.lock_db_for_query:
            if not self._db.lock(300):
                self.logger.error("Can't query database due to fail to acquire lock.")
                return None

        # fetch data
        query_readable = re.sub(r':([a-z_]+)', r'{\1}', query).format(**params)
        try:
            tuples = fetch(query, params, cur=cur)
        except Exception as e:
            self.logger.error(f"Error '{e}' for query={query_readable} occurred.")
            tuples = None
            pass

        # release database
        if cur is None and self.lock_db_for_query:
            self._db.release()

        # close connection
        self._db.close()

        if self.debug_log.sql:
            self.logger.debug(f"Result of query={query_readable}: {tuples}")

        return tuples


@dataclass
class DebugLogOptions:
    """Class to simplify use and handling of debug log options."""

    log_level: InitVar[int] = 10
    parse: bool = True             # Enable / Disable debug logging for method 'parse item'
    execute: bool = True           # Enable / Disable debug logging for method 'execute items'
    ondemand: bool = True          # Enable / Disable debug logging for method 'handle_ondemand'
    onchange: bool = True          # Enable / Disable debug logging for method 'handle_onchange'
    prepare: bool = True           # Enable / Disable debug logging for query preparation
    sql: bool = True               # Enable / Disable debug logging for sql stuff

    def __post_init__(self, log_level):
        if log_level > 10:
            self.parse = False
            self.execute = False
            self.ondemand = False
            self.onchange = False
            self.prepare = False
            self.prepare = False


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
        return res_dict


def translate_timeframe(timeframe: str) -> str:
    """translates different expression of timeframe"""

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


def timeframe_to_timeframe(timeframe_in: str, timeframe_out: str) -> int:
    """Convert timeframe to timeframe like month in years or years in days"""

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

    return lookup[timeframe_in][timeframe_out]


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


def timeframe_to_updatecyle(timeframe) -> str:

    lookup = {'day': 'daily',
              'week': 'weekly',
              'month': 'monthly',
              'year': 'yearly'}

    return lookup.get(timeframe)


def split_sting_letters_numbers(string) -> list:
    return re.findall(r'(\d+|[A-Za-z]+)', string)


ALLOWED_QUERY_TIMEFRAMES = ['year', 'month', 'week', 'day', 'hour']
ALLOWED_MINMAX_FUNCS = ['min', 'max', 'avg']
