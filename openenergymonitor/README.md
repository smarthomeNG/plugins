# OpenEnergyMonitor

This plugins uploads values to an OpenEnergyMonitor instance.

## Requirements

This plugin needs an OpenEnergyMonitor account. This can be on [emoncms.org](http://emoncms.org/) or a custom installation.

## Configuration

### plugin.yaml

```yaml
OpenEnergyMonitor:
   class_name: OpenEnergyMonitor
   class_path: plugins.openenergymonitor
   url:
    - http://emoncms.org
    - http://localhost/emoncms
   timeout: 4
   writeApiKey: ...
   inputKey: ...
   nodeId: 1
```

By setting the timeout, you can specify an amount of seconds, after which the plugin will run into a timeout, if the remote service is not responding.

You need to specify your write API key and a default inputKey. The default input key can be overridden later on items.

The node ID can be adjusted to match your needs

### items.yaml

In order to upload a value, items need add **OpenEnergyMonitor** as subitem on an item.

```yaml
temperatur:
   name: Temperatur
   type: num
   OpenEnergyMonitor: True
   inputKey: TemperaturWohnzimmer
   nodeId: 3
```

The inputKey and nodeId values are optional. If not specified, the default value from the plugin.yaml is used.
