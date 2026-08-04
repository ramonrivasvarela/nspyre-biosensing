###########################
# imports
###########################

# std
import numpy as np
import time
import math
from itertools import cycle
import logging
import scipy as sp
from scipy import signal
import datetime as Dt

# nidaqmx
import nidaqmx
from nidaqmx.constants import (AcquisitionType, CountDirection, Edge,
    READ_ALL_AVAILABLE, TaskMode, TriggerType)
from nidaqmx._task_modules.channels.ci_channel import CIChannel
from nidaqmx.stream_readers import CounterReader

# nspyre
from nspyre.gui.widgets.views import Plot1D, Plot2D, PlotFormatInit, PlotFormatUpdate
from nspyre.spyrelet.spyrelet import Spyrelet
from nspyre.gui.widgets.plotting import LinePlotWidget
from nspyre.gui.colors import colors
from nspyre.definitions import Q_

from lantz.drivers.ni.UriFSM import UriSetup
from spacefb import SpatialFeedbackXYZSpyrelet
#from lantz.drivers.swabian.pulsestreamer.lib.Sequence import Sequence
#from lantz.drivers.swabian.pulsestreamer.lib.sequence import Sequence

import itertools as it
from nspyre.gui.colors import cyclic_colors, colors

# for data download
from threed.data_and_plot import save_excel

COLORS = cycle(colors.keys())

###########################
# classes
###########################
class PulsedODMRSwabianSpyrelet(BaseFeedbackSpyrelet):
    REQUIRED_DEVICES = [
        'sg',
        'pulses',
        'urixyz',#this is probably not needed
    ]
    REQUIRED_SPYRELETS = {
        'newSpaceFB': SpatialFeedbackXYZSpyrelet
    }
    """
    we run an ODMR,but this time our 
    mw_on time is a pi_pulse. This gives us a full
    rotation to the dark state, and gives us optimal contrast.
    """
    PARAMS = {
        'device':{
            'type': str,
            'default': 'Dev1',
        },
        'channel1':{
            'type':list,
            'items':list(['ctr0','ctr1','ctr2','ctr3','none']),
            'default':'ctr1',
            },
        'PS_clk_channel':{
            'type': str,
            'default': 'PFI0',
        },
        'sampling_rate':{
            'type':float,
            'units':'Hz',
            'suffix': ' Hz',
            'default': 2.5e6,
        },
        # 'time_per_point':{
            # 'type':float,
            # 'units': 's',
            # 'suffix': ' s',
            # 'default': 1
            # },
        ## in this spyrelet, we set n_points
        ## n_points is the amount of times we run one point.
        ## we may also call this "n_runs"
        'n_points':{
            'type':int,
            'default': 10000,
            'positive': True,
            },   
        'sweeps':{
            'type': int,
            'default': 100,
            'positive': True,
        },
        'frequency':{
            'type': range,
            'units':'Hz',
            'default':{'func': 'linspace',
                            'start': 2.8e9,
                            'stop': 2.94e9,
                            'num': 40},
        },
        'rf_amplitude':{
            'type': float,
            'default': -20,
        },
        'pi_time':{
            'type': float,
            'default': .5e-6,
            'suffix': ' s',
            'units': 's',
        },
        'probe_time':{
            'type': float,
            'default': 3.5e-6,
            'suffix': ' s',
            'units': "s"
        },
        'readout_time':{
            'type': float,
            'default': .4e-6,
            'suffix': ' s',
            'units': 's'
        },
        'wait_buffer_time':{
            'type': float,
            'default': 800e-6,
            'suffix': ' s',
            'units': 's'
        },
        'singlet_decay':{
            'type': float,
            'default': .6e-6,
            'suffix': ' s',
            'units': 's'
        },
        'clock_duration':{
            'type': float,
            'default': 10e-9,
            'suffix': ' s',
            'units': 's'
        },
        'timeout': {
            'type': int,
            'nonnegative': True,
            'default': 300
        },
        'aom_lag':{
            'type': float,
            'default': .027e-6,
            'suffix': ' s',
            'units': 's'
        },
        'buffer_time':{
            'type': float,
            'default': 0.1e-6,
            'suffix': ' s',
            'units': 's'
        },
        'feedback':{
            'type': bool,
            'default': False,
        },
        'dozfb':{
            'type': bool,
            'default': True
        },
        'sweeps_til_fb':{
            'type': int,
            'default': 10,
        },
        'x_initial':{
            'units': 'um',
            'type': float,
            'default': 0.0,
        },
        'y_initial':{
            'units': 'um',
            'type': float,
            'default': 0.0,
        },
        'z_initial': {
            'units': 'um',
            'type': float,
            'default': 0.0,
        },
        'xyz_step':{
            'type': float,
            'units': 'm',
            'default': 60e-9,
        },
        'count_step_shrink':{
            'type': int,
            'default': 2,
        },
        'starting_point': {
            'type': list,
            'items': list(['user_input','current_position (ignore input)']),
            'default': 'current_position (ignore input)',
        },
        'data_download':{
            'type': bool,
        },
    }

    def main(self, device, channel1, PS_clk_channel, timeout, sampling_rate, \
                    n_points, sweeps, frequency, rf_amplitude, pi_time, probe_time, aom_lag, \
                    readout_time, singlet_decay, clock_duration, buffer_time,data_download,\
                    feedback, dozfb, sweeps_til_fb,\
                    x_initial, y_initial,z_initial,xyz_step,count_step_shrink,starting_point,wait_buffer_time):
        for sweep in self.progress(range(sweeps)):
            ## run xy (and z) spatial feedback if the sweep is a multiple of designated number of xy (and z) sweeps
            if feedback and (sweep % sweeps_til_fb == 0) and (sweep > 0):
                self.run_feedback(x_initial, y_initial, z_initial, starting_point, dozfb, xyz_step, count_step_shrink) 
            ## frequency sweep
            for f in frequency:
                self.sg.frequency = f # setting sg to frequency f (SG396 communication overhead of <1ms)
                self.t0= time.time()
                ctrs_rates = self.read_odmr(n_points, self.buffers,self.index, self.t0) # calls read from base spyrelet)        
                ## acquire the following 
                self.acquire({
                    'sweep_idx': sweep,
                    'f': f,
                    'x': float(ctrs_rates[0]),
                    'y': float(ctrs_rates[1]),
                })
    def math_odmr(self, array):
        
        ## divide buffer to different experiments
        delta_buffer_start = array[1::4] - array[0::4] 
        delta_buffer_end = array[3::4] - array[2::4] # taking the difference between ticks
        ## the sequence first records the bright state, then the dark state.
        sum2 = np.sum(delta_buffer_start) 
        sum1 = np.sum(delta_buffer_end) 
        ## return dark, bright)
        return [sum1, sum2]

    def initialize(self, device, channel1, PS_clk_channel, timeout, sampling_rate, \
                    n_points, sweeps, frequency, rf_amplitude, pi_time, probe_time, aom_lag, \
                    readout_time, singlet_decay, clock_duration, buffer_time,data_download,\
                    feedback, dozfb, sweeps_til_fb,\
                    x_initial, y_initial,z_initial,xyz_step,count_step_shrink,starting_point,wait_buffer_time):
        ## make sure we only stream one sequence, set timeout for sample clock.
        self.index = 0
        self.timeout=timeout
        ## create channels list and check that there are no repeats
        self.channel = channel1
        ## we set the buffer size, n_points * number of clock pulses in 1 sequence.
        buffer_size = 4*n_points
        ni_ctr_sample_buffer = np.ascontiguousarray(np.zeros(buffer_size, dtype=np.uint32))
        
        self.buffers = [ni_ctr_sample_buffer]
        ## sampling rate should be higher than 1/readout
        self.sampling_rate = sampling_rate.to('Hz').m
        
        super().initialize(device, self.buffers, PS_clk_channel,
                           sampling_rate,data_download)
        
        ## initialize instruments. This stuff can probably be moved to 
        self.sg.rf_amplitude = rf_amplitude
        ## set up the pulse streamer.
        self.setup_pulses(pi_time,probe_time,aom_lag,readout_time,buffer_time,singlet_decay, clock_duration,wait_buffer_time)
        return
        
    def finalize(self, device, channel1, PS_clk_channel, timeout, sampling_rate, \
                    n_points, sweeps, frequency, rf_amplitude, pi_time, probe_time, aom_lag, \
                    readout_time, singlet_decay, clock_duration, buffer_time,data_download,\
                    feedback, dozfb, sweeps_til_fb,\
                    x_initial, y_initial,z_initial,xyz_step,count_step_shrink,starting_point,wait_buffer_time):
        ## perform common finalize
        super().finalize(device, self.buffers, PS_clk_channel,
                         sampling_rate,data_download)
        return

    def setup_pulses(self,pi_time,probe_time,aom_lag,readout_time,buffer_time,singlet_decay,clock_duration,wait_buffer_time):
        self.pulses.laser_time = int(probe_time.to("ns").m)
        self.pulses.singlet_decay = int(singlet_decay.to("ns").m)
        ## aom_lag is always laser_lag
        self.pulses.aom_lag = int(aom_lag.to("ns").m)
        self.pulses.readout_time = int(readout_time.to("ns").m)
        self.pulses.laser_buf = int(buffer_time.to("ns").m)
        self.pulses.wait_buff = int(round(wait_buffer_time.to("ns").m))
        self.pulses.tick_time = int(clock_duration.to("ns").m)
        ## we set the sequences. we put it in a list so that our index / read_odmr will work.
        self.seqs = [self.pulses.Diff_Pulsed_ODMR(pi_time)]
        print("sequence:", self.seqs)
        ## sets the ratio which we could use to scale up how many counts we get. 
        ## since we sum in our math function, this doesn't matter too much.
        self.ratio = self.pulses.total_time / (2 * self.pulses.readout_time)