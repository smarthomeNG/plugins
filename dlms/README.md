# DLMS

# Requirements

* smartmeter using DLMS (Device Language Message Specification) IEC 62056-21
* USB IR-Reader e.g. from volkszaehler.org

install by
<pre>
$ sudo apt-get install python3-serial
</pre>

for python 3.4.4 onwards use
<pre>
sudo python3 -m pip install pyserial
</pre>

make sure the serial port can be used by the user executing smarthome.py

Example for a recent version of the Volkszaehler IR-Reader, please adapt the vendor- and product-id for your own readers:
<pre>
echo 'SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", ATTRS{serial}=="0092C9FE", MODE="0666", GROUP="dialout", SYMLINK+="dlms0"' > /etc/udev/rules.d/11-dlms.rules
udevadm trigger
</pre>
If you like, you can also give the serial port a descriptive name with this.

## Supported Hardware

* smart meters using using DLMS (Device Language Message Specification) IEC 62056-21
* e.g. Landis & Gyr ZMD120

# Configuration

## plugin.conf

<pre>
[dlms]
    class_name = DLMS
    class_path = plugins.dlms
    serialport = /dev/dlms0
#    update_cycle = 20
</pre>

Description of the attributes:

* __serialport__: gives the serial port for the dlms query
* __update_cycle__: interval in seconds how often the data is read from the meter - be careful not to set a shorter interval than a read operation takes (default: 60)


## Setup procedure:

Start the plugin in standalone mode from the plugins directory e.g. **/usr/local/smarthome/plugins/dlms** with
**python3 __init__.py _serialport_**

If you need also the time values, start in verbose mode with 
**python3 __init__.py _serialport_ x**

Copy the given obis codes to your item configuration to help generate items as needed

## items.conf

You can use all obis codes available by the meter.

Attributes:
* __dlms_obis_code__: obis code such as 'x.y', 'x.y.z' or 'x.y.z*q'
 
<pre>
# Actual OBIS Codes for a real existing smartmeter (short version)
#
# 0.0.0(50871031)
# 0.0.1(50871031)
# 0.1.0(09)
# 0.1.2(0000)
# 0.1.3(160501)
# 0.2.0(B32)                      Configuration program version number
# 0.2.1(005)                      Parameter record number
# 0.2.8(F84F)
# 0.9.1(160353)                   Local Time at readout
# 0.9.2(160511)                   Local Date at readout
# 1.2.1(0194.29*kW)
# 1.2.2(0194.29*kW)
# 1.6.1(24.31*kW)(1605041345)
# 1.6.2(24.31*kW)(1605041345)
# 1.8.0(00023804*kWh)
# 1.8.1(00021271*kWh)
# 1.8.2(00002533*kWh)
# 2.2.1(0022.48*kW)
# 2.2.2(0022.48*kW)
# 2.6.1(06.00*kW)(1605051345)
# 2.6.2(06.00*kW)(1605051345)
# 2.8.0(00000552*kWh)
# 2.8.1(00000552*kWh)
# 2.8.2(00000000*kWh)
# 3.8.0(00021664*kvarh)
# 3.8.1(00021201*kvarh)
# 3.8.2(00000463*kvarh)
# 4.8.0(00000283*kvarh)
# 4.8.1(00000282*kvarh)
# 4.8.2(00000001*kvarh)
# C.3.1(___-----)
# C.3.2(__------)
# C.3.3(__------)
# C.3.4(--__5_--)
# C.4.0(60C00183)
# C.5.0(0020E0F0)
# C.7.0(00000017)
# F.F(00000000)

# if readout with verbose mode you will get time series as well, e.g.
#
# 1.6.2(25.29)(1610200845)
# 1.6.2*14(26.60)(1609051415)
# 1.6.2*13(30.53)(1608111515)
# 1.6.2*12(29.41)(1607081530)
# 1.6.2*11(29.41)(1606291130)
# 1.6.2*10(28.62)(1605260945)
# 1.6.2*09(28.27)(1604271015)
# 1.6.2*08(28.75)(1603151100)
# 1.6.2*07(27.79)(1602231415)
# 1.6.2*06(28.38)(1601051445)
# 1.6.2*05(27.23)(1512171100)
# 1.6.2*04(27.73)(1511051500)
# 1.6.2*03(26.14)(1510221000)
# 1.6.2*02(00.00)(0000000000)
# 1.6.2*01(00.00)(0000000000)           dlms_obis_code = 1.6.2*01 to get the first value in parentheses 
#                                   and dlms_obis_code = 1.6.2*01~1 to get the date value in parentheses
# 1.6.2*00(00.00)(0000000000)
#
# you can give the exact obis code

[Smartmeter]
    [[Serialnumber]]
        type = foo
        dlms_obis_code = 0.0.0
    [[Serialnumber_B]]
        type = foo
        dlms_obis_code = 0.0.1

    [[Ablesung]]
        # Date and time of last readout
        [[[Uhrzeit]]]
            type = foo
            dlms_obis_code = 0.9.1
        [[[Date]]]
            type = foo
            dlms_obis_code = 0.9.2
        [[Date_current_month]]
            type = foo
            dlms_obis_code = 0.1.3
        [[Month]]
            # Billing period counter
            type = num
            dlms_obis_code = 0.1.0
            
    [[Import]]
        [[[Energy]]]
            type = num
            sqlite = yes
            dlms_obis_code = 1.8.1
        [[[Peak]]]
            # actual month
            type = num
            dlms_obis_code = 1.6.2
        [[[Peak_Date]]]
            # actual month
            type = num
            dlms_obis_code = 1.6.2~1
            
        # other entries for last 15 months
        [[[Peak_1]]]
            type = num
            dlms_obis_code = 1.6.2*01
        [[[Peak_1_Date]]]
            type = num
            dlms_obis_code = 1.6.2*01~1
        [[[Peak_2]]]
            type = num
            dlms_obis_code = 1.6.2*02
        [[[Peak_2_Date]]]
            type = num
            dlms_obis_code = 1.6.2*02~1

    [[Export]]
        [[[Energy]]]
            type = num
            sqlite = yes
            dlms_obis_code = 2.8.1
            
</pre>

# Some background information

<pre>
OBIS codes are a combination of six value groups, which describe in a hierarchical way 
the exact meaning of each data item
A:  characteristic of the data item to be identified (abstract data, electricity-, gas-, heat-, water-related data)
B:  channel number, i.e. the number of the input of a metering equipment having several inputs for the measurement 
    of energy of the same or different types (e.g. in data concentrators, registration units). 
    Data from different sources can thus be identified. The definitions for this value group are independent from the value group A.
C:  abstract or physical data items related to the information source concerned, 
    e.g. current , voltage , power, volume, temperature. The definitions depend on the value of the value group A . 
    Measurement, tariff processing and data storage methods of these quantities are defined by value groups D, E and F
    For abstract data, the hierarchical structure of the 6 code fields is not applicable.
D:  types, or the result of the processing of physical quantities identified with the 
    value groups A and C, according to various specific algorithms. The algorithms can deliver energy and
    demand quantities as well as other physical quantities.
E:  further processing of measurement results identified with value groups A to D to tariff registers, 
    according to the tariff(s) in use. For abstract data or for measurement results for which tariffs are not relevant, 
    this value group can be used for further classification.
F:  the storage of data, identified by value groups A to E, according to different billing periods.
    Where this is not relevant, this value group can be used for further classification.
</pre>

## Manufacturer specific codes

If any value group C to F contains a value between 128 and 254, the whole code is considered as manufacturer specific.

Some value groups may be suppressed, if they are not relevant to an application, so optional value groups are A, B, E, F

A-B:C.D.E*F

<pre>
OBIS lines         parsing results  A   B   C   D   E   Sep F   data[0]     data[1]
----------------------------------------------------------------------------------------
1-1:F.F(00000000)                   1   1   F   F               (00000000)  
1-1:0.0.0(50871031)                 1   1   0   0   0           (50871031)
1-1:1.6.1(24.81*kW)(1604070900)     1   1   1   6   1           (24.81*kW)  (1604070900)
1-1:1.6.1*03(26.14)(1510221000)     1   1   1   6   1   *   03  (26.14)     (1510221000)
1-1:1.6.1&02(00.00)(0000000000)     1   1   1   6   1   &   02  (00.00)     (0000000000)
1-1:3.8.2*08(00000372)              1   1   3   8   2   *   08  (00000372)
</pre>