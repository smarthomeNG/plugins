.. index:: Plugins; Stateengine
.. index:: Stateengine; Sonstiges
.. _Sonstiges:

Sonstiges
#########

.. rubric:: Zustandsnamen
   :name: sonstigeszustandsnamen

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

.. rubric:: CLI
   :name: sonstigescli

Im CLI Plugin können folgende zwei Befehle zu Debuggingzwecken eingesetzt werden:

**se_list**
*Zeigt eine Liste der Regelwerk-Items, für die das stateengine-Plugin aktiv ist*

**se_detail <Id eines Regelwerk-Items>**
*Zeigt Details zum Objekt Item*
