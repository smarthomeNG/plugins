#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020-      Martin Sinn                         m.sinn@gmx.de
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  Part of rtr2 plugin to run with SmartHomeNG.
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

import inspect
import logging

class Temperature():

    def __init__(self, mode, comfort_temp=None, night_reduction=None, standby_reduction=None, fixed_reduction=True, hvac_mode=None, frost_temp=None):
        self.logger = logging.getLogger(__name__)

        self.mode = mode

        self._fixed_reduction = bool(fixed_reduction)
        self._night_reduction = self.to_float(night_reduction, 2)
        self._standby_reduction = self.to_float(standby_reduction, 1)
        self._temp_comfort = self.to_float(comfort_temp, 20)
        self.mode.hvac = self.to_int(hvac_mode, 2)
        self._temp_frost = self.to_float(frost_temp, 7)


    def to_int (self, value, default):
        try:
            return int(value)
        except:
            return int(default)

    def to_float (self, value, default):
        try:
            return float(value)
        except:
            return float(default)


    @property
    def set_temp(self):
        """
        Property: mode

        :return: actual set-temp
        :rtype: str
        """
        if self.mode.hvac == 1:
            return round(self._temp_comfort,2)
        elif self.mode.hvac == 2:
            return round(self._temp_comfort - self._standby_reduction, 2)
        elif self.mode.hvac == 3:
            return round(self._temp_comfort - self._night_reduction, 2)
        elif self.mode.hvac == 4:
            return round(self._temp_frost, 2)
        return 0.0

    @set_temp.setter
    def set_temp(self, value):

        if isinstance(value, int):
            value = round(float(value), 2)
        if isinstance(value, float):
            if self.mode.hvac == 1:
                self.comfort = value
            elif self.mode.hvac == 2:
                self.standby = value
            elif self.mode.hvac == 3:
                self.night = value
            return
        else:
            self._type_error('non-float')
            return


    @property
    def comfort(self):
        """
        Property: comfort temp

        :param value: set comfort temp
        :type value: float

        :return: comfort temp
        :rtype: float
        """
        return round(self._temp_comfort, 2)

    @comfort.setter
    def comfort(self, value):

        if isinstance(value, int):
            value = float(value)
        if isinstance(value, float):
            if not self._fixed_reduction:
                self._night_reduction = round(self._night_reduction - self._temp_comfort + value, 2)
                self._standby_reduction = round(self._standby_reduction - self._temp_comfort + value, 2)
            self._temp_comfort = value
            return
        else:
            self._type_error('non-float')
            return


    @property
    def standby(self):
        """
        Property: standby temp

        :param value: set standby temp
        :type value: float

        :return: standby temp
        :rtype: float
        """
        return round(self._temp_comfort - self._standby_reduction, 2)


    @standby.setter
    def standby(self, value):

        if isinstance(value, int):
            value = float(value)
        if isinstance(value, float):
            if self._fixed_reduction:
                self._temp_comfort = round(value + self._standby_reduction, 2)
            else:
                self._standby_reduction = round(self._standby_reduction - ((value + self._standby_reduction) - self._temp_comfort), 2)
            return
        else:
            self._type_error('non-float')
            return


    @property
    def night(self):
        """
        Property: night temp

        :param value: set night temp
        :type value: float

        :return: night temp
        :rtype: float
        """
        return round(self._temp_comfort - self._night_reduction, 2)


    @night.setter
    def night(self, value):

        if isinstance(value, int):
            value = float(value)
        if isinstance(value, float):
            if self._fixed_reduction:
                self._temp_comfort = round(value + self._night_reduction, 2)
            else:
                self._night_reduction = round(self._night_reduction - ((value + self._night_reduction) - self._temp_comfort), 2)
            return
        else:
            self._type_error('non-float')
            return


    @property
    def night_reduction(self):
        """
        Property: nighttime temp reduction

        :param value: set nighttime temp reduction
        :type value: float

        :return: nighttime temp reduction
        :rtype: float
        """
        return self._night_reduction


    @night_reduction.setter
    def night_reduction(self, value):

        if isinstance(value, int):
            value = float(value)
        if isinstance(value, float):
            self._night_reduction = value
            return
        else:
            self._type_error('non-float')
            return


    @property
    def standby_reduction(self):
        """
        Property: standby temp reduction

        :param value: set standby temp reduction
        :type value: float

        :return: standby temp reduction
        :rtype: float
        """
        return self._standby_reduction


    @standby_reduction.setter
    def standby_reduction(self, value):

        if isinstance(value, int):
            value = float(value)
        if isinstance(value, float):
            self._standby_reduction = value
            return
        else:
            self._type_error('non-float')
            return


    @property
    def fixed_reduction(self):
        """
        Property: fixed reduction (for standby and night)

        :param value: set night temp
        :type value: bool

        :return: fixed reduction
        :rtype: bool
        """
        return self._fixed_reduction


    @fixed_reduction.setter
    def fixed_reduction(self, value):

        if isinstance(value, bool):
            self._fixed_reduction = value
            return
        else:
            self._type_error('non-boolean')
            return


    @property
    def frost(self):
        """
        Property: night temp

        :param value: set frost temp
        :type value: float

        :return: frost temp
        :rtype: float
        """
        return self._temp_frost


    @frost.setter
    def frost(self, value):

        if isinstance(value, int):
            value = float(value)
        if isinstance(value, float):
            self._temp_frost = value
            return
        else:
            self._type_error('non-float')
            return


    def __repr__(self):
        return f"set-temp={self.set_temp} ({self.mode}) \n- comfort={self.comfort}, standby={self.standby}, night={self.night}, frost={self.frost} \n- standby reduction={self.standby_reduction}, night reduction={self.night_reduction} - fixed reduction={self.fixed_reduction}"


    def _type_error(self, err):
        prop = inspect.stack()[1][3]
        #self.logger.error("Cannot set property '{}' of item '{}' to a {} value".format(prop, self._item._path, err))
        self.logger.error("Cannot set property '{}' to a {} value".format(prop, err))
        return

