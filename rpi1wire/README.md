# Raspberry Pi 1-Wire plugin

# Requirements

This plugin has been developed for the Raspberry Pi. It allows easy access to 1-Wire - sensors.
We tested the plugin with the Raspberry Pi B and the temperature sensor DS18B20.

## Supported Hardware

Tested width:
Raspberry Pi Model B
1-Wire - Sensor DS18B20

# Configuration

## Raspberry Pi

   see also: http://www.kompf.de/weather/pionewiremini.html

### /boot/config.txt
<pre>
   # activating 1-wire without pullup (3-wire-Version)
   dtoverlay=w1-gpio,gpiopin=4,pullup=off
</pre>
### /etc/modules

<pre>
   #(3-wire-Version)
   w1-gpio pullup=0  
   w1-therm
</pre>

# Smarthome

## plugin.conf

<pre>
[rpi1wire]
   class_name = Rpi1Wire
   class_path = plugins.rpi1wire
#   dirname = "/sys/bus/w1/devices"
#   cycle = 120
</pre>

## plugin.yaml

<pre>
rpi1wire:
   class_name: Rpi1Wire
   class_path: plugins.rpi1wire
#   dirname: "/sys/bus/w1/devices"
#   cycle: 120
</pre>

dirname
<pre>
   is the path where the Raspberry provides the values of the 1-wire - sensors
   default "/sys/bus/w1/devices"
</pre>
cycle
<pre>
   is the period in which the values are updated
   default 120 seconds
</pre>   


## items
# .conf

<pre>
   [rpi1wire]
       [[sensor_list]]
           name = Sensor-List
           type = str
           visu_acl = ro
       [[sensors]]
          name = Sensors
          type = num
          visu_acl = ro
</pre>

# .yaml

<pre>
   rpi1wire:
       sensor_list:
           name: Sensor-List
           type: str
           visu_acl: ro
       sensors:
          name: Sensors
          type: num
          visu_acl: ro
</pre>
sh.rpi1wire.sensor_list()
<pre>
   - contains a list of all found sensors
</pre>
sh.rpi1wire.sensors()
<pre>
   - contains the number of sensors found
</pre>
### rpi1wire_name
<pre>   
   The name of the 1-wire - sensor
    - rpi1wire_name or rpi1wire_id are possible
</pre>   
### rpi1wire_id
<pre>   
   The id of the 1-wire - sensor
    - rpi1wire_name or rpi1wire_id are possible
</pre>   
### rpi1wire_update
<pre>   
   If you trigger this item, the sensors are re-searched without restart the server
</pre>   

### Example


<pre>
# items/my.conf

[someroom]
    [[mytemperature]]
        name = my Name
        type = num
        visu_acl = ro
        rpi1wire_name = rpi_temp1
        sqlite = yes

#or

[someroom]
    [[mytemperature]]
        name = my Name
        name = Wohnzimme Raumtemperatur
        type = num
        visu_acl = ro
        rpi1wire_id = 28-0215018970ff
        sqlite = yes

[rpi1wire]
    [[update]]
        name = Update Sensor-List
        type = bool
        visu_acl = rw
        rpi1wire_update = 1

</pre>
# or in YAML
<pre>
# items/my.yaml

someroom:
     mytemperature:
        name: my Name
        type: num
        visu_acl: ro
        rpi1wire_name: rpi_temp1
        sqlite: yes

#or

someroom:
     mytemperature:
        name: my Name
        name: Wohnzimme Raumtemperatur
        type: num
        visu_acl: ro
        rpi1wire_id: 28-0215018970ff
        sqlite: yes

rpi1wire:
     update:
        name: Update Sensor-List
        type: bool
        visu_acl: rw
        rpi1wire_update: 1

</pre>
