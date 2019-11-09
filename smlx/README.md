# Sml

## Requirements

To use this plugin for reading data from your smart power meter hardware,
you need a serial interface connected to your hardware.

**Right now, the network connection of the original plugin is not working**

Most smart power meters have an optical (IR) interface on the front of
the case. It can be used to read data from the
power meter, e.g. by using an 
[optical reader](http://wiki.volkszaehler.org/hardware/controllers/ir-schreib-lesekopf)
connected to a USB port.

An RS485 interface of the Smartmeter (if applicable), connected via an RS485 to USB converter, 
is also working.

Implemented algorithms for calculating CRC are thankfully 
taken from [PyCRC](https://github.com/tpircher/pycrc/blob/master/pycrc/algorithms.py)

The existing SML Plugin was taken as a basis. Mainly, it now only establishes
communication with the hardware in given cycles.

## History

- 2012 Plugin created by O.Hinckel
- 2018-12-29 Implemented Data extraction and CRC check for read data. Before malfunctions could happen due to incomplete data sets
- 2019-10-13 Added way to change CRC parameters with plugin.yaml
- 2019-10-18 Modified parsing. Not only OBIS codes ending with 255 (FF) are parsed now.
             Added conversion of 'valTime' into actual time string. Introduced new attribute `date_offset` for plugin.yaml for actual time calculation.
             Modified debug messages for better readability.
- 2019-10-24 Fixed issue with calculation of actualTime. Fixed misinterpretation of Client-ID as OBIS code.               
- 2019-10-29 Added properties for Smartmeter status 

## Hardware

The plugin was tested with the following hardware:

   * Hager EHZ363Z5
   * Hager EHZ363W5
   * EHM eHZ-GW8 E2A 500 AL1
   * EHM eHZ-ED300L
   * Holley DTZ541 (2018 model with faulty CRC implementation)
   * Landis&Gyr E220

## Configuration

### plugin.yaml

```
smlx:
  class_name: Smlx
  class_path: plugins.smlx
  serialport: /dev/ttyUSB0
  # host: 192.168.2.1
  # port: 1234
  # device: raw | hex | <known-device>
  # for CRC generation
  # poly: 0x1021
  # reflect_in: True
  # xor_in: 0xffff
  # reflect_out: True
  # xor_in: 0xffff
  # swap_crc_bytes: False
  # date_offset: 0
```

The plugin reads data from smart power meter hardware by using a serial
interface (e.g. /dev/ttyUSB0) or by connecting to a host/port. It reads
messages using the SML (Smart Message Language) protocol. If you
want to know more about the protocol see [here](http://wiki.volkszaehler.org/software/sml).

Usually, the smart power meter hardware is sending status information
every few seconds via the interface, which is read by the plugin. This
status information, consisting of a SML_PublicOpen and SML_GetList message,
provides the current power status and details (e.g. total power consumed,
current power).

All status values retrieved by these messages have a unique identifier, which
is called [OBIS](http://de.wikipedia.org/wiki/OBIS-Kennzahlen) code. This can
be used to identify the meaning of the value returned.

Description of the attributes:

   * `serialport` - defines the serial port to use to read data from
   * `host` - instead of serial port you can use a network connection
   * `port` - additionally to the host configuration you can specify a port
   * `device` - specifies connected device to indicate pre-processing
   * `date_offset` - date and time of initial Smartmeter start-up in seconds since epoch

Additionally, the following attributes influence the CRC check of the data read from smartmeter:

   * `poly` - the polynomial for the CRC generation, default for SML is ``0x1021``
   * `reflect_in` - reflect the octets in the input, default is ``True``
   * `xor_in` - Initial value for XOR calculation, default is ``0xffff``
   * `reflect_out` - Reflect the octet of checksum before application of XOR value, default is ``True``
   * `xor_in` - XOR final CRC value with this value, default is ``0xffff``
   * `swap_CRC_bytes` - Swap bytes of calculated checksum prior to comparison with given checksum, Default is ``False``

It is usually not necessary to modify the CRC check default values, but at least one Smartmeter model
(a Holley DTZ541 from 2018) uses the wrong CRC calculation parameters. For this faulty Holley version,
use the following values:

```
HolleyDTZ541:
    plugin_name: smlx
    serialport: /dev/ttyUSB0          # your own serial port entered here 
    buffersize: 1500                  # the smartmeter sends up to 30 OBIS values, so the standard buffer size of 1024 is too small
    poly: 0x1021
    reflect_in: true
    xor_in: 0x0000
    reflect_out: true
    xor_out: 0x0000
    swap_crc_bytes: True
    date_offset: 1563173307           # date and time of initial start-up of YOUR smartmeter in seconds after epoch (Unix timestamp). See below.
```

The `device` attribute can be used to specify the connected device and the
kind of data delivery. Since different devices (e.g. when connecting the
power meter device via a LAN gateway) the data can be differently. Usually
when connecting a serial device directly to the power meter device the
raw data can be directly used with this plugin. Some other devices need
to be configured.

The following kinds of device types are supported:
   * `raw` - this is the default and means the raw SML binary data is
     send to the plugin
   * `hex` - can be used in case the SML data is encoded as hex string
   * or a known device name

In case you have a known device you can also specify this and the plugin
knows which data pre-processing is required. The following known devices
are supported:
   * `smart-meter-gateway-com-1` - The Smart Meter Gateway COM-1
     http://shop.co-met.info/artikeldetails/kategorie/Smart-Metering/artikel/smart-meter-gateway-com-1.html

The `date_offset` attribute defines the point in time of the Smartmeter
start-up after it was installed. It is an integer number and represents
the seconds since Unix epoch. It is used by the plugin to calculate the
actual point in time of an OBIS output (see additional attributes below). 
If you do not have the exact date and time, do the following:
Start plugin with active debugging and check Logs for `DEBUG plugins.smlx` lines.
Look at 'Entry' lines, containing 'valTime'. If you find a valTime which 
looks like [None, 40385206], note the integer number. On the very left of the line,
note the date and time of the logging output as well. Use a Unix time converter
like [this] https://www.unixtime.de/ and convert this date and time into a Unix timestamp.
Finally calculate: `date_offset` = 'Unix timestamp' - 'valTime'.
Example Logging entry:
"2019-10-18  09:34:35 DEBUG    plugins.smlx        Entry {'objName': '1-0:1.8.0*255', 'status': 1839364, 'valTime': [None, 8210754], 'unit': 30, 'scaler': -1, 'value': 560445, 'signature': None, 'obis': '1-0:1.8.0*255', 'valueReal': 56044.5, 'unitName': 'Wh', 'realTime': 'Fri Oct 18 09:34:21 2019'}"
Convert '2019-10-18  09:34:35' into Unix Timestamp. Result: 1571384075. 'valTime' = 8210754. `date_offset` = 1571384075 - 8210754 = 1563173321‬.
If your Smartmeter does not provide a valid 'valTime' (always 'valTime': None), `date_offset` is useless and can be omitted.

### items.yaml

You can assign a value retrieved by the plugin to some of your items by
using the OBIS identifier.

Here's a list of OBIS codes which may be useful:

   * 129-129:199.130.3*255 - Manufacturer
   * 1-0:0.0.9*255 - ServerId / serial number
   * 1-0:1.8.0*255 - Total kWh consumption (in)
   * 1-0:1.8.1*255 - Tariff 1 kWh consumption (in)
   * 1-0:1.8.2*255 - Tariff 2 kWh consumption (in)
   * 1-0:2.8.0*255 - Total kWh delivery (out)
   * 1-0:2.8.1*255 - Tariff 1 kWh delivery (out)
   * 1-0:2.8.2*255 - Tariff 2 kWh delivery (out)
   * 1-0:16.7.0*255 - Current Delivery Watt (out)

Instead of assigning the value for a given OBIS code, you can also assign meta
information for an OBIS code which is included in the data packet sent from
the smartmeter device.

For the complete list of properties for an OBIS code see below. They can be
assigned to items using the `sml_prop` attribute. In case one property is not
available or explicitely unset, it's value will be set to None.

The following properties are available:
   * `objName` - this is the OBIS code as string / binary data
   * `status` - a status value
   * `valTime` - the time of value (as seconds of unit start or as timestamp)
   * `unit` - identifies the value's unit (e.g. W, kWh, V, A, ...)
   * `scaler` - the scaler (10-factor shift) used to calculate the real value
   * `value` - the value
   * `signature` - the signature to protect the payload

The status of the Smartmeter is a binary string. The first 8 bits are always 0000 0100,
so not interesting. Each other bit has a special meaning and will be decoded into the
following attributes:
   * `statRun` - True: meter is counting, False: standstill
   * `statFraudMagnet` - True: magnetic manipulation detected, False: ok
   * `statFraudCover` - True: cover manipulation detected, False: ok
   * `statEnergyTotal` - Current flow total. True: -A, False: +A
   * `statEnergyL1` - Current flow L1. True: -A, False: +A
   * `statEnergyL2` - Current flow L2. True: -A, False: +A
   * `statEnergyL3` - Current flow L3. True: -A, False: +A
   * `statRotaryField` - True rotary field not L1->L2->L3, False: ok
   * `statBackstop` - True backstop active, False: backstop not active
   * `statCalFault` - True calibration relevant fatal fault, False: ok
   * `statVoltageL1` - True Voltage L1 present, False: not present
   * `statVoltageL2` - True Voltage L2 present, False: not present
   * `statVoltageL3` - True Voltage L3 present, False: not present
   
Additionally, the following attributes will be calculated and also be provided:
   * `obis` - the OBIS code as string
   * `valueReal` - the real value when including the scaler calculation
   * `unitName` - the name of the unit
   * `actualTime` - the valTime (seconds since Smartmeter installation) + offset (date & time of initial Smartmeter start-up) converted into an actual time string (e.g. 'Fri Oct 18 09:34:21 2019') 

#### sml_obis

This assigns the value for the given OBIS code to the item.

```yaml
sml_obis: 1-0:1.8.0*255
```

#### sml_prop

Use this to assign other information for an OBIS code to the item. When not
explicitely specified, it defaults to `valueReal`.

```yaml
sml_prop: unitName
```

#### Example

Here is a short sample configuration:

```yaml
power:

    home:

        total:
            type: num
            sml_obis: 1-0:1.8.0*255

        current:
            type: num
            sml_obis: 1-0:16.7.0*255

        unit:
            type: num
            sml_obis: 1-0:16.7.0*255
            sml_prop: unitName
```

### logic.yaml
Currently, there is no logic configuration for this plugin.


## Methods
Currently, there are no functions offered from this plugin.
