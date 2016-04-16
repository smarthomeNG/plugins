# Ideen zum Widget handling.
Ideen zum Widget handling für smartVISU widgets durch smarthome.py.

Um Anwendern das benutzen von Plugins zu erleichtern, zu denen es smartVISU Widgets gibt implementiere ich einen Mechanismus um die Widgets mit smarthomeNG ausliefern zu können.

Im zweiten Schritt wird der Mechanismus so erweitert, dass diese Widgets auch in den per Autogeneration generierten Pages genutzt werden kann, die durch smarthomeNG beim Start generiert werden können.

Die Installation der Widgets in die smartVISU wird im ersten Schritt minimal invasiv erfolgen, um möglichst wenig Probleme und Wechselwirkungen zu erzeugen. In einem späteren Schritt ist eine vollständige Integration in die Widget Struktur der smartVISU angedacht. 


## Hinterlegung der Widgets im Plugin Verzeichnis

Um Widgets mit dem Plugin in die Installation des Anwenders auszuliefern, werden im Repository (Github) die Dateien aus denen das/die Widget(s) bestehen in einem Unterverzeichnis des Plugins abgelegt. Das Verzeichnis muss den Namen **sv_widgets** tragen.

Durch das auschecken des Plugins aus dem Repository werden die Widget Dateien auf das System des Anwenders übertragen. Beim anschließenden Neustart überträgt das Visu Plugin diese Dateien in die smartVISU Installation, falls **smartvisu_dir** für das Visu Plugin konfiguriert ist.


## Installation der Widgets in der smartVISU Umgebung

Beim Start von smarthomeNG werden die Widgets in die aktive **Pages** Umgebung der smartVISU kopiert. Dazu wird in der Umgebung ein Verzeichnis mit dem Namen **sh_widgets** angelegt und die Dateien werden in dieses Verzeichnis kopiert.

Nun kann auf ein Widget zugegriffen werden, indem der Anwender eine root-html-Datei um den Eintrag

```
	{% import "sh_widgets/<Name der Widget-Datei>.html" as <Widgetname> %}
```

erweitert und in der Seite das Widget aufruft.

Damit geänderte Widgets mit einer neuen Version eines Plugins ausgeliefert werden, wird beim kopieren ein vorhandenes Widget im Verzeichnis **sh_widgets** überschrieben. Wenn Anwender Widgets modifizieren wollen, so müssen sie eine Kopie im aktuellen Pages Verzeichnis (Parent zu **sh_widgets**) erstellen und die Importzeile entsprechend ändern:

```
	{% import "<Name der Widget-Datei>.html" as <Widgetname> %}
```


### Integration von Javascript Code und css in die smartVISU

Wenn Widgets Javascript Code oder css enthalten, muss dieses in die smartVISU integriert werden. Wie das am besten minimal invasiv erfolgt, muss ich mir noch ansehen. Vermutlich durch eine Erzeugung bzw. Ergänzung der Dateien visu.js bzw. visu.css im aktiven Pages Verzeichnis.

