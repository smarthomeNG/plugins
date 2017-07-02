# KOSTAL

Version: 1.3.1

This plugin is designed to retrieve data from a [KOSTAL](http://www.kostal-solar-electric.com/) inverter module (e.g. PIKO inverters).
Since UI-version (communication-board) 6 json-format is supported.

Forum thread to the plugin: https://knx-user-forum.de/forum/supportforen/smarthome-py/

## Supported Hardware

Is currently working with the following KOSTAL inverter modules:

  * KOSTAL PIKO 3.0 UI-Version 06.20 (datastructure=json)
  * KOSTAL PIKO 5.5 UI-Version 05.xx (datastructure=html)

  (should work with all KOSTAL PIKO inverters)
  <add more successfull testet Kostal Inverters with UI-Version and used datastructure>

knx-user-forum.de

### Hint
  If com­mu­ni­ca­tion board (Kom­mu­nika­tions­board II) firmware has a version 5.x,
  then the inverter generates an html - page.
  The default datastructure=html configuration of this plugin, trys to read
  the current inverter values from this status page.

  If com­mu­ni­ca­tion board (Kom­mu­nika­tions­board II) firmware has a version 6.x,
  then the inverter generates ajax - style status page.
  The datastructure=json configuration of this plugin, reads the current
  inverter values from an json-comminication string.

  So the datastructure - configuration depends on the firmwareversion of your
  communication board.

  New inverters:
  http://kostal-solar-electric.com/de-DE/Produkte_Service/PIKO-Wechselrichter_neue_Generation
  My Kostal Piko 3.0 was shipped with a communication board with a firmware version 5.x.
  After a firmware-upgrade my inverter doesn't ship a html-page. Now i could user the
  JSON-communication.
  Firmware Updates http://www.kostal-solar-electric.com/de-DE/Download/Updates

  Old inverters:
  http://kostal-solar-electric.com/de-DE/Produkte_Service/PIKO-Wechselrichter_bewaehrte_Generation,
  I'll don't know if the communication board of old inverters could also be updated to version 6.x.


## Configuration

### plugin.conf

The plugin can be configured like this:

<pre>
[Kostal-PV]
   class_name = Kostal
   class_path = plugins.kostal
   ip = 192.168.1.21
   cycle = 5
#   user = pvserver
#   passwd = pvwr
#   datastructure=html
# use
#   datastructure=json
# for UI-Version >6
</pre>

This plugin retrieves data from a KOSTAL inverter module of a solar energy
plant.

The data retrieval is done by establishing a network connection to the
inverter module and retrieving the status via a HTTP/JSON request.

You need to configure the IP address of the inverter module.
If datastructure=html is used the user and password attributes (user, passwd)
can be overwritten, but defaults to the standard credentials.

If datasructure=json is used, no credentials are requred.

The cycle parameter defines the update interval and defaults to 300 seconds.

### items.conf

#### Example

Example configuration which shows all supported values, depending on the
features of the inverter.

Example: PIKO 3.0 is a single phase inverter with a single dc-line (dc-string).
  all DC2, DC3, AC2 and AC3 values would reply a None-value.

If your communication board has a firmwareversion 5 (datastructure=html),
the following values are not displayed in the html-status page and also not
available for the plugin.

dctot_w, dc1_w, dc2_w, dc3_w,
actot_cos, actot_limitation, ac1_a, ac2_a, ac3_a,
operationtime_h

Hint:
Item names have changed from the previous version of the plugin, so that both
types of communication can be configured the same way.

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
