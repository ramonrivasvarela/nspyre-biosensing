"""
Created on 5/30/2025 by Ramon Rivas
"""
import numpy as np
from math import sin, cos, radians, lcm
import math
#from threed.data_and_plot import save_excel
import datetime as Dt
import pandas as pd

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

#### IQ params
        # Should change it according to crosstalk between I and Q, calibrated using oscilloscope. If no crosstalk should be 0.5 and 0
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
        self.Pulser.constant((dig_chan, q, i))
    
    def set_state_off(self):
        self.change_state([], 0, 0)
        self.Pulser.constant(([], 0, 0))

    def stream(
        self,
        couples: list[tuple[int, list[int]]],
        i: float = 0.0,
        q: float = 0.0,
        n_runs: int = 1,
    ) -> None:
        """
        Build and stream a pulse sequence.

        Args
        ----
        couples : list of (duration, digital_channels).
            Each tuple sets all `digital_channels` high for `duration` microseconds.
        i, q : float
            Analogue amplitudes (I and Q) applied for the *total* sequence length.
        n_runs : int
            How many times to replay the sequence (≥1).

        Raises
        ------
        ValueError
            If an unknown digital channel is requested or inputs are malformed.
        """
        if not couples:
            raise ValueError("`couples` must contain at least one (duration, chans) tuple.")

        if n_runs < 1:
            raise ValueError("`n_runs` must be ≥ 1.")

        seq = self.Pulser.createSequence()
        total_duration = 0.0  # accumulate to size analogue section correctly

        for duration, dig_chans in couples:
            if not isinstance(duration, (int, float)) or duration <= 0:
                raise ValueError(f"Invalid duration {duration}. Must be > 0 µs.")

            for dig_chan in dig_chans:
                try:
                    seq.setDigital(dig_chan, [(duration, 1)])
                except KeyError as exc:
                    raise ValueError(
                        f"Digital channel {dig_chan} not found in channel dictionary."
                    ) from exc

            total_duration += duration
            # (Optional) self.change_state(dig_chans, q=i, i=q)  # if tracking needed

        # Apply constant analogue levels for the full combined duration
        seq.setAnalog(0, [(total_duration, i)])
        seq.setAnalog(1, [(total_duration, q)])

        # Stream sequence
        self.Pulser.stream(seq, n_runs)

        # Reset internal state after streaming
        self.change_state([], 0.0, 0.0)

    def I1I2pulse(self,sideband_frequency, ns_read_time, ns_clock_time, runs):
        # seq, self.new_pulse_time= mgr.Pulser.odmr_temp_calib_no_bg(sideband_frequency, ns_read_time, ns_clock_time)
        IQleft = [0.355, 0.348]
        IQright = [0.357, 0.350]
        itty_bitty_time = 8
        freq_ns = sideband_frequency/ 1e9
        multiplier = math.lcm(round((1/freq_ns)),8)
        new_pulse_time = multiplier * int(ns_read_time/multiplier)
        print("New pulse time is " + str(new_pulse_time))
        num_samples = new_pulse_time /  itty_bitty_time
        print("num_samples is  " + str(num_samples))
        endpoint = freq_ns * (num_samples - 1) * itty_bitty_time

        pointsAO0 = np.linspace(0., float(endpoint), num = int(num_samples))
        pointsAO1 = np.linspace(0., float(endpoint), num = int(num_samples))
        seq_dict={'clock': [], 'laser': [], 'Q':[], 'I':[]}
        # Note that we have different amplitudes of sine waves for left and right sideband modulations from calibration
        for i in range(2):
            if i == 0:
                analog_ptsAO0, analog_ptsAO1 = np.cos(2*np.pi * pointsAO0), np.sin(2*np.pi * pointsAO1)
                zip_seqAO0 = [(itty_bitty_time,) * (int(num_samples)), tuple((IQleft[0] * analog_ptsAO0))]
                zip_seqAO1 = [(itty_bitty_time,) * (int(num_samples)), tuple((IQleft[1] * analog_ptsAO1))]

            elif i == 1:
                analog_ptsAO0, analog_ptsAO1 = np.sin(2*np.pi * pointsAO0), np.cos(2*np.pi * pointsAO1)
                zip_seqAO0 = [(itty_bitty_time,) * (int(num_samples)), tuple((IQright[0] * analog_ptsAO0))]
                zip_seqAO1 = [(itty_bitty_time,) * (int(num_samples)), tuple((IQright[1] * analog_ptsAO1))]

            seq_dict['Q'] += list(zip(*zip_seqAO0))
            seq_dict['I'] += list(zip(*zip_seqAO1))

            seq_dict['clock'] += [(ns_clock_time, 1), (new_pulse_time - ns_clock_time, 0)]
            seq_dict['laser'] += [(new_pulse_time, 1)]
        seq= self.make_seq(**seq_dict)
        return seq, new_pulse_time


    def stream_sequence(self, sequence:Sequence, n_runs:int=1, SWITCH:bool=True, AM:bool=False, CW:bool=False):
        """
        Stream a sequence object for n_runs.
        WARNING: WILL NOT CHANGE self.blue_laser_on, self.green_laser_on, self.switch_on, self.q_analog, or self.i_analog.
        Use self.change_state() to change the state of the pulser before streaming.

        If SWITCH or AM are true, then the relevant final states are implemented to keep the microwave off.
        If CW is true, then the laser is kept on throughout.
        """
        digital_set = []
        if SWITCH:
            digital_set.append(self.channel_dict['switch'])
        if CW:
            digital_set.append(self.channel_dict['laser'])
        analog_set = -1 if AM else 0
        self.Pulser.stream(sequence,n_runs, final = OutputState(digital_set, analog_set,0))
        self.change_state(digital_set, analog_set, 0)
    def stream_converted_sequence(self, seqs, n_runs):
        self.Pulser.stream(self.convert_sequence(seqs), n_runs)
    def convert_sequence(self, seqs):
         # 0-7 are the 8 digital channels
         # 8-9 are the 2 analog channels
        data = {}
        time = -0.01
        for seq in seqs:
            col = np.zeros(10)
            col[seq[1]] = 1
            col[8] = seq[2]
            col[9] = seq[3]
            init_time = time + 0.01
            data[init_time] = col
            time = time + seq[0]
            #data[prev_time_stamp + 0.01] = col
            data[time] = col
            #prev_time_stamp = seq[0]
        dft = pd.DataFrame(data)
        df = dft.T #transposes to have channels listed on vertical lines
        rev_dict={0: "clock", 1: "blue", 2: "SRS", 3: "NIR", 4: "gate1", 5: "gate2", 6: "gate3", 7: "laser", 8: "I", 9: "Q"}
        sub_df = df[list(rev_dict.keys())]
        fin = sub_df.rename(columns = rev_dict)
        return fin
    
    def flip_mirror(self, output=[], i=0, q=0, n_runs=1):
        pulse = [(1000000, [5], 0, 0)]
        self.Pulser.stream(pulse, n_runs, final=OutputState(output, i, q))
        self.change_state(output, q, i)

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
        if cam_trigger == 'EXTERNAL_EXPOSURE':
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
        self.change_state(digital_set, analog_set, 0)

# This method of making sequences runs into trouble with rpyc. Do not use.
    def make_seq(self, clock = None, camera = None, laser_405 =  None, laser_488 = None, laser_647 = None, mirror = None, switch = None, laser = None, Q = None, I = None):
        seq = self.Pulser.createSequence()
        if clock is not None:
            seq.setDigital(self.channel_dict['clock'], clock)
        if camera is not None:
            seq.setDigital(self.channel_dict['camera'], camera)
        if laser_405 is not None:
            seq.setDigital(self.channel_dict['405'], laser_405)
        if laser_488 is not None:
            seq.setDigital(self.channel_dict['488'], laser_488)
        if laser_647 is not None:
            seq.setDigital(self.channel_dict['647'], laser_647)
        if mirror is not None:
            seq.setDigital(self.channel_dict['mirror'], mirror)
        if switch is not None:
            seq.setDigital(self.channel_dict['switch'], switch)
        if laser is not None:
            seq.setDigital(self.channel_dict['laser'], laser)
        if Q is not None:
            seq.setAnalog(0, Q)
        if I is not None:
            seq.setAnalog(1, I)
        return seq



    def ODMRHeatDissipation(self, ns_read_time, ns_clock_duration, ns_laser_lag, runs ,  wait_time):  
        #Developed by Tian-Xing at 20230720, for trainsent ODMR on WSP, for avoiding the Singlet Fission
        # laser_recharge is not used here, since we want to 'wait' after both sg and bg
        print('now setting up pulse sequence')
        print('self.read_time:', ns_read_time)
        print('self.clock_time:',  ns_clock_duration)        
        #self.laser_lag
        #self.laserLag_time = 80 #hard coded for now
        
        # First block of the full seuqence, which is turnning on the laser
        laser = []
        clock = []
        mwI = []
        mwQ = []
        
        # Laser_lag repeating sequence
        Laser_lag_laser = [(ns_laser_lag, 1)]
        Laser_lag_clock = [(ns_laser_lag, 0)]
        Laser_lag_mwI = [(ns_laser_lag, self.IQ0[0])]
        Laser_lag_mwQ = [(ns_laser_lag, self.IQ0[1])]

        # mwOn repeating sequence
        # TX Note: not sure setting the readout clock like this will work, becaues the odmr_math in the dr_psNew spyrelet seems incompatible with this
        mwOn_laser = [(ns_read_time, 1)]
        mwOn_clock = [(ns_clock_duration,1),(ns_read_time-2*ns_clock_duration,0),(ns_clock_duration,1)]
        mwOn_mwI = [(ns_read_time, self.IQpx[0])]
        mwOn_mwQ = [(ns_read_time, self.IQpx[1])]


        # mwOff repeating sequence
        mwOff_laser = [(ns_read_time, 1)]
        mwOff_clock = [(ns_clock_duration,1),(ns_read_time-2*ns_clock_duration,0),(ns_clock_duration,1)]
        mwOff_mwI = [(ns_read_time, self.IQ0[0])]
        mwOff_mwQ = [(ns_read_time, self.IQ0[1])]
        
        
        # wait repeating sequence
        wait_laser = [(wait_time, 0)]
        wait_clock = [(wait_time, 0)]
        wait_mwI = [(wait_time, self.IQ0[0])]
        wait_mwQ = [(wait_time, self.IQ0[1])]
        

        # adding initial sequence to repeating sequence
        for i in range(runs):        
            laser += Laser_lag_laser + mwOn_laser + wait_laser + Laser_lag_laser + mwOff_laser + wait_laser
            clock += Laser_lag_clock + mwOn_clock + wait_clock + Laser_lag_clock + mwOff_clock + wait_clock
            mwI += Laser_lag_mwI + mwOn_mwI + wait_mwI + Laser_lag_mwI + mwOff_mwI + wait_mwI
            mwQ += Laser_lag_mwQ + mwOn_mwQ + wait_mwQ + Laser_lag_mwQ + mwOff_mwQ + wait_mwQ
        
        # Last clock to collect for the last point in the run
        # TX Note: Need to set this last clock to readout the current fluorescence value because in math_odmr, delta_buffer = array[1:] - array[0:-1]. We need to recored the fluorescence value for the last waiting window of each run        
        laser += [(ns_clock_duration, 0)]
        clock += [(ns_clock_duration, 1)]
        mwI += [(ns_clock_duration, self.IQ0[0])]
        mwQ += [(ns_clock_duration, self.IQ0[1])]

        ns_total_time = (2*ns_laser_lag + 2 * ns_read_time + 2*wait_time)*runs + ns_clock_duration
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
    
    def ODMRNoWait(self,  ns_read_time, ns_clock_duration, ns_laser_lag, runs , mode = 'QAM',):
        print('now setting up pulse sequence')
        print('self.read_time:', ns_read_time)
        print('self.clock_time:',  ns_clock_duration)        
        #self.laser_lag
        #self.laserLag_time = 80 #hard coded for now
        
        # First laser lag for first MWon signal
        laser = [(ns_laser_lag, 1)]
        clock = [(ns_laser_lag, 0)]
        if mode == 'QAM': 
            mwI = [(ns_laser_lag, self.IQ0[0])]
            mwQ = [(ns_laser_lag, self.IQ0[1])]
        else:
            mwI = [(ns_laser_lag, -1)]

        # mwOnOff repeating sequence
        mwOnOff_laser = [(ns_read_time, 1), (ns_read_time, 1)]
        if mode == 'QAM':
            mwOnOff_mwI = [(ns_read_time, self.IQpx[0]), (ns_read_time, self.IQ0[0])]
            mwOnOff_mwQ = [(ns_read_time, self.IQpx[1]), (ns_read_time, self.IQ0[1])]
        else:
            mwOnOff_mwI = [(ns_read_time, 0), (ns_read_time, -1)]
        mwOnOff_clock = [(ns_clock_duration,1),(ns_read_time-ns_clock_duration,0),(ns_clock_duration,1),(ns_read_time-ns_clock_duration,0)]

        # adding initial sequence to repeating sequence
        for i in range(runs):        
            laser += mwOnOff_laser
            clock += mwOnOff_clock
            mwI += mwOnOff_mwI
            if mode == 'QAM':
                mwQ += mwOnOff_mwQ
        
        # Last clock to collect for the last point in the run        
        laser += [(ns_clock_duration, 0)]
        clock += [(ns_clock_duration, 1)]
        if mode == 'QAM':
            mwI += [(ns_clock_duration, self.IQ0[0])]
            mwQ += [(ns_clock_duration, self.IQ0[1])]
        else:
            mwI += [(ns_clock_duration, -1)]

        # ns_total_time = ns_laser_lag + 2 * ns_read_time*runs + ns_clock_duration
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
    
    def odmr_temp_calib_no_bg(self, freq, ns_read_time, ns_clock_time):
        '''
        Shivam: Same as above but with no background measurements for normalization.
        '''
        print('self.read_time:', ns_read_time)
        print(' self.clock_time:',  ns_clock_time)
        # self.total_time = 0
        seq1, new_pulse_time = self.new_sideband_center(ns_read_time, ns_clock_time, freq, modulation = "left")
        seq2, new_pulse_time = self.new_sideband_center(ns_read_time, ns_clock_time, freq, modulation = "right")
        

        # self.total_time += 2 * ns_read_time
        
        return seq1 + seq2 , new_pulse_time
    
    def new_sideband_center(self, ns_pulse_time, ns_clock_time, frequency, modulation):
        '''
        This function produces one pulse_time pulse of a sideband modulation of frequency (generally 50 us)
        Modulation "left" and "right" indicate which direction to produce sideband peak.
        
        '''
        
        experiment = self.create_sequence()
        patternAO0, patternAO1 = [], []
        itty_bitty_time = 8
        freq_ns = frequency/ 1e9
        multiplier = math.lcm(round((1/freq_ns)),8)
        new_pulse_time = multiplier * int(ns_pulse_time/multiplier)
        print("New pulse time is " + str(new_pulse_time))
        num_samples = new_pulse_time /  itty_bitty_time
        print("num_samples is  " + str(num_samples))
        endpoint = freq_ns * (num_samples - 1) * itty_bitty_time

        pointsAO0 = np.linspace(0., float(endpoint), num = int(num_samples))
        pointsAO1 = np.linspace(0., float(endpoint), num = int(num_samples))

        # Note that we have different amplitudes of sine waves for left and right sideband modulations from calibration

        if modulation == "left":
            analog_ptsAO0, analog_ptsAO1 = np.cos(2*np.pi * pointsAO0), np.sin(2*np.pi * pointsAO1)
            zip_seqAO0 = [(itty_bitty_time,) * (int(num_samples)), tuple((self.IQleft[0] * analog_ptsAO0))]
            zip_seqAO1 = [(itty_bitty_time,) * (int(num_samples)), tuple((self.IQleft[1] * analog_ptsAO1))]

        elif modulation == "right":
            analog_ptsAO0, analog_ptsAO1 = np.sin(2*np.pi * pointsAO0), np.cos(2*np.pi * pointsAO1)
            zip_seqAO0 = [(itty_bitty_time,) * (int(num_samples)), tuple((self.IQright[0] * analog_ptsAO0))]
            zip_seqAO1 = [(itty_bitty_time,) * (int(num_samples)), tuple((self.IQright[1] * analog_ptsAO1))]

        

        patternAO0 += list(zip(*zip_seqAO0)) 
        patternAO1 += list(zip(*zip_seqAO1))

        patternClock = [(ns_clock_time, 1), (new_pulse_time - ns_clock_time, 0)]
        patternGreen = [(new_pulse_time, 1)]


        experiment.setAnalog(0, patternAO0)
        experiment.setAnalog(1, patternAO1)

        experiment.setDigital(self.channel_dict['clock'], patternClock)
        experiment.setDigital(self.channel_dict['laser'], patternGreen)

        return experiment, new_pulse_time
    
    def setup_no_wait(self, ns_laser_lag, ns_probe_time, ns_clock_duration, runs, mode, switch):
        '''
        Sets up the pulse sequence for ODMR without wait time. Returns the relevant instrument sequences as a dictionary
        '''
        IQ0 = [-0.0025,-0.0025]
        IQpx = [0.4461,-.0025]
        
        #if self.VERBOSE: 
        #    print('\n using sequence without wait time')
        #    print('self.read_time:', ns_probe_time)
        #    print('self.clock_time:',  ns_clock_duration)       
        #    print('self.laser_lag:', ns_laser_lag) 

        #### LASER LAG
        laser = [(ns_laser_lag, 1)]
        clock = [(ns_laser_lag, 0)]
        if mode == 'QAM': 
            mwQ = [(ns_laser_lag, IQ0[0])]
            mwI = [(ns_laser_lag, IQ0[1])]
        elif mode == 'AM':
            mwQ = [(ns_laser_lag, -1)]
        elif mode == 'NoMod':
            if not switch:
                raise ValueError('NoMod mode requires switch to be True')

        if switch:
            #if self.VERBOSE: print('using switch')
            switch = [(ns_laser_lag, 1)]


        #### (mwOnOff repeating sequence defn)
        mwOnOff_laser = [(ns_probe_time, 1), (ns_probe_time, 1)]
        if mode == 'QAM':
            mwOnOff_mwQ = [(ns_probe_time, IQpx[0]), (ns_probe_time, IQ0[0])]
            mwOnOff_mwI = [(ns_probe_time, IQpx[1]), (ns_probe_time, IQ0[1])]
        elif mode == 'AM':
            mwOnOff_mwQ = [(ns_probe_time, 0), (ns_probe_time, -1)]
        elif mode == 'NoMod':
            pass
        mwOnOff_clock = [(ns_clock_duration,1),(ns_probe_time-ns_clock_duration,0),(ns_clock_duration,1),(ns_probe_time-ns_clock_duration,0)]
        if switch:
            mwOnOff_switch = [(ns_probe_time, 0), (ns_probe_time, 1)]

        #### REPEATING MICROWAVE ON/OFF SEQUENCE
        for i in range(runs):        
            laser += mwOnOff_laser
            clock += mwOnOff_clock
            mwQ += mwOnOff_mwQ
            if mode == 'QAM':
                mwI += mwOnOff_mwI
            if switch:
                switch += mwOnOff_switch
        
        #### Last clock to collect for the last point in the run        
        laser += [(ns_clock_duration, 0)]
        clock += [(ns_clock_duration, 1)]
        if mode == 'QAM':
            mwQ += [(ns_clock_duration, IQ0[0])]
            mwI += [(ns_clock_duration, IQ0[1])]
        elif mode == 'AM':
            mwQ += [(ns_clock_duration, -1)] 
        elif mode == 'NoMod':
            pass
        if switch:
            switch += [(ns_clock_duration, 1)]
        
        #### FINALIZE
        #if self.VERBOSE:
        #    print('Finished setting up pulse sequence')

        seq_dict = {'clock': clock,'laser': laser}
        if mode == 'QAM':
            seq_dict['Q'] = mwQ
            seq_dict['I'] = mwI
        elif mode == 'AM':
            seq_dict['Q'] = mwQ
        elif mode == 'NoMod':
            pass

        if switch:
            seq_dict['switch'] = switch

        return seq_dict
        
    ## still need to change this to new method
    def setup_ODMR_wait(self, ns_laser_lag, ns_probe_time, ns_clock_duration, ns_cooldown_time, ns_pulsewait_time ,runs, mode, switch):
        '''
        Sets up the pulse sequence for ODMR without wait time. Returns the relevant instrument sequences as a dictionary
        '''
        
        IQ0 = [-0.0025,-0.0025]
        IQpx = [0.4461,-.0025]
        
        #if self.VERBOSE: 
        #    print('\n using sequence with wait time')
        #    print('self.read_time:', ns_probe_time)
        #    print('self.clock_time:',  ns_clock_duration)     
        #    print('self.cooldown_time:', ns_cooldown_time)  
        #    print('self.laser_lag:', ns_laser_lag) 
        #    print('self.pulsewait_time:', ns_pulsewait_time)

        #### LASER LAG
        laser = [(ns_laser_lag, 1)]
        clock = [(ns_laser_lag, 0)]
        if mode == 'QAM': 
            mwQ = [(ns_laser_lag, IQ0[0])]
            mwI = [(ns_laser_lag, IQ0[1])]
        elif mode == 'AM':
            mwQ = [(ns_laser_lag, -1)]
        elif mode == 'NoMod':
            if not switch:
                raise ValueError('NoMod mode requires switch to be True')

        #if switch:
            #if self.VERBOSE: print('using switch')
            switch = [(ns_laser_lag, 1)]


        #### (mwOnOff repeating sequence defn)
        mwOnOff_laser = [(ns_probe_time, 1), (ns_cooldown_time,0),
                          (ns_probe_time, 1), (ns_cooldown_time,0), (ns_pulsewait_time, 0)]
        if mode == 'QAM':
            mwOnOff_mwQ = [(ns_probe_time, IQpx[0]), 
                            (ns_probe_time + 2 * ns_cooldown_time + ns_pulsewait_time, IQ0[0])]
            mwOnOff_mwI = [(ns_probe_time, IQpx[1]), 
                           (ns_probe_time + 2 * ns_cooldown_time + ns_pulsewait_time, IQ0[1])]
        elif mode == 'AM':
            mwOnOff_mwQ = [(ns_probe_time, 0), 
                            (ns_probe_time + 2 * ns_cooldown_time + ns_pulsewait_time, -1)]
        elif mode == 'NoMod':
            pass
        mwOnOff_clock = [(ns_clock_duration,1),(ns_probe_time-2*ns_clock_duration,0),(ns_clock_duration,1), (ns_cooldown_time + ns_pulsewait_time, 0),
                         (ns_clock_duration,1),(ns_probe_time-2*ns_clock_duration,0),(ns_clock_duration,1), (ns_cooldown_time + ns_pulsewait_time, 0)]
        if switch:
            mwOnOff_switch = [(ns_probe_time, 0),
                               (ns_probe_time + 2 * ns_cooldown_time + ns_pulsewait_time, 1)]

        #### REPEATING MICROWAVE ON/OFF SEQUENCE
        for i in range(runs):        
            laser += mwOnOff_laser
            clock += mwOnOff_clock
            mwQ += mwOnOff_mwQ
            if mode == 'QAM':
                mwI += mwOnOff_mwI
            if switch:
                switch += mwOnOff_switch
        
        #### Last clock to collect for the last point in the run        
        laser += [(ns_clock_duration, 0)]
        clock += [(ns_clock_duration, 1)]
        if mode == 'QAM':
            mwQ += [(ns_clock_duration, IQ0[0])]
            mwI += [(ns_clock_duration, IQ0[1])]
        elif mode == 'AM':
            mwQ += [(ns_clock_duration, -1)] 
        elif mode == 'NoMod':
            pass
        if switch:
            switch += [(ns_clock_duration, 1)]
        
        #### FINALIZE
        #if self.VERBOSE:
        #    print('Finished setting up pulse sequence')

        seq_dict = {'clock': clock,'laser': laser}
        if mode == 'QAM':
            seq_dict['Q'] = mwQ
            seq_dict['I'] = mwI
        elif mode == 'AM':
            seq_dict['Q'] = mwQ
        elif mode == 'NoMod':
            pass

        if switch:
            seq_dict['switch'] = switch

        return seq_dict


    def setup_LPvT(self, ns_read_time, ns_clock_time, freq_array, num_freq = 4):
        print('ns_read_time: ', ns_read_time)
        print('ns_clock_time: ', ns_clock_time)
        print('num_freq: ', num_freq)
        print('freq_array:', freq_array)
        freq_ct = len(freq_array)
        if freq_ct != num_freq:
            print("\nWARNING\n\n, Hard Coded", num_freq, "frequencies to be used for ODMR Temperature Measurement.\n",
                  "frequency array of size greater or smaller was given to pulse streamer. \n\n")
        experiment = self.create_sequence()
        #patternNIR = [(self.heat_on, 1), (self.heat_off, 0)] * int((self.read_time)/(self.heat_off + self.heat_on)) 
        # Shivam: Green laser on for all frequency points       
        patternGreen = [(ns_read_time, 1)] * freq_ct * 2
        
        patternAO0, patternAO1 = [], []
        #list_for_num_freq = {'4': [0,3,1,2,2,1,3,0], '2': [0,1,1,0]}
        ## for idx in list_for_num_freq[str(num_freq)]:
        if freq_ct == 2:
            for idx in [0,1,1,0]:
                patternAO0 += self.sidebandPattern(ns_read_time, freq_array[idx], self.IQboth[0])
                patternAO1 += self.sidebandPattern(ns_read_time, freq_array[idx], self.IQboth[1], sine = True)
        if freq_ct == 4:
            for idx in [0,3,1,2,2,1,3,0]:
                patternAO0 += self.sidebandPattern(ns_read_time, freq_array[idx], self.IQboth[0]) 
                patternAO1 += self.sidebandPattern(ns_read_time, freq_array[idx], self.IQboth[1], sine = True)
            
        patternClock = freq_ct * [(ns_clock_time, 1), (ns_read_time - ns_clock_time, 0)]*2# + [(self.clock_time,1)]
        #dictionary:
        #default_digi_dict = {"clock": 0, "blue": 1, "SRS": 2, "NIR":3, "gate1": 4, "gate2": 5, "gate3": 6, "laser": 7, "": None}
        experiment.setDigital(self.channel_dict['clock'], patternClock)
        #self.sequence.setDigital(0, patternClock)
        #experiment.setDigital(self.channel_dict['NIR'], patternNIR)
        experiment.setDigital(self.channel_dict['laser'], patternGreen)
        experiment.setAnalog(0, patternAO0)
        experiment.setAnalog(1, patternAO1)
        self.total_time = ns_read_time * freq_ct * 2# + self.clock_time
        #import pdb; pdb.set_trace()
        return experiment
    
    def sidebandPattern(self, ns_pulse_time, frequency, IQ, sine = False):
        freq_ns = frequency / 1e9
        itty_bitty_time = 8
        num_samples = ns_pulse_time/itty_bitty_time
        endpoint = freq_ns * int(num_samples) * itty_bitty_time ##TIME ##set itty_bitty_time from here to nearest int
        points = np.linspace(0., float(endpoint), num = int(num_samples))
        analog_pts = np.cos(2*np.pi * points) if sine == False else np.sin(2*np.pi*points) ## freq_ns inside sinusoid
        zip_seq = [(itty_bitty_time,) * int(num_samples), tuple(IQ * analog_pts)]
        pattern = list(zip(*zip_seq))
        return pattern

    def odmr_center_create_sequence_IQ(self, odmr_span,sweep_time, clock_time, probe_time, laser_pause):
                # constants
        DT_NS = max(8, (int(sweep_time *1e4)//8)*8)
        print("DT_NS:", DT_NS)

        clock_time_ns = int(round(clock_time * 1e9))
        IQleft  = [0.355, 0.348]
        IQright = [0.357, 0.350]

        # probe_time rounded to a multiple of 8 ns
        number_bins   = max(1, int(round((probe_time * 1e9) / DT_NS)))
        probe_time_ns = number_bins * DT_NS

        # total points
        n_points = int(sweep_time // (probe_time_ns * 1e-9))
        sweep_time_ns = probe_time_ns * n_points

        # frequency values (GHz if odmr_span is in Hz; GHz*ns is unitless for phase)
        f_values = np.linspace(0.0, odmr_span * 1e-9, n_points * number_bins, dtype=np.float64)

        laser_pause_ns = int(round(laser_pause * 1e9))
        if laser_pause_ns < (probe_time_ns - clock_time_ns):
            # keep the warning but avoid printing in performance-critical paths if not needed
            print("Warning: laser pause time is less than probe_time - clock_time. "
                "Setting laser pause time to probe_time - clock_time")
            laser_pause_ns = probe_time_ns - clock_time_ns

        # ----- digital channels (lightweight list multiplications are fine) -----
        clock_pulse = [(clock_time_ns, 1), (probe_time_ns - clock_time_ns, 0)]  # one probe block
        laser = 4 * [(sweep_time_ns + clock_time_ns, 1), (laser_pause_ns, 0)]
        clock = 4 * (clock_pulse * n_points + [(clock_time_ns, 1), (laser_pause_ns, 0)])
        switch = 2 * [
            (sweep_time_ns + clock_time_ns, 1), (laser_pause_ns, 0),
            (sweep_time_ns + clock_time_ns, 0), (laser_pause_ns, 0)
        ]

        # ----- analog channels (vectorised) -----
        # Phase accumulates: phi_k = sum_{j<=k} 2π * f_j * DT_NS
        phi = (2.0 * np.pi * DT_NS) * np.cumsum(f_values)  # shape (N,)

        cos_phi = np.cos(phi)
        sin_phi = np.sin(phi)

        # Precompute amplitude arrays
        i_left_vals  = IQleft[1]  * cos_phi
        i_right_vals = IQright[1] * cos_phi
        q_left_vals  = -IQleft[0] * sin_phi
        q_right_vals =  IQright[0] * sin_phi

        # Convert to lists of (duration, value) tuples efficiently
        dur8 = np.full(phi.size, DT_NS, dtype=np.int64)

        # Using column_stack + map(tuple) is faster than Python loops for large N
        i_left  = list(map(tuple, np.column_stack((dur8, i_left_vals))))
        i_right = list(map(tuple, np.column_stack((dur8, i_right_vals))))
        q_left  = list(map(tuple, np.column_stack((dur8, q_left_vals))))
        q_right = list(map(tuple, np.column_stack((dur8, q_right_vals))))

        # Headers/tail segments unchanged
        i = (
            [(laser_pause_ns + clock_time_ns + sweep_time_ns, IQleft[1])]
            + i_left
            + [(2 * laser_pause_ns + 2 * clock_time_ns + sweep_time_ns, IQright[1])]
            + i_right
            + [(laser_pause_ns + clock_time_ns, IQright[1])]
        )

        q = (
            [(laser_pause_ns + clock_time_ns + sweep_time_ns, 0.0)]
            + q_left
            + [(2 * laser_pause_ns + 2 * clock_time_ns + sweep_time_ns, 0.0)]
            + q_right
            + [(laser_pause_ns + clock_time_ns, 0.0)]
        )

        # ----- build sequence -----
        seq = self.create_sequence()
        seq.setDigital(self.channel_dict['clock'], clock)
        seq.setDigital(self.channel_dict['laser'], laser)
        seq.setDigital(self.channel_dict['switch'], switch)
        seq.setAnalog(0, q)
        seq.setAnalog(1, i)

        return seq, n_points

    def odmr_center_create_sequence_FM(self, n_steps, odmr_span,sweep_time, clock_time, probe_time, laser_pause):

        clock_time_ns = int(round(clock_time * 1e9))
        probe_time_ns = int(round(probe_time * 1e9))
        
       
        
        # n_points = sweep_time_ns // probe_time_ns

        # frequency values (GHz if odmr_span is in Hz; GHz*ns is unitless for phase)
        q_values_up = np.linspace(0, 1, n_steps, dtype=np.float64)
        # q_values_down = np.linspace(0, -1, n_steps, dtype=np.float64)
        # ----- digital channels (lightweight list multiplications are fine) -----
        
        laser = [(probe_time_ns*(n_steps*4+1), 1)]
        clock = (n_steps*4+1)*[(clock_time_ns, 1), (probe_time_ns - clock_time_ns, 0)] 
        switch = 2*n_steps * [ (probe_time_ns, 1), (probe_time_ns, 0)] + [(probe_time_ns, 1)]
        q_channel=[(clock_time_ns, 0)]+[(2*probe_time_ns, val) for q in q_values_up for val in (q, -q)]+ [(probe_time_ns-clock_time_ns, 0)]

        # ----- analog channels (vectorised) -----
        # Phase accumulates: phi_k = sum_{j<=k} 2π * f_j * DT_NS
        
        print('q=', q_channel)
        print('clock=', clock)
        print('laser=', laser)
        print('switch=', switch)
        # ----- build sequence -----
        seq = self.create_sequence()
        seq.setDigital(self.channel_dict['clock'], clock)
        seq.setDigital(self.channel_dict['laser'], laser)
        seq.setDigital(self.channel_dict['switch'], switch)
        seq.setAnalog(0, q_channel)

        return seq, n_steps, probe_time_ns
    
        #         # constants
        # DT_NS = max(8, int(sweep_time*1e9 // (n_steps)))
        
        # print("DT_NS:", DT_NS)

        # clock_time_ns = int(round(clock_time * 1e9))
        # IQleft  = [0.355, 0.348]
        # IQright = [0.357, 0.350]

        # # probe_time rounded to a multiple of 8 ns
        # number_bins   = max(1, int(round((probe_time * 1e9) / DT_NS)))
        # probe_time_ns = number_bins * DT_NS

        # # total points
        # n_points = int(sweep_time // (probe_time_ns * 1e-9))
        # sweep_time_ns = probe_time_ns * n_steps*DT_NS

        # # frequency values (GHz if odmr_span is in Hz; GHz*ns is unitless for phase)
        # q_values_up = np.linspace(0.0, 1, n_steps, dtype=np.float64)
        # q_values_down = np.linspace(0, -1, n_steps, dtype=np.float64)
        # laser_pause_ns = int(round(laser_pause * 1e9))
        # if laser_pause_ns < (probe_time_ns - clock_time_ns):
        #     # keep the warning but avoid printing in performance-critical paths if not needed
        #     print("Warning: laser pause time is less than probe_time - clock_time. "
        #         "Setting laser pause time to probe_time - clock_time")
        #     laser_pause_ns = probe_time_ns - clock_time_ns

        # # ----- digital channels (lightweight list multiplications are fine) -----
        # clock_pulse = [(clock_time_ns, 1), (probe_time_ns - clock_time_ns, 0)]  # one probe block
        # laser = 4 * [(sweep_time_ns + clock_time_ns, 1), (laser_pause_ns, 0)]
        # clock = 4 * (clock_pulse * n_points + [(clock_time_ns, 1), (laser_pause_ns, 0)])
        # switch = 2 * [
        #     (sweep_time_ns + clock_time_ns, 1), (laser_pause_ns, 0),
        #     (sweep_time_ns + clock_time_ns, 0), (laser_pause_ns, 0)
        # ]

        # # ----- analog channels (vectorised) -----
        # # Phase accumulates: phi_k = sum_{j<=k} 2π * f_j * DT_NS
        

        # q_seq_up=[(DT_NS, q) for q in q_values_up]
        # q_seq_down=[(DT_NS, q) for q in q_values_down]
        # q_seq = q_seq_up +[(clock_time_ns, 1), (laser_pause_ns, 0)]+ q_seq_down+ [(clock_time_ns, -1), (laser_pause_ns, 0)]
        # # ----- build sequence -----
        # seq = self.create_sequence()
        # seq.setDigital(self.channel_dict['clock'], clock)
        # seq.setDigital(self.channel_dict['laser'], laser)
        # seq.setDigital(self.channel_dict['switch'], switch)
        # seq.setAnalog(0, q_seq)

        # return seq, n_points

    def odmr_center_create_sequence_FM_old(self, n_steps, odmr_span,sweep_time, clock_time, probe_time, laser_pause):
        DT_NS = max(8, int(sweep_time*1e9 // (n_steps)))
        
        print("DT_NS:", DT_NS)

        clock_time_ns = int(round(clock_time * 1e9))

        # probe_time rounded to a multiple of 8 ns
        number_bins   = max(1, int(round((probe_time * 1e9) / DT_NS)))
        probe_time_ns = number_bins * DT_NS

        # total points
        n_points = int(sweep_time // (probe_time_ns * 1e-9))
        # sweep_time_ns = n_steps * DT_NS
        sweep_time_ns = probe_time_ns *n_points
        n_steps=int(sweep_time_ns//DT_NS)
        # n_points = sweep_time_ns // probe_time_ns

        # frequency values (GHz if odmr_span is in Hz; GHz*ns is unitless for phase)
        q_values_up = np.linspace(0, 1, n_steps, dtype=np.float64)
        q_values_down = np.linspace(0, -1, n_steps, dtype=np.float64)
        laser_pause_ns = int(round(laser_pause * 1e9))
        if laser_pause_ns < (probe_time_ns - clock_time_ns):
            # keep the warning but avoid printing in performance-critical paths if not needed
            print("Warning: laser pause time is less than probe_time - clock_time. "
                "Setting laser pause time to probe_time - clock_time")
            laser_pause_ns = probe_time_ns - clock_time_ns

        # ----- digital channels (lightweight list multiplications are fine) -----
        clock_pulse = [(clock_time_ns, 1), (probe_time_ns - clock_time_ns, 0)]  # one probe block
        laser = 4 * [(sweep_time_ns + clock_time_ns, 1), (laser_pause_ns, 0)]
        clock = 4 * (clock_pulse * n_points + [(clock_time_ns, 1), (laser_pause_ns, 0)])
        switch = 2 * [
            (sweep_time_ns + clock_time_ns, 1), (laser_pause_ns, 0),
            (sweep_time_ns + clock_time_ns, 0), (laser_pause_ns, 0)
        ]

        # ----- analog channels (vectorised) -----
        # Phase accumulates: phi_k = sum_{j<=k} 2π * f_j * DT_NS
        

        q_seq_up=[(DT_NS, q) for q in q_values_up]
        q_seq_down=[(DT_NS, q) for q in q_values_down]
        q_seq = [(sweep_time_ns+clock_time_ns+laser_pause_ns, 0)]+q_seq_up +[(clock_time_ns, 1), (2*laser_pause_ns+sweep_time_ns+clock_time_ns, 0)]+ q_seq_down+ [(clock_time_ns, -1), (laser_pause_ns, 0)]
        print('q=', q_seq)
        print('clock=', clock)
        print('laser=', laser)
        print('switch=', switch)
        # ----- build sequence -----
        seq = self.create_sequence()
        seq.setDigital(self.channel_dict['clock'], clock)
        seq.setDigital(self.channel_dict['laser'], laser)
        seq.setDigital(self.channel_dict['switch'], switch)
        seq.setAnalog(0, q_seq)

        return seq, n_points, probe_time_ns
