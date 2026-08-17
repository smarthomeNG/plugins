.. index:: Plugins; matter
.. index:: matter

======
matter
======

Matter-Plugin für SmartHomeNG mit zwei unabhängigen Rollen: **server** (kommissioniert und steuert
echte Matter-Geräte direkt - ohne separaten Hub/Bridge/App) und **bridge** (macht shng-Items als
eigene "Geräte" für andere Matter-Ökosysteme sichtbar - Apple Home, Google Home, ...).
Beide Rollen sind individuell über Item-Attribut wählbar; beide laufen in derselben Plugin-Instanz.

Voraussetzungen
===============

Dieses Plugin hat eine Laufzeitabhängigkeit außerhalb von Python (Node.js) und startet zwei
separate Node.js-Prozesse, einen pro Rolle - beide benötigen eine unterstützte Node.js-Version
(``>=20.19.0 <22.0.0 || >=22.13.0``). Mit ``nvm``::

    nvm install lts/jod
    nvm use lts/jod

Beide Rollen teilen sich ein gemeinsames Node.js-Dependency-Verzeichnis, es genügt eine
einzige Installation::

    cd plugins/matter/sidecar
    npm install

Das installiert sowohl den matter-server-Sidecar als auch die von ``bridge.js`` benötigten Pakete.

Konfiguration
=============

Siehe plugin.yaml für die vollständige Parameterliste. 

Item-Attribute
--------------

``matter_node``, ``matter_endpoint``, ``matter_cluster`` adressieren eine bestimmte Gerätefunktion. 
Diese drei müssen nur einmal am Hauptitem eines Geräts gesetzt werden und werden an alle Kind-Items
vererbt.

Für einen Schalter (matter-intern bool-Item im On/Off-Schema, z.B. OnOff) wird ``matter_switch: true``
verwendet. Für alles andere werden die Low-Level-Attribute direkt verwendet: ``matter_attribute``
macht das Item zu einem Read-/Subscribe-Spiegel dieses Attributs. ``matter_command`` (optional mit
``matter_command_params``) lässt eine Änderung des Itemwerts den entsprechenden Befehl auslösen; der
Platzhalter ``"$value"`` in einem Parameterwert wird durch durch den geschriebenen Item-Wert
ersetzet (z.B. für den ``level``-Parameter von ``MoveToLevel``). ``matter_attribute`` und
``matter_command`` können am selben Item gesetzt werden (spiegelt den Status per Subscription, steuert
ihn per Befehl beim Schreiben).

Ein reines Befehls-Item ohne passendes Status-Attribut (z.B. ``toggle``) schreibt immer nur True oder 1
und benötigt daher ``enforce_updates: true`` und ggf. einen ``autotimer``, der ihn wieder auf False oder
0 zurücksetzt.

``matter_available`` (bool, read-only) gibt an, ob das Gerät für den matter-server erreichbar ist.

Geräte dauerhaft benennen: matter_alias
---------------------------------------

``node_id`` wird von matter-server zum Kommissionierungszeitpunkt vergeben und ist über einen
Dekommissionierungs-/Rekommissionierungszyklus hinweg nicht garantiert stabil (Werksreset eines
Geräts, Wechsel von und wieder auf shngs Fabric, ...). Jedes über ein fest eingetragenes
``matter_node`` adressierte Item zeigt danach still auf das falsche Gerät, bis es von Hand
aktualisiert wird.

``matter_alias`` kann statt ``matter_node`` verwendet werden, um einen lesbaren Namen zu benutzen.

Die Zuordnung zu der jeweiligen ``matter_node`` erfolgt im Web-Interface und wird **durch das Plugin**
in Items unterhalb von ``server_alias_base_item`` gesichert. Jedes direkte Kind-Item davon gilt als
eine Alias-Definition. Die ``node_id`` eines Items wird dann bei jedem Zugriff über diese Tabelle 
aufgelöst, statt fest codiert zu sein. Das Basis-Item selbst muss bereits existieren, das Plugin 
legt es nicht selbst an.

bridge-Rolle: shng-Items für andere Matter-Ökosysteme sichtbar machen
=====================================================================

Die bridge-Rolle stellt shng-Items als gebrückte Gerätefunktionen für andere Matter-Controller wie 
Apple Home bereit.

``matter_expose_type`` an einem Item definiert seine matter-Funktion:

- ``switch`` - ein schreibbarer bool-Aktor (``OnOffPlugInUnit``). Vom anderen Controller aus
  beschreibbar; ein Schreiben dort löst über den üblichen Item-Update-Mechanismus zurück ins Item
  aus, und eine Item-Wertänderung wird genauso an den anderen Controller weitergegeben.
- ``contact`` - ein reiner bool-Sensor (``ContactSensor``, z.B. ein Türkontakt), der Werte wird nur 
  von SmartHomeNG aus weitergegeben, es ist keine Änderung über Matter möglich.
- ``temperature_sensor`` - ein reiner Sensor (``TemperatureSensor``), analog zu ``contact``. 
  Der Item-Wert wird als Grad Celsius interpretiert.

``matter_expose_name`` (optional) legt den Namen fest, der dem anderen Controller angezeigt wird.
Ohne ihn wird der vollständige Item-Pfad verwendet.

Das Koppeln der bridge mit dem Fabric eines anderen Controllers (Apple Home, Google Home, ...) 
benötigt den Code oder QR-Code des Bridge-Webinterfaces. Da die bridge nur ein Entwicklungs-/Test-
Attestierungszertifikat (nicht CSA-zertifiziert) hat, zeigen die meisten Controller während der
Kopplung eine Warnung "nicht zertifiziertes Zubehör" an.

Änderungen an ``matter_expose_*``-Attributen werden üblicherweise innerhalb weniger Sekunden über
matter an gekoppelte Controller verteilt. 

Item-Structs
============

``item_structs`` in ``plugin.yaml`` ist als wachsende Sammlung fertiger Vorlagen für bekannte,
getestete Geräte gedacht - nicht als generische Vorlagen pro Cluster. Für diese muss in der Regel
nur ``matter_node`` zusätzlich gesetzt werden. Bisher vorhanden: 

- ``matter.shelly_plug_m_3gen_simple`` (OnOff-Schalter/Toggle + Verfügbarkeit)
- ``matter.shelly_plug_m_3gen`` (zusätzlich mit Messung von Leistung/Spannung/Strom)

Im Test stellte sich heraus, dass die Spannungswerte über Matter nicht immer live übertagen wurden,
obwohl diese im Gerät vorliegen und z.B. über MQTT sehr wohl übertragen werden. Dies sollte im
Zweifelsfall selbst geprüft werden.

Ein Gerät mit Apple Home / Google Home usw. teilen
==================================================

Matter-Geräte unterstützen die gleichzeitige Verbindung zu mehreren Controllern - ein mit shng
gekoppeltes Gerät kann auch einem anderen Ökosystem auf dessen separaten Fabric beitreten, ohne
dass shng seine eigene Kopplung verliert. Der **Teilen**-Button im Devices-Tab öffnet auf diesem
Gerät ein neues 15-minütiges Kopplungsfenster und zeigt sowohl einen scanbaren QR-Code als auch 
den manuellen Pairing-Code (und den rohen QR-Inhalts-String) zur Eingabe in der anderen App.

Der **Fabrics**-Button listet jede aktuell auf einem Gerät vorhandene Fabric (Vendor, Label,
fabric_id) mit einer Entfernen-Option je Fabric. Für das Entfernen aus dem shng-Fabric sollte
der **Entfernen**-Button verwendet werden.

Aktueller Umfang
================

**server-Rolle**: Sidecar-Überwachung, WS-Client, Item-Mapping (generisches Attribut/Befehl, plus
``matter_switch``-Kurzform für bool-On/Off-Cluster), Endpoint-/Cluster-Discovery-Browser und
Copy-Paste-Item-Generator-YAML im Webif.

**bridge-Rolle**: nur ``switch``/``contact``/``temperature_sensor``, Live-Hinzufügen/-Entfernen
von Accessories ohne bridge-Neustart, Webif-Kopplung.
