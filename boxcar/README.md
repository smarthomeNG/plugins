# Boxcar Notification Service

## Requirements

You need to register at http://boxcar.io and get a free Boxcar Account.
In addition you need the free Boxcar App from Apple Appstore on your iOS Device.

## Supported Hardware

* Hardware supported by Boxcar.io Service (ATM only iOS, Android coming soon - perhaps)

## Configuration

### plugin.yaml

The following snippet can be used within the plugin.yaml.

```
bc:
    class_name: Boxcar
    class_path: plugins.boxcar
    apikey: abcdefghij123456    # Get it from your Boxcar Account
    email: your@mail.org        # Registered with Boxcar
```

Attributes apikey and email need to be set.

### items.yaml

Not needed yet.

### logic.yaml

To push a message to your iOS Device just call

```
sh.bc('House at Tulpenstrasse',' Waschmaschine fertig!')
```

``sh`` is the main smarthome instance.
``bc`` is the name of the plugin instance (defined in plugins.yaml).

Two parameters with text to be send are supported.
If you only want to send one string, set the second string to an empty string.
