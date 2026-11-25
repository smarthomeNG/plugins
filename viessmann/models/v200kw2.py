#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab

"""commands/lookups for Viessmann model V200KW2"""

MODEL = 'V200KW2'

commands = {
    'Allgemein': {
        # Allgemein
        'Temperatur': {
            'Aussen': {
                'read': True,
                'write': False,
                'opcode': '0800',
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
        },
        'Anlagenschema': {
            'read': True,
            'write': False,
            'opcode': '7700',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
            'lookup': 'systemschemes',
        },  # Anlagenschema
        'AnlagenSoftwareIndex': {
            'read': True,
            'write': False,
            'opcode': '7330',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # Bedienteil SoftwareIndex
        'Systemtime': {
            'read': True,
            'write': True,
            'opcode': '088e',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Time',
            'params': {'value': 'VAL', 'len': 8},
        },  # Systemzeit
    },
    'Kessel': {
        # Kessel
        'TempKOffset': {
            'read': True,
            'write': True,
            'opcode': '6760',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
            'cmd_settings': {'force_min': 10, 'force_max': 50},
        },  # Kesseloffset KT ueber WWsoll in Grad C
        'Ist': {
            'read': True,
            'write': False,
            'opcode': '0802',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'mult': 10, 'len': 2},
        },  # Kesseltemperatur
        'Soll': {
            'read': True,
            'write': True,
            'opcode': '5502',
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
            'opcode': '0847',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
            'lookup': 'returnstatus',
        },  # Sammelstörung
        'Brennerstoerung': {
            'read': True,
            'write': False,
            'opcode': '0883',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
            'lookup': 'returnstatus',
        },
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
            'opcode': '0845',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # Speicherladepumpe für Warmwasser
        'Zirkulation': {
            'read': True,
            'write': False,
            'opcode': '0846',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # Zirkulationspumpe
        'Heizkreis_A1M1': {
            'read': True,
            'write': False,
            'opcode': '2906',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # Heizkreispumpe A1M1
        'Heizkreis_M2': {
            'read': True,
            'write': False,
            'opcode': '3906',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # Heizkreispumpe M2
    },
    'Brenner': {
        # Brenner
        'Typ': {
            'read': True,
            'write': False,
            'opcode': 'a30b',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # Brennertyp 0=einstufig 1=zweistufig 2=modulierend
        'Stufe': {
            'read': True,
            'write': False,
            'opcode': '551e',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
            'lookup': 'returnstatus',
        },  # Ermittle die aktuelle Brennerstufe
        'Starts': {
            'read': True,
            'write': True,
            'opcode': '088a',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'signed': True, 'len': 2},
            'cmd_settings': {'force_min': 0, 'force_max': 1193045},
        },  # Brennerstarts
        'Status_1': {
            'read': True,
            'write': False,
            'opcode': '55d3',
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
        'BetriebsstundenStufe1': {
            'read': True,
            'write': True,
            'opcode': '0886',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'mult': 3600, 'len': 4},
            'cmd_settings': {'force_min': 0, 'force_max': 1193045},
        },  # Brenner-Betriebsstunden Stufe 1
        'BetriebsstundenStufe2': {
            'read': True,
            'write': True,
            'opcode': '08a3',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'mult': 3600, 'len': 4},
            'cmd_settings': {'force_min': 0, 'force_max': 1193045},
        },  # Brenner-Betriebsstunden Stufe 2
    },
    'Heizkreis': {
        'A1M1': {
            # Heizkreis A1M1
            'Temperatur': {
                'Raum': {
                    'Soll_Normal': {
                        'read': True,
                        'write': True,
                        'opcode': '2306',
                        'reply_pattern': '*',
                        'item_type': 'num',
                        'dev_datatype': 'Number',
                        'params': {'value': 'VAL', 'signed': True, 'len': 1},
                        'cmd_settings': {'force_min': 4, 'force_max': 37},
                    },  # Raumtemperatur Soll Normalbetrieb A1M1
                    'Soll_Reduziert': {
                        'read': True,
                        'write': True,
                        'opcode': '2307',
                        'reply_pattern': '*',
                        'item_type': 'num',
                        'dev_datatype': 'Number',
                        'params': {'value': 'VAL', 'signed': True, 'len': 1},
                        'cmd_settings': {'force_min': 4, 'force_max': 37},
                    },  # Raumtemperatur Soll Reduzierter Betrieb A1M1
                    'Soll_Party': {
                        'read': True,
                        'write': True,
                        'opcode': '2308',
                        'reply_pattern': '*',
                        'item_type': 'num',
                        'dev_datatype': 'Number',
                        'params': {'value': 'VAL', 'signed': True, 'len': 1},
                        'cmd_settings': {'force_min': 4, 'force_max': 37},
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
                },
            },
            'Betriebsart': {
                'read': True,
                'write': True,
                'opcode': '2301',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'len': 1},
                'lookup': 'operatingmodes',
            },  # Betriebsart A1M1
            'Aktuelle_Betriebsart': {
                'read': True,
                'write': False,
                'opcode': '2500',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'len': 1},
                'lookup': 'operatingmodes',
            },  # Aktuelle Betriebsart A1M1
            'Sparbetrieb': {
                'read': True,
                'write': True,
                'opcode': '2302',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'len': 1},
                'cmd_settings': {'force_min': 0, 'force_max': 1},
            },  # Sparbetrieb A1M1
            'Partybetrieb_Zeit': {
                'read': True,
                'write': True,
                'opcode': '27f2',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'len': 1},
                'cmd_settings': {'force_min': 0, 'force_max': 12},
            },  # Partyzeit M2
            'Partybetrieb': {
                'read': True,
                'write': True,
                'opcode': '2303',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'len': 1},
                'cmd_settings': {'force_min': 0, 'force_max': 1},
            },  # Partybetrieb A1M1
            'MischerM1': {
                'read': True,
                'write': False,
                'opcode': '254c',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'mult': 2.55, 'len': 1},
            },  # Ermittle Mischerposition M1
            'Heizkreispumpenlogik': {
                'read': True,
                'write': True,
                'opcode': '27a5',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'signed': True, 'len': 1},
                'cmd_settings': {'force_min': 0, 'force_max': 15},
            },  # 0=ohne HPL-Funktion, 1=AT > RTsoll + 5 K, 2=AT > RTsoll + 4 K, 3=AT > RTsoll + 3 K, 4=AT > RTsoll + 2 K, 5=AT > RTsoll + 1 K, 6=AT > RTsoll, 7=AT > RTsoll - 1 K, 8=AT > RTsoll - 2 K, 9=AT > RTsoll - 3 K, 10=AT > RTsoll - 4 K, 11=AT > RTsoll - 5 K, 12=AT > RTsoll - 6 K, 13=AT > RTsoll - 7 K, 14=AT > RTsoll - 8 K, 15=AT > RTsoll - 9 K
            'Sparschaltung': {
                'read': True,
                'write': True,
                'opcode': '27a6',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'signed': True, 'len': 1},
                'cmd_settings': {'force_min': 5, 'force_max': 36},
            },  # AbsolutSommersparschaltung
            'Heizkennlinie': {
                'Neigung': {
                    'read': True,
                    'write': True,
                    'opcode': '2305',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'mult': 10, 'len': 1},
                    'cmd_settings': {'force_min': 0.2, 'force_max': 3.5},
                },  # Neigung Heizkennlinie A1M1
                'Niveau': {
                    'read': True,
                    'write': True,
                    'opcode': '2304',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'signed': True, 'len': 1},
                    'cmd_settings': {'force_min': -13, 'force_max': 40},
                },  # Niveau Heizkennlinie A1M1
            },
        },
        'M2': {
            # Heizkreis M2
            'Temperatur': {
                'Raum': {
                    'Soll_Normal': {
                        'read': True,
                        'write': True,
                        'opcode': '3306',
                        'reply_pattern': '*',
                        'item_type': 'num',
                        'dev_datatype': 'Number',
                        'params': {'value': 'VAL', 'signed': True, 'len': 1},
                        'cmd_settings': {'force_min': 4, 'force_max': 37},
                    },  # Raumtemperatur Soll Normalbetrieb
                    'Soll_Reduziert': {
                        'read': True,
                        'write': True,
                        'opcode': '3307',
                        'reply_pattern': '*',
                        'item_type': 'num',
                        'dev_datatype': 'Number',
                        'params': {'value': 'VAL', 'signed': True, 'len': 1},
                        'cmd_settings': {'force_min': 4, 'force_max': 37},
                    },  # Raumtemperatur Soll Reduzierter Betrieb
                    'Soll_Party': {
                        'read': True,
                        'write': True,
                        'opcode': '3308',
                        'reply_pattern': '*',
                        'item_type': 'num',
                        'dev_datatype': 'Number',
                        'params': {'value': 'VAL', 'signed': True, 'len': 1},
                        'cmd_settings': {'force_min': 4, 'force_max': 37},
                    },  # Raumtemperatur Soll Party Betrieb
                },
                'Vorlauf': {
                    'Soll': {
                        'read': True,
                        'write': True,
                        'opcode': '37c6',
                        'reply_pattern': '*',
                        'item_type': 'num',
                        'dev_datatype': 'Number',
                        'params': {'value': 'VAL', 'mult': 10, 'len': 2},
                        'cmd_settings': {'force_min': 10, 'force_max': 80},
                    },  # Vorlauftemperatur Soll
                    'Ist': {
                        'read': True,
                        'write': False,
                        'opcode': '080c',
                        'reply_pattern': '*',
                        'item_type': 'num',
                        'dev_datatype': 'Number',
                        'params': {'value': 'VAL', 'mult': 10, 'len': 2},
                    },  # Vorlauftemperatur Ist
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
                        'cmd_settings': {'force_min': 1, 'force_max': 127},
                    },  # Maximalbegrenzung der Vorlauftemperatur
                },
            },
            'Betriebsart': {
                'read': True,
                'write': True,
                'opcode': '3301',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'len': 1},
                'lookup': 'operatingmodes',
            },  # Betriebsart M2
            'Aktuelle_Betriebsart': {
                'read': True,
                'write': False,
                'opcode': '3500',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'len': 1},
                'lookup': 'operatingmodes',
            },  # Aktuelle Betriebsart M2
            'Sparbetrieb': {
                'read': True,
                'write': True,
                'opcode': '3302',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'len': 1},
                'cmd_settings': {'force_min': 0, 'force_max': 1},
            },  # Sparbetrieb
            'Partybetrieb': {
                'read': True,
                'write': True,
                'opcode': '3303',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'len': 1},
                'cmd_settings': {'force_min': 0, 'force_max': 1},
            },  # Partybetrieb A1M1
            'Partybetrieb_Zeit': {
                'read': True,
                'write': True,
                'opcode': '37f2',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'len': 1},
                'cmd_settings': {'force_min': 0, 'force_max': 12},
            },  # Partyzeit M2
            'MischerM2': {
                'read': True,
                'write': False,
                'opcode': '354c',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'mult': 2.55, 'len': 1},
            },  # Ermittle Mischerposition M2
            'MischerM2Auf': {
                'read': True,
                'write': True,
                'opcode': '084d',
                'reply_pattern': '*',
                'item_type': 'bool',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'len': 1},
                'cmd_settings': {'force_min': 0, 'force_max': 1},
            },  # MischerM2 Auf 0=AUS;1=EIN
            'MischerM2Zu': {
                'read': True,
                'write': True,
                'opcode': '084c',
                'reply_pattern': '*',
                'item_type': 'bool',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'len': 1},
                'cmd_settings': {'force_min': 0, 'force_max': 1},
            },  # MischerM2 Zu 0=AUS;1=EIN
            'Heizkreispumpenlogik': {
                'read': True,
                'write': True,
                'opcode': '37a5',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'signed': True, 'len': 1},
                'cmd_settings': {'force_min': 0, 'force_max': 15},
            },  # 0=ohne HPL-Funktion, 1=AT > RTsoll + 5 K, 2=AT > RTsoll + 4 K, 3=AT > RTsoll + 3 K, 4=AT > RTsoll + 2 K, 5=AT > RTsoll + 1 K, 6=AT > RTsoll, 7=AT > RTsoll - 1 K, 8=AT > RTsoll - 2 K, 9=AT > RTsoll - 3 K, 10=AT > RTsoll - 4 K, 11=AT > RTsoll - 5 K, 12=AT > RTsoll - 6 K, 13=AT > RTsoll - 7 K, 14=AT > RTsoll - 8 K, 15=AT > RTsoll - 9 K
            'Sparschaltung': {
                'read': True,
                'write': True,
                'opcode': '37a6',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'signed': True, 'len': 1},
                'cmd_settings': {'force_min': 5, 'force_max': 36},
            },  # AbsolutSommersparschaltung
            'StatusKlemme2': {
                'read': True,
                'write': False,
                'opcode': '3904',
                'reply_pattern': '*',
                'item_type': 'bool',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'len': 1},
            },  # 0=OK, 1=Kurzschluss, 2=nicht vorhanden, 3-5=Referenzfehler, 6=nicht vorhanden
            'StatusKlemme17': {
                'read': True,
                'write': False,
                'opcode': '3905',
                'reply_pattern': '*',
                'item_type': 'bool',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'len': 1},
            },  # 0=OK, 1=Kurzschluss, 2=nicht vorhanden, 3-5=Referenzfehler, 6=nicht vorhanden
            'Heizkennlinie': {
                'Neigung': {
                    'read': True,
                    'write': True,
                    'opcode': '3305',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'mult': 10, 'len': 1},
                    'cmd_settings': {'force_min': 0.2, 'force_max': 3.5},
                },  # Neigung Heizkennlinie M2
                'Niveau': {
                    'read': True,
                    'write': True,
                    'opcode': '3304',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'signed': True, 'len': 1},
                    'cmd_settings': {'force_min': -13, 'force_max': 40},
                },  # Niveau Heizkennlinie M2
            },
        },
    },
    'Warmwasser': {
        # Warmwasser
        'Status': {
            'read': True,
            'write': False,
            'opcode': '650A',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # 0=Ladung inaktiv, 1=in Ladung, 2=im Nachlauf
        'KesselOffset': {
            'read': True,
            'write': True,
            'opcode': '6760',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
            'cmd_settings': {'force_min': 10, 'force_max': 50},
        },  # Warmwasser Kessel Offset in K
        'BeiPartyDNormal': {
            'read': True,
            'write': True,
            'opcode': '6764',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
            'cmd_settings': {'force_min': 0, 'force_max': 2},
        },  # WW Heizen bei Party 0=AUS, 1=nach Schaltuhr, 2=EIN
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
            'cmd_settings': {'force_min': 10, 'force_max': 80},
        },  # Warmwasser-Solltemperatur
        'SollAktuell': {
            'read': True,
            'write': False,
            'opcode': '6500',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'mult': 10, 'len': 1},
        },  # Warmwasser-Solltemperatur aktuell
        'SollMax': {
            'read': True,
            'write': False,
            'opcode': '675a',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # 0=inaktiv, 1=aktiv
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
            },  # Ferienprogramm A1M1 0=inaktiv 1=aktiv
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
            },  # Ferienprogramm M2 0=inaktiv 1=aktiv
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
        '10': 'A1 + M2 + M3 + WW',
    },
}
