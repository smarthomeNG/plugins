#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  (C) 2019 René Jahncke aka Tom-Bom-badil     tommy_bombadil@hotmail.com
#########################################################################
#
#  Plugin to read out SAMSON TROVIS 557x heating controllers.
#
#  This file is part of SmartHomeNG.   
#
#  SmartHomeNG is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHomeNG is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHomeNG. If not, see <http://www.gnu.org/licenses/>.
#
#########################################################################



import serial
import array
from   lib.module import Modules
from   lib.model.smartplugin import *
from   datetime import datetime
from . import _coils
from . import _listen
from . import _register
from   pymodbus import version as pymodbusversion

try:   # Modbus rtu/serial, for pymodbus3+ or pymodbus2.x
    from pymodbus.client import ModbusSerialClient
except:
    from pymodbus.client.sync import ModbusSerialClient

try:   # Modbus tcp, for pymodbus3+ or pymodbus2.x
    from pymodbus.client.tcp import ModbusTcpClient
except:
    from pymodbus.client.sync import ModbusTcpClient



class trovis557x(SmartPlugin):


    ALLOW_MULTIINSTANCE = False
    PLUGIN_VERSION = '2.0.0'


    # Starten
    def __init__(self, sh, *args, **kwargs):
        self._init_complete = False
        self.logger = logging.getLogger(__name__)
        self.sh = sh
        self.logger.debug('__init__ aufgerufen')
        self.init_vars()
        self._modbus = self.connect_trovis()
        if self._connected and self.init_webinterface():
            self._modbus.close()
            self._init_complete = True

    # Nach dem Starten 1x für jedes Item durchlaufen
    def parse_item(self, item):

        if self.has_iattr(item.conf, 'trovis557x_var'):
            kurzname = str(item.conf['trovis557x_var'])
            if kurzname in self._register_tabelle.keys() or kurzname in self._coil_tabelle.keys():
                self._trovis_itemlist[kurzname] = item
                self.logger.debug('Parse_item: Verbinde Var ' + kurzname + ' ---> Item ' + str(item))
            else:
                self.logger.warning('! Parse_item: Unbekannter Wert "' + kurzname + '" von ' + str(item) + ' angefordert')


    # Setzt regelmäßigen Aufruf von poll_device im Scheduler, siehe cycle
    def run(self):
        self.logger.debug('run aufgerufen')
        self.scheduler_add('poll_device', self.poll_device, cycle=self._cycle)
        self.alive = True


    # Wird regelmäßig vom Scheduler aufgerufen
    def poll_device(self):
        self.logger.debug('poll_device aufgerufen')
        startzeit = datetime.now()
        
        self._modbus = self.connect_trovis()

        self.logger.debug('Registerbereiche lesen: ' + str(self._register_bereiche))
        for bereich in self._register_bereiche:
            ids_mit_werten = self.leseTrovis(bereich, 'register')
            if ids_mit_werten:
                self.logger.debug(str(ids_mit_werten))
                self.verarbeiteWerte(ids_mit_werten, 'register')
                ids_mit_werten = []
            
        self.logger.debug('Coilbereiche lesen: ' + str(self._coil_bereiche))
        for bereich in self._coil_bereiche:
            ids_mit_werten = self.leseTrovis(bereich, 'coils')
            if ids_mit_werten:
                self.logger.debug(str(ids_mit_werten))
                self.verarbeiteWerte(ids_mit_werten, 'coils')

        self._modbus.close()
        
        endzeit = datetime.now()
        dauer = (endzeit - startzeit).total_seconds()
        self.logger.debug('===========  Durchlauf beendet, Gesamtdauer: %.1f s' % dauer)


    # Beim Beenden 'saubermachen'
    def stop(self):
        self.logger.debug("Stop aufgerufen")
        if self._connected:
            self._modbus.close()
        self.alive = False


    def init_webinterface(self):
        """"
        Initialize the web interface for this plugin
        This method is only needed if the plugin is implementing a web interface
        """
        try:
            self.mod_http = Modules.get_instance().get_module(
                'http')  # try/except to handle running in a core version that does not support modules
        except:
            self.mod_http = None
        if self.mod_http == None:
            self.logger.error("Not initializing the web interface")
            return False

        import sys
        if not "SmartPluginWebIf" in list(sys.modules['lib.model.smartplugin'].__dict__):
            self.logger.warning("Web interface needs SmartHomeNG v1.5 and up. Not initializing the web interface")
            return False

        # set application configuration for cherrypy
        webif_dir = self.path_join(self.get_plugin_dir(), 'webif')
        config = {
            '/': {
                'tools.staticdir.root': webif_dir,
            },
            '/static': {
                'tools.staticdir.on': True,
                'tools.staticdir.dir': 'static'
            }
        }

        # Register the web interface as a cherrypy app
        self.mod_http.register_webif(WebInterface(webif_dir, self),
                                     self.get_shortname(),
                                     config,
                                     self.get_classname(), self.get_instance_name(),
                                     description='')

        return True


# ------------------------------------------
#    Ab hier Plugin-eigene Funktionen
# ------------------------------------------


    # Aus Master-Tabellen lesen: ID rein, Name raus
    def getKeyFromID(self, ID, datentyp):
        try:
            if datentyp == 'register':
                found = next(key for key in self._register_tabelle if self._register_tabelle[key]['ID'] == ID)
            else:
                found = next(key for key in self._coil_tabelle if self._coil_tabelle[key]['ID'] == ID)
        except StopIteration:
            found=-1
        return found


    # Variablen etc initialisieren (wird von __init__ gerufen)
    def init_vars(self):
        
        self._model = self.get_parameter_value('model')
        self._revision = self.get_parameter_value('revision')
        
        self._modbus_mode = self.get_parameter_value('modbus_mode')
        self._modbus_port = self.get_parameter_value('modbus_port')
        if self._modbus_mode == 'tcp':
            self._modbus_trovis_ip = self._modbus_port.split(':')[0]
            self._modbus_trovis_ip_port = self._modbus_port.split(':')[1]
        self._modbus_speed = self.get_parameter_value('modbus_speed')
        self._modbus_timeout = self.get_parameter_value('modbus_timeout')
        self._modbus_trovis_address = self.get_parameter_value('modbus_trovis_address')
        self._modbus_debug = self.get_parameter_value('modbus_debug')
        
        self._cycle = self.get_parameter_value('cycle')

        self._register_bereiche = _register.register_bereiche
        self._register_tabelle = _register.register_tabelle
        self._coil_bereiche = _coils.coil_bereiche
        self._coil_tabelle = _coils.coil_tabelle
        self._listen_tabelle = _listen.listen_tabelle    

        self._trovis_itemlist = {}
        
        self._pymodbus_major = pymodbusversion.version.short()[0]


    # Schnittstelle initialisieren (wird von __init__ und bei jedem Poll aufgerufen)
    def connect_trovis(self):
        try:
            # self._modbus_debug = False  #ToDo
            if self._modbus_mode == 'rtu':
                connection = ModbusSerialClient(method=self._modbus_mode, port=self._modbus_port, timeout=self._modbus_timeout, baudrate=self._modbus_speed)
            else:
                connection = ModbusTcpClient(host=self._modbus_trovis_ip, port=self._modbus_trovis_ip_port)
                # Aus anderem Plugin: self.client = ModbusTcpClient(ip, port=port)
            if connection.connect():
                self._connected = True
                self.logger.info('Verbindung zur Trovis hergestellt: ' + str(connection))
            else:
                self._connected = False
                self.logger.debug('Verbindung zur Trovis fehlgeschlagen: ' + str(connection))
        except Exception as e:
            self.logger.debug('Exception beim Trovis Verbindungsaufbau: ' + str(e))
        return connection
        
        
    # Trovis auslesen
    def leseTrovis(self, _bereich, _datentyp):
        
        # self.logger.info('Version: ' + self._pymodbus_major)
        
        try:
            _ids_mit_werten = []
            werte = []
            id_aktuell = _bereich[0]
            if _datentyp == 'register': # register lesen
                self.logger.debug('Lese Registerbereich ' + str(_bereich[0]) + ' - ' + str(_bereich[1]))
                if self._pymodbus_major == '2':
                    werte = self._modbus.read_holding_registers(_bereich[0], _bereich[1]-_bereich[0]+1, unit = self._modbus_trovis_address)
                else:
                    werte = self._modbus.read_holding_registers(_bereich[0], _bereich[1]-_bereich[0]+1, slave = self._modbus_trovis_address)
                for wert in werte.registers:
                    if self.getKeyFromID(id_aktuell, 'register') != -1:
                        _ids_mit_werten.append([id_aktuell, wert])
                    id_aktuell += 1
            else: # coils lesen
                self.logger.debug('Lese Coilsbereich ' + str(_bereich[0]) + ' - ' + str(_bereich[1]))
                if self._pymodbus_major == '2':
                    werte = self._modbus.read_coils(_bereich[0], _bereich[1]-_bereich[0]+1, unit = self._modbus_trovis_address)
                else:
                    werte = self._modbus.read_coils(_bereich[0], _bereich[1]-_bereich[0]+1, slave = self._modbus_trovis_address)
                for wert in werte.bits:
                    if self.getKeyFromID(id_aktuell, 'coil') != -1:
                        _ids_mit_werten.append([id_aktuell, int(wert)])
                    id_aktuell += 1
                    # unsauber, aber Länge von 'werte' ist immer Vielfaches von
                    # 8 (8 bits = 1 Byte) und wird ggf rechts mit Nullen aufgefüllt,
                    # daher sind im Ergebnis ggf mehr Elemente als angefragt:
                    if id_aktuell > _bereich[1]:
                        break
        except Exception as e:
            _ids_mit_werten = []
            self.logger.debug('Im Bereich ' + str(_bereich) + ' liefert dieser Regler oder die Reglerkonfiguration keine lesbaren Register/Coils!')
        return _ids_mit_werten


    # Ausgelesene Werte verarbeiten und bei Bedarf auf Items schreiben
    def verarbeiteWerte(self, _ids_mit_werten, _datentyp):   # für das jeweils erste WMZ-Register stimmt etwas nicht (?)

        # self.logger.debug('Verarbeite ' + _datentyp + ' ' + str(_ids_mit_werten[0][0]) + '-' + str(_ids_mit_werten[len(_ids_mit_werten)-1][0]) + ':')
        
        for id, buswert in _ids_mit_werten:
            
            itemwert = ''
            kurzname = self.getKeyFromID(id, _datentyp)

            if _datentyp == 'register':
                alle_details = self._register_tabelle[kurzname]
                faktor = alle_details['Faktor']
                digits = alle_details['Digits']
            else:
                alle_details = self._coil_tabelle[kurzname]
            art = alle_details['Art']
            typ = alle_details['Typ']
            einheit = alle_details['Einheit']
            
            # hier oben ggf. Sonderlocken für einzelne Register
            # if kurzname == 'xyz':
            # usw.

            # Standardtypen für Register *und* Coils
            if typ[:6] == 'Liste_':
                wert = int(buswert)
                einheit = self._listen_tabelle[typ][wert]
                
            elif typ == '???':
                wert = int(buswert)
                kurzname = 'unbekannt-' + str(id)

            # Standardtypen ausschliesslich für Register
            elif typ == 'Version':
                wert = str('{0:.'+str(digits)+'f}').format((buswert*faktor)/10**digits)

            elif typ == 'Zahl':
                busmin = int(alle_details['Busmin'])
                # 16bit-Register auf negativen Wert prüfen (z.B. Temperaturen)
                if busmin < 0 and buswert > 32767:
                    signed_int = buswert - 65536
                else:
                    signed_int = buswert

                if kurzname in self._trovis_itemlist.keys() and self.has_iattr(self._trovis_itemlist[kurzname].conf, 'invalid_to_zero'):
                    if buswert == 32767 and self.get_iattr_value(self._trovis_itemlist[kurzname].conf, 'invalid_to_zero') == True:
                        self.logger.debug('    ~~> Setze 32767 auf 0: ----> ' + kurzname)
                        signed_int = 0

                if digits == 0:
                    wert = int(str('{0:.'+str(digits)+'f}').format((signed_int*faktor)))
                else:
                    wert = float(str('{0:.'+str(digits)+'f}').format((signed_int*faktor)))

            elif typ == 'Datum':
                if len(str(buswert)) == 3:
                    wert = '0' + '{0:.2f}'.format(buswert/100) + '.'
                else:
                    wert = '{0:.2f}'.format(buswert/100) + '.'

            elif typ == 'Uhrzeit':
                if int(buswert) == 0:
                    wert = '00:00'
                elif int(buswert) < 60:
                    wert = '00:' + str(buswert)[-2:]
                elif int(buswert) < 960:
                    wert = str(buswert)[:1] + ':' + str(buswert)[-2:]
                else:
                    wert = str(buswert)[:2] + ':' + str(buswert)[-2:]

            else:
                wert = int(buswert)
                kurzname = 'UNGUELTIG-' + id

            # itemwert = [str(buswert), str(wert), str(einheit)]
            
            if kurzname in self._trovis_itemlist.keys():
                # alt - wurde als Liste geschrieben: self._trovis_itemlist[kurzname]([buswert, wert, einheit])
                self._trovis_itemlist[kurzname](wert)
                self._trovis_itemlist[kurzname].conf['liste'] = ([buswert, wert, einheit])
                if typ[:6] == 'Liste_':
                    self.logger.debug('    ~~> ID %s = %s ---> Var %s = %s ---> Item %s' % (id, buswert, kurzname, einheit, self._trovis_itemlist[kurzname]))
                else:
                    self.logger.debug('    ~~> ID %s = %s ---> Var %s = %s ---> Item %s' % (id, buswert, kurzname, str(wert) + ' ' + einheit, self._trovis_itemlist[kurzname]))

            # Vorsicht - große Datenmengen in kurzer Zeit!!!
            # Kommentar entfernen, um alle gelesenen Register/Coils einzeln im Debug-Log zu sehen:
            #
            # self.logger.debug('%4u ---> %s ---> %s' % (id, kurzname, itemwert))
                


# ------------------------------------------
#    Webinterface of the plugin
# ------------------------------------------

import cherrypy
from jinja2 import Environment, FileSystemLoader


class WebInterface(SmartPluginWebIf):

    def __init__(self, webif_dir, plugin):
        """
        Initialization of instance of class WebInterface
        :param webif_dir: directory where the webinterface of the plugin resides
        :param plugin: instance of the plugin
        :type webif_dir: str
        :type plugin: object
        """
        self.logger = logging.getLogger(__name__)
        self.webif_dir = webif_dir
        self.plugin = plugin
        self.tplenv = self.init_template_environment()

    @cherrypy.expose
    def index(self, reload=None):
        """
        Build index.html for cherrypy
        Render the template and return the html file to be delivered to the browser
        :return: contents of the template after beeing rendered 
        """
        tmpl = self.tplenv.get_template('index.html')
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        return tmpl.render(p=self.plugin)  
    
