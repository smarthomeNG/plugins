#
# Plugin for Stiebel Eltron and Tecalor integrated heatpumps LWZ/THZ 30x/40x.
#

# Requirements
* pySerial (sudo apt-get install python-serial)
* Serial port connected to the LWZ/THZ maintenance port.
  The wiring description is provided at:
  http://robert.penz.name/heat-pump-lwz

## Supported Hardware

Tested with:
* THZ 404 SOL, software version 5.39, software IDs 5993 & 7278
* THZ 303i, software version 4.39

According to the FHEM forum (http://forum.fhem.de/index.php/topic,13132.0.html) the original Perl code also works with other heatpump models (303, 304, 403). 

# Configuration

## plugin.conf

<pre>
[thz]
    class_name = THZ
    class_path = plugins.thz
    serial_port = /dev/ttyUSB0
    baudrate = 115200
    poll_period = 30
    min_update_period = 300
    max_update_period = 43200
</pre>

Description of the attributes:

* __serial_port__: serial port connected to the heatpump
* __baudrate__: port speed, recent models use 115200 bps, older heatpumps may use 57600 bps or even 9600 bps
* __poll_period__: interval in seconds how often the data is read from the heatpump
* __min_update_period__: interval in seconds for updating the values changing frequently (e.g. temperature), it should be higher than the poll period
* __max_update_period__: interval in seconds for updating the values with infrequent changes (e.g. counters updated once per day)

## items.conf

There are read-only parameters and read-write parameters.
Temperature values are in °C.
Heat and power values are provided in kWh.
For the description of the read-write parameters refer to the heatpump manual. The parameter name includes the parameter number (i.e. the prefix pXX) described in the manual.

<pre>
[thz]
# plugin status
    [[comPortStatus]]
        # port status:
        # 0 - failed to open serial port,
        # 1 - serial port OK
        type = num
        thz = comPortStatus
    [[comPortReopenAttempts]]
        # number of attempts to open the serial port incl. temporary failures
        type = num
        thz = comPortReopenAttempts
    [[rxCount]]
        # number of messages received from the heatpump
        type = num
        thz = rxCount
    [[txCount]]
        # number of messages transmitted to the heatpump
        type = num
        thz = txCount
    [[rxChecksumErrorCount]]
        # number of received messages with checksum errors
        # This indicates issues with the serial link (too long cable,
        # poor shielding, poor USB adapter, performance problems).
        type = num
        thz = rxChecksumErrorCount
    [[rxNackCount]]
        # number of requests rejected by the heatpump
        # Rare occurence may indicate issues with serial link.
        # Periodic occurence indicates (partial) protocol incompatibility with
        # the given heatpump model or software version/ID.
        type = num
        thz = rxNackCount
    [[rxTimeoutCount]]
        # number of requests not responded to by the heatpump
        type = num
        thz = rxTimeoutCount
    [[rxFramingErrorCount]]
        # number of low-level protocol violations in the receive path
        # This indicates issues with the serial link (too long cable,
        # poor shielding, poor USB adapter, performance problems).
        type = num
        thz = rxFramingErrorCount

# special parameters for debugging purposes
    [[logRegister]]
        # request logging register with the specified ID (hex)
        type = str
        thz = logRegister
    [[logFullScan]]
        # request logging a full register scan
        type = str
        thz = logFullScan

# read-only parameters

    [[outsideTemp]]
        # Aussentemperatur (korrigiert)
        type = num
        thz = outsideTemp
        sqlite = init
    [[flowTemp]]
        # Vorlauftemperatur HK1
        type = num
        thz = flowTemp
        sqlite = init
    [[returnTemp]]
        # Ruecklauftemperatur HK1
        type = num
        thz = returnTemp
        sqlite = init
    [[dhwTemp]]
        # Warmwassertemperatur (Ist)
        type = num
        thz = dhwTemp
        sqlite = init
    [[hotGasTemp]]
        # Heissgastemperatur
        type = num
        thz = hotGasTemp
        sqlite = init
#    [[insideTemp]]
        # Raumtemperatur (vom Zusatzfuehler)
#        type = num
#        thz = insideTemp
    [[evaporatorTemp]]
        # Verdampfertemperatur
        type = num
        thz = evaporatorTemp
        sqlite = init
    [[condenserTemp]]
        # Verfluessigertemperatur 
        type = num
        thz = condenserTemp
        sqlite = init
    [[mixerOpen]]
        # Eingang "Mischerventil AUF" (siehe Anschlusse, Installationsanleitung)
        type = bool
        thz = mixerOpen
        sqlite = init
    [[mixerClosed]]
        # Eingang "Mischerventil ZU" (siehe Anschlusse, Installationsanleitung)
        type = bool
        thz = mixerClosed
        sqlite = init
    [[heatPipeValve]]
        # Heatpipe Ventil
        type = bool
        thz = heatPipeValve
        sqlite = init
    [[diverterValve]]
        # Umschaltventil
        type = bool
        thz = diverterValve
        sqlite = init
    [[dhwPumpOn]]
        # WW-Umwaelzpumpe an
        type = bool
        thz = dhwPumpOn
        sqlite = init
    [[heatingCircuitPumpOn]]
        # Heizkreis-Zirkulationspumpe (HK1) an
        type = bool
        thz = heatingCircuitPumpOn
        sqlite = init
#    [[solarPumpOn]]
        # Solar-Zirkulationspumpe an
#        type = bool
#        thz = solarPumpOn
    [[compressorOn]]
        # Verdichter an
        type = bool
        thz = compressorOn
        sqlite = init
    [[boosterStage1On]]
        # Heizstab Stufe 1 an
        type = bool
        thz = boosterStage1On
        sqlite = init
    [[boosterStage2On]]
        # Heizstab Stufe 2 an
        type = bool
        thz = boosterStage2On
        sqlite = init
    [[boosterStage3On]]
        # Heizstab Stufe 3 an
        type = bool
        thz = boosterStage3On
        sqlite = init
    [[highPressureSensorOn]]
        # Hochdruckwaechter
        type = bool
        thz = highPressureSensorOn
        sqlite = init
    [[lowPressureSensorOn]]
        # Niederdruckwaechter
        type = bool
        thz = lowPressureSensorOn
        sqlite = init
    [[evaporatorIceMonitorOn]]
        # Waechter Vereisung Verdampfer
        type = bool
        thz = evaporatorIceMonitorOn
        sqlite = init
    [[signalAnodeOn]]
        # Signalanode
        type = bool
        thz = signalAnodeOn
        sqlite = init
    [[evuEnable]]
        # EVU Freigabe (ausserhalb der Sperrzeit fuer Zusatzheizung)
        type = bool
        thz = evuEnable
    [[ovenFireplaceOn]]
        # Eingang "Ofen/Kamin" (siehe Anschluesse, Installationsanleitung)
        type = bool
        thz = ovenFireplaceOn
    [[STB_On]]
        # Eingang "STB" (siehe Anschluesse, Installationsanleitung)
        type = bool
        thz = STB_On
    [[outputVentilatorPower]]
        # Abluft Soll, %
        type = num
        thz = outputVentilatorPower
    [[inputVentilatorPower]]
        # Zuluft Soll, %
        type = num
        thz = inputVentilatorPower
    [[mainVentilatorPower]]
        # Fortluefter Soll, %
        type = num
        thz = mainVentilatorPower
    [[outputVentilatorSpeed]]
        # Drehzahl (Ist) Abluefter,Hz
        type = num
        thz = outputVentilatorSpeed
    [[inputVentilatorSpeed]]
        # Drehzahl (Ist) Zuluefter,Hz
        type = num
        thz = inputVentilatorSpeed
    [[mainVentilatorSpeed]]
        # Drehzahl (Ist) Fortluefter,Hz
        type = num
        thz = mainVentilatorSpeed
    [[outside_tempFiltered]]
        # Aussentemperatur (mit Verzoegerung)
        type = num
        thz = outside_tempFiltered
        sqlite = init
    [[relHumidity]]
        # relative Luftfeuchtigkeit (nur mit vorhandener Fernbedienung)
        type = num
        thz = relHumidity
        sqlite = init
    [[dewPoint]]
        # Taupunkt (nur beim Kuehlen ?)
        type = num
        thz = dewPoint
    [[P_Nd]]
        # Niederdruck-Wert
        type = num
        thz = P_Nd
        sqlite = init
    [[P_Hd]]
        # Hochdruck-Wert
        type = num
        thz = P_Hd
        sqlite = init
    [[actualPower_Qc]]
        # momentane Waermeleistung (Schaetzwert)
        type = num
        thz = actualPower_Qc
    [[actualPower_Pel]]
        # momentane elektrische Leistung (Schaetzwert)
        type = num
        thz = actualPower_Pel
    [[roomTempRC]]
        # Raumtemperatur (nur mit vorhandener Fernbedienung)
        type = num
        thz = roomTempRC
    [[compressorHeatingCycles]]
        # Verdichterlaufzeit zum Heizen (Stunden)
        type = num
        thz = compressorHeatingCycles
        sqlite = init
    [[compressorCoolingCycles]]
        # Verdichterlaufzeit zum Kuehlen (Stunden)
        type = num
        thz = compressorCoolingCycles
        sqlite = init
    [[compressorDHWCycles]]
        # Verdichterlaufzeit zur WW-Erwaermung (Stunden)
        type = num
        thz = compressorDHWCycles
        sqlite = init
    [[boosterDHWCycles]]
        # Heizstablaufzeit zur WW-Erwaermung (Stunden)
        type = num
        thz = boosterDHWCycles
        sqlite = init
    [[boosterHeatingCycles]]
        # Heizstablaufzeit Heizen (Stunden)
        type = num
        thz = boosterHeatingCycles
        sqlite = init
#    [[collectorTempSol]]
        # Solarkollektor-Temperatur
#        type = num
#        thz = collectorTempSol
#    [[dhwTempSol]]
        # Temperatur solare Warmwasserbereitung
#        type = num
#        thz = dhwTempSol
#    [[flowTempSol]]
        # solare HK-Vorlauftemperatur
#        type = num
#        thz = flowTempSol
#    [[ed_sol_pump_temp]]
        #  ???
#        type = num
#        thz = ed_sol_pump_temp
    [[dhwSetTemp]]
        # WW-Solltemperatur
        type = num
        thz = dhwSetTemp
        sqlite = init
    [[compBlockTime]]
        # ???
        type = num
        thz = compBlockTime
    [[heatBlockTime]]
        # ???
        type = num
        thz = heatBlockTime
    [[opModeHC]]
        # Betriebsmodus Heizung
        type = str
        thz = opModeHC
    [[returnTempHC1]]
        # Ruecklauftemperatur HK1
        type = num
        thz = returnTempHC1
        sqlite = init
    [[integralHeatHC1]]
        # ???
        type = num
        thz = integralHeatHC1
    [[flowTempHC1]]
        # Vorlauftemperatur HK1
        type = num
        thz = flowTempHC1
        sqlite = init
    [[heatSetTempHC1]]
        # Solltemperatur HK1
        type = num
        thz = heatSetTempHC1
        sqlite = init
    [[heatTempHC1]]
        # Isttemperatur HK1
        type = num
        thz = heatTempHC1
        sqlite = init
    [[onHysteresisNo]]
        # Hysteresennummer
        type = num
        thz = onHysteresisNo
    [[offHysteresisNo]]
        # Hysteresennummer
        type = num
        thz = offHysteresisNo
    [[HCBoosterStage]]
        # Zusatzheizungsstufe
        type = num
        thz = HCBoosterStage
#    [[returnTempHC2]]
        # Ruecklauftemperatur HK2
#        type = num
#        thz = returnTempHC2
#    [[heatSetTempHC2]]
        # Solltemperatur HK2
#        type = num
#        thz = heatSetTempHC2
#    [[heatTempHC2]]
        # Isttemperatur HK2
#        type = num
#        thz = heatTempHC2
    [[numberOfFaults]]
        # Anzahl Fehlermeldungen ((es gibt 10, das Plugin gibt aber nur die ersten 4 aus))
        type = num
        thz = numberOfFaults
    [[fault0Code]]
        # Fehlercode 0
        type = num
        thz = fault0Code
    [[fault0Time]]
        # Zeit Fehlercode 0
        type = str
        thz = fault0Time
    [[fault0Date]]
        # Datum Fehlercode 0
        type = str
        thz = fault0Date
    [[fault1Code]]
        type = num
        thz = fault1Code
    [[fault1Time]]
        type = str
        thz = fault1Time
    [[fault1Date]]
        type = str
        thz = fault1Date
    [[fault2Code]]
        type = num
        thz = fault2Code
    [[fault2Time]]
        type = str
        thz = fault2Time
    [[fault2Date]]
        type = str
        thz = fault2Date
    [[fault3Code]]
        type = num
        thz = fault3Code
    [[fault3Time]]
        type = str
        thz = fault3Time
    [[fault3Date]]
        type = str
        thz = fault3Date
    [[time]]
        # WP-Zeit
        type = str
        thz = time
    [[date]]
        # WP-Datum
        type = str
        thz = date
    [[version]]
        # Softwarestand
        type = num
        thz = version
    [[prodDate]]
        # WP-Produktionsdatum
        type = str
        thz = prodDate
    [[flowRateHC1]]
        # Volumenstrom HK1, l/min
        type = num
        thz = flowRateHC1
    [[softwareID]]
        # Software ID
        type = num
        thz = softwareID

    # Parameter gesetzt auf true, wenn enstsprechende
    # Icons im Display angezeigt werden
#    [[iconProgram]]
        # Icon "Schaltprogramm"
#        type = bool
#        thz = iconProgram
    [[iconCompressor]]
        # Icon "Verdichter"
        type = bool
        thz = iconCompressor
    [[iconHeating]]
        # Icon "Heizen"
        type = bool
        thz = iconHeating
    [[iconCooling]]
        # Icon "Kuehlen"
        type = bool
        thz = iconCooling
    [[iconDHW]]
        # Icon "Warmwasserbereitung"
        type = bool
        thz = iconDHW
    [[iconBooster]]
        # Icon "elektrische Nachheizstufen"
        type = bool
        thz = iconBooster
    [[iconService]]
        # Icon "Service"
        type = bool
        thz = iconService
    [[iconBothFilters]]
        # Icon "Filterwechsel oben und unten"
        type = bool
        thz = iconBothFilters
#    [[iconVentilation]]
        # Icon "Lueftungsstufe"
#        type = bool
#        thz = iconVentilation
    [[iconCirculationPump]]
        # Icon "Heizkreispumpe"
        type = bool
        thz = iconCirculationPump
    [[iconDeicingCondenser]]
        # Icon "Abtauen Verdamper"
        type = bool
        thz = iconDeicingCondenser
    [[iconUpperFilter]]
        # Icon "Filterwechsel oben"
        type = bool
        thz = iconUpperFilter
    [[iconLowerFilter]]
        # Icon "Filterwechsel unten"
        type = bool
        thz = iconLowerFilter

    # Energiewerte
    [[boostDHWTotal]]
        # Energieverbrauch Zusatzheizung zur WW-Erwaermung
        type = num
        thz = boostDHWTotal
        sqlite = init
    [[boostHCTotal]]
        # Energieverbrauch Zusatzheizung zum Heizen
        type = num
        thz = boostHCTotal
        sqlite = init
    [[heatRecoveredDay]]
        # Waermemenge Waermeruckgewinnung, Tageswert
        type = num
        thz = heatRecoveredDay
        sqlite = init
    [[heatRecoveredTotal]]
        # Waermemenge Waermeruckgewinnung, gesamt
        type = num
        thz = heatRecoveredTotal
        sqlite = init
    [[heatDHWDay]]
        # Waermemenge WW-Bereitung, Tageswert
        type = num
        thz = heatDHWDay
        sqlite = init
    [[heatDHWTotal]]
        # Waermemenge WW-Bereitung, gesamt
        type = num
        thz = heatDHWTotal
        sqlite = init
    [[heatHCDay]]
        # Waermemenge Heizen, Tageswert
        type = num
        thz = heatHCDay
        sqlite = init
    [[heatHCTotal]]
        # Waermemenge Heizen, gesamt
        type = num
        thz = heatHCTotal
        sqlite = init
    [[ePowerDHWDay]]
        # Energieverbrauch zur WW-Erwaermung, Tageswert
        type = num
        thz = ePowerDHWDay
        sqlite = init
    [[ePowerDHWTotal]]
        # Energieverbrauch zur WW-Erwaermung, gesamt
        type = num
        thz = ePowerDHWTotal
        sqlite = init
    [[ePowerHCDay]]
        # Energieverbrauch zum Heizen, Tageswert
        type = num
        thz = ePowerHCDay
        sqlite = init
    [[ePowerHCTotal]]
        # Energieverbrauch zum Heizen, gesamt
        type = num
        thz = ePowerHCTotal
        sqlite = init

# read/write parameters

    # Parameternamen beinhalten Parameternummern (pXX), die im Handbuch
    # beschrieben sind.

    [[pOpMode]]
        type = str
        thz = pOpMode
#    [[p01RoomTempDayHC1]]
#        type = num
#        thz = p01RoomTempDayHC1
#    [[p01RoomTempDayHC1SummerMode]]
#        type = num
#        thz = p01RoomTempDayHC1SummerMode
#    [[p01RoomTempDayHC2]]
#        type = num
#        thz = p01RoomTempDayHC2
#    [[p01RoomTempDayHC2SummerMode]]
#        type = num
#        thz = p01RoomTempDayHC2SummerMode
#    [[p02RoomTempNightHC1]]
#        type = num
#        thz = p02RoomTempNightHC1
#    [[p02RoomTempNightHC1SummerMode]]
#        type = num
#        thz = p02RoomTempNightHC1SummerMode
#    [[p02RoomTempNightHC2]]
#        type = num
#        thz = p02RoomTempNightHC2
#    [[p02RoomTempNightHC2SummerMode]]
#        type = num
#        thz = p02RoomTempNightHC2SummerMode
#    [[p03RoomTempStandbyHC1]]
#        type = num
#        thz = p03RoomTempStandbyHC1
#    [[p03RoomTempStandbyHC1SummerMode]]
#        type = num
#        thz = p03RoomTempStandbyHC1SummerMode
#    [[p03RoomTempStandbyHC2]]
#        type = num
#        thz = p03RoomTempStandbyHC2
#    [[p03RoomTempStandbyHC2SummerMode]]
#        type = num
#        thz = p03RoomTempStandbyHC2SummerMode
#    [[p04DHWsetDayTemp]]
#        type = num
#        thz = p04DHWsetDayTemp
#    [[p05DHWsetNightTemp]]
#        type = num
#        thz = p05DHWsetNightTemp
#    [[p06DHWsetStandbyTemp]]
#        type = num
#        thz = p06DHWsetStandbyTemp
    [[p07FanStageDay]]
        type = num
        thz = p07FanStageDay
#    [[p08FanStageNight]]
#        type = num
#        thz = p08FanStageNight
#    [[p09FanStageStandby]]
#        type = num
#        thz = p09FanStageStandby
#    [[p99FanStageParty]]
#        type = num
#        thz = p99FanStageParty
#    [[p11DHWsetManualTemp]]
#        type = num
#        thz = p11DHWsetManualTemp
    [[p13GradientHC1]]
        type = num
        thz = p13GradientHC1
    [[p14LowEndHC1]]
        type = num
        thz = p14LowEndHC1
    [[p15RoomInfluenceHC1]]
        type = num
        thz = p15RoomInfluenceHC1
#    [[p16GradientHC2]]
#        type = num
#        thz = p16GradientHC2
#    [[p17LowEndHC2]]
#        type = num
#        thz = p17LowEndHC2
#    [[p18RoomInfluenceHC2]]
#        type = num
#        thz = p18RoomInfluenceHC2
#    [[p19FlowProportionHC1]]
#        type = num
#        thz = p19FlowProportionHC1
#    [[p21Hyst1]]
#        type = num
#        thz = p21Hyst1
#    [[p22Hyst2]]
#        type = num
#        thz = p22Hyst2
#    [[p23Hyst3]]
#        type = num
#        thz = p23Hyst3
#    [[p24Hyst4]]
#        type = num
#        thz = p24Hyst4
#    [[p25Hyst5]]
#        type = num
#        thz = p25Hyst5
#    [[p29HystAsymmetry]]
#        type = num
#        thz = p29HystAsymmetry
#    [[p30integralComponent]]
#        type = num
#        thz = p30integralComponent
#    [[p32hystDHW]]
#        type = num
#        thz = p32hystDHW
#    [[p33BoosterTimeoutDHW]]
#        type = num
#        thz = p33BoosterTimeoutDHW
#    [[p34BoosterDHWTempAct]]
#        type = num
#        thz = p34BoosterDHWTempAct
#    [[p35PasteurisationInterval]]
#        type = num
#        thz = p35PasteurisationInterval
#    [[p35PasteurisationTemp]]
#        type = num
#        thz = p35PasteurisationTemp
    [[p37FanStage1AirIn]]
        type = num
        thz = p37FanStage1AirIn
#    [[p38FanStage2AirIn]]
#        type = num
#        thz = p38FanStage2AirIn
#    [[p39FanStage3AirIn]]
#        type = num
#        thz = p39FanStage3AirIn
    [[p40FanStage1AirOut]]
        type = num
        thz = p40FanStage1AirOut
#    [[p41FanStage2AirOut]]
#        type = num
#        thz = p41FanStage2AirOut
#    [[p42FanStage3AirOut]]
#        type = num
#        thz = p42FanStage3AirOut
#    [[p43UnschedVent3]]
#        type = num
#        thz = p43UnschedVent3
#    [[p44UnschedVent2]]
#        type = num
#        thz = p44UnschedVent2
#    [[p45UnschedVent1]]
#        type = num
#        thz = p45UnschedVent1
#    [[p46UnschedVent0]]
#        type = num
#        thz = p46UnschedVent0
#    [[p49SummerModeTemp]]
#        type = num
#        thz = p49SummerModeTemp
#    [[p50SummerModeHysteresis]]
#        type = num
#        thz = p50SummerModeHysteresis
#    [[p54MinPumpCycles]]
#        type = num
#        thz = p54MinPumpCycles
#    [[p55MaxPumpCycles]]
#        type = num
#        thz = p55MaxPumpCycles
#    [[p56OutTempMaxPumpCycles]]
#        type = num
#        thz = p56OutTempMaxPumpCycles
#    [[p57OutTempMinPumpCycles]]
#        type = num
#        thz = p57OutTempMinPumpCycles
#    [[p75passiveCooling]]
#        type = num
#        thz = p75passiveCooling
#    [[p76RoomThermCorrection]]
#        type = num
#        thz = p76RoomThermCorrection
#    [[p77OutThermFilterTime]]
#        type = num
#        thz = p77OutThermFilterTime
#    [[p78DualModePoint]]
#        type = num
#        thz = p78DualModePoint
#    [[p79BoosterTimeoutHC]]
#        type = num
#        thz = p79BoosterTimeoutHC
#    [[p83DHWsetSolarTemp]]
#        type = num
#        thz = p83DHWsetSolarTemp
#    [[p99DHWmaxFlowTemp]]
#        type = num
#        thz = p99DHWmaxFlowTemp
#    [[p89DHWeco]]
#        type = num
#        thz = p89DHWeco
#    [[p99startUnschedVent]]
#        type = num
#        thz = p99startUnschedVent
#    [[pClockDay]]
#        type = num
#        thz = pClockDay
#    [[pClockDay]]
#        type = num
#        thz = pClockDay
#    [[pClockYear]]
#        type = num
#        thz = pClockYear
#    [[pClockHour]]
#        type = num
#        thz = pClockHour
#    [[pClockMinute]]
#        type = num
#        thz = pClockMinute
</pre>

#######################################################
Release history

* beta1, Dec 17, 2016
  + new status parameters
      iconCooling
      iconService
  + new read/write parameters:
      p32hystDHW
      p34BoosterDHWTempAct
      p35PasteurisationInterval
      p35PasteurisationTemp
      p76RoomThermCorrection
      p77OutThermFilterTime
      p89DHWeco
      p99DHWmaxFlowTemp
      p99startUnschedVent
      pClockDay
      pClockMonth
      pClockYear
      pClockHour
      pClockMinute
  - removed parameters:
      p99CoolingRtDay (redundant, see p01-p03 summer mode)
      p99CoolingRtNight (redundant, see p01-p03 summer mode)

* alpha6, Aug 5, 2016
  + new read/write parameters:
      p99CoolingRtDay
      p99CoolingRtNight
      p99CoolingSwitch
  + new status parameters
      inputVentSpeed
      outputVentSpeed
      inputAirFlow
      outputAirFlow


* alpha5, Jan 31, 2015

* alpha4, Jan 25, 2015

* alpha3, Jan 5, 2015

* alpha2, Dec 26, 2014

* alpha1, Dec 19, 2014

