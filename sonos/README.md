### Overview

[1. Requirements](#req)

[2. Sonos Speaker UID](#uid)

[3. SmarthomeNG Integration](#sh)

[4. Item Structure](#struc)

[5. Item Description](#desc)

[6. SmartVISU Integration](#visu)

[7. Best Practise](#best)
<p>

### <a name="req"></a>Requirements

* SmarthomeNG v1.3 or newer
* Python3 libraries ```requests``` and ```xmltodict```

To install all necessary libraries for SmarthomeNG, you can run following bash command:
```bash
sudo pip3 install -r /usr/local/smarthome/requirements/all.txt
```
Change the path ```/usr/local/smarthome``` to your SmarthomeNG base directory.

For any questions, bug reports and feature requests, please post to the 
[Sonos-Plugin thread](https://knx-user-forum.de/forum/supportforen/smarthome-py/25151-sonos-anbindung) in the
[KNX-User-Forum](https://knx-user-forum.de/). 

### <a name="uid"></a>Sonos Speaker UID
Before you can start, you have to find all UIDs of your Sonos Speaker in the network. Therefor you can use the
```search_uids.py``` script in the plugin folder. Execute the script on your console via:

```python3 search_uids.py```

The output should be just about like this:
```bash

---------------------------------------------------------
rincon_000f448c3392a01411
        ip           : 192.168.1.100
        speaker name : Wohnzimmer 
        speaker model: Sonos PLAY:1 

---------------------------------------------------------
rincon_c7e91735d19711411
        ip           : 192.168.1.99
        speaker name : Kinderzimmer 
        speaker model: Sonos PLAY:3 
---------------------------------------------------------
```
The first line of each entry is our UID (rincon_xxxxxxxxxxxxxx) we were looking for.

### <a name="sh"></a>Smarthome Integration

Edit the file ```/usr/local/smarthome/etc/plugins.conf``` (might differ) and add the following entry:
```bash
[sonos]
    class_name = Sonos
    class_path = plugins.sonos
    discover_cycle = 120 # can be omitted, default 120 seconds
```
After that you have to create an item configuration file under ```/usr/local/smarthome/items```, e.g. ```sonos.yaml```.
You can use the full-featured example configuration in the example sub folder. Just change the [Sonos UID](#uid) to your
needs.

### <a name="struc"></a>Item Structure 
The first thing to mention is that you don't have to implement all items / functions for a speaker. Choose your
functionality and all the relevant items. To get the Sonos widget working you have at least to implement all items
marked with ```visu``` in the items description below. This list is updated if a new functionality is implemented in the 
widget. 

Every item is described by one or more additional tags in the item description below: ```read```, ```write``` and 
```visu```. These attributes indicates whether an item is readable and/or writeable.    

For a minimal functionality you have to set up an item with the attribute 'sonos_uid' and at least one child item.
Example:
```bash
MyRoom:
    MySonos:
        sonos_uid: rincon_xxxxxxxxxxxxxx
        
        play:
            type: bool
            sonos_recv: play
            sonos_send: play
```

The level of the item with the attribute 'sonos_uid' doesn't matter, the below example is also possible.
Example:
```bash
MyRoom:
    parent:
        child:
        ...
        
        child2:
        ...
        
        child3:
            MySonos:
                sonos_uid: rincon_xxxxxxxxxxxxxx
    
                play:
                  type: bool
                  sonos_recv: play
                  sonos_send: play
```
You can multiple use the same Sonos speaker for your items. The only requirement for a Sonos item is the parent item 
with the sonos uid. 
Example:
```bash
Kitchen:
    child1:
        MySonos:
            sonos_uid: rincon_xxxxxxxxxxxxxx
            
            play:
                type: bool
                sonos_recv: play
                sonos_send: play
        
        child2:
            MySonos2:
            sonos_uid: rincon_xxxxxxxxxxxxxx
            
            play:
                type: bool
                sonos_recv: play
                sonos_send: play
            stop:
                type: bool
                sonos_recv: stop
                sonos_send: stop
```
Last but not least you can rename the item name. This is not recommended due to the fact, that (only) the Sonos widget 
depends on that names (of course you can edit the sonos.html to adapt the widget to your changes).  
Example:
```bash
MyRoom:
    MySonos:
        sonos_uid: rincon_xxxxxxxxxxxxxx
        
        my_awesome_mute_item_name:
            type: bool
            sonos_recv: mute
            sonos_send: mute
```

### <a name="desc"></a>Item Description

---
**bass**
```read``` ```write```
<p>
This item sets the bass level for a speaker. It must be an integer value between -10 and 10. This property is NOT a
group item, nevertheless you can set the child item ```group_command``` to 'True' to set the bass level to all members
of the group. This must be done before setting the bass item to a new value. This item is changed by Sonos events and 
should always be up-to-date.

---
**coordinator**
```read```
<p>
Returns the UID of the coordinator as a string. This is the uid of the current speaker if ```is_coordinator``` is 
'True'. This item is changed by Sonos events and should always be up-to-date.

---
**cross_fade**
```read``` ```write```
<p>
Sets / gets the cross-fade mode for a speaker. 'True' to set cross-fade to 'on' or 'False' for 'off'. This is a group 
command and effects all speakers in the group. This item is changed by Sonos events and should always be up-to-date.

---
**current_track**
```read```
<p>
Returns the current position in the playlist / queue of the played track. This item is changed by Sonos events and 
should always be up-to-date.

---
**current_track_duration**
```read```
<p>
Returns the current duration of track in format HH:mm:ss. This item is changed by Sonos events and should always 
be up-to-date.

---
**current_transport_actions**
```read``` ```visu```
<p>
Returns the possible transport actions for the current track. Possible value are: Set, Stop, Pause, Play, 
X_DLNA_SeekTime, Next, Previous, X_DLNA_SeekTrackNr. This item is changed by Sonos events and should always be 
up-to-date.

---
**current_valid_play_modes**
```read```
<p>
Returns all valid play mode options for the current track. The modes are delivered as string, delimited by a ','.
One of these modes can be passed to the 'play_mode' command. This item is changed by Sonos events and should always be 
up-to-date.
 
---
**dialog_mode**
```read``` ```write```
<p>
Only supported by Sonos Playbar. 
Sets / gets the dialog mode for a Playbar. It must be 'True' to set the dialog mode to 'on' or 'False' for 'off'. 
This item is changed by Sonos events and should always be up-to-date (this must be proofed).

---
**household_id**
```read```
<p>
Returns the household id for the speaker.

---
**is_coordiantor**
```read```
<p>
Bool value that indicates whether the current speaker is the coordinator of the group or not. 'True' if the speaker is 
the coordinator, 'False' if not. This item is changed by Sonos events and should always be up-to-date.

---
**is_initialized**
```read```
<p>
If 'True', this item indicates a fully initialized Sonos speaker. If 'False' the sepaker is either offline or not fully
initialized. Use this item to before starting logics or scenes.

---
**join**
```write```

<p>

Joins a Sonos speaker to an existing group by passing any UID of a speaker that is member of this group. You should use
the additional SmarthomeNG attribute ```enforce_update: True```.

---
**load_sonos_playlist**
```write```
<p>

Loads a Sonos playlist by its name. The item ```sonos_playlists``` shows all available playlists. This is a group 
command can be executed on any speaker of a group.
 
_child item_ ```start_after```:
If you add an child item (type ```bool```) with an attribute ```sonos_attrib = start_after``` you can control the 
behaviour after the playlist was loaded. If you set this item to ```True```, the speaker starts playing
immediately, ```False``` otherwise. (see example item configuration). You can omit this child item, the default
setting is 'False'.

_child item_ ```clear_queue```:
If you add an child item (type ```bool```) with an attribute ```sonos_attrib = clear_queue```, the Sonos queue will be 
cleared before loading the new playlist if you set this item to ```True```, ```False``` otherwise. (see example item 
configuration). You can omit this child item, the default setting is 'False'.

_child item_ ```start_track```:
If you add an child item (type ```num```) with an attribute ```sonos_attrib = start_track```, you can define the track 
to start play from. First item in the queue is 0. You can omit this child item, the default setting is 0.

---
**loudness**
```read``` ```write```
<p>
Sets / gets the loudness for a speaker. It must be 'True' to set loudness to 'on' or 'False' for 'off'. This property
is NOT a group item, nevertheless you can set the child item ```group_command``` to 'True' to set the loudness to all 
members of the group. This must be done before setting the loudness item to a new value. This item is changed by Sonos 
events and should always be up-to-date.

---
**streamtype**
```read``` ```visu```
<p>
Returns the current stream type. Possible values are 'music' (default, e.g. playing a Spotify track), 'radio', 'tv' (if 
the audio output of a Sonos Playbar is set to TV), or 'line-in' (e.g Sonos Play5). This item is changed by Sonos events 
and should always be up-to-date.

---
**mute**
```read``` ```write``` ```visu```
<p>
Mutes or un-mutes a speaker. Must be a bool value. 'True' to mute, 'False' to un-mute the speaker. This is a group 
command and effects all speakers in the group. This item is changed by Sonos events and should always be up-to-date.

---
**next**
```write``` ```visu```
<p>

Go to the next track. 'True' for the next track, all other values have no effects. Be aware that you have to use the
additional SmarthomeNG attribute ```enforce_updates: true``` for this item to make it working. This is a group command 
and effects all speakers in the group. 

---
**night_mode**
```read``` ```write```
<p>
Only supported by Sonos Playbar. 
Sets / gets the night mode for a Playbar. It must be 'True' to set the night mode to 'on' or 'False' for 'off'. 
This item is changed by Sonos events and should always be up-to-date (this must be proofed).

---
**number_of_tracks**
```read```
<p>
Returns the total number of tracks in the queue. This item is changed by Sonos events and should always 
be up-to-date.

---
**pause**
```read``` ```write``` ```visu```
<p>
Pauses the playback. 'True' for pause, 'False' to start the playback. This is a group command and effects all
speakers in the group. This item is changed by Sonos events and should always be up-to-date.

---
**play**
```read``` ```write``` ```visu```
<p>
Start playback. 'True' for play, 'False' to pause the playback. This is a group command and effects all
speakers in the group. This item is changed by Sonos events and should always be up-to-date.

---
**player_name**
```read```
<p>
Returns the speaker name. This item is changed by Sonos events and should always be up-to-date.

---
**play_mode**
```read``` ```write```
<p>
Sets / gets the play mode for a speaker. Allowed values are 'NORMAL', 'REPEAT_ALL', 'SHUFFLE', 'SHUFFLE_NOREPEAT', 
'SHUFFLE_REPEAT_ONE', 'REPEAT_ONE'. This is a group command and effects all speakers in the group. This item is changed 
by Sonos events and should always be up-to-date.

---
**play_tunein**
```write```
<p>
Plays a radio station by a give name. Keep in mind that Sonos searches for an appropiate radio station. If more than one
station was found, the first result will be used. 

_child item_ ```start_after```:
If you add an child item (type ```bool```) with an attribute ```sonos_attrib =start_after``` you can control the behaviour
after the radio station was added to the Sonos speaker. If you set this item to ```True```, the speaker starts playing
immediately, ```False``` otherwise. (see example item configuration). You can omit this child item, the default
setting is 'True'.

---
**play_url**
```write```
<p>
Plays a given url. 

_child item_ ```start_after```:
If you add an child item (type ```bool```) with an attribute ```sonos_attrib =start_after``` you can control the behaviour
after the url was added to the Sonos speaker. If you set this item to ```True```, the speaker starts playing
immediately, ```False``` otherwise. (see example item configuration). You can omit this child item, the default
setting is 'True'.

---
**previous**
```write``` ```visu```
<p>

Go back to the previously played track. 'True' for previously played track, all other values have no effects. Be aware 
that you have to use the additional SmarthomeNG attribute ```enforce_updates: true``` for this item to make it working. 
This is a group command and effects all speakers in the group.

---
**radio_station**
```read``` ```visu```
<p>
Returns the name of the currently played radio station. If no radio broadcast is currently played (see item 
```streamtype```), the item is empty. This item is changed by Sonos events and should always be up-to-date.

---
**radio_show**
```read``` ```visu```
<p>
If available (it dependson the radio station), this item returns the name of the currently played radio show. If no 
radio broadcast is currently played (see item ```streamtype```), this item is always empty. This item is changed by 
Sonos events and should always be up-to-date.

---
**snooze**
```read``` ```write```
<p>
Sets / gets the snooze timer. It must be an integer between 0 - 86399 (in seconds). If this item is set to or is 0, the 
snooze timer is deactivated. This is a group command and effects all speakers in the group. The value is NOT updated in 
real-time. For each speaker discover cycle the item will be updated.
  
---  
**sonos_playlists**
```read``` ```visu```
<p>

Returns a list of Sonos playlists. These playlists can be loaded by the ```load_sonos_playlist``` item. 

---
**status_light**
```read``` ```write```
<p>
Sets / gets the status light indicator of a speaker. 'True' to turn the light on, 'False' to turn it off. The value is 
NOT updated in real-time. For each speaker discover cycle the item will be updated.

---
**stop**
```read``` ```write``` ```visu```
<p>
Stops the playback. 'True' for stop, 'False' to start the playback. This is a group command and effects all
speakers in the group. This item is changed by Sonos events and should always be up-to-date.

---
**stream_content**
```read``` ```visu```
<p>
Returns the content send by a radio station, e.g. the currently played track and artist. If no radio broadcast is 
currently played (see item```streamtype```), the item is empty. This item is changed by Sonos events and should always 
be up-to-date.

---
**switch_line_in**
```write```
<p>
Switches the audio input of a Sonos Play5 (or all other speakers with a line-in) to line-in. 'True' to switch to 
line-in, all other values have no effect.

---
**switch_tv**
```write```
<p>
Switch the playbar speaker's input to TV. 'True' to switch to TV, all other values have no effect. Only supported by 
Sonos Playbar.

---
**track_album**
```read``` ```visu```
<p>
Returns the album title of currently played track. This item is changed by Sonos events and should always be up-to-date.

---
**track_album_art**
```read``` ```visu```
<p>
Returns the album cover url of currently played track. This item is changed by Sonos events and should always be 
up-to-date.

---
**track_artist**
```read``` ```visu```
<p>
Returns the artist of the current track. This item is changed by Sonos events and should always be up-to-date.

---
**track_title**
```read``` ```visu```
<p>
Returns the title of the current track. This item is changed by Sonos events and should always be up-to-date.

---
**track_uri**
```read``` ```visu```
<p>
Returns the uri of currently played track. This item is changed by Sonos events and should always be up-to-date.

---
**treble**
```read``` ```write```
<p>

Sets / gets the treble level for a speaker. It must be an integer value between -10 and 10. This property is NOT a
group item, nevertheless you can set the child item ```group_command``` to 'True' to set the bass level to all members
of the group. This must be done before setting the treble item to a new value. This item is changed by Sonos events and 
should always be up-to-date.

---
**uid**
```read```
<p>

Returns the UID of a Sonos speaker.

---
**unjoin**
```write```
<p>

Unjoins a speaker from a group. 

_child item_ ```start_after```:
If you add an child item (type ```bool```) with an attribute ```sonos_attrib =start_after``` you can control the 
behaviour after the speaker was unjoined from a group.. If you set this item to ```True```, the speaker starts playing
immediately, ```False``` otherwise. (see example item configuration). You can omit this child item, the default
setting is 'False'.

---
**volume**
```read``` ```write``` ```visu```
<p>

Sets / gets the volume level of a speaker. Must be an integer between 0-100. This item is changed by Sonos events and 
should always be up-to-date. It's recommend to set the attribute ```enforce_updates: true```.

_child item_ ```group_command```:
If you add a child item with type of ```bool``` and an attribute ```sonos_attrib: group_command``` the volume will bet
set to all members of the current group.

_child item_ ```max_volume```:
If you add a child item with type of ```num``` and an attribute ```sonos_attrib: max_volume``` the volume can only be 
set to the given ```max_volume``` value. This does not effect the volume set by the Sonos app. If 
```group_command``` was set to ```true``` the ```max_volume``` effects all speakers in the group.   

_child item_ ```volume_dpt3```:
Things get a little bit more complicated when you're trying to increase or decrease the volume level via a knx dpt3 
command. To make it easier and without logics, a child item ```volume_dpt3``` can be added to the volume item:

```bash
volume:
    ...
    ...
    volume_dpt3:
        type: list
        sonos_attrib: vol_dpt3
        sonos_dpt3_step: 2
        sonos_dpt3_time: 1
    
        helper:
            sonos_attrib: dpt3_helper
            type: num
            sonos_send: volume
```
Make sure you also add the shown helper item. You can change the fade steps [```sonos_dpt3_step```] and the time per 
step in seconds ```[sonos_dpt3_time]```. Both values can be omitted. In this case the default values are: 
```sonos_dpt3_step: 2``` and ```sonos_dpt3_step: 1```. The ```group_command``` and ```max_volume``` items will be 
considered.

---
**zone_group_members**
```read```
<p>
Returns a list of all UIDs of the group the speaker is a member in. The list contains always the current speaker. This 
item is changed by Sonos events and should always be up-to-date.

---

### <a name="visu"></a>SmartVISU Integration

The Sonos Plugin fulfills all requirements for an automatic integration in SmartVISU via the **visu_websocket** and
**visu_smartvisu** plugins (for detailed information follow this 
[link](https://github.com/smarthomeNG/smarthome/wiki/Visu_smartvisu_autogen_in_v1.2)). 

#### Sonos widget via plugin
To install / show the Sonos widget via the ```visu_smartvisu``` plugin, you have to [set up the mentioned plugin 
properly](https://github.com/smarthomeNG/plugins/blob/develop/visu_smartvisu/README.md). After that you can define a 
page item like that:
```bash
MyPage:
    name: Sonos
    sv_page: room
    sv_img: audio_audio.svg

    sonos:
      name: Sonos Kitchen
      visu_acl: rw
      sv_blocksize: 1 # optional
      sv_widget: "{{ sonos.player('sonos_kueche', 'MySonos.Kueche') }}"
```
The important entry here is ```{{ sonos.player('sonos_kueche', 'MySonos.Kueche') }}```.  The first value is a 
self-defined unique identifier, the second value is the full path of the Sonos item which you want to control. If you 
have more than one Sonos widget per page, make sure you set an **unique** identifier for each widget.

#### Manual setup
Copy the file ```widget_sonos.html``` from the ```sv_widget``` folder to your smartVISU directory, e.g.
```bash
/var/www/smartvisu/pages/YOUR_PATH_HERE 
```
Change to this directory and append the content of ```widget_sonos.js``` (also located in the sv_widget directory) 
to ```visu.js``` and ```widget_sonos.css``` to ```visu.css```. Create both files if they do not not exist.

Edit your page where you want to display the widget and add the following code snippet:
```bash
{% import "widget_sonos.html" as sonos %}
{% block content %}

<div class="block">
  <div class="set-2" data-role="collapsible-set" data-theme="c" data-content-theme="a" data-mini="true">
    <div data-role="collapsible" data-collapsed="false" >
      {{ sonos.player('sonos_kueche', 'Sonos.Kueche') }}
    </div>
  </div>
</div>

{% endblock %}

```


### <a name="best"></a>Best practise

#### Group commands
As you can see, some of the items have an additional child item "group_command". You can ommit this child item, then 
the default value is always ```False```. If you set the```group_command``` item to ```True``` the value from the parent
item( e.g. ```volume```) will be set to all members of the speaker's group. To get all UIDs of a group you can check the 
the item ```zone_group_members```.

**Important**: Some of the items ​​always act as a group commands. Here is list of all relevant item:
  
```bash
play
pause
stop
mute
cross_fade
snooze
play_mode
next
previous
play_tunein
play_url
load_sonos_playlist
```
For this items you don't have to pay attention to which speaker of the group you have to send the command. This is done 
automatically and affects all speakers of the group.

#### Do not stress the discover functionality
You can define the parameter 'discover_cycle' on plugin start to set the interval how often the plugin searches for 
new and / or offline speakers in the network. Due to the initialization of the speakers and network traffic, it is 
not recommended to set the value less than 60 seconds.

#### Use the "is_initialized" item

It takes some time to discover all Sonos speakers in the network. Use the "is_initialized" item for your logic. If true,
the speaker is fully functional. If this item is 'False' the speaker is not yet initialized or offline.

Example
```bash
if sh.MySonosPlayer.is_initialized():
    do_something()
```
#### "Non-realtime" items
Some properties are not event-driver. That means they are not updated by the Sonos event system. These properties are:

snooze
status_light

These values are updated periodically with each speaker discovery cycle.

#### Yaml or "classical" item configuration
The plugin comes with an example in yaml format. This will be the preferable format for the SamrthomeNG item 
configuration in the future. Feel free to change this example  to the "classical" format. SmarthomeNG is 
backward-compatible.

This example shows a yaml config and the 'classic' pendant: 
```bash
MySonos:
  Kueche:
    sonos_uid: rincon_xxxxxxxxxxxxxx

    is_initialized:
      type: bool
      sonos_recv: is_initialized

    volume:
      type: num
      sonos_recv: volume
      sonos_send: volume

      group_command:
        type: bool
        value: false
        sonos_attrib: group

    play:
      type: bool
      sonos_recv: play
      sonos_send: play
      
      .....
```
becomes 
```bash
[MySonos]
    [[Kueche]]
        sonos_uid = rincon_xxxxxxxxxxxxxx

        [[[is_initialized]]]
            type =bool
            sonos_recv = is_initialized

        [[[volume]]
            type = num
            sonos_recv = volume
            sonos_send = volume
            [[[[group_command]]]]
                type = bool
                value = false
                sonos_attrib = group
    
        [[[play]]]
            type = bool
            sonos_recv = play
            sonos_send = play
      .....
```
#### DPT3 volume example
```bash
 Kueche:
    sonos_uid: rincon_000e58cxxxxxxxxx

    volume:
      type: num
      sonos_recv: volume
      sonos_send: volume
      enforce_updates: true

      group_command:
        type: bool
        value: false
        sonos_attrib: group

      max_volume:
        type: num
        value: -1
        sonos_attrib: max_volume

      volume_dpt3:
        type: list
        sonos_attrib: vol_dpt3
        sonos_dpt3_step: 4
        sonos_dpt3_time: 1
        knx_dpt: 3
        knx_listen: 7/1/0

        helper:
          sonos_attrib: dpt3_helper
          type: num
          sonos_send: volume
```

#### Debug on error
You've any trouble to get the plugin working, start SmarthomeNG in debug mode and post the logfile with the error to
the [**support thread**](https://knx-user-forum.de/forum/supportforen/smarthome-py/25151-sonos-anbindung) in the 
KNX User Forum.