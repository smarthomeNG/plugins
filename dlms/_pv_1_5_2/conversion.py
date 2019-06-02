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

class Conversion:
    def _to_datetime_ZST10(self, text):
        """
        this function converts a string of form "YYMMDDhhmm" into a datetime object
        :param text: string to convert
        :return: a datetime object upon success or None if error found by malformed string
        """
        if len(text) != 10:
            self.logger.error("too few characters for date/time code from OBIS")
            return None
        if not text.isdigit():
            self.logger.error("only digits allowed for date/time code from OBIS")
            return None
        else:
            year = int(text[0:2])+2000
            month = int(text[2:4])
            day = int(text[4:6])
            hour = int(text[6:8])
            minute = int(text[8:10])
            return datetime.datetime(year,month,day,hour,minute,0)

    def _to_datetime_ZST12(self, text):
        """
        this function converts a string of form "YYMMDDhhmmss" into a datetime object
        :param text: string to convert
        :return: a datetime object upon success or None if error found by malformed string
        """
        if len(text) != 12:
            self.logger.error("too few characters for date/time code from OBIS")
            return None
        if not text.isdigit():
            self.logger.error("only digits allowed for date/time code from OBIS")
            return None
        else:
            year = int(text[0:2])+2000
            month = int(text[2:4])
            day = int(text[4:6])
            hour = int(text[6:8])
            minute = int(text[8:10])
            second = int(text[10:12])
            return datetime.datetime(year,month,day,hour,minute,second)

    def _to_date_D6(self, text):
        """
        this function converts a string of form "YYMMDD" into a datetime.date object
        :param text: string to convert
        :return: a datetime.date object upon success or None if error found by malformed string
        """
        if len(text) != 6:
            self.logger.error("too few characters for date code from OBIS")
            return None
        if not text.isdigit():
            self.logger.error("only digits allowed for date code from OBIS")
            return None
        else:
            year = int(text[0:2])+2000
            month = int(text[2:4])
            day = int(text[4:6])
            return datetime.date(year,month,day)

    def _to_time_Z4(self, text):
        """
        this function converts a string of form "hhmm" into a datetime.time object
        :param text: string to convert
        :return: a datetime.time object upon success or None if error found by malformed string
        """
        if len(text) != 4:
            self.logger.error("too few characters for time code from OBIS")
            return None
        if not text.isdigit():
            self.logger.error("only digits allowed for time code from OBIS")
            return None
        else:
            hour = int(text[0:2])
            minute = int(text[2:4])
            return datetime.time(hour,minute)

    def _to_time_Z6(self, text):
        """
        this function converts a string of form "hhmmss" into a datetime.time object
        :param text: string to convert
        :return: a datetime.time object upon success or None if error found by malformed string
        """
        if len(text) != 6:
            self.logger.error("too few characters for time code from OBIS")
            return None
        if not text.isdigit():
            self.logger.error("only digits allowed for time code from OBIS")
            return None
        else:
            hour = int(text[0:2])
            minute = int(text[2:4])
            second = int(text[4:6])
            return datetime.time(hour,minute,second)

    def _convert_value( self, v, converter = 'str'):
        """
        This function converts the OBIS value to a user chosen value
        :param v: the value to convert from given as string
        :param converter: should contain one of ['str','float', 'int','ZST10', 'ZST12', 'D6', 'Z6', 'Z4', 'num']
        :return: after successful conversion the value in converted form
        """

        if converter == 'str' or len(converter) == 0:
            return v

        if converter == 'float':
            try:
                return float(v)
            except ValueError:
                self.logger.error("Could not convert from '{}' to a float".format(v))
                return None

        if converter == 'int':
            try:
                return int(v)
            except ValueError:
                self.logger.error("Could not convert from '{}' to an integer".format(v))
                return None

        if converter == 'ZST10':
            if len(v) == 10 and v.isdigit():
                # this is a date!
                v = self._to_datetime_ZST10(v)
                return v
            else:
                self.logger.error("Could not convert from '{}' to a Datetime".format(v))

        if converter == 'ZST12':
            if len(v) == 12 and v.isdigit():
                # this is a date!
                v = self._to_datetime_ZST12(v)
                return v
            else:
                self.logger.error("Could not convert from '{}' to a Datetime".format(v))

        if converter == 'D6':
            if len(v) == 6 and v.isdigit():
                # this is a date!
                v = self._to_date_D6(v)
                return v
            else:
                self.logger.error("Could not convert from '{}' to a Datetime".format(v))

        if converter == 'Z6':
            if len(v) == 6 and v.isdigit():
                # this is a date!
                v = self._to_time_Z6(v)
                return v
            else:
                self.logger.error("Could not convert from '{}' to a Datetime".format(v))

        if converter == 'Z4':
            if len(v) == 4 and v.isdigit():
                # this is a date!
                v = self._to_time_Z4(v)
                return v
            else:
                self.logger.error("Could not convert from '{}' to a Datetime".format(v))

        if converter == 'num':
            try:
                return int(v)
            except ValueError:
                pass

            try:
                return float(v)
            except ValueError:
                pass

        return v

