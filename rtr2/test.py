
from mode import *
from temperature import *

m = Mode()
t = Temperature(m, {'comfort': '20.x', 'frost': '8.5'})

#self._night_reduction = init.get('night_reduction', 3.0)
#self._standby_reduction = init.get('standby_reduction', 1.5)
#self._fixed_reduction = init.get('fixed_reduction', True)


def test_set_temp():
    t._fixed_reduction = True
    print('t._fixed_reduction =', t._fixed_reduction)
    print('t.comfort =',t.comfort)
    print(t)
    print()
    t.comfort = 22
    print('t.comfort =',t.comfort)
    print(t)
    print()
    t.comfort = 20
    #
    print('t.comfort =',t.comfort, 't.standby =',t.standby)
    print(t)
    print()
    t.standby = 20.5
    print('t.comfort =',t.comfort, 't.standby =',t.standby)
    print(t)
    print()
    #
    print('t.comfort =',t.comfort, 't.standby =',t.standby, 't.night =',t.night)
    print(t)
    print()
    t.night = 15
    print('t.comfort =',t.comfort, 't.standby =',t.standby, 't.night =',t.night)
    print(t)
    print()
    #
    print('t.comfort =',t.comfort, 't.standby =',t.standby, 't.night =',t.night, 't.frost =',t.frost)
    print(t)
    print()
    t.frost = 8.5
    print('t.comfort =',t.comfort, 't.standby =',t.standby, 't.night =',t.night, 't.frost =',t.frost)
    print(t)
    print()
    #
    m.comfort = True
    print(t.set_temp, f' ({m})')
    m.standby = True
    print(t.set_temp, f' ({m})')
    m.night = True
    print(t.set_temp, f' ({m})')
    m.frost = True
    print(t.set_temp, f' ({m})')
    m.frost = False
    print(t.set_temp, f' ({m})')
    print()
    print(t)
    return

defaults = {'comfort': '21', 'frost': '8', 'standby_reduction': '1', 'night_reduction': '2', 'fixed_reduction': True}

t = Temperature(m)
print(t)

t = Temperature(m, defaults=defaults)
print(t)

init = {'comfort': '20.x', 'frost': '8.5', 'fixed_reduction': True}
t = Temperature(m, init, defaults)
print(t)

init = {'comfort': '20.x', 'frost': '8.5', 'fixed_reduction': False}
t = Temperature(m, init, defaults)
print(t)

#test_set_temp()
