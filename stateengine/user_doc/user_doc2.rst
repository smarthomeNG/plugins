.. index:: Plugins; Stateengine; Konfiguration
.. index:: Konfiguration

Konfiguration
#############

.. important::

      Detaillierte Informationen zur Konfiguration des Plugins sind unter :doc:`/plugins_doc/config/stateengine` zu finden.

.. rubric:: Pluginkonfiguration
   :name: pluginkonfiguration

.. code-block:: yaml

   #etc/plugin.yaml
   stateengine:
       plugin_name: stateengine
       #startup_delay_default: 10
       #suspend_time_default: 3600
       #log_level: 0
       #log_directory: var/log/StateEngine/
       #log_maxage: 0

.. rubric:: Objekt-Item
  :name: objektitem

Für jedes Item, für das eine State Machine angelegt werden soll, muss ein "Objekt-Item" erstellt werden.
Es wird empfohlen, dieses mit dem Namen ``rules`` als Child-Item unter das Item, das automatisiert werden soll, zu legen.
Im Beispiel wird zudem ein Item ``automatik`` definiert, da so auch die speziellen Items zur State Engine
übersichtlich gruppiert werden können.

.. code-block:: yaml

   #items/item.yaml
   beispiel:
       raffstore1:
           automatik:
               rules:
                   type: bool
                   eval: True
                   #name: Automatik Raffstore 1
                   se_plugin: active
                   se_laststate_item_id: beispiel.raffstore1.automatik.state_id
                   se_laststate_item_name: beispiel.raffstore1.automatik.state_name
                   #se_startup_delay: 30
                   #se_repeat_actions: true
                   #se_suspend_time: 7200

Eine Neuermittlung des aktuellen Zustands wird jedesmal
durchgeführt, wenn ein Wert für das Objekt-Item geschrieben wird.
Somit können die Standardmöglichkeiten von smarthomeNG wie
``cycle``, ``crontab`` und ``eval_trigger`` verwendet
werden, um die Neuermittlung des aktuellen Zustands auszulösen.
Details zu diesen Attributen können der `smarthomeNG
Dokumentation <https://www.smarthomeng.de/user/konfiguration/items_standard_attribute.html>`_
entnommen werden.

Bei jedem Aufruf des Objekt-Items werden die Zustände hierarchisch evaluiert.
Zuerst wird also der erste Status getestet. Kann dieser nicht aktiviert werden,
folgt der darunter angegebene, etc. Details hierzu finden sich im nächsten Teil
der Dokumentation.

Ein vollständiges Objekt-Item könnte wie folgt aussehen:

.. code-block:: yaml

   #items/item.yaml
   beispiel:
       raffstore1:
           automatik:
               settings:
                   suspendduration:
                       type: num
                       visu_acl: rw
                       cache: 'True'

                   some_targetvalue:
                       type: num
                       visu_acl: rw
                       cache: 'True'

               stateengine_id:
                   type: str
                   visu_acl: r
                   cache: 'on'

               stateengine_name:
                   type: str
                   visu_acl: r
                   cache: 'on'

               stateengine_suspend_end:
                   type: str
                   visu_acl: ro
                   cache: 'on'

               lock:
                   type: bool
                   knx_dpt: 1
                   visu_acl: rw
                   cache: 'on'

               suspend:
                   type: bool
                   knx_dpt: 1
                   visu_acl: rw
                   cache: 'True'

               manuell:
                   type: bool
                   se_manual_invert: 'True'
                   se_manual_exclude:
                     - database:*
                     - KNX:1.1.4
                   eval_trigger:
                     - taster1
                     - taster2

               rules:
                   type: bool
                   se_plugin: active
                   se_startup_delay: 300
                   se_repeat_actions: False
                   se_laststate_item_id: ..stateengine_id
                   se_laststate_item_name: ..stateengine_name
                   se_item_suspend_end: ..stateengine_suspend_end
                   se_suspend_time: eval:stateengine_eval.get_relative_itemvalue('..settings.suspendduration') * 60
                   eval: True
                   eval_trigger:
                     - some_trigger_object_id

                   state1:
                       se_use: default.state1 #Wird in weiterer Folge erläutert
