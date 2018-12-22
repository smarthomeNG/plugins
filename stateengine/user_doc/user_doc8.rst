.. index:: Plugins; Stateengine; Vorgabezustände
.. index:: Vorgabezustände

Vorgabezustände
###############

Es ist möglich, Vorgabezustände in der Konfiguration zu definieren
und diese später für konkrete Objekte anzuwenden. Dabei können im
konkreten Zustand auch Einstellungen des Vorgabezustands
überschrieben werden.

Vorgabezustände werden als Item an beliebiger Stelle innerhalb der
Item-Struktur definiert. Es ist sinnvoll, die Vorgabezustände
unter einem gemeinsamen Item namens ``default`` zusammenzufassen. Innerhalb der
Vorgabezustand-Items stehen die gleichen Möglichkeiten wie in
normalen Zustands-Items zur Verfügung. Das dem
Vorgabezustands-Item übergeordnete Item darf nicht das Attribut
``se_plugin: active`` haben, da diese Items nur Vorlagen und keine
tatsächlichen State Machines darstellen. Im Item über dem
Vorgabezustands-Item können jedoch Items über
``se_item_<Bedingungsname|Aktionsname>`` angegeben werden. Diese
stehen in den Vorgabezuständen und in den von den Vorgabezuständen
abgeleiteten Zuständen zur Verfügung und müssen so nicht jedes Mal
neu definiert werden.

Im konkreten Zustands-Item kann das Vorgabezustand-Item über das
Attribut

.. code-block:: yaml

   se_use: <Id des Vorgabezustand-Item>

eingebunden werden. Die Vorgabezustand-Items können geschachtelt
werden, das heißt ein Vorgabezustand kann also selbst wiederum
über ``se_use`` von einem weiteren Vorgabezustand abgeleitet
werden. Um unnötige Komplexität und Zirkelbezüge zu vermeiden, ist
die maximale Tiefe jedoch auf 5 Ebenen begrenzt.

.. rubric:: Beispiel
   :name: beispiel

.. code-block:: yaml

   beispiel:
       default:
           <...>
           se_item_height: ...hoehe
           Nacht:
               <...>
               enter:
                   (...)
               se_set_height: value:100
               se_set_lamella: 0
           Morgens:
               <...>
               enter:
                   <...>
               se_set_height: value:100
               se_set_lamella: 25

       raffstore1:
           lamelle:
              type: num
           hoehe:
              type: num

           automatik:
               rules:
                   <...>
                   se_item_lamella: beispiel.raffstore1.lamelle
                   Nacht:
                       se_use: beispiel.default.Nacht
                       enter_additional:
                           <... zusätzliche Einstiegsbedingung ...>
                       enter:
                           <... Änderungen an der Einstiegsbedingung des Vorgabezustands ...>
                   Morgens:
                       se_use: beispiel.default.Morgens
