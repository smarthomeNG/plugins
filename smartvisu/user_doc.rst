
.. index:: Plugins; smartvisu (smartVISU Unterstützung)
.. index:: smartvisu
.. index:: smartVISU

=========
smartvisu
=========

Das Plugin stellt das Bindeglied zur smartVISU dar. Es verfügt über folgende Feature:

- es kann mit Hilfe einiger Item Attribute Seiten für die smartVISU generieren
- es kann Widgets, die in Plugins enthalten sind in die smartVISU installieren
- zur Unterstützung des Widget Assistenten der smartVISU erstellt es eine aktuelle Liste der SmartHomeNG Items
  in der smartVISU
- Es aktiviert das Nutzdatenprotoll für die smartVISU im neuen Websocket Modul. Wenn dieses Plugin nicht geladen ist,
  reagiert das Websocket Modul nicht auf Kommandos von der smartVISU

Mit dem Plugin **smartvisu** können aus der Definition der Items in SmartHomeNG automatisch Seiten für die
smartVISU erstellt werden. Diese Visu Seiten werden im Verzeichnis ``smarthome`` des ``pages`` Verzeichnisses
der smartVISU erstellt. Das Plugin unterstützt smartVISU Versionen ab v2.8.

Das smartvisu Plugin ist der Ersatz für das Plugin visu_smartvisu, welches nun deprecated ist und in einem der
kommenden Releases aus SmartHomeNG entfernt wird.

Das smartvisu Plugin funktioniert sowohl mit dem neuen websocket Modul, als auch mit dem alten visu_websocket Plugin.
Die default_acl Einstellung funktioniert nur im Zusammenspiel mit dem websocket Modul.


Konfiguration
=============

Die Informationen zur Konfiguration des Plugins sind unter :doc:`/plugins_doc/config/smartvisu` beschrieben.

Weiterführende Informationen
============================

.. note::

    Das Plugin ist nur aktiv, wenn die Plugins gestartet werden. Nachdem es die Generierungs- und Kopier-Aktionen
    abgeschlossen hat, stoppt es. Es wird in der Admin GUI in der Liste der Plugins daher als pausiert angezeigt.

    Wird hier der Start Button für das Plugin gedrückt, werden die Visu Seiten erneut generiert und die Widgets
    werden erneut kopiert. Das Plugin stoppt anschließend wieder.


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

Weitere Dokumentation
---------------------

Alle weiteren Informationen zur Visualisierung mit smartVISU sind unter :doc:`/visualisierung/visualisierung`
beschrieben.



Informationen für Entwickler
============================

**Dieser Abschnitt ist veraltet und muss aktualisiert werden**

This section gives **smarthomeNG** developers additional information about the smartvisu plugin. For information
about the configuration of the plugin refer to **README.md**.

This file describes the widget handling for smartVISU widgets and the autogeneration of smartVISU pages.


Dateien des Plugins
-------------------

Das Plugin besteht aus mehreren Dateien, die im folgenden kurz beschrieben werden.


init.py
~~~~~~~
Main file of the plugin.

sv_widgets subdirectory
~~~~~~~~~~~~~~~~~~~~~~~
This directory stores general-use widgets, which are not specific to a plugin. These plugins are installed
together with widgets from different plugins.

tplNG subdirectory
~~~~~~~~~~~~~~~~~~
This directory stores template files, that are used while auto-generating pages for smartVISU. The files in this
directory are copied to the pages/base/tplNG directory, which is created.


Handling of smartVISU widgets
-----------------------------
The visu plugin handles widgets, which a plugin developer delivers with the plugin he has written. For this
to work, the attribute **`smartvisu_dir`** in the visu section of **`plugin.yaml`** must be set to the base
directory of smartVISU.

It handles widgets that define their own Javascript or css. The Javascript and css files must follow the same
naming convention as the html file.

Add a widget to a plugin
~~~~~~~~~~~~~~~~~~~~~~~~
A developer of a plugin can add widgets to the plugin. He has to create a directory named **sv_widgets** in
his plugin directory and add the file(s) of the widget to that directory.

All files in the **sv_widgets** directory are copied to the smartVISU installation.

A widget html-file may contain multiple widgets.

For further automatic integration the widget must follow a name convention. It must be named **`widget_<class>.html`**.
Where **`<class>`** is the class name for the import statement in smartVISU. If this convention is followed,
a statement in the form of

.. code-block:: jinja

	{% import "widget_<class>.html" as <class> %}

is generated.

**Example**:
    For a file **`widget_hue.html`** the statement

    .. code-block:: jinja

        {% import "widget_hue.html" as hue %}

is generated.

The widgets in that file can be called by the directives

.. code-block:: jinja

	{{ hue.control( '...' ) }}

 or

.. code-block:: jinja

	{{ hue.control_group( '...' ) }}

If a Javascript file would exist for the hue widget, it would have to have the name  **`widget_hue.js`**. To
include this file in smartVISU, the following lines are added to root.html:

.. code-block:: jinja

    {% if isfile('widgets/sh_widgets/widget_hue.js') %}
        <script type="text/javascript" src="widgets/sh_widgets/widget_hue.js"></script>
    {% endif %}

The handling of a css file is analog to the Javascript handling.


Modifications to smartVISU made by the visu plugin
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
For this functionality to work, smarthome.py must have write access to the smartVISU directory structure. The
modifications to smartVISU are minimal invasive. The implementation may change, if smartVISU is forked.

The visu plugin creates a directory named **_sh_widgets** in the **widgets** directory of smartVISU. All files
copied from the different plugins are stored in this directory.

On the first run the visu plugin creates a copy of the file **root.html** in the **pages/base** directory of
smartVISU. The copied file is called **root_master.html**.

On each start of smarthome.py the visu plugin creates a new version of **root.html**. The new version is made
of the contents of **root_master.html** and the necessary statements are inserted.
