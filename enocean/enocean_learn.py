#!/usr/bin/env python3
# enocean_learn.py

'''
Logic for trigger the enocean learn method.
This method has to be used to leran in new actors into SHNG when using the enocean plugin.
Actually the following device codes are available:

- 10: Eltako Switch FSR61, Eltako FSVA-230V
- 20: Eltako FSUD-230V
- 21: Eltako FHK61SSR dim device (EEP A5-38-08)
- 22: Eltako FRGBW71L RGB dim devices (EEP 07-3F-7F)
- 30: Radiator Valve
- 40: Eltako shutter actors FSB61NP-230V, FSB14, FSB61, FSB71

Usage:
1.) please fill in the correct values for id_offset and device
2.) copy the file to the SHNG folder: logics
3.) Do the following entry in the file: ./etc/locic.yaml
    enocean_learn:
        enabled: false
        filename: enocean_learn.py

OR
copy make a new logic via SHNG backend and copy the complete code inside the new logic.

When finished you can trigger the logic ones via backend to lern in your specific actuator.
'''
# =====================================
# ### --- General Learn Routine --- ###
# =====================================
'''
send_learn_protocol(self, id_offset=0, device=10)
'''
sh.enocean.send_learn_protocol(0, 10)


# =================================
# ### --- UTE Learn Routine --- ###
# =================================
'''
start_UTE_learnmode(self, id_offset=0)
'''
#start_UTE_learnmode(0)


# ====================================
# ### --- Smart Act Learn Mode --- ###
# ====================================
'''
This function enables/disables the controller's smart acknowledge mode
set_smart_ack_learn_mode(self, onoff=1)
'''
#set_smart_ack_learn_mode(self, onoff=1)