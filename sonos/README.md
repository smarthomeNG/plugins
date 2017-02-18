This sub-project is a client implementation for the Sonos Broker. It is a plugin for the 
SmarthomeNG framework (https://github.com/smarthomeNG).

##Release

v1.0    (2017-02-18)
    
    -- Attention: only compatible with SmarthomeNG
    -- SmartPlugin functionality added
    -- dpt3 functionality added for volume item
    -- command 'transport_actions' added
    -- command 'nightmode' added 
    -- play_tts: attribute 'force_stream_mode' (re)-added
    -- added attribute 'play' to 'unjoin'
        -- resumes the last played track / radio before join to another group
    -- added missing 'track_album' property
    -- add new property 'playlist_total_tracks'
    -- attribute 'is_coordiantor' in example has now the right value
    -- version string updated
    -- change expected Sonos Broker version to v1.0

## Overview

[1. Requirements](#req)

[2. Integration in SmarthomeNG](#shng)

[3. Volume DPT3 support](#dpt)

[4. Group behavior](#group)

[5. Methods](#meth)

[6. SmartVISU Integration](#visu)

[7. FAQ](#faq)


##<a name="req"></a>Requirements:

  Sonos Broker v1.0
  (https://github.com/pfischi/shSonos)

  SmarthomeNG 1.3 
  (https://github.com/smarthomeNG/smarthome)


##<a name="shng"></a>Integration in SmarthomeNG

Go to /usr/smarthome/etc and edit plugins.conf and add ths entry:

    [sonos]
      class_name = Sonos
      class_path = plugins.sonos
      #broker_url = 192.168.178.31:12900        #optional
      #refresh = 120                            #optional
      
You dont't have to set the ***broker_url*** variable. If value is not set, the current system ip and the default 
broker port (12900) will be assumed. Add this this parameter manually, if the sonos broker is not running on 
the same system.
The ***refresh*** parameter specifies, how often the broker is requested for sonos status updates (default: 120s).
Normally, all changes to the speakers will be triggered automatically to the plugin.

Go to /usr/smarthome/items. Create a file named sonos.conf or copy the sonos.conf from the examples folder.
  
Edit file with this sample of mine:
  
    [Kinderzimmer]
        sonos_uid = rincon_100e88c3772e01500

        [[mute]]
            type = bool
            enforce_updates = True
            visu_acl = rw
            sonos_recv = mute
            sonos_send = mute
    
            [[[group_command]]]
                type = bool
                value = 0
    
        [[led]]
            type = bool
            enforce_updates = True
            visu_acl = rw
            sonos_recv = led
            sonos_send = led
    
            [[[group_command]]]
                type = bool
                value = 0
    
        [[volume]]
            type = num
            sonos_recv = volume
            sonos_send = volume
    
            [[[group_command]]]
                type = bool
                value = 0
    
            [[[volume_dpt3]]]
                type = list
                sonos_volume_dpt3 = foo
                sonos_vol_step = 2
                sonos_vol_time = 1
        
                [[[[helper]]]]
                    type = num
                    sonos_send = volume
                
        [[max_volume]]
            type = num
            enforce_updates = True
            visu_acl = rw
            sonos_recv = max_volume
            sonos_send = max_volume
    
            [[[group_command]]]
                type = bool
                value = 0
    
        [[stop]]
            type = bool
            enforce_updates = True
            visu_acl = rw
            sonos_recv = stop
            sonos_send = stop
    
        [[play]]
            type = bool
            enforce_updates = True
            visu_acl = rw
            sonos_recv = play
            sonos_send = play
    
        [[seek]]
            type = str
            enforce_updates = True
            visu_acl = rw
            sonos_send = seek    #use HH:mm:ss
    
        [[pause]]
            type = bool
            enforce_updates = True
            visu_acl = rw
            sonos_recv = pause
            sonos_send = pause
    
        [[next]]
            type = foo
            enforce_updates = True
            sonos_send = next
            visu_acl = rw
    
        [[previous]]
            type = foo
            enforce_updates = True
            sonos_send = previous
            visu_acl = rw
    
        [[track_title]]
            type = str
            sonos_recv = track_title
        
        [[track_album]]
            type = str
            sonos_recv = track_album
    
        [[track_duration]]
            type = str
            sonos_recv = track_duration
            visu_acl = rw
    
        [[track_position]]
            type = str
            sonos_recv = track_position
            visu_acl = rw
    
        [[track_artist]]
            type = str
            sonos_recv = track_artist
    
        [[track_uri]]
            type = str
            sonos_recv = track_uri
            visu_acl = rw
    
        [[track_album_art]]
            type = str
            sonos_recv = track_album_art
    
        [[playlist_position]]
            type = num
            sonos_recv = playlist_position
            visu_acl = rw

        [[playlist_total_tracks]]
            type = num
            sonos_recv = playlist_total_tracks
    
        [[streamtype]]
            type = str
            sonos_recv = streamtype
            visu_acl = rw
    
        [[play_uri]]
            type = str
            enforce_updates = True
            sonos_send = play_uri
    
        [[play_tunein]]
            # 'play_tunein' expects a radio station name
            # The name will be searched within TuneIn and the first match is played.
            # To make sure the correct radio station is played provide the full radio station 
            # showing in the Sonos app.
            type = str
            enforce_updates = True
            sonos_send = play_tunein
            
        [[play_snippet]]
            type = str
            enforce_updates = True
            sonos_send = play_snippet
    
            [[[volume]]]
                type = num
                value = -1
    
            [[[group_command]]]
                type = bool
                value = 0
    
        [[play_tts]]
            type = str
            enforce_updates = True
            sonos_send = play_tts
            visu_acl = rw
    
            [[[volume]]]
                type = num
                value = -1
    
            [[[language]]]
                type = str
                value = 'de'
    
            [[[group_command]]]
                type = bool
                value = 0
            
            [[[force_stream_mode]]]
                type = bool
                value = 0
    
        [[radio_show]]
            type = str
            sonos_recv = radio_show
            visu_acl = rw
    
        [[radio_station]]
            type = str
            sonos_recv = radio_station
            visu_acl = rw
    
        [[uid]]
            type = str
            sonos_recv = uid
            visu_acl = rw
    
        [[ip]]
            type = str
            sonos_recv = ip
            visu_acl = rw
    
        [[model]]
            type = str
            sonos_recv = model
            visu_acl = rw

        [[model_number]]
            type = str
            sonos_recv = model_number
            visu_acl = rw
    
        [[display_version]]
            type = str
            sonos_recv = display_version
            visu_acl = rw
    
        [[household_id]]
            type = str
            sonos_recv = household_id
            visu_acl = rw
    
        [[zone_name]]
            type = str
            sonos_recv = zone_name
            visu_acl = rw
    
        [[zone_icon]]
            type = str
            sonos_recv = zone_icon
            visu_acl = rw
    
        [[serial_number]]
            type = str
            sonos_recv = serial_number
            visu_acl = rw
    
        [[software_version]]
            type = str
            sonos_recv = software_version
            visu_acl = rw
    
        [[hardware_version]]
            type = str
            sonos_recv = hardware_version
            visu_acl = rw
    
        [[mac_address]]
            type = str
            sonos_recv = mac_address
            visu_acl = rw
    
        [[status]]
            type = bool
            sonos_recv = status
            visu_acl = rw
    
        [[join]]
            type = str
            enforce_updates = True
            sonos_send = join
            visu_acl = rw
    
        [[unjoin]]
            type = foo
            enforce_updates = True
            sonos_send = unjoin
            visu_acl = rw
            
            [[[play]]]
                type = bool
                value = 1
    
        [[partymode]]
            type = foo
            enforce_updates = True
            sonos_send = partymode
            visu_acl = rw
    
        [[volume_up]]
            type = foo
            enforce_updates = True
            visu_acl = rw
            sonos_send = volume_up
    
            [[[group_command]]]
                type = bool
                value = 0
    
        [[volume_down]]
            type = foo
            enforce_updates = True
            visu_acl = rw
            sonos_send = volume_down
    
            [[[group_command]]]
                type = bool
                value = 0
    
        [[additional_zone_members]]
            type = str
            visu_acl = rw
            sonos_recv = additional_zone_members
    
        [[bass]]
            type = num
            visu_acl = rw
            sonos_recv = bass
            sonos_send = bass
    
            [[[group_command]]]
                type = bool
                value = 0
    
        [[treble]]
            type = num
            visu_acl = rw
            sonos_recv = treble
            sonos_send = treble
    
            [[[group_command]]]
                type = bool
                value = 0
    
        [[loudness]]
            type = bool
            visu_acl = rw
            sonos_recv = loudness
            sonos_send = loudness
    
            [[[group_command]]]
                type = bool
                value = 0
        
        [[nightmode]]
            type = bool
            enforce_updates = True
            visu_acl = rw
            sonos_recv = nightmode
            sonos_send = nightmode
        
        [[playmode]]
            type = str
            enforce_updates = True
            visu_acl = rw
            sonos_recv = playmode
            sonos_send = playmode
    
        [[alarms]]
            type = dict
            enforce_updates = True
            visu_acl = rw
            sonos_recv = alarms
            sonos_send = alarms
        
        [[is_coordinator]]
            type = bool
            sonos_recv = is_coordinator

        [[tts_local_mode]]
            type = bool
            sonos_recv = tts_local_mode
        
        [[sonos_playlists]]
            type = str  
            sonos_send = sonos_playlists
            enforce_updates = True

        [[load_sonos_playlist]]
            type = str
            sonos_send = load_sonos_playlist
            enforce_updates = True

            [[[play_after_insert]]]
                type = bool
                value = 1
            
            [[[clear_queue]]]
                type = bool
                value = 1
        
        [[balance]]
            type = num
            visu_acl = rw
            sonos_recv = balance
            sonos_send = balance
            
            [[[group_command]]]
                type = bool
                value = 0
        
        [[wifi_state]]
            type = bool
            visu_acl = rw
            sonos_recv = wifi_state
            sonos_send = wifi_state

            [[[persistent]]]
                type = bool
                value = 0
            
        [[clear_queue]]    
            type = bool
            enforce_updates = True
            sonos_send = clear_queue
         
        [[transport_actions]]
            type = str
            sonos_recv = transport_actions
    
        
        
 This sonos.conf file implements most of the commands to interact with the Sonos Broker. Please follow the detailed
 description under the [command section in the Broker manual](../README.md#available-commands).

 You can find an example config in the plugin sub-directory "examples". 


 To get your sonos speaker id, type this command in your browser (while sonos server is running):
  
    http://<sonos_server_ip:port>/client/list

##<a name="dpt">Volume DPT3 support

If you take look at the ```volume``` item in your Sonos items configuration you should find something like this:
```
[[volume]]
    type = num
    sonos_recv = volume
    sonos_send = volume

    [[[group_command]]]
        type = bool
        value = 0

    [[[volume_dpt3]]]
        type = list
        sonos_volume_dpt3 = foo
        sonos_vol_step = 2
        sonos_vol_time = 1

        [[[[helper]]]]
            type = num
            sonos_send = volume
```
If you want to use a dim-like functionality to control the volume (e.g. with a button), you can edit the 
```volume_dpt3``` item. ***sonos_vol_step*** (default: 2) defines the volume step for up and down, ***sonos_vol_time*** 
(default: 1) the time between the steps. Both values are optional, if not set, the default value is used. A real-world
example could look like this:
```
[[[volume_dpt3]]]
    type = list
    knx_dpt = 3
    knx_listen = 7/0/0
    sonos_volume_dpt3 = foo
    sonos_vol_step = 2
    sonos_vol_time = 1
 
    [[[[helper]]]]
        type = num
        sonos_send = volume
```
Don't change the items name, otherwise the function will not work.

##<a name="group"></a>Group behaviour

 If two or more speakers are in the same zone, most of the commands are automatically executed for all zone
 members. Normally the Sonos API requires to send the command to the zone master. This is done by the Broker
 automatically. You don't have to worry about which speaker is the zone master. Just send your command to one 
 of the zone member speaker. 

##### These commands will always act as group commands:

    stop
    play
    seek
    pause
    next
    previous
    play_uri
    play_tunein
    play_snippet ('group_command' parameter only affects the snippet volume)
    play_tts ('group_command' parameter only affects the snippet volume)
    partymode
    playmode
    set_playlist

###### These commands only act as group commands if the parameter 'group_command' is set to 1:

    mute
    led
    volume
    max_volume
    volume_up
    volume_down
    join
    unjoin
    bass
    treble
    loudness
    balance

##<a name="meth"></a>Methods

get_favorite_radiostations(<start_item>, <max_items>)

    Get all favorite radio stations from sonos library

    start_item [optional]: item to start, starting with 0 (default: 0)
    max_items [optional]: maximum items to fetch. (default: 50)

    Parameter max_items can only be used, if start_item is set (positional argument)

    It's a good idea to check to see if the total number of favorites is greater than the amount of
    requested ('max_items'), if it is, use `start` to page through and  get the entire list of favorites.

    Response:

    JSON object, utf-8 encoded

    Example:

    {
        "favorites":
        [
            { "title": "Radio TEDDY", "uri": "x-sonosapi-stream:s80044?sid=254&flags=32" },
            { "title": "radioeins vom rbb 95.8 (Pop)", "uri": "x-sonosapi-stream:s25111?sid=254&flags=32" }
        ],
            "returned": 2,
            "total": "10"
    }

    call this function with:
    sh.sonos.get_favorite_radiostations()
    
version()

    current plugin version
    
    call this function with:
    sh.sonos.version()

refresh_media_library(<display_option>)
    
    Refreshs the media library
    For parameter 'display_option' see 
    <a href="http://www.sonos.com/support/help/3.4/en/sonos_user_guide/Chap07_new/Compilation_albums.htm">Sonos Help Page</<a>
    
    call this function with:
    
    sh.sonos.refresh_media_library()

discover()

    Performs a manual scan for Sonos speaker in the network.
    
    call this function with:
    sh.sonos.discover()


##<a name="visu"></a>smartVISU Integration

More information [--> HERE <--](https://github.com/pfischi/shSonos/tree/develop/widget.smartvisu)

##<a name="faq"></a>FAQ

##### utf-8 codec error
If you're using Onkelandy's SmarthomeNG Image (and other Linux distros), following error can occurred if you're using 
non-ASCII characters for Sonos speaker names:
```
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xb0 in position 37: invalid start byte
```
This happens because the 'stdout' setting of the system is set to an ASCII character set. You can this by entering 
following command in your console:
```
export LC_ALL=de_DE.utf8
export LANGUAGE=de_DE.utf8
```
For more information about 'locales', please follow this [--> LINK <--](https://www.thomas-krenn.com/de/wiki/Locales_unter_Ubuntu_konfigurieren)