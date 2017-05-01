# MQTT

This plugin implements a MQTT client.

The MQTT protocol was initially developed by IBM. Since protocol version v3.1.1 it has become an official OASIS standard.

Requirements
============
This plugin needs the following MQTT python modules:

   * [paho-mqtt](https://pypi.python.org/pypi/paho-mqtt)

<pre>In Linux systems can use: pip3 install paho-mqtt </pre>

Besides the Python module you need a MQTT broker to communicate to other MQTT clients. The open souce broker [Mosquitto](https://mosquitto.org) is a good choice.


Configuration
=============

plugin.conf
-----------
<pre>
[mqtt]
    class_name = Mqtt
    class_path = plugins.mqtt
    host = '192.168.0.55'
    port = 1883
    
</pre>


items.conf
--------------

With this attribute you could specify channels to send and receive info.

# Example
```
[alarm_in]
	# messages coming from the alarm panel
        name = alarm_test_mqtt_in
        type = foo
        mqtt_topic_in = "alarm/out"

[alarm_out]
	# messages to send to the alarm panel
        name = alarm_test_mqtt_out
        type = foo
        mqtt_topic_out = "alarm/in"
```

Datatype foo delivers the raw data from the mqtt message to the item (as an array of bytes). 

**NEW:** You can use any of the other datatypes. If you use any of those datatypes, the data from the mqtt message will be casted to the desired format.

Now you could simply use:
```sh.alarm_out(arm)``` to send a mqtt message via the topic 'alarm/out'.
```sh.alarm_in()``` to see messages coming from mqtt bus via topic 'alarm/in'

logic.conf 
-------------

```
[Alarm]
    watch_item = alarm_in	# monitor for changes
```
