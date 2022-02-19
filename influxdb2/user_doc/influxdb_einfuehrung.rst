
InfluxDB Einführung
===================

Was ist InfluxDB?
-----------------

Bei InfluxDB handelt es sich um eine spezialisierte Datenbank des Unternehmens InfluxData, die ihre Priorität anders
als relationale Datenbanken wie MySQL und MariaDB oder strukturierte Datenbanken wie Redis auf eine maximale Effizienz
bei begrenzter Komplexität setzt. Die Software steht unter einer Open Source Lizenz.

Zu den Merkmalen von InfluxDB zählen unter anderem:

- Spezialisierung auf Zeitreihen
- Kombination mehrerer Quellen in einer zentralen Instanz
- Sehr hohe Effizienz bei der Verarbeitung
- Erfassung von Daten aus unterschiedlichen Quellen etwa über die API von Drittanbietern


Was ist ein Bucket?
-------------------

Ein Bucket ist ein benannter Speicherort innerhalb von InfluxDB. Ein Bucket hat eine Aufbewahrungsrichtlinie,
die für die im Bucket gespeicherten Zeitreihendaten, festlegt wie lange die Daten in der InfluxDB aufbewahrt
werden sollen.


Fields und Tags
---------------

...
