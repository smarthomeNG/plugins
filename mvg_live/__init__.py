#!/usr/bin/env python3
#
#########################################################################
#  Copyright 2017 René Frieß                      rene.friess(a)gmail.com
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
from mvg import MvgApi
from lib.model.smartplugin import SmartPlugin

class MVG_Live(SmartPlugin):
    ALLOW_MULTIINSTANCE = False
    PLUGIN_VERSION = "1.6.0"

    def __init__(self, sh, *args, **kwargs):
        """
        Initializes the plugin
        """
        self.logger = logging.getLogger(__name__)

    def run(self):
        self.alive = True

    def stop(self):
        self.alive = False

    def get_station(self, station):
        mvg_station = MvgApi.station(station)
        if mvg_station:
            return mvg_station

    def get_station_departures(self, station):
        mvg_station = self.get_station(station)
        if mvg_station:
            mvgapi = MvgApi(mvg_station['id'])
            return mvgapi.departures()
        else:
            logger.error("Station %s does not exist."%station)