# DMX

## Requirements

This plugin needs one of the supported DMX interfaces:

   * [NanoDMX](http://www.dmx4all.de/)
   * [DMXking](http://www.dmxking.com) it should work with other Enttec Pro compatible as well.

and pyserial.

```
apt-get install python-serial
```

## Configuration

### plugin.conf

```
[dmx]
   class_name = DMX
   class_path = plugins.dmx
   tty = /dev/usbtty...
#  interface = nanodmx
```

With ``interface``  you could choose between ``nanodmx`` and ``enttec``. By default nanodmx is used.

You have to adapt the tty to your local enviroment. In my case it's ``/dev/usbtty-1-2.4`` because I have the following udev rule:

``` 
# /etc/udev/rules.d/80-smarthome.rules
SUBSYSTEMS=="usb",KERNEL=="ttyACM*",ATTRS{product}=="NanoDMX Interface",SYMLINK+="usbtty-%b"
```

### items.conf

#### dmx_ch

With this attribute you could specify one or more DMX channels.

### Example
```
[living_room]
    [[dimlight]]
        type = num
        dmx_ch = 10 | 11
```

Now you could simply use:
``sh.living_room.dimlight(80)`` to dim the living room light.

## Functions

### send(channel, value)

Sends the value to the given dmx channel. The value could be ``0`` to ``255``.

Example: ``sh.dmx.send(12, 255)``
