#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2016 <Onkel Andy>                    <onkelandy@hotmail.com>
#########################################################################
#  This file is part of SmartHomeNG
#
#  Denon AV plugin for SmartDevicePlugin class
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
#  along with SmartHomeNG  If not, see <http://www.gnu.org/licenses/>.
#########################################################################

import builtins
import os
import sys

if __name__ == '__main__':
    builtins.SDP_standalone = True

    class SmartPlugin:
        pass

    class SmartPluginWebIf:
        pass

    BASE = os.path.sep.join(os.path.realpath(__file__).split(os.path.sep)[:-3])
    sys.path.insert(0, BASE)

else:
    # don't clobber a True set by the real __main__ run - loading
    # commands.py via pydoc.locate('plugins.epson.commands') imports
    # this file a second time under its package name, hitting this branch
    # with __name__ != '__main__' even in standalone mode
    if not hasattr(builtins, 'SDP_standalone'):
        builtins.SDP_standalone = False

from lib.model.sdp.command import SDPCommandParseStr
from lib.model.sdp.declarations import TransportRule
from lib.model.sdp.globals import CONN_SER_ASYNC
from lib.model.smartdeviceplugin import SmartDevicePlugin, Standalone


class epson(SmartDevicePlugin):
    """Device class for Epson projectors."""

    PLUGIN_VERSION = '1.0.0'

    TRANSPORTS = (TransportRule(CONN_SER_ASYNC, requires='serialport'),)
    COMMAND_CLASS = SDPCommandParseStr
    LINE_TERMINATED = True


if __name__ == '__main__':
    s = Standalone(epson, sys.argv[0])
