#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
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
from . import StateEngineStruct

global_struct = {}
__allstructs = []


def create(_abitem, struct):
    _find_result = next((item for item in __allstructs if item["name"] == struct), False)
    if not _find_result:
        created_struct = StateEngineStruct.SeStructMain(_abitem, struct, global_struct)
        __allstructs.append({'name': struct, 'struct': created_struct})
        _abitem.logger.debug("Struct {} created. ", struct)
        return created_struct
    else:
        #_abitem.logger.debug("Struct {} already exists - skip creation. All structs: {}", struct, __allstructs)
        return _find_result.get("struct")


def exists(_abitem, struct):
    return True if struct in __allstructs else False
