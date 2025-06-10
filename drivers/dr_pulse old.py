"""
Created on 5/30/2025 by Ramon Rivas
"""
import numpy as np
import pandas as pd
from math import sin, cos, radians, lcm

#import matlab.engine #import matlab.egnine
import subprocess
#from threed.data_and_plot import save_excel
import datetime as Dt


from lantz.core import Driver
from lantz.drivers.swabian.pulsestreamer.lib.pulse_streamer_grpc import PulseStreamer,OutputState
#from lantz.drivers.swabian.pulsestreamer.lib.sequence import Sequence
from lantz.drivers.swabian.pulsestreamer.lib.Sequence import Sequence
#from lantz.drivers.swabian.pulsestreamer.grpc.pulse_streamer_grpc import PulseStreamer
#from lantz.drivers.swabian.pulsestreamer.sequence import Sequence
from lantz import Q_
from lantz import Action, Feat, DictFeat, ureg



class Pulses(Driver):

    
    #default_digi_dict = {"laser": "ch0", "offr_laser": "ch1", "EOM": "ch4", "CTR": "ch5", "switch": "ch6", "gate": "ch7", "": None}
    #default_digi_dict = {"laser": 0, "blue": 1, "SRS": 2, "VSG":3, "gate1": 4, "gate2": 5, "gate3": 6, "gate4": 7, "": None}
    #default_digi_dict = {"gate4": 0, "blue": 1, "SRS": 2, "VSG":3, "gate1": 4, "gate2": 5, "gate3": 6, "laser": 7, "": None}
    default_digi_dict = {"clock": 0, "blue": 1, "SRS": 2, "VSG":3, "gate1": 4, "gate2": 5, "gate3": 6, "laser": 7, "": None}
    rev_dict = {0: "clock", 1: "blue", 2: "SRS", 3: "VSG", 4: "gate1", 5: "gate2", 6: "gate3", 7: "laser", 8: "I", 9: "Q"}
    #rev_dict = {0: "laser", 1: "blue", 2: "SRS", 3: "VSG", 4: "gate1", 5: "gate2", 6: "gate3", 7: "gate4", 8: "I", 9: "Q"}
    
## Should change aom to laser
    def __init__(self, channel_dict = default_digi_dict, rev_dict = rev_dict, laser_time = 3.5*Q_(1,"us"), 
                 laser_lag = .073*Q_(1,"us"), aom_ramp = .15*Q_(1,"us"), readout_time = .4*Q_(1,"us"), 
                 laser_buf = .100*Q_(1,"us"), read_time = 50*Q_(1, "us"), clock_time = Q_(0.1, "us"),
                 IQ=[.4,0], ip="10.135.70.127"):
        """
        :param channel_dict: Dictionary of which channels correspond to which instr controls
        :param readout_time: Laser+gate readout time in us
        :param laser_time: Laser time to reinit post readout
        :param aom_lag: Delay in AOM turning on
        :param laser_buf: Buffer after laser turns off
        :param IQ: IQ modulation/analog channels
        """
        super().__init__()
        
        # parameters for all sequences
        self.channel_dict = {"clock": 0, "camera": 1, "405": 2, "488":3, "647": 4, "mirror": 5, "switch": 6, "laser": 7, "": None}
        self._reverse_dict = rev_dict
        self.laser_time = int(round(laser_time.to("ns").magnitude))
        self.laser_lag = int(round(laser_lag.to("ns").magnitude))
        self.readout_time = int(round(readout_time.to("ns").magnitude))
        self.laser_buf = int(round(laser_buf.to("ns").magnitude))# is this ever used?
        self.read_time = int(round(read_time.to("ns").magnitude))
        self.clock_time = int(round(clock_time.to("ns").magnitude))
        self.total_time = 0 #update when a pulse sequence is streamed
        
        # create pulse streamer instance
        self.Pulser = PulseStreamer(ip)
        self.sequence = self.Pulser.createSequence()
        self.sub_sequence = self.Pulser.createSequence()
        #self.latest_streamed = pd.DataFrame({})
        
## Should change it according to crosstalk between I and Q. If no crosstalk should be 0.5 and 0
        
        #note: IQ
        #optimized for 720MHz for CdSe
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

        ##Needs to be tested
        self.IQplus = [1,0]
        self.IQminus = [-1,0]
        
        # #commented out 20220828
        # self.IQ0 = [-0.0033,-0.0033]#[-.0231,-0.00815]#[-.0177,-.0045]
        # self.IQ = self.IQ0
        # self.IQpx = [0.4461,-.0033]#[0.4,-.005]
        # self.IQnx = [-0.4922,-0.0082]#[-.435,-.0045]
        # self.IQpy = [-0.0231,0.4772]#[-.0178,.4195]
        # self.IQny = [-2.31E-02, -0.4838]
        # self.IQboth = [0.4355, 0.4667]
        # self.IQtest = [.95, 0]
        
        # self.IQ0 = [-0.0028,-0.0028]#[-.0231,-0.00815]#[-.0177,-.0045]
        # self.IQ = self.IQ0
        # self.IQpx = [0.4461,-.0028]#[0.4,-.005]
        # self.IQnx = [-0.4922,-0.0082]#[-.435,-.0045]
        # self.IQpy = [-0.0231,0.4772]#[-.0178,.4195]
        # self.IQny = [-2.31E-02, -0.4838]
        # self.IQboth = [0.4355, 0.4667]
        # self.IQtest = [.95, 0]
        
    ### We use the following to make sidebands work:
    
    
    def has_sequence(self):
        """
        Has Sequence
        """
        return self.Pulser.hasSequence()
    

    def laser_on(self, index, q=0.0, i=0.0):
        return self.Pulser.constant((index, q, i))
    
    def laser_off(self, index):
        return self.Pulser.constant((index, -1, 0))


    # def stream(self,seq,n_runs, leave_laser_on = False):
    #     if(leave_laser_on):
    #         self.Pulser.stream(seq,n_runs,final = OutputState([3],0,0))
    #     else:
    #         self.Pulser.stream(seq,n_runs,final = OutputState([],0,0))

    def stream(self,seq,n_runs):
        self.Pulser.stream(seq,n_runs)



