.. index:: Plugins; Stateengine; Advanced
.. index:: Advanced
.. _Advanced:

Advanced
========

Vordefinierte Funktionen
------------------------

Das stateengine Plugin stellt verschiedene vordefinierte
Funktionen zur Verfügung, die einfach für
``se_set_<Aktionsname>`` und ``se_run_<Aktionsname>`` Aktionen
verwendet werden können:


**Sonnenstandsabhängige Lamellenausrichtung**
*Die Neigung der Lamellen wird automatisch von der Höhe der Sonne bestimmt.*

.. code-block:: yaml

   stateengine_eval.sun_tracking()

**Zufallszahl**
*Über min und max kann die kleinste/größte Nummer, die zurückgegeben werden soll, festgelegt werden.*

.. code-block:: yaml

   stateengine_eval.get_random_int(min,max)

``min`` und ``max`` können weggelassen werden, in diesem Fall sind die
Vorgabewerte 0 für ``min`` und 255 für ``max``.

**Shell-Kommando ausführen**
*Führt ein Shell-Kommando aus*

.. code-block:: yaml

   stateengine_eval.execute(command)

**Wert einer Variable ermitteln**
*Liefert den Wert der Variablen <varname>*

.. code-block:: yaml

   stateengine_eval.get_variable(varname)

**Item-Id relativ zum Regelwerk-Item ermitteln**
*Eine Item-Id relativ zur Item-Id des Regelwerk-Items wird ermittelt.*

.. code-block:: yaml

   stateengine_eval.get_relative_itemid(subitem_id)

**Item-Wert relativ zum Regelwerk-Item ermitteln**
*Der Wert eines Items relativ zur Item-Id des Regelwerk-Items wird ermittelt.*

.. code-block:: yaml

   stateengine_eval.get_relative_itemvalue(subitem_id)

**Suspend-Ende in einen Text einsetzen**
*Das Ende der Suspend-Zeit wird in den Text suspend_text eingesetzt.*

.. code-block:: yaml

   stateengine_eval.insert_suspend_time(suspend_item_id, suspend_text="Ausgesetzt bis %X")

Im Text sind entsprechende Platzhalter
vorzusehen (Siehe `strftime() and strptime()
Behavior <https://docs.python.org/3/library/datetime.html#strftime-strptime-behavior>`_).
Wird kein ``suspend_text`` angegeben, so wird als Vorgabewert
"Ausgesetzt bis %X" verwendet.

Zur Ermittlung des Endes der Suspend-Zeit muss über
``suspend_item_id`` ein Item angegeben werden, dessen Wert bei
Eintritt in den Suspend-Status geändert wird. Über das Alter des
Werts in diesem Item wird die bereits abgelaufene Suspend-Zeit
bestimmt. Dies könnte auch über ein relatives Item angegeben werden,
wobei dieses unbedingt in Anführungszeichen gesetzt werden muss, z.B. ``'..suspend'``


Variablen
---------

Im Plugin stehen folgende Variablen zur Verfügung:

**item.suspend_time:**
*Die Suspend-Time des Items*

**item.suspend_remaining:**
*Die übrige Dauer des Suspend Zustands*

**current.state_id:**
*Die Id des Status, der gerade geprüft wird*

**current.state_name:**
*Der Name des Status, der gerade geprüft wird*


Zustandsnamen
-------------

**name (optional):**
*Name des Zustands*

Der Name des Zustands wird im Protokoll sowie als Wert für das
über ``se_laststate_item_name`` angegebene Item verwendet. Wenn
kein Name angegeben ist, wird hier die Id des
Zustands-Items verwendet.

**se_name:**
*Überschreiben des Namens des Zustands*

Über das Attribut ``se_name`` kann der im Attribut ``name`` angegebene Wert
überschrieben werden, beispielsweise mittels ``eval:sh.eine_funktion()``.
Dies wirkt sich jedoch nur auf den Wert aus, der in das über
``se_laststate_item_name`` angegebene Item geschrieben wird. Dies kann
beispielsweise nützlich sein, um den Namen abhängig von einer Bedingungsgruppe
zu ändern. Ist also z.B. der Zustand auf Grund der Temperatur eingenommen worden,
könnte der Name auf "Zustand (Temp)" geändert werden. Ist der Zustand aufgrund
der Helligkeitsbedingung aktiv, könnte der Name auf "Zustand (Hell)" geändert werden.
Im Protokoll wird immer der über das Attribut ``name`` angegebene Wert verwendet.


CLI
---

Sofern die eingesetzte smarthomeNG-Version dies unterstützt,
registriert das stateengine-Plugin zwei eigene Kommandos beim
CLI-Plugin.

**se_list**
*Zeigt eine Liste der Regelwerk-Items, für die das stateengine-Plugin aktiv ist*

**se_detail <Id eines Regelwerk-Items>**
*Zeigt Details zum Objekt Item*


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

Für dieses Verhalten sind zunächst einige weitere Steueritems
erforderlich, dann kann das Verhalten in einem Zustand abgebildet
werden. Suspend-Item und Zustand können durch ``struct: stateengine.state_suspend``
auf Höhe des Regelwerk-Items automatisch implementiert werden.

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
                     - KNX:1.1.4
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
(``Caller``) einem Doppelpunkt und der Quelle (``Source``). Ohne Leerzeichen!
Mehrere Elemente werden durch "|" getrennt bzw. im yaml als Liste deklariert.
Für ``Caller`` und ``Source`` kann dabei jeweils auch ``"*"`` angegeben werden, dies
bedeutet, dass der jeweilige Teil nicht berücksichtigt werd.

Wenn bei der Prüfung festgestellt wird, dass ein Wert über eine
Eval-Funktionalität geändert wurde, so wird die Änderung
zurückverfolgt bis zur ursprünglichen Änderung, die die Eval-Kette
ausgelöst hat. Diese ursprüngliche Änderung wird dann geprüft.

Der Wert von ``Caller`` zeigt an, welche Funktionalität das Item
geändert hat. Der Wert von ``Source`` ist Abhängig vom Caller.
Häufig verwendete ``Caller`` sind:

-  ``Init``: Initialisierung von smarthomeNG. ``Source`` ist in der Regel leer
-  ``Visu``: Änderung über die Visualisierung (Visu-Plugin). ``Source`` beinhaltet die IP und den Port der Gegenstelle
-  ``KNX``: Änderung über das KNX-Plugin. ``Source`` ist die physische Adresse des sendenden Geräts


Wenn ``se_manual_include`` oder ``se_manual_exclude`` angegeben
sind, muss ``se_manual_invert`` nicht angegeben werden.

Um etwaige Probleme mit den exclude und include Funktionen einfacher erkennen zu können,
kann ein spezielles Logging aktiviert werden: ``se_manual_logitem: <dateiname>``

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
