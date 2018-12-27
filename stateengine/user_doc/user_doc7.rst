.. index:: Plugins; Stateengine; Aktionen - kombiniert
.. index:: Aktionen - kombiniert
.. _Aktionen:

Aktionen - kombiniert
#####################

Bei der kombinierten Variante zur Definition von Aktionen werden
alle Parameter einer Aktion in einem Attribut definiert. Über den
Aktionsnamen werden lediglich eventuelle Items zugeordnet. Die
einzelnen Parameter werden bei conf-Files in der
Listenschreibweise mit dem Zeichen ``|`` getrennt aufgelistet:

.. code-block:: none

    se_action_<Aktionsname>: function: <func> | (evtl. Detailparameter zur Funktion) | delay: <delay> | order: <order> | repeat: <repeat>

Bei yaml Files werden die Parameter mittels Aufzählungszeichen "-"
untereinander definiert:

.. code-block:: yaml

    se_action_<Aktionsname>:
       - function: <func>
       - Detailparameter der Funktion, z.B. "to: .."
       - delay: <delay>
       - order: <order>
       - repeat: <repeat>

Die Parameter haben dabei folgende Bedeutung:

.. rubric:: delay: ``<delay>``
   :name: delay

Über den optionalen Parameter ``<delay>`` wird die Verzögerung angegeben, nach der die
Aktion ausgeführt werden soll.

Die Angabe erfolgt in Sekunden oder mit dem Suffix "m" in Minuten.

.. code-block:: yaml

       delay: 30         --> 30 Sekunden
       delay: 30m        --> 30 Minuten

Der Timer zur Ausführung der Aktion nach der angegebenen
Verzögerung wird entfernt, wenn eine gleichartike Aktion
ausgeführt werden soll (egal ob verzögert oder nicht). Wenn also
die Verzögerung größer als der ``cycle`` ist, wird die Aktion
nie durchgeführt werden, es sei denn die Aktion soll nur
einmalig ausgeführt werden.

.. rubric:: repeat: ``<repeat>``
   :name: repeat

.. code-block:: yaml

       repeat: True|False

Über das Attribut wird unabhängig vom globalen Setting für das
stateengine Item festgelegt, ob eine Aktion auch beim erneuten
Eintritt in den Status ausgeführt wird oder nicht.

.. rubric:: order: ``<order>``
   :name: order

Die Reihenfolge, in der die Aktionen ausgeführt werden, ist nicht
zwingend die Reihenfolge in der die Attribute definiert sind. In
den meisten Fällen ist dies kein Problem da die Aktionen
voneinander unabhängig sind und daher in beliebiger Reihenfolge
ausgeführt werden können. In Einzelfällen kann es jedoch
erforderlich sein, mehrere Aktionen in einer bestimmten
Reihenfolge auszuführen. Dies kann über den Parameter
``order: <order>`` erfolgen. Mit diesem Attribut wird der Aktion
eine Zahl zugewiesen. Aktionen werden in aufsteigender Reihenfolge
der zugewiesenen Zahlen ausgeführt.

Der Parameter ist optional und kann auch weggelassen werden. Für
Aktionen, denen keine Reihenfolge explizit zugewiesen wurde, wird
der Reihenfolgenwert 1 verwendet.

Es ist möglich zwei Aktionen die gleiche Zahl zuzuweisen, die
Reihenfolge der beiden Aktionen untereinander ist dann wieder
undefiniert. Innerhalb der gesamten Aktionen werden die beiden
Aktionen jedoch an der angegebenen Position ausgeführt.

.. code-block:: yaml

       order: 1|2|...

.. rubric:: function: ``<func>``
   :name: function

Mit dem Parameter ``<func>`` wird die auszuführende Funktion
festgelegt. In Abhängigkeit zur gewählten Funktion werden
zusätzliche Detailparameter erforderlich.
Folgende Werte sind möglich:

**Funktion ``set``: Item auf einen Wert setzen**

.. code-block:: yaml

   se_action_<Aktionsname>:
       - function: set
       - to: <val>
       - force: [True/False]

Das Item, das verändert werden soll, muss auf Ebene des
Objekt-Items über das Attribut ``se_item_<Aktionsname>``
angegeben werden.

Der Parameter ``to: <val>`` legt fest, auf welchen Wert das Item
gesetzt werden soll. Der Wert,
auf den das Item gesezt wird, kann als statischer Wert, als
Wert eines Items oder als Ergebnis der Ausführung einer Funktion
festgelegt werden. Wichtig ist, dass bei z.B. ``to: item:<item>``
nach dem item: kein Leerzeichen eingesetzt werden darf!

Über den optionalen Parameter
``force: [True/False]`` kann eine Wertänderung erzwungen werden:
Wenn das Item bereits den zu setzenden Wert hat, dann ändert
smarthomeNG das Item nicht. Selbst wenn beim Item das Attribut
``enforce_updates: yes`` gesetzt ist, wird zwar der Wert neu
gesetzt, der von smarthomeNG Änderungszeit nicht neu gesetzt. Wird
der Parameter ``force: True`` gesetzt, so wird das Plugin den Wert
des Items bei Bedarf zuerst auf einen anderen Wert ändern und dann
auf dem Zielwert setzen. Damit erfolgt auf jeden Fall eine
Wertänderung (ggf. sogar zwei) mit allen damit in Zusammenhang
stehenden Änderungen (eval's, Aktualisierung der Änderungszeiten,
etc).

**Funktion ``run``: Ausführen einer Funktion**

.. code-block:: yaml

   se_action_<Aktionsname>:
       - function: run
       - eval:(Funktion)

Die Angabe ist vergleichbar mit dem Ausführen einer Funktion zur
Ermittlung des Werts für ein Item, hier wird jedoch kein Item
benötigt. Außerdem wird der Rückgabewert der Funktion ignoriert.

**Funktion ``trigger``: Auslösen einer Logikausführung**

.. code-block:: yaml

   se_action_<Aktionsname>:
       - function: trigger
       - logic: <Logikname>
       - value: <Wert>

Löst die Ausführung der Logik ``<Logikname>`` aus. Um beim
Auslösen einen Wert an die Logik zu übergeben, kann dieser Wert
über die Angabe von ``value: <Wert>`` hinter dem Logiknamen
angegeben werden. Wenn kein Wert übergeben werden, soll lässt man
den Teil weg.

**Funktion ``byattr``: Alle Items, die ein bestimmtes Attribut haben, auf den Wert dieses Attributs setzen**

.. code-block:: yaml

   se_action_<Aktionsname>:
       - function: byattr
       - attribute: <Attributname>

Mit dieser Funktion wird der Name eines anderen (beliebigen)
Attributs angegeben. Beim Ausführen werden alle Items
herausgesucht, die das angegebene Attribut enthalten. Diese Items
werden auf den Wert gesetzt, der dem genannten Attribut in den
Items jeweils zugewiesen ist.

.. code-block:: yaml

       dummy1:
               type: num
               <Attributname>: 42

wird dann auf ``42`` gesetzt.
Ein anderes Item

.. code-block:: yaml

       dummy2:
               type: str
               <Attributname>: Rums


wird gleichzeitig auf ``Rums`` gesetzt.

**Funktion ``special``: Sondervorgänge**

.. code-block:: yaml

   se_action_<Aktionsname>:
       - function: special
       - value: <Sondervorgang>

Für bestimmte Sondervorgänge sind besondere Aktionen im Plugin
definiert (z. B. für das Suspend). Diese werden jedoch nicht hier
erläutert, sondern an den Stellen, andenen Sie verwendet werden.

.. rubric:: Beispiel zu Aktionen
   :name: beispielzuaktionenkombiniert

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
                           se_action_height:
                               - function: set
                               - to: value:100
                           se_action_lamella:
                               - function: set
                               - to: value:25
                           <...>
                       Nacht:
                           <...>
                           se_action_height:
                               - function: set
                               - to: value:100
                           se_action_lamella:
                               - function: set
                               - to: value:0
                           <...>
                       Nachfuehren:
                           <...>
                           se_action_height:
                               - function: set
                               - to: value:100
                           se_action_lamella:
                               - function: set
                               - to: eval:stateengine_eval.sun_tracking()
                           <...>
                       Sonder:
                           <...>
                           se_action_logic1:
                               - function: trigger
                               - logic: myLogic
                               - value: 42
                               - delay: 10
                           <...>
