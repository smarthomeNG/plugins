# OpenWeatherMap

#### Version 1.5.0.2

This plugins can be used retrieve weather information from OpenWeatherMap (https://openweathermap.org/).

## Support
Support is provided trough the support thread within the smarthomeNG forum: [Smarthome.py](https://knx-user-forum.de/forum/supportforen/smarthome-py)


### Requirements

An api key from OpenWeatherMap is needed. It can be obtained free of charge from ```https://openweathermap.org```.

The api key which is available free of charge allows up to 60 calls a minute. Keep this in mind if you want to change the update frequency using the **`cycle`** parameter.

## Configuration

### plugin.yaml

Use the plugin configuration to configure the openweathermap plugin.

You can configure multiple instances of the openweathermap plugin to collect data for multiple locations.

```yaml
# for etc/plugin.yaml configuration file:
weather_openweathermap:
    class_name: OpenWeatherMap
    class_path: plugins.openweathermap
    key: xxxxyyyyxxxxyyyy
    latitude: '48.04712'
    longitude: '11.81421'
    # language: de
    # cycle: 600
    # instance: ...
```


### Example: items.yaml
Example configuration of an item-tree for the openweathermap plugin in yaml-format:

```yaml

 ...:

owm:

    home:

        latitude:
            type: num
            owm_matchstring@home: coord/lat

        longitude:
            type: num
            owm_matchstring@home: coord/lon

        conditions:
            type: list
            owm_matchstring@home: weather
            
        temp:
            type: num
            owm_matchstring@home: main/temp

        pressure:
            type: num
            owm_matchstring@home: main/pressure

            grnd_level:
                type: num
                owm_matchstring@home: main/grnd_level

            sea_level:
                type: num
                owm_matchstring@home: main/sea_level

        humidity:
            type: num
            owm_matchstring@home: main/humidity

        temp_min:
            type: num
            owm_matchstring@home: main/temp_min

        temp_max:
            type: num
            owm_matchstring@home: main/temp_max

        wind:

            wind_speed:
                type: num
                owm_matchstring@home: wind/speed

            wind_deg:
                type: num
                owm_matchstring@home: wind/deg

        clouds:
            type: num
            owm_matchstring@home: clouds/all

        rain_3h:
            type: num
            owm_matchstring@home: rain/3h

        snow_3h:
            type: num
            owm_matchstring@home: snow/3h

        time:
            type: num
            owm_matchstring@home: dt

        sunrise_utc:
            type: num
            owm_matchstring@home: sys/sunrise

        sunset_utc:
            type: num
            owm_matchstring@home: sys/sunset

        country:
            type: str
            owm_matchstring@home: sys/country

        city_name:
            type: str
            owm_matchstring@home: name

        city_id:
            type: num
            owm_matchstring@home: id

        uvi:
            type: num
            owm_matchstring@home: uvi_value

        uvi_date:
            type: num
            owm_matchstring@home: uvi_date
```

### logic.yaml

No logic configuration implemented.

## Methods / Functions

No methods or functions are implemented.
