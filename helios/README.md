# Helios ECx00Pro / Vallox xx SE Plugin

Detailed documentation can be found on the Wiki:
https://github.com/Tom-Bom-badil/helios/wiki


## Plugin installation in short:

All files go to ``smarthome/plugins/helios``. Then do the following:

```
files/helios.conf         copy file to smarthome/items/helios.conf
files/helios_logics.py    copy file to smarthome/logics/helios.conf
```

Add the following lines to ``smarthome/etc/plugin.conf``:

```
[helios]
    class_name = helios
    class_path = plugins.helios
    tty = /dev/ttyUSB0    # put your serial port here (usually /dev/ttyUSB0 or /dev/ttyAMA0)
    cycle = 60            # update interval in seconds; ex-default: 300
```

Add the following lines to smarthome/etc/logic.conf:

```
[fanspeed_uzsu_logic]
    filename = helios_logics.py
    watch_item = ventilation.fanspeed.fanspeed_uzsu

[booster_logic]
    filename = helios_logics.py 
    watch_item = ventilation.booster_mode.logics.switch 
```

At next you should update the settings in the first section of ``smarthome/items/helios.conf`` in order to get correct values.

Restart, plugin should be running by now (check items in backend plugin).

Troubleshooting options on github (see above).

## Widget for SmartVisu

Copy all files from ``sv_widgets`` to ``smartVISU/widgets``. Then add following 2 lines to your HTML:

```html
{% import "helios.html" as helios %}
{{ helios.show_widget('EC300Pro', true, 'Kontrollierte Wohnraumlüftung') }}
```

Widget options:
```html
{{ helios.show_widget(id, use_uzsu, title) }}
id          unique id
use_uzsu    display UZSU icon true / false
title       optional title on top
```

Enjoy! :)
