#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2016 - 2018 Bernd Meiners              Bernd.Meiners@mail.de
#########################################################################
#
#  This file is part of SmartHomeNG.py.
#  Visit:  https://github.com/smarthomeNG/
#          https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  SmartHomeNG.py is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHomeNG.py is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHomeNG.py. If not, see <http://www.gnu.org/licenses/>.
#########################################################################


__license__ = "GPL"
__version__ = "2.0"
__revision__ = "0.1"
__docformat__ = 'reStructuredText'

import datetime

CONVERTERS = {
    'int': 'int',
    'float': 'float',
    'ZST10': 'datetime',
    'ZST12': 'datetime',
    'D6': 'date',
    'Z6': 'time',
    'Z4': 'time',
    'num': 'num'
}


class Conversion:
    def _from_ZST10(self, text: str) -> datetime.datetime:
        """
        this function converts a string of form "YYMMDDhhmm" into a datetime object
        :param text: string to convert
        :return: a datetime object upon success or None if error found by malformed string
        """
        if len(text) != 10:
            raise ValueError("too few characters for date/time code from OBIS")

        year = int(text[0:2]) + 2000
        month = int(text[2:4])
        day = int(text[4:6])
        hour = int(text[6:8])
        minute = int(text[8:10])
        return datetime.datetime(year, month, day, hour, minute, 0)

    def _from_ZST12(self, text: str) -> datetime.datetime:
        """
        this function converts a string of form "YYMMDDhhmmss" into a datetime object
        :param text: string to convert
        :return: a datetime object upon success or None if error found by malformed string
        """
        if len(text) != 12:
            raise ValueError("too few characters for date/time code from OBIS")

        year = int(text[0:2]) + 2000
        month = int(text[2:4])
        day = int(text[4:6])
        hour = int(text[6:8])
        minute = int(text[8:10])
        second = int(text[10:12])
        return datetime.datetime(year, month, day, hour, minute, second)

    def _from_D6(self, text: str) -> datetime.date:
        """
        this function converts a string of form "YYMMDD" into a datetime.date object
        :param text: string to convert
        :return: a datetime.date object upon success or None if error found by malformed string
        """
        if len(text) != 6:
            raise ValueError("too few characters for date code from OBIS")

        year = int(text[0:2]) + 2000
        month = int(text[2:4])
        day = int(text[4:6])
        return datetime.date(year, month, day)

    def _from_Z4(self, text: str) -> datetime.time:
        """
        this function converts a string of form "hhmm" into a datetime.time object
        :param text: string to convert
        :return: a datetime.time object upon success or None if error found by malformed string
        """
        if len(text) != 4:
            raise ValueError("too few characters for time code from OBIS")

        hour = int(text[0:2])
        minute = int(text[2:4])
        return datetime.time(hour, minute)

    def _from_Z6(self, text: str) -> datetime.time:
        """
        this function converts a string of form "hhmmss" into a datetime.time object
        :param text: string to convert
        :return: a datetime.time object upon success or None if error found by malformed string
        """
        if len(text) != 6:
            raise ValueError("too few characters for time code from OBIS")

        hour = int(text[0:2])
        minute = int(text[2:4])
        second = int(text[4:6])
        return datetime.time(hour, minute, second)

    def _convert_value(self, val, converter: str = ''):
        """
        This function converts the OBIS value to a user chosen valalue
        :param val: the value to convert given as string
        :param converter: type of value, should contain one of CONVERTERS
        :return: after successful conversion the value in converted form
        """
        if converter not in CONVERTERS:
            return val

        try:
            if converter in ('num', 'float', 'int'):

                if converter in ('num', 'int'):
                    try:
                        return int(val)
                    except (ValueError, AttributeError):
                        if converter == 'int':
                            raise ValueError

                # try/except to catch floats like '1.0' and '1,0'
                try:
                    return float(val)
                except ValueError:
                    if ',' in val:
                        val = val.replace(',', '.')
                        return float(val)
                    else:
                        raise ValueError

            if not val.isdigit():
                raise ValueError("only digits allowed for date/time code from OBIS")

            if converter == 'int':
                return int(val)

            # try to find self._from_<converter> -> run it and return result
            if hasattr(self, f'_from_{converter}'):
                return getattr(self, f'_from_{converter}')(val)

            # no suitable converter found
            raise ValueError

        except ValueError as e:
            raise ValueError(f'could not convert from "{val}" to a {CONVERTERS[converter]} ({e})')
