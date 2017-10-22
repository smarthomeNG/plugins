# lirc

Send commands to lircd that sends IR-signals to any device that has an IR-interface.

## Requirements

At least a running and listening lircd with an IR-transmitter, optional an IR-receiver (for learning remotes) and the remote configuration
file of your remote control. You can create this file by learning your remote with irrecord or use an existing file from the remotes database.

For more information about lircd and the remotes database see http://www.lirc.org/html/lircd.html and http://lirc-remotes.sourceforge.net/


## Configuration

### plugin.yaml

```
lirc1:
    class_name: LIRC
    class_path: plugins.lirc
    instance: "livingroom"
    lirc_Host: "127.0.0.1"
#    lirc_Port: 6610

lirc2:
    class_name: LIRC
    class_path: plugins.lirc
    instance: "hifisystem"
    lirc_host: "192.168.1.10"
#    lirc_port: 6610
```

#### instance
This attribute is mandatory. You have to provide an unique identifier for every instance. That identifier will be used to relate the items to the
correct lircd.

#### lirc_host
This attribute is mandatory. You have to provide the IP adress or the hostname of the lircd.

#### lirc_port
You could specify a port to connect to. By default port 8765 is used.


### items.yaml

If the value of an item configured in items.yaml is set or updated the plugin will send an command to lircd to send the related lirc_key n times
whereby n means the value that has been assigned to the item. The plugin will reset the item to 0.
e.g. DVDLIVINGROOM_POWER ist set to 5  => lircd will send 5x POWER via IR
     DVDLIVINGROOM_POWER ist set to 1  => lircd will send 1x POWER via IR


```
LIRC:
    REMOTE_DVDLIVINGROOM:
        DVDLIVINGROOM_POWER:
            type: num
            lirc_instance: "livingroom"
            lirc_remote: "PHILIPSDVD"
            lirc_key: "POWER"
```

#### lirc_instance
the relation to an instance configured in plugin.yaml.

#### lirc_remote
the name of the remote. This name has to match the name of the remote in lircd.

#### lirc_key
the name of the key on the given remote. This name has to match the name of the key in lircd.

#### Example
```
LIRC:
    REMOTE_DVDLIVINGROOM:
        DVDLIVINGROOM_POWER:
            type: num
            lirc_instance: "livingroom"
            lirc_remote: "PHILIPSDVD"
            lirc_key: "POWER"

    REMOTE_RADIOOFFICE:
        TEVION_RCD9211_POWER:
            type: num
            lirc_instance: "hifisystem"
            lirc_remote: "TEVION_RCD9211"
            lirc_key: "POWER"
        TEVION_RCD9211_FUNCTION:
            type: num
            lirc_instance: "hifisystem"
            lirc_remote: "TEVION_RCD9211"
            lirc_key: "FUNCTION"
        TEVION_RCD9211_VOLUP:
            type: num
            lirc_instance: "hifisystem"
            lirc_remote: "TEVION_RCD9211"
            lirc_key: "VOLUP"
        TEVION_RCD9211_VOLDOWN:
            type: num
            lirc_instance: "hifisystem"
            lirc_remote: "TEVION_RCD9211"
            lirc_key: "VOLDOWN"
```

## Logging

You can configure the logger to see specific outputs of the plugin. That's helpfull when setting up the plugin. To see e.g. the debug-outputs of
the plugin you have to configure the logging.yaml file. The name of logger for every instance is created by "plugins.lirc" + "_instancename" 
e.g. plugins.lirc_livingroom or plugins.lirc_hifisystem


```
loggers:
    plugins.lirc_livingroom:
       level: DEBUG
```