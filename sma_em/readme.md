# SMA-EM Plugin

Version 1.3.0.1

This plugin retrieves the data sent by the SMA Energy Meter.
In agreement with the author Florian Wenger, this plugin uses code published in
https://github.com/datenschuft/SMA-EM/ - especially the readem method.

Forum thread to the plugin: https://knx-user-forum.de/forum/supportforen/smarthome-py/1030610-sma_em-plugin

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
    [[regard]]
        name = Solar Energy Regard
        sma_em_data_type = pregard
        type = num
		[[[kw]]]
			type = num
			eval = sh.smaem.regard() / 1000
			eval_trigger = smaem.regard
</pre>