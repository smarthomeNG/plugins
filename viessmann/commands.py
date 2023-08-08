#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab

""" commands for dev viessmann """

# models defined:
#
# V200KW2
# V200KO1B
# V200WO1C
# V200HO1C


commands = {
    'ALL': {
        'Anlagentyp': {'read': True, 'write': False, 'opcode': '00f8', 'reply_pattern': '*', 'item_type': 'str', 'dev_datatype': 'H', 'params': {'value': 'VAL', 'len': 2}, 'lookup': 'devicetypes', 'item_attrs': {'no_read_groups': True, 'attributes': {'md_read_initial': True}}},     # getAnlTyp -- Information - Allgemein: Anlagentyp (204D)
    },
    'V200KO1B': {
        'Allgemein': {
            'Temperatur': {
                'Aussen':               {'read': True, 'write': False, 'opcode': '0800', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2}},     # Aussentemperatur
                'Aussen_TP':            {'read': True, 'write': False, 'opcode': '5525', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2}},     # Aussentemperatur_tiefpass
                'Aussen_Dp':            {'read': True, 'write': False, 'opcode': '5527', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2}},     # Aussentemperatur in Grad C (Gedaempft)
                'Speicher_Ladesensor':  {'read': True, 'write': False, 'opcode': '0812', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'len': 2}},     # Temperatur Speicher Ladesensor Komfortsensor
                'Auslauf':              {'read': True, 'write': False, 'opcode': '0814', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'len': 2}},     # Auslauftemperatur
                'Abgas':                {'read': True, 'write': False, 'opcode': '0816', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'len': 2}},     # Abgastemperatur
                'Gem_Vorlauf':          {'read': True, 'write': False, 'opcode': '081a', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'len': 2}},     # Gem. Vorlauftemperatur
            },
            'Relais_K12':               {'read': True, 'write': False, 'opcode': '0842', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # Relais K12 Interne Anschlußerweiterung
            'Eingang_0-10_V':           {'read': True, 'write': False, 'opcode': '0a86', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # Eingang 0-10 V
            'EA1_Kontakt_0':            {'read': True, 'write': False, 'opcode': '0a90', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # EA1: Kontakt 0
            'EA1_Kontakt_1':            {'read': True, 'write': False, 'opcode': '0a91', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # EA1: Kontakt 1
            'EA1_Kontakt_2':            {'read': True, 'write': False, 'opcode': '0a92', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # EA1: Kontakt 2
            'EA1_Externer_Soll_0-10V':  {'read': True, 'write': False, 'opcode': '0a93', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # EA1: Externer Sollwert 0-10V
            'EA1_Relais_0':             {'read': True, 'write': False, 'opcode': '0a95', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # EA1: Relais 0
            'AM1_Ausgang_1':            {'read': True, 'write': False, 'opcode': '0aa0', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # AM1 Ausgang 1
            'AM1_Ausgang_2':            {'read': True, 'write': False, 'opcode': '0aa1', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # AM1 Ausgang 2
            'TempKOffset':              {'read': True, 'write': True,  'opcode': '6760', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 1193045}},     # Kesseloffset KT ueber WWsoll in Grad C
            'Systemtime':               {'read': True, 'write': True,  'opcode': '088e', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'T', 'params': {'value': 'VAL', 'len': 8}},     # Systemzeit
            'Anlagenschema':            {'read': True, 'write': False, 'opcode': '7700', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 2}, 'lookup': 'systemschemes'},     # Anlagenschema
            'Inventory':                {'read': True, 'write': False, 'opcode': '08e0', 'reply_pattern': '*', 'item_type': 'str',  'dev_datatype': 'S', 'params': {'value': 'VAL', 'len': 7}},     # Sachnummer
            'CtrlId':                   {'read': True, 'write': False, 'opcode': '08e0', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 7}, 'lookup': 'devicetypes'},     # Reglerkennung
        },
        'Kessel': {
            # Kessel
            'Ist':                  {'read': True, 'write': False, 'opcode': '0802', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'len': 2}},     # Kesseltemperatur
            'TP':                   {'read': True, 'write': False, 'opcode': '0810', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'len': 2}},     # Kesseltemperatur_tiefpass
            'Soll':                 {'read': True, 'write': False, 'opcode': '555a', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'len': 2}},     # Kesselsolltemperatur
        },
        'Fehler': {
            # Fehler
            'Sammelstoerung':           {'read': True, 'write': False, 'opcode': '0a82', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'lookup': 'returnstatus'},     # Sammelstörung
            'Error0':                   {'read': True, 'write': False, 'opcode': '7507', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 9}, 'lookup': 'errors'},     # Fehlerhistory Eintrag 1
            'Error1':                   {'read': True, 'write': False, 'opcode': '7510', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 9}, 'lookup': 'errors'},     # Fehlerhistory Eintrag 2
            'Error2':                   {'read': True, 'write': False, 'opcode': '7519', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 9}, 'lookup': 'errors'},     # Fehlerhistory Eintrag 3
            'Error3':                   {'read': True, 'write': False, 'opcode': '7522', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 9}, 'lookup': 'errors'},     # Fehlerhistory Eintrag 4
            'Error4':                   {'read': True, 'write': False, 'opcode': '752b', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 9}, 'lookup': 'errors'},     # Fehlerhistory Eintrag 5
            'Error5':                   {'read': True, 'write': False, 'opcode': '7534', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 9}, 'lookup': 'errors'},     # Fehlerhistory Eintrag 6
            'Error6':                   {'read': True, 'write': False, 'opcode': '753d', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 9}, 'lookup': 'errors'},     # Fehlerhistory Eintrag 7
            'Error7':                   {'read': True, 'write': False, 'opcode': '7546', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 9}, 'lookup': 'errors'},     # Fehlerhistory Eintrag 8
            'Error8':                   {'read': True, 'write': False, 'opcode': '754f', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 9}, 'lookup': 'errors'},     # Fehlerhistory Eintrag 9
            'Error9':                   {'read': True, 'write': False, 'opcode': '7558', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 9}, 'lookup': 'errors'},     # Fehlerhistory Eintrag 10
        },
        'Pumpen': {
            # Pumpen
            'Speicherlade':             {'read': True, 'write': False, 'opcode': '6513', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # Speicherladepumpe
            'Zirkulation':              {'read': True, 'write': False, 'opcode': '6515', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # Zirkulationspumpe
            'Intern':                   {'read': True, 'write': False, 'opcode': '7660', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # Interne Pumpe
            'Heizkreis_A1M1':           {'read': True, 'write': False, 'opcode': '2906', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # Heizkreispumpe A1
            'Heizkreis_A1M1_RPM':       {'read': True, 'write': False, 'opcode': '7663', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # Heizkreispumpe A1M1 Drehzahl
            'Heizkreis_M2':             {'read': True, 'write': False, 'opcode': '3906', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # Heizkreispumpe M2
            'Heizkreis_M2_RPM':         {'read': True, 'write': False, 'opcode': '7665', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # Heizkreispumpe M2 Drehzahl
            'Relais_Status':            {'read': True, 'write': False, 'opcode': 'a152', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # Relais-Status Heizkreispumpe 1
        },
        'Brenner': {
            # Brenner
            'Starts':                   {'read': True, 'write': True,  'opcode': '088a', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 4}, 'cmd_settings': {'force_min': 0, 'force_max': 1193045}},     # Brennerstarts
            'Betriebsstunden':          {'read': True, 'write': True,  'opcode': '08a7', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 3600, 'len': 4}, 'cmd_settings': {'force_min': 0, 'force_max': 1193045}},     # Brenner-Betriebsstunden
            'Status_1':                 {'read': True, 'write': False, 'opcode': '0842', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # Brennerstatus Stufe1
            'Status_2':                 {'read': True, 'write': False, 'opcode': '0849', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # Brennerstatus Stufe2
            'Oeldurchsatz':             {'read': True, 'write': True,  'opcode': '5726', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 4}, 'cmd_settings': {'force_min': 0, 'force_max': 1193045}},     # Oeldurchsatz Brenner in Dezi-Liter pro Stunde
            'Oelverbrauch':             {'read': True, 'write': True,  'opcode': '7574', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 1000, 'signed': True, 'len': 4}},     # Oelverbrauch kumuliert
        },
        'Solar': {
            # Solar
            'Nachladeunterdrueckung':   {'read': True, 'write': False, 'opcode': '6551', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},
            'Pumpe':                    {'read': True, 'write': False, 'opcode': '6552', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},
            'Kollektortemperatur':      {'read': True, 'write': False, 'opcode': '6564', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2}},
            'Speichertemperatur':       {'read': True, 'write': False, 'opcode': '6566', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'len': 2}},
            'Betriebsstunden':          {'read': True, 'write': False, 'opcode': '6568', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 100, 'len': 4}},
            'Steuerung':                {'read': True, 'write': False, 'opcode': '7754', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 2}},
        },
        'Heizkreis': {
            'A1M1': {
                # Heizkreis A1M1
                'Temperatur': {
                    'Raum': {
                        'Ist':                           {'read': True, 'write': False, 'opcode': '0896', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}},     # Raumtemperatur A1M1
                        'Soll_Normalbetrieb':            {'read': True, 'write': True,  'opcode': '2306', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': 3, 'force_max': 37}},     # Raumtemperatur Soll Normalbetrieb A1M1
                        'Soll_Red_Betrieb':              {'read': True, 'write': True,  'opcode': '2307', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': 3, 'force_max': 37}},     # Raumtemperatur Soll Reduzierter Betrieb A1M1
                        'Soll_Party_Betrieb':            {'read': True, 'write': True,  'opcode': '2308', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': 3, 'force_max': 37}},     # Raumtemperatur Soll Party Betrieb A1M1
                    },
                    'Vorlauf': {
                        'Ist':                           {'read': True, 'write': False, 'opcode': '2900', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'len': 2}},     # Vorlauftemperatur A1M1
                        'Soll':                          {'read': True, 'write': False, 'opcode': '2544', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'len': 2}},     # Vorlauftemperatur Soll A1M1
                        'Min':                           {'read': True, 'write': True,  'opcode': '27c5', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': 1, 'force_max': 127}},     # Minimalbegrenzung der Vorlauftemperatur
                        'Max':                           {'read': True, 'write': True,  'opcode': '27c6', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': 10, 'force_max': 127}},     # Maximalbegrenzung der Vorlauftemperatur
                        'Erhoehung_Soll':                {'read': True, 'write': True,  'opcode': '27fa', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 50}},     # Erhöhung des Kesselwasser- bzw. Vorlauftemperatur-Sollwertes beim Übergang von Betrieb mit reduzierter Raumtemperatur in den Betrieb mit normaler Raumtemperatur um 20 %
                        'Erhoehung_Zeit':                {'read': True, 'write': True,  'opcode': '27fa', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 150}},     # Zeitdauer für die Erhöhung des Kesselwasser bzw.VorlauftemperaturSollwertes (siehe Codieradresse „FA“) 60 min.
                    },
                    'Grenze_red_Betrieb':                {'read': True, 'write': True,  'opcode': '27f8', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': -61, 'force_max': 10}},     # Temperaturgrenze für Aufhebung des reduzierten Betriebs -5 ºC
                    'Grenze_red_Raumtemp':               {'read': True, 'write': True,  'opcode': '27f9', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': -60, 'force_max': 10}},     # Temperaturgrenze für Anhebung des reduzierten RaumtemperaturSollwertes
                },
                'Status': {
                    'Aktuelle_Betriebsart':              {'read': True, 'write': False, 'opcode': '2301', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'lookup': 'operatingmodes'},     # Aktuelle Betriebsart A1M1
                    'Betriebsart':                       {'read': True, 'write': True,  'opcode': '2323', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 4}},     # Betriebsart A1M1
                    'Sparbetrieb':                       {'read': True, 'write': False, 'opcode': '2302', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # Sparbetrieb A1M1
                    'Zustand_Sparbetrieb':               {'read': True, 'write': True,  'opcode': '2331', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 1}},     # Zustand Sparbetrieb A1M1
                    'Partybetrieb':                      {'read': True, 'write': False, 'opcode': '2303', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # Partybetrieb A1M1
                    'Zustand_Partybetrieb':              {'read': True, 'write': True,  'opcode': '2330', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 1}},     # Zustand Partybetrieb A1M1
                    'StatusFrost':                       {'read': True, 'write': False, 'opcode': '2500', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # Status Frostwarnung A1M1
                    'Externe_Raumsolltemperatur_Normal': {'read': True, 'write': True,  'opcode': '2321', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 37}},     # Externe Raumsolltemperatur Normal A1M1
                    'Externe_Betriebsartenumschaltung':  {'read': True, 'write': True,  'opcode': '2549', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 4}},     # Externe Betriebsartenumschaltung A1M1
                    'Speichervorrang':                   {'read': True, 'write': True,  'opcode': '27a2', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 15}},     # Speichervorrang auf Heizkreispumpe und Mischer
                    'Frostschutzgrenze':                 {'read': True, 'write': True,  'opcode': '27a3', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': -9, 'force_max': 15}},     # Frostschutzgrenze
                    'Frostschutz':                       {'read': True, 'write': True,  'opcode': '27a4', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 1}},     # Frostschutzgrenze
                    'Heizkreispumpenlogik':              {'read': True, 'write': True,  'opcode': '27a5', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 15}},     # HeizkreispumpenlogikFunktion
                    'Sparschaltung':                     {'read': True, 'write': True,  'opcode': '27a6', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': 5, 'force_max': 35}},     # AbsolutSommersparschaltung
                    'Mischersparfunktion':               {'read': True, 'write': True,  'opcode': '27a7', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 1}},     # Mischersparfunktion
                    'Pumpenstillstandzeit':              {'read': True, 'write': True,  'opcode': '27a9', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 15}},     # Pumpenstillstandzeit
                },
                'Heizkennlinie': {
                    'Neigung':                           {'read': True, 'write': True,  'opcode': '27d3', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'len': 1}, 'cmd_settings': {'force_min': 0.2, 'force_max': 3.5}},     # Neigung Heizkennlinie A1M1
                    'Niveau':                            {'read': True, 'write': True,  'opcode': '27d4', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': -13, 'force_max': 40}},     # Niveau Heizkennlinie A1M1
                },
                'Partybetrieb_Zeitbegrenzung':           {'read': True, 'write': True,  'opcode': '27f2', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 12}},     # Zeitliche Begrenzung für Partybetrieb oder externe BetriebsprogrammUmschaltung mit Taster
            },
            'M2': {
                # Heizkreis M2
                'Temperatur': {
                    'Raum': {
                        'Ist':                           {'read': True, 'write': False, 'opcode': '0898', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}},     # Raumtemperatur
                        'Soll_Normalbetrieb':            {'read': True, 'write': True,  'opcode': '3306', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': 3, 'force_max': 37}},     # Raumtemperatur Soll Normalbetrieb
                        'Soll_Red_Betrieb':              {'read': True, 'write': True,  'opcode': '3307', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': 3, 'force_max': 37}},     # Raumtemperatur Soll Reduzierter Betrieb
                        'Soll_Party_Betrieb':            {'read': True, 'write': True,  'opcode': '3308', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': 3, 'force_max': 37}},     # Raumtemperatur Soll Party Betrieb
                    },
                    'Vorlauf': {
                        'Ist':                           {'read': True, 'write': False, 'opcode': '3900', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'len': 2}},     # Vorlauftemperatur
                        'Soll':                          {'read': True, 'write': False, 'opcode': '3544', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'len': 2}},     # Vorlauftemperatur Soll
                        'Min':                           {'read': True, 'write': True,  'opcode': '37c5', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': 1, 'force_max': 127}},     # Minimalbegrenzung der Vorlauftemperatur
                        'Max':                           {'read': True, 'write': True,  'opcode': '37c6', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': 10, 'force_max': 127}},     # Maximalbegrenzung der Vorlauftemperatur
                        'Erhoehung_Soll':                {'read': True, 'write': True,  'opcode': '37fa', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 50}},     # Erhöhung des Kesselwasser- bzw. Vorlauftemperatur-Sollwertes beim Übergang von Betrieb mit reduzierter Raumtemperatur in den Betrieb mit normaler Raumtemperatur um 20 %
                        'Erhoehung_Zeit':                {'read': True, 'write': True,  'opcode': '37fb', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 150}},     # Zeitdauer für die Erhöhung des Kesselwasser bzw.VorlauftemperaturSollwertes (siehe Codieradresse „FA“) 60 min.
                    },
                    'Grenze_red_Betrieb':                {'read': True, 'write': True,  'opcode': '37f8', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': -61, 'force_max': 10}},     # Temperaturgrenze für Aufhebung des reduzierten Betriebs -5 ºC
                    'Grenze_red_Raumtemp':               {'read': True, 'write': True,  'opcode': '37f9', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': -60, 'force_max': 10}},     # Temperaturgrenze für Anhebung des reduzierten RaumtemperaturSollwertes
                },
                'Status': {
                    'Aktuelle_Betriebsart':              {'read': True, 'write': False, 'opcode': '3301', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'lookup': 'operatingmodes'},     # Aktuelle Betriebsart
                    'Betriebsart':                       {'read': True, 'write': True,  'opcode': '3323', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 4}},     # Betriebsart
                    'Sparbetrieb':                       {'read': True, 'write': False, 'opcode': '3302', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # Sparbetrieb
                    'Zustand_Sparbetrieb':               {'read': True, 'write': True,  'opcode': '3331', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 1}},     # Zustand Sparbetrieb
                    'Partybetrieb':                      {'read': True, 'write': False, 'opcode': '3303', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # Partybetrieb
                    'Zustand_Partybetrieb':              {'read': True, 'write': True,  'opcode': '3330', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 1}},     # Zustand Partybetrieb
                    'StatusFrost':                       {'read': True, 'write': False, 'opcode': '3500', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # Status Frostwarnung
                    'Externe_Raumsolltemperatur_Normal': {'read': True, 'write': True,  'opcode': '3321', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 37}},     # Externe Raumsolltemperatur Normal
                    'Externe_Betriebsartenumschaltung':  {'read': True, 'write': True,  'opcode': '3549', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 4}},     # Externe Betriebsartenumschaltung
                    'Speichervorrang':                   {'read': True, 'write': True,  'opcode': '37a2', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 15}},     # Speichervorrang auf Heizkreispumpe und Mischer
                    'Frostschutzgrenze':                 {'read': True, 'write': True,  'opcode': '37a3', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': -9, 'force_max': 15}},     # Frostschutzgrenze
                    'Frostschutz':                       {'read': True, 'write': True,  'opcode': '37a4', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 1}},     # Frostschutzgrenze
                    'Heizkreispumpenlogik':              {'read': True, 'write': True,  'opcode': '37a5', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 15}},     # HeizkreispumpenlogikFunktion
                    'Sparschaltung':                     {'read': True, 'write': True,  'opcode': '37a6', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': 5, 'force_max': 35}},     # AbsolutSommersparschaltung
                    'Mischersparfunktion':               {'read': True, 'write': True,  'opcode': '37a7', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 1}},     # Mischersparfunktion
                    'Pumpenstillstandzeit':              {'read': True, 'write': True,  'opcode': '37a9', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 15}},     # Pumpenstillstandzeit
                },
                'Heizkennlinie': {
                    'Neigung':                           {'read': True, 'write': True,  'opcode': '37d3', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'len': 1}, 'cmd_settings': {'force_min': 0.2, 'force_max': 3.5}},     # Neigung Heizkennlinie
                    'Niveau':                            {'read': True, 'write': True,  'opcode': '37d4', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': -13, 'force_max': 40}},     # Niveau Heizkennlinie
                },
                'Partybetrieb_Zeitbegrenzung':           {'read': True, 'write': True,  'opcode': '37f2', 'reply_pattern': '*', 'item_type': 'num', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 12}},     # Zeitliche Begrenzung für Partybetrieb oder externe BetriebsprogrammUmschaltung mit Taster
            },
        },
        'Warmwasser': {
            # Warmwasser
            'Ist':              {'read': True, 'write': False, 'opcode': '0804', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'len': 2}},     # Warmwassertemperatur in Grad C
            'Soll':             {'read': True, 'write': True,  'opcode': '6300', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': 10, 'force_max': 95}},     # Warmwasser-Solltemperatur
            'Status':           {'read': True, 'write': True,  'opcode': '650a', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 1}},     # Satus Warmwasserbereitung
            'PumpenNachlauf':   {'read': True, 'write': True,  'opcode': '6762', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 2}, 'cmd_settings': {'force_min': 0, 'force_max': 1}},     # Warmwasserpumpennachlauf
        },
        'Ferienprogramm': {
            'A1M1': {
                # Ferienprogramm HK
                'Status':       {'read': True, 'write': False, 'opcode': '2535', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # Ferienprogramm A1M1
                'Abreisetag':   {'read': True, 'write': True,  'opcode': '2309', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'D', 'params': {'value': 'VAL', 'len': 8}},     # Ferien Abreisetag A1M1
                'Rückreisetag': {'read': True, 'write': True,  'opcode': '2311', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'D', 'params': {'value': 'VAL', 'len': 8}},     # Ferien Rückreisetag A1M1
            },
            'M2': {
                # Ferienprogramm HK
                'Status':       {'read': True, 'write': False, 'opcode': '3535', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # Ferienprogramm M2
                'Abreisetag':   {'read': True, 'write': True,  'opcode': '3309', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'D', 'params': {'value': 'VAL', 'len': 8}},     # Ferien Abreisetag M2
                'Rückreisetag': {'read': True, 'write': True,  'opcode': '3311', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'D', 'params': {'value': 'VAL', 'len': 8}},     # Ferien Rückreisetag M2
            },
        },
        'Timer': {
            'Warmwasser': {
                # Schaltzeiten Warmwasser
                'Mo': {'read': True, 'write': True, 'opcode': '2100', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Warmwasserbereitung Montag
                'Di': {'read': True, 'write': True, 'opcode': '2108', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Warmwasserbereitung Dienstag
                'Mi': {'read': True, 'write': True, 'opcode': '2110', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Warmwasserbereitung Mittwoch
                'Do': {'read': True, 'write': True, 'opcode': '2118', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Warmwasserbereitung Donnerstag
                'Fr': {'read': True, 'write': True, 'opcode': '2120', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Warmwasserbereitung Freitag
                'Sa': {'read': True, 'write': True, 'opcode': '2128', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Warmwasserbereitung Samstag
                'So': {'read': True, 'write': True, 'opcode': '2130', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Warmwasserbereitung Sonntag
            },
            'A1M1': {
                # Schaltzeiten HK
                'Mo': {'read': True, 'write': True, 'opcode': '2000', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Heizkreis Montag
                'Di': {'read': True, 'write': True, 'opcode': '2008', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Heizkreis Dienstag
                'Mi': {'read': True, 'write': True, 'opcode': '2010', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Heizkreis Mittwoch
                'Do': {'read': True, 'write': True, 'opcode': '2018', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Heizkreis Donnerstag
                'Fr': {'read': True, 'write': True, 'opcode': '2020', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Heizkreis Freitag
                'Sa': {'read': True, 'write': True, 'opcode': '2028', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Heizkreis Samstag
                'So': {'read': True, 'write': True, 'opcode': '2030', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Heizkreis Sonntag
            },
            'M2': {
                # Schaltzeiten HK
                'Mo': {'read': True, 'write': True, 'opcode': '3000', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Heizkreis Montag
                'Di': {'read': True, 'write': True, 'opcode': '3008', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Heizkreis Dienstag
                'Mi': {'read': True, 'write': True, 'opcode': '3010', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Heizkreis Mittwoch
                'Do': {'read': True, 'write': True, 'opcode': '3018', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Heizkreis Donnerstag
                'Fr': {'read': True, 'write': True, 'opcode': '3020', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Heizkreis Freitag
                'Sa': {'read': True, 'write': True, 'opcode': '3028', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Heizkreis Samstag
                'So': {'read': True, 'write': True, 'opcode': '3030', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Heizkreis Sonntag
            },
            'Zirkulation': {
                # Schaltzeiten Zirkulation
                'Mo': {'read': True, 'write': True, 'opcode': '2200', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Zirkulationspumpe Montag
                'Di': {'read': True, 'write': True, 'opcode': '2208', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Zirkulationspumpe Dienstag
                'Mi': {'read': True, 'write': True, 'opcode': '2210', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Zirkulationspumpe Mittwoch
                'Do': {'read': True, 'write': True, 'opcode': '2218', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Zirkulationspumpe Donnerstag
                'Fr': {'read': True, 'write': True, 'opcode': '2220', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Zirkulationspumpe Freitag
                'Sa': {'read': True, 'write': True, 'opcode': '2228', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Zirkulationspumpe Samstag
                'So': {'read': True, 'write': True, 'opcode': '2230', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Zirkulationspumpe Sonntag
            }
        }
    },
    'V200HO1C': {
        'Allgemein': {
            # Allgemein
            'Anlagenschema':        {'read': True, 'write': False, 'opcode': '7700', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 2}, 'lookup': 'systemschemes'},     # Anlagenschema
            'Frostgefahr':          {'read': True, 'write': False, 'opcode': '2510', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # Frostgefahr
            'Anlagenleistung':      {'read': True, 'write': False, 'opcode': 'a38f', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2}},     # Anlagenleistung
            'Temperatur': {
                'Aussen_TP':        {'read': True, 'write': False, 'opcode': '5525', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2}},     # Aussentemperatur_tiefpass
                'Aussen_Dp':        {'read': True, 'write': False, 'opcode': '5527', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2}},     # Aussentemperatur in Grad C (Gedaempft)
            },
        },
        'Kessel': {
            # Kessel
            'TP':                   {'read': True, 'write': False, 'opcode': '0810', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'len': 2}},     # Kesseltemperatur_tiefpass
            'Soll':                 {'read': True, 'write': False, 'opcode': '555a', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'len': 2}},     # Kesselsolltemperatur
            'Abgastemperatur':      {'read': True, 'write': False, 'opcode': '0816', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'len': 2}},     # Abgastemperatur
        },
        'Fehler': {
            # Fehler
            'Sammelstoerung':       {'read': True, 'write': False, 'opcode': '0a82', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'lookup': 'returnstatus'},     # Sammelstörung
            'Error0':               {'read': True, 'write': False, 'opcode': '7507', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 9}, 'lookup': 'errors'},     # Fehlerhistory Eintrag 1
            'Error1':               {'read': True, 'write': False, 'opcode': '7510', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 9}, 'lookup': 'errors'},     # Fehlerhistory Eintrag 2
            'Error2':               {'read': True, 'write': False, 'opcode': '7519', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 9}, 'lookup': 'errors'},     # Fehlerhistory Eintrag 3
            'Error3':               {'read': True, 'write': False, 'opcode': '7522', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 9}, 'lookup': 'errors'},     # Fehlerhistory Eintrag 4
            'Error4':               {'read': True, 'write': False, 'opcode': '752b', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 9}, 'lookup': 'errors'},     # Fehlerhistory Eintrag 5
            'Error5':               {'read': True, 'write': False, 'opcode': '7534', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 9}, 'lookup': 'errors'},     # Fehlerhistory Eintrag 6
            'Error6':               {'read': True, 'write': False, 'opcode': '753d', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 9}, 'lookup': 'errors'},     # Fehlerhistory Eintrag 7
            'Error7':               {'read': True, 'write': False, 'opcode': '7546', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 9}, 'lookup': 'errors'},     # Fehlerhistory Eintrag 8
            'Error8':               {'read': True, 'write': False, 'opcode': '754f', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 9}, 'lookup': 'errors'},     # Fehlerhistory Eintrag 9
            'Error9':               {'read': True, 'write': False, 'opcode': '7558', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 9}, 'lookup': 'errors'},     # Fehlerhistory Eintrag 10
        },
        'Pumpen': {
            # Pumpen
            'Speicherlade':         {'read': True, 'write': False, 'opcode': '6513', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # Speicherladepumpe für Warmwasser
            'Zirkulation':          {'read': True, 'write': True,  'opcode': '6515', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # Zirkulationspumpe
            'Intern':               {'read': True, 'write': False, 'opcode': '7660', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # Interne Pumpe
            'Heizkreis_1':          {'read': True, 'write': False, 'opcode': '2906', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # Heizkreispumpe A1
            'Heizkreis_2':          {'read': True, 'write': False, 'opcode': '3906', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # Heizkreispumpe M2
        },
        'Brenner': {
            # Brenner
            'Starts':               {'read': True, 'write': False, 'opcode': '088a', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 4}},     # Brennerstarts
            'Leistung':             {'read': True, 'write': False, 'opcode': 'a305', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2}},     # Brennerleistung
            'Betriebsstunden':      {'read': True, 'write': False, 'opcode': '08a7', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 3600, 'len': 4}},     # Brenner-Betriebsstunden
        },
        'Solar': {
            # Solar
            'Pumpe':                {'read': True, 'write': False, 'opcode': '6552', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # Solarpumpe
            'Kollektortemperatur':  {'read': True, 'write': False, 'opcode': '6564', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2}},     # Kollektortemperatur
            'Speichertemperatur':   {'read': True, 'write': False, 'opcode': '6566', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'len': 2}},     # Spichertemperatur
            'Betriebsstunden':      {'read': True, 'write': False, 'opcode': '6568', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 100, 'len': 4}},     # Solar Betriebsstunden
            'Waermemenge':          {'read': True, 'write': False, 'opcode': '6560', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 2}},     # Solar Waermemenge
            'Ausbeute':             {'read': True, 'write': False, 'opcode': 'cf30', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 4}},     # Solar Ausbeute
        },
        'Heizkreis': {
            '1': {
                # Heizkreis 1
                'Betriebsart':      {'read': True, 'write': True,  'opcode': '2500', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 3}},     # Betriebsart (0=Abschaltbetrieb, 1=Red. Betrieb, 2=Normalbetrieb (Schaltuhr), 3=Normalbetrieb (Dauernd))
                'Heizart':          {'read': True, 'write': True,  'opcode': '2323', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 4}},     # Heizart     (0=Abschaltbetrieb, 1=Nur Warmwasser, 2=Heizen und Warmwasser, 3=Normalbetrieb (Reduziert), 4=Normalbetrieb (Dauernd))
                'Temperatur': {
                    'Vorlauf_Soll': {'read': True, 'write': False, 'opcode': '2544', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'len': 2}},     # Vorlauftemperatur Soll
                    'Vorlauf_Ist':  {'read': True, 'write': False, 'opcode': '2900', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'len': 2}},     # Vorlauftemperatur Ist
                },
            },
            '2': {
                # Heizkreis 2
                'Betriebsart':      {'read': True, 'write': True,  'opcode': '3500', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 3}},     # Betriebsart (0=Abschaltbetrieb, 1=Red. Betrieb, 2=Normalbetrieb (Schaltuhr), 3=Normalbetrieb (Dauernd))
                'Heizart':          {'read': True, 'write': True,  'opcode': '3323', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 4}},     # Heizart     (0=Abschaltbetrieb, 1=Nur Warmwasser, 2=Heizen und Warmwasser, 3=Normalbetrieb (Reduziert), 4=Normalbetrieb (Dauernd))
                'Temperatur': {
                    'Vorlauf_Soll': {'read': True, 'write': False, 'opcode': '3544', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'len': 2}},     # Vorlauftemperatur Soll
                    'Vorlauf_Ist':  {'read': True, 'write': False, 'opcode': '3900', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'len': 2}},     # Vorlauftemperatur Ist
                },
            },
        },
        'Warmwasser': {
            # Warmwasser
            'Ist':                  {'read': True, 'write': False, 'opcode': '0812', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'len': 2}},     # Warmwassertemperatur in Grad C
            'Soll':                 {'read': True, 'write': True,  'opcode': '6300', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': 10, 'force_max': 80}},     # Warmwasser-Solltemperatur
            'Austritt':             {'read': True, 'write': False, 'opcode': '0814', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'len': 2}},     # Warmwasseraustrittstemperatur in Grad C
        },
    },
    'V200KW2': {
        'Allgemein': {
            # Allgemein
            'Temperatur': {
                'Aussen':                 {'read': True, 'write': False, 'opcode': '0800', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2}},     # Aussentemperatur_tiefpass
                'Aussen_Dp':              {'read': True, 'write': False, 'opcode': '5527', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2}},     # Aussentemperatur in Grad C (Gedaempft)
            },
            'Anlagenschema':              {'read': True, 'write': False, 'opcode': '7700', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 2}, 'lookup': 'systemschemes'},     # Anlagenschema
            'AnlagenSoftwareIndex':       {'read': True, 'write': False, 'opcode': '7330', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # Bedienteil SoftwareIndex
            'Systemtime':                 {'read': True, 'write': True,  'opcode': '088e', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'T', 'params': {'value': 'VAL', 'len': 8}},     # Systemzeit
        },
        'Kessel': {
            # Kessel
            'TempKOffset':                {'read': True, 'write': True,  'opcode': '6760', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'cmd_settings': {'force_min': 10, 'force_max': 50}},     # Kesseloffset KT ueber WWsoll in Grad C
            'Ist':                        {'read': True, 'write': False, 'opcode': '0802', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'len': 2}},     # Kesseltemperatur
            'Soll':                       {'read': True, 'write': True,  'opcode': '5502', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'len': 2}},     # Kesselsolltemperatur
        },
        'Fehler': {
            # Fehler
            'Sammelstoerung':             {'read': True, 'write': False, 'opcode': '0847', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'lookup': 'returnstatus'},     # Sammelstörung
            'Brennerstoerung':            {'read': True, 'write': False, 'opcode': '0883', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'lookup': 'returnstatus'},
            'Error0':                     {'read': True, 'write': False, 'opcode': '7507', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 9}, 'lookup': 'errors'},     # Fehlerhistory Eintrag 1
            'Error1':                     {'read': True, 'write': False, 'opcode': '7510', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 9}, 'lookup': 'errors'},     # Fehlerhistory Eintrag 2
            'Error2':                     {'read': True, 'write': False, 'opcode': '7519', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 9}, 'lookup': 'errors'},     # Fehlerhistory Eintrag 3
            'Error3':                     {'read': True, 'write': False, 'opcode': '7522', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 9}, 'lookup': 'errors'},     # Fehlerhistory Eintrag 4
            'Error4':                     {'read': True, 'write': False, 'opcode': '752b', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 9}, 'lookup': 'errors'},     # Fehlerhistory Eintrag 5
            'Error5':                     {'read': True, 'write': False, 'opcode': '7534', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 9}, 'lookup': 'errors'},     # Fehlerhistory Eintrag 6
            'Error6':                     {'read': True, 'write': False, 'opcode': '753d', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 9}, 'lookup': 'errors'},     # Fehlerhistory Eintrag 7
            'Error7':                     {'read': True, 'write': False, 'opcode': '7546', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 9}, 'lookup': 'errors'},     # Fehlerhistory Eintrag 8
            'Error8':                     {'read': True, 'write': False, 'opcode': '754f', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 9}, 'lookup': 'errors'},     # Fehlerhistory Eintrag 9
            'Error9':                     {'read': True, 'write': False, 'opcode': '7558', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 9}, 'lookup': 'errors'},     # Fehlerhistory Eintrag 10
        },
        'Pumpen': {
            # Pumpen
            'Speicherlade':               {'read': True, 'write': False, 'opcode': '0845', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # Speicherladepumpe für Warmwasser
            'Zirkulation':                {'read': True, 'write': False, 'opcode': '0846', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # Zirkulationspumpe
            'Heizkreis_A1M1':             {'read': True, 'write': False, 'opcode': '2906', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # Heizkreispumpe A1M1
            'Heizkreis_M2':               {'read': True, 'write': False, 'opcode': '3906', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # Heizkreispumpe M2
        },
        'Brenner': {
            # Brenner
            'Typ':                        {'read': True, 'write': False, 'opcode': 'a30b', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # Brennertyp 0=einstufig 1=zweistufig 2=modulierend
            'Stufe':                      {'read': True, 'write': False, 'opcode': '551e', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'lookup': 'returnstatus'},     # Ermittle die aktuelle Brennerstufe
            'Starts':                     {'read': True, 'write': True,  'opcode': '088a', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 2}, 'cmd_settings': {'force_min': 0, 'force_max': 1193045}},     # Brennerstarts
            'Status_1':                   {'read': True, 'write': False, 'opcode': '55d3', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # Brennerstatus Stufe1
            'Status_2':                   {'read': True, 'write': False, 'opcode': '0849', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # Brennerstatus Stufe2
            'BetriebsstundenStufe1':      {'read': True, 'write': True,  'opcode': '0886', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 3600, 'len': 4}, 'cmd_settings': {'force_min': 0, 'force_max': 1193045}},     # Brenner-Betriebsstunden Stufe 1
            'BetriebsstundenStufe2':      {'read': True, 'write': True,  'opcode': '08a3', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 3600, 'len': 4}, 'cmd_settings': {'force_min': 0, 'force_max': 1193045}},     # Brenner-Betriebsstunden Stufe 2
        },
        'Heizkreis': {
            'A1M1': {
                # Heizkreis A1M1
                'Temperatur': {
                    'Raum': {
                        'Soll_Normal':    {'read': True, 'write': True,  'opcode': '2306', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': 4, 'force_max': 37}},     # Raumtemperatur Soll Normalbetrieb A1M1
                        'Soll_Reduziert': {'read': True, 'write': True,  'opcode': '2307', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': 4, 'force_max': 37}},     # Raumtemperatur Soll Reduzierter Betrieb A1M1
                        'Soll_Party':     {'read': True, 'write': True,  'opcode': '2308', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': 4, 'force_max': 37}},     # Raumtemperatur Soll Party Betrieb A1M1
                    },
                    'Vorlauf': {
                        'Ist':            {'read': True, 'write': False, 'opcode': '2900', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'len': 2}},     # Vorlauftemperatur A1M1
                        'Soll':           {'read': True, 'write': False, 'opcode': '2544', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'len': 2}},     # Vorlauftemperatur Soll A1M1
                    },
                },
                'Betriebsart':            {'read': True, 'write': True,  'opcode': '2301', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'lookup': 'operatingmodes'},     # Betriebsart A1M1
                'Aktuelle_Betriebsart':   {'read': True, 'write': False, 'opcode': '2500', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'lookup': 'operatingmodes'},     # Aktuelle Betriebsart A1M1
                'Sparbetrieb':            {'read': True, 'write': True,  'opcode': '2302', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 1}},     # Sparbetrieb A1M1
                'Partybetrieb_Zeit':      {'read': True, 'write': True,  'opcode': '27f2', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 12}},     # Partyzeit M2
                'Partybetrieb':           {'read': True, 'write': True,  'opcode': '2303', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 1}},     # Partybetrieb A1M1
                'MischerM1':              {'read': True, 'write': False, 'opcode': '254c', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 2.55, 'len': 1}},     # Ermittle Mischerposition M1
                'Heizkreispumpenlogik':   {'read': True, 'write': True,  'opcode': '27a5', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 15}},     # 0=ohne HPL-Funktion, 1=AT > RTsoll + 5 K, 2=AT > RTsoll + 4 K, 3=AT > RTsoll + 3 K, 4=AT > RTsoll + 2 K, 5=AT > RTsoll + 1 K, 6=AT > RTsoll, 7=AT > RTsoll - 1 K, 8=AT > RTsoll - 2 K, 9=AT > RTsoll - 3 K, 10=AT > RTsoll - 4 K, 11=AT > RTsoll - 5 K, 12=AT > RTsoll - 6 K, 13=AT > RTsoll - 7 K, 14=AT > RTsoll - 8 K, 15=AT > RTsoll - 9 K
                'Sparschaltung':          {'read': True, 'write': True,  'opcode': '27a6', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': 5, 'force_max': 36}},     # AbsolutSommersparschaltung
                'Heizkennlinie': {
                    'Neigung':            {'read': True, 'write': True,  'opcode': '2305', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'len': 1}, 'cmd_settings': {'force_min': 0.2, 'force_max': 3.5}},     # Neigung Heizkennlinie A1M1
                    'Niveau':             {'read': True, 'write': True,  'opcode': '2304', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': -13, 'force_max': 40}},     # Niveau Heizkennlinie A1M1
                },
            },
            'M2': {
                # Heizkreis M2
                'Temperatur': {
                    'Raum': {
                        'Soll_Normal':    {'read': True, 'write': True,  'opcode': '3306', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': 4, 'force_max': 37}},     # Raumtemperatur Soll Normalbetrieb
                        'Soll_Reduziert': {'read': True, 'write': True,  'opcode': '3307', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': 4, 'force_max': 37}},     # Raumtemperatur Soll Reduzierter Betrieb
                        'Soll_Party':     {'read': True, 'write': True,  'opcode': '3308', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': 4, 'force_max': 37}},     # Raumtemperatur Soll Party Betrieb
                    },
                    'Vorlauf': {
                        'Soll':           {'read': True, 'write': True,  'opcode': '37c6', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'len': 2}, 'cmd_settings': {'force_min': 10, 'force_max': 80}},     # Vorlauftemperatur Soll
                        'Ist':            {'read': True, 'write': False, 'opcode': '080c', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'len': 2}},     # Vorlauftemperatur Ist
                        'Min':            {'read': True, 'write': True,  'opcode': '37c5', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': 1, 'force_max': 127}},     # Minimalbegrenzung der Vorlauftemperatur
                        'Max':            {'read': True, 'write': True,  'opcode': '37c6', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': 1, 'force_max': 127}},     # Maximalbegrenzung der Vorlauftemperatur
                    },
                },
                'Betriebsart':            {'read': True, 'write': True,  'opcode': '3301', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'lookup': 'operatingmodes'},     # Betriebsart M2
                'Aktuelle_Betriebsart':   {'read': True, 'write': False, 'opcode': '3500', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'lookup': 'operatingmodes'},     # Aktuelle Betriebsart M2
                'Sparbetrieb':            {'read': True, 'write': True,  'opcode': '3302', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 1}},     # Sparbetrieb
                'Partybetrieb':           {'read': True, 'write': True,  'opcode': '3303', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 1}},     # Partybetrieb A1M1
                'Partybetrieb_Zeit':      {'read': True, 'write': True,  'opcode': '37f2', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 12}},     # Partyzeit M2
                'MischerM2':              {'read': True, 'write': False, 'opcode': '354c', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 2.55, 'len': 1}},     # Ermittle Mischerposition M2
                'MischerM2Auf':           {'read': True, 'write': True,  'opcode': '084d', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 1}},     # MischerM2 Auf 0=AUS;1=EIN
                'MischerM2Zu':            {'read': True, 'write': True,  'opcode': '084c', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 1}},     # MischerM2 Zu 0=AUS;1=EIN
                'Heizkreispumpenlogik':   {'read': True, 'write': True,  'opcode': '37a5', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 15}},     # 0=ohne HPL-Funktion, 1=AT > RTsoll + 5 K, 2=AT > RTsoll + 4 K, 3=AT > RTsoll + 3 K, 4=AT > RTsoll + 2 K, 5=AT > RTsoll + 1 K, 6=AT > RTsoll, 7=AT > RTsoll - 1 K, 8=AT > RTsoll - 2 K, 9=AT > RTsoll - 3 K, 10=AT > RTsoll - 4 K, 11=AT > RTsoll - 5 K, 12=AT > RTsoll - 6 K, 13=AT > RTsoll - 7 K, 14=AT > RTsoll - 8 K, 15=AT > RTsoll - 9 K
                'Sparschaltung':          {'read': True, 'write': True,  'opcode': '37a6', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': 5, 'force_max': 36}},     # AbsolutSommersparschaltung
                'StatusKlemme2':          {'read': True, 'write': False, 'opcode': '3904', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # 0=OK, 1=Kurzschluss, 2=nicht vorhanden, 3-5=Referenzfehler, 6=nicht vorhanden
                'StatusKlemme17':         {'read': True, 'write': False, 'opcode': '3905', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # 0=OK, 1=Kurzschluss, 2=nicht vorhanden, 3-5=Referenzfehler, 6=nicht vorhanden
                'Heizkennlinie': {
                    'Neigung':            {'read': True, 'write': True,  'opcode': '3305', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'len': 1}, 'cmd_settings': {'force_min': 0.2, 'force_max': 3.5}},     # Neigung Heizkennlinie M2
                    'Niveau':             {'read': True, 'write': True,  'opcode': '3304', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': -13, 'force_max': 40}},     # Niveau Heizkennlinie M2
                },
            },
        },
        'Warmwasser': {
            # Warmwasser
            'Status':           {'read': True, 'write': False, 'opcode': '650A', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # 0=Ladung inaktiv, 1=in Ladung, 2=im Nachlauf
            'KesselOffset':     {'read': True, 'write': True,  'opcode': '6760', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'cmd_settings': {'force_min': 10, 'force_max': 50}},     # Warmwasser Kessel Offset in K
            'BeiPartyDNormal':  {'read': True, 'write': True,  'opcode': '6764', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 2}},     # WW Heizen bei Party 0=AUS, 1=nach Schaltuhr, 2=EIN
            'Ist':              {'read': True, 'write': False, 'opcode': '0804', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'len': 2}},     # Warmwassertemperatur in Grad C
            'Soll':             {'read': True, 'write': True,  'opcode': '6300', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'signed': True, 'len': 1}, 'cmd_settings': {'force_min': 10, 'force_max': 80}},     # Warmwasser-Solltemperatur
            'SollAktuell':      {'read': True, 'write': False, 'opcode': '6500', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'len': 1}},      # Warmwasser-Solltemperatur aktuell
            'SollMax':          {'read': True, 'write': False, 'opcode': '675a', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # 0=inaktiv, 1=aktiv
        },
        'Ferienprogramm': {
            'A1M1': {
                # Ferienprogramm HK
                'Status':       {'read': True, 'write': False, 'opcode': '2535', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # Ferienprogramm A1M1 0=inaktiv 1=aktiv
                'Abreisetag':   {'read': True, 'write': True,  'opcode': '2309', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'D', 'params': {'value': 'VAL', 'len': 8}},     # Ferien Abreisetag A1M1
                'Rückreisetag': {'read': True, 'write': True,  'opcode': '2311', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'D', 'params': {'value': 'VAL', 'len': 8}},     # Ferien Rückreisetag A1M1
            },
            'M2': {
                # Ferienprogramm HK
                'Status':       {'read': True, 'write': False, 'opcode': '3535', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # Ferienprogramm M2 0=inaktiv 1=aktiv
                'Abreisetag':   {'read': True, 'write': True,  'opcode': '3309', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'D', 'params': {'value': 'VAL', 'len': 8}},     # Ferien Abreisetag M2
                'Rückreisetag': {'read': True, 'write': True,  'opcode': '3311', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'D', 'params': {'value': 'VAL', 'len': 8}},     # Ferien Rückreisetag M2
            },
        },
        'Timer': {
            'Warmwasser': {
                # Schaltzeiten Warmwasser
                'Mo': {'read': True, 'write': True, 'opcode': '2100', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Warmwasserbereitung Montag
                'Di': {'read': True, 'write': True, 'opcode': '2108', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Warmwasserbereitung Dienstag
                'Mi': {'read': True, 'write': True, 'opcode': '2110', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Warmwasserbereitung Mittwoch
                'Do': {'read': True, 'write': True, 'opcode': '2118', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Warmwasserbereitung Donnerstag
                'Fr': {'read': True, 'write': True, 'opcode': '2120', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Warmwasserbereitung Freitag
                'Sa': {'read': True, 'write': True, 'opcode': '2128', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Warmwasserbereitung Samstag
                'So': {'read': True, 'write': True, 'opcode': '2130', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Warmwasserbereitung Sonntag
            },
            'A1M1': {
                # Schaltzeiten HK
                'Mo': {'read': True, 'write': True, 'opcode': '2000', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Heizkreis Montag
                'Di': {'read': True, 'write': True, 'opcode': '2008', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Heizkreis Dienstag
                'Mi': {'read': True, 'write': True, 'opcode': '2010', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Heizkreis Mittwoch
                'Do': {'read': True, 'write': True, 'opcode': '2018', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Heizkreis Donnerstag
                'Fr': {'read': True, 'write': True, 'opcode': '2020', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Heizkreis Freitag
                'Sa': {'read': True, 'write': True, 'opcode': '2028', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Heizkreis Samstag
                'So': {'read': True, 'write': True, 'opcode': '2030', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Heizkreis Sonntag
            },
            'M2': {
                # Schaltzeiten HK
                'Mo': {'read': True, 'write': True, 'opcode': '3000', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Heizkreis Montag
                'Di': {'read': True, 'write': True, 'opcode': '3008', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Heizkreis Dienstag
                'Mi': {'read': True, 'write': True, 'opcode': '3010', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Heizkreis Mittwoch
                'Do': {'read': True, 'write': True, 'opcode': '3018', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Heizkreis Donnerstag
                'Fr': {'read': True, 'write': True, 'opcode': '3020', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Heizkreis Freitag
                'Sa': {'read': True, 'write': True, 'opcode': '3028', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Heizkreis Samstag
                'So': {'read': True, 'write': True, 'opcode': '3030', 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'C', 'params': {'value': 'VAL', 'len': 8}},     # Timer Heizkreis Sonntag
            },
        },
    },
    'V200WO1C': {
        'Allgemein': {'item_attrs': {'cycle': 45},
            'Temperatur': {
                'Aussen':             {'read': True, 'write': False, 'opcode': '0101', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2}},     # getTempA -- Information - Allgemein: Aussentemperatur (-40..70)
            },
            # Anlagenstatus
            'Betriebsart':            {'read': True, 'write': True,  'opcode': 'b000', 'reply_pattern': '*', 'item_type': 'str',  'dev_datatype': 'H', 'params': {'value': 'VAL', 'len': 1}, 'lookup': 'operatingmodes', 'item_attrs': {'attributes': {'md_read_initial': True}, 'lookup_item': True}},     # getBetriebsart -- Bedienung HK1 - Heizkreis 1: Betriebsart (Textstring)
            'Manuell':                {'read': True, 'write': True,  'opcode': 'b020', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'cmd_settings': {'force_min': 0, 'force_max': 2}},     # getManuell / setManuell -- 0 = normal, 1 = manueller Heizbetrieb, 2 = 1x Warmwasser auf Temp2
            # Allgemein
            'Outdoor_Fanspeed':       {'read': True, 'write': False, 'opcode': '1a52', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # getSpdFanOut -- Outdoor Fanspeed
            'Status_Fanspeed':        {'read': True, 'write': False, 'opcode': '1a53', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # getSpdFan -- Geschwindigkeit Luefter
            'Kompressor_Freq':        {'read': True, 'write': False, 'opcode': '1a54', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # getSpdKomp -- Compressor Frequency
            'SollLeistungVerdichter': {'read': True, 'write': False, 'opcode': '5030', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # getPwrSollVerdichter -- Diagnose - Anlagenuebersicht: Soll-Leistung Verdichter 1 (0..100)
        },
        'Pumpen': {
            'Sekundaer':              {'read': True, 'write': False, 'opcode': '0484', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'lookup': 'returnstatus'},     # getStatusSekP -- Diagnose - Anlagenuebersicht: Sekundaerpumpe 1 (0..1)
            'Heizkreis':              {'read': True, 'write': False, 'opcode': '048d', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'lookup': 'returnstatus'},     # getStatusPumpe -- Information - Heizkreis HK1: Heizkreispumpe (0..1)
            'Zirkulation':            {'read': True, 'write': False, 'opcode': '0490', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'lookup': 'returnstatus'},     # getStatusPumpeZirk -- Information - Warmwasser: Zirkulationspumpe (0..1)
        },
        'Heizkreis': {
            'Temperatur': {
                'Raum': {
                    'Soll':           {'read': True, 'write': False, 'opcode': '2000', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2}},     # getTempRaumSollNormal -- Bedienung HK1 - Heizkreis 1: Raumsolltemperatur normal (10..30)
                    'Soll_Reduziert': {'read': True, 'write': False, 'opcode': '2001', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2}},     # getTempRaumSollRed -- Bedienung HK1 - Heizkreis 1: Raumsolltemperatur reduzierter Betrieb (10..30)
                    'Soll_Party':     {'read': True, 'write': False, 'opcode': '2022', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2}},     # getTempRaumSollParty -- Bedienung HK1 - Heizkreis 1: Party Solltemperatur (10..30)
                },
                'Vorlauf': {
                    'Ist':            {'read': True, 'write': False, 'opcode': '0105', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2}},     # getTempSekVL -- Information - Heizkreis HK1: Vorlauftemperatur Sekundaer 1 (0..95)
                    'Soll':           {'read': True, 'write': False, 'opcode': '1800', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2}},     # getTempVLSoll -- Diagnose - Heizkreis HK1: Vorlaufsolltemperatur HK1 (0..95)
                    'Mittel':         {'read': True, 'write': False, 'opcode': '16b2', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2}},     # getTempSekVLMittel -- Statistik - Energiebilanz: mittlere sek. Vorlauftemperatur (0..95)
                },
                'Ruecklauf': {
                    'Ist':            {'read': True, 'write': False, 'opcode': '0106', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2}},     # getTempSekRL -- Diagnose - Anlagenuebersicht: Ruecklauftemperatur Sekundaer 1 (0..95)
                    'Mittel':         {'read': True, 'write': False, 'opcode': '16b3', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2}},     # getTempSekRLMittel -- Statistik - Energiebilanz: mittlere sek.Temperatur RL1 (0..95)
                },
            },
            'Heizkennlinie': {
                'Niveau':             {'read': True, 'write': False, 'opcode': '2006', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2}},     # getHKLNiveau -- Bedienung HK1 - Heizkreis 1: Niveau der Heizkennlinie (-15..40)
                'Neigung':            {'read': True, 'write': False, 'opcode': '2007', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2}},     # getHKLNeigung -- Bedienung HK1 - Heizkreis 1: Neigung der Heizkennlinie (0..35)
            },
        },
        'Warmwasser': {
            'Ist':                    {'read': True, 'write': False, 'opcode': '010d', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2}},     # getTempWWIstOben -- Information - Warmwasser: Warmwassertemperatur oben (0..95)
            'Soll':                   {'read': True, 'write': True,  'opcode': '6000', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2}, 'cmd_settings': {'force_min': 10, 'force_max': 60}},     # getTempWWSoll -- Bedienung WW - Betriebsdaten WW: Warmwassersolltemperatur (10..60 (95))
            'Ventil':                 {'read': True, 'write': False, 'opcode': '0494', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}, 'lookup': 'returnstatus'},     # getStatusVentilWW -- Diagnose - Waermepumpe: 3-W-Ventil Heizen WW1 (0 (Heizen)..1 (WW))
        },
        'Statistik': {
            # Statistiken / Laufzeiten
            'Einschaltungen': {
                'Sekundaer':          {'read': True, 'write': False, 'opcode': '0504', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 4}},     # getAnzQuelleSek -- Statistik - Schaltzyklen Anlage: Einschaltungen Sekundaerquelle (?)
                'Heizstab1':          {'read': True, 'write': False, 'opcode': '0508', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 4}},     # getAnzHeizstabSt1 -- Statistik - Schaltzyklen Anlage: Einschaltungen Heizstab Stufe 1 (?)
                'Heizstab2':          {'read': True, 'write': False, 'opcode': '0509', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 4}},     # getAnzHeizstabSt2 -- Statistik - Schaltzyklen Anlage: Einschaltungen Heizstab Stufe 2 (?)
                'HK':                 {'read': True, 'write': False, 'opcode': '050d', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 4}},     # getAnzHK -- Statistik - Schaltzyklen Anlage: Einschaltungen Heizkreis (?)
            },
            'Laufzeiten': {
                'Sekundaerpumpe':     {'read': True, 'write': False, 'opcode': '0584', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 3600, 'len': 4}},     # getLZPumpeSek -- Statistik - Betriebsstunden Anlage: Betriebsstunden Sekundaerpumpe (?)
                'Heizstab1':          {'read': True, 'write': False, 'opcode': '0588', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 3600, 'len': 4}},     # getLZHeizstabSt1 -- Statistik - Betriebsstunden Anlage: Betriebsstunden Heizstab Stufe 1 (?)
                'Heizstab2':          {'read': True, 'write': False, 'opcode': '0589', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 3600, 'len': 4}},     # getLZHeizstabSt2 -- Statistik - Betriebsstunden Anlage: Betriebsstunden Heizstab Stufe 2 (?)
                'PumpeHK':            {'read': True, 'write': False, 'opcode': '058d', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 3600, 'len': 4}},     # getLZPumpe -- Statistik - Betriebsstunden Anlage: Betriebsstunden Pumpe HK1 (0..1150000)
                'WWVentil':           {'read': True, 'write': False, 'opcode': '0594', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 3600, 'len': 4}},     # getLZVentilWW -- Statistik - Betriebsstunden Anlage: Betriebsstunden Warmwasserventil (?)
                'VerdichterStufe1':   {'read': True, 'write': False, 'opcode': '1620', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 4}},     # getLZVerdSt1 -- Statistik - Betriebsstunden Anlage: Betriebsstunden Verdichter auf Stufe 1 (?)
                'VerdichterStufe2':   {'read': True, 'write': False, 'opcode': '1622', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 4}},     # getLZVerdSt2 -- Statistik - Betriebsstunden Anlage: Betriebsstunden Verdichter auf Stufe 2 (?)
                'VerdichterStufe3':   {'read': True, 'write': False, 'opcode': '1624', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 4}},     # getLZVerdSt3 -- Statistik - Betriebsstunden Anlage: Betriebsstunden Verdichter auf Stufe 3 (?)
                'VerdichterStufe4':   {'read': True, 'write': False, 'opcode': '1626', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 4}},     # getLZVerdSt4 -- Statistik - Betriebsstunden Anlage: Betriebsstunden Verdichter auf Stufe 4 (?)
                'VerdichterStufe5':   {'read': True, 'write': False, 'opcode': '1628', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 4}},     # getLZVerdSt5 -- Statistik - Betriebsstunden Anlage: Betriebsstunden Verdichter auf Stufe 5 (?)
                'VerdichterWP':       {'read': True, 'write': False, 'opcode': '5005', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 3600, 'len': 4}},     # getLZWP -- Statistik - Betriebsstunden Anlage: Betriebsstunden Waermepumpe  (0..1150000)
            },
            'OAT_Temperature':        {'read': True, 'write': False, 'opcode': '1a5c', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # getTempOAT -- OAT Temperature
            'ICT_Temperature':        {'read': True, 'write': False, 'opcode': '1a5d', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # getTempICT -- OCT Temperature
            'CCT_Temperature':        {'read': True, 'write': False, 'opcode': '1a5e', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # getTempCCT -- CCT Temperature
            'HST_Temperature':        {'read': True, 'write': False, 'opcode': '1a5f', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # getTempHST -- HST Temperature
            'OMT_Temperature':        {'read': True, 'write': False, 'opcode': '1a60', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'len': 1}},     # getTempOMT -- OMT Temperature
            'WaermeWW12M':            {'read': True, 'write': False, 'opcode': '1660', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'len': 4}},     # Wärmeenergie für WW-Bereitung der letzten 12 Monate (kWh)
            'ElektroWW12M':           {'read': True, 'write': False, 'opcode': '1670', 'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'V', 'params': {'value': 'VAL', 'mult': 10, 'len': 4}},     # elektr. Energie für WW-Bereitung der letzten 12 Monate (kWh)
        }
    }
}

lookups = {
    'ALL': {
        'devicetypes': {
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
        },
        'errors': {
            '00': 'Regelbetrieb (kein Fehler)',
            '0F': 'Wartung (fuer Reset Codieradresse 24 auf 0 stellen)',
            '10': 'Kurzschluss Aussentemperatursensor',
            '18': 'Unterbrechung Aussentemperatursensor',
            '19': 'Unterbrechung Kommunikation Aussentemperatursensor RF',
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
            'V': 'Kommunikationsfehler Erweiterungssatz fuer Mischerkreis M2',
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
            'D': 'Kurzschluss Raumtemperatursensor, Heizkreis M1',
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
        'operatingmodes': {
            '00': 'Abschaltbetrieb',
            '01': 'Reduzierter Betrieb',
            '02': 'Normalbetrieb',
            '03': 'Dauernd Normalbetrieb'
        },
        'returnstatus': {
            '00': '0',
            '01': '1',
            '03': '2',
            'AA': 'NOT OK',
        },
        'setreturnstatus': {
            '00': 'OK',
            '05': 'SYNC (NOT OK)',
        }
    },
    'V200KW2': {
        'operatingmodes': {
            '00': 'Warmwasser (Schaltzeiten)',
            '01': 'reduziert Heizen (dauernd)',
            '02': 'normal Heizen (dauernd)',
            '04': 'Heizen und Warmwasser (FS)',
            '03': 'Heizen und Warmwasser (Schaltzeiten)',
            '05': 'Standby'
        },
        'systemschemes': {
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
    },
    'V200KO1B': {
        'operatingmodes': {
            '00': 'Warmwasser (Schaltzeiten)',
            '01': 'reduziert Heizen (dauernd)',
            '02': 'normal Heizen (dauernd)',
            '04': 'Heizen und Warmwasser (FS)',
            '03': 'Heizen und Warmwasser (Schaltzeiten)',
            '05': 'Standby'
        },
        'systemschemes': {
            '01': 'A1',
            '02': 'A1 + WW',
            '04': 'M2',
            '03': 'M2 + WW',
            '05': 'A1 + M2',
            '06': 'A1 + M2 + WW'
        }
    },
    'V200WO1C': {
        'operatingmodes': {
            '00': 'Abschaltbetrieb',
            '01': 'Warmwasser',
            '02': 'Heizen und Warmwasser',
            '03': 'undefiniert',
            '04': 'dauernd reduziert',
            '05': 'dauernd normal',
            '06': 'normal Abschalt',
            '07': 'nur kühlen'
        },
        'systemschemes': {
            '01': 'WW',
            '02': 'HK + WW',
            '04': 'HK + WW',
            '05': 'HK + WW'
        },
    },
    'V200HO1C': {
        'operatingmodes': {
            '00': 'Abschaltbetrieb',
            '01': 'Warmwasser',
            '02': 'Heizen und Warmwasser',
            '03': 'Normal reduziert',
            '04': 'Normal dauernd'
        },
        'systemschemes': {
            '01': 'WW',
            '02': 'HK + WW',
            '04': 'HK + WW',
            '05': 'HK + WW'
        }
    }
}
