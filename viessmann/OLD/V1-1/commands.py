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
        'getAussentemperatur': { 'addr': '0800', 'len': 2, 'type': 'read', 'result': 'float', 'signage': 'signed', 'valuetransform': 'div10' }, #Aussentemperatur
        'getKesseltemperatur': { 'addr': '0810', 'len': 2, 'type': 'read', 'result': 'float', 'signage': 'unsigned', 'valuetransform': 'div10' }, #Kesseltemperatur
        'getVorlauftemperatur_A1M1': { 'addr': '0810', 'len': 2, 'type': 'read', 'result': 'float', 'signage': 'unsigned', 'valuetransform': 'div10' }, #Vorlauftemperatur A1M1
        'getTemperatur_Speicher_Ladesensor': { 'addr': '0812', 'len': 2, 'type': 'read', 'result': 'float', 'signage': 'unsigned', 'valuetransform': 'div10' }, #Temperatur Speicher Ladesensor Komfortsensor
        'getAuslauftemperatur': { 'addr': '0814', 'len': 2, 'type': 'read', 'result': 'float', 'signage': 'unsigned', 'valuetransform': 'div10' }, #Auslauftemperatur
        'getAbgastemperatur': { 'addr': '0816', 'len': 2, 'type': 'read', 'result': 'float', 'signage': 'unsigned', 'valuetransform': 'div10' }, #Abgastemperatur
        'getGem._Vorlauftemperatur': { 'addr': '081a', 'len': 2, 'type': 'read', 'result': 'float', 'signage': 'unsigned', 'valuetransform': 'div10' }, #Gem. Vorlauftemperatur
        'getRelais_K12_Interne Anschlußerweiterung': { 'addr': '0842', 'len': 1, 'type': 'read', 'result': 'bool', 'signage': 'unsigned', 'valuetransform': 'non' }, #Relais K12 Interne Anschlußerweiterung
        'getBrennerstarts': { 'addr': '088a', 'len': 4, 'type': 'read', 'result': 'int', 'signage': 'unsigned', 'valuetransform': 'non' }, #Brennerstarts
        'getRaumtemperatur_A1M1': { 'addr': '0896', 'len': 1, 'type': 'read', 'result': 'float', 'signage': 'unsigned', 'valuetransform': 'div10' }, #Raumtemperatur A1M1
        'getRaumtemperatur_M2': { 'addr': '0898', 'len': 1, 'type': 'read', 'result': 'float', 'signage': 'unsigned', 'valuetransform': 'div10' }, #Raumtemperatur M2
        'getBrenner-Betriebsstunden': { 'addr': '08a7', 'len': 4, 'type': 'read', 'result': 'float', 'signage': 'unsigned', 'valuetransform': 'div3600' }, #Brenner-Betriebsstunden
        'getSammelstörung': { 'addr': '0a82', 'len': 1, 'type': 'read', 'result': 'bool', 'signage': 'unsigned', 'valuetransform': 'non' }, #Sammelstörung
        'getEingang_0-10_V': { 'addr': '0a86', 'len': 1, 'type': 'read', 'result': 'float', 'signage': 'unsigned', 'valuetransform': 'non' }, #Eingang 0-10 V
        'getEA1_Kontakt_0': { 'addr': '0a90', 'len': 1, 'type': 'read', 'result': 'bool', 'signage': 'unsigned', 'valuetransform': 'non' }, #EA1: Kontakt 0
        'getEA1_Kontakt_1': { 'addr': '0a91', 'len': 1, 'type': 'read', 'result': 'bool', 'signage': 'unsigned', 'valuetransform': 'non' }, #EA1: Kontakt 1
        'getEA1_Kontakt_2': { 'addr': '0a92', 'len': 1, 'type': 'read', 'result': 'bool', 'signage': 'unsigned', 'valuetransform': 'non' }, #EA1: Kontakt 2
        'getEA1_Externer_Sollwert_0-10V': { 'addr': '0a93', 'len': 1, 'type': 'read', 'result': 'float', 'signage': 'unsigned', 'valuetransform': 'non' }, #EA1: Externer Sollwert 0-10V
        'getEA1_Relais_0': { 'addr': '0a95', 'len': 1, 'type': 'read', 'result': 'bool', 'signage': 'unsigned', 'valuetransform': 'non' }, #EA1: Relais 0
        'getAM1_Ausgang_1': { 'addr': '0aa0', 'len': 1, 'type': 'read', 'result': 'bool', 'signage': 'unsigned', 'valuetransform': 'non' }, #AM1 Ausgang 1
        'getAM1_Ausgang_2': { 'addr': '0aa1', 'len': 1, 'type': 'read', 'result': 'bool', 'signage': 'unsigned', 'valuetransform': 'non' }, #AM1 Ausgang 2
        'getSparbetrieb_A1M1': { 'addr': '2302', 'len': 1, 'type': 'read', 'result': 'bool', 'signage': 'unsigned', 'valuetransform': 'non' }, #Sparbetrieb A1M1
        'getPartybetrieb_A1M1': { 'addr': '2303', 'len': 1, 'type': 'read', 'result': 'bool', 'signage': 'unsigned', 'valuetransform': 'non' }, #Partybetrieb A1M1
        'getRaumtemperatur_Soll_Normalbetrieb_A1M1': { 'addr': '2306', 'len': 1, 'type': 'read', 'result': 'float', 'signage': 'unsigned', 'valuetransform': 'non' }, #Raumtemperatur Soll Normalbetrieb A1M1
        'getRaumtemperatur_Soll_Reduzierter_Betrieb_A1M': { 'addr': '2307', 'len': 1, 'type': 'read', 'result': 'float', 'signage': 'unsigned', 'valuetransform': 'non' }, #Raumtemperatur Soll Reduzierter Betrieb A1M
        'getRaumtemperatur_Soll_Party_Betrieb_A1M1': { 'addr': '2308', 'len': 1, 'type': 'read', 'result': '', 'signage': '', 'valuetransform': 'non' }, #Raumtemperatur Soll Party Betrieb A1M1
        'getExterne_Raumsolltemperatur_Normal_A1M1': { 'addr': '2321', 'len': 1, 'type': 'read', 'result': 'float', 'signage': 'unsigned', 'valuetransform': 'div10' }, #Externe Raumsolltemperatur Normal A1M1
        'getBetriebsart_A1M1': { 'addr': '2323', 'len': 1, 'type': 'read', 'result': 'byte', 'signage': 'unsigned', 'valuetransform': 'non' }, #Betriebsart A1M1
        'getZustand_Partybetrieb_A1M1': { 'addr': '2330', 'len': 1, 'type': 'read', 'result': 'bool', 'signage': 'unsigned', 'valuetransform': 'non' }, #Zustand Partybetrieb A1M1
        'getZustand_Sparbetrieb_A1M1': { 'addr': '2331', 'len': 1, 'type': 'read', 'result': 'bool', 'signage': 'unsigned', 'valuetransform': 'non' }, #Zustand Sparbetrieb A1M1
        'getAktuelle_Betriebsart_A1M1': { 'addr': '2500', 'len': 1, 'type': 'read', 'result': 'byte', 'signage': 'unsigned', 'valuetransform': 'non' }, #Aktuelle Betriebsart A1M1
        'getVorlauftemperatur_Soll_A1M1': { 'addr': '2544', 'len': 2, 'type': 'read', 'result': 'float', 'signage': 'unsigned', 'valuetransform': 'div10' }, #Vorlauftemperatur Soll A1M1
        'getNeigung_Heizkennlinie_A1': { 'addr': '27d3', 'len': 1, 'type': 'read', 'result': 'byte', 'signage': 'unsigned', 'valuetransform': 'div10' }, #Neigung Heizkennlinie A1
        'getNiveau_Heizkennlinie_A1': { 'addr': '27d4', 'len': 1, 'type': 'read', 'result': 'int', 'signage': 'signed', 'valuetransform': 'non' }, #Niveau Heizkennlinie A1
        'getHeizkreispumpe_A1M1': { 'addr': '2906', 'len': 1, 'type': 'read', 'result': 'bool', 'signage': 'unsigned', 'valuetransform': 'non' }, #Heizkreispumpe A1M1
        'getSparbetrieb_M2': { 'addr': '3302', 'len': 1, 'type': 'read', 'result': 'bool', 'signage': 'unsigned', 'valuetransform': 'non' }, #Sparbetrieb M2
        'getPartybetrieb_M2': { 'addr': '3303', 'len': 1, 'type': 'read', 'result': 'bool', 'signage': 'unsigned', 'valuetransform': 'non' }, #Partybetrieb M2
        'getRaumtemperatur_Soll_Normalbetrieb_M2': { 'addr': '3306', 'len': 1, 'type': 'read', 'result': 'float', 'signage': 'unsigned', 'valuetransform': 'non' }, #Raumtemperatur Soll Normalbetrieb M2
        'getRaumtemperatur_Soll_Reduzierter_Betrieb_M2': { 'addr': '3307', 'len': 1, 'type': 'read', 'result': 'float', 'signage': 'unsigned', 'valuetransform': 'non' }, #Raumtemperatur Soll Reduzierter Betrieb M2
        'getRaumtemperatur_Soll_Party_Betrieb_M2': { 'addr': '3308', 'len': 1, 'type': 'read', 'result': 'float', 'signage': 'unsigned', 'valuetransform': 'non' }, #Raumtemperatur Soll Party Betrieb M2
        'getFerien_Abreisetag_M2': { 'addr': '3309', 'len': 4, 'type': 'read', 'result': 'byte', 'signage': 'unsigned', 'valuetransform': 'non' }, #Ferien Abreisetag M2
        'getFerien_Rückreisetag_M2': { 'addr': '3311', 'len': 4, 'type': 'read', 'result': 'byte', 'signage': 'unsigned', 'valuetransform': 'non' }, #Ferien Rückreisetag M2
        'getExterne_Raumsolltemperatur_Normal_M2': { 'addr': '3321', 'len': 1, 'type': 'read', 'result': 'float', 'signage': 'unsigned', 'valuetransform': 'div10' }, #Externe Raumsolltemperatur Normal M2
        'getBetriebsart_M2': { 'addr': '3323', 'len': 1, 'type': 'read', 'result': 'byte', 'signage': 'unsigned', 'valuetransform': 'non' }, #Betriebsart M2
        'getZustand_Partybetrieb_M2': { 'addr': '3330', 'len': 1, 'type': 'read', 'result': 'bool', 'signage': 'unsigned', 'valuetransform': 'non' }, #Zustand Partybetrieb M2
        'getZustand_Sparbetrieb_M2': { 'addr': '3331', 'len': 1, 'type': 'read', 'result': 'bool', 'signage': 'unsigned', 'valuetransform': 'non' }, #Zustand Sparbetrieb M2
        'getAktuelle_Betriebsart_M2': { 'addr': '3500', 'len': 1, 'type': 'read', 'result': 'byte', 'signage': 'unsigned', 'valuetransform': 'non' }, #Aktuelle Betriebsart M2
        'getFerienprogramm_M2': { 'addr': '3535', 'len': 1, 'type': 'read', 'result': 'byte', 'signage': 'unsigned', 'valuetransform': 'non' }, #Ferienprogramm M2
        'getVorlauftemperatur_Soll_M2': { 'addr': '3544', 'len': 2, 'type': 'read', 'result': 'float', 'signage': 'unsigned', 'valuetransform': 'div10' }, #Vorlauftemperatur Soll M2
        'getExterne_Betriebsartenumschaltung_M2': { 'addr': '3549', 'len': 1, 'type': 'read', 'result': '', 'signage': '', 'valuetransform': 'non' }, #Externe Betriebsartenumschaltung M2
        'getNeigung_Heizkennlinie_M2': { 'addr': '37d3', 'len': 1, 'type': 'read', 'result': 'byte', 'signage': 'unsigned', 'valuetransform': 'div10' }, #Neigung Heizkennlinie M2
        'getNiveau_Heizkennlinie_M2': { 'addr': '37d4', 'len': 1, 'type': 'read', 'result': 'int', 'signage': 'signed', 'valuetransform': 'non' }, #Niveau Heizkennlinie M2
        'getVorlauftemperatur_M2': { 'addr': '3900', 'len': 1, 'type': 'read', 'result': 'float', 'signage': 'unsigned', 'valuetransform': 'div10' }, #Vorlauftemperatur M2
        'getHeizkreispumpe_M2': { 'addr': '3906', 'len': 1, 'type': 'read', 'result': 'bool', 'signage': 'unsigned', 'valuetransform': 'non' }, #Heizkreispumpe M2
        'getAussentemperatur_TP': { 'addr': '5525', 'len': 2, 'type': 'read', 'result': 'float', 'signage': 'signed', 'valuetransform': 'div10' }, #Aussentemperatur_tiefpass
        'getKesselsolltemperatur': { 'addr': '555a', 'len': 1, 'type': 'read', 'result': 'float', 'signage': 'unsigned', 'valuetransform': 'div10' }, #Kesselsolltemperatur
        'getWarmwasser-Solltemperatur': { 'addr': '6300', 'len': 1, 'type': 'read', 'result': 'float', 'signage': 'unsigned', 'valuetransform': 'non' }, #Warmwasser-Solltemperatur
        'getSatus_Warmwasserbereitung': { 'addr': '650a', 'len': 1, 'type': 'read', 'result': 'bool', 'signage': 'unsigned', 'valuetransform': 'non' }, #Satus Warmwasserbereitung
        'getSpeicherladepumpe': { 'addr': '6513', 'len': 1, 'type': 'read', 'result': 'bool', 'signage': 'unsigned', 'valuetransform': 'non' }, #Speicherladepumpe
        'getZirkulationspumpe': { 'addr': '6515', 'len': 1, 'type': 'read', 'result': 'bool', 'signage': 'unsigned', 'valuetransform': 'non' }, #Zirkulationspumpe
        'getInterne_Pumpe': { 'addr': '7660', 'len': 1, 'type': 'read', 'result': 'bool', 'signage': 'unsigned', 'valuetransform': 'non' }, #Interne Pumpe
        'getHeizkreispumpe_A1': { 'addr': '7663', 'len': 1, 'type': 'read', 'result': 'bool', 'signage': 'unsigned', 'valuetransform': 'non' }, #Heizkreispumpe A1
        'getHeizkreispumpe_A1M1_Drehzahl': { 'addr': '7663', 'len': 1, 'type': 'read', 'result': 'int', 'signage': 'unsigned', 'valuetransform': 'non' }, #Heizkreispumpe A1M1 Drehzahl
        'getHeizkreispumpe_Drehzahl': { 'addr': '7665', 'len': 1, 'type': 'read', 'result': 'int', 'signage': 'unsigned', 'valuetransform': 'non' }, #Heizkreispumpe Drehzahl
        'getRelais-Status_Heizkreispumpe_1': { 'addr': 'a152', 'len': 1, 'type': 'read', 'result': 'bool', 'signage': 'unsigned', 'valuetransform': 'non' }, #Relais-Status Heizkreispumpe 1
        'setBrennerstarts': { 'addr': '088a', 'len': 4, 'type': 'write', 'valuetransform': 'non', 'min_value': 0, 'max_value': 1193045 }, #Brennerstarts
        'setBrenner-Betriebsstunden': { 'addr': '08a7', 'len': 4, 'type': 'write', 'valuetransform': 'div3600', 'min_value': , 'max_value':  }, #Brenner-Betriebsstunden
        'setSparbetrieb_A1M1': { 'addr': '2302', 'len': 1, 'type': 'write', 'valuetransform': 'non', 'min_value': 0, 'max_value': 1 }, #Sparbetrieb A1M1
        'setRaumtemperatur_Soll_Normalbetrieb_A1M1': { 'addr': '2306', 'len': 1, 'type': 'write', 'valuetransform': 'non', 'min_value': 3, 'max_value': 37 }, #Raumtemperatur Soll Normalbetrieb A1M1
        'setRaumtemperatur_Soll_Reduzierter_Betrieb_A1M': { 'addr': '2307', 'len': 1, 'type': 'write', 'valuetransform': 'non', 'min_value': 3, 'max_value': 37 }, #Raumtemperatur Soll Reduzierter Betrieb A1M
        'setRaumtemperatur_Soll_Party_Betrieb_A1M1': { 'addr': '2308', 'len': 1, 'type': 'write', 'valuetransform': 'non', 'min_value': 3, 'max_value': 37 }, #Raumtemperatur Soll Party Betrieb A1M1
        'setExterne_Raumsolltemperatur_Normal_A1M1': { 'addr': '2321', 'len': 1, 'type': 'write', 'valuetransform': 'div10', 'min_value': 0, 'max_value': 37 }, #Externe Raumsolltemperatur Normal A1M1
        'setBetriebsart_A1M1': { 'addr': '2323', 'len': 1, 'type': 'write', 'valuetransform': 'non', 'min_value': 0, 'max_value': 4 }, #Betriebsart A1M1
        'setZustand_Partybetrieb_A1M1': { 'addr': '2330', 'len': 1, 'type': 'write', 'valuetransform': 'non', 'min_value': 0, 'max_value': 1 }, #Zustand Partybetrieb A1M1
        'setZustand_Sparbetrieb_A1M1': { 'addr': '2331', 'len': 1, 'type': 'write', 'valuetransform': 'non', 'min_value': 0, 'max_value': 1 }, #Zustand Sparbetrieb A1M1
        'setNeigung_Heizkennlinie_A1': { 'addr': '27d3', 'len': 1, 'type': 'write', 'valuetransform': 'div10', 'min_value': 0,2, 'max_value': 3,5 }, #Neigung Heizkennlinie A1
        'setNiveau_Heizkennlinie_A1': { 'addr': '27d4', 'len': 1, 'type': 'write', 'valuetransform': 'non', 'min_value': -13, 'max_value': 40 }, #Niveau Heizkennlinie A1
        'setSparbetrieb_M2': { 'addr': '3302', 'len': 1, 'type': 'write', 'valuetransform': 'non', 'min_value': 0, 'max_value': 1 }, #Sparbetrieb M2
        'setRaumtemperatur_Soll_Normalbetrieb_M2': { 'addr': '3306', 'len': 1, 'type': 'write', 'valuetransform': 'non', 'min_value': 3, 'max_value': 37 }, #Raumtemperatur Soll Normalbetrieb M2
        'setRaumtemperatur_Soll_Reduzierter_Betrieb_M2': { 'addr': '3307', 'len': 1, 'type': 'write', 'valuetransform': 'non', 'min_value': 3, 'max_value': 37 }, #Raumtemperatur Soll Reduzierter Betrieb M2
        'setRaumtemperatur_Soll_Party_Betrieb_M2': { 'addr': '3308', 'len': 1, 'type': 'write', 'valuetransform': 'non', 'min_value': 3, 'max_value': 37 }, #Raumtemperatur Soll Party Betrieb M2
        'setFerien_Abreisetag_M2': { 'addr': '3309', 'len': 4, 'type': 'write', 'valuetransform': 'non', 'min_value': , 'max_value':  }, #Ferien Abreisetag M2
        'setFerien_Rückreisetag_M2': { 'addr': '3311', 'len': 4, 'type': 'write', 'valuetransform': 'non', 'min_value': , 'max_value':  }, #Ferien Rückreisetag M2
        'setExterne_Raumsolltemperatur_Normal_M2': { 'addr': '3321', 'len': 1, 'type': 'write', 'valuetransform': 'div10', 'min_value': 0, 'max_value': 37 }, #Externe Raumsolltemperatur Normal M2
        'setBetriebsart_M2': { 'addr': '3323', 'len': 1, 'type': 'write', 'valuetransform': 'non', 'min_value': 0, 'max_value': 4 }, #Betriebsart M2
        'setZustand_Partybetrieb_M2': { 'addr': '3330', 'len': 1, 'type': 'write', 'valuetransform': 'non', 'min_value': 0, 'max_value': 1 }, #Zustand Partybetrieb M2
        'setZustand_Sparbetrieb_M2': { 'addr': '3331', 'len': 1, 'type': 'write', 'valuetransform': 'non', 'min_value': 0, 'max_value': 1 }, #Zustand Sparbetrieb M2
        'setFerienprogramm_M2': { 'addr': '3535', 'len': 1, 'type': 'write', 'valuetransform': 'non', 'min_value': , 'max_value':  }, #Ferienprogramm M2
        'setExterne_Betriebsartenumschaltung_M2': { 'addr': '3549', 'len': 1, 'type': 'write', 'valuetransform': 'non', 'min_value': , 'max_value':  }, #Externe Betriebsartenumschaltung M2
        'setNeigung_Heizkennlinie_M2': { 'addr': '37d3', 'len': 1, 'type': 'write', 'valuetransform': 'div10', 'min_value': 0,2, 'max_value': 3,5 }, #Neigung Heizkennlinie M2
        'setNiveau_Heizkennlinie_M2': { 'addr': '37d4', 'len': 1, 'type': 'write', 'valuetransform': 'non', 'min_value': -13, 'max_value': 40 }, #Niveau Heizkennlinie M2
        'setWarmwasser-Solltemperatur': { 'addr': '6300', 'len': 1, 'type': 'write', 'valuetransform': 'non', 'min_value': 10, 'max_value': 95 }, #Warmwasser-Solltemperatur
        'setSatus_Warmwasserbereitung': { 'addr': '650a', 'len': 1, 'type': 'write', 'valuetransform': 'non', 'min_value': 0, 'max_value': 1 }, #Satus Warmwasserbereitung
    },
}