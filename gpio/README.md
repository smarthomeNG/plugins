# GPIO

## Changelog
1.0 
- initial release

1.0.1
- Changed event detection from constant polling to GPIO.add_event_detect

## Requirements

RPi.GPIO Python module

Install it with:
sudo pip3 install RPi.GPIO --upgrade

## Supported Hardware

Raspberry Pi all versions (tested on Raspberry Pi 1 revision 2)

## Configuration

### plugin.conf (deprecated) / plugin.yaml

<pre>
[GPIO]
   class_name = Raspi_GPIO
   class_path = plugins.gpio
#   mode = BOARD
</pre>

<pre>
GPIO:
   class_name: Raspi_GPIO
   class_path: plugins.gpio
#   mode: BOARD
</pre>

#### `mode`
Define the GPIO PIN Mode that you use to declare the pin numbers. If not set, default is BOARD

Possible modes: BOARD or BCM. More information can be found here: 
http://raspberrypi.stackexchange.com/questions/12966/what-is-the-difference-between-board-and-bcm-for-gpio-pin-numbering


### items.conf (deprecated) / items.yaml

#### gpio_in

Define the pin number of your Raspberry Pi that should be read, i.e. where a sensor is attached. Beware that the number has to follow the rules of the "mode" you have defined in the plugin.conf (Board or BCM).

#### gpio_out

Define the pin number of your Raspberry Pi that should be written, i.e. where a LED is attached. Beware that the number has to follow the rules of the "mode" you have defined in the plugin.conf (Board or BCM). The Output-Pin will also automatically be read by the plugin as Input.

#### Example

<pre>
# .conf
[item1]
    type = bool
    visu_acl = ro
    gpio_in = 10
[item2]
    type = bool
    visu_acl = rw
    gpio_out = 13
</pre>

<pre>
# .yaml
item1:
    type: bool
    visu_acl: ro
    gpio_in: 10
item2:
    type: bool
    visu_acl: rw
    gpio_out: 13
</pre>