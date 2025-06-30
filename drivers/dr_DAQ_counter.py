'''
nidaqmx driver/wrapper designed for ease of reading from a DAQ counter channel.

Written by: David Ovetsky
6/25/2025
'''

import nidaqmx
from nidaqmx.constants import (AcquisitionType, CountDirection, Edge)
from nidaqmx.stream_readers import CounterReader
import time
import numpy as np

class DAQCounter:
    '''
    A class to handle reading from a DAQ counter using the NIDAQmx library.
    Assumes a clock channel and single counter channel. Edits will need to be made for different configurations, ex. more counters.
    '''
    def __init__(self, dev, clk_pfi = 'PFI0', apd_ctr = 'ctr1'): # counter channel requires ctr, clock channel requires pfi
        self.read_task = None
        self.reader = None
        self.buffer = None
        self.n_samples = 0
        self.ctrs_pfis = { # Not used but good to have for reference.
                    'ctr0': 'PFI8',
                    'ctr1': 'PFI3',
                    'ctr2': 'PFI0',
                    'ctr3': 'PFI5',
        }
        self.n_ctrs = 1
        self.sampling_rate = 0 # TEMPORARY
        self.clk_channel = '/' + dev + '/' + clk_pfi
        self.ctr_channel ='/' + dev + '/' + apd_ctr




    def set_sampling_rate(self, sampling_rate):
        """
        Set the sampling rate for the counter.
        """
        self.sampling_rate = sampling_rate




    def create_buffer(self, size):
        """
        Create a buffer for reading samples, store it, and return it. 
        Note that the desired size should always be one larger than the amount of signal points, since signal points are derived from differences in counts.
        """
        self.n_samples = size
        self.buffer = np.ascontiguousarray(np.zeros(size, dtype=np.uint32))
        return self.buffer



    def initialize(self, bounded_sample = True):
        """
        Initialize the counter by creating a read task and adding the counter channel.
        If bounded_sample is True, the task will be configured for finite sampling.
        """

        ## Set up the counter, connect it to the clock.
        self.read_task = nidaqmx.Task()
        self.read_task.ci_channels.add_ci_count_edges_chan(
            self.ctr_channel,
            edge=Edge.RISING,
            initial_count=0,
            count_direction=CountDirection.COUNT_UP
        )
        self.read_task.ci_channels.all.ci_count_edges_term = self.clk_channel

        ## Set up the clock channel.
        if bounded_sample:
            sample_mode = AcquisitionType.FINITE
        else:
            sample_mode = AcquisitionType.CONTINUOUS

        self.read_task.timing.cfg_samp_clk_timing(
            self.sampling_rate, # must be equal or larger than max rate expected by PS
            source= self.clk_channel,
            sample_mode=sample_mode, 
            samps_per_chan= self.n_ctrs
        )

        ## Set up the reader.
        self.reader = CounterReader(self.read_task.in_stream)



    def finalize(self):
        """
        Finalize the counter by stopping and clearing the read task.
        """
        if self.read_task is not None:
            self.read_task.stop()
            self.read_task.close()
            self.read_task = None
            self.reader = None
            self.buffer = None
            self.n_samples = 0
    


    def start(self):
        """
        Start the counter task.
        """
        if self.read_task is not None:
            self.read_task.start()



    def read(self, timeout=10.0):
        '''Read samples from the counter channel into the buffer. No need to return anything, data is accessed through the buffer.'''
        num_samps = self.reader.read_many_sample_uint32(
            self.buffer,
            number_of_samples_per_channel= self.n_samples,
            timeout= timeout
        )
        
        if num_samps < self.n_samples:
            print('something wrong: buffer issue')
        self.read_task.stop() 
        return 
    
    
    def start_stream_read(self, pulses, sequence, n_runs = 1, timeout = 10):
        """
        start, stream, and read from a single method by passing in the pulse streamer and all of its arguments.
        pulses: PulseStreamer instance
        sequence: Sequence object to stream
        n_runs: number of runs to stream, to pass to the PulseStreamer
        timeout: timeout for reading samples
        """
        if self.buffer is None:
            raise RuntimeError("Buffer not created. Call create_buffer() before starting the stream read.")

        if self.read_task is not None:
            self.read_task.start()
        
        pulses.stream(sequence, int(n_runs))

        num_samps = self.reader.read_many_sample_uint32(
            self.buffer,
            number_of_samples_per_channel= self.n_samples,
            timeout= timeout
        )
        
        if num_samps < self.n_samples:
            raise RuntimeError('Something went wrong: buffer issue, not enough samples read.')
        self.read_task.stop() 
        return 


    