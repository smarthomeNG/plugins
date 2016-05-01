# Enigma2

# Requirements
This plugin requires lib requests. You can install this lib with: 
<pre>
sudo pip3 install requests --upgrade
</pre>

It is completely based on the openwebif interface for Enigma2 devices

Version 0.1 tested with a VUSolo2 and a VUSolo4k with newest VTI Image
The version is pre alpha and continously under development.

# Configuration

## plugin.conf
<pre>
[vusolo4k]
    class_name = Enigma2
    class_path = plugins.enigma2
    host = xxx.xxx.xxx.xxx
    port = 81
    cycle = 240
    ssl = False    # use https or not
    verify = False # verify ssl certificate
    device_id = vusolo4k
[vusolo2]
    class_name = Enigma2
    class_path = plugins.enigma2
    host = xxx.xxx.xxx.xxx
    port = 81
    cycle = 240
    ssl = False    # use https or not
    verify = False # verify ssl certificate
    device_id = vusolo2
[...]    
</pre>

Note: Depending on the device a shorter cycle time can result in problems with CPU rating and, in consequence with the accessibility of the services on the device.
If cycle time is reduced, please carefully watch your device and your sh.log. In the development process, 240 seconds also worked worked fine on the used devices.

### Attributes
  * `username`: Optional login information #not tested so far
  * `password`: Optional login information #not tested so far
  * `host`: Hostname or ip address of the FritzDevice.
  * `port`: Port of the FritzDevice, typically 49433 for https or 49000 for http
  * `cycle`: timeperiod between two update cycles. Default is 240 seconds.
  * `ssl`: True or False => True will add "https", False "http" to the URLs in the plugin
  * `verify`: True or False => Turns certificate verification on or off. Typically False
  * `device_id`: Unique identifier for each Enigma2Device / each instance of the plugin

## items.conf

### avm_identifier
This attribute defines to which instance of the plugin the item is related to. See avm_identifier above.

### avm_data_type
This attribute defines supported functions that can be set for an item. Full set see example below.

### Example:
<pre>
[enigma2]
    [[vusolo4k]]
        [[[e2enigmaversion]]]
            type = str
            enigma2_data_type = e2enigmaversion
            enigma2_page = about
            device_id = vusolo4k
            visu_acl = ro
        [[[e2imageversion]]]
            type = str
            enigma2_data_type = e2imageversion
            enigma2_page = about
            device_id = vusolo4k
            visu_acl = ro
        [[[e2webifversion]]]
            type = str
            enigma2_data_type = e2webifversion
            enigma2_page = about
            device_id = vusolo4k
            visu_acl = ro
        [[[e2model]]]
            type = str
            enigma2_data_type = e2model
            enigma2_page = about
            device_id = vusolo4k
            visu_acl = ro
        [[[e2videowidth]]]
            type = num
            enigma2_data_type = e2videowidth
            enigma2_page = about
            device_id = vusolo4k
            visu_acl = ro
        [[[e2videoheight]]]
            type = num
            enigma2_data_type = e2videowidth
            enigma2_page = about
            device_id = vusolo4k
            visu_acl = ro
        [[[e2videoheight]]]
            type = num
            enigma2_data_type = e2apid
            enigma2_page = about
            device_id = vusolo4k
            visu_acl = ro
        [[[e2instandby]]]
            type = bool
            enigma2_data_type = e2instandby
            enigma2_page = powerstate
            device_id = vusolo4k
            visu_acl = ro
        [[[e2servicename]]]
            type = str
            enigma2_data_type = e2servicename
            enigma2_page = subservices
            device_id = vusolo4k
            visu_acl = ro
        [[[remote]]] # see http://dream.reichholf.net/wiki/Enigma2:WebInterface#RemoteControl
            [[[[POWER]]]]
                type = bool
                visu_acl = rw
                enigma2_remote_command_id = 116
                device_id = vusolo4k
                enforce_updates = true
            [[[[OK]]]]
                type = bool
                visu_acl = rw
                enigma2_remote_command_id = 352
                device_id = vusolo4k
                enforce_updates = true
            [[[[EXIT]]]]
                type = bool
                visu_acl = rw
                enigma2_remote_command_id = 174
                device_id = vusolo4k
                enforce_updates = true
            [[[[INFO]]]]
                type = bool
                visu_acl = rw
                enigma2_remote_command_id = 352
                device_id = vusolo4k
                enforce_updates = true
            [[[[AUDIO]]]]
                type = bool
                visu_acl = rw
                enigma2_remote_command_id = 392
                device_id = vusolo4k
                enforce_updates = true
            [[[[VIDEO]]]]
                type = bool
                visu_acl = rw
                enigma2_remote_command_id = 393
                device_id = vusolo4k
                enforce_updates = true
            [[[[EPG]]]]
                type = bool
                visu_acl = rw
                enigma2_remote_command_id = 358
                device_id = vusolo4k
                enforce_updates = true
            [[[[MENU]]]]
                type = bool
                visu_acl = rw
                enigma2_remote_command_id = 139
                device_id = vusolo4k
                enforce_updates = true
            [[[[SUBTITLE]]]]
                type = bool
                visu_acl = rw
                enigma2_remote_command_id = 370
                device_id = vusolo4k
                enforce_updates = true
            [[[[UP]]]]
                type = bool
                visu_acl = rw
                enigma2_remote_command_id = 103
                device_id = vusolo4k
                enforce_updates = true
            [[[[DOWN]]]]
                type = bool
                visu_acl = rw
                enigma2_remote_command_id = 108
                device_id = vusolo4k
                enforce_updates = true
            [[[[LEFT]]]]
                type = bool
                visu_acl = rw
                enigma2_remote_command_id = 105
                device_id = vusolo4k
                enforce_updates = true
            [[[[RIGHT]]]]
                type = bool
                visu_acl = rw
                enigma2_remote_command_id = 106
                device_id = vusolo4k
                enforce_updates = true
            [[[[VolUP]]]]
                type = bool
                visu_acl = rw
                enigma2_remote_command_id = 115
                device_id = vusolo4k
                enforce_updates = true
            [[[[VolDOWN]]]]
                type = bool
                visu_acl = rw
                enigma2_remote_command_id = 114
                device_id = vusolo4k
                enforce_updates = true
            [[[[MUTE]]]]
                type = bool
                visu_acl = rw
                enigma2_remote_command_id = 113
                device_id = vusolo4k
                enforce_updates = true
            [[[[NEXT]]]]
                type = bool
                visu_acl = rw
                enigma2_remote_command_id = 407
                device_id = vusolo4k
                enforce_updates = true
            [[[[PREVIOUS]]]]
                type = bool
                visu_acl = rw
                enigma2_remote_command_id = 412
                device_id = vusolo4k
                enforce_updates = true
            [[[[0]]]]
                type = bool
                visu_acl = rw
                enigma2_remote_command_id = 11
                device_id = vusolo4k
                enforce_updates = true
            [[[[1]]]]
                type = bool
                visu_acl = rw
                enigma2_remote_command_id = 2
                device_id = vusolo4k
                enforce_updates = true
            [[[[2]]]]
                type = bool
                visu_acl = rw
                enigma2_remote_command_id = 3
                device_id = vusolo4k
                enforce_updates = true
            [[[[3]]]]
                type = bool
                visu_acl = rw
                enigma2_remote_command_id = 4
                device_id = vusolo4k
                enforce_updates = true
            [[[[4]]]]
                type = bool
                visu_acl = rw
                enigma2_remote_command_id = 5
                device_id = vusolo4k
                enforce_updates = true
            [[[[5]]]]
                type = bool
                visu_acl = rw
                enigma2_remote_command_id = 6
                device_id = vusolo4k
                enforce_updates = true
            [[[[6]]]]
                type = bool
                visu_acl = rw
                enigma2_remote_command_id = 7
                device_id = vusolo4k
                enforce_updates = true
            [[[[7]]]]
                type = bool
                visu_acl = rw
                enigma2_remote_command_id = 8
                device_id = vusolo4k
                enforce_updates = true
            [[[[8]]]]
                type = bool
                visu_acl = rw
                enigma2_remote_command_id = 9
                device_id = vusolo4k
                enforce_updates = true
            [[[[9]]]]
                type = bool
                visu_acl = rw
                enigma2_remote_command_id = 10
                device_id = vusolo4k
                enforce_updates = true
</pre>

# Functions

## send_message(self, messagetext, messagetype=1, timeout=10)
Sets a message to the device
messagetype: Number from 0 to 3, 0= Yes/No, 1= Info, 2=Message, 3=Attention
timeout: Number of seconds the message should stay on the device, default: 10
<pre>
sh.vusolo4k.send_message("Testnachricht",1,10)
</pre>       

## get_answer()
This function checks for an answer to a sent message. If you call this method, take into account the timeout until the message can be answered and e.g. set a "while (count < 0)"
<pre>
sh.vusolo4k.get_answer()
</pre>
