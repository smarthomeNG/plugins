#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2016 <Onkel Andy>                    <onkelandy@hotmail.com>
#########################################################################
#  This file is part of SmartHomeNG.
#
#  Plugin to control AV Devices via TCP and/or RS232
#  Tested with Pioneer AV Receivers.
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
import re

VERBOSE1 = logging.DEBUG - 1
VERBOSE2 = logging.DEBUG - 2
logging.addLevelName(logging.DEBUG - 1, 'VERBOSE1')
logging.addLevelName(logging.DEBUG - 2, 'VERBOSE2')


class CreateExpectedResponse(object):
    def __init__(self, buffer, name, sendcommands, logger):
        self._buffer = buffer
        self._name = name
        self._send_commands = sendcommands

        self.logger = logger
        self.logger.debug(
            "Processing Response {}: Creating expected response. Buffer: {}. Name: {}. Sendcommands: {}".format(
                self._name, re.sub('[\r\n]', ' --- ', self._buffer), self._name, self._send_commands))

    def create_expected(self):
        expectedresponse = []
        try:
            for resp in self._send_commands:
                if resp.split(',', 2)[2].find('|') >= 0:
                    splitresponse = resp.split(';')[0].split('|')
                else:
                    splitresponse = [resp]
                splitresponse[0] = splitresponse[0].split(',', 2)[2]
                for i in range(0, len(splitresponse)):
                    splitresponse[i] = splitresponse[i].split(',')[0]
                    if not self._buffer == '':
                        splitresponse[i] = Translate(self._buffer.split("\r\n")[0], splitresponse[i], self._name, '', '', self.logger).wildcard()
                        self.logger.log(VERBOSE2, "Processing Response {}: Splitresponse after wildcard {}: {}.".format(
                            self._name, i, splitresponse[i]))
                wildcardresponse = []
                for wild in splitresponse:
                    if '?' not in wild:
                        wildcardresponse.append(wild)
                splitresponse = '|'.join(wildcardresponse)
                if not splitresponse == '':
                    expectedresponse.append(splitresponse)
        except Exception as err:
            self.logger.error(
                "Processing Response {}: Problems creating expected response list. Error: {}".format(self._name, err))
        return expectedresponse


class Translate(object):
    def __init__(self, code, dictentry, name, caller, specialparse, logger):
        self._code = code
        self._dictentry = dictentry
        self._caller = caller
        self._name = name
        self._specialparse = specialparse
        self._data = code
        self._command = dictentry

        self.logger = logger

    def wildcard(self):
        if self._command.find('?') >= 1:
            wildcard_replace = []
            wildcard = []
            command = self._command.split('*')[0]
            unprocessed = command
            command = command.replace('*{str}', '*')
            command = realcommand = command.replace('?{str}', '?')
            for i in range(9, 0, -1):
                command = command.replace('?' * i, '?')
            splitcommand = command.split('?')
            splitreal = unprocessed.split('*')[0].split('?')[1:]
            splitcommand = splitcommand[:-1] if splitcommand[len(splitcommand) - 1] == '' else splitcommand
            splitreal = splitreal[:-1] if splitcommand[len(splitcommand) - 1] == '' else splitreal
            self.logger.log(VERBOSE2,
                            "Processing Wildcard {}: Command: {} (original: {}), Splitcommand: {}. Splitreal: {}. Data: {}".format(
                                self._name, command, unprocessed, splitcommand, splitreal, self._data))
            for i in range(0, len(splitcommand)):
                try:
                    data = self._data.split(splitcommand[i], 1)[1]
                except Exception:
                    break
                try:
                    toreplace = data[0:data.find(splitcommand[i + 1])] if data.find(splitcommand[i + 1]) >= 0 else data
                    wildcard_replace.append(toreplace)
                except Exception:
                    wildcard_replace.append(data)
                try:
                    start = realcommand.find(splitcommand[i]) + len(splitcommand[i]) \
                        if i == 0 and not splitcommand[i] == '' else 0
                    try:
                        end = start + realcommand[start:].find(splitcommand[i + 1])
                        newstart = end + len(splitcommand[i + 1])
                    except Exception:
                        end = None
                        newstart = 0
                    wildcard.append(realcommand[start:end])
                    realcommand = realcommand[newstart:]
                except Exception:
                    pass
            if wildcard_replace:
                self.logger.log(VERBOSE2,
                                "Processing Wildcard {}: Wildcard replace: {}, Wildcard: {}.".format(
                                    self._name, wildcard_replace, wildcard))
                newstring = ''
                for i in range(0, len(splitcommand)):
                    try:
                        self.logger.log(VERBOSE2,
                                        "Processing Wildcard {}: replace {}, wildcard {}, splitreal {}".format(
                                            self._name, wildcard_replace[i], wildcard[i], splitreal[i]))
                        cond1 = len(wildcard_replace[i]) == len(wildcard[i])
                        cond2 = '{str}' in splitreal[i]
                        replace = True if ((cond1 or cond2) and not wildcard[i] == '') else False
                    except Exception:
                        replace = False
                    try:
                        if replace is True:
                            newstring += splitcommand[i] + wildcard_replace[i]
                            self.logger.log(VERBOSE2,
                                            "Processing Wildcard {}: Replace {} by {}.".format(self._name, wildcard[i],
                                                                                               wildcard_replace[i]))
                        else:
                            try:
                                newstring += splitcommand[i] + wildcard[i]
                            except Exception:
                                newstring += splitcommand[i] + wildcard_replace[i]
                    except Exception as err:
                        newstring = unprocessed
                        self.logger.log(VERBOSE2, "Processing Wildcard {}: Problem {}.".format(self._name, err))
                        break
            else:
                newstring = unprocessed.split('*')[0]
            self.logger.log(VERBOSE2, "Processing Wildcard {}: Command to compare: {}.".format(self._name, newstring))
        else:
            newstring = self._command.split('*')[0]

        return newstring

    def translate(self):
        origcaller = self._caller
        caller = 'parse' if self._caller == 'writedict' else self._caller
        str_code = ''
        result = ''
        try:
            self._code = eval(self._code)
        except Exception:
            pass
        try:
            code = self._code.lower()
        except Exception:
            try:
                str_code = str(self._code)
                if str_code in self._specialparse[self._dictentry][caller].keys():
                    code = str_code
                else:
                    code = ''
                    for i in range(0, len(str_code)):
                        code += str_code[i].replace(str_code[i], '*') if \
                            str_code[i].isdigit() else str_code[i]
            except Exception:
                code = self._code
        try:
            if '*' in code and caller == 'parse':
                result_temp = self._specialparse[self._dictentry][caller].get(code)
                z = 0
                for i in range(0, len(result_temp)):
                    if result_temp[i] == '*':
                        result += result_temp[i].replace('*', str_code[z])
                        z += 1
                    else:
                        result += result_temp[i]
                self._specialparse[self._dictentry][caller].update({self._code: result})
            elif '*' in code:
                result_temp = self._specialparse[self._dictentry][caller].get(code)
                z = 0
                for i in range(0, len(str_code)):
                    if str_code[i].isdigit() and result_temp[z] == '*':
                        result += result_temp[z].replace('*', str_code[i])
                        z += 1
                self._specialparse[self._dictentry]['parse'].update({result: self._code})
                self._specialparse[self._dictentry]['update'].update({self._code: result})
            else:
                result = self._specialparse[self._dictentry][caller].get(code)
        except Exception:
            result = None
        self.logger.log(VERBOSE2, "Translating {}: Called by: {}. Dictentry: {},"
                        " Code: {}, Result: {}.".format(
                            self._name, origcaller, self._dictentry, code, result))
        return result


class ConvertValue(object):
    def __init__(self, receivedvalue, expectedtype, invert, valuelength, command, name, specialcommands, logger):
        self._receivedvalue = receivedvalue
        self._expectedtype = expectedtype
        self._invert = invert
        self._valuelength = valuelength
        self._command = command[0] if isinstance(command, list) else command
        self._special_commands = specialcommands
        self._name = name
        self.logger = logger
        self.logger.debug(
            "Converting Values {}: Received Value is: {} with expected type {}. Invert: {}. Length: {}. Command: {}".format(
                self._name, receivedvalue, expectedtype, invert, valuelength, command))

    def _convertbool(self):
        try:
            if self._invert is True:
                self._receivedvalue = False if int(self._receivedvalue) == 1 and \
                    len(str(self._receivedvalue)) <= 1 and self._valuelength == 1 \
                    else True if int(self._receivedvalue) == 0 and \
                    len(str(self._receivedvalue)) <= 1 and self._valuelength == 1 \
                    else self._receivedvalue
            else:
                self._receivedvalue = True if int(self._receivedvalue) == 1 and \
                    len(str(self._receivedvalue)) <= 1 and self._valuelength == 1 \
                    else False if int(self._receivedvalue) == 0 and \
                    len(str(self._receivedvalue)) <= 1 and self._valuelength == 1 \
                    else self._receivedvalue
        except Exception:
            pass
        return self._receivedvalue

    def _convertdisplay(self):
        returnvalue = ['display', '']
        try:
            content = self._receivedvalue[2:][:28]
            tempvalue = "".join(list(map(lambda i: chr(int(content[2 * i:][:2], 0x10)), range(14)))).strip()
            self._receivedvalue = re.sub(r'^[^A-Z0-9]*', '', tempvalue)
            self.logger.debug("Converting Values {}: Display Output Pioneer {}".format(self._name, self._receivedvalue))
            returnvalue = ['display', self._receivedvalue]
        except Exception as err:
            self.logger.log(VERBOSE1, "Converting Values {}: No display info for Pioneer found. Message: {}".format(
                self._name, err))
            try:
                infotype = self._receivedvalue[3:4]
                if infotype.isdigit():
                    infotype = int(infotype)
                    self._receivedvalue = self._receivedvalue[4:] if infotype == 0 else \
                        self._receivedvalue[5:] if infotype == 1 else self._receivedvalue[6:]
                    returnvalue = ['nowplaying', self._receivedvalue] if infotype == 1 and self._receivedvalue \
                        else ['station', self._receivedvalue] if infotype == 2 and self._receivedvalue \
                        else ['display', self._receivedvalue]
                    self.logger.log(VERBOSE1, "Converting Values {}: Displayinfo: {}".format(self._name, returnvalue))
            except Exception as err:
                self.logger.debug(
                    "Converting Values {}: Unknown display info for Denon received. Message: {}".format(
                        self._name, err))
        return returnvalue

    # Converting received values to bool, string or int to compare the responses with the expected response
    def convert_value(self):
        self._receivedvalue = self._convertdisplay() \
            if self._command in self._special_commands['Display']['Command'] \
            else self._convertbool() if 'bool' in self._expectedtype \
            else self._receivedvalue
        cond1 = 'bool' in self._expectedtype and 'int' in self._expectedtype
        cond2 = 'str' in self._expectedtype and 'bool' in self._expectedtype
        if 'int' in self._expectedtype:
            try:
                cond1 = str(self._receivedvalue).lower() == 'on' and \
                    ('bool' in self._expectedtype or self._valuelength == 1)
                cond2 = ('bool' in self._expectedtype or self._valuelength == 1) \
                    and (str(self._receivedvalue).lower() == 'off' or str(self._receivedvalue).lower() == 'standby')
                self._receivedvalue = 1 if cond1 else 0 if cond2 else self._receivedvalue
            except Exception:
                pass
            try:
                self._receivedvalue = int(self._receivedvalue)
            except Exception:
                pass
        elif not (cond1 or cond2):
            try:
                cond1 = str(self._receivedvalue).lower() == 'on' and (self._valuelength == 100 or self._valuelength == 2)
                cond2 = str(self._receivedvalue).lower() == 'open' and (self._valuelength == 100 or self._valuelength == 4)
                cond3 = str(self._receivedvalue).lower() == 'off' and (self._valuelength == 100 or self._valuelength == 3)
                cond4 = str(self._receivedvalue).lower() == 'standby' and (self._valuelength == 100 or self._valuelength == 7)
                cond5 = str(self._receivedvalue).lower() == 'close' and (self._valuelength == 100 or self._valuelength == 5)
                cond6 = str(self._receivedvalue).lower() == 'clos' and (self._valuelength == 100 or self._valuelength == 4)
                self._receivedvalue = True if cond1 or cond2 \
                    else False if cond3 or cond4 or cond5 or cond6 \
                    else self._receivedvalue
            except Exception:
                pass
        try:
            self._receivedvalue = eval(self._receivedvalue.lstrip('0'))
        except Exception:
            try:
                self._receivedvalue = eval(self._receivedvalue)
            except Exception:
                pass
        if not self._expectedtype == 'str':
            try:
                self._receivedvalue = float(self._receivedvalue) if '.' in self._receivedvalue \
                    else int(self._receivedvalue)
            except Exception:
                pass
        self.logger.debug("Converting Values {}: Received Value is now: {} with type {}.".format(
            self._name, self._receivedvalue, type(self._receivedvalue)))
        return self._receivedvalue


class CreateResponse(object):
    def __init__(self, commandinfo, reverseinfo, value, name, specialparse, logger):
        self._commandinfo = commandinfo
        self._reverseinfo = reverseinfo
        self._value = value
        self._name = name
        self._specialparse = specialparse

        try:
            self._splitresponse = self._commandinfo[4].split('|')
        except Exception:
            self._splitresponse = self._commandinfo.split('|')
        try:
            self._splitreverse = self._reverseinfo[4].split('|')
        except Exception:
            self._splitreverse = self._reverseinfo.split('|')

        self.logger = logger
        self.logger.log(VERBOSE1,
                        "Creating Response {}: Create response command {}, reverse {}, value {}".format(
                            self._name, commandinfo, reverseinfo, value))

    def _finalize(self, responselist, reverselist, func_type):
        replacedresponse = "|".join(responselist)
        replacedreverse = "|".join(reverselist)
        self.logger.log(VERBOSE2,
                        "Updating Item {}: Replaced response: {}, replaced reverse: {}. Type: {}".format(
                            self._name, replacedresponse, replacedreverse, func_type))
        return replacedresponse, replacedreverse

    def replace_string(self, command, value, dictentry=None):
        value = value.upper()
        try:
            value = self._specialparse[dictentry]['update'].get(value) or value
        except Exception:
            pass
        try:
            replaced = command.replace('*', '{}'.format(value), 1)
            replaced = replaced.replace('*', '')
        except Exception:
            replaced = command
        self.logger.log(VERBOSE2,
                        "Updating Item {}: Replaced string for command {} with dictentry {}: original value: {}. replaced value: {}".format(
                            self._name, command, dictentry, value, replaced))
        return replaced

    def replace_number(self, command, value, dictentry=None):
        try:
            value = self._specialparse[dictentry]['parse'].get(str(value)) or value
        except Exception:
            pass
        try:
            value = max(min(value, int(self._commandinfo[8])), int(self._commandinfo[7]))
        except Exception:
            try:
                value = min(value, int(self._commandinfo[8]))
            except Exception:
                pass
        value = max(min(value, int(re.sub('[^0-9]', '', re.sub('\*', '9', self._commandinfo[2])))), 0) \
            if self._commandinfo[2].count('*') > 1 else \
            max(min(value, 9), 0) if command.count('*') == 1 \
            else value
        try:
            value = str(self._specialparse[dictentry]['update'].get(value) or value)[:command.count('*')]
        except Exception:
            pass
        replaced = re.sub(r'(\*)\1+', '{0:0{1}d}'.format(int(value), command.count('*')), command) \
            if command.count('*') > 1 \
            else command.replace('*', '{0:01d}'.format(int(value))) \
            if command.count('*') == 1 \
            else command
        self.logger.log(VERBOSE2,
                        "Updating Item {}: 2: Replaced number for command {} with dictentry {}: original value: {}. replaced value: {}".format(
                            self._name, command, dictentry, value, replaced))
        return replaced

    def response_power(self):
        responselist = []
        for splitre in self._splitresponse:
            valuelength = splitre.count('*')
            if valuelength > 0 or 'R' in self._commandinfo[5]:
                responselist = []
                if self._commandinfo[6].lower() in ['1', 'true', 'yes', 'on']:
                    replacedvalue = '0'
                else:
                    replacedvalue = '1'
                replacedresponse = splitre.replace('*', replacedvalue)
            else:
                replacedresponse = splitre

            responselist.append('{},{},{}'.format(replacedresponse, self._commandinfo[9], valuelength))

        return self._finalize(responselist, [], 'power')

    def response_standard(self):
        responselist = []
        for splitre in self._splitresponse:
            valuelength = splitre.count('*')
            if valuelength > 0 or 'R' in self._commandinfo[5]:
                responselist = []
                replacedresponse = splitre.split('*')[0].strip()
                if splitre.count('?') == 1:
                    replacedresponse = re.sub('[?]', '', replacedresponse)
            else:
                replacedresponse = splitre

            responselist.append('{},{},{}'.format(replacedresponse, self._commandinfo[9], valuelength))

        return self._finalize(responselist, [], 'standard')

    def response_in_decrease(self):
        responselist = []
        reverselist = []
        for counting, splitre in enumerate(self._splitresponse):
            valuelength = reverselength = splitre.count('*')
            if valuelength > 0 or 'R' in self._commandinfo[5]:
                responselist = []
                reverselist = []
                replacedresponse = re.sub('[*]', '', splitre.strip())
                if splitre.count('?') == 1:
                    replacedresponse = re.sub('[?]', '', replacedresponse)
                try:
                    reverselength = self._splitreverse[counting].count('*')
                    replacedreverse = re.sub('[*]', '', self._splitreverse[counting].strip())
                    if self._splitreverse[counting].count('?') == 1:
                        replacedreverse = re.sub('[?]', '', replacedreverse)
                except Exception:
                    replacedreverse = ''
            else:
                replacedresponse = splitre
                try:
                    replacedreverse = self._splitreverse[counting]
                    reverselength = self._splitreverse[counting].count('*')
                except Exception:
                    replacedreverse = ''

            if not replacedresponse == '':
                responselist.append('{},{},{}'.format(replacedresponse, self._commandinfo[9], valuelength))
            if not replacedreverse == '':
                reverselist.append('{},{},{}'.format(replacedreverse, self._commandinfo[9], reverselength))
        return self._finalize(responselist, reverselist, 'in_decrease')

    def response_off(self):
        responselist = []
        reverselist = []
        for counting, splitre in enumerate(self._splitresponse):
            valuelength = reverselength = splitre.count('*')
            if valuelength > 0 or 'R' in self._commandinfo[5]:
                responselist = []
                reverselist = []
                replacedreverse = ''
                replacedresponse = splitre.replace('*******', 'STANDBY')
                replacedresponse = replacedresponse.replace('*****', 'CLOSE')
                replacedresponse = replacedresponse.replace('****', 'CLOS')
                replacedresponse = replacedresponse.replace('***', 'OFF')
                if self._commandinfo[6].lower() in ['1', 'true', 'yes', 'on']:
                    replacedvalue = '1'
                    reversevalue = '0'
                else:
                    replacedvalue = '0'
                    reversevalue = '1'
                try:
                    reverselength = self._splitreverse[counting].count('*')
                    replacedreverse = self._splitreverse[counting].replace('****', 'OPEN')
                    replacedreverse = replacedreverse.replace('**', 'ON')
                except Exception as err:
                    self.logger.log(VERBOSE2,
                                    "Updating Item {}: Problems replacing * for off reverse command: {}".format(
                                        self._name, err))

                replacedresponse = replacedresponse.replace('*', replacedvalue)
                replacedreverse = replacedreverse.replace('*', reversevalue)
            else:
                replacedresponse = splitre
                try:
                    replacedreverse = self._splitreverse[counting]
                    reverselength = self._splitreverse[counting].count('*')
                except Exception:
                    replacedreverse = ''

            if not replacedresponse == '':
                responselist.append('{},{},{}'.format(replacedresponse, self._commandinfo[9], valuelength))
            if not replacedreverse == '':
                reverselist.append('{},{},{}'.format(replacedreverse, self._commandinfo[9], reverselength))

        return self._finalize(responselist, reverselist, 'off')

    def response_set(self):
        responselist = []
        for splitre in self._splitresponse:
            valuelength = splitre.count('*')
            if valuelength > 0 or 'R' in self._commandinfo[5]:
                replacedresponse = ''
                try:
                    value = Translate(self._value, self._commandinfo[10], self._name,
                                      'update', self._specialparse, self.logger).translate() or self._value
                except Exception:
                    value = self._value
                try:
                    value = eval(value.lstrip('0'))
                except Exception:
                    pass
                self.logger.log(VERBOSE2, "Setting Response {}: Final value: {}".format(self._name, value))
                try:
                    translatecode = self._commandinfo[10]
                except Exception:
                    translatecode = None
                cond2 = isinstance(value, int) and 'int' in self._commandinfo[9]
                cond3 = isinstance(value, float) and 'float' in self._commandinfo[9]
                if value == 0 and 'bool' in self._commandinfo[9]:
                    value = 'OFF'
                    try:
                        replacedresponse = re.sub('\*+', '{}'.format(value), splitre)
                    except Exception:
                        replacedresponse = splitre
                elif cond2 or cond3:
                    replacedresponse = self.replace_number(splitre, value, translatecode)
                elif isinstance(value, str) and 'str' in self._commandinfo[9]:
                    replacedresponse = self.replace_string(splitre, value, translatecode)
                else:
                    self.logger.log(VERBOSE2,
                                    "Setting Response {}: There might be something wrong with replacing the response.".format(
                                        self._name))
            else:
                replacedresponse = splitre

            if not replacedresponse == '':
                responselist.append('{},{},{}'.format(replacedresponse, self._commandinfo[9], valuelength))
        self.logger.log(VERBOSE2, "Setting Response {}: Responselist: {}".format(self._name, responselist))
        return self._finalize(responselist, [], 'set')

    def response_on(self):
        responselist = []
        reverselist = []
        for counting, splitre in enumerate(self._splitresponse):
            valuelength = reverselength = splitre.count('*')
            if valuelength > 0 or 'R' in self._commandinfo[5]:
                replacedresponse = replacedreverse = replacedvalue = reversevalue = ''
                try:
                    replacedresponse = splitre.replace('****', 'OPEN')
                    replacedresponse = replacedresponse.replace('**', 'ON')
                    if self._commandinfo[6].lower() in ['1', 'true', 'yes', 'on']:
                        replacedvalue = '0'
                        reversevalue = '1'
                    else:
                        replacedvalue = '1'
                        reversevalue = '0'
                except Exception as err:
                    self.logger.debug(
                        "Updating Item {}: Problems replacing * for on command: {}".format(self._name, err))
                try:
                    reverselength = self._splitreverse[counting].count('*')
                    replacedreverse = self._splitreverse[counting].replace('*****', 'CLOSE')
                    replacedreverse = replacedreverse.replace('****', 'CLOS')
                    replacedreverse = replacedreverse.replace('***', 'OFF')
                except Exception as err:
                    self.logger.log(VERBOSE2,
                                    "Updating Item {}: Problems replacing * for on reverse command: {}".format(
                                        self._name, err))
                replacedresponse = replacedresponse.replace('*', replacedvalue)
                replacedreverse = replacedreverse.replace('*', reversevalue)
                self.logger.log(VERBOSE2,
                                "Updating Item {}: Replaced on response: {} Replaced on reverse: {}".format(
                                    self._name, replacedresponse, replacedreverse))
            else:
                replacedresponse = splitre
                try:
                    replacedreverse = self._splitreverse[counting]
                    reverselength = self._splitreverse[counting].count('*')
                except Exception:
                    replacedreverse = ''

            if not replacedresponse == '':
                responselist.append('{},{},{}'.format(replacedresponse, self._commandinfo[9], valuelength))
            if not replacedreverse == '':
                reverselist.append('{},{},{}'.format(replacedreverse, self._commandinfo[9], reverselength))
        self.logger.log(VERBOSE2, "Updating Item {}: Replaced on responselist: {} Replaced on reverselist: {}".format(
            self._name, responselist, reverselist))
        return self._finalize(responselist, reverselist, 'on')
