# Nuki
# Info
Plugin for integrating [Nuki Smartlock](https://nuki.io/de/smart-lock/) into smarthome.py facilitating triggering lock actions and getting status information from it.
# Requirements
You need a [Nuki Bridge](https://nuki.io/de/bridge/) which is already paired with your Nuki Smartlock(s).
# Configuration
## plugin.conf
```
[nuki]
    class_name = Nuki
    class_path = plugins.nuki
    bridge_ip = 192.168.1.10
    bridge_port = 8080
    bridge_api_token = q1W2e3
    
    # bridge_callback_ip = 192.168.0.2
    # bridge_callback_port = 8090
```

### Attributes
* `bridge_ip` : IP address of the Nuki Bridge
* `bridge_port` : Port number of the Nuki Bridge
* `bridge_api_token` : Token for authentification of the API connection
* `bridge_callback_ip`: IP address of the TCP dispatcher which is handling the Bridge callback requests. By default, the local IP address is used
* `bridge_callback_port` : Port number of the TCP dispatcher. By default, port number 8090 is used.

*This information can be set via the Nuki App

## item.conf

To get the Nuki functionality working, an item has to be type of `num` and  must implement two attributes,
`nuki_id` and `nuki_trigger`.

### nuki_id
This attribute connects the related item with the corresponding Nuki Smart Lock. 
The `nuki_id` can be figured out via the REST API of the Nuki Bridge (see API documentation) or by just (re)starting 
SmarthomeNG with the configured Nuki plugin. The `name` and the `nuki_id` of all paired Nuki Locks will be written to 
the log file of SmarthomeNG.

### nuki_trigger

There are three types of nuki triggers, `action`, `state` and `battery`. An item can only have one trigger 
attribute at once.

#### action
If you declare an item with the attribute `nuki_trigger = action` you can send actions to your Nuki lock. Below you
can find a list of possible lock actions: 

* 1     (unlock)
* 2     (lock)
* 3     (unlatch)
* 4     (lock 'n' go)
* 5     (lock 'n' go with unlatch)

If you set the the items value to one of this numbers, the corresponding lock action will be triggered. 


#### state
If you declare an item with the attribute `nuki_trigger = state`, this item will be set to the actual lock state,
whenever these lock state was changed. Find the list with the possible values below:

* 0     (uncalibrated)
* 1     (locked)
* 2     (unlocking)
* 3     (unlocked)
* 4     (locking)
* 5     (unlatched)
* 6     (unlatched (lock 'n' go))
* 7     (unlachting)
* 254   (motor blocked)
* 255   (undefined)



#### battery
If you declare an item with the attribute `nuki_trigger = state`, this item holds the actual battery state of your
Nuki lock.

* 0     (Batteries are good. No need to replace it.)
* 1     (Batteries are low. Please replace as soon as possible.)


## Example:
```
[MyNukiLock]

    [[MyLockState]]
        type = num
        nuki_id = 123456789
        nuki_trigger = state

    [[MyLockBattery]]
        type = num
        nuki_id = 123456789
        nuki_trigger = battery

    [[MyLockAction]]
        type = num
        nuki_id = 123456789
        nuki_trigger = action
        enforce_updates = true
```