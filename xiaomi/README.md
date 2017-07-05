# Xiaomi

Version 0.1

## Requirements
This plugin requires lib miflora. You can install this lib with:

```
sudo pip3 install miflora --upgrade
```

Due to the miflora package, currently all firmwares up to 2.6.6 are supported.

Forum thread to the plugin: https://knx-user-forum.de/forum/supportforen/smarthome-py/1027133-plugin-xiaomi-mi-plant-flowers-tester-light-monitor

## Supported Hardware

* Xiaomi Mi Plant Flowers Tester Light Monitor

## Configuration

### plugin.conf (deprecated) / plugin.yaml

Please provide a plugin.conf snippet for your plugin with ever option your plugin supports. Optional attributes should be commented out.

```
[xiaomi]
    class_name = Xiaomi
    class_path = plugins.xiaomi
    bt_addr = C4:7C:7E:21:F3:2B
    cycle = 300
    instance = xiaomi
```

```yaml
xiaomi:
    class_name: Xiaomi
    class_path: plugins.xiaomi
    bt_addr: C4:7C:7E:21:F3:2B
    cycle: 300
    instance: xiaomi
```

#### Attributes
  * `bt_addr`: The Bluetooth address of your xiaomi plant sensor. Find e.g. with hcitool lescan
  * `cycle`: Cycle interval for data retrieval
  * `instance`: Instance name in case multi-instance use is needed (one instance can handle one sensor)

### items.conf (deprecated) / items.yaml

#### xiaomi_data_type

The xiaomi_data_type is needed to provide information to the plugin, which values shall be stored in the item.
Possible xiaomi_data_type's are temperature, light, moisture, conductivity, name, firmware and battery.

#### Example

items/my.conf
```
[plants]
    [[sensor_office]]
        [[[temperature]]]
            type = num
            xiaomi_data_type@xiaomi = 'temperature'
        [[[light]]]
            type = num
            xiaomi_data_type@xiaomi = 'light'
        [[[moisture]]]
            type = num
            xiaomi_data_type@xiaomi = 'moisture'
        [[[conductivity]]]
            type = num
            xiaomi_data_type@xiaomi = 'conductivity'
        [[[name]]]
            type = str
            xiaomi_data_type@xiaomi = 'name'
        [[[firmware]]]
            type = str
            xiaomi_data_type@xiaomi = 'firmware'
        [[[battery]]]
            type = num
            xiaomi_data_type@xiaomi = 'battery'
```

items/my.yaml
```yaml
plants:

    sensor_office:

        temperature:
            type: num
            xiaomi_data_type@xiaomi: temperature

        light:
            type: num
            xiaomi_data_type@xiaomi: light

        moisture:
            type: num
            xiaomi_data_type@xiaomi: moisture

        conductivity:
            type: num
            xiaomi_data_type@xiaomi: conductivity

        name:
            type: str
            xiaomi_data_type@xiaomi: name

        firmware:
            type: str
            xiaomi_data_type@xiaomi: firmware

        battery:
            type: num
            xiaomi_data_type@xiaomi: battery
```
