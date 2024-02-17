
_defaults2= {
    'stopItems': None,          # used: to disable the controller

    'timerendItem': None,       # - NICHT für den PI Regler
    'HVACModeItem': None,       # - NICHT für den PI Regler
    'HVACMode': 0,              # - NICHT für den PI Regler

    'timerendItem': None,       # - NICHT für den PI Regler
    'HVACModeItem': None,       # - NICHT für den PI Regler
    'HVACMode': 0,              # - NICHT für den PI Regler

    'tempDefault': 0,           # - NICHT für den PI Regler
    'tempDrop': 0,              # - NICHT für den PI Regler
    'tempBoost': 0,             # - NICHT für den PI Regler
    'tempBoostTime': 0,         # - NICHT für den PI Regler
    'valveProtect': False,      # - NICHT für den PI Regler
    'valveProtectActive': False,# - NICHT für den PI Regler
    'validated': False          # - NICHT für den PI Regler
}

_defaults = {'currentItem' : None,              # used: to get x = current value
             'setpointItem' : None,             # used: to get w = setpoint value
             'actuatorItem' : None,             # used: to get actuator item to write the output (correcting value) y to
             'eSum' : 0,                        # Summe der Regelabweichungen
             'Kp' : 0,                          # Verstärkungsfaktor
             'Ki' : 0,                          # Integralfaktor
             'Tlast' : 0                        # ?Zeitpunkt der letzten Regelung?
}

def pi_controller(self, c):
    """
    this function calculates a new actuator value for a given controller

    w    = setpoint value / Führungsgröße (Sollwert)
    x    = current value / Regelgröße (Istwert)
    e    = control error / Regelabweichung
    eSum = sum of error values / Summe der Regelabweichungen
    y    = output to actuator / Stellgröße
    z    = disturbance variable / Störgröße
    Kp   = proportional gain / Verstärkungsfaktor
    Ki   = integral gain / Integralfaktor
    Ta   = scanning time (given in seconds)/ Abtastzeit

    esum = esum + e
    y = Kp * e + Ki * Ta * esum

    p_anteil = error * p_gain;
    error_integral = error_integral + error
    i_anteil = error_integral * i_gain

    :param c: controller for the calculation
    """

    # check if controller is currently deactivated
    if self._controller[c]['stopItems'] is not None and len(self._controller[c]['stopItems']) > 0:
        for i in self._controller[c]['stopItems']:
            item = self._items.return_item(i)
            if item():
                if self._items.return_item(self._controller[c]['actuatorItem'])() > 0:
                    self.logger.info("rtr: controller {0} currently deactivated, because of item {1}".format(c, item.property.path))
                self._items.return_item(self._controller[c]['actuatorItem'])(0)
                self.logger.debug("{0} | skipped because of item {1}".format(c, item.property.path))
                return

    # calculate scanning time
    Ta = int(time.time()) - self._controller[c]['Tlast']
    self.logger.debug("{0} | Ta = Time() - Tlast | {1} = {2} - {3}".format(c, Ta, (Ta + self._controller[c]['Tlast']),
                                                                           self._controller[c]['Tlast']))
    self._controller[c]['Tlast'] = int(time.time())

    # get current and set point temp
    w = self._items.return_item(self._controller[c]['setpointItem'])()
    x = self._items.return_item(self._controller[c]['currentItem'])()

    # skip execution if x is 0
    if x == 0.00:
        self.logger.debug("{0} | skip uninitiated x value (currently zero)".format(c))
        return

    # --- PI Controller calculations - begin

    # calculate control error
    e = w - x
    self.logger.debug("{0} | e = w - x | {1} = {2} - {3}".format(c, e, w, x))

    Kp = 1.0 / self._controller[c]['Kp']
    self._controller[c]['eSum'] = self._controller[c]['eSum'] + e * Ta
    i = self._controller[c]['eSum'] / (60.0 * self._controller[c]['Ki'])
    y = 100.0 * Kp * (e + i);

    # limit the new actuator value to [0 ... 100]
    if y > 100:
        y = 100
        self._controller[c]['eSum'] = (1.0 / Kp) * 60.0 * self._controller[c]['Ki']

    if y < 0 or self._controller[c]['eSum'] < 0:
        if y < 0:
            y = 0
        self._controller[c]['eSum'] = 0

    # --- PI Controller calculations - end

    self.logger.debug("{0} | eSum = {1}".format(c, self._controller[c]['eSum']))
    self.logger.debug("{0} | y = {1}".format(c, y))

    self._items.return_item(self._controller[c]['actuatorItem'])(y)
