# !/usr/bin/env python
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# Copyright 2020 Michael Wenzel
# Copyright 2020 Sebastian Helms
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
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
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
controlset = {
    'P300': {
        'Baudrate': 4800,
        'Bytesize': 8,          # 'EIGHTBITS'
        'Parity': 'E',          # 'PARITY_EVEN',
        'Stopbits': 2,          # 'STOPBITS_TWO',
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
        'Command_bytes_read': 5,
        'Command_bytes_write': 5,
        # init:              send'Reset_Command' receive'Reset_Command_Response' send'Sync_Command'
        # request:           send('StartByte' 'Länge der Nutzdaten als Anzahl der Bytes zwischen diesem Byte und der Prüfsumme' 'Request' 'Read' 'addr' 'checksum')
        # request_response:  receive('Acknowledge' 'StartByte' 'Länge der Nutzdaten als Anzahl der Bytes zwischen diesem Byte und der Prüfsumme' 'Response' 'Read' 'addr' 'Anzahl der Bytes des Wertes' 'Wert' 'checksum')
    },
    'KW': {
        'Baudrate': 4800,
        'Bytesize': 8,          # 'EIGHTBITS'
        'Parity': 'E',          # 'PARITY_EVEN',
        'Stopbits': 2,          # 'STOPBITS_TWO',
        'StartByte': 0x01,
        'Read': 0xF7,
        'Write': 0xF4,
        'Acknowledge': 0x01,
        'Reset_Command': 0x04,
        'Not_initiated': 0x05,
        'Write_Ack': 0x00,
    },
}

commandset = {
    'V200KO1B': {
        # Kessel
        'Aussentemperatur':                           {'addr': '0800', 'len': 2, 'unit': 'IS10',    'set': False},                                          # Aussentemperatur
        'Aussentemperatur_TP':                        {'addr': '5525', 'len': 2, 'unit': 'IS10',    'set': False},                                          # Aussentemperatur_tiefpass
        'Aussentemperatur_Dp':                        {'addr': '5527', 'len': 2, 'unit': 'IS10',    'set': False},                                          # Aussentemperatur in Grad C (Gedaempft)
        'Kesseltemperatur':                           {'addr': '0802', 'len': 2, 'unit': 'IU10',    'set': False},                                          # Kesseltemperatur
        'Kesseltemperatur_TP':                        {'addr': '0810', 'len': 2, 'unit': 'IU10',    'set': False},                                          # Kesseltemperatur_tiefpass
        'Kesselsolltemperatur':                       {'addr': '555a', 'len': 2, 'unit': 'IU10',    'set': False},                                          # Kesselsolltemperatur
        'Temp_Speicher_Ladesensor':                   {'addr': '0812', 'len': 2, 'unit': 'IU10',    'set': False},                                          # Temperatur Speicher Ladesensor Komfortsensor
        'Auslauftemperatur':                          {'addr': '0814', 'len': 2, 'unit': 'IU10',    'set': False},                                          # Auslauftemperatur
        'Abgastemperatur':                            {'addr': '0816', 'len': 2, 'unit': 'IU10',    'set': False},                                          # Abgastemperatur
        'Gem_Vorlauftemperatur':                      {'addr': '081a', 'len': 2, 'unit': 'IU10',    'set': False},                                          # Gem. Vorlauftemperatur
        'Relais_K12':                                 {'addr': '0842', 'len': 1, 'unit': 'IUBOOL',  'set': False},                                          # Relais K12 Interne Anschlußerweiterung
        'Eingang_0-10_V':                             {'addr': '0a86', 'len': 1, 'unit': 'IUINT',   'set': False},                                          # Eingang 0-10 V
        'EA1_Kontakt_0':                              {'addr': '0a90', 'len': 1, 'unit': 'IUBOOL',  'set': False},                                          # EA1: Kontakt 0
        'EA1_Kontakt_1':                              {'addr': '0a91', 'len': 1, 'unit': 'IUBOOL',  'set': False},                                          # EA1: Kontakt 1
        'EA1_Kontakt_2':                              {'addr': '0a92', 'len': 1, 'unit': 'IUBOOL',  'set': False},                                          # EA1: Kontakt 2
        'EA1_Externer_Soll_0-10V':                    {'addr': '0a93', 'len': 1, 'unit': 'IUINT',   'set': False},                                          # EA1: Externer Sollwert 0-10V
        'EA1_Relais_0':                               {'addr': '0a95', 'len': 1, 'unit': 'IUBOOL',  'set': False},                                          # EA1: Relais 0
        'AM1_Ausgang_1':                              {'addr': '0aa0', 'len': 1, 'unit': 'IUBOOL',  'set': False},                                          # AM1 Ausgang 1
        'AM1_Ausgang_2':                              {'addr': '0aa1', 'len': 1, 'unit': 'IUBOOL',  'set': False},                                          # AM1 Ausgang 2
        'TempKOffset':                                {'addr': '6760', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': 0,   'max_value': 1193045},   # Kesseloffset KT ueber WWsoll in Grad C
        'Systemtime':                                 {'addr': '088e', 'len': 8, 'unit': 'TI',      'set': True},                                           # Systemzeit
        'Anlagenschema':                              {'addr': '7700', 'len': 2, 'unit': 'SC',      'set': False},                                          # Anlagenschema
        'Anlagentyp':                                 {'addr': '00f8', 'len': 2, 'unit': 'DT',      'set': False},                                          # Heizungstyp
        'Inventory':                                  {'addr': '08e0', 'len': 7, 'unit': 'SN',      'set': False},                                          # Sachnummer
        'CtrlId':                                     {'addr': '08e0', 'len': 7, 'unit': 'DT',      'set': False},                                          # Reglerkennung
        # Fehler
        'Sammelstoerung':                             {'addr': '0a82', 'len': 1, 'unit': 'RT',      'set': False},                                          # Sammelstörung
        'Error0':                                     {'addr': '7507', 'len': 9, 'unit': 'ES',      'set': False},                                          # Fehlerhistory Eintrag 1
        'Error1':                                     {'addr': '7510', 'len': 9, 'unit': 'ES',      'set': False},                                          # Fehlerhistory Eintrag 2
        'Error2':                                     {'addr': '7519', 'len': 9, 'unit': 'ES',      'set': False},                                          # Fehlerhistory Eintrag 3
        'Error3':                                     {'addr': '7522', 'len': 9, 'unit': 'ES',      'set': False},                                          # Fehlerhistory Eintrag 4
        'Error4':                                     {'addr': '752b', 'len': 9, 'unit': 'ES',      'set': False},                                          # Fehlerhistory Eintrag 5
        'Error5':                                     {'addr': '7534', 'len': 9, 'unit': 'ES',      'set': False},                                          # Fehlerhistory Eintrag 6
        'Error6':                                     {'addr': '753d', 'len': 9, 'unit': 'ES',      'set': False},                                          # Fehlerhistory Eintrag 7
        'Error7':                                     {'addr': '7546', 'len': 9, 'unit': 'ES',      'set': False},                                          # Fehlerhistory Eintrag 8
        'Error8':                                     {'addr': '754f', 'len': 9, 'unit': 'ES',      'set': False},                                          # Fehlerhistory Eintrag 9
        'Error9':                                     {'addr': '7558', 'len': 9, 'unit': 'ES',      'set': False},                                          # Fehlerhistory Eintrag 10
        # Pumpen
        'Speicherladepumpe':                          {'addr': '6513', 'len': 1, 'unit': 'IUBOOL',  'set': False},                                          # Speicherladepumpe
        'Zirkulationspumpe':                          {'addr': '6515', 'len': 1, 'unit': 'IUBOOL',  'set': False},                                          # Zirkulationspumpe
        'Interne_Pumpe':                              {'addr': '7660', 'len': 1, 'unit': 'IUBOOL',  'set': False},                                          # Interne Pumpe
        'Heizkreispumpe_A1M1':                        {'addr': '2906', 'len': 1, 'unit': 'IUBOOL',  'set': False},                                          # Heizkreispumpe A1
        'Heizkreispumpe_A1M1_RPM':                    {'addr': '7663', 'len': 1, 'unit': 'IUNON',   'set': False},                                          # Heizkreispumpe A1M1 Drehzahl
        'Heizkreispumpe_M2':                          {'addr': '3906', 'len': 1, 'unit': 'IUINT',   'set': False},                                          # Heizkreispumpe M2
        'Heizkreispumpe_M2_RPM':                      {'addr': '7665', 'len': 1, 'unit': 'IUNON',   'set': False},                                          # Heizkreispumpe M2 Drehzahl
        'Relais_Status_Pumpe_A1M1':                   {'addr': 'a152', 'len': 1, 'unit': 'IUBOOL',  'set': False},                                          # Relais-Status Heizkreispumpe 1
        # Brenner
        'Brennerstarts':                              {'addr': '088a', 'len': 4, 'unit': 'ISNON',   'set': True, 'min_value': 0,   'max_value': 1193045},   # Brennerstarts
        'Brenner_Betriebsstunden':                    {'addr': '08a7', 'len': 4, 'unit': 'IU3600',  'set': True, 'min_value': 0,   'max_value': 1193045},   # Brenner-Betriebsstunden
        'Brennerstatus_1':                            {'addr': '0842', 'len': 1, 'unit': 'IUBOOL',  'set': False},                                          # Brennerstatus Stufe1
        'Brennerstatus_2':                            {'addr': '0849', 'len': 1, 'unit': 'IUBOOL',  'set': False},                                          # Brennerstatus Stufe2
        'Oeldurchsatz':                               {'addr': '5726', 'len': 4, 'unit': 'ISNON',   'set': True, 'min_value': 0,   'max_value': 1193045},   # Oeldurchsatz Brenner in Dezi-Liter pro Stunde
        'Oelverbrauch':                               {'addr': '7574', 'len': 4, 'unit': 'IS1000',  'set': True},                                           # Oelverbrauch kumuliert
        # Solar
        'Nachladeunterdrueckung':                     {'addr': '6551', 'len': 1, 'unit': 'IUBOOL',  'set': False},
        'SolarPumpe':                                 {'addr': '6552', 'len': 1, 'unit': 'IUBOOL',  'set': False},
        'Kollektortemperatur':                        {'addr': '6564', 'len': 2, 'unit': 'IS10',    'set': False},
        'Speichertemperatur':                         {'addr': '6566', 'len': 2, 'unit': 'IU10',    'set': False},
        'Solar_Betriebsstunden':                      {'addr': '6568', 'len': 4, 'unit': 'IU100',   'set': False},
        'Solarsteuerung':                             {'addr': '7754', 'len': 2, 'unit': 'IUINT',   'set': False},
        # Heizkreis A1M1
        'Raumtemperatur_A1M1':                        {'addr': '0896', 'len': 1, 'unit': 'ISNON',   'set': False},                                          # Raumtemperatur A1M1
        'Raumtemperatur_Soll_Normalbetrieb_A1M1':     {'addr': '2306', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': 3,   'max_value': 37},        # Raumtemperatur Soll Normalbetrieb A1M1
        'Raumtemperatur_Soll_Red_Betrieb_A1M1':       {'addr': '2307', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': 3,   'max_value': 37},        # Raumtemperatur Soll Reduzierter Betrieb A1M1
        'Raumtemperatur_Soll_Party_Betrieb_A1M1':     {'addr': '2308', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': 3,   'max_value': 37},        # Raumtemperatur Soll Party Betrieb A1M1
        'Aktuelle_Betriebsart_A1M1':                  {'addr': '2301', 'len': 1, 'unit': 'BA',      'set': False},                                          # Aktuelle Betriebsart A1M1
        'Betriebsart_A1M1':                           {'addr': '2323', 'len': 1, 'unit': 'IUINT',   'set': True, 'min_value': 0,   'max_value': 4},         # Betriebsart A1M1
        'Sparbetrieb_A1M1':                           {'addr': '2302', 'len': 1, 'unit': 'IUBOOL',  'set': False},                                          # Sparbetrieb A1M1
        'Zustand_Sparbetrieb_A1M1':                   {'addr': '2331', 'len': 1, 'unit': 'IUBOOL',  'set': True, 'min_value': 0,   'max_value': 1},         # Zustand Sparbetrieb A1M1        
        'Partybetrieb_A1M1':                          {'addr': '2303', 'len': 1, 'unit': 'IUBOOL',  'set': False},                                          # Partybetrieb A1M1
        'Zustand_Partybetrieb_A1M1':                  {'addr': '2330', 'len': 1, 'unit': 'IUBOOL',  'set': True, 'min_value': 0,   'max_value': 1},         # Zustand Partybetrieb A1M1        
        'Vorlauftemperatur_A1M1':                     {'addr': '2900', 'len': 2, 'unit': 'IU10',    'set': False},                                          # Vorlauftemperatur A1M1
        'Vorlauftemperatur_Soll_A1M1':                {'addr': '2544', 'len': 2, 'unit': 'IU10',    'set': False},                                          # Vorlauftemperatur Soll A1M1
        'StatusFrost_A1M1':                           {'addr': '2500', 'len': 1, 'unit': 'IUBOOL',  'set': False},                                          # Status Frostwarnung A1M1
        'Externe_Raumsolltemperatur_Normal_A1M1':     {'addr': '2321', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': 0,   'max_value': 37},        # Externe Raumsolltemperatur Normal A1M1
        'Externe_Betriebsartenumschaltung_A1M1':      {'addr': '2549', 'len': 1, 'unit': 'IUINT',   'set': True, 'min_value': 0,   'max_value': 4},         # Externe Betriebsartenumschaltung A1M1
        'Speichervorrang_A1M1':                       {'addr': '27a2', 'len': 1, 'unit': 'IUINT',   'set': True, 'min_value': 0,   'max_value': 15},        # Speichervorrang auf Heizkreispumpe und Mischer
        'Frostschutzgrenze_A1M1':                     {'addr': '27a3', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': -9,  'max_value': 15},        # Frostschutzgrenze
        'Frostschutz_A1M1':                           {'addr': '27a4', 'len': 1, 'unit': 'IUBOOL',  'set': True, 'min_value': 0,   'max_value': 1},         # Frostschutzgrenze
        'Heizkreispumpenlogik_A1M1':                  {'addr': '27a5', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': 0,   'max_value': 15},        # HeizkreispumpenlogikFunktion
        'Sparschaltung_A1M1':                         {'addr': '27a6', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': 5,   'max_value': 35},        # AbsolutSommersparschaltung
        'Mischersparfunktion_A1M1':                   {'addr': '27a7', 'len': 1, 'unit': 'IUBOOL',  'set': True, 'min_value': 0,   'max_value': 1},         # Mischersparfunktion
        'Pumpenstillstandzeit_A1M1':                  {'addr': '27a9', 'len': 1, 'unit': 'IUINT',   'set': True, 'min_value': 0,   'max_value': 15},        # Pumpenstillstandzeit
        'Vorlauftemperatur_min_A1M1':                 {'addr': '27c5', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': 1,   'max_value': 127},       # Minimalbegrenzung der Vorlauftemperatur
        'Vorlauftemperatur_max_A1M1':                 {'addr': '27c6', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': 10,  'max_value': 127},       # Maximalbegrenzung der Vorlauftemperatur
        'Neigung_Heizkennlinie_A1M1':                 {'addr': '27d3', 'len': 1, 'unit': 'IU10',    'set': True, 'min_value': 0.2, 'max_value': 3.5},       # Neigung Heizkennlinie A1M1
        'Niveau_Heizkennlinie_A1M1':                  {'addr': '27d4', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': -13, 'max_value': 40},        # Niveau Heizkennlinie A1M1
        'Partybetrieb_Zeitbegrenzung_A1M1':           {'addr': '27f2', 'len': 1, 'unit': 'IUINT',   'set': True, 'min_value': 0,   'max_value': 12},        # Zeitliche Begrenzung für Partybetrieb oder externe BetriebsprogrammUmschaltung mit Taster
        'Temperaturgrenze_red_Betrieb_A1M1':          {'addr': '27f8', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': -61, 'max_value': 10},        # Temperaturgrenze für Aufhebung des reduzierten Betriebs -5 ºC
        'Temperaturgrenze_red_Raumtemp_A1M1':         {'addr': '27f9', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': -60, 'max_value': 10},        # Temperaturgrenze für Anhebung des reduzierten RaumtemperaturSollwertes
        'Vorlauftemperatur_Erhoehung_Soll_A1M1':      {'addr': '27fa', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': 0,   'max_value': 50},        # Erhöhung des Kesselwasser- bzw. Vorlauftemperatur-Sollwertes beim Übergang von Betrieb mit reduzierter Raumtemperatur in den Betrieb mit normaler Raumtemperatur um 20 %
        'Vorlauftemperatur_Erhoehung_Zeit_A1M1':      {'addr': '27fa', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': 0,   'max_value': 150},       # Zeitdauer für die Erhöhung des Kesselwasser bzw.VorlauftemperaturSollwertes (siehe Codieradresse „FA“) 60 min.
        # Heizkreis M2
        'Raumtemperatur_M2':                          {'addr': '0898', 'len': 1, 'unit': 'ISNON',   'set': False},                                          # Raumtemperatur
        'Raumtemperatur_Soll_Normalbetrieb_M2':       {'addr': '3306', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': 3,   'max_value': 37},        # Raumtemperatur Soll Normalbetrieb
        'Raumtemperatur_Soll_Red_Betrieb_M2':         {'addr': '3307', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': 3,   'max_value': 37},        # Raumtemperatur Soll Reduzierter Betrieb
        'Raumtemperatur_Soll_Party_Betrieb_M2':       {'addr': '3308', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': 3,   'max_value': 37},        # Raumtemperatur Soll Party Betrieb
        'Aktuelle_Betriebsart_M2':                    {'addr': '3301', 'len': 1, 'unit': 'BA',      'set': False},                                          # Aktuelle Betriebsart
        'Betriebsart_M2':                             {'addr': '3323', 'len': 1, 'unit': 'IUINT',   'set': True, 'min_value': 0,   'max_value': 4},         # Betriebsart
        'Sparbetrieb_M2':                             {'addr': '3302', 'len': 1, 'unit': 'IUBOOL',  'set': False},                                          # Sparbetrieb
        'Zustand_Sparbetrieb_M2':                     {'addr': '3331', 'len': 1, 'unit': 'IUBOOL',  'set': True, 'min_value': 0,   'max_value': 1},         # Zustand Sparbetrieb 
        'Partybetrieb_M2':                            {'addr': '3303', 'len': 1, 'unit': 'IUBOOL',  'set': False},                                          # Partybetrieb
        'Zustand_Partybetrieb_M2':                    {'addr': '3330', 'len': 1, 'unit': 'IUBOOL',  'set': True, 'min_value': 0,   'max_value': 1},         # Zustand Partybetrieb        
        'Vorlauftemperatur_M2':                       {'addr': '3900', 'len': 2, 'unit': 'IU10',    'set': False},                                          # Vorlauftemperatur
        'Vorlauftemperatur_Soll_M2':                  {'addr': '3544', 'len': 2, 'unit': 'IU10',    'set': False},                                          # Vorlauftemperatur Soll
        'StatusFrost_M2':                             {'addr': '3500', 'len': 1, 'unit': 'IUBOOL',  'set': False},                                          # Status Frostwarnung
        'Externe_Raumsolltemperatur_Normal_M2':       {'addr': '3321', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': 0,   'max_value': 37},        # Externe Raumsolltemperatur Normal
        'Externe_Betriebsartenumschaltung_M2':        {'addr': '3549', 'len': 1, 'unit': 'IUINT',   'set': True, 'min_value': 0,   'max_value': 4},         # Externe Betriebsartenumschaltung
        'Speichervorrang_M2':                         {'addr': '37a2', 'len': 1, 'unit': 'IUINT',   'set': True, 'min_value': 0,   'max_value': 15},        # Speichervorrang auf Heizkreispumpe und Mischer
        'Frostschutzgrenze_M2':                       {'addr': '37a3', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': -9,  'max_value': 15},        # Frostschutzgrenze
        'Frostschutz_M2':                             {'addr': '37a4', 'len': 1, 'unit': 'IUBOOL',  'set': True, 'min_value': 0,   'max_value': 1},         # Frostschutzgrenze
        'Heizkreispumpenlogik_M2':                    {'addr': '37a5', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': 0,   'max_value': 15},        # HeizkreispumpenlogikFunktion
        'Sparschaltung_M2':                           {'addr': '37a6', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': 5,   'max_value': 35},        # AbsolutSommersparschaltung
        'Mischersparfunktion_M2':                     {'addr': '37a7', 'len': 1, 'unit': 'IUBOOL',  'set': True, 'min_value': 0,   'max_value': 1},         # Mischersparfunktion
        'Pumpenstillstandzeit_M2':                    {'addr': '37a9', 'len': 1, 'unit': 'IUINT',   'set': True, 'min_value': 0,   'max_value': 15},        # Pumpenstillstandzeit
        'Vorlauftemperatur_min_M2':                   {'addr': '37c5', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': 1,   'max_value': 127},       # Minimalbegrenzung der Vorlauftemperatur
        'Vorlauftemperatur_max_M2':                   {'addr': '37c6', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': 10,  'max_value': 127},       # Maximalbegrenzung der Vorlauftemperatur
        'Neigung_Heizkennlinie_M2':                   {'addr': '37d3', 'len': 1, 'unit': 'IU10',    'set': True, 'min_value': 0.2, 'max_value': 3.5},       # Neigung Heizkennlinie
        'Niveau_Heizkennlinie_M2':                    {'addr': '37d4', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': -13, 'max_value': 40},        # Niveau Heizkennlinie
        'Partybetrieb_Zeitbegrenzung_M2':             {'addr': '37f2', 'len': 1, 'unit': 'IUINT',   'set': True, 'min_value': 0,   'max_value': 12},        # Zeitliche Begrenzung für Partybetrieb oder externe BetriebsprogrammUmschaltung mit Taster
        'Temperaturgrenze_red_Betrieb_M2':            {'addr': '37f8', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': -61, 'max_value': 10},        # Temperaturgrenze für Aufhebung des reduzierten Betriebs -5 ºC
        'Temperaturgrenze_red_Raumtemp_M2':           {'addr': '37f9', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': -60, 'max_value': 10},        # Temperaturgrenze für Anhebung des reduzierten RaumtemperaturSollwertes
        'Vorlauftemperatur_Erhoehung_Soll_M2':        {'addr': '37fa', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': 0,   'max_value': 50},        # Erhöhung des Kesselwasser- bzw. Vorlauftemperatur-Sollwertes beim Übergang von Betrieb mit reduzierter Raumtemperatur in den Betrieb mit normaler Raumtemperatur um 20 %
        'Vorlauftemperatur_Erhoehung_Zeit_M2':        {'addr': '37fb', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': 0,   'max_value': 150},       # Zeitdauer für die Erhöhung des Kesselwasser bzw.VorlauftemperaturSollwertes (siehe Codieradresse „FA“) 60 min.
         # Warmwasser
        'Warmwasser_Temperatur':                      {'addr': '0804', 'len': 2, 'unit': 'IU10',    'set': False},                                          # Warmwassertemperatur in Grad C
        'Warmwasser_Solltemperatur':                  {'addr': '6300', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': 10,  'max_value': 95},        # Warmwasser-Solltemperatur
        'Status_Warmwasserbereitung':                 {'addr': '650a', 'len': 1, 'unit': 'IUBOOL',  'set': True, 'min_value': 0,   'max_value': 1},         # Satus Warmwasserbereitung
        'WarmwasserPumpenNachlauf':                   {'addr': '6762', 'len': 2, 'unit': 'ISNON' ,  'set': True, 'min_value': 0,   'max_value': 1},         # Warmwasserpumpennachlauf
        # Ferienprogramm HK_A1M1
        'Ferienprogramm_A1M1':                        {'addr': '2535', 'len': 1, 'unit': 'IUINT',   'set': False},                                          # Ferienprogramm A1M1
        'Ferien_Abreisetag_A1M1':                     {'addr': '2309', 'len': 8, 'unit': 'DA',      'set': True},                                           # Ferien Abreisetag A1M1
        'Ferien_Rückreisetag_A1M1':                   {'addr': '2311', 'len': 8, 'unit': 'DA',      'set': True},                                           # Ferien Rückreisetag A1M1
        # Ferienprogramm HK_M2
        'Ferienprogramm_M2':                          {'addr': '3535', 'len': 1, 'unit': 'IUINT',   'set': False},                                          # Ferienprogramm M2
        'Ferien_Abreisetag_M2':                       {'addr': '3309', 'len': 8, 'unit': 'DA',      'set': True},                                           # Ferien Abreisetag M2
        'Ferien_Rückreisetag_M2':                     {'addr': '3311', 'len': 8, 'unit': 'DA',      'set': True},                                           # Ferien Rückreisetag M2
        # Schaltzeiten Warmwasser
        'Timer_Warmwasser_Mo':                        {'addr': '2100', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Warmwasserbereitung Montag
        'Timer_Warmwasser_Di':                        {'addr': '2108', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Warmwasserbereitung Dienstag
        'Timer_Warmwasser_Mi':                        {'addr': '2110', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Warmwasserbereitung Mittwoch
        'Timer_Warmwasser_Do':                        {'addr': '2118', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Warmwasserbereitung Donnerstag
        'Timer_Warmwasser_Fr':                        {'addr': '2120', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Warmwasserbereitung Freitag
        'Timer_Warmwasser_Sa':                        {'addr': '2128', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Warmwasserbereitung Samstag
        'Timer_Warmwasser_So':                        {'addr': '2130', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Warmwasserbereitung Sonntag
        # Schaltzeiten HK_A1M1
        'Timer_A1M1_Mo':                              {'addr': '2000', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Heizkreis_A1M1 Montag
        'Timer_A1M1_Di':                              {'addr': '2008', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Heizkreis_A1M1 Dienstag
        'Timer_A1M1_Mi':                              {'addr': '2010', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Heizkreis_A1M1 Mittwoch
        'Timer_A1M1_Do':                              {'addr': '2018', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Heizkreis_A1M1 Donnerstag
        'Timer_A1M1_Fr':                              {'addr': '2020', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Heizkreis_A1M1 Freitag
        'Timer_A1M1_Sa':                              {'addr': '2028', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Heizkreis_A1M1 Samstag
        'Timer_A1M1_So':                              {'addr': '2030', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Heizkreis_A1M1 Sonntag
        # Schaltzeiten HK_M2
        'Timer_M2_Mo':                                {'addr': '3000', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Heizkreis_A1M1 Montag
        'Timer_M2_Di':                                {'addr': '3008', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Heizkreis_A1M1 Dienstag
        'Timer_M2_Mi':                                {'addr': '3010', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Heizkreis_A1M1 Mittwoch
        'Timer_M2_Do':                                {'addr': '3018', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Heizkreis_A1M1 Donnerstag
        'Timer_M2_Fr':                                {'addr': '3020', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Heizkreis_A1M1 Freitag
        'Timer_M2_Sa':                                {'addr': '3028', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Heizkreis_A1M1 Samstag
        'Timer_M2_So':                                {'addr': '3030', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Heizkreis_A1M1 Sonntag
        # Schaltzeiten Zirkulation
        'Timer_Zirku_Mo':                             {'addr': '2200', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Zirkulationspumpe Montag
        'Timer_Zirku_Di':                             {'addr': '2208', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Zirkulationspumpe Dienstag
        'Timer_Zirku_Mi':                             {'addr': '2210', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Zirkulationspumpe Mittwoch
        'Timer_Zirku_Do':                             {'addr': '2218', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Zirkulationspumpe Donnerstag
        'Timer_Zirku_Fr':                             {'addr': '2220', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Zirkulationspumpe Freitag
        'Timer_Zirku_Sa':                             {'addr': '2228', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Zirkulationspumpe Samstag
        'Timer_Zirku_So':                             {'addr': '2230', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Zirkulationspumpe Sonntag
    },
    'V200HO1C': {
        # Allgemein
        'Anlagentyp':                                 {'addr': '00f8', 'len': 2, 'unit': 'DT',      'set': False},                                          # Heizungstyp
        'Anlagenschema':                              {'addr': '7700', 'len': 2, 'unit': 'SC',      'set': False},                                          # Anlagenschema
        'Frostgefahr':                                {'addr': '2510', 'len': 1, 'unit': 'IUBOOL',  'set': False},                                          # Frostgefahr
        'Aussentemperatur_TP':                        {'addr': '5525', 'len': 2, 'unit': 'IS10',    'set': False},                                          # Aussentemperatur_tiefpass
        'Aussentemperatur_Dp':                        {'addr': '5527', 'len': 2, 'unit': 'IS10',    'set': False},                                          # Aussentemperatur in Grad C (Gedaempft)
        'Anlagenleistung':                            {'addr': 'a38f', 'len': 2, 'unit': 'IS10',    'set': False},                                          # Anlagenleistung
        # Kessel
        'Kesseltemperatur_TP':                        {'addr': '0810', 'len': 2, 'unit': 'IU10',    'set': False},                                          # Kesseltemperatur_tiefpass
        'Kesselsolltemperatur':                       {'addr': '555a', 'len': 2, 'unit': 'IU10',    'set': False},                                          # Kesselsolltemperatur
        'Abgastemperatur':                            {'addr': '0816', 'len': 2, 'unit': 'IU10',    'set': False},                                          # Abgastemperatur
        # Fehler
        'Sammelstoerung':                             {'addr': '0a82', 'len': 1, 'unit': 'RT',      'set': False},                                          # Sammelstörung
        'Error0':                                     {'addr': '7507', 'len': 9, 'unit': 'ES',      'set': False},                                          # Fehlerhistory Eintrag 1
        'Error1':                                     {'addr': '7510', 'len': 9, 'unit': 'ES',      'set': False},                                          # Fehlerhistory Eintrag 2
        'Error2':                                     {'addr': '7519', 'len': 9, 'unit': 'ES',      'set': False},                                          # Fehlerhistory Eintrag 3
        'Error3':                                     {'addr': '7522', 'len': 9, 'unit': 'ES',      'set': False},                                          # Fehlerhistory Eintrag 4
        'Error4':                                     {'addr': '752b', 'len': 9, 'unit': 'ES',      'set': False},                                          # Fehlerhistory Eintrag 5
        'Error5':                                     {'addr': '7534', 'len': 9, 'unit': 'ES',      'set': False},                                          # Fehlerhistory Eintrag 6
        'Error6':                                     {'addr': '753d', 'len': 9, 'unit': 'ES',      'set': False},                                          # Fehlerhistory Eintrag 7
        'Error7':                                     {'addr': '7546', 'len': 9, 'unit': 'ES',      'set': False},                                          # Fehlerhistory Eintrag 8
        'Error8':                                     {'addr': '754f', 'len': 9, 'unit': 'ES',      'set': False},                                          # Fehlerhistory Eintrag 9
        'Error9':                                     {'addr': '7558', 'len': 9, 'unit': 'ES',      'set': False},                                          # Fehlerhistory Eintrag 10
        # Pumpen
        'Speicherladepumpe':                          {'addr': '6513', 'len': 1, 'unit': 'IUBOOL',  'set': False},                                          # Speicherladepumpe für Warmwasser
        'Zirkulationspumpe':                          {'addr': '6515', 'len': 1, 'unit': 'IUBOOL',  'set': True},                                           # Zirkulationspumpe
        'Interne_Pumpe':                              {'addr': '7660', 'len': 1, 'unit': 'IUBOOL',  'set': False},                                          # Interne Pumpe
        'Heizkreispumpe_HK1':                         {'addr': '2906', 'len': 1, 'unit': 'IUBOOL',  'set': False},                                          # Heizkreispumpe A1
        'Heizkreispumpe_HK2':                         {'addr': '3906', 'len': 1, 'unit': 'IUINT',   'set': False},                                          # Heizkreispumpe M2
        # Brenner
        'Brennerstarts':                              {'addr': '088a', 'len': 4, 'unit': 'ISNON',   'set': False},                                          # Brennerstarts
        'Brennerleistung':                            {'addr': 'a305', 'len': 2, 'unit': 'IS10',    'set': False},                                          # Brennerleistung
        'Brenner_Betriebsstunden':                    {'addr': '08a7', 'len': 4, 'unit': 'IU3600',  'set': False},                                          # Brenner-Betriebsstunden
        # Solar
        'SolarPumpe':                                 {'addr': '6552', 'len': 1, 'unit': 'IUBOOL',  'set': False},                                          # Solarpumpe
        'Kollektortemperatur':                        {'addr': '6564', 'len': 2, 'unit': 'IS10',    'set': False},                                          # Kollektortemperatur
        'Speichertemperatur':                         {'addr': '6566', 'len': 2, 'unit': 'IU10',    'set': False},                                          # Spichertemperatur
        'Solar_Betriebsstunden':                      {'addr': '6568', 'len': 4, 'unit': 'IU100',   'set': False},                                          # Solar Betriebsstunden
        'Solar_Waermemenge':                          {'addr': '6560', 'len': 2, 'unit': 'IUINT',   'set': False},                                          # Solar Waermemenge
        'Solar_Ausbeute':                             {'addr': 'cf30', 'len': 4, 'unit': 'IUINT',   'set': False},                                          # Solar Ausbeute
        # Heizkreis 1
        'Betriebsart_HK1':                            {'addr': '2500', 'len': 1, 'unit': 'IUINT',   'set': True, 'min_value': 0, 'max_value': 3},           # Betriebsart (0=Abschaltbetrieb, 1=Red. Betrieb, 2=Normalbetrieb (Schaltuhr), 3=Normalbetrieb (Dauernd))
        'Heizart_HK1':                                {'addr': '2323', 'len': 1, 'unit': 'IUINT',   'set': True, 'min_value': 0, 'max_value': 4},           # Heizart     (0=Abschaltbetrieb, 1=Nur Warmwasser, 2=Heizen und Warmwasser, 3=Normalbetrieb (Reduziert), 4=Normalbetrieb (Dauernd))
        'Vorlauftemperatur_Soll_HK1':                 {'addr': '2544', 'len': 2, 'unit': 'IU10',    'set': False},                                          # Vorlauftemperatur Soll
        'Vorlauftemperatur_HK1':                      {'addr': '2900', 'len': 2, 'unit': 'IU10',    'set': False},                                          # Vorlauftemperatur Ist
        # Heizkreis 2
        'Betriebsart_HK2':                            {'addr': '3500', 'len': 1, 'unit': 'IUINT',   'set': True, 'min_value': 0, 'max_value': 3},           # Betriebsart (0=Abschaltbetrieb, 1=Red. Betrieb, 2=Normalbetrieb (Schaltuhr), 3=Normalbetrieb (Dauernd))
        'Heizart_HK2':                                {'addr': '3323', 'len': 1, 'unit': 'IUINT',   'set': True, 'min_value': 0, 'max_value': 4},           # Heizart     (0=Abschaltbetrieb, 1=Nur Warmwasser, 2=Heizen und Warmwasser, 3=Normalbetrieb (Reduziert), 4=Normalbetrieb (Dauernd))
        'Vorlauftemperatur_Soll_HK2':                 {'addr': '3544', 'len': 2, 'unit': 'IU10',    'set': False},                                          # Vorlauftemperatur Soll
        'Vorlauftemperatur_HK2':                      {'addr': '3900', 'len': 2, 'unit': 'IU10',    'set': False},                                          # Vorlauftemperatur Ist
        # Warmwasser
        'Warmwasser_Temperatur':                      {'addr': '0812', 'len': 2, 'unit': 'IU10',    'set': False},                                          # Warmwassertemperatur in Grad C
        'Warmwasser_Solltemperatur':                  {'addr': '6300', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': 10, 'max_value': 80},         # Warmwasser-Solltemperatur
        'Warmwasser_Austrittstemperatur':             {'addr': '0814', 'len': 2, 'unit': 'IU10',    'set': False},                                          # Warmwasseraustrittstemperatur in Grad C
    },
    'V200KW2': {
        # Allgemein
        'Anlagentyp':                                 {'addr': '00f8', 'len': 2, 'unit': 'DT',      'set': False},                                          # Ermittle Device Typ der Anlage
        'Anlagenschema':                              {'addr': '7700', 'len': 2, 'unit': 'SC',      'set': False},                                          # Anlagenschema
        'AnlagenSoftwareIndex':                       {'addr': '7330', 'len': 1, 'unit': 'IUNON',   'set': False},                                          # Bedienteil SoftwareIndex
        'Aussentemperatur':                           {'addr': '0800', 'len': 2, 'unit': 'IS10',    'set': False},                                          # Aussentemperatur_tiefpass
        'Aussentemperatur_Dp':                        {'addr': '5527', 'len': 2, 'unit': 'IS10',    'set': False},                                          # Aussentemperatur in Grad C (Gedaempft)
        'Systemtime':                                 {'addr': '088e', 'len': 8, 'unit': 'TI',      'set': True},                                           # Systemzeit
        # Kessel
        'TempKOffset':                                {'addr': '6760', 'len': 1, 'unit': 'IUINT',   'set': True, 'min_value': 10,   'max_value': 50},       # Kesseloffset KT ueber WWsoll in Grad C
        'Kesseltemperatur':                           {'addr': '0802', 'len': 2, 'unit': 'IU10',    'set': False},                                          # Kesseltemperatur
        'Kesselsolltemperatur':                       {'addr': '5502', 'len': 2, 'unit': 'IU10',    'set': True},                                           # Kesselsolltemperatur
        # Fehler
        'Sammelstoerung':                             {'addr': '0847', 'len': 1, 'unit': 'RT',      'set': False},                                          # Sammelstörung
        'Brennerstoerung':                            {'addr': '0883', 'len': 1, 'unit': 'RT',      'set': False},
        'Error0':                                     {'addr': '7507', 'len': 9, 'unit': 'ES',      'set': False},                                          # Fehlerhistory Eintrag 1
        'Error1':                                     {'addr': '7510', 'len': 9, 'unit': 'ES',      'set': False},                                          # Fehlerhistory Eintrag 2
        'Error2':                                     {'addr': '7519', 'len': 9, 'unit': 'ES',      'set': False},                                          # Fehlerhistory Eintrag 3
        'Error3':                                     {'addr': '7522', 'len': 9, 'unit': 'ES',      'set': False},                                          # Fehlerhistory Eintrag 4
        'Error4':                                     {'addr': '752b', 'len': 9, 'unit': 'ES',      'set': False},                                          # Fehlerhistory Eintrag 5
        'Error5':                                     {'addr': '7534', 'len': 9, 'unit': 'ES',      'set': False},                                          # Fehlerhistory Eintrag 6
        'Error6':                                     {'addr': '753d', 'len': 9, 'unit': 'ES',      'set': False},                                          # Fehlerhistory Eintrag 7
        'Error7':                                     {'addr': '7546', 'len': 9, 'unit': 'ES',      'set': False},                                          # Fehlerhistory Eintrag 8
        'Error8':                                     {'addr': '754f', 'len': 9, 'unit': 'ES',      'set': False},                                          # Fehlerhistory Eintrag 9
        'Error9':                                     {'addr': '7558', 'len': 9, 'unit': 'ES',      'set': False},                                          # Fehlerhistory Eintrag 10
        # Pumpen
        'Speicherladepumpe':                          {'addr': '0845', 'len': 1, 'unit': 'IUBOOL',  'set': False},                                          # Speicherladepumpe für Warmwasser
        'Zirkulationspumpe':                          {'addr': '0846', 'len': 1, 'unit': 'IUBOOL',  'set': False},                                          # Zirkulationspumpe
        'Heizkreispumpe_A1M1':                        {'addr': '2906', 'len': 1, 'unit': 'IUBOOL',  'set': False},                                          # Heizkreispumpe A1M1
        'Heizkreispumpe_M2':                          {'addr': '3906', 'len': 1, 'unit': 'IUBOOL',  'set': False},                                          # Heizkreispumpe M2
        # Brenner
        'Brennertyp':                                 {'addr': 'a30b', 'len': 1, 'unit': 'IUNON',   'set': False},                                          # Brennertyp 0=einstufig 1=zweistufig 2=modulierend
        'Brennerstufe':                               {'addr': '551e', 'len': 1, 'unit': 'RT',      'set': False},                                          # Ermittle die aktuelle Brennerstufe
        'Brennerstarts':                              {'addr': '088a', 'len': 2, 'unit': 'ISNON',   'set': True, 'min_value': 0,   'max_value': 1193045},   # Brennerstarts
        'Brennerstatus_1':                            {'addr': '55d3', 'len': 1, 'unit': 'IUBOOL',  'set': False},                                          # Brennerstatus Stufe1
        'Brennerstatus_2':                            {'addr': '0849', 'len': 1, 'unit': 'IUBOOL',  'set': False},                                          # Brennerstatus Stufe2
        'Brenner_BetriebsstundenStufe1':              {'addr': '0886', 'len': 4, 'unit': 'IU3600',  'set': True, 'min_value': 0,   'max_value': 1193045},   # Brenner-Betriebsstunden Stufe 1
        'Brenner_BetriebsstundenStufe2':              {'addr': '08a3', 'len': 4, 'unit': 'IU3600',  'set': True, 'min_value': 0,   'max_value': 1193045},   # Brenner-Betriebsstunden Stufe 2
        # Heizkreis A1M1
        'Betriebsart_A1M1':                           {'addr': '2301', 'len': 1, 'unit': 'BA',      'set': True},                                           # Betriebsart A1M1
        'Aktuelle_Betriebsart_A1M1':                  {'addr': '2500', 'len': 1, 'unit': 'BA',      'set': False},                                          # Aktuelle Betriebsart A1M1
        'Sparbetrieb_A1M1':                           {'addr': '2302', 'len': 1, 'unit': 'IUBOOL',  'set': True, 'min_value': 0,   'max_value': 1},         # Sparbetrieb A1M1
        'Partybetrieb_A1M1_Zeit':                     {'addr': '27f2', 'len': 1, 'unit': 'IUINT',   'set': True, 'min_value': 0,   'max_value': 12},        # Partyzeit M2
        'Partybetrieb_A1M1':                          {'addr': '2303', 'len': 1, 'unit': 'IUBOOL',  'set': True, 'min_value': 0,   'max_value': 1},         # Partybetrieb A1M1
        'Vorlauftemperatur_A1M1':                     {'addr': '2900', 'len': 2, 'unit': 'IU10',    'set': False},                                          # Vorlauftemperatur A1M1
        'Vorlauftemperatur_Soll_A1M1':                {'addr': '2544', 'len': 2, 'unit': 'IU10',    'set': False},                                          # Vorlauftemperatur Soll A1M1
        'Raumtemperatur_Soll_Normalbetrieb_A1M1':     {'addr': '2306', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': 4,   'max_value': 37},        # Raumtemperatur Soll Normalbetrieb A1M1
        'Raumtemperatur_Soll_Red_Betrieb_A1M1':       {'addr': '2307', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': 4,   'max_value': 37},        # Raumtemperatur Soll Reduzierter Betrieb A1M1
        'Raumtemperatur_Soll_Party_Betrieb_A1M1':     {'addr': '2308', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': 4,   'max_value': 37},        # Raumtemperatur Soll Party Betrieb A1M1
        'Neigung_Heizkennlinie_A1M1':                 {'addr': '2305', 'len': 1, 'unit': 'IU10',    'set': True, 'min_value': 0.2, 'max_value': 3.5},       # Neigung Heizkennlinie A1M1
        'Niveau_Heizkennlinie_A1M1':                  {'addr': '2304', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': -13, 'max_value': 40},        # Niveau Heizkennlinie A1M1
        'MischerM1':                                  {'addr': '254c', 'len': 1, 'unit': 'IUPR',    'set': False},                                          # Ermittle Mischerposition M1
        'Heizkreispumpenlogik_A1M1':                  {'addr': '27a5', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': 0,   'max_value': 15},        # 0=ohne HPL-Funktion, 1=AT > RTsoll + 5 K, 2=AT > RTsoll + 4 K, 3=AT > RTsoll + 3 K, 4=AT > RTsoll + 2 K, 5=AT > RTsoll + 1 K, 6=AT > RTsoll, 7=AT > RTsoll - 1 K, 8=AT > RTsoll - 2 K, 9=AT > RTsoll - 3 K, 10=AT > RTsoll - 4 K, 11=AT > RTsoll - 5 K, 12=AT > RTsoll - 6 K, 13=AT > RTsoll - 7 K, 14=AT > RTsoll - 8 K, 15=AT > RTsoll - 9 K
        'Sparschaltung_A1M1':                         {'addr': '27a6', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': 5,   'max_value': 36},        # AbsolutSommersparschaltung
        # Heizkreis M2
        'Betriebsart_M2':                             {'addr': '3301', 'len': 1, 'unit': 'BA',      'set': True},                                           # Betriebsart M2
        'Aktuelle_Betriebsart_M2':                    {'addr': '3500', 'len': 1, 'unit': 'BA',      'set': False},                                          # Aktuelle Betriebsart M2
        'Sparbetrieb_M2':                             {'addr': '3302', 'len': 1, 'unit': 'IUBOOL',  'set': True, 'min_value': 0,   'max_value': 1},         # Sparbetrieb
        'Partybetrieb_M2':                            {'addr': '3303', 'len': 1, 'unit': 'IUBOOL',  'set': True, 'min_value': 0,   'max_value': 1},         # Partybetrieb A1M1
        'Partybetrieb_M2_Zeit':                       {'addr': '37f2', 'len': 1, 'unit': 'IUINT',   'set': True, 'min_value': 0,   'max_value': 12},        # Partyzeit M2
        'Raumtemperatur_Soll_Normalbetrieb_M2':       {'addr': '3306', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': 4,   'max_value': 37},        # Raumtemperatur Soll Normalbetrieb
        'Raumtemperatur_Soll_Red_Betrieb_M2':         {'addr': '3307', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': 4,   'max_value': 37},        # Raumtemperatur Soll Reduzierter Betrieb
        'Raumtemperatur_Soll_Party_Betrieb_M2':       {'addr': '3308', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': 4,   'max_value': 37},        # Raumtemperatur Soll Party Betrieb
        'Neigung_Heizkennlinie_M2':                   {'addr': '3305', 'len': 1, 'unit': 'IU10',    'set': True, 'min_value': 0.2, 'max_value': 3.5},       # Neigung Heizkennlinie M2
        'Niveau_Heizkennlinie_M2':                    {'addr': '3304', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': -13, 'max_value': 40},        # Niveau Heizkennlinie M2
        'MischerM2':                                  {'addr': '354c', 'len': 1, 'unit': 'IUPR',    'set': False},                                          # Ermittle Mischerposition M2
        'MischerM2Auf':                               {'addr': '084d', 'len': 1, 'unit': 'IUBOOL',  'set': True, 'min_value': 0,   'max_value': 1},         # MischerM2 Auf 0=AUS;1=EIN
        'MischerM2Zu':                                {'addr': '084c', 'len': 1, 'unit': 'IUBOOL',  'set': True, 'min_value': 0,   'max_value': 1},         # MischerM2 Zu 0=AUS;1=EIN
        'Vorlauftemperatur_Soll_M2':                  {'addr': '37c6', 'len': 2, 'unit': 'IU10',    'set': True, 'min_value': 10,  'max_value': 80},        # Vorlauftemperatur Soll
        'Vorlauftemperatur_M2':                       {'addr': '080c', 'len': 2, 'unit': 'IU10',    'set': False},                                          # Vorlauftemperatur Ist
        'Vorlauftemperatur_min_M2':                   {'addr': '37c5', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': 1,   'max_value': 127},       # Minimalbegrenzung der Vorlauftemperatur
        'Vorlauftemperatur_max_M2':                   {'addr': '37c6', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': 1,   'max_value': 127},       # Maximalbegrenzung der Vorlauftemperatur
        'Heizkreispumpenlogik_M2':                    {'addr': '37a5', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': 0,   'max_value': 15},        # 0=ohne HPL-Funktion, 1=AT > RTsoll + 5 K, 2=AT > RTsoll + 4 K, 3=AT > RTsoll + 3 K, 4=AT > RTsoll + 2 K, 5=AT > RTsoll + 1 K, 6=AT > RTsoll, 7=AT > RTsoll - 1 K, 8=AT > RTsoll - 2 K, 9=AT > RTsoll - 3 K, 10=AT > RTsoll - 4 K, 11=AT > RTsoll - 5 K, 12=AT > RTsoll - 6 K, 13=AT > RTsoll - 7 K, 14=AT > RTsoll - 8 K, 15=AT > RTsoll - 9 K
        'Sparschaltung_M2':                           {'addr': '37a6', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': 5,   'max_value': 36},        # AbsolutSommersparschaltung
        'StatusKlemme2':                              {'addr': '3904', 'len': 1, 'unit': 'IUINT',   'set': False},                                          # 0=OK, 1=Kurzschluss, 2=nicht vorhanden, 3-5=Referenzfehler, 6=nicht vorhanden
        'StatusKlemme17':                             {'addr': '3905', 'len': 1, 'unit': 'IUINT',   'set': False},                                          # 0=OK, 1=Kurzschluss, 2=nicht vorhanden, 3-5=Referenzfehler, 6=nicht vorhanden
        # Warmwasser
        'Warmwasser_Status':                          {'addr': '650A', 'len': 1, 'unit': 'IUNON',   'set': False},                                          # 0=Ladung inaktiv, 1=in Ladung, 2=im Nachlauf
        'Warmwasser_KesselOffset':                    {'addr': '6760', 'len': 1, 'unit': 'IUINT',   'set': True, 'min_value': 10,  'max_value': 50},        # Warmwasser Kessel Offset in K
        'Warmwasser_BeiPartyDNormal':                 {'addr': '6764', 'len': 1, 'unit': 'IUNON',   'set': True, 'min_value': 0,  'max_value': 2},          # WW Heizen bei Party 0=AUS, 1=nach Schaltuhr, 2=EIN
        'Warmwasser_Temperatur':                      {'addr': '0804', 'len': 2, 'unit': 'IU10',    'set': False},                                          # Warmwassertemperatur in Grad C
        'Warmwasser_Solltemperatur':                  {'addr': '6300', 'len': 1, 'unit': 'ISNON',   'set': True, 'min_value': 10,  'max_value': 80},        # Warmwasser-Solltemperatur
        'Warmwasser_SolltemperaturAktuell':           {'addr': '6500', 'len': 1, 'unit': 'IU10'  ,  'set': False},                                          # Warmwasser-Solltemperatur aktuell
        'Warmwasser_SollwertMax':                     {'addr': '675a', 'len': 1, 'unit': 'IUBOOL',  'set': False},                                          # 0=inaktiv, 1=aktiv
        # Ferienprogramm HK_A1M1
        'Ferienprogramm_A1M1':                        {'addr': '2535', 'len': 1, 'unit': 'IUBOOL',  'set': False},                                          # Ferienprogramm A1M1 0=inaktiv 1=aktiv
        'Ferien_Abreisetag_A1M1':                     {'addr': '2309', 'len': 8, 'unit': 'DA',      'set': True},                                           # Ferien Abreisetag A1M1
        'Ferien_Rückreisetag_A1M1':                   {'addr': '2311', 'len': 8, 'unit': 'DA',      'set': True},                                           # Ferien Rückreisetag A1M1
        # Ferienprogramm HK_M2
        'Ferienprogramm_M2':                          {'addr': '3535', 'len': 1, 'unit': 'IUBOOL',  'set': False},                                          # Ferienprogramm M2 0=inaktiv 1=aktiv
        'Ferien_Abreisetag_M2':                       {'addr': '3309', 'len': 8, 'unit': 'DA',      'set': True},                                           # Ferien Abreisetag M2
        'Ferien_Rückreisetag_M2':                     {'addr': '3311', 'len': 8, 'unit': 'DA',      'set': True},                                           # Ferien Rückreisetag M2
        # Schaltzeiten Warmwasser
        'Timer_Warmwasser_Mo':                        {'addr': '2100', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Warmwasserbereitung Montag
        'Timer_Warmwasser_Di':                        {'addr': '2108', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Warmwasserbereitung Dienstag
        'Timer_Warmwasser_Mi':                        {'addr': '2110', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Warmwasserbereitung Mittwoch
        'Timer_Warmwasser_Do':                        {'addr': '2118', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Warmwasserbereitung Donnerstag
        'Timer_Warmwasser_Fr':                        {'addr': '2120', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Warmwasserbereitung Freitag
        'Timer_Warmwasser_Sa':                        {'addr': '2128', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Warmwasserbereitung Samstag
        'Timer_Warmwasser_So':                        {'addr': '2130', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Warmwasserbereitung Sonntag
        # Schaltzeiten HK_A1M1
        'Timer_A1M1_Mo':                              {'addr': '2000', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Heizkreis_A1M1 Montag
        'Timer_A1M1_Di':                              {'addr': '2008', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Heizkreis_A1M1 Dienstag
        'Timer_A1M1_Mi':                              {'addr': '2010', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Heizkreis_A1M1 Mittwoch
        'Timer_A1M1_Do':                              {'addr': '2018', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Heizkreis_A1M1 Donnerstag
        'Timer_A1M1_Fr':                              {'addr': '2020', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Heizkreis_A1M1 Freitag
        'Timer_A1M1_Sa':                              {'addr': '2028', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Heizkreis_A1M1 Samstag
        'Timer_A1M1_So':                              {'addr': '2030', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Heizkreis_A1M1 Sonntag
        # Schaltzeiten HK_M2
        'Timer_M2_Mo':                                {'addr': '3000', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Heizkreis_A1M1 Montag
        'Timer_M2_Di':                                {'addr': '3008', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Heizkreis_A1M1 Dienstag
        'Timer_M2_Mi':                                {'addr': '3010', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Heizkreis_A1M1 Mittwoch
        'Timer_M2_Do':                                {'addr': '3018', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Heizkreis_A1M1 Donnerstag
        'Timer_M2_Fr':                                {'addr': '3020', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Heizkreis_A1M1 Freitag
        'Timer_M2_Sa':                                {'addr': '3028', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Heizkreis_A1M1 Samstag
        'Timer_M2_So':                                {'addr': '3030', 'len': 8, 'unit': 'CT',      'set': True},                                           # Timer Heizkreis_A1M1 Sonntag
    },
    'V200WO1C': {
        # generelle Infos
        'Anlagentyp':                                 {'addr': '00f8', 'len': 2, 'unit': 'DT',      'set': False},                                          # getAnlTyp -- Information - Allgemein: Anlagentyp (204D)
        'Aussentemperatur':                           {'addr': '0101', 'len': 2, 'unit': 'IS10',    'set': False},                                          # getTempA -- Information - Allgemein: Aussentemperatur (-40..70)
        # Anlagenstatus
        'Betriebsart':                                {'addr': 'b000', 'len': 1, 'unit': 'BA',      'set': True},                                           # getBetriebsart -- Bedienung HK1 - Heizkreis 1: Betriebsart (Textstring)
        'Manuell':                                    {'addr': 'b020', 'len': 1, 'unit': 'IUNON',   'set': True, 'min_value': 0,   'max_value': 2},         # getManuell / setManuell -- 0 = normal, 1 = manueller Heizbetrieb, 2 = 1x Warmwasser auf Temp2
        'Sekundaerpumpe':                             {'addr': '0484', 'len': 1, 'unit': 'RT',      'set': False},                                          # getStatusSekP -- Diagnose - Anlagenuebersicht: Sekundaerpumpe 1 (0..1)
        'Heizkreispumpe':                             {'addr': '048d', 'len': 1, 'unit': 'RT',      'set': False},                                          # getStatusPumpe -- Information - Heizkreis HK1: Heizkreispumpe (0..1)
        'Zirkulationspumpe':                          {'addr': '0490', 'len': 1, 'unit': 'RT',      'set': False},                                          # getStatusPumpeZirk -- Information - Warmwasser: Zirkulationspumpe (0..1)
        'VentilHeizenWW':                             {'addr': '0494', 'len': 1, 'unit': 'RT',      'set': False},                                          # getStatusVentilWW -- Diagnose - Waermepumpe: 3-W-Ventil Heizen WW1 (0 (Heizen)..1 (WW))
        'Vorlaufsolltemp':                            {'addr': '1800', 'len': 2, 'unit': 'IS10',    'set': False},                                          # getTempVLSoll -- Diagnose - Heizkreis HK1: Vorlaufsolltemperatur HK1 (0..95)
        'Outdoor_Fanspeed':                           {'addr': '1a52', 'len': 1, 'unit': 'IUNON',   'set': False},                                          # getSpdFanOut -- Outdoor Fanspeed
        'Status_Fanspeed':                            {'addr': '1a53', 'len': 1, 'unit': 'IUNON',   'set': False},                                          # getSpdFan -- Geschwindigkeit Luefter
        'Kompressor_Freq':                            {'addr': '1a54', 'len': 1, 'unit': 'IUNON',   'set': False},                                          # getSpdKomp -- Compressor Frequency
        # Temperaturen
        'SolltempWarmwasser':                         {'addr': '6000', 'len': 2, 'unit': 'IS10',    'set': True, 'min_value': 10,   'max_value': 60},       # getTempWWSoll -- Bedienung WW - Betriebsdaten WW: Warmwassersolltemperatur (10..60 (95))
        'VorlauftempSek':                             {'addr': '0105', 'len': 2, 'unit': 'IS10',    'set': False},                                          # getTempSekVL -- Information - Heizkreis HK1: Vorlauftemperatur Sekundaer 1 (0..95)
        'RuecklauftempSek':                           {'addr': '0106', 'len': 2, 'unit': 'IS10',    'set': False},                                          # getTempSekRL -- Diagnose - Anlagenuebersicht: Ruecklauftemperatur Sekundaer 1 (0..95)
        'Warmwassertemperatur':                       {'addr': '010d', 'len': 2, 'unit': 'IS10',    'set': False},                                          # getTempWWIstOben -- Information - Warmwasser: Warmwassertemperatur oben (0..95)
        # Stellwerte
        'Raumsolltemp':                               {'addr': '2000', 'len': 2, 'unit': 'IS10',    'set': False},                                          # getTempRaumSollNormal -- Bedienung HK1 - Heizkreis 1: Raumsolltemperatur normal (10..30)
        'RaumsolltempReduziert':                      {'addr': '2001', 'len': 2, 'unit': 'IS10',    'set': False},                                          # getTempRaumSollRed -- Bedienung HK1 - Heizkreis 1: Raumsolltemperatur reduzierter Betrieb (10..30)
        'HeizkennlinieNiveau':                        {'addr': '2006', 'len': 2, 'unit': 'IS10',    'set': False},                                          # getHKLNiveau -- Bedienung HK1 - Heizkreis 1: Niveau der Heizkennlinie (-15..40)
        'HeizkennlinieNeigung':                       {'addr': '2007', 'len': 2, 'unit': 'IS10',    'set': False},                                          # getHKLNeigung -- Bedienung HK1 - Heizkreis 1: Neigung der Heizkennlinie (0..35)
        'RaumsolltempParty':                          {'addr': '2022', 'len': 2, 'unit': 'IS10',    'set': False},                                          # getTempRaumSollParty -- Bedienung HK1 - Heizkreis 1: Party Solltemperatur (10..30)
        # Statistiken / Laufzeiten
        'EinschaltungenSekundaer':                    {'addr': '0504', 'len': 4, 'unit': 'IUNON',   'set': False},                                          # getAnzQuelleSek -- Statistik - Schaltzyklen Anlage: Einschaltungen Sekundaerquelle (?)
        'EinschaltungenHeizstab1':                    {'addr': '0508', 'len': 4, 'unit': 'IUNON',   'set': False},                                          # getAnzHeizstabSt1 -- Statistik - Schaltzyklen Anlage: Einschaltungen Heizstab Stufe 1 (?)
        'EinschaltungenHeizstab2':                    {'addr': '0509', 'len': 4, 'unit': 'IUNON',   'set': False},                                          # getAnzHeizstabSt2 -- Statistik - Schaltzyklen Anlage: Einschaltungen Heizstab Stufe 2 (?)
        'EinschaltungenHK':                           {'addr': '050d', 'len': 4, 'unit': 'IUNON',   'set': False},                                          # getAnzHK -- Statistik - Schaltzyklen Anlage: Einschaltungen Heizkreis (?)
        'LZSekundaerpumpe':                           {'addr': '0584', 'len': 4, 'unit': 'IU3600',  'set': False},                                          # getLZPumpeSek -- Statistik - Betriebsstunden Anlage: Betriebsstunden Sekundaerpumpe (?)
        'LZHeizstab1':                                {'addr': '0588', 'len': 4, 'unit': 'IU3600',  'set': False},                                          # getLZHeizstabSt1 -- Statistik - Betriebsstunden Anlage: Betriebsstunden Heizstab Stufe 1 (?)
        'LZHeizstab2':                                {'addr': '0589', 'len': 4, 'unit': 'IU3600',  'set': False},                                          # getLZHeizstabSt2 -- Statistik - Betriebsstunden Anlage: Betriebsstunden Heizstab Stufe 2 (?)
        'LZPumpeHK':                                  {'addr': '058d', 'len': 4, 'unit': 'IU3600',  'set': False},                                          # getLZPumpe -- Statistik - Betriebsstunden Anlage: Betriebsstunden Pumpe HK1 (0..1150000)
        'LZWWVentil':                                 {'addr': '0594', 'len': 4, 'unit': 'IU3600',  'set': False},                                          # getLZVentilWW -- Statistik - Betriebsstunden Anlage: Betriebsstunden Warmwasserventil (?)
        'LZVerdichterStufe1':                         {'addr': '1620', 'len': 4, 'unit': 'IUNON',   'set': False},                                          # getLZVerdSt1 -- Statistik - Betriebsstunden Anlage: Betriebsstunden Verdichter auf Stufe 1 (?)
        'LZVerdichterStufe2':                         {'addr': '1622', 'len': 4, 'unit': 'IUNON',   'set': False},                                          # getLZVerdSt2 -- Statistik - Betriebsstunden Anlage: Betriebsstunden Verdichter auf Stufe 2 (?)
        'LZVerdichterStufe3':                         {'addr': '1624', 'len': 4, 'unit': 'IUNON',   'set': False},                                          # getLZVerdSt3 -- Statistik - Betriebsstunden Anlage: Betriebsstunden Verdichter auf Stufe 3 (?)
        'LZVerdichterStufe4':                         {'addr': '1626', 'len': 4, 'unit': 'IUNON',   'set': False},                                          # getLZVerdSt4 -- Statistik - Betriebsstunden Anlage: Betriebsstunden Verdichter auf Stufe 4 (?)
        'LZVerdichterStufe5':                         {'addr': '1628', 'len': 4, 'unit': 'IUNON',   'set': False},                                          # getLZVerdSt5 -- Statistik - Betriebsstunden Anlage: Betriebsstunden Verdichter auf Stufe 5 (?)
        'VorlauftempSekMittel':                       {'addr': '16b2', 'len': 2, 'unit': 'IS10',    'set': False},                                          # getTempSekVLMittel -- Statistik - Energiebilanz: mittlere sek. Vorlauftemperatur (0..95)
        'RuecklauftempSekMittel':                     {'addr': '16b3', 'len': 2, 'unit': 'IS10',    'set': False},                                          # getTempSekRLMittel -- Statistik - Energiebilanz: mittlere sek.Temperatur RL1 (0..95)
        'OAT_Temperature':                            {'addr': '1a5c', 'len': 1, 'unit': 'IUNON',   'set': False},                                          # getTempOAT -- OAT Temperature
        'ICT_Temperature':                            {'addr': '1a5d', 'len': 1, 'unit': 'IUNON',   'set': False},                                          # getTempICT -- OCT Temperature
        'CCT_Temperature':                            {'addr': '1a5e', 'len': 1, 'unit': 'IUNON',   'set': False},                                          # getTempCCT -- CCT Temperature
        'HST_Temperature':                            {'addr': '1a5f', 'len': 1, 'unit': 'IUNON',   'set': False},                                          # getTempHST -- HST Temperature
        'OMT_Temperature':                            {'addr': '1a60', 'len': 1, 'unit': 'IUNON',   'set': False},                                          # getTempOMT -- OMT Temperature
        'LZVerdichterWP':                             {'addr': '5005', 'len': 4, 'unit': 'IU3600',  'set': False},                                          # getLZWP -- Statistik - Betriebsstunden Anlage: Betriebsstunden Waermepumpe  (0..1150000)
        'SollLeistungVerdichter':                     {'addr': '5030', 'len': 1, 'unit': 'IUNON',   'set': False},                                          # getPwrSollVerdichter -- Diagnose - Anlagenuebersicht: Soll-Leistung Verdichter 1 (0..100)
        'WaermeWW12M':                                {'addr': '1660', 'len': 4, 'unit': 'IU10',    'set': False},                                          # Wärmeenergie für WW-Bereitung der letzten 12 Monate (kWh)
        'ElektroWW12M':                               {'addr': '1670', 'len': 4, 'unit': 'IU10',    'set': False},                                          # elektr. Energie für WW-Bereitung der letzten 12 Monate (kWh)
    },
}

unitset = {
    'P300': {
        'BA':      {'unit_de': 'Betriebsart',       'type': 'list',     'signed': False, 'read_value_transform': 'non'},        # vito unit: BA
        'CT':      {'unit_de': 'CycleTime',         'type': 'timer',    'signed': False, 'read_value_transform': 'non'},        # vito unit: CT
        'DT':      {'unit_de': 'DeviceType',        'type': 'list',     'signed': False, 'read_value_transform': 'non'},        # vito unit: DT
        'ES':      {'unit_de': 'ErrorState',        'type': 'list',     'signed': False, 'read_value_transform': 'non'},        # vito unit: ES
        'IU2':     {'unit_de': 'INT unsigned 2',    'type': 'integer',  'signed': False, 'read_value_transform': '2'},          # vito unit: UT1U, PR1
        'IU10':    {'unit_de': 'INT unsigned 10',   'type': 'integer',  'signed': False, 'read_value_transform': '10'},         # vito unit:
        'IU100':   {'unit_de': 'INT unsigned 100',  'type': 'integer',  'signed': False, 'read_value_transform': '100'},        # vito unit:
        'IU3600':  {'unit_de': 'INT unsigned 3600', 'type': 'integer',  'signed': False, 'read_value_transform': '3600'},       # vito unit: CS
        'IUBOOL':  {'unit_de': 'INT unsigned bool', 'type': 'integer',  'signed': False, 'read_value_transform': 'bool'},       # vito unit:
        'IUINT':   {'unit_de': 'INT unsigned int',  'type': 'integer',  'signed': False, 'read_value_transform': '1'},          # vito unit:
        'IUNON':   {'unit_de': 'INT unsigned non',  'type': 'integer',  'signed': False, 'read_value_transform': 'non'},        # vito unit: UTI, CO
        'IS2':     {'unit_de': 'INT signed 2',      'type': 'integer',  'signed': True,  'read_value_transform': '2'},          # vito unit: UT1, PR
        'IS10':    {'unit_de': 'INT signed 10',     'type': 'integer',  'signed': True,  'read_value_transform': '10'},         # vito unit: UT, UN
        'IS100':   {'unit_de': 'INT signed 100',    'type': 'integer',  'signed': True,  'read_value_transform': '100'},        # vito unit:
        'IS1000':  {'unit_de': 'INT signed 1000',   'type': 'integer',  'signed': True,  'read_value_transform': '1000'},       # vito unit:
        'ISNON':   {'unit_de': 'INT signed non',    'type': 'integer',  'signed': True,  'read_value_transform': 'non'},        # vito unit:
        'RT':      {'unit_de': 'ReturnStatus',      'type': 'list',     'signed': False, 'read_value_transform': 'non'},        # vito unit: ST, RT
        'SC':      {'unit_de': 'SystemScheme',      'type': 'list',     'signed': False, 'read_value_transform': 'non'},        # vito unit:
        'SN':      {'unit_de': 'Sachnummer',        'type': 'serial',   'signed': False, 'read_value_transform': 'non'},        # vito unit:
        'SR':      {'unit_de': 'SetReturnStatus',   'type': 'list',     'signed': False, 'read_value_transform': 'non'},        # vito unit:
        'TI':      {'unit_de': 'SystemTime',        'type': 'datetime', 'signed': False, 'read_value_transform': 'non'},        # vito unit: TI
        'DA':      {'unit_de': 'Date',              'type': 'date',     'signed': False, 'read_value_transform': 'non'},        # vito unit:
        'HEX':     {'unit_de': 'HexString',         'type': 'string',   'signed': False, 'read_value_transform': 'hex'},        # vito unit:
    },
    'KW': {
        'BA':      {'unit_de': 'Betriebsart',       'type': 'list',     'signed': False, 'read_value_transform': 'non'},        # vito unit: BA
        'CT':      {'unit_de': 'CycleTime',         'type': 'timer',    'signed': False, 'read_value_transform': 'non'},        # vito unit: CT
        'DT':      {'unit_de': 'DeviceType',        'type': 'list',     'signed': False, 'read_value_transform': 'non'},        # vito unit: DT
        'ES':      {'unit_de': 'ErrorState',        'type': 'list',     'signed': False, 'read_value_transform': 'non'},        # vito unit: ES
        'IU2':     {'unit_de': 'INT unsigned 2',    'type': 'integer',  'signed': False, 'read_value_transform': '2'},          # vito unit: UT1U, PR1
        'IU10':    {'unit_de': 'INT unsigned 10',   'type': 'integer',  'signed': False, 'read_value_transform': '10'},         # vito unit:
        'IU100':   {'unit_de': 'INT unsigned 100',  'type': 'integer',  'signed': False, 'read_value_transform': '100'},        # vito unit:
        'IU1000':  {'unit_de': 'INT unsigned 1000', 'type': 'integer',  'signed': False, 'read_value_transform': '1000'},        # vito unit:
        'IU3600':  {'unit_de': 'INT unsigned 3600', 'type': 'integer',  'signed': False, 'read_value_transform': '3600'},       # vito unit: CS
        'IUPR':    {'unit_de': 'INT unsigned 2.55', 'type': 'integer',  'signed': False, 'read_value_transform': '2.55'},       # vito unit: PP
        'IUBOOL':  {'unit_de': 'INT unsigned bool', 'type': 'integer',  'signed': False, 'read_value_transform': 'bool'},       # vito unit:
        'IUINT':   {'unit_de': 'INT unsigned int',  'type': 'integer',  'signed': False, 'read_value_transform': '1'},          # vito unit:
        'IUNON':   {'unit_de': 'INT unsigned non',  'type': 'integer',  'signed': False, 'read_value_transform': 'non'},        # vito unit: UTI, CO
        'IS2':     {'unit_de': 'INT signed 2',      'type': 'integer',  'signed': True,  'read_value_transform': '2'},          # vito unit: UT1, PR
        'IS10':    {'unit_de': 'INT signed 10',     'type': 'integer',  'signed': True,  'read_value_transform': '10'},         # vito unit: UT, UN
        'IS100':   {'unit_de': 'INT signed 100',    'type': 'integer',  'signed': True,  'read_value_transform': '100'},        # vito unit:
        'IS1000':  {'unit_de': 'INT signed 1000',   'type': 'integer',  'signed': True,  'read_value_transform': '1000'},       # vito unit:
        'ISNON':   {'unit_de': 'INT signed non',    'type': 'integer',  'signed': True,  'read_value_transform': 'non'},        # vito unit:
        'RT':      {'unit_de': 'ReturnStatus',      'type': 'list',     'signed': False, 'read_value_transform': 'non'},        # vito unit: ST, RT
        'BT':      {'unit_de': 'Brennertyp',        'type': 'list',     'signed': False, 'read_value_transform': 'non'},        # vito unit:
        'SC':      {'unit_de': 'SystemScheme',      'type': 'list',     'signed': False, 'read_value_transform': 'non'},        # vito unit:
        'SN':      {'unit_de': 'Sachnummer',        'type': 'serial',   'signed': False, 'read_value_transform': 'non'},        # vito unit:
        'SR':      {'unit_de': 'SetReturnStatus',   'type': 'list',     'signed': False, 'read_value_transform': 'non'},        # vito unit:
        'TI':      {'unit_de': 'SystemTime',        'type': 'datetime', 'signed': False, 'read_value_transform': 'non'},        # vito unit: TI
        'DA':      {'unit_de': 'Date',              'type': 'date',     'signed': False, 'read_value_transform': 'non'},        # vito unit:
        'HEX':     {'unit_de': 'HexString',         'type': 'string',   'signed': False, 'read_value_transform': 'hex'},        # vito unit:
    }
}

errorset = {
    'P300': {
        '00': 'Regelbetrieb (kein Fehler)',
        '0F': 'Wartung (fuer Reset Codieradresse 24 auf 0 stellen)',
        '10': 'Kurzschluss Aussentemperatursensor',
        '18': 'Unterbrechung Aussentemperatursensor',
        '19': 'Unterbrechung Kommunikation Außentemperatursensor RF',
        '1D': 'Keine Kommunikation mit Sensor',
        '1E': 'Strömungssensor defekt',
        '1F': 'Strömungssensor defekt',
        '20': 'Kurzschluss Vorlauftemperatursensor',
        '21': 'Kurzschluss Ruecklauftemperatursensor',
        '28': 'Unterbrechung Aussentemperatursensor / Vorlauftemperatursensor Anlage',
        '29': 'Unterbrechung Ruecklauftemperatursensor',
        '30': 'Kurzschluss Kesseltemperatursensor',
        '38': 'Unterbrechung Kesseltemperatursensor',
        '40': 'Kurzschluss Vorlauftemperatursensor M2',
        '42': 'Unterbrechung Vorlauftemperatursensor M2',
        '44': 'Kurzschluss Vorlauftemperatursensor Heizkreis 3',
        '48': 'Unterbrechung Vorlauftemperatursensor Heizkreis 3',
        '50': 'Kurzschluss Speichertemperatursensor',
        '51': 'Kurzschluss Auslauftemperatursensor',
        '58': 'Unterbrechung Speichertemperatursensor',
        '59': 'Unterbrechung Auslauftemperatursensor',
        '92': 'Solar: Kurzschluss Kollektortemperatursensor',
        '93': 'Solar: Kurzschluss Sensor S3',
        '94': 'Solar: Kurzschluss Speichertemperatursensor',
        '9A': 'Solar: Unterbrechung Kollektortemperatursensor',
        '9B': 'Solar: Unterbrechung Sensor S3',
        '9C': 'Solar: Unterbrechung Speichertemperatursensor',
        '9E': 'Solar: Zu geringer bzw. kein Volumenstrom oder Temperaturwächter ausgeloest',
        '9F': 'Solar: Fehlermeldung Solarteil (siehe Solarregler)',
        'A4': 'Amx. Anlagendruck überschritten',
        'A7': 'Bedienteil defekt',
        'A8': 'Luft in der internen Umwaelzpumpe oder Mindest-Volumenstrom nicht erreicht',
        'B0': 'Kurzschluss Abgastemperatursensor',
        'B1': 'Kommunikationsfehler Bedieneinheit',
        'B4': 'Interner Fehler (Elektronik)',
        'B5': 'Interner Fehler (Elektronik)',
        'B6': 'Ungueltige Hardwarekennung (Elektronik)',
        'B7': 'Interner Fehler (Kesselkodierstecker)',
        'B8': 'Unterbrechung Abgastemperatursensor',
        'B9': 'Interner Fehler (Dateneingabe wiederholen)',
        'BA': 'Kommunikationsfehler Erweiterungssatz fuer Mischerkreis M2',
        'BB': 'Kommunikationsfehler Erweiterungssatz fuer Mischerkreis 3',
        'BC': 'Kommunikationsfehler Fernbedienung Vitorol, Heizkreis M1',
        'BD': 'Kommunikationsfehler Fernbedienung Vitorol, Heizkreis M2',
        'BE': 'Falsche Codierung Fernbedienung Vitorol',
        'BF': 'Falsches Kommunikationsmodul LON',
        'C1': 'Externe Sicherheitseinrichtung (Kessel kuehlt aus)',
        'C2': 'Kommunikationsfehler Solarregelung',
        'C3': 'Kommunikationsfehler Erweiterung AM1',
        'C4': 'Kommunikationsfehler Erweiterumg Open Therm',
        'C5': 'Kommunikationsfehler drehzahlgeregelte Heizkreispumpe, Heizkreis M1',
        'C6': 'Kommunikationsfehler drehzahlgeregelte Heizkreispumpe, Heizkreis M2',
        'C7': 'Falsche Codierung der Heizkreispumpe',
        'C8': 'Kommunikationsfehler drehzahlgeregelte, externe Heizkreispumpe 3',
        'C9': 'Stoermeldeeingang am Schaltmodul-V aktiv',
        'CD': 'Kommunikationsfehler Vitocom 100 (KM-BUS)',
        'CE': 'Kommunikationsfehler Schaltmodul-V',
        'CF': 'Kommunikationsfehler LON Modul',
        'D1': 'Brennerstoerung',
        'D4': 'Sicherheitstemperaturbegrenzer hat ausgeloest oder Stoermeldemodul nicht richtig gesteckt',
        'D6': 'Eingang DE1 an Erweiterung EA1 meldet eine Stoerung',
        'D7': 'Eingang DE2 an Erweiterung EA1 meldet eine Stoerung',
        'D8': 'Eingang DE3 an Erweiterung EA1 meldet eine Stoerung',
        'DA': 'Kurzschluss Raumtemperatursensor, Heizkreis M1',
        'DB': 'Kurzschluss Raumtemperatursensor, Heizkreis M2',
        'DC': 'Kurzschluss Raumtemperatursensor, Heizkreis 3',
        'DD': 'Unterbrechung Raumtemperatursensor, Heizkreis M1',
        'DE': 'Unterbrechung Raumtemperatursensor, Heizkreis M2',
        'DF': 'Unterbrechung Raumtemperatursensor, Heizkreis 3',
        'E0': 'Fehler externer LON Teilnehmer',
        'E1': 'Isolationsstrom waehrend des Kalibrierens zu hoch',
        'E3': 'Zu geringe Wärmeabnahme während des Kalibrierens, Temperaturwächter hat ausgeschaltet',
        'E4': 'Fehler Versorgungsspannung',
        'E5': 'Interner Fehler, Flammenverstärker(Ionisationselektrode)',
        'E6': 'Abgas- / Zuluftsystem verstopft, Anlagendruck zu niedrig',
        'E7': 'Ionisationsstrom waehrend des Kalibrierens zu gering',
        'E8': 'Ionisationsstrom nicht im gültigen Bereich',
        'EA': 'Ionisationsstrom waehrend des Kalibrierens nicht im gueltigen Bereich',
        'EB': 'Wiederholter Flammenverlust waehrend des Kalibrierens',
        'EC': 'Parameterfehler waehrend des Kalibrierens',
        'ED': 'Interner Fehler',
        'EE': 'Flammensignal ist bei Brennerstart nicht vorhanden oder zu gering',
        'EF': 'Flammenverlust direkt nach Flammenbildung (waehrend der Sicherheitszeit)',
        'F0': 'Interner Fehler (Regelung tauschen)',
        'F1': 'Abgastemperaturbegrenzer ausgeloest',
        'F2': 'Temperaturbegrenzer ausgeloest',
        'F3': 'Flammensigal beim Brennerstart bereits vorhanden',
        'F4': 'Flammensigal nicht vorhanden',
        'F7': 'Differenzdrucksensor defekt, Kurzschluss ider Wasserdrucksensor',
        'F8': 'Brennstoffventil schliesst zu spaet',
        'F9': 'Geblaesedrehzahl beim Brennerstart zu niedrig',
        'FA': 'Geblaesestillstand nicht erreicht',
        'FC': 'Gaskombiregler defekt oder fehlerhafte Ansteuerung Modulationsventil oder Abgasweg versperrt',
        'FD': 'Fehler Gasfeuerungsautomat, Kesselkodierstecker fehlt(in Verbindung mit B7)',
        'FE': 'Starkes Stoerfeld (EMV) in der Naehe oder Elektronik defekt',
        'FF': 'Starkes Stoerfeld (EMV) in der Naehe oder interner Fehler'
    },
    'KW': {
        '00': 'Regelbetrieb (kein Fehler)',
        '0F': 'Wartung (fuer Reset Codieradresse 24 auf 0 stellen)',
        '10': 'Kurzschluss Aussentemperatursensor',
        '18': 'Unterbrechung Aussentemperatursensor',
        '19': 'Unterbrechung Kommunikation Außentemperatursensor RF',
        '1D': 'Keine Kommunikation mit Sensor',
        '1E': 'Strömungssensor defekt',
        '1F': 'Strömungssensor defekt',
        '20': 'Kurzschluss Vorlauftemperatursensor',
        '21': 'Kurzschluss Ruecklauftemperatursensor',
        '28': 'Unterbrechung Aussentemperatursensor / Vorlauftemperatursensor Anlage',
        '29': 'Unterbrechung Ruecklauftemperatursensor',
        '30': 'Kurzschluss Kesseltemperatursensor',
        '38': 'Unterbrechung Kesseltemperatursensor',
        '40': 'Kurzschluss Vorlauftemperatursensor M2',
        '42': 'Unterbrechung Vorlauftemperatursensor M2',
        '44': 'Kurzschluss Vorlauftemperatursensor Heizkreis 3',
        '48': 'Unterbrechung Vorlauftemperatursensor Heizkreis 3',
        '50': 'Kurzschluss Speichertemperatursensor',
        '51': 'Kurzschluss Auslauftemperatursensor',
        '58': 'Unterbrechung Speichertemperatursensor',
        '59': 'Unterbrechung Auslauftemperatursensor',
        '92': 'Solar: Kurzschluss Kollektortemperatursensor',
        '93': 'Solar: Kurzschluss Sensor S3',
        '94': 'Solar: Kurzschluss Speichertemperatursensor',
        '9A': 'Solar: Unterbrechung Kollektortemperatursensor',
        '9B': 'Solar: Unterbrechung Sensor S3',
        '9C': 'Solar: Unterbrechung Speichertemperatursensor',
        '9E': 'Solar: Zu geringer bzw. kein Volumenstrom oder Temperaturwächter ausgeloest',
        '9F': 'Solar: Fehlermeldung Solarteil (siehe Solarregler)',
        'A4': 'Amx. Anlagendruck überschritten',
        'A7': 'Bedienteil defekt',
        'A8': 'Luft in der internen Umwaelzpumpe oder Mindest-Volumenstrom nicht erreicht',
        'B0': 'Kurzschluss Abgastemperatursensor',
        'B1': 'Kommunikationsfehler Bedieneinheit',
        'B4': 'Interner Fehler (Elektronik)',
        'B5': 'Interner Fehler (Elektronik)',
        'B6': 'Ungueltige Hardwarekennung (Elektronik)',
        'B7': 'Interner Fehler (Kesselkodierstecker)',
        'B8': 'Unterbrechung Abgastemperatursensor',
        'B9': 'Interner Fehler (Dateneingabe wiederholen)',
        'BA': 'Kommunikationsfehler Erweiterungssatz fuer Mischerkreis M2',
        'BB': 'Kommunikationsfehler Erweiterungssatz fuer Mischerkreis 3',
        'BC': 'Kommunikationsfehler Fernbedienung Vitorol, Heizkreis M1',
        'BD': 'Kommunikationsfehler Fernbedienung Vitorol, Heizkreis M2',
        'BE': 'Falsche Codierung Fernbedienung Vitorol',
        'BF': 'Falsches Kommunikationsmodul LON',
        'C1': 'Externe Sicherheitseinrichtung (Kessel kuehlt aus)',
        'C2': 'Kommunikationsfehler Solarregelung',
        'C3': 'Kommunikationsfehler Erweiterung AM1',
        'C4': 'Kommunikationsfehler Erweiterumg Open Therm',
        'C5': 'Kommunikationsfehler drehzahlgeregelte Heizkreispumpe, Heizkreis M1',
        'C6': 'Kommunikationsfehler drehzahlgeregelte Heizkreispumpe, Heizkreis M2',
        'C7': 'Falsche Codierung der Heizkreispumpe',
        'C8': 'Kommunikationsfehler drehzahlgeregelte, externe Heizkreispumpe 3',
        'C9': 'Stoermeldeeingang am Schaltmodul-V aktiv',
        'CD': 'Kommunikationsfehler Vitocom 100 (KM-BUS)',
        'CE': 'Kommunikationsfehler Schaltmodul-V',
        'CF': 'Kommunikationsfehler LON Modul',
        'D1': 'Brennerstoerung',
        'D4': 'Sicherheitstemperaturbegrenzer hat ausgeloest oder Stoermeldemodul nicht richtig gesteckt',
        'D6': 'Eingang DE1 an Erweiterung EA1 meldet eine Stoerung',
        'D7': 'Eingang DE2 an Erweiterung EA1 meldet eine Stoerung',
        'D8': 'Eingang DE3 an Erweiterung EA1 meldet eine Stoerung',
        'DA': 'Kurzschluss Raumtemperatursensor, Heizkreis M1',
        'DB': 'Kurzschluss Raumtemperatursensor, Heizkreis M2',
        'DC': 'Kurzschluss Raumtemperatursensor, Heizkreis 3',
        'DD': 'Unterbrechung Raumtemperatursensor, Heizkreis M1',
        'DE': 'Unterbrechung Raumtemperatursensor, Heizkreis M2',
        'DF': 'Unterbrechung Raumtemperatursensor, Heizkreis 3',
        'E0': 'Fehler externer LON Teilnehmer',
        'E1': 'Isolationsstrom waehrend des Kalibrierens zu hoch',
        'E3': 'Zu geringe Wärmeabnahme während des Kalibrierens, Temperaturwächter hat ausgeschaltet',
        'E4': 'Fehler Versorgungsspannung',
        'E5': 'Interner Fehler, Flammenverstärker(Ionisationselektrode)',
        'E6': 'Abgas- / Zuluftsystem verstopft, Anlagendruck zu niedrig',
        'E7': 'Ionisationsstrom waehrend des Kalibrierens zu gering',
        'E8': 'Ionisationsstrom nicht im gültigen Bereich',
        'EA': 'Ionisationsstrom waehrend des Kalibrierens nicht im gueltigen Bereich',
        'EB': 'Wiederholter Flammenverlust waehrend des Kalibrierens',
        'EC': 'Parameterfehler waehrend des Kalibrierens',
        'ED': 'Interner Fehler',
        'EE': 'Flammensignal ist bei Brennerstart nicht vorhanden oder zu gering',
        'EF': 'Flammenverlust direkt nach Flammenbildung (waehrend der Sicherheitszeit)',
        'F0': 'Interner Fehler (Regelung tauschen)',
        'F1': 'Abgastemperaturbegrenzer ausgeloest',
        'F2': 'Temperaturbegrenzer ausgeloest',
        'F3': 'Flammensigal beim Brennerstart bereits vorhanden',
        'F4': 'Flammensigal nicht vorhanden',
        'F7': 'Differenzdrucksensor defekt, Kurzschluss ider Wasserdrucksensor',
        'F8': 'Brennstoffventil schliesst zu spaet',
        'F9': 'Geblaesedrehzahl beim Brennerstart zu niedrig',
        'FA': 'Geblaesestillstand nicht erreicht',
        'FC': 'Gaskombiregler defekt oder fehlerhafte Ansteuerung Modulationsventil oder Abgasweg versperrt',
        'FD': 'Fehler Gasfeuerungsautomat, Kesselkodierstecker fehlt(in Verbindung mit B7)',
        'FE': 'Starkes Stoerfeld (EMV) in der Naehe oder Elektronik defekt',
        'FF': 'Starkes Stoerfeld (EMV) in der Naehe oder interner Fehler'
    },
}

operatingmodes = {
    'V200KW2': {
        '00': 'Warmwasser (Schaltzeiten)',
        '01': 'reduziert Heizen (dauernd)',
        '02': 'normal Heizen (dauernd)',
        '04': 'Heizen und Warmwasser (FS)',
        '03': 'Heizen und Warmwasser (Schaltzeiten)',
        '05': 'Standby',
    },
    'V200KO1B': {
        '00': 'Warmwasser (Schaltzeiten)',
        '01': 'reduziert Heizen (dauernd)',
        '02': 'normal Heizen (dauernd)',
        '04': 'Heizen und Warmwasser (FS)',
        '03': 'Heizen und Warmwasser (Schaltzeiten)',
        '05': 'Standby',
    },
    'aktuelle_Betriebsart': {
        '00': 'Abschaltbetrieb',
        '01': 'Reduzierter Betrieb',
        '02': 'Normalbetrieb',
        '03': 'Dauernd Normalbetrieb',
    },
    'V200WO1C': {
        '00': 'Abschaltbetrieb',
        '01': 'Warmwasser',
        '02': 'Heizen und Warmwasser',
        '03': 'undefiniert',
        '04': 'dauernd reduziert',
        '05': 'dauernd normal',
        '06': 'normal Abschalt',
        '07': 'nur kühlen',
    },
    'V200HO1C': {
        '00': 'Abschaltbetrieb',
        '01': 'Warmwasser',
        '02': 'Heizen und Warmwasser',
        '03': 'Normal reduziert',
        '04': 'Normal dauernd'
    }
}

systemschemes = {
    'V200KW2': {
        '00': '-',
        '01': 'A1',
        '02': 'A1 + WW',
        '03': 'M2',
        '04': 'M2 + WW',
        '05': 'A1 + M2',
        '06': 'A1 + M2 + WW',
        '07': 'M2 + M3',
        '08': 'M2 + M3 + WW',
        '09': 'M2 + M3 + WW',
        '10': 'A1 + M2 + M3 + WW'
    },
    'V200KO1B': {
        '01': 'A1',
        '02': 'A1 + WW',
        '04': 'M2',
        '03': 'M2 + WW',
        '05': 'A1 + M2',
        '06': 'A1 + M2 + WW'
    },
    'V200WO1C': {
        '01': 'WW',
        '02': 'HK + WW',
        '04': 'HK + WW',
        '05': 'HK + WW'
    },
    'V200HO1C': {
        '01': 'WW',
        '02': 'HK + WW',
        '04': 'HK + WW',
        '05': 'HK + WW'
    }
}

devicetypes = {
    '2098': 'V200KW2',   # Protokoll: KW
    '2053': 'GWG_VBEM',  # Protokoll: GWG
    '20CB': 'VScotHO1',  # Protokoll: P300
    '2094': 'V200KW1',   # Protokoll: KW
    '209F': 'V200KO1B',  # Protokoll: P300
    '204D': 'V200WO1C',  # Protokoll: P300
    '20B8': 'V333MW1',
    '20A0': 'V100GC1',
    '20C2': 'VDensHO1',
    '20A4': 'V200GW1',
    '20C8': 'VPlusHO1',
    '2046': 'V200WO1',
    '2047': 'V200WO1',
    '2049': 'V200WO1',
    '2032': 'VBC550',
    '2033': 'VBC550'
}

returnstatus = {
    'P300': {
        '00': '0',
        '01': '1',
        '03': '2',
        'AA': 'NOT OK',
        # At least for device 20CB the heating circuit pump returns status 03 when it's on and the heating runs in in night mode
    },
    'KW': {
        '00': '0',
        '01': '1',
        '03': '2',
        'AA': 'NOT OK',
    },
}

setreturnstatus = {
    'P300': {
        '00': 'OK',
        '05': 'SYNC (NOT OK)',
    },
    'KW': {
        '00': 'OK',
        '05': 'SYNC (NOT OK)',
    },
}


# P300 Protokoll
#
# Beispiel
#
# Senden        41 5 0 1 55 25 2 82
# Read Request  -- - - - ----- - --
#                | | | |   |   |  +------- Prüfsumme (Summe über alley Bytes ohne die 41; [hex]5+0+1+55+25+2 = [dez]5+0+1+(5x16)+5+(2x16)+5+2 = 130dez = 82hex
#                | | | |   |   +---------- XX Anzahl der Bytes, die in der Antwort erwartet werden
#                | | | |   +-------------- XX XX 2 byte Adresse der Daten oder Prozedur
#                | | | +------------------ XX 01 = ReadData, 02 = WriteData, 07 = Function Call
#                | | +-------------------- XX 00 = Anfrage, 01 = Antwort, 03 = Fehler
#                | +---------------------- Länge der Nutzdaten (Anzahl der Bytes zwischen dem Telegramm-Start-Byte (0x41) und der Prüfsumme)
#                +------------------------ Telegramm-Start-Byte
#
# Empfangen   :  6 ----------------------- OK (Antwort auf 0x16 0x00 0x00 und auf korrekt empfangene Telegramme)
#                5 ----------------------- Schnittstelle ist aktiv und wartet auf eine Initialisierung
#               15 ----------------------- Schnittstelle meldet einen Fehler zurück
#
#               41 7 1 1 55 25 2 EF 0 74
#               -- - - - ----- - ---- --
#                | | | |   |   |   |   +-- Prüfsumme (Summe über alley Bytes ohne die 41; [hex]7+1+1+55+25+2+EF+0 = [dez]7+1+1+(5x16)+5+(2x16)+5+2+(14*16)+(15*16)+0 = [dez]7+1+1+(80)+5+(32)+5+2+(224)+(15)+0 = 372dez = 1.74hex)
#                | | | |   |   |   +------ Wert
#                | | | |   |   +---------- XX Anzahl der Bytes, die in der Antwort erwartet werden
#                | | | |   +-------------- XX XX 2 byte Adresse der Daten oder Prozedur
#                | | | +------------------ XX 01 = ReadData, 02 = WriteData, 07 = Function Call
#                | | +-------------------- XX 00 = Anfrage, 01 = Antwort, 03 = Fehler
#                | +---------------------- Länge der Nutzdaten (Anzahl der Bytes zwischen dem Telegramm-Start-Byte (0x41) und der Prüfsumme)
#                +------------------------ Telegramm-Start-Byte
# Kommunikationsbeispiele
# Information Kessel Außentemperatur read 2-Byte -60..60 0x5525
# DATA TX: 41 5 0 1 55 25 2 82
# DATA RX: 41 7 1 1 55 25 2 EF 0 74 --> 00EF = 239 --> 23.9°C (Faktor 0.1)
# --> Senden   41 5 0 1 55 25 2 82
#              -- - - - ----- - --
#               | | | |   |   |  +-- Prüfsumme (Summe über alley Bytes ohne die 41; [hex]5+0+1+55+25+2 = [dez]5+0+1+(5x16)+5+(2x16)+5+2 = 130dez = 82hex
#               | | | |   |   +----- XX Anzahl der Bytes, die in der Antwort erwartet werden
#               | | | |   +--------- XX XX 2 byte Adresse der Daten oder Prozedur
#               | | | +------------- XX 01 = ReadData, 02 = WriteData, 07 = Function Call
#               | | +--------------- XX 00 = Anfrage, 01 = Antwort, 03 = Fehler
#               | +----------------- Länge der Nutzdaten (Anzahl der Bytes zwischen dem Telegramm-Start-Byte (0x41) und der Prüfsumme)
#               +------------------- Telegramm-Start-Byte
#
# --> Empfangen 6 41 7 1 1 55 25 2 EF 0 74
#               - -- - - - ----- - ---- --
#               |  | | | |   |   |   |   +-- Prüfsumme (Summe über alley Bytes ohne die 41; [hex]7+1+1+55+25+2+EF+0 = [dez]7+1+1+(5x16)+5+(2x16)+5+2+(14*16)+(15*16)+0 = [dez]7+1+1+(80)+5+(32)+5+2+(224)+(15)+0 = 372dez = 1.74hex)
#               |  | | | |   |   |   +------ Wert
#               |  | | | |   |   +---------- XX Anzahl der Bytes, die in der Antwort erwartet werden
#               |  | | | |   +-------------- XX XX 2 byte Adresse der Daten oder Prozedur
#               |  | | | +------------------ XX 01 = ReadData, 02 = WriteData, 07 = Function Call
#               |  | | +-------------------- XX 00 = Anfrage, 01 = Antwort, 03 = Fehler
#               |  | +---------------------- Länge der Nutzdaten (Anzahl der Bytes zwischen dem Telegramm-Start-Byte (0x41) und der Prüfsumme)
#               |  +------------------------ Telegramm-Start-Byte
#               +--------------------------- OK (Antwort auf 0x16 0x00 0x00 und auf korrekt empfangene Telegramme)
#
# --> Antwort: 0x00EF = 239 = 23.9°
