.. index:: shelly plugin
.. index:: Plugins; shelly
.. index:: Plugins; mqtt
.. index:: mqtt; shelly plugin

======
shelly
======

Das Plugin dienst zur Steuerung von Shelly Devices über MQTT. Zur Aktivierung von MQTT für die Shelly Devices bitte
die Dokumentation des jeweiligen Devices zu Rate ziehen.

Zurzeit wird Schalter (Relay) Funktion folgender Shelly Devices unterstützt:

- Shellyplug
- Shellyplug-s
- Shelly1/pm
- Shelly2
- Shelly2.5
- Shelly4Pro

Es werden alle Relays eines Shelly Devices (bis zu 4) unterstützt. Weiterhin werden die folgenden
Attribute/Parameter der Devices unterstützt, soweit die Devices selbst diese unterstützen:

- power
- energy
- temperature
- temperature_f

sowie der online-Status.


.. attention::

    Das Plugin kommuniziert über MQTT und benötigt das mqtt neues Modul, welches die Kommunikation mit dem MQTT Broker
    durchführt. Dieses Modul muß geladen und konfiguriert sein, damit das Plugin funktioniert.



Web Interface des Plugins
=========================

Shelly Items
------------

Das Webinterface zeigt die Items an, für die ein Shelly Device konfiguriert ist.

.. image:: user_doc/assets/shelly-webif-items.jpg
   :class: screenshot

Der Item Wert, sowie die Zeitangaben zu letzten Update und zum letzten Change werden periodisch aktualisiert.


Shelly Devices
--------------

Das Webinterface zeigt Informationen zu den konfigurierten Shelly Devices an, sowie etwa hinzugekommen Devices die
in SmartHomeNG noch nicht konfiguriert (mit einem Item vebunden) sind.

.. image:: user_doc/assets/shelly-webif-devices.jpg
   :class: screenshot


Broker Information
------------------

Das Webinterface zeigt Informationen zum genutzten MQTT Broker an.

.. image:: user_doc/assets/shelly-webif-brokerinfo.jpg
   :class: screenshot

