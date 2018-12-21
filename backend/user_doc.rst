.. index:: Plugins; backend (Backend Administrationsoberfläche)
.. index:: backend

backend
#######

Konfiguration
=============

Die Informationen zur Konfiguration des Plugins sind unter :doc:`/plugins_doc/config/backend` beschrieben.


Web Interface
=============

Das backend Plugin verfügt über ein Webinterface, mit dessen Hilfe die Items die das Plugin nutzen
übersichtlich dargestellt werden. Außerdem können Statistiken über die KNX Aktivität angezeigt
werden.


Aufruf des Webinterfaces
------------------------

Das Plugin kann aus dem backend aufgerufen werden. Dazu auf der Seite Plugins in der entsprechenden
Zeile das Icon in der Spalte **Web Interface** anklicken.

Außerdem kann das Webinterface direkt über ``http://smarthome.local:8383/backend``.


Beispiele
---------

Das Backend Plugin liefert zahlreiche Infroamtionen, die zum Beispiel bei der Fehlersuche
hilfreich sind. Inzwischen kann man damit auch eine Reihe von Administrationsaufgaben erledigen.

.. image:: assets/backend_systeminfo.jpg
   :class: screenshot

Genauer ist das unter :doc:`/backend/backend` beschrieben.

Die Konfiguration de Plugins ist unter :doc:`/plugins_doc/config/backend` ausführlich beschrieben.


.. toctree::
   :maxdepth: 4
   :hidden:
   :titlesonly:

   user_doc/backend
   user_doc/items
   user_doc/logiken
