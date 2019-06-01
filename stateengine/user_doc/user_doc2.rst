.. index:: Plugins; Stateengine
.. index:: Stateengine; Konfiguration

Konfiguration
#############

.. important::

      Detaillierte Informationen zur Konfiguration des Plugins sind unter :doc:`/plugins_doc/config/stateengine` zu finden.

.. rubric:: Pluginkonfiguration
   :name: pluginkonfiguration

.. code-block:: yaml

   #etc/plugin.yaml
   stateengine:
       plugin_name: stateengine
       #startup_delay_default: 10
       #suspend_time_default: 3600
       #log_level: 0
       #log_directory: var/log/StateEngine/
       #log_maxage: 0

.. rubric:: Logging
  :name: logging

Es gibt zwei Möglichkeiten, den Output des Plugins zu loggen:
**intern**
Hierbei werden, sofern das Loglevel 1 oder 2 beträgt, sämtliche Logeinträge in eigene Dateien in einem selbst definierten Verzeichnis geschrieben.

**logging.yaml**
Sowohl der Output des Plugins generell, als auch der Einträge für bestimmte Items können in der logging.yaml Datei wie folge deklariert werden:

.. code-block:: yaml

  #etc/logging.yaml
  stateengine_file:
      class: logging.handlers.TimedRotatingFileHandler
      formatter: shng_simple
      level: DEBUG
      utc: false
      when: midnight
      backupCount: 7
      filename: ./var/log/stateengine.log
      encoding: utf8

  plugins.stateengine:
      # Default logger for SmartHomeNG plugins
      handlers: [shng_details_file]
      level: ERROR

  plugins.stateengine.licht:
      # Default logger for SmartHomeNG plugins
      handlers: [stateengine_file]
      level: DEBUG

Das obige Beispiel würde in die Datei var/log/stateengine.log sämtliche Debug Information schreiben, die für das Item und dessen Unteritem relevant sind,
also z.B. sämtliche Lichter. Zusätzlich werden alle Fehlermeldungen in die Datei smarthome-details.log geschrieben.
