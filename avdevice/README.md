# AV Device

## Requirements

Serial Python module

Install it with:
sudo pip3 install serial --upgrade

## Supported Hardware

Hopefully several different AV devices based on TCP or Serial RS232 connections
Tested with Pioneer AV receivers and Epson projector

## Configuration

### plugin.yaml

```
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
```


#### Attributes:

* `model`: string. name of AV device. Has to correspond to a text file with the same name in the folder plugins/avdevice.
* `instance`: string. define instance name, each device needs an individual instance name!
* `tcp_ip`: IP address
* `tcp_port`: TCP/IP port
* `tcp_timeout`: TCP/IP timeout
* `rs232_port`: If you use a RS232 cable to communicate with your device (highly recommended!) define the interface port
* `rs232_baudrate`: baudrate for RS232
* `rs232_timeout`: timeout for RS232
* `ignoreresponse`: list of values. the plugin doesn't care about responses from the device starting with the given values. List responses for menu navigation, etc. For Pioneer receivers the following list is recommended: RGB, RGC, RGD, GBH, GHH, VTA, AUA, AUB
* `forcedbuffer`: list of strings. If for whatever reason you don't want to buffer the response from your device you can still define specific responses that should get buffered. This is important for responses that change or get sent very quickly. Artist, title, radio station, etc. are examples that should be put here. For Pioneer receivers the following list is recommended: GEH01020, GEH04022, GEH05024
* `inputignoredisplay`: list of int. The value of the LCD display on your receiver might get updated very often, e.g. when it shows song titles as a scrolling text. To avoid constant display updates and therefore possible confusion with relevant answers of your device listing source inputs like internet radio, LAN streaming, etc. here is highly recommended. For Pioneer receivers the following list is recommended: 26,38,40,41,44,17,02,48,0
* `dependson_item`: item. If given item has given value the commands are sent to the device, otherwise they are not. Relevant if you have your device connected to a power socket that can be turned off.
* `dependson_value`: boolean. If given item has given value the commands are sent to the device, otherwise they are not. Relevant if you have your device connected to a power socket that can be turned off.
* `errorresponse`: list of strings. The standard error responses from your device. For Pioneer receivers they are "E" followed by a number. If no values are provided error answers from your device might get recognized much slower but actually should still get recognized.
* `resetonerror`: boolean. Reset the value of the item that could not be updated. E.g. you set the volume of zone 2 to "100". If either the dependson item is off or the device sends an error response or after several connection and send retries the expected response is not received, the volume item gets set to value it had before you sent the command. That way you avoid having a wrong value displayed in your Visu.
* `depend0_power0`: boolean. If the dependson item is off the power off all zones are set to off. This is especially relevant for a correct representation in your Visu when you have a powered on device but turn off the power socket.
* `depend0_volume0`: boolean. Same as above but in this case the volume is set to 0 for all zones. This is for Visu purposes only.
* `sendretries`: integer. This value defines how often a command should be sent when receiving a wrong answer from the device.
* `resendwait`: float. Seconds the plugin should wait between each resend retry.
* `reconnectretries`: integer. If the plugin can not connect to the device it retries this often. This is especially useful for TCP connections on devices that are plugged into a switchable socket as most receivers need about 40-50 seconds to boot their network device.
* `secondstokeep`: integer. Seconds the plugin should temporarily save a command to retry later on after establishing a connection. This is especially useful for TCP connections on devices that are plugged into a switchable socket as most receivers need about 40-50 seconds to boot their network device.
* `responsebuffer`: integer or boolean. Set this to a number to collect quickly received responses in a buffer and evaluate them collectively. The standard value should be fine and prevent responses getting lost. Some receivers might first respond to a command with an update of the display and then with the actual value. The buffer ensures the correct evaluation of the response.
* `autoreconnect`: boolean. Automatically tries to reconnect if no response is received or connection is lost. This should not be necessary as the plugin always tries to reconnect before sending a command.

### items.yaml

#### avdevice_zone[0-4]@[instance]: [command]

specifiy the zone number and instance.
The command has to correspond to a "base" command in the relevant text configuration file in the avdevice plugin folder named the same as the "model" configured in plugin.yaml.
It is important to set the correct type for each item. The Pioneer RS232 codeset expects bool and int types only.
For example to set the listening mode to "pure direct", the item has to be int and you set it to the value "8".

Full item examples are included as separate yaml files for Pioneer and Denon devices. In general the items are setup the same independent of the AV device model. The examples include the tested items/commands and allow easy copy/paste.

Speakers Items are special and should be set up the way mentioned in the following example. 1 and 2 correspond to the value the speaker command expects.

#### Example

```
# items/my.yaml
Pioneer:
    type: foo

    Power:
        type: bool
        visu_acl: rw
        avdevice_zone1@pioneer_one: power
        enforce_updates: 'no'
        knx_dpt: 1

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

```

### model.txt

#### ZONE;FUNCTION;FUNCTIONTYPE;SEND;QUERY;RESPONSE;READWRITE;INVERTRESPONSE;MAXVALUE;RESPONSETYPE

Configure your commands depending on your model and manufacturer. You have to name the file the same as configured in the plugin.yaml as "model". E.g. if you've configured "model: vsx-923" you name the file "vsx-923.txt"

Each line holds one specific command that should be sent to the device. You also specify the zone, the query command, response command, etc.

* `zone`: Number of zone. Has to correspond to the attribute in item.yaml. E.g. for zone 1 use "avdevice_zone1: command". Zone 0 holds special commands like navigating in the menu, display reponse, information about currently playing songs, etc.

* `function`: name of the function. You can name it whatever you like. You reference this value in the item using avdevice_zoneX: function.

* `functiontype`: for boolean functions use "on" or "off". For commands setting a specific value like source, input mode, volume, etc. use "set". To increase or decrease a value use the corresponding "increase" or "decrease". For everything else leave empty!

* `send`: the command to be sent, e.g. power off is "PF" for Pioneer receivers. You can use a pipe "|" if more than one command should be sent. That might be necessary for power on commands via RS232, e.g. for Pioneer receivers to power on "PO|PO" forces the plugin to send the "PO" command twice. Use stars "\*" to specify the format of the value to be sent. Let's say your device expects the value for volume as 3 digits, a "\*\*\*VL" ensures that even setting the volume to "5" sends the command as "005VL"

* `query`: Query command. This is usually useful after setting up the connection or turning on the power. This command gets also used if the plugin doesn't receive the correct answer after sending a command. It is recommended to leave this value empty for all functions except on, off and set.

* `response`: The expected response after sending a command. Use "none" if you don't want to wait for the correct response. You can use stars "\*" again to ensure that the exact correct value is set. Example: You set the volume to 100. If you want to ensure that the device responds with any value for volume just use "VOL" here (or whatever response your device sends). If you want to ensure that the device is set to a volume of 100, use stars as placeholders, e.g. "VOL\*\*\*" for 3 digits. You can even specify multiple response possibilities separated by "|".

* `readwrite`: R for read only, W for write only, RW for Read and Write. E.g. display values are read only whereas turning the volume up might be a write operation only. Setting this correctly ensures a fast and reliable plugin operation

* `invertresponse`: some devices are stupid enough to reply with a "0" for "on" and "1" for "off". E.g. a Pioneer receiver responds with "PWR0" if the device is turned on. Configure with "yes" if your device is quite stupid, too.

* `maxvalue`: You can define the maximum value for setting a specific function. This might be most relevant for setting the volume. If you configure this with "100" and set the volume to "240" (via Visu or CLI) the value will get clamped by the plugin and set to "100".

* `responsetype`: Defines the type of the response value and can be set to "bool", "num" or "str" or a mixture of them (separated by a pipe "|"). Most response types are set automatically on startup but you can force a specific type using this value. It is recommended to use the values suggested in the txt files that come with the plugin.

#### Example

```
# plugins/avdevice/pioneer.txt
ZONE; FUNCTION; FUNCTIONTYPE; SEND; QUERY; RESPONSE; READWRITE; INVERTRESPONSE; MAXVALUE; RESPONSETYPE
1; power; on; PO|PO; ?P; PWR*; RW; yes
1; power; off; PF; ?P; PWR*; RW; yes
1; volume+; increase; VU; ; VOL; W
1; volume-; decrease; VD; ; VOL; W
1; volume; set; ***VL; ?V; VOL***; RW; ; 185
1; input; set; **FN; ?F; FN**; RW
1; speakers; set; *SPK; ?SPK; SPK*; RW
2; power; on; APO|APO; ?AP; APR*; RW; yes
2; power; off; APF; ?AP; APR*; RW; yes
0; title; ; ; ; GEH01020; R
0; station; ; ; ; GEH04022; R
0; genre; ; ; ; GEH05024; R
0; display; ; ?FL; ?FL; FL******************************; R

```

### Troubleshooting
1.) Have a look at the smarthome logfile. If you can't figure out the reason for your problem, change the verbose level in logging.yaml.
You can use level 10 (=DEBUG), 9 (VERBOSE1) and 8 (VERBOSE2) as debugging levels.

2.) Concerning send and response entries in the textfile, make sure the number of stars correspond to the way your device wants to receive the command or sends the response.
Example 1: Your Pioneer receiver expects the value for the volume as three digits. So the command needs three stars. If you now set the item to a value with only two digits, like 90, the plugin converts the command automatically to have a leading 0.
Example 2: Your Denon receiver responds with values like ON, OFF or STANDBY to power commands. Replace every character with a star! ON = 2 stars, OFF = 3 stars, etc.
Example 3: Sending or receiving strings of different length like "CD", "GAME", etc. should be set up with one star only. Set the responsetype accordingly!

3.) Set the response type in the textfile to the correct value. The plugin tries to anticipate the correct value but that doesn't always work. The sleep timer of Denon devices is a wonderfully sick example: You can set values betwwen 1 and 120 to set the timer in minutes. If you want to turn it off, the receiver expects the value "OFF" instead of a zero. The plugin fixes that problem if you set the responsetype to bool|num. As soon as you set the item to 0, it magically converts that value to "OFF" and the other way around when receiving "OFF".
