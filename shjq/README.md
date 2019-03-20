# shjq

This is a generic JSON to smarthome plugin. Fetch any JSON encoded
data via http(s) or from a file, extract the interesting data and feed
the values to smarthome items.

It uses the lightweight and flexible JSON processor jq [https://stedolan.github.io/jq/]

# Dependencies

This plugin requires
- requests
- requests-file
- pyjq 

# Configuration

## Enable the plugin in etc/plugin.yaml

You can add as many instances as you have JSON sources to process. Make sure to add a 
unique instance name to each instance if you configure more than on instance. Those
instance name will serve as a key to the item configuration further down.

### Plugin specific attributes
#### url

The address of the json data. Currently http://, https:// and file:// schemes are supported.
Note: using absolute file paths for the file:// schema yields in tripple forward slashes. This
might look funny but it is not an error.

#### cycle

The repetitive polling interval in seconds. Defaults to 30 seconds.

### Example

The following examples uses openweathermap and it's sample API Key. Don't use this key for anything else
but testing.  Examples were taken from
[https://openweathermap.org/current].

### http client

    shjq:
      class_name: SHJQ
      class_path: plugins.shjq
      url: https://samples.openweathermap.org/data/2.5/weather?q=London,uk&appid=b6907d289e10d714a6e88b30761fae22
      cycle: 30

### file client

    shjq:
      class_name: SHJQ
      class_path: plugins.shjq
      url: file:///path/to/data.json
      cycle: 30

### multi instance
    shjquk:
      class_name: SHJQ
      class_path: plugins.shjq
      url: https://samples.openweathermap.org/data/2.5/weather?q=London,uk&appid=b6907d289e10d714a6e88b30761fae22
      instance: london

    shjquk:
      class_name: SHJQ
      class_path: plugins.shjq
      url: https://samples.openweathermap.org/data/2.5/weather?id=2172797&appid=b6907d289e10d714a6e88b30761fae22
      instance: cairns


## item configuration in items/myitem.yaml
This is the fun part. This is a sample item. Notice the special attribute shjq_source.

### Single instance
just use the shjq_source attribute

    temperature:
      type: num
      shjq_source: .main.temp

### Multi instance
Use the shjq_source@instance attribute syntax

    temperature:
      london:
        type: num
        shjq_source@london: .main.temp
      cairns:
        type: num
        shjq_source@cairns: .main.temp

The value for the shjq_source attribute is a jq filter, passed directly to jq itself
Use any kind of jq filter that suites your needs. Make sure your filter returns a single value.
Jq filters can be tricky to develop for complex json structures. Getting them straight might be easier
outside of smarthome by using the commandline version of jq and curl like this

    curl https://json.server.org/data.json | jq -f '.object'

Look at [https://stedolan.github.io/jq/tutorial/] to get startet with jq filters.

# Disclaimer and License
This document and the shjq plugin for smarthome.py is free software:
you can redistribute it and/or modify it under the terms of the 
GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

smjq is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with shjq. If not, see <http://www.gnu.org/licenses/>.
