# KOSTAL

VERSION = "1.3.1"

# Requirements

This plugin is designed to retrieve data from a [KOSTAL](http://www.kostal-solar-electric.com/) inverter module (e.g. PIKO inverters)
Since UI-version 6 json-format is supported

Tested with Kostal Piko 3.0 (single phase)  UI-Version 06.20
dc-line 2, ac line 2 and ac line 3 values unchecked/untested

## Supported Hardware

Is currently working with the following KOSTAL inverter modules:

  * KOSTAL PIKO 3.0
  (should work with all KOSTAL PIKO inverters)

# Configuration

## plugin.conf

The plugin can be configured like this:

<pre>
[Kostal-PV]
   class_name = Kostal
   class_path = plugins.kostal
   ip = 192.168.1.21
   cycle = 5
#   user = pvserver
#   passwd = pvwr
#   datastucture=html
# use
#   datastucture=json
# for UI-Version >6
</pre>

This plugin retrieves data from a KOSTAL inverter module of a solar energy
plant.

The data retrieval is done by establishing a network connection to the
inverter module and retrieving the status via a HTTP/JSON request.

You need to configure the host (or IP) address of the inverter module.
If datastucture=html is used the user and password attributes (user, passwd) can be overwritten, but
defaults to the standard credentials.

If datasructure=json is used, no credentials are requred.

The cycle parameter defines the update interval and defaults to 300 seconds.

## items.conf

### Example

Example configuration which shows the current status and the current, total and
daily power. Additionally it shows the volts and watts for the phases.

<pre>
# items/my.conf
[solar]
    [[status]]
        name = Wechselrichter Status
        type = str
        kostal = operation_status
    [[dcpower]]
        name = Gleichspannungsleitung gesamt
        type = num
        kostal = dctot_w
    [[dc1_v]]
        name = DC-Strang 1 Spannung
        type = num
        kostal = dc1_v
    [[dc1_a]]
        name = DC-Strang 1 Strom
        type = num
        kostal = dc1_a
    [[dc1_w]]
        name = DC-Strang 1 Leistung
        type = num
        kostal = dc1_w
    [[dc2_v]]
        name = DC-Strang 2 Spannung
        type = num
        kostal = dc2_v
    [[dc2_a]]
        name = DC-Strang 2 Strom
        type = num
        kostal = dc2_a
    [[dc2_w]]
        name = DC-Strang 2 Leistung
        type = num
        kostal = dc2_w
    [[actot_w]]
        name = Wechselspannungsleistung gesamt
        type = num
        kostal = actot_w
    [[actot_cos]]
        name = Cos phi
        type = num
        kostal = actot_cos
    [[actot_limitation]]
        name = Abregelungsfaktor
        type = num
        kostal = actot_limitation
    [[ac1_v]]
        name = Phase 1 Spannung
        type = num
        kostal = ac1_v
    [[ac1_a]]
        name = Phase 1 Strom
        type = num
        kostal = ac1_a
    [[ac1_w]]
        name = Phase 1 Leistung
        type = num
        kostal = ac1_w
    [[ac2_v]]
        name = Phase 2 Spannung
        type = num
        kostal = ac2_v
    [[ac2_a]]
        name = Phase 2 Strom
        type = num
        kostal = ac2_a
    [[ac2_w]]
        name = Phase 2 Leistung
        type = num
        kostal = ac2_w
    [[ac3_v]]
        name = Phase 3 Spannung
        type = num
        kostal = ac3_v
    [[ac3_a]]
        name = Phase 3 Strom
        type = num
        kostal = ac3_a
    [[ac3_w]]
        name = Phase 3 Leistung
        type = num
        kostal = ac3_w
    [[yield_day_wh]]
        name = Gesamtleistung heute
        type = num
        kostal = yield_day_wh
    [[yield_tot_kwh]]
        name = Gesamtleistung total
        type = num
        kostal = yield_tot_kwh
    [[operationtime_h]]
        name = Betriebsstunden
        type = num
        kostal = operationtime_h
</pre>

## logic.conf

No logic related stuff implemented.

# Methods

No methods provided currently.
