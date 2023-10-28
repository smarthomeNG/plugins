# !/usr/bin/env python
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# Copyright 2023 Michael Wenzel
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#  AVM for SmartHomeNG.  https://github.com/smarthomeNG//
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

import ruamel.yaml

FILENAME_ATTRIBUTES = 'item_attributes.py'

FILENAME_PLUGIN = 'plugin.yaml'

DOC_FILE_NAME = 'user_doc.rst'

PLUGIN_VERSION = '1.2.6'

ITEM_ATTRIBUTES = {
    'db_addon_fct': {
        'verbrauch_heute':                         {'cat': 'verbrauch',     'on': 'change', 'sub_cat': 'onchange',   'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Verbrauch am heutigen Tag (Differenz zwischen aktuellem Wert und den Wert am Ende des vorherigen Tages)'},
        'verbrauch_tag':                           {'cat': 'verbrauch',     'on': 'change', 'sub_cat': 'onchange',   'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Verbrauch am heutigen Tag (Differenz zwischen aktuellem Wert und den Wert am Ende des vorherigen Tages)'},
        'verbrauch_woche':                         {'cat': 'verbrauch',     'on': 'change', 'sub_cat': 'onchange',   'item_type': 'num',   'calc': 'weekly',    'params': False,  'description': 'Verbrauch in der aktuellen Woche'},
        'verbrauch_monat':                         {'cat': 'verbrauch',     'on': 'change', 'sub_cat': 'onchange',   'item_type': 'num',   'calc': 'monthly',   'params': False,  'description': 'Verbrauch im aktuellen Monat'},
        'verbrauch_jahr':                          {'cat': 'verbrauch',     'on': 'change', 'sub_cat': 'onchange',   'item_type': 'num',   'calc': 'yearly',    'params': False,  'description': 'Verbrauch im aktuellen Jahr'},
        'verbrauch_last_24h':                      {'cat': 'verbrauch',     'on': 'demand', 'sub_cat': 'last',       'item_type': 'num',   'calc': 'hourly',    'params': False,  'description': 'Verbrauch innerhalb letzten 24h'},
        'verbrauch_last_7d':                       {'cat': 'verbrauch',     'on': 'demand', 'sub_cat': 'last',       'item_type': 'num',   'calc': 'hourly',    'params': False,  'description': 'Verbrauch innerhalb letzten 7 Tage'},
        'verbrauch_heute_minus1':                  {'cat': 'verbrauch',     'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Verbrauch gestern (heute -1 Tag) (Differenz zwischen Wert am Ende des gestrigen Tages und dem Wert am Ende des Tages davor)'},
        'verbrauch_heute_minus2':                  {'cat': 'verbrauch',     'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Verbrauch vorgestern (heute -2 Tage)'},
        'verbrauch_heute_minus3':                  {'cat': 'verbrauch',     'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Verbrauch heute -3 Tage'},
        'verbrauch_heute_minus4':                  {'cat': 'verbrauch',     'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Verbrauch heute -4 Tage'},
        'verbrauch_heute_minus5':                  {'cat': 'verbrauch',     'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Verbrauch heute -5 Tage'},
        'verbrauch_heute_minus6':                  {'cat': 'verbrauch',     'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Verbrauch heute -6 Tage'},
        'verbrauch_heute_minus7':                  {'cat': 'verbrauch',     'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Verbrauch heute -7 Tage'},
        'verbrauch_heute_minus8':                  {'cat': 'verbrauch',     'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Verbrauch heute -8 Tage'},
        'verbrauch_tag_minus1':                    {'cat': 'verbrauch',     'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Verbrauch gestern (heute -1 Tag) (Differenz zwischen Wert am Ende des gestrigen Tages und dem Wert am Ende des Tages davor)'},
        'verbrauch_tag_minus2':                    {'cat': 'verbrauch',     'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Verbrauch vorgestern (heute -2 Tage)'},
        'verbrauch_tag_minus3':                    {'cat': 'verbrauch',     'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Verbrauch heute -3 Tage'},
        'verbrauch_tag_minus4':                    {'cat': 'verbrauch',     'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Verbrauch heute -4 Tage'},
        'verbrauch_tag_minus5':                    {'cat': 'verbrauch',     'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Verbrauch heute -5 Tage'},
        'verbrauch_tag_minus6':                    {'cat': 'verbrauch',     'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Verbrauch heute -6 Tage'},
        'verbrauch_tag_minus7':                    {'cat': 'verbrauch',     'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Verbrauch heute -7 Tage'},
        'verbrauch_tag_minus8':                    {'cat': 'verbrauch',     'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Verbrauch heute -8 Tage'},
        'verbrauch_woche_minus1':                  {'cat': 'verbrauch',     'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'weekly',    'params': False,  'description': 'Verbrauch Vorwoche (aktuelle Woche -1)'},
        'verbrauch_woche_minus2':                  {'cat': 'verbrauch',     'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'weekly',    'params': False,  'description': 'Verbrauch aktuelle Woche -2 Wochen'},
        'verbrauch_woche_minus3':                  {'cat': 'verbrauch',     'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'weekly',    'params': False,  'description': 'Verbrauch aktuelle Woche -3 Wochen'},
        'verbrauch_woche_minus4':                  {'cat': 'verbrauch',     'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'weekly',    'params': False,  'description': 'Verbrauch aktuelle Woche -4 Wochen'},
        'verbrauch_monat_minus1':                  {'cat': 'verbrauch',     'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'monthly',   'params': False,  'description': 'Verbrauch Vormonat (aktueller Monat -1)'},
        'verbrauch_monat_minus2':                  {'cat': 'verbrauch',     'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'monthly',   'params': False,  'description': 'Verbrauch aktueller Monat -2 Monate'},
        'verbrauch_monat_minus3':                  {'cat': 'verbrauch',     'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'monthly',   'params': False,  'description': 'Verbrauch aktueller Monat -3 Monate'},
        'verbrauch_monat_minus4':                  {'cat': 'verbrauch',     'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'monthly',   'params': False,  'description': 'Verbrauch aktueller Monat -4 Monate'},
        'verbrauch_monat_minus12':                 {'cat': 'verbrauch',     'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'monthly',   'params': False,  'description': 'Verbrauch aktueller Monat -12 Monate'},
        'verbrauch_jahr_minus1':                   {'cat': 'verbrauch',     'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'yearly',    'params': False,  'description': 'Verbrauch Vorjahr (aktuelles Jahr -1 Jahr)'},
        'verbrauch_jahr_minus2':                   {'cat': 'verbrauch',     'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'yearly',    'params': False,  'description': 'Verbrauch aktuelles Jahr -2 Jahre'},
        'verbrauch_jahr_minus3':                   {'cat': 'verbrauch',     'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'yearly',    'params': False,  'description': 'Verbrauch aktuelles Jahr -3 Jahre'},
        'verbrauch_rolling_12m_heute_minus1':      {'cat': 'verbrauch',     'on': 'demand', 'sub_cat': 'rolling',    'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Verbrauch der letzten 12 Monate ausgehend im Ende des letzten Tages'},
        'verbrauch_rolling_12m_tag_minus1':        {'cat': 'verbrauch',     'on': 'demand', 'sub_cat': 'rolling',    'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Verbrauch der letzten 12 Monate ausgehend im Ende des letzten Tages'},
        'verbrauch_rolling_12m_woche_minus1':      {'cat': 'verbrauch',     'on': 'demand', 'sub_cat': 'rolling',    'item_type': 'num',   'calc': 'weekly',    'params': False,  'description': 'Verbrauch der letzten 12 Monate ausgehend im Ende der letzten Woche'},
        'verbrauch_rolling_12m_monat_minus1':      {'cat': 'verbrauch',     'on': 'demand', 'sub_cat': 'rolling',    'item_type': 'num',   'calc': 'monthly',   'params': False,  'description': 'Verbrauch der letzten 12 Monate ausgehend im Ende des letzten Monats'},
        'verbrauch_rolling_12m_jahr_minus1':       {'cat': 'verbrauch',     'on': 'demand', 'sub_cat': 'rolling',    'item_type': 'num',   'calc': 'yearly',    'params': False,  'description': 'Verbrauch der letzten 12 Monate ausgehend im Ende des letzten Jahres'},
        'verbrauch_jahreszeitraum_minus1':         {'cat': 'verbrauch',     'on': 'demand', 'sub_cat': 'jahrzeit',   'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Verbrauch seit dem 1.1. bis zum heutigen Tag des Vorjahres'},
        'verbrauch_jahreszeitraum_minus2':         {'cat': 'verbrauch',     'on': 'demand', 'sub_cat': 'jahrzeit',   'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Verbrauch seit dem 1.1. bis zum heutigen Tag vor 2 Jahren'},
        'verbrauch_jahreszeitraum_minus3':         {'cat': 'verbrauch',     'on': 'demand', 'sub_cat': 'jahrzeit',   'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Verbrauch seit dem 1.1. bis zum heutigen Tag vor 3 Jahren'},
        'zaehlerstand_heute_minus1':               {'cat': 'zaehler',       'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Zählerstand / Wert am Ende des letzten Tages (heute -1 Tag)'},
        'zaehlerstand_heute_minus2':               {'cat': 'zaehler',       'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Zählerstand / Wert am Ende des vorletzten Tages (heute -2 Tag)'},
        'zaehlerstand_heute_minus3':               {'cat': 'zaehler',       'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Zählerstand / Wert am Ende des vorvorletzten Tages (heute -3 Tag)'},
        'zaehlerstand_tag_minus1':                 {'cat': 'zaehler',       'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Zählerstand / Wert am Ende des letzten Tages (heute -1 Tag)'},
        'zaehlerstand_tag_minus2':                 {'cat': 'zaehler',       'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Zählerstand / Wert am Ende des vorletzten Tages (heute -2 Tag)'},
        'zaehlerstand_tag_minus3':                 {'cat': 'zaehler',       'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Zählerstand / Wert am Ende des vorvorletzten Tages (heute -3 Tag)'},
        'zaehlerstand_woche_minus1':               {'cat': 'zaehler',       'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'weekly',    'params': False,  'description': 'Zählerstand / Wert am Ende der vorvorletzten Woche (aktuelle Woche -1 Woche)'},
        'zaehlerstand_woche_minus2':               {'cat': 'zaehler',       'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'weekly',    'params': False,  'description': 'Zählerstand / Wert am Ende der vorletzten Woche (aktuelle Woche -2 Wochen)'},
        'zaehlerstand_woche_minus3':               {'cat': 'zaehler',       'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'weekly',    'params': False,  'description': 'Zählerstand / Wert am Ende der aktuellen Woche -3 Wochen'},
        'zaehlerstand_monat_minus1':               {'cat': 'zaehler',       'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'monthly',   'params': False,  'description': 'Zählerstand / Wert am Ende des letzten Monates (aktueller Monat -1 Monat)'},
        'zaehlerstand_monat_minus2':               {'cat': 'zaehler',       'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'monthly',   'params': False,  'description': 'Zählerstand / Wert am Ende des vorletzten Monates (aktueller Monat -2 Monate)'},
        'zaehlerstand_monat_minus3':               {'cat': 'zaehler',       'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'monthly',   'params': False,  'description': 'Zählerstand / Wert am Ende des aktuellen Monats -3 Monate'},
        'zaehlerstand_jahr_minus1':                {'cat': 'zaehler',       'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'yearly',    'params': False,  'description': 'Zählerstand / Wert am Ende des letzten Jahres (aktuelles Jahr -1 Jahr)'},
        'zaehlerstand_jahr_minus2':                {'cat': 'zaehler',       'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'yearly',    'params': False,  'description': 'Zählerstand / Wert am Ende des vorletzten Jahres (aktuelles Jahr -2 Jahre)'},
        'zaehlerstand_jahr_minus3':                {'cat': 'zaehler',       'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'yearly',    'params': False,  'description': 'Zählerstand / Wert am Ende des aktuellen Jahres -3 Jahre'},
        'minmax_last_24h_min':                     {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'last',       'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'minimaler Wert der letzten 24h'},
        'minmax_last_24h_max':                     {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'last',       'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'maximaler Wert der letzten 24h'},
        'minmax_last_24h_avg':                     {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'last',       'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'durchschnittlicher Wert der letzten 24h'},
        'minmax_last_7d_min':                      {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'last',       'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'minimaler Wert der letzten 7 Tage'},
        'minmax_last_7d_max':                      {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'last',       'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'maximaler Wert der letzten 7 Tage'},
        'minmax_last_7d_avg':                      {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'last',       'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'durchschnittlicher Wert der letzten 7 Tage'},
        'minmax_heute_min':                        {'cat': 'wertehistorie', 'on': 'change', 'sub_cat': 'onchange',   'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Minimalwert seit Tagesbeginn'},
        'minmax_heute_max':                        {'cat': 'wertehistorie', 'on': 'change', 'sub_cat': 'onchange',   'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Maximalwert seit Tagesbeginn'},
        'minmax_heute_avg':                        {'cat': 'wertehistorie', 'on': 'change', 'sub_cat': 'onchange',   'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Durschnittswert seit Tagesbeginn'},
        'minmax_heute_minus1_min':                 {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Minimalwert gestern (heute -1 Tag)'},
        'minmax_heute_minus1_max':                 {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Maximalwert gestern (heute -1 Tag)'},
        'minmax_heute_minus1_avg':                 {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Durchschnittswert gestern (heute -1 Tag)'},
        'minmax_heute_minus2_min':                 {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Minimalwert vorgestern (heute -2 Tage)'},
        'minmax_heute_minus2_max':                 {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Maximalwert vorgestern (heute -2 Tage)'},
        'minmax_heute_minus2_avg':                 {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Durchschnittswert vorgestern (heute -2 Tage)'},
        'minmax_heute_minus3_min':                 {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Minimalwert heute vor 3 Tagen'},
        'minmax_heute_minus3_max':                 {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Maximalwert heute vor 3 Tagen'},
        'minmax_heute_minus3_avg':                 {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Durchschnittswert heute vor 3 Tagen'},
        'minmax_tag_min':                          {'cat': 'wertehistorie', 'on': 'change', 'sub_cat': 'onchange',   'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Minimalwert seit Tagesbeginn'},
        'minmax_tag_max':                          {'cat': 'wertehistorie', 'on': 'change', 'sub_cat': 'onchange',   'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Maximalwert seit Tagesbeginn'},
        'minmax_tag_avg':                          {'cat': 'wertehistorie', 'on': 'change', 'sub_cat': 'onchange',   'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Durschnittswert seit Tagesbeginn'},
        'minmax_tag_minus1_min':                   {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Minimalwert gestern (heute -1 Tag)'},
        'minmax_tag_minus1_max':                   {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Maximalwert gestern (heute -1 Tag)'},
        'minmax_tag_minus1_avg':                   {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Durchschnittswert gestern (heute -1 Tag)'},
        'minmax_tag_minus2_min':                   {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Minimalwert vorgestern (heute -2 Tage)'},
        'minmax_tag_minus2_max':                   {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Maximalwert vorgestern (heute -2 Tage)'},
        'minmax_tag_minus2_avg':                   {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Durchschnittswert vorgestern (heute -2 Tage)'},
        'minmax_tag_minus3_min':                   {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Minimalwert heute vor 3 Tagen'},
        'minmax_tag_minus3_max':                   {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Maximalwert heute vor 3 Tagen'},
        'minmax_tag_minus3_avg':                   {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Durchschnittswert heute vor 3 Tagen'},
        'minmax_woche_min':                        {'cat': 'wertehistorie', 'on': 'change', 'sub_cat': 'onchange',   'item_type': 'num',   'calc': 'weekly',    'params': False,  'description': 'Minimalwert seit Wochenbeginn'},
        'minmax_woche_max':                        {'cat': 'wertehistorie', 'on': 'change', 'sub_cat': 'onchange',   'item_type': 'num',   'calc': 'weekly',    'params': False,  'description': 'Maximalwert seit Wochenbeginn'},
        'minmax_woche_minus1_min':                 {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'weekly',    'params': False,  'description': 'Minimalwert Vorwoche (aktuelle Woche -1)'},
        'minmax_woche_minus1_max':                 {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'weekly',    'params': False,  'description': 'Maximalwert Vorwoche (aktuelle Woche -1)'},
        'minmax_woche_minus1_avg':                 {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'weekly',    'params': False,  'description': 'Durchschnittswert Vorwoche (aktuelle Woche -1)'},
        'minmax_woche_minus2_min':                 {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'weekly',    'params': False,  'description': 'Minimalwert aktuelle Woche -2 Wochen'},
        'minmax_woche_minus2_max':                 {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'weekly',    'params': False,  'description': 'Maximalwert aktuelle Woche -2 Wochen'},
        'minmax_woche_minus2_avg':                 {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'weekly',    'params': False,  'description': 'Durchschnittswert aktuelle Woche -2 Wochen'},
        'minmax_monat_min':                        {'cat': 'wertehistorie', 'on': 'change', 'sub_cat': 'onchange',   'item_type': 'num',   'calc': 'monthly',   'params': False,  'description': 'Minimalwert seit Monatsbeginn'},
        'minmax_monat_max':                        {'cat': 'wertehistorie', 'on': 'change', 'sub_cat': 'onchange',   'item_type': 'num',   'calc': 'monthly',   'params': False,  'description': 'Maximalwert seit Monatsbeginn'},
        'minmax_monat_minus1_min':                 {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'monthly',   'params': False,  'description': 'Minimalwert Vormonat (aktueller Monat -1)'},
        'minmax_monat_minus1_max':                 {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'monthly',   'params': False,  'description': 'Maximalwert Vormonat (aktueller Monat -1)'},
        'minmax_monat_minus1_avg':                 {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'monthly',   'params': False,  'description': 'Durchschnittswert Vormonat (aktueller Monat -1)'},
        'minmax_monat_minus2_min':                 {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'monthly',   'params': False,  'description': 'Minimalwert aktueller Monat -2 Monate'},
        'minmax_monat_minus2_max':                 {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'monthly',   'params': False,  'description': 'Maximalwert aktueller Monat -2 Monate'},
        'minmax_monat_minus2_avg':                 {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'monthly',   'params': False,  'description': 'Durchschnittswert aktueller Monat -2 Monate'},
        'minmax_jahr_min':                         {'cat': 'wertehistorie', 'on': 'change', 'sub_cat': 'onchange',   'item_type': 'num',   'calc': 'yearly',    'params': False,  'description': 'Minimalwert seit Jahresbeginn'},
        'minmax_jahr_max':                         {'cat': 'wertehistorie', 'on': 'change', 'sub_cat': 'onchange',   'item_type': 'num',   'calc': 'yearly',    'params': False,  'description': 'Maximalwert seit Jahresbeginn'},
        'minmax_jahr_minus1_min':                  {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'yearly',    'params': False,  'description': 'Minimalwert Vorjahr (aktuelles Jahr -1 Jahr)'},
        'minmax_jahr_minus1_max':                  {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'yearly',    'params': False,  'description': 'Maximalwert Vorjahr (aktuelles Jahr -1 Jahr)'},
        'minmax_jahr_minus1_avg':                  {'cat': 'wertehistorie', 'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'yearly',    'params': False,  'description': 'Durchschnittswert Vorjahr (aktuelles Jahr -1 Jahr)'},
        'tagesmitteltemperatur_heute':             {'cat': 'tagesmittel',   'on': 'change', 'sub_cat': 'onchange',   'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Tagesmitteltemperatur heute'},
        'tagesmitteltemperatur_heute_minus1':      {'cat': 'tagesmittel',   'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Tagesmitteltemperatur des letzten Tages (heute -1 Tag)'},
        'tagesmitteltemperatur_heute_minus2':      {'cat': 'tagesmittel',   'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Tagesmitteltemperatur des vorletzten Tages (heute -2 Tag)'},
        'tagesmitteltemperatur_heute_minus3':      {'cat': 'tagesmittel',   'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Tagesmitteltemperatur des vorvorletzten Tages (heute -3 Tag)'},
        'tagesmitteltemperatur_tag':               {'cat': 'tagesmittel',   'on': 'change', 'sub_cat': 'onchange',   'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Tagesmitteltemperatur heute'},
        'tagesmitteltemperatur_tag_minus1':        {'cat': 'tagesmittel',   'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Tagesmitteltemperatur des letzten Tages (heute -1 Tag)'},
        'tagesmitteltemperatur_tag_minus2':        {'cat': 'tagesmittel',   'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Tagesmitteltemperatur des vorletzten Tages (heute -2 Tag)'},
        'tagesmitteltemperatur_tag_minus3':        {'cat': 'tagesmittel',   'on': 'demand', 'sub_cat': 'timeframe',  'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Tagesmitteltemperatur des vorvorletzten Tages (heute -3 Tag)'},
        'serie_minmax_monat_min_15m':              {'cat': 'serie',         'on': 'demand', 'sub_cat': 'minmax',     'item_type': 'list',  'calc': 'monthly',   'params': False,  'description': 'monatlicher Minimalwert der letzten 15 Monate (gleitend)'},
        'serie_minmax_monat_max_15m':              {'cat': 'serie',         'on': 'demand', 'sub_cat': 'minmax',     'item_type': 'list',  'calc': 'monthly',   'params': False,  'description': 'monatlicher Maximalwert der letzten 15 Monate (gleitend)'},
        'serie_minmax_monat_avg_15m':              {'cat': 'serie',         'on': 'demand', 'sub_cat': 'minmax',     'item_type': 'list',  'calc': 'monthly',   'params': False,  'description': 'monatlicher Mittelwert der letzten 15 Monate (gleitend)'},
        'serie_minmax_woche_min_30w':              {'cat': 'serie',         'on': 'demand', 'sub_cat': 'minmax',     'item_type': 'list',  'calc': 'weekly',    'params': False,  'description': 'wöchentlicher Minimalwert der letzten 30 Wochen (gleitend)'},
        'serie_minmax_woche_max_30w':              {'cat': 'serie',         'on': 'demand', 'sub_cat': 'minmax',     'item_type': 'list',  'calc': 'weekly',    'params': False,  'description': 'wöchentlicher Maximalwert der letzten 30 Wochen (gleitend)'},
        'serie_minmax_woche_avg_30w':              {'cat': 'serie',         'on': 'demand', 'sub_cat': 'minmax',     'item_type': 'list',  'calc': 'weekly',    'params': False,  'description': 'wöchentlicher Mittelwert der letzten 30 Wochen (gleitend)'},
        'serie_minmax_tag_min_30d':                {'cat': 'serie',         'on': 'demand', 'sub_cat': 'minmax',     'item_type': 'list',  'calc': 'daily',     'params': False,  'description': 'täglicher Minimalwert der letzten 30 Tage (gleitend)'},
        'serie_minmax_tag_max_30d':                {'cat': 'serie',         'on': 'demand', 'sub_cat': 'minmax',     'item_type': 'list',  'calc': 'daily',     'params': False,  'description': 'täglicher Maximalwert der letzten 30 Tage (gleitend)'},
        'serie_minmax_tag_avg_30d':                {'cat': 'serie',         'on': 'demand', 'sub_cat': 'minmax',     'item_type': 'list',  'calc': 'daily',     'params': False,  'description': 'täglicher Mittelwert der letzten 30 Tage (gleitend)'},
        'serie_verbrauch_tag_30d':                 {'cat': 'serie',         'on': 'demand', 'sub_cat': 'verbrauch',  'item_type': 'list',  'calc': 'daily',     'params': False,  'description': 'Verbrauch pro Tag der letzten 30 Tage'},
        'serie_verbrauch_woche_30w':               {'cat': 'serie',         'on': 'demand', 'sub_cat': 'verbrauch',  'item_type': 'list',  'calc': 'weekly',    'params': False,  'description': 'Verbrauch pro Woche der letzten 30 Wochen'},
        'serie_verbrauch_monat_18m':               {'cat': 'serie',         'on': 'demand', 'sub_cat': 'verbrauch',  'item_type': 'list',  'calc': 'monthly',   'params': False,  'description': 'Verbrauch pro Monat der letzten 18 Monate'},
        'serie_zaehlerstand_tag_30d':              {'cat': 'serie',         'on': 'demand', 'sub_cat': 'zaehler',    'item_type': 'list',  'calc': 'daily',     'params': False,  'description': 'Zählerstand am Tagesende der letzten 30 Tage'},
        'serie_zaehlerstand_woche_30w':            {'cat': 'serie',         'on': 'demand', 'sub_cat': 'zaehler',    'item_type': 'list',  'calc': 'weekly',    'params': False,  'description': 'Zählerstand am Wochenende der letzten 30 Wochen'},
        'serie_zaehlerstand_monat_18m':            {'cat': 'serie',         'on': 'demand', 'sub_cat': 'zaehler',    'item_type': 'list',  'calc': 'monthly',   'params': False,  'description': 'Zählerstand am Monatsende der letzten 18 Monate'},
        'serie_waermesumme_monat_24m':             {'cat': 'serie',         'on': 'demand', 'sub_cat': 'summe',      'item_type': 'list',  'calc': 'monthly',   'params': False,  'description': 'monatliche Wärmesumme der letzten 24 Monate'},
        'serie_kaeltesumme_monat_24m':             {'cat': 'serie',         'on': 'demand', 'sub_cat': 'summe',      'item_type': 'list',  'calc': 'monthly',   'params': False,  'description': 'monatliche Kältesumme der letzten 24 Monate'},
        'serie_tagesmittelwert_0d':                {'cat': 'serie',         'on': 'demand', 'sub_cat': 'mittel_d',   'item_type': 'list',  'calc': 'daily',     'params': False,  'description': 'Tagesmittelwert für den aktuellen Tag'},
        'serie_tagesmittelwert_stunde_0d':         {'cat': 'serie',         'on': 'demand', 'sub_cat': 'mittel_h',   'item_type': 'list',  'calc': 'daily',     'params': False,  'description': 'Stundenmittelwert für den aktuellen Tag'},
        'serie_tagesmittelwert_stunde_30_0d':      {'cat': 'serie',         'on': 'demand', 'sub_cat': 'mittel_h1',  'item_type': 'list',  'calc': 'daily',     'params': False,  'description': 'Stundenmittelwert für den aktuellen Tag'},
        'serie_tagesmittelwert_tag_stunde_30d':    {'cat': 'serie',         'on': 'demand', 'sub_cat': 'mittel_d_h', 'item_type': 'list',  'calc': 'daily',     'params': False,  'description': 'Stundenmittelwert pro Tag der letzten 30 Tage (bspw. zur Berechnung der Tagesmitteltemperatur basierend auf den Mittelwert der Temperatur pro Stunde'},
        'general_oldest_value':                    {'cat': 'gen',           'on': 'demand', 'sub_cat': None,         'item_type': 'num',   'calc': 'None',      'params': False,  'description': 'Ausgabe des ältesten Wertes des entsprechenden "Parent-Items" mit database Attribut'},
        'general_oldest_log':                      {'cat': 'gen',           'on': 'demand', 'sub_cat': None,         'item_type': 'list',  'calc': 'None',      'params': False,  'description': 'Ausgabe des Timestamp des ältesten Eintrages des entsprechenden "Parent-Items" mit database Attribut'},
        'kaeltesumme':                             {'cat': 'summe',         'on': 'demand', 'sub_cat': None,         'item_type': 'num',   'calc': 'daily',     'params': True,   'description': 'Berechnet die Kältesumme für einen Zeitraum, db_addon_params: (year=optional, month=optional)'},
        'waermesumme':                             {'cat': 'summe',         'on': 'demand', 'sub_cat': None,         'item_type': 'num',   'calc': 'daily',     'params': True,   'description': 'Berechnet die Wärmesumme für einen Zeitraum, db_addon_params: (year=optional, month=optional)'},
        'gruenlandtempsumme':                      {'cat': 'summe',         'on': 'demand', 'sub_cat': None,         'item_type': 'num',   'calc': 'daily',     'params': True,   'description': 'Berechnet die Grünlandtemperatursumme für einen Zeitraum, db_addon_params: (year=optional)'},
        'wachstumsgradtage':                       {'cat': 'summe',         'on': 'demand', 'sub_cat': None,         'item_type': 'num',   'calc': 'daily',     'params': True,   'description': 'Berechnet die Wachstumsgradtage auf Basis der stündlichen Durchschnittswerte eines Tages für das laufende Jahr mit an Angabe des Temperaturschwellenwertes (threshold=Schwellentemperatur)'},
        'wuestentage':                             {'cat': 'summe',         'on': 'demand', 'sub_cat': 'kenntage',   'item_type': 'num',   'calc': 'daily',     'params': True,   'description': 'Berechnet die Anzahl der Wüstentage des Jahres, db_addon_params: (year=optional)'},
        'heisse_tage':                             {'cat': 'summe',         'on': 'demand', 'sub_cat': 'kenntage',   'item_type': 'num',   'calc': 'daily',     'params': True,   'description': 'Berechnet die Anzahl der heissen Tage des Jahres, db_addon_params: (year=optional)'},
        'tropennaechte':                           {'cat': 'summe',         'on': 'demand', 'sub_cat': 'kenntage',   'item_type': 'num',   'calc': 'daily',     'params': True,   'description': 'Berechnet die Anzahl der Tropennächte des Jahres, db_addon_params: (year=optional)'},
        'sommertage':                              {'cat': 'summe',         'on': 'demand', 'sub_cat': 'kenntage',   'item_type': 'num',   'calc': 'daily',     'params': True,   'description': 'Berechnet die Anzahl der Sommertage des Jahres, db_addon_params: (year=optional)'},
        'heiztage':                                {'cat': 'summe',         'on': 'demand', 'sub_cat': 'kenntage',   'item_type': 'num',   'calc': 'daily',     'params': True,   'description': 'Berechnet die Anzahl der Heiztage des Jahres, db_addon_params: (year=optional)'},
        'vegetationstage':                         {'cat': 'summe',         'on': 'demand', 'sub_cat': 'kenntage',   'item_type': 'num',   'calc': 'daily',     'params': True,   'description': 'Berechnet die Anzahl der Vegatationstage des Jahres, db_addon_params: (year=optional)'},
        'frosttage':                               {'cat': 'summe',         'on': 'demand', 'sub_cat': 'kenntage',   'item_type': 'num',   'calc': 'daily',     'params': True,   'description': 'Berechnet die Anzahl der Frosttage des Jahres, db_addon_params: (year=optional)'},
        'eistage':                                 {'cat': 'summe',         'on': 'demand', 'sub_cat': 'kenntage',   'item_type': 'num',   'calc': 'daily',     'params': True,   'description': 'Berechnet die Anzahl der Eistage des Jahres, db_addon_params: (year=optional)'},
        'tagesmitteltemperatur':                   {'cat': 'complex',       'on': 'demand', 'sub_cat': None,         'item_type': 'list',  'calc': 'daily',     'params': True,   'description': 'Berechnet die Tagesmitteltemperatur auf Basis der stündlichen Durchschnittswerte eines Tages für die angegebene Anzahl von Tagen (timeframe=day, count=integer)'},
        'db_request':                              {'cat': 'complex',       'on': 'demand', 'sub_cat': None,         'item_type': 'list',  'calc': 'group',     'params': True,   'description': 'Abfrage der DB: db_addon_params: (func=mandatory, item=mandatory, timespan=mandatory, start=optional, end=optional, count=optional, group=optional, group2=optional)'},
        'minmax':                                  {'cat': 'complex',       'on': 'demand', 'sub_cat': None,         'item_type': 'num',   'calc': 'timeframe', 'params': True,   'description': 'Berechnet einen min/max/avg Wert für einen bestimmen Zeitraum:  db_addon_params: (func=mandatory, timeframe=mandatory, start=mandatory)'},
        'minmax_last':                             {'cat': 'complex',       'on': 'demand', 'sub_cat': None,         'item_type': 'num',   'calc': 'timeframe', 'params': True,   'description': 'Berechnet einen min/max/avg Wert für ein bestimmtes Zeitfenster von jetzt zurück:  db_addon_params: (func=mandatory, timeframe=mandatory, start=mandatory, end=mandatory)'},
        'verbrauch':                               {'cat': 'complex',       'on': 'demand', 'sub_cat': None,         'item_type': 'num',   'calc': 'timeframe', 'params': True,   'description': 'Berechnet einen Verbrauchswert für einen bestimmen Zeitraum:  db_addon_params: (timeframe=mandatory, start=mandatory end=mandatory)'},
        'zaehlerstand':                            {'cat': 'complex',       'on': 'demand', 'sub_cat': None,         'item_type': 'num',   'calc': 'timeframe', 'params': True,   'description': 'Berechnet einen Zählerstand für einen bestimmen Zeitpunkt:  db_addon_params: (timeframe=mandatory, start=mandatory)'},
    },
    'db_addon_info': {
        'db_version':                              {'cat': 'info',                                                   'item_type': 'str',   'calc': 'no',        'params': False,  'description': 'Version der verbundenen Datenbank'},
    },                                                                                                               
    'db_addon_admin': {                                                                                              
        'suspend':                                 {'cat': 'admin',                                                  'item_type': 'bool',  'calc': 'no',        'params': False,  'description': 'Unterbricht die Aktivitäten des Plugin'},
        'recalc_all':                              {'cat': 'admin',                                                  'item_type': 'bool',  'calc': 'no',        'params': False,  'description': 'Startet einen Neuberechnungslauf aller on-demand Items'},
        'clean_cache_values':                      {'cat': 'admin',                                                  'item_type': 'bool',  'calc': 'no',        'params': False,  'description': 'Löscht Plugin-Cache und damit alle im Plugin zwischengespeicherten Werte'},
    },
}

FILE_HEADER = """\
# !/usr/bin/env python
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# Copyright 2023 Michael Wenzel
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#  DatabaseAddOn for SmartHomeNG.  https://github.com/smarthomeNG//
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


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
#
#                                 THIS FILE IS AUTOMATICALLY CREATED BY USING item_attributes_master.py
#
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

"""


def get_attrs(sub_dict: dict = {}) -> list:
    attributes = []
    for entry in ITEM_ATTRIBUTES:
        for db_addon_fct in ITEM_ATTRIBUTES[entry]:
            if sub_dict.items() <= ITEM_ATTRIBUTES[entry][db_addon_fct].items():
                attributes.append(db_addon_fct)
    return attributes


def export_item_attributes_py():

    print()
    print(f"A) Start generation of {FILENAME_ATTRIBUTES}")

    ATTRS = dict()
    ATTRS['ONCHANGE_ATTRIBUTES'] = get_attrs(sub_dict={'on': 'change'})
    ATTRS['ONCHANGE_HOURLY_ATTRIBUTES'] = get_attrs(sub_dict={'on': 'change', 'calc': 'hourly'})
    ATTRS['ONCHANGE_DAILY_ATTRIBUTES'] = get_attrs(sub_dict={'on': 'change', 'calc': 'daily'})
    ATTRS['ONCHANGE_WEEKLY_ATTRIBUTES'] = get_attrs(sub_dict={'on': 'change', 'calc': 'weekly'})
    ATTRS['ONCHANGE_MONTHLY_ATTRIBUTES'] = get_attrs(sub_dict={'on': 'change', 'calc': 'monthly'})
    ATTRS['ONCHANGE_YEARLY_ATTRIBUTES'] = get_attrs(sub_dict={'on': 'change', 'calc': 'yearly'})
    ATTRS['ONDEMAND_ATTRIBUTES'] = get_attrs(sub_dict={'on': 'demand'})
    ATTRS['ONDEMAND_HOURLY_ATTRIBUTES'] = get_attrs(sub_dict={'on': 'demand', 'calc': 'hourly'})
    ATTRS['ONDEMAND_DAILY_ATTRIBUTES'] = get_attrs(sub_dict={'on': 'demand', 'calc': 'daily'})
    ATTRS['ONDEMAND_WEEKLY_ATTRIBUTES'] = get_attrs(sub_dict={'on': 'demand', 'calc': 'weekly'})
    ATTRS['ONDEMAND_MONTHLY_ATTRIBUTES'] = get_attrs(sub_dict={'on': 'demand', 'calc': 'monthly'})
    ATTRS['ONDEMAND_YEARLY_ATTRIBUTES'] = get_attrs(sub_dict={'on': 'demand', 'calc': 'yearly'})
    ATTRS['ALL_HOURLY_ATTRIBUTES'] = get_attrs(sub_dict={'calc': 'hourly'})
    ATTRS['ALL_DAILY_ATTRIBUTES'] = get_attrs(sub_dict={'calc': 'daily'})
    ATTRS['ALL_WEEKLY_ATTRIBUTES'] = get_attrs(sub_dict={'calc': 'weekly'})
    ATTRS['ALL_MONTHLY_ATTRIBUTES'] = get_attrs(sub_dict={'calc': 'monthly'})
    ATTRS['ALL_YEARLY_ATTRIBUTES'] = get_attrs(sub_dict={'calc': 'yearly'})
    ATTRS['ALL_PARAMS_ATTRIBUTES'] = get_attrs(sub_dict={'params': True})
    ATTRS['ALL_VERBRAUCH_ATTRIBUTES'] = get_attrs(sub_dict={'cat': 'verbrauch'})
    ATTRS['VERBRAUCH_ATTRIBUTES_ONCHANGE'] = get_attrs(sub_dict={'cat': 'verbrauch', 'sub_cat': 'onchange'})
    ATTRS['VERBRAUCH_ATTRIBUTES_TIMEFRAME'] = get_attrs(sub_dict={'cat': 'verbrauch', 'sub_cat': 'timeframe'})
    ATTRS['VERBRAUCH_ATTRIBUTES_LAST'] = get_attrs(sub_dict={'cat': 'verbrauch', 'sub_cat': 'last'})
    ATTRS['VERBRAUCH_ATTRIBUTES_ROLLING'] = get_attrs(sub_dict={'cat': 'verbrauch', 'sub_cat': 'rolling'})
    ATTRS['VERBRAUCH_ATTRIBUTES_JAHRESZEITRAUM'] = get_attrs(sub_dict={'cat': 'verbrauch', 'sub_cat': 'jahrzeit'})
    ATTRS['ALL_ZAEHLERSTAND_ATTRIBUTES'] = get_attrs(sub_dict={'cat': 'zaehler'})
    ATTRS['ZAEHLERSTAND_ATTRIBUTES_TIMEFRAME'] = get_attrs(sub_dict={'cat': 'zaehler', 'sub_cat': 'timeframe'})
    ATTRS['ALL_HISTORIE_ATTRIBUTES'] = get_attrs(sub_dict={'cat': 'wertehistorie'})
    ATTRS['HISTORIE_ATTRIBUTES_ONCHANGE'] = get_attrs(sub_dict={'cat': 'wertehistorie', 'sub_cat': 'onchange'})
    ATTRS['HISTORIE_ATTRIBUTES_LAST'] = get_attrs(sub_dict={'cat': 'wertehistorie', 'sub_cat': 'last'})
    ATTRS['HISTORIE_ATTRIBUTES_TIMEFRAME'] = get_attrs(sub_dict={'cat': 'wertehistorie', 'sub_cat': 'timeframe'})
    ATTRS['ALL_TAGESMITTEL_ATTRIBUTES'] = get_attrs(sub_dict={'cat': 'tagesmittel'})
    ATTRS['TAGESMITTEL_ATTRIBUTES_ONCHANGE'] = get_attrs(sub_dict={'cat': 'tagesmittel', 'sub_cat': 'onchange'})
    ATTRS['TAGESMITTEL_ATTRIBUTES_TIMEFRAME'] = get_attrs(sub_dict={'cat': 'tagesmittel', 'sub_cat': 'timeframe'})
    ATTRS['ALL_SERIE_ATTRIBUTES'] = get_attrs(sub_dict={'cat': 'serie'})
    ATTRS['SERIE_ATTRIBUTES_MINMAX'] = get_attrs(sub_dict={'cat': 'serie', 'sub_cat': 'minmax'})
    ATTRS['SERIE_ATTRIBUTES_ZAEHLERSTAND'] = get_attrs(sub_dict={'cat': 'serie', 'sub_cat': 'zaehler'})
    ATTRS['SERIE_ATTRIBUTES_VERBRAUCH'] = get_attrs(sub_dict={'cat': 'serie', 'sub_cat': 'verbrauch'})
    ATTRS['SERIE_ATTRIBUTES_SUMME'] = get_attrs(sub_dict={'cat': 'serie', 'sub_cat': 'summe'})
    ATTRS['SERIE_ATTRIBUTES_MITTEL_D'] = get_attrs(sub_dict={'cat': 'serie', 'sub_cat': 'mittel_d'})
    ATTRS['SERIE_ATTRIBUTES_MITTEL_H'] = get_attrs(sub_dict={'cat': 'serie', 'sub_cat': 'mittel_h'})
    ATTRS['SERIE_ATTRIBUTES_MITTEL_H1'] = get_attrs(sub_dict={'cat': 'serie', 'sub_cat': 'mittel_h1'})
    ATTRS['SERIE_ATTRIBUTES_MITTEL_D_H'] = get_attrs(sub_dict={'cat': 'serie', 'sub_cat': 'mittel_d_h'})
    ATTRS['ALL_GEN_ATTRIBUTES'] = get_attrs(sub_dict={'cat': 'gen'})
    ATTRS['ALL_SUMME_ATTRIBUTES'] = get_attrs(sub_dict={'cat': 'summe'})
    ATTRS['ALL_COMPLEX_ATTRIBUTES'] = get_attrs(sub_dict={'cat': 'complex'})
    ATTRS['TAGESMITTEL_ATTRIBUTES_ONCHANGE'] = get_attrs(sub_dict={'cat': 'tagesmittel', 'sub_cat': 'onchange'})

    for entry in ATTRS['HISTORIE_ATTRIBUTES_ONCHANGE']:
        if entry.endswith('avg'):
            ATTRS['TAGESMITTEL_ATTRIBUTES_ONCHANGE'].append(entry)

    # create file and write header
    f = open(FILENAME_ATTRIBUTES, "w")
    f.write(FILE_HEADER)
    f.close()

    # write avm_data_types
    for attr, alist in ATTRS.items():
        with open(FILENAME_ATTRIBUTES, "a") as f:
            print(f'{attr} = {alist!r}', file=f)

    print(f"   {FILENAME_ATTRIBUTES} successfully generated.")


def create_plugin_yaml_item_attribute_valids(attribute):
    """Create valid_list of db_addon_fct based on master dict"""

    valid_list_str =         """        # NOTE: valid_list is automatically created by using item_attributes_master.py"""
    valid_list_desc_str =    """        # NOTE: valid_list_description is automatically created by using item_attributes_master.py"""
    valid_list_item_type =   """        # NOTE: valid_list_item_type is automatically created by using item_attributes_master.py"""
    valid_list_calculation = """        # NOTE: valid_list_calculation is automatically created by using item_attributes_master.py"""

    for db_addon_fct in ITEM_ATTRIBUTES[attribute]:
        valid_list_str = f"""{valid_list_str}\n\
          - {db_addon_fct!r:<40}"""

        valid_list_desc_str = f"""{valid_list_desc_str}\n\
          - '{ITEM_ATTRIBUTES[attribute][db_addon_fct]['description']:<}'"""

        valid_list_item_type = f"""{valid_list_item_type}\n\
          - '{ITEM_ATTRIBUTES[attribute][db_addon_fct]['item_type']:<}'"""

        valid_list_calculation = f"""{valid_list_calculation}\n\
          - '{ITEM_ATTRIBUTES[attribute][db_addon_fct]['calc']:<}'"""

    valid_list_calculation = f"""{valid_list_calculation}\n\r"""

    return valid_list_str, valid_list_desc_str, valid_list_item_type, valid_list_calculation


def update_plugin_yaml_item_attributes():
    """Update 'valid_list', 'valid_list_description', 'valid_list_item_type' and 'valid_list_calculation' of item attributes in plugin.yaml"""

    print()
    print(f"B) Start updating valid for attributes in {FILENAME_PLUGIN}")

    for attribute in ITEM_ATTRIBUTES:

        print(f"   Attribute {attribute} in progress")

        yaml = ruamel.yaml.YAML()
        yaml.indent(mapping=4, sequence=4, offset=4)
        yaml.width = 200
        yaml.allow_unicode = True
        yaml.preserve_quotes = False

        valid_list_str, valid_list_desc_str, valid_list_item_type_str, valid_list_calc_str = create_plugin_yaml_item_attribute_valids(attribute)

        with open(FILENAME_PLUGIN, 'r', encoding="utf-8") as f:
            data = yaml.load(f)

        if data.get('item_attributes', {}).get(attribute):
            data['item_attributes'][attribute]['valid_list'] = yaml.load(valid_list_str)
            data['item_attributes'][attribute]['valid_list_description'] = yaml.load(valid_list_desc_str)
            data['item_attributes'][attribute]['valid_list_item_type'] = yaml.load(valid_list_item_type_str)
            data['item_attributes'][attribute]['valid_list_calculation'] = yaml.load(valid_list_calc_str)

            with open(FILENAME_PLUGIN, 'w', encoding="utf-8") as f:
                yaml.dump(data, f)
            print(f"   Successfully updated Attribute '{attribute}' in plugin.yaml!")
        else:
            print(f"   Attribute '{attribute}' not defined in plugin.yaml")


def check_plugin_yaml_structs():
    # check structs for wrong attributes
    print()
    print(f'C) Checking used attributes in structs defined in {FILENAME_PLUGIN} ')

    # open plugin.yaml and update
    yaml = ruamel.yaml.YAML()
    yaml.indent(mapping=4, sequence=4, offset=4)
    yaml.width = 200
    yaml.allow_unicode = True
    yaml.preserve_quotes = False
    with open(FILENAME_PLUGIN, 'r', encoding="utf-8") as f:
        data = yaml.load(f)

    structs = data.get('item_structs')

    def get_all_keys(d):
        for key, value in d.items():
            yield key, value
            if isinstance(value, dict):
                yield from get_all_keys(value)

    attr_valid = True

    if structs:
        for attr, attr_val in get_all_keys(structs):
            if attr in ITEM_ATTRIBUTES:
                if attr_val not in ITEM_ATTRIBUTES[attr].keys():
                    print(f"    - {attr_val} not a valid value for {ITEM_ATTRIBUTES[attr]}")
                    attr_valid = False

    if attr_valid:
        print(f"   All used attributes are valid.")

    print(f'   Check complete.')


def update_user_doc():
    # Update user_doc.rst
    print()
    print(f'D) Start updating DB-Addon-Attributes and descriptions in {DOC_FILE_NAME}!"')
    attribute_list = [
        "Dieses Kapitel wurde automatisch durch Ausführen des Skripts in der Datei 'item_attributes_master.py' erstellt.\n", "\n",
        "Nachfolgend eine Auflistung der möglichen Attribute für das Plugin im Format: Attribute: Beschreibung | Berechnungszyklus | Item-Type\n",
        "\n"]

    for attribute in ITEM_ATTRIBUTES:
        attribute_list.append("\n")
        attribute_list.append(f"{attribute}\n")
        attribute_list.append('-' * len(attribute))
        attribute_list.append("\n")
        attribute_list.append("\n")

        for db_addon_fct in ITEM_ATTRIBUTES[attribute]:
            attribute_list.append(f"- {db_addon_fct}: {ITEM_ATTRIBUTES[attribute][db_addon_fct]['description']} "
                                  f"| Berechnung: {ITEM_ATTRIBUTES[attribute][db_addon_fct]['calc']} "
                                  f"| Item-Type: {ITEM_ATTRIBUTES[attribute][db_addon_fct]['item_type']}\n")
            attribute_list.append("\n")

    with open(DOC_FILE_NAME, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    start = end = None
    for i, line in enumerate(lines):
        if 'db_addon Item-Attribute' in line:
            start = i + 3
        if 'Hinweise' in line:
            end = i - 1

    part1 = lines[0:start]
    part3 = lines[end:len(lines)]
    new_lines = part1 + attribute_list + part3

    with open(DOC_FILE_NAME, 'w', encoding='utf-8') as file:
        for line in new_lines:
            file.write(line)

    print(f"   Successfully updated Foshk-Attributes in {DOC_FILE_NAME}!")


if __name__ == '__main__':

    print(f'Start automated update and check of {FILENAME_PLUGIN} with generation of {FILENAME_ATTRIBUTES} and update of {DOC_FILE_NAME}.')
    print('-------------------------------------------------------------')

    export_item_attributes_py()

    update_plugin_yaml_item_attributes()

    check_plugin_yaml_structs()

    update_user_doc()

    print()
    print(f'Automated update and check of {FILENAME_PLUGIN} and generation of {FILENAME_ATTRIBUTES} complete.')
