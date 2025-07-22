"""
Created on 5/30/2025 by Ramon Rivas
"""
import numpy as np
from math import sin, cos, radians, lcm
#from threed.data_and_plot import save_excel
import datetime as Dt

#REQUIRED IMPORT
from pulsestreamer import PulseStreamer, OutputState, Sequence



class PulserClass():


    
## Should change aom to laser
    def __init__(self, ip="10.135.70.127"):


        
        # create pulse streamer instance
        self.Pulser = PulseStreamer(ip)
        self.sequence = self.Pulser.createSequence()
        self.sub_sequence = self.Pulser.createSequence()
        self.green_laser_on=False
        self.blue_laser_on=False
        self.switch_on=False
        self.q_analog=0
        self.i_analog=0
        
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
        self.channel_dict = {"clock": 0, "camera": 1, "405": 2, "488":3, "647": 4, "mirror": 5, "switch": 6, "laser": 7, "": None}

    def change_state(self, dig_chan:list, q:float=0.0, i:float=0.0):
        """
        Change the state of the pulser.
        """
        self.blue_laser_on = False
        self.green_laser_on = False
        self.switch_on = False
        for chan in dig_chan:
            if chan==3:
                self.blue_laser_on = True
            if chan==7:
                self.green_laser_on = True
            if chan==6:
                self.switch_on = True
        self.q_analog = q
        self.i_analog = i

    
    
    def has_sequence(self):
        """
        Has Sequence
        """
        return self.Pulser.hasSequence()
    
    def create_sequence(self):
        """
        Create a new sequence object and return it.
        """
        sequence = self.Pulser.createSequence()
        return sequence

    def set_state(self, dig_chan, q=0.0, i=0.0):
        self.change_state(dig_chan, q, i)
        return self.Pulser.constant((dig_chan, q, i))
    
    def set_state_off(self):
        self.change_state([], 0, 0)
        return self.Pulser.constant(([], 0, 0))

    def stream(self, duration:int, dig_chans:list, i:float=0, q:float=0, n_runs:int=1):
        # Build sequence
        seq = self.Pulser.createSequence()
        for dig_chan in dig_chans:
            try:
                seq.setDigital(dig_chan, [(duration, 1)])
            except KeyError:
                raise ValueError(f"Digital channel {dig_chan} not found in channel dictionary.")
        seq.setAnalog(0, [(duration, i)])
        seq.setAnalog(1, [(duration, q)])

        # Update state
        #self.change_state(dig_chan, q, i)

        # Stream sequence
        self.Pulser.stream(
            seq,
            n_runs
            
        )

        # Final update
        #self.change_state(dig_chan, q, i)


    def stream_sequence(self, sequence:Sequence, n_runs:int=1):
        """
        Stream a sequence object for n_runs.
        WARNING: WILL NOT CHANGE self.blue_laser_on, self.green_laser_on, self.switch_on, self.q_analog, or self.i_analog.
        Use self.change_state() to change the state of the pulser before streaming.
        """
        self.Pulser.stream(sequence, n_runs)

    def flip_mirror(self, output=[], i=0, q=0, n_runs=1):
        pulse = [(1000000, [5], 0, 0)]
        self.change_state([], 0, 0)
        self.Pulser.stream(pulse, n_runs, final=OutputState(output, i, q))
        self.change_state(output, q, i)


    def stream_umOFF(self,seq,n_runs,AM = True, SWITCH = True): #for shutting off the microwave via AM and Switch
        digital_set = []
        if SWITCH:
            digital_set.append(self.channel_dict['switch'])
        analog_set = 0
        if AM:
            analog_set = -1
        self.Pulser.stream(seq,n_runs, final = OutputState(digital_set, analog_set,0))

    def reset(self):
        self.Pulser.reset()
        self.change_state([], 0, 0)

    def WFODMR(self, runs, ns_exp_time, ns_readout_time, trig = 10000000, buff = 5000000, mode = 'QAM', FT = True): 
        '''
        Fully generalized WFODMR code.

        TIME inputs in ns

        mode: QAM for vector modulation (IQ mixer)
        mode: AM for analog modulation of amplitude
        mode: SWITCH is AM mode but modulation is done entirely via a separate switch. There is no double modulation mode (AM+Switch), yet. 
        '''        
        if not FT:
            trig = ns_exp_time
        pulse_len = ns_exp_time+buff+ns_readout_time
        cam_off = ns_exp_time + ns_readout_time + buff - trig

        experiment = self.Pulser.createSequence()

        #### INITIAL THROWAWAY PULSE
        laser = [(pulse_len,0)]
        cam = [(trig,1), (cam_off,0)] #Check if need a lag for the camera
        if(mode == 'QAM'):
            mwI = [(pulse_len, self.IQ0[0])]
            mwQ = [(pulse_len, self.IQ0[1])]
            mwOnOff_mwI = [(ns_exp_time, self.IQpx[0]), (pulse_len + ns_readout_time + buff, self.IQ0[0])]
            mwOnOff_mwQ = [(ns_exp_time, self.IQpx[1]), (pulse_len + ns_readout_time + buff, self.IQ0[1])]
        elif(mode == 'AM'):
            ## NOTE IT SAYS mwI but it's actually Q that's plugged into A0
            mwI = [(pulse_len, -1)]
            mwOnOff_mwI = [(ns_exp_time, 0), (pulse_len + ns_readout_time + buff, -1)]
        elif(mode == 'SWITCH'):
            mwI = [(pulse_len, 0)]
            mwOnOff_mwI = [(2*pulse_len, 0)]
            switch = [(pulse_len, 1)]
            switchOnOff = [(ns_exp_time,0),(pulse_len+buff+ns_readout_time,1)]

        #### MAIN SEQUENCE

        cam_seq = [(trig,1), (cam_off,0)]
        laser_seq = [(ns_exp_time,1),(buff+ns_readout_time,0)]
        for i in range(runs):        
            #laser += mwOnOff_laser
            mwI += mwOnOff_mwI
            if mode == 'QAM':
                mwQ += mwOnOff_mwQ
            elif mode == 'SWITCH':
                switch += switchOnOff
            cam += cam_seq + cam_seq
            laser += laser_seq + laser_seq


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
    
    def pulse_setup(self, runs, mode,cam_trigger, ns_exp_time, ns_readout_time):#, mw_duty, mw_rep):
        #print('\n using sequence without wait time')
        seqs=[]
        if cam_trigger == 'EXTERNAL_EXPOSURE':
            seqs.append(self.WFODMR(runs, ns_exp_time, ns_readout_time,  mode = mode, FT = False))#, mw_duty = mw_duty, mw_rep = mw_rep))
        else:
            seqs.append(self.WFODMR(runs, ns_exp_time, ns_readout_time,10000000,5000000,mode))#, mw_duty = mw_duty, mw_rep = mw_rep))
        return seqs
    
    def pulse_for_widefield(self, runs, mode, cam_trigger, ns_exp_time, ns_readout_time, AM_mode = True, switch_mode = True):
        """
        Pulse sequence for widefield imaging.
        """
        if cam_trigger == 'External':
            pulse=self.WFODMR(runs, ns_exp_time, ns_readout_time,  mode = mode, FT = False)#, mw_duty = mw_duty, mw_rep = mw_rep))
        else:
            pulse=self.WFODMR(runs, ns_exp_time, ns_readout_time,10000000,5000000,mode)#, mw_duty = mw_duty, mw_rep = mw_rep))
        digital_set = []
        if switch_mode:
            digital_set.append(self.channel_dict['switch'])
        analog_set = 0
        if AM_mode:
            analog_set = -1
        self.Pulser.stream(pulse,runs, final = OutputState(digital_set, analog_set,0))

    