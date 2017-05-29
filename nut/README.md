# NUT - Network UPS Tool plugin

Requirements
============
none


Configuration
=============

## plugin.conf

<pre>
 [nut]

    class_name = NUT
    class_path = plugins.nut
    host = localhost
    port = port
    cycle = cycle
</pre>

## items.conf
<pre>
 [ups_item]
      
    type = str
    nut_var = variable
</pre>

