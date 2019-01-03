.. index:: Plugins; Stateengine; Vordefinierte Funktionen
.. index:: Vordefinierte Funktionen

Vordefinierte Funktionen
########################

Das stateengine Plugin stellt verschiedene vordefinierte
Funktionen zur Verfügung, die einfach für
``se_set_<Aktionsname>`` und ``se_run_<Aktionsname>`` Aktionen
verwendet werden können:


Winkel zum Nachführen der Jalousielamellen auf Basis des Sonnenstands
---------------------------------------------------------------------

.. code-block:: yaml

   stateengine_eval.sun_tracking()


Zufallszahl
-----------

.. code-block:: yaml

   stateengine_eval.get_random_int(min,max)

Über ``min`` und ``max`` kann die kleinste/größte Nummer, die
zurückgegeben werden soll, festgelegt werden. ``min`` und
``max`` können weggelassen werden, in diesem Fall sind die
Vorgabewerte 0 für ``min`` und 255 für ``max``.


.. rubric:: Shell-Kommando ausführen
   :name: shellkommandoausfhren

.. code-block:: yaml

   stateengine_eval.execute(command)

Führt das Shell-Kommando ``command`` aus

.. rubric:: Wert einer Variable ermitteln
   :name: werteinervariableermitteln

.. code-block:: yaml

   stateengine_eval.get_variable(varname)

Liefert den Wert der :ref:`Variablen` ``varname``

.. rubric:: Item-Id relativ zum Objekt-Item ermitteln
   :name: itemidrelativzumobjektitemermitteln

.. code-block:: yaml

   stateengine_eval.get_relative_itemid(subitem_id)

Eine Item-Id relativ zur Item-Id des Objekt-Items wird ermittelt.

.. rubric:: Item-Wert relativ zum Objekt-Item ermitteln
   :name: itemwertrelativzumobjektitemermitteln

.. code-block:: yaml

   stateengine_eval.get_relative_itemvalue(subitem_id)

Der Wert eines Items relativ zur Item-Id des Objekt-Items wird
ermittelt.

.. rubric:: Suspend-Ende in einen Text einsetzen
   :name: suspendendeineinentexteinsetzen

.. code-block:: yaml

   stateengine_eval.insert_suspend_time(suspend_item_id, suspend_text="Ausgesetzt bis %X")

Das Ende der Suspend-Zeit wird in den Text ``suspend_text``
eingesetzt. Im Text sind daher entsprechende Platzhalter
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
