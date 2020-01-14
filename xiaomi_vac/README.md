# Xiaomi Vacuum Robot Plugin for SmarthomeNG
Das Plugin basiert auf der [python-miio](https://github.com/rytilahti/python-miio) Bibliothek. Das Plugin bzw python-miio benötigt den Kommunikationstoken des Roboters. 

- [Bitte der Installationsanweisung von python-miio folgen](https://python-miio.readthedocs.io/en/latest/discovery.html#installation)
- anschließend den Plugin Ordner nach smarthomeNG/plugins kopieren
- Folgendes zur etc/plugin.yaml hinzufügen

    ```Roboter:
    class_name: Robvac
    class_path: plugins.xiaomi_vac
    ip: '192.XXX.XXX.XXX'
    token: 'euerToken'
    read_cycle: 12
    ```
    
- Um die Verbindung zu überprüfen, kann in der Kommandozeile/Shell nach der Installation mit 

```export MIROBO_IP=192.xxx.xxx.xxx
   export MIROBO_TOKEN=euerToken
```
   
- und anschließendem

```mirobo```
sollte eine Ausgabe ähnlich diesem anzeigen.
```
> State: Charging
> Battery: 100
> Fanspeed: 60
> Cleaning since: 0:00:00
> Cleaned area: 0.0 m²
> DND enabled: 0
> Map present: 1
> in_cleaning: 0"
```

## Funktionen

folgende Werte/Funktionen können vom Saugroboter ausgelesen bzw. gestartet werden:
- Start
- Stop/ zur Ladestation fahren
- Pause
- Finden
- Spotreinigung
- Lüftergesschwindigkeit ändern
- Lautstärke ansage ändern
- gerenigte Fläche
- Reinigungszeit
- Status
- Zustand
- Fehlercode

uvm.
