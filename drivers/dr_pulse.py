"""
Created on 5/30/2025 by Ramon Rivas
"""
import numpy as np
from math import sin, cos, radians, lcm
#from threed.data_and_plot import save_excel
import datetime as Dt

#REQUIRED IMPORT
from pulsestreamer import PulseStreamer, OutputState, Sequence



class dr_ps():


    
## Should change aom to laser
    def __init__(self, ip="10.135.70.127"):


        
        # create pulse streamer instance
        self.Pulser = PulseStreamer(ip)
        self.sequence = self.Pulser.createSequence()
        self.sub_sequence = self.Pulser.createSequence()
        
## Should change it according to crosstalk between I and Q. If no crosstalk should be 0.5 and 0
        
        #note: IQ
        self.IQ0 = [-0.0025,-0.0025]#[-.0231,-0.00815]#[-.0177,-.0045]
        self.IQ = self.IQ0
        self.IQpx = [0.4461,-.0025]#[0.4,-.005]
        self.IQnx = [-0.4922,-0.0025]#[-.435,-.0045]
        self.IQpy = [-0.0025,0.4772]#[-.0178,.4195]
        self.IQny = [-0.0025, -0.4838]
        self.IQboth = [0.4355, 0.4667]
        self.IQtest = [.95, 0]
        self.IQleft = [0.355, 0.348]
        self.IQright = [0.357, 0.350]

    
    
    def has_sequence(self):
        """
        Has Sequence
        """
        return self.Pulser.hasSequence()
    

    def set_state(self, dig_chan, q=0.0, i=0.0):
        return self.Pulser.constant((dig_chan, q, i))
    
    def set_state_off(self):
        return self.Pulser.constant(([], 0, 0))

    def stream(self, duration:int, dig_chan:list, i:float=0, q:float=0, n_runs:int=1):
        pulse = [(duration, dig_chan, i, q)]
        self.Pulser.stream(pulse, n_runs)

    def flip_mirror(self, output=[], i=0, q=0, n_runs=1):
        pulse = [(1000000, [5], 0, 0)]
        self.Pulser.stream(pulse, n_runs, final=OutputState(output, i, q))




