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
    apikey = your own api key
    language = de (optional)
</pre>

### Attributes
  * `apikey`: Your own personal API key for Google Directions. For your own key see https://developers.google.com/maps/documentation/directions/intro?hl=de#traffic-model
  * `language`: Any 2 char language code that is supported by Google Directions API, default is "de"

## items.conf

Currently, no pre defined items exist, the example below needs these items:
<pre>
[travel_info]
    [[travel_time]]
        type = num

    [[travel_distance]]
        type = num

    [[travel_summary]]
        type = str

    [[html_instructions]]
        type = str

    [[copyrights]]
        type = str

    [[start_address]]
        type = str

    [[start_location]]

        [[[lat]]]
            type = num

        [[[lon]]]
            type = num

    [[end_address]]
        type = str

    [[end_location]]

        [[[lat]]]
            type = num

        [[[lon]]]
            type = num
</pre>
# Functions

## get_route_info(origin, destination, alternatives, mode):
Returns route information for a provided origin (in the example home coordinates) and destination (in the example Berlin)
<pre>
route = sh.traffic.get_route_info(sh._lat+','+sh._lon, 'Berlin', False, 'driving')

summary = route['summary']+": %.1f km in %.0f min" % (round(route['duration']/60,2), round(route['distance']/1000,2))
if route['summary'] is not '':
    route['summary'] += ": "
summary = route['summary']+"%.1f km in %.0f min" % (round(route['duration']/60,2), round(route['distance']/1000,2))
sh.travel_info.travel_time(route['duration'])
sh.travel_info.travel_distance(route['distance'])
sh.travel_info.travel_summary(summary)
sh.travel_info.html_instructions(route['html_instructions'])
sh.travel_info.copyrights(route['copyrights'])
sh.travel_info.start_address(route['start_address'])
sh.travel_info.start_location.lat(route['start_location_lat'])
sh.travel_info.start_location.lon(route['start_location_lon'])
sh.travel_info.end_address(route['end_address'])
sh.travel_info.end_location.lat(route['end_location_lat'])
sh.travel_info.end_location.lon(route['end_location_lon'])
</pre>
Returned is a dict (or in case of alternatives = True an array of dicts) with route information.
The following dict keys are available: distance (in meters), duration (in seconds), summary