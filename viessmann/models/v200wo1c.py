#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab

"""commands/lookups for Viessmann model V200WO1C"""

MODEL = 'V200WO1C'

commands = {
    'Allgemein': {
        'item_attrs': {'cyclic': True},
        'Temperatur': {
            'Aussen': {
                'read': True,
                'write': False,
                'opcode': '0101',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2},
            }  # getTempA -- Information - Allgemein: Aussentemperatur (-40..70)
        },
        # Anlagenstatus
        'Betriebsart': {
            'read': True,
            'write': True,
            'opcode': 'b000',
            'reply_pattern': '*',
            'item_type': 'str',
            'dev_datatype': 'Hex',
            'params': {'value': 'VAL', 'len': 1},
            'lookup': 'operatingmodes',
            'item_attrs': {'initial': True, 'lookup_item': True},
        },  # getBetriebsart -- Bedienung HK1 - Heizkreis 1: Betriebsart (Textstring)
        'Manuell': {
            'read': True,
            'write': True,
            'opcode': 'b020',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
            'cmd_settings': {'force_min': 0, 'force_max': 2},
        },  # getManuell / setManuell -- 0 = normal, 1 = manueller Heizbetrieb, 2 = 1x Warmwasser auf Temp2
        # Allgemein
        'Outdoor_Fanspeed': {
            'read': True,
            'write': False,
            'opcode': '1a52',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # getSpdFanOut -- Outdoor Fanspeed
        'Status_Fanspeed': {
            'read': True,
            'write': False,
            'opcode': '1a53',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # getSpdFan -- Geschwindigkeit Luefter
        'Kompressor_Freq': {
            'read': True,
            'write': False,
            'opcode': '1a54',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # getSpdKomp -- Compressor Frequency
        'SollLeistung_Verdichter': {
            'read': True,
            'write': False,
            'opcode': '5030',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # getPwrSollVerdichter -- Diagnose - Anlagenuebersicht: Soll-Leistung Verdichter 1 (0..100)
    },
    'Pumpen': {
        'Sekundaer': {
            'read': True,
            'write': False,
            'opcode': '0484',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # getStatusSekP -- Diagnose - Anlagenuebersicht: Sekundaerpumpe 1 (0..1)
        'Heizkreis': {
            'read': True,
            'write': False,
            'opcode': '048d',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # getStatusPumpe -- Information - Heizkreis HK1: Heizkreispumpe (0..1)
        'Zirkulation': {
            'read': True,
            'write': False,
            'opcode': '0490',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # getStatusPumpeZirk -- Information - Warmwasser: Zirkulationspumpe (0..1)
    },
    'Heizkreis': {
        'Temperatur': {
            'Raum': {
                'Soll': {
                    'read': True,
                    'write': False,
                    'opcode': '2000',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2},
                },  # getTempRaumSollNormal -- Bedienung HK1 - Heizkreis 1: Raumsolltemperatur normal (10..30)
                'Soll_Reduziert': {
                    'read': True,
                    'write': False,
                    'opcode': '2001',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2},
                },  # getTempRaumSollRed -- Bedienung HK1 - Heizkreis 1: Raumsolltemperatur reduzierter Betrieb (10..30)
                'Soll_Party': {
                    'read': True,
                    'write': False,
                    'opcode': '2022',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2},
                },  # getTempRaumSollParty -- Bedienung HK1 - Heizkreis 1: Party Solltemperatur (10..30)
            },
            'Vorlauf': {
                'Ist': {
                    'read': True,
                    'write': False,
                    'opcode': '0105',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2},
                    'item_attrs': {'cyclic': True},
                },  # getTempSekVL -- Information - Heizkreis HK1: Vorlauftemperatur Sekundaer 1 (0..95)
                'Soll': {
                    'read': True,
                    'write': False,
                    'opcode': '1800',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2},
                },  # getTempVLSoll -- Diagnose - Heizkreis HK1: Vorlaufsolltemperatur HK1 (0..95)
                'Mittel': {
                    'read': True,
                    'write': False,
                    'opcode': '16b2',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2},
                },  # getTempSekVLMittel -- Statistik - Energiebilanz: mittlere sek. Vorlauftemperatur (0..95)
            },
            'Ruecklauf': {
                'Ist': {
                    'read': True,
                    'write': False,
                    'opcode': '0106',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2},
                    'item_attrs': {'cyclic': True},
                },  # getTempSekRL -- Diagnose - Anlagenuebersicht: Ruecklauftemperatur Sekundaer 1 (0..95)
                'Mittel': {
                    'read': True,
                    'write': False,
                    'opcode': '16b3',
                    'reply_pattern': '*',
                    'item_type': 'num',
                    'dev_datatype': 'Number',
                    'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2},
                },  # getTempSekRLMittel -- Statistik - Energiebilanz: mittlere sek.Temperatur RL1 (0..95)
            },
        },
        'Heizkennlinie': {
            'Niveau': {
                'read': True,
                'write': False,
                'opcode': '2006',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2},
            },  # getHKLNiveau -- Bedienung HK1 - Heizkreis 1: Niveau der Heizkennlinie (-15..40)
            'Neigung': {
                'read': True,
                'write': False,
                'opcode': '2007',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2},
            },  # getHKLNeigung -- Bedienung HK1 - Heizkreis 1: Neigung der Heizkennlinie (0..35)
        },
    },
    'Warmwasser': {
        'Ist': {
            'read': True,
            'write': False,
            'opcode': '010d',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2},
            'item_attrs': {'cyclic': True},
        },  # getTempWWIstOben -- Information - Warmwasser: Warmwassertemperatur oben (0..95)
        'Soll': {
            'read': True,
            'write': True,
            'opcode': '6000',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'mult': 10, 'signed': True, 'len': 2},
            'cmd_settings': {'force_min': 10, 'force_max': 60},
        },  # getTempWWSoll -- Bedienung WW - Betriebsdaten WW: Warmwassersolltemperatur (10..60 (95))
        'Ventil': {
            'read': True,
            'write': False,
            'opcode': '0494',
            'reply_pattern': '*',
            'item_type': 'bool',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # getStatusVentilWW -- Diagnose - Waermepumpe: 3-W-Ventil Heizen WW1 (0 (Heizen)..1 (WW))
    },
    'Statistik': {
        'item_attrs': {'cycle': 600},
        # Statistiken / Laufzeiten
        'Einschaltungen': {
            'Sekundaer': {
                'read': True,
                'write': False,
                'opcode': '0504',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'len': 4},
            },  # getAnzQuelleSek -- Statistik - Schaltzyklen Anlage: Einschaltungen Sekundaerquelle (?)
            'Heizstab1': {
                'read': True,
                'write': False,
                'opcode': '0508',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'len': 4},
            },  # getAnzHeizstabSt1 -- Statistik - Schaltzyklen Anlage: Einschaltungen Heizstab Stufe 1 (?)
            'Heizstab2': {
                'read': True,
                'write': False,
                'opcode': '0509',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'len': 4},
            },  # getAnzHeizstabSt2 -- Statistik - Schaltzyklen Anlage: Einschaltungen Heizstab Stufe 2 (?)
            'Heizkreis': {
                'read': True,
                'write': False,
                'opcode': '050d',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'len': 4},
            },  # getAnzHK -- Statistik - Schaltzyklen Anlage: Einschaltungen Heizkreis (?)
        },
        'Laufzeiten': {
            'Sekundaer': {
                'read': True,
                'write': False,
                'opcode': '0584',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'mult': 3600, 'len': 4},
            },  # getLZPumpeSek -- Statistik - Betriebsstunden Anlage: Betriebsstunden Sekundaerpumpe (?)
            'Heizstab1': {
                'read': True,
                'write': False,
                'opcode': '0588',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'mult': 3600, 'len': 4},
            },  # getLZHeizstabSt1 -- Statistik - Betriebsstunden Anlage: Betriebsstunden Heizstab Stufe 1 (?)
            'Heizstab2': {
                'read': True,
                'write': False,
                'opcode': '0589',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'mult': 3600, 'len': 4},
            },  # getLZHeizstabSt2 -- Statistik - Betriebsstunden Anlage: Betriebsstunden Heizstab Stufe 2 (?)
            'Heizkreis': {
                'read': True,
                'write': False,
                'opcode': '058d',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'mult': 3600, 'len': 4},
            },  # getLZPumpe -- Statistik - Betriebsstunden Anlage: Betriebsstunden Pumpe HK1 (0..1150000)
            'Ventil': {
                'read': True,
                'write': False,
                'opcode': '0594',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'mult': 3600, 'len': 4},
            },  # getLZVentilWW -- Statistik - Betriebsstunden Anlage: Betriebsstunden Warmwasserventil (?)
            'VerdichterStufe1': {
                'read': True,
                'write': False,
                'opcode': '1620',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'len': 4},
            },  # getLZVerdSt1 -- Statistik - Betriebsstunden Anlage: Betriebsstunden Verdichter auf Stufe 1 (?)
            'VerdichterStufe2': {
                'read': True,
                'write': False,
                'opcode': '1622',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'len': 4},
            },  # getLZVerdSt2 -- Statistik - Betriebsstunden Anlage: Betriebsstunden Verdichter auf Stufe 2 (?)
            'VerdichterStufe3': {
                'read': True,
                'write': False,
                'opcode': '1624',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'len': 4},
            },  # getLZVerdSt3 -- Statistik - Betriebsstunden Anlage: Betriebsstunden Verdichter auf Stufe 3 (?)
            'VerdichterStufe4': {
                'read': True,
                'write': False,
                'opcode': '1626',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'len': 4},
            },  # getLZVerdSt4 -- Statistik - Betriebsstunden Anlage: Betriebsstunden Verdichter auf Stufe 4 (?)
            'VerdichterStufe5': {
                'read': True,
                'write': False,
                'opcode': '1628',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'len': 4},
            },  # getLZVerdSt5 -- Statistik - Betriebsstunden Anlage: Betriebsstunden Verdichter auf Stufe 5 (?)
            'VerdichterWP': {
                'read': True,
                'write': False,
                'opcode': '5005',
                'reply_pattern': '*',
                'item_type': 'num',
                'dev_datatype': 'Number',
                'params': {'value': 'VAL', 'mult': 3600, 'len': 4},
            },  # getLZWP -- Statistik - Betriebsstunden Anlage: Betriebsstunden Waermepumpe  (0..1150000)
        },
        'OAT_Temperature': {
            'read': True,
            'write': False,
            'opcode': '1a5c',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # getTempOAT -- OAT Temperature
        'ICT_Temperature': {
            'read': True,
            'write': False,
            'opcode': '1a5d',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # getTempICT -- OCT Temperature
        'CCT_Temperature': {
            'read': True,
            'write': False,
            'opcode': '1a5e',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # getTempCCT -- CCT Temperature
        'HST_Temperature': {
            'read': True,
            'write': False,
            'opcode': '1a5f',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # getTempHST -- HST Temperature
        'OMT_Temperature': {
            'read': True,
            'write': False,
            'opcode': '1a60',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'len': 1},
        },  # getTempOMT -- OMT Temperature
        'WaermeWW12M': {
            'read': True,
            'write': False,
            'opcode': '1660',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'mult': 10, 'len': 4},
        },  # Wärmeenergie für WW-Bereitung der letzten 12 Monate (kWh)
        'ElektroWW12M': {
            'read': True,
            'write': False,
            'opcode': '1670',
            'reply_pattern': '*',
            'item_type': 'num',
            'dev_datatype': 'Number',
            'params': {'value': 'VAL', 'mult': 10, 'len': 4},
        },  # elektr. Energie für WW-Bereitung der letzten 12 Monate (kWh)
    },
}

lookups = {
    'operatingmodes': {
        '00': 'Abschaltbetrieb',
        '01': 'Warmwasser',
        '02': 'Heizen und Warmwasser',
        '03': 'undefiniert',
        '04': 'dauernd reduziert',
        '05': 'dauernd normal',
        '06': 'normal Abschalt',
        '07': 'nur kühlen',
    },
    'systemschemes': {'01': 'WW', '02': 'HK + WW', '04': 'HK + WW', '05': 'HK + WW'},
}
