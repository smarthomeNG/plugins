# Traffic

Version 0.1

# Requirements
This plugin requires lib requests. You can install this lib with:
<pre>
sudo pip3 install requests --upgrade
</pre>

This plugin provides functionality to query the Google Directions API for traffic / direction info.
All mappings to items need to be done via your own logic.

Forum thread to the plugin: https://knx-user-forum.de/forum/supportforen/smarthome-py/1048446-traffic-plugin-support-thread

Take care not to request the interface too often as there currently is only a limit of 2500 free requests / day.
More information and API key see: https://developers.google.com/maps/documentation/directions/intro?hl=de#traffic-model

# Configuration

## plugin.conf
<pre>
[traffic]
    class_name = Traffic
    class_path = plugins.traffic
    apikey = <your own api key>
    language = de (optional)
</pre>

### Attributes
  * `apikey`: Your own personal API key for Google Directions. For your own key register to https://creativecommons.tankerkoenig.de
  * `language`: Any 2 char language code that is supported by Google Directions API, default is "de"

## items.conf

Currently, no pre defined items exist

# Functions

## get_route_info(origin, destination, alternatives):
Returns route information for a provided origin (in the example home coordinates) and destination (in the example Berlin)
<pre>
route = sh.traffic.get_route_info(sh._lat+','+sh._lon, 'Berlin', False)
</pre>
Returned is a dict (or in case of alternatives = True an array of dicts) with route information.
The following dict keys are available: distance (in meters), duration (in seconds), summary