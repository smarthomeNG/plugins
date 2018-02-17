# KNX

Send and receive messages to and from knx bus via knxd connection.
By default the plugin connects on 127.0.0.1 port 6720 but it can be changed in plugin.conf.

## Requirements

This plugin needs a running eibd or knxd.

## Configuration

Sample files here are given in ``yaml`` (starting with SHNG 1.3) and ``conf`` (deprecated as of SHNG 1.3) format.

### plugin.yaml / plugin.conf (deprecated)

```yaml
knx:
    class_name: KNX
    class_path: plugins.knx
    # host: 127.0.0.1
    # port: 6720
    # send_time: 600    # update date/time every 600 seconds, default none
    # time_ga: 1/1/1    # default none
    # date_ga: 1/1/2    # default none
    # busmonitor: 'False'
    # readonly: 'False'
```

```
[knx]
   class_name = KNX
   class_path = plugins.knx
#   host = 127.0.0.1
#   port = 6720
#   send_time = 600 # update date/time every 600 seconds, default none
#   time_ga = 1/1/1 # default none
#   date_ga = 1/1/2 # default none
#   busmonitor = False
#   readonly = False
```

#### Attributes

* `host` : eibd or knxd hostname (default: 127.0.0.1) 
* `port` : eibd or knxd port (default: 6720) 
* `send_time` : interval to send time and date to the knx bus
* `time_ga` : groupadress to send a timestamp to the knx bus
* `date_ga` : groupadress to send a date to the knx bus
* `busmonitor` : Values: (True, False, 'logger'). If you set `busmonitor` to True, every KNX packet will be logged to the default plugin logger.                
  Set parameter to `busmonitor = 'logger'` to log all knx messages to a separate logger 'knx_busmonitor'.
  In `logging.yaml` you can configure a formatter, handler and a logger to write all bus messages to a separate file.
                 <pre>
                 formatters:
                     busmonitor:
                        format: '%(asctime)s;%(message)s'
                        datefmt: '%Y-%m-%d %H:%M:%S'
                 handlers:
                     busmonitor_file:
                        class: logging.handlers.TimedRotatingFileHandler
                        formatter: busmonitor
                        when: midnight
                        backupCount: 7
                        filename: ./var/log/knx_busmonitor.log
                 loggers:
                     knx_busmonitor:
                        level: INFO
                        handlers: [busmonitor_file]
                </pre>
                With this configuration all bus monitor messages are writen to `./var/log/knx_busmonitor.log`
            False disable the logging until you start SmartHomeNG in debug modus.

* `readonly` :  If you set `readonly` to True, the plugin only read the knx bus and send no group message to the bus.
* `enable_stats` : if you set this to True then the statistic functions are enabled to collect data (see below)

If you specify a `send_time` intervall and a `time_ga` and/or `date_ga` the plugin sends the time/date every cycle seconds on the bus.

### items.conf

#### knx_dpt

This attribute set the datapoint type used for conversion from Bus format to internal SmartHomeNG format. It is mandatory. 
If you don't provide one the item will be ignored.
The DPT has to match the type of the item!

The following datapoint types are supported:

```
|  DPT        |  Data         |  Type    |  Values
| ----------- | ------------- | -------- | ----------------------------------
|  1          |  1 bit        |  bool    |  True or False
|  2          |  2 bit        |  list    |  [0, 0] - [1, 1]
|  3          |  4 bit        |  list    |  [0, 0] - [1, 7]
|  4.002      |  8 bit        |  str     |  1 character (8859_1) e.g. ‘c’
|  5          |  8 bit        |  num     |  0 - 255
|  5.001      |  8 bit        |  num     |  0 - 100
|  6          |  8 bit        |  num     |  -128 - 127
|  7          |  2 byte       |  num     |  0 - 65535
|  8          |  2 byte       |  num     |  -32768 - 32767
|  9          |  2 byte       |  num     |  -671088,64 - 670760,96
|  10         |  3 byte       |  foo     |  datetime.time
|  11         |  3 byte       |  foo     |  datetime.date
|  12         |  4 byte       |  num     |  0 - 4294967295
|  13         |  4 byte       |  num     |  -2147483648 - 2147483647
|  14         |  4 byte       |  num     |  4-Octet Float Value IEEE 754
|  16         |  14 byte      |  str     |  14 characters (ASCII)
|  16.001     |  14 byte      |  str     |  14 characters (8859_1)
|  17         |  8 bit        |  num     |  Scene: 0 - 63
|  20         |  8 bit        |  num     |  HVAC: 0 - 255
|  24         |  var          |  str     |  unlimited string (8859_1)
|  232        |  3 byte       |  list    |  RGB: [0, 0, 0] - [255, 255, 255]
```


If you are missing one, open a bug report or drop me a message in the knx user forum.

#### knx_send
You could specify one or more group addresses to send updates to. Item update will only be sent if the item is not changed via KNX.

#### knx_status
Similar to knx_send but will send updates even for changes vie KNX if the knx_status GA differs from the destination GA.

#### knx_listen
You could specify one or more group addresses to monitor for changes.

#### knx_init
If you set this attribute, SmartHomeNG sends a read request to specified group address at startup and set the value of the item to the response.
It implies 'knx_listen'.

#### knx_cache
If you set this attribute, SmartHomeNG tries to read the cached value for the group address. If it fails it sends a read request to specified group address at startup and set the value of the item to the response.
It implies 'knx_listen'.

#### knx_reply
Specify one or more group addresses to allow reading the item value.

#### knx_poll
Specify the ga to poll and the time interval in seconds for an automated query of KNX.
This may be used for actors or sensors that do no support a regular sending of values themselves.

#### Example


```yaml
living_room:

    light:
        type: bool
        knx_dpt: 1
        knx_send: 1/1/3
        knx_listen:
          - 1/1/4
          - 1/1/5
        knx_init: 1/1/4

    temperature:
        type: num
        knx_dpt: 9
        knx_send: 1/1/6
        knx_reply: 1/1/6
        ow_id: 28.BBBBB20000    # see 1-Wire plugin
        ow_sensor: temperature    # see 1-Wire plugin

    window:
        type: bool
        knx_dpt: 1
        knx_poll: 1/1/9 | 60
```

```
[living_room]
    [[light]]
        type = bool
        knx_dpt = 1
        knx_send = 1/1/3
        knx_listen = 1/1/4 | 1/1/5
        knx_init = 1/1/4

    [[temperature]]
        type = num
        knx_dpt = 9
        knx_send = 1/1/6
        knx_reply = 1/1/6
        ow_id = 28.BBBBB20000 # see 1-Wire plugin
        ow_sensor = temperature # see 1-Wire plugin

    [[window]]
        type = bool
        knx_dpt = 1
        knx_poll = 1/1/9
```

### logic.conf

You could specify the `knx_listen` and `knx_reply` attribute to every logic in your logic.conf. The argument could be a single group address and dpt or a list of them.

```yaml
logic1:
    knx_dpt: 9
    knx_listen: 1/1/7

logic2:
    knx_dpt: 9
    knx_reply:
      - 1/1/8
      - 1/1/8
```

```
[logic1]
    knx_dpt = 9
    knx_listen = 1/1/7

[logic2]
    knx_dpt = 9
    knx_reply = 1/1/8 | 1/1/8
```

If there is a packet directed to the according group address, SmartHomeNG would trigger the logic and will pass the payload (via the trigger object) to the logic.

In the context of the KNX plugin the trigger dictionary consists of the following elements:

* trigger['by']         protocol ('KNX')
* trigger['source']     PA (physical adress of the KNX packet source) 
* trigger['value']      payload

## Functions

### encode(data, dpt)

This function encodes your data according to the specified datapoint.
``data = sh.knx.encode(data, 9)``

### groupwrite(ga, data, dpt)

With this function you could send the data to the specified group address.
``sh.knx.groupwrite('1/1/10', 10.3, '9')``

### groupread(ga, cache=False)

This function triggers a read request on the specified group address. Since KNX is event driven **it will not return the received value**!

### send_time(time_ga, date_ga)

This function sends the current time and/or date to the specified group address.

```python
sh.knx.send_time('1/1/1', '1/1/2') # send the time to 1/1/1 and the date to 1/1/2
sh.knx.send_time('1/1/1') # only send the time to 1/1/1
sh.knx.send_time(data_ga='1/1/2') # only send the date to 1/1/2
```

Hint: instead of this function you could use the plugin attribute 'send_time' as described above.

## Statistics

The statistics functions were introduced to watch what is happening on the KNX.
Mainly it is recorded which physical device sends data by write or response or requests data
by read operation.
Whenever such a telegram is received, it is recorded 
- which physical device sended the request (originator)
- which kind of request (read, write, response)
- target group address affected
- a counter for the specific kind of request (read, write, response) is increased.
    
With an additional logic these statistics can be requested from the plugin and examined for
- unknown group addresses which are not known to either ETS or to SmartHomeNG
- unknown physical addresses which are new and unexpected
- adresses that do not react upon requests
- adresses that can't satisfy cache requests

A sample logic that takes an ``esf`` file from ``ETS export as OPC`` to parse the known group addresses is provided as ``Check_KNX.py``
The result of the logic will be placed in the same directory as the ``esf`` file but with ``.txt`` suffix.

You will need to copy the script into your ``logics`` directory and add these lines to your ``ets/logic.yaml`` or ``etc/logic.conf`` (deprecated as of SmartHomeNG 1.3):

```yaml
Check_KNX:
    filename: Check_KNX.py
```

```
[Check_KNX]
    filename = Check_KNX.py
```

