
import time
from mode import *
from temperature import *
from pi_controller import *

class Rtr():

    def __init__(self, plugin):
        self.logger = logging.getLogger(__name__)

        self._ist_temp = 0

        self._mode = Mode()
        self._temp = Temperature(self._mode, {'comfort': '20.x', 'frost': '8.5'})
        # self._pi = Pi_controller(self._temp, 3, 120)
        self._pi = Pi_controller(self._temp)


    def update(self):
        self._pi.update(self._ist_temp)
        return


    # ----------------------------------------------------------------------
    # Methods to update status
    #
    def set_comfort(self, state):
        self._mode.comfort = state
        self._update_mode_items('comfort', state)

    def set_standby(self, state):
        self._mode.standby = state
        self._update_mode_items('standby', state)

    def set_night(self, state):
        self._mode.night = state
        self._update_mode_items('night', state)

    def set_frost(self, state):
        self._mode.frost = state
        self._update_mode_items('frost', state)

    def set_hvac(self, state):
        self._mode.hvac = state
        self._update_mode_items('hvac', state)

    def _update_mode_items(self, ignore_mode, state):
        if ignore_mode != 'comfort':
            pass # set comfort item to self._mode.comfort
        elif ignore_mode != 'standby':
            pass # set standby item to self._mode.standby
        elif ignore_mode != 'night':
            pass # set night item to self._mode.night
        elif ignore_mode != 'frost':
            pass # set frost item to self._mode.frost
        elif ignore_mode != 'hvac':
            pass # set hvac item to self._mode.hvac


    @property
    def heating(self):
        """
        Property: heating state

        :return: actual heating state
        :rtype: bool
        """
        return (self._pi.output >= 1.0)


    def __repr__(self):
        return f"Mode object:\n{self._mode}\n\nTemperature object:\n{self._temp}\n\nPI-controller object:\n{self._pi}"


r = Rtr(plugin=None)
print(r)
print()

r._ist_temp=18.5
s=2
r.update()
print(r._pi)

time.sleep(s)
r.update()
print(r._pi)

r._ist_temp=18.7
time.sleep(s)
r.update()
print(r._pi)

time.sleep(s)
r.update()
print(r._pi)

time.sleep(s)
r.update()
print(r._pi)

r._mode.night=True
time.sleep(s)
r.update()
print(r._pi)

time.sleep(s)
r.update()
print(r._pi)
print('---')
print()

print(r._temp)
r.set_frost(True)
print('--> set to frost')
print(r._temp)
r.set_comfort(True)
print('--> set to comfort')
print(r._temp)
print()
