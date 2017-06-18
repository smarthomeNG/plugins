# TankerKoenig

Version 0.1

## Requirements

This plugin requires lib requests. You can install this lib with: 
<pre>
sudo pip3 install requests --upgrade
</pre>

All mappings to items need to be done via your own logic.

Forum thread to the plugin: https://knx-user-forum.de/forum/supportforen/smarthome-py/938924-benzinpreis-plugin

Take care not to request the interface too often or for too many petrol stations. Please follow instructions given on
https://creativecommons.tankerkoenig.de/#techInfo and e.g. use prices function for price retrieval. Static information
such as name or location can be directly set in your python logics.

Recommended by tankerkoenig is to store meta data (Name, Address etc.) statically in your code, db, file cache etc and
just request / update prices via get_petrol_station_prices.
Other ways of using the interface may result in mail communication with responsibles of tankerkoenig, telling you
of using the interface in the way described above (static storage of meta data). Please take this into account when
integrating it..

## Configuration

### plugin.conf
<pre>
[tankerkoenig]
    class_name = TankerKoenig
    class_path = plugins.tankerkoenig
    apikey = <your own api key>
</pre>

#### Attributes
  * `apikey`: Your own personal API key for TankerKoenig. For your own key register to https://creativecommons.tankerkoenig.de

### items.conf

#### Example (for cheapest station and for one station that is requested via its id):
<pre>
[petrol_station]
    [[cheapest]]
        [[[isOpen]]]
            type=bool
            visu_acl = ro
        [[[name]]]
            type=str
            visu_acl = ro
        [[[price]]]
            type=num
            visu_acl = ro
    [[DemoBavariaPetrol]]
        tankerkoenig_id = a07b7f50-6e6f-4e6e-9bce-17d79bf0778c
        [[[diesel]]]
            type=num
            visu_acl = ro
        [[[name]]]
            type=str
            visu_acl = ro
        [[[isOpen]]]
            type=bool
            visu_acl = ro
</pre>

## Functions

### get_petrol_stations(lat, lon, type, sort, rad):
Gets a list of petrol stations around provided coordinates, depending on a provided type, sort order and radius.
In the example, sh._lat and sh.._long are the geocoordinates configured for smarthome in etc/smarthome.conf. You
can also set your own coordinates!
<pre>
cheapest = sh.tankerkoenig.get_petrol_stations(sh._lat, sh._lon, 'diesel', 'price', rad='2')
</pre>
Returned is an array of petrol station data, with the following available keys:
'place', 'brand', 'houseNumber', 'street', 'id', 'lng', 'name', 'lat', 'price', 'dist', 'isOpen', 'postCode'
Note: Take care with too high rad values, as this also increases load on tankerkoenig interface.

### get_petrol_station_detail(id)
This funktion gets the details of one petrol station, identified by its internal TankerKoenig ID.
<pre>
detail = sh.tankerkoenig.get_petrol_station_detail(sh.petrol_station.DemoBavariaPetrol.conf['tankerkoenig_id'])
</pre>
Returned keys are 'e5', 'e10', 'diesel', 'street', 'houseNumber', 'postCode', 'place', 'brand', 'id', 'lng', 'name', 'lat', 'isOpen'

## Logics

### Fill items with cheapest petrol station data
<pre>
cheapest = sh.tankerkoenig.get_petrol_stations(sh._lat, sh._lon, 'diesel', 'price', rad='10')
sh.petrol_station.cheapest.name(cheapest[0]['name'])
sh.petrol_station.cheapest.isOpen(cheapest[0]['isOpen'])
sh.petrol_station.cheapest.price(cheapest[0]['price'])
</pre>

### Get data of one petrol station
<pre>
detail = sh.tankerkoenig.get_petrol_station_detail(sh.petrol_station.DemoBavariaPetrol.conf['tankerkoenig_id'])
sh.petrol_station.DemoBavariaPetrol.name(detail['name'])
sh.petrol_station.DemoBavariaPetrol.isOpen(detail['isOpen'])
sh.petrol_station.DemoBavariaPetrol.diesel(detail['diesel'])
</pre>

### Get prices of two petrol stations
<pre>
prices = sh.tankerkoenig.get_petrol_station_prices(['6437ff91-823c-40c6-b556-42553056f7cd','56e30926-02dd-41aa-9e05-1120cbafe34f'])
</pre>