# REST plugin

## Description

This plugin makes use of the new SmartHomeNG module system. It provides a REST based API
built upon Cherrpy.
Basic REST command such as put and get are supported.

## Requirements

This plugin requires CherryPy to be installed via pip.

## Configuration

### plugin.conf (deprecated) / plugin.yaml

```
[REST]
   class_name = REST
   class_path = plugins.rest
```

```yaml
REST:
    class_name: REST
    class_path: plugins.rest
```

### items.conf (deprecated) / items.yaml

 All items are provided via the REST api, no setting has to be made in items.conf (deprecated) / items.yaml

## Usage

### GET

Gets the value of an item.

http://<your_server_ip>:<your_backend_port>/rest/get/<item_path>

E.g. http://192.168.178.100:1234/rest/get/office.light returns "True" when the light is on.

### PUT

Sets a value of an item.

http://<your_server_ip>:<your_backend_port>/rest/get/<item_path>/<value>

E.g. http://<your_server_ip>:<your_backend_port>/rest/put/<item_path>

http://192.168.178.100:1234/rest/put/office.light/0 turns of the light.

### HEAD

Returns meta data of the item.

http://<your_server_ip>:<your_backend_port>/rest/head/<item_path>

E.g. http://192.168.178.100:1234/rest/head/office.light

[{"name": "office.light", "last_change": "2017-08-18 12:40:33.544449+02:00", "threshold": "False", "crontab": "", 
"enforce_updates": "False", "eval_trigger": "False", "autotimer": "False", "logics": "[]", 
"config": "{\"alexa_actions\": \"turnOn turnOff\", \"alexa_name\": \"Lampe B\\u00fcro\", \"knx_dpt\": \"1\", 
\"knx_init\": \"2/3/50\", \"knx_listen\": \"2/3/50\", \"knx_send\": [\"2/3/10\"], \"nw\": \"yes\", \"sim\": \"track\", 
\"visu_acl\": \"rw\"}", "previous_change": "2017-08-18 15:12:36.970801+02:00", "eval": "None", "cycle": "", 
"previous_age": "", "triggers": "[\"bound method KNX.update_item of plugins.knx.KNX\", 
\"bound method WebSocket.update_item of plugins.visu_websocket.WebSocket\", 
\"bound method Simulation.update_item of plugins.simulation.Simulation\"]", "path": "office.light", "age": 9123.543011, 
"type": "bool", "last_update": "2017-08-18 12:40:33.544449+02:00", "changed_by": "Cache", 
"cache": "/usr/local/smarthome/var/cache/office.light"}]

### General

In case of an error (e.g. item is not found), the plugin returns an error formatted as JSON:

{"Error": "No item with item path offifce.light found."}