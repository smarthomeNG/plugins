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

import logging
import functools
from lib.model.smartplugin import *
from lib.item import Items
from lib.shtime import Shtime

from datetime import datetime, timedelta
from time import sleep
from dateutil.rrule import rrulestr
from dateutil import parser
from dateutil.tz import tzutc
from unittest import mock
from collections import OrderedDict
import copy
import html
import json
from .webif import WebInterface
from scipy import interpolate

ITEM_TAG = ['uzsu_item']


class UZSU(SmartPlugin):
    """
    Main class of the UZSU Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    ALLOW_MULTIINSTANCE = False

    PLUGIN_VERSION = "1.6.6"      # item buffer for all uzsu enabled items

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
        self.logger.info("Init with timezone {}".format(self._timezone))

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
            self._webdata['items'][item.id()].update({'lastvalue': '-'})
            self._update_item(item, 'UZSU Plugin', 'run')
            cond1 = self._items[item].get('active') and self._items[item]['active'] is True
            cond2 = self._items[item].get('list')
            if cond1 and cond2:
                self._update_count['todo'] = self._update_count.get('todo') + 1
        self.logger.debug("Going to update {} items from {}".format(self._update_count['todo'], list(self._items.keys())))

        for item in self._items:
            cond1 = self._items[item].get('active') is True
            cond2 = self._items[item].get('list')
            # remove lastvalue dict entry, it is not used anymore
            try:
                self._items[item].pop('lastvalue')
                self._update_item(item, 'UZSU Plugin', 'lastvalue removed')
                self.logger.debug("Item '{}': removed lastvalue dict entry as it is deprecated.".format(item))
            except Exception:
                pass
            self._check_rruleandplanned(item)
            if cond1 and cond2:
                self._schedule(item, caller='run')
            elif cond1 and not cond2:
                self.logger.warning("Item '{}' is active but has no entries.".format(item))
                self._planned.update({item: None})
                self._webdata['items'][item.id()].update({'planned': {'value': '-', 'time': '-'}})
            else:
                self.logger.debug("Not scheduling item {}, cond1 {}, cond2 {}".format(item, cond1, cond2))
                self.logger.info('Dry run of scheduler calculation for item {}'
                                 'to get calculated sunset/rise entries'.format(item))
                self._schedule(item, caller='dry_run')

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("stop method called")
        self.scheduler_remove('uzsu_sunupdate')
        for item in self._items:
            try:
                self.scheduler_remove('{}'.format(item.property.path))
                self.logger.debug('Removing scheduler for item {}'.format(item.property.path))
            except Exception as err:
                self.logger.debug('Scheduler for item {} not removed. Problem: {}'.format(item.property.path, err))
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
                self.logger.debug('Updating sun info for item {}. Caller: {}'.format(item, caller))
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
            self._items[item]['sunrise'] = '{:02}:{:02}'.format(_sunrise.hour, _sunrise.minute)
            self._items[item]['sunset'] = '{:02}:{:02}'.format(_sunset.hour, _sunset.minute)
            self.logger.debug('Updated sun entries for item {}, triggered by {}. sunrise: {}, sunset: {}'.format(
                item, caller, self._items[item]['sunrise'], self._items[item]['sunset']))
            success = True
        except Exception as e:
            success = "Not updated sun entries for item {}. Error {}".format(item, e)
            self.logger.debug(success)
        return success

    def _update_suncalc(self, item, entry, entryindex, entryvalue):
        update = False
        if entry.get('calculated'):
            update = True if entry == self._items[item]['list'][entryindex] else update
            with mock.patch.dict(entry, calculated=entryvalue):
                update = True if entry == self._items[item]['list'][entryindex] else update
        else:
            update = True
        if entry.get('calculated') and entryvalue is None:
            self.logger.debug("No sunset/rise in time for current entry {}. Removing calculated value.".format(entry))
            self._items[item]['list'][entryindex].pop('calculated')
            self._update_item(item, 'UZSU Plugin', 'update_sun')
        elif update is True and not entry.get('calculated') == entryvalue:
            self.logger.debug("Updated calculated time for item {} entry {} with value {}.".format(
                item, self._items[item]['list'][entryindex], entryvalue))
            self._items[item]['list'][entryindex]['calculated'] = entryvalue
            self._update_item(item, 'UZSU Plugin', 'update_sun')
        elif entry.get('calculated'):
            self.logger.debug("Sun calculation {} entry not updated for item {} with value {}".format(
                entryvalue, item, entry.get('calculated')))

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
            self.logger.warning("Item to be set by uzsu '{}' does not exist. Error: {}".format(_itemforuzsu, err))
        try:
            _itemtype = _uzsuitem.property.type
        except Exception as err:
            try:
                _itemtype = _uzsuitem.type()
            except Exception:
                _itemtype = 'foo' if _uzsuitem is not None else None
            if _itemtype is None:
                self.logger.warning("Item to be set by uzsu '{}' does not exist. Error: {}".format(_itemforuzsu, err))
            else:
                self.logger.warning("Item to be set by uzsu '{}' does not have a type attribute."
                                    "Error: {}".format(_itemforuzsu, err))
        return _itemtype

    def _logics_lastvalue(self, by=None, item=None):
        if self._items.get(item):
            lastvalue = self._lastvalues.get(item)
        else:
            lastvalue = None
        by_test = " Queried by {}".format(by) if by is not None else ""
        self.logger.debug("Last value of item {} is: {}.{}".format(item, lastvalue, by_test))
        return lastvalue

    def _logics_resume(self, activevalue=True, item=None):
        self._logics_activate(True, item)
        lastvalue = self._logics_lastvalue(item)
        self._set(item=item, value=lastvalue, caller='logic')
        self.logger.info("Resuming item {}: Activated and value set to {}."
                         "Active value: {}".format(item, lastvalue, activevalue))
        return lastvalue

    def _logics_activate(self, activevalue=None, item=None):
        if isinstance(activevalue, str):
            if activevalue.lower() in ['1', 'yes', 'true', 'on']:
                activevalue = True
            elif activevalue.lower() in ['0', 'no', 'false', 'off']:
                activevalue = False
            else:
                self.logger.warning("Value to activate item '{}' has to be True or False".format(item))
        if isinstance(activevalue, bool):
            self._items[item] = item()
            self._items[item]['active'] = activevalue
            self.logger.info("Item {} is set via logic to: {}".format(item, activevalue))
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
            self.logger.info("Item {} interpolation is set via logic to: type={}, interval={}, backintime={}".format(
                item, intpl_type, abs(interval), backintime))
            self._update_item(item, 'UZSU Plugin', 'logic')
            return self._items[item].get('interpolation')

    def _logics_clear(self, clear=False, item=None):
        if isinstance(clear, str):
            if clear.lower() in ['1', 'yes', 'true', 'on']:
                clear = True
            else:
                self.logger.warning("Value to clear uzsu item '{}' has to be True".format(item))
        if isinstance(clear, bool) and clear is True:
            self._items[item].clear()
            self._items[item] = {'interpolation': {}, 'active': False}
            self.logger.info("UZSU settings for item '{}' are cleared".format(item))
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
            self.logger.info("UZSU interpolation dict for item '{}' is cleared".format(item))
            return self._itpl[item]
        else:
            self.logger.info("UZSU interpolation dict for item '{}' is: {}".format(item, self._itpl[item]))
            return self._itpl[item]

    def _logics_planned(self, item=None):
        if self._planned.get(item) not in [None, {}, 'notinit'] and self._items[item].get('active') is True:
            self.logger.info("Item '{}' is going to be set to {} at {}".format(
                item, self._planned[item]['value'], self._planned[item]['next']))
            self._webdata['items'][item.id()].update({'planned': {'value': self._planned[item]['value'],
                                                                  'time': self._planned[item]['next']}})
            return self._planned[item]
        elif self._planned.get(item) == 'notinit' and self._items[item].get('active') is True:
            self.logger.info("Item '{}' is active but not fully initialized yet.".format(item))
            return None
        elif not self._planned.get(item) and self._items[item].get('active') is True:
            self.logger.warning("Item '{}' is active but has no (active) entries.".format(item))
            self._planned.update({item: None})
            self._webdata['items'][item.id()].update({'planned': {'value': '-', 'time': '-'}})
            return None
        else:
            self.logger.info("Nothing planned for item '{}'.".format(item))
            return None

    def _add_dicts(self, item):
        """
        Method to add interpolation dict if it's not available
        :param item:    The item to process
        :type item:     item
        """
        if not self._items[item].get('interpolation'):
            self._items[item]['interpolation'] = {}
        if not self._items[item]['interpolation'].get('type'):
            self._items[item]['interpolation']['type'] = 'none'
        if not self._items[item]['interpolation'].get('initialized'):
            self._items[item]['interpolation']['initialized'] = False
        if not self._items[item]['interpolation'].get('interval'):
            self._items[item]['interpolation']['interval'] = self._interpolation_interval
        if not self._items[item]['interpolation'].get('initage'):
            self._items[item]['interpolation']['initage'] = self._backintime
        self._items[item]['plugin_version'] = self.PLUGIN_VERSION
        if not self._items[item].get('list'):
            self._items[item]['list'] = []
        if self._items[item].get('active') is None:
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
            if self._items[item].get('interpolation'):
                self._items[item]['interpolation']['initialized'] = False
            if self._items[item].get('list'):
                for entry, _ in enumerate(self._items[item]['list']):
                    self._items[item]['list'][entry].pop('condition', None)
                    self._items[item]['list'][entry].pop('holiday', None)
                    self._items[item]['list'][entry].pop('delayedExec', None)

            self._webdata['items'].update({item.id(): {}})
            self._update_item(item, 'UZSU Plugin', 'init')
            self._planned.update({item: 'notinit'})
            self._webdata['items'][item.id()].update({'planned': {'value': '-', 'time': '-'}})

            return self.update_item

    def _remove_dupes(self, item):
        self._items[item]['list'] = [i for n, i in enumerate(self._items[item]['list'])
                                     if i not in self._items[item]['list'][:n]]
        self.logger.debug('Removed duplicate entries for item {}.'.format(item))
        compare_entries = item.prev_value()
        if compare_entries.get('list'):
            newentries = []
            [newentries.append(i) for i in self._items[item]['list'] if i not in compare_entries['list']]
            self.logger.debug('Got update for item {}: {}'.format(item, newentries))
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
                            self.logger.warning("Set old entry for item '{}' at {} with value {} to inactive"
                                                " because newer active entry with value {} found.".format(
                                                    item, time, oldvalue, newvalue))

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
                        self.logger.warning("Error creating rrule: {}".format(err))
            if count > 0:
                self.logger.debug("Updated {} rrule entries for item: {}".format(count, item))
                self._update_item(item, 'UZSU Plugin', 'create_rrule')
            if _inactive >= len(self._items[item]['list']):
                self._planned.update({item: None})
                self._webdata['items'][item.id()].update({'planned': {'value': '-', 'time': '-'}})

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        This is called by smarthome engine when the item changes, e.g. by Visu or by the command line interface
        The relevant item is put into the internal item list and registered to the scheduler
        :param item:    item to be updated towards the plugin
        :param caller:  if given it represents the callers name
        :param source:  if given it represents the source
        :param dest:    if given it represents the dest
        """
        cond = (not caller == 'UZSU Plugin') or source == 'logic'
        self.logger.debug('Update Item {}, Caller {}, Source {}, Dest {}. Will update: {}'.format(
            item, caller, source, dest, cond))
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
            self._webdata['items'][item.id()].update({'lastvalue': '-'})
            self._webdata['items'][item.id()].update({'planned': {'value': '-', 'time': '-'}})
            self.logger.debug('lastvalue for item {} set to None because UZSU is deactivated'.format(item))
        if cond:
            self._schedule(item, caller='update')
        elif 'sun' in source:
            self.logger.info('Not running dry run of scheduler calculation for item {}'
                             ' because of {} source'.format(item, source))
        else:
            self.logger.info('Dry run of scheduler calculation for item {}'
                             ' to get calculated sunset/rise entries. Source: {}'.format(item, source))
            self._schedule(item, caller='dry_run')

        if self._items[item] != self.itemsApi.return_item(str(item)) and cond:
            self._update_item(item, 'UZSU Plugin', 'update')

    def _update_item(self, item, caller="", comment=""):
        success = self._get_sun4week(item, caller="_update_item")
        if success:
            self.logger.debug('Updated weekly sun info for item {}'
                              ' caller: {} comment: {}'.format(item, caller, comment))
        else:
            self.logger.debug('Issues with updating weekly sun info'
                              ' for item {} caller: {} comment: {}'.format(item, caller, comment))
        success = self._series_calculate(item, caller, comment)
        if success is True:
            self.logger.debug('Updated seriesCalculated for item {}'
                              ' caller: {} comment: {}'.format(item, caller, comment))
        else:
            self.logger.debug('Issues with updating seriesCalculated'
                              ' for item {} caller: {} comment: {}, issue: {}'.format(item, caller, comment, success))
        success = self._update_sun(item, caller="_update_item")
        if success is True:
            self.logger.debug('Updated sunset/rise calculations for item {}'
                              ' caller: {} comment: {}'.format(item, caller, comment))
        else:
            self.logger.debug('Issues with updating sunset/rise calculations'
                              ' for item {} caller: {} comment: {}, issue: {}'.format(item, caller, comment, success))
        item(self._items[item], caller, comment)
        self._webdata['items'][item.id()].update({'interpolation': self._items[item].get('interpolation')})
        self._webdata['items'][item.id()].update({'active': str(self._items[item].get('active'))})
        #self._webdata['items'][item.id()].update({'sun': self._items[item].get('SunCalculated')})
        _suncalc = self._items[item].get('SunCalculated')
        self._webdata['items'][item.id()].update({'sun': _suncalc})
        self._webdata['sunCalculated'] = _suncalc
        self._webdata['items'][item.id()].update({'dict': self.get_itemdict(item)})
        if not comment == "init":
            _uzsuitem, _itemvalue = self._get_dependant(item)
            item_id = None if _uzsuitem is None else _uzsuitem.id()
            self._webdata['items'][item.id()].update({'depend': {'item': item_id, 'value': str(_itemvalue)}})

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
            self.scheduler_remove('{}'.format(item.property.path))
            _caller = "Scheduler:UZSU"
            self.logger.debug('Schedule Item {}, Trigger: {}, Changed by: {}'.format(
                item, caller, item.changed_by()))
        else:
            self.logger.debug('Calculate Item {}, Trigger: {}, Changed by: {}'.format(
                item, caller, item.changed_by()))
            _caller = "dry_run"
        _next = None
        _value = None
        self._update_sun(item, caller=_caller)
        self._add_dicts(item)
        if not self._items[item]['interpolation'].get('itemtype') or \
                self._items[item]['interpolation']['itemtype'] == 'none':
            self._items[item]['interpolation']['itemtype'] = self._add_type(item)
        if self._items[item].get('interpolation') is None:
            self.logger.error("Something is wrong with your UZSU item. You most likely use a"
                              " wrong smartVISU widget version!"
                              " Use the latest device.uzsu SV 2.9. or higher "
                              "If you write your uzsu dict directly please use the format given in the documentation: "
                              "https://www.smarthomeng.de/user/plugins/uzsu/user_doc.html and "
                              "include the interpolation array correctly!")
            return
        elif not self._items[item]['interpolation'].get('itemtype'):
            self.logger.error("item '{}' to be set by uzsu does not exist.".format(
                self.get_iattr_value(item.conf, ITEM_TAG[0])))
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
                    self.logger.debug("uzsu active entry for item {} with datetime {}, value {}"
                                      " and tzinfo {}".format(item, next, value, next.tzinfo))
                if _next is None:
                    _next = next
                    _value = value
                elif next and next < _next:
                    self.logger.debug("uzsu active entry for item {} using now {}, value {}"
                                      " and tzinfo {}".format(item, next, value, next.tzinfo))
                    _next = next
                    _value = value
                else:
                    self.logger.debug("uzsu active entry for item {} keep {}, value {} and tzinfo {}".format(
                        item, _next, _value, _next.tzinfo))
        elif not self._items[item].get('list') and self._items[item].get('active') is True:
            self.logger.warning("item '{}' is active but has no entries.".format(item))
            self._planned.update({item: None})
            self._webdata['items'][item.id()].update({'planned': {'value': '-', 'time': '-'}})
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
                self._webdata['items'][item.id()].update({'lastvalue': _initvalue})
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
                self.logger.info("Looking if there was a value set after {} for item {}".format(
                    _timediff, item))
                self._items[item]['interpolation']['initialized'] = True
                self._update_item(item, 'UZSU Plugin', 'init')
            if cond1 and not cond2 and cond3 and cond6:
                self._set(item=item, value=_initvalue, caller=_caller)
                self.logger.info("Updated item {} on startup with value {} from time {}".format(
                    item, _initvalue, datetime.fromtimestamp(_inittime/1000.0)))
            _itemtype = self._items[item]['interpolation'].get('itemtype')
            if cond2 and _interval < 1:
                self.logger.warning("Interpolation is set to {} but interval is {}. Ignoring interpolation".format(
                    _interpolation, _interval))
            elif cond2 and _itemtype not in ['num']:
                self.logger.warning("Interpolation is set to {} but type of item {} is {}."
                                    " Ignoring interpolation and setting UZSU interpolation to none.".format(
                                        item, _interpolation, _itemtype))
                _reset_interpolation = True
            elif _interpolation.lower() == 'cubic' and _interval > 0:
                try:
                    tck = interpolate.PchipInterpolator(list(self._itpl[item].keys()), list(self._itpl[item].values()))
                    _nextinterpolation = datetime.now(self._timezone) + timedelta(minutes=_interval)
                    _next = _nextinterpolation if _next > _nextinterpolation else _next
                    _value = round(float(tck(_next.timestamp() * 1000.0)), self._interpolation_precision)
                    _value_now = round(float(tck(entry_now)), self._interpolation_precision)
                    if _caller != "dry_run":
                        self._set(item=item, value=_value_now, caller=_caller)
                    self.logger.info("Updated: {}, cubic interpolation value: {}, based on dict: {}."
                                     " Next: {}, value: {}".format(item, _value_now, self._itpl[item], _next, _value))
                except Exception as e:
                    self.logger.error("Error cubic interpolation for item {} "
                                      "with interpolation list {}: {}".format(item, self._itpl[item], e))
            elif _interpolation.lower() == 'linear' and _interval > 0:
                try:
                    tck = interpolate.interp1d(list(self._itpl[item].keys()), list(self._itpl[item].values()))
                    _nextinterpolation = datetime.now(self._timezone) + timedelta(minutes=_interval)
                    _next = _nextinterpolation if _next > _nextinterpolation else _next
                    _value = round(float(tck(_next.timestamp() * 1000.0)), self._interpolation_precision)
                    _value_now = round(float(tck(entry_now)), self._interpolation_precision)
                    if caller != 'set' and _caller != "dry_run":
                        self._set(item=item, value=_value_now, caller=_caller)
                    self.logger.info("Updated: {}, linear interpolation value: {}, based on dict: {}."
                                     " Next: {}, value: {}".format(item, _value_now, self._itpl[item], _next, _value))
                except Exception as e:
                    self.logger.error("Error linear interpolation: {}".format(e))
            if cond5 and _value < 0:
                self.logger.warning("value {} for item '{}' is negative. This might be due"
                                    " to not enough values set in the UZSU.".format(_value, item))
            if _reset_interpolation is True:
                self._items[item]['interpolation']['type'] = 'none'
                self._update_item(item, 'UZSU Plugin', 'reset_interpolation')
            if _caller != "dry_run":
                self.logger.debug("will add scheduler named uzsu_{} with datetime {} and tzinfo {}"
                                  " and value {}".format(item.property.path, _next, _next.tzinfo, _value))
                self._planned.update({item: {'value': _value, 'next': _next.strftime('%Y-%m-%d %H:%M')}})
                self._webdata['items'][item.id()].update({'planned': {'value': _value, 'time': _next.strftime('%d.%m.%Y %H:%M')}})
                self._update_count['done'] = self._update_count.get('done') + 1
                self.scheduler_add('{}'.format(item.property.path), self._set,
                                   value={'item': item, 'value': _value, 'caller': 'Scheduler'}, next=_next)
                if self._update_count.get('done') == self._update_count.get('todo'):
                    self.scheduler_trigger('uzsu_sunupdate', by='UZSU Plugin')
                    self._update_count = {'done': 0, 'todo': 0}
        elif self._items[item].get('active') is True and self._items[item].get('list'):
            self.logger.warning("item '{}' is active but has no active entries.".format(item))
            self._planned.update({item: None})
            self._webdata['items'][item.id()].update({'planned': {'value': '-', 'time': '-'}})

    def _set(self, item=None, value=None, caller=None):
        """
        This function sets the specific item
        :param item:    item to be updated towards the plugin
        :param value:   value the item should be set to
        :param caller:  if given it represents the callers name
        """
        _uzsuitem, _itemvalue = self._get_dependant(item)
        _uzsuitem(value, 'UZSU Plugin', 'set')
        self._webdata['items'][item.id()].update({'depend': {'item': _uzsuitem.id(), 'value': str(_itemvalue)}})
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
                        self.logger.debug("Created rrule: '{}' for time:'{}'".format(
                            str(rrule).replace('\n', ';'), time))
                    except ValueError:
                        self.logger.debug("Could not create a rrule from rrule: '{}' and time:'{}'".format(
                            entry['rrule'], time))
                        if 'sun' in time:
                            rrule = rrulestr(entry['rrule'], dtstart=datetime.combine(
                                weekbefore, self._sun(datetime.combine(weekbefore.date(),
                                                                       datetime.min.time()).replace(tzinfo=self._timezone),
                                                      time, timescan).time()))
                            self.logger.debug("Looking for {} sun-related time. Found rrule: {}".format(
                                timescan, str(rrule).replace('\n', ';')))
                        else:
                            rrule = rrulestr(entry['rrule'], dtstart=datetime.combine(weekbefore, datetime.min.time()))
                            self.logger.debug("Looking for {} time. Found rrule: {}".format(
                                timescan, str(rrule).replace('\n', ';')))
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
                        self.logger.debug("Result parsing time (rrule) {}: {}".format(time, next))
                        if entryindex is not None and timescan == 'next':
                            self._update_suncalc(item, entry, entryindex, next.strftime("%H:%M"))
                    else:
                        next = datetime.combine(dt.date(), parser.parse(time.strip()).time()).replace(tzinfo=self._timezone)
                        self._update_suncalc(item, entry, entryindex, None)
                    if next and next.date() == dt.date():
                        self._itpl[item][next.timestamp() * 1000.0] = value
                        if next - timedelta(seconds=1) > datetime.now().replace(tzinfo=self._timezone):
                            self.logger.debug("Return from rrule {}: {}, value {}.".format(timescan, next, value))
                            return next, value
                        else:
                            self.logger.debug("Not returning {} rrule {} because it's in the past.".format(timescan, next))
            if 'sun' in time and 'series' not in time:
                next = self._sun(datetime.combine(today, datetime.min.time()).replace(
                    tzinfo=self._timezone), time, timescan)
                cond_future = next > datetime.now(self._timezone)
                if cond_future:
                    self.logger.debug("Result parsing time today (sun) {}: {}".format(time, next))
                    if entryindex is not None:
                        self._update_suncalc(item, entry, entryindex, next.strftime("%H:%M"))
                else:
                    self._itpl[item][next.timestamp() * 1000.0] = value
                    self.logger.debug("Include previous today (sun): {}, value {} for interpolation.".format(next, value))
                    if entryindex:
                        self._update_suncalc(item, entry, entryindex, next.strftime("%H:%M"))
                    next = self._sun(datetime.combine(tomorrow, datetime.min.time()).replace(
                        tzinfo=self._timezone), time, timescan)
                    self.logger.debug("Result parsing time tomorrow (sun) {}: {}".format(time, next))
            elif 'series' not in time:
                next = datetime.combine(today, parser.parse(time.strip()).time()).replace(tzinfo=self._timezone)
                cond_future = next > datetime.now(self._timezone)
                if not cond_future:
                    self._itpl[item][next.timestamp() * 1000.0] = value
                    self.logger.debug("Include {} today: {}, value {} for interpolation.".format(timescan, next, value))
                    next = datetime.combine(tomorrow, parser.parse(time.strip()).time()).replace(tzinfo=self._timezone)
            if 'series' in time:
                # Get next Time for Series
                next = self._series_get_time(entry, timescan)
                if next is None:
                    return None, None
                self._itpl[item][next.timestamp() * 1000.0] = value
                self.logger.debug("Looking for {} series-related time. Found rrule: {} with start-time . {}".format(
                    timescan, entry['rrule'].replace('\n', ';'), entry['series']['timeSeriesMin']))

            cond_today = False if next is None else next.date() == today.date()
            cond_yesterday = False if next is None else next.date() - timedelta(days=1) == yesterday.date()
            cond_tomorrow = False if next is None else next.date() == tomorrow.date()
            cond_next = False if next is None else next > datetime.now(self._timezone)
            cond_previous_today = False if next is None else next - timedelta(seconds=1) < datetime.now(self._timezone)
            cond_previous_yesterday = False if next is None else next - timedelta(days=1) < datetime.now(self._timezone)
            if next and cond_today and cond_next:
                self._itpl[item][next.timestamp() * 1000.0] = value
                self.logger.debug("Return next today: {}, value {}".format(next, value))
                return next, value
            if next and cond_tomorrow and cond_next:
                self._itpl[item][next.timestamp() * 1000.0] = value
                self.logger.debug("Return next tomorrow: {}, value {}".format(next, value))
                return next, value
            if 'series' in time and next and cond_next:
                self.logger.debug("Return next for series: {}, value {}".format(next, value))
                return next, value
            if next and cond_today and cond_previous_today:
                self._itpl[item][(next - timedelta(seconds=1)).timestamp() * 1000.0] = value
                self.logger.debug("Not returning previous today {} because it's in the past.".format(next))
            if next and cond_yesterday and cond_previous_yesterday:
                self._itpl[item][(next - timedelta(days=1)).timestamp() * 1000.0] = value
                self.logger.debug("Not returning previous yesterday {} because it's in the past.".format(next))
        except Exception as e:
            self.logger.error("Error '{}' parsing time: {}".format(time, e))
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
        self.logger.debug("Series Calculate method for item {} called by {}. Source: {}".format(item, caller, source))
        if not self._items[item].get('list'):
            issue = "No list entry in UZSU dict for item {}".format(item)
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
                        issue = "Could not calculate serie for item {}"\
                                " - because interval is None - {}".format(item, mydict)
                        self.logger.warning(issue)
                        return issue

                    if (daycount == '' or daycount is None) and seriesend is None:
                        issue = "Could not calculate series because "\
                                "timeSeriesCount is NONE and TimeSeriesMax is NONE"
                        self.logger.warning(issue)
                        return issue

                    interval = int(interval.split(":")[0]) * 60 + int(mydict['series']['timeSeriesIntervall'].split(":")[1])

                    if interval == 0:
                        issue = "Could not calculate serie because interval is ZERO - {}".format(mydict)
                        self.logger.warning(issue)
                        return issue

                    if daycount is not None and daycount != '':
                        if int(daycount) * interval >= 1440:
                            org_daycount = daycount
                            daycount = int(1439 / interval)
                            self.logger.warning("Cut your SerieCount to {} -"
                                                " because interval {} x SerieCount {}"
                                                " is more than 24h".format(daycount, interval, org_daycount))

                    if 'sun' not in mydict['series']['timeSeriesMin']:
                        starttime = datetime.strptime(mydict['series']['timeSeriesMin'], "%H:%M")
                    else:
                        mytime = self._sun(datetime.now().replace(hour=0, minute=0, second=0).astimezone(self._timezone),
                                           seriesstart, "next")
                        starttime = ("{:02d}".format(mytime.hour) + ":" + "{:02d}".format(mytime.minute))
                        starttime = datetime.strptime(starttime, "%H:%M")

                    # calculate End of Serie by Count
                    if seriesend is None:
                        endtime = starttime
                        endtime += timedelta(minutes=interval * int(daycount))

                    if seriesend is not None and 'sun' in seriesend:
                        mytime = self._sun(datetime.now().replace(hour=0, minute=0, second=0).astimezone(self._timezone),
                                           seriesend, "next")
                        endtime = ("{:02d}".format(mytime.hour) + ":" + "{:02d}".format(mytime.minute))
                        endtime = datetime.strptime(endtime, "%H:%M")
                    elif seriesend is not None and 'sun' not in seriesend:
                        endtime = datetime.strptime(seriesend, "%H:%M")

                    if seriesend is None and endtime:
                        seriesend = str(endtime.time())[:5]

                    if endtime <= starttime:
                        endtime += timedelta(days=1)

                    timediff = endtime - starttime
                    original_daycount = daycount

                    if daycount is None:
                        daycount = int(timediff.total_seconds() / 60 / interval)
                    else:
                        new_daycount = int(timediff.total_seconds() / 60 / interval)
                        if int(daycount) > new_daycount:
                            self.logger.warning("Cut your SerieCount to {} - because interval {}"
                                                " x SerieCount {} is not possible between {} and {}".format(
                                                    new_daycount, interval, daycount, starttime, endtime))
                            daycount = new_daycount

                    #####################
                    # advanced rule including all sun times, start and end times  and calculated max counts, etc.
                    rrule = rrulestr(mydict['rrule'] + ";COUNT=7",
                                     dtstart=datetime.combine(datetime.now(),
                                                              parser.parse(str(starttime.hour) + ':' +
                                                                           str(starttime.minute)).time()))
                    mynewlist = []

                    interval = int(mydict['series']['timeSeriesIntervall'].split(":")[0])*60 + \
                                int(mydict['series']['timeSeriesIntervall'].split(":")[1])
                    exceptions = 0
                    for day in list(rrule):
                        if not mydays[day.weekday()] in mydict['rrule']:
                            continue
                        myrulenext = "FREQ=MINUTELY;COUNT={};INTERVAL={}".format(daycount, interval)

                        if 'sun' not in mydict['series']['timeSeriesMin']:
                            starttime = datetime.strptime(mydict['series']['timeSeriesMin'], "%H:%M")
                        else:
                            seriesstart = mydict['series']['timeSeriesMin']
                            mytime = self._sun(day.replace(hour=0, minute=0, second=0).astimezone(self._timezone),
                                               seriesstart, "next")
                            starttime = ("{:02d}".format(mytime.hour) + ":" + "{:02d}".format(mytime.minute))
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
                                self.logger.info("Item {}: Between starttime {} and endtime {}"
                                                 " is a maximum valid interval of {:02d}:{:02d}. "
                                                 "{} is set too high for a continuous series trigger. "
                                                 "The UZSU will only be scheduled for the start time.".format(
                                                    item, datetime.strftime(starttime, "%H:%M"),
                                                    datetime.strftime(endtime, "%H:%M"),
                                                    max_interval.seconds // 3600, max_interval.seconds % 3600//60,
                                                    mydict['series']['timeSeriesIntervall']))
                            exceptions += 1
                            max_interval = int(max_interval.total_seconds() / 60)
                            myrulenext = "FREQ=MINUTELY;COUNT=1;INTERVAL={}".format(max_interval)
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
                                        mytpl['seriesMax'] = str((seriestarttime +
                                                                  timedelta(minutes=interval * count)).time())[:5]
                                    else:
                                        mytpl['seriesMax'] = "{:02d}".format(endtime.hour) + ":" + \
                                                             "{:02d}".format(endtime.minute)
                                    mytpl['seriesDay'] = actday
                                    mytpl['maxCountCalculated'] = count if exceptions == 0 else 0
                                    self.logger.debug("Mytpl: {}, count {}, "
                                                      "daycount {}, interval {}".format(mytpl, count, daycount, interval))
                                    mynewlist.append(mytpl)
                                count = 0
                                seriestarttime = None
                                actday = mydays[time.weekday()]
                            if time.time() < datetime.now().time() and time.date() <= datetime.now().date():
                                continue
                            if time >= datetime.now()+timedelta(days=7):
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
                                mytpl['seriesMax'] = "{:02d}".format(endtime.hour) + ":" + "{:02d}".format(endtime.minute)
                            mytpl['maxCountCalculated'] = count if exceptions == 0 else 0
                            mytpl['seriesDay'] = actday
                            self.logger.debug("Mytpl for last time of day: {},"
                                              " count {} daycount {},"
                                              " interval {}".format(mytpl, count, original_daycount, interval))
                            mynewlist.append(mytpl)

                    if mynewlist:
                        self._items[item]['list'][i]['seriesCalculated'] = mynewlist
                        self.logger.debug("Series for item {} calculated: {}".format(
                            item, self._items[item]['list'][i]['seriesCalculated']))
                except Exception as e:
                    self.logger.warning("Error: {}. Series entry {} for item {} could not be calculated."
                                        " Skipping series calculation".format(e, mydict, item))
                    continue
            return True

        except Exception as e:
            self.logger.warning("Series for item {} could not be calculated for list {}. Error: {}".format(
                item, self._items[item]['list'], e))

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
        self.logger.debug("Get sun4week for item {} called by {}".format(item, caller))
        mynewdict = {'sunrise': {}, 'sunset': {}}
        for day in (list(dayrule)):
            actday = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU'][day.weekday()]
            mysunrise = self._sun(day.astimezone(self._timezone), "sunrise", "next")
            mysunset = self._sun(day.astimezone(self._timezone), "sunset", "next")
            mynewdict['sunrise'][actday] = ("{:02d}".format(mysunrise.hour) + ":" + "{:02d}".format(mysunrise.minute))
            mynewdict['sunset'][actday] = ("{:02d}".format(mysunset.hour) + ":" + "{:02d}".format(mysunset.minute))
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
            interval = int(interval.split(":")[0])*60 + int(mydict['series']['timeSeriesIntervall'].split(":")[1])
        else:
            return returnvalue
        if interval == 0:
            self.logger.warning("Could not calculate serie because interval is ZERO - {}".format(mydict))
            return returnvalue

        if 'sun' not in mydict['series']['timeSeriesMin']:
            starttime = datetime.strptime(mydict['series']['timeSeriesMin'], "%H:%M")
        else:
            mytime = self._sun(datetime.now().replace(hour=0, minute=0, second=0).astimezone(self._timezone),
                               seriesstart, "next")
            starttime = ("{:02d}".format(mytime.hour) + ":" + "{:02d}".format(mytime.minute))
            starttime = datetime.strptime(starttime, "%H:%M")

        if daycount is None and seriesend is not None:
            if 'sun' in seriesend:
                mytime = self._sun(datetime.now().replace(hour=0, minute=0, second=0).astimezone(self._timezone),
                                   seriesend, "next")
                seriesend = ("{:02d}".format(mytime.hour) + ":" + "{:02d}".format(mytime.minute))
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
                self.logger.warning("Cut your SerieCount to {} - because interval {}"
                                    " x SerieCount {} is more than 24h".format(count, interval, org_count))
            else:
                new_daycount = int(timediff.total_seconds() / 60 / interval)
                if int(daycount) > new_daycount:
                    self.logger.warning("Cut your SerieCount to {} - because interval {}"
                                        " x SerieCount {} is not possible between {} and {}".format(
                                            new_daycount, interval, daycount, datetime.strftime(starttime, "%H:%M"),
                                            datetime.strftime(endtime, "%H:%M")))
                    daycount = new_daycount
        mylist = OrderedDict()
        actrrule = mydict['rrule'] + ';COUNT=9'
        rrule = rrulestr(actrrule, dtstart=datetime.combine(datetime.now()-timedelta(days=7),
                                                            parser.parse(str(starttime.hour) + ':' +
                                                                         str(starttime.minute)).time()))
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
            returnvalue = mysortedlist[myindex+1]
        else:
            returnvalue = mysortedlist[myindex-1]

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

        self.logger.debug("Given param dt={}, tz={} for {}".format(dt, dt.tzinfo, timescan))

        # now start into parsing details
        self.logger.debug('Examine param time string: {}'.format(tstr))

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
            self.logger.error('Wrong syntax: {} - wrong amount of tabs. Should be'
                              ' [H:M<](sunrise|sunset)[+|-][offset][<H:M]'.format(tstr))
            return
        # calculate the time offset
        doff = 0  # degree offset
        moff = 0  # minute offset
        tmp, op, offs = cron.rpartition('+')
        if op:
            if offs.endswith('m'):
                moff = int(offs.strip('m'))
            else:
                doff = float(offs)
        else:
            tmp, op, offs = cron.rpartition('-')
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
            self.logger.debug('{} time for sunrise: {}'.format(timescan, next_time))
            # time in next_time will be in utctime. So we need to adjust it
            if next_time.tzinfo == tzutc():
                next_time = next_time.astimezone(self._timezone)
            else:
                self.logger.warning("next_time.tzinfo was not given as utc!")
            self.logger.debug("next_time.tzinfo gives {}".format(next_time.tzinfo))
            self.logger.debug("Sunrise is included and calculated as {}".format(next_time))
        elif cron.startswith('sunset'):
            next_time = self._sh.sun.set(doff, moff, dt=dt)
            self.logger.debug('{} time for sunset: {}'.format(timescan, next_time))
            # time in next_time will be in utctime. So we need to adjust it
            if next_time.tzinfo == tzutc():
                next_time = next_time.astimezone(self._timezone)
            else:
                self.logger.warning("next_time.tzinfo was not given as utc!")
            self.logger.debug("Sunset is included and calculated as {}".format(next_time))
        else:
            self.logger.error('Wrong syntax: {} not starting with sunrise/set. Should be '
                              '[H:M<](sunrise|sunset)[+|-][offset][<H:M]'.format(tstr))
            return
        if smin is not None:
            h, sep, m = smin.partition(':')
            try:
                dmin = next_time.replace(day=dt.day, hour=int(h), minute=int(m), second=0, tzinfo=self._timezone)
            except Exception as err:
                self.logger.error('Problems assigning dmin: {}. Wrong syntax: {}. Should be '
                                  '[H:M<](sunrise|sunset)[+|-][offset][<H:M]'.format(err, tstr))
                return
        elif smax is None:
            dmin = next_time
        if smax is not None:
            h, sep, m = smax.partition(':')
            try:
                dmax = next_time.replace(day=dt.day, hour=int(h), minute=int(m), second=0, tzinfo=self._timezone)
            except Exception as err:
                self.logger.error('Problems assigning dmax: {}. Wrong syntax: {}. Should be '
                                  '[H:M<](sunrise|sunset)[+|-][offset][<H:M]'.format(err, tstr))
                return
        elif smin is None:
            dmax = next_time
        if dmin is not None and dmax is not None and dmin > dmax:
            self.logger.error("Wrong times: the earliest time should be smaller than the "
                              "latest time in {}".format(tstr))
            return
        try:
            next_time = dmin if dmin > next_time else next_time
        except Exception:
            pass
        try:
            next_time = dmax if dmax < next_time else next_time
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
            self.logger.warning("Item to be queried '{}' does not exist. Error: {}".format(
                self.get_iattr_value(item.conf, ITEM_TAG[0]), err))
            return None

        try:
            _itemvalue = _uzsuitem()
        except Exception as err:
            _itemvalue = None
            self.logger.warning("Item to be queried '{}' does not have a type attribute. Error: {}".format(
                self.get_iattr_value(item.conf, ITEM_TAG[0]), err))
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
        sortedlist = sorted([k.id() for k in self._items.keys()])
        finallist = []
        for i in sortedlist:
            finallist.append(self.itemsApi.return_item(i))
        return finallist
