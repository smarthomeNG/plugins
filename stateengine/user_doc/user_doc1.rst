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

.. rubric:: Einführung
   :name: einfuehrungstateengine

Als Einstieg in das Plugin empfiehlt es sich, den `Blogeintrag <https://www.smarthomeng.de/tag/stateengine>`_
auf der SmarthomeNG Seite zu lesen!

.. rubric:: Funktionalität
   :name: funktionalitaet

Über zusätzliche Items in den items/\*.yaml Dateien können für beliebige Items
Zustandsautomaten implementiert werden. Jeder Zustand kann Sets von Einstiegsbedingungen haben
und diverse Aktionen auslösen, wenn der Zustand aktiv wird.

In regelmäßigen Intervallen werden die Zustände für jedes Objekt der angegebenen
Reihe nach geprüft. Der erste Zustand, bei dem eine Gruppe Einstiegsbedingungen
vollständig erfüllt ist, wird zum aktuellen Zustand. Die
Aktionen, die für diesen Zustand definiert sind, werden ausgeführt.

Wenn kein passender Zustand gefunden wird, passiert nichts, das Objekt verbleibt im vorherigen Zustand.
Dies kann in manchen Fällen Sinn machen, meist bietet es sich aber an,
einen Standardzustand ohne Eingangsbedingungen ganz am Ende der Hierarchie festzulegen.

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
