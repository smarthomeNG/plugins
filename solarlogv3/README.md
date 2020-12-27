# Solarlog

This plugin can read a Webpage from SolarLog logging device and return values. 
The skeleton was created by Niko Will in 2013 and converted to a SmartPlugin in 2019 by Bernd Meiners.
The adaption to Firmware > 3.x was done by klab in 2017 and merged with the old plugin in 2020 by Christian Michels

## Requirements

This plugin has no requirements or dependencies but works together with SolarLog and Firmware >= 3.x

## Todo

Show parsed data within webinterface

## Configuration

### plugin.yaml

```
solarlogFw3:
    class_name: SolarLogFw3
    class_path: plugins.solarlogFw3
    host: http://solarlog.fritz.box/
```

#### Attributes

* `host`: specifies the hostname of the SolarLog.
* `cycle`: specifies the cycle for the query of the SolarLog.

### items.yaml
You need to know the format details of the SolarLog to define the valid values for this plugin to work correctly.
All the plugin does is to request the JavaScript files from the device and parse them. 
Almost the same way the webpage does when you visit the URL of your SolarLog in the browser.
A description of the format and the correspondig variables can be found here (german): [https://www.photonensammler.de/wiki/doku.php?id=solarlog_datenformat](https://www.photonensammler.de/wiki/doku.php?id=solarlog_datenformat)

#### solarlog

This is the only attribute for items. To retrieve values from the SolarLog data 
format you just have to use their variable name like on the site which was mentioned above described.

If you want to use values from a array structure like the PDC value from the seconds string on 
the first inverter then you have to use the variable name underscore inverter-1 underscore string-1:

var[_inverter[_string]]

This example should clarify details on how to use:

```yaml
solarlog_v3:

    w_gesamt_zaehler:
        type: num
        cache: 'on'
        solarfw3: 101

    w_gesamt:
        type: num
        cache: 'on'
        solarfw3: 102

    spannung_ac:
        type: num
        cache: 'on'
        solarfw3: 103

    spannung_dc1:
        type: num
        cache: 'on'
        solarfw3: 104

    wh_heute:
        type: num
        solarfw3: 105
        cache: 'on'

    wh_gestern:
        type: num
        cache: 'on'
        solarfw3: 106

    wh_monat:
        type: num
        cache: 'on'
        solarfw3: 107

    wh_jahr:
        type: num
        cache: 'on'
        solarfw3: 108

    wh_gesamt:
        type: num
        cache: 'on'
        solarfw3: 109

    wp_generatorleistung:
        type: num
        cache: 'on'
        solarfw3: 116
```

The ``database: yes`` implies that a database plugin is confgured, too. For display of measurements within a visu graph.

### logic.yaml

Currently there is no logic configuration for this plugin.

## Functions

Currently there are no functions offered from this plugin.
