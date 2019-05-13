# Artnet

## Requirements

You need a device understanding Artnet.
I suggest to use the software OLA http://www.opendmx.net/index.php/Open_Lighting_Architecture to translate the ArtNet packets into DMX Signals.
Alternatively you can use any Art-Net to DMX Adapter
OLA supports most USB -> DMX Adapters available at the moment.

## Supported Hardware

* Hardware supported by OLA. See Link above.

## Configuration

### plugin.yaml

```yaml
artnet1:
    class_name: ArtNet
    class_path: plugins.artnet
    artnet_universe: 0
    artnet_net: 0
    artnet_subnet: 0
    ip: 192.168.159.216
    port: 6454
    update_cycle: 120
    instance: keller
```

#### Attributes
  * `artnet_universe`: Optional login information
  * `artnet_net`: Required login information
  * `artnet_subnet`: Hostname or ip address of the FritzDevice.
  * `ip`: Port of the FritzDevice, typically 49433 for https or 49000 for http
  * `port`: True or False => True will add "https", False "http" to the URLs in the plugin
  * `update_cycle`: timeperiod between two update cycles. Default is 300 seconds.
  * `instance`: Name of this plugin instance (e.g. above: keller)

### items.yaml

#### artnet_address
This attribute assigns an item to the respective artnet-address (DMX channel)

### Example:
```yaml
    lightbar:
        red:
            artnet_address@keller: 1
        green:
            artnet_address@keller: 2
        blue:
            artnet_address@keller: 3
```

### logic.yaml
Notice: First DMX channel is 1! Not 0!

To send DMX Data to the universe set in plugin.yaml you have 3 possibilities:

#### 1) Send single value
``sh.artnet1(<DMX_CHAN>, <DMX_VALUE>)``

Sets DMX_CHAN to value DMX_VALUE.

Example: ``sh.artnet1(12,255)``
If channels 1-11 are already set, they will not change.
If channels 1-11 are not set till now, the will be set to value 0.
This is needed because on a DMX bus you can not set just one specific channel.
You have to begin at first channel setting your values.

#### 2) Send a list of values starting at channel
``sh.artnet1(<DMX_CHAN>, <DMX_VALUE_LIST>)``
Sends <DMX_VALUE_LIST> to DMX Bus starting at <DMX_CHAN>

Example:
``sh.artnet1(10,[0,33,44,55,99])``
If channels 1-9 are already set, they will not change.
If channels 1-9 are not set till now, the will be set to value 0.
This is needed because on a DMX bus you can not set just one specific channel.
You have to begin at first channel setting your values.
Values in square brackets will be written to channel (10-14)

#### 3) Send a list of values

``sh.artnet1(<DMX_VALUE_LIST>)``

Sends <DMX_VALUE_LIST> to DMX Bus starting at channel 1

This is nearly the same as 2) but without starting channel.

Example:

``sh.artnet1([0,33,44,55,99])``
Values in Square brackets will be written to channel (1-5)
