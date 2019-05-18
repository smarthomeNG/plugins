#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2013 Marcus Popp                              marcus@popp.mx
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
#  along with SmartHomeNG. If not, see <http://www.gnu.org/licenses/>.
#########################################################################

import logging
import datetime
import os
import errno

import dateutil.tz
import dateutil.rrule
import dateutil.relativedelta
from lib.model.smartplugin import SmartPlugin
from lib.shtime import Shtime
from lib.network import Http
from bin.smarthome import VERSION


class iCal(SmartPlugin):
    PLUGIN_VERSION = "1.5.2"
    ALLOW_MULTIINSTANCE = False
    DAYS = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")
    FREQ = ("YEARLY", "MONTHLY", "WEEKLY", "DAILY", "HOURLY", "MINUTELY", "SECONDLY")
    PROPERTIES = ("SUMMARY", "DESCRIPTION", "LOCATION", "CATEGORIES", "CLASS")

    def __init__(self, smarthome):
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)
        try:
            self.shtime = Shtime.get_instance()
            try:
                self.dl = Http(timeout=self.get_parameter_value('timeout'))
            except:
                self.dl = Http('')
            self._items = []
            self._icals = {}
            self._ical_aliases = {}
            self.sh = smarthome
            cycle = self.get_parameter_value('cycle')
            calendars = self.get_parameter_value('calendars')
            config_dir = self.get_parameter_value('directory')
        except Exception as err:
            self.logger.error('Problems initializing: {}'.format(err))
            self._init_complete = False
            return
        try:
            self._directory = '{}/{}'.format(self.get_vardir(), config_dir)
        except Exception:
            self._directory = '{}/var/{}'.format(self.sh.get_basedir(), config_dir)
        try:
            os.makedirs(self._directory)
            self.logger.debug('Created {} subfolder in var'.format(config_dir))
        except OSError as e:
            if e.errno != errno.EEXIST:
                self.logger.error('Problem creating {} folder in {}/var'.format(config_dir, self.sh.get_basedir()))
                self._init_complete = False
                return

        for calendar in calendars:
            if isinstance(calendar, dict):
                calendar=list("{!s}:{!s}".format(k,v) for (k,v) in calendar.items())[0]
            if ':' in calendar and 'http' != calendar[:4]:
                name, _, cal = calendar.partition(':')
                calendar = cal.strip()
                self.logger.info('Registering calendar {} with alias {}.'.format(calendar, name))
                self._ical_aliases[name.strip()] = calendar
            else:
                self.logger.info('Registering calendar {} without alias.'.format(calendar))
            calendar = calendar.strip()
            self._icals[calendar] = self._read_events(calendar)

        smarthome.scheduler.add('iCalUpdate', self._update_items, cron='* * * *', prio=5)
        smarthome.scheduler.add('iCalRefresh', self._update_calendars, cycle=int(cycle), prio=5)

    def run(self):
        self.alive = True

    def stop(self):
        self.alive = False

    def parse_item(self, item):
        if self.has_iattr(item.conf, 'ical_calendar'):
            uri = self.get_iattr_value(item.conf, 'ical_calendar').strip()

            if uri in self._ical_aliases:
                uri = self._ical_aliases[uri]

            if uri not in self._icals:
                self._icals[uri] = self._read_events(uri)

            self._items.append(item)

    def parse_logic(self, logic):
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        pass

    def __call__(self, ics='', delta=1, offset=0, username=None, password=None, prio=1, verify=True):
        if ics in self._ical_aliases:
            self.logger.debug('iCal retrieve events by alias {0} -> {1}'.format(ics, self._ical_aliases[ics]))
            return self._filter_events(self._icals[self._ical_aliases[ics]], delta, offset)

        if ics in self._icals:
            self.logger.debug('iCal retrieve cached events {0}'.format(ics))
            return self._filter_events(self._icals[ics], delta, offset)

        self.logger.debug('iCal retrieve events {0}'.format(ics))
        return self._filter_events(self._read_events(ics, username=username, password=password, prio=prio, verify=verify), delta, offset)

    def _update_items(self):
        if len(self._items):
            now = self.shtime.now()

            events = {}
            for calendar in self._icals:
                events[calendar] = self._filter_events(self._icals[calendar], 0, 0)

            for item in self._items:
                calendar = item.conf['ical_calendar']

                if calendar in self._ical_aliases:
                    calendar = self._ical_aliases[calendar]

                val = False
                for date in events[calendar]:
                    for event in events[calendar][date]:
                        if event['Start'] <= now <= event['End'] or (event['Start'] == event['End'] and event['Start'] <= now <= event['End'].replace(second=59, microsecond=999)):
                            val = True
                            break

                item(val)

    def _update_calendars(self):
        for uri in self._icals:
            self._icals[uri] = self._read_events(uri)
            self.logger.debug('Updated calendar {0}'.format(uri))

        if len(self._icals):
            self._update_items()

    def _filter_events(self, events, delta=1, offset=0, prio=1):
        now = self.shtime.now()
        offset = offset - 1  # start at 23:59:59 the day before
        delta += 1  # extend delta for negative offset
        start = now.replace(hour=23, minute=59, second=59, microsecond=0) + datetime.timedelta(days=offset)
        end = start + datetime.timedelta(days=delta)
        revents = {}
        for event in events:
            event = events[event]
            e_start = event['DTSTART']
            e_end = event['DTEND']
            if 'RRULE' in event and (event['RRULE'] is not None):
                e_duration = e_end - e_start
                for e_rstart in event['RRULE'].between(start, end, inc=True):
                    if e_rstart not in event['EXDATES']:
                        date = e_rstart.date()
                        revent = {'Start': e_rstart, 'End': e_rstart + e_duration}
                        for prop in self.PROPERTIES:
                            if prop in event:
                                revent[prop.capitalize()] = event[prop]
                        if date not in revents:
                            revents[date] = [revent]
                        else:
                            revents[date].append(revent)
            else:
                if (e_start > start and e_start < end) or (e_start < start and e_end > start):
                    date = e_start.date()
                    revent = {'Start': e_start, 'End': e_end}
                    for prop in self.PROPERTIES:
                        if prop in event:
                            revent[prop.capitalize()] = event[prop]
                    if date not in revents:
                        revents[date] = [revent]
                    else:
                        revents[date].append(revent)
        return revents

    def _read_events(self, ics, username=None, password=None, prio=1, verify=True):
        if ics.startswith('http'):
            _, _, cal = ics.partition('//')
            name = '{}.ics'.format(cal.split('/')[0].replace('.', '_'))
            for entry in self._ical_aliases:
                name = '{}.ics'.format(entry) if ics == self._ical_aliases[entry] else name
            filename = '{}/{}'.format(self._directory, name)
            auth = 'HTTPBasicAuth' if username else None
            downloaded = self.dl.download(url=ics, local=filename, params={username:username, password:password}, verify=verify, auth=auth)
            if downloaded is False:
                self.logger.error('Could not download online ics file {0}.'.format(ics))
                return {}
            self.logger.debug('Online ics {} successfully downloaded to {}'.format(ics, filename))
            ics = os.path.normpath(filename)
        try:
            ics = '{}/{}'.format(self._directory, ics) if self._directory not in ics else ics
            with open(ics, 'r') as f:
                ical = f.read()
                self.logger.debug('Read offline ical file {}'.format(ics))
        except IOError as e:
            self.logger.error('Could not open local ics file {0}: {1}'.format(ics, e))
            return {}

        return self._parse_ical(ical, ics, prio)

    def _parse_date(self, val, dtzinfo, par=''):
        if par.startswith('TZID='):
            tmp, par, timezone = par.partition('=')
        if 'T' in val:  # ISO datetime
            val, sep, off = val.partition('Z')
            dt = datetime.datetime.strptime(val, "%Y%m%dT%H%M%S")
        else:  # date
            y = int(val[0:4])
            m = int(val[4:6])
            d = int(val[6:8])
            dt = datetime.datetime(y, m, d)
        dt = dt.replace(tzinfo=dtzinfo)
        return dt

    def _parse_ical(self, ical, ics, prio):
        events = {}
        tzinfo = self.shtime.tzinfo()
        ical = ical.replace("\r\n\\n", ", ")
        ical = ical.replace("\n\\n", ", ").replace("\\n", ", ")
        ical = ical.replace("\\n", ", ")
        for line in ical.splitlines():
            if line == 'BEGIN:VEVENT':
                prio_count = {'UID': 1, 'SUMMARY': 1, 'SEQUENCE': 1, 'RRULE': 1, 'CLASS': 1, 'DESCRIPTION': 1}
                event = {'EXDATES': []}
            elif line == 'END:VEVENT':
                if 'UID' not in event:
                    self.logger.warning("problem parsing {0} no UID for event: {1}".format(ics, event))
                    continue
                if 'SUMMARY' not in event:
                    self.logger.warning("problem parsing {0} no SUMMARY for UID: {1}".format(ics, event['UID']))
                    continue
                if 'DTSTART' not in event:
                    self.logger.warning("problem parsing {0} no DTSTART for UID: {1}".format(ics, event['UID']))
                    continue
                if 'DTEND' not in event:
                    self.logger.warning("Warning in parsing {0} no DTEND for UID: {1}. Setting DTEND from DTSTART".format(ics, event['UID']))
                    # Set end to start time:
                    event['DTEND'] = event['DTSTART']
                    continue
                if 'RRULE' in event:
                    event['RRULE'] = self._parse_rrule(event, tzinfo)
                if event['UID'] in events:
                    if 'RECURRENCE-ID' in event:
                        events[event['UID']]['EXDATES'].append(event['RECURRENCE-ID'])
                        events[event['UID'] + event['DTSTART'].isoformat()] = event
                    else:
                        self.logger.warning("problem parsing {0} duplicate UID: {1} ({2})".format(ics, event['UID'], event['SUMMARY']))
                        continue
                else:
                    events[event['UID']] = event
                del(event)
            elif 'event' in locals():
                key, sep, val = line.partition(':')
                key, sep, par = key.partition(';')
                key = key.upper()
                if key == 'TZID':
                    tzinfo = dateutil.tz.gettz(val)
                elif key in ['UID', 'SUMMARY', 'SEQUENCE', 'RRULE', 'CLASS', 'DESCRIPTION']:
                    if event.get(key) is None or prio_count[key] == prio:
                        prio_count[key] = prio_count.get(key) + 1
                        event[key] = val
                    else:
                        self.logger.info('Value {} for entry {} ignored because of prio setting'.format(val, key))
                elif key in ['DTSTART', 'DTEND', 'EXDATE', 'RECURRENCE-ID']:
                    try:
                        date = self._parse_date(val, tzinfo, par)
                    except Exception as e:
                        self.logger.warning("Problem parsing: {0}: {1}".format(ics, e))
                        continue
                    if key == 'EXDATE':
                        event['EXDATES'].append(date)  # noqa
                    else:
                        event[key] = date  # noqa
                else:
                    event[key] = val  # noqa
        return events

    def _parse_rrule(self, event, tzinfo):
        rrule = dict(a.split('=') for a in event['RRULE'].upper().split(';'))
        self.logger.debug("Rrule {0}".format(rrule))
        args = {}
        if 'FREQ' not in rrule:
            self.logger.debug("Rrule has no frequency")
            return
        freq = self.FREQ.index(rrule['FREQ'])
        self.logger.debug("Frequency: {0}".format(freq))
        del(rrule['FREQ'])
        if 'DTSTART' not in rrule:
            rrule['DTSTART'] = event['DTSTART']
        if 'WKST' in rrule:
            if rrule['WKST'] in self.DAYS:
                rrule['WKST'] = self.DAYS.index(rrule['WKST'])
            else:
                rrule['WKST'] = int(rrule['WKST'])
        if 'BYDAY' in rrule:
            day = rrule['BYDAY']
            if day.isalpha():
                if day in self.DAYS:
                    day = self.DAYS.index(day)
            else:
                n = int(day[0:-2])
                day = self.DAYS.index(day[-2:])
                day = dateutil.rrule.weekday(day, n)
            rrule['BYWEEKDAY'] = day
            del(rrule['BYDAY'])
        if 'COUNT' in rrule:
            rrule['COUNT'] = int(rrule['COUNT'])
        if 'INTERVAL' in rrule:
            rrule['INTERVAL'] = int(rrule['INTERVAL'])
        if 'BYMONTHDAY' in rrule:
            rrule['BYMONTHDAY'] = int(rrule['BYMONTHDAY'])
        if 'BYMONTH' in rrule:
            rrule['BYMONTH'] = int(rrule['BYMONTH'])
        if 'UNTIL' in rrule:
            try:
                rrule['UNTIL'] = self._parse_date(rrule['UNTIL'], tzinfo)
            except Exception as e:
                self.logger.warning("Problem parsing UNTIL: {1} --- {0} ".format(event, e))
                return
        for par in rrule:
            args[par.lower()] = rrule[par]

        return dateutil.rrule.rrule(freq, **args)
