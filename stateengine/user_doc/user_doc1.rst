.. index:: Plugins; Stateengine; Allgemein
.. index:: Allgemein

Allgemein
#########

.. important::

      Es ist nicht empfehlenswert, das stateengine Plugin
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

Über zusätzliche Items in den items/\*.yaml Dateien können Objekt-Items
definiert werden, die eine beliebige Anzahl benutzerdefinierter
Zustände haben. Jeder Zustand kann Sets von Einstiegsbedingungen haben
und diverse Aktionen auslösen, wenn der Zustand aktiv wird.

In regelmäßigen Intervallen werden die Zustände für jedes Objekt der angegebenen
Reihe nach geprüft. Der erste Zustand, bei dem eine Gruppe Einstiegsbedingungen
vollständig erfüllt ist, wird zum aktuellen Zustand. Die
Aktionen, die für diesen Zustand definiert sind, werden ausgeführt.

Wenn kein passender Zustand gefunden wird, passiert nichts. Das Objekt verbleibt im vorherigen Zustand.
Dies kann in manchen Fällen Sinn machen, meist bietet es sich aber an,
einen Standardzustand ganz am Ende festzulegen, der keine Eingangsbedingungen hat.

Die folgenden Bedingungen können Teil der Bedingungsgruppen sein:

-  Tageszeit (Minimum, Maximum, Wert)
-  Wochentag (Minimum, Maximum, Wert)
-  Azimut der Sonne (Minimum, Maximum, Wert)
-  Altitude der Sonne (Minimum, Maximum, Wert)
-  Alter des aktuellen Zustands (Minimum, Maximum, Wert)
-  Zufallszahl (Minimum, Maximum, Wert)
-  Vorheriger Zustand (Wert)
-  Trigger-Objekt, das die Zustandsermittlung ausgelöst hat

Zusätzlich können beliebige Items (z.B. Temperatur) als Bedingungen geprüft werden
(Minimum, Maximum oder Wert)
