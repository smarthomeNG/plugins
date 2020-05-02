# YamahaYXC

Plugin to control Yamaha MusicCast-enabled devices (receivers, networked speakers), e.g.: Power On / Off, select input, set volume and mute, playback/pause, get current playing status

The base material for the plugin and the documentation was shamelessly copied from Raoul Thill, author of the yamaha plugin for older Yamaha receivers in sh.py


## Notes
This plugin is still under development, but in daily use by myself: displaying current device and playback status as well as controlling power, playback and volume. Currently tested devices are WX-010, ISX-18D, RX-V483.
The plugin makes use of the Yamaha Extended Control (YXC) API, which is based on JSON formatted data.
The plugin subscribes to active devices to get notifications of changed. These are received over UDP. The plugin should handle multiple network interfaces to connect to different devices (no errors so far, but not enough devices to actually test, yet) 

Items can be called to your own liking; they are identified by the plugin by the respective yamahayxc_cmd item property. Command/status items can _NOT_ be nested below the device item, all items accessed by the plugin need to be on the same level directly below the device id. (sorry)

The 'update' item has no own function. Writing to this item triggers a pull of all information. Not needed if push notifications work. Used by me for testing and before the notification code was written. Ignore as you like.

Feel free to comment and to file issues.
At the moment only the main zone and the netusb player are supported. Support for multiple zones should be possible on request. For other players supply test equipment :)

Starting with sh.py release v1.7 item structs are available for basic media players and for devices with additional alarm clock functions.


## Requirements

The following python packages need to be installed on your system:

- requests

Those packages can be installed using:

```bash
# Debian based
sudo apt-get install python3-requests

# Arch Linux
sudo pacman -S python-requests

# Fedora
sudo dnf install python3-requests
```

## Installation

```bash
cd smarthome.py directory
cd plugins
git clone https://github.com/Morg42/yamahayxc.git
```

### plugin.conf (deprecated) / plugin.yaml
```
[yamahayxc]
    class_name = YamahaYXC
    class_path = plugins.yamahayxc
```

```yaml
yamahayxc:
    class_name: YamahaYXC
    class_path: plugins.yamahayxc
```

### items.yaml

```yaml
media:
    
    wx010:
        struct: yamahayxc.basic

        yamahayxc_host: 192.168.2.211
```

or without structs (results in identical item tree):

```yaml
media:

    wx010:
        yamahayxc_host: 192.168.2.211
        yamahayxc_zone: main

# writable items to control device/playback
        # True = power on, False = standby
        power:
            type: bool
            yamahayxc_cmd: power
            enforce_updates: 'True'

        # numeric volume. Range is 0..60 on my devices. May vary
        volume:
            type: num
            yamahayxc_cmd: volume
            enforce_updates: 'True'

        # True = mute enable, False = mute disable
        mute:
            type: bool
            yamahayxc_cmd: mute
            enforce_updates: 'True'

        # input source as string. Heavily dependent on device.
        input:
            type: str
            yamahayxc_cmd: input
            enforce_updates: 'True'

        # possible values are 'play', 'stop', 'pause', 'previous', 'next'...
        playback:
            type: str
            yamahayxc_cmd: playback
            enforce_updates: 'True'
            
        # values are numeric and can (as of now) not be queried by the plugin
        preset:
            type: num
            yamahayxc_cmd: preset
            enforce_updates: 'True'

        # values are numeric and can be 0 / 30 / 60 / 90 / 120 [minutes]
        sleep:
            type: num
            yamahayxc_cmd: sleep
            enforce_updates: 'True'
            
# read-only items to monitor device/playback status
        # name of current track, if available
        track:
            type: str
            yamahayxc_cmd: track

        # name of current artist, if available. Radio station name for net_radio
        artist:
            type: str
            yamahayxc_cmd: artist

        # this is the URL of current album art image, if supported / supplied
        # it is hosted on the respective yamaha device
        albumart:
            type: str
            yamahayxc_cmd: albumart

        # current time of playback in percent of total_time
        # -1 if total_time is not available
        play_pos:
            type: num
            yamahayxc_cmd: play_time

        # total time of playback in seconds. 0 if not applicable / available
        totaltime:
            type: num
            yamahayxc_cmd: total_time

# write-only item to pass arbitrary command. Use at own discretion
        passthru:
            type: str
            yamahayxc_cmd: passthru
            enforce_updates: 'True'

# write-only item to force update of all items above. See notes.
         update:
            type: bool
            yamahayxc_cmd: state
            enforce_updates: 'True'



# the following items are only valid for devices with alarm clock functions
# these are included in addition to the others from the 'alarm' struct:

        # enable / disable alarm function
        alarm_on:
            type: bool
            yamahayxc_cmd: alarm_on
            enforce_updates: 'True'

        # enable / disable alarm beep (solo or in addition to music)
        alarm_beep:
            type: bool
            yamahayxc_cmd: alarm_beep
            enforce_updates: 'True'

        # get/set alarm time. Formatted as 4 digit 24 hour string
        alarm_time:
            type: str
            yamahayxc_cmd: alarm_time
            enforce_updates: 'True'

```

### Example CLI usage

```
> up media.wx010.power=True
> up media.wx010.input=net_radio
> up media.wx010.volume=15
> up media.wx010.mute=True
> up media.wx010.mute=False
> up media.wx010.playback=play
> up media.wx010.power=False
> up media.wx010.passthru='v1/Main/setPower?power=off'
> up media.wx010.alarm_time='1430'
```

Note: I cheated. The wx-010 doesn't have alarm functions...