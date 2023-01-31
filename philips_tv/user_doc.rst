.. index:: Plugins; philips_tv
.. index:: philips_tv

==========
philips_tv
==========

.. image:: webif/static/img/plugin_logo.png
   :alt: plugin logo
   :width: 300px
   :height: 300px
   :scale: 50 %
   :align: left

Konfiguration
=============

SmarthomeNG plugin, mit Unterstützung für Philips TVs mit OAuth Identifizierung.

Die Informationen zur Konfiguration des Plugins sind unter :doc:`/plugins_doc/config/philips_tv` beschrieben.

Requirements
=============
- requests

Supported Hardware
==================
Philips Smart TV mit OAuth Identifizierung


Web Interface
=============

Das philips_tv Plugin verfügt über ein Webinterface, um  für Philips TV das OAuth2 Authentifizierungsverfahren direkt durchzuführen und die Anmeldedaten (user + password) direkt in die Konfiguration (plugin.yaml) zu uebernehmen.


Aufruf des Webinterfaces
------------------------

Das Plugin kann aus dem Admin Interface aufgerufen werden. Dazu auf der Seite Plugins in der entsprechenden
Zeile das Icon in der Spalte **Web Interface** anklicken.

Außerdem kann das Webinterface direkt über ``http://smarthome.local:8383/philips_tv`` aufgerufen werden.


Beispiele
---------

Folgende Informationen können im Webinterface angezeigt werden:

Im ersten Tab Philips OAuth2 findet sich direkt die Schritt fuer Schritt Anleitung zur OAuth2 Authentifizierung. 

Changelog
---------
V1.9.6     Initial plugin version