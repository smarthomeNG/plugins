.. index:: Plugins; resol (Resol Unterstützung)
.. index:: resol

=====
resol
=====

.. image:: webif/static/img/plugin_logo.png
   :alt: plugin logo
   :width: 300px
   :height: 300px
   :scale: 50 %
   :align: left

Allgemein
=========

Resol plugin, mit Unterstützung für Resol Solar Datenlogger, Frischwasserwärmetauscher und Regler.

Konfiguration
=============

Die Informationen zur Konfiguration des Plugins sind unter :doc:`/plugins_doc/config/resol` beschrieben.


Weiterführende Informationen
============================

Weitere Informationen zu Resol Parametern und Quellen sind hier zu finden:

https://github.com/danielwippermann/resol-vbus

https://danielwippermann.github.io/resol-vbus/#/vsf


Resol Protokol
--------------

Synch byte beween messages: 0xAA

Message:

    Byte    Content
	
    0-1     Destination
	
    2-3     Source
	
    4       Protocol Version,        0x10 -> "PV1", 0x20 -> "PV2", 0x30 -> "PV3"
	
    5-6     Command
	
    7-8     Frame count,             Example 0x1047-> 104 bytes
	
	
Beispiele
=========

.. code-block:: yaml

        solar:
            resol_source@solar: '0x7721'
            resol_destination@solar: '0x0010'
            resol_command@solar: '0x0100'

            sensordefektmaske:
                type: num
                resol_offset@solar: 36
                resol_bituse@solar: 16
                resol_factor@solar:
                 - '1.0'
                 - '256.0'

            temperatur_1:
                name: 'Temperature Kollektor'
                type: num
                resol_offset@solar: 0
                resol_bituse@solar: 16
                resol_factor@solar: 
                 - '0.1'
                 - '25.6'
                resol_isSigned@solar:
                 - False
                 - True



