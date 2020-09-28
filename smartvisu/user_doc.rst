
.. index:: Plugins; smartvisu (smartVISU Unterstützung)
.. index:: smartvisu
.. index:: smartVISU

=========
smartvisu
=========

Mit dem Plugin **smartvisu** können aus der Definition der Items
in SmartHomeNG automatisch Visuseiten erstellt werden. Diese Visu Seiten
werden im Verzeichnis ``smarthome`` des ``pages`` Verzeichnisses der smartVISU
erstellt. Das Plugin unterstützt smartVISU Versionen von v2.8 bis zur releasten
v2.9.2 (master branch).


Mischung von generierten und manuell erstellten Seiten
------------------------------------------------------

In der smartVISU ist es möglich generierte und manuell erstellte Seiten zu mischen. Dazu muss in der
smartVISU unter ``pages`` ein weiteres Verzeichnis (z.B. mit dem Namen ``manuell`` angelegt werden und
diese Seiten müssen in der Konfiguration der smartVISU unter **Benutzeroberfläche** anstelle der ``smarthomeNG``
Seiten ausgewählt werden.

smartVISU prüft dann, ob eine angeforderte Seite unter ``manuell`` vorhanden ist und benutzt diese Seite. Falls
die angeforderte Seite unter ``manuell`` nicht gefunden wird, wird sie aus den ``smarthome`` Seiten geladen.


Das Vorgehen hierzu ist auch unter :doc:`/visualisierung/automatic_generation` im Abschnitt
**Manuell erstellte Seiten** beschrieben.



Konfiguration
=============

Die Informationen zur Konfiguration des Plugins sind unter :doc:`/plugins_doc/config/smartvisu` beschrieben.


Weiterführende Informationen
============================

Alle weiteren Informationen zur Visualisierung mit smartVISU sind unter :doc:`/visualisierung/visualisierung`
beschrieben.
