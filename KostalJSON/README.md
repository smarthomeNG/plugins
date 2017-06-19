# KOSTAL

# Requirements

This plugin is designed to retrieve data from a [KOSTAL](http://www.kostal-solar-electric.com/) inverter module (e.g. PIKO inverters) with UI-Interface Version >6.
PIKO - Inverters with UI-Firmware <6 should work with the KOSTAL plugin.
Since UI-version 6 json-format is supported

Tested with Kostal Piko 3.0 (single phase)  UI-Version 06.20
dc-line 2, ac line 2 and ac line 3 values unchecked/untested

## Supported Hardware

Is currently working with the following KOSTAL inverter modules:

  * KOSTAL PIKO 3.0
  (should work with all KOSTAL PIKO inverters with UI-Firmwareversion >6)

# Configuration

## plugin.conf

The plugin can be configured like this:

<pre>
[Kostal-PV]
   class_name = KostalJSON
   class_path = plugins.KostalJSON
   ip = 192.168.1.21
   cycle = 5
</pre>

This plugin retrieves data from a KOSTAL inverter module of a solar energy
plant.

The data retrieval is done by establishing a network connection to the 
inverter module and retrieving the status via a HTTP/JSON request.

You need to configure the host (or IP) address of the inverter module.

The cycle parameter defines the update interval and defaults to 300 seconds.

## items.conf

### Example

Example configuration which shows the current status and the current, total and
daily power. Additionally it shows the volts and watts for the phases.

<pre>
# items/my.conf
[solar]
    [[status]]
        type = str
        kostal = operation_status
    [[dcpower]]
        type = num
        kostal = dctot_w
    [[dc1_v]]
        type = num
        kostal = dc1_v
    [[dc1_a]]
        type = num
        kostal = dc1_a
    [[dc1_w]]
        type = num
        kostal = dc1_w
    [[dc2_v]]
        type = num
        kostal = dc2_v
    [[dc2_a]]
        type = num
        kostal = dc2_a
    [[dc2_w]]
        type = num
        kostal = dc2_w
    [[actot_w]]
        type = num
        kostal = actot_w
    [[actot_cos]]
        type = num
        kostal = actot_cos
    [[actot_limitation]]
        type = num
        kostal = actot_limitation
    [[ac1_v]]
        type = num
        kostal = ac1_v
    [[ac1_a]]
        type = num
        kostal = ac1_a
    [[ac1_w]]
        type = num
        kostal = ac1_w
    [[ac2_v]]
        type = num
        kostal = ac2_v
    [[ac2_a]]
        type = num
        kostal = ac2_a
    [[ac2_w]]
        type = num
        kostal = ac2_w
    [[ac3_v]]
        type = num
        kostal = ac3_v
    [[ac3_a]]
        type = num
        kostal = ac3_a
    [[ac3_w]]
        type = num
        kostal = ac3_w
    [[yield_day_wh]]
        type = num
        kostal = yield_day_wh
    [[yield_tot_kwh]]
        type = num
        kostal = yield_tot_kwh
    [[operationtime_h]]
        type = num
        kostal = operationtime_h
</pre>

## logic.conf

No logic related stuff implemented.

# Methods

No methods provided currently.

