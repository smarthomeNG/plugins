#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2017-       Martin Sinn                         m.sinn@gmx.de
#           2016        Thomas Ernst
#           2012-2013   Marcus Popp                        marcus@popp.mx
#########################################################################
#  Commandline Interface for SmartHomeNG
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
import threading

import lib.connection
from lib.logic import Logics
from lib.model.smartplugin import SmartPlugin
from lib.utils import Utils


class CLIHandler(lib.connection.Stream):
    terminator = '\n'.encode()

    def __init__(self, smarthome, sock, source, updates, hashed_password, commands):
        """
        Constructor
        :param smarthome: SmartHomeNG instance
        :param sock: Socket
        :param source: Source
        :param updates: Flag: Updates allowed
        :param hashed_password: Hashed password that is required to logon
        :param commands: CLICommands instance containing available commands
        """
        lib.connection.Stream.__init__(self, sock, source)
        self.logger = logging.getLogger(__name__)
        self.source = source
        self.updates_allowed = updates
        self.sh = smarthome
        self.hashed_password = hashed_password
        self.commands = commands
        self.__prompt_type = ''
        self.push("SmartHomeNG v{0}\n".format(self.sh.version))

        if hashed_password is None:
            self.__push_helpmessage()
            self.__push_command_prompt()
        else:
            self.__push_password_prompt()

    def push(self, data):
        """
        Send data to client
        :param data: String to send
        """
        self.send(data.encode())

    def found_terminator(self, data):
        """
        Received data and found terminator (newline) in data
        :param data: Received data up to terminator
        """
        # Call process methods based on prompt type
        cmd = data.decode().strip()
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
            self.close()
            return

    def __process_command(self, cmd):
        """
        Process entered command
        :param cmd: entered command
        """
        if cmd in ('quit', 'q', 'exit', 'x'):
            self.push('bye\n')
            self.close()
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
        self.__echo_off()
        self.push("Password: ")
        self.__prompt_type = 'password'

    def __push_password_finished(self):
        """
        Push 'echo on' and newline to client
        :return:
        """
        self.__echo_on()
        self.push("\n")

    def __echo_off(self):
        """
        Send 'IAC WILL ECHO' to client, telling the client that we will echo.
        Check that reply is 'IAC DO ECHO', meaning that the client has understood.
        As we are not echoing entered text will be invisible
        """
        try:
            self.socket.settimeout(2)
            self.send(bytearray([0xFF, 0xFB, 0x01]))  # IAC WILL ECHO
            data = self.socket.recv(3)
            self.socket.setblocking(0)
            if data != bytearray([0xFF, 0xFD, 0x01]):  # IAC DO ECHO
                self.logger.error("Error at 'echo off': Sent b'\\xff\\xfb\\x01 , Expected reply b'\\xff\\xfd\\x01, received {0}".format(data))
                self.push("'echo off' failed. Bye")
                self.close()
        except Exception as e:
            self.push("\nException at 'echo off'. See log for details.")
            self.logger.exception(e)
            self.close()

    def __echo_on(self):
        """
        Send 'IAC WONT ECHO' to client, telling the client that we wont echo.
        Check that reply is 'IAC DONT ECHO', meaning that the client has understood.
        Now the client should be echoing and we do not have to care about this
        """
        try:
            self.socket.settimeout(2)
            self.send(bytearray([0xFF, 0xFC, 0x01]))  # IAC WONT ECHO
            data = self.socket.recv(3)
            self.socket.setblocking(0)
            if data != bytearray([0xFF, 0xFE, 0x01]):  # IAC DONT ECHO
                self.logger.error("Error at 'echo on': Sent b'\\xff\\xfc\\x01 , Expected reply b'\\xff\\xfe\\x01, received {0}".format(data))
                self.push("'echo off' failed. Bye")
                self.close()
        except Exception as e:
            self.push("\nException at 'echo on'. See log for details.")
            self.logger.exception(e)
            self.close()

    def __push_command_prompt(self):
        """Push command prompt to client"""
        self.push("CLI > ")
        self.__prompt_type = 'command'


class CLI(lib.connection.Server, SmartPlugin):

    PLUGIN_VERSION = '1.4.0'     # is checked against version in plugin.yaml

    def __init__(self, smarthome, update='False', ip='127.0.0.1', port=2323, hashed_password=''):
        """
        Constructor
        :param smarthome: smarthomeNG instance
        :param update: Flag: Updates allowed
        :param ip: IP to bind on
        :param port: Port to bind on
        :param hashed_password: Hashed password that is required to logon
        """
        self.logger = logging.getLogger(__name__)

        if hashed_password is None or hashed_password == '':
            self.logger.warning("CLI: You should set a password for this plugin.")
            hashed_password = None
        elif hashed_password.lower() == 'none':
            hashed_password = None
        elif not Utils.is_hash(hashed_password):
            self.logger.error("CLI: Value given for 'hashed_password' is not a valid hash value. Login will not be possible")

        lib.connection.Server.__init__(self, ip, port)
        self.sh = smarthome
        self.updates_allowed = Utils.to_bool(update)
        self.hashed_password = hashed_password
        self.commands = CLICommands(self.sh, self.updates_allowed)
        self.alive = False


    def handle_connection(self):
        """
        Handle incoming connection
        """
        sock, address = self.accept()
        if sock is None:
            return
        self.logger.debug("{}: incoming connection from {} to {}".format(self._name, address, self.address))
        CLIHandler(self.sh, sock, address, self.updates_allowed, self.hashed_password, self.commands)

    def run(self):
        """
        Called by SmartHomeNG to start plugin
        """
        self.alive = True

    def stop(self):
        """
        Called by SmarthomeNG to stop plugin
        """
        self.alive = False
        self.close()

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

    def __init__(self, smarthome, updates_allowed=False):
        """
        Constructor
        :param smarthome: sh.py instance
        :param updates_allowed: bool True: basic commands may do updates, False: basic commands may not do updates
        """
        self.sh = smarthome
        self.logger = logging.getLogger(__name__)
        self.updates_allowed = updates_allowed
        self._commands = {}

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
        if self.logics is None:
            self.logics = Logics.get_instance()
        for command, data in self._commands.items():
            if cmd == command or cmd.startswith(command + " "):
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
                handler.push("{0}\n".format(item.id()))
        else:
            if match:
                items = self.sh.match_items(parameter)
                childs = False
            else:
                items = [self.sh.return_item(parameter)]
                childs = True
            if len(items):
                for item in items:
                    if hasattr(item, 'id'):
                        if item.type():
                            handler.push("{0} = {1}\n".format(item.id(), item()))
                        else:
                            handler.push("{}\n".format(item.id()))
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
            items = self.sh.match_items(parameter)
        else:
            items = [self.sh.return_item(parameter)]
        if len(items):
            for item in items:
                # noinspection PyProtectedMember
                if hasattr(item, 'id') and item._type:
                    handler.push("Item {} ".format(item.id()))
                    handler.push("{\n")
                    handler.push("  type: {}\n".format(item.type()))
                    handler.push("  value: {}\n".format(item()))
                    handler.push("  age: {}\n".format(item.age()))
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
        for command, data in sorted(self._commands.items()):
            if parameter == '' or data['group'] == parameter:
                if data['usage'] is not None:
                    handler.push(data['usage'] + '\n')
        if parameter != '':
            if not parameter in ['item', 'log', 'logic', 'scheduler']:
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
            logs = self.sh.return_logs()
            if parameter not in logs:
                handler.push("Log '{0}' does not exist\n".format(parameter))
                log = None
            else:
                log = logs[parameter]

        if log is not None:
            log.clean(self.sh.now())

    # noinspection PyUnusedLocal
    def _cli_il(self, handler, parameter, source):
        """
        CLI command "il" - list all items
        :param handler: CLIHandler instance
        :param parameter: Parameters used to call the command
        :param source: Source
        """
        handler.push("Items:\n======\n")
        for item in self.sh.return_items():
            if item.type():
                handler.push("{0} = {1}\n".format(item.id(), item()))
            else:
                handler.push("{0}\n".format(item.id()))

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
        items = self.sh.match_items(path)
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

    # noinspection PyUnusedLocal
    def _cli_logd(self, handler, parameter, source):
        if parameter is None or parameter == "":
            log = self.sh.log
        else:
            logs = self.sh.return_logs()
            if parameter not in logs:
                handler.push("Log '{0}' does not exist\n".format(parameter))
                log = None
            else:
                log = logs[parameter]

        if log is not None:
            handler.push("Log dump of '{0}':\n".format(log._name))
            for entry in log.last(10):
                values = [str(value) for value in entry]
                handler.push(str(values))
                handler.push("\n")
