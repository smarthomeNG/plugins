.. index:: Plugins; fronius
.. index:: fronius

=======
fronius
=======

.. image:: webif/static/img/plugin_logo.png
   :alt: plugin logo
   :width: 300px
   :height: 300px
   :scale: 50 %
   :align: left

Das Plugin dient zum Anschluss von Solarwechselrichtern der
Firma Fronius an smarthomeNG. Es liest die Information des
Wechselrichters über das REST API aus. Der Wechselrichter
wird mit konstantem Zyklus abgefragt. Die zurückgegebenen
JSON Container werden in smarthome Items umgesetzt.

Unterstützte Geräte
===================

Fronius Symo GEN24


Konfiguration
=============

Die Pluginparameter und die Informationen zur Item-spezifischen Konfiguration des Plugins sind
unter :doc:`/plugins_doc/config/fronius` beschrieben.

plugin.yaml
-----------

Nachfolgend eine Beispielkonfiguration:

.. code-block:: yaml

    fronius:
        plugin_name: fronius
        poll_cycle: 10
        ip_address: 192.168.1.181
        data_file: /usr/local/smarthome/var/db/fronius.txt

items.yaml
----------

Items für das plugins müssen den Eintrag ``sim: track`` enthalten. Es gibt
folgendes Einträge:

- soc: Ladezustand der Batterie
- p_pv: Aktuelle PV Leistung
- p_grid: Aktuelle Leistung vom Netz
- p_accu: Aktuelle Leistung aus der Batterie
- p_load: Aktueller Verbrauch der Hauses
- p_pv_day: Aktuell erzeugte Energie des Tages
- p_pv_day_database: Item für Tagesenergie in der Datenbank


Nachfolgend eine Beispielkonfiguration:

.. code-block:: yaml

    Solar:
      BatterySOC:
        type: num
        fronius_data: soc
      BatteryPower:
        type: num
        fronius_data: p_accu
      SolarPower:
        type: num
        fronius_data: p_pv
      SolarDailyPower:
        type: num
        fronius_data: p_pv_day
      SolarDailyPowerDatabase:
        type: num
        database: yes
        fronius_data: p_pv_day_database
      HousePower:
        type: num
        database: yes
        fronius_data: p_load

Tagesenergie
------------

Umrichter der Serie GEN24 geben über das REST API keine Energiesummen aus.
Das plugin berechnet sie daher selber. Dazu wird die PV Leistung p_pv über
die Zeit aufintegriert. Die dabei berechnete Energie kann stets aktuell
über p_pv_day abgefragt werden. Damit der Wert einen Reset übersteht wird
er ein einer Datei gespeichert.
Zu Mitternacht wird der Wert p_pv_day auf den Wert p_pv_day_database kopiert
und zu Null gesetzt. Somit kann der nächste Tage gezählt werden. Der Wert
p_pv_day_database kann in der Datenbank gespeichert werden. Dann hat man
eine Statistik über die Tagesenergie.


Web Interface
=============

Das Plugin stellt ein WebIF zur Verfügung, in dem alle mit dem Plugin verknüpften Items gelistet sind.
