.. index:: Plugins; Stateengine; Aussetzen
.. index:: Aussetzen

Aussetzen
#########

.. rubric:: Suspend - Zeitweises Deaktivieren der automatischen Zustandsermittlung nach manuellen Aktionen
   :name: suspend

Eine besondere Anforderung: Nach bestimmten manuellen Aktionen (z.
B. über einen Taster, die Visu, o. ä.) soll die automatische
Zustandsermittlung für eine gewisse Zeit ausgesetzt werden. Nach
Ablauf dieser Zeit soll die Automatik wieder aktiv werden.

Für dieses Verhalten sind zunächst einige weitere Steueritems
erforderlich, dann kann das Verhalten in einem Zustand abgebildet
werden.

.. rubric:: Das "Suspend"-Item
   :name: dassuspenditem

Zunächst wird ein "Suspend"-Item benötigt. Dieses Item zeigt zum
einen die zeitweise Deaktivierung an, außerdem kann die
Deaktivierung über dieses Item vorzeitig beendet werden:

.. code-block:: yaml

   beispiel:
           suspend:
               suspend:
                   type: bool
                   name: Suspend-Item
                   visu_acl: rw


.. rubric:: Das "Manuell"-Item
   :name: dasmanuellitem

Ein weiteres Item wird benötigt, um alle Aktionen, die den
Suspend-Zustand auslösen sollen, zu kapseln. Dieses Item ist das
"Manuell"-Item. Es wird so angelegt, dass der Wert dieses Items
bei jeder manuellen Betätigung invertiert wird:

.. code-block:: yaml

   beispiel:
           suspend:
               manuell:
                   type: bool
                   name: Manuelle Bedienung
                   eval_trigger:
                       - beispiel.item1
                       - beispiel.item2
                       - ....
                   se_manual_invert = true


In das Attribut ``eval_trigger`` werden alle Items eingetragen,
deren Änderung als manuelle Betätigung gewertet werden soll.
Änderungen an diesen Items, die vom stateengine-Plugin selbst
vorgenommen wurden, werden dabei automatisch ausgefiltert um
Endlosschleifen zu verhindern.

Das Attribut ``se_manual_invert: true`` veranlasst das
stateengine-Plugin dabei, den Wert des Items bei Änderungen zu
invertieren, wie es für das Auslösen des Suspend-Zustands
erforderlich ist.

Das Manuell-Item kann noch wesentlich komplexer ausgestaltet
werden. Beispielsweise können Änderungen durch bestimmte
Ereignisse ausgeschlossen werden.

.. rubric:: Der Suspend-Zustand
   :name: dersuspendzustand

Mit diesen beiden Items kann nun ein einfacher Suspend-Zustand
definiert werden. Als Aktion im Suspend-Zustand wird dabei die
Sonderaktion "suspend" verwendet. Diese hat zwei Parameter:

.. code-block:: yaml

   se_special_suspend: suspend:<Suspend-Item>,<Manuell-Item>


Der Suspend-Zustand sieht damit wie folgt aus:

.. code-block:: yaml

   suspend:
           type: foo
           name: Ausgesetzt

           on_enter_or_stay:
               type: foo
               name: Ausführen immer wenn ein Zustand aktiv ist

               # Suspend-Item setzen
               se_special_suspend: suspend:test.suspend.suspend,test.suspend.manuell

           on_leave:
               type: foo
               name: Ausführen beim Verlassen des Zustands

               # Suspend-Item zurücksetzen
               se_set_suspend: False

          enter_manuell:
               type: foo
               name: Bedingung: Suspend beginnen

               #Bedingung: Manuelle Aktion wurde durchgeführt
               se_value_trigger_source: test.suspend.manuell

           enter_stay:
               type: foo
               name: Bedingung: Im Suspend verbleiben

               #Bedingung: Suspend ist aktiv
               se_value_laststate: var:current.state_id

               #Bedingung: Suspendzeit ist noch nicht abgelaufen
               se_agemax_manuell: var:item.suspend_time

               #Bedingung: Suspend-Item wurde nicht extern geändert
               se_value_suspend: True


Bei der Zustandsermittlung die Reihenfolge der Definition der
Zustände relevant. Da der Suspend-Zustand anderen Zuständen
vorgehen sollte steht er üblicherweise sehr weit vorrne in der
Reihenfolge. In der Regel wird der Suspend-Zustand in der
Definition der zweite Zustand, nach dem
:ref:`Lock-Zustand` sein.

.. rubric:: Komplettes Beispiel
   :name: komplettesbeispiel

Baut man die einzelnen Teile zusammen erhält man die folgende
Konfiguration.

.. code-block:: yaml

       item:
               type: foo
               name: stateengine Suspend Beispiel

               suspend:
                   type: bool
                   name: Suspend-Item
                   visu_acl: rw

               manuell:
                   type: bool
                   name: Manuelle Bedienung
                   eval_trigger:
                       - beispiel.item1
                       - beispiel.item2
                   se_manual_invert: true

               rules:
                   type: bool
                   name: Automatik Test Suspend
                   se_plugin: active

                   # Sowohl das Manuell- als auch das Suspend-Item müssen eine Zustandsermittlung auslösen
                   eval_trigger:
                       - test.suspend.manuell
                       - test.suspend.suspend

                   #Items für Bedingungen und Aktionen zuweisen
                   se_item_suspend: test.suspend.suspend
                   se_item_manuell: test.suspend.manuell

                   suspend:
                       type: foo
                       name: Ausgesetzt

                       on_enter_or_stay:
                           se_action_suspend:
                             - 'function: special'
                             - 'value: suspend:..suspend, ..manuell'
                             - 'repeat: True'
                             - 'order: 1'
                           se_action_suspend_end:
                             - 'function: set'
                             - "to: eval:stateengine_eval.insert_suspend_time('..suspend', suspend_text='%X')"
                             - 'repeat: True'
                             - 'order: 2'
                           se_action_retrigger:
                             - 'function: set'
                             - 'to: True'
                             - 'delay: var:item.suspend_remaining'
                             - 'repeat: True'
                             - 'order: 3'

                       on_leave:
                           se_action_suspend:
                             - 'function: set'
                             - 'to: False'
                           se_action_suspend_end:
                             - 'function: set'
                             - 'to:  '

                       enter_manuell:
                           se_value_trigger_source: eval:stateengine_eval.get_relative_itemid('..manuell')
                           se_value_suspend_active: 'True'

                       enter_stay:
                           name: Bedingung Im Suspend verbleiben
                           #Bedingung: Suspend ist aktiv
                           se_value_laststate: var:current.state_id
                           #Bedingung: Suspendzeit ist noch nicht abgelaufen
                           se_agemax_manuell: var:item.suspend_time
                           #Bedingung: Suspend-Item wurde nicht extern geändert
                           se_value_suspend: True


.. rubric:: Dauer der zeitweisen Deaktivierung
   :name: dauerderzeitweisendeaktivierung

Die Dauer der zeitweisen Deaktivierung wird in der
Plugin-Konfiguration über die Einstellung ``suspend_time_default``
angegeben. Vorgabewert sind 3600 Sekunden (1 Stunde). Wenn die
Dauer der zeitweisen Deaktivierung für ein einzelnes Objekt-Item
abweichend sein soll, kann dort das Attribut

.. code-block:: yaml

       se_suspend_time: <Sekunden>

angegeben werden. Der Parameter verwendet den Datentyp AbValue

.. rubric:: Erweiterte Funktionen des "Manuell"-Items für den Suspend-Zustand
   :name: erweiterte

.. rubric:: Bestimmte Item-Änderungen nicht als "manuelle Bedienung" auswerten
   :name: bestimmteitem

In bestimmten Fällen ist es erforderlich, das Item-Änderungen, die
durch bestimmte Aufrufe ausgelöst werden, nicht als manuelle
Betätigung gewertet werden. Hierzu zählt zum Beispiel die
Rückmeldung der Raffstore-Position nach dem Verfahren durch den
Jalousieaktor. Hierfür stehen zwei für das Manuell-Item weitere
Attribute bereit:

| **as_manual_include**
| *Liste der Aufrufe, die als "manuelle Betätigung" gewertet
  werden sollen*

| **as_manual_exclude**
| *Liste der Aufrufe, die nicht als "manuelle Betätigung" gewertet
  werden sollen*

Bei beiden Attributen wird eine Liste von Elementen angegeben. Die
einzelnen Elemente bestehen dabei aus dem Aufrufenden
(``Caller``) einem Doppelpunkt und der Quelle (``Source``).
Mehrere Elemente werden durch "|" getrennt bzw. im yaml als Liste deklariert.
Für ``Caller`` und ``Source`` kann dabei jeweils auch "*" angegeben werden, dies
bedeutet, dass der jeweilige Teil nicht berücksichtigt werd.

Wenn bei der Prüfung festgestellt wird, dass ein Wert über eine
Eval-Funktionalität geändert wurde, so wird die Änderung
zurückverfolgt bis zur ursprünglichen Änderung, die die Eval-Kette
ausgelöst hat. Diese ursprüngliche Änderung wird dann geprüft.

Der Wert von ``Caller`` zeigt an, welche Funktionalität das Item
geändert hat. Der Wert von ``Source`` ist Abhängig vom Caller.
Häufig verwendete ``Caller`` sind:

-  ``Init``: Initialisierung von smarthomeNG. ``Source`` ist
   in der Regel leer
-  ``Visu``: Änderung über die Visualisierung (Visu-Plugin).
   ``Source`` beinhaltet die IP und den Port der Gegenstelle
-  ``KNX``: Änderung über das KNX-Plugin. ``Source`` ist die
   physische Adresse des sendenden Geräts

Wenn ``se_manual_include`` oder ``se_manual_exclude`` angegeben
sind, muss ``se_manual_invert`` nicht angegeben werden.

.. code-block:: yaml

   beispiel:
           suspend:
               manuell:
                   type: bool
                   name: Manuelle Bedienung
                   eval_trigger:
                       - beispiel.item1
                       - beispiel.item2
                   se_manual_exclude:
                       - KNX:1.1.42
                       - Init:*


Hier werden alle Änderungen der Items ``beispiel.item1`` und
``beispiel.item2`` als manuelle Betätigung gewertet, sofern Sie
nicht durch das KNX-Gerät mit der physischen Adresse 1.1.42 oder
durch die Initialisierung von smarthomeNG erfolgt sind.

.. rubric:: Erweitertes Logging für das Manuell-Item:
   :name: erweitertesloggingfrdasmanuellitem

Sofern im Manuell-Item die Attribute ``se_manual_include`` bzw.
``se_manual_exclude`` verwendet werden, ist auch hier eine
Protokollierung mittels des erweiterten Loggings möglich. Dazu
muss das Item, unter dem das Log geführt wird über das zusätzliche
Attribut ``se_manual_logitem`` angegeben werden. Hier wird man als
Item in der Regel das Manuell-Item angeben:

.. code-block:: yaml

   beispiel:
           suspend:
               manuell:
                   ....
                   se_manual_logitem: beispiel.suspend.manuell


Wird statt ``se_manual_include`` oder ``se_manual_exclude`` nur
``se_manual_invert`` verwendet, ist kein erweitertes Logging
möglich.
