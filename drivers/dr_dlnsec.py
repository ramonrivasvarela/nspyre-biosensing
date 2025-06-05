# -*- coding: utf-8 -*-
"""
Created on 4/1/2025 by David Ovetsky

Based on Lantz rewrite created by Aidan Jones, Maurer Lab

Adapted from Axel Griesmaier, LABS electronics


"""

## IN ORDER TO USE THIS DRIVER, ENSURE THAT CONDA HAS THE PYSERIAL PACKAGE.
# Check conda list for "pyserial" package. If not, run the following command:
# conda install pyserial

import serial



class DLnsec:
    def __init__(self, *args, **kwargs):
        print('init function')
        self.port = args[0]
        self.pre = None
        self.width = None
        self.laserison = None
        self.modeis = None
        self.powerset = None
        self.t_cycle = None
        self.freq = None

        try:
            self.serial = serial.Serial(port=self.port,baudrate=9600,bytesize=serial.EIGHTBITS,parity=serial.PARITY_NONE,timeout=2)
        except:
            print('Error: Unable to connect to the device.')
            raise
        self.serial.write_timeout = 1
        self.serial.read_timeout = 1

    # def initialize(self):
    #     self.serial = serial.Serial(port=self.port,baudrate=9600,bytesize=serial.EIGHTBITS,parity=serial.PARITY_NONE,timeout=2)
    #     self.serial.write_timeout = 1
    #     self.serial.read_timeout = 1
 
    def finalize(self):
        self.serial.close()

    def write(self,cmd):
        self.serial.write(cmd + b'\n')

    def read(self, cmd):
        self.serial.write(cmd + b'\n')
        answer = self.serial.readline().strip().decode()
        self.serial.read()
        return answer

    def on(self):
        self.write(b'*ON')
        self.laserison = 1

    def off(self):
        self.write(b'*OFF')
        self.laserison = 0

    def LAS(self):
        self.write(b'LAS')

    def EXT(self):
        self.write(b'EXT')

    def reboot(self):
        self.write(b'*RBT')

    def idn(self):
        answer = self.read(b'*IDN')
        return str(answer)

    def power_settings(self):
        answer = self.read(b'PWR?')
        print('answer:', answer)
        print(type(answer))
        self.powerset = int(answer)
        return int(answer)
        #import pdb; pdb.set_trace()
        # print('power settings:')
        # self.serial.write(b'PWR?\n')
        # resp = self.serial.readline()
        # print('response: {}'.format(resp))
        # self.PWR = resp.strip().decode()
        # return int(self.PWR)
        #return self.read(b'PWR?')
        #print(self.read(b'PWR?'))
        #print(type(self.read(b'PWR?')))
        # print(str(self.read('PWR?')))
        # print(type(str(self.read('PWR?'))))
        #print(self.serial.read(50))
        #print(type(self.serial.read(50)))
        #return self.read(b'PWR?')
        #return self.serial.readline().strip().decode()
        
    def power_settings(self, value):
        strn = 'PWR' + '{:0d}'.format(int(value))
        print(strn)
        self.write(strn.encode())

    # def set_mode(self, mode):
        # assert mode in ['LAS', 'INT', 'EXT', 'STOP']
        # self.write(bytes(mode, encoding='utf-8')+b'')
        # self.modeis = mode
    # def set_width(self, width):
        # assert type(width) == int
        # assert width >=0
        # assert width <=255
        # self.width = width
        # self.write(b'WID %i'%int(width))
        # self.t_width = 1/16e6*self.pre*(width+1)
    # def set_prescaler(self, pre):
        # assert type(pre) == int
        # assert pre in [1, 8, 64, 256, 1024]
        # self.pre = pre
        # self.write(b'PRE %i'%int(pre))
        # self.freq = 16e6/256/pre
        # self.t_cycle = 1 / self.freq

    # def query(self, attr):
        # self.serial.write('{}\n'.format(attr).encode('ASCII'))
        # resp = self.serial.readline()
        # print('response: {}'.format(resp))
        # self.PWR = resp.strip().decode()
  
    # def read(self, cmd):
        # print('cmd:')
        # print(cmd)
        # self.serial.write(cmd + b'\n')
        # #self.serial.read()
        # answer = self.serial.readline().decode().strip()
        # print('answer:')
        # print(answer)
        # print(type(answer))
        # return str(answer)
        
    # def on(self):
        # self.write(b'*ON')
        # self.laserison = 1
    # def off(self):
        # self.write(b'*OFF')
        # self.laserison = 0
    # @Feat(values={False: '0', True: '1'})
    # def on_off(self):
        # return self.laserison

    # @on_off.setter
    # def on_off(self, value):
        # self.laserison = value
        # self.write(b'*{}'.format("ON" if value else "OFF"))
       

    # @Feat()
    # def idn(self):
        # return self.id
        # #return self.read(b'*IDN')       
        
    # @DictFeat(units='W', keys={'photodiode', 'pd', 'thermopile', 'tp', 'power meter'})
    # def ld_power(self, method):
        # query = 'MEAS:POW{}?'
        # ml = method.lower()
        # if ml in {'photodiode', 'pd'}:
            # method_val = 2
        # elif ml in {'thermopile', 'tp', 'power meter'}:
            # method_val = 3
        # return float(self.query(query.format(method_val)))
        
    # def set_power(self,pwr):
        # strn = 'PWR' + '{:0d}'.format(pwr)
        # self.write(strn.encode())
        # self.get_power()
    # def get_power(self):
        # answer = self.read(b'PWR?')
        # self.powerset = int(answer)
        # return int(answer)
        
        
    # @Feat(values = {'LAS', 'INT', 'EXT', 'STOP'})
    # def mode(self):
        # return self.modeis
        
    # @mode.setter
    # def mode(self, mode):
        # self.serial.write(bytes(mode, encoding='utf-8')+b'')
        # self.modeis = mode
        
    # # def set_mode(self, mode):
        # # assert mode in ['LAS', 'INT', 'EXT', 'STOP']
        # # self.write(bytes(mode, encoding='utf-8')+b'')
        # # self.modeis = mode
        
    # @Feat()
    # def width(self):
        # return self.width
        
    # @width.setter
    # def width(self, width):
        # #self.width = width
        # #self.write(b''+'WID {}'.format(int(width)))
        # self.serial.write(b'WID %i'%int(width))
        # self.t_width = 1/16e6*self.pre*(width+1)
        
        
        
    # # def set_width(self, width):
        # # assert type(width) == int
        # # assert width >=0
        # # assert width <=255
        # # self.width = width
        # # self.write(b'WID %i'%int(width))
        # # self.t_width = 1/16e6*self.pre*(width+1)
        
    # @Feat(values = {1, 8, 64, 256, 1024})
    # def prescaler(self):
        # return self.pre
        
    # @prescaler.setter
    # def prescaler(self, pre):
        # #self.write(b'PRE {}'.format(int(pre)))
        # self.serial.write(b'PRE %i'%int(pre))
        # self.freq = 16e6/256/pre
        # self.t_cycle = 1 / self.freq
        # self.pre = pre
        
    # # def set_prescaler(self, pre):
        # # assert type(pre) == int
        # # assert pre in [1, 8, 64, 256, 1024]
        # # self.pre = pre
        # # self.write(b'PRE %i'%int(pre))
        # # self.freq = 16e6/256/pre
        # # self.t_cycle = 1 / self.freq
        
