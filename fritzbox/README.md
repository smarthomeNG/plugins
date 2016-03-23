# FritzBox

# Requirements
This plugin has no requirements or dependencies.
At the moment only fritzbox firmware versions before 5.50 are supported.

# Configuration

## plugin.conf
<pre>
[fritzbox]
    class_name = FritzBox
    class_path = plugins.fritzbox
    host = fritz.box
    password = blub
</pre>

### Attributes
  * `host`: specifies the hostname or ip address of the FritzBox.
  * `password`: the password of the FritzBox web interface.

## items.conf

### fritzbox
This attribute defines supported functions of the plugin. The function is executed, when the item is set to a bool `true` value.
Functions supported in the plugin:
 * `call <<from>> <<to>>`: The FritzBox will initiate a call from the number (outgoing line) defined with `from` to a number defined with `to`.

### fritzbox:<<telcfg>>
This attributes represents direct access to the FritzBox webinterface. Each attribute which starts with `fritzbox:` is taken to create a dictionary, which is sent to the FritzBox. Here you can use every command which is available for the telcfg interface (just replace the `telcfg:` with `fritzbox:`). A list of known commands is described here: http://www.wehavemorefun.de/fritzbox/Telcfg

Example item:

<pre>
<<<<<<< HEAD
[example]
    [[fritzbox]]
        [[[ip]]]
            type = str
            fritzbox = external_ip
        [[[connected]]]
            type = bool
            fritzbox = connected
        [[[packets_sent]]]
            type = num
            fritzbox = packets_sent
        [[[packets_received]]]
            type = num
            fritzbox = packets_received
        [[[bytes_sent]]]
            type = num
            fritzbox = bytes_sent
        [[[bytes_received]]]
            type = num
            fritzbox = bytes_received
        [[[tam]]]  # telephone answering machine
            type = bool
            fritzbox = tam # read only!
            fb_tam = 0
        [[[tam2]]]  # 2nd telephone answering machine
            type = bool
            fritzbox = tam # read only!
            fb_tam = 1
        [[[wlan]]]
            type = bool
            fritzbox = wlan
        [[[wlan_2]]]
            type = bool
            fritzbox = wlan
            fb_wlan = 2  # 5 GHz
        [[[link]]]
            type = bool
            fritzbox = link
        [[[host]]]
            type = bool
            fritzbox = host
            fb_mac = XX:XX:XX:XX:XX:XX 
    [[fbswitch]]
        type = bool
        fritzbox = switch
        fb_ain = 081111111111
        [[[energy]]]
            type = num
            fritzbox = energy  # Wh
        [[[power]]]
            type = num
            fritzbox = power  # mW
    [[fbswitch2]]
        type = num
        fritzbox = power
        fb_ain = 082222222222
        eval = value / 1000  # convert from mW to W
=======
[fb]
    [[call1]]
        type=bool
        fritzbox=call **610 **611
    [[call2]]
        type=bool
        fritzbox:settings/UseClickToDial = '1'
        fritzbox:command/Dial = '**610'
        fritzbox:settings/DialPort = '**611'
>>>>>>> parent of 099437a... fritzbox: rewritten
</pre>

Both `call1` and `call2` will have the same effect. The first uses the implemented call function. The later uses the telcfg commands which are used internally in the call function. With the second option you can control almost anything which can be controlled via the web interface of your FritzBox.

## logic.conf

Currently there is no logic configuration for this plugin.

# Functions

## call(from, to)
This function calls a specified number with the specified caller.
<pre>
sh.fritzbox.call('**610', '**611')
</pre>
<<<<<<< HEAD

## calllist()
This function returns a list of all calls.

## hangup()
This function hangs up ongoing calls.

## reboot()
This function reboots the FritzBox.

## reconnect()
This function reconnect the upstream connection.

## webcm(commands)
This is a legacy function to the 'old' interface. See [www.wehavemorefun.de/fritzbox/Telcfg](http://www.wehavemorefun.de/fritzbox/Telcfg) for a list of possible commands.
e.g. to make a call:
<pre>
sh.fritzbox.webcm({'telcfg:settings/UseClickToDial': '1', 'telcfg:command/Dial': '**611', 'telcfg:settings/DialPort': '**610'})
</pre>
=======
>>>>>>> parent of 099437a... fritzbox: rewritten
