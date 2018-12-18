# Alexa4PayloadV3






## Table of Content

1. [Generell](#generell)
2. [Icon / Display Categories](#icons)
3. [Entwicklung / Einbau von neuen Skills](#entwicklung)
4. [Alexa-ThermostatController](#thermostatcontroller) + [Thermosensor](#thermostatsensor)
5. [Alexa-PowerController](#powercontroller)
6. [Alexa-BrightnessController](#brightnesscontroller)
7. [Alexa-PowerLevelController](#powerlevelcontroller)
8. [Alexa-PercentageController](#percentagecontroller)
9. [Alexa-LockController](#lockcontroller)
10. [Alexa-CameraStreamController](#camerastreamcontroller)
11. [Alexa-SceneController](#scenecontroller)



# --------------------------------------

## Generell <a name="generell"/></a>

Die Daten des Plugin müssen in den Ordner /usr/local/smarthome/plugins/alexa4p3/ (wie gewohnt)
Die Rechte entsprechend setzen.

Das Plugin sollte ohne Änderungen die ursprünglichen Funktionen von Payload V2 
weiterverarbeiten können.

Um die neuen Payload-Features nutzen zu können muss lediglich die Skill-Version in der Amazon Hölle auf PayLoad Version 3 umgestellt werden. Alles andere kann unverändert weiterverwendet werden.

Das Plugin muss in der plugin.yaml eingefügt werden :

<pre><code>
Alexa4P3:
    class_name: Alexa4P3
    class_path: plugins.alexa4p3
    service_port: 9000
</code></pre>

Das ursprünglich Plugin kann deaktiviertwerden :

<pre><code>
#alexa:
#    class_name: Alexa
#    class_path: plugins.alexa
#    service_port: 9000
</code></pre>

Idealerweise kopiert man sich seine ganzen conf/yaml Files aus dem Items-Verzeichnis.
und ersetzt dann die "alten" Actions durch die "Neuen". Nachdem der Skill auf Payload V3 umgestellt wurde
muss ein Discover durchgeführt werden. Im besten Fall funktioniert dann alles wie gewohnt.

In den Items sind die "neuen" V3 Actions zu definieren :

Zum Beispiel :

PayloadV2 : turnon
PayloadV3 : TurnOn

Die Actions unterscheiden sich zwischen Payload V2 und V3 oft nur durch Gross/Klein-Schreibung

## Icons / Catagories <a name="icons"/></a>
Optional kann im Item angegeben werden welches Icon in der Alexa-App verwendet werden soll :

        alexa_icon = "LIGHT"

<table>
  <thead>
    <tr>
      <th>Value</th>
      <th>Description</th>
      <th>Notes</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>ACTIVITY_TRIGGER</td>
      <td>Describes a combination of devices set to a specific state, when the state change must occur in a specific order. For example, a "watch Netflix" scene might require the: 1. TV to be powered on &amp; 2. Input set to HDMI1.</td>
      <td>Applies to Scenes</td>
    </tr>
    <tr>
      <td>CAMERA</td>
      <td>Indicates media devices with video or photo capabilities.</td>
      <td>&nbsp;</td>
    </tr>
    <tr>
      <td>CONTACT_SENSOR</td>
      <td>Indicates an endpoint that detects and reports changes in contact between two surfaces.</td>
      <td>&nbsp;</td>
    </tr>
    <tr>
      <td>DOOR</td>
      <td>Indicates a door.</td>
      <td>&nbsp;</td>
    </tr>
    <tr>
      <td>DOORBELL</td>
      <td>Indicates a doorbell.</td>
      <td>&nbsp;</td>
    </tr>
    <tr>
      <td>LIGHT</td>
      <td>Indicates light sources or fixtures.</td>
      <td>&nbsp;</td>
    </tr>
    <tr>
      <td>MICROWAVE</td>
      <td>Indicates a microwave oven endpoint.</td>
      <td>&nbsp;</td>
    </tr>
    <tr>
      <td>MOTION_SENSOR</td>
      <td>Indicates an endpoint that detects and reports movement in an area.</td>
      <td>&nbsp;</td>
    </tr>
    <tr>
      <td>OTHER</td>
      <td>An endpoint that cannot be described in one of the other categories.</td>
      <td>&nbsp;</td>
    </tr>
    <tr>
      <td>SCENE_TRIGGER</td>
      <td>Describes a combination of devices set to a specific state, when the order of the state change is not important. For example a bedtime scene might include turning off lights and lowering the thermostat, but the order is unimportant.</td>
      <td>Applies to Scenes</td>
    </tr>
    <tr>
      <td>SMARTLOCK</td>
      <td>Indicates an endpoint that locks.</td>
      <td>&nbsp;</td>
    </tr>
    <tr>
      <td>SMARTPLUG</td>
      <td>Indicates modules that are plugged into an existing electrical outlet.</td>
      <td>Can control a variety of devices.</td>
    </tr>
    <tr>
      <td>SPEAKER</td>
      <td>Indicates the endpoint is a speaker or speaker system.</td>
      <td>&nbsp;</td>
    </tr>
    <tr>
      <td>SWITCH</td>
      <td>Indicates in-wall switches wired to the electrical system.</td>
      <td>Can control a variety of devices.</td>
    </tr>
    <tr>
      <td>TEMPERATURE_SENSOR</td>
      <td>Indicates endpoints that report the temperature only.</td>
      <td>The endpoint's temperature data is not shown in the Alexa app.</td>
    </tr>
    <tr>
      <td>THERMOSTAT</td>
      <td>Indicates endpoints that control temperature, stand-alone air conditioners, or heaters with direct temperature control.</td>
      <td>&nbsp;</td>
    </tr>
    <tr>
      <td>TV</td>
      <td>Indicates the endpoint is a television.</td>
      <td>&nbsp;</td>
    </tr>
  </tbody>
</table>
default = "Switch" (vergleiche : https://developer.amazon.com/docs/device-apis/alexa-discovery.html#display-categories )

Optional kann im Item angegeben werden ob es durch Amazon abgefragt werden kann :
<pre><code>
	alexa_retrievable = true
</code></pre>

default = false
**==!! Achtung das sorgt für Traffic auf der Lambda bei Benutzung der Alexa-App !!==**


Die sonstigen Parameter aus dem ursprüngliche Alexa-Plugin bleiben erhalten und werden weiterhin genutzt.
(alexa_name / alexa_device / alexa_description / alexa_actions /alexa_item_range)

Beispiel für Item im .conf-Format:

<pre><code>
[OG]
    [[Flur]]
        name = Flur_Obeschoss
        [[[Spots]]]
        alexa_name = "Licht Flur OG"
        alexa_device = Licht_Flur_OG
	alexa_actions = "TurnOn TurnOff"
        alexa_icon = "LIGHT"
        type = bool
        visu_acl = rw
        knx_dpt = 1
        knx_listen = 1/1/107
        knx_send = 1/1/107
        enforce_updates = true
            [[[[dimmen]]]]
                type = num
                alexa_device = Licht_Flur_OG
                alexa_actions = "AdjustBrightness SetBrightness"
                alexa_retrievable= True
                alexa_item_range = 0-255
                visu_acl = rw
                knx_dpt = 5
                knx_listen = 1/4/100
                knx_send = 1/3/100
                knx_init = 1/4/100
                enforce_updates = true
        [[[Treppe]]]
        type = bool
        visu_acl = rw
        knx_dpt = 1
        knx_listen = 1/1/133
        knx_send = 1/1/133
        enforce_updates = true

</code></pre>

im .yaml-Format :

<pre><code>
%YAML 1.1
---

OG:

    Flur:
        name: Flur_Obeschoss
        Spots:
            alexa_name: Licht Flur OG
            alexa_device: Licht_Flur_OG
            alexa_actions: TurnOn TurnOff
            alexa_icon: LIGHT
            type: bool
            visu_acl: rw
            knx_dpt: 1
            knx_listen: 1/1/107
            knx_send: 1/1/107
            enforce_updates: 'true'
            dimmen:
                type: num
                alexa_device: Licht_Flur_OG
                alexa_actions: AdjustBrightness SetBrightness
                alexa_retrievable: 'True'
                alexa_item_range: 0-255
                visu_acl: rw
                knx_dpt: 5
                knx_listen: 1/4/100
                knx_send: 1/3/100
                knx_init: 1/4/100
                enforce_updates: 'true'
        Treppe:
            type: bool
            visu_acl: rw
            knx_dpt: 1
            knx_listen: 1/1/133
            knx_send: 1/1/133
            enforce_updates: 'true'
</code></pre>

## Entwicklung / Einbau von neuen Fähigkeiten <a name="entwicklung"/></a>
Um weitere Actions hinzuzufügen muss die Datei p3_actions.py mit den entsprechenden Actions ergänzt werden.
(wie ursprünglich als selbstregistrierende Funktion)

<pre><code>

@alexa('action_name', 'directive_type', 'response_type','namespace',[]) // in der Datei p3_actions.py
@alexa('TurnOn', 'TurnOn', 'powerState','Alexa.PowerController',[]) // in der Datei p3_actions.py

</code></pre>

Hierbei ist zu beachten, das für die jeweilige Action die folgenden Paramter übergeben werden :

action_name     = neuer Action-Name z.B.: TurnOn (gleich geschrieben wie in der Amazon-Beschreibung - auch Gross/Klein)

directive_type  = gleich wie action_name (nur notwendig wegen Kompatibilität V2 und V3)

response_type   = Property des Alexa Interfaces
siehe Amazon z.B. : https://developer.amazon.com/docs/device-apis/alexa-brightnesscontroller.html#properties

namespace       = NameSpace des Alexa Interfaces
siehe Amazon z.B.: https://developer.amazon.com/docs/device-apis/list-of-interfaces.html

[]              = Array für Abhängigkeiten von anderen Capabilties (z.B. beim Theromcontroller ThermostatMode und TargetTemperatur)

In der "service.py" muss für den ReportState der Rückgabewert für die neue Action hinzugefügt werden.
(siehe Quellcode)

## Alexa-ThermostatController + Thermosensor <a name="thermostatcontroller"/></a>

Es kann nun via Alexa die Solltemperatur verändert werden und der Modus des Thermostaten kann umgestellt werden.
Die Konfiguration der YAML-Datei sieht wie folgt aus

Es müssen beim Thermostaten in YAML die Einträge für :
alexa_thermo_config, alexa_icon, alexa_actions vorgenommen werden.

alexa_thermo_config = "0:AUTO 1:HEAT 2:COOL 3:ECO 4:ECO"
Hierbei stehen die Werte für für die KNX-Werte von DPT 20

<pre><code>
$00 Auto
$01 Comfort
$02 Standby
$03 Economy
$04 Building Protection
</code></pre>

Die Modi AUTO / HEAT / COOL / ECO / OFF entsprechen den Alexa-Befehlen aus dem Theromstatconroller
siehe Amazon : https://developer.amazon.com/docs/device-apis/alexa-property-schemas.html#thermostatmode

<pre><code>
alexa_icon = "THERMOSTAT" = Thermostatcontroller

alexa_icon = "TEMPERATURE_SENSOR" = Temperatursensor
</code></pre>

### Thermostatsensor<a name="thermostatsensor"/></a>

Der Temperartursensor wird beim Item der Ist-Temperatur hinterlegt.
Der Thermostatconroller wird beim Thermostat-Item hinterlegt. An Amazon werden die Icons als Array übertragen.
Die Abfrage der Ist-Temperatur muss mit der Action  "ReportTemperature" beim Item der Ist-Temperatur hinterlegt werden.

<pre><code>
alexa_actions : "ReportTemperature"
</code></pre>

Alexa wie ist die Temperatur in der Küche ?

### Verändern der Temperatur (SetTargetTemperature AdjustTargetTemperature)

<pre><code>
alexa_actions = "SetTargetTemperature AdjustTargetTemperature"
</code></pre>

Hiermit werden die Solltemperatur auf einen Wert gesetzt oder die Temperatur erhöht.
Diese Actions müssen beim Item des Soll-Wertes des Thermostaten eingetragen werden

Alexa erhöhe die Temperatur in der Küche um zwei Grad

Alexa stelle die Temperatur in der Küche auf zweiundzwanzig Grad

### Thermostatmode<a name="Thermostatmode"/></a>

alexa_actions = "SetThermostatMode"

Hier wird das Item des Modus angesteuert. Diese Action muss beim Item des Thermostat-Modes eingetragen werden.
Falls keine Modes angegeben wurden wird "0:AUTO" als default gesetzt

Alexa stelle den Thermostaten Küche auf Heizen


<pre><code>
%YAML 1.1
---
EG:
    name: EG
    sv_page: cat_seperator
    Kueche:
        temperature:
            name: Raumtemperatur
            alexa_description : "Küche Thermostat"
            alexa_name : "Küche Thermostat"
            alexa_device : thermo_Kueche 
            alexa_thermo_config : "0:AUTO 1:HEAT 2:OFF 3:ECO 4:ECO"
            alexa_icon : "THERMOSTAT"
            actual:
                type: num
                sqlite: 'yes'
                visu: 'yes'
                knx_dpt: 9
                initial_value: 21.8
                alexa_device : thermo_Kueche 
                alexa_retrievable : True
                alexa_actions : "ReportTemperature"
                alexa_icon : "TEMPERATURE_SENSOR"
            SollBasis:
                type: num
                visu_acl: rw
                knx_dpt: 9
                initial_value: 21.0
                alexa_device : thermo_Kueche 
                alexa_actions : "SetTargetTemperature AdjustTargetTemperature"
            Soll:
                type: num
                sqlite: 'yes'
                visu: 'yes'
                visu_acl: rw
                knx_dpt: 9
                initial_value: 21.0
                alexa_device : thermo_Kueche 
            mode:
                type: num
                visu_acl: rw
                knx_dpt: 20
                initial_value: 1.0
                alexa_device : thermo_Kueche 
                alexa_actions : "SetThermostatMode"
            state:
                type: bool
                visu_acl: r
                sqlite: 'yes'
                visu: 'yes'
                knx_dpt: 1
                cache: true
                alexa_device : thermo_Kueche 
</code></pre>

Beispiel für einen MDT-Glastron, der Modus wird auf Objekt 12 in der ETS-Parametrierung gesendet (Hierzu eine entsprechende 
Gruppenadresse anlegen)

<pre><code>
 temperature:
            name: Raumtemperatur
            alexa_description : "Küche Thermostat"
            alexa_name : "Küche Thermostat"
            alexa_device : thermo_Kueche 
            alexa_thermo_config : "0:AUTO 1:HEAT 2:OFF 3:ECO 4:ECO"
            alexa_icon : "THERMOSTAT"
        plan:
            type: num
            visu_acl: rw
            database@mysqldb: init
            knx_dpt: 9
            knx_send: 2/1/2
            knx_listen: 2/1/2
            knx_cache: 2/1/2
            alexa_device : thermo_Kueche 
            alexa_actions : "SetTargetTemperature AdjustTargetTemperature"
        state:
            type: num
            visu_acl: r
            database@mysqldb: init
            knx_dpt: 9
            knx_listen: 2/1/1
            knx_cache: 2/1/1
            alexa_device : thermo_Kueche 
            alexa_retrievable : True
            alexa_actions : "ReportTemperature"
            alexa_icon : "TEMPERATURE_SENSOR"
        mode:
            type: num
            visu_acl: rw
            knx_dpt: 20
            initial_value: 1.0
            alexa_device : thermo_Kueche 
            alexa_actions : "SetThermostatMode"

        humidity:
            type: num
            visu_acl: r
            database@mysqldb: init
            knx_dpt: 9
            knx_listen: 2/1/5
            knx_cache: 2/1/5

        actor_state:
            type: num
            visu_acl: r
            database@mysqldb: init
            knx_dpt: '5.001'
            knx_listen: 2/1/3
            knx_cache: 2/1/3

</code></pre>

## Alexa-PowerController<a name="powercontroller"/></a>

Alexa schalte das Licht im Flur OG ein

Mit dem PowerController können beliebige Geräte ein und ausgeschalten werden.
Folgende Paramter sind anzugeben :

<pre><code>
	    alexa_actions = "TurnOn TurnOff"
</code></pre>

Beispiel

<pre><code>
        [[[Licht]]]
        type = bool
        alexa_name = "Licht Büro"
        alexa_description = "Licht Büro"
	    alexa_actions = "TurnOn TurnOff"
        alexa_retrievable = true
        alexa_icon = "LIGHT"
        visu_acl = rw
        knx_dpt = 1
        knx_listen = 1/1/105
        knx_send = 1/1/105
        enforce_updates = true
</code></pre>

## Alexa-BrightnessController<a name="brightnesscontroller"/></a>
Alexa stelle das Licht am Esstisch auf fünfzig Prozent
Alexa dimme das Licht am Esstisch um zehn Prozent
Folgende Parameter sind anzugeben :

<pre><code>
	    alexa_actions = "AdjustBrightness SetBrightness"
        alexa_item_range = 0-255
</code></pre>

Es kann der BrightnessController mit dem PowerController kombiniert werden

Beispiel :
<pre><code>
    [[[Licht_Esstisch]]]
    type = bool
    alexa_name = "Licht Esstisch"
    alexa_actions = "TurnOn TurnOff"
    alexa_device = licht_esstisch
    alexa_description = "Licht Esstisch"
    alexa_icon = "SWITCH"
    alexa_retrievable= True
    visu_acl = rw
	knx_dpt = 1
	knx_listen = 1/1/9
	knx_send = 1/1/9
    enforce_updates = true
        [[[[dimmen]]]]
        type = num
        alexa_device = licht_esstisch
        alexa_actions = "AdjustBrightness SetBrightness"
        alexa_retrievable= True
        alexa_item_range = 0-255
        visu_acl = rw
        knx_dpt = 5
        knx_listen = 1/4/9
        knx_send = 1/3/9
        knx_init = 1/4/9
        enforce_updates = true
</code></pre>

## Alexa-PowerLevelController<a name="powerlevelcontroller"/></a>
tbd
## Alexa-PercentageController<a name="percentagecontroller"/></a>
tbd
## Alexa-LockController<a name="lockcontroller"/></a>
tbd
## Alexa-CameraStreamContoller<a name="camerastreamcontroller"/></a>
tbd
## Alexa-SceneController<a name="scenecontroller"/></a>

Alexa aktiviere Szene kommen

Mit dem Scene-Controller können Szenen aufgerufen werden.
Folgende Parameter sind anzugeben:
<pre><code>
alexa-actions = "Activate"
alexa_item_turn_on = 3
alexa_icon = "SCENE_TRIGGER"
</code></pre>

Das "alexa_item_turn_on" ist die Nummer der Szene die aufgerufen werden soll.


Beispiel Konfiguration :
<pre><code>
        scene:
            type: num
            name: scene_kommen
            alexa_description : "Szene Kommen"
            alexa_name : "Szene Kommen"
            alexa_device : Szene_Kommen
            alexa_icon : "SCENE_TRIGGER"
            alexa_item_turn_on : 3
            alexa_actions : "Activate"
            alexa_retrievable : false
</code></pre>
