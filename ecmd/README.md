# ECMD

# Requirements

The ECMD plugin connects to an AVR microcontroller board with ethersex firmware via network. The ECMD protocoll provides access to attached 1wire temperature sensors DS1820.

## Supported Hardware

* 8-bit AVR microcontroller boards with network support, like NetIO (Pollin), Etherrape (lochraster.org), etc.
* 1-wire temperature and other sensors 
* - DS1820 (Temperatursensor)
* - DS18B20 (Temperatursensor)
* - DS1822 (Temperatursensor)
* - DS2502 (EEPROM)
* - DS2450 (4 Kanal ADC)

# Configuration

## plugin.conf

You can specify the host ip of your ethersex device.

<pre>
[ecmd]
    class_name = ECMD
    class_path = plugins.ecmd
    host = 10.10.10.10
#   port = 2701
</pre>

This plugin needs an host attribute and you could specify a port attribute which differs from the default '1010'.

## items.conf

The item needs to define the 1-wire address of the sensor.

### ecmd1wire_addr 

ecmd1wire_addr = 10f01929020800dc
type = num


### Example

Please provide an item configuration with every attribute and usefull settings.

<pre>
# items/my.conf

[someroom]
    [[temperature]]
        name = Raumtemperatur
        ecmd1wire_addr = 10f01929020800dc
        type = num
        sqlite = yes
        history = yes
        visu = yes
        sv_widget = "{{ basic.float('item', 'item', '°') }}" , "{{ plot.period('item-plot', 'item') }}"
</pre>

