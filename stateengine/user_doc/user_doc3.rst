.. index:: Plugins; Stateengine; Zustand-Item
.. index:: Zustand-Item

Zustand-Item
############

.. rubric:: Zustände: Das Zustands-Item
   :name: daszustandsitem

Alle Items unterhalb des Objekt-Items (z.B. ``rules``)
beschreiben Zustände des Objekts ("Zustands-Item").
Die Ids der Zustands-Items sind
beliebig. Sie werden als Werte für das über
``se_laststate_item_id`` angegebene Item verwendet, um den
aktuellen Zustand abzulegen.

.. code-block:: yaml

   beispiel:
     raffstore1:
         automatik:
             rules:
                 Tag:
                     name: Tag
                     se_name: eval: sh.eine_funktion()

**name (optional):**
*Name des Zustands*

Der Name des Zustands wird im Protokoll sowie als Wert für das
über ``se_laststate_item_name`` angegebene Item verwendet. Wenn
kein Name angegeben ist, wird hier die Id des
Zustands-Items verwendet.

**se_name (optional):**
*Ermittlung des Namens des Zustands*

Über das Attribut ``se_name`` kann der im Attribut ``name`` angegebene Wert
überschrieben werden. Dies wirkt sich jedoch nur auf den Wert
aus, der in das über ``se_laststate_item_name`` angegebene
Item geschrieben wird. Im Protokoll wird immer der über das
Attribut ``name`` angegebene Wert verwendet.

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
   erfüllt sind (UND-Verknüpfung).

-  Ein Zustand kann aktueller Zustand werden, wenn eine beliebige
   der definierten Bedingungsgruppen des Zustands erfüllt ist. Die
   Prüfung ist mit der ersten erfüllten Bedingungsgruppe beendet
   (ODER-Verknüpfung).

-  Ein Zustand, der keine Bedingungsgruppen hat, kann immer
   aktueller Zustand werden. Solch ein Zustand kann als
   Default-Zustand am Ende der Zustände definiert werden.

.. rubric:: Aktionen
   :name: aktionenintro

Jeder Zustand kann eine beliebige Anzahl an Aktionen definieren.
Sobald ein Zustand aktueller Zustand wird, werden die Aktionen des
Zustands ausgeführt. Für die Aktionen gibt es vier Ereignisse, die
festlegen, wann eine Aktion ausgeführt wird.

   Details zu den Aktionen werden im Abschnitt
   :ref:`Aktionen` erläutert.

.. rubric:: Items
   :name: items

Bedingungen und Aktionen beziehen sich überlicherweise auf Items wie beispielsweise
die Höhe einer Jalousie oder die Außenhelligkeit.
Diese Items müssen auf Ebene des Objekt-Items über das Attribut
``se_item_<Bedingungsname/Aktionsname>`` bekannt gemacht werden.

.. rubric:: Beispiel
   :name: beispielzustand

.. code-block:: yaml

   beispiel:
     raffstore1:
         automatik:
             rules:
                 <Allgemeine Objektkonfiguration>
                 se_item_height: beispiel.raffstore1.hoehe
                 se_item_brightness: beispiel.wetterstation.helligkeit

                 Nacht:
                     name: Nacht
                     on_enter_or_stay:
                        se_set_height: 100
                     enter_toodark:
                        se_max_brightness: 25

**Attribut se_item_height:**
*Definition des Items, das durch die Aktion se_set_height verändert wird*

**Attribut se_item_brightness:**
*Definition des Items, dessen Wert für die Bedingung abgefragt werden soll*

Im Beispiel wird also im Zustand Nacht das Item ``beispiel.raffstore1.hoehe`` auf
den Wert 100 gesetzt, sobald ``beispiel.wetterstation.helligkeit`` den Wert 25
übersteigt.
