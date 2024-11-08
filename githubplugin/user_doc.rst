
.. index:: Plugins; githubplugin
.. index:: githubplugin


============
githubplugin
============


Wenn man das Plugin eines anderen Autors ausprobieren oder testen möchte, muss es aus einem fremden Repository von GitHub in die eigene Installation eingebunden werden.

Dieses Plugin ermöglicht es komfortabel, fremde Plugins von GitHub zu installieren und wieder zu deinstallieren. 

Die Bedienung des Plugins und die Übersicht über installierte Plugins erfolgt über das Web-Interface, das über die Admin-UI von SmartHomeNG zugänglich ist.

Dort können Plugins angezeigt, installiert und entfernt werden. Das Löschen von installierten Plugins ist nur möglich, wenn deren git-Verzeichnisse keine veränderten, gelöschten oder hinzugefügten Dateien enthalten und mögliche Commits zu GitHub hochgeladen wurden (push).

Das Plugin legt im Verzeichnis `plugins` das Unterverzeichnis `priv_repos` an, in dem die heruntergeladenen Daten abgelegt werden. Die Repositories werden in `plugins/priv_repos/<Autor>/` abgelegt, die Worktree-Daten für die jeweiligen Branches werden in `plugins/priv_repos/<Autor>_wt_<Branch>/` abgelegt und die eigentlichen Plugins werden im Plugin-Ordner als `plugins/priv_<Name>` verlinkt. Dabei ist Name ein Bezeichner, der vom Nutzer selbst festgelegt werden kann. Dieser wird dann in der Form `priv_<Name>` auch in der `etc/plugin.yaml` als Bezeichner für das Plugin verwendet.

Anforderungen
=============

Notwendige Software
-------------------

Das Plugin benötigt die Python-Pakete GitPython und PyGithub.

Konfiguration
=============

Das Plugin benötigt keine Konfiguration.

Ohne weiteres Zutun sind 60 Zugriffe pro Stunde möglich. Für den normalen Nutzer, der gelegentlich neue Plugins zum Testen oder Ausprobieren installiert, reicht das völlig aus. Wenn mehr Zugriffe benötigt werden, kann auf der Seite `GitHub App-Tokens <https://github.com/settings/tokens>` ein Token registriert und in der Plugin-Konfiguration hinterlegt werden. Damit sind bis zu 5000 Zugriffe pro Stunde möglich.

Die Plugin-Parameter sind unter :doc:`/plugins_doc/config/githubplugin` beschrieben.

