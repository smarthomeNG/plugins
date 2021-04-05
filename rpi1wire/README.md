# Raspberry Pi 1-Wire plugin

# Requirements

This plugin has been developed for the Raspberry Pi. It allows easy access to 1-Wire - sensors.
We tested the plugin with the Raspberry Pi B and the temperature sensor DS18B20.


### Supported Hardware

Tested with:
Raspberry Pi Model B, 
Raspberry Pi 2B, 
Raspberry Pi 3B, 
1-Wire - Sensor DS18B20

## Configuration

### Raspberry Pi

See also: http://www.kompf.de/weather/pionewiremini.html

Adjustment of ``/boot/config.txt`` according to 2- or 3-wire cabling:

If the onewire devices are actively driven and thus use the 3-wire version

```
# activating 1-wire without pullup (3-wire-Version)
dtoverlay=w1-gpio,gpiopin=4,pullup=off
```

```
# activating 1-wire with pullup (2-wire-Version)
dtoverlay=w1-gpio,gpiopin=4,pullup=on
```

Adjustment of ``/etc/modules`` according to 2- or 3-wire cabling:

```
#(3-wire-Version)
w1-gpio pullup=0  
w1-therm
```

```
#(2-wire-Version)
w1-gpio pullup=1
w1-therm
```

# SmarthomeNG

## plugin.yaml

```yaml
rpi1wire:
   class_name: Rpi1Wire
   class_path: plugins.rpi1wire
#   dirname: "/sys/bus/w1/devices"
#   cycle: 120
```

* ``dirname`` is the path where the Raspberry provides the values of the 1-wire - sensors
  default "/sys/bus/w1/devices"

* ``cycle`` is the period in which the values are updated
   default is 120 seconds

## Items

```yaml
someitem:
    somelist:
        rpi1wire_sys: list
        name: Sensor-List
        type: str
        visu_acl: ro
    somecount:
        rpi1wire_sys: count
        name: Sensors
        type: num
        visu_acl: ro
    someupdate:
        rpi1wire: update
        name: Update Sensors
        type: bool
        inital_value: 0
        visu_acl: rw
```

``rpi1wire_sys: list`` - contains a list of all found sensors
``rpi1wire_sys: count`` - contains the number of sensors found
``rpi1wire_sys: update`` - Item for searching sensors and update list and count

### rpi1wire_id  or  rpi1wire_name

The id or name of the 1-wire - sensor. Both attributes serve the same purpose.
The Item having one of these attributes will receive the temperature measurement.
The Item thus needs to be of type num.

### rpi1wire_sys: update

If this item is triggered, the sensors are re-searched without restarting the server

### logic.yaml
Please refer to the documentation generated from plugin.yaml metadata.


## Examples

### Example 1

```yaml
someroom:
     mytemperature:
        name: my Name
        type: num
        visu_acl: ro
        rpi1wire_name: rpi_temp1
        database: yes
```

### Example 2

```yaml
someroom:
     mytemperature:
        name: my Name
        name: Wohnzimmer Raumtemperatur
        type: num
        visu_acl: ro
        rpi1wire_id: 28-0215018970ff
        database: yes

rpi1wire:
     update:
        name: Update Sensor-List
        type: bool
        rpi1wire_sys: update
        visu_acl: rw
        initial_value: 0
    sensor_list:
        rpi1wire_sys: list
        name: Sensor List
        type: str
        visu_acl: ro
    sensor_count:
        rpi1wire_sys: count
        name: Sensor Count
        type: num
        visu_acl: ro
```


## Web Interfaces

A Big ToDo here: 
- List found sensors
- List Items affected with rpi1wire_id or rpi1wire_name
- Show Items with rpi1wire_update

