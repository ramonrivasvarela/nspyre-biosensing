import numpy as np
import pandas as pd
from math import sin, cos, radians, lcm
import matplotlib.pyplot as plt
#import matlab.engine #import matlab.egnine
import subprocess
#from threed.data_and_plot import save_excel
import datetime as Dt
import openpyxl

from lantz.core import Driver
from lantz.drivers.swabian.pulsestreamer.lib.pulse_streamer_grpc import PulseStreamer,OutputState
#from lantz.drivers.swabian.pulsestreamer.lib.sequence import Sequence
from lantz.drivers.swabian.pulsestreamer.lib.Sequence import Sequence
#from lantz.drivers.swabian.pulsestreamer.grpc.pulse_streamer_grpc import PulseStreamer
#from lantz.drivers.swabian.pulsestreamer.sequence import Sequence
from lantz import Q_
from lantz import Action, Feat, DictFeat, ureg



class newPulses(Driver):

    
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
    
    
    @Feat()
    def has_sequence(self):
        """
        Has Sequence
        """
        return self.Pulser.hasSequence()
    
    @Action()
    def laser_on(self):
        return self.Pulser.constant(([7], 0.0, 0.0))


    # def stream(self,seq,n_runs, leave_laser_on = False):
    #     if(leave_laser_on):
    #         self.Pulser.stream(seq,n_runs,final = OutputState([3],0,0))
    #     else:
    #         self.Pulser.stream(seq,n_runs,final = OutputState([],0,0))

    def stream(self,seq,n_runs):
        self.Pulser.stream(seq,n_runs)

    def stream_umOFF(self,seq,n_runs,AM = True, SWITCH = True): #for shutting off the microwave via AM and Switch
        digital_set = []
        if SWITCH:
            digital_set.append(self.channel_dict['switch'])
        analog_set = 0
        if AM:
            analog_set = -1
        self.Pulser.stream(seq,n_runs, final = OutputState(digital_set, analog_set,0))


    def clocksource(self,clk_src):
        self.Pulser.selectClock(clk_src)

    def _normalize_IQ(self, IQ): ####what is this for???
        self.IQ = IQ/(2.5*np.linalg.norm(IQ))

### convert sequence was here--> maybe need to write a different function to save the sequence to the data frame###

    #There were commented versions in the original pulses driver (including uri sweep unknown). Remember to check    
    def MWSweepPattern(self, params, pi):
        latest_time = params[-1]
        pi_ns = int(round(pi.to('ns').m))
        seq = []
        mwSweep = Sequence()
        patternLaser =   [(self.aom_lag, 1), (self.laser_time - self.aom_lag, 1)]
        patternMW0   =   [(self.aom_lag + self.laser_time + self.singlet_decay, self.IQ0[0]),
                          (pi_ns, self.IQpx[0]), (latest_time + self.read_time + self.clock_time - self.aom_lag - self.laser_time - self.singlet_decay - pi_ns, self.IQ0[0])]
        patternMW1   =   [(self.aom_lag + self.laser_time + self.singlet_decay, self.IQ0[1]), 
                          (pi_ns, self.IQpx[1]), (latest_time + self.read_time + self.clock_time - self.aom_lag - self.laser_time - self.singlet_decay - pi_ns, self.IQ0[1])]
        for k, start_time in enumerate(params):
            patternClock = [(start_time, 0), (self.clock_time, 1), (self.read_time - self.clock_time, 0), (self.clock_time, 1)]
            if start_time >= self.laser_time:
                patternLaser += [(start_time - self.laser_time - self.aom_lag, 0), (self.aom_lag, 1), (self.read_time - self.aom_lag, 1), (self.aom_lag, 0)]
                
            mwSweep.setDigital(self.channel_dict["clock"], patternClock)
            mwSweep.setDigital(self.channel_dict['laser'], patternLaser)
            mwSweep.setAnalog(0, patternMW0)
            mwSweep.setAnalog(1, patternMW1)
            
            seq += mwSweep
            
        self.total_time = self.aom_lag + self.laser_time + self.singlet_decay + pi_ns + latest_time + self.read_time + self.clock_time
        return seq    
            
    def CWUriMRnew(self, mode = 'QAM'):
        print('now setting up pulse sequence')
        print('self.read_time:', self.read_time)
        print('self.clock_time:',  self.clock_time)        
        #self.laser_lag
        #self.laserLag_time = 80 #hard coded for now
        
        # First laser lag for first MWon signal
        laser = [(self.laser_lag, 1)]
        clock = [(self.laser_lag, 0)]
        if mode == 'QAM':
            mwI = [(self.laser_lag, self.IQ0[0])]
            mwQ = [(self.laser_lag, self.IQ0[1])]
        else:
            mwI = [(self.laser_lag, -1)]
        
        # mwOnOff repeating sequence
        mwOnOff_laser = [(self.read_time, 1), (self.read_time, 1)]
        if mode == 'QAM':
            mwOnOff_mwI = [(self.read_time, self.IQpx[0]), (self.read_time, self.IQ0[0])]
            mwOnOff_mwQ = [(self.read_time, self.IQpx[1]), (self.read_time, self.IQ0[1])]
        else:
            mwOnOff_mwI = [(self.read_time, 0), (self.read_time, -1)]
        mwOnOff_clock = [(self.clock_time,1),(self.read_time-self.clock_time,0),(self.clock_time,1),(self.read_time-self.clock_time,0)]
        
        # adding initial sequence to repeating sequence
        for i in range(self.runs):        
            laser += mwOnOff_laser
            clock += mwOnOff_clock
            mwI += mwOnOff_mwI
            if mode == 'QAM':
                mwQ += mwOnOff_mwQ
        
        # Last clock to collect for the last point in the run        
        laser += [(self.clock_time, 0)]
        clock += [(self.clock_time, 1)]
        if mode == 'QAM':
            mwI += [(self.clock_time, self.IQ0[0])]
            mwQ += [(self.clock_time, self.IQ0[1])]
        else:
            mwI += [(self.clock_time, -1)]
        
        self.total_time += self.laser_lag + 2 * self.read_time*self.runs + self.clock_time
        dchans = [self.channel_dict['laser'],self.channel_dict['clock']]
        dpatterns = [laser,clock]
        if mode == 'QAM':
            achans = [0,1]
            apatterns = [mwI,mwQ]
        else:
            achans = [0]
            apatterns = [mwI]
        
        self.sequence.setDigital(self.channel_dict['laser'], laser)
        self.sequence.setDigital(self.channel_dict['clock'], clock)
        self.sequence.setAnalog(0, mwI)
        if mode == 'QAM':
            self.sequence.setAnalog(1, mwQ)    
        
        print('Finished setting up pulse sequence')
        print('self.sequence data:',  self.sequence.getData())
        #self.plotSeq(self.sequence.getData(),'CWUriMRnew')
        #self.plotSeq(dchans,achans,dpatterns,apatterns,'CWUriMRnew') #works
        return self.sequence
    

    def I1I2_old(self, exp_time, readout_time, freq, laser_lag = 70000000, four_pt = True):
        '''
        I1I2 measurement using sig-gen FM modulation 
        '''
        
        patternCam = [(exp_time, 1), (readout_time, 0)]
        patternLaser = [(exp_time, 1), (readout_time, 0)]

        uwLeft = [(exp_time+readout_time,-1)] ##AO 0
        uwRight = [(exp_time+readout_time,1)] ##AO 0


        experiment = self.Pulser.createSequence()

        laser = [(laser_lag, 1)]
        mwQ = [(laser_lag-readout_time/2, 0)]
        cam = [(laser_lag-readout_time, 1),(readout_time,0)]

        for i in range(2):
            laser+= patternLaser
            cam+= patternCam
            if i==0:
                mwQ += uwLeft
            else:
                mwQ+= uwRight

        if four_pt:
            for i in range(2):
                laser+= patternLaser
                cam+= patternCam
                if i==0:
                    mwQ += uwRight
                else:
                    mwQ += uwLeft
            experiment.setAnalog(0, mwQ)
            experiment.setDigital(self.channel_dict['camera'], cam)
            experiment.setDigital(self.channel_dict['488'], laser)

            total_time = 4 * (exp_time+readout_time) + laser_lag
            print('sequence prepared')
            return experiment #, total_time

        experiment.setAnalog(0, mwQ)
        experiment.setDigital(self.channel_dict['camera'], cam)
        experiment.setDigital(self.channel_dict['488'], laser)
        total_time = 2 * (exp_time+readout_time) + laser_lag
        
        return experiment #, total_time

    def I1I2_double(self, exp_time, readout_time, freq, laser_lag = 70000000, four_pt = True):
        '''
        I1I2 measurement w/ FM modulation, double initial throwaway pulse?
        '''
        patternCam = [(exp_time, 1), (readout_time, 0)]
        patternLaser = [(exp_time, 1), (readout_time, 0)]

        uwLeft = [(exp_time+readout_time,-1)] 
        uwRight = [(exp_time+readout_time,1)] 


        experiment = self.Pulser.createSequence()

        laser = [(laser_lag, 1)]
        mwQ = [(laser_lag-readout_time/2, 0)]
        cam = [(laser_lag-readout_time, 1),(readout_time,0)]

        laser+=patternLaser
        cam+=patternCam
        mwQ+=uwLeft
        for i in range(2):
            laser+= patternLaser
            cam+= patternCam
            if i==0:
                mwQ += uwLeft
            else:
                mwQ+= uwRight

        if four_pt:
            for i in range(2):
                laser+= patternLaser
                cam+= patternCam
                if i==0:
                    mwQ += uwRight
                else:
                    mwQ += uwLeft
            experiment.setAnalog(0, mwQ)
            experiment.setDigital(self.channel_dict['camera'], cam)
            experiment.setDigital(self.channel_dict['488'], laser)
            total_time = 4 * (exp_time+readout_time) + laser_lag
            print('sequence prepared')
            return experiment #, total_time

        experiment.setAnalog(0, mwQ)
        experiment.setDigital(self.channel_dict['camera'], cam)
        experiment.setDigital(self.channel_dict['488'], laser)
        total_time = 2 * (exp_time+readout_time) + laser_lag
        
        return experiment #, total_time

    def I1I2_FT(self, exp, read, trig, buff, debug_flag_rev = False, n_pair = 1, throwaway = 1, ref = True, bg = True):

        '''
        I1I2 measurement w/ FM modulation, implementing frame transfer regime
        '''
        pulse_str = ''

        experiment = self.Pulser.createSequence()
        pulse_len = exp+buff+read
        cam_off = exp + read + buff - trig

        uwLeft = [(pulse_len,-1)] 
        uwRight = [(pulse_len,1)]
        p1 = '1'
        p2 = '2'
        
        uwOn = [(pulse_len,0)]
        uwOff = [(pulse_len,1)]

        if debug_flag_rev:
            uwLeft = [(pulse_len,1)] 
            uwRight = [(pulse_len,-1)] 
            p1 = '2'
            p2 = '1'

        cam_seq = [(trig,1), (cam_off,0)]
        laser_seq = [(exp,1),(buff+read,0)]


        mwQ = []
        mwQ += uwLeft*throwaway
        cam = []
        cam += cam_seq*throwaway
        switch = []
        switch = uwOn*throwaway

        laser = [(pulse_len,0)]*throwaway

        for i in range(2*n_pair):
            laser+= laser_seq
            cam+= cam_seq
            if i%2==0:
                mwQ += uwLeft
                switch += uwOn
                pulse_str+=p1
            else:
                mwQ+= uwRight
                switch += uwOn
                pulse_str+=p2
            if bg:
                laser+= laser_seq
                cam+= cam_seq
                switch += uwOff
                mwQ+= uwRight
                pulse_str +='0'

        if ref:
            for i in range(2*n_pair):
                laser+= laser_seq
                cam+= cam_seq
                if i%2==0: 
                    mwQ += uwRight
                    switch += uwOn
                    pulse_str+='2'
                else:
                    mwQ+= uwLeft
                    switch += uwOn
                    pulse_str+='1'
                if bg:
                    laser+= laser_seq
                    cam+= cam_seq
                    switch += uwOff
                    mwQ+= uwRight
                    pulse_str = '0'

            experiment.setAnalog(0, mwQ)
            experiment.setDigital(self.channel_dict['camera'], cam)
            experiment.setDigital(self.channel_dict['488'], laser)
            experiment.setDigital(self.channel_dict['switch'], switch)
            print('sequence prepared')
            print(cam)
            print(laser)
            print(pulse_str)
            return experiment #, total_time

        experiment.setAnalog(0, mwQ)
        experiment.setDigital(self.channel_dict['camera'], cam)
        experiment.setDigital(self.channel_dict['488'], laser)
        experiment.setDigital(self.channel_dict['switch'], switch)

        print('sequence prepared')
        print(cam)
        print(laser)
        print(pulse_str)
        return experiment #, total_time

    def I1I2(self, exp, read, trig, buff, label, FT = True):
        '''
        Fully general I1I2 Code. 

        label: list of entries {t,0,1,2}:
        't': throwaway pulse (no microwave, no laser)
        0: background pulse (no microwave, laser)
        1: f1 pulse
        2: f2 pulse
        
        ex: "['t','t','t', 1, 0, 2, 0, 2, 0, 1, 0]"

        all codes not on this list will cause a warning and be ignored
        '''

        if not FT:
            trig = exp

        experiment = self.Pulser.createSequence()
        pulse_len = exp+buff+read
        cam_off = exp + read + buff - trig

        ## mwQ frequency modulation
        uwLeft = [(pulse_len,-1)] 
        uwRight = [(pulse_len,1)]
        ## Switch modulation
        uwOn = [(exp,0),(buff+read,1)]
        uwOff = [(pulse_len,1)]
        ## Cam and Laser pulse sequences
        cam_seq = [(trig,1), (cam_off,0)]
        laser_seq = [(exp,1),(buff+read,0)]
        off_seq = [(pulse_len, 0)] #laser & cam


        mwQ = []
        cam = []
        switch = []
        laser = []

        
        for i in range(len(label)):
            if label[i] == 't':            
            ## Throwaway
                mwQ += uwLeft
                cam += cam_seq
                switch += uwOff
                laser += off_seq
            elif label[i] == 1 or label[i] == '1':
                mwQ += uwLeft
                cam += cam_seq
                switch += uwOn
                laser += laser_seq
            elif label[i] == 2 or label[i] == '2':
                mwQ += uwRight
                cam += cam_seq
                switch += uwOn
                laser += laser_seq
            elif label[i] == 0 or label[i] == '0':
                mwQ += uwRight
                cam += cam_seq
                switch += uwOff
                laser += laser_seq
            else:
                print(f'Warning, {label[i]} not a valid code. Skipping...')

        experiment.setAnalog(0, mwQ)
        experiment.setDigital(self.channel_dict['camera'], cam)
        experiment.setDigital(self.channel_dict['488'], laser)
        experiment.setDigital(self.channel_dict['switch'], switch)
        print('sequence prepared')
        return experiment #, total_time


    #ODMR sequence for use with ixon Ultra camera (wide field detection)
    def WFODMR_quickpulse(self, exp_time, readout_time, mode = 'QAM'):
        '''
        NOT THE MOST RECENT, DEPRECATED

        mode: QAM for vector modulation (IQ mixer)
        mode: AM for analog modulation of amplitude
        '''
        print('now setting up pulse sequence')
        print('exposure time:', exp_time)
        print('readout time:', readout_time)
        print('probe time:', self.read_time)
        frame_time = exp_time + readout_time

        experiment = self.Pulser.createSequence()

        
        
        #Laser Lag in this sequence is more of an initial lag to account for the first exposure+readout of the camera in order to deal with first-image-artifacts
        laser = [(self.laser_lag, 1)]
        cam = [(self.laser_lag-readout_time, 1),(readout_time,0)] #Check if need a lag for the camera
        
        mwOff_time = self.read_time*2-self.exp_time
        if(mode == 'QAM'):
            mwI = [(self.laser_lag, self.IQ0[0])]
            mwQ = [(self.laser_lag, self.IQ0[1])]
            mwOnOff_mwI = [(self.read_time, self.IQpx[0]), (self.read_time, self.IQ0[0])]
            mwOnOff_mwQ = [(self.read_time, self.IQpx[1]), (self.read_time, self.IQ0[1])]
        elif(mode == 'AM'):
            ## NOTE IT SAYS mwI but it's actually Q that's plugged into A0
            mwI = [(self.laser_lag, -1)] 
            mwOnOff_mwI = [(self.read_time, 0), (self.read_time, -1)]

        
        # adding initial sequence to repeating sequence
        camcycles = (self.read_time - (self.read_time%frame_time)) / frame_time #counts total number of frames during the read time

        #import pdb; pdb.set_trace()
        seq = [(exp_time, 1), (readout_time, 0)]
        for i in range(self.runs):        
            #laser += mwOnOff_laser
            mwI += mwOnOff_mwI
            if mode == 'QAM':
                mwQ += mwOnOff_mwQ
            for j in range(int(camcycles)):
                cam += seq
                laser += seq
            cam += [(self.read_time%frame_time, 0)]
            laser += [(self.read_time%frame_time, 1)]
            for j in range(int(camcycles)):
                cam += seq
                laser += seq
            cam += [(self.read_time%frame_time, 0)]
            laser += [(self.read_time%frame_time, 1)]
        
        self.total_time += self.laser_lag + 2 * self.read_time*self.runs # + self.clock_time
        dchans = [self.channel_dict['laser'],self.channel_dict['clock'],self.channel_dict['camera']]
        achans = [0,1]
        dpatterns = [laser,cam]
        if mode == 'QAM':
            apatterns = [mwI,mwQ]
        elif mode == 'AM':
            apatterns = [mwI]

        experiment.setDigital(self.channel_dict['488'], laser)
        experiment.setDigital(self.channel_dict['camera'], cam)
        experiment.setAnalog(0, mwI)
        if(mode == 'QAM'):
            experiment.setAnalog(1, mwQ)    
        
        print('Finished setting up pulse sequence')
        print('self.sequence data:',  experiment.getData())
        #self.plotSeq(self.sequence.getData(),'CWUriMRnew')
        #self.plotSeq(dchans,achans,dpatterns,apatterns,'CWUriMRnew') #works
        return experiment

    def WFODMR_FT(self, exp, read, trig, buff, runs, mode = 'QAM'): 
        '''
        NOT THE MOST RECENT, DEPRECATED

        mode: QAM for vector modulation (IQ mixer)
        mode: AM for analog modulation of amplitude
        mode: SWITCH is AM mode but modulation is done entirely via a separate switch. There is no double modulation mode (AM+Switch), yet. 
        '''        
        pulse_len = exp+buff+read
        cam_off = exp + read + buff - trig

        experiment = self.Pulser.createSequence()

        #### INITIAL THROWAWAY PULSE
        laser = [(pulse_len,0)]
        cam = [(trig,1), (cam_off,0)] #Check if need a lag for the camera
        mwOff_time = self.read_time*2-self.exp_time
        if(mode == 'QAM'):
            mwI = [(pulse_len, self.IQ0[0])]
            mwQ = [(pulse_len, self.IQ0[1])]
            mwOnOff_mwI = [(exp, self.IQpx[0]), (pulse_len + read + buff, self.IQ0[0])]
            mwOnOff_mwQ = [(exp, self.IQpx[1]), (pulse_len + read + buff, self.IQ0[1])]
        elif(mode == 'AM'):
            ## NOTE IT SAYS mwI but it's actually Q that's plugged into A0
            mwI = [(pulse_len, -1)]
            mwOnOff_mwI = [(exp, 0), (pulse_len + read + buff, -1)]
        elif(mode == 'SWITCH'):
            mwI = [(pulse_len, 0)]
            mwOnOff_mwI = [(2*pulse_len, 0)]
            switch = [(pulse_len, 1)]
            switchOnOff = [(exp,0),(pulse_len+buff+read,1)]

        ####

        cam_seq = [(trig,1), (cam_off,0)]
        laser_seq = [(exp,1),(buff+read,0)]
        for i in range(runs):        
            #laser += mwOnOff_laser
            mwI += mwOnOff_mwI
            if mode == 'QAM':
                mwQ += mwOnOff_mwQ
            elif mode == 'SWITCH':
                switch += switchOnOff
            cam += cam_seq + cam_seq
            laser += laser_seq + laser_seq
        
        dchans = [self.channel_dict['laser'],self.channel_dict['clock'],self.channel_dict['camera']]
        achans = [0,1]
        dpatterns = [laser,cam]
        if mode == 'QAM':
            apatterns = [mwI,mwQ]
        elif mode == 'AM' or mode == 'SWITCH':
            apatterns = [mwI]
        if mode == 'SWITCH':
            dpatterns.append(switch)


        experiment.setDigital(self.channel_dict['488'], laser)
        experiment.setDigital(self.channel_dict['camera'], cam)
        experiment.setAnalog(0, mwI)
        if (mode == 'QAM'):
            experiment.setAnalog(1, mwQ)   
        elif (mode =='SWITCH'):
            experiment.setDigital(self.channel_dict['switch'], switch)


        
        print('Finished setting up pulse sequence')
        print('self.sequence data:',  experiment.getData())
        #self.plotSeq(self.sequence.getData(),'CWUriMRnew')
        #self.plotSeq(dchans,achans,dpatterns,apatterns,'CWUriMRnew') #works
        return experiment

    def WFODMR(self, runs, exp, read, trig = 10000000, buff = 5000000, mode = 'QAM', FT = True, mw_duty = 1, mw_rep = 50): 
        '''
        Fully generalized WFODMR code.

        TIME inputs in ns

        mode: QAM for vector modulation (IQ mixer)
        mode: AM for analog modulation of amplitude
        mode: SWITCH is AM mode but modulation is done entirely via a separate switch. There is no double modulation mode (AM+Switch), yet. 
        '''        
        if not FT:
            trig = exp
        pulse_len = exp+buff+read
        cam_off = exp + read + buff - trig

        experiment = self.Pulser.createSequence()

        #### INITIAL THROWAWAY PULSE
        laser = [(pulse_len,0)]
        cam = [(trig,1), (cam_off,0)] #Check if need a lag for the camera
        res = mw_rep
        duty = mw_duty
        if(mode == 'QAM'):
            mwI = [(pulse_len, self.IQ0[0])]
            mwQ = [(pulse_len, self.IQ0[1])]
            if mw_duty == 1:
                mwOnOff_mwI = [(exp, self.IQpx[0]), (pulse_len + read + buff, self.IQ0[0])]
                mwOnOff_mwQ = [(exp, self.IQpx[1]), (pulse_len + read + buff, self.IQ0[1])]
            else:
                mwOnOff_mwI = [(exp*duty/res, self.IQpx[0]), (exp*(1-duty)/res, self.IQ0[0])]*res + [(pulse_len + read + buff, self.IQ0[0])]
                mwOnOff_mwQ = [(exp*duty/res, self.IQpx[1]), (exp*(1-duty)/res, self.IQ0[1])]*res + [(pulse_len + read + buff, self.IQ0[1])]
        elif(mode == 'AM'):
            ## NOTE IT SAYS mwI but it's actually Q that's plugged into A0
            mwI = [(pulse_len, -1)]
            if mw_duty == 1:
                mwOnOff_mwI = [(exp, 0), (pulse_len + read + buff, -1)]
            else:
                mwOnOff_mwI = [(exp*duty/res, 0), (exp*(1-duty)/res,-1)]*res + [(pulse_len + read + buff, -1)]

        elif(mode == 'SWITCH'):
            print('untested, and mw_duty unimplemented!')
            if mw_duty != 1:
                raise Exception('mw_duty unimplemented.')
            mwI = [(pulse_len, 0)]
            mwOnOff_mwI = [(2*pulse_len, 0)]
            switch = [(pulse_len, 1)]
            switchOnOff = [(exp,0),(pulse_len+buff+read,1)]

        #### MAIN SEQUENCE

        cam_seq = [(trig,1), (cam_off,0)]
        laser_seq = [(exp,1),(buff+read,0)]
        for i in range(runs):        
            #laser += mwOnOff_laser
            mwI += mwOnOff_mwI
            if mode == 'QAM':
                mwQ += mwOnOff_mwQ
            elif mode == 'SWITCH':
                switch += switchOnOff
            cam += cam_seq + cam_seq
            laser += laser_seq + laser_seq
        
        dchans = [self.channel_dict['laser'],self.channel_dict['clock'],self.channel_dict['camera']]
        achans = [0,1]
        dpatterns = [laser,cam]
        if mode == 'QAM':
            apatterns = [mwI,mwQ]
        elif mode == 'AM' or mode == 'SWITCH':
            apatterns = [mwI]
        if mode == 'SWITCH':
            dchans.append(self.channel_dict['switch'])
            dpatterns.append(switch)


        experiment.setDigital(self.channel_dict['488'], laser)
        experiment.setDigital(self.channel_dict['camera'], cam)
        experiment.setAnalog(0, mwI)
        if (mode == 'QAM'):
            experiment.setAnalog(1, mwQ)   
        elif (mode =='SWITCH'):
            experiment.setDigital(self.channel_dict['switch'], switch)


        
        print('Finished setting up pulse sequence')
        print('self.sequence data:',  experiment.getData())
        #self.plotSeq(self.sequence.getData(),'CWUriMRnew')
        #self.plotSeq(dchans,achans,dpatterns,apatterns,'CWUriMRnew') #works
        return experiment

    def gain_seq(self, exp, read, trig = 10000000, buff = 5000000, FT = True): 
        '''
        Quick 2-pulse seq for optimizing gain
        '''        
        if not FT:
            trig = exp
        pulse_len = exp+buff+read
        cam_off = exp + read + buff - trig

        experiment = self.Pulser.createSequence()

        laser = [(pulse_len,1)] * 2
        cam = [(trig,1), (cam_off,0)] *2
        
        dchans = [self.channel_dict['laser'],self.channel_dict['camera']]
        dpatterns = [laser,cam]
        experiment.setDigital(self.channel_dict['488'], laser)
        experiment.setDigital(self.channel_dict['camera'], cam) 

        print('Finished gain_seq:')
        print('laser: ',laser)
        print('cam: ', cam)
        print('self.sequence data:',  experiment.getData())
        print('---')
        #self.plotSeq(self.sequence.getData(),'CWUriMRnew')
        #self.plotSeq(dchans,achans,dpatterns,apatterns,'CWUriMRnew') #works
        return experiment

    def FM_WFODMR(self, exp, read, trig, buff, runs, f_start, f_end, N, throwaway = 1):

        '''
        NON-FUNCTIONAL DUE TO CAMERA FLUORESCENCE DYNAMICS

        WFODMR done via FM, using FT.
        TODO: add non-FT version
        gets passed in the full frequency range in the form of the start, stop and desired number of frequencies.
        Returns a series of sequences for the spyrelet to run in series.  

        the frequency space is carved into cycles, which is carved into individual frequencies, which is carved into runs, which has 2 pulses (sig+bg)
        '''
        max_img = 17 #I believe this is really 21, but I don't want to push it, and 1 throwaway + 4 sets of 2 runs (2 img each) is clean

        imgs_per_freq = 2*runs #sig+bg
        freq_per_cycle = int((max_img - throwaway)/imgs_per_freq)
        # freq_per_cycle = 1 
        cycles = int(N/freq_per_cycle)
        leftover = N%freq_per_cycle
        '''
        1 run > 8 freqs
        2 runs > 4 freqs
        3 runs > 2 freqs
        4 runs > 2 freqs
        5 runs+ > 1 freq
        9 runs impossible

        return [seq0, seq1, seq2, ... seq#(cycles-1), seq_leftover], freq_per_cycle*imgs_per_freq+throwaway, leftover*imgs_per_freq + throwaway
        '''

        seq_series = []
        modulation_series = np.linspace(-1,1,N,endpoint = True)

        ## USEFUL PARAMS
        pulse_len = exp+buff+read
        cam_off = exp + read + buff - trig
          
        uwOn = [(pulse_len,0)]
        uwOff = [(pulse_len,1)]

        cam_seq = [(trig,1), (cam_off,0)]
        laser_seq = [(exp,1),(buff+read,0)]

        for i in range(cycles):
            ## CREATE seq_series[i]
            seq = self.Pulser.createSequence()  

            ## INIT and THROWAWAY
            uwPulse = [(pulse_len,-1)]
            mwQ = []
            mwQ += uwPulse*throwaway
            cam = []
            cam += cam_seq*throwaway
            switch = []
            switch = uwOn*throwaway
            laser = [(pulse_len,0)]*throwaway

            for j in range(freq_per_cycle*i, freq_per_cycle*(i+1)):
                uwPulse = [(pulse_len,modulation_series[j])] 
                for k in range(runs):
                    laser+= laser_seq
                    cam+= cam_seq
                    mwQ += uwPulse
                    switch += uwOn

                    laser+= laser_seq
                    cam+= cam_seq
                    mwQ+= uwPulse
                    switch += uwOff


            seq.setAnalog(0, mwQ)
            seq.setDigital(self.channel_dict['camera'], cam)
            seq.setDigital(self.channel_dict['488'], laser)
            seq.setDigital(self.channel_dict['switch'], switch)
            print('sequence prepared')
            seq_series.append(seq)

        if leftover > 0:
            seq = self.Pulser.createSequence()  
            ## INIT and THROWAWAY
            mwQ = []
            mwQ += uwPulse*throwaway
            cam = []
            cam += cam_seq*throwaway
            switch = []
            switch = uwOn*throwaway
            laser = [(pulse_len,0)]*throwaway
            for j in range(leftover):
                uwPulse = [(pulse_len,modulation_series[freq_per_cycle*cycles+j])] 
                for k in range(runs):
                    laser+= laser_seq
                    cam+= cam_seq
                    mwQ += uwPulse
                    switch += uwOn

                    laser+= laser_seq
                    cam+= cam_seq
                    mwQ+= uwPulse
                    switch += uwOff

            seq.setAnalog(0, mwQ)
            seq.setDigital(self.channel_dict['camera'], cam)
            seq.setDigital(self.channel_dict['488'], laser)
            seq.setDigital(self.channel_dict['switch'], switch)
            print('sequence prepared')
            seq_series.append(seq)

        #Returns a series of pulse-sequences [seq1,seq2,seq3,...] to run, and the # of images per cycle, as well as the # of images in the last sequence.
        return seq_series, freq_per_cycle*imgs_per_freq+throwaway, leftover*imgs_per_freq + throwaway #, total_time

    def debug_cam_pulse(self,exp,read,trig,buff):
        #### Change this to whatever you need to debug in the moment
        exp_buffer = buff
        if(exp<trig):
            print('exposure too short...')
        cam_off = exp + read + exp_buffer - trig
        experiment = self.Pulser.createSequence()
        camera = [(trig,1), (cam_off,0), (trig,1), (cam_off,0), (trig,1), (cam_off,0)]
        laser = [(exp,0), (read+exp_buffer,0), (exp,1), (read+exp_buffer,0), (exp,1), (read+exp_buffer,0)]
        experiment.setDigital(self.channel_dict['camera'], camera)
        experiment.setDigital(self.channel_dict['488'], laser)
        print(camera)
        print(laser)
        return experiment



    def camLagExperiment(self,exp_time,t1,t2,runs, zero_pulse = True):
        '''
        Laser: OFF(100ms) ON(500ms) OFF(100ms)
        t1,t2 <= 100
        '''

        experiment = self.Pulser.createSequence()



        laser_on_time = 0.8e9
        laser_pad_time = 0.1e9
        middle_section_time = 0.5e9 
        fringe_section_time = (laser_on_time - middle_section_time)/2


        laser = [(laser_pad_time,0), (laser_on_time,1), (laser_pad_time,0)]
        camera = [(int(laser_pad_time+t1),0), (int(exp_time),1), (int(fringe_section_time - t1-exp_time),0)] #section 1
        camera += [(int((0.5e9-exp_time)/2),0),(int(exp_time),1),(int((0.5e9-exp_time)/2),0)] 
        camera += [(int(fringe_section_time + t2 - exp_time),0),(int(exp_time),1),(int(laser_pad_time - t2),0)]

        laser *= runs
        camera *= runs

        #initial wasted pulse
        if(zero_pulse):
            laser = [(2*exp_time,0)] + laser 
            camera = [(exp_time,1),(exp_time,0)] + camera 

        print(camera)
        # print(laser)
        # import pdb;pdb.set_trace()
        experiment.setDigital(self.channel_dict['488'], laser)
        experiment.setDigital(self.channel_dict['camera'], camera)

        return experiment

    def laserLagSequence(self, exp_time, offset_time):
        '''
        frame time hard coded to be exp_time + 59ms. There's not much room for optimization here anyway, with respect to this experiment.
        camera waits for offset_time (LO) and then captures for exposure time (HI)
        laser waits for dead_time (LO, defined below), and then is turned on for however long until exposure time is over. Then all is shut off,
        and a period of 60ms off time at the end is added to make sure camera reads out safely.
        '''
        dead_time = 1.1*exp_time # time before laser is turned on.
        offset_time  = float(offset_time)
        #Initial off sequences
        laser = [(dead_time, 0)]
        cam = [(offset_time, 0),(exp_time, 1),(dead_time,0)]

        if offset_time <= 0.1*exp_time:
            laser += [(offset_time+exp_time,0)]
        else:
            #laser+= [(offset_time-0.1*exp_time,1),(dead_time,0)]
            laser+= [(offset_time,1),(dead_time+0.1*exp_time,0)]

        dchans = [self.channel_dict['laser'],self.channel_dict['camera']]
        dpatterns = [laser,cam]
        
        laser_print = []
        for t,p in laser:
            laser_print.append((int(t/1e6),p))
        cam_print = []
        for t,p in cam:
            cam_print.append((int(t/1e6),p))

        print('laser:', laser_print)
        print('cam:', cam_print)
        self.sequence.setDigital(self.channel_dict['488'], laser)
        self.sequence.setDigital(self.channel_dict['camera'], cam)
        
        print('Finished setting up pulse sequence')
        print('self.sequence data:',  self.sequence.getData())
        #self.plotSeq(self.sequence.getData(),'CWUriMRnew')
        #self.plotSeq(dchans,achans,dpatterns,apatterns,'CWUriMRnew') #works
        return self.sequence 

    
    def ODMRHeatDissipation(self, laser_recharge, wait_time):  
        #Developed by Tian-Xing at 20230720, for trainsent ODMR on WSP, for avoiding the Singlet Fission
        # laser_recharge is not used here, since we want to 'wait' after both sg and bg
        print('now setting up pulse sequence')
        print('self.read_time:', self.read_time)
        print('self.clock_time:',  self.clock_time)        
        #self.laser_lag
        #self.laserLag_time = 80 #hard coded for now
        
        # First block of the full seuqence, which is turnning on the laser
        laser = []
        clock = []
        mwI = []
        mwQ = []
        
        # Laser_lag repeating sequence
        Laser_lag_laser = [(self.laser_lag, 1)]
        Laser_lag_clock = [(self.laser_lag, 0)]
        Laser_lag_mwI = [(self.laser_lag, self.IQ0[0])]
        Laser_lag_mwQ = [(self.laser_lag, self.IQ0[1])]
        
        # mwOn repeating sequence
        # TX Note: not sure setting the readout clock like this will work, becaues the odmr_math in the dr_psNew spyrelet seems incompatible with this
        mwOn_laser = [(self.read_time, 1)]
        mwOn_clock = [(self.clock_time,1),(self.read_time-2*self.clock_time,0),(self.clock_time,1)]
        mwOn_mwI = [(self.read_time, self.IQpx[0])]
        mwOn_mwQ = [(self.read_time, self.IQpx[1])]
        
        
        # mwOff repeating sequence
        mwOff_laser = [(self.read_time, 1)]
        mwOff_clock = [(self.clock_time,1),(self.read_time-2*self.clock_time,0),(self.clock_time,1)]
        mwOff_mwI = [(self.read_time, self.IQ0[0])]
        mwOff_mwQ = [(self.read_time, self.IQ0[1])]
        
        
        # wait repeating sequence
        wait_laser = [(wait_time, 0)]
        wait_clock = [(wait_time, 0)]
        wait_mwI = [(wait_time, self.IQ0[0])]
        wait_mwQ = [(wait_time, self.IQ0[1])]
        

        # adding initial sequence to repeating sequence
        for i in range(self.runs):        
            laser += Laser_lag_laser + mwOn_laser + wait_laser + Laser_lag_laser + mwOff_laser + wait_laser
            clock += Laser_lag_clock + mwOn_clock + wait_clock + Laser_lag_clock + mwOff_clock + wait_clock
            mwI += Laser_lag_mwI + mwOn_mwI + wait_mwI + Laser_lag_mwI + mwOff_mwI + wait_mwI
            mwQ += Laser_lag_mwQ + mwOn_mwQ + wait_mwQ + Laser_lag_mwQ + mwOff_mwQ + wait_mwQ
        
        # Last clock to collect for the last point in the run
        # TX Note: Need to set this last clock to readout the current fluorescence value because in math_odmr, delta_buffer = array[1:] - array[0:-1]. We need to recored the fluorescence value for the last waiting window of each run        
        laser += [(self.clock_time, 0)]
        clock += [(self.clock_time, 1)]
        mwI += [(self.clock_time, self.IQ0[0])]
        mwQ += [(self.clock_time, self.IQ0[1])]
        
        self.total_time = (2*self.laser_lag + 2 * self.read_time + 2*wait_time)*self.runs + self.clock_time
        dchans = [self.channel_dict['laser'],self.channel_dict['clock']]
        achans = [0,1]
        dpatterns = [laser,clock]
        apatterns = [mwI,mwQ]
        
        self.sequence.setDigital(self.channel_dict['laser'], laser)
        self.sequence.setDigital(self.channel_dict['clock'], clock)
        self.sequence.setAnalog(0, mwI)
        self.sequence.setAnalog(1, mwQ)    
        
        print('Finished setting up pulse sequence')
        print('self.sequence data:',  self.sequence.getData())
        #self.plotSeq(self.sequence.getData(),'CWUriMRnew')
        #self.plotSeq(dchans,achans,dpatterns,apatterns,'CWUriMRnew') #works
        
        return self.sequence
    
    def gsLifetime(self,laserOffTime,readStartTime,numPoints):
        print('now setting up pulse sequence')
        print('self.read_time:', self.read_time)
        print('self.clock_time:',  self.clock_time)
        print('self.laser_lag:',  self.laser_lag)
        
        laser_off = laserOffTime # time used to allow the system to thermalize
        laser_on = readStartTime + self.read_time * numPoints # time that laser stays on 
        
        laser = [(self.laser_lag,1),(laser_on,1),(laser_off,0)]
        
        if readStartTime == 0:
            clock = [(self.laser_lag,0),(self.clock_time,1)]
        else:
            clock = [(self.laser_lag,0),(readStartTime,0),(self.clock_time,1)]
        
        for i in range(numPoints):
            clock.append((self.read_time-self.clock_time,0))
            clock.append((self.clock_time,1))
        clock.append((laser_off-self.clock_time,0))
        
        self.sequence.setDigital(self.channel_dict['laser'], laser)
        self.sequence.setDigital(self.channel_dict['clock'], clock)  
        print('Finished setting up pulse sequence')
        se_time = self.sequence.getDuration()
        print('Sequence duration is:', se_time)
        return self.sequence,se_time
    
    def mixedStateCreation(self,laserOffTime,readStartTime,numPoints):
        print('now setting up pulse sequence')
        print('self.read_time:', self.read_time)
        print('self.clock_time:',  self.clock_time)
        print('self.laser_lag:',  self.laser_lag)
        
        laser_off = laserOffTime # time used to allow the system to thermalize
        laser_on = readStartTime + self.read_time * numPoints # time that laser stays on 
        
        laser = [(self.laser_lag,1),(laser_on,1),(laser_off,0)]
        mwI_on = [(self.laser_lag,self.IQ0[0]),(laser_on,self.IQpx[0]),(laser_off,self.IQ0[0])]
        mwQ_on = [(self.laser_lag,self.IQ0[1]),(laser_on,self.IQpx[1]),(laser_off,self.IQ0[1])]
        mwI_off = [(self.laser_lag,self.IQ0[0]),(laser_on,self.IQ0[0]),(laser_off,self.IQ0[0])]
        mwQ_off = [(self.laser_lag,self.IQ0[1]),(laser_on,self.IQ0[1]),(laser_off,self.IQ0[1])]
        
        if readStartTime == 0:
            clock = [(self.laser_lag,0),(self.clock_time,1)]
        else:
            clock = [(self.laser_lag,0),(readStartTime,0),(self.clock_time,1)]
        
        for i in range(numPoints):
            clock.append((self.read_time-self.clock_time,0))
            clock.append((self.clock_time,1))
        clock.append((laser_off-self.clock_time,0))
        
        self.sequence.setDigital(self.channel_dict['laser'], laser + laser)
        self.sequence.setDigital(self.channel_dict['clock'], clock + clock)
        self.sequence.setAnalog(0, mwI_on + mwI_off)
        self.sequence.setAnalog(1, mwQ_on + mwQ_off)

        print('Finished setting up pulse sequence')
        se_time = self.sequence.getDuration()
        print('Sequence duration is:', se_time)
        return self.sequence,se_time
        
    def flip_the_mirror(self):
        flip = \
            [(1000000, [self.channel_dict['mirror']], *self.IQ0)]
            
        #self.total_time = pulse_time * n_pulses
        
        return flip
    
    def testNewSeq(self):
        
        # from pulsestreamer import PulseStreamer, Sequence 
        #ip_address = '10.135.70.127'
        #ps = PulseStreamer(ip_address)
   
        pattern = [(10000, 1), (30000, 0)]
        seq = self.Pulser.createSequence()
        seq.setDigital(7, pattern)
        n_runs = PulseStreamer.REPEAT_INFINITELY
        self.stream(seq,n_runs)
        
    def plotSeq(self,dchans,achans,dpatterns,apatterns,spyreletName):
        
        ## create the proper file name including the directory
        time_string = Dt.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        fileName = 'C:\\NSpyre\\nspyre_files\\data\\Sequences\\' + spyreletName + time_string + '.xlsx'
        print('fileName:', fileName)
        
        ## save the data to a panda dataframe
        data = {
                'dchans': dchans,
                'dpatterns': dpatterns,
                'achans': achans,
                'apatterns': apatterns
        }

        df = pd.DataFrame(data)
        print('dfNew:\n', df)
        
        ## save the dataframe to an excel file with the given name and directory
        df.to_excel(fileName)
        
        # '''sequence is saved to an excel file where digital channels are in binary form
        # (powers of 2) and analog channels levels are in 16 bits form (should divide by 
        # 2^15-1 to get the actual value.
        # The file is then ploted using a seperate MATLAB file that takes advatage of the
        # sequence.plot() method of the pulsestreamer (only compatible with MATLAB) 
        # '''

    # def convert_sequence(self, seqs):
         # # 0-7 are the 8 digital channels
         # # 8-9 are the 2 analog channels
        # data = {}
        # time = -0.01
        # print('in convert_sequence')
        # for seq in seqs:
            # col = np.zeros(10)
            # #print('seq[1]:', seq[1], 'type:', type(seq[1]))
            # col[seq[1]] = 1
            # col[8] = seq[2]
            # col[9] = seq[3]
            # init_time = time + 0.01
            # data[init_time] = col
            # time = time + seq[0]
            # #data[prev_time_stamp + 0.01] = col
            # data[time] = col
            # #prev_time_stamp = seq[0]
        # dft = pd.DataFrame(data)
        # df = dft.T #transposes to have channels listed on vertical lines
        # sub_df = df[list(self._reverse_dict.keys())]
        # fin = sub_df.rename(columns = self._reverse_dict)
        # #print('data:', data, 'dft.T:', dft.T, 'sub_df:', sub_df, 'fin:', sub_df.rename(columns = self._reverse_dict))
        # return fin   

#### WORK IN PROGRESS #####
    # def PentTripletTransition(self, init_time, init_mw_gap, mw_time, measurement_time, iteration):
        # init_laser = [(self.aom_lag, 1), (init_time, 1)]
        # init_clock = [(self.aom_lag, 0), (init_time, 0)]
        # init_mw0 = [(self.aom_lag, self.IQ0[0]), (init, self.IQ0[0])]
        # init_mw1 = [(self.aom_lag, self.IQ0[1]), (init, self.IQ0[1])]
       
        # dark_laser = [(init_mw_gap, 0)]
        # dark_clock = [(init_mw_gap, 0)]
        # dark_mw0 = [(init_mw_gap, self.IQ0[0])]
        # dark_mw1 = [(init_mw_gap, self.IQ0[1])]
        
        # mw_laser = [(mw_time, 0)]
        # mw_clock = [(mw_time, 0)]
        # mw_mw0 = [(mw_time, self.IQpx[0])]
        # mw_mw1 = [(mw_time, self.IQpx[1])] 

        # seq_laser = init_laser + dark_laser + mw_laser
        # seq_clock = init_clock + dark_clock + mw_clock
        # seq_mw0 = init_mw0 + dark_mw0 + mw_mw0
        # seq_mw1 = init_mw1 + dark_mw1 + mw_mw1
        
        # measurement_laser = [(measurement_time, 0)]
        # measurement_clock = [(self.clock_time, 1), (measurement_time - self.clock_time, 0)]
        # measurement_mw0 = [(measurement_time, self.IQ0[0])]
        # measurement_mw1 = [(measurement_time, self.IQ0[1])]
        
        # for i in range(iteration):
            # seq_laser += measurement_laser
            # seq_clock += measurement_clock
            # seq_mw0 += measurement_mw0
            # seq_mw1 += measurement_mw1
        
        # self.total_time = init_time + init_mw_gap + mw_time + measurement_time * iteration
        # dchans = [self.channel_dict['laser'],self.channel_dict['clock']]
        # achans = [0,1]
        # dpatterns = [seq_laser, seq_clock]
        # apatterns = [seq_mw0, seq_mw1]
        
        # self.sequence.setDigital(self.channel_dict['laser'], seq_laser)
        # self.sequence.setDigital(self.channel_dict['clock'], seq_clock)
        # self.sequence.setAnalog(0, seq_mw0)
        # self.sequence.setAnalog(1, seq_mw1)    
        
        # self.plotSeq(dchans,achans,dpatterns,apatterns,'PentTripletTransition')
        
        # return self.sequence
        
    #######################################
    # Charge dynamics
    # def charge_dynamics_bright_time(self, laser_duration, read_duration, recharge_time):
        
    # read_duration defines the duration of one full measurement, including one laser pulse sandwiched between two clock pulses.
    # recharge_time defines the duration for reionization after conversion to NV0.
    # sequence:
    #           _______________ __________
    # laser: __/  initialize   |   read   |______recharge____
    #                           _          _
    # clock: __________________| |________| |____recharge____
    #
    # All other channels are set to 0
    
        # initialize_laser = [(self.aom_lag, 1), (laser_duration, 1)]
        # initialize_clock = [(self.aom_lag, 0), (laser_duration, 0)]
        # initialize_mw0 = [(self.aom_lag, self.IQ0[0]), (laser_duration, self.IQ0[0])]
        # initialize_mw1 = [(self.aom_lag, self.IQ0[1]), (laser_duration, self.IQ0[1])]
        
        # read_laser = [(self.aom_lag,1),          (read_duration - self.clock_time,1),                         (self.clock_time,0)]
        # read_clock = [(self.aom_lag,0),          (self.clock_time,1), (read_duration - 2*self.clock_time, 0), (self.clock_time, 1)]
        # read_mw0 = [(self.aom_lag, self.IQ0[0]), (read_duration - self.clock_time, self.IQ0[0]),              (self.clock_time, self.IQ0[0])]
        # read_mw1 = [(self.aom_lag, self.IQ0[1]), (read_duration - self.clock_time, self.IQ0[1]),              (self.clock_time, self.IQ0[0])]

        # recharge_laser = [(recharge_time, 0)]
        # recharge_clock = [(recharge_time, 0)]
        # recharge_mw0 = [(recharge_time, self.IQ0[0])]
        # recharge_mw1 = [(recharge_time, self.IQ0[1])]
        
        # recharge.setDigital(self.channel_dict['laser'], recharge_laser)
        # recharge.setDigital(self.channel_dict['clock'], recharge_clock)
        # recharge.setAnalog(0, recharge_mw0)
        # recharge.setAnalog(1, recharge_mw1)

        # laser = initialize_laser + read_laser + recharge_laser
        # clock = initialize_clock + read_clock + recharge_clock
        # mw0 = initialize_mw0 + read_mw0 + recharge_mw0
        # mw1 = initialize_mw1 + read_mw1 + recharge_mw1
        
        # self.total_time = self.aom_lag + laser_duration + read_duration + recharge_time
        # dchans = [self.channel_dict['laser'],self.channel_dict['clock']]
        # achans = [0,1]
        # dpatterns = [laser, clock]
        # apatterns = [mw0, mw1]
        
        # self.sequence.setDigital(self.channel_dict['laser'], laser)
        # self.sequence.setDigital(self.channel_dict['clock'], clock)
        # self.sequence.setAnalog(0, mw0)
        # self.sequence.setAnalog(1, mw1)   
        
        # self.plotSeq(dchans, achans, dpatterns, apatterns, 'charge_dynamics_bright_time')
        
        # return self.sequence

    # def charge_dynamics_dark_time(self, dark_time, read_duration, recharge_time):
    
    # # dark_time defines the duration of dark time (no laser illumination) after initialization and before readout.
    # # read_duration defines the duration of one full measurement, including one laser pulse sandwiched between two clock pulses.
    # # recharge_time defines the duration for reionization after conversion to NV0.
    # # sequence:
    # #           _______________        __________
    # # laser: __/  initialize   |_dark_/   read   |______recharge____
    # #                                   _         _
    # # clock: __________________________| |_______| |____recharge____
    # #
    # # All other channels are set to 0.
        # initialize_laser = [(self.aom_lag, 1), (self.laser_time, 1)]
        # initialize_clock = [(self.aom_lag, 0), (self.laser_time, 0)]
        # initialize_mw0 = [(self.aom_lag, self.IQ0[0]), (self.laser_time, self.IQ0[0])]
        # initialize_mw1 = [(self.aom_lag, self.IQ0[1]), (self.laser_time, self.IQ0[1])]
        
        # dark_laser = [(dark_time, 0)]
        # dark_clock = [(dark_time, 0)]
        # dark_mw0 = [(dark_time, self.IQ0[0])]
        # dark_mw1 = [(dark_time, self.IQ0[1])]

        # read_laser = [(self.aom_lag,1),          (read_duration - self.clock_time,1),                         (self.clock_time,0)]
        # read_clock = [(self.aom_lag,0),          (self.clock_time,1), (read_duration - 2*self.clock_time, 0), (self.clock_time, 1)]
        # read_mw0 = [(self.aom_lag, self.IQ0[0]), (read_duration - self.clock_time, self.IQ0[0]),              (self.clock_time, self.IQ0[0])]
        # read_mw1 = [(self.aom_lag, self.IQ0[1]), (read_duration - self.clock_time, self.IQ0[1]),              (self.clock_time, self.IQ0[0])]
        
        # recharge_laser = [(recharge_time, 0)]
        # recharge_clock = [(recharge_time, 0)]
        # recharge_mw0 = [(recharge_time, self.IQ0[0])]
        # recharge_mw1 = [(recharge_time, self.IQ0[1])]

        # laser = initialize_laser + dark_laser + read_laser + recharge_laser
        # clock = initialize_clock + dark_clock + read_clock + recharge_clock
        # mw0 = initialize_mw0 + dark_mw0 + read_mw0 + recharge_mw0
        # mw1 = initialize_mw1 + dark_mw1 + read_mw1 + recharge_mw1
        
        # self.total_time = 2*self.aom_lag + self.laser_time + wait_time + read_duration + recharge_time
        # dchans = [self.channel_dict['laser'],self.channel_dict['clock']]
        # achans = [0,1]
        # dpatterns = [laser, clock]
        # apatterns = [mw0, mw1]
        
        # self.sequence.setDigital(self.channel_dict['laser'], laser)
        # self.sequence.setDigital(self.channel_dict['clock'], clock)
        # self.sequence.setAnalog(0, mw0)
        # self.sequence.setAnalog(1, mw1)   
        
        # self.plotSeq(dchans, achans, dpatterns, apatterns, 'charge_dynamics_dark_time')
        
        # return sequence


        ################### OLD WFODMRS ################################################################
         #ODMR sequence for use with ixon Ultra camera (wide field detection)
        # def WFODMR(self, exp_time, frame_time):
        #     print('now setting up pulse sequence')
        #     print('self.read_time:', self.read_time)   
        #     print('exposure time:', exp_time)
        #     print('collection time:', frame_time)
        #     cam_delay = frame_time - exp_time
        #     #self.laser_lag
        #     #self.laserLag_time = 80 #hard coded for now
            
        #     # First laser lag for first MWon signal
        #     laser = [(self.laser_lag, 1)]
        #     mwI = [(self.laser_lag, self.IQ0[0])]
        #     mwQ = [(self.laser_lag, self.IQ0[1])]
        #     cam = [(self.laser_lag, 0)] #Check if need a lag for the camera
            
        #     # mwOnOff repeating sequence
        #     mwOnOff_laser = [(self.read_time, 1), (self.read_time, 1)]
        #     mwOff_time = self.read_time*2-self.exp_time
        #     mwOnOff_mwI = [(self.read_time, self.IQpx[0]), (self.read_time, self.IQ0[0])]
        #     mwOnOff_mwQ = [(self.read_time, self.IQpx[1]), (self.read_time, self.IQ0[1])]
        #     # mwOnOff_mwI = [(self.exp_time, self.IQpx[0]), (mwOff_time, self.IQ0[0])]
        #     # mwOnOff_mwQ = [(self.exp_time, self.IQpx[1]), (mwOff_time, self.IQ0[1])]
            
        #     #camera repeating sequence
        #     #cam = [(exp_time, 1), (cam_delay, 0)]
            
        #     # adding initial sequence to repeating sequence
        #     camcycles = (self.read_time - (self.read_time%frame_time)) / frame_time #counts total number of frames during the read time
        #     #import pdb; pdb.set_trace()
        #     for i in range(self.runs):        
        #         laser += mwOnOff_laser
        #         mwI += mwOnOff_mwI
        #         mwQ += mwOnOff_mwQ
        #         for j in range(int(camcycles)):
        #             cam += [(exp_time, 1), (cam_delay, 0)]
        #         cam += [(self.read_time%frame_time, 0)]
        #         for j in range(int(camcycles)):
        #             cam += [(exp_time, 1), (cam_delay, 0)]
        #         cam += [(self.read_time%frame_time, 0)]
            
        #     # # Last clock to collect for the last point in the run        
        #     # laser += [(self.clock_time, 0)]
        #     # clock += [(self.clock_time, 1)]
        #     # mwI += [(self.clock_time, self.IQ0[0])]
        #     # mwQ += [(self.clock_time, self.IQ0[1])]
        #     # cam += [(self.clock, 0)]
            
        #     self.total_time += self.laser_lag + 2 * self.read_time*self.runs # + self.clock_time
        #     dchans = [self.channel_dict['laser'],self.channel_dict['clock'],self.channel_dict['camera']]
        #     achans = [0,1]
        #     dpatterns = [laser,cam]
        #     apatterns = [mwI,mwQ]
            
        #     self.sequence.setDigital(self.channel_dict['488'], laser)
        #     self.sequence.setDigital(self.channel_dict['camera'], cam)
        #     self.sequence.setAnalog(0, mwI)
        #     self.sequence.setAnalog(1, mwQ)    
            
        #     print('Finished setting up pulse sequence')
        #     print('self.sequence data:',  self.sequence.getData())
        #     #self.plotSeq(self.sequence.getData(),'CWUriMRnew')
        #     #self.plotSeq(dchans,achans,dpatterns,apatterns,'CWUriMRnew') #works
        #     return self.sequence

        # def WFODMR_PR(self, exp_time, frame_time): #PR = Protective Readout
        #     print('now setting up pulse sequence')
        #     print('self.read_time:', self.read_time)   
        #     print('exposure time:', exp_time)
        #     print('collection time:', frame_time)
        #     cam_delay = frame_time - exp_time
        #     #self.laser_lag
        #     #self.laserLag_time = 80 #hard coded for now
            
        #     # First laser lag for first MWon signal
        #     laser = [(self.laser_lag, 1)]
        #     mwI = [(self.laser_lag, self.IQ0[0])]
        #     mwQ = [(self.laser_lag, self.IQ0[1])]
        #     cam = [(self.laser_lag, 0)] #Check if need a lag for the camera
            
        #     # mwOnOff repeating sequence
        #     #mwOnOff_laser = [(self.read_time, 1), (self.read_time, 1)] #not needed for PR, deal with laser elsewhere
        #     mwOff_time = self.read_time*2-self.exp_time
        #     mwOnOff_mwI = [(self.read_time, self.IQpx[0]), (self.read_time, self.IQ0[0])]
        #     mwOnOff_mwQ = [(self.read_time, self.IQpx[1]), (self.read_time, self.IQ0[1])]
        #     # mwOnOff_mwI = [(self.exp_time, self.IQpx[0]), (mwOff_time, self.IQ0[0])]
        #     # mwOnOff_mwQ = [(self.exp_time, self.IQpx[1]), (mwOff_time, self.IQ0[1])]
        #     #camera repeating sequence
        #     #cam = [(exp_time, 1), (cam_delay, 0)]
            
        #     # adding initial sequence to repeating sequence
        #     camcycles = (self.read_time - (self.read_time%frame_time)) / frame_time #counts total number of frames during the read time
        #     #import pdb; pdb.set_trace()
        #     for i in range(self.runs):        
        #         #laser += mwOnOff_laser
        #         mwI += mwOnOff_mwI
        #         mwQ += mwOnOff_mwQ
        #         for j in range(int(camcycles)):
        #             seq = [(exp_time, 1), (cam_delay, 0)]
        #             cam += seq
        #             laser += seq
        #         cam += [(self.read_time%frame_time, 0)]
        #         laser += [(self.read_time%frame_time, 1)]
                
        #         for j in range(int(camcycles)):
        #             seq = [(exp_time, 1), (cam_delay, 0)]
        #             cam += seq
        #             laser += seq
        #         cam += [(self.read_time%frame_time, 0)]
        #         laser += [(self.read_time%frame_time, 1)]
            
        #     # # Last clock to collect for the last point in the run        
        #     # laser += [(self.clock_time, 0)]
        #     # clock += [(self.clock_time, 1)]
        #     # mwI += [(self.clock_time, self.IQ0[0])]
        #     # mwQ += [(self.clock_time, self.IQ0[1])]
        #     # cam += [(self.clock, 0)]
            
        #     self.total_time += self.laser_lag + 2 * self.read_time*self.runs # + self.clock_time
        #     dchans = [self.channel_dict['laser'],self.channel_dict['clock'],self.channel_dict['camera']]
        #     achans = [0,1]
        #     dpatterns = [laser,cam]
        #     apatterns = [mwI,mwQ]

        #     self.sequence.setDigital(self.channel_dict['488'], laser)
        #     self.sequence.setDigital(self.channel_dict['camera'], cam)
        #     self.sequence.setAnalog(0, mwI)
        #     self.sequence.setAnalog(1, mwQ)    
            
        #     print('Finished setting up pulse sequence')
        #     print('self.sequence data:',  self.sequence.getData())
        #     #self.plotSeq(self.sequence.getData(),'CWUriMRnew')
        #     #self.plotSeq(dchans,achans,dpatterns,apatterns,'CWUriMRnew') #works
        #     return self.sequence

