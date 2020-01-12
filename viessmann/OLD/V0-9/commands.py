#!/usr/bin/env python
#########################################################################
# Copyright 2013 Stefan Kals
#########################################################################
#  Viessmann-Plugin for SmartHomeNG.  https://github.com/smarthomeNG//
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

controlset = {
    'P300': {
        'StartByte': 0x41,
        'Request': 0x00,
        'Response': 0x01,
        'Error': 0x03,
        'Read': 0x01,
        'Write': 0x02,
        'Function_Call': 0x7,
        'Acknowledge': 0x06,
        'Not_initiated': 0x05,
        'Init_Error': 0x15,
        'Reset_Command': 0x04,
        'Reset_Command_Response': 0x05,
        'Sync_Command': 0x160000,
        'Sync_Command_Response': 0x06,
        'Command_bytes_read': 0x05,
        'Command_bytes_write': 0x06,
        'Command_length': 9,
        'Checksum_length': 1,
        #init:              send'Reset_Command' receive'Reset_Command_Response' send'Sync_Command'
        #request:           send('StartByte' 'Länge der Nutzdaten als Anzahl der Bytes zwischen diesem Byte und der Prüfsumme' 'Request' 'Read' 'addr' 'checksum')
        #request_response:  receive('Acknowledge' 'StartByte' 'Länge der Nutzdaten als Anzahl der Bytes zwischen diesem Byte und der Prüfsumme' 'Response' 'Read' 'addr' 'Anzahl der Bytes des Wertes' 'Wert' 'checksum')
    },
}
    
# command properties:
    # addr:             Datenpunkt in der Regelung
    # len:              Anzahl der Bytes, die in der Antwort erwartet werden bzw. beinhaltet sind
    # type:             read oder write
    # result:           float, int, bool
    # valuetransform:   Umrechnungsfaktor
    # min_value:        kleiner Wert, der geschrieben werden kann
    # max_value:        groesster Wert, der geschrieben werden kann
    # signage:          Vorzeichenhandling
    
commandset = {
    'V200KO1B': {
        'getTempA':                     { 'addr': '0800', 'len': 2, 'type': 'read', 'result': 'float', 'signage': 'signed', 'valuetransform': 'div10' }, #Ermittle die Aussentemperatur in Grad C
        'getTempRaumNorSollM2':         { 'addr': '3306', 'len': 1, 'type': 'read', 'result': 'int', 'signage': 'signed', 'valuetransform': 'non' }, #Ermittle die Raumsolltemperatur normal M2 in Grad C
        'getNiveauM2':                  { 'addr': '37d4', 'len': 1, 'type': 'read', 'result': 'int', 'signage': 'signed', 'valuetransform': 'non' }, #Ermittle Niveau Heizkennlinie M2
        'getTempWWsoll':                { 'addr': '6300', 'len': 1, 'type': 'read', 'result': 'int', 'signage': 'signed', 'valuetransform': 'non' }, #Ermittle die Warmwassersolltemperatur in Grad C
        'getBrennerStarts':             { 'addr': '088a', 'len': 4, 'type': 'read', 'result': 'int', 'signage': 'unsigned', 'valuetransform': 'non' }, #Ermittle die Brennerstarts
        'getBrennerStunden1':           { 'addr': '08a7', 'len': 4, 'type': 'read', 'result': 'float', 'signage': 'unsigned', 'valuetransform': 'div3600' }, #Brennerstunden in Stufe 1
        'getPumpeStatusM2':             { 'addr': '3906', 'len': 1, 'type': 'read', 'result': 'bool', 'signage': 'unsigned', 'valuetransform': 'non' }, #Brennerstunden in Stufe 1
        'setTempRaumNorSollM2':         { 'addr': '3306', 'len': 1, 'type': 'write', 'valuetransform': 'non', 'min_value': 3, 'max_value': 37 }, #Setze die Raumsolltemperatur normal M2 in Grad C
        'setNiveauM2':                  { 'addr': '37d4', 'len': 1, 'type': 'write', 'valuetransform': 'non', 'min_value': -13, 'max_value': 40 }, #Setze Niveau Heizkennlinie M2
        'setTempWWsoll':                { 'addr': '6300', 'len': 1, 'type': 'write', 'valuetransform': 'non', 'min_value': 10, 'max_value': 95 }, #Setze die Warmwassersolltemperatur in Grad C
    },
}