#!/usr/bin/env python3
#
#########################################################################
#  Copyright 2017 René Frieß                      rene.friess(a)gmail.com
#  Version 1.3.0.1
#########################################################################
#
#  This file is part of SmartHomeNG.
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

import logging
import MVGLive

from lib.model.smartplugin import SmartPlugin

class MVG_Live(SmartPlugin):
    ALLOW_MULTIINSTANCE = False
    PLUGIN_VERSION = "1.5.0.2"

    def __init__(self, sh, *args, **kwargs):
        """
        Initializes the plugin
        """
        self.logger = logging.getLogger(__name__)
        self._mvg_live = MVGLive.MVGLive()

    def run(self):
        self.alive = True

    def stop(self):
        self.alive = False

    def get_station_departures(self, station, timeoffset=0, entries=10, ubahn=True, tram=True, bus=True, sbahn=True):
        return self._mvg_live.getlivedata(station, timeoffset, entries, ubahn, tram, bus, sbahn)
