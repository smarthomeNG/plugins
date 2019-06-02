.. index:: Plugins; Stateengine
.. index:: Stateengine; Regelwerk-Item

Regelwerk-Item
##############

Unter jedem Item, für das eine State Machine angelegt werden soll, muss ein "Regelwerk-Item" erstellt werden.
Es wird empfohlen, dieses mit dem Namen ``rules`` als Child-Item unter das Item, das automatisiert werden soll, zu legen.
Dieses Item benötigt einige vorgegebene Definitionen, die am einfachsten über das ``struct`` Attribut
eingebunden werden. Das Item sieht dann folgendermaßen aus:

.. code-block:: yaml

   #items/item.yaml
   raffstore1:
       automatik:
           struct: stateengine.general

           rules:
              cycle: 60

Bei jedem Aufruf des Regelwerk-Items - im Beispiel auf Grund der cycle Angabe also
alle 60 Sekunden - werden die Zustände hierarchisch evaluiert.
Zuerst wird also der erste Status getestet. Kann dieser nicht aktiviert werden,
folgt der darunter angegebene, etc. Details hierzu finden sich im nächsten Teil
der Dokumentation.

.. rubric:: Item-Definitionen
   :name: itemdefinitionen

Bedingungen und Aktionen beziehen sich überlicherweise auf Items wie beispielsweise
die Höhe einer Jalousie oder die Außenhelligkeit.
Diese Items müssen auf Ebene des Regelwerk-Items über das Attribut
``se_item_<Bedingungsname/Aktionsname>`` bekannt gemacht werden.

.. rubric:: Beispiel
   :name: beispielregelwerk

Im Beispiel wird durch ``se_item_height`` das Item ``beispiel.raffstore1.hoehe``
dem Plugin unter dem Namen "height" bekannt gemacht. Das Item ``beispiel.wetterstation.helligkeit``
wird durch ``se_item_brightness`` als "brightness" referenziert.

Auf diese Namen beziehen sich nun in weiterer Folge Bedingungen und Aktionen. Im Beispiel
wird im Zustand Nacht das Item ``beispiel.raffstore1.hoehe`` auf den Wert 100 gesetzt, sobald
``beispiel.wetterstation.helligkeit`` den Wert 25 übersteigt. Erklärungen zu Bedingungen
und Aktionen folgen auf den nächsten Seiten.

.. code-block:: yaml

    #items/item.yaml
    raffstore1:
        automatik:
            struct: stateengine.general
            rules:
                se_item_height: beispiel.raffstore1.hoehe
                se_item_brightness: beispiel.wetterstation.helligkeit

                Nacht:
                    name: Nacht
                    on_enter_or_stay:
                        se_action_height:
                            - 'function: set'
                            - 'to: 100'
                    enter_toodark:
                        se_max_brightness: 25
