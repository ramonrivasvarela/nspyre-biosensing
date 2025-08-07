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
from collections import OrderedDict
from nidaqmx.stream_writers import AnalogMultiChannelWriter

class NIDAQAxis:
    def __init__(self, ao_ch, cal, limits=(None, None)):
        self.ch      = ao_ch
        #self.units   = units
        self.cal     = cal           # V / unit
        self.limits  = limits        # (min, max) in <units>

    # ---- unit handling ----
    # def _as_quantity(self, val):
    #     if not isinstance(val, Q_):
    #         val = Q_(val, self.units)
    #     else:
    #         val = val.to(self.units)
    #     return val

    def units_to_volts(self, pos):
        return (pos * self.cal)
    
class DAQCounter:
    
    '''
    A class to handle reading from a DAQ counter using the NIDAQmx library.
    Assumes a clock channel and single counter channel. Edits will need to be made for different configurations, ex. more counters.
    '''
    def __init__(self, dev, x_ch, y_ch, z_ch, acq_rate=15000, clk_pfi = 'PFI0', apd_ctr = 'ctr1'): # counter channel requires ctr, clock channel requires pfi
        self.read_task = None
        self.reader = None
        self.ctr_buffer = None
        self.n_samples = 0
        self.dev = dev
        self.ctrs_pfis = { # Not used but good to have for reference.
                    'ctr0': 'PFI8',
                    'ctr1': 'PFI3',
                    'ctr2': 'PFI0',
                    'ctr3': 'PFI5',
        }
        self.sampling_rate = 0 # TEMPORARY
        self.clk_channel = '/' + dev + '/' + clk_pfi
        self.ctr_channel = '/' + dev + '/' + apd_ctr
        self.pfi_channel = '/' + dev + '/' + self.ctrs_pfis[apd_ctr] 
        self.axes = {
            'x': NIDAQAxis(dev+'/' + x_ch, 0.73 / 11.42, limits=(-114.2 / 0.73, 114.2 / 0.73)),  # Calibration: V/um
            'y': NIDAQAxis(dev+'/' + y_ch, 1 / 11.42, limits=(-114.2, 114.2)),  # Calibration: V/um
            'z': NIDAQAxis(dev+'/' + z_ch, 1 / 25, limits=(0, 250)) }
        self.acq_rate  = acq_rate
        self.ao_motion_task = None

    def initialize_motion(self):
        if self.ao_motion_task is not None:
            self.finalize_motion()
        print("Creating motion task.")
        self.ao_motion_task = nidaqmx.Task('AO_Task')
        print("Created motion task.")
        for name, ax in self.axes.items():
            kw = {}
            if ax.limits[0] is not None:
                kw['min_val'] = ax.units_to_volts(ax.limits[0])
            if ax.limits[1] is not None:
                kw['max_val'] = ax.units_to_volts(ax.limits[1])
            print(f"Adding voltage chan for {name}")
            self.ao_motion_task.ao_channels.add_ao_voltage_chan(
                ax.ch, name_to_assign_to_channel=name, **kw
            )
            print(f"Added voltage chan for {name}")

    def finalize_motion(self):
    # if self.ao_motion_task:
    #     self.ao_motion_task.close()
        if self.ao_motion_task:
            try:
                self.ao_motion_task.stop()
            except nidaqmx.errors.DaqError:
                pass
            self.ao_motion_task.close()
        self.ao_motion_task = None


        
    def set_sampling_rate(self, sampling_rate):
        """
        Set the sampling rate for the counter.
        """
        self.sampling_rate = int(sampling_rate)




    def create_buffer(self, size):
        """
        Create a buffer for reading samples, store it, and return it. 
        Note that the desired size should always be one larger than the amount of signal points, since signal points are derived from differences in counts.
        """
        self.n_samples = size
        self.ctr_buffer = np.ascontiguousarray(np.zeros(size, dtype=np.uint32))
        return self.ctr_buffer



    def create_counter(self, line_scan_mode=False):
        """
        Initialize the counter by creating a read task and adding the counter channel.
        If bounded_sample is True, the task will be configured for finite sampling.
        """

        ## Set up the counter, connect it to the clock.
        print(f'Initializing DAQCounter with clock channel {self.clk_channel} and counter channel {self.ctr_channel}')
        if self.read_task is not None:
            self.finalize_counter()

        self.read_task = nidaqmx.Task()
        self.read_task.ci_channels.add_ci_count_edges_chan(
            self.ctr_channel,
            edge=Edge.RISING,
            initial_count=0,
            count_direction=CountDirection.COUNT_UP
        )
        self.read_task.ci_channels.all.ci_count_edges_term = self.pfi_channel
        if line_scan_mode:
            self.set_line_scan_mode()
        else:
            self.set_counting_mode()

    def set_counting_mode(self, bounded_sample=True):
        ## Set up the clock channel.
        if bounded_sample:
            sample_mode = AcquisitionType.FINITE
        else:
            sample_mode = AcquisitionType.CONTINUOUS
                                                                                                                                                                                                                  
        self.read_task.timing.cfg_samp_clk_timing(
            self.sampling_rate, # must be equal or larger than max rate expected by PS
            source= self.clk_channel,
            sample_mode=sample_mode, 
            samps_per_chan= self.n_samples
        )

        ## Set up the reader.
        self.reader = CounterReader(self.read_task.in_stream)
    



    def finalize_counter(self):
        """
        Finalize the counter by stopping and clearing the read task.
        """
        if self.read_task is not None:
            self.read_task.stop()
            self.read_task.close()
            self.read_task = None
            self.reader = None
            self.ctr_buffer = None
            self.n_samples = 0
    


    def start_counter(self):
        """
        Start the counter task.
        """
        if self.ctr_buffer is None:
            raise RuntimeError("Buffer not created. Call create_buffer() before starting the stream read.")
        if self.read_task is not None:
            self.read_task.start()



    def read_counter(self, timeout=10.0):
        '''Read samples from the counter channel into the buffer. No need to return anything, data is accessed through the buffer.'''
        num_samps = self.reader.read_many_sample_uint32(
            self.ctr_buffer,
            number_of_samples_per_channel= self.n_samples,
            timeout= timeout
        )
        
        if num_samps < self.n_samples:
            print('something wrong: buffer issue')
        self.read_task.stop() 
        return 
    
    def buffer_to_data(self, probe_time):
        if self.ctr_buffer is None:
            raise ValueError("Buffer is not initialized.")
        all_data = np.array(self.ctr_buffer[1:] - self.ctr_buffer[0:-1])
        data = np.sum(all_data)/ ((self.n_samples+1)*probe_time )
        return data
    
    def read_to_data(self,probe_time, timeout=10.0):
        """
        Read samples from the counter channel into the buffer and convert to data.
        Returns the data as a float.
        """
        self.read_counter(timeout)
        return self.buffer_to_data(probe_time)
    
    ### MOTION TASKS SECTION ###
    
    def move(self, target: dict):
        for name, axis in self.axes.items():
            if target[name] < axis.limits[0] or target[name] > axis.limits[1]:
                raise ValueError(f"{name} position {target[name]} is out of bounds {axis.limits}")
        steps = 10
        start_v = np.array([
            axis.units_to_volts(self.position[name])
            for name, axis in self.axes.items()
        ])
        stop_v = np.array([
            axis.units_to_volts(target[name])
            for name, axis in self.axes.items()
        ])
        voltages = np.linspace(start_v, stop_v, steps).T

        # Ensure voltages array is C-contiguous
        voltages = np.ascontiguousarray(voltages)

        self.ao_motion_task.timing.cfg_samp_clk_timing(
            self.acq_rate,
            sample_mode=nidaqmx.constants.AcquisitionType.FINITE,
            samps_per_chan=steps,
        )

        writer = AnalogMultiChannelWriter(self.ao_motion_task.out_stream, auto_start=False)
        writer.write_many_sample(voltages)
        self.ao_motion_task.start()
        self.ao_motion_task.wait_until_done()
        self.ao_motion_task.stop()

        self.position = target

    def set_line_scan_mode(self):
        self.ao_motion_task.timing.cfg_samp_clk_timing(
            self.sampling_rate,
            sample_mode=nidaqmx.constants.AcquisitionType.FINITE,
            samps_per_chan=self.n_samples
        )
        # Shivam: This is the line which writes the voltage values into the ao_motion_task
        # and starts when we write self.ao_motion_task.start() below.
        self.sample_writer_stream = AnalogMultiChannelWriter(self.ao_motion_task.out_stream,
                                                            auto_start=False)
                # configure counter input task
        self.read_task.timing.cfg_samp_clk_timing(
            self.sampling_rate,
            source='/{}/ao/SampleClock'.format(self.dev),
            sample_mode=nidaqmx.constants.AcquisitionType.FINITE,
            samps_per_chan=self.n_samples
        )
        
        # set the counter input to trigger / start acquisition when the AO starts
        self.read_task.triggers.arm_start_trigger.dig_edge_src = '/{}/ao/StartTrigger'.format(self.dev)
        self.read_task.triggers.arm_start_trigger.trig_type = nidaqmx.constants.TriggerType.DIGITAL_EDGE
        #self.ao_motion_task.triggers.start_trigger.disable_start_trig()
        
        # create counter stream object
        self.reader = CounterReader(self.read_task.in_stream)

    def line_scan(self, init_point, final_point, steps, pts_per_step=1):
        """1-axis line scan while acquiring counter data"""
        self.prepare_line_scan(init_point, final_point, steps, pts_per_step)
        self.start_line_scan()
    
    def prepare_line_scan(self, init_point, final_point, steps, pts_per_step=1):
        """1-axis line scan while acquiring counter data"""
        self.final_point = final_point
        self.shape = (steps, pts_per_step + 1)
        self.move(init_point)
        step_voltages = self.linear_func(init_point, final_point, steps)
        step_voltages = np.repeat(step_voltages, pts_per_step + 1, axis=0)
        # # configure analog output task
        # self.ao_motion_task.timing.cfg_samp_clk_timing(
        #     self.acq_rate,
        #     sample_mode=nidaqmx.constants.AcquisitionType.FINITE,
        #     samps_per_chan=step_voltages.shape[0]
        # )
        # # Shivam: This is the line which writes the voltage values into the ao_motion_task
        # # and starts when we write self.ao_motion_task.start() below.
        # sample_writer_stream = AnalogMultiChannelWriter(self.ao_motion_task.out_stream,
        #                                                     auto_start=False)
        # must use array with contiguous memory region because NI uses C arrays under the hood
        # Shivam: This is the section where voltage values are made contiguous and encoded
        ni_ao_sample_buffer = np.ascontiguousarray(step_voltages.transpose(), dtype=float)
        # TODO timeout
        self.sample_writer_stream.write_many_sample(ni_ao_sample_buffer, timeout=60)
        
        # # e.g. "Dev1"
        # device_name = list(self.axes.items())[0][1].ch.split('/')[0]
        
        # # configure counter input task
        # self.read_task.timing.cfg_samp_clk_timing(
        #     self.sampling_rate,
        #     source='/{}/ao/SampleClock'.format(device_name),
        #     sample_mode=nidaqmx.constants.AcquisitionType.FINITE,
        #     samps_per_chan=step_voltages.shape[0]
        # )
        
        # # set the counter input to trigger / start acquisition when the AO starts
        # self.read_task.triggers.arm_start_trigger.dig_edge_src = '/{}/ao/StartTrigger'.format(device_name)
        # self.read_task.triggers.arm_start_trigger.trig_type = nidaqmx.constants.TriggerType.DIGITAL_EDGE
        # #self.ao_motion_task.triggers.start_trigger.disable_start_trig()
        
        # # create counter stream object
        # self.reader = CounterReader(self.read_task.in_stream)

        # must use array with contiguous memory region because NI uses C arrays under the hood
        # self.ni_ctr_sample_buffer = np.ascontiguousarray(np.zeros(step_voltages.shape[0]), dtype=np.uint32)
        self.create_buffer()
        self.read_task.start()
        self.ao_motion_task.start()
        
    def start_line_scan(self):
        # TODO timeout
        self.reader.read_many_sample_uint32(self.ctr_buffer,
                                        number_of_samples_per_channel=nidaqmx.constants.READ_ALL_AVAILABLE,
                                        timeout=60)
        
        # wait for motion to complete
        #time.sleep((1.1*step_voltages.shape[0] / self.acq_rate).to('s').m)

        self.read_task.stop()
        self.ao_motion_task.stop()
        scanned = self.ctr_buffer.reshape(self.shape)
        averaged = np.diff(scanned).mean(axis=1)
        self.position = self.final_point
        # print('what is my final point', final_point, self.position)
        return averaged*self.acq_rate
    
    def linear_func(self, start_pt, stop_pt, steps):
        """Generate a set of linearly spaced points between the start and stop point
        return value is in volts"""
        start_volts = np.array([])
        stop_volts = np.array([])
        for axis in self.axes:
            start_volts = np.append(start_volts, self.axes[axis].units_to_volts(start_pt[axis]))
            stop_volts = np.append(stop_volts, self.axes[axis].units_to_volts(stop_pt[axis]))
        linear_steps = np.linspace(0.0, 1.0, steps)
        # pt0 = [0, 0]
        # pt1 =  [1, 2]
        # np.ones = [1, 1, 1, 1, 1, 1, ...]
                        # [[x, x, x, x, x, x....]
                        # [y, y, y, y, y, y, y...]]
                        
                        # [[0.1, 0.2, ..., 1]
                        # [0.2, 0.4, ..., 2]]
        return np.outer(np.ones(steps), start_volts) + np.outer(linear_steps, stop_volts-start_volts)
    
    


    