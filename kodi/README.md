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
    instance = mediacenter
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
The port to connect to. This must be Kodi's TCP port not its HTTP port (see [Kodi JSON-RPC API](http://kodi.wiki/?title=JSON-RPC_API)]. Default is 9090.

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
...
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
        # input commands
        left:
            type: bool
            enforce_updates: true
            kodi_item@mediacenter: left
        right:
            type: bool
            enforce_updates: true
            kodi_item@mediacenter: right
        up:
            type: bool
            enforce_updates: true
            kodi_item@mediacenter: up
        down:
            type: bool
            enforce_updates: true
            kodi_item@mediacenter: down
        home:
            type: bool
            enforce_updates: true
            kodi_item@mediacenter: home
        back:
            type: bool
            enforce_updates: true
            kodi_item@mediacenter: back
        select:
            type: bool
            enforce_updates: true
            kodi_item@mediacenter: select
        play_pause:
            type: bool
            enforce_updates: true
            kodi_item@mediacenter: play_pause
        stop:
            type: bool
            enforce_updates: true
            kodi_item@mediacenter: stop
```

#### kodi_item
You could assign the following values to `kodi_item`:

   * `volume` a numeric value (0 -100)
   * `mute` a bool flag
   * `title` a string with the name of the movie, song or picture
   * `media` a string with the current media type (Video, Audio, Picture)
   * `state` current state as string (Menu, Playing, Pause)
   * `favorites` the favorites of your Kodi system (must be of type dict)
   * `play_pause` request Kodi to pause or restart the current players (should be of type bool and `enforce_updates: true`)
   * `stop` request Kodi to stop all players (should be of type bool and `enforce_updates: true`)
   * `left` send a left request to Kodi, same as pressing the left arrow on the keyboard (should be of type bool and `enforce_updates: true`)
   * `right` send a right request to Kodi, same as pressing the right arrow on the keyboard (should be of type bool and `enforce_updates: true`)
   * `up` send an up request to Kodi, same as pressing the up arrow on the keyboard (should be of type bool and `enforce_updates: true`)
   * `down` send a down request to Kodi, same as pressing the down arrow on the keyboard (should be of type bool and `enforce_updates: true`)
   * `home` go to the home menu (should be of type bool and `enforce_updates: true`)
   * `back` go to the previous menu (should be of type bool and `enforce_updates: true`)
   * `select` select the currently highlightes item in Kodi (should be of type bool and `enforce_updates: true`)

The `volume` and `mute` items influence Kodi when their value changes.
All items that are marked as "should be of type bool" are essentially input commands which are usually send to Kodi over an attached keyboard. The keyboard behavior can be simulated through boolean items with `enforce_updates: true`.


### logic.conf

Nothing so far

## Functions
This plugin provides the function to send notification messages to Kodi.

```python
sh.living.kodi.notify('Door', 'Ding Dong')
```
