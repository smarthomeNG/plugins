.. index:: Plugins; Stateengine; Sperren
.. index:: Sperren

Sperren
#######

Für das Sperren der automatischen Zustandsermittlung führt man ein
Sperr-Item ein, das beispielsweise über einen Taster oder die Visu änderbar
ist.

Die Sperre soll aktiv sein, wenn das Sperr-Item den Wert ``True``
hat.


Das Sperr-Item
--------------

Das Sperritem definiert man wie folgt:

.. code-block:: yaml

   beispiel:
     lock:
         item:
             type: bool
             name: Sperr-Item
             visu_acl: rw
             cache: on


Der Sperrzustand
----------------

Eine Änderung des Sperr-Items muss direkt eine
Zustandsermittlung auslösen, das Sperr-Item wird daher in die
Liste der ``eval_trigger`` aufgenommen.

Einstiegsbedingung für den Sperrzustand ist nun einfach, dass das
Sperr-Item den Wert ``True`` hat. Für das Sperr-Item werden in
diesem Beispiel keinerlei Aktionen definiert. Solange also das
Sperr-Item aktiv ist, passiert nichts.

.. code-block:: yaml

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


Bei der Zustandsermittlung ist die Reihenfolge der
Zustände relevant. Da der Sperrzustand allen anderen Zuständen
vorgeht, ist er üblicherweise der erste Zustand in der Definition.
