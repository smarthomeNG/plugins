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

class Mode():

    _mode_hvac = 2          # 1=comfort, 2=standby, 3=night, 4=frost
    _mode_before_frost = 0  # store mode when turning frost mode on to restore it later

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        self._mode_hvac = 2
        self._mode_before_frost = 0


    @property
    def comfort(self):
        """
        Property: comfort mode

        :param value: set comfort mode state
        :type value: bool

        :return: actual comfort mode state
        :rtype: bool
        """
        return (self._mode_hvac == 1)

    @comfort.setter
    def comfort(self, value):

        if isinstance(value, bool):
            if value:
                self._mode_hvac = 1
            elif self._mode_hvac == 1:
                self._mode_hvac = 2
            return
        else:
            self._type_error('non-boolean')
            return


    @property
    def standby(self):
        """
        Property: standby mode

        :param value: set standby mode state
        :type value: bool

        :return: actual standby mode state
        :rtype: bool
        """
        return (self._mode_hvac == 2)

    @standby.setter
    def standby(self, value):

        if isinstance(value, bool):
            if value:
                self._mode_hvac = 2
            elif self._mode_hvac == 2:
                self._mode_hvac = 2
            return
        else:
            self._type_error('non-boolean')
            return


    @property
    def night(self):
        """
        Property: night mode

        :param value: set night mode state
        :type value: bool

        :return: actual night mode state
        :rtype: bool
        """
        return (self._mode_hvac == 3)

    @night.setter
    def night(self, value):

        if isinstance(value, bool):
            if value:
                self._mode_hvac = 3
            elif self._mode_hvac == 3:
                self._mode_hvac = 2
            return
        else:
            self._type_error('non-boolean')
            return


    @property
    def frost(self):
        """
        Property: frost mode

        :param value: set frost mode state
        :type value: bool

        :return: actual frost mode state
        :rtype: bool
        """
        return (self._mode_hvac == 4)

    @frost.setter
    def frost(self, value):

        if isinstance(value, bool):
            if value:
                self._mode_before_frost = self._mode_hvac
                self._mode_hvac = 4
            elif self._mode_hvac == 4:
                if self._mode_before_frost >= 1 and self._mode_before_frost <= 3:
                    self._mode_hvac = self._mode_before_frost
                else:
                    self._mode_hvac = 2
            return
        else:
            self._type_error('non-boolean')
            return


    @property
    def hvac(self):
        """
        Property: hvac mode

        :param value: set hvac mode state
        :type value: int

        :return: actual hvac mode state
        :rtype: int
        """
        return self._mode_hvac

    @hvac.setter
    def hvac(self, value):

        if isinstance(value, int):
            if value > 0 and value < 5:
                if value == 4:
                    self._mode_before_frost = self._mode_hvac
                self._mode_hvac = value
            else:
                self.logger.error("Cannot set property 'hvac' to a value of {}".format(value))
            return
        else:
            self._type_error('non-integer', value)
            return


    def _get_modename(self, mode):
        if mode == 1:
            return 'comfort'
        elif mode == 2:
            return 'standby'
        elif mode == 3:
            return 'night'
        elif mode == 4:
            return 'frost'
        return 'unknown'

    @property
    def mode(self):
        """
        Property: mode

        :return: actual mode as s readable string
        :rtype: str
        """
        return self._get_modename(self._mode_hvac)


    def __repr__(self):
        if self._mode_hvac == 4:
            return self.mode + f' ({self._get_modename(self._mode_before_frost)})'
        return self.mode


    def _type_error(self, err, value=None):
        prop = inspect.stack()[1][3]
        #self.logger.error("Cannot set property '{}' of item '{}' to a {} value".format(prop, self._item._path, err))
        if value is None:
            self.logger.error(f"Cannot set property '{prop}' to a {err} value")
        else:
            self.logger.error(f"Cannot set property '{prop}' to a {err} value of '{value}'")
        return

