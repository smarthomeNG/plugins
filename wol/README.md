# WakeOnLan

## Requirements

none

## Configuration

### plugin.yaml

```yaml
wakeonlan:
    plugin_name: wol
```

### items.yaml

```yaml
wakeonlan_item:
    type: bool
    wol_mac: 01:02:03:04:05:06
    # wol_ip: 1.2.3.4
```

#### wol_mac

This attribute is mandatory. You have to provide the mac address for the host to wake up. Type of separators are unimportant. you can use:

```yaml
wol_mac: 01:02:03:04:05:06
```

or

```yaml
wol_mac: 01-02-03-04-05-06
```

or don't use any separators:

```yaml
wol_mac: 010203040506
```

#### wol_ip
This attribute is optional. You have to provide the ip address of the host to wake up when waking up hosts in different subnets (not the same broadcast domain).
```yaml
wol_ip: 1.2.3.4
```
