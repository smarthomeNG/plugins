
import logging
import time

_defaults = {'currentItem' : None,              # used: to get x = current value
             'setpointItem' : None,             # used: to get w = setpoint value
             'actuatorItem' : None,             # used: to get actuator item to write the output (correcting value) y to
             'stopItems' : None,                # used: to disable the controller
}

class Pi_controller():

    def __init__(self, temperature, Kp=10, Ki=15):
        self.logger = logging.getLogger(__name__)

        self._temperature = temperature
        self.logger.info(f"PI-controller.__init__: temp={temperature.set_temp}, Kp={Kp}, Ki={Ki}")
        self.controller_type = 'PI'

        self._set_temp = self._temperature.set_temp   # setpoint value
        self._Kp = Kp               # Verstärkungsfaktor
        self._Ki = Ki               # Integralfaktor
        self._eSum = 0              # Summe der Regelabweichungen

        self.current_time = time.time()
        self.last_time = self.current_time
        self.last_input = None
        self.output = 0.0


    def update(self, feedback_value, set_temp=None):
        """
        this function calculates a new actuator value

        w    = setpoint value / Führungsgröße (Sollwert)
        x    = current value / Regelgröße (Istwert)
        e    = control error / Regelabweichung
        eSum = sum of error values / Summe der Regelabweichungen
        y    = output to actuator / Stellgröße
        Kp   = proportional gain / Verstärkungsfaktor
        Ki   = integral gain / Integralfaktor
        Ta   = scanning time (given in seconds)/ Abtastzeit

        esum = esum + e
        y = Kp * e + Ki * Ta * esum

        p_anteil = error * p_gain;
        error_integral = error_integral + error
        i_anteil = error_integral * i_gain

        """
        self._set_temp = self._temperature.set_temp   # setpoint value

        # calculate scanning time
        self.current_time = time.time()
        Ta = self.current_time - self.last_time
        self.logger.debug(f"Ta = Time() - Tlast | {Ta} = {self.current_time} - {self.last_time}")
        self.last_time = self.current_time

        # get current and set point temp
        w = self._set_temp
        if (self.last_input is None) and (feedback_value == 0):
            return
        self.last_input = feedback_value
        x = feedback_value

        # --- PI Controller calculations - begin

        # calculate control error
        e = w - x
        self.logger.debug(f"e = w - x | {e} = {w} - {x}")

        Kp = 1.0 / self._Kp
        self._eSum = self._eSum + e * Ta
        i = self._eSum / (60.0 * self._Ki)
        y = 100.0 * Kp * (e + i)

        # limit the new actuator value to [0 ... 100]
        if y > 100:
            y = 100
            self._eSum = (1.0 / Kp) * 60.0 * self._Ki

        if y < 0 or self._eSum < 0:
            if y < 0:
                y = 0
            self._eSum = 0

        # --- PI Controller calculations - end

        self.logger.debug(f"eSum = {self._eSum}")
        self.logger.debug(f"y = {y}")

        self.output = round(y, 2)
        self.logger.debug(f"PI-controller.update: control_output={self.output}, actual={feedback_value}, set_temp={self._set_temp}")
        return self.output


    def __repr__(self):
        return f"{self.controller_type}-controller, set_temp={self._set_temp}, Kp={self._Kp}, Ki={self._Ki}, eSum={round(self._eSum,4)}, output={round(self.output,2)}, last_input={self.last_input}"


# =============================================================================================================
# =============================================================================================================
# =============================================================================================================

def old_pi_controller(self, c):
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

