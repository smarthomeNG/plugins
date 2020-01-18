# Snmp

## Requirements

To use this plugin to query information via SNMP, you need to install puresnmp.
This python package is in requirements.



## History

- 2020 Plugin created by M.Wenzel


## Hardware

The plugin was tested with the following hardware:

   * QNAP NAS TS-251
   * Raspberry Pi 3B

## Configuration

### plugin.yaml

```
nas:
    plugin_name: snmp
    cycle: 300
    snmp_host: 192.168.2.9
    snmp_community: public
    instance: nas1
```

The plugin queries information via the snmp from other computers using the oid.
If you want to know more about the feature see [here](https://de.wikipedia.org/wiki/Management_Information_Base).

Description of the attributes:

   * `cycle` - defines the cyclytime for queries
   * `snmp_host` - defined the computer to the queried
   * `snmp_port` - defined the port to the queried
   * `snmp_community` - defines the community for queried information

### items.yaml

You can assign a value retrieved by the plugin to some of your items by
using the OID identifier.


#### snmp_oid

This assigns the value for the given OID code to the item.

```yaml
snmp_oid: '1.3.6.1.4.1.24681.1.2.5.0'
```

#### snmp_prop

Use this to assign the response to be handled as string or value

```yaml
snmp_prop: value
```

#### Example

Here is a short sample configuration:

```yaml
nas:

	cpu_temp:
		name: CPU-Temperatur in °C
		type: num
		snmp_oid: '1.3.6.1.4.1.24681.1.2.5.0'
		snmp_prop: 'value'
		
	cpu_usage:
		name: CPU-Auslastung [0-1]
		type: num
		snmp_oid: '1.3.6.1.4.1.24681.1.2.1.0'
		snmp_prop: 'value'
```

### logic.yaml
Currently, there is no logic configuration for this plugin.


## Methods
Currently, there are no functions offered from this plugin.
