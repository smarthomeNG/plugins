snap7logo
=====================================================
SmarthomeNG plugin, zum Kommunizieren mit einer Siemens LOGO PLC

Anforderungen
-------------
* Python > 3.6
* python-snap7>=0.10
* snap7 >=1.1.0 

Damit das Plungin beutzt werden kann müssen die Bibliotheken ``snap7`` and ``python-snap7`` installiert sein:

https://python-snap7.readthedocs.io/en/latest/installation.html


snap7
~~~~~

Bibliothek sollte autoamtisch von python-snap7 installiert werden:

.. code::
    #download and compile snap7 for rpi

    wget http://sourceforge.net/projects/snap7/files/1.2.1/snap7-full-1.2.1.tar.gz/download
    tar -zxvf snap7-full-1.2.1.tar.gz
    cd snap7-full-1.2.1/build/unix
    sudo make –f arm_v7_linux.mk all
    # sudo make install

    #copy compiled library to your lib directories
    sudo cp ../bin/arm_v7-linux/libsnap7.so /usr/lib/libsnap7.so
    sudo cp ../bin/arm_v7-linux/libsnap7.so /usr/local/lib/libsnap7.so

python-snap7
~~~~~~~~~~~~
Bibliothek sollte autoamtisch von SH installiert werden:

.. code::
    #install python pip if you don't have it:
    sudo apt-get install python-pip
    sudo pip install python-snap7

Hardware
-------------
Siemens LOGO version 0BA7
Siemens LOGO version 0BA8 8.1 8.2 (8.3 nicht getestet?)


Konfiguration
-------------

plugin.yaml
~~~~~~~~~~~

Bitte die Dokumentation lesen, die aus den Metadaten der plugin.yaml erzeugt wurde.

Konfigurationsbeispiel für die Kommunikation mit zwei LOGO's 

/etc/plugins.yaml
.. code::yaml
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

This plugin needs an host attribute and you could specify a port attribute

* 'instance' = give the instance a name (e.g.'logo1') for multiinstance

* 'io_wait' = timeperiod between two read requests. Default 5 seconds.

* 'version' = Siemens Hardware Version. Default 0BA7

items.yaml
~~~~~~~~~~

Bitte die Dokumentation lesen, die aus den Metadaten der plugin.yaml erzeugt wurde.

Beispiel für SH-Item's - siehe example.yaml

logic.yaml
~~~~~~~~~~

Bitte die Dokumentation lesen, die aus den Metadaten der plugin.yaml erzeugt wurde.


Funktionen
~~~~~~~~~~

Bitte die Dokumentation lesen, die aus den Metadaten der plugin.yaml erzeugt wurde.

Changelog
---------
V1.5.4      kosmetische Verbesserung der Log-Ausgaben
            example.yaml + user_doc.rst hinzugefuegt

Aufruf des Webinterfaces
-------------

Das Plugin kann aus dem Admin Interface aufgerufen werden. Dazu auf der Seite Plugins in der entsprechenden
Zeile das Icon in der Spalte **Web Interface** anklicken.

.. image:: assets/tab1_readed.png
   :class: screenshot 