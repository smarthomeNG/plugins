# Sample Plugin <- put the name of your plugin here

#### Version 1.x.y

Describe the purpose of the plugin right here. (What is the plugin good for?)

## Change history

If you want, you can add a change history here:

### Changes Since version 1.x.x

- Fixed this

### Changes Since version 1.x.w

- Added that feature


## Requirements

List the requirements of your plugin. Does it need special software or hardware?

### Needed software

* list
* the
* needed
* software

Including Python modules and SmartHomeNG modules

### Supported Hardware

* list
* the
* supported
* hardware

## Configuration

### plugin.yaml

Please provide a plugin.yaml snippet for your plugin with ever option your plugin supports. Optional attributes should be commented out.

```yaml
My:
   class_name: MyPlugin
   class_path: plugins.myplugin
   host: 10.10.10.10
#   port: 1010
```

Please provide a description of the attributes.
This plugin needs an host attribute and you could specify a port attribute which differs from the default '1010'.

### items.yaml

List and describe the possible item attributes.

#### my_attr

Description of the attribute(s)...

#### my_attr2

#### Example

Please provide an item configuration with every attribute and usefull settings.

```yaml
# items/my.yaml

someroom:
    mydevice:
        type: bool
        my_attr: setting
```

### logic.yaml
If your plugin support item triggers as well, please describe the attributes like the item attributes.


## Methods
If your plugin provides methods for logics. List and describe them here...

### method1(param1, param2)
This method enables the logic to send param1 and param2 to the device. You could call it with `sh.my.method1('String', 2)`.

### method2()
This method does nothing.
