
Konfiguration des Plugins
=========================

*** Ausgelagert ***

Item structs
------------

Zur Vereinfachung der Einrichtung von Items sind für folgende Shelly Devices Item-structs vordefiniert:

- shellyplug
- shellyplug_s
- shellyht
- shellyflood

Unter Verwendung der entsprechenden Vorlage kann die Einrichtung einfach durch Angabe der shally_id des
entsprechenden Devices erfolgen:

.. code:: yaml

    plug1:
        name: Mein erster Shellyplug-S
        type: bool
        shelly_id: '040BD0'
        struct: shelly.shellyplug_s


Damit werden außer dem Schalter selbst, Unteritems für Online-Status, Leistung, Energieverbrauch und Temperatur
des Devices (in °C und °F) angelegt.


weitere Informationen
---------------------

Informationen zur Konfiguration und die vollständige Beschreibung der Item-Attribute sind
unter :doc:`/plugins_doc/config/shelly` zu finden.

