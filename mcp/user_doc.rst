.. index:: Plugins; mcp (MCP Server)
.. index:: mcp

===
mcp
===

Das Plugin stellt einen MCP-Server (Model Context Protocol) bereit. Damit können KI-Agenten wie
Claude Code Items lesen und (nur wo erlaubt) schreiben, auf Diagnosedaten zugreifen und auf
Änderungen von Items warten - mit typisierten Werkzeugen statt mit selbst gebauten REST-Aufrufen.

Typische Anwendungen:

- Diagnose: Welchen Wert hat ein Item, wer hat es zuletzt geändert, welche Logiken laufen wann, welche
  Plugins sind geladen?
- Entwicklung: Ein Item setzen und beobachten, was daraufhin passiert (``set_item`` und
  ``wait_for_change``).
- Unterstützung beim Schreiben von Konfiguration, weil der Agent die echte Item-Struktur sehen kann.

Anforderungen
=============

- Python 3.11 oder neuer.
- Das Python-Paket ``mcp`` (Version 2.3 oder neuer, aber unter 3). Es wird über die ``requirements.txt``
  des Plugins installiert.
- Eine SmartHomeNG-Version, deren Admin-Modul PyJWT 2.10 oder neuer zulässt. Das Paket ``mcp`` benötigt
  ``pyjwt[crypto]>=2.10.1``.

Sicherheit
==========

.. warning::

   Ein MCP-Client sieht Item-Werte und Diagnosedaten und kann Items schreiben, die dafür freigegeben
   sind. Alles, was ein Werkzeug zurückgibt, wird als Kontext an den Anbieter des KI-Modells übertragen.
   Item-Werte und Logeinträge können Zeichenketten enthalten, die von Geräten oder aus dem Netzwerk
   stammen. Ein präparierter Text kann ein Modell zu unerwünschten Aktionen verleiten.

Das Plugin begrenzt deshalb, was ein Client sehen und tun kann:

- **Kein Zugriff ohne Token.** Jede Anfrage braucht den Header ``Authorization: Bearer <token>``. Ohne
  konfiguriertes ``token`` startet das Plugin nicht.
- **Nur lokal, solange nichts anderes konfiguriert ist.** Der Server bindet an ``127.0.0.1``. Eine andere
  ``bind_address`` öffnet ihn für das Netzwerk; das Plugin warnt dann bei jedem Start, auch wenn kein TLS
  und keine ``allowed_hosts`` konfiguriert sind (siehe `Zugriff von anderen Rechnern`_).
- **Jeder Client hat sein eigenes Token und seine eigenen Rechte** (siehe ``clients``). Fehlgeschlagene
  Anmeldungen werden mit der Adresse des Absenders protokolliert (nie mit dem Token) und gebremst.
- **Items sind standardmäßig unsichtbar.** Ohne Attribut ``mcp_access`` (und mit ``default_access: none``)
  gibt es das Item für den Client nicht: Es fehlt in Listen, und jeder direkte Zugriff liefert dieselbe
  Antwort wie für ein nicht vorhandenes Item.
- **Schreiben nur mit ``rw``.** Ein Standard-Zugriff ``rw`` ist nicht möglich.
- **Schreibzugriffe sind begrenzt** (``write_rate_limit``) und im Item-Verlauf erkennbar
  (``last_change_by`` enthält ``mcp:local``).
- Konfiguration, Logik-Quelltext, das Auswerten von Ausdrücken, das Ausführen von Logiken sowie das
  Neustarten oder Neuladen von Plugins sind über dieses Plugin nicht verfügbar.

.. note::

   Das Plugin schützt nicht vor einem Agenten, der ohnehin Dateizugriff auf die Installation oder
   Zugriff auf die Admin-Oberfläche hat. Ein solcher Agent kann Konfiguration, Logiken und Plugins ändern
   und SmartHomeNG neu starten. Die Zugriffsstufen verhindern Fehlgriffe und begrenzen Clients ohne
   solchen Zugriff.

Konfiguration
=============

.. important::

      Detaillierte Informationen zur Konfiguration des Plugins sind unter :doc:`/plugins_doc/config/mcp` zu finden.

plugin.yaml
-----------

.. code-block:: yaml

   mcp:
       plugin_name: mcp
       token: <zufälliges Token>
       # alle weiteren Parameter sind optional

Es kann nur eine Instanz des Plugins betrieben werden.

token
^^^^^

Pflichtparameter. Jeder Client muss dieses Token senden. Ein geeignetes Token erzeugt man zum Beispiel
mit:

.. code-block:: shell

   python -c "import secrets; print(secrets.token_urlsafe(32))"

clients
^^^^^^^

Weitere Clients mit eigenem Token, zum Beispiel ein Agent ohne Dateizugriff auf den Host. Der Parameter
``token`` gehört dem Client ``local``; jeder weitere Client erhält einen Namen und eigene Einstellungen:

.. code-block:: yaml

   mcp:
       plugin_name: mcp
       token: <Token für local>
       clients:
           desktop:
               token: <anderes Token, mindestens 16 Zeichen>
               default_access: ro      # Standard none
               max_access: ro          # Obergrenze, Standard ro; rw erlaubt Schreiben
               expose: [system]        # Standard []
               write_paths: [lights.*] # optional: nur diese Item-Pfade bleiben beschreibbar
               elevate_to: rw          # optional: Ceiling, das ein Administrator zeitweise gewähren darf
               elevate_minutes: 30     # Dauer einer Erhöhung, Standard 30
               write_rate_limit: 10    # Standard: Wert des Plugin-Parameters

Ein Client erhält ohne weitere Angaben die restriktivsten Werte: Er sieht nur Items, die ``mcp_access``
freigibt, stellt keine Diagnosegruppe bereit und darf nicht schreiben. ``max_access`` begrenzt, was ein Item
dem Client gewähren kann (``ro`` macht aus ``rw`` ein ``ro``, ``none`` blendet alles aus). ``write_paths`` ist eine
Liste von Pfadmustern (``fnmatch``, ``*`` steht auch für Punkte): Nur dort bleibt ``rw`` erhalten, alle anderen
Items sind für den Client schreibgeschützt; ohne Angabe gibt es keine Einschränkung. Jeder Client hat
sein eigenes Schreibfenster. Mit ``elevate_to`` (muss über ``max_access`` liegen) kann ein Administrator im
Webinterface des Plugins die Obergrenze für ``elevate_minutes`` Minuten anheben, zum Beispiel einen
schreibgeschützten Client für eine Sitzung auf ``rw``. Die Erhöhung liegt nur im Speicher und endet mit dem
Ablauf der Zeit, über den Knopf „Beenden“ oder beim Neustart von shng; ``write_paths`` gilt weiter. ``inherit_rw_access`` gilt je Client. Namen und Tokens müssen eindeutig sein;
``local`` ist als Name reserviert. Ein Token wird nur vom Plugin geprüft: Wer es kennt, handelt als dieser
Client. Ein ungültiger Eintrag verhindert den Start des Plugins.

allowed_networks (je Client)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Liste von Adressen oder Netzen in CIDR-Schreibweise, von denen sich der Client verbinden darf, zum Beispiel
``['192.168.1.0/24', '::1']``. Verbindet sich der Client mit gültigem Token von einer anderen Adresse, antwortet
der Server mit 403 und protokolliert das. Ohne Angabe gibt es keine Einschränkung. Hinter einem Reverse Proxy
zählt die Adresse, die der Proxy in ``X-Forwarded-For`` meldet, sofern der Proxy lokal läuft.

Webinterface
^^^^^^^^^^^^

Das Plugin hat ein Webinterface (``/plugin/mcp`` im Webinterface-Modul ``http``). Es zeigt den Endpunkt, die Clients
mit ihren Einstellungen, der Zahl der Anfragen und dem Zeitpunkt der letzten Anfrage, die Knöpfe zum Erhöhen
und Beenden einer Erhöhung und den Befehl zum Verbinden von Claude Code. Tokens zeigt es nie an. Die Knöpfe
senden ein Formular mit einem Token, das nur die ausgelieferte Seite kennt, damit eine fremde Webseite sie
nicht auslösen kann. Das Webinterface selbst ist, wie das der anderen Plugins, nicht durch das Plugin
geschützt.

bind_address und port
^^^^^^^^^^^^^^^^^^^^^

Standard ist ``127.0.0.1`` und Port ``8765``. Der Endpunkt lautet ``http://<bind_address>:<port>/mcp``.

default_access
^^^^^^^^^^^^^^

Zugriff auf Items, in deren Hierarchie kein ``mcp_access`` gesetzt ist: ``none`` (Standard) oder ``ro``.
``rw`` ist nicht zulässig.

inherit_rw_access
^^^^^^^^^^^^^^^^^

Standard ``false``. Bei ``true`` erben Unter-Items den Zugriff ``rw`` ihres Eltern-Items. Nur für Test und
Entwicklung gedacht; das Plugin warnt bei jedem Start.

expose
^^^^^^

Liste der Diagnosegruppen, die zusätzlich zu den Items bereitgestellt werden. Standard ist die leere Liste.
Mögliche Werte:

========== ==========================================================================
Gruppe     Werkzeuge
========== ==========================================================================
plugins    ``list_plugins``, ``get_plugin_info``
scheduler  ``list_schedulers``
logics     ``list_logics``
threads    ``get_threads``
system     ``get_system_info``
logs       ``get_logs``
history    ``get_item_history`` (nur mit laufendem database-Plugin)
========== ==========================================================================

write_rate_limit
^^^^^^^^^^^^^^^^

Maximale Schreibzugriffe über MCP pro Minute, gleitendes Fenster über alle Items. Standard ``30``,
``0`` schaltet die Begrenzung ab (zum Beispiel für Lasttests).

log_redact
^^^^^^^^^^

Liste regulärer Ausdrücke. Treffer in Lognachrichten werden durch ``***`` ersetzt, bevor ``get_logs`` sie
ausliefert. Zusätzlich gelten immer eingebaute Muster für Werte hinter Namen wie ``password``, ``token``,
``secret``, ``api_key`` und ``authorization``, für ``Bearer``/``Basic``-Zugangsdaten und für Benutzer und
Passwort in URLs (``://benutzer:passwort@``). Das ist eine Hilfe, keine Garantie: Geheimnisse in anderer Form
erkennt das Plugin nicht. Der Filter ``contains`` sucht im bereits bereinigten Text.

tls_certfile und tls_keyfile
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

PEM-Dateien mit Zertifikat und privatem Schlüssel. Nur zusammen gesetzt spricht der Server HTTPS statt HTTP;
das Plugin startet nicht, wenn nur eine der Dateien angegeben ist oder eine fehlt. Der Endpunkt lautet dann
``https://...``.

allowed_hosts und allowed_origins
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Zusätzlich zu ``127.0.0.1``, ``localhost`` und ``::1`` erlaubte Werte des ``Host``- und des ``Origin``-Headers,
zum Beispiel ``['shng.example:*']`` (``*`` steht für den Port) und ``['https://app.example']``. Anfragen ohne
``Origin`` sind immer erlaubt, ein anderer Host oder Origin wird mit 421 bzw. 403 abgewiesen. Ohne Angabe prüft
das Plugin den Host nur bei einer Loopback-Adresse; bei einer anderen ``bind_address`` ist die Prüfung dann aus,
und das Plugin warnt. Wird der Server unter einem Namen erreicht (Reverse Proxy), muss dieser Name in
``allowed_hosts`` stehen.

auth_failure_limit
^^^^^^^^^^^^^^^^^^

Fehlgeschlagene Anmeldungen pro Minute und Absenderadresse, ab denen der Server mit 429 und ``Retry-After``
antwortet (Standard ``20``, ``0`` schaltet ab). Ein gültiges Token wird nie gebremst. Die ersten Fehlversuche je
Minute stehen mit der Adresse im Log.

history_plugin und history_max_days
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``history_plugin`` ist der Abschnittsname (aus ``plugin.yaml``) der Instanz des ``database``-Plugins, aus der
``get_item_history`` liest; leer nimmt die erste laufende Instanz. ``history_max_days`` (Standard ``7``) ist die
größte Zeitspanne, die eine Anfrage lesen darf. Die Abfrage lädt die Zeilen des Zeitfensters in den Speicher; bei
Items mit sehr dichter Protokollierung sollte der Wert klein bleiben.

max_page_size und wait_max_seconds
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Obergrenze für die Seitengröße bei Listen (Standard ``200``) und für die Wartezeit von
``wait_for_change`` in Sekunden (Standard ``30``).

items.yaml
----------

Das Plugin definiert zwei Item-Attribute.

mcp_access
^^^^^^^^^^

``none`` (unsichtbar), ``ro`` (lesen) oder ``rw`` (lesen und schreiben). Für ein Item gilt der erste
explizite Wert, den man beim Aufstieg durch die Hierarchie findet:

=============================================== ===================================================
Fundstelle                                       Zugriff auf das Item
=============================================== ===================================================
``none`` oder ``ro`` am Item oder einem Vorfahr  genau dieser Wert (gilt also für alle Unter-Items)
``rw`` am Item selbst                            ``rw``
``rw`` an einem Vorfahr                          ``ro`` (``rw`` nur mit ``inherit_rw_access``)
ungültiger Wert                                  ``none`` (wird nie als Freigabe gewertet)
nirgends gesetzt                                 ``default_access``
=============================================== ===================================================

mcp_rate_limit
^^^^^^^^^^^^^^

Schreibzugriffe pro Minute für dieses Item. Der Wert ersetzt für dieses Item das globale
``write_rate_limit``: Das Item hat sein eigenes Fenster und verbraucht nichts vom globalen. ``0`` bedeutet
unbegrenzt.

Beispiel
^^^^^^^^

.. code-block:: yaml

   haus:
       mcp_access: ro              # alles darunter ist lesbar

       wohnzimmer:
           licht:
               type: bool
               mcp_access: rw      # nur dieses Item ist schreibbar
               mcp_rate_limit: 10

       alarmanlage:
           mcp_access: none        # samt aller Unter-Items unsichtbar

Werkzeuge
=========

Alle Listen werden seitenweise geliefert: ``limit`` (Standard 50, begrenzt durch ``max_page_size``) und
``cursor`` (aus der vorherigen Antwort; ``null`` auf der letzten Seite).

================== =========================================== =======================================================
Werkzeug           Argumente                                   Ergebnis
================== =========================================== =======================================================
list_items         prefix, type, has_attr, limit, cursor       sichtbare Items (Pfad, Typ, Wert, Zugriff), nach Pfad
get_item           path, detail (``value`` oder ``full``)      Item; ``full`` ergänzt Name, Beschreibung, Zeitstempel,
                                                               Kinder, Trigger und Attribute ohne geheim wirkende Namen
set_item           path, value                                 ``previous``, ``value`` (direkt danach gelesen),
                                                               ``changed``
wait_for_change    path, timeout                               wartet auf eine Wertänderung; ``changed``, ``value``,
                                                               ``previous``, ``timed_out``
get_access_info    -                                           wirksame Einstellungen dieser Verbindung
list_plugins       limit, cursor                               geladene Plugin-Instanzen
get_plugin_info    name                                        Status einer Plugin-Instanz (Name aus plugin.yaml)
list_schedulers    -                                           Scheduler-Worker, laufende Aufgaben und Einträge
get_logs           file, level, since, contains, limit, cursor Einträge einer Logdatei, neueste zuerst
list_logics        limit, cursor                               Logiken mit nächstem/letztem Lauf, nie der Quelltext
get_threads        limit, cursor                               Threads des Prozesses
get_system_info    -                                           Version, Status, Python, Plattform, pid, Laufzeit
get_item_history   path, since, until, limit, cursor            geloggte Werte des database-Plugins, neueste zuerst
================== =========================================== =======================================================

Hinweise:

- ``get_item_history`` gibt es nur, wenn beim Start des MCP-Servers ein ``database``-Plugin läuft. Es liest über
  dessen öffentliche Schnittstelle die Werte des Items; ``since`` gilt einschließlich, ``until`` ausschließlich
  (ISO 8601, ohne beide die letzten 24 Stunden, eine Zeit ohne Offset ist die lokale Zeit der Instanz). Die Zeiten
  der Einträge sind UTC, ``valid`` ist ``false`` bei Lücken und markierten Zeilen. Der ``cursor`` setzt am Ende
  der Seite fort und wiederholt das Zeitfenster. Ein Item ohne Verlauf liefert ``not_found``, ein Item, das der
  Client nicht sehen darf, dasselbe. Der Dienst gehört zur Gruppe ``history`` aus ``expose``.
- ``set_item`` wandelt den Wert zuerst in den Item-Typ um. Passt er nicht, kommt ``invalid_value`` und es
  wird nichts geschrieben. ``null`` kann nicht geschrieben werden. Der zurückgegebene ``value`` kann vom
  geschriebenen abweichen (zum Beispiel durch ``eval``, Hysterese oder gleichzeitige Schreiber);
  ``changed: false`` ist kein Fehler.
- ``get_plugin_info`` meldet als ``item_count`` die Items, die das Plugin selbst mit ``mcp_access`` gesetzt haben;
  geerbter oder per ``default_access`` gewährter Zugriff zählt nicht.
- ``wait_for_change`` wertet nur echte Wertänderungen; ein Update mit gleichem Wert zählt nicht.
- ``get_logs`` liest die Dateien in ``var/log`` (Namen unter ``log_files`` in ``get_access_info``). ``level``
  ist eine Mindeststufe, ``since`` ein ISO-Zeitstempel in der Zeit der Instanz, ``contains`` ein Text ohne
  Beachtung der Groß-/Kleinschreibung. Ein Traceback gehört zum Eintrag davor. ``ts``, ``level`` und ``logger``
  werden aus dem Format gelesen, mit dem der Logging-Handler die Datei schreibt (``format`` und ``datefmt`` aus
  ``logging.yaml``, also auch ``shng_sh``). Rotierte Dateien wie ``name.2026-10-27.log`` nutzen das Format des
  Handlers von ``name.log``. Ein Datum ohne Jahr (``%m%d``) erhält das jüngste Jahr, das nicht nach der letzten
  Änderung der Datei liegt. Ein einzelner Buchstabe als Stufe (``%(levelname).1s``) steht für die
  Standardstufe, ``D`` also für ``DEBUG``. Dateien ohne Handler lesen Zeilen im Format ``shng_simple``. Zeilen,
  die nicht zum Format passen, kommen als Text zurück und fallen bei ``level`` und ``since`` heraus. Jede Anfrage
  liest die Datei bis zur gewünschten
  Stelle; sehr große Dateien sind
  entsprechend langsam (etwa 4 s für 54 MB). Nachrichten sind auf 4000 Zeichen begrenzt.
- ``list_schedulers`` liefert je Eintrag Name, Zustand, Priorität, nächsten Lauf sowie Zykluszeiten und
  Crontab-Ausdrücke. Das aufgerufene Objekt und der übergebene Wert fehlen bewusst.

Fehler
------

Ein Fehler wird als Werkzeugfehler mit JSON-Text geliefert, zum Beispiel
``{"code": "not_found", "message": "item not found"}``:

================ ======================================================================================
Code             Bedeutung
================ ======================================================================================
not_found        Pfad oder Plugin existiert nicht oder ist für diese Verbindung unsichtbar
forbidden        Schreibzugriff auf ein Item, das nur gelesen werden darf
invalid_value    Wert ist ``null`` oder passt nicht zum Item-Typ
rate_limited     Schreiblimit erreicht; ``retry_after`` nennt die Sekunden bis zum nächsten Versuch
not_exposed      Die Diagnosegruppe ist in ``expose`` nicht freigegeben
bad_request      ungültiges ``limit``, ``cursor``, ``detail`` oder ``timeout``
================ ======================================================================================

Ressource und Abonnement
========================

Zusätzlich zu den Werkzeugen gibt es die Ressourcenvorlage ``shng://item/{pfad}``: Sie liefert ein Item mit
seinen Metadaten wie ``get_item`` mit ``detail=full`` und beachtet dieselben Zugriffsrechte des Clients.

Ein Client, der das Protokoll ``2026-07-28`` des MCP-SDKs spricht, kann mit ``subscriptions/listen`` und
``resource_subscriptions=['shng://item/pfad']`` einen Strom öffnen und erfährt, wann sich der Wert eines Items
geändert hat; er liest das Item dann neu. Das Plugin sendet das Ereignis nur,

- für Items, die selbst ``mcp_access`` tragen (nur sie sind an das Plugin gebunden; für andere gibt es keine
  Ereignisse, dort bleibt ``wait_for_change``),
- wenn der Client das Item laut seiner Rechte sehen darf (ein ausgeblendetes Item bleibt still, auch wenn der
  Client dessen URI abonniert),
- bei einer Wertänderung, nicht bei einem Update mit gleichem Wert, und höchstens einmal je Item in 0,25 s.

Es gibt kein Nachliefern: Reißt der Strom ab, öffnet der Client ihn neu und liest die Items neu. Ob ein
bestimmter Client (Claude Code, Claude Desktop) Abonnements nutzt, hängt von dessen Protokollstand ab und ist hier
nicht geprüft; getestet ist der Weg mit dem Client des MCP-SDKs.

Verbindung mit Claude Code
==========================

Nach dem Eintrag in ``plugin.yaml`` und einem Neustart von SmartHomeNG:

.. code-block:: shell

   claude mcp add --transport http shng http://127.0.0.1:8765/mcp --header "Authorization: Bearer <token>"

Danach stehen die Werkzeuge in Claude Code unter dem Namen ``shng`` zur Verfügung.

Beispiel für eine Entwicklungsinstanz
=====================================

Auf einer eigenen Test- oder Entwicklungsinstanz (nicht auf der produktiven) kann man den Zugriff
großzügiger einstellen:

.. code-block:: yaml

   mcp:
       plugin_name: mcp
       token: <zufälliges Token>
       default_access: ro
       inherit_rw_access: true
       expose: [plugins, scheduler, logics, threads, system]
       write_rate_limit: 120

Dabei ist jedes Item lesbar, und ``rw`` an einem Item gilt auch für alle Unter-Items. Das Plugin warnt bei
jedem Start vor ``inherit_rw_access``.

Im Verzeichnis ``sample_config`` des Plugins liegt eine Beispielkonfiguration (Items mit allen Zugriffsstufen,
eine Logik und ein Skript ``testbed.sh``, das sie in ``etc`` ein- und ausschaltet) mit einer Liste der
erwarteten Ergebnisse in ``README.md``.

Zugriff von anderen Rechnern
============================

Ein zweiter Client ohne Dateizugriff auf den Host (ein Agent auf einem anderen Rechner, Claude Desktop) braucht
vier Dinge, die der Anwender bewusst konfiguriert:

1. ein eigenes Token unter ``clients`` mit den restriktiven Standardwerten und nur den Rechten, die er braucht,
   gegebenenfalls ``allowed_networks`` und ``write_paths``;
2. eine ``bind_address``, unter der der Rechner erreichbar ist (``0.0.0.0`` oder die Adresse der Netzwerkkarte);
3. Verschlüsselung: ``tls_certfile`` und ``tls_keyfile`` oder ein TLS-Proxy davor, sonst läuft das Token im
   Klartext durchs Netz;
4. ``allowed_hosts`` mit dem Namen, unter dem der Server erreicht wird.

Wer das Token kennt und von einer erlaubten Adresse kommt, handelt als dieser Client. Das Token gehört in
``etc/plugin.yaml`` mit Zugriffsrechten nur für den Benutzer von SmartHomeNG und wird nie im Webinterface oder Log
angezeigt. Ein Token, das in falsche Hände geraten ist, ersetzt man in ``plugin.yaml`` und startet SmartHomeNG neu;
bis dahin zeigt das Webinterface die Anfragen des Clients. Ob der jeweilige Client Verbindungen zu einem
Server mit selbst signiertem Zertifikat zulässt, hängt von ihm ab.

Einschränkungen
===============

- Es gibt derzeit nur den Zugriff über ein einziges Token von einem Client, der auf demselben Rechner
  läuft (oder der über ``bind_address`` bewusst erreichbar gemacht wurde). Getrennte Berechtigungen pro
  Token sind nicht vorgesehen.
- Item-Verlauf (Datenbank-Plugin), Benachrichtigungen bei Änderungen (Resource Subscriptions) und eine
  Status-Seite im Web Interface sind nicht enthalten.
