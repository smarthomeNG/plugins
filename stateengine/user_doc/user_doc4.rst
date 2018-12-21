.. index:: Plugins; Stateengine; Zustand-Item
.. index:: Zustand-Item

Zustand-Item
############

.. rubric:: Zustände: Das Zustands-Item
   :name: daszustandsitem

Alle Items unterhalb des Objekt-Items beschreiben Zustände des
Objekts ("Zustands-Item"). Die Ids der Zustands-Items sind
beliebig. Sie werden als Werte für das über
``se_laststate_item_id`` angegebene Item verwendet um den
aktuellen Zustand abzulegen.

.. code-block:: yaml

   beispiel:
           raffstore1:
               automatik:
                   rules:
                       Tag:
                           type: foo
                           name: Tag
                           se_name: eval: sh.eine_funktion()


| **type (obligatorisch):**
| *Datentp des Items*

Für das Zustands-Item muss immer der Datentyp "foo" verwendet
werden

| **name (optional):**
| *Name des Zustands*

Der Name des Zustands wird im Protokoll sowie als Wert für das
über ``se_laststate_item_name`` angegebene Item verwendet. Wenn
kein Name angegeben ist, wird hier ebenfalls die Id des
Zustands-Items verwendet.

| **se_name (optional):**
| *Ermittlung des Namens des Zustands*

| Über das Attribut ``se_name`` kann der im Attribut ``name``
  überschrieben werden. Dies wirkt sich jedoch nur auf den Wert
  aus, der in das über ``se_laststate_item_name`` angegebene
  Item geschrieben wird. Im Protokoll wird immer der über das
  Attribut ``name`` angegebene Wert verwendet.
| Der Parameter verwendet den Datentyp AbValue

.. rubric:: Bedingungsgruppen
   :name: bedingungsgruppen

Jeder Zustand kann eine beliebige Anzahl von Bedingungsgruppen
haben. Jede Bedingungsgruppe definiert ein Set an Bedingungen das
überprüft wird, wenn der aktuelle Status neu ermittelt wird.
Sobald die Bedingungen einer Bedingungsgruppe vollständig erfüllt
sind, kann der Status aktiv werden.

Jede Bedingungsgruppe wird durch ein Item
("Bedingungsgruppen-Item") unterhalb des Zustands-Items
abgebildet. Eine Bedingungsgruppe kann beliebig viele Bedingungen
umfassen. Bedingungen werden als Attribute im
Bedingungsgruppen-Item definiert. Details zu den Bedingungen
werden im Abschnitt :ref:`Bedingungen` erläutert.

Die folgenden Regeln kommen zur Anwendung:

-  Zustände und Bedingungsgruppen werden in der Reihenfolge
   geprüft, in der sie in der Konfigurationsdatei definiert sind.

-  Eine einzelne Bedingungsgruppe ist erfüllt, wenn alle
   Bedingungen, die in der Bedingungsgruppe definiert sind,
   erfüllt sind (UND-Verknüpfung). Einschränkungen, die in der
   Bedingungsgruppe nicht definiert sind, werden nicht geprüft.

-  Ein Zustand kann aktueller Zustand werden, wenn eine beliebige
   der definierten Bedingungsgruppen des Zustands erfüllt ist. Die
   Prüfung ist mit der ersten erfüllten Bedingungsgruppe beendet
   (ODER-Verknüpfung).

-  Ein Zustand der keine Bedingungsgruppen hat kann immer
   aktueller Zustand werden. Solch ein Zustand kann als
   Default-Zustand am Ende der Zustände definiert werden.

.. rubric:: Aktionen
   :name: aktionen

Jeder Zustand kann eine beliebige Anzahl an Aktionen definieren.
Sobald ein Zustand aktueller Zustand wird werden die Aktionen des
Zustands ausgeführt. Für die Aktionen gibt es vier Ereignisse, die
festlegen, wann eine Aktion ausgeführt wird:

-  **on_enter**: Aktionen, die beim erstmaligen Aktivieren des
   Zustands ausgeführt werden

-  **on_stay**: Aktionen, die ausgeführt werden, wenn der Zustand
   zuvor bereits aktiv war und weiterhin aktiv bleibt.

-  **on_enteror_stay**: Aktionen, die ausgeführt werden, wenn der
   Zustand aktiv ist, unabhängig davon, ob er bereits zuvor aktiv
   war oder nicht.

-  **on_leave**: Aktionen, die ausgeführt werden, direkt bevor ein
   anderer Zustand aktiv wird.

   Details zu den Aktionen werden im Abschnitt
   :ref:`Aktionen` erläutert.

.. rubric:: Items
   :name: items

Bedingungen und Aktionen beziehen sich überlicherweise auf Items.
Diese Items müssen auf Ebene des Objekt-Items über das Attribut
``se_item_<Bedingungsname/Aktionsname>`` bekannt gemacht werden.

.. rubric:: Beispiel
   :name: beispiel

.. code-block:: yaml

   beispiel:
           raffstore1:
               automatik:
                   rules:
                       <Allgemeine Objektkonfiguration>

                       Tag:
                           type: foo
                           name: Tag
                           <Aktionen bei Zustand "Tag">
                           enter:
                               <Bedingungen>
                       Nacht:
                           type: foo
                           name: Nacht
                           <Aktionen bei Zustand "Nacht">
                           enter_toodark:
                               <Bedingungen um den Zustand anzusteuern, wenn es zu dunkel ist>
                           enter_toolate:
                               <Bedingungen um den Zustand anzusteuern, wenn es zu spät ist>


| **Attribute se_item_height und se_item_lamella:**
| *Definition der Items, die durch die Aktionen
  se_set_height und se_set_lamella verändert werden*

Die Items werden durch ihre Item-Id angegeben

| **Attribut nam:**
| *Name des Zustands*

Der Name wird in das über ``se_laststate_item_name`` definierte
Item geschrieben, wenn der Zustand aktueller Zustand wird. Dieser
Wert kann z. B. in einer Visualisierung dargestellt werden.

| **Attribute se_set_height und se_set_leave:**
| *Neue statische Werte für die Items die über
  se_item_height und se_item_leave festgelegt wurden*

| **Untergeordnete Items enter, enter_toodark und
  enter_toolate:**
| *Bedingungsgruppen die erfüllt sein müssen, damit ein Zustand
  aktueller Zustand werden kann*
