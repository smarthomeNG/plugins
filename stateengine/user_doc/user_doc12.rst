.. index:: Plugins; Stateengine; Sperren
.. index:: Sperren
.. _Lock-Zustand:

Sperren
#######

.. rubric:: Lock - Sperren der automatischen Zustandsermittlung
   :name: lock

Für das Sperren der automatischen Zustandsermittlung führt man ein
Sperr-Item ein, dass beispielsweise über einen Taster änderbar
ist.

Die Sperre soll aktiv sein, wenn das Sperr-Item den Wert ``True``
hat.

.. rubric:: Das Sperr-Item
   :name: dassperritem

Das Sperritem definiert man wie folgt:

.. code-block:: yaml

   beispiel:
           lock:
               item:
                   type: bool
                   name: Sperr-Item
                   visu_acl: rw
                   cache: on


.. rubric:: Der Sperrzustand
   :name: dersperrzustand

Der Sperrzustand geht allen anderen Zuständen vor und wird deshalb
als erster Zustand definiert.

Zudem muss eine Änderung des Sperr-Items direkt eine
Zustandsermittlung auslösen, das Sperr-Item wird daher in die
Liste der ``eval_trigger`` aufgenommen.

Einstiegsbedingung für den Sperrzustand ist nun einfach, dass das
Sperr-Item den Wert ``True`` hat. Für das Sperr-Item werden in
diesem Beispiel keinerlei Aktionen definiert. Solange also das
Sperr-Item aktiv ist, passiert: nichts.

.. code-block:: yaml

   beispiel:
           lock:
               rules:
                   # Sperr-Item zu eval_trigger:
                   eval_trigger:
                       - <andere Einträge>
                       - beispiel.lock.item

                   # Items für Bedingungen und Aktionen
                   se_item_lock: beispiel.lock.item

                   lock:
                       type: foo
                       name: Manuell gesperrt

                       enter:
                           se_value_lock: true


Bei der Zustandsermittlung die Reihenfolge der Definition der
Zustände relevant. Da der Sperrzustand allen anderen Zuständen
vorgeht ist er üblicherweise der erste Zustand in der Definition.
