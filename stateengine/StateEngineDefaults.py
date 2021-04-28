#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2014-2018 Thomas Ernst                       offline@gmx.net
#  Copyright 2019- Onkel Andy                       onkelandy@hotmail.com
#########################################################################
#  Finite state machine plugin for SmartHomeNG
#
#  This plugin is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This plugin is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this plugin. If not, see <http://www.gnu.org/licenses/>.
#########################################################################
import logging


startup_delay = 10

suspend_time = 3600

log_level = 0

suntracking_offset = 0

lamella_open_value = 0

instant_leaveaction = False

plugin_identification = "StateEngine Plugin"

VERBOSE = logging.DEBUG - 1

logger = None

se_logger = logging.getLogger('stateengine')

log_maxage = 0


def write_to_log(logger):
    logger.info("StateEngine default suntracking offset = {0}".format(suntracking_offset))
    logger.info("StateEngine default suntracking lamella open value = {0}".format(lamella_open_value))
    logger.info("StateEngine default startup delay = {0}".format(startup_delay))
    logger.info("StateEngine default suspension time = {0}".format(suspend_time))
    logger.info("StateEngine default instant_leaveaction = {0}".format(instant_leaveaction))
