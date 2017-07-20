# RTR plug-in

Providing a room temperature regulator

## Configuration

### plugin.conf

```
[rtr]
    class_name = RTR
    class_path = plugins.rtr
#    default_Kp = # Proportional gain
#    default_Ki = # Integral gain
```

Description of the attributes:

* __default_Kp__: change default value for Kp (optional, default: 5)
* __default_Ki__: change default value for Ki (optional, default: 240)

### items.conf

Three items need to be assigned ``rtr_current``, ``rtr_setpoint`` and ``rtr_actuator``. The attributes each are assigned an integer index.
The same index shows that the items belong to the same rtr.

The value of the items must be a numeric one.

#### rtr_current

This attribute marks the item with an integer index as a provider for the *current value* (e.g. measured temperature)
In the example below it is the item ``gf.floor.temp``

#### rtr_setpoint

This attribute marks the item as a provider for the *setpoint value* (e.g. the wanted temperature in a room). In the example below it is the item ``gf.floor.temp.set``

#### rtr_actuator

This attribute marks the item as a receiving one for the value to be sent to the actuator.  In the example below it is the item ``gf.floor.temp.state``

#### Example

The following shows an example for a working 

```
# items/gf.conf
[gf]
    [[floor]]
        [[[temp]]]
            name = Temp
            type = num
            knx_dpt = 9
            knx_send = 4/2/120
            knx_reply = 4/2/120
            ow_addr = 28.52734A030000
            ow_sensor = T
            rtr_current = 1

            [[[[set]]]]
                type = num
                visu = yes
                cache = On
                knx_dpt = 9
                knx_send = 4/3/120
                knx_listen = 4/3/120
                rtr_setpoint = 1

            [[[[state]]]]
                type = num
                visu = yes
                knx_dpt = 9
                knx_send = 4/1/120
                knx_listen = 4/1/120
                rtr_actuator = 1
```

```yaml
gf:

    floor:

        temp:
            name: Temp
            type: num
            knx_dpt: 9
            knx_send: 4/2/120
            knx_reply: 4/2/120
            ow_addr: 28.52734A030000
            ow_sensor: T
            rtr_current: 1

            set:
                type: num
                visu: 'yes'
                cache: 'On'
                knx_dpt: 9
                knx_send: 4/3/120
                knx_listen: 4/3/120
                rtr_setpoint: 1

            state:
                type: num
                visu: 'yes'
                knx_dpt: 9
                knx_send: 4/1/120
                knx_listen: 4/1/120
                rtr_actuator: 1
```
