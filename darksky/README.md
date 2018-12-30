# darksky.net / forecast.io

#### Version 1.5.0.2

This plugins can be used retrieve weather information from darksky.net / forecast.io.

## Support
Support is provided trough the support thread within the smarthomeNG forum: [Neues Plugin: Wetterdaten via darksky.net / forecast.io](https://knx-user-forum.de/forum/supportforen/smarthome-py/1244744-neues-plugin-wetterdaten-via-darksky-net-forecast-io)


### Requirements

An api key from darksky is needed. It can be obtained free of charge from ```https://darksky.net/dev```.

The api key which is available free of charge allows up to 1000 calls a day. Keep this in mind if you want to change the update frequency using the **`cycle`** parameter.

## Configuration

### plugin.yaml

Use the plugin configuration to configure the darksky plugin.

You can configure multiple instances of the darksky plugin to collect data for multiple locations.

```yaml
# for etc/plugin.yaml configuration file:
weather_darksky:
    class_name: DarkSky
    class_path: plugins.darksky
    key: xxxxyyyyxxxxyyyy
    latitude: '48.04712'
    longitude: '11.81421'
    # lang: de
    # cycle: 600
    # instance: ...
```


### Example: items.yaml
Example configuration of an item-tree for the darksky plugin in yaml-format. For the meaning of some of the matchstrings
please directly consult https://darksky.net/dev/docs:

```yaml

 ...:

darksky:

    latitude:
        type: num
        ds_matchstring: latitude

    longitude:
        type: num
        ds_matchstring: longitude

    timezone:
        type: str
        ds_matchstring: timezone

    currently:

        time:
            type: num
            ds_matchstring: currently/time

        summary:
            type: str
            ds_matchstring: currently/summary

        icon:
            type: str
            ds_matchstring: currently/icon
        
        # create item with icon representation for SmartVisu, won't show up in Plugin's Web Interface 
        icon_sv:
            type: str
            eval_trigger: darksky.currently.icon
            eval: sh.weather_darksky.map_icon(sh.darksky.currently.icon())

        nearestStormDistance:
            type: num
            ds_matchstring: currently/nearestStormDistance

        precipIntensity:
            type: num
            ds_matchstring: currently/precipIntensity

        precipIntensityError:
            type: num
            ds_matchstring: currently/precipIntensityError

        precipProbability:
            type: num
            ds_matchstring: currently/precipProbability

        precipType:
            type: str
            ds_matchstring: currently/precipType

        temperature:
            type: num
            ds_matchstring: currently/temperature

        apparenttemperature:
            type: num
            ds_matchstring: currently/apparentTemperature

        dewpoint:
            type: num
            ds_matchstring: currently/dewPoint

        humidity:
            type: num
            ds_matchstring: currently/humidity

        pressure:
            type: num
            ds_matchstring: currently/pressure

        windSpeed:
            type: num
            ds_matchstring: currently/windSpeed

        windGust:
            type: num
            ds_matchstring: currently/windGust

        windBearing:
            type: num
            ds_matchstring: currently/windBearing

        cloudCover:
            type: num
            ds_matchstring: currently/cloudCover

        uvIndex:
            type: num
            ds_matchstring: currently/uvIndex

        visibility:
            type: num
            ds_matchstring: currently/visibility

        ozone:
            type: num
            ds_matchstring: currently/ozone

    minutely:

        summary:
            type: str
            ds_matchstring: minutely/summary

        icon:
            type: str
            ds_matchstring: minutely/icon

    hourly:

        summary:
            type: str
            ds_matchstring: hourly/summary

        icon:
            type: str
            ds_matchstring: hourly/icon

    daily:

        summary:
            type: str
            ds_matchstring: daily/summary

        icon:
            type: str
            ds_matchstring: daily/icon    
        
        icon_sv:
                type: str
                eval_trigger: ..icon
                eval: sh.darksky_weather.map_icon(sh...icon())  
            
        data:
            type: list
            ds_matchstring: daily/data
            cache: 'yes'

        # all day0, day1, day2 ... items won't show up in WebIf of plugin! Use item tree to check!
        day0:
            date:
                type: str
                eval_trigger: ...data
                eval: datetime.datetime.fromtimestamp(sh....data()[0]['time']).strftime('%a %d.%m.%Y')

            icon:
                type: str
                eval_trigger: ...data
                eval: sh....data()[0]['icon']
            
            icon_sv:
                type: str
                eval_trigger: ..icon
                eval: sh.darksky_weather.map_icon(sh...icon())

            temperature_max:
                type: num
                eval_trigger: ...data
                eval: sh....data()[0]['temperatureMax']
      
        day1:
            date:
                type: str
                eval_trigger: ...data.data
                eval: datetime.datetime.fromtimestamp(sh....data()[1]['time']).strftime('%a %d.%m.%Y')

            icon:
                type: str
                eval_trigger: ...data.data
                eval: sh....data()[1]['icon']
            
            icon_sv:
                type: str
                eval_trigger: ...data.day1.icon
                eval: sh.darksky_weather.map_icon(sh....data.day1.icon())

            temperature_max:
                type: num
                eval_trigger: ...data.data
                eval: sh....data()[1]['temperatureMax']
                
        day2:
            date:
                type: str
                eval_trigger: ...data.data
                eval: datetime.datetime.fromtimestamp(sh....data()[2]['time']).strftime('%a %d.%m.%Y')

            icon:
                type: str
                eval_trigger: ...data.data
                eval: sh....data()[2]['icon']
            
            icon_sv:
                type: str
                eval_trigger: ...data.day2.icon
                eval: sh.darksky_weather.map_icon(sh....data.day2.icon())

            temperature_max:
                type: num
                eval_trigger: ...data.data
                eval: sh....data()[2]['temperatureMax']
                
    alerts:

        list:
            type: list
            ds_matchstring: alerts 
            
        string_detail:
            type: str
            ds_matchstring@home: alerts_string
               
    flags:

        sources:
            type: str
            ds_matchstring: flags/sources

        units:
            type: str
            ds_matchstring: flags/units

        nearest_station:
            type: num
            ds_matchstring: flags/nearest-station
```

### logic.yaml

No logic configuration implemented.

## Methods / Functions

No methods or functions are implemented.
