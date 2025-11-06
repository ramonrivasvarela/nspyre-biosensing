import serial
from serial.tools import list_ports
from serial import SerialException
import time
import sys
import os

class CoboltLaser():
    '''Creates a laser object using either COM-port or serial number to connect to laser. \n Will automatically return proper subclass, if applicable'''
    
    def __init__(self, *args, **kwargs):
        #super.__init__(*args, **kwargs)
        self.serialnumber=None
        self.port=args[0]
        self.modelnumber = None
        self.baudrate=115200
        self.adress=None
        self.connect()
    
    def __str__(self):
        try:
            return f'Serial number: {self.serialnumber}, Model number: {self.modelnumber}, Wavelength: {"{:.0f}".format(float(self.modelnumber[0:4]))} nm, Type: {self.__class__.__name__}'
        except:
            return f'Serial number: {self.serialnumber}, Model number: {self.modelnumber}'
    
    def connect(self): 
        '''Connects the laser on using a specified COM-port (preferred) or serial number. \n Will throw exception if it cannot connect to specified port or find laser with given serial number'''
        
        if self.port!= None:
            try:
                self.adress=serial.Serial(self.port,self.baudrate, timeout=1)
            except Exception as error:
                self.adress=None
                raise SerialException (f'{self.port} not accesible. Error: {error}')
        

        elif self.serialnumber!= None : 
            ports=list_ports.comports()
            for port in ports:
                try:
                    self.adress=serial.Serial(port.device,baudrate=self.baudrate, timeout=1)
                    sn=self.send_cmd('sn?')
                    self.adress.close()
                    if sn == self.serialnumber:
                        self.port=port.device
                        self.adress=serial.Serial(self.port,baudrate=self.baudrate)
                        break    
                except:
                    pass             
            if self.port==None:
                raise Exception('No laser found')
        if self.adress!=None:
            self._identify_()
        if self.__class__==CoboltLaser:
            self._classify_()



    def _identify_(self): 
        """Fetch Serial number and model number of laser. \n
        Will raise exception and close connection if not connected to a cobolt laser"""
        try:
            firmware = self.send_cmd('gfv?')
            if 'ERROR' in firmware:
                self.disconnect()
                raise Exception('Not a Cobolt laser')
            self.serialnumber = self.send_cmd('sn?') 
            if not '.' in firmware: 
                if '0' in self.serialnumber: 
                    self.modelnumber=f'0{self.serialnumber.partition(str(0))[0]}-04-XX-XXXX-XXX'
                    self.serialnumber=self.serialnumber.partition('0')[2] 
                    while self.serialnumber[0]=='0':
                        self.serialnumber=self.serialnumber[1:]                   
            else:
                self.modelnumber=self.send_cmd('glm?')
        except:
            self.disconnect()
            raise Exception('Not a Cobolt laser')

    def _classify_(self):
        '''Classifies the laser into probler subclass depending on laser type'''
        try:
            if '-06-' in self.modelnumber:
                if '532' in self.modelnumber[0:4] or '561' in self.modelnumber[0:4] or '553' in self.modelnumber[0:4]:
                    self.__class__=Cobolt06DPL
                else:
                    self.__class__=Cobolt06MLD
        except:
            pass
            
    def is_connected(self): 
        """Ask if laser is connected"""
        if self.adress.is_open:
            try:
                test=self.send_cmd('?')
                if test=='OK':
                    return True
                else:
                    return False
            except:
                return False
        else:
            return False
    
         
    def turn_on(self):
        '''Turn on the laser with the autostart sequence.The laser will await the TEC setpoints and pass a warm-up state'''
        self.send_cmd(f'@cob1') 
        return self.send_cmd(f'l?')

    def turn_off(self):
        '''Turn off the laser '''
        self.send_cmd(f'l0')        
        return self.send_cmd(f'l?')
        
    def is_on(self):
        '''Ask if laser is turned on '''
        answer=self.send_cmd(f'l?') 
        print(answer)
        if answer == '1':
            return True
        else:
            return False

    def interlock(self):
        '''Returns: 0 if closed, 1 if open '''
        return self.send_cmd(f'ilk?')

    def get_fault(self):
        '''Get laser fault'''
        faults={'0': '0 - No errors',
        '1':'1 – Temperature error',
        '3':'3 - Interlock error',
        '4':'4 – Constant power time out'}
        fault=self.send_cmd(f'f?')
        return faults.get(fault,fault)

    def clear_fault(self):
        '''Clear laser fault'''
        self.send_cmd(f'cf')
    
    def get_mode(self):
        '''Get operating mode'''
        modes={'0': '0 - Constant Current',
        '1': '1 - Constant Power',
        '2':'2 - Modulation Mode'}
        mode=self.send_cmd(f'gam?')
        return modes.get(mode,mode)

    def get_state(self): 
        '''Get autostart state'''
        states={'0':'0–Off',
        '1':'1 – Waiting for key',
        '2':'2 – Continuous',
        '3':'3 – On/Off Modulation',
        '4':'4 – Modulation',
        '5':'5 – Fault',
        '6':'6 – Aborted'}
        state=self.send_cmd(f'gom?')
        return states.get(state,state)
   
    def get_key_state(self):
        return self.send_cmd(f'@cobasks')
    
    def constant_current(self):
        '''Enter constant current mode, current in mA ''' 
        self.send_cmd(f'ci')
        
    def current(self):
        '''Get laser current in mA '''
        return float(self.send_cmd(f'i?'))
        
    def current(self, current):
        '''Set laser current in mA'''
        self.send_cmd(f'slc {current}')

    def current_setpoint(self):
        '''Get laser current setpoint in mA '''
        return float(self.send_cmd(f'glc?'))

    def constant_power(self):
        '''Enter constant power mode, power in mW''' 
        self.send_cmd(f'cp')
        
    def power(self):
        ''' Get laser power in mW'''
        return float(self.send_cmd(f'pa?'))*1000   

    def power(self, power):
        '''Set laser power in mW '''
        self.send_cmd(f'p {float(power)/1000}')
     
    def power_setpoint(self):
        ''' Get laser power setpoint in mW'''
        return float(self.send_cmd(f'p?'))*1000    

    def get_ophours(self):
        ''' Get laser operational hours'''
        return self.send_cmd(f'hrs?')

    
    def _timeDiff_( self, time_start ):
        '''time in ms'''
        time_diff = ( time.perf_counter() - time_start )
        return time_diff


    def send_cmd( self, message, timeout = 1 ):
        """ Sends a message to the laset and awaits response until timeout (in s).

            Returns: \n
                The response recieved from the laser is string format or\n
                "Syntax Error: No response" on a failed attempt,\n
                "Syntax Error: Write failed" if no connection is available\n
        """
        time_start = time.perf_counter()
        message += "\r"
        try:
            self.adress.write(message.encode() )
        except: 
            return 'Error: write failed'


        time_stamp = 0
        while ( time_stamp < timeout ):

            try:
                received_string = self.adress.readline().decode()
                time_stamp = self._timeDiff_( time_start )
            except:
                time_stamp = self._timeDiff_( time_start )
                continue


            if ( len( received_string ) > 1 ):
                while ( ( received_string[ -1 ] == '\n' ) or ( received_string[ -1 ] == '\r' ) ):
                    received_string = received_string[ 0 : -1 ]
                    if ( len( received_string ) < 1 ):
                        break
                
                return  received_string

        return "Syntax Error: No response"

class Infrared(CoboltLaser):
    '''For lasers of type 06-MLD'''
    def __init__(self,port,serialnumber=None):
        super().__init__(port,serialnumber)


    def modulation_mode(self):
        '''Enter modulation mode with the possibility  to set modulation power in mW'''
        return self.send_cmd(f'em')
    
    def modulation_power(self):
        return self.send_cmd(f"glmp?")
        
    def modulation_power(self, pwr):
        self.send_cmd(f'slmp {pwr}')
    
    def digital_modulation(self):
        return self.send_cmd(f'gdmes?')
        
    def digital_modulation(self,enable):
        '''Enable digital modulation mode by enable=1, turn off by enable=0'''
        self.send_cmd(f'sdmes {enable}')

    def analog_modulation(self):
        return self.send_cmd(f'games?')
        

    def analog_modulation(self,enable):
        '''Enable analog modulation mode by enable=1, turn off by enable=0''' 
        self.send_cmd(f'sames {enable}')
    
    # def on_off_modulation(self,enable):
        # '''Enable On/Off modulation mode by enable=1, turn off by enable=0'''
        # if enable==1:
            # return self.send_cmd('eoom')
        # elif enable==0:
            # return self.send_cmd('xoom')

    def analog_impedance(self):
        '''Get the impedance of the analog modulation \n
        return: 0 for HighZ and 1 for 50 Ohm '''
        return self.send_cmd(f'galis?')
        
    def analog_impedance(self,arg):
        '''Set the impedance of the analog modulation by \n
        arg=0 for HighZ and \n
        arg=1 for 50 Ohm '''
        self.send_cmd(f'salis {arg}')