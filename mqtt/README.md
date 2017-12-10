# MQTT

#### Version 1.3.4

This plugin implements the the functionality for SmartHomeNG to act as a MQTT client.

This plugin is a complete rewrite, replacing the initial MQTT plugin from smarthome.py.

MQTT is a lightweight machine-to-machine (M2M)/"Internet of Things" connectivity protocol. The MQTT protocol was initially developed by IBM. Since protocol version v3.1.1 it has become an official OASIS standard.

Details on the protocol can be found on [mqtt.org](http://mqtt.org).

## Support
Support is provided trough the support thread within the smarthomeNG forum: [Support-Thread](https://knx-user-forum.de/forum/supportforen/smarthome-py/1089334-neues-mqtt-plugin)

## Change History

### Changes since version 1.3.3

- Fixed error not initializing subscriptions for items, if the broker was slow to respond on connect

### Changes since version 1.3.2

- Fixed error with empty last_will_topic
- allowed Muilti-Instance

### Changes since version 1.3.1

- Login to broker with user/password is supported
- Log the type and version of the broker
- configure host by dns-name or ip address 
- Added functions to allow other plugins to use this plugin for MQTT communication (documented at the end of this document)


### Requirements

This plugin needs the following following software to be installed and running:

- MQTT python module: [paho-mqtt](https://pypi.python.org/pypi/paho-mqtt)
<pre>In Linux systems can use: pip3 install paho-mqtt </pre>

- A MQTT broker for communication with other MQTT clients. The broker may be running on the hardware SmartHomeNG is running on, or on another hardware that can be reached via TCP/IP. The open souce broker [Mosquitto](https://mosquitto.org) is a good choice. 

### Using Mosquitto Broker on Raspberry Pi
If want to run the broker on a Raspberry Pi you should be aware, that the broker on the raspbian repository is quite old. You should add the mosquitto.org repository as a trusted site to your **`apt-get`** to get a recent version of mosquitto installed.


## Configuration

### plugin.yaml (minimal configuration)
To setup the MQTT plugin only three parameters need to be defined in **`plugin.yaml`**:

```yaml
mqtt:
    class_name: Mqtt
    class_path: plugins.mqtt
    host: '192.168.0.55'
```

All other parameters are optional and only used, if you want to use advanced features. When not configuring the advanced parameters, this plugin should be compatible in usage to the old MQTT plugin from smarthome.py.

### plugin.yaml (advanced configuration)

```yaml
mqtt:
    class_name: Mqtt
    class_path: plugins.mqtt
    host: '192.168.0.55'
    # port: 1883
    # qos: 1
    # last_will_topic: 'shng/$online'
    # last_will_payload: False
    # birth_topic: 'shng/$online'
    # birth_payload: True

    # user: None                 # username (or None)
    # password: None             # password (or None)
    # hashed_password: 1245a9633edf47b7091f37c4d294b5be5a9936c81 ...    
    # === The following parameters are not yet implemented:
    # publish_items: no          # NEW: publish using item-path
    # items_topic_prefix: 'shng' # NEW: prefix for publishing items     
    # acl: pub                   # NEW: access control (none, pub, sub, pubsub)
    # tls: None                  # use TLS version (v1 or None)
    # ca_certs: '/etc/...'       # path to the Certificate Authority certificate files     
```

All entries that are commented out are optional and don't have to be specified to get the plugin up and running.

#### host - Adress of MQTT broker
**`host`** specifies the IP adress of the MQTT broker to use. If you use a broker on the computer you are running SmartHomeNG on, you don't need to specify this parameter. In this case it is assumed, that the MQTT broker runs on the same machine as SmartHomeNG and 127.0.0.1 (for localhost) is used.

#### port - Port used by broker
Port 1883 and 8883 are the IANA reserved ports for MQTT.

* 1883: This is the default MQTT port. It is defined at IANA as **MQTT over TCP**. 
* 8883: This is the default MQTT port for MQTT over TLS. It’s registered at IANA for **Secure MQTT**.

In a standard setup you should not need to configure this parameter.

#### qos - Quality-Of-Service
**`qos`** defines the default quality of service level used when communicating with the broker. It can be overwritten by setting the **`mqtt_qos`** attribute on an individual item.

You don't have to specify a settings for **`qos`**.  The default value used will be QoS 1.

MQTT supports three levels for Quality-Of-Service (0=at most once, 1=at least once, 2=excactly once). QoS 2 has the most overhead and should be used only if needed. 

A good explanation about Quality-of-Service in MQTT can be found [here](http://www.hivemq.com/blog/mqtt-essentials-part-6-mqtt-quality-of-service-levels).


#### last_will_topic - MQTT testament message
if **`last_will_topic`** is not specified, there will be no last-will-message sent. As a standard the last-will message will only be sent if the connection to the broker aborts (is not closed in an orderly manner). 

Last-will-messages will be sent with the default QoS. 

If you specify a birth-message, the last-will-message will be sent with the retain flag set and the last-will-message will also be sent if the connection is closed orderly (by shutting down SmartHomeNG).

#### last_will_payload - MQTT testament message
if **`last_will_payload`** is not specified, there will be no last-will message sent.

#### birth_topic - Birth message
The birth message is the opposite to the MQTT Testament message and sent, when the plugin starts up. if **`birth_topic`** is not specified, the **`last_will_topic`** will be used for the birth message too. Birth-messages will be sent with the default QoS and the retain flag set.

#### birth_payload - birth message
if **`birth_payload`** is not specified, no birth message will be sent. In this case there will be no last-will message sent, if the connection is closed orderly (by shutting down SmartHomeNG).

#### user - username to login to broker (optional)
Username to login to the MQTT broker, if the broker is configured for user/password authentication.

>NOTICE: Until Implementation of TLS, username and password are transmitted unencrypted.

#### password - password to login to broker (optional)
Password to login to the MQTT broker, if the broker is configured for user/password authentication.

>NOTICE: 
>
>- Until Implementation of TLS, username and password are transmitted unencrypted.
>- At this stage of implementation the Password is stored in the plugin.yaml file as clear text.

### Configuration *(not yet implemented)*

#### hashed_password (optional)
The password for broker login as hash value. Can be used instead of "password" if you do not want a plaintext password in your config file. Currently hashed_password is the SHA-512 hash value of the password. To create the hash for your password, you can use function "Create password hash" on page "Services" in the backend.

#### publish_items
	-> ***not yet implemented***
**`publish_items`** controls weather the items should be published by their item-path. If **`publish_items`**  is set to True, items are published (using **`items_topic_prefix`**) if the acl-setting for that items allows it.

#### items_topic_prefix
	-> ***not yet implemented***
**`items_topic_prefix`** defines the prefix when building the MQTT topic from item-path.

Example: If you have the following items:

```yaml
root:
   parent:
       testitem:
            name: Test Item for publishing
            type: num
```
and have set 

```yaml
mqtt:
    items_topic_prefix: 'item_tree'
```
The item **`testitem`** would be published with the MQTT topic 

**`item_tree/root/parent/testitem`**

#### acl - Access Control List
	-> ***not yet implemented***
**`acl`** defines the global default setting for the access control to the items. Access control is only active, when publishing the item-tree structure of SmartHomeNG.

- none=no access (default, if parameter is not configured)
- pub=publish as topic (read only from other client)
- sub=subscribe to topic (accept data from other clients)
- pubsub=publish and subscribe topic.

This parameter defines the default access control for items, which have no individual access control configured.

#### tls - Use tls for encryption
	-> ***not yet implemented***
Use tls for encryption

#### ca_certs - path to certificate files
	-> ***not yet implemented***
path to certificate files


### Example: items.yaml
Example configuration in yaml-format:

```yaml
alarm_in_
    # messages coming from the alarm panel
    # (called 'alarm/out' by the alarm panel)
    name: alarm_test_mqtt_in
    type: foo
    mqtt_topic_in: 'alarm/out'

alarm_out:
    # messages published, to be read by the alarm panel
    name: alarm_test_mqtt_out
    type: foo
    mqtt_topic_out: 'alarm/in'

```

### Example: items.conf
Example configuration in the old conf-format:

```
[[alarm_in_]]
    # messages coming from the alarm panel
    # (called 'alarm/out' by the alarm panel)
    name = alarm_test_mqtt_in
    type = foo
    mqtt_topic_in = 'alarm/out'

[[alarm_out]]
    # messages published, to be read by the alarm panel
    name = alarm_test_mqtt_out
    type = foo
    mqtt_topic_out = 'alarm/in'

```


Datatype foo delivers the raw data from the MQTT message to the item (as an array of bytes). 

**NEW:** You can use any of the other datatypes. If you use any of those datatypes, the data from the mqtt message will be casted to the desired format.

#### mqtt_topic_out
**`mqtt_topic_out`** defines the MQTT topic under which the items value is to be published as payload.

#### mqtt_topic_init
**`mqtt_topic_init`** is equivalent to **`mqtt_topic_out`**, except it initializes the topic when SmartHomeNG ist started.

#### mqtt_topic_in
**`mqtt_topic_in`** defines the MQTT topic to subscribe to. Upon receiving a message with this topic, the payload is used to set the item's value.

#### mqtt_topic
If you specify **`mqtt_topic`**, it set this topic for in- and outgoing messages. Thus it overwrites seperate values you might have specified for **`mqtt_topic_out`** or **`mqtt_topic_in`**.

#### mqtt_acl - Access control for this item
	-> ***not yet implemented***
**`mqtt_acl`** defines the access control setting for this item. If not specified, the plugin's default is used. Access control is only active, when publishing the item-tree structure of SmartHomeNG.

#### mqtt_qos
**`mqtt_qos`** defines the quality of service level for this item used when communicating with the broker. If not specified, the plugin's default is used.

#### mqtt_retain
When set to **`True`**, the MQTT message is sent with the retain flag set.

Now you could simply use:
```sh.alarm_out(arm)``` to send a mqtt message via the topic 'alarm/out'.
```sh.alarm_in()``` to see messages coming from mqtt bus via topic 'alarm/in'

### logic.yaml

You can specify a MQTT topic to trigger a logic. The logic is triggered every time a message with this topic is received. 

```yaml
Alarm:
    mqtt_watch_topic: alarm_in	# monitor for changes
#    mqtt_payload_type: str
```

**`mqtt_watch_topic`** specifies the MQTT topic which triggers the logic. A logic that is triggered by the MQTT plugin gets the following information:

* trigger['by']	**`MQTT`** or **`MQTT@<instance>`**
* trigger['source']	topic of the MQTT message 
* trigger['value']	payload of the MQTT message


if  **`mqtt_payload_type`** is specified, the payload is converted to the SmartHomeNG datatype before being handed to the logic. Otherwise the payload is handed over as raw data (array of bytes).

## Interface for other Plugins
Version 1.3.2 added functions to allow other plugins to use this plugin for MQTT communication.

> Example: A plugin (enow) to communicate with an EnOcean gateway over MQTT.
>
> (Links to this example will be added later.)


### Functions of the interface

#### publish_topic(plug, topic, payload, qos=None, retain=False)

        function to publish a topic
        
        this function is to be called from other plugins, which are utilizing
        the mqtt plugin
        
        :param topic:      topic to publish to
        :param payload:    payload to publish
        :param qos:        quality of service (optional) otherwise the default of the mqtt plugin will be used
        :param retain:     retain flag (optional)


#### subscription_callback(plug, sub, callback=None)

        function set a callback function
        
        this function is to be called from other plugins, which are utilizing
        the mqtt plugin
        
        :param plug:       identifier of plgin/logic using the MQTT plugin
        :param sub:        topic(s) which should call the callback function
                           example: 'device/eno-gw1/#'
        :param callback:   quality of service (optional) otherwise the default of the mqtt plugin will be used

#### subscribe_topic(plug, topic, qos=None)

        function to subscribe to a topic
         
        this function is to be called from other plugins, which are utilizing
        the mqtt plugin
         
        :param topic:      topic to subscribe to
        :param qos:        quality of service (optional) otherwise the default of the mqtt plugin will be used
