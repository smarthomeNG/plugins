# MVG Live

Version 0.1

## Requirements
This plugin requires lib PyMVGLive. You can install this lib with:
<pre>
sudo pip3 install PyMVGLive --upgrade
</pre>

This plugin provides functionality to query the data of www.mvg-live.de via the python package PyMVGLive. Take care to not run it too often. My example below is triggered by a select action in the
SmartVISU 2.9 select widget.

Forum thread to the plugin: https://knx-user-forum.de/forum/supportforen/smarthome-py/1108867-neues-plugin-mvg_live

## Configuration

### plugin.conf
<pre>
[mvg_live]
    class_name = MVG_Live
    class_path = plugins.mvg_live
</pre>

### items.conf / items.yaml

Currently, no pre defined items exist, the example below needs these items:
<pre>
[travel_info]

     [[mvg_station]]
        type = num

        [[[search]]]
            type = str
            cache = yes
            visu_acl: rw

            [[[[result]]]]
                type = str
                cache = yes
                visu_acl: rw
</pre>

<pre>
travel_info:

    mvg_station:

        search:
            type: str
            cache: 'yes'
            visu_acl: rw

            result:
                type: str
                cache: 'yes'
                visu_acl: ro
</pre>

## Functions

### get_station_departures(self, station, timeoffset=0, entries=10, ubahn=True, tram=True, bus=True, sbahn=True):
Returns information about the departures in a specific station. See www.mvg-live.de for the allowed names.

## Logics

### logics.conf / yaml
<pre>
[MVGWatch]
    filename = mvg.py
    watch_items = travel_info.mvg_station.search
</pre

<pre>
MVGWatch:
    filename: mvg.py
    watch_item:
      - travel_info.mvg_station.search
</pre>

### mvg.py

```html
results = sh.mvg_live.get_station_departures(sh.travel_info.mvg_station.search(), entries=15, bus=False, tram=False)
html_string = '<table>'
i = 1
for result in results:

    dir_info = ''
    line_string = '<tr><td style="width: 10px;"></td>'
    line_string += '<td><img src="%s" alt="%s"/><td><td style="margin-left: 5px;"><img src="%s" alt="%s"/></td>' % (
    result['productsymbolurl'], result['product'], result['linesymbolurl'], result['linename'])
    line_string += '<td style="text-align: left; padding-left: 15px; width: 100%;">'
    line_string += '%s </td>' % result['destination']
    line_string += '<td style="color: #000; font-weight: bold; font-size: 25px;">'
    line_string += '<div style="background-color: #fff; width: 30px; ">%i</div></td></tr>' % result['time']
    html_string += line_string
    i = i + 1
    if i == 7:
        break

html_string += '</table>'
sh.travel_info.mvg_station.search.result(html_string)
```

### SmartVisu integration (Requires SmartVisu 2.9 as select widget is used)

<pre>
{{ basic.select('travel_info.mvg_station.search', 'travel_info.mvg_station.search', '', ['Frankfurter Ring', 'Hauptbahnhof', 'Karlsplatz (Stachus)', 'Marienplatz'], '', ['Frankfurter Ring', 'Hauptbahnhof', 'Karlsplatz (Stachus)', 'Marienplatz']) }}
{{ basic.print('travel_info.mvg_station.search.result', 'travel_info.mvg_station.search.result', 'html') }}
</pre>