# AVM

# Requirements
This plugin requires lib requests. You can install this lib with: 
<pre>
sudo pip3 install requests --upgrade
</pre>

It is completely based on the TR-064 interface from AVM (http://avm.de/service/schnittstellen/)

Version 0.914 tested with a FritzBox 7490 (FRITZ!OS 06.51), a FRITZ! WLAN Repeater 1750E (FRITZ!OS 06.32) and a
WLAN Repeater 300E (FRITZ!OS 06.30).

The MonitoringService currently does not support parallel incoming or outgoing calls. For being able to connect to
the FritzDevice's CallMonitor, you have to activate it, by typing `#96*5*` on a directly connected phone.

# Configuration

## plugin.conf
<pre>
[fb1]
    class_name = AVM
    class_path = plugins.avm
    username = ... # optional
    password = ...
    host = fritz.box
    port = 49443
    cycle = 300
    ssl = True     # use https or not
    verify = False # verify ssl certificate
    call_monitor = True
    avm_identifier = fritzbox_1
[fb2]
    class_name = AVM
    class_path = plugins.avm
    username = ... # optional
    password = ...
    host = ...
    port = 49443
    cycle = 300
    ssl = True     # use https or not
    verify = False # verify ssl certificate
    call_monitor = True
    avm_identifier = fritzbox_2
[...]    
</pre>

Note: Depending on the FritzDevice a shorter cycle time can result in problems with CPU rating and, in consequence with the accessibility of the webservices on the device.
If cycle time is reduced, please carefully watch your device and your sh.log. In the development process, 120 Seconds also worked worked fine on the used devices.

### Attributes
  * `username`: Optional login information
  * `password`: Required login information
  * `host`: Hostname or ip address of the FritzDevice.
  * `port`: Port of the FritzDevice, typically 49433 for https or 49000 for http
  * `cycle`: timeperiod between two update cycles. Default is 240 seconds.
  * `ssl`: True or False => True will add "https", False "http" to the URLs in the plugin
  * `verify`: True or False => Turns certificate verification on or off. Typically False
  * `call_monitor`: True or False => Activates or deactivates the MonitoringService, which connects to the FritzDevice's call monitor
  * `avm_identifier`: Unique identifier for each FritzDevice / each instance of the plugin

## items.conf

### avm_identifier
This attribute defines to which instance of the plugin the item is related to. See avm_identifier above.

### avm_data_type
This attribute defines supported functions that can be set for an item. Full set see example below.

### Example:
<pre>
[example] 
	[[uptime_7490]]
        type = num
        visu_acl = ro
        avm_data_type = uptime
        avm_identifier = fritzbox_1
    [[uptime_1750]]
        type = num
        visu_acl = ro
        avm_data_type = uptime
        avm_identifier = wlan_repeater_1750
    [[serial_number_7490]]
        type = str
        visu_acl = ro
        avm_data_type = serial_number
        avm_identifier = fritzbox_1
    [[serial_number_1750]]
        type = str
        visu_acl = ro
        avm_data_type = serial_number
        avm_identifier = wlan_repeater_1750
    [[firmware_7490]]
        type = str
        visu_acl = ro
        avm_data_type = software_version
        avm_identifier = fritzbox_1
    [[firmware_1750]]
        type = str
        visu_acl = ro
        avm_data_type = software_version
        avm_identifier = wlan_repeater_1750
    [[hardware_version_7490]]
        type = str
        visu_acl = ro
        avm_data_type = hardware_version
        avm_identifier = fritzbox_1
    [[hardware_version_1750]]
        type = str
        visu_acl = ro
        avm_data_type = hardware_version
        avm_identifier = wlan_repeater_1750
    [[myfritz]]
    	type = bool
        avm_identifier = fritzbox_1
        avm_data_type = myfritz_status
	[[monitor]]
	    [[[incoming]]]
            [[[[is_call_incoming]]]]
                type = bool
                avm_identifier = fritzbox_1
                avm_data_type = is_call_incoming
                cache = yes
            [[[[duration]]]]
                type = num
                avm_identifier = fritzbox_1
                avm_data_type = call_duration_incoming
                cache = yes
            [[[[last_caller]]]]
                type = str
                avm_identifier = fritzbox_1
                avm_data_type = last_caller_incoming
                cache = yes
            [[[[last_call_date]]]]
                type = str
                avm_identifier = fritzbox_1
                avm_data_type = last_call_date_incoming
                cache = yes
            [[[[event]]]]
                type = str
                avm_identifier = fritzbox_1
                avm_data_type = call_event_incoming
                cache = yes
	    [[[outgoing]]]
	        [[[[is_call_outgoing]]]]
                type = bool
                avm_identifier = fritzbox_1
                avm_data_type = is_call_outgoing
                cache = yes
            [[[[duration]]]]
                type = num
                avm_identifier = fritzbox_1
                avm_data_type = call_duration_outgoing
                cache = yes
            [[[[last_caller]]]]
                type = str
                avm_identifier = fritzbox_1
                avm_data_type = last_caller_outgoing
                cache = yes
            [[[[last_call_date]]]]
                type = str
                avm_identifier = fritzbox_1
                avm_data_type = last_call_date_outgoing
                cache = yes
            [[[[event]]]]
                type = str
                avm_identifier = fritzbox_1
                avm_data_type = call_event_outgoing
                cache = yes
        [[[newest]]]
            [[[[direction]]]]
                type = str
                avm_identifier = fritzbox_1
                avm_data_type = call_direction
                cache = yes
            [[[[event]]]]
                type = str
                avm_identifier = fritzbox_1
                avm_data_type = call_event
                cache = yes
    [[tam]]        
        index = 1
        type = bool
        visu_acl = rw
        avm_identifier = fritzbox_1
        avm_data_type = tam
        [[[name]]]
            type = str
            visu_acl = ro
            avm_identifier = fritzbox_1
            avm_data_type = tam_name
        [[[message_number_old]]]
            type = num
            visu_acl = ro
            avm_identifier = fritzbox_1
            avm_data_type = tam_old_message_number
            eval = (sh.avm.tam.message_number_total()-sh.avm.tam.message_number_new())
            eval_trigger = avm.tam.message_number_total | avm.tam.message_number_new
        [[[message_number_new]]]
            type = num
            visu_acl = ro
            avm_identifier = fritzbox_1
            avm_data_type = tam_new_message_number
        [[[message_number_total]]]
            type = num
            visu_acl = ro
            avm_identifier = fritzbox_1
            avm_data_type = tam_total_message_number
    [[wan]]   
        [[[connection_status]]]
           	type = str
           	visu_acl = ro
            avm_data_type = wan_connection_status
            avm_identifier = fritzbox_1
        [[[connection_error]]]
           	type = str
           	visu_acl = ro
            avm_data_type = wan_connection_error
            avm_identifier = fritzbox_1
        [[[is_connected]]]
            type = bool
            visu_acl = ro
            avm_data_type = wan_is_connected
            avm_identifier = fritzbox_1
        [[[uptime]]]
            type = num
            visu_acl = ro
            avm_data_type = wan_uptime
            avm_identifier = fritzbox_1
        [[[ip]]]
            type = str
            visu_acl = ro
            avm_data_type = wan_ip
            avm_identifier = fritzbox_1
        [[[upstream]]]
            type = num
            visu_acl = ro
            avm_data_type = wan_upstream
            avm_identifier = fritzbox_1
        [[[downstream]]]
            type = num
            visu_acl = ro
            avm_data_type = wan_downstream
            avm_identifier = fritzbox_1
        [[[total_packets_sent]]]
            type = num
            visu_acl = ro
            avm_data_type = wan_total_packets_sent
            avm_identifier = fritzbox_1
        [[[total_packets_received]]]
            type = num
            visu_acl = ro
            avm_data_type = wan_total_packets_received
            avm_identifier = fritzbox_1
        [[[total_bytes_sent]]]
            type = num
            visu_acl = ro
            avm_data_type = wan_total_bytes_sent
            avm_identifier = fritzbox_1
        [[[total_bytes_received]]]
            type = num
            visu_acl = ro
            avm_data_type = wan_total_bytes_received
            avm_identifier = fritzbox_1
        [[[link]]]
            type = bool
            visu_acl = ro
            avm_data_type = wan_link
            avm_identifier = fritzbox_1
    [[wlan]]
        [[[gf_wlan_1]]]
            type = bool
            visu_acl = rw
            avm_data_type = wlanconfig #2,4ghz
            avm_wlan_index = 1
            avm_identifier = fritzbox_1 
        [[[gf_wlan_2]]]
            type = bool
            visu_acl = rw
            avm_data_type = wlanconfig #5 GHz
            avm_wlan_index = 2
            avm_identifier = fritzbox_1# 
        [[[gf_wlan_3]]] 
            type = bool
            visu_acl = rw
            avm_data_type = wlanconfig # Guest
            avm_wlan_index = 3
            avm_identifier = fritzbox_1
        [[[gf_wlan_3_tr]]] 
            type = num
            visu_acl = rw
            avm_data_type = wlan_guest_time_remaining # Guest
            avm_wlan_index = 3
            avm_identifier = fritzbox_1
        [[[uf_wlan_1]]]
            type = bool
            visu_acl = rw
            avm_data_type = wlanconfig #2,4ghz
            avm_wlan_index = 1
            avm_identifier = wlan_repeater_1750 
        [[[uf_wlan_2]]]
            type = bool
            visu_acl = rw
            avm_data_type = wlanconfig #5 GHz
            avm_wlan_index = 2
            avm_identifier = wlan_repeater_1750
        [[[uf_wlan_3]]] 
            type = bool
            visu_acl = rw 
            avm_data_type = wlanconfig # Guest
            avm_wlan_index = 3
            avm_identifier = wlan_repeater_1750
        [[[garage_wlan_1]]]
            type = bool
            visu_acl = rw
            avm_data_type = wlanconfig # Wifi
            avm_wlan_index = 1
            avm_identifier = wlan_repeater_300 
        [[[garage_wlan_2]]]
            type = bool
            visu_acl = rw
            avm_data_type = wlanconfig # Guest (e.g. on devices where no 5ghz wifi is possible)
            avm_wlan_index = 2
            avm_identifier = wlan_repeater_300
    [[devices]]
        [[[iPad]]]
            mac = 96:B9:35:8F:7F:A2
            avm_data_type = network_device
            type = bool
            visu_acl = ro
            avm_identifier = fritzbox_1
            [[[[ip]]]] # no avm_identifier necessary, attributes are parsed via child items
                type = str
                avm_data_type = device_ip
                visu_acl = ro
            [[[[connection_type]]]]
                type = str
                avm_data_type = device_connection_type
                visu_acl = ro
            [[[[hostname]]]]
                type = str
                avm_data_type = device_hostname
                visu_acl = ro
        [[[GalaxyS5]]]
            mac = 18:4B:87:33:B3:AE
            avm_data_type = network_device
            type = bool
            visu_acl = ro
            avm_identifier = fritzbox_1
            [[[[ip]]]]
                type = str
                avm_data_type = device_ip
                visu_acl = ro
            [[[[connection_type]]]]
                type = str
                avm_data_type = device_connection_type
                visu_acl = ro
            [[[[hostname]]]]
                type = str
                avm_data_type = device_hostname
                visu_acl = ro      
        [[[Denon]]]
            mac = 00:05:CD:5F:97:EC
            avm_data_type = network_device
            type = bool
            visu_acl = ro
            avm_identifier = fritzbox_1
            [[[[ip]]]]
                type = str
                avm_data_type = device_ip
                visu_acl = ro
            [[[[connection_type]]]]
                type = str
                avm_data_type = device_connection_type
                visu_acl = ro
            [[[[hostname]]]]
                type = str
                avm_data_type = device_hostname
                visu_acl = ro
    [[dect]]
        [[[socket_living]]]
            type = bool
            avm_data_type = aha_device
            avm_identifier = fritzbox_1
            ain = 08761 0208600 # has to be identical to id in fritzbox (also with spaces!)
            visu_acl = rw
            [[[[energy]]]]
                avm_data_type = energy
                type = num
                visu_acl = ro
            [[[[power]]]]
                avm_data_type = power
                type = num
                sqlite = yes 
                visu_acl = ro
                eval = value / 100
            [[[[temperature]]]]
                avm_data_type = temperature
                type = num
                visu_acl = ro
        [[[socket_office]]]
            type = bool
            avm_data_type = aha_device
            avm_identifier = fritzbox_1
            ain = 08761 0209293 # has to be identical to id in fritzbox (also with spaces!)
            visu_acl = rw
            [[[[energy]]]]
                avm_data_type = energy
                type = num
                visu_acl = ro
            [[[[power]]]]
                avm_data_type = power
                type = num
                sqlite = yes 
                visu_acl = ro
                eval = value / 100
            [[[[temperature]]]]
                avm_data_type = temperature
                type = num
                visu_acl = ro
</pre>

# Functions

## set_call_origin(phone_name)
Sets the origin of a call. E.g. an internal number associated to a phone. Typically set before using "start_call".
<pre>
sh.fb1.set_call_origin("**610")
</pre>       

## start_call(phone_number)
This function starts a call. Parameter can be an external or internal number.
<pre>
sh.fb1.start_call('0891234567')
sh.fb1.start_call('**9')
</pre>

## cancel_call()
This function cancels a running call.

## reconnect()
This function reconnects the WAN (=internet) connection.

## reboot()
This function reboots the FritzDevice.

## get_contact_name_by_phone_number(phone_number)
This is a function to search for telephone numbers in the contacts stored on the devices phone book

## get_calllist()
Returns an array with calllist entries

## is_host_active(mac_address)
This function checks, if a device running on a given mac address is active on the FritzDevice. Can be used for presence detection.
