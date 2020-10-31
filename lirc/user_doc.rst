.. index:: Plugins; lirc
.. index:: lirc

lirc
####

Konfiguration
=============

.. important::

      Detaillierte Informationen zur Konfiguration des Plugins sind unter :doc:`/plugins_doc/config/lirc` zu finden.


.. code-block:: yaml

    # etc/plugin.yaml
    lirc:
        plugin_name: lirc
        #instance: hifisystem
        #lirc_host: 192.168.1.10
        #lirc_port: 6610

Items
=====

Sobald ein entsprechend konfiguriertes Item gesetzt oder aktualisiert wird, sendet das Plugin den entsprechenden Befehl x Mal.
x wird dabei vom Wert bestimmt, auf den das Item gesetzt wird. Nach dem Senden wird der Wert des Items automatisch auf 0 gesetzt.
Beispiel:

.. code-block:: yaml

    # items/item.yaml
    REMOTE_DVDLIVINGROOM:
        DVDLIVINGROOM_POWER:
            type: num
            lirc_remote@instancename: "PHILIPSDVD"
            lirc_key@instancename: "POWER"

Wird DVDLIVINGROOM_POWER auf 5 gesetzt, wird der "POWER" Befehl 5 Mal gesendet.
Bekommt das Item den Wert 1, wird der Befehl ein Mal gesendet.
