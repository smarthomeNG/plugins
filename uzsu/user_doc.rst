.. index:: Plugins; uzsu
.. index:: uzsu

uzsu
####

Einführung
==========

Die Funktionsweise der universellen Zeitschaltuhr wird auf dem `SmarthomeNG Blog <https://www.smarthomeng.de/tag/uzsu>`_
beschrieben. Dort finden sich auch einige praktische Beispiele.


Konfiguration
=============

.. important::

      Detaillierte Informationen zur Konfiguration des Plugins sind unter :doc:`/plugins_doc/config/uzsu` zu finden.


.. code-block:: yaml

    # etc/plugin.yaml
    uzsu:
        plugin_name: uzsu
        #remove_duplicates: True


.. code-block:: yaml

    # items/my.yaml
    someroom:

        someitem:
            type: num

            UZSU:
                type: dict
                uzsu_item: someroom.someitem #Ab smarthomeNG 1.6 ist es möglich, einfach nur '..' zu nutzen, um auf das Parent-Item zu verweisen.
                cache: 'True'

                active: # Dieser Eintrag kann genutzt werden, um die UZSU durch einen einfachen Item Call zu (de)aktivieren.
                    type: bool
                    eval: sh...activate(value)
                    visu_acl: rw

SmartVISU
=========

Das UZSU Plugin wird durch die smartVISU2.9 sowohl in Form eines Popups als auch einer grafischen Darstellung unterstützt. Bei Problemen bitte das entsprechende Supportforum konsultieren. Es wird empfohlen, die Visualisierung für das Einstellen der UZSU zu verwenden. Die folgenden Informationen zum Datenformat können übersprungen werden.

Datenformat
===========

Jedes USZU Item wird als dict-Typ gespeichert. Jeder Listen-Eintrag ist wiederum ein dict, das aus Key und Value-Paaren besteht. Im Folgenden werden die möglichen Dictionary-Keys gelistet. Nutzt man das USZU Widget der SmartVISU, muss man sich um diese Einträge nicht kümmern.

-  **dtstart**: Ein datetime Objekt, das den exakten Startwert für den rrule Algorithmus besimmt. Dieser Parameter ist besonder bei FREQ=MINUTELY rrules relevant.

-  **value**: Der Wert, auf den das uzsu_item gesetzt werden soll.

-  **active**: ``True`` wenn die UZSU aktiviert ist, ``False`` wenn keine Aktualisierungen vorgenommen werden sollen. Dieser Wert kann über die Pluginfunktion activate gesteuert werden.

-  **time**: Zeit als String. Entweder eine direkte Zeitangabe wie ``17:00`` oder eine Kombination mit Sonnenauf- und Untergang wie bei einem crontab, z.B. ``17:00<sunset``, ``sunrise>8:00``, ``17:00<sunset``.

-  **rrule**: Hier können Wiederholungsregeln wie in `rrule <https://dateutil.readthedocs.io/en/stable/rrule.html>`_ beschrieben festgelegt werden.


Interpolation
=============

.. important::

      Wenn die Interpolation aktiviert ist, wird das UZSU Item im gegebenen Intervall aktualisiert, auch wenn der nächste UZSU Eintrag über die Tagesgrenze hinaus geht. Gibt es beispielsweise heute um 23:00 einen Eintrag mit dem Wert 100 und morgen um 1:00 einen Eintrag mit dem Wert 0, wird zwischen den beiden Zeitpunkten der Wert kontinuierlich abnehmen. Bei linearer Interpolation wird um Mitternacht der Wert 50 geschrieben.

Interpolation ist ein eigenes Dict innerhalb des UZSU Dictionary mit folgenden Einträgen:

-  **type**: string, setzt die mathematische Interpolationsfunktion cubic, linear oder none. Ist der Wert cubic oder linear gesetzt, wird der für die aktuelle Zeit interpolierte Wert sowohl beim Pluginstart als auch im entsprechenden Intervall gesetzt.

-  **interval**: integer, setzt den zeitlichen Abstand (in Sekunden) der automatischen UZSU Auslösungen

-  **initage**: integer, definiert die Anzahl Sekunden, innerhalb der beim Pluginstart etwaige versäumte UZSU Einträge gesucht werden sollen. Diese Einstellung ist obsolet, wenn die Interpolation nicht auf none ist, weil dann beim Pluginstart der errechnete Wert automatisch gesetzt wird.

-  **itemtype**: Der Item-Typ des uzsu_item, das durch die UZSU gesetzt werden soll. Dieser Wert wird beim Pluginstart automatisch ermittelt und sollte nicht verändert werden.

-  **initizialized**: bool, wird beim Pluginstart automatisch gesetzt, sobald ein gültiger Eintrag innerhalb der initage Zeit gefunden wurde und diese Initialisierung tatsächlich ausgeführt wurde.


Funktionen
==========

.. important::

      Detaillierte Informationen zu den Funktionen des Plugins sind unter :doc:`/plugins_doc/config/uzsu` zu finden.


Webinterface
============

Das Webinterface bietet folgende Informationen:

-  **UZSUs**: Liste aller UZSU Items mit farbkodierter Information über den Status (inaktiv, aktiv, Problem)

-  **UZSU Items**: Info zu den Items, die über die UZSU geschaltet werden (inkl. Typ)

-  **UZSU Item Werte**: Aktueller Wert des UZSU Items, geplanter nächster Wert und Zeitpunkt der Schaltung

-  **UZSU Interpolation**: Interpolationstyp und Intervall

-  **UZSU Init**: Back in Time bzw. init age Wert

-  **UZSU dict**: Durch Klicken auf eine Zeile wird das gesamte Dictionary einer UZSU angezeigt.

.. image:: uzsu_webif.png
   :height: 1632px
   :width: 3286px
   :scale: 25%
   :alt: Web Interface
   :align: center


Beispiel
========

Folgender Python Aufruf bzw. Dictionary Eintrag schaltet das Licht jeden zweiten Tag um 16:30 auf den Wert 100% und deaktiviert es um 17:30 Uhr. Dazwischen wird im Abstand von 5 Minuten der Wert linear interpoliert. Um 17:00 Uhr ist er somit bei 50%.

.. code:: python

   sh.eg.wohnen.leuchte.uzsu({'active':True, 'list':[
   {'value':100, 'active':True, 'rrule':'FREQ=DAILY;INTERVAL=2', 'time': '16:30'},
   {'value':0, 'active':True, 'rrule':'FREQ=DAILY;INTERVAL=2', 'time': '17:30'}],
   {'interval': 5, 'type': 'cubic', 'initialized': False, 'itemtype': 'num', 'initage': 0}
   })
