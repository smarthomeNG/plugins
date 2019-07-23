.. index:: Plugins; kodi
.. index:: kodi

kodi
####

Konfiguration
=============

.. important::

    Die Informationen zur Konfiguration des Plugins sind unter :doc:`/plugins_doc/config/kodi` beschrieben.

.. code-block:: yaml

    # etc/plugin.yaml
    kodi:
        plugin_name: kodi
        host: 10.0.0.1
        #instance: kodi_one
        #autoreconnect: False
        #connect_retries: 10
        #connect_cycle: 5
        #send_retries: 5

Items
=====

kodi_item@[Instanz]: [Funktion]
-------------------------------
Folgende Funktionen werden aktuell unterstützt:
**on_off**
Item Type `bool`. If the item is set to `False`, a shutdown request is send to Kodi. If the item is set to `True`, the plugin tries to establish a connection to Kodi (this does not include Wake on LAN or anything else).

##### volume
Item type `num`. Changing the item controls the volume of Kodi. The allowed range is 0 to 100.

##### mute
Item type `bool`. Changing the item controls muting the Kodi player.

##### mute
Item type `num`. Set to 0 to query the current player id. Will also get updated automatically as soon as a player is active.

##### title
Item type `str`. This item displays information about the currently playing element's title in Kodi. Changing its value has no effect as it is only set by the plugin and not read on updates.

##### media
Item type `str`. This item displays information about the currently playing element's media type in Kodi. Changing its value has no effect as it is only set by the plugin and not read on updates.

##### macro
Item type `str`. Currently you can use the values "resume" and "beginning". If a movie has been played for a while and stopped, Kodi won't let you just play the movie. You have to choose if you want to start from the beginning or if you want to resume at the last playback position. There might be other macros coming. They are basically just a sequence of commands.

##### state
Item type `str`. This item displays information about the current state of Kodi (Playing, Stopped, Screensaver,...). Changing its value has no effect as it is only set by the plugin and not read on updates.

##### favorites
Item type `dict`. The item stores information about favorites defined in Kodi in a dictionary. Changing its value has no effect as it is only set by the plugin and not read on updates.

##### input
Item type `str`. This item gives complete control over sending inputs to Kodi and can be seen as simulating keyboard events and shortcuts.
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



Struct Vorlagen
===============

Ab smarthomeNG 1.6 können Vorlagen aus dem Plugin einfach eingebunden werden. Dabei stehen folgende Vorlagen zur Verfügung:

- general: Display, Menü, Cursorssteuerung, Statusupdate, Neuladen der Konfiguration, etc.
- speaker_selection: Zur Auswahl von Speaker A, B oder beide
- individual_volume: Zur Einstellung der Lautstärke für jeden einzelnen Lautsprecher
- sound_settings: Listening Mode, Bass und Höhen, dynamische Kompression, etc.
- video_settings: Aspect Ratio, Monitorout, etc.
- zone1, zone2, zone3: Sämtliche für die Zonen relevante Features wie Quelle, Lautstärke, etc.

Die Vorlagen beinhalten möglicherweise zu viele Items bzw. Items, die vom Gerät nicht unterstützt werden. Wenn aber kein entsprechendes Kommando im models/model.txt File hinterlegt ist, werden die betroffenen Items einfach ignoriert. Also kein Problem!
