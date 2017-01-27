 # Harmony Hub Plugin

 ### Requirenments

 - an Harmony Hub device
 - SmarthomeNG version >= 1.2
 - Python3 module <b>sleekxmpp</b>
  ```
  sudo pip3 install sleekxmpp
  ```
 
 ### Setup activities on Harmony Hub
 
 Thanks to Logitech for closing the access to the Harmony API for end-users, it#s only possible to trigger pre-configured
 activities on your Harmony Hub. (https://support.myharmony.com/en-us/how-to-create-a-harmony-activity). To trigger
 single actions on a device, simple create an activity for each action.

 #### Finding Activity ID

 Before you can start setting up your SmarthomNG items, you have to find out the ids of your configured Harmony Hub
 activities. Therefor you can use the script ```get_activities.py```. You can find in in the Harmony plugin folder,
 usually under ```/usr/local/smarthome/plugins/harmony```
 
 ```python3 get_activities.py -i HARMONY_HUB_IP -p HARMONY_HUB_PORT```
 
 This is an example output:
 ```
 Available Harmony Hub activities:
 {24534937: 'Sat', 24556412: 'dummy', 24555597: 'NVIDIA Shield', -1: 'PowerOff'}
 ```
 
 #### Dummy activity
 A very annoying Harmony Hub behaviour is, that you cannot trigger an activity twice, if it was the last triggered  
 activity. The trick is to define a dummy activity with any unused device in your Harmony App. You can set all delays 
 of this device to 0 in the Harmony Hub settings. If you call this activity <b>dummy</b>, the plugin will use this 
 activity automatically for the internal processing, otherwise you can setup this dummy activity in th plugin 
 configuration.
<p>

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
 
 If your dummy activity is NOT called 'dummy', you have to set the ```harmony_dummy_activity``` manually.
 You can set ```sleekxmpp_debug = true``` to enable verbose output for the underlying sleekxmpp library. 
 <p>
  
 ### Setup item
  
 To configure an Harmony activity vou have to configure an item as follows:
 
 ```
 [MyItem]
    type = bool
    enforce_updates = true
    harmony_activity_0 = 24556412
    harmony_activity_1 = 44153418
    harmony_delay_0 = 1
    harmony_delay_1 = 5
 ```
 
 **harmony_activity_0|1**     [at least one required, type: int]<p>
 All plugin attributes are only valid for items with the type bool. You have to set at least one of the attributes 
 <b>harmony_activity_0</b> or <b>harmony_activity_1</b>, both values together are valid too. If the item value is 
 'True', the activity id defined for harmony_activity_1 will be triggered, harmony_activity_0 vice versa.<p>
 
 **harmony_delay_0|1**     [optional, default: 0, type: int (seconds)]<p>
 Sometimes a device is unresponsive after a power-off/power-on (e.g. turning on the socket). Therefor you can set up a 
 trigger delay for the activity. The attribute harmony_delay_1 defines a delay in seconds for activity defined under 
 harmony_activity_1, harmony_delay_0 for harmony_activity_1. If you omitting these values, the activities are triggered 
 instantly. 
 If an activity should be triggered before and a delayed activity with the same id is already pending, the
 new trigger activity will be ignored.
 
 ### Examples
 ```
 [TV]
    type = bool
    knx_dpt = 1
    knx_listen = 2/2/0
    knx_send = 2/2/1
    knx_init = 2/2/0
    enforce_updates = true
    harmony_activity_1 = 12345678
    harmony_delay_1 = 3
 ```
 
 A value '1' on KNX group address 2/2/0 enables the socket and turn on the plugged-in TV. With a delay of 3 seconds, the 
 Harmony Hub triggers a predefined power-on activity for the TV. 