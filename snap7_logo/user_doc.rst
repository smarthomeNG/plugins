snap7logo
=====================================================
SmarthomeNG plugin, zum Kommunizieren mit einer Siemens LOGO PLC

Anforderungen
-------------
* Python > 3.6
* python-snap7>=1.10
* snap7 

Damit das Plungin beutzt werden kann müssen die Bibliotheken ``snap7`` and ``python-snap7`` installiert sein:


snap7
~~~~~
die Bibliothek sollte mit linux_64bit autoamtisch von python-snap7 installiert werden.

snap7 - manuelle Installation:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: shell-session

    #download and compile snap7 for rpi
    wget http://sourceforge.net/projects/snap7/files/1.2.1/snap7-full-1.2.1.tar.gz/download
    tar -zxvf snap7-full-1.2.1.tar.gz
    cd snap7-full-1.2.1/build/unix
    sudo make –f arm_v7_linux.mk all

    #copy compiled library to your lib directories
    sudo cp ../bin/arm_v7-linux/libsnap7.so /usr/lib/libsnap7.so
    sudo cp ../bin/arm_v7-linux/libsnap7.so /usr/local/lib/libsnap7.so

python-snap7
~~~~~~~~~~~~
das Paket sollte automatisch von SH installiert werden:

python-snap7 - manuelle Installation:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

https://python-snap7.readthedocs.io/en/latest/installation.html

.. code:: shell-session 

    #install python pip if you don't have it:
    sudo pip install python-snap7

Hardware
-------------
Siemens LOGO version 0BA7

Siemens LOGO version 0BA8 8.1 8.2 (8.3 nicht getestet?)


Konfiguration
-------------

plugin.yaml
~~~~~~~~~~~

Konfigurationsbeispiel für die Kommunikation mit zwei LOGO's 

/etc/plugins.yaml

.. code-block:: yaml

    logo1:
        plugin_name: snap7_logo
        instance: logo1
        host: 10.10.10.99
        tsap_server: 0x200
        tsap_client: 0x100
        # port: 102
        # io_wait: 5
        # version: 0BA7
    logo2:
        plugin_name: snap7_logo
        instance: logo2
        host: 10.10.10.100
        version: 0BA8
        # port: 102
        # io_wait: 5

Bitte die Dokumentation lesen, die aus den Metadaten der plugin.yaml erzeugt wurde.


items.yaml
~~~~~~~~~~

Beispiel für SH-Item's - siehe example.yaml

Bitte die Dokumentation lesen, die aus den Metadaten der plugin.yaml erzeugt wurde.


logic.yaml
~~~~~~~~~~

Bitte die Dokumentation lesen, die aus den Metadaten der plugin.yaml erzeugt wurde.


Funktionen
~~~~~~~~~~

Bitte die Dokumentation lesen, die aus den Metadaten der plugin.yaml erzeugt wurde.


Changelog
---------
V1.5.4      example.yaml + user_doc.rst hinzugefuegt
            Kosmetische Verbesserungen der Log-Ausgabe


Aufruf des Webinterfaces
------------------------

Das Plugin kann aus dem Admin Interface aufgerufen werden. Dazu auf der Seite Plugins in der entsprechenden
Zeile das Icon in der Spalte **Web Interface** anklicken.

.. image:: assets/tab1_readed.png
   :class: screenshot 