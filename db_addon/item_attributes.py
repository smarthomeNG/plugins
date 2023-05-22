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
#                                 THIS FILE IS AUTOMATICALLY CREATED BY USING item_attributs_master.py
#
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

ALL_ONCHANGE_ATTRIBUTES = ['verbrauch_heute', 'verbrauch_woche', 'verbrauch_monat', 'verbrauch_jahr', 'minmax_heute_min', 'minmax_heute_max', 'minmax_woche_min', 'minmax_woche_max', 'minmax_monat_min', 'minmax_monat_max', 'minmax_jahr_min', 'minmax_jahr_max', 'tagesmitteltemperatur_heute']
ALL_DAILY_ATTRIBUTES = ['verbrauch_heute_minus1', 'verbrauch_heute_minus2', 'verbrauch_heute_minus3', 'verbrauch_heute_minus4', 'verbrauch_heute_minus5', 'verbrauch_heute_minus6', 'verbrauch_heute_minus7', 'verbrauch_rolling_12m_heute_minus1', 'verbrauch_jahreszeitraum_minus1', 'verbrauch_jahreszeitraum_minus2', 'verbrauch_jahreszeitraum_minus3', 'zaehlerstand_heute_minus1', 'zaehlerstand_heute_minus2', 'zaehlerstand_heute_minus3', 'minmax_last_24h_min', 'minmax_last_24h_max', 'minmax_last_24h_avg', 'minmax_last_7d_min', 'minmax_last_7d_max', 'minmax_last_7d_avg', 'minmax_heute_minus1_min', 'minmax_heute_minus1_max', 'minmax_heute_minus1_avg', 'minmax_heute_minus2_min', 'minmax_heute_minus2_max', 'minmax_heute_minus2_avg', 'minmax_heute_minus3_min', 'minmax_heute_minus3_max', 'minmax_heute_minus3_avg', 'tagesmitteltemperatur_heute_minus1', 'tagesmitteltemperatur_heute_minus2', 'tagesmitteltemperatur_heute_minus3', 'serie_minmax_tag_min_30d', 'serie_minmax_tag_max_30d', 'serie_minmax_tag_avg_30d', 'serie_verbrauch_tag_30d', 'serie_zaehlerstand_tag_30d', 'serie_tagesmittelwert_stunde_0d', 'serie_tagesmittelwert_tag_stunde_30d', 'kaeltesumme', 'waermesumme', 'gruenlandtempsumme', 'tagesmitteltemperatur', 'wachstumsgradtage']
ALL_WEEKLY_ATTRIBUTES = ['verbrauch_woche_minus1', 'verbrauch_woche_minus2', 'verbrauch_woche_minus3', 'verbrauch_woche_minus4', 'verbrauch_rolling_12m_woche_minus1', 'zaehlerstand_woche_minus1', 'zaehlerstand_woche_minus2', 'zaehlerstand_woche_minus3', 'minmax_woche_minus1_min', 'minmax_woche_minus1_max', 'minmax_woche_minus1_avg', 'minmax_woche_minus2_min', 'minmax_woche_minus2_max', 'minmax_woche_minus2_avg', 'serie_minmax_woche_min_30w', 'serie_minmax_woche_max_30w', 'serie_minmax_woche_avg_30w', 'serie_verbrauch_woche_30w', 'serie_zaehlerstand_woche_30w']
ALL_MONTHLY_ATTRIBUTES = ['verbrauch_monat_minus1', 'verbrauch_monat_minus2', 'verbrauch_monat_minus3', 'verbrauch_monat_minus4', 'verbrauch_monat_minus12', 'verbrauch_rolling_12m_monat_minus1', 'zaehlerstand_monat_minus1', 'zaehlerstand_monat_minus2', 'zaehlerstand_monat_minus3', 'minmax_monat_minus1_min', 'minmax_monat_minus1_max', 'minmax_monat_minus1_avg', 'minmax_monat_minus2_min', 'minmax_monat_minus2_max', 'minmax_monat_minus2_avg', 'serie_minmax_monat_min_15m', 'serie_minmax_monat_max_15m', 'serie_minmax_monat_avg_15m', 'serie_verbrauch_monat_18m', 'serie_zaehlerstand_monat_18m', 'serie_waermesumme_monat_24m', 'serie_kaeltesumme_monat_24m']
ALL_YEARLY_ATTRIBUTES = ['verbrauch_jahr_minus1', 'verbrauch_jahr_minus2', 'verbrauch_rolling_12m_jahr_minus1', 'zaehlerstand_jahr_minus1', 'zaehlerstand_jahr_minus2', 'zaehlerstand_jahr_minus3', 'minmax_jahr_minus1_min', 'minmax_jahr_minus1_max', 'minmax_jahr_minus1_avg']
ALL_NEED_PARAMS_ATTRIBUTES = ['kaeltesumme', 'waermesumme', 'gruenlandtempsumme', 'tagesmitteltemperatur', 'wachstumsgradtage', 'db_request']
ALL_VERBRAUCH_ATTRIBUTES = ['verbrauch_heute', 'verbrauch_woche', 'verbrauch_monat', 'verbrauch_jahr', 'verbrauch_heute_minus1', 'verbrauch_heute_minus2', 'verbrauch_heute_minus3', 'verbrauch_heute_minus4', 'verbrauch_heute_minus5', 'verbrauch_heute_minus6', 'verbrauch_heute_minus7', 'verbrauch_woche_minus1', 'verbrauch_woche_minus2', 'verbrauch_woche_minus3', 'verbrauch_woche_minus4', 'verbrauch_monat_minus1', 'verbrauch_monat_minus2', 'verbrauch_monat_minus3', 'verbrauch_monat_minus4', 'verbrauch_monat_minus12', 'verbrauch_jahr_minus1', 'verbrauch_jahr_minus2', 'verbrauch_rolling_12m_heute_minus1', 'verbrauch_rolling_12m_woche_minus1', 'verbrauch_rolling_12m_monat_minus1', 'verbrauch_rolling_12m_jahr_minus1', 'verbrauch_jahreszeitraum_minus1', 'verbrauch_jahreszeitraum_minus2', 'verbrauch_jahreszeitraum_minus3']
ALL_ZAEHLERSTAND_ATTRIBUTES = ['zaehlerstand_heute_minus1', 'zaehlerstand_heute_minus2', 'zaehlerstand_heute_minus3', 'zaehlerstand_woche_minus1', 'zaehlerstand_woche_minus2', 'zaehlerstand_woche_minus3', 'zaehlerstand_monat_minus1', 'zaehlerstand_monat_minus2', 'zaehlerstand_monat_minus3', 'zaehlerstand_jahr_minus1', 'zaehlerstand_jahr_minus2', 'zaehlerstand_jahr_minus3']
ALL_HISTORIE_ATTRIBUTES = ['minmax_last_24h_min', 'minmax_last_24h_max', 'minmax_last_24h_avg', 'minmax_last_7d_min', 'minmax_last_7d_max', 'minmax_last_7d_avg', 'minmax_heute_min', 'minmax_heute_max', 'minmax_heute_minus1_min', 'minmax_heute_minus1_max', 'minmax_heute_minus1_avg', 'minmax_heute_minus2_min', 'minmax_heute_minus2_max', 'minmax_heute_minus2_avg', 'minmax_heute_minus3_min', 'minmax_heute_minus3_max', 'minmax_heute_minus3_avg', 'minmax_woche_min', 'minmax_woche_max', 'minmax_woche_minus1_min', 'minmax_woche_minus1_max', 'minmax_woche_minus1_avg', 'minmax_woche_minus2_min', 'minmax_woche_minus2_max', 'minmax_woche_minus2_avg', 'minmax_monat_min', 'minmax_monat_max', 'minmax_monat_minus1_min', 'minmax_monat_minus1_max', 'minmax_monat_minus1_avg', 'minmax_monat_minus2_min', 'minmax_monat_minus2_max', 'minmax_monat_minus2_avg', 'minmax_jahr_min', 'minmax_jahr_max', 'minmax_jahr_minus1_min', 'minmax_jahr_minus1_max', 'minmax_jahr_minus1_avg']
ALL_TAGESMITTEL_ATTRIBUTES = ['tagesmitteltemperatur_heute', 'tagesmitteltemperatur_heute_minus1', 'tagesmitteltemperatur_heute_minus2', 'tagesmitteltemperatur_heute_minus3']
ALL_SERIE_ATTRIBUTES = ['serie_minmax_monat_min_15m', 'serie_minmax_monat_max_15m', 'serie_minmax_monat_avg_15m', 'serie_minmax_woche_min_30w', 'serie_minmax_woche_max_30w', 'serie_minmax_woche_avg_30w', 'serie_minmax_tag_min_30d', 'serie_minmax_tag_max_30d', 'serie_minmax_tag_avg_30d', 'serie_verbrauch_tag_30d', 'serie_verbrauch_woche_30w', 'serie_verbrauch_monat_18m', 'serie_zaehlerstand_tag_30d', 'serie_zaehlerstand_woche_30w', 'serie_zaehlerstand_monat_18m', 'serie_waermesumme_monat_24m', 'serie_kaeltesumme_monat_24m', 'serie_tagesmittelwert_stunde_0d', 'serie_tagesmittelwert_tag_stunde_30d']
ALL_GEN_ATTRIBUTES = ['general_oldest_value', 'general_oldest_log']
ALL_COMPLEX_ATTRIBUTES = ['kaeltesumme', 'waermesumme', 'gruenlandtempsumme', 'tagesmitteltemperatur', 'wachstumsgradtage', 'db_request']
