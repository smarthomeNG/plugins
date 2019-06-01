.. index:: Plugins; Stateengine
.. index:: Stateengine; Aktionen - einzeln
.. _Aktionen - einzeln:

Aktionen - einzeln
##################

Es gibt zwei Möglichkeiten, Aktionen zu definieren.

Bei der Einzelvariante werden alle
Parameter einer Aktion in separaten Attributen definiert. Über den
gemeinsamen Aktionsnamen gehören die Attribute einer Aktion
zusammen.

Ähnlich wie Bedingungen benötigen auch Aktionen einen Namen. Der
Name ist auch hier beliebig und wird lediglich in der Benennung
der Attribute verwendet. Die Namen aller Attribute, die zu einer
Bedingung gehören, folgen dem Muster ``se_<Funktion>_<Aktionsname>``.

.. rubric:: Aktion: Item auf einen Wert setzen
   :name: aktionitemaufeinenwertsetzen

.. code-block:: yaml

       se_set_<Aktionsname>

Das Item, das verändert werden soll, muss auf Ebene des
Regelwerk-Items über das Attribut ``se_item_<Aktionsname>``
angegeben werden.

Der Wert, auf den das Item gesezt wird, kann als statischer Wert, als Wert eines
Items oder als Ergebnis der Ausführung einer Funktion festgelegt
werden.

.. rubric:: Aktion: Ausführen einer Funktion
   :name: aktionausfuehreneinerfunktion

.. code-block:: yaml

       se_run_<Aktionsname>: eval:(Funktion)

Die Angabe ist vergleichbar mit dem Ausführen einer Funktion zur
Ermittlung des Werts für ein Item, hier wird jedoch kein Item
benötigt. Außerdem wird der Rückgabewert der Funktion ignoriert.

.. rubric:: Aktion: Auslösen einer Logikausführung
   :name: aktionausloeseneinerlogikausfuehrung

.. code-block:: yaml

       se_trigger_<Aktionsname>: meineLogik:Zu übergebender Wert

Um beim Auslösen einen Wert an die Logik zu übergeben, kann dieser
Wert im Attribut über die Angabe von ``: <Wert>`` hinter dem
Logiknamen angegeben werden.

.. rubric:: Aktion: Alle Items, die ein bestimmtes Attribut haben,
   auf den Wert dieses Attributs setzen
   :name: aktionalleitemsdieeinbestimmtesattributhabenaufdenwertdiesesattributssetzen

.. code-block:: yaml

       se_byattr_<Aktionsname>: mein_eigenes_Attribut

Mit diesem Attribut wird der Name eines anderen (beliebigen)
Attributs angegeben. Beim Ausführen werden alle Items
herausgesucht, die das angegebene Attribut enthalten. Diese Items
werden auf den Wert gesetzt, der dem genannten Attribut in den
Items jeweils zugewiesen ist.

.. code-block:: yaml

       dummy:
               type: num
               mein_eigenes_Attribut: 42

wird dann auf ``42`` gesetzt.
Ein anderes Item

.. code-block:: yaml

       dummy2:
               type: str
               mein_eigenes_Attribut: Rums

wird gleichzeitig auf ``Rums`` gesetzt.

.. rubric:: Aktion: Sondervorgänge
   :name: aktionsondervorgnge

.. code-block:: yaml

       se_special_<Aktionsname>: (Sondervorgang)

Für bestimmte Sondervorgänge sind besondere Aktionen im Plugin
definiert (z. B. für das Suspend). Diese werden jedoch nicht hier
erläutert, sondern an den Stellen, an denen Sie verwendet werden.

.. rubric:: Verzögertes Ausführen einer Aktion
   :name: verzgertesausfhreneineraktion

.. code-block:: yaml

       se_delay_<Aktionsname>: 30 (Sekunden)|30m (Minuten)

Über das Attribut wird die Verzögerung angegeben, nach der die
Aktion ausgeführt werden soll. Die Angabe erfolgt in Sekunden oder
mit dem Suffix "m" in Minuten.

Der Timer zur Ausführung der Aktion nach der angegebenen
Verzögerung wird entfernt, wenn eine gleichartike Aktion
ausgeführt werden soll (egal ob verzögert oder nicht). Wenn also
die Verzögerung größer als der ``cycle`` ist, wird die Aktion
nie durchgeführt werden, es sei denn die Aktion soll nur
einmalig ausgeführt werden.

.. rubric:: Wiederholen einer Aktion
   :name: wiederholeneineraktion

.. code-block:: yaml

       se_repeat_<Aktionsname>: True|False

Über das Attribut wird unabhängig vom globalen Setting für das
stateengine Item festgelegt, ob eine Aktion auch beim erneuten
Eintritt in den Status ausgeführt wird oder nicht.

.. rubric:: Festlegen der Ausführungsreihenfolge von Aktionen
   :name: festlegenderausfhrungsreihenfolgevonaktionen

.. code-block:: yaml

       se_order_<Aktionsname>
       se_order_aktion1: 3
       se_order_aktion2: 2
       se_order_aktion3: 1
       se_order_aktion4: 2

Die Reihenfolge, in der die Aktionen ausgeführt werden, ist nicht
zwingend die Reihenfolge in der die Attribute definiert sind. In
den meisten Fällen ist dies kein Problem, da die Aktionen
voneinander unabhängig sind und daher in beliebiger Reihenfolge
ausgeführt werden können. In Einzelfällen kann es jedoch
erforderlich sein, mehrere Aktionen in einer bestimmten
Reihenfolge auszuführen.

Es ist möglich, zwei Aktionen die gleiche Zahl zuzuweisen, die
Reihenfolge der beiden Aktionen untereinander ist dann wieder
zufällig. Innerhalb der gesamten Aktionen werden die beiden
Aktionen jedoch an der angegebenen Position ausgeführt.

.. rubric:: Aktion: Minimumabweichung
   :name: minimumabweichung

Es ist möglich, eine Minimumabweichung für
Änderungen zu definieren. Wenn die Differenz zwischen dem
aktuellen Wert des Items und dem ermittelten neuen Wert kleiner
ist als die festgelegte Minimumabweichung wird keine Änderung
vorgenommen. Die Minimumabweichung wird über das Attribut
``se_mindelta_<Aktionsname>`` auf der Ebene des Regelwerk-Items
festgelegt.

.. rubric:: Aktion: Item zwangsweise auf einen Wert setzen
   :name: aktionitemzwangsweiseaufeinenwertsetzen

.. code-block:: yaml

       se_force_<Aktionsname>

Diese Aktion funktioniert analog zu ``se_set_<Aktionsname>``.
Einziger Unterschied ist, dass die Wertänderung erzwungen wird:
Wenn das Item bereits den zu setzenden Wert hat, dann ändert
smarthomeNG das Item nicht. Selbst wenn beim Item das Attribut
``enforce_updates: yes`` gesetzt ist, wird zwar der Wert neu
gesetzt, der von smarthomeNG die Änderungszeit nicht neu gesetzt. Mit
dem Attribut ``se_force_<Aktionsname>`` wird das Plugin den Wert
des Items bei Bedarf zuerst auf einen anderen Wert ändern und dann
auf dem Zielwert setzen. Damit erfolgt auf jeden Fall eine
Wertänderung (ggf. sogar zwei) mit allen damit in Zusammenhang
stehenden Änderungen (eval's, Aktualisierung der Änderungszeiten,
etc).

.. rubric:: Beispiel zu Aktionen
   :name: beispielzuaktioneneinzeln

.. code-block:: yaml

   beispiel:
       raffstore:
           automatik:
               rules:
                   <...>
                   se_item_height: beispiel.raffstore1.hoehe
                   se_mindelta_height: 10
                   se_item_lamella: beispiel.raffstore1.lamelle
                   se_mindelta_lamella: 5

                   Daemmerung:
                       <...>
                       se_set_height: value:100
                       se_set_lamella: value:25
                       <...>
                   Nacht:
                       <...>
                       se_set_height: value:100
                       se_set_lamella: value:0
                       <...>
                   Sonnenstand:
                       <...>
                       se_set_height: value:100
                       se_set_lamella: eval:stateengine_eval.sun_tracking()
                       <...>
                   Sonder:
                       <...>
                       se_trigger_logic1: myLogic:42
                       se_delay_logic1: 10
                       <...>
