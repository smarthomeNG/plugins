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
from lib.model.smartplugin import SmartPlugin
from datetime import datetime, timedelta
from dateutil.rrule import rrulestr
from dateutil import parser
from dateutil.tz import tzutc
import lib.orb

ITEM_TAG = ['uzsu_item']
class UZSU(SmartPlugin):
    """
    Main class of the UZSU Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """
    
    ALLOW_MULTIINSTANCE = False
    
    PLUGIN_VERSION = "1.3.0"


    _items = {}         # item buffer for all uzsu enabled items

    def __init__(self, smarthome, path=None, *args, **kwargs):
        """
        Initalizes the plugin. The parameters describe for this method are pulled from the entry in plugin.conf.

        :param sh:  The instance of the smarthome object, save it for later references
        """
        self.logger = logging.getLogger(__name__)
        self.logger.info('Init UZSU')
        self._sh = smarthome

    def run(self):
        """
        This is called once at the beginning after all items are already parsed from smarthome.py
        All active uzsu items are registered to the scheduler
        """
        self.logger.debug("run method called")
        self.alive = True
        # if you want to create child threads, do not make them daemon = True!
        # They will not shutdown properly. (It's a python bug)

        for item in self._items:
            if 'active' in self._items[item]:
                if self._items[item]['active']:
                    self._schedule(item)

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("stop method called")
        self.alive = False

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        The plugin can, corresponding to its attribute keywords, decide what to do with
        the item in future, like adding it to an internal array for future reference

        :param item:    The item to process.
        :return:        If the plugin needs to be informed of an items change you should return a call back function
                        like the function update_item down below. An example when this is needed is the knx plugin
                        where parse_item returns the update_item function when the attribute knx_send is found.
                        This means that when the items value is about to be updated, the call back function is called
                        with the item, caller, source and dest as arguments and in case of the knx plugin the value
                        can be sent to the knx with a knx write function within the knx plugin.
        """
        if self.has_iattr(item.conf, ITEM_TAG[0]):
            self._items[item] = item()
            return self.update_item


    def update_item(self, item, caller=None, source=None, dest=None):
        """
        This is called by smarthome engine when the item changes, e.g. by Visu or by the command line interface
        The relevant item is put into the internal item list and registered to the scheduler
        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        self._items[item] = item()
        self._schedule(item)


    def _schedule(self, item):
        """
        This function schedules an item: First the item is removed from the scheduler.
        If the item is active then the list is searched for the nearest next execution time
        """
        self._sh.scheduler.remove('uzsu_{}'.format(item))
        _next = None
        _value = None
        if 'active' in self._items[item]:
            if self._items[item]['active']:
                for entry in self._items[item]['list']:
                    next, value = self._next_time(entry)
                    if next is not None:
                        self.logger.debug("uzsu active entry for item {} with datetime {}, value {} and tzinfo {}".format(item, next, value, next.tzinfo))
                    if _next is None:
                        _next = next
                        _value = value
                    elif next and next < _next:
                        self.logger.debug("uzsu active entry for item {} using now {}, value {} and tzinfo {}".format(item, next, value, next.tzinfo))
                        _next = next
                        _value = value
                    else:
                        self.logger.debug("uzsu active entry for item {} keep {}, value {} and tzinfo {}".format(item, _next, _value, _next.tzinfo))
            else:
                self.logger.debug("uzsu item '{}' is not active".format(item))
        else:
            self.logger.debug("uzsu item '{}' does not have an 'active' attribute".format(item))
        if _next and _value is not None:
            self.logger.debug("will add scheduler named uzsu_{} with datetime {} and tzinfo {}".format(item, _next, _next.tzinfo))
            self._sh.scheduler.add('uzsu_{}'.format(item), self._set, value={'item': item, 'value': _value}, next=_next)


    def _set(self, **kwargs):
        item = kwargs['item']
        value = kwargs['value']
        self._sh.return_item(item.conf['uzsu_item'])(value, caller='UZSU')
        self._schedule(item)

    def _next_time(self, entry):
        """
        Returns the next execution time and value
        :param entry:   a dictionary that may contain the following keys:
                        value
                        active
                        date
                        rrule
                        dtstart
        """
        try:
            if not isinstance(entry, dict):
                return None, None
            if not 'value' in entry:
                return None, None
            if not 'active' in entry:
                return None, None
            if not 'time' in entry:
                return None, None
            now = datetime.now()
            value = entry['value']
            active = entry['active']
            today = datetime.today()
            yesterday = today - timedelta(days=1)
            time = entry['time']
            if not active:
                return None, None
            if 'date' in entry:
                date = entry['date']
            if 'rrule' in entry:
                if 'dtstart' in entry:
                    rrule = rrulestr(entry['rrule'], dtstart=entry['dtstart'])
                else:
                    try:
                        rrule = rrulestr(entry['rrule'], dtstart=datetime.combine(yesterday, parser.parse(time.strip()).time()))
                    except ValueError:
                        self.logger.debug("Could not create a rrule from rrule:'{}'and time:'{}'".format(entry['rrule'],time))
                        if 'sun' in time:
                            self.logger.debug("Looking for next sun-related time with rrulestr()")
                            rrule = rrulestr(entry['rrule'], dtstart=datetime.combine(yesterday, self._sun(datetime.combine(yesterday.date(), datetime.min.time()).replace(tzinfo=self._sh.tzinfo()), time).time()))
                        else:
                            self.logger.debug("Looking for next time with rrulestr()")
                            rrule = rrulestr(entry['rrule'], dtstart=datetime.combine(yesterday, datetime.min.time()))
                dt = now
                while self.alive:
                    dt = rrule.after(dt)
                    if dt is None:
                        return None, None
                    if 'sun' in time:
                        next = self._sun(datetime.combine(dt.date(), datetime.min.time()).replace(tzinfo=self._sh.tzinfo()), time)
                        self.logger.debug("Result parsing time (rrule){}: {}".format(time, next))
                    else:
                        next = datetime.combine(dt.date(), parser.parse(time.strip()).time()).replace(tzinfo=self._sh.tzinfo())
                    if next and next.date() == dt.date() and next > datetime.now(self._sh.tzinfo()):
                        return next, value
            if 'sun' in time:
                next = self._sun(datetime.combine(today, datetime.min.time()).replace(tzinfo=self._sh.tzinfo()), time)
                self.logger.debug("Result parsing time (sun) {}: {}".format(time, next))
            else:
                next = datetime.combine(today, parser.parse(time.strip()).time()).replace(tzinfo=self._sh.tzinfo())
            if next and next.date() == today and next > datetime.now(self._sh.tzinfo()):
                return next, value
        except Exception as e:
            self.logger.error("Error '{}' parsing time: {}".format(time, e))
        return None, None

    def _sun(self, dt, tstr):
        """
        parses a given string with a time range to determine it's timely boundaries and 
        returns a time 
        
        :param: dt contains a datetime object, 
        :param: tstr contains a string with '[H:M<](sunrise|sunset)[+|-][offset][<H:M]' like e.g. '6:00<sunrise<8:00'
        :return: the calculated date and time in timezone aware format
        """
        # checking preconditions from configuration:
        if not self._sh.sun:  # no sun object created
            self.logger.error('No latitude/longitude specified. You could not use sunrise/sunset as UZSU entry.')
            return

        # create an own sun object:
        try:
            longitude = self._sh.sun._obs.long
            latitude = self._sh.sun._obs.lat
            elevation = self._sh.sun._obs.elev
            uzsu_sun = lib.orb.Orb('sun', longitude, latitude, elevation)
            self.logger.debug("Created a new sun object with latitude={}, longitude={}, elevation={}".format(latitude, longitude, elevation)) 
        except Exception as e:
            self.logger.error("Error '{}' creating a new sun object. You could not use sunrise/sunset as UZSU entry.".format(e))
            return

        self.logger.debug("Given param dt={}, tz=".format(dt, dt.tzinfo)) 

        # now start into parsing details
        self.logger.debug('Examine param time string: {0}'.format(tstr))
            
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
            self.logger.error('Wrong syntax: {0}. Should be [H:M<](sunrise|sunset)[+|-][offset][<H:M]'.format(tstr))
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
            # time in next_time will be in utctime. So we need to adjust it
            if next_time.tzinfo == tzutc():
                next_time = next_time.astimezone(self._sh.tzinfo())
            else:
                self.logger.warning("next_time.tzinfo was not given as utc!") 
            self.logger.debug("next_time.tzinfo gives {}".format(next_time.tzinfo)) 
            self.logger.debug("Sunrise is included and calculated as {}".format(next_time)) 
        elif cron.startswith('sunset'):
            next_time = uzsu_sun.set(doff, moff, dt=dt)
            # time in next_time will be in utctime. So we need to adjust it
            if next_time.tzinfo == tzutc():
                next_time = next_time.astimezone(self._sh.tzinfo())
            else:
                self.logger.warning("next_time.tzinfo was not given as utc!") 
            self.logger.debug("Sunset is included and calculated as {}".format(next_time)) 
        else:
            self.logger.error('Wrong syntax: {0}. Should be [H:M<](sunrise|sunset)[+|-][offset][<H:M]'.format(tstr))
            return

        
        if smin is not None:
            h, sep, m = smin.partition(':')
            try:
                dmin = next_time.replace(hour=int(h), minute=int(m), second=0, tzinfo=self._sh.tzinfo())
            except Exception:
                self.logger.error('Wrong syntax: {0}. Should be [H:M<](sunrise|sunset)[+|-][offset][<H:M]'.format(tstr))
                return
            if dmin > next_time:
                next_time = dmin
        if smax is not None:
            h, sep, m = smax.partition(':')
            try:
                dmax = next_time.replace(hour=int(h), minute=int(m), second=0, tzinfo=self._sh.tzinfo())
            except Exception:
                self.logger.error('Wrong syntax: {0}. Should be [H:M<](sunrise|sunset)[+|-][offset][<H:M]'.format(tstr))
                return
            if dmax < next_time:
                next_time = dmax
        
        if dmin is not None and dmax is not None:
            if dmin > dmax:
                self.logger.error('Wrong times: the earliest time should be smaller than the latest time in {}'.format(tstr))
                return
            
        return next_time
