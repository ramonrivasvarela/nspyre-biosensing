import numpy as np


from lantz.core import Driver
from lantz.drivers.swabian.pulsestreamer.lib.pulse_streamer_grpc import PulseStreamer,OutputState
#from lantz.drivers.swabian.pulsestreamer.lib.sequence import Sequence
from lantz.drivers.swabian.pulsestreamer.lib.Sequence import Sequence
#from lantz.drivers.swabian.pulsestreamer.grpc.pulse_streamer_grpc import PulseStreamer
#from lantz.drivers.swabian.pulsestreamer.sequence import Sequence
from lantz import Q_
from lantz import Action, Feat, DictFeat, ureg



class pulsesWF(Driver):
    '''

    RPyC: 
    Accessed by Spyrelet via RPyC protocol. This protocol provides a handle for the object-internal methods and variables
    only as pointers. Avoid sending objects back and forth, though primitives are ok, instead accessing necessary methods and variables 
    via object-internal means such as self.Pulser.method() or self.Pulser.variable. This is why we build all sequences in the driver, and 
    only access them through the Pulser self.sequences dictionary. 
    '''


    default_dict = {"clock": 0, "camera": 1, "405": 2, "488":3, "647": 4, "mirror": 5, "switch": 6, "laser": 7, "": None}

    def __init__(self, channel_dict = default_dict, ip="10.135.70.127"):
        super().__init__()
        self.channel_dict = {"clock": 0, "camera": 1, "405": 2, "488":3, "647": 4, "mirror": 5, "switch": 6, "laser": 7, "": None}  
        self.latest_streamed = None

        self.Pulser = PulseStreamer(ip)

        ### DEFINE ALL NECESSARY SEQUENCES:
        self.sequences = {}
        
        self.IQ0 = [-0.0025,-0.0025]
        self.IQpx = [0.4461,-.0025]#[0.4,-.005]
        self.IQnx = [-0.4922,-0.0025]#[-.435,-.0045]
        self.IQpy = [-0.0025,0.4772]#[-.0178,.4195]
        self.IQny = [-0.0025, -0.4838]
    @Feat()
    def has_sequence(self):
        """
        Has Sequence
        """
        return self.Pulser.hasSequence()
    
    @Action()
    def laser_on(self):
        return self.Pulser.constant(([3,6], 0.0, 0.0))
    
    @Action()
    def laser_off(self):
        return self.Pulser.constant(([6], 0.0, 0.0))

    def stream(self,seq_key,n_runs,mode = 'AM', SWITCH = True,LASER = False): 
        '''
        Microwave-safe(ish) streaming.
        Ought to transition to using the switch in the inverted regime: HI means PASS, LO (default) means BLOCK. This way we can ensure no microwaves are leaking through when not intended, and the switch is only on when we want microwaves.

        Sets the final state after streaming to ensure no microwave drive.
        '''
        seq = self.sequences.get(seq_key, None)
        if seq is None:
            print(f'Sequence {seq_key} not found. Please build sequence before streaming.')
            return
        
        digital_set = []
        if SWITCH:
            digital_set.append(self.channel_dict['switch'])
        if LASER:
            digital_set.append(self.channel_dict['laser'])
        Q_set = -1 if mode == 'AM' else 0
        self.Pulser.stream(seq,n_runs, final = OutputState(digital_set, Q_set,0))

    def prep_I1I2(self, label, exp, read, trig = 10e6, buff = 5e6, key = 'I1I2'):
        '''
        Fully general I1I2 Code. 
        AM Mode only.

        label: list of entries {t,0,1,2}:
        't': throwaway pulse (no microwave, no laser)
        0: background pulse (no microwave, laser)
        1: f1 pulse
        2: f2 pulse
        
        ex: "['t','t','t', 1, 0, 2, 0, 2, 0, 1, 0]"

        all codes not on this list will cause a warning and be ignored

        uw_duty and uw_rep are not added due to need to check switch operation frequency limits.
        '''
        experiment = self.Pulser.createSequence()

        pulse_len = exp+buff+read # Full pulse
        cam_off = exp + read + buff - trig # Full pulse minus trigger, for timing camera readout

        ## uwQ frequency modulation
        uwLeft = [(pulse_len,-1)] 
        uwRight = [(pulse_len,1)]
        ## Switch modulation
        switchOn = [(exp,0),(buff+read,1)]
        switchOff = [(pulse_len,1)]
        ## Cam and Laser pulse sequences
        cam_seq = [(trig,1), (cam_off,0)]
        laser_seq = [(exp,1),(buff+read,0)]
        off_seq = [(pulse_len, 0)] #laser & cam


        uwQ = []
        cam = []
        switch = []
        laser = []

        ## BUILD SEQUENCE 
        for i in range(len(label)):
            if label[i] == 't':            
            ## Throwaway
                uwQ += uwLeft
                cam += cam_seq
                switch += switchOff
                laser += laser_seq
            elif label[i] == 1 or label[i] == '1':
                uwQ += uwLeft
                cam += cam_seq
                switch += switchOn
                laser += laser_seq
            elif label[i] == 2 or label[i] == '2':
                uwQ += uwRight
                cam += cam_seq
                switch += switchOn
                laser += laser_seq
            elif label[i] == 0 or label[i] == '0':
                uwQ += uwRight
                cam += cam_seq
                switch += switchOff
                laser += laser_seq
            else:
                print(f'Warning, {label[i]} not a valid code. Skipping...')

        ## ORGANIZE CHANNELS and OUTPUT
        experiment.setAnalog(0, uwQ)
        experiment.setDigital(self.channel_dict['camera'], cam)
        experiment.setDigital(self.channel_dict['488'], laser)
        experiment.setDigital(self.channel_dict['switch'], switch)
        print('sequence prepared')
        self.sequences[key] = experiment
        # import pickle
        # Digitals = [(self.channel_dict['488'], laser), (self.channel_dict['camera'], cam), (self.channel_dict['switch'], switch)]
        # Analogs = [(0, uwQ)]
        # with open('Z:/dovetsky/current_seq.pkl', 'wb') as f:
        #     pickle.dump({'Digitals': Digitals, 'Analogs': Analogs}, f)

    def prep_ODMR(self, label, exp, read, trig = 10000000, buff = 5000000, 
               mode = 'QAM', uw_duty = 1, uw_rep = 50, key = 'ODMR', dim_throwaway = True): 
        '''
        Fully generalized WFODMR code.

        TIME inputs in ns

        label: list of entries {t,0,1,2}:
        't': throwaway pulse (no microwave, laser, sacrificial)
        0: background pulse (no microwave, laser)
        1: signal pulse
        
        ex: "['t', 1, 0, 1, 0]"

        mode: QAM for vector modulation (IQ mixer)
        mode: AM for analog modulation of amplitude

        SWITCH mode adds modulation via switch. 
        '''        
        experiment = self.Pulser.createSequence()

        pulse_len = exp+buff+read
        cam_off = exp + read + buff - trig
        ## uwQ frequency modulation
        if(mode == 'QAM'):
            uwQOff = [(pulse_len, self.IQ0[0])]
            uwIOff = [(pulse_len, self.IQ0[1])]
            if uw_duty == 1:
                uwQOn = [(exp, self.IQpx[0]), (read + buff, self.IQ0[0])]
                uwIOn = [(exp, self.IQpx[1]), (read + buff, self.IQ0[1])]
            else:
                on_time = exp*uw_duty/uw_rep # short duration uw pulse
                off_time = exp*(1-uw_duty)/uw_rep # short duration uw break
                uwQOn = [(on_time, self.IQpx[0]), (off_time, self.IQ0[0])]*uw_rep + [(read + buff, self.IQ0[0])]
                uwIOn = [(on_time, self.IQpx[1]), (off_time, self.IQ0[1])]*uw_rep + [(read + buff, self.IQ0[1])]
        elif(mode == 'AM'):
            uwQOff = [(pulse_len, -1)]
            if uw_duty == 1:
                uwQOn = [(exp, 0), (read + buff, -1)]
            else:
                on_time = exp*uw_duty/uw_rep # short duration uw pulse
                off_time = exp*(1-uw_duty)/uw_rep # short duration uw break
                uwQOn = [(on_time, 0), (off_time,-1)]*uw_rep + [(read + buff, -1)]
            uwIOff = []
            uwIOn = []
        ## Switch modulation
        switchOn = [(exp,0),(buff+read,1)] 
        switchOff = [(pulse_len, 1)]
        ## Cam and Laser pulse sequences
        cam_seq = [(trig,1), (cam_off,0)]
        laser_seq = [(exp,1),(buff+read,0)]
        off_seq = [(pulse_len, 0)] #laser & cam


        uwI = []
        uwQ = []
        cam = []
        switch = []
        laser = []

        #### BUILD SEQUENCE
        for i in range(len(label)):
            if label[i] == 't':            
            ## Throwaway
                uwQ += uwQOff
                uwI += uwIOff
                cam += cam_seq
                switch += switchOff
                if dim_throwaway: laser += off_seq
                else: laser += laser_seq
            elif label[i] == 1 or label[i] == '1':
                uwQ += uwQOn
                uwI += uwIOn
                cam += cam_seq
                switch += switchOn
                laser += laser_seq
            elif label[i] == 0 or label[i] == '0':
                uwQ += uwQOff
                uwI += uwIOff
                cam += cam_seq
                switch += switchOff
                laser += laser_seq
            else:
                print(f'Warning, {label[i]} not a valid code. Skipping...')

        # print('laser: ',laser)
        # print('cam: ', cam)
        # print('switch: ', switch)
        # print('uwQ: ', uwQ)
        # print('uwI: ', uwI)
        experiment.setDigital(self.channel_dict['488'], laser)
        experiment.setDigital(self.channel_dict['camera'], cam)
        experiment.setAnalog(0, uwQ)
        if (mode == 'QAM'):
            experiment.setAnalog(1, uwI)   
        experiment.setDigital(self.channel_dict['switch'], switch)

        print('Finished setting up pulse sequence')
        print('self.sequence data:',  experiment.getData())
        self.sequences[key] = experiment
        import pickle
        Digitals = [(self.channel_dict['488'], laser), (self.channel_dict['camera'], cam), (self.channel_dict['switch'], switch)]
        Analogs = [(0, uwQ)]
        if mode == 'QAM':
            Analogs.append((1, uwI))
        seq = {'Digitals': Digitals, 'Analogs': Analogs}
        with open('Z:/dovetsky/current_seq.pkl', 'wb') as f:
            pickle.dump(seq, f)
        print('saved seq as current_seq.pkl: ', seq)
    
    def prep_ODMR_legacy(self, runs, exp, read, trig = 10000000, buff = 5000000, mode = 'QAM', FT = True, mw_duty = 1, mw_rep = 50, key = 'main'):
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

        self.sequences[key] = experiment
        import pickle
        Digitals = [(self.channel_dict['488'], laser), (self.channel_dict['camera'], cam)]
        if mode == 'SWITCH':
            Digitals.append((self.channel_dict['switch'], switch))
        Analogs = [(0, mwI)]
        if mode == 'QAM':
            Analogs.append((1, mwQ))
        seq = {'Digitals': Digitals, 'Analogs': Analogs}
        with open('Z:/dovetsky/current_seq_legacy.pkl', 'wb') as f:
            pickle.dump(seq, f)
        print('saved seq as current_seq_legacy.pkl: ', seq)




    def prep_gain_seq(self, n, exp, read, trig = 10000000, buff = 5000000, key = 'gain'): 
        '''
        Quick n-pulse seq for optimizing gain
        no microwave
        '''        
        pulse_len = exp+buff+read
        cam_off = exp + read + buff - trig

        experiment = self.Pulser.createSequence()

        laser = [(pulse_len,1)] * n
        cam = [(trig,1), (cam_off,0)] * n
        

        experiment.setDigital(self.channel_dict['488'], laser)
        experiment.setDigital(self.channel_dict['camera'], cam) 

        print('Finished gain_seq:')
        print('laser: ',laser)
        print('cam: ', cam)
        print('self.sequence data:',  experiment.getData())
        print('---')

        self.sequences[key] = experiment




        
        
        