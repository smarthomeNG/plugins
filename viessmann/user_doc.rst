.. index:: Plugins; viessmann
.. index:: viessmann

=========
viessmann
=========

.. image:: webif/static/img/plugin_logo.svg
   :alt: plugin logo
   :width: 300px
   :height: 300px
   :scale: 50 %
   :align: left

Das Viessmann-Plugin ermöglicht die Verbindung zu einer Viessmann-Heizung über einen IR-Adapter (z.B. Optolink oder Nachbauten, wie im OpenV-Wiki beschrieben) und das Lesen und Schreiben von Parametern der Heizung.
Derzeit sind das P300- und das KW-Protokoll unterstützt. Weitere Gerätetypen, die diese Protokolle unterstützen, können einfach hinzugefügt werden. Für weitere Protokolle (z.B. GWG) wird zusätzliche Entwicklungsarbeit notwendig sein.

Details zu den betroffenen Geräten und Protokollen finden sich im
.. _OpenV-Wiki: https://github.com/openv/openv/wiki/vcontrold

Dieses Plugin nutzt eine separate Datei ``commands.py``, in der die Definitionen für Protokolle, Gerätetypen und Befehlssätze enthalten sind. Neue Geräte können hinzugefügt werden, indem die entsprechenden Informationen in der ``commands.py`` ergänzt werden.

Das Plugin unterstützt die serielle Kommunikation mit dem Lesekopf (ggf. über einen USB-Seriell-Adapter).

Zur Identifizierung des Heizungstyps kann das Plugin auch im Standalone-Modus betrieben werden (s.u.)


Anpassungen durch Update auf sdp
--------------------------------

Durch die Umstellung auf sdp haben sich sowohl Änderungen in der Plugin- als auch der Item-Konfiguration geändert.

Plugin-Konfiguration:
~~~~~~~~~~~~~~~~~~~~~

-  der Parameter ``heating_type`` ist in ``model`` umbenannt worden
-  der Parameter ``suspend_item`` ist neu hinzugefügt worden und bestimmt (bei Bedarf) das Item zum Steuern des Suspend-Modus

Item-Konfiguration:
~~~~~~~~~~~~~~~~~~~

Die Item-Konfiguration von sdp wird durch mitgelieferte Structs unterstützt. Zu Details siehe weiter unten.

Das Attribut ``viess_balist`` gibt es nicht mehr, die Funktionalität wird durch Lookup-Tabellen abgebildet. Die Lookup-Tabelle zur Betriebsart ist im Item ``Allgemein.Betriebsart.lookup`` standardmäßig verfügbar.

Plugin-Funktionen:
~~~~~~~~~~~~~~~~~~

Die Funktion ``update_all_read_items`` existiert nicht mehr. SmartDevicePlugin bietet - generell - die Funktion ``read_all_commands(group='')`` an, die die gleiche Funktionalität darstellt. Hier kann eine Gruppe, eine Liste von Gruppen oder 0 (für alle Items) angegeben werden, die gelesen werden sollen. Die Konfiguration entspricht den read_groups_triggers (die intern nur diese Funktion anstoßen).


Changelog
---------

1.3.0
~~~~~

-  komplettes Rewrite auf Basis SmartDevicePlugin
-  Umfang der unterstützten Geräte beibehalten
-  breaking Change: Konfiguration (Plugin und Items) müssen angepasst werden

1.2.2
~~~~~

-  Funktion zum manuellen Schreiben von Werten hinzugefügt

1.2.0
~~~~~

-  Komplette Überarbeitung von Code und Webinterface (AJAX)
-  Code refaktorisiert und besser strukturiert
-  Funktion zum Lesen mehrerer Werte gleichzeitig im KW-Protokoll
-  Verbesserte Fehler- und Locking-Behandlung
-  Funktionen zum manuellen Auslesen von konfigurierten und unbekannten Adressen, z.B. zum Testen von Adressen
-  Webinterface mit der Möglichkeit, Adressen manuell auszulesen

1.1.0
~~~~~

-  Unterstützung für das KW-Protokoll

1.0.0
~~~~~

-  Erste Version

Anforderungen
=============

Das Plugin benötigt die ``pyserial``-Bibliothek und einen seriellen IR-Adapter.

Unterstützte Geräte
-------------------

Jede Viessmann-Heizung mit Optolink-Anschluss wird grundsätzlich unterstützt.

Derzeit sind Gerätekonfigurationen (Befehlssätze) für die folgenden Type verfügbar:

-  V200KO1B
-  V200HO1C
-  V200KW2
-  V200WO1C

Weitere Gerätetypen können problemlos hinzugefügt werden, wenn die entsprechenden Befehlsadressen bekannt sind.

Konfiguration
=============

Diese Plugin Parameter und die Informationen zur Item-spezifischen Konfiguration des Plugins sind
unter :doc:`/plugins_doc/config/viessmann` beschrieben.


plugin.yaml
-----------

.. code:: yaml

    viessmann:
        protocol: P300
        plugin_name: viessmann
        model: V200KO1B
        serialport: /dev/ttyUSB_optolink


items.yaml
----------

Zur Vereinfachung werden fertige Structs für alle unterstützten Gerätetypen mitgeliefert. Diese können wie folgt eingebunden werden:

.. code:: yaml

    heizungsitem:
        struct: viessmann.MODEL


:note: Das Wort "MODEL" in der Itemkonfiguration bleibt wörtlich so stehen, sdp verwendet automatisch den entsprechend passenden Struct.


Sofern keine weiteren Angaben gewünscht sind, ist die Item-Konfiguration damit abgeschlossen. Da die Item-Struktur der Kommando-Struktur entspricht, werden sich die Items ändern, d.h. verschieben und ggf. umbenennen. Item-Referenzen müssen entsprechend angepasst werden.


Sofern eine manuelle Item-Konfiguration gewünscht wird, ist dies auch möglich. Die Verknüfpung von SmartHomeNG-Items und Heizungsparametern ist vollständig flexibel und konfigurierbar. Mit den Item-Attributen kann das Verhalten des Plugins festgelegt werden.

Die folgenden Attribute werden unterstützt:


viess\_command
~~~~~~~~~~~~~~

Dieses Attribut legt fest, welcher Befehl ausgeführt bzw. welcher Parameter vom Gerät gelesen oder geschrieben werden soll.

.. code:: yaml

    item:
        viess_command: Allgemein.Temperatur.Aussen


:note: Dies entspricht prinzipiell dem bisherigen Attribut `viess_read`, ohne Aussagen über Lese- oder Schreibverhalten zu treffen. Durch die Umstellung der Befehlsstruktur müssen die Werte angepasst werden.


viess\_read
~~~~~~~~~~~

Das Item erhält Werte vom Gerät (Wert kann gelesen werden). Typ bool. (Entspricht grob dem alten Attribut `viess_read`)


viess\_write
~~~~~~~~~~~~

Der Wert des Items wird bei Änderungen an die Heizung gesendet. Typ bool. (Entspricht grob dem alten Attribut `viess_send`)


viess\_read\_cycle
~~~~~~~~~~~~~~~~~~

Mit einer Angabe in Sekunden wird ein periodisches Lesen angefordert. ``viess_read`` muss zusätzlich konfiguriert sein.

.. code:: yaml

    item:
        viess_command: Allgemein.Temperatur.Aussen
        viess_read_cycle: 3600  # every hour


viess\_read\_initial
~~~~~~~~~~~~~~~~~~~~

Wenn dieses Attribut vorhanden und auf ``true`` gesetzt ist, wird das Item nach dem Start von SmartHomeNG einmalig gelesen.

.. code:: yaml

    item:
        viess_command: Allgemein.Temperatur.Aussen
        viess_read_initial: true


viess\_read\_group:
~~~~~~~~~~~~~~~~~~~

Weist das Item der angegebenen Gruppe zum gesammelten Lesen zu. Die Gruppe kann alt int-Wert oder als str (Name) angegeben werden, mehrere Gruppen können als Liste zugewiesen werden.

.. code:: yaml

    item:
        viess_command: Betriebsart_A1M1
        viess_read_group:
           - Status
           - Betrieb
           - 5


Standardmäßig sind in den Structs bereits Gruppen für alle Strukturbäume vorhanden.


viess\_read\_group\_trigger:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Ein Item mit diesem Attribut löst das Lesen der angegebenen Gruppe(n) aus (siehe `viess_read_group`). Mehrere Gruppen können als Liste angegeben werden, wenn als Gruppe 0 angegeben wird, werden alle Werte vom Gerät gelesen.

Dieses Attribut kann nicht gleichzeitig mit ``viess_command`` gesetzt werden.


viess\_lookup:
~~~~~~~~~~~~~~

Wenn ein Befehl mit einer Lookup-Tabelle versehen ist, kann die Lookup-Tabelle mit dem angegebenen Namen beim Start einmalig in das Item geschrieben werden. Damit können z.B. Klartextwerte für die Visualisierung angeboten werden.

.. code:: yaml

    item:
        viess_lookup: operationmode


:note: In den vorgefertigten Structs sind bei Items, die Werte aus Lookup-Tabellen zurückgeben, die jeweiligen Lookup-Tabellen in Unteritems mit dem Namen ``lookup`` vorhanden.


Beispiel
--------

Here you can find a configuration sample using the commands for
V200KO1B:

.. code:: yaml

    viessmann:
        struct: MODEL


Funktionen
==========

read\_addr(addr)
----------------

Diese Funktion löst das Lesen des Parameters mit der übergebenen Adresse ``addr`` aus. Die Adresse muss als vierstellige Hex-Zahl im String-Format übergeben werden. Es können nur Adressen ausgelesen werden, die im Befehlssatz für den aktiven Heizungstyp enthalten sind. Unabhängig von der Itemkonfiguration werden durch ``read_addr()`` keine Werte an Items zugewiesen.
Der Rückgabewert ist das Ergebnis des Lesevorgangs oder None, wenn ein Fehler aufgetreten ist.


read\_temp\_addr(addr, length=1, mult=0, signed=False)
------------------------------------

Diese Funktion versucht, den Parameter an der Adresse ``addr`` zu lesen und einen Wert von ``length`` Bytes (ggf. mit einem Multiplikator ``mult`` und (nicht) vorzeichenbehaftet) zu konvertieren. Die Adresse muss als vierstellige Hex-Zahl im String-Format übergeben werden, im Gegensatz zu ``read_addr()`` aber nicht im Befehlssatz definiert sein. ``length`` ist auf Werte zwischen 1 und 8 (Bytes) beschränkt. ``mult`` gibt den Divisor an und ``signed``, ob der Wert vorzeichenbehaftet ist.
Der Rückgabewert ist das Ergebnis des Lesevorgangs oder None, wenn ein Fehler aufgetreten ist.


write\_addr(addr, value)
------------------------

Diese Funktion versucht, den Wert ``value`` an die angegebene Adresse zu schreiben. Die Adresse muss als vierstellige Hex-Zahl im String-Format übergeben werden. Es können nur Adressen beschrieben werden, die im Befehlssatz für den aktiven Heizungstyp enthalten sind. Durch ``write_addr`` werden Itemwerte nicht direkt geändert; wenn die geschriebenen Werte von der Heizung wieder ausgelesen werden (z.B. durch zyklisches Lesen), werden die geänderten Werte in die entsprechenden Items übernommen.


:Warning: Das Schreiben von beliebigen Werten oder Werten, deren Bedeutung nicht klar ist, kann im Heizungsgerät möglicherweise unerwartete Folgen haben. Auch eine Beschädigung der Heizung ist nicht auszuschließen.


:Note: Wenn eine der Plugin-Funktionen in einer Logik verwendet werden sollen, kann dies in der folgenden Form erfolgen:

.. code::yaml

    result = sh.plugins.return_plugin('viessmann').read_temp_addr('00f8', 2, 'DT')


Web Interface
=============

Im Web-Interface gibt es neben den allgemeinen Statusinformationen zum Plugin zwei Seiten.

Auf einer Seite werden die Items aufgelistet, die Plugin-Attributen konfiguriert haben. Damit kann eine schnelle Übersicht über die Konfiguration und die aktuellen Werte geboten werden.

Auf der zweiten Seite werden alle im aktuellen Befehlssatz enthaltenen Parameter aufgelistet. Dabei besteht für jeden Wert einzeln die Möglichkeit, einen Lesevorgang auszulösen. Die Rückgabewerte werden in die jeweilige Tabellenzeile eingetragen. Dieser entspricht der Funktion ``read_addr()``, d.h. es werden keine Item-Werte aktualisiert.

Weiterhin kann in der Zeile für den Parameter "_Custom" eine freie Adresse angegeben werden, die analog zur Funktion ``read_temp_addr()`` einen Lesevorgang auf beliebigen Adressen erlaubt. Auch hier wird der Rückgabewert in die jeweilige Tabellenzeile eingetragen. Damit wird ermöglicht, ohne großen Aufwand Datenpunkte und deren Konfiguration (Einheit und Datenlänge) zu testen.


Standalone-Modus
================

Wenn der Heizungstyp nicht bekannt ist, kann das Plugin im Standalone-Modus (also ohne SmartHomeNG zu starten) genutzt werden. Es versucht dann, mit der Heizung zu kommunizieren und den Gerätetyp zu identizifieren.

Dazu muss das Plugin im Plugin-Ordner direkt aufgerufen werden:

``./__init__.py <serieller Port> [-v]``

Der serielle Port ist dabei die Gerätedatei bzw. der entsprechende Port, an dem der Lesekopf angeschlossen ist, z.B. ``/dev/ttyUSB0``. Dieses Argument ist verpflichtend.

Das optionale zweite Argument ``-v`` weist das Plugin an, zusätzliche Debug-Ausgaben zu erzeugen. Solange keine Probleme beim Aufruf auftreten, ist das nicht erforderlich.

Sollte die Datei sich nicht starten lassen, muss ggf. der Dateimodus angepasst werden. Mit ``chmod u+x __init__.py`` kann die z.B. unter Linux erfolgen.

