.. index:: Plugins; Stateengine; Allgemein
.. index:: Allgemein

Allgemein
#########

.. important::

      Es ist nicht empfehlenswert das stateengine Plugin
      für sicherheitsrelevante Zustände, wie zum Beispiel das Hochfahren
      von Jalousien bei zu viel Wind, zu verwenden. Sicherheitsrelevante
      Funktionen müssen so einfach wie möglich aufgebaut sein. Es wird
      daher dringend dazu geraten, solche Funktionen unabhängig von
      smarthomeNG und dem stateengine Plugin zu realisieren. Für das
      Hochfahren von Jalousien bei Windalarm beispielsweise sollte die
      Sperrfunktionalität verwendet werden, über die alle aktuellen
      Jalousieaktoren verfügen!

.. rubric:: Funktionalität
   :name: funktionalitaet

Über zusätzliche Items in den items/\*.conf-Dateien können Objekte
definiert werden, die eine beliebige Anzahl benutzerdefinierter
Zustand haben. Jeder Zustand kann Sets von Einstiegs- und
Ausstiegsbedingungen haben, sowie diverse Aktionen auslösen, wenn
der Zustand aktiv wird. In regelmäßigen Intervallen werden die
Zustände für jedes Objekt geprüft.

-  Wenn die Ausstiegsbedingungen des aktuellen Zustands nicht
   erfüllt sind bleibt das Objekt im aktuellen Zustand.
-  Wenn der aktuelle Zustand verlassen werden kann werden alle
   Zustände in der Reihenfolge, in der sie in der
   Konfigurationsdatei definiert sind, abgeprüft.
-  Der erste Zustand bei dem eine Gruppe Einstiegsbedingungen
   vollständig erfüllt ist, wird zum aktuellen Zustand. Die
   Aktionen, die für diesen Zustand definiert sind, werden
   ausgeführt.
-  Wenn kein passender Zustand gefunden wird passiert nichts. Das
   Objekt verbleibt im vorherigen Zustand.

Die folgenden Bedingungen können Teil der Bedingungsgruppen sein:

-  Tageszeit (Minimum, Maximum, Wert)
-  Wochentag (Minimum, Maximum, Wert)
-  Azimut der Sonne (Minimum, Maximum, Wert)
-  Altitude der Sonne (Minimum, Maximum, Wert)
-  Alter des aktuellen Zustands (Minimum, Maximum, Wert)
-  Zufallszahl (Minimum, Maximum, Wert)
-  Vorheriger Zustand (Wert)
-  Trigger-Objekt, dass die Zustandsermittlung ausgelöst hat

Zusätzlich können beliebige Items als Bedingungen geprüft werden
(Minimum, Maximum oder Wert)

Der ursprüngliche Zweck dieses Plugins war es, Jalousien zu
steuern. Mit den steigenden Anforderungen hat es sich jedoch zu
einem flexiblen Zustandsautomaten entwickelt, mit dem nahezu alles
gesteuert werden kann. Im Prinzip ist es ein `endlicher
Automat <https://de.wikipedia.org/wiki/Endlicher_Automat>`_.
