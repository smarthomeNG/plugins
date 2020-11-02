# Wetterdienst

This plugins can be used retrieve weather information from the Deutsche Wetterdienst (DWD) via https://pypi.org/project/wetterdienst.

## Support
Support is provided trough the support thread within the smarthomeNG forum: [Smarthome.py](https://knx-user-forum.de/forum/supportforen/smarthome-py)


### Requirements
wetterdienst pypi package. Install via pip3 install wetterdienst

## Configuration

### plugin.yaml

Use the plugin configuration to configure the wetterdienst plugin.

One instance of the plugin supports multiple stations. To find the station IDs relevant for you, use the plugin's web interface.
For possible combinations of search parameters, see https://wetterdienst.readthedocs.io/_/downloads/en/latest/pdf/ chapter 1.3.1.

```yaml
# for etc/plugin.yaml configuration file:
wetterdienst:
    plugin_name: wetterdienst
    latitude: '48.12345'
    longitude: '11.12345'
```
* latitude: (optional): specify fix latitude coordinates for station search. If not used, SmartHomeNG coordinates will be used. You can still search stations around other coordinates manually via the plugin's web interface.
* longitude: (optional): specify fix longitude coordinates for station search. If not used, SmartHomeNG coordinates will be used. You can still search stations around other coordinates manually via the plugin's web interface.

### Example: items.yaml
Example configuration of an item-tree for the openweathermap plugin in yaml-format:

```yaml

 ...:

owm:
    rain_layer:
        type: str
        owm_matchstring@home: precipitation_new
        x@home: 13
        y@home: 48
        z@home: 7

    cloud_layer:
        type: str
        owm_matchstring@home: clouds_new
        x@home: 1
        y@home: 1
        z@home: 2

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

        forecast_3hours: # next 3 hours, use 0-39 for further forecasts
            time:
                type: num
                owm_matchstring@home: forecast/1/dt

            conditions:
                type: list
                owm_matchstring@home: weather

            temp:
                type: num
                owm_matchstring@home: forecast/1/main/temp

            temp_min:
                type: num
                owm_matchstring@home: forecast/1/main/temp_min

            temp_max:
                type: num
                owm_matchstring@home: forecast/1/main/temp_max

            pressure:
                type: num
                owm_matchstring@home: forecast/1/main/pressure

            grnd_level:
                type: num
                owm_matchstring@home: forecast/1/main/grnd_level

            sea_level:
                type: num
                owm_matchstring@home: forecast/1/main/sea_level

            humidity:
                type: num
                owm_matchstring@home: forecast/1/main/humidity

            wind:
                wind_speed:
                    type: num
                    owm_matchstring@home: forecast/1/wind/speed

                wind_deg:
                    type: num
                    owm_matchstring@home: forecast/1/wind/deg

            clouds:
                type: num
                owm_matchstring@home: forecast/1/clouds/all

        forecast_daily0: # tomorrow's forecast
            time:
                type: num
                owm_matchstring@home: forecast/daily/0/dt

            temp:
                type: num
                owm_matchstring@home: forecast/daily/0/main/temp

            temp_min:
                type: num
                owm_matchstring@home: forecast/daily/0/main/temp_min

            temp_max:
                type: num
                owm_matchstring@home: forecast/daily/0/main/temp_max

            pressure:
                type: num
                owm_matchstring@home: forecast/daily/0/main/pressure

                grnd_level:
                    type: num
                    owm_matchstring@home: forecast/daily/0/main/grnd_level

                sea_level:
                    type: num
                    owm_matchstring@home: forecast/daily/0/main/sea_level

            humidity:
                type: num
                owm_matchstring@home: forecast/daily/0/main/humidity

            wind:
                wind_speed:
                    type: num
                    owm_matchstring@home: forecast/daily/0/wind/speed

                wind_deg:
                    type: num
                    owm_matchstring@home: forecast/daily/0/wind/deg

            clouds:
                type: num
                owm_matchstring@home: forecast/daily/0/clouds/all

        forecast_daily1: # day after tomorrow (max index 4 = 5 days ahead)
            time:
                type: num
                owm_matchstring@home: forecast/daily/1/dt

            temp:
                type: num
                owm_matchstring@home: forecast/daily/1/main/temp

            temp_min:
                type: num
                owm_matchstring@home: forecast/daily/1/main/temp_min

            temp_max:
                type: num
                owm_matchstring@home: forecast/daily/1/main/temp_max

            pressure:
                type: num
                owm_matchstring@home: forecast/daily/1/main/pressure

            grnd_level:
                type: num
                owm_matchstring@home: forecast/daily/1/main/grnd_level

            sea_level:
                type: num
                owm_matchstring@home: forecast/daily/1/main/sea_level

            humidity:
                type: num
                owm_matchstring@home: forecast/daily/1/main/humidity

            wind:
                wind_speed:
                    type: num
                    owm_matchstring@home: forecast/daily/1/wind/speed

                wind_deg:
                    type: num
                    owm_matchstring@home: forecast/daily/1/wind/deg

            clouds:
                type: num
                owm_matchstring@home: forecast/daily/1/clouds/all

```

### logic.yaml

No logic configuration implemented.

## Methods / Functions

No methods or functions are implemented.
