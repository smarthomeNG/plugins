#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2012-2013   Marcus Popp                        marcus@popp.mx
# Copyright 2016        Thomas Ernst
# Copyright 2017-       Martin Sinn                         m.sinn@gmx.de
# Copyright 2017-       Serge Wagener                serge@wagener.family
# Copyright 2020        Bernd Meiners               Bernd.Meiners@mail.de
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  Commandline Interface for SmartHomeNG
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
import threading

import lib.log
from lib.logic import Logics
from lib.item import Items
from lib.model.smartplugin import SmartPlugin
from .webif import WebInterface

from lib.utils import Utils
from lib.network import Tcp_server

from lib.shtime import Shtime

shtime = Shtime.get_instance()


class CLIHandler:
    terminator = '\n'.encode()

    def __init__(self, smarthome, client, source, updates, hashed_password, commands, plugin):
        """
        Constructor
        :param smarthome: SmartHomeNG instance
        :param client: lib.network.__Client
        :param source: Source
        :param updates: Flag: Updates allowed
        :param hashed_password: Hashed password that is required to logon
        :param commands: CLICommands instance containing available commands
        """
        self.logger = logging.getLogger(__name__)
        self.source = source
        self.updates_allowed = updates
        self.sh = smarthome
        self.hashed_password = hashed_password
        self.commands = commands
        self.__prompt_type = ''
        self.__client = client
        self.__socket = self.__client.socket
        self.__client.set_callbacks(data_received=self.data_received)
        self.push("SmartHomeNG v{}  -  cli plugin v{}\n".format(self.sh.version, CLI.PLUGIN_VERSION))

        if hashed_password is None:
            self.__push_helpmessage()
            self.__push_command_prompt()
        else:
            self.__push_password_prompt()
        self.plugin = plugin
        self.logger.debug("CLI Handler init with updates {}".format("allowed" if updates else "not allowed"))

    def push(self, data):
        """
        Send data to client
        :param data: String to send
        """
        self.__client.send(data)

    def data_received(self, server, client, cmd):
        """
        Received data and found terminator (newline) in data
        :param data: Received data up to terminator
        """
        # Call process methods based on prompt type
        if self.__prompt_type == 'password':
            self.__process_password(cmd)
        elif self.__prompt_type == 'command':
            self.__process_command(cmd)

    def __process_password(self, cmd):
        """
        Process entered password
        :param cmd: entered password
        """
        self.__push_password_finished()
        if Utils.check_hashed_password(cmd, self.hashed_password):
            self.logger.debug("CLI: {0} Authorization succeeded".format(self.source))
            self.__push_helpmessage()
            self.__push_command_prompt()
            return
        else:
            self.logger.debug("CLI: {0} Authorization failed".format(self.source))
            self.push("Authorization failed. Bye\n")
            self.__client.close()
            return

    def __process_command(self, cmd):
        """
        Process entered command
        :param cmd: entered command
        """
        self.logger.debug("CLI: process command '{}'".format(cmd))
        if cmd == '':
            self.__push_command_prompt()
        else:
            if cmd in ('quit', 'q', 'exit', 'x'):
                self.push('bye\n')
                self.__client.close()
                return
            else:
                if not self.commands.execute(self, cmd, self.source):
                    self.push("Unknown command.\n")
                    self.__push_helpmessage()
                self.__push_command_prompt()

    def __push_helpmessage(self):
        """Push help message to client"""
        self.push("Enter 'help' for a list of available commands.\n")

    def __push_password_prompt(self):
        """
        Push 'echo off' and password prompt to client.
        """
        self.__client.send_echo_off()
        self.push("Password: ")
        self.__prompt_type = 'password'

    def __push_password_finished(self):
        """
        Push 'echo on' and newline to client
        :return:
        """
        self.__client.send_echo_on()
        self.push("\n")

    def __push_command_prompt(self):
        """Push command prompt to client"""
        self.push("CLI > ")
        self.__prompt_type = 'command'


class CLI(SmartPlugin):

    PLUGIN_VERSION = '1.8.2'     # is checked against version in plugin.yaml

    def __init__(self, sh):
        """
        Initalizes the plugin.

        If the sh object is needed at all, the method self.get_sh() should be used to get it.
        There should be almost no need for a reference to the sh object any more.

        Plugins have to use the new way of getting parameter values:
        use the SmartPlugin method get_parameter_value(parameter_name). Anywhere within the Plugin you can get
        the configured (and checked) value for a parameter by calling self.get_parameter_value(parameter_name). It
        returns the value in the datatype that is defined in the metadata.
        """

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        self.items = Items.get_instance()

        self.updates_allowed = self.get_parameter_value('update')
        self.ip = self.get_parameter_value('ip')
        self.port = self.get_parameter_value('port')
        self.hashed_password = self.get_parameter_value('hashed_password')
        if self.hashed_password is None or self.hashed_password == '':
            self.logger.warning("CLI: You should set a password for this plugin.")
            self.hashed_password = None
        elif self.hashed_password.lower() == 'none':
            self.hashed_password = None
        elif not Utils.is_hash(self.hashed_password):
            self.logger.error("CLI: Value given for 'hashed_password' is not a valid hash value. Login will not be possible")

        name = 'plugins.' + self.get_fullname()
        self.server = Tcp_server(host=self.ip, port=self.port, name=name, mode=Tcp_server.MODE_TEXT_LINE)
        self.server.set_callbacks(incoming_connection=self.handle_connection)
        self.commands = CLICommands(self.get_sh(), self.updates_allowed, self)
        self.alive = False

        # On initialization error use:
        #   self._init_complete = False
        #   return

        # if plugin should start even without web interface
        self.init_webinterface(WebInterface)
        # if plugin should not start without web interface
        # if not self.init_webinterface():
        #     self._init_complete = False

    def handle_connection(self, server, client):
        """
        Handle incoming connection
        """
        self.logger.debug("Incoming connection from {}".format(client.name))
        CLIHandler(self.get_sh(), client, client.name, self.updates_allowed, self.hashed_password, self.commands, self)

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        self.alive = True
        self.server.start()

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called")
        self.alive = False
        try:  # keep some ugly errors on keyboard interrupt to yourself
            self.server.close()
        except:
            pass

    def add_command(self, command, function, usage):
        """
        Add command to list of available commands
        :param command: Command to add
        :param function: Function to execute for command
        :param usage: Usage string for help-command
        """
        self.commands.add_command(command, function, usage)

    def remove_command(self, command):
        """
        Remove a command from the list of available commands
        :param command: Command to remove
        :return: True: command found and removed, False: command not found
        """
        return self.commands.remove_command(command)


class CLICommands:
    """
    Class containing handling for CLI commands as well as a basic set of commands
    """

    logics = None

    def __init__(self, smarthome, updates_allowed=False, plugin=None):
        """
        Constructor
        :param smarthome: sh.py instance
        :param updates_allowed: bool True: basic commands may do updates, False: basic commands may not do updates
        """
        self.sh = smarthome
        self.plugin = plugin
        self.logger = logging.getLogger(__name__)
        self.updates_allowed = updates_allowed
        self._commands = {}

        self.logger.debug("add basic commands")
        # Add basic commands
        self.add_command('il', self._cli_il, 'item', 'il: list all items (with values) - command alias: la')
        self.add_command('la', self._cli_il, 'item', None)
        self.add_command('dump', self._cli_ii, 'item', None)
        self.add_command('if', self._cli_if, 'item', 'if: list the first level items\nif [item]: list item and every child item (with values)')
        self.add_command('ii', self._cli_ii, 'item', 'ii [item]: dump detail-information about a given item - command alias: dump')

        self.add_command('iupdate', self._cli_iupdate, 'item', 'iupdate [item] = [value]: update the item with value - command alias: update')
        self.add_command('update', self._cli_iupdate, 'item', None)
        self.add_command('iup', self._cli_iupdate, 'item', 'iup: alias for iupdate - command alias: up')
        self.add_command('up', self._cli_iupdate, 'item',  None)

        self.add_command('logc', self._cli_logc, 'log', 'logc [log]: clean (memory) log')
        self.add_command('logd', self._cli_logd, 'log', 'logd [log]: log dump of (memory) log')
        self.add_command('logl', self._cli_logl, 'log', 'logl: list existing (memory) logs')

        self.add_command('ll', self._cli_ll, 'logic', 'll: list all logics and next execution time - command alias: lo')
        self.add_command('lo', self._cli_ll, 'logic', None)   # old command
        self.add_command('li', self._cli_dumpl, 'logic', 'li [logic]: logic information - dump details about given logic')
        self.add_command('dumpl', self._cli_dumpl, 'logic', None)
        self.add_command('ld', self._cli_ld, 'logic', 'ld [logic]: disables logic - command alias: dl')
        self.add_command('dl', self._cli_ld, 'logic', None)   # old command
        self.add_command('le', self._cli_le, 'logic', 'le [logic]: enables logic - command alias: el')
        self.add_command('el', self._cli_le, 'logic', None)   # old command
        self.add_command('lr', self._cli_lr, 'logic', 'lr [logic]: reload a logic - command alias: rl')
        self.add_command('rl', self._cli_lr, 'logic', None)
        self.add_command('lrr', self._cli_lrr, 'logic', 'lrr [logic]: reload and run a logic - command alias: rr')
        self.add_command('rr', self._cli_lrr, 'logic', None)
        self.add_command('lt', self._cli_lt, 'logic', 'lt [logic]: trigger a logic - command alias: tr')
        self.add_command('tr', self._cli_lt, 'logic', None)

        self.add_command('sl', self._cli_sl, 'scheduler', 'sl: list all scheduler tasks by name')
        self.add_command('st', self._cli_sl, 'scheduler', 'st: list all scheduler tasks by execution time')
        self.add_command('si', self._cli_si, 'scheduler', 'si [task]: show details for given scheduler task')

        self.add_command('tl', self._cli_tl, '???', 'tl: list current thread names')
        self.add_command('rt', self._cli_rt, '???', 'rt: return runtime')
        self.add_command('help', self._cli_help2, '-', 'help [group]: show help for group of commands [item, log, logic, scheduler]' )
        self.add_command('h', self._cli_help2, '-', 'h: alias for help')
        self.logger.debug("finished adding basic commands")

    def add_command(self, command, function, group, usage):
        """
        Add command to list
        :param command: Command to add
        :param function: Function to execute for command
        :param usage: Usage string for help-command
        """
        if command in self._commands:
            self.logger.error("add_command: Trying to redefine an already existing command with {} ({})".format(command, str(usage)))
        self._commands[command] = {'function': function, 'group': group, 'usage': usage}

    def remove_command(self, command):
        """
        Remove a command from the list
        :param command: Command to remove
        :return: True: command found and removed, False: command not found
        """
        if command in self._commands:
            del self._commands[command]
            return True
        else:
            return False

    def execute(self, handler, cmd, source):
        """
        Execute an arbitrary command
        :param handler: CLIHandler to use for reply
        :param cmd: Received command
        :param source: Call source
        :return: TRUE: Command found and handled, FALSE: Unknown command, nothing done
        """
        if self.plugin and getattr(self.plugin, 'alive', False):
            if self.logics is None:
                self.logics = Logics.get_instance()
            for command, data in self._commands.items():
                if cmd == command or cmd.startswith(command + " "):
                    self.logger.debug("try to dispatch command '{}'".format(cmd))
                    try:
                        data['function'](handler, cmd.lstrip(command).strip(), source)
                    except Exception as e:
                        self.logger.exception(e)
                        handler.push("Exception \"{0}\" occured when executing command \"{1}\".\n".format(e, command))
                        handler.push("See smarthomeNG log for details\n")
                    return True
        return False

    # noinspection PyUnusedLocal
    def _cli_lt(self, handler, parameter, source):
        """
        CLI command "lt" - Trigger logic
        :param handler: CLIHandler instance
        :param parameter: Parameters used to call the command
        :param source: Source
        """
        if not self.updates_allowed:
            handler.push("Logic triggering is not allowed.\n")
            return
        if parameter is None or parameter == "":
            handler.push("Please name logic to trigger\n")
        elif parameter in self.logics.return_loaded_logics():
            self.logics.trigger_logic(parameter, by='CLI')
            handler.push("Logic '{0}' triggered.\n".format(parameter))
        else:
            handler.push("Logic '{0}' not found.\n".format(parameter))

    def _cli_dumpl(self, handler, parameter, source):
        if parameter in self.logics.return_loaded_logics():
            info = self.logics.get_logic_info(parameter, ordered=True)
#            handler.push("Logic {} ".format(info['name']))
            handler.push("{\n")
            for key in info:
                handler.push("  {}: {}\n".format(key, info[key]))
            handler.push("}\n")
        else:
            handler.push("Logic '{0}' not found.\n".format(parameter))

    def _cli_le(self, handler, parameter, source):
        if not self.updates_allowed:
            handler.push("Logic enabling is not allowed.\n")
            return
        if parameter in self.logics.return_loaded_logics():
            self.logics.return_logic(parameter).enable()
        else:
            handler.push("Logic '{0}' not found.\n".format(parameter))

    def _cli_ld(self, handler, parameter, source):
        if not self.updates_allowed:
            handler.push("Logic disabling is not allowed.\n")
            return
        if parameter in self.logics.return_loaded_logics():
            self.logics.return_logic(parameter).disable()
        else:
            handler.push("Logic '{0}' not found.\n".format(parameter))

    # noinspection PyUnusedLocal
    def _cli_lr(self, handler, parameter, source):
        """
        CLI command "lr" - Reload logic
        :param handler: CLIHandler instance
        :param parameter: Parameters used to call the command
        :param source: Source
        """
        if not self.updates_allowed:
            handler.push("Logic triggering is not allowed.\n")
            return
        if parameter is None or parameter == "":
            handler.push("Please name logic to reload\n")
        elif parameter in self.logics.return_loaded_logics():
            self.logics.load_logic(parameter)
            handler.push("Logic '{0}' reloaded.\n".format(parameter))
        else:
            handler.push("Logic '{0}' not found.\n".format(parameter))

    # noinspection PyUnusedLocal
    def _cli_lrr(self, handler, parameter, source):
        """
        CLI command "lrr" - Reload and trigger logic
        :param handler: CLIHandler instance
        :param parameter: Parameters used to call the command
        :param source: Source
        """
        if not self.updates_allowed:
            handler.push("Logic triggering is not allowed.\n")
            return
        if parameter is None or parameter == "":
            handler.push("Please name logic to reload and trigger")
        elif parameter in self.logics.return_loaded_logics():
            self.logics.load_logic(parameter)
            self.logics.trigger_logic(parameter, by='CLI')
            handler.push("Logic '{0}' reloaded and triggered.\n".format(parameter))
        else:
            handler.push("Logic '{0}' not found.\n".format(name))

    # noinspection PyUnusedLocal
    def _cli_ll(self, handler, parameter, source):
        """
        CLI command "ll" - List logics
        :param handler: CLIHandler instance
        :param parameter: Parameters used to call the command
        :param source: Source
        """
        handler.push("Logics:\n")
        for logic in sorted(self.logics.return_loaded_logics()):
            data = []
            info = self.logics.get_logic_info(logic)
            if not info['enabled']:
                data.append("disabled")
            if 'next_exec' in info:
                data.append("scheduled for {0}".format(info['next_exec']))
            handler.push("{0}".format(logic))
            if len(data):
                handler.push(" ({0})".format(", ".join(data)))
            handler.push("\n")


    def thread_sum(self, name, count):
        thread = dict()
        if count > 0:
            thread['name'] = name
            thread['sort'] = str(thread['name']).lower()
            thread['id'] = "(" + str(count) + " threads" + ")"
            thread['alive'] = True
        return thread

    # noinspection PyUnusedLocal,PyMethodMayBeStatic
    def _cli_tl(self, handler, parameter, source):
        """
        CLI command "tl" - list all threads with names
        :param handler: CLIHandler instance
        :param parameter: Parameters used to call the command
        :param source: Source
        """
        threads_count = 0
        cp_threads = 0
        http_threads = 0
        idle_threads = 0
        for thread in threading.enumerate():
            if thread.name.find("CP Server") == 0:
                cp_threads += 1
            if thread.name.find("HTTPServer") == 0:
                http_threads +=1
            if thread.name.find("idle") == 0:
                idle_threads +=1

        threads = []
        for t in threading.enumerate():
            if t.name.find("CP Server") != 0 and t.name.find("HTTPServer") != 0 and t.name.find("idle") != 0:
                thread = dict()
                thread['name'] = t.name
                thread['sort'] = str(t.name).lower()
                thread['id'] = ''    # t.ident
                thread['alive'] = t.is_alive()
                threads.append(thread)
                threads_count += 1

        if cp_threads > 0:
            threads.append(self.thread_sum("CP Server", cp_threads))
            threads_count += cp_threads
        if http_threads > 0:
            threads.append(self.thread_sum("HTTPServer", http_threads))
            threads_count += http_threads
        if idle_threads > 0:
            threads.append(self.thread_sum("idle", idle_threads))
            threads_count += idle_threads

        threads_sorted = sorted(threads, key=lambda k: k['sort'])

        handler.push("{0} Threads:\n".format(threads_count))
        for t in threads_sorted:
            handler.push("{:<30}     {}\n".format(t['name'], t['id']))

    # noinspection PyUnusedLocal
    def _cli_rt(self, handler, parameter, source):
        """
        CLI command "rt" - show runtime
        :param handler: CLIHandler instance
        :param parameter: Parameters used to call the command
        :param source: Source
        """
        handler.push("Runtime: {}\n".format(self.sh.runtime()))

    # noinspection PyUnusedLocal
    def _cli_if(self, handler, parameter, source):
        """
        CLI command "if" - list first level items
        :param handler: CLIHandler instance
        :param parameter: Parameters used to call the command
        :param source: Source
        """
        handler.push("Items:\n======\n")
#        handler.push("Items ({}):\n==========\n".format(self.plugin.items.item_count()))
        self._cli_ls_int(handler, parameter, '*' in parameter or ':' in parameter)

    def _cli_ls_int(self, handler, parameter, match=True):
        """
        Internal processing for command "ls"
        :param handler: CLIHandler instance
        :param parameter: Parameters used to call the command
        :param match: True: use match_items to select items, False: single item given
        """
        if not parameter:
            for item in self.sh:
                handler.push("{0}\n".format(item.property.path))
        else:
            if match:
                items = self.plugin.items.match_items(parameter)
                childs = False
            else:
                items = [self.plugin.items.return_item(parameter)]
                childs = True
            if len(items):
                for item in items:
                    if hasattr(item, 'id'):
                        if item.type():
                            handler.push("{0} = {1}\n".format(item.property.path, item()))
                        else:
                            handler.push("{}\n".format(item.property.path))
                        if childs:
                            for child in item:
                                self._cli_ls_int(handler, child.id())
            else:
                handler.push("Could not find path: {}\n".format(parameter))

    # noinspection PyUnusedLocal
    def _cli_ii(self, handler, parameter, source):
        """
        CLI command "dump" - dump item(s)
        :param handler: CLIHandler instance
        :param parameter: Parameters used to call the command
        :param source: Source
        """
        if '*' in parameter or ':' in parameter:
            items = self.plugin.items.match_items(parameter)
        else:
            items = [self.plugin.items.return_item(parameter)]
        if len(items):
            for item in items:
                # noinspection PyProtectedMember
                if hasattr(item, 'id') and item._type:
                    handler.push("Item {} ".format(item.property.path))
                    handler.push("{\n")
                    handler.push("  type: {}\n".format(item.type()))
                    handler.push("  value: {}\n".format(item()))
                    handler.push("  age: {}\n".format(item.property.last_change_age))
                    handler.push("  last_change: {}\n".format(item.last_change()))
                    handler.push("  changed_by: {}\n".format(item.changed_by()))
                    handler.push("  previous_value: {}\n".format(item.prev_value()))
                    handler.push("  previous_age: {}\n".format(item.prev_age()))
                    handler.push("  previous_change: {}\n".format(item.prev_change()))
                    if hasattr(item, 'conf'):
                        handler.push("  config: {\n")
                        for name in item.conf:
                            handler.push("    {}: {}\n".format(name, item.conf[name]))
                        handler.push("  }\n")
                    handler.push("  logics: [\n")
                    for trigger in item.get_logic_triggers():
                        handler.push("    {}\n".format(trigger))
                    handler.push("  ]\n")
                    handler.push("  triggers: [\n")
                    for trigger in item.get_method_triggers():
                        handler.push("    {}\n".format(trigger))
                    handler.push("  ]\n")
                    handler.push("}\n")
        else:
            handler.push("Nothing found\n")

    # noinspection PyUnusedLocal
    def _cli_help2(self, handler, parameter, source):
        """
        CLI command "help" - show available commands
        :param handler: CLIHandler instance
        :param parameter: Parameters used to call the command
        :param source: Source
        """
        self.logger.debug("execute _cli_help2 with parameter '{}'".format(parameter))
        for command, data in sorted(self._commands.items()):
            if parameter == '' or data['group'] == parameter:
                if data['usage'] is not None:
                    handler.push(data['usage'] + '\n')
        if parameter != '':
            if parameter not in ['item', 'log', 'logic', 'scheduler']:
                handler.push('help: Unknown group\n\n')
                data = self._commands['help']
                handler.push(data['usage'] + '\n')
            else:
                handler.push('\n')
            for command, data in sorted(self._commands.items()):
                if data['group'] == '???':
                    if data['usage'] is not None:
                        handler.push(data['usage'] + '\n')
        handler.push('quit, q: quit the session\n')

    # noinspection PyUnusedLocal
    def _cli_logc(self, handler, parameter, source):
        """
        CLI command "cl" - clear (memory) log
        :param handler: CLIHandler instance
        :param parameter: Parameters used to call the command
        :param source: Source
        """
        if parameter is None or parameter == "":
            log = self.sh.log
        else:
            logs = self.sh.logs.return_logs()
            if parameter not in logs:
                handler.push("Log '{0}' does not exist\n".format(parameter))
                log = None
            else:
                log = logs[parameter]

        if log is not None:
            log.clean(shtime.now())

    # noinspection PyUnusedLocal
    def _cli_il(self, handler, parameter, source):
        """
        CLI command "il" - list all items
        :param handler: CLIHandler instance
        :param parameter: Parameters used to call the command
        :param source: Source
        """
        handler.push("Items:\n======\n")
#        wrk = "Items ({}):".format(self.plugin.items.item_count())
#        wrk += '\n'+'='*len(wrk)+'\n'
#        handler.push(wrk)
        for item in self.plugin.items.return_items():
            if item.type():
                handler.push("{0} = {1}\n".format(item.property.path, item()))
            else:
                handler.push("{0}\n".format(item.property.path))
        wrk = "{} Items".format(self.plugin.items.item_count())
        wrk = '-' * len(wrk) + '\n' + wrk + '\n'
        handler.push(wrk)

    def _cli_iupdate(self, handler, parameter, source):
        """
        CLI command "update" - update item value
        :param handler: CLIHandler instance
        :param parameter: Parameters used to call the command
        :param source: Source
        """
        if not self.updates_allowed:
            handler.push("Updating items is not allowed.\n")
            return
        path, sep, value = parameter.partition('=')
        path = path.strip()
        value = value.strip()
        if not value:
            handler.push("You have to specify an item value. Syntax: up item = value\n")
            return
        items = self.plugin.items.match_items(path)
        if len(items):
            for item in items:
                if not item.type():
                    handler.push("Could not find item with a valid type specified: '{0}'\n".format(path))
                    return
                item(value, 'CLI', source)
        else:
            handler.push("Could not find any item with given pattern: '{0}'\n".format(path))

    # noinspection PyUnusedLocal
    def _cli_sl(self, handler, parameter, source):
        logics = sorted(self.logics.return_loaded_logics())
        tasks = []
        for name in sorted(self.sh.scheduler):
            nt = self.sh.scheduler.return_next(name)
            if name not in logics and nt is not None:
                task = {'nt': nt, 'name': name}
                tasks.append(task)

        handler.push("{} scheduler tasks:\n".format(len(tasks)))
        for task in tasks:
            handler.push("{0} (scheduled for {1})\n".format(task['name'], task['nt'].strftime('%Y-%m-%d %H:%M:%S%z')))

    # noinspection PyUnusedLocal
    def _cli_st(self, handler, parameter, source):
        logics = sorted(self.logics.return_loaded_logics())
        tasks = []
        for name in sorted(self.sh.scheduler):
            nt = self.sh.scheduler.return_next(name)
            if name not in logics and nt is not None:
                task = {'nt': nt, 'name': name}
                p = len(tasks)
                for i in range(0, len(tasks)):
                    if nt < tasks[i]['nt']:
                        p = i
                        break
                tasks.insert(p, task)

        handler.push("{} scheduler tasks by time:\n".format(len(tasks)))
        for task in tasks:
            handler.push("{0} {1}\n".format(task['nt'].strftime('%Y-%m-%d %H:%M:%S%z'), task['name']))

    # noinspection PyUnusedLocal
    def _cli_si(self, handler, parameter, source):
        if parameter not in self.sh.scheduler._scheduler:
            handler.push("Scheduler task '{}' not found\n".format(parameter))
        else:
            task = self.sh.scheduler._scheduler[parameter]
            handler.push("Task {}\n".format(parameter))
            handler.push("{\n")
            for key in task:
                handler.push("  {} = {}\n".format(key, task[key]))
            handler.push("}\n")

    from dateutil.tz import tzlocal
    from datetime import datetime
    # noinspection PyUnusedLocal
    def _cli_logd(self, handler, parameter, source):
        if parameter is None or parameter == "":
            log = self.sh.logs.return_logs()['env.core.log']
        else:
            logs = self.sh.logs.return_logs()
            if parameter not in logs:
                handler.push("Log '{0}' does not exist\n".format(parameter))
                log = None
            else:
                log = logs[parameter]

        if log is not None:
            handler.push("Log dump of '{0}':\n".format(log._name))
            for entry in log.last(10):
                ts = entry[0].strftime("%d.%m.%Y %H:%M:%S %Z")
                values = [str(value) for value in entry]
                del values[0]
                handler.push(ts + ': ' + str(values))
                handler.push("\n")

    # noinspection PyUnusedLocal
    def _cli_logl(self, handler, parameter, source):
        logs = self.sh.logs.return_logs()
        if logs is not None:
            handler.push("Existing (memory) logs:\n")
            for log in sorted(list(logs)):
                memlog_instance = self.sh.logs.return_logs()[log]
                if memlog_instance.handler is None:
                    loghandler_name = 'None'
                    loghandler_level = '?'
                    handler.push("- {:<20}(maxlen={})\n".format(log, memlog_instance.maxlen))
                else:
                    loghandler_name = memlog_instance.handler.get_name()
                    loghandler_level = logging.getLevelName(memlog_instance.handler.level)
                    handler.push("- {:<20}(maxlen={}, level={}, LogHandler={})\n".format(log, memlog_instance.maxlen, loghandler_level, loghandler_name))

