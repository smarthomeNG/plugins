.. index:: tasmota plugin
.. index:: Plugins; tasmota
.. index:: Plugins; mqtt
.. index:: mqtt; tasmota plugin

=======
tasmota
=======

Das Plugin dienst zur Steuerung von Tasmota Devices über MQTT. Zur Aktivierung von MQTT für die Tasmota Devices
bitte die Dokumentation des jeweiligen Devices zu Rate ziehen.

Unterstützte Funktionen sind:
* Relays eines Tasmota Devices (bis zu 4)
* DS18B20 Temperatursensoren
* AM2301 Sensoren für Tempteratur und Luftfeuchte
* RGBW Dimmer (H801) mit Senden und Empfangen von HSB
* RF-Daten Senden und Empfangen mit Sonoff Bridge RF


.. attention::

    Das Plugin kommuniziert über MQTT und benötigt das mqtt neues Modul, welches die Kommunikation mit dem MQTT Broker
    durchführt. Dieses Modul muß geladen und konfiguriert sein, damit das Plugin funktioniert.


Konfiguration
=============

Für die Nutzung eines Tasmota Devices müssen in dem entsprechenden Item die zwei Attribute ``tasmota_topic`` und
``tasmota_attr`` konfiguriert werden, wie im folgenden Beispiel gezeigt:

.. code-block:: yaml

    schalter:
        type: bool
        tasmota_topic: delock_switch2
        tasmota_attr: relay

        leistung:
            type: num
            tasmota_topic: ..:.
            tasmota_attr: power


Vollständige Informationen zur Konfiguration und die vollständige Beschreibung der Item-Attribute sind
unter :doc:`/plugins_doc/config/tasmota` zu finden.


Web Interface des Plugins
=========================

Tasmota Items
-------------

Das Webinterface zeigt die Items an, für die ein Tasmota Device konfiguriert ist.

.. image:: user_doc/assets/webif_tab1.jpg
   :class: screenshot


Tasmota Devices
---------------

Das Webinterface zeigt Informationen zu den konfigurierten Tasmota Devices an, sowie etwa hinzugekommen Devices die
in SmartHomeNG noch nicht konfiguriert (mit einem Item vebunden) sind.

.. image:: user_doc/assets/webif_tab2.jpg
   :class: screenshot

Ein Klick auf das Tasmota Topic öffnet Konfigurationsseite des Devices.


Tasmota Sensoren
----------------

Das Webinterface zeigt Informationen mit Werten der Sensoren, falls das jeweilige Tasmota Device diese
Informationen bereitstellt.

.. image:: user_doc/assets/webif_tab3.jpg
   :class: screenshot

Ein Klick auf das Tasmota Topic öffnet Konfigurationsseite des Devices.


Tasmota Lights
--------------

Das Webinterface zeigt Informationen der Devices mit RGB-Steuerung an, falls das jeweilige Tasmota Device diese
Informationen bereitstellt.

.. image:: user_doc/assets/webif_tab4.jpg
   :class: screenshot

Ein Klick auf das Tasmota Topic öffnet Konfigurationsseite des Devices.


Tasmota RF
----------

Das Webinterface zeigt Informationen der Devices RF-Fähigkeit an, falls das jeweilige Tasmota Device diese
Informationen bereitstellt.

.. image:: user_doc/assets/webif_tab5.jpg
   :class: screenshot

Ein Klick auf das Tasmota Topic öffnet Konfigurationsseite des Devices.


Broker Information
------------------

Das Webinterface zeigt Informationen zum genutzten MQTT Broker an.

.. image:: user_doc/assets/webif_tab6.jpg
   :class: screenshot

