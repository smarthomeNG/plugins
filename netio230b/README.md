# NetIO230B

## Requirements

## Supported Hardware

* KOUKAAM NETIO230B

## Configuration

### plugin.yaml

```yaml
netio230b0:
    class_name: NetIO230B
    class_path: plugins.netio230b
    address: 10.0.0.10
    user: username
    password: password
#   netio_id: 1
```

Description of the attributes:

* __address__: ip address of the netio230b power distribution
* __user__: username needed for login
* __password__: password needed for login
* __netio_id__: optional, set id if you want to control more than one device

### items.yaml

There are two types of items in this plugin. Items to control the state of the power
distribution (control item) and items to detect an error (error item). The error item
is used to detect wether it is not possible to communicate with the device.

* __netio_id__: Contains the device id specified in plugin.yaml. This attribute is optional for the control item.

* __netio_port__: Specify one of the 4 ports of the power distribution, starting with 0. This attribute must not
be set for the error item.

#### Example

```yaml
someroom:

    control0:
        type: bool
        netio_id: 1
        netio_port: 0

    control1:
        type: bool
        netio_port: 3

    control2:
        type: bool
        netio_id: 2
        netio_port: 2

    error1:
        type: bool
        netio_id: 1

    error2:
        type: bool
        netio_id: 2
```

* __control0__: item to control port 0 of netio230b device with id 1
* __control1__: item to control port 3 of netio230b device with id 1 (default for netio_id is 1)
* __control2__: item to control port 2 of netio230b device with id 2
* __error1__: item to get error state of netio230b device with id 1
* __error2__: item to get error state of netio230b device with id 2

## logic.yaml

The state of a port can be changed by setting the belonging item to True or False. For the example above mentioned:

```python
sh.someroom.control0(True)
sh.someroom.control1(False)
```
