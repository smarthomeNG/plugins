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

http://<your_server_ip>:<your_backend_port>/rest/item/<item_path>
http://<your_server_ip>:<your_backend_port>/rest/items/

### HTTP GET (e.g. normal access to the URL)

Gets the value of an item.

E.g. http://192.168.178.100:1234/rest/item/office.light returns "True" when the light is on.
E.g. http://192.168.178.100:1234/rest/items/ return the list of all available items.

### HTTP PUT

An HTTP PUT request to the URL sets a value of an item.

http://<your_server_ip>:<your_backend_port>/rest/item/<item_path>/<value>

E.g. http://192.168.178.100:1234/rest/item/office.light/0 turns of the light.

### General

In case of an error (e.g. item is not found), the plugin returns an error formatted as JSON:

{"Error": "No item with item path offifce.light found."}

In case a PUT request is successful, it returns a SUCCESS message as JSON.