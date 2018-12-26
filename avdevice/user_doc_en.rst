.. index:: Plugins; avdevice
.. index:: avdevice

avdevice
########

Configuration
=============

.. important::

You can find the configuration information at :doc:`/plugins_doc/config/avdevice`.

.. code-block:: yaml

    # etc/plugin.yaml
    avdevice:
        class_name: AVDevice
        class_path: plugins.avdevice
        model: sc-lx86
        #instance: pioneer_one
        tcp_ip: 10.0.0.130
        #tcp_port: 23
        #tcp_timeout: 1
        rs232_port: /dev/ttyUSB1
        #rs232_baudrate: 9600
        #rs232_timeout: 0.1
        #ignoreresponse: 'RGB,RGC,RGD,GBH,GHH,VTA,AUA,AUB'
        #forcebuffer: 'GEH01020, GEH04022, GEH05024'
        #inputignoredisplay: ''
        #dependson_item: ''
        #dependson_value: True
        #errorresponse: E02, E04, E06
        #resetonerror: False
        #depend0_power0: False
        #depend0_volume0: False
        #sendretries: 10
        #resendwait: 1.0
        #reconnectretries: 13
        #reconnectcycle: 10
        #secondstokeep: 50
        #responsebuffer: 5
        #autoreconnect: false
        #update_exclude: ''

Items
=====

avdevice_zone[0-4]@[instance]: [function]
----------------------------------------

Specifiy the zone number and instance. If you don’t use zones you can
either use ``avdevice`` or ``avdevice_zone0`` as attributes.

The command has to correspond to a command in the relevant text
configuration file in the avdevice plugin folder named the same as the
``model`` configured in plugin.yaml. It is important to set the correct
type for each item. The Pioneer RS232 codeset expects bool and int types
only. For example to set the listening mode to "pure direct", the item
has to be int and you set it to the value "8". If you want to use the
``translation-feature`` you should set the item to ``foo``. This feature is
explained later.

Full item examples are included as separate yaml files for Pioneer and
Denon devices. The examples include the tested items/commands and
allow easy copy/paste.

Special attribute values (statusupdate and reload) are described at :doc:`/plugins_doc/config/avdevice`.


avdevice_zone[0-4]_speakers@[instance]: [function]
-------------------------------------------------

Specifiy the zone number and instance. This attribute is used to switch between
Speaker A, B and AB layout. Speakers Items are special and
should be set up the way mentioned in the following example. 1 and 2
correspond to the value the speaker command expects (for example for
Pioneer receivers < 2016).

.. code-block:: yaml

    # items/my.yaml
    Pioneer:
        type: foo

        Speakers:
            type: num
            visu_acl: rw
            avdevice_zone1: speakers

        SpeakerA:
            type: bool
            visu_acl: rw
            avdevice_zone1_speakers: 1

        SpeakerB:
            type: bool
            visu_acl: rw
            avdevice_zone1_speakers: 2


avdevice_zone[0-4]_depend@[instance]: [function]
-----------------------------------------------

Specifiy the zone number and instance. The depend attribute lets you
specifiy for each item if it depends on another item/function. If you
define such a dependency several things will happen:

- The item only gets updated/changed if the dependency is fullfilled

- Query command of the item will get removed from the queue if the dependency is not
fullfilled

- Query command of the item will (only) get added if one of
the master items gets changed and the dependency is fullfilled.

- After connecting to the device the query command of an item only gets
added if you add ``init`` to the dependency configuration.

You can use multiple depend items and attributes even for different
zones. You can even define ``and/or`` for the dependencies by adding up to
four different groups (a, b, c, d) after the value seperated by a comma
``,``.

You can not only define a ``master item`` but also a ``master value`` and
several standard python comparison operators.

If you don’t set an operator and value, ``==`` and ``True`` is assumed. If
you don’t set a group, group ``a`` is assumed. This means, if you add
several dependent function without a group, the functions will get
evaluated as ``or`` and dependency is fullfilled as soon as one of the
functions/items corresponds to the given value.

The example below shows the following dependencies:

- The disctype will always be queried after connecting to the device (as long as you have
specified a query command in the command-file)

- Audio language and encoding will be queried after connecting to the device or as so
on as
the item with the ``play`` function (Oppo.Play) is True
- The track will get updated/queried if these dependencies are fullfilled: (play is True
or status is play) AND verbose is set to 2 AND audiotype is either PCM
or PCM 44.1/16

- The trackname will get updated/queried if these
dependencies are fullfilled: (play is True or status is play) AND
verbose is set to 2 AND audiotype is either PCM or PCM 44.1/16 AND
disctpye is one of these three values: DVD-AUDIO, CDDA, DATA-DISC

.. code-block:: yaml

    # items/my.yaml
    Oppo:
        type: foo

        Power:
          visu_acl: rw
          type: bool
          avdevice@oppo: power

        Verbose:
          visu_acl: rw
          type: num
          cache: 'false'
          enforce_updates: 'yes'
          avdevice@oppo: verbose

        Status:
          visu_acl: rw
          type: str
          cache: 'False'
          enforce_updates: 'yes'
          avdevice@oppo: status
          on_change:
              - ..Pause = True if value == 'PAUSE' else False
              - ..Stop = True if not (value == 'PLAY' or value == 'PAUSE' or value == 'INVALID') else False
              - ..Play = True if value == 'PLAY' else False

        Play:
          visu_acl: rw
          type: bool
          enforce_updates: 'yes'
          avdevice@oppo: play

        Disctype:
          visu_acl: rw
          type: str
          cache: 'False'
          enforce_updates: 'yes'
          avdevice@oppo: disctype
          avdevice_depend@oppo: init

        Audio:
          type: foo

          Language:
            visu_acl: rw
            type: str
            cache: 'False'
            enforce_updates: 'yes'
            avdevice@oppo: audiolanguage
            avdevice_depend@oppo:
              - play
              - init

          Encoding:
            visu_acl: rw
            type: str
            cache: 'False'
            enforce_updates: 'yes'
            avdevice@oppo: audiotype
            avdevice_depend@oppo:
              - play
              - init

        Track:
          visu_acl: rw
          type: num
          cache: 'False'
          enforce_updates: 'yes'
          avdevice@oppo: audiotrack
          avdevice_depend@oppo:
              - play = True, a
              - status = PLAY, a
              - verbose = 2, b
              - audiotype = PCM, c
              - audiotype = PCM 44.1/16, c

        Trackname:
          visu_acl: rw
          type: str
          avdevice@oppo: trackname
          avdevice_depend@oppo:
            - disctype = DVD-AUDIO, a
            - disctype = CDDA, a
            - disctype = DATA-DISC, a
            - play = True, b
            - status = PLAY, b
            - audiotype = PCM, c
            - audiotype = PCM 44.1/16, c
            - verbose = 2, d

avdevice_zone[0-4]_init@[instance]: [function]
---------------------------------------------

Specifiy the zone number and instance.
The init attribute lets you set a specific command to a specific value as soon as the device is connected. For example if you want to always set the verbose level to 2 as soon as the plugin connects to it (at startup and after turning on the power socket or reconnecting the cable) you can define an additional item with the attribute "avdevice_init". The value of that item (Oppo.Verbose.Init) gets appended to the command linked to the verbose item (Oppo.Verbose).

You can use multiple init items and attributes even for different zones.

.. code-block:: yaml

    # items/my.yaml
    Oppo:
        type: foo
        Verbose:
          type: bool
          visu_acl: rw
          avdevice_zone1: verbose

          Init:
              visu_acl: rw
              type: bool
              cache: 'true'
              value: 2
              avdevice_zone1_init: verbose

    Pioneer:
        type: foo

        Zone1:
            type: foo

            Mute:
              type: bool
              visu_acl: rw
              avdevice_zone1: mute

              Init:
                  visu_acl: rw
                  type: bool
                  cache: 'true'
                  value: True
                  avdevice_zone1_init: mute

        Zone2:
            type: foo

            Mute:
              type: bool
              visu_acl: rw
              avdevice_zone2: mute

              Init:
                  visu_acl: rw
                  type: bool
                  cache: 'true'
                  value: True
                  avdevice_zone2_init: mute


Commands
========

Configure your commands depending on your model and manufacturer. You
have to name the file the same as configured in the plugin.yaml as
“model”. E.g. if you’ve configured ``model: vsx-923`` you name the file
``vsx-923.txt``

Each line holds one specific command that should be sent to the device.
You also specify the zone, the query command, response command, etc. You
can comment out lines by placing a ``#`` in front of the line. You can also
comment a whole block by using ``’’’`` at the beginning and end of a block.

-  ``zone``: Number of zone. Has to correspond to the attribute in
   item.yaml. E.g. for zone 1 use “avdevice_zone1: command”. Zone 0
   holds special commands like navigating in the menu, display reponse,
   information about currently playing songs, etc.

-  ``function``: name of the function. You can name it whatever you
   like. You reference this value in the item using avdevice_zoneX:
   function.

-  ``functiontype``: for boolean functions use “on” or “off”. For
   commands setting a specific value like source, input mode, volume,
   etc. use “set”. To increase or decrease a value use the corresponding
   “increase” or “decrease”. For everything else leave empty!

-  ``send``: the command to be sent, e.g. power off is “PF” for Pioneer
   receivers. You can use a pipe “\|” if more than one command should be
   sent. Add an integer or float to specify a pause in seconds between
   the commands, like “PO\|2\|PO”. That might be necessary for power on
   commands via RS232, e.g. for Pioneer receivers to power on “PO|PO”
   forces the plugin to send the “PO” command twice. Use stars “\*” to
   specify the format of the value to be sent. Let’s say your device
   expects the value for volume as 3 digits, a “\*\*\*VL” ensures that
   even setting the volume to “5” sends the command as “005VL”

-  ``query``: Query command. This is usually useful after setting up the
   connection or turning on the power. This command gets also used if
   the plugin doesn’t receive the correct answer after sending a
   command. It is recommended to leave this value empty for all
   functions except on, off and set.

-  ``response``: The expected response after sending a command. Use
   “none” if you don’t want to wait for the correct response. Use “\*” the same way
   as with the send command. You can even specify multiple response
   possibilities separated by “\|”.

-  ``readwrite``: R for read only, W for write only, RW for Read and
   Write. E.g. display values are read only whereas turning the volume
   up might be a write operation only. Setting this correctly ensures a
   fast and reliable plugin operation

-  ``invertresponse``: some devices are stupid enough to reply with a
   “0” for “on” and “1” for “off”. E.g. a Pioneer receiver responds with
   “PWR0” if the device is turned on. Configure with “yes” if your
   device is quite stupid, too.

-  ``minvalue``: You can define the minimum value for setting a specific
   function. This might be most relevant for setting the volume or
   bass/trebble values. If you configure this with “-3” and set the bass
   to “-5” (via Visu or CLI) the value will get clamped by the plugin
   and set to “-3”.

-  ``maxvalue``: You can define the maximum value for setting a specific
   function. This might be most relevant for setting the volume. If you
   configure this with “100” and set the volume to “240” (via Visu or
   CLI) the value will get clamped by the plugin and set to “100”.

-  ``responsetype``: Defines the type of the response value and can be
   set to “bool”, “num” or “str” or a mixture of them (separated by a
   pipe “\|” or comma “,”). Most response types are set automatically on
   startup but you can force a specific type using this value. It is
   recommended to use the values suggested in the txt files that come
   with the plugin.

-  ``translationfile``: If you want to translate a specific value/code
   to something else, define the name of a txt file in the translation folder
   here that holds the information on how to translate which value. This feature
   is described later in more detail.

.. code-block:: none

   # plugins/avdevice/pioneer.txt
   ZONE; FUNCTION; FUNCTIONTYPE; SEND; QUERY; RESPONSE; READWRITE; INVERTRESPONSE; MINVALUE; MAXVALUE; RESPONSETYPE; TRANSLATIONFILE
   1; power; on; PO|PO; ?P; PWR*; RW; yes
   1; power; off; PF; ?P; PWR*; RW; yes
   1; volume+; increase; VU; ; VOL; W
   1; volume-; decrease; VD; ; VOL; W
   1; volume; set; ***VL; ?V; VOL***; RW; ; 80; 185
   1; input; set; **FN; ?F; FN**; RW
   1; speakers; set; *SPK; ?SPK; SPK*; RW
   '''
   #commented out from here
   2; power; on; APO|APO; ?AP; APR*; RW; yes
   2; power; off; APF; ?AP; APR*; RW; yes
   0; title; ; ; ; GEH01020; R
   0; station; ; ; ; GEH04022; R
   0; genre; ; ; ; GEH05024; R
   #commented out until here
   '''
   0; display; ; ?FL; ?FL; FL******************************; R
   1; input; set; **FN; ?F; FN**; RW; ; ; ; ; pioneer_input
   1; mode; set; ****SR; ?S; SR****; RW; ; ; ; num; pioneer_SR
   1; playingmode; ; ?L; ?L; LM****; R; ; ; ; str,int; pioneer_LM
   #0; test; ; ; ; noidea; R (commented out)


Translations
============

You could create a file called denon_volume.txt and link it
in your model.txt file to convert 3 digit volume to a float. Denon
receivers handle e.g. 50.5 as 505. If you want to use value limits or
visualize the volume correctly in your VISU you should use the following
translation file:

.. code-block:: none

   # plugins/avdevice/denon_volume.txt
   CODE; TRANSLATION
   ***; **.*

Pioneer receivers use numbers to define input source or listening mode
what is very cryptic and not very user friendly. Therefore you should
use the relevant files in the plugins folder like pioneer_input. That
file looks something like this:

.. code-block:: none

   # plugins/avdevice/pioneer_input.txt
   CODE; TRANSLATION
   00; PHONO
   01; CD
   02; TUNER

Now, when the plugin receives FN01 as a response, the response gets
converted to “CD”. Vice versa you can even update your item to “CD” and
the plugin will send “01FN” as a command. It is advised to define the
according item as ``type: foo`` so you can either use a number or string,
just the way you like.


Wildcards
=========

For the model.txt file you can use question marks as a wild card if the
response of the device includes information for several different items.
This is the case with a lot of responses from Oppo bluray players.

Use a “?” for “any single character”, use “??” for “two characters of
any value” and so on. If the length of the wildcard can differ, use a
“?{str}” meaning that the plugin expects a string of any given length.

The definition for audiotype in the example means that the expected
response consists of: “@QAT OK” in the beginning followed by a single
character followed by a “/” and another single character again. After
that is the relevant part of the response, the value of the item,
defined by exactly three digits/characters. Behind that is a blank and
any value consisting of five characters or digits.

The example definition for audiotrack means that the response can be:
“@UAT” followed by any word/number without a specific length, followed
by a blank and the real value consisting of two characters. The response
could also start with “@QTK OK” followed by the relevant value
consisting of exactly one digit/character. After that there will be a
“/” and any character/digit. It is important to add the “/?” in the end
because the plugin also compares the length of the response with the
expected length (calculated from the response in the command-file). It
is not relevant, if you use a {str} in your response because then the
length can not be determined.

This feature is still under development. Feel free to experiment with it
and post your experience in the knx-forum.

.. code-block:: none

    # plugins/avdevice/oppo-udp203.txt
    ZONE; FUNCTION; FUNCTIONTYPE; SEND; QUERY; RESPONSE; READWRITE; INVERTRESPONSE; MINVALUE; MAXVALUE; RESPONSETYPE; TRANSLATIONFILE
    0; audiotype; ; ; #QAT; @QAT OK ?/? *** ?????; R; ; ; ; str
    0; audiotrack; ; #AUD; #QTK; @UAT ?{str} **|@QTK OK */?; RW; ; ; ; num


Webinterface
============

Use the web interface to see which item using the plugin is set to which value.
Furthermore you can see a history of the commands and queries being sent by the
plugin. You can also use the web interface to reload your configuration file.

.. image:: avdevice_webif.png
   :height: 1618px
   :width: 3338px
   :scale: 25%
   :alt: Web Interface
   :align: center

Troubleshooting
===============
1.) Have a look at the webinterface. You'll figure out the item ids and values
as well as a history of the commands.

2.) Have a look at the smarthome logfile. If you can’t figure out the
reason for your problem, change the verbose level in logging.yaml. You
can use level 10 (=DEBUG), 9 (VERBOSE1) and 8 (VERBOSE2) as debugging
levels.

3.) Concerning send and response entries in the text file, make sure the
number of stars correspond to the way your device wants to receive the
command or sends the response. Example 1: Your Pioneer receiver expects
the value for the volume as three digits. So the command needs three
stars. If you now set the item to a value with only two digits, like 90,
the plugin converts the command automatically to have a leading 0.
Example 2: Your Denon receiver responds with values like ON, OFF or
STANDBY to power commands. Replace every character with a star! ON = 2
stars, OFF = 3 stars, etc. Example 3: Sending or receiving strings of
different length like “CD”, “GAME”, etc. should be set up with one star
only. Alternatively you can use "\*{str}". Set the responsetype
accordingly!

4.) Set the response type in the textfile to the correct value. The
plugin tries to anticipate the correct value but that doesn’t always
work. The sleep timer of Denon devices is a wonderfully sick example:
You can set values between 1 and 120 to set the timer in minutes. If you
want to turn it off, the receiver expects the value “OFF” instead of a
zero. The plugin fixes that problem if you set the responsetype to
bool|num. As soon as you set the item to 0, it magically converts that
value to “OFF” and the other way around when receiving “OFF”.
