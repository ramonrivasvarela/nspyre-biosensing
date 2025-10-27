import numpy as np
import pandas as pd
import math
# from math import sin, cos, radians
from lantz.core import Driver
#from lantz.drivers.swabian.pulsestreamer.lib.pulse_streamer_grpc import PulseStreamer
from lantz.drivers.swabian.pulsestreamer.lib.Sequence import Sequence
from lantz.drivers.swabian.pulsestreamer.lib.pulse_streamer_grpc import PulseStreamer
#from lantz.drivers.swabian.pulsestreamer.lib.sequence import Sequence
from lantz import Q_
from lantz import Action, Feat, DictFeat, ureg



class Pulses(Driver):

    
    #default_digi_dict = {"laser": "ch0", "offr_laser": "ch1", "EOM": "ch4", "CTR": "ch5", "switch": "ch6", "gate": "ch7", "": None}
    #default_digi_dict = {"laser": 0, "blue": 1, "SRS": 2, "VSG":3, "gate1": 4, "gate2": 5, "gate3": 6, "gate4": 7, "": None}
    #default_digi_dict = {"gate4": 0, "blue": 1, "SRS": 2, "VSG":3, "gate1": 4, "gate2": 5, "gate3": 6, "laser": 7, "": None}
    default_digi_dict = {"clock": 0, "blue": 1, "SRS": 2, "NIR":3, "gate1": 4, "gate2": 5, "gate3": 6, "laser": 7, "": None}
    rev_dict = {0: "clock", 1: "blue", 2: "SRS", 3: "NIR", 4: "gate1", 5: "gate2", 6: "gate3", 7: "laser", 8: "I", 9: "Q"}
    #rev_dict = {0: "laser", 1: "blue", 2: "SRS", 3: "VSG", 4: "gate1", 5: "gate2", 6: "gate3", 7: "gate4", 8: "I", 9: "Q"}
    
## Should change aom to laser
    def __init__(self, channel_dict = default_digi_dict, rev_dict = rev_dict, laser_time = 3.5*Q_(1,"us"), 
                 aom_lag = .73*Q_(1,"us"), aom_ramp = .15*Q_(1,"us"), readout_time = .4*Q_(1,"us"), 
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
        self.channel_dict = {"clock": 0, "cam": 1, "SRS": 2, "NIR":3, "gate1": 4, "gate2": 5, "gate3": 6, "laser": 7, "": None} #DAVID 10/1/24 - changed dict[1] to 'cam' from 'blue'
        #self.channel_dict = {"laser": 0, "blue": 1, "SRS": 2, "VSG":3, "gate1": 4, "gate2": 5, "gate3": 6, "gate4": 7, "": None}
        self._reverse_dict = rev_dict
        self.laser_time = int(round(laser_time.to("ns").magnitude))
        self.aom_lag = int(round(aom_lag.to("ns").magnitude))
        self.aom_ramp = int(round(aom_ramp.to("ns").magnitude))
        self.readout_time = int(round(readout_time.to("ns").magnitude))
        self.laser_buf = int(round(laser_buf.to("ns").magnitude))
        self.read_time = int(round(read_time.to("ns").magnitude))
        self.clock_time = int(round(clock_time.to("ns").magnitude))
        #self._normalize_IQ(IQ)
        self.Pulser = PulseStreamer(ip)
        print('creating sequence')
        self.sequence = Sequence()
        print('done creating sequence')
        self.latest_streamed = pd.DataFrame({})
        self.total_time = 0 #update when a pulse sequence is streamed
        self.high_res_freqs = [62500000, 41666667, 31250000, 25000000, 20833333, 17857143, 15625000, 13888889, 
                               12500000, 11363636, 10416667, 9615385, 8928571, 8333333, 7812500, 7352941, 
                               6944444, 6578947, 6250000, 5952381, 5681818, 5434783, 5208333, 5000000, 
                               4807692, 4629630, 4464286, 4310345, 4166667, 4032258, 3906250, 3787879,
                               3676471, 3571429, 3472222, 3378378, 3289474, 3205128, 3125000, 3048780, 
                               2976190, 2906977, 2840909, 2777778, 2717391, 2659574, 2604167, 2551020, 2500000]
        self.mid_res_freqs = [55555556, 37037037, 27777778, 22222222, 
                              18518519, 15873016, 13888889, 12345679, 
                              11111111, 10101010, 9259259, 8547009, 
                              7936508, 7407407, 6944444, 6535948, 
                              6172840, 5847953, 5555556, 5291005, 
                              5050505, 4830918, 4629630, 4444444, 
                              4273504, 4115226, 3968254, 3831418, 
                              3703704, 3584229, 3472222, 3367003, 
                              3267974, 3174603, 3086420, 3003003, 
                              2923977, 2849003, 2777778, 2710027, 
                              2645503, 2583979, 2525253, 2469136, 
                              2415459, 2364066, 2314815, 2267574, 2222222]
        self.low_res_freqs = [50000000, 33333333, 25000000, 20000000, 16666667, 
                              14285714, 12500000, 11111111, 10000000, 9090909, 
                              8333333, 7692308, 7142857, 6666667, 
                              6250000, 5882353, 5555556, 5263158, 5000000, 
                              4761905, 4545455, 4347826, 4166667, 
                              4000000, 3846154, 3703704, 3571429, 3448276, 
                              3333333, 3225806, 3125000, 3030303, 2941176, 
                              2857143, 2777778, 2702703, 2631579, 2564103, 
                              2500000, 2439024, 2380952, 2325581, 2272727, 
                              2222222, 2173913, 2127660, 2083333, 2040816, 2000000]

## Should change it according to crosstalk between I and Q. If no crosstalk should be 0.5 and 0
# Shivam: Check IQ0, IQboth, IQright, and IQleft values
        self.IQ0 = [-.0028,-0.0028]#[-.0177,-.0045]
        self.IQ = self.IQ0
        self.IQpx = [0.4461,-.0028]#[0.4,-.005]
        self.IQnx = [-0.4922,-0.0082]#[-.435,-.0045]
        self.IQpy = [-0.0231,0.4772]#[-.0178,.4195]
        self.IQny = [-2.31E-02, -0.4838]
        self.IQboth = [0.2, 0.2] #[0.500, 0.505]#[0.4355, 0.4667]  
        self.IQleft = [0.355, 0.348]
        self.IQright = [0.357, 0.350]

    
    @Feat()
    def has_sequence(self):
        """
        Has Sequence
        """
        return self.Pulser.hasSequence()
    
    @Action()
    def laser_on(self):
        return self.Pulser.constant(([7], 0.0, 0.0))

    def stream(self,seq,n_runs):
        self.latest_streamed = self.convert_sequence(seq)
        self.Pulser.stream(seq,n_runs)

    def clocksource(self,clk_src):
        self.Pulser.selectClock(clk_src)

    def _normalize_IQ(self, IQ):
        self.IQ = IQ/(2.5*np.linalg.norm(IQ))

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
        sub_df = df[list(self._reverse_dict.keys())]
        fin = sub_df.rename(columns = self._reverse_dict)
        return fin

    #IQ mod testing (getting side peaks when modulating IQ with a sinewave- 
                     #run with a sepectrum analyzer to see the peaks and ensure IQ is working well)
    def IQ_test(self, params, T):
        period = int(round(T.to("ns").magnitude))

        def single_test(time):
            stream = \
                [(1, [], 0,.4*np.cos(2*np.pi*time/period))]
            self.total_time = 1
            return stream
        
        seqs = [single_test(int(round(t))) for t in params]
        return seqs

    # one clock tick
    def Clock_tick(self):
        #clock_time = int(round(params).to('ns').magnitude)
        clock = \
            [(self.tick_time, [self.channel_dict["clock"]], *self.IQ0)]
        return clock
    
    # function to make a chopped laser during a period of time.
    # requires variable called self.seqs to allow for recursion.
    # this appends 
    def chopInit(self, time, channels, I, Q):
        pulse = []
        def chopMore(self, time, channels, I, Q):
            laser_pulse = \
                [(5, [self.channel_dict["laser"]] + channels, I, Q)]
            pulse += laser_pulse
            if time < 105:
                laser_wait = \
                    [(time - 5, [self.channel_dict["laser"]] + channels, I, Q)]
                pulse += laser_wait
                return pulse
            else:
                laser_wait = \
                    [(100, [self.channel_dict["laser"]] + channels, I, Q)]
                pulse += laser_wait
                chopMore(time, channels, I, Q)
    '''
    from fractions import Fraction
    from math import modf

    def simplest_fraction_in_interval(x, y):
        """Return the fraction with the lowest denominator in [x,y]."""
        if x == y:
            # The algorithm will not terminate if x and y are equal.
            raise ValueError("Equal arguments.")
        elif x < 0 and y < 0:
            # Handle negative arguments by solving positive case and negating.
            return -simplest_fraction_in_interval(-y, -x)
        elif x <= 0 or y <= 0:
            # One argument is 0, or arguments are on opposite sides of 0, so
            # the simplest fraction in interval is 0 exactly.
            return Fraction(0)
        else:
            # Remainder and Coefficient of continued fractions for x and y.
            xr, xc = modf(1/x);
            yr, yc = modf(1/y);
            if xc < yc:
                return Fraction(1, int(xc) + 1)
            elif yc < xc:
                return Fraction(1, int(yc) + 1)
            else:
                return 1 / (int(xc) + simplest_fraction_in_interval(xr, yr))

    def approximate_fraction(x, e):
        """Return the fraction with the lowest denominator that differs
        from x by no more than e."""
        return simplest_fraction_in_interval(x - e, x + e)
        
    '''




    'accepted sideband frequences'
    '''
    8 ns resolution
    [62500000.0, 41666666.666666664, 31250000.0, 25000000.0, 
    20833333.333333332, 17857142.85714286, 15625000.0, 13888888.888888888, 
    12500000.0, 11363636.363636363, 10416666.666666666, 9615384.615384616, 
    8928571.42857143, 8333333.333333333, 7812500.0, 7352941.176470588, 
    6944444.444444444, 6578947.368421053, 6250000.0, 5952380.952380952, 
    5681818.181818182, 5434782.608695652, 5208333.333333333, 5000000.0, 
    4807692.307692308, 4629629.62962963, 4464285.714285715, 4310344.827586207, 
    4166666.6666666665, 4032258.064516129, 3906250.0, 3787878.787878788,
    3676470.588235294, 3571428.5714285714, 3472222.222222222, 3378378.378378378, 
    3289473.6842105263, 3205128.205128205, 3125000.0, 3048780.487804878, 
    2976190.476190476, 2906976.7441860465, 2840909.090909091, 2777777.777777778, 
    2717391.304347826, 2659574.4680851065, 2604166.6666666665, 2551020.4081632653, 2500000.0]

    9 ns resolution
    [55555555.55555555, 37037037.03703704, 27777777.777777776, 22222222.222222224, 
    18518518.51851852, 15873015.873015873, 13888888.888888888, 12345679.01234568, 
    11111111.111111112, 10101010.1010101, 9259259.25925926, 8547008.547008548, 
    7936507.936507937, 7407407.407407408, 6944444.444444444, 6535947.712418301, 
    6172839.50617284, 5847953.216374269, 5555555.555555556, 5291005.291005291, 
    5050505.05050505, 4830917.874396135, 4629629.62962963, 4444444.444444444, 
    4273504.273504274, 4115226.3374485597, 3968253.9682539683, 3831417.624521073, 
    3703703.703703704, 3584229.3906810037, 3472222.222222222, 3367003.367003367, 
    3267973.8562091505, 3174603.1746031744, 3086419.75308642, 3003003.003003003, 
    2923976.6081871344, 2849002.849002849, 2777777.777777778, 2710027.100271003, 
    2645502.6455026455, 2583979.3281653747, 2525252.525252525, 2469135.8024691357, 
    2415458.9371980675, 2364066.193853428, 2314814.814814815, 2267573.6961451247, 2222222.222222222]

    10 ns resolution
    [50000000.0, 33333333.333333332, 25000000.0, 20000000.0, 16666666.666666666, 
    14285714.285714285, 12500000.0, 11111111.111111112, 10000000.0, 9090909.090909092, 
    8333333.333333333, 7692307.692307692, 7142857.142857143, 6666666.666666667, 
    6250000.0, 5882352.94117647, 5555555.555555556, 5263157.894736842, 5000000.0, 
    4761904.761904762, 4545454.545454546, 4347826.0869565215, 4166666.6666666665, 
    4000000.0, 3846153.846153846, 3703703.703703704, 3571428.5714285714, 3448275.8620689656, 
    3333333.3333333335, 3225806.4516129033, 3125000.0, 3030303.0303030303, 2941176.470588235, 
    2857142.8571428573, 2777777.777777778, 2702702.7027027025, 2631578.947368421, 2564102.564102564, 
    2500000.0, 2439024.3902439023, 2380952.380952381, 2325581.395348837, 2272727.272727273, 
    2222222.222222222, 2173913.0434782607, 2127659.574468085, 2083333.3333333333, 2040816.3265306123, 2000000.0]
    '''        

    def new_interanlSideband(self, pulse_times, freqArray, modulation = "left"):
        '''
        Written 05-11-2023 by Uri Zvi
        
        IMPORTANT!!! Before using this method change AO0 pulsestreamer output from Q SRS input to
        Analog Modulation input!
        
        This method is meant to use the internal Frequency Modulation (FM) function of the SG394.
        The carrier frequency and the modulation deviation is determined in advanced by user input
        in the appropriate spyrelet. This method accepts a pulseTarray and freqArray as and array of frequency deviations
        from the carriaer frequency, fc, and sets up a train of square pulses of frequency 
        1/pulseT Hz that switches between freequencies by changing the voltage of the square
        pulses. the max desired frequency deviation, w0, is mapped to voltage such that -w0 = -1V and w0 = 1V.
        
        Note that the deviation uses the internal FM function and is thus limited to the following ranges:
        fC ≤ 62.5 MHz:                      Smaller of fC or (64 MHz – fC)
        62.5 MHz < fC ≤ 126.5625 MHz        1 MHz
        126.5625 MHz < fC ≤ 253.1250 MHz    2 MHz
        253.1250 MHz < fC ≤ 506.25 MHz      4 MHz
        506.25 MHz < fC ≤ 1.0125 GHz        8 MHz
        1.0125 GHz < fC ≤ 2.025 GHz         16 MHz
        2.025 GHz < fC ≤ 4.050 GHz (SG394)  32 MHz
        
        It is recommanded to perform a quick calibration by setting AO0 to 1V with the desired w0 and check
        the output frequency. It is likely that w0 (or fc) should be adjusted such that 
        w0_calibrated/w0 = (fc+w0)/f_measured. Set this using the cal_factor 
        '''
        experiment = self.Pulser.createSequence()
        vArray = np.array(freqArray)/max(freqArray)
        pulseTarray = pulse_times
        patternClock, patternGreen = [], []
        
        zip_seqAO0 = [tuple(pulseTarray), tuple(vArray)]
        patternAO0 = list(zip(*zip_seqAO0))
        
        for pulse_time in pulseTarray:
            patternClock += [(self.clock_time, 1), (pulse_time - self.clock_time, 0)]
            patternGreen += [(pulse_time, 1)]

        experiment.setAnalog(0, patternAO0)
        experiment.setDigital(self.channel_dict['clock'], patternClock)
        experiment.setDigital(self.channel_dict['laser'], patternGreen)

        return experiment, new_pulse_time
    

    
    def new_sideband_center(self, pulse_time, frequency, modulation):
        '''
        This function produces one pulse_time pulse of a sideband modulation of frequency (generally 50 us)
        Modulation "left" and "right" indicate which direction to produce sideband peak.
        
        '''
        experiment = self.Pulser.createSequence()
        patternAO0, patternAO1 = [], []
        itty_bitty_time = 8
        freq_ns = frequency/ 1e9
        multiplier = math.lcm(round((1/freq_ns)),8)
        new_pulse_time = multiplier * int(pulse_time/multiplier)
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

        patternClock = [(self.clock_time, 1), (new_pulse_time - self.clock_time, 0)]
        patternGreen = [(new_pulse_time, 1)]


        experiment.setAnalog(0, patternAO0)
        experiment.setAnalog(1, patternAO1)

        experiment.setDigital(self.channel_dict['clock'], patternClock)
        experiment.setDigital(self.channel_dict['laser'], patternGreen)

        return experiment, new_pulse_time

    def sb_WF(self, pulse_time, frequency, modulation):
        '''
        This function produces one pulse_time pulse of a sideband modulation of frequency
        Modulation "left" and "right" indicate which direction to produce sideband peak.
        '''
        ##SETUP
        experiment = self.Pulser.createSequence()
        patternAO0, patternAO1 = [], []
        itty_bitty_time = 8
        freq_GHz = frequency/ 1e9
        multiplier = math.lcm(round((1/freq_GHz)),8) # DAVID: change to itty_bitty_time, probably?
        new_pulse_time = multiplier * int(pulse_time/multiplier) # DAVID: round down to nearest multiple of itty_bitty_time, I think
        print("New pulse time is " + str(new_pulse_time))
        num_samples = new_pulse_time /  itty_bitty_time #DAVID: This was done in such a strange order. 
        print("num_samples is  " + str(num_samples))
        endpoint = freq_GHz * (num_samples - 1) * itty_bitty_time

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

        patternClock = [(self.clock_time, 1), (new_pulse_time - self.clock_time, 0)]
        patternGreen = [(new_pulse_time, 1)]


        experiment.setAnalog(0, patternAO0)
        experiment.setAnalog(1, patternAO1)

        experiment.setDigital(self.channel_dict['clock'], patternClock)
        experiment.setDigital(self.channel_dict['laser'], patternGreen)

        return experiment, new_pulse_time

    def new_sideband_left(self, pulse_time, frequency, IQ, axis_angle = 0, phase = 90, dig_ch = [], clk = True):
        '''
        THIS METHOD WILL BE THE ALTERNATIVE ONE AND IS STILL IN PROGRESS
        '''
        experiment = self.Pulser.createSequence()
        patternAO0, patternAO1 = [], []
        
        freq_array = [frequency, frequency] # Needs to be fixed
        freq_ct = 2
        itty_bitty_time = 8

        multiplier = math.lcm(round((1/freq_array[0])*10**9),round((1/freq_array[1])*10**9),8) #multiplier in ns to determine pulse time with full periods
        print("my multiplier is: " + str(multiplier))
        new_pulse_time = multiplier * int(pulse_time/multiplier) # note that we remove 8 ns from the end of each pulse to prevent overlap
        print("the new pulse time is: ", str(new_pulse_time))
        print("freq 1 has ", str(new_pulse_time/round((1/freq_array[0])*10**9)), " periods")
        print("freq 2 has ", str(new_pulse_time/round((1/freq_array[1])*10**9)), " periods")
        seqAO = [0,1,1,0]
        for idx in seqAO:
            #import pdb; pdb.set_trace()
            freq_ns = freq_array[idx]/ 1e9
            num_samples = new_pulse_time/itty_bitty_time
            print("the sample number is: " + str(num_samples))
            newer_pulse_time = int(num_samples)*itty_bitty_time
            print("the newer pulse time is: ", str(newer_pulse_time))
            print("freq 1 has ", str(newer_pulse_time/round((1/freq_array[0])*10**9)), " periods")
            print("freq 2 has ", str(newer_pulse_time/round((1/freq_array[1])*10**9)), " periods")
            endpoint = freq_ns * (int(num_samples)-1) * itty_bitty_time ##TIME ##set itty_bitty_time from here to nearest int
            
            pointsAO0 = np.linspace(0., float(endpoint), num = int(num_samples)-1)
            pointsAO1 = np.linspace(0., float(endpoint), num = int(num_samples)-1)
            
            analog_ptsAO0, analog_ptsAO1 = np.cos(2*np.pi * pointsAO0), np.sin(2*np.pi * pointsAO1)#[:-1] #[:-1]
            zip_seqAO0 = [(itty_bitty_time,) * (int(num_samples)-1), tuple((self.IQboth[0] * analog_ptsAO0))]#-0.01
            zip_seqAO1 = [(itty_bitty_time,) * (int(num_samples)-1), tuple((self.IQboth[1] * analog_ptsAO1))]#-0.01
            patternAO0 += list(zip(*zip_seqAO0)) 
            patternAO1 += list(zip(*zip_seqAO1))

            patternClock = freq_ct * [(self.clock_time, 1), (newer_pulse_time - 8 - self.clock_time, 0)]*2
            patternGreen = [(newer_pulse_time - 8, 1)] * freq_ct * 2    
 
            experiment.setAnalog(0, patternAO0)
            experiment.setAnalog(1, patternAO1)

            experiment.setDigital(self.channel_dict['clock'], patternClock)
            experiment.setDigital(self.channel_dict['laser'], patternGreen)
 
        return experiment
    
    
    
    def sideband(self, pulse_time, frequency, IQ, axis_angle = 0, phase = 90, dig_ch = [], clk = True):
                          
        freq_ns = frequency / 1e9        
        itty_bitty_time = 8
        if round(frequency) in self.low_res_freqs:
            itty_bitty_time = 10
        elif round(frequency) in self.mid_res_freqs:
            itty_bitty_time = 9
        elif round(frequency) in self.high_res_freqs:
            itty_bitty_time = 8
        print('\n I chose a period for each analog sample as', itty_bitty_time)
        num_samples = pulse_time/itty_bitty_time
        
        # Shivam: endpoint gives an adjusted pulse time multiplied by frequency = end x position
        endpoint = freq_ns * int(num_samples) * itty_bitty_time #do we need the int()???
        # Shivam: New pulse time that is accurate for how long one frequency is delivered.
        new_pulse_time = int(num_samples) * itty_bitty_time * 10**(-9)
        print("This is the pulse time: " + str(new_pulse_time))
        print("Changes have been made")


       
        points = np.linspace(0., float(endpoint), num = int(num_samples))
      
        # import pdb; pdb.set_trace()
        # Shivam: axis_angle is not used for basic sideband modulation, set to 0.
        # Shivam: use points_I for both when you want theoretically aligned waves (if the PulseStreamer didn't have a lag)
        I_points = np.cos(2 * np.pi * points - radians(axis_angle))
        Q_points = np.cos(2 * np.pi * points - radians(axis_angle) + radians(phase))
        #print(I_points, '\n', 'followed by Q\n', Q_points)
        if clk == True:
            zip_seq = [(itty_bitty_time,) * int(num_samples),
                       (dig_ch + [self.channel_dict["clock"]],) + (dig_ch,) * (int(num_samples) - 1),
                       tuple(IQ[0] * I_points), tuple(IQ[1] * Q_points)]
        else:
            zip_seq = [(itty_bitty_time,) * int(num_samples), (dig_ch,) * (int(num_samples)),
                       tuple(IQ[0] * I_points), tuple(IQ[1] * Q_points)]
        sideband = list(zip(*zip_seq))
        return sideband, new_pulse_time
        
    def sidebandPattern(self, pulse_time, frequency, IQ, sine = False):
        freq_ns = frequency / 1e9
        itty_bitty_time = 8
        num_samples = pulse_time/itty_bitty_time
        endpoint = freq_ns * int(num_samples) * itty_bitty_time ##TIME ##set itty_bitty_time from here to nearest int
        points = np.linspace(0., float(endpoint), num = int(num_samples))
        analog_pts = np.cos(2*np.pi * points) if sine == False else np.sin(2*np.pi*points) ## freq_ns inside sinusoid
        zip_seq = [(itty_bitty_time,) * int(num_samples), tuple(IQ * analog_pts)]
        pattern = list(zip(*zip_seq))
        return pattern
        
    def setup_LPvT(self, freq_array, num_freq = 4):
        freq_ct = len(freq_array)
        if freq_ct != num_freq:
            print("\nWARNING\n\n, Hard Coded", num_freq, "frequencies to be used for ODMR Temperature Measurement.\n",
                  "frequency array of size greater or smaller was given to pulse streamer. \n\n")
        experiment = self.Pulser.createSequence()
        #patternNIR = [(self.heat_on, 1), (self.heat_off, 0)] * int((self.read_time)/(self.heat_off + self.heat_on)) 
        # Shivam: Green laser on for all frequency points       
        patternGreen = [(self.read_time, 1)] * freq_ct * 2
        
        patternAO0, patternAO1 = [], []
        #list_for_num_freq = {'4': [0,3,1,2,2,1,3,0], '2': [0,1,1,0]}
        ## for idx in list_for_num_freq[str(num_freq)]:
        if freq_ct == 2:
            for idx in [0,1,1,0]:
                patternAO0 += self.sidebandPattern(self.read_time, freq_array[idx], self.IQboth[0])
                patternAO1 += self.sidebandPattern(self.read_time, freq_array[idx], self.IQboth[1], sine = True)
        if freq_ct == 4:
            for idx in [0,3,1,2,2,1,3,0]:
                patternAO0 += self.sidebandPattern(self.read_time, freq_array[idx], self.IQboth[0]) 
                patternAO1 += self.sidebandPattern(self.read_time, freq_array[idx], self.IQboth[1], sine = True)
            
        patternClock = freq_ct * [(self.clock_time, 1), (self.read_time - self.clock_time, 0)]*2# + [(self.clock_time,1)]
        #dictionary:
        #default_digi_dict = {"clock": 0, "blue": 1, "SRS": 2, "NIR":3, "gate1": 4, "gate2": 5, "gate3": 6, "laser": 7, "": None}
        experiment.setDigital(self.channel_dict['clock'], patternClock)
        #self.sequence.setDigital(0, patternClock)
        #experiment.setDigital(self.channel_dict['NIR'], patternNIR)
        experiment.setDigital(self.channel_dict['laser'], patternGreen)
        experiment.setAnalog(0, patternAO0)
        experiment.setAnalog(1, patternAO1)
        self.total_time = self.read_time * freq_ct * 2# + self.clock_time
        #import pdb; pdb.set_trace()
        return experiment



    def odmr_temp_calib_old(self, freq, phi):
        '''
        Old one that Aidan had written.
        '''
        print('self.read_time:', self.read_time)
        print(' self.clock_time:',  self.clock_time)
        self.total_time = 0
        seq1, new_pulse_time = self.sideband(self.read_time, freq, self.IQboth, phase = phi, dig_ch = [self.channel_dict["laser"]], clk = True)
        seq2, new_pulse_time = self.sideband(self.read_time, freq, self.IQboth, phase = phi - 180, dig_ch = [self.channel_dict["laser"]], clk = True)
        clock2 = \
            [(self.clock_time, [self.channel_dict["clock"], self.channel_dict["laser"]], *self.IQ0)]
        unclock2 = \
            [((new_pulse_time - self.clock_time), [self.channel_dict["laser"]], *self.IQ0)]#self.channel_dict["laser"]
        #print("repepitition")
        self.total_time += 4 * self.read_time
        return seq1 + clock2 + unclock2 + seq2 + clock2 + unclock2, new_pulse_time
    

    def odmr_temp_calib(self, freq):
        '''
        Newer method for Alternate ODMR to obtain quasilinear slope for temperature measurements. On-off measurement method.
        Modulation "left" and "right" indicate which direction to produce sideband peak.
        We do left on, off, right on, off with n repeats
        '''
        print('self.read_time:', self.read_time)
        print(' self.clock_time:',  self.clock_time)
        self.total_time = 0
        seq1, new_pulse_time = self.new_sideband_center(self.read_time, freq, modulation = "left")
        seq2, new_pulse_time = self.new_sideband_center(self.read_time, freq, modulation = "right")
        # Off time generation
        off_seq = self.Pulser.createSequence()
        patternClock = [(self.clock_time, 1), (new_pulse_time - self.clock_time, 0)]
        patternGreen = [(new_pulse_time, 1)]
        patternAO0 = patternAO1 = [(new_pulse_time, 0)]

        off_seq.setDigital(self.channel_dict['clock'], patternClock)
        #self.sequence.setDigital(0, patternClock)
        #experiment.setDigital(self.channel_dict['NIR'], patternNIR)
        off_seq.setDigital(self.channel_dict['laser'], patternGreen)
        off_seq.setAnalog(0, patternAO0)
        off_seq.setAnalog(1, patternAO1)

        self.total_time += 4 * self.read_time
        
        return seq1 + off_seq + seq2 + off_seq, new_pulse_time
    
    def odmr_temp_calib_no_bg(self, freq):
        '''
        Shivam: Same as above but with no background measurements for normalization.
        '''
        print('self.read_time:', self.read_time)
        print(' self.clock_time:',  self.clock_time)
        self.total_time = 0
        seq1, new_pulse_time = self.new_sideband_center(self.read_time, freq, modulation = "left")
        seq2, new_pulse_time = self.new_sideband_center(self.read_time, freq, modulation = "right")
        

        self.total_time += 2 * self.read_time
        
        return seq1 + seq2 , new_pulse_time
        
        
    def hot_and_know_dummy(self, freq_array):
        self.total_time = 0
        experiment = Sequence()
        patternClock, patternGreen, patternAO0, patternAO1 = [(self.heat_time, 0)], [(self.heat_time, 0)], [(self.heat_time, 0)], [(self.heat_time, 0)]
        patternNIR = [(self.heat_init, 1)] + [(self.heat_off, 0), (self.heat_on, 1)] * int((self.heat_time - self.heat_init)/(self.heat_off + self.heat_on))
        patternAO0_sb, patternAO1_sb = [], []
        ##repeated for 1 second.
        for freq in freq_array:
            patternAO0_sb += self.sidebandPattern(self.read_time, freq, self.IQboth[0])
            patternAO1_sb += self.sidebandPattern(self.read_time, freq, self.IQboth[1], sine = True)
        condition = self.heat_time - self.heat_init
        while condition > 4 * self.read_time + self.wait_time:
            print('sideband pattern:', patternAO0_sb)
            patternAO0 += patternAO0_sb * int(1e9/(self.read_time * 4)) + [(self.wait_time, 0)]
            patternAO1 += patternAO1_sb * int(1e9/(self.read_time * 4)) + [(self.wait_time, 0)]
            patternClock += len(freq_array) * [(8, 1), (self.read_time - 8, 0)] + [(8, 1), (self.wait_time - 8, 0)]
            patternGreen += len(freq_array) * [(self.read_time, 1)] + [(self.wait_time, 0)]
            condition += -1 * (4 * self.read_time + self.wait_time)
        if condition > 4*self.read_time:            
            patternAO0 += patternAO0_sb * 1e9/(self.read_time * 4) 
            patternAO1 += patternAO1_sb * 1e9/(self.read_time * 4)
            patternClock += len(freq_array) * [(8, 1), (self.read_time - 8, 0), (8, 1)]
            patternGreen += len(freq_array) * [(self.read_time, 1)]
        #dictionary:
        #default_digi_dict = {"clock": 0, "blue": 1, "SRS": 2, "NIR":3, "gate1": 4, "gate2": 5, "gate3": 6, "laser": 7, "": None}
        experiment.setDigital(self.channel_dict['clock'], patternClock)
        #self.sequence.setDigital(0, patternClock)
        experiment.setDigital(self.channel_dict['NIR'], patternNIR)
        experiment.setDigital(self.channel_dict['laser'], patternGreen)
        experiment.setAnalog(0, patternAO0)
        experiment.setAnalog(1, patternAO1)
        return experiment
        
    def measureTemp(self, freq):
        self.total_time = 0; seq_point = []
        for f in freq:
            seq_point += self.sideband(self.read_time, f, self.IQboth, phase, dig_ch = [self.channel_dict['laser']], clk = True)
            self.total_time += self.read_time
        return seq_point
        
    def CWUriMR_sideband(self, freq, phi):
        '''remnant:
        # # # # # # clock1 = \
            # # # # # # [(self.clock_time, [self.channel_dict["clock"], self.channel_dict["laser"]], *self.IQpx)] #self.channel_dict["SRS"]], *self.IQ0)]
        # # # # # # unclock1 = \
            # # # # # # [((self.read_time - self.clock_time), [self.channel_dict["laser"]], *self.IQpx)] #self.channel_dict["SRS"]], *self.IQ0)]
        '''
        ## this is our ODMR sequence.
        ## we continually have the laser on
        ## we request data at the beginning of the microwave turning on and off.
        ## this results in us counting during these intervals. These last 50 us.
        print('self.read_time:', self.read_time)
        print(' self.clock_time:',  self.clock_time)
        self.total_time = 0
        seq1 = self.sideband(self.read_time, freq, self.IQboth, phase = phi, dig_ch = [self.channel_dict["laser"]], clk = True)
        clock2 = \
            [(self.clock_time, [self.channel_dict["clock"], self.channel_dict["laser"]], *self.IQ0)]
        unclock2 = \
            [((self.read_time - self.clock_time), [self.channel_dict["laser"]], *self.IQ0)]#self.channel_dict["laser"]
        #print("repepitition")
        self.total_time += 2 * self.read_time
        return seq1 + clock2 + unclock2
    
        
    def Diff_Pulsed_ODMR(self, pi):
        ## this is our pulsed ODMR sequence
        ## it uses the same read as ODMR, but it has
        ## well-defined reading intervals like rabi.
        
        ## first we define the pi time.
        pi_noround = pi.to("ns").magnitude
        pi_ns = int(round(pi.to("ns").magnitude))
        
        # init/readout setup
        ## we have the laser turn on time.
        aom_lag = \
            [(self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)]
        ## our read windows defined by the two following types of pulses.
        read_tick = \
            [(self.tick_time, [self.channel_dict["laser"], self.channel_dict["clock"]], *self.IQ0)]
        read_wait = \
            [(self.readout_time - self.tick_time, [self.channel_dict["laser"]], *self.IQ0)]
        ## and the remainder of our initialization time.
        init = \
            [(self.laser_time - self.tick_time - self.readout_time, [self.channel_dict["laser"]], *self.IQ0)]
        ## note, this laser buffer must include singlet decay time and laser lag.
        buffer = \
            [(self.aom_lag + self.singlet_decay, [], *self.IQ0)]
        setup = aom_lag + read_tick + read_wait + read_tick  + init + buffer
        setup_time = 2 * self.aom_lag + self.laser_time + self.singlet_decay
        # experiment
        pi_pulse = \
            [(pi_ns, [], *self.IQpx)]
        pi_pulse_D = \
            [(pi_ns, [], *self.IQ0)]
        ## we make sure to add a buffer so that the pulse truly lasts for pi time.
        ## delays in the signal generator / IQ mixer may cut it short without this adjustment.
        pulse_buffer = \
            [(self.laser_buf, [], *self.IQ0)]
        exp_seq1 = pi_pulse + pulse_buffer
        exp_seq2 = pi_pulse_D + pulse_buffer
        exp_time = pi_ns + self.laser_buf
        self.total_time = 2*(setup_time + exp_time)
        ## we return the bright state read window, then the dark state read window.
        ## the first value technically is garbage, but we do not care:
        ## we average each sequence over thousands of times.
        return setup + exp_seq1 + setup + exp_seq2
   
    def PS_rabi_sb(self, params, pi_xy, freq, phi = 90):
        ## this is our rabi sequence.
        ## we run a pi pulse, and then we measure the signal
        ## and reference counts we get from the NV.
        # # print('now in the driver')
        self.total_time = 0
        longest_time = params[-1]#int(round(params[-1]].to("ns").magnitude))
        ## we can measure the pi time on x and on y.
        ## they should be the same, but they technically
        ## have different offsets on our pulse streamer.
        if pi_xy == 'x':
            adjustment = 0
        else:
            adjustment = 90
        def single_PS_rabi(mw_on):
            ## these were for trouble shooting.
            # # print('MW time is now:', mw_on)
            # # print('driver aom_lag:', self.aom_lag)
            # # print('driver clock time:', self.clock_time)
            # # print('driver readout time:', self.readout_time)
            # # print('driver laser time:', self.laser_time)
            # # print('driver laser buffer:', self.laser_buf)
            wait = longest_time - mw_on
            #init/readout setup
            ## laser lag, then our clock windows. 
            ## the laser only initializing, the laser winding down,
            ## the pi pulse and its buffer, and a variable time to make sure
            ## each sequence is the same length.
            laser_rise = \
                [(self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)]
            clockL = \
                [(self.clock_time, [self.channel_dict["clock"], self.channel_dict["laser"]], *self.IQ0)]
            readInit = \
                [(self.readout_time - self.clock_time, [self.channel_dict["laser"]], *self.IQ0)]
            init = \
                [(self.laser_time - self.readout_time - self.clock_time - self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)]
                            
            read = \
                [(self.readout_time - self.clock_time - self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)]
            
            clockNoL = \
                [(self.clock_time, [self.channel_dict["clock"]], *self.IQ0)]
            laser_fall = \
                [(self.aom_lag + self.singlet_decay, [], *self.IQ0)]
            pi_pulse = self.sideband(mw_on, freq, self.IQboth, axis_angle = adjustment, phase = phi, clk = False)
            #print(pi_pulse)
            # mw_on time is added in the self.sideband() function
            MW_buffer = \
                [(self.mw_buf, [], *self.IQ0)]
            duty_cycle_balance  = \
                [(wait, [], *self.IQ0)]
            ## we put the pi pulse first so that all our counts are usable:
            ## as long as we initialize our counts before running any of this sequence.
            seq = pi_pulse + MW_buffer + laser_rise + clockL + readInit + clockL + init + laser_fall + duty_cycle_balance + laser_rise + clockL + readInit + clockL + init + laser_fall
            ## I make self.time_one to calculate the number of run_cts in spyrelet.
            self.time_one = (2*self.laser_time + 2* self.aom_lag + self.mw_buf + 2 * self.singlet_decay)+ longest_time
            self.total_time += self.time_one
            #print('aom lag is:', self.aom_lag)
            #print('laser time is:', self.laser_time)
            #print('laser buffer time is:', self.laser_buf)
            #print('total time from seq:', self.total_time)
            return seq
        
        
        ## we add an init before the first pi pulse to ensure the counts are good.
        seqs = [(self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)] + [(self.laser_time, [self.channel_dict["laser"]], *self.IQ0)] + [(self.aom_lag, [], *self.IQ0)]
        
        ##we concatenate all our single rabi pulses for each pi time.
        for mw_time in params:
            seqs += single_PS_rabi(mw_time)
        # # seqs = [single_PS_rabi(mw_time) for mw_time in params] #.array]
        
        ## we adjust total time.
        self.total_time += self.laser_time + 2*self.aom_lag
        return seqs
  
    def CPMG_Norm_sb(self,params,pi,pi2,n, sideband_freq, phi = 90):
        """
        for understanding how the CPMG part works, refer to CPMG4.
        In this sequence, I will document how the normalization works.
        """
        self.total_time = 0
        longest_time = params[-1]
        shortest_time = params[0]
        pi_noround = pi.to("ns").magnitude
        pi_ns = int(round(pi.to("ns").magnitude))
        pihalf_ns = int(round(pi2.to("ns").magnitude))
        
        
        def single_cpmg(tau):
            tau_rev_ns = int(round(longest_time + shortest_time - tau))
            if n > 0.5:
                tauspacing_ns = int(round(tau // n))
                taurevspacing_ns = int(round(tau_rev_ns // n))
                tauinit_ns = int(round(tau // (2*n)))
                taurevinit_ns = int(round(tau_rev_ns // (2*n)))
                #print("the time between pi pulses is", 1/n, "times the tau time")
            if n < 0.5:
                tauinit_ns = int(round(tau // 2))
                taurevinit_ns = int(round(tau_rev_ns // 2))
            #pi pulses
            pi_pulse = self.sideband(pi_ns, sideband_freq, self.IQboth, axis_angle = 90, phase = phi, clk = False)
            pihalf_pulse = self.sideband(pihalf_ns, sideband_freq, self.IQboth, phase = phi, clk = False)
            piminushalf_pulse = self.sideband(pihalf_ns, sideband_freq, self.IQboth, axis_angle = 180, phase = phi, clk = False)
            ## setup for reading
            aom_lag = \
                [(self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)]
            read_tick = \
                [(self.clock_time, [self.channel_dict["laser"], self.channel_dict["clock"]], *self.IQ0)]
            read_window = \
                [(self.readout_time - self.clock_time, [self.channel_dict["laser"]], *self.IQ0)]
            read_tick_buf = \
                [(self.clock_time, [self.channel_dict["clock"]], *self.IQ0)]
            init = \
                [(self.laser_time - self.clock_time - self.readout_time*2, [self.channel_dict["laser"]], *self.IQ0)]
            aom_buffer = \
                [(self.aom_lag - self.clock_time + self.singlet_decay, [], *self.IQ0)]
            setupSR = aom_lag + read_tick + read_window + read_tick + init + read_tick + read_window + read_tick_buf + aom_buffer
        
            self.setup_time = 2*self.aom_lag + self.laser_time + self.singlet_decay
            #experiment
            buffer = \
                [(self.laser_buf, [], *self.IQ0)]
            # reverse = \
            #     [(reverse_ns, [], *self.IQ)]
            tauinit = \
                [(tauinit_ns, [], *self.IQ0)]
            taurevinit = \
                [(taurevinit_ns, [], *self.IQ0)]
            middle = tauinit
            middle_rev = taurevinit
            middle_time = 0
            middlerev_time = 0
            if n > 0.5:
                middle = middle + pi_pulse 
                middle_time = middle_time + pi_ns 
                middle_rev = middle_rev + pi_pulse 
                middlerev_time = middlerev_time + pi_ns 
                if n > 1.5:
                    for i in range(n-1):
                        middle = middle + [(tauspacing_ns, [], *self.IQ0)] + pi_pulse 
                        middle_time = middle_time + pi_ns 
                        middle_rev = middle_rev + [(taurevspacing_ns, [], *self.IQ0)] + pi_pulse 
                        middlerev_time = middlerev_time + pi_ns 
            middle = middle + tauinit
            middle_time = middle_time
            middle_rev = middle_rev + taurevinit
            middlerev_time = middlerev_time
            echo = pihalf_pulse + middle + piminushalf_pulse + buffer
            echo_rev = pihalf_pulse + middle_rev + pihalf_pulse + buffer
            echo_time = middle_time + 2*pihalf_ns + tau + self.laser_buf
            echorev_time = middlerev_time + 2*pihalf_ns + tau_rev_ns + self.laser_buf
            self.total_time += echorev_time + echo_time + 2 * self.setup_time
            return echo + setupSR + echo_rev + setupSR
        def norm_seq():
            
            ## at the end of the sequence, we put a normalization sequence
            pi_pulse = self.sideband(pi_ns, sideband_freq, self.IQboth, axis_angle = 90, phase = phi, clk = False)
            wait = \
                [(self.mw_wait - self.aom_lag, [], *self.IQ0)]
            aom_lag = \
                [(self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)]
            read_tick = \
                [(self.clock_time, [self.channel_dict["laser"], self.channel_dict["clock"]], *self.IQ0)]
            read_window = \
                [(self.readout_time - self.clock_time, [self.channel_dict["laser"]], *self.IQ0)]
            init = \
                [(self.laser_time - self.clock_time - self.readout_time, [self.channel_dict["laser"]], *self.IQ0)]
            aom_buffer = \
                [(self.aom_lag, [], *self.IQ0)]
            buffer = \
                [(self.singlet_decay, [], *self.IQ0)]
            
            ## we set this to some short value because we do not need to re initialize here.
            zero_time = \
                [(100 - self.clock_time, [self.channel_dict["laser"]], *self.IQ0)]
            self.total_time += pi_ns + self.mw_wait + self.laser_time + 2 * self.aom_lag + self.singlet_decay + 100 + self.readout_time
            
            ## we run a pi pulse, wait, read the one state, wait for singlet, then read zero state.
            return (pi_pulse + wait + aom_lag + read_tick + read_window + read_tick + init + aom_buffer + buffer
                  + aom_lag + read_tick + read_window + read_tick + zero_time)
        ## initialize
        seqs = ([(self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)] + [(self.laser_time, [self.channel_dict["laser"]], *self.IQ0)] + [(self.aom_lag, [], *self.IQ0)])
        ## add all CPMG
        for tau_time in params:        
            seqs += single_cpmg(tau_time)
        ## we put the normalization at the very end of the sequences.    
        seqs += norm_seq()
        self.total_time += 2*self.aom_lag + self.laser_time
        print(self.total_time, "is the amount of time the sequence should take to run")
        ## this means one repeat will have len(tau_times) * data_ct * 8 + 4 reads.
        return seqs
        
        
    def AidanCPMG_sb(self,params,pi,pi2,n, sideband_freq, phi = 90):
        """
        We remove the reference reading windows, 
        so now we only read the signal.
        This means we will perform the operation 
        (F0 - F1)/(F0 + F1) for measuring dark state.
        We must reduce the read buckets in the spyrelet.
        
        We account for the heat gained 
        by the wire due to long pi pulse trains.
        """
        self.total_time = 0
        longest_time = params[-1]
        shortest_time = params[0]
        pi_ns = int(round(pi.to("ns").magnitude))
        pihalf_ns = int(round(pi2.to("ns").magnitude))
        
        
        def single_cpmg(tau):
            tau_rev_ns = int(round(longest_time + shortest_time - tau))
            if n > 0.5:
                tauspacing_ns = int(round(tau // n))
                taurevspacing_ns = int(round(tau_rev_ns // n))
                tauinit_ns = int(round(tau // (2*n)))
                taurevinit_ns = int(round(tau_rev_ns // (2*n)))
                #print("the time between pi pulses is", 1/n, "times the tau time")
            if n < 0.5:
                tauinit_ns = int(round(tau // 2))
                taurevinit_ns = int(round(tau_rev_ns // 2))
            #pi pulses
            pi_pulse = self.sideband(pi_ns, sideband_freq, self.IQboth, axis_angle = 90, phase = phi, clk = False)
            pihalf_pulse = self.sideband(pihalf_ns, sideband_freq, self.IQboth, phase = phi, clk = False)
            piminushalf_pulse = self.sideband(pihalf_ns, sideband_freq, self.IQboth, axis_angle = 180, phase = phi, clk = False)
            ## setup for reading
            aom_lag = \
                [(self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)]
            read_tick = \
                [(self.clock_time, [self.channel_dict["laser"], self.channel_dict["clock"]], *self.IQ0)]
            read_window = \
                [(self.readout_time - self.clock_time, [self.channel_dict["laser"]], *self.IQ0)]
            init = \
                [(self.laser_time - self.clock_time - self.readout_time, [self.channel_dict["laser"]], *self.IQ0)]
            aom_buffer = \
                [(self.aom_lag + self.singlet_decay, [], *self.IQ0)]
            setupSR = aom_lag + read_tick + read_window + read_tick + init + aom_buffer
        
            self.setup_time = 2*self.aom_lag + self.laser_time + self.singlet_decay
            
            ## initialize
            initialization = ([(self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)]
                            + [(self.laser_time, [self.channel_dict["laser"]], *self.IQ0)]
                            + [(self.aom_lag, [], *self.IQ0)])
            ## heat_wait
            heat_wait = \
                [(self.heat_decay, [], *self.IQ0)]
        
            #experiment
            buffer = \
                [(self.mw_wait, [], *self.IQ0)]
            # reverse = \
            #     [(reverse_ns, [], *self.IQ)]
            tauinit = \
                [(tauinit_ns, [], *self.IQ0)]
            taurevinit = \
                [(taurevinit_ns, [], *self.IQ0)]
            middle = tauinit
            middle_rev = taurevinit
            middle_time = tauinit_ns
            middlerev_time = taurevinit_ns
            if n > 0.5:
                middle = middle + pi_pulse 
                middle_time = middle_time + pi_ns 
                middle_rev = middle_rev + pi_pulse 
                middlerev_time = middlerev_time + pi_ns 
                if n > 1.5:
                    for i in range(n-1):
                        middle = middle + [(tauspacing_ns, [], *self.IQ0)] + pi_pulse 
                        middle_time = middle_time + pi_ns 
                        middle_rev = middle_rev + [(taurevspacing_ns, [], *self.IQ0)] + pi_pulse 
                        middlerev_time = middlerev_time + pi_ns 
            middle = middle + tauinit
            middle_time = middle_time + tauinit_ns
            middle_rev = middle_rev + taurevinit
            middlerev_time = middlerev_time + taurevinit_ns
            echo = pihalf_pulse + middle + piminushalf_pulse + buffer
            echo_rev = pihalf_pulse + middle_rev + pihalf_pulse + buffer
            echo_time = middle_time + 2*pihalf_ns + tau + self.mw_wait
            echorev_time = middlerev_time + 2*pihalf_ns + tau_rev_ns + self.mw_wait
            self.total_time += echorev_time + echo_time + 2 * (self.setup_time + 2*self.aom_lag + self.laser_time + self.heat_decay)
            return (initialization + echo + setupSR + heat_wait + initialization + echo_rev + setupSR + heat_wait)
        def norm_seq():
            
            ## at the end of the sequence, we put a normalization sequence
            pi_pulse = self.sideband(pi_ns, sideband_freq, self.IQboth, axis_angle = 90, phase = phi, clk = False)
            wait = \
                [(self.mw_wait - self.aom_lag, [], *self.IQ0)]
            aom_lag = \
                [(self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)]
            read_tick = \
                [(self.clock_time, [self.channel_dict["laser"], self.channel_dict["clock"]], *self.IQ0)]
            read_window = \
                [(self.readout_time - self.clock_time, [self.channel_dict["laser"]], *self.IQ0)]
            init = \
                [(self.laser_time - self.clock_time - self.readout_time, [self.channel_dict["laser"]], *self.IQ0)]
            aom_buffer = \
                [(self.aom_lag, [], *self.IQ0)]
            buffer = \
                [(self.singlet_decay, [], *self.IQ0)]
            
            ## we set this to some short value because we do not need to re initialize here.
            zero_time = \
                [(100 - self.clock_time, [self.channel_dict["laser"]], *self.IQ0)]
            self.total_time += pi_ns + self.mw_wait + self.laser_time + 2 * self.aom_lag + self.singlet_decay + 100 + self.readout_time
            
            ## we run a pi pulse, wait, read the one state, wait for singlet, then read zero state.
            return (pi_pulse + wait + aom_lag + read_tick + read_window + read_tick + init + aom_buffer + buffer
                  + aom_lag + read_tick + read_window + read_tick + zero_time)
        
        ## add all CPMG\
        seqs = []
        for tau_time in params:        
            seqs += single_cpmg(tau_time)
        ## we put the normalization at the very end of the sequences.    
        seqs += norm_seq()
        print(self.total_time, "is the amount of time the sequence should take to run")
        ## this means one repeat will have len(tau_times) * data_ct * 8 + 4 reads.
        return seqs
        
        
    def XY8_Norm_sb(self,params,pi_y,pi_x, pi_x_2, sideband_freq, phi = 90):
        """
        We run a sequence of 8 pi pulses
        pi half x, pi x, pi y, pi x, pi y, pi y, pi x, pi y, pi x, pi half x
        we need to know the pi time for x and y
        as well as the pi half time for x
        """
        self.total_time = 0
        longest_time = params[-1]
        shortest_time = params[0]
        pi_y_ns = int(round(pi_y.to("ns").magnitude))
        pi_x_ns = int(round(pi_x.to("ns").magnitude))
        pihalf_ns = int(round(pi_x_2.to("ns").magnitude))
        
        
        def single_XY8(tau):
            tau_rev_ns = int(round(longest_time + shortest_time - tau))
            tauspacing_ns = int(round(tau // 8))
            taurevspacing_ns = int(round(tau_rev_ns // 8))
            tauinit_ns = int(round(tau // (2*8)))
            taurevinit_ns = int(round(tau_rev_ns // (2*8)))
            #pi pulses
            pi_pulse_x = self.sideband(pi_x_ns, sideband_freq, self.IQboth, phase = phi, clk = False)
            pi_pulse_y = self.sideband(pi_y_ns, sideband_freq, self.IQboth, axis_angle = 90, phase = phi, clk = False)
            pihalf_pulse = self.sideband(pihalf_ns, sideband_freq, self.IQboth, phase = phi, clk = False)
            piminushalf_pulse = self.sideband(pihalf_ns, sideband_freq, self.IQboth, axis_angle = 180, phase = phi, clk = False)
            ## setup for reading
            aom_lag = \
                [(self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)]
            read_tick = \
                [(self.clock_time, [self.channel_dict["laser"], self.channel_dict["clock"]], *self.IQ0)]
            read_window = \
                [(self.readout_time - self.clock_time, [self.channel_dict["laser"]], *self.IQ0)]
            read_tick_buf = \
                [(self.clock_time, [self.channel_dict["clock"]], *self.IQ0)]
            init = \
                [(self.laser_time - self.clock_time - self.readout_time*2, [self.channel_dict["laser"]], *self.IQ0)]
            aom_buffer = \
                [(self.aom_lag - self.clock_time + self.singlet_decay, [], *self.IQ0)]
            setupSR = aom_lag + read_tick + read_window + read_tick + init + read_tick + read_window + read_tick_buf + aom_buffer
        
            self.setup_time = 2*self.aom_lag + self.laser_time + self.singlet_decay
            #experiment
            buffer = \
                [(self.laser_buf, [], *self.IQ0)]
            # reverse = \
            #     [(reverse_ns, [], *self.IQ)]
            tauinit = \
                [(tauinit_ns, [], *self.IQ0)]
            taurevinit = \
                [(taurevinit_ns, [], *self.IQ0)]
            tauspacer = \
                [(tauspacing_ns, [], *self.IQ0)]
            taurevspacer = \
                [(taurevspacing_ns, [], *self.IQ0)]
            echo = pihalf_pulse + tauinit + pi_pulse_x + tauspacer + pi_pulse_y + tauspacer \
                                          + pi_pulse_x + tauspacer + pi_pulse_y + tauspacer \
                                          + pi_pulse_y + tauspacer + pi_pulse_x + tauspacer \
                                          + pi_pulse_y + tauspacer + pi_pulse_x + tauinit + piminushalf_pulse + buffer
            echo_rev = pihalf_pulse + taurevinit + \
                       pi_pulse_x + taurevspacer + pi_pulse_y + taurevspacer + \
                       pi_pulse_x + taurevspacer + pi_pulse_y + taurevspacer + \
                       pi_pulse_y + taurevspacer + pi_pulse_x + taurevspacer + \
                       pi_pulse_y + taurevspacer + pi_pulse_x + taurevinit + pihalf_pulse + buffer
            echo_time = 4*pi_y_ns + 4*pi_x_ns + 2*pihalf_ns + tau + self.laser_buf #bright
            echorev_time = 4*pi_y_ns + 4*pi_x_ns + 2*pihalf_ns + tau_rev_ns + self.laser_buf #dark
            self.total_time += echorev_time + echo_time + 2 * self.setup_time
            return echo + setupSR + echo_rev + setupSR
        def norm_seq():
            
            ## at the end of the sequence, we put a normalization sequence
            pi_pulse = self.sideband(pi_x_ns, sideband_freq, self.IQboth, phase = phi, clk = False)
            wait = \
                [(self.mw_wait - self.aom_lag, [], *self.IQ0)]
            aom_lag = \
                [(self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)]
            read_tick = \
                [(self.clock_time, [self.channel_dict["laser"], self.channel_dict["clock"]], *self.IQ0)]
            read_window = \
                [(self.readout_time - self.clock_time, [self.channel_dict["laser"]], *self.IQ0)]
            init = \
                [(self.laser_time - self.clock_time - self.readout_time, [self.channel_dict["laser"]], *self.IQ0)]
            aom_buffer = \
                [(self.aom_lag, [], *self.IQ0)]
            buffer = \
                [(self.singlet_decay, [], *self.IQ0)]
            
            ## we set this to some short value because we do not need to re initialize here.
            zero_time = \
                [(100 - self.clock_time, [self.channel_dict["laser"]], *self.IQ0)]
            self.total_time += pi_x_ns + self.mw_wait + self.laser_time + 2 * self.aom_lag + self.singlet_decay + 100 + self.readout_time
            
            ## we run a pi pulse, wait, read the one state, wait for singlet, then read zero state.
            return (pi_pulse + wait + aom_lag + read_tick + read_window + read_tick + init + aom_buffer + buffer
                  + aom_lag + read_tick + read_window + read_tick + zero_time)
        ## initialize
        seqs = ([(self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)] + [(self.laser_time, [self.channel_dict["laser"]], *self.IQ0)] + [(self.aom_lag, [], *self.IQ0)])
        ## add all CPMG
        for tau_time in params:        
            seqs += single_XY8(tau_time)
        ## we put the normalization at the very end of the sequences.    
        seqs += norm_seq()
        self.total_time += 2*self.aom_lag + self.laser_time
        print(self.total_time, "is the amount of time the sequence should take to run")
        ## this means one repeat will have len(tau_times) * data_ct * 8 + 4 reads.
        return seqs
        
    def AidanXY8_sb(self,params,pi_y,pi_x, pi_x_2, sideband_freq, phi = 90):
        """
        We run a sequence of 8 pi pulses
        pi half x, pi x, pi y, pi x, pi y, pi y, pi x, pi y, pi x, pi half x
        we need to know the pi time for x and y
        as well as the pi half time for x
        """
        self.total_time = 0
        longest_time = params[-1]
        shortest_time = params[0]
        pi_y_ns = int(round(pi_y.to("ns").magnitude))
        pi_x_ns = int(round(pi_x.to("ns").magnitude))
        pihalf_ns = int(round(pi_x_2.to("ns").magnitude))
        
        
        def single_XY8(tau):
            tau_rev_ns = int(round(longest_time + shortest_time - tau))
            tauspacing_ns = int(round(tau // 8))
            taurevspacing_ns = int(round(tau_rev_ns // 8))
            tauinit_ns = int(round(tau // (2*8)))
            taurevinit_ns = int(round(tau_rev_ns // (2*8)))
            #pi pulses
            pi_pulse_x = self.sideband(pi_x_ns, sideband_freq, self.IQboth, phase = phi, clk = False)
            pi_pulse_y = self.sideband(pi_y_ns, sideband_freq, self.IQboth, axis_angle = 90, phase = phi, clk = False)
            pihalf_pulse = self.sideband(pihalf_ns, sideband_freq, self.IQboth, phase = phi, clk = False)
            piminushalf_pulse = self.sideband(pihalf_ns, sideband_freq, self.IQboth, axis_angle = 180, phase = phi, clk = False)
            ## setup for reading
            aom_lag = \
                [(self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)]
            read_tick = \
                [(self.clock_time, [self.channel_dict["laser"], self.channel_dict["clock"]], *self.IQ0)]
            read_window = \
                [(self.readout_time - self.clock_time, [self.channel_dict["laser"]], *self.IQ0)]
            read_tick_buf = \
                [(self.clock_time, [self.channel_dict["clock"]], *self.IQ0)]
            init = \
                [(self.laser_time - self.clock_time - self.readout_time, [self.channel_dict["laser"]], *self.IQ0)]
            aom_buffer = \
                [(self.aom_lag + self.singlet_decay, [], *self.IQ0)]
            setupSR = aom_lag + read_tick + read_window + read_tick + init + aom_buffer
        
            self.setup_time = 2*self.aom_lag + self.laser_time + self.singlet_decay
            
            ## initialize
            initialization = ([(self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)]
                            + [(self.laser_time, [self.channel_dict["laser"]], *self.IQ0)]
                            + [(self.aom_lag, [], *self.IQ0)])
            ## heat_wait
            heat_wait = \
                [(self.heat_decay, [], *self.IQ0)]
        
            #experiment
            buffer = \
                [(self.mw_wait, [], *self.IQ0)]
            # reverse = \
            #     [(reverse_ns, [], *self.IQ)]
            tauinit = \
                [(tauinit_ns, [], *self.IQ0)]
            taurevinit = \
                [(taurevinit_ns, [], *self.IQ0)]
            tauspacer = \
                [(tauspacing_ns, [], *self.IQ0)]
            taurevspacer = \
                [(taurevspacing_ns, [], *self.IQ0)]
            echo = pihalf_pulse + tauinit + pi_pulse_x + tauspacer + pi_pulse_y + tauspacer \
                                          + pi_pulse_x + tauspacer + pi_pulse_y + tauspacer \
                                          + pi_pulse_y + tauspacer + pi_pulse_x + tauspacer \
                                          + pi_pulse_y + tauspacer + pi_pulse_x + tauinit + piminushalf_pulse + buffer
            echo_rev = pihalf_pulse + taurevinit + \
                       pi_pulse_x + taurevspacer + pi_pulse_y + taurevspacer + \
                       pi_pulse_x + taurevspacer + pi_pulse_y + taurevspacer + \
                       pi_pulse_y + taurevspacer + pi_pulse_x + taurevspacer + \
                       pi_pulse_y + taurevspacer + pi_pulse_x + taurevinit + pihalf_pulse + buffer
            echo_time = 4*pi_y_ns + 4*pi_x_ns + 2*pihalf_ns + tauspacing_ns + self.mw_wait #dark
            echorev_time = 4*pi_y_ns + 4*pi_x_ns + 2*pihalf_ns + taurevspacing_ns + self.mw_wait #bright
            self.total_time += echorev_time + echo_time + 2 * (self.setup_time + 2*self.aom_lag + self.laser_time + self.heat_decay)
            return (initialization + echo + setupSR + heat_wait + initialization + echo_rev + setupSR + heat_wait)
        def norm_seq():
            
            ## at the end of the sequence, we put a normalization sequence
            pi_pulse = self.sideband(pi_x_ns, sideband_freq, self.IQboth, phase = phi, clk = False)
            wait = \
                [(self.mw_wait - self.aom_lag, [], *self.IQ0)]
            aom_lag = \
                [(self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)]
            read_tick = \
                [(self.clock_time, [self.channel_dict["laser"], self.channel_dict["clock"]], *self.IQ0)]
            read_window = \
                [(self.readout_time - self.clock_time, [self.channel_dict["laser"]], *self.IQ0)]
            init = \
                [(self.laser_time - self.clock_time - self.readout_time, [self.channel_dict["laser"]], *self.IQ0)]
            aom_buffer = \
                [(self.aom_lag, [], *self.IQ0)]
            buffer = \
                [(self.singlet_decay, [], *self.IQ0)]
            
            ## we set this to some short value because we do not need to re initialize here.
            zero_time = \
                [(100 - self.clock_time, [self.channel_dict["laser"]], *self.IQ0)]
            self.total_time += pi_x_ns + self.mw_wait + self.laser_time + 2 * self.aom_lag + self.singlet_decay + 100 + self.readout_time
            
            ## we run a pi pulse, wait, read the one state, wait for singlet, then read zero state.
            return (pi_pulse + wait + aom_lag + read_tick + read_window + read_tick + init + aom_buffer + buffer
                  + aom_lag + read_tick + read_window + read_tick + zero_time)
        ## initialize
        seqs = []
        ## add all CPMG
        for tau_time in params:        
            seqs += single_XY8(tau_time)
        ## we put the normalization at the very end of the sequences.    
        seqs += norm_seq()
        print(self.total_time, "is the amount of time the sequence should take to run")
        ## this means one repeat will have len(tau_times) * data_ct * 8 + 4 reads.
        return seqs    
        
    def YY8_Norm_sb(self,params,pi_y,pi_y_2, sideband_freq, phi = 90):
        """
        We run a sequence of 8 pi pulses
        pi half x, pi x, pi y, pi x, pi y, pi y, pi x, pi y, pi x, pi half x
        we need to know the pi time for x and y
        as well as the pi half time for x
        """
        self.total_time = 0
        longest_time = params[-1]
        shortest_time = params[0]
        pi_y_ns = int(round(pi_y.to("ns").magnitude))
        pihalf_ns = int(round(pi_y_2.to("ns").magnitude))
        
        
        def single_YY8(tau):
            tau_rev_ns = int(round(longest_time + shortest_time - tau))
            tauspacing_ns = int(round(tau // 8))
            taurevspacing_ns = int(round(tau_rev_ns // 8))
            tauinit_ns = int(round(tau // (2*8)))
            taurevinit_ns = int(round(tau_rev_ns // (2*8)))
            #pi pulses
            pi_pulse_y = self.sideband(pi_y_ns, sideband_freq, self.IQboth, axis_angle = 90, phase = phi, clk = False)
            pi_pulse_yneg = self.sideband(pi_y_ns, sideband_freq, self.IQboth, axis_angle = 270, phase = phi, clk = False)
            pihalf_pulse = self.sideband(pihalf_ns, sideband_freq, self.IQboth, axis_angle = 90, phase = phi, clk = False)
            piminushalf_pulse = self.sideband(pihalf_ns, sideband_freq, self.IQboth, axis_angle = 270, phase = phi, clk = False)
            ## setup for reading
            aom_lag = \
                [(self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)]
            read_tick = \
                [(self.clock_time, [self.channel_dict["laser"], self.channel_dict["clock"]], *self.IQ0)]
            read_window = \
                [(self.readout_time - self.clock_time, [self.channel_dict["laser"]], *self.IQ0)]
            read_tick_buf = \
                [(self.clock_time, [self.channel_dict["clock"]], *self.IQ0)]
            init = \
                [(self.laser_time - self.clock_time - self.readout_time*2, [self.channel_dict["laser"]], *self.IQ0)]
            aom_buffer = \
                [(self.aom_lag - self.clock_time + self.singlet_decay, [], *self.IQ0)]
            setupSR = aom_lag + read_tick + read_window + read_tick + init + read_tick + read_window + read_tick_buf + aom_buffer
        
            self.setup_time = 2*self.aom_lag + self.laser_time + self.singlet_decay
            #experiment
            buffer = \
                [(self.laser_buf, [], *self.IQ0)]
            # reverse = \
            #     [(reverse_ns, [], *self.IQ)]
            tauinit = \
                [(tauinit_ns, [], *self.IQ0)]
            taurevinit = \
                [(taurevinit_ns, [], *self.IQ0)]
            tauspacer = \
                [(tauspacing_ns, [], *self.IQ0)]
            taurevspacer = \
                [(taurevspacing_ns, [], *self.IQ0)]
            echo = pihalf_pulse + tauinit + pi_pulse_yneg + tauspacer + pi_pulse_y + tauspacer \
                                          + pi_pulse_y + tauspacer + pi_pulse_yneg + tauspacer \
                                          + pi_pulse_yneg + tauspacer + pi_pulse_yneg + tauspacer \
                                          + pi_pulse_y + tauspacer + pi_pulse_y + tauinit + piminushalf_pulse + buffer
            echo_rev = pihalf_pulse + taurevinit + \
                       pi_pulse_yneg + taurevspacer + pi_pulse_y + taurevspacer + \
                       pi_pulse_y + taurevspacer + pi_pulse_yneg + taurevspacer + \
                       pi_pulse_yneg + taurevspacer + pi_pulse_yneg + taurevspacer + \
                       pi_pulse_y + taurevspacer + pi_pulse_y + taurevinit + pihalf_pulse + buffer
            echo_time = 8*pi_y_ns + 2*pihalf_ns + tau + self.laser_buf
            echorev_time = 8*pi_y_ns + 2*pihalf_ns + tau_rev_ns + self.laser_buf
            self.total_time += echorev_time + echo_time + 2 * self.setup_time
            return echo + setupSR + echo_rev + setupSR
        def norm_seq():
            
            ## at the end of the sequence, we put a normalization sequence
            pi_pulse = self.sideband(pi_y_ns, sideband_freq, self.IQboth, axis_angle = 90, phase = phi, clk = False)
            wait = \
                [(self.mw_wait - self.aom_lag, [], *self.IQ0)]
            aom_lag = \
                [(self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)]
            read_tick = \
                [(self.clock_time, [self.channel_dict["laser"], self.channel_dict["clock"]], *self.IQ0)]
            read_window = \
                [(self.readout_time - self.clock_time, [self.channel_dict["laser"]], *self.IQ0)]
            init = \
                [(self.laser_time - self.clock_time - self.readout_time, [self.channel_dict["laser"]], *self.IQ0)]
            aom_buffer = \
                [(self.aom_lag, [], *self.IQ0)]
            buffer = \
                [(self.singlet_decay, [], *self.IQ0)]
            
            ## we set this to some short value because we do not need to re initialize here.
            zero_time = \
                [(100 - self.clock_time, [self.channel_dict["laser"]], *self.IQ0)]
            self.total_time += pi_y_ns + self.mw_wait + self.laser_time + 2 * self.aom_lag + self.singlet_decay + 100 + self.readout_time
            
            ## we run a pi pulse, wait, read the one state, wait for singlet, then read zero state.
            return (pi_pulse + wait + aom_lag + read_tick + read_window + read_tick + init + aom_buffer + buffer
                  + aom_lag + read_tick + read_window + read_tick + zero_time)
        ## initialize
        seqs = ([(self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)] + [(self.laser_time, [self.channel_dict["laser"]], *self.IQ0)] + [(self.aom_lag, [], *self.IQ0)])
        ## add all CPMG
        for tau_time in params:        
            seqs += single_YY8(tau_time)
        ## we put the normalization at the very end of the sequences.    
        seqs += norm_seq()
        self.total_time += 2*self.aom_lag + self.laser_time
        print(self.total_time, "is the amount of time the sequence should take to run")
        ## this means one repeat will have len(tau_times) * data_ct * 8 + 4 reads.
        return seqs
    
    def AidanYY8_sb(self,params,pi_y,pi_y_2, sideband_freq, phi = 90):
        """
        We run a sequence of 8 pi pulses
        pi half x, pi x, pi y, pi x, pi y, pi y, pi x, pi y, pi x, pi half x
        we need to know the pi time for x and y
        as well as the pi half time for x
        """
        self.total_time = 0
        longest_time = params[-1]
        shortest_time = params[0]
        pi_y_ns = int(round(pi_y.to("ns").magnitude))
        pihalf_ns = int(round(pi_y_2.to("ns").magnitude))
        
        
        def single_YY8(tau):
            tau_rev_ns = int(round(longest_time + shortest_time - tau))
            tauspacing_ns = int(round(tau // 8))
            taurevspacing_ns = int(round(tau_rev_ns // 8))
            tauinit_ns = int(round(tau // (2*8)))
            taurevinit_ns = int(round(tau_rev_ns // (2*8)))
            #pi pulses
            pi_pulse_y = self.sideband(pi_y_ns, sideband_freq, self.IQboth, axis_angle = 90, phase = phi, clk = False)
            pi_pulse_yneg = self.sideband(pi_y_ns, sideband_freq, self.IQboth, axis_angle = 270, phase = phi, clk = False)
            pihalf_pulse = self.sideband(pihalf_ns, sideband_freq, self.IQboth, axis_angle = 90, phase = phi, clk = False)
            piminushalf_pulse = self.sideband(pihalf_ns, sideband_freq, self.IQboth, axis_angle = 270, phase = phi, clk = False)
            ## setup for reading
            aom_lag = \
                [(self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)]
            read_tick = \
                [(self.clock_time, [self.channel_dict["laser"], self.channel_dict["clock"]], *self.IQ0)]
            read_window = \
                [(self.readout_time - self.clock_time, [self.channel_dict["laser"]], *self.IQ0)]
            read_tick_buf = \
                [(self.clock_time, [self.channel_dict["clock"]], *self.IQ0)]
            init = \
                [(self.laser_time - self.clock_time - self.readout_time, [self.channel_dict["laser"]], *self.IQ0)]
            aom_buffer = \
                [(self.aom_lag + self.singlet_decay, [], *self.IQ0)]
            setupSR = aom_lag + read_tick + read_window + read_tick + init + aom_buffer
        
            self.setup_time = 2*self.aom_lag + self.laser_time + self.singlet_decay
            
            ## initialize
            initialization = ([(self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)]
                            + [(self.laser_time, [self.channel_dict["laser"]], *self.IQ0)]
                            + [(self.aom_lag, [], *self.IQ0)])
            ## heat_wait
            heat_wait = \
                [(self.heat_decay, [], *self.IQ0)]
        
            #experiment
            buffer = \
                [(self.mw_wait, [], *self.IQ0)]
            # reverse = \
            #     [(reverse_ns, [], *self.IQ)]
            tauinit = \
                [(tauinit_ns, [], *self.IQ0)]
            taurevinit = \
                [(taurevinit_ns, [], *self.IQ0)]
            tauspacer = \
                [(tauspacing_ns, [], *self.IQ0)]
            taurevspacer = \
                [(taurevspacing_ns, [], *self.IQ0)]
            echo = pihalf_pulse + tauinit + pi_pulse_yneg + tauspacer + pi_pulse_y + tauspacer \
                                          + pi_pulse_y + tauspacer + pi_pulse_yneg + tauspacer \
                                          + pi_pulse_yneg + tauspacer + pi_pulse_yneg + tauspacer \
                                          + pi_pulse_y + tauspacer + pi_pulse_y + tauinit + piminushalf_pulse + buffer
            echo_rev = pihalf_pulse + taurevinit + \
                       pi_pulse_yneg + taurevspacer + pi_pulse_y + taurevspacer + \
                       pi_pulse_y + taurevspacer + pi_pulse_yneg + taurevspacer + \
                       pi_pulse_yneg + taurevspacer + pi_pulse_yneg + taurevspacer + \
                       pi_pulse_y + taurevspacer + pi_pulse_y + taurevinit + pihalf_pulse + buffer
            echo_time = 8*pi_y_ns + 2*pihalf_ns + tauspacing_ns + self.mw_wait #bright
            echorev_time = 8*pi_y_ns + 2*pihalf_ns + taurevspacing_ns + self.mw_wait #dark
            self.total_time += echorev_time + echo_time + 2 * (self.setup_time + 2*self.aom_lag + self.laser_time + self.heat_decay)
            return (initialization + echo + setupSR + heat_wait + initialization + echo_rev + setupSR + heat_wait)
        def norm_seq():
            
            ## at the end of the sequence, we put a normalization sequence
            pi_pulse = self.sideband(pi_y_ns, sideband_freq, self.IQboth, axis_angle = 90,phase = phi, clk = False)
            wait = \
                [(self.mw_wait - self.aom_lag, [], *self.IQ0)]
            aom_lag = \
                [(self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)]
            read_tick = \
                [(self.clock_time, [self.channel_dict["laser"], self.channel_dict["clock"]], *self.IQ0)]
            read_window = \
                [(self.readout_time - self.clock_time, [self.channel_dict["laser"]], *self.IQ0)]
            init = \
                [(self.laser_time - self.clock_time - self.readout_time, [self.channel_dict["laser"]], *self.IQ0)]
            aom_buffer = \
                [(self.aom_lag, [], *self.IQ0)]
            buffer = \
                [(self.singlet_decay, [], *self.IQ0)]
            
            ## we set this to some short value because we do not need to re initialize here.
            zero_time = \
                [(100 - self.clock_time, [self.channel_dict["laser"]], *self.IQ0)]
            self.total_time += pi_y_ns + self.mw_wait + self.laser_time + 2 * self.aom_lag + self.singlet_decay + 100 + self.readout_time
            
            ## we run a pi pulse, wait, read the one state, wait for singlet, then read zero state.
            return (pi_pulse + wait + aom_lag + read_tick + read_window + read_tick + init + aom_buffer + buffer
                  + aom_lag + read_tick + read_window + read_tick + zero_time)
        seqs = []
        ## add all CPMG
        for tau_time in params:        
            seqs += single_YY8(tau_time)
        ## we put the normalization at the very end of the sequences.    
        seqs += norm_seq()
        print(self.total_time, "is the amount of time the sequence should take to run")
        ## this means one repeat will have len(tau_times) * data_ct * 8 + 4 reads.
        return seqs
    
    
    def T1_reverse(self,params,pi, sideband_freq, phi = 90):
        """
        We remove the reference reading windows, 
        so now we only read the signal.
        This means we will perform the operation 
        (F0 - F1)/(F0 + F1) for measuring dark state.
        We must reduce the read buckets in the spyrelet.
        
        We account for the heat gained 
        by the wire due to long pi pulse trains.
        """
        self.total_time = 0
        longest_time = params[-1]
        shortest_time = params[0]
        pi_ns = int(round(pi.to("ns").magnitude))
        
        
        def single_T1(tau):
            tau_rev_ns = int(round(longest_time + shortest_time - tau))
            ## setup for reading
            aom_lag = \
                [(self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)]
            read_tick = \
                [(self.clock_time, [self.channel_dict["laser"], self.channel_dict["clock"]], *self.IQ0)]
            read_window = \
                [(self.readout_time - self.clock_time, [self.channel_dict["laser"]], *self.IQ0)]
            init = \
                [(self.laser_time - self.clock_time - self.readout_time, [self.channel_dict["laser"]], *self.IQ0)]
            aom_buffer = \
                [(self.aom_lag + self.singlet_decay, [], *self.IQ0)]
            setupSR = aom_lag + read_tick + read_window + read_tick + init + aom_buffer
        
            self.setup_time = 2*self.aom_lag + self.laser_time + self.singlet_decay
            
            ## initialize
            initialization = ([(self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)]
                            + [(self.laser_time, [self.channel_dict["laser"]], *self.IQ0)]
                            + [(self.aom_lag, [], *self.IQ0)])
        
            #pi pulses
            pi_buffer = \
                [(self.mw_wait, [], *self.IQ0)]
                
            pi_pulse = self.sideband(pi_ns, sideband_freq, self.IQboth, axis_angle = 90, clk = False)
            tau_time = \
                [(tau_rev_ns - pi_ns - self.mw_wait, [], *self.IQ0)]
                
            tau_bright = \
                [(tau, [], *self.IQ0)]
            
            tau_dark = pi_buffer + pi_pulse + tau_time
            
            self.total_time += tau + tau_rev_ns + 2 * (self.setup_time + 2*self.aom_lag + self.laser_time)
            return (initialization + tau_bright + setupSR + initialization + tau_dark + setupSR)
        def norm_seq():
            
            ## at the end of the sequence, we put a normalization sequence
            pi_pulse = self.sideband(pi_ns, sideband_freq, self.IQboth, axis_angle = 90, clk = False)
            wait = \
                [(self.mw_wait - self.aom_lag, [], *self.IQ0)]
            aom_lag = \
                [(self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)]
            read_tick = \
                [(self.clock_time, [self.channel_dict["laser"], self.channel_dict["clock"]], *self.IQ0)]
            read_window = \
                [(self.readout_time - self.clock_time, [self.channel_dict["laser"]], *self.IQ0)]
            init = \
                [(self.laser_time - self.clock_time - self.readout_time, [self.channel_dict["laser"]], *self.IQ0)]
            aom_buffer = \
                [(self.aom_lag, [], *self.IQ0)]
            buffer = \
                [(self.singlet_decay, [], *self.IQ0)]
            
            ## we set this to some short value because we do not need to re initialize here.
            zero_time = \
                [(100 - self.clock_time, [self.channel_dict["laser"]], *self.IQ0)]
            self.total_time += pi_ns + self.mw_wait + self.laser_time + 2 * self.aom_lag + self.singlet_decay + 100 + self.readout_time
            
            ## we run a pi pulse, wait, read the one state, wait for singlet, then read zero state.
            return (pi_pulse + wait + aom_lag + read_tick + read_window + read_tick + init + aom_buffer + buffer
                  + aom_lag + read_tick + read_window + read_tick + zero_time)
        
        ## add all CPMG\
        seqs = []
        for tau_time in params:        
            seqs += single_T1(tau_time)
        ## we put the normalization at the very end of the sequences.    
        seqs += norm_seq()
        print(self.total_time, "is the amount of time the sequence should take to run")
        ## this means one repeat will have len(tau_times) * data_ct * 8 + 4 reads.
        return seqs
        
    def T1OmegaGamma(self, params, pi,pi2, sbFreqLeft, sbFreqRight, phi1 = -90, phi2 = 90, linear = False):
        ''' here i have four sequences
        one is for determining omega.
        '''
        self.total_time = 0
        longest_time = params[-1]
        shortest_time = params[0]
        pi_noround = pi.to("ns").magnitude
        piLeftns = int(round(pi.to("ns").magnitude))
        piRightns = int(round(pi2.to("ns").magnitude))
        
        def single_omega(tau):
            tauinit_ns = int(round(tau // 2))
            #wait pulse
            duty_cycle_balance = \
                [(longest_time - tau, [], *self.IQ0)]
            #pi pulses
            pi_pulse = self.sideband(piLeftns, sbFreqLeft, self.IQboth, phase = phi1, clk = False)
            pi_pulseD = \
                [(piLeftns, [], *self.IQ0)]
            ## setup for reading
            aom_lag = \
                [(self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)]
            read_tick = \
                [(self.clock_time, [self.channel_dict["laser"], self.channel_dict["clock"]], *self.IQ0)]
            read_window = \
                [(self.readout_time - self.clock_time, [self.channel_dict["laser"]], *self.IQ0)]
            init = \
                [(self.laser_time - self.clock_time - self.readout_time, [self.channel_dict["laser"]], *self.IQ0)]
            aom_buffer = \
                [(self.aom_lag + self.singlet_decay, [], *self.IQ0)]
            setupSR = aom_lag + read_tick + read_window + read_tick + init + aom_buffer
        
            
            setup_time = 2*self.aom_lag + self.laser_time + self.singlet_decay
            
            ## initialize
            initialization = ([(self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)]
                            + [(self.laser_time - self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)]
                            + [(self.aom_lag + self.singlet_decay, [], *self.IQ0)])
            init_time = self.aom_lag + self.laser_time + self.singlet_decay
            '''## heat_wait
            heat_wait = \
                [(self.heat_decay, [], *self.IQ0)]
                '''
        
            #experiment
            buffer = \
                [(self.mw_wait, [], *self.IQ0)]
            # reverse = \
            #     [(reverse_ns, [], *self.IQ)]
            tauinit = \
                [(tauinit_ns, [], *self.IQ0)]
            middle = tauinit
            middle_time = tauinit_ns
            middle = middle + tauinit
            middle_time = middle_time + tauinit_ns
            echoRef = pi_pulseD + middle + pi_pulseD + buffer
            echoSig = pi_pulseD + middle + pi_pulse + buffer
            echo_time = middle_time + 2*piLeftns + self.mw_wait
            self.total_time += 2 * (echo_time + setup_time + init_time + longest_time - tau) + 2*(setup_time)
            return (duty_cycle_balance + initialization + echoRef + setupSR + setupSR + duty_cycle_balance + initialization + echoSig + setupSR + setupSR)
         
        def linear_omega(tau):
            tauinit_ns = int(round(tau // 2))
            #wait pulse
            duty_cycle_balance = \
                [(longest_time - tau, [], *self.IQ0)]
            #pi pulses
            pi_pulse = self.sideband(piLeftns, sbFreqLeft, self.IQboth, phase = phi1, clk = False)
            pi_pulseD = \
                [(piLeftns, [], *self.IQ0)]
            ## setup for reading
            aom_lag = \
                [(self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)]
            read_tick = \
                [(self.clock_time, [self.channel_dict["laser"], self.channel_dict["clock"]], *self.IQ0)]
            read_window = \
                [(self.readout_time - self.clock_time, [self.channel_dict["laser"]], *self.IQ0)]
            init = \
                [(self.laser_time - self.clock_time - self.readout_time, [self.channel_dict["laser"]], *self.IQ0)]
            aom_buffer = \
                [(self.aom_lag + self.singlet_decay, [], *self.IQ0)]
            setupSR = aom_lag + read_tick + read_window + read_tick + init + aom_buffer
        
            setup_time = 2*self.aom_lag + self.laser_time + self.singlet_decay
            
            ## initialize
            initialization = ([(self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)]
                            + [(self.laser_time - self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)]
                            + [(self.aom_lag + self.singlet_decay, [], *self.IQ0)])
            init_time = self.aom_lag + self.laser_time + self.singlet_decay
            '''## heat_wait
            heat_wait = \
                [(self.heat_decay, [], *self.IQ0)]
                '''
        
            #experiment
            buffer = \
                [(self.mw_wait, [], *self.IQ0)]
            # reverse = \
            #     [(reverse_ns, [], *self.IQ)]
            tauinit = \
                [(tauinit_ns, [], *self.IQ0)]
            middle = tauinit
            middle_time = tauinit_ns
            middle = middle + tauinit
            middle_time = middle_time + tauinit_ns
            #echoRef = pi_pulseD + middle + pi_pulseD + buffer
            echoSig = pi_pulse + middle + pi_pulseD + buffer
            echo_time = middle_time + 2*piLeftns + self.mw_wait
            self.total_time += (echo_time + setup_time + init_time + longest_time - tau) + setup_time
            return (duty_cycle_balance + initialization + echoSig + setupSR + setupSR)
            
            
        def single_gamma(tau):
            tauinit_ns = int(round(tau // 2))
            #wait pulse
            duty_cycle_balance = \
                [(longest_time - tau, [], *self.IQ0)]
            #pi pulses
            pi_pulse_neg = self.sideband(piLeftns, sbFreqLeft, self.IQboth, phase = phi1, clk = False)
            pi_pulse_pos = self.sideband(piRightns, sbFreqRight, self.IQboth, phase = phi2, clk = False)
            ## setup for reading
            aom_lag = \
                [(self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)]
            read_tick = \
                [(self.clock_time, [self.channel_dict["laser"], self.channel_dict["clock"]], *self.IQ0)]
            read_window = \
                [(self.readout_time - self.clock_time, [self.channel_dict["laser"]], *self.IQ0)]
            init = \
                [(self.laser_time - self.clock_time - self.readout_time, [self.channel_dict["laser"]], *self.IQ0)]
            aom_buffer = \
                [(self.aom_lag + self.singlet_decay, [], *self.IQ0)]
            setupSR = aom_lag + read_tick + read_window + read_tick + init + aom_buffer
        
            setup_time = 2*self.aom_lag + self.laser_time + self.singlet_decay
            
            ## initialize
            initialization = ([(self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)]
                            + [(self.laser_time - self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)]
                            + [(self.aom_lag + self.singlet_decay, [], *self.IQ0)])
                            
            init_time = self.aom_lag + self.laser_time + self.singlet_decay
            #experiment
            buffer = \
                [(self.mw_wait, [], *self.IQ0)]
            tauinit = \
                [(tauinit_ns, [], *self.IQ0)]
            middle = tauinit
            middle_time = tauinit_ns
            middle = middle + tauinit
            middle_time = middle_time + tauinit_ns
            echoRef = pi_pulse_neg + middle + pi_pulse_neg + buffer
            echoSig = pi_pulse_neg + middle + pi_pulse_pos + buffer
            echoRef_time = middle_time + 2*piLeftns + self.mw_wait
            echoSig_time = middle_time + piLeftns + piRightns + self.mw_wait
            self.total_time += echoRef_time + echoSig_time + 2 * (setup_time + init_time + longest_time - tau) + 2*(setup_time)
            return (duty_cycle_balance + initialization + echoRef + setupSR + setupSR + duty_cycle_balance + initialization + echoSig + setupSR + setupSR)
        
        def linear_gamma(tau):
            taurevinit_ns = int(round((longest_time + shortest_time - tau)//2))
            tauinit_ns = int(round(tau // 2))
            #pi pulses
            pi_pulse_neg = self.sideband(piLeftns, sbFreqLeft, self.IQboth, phase = phi1, clk = False)
            pi_pulse_pos = self.sideband(piRightns, sbFreqRight, self.IQboth, phase = phi2, clk = False)
            ## setup for reading
            aom_lag = \
                [(self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)]
            read_tick = \
                [(self.clock_time, [self.channel_dict["laser"], self.channel_dict["clock"]], *self.IQ0)]
            read_window = \
                [(self.readout_time - self.clock_time, [self.channel_dict["laser"]], *self.IQ0)]
            init = \
                [(self.laser_time - self.clock_time - self.readout_time, [self.channel_dict["laser"]], *self.IQ0)]
            aom_buffer = \
                [(self.aom_lag + self.singlet_decay, [], *self.IQ0)]
            setupSR = aom_lag + read_tick + read_window + read_tick + init + aom_buffer
        
            setup_time = 2*self.aom_lag + self.laser_time + self.singlet_decay
            
            ## initialize
            initialization = ([(self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)]
                            + [(self.laser_time - self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)]
                            + [(self.aom_lag + self.singlet_decay, [], *self.IQ0)])
                            
            init_time = self.aom_lag + self.laser_time + self.singlet_decay
            #experiment
            buffer = \
                [(self.mw_wait, [], *self.IQ0)]
            tauinit = \
                [(tauinit_ns, [], *self.IQ0)]
            taurevinit = \
                [(taurevinit_ns, [], *self.IQ0)]
            middle = tauinit
            middle_rev = taurevinit
            middle_time = tauinit_ns
            middle_rev_time = taurevinit_ns
            middle = middle + tauinit
            middle_rev = taurevinit + taurevinit
            middle_time = middle_time + tauinit_ns
            middle_rev_time = middle_rev_time + taurevinit_ns
            echoRef = pi_pulse_neg + middle_rev + pi_pulse_neg + buffer
            echoSig = pi_pulse_neg + middle + pi_pulse_pos + buffer
            echoRef_time = middle_rev_time + 2*piLeftns + self.mw_wait
            echoSig_time = middle_time + piLeftns + piRightns + self.mw_wait
            self.total_time += echoRef_time + echoSig_time + 2*init_time + 3 * (setup_time)
            return (initialization + echoRef + setupSR + initialization + echoSig + setupSR + setupSR) #returns backwards list, then forwards list
        # # def norm_seq():
            
            # # ## at the end of the sequence, we put a normalization sequence
            # # pi_pulse = self.sideband(pi_ns, sbFreqLeft, self.IQboth, axis_angle = 90, phase = phi, clk = False)
            # # wait = \
                # # [(self.mw_wait - self.aom_lag, [], *self.IQ0)]
            # # aom_lag = \
                # # [(self.aom_lag, [self.channel_dict["laser"]], *self.IQ0)]
            # # read_tick = \
                # # [(self.clock_time, [self.channel_dict["laser"], self.channel_dict["clock"]], *self.IQ0)]
            # # read_window = \
                # # [(self.readout_time - self.clock_time, [self.channel_dict["laser"]], *self.IQ0)]
            # # init = \
                # # [(self.laser_time - self.clock_time - self.readout_time, [self.channel_dict["laser"]], *self.IQ0)]
            # # aom_buffer = \
                # # [(self.aom_lag, [], *self.IQ0)]
            # # buffer = \
                # # [(self.singlet_decay, [], *self.IQ0)]
            
            # # ## we set this to some short value because we do not need to re initialize here.
            # # zero_time = \
                # # [(100 - self.clock_time, [self.channel_dict["laser"]], *self.IQ0)]
            # # self.total_time += pi_ns + self.mw_wait + self.laser_time + 2 * self.aom_lag + self.singlet_decay + 100 + self.readout_time
            
            # # ## we run a pi pulse, wait, read the one state, wait for singlet, then read zero state.
            # # return (pi_pulse + wait + aom_lag + read_tick + read_window + read_tick + init + aom_buffer + buffer
                  # # + aom_lag + read_tick + read_window + read_tick + zero_time)
        ## initialize
        seqs = []
        ## add all CPMG
        if linear == False:        
            for tau_time in params:        
                seqs += single_omega(tau_time) ## bright then dark
                seqs += single_gamma(tau_time) ## bright then dark
        else:
            for tau_time in params:        
                seqs += linear_omega(tau_time) ## bright then dark
                seqs += linear_gamma(tau_time) ## bright then dark
        # # ## we put the normalization at the very end of the sequences.    
        # # seqs += norm_seq()
        print(self.total_time, "is the amount of time the sequence should take to run")
        ## we read 4 times total in omega and 4 times in gamma.
        return seqs
        
        
    def flip_the_mirror(self):
        flip = \
            [(1000000, [self.channel_dict['mirror']], *self.IQ0)]
            
        #self.total_time = pulse_time * n_pulses
        
        return flip