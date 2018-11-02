# RTR plug-in

Providing a room temperature regulator


## plugin.yaml

```
rtr:
    class_name: RTR
    class_path: plugins.rtr
    # default_Kp: 10 # Proportional gain
    # default_Ki: 15 # Integral gain
```

Description of the attributes:

* __default_Kp__: change default value for Kp (optional, default: 10)
* __default_Ki__: change default value for Ki (optional, default: 15)

## items.yaml

Three items need to be assigned ``rtr_current``, ``rtr_setpoint`` and ``rtr_actuator``. The attributes each are assigned an integer index.
The same index shows that the items belong to the same controller.

But we have now a lot of optional attributes to custumize our controller from global defaults, read below.

### Required attributes:

#### rtr_current

This attribute marks the item with an integer index as a provider for the *current value* (e.g. measured temperature)
In the example below it is the item ``gf.floor.temp``

#### rtr_setpoint

This attribute marks the item as a provider for the *setpoint value* (e.g. the wanted temperature in a room). In the example below it is the item ``gf.floor.temp.set``

#### rtr_actuator

This attribute marks the item as a receiving one for the value to be sent to the actuator.  In the example below it is the item ``gf.floor.temp.state``

### Optional attributes

#### rtr_Kp, rtr_Ki

With those you can define different Kp and/or Ki values to your controller, which override the global default from default_Kp/default_Ki.

***The attributes are only valid on the same item, where ``rtr_current`` is defined and belongs to that controller.***

#### rtr_stops

This attribute can be used to define a item as a stop/pause trigger of the given contoller(s). When the value of the Item changes to on/true the controller(s) stops execution and set rtr_actuator to 0, till the value changes back to off/false.

***The attributes can only be set on a Item of type Bool. You can add muliple Items to one controller and also one Item to multiple controllers***

#### rtr_temp_default, rtr_temp_boost, rtr_temp_boost_time, rtr_temp_drop

They are for a new way, to handle 3 different temperature modes:

First we have a ``default`` room temperature, lets say 21 °C

This is set with ``rtr_temp_default = 21``

Now when we want to ``boost`` the temperature for a special event or what ever you can imagine, you can set the temperature manually to a higher value and hope you dont forget to set it back.

Or u use the boost function of this plugin, to set the temperature to your predefinied value of 23 °C. The Boost function will also handle for you a timer, when the temperature will be set back (lets say in 3 hours) to the predefinied default temperature.

For this set ``rtr_temp_boost = 23``. The end time, where the value will be set back to Default is defined in minutes. We can use the global attribute defaultBoostTime or you set a individual time.

For those finding this is not flexible enough: The function boost() can also be called with a individual end time. So you can create multiple logics with individual times and bind them to extra items.

Now at least we have third temperature mode ``drop``. With it you can build as example a away mode or night reduction where you want want to set temperature to maybe 19 °C.

So u set ``rtr_temp_drop = 19`` 

The drop-function has not per default a timer, like the boost function. But you can also pass a datetime value to the drop()-function, to set the time, when the temperature should be set back to default.

The importent thing is, that a created scheduler will survice a restart of smarthome, that the temperature will also be set back to default, when your computer reboots.

To achieve this, the plugins stores the unix timestamp of the timers end in a file under base_dir + '/var/rtr/timer/', to restore it at startup.

***The attributes are only valid on the same item, where ``rtr_setpoint`` is defined and belongs to that controller.***

For more info about the functions contine reading.

### Example

The following shows an simple example for a working.

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
                cache: 'On' # this can be importent, or your defined setpoint get lost after restarts
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

        door:
            name: Frontdoor
            open:
                rtr_stops:
                  - '1'
                  - '2'

    room1:
        temp:
            name: Temp
            type: num
            knx_dpt: 9
            knx_send: 4/2/130
            knx_reply: 4/2/130
            ow_addr: 28.52432A030000
            ow_sensor: T
            rtr_current: 2

            set:
                type: num
                visu: 'yes'
                cache: 'On' # this can be importent, or your defined setpoint get lost after restarts
                knx_dpt: 9
                knx_send: 4/3/130
                knx_listen: 4/3/130
                rtr_setpoint: 2

            state:
                type: num
                visu: 'yes'
                knx_dpt: 9
                knx_send: 4/1/130
                knx_listen: 4/1/130
                rtr_actuator: 2

        window:
            name: Window
            open:
                rtr_stops:
                  - '2'
```
