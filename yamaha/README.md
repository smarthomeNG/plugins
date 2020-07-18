# Yamaha

Plugin to control Yamaha RX-V and RX-S receivers, e.g.: Power On / Off, select input, set volume and mute.

## Notes
This plugin is still under development, but for the author in daily use. 
There the plugin is used to switch on the Yamaha RX-S600 and RX-V475 series and to change the input.
Depending on the input the volume is also adapted which works fine for the author but mute is not used in his logics.

The plugin makes use of the Yamaha Network Control (YNC) which is an XML format protocol.
Event notifications are received over UDP Multicast (SSDP) if the device sends them out.
To receive the notifications the Yamaha device needs to share the same subnet as the SmartHomeNG host.

Currently only the main zone is supported.

## Supported devices

All RX-V4xx, RX-V5xx, RX-V6xx, RX-V7xx and RX-Sxxx series share the same API, so they should be ok with this plugin.

RXS-602D is also tested and basically it works, except for the notifications which are not broadcasted at all.
Since this device also supports MusicCast, alternatively the Yamahaxyc plugin might be used.

After installation of the plugin it might be that no event notifications over multicast are received.
To enable event notifications it is needed to power on the device at least once using SmartHomeNG.

## Requirements

The following python packages are part of requirements.txt and will be installed upon start with SmartHomeNG Version 1.7 and later.

- lxml

They can also be installed by ``pip3 install -r requirements.txt --user`` from within the ``plugins/yamaha`` directory.

## Installation

### plugin.yaml

```yaml
yamaha:
    class_name: Yamaha
    class_path: plugins.yamaha
```

### items.yaml

```yaml
livingroom:

    yamaha:
        yamaha_host: 192.168.178.186

        power:
            type: bool
            yamaha_cmd: power
            enforce_updates: 'True'

        volume:
            type: num
            yamaha_cmd: volume
            enforce_updates: 'True'

        mute:
            type: bool
            yamaha_cmd: mute
            enforce_updates: 'True'

        input:
            type: str
            yamaha_cmd: input
            enforce_updates: 'True'
```

Attention: A top level item name will interfere with plugin names.
