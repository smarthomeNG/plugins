#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab

"""commands/lookups for Viessmann model V200HO1C"""

MODEL = 'V200HO1C'

commands = {
    'Allgemein': {
        # Allgemein
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
        'Frostgefahr': {
            'read': True,
            'write': False,
            'opcode': '2510',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # Frostgefahr
        'Anlagenleistung': {
            'read': True,
            'write': False,
            'opcode': 'a38f',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2},
        },  # Anlagenleistung
        'Temperatur': {
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
        },
    },
    'Kessel': {
        # Kessel
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
        'Abgastemperatur': {
            'read': True,
            'write': False,
            'opcode': '0816',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'mult': 10, 'len': 2},
        },  # Abgastemperatur
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
        },  # Speicherladepumpe für Warmwasser
        'Zirkulation': {
            'read': True,
            'write': True,
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
        'Heizkreis_1': {
            'read': True,
            'write': False,
            'opcode': '2906',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # Heizkreispumpe A1
        'Heizkreis_2': {
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
        'Starts': {
            'read': True,
            'write': False,
            'opcode': '088a',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'signed': True, 'len': 4},
        },  # Brennerstarts
        'Leistung': {
            'read': True,
            'write': False,
            'opcode': 'a305',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2},
        },  # Brennerleistung
        'Betriebsstunden': {
            'read': True,
            'write': False,
            'opcode': '08a7',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'mult': 3600, 'len': 4},
        },  # Brenner-Betriebsstunden
    },
    'Solar': {
        # Solar
        'Pumpe': {
            'read': True,
            'write': False,
            'opcode': '6552',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # Solarpumpe
        'Kollektortemperatur': {
            'read': True,
            'write': False,
            'opcode': '6564',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2},
        },  # Kollektortemperatur
        'Speichertemperatur': {
            'read': True,
            'write': False,
            'opcode': '6566',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'mult': 10, 'len': 2},
        },  # Spichertemperatur
        'Betriebsstunden': {
            'read': True,
            'write': False,
            'opcode': '6568',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'mult': 100, 'len': 4},
        },  # Solar Betriebsstunden
        'Waermemenge': {
            'read': True,
            'write': False,
            'opcode': '6560',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 2},
        },  # Solar Waermemenge
        'Ausbeute': {
            'read': True,
            'write': False,
            'opcode': 'cf30',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 4},
        },  # Solar Ausbeute
    },
    'Heizkreis': {
        '1': {
            # Heizkreis 1
            'Betriebsart': {
                'read': True,
                'write': True,
                'opcode': '2500',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'len': 1},
                'cmd_settings': {'force_min': 0, 'force_max': 3},
            },  # Betriebsart (0=Abschaltbetrieb, 1=Red. Betrieb, 2=Normalbetrieb (Schaltuhr), 3=Normalbetrieb (Dauernd))
            'Heizart': {
                'read': True,
                'write': True,
                'opcode': '2323',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'len': 1},
                'cmd_settings': {'force_min': 0, 'force_max': 4},
            },  # Heizart     (0=Abschaltbetrieb, 1=Nur Warmwasser, 2=Heizen und Warmwasser, 3=Normalbetrieb (Reduziert), 4=Normalbetrieb (Dauernd))
            'Temperatur': {
                'Vorlauf_Soll': {
                    'read': True,
                    'write': False,
                    'opcode': '2544',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'mult': 10, 'len': 2},
                },  # Vorlauftemperatur Soll
                'Vorlauf_Ist': {
                    'read': True,
                    'write': False,
                    'opcode': '2900',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'mult': 10, 'len': 2},
                },  # Vorlauftemperatur Ist
            },
        },
        '2': {
            # Heizkreis 2
            'Betriebsart': {
                'read': True,
                'write': True,
                'opcode': '3500',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'len': 1},
                'cmd_settings': {'force_min': 0, 'force_max': 3},
            },  # Betriebsart (0=Abschaltbetrieb, 1=Red. Betrieb, 2=Normalbetrieb (Schaltuhr), 3=Normalbetrieb (Dauernd))
            'Heizart': {
                'read': True,
                'write': True,
                'opcode': '3323',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'len': 1},
                'cmd_settings': {'force_min': 0, 'force_max': 4},
            },  # Heizart     (0=Abschaltbetrieb, 1=Nur Warmwasser, 2=Heizen und Warmwasser, 3=Normalbetrieb (Reduziert), 4=Normalbetrieb (Dauernd))
            'Temperatur': {
                'Vorlauf_Soll': {
                    'read': True,
                    'write': False,
                    'opcode': '3544',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'mult': 10, 'len': 2},
                },  # Vorlauftemperatur Soll
                'Vorlauf_Ist': {
                    'read': True,
                    'write': False,
                    'opcode': '3900',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'mult': 10, 'len': 2},
                },  # Vorlauftemperatur Ist
            },
        },
    },
    'Warmwasser': {
        # Warmwasser
        'Ist': {
            'read': True,
            'write': False,
            'opcode': '0812',
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
        'Austritt': {
            'read': True,
            'write': False,
            'opcode': '0814',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'mult': 10, 'len': 2},
        },  # Warmwasseraustrittstemperatur in Grad C
    },
}

lookups = {
    'operatingmodes': {
        '00': 'Abschaltbetrieb',
        '01': 'Warmwasser',
        '02': 'Heizen und Warmwasser',
        '03': 'Normal reduziert',
        '04': 'Normal dauernd',
    },
    'systemschemes': {'01': 'WW', '02': 'HK + WW', '04': 'HK + WW', '05': 'HK + WW'},
}
