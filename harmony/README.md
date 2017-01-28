# Harmony Hub Plugin

This is the SmarthomeNG-Plugin for a Harmony Hub device.
For support, questions and bug reports, please refer to [KNX-User-Forum](https://knx-user-forum.de/forum/supportforen/smarthome-py/1046500-harmony-hub-plugin)

### Requirenments

- an Harmony Hub device
- SmarthomeNG version >= 1.3
- Python3 module <b>sleekxmpp</b>

```
    sudo pip3 install sleekxmpp
```

#### Device IDs and Commands

Before you can start setting up your SmarthomNG items, you have to find out the ids of your configured Harmony Hub
devices and their associated commands. Therefor you can use the script ```get_activities.py```. normally located under 
'/usr/local/smarthome/plugins/harmony'.
 
Execute this script like this:
 
```python3 get_activities.py -i HARMONY_HUB_IP -p HARMONY_HUB_PORT```
 
If you want to save the output, you can redirect the stdout to a file:
 
```python3 get_activities.py -i HARMONY_HUB_IP -p HARMONY_HUB_PORT > /your/path/here.txt```
 
 
 This is an example output:
```
    Philips 50PFL7956K/02     device id: 31913922
    ---------------------------------------------
        Power
            command: PowerOff
            command: PowerOn
            command: PowerToggle
        NumericBasic
            command: 0
            command: 1
            ...
        Volume
            command: Mute
            command: VolumeDown
            command: VolumeUp
            ...
        ...
        
    Pace S HD 201     device id: 31914808
    -------------------------------------
        Power
            command: PowerToggle
        Channel
            command: ChannelPrev
            command: ChannelDown
            command: ChannelUp
            ...
        NavigationBasic
            command: DirectionDown
            command: DirectionLeft
            command: DirectionRight
            ...
        TransportBasic
            command: Stop
            command: Play
            command: Rewind
        ...
            
    Microsoft Xbox One     device id: 31907101
    ------------------------------------------
        Power
            command: PowerOff
            ...
        ...
```
 
You need the device id and the name of the command.
 
### Setup plugin

- Activate the plugin in your plugins.conf [default: /usr/local/smarthome/etc/plugins.conf]
- Set the IP for your Harmony hub device 

```
    [harmony]
        class_name = Harmony
        class_path = plugins.harmony
        harmony_ip = 192.168.178.78 
        #harmony_port = 5222 # [default: 5222, int]
        #harmony_dummy_activity = 1234567 #  [default: None, int]
        #sleekxmpp_debug = false  #[default:false, bool]
```
<p>
  
### Setup item
  
To configure Harmony command(s) vou have to set an item as follows:
 
```
    [MyItem]
        type = bool
        enforce_updates = true
        harmony_command_0 = DEVICE_ID:COMMAND(:DELAY)|DEVICE_ID:COMMAND(:DELAY)| .... | .... | .... | ....
        harmony_command_1 = DEVICE_ID:COMMAND(:DELAY)|DEVICE_ID:COMMAND(:DELAY)| .... | .... | .... | ....
```
 
**harmony_command_0_0|1**     [at least one required]<p>
All plugin attributes are only valid for items with the type 'bool'. You have to set at least one of the attributes 
<b>harmony_command_0</b> or <b>harmony_command_1</b>, both values together are valid too. If the item value is 
'True', the command defined for harmony_command_1 will be triggered, harmony_command_0 vice versa.<p>

As you can see the format of a **command** is always ```DEVICE_ID:COMMAND(:DELAY)|DEVICE_ID:COMMAND(:DELAY)```. The 
delay parameter defines the time in seconds to wait before the next command will be triggered. This parameter is 
optional (default: 0.2s) and can be omitted. You have to find out the right value by yourself since it heavily
depends on your device. The maximum value is 60 (seconds).  
You can group more than one commands together like this: ```COMMAND1 | COMMAND2 | COMMAND3```
 
### Limitations

Only one set of commands can be triggered by the plugin simultaneously to avoid unpredictable behavior. 
 
### Real World Examples

```
    [[Shield]]
        type = bool
        harmony_command_1 = 42282391:PowerOn:6|42282391:InputBd
        harmony_command_0 = 42282391:PowerOff
```
 
If the Item 'Shield' is set to True, the AV receiver is powered on and the and the input channel is set to 'Bluray' 
after 6 seconds (the AV receiver is not instantly responsive after a power-on). 
If the Item 'Shield' is set to False, the AV receiver is powered off.
 
```
    [[RTL]]
        type = bool
        harmony_command_1 = 42282391:InputSat/Cbl:0.2|31914808:3:0.3|31914808:Select
```
This command sets the input channel of the AV receiver to SAT/Cbl, enters '3' and commits the input with 'Select'.