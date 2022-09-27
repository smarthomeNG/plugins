.. index:: Plugins; solarforecast (Solarforecast REST API Unterstützung)
.. index:: solarforecast

=======
solarforecast
=======

Dieses Plugin unterstützt Solare.forecast Vorhersagen von Solaretrag (Leistung).

Für weitere Informationen empfiehlt sich die Lektüre der offiziellen
`Solar.forecast API Dokumentation <https://doc.forecast.solar/doku.php?id=start>`_

Konfiguration
=============

Die Informationen zur Konfiguration des Plugins sind unter :doc:`/plugins_doc/config/solarforecast` beschrieben.

Requirements
============

The plugin does not need a license key in public mode. An API key can be optained, which is optional.


Beispiele
=========

Beispiel für jeweils zwei Items mit vorhergesagtem Leistungsertrag f�r heute und morgen.

.. code:: yaml

solarforecast:

    today:
        type: num
        visu_acl: ro
        solarforecast_attribute: power_today
            
        date:
            type: str
            visu_acl: ro
            solarforecast_attribute: date_today

    tomorrow:
        type: num
        visu_acl: ro
        solarforecast_attribute: power_tomorrow

        date:
            type: str
            visu_acl: ro
            solarforecast_attribute: date_tomorrow


Web Interface
=============

Das solarforecast Plugin verfügt über ein Webinterface.

.. important::

   Das Webinterface des Plugins kann mit SmartHomeNG v1.4.2 und davor **nicht** genutzt werden.
   Es wird dann nicht geladen. Diese Einschränkung gilt nur für das Webinterface. Ansonsten gilt
   für das Plugin die in den Metadaten angegebene minimale SmartHomeNG Version.


Aufruf des Webinterfaces
------------------------

Das Plugin kann aus dem Admin Interface aufgerufen werden. Dazu auf der Seite Plugins in der entsprechenden
Zeile das Icon in der Spalte **Web Interface** anklicken.

Außerdem kann das Webinterface direkt über ``http://smarthome.local:8383/solarforecast`` aufgerufen werden.


