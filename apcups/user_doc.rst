.. index:: Plugins; apcups
.. index:: apcups


===============================
apcups
===============================


.. image:: webif/static/img/plugin_logo.png
   :alt: plugin logo
   :width: 300px
   :height: 300px
   :scale: 50 %
   :align: left

<Hier erfolgt die allgemeine Beschreibung des Zwecks des Plugins>


Anforderungen
=============

Ein laufender ``apcupsd`` mit einem konfigurierten Netserver (NIS) ist notwendig. Dieser kann lokal oder remote laufen.
Das Plugin fragt Laufzeitdaten vom apcupsd über das Hilfsprogramm ``apcaccess`` ab. Aus diesem Grund muss das ``apcups`` Package auch lokal installiert sein.
Wenn der Daemon lokal installiert ist, sollte die Datei ``/etc/apcupsd/apcupsd.conf`` noch folgende Informationen beinhalten:

::

   NETSERVER on
   NISPORT 3551
   NISIP 127.0.0.1

Unterstützte Geräte
-------------------

Aollte mit allen APC UPS Geräten funktionieren die den apcupsd unterstützen. Getestet wurde nur mit einer **smartUPS**.


Konfiguration
=============

Die Plugin Parameter und die Informationen zur Item-spezifischen Konfiguration des Plugins sind
unter :doc:`/plugins_doc/config/apcups` beschrieben.


plugin.yaml
-----------

Zu den Informationen, welche Parameter in der ../etc/plugin.yaml konfiguriert werden können bzw. müssen, bitte
bitte die Dokumentation :doc:`Dokumentation </plugins_doc/config/apcups>` lesen, die aus
den Metadaten der plugin.yaml erzeugt wurde (siehe oben).

items.yaml
----------

Zu den Informationen, welche Attribute in der Item Konfiguration verwendet werden können bzw. müssen, bitte
bitte die Dokumentation :doc:`Dokumentation </plugins_doc/config/apcups>` lesen, die aus
den Metadaten der plugin.yaml erzeugt wurde (siehe oben).

Es gibt nur ein einziges Attribut ``apcups``. Die Namen für den Statusabruf können über den Befehl ``apcaccess`` auf der Kommandozeile
abgerufen werden. Damit wird eine Liste der Art ``Statusname : Wert`` angezeigt.

Der Wert der dem ``apcups`` Item Attribut als Parameter übergeben wird ist dieser Statusname. Dem Item wird dann dieser Wert zugewiesen.

::

   APC      : 001,050,1127
   DATE     : 2017-11-02 07:59:15 +0100
   HOSTNAME : sh11
   VERSION  : 3.14.12 (29 March 2014) debian
   UPSNAME  : UPS_IDEN
   CABLE    : Ethernet Link
   DRIVER   : PCNET UPS Driver
   UPSMODE  : Stand Alone
   STARTTIME: 2017-11-02 07:59:11 +0100
   MODEL    : Smart-UPS 1400 RM
   STATUS   : ONLINE
   LINEV    : 227.5 Volts
   LOADPCT  : 31.2 Percent
   BCHARGE  : 100.0 Percent
   TIMELEFT : 30.0 Minutes
   MBATTCHG : 10 Percent
   MINTIMEL : 5 Minutes
   MAXTIME  : 0 Seconds
   MAXLINEV : 227.5 Volts
   MINLINEV : 226.0 Volts
   OUTPUTV  : 227.5 Volts
   SENSE    : High
   DWAKE    : 0 Seconds
   DSHUTD   : 120 Seconds
   DLOWBATT : 2 Minutes
   LOTRANS  : 208.0 Volts
   HITRANS  : 253.0 Volts
   RETPCT   : 0.0 Percent
   ITEMP    : 25.6 C
   ALARMDEL : Low Battery
   BATTV    : 27.7 Volts
   LINEFREQ : 49.8 Hz
   LASTXFER : Line voltage notch or spike
   NUMXFERS : 0
   TONBATT  : 0 Seconds
   CUMONBATT: 0 Seconds
   XOFFBATT : N/A
   SELFTEST : NO
   STESTI   : 336
   STATFLAG : 0x05000008
   REG1     : 0x00
   REG2     : 0x00
   REG3     : 0x00
   MANDATE  : 08/16/00
   SERIALNO : GS0034003173
   BATTDATE : 06/20/15
   NOMOUTV  : 230 Volts
   NOMBATTV : 24.0 Volts
   EXTBATTS : 0
   FIRMWARE : 162.3.I
   END APC  : 2017-11-02 08:00:39 +0100

Das Plugin führt eine automatische Typumwandlung durch entsprechend dem verwendeten Item Typ.
Bei der Umwandlung in einen numerischen Wert wird nach dem ersten Leerzeichen abgeschnitten und dann konvertiert.
Aus ``235 Volt`` wird also ``235``

logic.yaml
----------

Zu den Informationen, welche Konfigurationsmöglichkeiten für Logiken bestehen, bitte
bitte die Dokumentation :doc:`Dokumentation </plugins_doc/config/apcups>` lesen, die aus
den Metadaten der plugin.yaml erzeugt wurde (siehe oben).

Funktionen
----------

Zu den Informationen, welche Funktionen das Plugin bereitstellt (z.B. zur Nutzung in Logiken), bitte
bitte die Dokumentation :doc:`Dokumentation </plugins_doc/config/apcups>` lesen, die aus
den Metadaten der plugin.yaml erzeugt wurde (siehe oben).

<Hier können bei Bedarf ausführliche Beschreibungen zu den Funktionen dokumentiert werden.>

|

Beispiele
=========

Beispiel
~~~~~~~

The example below will read the keys **LINEV**, **STATUS** and
**TIMELEFT** and returns their values.

.. code:: yaml

   # items/apcups.yaml
   serverroom:

       apcups:

           linev:
               visu_acl: ro
               type: num
               apcups: linev

           status:
               # will be 'ONLINE', 'ONBATT', or in case of a problem simply empty
               visu_acl: ro
               type: str
               apcups: status

           timeleft:
               visu_acl: ro
               type: num
               apcups: timeleft

**type** depends on the values.

Status Report Fields
~~~~~~~~~~~~~~~~~~~~

Due to a look into this
http://apcupsd.org/manual/manual.html#configuration-examples file the
meaning of the above variables are as follows

::

   APC
       Header record indicating the STATUS format revision level, the number of records that follow the APC statement, and the number of bytes that follow the record.
   DATE
       The date and time that the information was last obtained from the UPS.
   HOSTNAME
       The name of the machine that collected the UPS data.
   UPSNAME
       The name of the UPS as stored in the EEPROM or in the UPSNAME directive in the configuration file.
   VERSION
       The apcupsd release number, build date, and platform.
   CABLE
       The cable as specified in the configuration file (UPSCABLE).
   MODEL
       The UPS model as derived from information from the UPS.
   UPSMODE
       The mode in which apcupsd is operating as specified in the configuration file (UPSMODE)
   STARTTIME
       The time/date that apcupsd was started.
   STATUS
       The current status of the UPS (ONLINE, ONBATT, etc.)
   LINEV
       The current line voltage as returned by the UPS.
   LOADPCT
       The percentage of load capacity as estimated by the UPS.
   BCHARGE
       The percentage charge on the batteries.
   TIMELEFT
       The remaining runtime left on batteries as estimated by the UPS.
   MBATTCHG
       If the battery charge percentage (BCHARGE) drops below this value, apcupsd will shutdown your system. Value is set in the configuration file (BATTERYLEVEL)
   MINTIMEL
       apcupsd will shutdown your system if the remaining runtime equals or is below this point. Value is set in the configuration file (MINUTES)
   MAXTIME
       apcupsd will shutdown your system if the time on batteries exceeds this value. A value of zero disables the feature. Value is set in the configuration file (TIMEOUT)
   MAXLINEV
       The maximum line voltage since the UPS was started, as reported by the UPS
   MINLINEV
       The minimum line voltage since the UPS was started, as returned by the UPS
   OUTPUTV
       The voltage the UPS is supplying to your equipment
   SENSE
       The sensitivity level of the UPS to line voltage fluctuations.
   DWAKE
       The amount of time the UPS will wait before restoring power to your equipment after a power off condition when the power is restored.
   DSHUTD
       The grace delay that the UPS gives after receiving a power down command from apcupsd before it powers off your equipment.
   DLOWBATT
       The remaining runtime below which the UPS sends the low battery signal. At this point apcupsd will force an immediate emergency shutdown.
   LOTRANS
       The line voltage below which the UPS will switch to batteries.
   HITRANS
       The line voltage above which the UPS will switch to batteries.
   RETPCT
       The percentage charge that the batteries must have after a power off condition before the UPS will restore power to your equipment.
   ITEMP
       Internal UPS temperature as supplied by the UPS.
   ALARMDEL
       The delay period for the UPS alarm.
   BATTV
       Battery voltage as supplied by the UPS.
   LINEFREQ
       Line frequency in hertz as given by the UPS.
   LASTXFER
       The reason for the last transfer to batteries.
   NUMXFERS
       The number of transfers to batteries since apcupsd startup.
   XONBATT
       Time and date of last transfer to batteries, or N/A.
   TONBATT
       Time in seconds currently on batteries, or 0.
   CUMONBATT
       Total (cumulative) time on batteries in seconds since apcupsd startup.
   XOFFBATT
       Time and date of last transfer from batteries, or N/A.
   SELFTEST

       The results of the last self test, and may have the following values:

           OK: self test indicates good battery
           BT: self test failed due to insufficient battery capacity
           NG: self test failed due to overload
           NO: No results (i.e. no self test performed in the last 5 minutes)

   STESTI
       The interval in hours between automatic self tests.
   STATFLAG
       Status flag. English version is given by STATUS.
   DIPSW
       The current dip switch settings on UPSes that have them.
   REG1
       The value from the UPS fault register 1.
   REG2
       The value from the UPS fault register 2.
   REG3
       The value from the UPS fault register 3.
   MANDATE
       The date the UPS was manufactured.
   SERIALNO
       The UPS serial number.
   BATTDATE
       The date that batteries were last replaced.
   NOMOUTV
       The output voltage that the UPS will attempt to supply when on battery power.
   NOMINV
       The input voltage that the UPS is configured to expect.
   NOMBATTV
       The nominal battery voltage.
   NOMPOWER
       The maximum power in Watts that the UPS is designed to supply.
   HUMIDITY
       The humidity as measured by the UPS.
   AMBTEMP
       The ambient temperature as measured by the UPS.
   EXTBATTS
       The number of external batteries as defined by the user. A correct number here helps the UPS compute the remaining runtime more accurately.
   BADBATTS
       The number of bad battery packs.
   FIRMWARE
       The firmware revision number as reported by the UPS.
   APCMODEL
       The old APC model identification code.
   END APC
       The time and date that the STATUS record was written.


|

Web Interface
=============

Aktuell hat das Plugin kein Webinterface

Tab 1: <Name des Tabs>
----------------------

<Hier wird der Inhalt und die Funktionalität des Tabs beschrieben.>

.. image:: assets/webif_tab1.jpg
   :class: screenshot

<Zu dem Tab ist ein Screenshot im Unterverzeichnis ``assets`` des Plugins abzulegen.

|

Version History
===============

<In diesem Abschnitt kann die Versionshistorie dokumentiert werden, falls der Plugin Autor dieses möchte.
Diese Abschnitt ist optional.>


