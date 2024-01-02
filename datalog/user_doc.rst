.. index:: Plugins; datalog
.. index:: datalog

=======
datalog
=======

.. image:: webif/static/img/plugin_logo.svg
   :alt: plugin logo
   :width: 300px
   :height: 300px
   :scale: 50 %
   :align: left

Plugin zum Auslagern der Itemdaten in Dateien auf dem Dateisystem. Es kann verwendet werden,
um verschiedene Logs und Protokollmuster zu konfigurieren und diese den
Items zuzuweisen.

Konfiguration
=============

.. important::

      Detaillierte Informationen zur Konfiguration des Plugins sind unter :doc:`/plugins_doc/config/datalog` zu finden.

plugin.yaml
-----------

.. code-block:: yaml

   datalog:
       plugin_name: datalog
   #    path: var/log/data
   #    filepatterns:
   #      - default:{log}-{year}-{month}-{day}.csv
   #      - yearly:{log}-{year}.csv
   #    logpatterns:
   #      - csv:{time};{item};{value}\n
   #    cycle: 300

Dies wird die Protokolle ``default`` und ``yearly`` einrichten, die das
konfigurierte Muster verwenden, um den Zieldateinamen (Schlüssel-Wert-Paare) zu erstellen. Das
``default`` Protokoll wird automatisch konfiguriert, wenn keine Dateimuster angegeben werden.

Zusätzlich werden die Muster, die verwendet werden sollen, um die Daten in die Dateien zu protokollieren, ebenfalls dort konfiguriert. Die Schlüssel-Wert-Paare spezifizieren die Dateierweiterung
und das zu verwendende Log-Muster. In diesem Beispiel werden alle Logdateien
mit der Endung ``.csv`` unter Verwendung des konfigurierten Musters protokolliert. Das obere Beispiel ist
auch die Standardvorgabe, wenn in der Konfiguration keine Log-Muster angegeben werden.

Beide Einstellungen können einige Platzhalter verwenden (siehe unten).

Der Parameter path kann verwendet werden, um in einem anderen Pfad als dem
Standardpfad zu protokollieren, und der Parameter cycle definiert das Intervall, in dem
die Daten in die Logdateien zu übertragen sind. Der Standardwert ist 300 Sekunden.

Platzhalter, die beim Attribut ``logpatterns`` verwendet werden können:

-  ``time``: String der aktuellen Uhrzeit im Format HH:MM:SS
-  ``stamp``: UNIX Zeitstempel der aktuellen Zeit
-  ``item``: die Item-ID
-  ``value``: der Wert des Items

items.yaml
----------

.. code-block:: yaml

   some:
       item1:
           type: str
           datalog: default
       item2:
           type: num
           datalog:
             - default
             - custom
       item3:
           type: num
           datalog: custom

Sobald sich item1 ändert, wird ein Eintrag in das default Log geschrieben. Beim Ändern
von item2, werden Einträge in das default und custom Log geschrieben und beim item3 in das custom Log.

Web Interface
=============

Das Plugin beinhaltet kein Web Interface.
