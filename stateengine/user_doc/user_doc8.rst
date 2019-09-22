.. index:: Plugins; Stateengine
.. index:: Stateengine; Beispiel

Beispiel
########

Die wichtigsten Elemente und Funktionen des Plugins sind soweit
vorgestellt. Zusätzliche Features werden abschließend unter
:ref:`Advanced` zusammengefasst.

Zusammenfassend soll in diesem Beispiel die Automatisierung eines Raffstores
gezeigt werden. Es werden Funktionen genutzt, die erst im Advanced-Teil
beschrieben werden. Folgende Zustände sollen abgedeckt werden:

-  Sperre über Sperr-Item
-  Zeitweises Deaktivieren ("Suspend") bei manuellen Aktionen
-  Sonnenschutz: Nachführen der Lamellen zum Sonnenstand bei großer Helligkeit
-  Nacht
-  Tag

.. rubric:: Items zum Prüfen
   :name: itemszumpruefen

Zuerst benötigen wir ein paar Items, die nachher als Bedingungen
abgeprüft werden sollen. Die boolschen Items sind insofern relevant,
als dass anschließend das Alter der entsprechenden Mindesthelligkeit
abgefragt werden kann. Eine Jalousie soll also beispielsweise erst
dann schließen, wenn die Sonne min. X Minuten heraußen ist. Und erst
wieder öffnen, wenn die Sonne länger als Y Minuten verdeckt ist.

.. code-block:: yaml

   #items/item.yaml
   beispiel:
           steckdosen:
               type: bool

           licht:
               type: bool

           wetterstation:
               helligkeit:
                   name: Helligkeit
                   type: num
                   initial_value: 50000 #nur für Demozwecke

                   gt43k:
                       type: bool
                       name: Helligkeit größer als 43 kLux
                       eval: sh.beispiel.wetterstation.helligkeit() > 43000
                       eval_trigger: beispiel.wetterstation.helligkeit

                   gt35k:
                       type: bool
                       name: Helligkeit größer als 35 kLux
                       eval: sh.beispiel.wetterstation.helligkeit() > 35000
                       eval_trigger: beispiel.wetterstation.helligkeit

                   gt25k:
                       type: bool
                       name: Helligkeit größer als 25 kLux
                       eval: sh.beispiel.wetterstation.helligkeit() > 25000
                       eval_trigger: beispiel.wetterstation.helligkeit

                   gt20k:
                       type: bool
                       name: Helligkeit größer als 20 kLux
                       eval: sh.beispiel.wetterstation.helligkeit() > 20000
                       eval_trigger: beispiel.wetterstation.helligkeit

               temperatur:
                   name: Temperatur
                   type: num
                   initial_value: 24 #nur für Demozwecke

.. rubric:: Trigger
   :name: trigger

Da wir mehrere Raffstores automatisieren wollen und alle
Raffstores gleichzeitig fahren sollen, brauchen wir einen externen
Trigger, auf den dann alle Automatiken hören:

.. code-block:: yaml

   #items/item.yaml
   beispiel:
           trigger:
               raffstore:
                   type: bool
                   name: Gemeinsamer Trigger für alle Raffstores
                   enforce_updates: yes #Wichtig!
                   cycle: 60 = 1


In diesem Fall wird die Zustandsermittlung jede Minute ausgelöst.

.. rubric:: Default-Konfiguration
   :name: defaultkonfiguration

Nun kommt die Default-Konfiguration. Sie ist unabhängig von
konkreten zu automatisierenden Objekten. Sie beinhaltet jedoch
umfangreiche Einstellungen, so dass die zu automatisierenden
Objekte, die die Einstellungen aus der Default-Konfiguration
verwenden, oft sehr simpel aufgebaut werden können.

Es bietet sich an, diese Struktur unter ``etc/struct.yaml`` abzulegen und später
über ``struct: stateengine_default_raffstore`` zu importieren. Auf diese Art
können auch einfach pro Automat Einstellungen wie z.B. die Dauer, welche die
Helligkeit den Schwellwert überschritten haben muss, über ein Item (settings.mindestdauer_helligkeit)
definiert und jederzeit abgeändert werden.

.. code-block:: yaml

   #etc/struct.yaml
   stateengine_default_raffstore:
       settings:
           mindestdauer_helligkeit:
              type: num
              cache: True
              initial_value: 30 #nur für Demozwecke

       rules:
           # Item für Helligkeit außen
           se_item_brightness: beispiel.wetterstation.helligkeit
           # Item für Temperatur außen
           se_item_temperature: beispiel.wetterstation.temperatur
           # Item das anzeigt, ob die Helligkeit außen mehr als 25kLux beträgt
           se_item_brightnessGt25k: beispiel.wetterstation.helligkeit.gt25k
           # Item das anzeigt, ob die Helligkeit außen mehr als 43kLux beträgt
           se_item_brightnessGt43k: beispiel.wetterstation.helligkeit.gt43k
           # Item für Behanghöhe
           se_item_hoehe: ...hoehe
           # Keine Änderung der Behanghöhe wenn Abweichung kleiner 10
           se_mindelta_hoehe: 10
           # Item für Lamellenwinkel
           se_item_lamelle: ...lamelle
           # Keine Änderung des Lamellenwinkels wenn Abweichung kleiner 5
           se_mindelta_lamelle: 5

           # Zustand "Nachführen der Lamellen zum Sonnenstand bei großer Helligkeit", Gebäudeseite 1
           Nachfuehren_Seite_Eins:
               type: foo
               name: Sonnenschutz
               # Aktionen:
               # - Behang ganz herunterfahren
               se_action_hoehe:
                - 'function: set'
                - 'to: 100'
               # - Lamellen zur Sonne ausrichten
               se_action_lamelle:
                 - 'function: set'
                 - 'to: eval:stateengine_eval.sun_tracking()'

               # Einstieg in "Sonnenschutz": Wenn
               enter:
                   # - das Flag "Helligkeit > 43kLux" seit mindestens 30 Sekunden gesetzt ist
                   se_value_brightnessGt43k: true
                   se_agemin_brightnessGt43k: item:..settings.mindestdauer_helligkeit
                   # - die Sonnenhöhe mindestens 1° ist
                   se_min_sun_altitude: 1
                   # - die Sonne aus Richtung 90° bis 270° kommt
                   se_min_sun_azimut: 90
                   se_max_sun_azimut: 270
                   # - es draußen mindestens 22° hat
                   se_min_temperature: 22

               # Hysterese für Helligkeit: Wenn
               enter_hysterese:
                   # ... wir bereits in "Sonnenschutz" sind
                   se_value_laststate: var:current.state_id
                   # .... das Flag "Helligkeit > 25kLux" gesetzt ist
                   se_value_brightnessGt25k: true
                   se_min_sun_altitude: 1
                   se_min_sun_azimut: 90
                   se_max_sun_azimut: 270
                   # Anmerkung: Hier keine erneute Prüfung der Temperatur, damit Temperaturschwankungen nicht
                   # zum Auf-/Abfahren der Raffstores führen

               # Verzögerter Ausstieg nach Unterschreitung der Mindesthelligkeit: Wenn
               enter_delay:
                   # ... wir bereits in "Sonnenschutz" sind
                   se_value_laststate: var:current.state_id
                   # .... das Flag "Helligkeit > 25kLux" nicht (!) gesetzt ist, aber diese Änderung nicht mehr als 1 Minute her ist
                   se_value_brightnessGt25k: false
                   se_agemax_brightnessGt25k: 60
                   se_min_sun_altitude: 1
                   se_min_sun_azimut: 90
                   se_max_sun_azimut: 270
                   # Anmerkung: Auch hier keine erneute Prüfung der Temperatur, damit Temperaturschwankungen nicht
                   # zum Auf-/Abfahren der Raffstores führen

           # Zustand "Nachführen der Lamellen zum Sonnenstand bei großer Helligkeit", Gebäudeseite 2
           Nachfuehren_Seite_Zwei:
               type: foo
               # Einstellungen des Vorgabezustands "Nachfuehren_Seite_Eins" übernehmen
               # Hier sollte eine relative Addressierung vorgenommen werden.
               se_use: ..Nachfuehren_Seite_Eins

               # Sonnenwinkel in den Bedingungsgruppen anpassen
               enter:
                   # ... die Sonne aus Richtung 220° bis 340° kommt
                   se_min_sun_azimut: 220
                   se_max_sun_azimut: 340

               enter_hysterese:
                   # ... die Sonne aus Richtung 220° bis 340° kommt
                   se_min_sun_azimut: 220
                   se_max_sun_azimut: 340

               enter_delay:
                   # ... die Sonne aus Richtung 220° bis 340° kommt
                   se_min_sun_azimut: 220
                   se_max_sun_azimut: 340

           # Zustand "Nacht"
           Nacht:
               type: foo
               name: Nacht
               # Aktionen:
               # - Behang ganz herunterfahren
               se_action_hoehe:
                - 'function: set'
                - 'to: 100'
               # - Lamellen ganz schließen
               se_action_lamelle:
                - 'function: set'
                - 'to: 0'

               # Einstieg in "Nacht": Wenn
               enter:
                   # - es zwischen 16:00 und 08:00 Uhr ist
                   se_min_time: '08:00'
                   se_max_time: '16:00'
                   se_negate_time: True
                   # - die Helligkeit höchstens 90 Lux beträgt
                   se_max_brightness: 90

           # Zustand "Tag"
           Tag:
               type: foo
               name: Tag (statisch)
               # Aktionen:
               # - Behang ganz hochfahren
               se_action_hoehe:
                - 'function: set'
                - 'to: 0'

               # Einstieg in "Tag": Wenn
               enter:
                   # - es zwischen 06:30 und 21:30 Uhr ist
                   se_min_time: '03:30'
                   se_max_time: '23:30'


.. rubric:: Automatisierung Raffstore 1
   :name: automatisierungraffstore1

Jetzt wollen wir den ersten Raffstore automatisieren. Einige Items
dazu haben wir sowieso schon, da der Raffstore über diese Items
gesteuert wird.

.. code-block:: yaml

   #items/item.yaml
   beispiel:
       raffstore1:
           name: Raffstore Beispiel 1

           aufab:
               type: bool
               name: Raffstore auf/ab fahren
               enforce_updates: on

           step:
               type: bool
               name: Raffstore Schritt fahren/stoppen
               enforce_updates: on

           hoehe:
               type: num
               name: Behanghöhe des Raffstores

           lamelle:
               type: num
               name: Lamellenwinkel des Raffstores

Jetzt kommen noch die Items zur Automatisierung und schließlich
das stateengine Regelwerk-Item hinzu. Das Erledigen wir über das Einbinden
der :ref:`Zustands-Templates`, die das Plugin mitbringt sowie der eigenen vorhin angelegten
Vorlage. Beim ``manuell`` Item müssen Eval-Trigger und manual_exclude den
eigenen Umständen entsprechen angepasst werden. Die ``eval_trigger`` des
Regelwerk-Items "rules" sollen ebenfalls je nach Bedarf ergänzt werden.

.. code-block:: yaml

   #items/item.yaml
   beispiel:
       raffstore1:
           automatik:
               struct:
                 - stateengine.general
                 - stateengine.state_lock
                 - stateengine.state_suspend
                 - stateengine_default_raffstore

               manuell:
                   # Weitere Attribute werden bereits über das Template stateengine.state_suspend geladen
                   eval_trigger:
                       - beispiel.raffstore1.aufab
                       - beispiel.raffstore1.step
                       - beispiel.raffstore1.hoehe
                       - beispiel.raffstore1.lamelle
                   se_manual_exclude:
                       - 'KNX:0.0.0' # Hier die Gruppenadresse des Schalt/Jalousieaktors angeben!
                       - 'Init:*'
                       - 'database:*'

               rules:
                   # Relevante Standard-Attribute werden durch den Import der Templates automatisch eingebunden.
                   # Item-Referenzen mittels se_item werden durch das oben eigens angelegte Template eingebunden.
                   # Erste Zustandsermittlung nach 30 Sekunden
                   se_startup_delay: 5
                   # Über diese Items soll die Statusermittlung ausgelöst werden
                   eval_trigger:
                     - beispiel.trigger.raffstore
                     - beispiel.raffstore1.automatik.anwesenheit
                     - beispiel.raffstore1.automatik.manuell
                     - beispiel.raffstore1.automatik.lock
                     - beispiel.raffstore1.automatik.suspend
                     - beispiel.wetterstation.*

                   # Als letzter Zustandseintrag sollte ein bedingungsloser Standardzustand deklariert werden.
                   # Dieser könnte natürlich auch im Template definiert sein, hier soll aber veranschaulicht werden,
                   # Dass Vorlagen auch durch eigene Zustände ergänzt werden können.
                   Default:
                       name: Tag
                       on_enter_or_stay:
                         # Setzen der Höhe auf 0.
                         se_action_hoehe:
                          - 'function: set'
                          - 'to: 0'
                       enter:
                          type: foo
                          # Dieser Eintrag bleibt leer, damit der Zustand ohne Bedingung aktiviert werden kann.


.. rubric:: Testen der State Engine
  :name: testenderstateengine

Nachdem die oben angegebenen Itemstrukturen angelegt worden sind, bietet sich ein
Test des Systems an, weshalb smarthomeNG mit aktiviertem Plugin gestartet werden sollte.
Es wird empfohlen, das Logfile unter ``var/log/stateengine`` mittels tail -f zu beobachten.

Folgendes wird passieren:

a) 5 Sekunden nach dem Start werden die Zustände lock, suspend, Sonnenschutz, Nacht, Tag evaluiert.

- Beim ersten Durchlauf wird die Bedingung "Hellligkeit höher 43000" wahr sein, da die Helligkeit der Wetterstation für diesen Test auf 50000 gesetzt wurde.
- Das Alter der Helligkeit ist zu gering (muss mindestens eine Minute sein)

Beim ersten Durchlauf wird kein Zustand eingenommen. Der Raffstore bleibt wo er ist.

b) Nach 60 Sekunden wird auf Grund der cycle Angabe der Zustandsautomat erneut aufgerufen. Die Bedingungen werden wie folgt evaluiert:

- Die Helligkeit ist nach wie vor höher als 43000 und diesmal auch alt genug.
- Die Sonnenposition sollte untertags innerhalb der gegebenen Grenzwerte liegen. Findet der Test in der Nacht statt, sollten die entsprechenden Wert für min_altitude und max_azimut angepasst werden.
- Die Temperatur entspricht beim Start 24 Grad, ist also über den vorgegebenen 22 Grad

Beim zweiten Durchlauf wird somit der Zustand Sonnenschutz aktiviert. Der Raffstore fährt herunter.

Let's play god. Ändern wir das Wetter ;) Entweder über das CLI, Visu oder Backend-Plugin oder Admin-Interface:

c) up beispiel.wetterstation.helligkeit=35000

- Die erste Bedingungsgruppe des Sonnenstandzustands ist nicht mehr "wahr", da die Helligkeit zu niedrig ist.
- Es wird ``enter_hysterese`` evaluiert. Da die Helligkeit noch über 25000 und die Sonnenposition gleich wie zuvor ist, ist diese Gruppe wahr.

Der Sonnenschutz bleibt somit aktiv, weil trotz der Helligkeitsverringerung der untere Schwellwert noch überschritten wurde. Der Raffstore bleibt unten.

d) up beispiel.wetterstation.helligkeit=15000

- Die ersten beiden Bedingungsgruppen sind unwahr, da die Helligkeit zu gering ist.
- Durch den Eintrag ``se_agemax_brightnessGt25k: 60`` in der Gruppe ``enter_delay`` wird 60 Sekunden gewartet.

Der Sonnenschutz bleibt nach wie vor, diesmal für 60 Sekunden aktiv, sofern sich sonst beim Wetter nichts mehr ändert. Der Raffstore bleibt unten.

e) Es erfolgt eine weitere Evaluierung des Automaten durch das cycle Attribut:

- Die Helligkeit ist nach wie vor zu gering.
- Es ist schon zu lange her, als die Helligkeit den unteren Grenzwert unterschritten hat.

Der Zustand wird verlassen. Gibt es einen nachfolgenden Zustand, der eingenommen werden kann, ist dies der neue aktive Zustand. Gibt es keine Zustände, die aktiviert werden könnten, verbleibt die State Engine beim letzten aktiven Zustand, also beim Sonnenschutz. Im Beispiel gibt es noch einen Standard "Tag" Eintrag, wodurch der Raffstore hoch fährt.

f) up beispiel.raffstore1.aufab =1

- Durch Triggern des "Manuell" Items wird die Zustandsevaluierung pausiert.

Sämtliche Änderungen der Helligkeit, Temperatur, etc. werden für die suspend_time ignoriert. Die Dauer ist im Template auf 60 Minuten festgelegt, kann aber manuell durch Ändern des entsprechenden Items geändert werden.

g) up beispiel.raffstore1.automatik.settings.suspendduration = 1

- Die Suspendzeit wird auf eine Minute verkürzt.
- Beim erneuten Durchlauf ist die Suspendzeit abgelaufen, daher dieser Zustand nicht mehr aktiv.

Es werden wieder sämtliche Zustände evaluiert.


.. rubric:: Automatisierung Raffstore 2
   :name: automatisierungraffstore2

Der zweite Raffstore ist ein komplexeres Beispiel. Hier werden
nicht nur die Vorgabewerte übernommen, hier werden komplett neue
Bedingungsgruppen definiert, sowie vorhandene Bedingungsgruppen
abgeändert. Es wird explizit auf Template-Imports via struct verzichtet.

.. code-block:: yaml

   #items/item.yaml
   beispiel:
       raffstore2:
           name: Raffstore Beispiel 2

           aufab:
               type: bool
               name: Raffstore auf/ab fahren
               enforce_updates: on

           step:
               type: bool
               name: Raffstore Schritt fahren/stoppen
               enforce_updates: on

           hoehe:
               type: num
               name: Behanghöhe des Raffstores

           lamelle:
               type: num
               name: Lamellenwinkel des Raffstores

           automatik:
               lock:
                   type: bool
                   name: Sperr-Item
                   visu_acl: rw
                   cache: on

               suspend:
                   type: bool
                   name: Suspend-Item
                   visu_acl: rw
                   # Achtung: Beim "Suspend"-Item niemals "enforce_updates = yes" setzen! Das führt dazu dass das Setzen des
                   # Suspend-Items bei der Initialisierung zu einem endlosen sofortigen Wiederaufruf der Statusermittlung führt!

               state_id:
                   type: str
                   name: Id des aktuellen Zustands
                   visu_acl: r
                   cache: on

               state_name:
                   type: str
                   name: Name des aktuellen Zustands
                   visu_acl: r
                   cache: on

               manuell:
                   type: bool
                   name: Manuelle Bedienung
                   # Änderungen dieser Items sollen als manuelle Bedienung gewertet werden
                   eval_trigger:
                       - beispiel.raffstore2.aufab
                       - beispiel.raffstore2.step
                       - beispiel.raffstore2.hoehe
                       - beispiel.raffstore2.lamelle
                   # Änderungen, die ursprünglich von diesen Triggern (<caller>:<source>) ausgelöst wurden, sollen nicht als manuelle Bedienung gewertet werden
                   se_manual_exclude:
                       - KNX:y.y.y
                       - Init:*

               anwesenheit:
                   type: bool
                   name: Anwesenheit im Raum
                   eval: or
                   eval_trigger:
                       - beispiel.steckdosen
                       - beispiel.licht

               rules:
                   type: bool
                   name: Automatik Raffstore 2
                   se_plugin: active
                   # Erste Zustandsermittlung nach 30 Sekunden
                   se_startup_delay: 30
                   # Über diese Items soll die Statusermittlung ausgelöst werden
                   eval_trigger: beispiel.trigger.raffstore | beispiel.raffstore2.automatik.anwesenheit | beispiel.raffstore2.automatik.manuell | beispiel.raffstore2.automatik.lock | beispiel.raffstore2.automatik.suspend
                   # In dieses Item soll die Id des aktuellen Zustands geschrieben werden
                   se_laststate_item_id: ..state_id
                   # In dieses Item soll der Name des aktuellen Zustands geschrieben werden
                   se_laststate_item_name: ..state_name
                   # Dieses Item zeigt die Anwesenheit im Raum
                   se_item_anwesend: ..anwesenheit
                   # Item das anzeigt, ob die Helligkeit außen mehr als 35kLux beträgt
                   se_item_brightnessGt35k: beispiel.wetterstation.helligkeit.gt35k
                   # Item das anzeigt, ob die Helligkeit außen mehr als 20Lux beträgt
                   se_item_brightnessGt20k: beispiel.wetterstation.helligkeit.gt20k

                   Lock:
                       # Zustand "Lock": Nur die Vorgabeeinstellungen übernehmen. Diese müssten laut Vorlage unter Advanced angelegt werden!
                       se_use: stateengine_default_raffstore.rules.Lock

                   Suspend:
                       # Zustand "Suspend": Nur die Vorgabeeinstellungen übernehmen. Diese müssten laut Vorlage unter Advanced angelegt werden!
                       se_use: stateengine_default_raffstore.rules.Suspend

                   Nachfuehren:
                       # Zustand "Nachführen": Vorgabeeinstellungen übernehmen
                       se_use: stateengine_default_raffstore.rules.Nachfuehren_Seite_Eins

                       # ..und jetzt verändern wir das ganze, in dem wir abhängig vom "Anwesend"-Flag andere
                       # Grenzwerte für die Helligkeit setzen.

                       # Erst definieren wir mal zusätzliche Einstiegsbedingungen, die die neuen Grenzwerte beinhalten:
                       :enter_anwesend:
                           # Einstieg in "Nachführen" bei Anwesenheit: Wenn
                           # - das Flag "Anwesenheit" gesetzt ist
                           se_value_anwesend: true
                           # - das Flag "Helligkeit > 35kLux" seit mindestens 60 Sekunden gesetzt ist (also 8k Lux früher als in "enter")
                           se_value_brightnessGt35k: true
                           se_agemin_brightnessGt35k: 60
                           # - die Sonnenhöhe mindestens 15° ist (also 3° früher als in "enter")
                           se_min_sun_altitude: 15
                           # - die Sonne aus Richtung 110° bis 270° kommt (also 20° früher als in "enter"
                           se_min_sun_azimut: 110
                           se_max_sun_azimut: 270

                       enter_anwesend_hysterese:
                           # Hysterese für Helligkeit bei Anwesenheit: Wenn
                           # - das Flag "Anwesenheit" gesetzt ist
                           se_value_anwesend: true
                           # ... wir bereits in "Nachführen" sind
                           se_value_laststate: var:current.state_id
                           # .... das Flag "Helligkeit > 20kLux" gesetzt ist (also 5 kLux früher als in "enter_hysterese")
                           se_value_brightnessGt20k: true
                           # ... die Sonnenhöhe mindestens 15° ist (Übernahme aus "enter_anwesend")
                           se_min_sun_altitude: 15
                           # ... die Sonne aus Richtung 110° bis 270° kommt (Übernahme aus "enter_anwesend")
                           se_min_sun_azimut: 110
                           se_max_sun_azimut: 270

                       enter_anwesend_delay:
                           # Verzögerter Ausstieg nach Unterschreitung der Mindesthelligkeit bei Anwesenheit: Wenn
                           # - das Flag "Anwesenheit" gesetzt ist
                           se_value_anwesend: true
                           # ... wir bereits in "Nachführen" sind
                           se_value_laststate: var:current.state_id
                           # .... das Flag "Helligkeit > 20kLux" nicht (!) gesetzt ist, aber diese Änderung nicht mehr als 20 Minuten her ist
                           se_value_brightnessGt20k: false
                           se_agemax_brightnessGt20k: 1200
                           # ... die Sonnenhöhe mindestens 15° ist (Übernahme aus "enter_anwesend")
                           se_min_sun_altitude: 15
                           # ... die Sonne aus Richtung 110° bis 270° kommt (Übernahme aus "enter_anwesend")
                           se_min_sun_azimut: 110
                           se_max_sun_azimut: 270

                       # Jetzt müssen wir die vorhandenen Bedingungen noch erweitern (sie gelten ja nur noch, wenn "Anwesenheit" nicht gesetzt ist)
                       enter:
                           # Einstieg in "Nachführen": Wenn zusätzlich
                           # - das Flag "Anwesenheit" nicht gesetzt ist
                           se_value_anwesend: false

                       enter_hysterese:
                           # Hysterese für Helligkeit: Wenn zusätzlich
                           # - das Flag "Anwesenheit" nicht gesetzt ist
                           se_value_anwesend: false

                       enter_delay:
                           # Verzögerter Ausstieg nach Unterschreitung der Mindesthelligkeit:  Wenn zusätzlich
                           # - das Flag "Anwesenheit" nicht gesetzt ist
                           se_value_anwesend: false

                   Nacht:
                       # Zustand "Nacht": Vorgabeeinstellungen übernehmen
                       se_use: stateengine_default_raffstore.rules.Nacht
                       # .. und zwei weitere Einstiegsbedingungen definieren

                       enter_schlafenszeit_woche:
                           # Einstieg in "Nacht": Wenn
                           # - es zwischen 21:00 und 07:00 Uhr ist
                           se_min_time: '07:00'
                           se_max_time: '21:00'
                           se_negate_time: True
                           # - der Wochentag zwischen Montag und Freitag liegt
                           se_min_weekday: 0
                           se_max_weekday: 4

                       enter_schlafenszeit_wochenende:
                           # Einstieg in "Nacht": Wenn
                           # - es zwischen 21:00 und 08:30 Uhr ist
                           se_min_time: '08:30'
                           se_max_time: '21:00'
                           se_negate_time: True
                           # - der Wochentag Samstag oder Sonntag ist
                           se_value_weekday:
                            - 5
                            - 6

                   Tag:
                       # Zustand "Tag": Vorgabeeinstellungen übernehmen
                       se_use: stateengine_default_raffstore.rules.Tag
