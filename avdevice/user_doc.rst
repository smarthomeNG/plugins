.. index:: Plugins; avdevice
.. index:: avdevice

avdevice
########

Konfiguration
=============

.. important::

      Detaillierte Informationen zur Konfiguration des Plugins sind unter :doc:`/plugins_doc/config/avdevice` zu finden.


.. code-block:: yaml

    # etc/plugin.yaml
    avdevice:
        class_name: AVDevice
        class_path: plugins.avdevice
        model: sc-lx86
        #instance: pioneer_one
        tcp_ip: 10.0.0.130
        #tcp_port: 23
        #tcp_timeout: 1
        rs232_port: /dev/ttyUSB1
        #rs232_baudrate: 9600
        #rs232_timeout: 0.1
        #ignoreresponse: 'RGB,RGC,RGD,GBH,GHH,VTA,AUA,AUB'
        #forcebuffer: 'GEH01020, GEH04022, GEH05024'
        #inputignoredisplay: ''
        #dependson_item: ''
        #dependson_value: True
        #errorresponse: E02, E04, E06
        #resetonerror: False
        #depend0_power0: False
        #depend0_volume0: False
        #sendretries: 10
        #resendwait: 1.0
        #reconnectretries: 13
        #reconnectcycle: 10
        #secondstokeep: 50
        #responsebuffer: 5
        #autoreconnect: false
        #update_exclude: ''

Kommandodatei
=============

model.txt
ZONE;FUNCTION;FUNCTIONTYPE;SEND;QUERY;RESPONSE;READWRITE;INVERTRESPONSE;MINVALUE;MAXVALUE;RESPONSETYPE;TRANSLATIONFILE

Die Kommandos sind entsprechend der Herstellerangaben je nach Modell unterschiedlich. Der Name der Textdatei muss dem Namen des Modells in der plugin.yaml entsprechen. Wurde dort beispielsweise ``model: vsx-923`` angegeben, muss die Textdatei ``vsx-923.txt`` heißen.

Jede Zeile beinhaltet einen konkreten Befehl, der an das Gerät gesendet werden soll. Außerdem werden Zone, Abfragebefehl, erwartetete Antwort, etc. angegeben. Zeilen können durch ``#``, Blöcke durch ``'''`` auskommentiert werden.

- **zone**: Zahl der Zone. Muss mit dem Attribut in der item.yaml Datei übereinstimmen, für Zone 1 wird beispielsweise ``avdevice_zone1: command`` genutzt. In Zone 0 werden allgemein gültige Funktionen wie Displa, Menü, Info, etc. angegeben.

- **function**: Name der Funktion, die in der item.yaml entsprechend referenziert wird. Der Name kann beliebig vergeben werden.

- **functiontype**: Für boolsche Werte ``on`` oder ``off`` (z.B. power). Für Kommandos, die einen bestimmten Wert, z.B. für Lautstärke, Eingang, etc. setzen, muss hier ``set`` genutzt werden. Um Werte zu erhöhen oder zu verringern (z.B. Lautstärke) sollte ``increase`` bzw. ``decrease`` genutzt werden. Für alle anderen Funktionen bleibt dieser Bereich leer.

- **send**: Das zu sendende Kommando, z.B. "PF" zum Ausschalten von Pioneer Receivern. Eine Pipe ``|`` kann genutzt werden, um mehrere Kommandos zu senden. Eine Zahl wird angegeben, um eine Pause zwischen Kommandos zu definieren, z.B. "PO|2|PO". Das kann von manchen Geräten gerade über RS232 so gefordert sein.
Sterne ``\*`` werden genutzt, um das Format des zu sendenden Werts zu deklarieren. Erwartet das Gerät beispielsweise immer eine Zahl mit drei Stellen, sorgt "\*\*\*VL" (VL wäre hier der Befehl, um die Lautstärke zu setzen) dafür, dass die Lautstärke auch korrekt eingestellt wird, wenn der Wert des Items nur eine Ziffer beinhaltet (z.B. 5 wird zu 005).

- **query**: Abfragekommando. Wird genutzt, um bei der Verbindung initiale Werte abzufragen und zu kontrollieren, ob ein Befehl richtig angekommen ist. Es wird empfohlen, dieses Kommando nur bei on, off oder set Befehlen zu nutzen.

- **response**: Die erwartete Antwort nach dem Senden eines Befehls. ``none`` oder Leerlassen sorgt dafür, dass auf keine Antwort gewartet wird. Ansonsten können wieder Sterne als Platzhalter für den zu erwartenden Wert genutzt werden. Beispiel: Der Lautstärkewert soll auf 100 gesetzt werden. Möchte man sicherstellen, dass die Lautstärke überhaupt gesetzt wird, gibt man hier je nach Gerät z.B. "VOL" ein. Möchte man sicher gehen, dass auch wirklich der gesendete Wert eingestellt wird, gibt man z.B. "VOL\*\*\*" an. Mehrfache Antwortmöglichkeiten werden durch eine Pipe ``|`` getrennt.

- **readwrite**: R steht für nur lesen, w nur schreiben und RW für schreiben und lesen. Die Displayanzeige ist beispielsweise "R", das stufenweise Lauterstellen wäre ein "R", viele andere Befehle sind "RW".

- **invertresponse**: Einige Geräte sind leider so dumm, dass sie ein "0" für "ein" und "1" for "aus" halten. Pioneer Receiver beispielsweise antworten mit "PWR0", wenn es eingeschaltet ist. Wird hier ein ``yes`` angeben, werden diese Werte umgekehrt interpretiert. Eine 1 ist dann also "an" wie es sein sollte.

- **minvalue**: Der minimale Wert, der gesendet werden soll, z.B. für Lautstärke oder Bass-Einstellung. Wird der Wert z.B. auf "-3" definiert, werden niedrigere Itemwerte wie "-5" auf diesen Wert limitiert.

- **maxvalue**: Der minimale Wert, der gesendet werden soll, z.B. für Lautstärke oder Bass-Einstellung. Wird der Wert z.B. auf "100" definiert, wird ein Lautstärkewert von "240" automatisch auf "100" gesetzt.

- **responsetype**: Dieser Wert kann normalerweise leer gelassen werden. Im Problemfall definiert er aber den Typ der Antwort. Dieser kann ``bool``, ``num`` oder ``str`` bzw. eine Mischung davon - getrennt durch Pipe oder Komma - sein. Man sollte sich an den Beispieldateien im Ordner models orientieren.

- **translationfile**: Soll ein bestimmter Wert/Code in etwas anderes übersetzt werden, wird hier der Filename zum Übersetzungsfile angegeben. Weitere Infos zu diesem Feature weiter unten.

.. code-block:: none

    # plugins/avdevice/pioneer.txt
    ZONE; FUNCTION; FUNCTIONTYPE; SEND; QUERY; RESPONSE; READWRITE; INVERTRESPONSE; MINVALUE; MAXVALUE; RESPONSETYPE; TRANSLATIONFILE
    1; power; on; PO|PO; ?P; PWR*; RW; yes
    1; power; off; PF; ?P; PWR*; RW; yes
    1; volume+; increase; VU; ; VOL; W
    1; volume-; decrease; VD; ; VOL; W
    1; volume; set; ***VL; ?V; VOL***; RW; ; 80; 185
    1; source; set; **FN; ?F; FN**; RW
    1; speakers; set; *SPK; ?SPK; SPK*; RW
    '''
    #commented out from here
    2; power; on; APO|APO; ?AP; APR*; RW; yes
    2; power; off; APF; ?AP; APR*; RW; yes
    0; title; ; ; ; GEH01020; R
    0; station; ; ; ; GEH04022; R
    0; genre; ; ; ; GEH05024; R
    #commented out until here
    '''
    0; display; ; ?FL; ?FL; FL******************************; R
    1; set_listeningmode; set; ****SR; ?S; SR****; RW; ; ; ; num; pioneer_SR
    #0; test; ; ; ; noidea; R (commented out)

Struct Vorlagen
===============

Ab smarthomeNG 1.6 können Vorlagen aus dem Plugin einfach eingebunden werden. Dabei stehen folgende Vorlagen zur Verfügung:

- general: Display, Menü, Cursorssteuerung, Statusupdate, Neuladen der Konfiguration, etc.
- speaker_selection: Zur Auswahl von Speaker A, B oder beide
- individual_volume: Zur Einstellung der Lautstärke für jeden einzelnen Lautsprecher
- sound_settings: Listening Mode, Bass und Höhen, dynamische Kompression, etc.
- video_settings: Aspect Ratio, Monitorout, etc.
- zone1, zone2, zone3: Sämtliche für die Zonen relevante Features wie Quelle, Lautstärke, etc.

Die Vorlagen beinhalten möglicherweise zu viele Items bzw. Items, die vom Gerät nicht unterstützt werden. Wenn aber kein entsprechendes Kommando im models/model.txt File hinterlegt ist, werden die betroffenen Items einfach ignoriert. Also kein Problem!

Translation
===========

Es muss eine Datei mit dem Namen, der in model.txt referenziert wurde in den Ordner translations gelegt werden.
Beispielsweise könnte eine Datei mit dem Namen denon_volume.txt angelegt werden, um eine dreistellige Lautstärkeangabe in eine Fließkommanzahl umzuwandeln. Für Denon Verstärker ist nämlich beispielsweise 50.5 intern 505. Folgendes File würde dafür sorgen, dass der richtige Wert in der Visu angezeigt wird:

.. code-block:: none

    # plugins/avdevice/denon_volume.txt
    CODE; TRANSLATION
    ***; **.*

Pioneerverstärker nutzen Nummern, um den Eingang oder Listening Mode zu definieren, was recht kryptisch ist. Eine elegante Lösung ist es, eine Datei namens pioneer_source in den translations Ordner zu legen und diesen in model.txt zu referenzieren. Die Datei könnte so aussehen:

.. code-block:: none

    # plugins/avdevice/pioneer_input.txt
    CODE; TRANSLATION
    00; PHONO
    01; CD
    02; TUNER

Wenn nun das Plugin FN01 als Antwort erhält, wird der Wert 1 automatisch in "CD" umgewandelt. Umgekehrt funktioniert es gleich. Es wird empfohlen, das entsprechende Item als type foo zu definieren, um beide Varianten, also String und Zahl, nutzen zu können.

Wildcards
=========

Im model.txt File können Fragezeichen als Wildcards deklariert werden, falls die erwartete Antwort Information für mehrere Items enthält. Dies ist beispielsweise bei Oppo Playern der Fall.

``?`` stünde somit für "jeders beliebige Zeichen", ``??`` für beliebige zwei Zeichen, etc. Wenn die Länge des Eintrags unklar ist, z.B. weil es sich um einen String mit unterschiedlicher Länge handelt, wird ein ``?{str}`` genutzt.

.. code-block:: none

    # plugins/avdevice/oppo-udp203.txt
    ZONE; FUNCTION; FUNCTIONTYPE; SEND; QUERY; RESPONSE; READWRITE; INVERTRESPONSE; MINVALUE; MAXVALUE; RESPONSETYPE; TRANSLATIONFILE
    0; audiotype; ; ; #QAT; @QAT OK ?/? *** ?????; R; ; ; ; str
    0; audiotrack; ; #AUD; #QTK; @UAT ?{str} **|@QTK OK */?; RW; ; ; ; num

Der Eintrag für Audiotype im Beispiel bedeutet, dass die erwartete Antwort aus folgenden Teilen besteht:
"@QAT OK " zu Beginn, gefolgt von einem beliebigen Zeichen, einem "/" und einem weiteren beliebigen Zeichen. Anschließend folgt der relevante Teil der Antwort in der Länge von genau drei Zeichen. Danach kommt ein Leerzeichen und eine beliebige Zeichnfolge mit exakt fünf Stellen.

Der Beispieleintrag für Audiotrack bedeutet, dass eine dieser beiden Antworten gültig ist:
"@UAT " wird von irgendeinem Wort oder einer Ziffernfolge unbestimmter Länge mit jeweils einem Leerzeichen davor und danach gefolgt. Der relevante Teil der Antwort hat exakt zwei Zeichen.
Auf "@QTK OK " folgt die erwartete Antwort als ein einzelnes Zeichen, danach kommt noch ein "/" und ein beliebiges Zeichen. Der Teil am Ende ist insofern wichtig, als dass die Gesamtlänge der Antwort auch zur Kontrolle herangezogen wird.

Dieses Feature ist noch unter Bearbeitung. Ideen und Erfahrungen bitte im KNX Forum diskutieren:
`Plugin AVDevice Support <https://knx-user-forum.de/forum/supportforen/smarthome-py/1097870-neues-plugin-av-device-f%C3%BCr-yamaha-pioneer-denon-etc>`_


Troubleshooting
===============

1.) smarthome Logfile beobachten. Sollte das Problem dort nicht auftauchen, kann das Verbose Level noch höher als DEBUG gestellt werden, nämlich auf 9 (VERBOSE1) oder 8 (VERBOSE2).

2.) Versichern, dass die Anzahl an Sternen im Textfile korrekt ist.

Beispiel 1: Ein Pioneer Receiver erwartet die Angabe der Lautstärke in Form von drei Ziffern. Ein Wert "90" wird dadurch in "090" umgewandelt.

Beispiel 2: Der Denon Receiver antwortet auf den Einschaltbefehl mit ON, OFF oder STANDBY. Jeder Buchstabe muss hier durch einen Stern ersetzt werden.

Beispiel 3: Strings unbestimmter Länge wie "CD", "GAME", etc. für die Quelle sollten als "*{str}" angegeben werden. Außerdem muss der responsetype richtig deklariert werden!

3.) Der Antworttyp im model.txt kann manuell gesetzt werden, falls eine automatische Eruierung nicht zum gewünschten Ergebnis führt. Der "Sleep Timer" bei Denon Geräten erlaubt Werte zwischen 1 und 120 und den Wert "OFF". Der Antworttyp muss hier auf "bool|num" gesetzt werden. Dadurch konvertiert das Plugin automatisch die Antwort "OFF" in 0 und umgekehrt.

4.) Das Web Interface gibt einen Überblick über die letzten Befehle, etc.
