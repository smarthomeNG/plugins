# Simulation 

# Requirements

This plugins has no requirements.

# Configuration

## plugin.conf

<pre>
[simulation]
   class_name = Simulation
   class_path = plugins.simulation
   data_file = /usr/smarthome/var/db/simulation.txt
</pre>

data_file: This is the file where all recorded events are stored.


## items.conf

List and describe the possible item attributes.

### sim

Add sim = track to each item that want to be included in the simulation


