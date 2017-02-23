# Wunderground

This plugins can be used retrieve weather information from wunderground.

# Requirements

An api key from wunderground is needed. It can be obtained free of charge from ```https://www.wunderground.com/weather/api/d/pricing.html```.


# Configuration

## plugin.conf

Use the plugin configuration to configure the wunderground plugin. 

You can configure multiple instances of the wunderground plugin to collect data for multiple locations.

<pre>
[weather_somewhere]
	class_name = Wunderground
	class_path = plugins.wunderground
	apikey = xxxxyyyyxxxxyyyy
	# language = de
	location = Germany/Hamburg
	item_subtree = mein_wetter
	instance = wetter_ham
</pre>


### apikey
Enter you registered wunderground API key

### language
Defines the language for the forcast data. (en: English, de: German, fr: French)

If you need another language, lookup a complete list of language codes on www.wunderground.com


For a complete list, consult www.wunderground.com


### location
The location for which you want weather information. 
Examples:

```
CA/San_Francisco                      US state/city
60290                                 US zipcode
Australia/Sydney                      country/city
37.8,-122.4                           latitude,longitude
KJFK                                  airport code
pws:KCASANFR70                        PWS id
autoip                                AutoIP address location
autoip.json?geo_ip=38.102.136.138     specific IP address location
```

To find a location string that works for you, you can look at your local waether on wunderground.com and use the location string you see on that page.

### item_subtree

**```item_subtree```** defines the part of the item-tree which the wunderground plugin searches during data updates for the **```wug_xmlstring```** attribute. 

If **```item_subtree```** is not defined or empty, the whole item-tree is searched, which creates unnecessary overhead vor SmartHomeNG.

### instance
Name of the plugin instance (SmartPlugin attribute). This is important if you define multiple weather locations using multiple instances of the wunderground plugin.

## items configuration
The following attributes can be used. You can define additional attributes. To do so, you have to lookup the matching wunderground xmlstring on www.wunderground.com.

The items can have a default value, set by using the ```value``` attribute. The default values are used, if the weather station you selected does not send data for the selected xmlstring. The following example defines default values for items, which are not supported by all weather stations.


## Example: items.yaml
Example configuration of an item-subtree for the wunderground plugin in yaml-format:

```YAML
...:

    mein_wetter:

        ort:
            type: str
            wug_xmlstring: display_location/city

        ort_wetterstation:
            type: str
            wug_xmlstring: observation_location/city
            value: unbekannt

        lokale_zeit:
            type: str
            wug_xmlstring: local_time_rfc822

        beobachtungszeitpunkt:
            type: str
            wug_xmlstring: observation_time_rfc822

        beobachtungszeitpunkt_datetime:
            type: num
            wug_xmlstring: observation_epoch

        wetter:
            type: str
            wug_xmlstring: weather

        wetter_icon:
            type: str
            wug_xmlstring: icon

        temperatur:
            type: num
            value: -9999
            wug_xmlstring: temp_c

        temperatur_gefuehlt:
            type: num
            value: -9999
            wug_xmlstring: feelslike_c

        rel_luftfeuchtigkeit:
            type: num
            value: -9999
            wug_xmlstring: relative_humidity

        taupunkt:
            type: num
            value: -9999
            wug_xmlstring: dewpoint_c

        luftdruck:
            type: num
            wug_xmlstring: pressure_mb

        luftdruck_trend:
            type: num
            value: -9999
            wug_xmlstring: pressure_trend

        sichtweite:
            type: num
            value: -9999
            wug_xmlstring: visibility_km

        uv:
            type: num
            value: -9999
            wug_xmlstring: UV

        niederschlag_1std:
            type: num
            value: -9999
            wug_xmlstring: precip_1hr_metric

        niederschlag_heute:
            type: num
            value: -9999
            wug_xmlstring: precip_today_metric

        windrichtung:
            type: str
            wug_xmlstring: wind_dir

        windrichtung_grad:
            type: num
            wug_xmlstring: wind_degrees

        windgeschwindigkeit:
            type: num
            value: -9999
            wug_xmlstring: wind_kph

        windboeen:
            type: num
            value: -9999
            wug_xmlstring: wind_gust_kph

        vorhersage:

            temperatur_min:
                type: num
                value: -9999
                wug_xmlstring: simpleforecast/forecastdays/forecastday/low/celsius

            temperatur_max:
                type: num
                value: -9999
                wug_xmlstring: simpleforecast/forecastdays/forecastday/high/celsius

            niederschlag:
                type: num
                value: -9999
                wug_xmlstring: simpleforecast/forecastdays/forecastday/pop

            verhaeltnisse:
                type: str
                value: -9999
                wug_xmlstring: simpleforecast/forecastdays/forecastday/conditions

            maxwindspeed:
                type: num
                value: -9999
                wug_xmlstring: simpleforecast/forecastdays/forecastday/maxwind/kph

            maxwinddir:
                type: str
                value: -9999
                wug_xmlstring: simpleforecast/forecastdays/forecastday/maxwind/dir

            maxwinddegrees:
                type: num
                value: -9999
                wug_xmlstring: simpleforecast/forecastdays/forecastday/maxwind/degrees

            avgwindspeed:
                type: num
                value: -9999
                wug_xmlstring: simpleforecast/forecastdays/forecastday/avewind/kph

            avgwinddir:
                type: str
                value: -9999
                wug_xmlstring: simpleforecast/forecastdays/forecastday/avewind/dir

            avgwinddegrees:
                type: num
                value: -9999
                wug_xmlstring: simpleforecast/forecastdays/forecastday/avewind/degrees

```

## Example: items.conf

<pre>
# items/weather.conf
Example configuration for wunderground plugin in the old conf-format:

[mein_wetter]
	[[ort]]
		type = str
		wug_xmlstring = display_location/city

	[[ort_wetterstation]]
		type = str
		wug_xmlstring = observation_location/city
		value = unbekannt

	[[lokale_zeit]]
		type = str
		wug_xmlstring = local_time_rfc822

	[[beobachtungszeitpunkt]]
		type = str
		wug_xmlstring = observation_time_rfc822

	[[beobachtungszeitpunkt_datetime]]
		type = num
		wug_xmlstring = observation_epoch

	[[wetter]]
		type = str
		wug_xmlstring = weather

	[[wetter_icon]]
		type = str
		wug_xmlstring = icon

	[[temperatur]]
		type = num
		value = -9999
		wug_xmlstring = temp_c

	[[temperatur_gefuehlt]]
		type = num
		value = -9999
		wug_xmlstring = feelslike_c

	[[rel_luftfeuchtigkeit]]
		type = num
		value = -9999
		wug_xmlstring = relative_humidity

	[[taupunkt]]
		type = num
		value = -9999
		wug_xmlstring = dewpoint_c

	[[luftdruck]]
		type = num
		wug_xmlstring = pressure_mb

	[[luftdruck_trend]]
		type = num
		value = -9999
		wug_xmlstring = pressure_trend

	[[sichtweite]]
		type = num
		value = -9999
		wug_xmlstring = visibility_km

	[[uv]]
		type = num
		value = -9999
		wug_xmlstring = UV

	[[niederschlag_1std]]
		type = num
		value = -9999
		wug_xmlstring = precip_1hr_metric

	[[niederschlag_heute]]
		type = num
		value = -9999
		wug_xmlstring = precip_today_metric

	[[windrichtung]]
		type = str
		wug_xmlstring = wind_dir

	[[windrichtung_grad]]
		type = num
		wug_xmlstring = wind_degrees

	[[windgeschwindigkeit]]
		type = num
		value = -9999
		wug_xmlstring = wind_kph

	[[windboeen]]
		type = num
		value = -9999
		wug_xmlstring = wind_gust_kph

	[[vorhersage]]

		[[[temperatur_min]]]
			type = num
			value = -9999
			wug_xmlstring = simpleforecast/forecastdays/forecastday/low/celsius

		[[[temperatur_max]]]
			type = num
			value = -9999
			wug_xmlstring = simpleforecast/forecastdays/forecastday/high/celsius

		[[[niederschlag]]]
			type = num
			value = -9999
			wug_xmlstring = simpleforecast/forecastdays/forecastday/pop

		[[[verhaeltnisse]]]
			type = str
			value = -9999
			wug_xmlstring = simpleforecast/forecastdays/forecastday/conditions

		[[[maxwindspeed]]]
			type = num
			value = -9999
			wug_xmlstring = simpleforecast/forecastdays/forecastday/maxwind/kph

		[[[maxwinddir]]]
			type = str
			value = -9999
			wug_xmlstring = simpleforecast/forecastdays/forecastday/maxwind/dir

		[[[maxwinddegrees]]]
			type = num
			value = -9999
			wug_xmlstring = simpleforecast/forecastdays/forecastday/maxwind/degrees

		[[[avgwindspeed]]]
			type = num
			value = -9999
			wug_xmlstring = simpleforecast/forecastdays/forecastday/avewind/kph

		[[[avgwinddir]]]
			type = str
			value = -9999
			wug_xmlstring = simpleforecast/forecastdays/forecastday/avewind/dir

		[[[avgwinddegrees]]]
			type = num
			value = -9999
			wug_xmlstring = simpleforecast/forecastdays/forecastday/avewind/degrees

</pre>

## logic.conf

No logic configuration implemented.

# Methods / Functions

No methods or funktions are implemented.

