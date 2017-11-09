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
The port to connect to. This must be Kodi's TCP port not its HTTP port (see [Kodi JSON-RPC API](http://kodi.wiki/?title=JSON-RPC_API)). Default is 9090.

### items.conf (deprecated) / items.yaml
You can register an item to the plugin by adding a field named `kodi_item` augmented with the respective plugin instance you want to register the item to:
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
        volume:
            type: num
            kodi_item@mediacenter: volume
        mute:
            type: bool
            kodi_item@mediacenter: mute
        title:
            type: str
            kodi_item@mediacenter: title
        state:
            type: str
            kodi_item@mediacenter: state
        media:
            type: str
            kodi_item@mediacenter: media
        favorites:
            type: dict
            kodi_item@mediacenter: favorites
        input:
            type: str
            enforce_updates: true
            kodi_item@mediacenter: input
```

#### kodi_item
If an item carries a `kodi_item` it should be of a specific type. Listed below are the types depending on the value that is assigned to `kodi_item`:

##### volume
Item type `num`. Changing the item controls the volume of Kodi. The allowed range is 0 to 100.

##### mute
Item type `bool`. Changing the item controls muting the Kodi player.

##### title
Item type `str`. This item displays information about the currently playing element's title in Kodi. Changing its value has no effect as it is only set by the plugin and not read on updates. 

##### media
Item type `str`. This item displays information about the currently playing element's media type in Kodi. Changing its value has no effect as it is only set by the plugin and not read on updates.

##### state
Item type `str`. This item displays information about the current state of Kodi (Playing, Stopped, Screensaver,...). Changing its value has no effect as it is only set by the plugin and not read on updates.

##### favorites
Item type `dict`. The item stores information about favorites defined in Kodi in a dictionary. Changing its value has no effect as it is only set by the plugin and not read on updates.

##### input
Item type `str`. This item gives complete control over sending inputs to Kodi and can be seen as simulating keyboard events and shotcuts.
If the item is set to an allowed Kodi input action, the respective action is send to Kodi. 
The item should be set to enforce updates in order to allow for sending consecutive commands of the same action.
There is a huge amount of actions possible. Listed below are a number of oft-used input actions this item may be set to. For all allowed actions see the plugin's source code (most of them are pretty self-explanatory).

   * `play` start the current Kodi player
   * `pause` pause the current Kodi player
   * `playpause` toggle the current Kodi player (if paused play, if playing pause)
   * `stop` stop the current Kodi player
   * `osd` show the On Screen Display for the current Kodi player
   * `left` highlight the element left of the current one (same as hitting the left arrow key on a keyboard)
   * `right` highlight the element right of the current one (same as hitting the right arrow key on a keyboard)
   * `up` highlight the element above the current one (same as hitting the up arrow key on a keyboard)
   * `down` highlight the element above the current one (same as hitting the down arrow key on a keyboard)
   * `select` select the currently highlighted element
   * `contextmenu` show the context menu for the currently highlighted element
   * `home` go to the home menu
   * `back` go to the previous menu
   * `volumeup` increase the volume
   * `volumedown` decrease the volume

### logic.conf

Nothing so far

## Functions
This plugin provides the function to send notification messages to Kodi.

```python
sh.living.kodi.notify('Door', 'Ding Dong')
```
