.. index:: Plugins; Stateengine
.. index:: Stateengine; Zustands-Templates
.. _Zustands-Templates:

Zustands-Templates
##################

.. rubric:: Struktur Templates
   :name: strukturtemplates

Neben der vom Plugin bereitgestellten Möglichkeit, Templates zu definieren (siehe weiter unten),
bietet sich ab **smarthomeNG 1.6** das ``struct`` Attribut an. Zum einen können in der Datei ``etc/struct.yaml``
eigene Vorlagen definiert werden, zum anderen stellt das Plugin einige Vorlagen fix fertig bereit. Sie
können wie folgt eingebunden werden:

.. code-block:: yaml

    #items/item.yaml
    beispiel:
        trigger:
            type: bool
            enforce_updates: True

        raffstore1:
            automatik:
                struct:
                  - stateengine.general
                  - stateengine.state_lock
                  - stateengine.state_suspend
                  - stateengine_default_raffstore #beispielsweise eine in etc/struct.yaml angelegte Vorlage

                manuell:
                   # Weitere Attribute werden bereits über das Template stateengine.state_suspend geladen
                    eval_trigger:
                       - beispiel.raffstore1.aufab
                       - beispiel.raffstore1.step
                       - beispiel.raffstore1.hoehe
                       - beispiel.raffstore1.lamelle
                    se_manual_exclude:
                       - KNX:y.y.y:*
                       - Init:*

                rules:
                  eval_trigger:
                      - ..lock
                      - ..supsend
                      - .. release
                      - beispiel.trigger

                  additional_state1:
                      type: foo

Zumindest in der SmarthomeNG Version 1.6.0 werden die eval_trigger Angaben aus den einzelnen Struct-Vorgaben nicht
kumuliert. Es ist daher wichtig, die eval_trigger Liste nochmals manuell im endgültigen Item anzulegen.

Die Vorlagen beinhalten folgende Strukturen:

Die ``general`` Vorlage enthält die Items, die generell für einen Zustandsautomaten
angelegt werden sollten. Das "rules" Item ist das Regelwerk-Item mit aktiviertem
se_plugin. Dieser Codeblock wird zwingend von jedem Zustandsautomaten benötigt.

.. code-block:: yaml

   #stateengine.general
   state_id:
       # The id/path of the actual state is assigned to this item by the stateengine
       type: str
       visu_acl: r
       cache: True

   state_name:
       # The name of the actual state is assigned to this item by the stateengine
       type: str
       visu_acl: r
       cache: True

   conditionset_id:
       remark: The id/path of the actual condition set is assigned to this item by the stateengine
       type: str
       visu_acl: r
       cache: True

   conditionset_name:
       remark: The name of the actual condition set is assigned to this item by the stateengine
       type: str
       visu_acl: r
       cache: True

   rules:
       name: Regeln und Item Verweise für den Zustandsautomaten
       type: bool
       se_plugin: active
       eval: True

       # se_startup_delay: 30
       # se_repeat_actions: true     # Ist das nicht eine Doublette zu anderen Möglichkeiten das zu konfigurieren?
       # se_suspend_time: 7200

       se_laststate_item_id: ..state_id
       se_laststate_item_name: ..state_name
       se_lastconditionset_item_id: ..conditionset_id
       se_lastconditionset_item_name: ..conditionset_name

Die ``state_lock`` Vorlage beinhaltet zum einen den Lock Zustand mit dem Namen "gesperrt",
zum anderen ein Item mit dem Namen ``lock``. Wird dieses auf "1/True" gesetzt, wird der
Zustand eingenommen. Der Zustand sollte immer als erster Zustand eingebunden werden.

.. code-block:: yaml

  #stateengine.state_lock
  lock:
      type: bool
      knx_dpt: 1
      visu_acl: rw
      cache: 'on'

  rules:
      se_item_lock: ..lock
      eval_trigger:
          - ..lock

      lock:
          name: gesperrt

          on_leave:
              se_action_lock:
                - 'function: set'
                - 'to: False'

          enter:
              se_value_lock: True

Die ``state_suspend`` Vorlage dient dem Abfragen von manuellen Tätigkeiten, wie
z.B. Schalten eines Lichts oder Fahren einer Jalousie mittels Taster oder Visu.
In diesem Fall soll die automatiche Evaluierung für eine gewisse Zeit pausieren.

Beim ``manuell`` Item muss unter Umständen der Eintrag ``se_manual_exclude`` in der eigenen
Baumstruktur überschrieben und durch einen Eintrag (z.B. beim Einsatz von KNX Aktoren) ``- KNX:physikalische Adresse:Gruppenadresse``
ergänzt werden. Außerdem muss ein eval_trigger manuell deklariert werden. Hier sollten alle
Items gelistet sein, die für ein vroübergehendes Aussetzen der Automatisierung sorgen sollen
(z.B. Schalt- und Dimm-Items)

Das Item ``settings.suspendduration`` ermöglicht es, die Dauer der Pausierung bequem
über eine Visu oder das Backend zu ändern. Setzt man das Item ``settings.suspend_active``
auf False, wird der Pause-Zustand deaktiviert und manuelle Betätigungen werden
beim nächsten Durchlauf eventuell durch andere Zustände überschrieben.

.. code-block:: yaml

  #stateengine.state_suspend
  suspend:
      type: bool
      knx_dpt: 1
      visu_acl: rw
      cache: True

  suspend_end:
      type: str
      visu_acl: ro
      cache: True

  manuell:
      type: bool
      name: manuell
      se_manual_invert: True
      se_manual_exclude:
        - database:*

  settings:
      suspendduration:
          type: num
          visu_acl: rw
          cache: True

      suspend_active:
          type: bool
          visu_acl: rw
          cache: True

  rules:
      se_item_suspend: ..suspend
      se_item_retrigger: ..rules
      se_item_suspend_end: ..suspend_end
      se_item_suspend_active: ..settings.suspend_active
      se_suspend_time: eval:se_eval.get_relative_itemvalue('..settings.suspendduration') * 60
      eval_trigger:
          - ..manuell

      suspend:
          name: ausgesetzt

          on_enter_or_stay:
              se_action_suspend:
                - 'function: special'
                - 'value: suspend:..suspend, ..manuell'
                - 'repeat: True'
                - 'order: 1'
              se_action_suspend_end:
                - 'function: set'
                - "to: eval:se_eval.insert_suspend_time('..suspend', suspend_text='%X')"
                - 'repeat: True'
                - 'order: 2'
              se_action_retrigger:
                - 'function: set'
                - 'to: True'
                - 'delay: var:item.suspend_remaining'
                - 'repeat: True'
                - 'order: 3'

          on_leave:
              se_action_suspend:
                - 'function: set'
                - 'to: False'
              se_action_suspend_end:
                - 'function: set'
                - 'to:  '

          enter_manuell:
              se_value_trigger_source: eval:se_eval.get_relative_itemid('..manuell')
              se_value_suspend_active: True

          enter_stay:
              se_value_laststate: var:current.state_id
              se_agemax_suspend: var:item.suspend_time
              se_value_suspend: True
              se_value_suspend_active: True

Die ``state_release`` Vorlage ist nicht unbedingt nötig, kann aber dazu genutzt werden,
schnell den Sperr- oder Pause-Zustand zu verlassen und die erneute Evaluierung
der Zustände anzuleiern.

.. code-block:: yaml

  #stateengine.state_release
  release: #triggers the release
      type: bool
      knx_dpt: 1
      visu_acl: rw
      enforce_updates: True

  rules:
      se_item_lock: ..lock
      se_item_suspend: ..suspend
      se_item_retrigger: ..rules
      se_item_release: ..release
      se_item_suspend_end: ..suspend_end
      eval_trigger:
          - ..release

      release:
          name: release

          on_enter_or_stay:
              se_action_suspend:
                - 'function: set'
                - 'to: False'
                - 'order: 1'
              se_action_lock:
                - 'function: set'
                - 'to: False'
                - 'order: 2'
              se_action_release:
                - 'function: set'
                - 'to: False'
                - 'order: 3'
              se_action_suspend_end:
                - 'function: set'
                - 'to: '
                - 'order: 4'
              se_action_retrigger:
                - 'function: set'
                - 'to: True'
                - 'order: 5'
                - 'repeat: True'
                - 'delay: 1'

          enter:
              se_value_release: True


.. rubric:: Pluginspezifische Templates
   :name: pluginspezifisch

Es ist neben der oben beschriebene Variante möglich, Vorgabezustände in
der Item-Konfiguration zu definieren
und diese später für konkrete Regelwerke durch Plugin-interne Attribute zu nutzen.
Dabei können im konkreten Zustand auch Einstellungen des Vorgabezustands
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
   :name: vorgabebeispiel

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
