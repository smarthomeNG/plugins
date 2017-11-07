# Kodi

## Requirements

You only need one or more Kodi (12 a.k.a. Frodo or above) with
System-Settings-Service "Allow programs on other systems to control Kodi" enabled.

## Configuration

### plugin.conf (deprecated) / plugin.yaml

```
# /etc/plugin.conf
[kodi]
    class_name = Kodi
    class_path = plugins.kodi
    instance = living
    host = xxx.xxx.xxx.xxx
    port = 9090
```

```yaml
# /etc/plugin.yaml
kodi:
    class_name: Kodi
    class_path: plugins.kodi
    instance: mediacenter
    host: xxx.xxx.xxx.xxx
    port: 9090
```

#### host
This attribute is mandatory. You have to provide the IP address of the Kodi system.

#### port
You could specify a port to connect to. By default port 9090 is used.

### items.conf (deprecated) / items.yaml

```
# /items/items.conf
[living]
    [[kodi]]
        type = str
        kodi_item@mediacenter = state
        [[[title]]]
            type = str
            kodi_item@mediacenter = title
        [[[media]]]
            type = str
            kodi_item@mediacenter = media
        [[[volume]]]
            type = num
            kodi_item@mediacenter = volume
        [[[mute]]]
            type = bool
            kodi_item@mediacenter = mute
```

```yaml
# /items/items.yaml
living:
    kodi:
        type: str
        kodi_item@mediacenter: state        
        volume:
            type: num
            kodi_item@mediacenter: volume
        mute:
            type: bool
            kodi_item@mediacenter: mute
        title:
            type: str
            kodi_item@mediacenter: title
        media:
            type: str
            kodi_item@mediacenter: media
        favorites:
            type: dict
            kodi_item@mediacenter: favorites
```

#### kodi_item
You could assign the following values to `kodi_item`:

   * `volume` a numeric value (0 -100)
   * `mute` a bool flag
   * `title` a string with the name of the movie, song or picture
   * `media` a string with the current media type (Video, Audio, Picture)
   * `state` current state as string (Menu, Playing, Pause)
   * `favorites` the favorites of your Kodi system (must be of type dict)

The `volume` and `mute` items influence Kodi when their value changes.

### logic.conf

Nothing so far

## Functions
=========
This plugin provides the function to send notification messages to Kodi.

```python
sh.living.kodi.notify('Door', 'Ding Dong')
```
