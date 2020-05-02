# MPD

## Requirements

You only need one or more Music Player Daemons (MPD).
For more information about MPD and it's commands see http://www.musicpd.org/doc/protocol/command_reference.html

## Configuration

### plugin.yaml

```yaml
mpd_bath:
    class_name: MPD
    class_path: plugins.mpd
    instance: bathroom
    host: 192.168.177.164
    port: 6601
#    cycle: 2

mpd_kitchen:
    class_name: MPD
    class_path: plugins.mpd
    instance: kitchen
    host: 192.168.177.164
    port: 6602
#    cycle: 2
```

#### instance
This attribute is mandatory. You have to provide an unique identifier for every instance.

#### host
This attribute is mandatory. You have to provide the IP adress or the hostname of the MPD.

#### port
You can specify a port to connect to. If not defined port 6600 will be used.

#### cycle
You can specify the update interval. If not defined cycle will be set to 2.


###Command groups and commands
```
There are 7 groups of commands tat can be used. Here's an overview of the available groups and their commands and datatypes

mpd_status
    Implements commands that are used to query MPD's status.

    playpause        # bool, 0 or 1, 1 while music is played, also used as mpd_command
    mute             # bool, 0 or 1, 1 when volume is set to 0%, also used as mpd_command
    volume           # num,  0-100 or -1 if the volume cannot be determined, also used as mpd_command
    repeat           # bool, 0 or 1, also used as mpd_command
    random           # bool, 0 or 1, also used as mpd_command
    single           # bool, 0 or 1, also used as mpd_command
    consume          # bool, 0 or 1, also used as mpd_command
    playlist         # num,  31-bit unsigned integer, the playlist version number
    playlistlength   # num,  integer, the length of the playlist
    mixrampdb        # num,  mixramp threshold in dB
    state            # str,  play, stop, or pause
    song             # num,  playlist song number of the current song stopped on or playing
    songid           # num,  playlist songid of the current song stopped on or playing
    time             # str,  total time elapsed (of current playing/paused song)
    elapsed          # str,  Total time elapsed within the current song, but with higher resolution
    bitrate          # num,  instantaneous bitrate in kbps
    audio            # str,  The format emitted by the decoder plugin during playback, format: "samplerate:bits:channels"
    nextsong         # num,  playlist song number of the next song to be played
    nextsongid       # num,  playlist songid of the next song to be played
    duration         # num,  Duration of the current song in seconds
    xfade            # num,  crossfade in seconds
    mixrampdelay     # num,  mixrampdelay in seconds
    updating_db      # str,  job id
    error            # str,  errormessage of MPD

mpd_songinfo
    Implements commands that are used to query information about the current playing song.

    file             # str,  path of the current playing file
    Last-Modified    # str,  Date of last modification of the song
    Artist           # str,  Artist of the current playing song
    Album            # str,  Album of the current playing song
    Title            # str,  Title of the current playing song
    Track            # str,  Track# of the current playing song
    Time             # str,  length of the current song
    Pos              # str,  position of the song in the playlist
    Id               # str,  Id of the song

mpd_statistic
    Implements commands that are used to query MPD's statistics.

    artists          # num,  number of artists
    albums           # num,  number of albums
    songs            # num,  number of songs
    uptime           # num,  daemon uptime in seconds
    db_playtime      # num,  sum of all song times in the db
    db_update        # num,  last db update in UNIX time
    playtime         # num,  time length of music played

mpd_command
    Implements commands that are used to control the playback.

    playpause        # bool, 0 or 1, 1 to play music, also used as mpd_status
    mute             # bool, 0 or 1, 1 to set the volume to 0%, also used as mpd_status
    volume           # num,  0-100 to set the volume, also used as mpd_status
    repeat           # bool, 0 or 1, also used as mpd_status
    random           # bool, 0 or 1, also used as mpd_status
    single           # bool, Toggles single state. When single is activated, playback is stopped after current
                     #       song, or song is repeated if the 'repeat' mode is enabled, also used as mpd_status
    consume          # bool, Sets consume state to STATE, STATE should be 0 or 1. When consume is activated,
                     #       each song played is removed from playlist, also used as mpd_status

    next             # bool, Plays next song in the playlist
    pause            # bool, Toggles pause/resumes playing, PAUSE is 0 or 1
    play             # num,  Begins playing the playlist at song number <value>
    playid           # num,  Begins playing the playlist at song <value>
    previous         # bool, Plays previous song in the playlist
    seek             # str,  Seeks to the position TIME (in seconds; fractions allowed)
                     #       of entry SONGPOS in the playlist format: "SONGPOS TIME"
    seekid           # str,  Seeks to the position TIME (in seconds; fractions allowed) of song SONGID
                     #       format: "SONGID TIME"
    seekcur          # str,  Seeks to the position TIME (in seconds; fractions allowed) within the current song
                     #       If prefixed by '+' or '-', then the time is relative to the current playing position
    stop             # bool, Stops playing
    crossfade        # num,  Sets crossfading between songs
    mixrampdb        # num,  Sets the threshold at which songs will be overlapped. Like crossfading but doesn't
                     #       fade the track volume, just overlaps
    mixrampdelay     # num,  Additional time subtracted from the overlap calculated by mixrampdb
    setvol           # num,  Sets volume to VOL, the range of volume is 0-100
    replay_gain_mode # str,  ets the replay gain mode. One of off, track, album, auto

mpd_url
    Parses the defined url and tries to play the stream.

mpd_localplaylist
    Searches for a local playlist with the defined filename and plays it if found.

mpd_rawcommand
    Takes whatever you assign to it and sends it directly to MPD.

mpd_database
    Implements commands that are used to control the database.

    update           # str,  Updates the music database: find new files, remove deleted files,
                     #       update modified files. <value> is a particular directory or song/file to update
                     #       If you do not specify it, everything is updated
    rescan           # str,  Same as update, but also rescans unmodified files
```

For some items it is useful to combine the status and the matching command in one item, e.g. playpause, mute, volume,
repeat, random, consume,...
See the items.yaml for examples.


###items.yaml

1st example shows all items

```yaml
EG:
    BATHROMM:
        MUSIC:
            volume:
                type: num
                mpd_status@bathroom: volume
                mpd_command@bathroom: setvol
                enforce_updates: true

            repeat:
                type: bool
                mpd_status@bathroom: repeat
                mpd_command@bathroom: repeat
                enforce_updates: true

            playpause:
                type: bool
                mpd_status@bathroom: playpause
                mpd_command@bathroom: playpause
                enforce_updates: true

            mute:
                type: bool
                mpd_status@bathroom: mute
                mpd_command@bathroom: mute
                enforce_updates: true

            random:
                type: bool
                mpd_status@bathroom: random
                mpd_command@bathroom: random
                enforce_updates: true

            single:
                type: bool
                mpd_status@bathroom: single
                mpd_command@bathroom: single
                enforce_updates: true

            consume:
                type: bool
                mpd_status@bathroom: consume
                mpd_command@bathroom: consume
                enforce_updates: true

            playlist:
                type: num
                mpd_status@bathroom: playlist

            playlistlength:
                type: num
                mpd_status@bathroom: playlistlength

            state:
                type: str
                mpd_status@bathroom: state

            song:
                type: num
                mpd_status@bathroom: song

            songid:
                type: num
                mpd_status@bathroom: songid

            nextsongid:
                type: num
                mpd_status@bathroom: nextsongid

            time:
                type: str
                mpd_status@bathroom: time

            elapsed:
                type: str
                mpd_status@bathroom: elapsed

            duration:
                type: num
                mpd_status@bathroom: duration

            bitrate:
                type: num
                mpd_status@bathroom: bitrate

            xfade:
                type: num
                mpd_status@bathroom: xfade
                mpd_command@bathroom: crossfade
                enforce_updates: true

            mixrampdb:
                type: num
                mpd_status@bathroom: mixrampdb
                mpd_command@bathroom: mixrampdb
                enforce_updates: true

            mixrampdelay:
                type: num
                mpd_status@bathroom: mixrampdelay
                mpd_command@bathroom: mixrampdelay
                enforce_updates: true

            audio:
                type: str
                mpd_status@bathroom: audio

            updating_db:
                type: str
                mpd_status@bathroom: updating_db

            error:
                type: str
                mpd_status@bathroom: error

            file:
                type: str
                mpd_songinfo@bathroom: file

            Last-Modified:
                type: str
                mpd_songinfo@bathroom: Last-Modified

            Artist:
                type: str
                mpd_songinfo@bathroom: Artist

            Album:
                type: str
                mpd_songinfo@bathroom: Album

            Title:
                type: str
                mpd_songinfo@bathroom: Title

            Name:
                type: str
                mpd_songinfo@bathroom: Name

            Track:
                type: str
                mpd_songinfo@bathroom: Track

            Time:
                type: str
                mpd_songinfo@bathroom: Time

            Pos:
                type: str
                mpd_songinfo@bathroom: Pos

            Id:
                type: str
                mpd_songinfo@bathroom: Id

            artists:
                type: num
                mpd_statistic@bathroom: artists

            albums:
                type: num
                mpd_statistic@bathroom: albums

            songs:
                type: num
                mpd_statistic@bathroom: songs

            uptime:
                type: num
                mpd_statistic@bathroom: uptime

            db_playtime:
                type: num
                mpd_statistic@bathroom: db_playtime

            db_update:
                type: num
                mpd_statistic@bathroom: db_update

            playtime:
                type: num
                mpd_statistic@bathroom: playtime

            next:
                type: bool
                mpd_command@bathroom: next
                enforce_updates: true

            pause :
                type: bool
                mpd_command@bathroom: pause
                enforce_updates: true

            play :
                type: num
                mpd_command@bathroom: play
                enforce_updates: true

            playid :
                type: num
                mpd_command@bathroom: playid
                enforce_updates: true

            previous :
                type: bool
                mpd_command@bathroom: previous
                enforce_updates: true

            seek :
                type: str
                mpd_command@bathroom: seek
                enforce_updates: true

            seekid :
                type: str
                mpd_command@bathroom: seekid
                enforce_updates: true

            seekcur :
                type: str
                mpd_command@bathroom: seekcur
                enforce_updates: true

            stop :
                type: bool
                mpd_command@bathroom: stop
                enforce_updates: true

            rawcommand :
                type: str
                mpd_rawcommand@bathroom: rawcommand
                enforce_updates: true

            radio1 :
                type: bool
                mpd_url@bathroom: "http://streamurlofradio1.de/"
                enforce_updates: true

            radio2 :
                type: bool
                mpd_url@bathroom: "http://streamurlofradio2.de/"
                enforce_updates: true

            plradio1 :
                type: bool
                mpd_localplaylist@bathroom: plradio1
                enforce_updates: true

            plradio2 :
                type: bool
                mpd_localplaylist@bathroom: plradio2
                enforce_updates: true

            playlist1 :
                type: bool
                mpd_localplaylist@bathroom: playlist1
                enforce_updates: true

            playlist2 :
                type: bool
                mpd_localplaylist@bathroom: playlist2
                enforce_updates: true

            updatedatabase:
                type: str
                mpd_database@bathroom: update
                enforce_updates: true

            rescandatabase:
                type: str
                mpd_database@bathroom: rescan
                enforce_updates: true
```

2nd example shows only items that are used in smartVISU

```yaml
EG:
    KITCHEN:
        MUSIC:
            volume:
                type: num
                mpd_status@kitchen: volume
                mpd_command@kitchen: setvol
                enforce_updates: true

            repeat:
                type: bool
                mpd_status@kitchen: repeat
                mpd_command@kitchen: repeat
                enforce_updates: true

            playpause:
                type: bool
                mpd_status@kitchen: playpause
                mpd_command@kitchen: playpause
                enforce_updates: true

            mute:
                type: bool
                mpd_status@kitchen: mute
                mpd_command@kitchen: mute
                enforce_updates: true

            random:
                type: bool
                mpd_status@kitchen: random
                mpd_command@kitchen: random
                enforce_updates: true

            state:
                type: str
                mpd_status@kitchen: state

            Artist:
                type: str
                mpd_songinfo@kitchen: Artist

            Album:
                type: str
                mpd_songinfo@kitchen: Album

            Title:
                type: str
                mpd_songinfo@kitchen: Title

            Name:
                type: str
                mpd_songinfo@kitchen: Name

            Track:
                type: str
                mpd_songinfo@kitchen: Track

            next:
                type: bool
                mpd_command@kitchen: next
                enforce_updates: true

            previous :
                type: bool
                mpd_command@kitchen: previous
                enforce_updates: true

            stop :
                type: bool
                mpd_command@kitchen: stop
                enforce_updates: true
```
