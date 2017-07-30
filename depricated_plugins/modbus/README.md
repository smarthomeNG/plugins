# Modbus Plugin

## Requirements

Not specified so far but the ``pymodbus`` module seems to be needed

## Supported Hardware

Waterkotte Sole-WP with RTU Modbus 

## Configuration

### plugin.conf

```
[modbus]
   class_name = Modbus
   class_path = plugins.modbus
   serialport = 
   # slave_address = 1
   # update_cycle = 30
```

The ``serialport`` needs to be given for communication with the modbus device.

Optional are ``slave_address`` and ``update_cycle`` for the query time in seconds


### items.conf

There are three attributes:

#### modbus_regaddr

Address of register

#### modbus_datatype

Datatype

#### modbus_datamask

Mask to isolate date

#### modbus_datatype

#### Example

Please provide an item configuration with every attribute and usefull settings.

```
# items/my.conf

[someroom]
    [[mydevice]]
        type = bool
        my_attr = setting
```

### logic.conf
If your plugin support item triggers as well, please describe the attributes like the item attributes.


## Methods
If your plugin provides methods for logics. List and describe them here...

### method1(param1, param2)
This method enables the logic to send param1 and param2 to the device. You could call it with `sh.my.method1('String', 2)`.

### method2()
This method does nothing.
