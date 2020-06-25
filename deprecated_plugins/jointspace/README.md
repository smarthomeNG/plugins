# Jointspace

## Supported Hardware

Tested with:
* Philips 37PFL9604H/12

Should work with all Philips TV sets > 2010 (http://jointspace.sourceforge.net)

## Configuration

### plugin.yaml

```yaml
jointspace:
    class_name: Jointspace
    class_path: plugins.jointspace
    host: '<ip>'
    # port = <port>
```

Description of the attributes:

* __host__: IP or hostname of the TV set
* __port__: Port number of Jointspace running on the TV set, default port 1925

### items.yaml example

```yaml
TV:
    type: bool
    visu_acl: rw
    jointspace_cmd: power
    enforce_updates: 'on'

    Mute:
        type: bool
        visu_acl: rw
        jointspace_cmd: mute
        enforce_updates: 'on'

    Volume:
        type: num
        visu_acl: rw
        jointspace_cmd: volume
        enforce_updates: 'on'

    Channel:
        type: str
        jointspace_listen: channel
        enforce_updates: 'on'

    Source:
        type: str
        jointspace_cmd: source
        enforce_updates: 'on'

    Keys:

        Standby:
            type: bool
            visu_acl: rw
            enforce_updates: 'on'
            jointspace_cmd: sendkey Standby

        VolumeUp:
            type: bool
            visu_acl: rw
            enforce_updates: 'on'
            jointspace_cmd: sendkey VolumeUp

        VolumeDown:
            type: bool
            visu_acl: rw
            enforce_updates: 'on'
            jointspace_cmd: sendkey VolumeDown

        ChannelUp:
            type: bool
            visu_acl: rw
            enforce_updates: 'on'
            jointspace_cmd: sendkey ChannelStepUp

        ChannelDown:
            type: bool
            visu_acl: rw
            enforce_updates: 'on'
            jointspace_cmd: sendkey ChannelStepDown

    # etc. list here: http://jointspace.sourceforge.net/projectdata/documentation/jasonApi/1/doc/API-Method-input-key-POST.html'
    Channels:

        ARD:
            type: bool
            visu_acl: rw
            enforce_updates: 'on'
            jointspace_cmd: channel 1

        SUPERRTL:
            type: bool
            visu_acl: rw
            enforce_updates: 'on'
            jointspace_cmd: channel 675
```

### SmartVISU integration

An example to be placed within a SmartVISU html page.

```html
{{ multimedia.station('TV.ARD', 'TV.Channels.ARD','pics/station/tv/das-erste_s.png', 1, 'midi') }}
{{ multimedia.station('TV.ZDF', 'TV.Channels.ZDF','pics/station/tv/zdf_s.png', 1, 'midi') }}

{{ basic.button('MuteTV', 'Tv.Keys.Mute', ' Mute ', 'alert', '', 'midi') }}
{{ basic.button('VolDownTV', 'TV.Keys.VolumeDown', ' Leiser ', 'minus', '', 'midi') }}
```
