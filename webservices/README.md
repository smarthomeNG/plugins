# WebServices plugin

## Description

This plugin makes use of the new SmartHomeNG module system. It provides a Webservice API based on REST and on a URL-based simple version and is
built upon CherryPy.
For REST, basic REST command such as PUT and GET are supported.

Support-Thread für das Plugin: https://knx-user-forum.de/forum/supportforen/smarthome-py/1163886-support-thread-f%C3%BCr-das-webservices-plugin

## Requirements

This plugin requires CherryPy to be installed via pip.
It requires SmartHomeNG 1.4 or higher!

## Configuration

### etc/module.yaml
Basic configuration for the webservices plugin needs to be done in etc/module.yaml. Here the port, user, and plain text password (or alternatively hashed password) can be configured for the service interface in general.
The Hash for the password can be generated via the Backend plugin! If user and password are left empty, none are set. This may be e.g. suitable in case a reverse proxy is used.

The webservice plugin is one functionality that builds upon the service layer configured in module.yaml, but there may be more in the future.

```yaml
    servicesport: 8384
    service_user: serviceuser
    service_password: ''
    service_hashed_password: 'xxx'
```

### plugin.conf (deprecated) / plugin.yaml

```
[WebServices]
   class_name = WebServices
   class_path = plugins.webservices
   mode = all
```

```yaml
WebServices:
    class_name: WebServices
    class_path: plugins.webservices
    mode: all
```
#### Attributes
  * `mode`: Optional mode for the plugin - "all" (default) means you can access all your items via the API. "set" means only defined item sets are accessible.

### items.conf (deprecated) / items.yaml

Currently access to all items is provided via the REST api in case the plugin is set via mode attribute to "all". In case that is not wanted, the attribute "webservices_set" can be used to group selected items to be accessible.

```yaml
MyItem:
    type: str
    webservices_set: 'MySet1'
    webservices_data: 'val'

MyItem2:
    type: num
    webservices_set:
     - 'MySet1'
     - 'MySet2'
    webservices_data: 'full'
```

There are two item-attributes in items.yaml/items.conf that are specific to the webservices plugin. These parameters beginn with **`webservices_`**.

#### webservices_set

**`webservices_set`** contains a string description of the item set, the item shall be added to. A set can be requested as whole by the webservice api. An item can be added to several sets via a yaml list of set identifiers [as Strings].

#### webservices_data
**`webservices_data`** is used to limit the returned values for an item. If the attribute value "val" is set, only the path name and the item value is returned. Otherwise, also all meta information is returned..

## Usage

### General: Error and Success Messages

In case of an error (e.g. item is not found), the plugin returns an error formatted as JSON:

{"Error": "No item with item path offifce.light found."}

In case a request is successful, it returns a SUCCESS message as JSON.

### Web-GUI (overview of services)

A web gui with a list of all available items is provided via
http://<your_server_ip>:<your_backend_port>/ws_gui/

### Simple Interface

#### Get Value

Gets the data of an item, enriched by meta data (if webservices_data is not set to "val"), as json object.

http://<your_server_ip>:<your_services_port>/ws/items/<item_path>

E.g. http://192.168.178.100:1234/ws/items/knx.gf.office.light

returns:

{"changed_by": "Cache", "enforce_updates": "False", "age": 1896.412548, "triggers": ["bound method KNX.update_item of plugins.knx.KNX", "bound method WebSocket.update_item of plugins.visu_websocket.WebSocket", "bound method Simulation.update_item of plugins.simulation.Simulation"], "last_change": "2017-12-02 06:53:56.310862+01:00", "autotimer": "False", "eval": "None", "value": true, "previous_age": "", "previous_value": true, "type": "bool", "config": {"alexa_actions": "turnOn turnOff", "alexa_name": "Lampe B\u00fcro", "knx_dpt": "1", "knx_init": "2/3/50", "knx_listen": "2/3/50", "knx_send": ["2/3/10"], "nw": "yes", "sim": "track", "visu_acl": "rw"}, "name": "knx.gf.office.light", "path": "knx.gf.office.light", "threshold": "False", "cache": "/python/smarthome/var/cache/knx.gf.office.light", "cycle": "", "last_update": "2017-12-02 06:53:56.310862+01:00", "previous_change": "2017-12-02 07:18:22.911165+01:00", "eval_trigger": "False", "crontab": "", "logics": ["LightCheckLogic"]}

#### Set Value

Sets a value of an item.

http://<your_server_ip>:<your_services_port>/items/<item_path>/<value>

E.g. http://192.168.178.100:1234/ws/items/office.light/0 or http://192.168.178.100:1234/ws/items/office.light/False turns off the light.

#### Get Item Set

Gets the data of an item set, enriched by meta data (if webservices_data is not set to "val"), as json object. The key for accessing the items is the item path.

http://<your_server_ip>:<your_services_port>/ws/itemset/<set_name>

### REST Compliant Interface

#### HTTP GET (e.g. normal access to the URL)

##### Reading an Item's Values

Gets the value of an item, enriched by meta data, as json object. Here, also the REST Url is provided as URL field.

http://<your_server_ip>:<your_services_port>/rest/items/<item_path>

E.g. http://192.168.178.100:1234/rest/items/knx.gf.office.light

returns:

{"changed_by": "Cache", "enforce_updates": "False", "age": 1896.412548, "triggers": ["bound method KNX.update_item of plugins.knx.KNX", "bound method WebSocket.update_item of plugins.visu_websocket.WebSocket", "bound method Simulation.update_item of plugins.simulation.Simulation"], "last_change": "2017-12-02 06:53:56.310862+01:00", "autotimer": "False", "eval": "None", "value": true, "previous_age": "", "previous_value": true, "type": "bool", "config": {"alexa_actions": "turnOn turnOff", "alexa_name": "Lampe B\u00fcro", "knx_dpt": "1", "knx_init": "2/3/50", "knx_listen": "2/3/50", "knx_send": ["2/3/10"], "nw": "yes", "sim": "track", "visu_acl": "rw"}, "name": "knx.gf.office.light", "path": "knx.gf.office.light", "threshold": "False", "cache": "/python/smarthome/var/cache/knx.gf.office.light", "cycle": "", "last_update": "2017-12-02 06:53:56.310862+01:00", "previous_change": "2017-12-02 07:18:22.911165+01:00", "eval_trigger": "False", "crontab": "", "logics": ["LightCheckLogic"]}

##### Item List

The following URL prints out a list of all items, that can be requested or modified by the plugin (all str, num and bool items).
For each item, the detail information is also delivered.

http://<your_server_ip>:<your_services_port>/rest/items/

E.g. http://192.168.178.100:1234/rest/items/ returns the list of all available (str, num, bool) items. The key for accessing the items is the item path.

##### Item Set

Gets the data of an item set, enriched by meta data (if webservices_data is not set to "val"), as json object. The key for accessing the items is the item path.

http://<your_server_ip>:<your_services_port>/rest/itemset/<set_name>

#### HTTP PUT

A HTTP PUT request to the URL sets a value of an item. Only num, bool and str item types are supported.
For bool items you can use int values 0 and 1, but also "yes", "no", "y", "n", "true", "false", "t", "f", "on", "off".
In case you send a string (or a string bool representation), take care it is provided in "...".

http://<your_server_ip>:<your_services_port>/rest/items/<item_path>

E.g. a PUT request with 0 as payload to http://192.168.178.100:1234/rest/items/office.light turns off the light.