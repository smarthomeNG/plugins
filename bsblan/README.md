# Plugin for BSB-Lan-Adapter

#### Version 1.0.0

This plugin connects your BSB-LPB-LAN-Adapter (https://github.com/1coderookie/BSB-LPB-LAN/) to SmarthomeNG.
BSB-LPB-LAN is a LAN Interface for Boiler-System-Bus (BSB) that enables you to control heating systems from Elco or 
Brötje and similar Systems. 
- read out all available Boiler data.

## Change history

### Changes Since version 1.x.x

- No Changes so far


### Requirements needed software

* Python > 3.7
* SmarthomeNG >= 1.7.2


## Configuration

### 1) /smarthome/etc/plugin.yaml

Enable the plugin in plugin.yaml and type in the adapters IP address.

```yaml
bsblan:
    plugin_name: bsblan
    bsblan_ip: 192.168.xxx.xxx
```

### 2) /smarthome/items/bsblan.yaml

Create an item and add the parameters you want to get from BSB-LAN.
A full list of supported parameters you can get from the BSB-LAN-Adapter Web interface (http://192.168.xxx.xxx/K)

```yaml
bsblan:
    Vorlauftemperatur_HK1:
        type: num
        bsb_lan: 8743
        visu_acl: ro
        descr:
            type: str
    Trinkwassertemperatur:
        type: num
        bsb_lan: 8830
        visu_acl: ro
        descr:
            type: str
    Vorlauftemperatur_HK2:
        type: num
        bsb_lan: 8773
        visu_acl: ro
        descr:
            type: str
    Heizkreispumpe_HK2_Status:
        type: num
        bsb_lan: 8760
        visu_acl: ro
        descr:
            type: str
    Status_Brenner:
        type: num
        bsb_lan: 8009
        visu_acl: ro
        descr:
            type: str
    Trinkwasserdurchfluss:
        type: num
        bsb_lan: 8860
        visu_acl: ro
        descr:
            type: str
    Kesseltemperatur:
        type: num
        bsb_lan: 8310
        visu_acl: ro
        descr:
            type: str
    Kesselrücklauftemperatur:
        type: num
        bsb_lan: 8314
        visu_acl: ro
        descr:
            type: str
    Wasserdruck:
        type: num
        bsb_lan: 8327
        visu_acl: ro
        descr:
            type: str
```








