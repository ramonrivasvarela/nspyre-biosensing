"""
Created on 8/3/2026 by David Ovetsky
"""

from pycobolt import Cobolt06MLD as Laser

class Cobolt488:

    COM = 'COM3'
    MODES = {
        "0": "0 - Constant Current",
        "1": "1 - Constant Power",
        "2": "2 - Modulation Mode",
    }
    STATES = {
            "0": "0 - Off",
            "1": "1 - Waiting for key",
            "2": "2 - Continuous",
            "3": "3 - On/Off Modulation",
            "4": "4 - Modulation",
            "5": "5 - Fault",
            "6": "6 - Aborted",
        }

    POWER_RANGE = [0, 112]  # in mW 
    CURRENT_RANGE = [0, 160]  # in mA 

    def __init__(self, *args, **kwargs):
        print('Connecting to Cobolt 488 laser')
        self.laser = Laser(port = self.COM)

        self.connected = self.laser.is_connected()
        # self.mode = self.laser.get_mode()
        # self.continuous_power = self.laser.get_power_setpoint()
        # self.modulation_power = self.laser.get_modulation_power()



    def is_connected(self):
        return self.laser.is_connected()

    def connect(self):
        if not self.connected:
            self.laser.connect()
            self.connected = self.laser.is_connected()
        return self.connected

    def disconnect(self):
        if self.connected:
            self.laser.disconnect()
            self.connected = False
        return not self.connected

    def check_on(self):
        return self.laser.is_on()

    def get_state(self):
        '''
        returns a string:
        '0 - Off'
        '1 - Waiting for key'
        '2 - Continuous'
        '3 - On/Off Modulation'
        '4 - Modulation'
        '5 - Fault'
        '6 - Aborted'
        '''
        self.state = self.laser.get_state()
        return self.state

    ## ON-OFF requires key. Prefer switching between modulation mode and constant power mode. 
    # def turn_on(self):
    #     if not self.check_on():
    #         self.laser.turn_on()
    #     return self.check_on()

    # def turn_off(self):
    #     if self.check_on():
    #         self.laser.turn_off()
    #     return not self.check_on()

    def get_mode(self):
        '''
        returns a string:
        '0 - Constant Current'
        '1 - Constant Power'
        '2 - Modulation Mode'
        '''
        self.mode = self.laser.get_mode()
        return self.mode

    ## CONSTANT CURRENT COMMANDS ##########################
    # def constant_current(self, current):
    #     '''
    #     current mA, enters constant current mode

    #     returns 'OK' if successful.
    #     '''
    #     return self.laser.constant_current(current)
    
    ## Also see commands get_current and set_current. Also get_current_setpoint/

    ###########################################################

    ## CONSTANT POWER (CONTINUOUS) COMMANDS ##########################
    def constant_power(self, power):
        '''
        power mW, enters constant power mode

        returns 'OK' if successful.
        '''
        return self.laser.constant_power(power)

    def set_power(self, power):
        '''
        power mW, sets the power in constant power mode

        returns 'OK' if successful.
        '''
        return self.laser.set_power(power)

    def get_power(self):
        '''
        returns the power in mW
        '''
        return self.laser.get_power()

    def get_power_setpoint(self):
        '''
        returns the power setpoint in mW
        '''
        return self.laser.get_power_setpoint()
    ##########################################################

    ## MODULATION MODE COMMANDS ##########################

    def modulation_mode(self, power):
        '''
        enters modulation mode

        power mW, sets the power in modulation mode

        returns 'OK' if successful.
        '''
        return self.laser.modulation_mode(power)

    def set_modulation_power(self, power):
        '''
        power mW, sets the modulation power in modulation mode

        returns 'OK' if successful.
        '''
        return self.laser.set_modulation_power(power)

    def get_modulation_power(self):
        '''
        returns the modulation power setpoint in mW
        '''
        return self.laser.get_modulation_power()


    