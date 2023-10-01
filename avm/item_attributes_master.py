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

ATTRIBUTE = 'avm_data_type'

FILE_HEADER = """\
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


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
#
#                                 THIS FILE IS AUTOMATICALLY CREATED BY USING item_attributs_master.py
#
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

"""

# Note: change / add information of avm_data_type within the following dict according to the given scheme
#     'avm_data_type':                {'interface': 'tr064',        'group': '',                'sub_group': None,                 'access': '',    'type': '',      'deprecated': False,  'supported_by_repeater': False,   'description': ''},
AVM_DATA_TYPES = {
    'tr064': {
      'uptime':                       {'interface': 'tr064',        'group': 'fritz_device',    'sub_group': None,                 'access': 'ro',  'type': 'num',   'deprecated': False,  'supported_by_repeater': True,    'description': 'Laufzeit des Fritzdevice in Sekunden'},
      'serial_number':                {'interface': 'tr064',        'group': 'fritz_device',    'sub_group': None,                 'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': True,    'description': 'Serialnummer des Fritzdevice'},
      'software_version':             {'interface': 'tr064',        'group': 'fritz_device',    'sub_group': None,                 'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': True,    'description': 'Software Version'},
      'hardware_version':             {'interface': 'tr064',        'group': 'fritz_device',    'sub_group': None,                 'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': True,    'description': 'Hardware Version'},
      'manufacturer':                 {'interface': 'tr064',        'group': 'fritz_device',    'sub_group': None,                 'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': True,    'description': 'Hersteller'},
      'product_class':                {'interface': 'tr064',        'group': 'fritz_device',    'sub_group': None,                 'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': True,    'description': 'Produktklasse'},
      'manufacturer_oui':             {'interface': 'tr064',        'group': 'fritz_device',    'sub_group': None,                 'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': True,    'description': 'Hersteller OUI'},
      'model_name':                   {'interface': 'tr064',        'group': 'fritz_device',    'sub_group': None,                 'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': True,    'description': 'Modellname'},
      'description':                  {'interface': 'tr064',        'group': 'fritz_device',    'sub_group': None,                 'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': True,    'description': 'Modellbeschreibung'},
      'device_log':                   {'interface': 'tr064',        'group': 'fritz_device',    'sub_group': None,                 'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': True,    'description': 'Geräte Log'},
      'security_port':                {'interface': 'tr064',        'group': 'fritz_device',    'sub_group': None,                 'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': True,    'description': 'Security Port'},
      'reboot':                       {'interface': 'tr064',        'group': 'fritz_device',    'sub_group': None,                 'access': 'wo',  'type': 'bool',  'deprecated': False,  'supported_by_repeater': True,    'description': 'Startet das Gerät neu'},
      'myfritz_status':               {'interface': 'tr064',        'group': 'myfritz',         'sub_group': None,                 'access': 'ro',  'type': 'bool',  'deprecated': False,  'supported_by_repeater': False,   'description': 'MyFritz Status (an/aus)'},
      'call_direction':               {'interface': 'tr064',        'group': 'call_monitor',    'sub_group': 'generic',            'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': False,   'description': 'Richtung des letzten Anrufes'},
      'call_event':                   {'interface': 'tr064',        'group': 'call_monitor',    'sub_group': 'generic',            'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': False,   'description': 'Status des letzten Anrufes'},
      'monitor_trigger':              {'interface': 'tr064',        'group': 'call_monitor',    'sub_group': 'trigger',            'access': 'ro',  'type': 'bool',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Monitortrigger'},
      'is_call_incoming':             {'interface': 'tr064',        'group': 'call_monitor',    'sub_group': 'in',                 'access': 'ro',  'type': 'bool',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Eingehender Anruf erkannt'},
      'last_caller_incoming':         {'interface': 'tr064',        'group': 'call_monitor',    'sub_group': 'in',                 'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': False,   'description': 'Letzter Anrufer'},
      'last_call_date_incoming':      {'interface': 'tr064',        'group': 'call_monitor',    'sub_group': 'in',                 'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': False,   'description': 'Zeitpunkt des letzten eingehenden Anrufs'},
      'call_event_incoming':          {'interface': 'tr064',        'group': 'call_monitor',    'sub_group': 'in',                 'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': False,   'description': 'Status des letzten eingehenden Anrufs'},
      'last_number_incoming':         {'interface': 'tr064',        'group': 'call_monitor',    'sub_group': 'in',                 'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': False,   'description': 'Nummer des letzten eingehenden Anrufes'},
      'last_called_number_incoming':  {'interface': 'tr064',        'group': 'call_monitor',    'sub_group': 'in',                 'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': False,   'description': 'Angerufene Nummer des letzten eingehenden Anrufs'},
      'is_call_outgoing':             {'interface': 'tr064',        'group': 'call_monitor',    'sub_group': 'out',                'access': 'ro',  'type': 'bool',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Ausgehender Anruf erkannt'},
      'last_caller_outgoing':         {'interface': 'tr064',        'group': 'call_monitor',    'sub_group': 'out',                'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': False,   'description': 'Letzter angerufener Kontakt'},
      'last_call_date_outgoing':      {'interface': 'tr064',        'group': 'call_monitor',    'sub_group': 'out',                'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': False,   'description': 'Zeitpunkt des letzten ausgehenden Anrufs'},
      'call_event_outgoing':          {'interface': 'tr064',        'group': 'call_monitor',    'sub_group': 'out',                'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': False,   'description': 'Status des letzten ausgehenden Anrufs'},
      'last_number_outgoing':         {'interface': 'tr064',        'group': 'call_monitor',    'sub_group': 'out',                'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': False,   'description': 'Nummer des letzten ausgehenden Anrufes'},
      'last_called_number_outgoing':  {'interface': 'tr064',        'group': 'call_monitor',    'sub_group': 'out',                'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': False,   'description': 'Letzte verwendete Telefonnummer für ausgehenden Anruf'},
      'call_duration_incoming':       {'interface': 'tr064',        'group': 'call_monitor',    'sub_group': 'duration',           'access': 'ro',  'type': 'num',   'deprecated': False,  'supported_by_repeater': False,   'description': 'Dauer des eingehenden Anrufs'},
      'call_duration_outgoing':       {'interface': 'tr064',        'group': 'call_monitor',    'sub_group': 'duration',           'access': 'ro',  'type': 'num',   'deprecated': False,  'supported_by_repeater': False,   'description': 'Dauer des ausgehenden Anrufs'},
      'tam':                          {'interface': 'tr064',        'group': 'tam',             'sub_group': None,                 'access': 'rw',  'type': 'bool',  'deprecated': False,  'supported_by_repeater': False,   'description': 'TAM an/aus'},
      'tam_name':                     {'interface': 'tr064',        'group': 'tam',             'sub_group': None,                 'access': 'ro',  'type': 'str ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Name des TAM'},
      'tam_new_message_number':       {'interface': 'tr064',        'group': 'tam',             'sub_group': None,                 'access': 'ro',  'type': 'num ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Anzahl der alten Nachrichten'},
      'tam_old_message_number':       {'interface': 'tr064',        'group': 'tam',             'sub_group': None,                 'access': 'ro',  'type': 'num ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Anzahl der neuen Nachrichten'},
      'tam_total_message_number':     {'interface': 'tr064',        'group': 'tam',             'sub_group': None,                 'access': 'ro',  'type': 'num ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Gesamtanzahl der Nachrichten'},
      'wan_connection_status':        {'interface': 'tr064',        'group': 'wan',             'sub_group': 'connection',         'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': False,   'description': 'WAN Verbindungsstatus'},
      'wan_connection_error':         {'interface': 'tr064',        'group': 'wan',             'sub_group': 'connection',         'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': False,   'description': 'WAN Verbindungsfehler'},
      'wan_is_connected':             {'interface': 'tr064',        'group': 'wan',             'sub_group': 'connection',         'access': 'ro',  'type': 'bool',  'deprecated': False,  'supported_by_repeater': False,   'description': 'WAN Verbindung aktiv'},
      'wan_uptime':                   {'interface': 'tr064',        'group': 'wan',             'sub_group': 'connection',         'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': False,   'description': 'WAN Verbindungszeit'},
      'wan_ip':                       {'interface': 'tr064',        'group': 'wan',             'sub_group': 'connection',         'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': False,   'description': 'WAN IP Adresse'},
      'wan_upstream':                 {'interface': 'tr064',        'group': 'wan',             'sub_group': 'dsl_interface',      'access': 'ro',  'type': 'num',   'deprecated': False,  'supported_by_repeater': False,   'description': 'WAN Upstream Datenmenge'},
      'wan_downstream':               {'interface': 'tr064',        'group': 'wan',             'sub_group': 'dsl_interface',      'access': 'ro',  'type': 'num',   'deprecated': False,  'supported_by_repeater': False,   'description': 'WAN Downstream Datenmenge'},
      'wan_total_packets_sent':       {'interface': 'tr064',        'group': 'wan',             'sub_group': 'common_interface',   'access': 'ro',  'type': 'num',   'deprecated': False,  'supported_by_repeater': False,   'description': 'WAN Verbindung-Anzahl insgesamt versendeter Pakete'},
      'wan_total_packets_received':   {'interface': 'tr064',        'group': 'wan',             'sub_group': 'common_interface',   'access': 'ro',  'type': 'num',   'deprecated': False,  'supported_by_repeater': False,   'description': 'WAN Verbindung-Anzahl insgesamt empfangener Pakete'},
      'wan_current_packets_sent':     {'interface': 'tr064',        'group': 'wan',             'sub_group': 'common_interface',   'access': 'ro',  'type': 'num',   'deprecated': False,  'supported_by_repeater': False,   'description': 'WAN Verbindung-Anzahl aktuell versendeter Pakete'},
      'wan_current_packets_received': {'interface': 'tr064',        'group': 'wan',             'sub_group': 'common_interface',   'access': 'ro',  'type': 'num',   'deprecated': False,  'supported_by_repeater': False,   'description': 'WAN Verbindung-Anzahl aktuell empfangener Pakete'},
      'wan_total_bytes_sent':         {'interface': 'tr064',        'group': 'wan',             'sub_group': 'common_interface',   'access': 'ro',  'type': 'num',   'deprecated': False,  'supported_by_repeater': False,   'description': 'WAN Verbindung-Anzahl insgesamt versendeter Bytes'},
      'wan_total_bytes_received':     {'interface': 'tr064',        'group': 'wan',             'sub_group': 'common_interface',   'access': 'ro',  'type': 'num',   'deprecated': False,  'supported_by_repeater': False,   'description': 'WAN Verbindung-Anzahl insgesamt empfangener Bytes'},
      'wan_current_bytes_sent':       {'interface': 'tr064',        'group': 'wan',             'sub_group': 'common_interface',   'access': 'ro',  'type': 'num',   'deprecated': False,  'supported_by_repeater': False,   'description': 'WAN Verbindung-Anzahl aktuelle Bitrate Senden'},
      'wan_current_bytes_received':   {'interface': 'tr064',        'group': 'wan',             'sub_group': 'common_interface',   'access': 'ro',  'type': 'num',   'deprecated': False,  'supported_by_repeater': False,   'description': 'WAN Verbindung-Anzahl aktuelle Bitrate Empfangen'},
      'wan_link':                     {'interface': 'tr064',        'group': 'wan',             'sub_group': 'common_interface',   'access': 'ro',  'type': 'bool',  'deprecated': False,  'supported_by_repeater': False,   'description': 'WAN Link'},
      'wlanconfig':                   {'interface': 'tr064',        'group': 'wlan_config',     'sub_group': None,                 'access': 'rw',  'type': 'bool',  'deprecated': False,  'supported_by_repeater': True,    'description': 'WLAN An/Aus'},
      'wlanconfig_ssid':              {'interface': 'tr064',        'group': 'wlan_config',     'sub_group': None,                 'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': True,    'description': 'WLAN SSID'},
      'wlan_guest_time_remaining':    {'interface': 'tr064',        'group': 'wlan_config',     'sub_group': None,                 'access': 'ro',  'type': 'num',   'deprecated': False,  'supported_by_repeater': True,    'description': 'Verbleibende Zeit, bis zum automatischen Abschalten des Gäste-WLAN'},
      'wlan_associates':              {'interface': 'tr064',        'group': 'wlan_config',     'sub_group': None,                 'access': 'ro',  'type': 'num',   'deprecated': False,  'supported_by_repeater': True,    'description': 'Anzahl der verbundenen Geräte im jeweiligen WLAN'},
      'wps_active':                   {'interface': 'tr064',        'group': 'wlan_config',     'sub_group': None,                 'access': 'rw',  'type': 'bool',  'deprecated': False,  'supported_by_repeater': True,    'description': 'Schaltet WPS für das entsprechende WlAN an / aus'},
      'wps_status':                   {'interface': 'tr064',        'group': 'wlan_config',     'sub_group': None,                 'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': True,    'description': 'WPS Status des entsprechenden WlAN'},
      'wps_mode':                     {'interface': 'tr064',        'group': 'wlan_config',     'sub_group': None,                 'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': True,    'description': 'WPS Modus des entsprechenden WlAN'},
      'wlan_total_associates':        {'interface': 'tr064',        'group': 'wlan',            'sub_group': None,                 'access': 'ro',  'type': 'num',   'deprecated': False,  'supported_by_repeater': True,    'description': 'Anzahl der verbundenen Geräte im WLAN'},
      'hosts_count':                  {'interface': 'tr064',        'group': 'host',            'sub_group': 'gen',                'access': 'ro',  'type': 'num',   'deprecated': False,  'supported_by_repeater': True,    'description': 'Anzahl der Hosts'},
      'hosts_info':                   {'interface': 'tr064',        'group': 'host',            'sub_group': 'gen',                'access': 'ro',  'type': 'dict',  'deprecated': False,  'supported_by_repeater': True,    'description': 'Informationen über die Hosts'},
      'mesh_topology':                {'interface': 'tr064',        'group': 'host',            'sub_group': 'gen',                'access': 'ro',  'type': 'dict',  'deprecated': False,  'supported_by_repeater': True,    'description': 'Topologie des Mesh'},
      'number_of_hosts':              {'interface': 'tr064',        'group': 'host',            'sub_group': 'gen',                'access': 'ro',  'type': 'num',   'deprecated': False,  'supported_by_repeater': True,    'description': 'Anzahl der verbundenen Hosts (Muss Child von "network_device" sein)'},
      'hosts_url':                    {'interface': 'tr064',        'group': 'host',            'sub_group': 'gen',                'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': True,    'description': 'URL zu Hosts (Muss Child von "network_device" sein)'},
      'mesh_url':                     {'interface': 'tr064',        'group': 'host',            'sub_group': 'gen',                'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': True,    'description': 'URL zum Mesh (Muss Child von "network_device" sein)'},
      'network_device':               {'interface': 'tr064',        'group': 'host',            'sub_group': 'child',              'access': 'ro',  'type': 'bool',  'deprecated': False,  'supported_by_repeater': True,    'description': 'Verbindungsstatus des Gerätes // Defines Network device via MAC-Adresse'},
      'device_ip':                    {'interface': 'tr064',        'group': 'host',            'sub_group': 'child',              'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': True,    'description': 'Geräte-IP (Muss Child von "network_device" sein)'},
      'device_connection_type':       {'interface': 'tr064',        'group': 'host',            'sub_group': 'child',              'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': True,    'description': 'Verbindungstyp (Muss Child von "network_device" sein)'},
      'device_hostname':              {'interface': 'tr064',        'group': 'host',            'sub_group': 'child',              'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': True,    'description': 'Gerätename (Muss Child von "network_device" sein'},
      'connection_status':            {'interface': 'tr064',        'group': 'host',            'sub_group': 'child',              'access': 'ro',  'type': 'bool',  'deprecated': False,  'supported_by_repeater': True,    'description': 'Verbindungsstatus (Muss Child von "network_device" sein)'},
      'is_host_active':               {'interface': 'tr064',        'group': 'host',            'sub_group': 'child',              'access': 'ro',  'type': 'bool',  'deprecated': False,  'supported_by_repeater': True,    'description': 'Host aktiv? (Muss Child von "network_device" sein)'},
      'host_info':                    {'interface': 'tr064',        'group': 'host',            'sub_group': 'host',               'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': True,    'description': 'Informationen zum Host (Muss Child von "network_device" sein)'},
      'number_of_deflections':        {'interface': 'tr064',        'group': 'deflection',      'sub_group': 'gen',                'access': 'ro',  'type': 'num',   'deprecated': False,  'supported_by_repeater': False,   'description': 'Anzahl der eingestellten Rufumleitungen'},
      'deflections_details':          {'interface': 'tr064',        'group': 'deflection',      'sub_group': 'gen',                'access': 'ro',  'type': 'dict',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Details zu allen Rufumleitung (als dict)'},
      'deflection_details':           {'interface': 'tr064',        'group': 'deflection',      'sub_group': 'single',             'access': 'ro',  'type': 'dict',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Details zur Rufumleitung (als dict); Angabe der Rufumleitung mit Parameter "avm_deflection_index" im Item'},
      'deflection_enable':            {'interface': 'tr064',        'group': 'deflection',      'sub_group': 'single',             'access': 'rw',  'type': 'bool',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Rufumleitung Status an/aus; Angabe der Rufumleitung mit Parameter "avm_deflection_index" im Item bzw Parent-Item'},
      'deflection_type':              {'interface': 'tr064',        'group': 'deflection',      'sub_group': 'single',             'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': False,   'description': 'Type der Rufumleitung; Angabe der Rufumleitung mit Parameter "avm_deflection_index" im Item bzw Parent-Item'},
      'deflection_number':            {'interface': 'tr064',        'group': 'deflection',      'sub_group': 'single',             'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': False,   'description': 'Telefonnummer, die umgeleitet wird; Angabe der Rufumleitung mit Parameter "avm_deflection_index" im Item bzw Parent-Item'},
      'deflection_to_number':         {'interface': 'tr064',        'group': 'deflection',      'sub_group': 'single',             'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': False,   'description': 'Zielrufnummer der Umleitung; Angabe der Rufumleitung mit Parameter "avm_deflection_index" im Item bzw Parent-Item'},
      'deflection_mode':              {'interface': 'tr064',        'group': 'deflection',      'sub_group': 'single',             'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': False,   'description': 'Modus der Rufumleitung; Angabe der Rufumleitung mit Parameter "avm_deflection_index" im Item bzw Parent-Item'},
      'deflection_outgoing':          {'interface': 'tr064',        'group': 'deflection',      'sub_group': 'single',             'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': False,   'description': 'Outgoing der Rufumleitung; Angabe der Rufumleitung mit Parameter "avm_deflection_index" im Item bzw Parent-Item'},
      'deflection_phonebook_id':      {'interface': 'tr064',        'group': 'deflection',      'sub_group': 'single',             'access': 'ro',  'type': 'str',   'deprecated': False,  'supported_by_repeater': False,   'description': 'Phonebook_ID der Zielrufnummer (Only valid if Type==fromPB); Angabe der Rufumleitung mit Parameter "avm_deflection_index" im Item bzw Parent-Item'},
      'aha_device':                   {'interface': 'tr064',        'group': 'homeauto',        'sub_group': None,                 'access': 'rw',  'type': 'bool',  'deprecated': True,   'supported_by_repeater': False,   'description': 'Steckdose schalten; siehe "switch_state"'},
      'hkr_device':                   {'interface': 'tr064',        'group': 'homeauto',        'sub_group': None,                 'access': 'ro',  'type': 'str',   'deprecated': True,   'supported_by_repeater': False,   'description': 'Status des HKR (OPEN; CLOSED; TEMP)'},
      'set_temperature':              {'interface': 'tr064',        'group': 'homeauto',        'sub_group': None,                 'access': 'ro',  'type': 'num',   'deprecated': True,   'supported_by_repeater': False,   'description': 'siehe "target_temperature"'},
      'temperature':                  {'interface': 'tr064',        'group': 'homeauto',        'sub_group': None,                 'access': 'ro',  'type': 'num',   'deprecated': True,   'supported_by_repeater': False,   'description': 'siehe "current_temperature"'},
      'set_temperature_reduced':      {'interface': 'tr064',        'group': 'homeauto',        'sub_group': None,                 'access': 'ro',  'type': 'num',   'deprecated': True,   'supported_by_repeater': False,   'description': 'siehe "temperature_reduced"'},
      'set_temperature_comfort':      {'interface': 'tr064',        'group': 'homeauto',        'sub_group': None,                 'access': 'ro',  'type': 'num',   'deprecated': True,   'supported_by_repeater': False,   'description': 'siehe "temperature_comfort"'},
      'firmware_version':             {'interface': 'tr064',        'group': 'homeauto',        'sub_group': None,                 'access': 'ro',  'type': 'str',   'deprecated': True,   'supported_by_repeater': False,   'description': 'siehe "fw_version"'},
    },
    'aha': {
      'device_id':                    {'interface': 'aha',          'group': 'device',          'sub_group': None,                 'access': 'ro',  'type': 'str ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Geräte -ID'},
      'manufacturer':                 {'interface': 'aha',          'group': 'device',          'sub_group': None,                 'access': 'ro',  'type': 'str ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Hersteller'},
      'product_name':                 {'interface': 'aha',          'group': 'device',          'sub_group': None,                 'access': 'ro',  'type': 'str ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Produktname'},
      'fw_version':                   {'interface': 'aha',          'group': 'device',          'sub_group': None,                 'access': 'ro',  'type': 'str ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Firmware Version'},
      'connected':                    {'interface': 'aha',          'group': 'device',          'sub_group': None,                 'access': 'ro',  'type': 'bool',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Verbindungsstatus'},
      'device_name':                  {'interface': 'aha',          'group': 'device',          'sub_group': None,                 'access': 'ro',  'type': 'str ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Gerätename'},
      'tx_busy':                      {'interface': 'aha',          'group': 'device',          'sub_group': None,                 'access': 'ro',  'type': 'bool',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Verbindung aktiv'},
      'device_functions':             {'interface': 'aha',          'group': 'device',          'sub_group': None,                 'access': 'ro',  'type': 'list',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Im Gerät vorhandene Funktionen'},
      'set_target_temperature':       {'interface': 'aha',          'group': 'hkr',             'sub_group': None,                 'access': 'wo',  'type': 'num ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Soll-Temperatur Setzen'},
      'target_temperature':           {'interface': 'aha',          'group': 'hkr',             'sub_group': None,                 'access': 'rw',  'type': 'num ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Soll-Temperatur (Status und Setzen)'},
      'current_temperature':          {'interface': 'aha',          'group': 'hkr',             'sub_group': None,                 'access': 'ro',  'type': 'num ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Ist-Temperatur'},
      'temperature_reduced':          {'interface': 'aha',          'group': 'hkr',             'sub_group': None,                 'access': 'ro',  'type': 'num ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Eingestellte reduzierte Temperatur'},
      'temperature_comfort':          {'interface': 'aha',          'group': 'hkr',             'sub_group': None,                 'access': 'ro',  'type': 'num ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Eingestellte Komfort-Temperatur'},
      'temperature_offset':           {'interface': 'aha',          'group': 'hkr',             'sub_group': None,                 'access': 'ro',  'type': 'num ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Eingestellter Temperatur-Offset'},
      'set_window_open':              {'interface': 'aha',          'group': 'hkr',             'sub_group': None,                 'access': 'wo',  'type': 'bool',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Window-Open-Funktion (Setzen)'},
      'window_open':                  {'interface': 'aha',          'group': 'hkr',             'sub_group': None,                 'access': 'rw',  'type': 'bool',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Window-Open-Funktion (Status und Setzen)'},
      'windowopenactiveendtime':      {'interface': 'aha',          'group': 'hkr',             'sub_group': None,                 'access': 'ro',  'type': 'num ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Zeitliches Ende der "Window Open" Funktion'},
      'set_hkr_boost':                {'interface': 'aha',          'group': 'hkr',             'sub_group': None,                 'access': 'wo',  'type': 'bool',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Boost-Funktion (Setzen)'},
      'hkr_boost':                    {'interface': 'aha',          'group': 'hkr',             'sub_group': None,                 'access': 'rw',  'type': 'bool',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Boost-Funktion (Status und Setzen)'},
      'boost_active':                 {'interface': 'aha',          'group': 'hkr',             'sub_group': None,                 'access': 'ro',  'type': 'bool',  'deprecated': True,   'supported_by_repeater': False,   'description': 'Status der "Boost" Funktion'},
      'boostactiveendtime':           {'interface': 'aha',          'group': 'hkr',             'sub_group': None,                 'access': 'ro',  'type': 'num ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Zeitliches Ende der Boost Funktion'},
      'summer_active':                {'interface': 'aha',          'group': 'hkr',             'sub_group': None,                 'access': 'ro',  'type': 'bool',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Status der "Sommer" Funktion'},
      'holiday_active':               {'interface': 'aha',          'group': 'hkr',             'sub_group': None,                 'access': 'ro',  'type': 'bool',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Status der "Holiday" Funktion'},
      'battery_low':                  {'interface': 'aha',          'group': 'hkr',             'sub_group': None,                 'access': 'ro',  'type': 'bool',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Battery-low Status'},
      'battery_level':                {'interface': 'aha',          'group': 'hkr',             'sub_group': None,                 'access': 'ro',  'type': 'num ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Batterie-Status in %'},
      'lock':                         {'interface': 'aha',          'group': 'hkr',             'sub_group': None,                 'access': 'ro',  'type': 'bool',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Tastensperre über UI/API aktiv'},
      'device_lock':                  {'interface': 'aha',          'group': 'hkr',             'sub_group': None,                 'access': 'ro',  'type': 'bool',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Tastensperre direkt am Gerät ein'},
      'errorcode':                    {'interface': 'aha',          'group': 'hkr',             'sub_group': None,                 'access': 'ro',  'type': 'num ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Fehlercodes die der HKR liefert'},
      'set_simpleonoff':              {'interface': 'aha',          'group': 'simpleonoff',     'sub_group': None,                 'access': 'wo',  'type': 'bool',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Gerät/Aktor/Lampe an-/ausschalten'},
      'simpleonoff':                  {'interface': 'aha',          'group': 'simpleonoff',     'sub_group': None,                 'access': 'rw',  'type': 'bool',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Gerät/Aktor/Lampe (Status und Setzen)'},
      'set_level':                    {'interface': 'aha',          'group': 'level',           'sub_group': None,                 'access': 'wo',  'type': 'num ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Level/Niveau von 0 bis 255 (Setzen)'},
      'level':                        {'interface': 'aha',          'group': 'level',           'sub_group': None,                 'access': 'rw',  'type': 'num ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Level/Niveau von 0 bis 255 (Setzen & Status)'},
      'set_levelpercentage':          {'interface': 'aha',          'group': 'level',           'sub_group': None,                 'access': 'wo',  'type': 'num ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Level/Niveau in Prozent von 0% bis 100% (Setzen)'},
      'levelpercentage':              {'interface': 'aha',          'group': 'level',           'sub_group': None,                 'access': 'rw',  'type': 'num ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Level/Niveau in Prozent von 0% bis 100% (Setzen & Status)'},
      'set_hue':                      {'interface': 'aha',          'group': 'color',           'sub_group': None,                 'access': 'wo',  'type': 'num ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Hue mit Wertebereich von 0° bis 359° (Setzen)'},
      'hue':                          {'interface': 'aha',          'group': 'color',           'sub_group': None,                 'access': 'rw',  'type': 'num ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Hue mit Wertebereich von 0° bis 359° (Status und Setzen)'},
      'set_saturation':               {'interface': 'aha',          'group': 'color',           'sub_group': None,                 'access': 'wo',  'type': 'num ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Saturation mit Wertebereich von 0 bis 255 (Setzen)'},
      'saturation':                   {'interface': 'aha',          'group': 'color',           'sub_group': None,                 'access': 'rw',  'type': 'num ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Saturation mit Wertebereich von 0 bis 255 (Status und Setzen)'},
      'set_colortemperature':         {'interface': 'aha',          'group': 'color',           'sub_group': None,                 'access': 'wo',  'type': 'num ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Farbtemperatur mit Wertebereich von 2700K bis 6500K (Setzen)'},
      'colortemperature':             {'interface': 'aha',          'group': 'color',           'sub_group': None,                 'access': 'rw',  'type': 'num ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Farbtemperatur mit Wertebereich von 2700K bis 6500K (Status und Setzen)'},
      'unmapped_hue':                 {'interface': 'aha',          'group': 'color',           'sub_group': None,                 'access': 'rw',  'type': 'num ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Hue mit Wertebereich von 0° bis 359° (Status und Setzen)'},
      'unmapped_saturation':          {'interface': 'aha',          'group': 'color',           'sub_group': None,                 'access': 'rw',  'type': 'num ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Saturation mit Wertebereich von 0 bis 255 (Status und Setzen)'},
      'color':                        {'interface': 'aha',          'group': 'color',           'sub_group': None,                 'access': 'rw',  'type': 'list ', 'deprecated': False,  'supported_by_repeater': False,   'description': 'Farbwerte als Liste [Hue, Saturation] (Status und Setzen)'},
      'hsv':                          {'interface': 'aha',          'group': 'color',           'sub_group': None,                 'access': 'rw',  'type': 'list ', 'deprecated': False,  'supported_by_repeater': False,   'description': 'Farbwerte und Helligkeit als Liste [Hue (0-359), Saturation (0-255), Level (0-255)] (Status und Setzen)'},
      'color_mode':                   {'interface': 'aha',          'group': 'color',           'sub_group': None,                 'access': 'ro',  'type': 'num ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Aktueller Farbmodus (1-HueSaturation-Mode; 4-Farbtemperatur-Mode)'},
      'supported_color_mode':         {'interface': 'aha',          'group': 'color',           'sub_group': None,                 'access': 'ro',  'type': 'num ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Unterstützer Farbmodus (1-HueSaturation-Mode; 4-Farbtemperatur-Mode)'},
      'fullcolorsupport':             {'interface': 'aha',          'group': 'color',           'sub_group': None,                 'access': 'ro',  'type': 'bool',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Lampe unterstützt setunmappedcolor'},
      'mapped':                       {'interface': 'aha',          'group': 'color',           'sub_group': None,                 'access': 'ro',  'type': 'bool',  'deprecated': False,  'supported_by_repeater': False,   'description': 'von den Colordefaults abweichend zugeordneter HueSaturation-Wert gesetzt'},
      'switch_state':                 {'interface': 'aha',          'group': 'switch',          'sub_group': None,                 'access': 'rw',  'type': 'bool',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Schaltzustand Steckdose (Status und Setzen)'},
      'switch_mode':                  {'interface': 'aha',          'group': 'switch',          'sub_group': None,                 'access': 'ro',  'type': 'str ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Zeitschaltung oder manuell schalten'},
      'switch_toggle':                {'interface': 'aha',          'group': 'switch',          'sub_group': None,                 'access': 'wo',  'type': 'bool',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Schaltzustand umschalten (toggle)'},
      'power':                        {'interface': 'aha',          'group': 'powermeter',      'sub_group': None,                 'access': 'ro',  'type': 'num ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Leistung in W (Aktualisierung alle 2 min)'},
      'energy':                       {'interface': 'aha',          'group': 'powermeter',      'sub_group': None,                 'access': 'ro',  'type': 'num ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'absoluter Verbrauch seit Inbetriebnahme in Wh'},
      'voltage':                      {'interface': 'aha',          'group': 'powermeter',      'sub_group': None,                 'access': 'ro',  'type': 'num ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Spannung in V (Aktualisierung alle 2 min)'},
      'humidity':                     {'interface': 'aha',          'group': 'humidity',        'sub_group': None,                 'access': 'ro',  'type': 'num ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Relative Luftfeuchtigkeit in % (FD440)'},
      'alert_state':                  {'interface': 'aha',          'group': 'alarm',           'sub_group': None,                 'access': 'ro',  'type': 'bool',  'deprecated': False,  'supported_by_repeater': False,   'description': 'letzter übermittelter Alarmzustand'},
      'blind_mode':                   {'interface': 'aha',          'group': 'blind',           'sub_group': None,                 'access': 'ro',  'type': 'str ',  'deprecated': False,  'supported_by_repeater': False,   'description': 'automatische Zeitschaltung oder manuell fahren'},
      'endpositionsset':              {'interface': 'aha',          'group': 'blind',           'sub_group': None,                 'access': 'ro',  'type': 'bool',  'deprecated': False,  'supported_by_repeater': False,   'description': 'ist die Endlage für das Rollo konfiguriert'},
      'statistics_temp':              {'interface': 'aha',          'group': 'device',          'sub_group': 'statistics',         'access': 'ro',  'type': 'list',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Wertestatistik für Temperatur'},
      'statistics_hum':               {'interface': 'aha',          'group': 'device',          'sub_group': 'statistics',         'access': 'ro',  'type': 'list',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Wertestatistik für Feuchtigkeit'},
      'statistics_voltage':           {'interface': 'aha',          'group': 'device',          'sub_group': 'statistics',         'access': 'ro',  'type': 'list',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Wertestatistik für Spannung'},
      'statistics_power':             {'interface': 'aha',          'group': 'device',          'sub_group': 'statistics',         'access': 'ro',  'type': 'list',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Wertestatistik für Leistung'},
      'statistics_energy':            {'interface': 'aha',          'group': 'device',          'sub_group': 'statistics',         'access': 'ro',  'type': 'list',  'deprecated': False,  'supported_by_repeater': False,   'description': 'Wertestatistik für Energie'},
    }
}

ATTRIBUTES_LIST = ['tr064', 'aha']


def get_attrs(ifaces: list = ATTRIBUTES_LIST, sub_dict: dict = {}) -> list:
    attributes = []
    for iface in ifaces:
        for avm_data_type in AVM_DATA_TYPES[iface]:
            if sub_dict.items() <= AVM_DATA_TYPES[iface][avm_data_type].items():
                attributes.append(avm_data_type)
    return attributes


def export_item_attributs_py():

    print(f"A) Start creating {FILENAME_ATTRIBUTES}!")

    ATTRS = dict()
    ATTRS['ALL_ATTRIBUTES_SUPPORTED_BY_REPEATER'] = get_attrs(sub_dict={'supported_by_repeater': True})
    ATTRS['ALL_ATTRIBUTES_WRITEABLE'] = get_attrs(sub_dict={'access': 'wo'}) + get_attrs(sub_dict={'access': 'rw'})
    ATTRS['ALL_ATTRIBUTES_WRITEONLY'] = get_attrs(sub_dict={'access': 'wo'})
    ATTRS['DEPRECATED_ATTRIBUTES'] = get_attrs(sub_dict={'deprecated': True})
    ATTRS['AHA_ATTRIBUTES'] = get_attrs(['aha'])
    ATTRS['AHA_RO_ATTRIBUTES'] = get_attrs(['aha'], {'access': 'ro'})
    ATTRS['AHA_WO_ATTRIBUTES'] = get_attrs(['aha'], {'access': 'wo'})
    ATTRS['AHA_RW_ATTRIBUTES'] = get_attrs(['aha'], {'access': 'rw'})
    ATTRS['AHA_STATS_ATTRIBUTES'] = get_attrs(['aha'], {'sub_group': 'statistics'})
    ATTRS['TR064_ATTRIBUTES'] = get_attrs(['tr064'])
    ATTRS['TR064_RW_ATTRIBUTES'] = get_attrs(['tr064'], {'access': 'rw'})
    ATTRS['CALL_MONITOR_ATTRIBUTES'] = get_attrs(['tr064'], {'group': 'call_monitor'})
    ATTRS['CALL_MONITOR_ATTRIBUTES_TRIGGER'] = get_attrs(['tr064'], {'group': 'call_monitor', 'sub_group': 'trigger'})
    ATTRS['CALL_MONITOR_ATTRIBUTES_GEN'] = get_attrs(['tr064'], {'group': 'call_monitor', 'sub_group': 'generic'})
    ATTRS['CALL_MONITOR_ATTRIBUTES_IN'] = get_attrs(['tr064'], {'group': 'call_monitor', 'sub_group': 'in'})
    ATTRS['CALL_MONITOR_ATTRIBUTES_OUT'] = get_attrs(['tr064'], {'group': 'call_monitor', 'sub_group': 'out'})
    ATTRS['CALL_MONITOR_ATTRIBUTES_DURATION'] = get_attrs(['tr064'], {'group': 'call_monitor', 'sub_group': 'duration'})
    ATTRS['WAN_CONNECTION_ATTRIBUTES'] = get_attrs(['tr064'], {'group': 'wan', 'sub_group': 'connection'})
    ATTRS['WAN_COMMON_INTERFACE_ATTRIBUTES'] = get_attrs(['tr064'], {'group': 'wan', 'sub_group': 'common_interface'})
    ATTRS['WAN_DSL_INTERFACE_ATTRIBUTES'] = get_attrs(['tr064'], {'group': 'wan', 'sub_group': 'dsl_interface'})
    ATTRS['TAM_ATTRIBUTES'] = get_attrs(['tr064'], {'group': 'tam'})
    ATTRS['WLAN_CONFIG_ATTRIBUTES'] = get_attrs(['tr064'], {'group': 'wlan_config'})
    ATTRS['WLAN_ATTRIBUTES'] = get_attrs(['tr064'], {'group': 'wlan'})
    ATTRS['FRITZ_DEVICE_ATTRIBUTES'] = get_attrs(['tr064'], {'group': 'fritz_device'})
    ATTRS['HOST_ATTRIBUTES'] = get_attrs(['tr064'], {'group': 'host', 'sub_group': 'host'})
    ATTRS['HOSTS_ATTRIBUTES'] = get_attrs(['tr064'], {'group': 'host', 'sub_group': 'gen'})
    ATTRS['HOST_ATTRIBUTES_CHILD'] = get_attrs(['tr064'], {'group': 'host', 'sub_group': 'child'})
    ATTRS['DEFLECTION_ATTRIBUTES'] = get_attrs(['tr064'], {'group': 'deflection'})
    ATTRS['HOMEAUTO_RO_ATTRIBUTES'] = get_attrs(['tr064'], {'group': 'homeauto', 'access': 'ro'})
    ATTRS['HOMEAUTO_RW_ATTRIBUTES'] = get_attrs(['tr064'], {'group': 'homeauto', 'access': 'rw'})
    ATTRS['HOMEAUTO_ATTRIBUTES'] = get_attrs(['tr064'], {'group': 'homeauto'})
    ATTRS['MYFRITZ_ATTRIBUTES'] = get_attrs(['tr064'], {'group': 'myfritz'})

    # create file and write header
    f = open(FILENAME_ATTRIBUTES, "w")
    f.write(FILE_HEADER)
    f.close()

    # write avm_data_types
    for attr, alist in ATTRS.items():
        with open(FILENAME_ATTRIBUTES, "a") as f:
            print(f'{attr} = {alist!r}', file=f)

    print(f'   {FILENAME_ATTRIBUTES} successfully created!')


def create_plugin_yaml_avm_data_type_valids(ifaces: list = ATTRIBUTES_LIST):
    """Create valid_list of avm_data_type based on master dict"""

    interface_group = None
    valid_list_str =      """        # NOTE: valid_list is automatically created by using item_attributes_master.py"""
    valid_list_desc_str = """        # NOTE: valid_list_description is automatically created by using item_attributes_master.py"""

    for iface in ifaces:
        valid_list_str = f"{valid_list_str}\n            # {iface} Attributes"
        valid_list_desc_str = f"{valid_list_desc_str}\n            # {iface} Attributes"

        for avm_data_type in AVM_DATA_TYPES[iface]:
            interface_group_new = f"{AVM_DATA_TYPES[iface][avm_data_type]['interface']}-{AVM_DATA_TYPES[iface][avm_data_type]['group']}"
            if interface_group_new != interface_group:
                interface_group = interface_group_new

                valid_list_str = f"""{valid_list_str}\n\
              # {interface_group} Attributes"""

                valid_list_desc_str = f"""{valid_list_desc_str}\n\
              # {interface_group} Attributes"""

            valid_list_str = f"""{valid_list_str}\n\
              - {avm_data_type!r:<40}# {AVM_DATA_TYPES[iface][avm_data_type]['access']:<5}{AVM_DATA_TYPES[iface][avm_data_type]['type']:<5}"""

            valid_list_desc_str = f"""{valid_list_desc_str}\n\
                          - '{AVM_DATA_TYPES[iface][avm_data_type]['description']:<}'"""

    valid_list_desc_str = f"""{valid_list_desc_str}\n\r"""

    return valid_list_str, valid_list_desc_str


def update_plugin_yaml_avm_data_type():
    """Update ´'valid_list' and 'valid_list_description' of 'avm_data_type´ in plugin.yaml"""

    print()
    print(f"B) Start updating Attribute '{ATTRIBUTE}' in {FILENAME_PLUGIN}!")

    yaml = ruamel.yaml.YAML()
    yaml.indent(mapping=4, sequence=4, offset=4)
    yaml.width = 200
    yaml.allow_unicode = True
    yaml.preserve_quotes = False

    valid_list_str, valid_list_description_str = create_plugin_yaml_avm_data_type_valids()

    with open(FILENAME_PLUGIN, 'r', encoding="utf-8") as f:
        data = yaml.load(f)

    if data.get('item_attributes', {}).get(ATTRIBUTE):
        data['item_attributes'][ATTRIBUTE]['valid_list'] = yaml.load(valid_list_str)
        data['item_attributes'][ATTRIBUTE]['valid_list_description'] = yaml.load(valid_list_description_str)

        with open(FILENAME_PLUGIN, 'w', encoding="utf-8") as f:
            yaml.dump(data, f)
        print(f'   valid_list and valid_list_description of {ATTRIBUTE} successfully updated in {FILENAME_PLUGIN}!')
    else:
        print(f'   Attribut "avm_data_type" not defined in {FILENAME_PLUGIN}')


def check_plugin_yaml_structs():
    # check structs for wrong attributes
    print()
    print(f'C) Checking {ATTRIBUTE} in structs defined in {FILENAME_PLUGIN} ')

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

    attributes_list = get_attrs()

    failure_found = False
    if structs:
        for attr, attr_val in get_all_keys(structs):
            if attr == ATTRIBUTE:
                if attr_val not in attributes_list:
                    print(f"    - {attr_val} not a valid value for {ATTRIBUTE}")
                    failure_found = True

    if not failure_found:
        print(f'   All selected {ATTRIBUTE}s are valid.')
    print(f'   Check complete.')


def update_user_doc():
    # Update user_doc.rst
    print()
    print(f'D) Start updating {ATTRIBUTE} and descriptions in {DOC_FILE_NAME}!"')
    attribute_list = [
        "\n",
        "Dieses Kapitel wurde automatisch durch Ausführen des Skripts in der Datei 'datapoints.py' erstellt.\n", "\n",
        "Nachfolgend eine Auflistung der möglichen Attribute für das Plugin:\n",
        "\n"]

    for attribute in AVM_DATA_TYPES:
        attribute_list.append("\n")
        attribute_list.append(f"{attribute.upper()}-Interface\n")
        attribute_list.append('-' * (len(attribute) + 10))
        attribute_list.append("\n")
        attribute_list.append("\n")

        for avm_data_type in AVM_DATA_TYPES[attribute]:
            attribute_list.append(f"- {avm_data_type}: {AVM_DATA_TYPES[attribute][avm_data_type]['description']} "
                                  f"| Zugriff: {AVM_DATA_TYPES[attribute][avm_data_type]['access']} "
                                  f"| Item-Type: {AVM_DATA_TYPES[attribute][avm_data_type]['type']}\n")
            attribute_list.append("\n")

    with open(DOC_FILE_NAME, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    start = end = None
    for i, line in enumerate(lines):
        if 'Attribute und Beschreibung' in line:
            start = i
        if 'item_structs' in line:
            end = i

    part1 = lines[0:start+2]
    part3 = lines[end-1:len(lines)]
    new_lines = part1 + attribute_list + part3

    with open(DOC_FILE_NAME, 'w', encoding='utf-8') as file:
        for line in new_lines:
            file.write(line)

    print(f"   Successfully updated {ATTRIBUTE} in {DOC_FILE_NAME}!")


if __name__ == '__main__':
    print()
    print(f'Start automated update and check of {FILENAME_PLUGIN} with generation of {FILENAME_ATTRIBUTES} and update of {DOC_FILE_NAME}.')
    print('------------------------------------------------------------------------')

    export_item_attributs_py()

    update_plugin_yaml_avm_data_type()

    check_plugin_yaml_structs()

    update_user_doc()

    print()
    print(f'Automated update and check of {FILENAME_PLUGIN} and generation of {FILENAME_ATTRIBUTES} complete.')

# Notes:
#   - HOST_ATTRIBUTES: host index needed
#   - HOSTS_ATTRIBUTES: no index needed
#   - HOST_ATTRIBUTES_CHILD: avm_mac needed
