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

ALL_ATTRIBUTES_SUPPORTED_BY_REPEATER = ['uptime', 'software_version', 'hardware_version', 'serial_number', 'manufacturer', 'product_class', 'manufacturer_oui', 'model_name', 'description', 'device_log', 'security_port', 'reboot', 'wlanconfig', 'wlanconfig_ssid', 'wlan_guest_time_remaining', 'wlan_associates', 'wps_active', 'wps_status', 'wps_mode', 'wlan_total_associates', 'hosts_count', 'hosts_info', 'mesh_topology', 'number_of_hosts', 'hosts_url', 'mesh_url', 'network_device', 'device_ip', 'device_connection_type', 'device_hostname', 'connection_status', 'is_host_active', 'host_info']
ALL_ATTRIBUTES_WRITEABLE = ['reboot', 'set_target_temperature', 'set_window_open', 'set_hkr_boost', 'set_simpleonoff', 'set_level', 'set_levelpercentage', 'set_hue', 'set_saturation', 'set_colortemperature', 'switch_toggle', 'tam', 'wlanconfig', 'wps_active', 'deflection_enable', 'aha_device', 'target_temperature', 'window_open', 'hkr_boost', 'switch_state']
ALL_ATTRIBUTES_WRITEONLY = ['set_target_temperature', 'set_window_open', 'set_hkr_boost', 'set_simpleonoff', 'set_level', 'set_levelpercentage', 'set_hue', 'set_saturation', 'set_colortemperature', 'switch_toggle']
DEPRECATED_ATTRIBUTES = ['aha_device', 'hkr_device', 'set_temperature', 'temperature', 'set_temperature_reduced', 'set_temperature_comfort', 'firmware_version', 'boost_active']
AHA_ATTRIBUTES = ['device_id', 'manufacturer', 'product_name', 'fw_version', 'connected', 'device_name', 'tx_busy', 'device_functions', 'set_target_temperature', 'target_temperature', 'current_temperature', 'temperature_reduced', 'temperature_comfort', 'temperature_offset', 'set_window_open', 'window_open', 'windowopenactiveendtime', 'set_hkr_boost', 'hkr_boost', 'boost_active', 'boostactiveendtime', 'summer_active', 'holiday_active', 'battery_low', 'battery_level', 'lock', 'device_lock', 'errorcode', 'set_simpleonoff', 'simpleonoff', 'set_level', 'level', 'set_levelpercentage', 'levelpercentage', 'set_hue', 'hue', 'set_saturation', 'saturation', 'set_colortemperature', 'colortemperature', 'unmapped_hue', 'unmapped_saturation', 'color_mode', 'supported_color_mode', 'fullcolorsupport', 'mapped', 'switch_state', 'switch_mode', 'switch_toggle', 'power', 'energy', 'voltage', 'humidity', 'alert_state', 'blind_mode', 'endpositionsset']
AHA_RO_ATTRIBUTES = ['device_id', 'manufacturer', 'product_name', 'fw_version', 'connected', 'device_name', 'tx_busy', 'device_functions', 'current_temperature', 'temperature_reduced', 'temperature_comfort', 'temperature_offset', 'windowopenactiveendtime', 'boost_active', 'boostactiveendtime', 'summer_active', 'holiday_active', 'battery_low', 'battery_level', 'lock', 'device_lock', 'errorcode', 'color_mode', 'supported_color_mode', 'fullcolorsupport', 'mapped', 'switch_mode', 'power', 'energy', 'voltage', 'humidity', 'alert_state', 'blind_mode', 'endpositionsset']
AHA_WO_ATTRIBUTES = ['set_target_temperature', 'set_window_open', 'set_hkr_boost', 'set_simpleonoff', 'set_level', 'set_levelpercentage', 'set_hue', 'set_saturation', 'set_colortemperature', 'switch_toggle']
AHA_RW_ATTRIBUTES = ['target_temperature', 'window_open', 'hkr_boost', 'switch_state']
TR064_ATTRIBUTES = ['uptime', 'software_version', 'hardware_version', 'serial_number', 'manufacturer', 'product_class', 'manufacturer_oui', 'model_name', 'description', 'device_log', 'security_port', 'reboot', 'myfritz_status', 'call_direction', 'call_event', 'monitor_trigger', 'is_call_incoming', 'last_caller_incoming', 'last_call_date_incoming', 'call_event_incoming', 'last_number_incoming', 'last_called_number_incoming', 'is_call_outgoing', 'last_caller_outgoing', 'last_call_date_outgoing', 'call_event_outgoing', 'last_number_outgoing', 'last_called_number_outgoing', 'call_duration_incoming', 'call_duration_outgoing', 'tam', 'tam_name', 'tam_new_message_number', 'tam_old_message_number', 'tam_total_message_number', 'wan_connection_status', 'wan_connection_error', 'wan_is_connected', 'wan_uptime', 'wan_ip', 'wan_upstream', 'wan_downstream', 'wan_total_packets_sent', 'wan_total_packets_received', 'wan_current_packets_sent', 'wan_current_packets_received', 'wan_total_bytes_sent', 'wan_total_bytes_received', 'wan_current_bytes_sent', 'wan_current_bytes_received', 'wan_link', 'wlanconfig', 'wlanconfig_ssid', 'wlan_guest_time_remaining', 'wlan_associates', 'wps_active', 'wps_status', 'wps_mode', 'wlan_total_associates', 'hosts_count', 'hosts_info', 'mesh_topology', 'number_of_hosts', 'hosts_url', 'mesh_url', 'network_device', 'device_ip', 'device_connection_type', 'device_hostname', 'connection_status', 'is_host_active', 'host_info', 'number_of_deflections', 'deflections_details', 'deflection_details', 'deflection_enable', 'deflection_type', 'deflection_number', 'deflection_to_number', 'deflection_mode', 'deflection_outgoing', 'deflection_phonebook_id', 'aha_device', 'hkr_device', 'set_temperature', 'temperature', 'set_temperature_reduced', 'set_temperature_comfort', 'firmware_version']
AVM_RW_ATTRIBUTES = ['tam', 'wlanconfig', 'wps_active', 'deflection_enable', 'aha_device']
CALL_MONITOR_ATTRIBUTES = ['call_direction', 'call_event', 'monitor_trigger', 'is_call_incoming', 'last_caller_incoming', 'last_call_date_incoming', 'call_event_incoming', 'last_number_incoming', 'last_called_number_incoming', 'is_call_outgoing', 'last_caller_outgoing', 'last_call_date_outgoing', 'call_event_outgoing', 'last_number_outgoing', 'last_called_number_outgoing', 'call_duration_incoming', 'call_duration_outgoing']
CALL_MONITOR_ATTRIBUTES_TRIGGER = ['monitor_trigger']
CALL_MONITOR_ATTRIBUTES_GEN = ['call_direction', 'call_event']
CALL_MONITOR_ATTRIBUTES_IN = ['is_call_incoming', 'last_caller_incoming', 'last_call_date_incoming', 'call_event_incoming', 'last_number_incoming', 'last_called_number_incoming']
CALL_MONITOR_ATTRIBUTES_OUT = ['is_call_outgoing', 'last_caller_outgoing', 'last_call_date_outgoing', 'call_event_outgoing', 'last_number_outgoing', 'last_called_number_outgoing']
CALL_MONITOR_ATTRIBUTES_DURATION = ['call_duration_incoming', 'call_duration_outgoing']
WAN_CONNECTION_ATTRIBUTES = ['wan_connection_status', 'wan_connection_error', 'wan_is_connected', 'wan_uptime', 'wan_ip']
WAN_COMMON_INTERFACE_ATTRIBUTES = ['wan_total_packets_sent', 'wan_total_packets_received', 'wan_current_packets_sent', 'wan_current_packets_received', 'wan_total_bytes_sent', 'wan_total_bytes_received', 'wan_current_bytes_sent', 'wan_current_bytes_received', 'wan_link']
WAN_DSL_INTERFACE_ATTRIBUTES = ['wan_upstream', 'wan_downstream']
TAM_ATTRIBUTES = ['tam', 'tam_name', 'tam_new_message_number', 'tam_old_message_number', 'tam_total_message_number']
WLAN_CONFIG_ATTRIBUTES = ['wlanconfig', 'wlanconfig_ssid', 'wlan_guest_time_remaining', 'wlan_associates', 'wps_active', 'wps_status', 'wps_mode']
WLAN_ATTRIBUTES = ['wlan_total_associates']
FRITZ_DEVICE_ATTRIBUTES = ['uptime', 'software_version', 'hardware_version', 'serial_number', 'manufacturer', 'product_class', 'manufacturer_oui', 'model_name', 'description', 'device_log', 'security_port', 'reboot']
HOST_ATTRIBUTES = ['host_info']  # host index needed
HOST_ATTRIBUTES_CHILD = ['network_device', 'device_ip', 'device_connection_type', 'device_hostname', 'connection_status', 'is_host_active']  # avm_mac needed
HOSTS_ATTRIBUTES = ['hosts_count', 'hosts_info', 'mesh_topology', 'number_of_hosts', 'hosts_url', 'mesh_url']  # no index needed
DEFLECTION_ATTRIBUTES = ['number_of_deflections', 'deflections_details', 'deflection_details', 'deflection_enable', 'deflection_type', 'deflection_number', 'deflection_to_number', 'deflection_mode', 'deflection_outgoing', 'deflection_phonebook_id']
HOMEAUTO_RO_ATTRIBUTES = ['hkr_device', 'set_temperature', 'temperature', 'set_temperature_reduced', 'set_temperature_comfort', 'firmware_version']
HOMEAUTO_RW_ATTRIBUTES = ['aha_device']
HOMEAUTO_ATTRIBUTES = ['aha_device', 'hkr_device', 'set_temperature', 'temperature', 'set_temperature_reduced', 'set_temperature_comfort', 'firmware_version']
MYFRITZ_ATTRIBUTES = ['myfritz_status']