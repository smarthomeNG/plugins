.. index:: Plugins; Stateengine
.. index:: Stateengine; Besondere Zustände
.. _Besondere Zustände:

Besondere Zustände
==================

Sperren
-------

Für das Sperren der automatischen Zustandsermittlung führt man ein
Sperr-Item ein, das beispielsweise über einen Taster oder die Visu änderbar
ist. Sperr-Item und Zustand können durch ``struct: stateengine.state_lock``
auf Höhe des Regelwerk-Items automatisch implementiert werden.

.. rubric:: Das "Sperr"-Item
  :name: dassperritem

Die Sperre soll aktiv sein, wenn das Sperr-Item den Wert ``True`` hat.
Das Sperritem definiert man wie folgt:

.. code-block:: yaml

   #items/item.yaml
   beispiel:
     lock:
         item:
             type: bool
             name: Sperr-Item
             visu_acl: rw
             cache: on

.. rubric:: Der Sperr-Zustand
 :name: dersperrzustand

Der zugehörige Zustand könnte so aussehen und sollte als erster Zustand definiert
werden, da er anderen Zuständen gegenüber priorisiert werden soll.

.. code-block:: yaml

   #items/item.yaml
   beispiel:
       jalousie1:
           rules:
               # Sperr-Item zu eval_trigger:
               eval_trigger:
                   - <andere Einträge>
                   - beispiel.lock.item

               # Items für Bedingungen und Aktionen
               se_item_lock: beispiel.lock.item #Siehe Beispiel oben

               locked:
                   type: foo
                   name: Manuell gesperrt

                   enter:
                       se_value_lock: true


Aussetzen
---------

Eine besondere Anforderung: Nach bestimmten manuellen Aktionen (z.
B. über einen Taster, die Visu, o. ä.) soll die automatische
Zustandsermittlung für eine gewisse Zeit ausgesetzt werden. Nach
Ablauf dieser Zeit soll die Automatik wieder aktiv werden.

Der Aussetzenzustand kann einfach über ``struct: stateenginge.state_suspend`` in
das Stateengine Item (auf der selben Hierarchieebene wie das rules Item)
übernommen werden. Es muss dann lediglich noch
das manuell Item angepasst werden - siehe weiter unten.

.. rubric:: Das "Suspend"-Item
  :name: dassuspenditem

Zunächst wird ein "Suspend"-Item benötigt. Dieses Item zeigt zum
einen die zeitweise Deaktivierung an, zum, anderen kann die
Deaktivierung über dieses Item vorzeitig beendet werden:

.. code-block:: yaml

   #items/item.yaml
   beispiel:
       raffstore1:
           automatik:

               suspend:
                   type: bool
                   knx_dpt: 1
                   visu_acl: rw
                   cache: 'True'

.. rubric:: Das "Manuell"-Item
  :name: dasmanuellitem

Ein weiteres Item wird benötigt, um alle Aktionen, die den
Suspend-Zustand auslösen sollen, zu kapseln. Dieses Item ist das
"Manuell"-Item. Es wird so angelegt, dass der Wert dieses Items
bei jeder manuellen Betätigung invertiert wird:

.. code-block:: yaml

   #items/item.yaml
   beispiel:
       raffstore1:
           automatik:

               manuell:
                   type: bool
                   se_manual_invert: 'True'
                   se_manual_logitem: beispiel.raffstore1.automatik.manuell
                   se_manual_exclude:
                     - database:*
                     - KNX:1.1.4:*
                   eval_trigger:
                     - taster1
                     - taster2

In das Attribut ``eval_trigger`` werden alle Items eingetragen,
deren Änderung als manuelle Betätigung gewertet werden soll.

Das Attribut ``se_manual_invert: true`` veranlasst das
stateengine-Plugin dabei, den Wert des Items bei Änderungen zu
invertieren, wie es für das Auslösen des Suspend-Zustands
erforderlich ist.

In bestimmten Fällen ist es erforderlich, dass Item-Änderungen, die
durch bestimmte Aufrufe ausgelöst werden, nicht als manuelle
Betätigung gewertet werden. Hierzu zählt zum Beispiel die
Rückmeldung der Raffstore-Position nach dem Verfahren durch den
Jalousieaktor. Hierfür stehen zwei weitere Attribute bereit:

**as_manual_include**
*Liste der Aufrufe, die als "manuelle Betätigung" gewertet werden sollen*

**as_manual_exclude**
*Liste der Aufrufe, die nicht als "manuelle Betätigung" gewertet werden sollen*

Bei beiden Attributen wird eine Liste von Elementen angegeben. Die
einzelnen Elemente bestehen dabei aus dem Aufrufenden
(``Caller``) einem Doppelpunkt und der Quelle (``Source``), bei Bedarf auch einer
weiteren durch Doppelpunkt getrennte Information wie z.B. die Gruppenadresse beim KNX Plugin.
Für den gesamten Ausdruck können RegEx genutzt werden, also beispielsweise "*" als Wildcard,
damit der jeweilige Teil nicht berücksichtigt wird.

Wenn bei der Prüfung festgestellt wird, dass ein Wert über eine
Eval-Funktionalität geändert wurde, so wird die Änderung
zurückverfolgt bis zur ursprünglichen Änderung, die die Eval-Kette
ausgelöst hat. Diese ursprüngliche Änderung wird dann geprüft.

Der Wert von ``Caller`` zeigt an, welche Funktionalität das Item
geändert hat. Der Wert von ``Source`` und ``Additional`` ist Abhängig vom Caller.
Häufig verwendete ``Caller`` sind:

-  ``Init``: Initialisierung von smarthomeNG. ``Source`` ist in der Regel leer
-  ``Visu``: Änderung über die Visualisierung (Visu-Plugin). ``Source`` beinhaltet die IP und den Port der Gegenstelle
-  ``KNX``: Änderung über das KNX-Plugin. ``Source`` ist die physische Adresse des sendenden Geräts. ``Additional`` beinhaltet die Gruppenadresse.


Wenn ``se_manual_include`` oder ``se_manual_exclude`` angegeben
sind, muss ``se_manual_invert`` nicht angegeben werden.

Um etwaige Probleme mit den exclude und include Funktionen einfacher erkennen zu können,
kann ein spezielles Logging aktiviert werden: ``se_manual_logitem: <dateiname>``

Ein weiteres Beispiel mit Wildcards. Groß- und Kleinschreibung spielen generell keine Rolle.

.. code-block:: yaml

   #items/item.yaml
   se_manual_exclude:
      - cli:127.0.*.1
      - knx:1.0.0:3/5/*


.. rubric:: Der Suspend-Zustand
  :name: dersuspendzustand

Mit diesen beiden Items kann nun ein einfacher Suspend-Zustand
definiert werden. Als Aktion im Suspend-Zustand wird dabei die
Sonderaktion "suspend" verwendet. Diese hat zwei Parameter:

.. code-block:: yaml

  se_special_suspend: suspend:<Suspend-Item>,<Manuell-Item>


Der Suspend-Zustand sieht damit wie folgt aus:

.. code-block:: yaml

 #items/item.yaml
 beispiel:
   raffstore1:
       automatik:
           rules:
               suspend:
                  type: foo
                  name: Ausgesetzt

                  on_enter_or_stay:
                      type: foo
                      name: Ausführen immer wenn ein Zustand aktiv ist

                      # Suspend-Item setzen
                      se_special_suspend: suspend:beispiel.raffstore1.automatik.suspend,beispiel.raffstore1.automatik.manuell

                  on_leave:
                      type: foo
                      name: Ausführen beim Verlassen des Zustands

                      # Suspend-Item zurücksetzen
                      se_set_suspend: False

                  enter_manuell:
                      type: foo
                      name: Bedingung: Suspend beginnen

                      #Bedingung: Manuelle Aktion wurde durchgeführt
                      se_value_trigger_source: beispiel.raffstore1.automatik.manuell

                  enter_stay:
                      type: foo
                      name: Bedingung: Im Suspend verbleiben

                      #Bedingung: Suspend ist aktiv
                      se_value_laststate: var:current.state_id

                      #Bedingung: Suspendzeit ist noch nicht abgelaufen
                      se_agemax_manuell: var:item.suspend_time

                      #Bedingung: Suspend-Item wurde nicht extern geändert
                      se_value_suspend: True

Da der Suspend-Zustand anderen Zuständen
vorgehen sollte, steht er üblicherweise sehr weit vorrne in der
Reihenfolge. In der Regel wird der Suspend-Zustand in der
Definition der zweite Zustand nach dem Lock-Zustand sein.

.. rubric:: Dauer der zeitweisen Deaktivierung
  :name: dauerderzeitweisendeaktivierung

Die Dauer der zeitweisen Deaktivierung wird in der
Plugin-Konfiguration über die Einstellung ``suspend_time_default``
angegeben. Vorgabewert sind 3600 Sekunden (1 Stunde). Wenn die
Dauer der zeitweisen Deaktivierung für ein einzelnes Regelwerk-Item
abweichend sein soll, kann dort das Attribut

.. code-block:: yaml

      se_suspend_time: <Sekunden>

angegeben werden. Der Parameter kann auch durch ein Item festgelegt werden.
