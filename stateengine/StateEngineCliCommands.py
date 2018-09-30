#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2014-     Thomas Ernst                       offline@gmx.net
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
# noinspection PyUnresolvedReferences
from lib.model.smartplugin import SmartPlugin
from lib.plugin import Plugins
from bin.smarthome import VERSION


class SeCliCommands:
    def __init__(self, smarthome, items, logger):
        self.__items = items
        self._sh = smarthome
        self.logger = logger


        # Add additional cli commands if cli is active (and functionality to add own cli commands is available)
        try:
            cli = self._get_cli_plugin()
            if cli is None:
                self.logger.info("StateEngine: Additional CLI commands not registered because CLI plugin is not active")
            elif not isinstance(cli, SmartPlugin):
                self.logger.info("StateEngine: Additional CLI commands not registered because CLI plugin is too old")
            else:
                cli.commands.add_command("se_list", self.cli_list, "StateEngine", "se_list: list StateEngine items")
                cli.commands.add_command("se_detail", self.cli_detail, "StateEngine", "se_detail [seItem]: show details on StateEngine item [seItem]")
                self.logger.info("StateEngine: Two additional CLI commands registered")
        except AttributeError as err:
            self.logger.error("StateEngine: Additional CLI commands not registered because error occured.")
            self.logger.exception(err)

    # CLI command se_list
    # noinspection PyUnusedLocal
    def cli_list(self, handler, parameter, source):
        handler.push("Items for StateEngine Plugin\n")
        handler.push("==========================\n")
        for name in sorted(self.__items):
            self.__items[name].cli_list(handler)

    # CLI command se_detail
    # noinspection PyUnusedLocal
    def cli_detail(self, handler, parameter, source):
        item = self.__cli_getitem(handler, parameter)
        if item is not None:
            item.cli_detail(handler)

    # get item from parameter
    def __cli_getitem(self, handler, parameter):
        if parameter not in self.__items:
            handler.push("no StateEngine item \"{0}\" found.\n".format(parameter))
            return None
        return self.__items[parameter]

    def _get_cli_plugin(self):
        # noinspection PyBroadException
        try:
            for plugin in self._sh.return_plugins():
                if plugin.__module__ == 'plugins.cli':
                    return plugin
            return None
        except Exception:
            return None
