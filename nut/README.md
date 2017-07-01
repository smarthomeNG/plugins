# NUT - Network UPS Tools plugin
This plugin is connecting to NUT daemon and can be used to read ups variables. You can list available variables using command `upsc your_ups_name`.
More about NUT: http://networkupstools.org/

Requirements
============
Configured & running upsd - NUT daemon


Configuration
=============

## plugin.conf

<pre>
nut:
    class_name: NUT
    class_path: plugins.nut
    ups: your_ups_name
    cycle: read cycle, optional, default 60
    host: upsd host, optional, default 'localhost'
    port: upsd port, optional, default 3493
    timeout: telnet read timeout, optional, default 5
</pre>

## items.conf
<pre>
ups_item:
    ...
    nut_var: variable_name_from_upsc
</pre>

## Example
The most important variable: `ups.status` is returned from ups as string containing `OL` - OnLine, `OB` - On Battery or `LB` - LowBattery. Easy way to parse to boolean:
<pre>
ups:  
    status:
        name: Status
        type: str
        nut_var: ups.status
        online:
            type: bool
            eval_trigger: ups.status 
            eval: 1 if 'OL' in sh.ups.status() else 0
        on_battery:
            type: bool
            eval_trigger: ups.status 
            eval: 1 if 'OB' in sh.ups.status() else 0
        low_battery:
            type: bool
            eval_trigger: ups.status 
            eval: 1 if 'LB' in sh.ups.status() else 0
    battery:
        percent:
            type: num
            sqlite: 'yes'
            nut_var: battery.charge
        voltage:
            type: num
            sqlite: 'yes'
            nut_var: battery.voltage
</pre>

Other ups variables, like `battery.charge`, can be directly parsed to num by sh.
