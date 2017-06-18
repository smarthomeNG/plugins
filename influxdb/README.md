# Logging to InfluxDB over UDP
Logging items to the time-series database [InfluxDB](https://www.influxdata.com/time-series-platform/influxdb/)

This started as a fork of the plugin `influxdata` with the following enhancements:
- proper naming
- specify a name for the measurement instead of falling back to the item's ID
- specify additional tags or fields globally (plugin.conf) and/or on per-item basis

The special smarthomeNG attributes `caller`, `source` and `dest` are always logged as tags.

Only if a measurement name is specified, the item's ID is automatically logged as well (tag `item`) - if you don't specify a measurement-name, the name will fallback to the item's ID which makes the item-tag redundant

## Proper Logging
Please read the [Key Concepts](https://docs.influxdata.com/influxdb/v1.1/concepts/key_concepts/) and [Schema Design](https://docs.influxdata.com/influxdb/v1.1/concepts/schema_and_data_layout/)

Especially these:
- [Encode meta data in tags](https://docs.influxdata.com/influxdb/v1.1/concepts/schema_and_data_layout/#encode-meta-data-in-tags)
- [Don’t encode data in measurement names](https://docs.influxdata.com/influxdb/v1.1/concepts/schema_and_data_layout/#don-t-encode-data-in-measurement-names)
- [Don’t put more than one piece of information in one tag](https://docs.influxdata.com/influxdb/v1.1/concepts/schema_and_data_layout/#don-t-put-more-than-one-piece-of-information-in-one-tag)

## Setup
### /etc/influxdb/influxdb.conf
You have to explicitly enable the UDP endpoint in influxdb. The UDP endpoint cannot be auth-protected and is bound to a specific database
<pre>
[[udp]]
  enabled = true
  bind-address = ":8089"
  database = "smarthome"
  # retention-policy = ""
</pre>

### plugin.conf
you can setup global tags and fields (JSON encoded)
<pre>
[influxdb]
    class_name = InfluxDB
    class_path = plugins.influxdb
#   host = localhost
#   port = 8089
#   keyword = influxdb
#   value_field = value
    tags = {"key": "value", "foo": "bar"}
    fields = {"key": "value", "foo": "bar"}
</pre>

### items.conf
logging into a measurement named `root.some_item`, default tags and tags/fields as specified in plugin.conf
<pre>
[root]
  [[some_item]]
    influxdb = true
</pre>

if `keyword` in plugin.conf is set to `sqlite` this can also be used as a drop-in replacement for sqlite.
<pre>
[root]
  [[some_item]]
    sqlite = true
</pre>

*recommended*: logging into the measurement `temp` with an additional tag `room` and default tags (including `item: root.dining_temp`) and tags/fields as specified in plugin.conf
<pre>
[root]
  [[dining_temp]]
    influxdb_name = temp
    influxdb_tags = {"room": "dining"}
</pre>
