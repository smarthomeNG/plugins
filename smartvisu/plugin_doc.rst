

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

