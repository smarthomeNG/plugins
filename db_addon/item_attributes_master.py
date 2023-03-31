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

ITEM_ATTRIBUTS = {
    'DB_ADDON_FCTS': {
        'verbrauch_heute':                         {'cat': 'verbrauch',       'item_type': 'num',   'calc': 'onchange',  'params': False,  'description': 'Verbrauch am heutigen Tag (Differenz zwischen aktuellem Wert und den Wert am Ende des vorherigen Tages)'},
        'verbrauch_woche':                         {'cat': 'verbrauch',       'item_type': 'num',   'calc': 'onchange',  'params': False,  'description': 'Verbrauch in der aktuellen Woche'},
        'verbrauch_monat':                         {'cat': 'verbrauch',       'item_type': 'num',   'calc': 'onchange',  'params': False,  'description': 'Verbrauch im aktuellen Monat'},
        'verbrauch_jahr':                          {'cat': 'verbrauch',       'item_type': 'num',   'calc': 'onchange',  'params': False,  'description': 'Verbrauch im aktuellen Jahr'},
        'verbrauch_heute_minus1':                  {'cat': 'verbrauch',       'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Verbrauch gestern (heute -1 Tag) (Differenz zwischen Wert am Ende des gestrigen Tages und dem Wert am Ende des Tages danach)'},
        'verbrauch_heute_minus2':                  {'cat': 'verbrauch',       'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Verbrauch vorgestern (heute -2 Tage)'},
        'verbrauch_heute_minus3':                  {'cat': 'verbrauch',       'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Verbrauch heute -3 Tage'},
        'verbrauch_heute_minus4':                  {'cat': 'verbrauch',       'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Verbrauch heute -4 Tage'},
        'verbrauch_heute_minus5':                  {'cat': 'verbrauch',       'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Verbrauch heute -5 Tage'},
        'verbrauch_heute_minus6':                  {'cat': 'verbrauch',       'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Verbrauch heute -6 Tage'},
        'verbrauch_heute_minus7':                  {'cat': 'verbrauch',       'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Verbrauch heute -7 Tage'},
        'verbrauch_woche_minus1':                  {'cat': 'verbrauch',       'item_type': 'num',   'calc': 'weekly',    'params': False,  'description': 'Verbrauch Vorwoche (aktuelle Woche -1)'},
        'verbrauch_woche_minus2':                  {'cat': 'verbrauch',       'item_type': 'num',   'calc': 'weekly',    'params': False,  'description': 'Verbrauch aktuelle Woche -2 Wochen'},
        'verbrauch_woche_minus3':                  {'cat': 'verbrauch',       'item_type': 'num',   'calc': 'weekly',    'params': False,  'description': 'Verbrauch aktuelle Woche -3 Wochen'},
        'verbrauch_woche_minus4':                  {'cat': 'verbrauch',       'item_type': 'num',   'calc': 'weekly',    'params': False,  'description': 'Verbrauch aktuelle Woche -4 Wochen'},
        'verbrauch_monat_minus1':                  {'cat': 'verbrauch',       'item_type': 'num',   'calc': 'monthly',   'params': False,  'description': 'Verbrauch Vormonat (aktueller Monat -1)'},
        'verbrauch_monat_minus2':                  {'cat': 'verbrauch',       'item_type': 'num',   'calc': 'monthly',   'params': False,  'description': 'Verbrauch aktueller Monat -2 Monate'},
        'verbrauch_monat_minus3':                  {'cat': 'verbrauch',       'item_type': 'num',   'calc': 'monthly',   'params': False,  'description': 'Verbrauch aktueller Monat -3 Monate'},
        'verbrauch_monat_minus4':                  {'cat': 'verbrauch',       'item_type': 'num',   'calc': 'monthly',   'params': False,  'description': 'Verbrauch aktueller Monat -4 Monate'},
        'verbrauch_monat_minus12':                 {'cat': 'verbrauch',       'item_type': 'num',   'calc': 'monthly',   'params': False,  'description': 'Verbrauch aktueller Monat -12 Monate'},
        'verbrauch_jahr_minus1':                   {'cat': 'verbrauch',       'item_type': 'num',   'calc': 'yearly',    'params': False,  'description': 'Verbrauch Vorjahr (aktuelles Jahr -1 Jahr)'},
        'verbrauch_jahr_minus2':                   {'cat': 'verbrauch',       'item_type': 'num',   'calc': 'yearly',    'params': False,  'description': 'Verbrauch aktuelles Jahr -2 Jahre'},
        'verbrauch_rolling_12m_heute_minus1':      {'cat': 'verbrauch',       'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Verbrauch der letzten 12 Monate ausgehend im Ende des letzten Tages'},
        'verbrauch_rolling_12m_woche_minus1':      {'cat': 'verbrauch',       'item_type': 'num',   'calc': 'weekly',    'params': False,  'description': 'Verbrauch der letzten 12 Monate ausgehend im Ende der letzten Woche'},
        'verbrauch_rolling_12m_monat_minus1':      {'cat': 'verbrauch',       'item_type': 'num',   'calc': 'monthly',   'params': False,  'description': 'Verbrauch der letzten 12 Monate ausgehend im Ende des letzten Monats'},
        'verbrauch_rolling_12m_jahr_minus1':       {'cat': 'verbrauch',       'item_type': 'num',   'calc': 'yearly',    'params': False,  'description': 'Verbrauch der letzten 12 Monate ausgehend im Ende des letzten Jahres'},
        'verbrauch_jahreszeitraum_minus1':         {'cat': 'verbrauch',       'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Verbrauch seit dem 1.1. bis zum heutigen Tag des Vorjahres'},
        'verbrauch_jahreszeitraum_minus2':         {'cat': 'verbrauch',       'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Verbrauch seit dem 1.1. bis zum heutigen Tag vor 2 Jahren'},
        'verbrauch_jahreszeitraum_minus3':         {'cat': 'verbrauch',       'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Verbrauch seit dem 1.1. bis zum heutigen Tag vor 3 Jahren'},
        'zaehlerstand_heute_minus1':               {'cat': 'zaehler',         'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Zählerstand / Wert am Ende des letzten Tages (heute -1 Tag)'},
        'zaehlerstand_heute_minus2':               {'cat': 'zaehler',         'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Zählerstand / Wert am Ende des vorletzten Tages (heute -2 Tag)'},
        'zaehlerstand_heute_minus3':               {'cat': 'zaehler',         'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Zählerstand / Wert am Ende des vorvorletzten Tages (heute -3 Tag)'},
        'zaehlerstand_woche_minus1':               {'cat': 'zaehler',         'item_type': 'num',   'calc': 'weekly',    'params': False,  'description': 'Zählerstand / Wert am Ende der vorvorletzten Woche (aktuelle Woche -1 Woche)'},
        'zaehlerstand_woche_minus2':               {'cat': 'zaehler',         'item_type': 'num',   'calc': 'weekly',    'params': False,  'description': 'Zählerstand / Wert am Ende der vorletzten Woche (aktuelle Woche -2 Wochen)'},
        'zaehlerstand_woche_minus3':               {'cat': 'zaehler',         'item_type': 'num',   'calc': 'weekly',    'params': False,  'description': 'Zählerstand / Wert am Ende der aktuellen Woche -3 Wochen'},
        'zaehlerstand_monat_minus1':               {'cat': 'zaehler',         'item_type': 'num',   'calc': 'monthly',   'params': False,  'description': 'Zählerstand / Wert am Ende des letzten Monates (aktueller Monat -1 Monat)'},
        'zaehlerstand_monat_minus2':               {'cat': 'zaehler',         'item_type': 'num',   'calc': 'monthly',   'params': False,  'description': 'Zählerstand / Wert am Ende des vorletzten Monates (aktueller Monat -2 Monate)'},
        'zaehlerstand_monat_minus3':               {'cat': 'zaehler',         'item_type': 'num',   'calc': 'monthly',   'params': False,  'description': 'Zählerstand / Wert am Ende des aktuellen Monats -3 Monate'},
        'zaehlerstand_jahr_minus1':                {'cat': 'zaehler',         'item_type': 'num',   'calc': 'yearly',    'params': False,  'description': 'Zählerstand / Wert am Ende des letzten Jahres (aktuelles Jahr -1 Jahr)'},
        'zaehlerstand_jahr_minus2':                {'cat': 'zaehler',         'item_type': 'num',   'calc': 'yearly',    'params': False,  'description': 'Zählerstand / Wert am Ende des vorletzten Jahres (aktuelles Jahr -2 Jahre)'},
        'zaehlerstand_jahr_minus3':                {'cat': 'zaehler',         'item_type': 'num',   'calc': 'yearly',    'params': False,  'description': 'Zählerstand / Wert am Ende des aktuellen Jahres -3 Jahre'},
        'minmax_last_24h_min':                     {'cat': 'wertehistorie',   'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'minimaler Wert der letzten 24h'},
        'minmax_last_24h_max':                     {'cat': 'wertehistorie',   'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'maximaler Wert der letzten 24h'},
        'minmax_last_24h_avg':                     {'cat': 'wertehistorie',   'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'durchschnittlicher Wert der letzten 24h'},
        'minmax_last_7d_min':                      {'cat': 'wertehistorie',   'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'minimaler Wert der letzten 7 Tage'},
        'minmax_last_7d_max':                      {'cat': 'wertehistorie',   'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'maximaler Wert der letzten 7 Tage'},
        'minmax_last_7d_avg':                      {'cat': 'wertehistorie',   'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'durchschnittlicher Wert der letzten 7 Tage'},
        'minmax_heute_min':                        {'cat': 'wertehistorie',   'item_type': 'num',   'calc': 'onchange',  'params': False,  'description': 'Minimalwert seit Tagesbeginn'},
        'minmax_heute_max':                        {'cat': 'wertehistorie',   'item_type': 'num',   'calc': 'onchange',  'params': False,  'description': 'Maximalwert seit Tagesbeginn'},
        'minmax_heute_minus1_min':                 {'cat': 'wertehistorie',   'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Minimalwert gestern (heute -1 Tag)'},
        'minmax_heute_minus1_max':                 {'cat': 'wertehistorie',   'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Maximalwert gestern (heute -1 Tag)'},
        'minmax_heute_minus1_avg':                 {'cat': 'wertehistorie',   'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Durchschnittswert gestern (heute -1 Tag)'},
        'minmax_heute_minus2_min':                 {'cat': 'wertehistorie',   'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Minimalwert vorgestern (heute -2 Tage)'},
        'minmax_heute_minus2_max':                 {'cat': 'wertehistorie',   'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Maximalwert vorgestern (heute -2 Tage)'},
        'minmax_heute_minus2_avg':                 {'cat': 'wertehistorie',   'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Durchschnittswert vorgestern (heute -2 Tage)'},
        'minmax_heute_minus3_min':                 {'cat': 'wertehistorie',   'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Minimalwert heute vor 3 Tagen'},
        'minmax_heute_minus3_max':                 {'cat': 'wertehistorie',   'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Maximalwert heute vor 3 Tagen'},
        'minmax_heute_minus3_avg':                 {'cat': 'wertehistorie',   'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Durchschnittswert heute vor 3 Tagen'},
        'minmax_woche_min':                        {'cat': 'wertehistorie',   'item_type': 'num',   'calc': 'onchange',  'params': False,  'description': 'Minimalwert seit Wochenbeginn'},
        'minmax_woche_max':                        {'cat': 'wertehistorie',   'item_type': 'num',   'calc': 'onchange',  'params': False,  'description': 'Maximalwert seit Wochenbeginn'},
        'minmax_woche_minus1_min':                 {'cat': 'wertehistorie',   'item_type': 'num',   'calc': 'weekly',    'params': False,  'description': 'Minimalwert Vorwoche (aktuelle Woche -1)'},
        'minmax_woche_minus1_max':                 {'cat': 'wertehistorie',   'item_type': 'num',   'calc': 'weekly',    'params': False,  'description': 'Maximalwert Vorwoche (aktuelle Woche -1)'},
        'minmax_woche_minus1_avg':                 {'cat': 'wertehistorie',   'item_type': 'num',   'calc': 'weekly',    'params': False,  'description': 'Durchschnittswert Vorwoche (aktuelle Woche -1)'},
        'minmax_woche_minus2_min':                 {'cat': 'wertehistorie',   'item_type': 'num',   'calc': 'weekly',    'params': False,  'description': 'Minimalwert aktuelle Woche -2 Wochen'},
        'minmax_woche_minus2_max':                 {'cat': 'wertehistorie',   'item_type': 'num',   'calc': 'weekly',    'params': False,  'description': 'Maximalwert aktuelle Woche -2 Wochen'},
        'minmax_woche_minus2_avg':                 {'cat': 'wertehistorie',   'item_type': 'num',   'calc': 'weekly',    'params': False,  'description': 'Durchschnittswert aktuelle Woche -2 Wochen'},
        'minmax_monat_min':                        {'cat': 'wertehistorie',   'item_type': 'num',   'calc': 'onchange',  'params': False,  'description': 'Minimalwert seit Monatsbeginn'},
        'minmax_monat_max':                        {'cat': 'wertehistorie',   'item_type': 'num',   'calc': 'onchange',  'params': False,  'description': 'Maximalwert seit Monatsbeginn'},
        'minmax_monat_minus1_min':                 {'cat': 'wertehistorie',   'item_type': 'num',   'calc': 'monthly',   'params': False,  'description': 'Minimalwert Vormonat (aktueller Monat -1)'},
        'minmax_monat_minus1_max':                 {'cat': 'wertehistorie',   'item_type': 'num',   'calc': 'monthly',   'params': False,  'description': 'Maximalwert Vormonat (aktueller Monat -1)'},
        'minmax_monat_minus1_avg':                 {'cat': 'wertehistorie',   'item_type': 'num',   'calc': 'monthly',   'params': False,  'description': 'Durchschnittswert Vormonat (aktueller Monat -1)'},
        'minmax_monat_minus2_min':                 {'cat': 'wertehistorie',   'item_type': 'num',   'calc': 'monthly',   'params': False,  'description': 'Minimalwert aktueller Monat -2 Monate'},
        'minmax_monat_minus2_max':                 {'cat': 'wertehistorie',   'item_type': 'num',   'calc': 'monthly',   'params': False,  'description': 'Maximalwert aktueller Monat -2 Monate'},
        'minmax_monat_minus2_avg':                 {'cat': 'wertehistorie',   'item_type': 'num',   'calc': 'monthly',   'params': False,  'description': 'Durchschnittswert aktueller Monat -2 Monate'},
        'minmax_jahr_min':                         {'cat': 'wertehistorie',   'item_type': 'num',   'calc': 'onchange',  'params': False,  'description': 'Minimalwert seit Jahresbeginn'},
        'minmax_jahr_max':                         {'cat': 'wertehistorie',   'item_type': 'num',   'calc': 'onchange',  'params': False,  'description': 'Maximalwert seit Jahresbeginn'},
        'minmax_jahr_minus1_min':                  {'cat': 'wertehistorie',   'item_type': 'num',   'calc': 'yearly',    'params': False,  'description': 'Minimalwert Vorjahr (aktuelles Jahr -1 Jahr)'},
        'minmax_jahr_minus1_max':                  {'cat': 'wertehistorie',   'item_type': 'num',   'calc': 'yearly',    'params': False,  'description': 'Maximalwert Vorjahr (aktuelles Jahr -1 Jahr)'},
        'minmax_jahr_minus1_avg':                  {'cat': 'wertehistorie',   'item_type': 'num',   'calc': 'yearly',    'params': False,  'description': 'Durchschnittswert Vorjahr (aktuelles Jahr -1 Jahr)'},
        'tagesmitteltemperatur_heute':             {'cat': 'tagesmittel',     'item_type': 'num',   'calc': 'onchange',  'params': False,  'description': 'Tagesmitteltemperatur heute'},
        'tagesmitteltemperatur_heute_minus1':      {'cat': 'tagesmittel',     'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Tagesmitteltemperatur des letzten Tages (heute -1 Tag)'},
        'tagesmitteltemperatur_heute_minus2':      {'cat': 'tagesmittel',     'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Tagesmitteltemperatur des vorletzten Tages (heute -2 Tag)'},
        'tagesmitteltemperatur_heute_minus3':      {'cat': 'tagesmittel',     'item_type': 'num',   'calc': 'daily',     'params': False,  'description': 'Tagesmitteltemperatur des vorvorletzten Tages (heute -3 Tag)'},
        'serie_minmax_monat_min_15m':              {'cat': 'serie',           'item_type': 'list',  'calc': 'monthly',   'params': False,  'description': 'monatlicher Minimalwert der letzten 15 Monate (gleitend)'},
        'serie_minmax_monat_max_15m':              {'cat': 'serie',           'item_type': 'list',  'calc': 'monthly',   'params': False,  'description': 'monatlicher Maximalwert der letzten 15 Monate (gleitend)'},
        'serie_minmax_monat_avg_15m':              {'cat': 'serie',           'item_type': 'list',  'calc': 'monthly',   'params': False,  'description': 'monatlicher Mittelwert der letzten 15 Monate (gleitend)'},
        'serie_minmax_woche_min_30w':              {'cat': 'serie',           'item_type': 'list',  'calc': 'weekly',    'params': False,  'description': 'wöchentlicher Minimalwert der letzten 30 Wochen (gleitend)'},
        'serie_minmax_woche_max_30w':              {'cat': 'serie',           'item_type': 'list',  'calc': 'weekly',    'params': False,  'description': 'wöchentlicher Maximalwert der letzten 30 Wochen (gleitend)'},
        'serie_minmax_woche_avg_30w':              {'cat': 'serie',           'item_type': 'list',  'calc': 'weekly',    'params': False,  'description': 'wöchentlicher Mittelwert der letzten 30 Wochen (gleitend)'},
        'serie_minmax_tag_min_30d':                {'cat': 'serie',           'item_type': 'list',  'calc': 'daily',     'params': False,  'description': 'täglicher Minimalwert der letzten 30 Tage (gleitend)'},
        'serie_minmax_tag_max_30d':                {'cat': 'serie',           'item_type': 'list',  'calc': 'daily',     'params': False,  'description': 'täglicher Maximalwert der letzten 30 Tage (gleitend)'},
        'serie_minmax_tag_avg_30d':                {'cat': 'serie',           'item_type': 'list',  'calc': 'daily',     'params': False,  'description': 'täglicher Mittelwert der letzten 30 Tage (gleitend)'},
        'serie_verbrauch_tag_30d':                 {'cat': 'serie',           'item_type': 'list',  'calc': 'daily',     'params': False,  'description': 'Verbrauch pro Tag der letzten 30 Tage'},
        'serie_verbrauch_woche_30w':               {'cat': 'serie',           'item_type': 'list',  'calc': 'weekly',    'params': False,  'description': 'Verbrauch pro Woche der letzten 30 Wochen'},
        'serie_verbrauch_monat_18m':               {'cat': 'serie',           'item_type': 'list',  'calc': 'monthly',   'params': False,  'description': 'Verbrauch pro Monat der letzten 18 Monate'},
        'serie_zaehlerstand_tag_30d':              {'cat': 'serie',           'item_type': 'list',  'calc': 'daily',     'params': False,  'description': 'Zählerstand am Tagesende der letzten 30 Tage'},
        'serie_zaehlerstand_woche_30w':            {'cat': 'serie',           'item_type': 'list',  'calc': 'weekly',    'params': False,  'description': 'Zählerstand am Wochenende der letzten 30 Wochen'},
        'serie_zaehlerstand_monat_18m':            {'cat': 'serie',           'item_type': 'list',  'calc': 'monthly',   'params': False,  'description': 'Zählerstand am Monatsende der letzten 18 Monate'},
        'serie_waermesumme_monat_24m':             {'cat': 'serie',           'item_type': 'list',  'calc': 'monthly',   'params': False,  'description': 'monatliche Wärmesumme der letzten 24 Monate'},
        'serie_kaeltesumme_monat_24m':             {'cat': 'serie',           'item_type': 'list',  'calc': 'monthly',   'params': False,  'description': 'monatliche Kältesumme der letzten 24 Monate'},
        'serie_tagesmittelwert_stunde_0d':         {'cat': 'serie',           'item_type': 'list',  'calc': 'daily',     'params': False,  'description': 'Stundenmittelwert für den aktuellen Tag'},
        'serie_tagesmittelwert_tag_stunde_30d':    {'cat': 'serie',           'item_type': 'list',  'calc': 'daily',     'params': False,  'description': 'Stundenmittelwert pro Tag der letzten 30 Tage (bspw. zur Berechnung der Tagesmitteltemperatur basierend auf den Mittelwert der Temperatur pro Stunde'},
        'general_oldest_value':                    {'cat': 'gen',             'item_type': 'num ',  'calc': False,       'params': False,  'description': 'Ausgabe des ältesten Wertes des entsprechenden "Parent-Items" mit database Attribut'},
        'general_oldest_log':                      {'cat': 'gen',             'item_type': 'list',  'calc': False,       'params': False,  'description': 'Ausgabe des Timestamp des ältesten Eintrages des entsprechenden "Parent-Items" mit database Attribut'},
        'kaeltesumme':                             {'cat': 'complex',         'item_type': 'num',   'calc': 'daily',     'params': True,   'description': 'Berechnet die Kältesumme für einen Zeitraum, db_addon_params: (year=mandatory, month=optional)'},
        'waermesumme':                             {'cat': 'complex',         'item_type': 'num',   'calc': 'daily',     'params': True,   'description': 'Berechnet die Wärmesumme für einen Zeitraum, db_addon_params: (year=mandatory, month=optional)'},
        'gruenlandtempsumme':                      {'cat': 'complex',         'item_type': 'num',   'calc': 'daily',     'params': True,   'description': 'Berechnet die Grünlandtemperatursumme für einen Zeitraum, db_addon_params: (year=mandatory)'},
        'tagesmitteltemperatur':                   {'cat': 'complex',         'item_type': 'list',  'calc': 'daily',     'params': True,   'description': 'Berechnet die Tagesmitteltemperatur auf Basis der stündlichen Durchschnittswerte eines Tages für die angegebene Anzahl von Tagen (timeframe=day, count=integer)'},
        'wachstumsgradtage':                       {'cat': 'complex',         'item_type': 'num',   'calc': 'daily',     'params': True,   'description': 'Berechnet die Wachstumsgradtage auf Basis der stündlichen Durchschnittswerte eines Tages für das laufende Jahr mit an Angabe des Temperaturschwellenwertes (threshold=Schwellentemperatur)'},
        'db_request':                              {'cat': 'complex',         'item_type': 'list',  'calc': 'group',     'params': True,   'description': 'Abfrage der DB: db_addon_params: (func=mandatory, item=mandatory, timespan=mandatory, start=optional, end=optional, count=optional, group=optional, group2=optional)'},
    },
    'DB_ADDON_INFO': {
        'db_version':                              {'cat': 'info',            'item_type': 'str',   'calc': False,       'params': False,  'description': 'Version der verbundenen Datenbank'},
    },
    'DB_ADDON_ADMIN': {
        'suspend':                                 {'cat': 'admin',           'item_type': 'bool',  'calc': False,       'params': False,  'description': 'Unterbricht die Aktivitäten des Plugin'},
        'recalc_all':                              {'cat': 'admin',           'item_type': 'bool',  'calc': False,       'params': False,  'description': 'Startet einen Neuberechnungslauf aller on-demand Items'},
        'clean_cache_values':                      {'cat': 'admin',           'item_type': 'bool',  'calc': False,       'params': False,  'description': 'Löscht Plugin-Cache und damit alle im Plugin zwischengespeicherten Werte'},
    },
}


def get_attrs(sub_dict: dict = {}) -> list:
    attributes = []
    for entry in ITEM_ATTRIBUTS:
        for db_addon_fct in ITEM_ATTRIBUTS[entry]:
            if sub_dict.items() <= ITEM_ATTRIBUTS[entry][db_addon_fct].items():
                attributes.append(db_addon_fct)
    return attributes


def export_db_addon_data():
    ATTRS = {}
    ATTRS['ALL_ONCHANGE_ATTRIBUTES'] = get_attrs(sub_dict={'calc': 'onchange'})
    ATTRS['ALL_DAILY_ATTRIBUTES'] = get_attrs(sub_dict={'calc': 'daily'})
    ATTRS['ALL_WEEKLY_ATTRIBUTES'] = get_attrs(sub_dict={'calc': 'weekly'})
    ATTRS['ALL_MONTHLY_ATTRIBUTES'] = get_attrs(sub_dict={'calc': 'monthly'})
    ATTRS['ALL_YEARLY_ATTRIBUTES'] = get_attrs(sub_dict={'calc': 'yearly'})
    ATTRS['ALL_NEED_PARAMS_ATTRIBUTES'] = get_attrs(sub_dict={'params': True})
    ATTRS['ALL_VERBRAUCH_ATTRIBUTES'] = get_attrs(sub_dict={'cat': 'verbrauch'})
    ATTRS['ALL_ZAEHLERSTAND_ATTRIBUTES'] = get_attrs(sub_dict={'cat': 'zaehler'})
    ATTRS['ALL_HISTORIE_ATTRIBUTES'] = get_attrs(sub_dict={'cat': 'wertehistorie'})
    ATTRS['ALL_TAGESMITTEL_ATTRIBUTES'] = get_attrs(sub_dict={'cat': 'tagesmittel'})
    ATTRS['ALL_SERIE_ATTRIBUTES'] = get_attrs(sub_dict={'cat': 'serie'})
    ATTRS['ALL_GEN_ATTRIBUTES'] = get_attrs(sub_dict={'cat': 'gen'})
    ATTRS['ALL_COMPLEX_ATTRIBUTES'] = get_attrs(sub_dict={'cat': 'complex'})

    for attr, alist in ATTRS.items():
        print(f'{attr} = {alist!r}')


def export_for_plugin_yaml():
    for entry in ITEM_ATTRIBUTS:
        print(f'{entry}:')
        print('valid_list:')
        for func in ITEM_ATTRIBUTS[entry]:
            print(f"    - '{func}'")

        for title in ['description', 'item_type', 'calc']:
            print(f'valid_list_{entry}:')
            for func in ITEM_ATTRIBUTS[entry]:
                print(f"    - '{ITEM_ATTRIBUTS[entry][func][title]}'")
        print()


if __name__ == '__main__':
    export_db_addon_data()
    print()
    print('--------------------------------------------------------------')
    print()
    export_for_plugin_yaml()
