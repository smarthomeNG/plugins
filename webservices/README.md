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

http://<your_server_ip>:<your_backend_port>/rest/item/<item_path>
http://<your_server_ip>:<your_backend_port>/rest/items/

### HTTP GET (e.g. normal access to the URL)

Gets the value of an item.

E.g. http://192.168.178.100:1234/rest/item/office.light returns "True" when the light is on.
E.g. http://192.168.178.100:1234/rest/items/ return the list of all available items.

### HTTP PUT

A HTTP PUT request to the URL sets a value of an item. Only num, bool and str item types are supported.
For bool items you can use int values 0 and 1, but also "yes", "no", "y", "n", "true", "false", "t", "f", "on", "off".
In case you send a string (or a string bool representation), take care it is provided in "...".

http://<your_server_ip>:<your_backend_port>/rest/item/<item_path>/<value>

E.g. http://192.168.178.100:1234/rest/item/office.light/0 turns of the light.

### General

In case of an error (e.g. item is not found), the plugin returns an error formatted as JSON:

{"Error": "No item with item path offifce.light found."}

In case a PUT request is successful, it returns a SUCCESS message as JSON.