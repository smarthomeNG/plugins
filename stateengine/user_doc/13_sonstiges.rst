
.. index:: Stateengine; Sonstiges
.. _Sonstiges:

=========
Sonstiges
=========

Einbinden anderer Zustände
--------------------------

**se_use (optional):**
*Einbinden einer weiteren Zustandskonfiguration*

.. code-block:: yaml

    se_use: <Zustandsitem> # z.B. stateengine_defaults.state_suspend.rules.suspend

Seit Version 1.8 wird se_use gleich behandelt wie andere Plugin spezifische Attribute mit Wertzuweisung.
Dadurch ist es nicht nur möglich, eine Liste von einzubindenden Zuständen zu deklarieren,
sondern auch auf die verschiedenen Schlüsselwörter zurückzugreifen:

- item:<Itempfad> liest den Wert aus gegebenem Item aus und nutzt diesen als Zustandserweiterung
- eval:<Ausdruck> ermöglicht das dynamische Erweitern des Zustands, z.B. abhängig von einem vorigen Zustand, etc.
- value:<Itempfad> sucht das eingegebene Item und bindet dieses ein. Der Wert kann auch als relativer Pfad angegeben werden
- struct:<structname> ermögicht den Zugriff auf Structs, die entweder selbst oder durch irgendein Plugin bereit gestellt werden

Beinhaltet ein verknüpfter State ebenfalls ein se_use Attribut, werden auch die weiteren Zustände mit eingebunden. Je "tiefer" eine
Deklaration steckt, desto geringer ist ihre Priorität. Heißt, etwaige Zustandseinstellungen im eigentlichen Item erweitern und
überschreiben Einstellungen, die mit se_use eingebunden wurden.

Weitere Details sind unter :ref:`_Zustand-Templates` zu finden.

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
Dies kann beispielsweise nützlich sein, um den Namen abhängig von einer Bedingungsgruppe
zu ändern. Ist also z.B. der Zustand auf Grund der Temperatur eingenommen worden,
könnte der Name auf "Zustand (Temp)" geändert werden. Ist der Zustand aufgrund
der Helligkeitsbedingung aktiv, könnte der Name auf "Zustand (Hell)" geändert werden.

CLI
---

Im CLI Plugin können folgende zwei Befehle zu Debuggingzwecken eingesetzt werden:

**se_list**
*Zeigt eine Liste der Regelwerk-Items, für die das stateengine-Plugin aktiv ist*

**se_detail <Id eines Regelwerk-Items>**
*Zeigt Details zum Objekt Item*
