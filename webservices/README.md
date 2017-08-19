# WebServices plugin

## Description

This plugin makes use of the new SmartHomeNG module system. It provides a Webservice API based on REST and is 
built upon Cherrpy.
Basic REST command such as PUT and GET are supported.

## Requirements

This plugin requires CherryPy to be installed via pip.

## Configuration

### plugin.conf (deprecated) / plugin.yaml

```
[WebServices]
   class_name = WebServices
   class_path = plugins.webservices
```

```yaml
WebServices:
    class_name: WebServices
    class_path: plugins.webservices
```

### items.conf (deprecated) / items.yaml

Currently access to all items is provided via the REST api, no setting has to be made in items.conf (deprecated) / items.yaml

## Usage

### General: Error and Success Messages

In case of an error (e.g. item is not found), the plugin returns an error formatted as JSON:

{"Error": "No item with item path offifce.light found."}

In case a request is successful, it returns a SUCCESS message as JSON.

### Simple Interface

#### Get

Gets the value of an item.

http://<your_server_ip>:<your_backend_port>/ws/get/<item_path>

E.g. http://192.168.178.100:1234/ws/get/office.light returns "True" when the light is on.

#### Set

Sets a value of an item.

http://<your_server_ip>:<your_backend_port>/ws/set/<item_path>/<value>

E.g. http://192.168.178.100:1234/ws/set/office.light/0 or http://192.168.178.100:1234/ws/set/office.light/False turns off the light.

#### Details

Returns detail data of the item.

http://<your_server_ip>:<your_backend_port>/ws/details/<item_path>

E.g. http://192.168.178.100:1234/ws/details/office.light

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

### REST Compliant Interface

http://<your_server_ip>:<your_backend_port>/rest/item/<item_path>
http://<your_server_ip>:<your_backend_port>/rest/items/

#### HTTP GET (e.g. normal access to the URL)

Gets the value of an item.

E.g. http://192.168.178.100:1234/rest/item/office.light returns "True" when the light is on.
E.g. http://192.168.178.100:1234/rest/items/ return the list of all available items.

#### HTTP PUT

A HTTP PUT request to the URL sets a value of an item. Only num, bool and str item types are supported.
For bool items you can use int values 0 and 1, but also "yes", "no", "y", "n", "true", "false", "t", "f", "on", "off".
In case you send a string (or a string bool representation), take care it is provided in "...".

http://<your_server_ip>:<your_backend_port>/rest/item/<item_path>/<value>

E.g. http://192.168.178.100:1234/rest/item/office.light/0 turns off the light.

#### HTTP GET (List of Accessible Items)

The following URL prints out a list of all items, that can be requested or modified by the plugin (all str, num and bool items).

http://<your_server_ip>:<your_backend_port>/rest/items/