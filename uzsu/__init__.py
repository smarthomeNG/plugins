#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
######################################################################################
# Copyright 2011-2013 Niko Will
# Copyright 2017,2022 Bernd Meiners                              Bernd.Meiners@mail.de
# Copyright 2018 Andreas Künz                                    onkelandy66@gmail.com
# Copyright 2021 extension for series Andre Kohler       andre.kohler01@googlemail.com
######################################################################################
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
#  along with SmartHomeNG.  If not, see <http://www.gnu.org/licenses/>.
##########################################################################


# Item Data Format
#
# Each UZSU item is of type list. Each list entry has to be a dict with specific key and value pairs.
# Here are the possible keys and their purpose:
#
#     dtstart:  a datetime object. Exact datetime as start value for the rrule algorithm.
#               Important e.g. for FREQ=MINUTELY rrules (optional).
#
#     value:    the value which will be set to the item.
#
#     active:   True if the entry is activated, False if not.
#               A deactivated entry is stored to the database but doesn't trigger the setting of the value.
#               It can be enabled later with the update method.
#
#     time:     time as string
#               A) regular time expression like 17:00
#               B) to use sunrise/sunset arithmetics like in the crontab
#                  examples:
#                     17:00<sunset
#                     sunrise>8:00
#                     17:00<sunset.
#               C) 'serie' to indicate the use of a time series; definition of a
#                   time series is mandatory using dict key 'series'
#
#     series:   definition of the time series as dict using keys 'active', 'timeSeriesMin',
#               'timeSeriesMax', 'timeSeriesIntervall'
#                   example:
#                       "series":{"active":true,
#                                 "timeSeriesMin":"06:15",
#                                 "timeSeriesMax":"15:30",
#                                 "timeSeriesIntervall":"01:00"}
#               alternative to 'timeSeriesMax', which indicated the end time of the time series, the key 'timeSeriesCount'
#               can be used to define the number of cycles to be run
#                   example:
#                       "series":{"active":true,
#                                 "timeSeriesMin":"06:15",
#                                 "timeSeriesCount":"4",
#                                 "timeSeriesIntervall":"01:00"}
#
#
#     rrule:    You can use the recurrence rules documented in the iCalendar RFC for recurrence use of a switching entry.
#
# Example
#
# Activates the light every other day at 16:30 and deactivates it at 17:30 for five times:
#
# sh.eg.wohnen.kugellampe.uzsu({'active':True, 'list':[
# {'value':1, 'active':True, 'rrule':'FREQ=DAILY;INTERVAL=2;COUNT=5', 'time': '16:30'},
# {'value':0, 'active':True, 'rrule':'FREQ=DAILY;INTERVAL=2;COUNT=5', 'time': '17:30'}
# ]})

import functools
from lib.model.smartplugin import SmartPlugin
from lib.item import Items
from lib.shtime import Shtime

from datetime import datetime, timedelta
from time import sleep
from dateutil.rrule import rrulestr
from dateutil import parser
from dateutil.tz import tzutc
from unittest import mock
from collections import OrderedDict
import html
import json
from .webif import WebInterface

ITEM_TAG = ['uzsu_item']


class UZSU(SmartPlugin):
    """
    Main class of the UZSU Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    ALLOW_MULTIINSTANCE = False

    PLUGIN_VERSION = "2.0.0"      # item buffer for all uzsu enabled items

    def __init__(self, smarthome):
        """
        Initializes the plugin. The parameters describe for this method are pulled from the entry in plugin.conf.
        :param smarthome:  The instance of the smarthome object, save it for later references
        """
        self.itemsApi = Items.get_instance()
        self._timezone = Shtime.get_instance().tzinfo()
        self._remove_duplicates = self.get_parameter_value('remove_duplicates')
        self._interpolation_interval = self.get_parameter_value('interpolation_interval')
        self._interpolation_type = self.get_parameter_value('interpolation_type')
        self._interpolation_precision = self.get_parameter_value('interpolation_precision')
        self._backintime = self.get_parameter_value('backintime')
        self._suncalculation_cron = self.get_parameter_value('suncalculation_cron')
        self._sh = smarthome
        self._items = {}
        self._lastvalues = {}
        self._planned = {}
        self._webdata = {'sunCalculated': {}, 'items': {}}
        self._update_count = {'todo': 0, 'done': 0}
        self._itpl = {}
        self.init_webinterface(WebInterface)
        self.logger.info(f'Init with timezone {self._timezone}')

    def run(self):
        """
        This is called once at the beginning after all items are already parsed from smarthome.py
        All active uzsu items are registered to the scheduler
        """
        self.logger.debug("run method called")
        self.alive = True
        self.scheduler_add('uzsu_sunupdate', self._update_all_suns,
                           value={'caller': 'Scheduler:UZSU'}, cron=self._suncalculation_cron)
        self.logger.info("Adding sun update schedule for midnight")

        for item in self._items:
            self._add_dicts(item)
            self._items[item]['interpolation']['itemtype'] = self._add_type(item)
            self._lastvalues[item] = None
            self._webdata['items'][item.property.path].update({'lastvalue': '-'})
            self._update_item(item, 'UZSU Plugin', 'run')
            cond1 = self._items[item].get('active') and self._items[item]['active']
            cond2 = self._items[item].get('list')
            if cond1 and cond2:
                self._update_count['todo'] = self._update_count.get('todo', 0) + 1
        self.logger.debug(f'Going to update {self._update_count["todo"]} items from {list(self._items.keys())}')

        for item in self._items:
            cond1 = self._items[item].get('active') is True
            cond2 = self._items[item].get('list')
            # remove lastvalue dict entry, it is not used anymore
            try:
                self._items[item].pop('lastvalue')
                self._update_item(item, 'UZSU Plugin', 'lastvalue removed')
                self.logger.debug(f'Item "{item}": removed lastvalue dict entry as it is deprecated.')
            except Exception:
                pass
            self._check_rruleandplanned(item)
            if cond1 and cond2:
                self._schedule(item, caller='run')
            elif cond1 and not cond2:
                self.logger.warning(f'Item "{item}" is active but has no entries.')
                self._planned.update({item: None})
                self._webdata['items'][item.property.path].update({'planned': {'value': '-', 'time': '-'}})
            else:
                self.logger.debug(f'Not scheduling item {item}, cond1 {cond1}, cond2 {cond2}')
                self.logger.info(f'Dry run of scheduler calculation for item {item} to get calculated sunset/rise entries')
                self._schedule(item, caller='dry_run')

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("stop method called")
        self.scheduler_remove('uzsu_sunupdate')
        for item in self._items:
            try:
                self.scheduler_remove(item.property.path)
                self.logger.debug(f'Removing scheduler for item {item.property.path}')
            except Exception as err:
                self.logger.debug(f'Scheduler for item {item.property.path} not removed. Problem: {err}')
        self.alive = False

    def _update_all_suns(self, caller=None):
        """
        Update sun information for all uzsu items
        :param caller:  if given it represents the callers name
        :type caller:   str
        """
        for item in self._items:
            success = self._update_sun(item, caller="update_all_suns")
            if success:
                self.logger.debug(f'Updating sun info for item {item}. Caller: {caller}')
                self._update_item(item, 'UZSU Plugin', 'update_all_suns')

    def _update_sun(self, item, caller=None):
        """
        Update general sunrise and sunset information for visu
        :param caller:  if given it represents the callers name
        :param item:    uzsu item
        :type caller:   str
        :type item:     item
        """
        if caller != "_update_item":
            self._items[item] = item()
        try:
            _sunrise = self._sh.sun.rise()
            _sunset = self._sh.sun.set()
            if _sunrise.tzinfo == tzutc():
                _sunrise = _sunrise.astimezone(self._timezone)
            if _sunset.tzinfo == tzutc():
                _sunset = _sunset.astimezone(self._timezone)
            self._items[item]['sunrise'] = f'{_sunrise.hour:02}:{_sunrise.minute:02}'
            self._items[item]['sunset'] = f'{_sunset.hour:02}:{_sunset.minute:02}'
            self.logger.debug(f'Updated sun entries for item {item}, triggered by {caller}. sunrise: {self._items[item]["sunrise"]}, sunset: {self._items[item]["sunset"]}')
            success = True
        except Exception as e:
            success = f'Not updated sun entries for item {item}. Error {e}'
            self.logger.debug(success)
        return success

    def _update_suncalc(self, item, entry, entryindex, entryvalue):
        update = False
        if entry.get('calculated'):
            if entry == self._items[item]['list'][entryindex]:
                update = True
            with mock.patch.dict(entry, calculated=entryvalue):
                if entry == self._items[item]['list'][entryindex]:
                    update = True
        else:
            update = True
        if entry.get('calculated') and entryvalue is None:
            self.logger.debug(f'No sunset/rise in time for current entry {entry}. Removing calculated value.')
            self._items[item]['list'][entryindex].pop('calculated')
            self._update_item(item, 'UZSU Plugin', 'update_sun')
        elif update is True and not entry.get('calculated') == entryvalue:
            self.logger.debug(f'Updated calculated time for item {item} entry {self._items[item]["list"][entryindex]} with value {entryvalue}.')
            self._items[item]['list'][entryindex]['calculated'] = entryvalue
            self._update_item(item, 'UZSU Plugin', 'update_sun')
        elif entry.get('calculated'):
            self.logger.debug(f'Sun calculation {entryvalue} entry not updated for item {item} with value {entry["calculated"]}')

    def _add_type(self, item):
        """
        Adding the type of the item that is changed by the uzsu to the item dict
        :param item:    uzsu item
        :type item:     item
        :return:        The item type of the item that is changed
        """
        _itemforuzsu = self.get_iattr_value(item.conf, ITEM_TAG[0])
        try:
            _uzsuitem = self.itemsApi.return_item(_itemforuzsu)
        except Exception as err:
            _uzsuitem = None
            self.logger.warning(f'Item to be set by uzsu "{_itemforuzsu}" does not exist. Error: {err}')
        try:
            _itemtype = _uzsuitem.property.type
        except Exception as err:
            try:
                _itemtype = _uzsuitem.type()
            except Exception:
                _itemtype = 'foo' if _uzsuitem else None
            if _itemtype is None:
                # TODO: this is apparently wrong, as existence of the item was
                # established in the previous try/except block. What does this
                # error actually indicate?
                self.logger.warning(f'Item to be set by uzsu "{_itemforuzsu}" does not exist. Error: {err}')
            else:
                self.logger.warning(f'Item to be set by uzsu "{_itemforuzsu}" does not have a type attribute. Error: {err}')
        return _itemtype

    def _logics_lastvalue(self, by=None, item=None):
        if self._items.get(item):
            lastvalue = self._lastvalues.get(item)
        else:
            lastvalue = None
        by_test = f' Queried by {by}' if by else ""
        self.logger.debug(f'Last value of item {item} is: {lastvalue}.{by_test}')
        return lastvalue

    def _logics_resume(self, activevalue=True, item=None):
        self._logics_activate(True, item)
        lastvalue = self._logics_lastvalue(item)
        self._set(item=item, value=lastvalue, caller='logic')
        self.logger.info(f'Resuming item {item}: Activated and value set to {lastvalue}. Active value: {activevalue}')
        return lastvalue

    def _logics_activate(self, activevalue=None, item=None):
        if isinstance(activevalue, str):
            if activevalue.lower() in ['1', 'yes', 'true', 'on']:
                activevalue = True
            elif activevalue.lower() in ['0', 'no', 'false', 'off']:
                activevalue = False
            else:
                self.logger.warning(f'Value to activate item "{item}" has to be True or False')
        if isinstance(activevalue, bool):
            self._items[item] = item()
            self._items[item]['active'] = activevalue
            self.logger.info(f'Item {item} is set via logic to: {activevalue}')
            self._update_item(item, 'UZSU Plugin', 'logic')
            return activevalue
        if activevalue is None:
            return self._items[item].get('active')

    def _logics_interpolation(self, intpl_type=None, interval=None, backintime=None, item=None):
        interval = self._interpolation_interval if interval is None else interval
        backintime = self._backintime if backintime is None else backintime
        if intpl_type is None:
            return self._items[item].get('interpolation')
        else:
            self._items[item] = item()
            self._items[item]['interpolation']['type'] = str(intpl_type).lower()
            self._items[item]['interpolation']['interval'] = abs(int(interval))
            self._items[item]['interpolation']['initage'] = int(backintime)
            self.logger.info(f'Item {item} interpolation is set via logic to: type={intpl_type}, interval={abs(interval)}, backintime={backintime}')
            self._update_item(item, 'UZSU Plugin', 'logic')
            return self._items[item].get('interpolation')

    def _logics_clear(self, clear=False, item=None):
        if isinstance(clear, str):
            if clear.lower() in ['1', 'yes', 'true', 'on']:
                clear = True
            else:
                self.logger.warning(f'Value to clear uzsu item "{item}" has to be True')
        if isinstance(clear, bool) and clear is True:
            self._items[item].clear()
            self._items[item] = {'interpolation': {}, 'active': False}
            self.logger.info(f'UZSU settings for item "{item}" are cleared')
            self._update_item(item, 'UZSU Plugin', 'clear')
            return True
        else:
            return False

    def _logics_itpl(self, clear=False, item=None):
        if isinstance(clear, str):
            if clear.lower() in ['1', 'yes', 'true', 'on']:
                clear = True
        if isinstance(clear, bool) and clear is True:
            self._itpl[item].clear()
            self.logger.info(f'UZSU interpolation dict for item "{item}" is cleared')
            return self._itpl[item]
        else:
            self.logger.info(f'UZSU interpolation dict for item "{item}" is: {self._itpl[item]}')
            return self._itpl[item]

    def _logics_planned(self, item=None):
        if self._planned.get(item) not in [None, {}, 'notinit'] and self._items[item].get('active') is True:
            self.logger.info(f"Item '{item}' is going to be set to {self._planned[item]['value']} at {self._planned[item]['next']}")
            self._webdata['items'][item.property.path].update(
                {'planned': {'value': self._planned[item]['value'], 'time': self._planned[item]['next']}})
            return self._planned[item]
        elif self._planned.get(item) == 'notinit' and self._items[item].get('active') is True:
            self.logger.info(f'Item "{item}" is active but not fully initialized yet.')
            return None
        elif not self._planned.get(item) and self._items[item].get('active') is True:
            self.logger.warning(f'Item "{item}" is active but has no (active) entries.')
            self._planned.update({item: None})
            self._webdata['items'][item.property.path].update({'planned': {'value': '-', 'time': '-'}})
            return None
        else:
            self.logger.info(f'Nothing planned for item "{item}".')
            return None

    def _add_dicts(self, item):
        """
        Method to add interpolation dict if it's not available
        :param item:    The item to process
        :type item:     item
        """
        if 'interpolation' not in self._items[item]:
            self._items[item]['interpolation'] = {
                'type': 'none',
                'initialized': False,
                'interval': self._interpolation_interval,
                'initage': self._backintime
            }
        else:
            if 'type' not in self._items[item]['interpolation']:
                self._items[item]['interpolation']['type'] = 'none'
            if 'initialized' not in self._items[item]['interpolation']:
                self._items[item]['interpolation']['initialized'] = False
            if 'interval' not in self._items[item]['interpolation']:
                self._items[item]['interpolation']['interval'] = self._interpolation_interval
            if 'initage' not in self._items[item]['interpolation']:
                self._items[item]['interpolation']['initage'] = self._backintime

        self._items[item]['plugin_version'] = self.PLUGIN_VERSION
        if 'list' not in self._items[item]:
            self._items[item]['list'] = []
        if 'active' not in self._items[item]:
            self._items[item]['active'] = False

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        The plugin can, corresponding to its attribute keywords, decide what to do with
        the item in the future, like adding it to an internal array for future reference
        :param item:    The item to process
        :type item:     item
        :return:        If the plugin needs to be informed of an items change you should return a call back function
                        like the function update_item down below. An example when this is needed is the knx plugin
                        where parse_item returns the update_item function when the attribute knx_send is found.
                        This means that when the items value is about to be updated, the call back function is called
                        with the item, caller, source and dest as arguments and in case of the knx plugin the value
                        can be sent to the knx with a knx write function within the knx plugin.
        """
        if self.has_iattr(item.conf, ITEM_TAG[0]):
            item.expand_relativepathes(ITEM_TAG[0], '', '')

            # add functions for use in logics and webif
            item.activate = functools.partial(self._logics_activate, item=item)
            item.lastvalue = functools.partial(self._logics_lastvalue, item=item)
            item.resume = functools.partial(self._logics_resume, item=item)
            item.interpolation = functools.partial(self._logics_interpolation, item=item)
            item.clear = functools.partial(self._logics_clear, item=item)
            item.planned = functools.partial(self._logics_planned, item=item)
            item.itpl = functools.partial(self._logics_itpl, item=item)

            self._items[item] = item()
            if 'interpolation' in self._items[item]:
                self._items[item]['interpolation']['initialized'] = False
            if self._items[item].get('list'):
                for entry, _ in enumerate(self._items[item]['list']):
                    self._items[item]['list'][entry].pop('condition', None)
                    self._items[item]['list'][entry].pop('holiday', None)
                    self._items[item]['list'][entry].pop('delayedExec', None)

            self._webdata['items'].update({item.property.path: {}})
            self._update_item(item, 'UZSU Plugin', 'init')
            self._planned.update({item: 'notinit'})
            self._webdata['items'][item.property.path].update({'planned': {'value': '-', 'time': '-'}})

            return self.update_item

    def _remove_dupes(self, item):
        self._items[item]['list'] = [i for n, i in enumerate(self._items[item]['list'])
                                     if i not in self._items[item]['list'][:n]]
        self.logger.debug(f'Removed duplicate entries for item {item}.')
        compare_entries = item.prev_value()
        if compare_entries.get('list'):
            newentries = []
            [newentries.append(i) for i in self._items[item]['list'] if i not in compare_entries['list']]
            self.logger.debug(f'Got update for item {item}: {newentries}')
            for entry in self._items[item]['list']:
                for new in newentries:
                    found = False
                    if not entry.get('value') == new.get('value') and new.get('active') is True:
                        try:
                            with mock.patch.dict(entry, value=new.get('value'), calculated=new['calculated']):
                                found = True if entry == new else found
                        except Exception:
                            with mock.patch.dict(entry, value=new.get('value')):
                                found = True if entry == new else found
                        if found is True:
                            self._items[item]['list'][self._items[item]['list'].index(entry)].update({'active': False})
                            time = entry['time']
                            oldvalue, newvalue = entry['value'], new['value']
                            self.logger.warning(f'Set old entry for item "{item}" at {time} with value {oldvalue} to inactive because newer active entry with value {newvalue} found.')

    def _check_rruleandplanned(self, item):
        if self._items[item].get('list'):
            _inactive = 0
            count = 0
            for entry in self._items[item]['list']:
                if entry.get('active') is False:
                    _inactive += 1
                if entry.get('rrule') == '':
                    try:
                        _index = self._items[item]['list'].index(entry)
                        self._items[item]['list'][_index]['rrule'] = 'FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR,SA,SU'
                        count += 1
                    except Exception as err:
                        self.logger.warning(f'Error creating rrule: {err}')
            if count > 0:
                self.logger.debug(f'Updated {count} rrule entries for item: {item}')
                self._update_item(item, 'UZSU Plugin', 'create_rrule')
            if _inactive >= len(self._items[item]['list']):
                self._planned.update({item: None})
                self._webdata['items'][item.property.path].update({'planned': {'value': '-', 'time': '-'}})

    def update_item(self, item, caller=None, source='', dest=None):
        """
        This is called by smarthome engine when the item changes, e.g. by Visu or by the command line interface
        The relevant item is put into the internal item list and registered to the scheduler
        :param item:    item to be updated towards the plugin
        :param caller:  if given it represents the callers name
        :param source:  if given it represents the source
        :param dest:    if given it represents the dest
        """
        cond = (not caller == 'UZSU Plugin') or source == 'logic'
        self.logger.debug(f'Update Item {item}, Caller {caller}, Source {source}, Dest {dest}. Will update: {cond}')
        if not source == 'create_rrule':
            self._check_rruleandplanned(item)
        # Removing Duplicates
        if self._remove_duplicates is True and self._items[item].get('list') and cond:
            self._remove_dupes(item)
        self._add_dicts(item)
        if not self._items[item]['interpolation'].get('itemtype') or \
                self._items[item]['interpolation']['itemtype'] == 'none':
            self._items[item]['interpolation']['itemtype'] = self._add_type(item)
        if cond and self._items[item].get('active') is False and not source == 'update_sun':
            self._lastvalues[item] = None
            self._webdata['items'][item.property.path].update({'lastvalue': '-'})
            self._webdata['items'][item.property.path].update({'planned': {'value': '-', 'time': '-'}})
            self.logger.debug(f'lastvalue for item {item} set to None because UZSU is deactivated')
        if cond:
            self._schedule(item, caller='update')
        elif 'sun' in source:
            self.logger.info(f'Not running dry run of scheduler calculation for item {item} because of {source} source')
        else:
            self.logger.info(f'Dry run of scheduler calculation for item {item} to get calculated sunset/rise entries. Source: {source}')
            self._schedule(item, caller='dry_run')

        if self._items[item] != self.itemsApi.return_item(str(item)) and cond:
            self._update_item(item, 'UZSU Plugin', 'update')

    def _update_item(self, item, caller="", comment=""):
        success = self._get_sun4week(item, caller="_update_item")
        if success:
            self.logger.debug(f'Updated weekly sun info for item {item} caller: {caller} comment: {comment}')
        else:
            self.logger.debug(f'Issues with updating weekly sun info for item {item} caller: {caller} comment: {comment}')
        success = self._series_calculate(item, caller, comment)
        if success is True:
            self.logger.debug(f'Updated seriesCalculated for item {item} caller: {caller} comment: {comment}')
        else:
            self.logger.debug(f'Issues with updating seriesCalculated for item {item} caller: {caller} comment: {comment}, issue: {success}')
        success = self._update_sun(item, caller="_update_item")
        if success is True:
            self.logger.debug(f'Updated sunset/rise calculations for item {item} caller: {caller} comment: {comment}')
        else:
            self.logger.debug(f'Issues with updating sunset/rise calculations for item {item} caller: {caller} comment: {comment}, issue: {success}')
        item(self._items[item], caller, comment)
        self._webdata['items'][item.property.path].update({'interpolation': self._items[item].get('interpolation')})
        self._webdata['items'][item.property.path].update({'active': str(self._items[item].get('active'))})
        # self._webdata['items'][item.property.path].update({'sun': self._items[item].get('SunCalculated')})
        _suncalc = self._items[item].get('SunCalculated')
        self._webdata['items'][item.property.path].update({'sun': _suncalc})
        self._webdata['sunCalculated'] = _suncalc
        self._webdata['items'][item.property.path].update({'dict': self.get_itemdict(item)})
        if comment != "init":
            _uzsuitem, _itemvalue = self._get_dependant(item)
            item_id = None if _uzsuitem is None else _uzsuitem.property.path
            self._webdata['items'][item.property.path].update({'depend': {'item': item_id, 'value': str(_itemvalue)}})

    def _interpolate(self, data: dict, time: float, linear=True, use_precision=True):
        """
        Returns linear / cubic interpolation for series data at specified time
        """
        ts_last = 0
        ts_next = -1
        for ts in data.keys():
            if ts <= time and ts > ts_last:
                ts_last = ts
            # use <= to get last data value for series of identical timestamps
            if ts >= time and (ts <= ts_next or ts_next == -1):
                ts_next = ts

        if time == ts_next:
            value = float(data[ts_next])
        elif time == ts_last:
            value = float(data[ts_last])
        else:
            d_last = float(data[ts_last])
            d_next = float(data[ts_next])

            if linear:

                # linear interpolation
                value = d_last + ((d_next - d_last) / (ts_next - ts_last)) * (time - ts_last)
            else:

                # cubic interpolation with m0/m1 = 0
                t = (time - ts_last) / (ts_next - ts_last)
                value = (2 * t ** 3 - 3 * t ** 2 + 1) * d_last + (-2 * t ** 3 + 3 * t ** 2) * d_next

        if use_precision:
            value = round(value, self._interpolation_precision)

        return value

    def _schedule(self, item, caller=None):
        """
        This function schedules an item: First the item is removed from the scheduler.
        If the item is active then the list is searched for the nearest next execution time.
        No matter if active or not the calculation for the execution time is triggered.
        :param item:    item to be updated towards the plugin.
        :param caller:  if given it represents the callers name. If the caller is set
                        to "dry_run" the evaluation of sun entries takes place but no scheduler will be set.
        """
        if caller != "dry_run":
            self.scheduler_remove(item.property.path)
            _caller = "Scheduler:UZSU"
            self.logger.debug(f'Schedule Item {item}, Trigger: {caller}, Changed by: {item.changed_by()}')
        else:
            self.logger.debug(f'Calculate Item {item}, Trigger: {caller}, Changed by: {item.changed_by()}')
            _caller = "dry_run"
        _next = None
        _value = None
        self._update_sun(item, caller=_caller)
        self._add_dicts(item)
        if not self._items[item]['interpolation'].get('itemtype') or \
                self._items[item]['interpolation']['itemtype'] == 'none':
            self._items[item]['interpolation']['itemtype'] = self._add_type(item)
        if self._items[item].get('interpolation') is None:
            self.logger.error("Something is wrong with your UZSU item. You most likely use a wrong smartVISU widget version! Use the latest device.uzsu SV 2.9. or higher If you write your uzsu dict directly please use the format given in the documentation: https://www.smarthomeng.de/user/plugins/uzsu/user_doc.html and include the interpolation array correctly!")
            return
        elif not self._items[item]['interpolation'].get('itemtype'):
            self.logger.error(f'item "{self.get_iattr_value(item.conf, ITEM_TAG[0])}" to be set by uzsu does not exist.')
        elif self._items[item].get('active') is True or _caller == "dry_run":
            self._itpl[item] = OrderedDict()
            for i, entry in enumerate(self._items[item]['list']):
                next, value = self._get_time(entry, 'next', item, i, _caller)
                previous, previousvalue = self._get_time(entry, 'previous', item, i, _caller)
                cond1 = next is None and previous is not None
                cond2 = previous is not None and next is not None and previous < next
                if cond1 or cond2:
                    next = previous
                    value = previousvalue
                if next is not None:
                    self.logger.debug(f'uzsu active entry for item {item} with datetime {next}, value {value} and tzinfo {next.tzinfo}')
                if _next is None:
                    _next = next
                    _value = value
                elif next and next < _next:
                    self.logger.debug(f'uzsu active entry for item {item} using now {next}, value {value} and tzinfo {next.tzinfo}')
                    _next = next
                    _value = value
                else:
                    self.logger.debug(f'uzsu active entry for item {item} keep {_next}, value {_value} and tzinfo {_next.tzinfo}')
        elif not self._items[item].get('list') and self._items[item].get('active') is True:
            self.logger.warning(f'item "{item}" is active but has no entries.')
            self._planned.update({item: None})
            self._webdata['items'][item.property.path].update({'planned': {'value': '-', 'time': '-'}})
        if _next and _value is not None and (self._items[item].get('active') is True or _caller == "dry_run"):
            _reset_interpolation = False
            _interval = self._items[item]['interpolation'].get('interval')
            _interval = self._interpolation_interval if not _interval else int(_interval)
            if _interval < 0:
                _interval = abs(int(_interval))
                self._items[item]['interpolation']['interval'] = _interval
                self._update_item(item, 'UZSU Plugin', 'intervalchange')
            _interpolation = self._items[item]['interpolation'].get('type')
            _interpolation = self._interpolation_type if not _interpolation else _interpolation
            _initage = self._items[item]['interpolation'].get('initage')
            _initage = 0 if not _initage else int(_initage)
            _initialized = self._items[item]['interpolation'].get('initialized')
            _initialized = False if not _initialized else _initialized
            entry_now = datetime.now(self._timezone).timestamp() * 1000.0
            self._itpl[item][entry_now] = 'NOW'
            itpl_list = sorted(list(self._itpl[item].items()))
            entry_index = itpl_list.index((entry_now, 'NOW'))
            _inittime = itpl_list[entry_index - min(1, entry_index)][0]
            _initvalue = itpl_list[entry_index - min(1, entry_index)][1]
            itpl_list = itpl_list[entry_index - min(2, entry_index):entry_index + min(3, len(itpl_list))]
            itpl_list.remove((entry_now, 'NOW'))
            if _caller != "dry_run":
                self._lastvalues[item] = _initvalue
                self._webdata['items'][item.property.path].update({'lastvalue': _initvalue})
            _timediff = datetime.now(self._timezone) - timedelta(minutes=_initage)
            if not self._items[item]['interpolation'].get('itemtype') == 'bool':
                try:
                    _value = float(_value)
                except ValueError:
                    pass
            cond1 = _inittime - _timediff.timestamp() * 1000.0 >= 0
            cond2 = _interpolation.lower() in ['cubic', 'linear']
            cond3 = _initialized is False
            cond4 = _initage > 0
            cond5 = isinstance(_value, float)
            cond6 = caller != 'set' and _caller != "dry_run"
            self._itpl[item] = OrderedDict(itpl_list)
            if not cond2 and cond3 and cond4:
                self.logger.info(f'Looking if there was a value set after {_timediff} for item {item}')
                self._items[item]['interpolation']['initialized'] = True
                self._update_item(item, 'UZSU Plugin', 'init')
            if cond1 and not cond2 and cond3 and cond6:
                self._set(item=item, value=_initvalue, caller=_caller)
                self.logger.info(f'Updated item {item} on startup with value {_initvalue} from time {datetime.fromtimestamp(_inittime/1000.0)}')
            _itemtype = self._items[item]['interpolation'].get('itemtype')
            if cond2 and _interval < 1:
                self.logger.warning(f'Interpolation is set to {_interpolation} but interval is {_interval}. Ignoring interpolation')
            elif cond2 and _itemtype not in ['num']:
                self.logger.warning(f'Interpolation is set to {item} but type of item {_interpolation} is {_itemtype}. Ignoring interpolation and setting UZSU interpolation to none.')
                _reset_interpolation = True
            elif _interpolation.lower() in ('cubic', 'linear') and _interval > 0:
                try:
                    _nextinterpolation = datetime.now(self._timezone) + timedelta(minutes=_interval)
                    _next = _nextinterpolation if _next > _nextinterpolation else _next
                    _value = self._interpolate(self._itpl[item], _next.timestamp() * 1000.0, _interpolation.lower() == 'linear')
                    _value_now = self._interpolate(self._itpl[item], entry_now, _interpolation.lower() == 'linear')
                    if _caller != "dry_run":
                        self._set(item=item, value=_value_now, caller=_caller)
                    self.logger.info(f'Updated: {item}, {_interpolation.lower()} interpolation value: {_value_now}, based on dict: {self._itpl[item]}. Next: {_next}, value: {_value}')
                except Exception as e:
                    self.logger.error(f'Error {_interpolation.lower()} interpolation for item {item} with interpolation list {self._itpl[item]}: {e}')
            if cond5 and _value < 0:
                self.logger.warning(f'value {_value} for item "{item}" is negative. This might be due to not enough values set in the UZSU.')
            if _reset_interpolation is True:
                self._items[item]['interpolation']['type'] = 'none'
                self._update_item(item, 'UZSU Plugin', 'reset_interpolation')
            if _caller != "dry_run":
                self.logger.debug(f'will add scheduler named uzsu_{item.property.path} with datetime {_next} and tzinfo {_next.tzinfo} and value {_value}')
                self._planned.update({item: {'value': _value, 'next': _next.strftime('%Y-%m-%d %H:%M')}})
                self._webdata['items'][item.property.path].update({'planned': {'value': _value, 'time': _next.strftime('%d.%m.%Y %H:%M')}})
                self._update_count['done'] = self._update_count.get('done', 0) + 1
                self.scheduler_add(item.property.path, self._set,
                                   value={'item': item, 'value': _value, 'caller': 'Scheduler'}, next=_next)
                if self._update_count.get('done') == self._update_count.get('todo'):
                    self.scheduler_trigger('uzsu_sunupdate', by='UZSU Plugin')
                    self._update_count = {'done': 0, 'todo': 0}
        elif self._items[item].get('active') is True and self._items[item].get('list'):
            self.logger.warning(f'item "{item}" is active but has no active entries.')
            self._planned.update({item: None})
            self._webdata['items'][item.property.path].update({'planned': {'value': '-', 'time': '-'}})

    def _set(self, item=None, value=None, caller=None):
        """
        This function sets the specific item
        :param item:    item to be updated towards the plugin
        :param value:   value the item should be set to
        :param caller:  if given it represents the callers name
        """
        _uzsuitem, _itemvalue = self._get_dependant(item)
        _uzsuitem(value, 'UZSU Plugin', 'set')
        self._webdata['items'][item.property.path].update({'depend': {'item': _uzsuitem.property.path, 'value': str(_itemvalue)}})
        if not caller or caller == "Scheduler":
            self._schedule(item, caller='set')

    def _get_time(self, entry, timescan, item=None, entryindex=None, caller=None):
        """
        Returns the next and previous execution time and value
        :param entry:       a dictionary that may contain the following keys:
                            value
                            active
                            date
                            rrule
                            dtstart
        :param item:        item to be updated towards the plugin
        :param timescan:    defines whether to find values in the future or past
        :param caller:      defines the caller of the method. If it's name is dry_run just
                            simulate getting time even if entry is not active
        """
        try:
            time = entry['time']
        except Exception:
            time = None
        try:
            if not isinstance(entry, dict):
                return None, None
            if 'value' not in entry:
                return None, None
            if 'active' not in entry:
                return None, None
            if 'time' not in entry:
                return None, None
            value = entry['value']
            next = None
            active = True if caller == "dry_run" else entry['active']
            today = datetime.today()
            tomorrow = today + timedelta(days=1)
            yesterday = today - timedelta(days=1)
            weekbefore = today - timedelta(days=7)
            time = entry['time']
            if not active:
                return None, None
            if 'rrule' in entry and 'series' not in time:
                if entry['rrule'] == '':
                    entry['rrule'] = 'FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR,SA,SU'
                if 'dtstart' in entry:
                    rrule = rrulestr(entry['rrule'], dtstart=entry['dtstart'])
                else:
                    try:
                        rrule = rrulestr(entry['rrule'], dtstart=datetime.combine(
                            weekbefore, parser.parse(time.strip()).time()))
                        rstr = str(rrule).replace('\n', ';')
                        self.logger.debug(f"Created rrule: '{rstr}'' for time:'{time}'")
                    except ValueError:
                        self.logger.debug(f"Could not create a rrule from rrule: '{entry['rrule']}' and time:'{time}'")
                        if 'sun' in time:
                            rrule = rrulestr(entry['rrule'], dtstart=datetime.combine(
                                weekbefore, self._sun(datetime.combine(weekbefore.date(),
                                                                       datetime.min.time()).replace(tzinfo=self._timezone),
                                                      time, timescan).time()))
                            rstr = str(rrule).replace('\n', ';')
                            self.logger.debug(f'Looking for {timescan} sun-related time. Found rrule: {rstr}')
                        else:
                            rrule = rrulestr(entry['rrule'], dtstart=datetime.combine(weekbefore, datetime.min.time()))
                            rstr = str(rrule).replace('\n', ';')
                            self.logger.debug(f'Looking for {timescan} time. Found rrule: {rstr}')
                dt = datetime.now()
                while self.alive:
                    dt = rrule.before(dt) if timescan == 'previous' else rrule.after(dt)
                    if dt is None:
                        return None, None
                    if 'sun' in time:
                        sleep(0.01)
                        next = self._sun(datetime.combine(dt.date(),
                                                          datetime.min.time()).replace(tzinfo=self._timezone),
                                         time, timescan)
                        self.logger.debug(f'Result parsing time (rrule) {time}: {next}')
                        if entryindex is not None and timescan == 'next':
                            self._update_suncalc(item, entry, entryindex, next.strftime("%H:%M"))
                    else:
                        next = datetime.combine(dt.date(), parser.parse(time.strip()).time()).replace(tzinfo=self._timezone)
                        self._update_suncalc(item, entry, entryindex, None)
                    if next and next.date() == dt.date():
                        self._itpl[item][next.timestamp() * 1000.0] = value
                        if next - timedelta(seconds=1) > datetime.now().replace(tzinfo=self._timezone):
                            self.logger.debug(f'Return from rrule {timescan}: {next}, value {value}.')
                            return next, value
                        else:
                            self.logger.debug(f"Not returning {timescan} rrule {next} because it's in the past.")
            if 'sun' in time and 'series' not in time:
                next = self._sun(datetime.combine(today, datetime.min.time()).replace(
                    tzinfo=self._timezone), time, timescan)
                cond_future = next > datetime.now(self._timezone)
                if cond_future:
                    self.logger.debug(f'Result parsing time today (sun) {time}: {next}')
                    if entryindex is not None:
                        self._update_suncalc(item, entry, entryindex, next.strftime("%H:%M"))
                else:
                    self._itpl[item][next.timestamp() * 1000.0] = value
                    self.logger.debug(f'Include previous today (sun): {next}, value {value} for interpolation.')
                    if entryindex:
                        self._update_suncalc(item, entry, entryindex, next.strftime("%H:%M"))
                    next = self._sun(datetime.combine(tomorrow, datetime.min.time()).replace(
                        tzinfo=self._timezone), time, timescan)
                    self.logger.debug(f'Result parsing time tomorrow (sun) {time}: {next}')
            elif 'series' not in time:
                next = datetime.combine(today, parser.parse(time.strip()).time()).replace(tzinfo=self._timezone)
                cond_future = next > datetime.now(self._timezone)
                if not cond_future:
                    self._itpl[item][next.timestamp() * 1000.0] = value
                    self.logger.debug(f'Include {timescan} today: {next}, value {value} for interpolation.')
                    next = datetime.combine(tomorrow, parser.parse(time.strip()).time()).replace(tzinfo=self._timezone)
            if 'series' in time:
                # Get next Time for Series
                next = self._series_get_time(entry, timescan)
                if next is None:
                    return None, None
                self._itpl[item][next.timestamp() * 1000.0] = value
                rstr = str(rrule).replace('\n', ';')
                self.logger.debug(f'Looking for {timescan} series-related time. Found rrule: {rstr} with start-time {entry["series"]["timeSeriesMin"]}')

            cond_today = False if next is None else next.date() == today.date()
            cond_yesterday = False if next is None else next.date() - timedelta(days=1) == yesterday.date()
            cond_tomorrow = False if next is None else next.date() == tomorrow.date()
            cond_next = False if next is None else next > datetime.now(self._timezone)
            cond_previous_today = False if next is None else next - timedelta(seconds=1) < datetime.now(self._timezone)
            cond_previous_yesterday = False if next is None else next - timedelta(days=1) < datetime.now(self._timezone)
            if next and cond_today and cond_next:
                self._itpl[item][next.timestamp() * 1000.0] = value
                self.logger.debug(f'Return next today: {next}, value {value}')
                return next, value
            if next and cond_tomorrow and cond_next:
                self._itpl[item][next.timestamp() * 1000.0] = value
                self.logger.debug(f'Return next tomorrow: {next}, value {value}')
                return next, value
            if 'series' in time and next and cond_next:
                self.logger.debug(f'Return next for series: {next}, value {value}')
                return next, value
            if next and cond_today and cond_previous_today:
                self._itpl[item][(next - timedelta(seconds=1)).timestamp() * 1000.0] = value
                self.logger.debug(f'Not returning previous today {next} because it‘s in the past.')
            if next and cond_yesterday and cond_previous_yesterday:
                self._itpl[item][(next - timedelta(days=1)).timestamp() * 1000.0] = value
                self.logger.debug(f'Not returning previous yesterday {next} because it‘s in the past.')
        except Exception as e:
            self.logger.error(f'Error "{time}" parsing time: {e}')
        return None, None

    def _series_calculate(self, item, caller=None, source=None):
        """
                Calculate serie-entries for next 168 hour (7 days) - from now to now-1 second
                and writes the list to "seriesCalculated" in item
                :param item:      an item with series entry
                :param caller:    caller of the method
                :param source:    source of the method caller
                :return:          True if everything went smoothly, otherwise False
        """
        self.logger.debug(f'Series Calculate method for item {item} called by {caller}. Source: {source}')
        if not self._items[item].get('list'):
            issue = f'No list entry in UZSU dict for item {item}'
            return issue
        try:
            mydays = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']
            for i, mydict in enumerate(self._items[item]['list']):
                try:
                    del mydict['seriesCalculated']
                except Exception:
                    pass
                if mydict.get('series', None) is None:
                    continue
                try:
                    #####################
                    seriesbegin, seriesend, daycount, mydict = self._fix_empty_values(mydict)
                    interval = mydict['series'].get('timeSeriesIntervall', None)
                    seriesstart = seriesbegin
                    endtime = None

                    if interval is None or interval == "":
                        issue = f'Could not calculate serie for item {item} - because interval is None - {mydict}'
                        self.logger.warning(issue)
                        return issue

                    if (daycount == '' or daycount is None) and seriesend is None:
                        issue = "Could not calculate series because timeSeriesCount is NONE and TimeSeriesMax is NONE"
                        self.logger.warning(issue)
                        return issue

                    interval = int(interval.split(":")[0]) * 60 + int(mydict['series']['timeSeriesIntervall'].split(":")[1])

                    if interval == 0:
                        issue = f'Could not calculate serie because interval is ZERO - {mydict}'
                        self.logger.warning(issue)
                        return issue

                    if daycount is not None and daycount != '':
                        if int(daycount) * interval >= 1440:
                            org_daycount = daycount
                            daycount = int(1439 / interval)
                            self.logger.warning(f'Cut your SerieCount to {daycount} - because interval {interval} x SerieCount {org_daycount} is more than 24h')

                    if 'sun' not in mydict['series']['timeSeriesMin']:
                        starttime = datetime.strptime(mydict['series']['timeSeriesMin'], "%H:%M")
                    else:
                        mytime = self._sun(datetime.now().replace(hour=0, minute=0, second=0).astimezone(self._timezone), seriesstart, "next")
                        starttime = (f'{mytime.hour:02d}:{mytime.minute:02d}')
                        starttime = datetime.strptime(starttime, "%H:%M")

                    # calculate End of Serie by Count
                    if seriesend is None:
                        endtime = starttime
                        endtime += timedelta(minutes=interval * int(daycount))

                    if seriesend is not None and 'sun' in seriesend:
                        mytime = self._sun(datetime.now().replace(hour=0, minute=0, second=0).astimezone(self._timezone), seriesend, "next")
                        endtime = (f'{mytime.hour:02d}:{mytime.minute:02d}')
                        endtime = datetime.strptime(endtime, "%H:%M")
                    elif seriesend is not None and 'sun' not in seriesend:
                        endtime = datetime.strptime(seriesend, "%H:%M")

                    if seriesend is None and endtime:
                        seriesend = str(endtime.time())[:5]

                    if not endtime:
                        endtime = starttime

                    if endtime <= starttime:
                        endtime += timedelta(days=1)

                    timediff = endtime - starttime
                    original_daycount = daycount

                    if daycount is None:
                        daycount = int(timediff.total_seconds() / 60 / interval)
                    else:
                        new_daycount = int(timediff.total_seconds() / 60 / interval)
                        if int(daycount) > new_daycount:
                            self.logger.warning(f'Cut your SerieCount to {new_daycount} - because interval {interval} x SerieCount {daycount} is not possible between {starttime} and {endtime}')
                            daycount = new_daycount

                    #####################
                    # advanced rule including all sun times, start and end times  and calculated max counts, etc.
                    rrule = rrulestr(mydict['rrule'] + ";COUNT=7",
                                     dtstart=datetime.combine(datetime.now(),
                                     parser.parse(str(starttime.hour) + ':' +
                                     str(starttime.minute)).time()))
                    mynewlist = []

                    interval = int(mydict['series']['timeSeriesIntervall'].split(":")[0]) * 60 + \
                        int(mydict['series']['timeSeriesIntervall'].split(":")[1])
                    exceptions = 0
                    for day in list(rrule):
                        if not mydays[day.weekday()] in mydict['rrule']:
                            continue
                        myrulenext = f'FREQ=MINUTELY;COUNT={daycount};INTERVAL={interval}'

                        if 'sun' not in mydict['series']['timeSeriesMin']:
                            starttime = datetime.strptime(mydict['series']['timeSeriesMin'], "%H:%M")
                        else:
                            seriesstart = mydict['series']['timeSeriesMin']
                            mytime = self._sun(day.replace(hour=0, minute=0, second=0).astimezone(self._timezone),
                                               seriesstart, "next")
                            starttime = (f'{mytime.hour:02d}:{mytime.minute:02d}')
                            starttime = datetime.strptime(starttime, "%H:%M")
                        dayrule = rrulestr(myrulenext, dtstart=day.replace(hour=starttime.hour,
                                                                           minute=starttime.minute, second=0))
                        dayrule.after(day.replace(hour=0, minute=0))    # First Entry for this day
                        count = 0

                        try:
                            actday = mydays[list(dayrule)[0].weekday()]
                        except Exception:
                            max_interval = endtime - starttime
                            if exceptions == 0:
                                self.logger.info(f'Item {item}: Between starttime {datetime.strftime(starttime, "%H:%M")} and endtime {datetime.strftime(endtime, "%H:%M")} is a maximum valid interval of {max_interval.seconds // 3600:02d}:{max_interval.seconds % 3600//60:02d}. {mydict["series"]["timeSeriesIntervall"]} is set too high for a continuous series trigger. The UZSU will only be scheduled for the start time.')
                            exceptions += 1
                            max_interval = int(max_interval.total_seconds() / 60)
                            myrulenext = f'FREQ=MINUTELY;COUNT=1;INTERVAL={max_interval}'
                            dayrule = rrulestr(myrulenext, dtstart=day.replace(hour=starttime.hour,
                                                                               minute=starttime.minute, second=0))
                            dayrule.after(day.replace(hour=0, minute=0))
                            actday = mydays[day.weekday()] if list(dayrule) is None else mydays[list(dayrule)[0].weekday()]
                        seriestarttime = None
                        for time in list(dayrule):
                            if mydays[time.weekday()] != actday:
                                if seriestarttime is not None:
                                    mytpl = {'seriesMin': str(seriestarttime.time())[:5]}
                                    if original_daycount is not None:
                                        mytpl['seriesMax'] = str((seriestarttime + timedelta(minutes=interval * count)).time())[:5]
                                    else:
                                        mytpl['seriesMax'] = f'{endtime.hour:02d}:{endtime.minute:02d}'
                                    mytpl['seriesDay'] = actday
                                    mytpl['maxCountCalculated'] = count if exceptions == 0 else 0
                                    self.logger.debug(f'Mytpl: {mytpl}, count {count}, daycount {daycount}, interval {interval}')
                                    mynewlist.append(mytpl)
                                count = 0
                                seriestarttime = None
                                actday = mydays[time.weekday()]
                            if time.time() < datetime.now().time() and time.date() <= datetime.now().date():
                                continue
                            if time >= datetime.now() + timedelta(days=7):
                                continue
                            if seriestarttime is None:
                                seriestarttime = time
                            count += 1
                        # add the last Time for this day
                        if seriestarttime is not None:
                            mytpl = {'seriesMin': str(seriestarttime.time())[:5]}
                            if original_daycount is not None:
                                mytpl['seriesMax'] = str((seriestarttime + timedelta(minutes=interval * count)).time())[:5]
                            else:
                                mytpl['seriesMax'] = f'{endtime.hour:02d}:{endtime.minute:02d}'
                            mytpl['maxCountCalculated'] = count if exceptions == 0 else 0
                            mytpl['seriesDay'] = actday
                            self.logger.debug(f'Mytpl for last time of day: {mytpl}, count {count} daycount {original_daycount}, interval {interval}')
                            mynewlist.append(mytpl)

                    if mynewlist:
                        self._items[item]['list'][i]['seriesCalculated'] = mynewlist
                        self.logger.debug(f'Series for item {item} calculated: {self._items[item]["list"][i]["seriesCalculated"]}')
                except Exception as e:
                    self.logger.warning(f'Error: {e}. Series entry {mydict} for item {item} could not be calculated. Skipping series calculation')
                    continue
            return True

        except Exception as e:
            self.logger.warning(f'Series for item {item} could not be calculated for list {self._items[item]["list"]}. Error: {e}')

    def _get_sun4week(self, item, caller=None):
        """
        Getting the values for sunrise and sunset for the whole upcoming 7 days - relevant for time series
        :param item:    uzsu item
        :type item:     item
        :param caller:  Method calling this method
        :type caller:   string
        :return:        True at the end of the method
        """
        dayrule = rrulestr("FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR,SA,SU" + ";COUNT=7",
                           dtstart=datetime.now().replace(hour=0, minute=0, second=0))
        self.logger.debug(f'Get sun4week for item {item} called by {caller}')
        mynewdict = {'sunrise': {}, 'sunset': {}}
        for day in (list(dayrule)):
            actday = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU'][day.weekday()]
            mysunrise = self._sun(day.astimezone(self._timezone), "sunrise", "next")
            mysunset = self._sun(day.astimezone(self._timezone), "sunset", "next")
            mynewdict['sunrise'][actday] = (f'{mysunrise.hour:02d}:{mysunrise.minute:02d}')
            mynewdict['sunset'][actday] = (f'{mysunset.hour:02d}:{mysunset.minute:02d}')
        self._items[item]['SunCalculated'] = mynewdict
        return True

    def _fix_empty_values(self, mydict):
        daycount = mydict['series'].get('timeSeriesCount', None)
        seriesend = mydict['series'].get('timeSeriesMax', None)
        seriesbegin = mydict['series'].get('timeSeriesMin', None)
        # Fix empty values in series dict
        if seriesbegin == '':
            self.logger.warning("No starttime for series set. Setting it to midnight 00:00")
            seriesbegin = '00:00'
            mydict['series']['timeSeriesMin'] = seriesbegin
        if seriesend == '':
            self.logger.warning("No endtime for series set. Setting it to midnight 23:59")
            seriesend = '23:59'
            mydict['series']['timeSeriesMax'] = seriesend
        if daycount == '':
            self.logger.warning("No count for series set. Setting it to 1")
            daycount = '1'
            mydict['series']['timeSeriesCount'] = daycount
        return seriesbegin, seriesend, daycount, mydict

    def _series_get_time(self, mydict, timescan=''):
        """
                Returns the next time/date for a serie
                :param mydict:      list-Item from UZSU-dict
                :param timescan:    direction to search for next/previous
        """

        returnvalue = None
        seriesbegin, seriesend, daycount, mydict = self._fix_empty_values(mydict)
        interval = mydict['series'].get('timeSeriesIntervall', None)
        seriesstart = seriesbegin

        if interval is not None and interval != "":
            interval = int(interval.split(":")[0]) * 60 + int(mydict['series']['timeSeriesIntervall'].split(":")[1])
        else:
            return returnvalue
        if interval == 0:
            self.logger.warning(f'Could not calculate serie because interval is ZERO - {mydict}')
            return returnvalue

        if 'sun' not in mydict['series']['timeSeriesMin']:
            starttime = datetime.strptime(mydict['series']['timeSeriesMin'], "%H:%M")
        else:
            mytime = self._sun(datetime.now().replace(hour=0, minute=0, second=0).astimezone(self._timezone),
                               seriesstart, "next")
            starttime = f'{mytime.hour:02d}:{mytime.minute:02d}'
            starttime = datetime.strptime(starttime, "%H:%M")

        if daycount is None and seriesend is not None:
            if 'sun' in seriesend:
                mytime = self._sun(datetime.now().replace(hour=0, minute=0, second=0).astimezone(self._timezone),
                                   seriesend, "next")
                seriesend = (f'{mytime.hour:02d}:{mytime.minute:02d}')
                endtime = datetime.strptime(seriesend, "%H:%M")
            else:
                endtime = datetime.strptime(seriesend, "%H:%M")
            if endtime < starttime:
                endtime += timedelta(days=1)
            timediff = endtime - starttime
            daycount = int(timediff.total_seconds() / 60 / interval)
        else:
            if seriesend is None:
                endtime = starttime
                endtime += timedelta(minutes=interval * int(daycount))
                timediff = endtime - starttime
                daycount = int(timediff.total_seconds() / 60 / interval)
            else:
                endtime = datetime.strptime(seriesend, "%H:%M")
                timediff = endtime - starttime

        if daycount is not None and daycount != '':
            if seriesend is None and (int(daycount) * interval >= 1440):
                org_count = daycount
                count = int(1439 / interval)
                self.logger.warning(f'Cut your SerieCount to {count} - because interval {interval} x SerieCount {org_count} is more than 24h')
            else:
                new_daycount = int(timediff.total_seconds() / 60 / interval)
                if int(daycount) > new_daycount:
                    self.logger.warning(f'Cut your SerieCount to {new_daycount} - because interval {interval} x SerieCount {daycount} is not possible between {datetime.strftime(starttime, "%H:%M")} and {datetime.strftime(endtime, "%H:%M")}')
                    daycount = new_daycount
        mylist = OrderedDict()
        actrrule = mydict['rrule'] + ';COUNT=9'
        rrule = rrulestr(
            actrrule,
            dtstart=datetime.combine(datetime.now() - timedelta(days=7),
            parser.parse(str(starttime.hour) + ':' + str(starttime.minute)).time())
        )
        for day in list(rrule):
            mycount = 1
            timestamp = day
            mylist[timestamp] = 'x'
            while mycount < daycount:
                timestamp = timestamp + timedelta(minutes=interval)
                mylist[timestamp] = 'x'
                mycount += 1

        now = datetime.now()
        mylist[now] = 'now'
        mysortedlist = sorted(mylist)
        myindex = mysortedlist.index(now)
        if timescan == 'next':
            returnvalue = mysortedlist[myindex + 1]
        else:
            returnvalue = mysortedlist[myindex - 1]

        # Get correct "sun" for this Day
        if 'sun' in mydict['series']['timeSeriesMin'] and returnvalue is not None:
            mytime = self._sun(returnvalue.replace(hour=0, minute=0, second=0).astimezone(self._timezone),
                               mydict['series']['timeSeriesMin'], "next")
            delta_dt1 = returnvalue.replace(hour=mytime.hour, minute=mytime.minute, second=0)
            delta_dt2 = returnvalue.replace(hour=starttime.hour, minute=starttime.minute, second=0)
            delta_time = delta_dt1.minute - delta_dt2.minute
            returnvalue += timedelta(minutes=delta_time)
        if returnvalue is not None:
            returnvalue = returnvalue.replace(tzinfo=self._timezone)

        return returnvalue

    def _sun(self, dt, tstr, timescan):
        """
        parses a given string with a time range to determine its timely boundaries and
        returns a time
        :param dt:          contains a datetime object,
        :param tstr:        contains a string with '[H:M<](sunrise|sunset)[+|-][offset][<H:M]' like e.g. '6:00<sunrise<8:00'
        :param timescan:    defines whether to find values in the future or past, for logging purposes
        :return:            the calculated date and time in timezone aware format
        """

        self.logger.debug(f'Given param dt={dt}, tz={dt.tzinfo} for {timescan}')

        # now start into parsing details
        self.logger.debug(f'Examine param time string: {tstr}')

        # find min/max times
        tabs = tstr.split('<')
        if len(tabs) == 1:
            smin = None
            cron = tabs[0].strip()
            smax = None
        elif len(tabs) == 2:
            if tabs[0].startswith('sun'):
                smin = None
                cron = tabs[0].strip()
                smax = tabs[1].strip()
            else:
                smin = tabs[0].strip()
                cron = tabs[1].strip()
                smax = None
        elif len(tabs) == 3:
            smin = tabs[0].strip()
            cron = tabs[1].strip()
            smax = tabs[2].strip()
        else:
            self.logger.error(f'Wrong syntax: {tstr} - wrong amount of tabs. Should be [H:M<](sunrise|sunset)[+|-][offset][<H:M]')
            return
        # calculate the time offset
        doff = 0  # degree offset
        moff = 0  # minute offset
        _, op, offs = cron.rpartition('+')
        if op:
            if offs.endswith('m'):
                moff = int(offs.strip('m'))
            else:
                doff = float(offs)
        else:
            _, op, offs = cron.rpartition('-')
            if op:
                if offs.endswith('m'):
                    moff = -int(offs.strip('m'))
                else:
                    doff = -float(offs)
        # see if sunset or sunrise are included in give tstr param
        dmin = None
        dmax = None
        if cron.startswith('sunrise'):
            next_time = self._sh.sun.rise(doff, moff, dt=dt)
            self.logger.debug(f'{timescan} time for sunrise: {next_time}')
            # time in next_time will be in utctime. So we need to adjust it
            if next_time.tzinfo == tzutc():
                next_time = next_time.astimezone(self._timezone)
            else:
                self.logger.warning("next_time.tzinfo was not given as utc!")
            self.logger.debug(f'next_time.tzinfo gives {next_time.tzinfo}')
            self.logger.debug(f'Sunrise is included and calculated as {next_time}')
        elif cron.startswith('sunset'):
            next_time = self._sh.sun.set(doff, moff, dt=dt)
            self.logger.debug(f'{timescan} time for sunset: {next_time}')
            # time in next_time will be in utctime. So we need to adjust it
            if next_time.tzinfo == tzutc():
                next_time = next_time.astimezone(self._timezone)
            else:
                self.logger.warning("next_time.tzinfo was not given as utc!")
            self.logger.debug(f'Sunset is included and calculated as {next_time}')
        else:
            self.logger.error(f'Wrong syntax: {tstr} not starting with sunrise/set. Should be [H:M<](sunrise|sunset)[+|-][offset][<H:M]')
            return
        if smin is not None:
            h, _, m = smin.partition(':')
            try:
                dmin = next_time.replace(day=dt.day, hour=int(h), minute=int(m), second=0, tzinfo=self._timezone)
            except Exception as err:
                self.logger.error(f'Problems assigning dmin: {err}. Wrong syntax: {tstr}. Should be [H:M<](sunrise|sunset)[+|-][offset][<H:M]')
                return
        elif smax is None:
            dmin = next_time
        if smax is not None:
            h, _, m = smax.partition(':')
            try:
                dmax = next_time.replace(day=dt.day, hour=int(h), minute=int(m), second=0, tzinfo=self._timezone)
            except Exception as err:
                self.logger.error(f'Problems assigning dmax: {err}. Wrong syntax: {tstr}. Should be [H:M<](sunrise|sunset)[+|-][offset][<H:M]')
                return
        elif smin is None:
            dmax = next_time
        if dmin is not None and dmax is not None and dmin > dmax:
            self.logger.error(f'Wrong times: the earliest time should be smaller than the latest time in {tstr}')
            return
        try:
            next_time = max(dmin, next_time)
        except Exception:
            pass
        try:
            next_time = min(dmax, next_time)
        except Exception:
            pass
        return next_time

    def _get_dependant(self, item):
        """
        Getting the value of the dependent item for the webif
        :param item:    uzsu item
        :type item:     item
        :return:        The item value of the item that is changed
        """
        try:
            _uzsuitem = self.itemsApi.return_item(self.get_iattr_value(item.conf, ITEM_TAG[0]))
        except Exception as err:
            self.logger.warning(f'Item to be queried "{self.get_iattr_value(item.conf, ITEM_TAG[0])}" does not exist. Error: {err}')
            return

        try:
            _itemvalue = _uzsuitem()
        except Exception as err:
            _itemvalue = None
            self.logger.warning(f'Item to be queried "{self.get_iattr_value(item.conf, ITEM_TAG[0])}" does not have a type attribute. Error: {err}')
        return _uzsuitem, _itemvalue

    def get_itemdict(self, item):
        """
        Getting a sorted item list with uzsu config
        :item:          uzsu item
        :return:        sanitized dict from uzsu item
        """

        return html.escape(json.dumps(self._items[item]))

    def get_items(self):
        """
        Getting a sorted item list with uzsu config

        :return:        sorted itemlist
        """
        sortedlist = sorted([k.property.path for k in self._items.keys()])
        finallist = []
        for i in sortedlist:
            finallist.append(self.itemsApi.return_item(i))
        return finallist
