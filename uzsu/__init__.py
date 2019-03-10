#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2011-2013 Niko Will
# Copyright 2017 Bernd Meiners                      Bernd.Meiners@mail.de
#########################################################################
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
#     dtstart:  a datetime object. Exact datetime as start value for the rrule algorithm. Important e.g. for FREQ=MINUTELY rrules (optional).
#
#     value:    the value which will be set to the item.
#
#     active:   True if the entry is activated, False if not.
#               A deactivated entry is stored to the database but doesn't trigger the setting of the value.
#               It can be enabled later with the update method.
#
#     time:     time as string to use sunrise/sunset arithmetics like in the crontab
#               examples:
#               17:00<sunset
#               sunrise>8:00
#               17:00<sunset.
#               You also can set the time with 17:00
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
import lib.orb
from unittest import mock
from collections import OrderedDict
from bin.smarthome import VERSION
import copy

try:
    from scipy import interpolate
    REQUIRED_PACKAGE_IMPORTED = True
except Exception:
    REQUIRED_PACKAGE_IMPORTED = False

ITEM_TAG = ['uzsu_item']


class UZSU(SmartPlugin):
    """
    Main class of the UZSU Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    ALLOW_MULTIINSTANCE = False

    PLUGIN_VERSION = "1.5.3"

    _items = {}         # item buffer for all uzsu enabled items

    def __init__(self, smarthome):
        """
        Initalizes the plugin. The parameters describe for this method are pulled from the entry in plugin.conf.

        :param sh:  The instance of the smarthome object, save it for later references
        """

        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)
        self.itemsApi = Items.get_instance()
        self._timezone = Shtime.get_instance().tzinfo()
        self._remove_duplicates = self.get_parameter_value('remove_duplicates')
        self._sh = smarthome
        self._uzsu_sun = None
        self._items = {}
        self._planned = {}
        self._update_count = {'todo': 0, 'done': 0}
        self._itpl = {}
        self.init_webinterface()
        self.logger.info("Init with timezone {}".format(self._timezone))
        if not REQUIRED_PACKAGE_IMPORTED:
            self.logger.warning("Unable to import Python package 'scipy' which is necessary for interpolation.")
            self._init_complete = False

    def run(self):
        """
        This is called once at the beginning after all items are already parsed from smarthome.py
        All active uzsu items are registered to the scheduler
        """
        self.logger.debug("run method called")
        self.alive = True
        self.scheduler_add('uzsu_sunupdate', self._update_all_suns, value={'caller': 'scheduler'}, cron='0 0 * *')
        self.logger.info("Adding sun update schedule for midnight")

        for item in self._items:
            self._items[item]['interpolation']['itemtype'] = self._add_type(item)
            item(self._items[item], 'UZSU Plugin', 'itemtype')
            cond1 = self._items[item].get('active') and self._items[item]['active'] is True
            cond2 = self._items[item].get('list')
            if cond1 and cond2:
                self._update_count['todo'] = self._update_count.get('todo') + 1
        self.logger.debug("Going to update {} items: {}".format(self._update_count['todo'], list(self._items.keys())))

        for item in self._items:
            cond1 = self._items[item].get('active') is True
            cond2 = self._items[item].get('list')
            self._check_rruleandplanned(item)
            if cond1 and cond2:
                self._schedule(item, caller='run')
            elif cond1 and not cond2:
                self.logger.warning("Item '{}' is active but has no entries.".format(item))
                self._planned.update({item: None})
            else:
                self.logger.debug("Not scheduling item {}, cond1 {}, cond2 {}".format(item, cond1, cond2))

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("stop method called")
        for item in self._items:
            try:
                self.scheduler_remove('uzsu_{}'.format(item))
                self.logger.debug('Removing scheduler for item {}'.format(item))
            except Exception as err:
                self.logger.debug('Scheduler for item {} not removed. Problem: {}'.format(item, err))
        self.alive = False

    def _update_all_suns(self, caller=None):
        """
        Update sun information for all uzsu items

        :param caller:  if given it represents the callers name
        :type caller:   str
        """
        for item in self._items:
            success = self._update_sun(item)
            if success:
                self.logger.debug('Updating sun info for item {}'.format(item))
                item(self._items[item], 'UZSU Plugin', 'update_all_suns')

    def _update_sun(self, item, caller=None):
        """
        Update general sunrise and sunset information for visu

        :param caller:  if given it represents the callers name
        :param item:    uzsu item
        :type caller:   str
        :type item:     item
        """
        try:
            self._uzsu_sun = self._create_sun()
            if '.'.join(VERSION.split('.', 3)[:3]) > '1.5.1':
                self._items[item] = item()
            else:
                self._items[item] = copy.deepcopy(item())
            _sunrise = self._uzsu_sun.rise()
            _sunset = self._uzsu_sun.set()
            if _sunrise.tzinfo == tzutc():
                _sunrise = _sunrise.astimezone(self._timezone)
            if _sunset.tzinfo == tzutc():
                _sunset = _sunset.astimezone(self._timezone)
            self._items[item]['sunrise'] = '{:02}:{:02}'.format(_sunrise.hour, _sunrise.minute)
            self._items[item]['sunset'] = '{:02}:{:02}'.format(_sunset.hour, _sunset.minute)
            self.logger.debug('Updated sun entries for item {}, triggered by {}. sunrise: {}, sunset: {}'.format(
                item, caller, self._items[item]['sunrise'], self._items[item]['sunset']))
            success = True
        except Exception:
            success = False
        return success

    def _update_suncalc(self, item, entry, entryindex, entryvalue):
        update = False
        if entry.get('calculated'):
            update = True if entry == self._items[item]['list'][entryindex] else update
            with mock.patch.dict(entry, calculated=entryvalue):
                update = True if entry == self._items[item]['list'][entryindex] else update
        else:
            update = True
        if update is True and not entry.get('calculated') == entryvalue:
            self.logger.debug("Updated calculated time for item {} entry {} with value {}.".format(
                item, self._items[item]['list'][entryindex], entryvalue))
            self._items[item]['list'][entryindex]['calculated'] = entryvalue
            item(self._items[item], 'UZSU Plugin', 'update_sun')
        else:
            self.logger.debug("Sun calculation {} entry not updated for item {} with value {}".format(
                entryvalue, item, entry.get('calculated')))

    def _add_type(self, item):
        """
        Adding the type of the item that is changed by the uzsu to the item dict

        :param item:    uzsu item
        :type item:     item
        :return:        The item type of the item that is changed
        """
        try:
            _uzsuitem = self.itemsApi.return_item(self.get_iattr_value(item.conf, ITEM_TAG[0]))
        except Exception as err:
            _uzsuitem = None
            self.logger.warning("Item to be set by uzsu '{}' does not exist. Error: {}".format(
                self.get_iattr_value(item.conf, ITEM_TAG[0]), err))
        try:
            _itemtype = _uzsuitem.type()
        except Exception as err:
            _itemtype = 'foo' if _uzsuitem else None
            self.logger.warning("Item to be set by uzsu '{}' does not have a type attribute. Error: {}".format(
                self.get_iattr_value(item.conf, ITEM_TAG[0]), err))
        return _itemtype

    def _logics_activate(self, activevalue=None, item=None):
        if isinstance(activevalue, str):
            if activevalue.lower() in ['1', 'yes', 'true', 'on']:
                activevalue = True
            elif activevalue.lower() in ['0', 'no', 'false', 'off']:
                activevalue = False
            else:
                self.logger.warning("Value to activate item '{}' has to be True or False".format(item))
        if isinstance(activevalue, bool):
            if '.'.join(VERSION.split('.', 3)[:3]) > '1.5.1':
                self._items[item] = item()
            else:
                self._items[item] = copy.deepcopy(item())
            self._items[item]['active'] = activevalue
            self.logger.info("Item {} is set via logic to: {}".format(item, activevalue))
            item(self._items[item], 'UZSU Plugin', 'logic')
            return activevalue
        if activevalue is None:
            return self._items[item].get('active')

    def _logics_interpolation(self, type=None, interval=5, backintime=0, item=None):
        if type is None:
            return self._items[item].get('interpolation')
        else:
            if '.'.join(VERSION.split('.', 3)[:3]) > '1.5.1':
                self._items[item] = item()
            else:
                self._items[item] = copy.deepcopy(item())
            self._items[item]['interpolation']['type'] = str(type).lower()
            self._items[item]['interpolation']['interval'] = abs(int(interval))
            self._items[item]['interpolation']['initage'] = int(backintime)
            self.logger.info("Item {} interpolation is set via logic to: type={}, interval={}, backintime={}".format(
                item, type, abs(interval), backintime))
            item(self._items[item], 'UZSU Plugin', 'logic')
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
            item(self._items[item], 'UZSU Plugin', 'clear')
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
            return self._planned[item]
        elif self._planned.get(item) == 'notinit' and self._items[item].get('active') is True:
            self.logger.info("Item '{}' is active but not fully initialized yet.".format(item))
            return None
        elif not self._planned.get(item) and self._items[item].get('active') is True:
            self.logger.warning("Item '{}' is active but has no (active) entries.".format(item))
            self._planned.update({item: None})
            return None
        else:
            self.logger.info("Nothing planned for item '{}'.".format(item))
            return None

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        The plugin can, corresponding to its attribute keywords, decide what to do with
        the item in future, like adding it to an internal array for future reference

        :param item:    The item to process.
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
            item.interpolation = functools.partial(self._logics_interpolation, item=item)
            item.clear = functools.partial(self._logics_clear, item=item)
            item.planned = functools.partial(self._logics_planned, item=item)
            item.itpl = functools.partial(self._logics_itpl, item=item)

            if '.'.join(VERSION.split('.', 3)[:3]) > '1.5.1':
                self._items[item] = item()
            else:
                self._items[item] = copy.deepcopy(item())
            try:
                self._items[item]['interpolation']['initialized'] = False
            except Exception:
                self._items[item]['interpolation'] = {}
                self._items[item]['interpolation']['type'] = 'none'
                self._items[item]['interpolation']['initialized'] = False
            if self._items[item].get('list'):
                for entry, _ in enumerate(self._items[item]['list']):
                    self._items[item]['list'][entry].pop('condition', None)
                    self._items[item]['list'][entry].pop('holiday', None)
                    self._items[item]['list'][entry].pop('delayedExec', None)
            else:
                self._items[item]['list'] = []
            if not self._items[item].get('active'):
                self._items[item]['active'] = False
            item(self._items[item], 'UZSU Plugin', 'init')
            self._planned.update({item: 'notinit'})
            self.logger.debug('Dict for item {} is: {}'.format(item, self._items[item]))
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
        item(self._items[item], 'UZSU Plugin', 'update')

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
                item(self._items[item], 'UZSU Plugin', 'create_rrule')
            if _inactive >= len(self._items[item]['list']):
                self._planned.update({item: None})

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        This is called by smarthome engine when the item changes, e.g. by Visu or by the command line interface
        The relevant item is put into the internal item list and registered to the scheduler

        :param item:    item to be updated towards the plugin
        :param caller:  if given it represents the callers name
        :param source:  if given it represents the source
        :param dest:    if given it represents the dest
        """
        if '.'.join(VERSION.split('.', 3)[:3]) > '1.5.1':
            self._items[item] = item()
        else:
            self._items[item] = copy.deepcopy(item())
        cond = (not caller == 'UZSU Plugin') or source == 'logic'
        self.logger.debug('Update Item {}, Caller {}, Source {}, Dest {}. Will update: {}'.format(
            item, caller, source, dest, cond))
        if not source == 'create_rrule':
            self._check_rruleandplanned(item)
        # Removing Duplicates
        if self._remove_duplicates is True and self._items[item].get('list') and cond:
            self._remove_dupes(item)
        if cond:
            self._schedule(item, caller='update')

    def _schedule(self, item, caller=None):
        """
        This function schedules an item: First the item is removed from the scheduler.
        If the item is active then the list is searched for the nearest next execution time.
        No matter it active or not the calculation for the execution time is triggered.

        :param item:    item to be updated towards the plugin
        :param caller:  if given it represents the callers name
        """
        self.scheduler_remove('uzsu_{}'.format(item))
        self.logger.debug('Schedule Item {}, Trigger: {}, Changed by: {}'.format(
            item, caller, item.changed_by()))
        _next = None
        _value = None
        self._update_sun(item, caller='schedule')

        if not self._items[item]['interpolation'].get('itemtype'):
            self.logger.error("item '{}' to be set by uzsu does not exist.".format(
                self.get_iattr_value(item.conf, ITEM_TAG[0])))
        elif not self._items[item].get('list') and self._items[item].get('active') is True:
            self.logger.warning("item '{}' is active but has no entries.".format(item))
            self._planned.update({item: None})
        elif self._items[item].get('active') is True:
            self._itpl[item] = OrderedDict()
            for i, entry in enumerate(self._items[item]['list']):
                next, value = self._get_time(entry, 'next', item, i)
                previous, previousvalue = self._get_time(entry, 'previous', item, i)
                item(self._items[item], 'UZSU Plugin', 'schedule')
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
        if _next and _value is not None and self._items[item].get('active') is True:
            _reset_interpolation = False
            _interval = self._items[item]['interpolation'].get('interval')
            _interval = 5 if not _interval else int(_interval)
            if _interval < 0:
                _interval = abs(int(_interval))
                self._items[item]['interpolation']['interval'] = _interval
                item(self._items[item], 'UZSU Plugin', 'intervalchange')
            _interpolation = self._items[item]['interpolation'].get('type')
            _interpolation = 'none' if not _interpolation else _interpolation
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
            _timediff = datetime.now(self._timezone) - timedelta(minutes=_initage)
            try:
                _value = float(_value)
            except ValueError:
                pass
            cond1 = _inittime - _timediff.timestamp() * 1000.0 >= 0
            cond2 = _interpolation.lower() in ['cubic', 'linear']
            cond3 = _initialized is False
            cond4 = _initage > 0
            cond5 = isinstance(_value, float)
            self._itpl[item] = OrderedDict(itpl_list)
            if not cond2 and cond3 and cond4:
                self.logger.info("Looking if there was a value set after {} for item {}".format(
                    _timediff, item))
                self._items[item]['interpolation']['initialized'] = True
                item(self._items[item], 'UZSU Plugin', 'init')
            if cond1 and not cond2 and cond3:
                self._set(item=item, value=_initvalue, caller='scheduler')
                self.logger.info("Updated item {} on startup with value {} from time {}".format(
                    item, _initvalue, datetime.fromtimestamp(_inittime/1000.0)))
            _itemtype = self._items[item]['interpolation'].get('itemtype')
            if cond2 and not REQUIRED_PACKAGE_IMPORTED:
                self.logger.warning("Interpolation is set to {} but scipy not installed. Ignoring interpolation".format(
                    _interpolation))
            elif cond2 and _interval < 1:
                self.logger.warning("Interpolation is set to {} but interval is {}. Ignoring interpolation".format(
                    _interpolation, _interval))
            elif cond2 and _itemtype not in ['num']:
                self.logger.warning("Interpolation is set to {} but type of item is {}."
                                    " Ignoring interpolation and setting UZSU interpolation to none.".format(
                                        _interpolation, _itemtype))
                _reset_interpolation = True
            elif _interpolation.lower() == 'cubic' and _interval > 0:
                try:
                    tck = interpolate.PchipInterpolator(list(self._itpl[item].keys()), list(self._itpl[item].values()))
                    _nextinterpolation = datetime.now(self._timezone) + timedelta(minutes=_interval)
                    _next = _nextinterpolation if _next > _nextinterpolation else _next
                    _value = round(float(tck(_next.timestamp() * 1000.0)), 2)
                    _value_now = round(float(tck(entry_now)), 2)
                    self._set(item=item, value=_value_now, caller='scheduler')
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
                    _value = round(float(tck(_next.timestamp() * 1000.0)), 2)
                    _value_now = round(float(tck(entry_now)), 2)
                    self._set(item=item, value=_value_now, caller='scheduler')
                    self.logger.info("Updated: {}, linear interpolation value: {}, based on dict: {}."
                                     " Next: {}, value: {}".format(item, _value_now, self._itpl[item], _next, _value))
                except Exception as e:
                    self.logger.error("Error linear interpolation: {}".format(e))
            if cond5 and _value < 0:
                self.logger.warning("value {} for item '{}' is negative. This might be due"
                                    " to not enough values set in the UZSU.".format(_value, item))
            if _reset_interpolation is True:
                self._items[item]['interpolation']['type'] = 'none'
                item(self._items[item], 'UZSU Plugin', 'reset_interpolation')

            self.logger.debug("will add scheduler named uzsu_{} with datetime {} and tzinfo {}"
                              " and value {}".format(item, _next, _next.tzinfo, _value))
            self._planned.update({item: {'value': _value, 'next': _next.strftime('%Y-%m-%d %H:%M')}})
            self._update_count['done'] = self._update_count.get('done') + 1
            self.scheduler_add('uzsu_{}'.format(item), self._set, value={'item': item, 'value': _value}, next=_next)
            if self._update_count.get('done') == self._update_count.get('todo'):
                self.scheduler_trigger('uzsu_sunupdate', by='UZSU Plugin')
                self._update_count = {'done': 0, 'todo': 0}
        elif self._items[item].get('active') is True and self._items[item].get('list'):
            self.logger.warning("item '{}' is active but has no active entries.".format(item))
            self._planned.update({item: None})

    def _set(self, item=None, value=None, caller=None):
        """
        This function sets the specific item

        :param item:    item to be updated towards the plugin
        :param value:   value the item should be set to
        :param caller:  if given it represents the callers name
        """
        _uzsuitem = self.itemsApi.return_item(self.get_iattr_value(item.conf, ITEM_TAG[0]))
        _uzsuitem(value, 'UZSU Plugin', 'set')
        if not caller:
            self._schedule(item, caller='set')

    def _get_time(self, entry, timescan, item=None, entryindex=None):
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
        """
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
            active = entry['active']
            today = datetime.today()
            tomorrow = today + timedelta(days=1)
            yesterday = today - timedelta(days=1)
            weekbefore = today - timedelta(days=7)
            time = entry['time']
            if not active:
                return None, None
            if 'rrule' in entry:
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
                                                                       datetime.min.time()).replace(tzinfo=self._timezone), time, timescan).time()))
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
                        next = self._sun(datetime.combine(dt.date(), datetime.min.time()).replace(tzinfo=self._timezone), time, timescan)
                        self.logger.debug("Result parsing time (rrule) {}: {}".format(time, next))
                        if entryindex is not None:
                            self._update_suncalc(item, entry, entryindex, next.strftime("%H:%M"))
                    else:
                        next = datetime.combine(dt.date(), parser.parse(time.strip()).time()).replace(tzinfo=self._timezone)
                    if next and next.date() == dt.date():
                        self._itpl[item][next.timestamp() * 1000.0] = value
                        if next - timedelta(seconds=1) > datetime.now().replace(tzinfo=self._timezone):
                            self.logger.debug("Return from rrule {}: {}, value {}.".format(timescan, next, value))
                            return next, value
                        else:
                            self.logger.debug("Not returning {} rrule {} because it's in the past.".format(timescan, next))
            if 'sun' in time:
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
            else:
                next = datetime.combine(today, parser.parse(time.strip()).time()).replace(tzinfo=self._timezone)
                cond_future = next > datetime.now(self._timezone)
                if not cond_future:
                    self._itpl[item][next.timestamp() * 1000.0] = value
                    self.logger.debug("Include {} today: {}, value {} for interpolation.".format(timescan, next, value))
                    next = datetime.combine(tomorrow, parser.parse(time.strip()).time()).replace(tzinfo=self._timezone)
            cond_today = next.date() == today.date()
            cond_yesterday = next.date() - timedelta(days=1) == yesterday.date()
            cond_tomorrow = next.date() == tomorrow.date()
            cond_next = next > datetime.now(self._timezone)
            cond_previous_today = next - timedelta(seconds=1) < datetime.now(self._timezone)
            cond_previous_yesterday = next - timedelta(days=1) < datetime.now(self._timezone)
            if next and cond_today and cond_next:
                self._itpl[item][next.timestamp() * 1000.0] = value
                self.logger.debug("Return next today: {}, value {}".format(next, value))
                return next, value
            if next and cond_tomorrow and cond_next:
                self._itpl[item][next.timestamp() * 1000.0] = value
                self.logger.debug("Return next tomorrow: {}, value {}".format(next, value))
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

    def _create_sun(self):
        """
        Creates a sun object for sun calculations
        """
        # checking preconditions from configuration:
        uzsu_sun = None
        if not self._sh.sun:  # no sun object created
            self.logger.error("No latitude/longitude specified. Not possible to create sun object.")

        # create an own sun object:
        if not self._uzsu_sun:
            try:
                longitude = self._sh.sun._obs.long
                latitude = self._sh.sun._obs.lat
                elevation = self._sh.sun._obs.elev
                uzsu_sun = lib.orb.Orb('sun', longitude, latitude, elevation)
                self.logger.debug("Created a new sun object with latitude={}, longitude={}, elevation={}".format(
                    latitude, longitude, elevation))
            except Exception as e:
                self.logger.error("Error '{}' creating a new sun object. You could not "
                                  "use sunrise/sunset as UZSU entry.".format(e))
        else:
            uzsu_sun = self._uzsu_sun
        return uzsu_sun

    def _sun(self, dt, tstr, timescan):
        """
        parses a given string with a time range to determine it's timely boundaries and
        returns a time

        :param dt:          contains a datetime object,
        :param tstr:        contains a string with '[H:M<](sunrise|sunset)[+|-][offset][<H:M]' like e.g. '6:00<sunrise<8:00'
        :param timescan:    defines whether to find values in the future or past, for logging purposes
        :return:            the calculated date and time in timezone aware format
        """
        uzsu_sun = self._create_sun()
        if not uzsu_sun:
            return

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
            self.logger.error('Wrong syntax: {}. Should be [H:M<](sunrise|sunset)[+|-][offset][<H:M]'.format(
                tstr))
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
            next_time = uzsu_sun.rise(doff, moff, dt=dt)
            self.logger.debug('{} time for sunrise: {}'.format(timescan, next_time))
            # time in next_time will be in utctime. So we need to adjust it
            if next_time.tzinfo == tzutc():
                next_time = next_time.astimezone(self._timezone)
            else:
                self.logger.warning("next_time.tzinfo was not given as utc!")
            self.logger.debug("next_time.tzinfo gives {}".format(next_time.tzinfo))
            self.logger.debug("Sunrise is included and calculated as {}".format(next_time))
        elif cron.startswith('sunset'):
            next_time = uzsu_sun.set(doff, moff, dt=dt)
            self.logger.debug('{} time for sunset: {}'.format(timescan, next_time))
            # time in next_time will be in utctime. So we need to adjust it
            if next_time.tzinfo == tzutc():
                next_time = next_time.astimezone(self._timezone)
            else:
                self.logger.warning("next_time.tzinfo was not given as utc!")
            self.logger.debug("Sunset is included and calculated as {}".format(next_time))
        else:
            self.logger.error('Wrong syntax: {}. Should be [H:M<](sunrise|sunset)[+|-][offset][<H:M]'.format(
                tstr))
            return
        if smin is not None:
            h, sep, m = smin.partition(':')
            try:
                dmin = next_time.replace(day=dt.day, hour=int(h), minute=int(m), second=0, tzinfo=self._timezone)
            except Exception:
                self.logger.error('Wrong syntax: {}. Should be [H:M<](sunrise|sunset)[+|-][offset][<H:M]'.format(
                    tstr))
                return
        elif smax is None:
            dmin = next_time
        if smax is not None:
            h, sep, m = smax.partition(':')
            try:
                dmax = next_time.replace(day=dt.day, hour=int(h), minute=int(m), second=0, tzinfo=self._timezone)
            except Exception:
                self.logger.error('Wrong syntax: {}. Should be [H:M<](sunrise|sunset)[+|-][offset][<H:M]'.format(
                    tstr))
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
            _uzsuitem = None
            self.logger.warning("Item to be queried '{}' does not exist. Error: {}".format(
                self.get_iattr_value(item.conf, ITEM_TAG[0]), err))
        try:
            _itemvalue = _uzsuitem()
        except Exception as err:
            _itemvalue = None
            self.logger.warning("Item to be queried '{}' does not have a type attribute. Error: {}".format(
                self.get_iattr_value(item.conf, ITEM_TAG[0]), err))
        return _itemvalue

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

    def init_webinterface(self):
        """"
        Initialize the web interface for this plugin

        This method is only needed if the plugin is implementing a web interface
        """
        try:
            self.mod_http = Modules.get_instance().get_module('http')
        except Exception:
            self.mod_http = None
        if self.mod_http is None:
            self.logger.error("Plugin '{}': Not initializing the web interface".format(self.get_shortname()))
            return False

        import sys
        if "SmartPluginWebIf" not in list(sys.modules['lib.model.smartplugin'].__dict__):
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
    def index(self, action=None, item_id=None, item_path=None, reload=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        item = self.plugin.get_sh().return_item(item_path)
        tmpl = self.tplenv.get_template('index.html')
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        return tmpl.render(p=self.plugin,
                           language=self.plugin._sh.get_defaultlanguage(), now=self.plugin.shtime.now())
