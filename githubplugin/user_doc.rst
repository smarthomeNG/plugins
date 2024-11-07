
.. index:: Plugins; githubplugin
.. index:: githubplugin


============
githubplugin
============


Wenn man das Plugin eines anderen Autors ausprobieren oder testen möchte, muss es aus einem fremden Repository von GitHub in die eigene Installation eingebunden werden.

Dieses Plugin ermöglicht es komfortabel, fremde Plugins von GitHub zu installieren und wieder zu deinstallieren. 

Auch wenn die Funktionen des Plugins grundsätzlich über Logiken genutzt werden können, erfolgt die Bedienung grundsätzlich über das pluginspezifische Webinterface, das über die Admin-UI von SmartHomeNG zugänglich ist.

Dort können Plugins angezeigt, installiert und entfernt werden. Das Löschen von installierten Plugins, deren git-Verzeichnisse nicht "sauber" sind (veränderte, gelöschte oder hinzugefügte Dateien im git-Index), können nicht über die Weboberfläche entfernt werden. Diese Änderungen müssen erst von Hand rückgängig gemacht oder per commit/push gesichert werden.

Vorsicht: Wenn Änderungen an Fremd-Plugins per `git commit` in den Index übernommen wurden, aber nicht per push oder Pull-Request an GitHub gesendet wurden, können diese beim Löschen des Plugins ggf. unwiderruflich verloren gehen.

Anforderungen
=============

Notwendige Software
-------------------

Das Plugin benötigt die Python-Pakete GitPython und PyGithub.


Konfiguration
=============

Das Plugin ist ohne Konfiguration lauffähig.

Optional kann ein GitHub-API-Key hinterlegt werden, um die Anzahl der möglichen GitHub-Zugriffe zu erhöhen. 

Die installiereten Fremd-Plugins werden über den Besitzer des GitHub-Repositories, den jeweiligen branch und den Pluginnamen identifiziert. Dazu wird ein Bezeichner nach dem Format `<Besitzer>/<Branch>-<Plugin>` erstellt. Alternativ kann vom Benutzer ein eigener Bezeichner frei gewählt werden. Um diese Bezeichner dauerhaft zu sichern, kann ein Item vom Typ `dict` bestimmt werden. Dieses benötigt nur die Item-Attribute

.. code:
   repoitem: true
   cache: true


Die Plugin Parameter und die Informationen zur Item-spezifischen Konfiguration des Plugins sind unter :doc:`/plugins_doc/config/githubplugin` beschrieben.

Dort findet sich auch die Dokumentation zu Funktionen, die das Plugin evtl. bereit stellt.

