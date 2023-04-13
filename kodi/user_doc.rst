.. index:: Plugins; kodi
.. index:: kodi

kodi
####

Konfiguration
=============

.. important::

    Die Informationen zur Konfiguration des Plugins sind unter :doc:``/plugins_doc/config/kodi`` beschrieben.


Hinweise zu Verbindungen
========================

Über die plugin-Parameter connect_retries und connect_cycle kann eingestellt werden, wie oft das Plugin versucht, eine Verbindung zu Kodi aufzubauen. 
Nach Ablauf dieser Versuche wartet das Plugin 30 Sekunden, bevor das Ganze wiederholt wird. Für diese Wiederholungen gibt es keine zeitliche Beschränkung, d.h. solange keine Verbindung besteht, versucht das Plugin alle 30 Sekunden erneut, die Verbindung mit den oben genannten Parametern herzustellen.
