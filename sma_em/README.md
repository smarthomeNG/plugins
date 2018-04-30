# SMA-EM Plugin

This plugin retrieves the data sent by the SMA Energy Meter.
In agreement with the author Florian Wenger, this plugin uses code published in
https://github.com/datenschuft/SMA-EM/ - especially the readem method.

Forum thread to the plugin: https://knx-user-forum.de/forum/supportforen/smarthome-py/1030610-sma_em-plugin

The SMA Energy Meter broadcasts its information via multicast to the network address 239.12.255.254. Beyond the items
supported by this plugin, the readem method allows for a lot more of parameters. The items will be extended in future
versions of this plugin on demand. The available values can be seen in the readem method of this plugin.

If demand exists, the plugin can also be extended to be used with more than one energy meter.

## Configuration

### plugin.yaml

```yaml
sma_em:
    class_name: SMA_EM
    class_path: plugins.sma_em
    serial: xxxxxxxxxx
    time_sleep: 5
```

#### Attributes
  * `serial`: The serial number of your energy meter
  * `time_sleep`: The time in seconds to sleep after a multicast was received. I introduced this to avoid too many values to be processed

### items.yaml

#### Example:

```yaml
smaem:

    psurplus:
        name: Solar Energy Surplus
        sma_em_data_type: psurplus
        type: num

        kw:
            type: num
            eval: sh.smaem.psurplus() / 1000
            eval_trigger: smaem.psurplus

    psurplus_counter:
        name: Solar Energy Surplus Counter
        sma_em_data_type: psurpluscounter
        type: num

    pregard:
        name: Energy Regard
        sma_em_data_type: pregard
        type: num

        kw:
            type: num
            eval: sh.smaem.pregard() / 1000
            eval_trigger: smaem.pregard

    pregard_counter:
        name: Energy Regard Counter
        sma_em_data_type: pregardcounter
        type: num

    ssurplus:
        sma_em_data_type: ssurplus
        type: num

    ssurplus_counter:
        sma_em_data_type: ssurpluscounter
        type: num

    sregard:
        sma_em_data_type: sregard
        type: num

    sregard_counter:
        sma_em_data_type: sregardcounter
        type: num

    qsurplus:
        sma_em_data_type: qsurplus
        type: num

    qsurplus_counter:
        sma_em_data_type: qsurpluscounter
        type: num

    qregard:
        sma_em_data_type: qregard
        type: num

    qregard_counter:
        sma_em_data_type: qregardcounter
        type: num

    cosphi:
        sma_em_data_type: cosphi
        type: num

    p1surplus:
        sma_em_data_type: p1surplus
        type: num

    p1surplus_counter:
        sma_em_data_type: p1surpluscounter
        type: num

    p1regard:
        sma_em_data_type: p1regard
        type: num

    p1regard_counter:
        sma_em_data_type: p1regardcounter
        type: num

    s1surplus:
        sma_em_data_type: s1surplus
        type: num

    s1surplus_counter:
        sma_em_data_type: s1surpluscounter
        type: num

    s1regard:
        sma_em_data_type: s1regard
        type: num

    s1regard_counter:
        sma_em_data_type: s1regardcounter
        type: num

    q1surplus:
        sma_em_data_type: q1surplus
        type: num

    q1surplus_counter:
        sma_em_data_type: q1surpluscounter
        type: num

    q1regard:
        sma_em_data_type: q1regard
        type: num

    q1regard_counter:
        sma_em_data_type: q1regardcounter
        type: num

    v1:
        sma_em_data_type: v1
        type: num

    thd1:
        sma_em_data_type: thd1
        type: num

    cosphi1:
        sma_em_data_type: cosphi1
        type: num

    p2surplus:
        sma_em_data_type: p2surplus
        type: num

    p2surplus_counter:
        sma_em_data_type: p2surpluscounter
        type: num

    p2regard:
        sma_em_data_type: p2regard
        type: num

    p2regard_counter:
        sma_em_data_type: p2regardcounter
        type: num

    s2surplus:
        sma_em_data_type: s2surplus
        type: num

    s2surplus_counter:
        sma_em_data_type: s2surpluscounter
        type: num

    s2regard:
        sma_em_data_type: s2regard
        type: num

    s2regard_counter:
        sma_em_data_type: s2regardcounter
        type: num

    q2surplus:
        sma_em_data_type: q2surplus
        type: num

    q2surplus_counter:
        sma_em_data_type: q2surpluscounter
        type: num

    q2regard:
        sma_em_data_type: q2regard
        type: num

    q2regard_counter:
        sma_em_data_type: q2regardcounter
        type: num

    v2:
        sma_em_data_type: v2
        type: num

    thd2:
        sma_em_data_type: thd2
        type: num

    cosphi2:
        sma_em_data_type: cosphi2
        type: num

    p3surplus:
        sma_em_data_type: p3surplus
        type: num

    p3surplus_counter:
        sma_em_data_type: p3surpluscounter
        type: num

    p3regard:
        sma_em_data_type: p3regard
        type: num

    p3regard_counter:
        sma_em_data_type: p3regardcounter
        type: num

    s3surplus:
        sma_em_data_type: s3surplus
        type: num

    s3surplus_counter:
        sma_em_data_type: s3surpluscounter
        type: num

    s3regard:
        sma_em_data_type: s3regard
        type: num

    s3regard_counter:
        sma_em_data_type: s3regardcounter
        type: num

    q3surplus:
        sma_em_data_type: q3surplus
        type: num

    q3surplus_counter:
        sma_em_data_type: q3surpluscounter
        type: num

    q3regard:
        sma_em_data_type: q3regard
        type: num

    q3regard_counter:
        sma_em_data_type: q3regardcounter
        type: num

    v3:
        sma_em_data_type: v3
        type: num

    thd3:
        sma_em_data_type: thd3
        type: num

    cosphi3:
        sma_em_data_type: cosphi3
        type: num
```
