import serial
from datetime import datetime
from pymodbus.client.sync import ModbusSerialClient as ModbusClient

connection = ModbusClient(method='rtu',port ='/dev/ttytrovis', timeout=0.5)
connection.connect()
print('Verbindung über: ', connection)

suchbereiche = list()
bereiche = list()
coils = list()

# Diese Coilbereiche durchsuchen - mehrere Bereiche können angegeben werden (ein Bereich je Zeile):
suchbereiche.append([0,99])       # Durchsuche die ersten 100 Coils
# suchbereiche.append([300,499])  # Ggf zweiter Bereich usw usw



#################################################################################################
# Bereits durchsuchte Bereiche: 

# suchbereiche.append([0,9999])
# ([1, 39], [56, 68], [87, 112], [115, 123], [129, 167], [175, 214], [221, 237], [244, 308],
#  [321, 337], [997, 1008], [1016, 1018], [1024, 1044], [1199, 1208], [1211, 1212], [1216, 1218],
#  [1224, 1237], [1799, 1808], [1824, 1844], [9899, 9910])

# ... hier erweitern ...
#################################################################################################


# Gültige Coils finden:
def durchsuche_bereiche(suchbereiche):
    anfangzeit = datetime.now()
    for bereich in suchbereiche:
        anfang = bereich[0]
        ende   = bereich[1]
        gefunden_anfang = -1 #0
        gefunden_ende   = 0
        while anfang <= ende:
            try:
                ergebnis = int((connection.read_coils(anfang, 1, unit=247)).bits[0])
                print(str(anfang) + ":" + str(ergebnis))
                if gefunden_anfang == -1:
                    gefunden_anfang = anfang
                gefunden_ende = anfang
                if anfang==bereich[1]:
                    bereiche.append([gefunden_anfang, gefunden_ende])
            except Exception as e:
                print(str(anfang), 'Fehler: ', e)
                if gefunden_anfang != -1:
                    bereiche.append([gefunden_anfang, gefunden_ende])
                    gefunden_anfang = -1
            anfang += 1
    endzeit = datetime.now()
    print('Gefundene Coilbereiche:', bereiche)
    dauer = endzeit - anfangzeit
    print('Suchzeit: ', dauer, 's')
    return bereiche

# Gefundenen gültige Coils mit Werten am Stück ausgeben:
def lese_coils(liste):
    print('Auslesen aller gefundenen Coils am Stück:')
    anfangzeit = datetime.now()
    for anfang, ende in liste:
        try:
            ergebnis = connection.read_coils(anfang, ende-anfang+1, unit=247)
        except Exception as e:
            print(str(anfang), 'Fehler: ', e)
        coilnum = anfang
        for coil in ergebnis.bits:
            coils.append([coilnum, int(coil)])
            coilnum += 1
            # unsauber, aber Länge von ergebnis ist immer Vielfaches von
            # 8 (8 bits = 1 Byte) und wird ggf rechts mit Nullen aufgefüllt,
            # daher sind im Ergebnis ggf mehr Elemente als angefragt:
            if coilnum > ende:
                break
    endzeit = datetime.now()
    print(coils)
    dauer = endzeit - anfangzeit
    print('Auslesezeit: ', dauer, 's')
    return coils
    
    
# Hauptroutine
gefunden = durchsuche_bereiche(suchbereiche)
lese_coils(gefunden)
connection.close()