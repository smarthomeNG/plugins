
.. index:: Plugins; githubplugin
.. index:: githubplugin


============
githubplugin
============


Wenn man das Plugin eines anderen Autors ausprobieren oder testen möchte, muss es aus einem fremden Repository von GitHub in die eigene Installation eingebunden werden.

Dieses Plugin ermöglicht es komfortabel, fremde Plugins von GitHub zu installieren und wieder zu deinstallieren. Dazu wird ein Name vergeben, der dann als Name `plugins/priv_<name>` für das jeweilige Plugin verwendet wird.

Auch wenn die Funktionen des Plugins grundsätzlich über Logiken und direkten Zugriff auf die Methoden der Plugin-Klasse genutzt werden können, erfolgt die Bedienung grundsätzlich über das pluginspezifische Webinterface, das über die Admin-UI von SmartHomeNG zugänglich ist.

Dort können Plugins angezeigt, installiert und entfernt werden. Das Löschen von installierten Plugins ist nur möglich, wenn deren git-Verzeichnisse keine veränderten, gelöschten oder hinzugefügten Dateien enthalten. Diese Änderungen müssen erst von Hand rückgängig gemacht oder per commit/push gesichert werden.

Anforderungen
=============

Notwendige Software
-------------------

Das Plugin benötigt die Python-Pakete GitPython und PyGithub.


Konfiguration
=============

Das Plugin benötigt keine Konfiguration.

Optional kann ein GitHub-API-Key hinterlegt werden, um die Anzahl der möglichen GitHub-Zugriffe zu erhöhen. 

Die Plugin-Parameter sind unter :doc:`/plugins_doc/config/githubplugin` beschrieben.

