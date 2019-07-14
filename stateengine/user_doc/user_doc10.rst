.. index:: Plugins; Stateengine
.. index:: Stateengine; Funktionen und Variablen
.. Funktionen und Variablen:

Funktionen und Variablen
########################

.. rubric:: Vordefinierte Funktionen
  :name: vordefiniertefunktionen


Das stateengine Plugin stellt verschiedene vordefinierte
Funktionen zur Verfügung, die einfach für
``se_set_<Aktionsname>`` und ``se_run_<Aktionsname>`` Aktionen
verwendet werden können:

**Sonnenstandsabhängige Lamellenausrichtung**
*Die Neigung der Lamellen wird automatisch von der Höhe der Sonne bestimmt.*

.. code-block:: yaml

   se_eval.sun_tracking()

**Zufallszahl**
*Über min und max kann die kleinste/größte Nummer, die zurückgegeben werden soll, festgelegt werden.*

.. code-block:: yaml

   se_eval.get_random_int(min,max)

``min`` und ``max`` können weggelassen werden, in diesem Fall sind die
Vorgabewerte 0 für ``min`` und 255 für ``max``.

**Shell-Kommando ausführen**
*Führt ein Shell-Kommando aus*

.. code-block:: yaml

   se_eval.execute(command)

**Wert einer Variable ermitteln**
*Liefert den Wert der Variablen <varname>*

.. code-block:: yaml

   se_eval.get_variable(varname)

**Item relativ zum Regelwerk-Item ermitteln**
*Ein Item Objekt relativ zur Item-Id des Regelwerk-Items wird ermittelt.*

.. code-block:: yaml

  se_eval.get_relative_item(subitem_id)
  se_eval.get_relative_item('..suspend')

Das zurückgelieferte Item kann nun genutzt werden, um in einem eval Ausdruck
gesetzt oder abgefragt zu werden.

**Item-Id relativ zum Regelwerk-Item ermitteln**
*Eine Item-Id relativ zur Item-Id des Regelwerk-Items wird ermittelt.*

.. code-block:: yaml

   se_eval.get_relative_itemid(subitem_id)
   se_eval.get_relative_itemid('..suspend')

Statt dieser Funktion kann se_eval.get_relative_itemproperty('..suspend', 'path')
verwendet werden.

**Item-Wert relativ zum Regelwerk-Item ermitteln**
*Der Wert eines Items relativ zur Item-Id des Regelwerk-Items wird ermittelt.*

.. code-block:: yaml

   se_eval.get_relative_itemvalue(subitem_id)
   se_eval.get_relative_itemvalue('..suspend')

Statt dieser Funktion kann se_eval.get_relative_itemproperty('..suspend', 'value')
verwendet werden.

**Item-Property relativ zum Regelwerk-Item ermitteln**
*Eine Property eines Items relativ zur Item-Id des Regelwerk-Items wird ermittelt.*

.. code-block:: yaml

  se_eval.get_relative_itemproperty(subitem_id, property)
  se_eval.get_relative_itemproperty('..suspend', 'last_change_age')

Welche Werte für ``property`` genutzt werden können, ist hier nachzulesen:
`Item Properties <https://www.smarthomeng.de/user/konfiguration/items_properties.html?highlight=property>`_).

**Wert eines Item-Attributs ermitteln**
*Der Wert eines Attributs wird ermittelt.*

.. code-block:: yaml

  se_eval.get_attribute_value(item or var, attribute)
  se_eval.get_attribute_value('..settings', 'some_special_attribute')
  se_eval.get_attribute_value('var:current.state_id', 'some_special_attribute')

Der erste Wert muss ein String sein, der entweder ein (relatives) Item enthält
oder eine StateEngine Variable (startet mit var:). Der zweite Wert ist der
Attributname, der eruiert werden soll. Gerade in Kombination mit der Abfrage
der aktuellen Status- oder Conditionset-ID können hier Konfigurationen vereinfacht werden.

**Suspend-Ende in einen Text einsetzen**
*Das Ende der Suspend-Zeit wird in den Text suspend_text eingesetzt.*

.. code-block:: yaml

   se_eval.insert_suspend_time(suspend_item_id, suspend_text="Ausgesetzt bis %X")

Im Text sind entsprechende Platzhalter
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


.. rubric:: Variablen
  :name: speziellevariablen

Im Plugin stehen folgende Variablen zur Verfügung:

**item.suspend_time:**
*Die Suspend-Time des Items*

**item.suspend_remaining:**
*Die übrige Dauer des Suspend Zustands*

Beide obigen Variablen werden vom Suspendzustand genutzt, können bei
Bedarf aber auch für andere Zwecke, welche auch immer, genutzt werden.

**current.action_name:**
*Der Name der Aktion, in der auf die Variable zugegriffen wird*

Der Name der aktuellen Aktion, also der Teil hinter ``se_action_`` kann für 
das Setzen oder Eruieren von Werten herangezogen werden. Dies macht insbesondere
dann Sinn, wenn auf Setting-Items in der Aktion Bezug genommen wird. Durch
diese Variable ist es so je nach Setup möglich, ein Template für sämtliche
Aktionen zu nutzen. Hier ein Beispiel. Das Template "setvalue" wird für das
Setzen mehrerer Items herangezogen. Der eval Ausdruck schafft eine Referenz
auf das passende Unteritem in licht1.automatik.settings.

.. code-block:: yaml

    #items/item.yaml
    licht1:
        irgendeinitem:
            type: bool

        dimmen:
            warm:
                sollwert:
                    type: num
            kalt:
                sollwert:
                    type: num

        automatik:
            settings:
                sollwert_warm:
                    type: num
                sollwert_kalt:
                    type: num
                wasauchimmer:
                    type: bool

            rules:
                se_item_sollwert_warm: licht1.dimmen.warm.sollwert
                se_item_sollwert_kalt: licht1.dimmen.kalt.sollwert
                se_item_wasauchimmer: licht1.irgendeinitem
                se_template_setvalue: "eval:sh.return_item(se_eval.get_relative_itemid('..settings.{}'.format(
                                       se_eval.get_variable('current.action_name'))))()"
                zustand1:
                   name: 'Ein Zustand'
                   on_enter_or_stay:
                       se_action_sollwert_warm:
                         - 'function: set'
                         - "to: template:setvalue"
                       se_action_sollwert_kalt:
                         - 'function: set'
                         - "to: template:setvalue"
                       se_action_wasauchimmer:
                         - 'function: set'
                         - "to: template:setvalue"

**current.state_id:**
*Die Id des Status, der gerade geprüft wird*

**current.state_name:**
*Der Name des Status, der gerade geprüft wird*

Das angeführte Beispiel zeigt, wie eine Bedingung mit einem Wert abgeglichen
werden kann, der in einem passenden Settingitem hinterlegt ist. Konkret
würde beim Evaluieren vom Zustand_Eins mit dem Namen "sueden" die maximale
Helligkeit der Wetterstation mit dem Wert von automatik.settings.sueden.max_bright
verglichen werden. Im Zustand_Zwei namens osten würde der Vergleich hingegen
mit dem Item automatik.settings.osten.max_bright stattfinden. Zu beachten ist,
dass die Eval Ausdrücke exakt gleich sind, was ein Anlegen von eigenen Templates
deutlich vereinfacht.

.. code-block:: yaml

    #items/item.yaml
    raffstore1:
        automatik:
            struct: stateengine.general

            settings:
                sueden:
                    max_bright:
                        type: num
                        value: 80

                osten:
                    max_bright:
                        type: num
                        value: 30

            rules:
                se_item_brightness: wetterstation.helligkeit
                cycle: 10

                Zustand_Eins:
                    name: sueden
                    enter:
                        se_max_brightness: eval:se_eval.get_relative_itemvalue('..settings.{}.max_bright'.format(se_eval.get_variable('current.state_name'))

                Zustand_Zwei:
                    name: osten
                    enter:
                        se_max_brightness: eval:se_eval.get_relative_itemvalue('..settings.{}.max_bright'.format(se_eval.get_variable('current.state_name'))


**current.conditionset_id:**
*Die Id der Bedingungsgruppe, die gerade geprüft wird*

**current.conditionset_name:**
*Der Name der Bedingungsgruppe, die gerade geprüft wird*

Das Beispiel zeigt einen Windzustand. Dieser übernimmt keine Funktionen,
sondern dient lediglich der Visualisierung (Sicherheitsrelevante Features
sollten unbedingt z.B. über den KNX Bus erfolgen!).

- enter_normal wird angenommen, sobald das Wind-Item aktiv ist, zuvor aber
nicht der Lock-Zustand aktiv war.

- enter_afterlock wird angenommen, sobald das Wind-Item aktiv ist und zuvor
der Sperr-Zustand aktiv war.

- enter_stayafterlock wird Dank des se_value_conditionset_name dann angenommen,
solange das Wind-Item noch aktiv ist und der Zustand aufgrund des enter_afterlock
aktiviert wurde.

Da bei der on_leave Aktion der Lock-Zustand nur dann aktiviert wird, wenn der
Zustand auf Grund eines "lock" Bedingungssets eingenommen wurde, kann nun der
Sperrzustand wieder hergestellt werden.

.. code-block:: yaml

    #items/item.yaml
    raffstore1:
        automatik:
            struct: stateengine.general
            rules:
                se_item_wind: ....sicherheit
                wind:
                    name: wind
                    on_leave:
                        se_action_lock:
                          - function:set
                          - to:True
                          - conditionset:(.*)enter_(.*)lock

                    enter_normal:
                        se_value_wind: True
                        se_value_laststate: eval:stateengine_eval.get_relative_itemid('..rules.lock')
                        se_negate_laststate: True

                    enter_afterlock:
                        se_value_wind: True
                        se_value_laststate: eval:stateengine_eval.get_relative_itemid('..rules.lock')

                    enter_stayafterlock:
                        se_value_wind: True
                        se_value_laststate: var:current.state_id
                        se_value_lastconditionset_name:
                            - 'var:current.conditionset_name'
                            - 'enter_afterlock'
