# TankerKoenig

Version 0.1

# Requirements
This plugin requires lib requests. You can install this lib with: 
<pre>
sudo pip3 install requests --upgrade
</pre>

All mappings to items need to be done via your own logic.

# Configuration

## plugin.conf
<pre>
[tankerkoenig]
    class_name = TankerKoenig
    class_path = plugins.tankerkoenig
    apikey = <your own api key>
</pre>

### Attributes
  * `apikey`: Your own personal API key for TankerKoenig. For your own key register to https://creativecommons.tankerkoenig.de

## items.conf

### Example (for cheapest station):
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

# Functions

## get_petrol_stations(lat, lon, type, sort, rad):
Gets a list of petrol stations around provided coordinates, depending on a provided type, sort order and radius.
<pre>
cheapest = sh.tankerkoenig.get_petrol_stations(sh._lat, sh._lon, 'diesel', 'price', rad='10')
</pre>

## get_petrol_station_detail(id)
This funktion gets the details of a petrol station, identified by their internal TankerKoenig ID.
<pre>
detail = sh.tankerkoenig.get_petrol_station_detail(sh.petrol_station.DemoBavariaPetrol.conf['tankerkoenig_id'])
</pre>

# Logics

## Fill items with cheapest petrol station data
cheapest = sh.tankerkoenig.get_petrol_stations(sh._lat, sh._lon, 'diesel', 'price', rad='10')
sh.petrol_station.cheapest.name(cheapest[0]['name'])
sh.petrol_station.cheapest.isOpen(cheapest[0]['isOpen'])
sh.petrol_station.cheapest.price(cheapest[0]['price'])