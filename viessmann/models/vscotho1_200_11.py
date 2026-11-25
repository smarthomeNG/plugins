#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab

"""commands/lookups for Viessmann model VScotHO1_200_11"""

MODEL = 'VScotHO1_200_11'

commands = {
    'Allgemein': {
        'Temperatur': {
            'Aussentemperatur': {
                'read': True,
                'write': False,
                'opcode': '0800',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2},
            },  # Aussentemperatur
            'Aussentemperatur_TP': {
                'read': True,
                'write': False,
                'opcode': '5525',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2},
            },  # Aussentemperatur_tiefpass
            'Aussentemperatur_Dp': {
                'read': True,
                'write': False,
                'opcode': '5527',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2},
            },  # Aussentemperatur in Grad C (Gedaempft)
            'Temp_Speicher_Ladesensor': {
                'read': True,
                'write': False,
                'opcode': '0812',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'mult': 10, 'len': 2},
            },  # Temperatur Speicher Ladesensor Komfortsensor
            'Auslauftemperatur': {
                'read': True,
                'write': False,
                'opcode': '0814',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'mult': 10, 'len': 2},
            },  # Auslauftemperatur
            'Abgastemperatur': {
                'read': True,
                'write': False,
                'opcode': '0816',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'mult': 10, 'len': 2},
            },  # Abgastemperatur
            'Gem_Vorlauftemperatur': {
                'read': True,
                'write': False,
                'opcode': '081a',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'mult': 10, 'len': 2},
            },  # Gem. Vorlauftemperatur
        },
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
            'item_type': 'str',
            'dev_datatype': 'Hex',
            'params': {'value': 'VAL', 'len': 1},
            'lookup': 'systemschemes',
        },  # Anlagenschema
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
        'Kesseltemperatur': {
            'read': True,
            'write': False,
            'opcode': '0802',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'mult': 10, 'len': 2},
        },  # Kesseltemperatur
        'Kesseltemperatur_TP': {
            'read': True,
            'write': False,
            'opcode': '0810',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'mult': 10, 'len': 2},
        },  # Kesseltemperatur_tiefpass
        'Kesselsolltemperatur': {
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
        'Fehler01': {
            'read': True,
            'write': False,
            'opcode': '7590',
            'reply_pattern': '*',
            'item_type': 'str',
            'dev_datatype': 'ErrorHistory',
            'params': {'value': 'VAL', 'len': 9},
        },  # Fehlerhistory Eintrag 1
        'Fehler02': {
            'read': True,
            'write': False,
            'opcode': '7599',
            'reply_pattern': '*',
            'item_type': 'str',
            'dev_datatype': 'ErrorHistory',
            'params': {'value': 'VAL', 'len': 9},
        },  # Fehlerhistory Eintrag 2
        'Fehler03': {
            'read': True,
            'write': False,
            'opcode': '75a2',
            'reply_pattern': '*',
            'item_type': 'str',
            'dev_datatype': 'ErrorHistory',
            'params': {'value': 'VAL', 'len': 9},
        },  # Fehlerhistory Eintrag 3
        'Fehler04': {
            'read': True,
            'write': False,
            'opcode': '75ab',
            'reply_pattern': '*',
            'item_type': 'str',
            'dev_datatype': 'ErrorHistory',
            'params': {'value': 'VAL', 'len': 9},
        },  # Fehlerhistory Eintrag 4
        'Fehler05': {
            'read': True,
            'write': False,
            'opcode': '75b4',
            'reply_pattern': '*',
            'item_type': 'str',
            'dev_datatype': 'ErrorHistory',
            'params': {'value': 'VAL', 'len': 9},
        },  # Fehlerhistory Eintrag 5
        'Fehler06': {
            'read': True,
            'write': False,
            'opcode': '75bd',
            'reply_pattern': '*',
            'item_type': 'str',
            'dev_datatype': 'ErrorHistory',
            'params': {'value': 'VAL', 'len': 9},
        },  # Fehlerhistory Eintrag 6
        'Fehler07': {
            'read': True,
            'write': False,
            'opcode': '75c6',
            'reply_pattern': '*',
            'item_type': 'str',
            'dev_datatype': 'ErrorHistory',
            'params': {'value': 'VAL', 'len': 9},
        },  # Fehlerhistory Eintrag 7
        'Fehler08': {
            'read': True,
            'write': False,
            'opcode': '75cf',
            'reply_pattern': '*',
            'item_type': 'str',
            'dev_datatype': 'ErrorHistory',
            'params': {'value': 'VAL', 'len': 9},
        },  # Fehlerhistory Eintrag 8
        'Fehler09': {
            'read': True,
            'write': False,
            'opcode': '75d8',
            'reply_pattern': '*',
            'item_type': 'str',
            'dev_datatype': 'ErrorHistory',
            'params': {'value': 'VAL', 'len': 9},
        },  # Fehlerhistory Eintrag 9
        'Fehler10': {
            'read': True,
            'write': False,
            'opcode': '75e1',
            'reply_pattern': '*',
            'item_type': 'str',
            'dev_datatype': 'ErrorHistory',
            'params': {'value': 'VAL', 'len': 9},
        },  # Fehlerhistory Eintrag 10
        'Fehler11': {
            'read': True,
            'write': False,
            'opcode': '75ea',
            'reply_pattern': '*',
            'item_type': 'str',
            'dev_datatype': 'ErrorHistory',
            'params': {'value': 'VAL', 'len': 9},
        },  # Fehlerhistory Eintrag 11
        'Fehler12': {
            'read': True,
            'write': False,
            'opcode': '75f3',
            'reply_pattern': '*',
            'item_type': 'str',
            'dev_datatype': 'ErrorHistory',
            'params': {'value': 'VAL', 'len': 9},
        },  # Fehlerhistory Eintrag 12
        'Fehler13': {
            'read': True,
            'write': False,
            'opcode': '75fc',
            'reply_pattern': '*',
            'item_type': 'str',
            'dev_datatype': 'ErrorHistory',
            'params': {'value': 'VAL', 'len': 9},
        },  # Fehlerhistory Eintrag 13
        'Fehler14': {
            'read': True,
            'write': False,
            'opcode': '7605',
            'reply_pattern': '*',
            'item_type': 'str',
            'dev_datatype': 'ErrorHistory',
            'params': {'value': 'VAL', 'len': 9},
        },  # Fehlerhistory Eintrag 14
        'Fehler15': {
            'read': True,
            'write': False,
            'opcode': '760e',
            'reply_pattern': '*',
            'item_type': 'str',
            'dev_datatype': 'ErrorHistory',
            'params': {'value': 'VAL', 'len': 9},
        },  # Fehlerhistory Eintrag 15
        'Fehler16': {
            'read': True,
            'write': False,
            'opcode': '7617',
            'reply_pattern': '*',
            'item_type': 'str',
            'dev_datatype': 'ErrorHistory',
            'params': {'value': 'VAL', 'len': 9},
        },  # Fehlerhistory Eintrag 16
        'Fehler17': {
            'read': True,
            'write': False,
            'opcode': '7620',
            'reply_pattern': '*',
            'item_type': 'str',
            'dev_datatype': 'ErrorHistory',
            'params': {'value': 'VAL', 'len': 9},
        },  # Fehlerhistory Eintrag 17
        'Fehler18': {
            'read': True,
            'write': False,
            'opcode': '7629',
            'reply_pattern': '*',
            'item_type': 'str',
            'dev_datatype': 'ErrorHistory',
            'params': {'value': 'VAL', 'len': 9},
        },  # Fehlerhistory Eintrag 18
        'Fehler19': {
            'read': True,
            'write': False,
            'opcode': '7632',
            'reply_pattern': '*',
            'item_type': 'str',
            'dev_datatype': 'ErrorHistory',
            'params': {'value': 'VAL', 'len': 9},
        },  # Fehlerhistory Eintrag 19
        'Fehler20': {
            'read': True,
            'write': False,
            'opcode': '763b',
            'reply_pattern': '*',
            'item_type': 'str',
            'dev_datatype': 'ErrorHistory',
            'params': {'value': 'VAL', 'len': 9},
        },  # Fehlerhistory Eintrag 20
    },
    'Pumpen': {
        'Speicherladepumpe': {
            'read': True,
            'write': False,
            'opcode': '6513',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # Speicherladepumpe
        'Zirkulationspumpe': {
            'read': True,
            'write': False,
            'opcode': '6515',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # Zirkulationspumpe
        'Interne_Pumpe': {
            'read': True,
            'write': False,
            'opcode': '7660',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # Interne Pumpe
        'Heizkreispumpe_A1M1': {
            'read': True,
            'write': False,
            'opcode': '2906',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # Heizkreispumpe A1
        'Heizkreispumpe_A1M1_RPM': {
            'read': True,
            'write': False,
            'opcode': '7663',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # Heizkreispumpe A1M1 Drehzahl
        'Relais_Status_Pumpe_A1M1': {
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
        'Brennerstarts': {
            'read': True,
            'write': True,
            'opcode': '088a',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'signed': True, 'len': 4},
            'cmd_settings': {'force_min': 0, 'force_max': 1193045},
        },  # Brennerstarts
        'Brenner_Betriebsstunden': {
            'read': True,
            'write': True,
            'opcode': '08a7',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'mult': 3600, 'len': 4},
            'cmd_settings': {'force_min': 0, 'force_max': 1193045},
        },  # Brenner-Betriebsstunden
        'Brennerstatus_1': {
            'read': True,
            'write': False,
            'opcode': '0842',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # Brennerstatus Stufe1
    },
    'Heizkreis': {
        'A1M1': {
            'Temperatur': {
                'Raum': {
                    'Raumtemperatur_A1M1': {
                        'read': True,
                        'write': False,
                        'opcode': '0896',
                        'reply_pattern': '*',
                        'item_type': 'num',
                        'dev_datatype': 'Number',
                        'params': {'value': 'VAL', 'signed': True, 'len': 1},
                    },  # Raumtemperatur A1M1
                    'Raumtemperatur_Soll_Normalbetrieb_A1M1': {
                        'read': True,
                        'write': True,
                        'opcode': '2306',
                        'reply_pattern': '*',
                        'item_type': 'num',
                        'dev_datatype': 'Number',
                        'params': {'value': 'VAL', 'signed': True, 'len': 1},
                        'cmd_settings': {'force_min': 3, 'force_max': 37},
                    },  # Raumtemperatur Soll Normalbetrieb A1M1
                    'Raumtemperatur_Soll_Red_Betrieb_A1M1': {
                        'read': True,
                        'write': True,
                        'opcode': '2307',
                        'reply_pattern': '*',
                        'item_type': 'num',
                        'dev_datatype': 'Number',
                        'params': {'value': 'VAL', 'signed': True, 'len': 1},
                        'cmd_settings': {'force_min': 3, 'force_max': 37},
                    },  # Raumtemperatur Soll Reduzierter Betrieb A1M1
                    'Raumtemperatur_Soll_Party_Betrieb_A1M1': {
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
                    'Vorlauftemperatur_A1M1': {
                        'read': True,
                        'write': False,
                        'opcode': '2900',
                        'reply_pattern': '*',
                        'item_type': 'num',
                        'dev_datatype': 'Number',
                        'params': {'value': 'VAL', 'mult': 10, 'len': 2},
                    },  # Vorlauftemperatur A1M1
                    'Vorlauftemperatur_Soll_A1M1': {
                        'read': True,
                        'write': False,
                        'opcode': '2544',
                        'reply_pattern': '*',
                        'item_type': 'num',
                        'dev_datatype': 'Number',
                        'params': {'value': 'VAL', 'mult': 10, 'len': 2},
                    },  # Vorlauftemperatur Soll A1M1
                    'Vorlauftemperatur_min_A1M1': {
                        'read': True,
                        'write': True,
                        'opcode': '27c5',
                        'reply_pattern': '*',
                        'item_type': 'num',
                        'dev_datatype': 'Number',
                        'params': {'value': 'VAL', 'signed': True, 'len': 1},
                        'cmd_settings': {'force_min': 1, 'force_max': 127},
                    },  # Minimalbegrenzung der Vorlauftemperatur
                    'Vorlauftemperatur_max_A1M1': {
                        'read': True,
                        'write': True,
                        'opcode': '27c6',
                        'reply_pattern': '*',
                        'item_type': 'num',
                        'dev_datatype': 'Number',
                        'params': {'value': 'VAL', 'signed': True, 'len': 1},
                        'cmd_settings': {'force_min': 10, 'force_max': 127},
                    },  # Maximalbegrenzung der Vorlauftemperatur
                    'Vorlauftemperatur_Erhoehung_Soll_A1M1': {
                        'read': True,
                        'write': True,
                        'opcode': '27fa',
                        'reply_pattern': '*',
                        'item_type': 'num',
                        'dev_datatype': 'Number',
                        'params': {'value': 'VAL', 'signed': True, 'len': 1},
                        'cmd_settings': {'force_min': 0, 'force_max': 50},
                    },  # Erhöhung des Kesselwasser- bzw. Vorlauftemperatur-Sollwertes beim Übergang von Betrieb mit reduzierter Raumtemperatur in den Betrieb mit normaler Raumtemperatur um 20 %
                },
                'Temperaturgrenze_red_Betrieb_A1M1': {
                    'read': True,
                    'write': True,
                    'opcode': '27f8',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'signed': True, 'len': 1},
                    'cmd_settings': {'force_min': -61, 'force_max': 10},
                },  # Temperaturgrenze für Aufhebung des reduzierten Betriebs -5 ºC
                'Temperaturgrenze_red_Raumtemp_A1M1': {
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
                'Aktuelle_Betriebsart_A1M1': {
                    'read': True,
                    'write': False,
                    'opcode': '2301',
                    'reply_pattern': '*',
                    'item_type': 'str',
                    'dev_datatype': 'Hex',
                    'params': {'value': 'VAL', 'len': 1},
                    'lookup': 'operatingmodes',
                    'item_attrs': {'initial': True, 'lookup_item': True},
                },  # Aktuelle Betriebsart A1M1
                'Betriebsart_A1M1': {
                    'read': True,
                    'write': True,
                    'opcode': '2323',
                    'reply_pattern': '*',
                    'item_type': 'str',
                    'dev_datatype': 'Hex',
                    'params': {'value': 'VAL', 'len': 1},
                    'item_attrs': {'initial': True, 'lookup_item': True},
                },  # Betriebsart A1M1
                'StatusFrost_A1M1': {
                    'read': True,
                    'write': False,
                    'opcode': '2500',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'len': 1},
                },  # Status Frostwarnung A1M1
                'Externe_Raumsolltemperatur_Normal_A1M1': {
                    'read': True,
                    'write': True,
                    'opcode': '2321',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'signed': True, 'len': 1},
                    'cmd_settings': {'force_min': 0, 'force_max': 37},
                },  # Externe Raumsolltemperatur Normal A1M1
                'Externe_Betriebsartenumschaltung_A1M1': {
                    'read': True,
                    'write': True,
                    'opcode': '2549',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'len': 1},
                    'cmd_settings': {'force_min': 0, 'force_max': 4},
                },  # Externe Betriebsartenumschaltung A1M1
                'Speichervorrang_A1M1': {
                    'read': True,
                    'write': True,
                    'opcode': '27a2',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'len': 1},
                    'cmd_settings': {'force_min': 0, 'force_max': 15},
                },  # Speichervorrang auf Heizkreispumpe und Mischer
                'Frostschutzgrenze_A1M1': {
                    'read': True,
                    'write': True,
                    'opcode': '27a3',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'signed': True, 'len': 1},
                    'cmd_settings': {'force_min': -9, 'force_max': 15},
                },  # Frostschutzgrenze
                'Heizkreispumpenlogik_A1M1': {
                    'read': True,
                    'write': True,
                    'opcode': '27a5',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'signed': True, 'len': 1},
                    'cmd_settings': {'force_min': 0, 'force_max': 15},
                },  # HeizkreispumpenlogikFunktion
                'Sparschaltung_A1M1': {
                    'read': True,
                    'write': True,
                    'opcode': '27a6',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'signed': True, 'len': 1},
                    'cmd_settings': {'force_min': 5, 'force_max': 35},
                },  # AbsolutSommersparschaltung
                'Pumpenstillstandzeit_A1M1': {
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
                'Neigung_Heizkennlinie_A1M1': {
                    'read': True,
                    'write': True,
                    'opcode': '27d3',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'mult': 10, 'len': 1},
                    'cmd_settings': {'force_min': 0.2, 'force_max': 3.5},
                },  # Neigung Heizkennlinie A1M1
                'Niveau_Heizkennlinie_A1M1': {
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
            'Partybetrieb_Zeitbegrenzung_A1M1': {
                'read': True,
                'write': True,
                'opcode': '27f2',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'len': 1},
                'cmd_settings': {'force_min': 0, 'force_max': 12},
            },  # Zeitliche Begrenzung für Partybetrieb oder externe BetriebsprogrammUmschaltung mit Taster
        }
    },
    'Warmwasser': {
        'Warmwasser_Temperatur': {
            'read': True,
            'write': False,
            'opcode': '0804',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'mult': 10, 'len': 2},
        },  # Warmwassertemperatur in Grad C
        'Warmwasser_Solltemperatur': {
            'read': True,
            'write': True,
            'opcode': '6300',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'signed': True, 'len': 1},
            'cmd_settings': {'force_min': 10, 'force_max': 95},
        },  # Warmwasser-Solltemperatur
        'WarmwasserPumpenNachlauf': {
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
            'Ferienprogramm_A1M1': {
                'read': True,
                'write': False,
                'opcode': '2535',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'len': 1},
            },  # Ferienprogramm A1M1
            'Ferien_Abreisetag_A1M1': {
                'read': True,
                'write': True,
                'opcode': '2309',
                'reply_pattern': '*',
                'item_type': 'bool',
                'dev_datatype': 'Date',
                'params': {'value': 'VAL', 'len': 8},
            },  # Ferien Abreisetag A1M1
            'Ferien_Rückreisetag_A1M1': {
                'read': True,
                'write': True,
                'opcode': '2311',
                'reply_pattern': '*',
                'item_type': 'bool',
                'dev_datatype': 'Date',
                'params': {'value': 'VAL', 'len': 8},
            },  # Ferien Rückreisetag A1M1
        }
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
