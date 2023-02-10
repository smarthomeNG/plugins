.. index:: Plugins; enocean
.. index:: enocean

=======
enocean
=======

.. image:: webif/static/img/plugin_logo.png
   :alt: plugin logo
   :width: 300px
   :height: 300px
   :scale: 50 %
   :align: left


Allgemein
=========

Enocean plugin zur Integration von Enocean Funksensoren und -aktoren, z.B. von Eltako.

Anforderungen
=============
Es wird ein Hardware Radio Transceiver Modul benötigt, z.B.:

 * USB 300
 * Fam4Pi
 * EnOcean PI 868 Funk Modul


.. important::

   Der user `samrthome`, unter dem smarthomeNG ausgeführt wird, muss die nötigen Zugriffsrechte 
   auf die Linux Gruppe `dialout` besitzen, damit die Hardware über Linux devices angesprochen und konfiguriert werden kann. 

Hierzu folgendes in der Linux Konsole ausführen:

.. code-block:: bash
    sudo gpasswd --add smarthome dialout


Konfiguration
=============

Die Informationen zur Konfiguration des Plugins sind unter :doc:`/plugins_doc/config/enocean` beschrieben.

plugin.yaml
-----------

*serialport*

Hier wird der `serialport` zum Enocean Hardwareadapter angegeben werden.
Unter Linux wird empfohlen, das entsprechende Linux Uart device über eine Udev-Regel auf einen Link zu mappen und diesen Link dann als `serialport` anzugeben.

*tx_id*
Die tx_id ist die Transmitter ID der Enocean Hardware und als achtstelliger Hexadezimalwert definiert. Die Angabe ist erstmal optional und muss nur zwingend angegeben werden,
falls Enocean Aktoren geschaltet werden sollen, d.h. der Hardware Kontroller auch Senebefehle absetzen muss.
 
Werden mehrere Aktuatoren betrieben, sollte die Base-ID (**not Unique-ID or Chip-ID**) der Enocean Hardware als Transmitter ID angegeben werden. 
Weitere Information zum Unterschied zwischen Base-ID und Chip-ID finden sich unter:
``https://www.enocean.com/en/knowledge-base-doku/enoceansystemspecification%3Aissue%3Awhat_is_a_base_id/``

Über die Angabe der Base-ID können für die Kommunikation mit den Aktuatoren 128 verschiedene Sende-IDs im Wertebereich von (Base-ID und Base-ID + 127) vergeben werden.

*Wie bekommt man die Base-ID des Enocean Adapters?*
Es gibt zwei verschiedene Wege, um die Base ID der Enocean Hardware auszulesen:

 a) Über das Enocean Plugin Webinterface
 b) Über die smarthomeNG Logdateien, die durch das Enocean plugin erzeugt werden.

Zu a) 
1. Konfiguriere das Enocean plugin in der plugin.yaml mit leerer tx_id (oder tx_id = 0).
2. Starte SmarthomeNG neu.
3. Öffne das Enocean webinterface des Plugins unter: http://localip:8383/enocean/
4. Ablesen der Transceiver's BaseID, welches auf der oberen recten Seite angezeigt wird. 
5. Übernahme der im Webinterface angezeigten Base-ID in die plugin.yaml als Parameter `tx_id`.

Zu b)
1. Konfiguriere das Enocean plugin in der plugin.yaml mit leerer tx_id (oder tx_id = 0).
2. Konfiguriere das Loglevel INFO in logger.yaml für das Enocean Plugin. Alternativ über das Admin Interface unter Logger
3. Starte SmarthomeNG neu.
4. Nach dem Neustart das Logfile öffnen und nach dem Eintrag ``enocean: Base ID = 0xYYYYZZZZ`` suchen.
6. Übernahme dieser im Log angezeigten Base-ID in die plugin.yaml als Parameter `tx_id`.

Web Interface
=============

Das enocean Plugin verfügt über ein Webinterface.


Aufruf des Webinterfaces
------------------------

Das Plugin kann aus dem Admin Interface aufgerufen werden. Dazu auf der Seite Plugins in der entsprechenden
Zeile das Icon in der Spalte **Web Interface** anklicken.

Außerdem kann das Webinterface direkt über ``http://smarthome.local:8383/enocean`` aufgerufen werden.


Beispiele
=========

Beispiele für eine Item.yaml mit verschiedenen Enocean Sensoren und Aktoren:

.. code-block:: yaml

  EnOcean_Item:
    Outside_Temperature:
        type: num
        enocean_rx_id: 0180924D
        enocean_rx_eep: A5_02_05
        enocean_rx_key: TMP

    Door:
        enocean_rx_id: 01234567
        enocean_rx_eep: D5_00_01
        status:
            type: bool
            enocean_rx_key: STATUS

    FT55switch:
        enocean_rx_id: 012345AA
        enocean_rx_eep: F6_02_03
            up:
                type: bool
                enocean_rx_key: BO
            down:
                type: bool
                enocean_rx_key: BI

    Brightness_Sensor:
        name: brightness_sensor_east
        remark: Eltako FAH60
        type: num
        enocean_rx_id: 01A51DE6
        enocean_rx_eep: A5_06_01
        enocean_rx_key: BRI
        visu_acl: rw
        sqlite: 'yes'

    dimmer1:
        remark: Eltako FDG14 - Dimmer
        enocean_rx_id: 00112233
        enocean_rx_eep: A5_11_04
        light:
        type: bool
        enocean_rx_key: STAT
        enocean_tx_eep: A5_38_08_02
        enocean_tx_id_offset: 1
        level:
            type: num
            enocean_rx_key: D
            enocean_tx_eep: A5_38_08_03
            enocean_tx_id_offset: 1
            ref_level: 80
            dim_speed: 100
            block_dim_value: 'False'

    handle:
        enocean_rx_id: 01234567
        enocean_rx_eep: F6_10_00
        status:
            type: num
            enocean_rx_key: STATUS

    actor1:
        enocean_rx_id: FFAABBCC
        enocean_rx_eep: A5_12_01
        power:
            type: num
            enocean_rx_key: VALUE

    actor1B:
        remark: Eltako FSR61, FSR61NP, FSR61G, FSR61LN, FLC61NP - Switch for Ligths
        enocean_rx_id: 1A794D3
        enocean_rx_eep: F6_02_03
        light:
            type: bool
            enocean_tx_eep: A5_38_08_01
            enocean_tx_id_offset: 1
            enocean_rx_key: B
            block_switch: 'False'
            cache: 'True'
            enforce_updates: 'True'
            visu_acl: rw

    actor_D2:
        remark: Actor with VLD Command
        enocean_rx_id: FFDB7381
        enocean_rx_eep: D2_01_07
        move:
            type: bool
            enocean_rx_key: STAT
            enocean_tx_eep: D2_01_07
            enocean_tx_id_offset: 1
            # pulsewith-attribute removed use autotimer functionality instead
            autotimer: 1 = 0  
            
    actorD2_01_12:
        enocean_rx_id: 050A2FF4
        enocean_rx_eep: D2_01_12
        switch:
            cache: 'on'
            type: bool
            enocean_rx_key: STAT_A
            enocean_channel: A
            enocean_tx_eep: D2_01_12
            enocean_tx_id_offset: 2

    awning:
        name: Eltako FSB14, FSB61, FSB71
        remark: actor for Shutter
        type: str
        enocean_rx_id: 1A869C3
        enocean_rx_eep: F6_0G_03
        enocean_rx_key: STATUS
        move:
            type: num
            enocean_tx_eep: A5_3F_7F
            enocean_tx_id_offset: 0
            enocean_rx_key: B
            enocean_rtime: 60
            block_switch: 'False'
            enforce_updates: 'True'
            cache: 'True'
            visu_acl: rw

    rocker:
        enocean_rx_id: 0029894A
        enocean_rx_eep: F6_02_01
        short_800ms_directly_to_knx:
            type: bool
            enocean_rx_key: AI
            enocean_rocker_action: **toggle**
            enocean_rocker_sequence: released **within** 0.8
            knx_dpt: 1
            knx_send: 3/0/60

        long_800ms_directly_to_knx:
            type: bool
            enocean_rx_key: AI
            enocean_rocker_action: toggle
            enocean_rocker_sequence: released **after** 0.8
            knx_dpt: 1
            knx_send: 3/0/61

        rocker_double_800ms_to_knx_send_1:
            type: bool
            enforce_updates: true
            enocean_rx_key: AI
            enocean_rocker_action: **set**
            enocean_rocker_sequence: **released within 0.4, pressed within 0.4**
            knx_dpt: 1
            knx_send: 3/0/62

    brightness_sensor:
        enocean_rx_id: 01234567
        enocean_rx_eep: A5_08_01
        lux:
            type: num
            enocean_rx_key: BRI

        movement:
            type: bool
            enocean_rx_key: MOV

    occupancy_sensor:
        enocean_rx_id: 01234567
        enocean_rx_eep: A5_07_03
        lux:
            type: num
            enocean_rx_key: ILL

        movement:
            type: bool
            enocean_rx_key: PIR

        voltage:
            type: bool
            enocean_rx_key: SVC

    temperature_sensor:
        enocean_rx_id: 01234567
        enocean_rx_eep: A5_04_02
        temperature:
            type: num
            enocean_rx_key: TMP

        humidity:
            type: num
            enocean_rx_key: HUM

        power_status:
            type: num
            enocean_rx_key: ENG

    sunblind:
        name: Eltako FSB14, FSB61, FSB71
        remark: actor for Shutter
        type: str
        enocean_rx_id: 1A869C3
        enocean_rx_eep: F6_0G_03
        enocean_rx_key: STATUS
        # runtime Range [0 - 255] s
        enocean_rtime: 80
        Tgt_Position:
            name: Eltako FSB14, FSB61, FSB71
            remark: Pos. 0...255
            type: num
            enocean_rx_id: ..:.
            enocean_rx_eep: ..:.
            enforce_updates: 'True'
            cache: 'True'
            visu_acl: rw
        Act_Position:
            name: Eltako FSB14, FSB61, FSB71
            remark: Ist-Pos. 0...255 berechnet aus (letzer Pos. + Fahrzeit * 255/rtime)
            type: num
            enocean_rx_id: ..:.
            enocean_rx_eep: ..:.
            enocean_rx_key: POSITION
            enforce_updates: 'True'
            cache: 'True'
            visu_acl: rw
            eval: min(max(value, 0), 255)
            on_update:
                - EnOcean_Item.sunblind = 'stopped'
        Run:
            name: Eltako FSB14, FSB61, FSB71
            remark: Ansteuerbefehl 0x00, 0x01, 0x02
            type: num
            enocean_rx_id: ..:.
            enocean_rx_eep: ..:.
            enocean_tx_eep: A5_3F_7F
            enocean_tx_id_offset: 0
            enocean_rx_key: B
            enocean_rtime: ..:.
            # block actuator
            block_switch: 'True'
            enforce_updates: 'True'
            cache: 'True'
            visu_acl: rw
            struct: uzsu.child
        Movement:
            name: Eltako FSB14, FSB61, FSB71
            remark: Wenn Rolladen gestoppt wurde steht hier die gefahrene Zeit in s und die Richtung
            type: num
            enocean_rx_id: ..:.
            enocean_rx_eep: A5_0G_03
            enocean_rx_key: MOVE
            cache: 'False'
            enforce_updates: 'True'
            eval: value * 255/int(sh.EnOcean_Item.sunblind.property.enocean_rtime)
            on_update:
                - EnOcean_Item.sunblind = 'stopped'
                - EnOcean_Item.sunblind.Act_Position = EnOcean_Item.sunblind.Act_Position() + value

    RGBdimmer:
        type: num
        remark: Eltako FRGBW71L - RGB Dimmer
        enocean_rx_id: 1A869C3
        enocean_rx_eep: A5_3F_7F
        enocean_rx_key: DI_0
        red:
            type: num
            enocean_tx_eep: 07_3F_7F
            enocean_tx_id_offset: 1
            enocean_rx_key: DI_0
            ref_level: 80
            dim_speed: 100
            color: red
        green:
            type: num
            enocean_tx_eep: 07_3F_7F
            enocean_tx_id_offset: 1
            enocean_rx_key: DI_1
            ref_level: 80
            dim_speed: 100
            color: green
        blue:
            type: num
            enocean_tx_eep: 07_3F_7F
            enocean_tx_id_offset: 1
            enocean_rx_key: DI_2
            ref_level: 80
            dim_speed: 100
            color: blue
        white:
            type: num
            enocean_tx_eep: 07_3F_7F
            enocean_tx_id_offset: 1
            enocean_rx_key: DI_3
            ref_level: 80
            dim_speed: 100
            color: white 
    water_sensor:
        enocean_rx_id: 00000000
        enocean_rx_eep: A5_30_03

        alarm:
            type: bool
            enocean_rx_key: ALARM
            visu_acl: ro

        temperature:
            type: num
            enocean_rx_key: TEMP
            visu_acl: ro
  



