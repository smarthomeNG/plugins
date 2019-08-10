import serial
from datetime import datetime
from pymodbus.client.sync import ModbusSerialClient as ModbusClient

connection = ModbusClient(method='rtu',port ='/dev/ttytrovis', timeout=0.5)
connection.connect()
print('Verbindung über: ', connection)

suchbereiche = list()
bereiche = list()
register = list()

# Diese Registerbereiche durchsuchen - mehrere Bereiche können angegeben werden (ein Bereich je Zeile):
suchbereiche.append([0,99])       # Durchsuche die ersten 100 Register
# suchbereiche.append([300,499])  # Ggf zweiter Bereich usw usw (max 124 Register pro Bereich!)

#################################################################################################
# Bereits durchsuchte Bereiche: 

# suchbereiche.append([0,10299])
gueltig = ( # normalerweise können 124 Register gelesen werden; ab 10000 nur 49; Auslesezeit 19.5s
    [0, 6], [9, 40], [98, 154], [159, 166], [200, 214], [299, 319], [999, 1044],
    [1053, 1071], [1089, 1095], [1199, 1243], [1255, 1271], [1455, 1470], [1799, 1812],
    [1827, 1839], [1855, 1870], [2999, 3123], [3124, 3248], [3249, 3250], [3499, 3548],
    [3999, 4123], [4124, 4248], [4249, 4373], [4374, 4498], [4499, 4623], [4624, 4748],
    [4749, 4873], [4874, 4998], [4999, 5123], [5124, 5248], [5249, 5373], [5374, 5498],
    [5499, 5623], [5624, 5748], [5749, 5873], [5874, 5998], [5999, 6046], [6489, 6613],
    [6614, 6738], [6739, 6863], [6864, 6988], [6989, 7113], [7114, 7238], [7239, 7363],
    [7364, 7488], [7489, 7613], [7614, 7738], [7739, 7863], [7864, 7988], [7989, 8113],
    [8114, 8238], [8239, 8363], [8364, 8488], [8489, 8613], [8614, 8738], [8739, 8863],
    [8864, 8988], [8989, 9113], [9114, 9238], [9239, 9363], [9364, 9488], [9489, 9613],
    [9614, 9738], [9739, 9863], [9864, 9988], [9989, 9999],
    [10000, 10040], [10041, 10080], [10081, 10120], [10121, 10160], [10161, 10200],
    [10201, 10240], [10241, 10253]
)

#for start, ende in gueltig:
#    suchbereiche.append([start,ende])
   
# ... hier ggf. erweitern ...
#################################################################################################


# Gültige Register finden:
def durchsuche_bereiche(suchbereiche):
    anfangzeit = datetime.now()
    for bereich in suchbereiche:
        anfang = bereich[0]
        ende   = bereich[1]
        gefunden_anfang = -1 #0
        gefunden_ende   = 0
        while anfang <= ende:
            try:
                ergebnis = connection.read_holding_registers(anfang, 1, unit=247)
                print(str(anfang) + ":" + str(ergebnis.registers))
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
    print('Gefundene Registerbereiche:', bereiche)
    dauer = endzeit - anfangzeit
    print('Suchzeit: ', dauer, 's')
    return bereiche

# Gefundenen gültige Register mit Werten am Stück ausgeben:
def lese_register(liste):
    print('Auslesen aller gefundenen Register am Stück:')
    anfangzeit = datetime.now()
    for anfang, ende in liste:
        try:
            ergebnis = connection.read_holding_registers(anfang, ende-anfang+1, unit=247)
            print(anfang, '-', ende, ':', ergebnis)
        except Exception as e:
            print(str(anfang), 'Fehler: ', e)
        regnum = anfang
        try:
            for reg in ergebnis.registers:
                register.append([regnum, int(reg)])
                regnum += 1
        except Exception as f:
            print(f)
    endzeit = datetime.now()
    print(register)
    dauer = endzeit - anfangzeit
    print('Auslesezeit: ', dauer, 's')
    return register
    
    
# Hauptroutine
gefunden = durchsuche_bereiche(suchbereiche)
lese_register(gefunden)

#lese_register(suchbereiche)

connection.close()