
.. index:: database; PostgreSQL installieren
.. index:: database; TimescaleDB installieren

.. role:: bluesup

=====================================================
PostgreSQL/TimescaleDB Installation :bluesup:`Neu`
=====================================================

Diese Seite beschreibt die Installation und Grundeinrichtung eines PostgreSQL Servers, optional
erweitert um die `TimescaleDB <https://www.tigerdata.com>`__ Extension, für die Nutzung mit dem
``database`` Plugin.

.. note::

   PostgreSQL kann auch **ohne** die TimescaleDB Erweiterung genutzt werden - dann verhält es sich
   funktional wie MySQL/MariaDB, nur mit einem anderen Server. Details zu den TimescaleDB
   Zusatzfunktionen (Kompression, native Aggregation, native Aufbewahrungsfristen) sind im
   Abschnitt "PostgreSQL+TimescaleDB Unterstützung" in :doc:`../user_doc` beschrieben.

PostgreSQL installieren
========================

PostgreSQL selbst ist auf aktuellen Debian- und Ubuntu-Versionen im Standard-Repository enthalten
und wird wie folgt installiert:

.. code-block:: bash

   sudo apt-get install postgresql postgresql-contrib

Mit dem folgenden Befehl kann kontrolliert werden, ob der Server läuft:

.. code-block:: bash

   systemctl status postgresql

Anschließend wird eine Datenbank und ein eigener Benutzer für SmartHomeNG angelegt (Passwort bitte
durch ein eigenes ersetzen):

.. code-block:: bash

   sudo -u postgres psql -c "CREATE USER shng WITH PASSWORD 'shng_password';"
   sudo -u postgres psql -c "CREATE DATABASE shng OWNER shng;"

Wer nur PostgreSQL ohne TimescaleDB nutzen möchte, kann den folgenden Abschnitt überspringen - das
Plugin funktioniert auch mit einem reinen PostgreSQL-Server, nur ohne die oben verlinkten
TimescaleDB-Zusatzfunktionen.

TimescaleDB Erweiterung installieren
======================================

.. important::

   Die TimescaleDB Paketquelle veröffentlicht (Stand: Erstellung dieser Anleitung) Pakete nur bis
   einschließlich Debian bookworm (12), noch nicht für trixie (13).

   Bis eine offizielle trixie-Unterstützung existiert, kann die bookworm-Paketquelle genutzt
   werden - die Pakete sind gegen die jeweilige PostgreSQL-Hauptversion gebaut, nicht fest an eine
   Debian-Version gebunden. Dies ist ein inoffizieller Workaround, keine von TimescaleDB offiziell
   unterstützte Konfiguration. Vor der praktischen Nutzung sollte auf
   `der offiziellen Installationsseite <https://www.tigerdata.com/docs/get-started/choose-your-path/install-timescaledb>`__
   geprüft werden, ob sich daran etwas geändert hat.

Einrichtung der Paketquelle (mit explizit gesetztem ``bookworm`` statt der über ``lsb_release``
ermittelten Debian-Kennung, siehe Hinweis oben):

.. code-block:: bash

   sudo apt-get install gnupg postgresql-common apt-transport-https lsb-release wget
   echo "deb https://packagecloud.io/timescale/timescaledb/debian/ bookworm main" | sudo tee /etc/apt/sources.list.d/timescaledb.list
   wget --quiet -O - https://packagecloud.io/timescale/timescaledb/gpgkey | sudo gpg --dearmor -o /etc/apt/trusted.gpg.d/timescaledb.gpg
   sudo apt-get update

Im Regelfall genügt der einfache Befehl (Versionsnummer ggf. an die installierte PostgreSQL
Version anpassen):

.. code-block:: bash

   sudo apt-get install timescaledb-2-postgresql-17

.. hint::

   Weil die TimescaleDB-Pakete gegen bookworm gebaut sind, das System aber ggf. bereits neuere
   Debian-Versionen von ``postgresql-17``/``libpq5`` installiert hat (oder installieren würde),
   kann ``apt`` beim einfachen Befehl oben in seltenen Fällen mit nicht auflösbaren Abhängigkeiten
   scheitern, weil der Resolver Pakete unterschiedlicher Debian-Versionen mischen will. In diesem
   Fall hilft es, alle betroffenen Pakete in einem Kommando und mit ``-t`` explizit auf die eigene
   Paketquelle (z.B. ``trixie``) festgelegt zu installieren:

   .. code-block:: bash

      sudo apt-get install -t trixie postgresql-17 postgresql-client-17 libpq5 timescaledb-2-postgresql-17

   Ein solcher Konflikt wurde auf Devuan excalibur (dem trixie-Gegenstück von Devuan) beobachtet
   und dort mit ``-t excalibur-security`` statt ``-t trixie`` behoben. Auf einem frisch
   aufgesetzten, echten Debian trixie (getestet in einem Container, arm64) trat der Konflikt
   dagegen **nicht** auf - der einfache Befehl oben installierte dort ohne Probleme. Ob der
   Konflikt auftritt, scheint also vom bereits vorhandenen Systemzustand abzuhängen (z.B. weitere
   aktive Paketquellen, bereits vorgenommene Teil-Upgrades). Zuerst den einfachen Befehl
   versuchen, bei einer Fehlermeldung zu nicht auflösbaren Abhängigkeiten auf den ``-t trixie``
   Befehl ausweichen; sollte das nicht ausreichen, probeweise ``-t trixie-security`` verwenden.

Anschließend passt ``timescaledb-tune`` die PostgreSQL-Konfiguration automatisch an die vorhandene
Hardware an (Arbeitsspeicher etc.) und der Server wird neu gestartet:

.. code-block:: bash

   sudo timescaledb-tune --quiet --yes
   sudo systemctl restart postgresql

Die Erweiterung muss abschließend pro Datenbank aktiviert werden:

.. code-block:: bash

   sudo -u postgres psql -d shng -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"

Python-Modul installieren
===========================

Das Plugin greift über das Python-Modul ``psycopg2-binary`` auf PostgreSQL zu. Dieses Modul ist
nicht Teil der Grundinstallation und muss im für SmartHomeNG verwendeten virtuellen Python
Environment (siehe :doc:`/referenz/python/virtual_environments`) nachinstalliert werden:

.. code-block:: bash

   pip3 install psycopg2-binary

Die eigentliche Plugin-Konfiguration (``driver: timescaledb``, Verbindungsdaten) ist unter
:doc:`/plugins_doc/config/database` beschrieben, die TimescaleDB-spezifischen Parameter
(``timescale_hypertable`` und weitere) im Abschnitt "PostgreSQL+TimescaleDB Unterstützung" von
:doc:`../user_doc`.
