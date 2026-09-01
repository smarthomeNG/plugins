#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab

"""commands/lookups for Viessmann model V200KO1B"""

MODEL = 'V200KO1B'

commands = {
    'Allgemein': {
        'Temperatur': {
            'Aussen': {
                'read': True,
                'write': False,
                'opcode': '0800',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2},
            },  # Aussentemperatur
            'Aussen_TP': {
                'read': True,
                'write': False,
                'opcode': '5525',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2},
            },  # Aussentemperatur_tiefpass
            'Aussen_Dp': {
                'read': True,
                'write': False,
                'opcode': '5527',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2},
            },  # Aussentemperatur in Grad C (Gedaempft)
            'Speicher_Ladesensor': {
                'read': True,
                'write': False,
                'opcode': '0812',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'mult': 10, 'len': 2},
            },  # Temperatur Speicher Ladesensor Komfortsensor
            'Auslauf': {
                'read': True,
                'write': False,
                'opcode': '0814',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'mult': 10, 'len': 2},
            },  # Auslauftemperatur
            'Abgas': {
                'read': True,
                'write': False,
                'opcode': '0816',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'mult': 10, 'len': 2},
            },  # Abgastemperatur
            'Gem_Vorlauf': {
                'read': True,
                'write': False,
                'opcode': '081a',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'mult': 10, 'len': 2},
            },  # Gem. Vorlauftemperatur
        },
        'Relais_K12': {
            'read': True,
            'write': False,
            'opcode': '0842',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # Relais K12 Interne Anschlußerweiterung
        'Eingang_0-10_V': {
            'read': True,
            'write': False,
            'opcode': '0a86',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # Eingang 0-10 V
        'EA1_Kontakt_0': {
            'read': True,
            'write': False,
            'opcode': '0a90',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # EA1: Kontakt 0
        'EA1_Kontakt_1': {
            'read': True,
            'write': False,
            'opcode': '0a91',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # EA1: Kontakt 1
        'EA1_Kontakt_2': {
            'read': True,
            'write': False,
            'opcode': '0a92',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # EA1: Kontakt 2
        'EA1_Externer_Soll_0-10V': {
            'read': True,
            'write': False,
            'opcode': '0a93',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # EA1: Externer Sollwert 0-10V
        'EA1_Relais_0': {
            'read': True,
            'write': False,
            'opcode': '0a95',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # EA1: Relais 0
        'AM1_Ausgang_1': {
            'read': True,
            'write': False,
            'opcode': '0aa0',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # AM1 Ausgang 1
        'AM1_Ausgang_2': {
            'read': True,
            'write': False,
            'opcode': '0aa1',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # AM1 Ausgang 2
        'TempKOffset': {
            'read': True,
            'write': True,
            'opcode': '6760',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'signed': True, 'len': 1},
            'cmd_settings': {'force_min': 0, 'force_max': 1193045},
        },  # Kesseloffset KT ueber WWsoll in Grad C
        'Systemtime': {
            'read': True,
            'write': True,
            'opcode': '088e',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Time',
            'params': {'value': 'VAL', 'len': 8},
        },  # Systemzeit
        'Anlagenschema': {
            'read': True,
            'write': False,
            'opcode': '7700',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 2},
            'lookup': 'systemschemes',
        },  # Anlagenschema
        'Inventory': {
            'read': True,
            'write': False,
            'opcode': '08e0',
            'reply_pattern': '*',
            'item_type': 'str',
            'dev_datatype': 'Serial',
            'params': {'value': 'VAL', 'len': 7},
        },  # Sachnummer
        'CtrlId': {
            'read': True,
            'write': False,
            'opcode': '08e0',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 7},
            'lookup': 'devicetypes',
        },  # Reglerkennung
    },
    'Kessel': {
        # Kessel
        'Ist': {
            'read': True,
            'write': False,
            'opcode': '0802',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'mult': 10, 'len': 2},
        },  # Kesseltemperatur
        'TP': {
            'read': True,
            'write': False,
            'opcode': '0810',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'mult': 10, 'len': 2},
        },  # Kesseltemperatur_tiefpass
        'Soll': {
            'read': True,
            'write': False,
            'opcode': '555a',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'mult': 10, 'len': 2},
        },  # Kesselsolltemperatur
    },
    'Fehler': {
        # Fehler
        'Sammelstoerung': {
            'read': True,
            'write': False,
            'opcode': '0a82',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
            'lookup': 'returnstatus',
        },  # Sammelstörung
        'Error0': {
            'read': True,
            'write': False,
            'opcode': '7507',
            'reply_pattern': '*',
            'item_type': 'str',
            'dev_datatype': 'ErrorHistory',
            'params': {'value': 'VAL', 'len': 9},
        },  # Fehlerhistory Eintrag 1
        'Error1': {
            'read': True,
            'write': False,
            'opcode': '7510',
            'reply_pattern': '*',
            'item_type': 'str',
            'dev_datatype': 'ErrorHistory',
            'params': {'value': 'VAL', 'len': 9},
        },  # Fehlerhistory Eintrag 2
        'Error2': {
            'read': True,
            'write': False,
            'opcode': '7519',
            'reply_pattern': '*',
            'item_type': 'str',
            'dev_datatype': 'ErrorHistory',
            'params': {'value': 'VAL', 'len': 9},
        },  # Fehlerhistory Eintrag 3
        'Error3': {
            'read': True,
            'write': False,
            'opcode': '7522',
            'reply_pattern': '*',
            'item_type': 'str',
            'dev_datatype': 'ErrorHistory',
            'params': {'value': 'VAL', 'len': 9},
        },  # Fehlerhistory Eintrag 4
        'Error4': {
            'read': True,
            'write': False,
            'opcode': '752b',
            'reply_pattern': '*',
            'item_type': 'str',
            'dev_datatype': 'ErrorHistory',
            'params': {'value': 'VAL', 'len': 9},
        },  # Fehlerhistory Eintrag 5
        'Error5': {
            'read': True,
            'write': False,
            'opcode': '7534',
            'reply_pattern': '*',
            'item_type': 'str',
            'dev_datatype': 'ErrorHistory',
            'params': {'value': 'VAL', 'len': 9},
        },  # Fehlerhistory Eintrag 6
        'Error6': {
            'read': True,
            'write': False,
            'opcode': '753d',
            'reply_pattern': '*',
            'item_type': 'str',
            'dev_datatype': 'ErrorHistory',
            'params': {'value': 'VAL', 'len': 9},
        },  # Fehlerhistory Eintrag 7
        'Error7': {
            'read': True,
            'write': False,
            'opcode': '7546',
            'reply_pattern': '*',
            'item_type': 'str',
            'dev_datatype': 'ErrorHistory',
            'params': {'value': 'VAL', 'len': 9},
        },  # Fehlerhistory Eintrag 8
        'Error8': {
            'read': True,
            'write': False,
            'opcode': '754f',
            'reply_pattern': '*',
            'item_type': 'str',
            'dev_datatype': 'ErrorHistory',
            'params': {'value': 'VAL', 'len': 9},
        },  # Fehlerhistory Eintrag 9
        'Error9': {
            'read': True,
            'write': False,
            'opcode': '7558',
            'reply_pattern': '*',
            'item_type': 'str',
            'dev_datatype': 'ErrorHistory',
            'params': {'value': 'VAL', 'len': 9},
        },  # Fehlerhistory Eintrag 10
    },
    'Pumpen': {
        # Pumpen
        'Speicherlade': {
            'read': True,
            'write': False,
            'opcode': '6513',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # Speicherladepumpe
        'Zirkulation': {
            'read': True,
            'write': False,
            'opcode': '6515',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # Zirkulationspumpe
        'Intern': {
            'read': True,
            'write': False,
            'opcode': '7660',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # Interne Pumpe
        'Heizkreis_A1M1': {
            'read': True,
            'write': False,
            'opcode': '2906',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # Heizkreispumpe A1
        'Heizkreis_A1M1_RPM': {
            'read': True,
            'write': False,
            'opcode': '7663',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # Heizkreispumpe A1M1 Drehzahl
        'Heizkreis_M2': {
            'read': True,
            'write': False,
            'opcode': '3906',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # Heizkreispumpe M2
        'Heizkreis_M2_RPM': {
            'read': True,
            'write': False,
            'opcode': '7665',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # Heizkreispumpe M2 Drehzahl
        'Relais_Status': {
            'read': True,
            'write': False,
            'opcode': 'a152',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # Relais-Status Heizkreispumpe 1
    },
    'Brenner': {
        # Brenner
        'Starts': {
            'read': True,
            'write': True,
            'opcode': '088a',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'signed': True, 'len': 4},
            'cmd_settings': {'force_min': 0, 'force_max': 1193045},
        },  # Brennerstarts
        'Betriebsstunden': {
            'read': True,
            'write': True,
            'opcode': '08a7',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'mult': 3600, 'len': 4},
            'cmd_settings': {'force_min': 0, 'force_max': 1193045},
        },  # Brenner-Betriebsstunden
        'Status_1': {
            'read': True,
            'write': False,
            'opcode': '0842',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # Brennerstatus Stufe1
        'Status_2': {
            'read': True,
            'write': False,
            'opcode': '0849',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # Brennerstatus Stufe2
        'Oeldurchsatz': {
            'read': True,
            'write': True,
            'opcode': '5726',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'signed': True, 'len': 4},
            'cmd_settings': {'force_min': 0, 'force_max': 1193045},
        },  # Oeldurchsatz Brenner in Dezi-Liter pro Stunde
        'Oelverbrauch': {
            'read': True,
            'write': True,
            'opcode': '7574',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'mult': 1000, 'signed': True, 'len': 4},
        },  # Oelverbrauch kumuliert
    },
    'Solar': {
        # Solar
        'Nachladeunterdrueckung': {
            'read': True,
            'write': False,
            'opcode': '6551',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },
        'Pumpe': {
            'read': True,
            'write': False,
            'opcode': '6552',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },
        'Kollektortemperatur': {
            'read': True,
            'write': False,
            'opcode': '6564',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2},
        },
        'Speichertemperatur': {
            'read': True,
            'write': False,
            'opcode': '6566',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'mult': 10, 'len': 2},
        },
        'Betriebsstunden': {
            'read': True,
            'write': False,
            'opcode': '6568',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'mult': 100, 'len': 4},
        },
        'Steuerung': {
            'read': True,
            'write': False,
            'opcode': '7754',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 2},
        },
    },
    'Heizkreis': {
        'A1M1': {
            # Heizkreis A1M1
            'Temperatur': {
                'Raum': {
                    'Ist': {
                        'read': True,
                        'write': False,
                        'opcode': '0896',
                        'reply_pattern': '*',
                        'item_type': 'num',
                        'dev_datatype': 'Number',
                        'params': {'value': 'VAL', 'signed': True, 'len': 1},
                    },  # Raumtemperatur A1M1
                    'Soll_Normalbetrieb': {
                        'read': True,
                        'write': True,
                        'opcode': '2306',
                        'reply_pattern': '*',
                        'item_type': 'num',
                        'dev_datatype': 'Number',
                        'params': {'value': 'VAL', 'signed': True, 'len': 1},
                        'cmd_settings': {'force_min': 3, 'force_max': 37},
                    },  # Raumtemperatur Soll Normalbetrieb A1M1
                    'Soll_Red_Betrieb': {
                        'read': True,
                        'write': True,
                        'opcode': '2307',
                        'reply_pattern': '*',
                        'item_type': 'num',
                        'dev_datatype': 'Number',
                        'params': {'value': 'VAL', 'signed': True, 'len': 1},
                        'cmd_settings': {'force_min': 3, 'force_max': 37},
                    },  # Raumtemperatur Soll Reduzierter Betrieb A1M1
                    'Soll_Party_Betrieb': {
                        'read': True,
                        'write': True,
                        'opcode': '2308',
                        'reply_pattern': '*',
                        'item_type': 'num',
                        'dev_datatype': 'Number',
                        'params': {'value': 'VAL', 'signed': True, 'len': 1},
                        'cmd_settings': {'force_min': 3, 'force_max': 37},
                    },  # Raumtemperatur Soll Party Betrieb A1M1
                },
                'Vorlauf': {
                    'Ist': {
                        'read': True,
                        'write': False,
                        'opcode': '2900',
                        'reply_pattern': '*',
                        'item_type': 'num',
                        'dev_datatype': 'Number',
                        'params': {'value': 'VAL', 'mult': 10, 'len': 2},
                    },  # Vorlauftemperatur A1M1
                    'Soll': {
                        'read': True,
                        'write': False,
                        'opcode': '2544',
                        'reply_pattern': '*',
                        'item_type': 'num',
                        'dev_datatype': 'Number',
                        'params': {'value': 'VAL', 'mult': 10, 'len': 2},
                    },  # Vorlauftemperatur Soll A1M1
                    'Min': {
                        'read': True,
                        'write': True,
                        'opcode': '27c5',
                        'reply_pattern': '*',
                        'item_type': 'num',
                        'dev_datatype': 'Number',
                        'params': {'value': 'VAL', 'signed': True, 'len': 1},
                        'cmd_settings': {'force_min': 1, 'force_max': 127},
                    },  # Minimalbegrenzung der Vorlauftemperatur
                    'Max': {
                        'read': True,
                        'write': True,
                        'opcode': '27c6',
                        'reply_pattern': '*',
                        'item_type': 'num',
                        'dev_datatype': 'Number',
                        'params': {'value': 'VAL', 'signed': True, 'len': 1},
                        'cmd_settings': {'force_min': 10, 'force_max': 127},
                    },  # Maximalbegrenzung der Vorlauftemperatur
                    'Erhoehung_Soll': {
                        'read': True,
                        'write': True,
                        'opcode': '27fa',
                        'reply_pattern': '*',
                        'item_type': 'num',
                        'dev_datatype': 'Number',
                        'params': {'value': 'VAL', 'signed': True, 'len': 1},
                        'cmd_settings': {'force_min': 0, 'force_max': 50},
                    },  # Erhöhung des Kesselwasser- bzw. Vorlauftemperatur-Sollwertes beim Übergang von Betrieb mit reduzierter Raumtemperatur in den Betrieb mit normaler Raumtemperatur um 20 %
                    'Erhoehung_Zeit': {
                        'read': True,
                        'write': True,
                        'opcode': '27fa',
                        'reply_pattern': '*',
                        'item_type': 'num',
                        'dev_datatype': 'Number',
                        'params': {'value': 'VAL', 'signed': True, 'len': 1},
                        'cmd_settings': {'force_min': 0, 'force_max': 150},
                    },  # Zeitdauer für die Erhöhung des Kesselwasser bzw.VorlauftemperaturSollwertes (siehe Codieradresse „FA“) 60 min.
                },
                'Grenze_red_Betrieb': {
                    'read': True,
                    'write': True,
                    'opcode': '27f8',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'signed': True, 'len': 1},
                    'cmd_settings': {'force_min': -61, 'force_max': 10},
                },  # Temperaturgrenze für Aufhebung des reduzierten Betriebs -5 ºC
                'Grenze_red_Raumtemp': {
                    'read': True,
                    'write': True,
                    'opcode': '27f9',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'signed': True, 'len': 1},
                    'cmd_settings': {'force_min': -60, 'force_max': 10},
                },  # Temperaturgrenze für Anhebung des reduzierten RaumtemperaturSollwertes
            },
            'Status': {
                'Aktuelle_Betriebsart': {
                    'read': True,
                    'write': False,
                    'opcode': '2301',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'len': 1},
                    'lookup': 'operatingmodes',
                },  # Aktuelle Betriebsart A1M1
                'Betriebsart': {
                    'read': True,
                    'write': True,
                    'opcode': '2323',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'len': 1},
                    'cmd_settings': {'force_min': 0, 'force_max': 4},
                },  # Betriebsart A1M1
                'Sparbetrieb': {
                    'read': True,
                    'write': False,
                    'opcode': '2302',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'len': 1},
                },  # Sparbetrieb A1M1
                'Zustand_Sparbetrieb': {
                    'read': True,
                    'write': True,
                    'opcode': '2331',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'len': 1},
                    'cmd_settings': {'force_min': 0, 'force_max': 1},
                },  # Zustand Sparbetrieb A1M1
                'Partybetrieb': {
                    'read': True,
                    'write': False,
                    'opcode': '2303',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'len': 1},
                },  # Partybetrieb A1M1
                'Zustand_Partybetrieb': {
                    'read': True,
                    'write': True,
                    'opcode': '2330',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'len': 1},
                    'cmd_settings': {'force_min': 0, 'force_max': 1},
                },  # Zustand Partybetrieb A1M1
                'StatusFrost': {
                    'read': True,
                    'write': False,
                    'opcode': '2500',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'len': 1},
                },  # Status Frostwarnung A1M1
                'Externe_Raumsolltemperatur_Normal': {
                    'read': True,
                    'write': True,
                    'opcode': '2321',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'signed': True, 'len': 1},
                    'cmd_settings': {'force_min': 0, 'force_max': 37},
                },  # Externe Raumsolltemperatur Normal A1M1
                'Externe_Betriebsartenumschaltung': {
                    'read': True,
                    'write': True,
                    'opcode': '2549',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'len': 1},
                    'cmd_settings': {'force_min': 0, 'force_max': 4},
                },  # Externe Betriebsartenumschaltung A1M1
                'Speichervorrang': {
                    'read': True,
                    'write': True,
                    'opcode': '27a2',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'len': 1},
                    'cmd_settings': {'force_min': 0, 'force_max': 15},
                },  # Speichervorrang auf Heizkreispumpe und Mischer
                'Frostschutzgrenze': {
                    'read': True,
                    'write': True,
                    'opcode': '27a3',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'signed': True, 'len': 1},
                    'cmd_settings': {'force_min': -9, 'force_max': 15},
                },  # Frostschutzgrenze
                'Frostschutz': {
                    'read': True,
                    'write': True,
                    'opcode': '27a4',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'len': 1},
                    'cmd_settings': {'force_min': 0, 'force_max': 1},
                },  # Frostschutzgrenze
                'Heizkreispumpenlogik': {
                    'read': True,
                    'write': True,
                    'opcode': '27a5',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'signed': True, 'len': 1},
                    'cmd_settings': {'force_min': 0, 'force_max': 15},
                },  # HeizkreispumpenlogikFunktion
                'Sparschaltung': {
                    'read': True,
                    'write': True,
                    'opcode': '27a6',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'signed': True, 'len': 1},
                    'cmd_settings': {'force_min': 5, 'force_max': 35},
                },  # AbsolutSommersparschaltung
                'Mischersparfunktion': {
                    'read': True,
                    'write': True,
                    'opcode': '27a7',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'len': 1},
                    'cmd_settings': {'force_min': 0, 'force_max': 1},
                },  # Mischersparfunktion
                'Pumpenstillstandzeit': {
                    'read': True,
                    'write': True,
                    'opcode': '27a9',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'len': 1},
                    'cmd_settings': {'force_min': 0, 'force_max': 15},
                },  # Pumpenstillstandzeit
            },
            'Heizkennlinie': {
                'Neigung': {
                    'read': True,
                    'write': True,
                    'opcode': '27d3',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'mult': 10, 'len': 1},
                    'cmd_settings': {'force_min': 0.2, 'force_max': 3.5},
                },  # Neigung Heizkennlinie A1M1
                'Niveau': {
                    'read': True,
                    'write': True,
                    'opcode': '27d4',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'signed': True, 'len': 1},
                    'cmd_settings': {'force_min': -13, 'force_max': 40},
                },  # Niveau Heizkennlinie A1M1
            },
            'Partybetrieb_Zeitbegrenzung': {
                'read': True,
                'write': True,
                'opcode': '27f2',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'len': 1},
                'cmd_settings': {'force_min': 0, 'force_max': 12},
            },  # Zeitliche Begrenzung für Partybetrieb oder externe BetriebsprogrammUmschaltung mit Taster
        },
        'M2': {
            # Heizkreis M2
            'Temperatur': {
                'Raum': {
                    'Ist': {
                        'read': True,
                        'write': False,
                        'opcode': '0898',
                        'reply_pattern': '*',
                        'item_type': 'num',
                        'dev_datatype': 'Number',
                        'params': {'value': 'VAL', 'signed': True, 'len': 1},
                    },  # Raumtemperatur
                    'Soll_Normalbetrieb': {
                        'read': True,
                        'write': True,
                        'opcode': '3306',
                        'reply_pattern': '*',
                        'item_type': 'num',
                        'dev_datatype': 'Number',
                        'params': {'value': 'VAL', 'signed': True, 'len': 1},
                        'cmd_settings': {'force_min': 3, 'force_max': 37},
                    },  # Raumtemperatur Soll Normalbetrieb
                    'Soll_Red_Betrieb': {
                        'read': True,
                        'write': True,
                        'opcode': '3307',
                        'reply_pattern': '*',
                        'item_type': 'num',
                        'dev_datatype': 'Number',
                        'params': {'value': 'VAL', 'signed': True, 'len': 1},
                        'cmd_settings': {'force_min': 3, 'force_max': 37},
                    },  # Raumtemperatur Soll Reduzierter Betrieb
                    'Soll_Party_Betrieb': {
                        'read': True,
                        'write': True,
                        'opcode': '3308',
                        'reply_pattern': '*',
                        'item_type': 'num',
                        'dev_datatype': 'Number',
                        'params': {'value': 'VAL', 'signed': True, 'len': 1},
                        'cmd_settings': {'force_min': 3, 'force_max': 37},
                    },  # Raumtemperatur Soll Party Betrieb
                },
                'Vorlauf': {
                    'Ist': {
                        'read': True,
                        'write': False,
                        'opcode': '3900',
                        'reply_pattern': '*',
                        'item_type': 'num',
                        'dev_datatype': 'Number',
                        'params': {'value': 'VAL', 'mult': 10, 'len': 2},
                    },  # Vorlauftemperatur
                    'Soll': {
                        'read': True,
                        'write': False,
                        'opcode': '3544',
                        'reply_pattern': '*',
                        'item_type': 'num',
                        'dev_datatype': 'Number',
                        'params': {'value': 'VAL', 'mult': 10, 'len': 2},
                    },  # Vorlauftemperatur Soll
                    'Min': {
                        'read': True,
                        'write': True,
                        'opcode': '37c5',
                        'reply_pattern': '*',
                        'item_type': 'num',
                        'dev_datatype': 'Number',
                        'params': {'value': 'VAL', 'signed': True, 'len': 1},
                        'cmd_settings': {'force_min': 1, 'force_max': 127},
                    },  # Minimalbegrenzung der Vorlauftemperatur
                    'Max': {
                        'read': True,
                        'write': True,
                        'opcode': '37c6',
                        'reply_pattern': '*',
                        'item_type': 'num',
                        'dev_datatype': 'Number',
                        'params': {'value': 'VAL', 'signed': True, 'len': 1},
                        'cmd_settings': {'force_min': 10, 'force_max': 127},
                    },  # Maximalbegrenzung der Vorlauftemperatur
                    'Erhoehung_Soll': {
                        'read': True,
                        'write': True,
                        'opcode': '37fa',
                        'reply_pattern': '*',
                        'item_type': 'num',
                        'dev_datatype': 'Number',
                        'params': {'value': 'VAL', 'signed': True, 'len': 1},
                        'cmd_settings': {'force_min': 0, 'force_max': 50},
                    },  # Erhöhung des Kesselwasser- bzw. Vorlauftemperatur-Sollwertes beim Übergang von Betrieb mit reduzierter Raumtemperatur in den Betrieb mit normaler Raumtemperatur um 20 %
                    'Erhoehung_Zeit': {
                        'read': True,
                        'write': True,
                        'opcode': '37fb',
                        'reply_pattern': '*',
                        'item_type': 'num',
                        'dev_datatype': 'Number',
                        'params': {'value': 'VAL', 'signed': True, 'len': 1},
                        'cmd_settings': {'force_min': 0, 'force_max': 150},
                    },  # Zeitdauer für die Erhöhung des Kesselwasser bzw.VorlauftemperaturSollwertes (siehe Codieradresse „FA“) 60 min.
                },
                'Grenze_red_Betrieb': {
                    'read': True,
                    'write': True,
                    'opcode': '37f8',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'signed': True, 'len': 1},
                    'cmd_settings': {'force_min': -61, 'force_max': 10},
                },  # Temperaturgrenze für Aufhebung des reduzierten Betriebs -5 ºC
                'Grenze_red_Raumtemp': {
                    'read': True,
                    'write': True,
                    'opcode': '37f9',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'signed': True, 'len': 1},
                    'cmd_settings': {'force_min': -60, 'force_max': 10},
                },  # Temperaturgrenze für Anhebung des reduzierten RaumtemperaturSollwertes
            },
            'Status': {
                'Aktuelle_Betriebsart': {
                    'read': True,
                    'write': False,
                    'opcode': '3301',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'len': 1},
                    'lookup': 'operatingmodes',
                },  # Aktuelle Betriebsart
                'Betriebsart': {
                    'read': True,
                    'write': True,
                    'opcode': '3323',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'len': 1},
                    'cmd_settings': {'force_min': 0, 'force_max': 4},
                },  # Betriebsart
                'Sparbetrieb': {
                    'read': True,
                    'write': False,
                    'opcode': '3302',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'len': 1},
                },  # Sparbetrieb
                'Zustand_Sparbetrieb': {
                    'read': True,
                    'write': True,
                    'opcode': '3331',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'len': 1},
                    'cmd_settings': {'force_min': 0, 'force_max': 1},
                },  # Zustand Sparbetrieb
                'Partybetrieb': {
                    'read': True,
                    'write': False,
                    'opcode': '3303',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'len': 1},
                },  # Partybetrieb
                'Zustand_Partybetrieb': {
                    'read': True,
                    'write': True,
                    'opcode': '3330',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'len': 1},
                    'cmd_settings': {'force_min': 0, 'force_max': 1},
                },  # Zustand Partybetrieb
                'StatusFrost': {
                    'read': True,
                    'write': False,
                    'opcode': '3500',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'len': 1},
                },  # Status Frostwarnung
                'Externe_Raumsolltemperatur_Normal': {
                    'read': True,
                    'write': True,
                    'opcode': '3321',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'signed': True, 'len': 1},
                    'cmd_settings': {'force_min': 0, 'force_max': 37},
                },  # Externe Raumsolltemperatur Normal
                'Externe_Betriebsartenumschaltung': {
                    'read': True,
                    'write': True,
                    'opcode': '3549',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'len': 1},
                    'cmd_settings': {'force_min': 0, 'force_max': 4},
                },  # Externe Betriebsartenumschaltung
                'Speichervorrang': {
                    'read': True,
                    'write': True,
                    'opcode': '37a2',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'len': 1},
                    'cmd_settings': {'force_min': 0, 'force_max': 15},
                },  # Speichervorrang auf Heizkreispumpe und Mischer
                'Frostschutzgrenze': {
                    'read': True,
                    'write': True,
                    'opcode': '37a3',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'signed': True, 'len': 1},
                    'cmd_settings': {'force_min': -9, 'force_max': 15},
                },  # Frostschutzgrenze
                'Frostschutz': {
                    'read': True,
                    'write': True,
                    'opcode': '37a4',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'len': 1},
                    'cmd_settings': {'force_min': 0, 'force_max': 1},
                },  # Frostschutzgrenze
                'Heizkreispumpenlogik': {
                    'read': True,
                    'write': True,
                    'opcode': '37a5',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'signed': True, 'len': 1},
                    'cmd_settings': {'force_min': 0, 'force_max': 15},
                },  # HeizkreispumpenlogikFunktion
                'Sparschaltung': {
                    'read': True,
                    'write': True,
                    'opcode': '37a6',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'signed': True, 'len': 1},
                    'cmd_settings': {'force_min': 5, 'force_max': 35},
                },  # AbsolutSommersparschaltung
                'Mischersparfunktion': {
                    'read': True,
                    'write': True,
                    'opcode': '37a7',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'len': 1},
                    'cmd_settings': {'force_min': 0, 'force_max': 1},
                },  # Mischersparfunktion
                'Pumpenstillstandzeit': {
                    'read': True,
                    'write': True,
                    'opcode': '37a9',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'len': 1},
                    'cmd_settings': {'force_min': 0, 'force_max': 15},
                },  # Pumpenstillstandzeit
            },
            'Heizkennlinie': {
                'Neigung': {
                    'read': True,
                    'write': True,
                    'opcode': '37d3',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'mult': 10, 'len': 1},
                    'cmd_settings': {'force_min': 0.2, 'force_max': 3.5},
                },  # Neigung Heizkennlinie
                'Niveau': {
                    'read': True,
                    'write': True,
                    'opcode': '37d4',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'signed': True, 'len': 1},
                    'cmd_settings': {'force_min': -13, 'force_max': 40},
                },  # Niveau Heizkennlinie
            },
            'Partybetrieb_Zeitbegrenzung': {
                'read': True,
                'write': True,
                'opcode': '37f2',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'len': 1},
                'cmd_settings': {'force_min': 0, 'force_max': 12},
            },  # Zeitliche Begrenzung für Partybetrieb oder externe BetriebsprogrammUmschaltung mit Taster
        },
    },
    'Warmwasser': {
        # Warmwasser
        'Ist': {
            'read': True,
            'write': False,
            'opcode': '0804',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'mult': 10, 'len': 2},
        },  # Warmwassertemperatur in Grad C
        'Soll': {
            'read': True,
            'write': True,
            'opcode': '6300',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'signed': True, 'len': 1},
            'cmd_settings': {'force_min': 10, 'force_max': 95},
        },  # Warmwasser-Solltemperatur
        'Status': {
            'read': True,
            'write': True,
            'opcode': '650a',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
            'cmd_settings': {'force_min': 0, 'force_max': 1},
        },  # Satus Warmwasserbereitung
        'PumpenNachlauf': {
            'read': True,
            'write': True,
            'opcode': '6762',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'signed': True, 'len': 2},
            'cmd_settings': {'force_min': 0, 'force_max': 1},
        },  # Warmwasserpumpennachlauf
    },
    'Ferienprogramm': {
        'A1M1': {
            # Ferienprogramm HK
            'Status': {
                'read': True,
                'write': False,
                'opcode': '2535',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'len': 1},
            },  # Ferienprogramm A1M1
            'Abreisetag': {
                'read': True,
                'write': True,
                'opcode': '2309',
                'reply_pattern': '*',
                'item_type': 'bool',
                'dev_datatype': 'Date',
                'params': {'value': 'VAL', 'len': 8},
            },  # Ferien Abreisetag A1M1
            'Rückreisetag': {
                'read': True,
                'write': True,
                'opcode': '2311',
                'reply_pattern': '*',
                'item_type': 'bool',
                'dev_datatype': 'Date',
                'params': {'value': 'VAL', 'len': 8},
            },  # Ferien Rückreisetag A1M1
        },
        'M2': {
            # Ferienprogramm HK
            'Status': {
                'read': True,
                'write': False,
                'opcode': '3535',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'len': 1},
            },  # Ferienprogramm M2
            'Abreisetag': {
                'read': True,
                'write': True,
                'opcode': '3309',
                'reply_pattern': '*',
                'item_type': 'bool',
                'dev_datatype': 'Date',
                'params': {'value': 'VAL', 'len': 8},
            },  # Ferien Abreisetag M2
            'Rückreisetag': {
                'read': True,
                'write': True,
                'opcode': '3311',
                'reply_pattern': '*',
                'item_type': 'bool',
                'dev_datatype': 'Date',
                'params': {'value': 'VAL', 'len': 8},
            },  # Ferien Rückreisetag M2
        },
    },
    'Timer': {
        'Warmwasser': {
            # Schaltzeiten Warmwasser
            'Mo': {
                'read': True,
                'write': True,
                'opcode': '2100',
                'reply_pattern': '*',
                'item_type': 'list',
                'dev_datatype': 'Control',
                'params': {'value': 'VAL', 'len': 8},
            },  # Timer Warmwasserbereitung Montag
            'Di': {
                'read': True,
                'write': True,
                'opcode': '2108',
                'reply_pattern': '*',
                'item_type': 'list',
                'dev_datatype': 'Control',
                'params': {'value': 'VAL', 'len': 8},
            },  # Timer Warmwasserbereitung Dienstag
            'Mi': {
                'read': True,
                'write': True,
                'opcode': '2110',
                'reply_pattern': '*',
                'item_type': 'list',
                'dev_datatype': 'Control',
                'params': {'value': 'VAL', 'len': 8},
            },  # Timer Warmwasserbereitung Mittwoch
            'Do': {
                'read': True,
                'write': True,
                'opcode': '2118',
                'reply_pattern': '*',
                'item_type': 'list',
                'dev_datatype': 'Control',
                'params': {'value': 'VAL', 'len': 8},
            },  # Timer Warmwasserbereitung Donnerstag
            'Fr': {
                'read': True,
                'write': True,
                'opcode': '2120',
                'reply_pattern': '*',
                'item_type': 'list',
                'dev_datatype': 'Control',
                'params': {'value': 'VAL', 'len': 8},
            },  # Timer Warmwasserbereitung Freitag
            'Sa': {
                'read': True,
                'write': True,
                'opcode': '2128',
                'reply_pattern': '*',
                'item_type': 'list',
                'dev_datatype': 'Control',
                'params': {'value': 'VAL', 'len': 8},
            },  # Timer Warmwasserbereitung Samstag
            'So': {
                'read': True,
                'write': True,
                'opcode': '2130',
                'reply_pattern': '*',
                'item_type': 'list',
                'dev_datatype': 'Control',
                'params': {'value': 'VAL', 'len': 8},
            },  # Timer Warmwasserbereitung Sonntag
        },
        'A1M1': {
            # Schaltzeiten HK
            'Mo': {
                'read': True,
                'write': True,
                'opcode': '2000',
                'reply_pattern': '*',
                'item_type': 'list',
                'dev_datatype': 'Control',
                'params': {'value': 'VAL', 'len': 8},
            },  # Timer Heizkreis Montag
            'Di': {
                'read': True,
                'write': True,
                'opcode': '2008',
                'reply_pattern': '*',
                'item_type': 'list',
                'dev_datatype': 'Control',
                'params': {'value': 'VAL', 'len': 8},
            },  # Timer Heizkreis Dienstag
            'Mi': {
                'read': True,
                'write': True,
                'opcode': '2010',
                'reply_pattern': '*',
                'item_type': 'list',
                'dev_datatype': 'Control',
                'params': {'value': 'VAL', 'len': 8},
            },  # Timer Heizkreis Mittwoch
            'Do': {
                'read': True,
                'write': True,
                'opcode': '2018',
                'reply_pattern': '*',
                'item_type': 'list',
                'dev_datatype': 'Control',
                'params': {'value': 'VAL', 'len': 8},
            },  # Timer Heizkreis Donnerstag
            'Fr': {
                'read': True,
                'write': True,
                'opcode': '2020',
                'reply_pattern': '*',
                'item_type': 'list',
                'dev_datatype': 'Control',
                'params': {'value': 'VAL', 'len': 8},
            },  # Timer Heizkreis Freitag
            'Sa': {
                'read': True,
                'write': True,
                'opcode': '2028',
                'reply_pattern': '*',
                'item_type': 'list',
                'dev_datatype': 'Control',
                'params': {'value': 'VAL', 'len': 8},
            },  # Timer Heizkreis Samstag
            'So': {
                'read': True,
                'write': True,
                'opcode': '2030',
                'reply_pattern': '*',
                'item_type': 'list',
                'dev_datatype': 'Control',
                'params': {'value': 'VAL', 'len': 8},
            },  # Timer Heizkreis Sonntag
        },
        'M2': {
            # Schaltzeiten HK
            'Mo': {
                'read': True,
                'write': True,
                'opcode': '3000',
                'reply_pattern': '*',
                'item_type': 'list',
                'dev_datatype': 'Control',
                'params': {'value': 'VAL', 'len': 8},
            },  # Timer Heizkreis Montag
            'Di': {
                'read': True,
                'write': True,
                'opcode': '3008',
                'reply_pattern': '*',
                'item_type': 'list',
                'dev_datatype': 'Control',
                'params': {'value': 'VAL', 'len': 8},
            },  # Timer Heizkreis Dienstag
            'Mi': {
                'read': True,
                'write': True,
                'opcode': '3010',
                'reply_pattern': '*',
                'item_type': 'list',
                'dev_datatype': 'Control',
                'params': {'value': 'VAL', 'len': 8},
            },  # Timer Heizkreis Mittwoch
            'Do': {
                'read': True,
                'write': True,
                'opcode': '3018',
                'reply_pattern': '*',
                'item_type': 'list',
                'dev_datatype': 'Control',
                'params': {'value': 'VAL', 'len': 8},
            },  # Timer Heizkreis Donnerstag
            'Fr': {
                'read': True,
                'write': True,
                'opcode': '3020',
                'reply_pattern': '*',
                'item_type': 'list',
                'dev_datatype': 'Control',
                'params': {'value': 'VAL', 'len': 8},
            },  # Timer Heizkreis Freitag
            'Sa': {
                'read': True,
                'write': True,
                'opcode': '3028',
                'reply_pattern': '*',
                'item_type': 'list',
                'dev_datatype': 'Control',
                'params': {'value': 'VAL', 'len': 8},
            },  # Timer Heizkreis Samstag
            'So': {
                'read': True,
                'write': True,
                'opcode': '3030',
                'reply_pattern': '*',
                'item_type': 'list',
                'dev_datatype': 'Control',
                'params': {'value': 'VAL', 'len': 8},
            },  # Timer Heizkreis Sonntag
        },
        'Zirkulation': {
            # Schaltzeiten Zirkulation
            'Mo': {
                'read': True,
                'write': True,
                'opcode': '2200',
                'reply_pattern': '*',
                'item_type': 'list',
                'dev_datatype': 'Control',
                'params': {'value': 'VAL', 'len': 8},
            },  # Timer Zirkulationspumpe Montag
            'Di': {
                'read': True,
                'write': True,
                'opcode': '2208',
                'reply_pattern': '*',
                'item_type': 'list',
                'dev_datatype': 'Control',
                'params': {'value': 'VAL', 'len': 8},
            },  # Timer Zirkulationspumpe Dienstag
            'Mi': {
                'read': True,
                'write': True,
                'opcode': '2210',
                'reply_pattern': '*',
                'item_type': 'list',
                'dev_datatype': 'Control',
                'params': {'value': 'VAL', 'len': 8},
            },  # Timer Zirkulationspumpe Mittwoch
            'Do': {
                'read': True,
                'write': True,
                'opcode': '2218',
                'reply_pattern': '*',
                'item_type': 'list',
                'dev_datatype': 'Control',
                'params': {'value': 'VAL', 'len': 8},
            },  # Timer Zirkulationspumpe Donnerstag
            'Fr': {
                'read': True,
                'write': True,
                'opcode': '2220',
                'reply_pattern': '*',
                'item_type': 'list',
                'dev_datatype': 'Control',
                'params': {'value': 'VAL', 'len': 8},
            },  # Timer Zirkulationspumpe Freitag
            'Sa': {
                'read': True,
                'write': True,
                'opcode': '2228',
                'reply_pattern': '*',
                'item_type': 'list',
                'dev_datatype': 'Control',
                'params': {'value': 'VAL', 'len': 8},
            },  # Timer Zirkulationspumpe Samstag
            'So': {
                'read': True,
                'write': True,
                'opcode': '2230',
                'reply_pattern': '*',
                'item_type': 'list',
                'dev_datatype': 'Control',
                'params': {'value': 'VAL', 'len': 8},
            },  # Timer Zirkulationspumpe Sonntag
        },
    },
}

lookups = {
    'operatingmodes': {
        '00': 'Warmwasser (Schaltzeiten)',
        '01': 'reduziert Heizen (dauernd)',
        '02': 'normal Heizen (dauernd)',
        '04': 'Heizen und Warmwasser (FS)',
        '03': 'Heizen und Warmwasser (Schaltzeiten)',
        '05': 'Standby',
    },
    'systemschemes': {'01': 'A1', '02': 'A1 + WW', '04': 'M2', '03': 'M2 + WW', '05': 'A1 + M2', '06': 'A1 + M2 + WW'},
}
