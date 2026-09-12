.. index:: Plugins; smarttv
.. index:: smarttv

=======
smarttv
=======

Dieses Plugin erlaubt es, SmartTV-Geräte wie z.B. Samsung zu steuern. Es hat zwei Implementierungen
(für das alte und das neue API der TVs). Für das neue API muss auf dem TV der Zugriff akzeptiert
werden, indem ein Button auf dem TV gedrückt wird, wenn der erste Request eingeht.

Voraussetzungen
================

Für die Ansteuerung von Geräten der Samsung M-Serie (**tv_version**: samsung_m_series) wird das
Python-Paket ``websocket-client`` (ab Version 0.44.0) benötigt. Es wird automatisch über
``requirements.txt`` installiert. Für die klassische Implementierung (**tv_version**: classic) wird
es nicht benötigt.

Konfiguration
=============

Die Informationen zur Konfiguration des Plugins sind unter :doc:`/plugins_doc/config/smarttv` beschrieben.

.. important::

   Der Standard-Port (**port**: 55000) gilt unabhängig vom Wert von **tv_version**. Geräte der
   Samsung M-Serie (**tv_version**: samsung_m_series) werden über eine WebSocket-Verbindung
   angesprochen, die den Port 8001 verwendet. **port** muss dafür explizit auf 8001 gesetzt werden.

Mehrere Instanzen
-----------------

Für die Steuerung mehrerer SmartTV-Geräte unterstützt das Plugin mehrere Instanzen. Jede Instanz
erhält einen eigenen Abschnitt in ``etc/plugin.yaml`` mit eigenem **host**::

    smarttv1:
        plugin_name: smarttv
        instance: wohnzimmer
        host: 192.168.0.45

    smarttv2:
        plugin_name: smarttv
        instance: kueche
        host: 192.168.0.46

In den Items wird die gewünschte Instanz mit ``@<Instanzname>`` am Attribut **smarttv** angegeben::

    tv_wohnzimmer:
        type: str
        smarttv@wohnzimmer: 'true'
        enforce_updates: 'true'

    tv_kueche:
        type: str
        smarttv@kueche: 'true'
        enforce_updates: 'true'

Beispiele
=========

Das Item-Attribut **smarttv** kann auf zwei Arten verwendet werden:

- Auf einem Item vom Typ **str** mit dem Wert ``true``: Jeder String, der in dieses Item geschrieben
  wird, wird an das SmartTV-Gerät gesendet.
- Auf einem Item vom Typ **bool** mit einem oder mehreren Tastenwerten (durch Komma getrennt): Beim
  Setzen des Items auf **true** werden die angegebenen Tasten an das Gerät gesendet. Für reine
  Befehls-Items empfiehlt sich zusätzlich **enforce_updates**.

::

    tv:
        type: str
        smarttv: 'true'
        enforce_updates: 'true'

        mute:
            type: bool
            smarttv: KEY_MUTE
            enforce_updates: 'true'

        KIKA:
            name: KIKATV
            type: bool
            visu_acl: rw
            smarttv:
              - KEY_1
              - KEY_0
              - KEY_6
              - KEY_ENTER
            enforce_updates: 'true'

Verfügbare Tasten (KEY_-Werte)
===============================

Je nach Gerät werden nicht alle der folgenden Tastenwerte unterstützt::

    KEY_MENU, KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT, KEY_3, KEY_VOLUP, KEY_4
    KEY_5, KEY_6, KEY_VOLDOWN, KEY_7, KEY_8, KEY_9, KEY_MUTE, KEY_CHDOWN, KEY_0
    KEY_CHUP, KEY_PRECH, KEY_GREEN, KEY_YELLOW, KEY_CYAN, KEY_ADDDEL, KEY_SOURCE
    KEY_INFO, KEY_PIP_ONOFF, KEY_PIP_SWAP, KEY_PLUS100, KEY_CAPTION, KEY_PMODE
    KEY_TTX_MIX, KEY_TV, KEY_PICTURE_SIZE, KEY_AD, KEY_PIP_SIZE
    KEY_MAGIC_CHANNEL, KEY_PIP_SCAN, KEY_PIP_CHUP, KEY_PIP_CHDOWN
    KEY_DEVICE_CONNECT, KEY_HELP, KEY_ANTENA, KEY_CONVERGENCE, KEY_11, KEY_12
    KEY_AUTO_PROGRAM, KEY_FACTORY, KEY_3SPEED, KEY_RSURF, KEY_ASPECT
    KEY_TOPMENU, KEY_GAME, KEY_QUICK_REPLAY, KEY_STILL_PICTURE, KEY_DTV
    KEY_FAVCH, KEY_REWIND, KEY_STOP, KEY_PLAY, KEY_FF, KEY_REC, KEY_PAUSE
    KEY_TOOLS, KEY_INSTANT_REPLAY, KEY_LINK, KEY_FF_, KEY_GUIDE, KEY_REWIND_
    KEY_ANGLE, KEY_RESERVED1, KEY_ZOOM1, KEY_PROGRAM, KEY_BOOKMARK
    KEY_DISC_MENU, KEY_PRINT, KEY_RETURN, KEY_SUB_TITLE, KEY_CLEAR, KEY_VCHIP
    KEY_REPEAT, KEY_DOOR, KEY_OPEN, KEY_WHEEL_LEFT, KEY_POWER, KEY_SLEEP, KEY_2
    KEY_DMA, KEY_TURBO, KEY_1, KEY_FM_RADIO, KEY_DVR_MENU, KEY_MTS, KEY_PCMODE
    KEY_TTX_SUBFACE, KEY_CH_LIST, KEY_RED, KEY_DNIe, KEY_SRS
    KEY_CONVERT_AUDIO_MAINSUB, KEY_MDC, KEY_SEFFECT, KEY_DVR, KEY_DTV_SIGNAL
    KEY_LIVE, KEY_PERPECT_FOCUS, KEY_HOME, KEY_ESAVING, KEY_WHEEL_RIGHT
    KEY_CONTENTS, KEY_VCR_MODE, KEY_CATV_MODE, KEY_DSS_MODE, KEY_TV_MODE
    KEY_DVD_MODE, KEY_STB_MODE, KEY_CALLER_ID, KEY_SCALE, KEY_ZOOM_MOVE
    KEY_CLOCK_DISPLAY, KEY_AV1, KEY_SVIDEO1, KEY_COMPONENT1
    KEY_SETUP_CLOCK_TIMER, KEY_COMPONENT2, KEY_MAGIC_BRIGHT, KEY_DVI, KEY_HDMI
    KEY_W_LINK, KEY_DTV_LINK, KEY_APP_LIST, KEY_BACK_MHP, KEY_ALT_MHP, KEY_DNSe
    KEY_RSS, KEY_ENTERTAINMENT, KEY_ID_INPUT, KEY_ID_SETUP, KEY_ANYNET
    KEY_POWEROFF, KEY_POWERON, KEY_ANYVIEW, KEY_MS, KEY_MORE, KEY_PANNEL_POWER
    KEY_PANNEL_CHUP, KEY_PANNEL_CHDOWN, KEY_PANNEL_VOLUP, KEY_PANNEL_VOLDOW
    KEY_PANNEL_ENTER, KEY_PANNEL_MENU, KEY_PANNEL_SOURCE, KEY_AV2, KEY_AV3
    KEY_SVIDEO2, KEY_SVIDEO3, KEY_ZOOM2, KEY_PANORAMA, KEY_4_3, KEY_16_9
    KEY_DYNAMIC, KEY_STANDARD, KEY_MOVIE1, KEY_CUSTOM, KEY_AUTO_ARC_RESET
    KEY_AUTO_ARC_LNA_ON, KEY_AUTO_ARC_LNA_OFF, KEY_AUTO_ARC_ANYNET_MODE_OK
    KEY_AUTO_ARC_ANYNET_AUTO_START, KEY_AUTO_FORMAT, KEY_DNET, KEY_HDMI1
    KEY_AUTO_ARC_CAPTION_ON, KEY_AUTO_ARC_CAPTION_OFF, KEY_AUTO_ARC_PIP_DOUBLE
    KEY_AUTO_ARC_PIP_LARGE, KEY_AUTO_ARC_PIP_SMALL, KEY_AUTO_ARC_PIP_WIDE
    KEY_AUTO_ARC_PIP_LEFT_TOP, KEY_AUTO_ARC_PIP_RIGHT_TOP
    KEY_AUTO_ARC_PIP_LEFT_BOTTOM, KEY_AUTO_ARC_PIP_RIGHT_BOTTOM
    KEY_AUTO_ARC_PIP_CH_CHANGE, KEY_AUTO_ARC_AUTOCOLOR_SUCCESS
    KEY_AUTO_ARC_AUTOCOLOR_FAIL, KEY_AUTO_ARC_C_FORCE_AGING
    KEY_AUTO_ARC_USBJACK_INSPECT, KEY_AUTO_ARC_JACK_IDENT, KEY_NINE_SEPERATE
    KEY_ZOOM_IN, KEY_ZOOM_OUT, KEY_MIC, KEY_HDMI2, KEY_HDMI3
    KEY_AUTO_ARC_CAPTION_KOR, KEY_AUTO_ARC_CAPTION_ENG
    KEY_AUTO_ARC_PIP_SOURCE_CHANGE, KEY_HDMI4, KEY_AUTO_ARC_ANTENNA_AIR
    KEY_AUTO_ARC_ANTENNA_CABLE, KEY_AUTO_ARC_ANTENNA_SATELLITE, KEY_EXT1
    KEY_EXT2, KEY_EXT3, KEY_EXT4, KEY_EXT5, KEY_EXT6, KEY_EXT7, KEY_EXT8
    KEY_EXT9, KEY_EXT10, KEY_EXT11, KEY_EXT12, KEY_EXT13, KEY_EXT14, KEY_EXT15
    KEY_EXT16, KEY_EXT17, KEY_EXT18, KEY_EXT19, KEY_EXT20, KEY_EXT21, KEY_EXT22
    KEY_EXT23, KEY_EXT24, KEY_EXT25, KEY_EXT26, KEY_EXT27, KEY_EXT28, KEY_EXT29
    KEY_EXT30, KEY_EXT31, KEY_EXT32, KEY_EXT33, KEY_EXT34, KEY_EXT35, KEY_EXT36
    KEY_EXT37, KEY_EXT38, KEY_EXT39, KEY_EXT40, KEY_EXT41
