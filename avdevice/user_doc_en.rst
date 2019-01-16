.. index:: Plugins; avdevice
.. index:: avdevice

avdevice
########

Configuration
=============

.. important::

      Find detailed information on the config at :doc:`/plugins_doc/config/avdevice`


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

Commandfile
===========

model.txt
ZONE;FUNCTION;FUNCTIONTYPE;SEND;QUERY;RESPONSE;READWRITE;INVERTRESPONSE;MINVALUE;MAXVALUE;RESPONSETYPE;TRANSLATIONFILE

Configure your commands depending on your model and manufacturer. You have to name the file the same as configured in the plugin.yaml as "model". E.g. if you've configured ``model: vsx-923`` you name the file ``vsx-923.txt``

Each line holds one specific command that should be sent to the device. You also specify the zone, the query command, response command, etc. You can comment out lines by placing a ``#`` in front of the line. You can also comment a whole block by using ``'''`` at the beginning and end of a block.

- **zone**: Number of zone. Has to correspond to the attribute in item.yaml. E.g. for zone 1 use ``avdevice_zone1: command``. Zone 0 holds special commands like navigating in the menu, display reponse, information about currently playing songs, etc.

- **function**: name of the function. You can name it whatever you like. You reference this value in the item using avdevice_zoneX: function.

- **functiontype**: for boolean functions use ``on`` or ``off``. For commands setting a specific value like source, input mode, volume, etc. use ``set``. To increase or decrease a value use the corresponding ``increase`` or ``decrease``. For everything else leave empty!

- **send**: the command to be sent, e.g. power off is "PF" for Pioneer receivers. You can use a pipe ``|`` if more than one command should be sent. Add an integer or float to specify a pause in seconds between the commands, like "PO|2|PO". That might be necessary for power on commands via RS232, e.g. for Pioneer receivers to power on "PO|PO" forces the plugin to send the "PO" command twice. Use stars ``\*`` to specify the format of the value to be sent. Let's say your device expects the value for volume as 3 digits, a "\*\*\*VL" ensures that even setting the volume to "5" sends the command as "005VL"

- **query**: Query command. This is usually useful after setting up the connection or turning on the power. This command gets also used if the plugin doesn't receive the correct answer after sending a command. It is recommended to leave this value empty for all functions except on, off and set.

- **response**: The expected response after sending a command. Use ``none`` if you don't want to wait for the correct response. You can use stars "\*" again to ensure that the exact correct value is set. Example: You set the volume to 100. If you want to ensure that the device responds with any value for volume just use "VOL" here (or whatever response your device sends). If you want to ensure that the device is set to a volume of 100, use stars as placeholders, e.g. "VOL\*\*\*" for 3 digits. You can even specify multiple response possibilities separated by ``|``.

- **readwrite**: R for read only, W for write only, RW for Read and Write. E.g. display values are read only whereas turning the volume up might be a write operation only. Setting this correctly ensures a fast and reliable plugin operation

- **invertresponse**: some devices are stupid enough to reply with a "0" for "on" and "1" for "off". E.g. a Pioneer receiver responds with "PWR0" if the device is turned on. Configure with ``yes`` if your device is quite stupid, too.

- **minvalue**: You can define the minimum value for setting a specific function. This might be most relevant for setting the volume or bass/trebble values. If you configure this with "-3" and set the bass to "-5" (via Visu or CLI) the value will get clamped by the plugin and set to "-3".

- **maxvalue**: You can define the maximum value for setting a specific function. This might be most relevant for setting the volume. If you configure this with "100" and set the volume to "240" (via Visu or CLI) the value will get clamped by the plugin and set to "100".

- **responsetype**: Defines the type of the response value and can be set to ``bool``, ``num`` or ``str`` or a mixture of them (separated by a pipe "|" or comma ","). Most response types are set automatically on startup but you can force a specific type using this value. It is recommended to use the values suggested in the txt files that come with the plugin.

- **translationfile**: If you want to translate a specific value/code to something else, define a txt file here that holds the information on how to translate which value. Find more info on this feature below.

.. code-block:: none

    # plugins/avdevice/pioneer.txt
    ZONE; FUNCTION; FUNCTIONTYPE; SEND; QUERY; RESPONSE; READWRITE; INVERTRESPONSE; MINVALUE; MAXVALUE; RESPONSETYPE; TRANSLATIONFILE
    1; power; on; PO|PO; ?P; PWR*; RW; yes
    1; power; off; PF; ?P; PWR*; RW; yes
    1; volume+; increase; VU; ; VOL; W
    1; volume-; decrease; VD; ; VOL; W
    1; volume; set; ***VL; ?V; VOL***; RW; ; 80; 185
    1; source; set; **FN; ?F; FN**; RW
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
    1; set_listeningmode; set; ****SR; ?S; SR****; RW; ; ; ; num; pioneer_SR
    #0; test; ; ; ; noidea; R (commented out)

Struct Templates
================

Since smarthomeNG 1.6 you can use templates provided by the plugin:

- general: Display, menu, cursor, statusupdate, reload config, etc.
- speaker_selection: speaker A, B or both
- individual_volume: set the volume of each speaker individually
- sound_settings: listening Mode, bass, trebble, dynamic compression, etc.
- video_settings: aspect Ratio, monitorout, etc.
- zone1, zone2, zone3: several relevant functions like source, volume, etc.

The templates might include too many items or items your device does not support. As long as there is no command in the models/model.txt file, the items are just ignored. So no problem!

Translation
===========

Create a filename in the translations folder named as referenced in the model.txt that contains translations.
You could create a file called denon_volume.txt and link it in your model.txt file to convert 3 digit volume to a float. Denon receivers handle e.g. 50.5 as 505. If you want to use value limits or visualize the volume correctly in your VISU you should use the following translation file:

.. code-block:: none

    # plugins/avdevice/denon_volume.txt
    CODE; TRANSLATION
    ***; **.*

Pioneer receivers use numbers to define input source or listening mode what is very cryptic and not very user friendly. Therefore you should use the relevant files in the plugins folder like pioneer_input. That file looks something like this:

.. code-block:: none

    # plugins/avdevice/pioneer_input.txt
    CODE; TRANSLATION
    00; PHONO
    01; CD
    02; TUNER

Now, when the plugin receives FN01 as a response, the response gets converted to "CD". Vice versa you can even update your item to "CD" and the plugin will send "01FN" as a command. It is advised to define the according item as type=foo so you can either use a number or string, just the way you like.

Wildcards
=========

For the model.txt file you can use question marks as a wild card if the response of the device includes information for several different items. This is the case with a lot of responses from Oppo bluray players.

Use a ``?`` for "any single character", use "??" for "two characters of any value" and so on. If the length of the wildcard can differ, use a ``?{str}`` meaning that the plugin expects a string of any given length.

.. code-block:: none

    # plugins/avdevice/oppo-udp203.txt
    ZONE; FUNCTION; FUNCTIONTYPE; SEND; QUERY; RESPONSE; READWRITE; INVERTRESPONSE; MINVALUE; MAXVALUE; RESPONSETYPE; TRANSLATIONFILE
    0; audiotype; ; ; #QAT; @QAT OK ?/? *** ?????; R; ; ; ; str
    0; audiotrack; ; #AUD; #QTK; @UAT ?{str} **|@QTK OK */?; RW; ; ; ; num

The definition for audiotype in the example means that the expected response consists of:
"@QAT OK " in the beginning followed by a single character followed by a "/" and another single character again. After that is the relevant part of the response, the value of the item, defined by exactly three digits/characters. Behind that is a blank and any value consisting of five characters or digits.

The example definition for audiotrack means that the response can be: "@UAT " followed by any word/number without a specific length, followed by a blank and the real value consisting of two characters. The response could also start with "@QTK OK " followed by the relevant value consisting of exactly one digit/character. After that there will be a "/" and any character/digit. It is important to add the "/?" in the end because the plugin also compares the length of the response with the expected length (calculated from the response in the command-file). It is not relevant, if you use a {str} in your response because then the length can not be determined.

This feature is still under development. Feel free to experiment with it and post your experience in the knx-forum:
`Plugin AVDevice Support <https://knx-user-forum.de/forum/supportforen/smarthome-py/1097870-neues-plugin-av-device-f%C3%BCr-yamaha-pioneer-denon-etc>`_


Troubleshooting
===============

1.) Have a look at the smarthome logfile. If you can't figure out the reason for your problem, change the verbose level in logging.yaml.
You can use level 10 (=DEBUG), 9 (VERBOSE1) and 8 (VERBOSE2) as debugging levels.

2.) Concerning send and response entries in the textfile, make sure the number of stars correspond to the way your device wants to receive the command or sends the response.

Example 1: Your Pioneer receiver expects the value for the volume as three digits. So the command needs three stars. If you now set the item to a value with only two digits, like 90, the plugin converts the command automatically to have a leading 0.

Example 2: Your Denon receiver responds with values like ON, OFF or STANDBY to power commands. Replace every character with a star! ON = 2 stars, OFF = 3 stars, etc.

Example 3: Sending or receiving strings of different length like "CD", "GAME", etc. should be set up with "*{str}". Set the responsetype accordingly!

3.) Set the response type in the textfile to the correct value. The plugin tries to anticipate the correct value but that doesn't always work. The sleep timer of Denon devices is a wonderfully sick example: You can set values between 1 and 120 to set the timer in minutes. If you want to turn it off, the receiver expects the value "OFF" instead of a zero. The plugin fixes that problem if you set the responsetype to bool|num. As soon as you set the item to 0, it magically converts that value to "OFF" and the other way around when receiving "OFF".

4.) The web interface gives an overview on the last sent commands, etc.
