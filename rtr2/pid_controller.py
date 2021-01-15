#!/usr/bin/python
#
# This file is part of IvPID.
# Copyright (C) 2015 Ivmech Mechatronics Ltd. <bilgi@ivmech.com>
#
# IvPID is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# IvPID is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# title           :PID.py
# description     :python pid controller
# author          :Caner Durmusoglu
# date            :20151218
# version         :0.1
# notes           :
# python_version  :2.7
# ==============================================================================

"""
Ivmech PID Controller is simple implementation of a Proportional-Integral-Derivative (PID) Controller
in the Python Programming Language.
More information about PID Controller: http://en.wikipedia.org/wiki/PID_controller
"""
import time

class PID:
    """PID Controller
    """

    def __init__(self, Kp=0.2, Ki=0.0, Kd=0.0):

        self._Kp = Kp
        self._Ki = Ki
        self._Kd = Kd

        self.sample_time = 0.00
        self.current_time = time.time()
        self.last_time = self.current_time

        self.clear()

    def clear(self):
        """Clears PID computations and coefficients"""
        self.SetPoint = 0.0

        self.PTerm = 0.0
        self.ITerm = 0.0
        self.DTerm = 0.0
        self.last_error = 0.0

        # Windup Guard
        self.int_error = 0.0
        self.windup_guard = 20.0

        self.output = 0.0

    def update(self, feedback_value):
        """Calculates PID value for given reference feedback

        .. math::
            u(t) = K_p e(t) + K_i \int_{0}^{t} e(t)dt + K_d {de}/{dt}

        .. figure:: images/pid_1.png
           :align:   center

           Test PID with Kp=1.2, Ki=1, Kd=0.001 (test_pid.py)

        """
        error = self.SetPoint - feedback_value

        self.current_time = time.time()
        delta_time = self.current_time - self.last_time
        delta_error = error - self.last_error

        if (delta_time >= self.sample_time):
            self.PTerm = self._Kp * error
            self.ITerm += error * delta_time

            if (self.ITerm < -self.windup_guard):
                self.ITerm = -self.windup_guard
            elif (self.ITerm > self.windup_guard):
                self.ITerm = self.windup_guard

            self.DTerm = 0.0
            if delta_time > 0:
                self.DTerm = delta_error / delta_time

            # Remember last time and last error for next calculation
            self.last_time = self.current_time
            self.last_error = error

            self.output = self.PTerm + (self._Ki * self.ITerm) + (self._Kd * self.DTerm)

    def setWindup(self, windup):
        """Integral windup, also known as integrator windup or reset windup,
        refers to the situation in a PID feedback controller where
        a large change in setpoint occurs (say a positive change)
        and the integral terms accumulates a significant error
        during the rise (windup), thus overshooting and continuing
        to increase as this accumulated error is unwound
        (offset by errors in the other direction).
        The specific problem is the excess overshooting.
        """
        self.windup_guard = windup

    def setSampleTime(self, sample_time):
        """PID that should be updated at a regular interval.
        Based on a pre-determined sampe time, the PID decides if it should compute or return immediately.
        """
        self.sample_time = sample_time

# ===========================================================================================

    @property
    def Kp(self):
        """
        Property: Kp - proportional gain

        Determines how aggressively the PID reacts to the current error with setting Proportional Gain

        :param value: set proportional gain
        :type value: float

        :return: actual proportional gain
        :rtype: float
        """
        return self._Kp

    @Kp.setter
    def Kp(self, value):

        if isinstance(value, int):
            value = float(value)
        if isinstance(value, float):
            self._Kp = value
            return
        else:
            self._type_error('non-float')
            return


    @property
    def Ki(self):
        """
        Property: Ki - integral gain

        Determines how aggressively the PID reacts to the current error with setting Integral Gain

        :param value: set integral gain
        :type value: float

        :return: actual integral gain
        :rtype: float
        """
        return self._Ki

    @Ki.setter
    def Ki(self, value):

        if isinstance(value, int):
            value = float(value)
        if isinstance(value, float):
            self._Ki = value
            return
        else:
            self._type_error('non-float')
            return


    @property
    def Kd(self):
        """
        Property: Kd - derivative gain

        Determines how aggressively the PID reacts to the current error with setting Derivative Gain

        :param value: set derivative gain
        :type value: float

        :return: actual derivative gain
        :rtype: float
        """
        return self._Kd

    @Kd.setter
    def Kd(self, value):

        if isinstance(value, int):
            value = float(value)
        if isinstance(value, float):
            self._Kd = value
            return
        else:
            self._type_error('non-float')
            return


    def __repr__(self):
        return "PID controller"


    def _type_error(self, err):
        import inspect
        prop = inspect.stack()[1][3]
        #self.logger.error("Cannot set property '{}' of item '{}' to a {} value".format(prop, self._item._path, err))
        self.logger.error("Cannot set property '{}' to a {} value".format(prop, err))
        return

