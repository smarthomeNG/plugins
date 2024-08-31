.. index:: Plugins; pcomfcloud
.. index:: pcomfcloud

==========
pcomfcloud
==========

.. image:: webif/static/img/plugin_logo.png
   :alt: plugin logo
   :width: 300px
   :height: 300px
   :scale: 50 %
   :align: left


<Hier erfolgt die allgemeine Beschreibung des Zwecks des Plugins>

|


Plugin Instanz hinzufügen
=========================

Da das Plugin ohne vorherige Konfiguration weiterer Parameter lauffähig ist, wird die Instanz beim Hinzufügen in
der Admin GUI auch gleich aktiviert und beim Neustart von SmartHomeNG geladen. Die Konfiguration erfolgt anschließend
im Web Interface.

Das Plugin unterstützt je Instanz nur eine Bridge. Dafür ist es Multi-Instance fähig, so dass bei Einsatz mehrerer
Bridges einfach mehrere Instanzen des Plugins konfiguriert werden können.


Konfiguration
=============

Die grundlegende Konfiguration des Plugins selbst, erfolgt durch das Web Interface des Plugins. Mit dem Web Interface
kann die Verbindung zu einer Bridge hergestellt werden kann. Optionale weitere Einstellungen
(z.B. default_transitionTime) können über die Admin GUI vorgenommen werden. Diese Parameter und die Informationen
zur Item-spezifischen Konfiguration des Plugins sind unter :doc:`/plugins_doc/config/hue3` beschrieben.

|



|

Web Interface
=============

Das pcomfcloud Plugin verfügt über ein Webinterface, mit dessen Hilfe die Items die das Plugin nutzen
übersichtlich dargestellt werden. Außerdem können Informationen zu den Devices angezeigt werden,
die durch die Panasonic Comfort Cloud verwaltet werden.


Aufruf des Webinterfaces
------------------------

Das Plugin kann aus der Admin GUI (von der Seite Plugins/Plugin Liste aus) aufgerufen werden. Dazu auf der Seite
in der entsprechenden Zeile das Icon in der Spalte **Web Interface** anklicken.

Außerdem kann das Webinterface direkt über ``http://smarthome.local:8383/plugin/pcomfcloud`` bzw.
``http://smarthome.local:8383/plugin/pcomfcloud_<Instanz>`` aufgerufen werden.

|

Beispiele
---------

Folgende Informationen können im Webinterface angezeigt werden:

Oben rechts werden allgemeine Parameter zum Plugin angezeigt. Die weiteren Informationen werden in den
sechs Tabs des Webinterface angezeigt.

Im ersten Tab werden die Items angezeigt, die das Plugin nutzen:

.. image:: assets/webif_tab1.jpg
   :class: screenshot


|
|

Im zweiten Tab werden Informationen zu den Leuchten angezeigt, die in der Hue Bridge bekannt sind:

.. image:: assets/webif_tab2.jpg
   :class: screenshot

|
|

Im dritten Tab werden die Szenen angezeigt, die in der Hue Bridge definiert sind:

.. image:: assets/webif_tab3.jpg
   :class: screenshot


|
|

Im vierten Tab werden die Gruppen angezeigt, die in der Hue Bridge definiert sind:

.. image:: assets/webif_tab4.jpg
   :class: screenshot


|
|

Im fünften Tab werden die Sensoren angezeigt, die in der Hue Bridge bekannt sind:

.. image:: assets/webif_tab5.jpg
   :class: screenshot

|
|

Im sechsten Tab werden die Devices angezeigt, die in der Hue Bridge bekannt sind:

.. image:: assets/webif_tab6.jpg
   :class: screenshot

|
|

Auf dem siebten Reiter werden Informationen zur Hue Bridge angezeigt. Wenn weitere Anwendungen die Bridge nutzen,
wird zusätzlich eine Liste der in der Bridge konfigurierten Benutzer/Apps angezeigt.

.. image:: assets/webif_tab7.jpg
   :class: screenshot

|
|

