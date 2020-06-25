# Tellstick

This plugin is design for TellStick and TellStick Duo RF Transmitter


## Requirements

You need to install ``telldus-core`` and configure it (http://developer.telldus.com/wiki/TellStickInstallationSource)

After installing you need to configure your devices in ``/etc/tellstick.conf`` (http://developer.telldus.com/wiki/TellStick_conf)   

## Configuration

### plugin.yaml

```yaml
tellstick:
    class_name: Tellstick
    class_path: plugins.tellstick
```

### item.yaml

#### ts_id

id of the device in /etc/tellstick.conf

#### Example :

```yaml
kitchen:
    light:
        type: bool
        ts_id: 1
```
