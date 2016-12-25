# SMA-EM Plugin

Version 1.3.0.1

This plugin retrieves the data sent by the SMA Energy Meter.
In agreement with the author Florian Wenger, this plugin uses code published in
https://github.com/datenschuft/SMA-EM/ - especially the readem method.

# Requirements
This plugin requires lib requests. You can install this lib with:
<pre>
sudo pip3 install requests --upgrade
</pre>

Forum thread to the plugin: https://knx-user-forum.de/forum/supportforen/smarthome-py/986480-odlinfo-plugin-f%C3%BCr-strahlungsdaten

The SMA Energy Meter broadcasts its information via multicast to the network address 239.12.255.254. Beyond the items
supported by this plugin, the readem method allows for a lot more of parameters. The items will be extended in future
versions of this plugin on demand. The available values can be seen in the readem method of this plugin.

If demand exists, the plugin can also be extended to be used with more than 1 energy meter.

# Configuration

## plugin.conf
<pre>
[sma_em]
    class_name = SMA_EM
    class_path = plugins.sma_em
    serial = xxxxxxxxxx
    time_sleep = 5
</pre>

### Attributes
  * `serial`: The serial number of your energy meter
  * `time_sleep`: The time in seconds to sleep after a multicast was received. I introduced this to avoid too many values to be processed

## items.conf

### Example:
<pre>
# items/sma-em.conf
[smaem]
    [[surplus]]
        name = Solar Energy Surplus
        sma_em_data_type = psurplus
        type = num
        [[[kw]]]
			type = num
			eval = sh.smaem.surplus() / 1000
			eval_trigger = smaem.surplus
			database@mysqldb = init
    [[regard]]
        name = Solar Energy Regard
        sma_em_data_type = pregard
        type = num
		[[[kw]]]
			type = num
			eval = sh.smaem.regard() / 1000
			eval_trigger = smaem.regard
			database@mysqldb = init
	[[regard_active]]
        visu_acl = ro
        type = bool
    [[surplus_active]]
        visu_acl = ro
        type = bool
</pre>