.. index:: Plugins; Stateengine; Bedingungen
.. index:: Bedingungen
.. _Bedingungen:

Bedingungen
###########

.. rubric:: Grundlagen von Bedingungen
   :name: grundlagenbedingungen

Jede Bedingung erfordert drei Dinge:

-  Einen Namen, der die Bedingung und die zugehörigen Elemente
   identifiziert
-  Grenzwerte um zu prüfen, ob die Bedingung erfüllt ist
-  Eine Möglichkeit, den aktuellen Wert zu ermitteln, gegen den die
   Grenzwerte geprüft werden

.. rubric:: Name der Bedingung
   :name: namederbedingung

Der Name der Bedingung ist beliebig und wird lediglich zur
Benennung der Attribute verwendet. Die Namen aller Attribute, die
zu einer Bedingung gehören, folgen dem Muster
``se_<Funktion>_<Bedingungsname>``. Es gibt verschiedene
"besondere" Bedingungsnamen, die später erläutert werden.

.. rubric:: Grenzwerte
   :name: grenzwerte

Die Grenzwerte einer Bedingung werden in den Bedingungsgruppen
definiert. Die folgenden Grenzwerte sind möglich:

**Minimum**

.. code-block:: yaml

       se_min_<Bedingungsname>: [Wert]

Die Bedingung ist erfüllt, wenn der aktuelle Wert größer als das
angegebene Minimum ist.

**Maximum**

.. code-block:: yaml

       se_max_<Bedingungsname>: [Wert]

Die Bedingung ist erfüllt, wenn der aktuelle Wert kleiner als das
angegebene Maximum ist.

**Bestimmter Wert**

.. code-block:: yaml

       se_value_<Bedingungsname>: [Wert]

Die Bedingung ist erfüllt, wenn der aktuelle Wert gleich dem
angegebenen Wert oder gleich einem der in einer Liste angegebenen Wert ist.

.. code-block:: yaml

       se_value_<Bedingungsname>:
          - [Wert1]
          - [Wert2]
          - [WertN]

**Negieren**

.. code-block:: yaml

       se_negate_<Bedingungsname>: True|False

Die gesamte Bedingung (Minimum, Maximum und Wert) wird negiert
(umgekehrt). Für das Attribut wird der Datentyp Boolean verwendet,
zulässige Werte sind "true", "1", "yes", "on" bzw. "false", "0",
"no", "off"

**Mindestalter**

.. code-block:: yaml

       se_agemin_<Bedingungsname>: [Wert]

Die Bedingung ist erfüllt, wenn das Alter des Items, das zur
Ermittlung des Werts angegeben ist, größer als das angegebene
Mindestalter ist.

**Höchstalter**

.. code-block:: yaml

       se_agemax_<Bedingungsname>: [Wert]

Die Bedingung ist erfüllt, wenn das Alter des Items, das zur
Ermittlung des Werts angegeben ist, kleiner als das angegebene
Höchstalter ist.

**Altersbedingung negieren**

.. code-block:: yaml

       se_agenegate_<Bedingungsname>: True|False

Die Altersbedingung (Mindestalter, Höchstalter) wird negiert
(umgekehrt). Für das Attribut wird der Datentyp Boolean verwendet,
zulässige Werte sind "true", "1", "yes", "on" bzw. "false", "0",
"no", "off"

.. rubric:: Bereitstellung des zu setzenden Werts
   :name: bereitstellungdesaktuellenwerts

Der zu setzende Wert kann entweder über einen statischen Wert, ein Item oder über eine
Eval-Funktion bereitgestellt werden.

Der Name des Items wird auf Ebene des Objekt-Items über das Attribut
``se_item_<Bedingungsname>`` angegeben und in der Bedingung mit dem
gleichen Bedingungsnamen referenziert.


.. rubric:: Beispiel
   :name: beispielbedingungen

Im folgenden Beispiel wird der Zustand "Daemmerung" eingenommen, sobald
die Helligkeit (über se_item_brightness definiert) zwischen 500 und 1000 Lux liegt.

Der Zustand "Sonder" wird eingenommen, sobald die Helligkeit mindestens dem im
Item test.wert hinterlegten Wert entspricht, aber nicht mehr als 500 Einheiten
über diesem Wert liegt.

.. code-block:: yaml

   beispiel:
       raffstore1:
           automatik:
               rules:
                   <...>
                   se_item_brightness: beispiel.wetterstation.helligkeit
                   Daemmerung:
                       type: foo
                       name: Dämmerung
                       <Aktionen>
                       enter:
                           se_min_brightness: 500
                           se_max_brightness: 1000

                   Sonder:
                       type: foo
                       name: Ein spezielles Bedingungsset
                       <Aktionen>
                       enter:
                           se_min_brightness: item:test.wert
                           se_max_brightness: eval:sh.test.wert() + 500


.. rubric:: "Besondere" Bedingungen
   :name: besonderebedingungen

Das Plugin stellt die Werte für einige "besondere" Bedingungen
automatisch bereit. Für diese Bedingungen muss daher kein Item und
keine Eval-Funktion zur Ermittlung des aktuellen Werts angegeben
werden. Die "besonderen" Bedingungen werden über reservierte
Bedingungsnamen gekennzeichnet. Diese Bedingungsnamen dürfen daher
nicht für andere Bedingungen verwendet werden.

Die folgenden "besonderen" Bedingungsnamen können verwendet werden

**time**
*Aktuelle Uhreit*
Die Werte für ``se_value_time``, ``se_min_time`` und
``se_max_time`` müssen im Format "hh:mm" (":") angegeben werden.
Es wird ein 24 Stunden-Zeitformat verwendet. Beispiele: "08:00"
oder "13:37". Um das Ende des Tages anzugeben kann der Wert
"24:00" verwendet werden, der für die Prüfungen automatisch zu
"23:59:59" konvertiert wird. Wichtig sind die Anführungszeichen
oder Hochkommas!

**weekday**
*Wochentag*
0 = Montag, 1 = Dienstag, 2 = Mittwoch, 3 = Donnerstag, 4 =
Freitag, 5 = Samstag, 6 = Sonntag

**month**
*Monat*
1 = Januar, ..., 12 = Dezember

**sun_azimut**
*Sonnenstand (Horizontalwinkel)*
Der Azimut (Horizontalwinkel) ist die Kompassrichtung, in der die
Sonne steht. Der Azimut wird von smarthomeNg auf Basis der
aktuellen Zeit sowie der konfigurierten geographischen Position
berechnet. Siehe auch `SmarthomeNg
Dokumentation <https://www.smarthomeng.de/user/logiken/objekteundmethoden_zeit_sonne_mond.html>`_
für Voraussetzungen zur Berechnung der Sonnenposition.
Beispielwerte: 0 → Sonne exakt im Norden, 90 → Sonne exakt im
Osten, 180 → Sonne exakt im Süden, 270 → Sonne exakt im Westen

**sun_altitude**
*Sonnenstand (Vertikalwinkel)*
Die Altitude (Vertikalwikel) ist der Winkel, in dem die Sonne über
dem Horizont steht. Die Altitude wird von smarthomeNg auf Basis
der aktuellen Zeit sowie der konfigurierten geographischen
Position berechnet. Siehe auch `SmarthomeNG
Dokumentation <https://www.smarthomeng.de/user/logiken/objekteundmethoden_zeit_sonne_mond.html>`_
für Voraussetzungen zur Berechnung der Sonnenposition. Werte:
negativ → Sonne unterhalb des Horizonts, 0 →
Sonnenaufgang/Sonnenuntergang, 90 → Sonne exakt im Zenith
(passiert nur in äquatorialen Bereichen)

**age**
*Zeit seit der letzten Änderung des Zustands (Sekunden)*
Das Alter wird über die letzte Änderung des Items, das als
``se_laststate_item_id`` angegeben ist, ermittelt.

**random**
*Zufallszahl zwischen 0 und 100*
Wenn etwas zufällig mit einer Wahrscheinlichkeit von 60% passieren
soll, kan beispielsweise die Bedingung ``max_random: 60``
verwendet werden.

**laststate**
*Id des Zustandsitems des aktuellen Status*
Wichtig: Hier muss die vollständige Item-Id angegeben werden

**trigger_item, trigger_caller, trigger_source, trigger_dest**
*item, caller, source und dest-Werte, durch die die
Zustandsermittlung direkt ausgelöst wurde*
Über diese vier Bedingungen kann der direkte Auslöser der
Zustandsermittlung abgeprüft werden, also die Änderung, die
smarthomeNG veranlasst, die Zustandsermittlung des
stateengine-Plugins aufzurufen.

**original_item, original_caller, original_source**
*item, caller, source und dest-Werte, durch die die
Zustandsermittlung ursprünglich ausgelöst wurde*
Über diese vier Bedingungen kann der ursprüngliche Auslöser der
Zustandsermittlung abgeprüft werden. Beim Aufruf der
Zustandsermittung über einen ``eval_trigger`` Eintrag wird über
``trigger_caller`` beispielsweise nur ``Eval`` weitergegeben.
In den drei ``original_*`` Bedingungen wird in diesem Fall der
Auslöser der Änderung zurückverfolgt und der Einstieg in die
``Eval``-Kette ermittelt.
