# NUT - Network UPS Tools plugin

This plugin is connecting to NUT daemon and can be used to read ups variables. 

The primary goal of the Network UPS Tools (NUT) project is to provide support for Power Devices, 
such as Uninterruptible Power Supplies, Power Distribution Units, Automatic Transfer Switch, Power Supply Units and Solar Controllers.

The plugin can be used standalone to list available variables using command `upsc your_ups_name`.
More about NUT: http://networkupstools.org/


## Requirements

Configured & running upsd - NUT daemon


## Configuration

### plugin.conf

```yaml
nut:
    class_name: NUT
    class_path: plugins.nut
    ups: your_ups_name
    cycle: read cycle, optional, default 60
    host: upsd host, optional, default 'localhost'
    port: upsd port, optional, default 3493
    timeout: telnet read timeout, optional, default 5
```

## items.conf

```yaml
ups_item:
    ...
    nut_var: variable_name_from_upsc
```

## Example

The most important variable: `ups.status` is returned from ups as string containing `OL` - OnLine, `OB` - On Battery or `LB` - LowBattery. Easy way to parse to boolean:

```yaml
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
```

Other ups variables, like `battery.charge`, can be directly parsed to num by sh.
