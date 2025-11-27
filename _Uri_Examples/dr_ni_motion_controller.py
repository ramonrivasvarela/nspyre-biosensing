"""
    lantz.drivers.ni.ni_motion_controller
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Generalized NI DAQ-based motion controller that uses analog outputs to drive
    motion stages.

    Author: Uri Zvi, Jacob Feder, Aidan Jones
    Date: 9/30/2020
"""

# std lib
from collections import OrderedDict
import time
from math import ceil
import itertools    

# 3rd party
import numpy as np
import nidaqmx
from nidaqmx.stream_writers import AnalogMultiChannelWriter
from nidaqmx.stream_readers import CounterReader

# lantz
from lantz import Driver
#from lantz.driver import Feat, DictFeat, Action
from lantz.core.feat import Feat, DictFeat
from lantz.core.action import Action
from lantz import Q_

class NIDAQAxis():
    def __init__(self, ao_ch, units, cal, limits=(None, None)):
        """Class representing an individual axis associated with an individual 
        DAQ analog output (ao) channel
        ao_ch: NI DAQ channel string e.g. 'Dev/ao0'
        units: units string of the axis e.g. 'um'
        cal: conversion of axis units to volts e.g. Q_(10.0, 'V/um')
        limits: limits tuple e.g. (Q_(min, 'um'), Q_(max, 'um'))
        """
        self.ch = ao_ch
        self.units = units
        self.limits = limits
        self.cal = cal

    def enforce_units(self, val):
        """Convert an input quantity object or float into the native units of 
        this axis"""
        if not isinstance(val, Q_):
            val = Q_(val, self.units)
        else:
            val = val.to(self.units)
        return val

    def units_to_volts(self, pos):
        """Convert a quantity in the axis units to a voltage (as a float)"""
        return (self.enforce_units(pos) * self.cal).to('V').m

    def generate_smoothed_pts(self, start_pt, stop_pt, steps):
        """Generate a set of points along a smoothed cosine path between the 
        start and stop points, in order to minimize large accelerations"""
        versine_steps = (1.0 - np.cos(np.linspace(0.0, np.pi, steps))) / 2.0
        return np.ones(steps) * start_pt + versine_steps * (stop_pt - start_pt)

class NIDAQMotionController(Driver):
    def __init__(self, ctr_ch, acq_rate, axes, ao_smooth_steps=Q_(100, '1/V')):
        """Motion controller for an n-dimensional set of NI DAQ analog output
        axes
        axes: dictionary of axis name mapped to NIDAQAxis object

        example initialization:
        axis1 = NIDAQAxis('Dev1/ao0', 'um', Q_(10.0, 'V/um'))
        axis2 = NIDAQAxis('Dev1/ao1', 'um', Q_(10.0, 'V/um'))
        mc = NIDAQMotionController('Dev1', {'x' : axis1, 'y' : axis2})
        or
        mc = NIDAQMotionController('Dev1', x=axis1, y=axis2)
        """
        self.axes = OrderedDict(axes)
        self.position = {}
        for a in self.axes:
            self.position[a] = Q_(0.0, self.axes[a].units)
        self.acq_rate = acq_rate
        print('\ninit acq rate:\n', self.acq_rate)
        self.ao_smooth_steps = ao_smooth_steps
        self.current_counter_task = None
        self.counter_tasks = []
        self.sleep_factor = 1
        self.ctr_ch = ctr_ch
        print('init self.sleep_factor to 1')

    def initialize(self):
        self.ao_motion_task = nidaqmx.Task('NIDAQMotionController_AO')

        for a in self.axes:
            min_max_dict = {}
            # TODO allow limits specified in volts as well
            if self.axes[a].limits[0]:
                min_max_dict['min_val'] = self.axes[a].units_to_volts(self.axes[a].limits[0])
            if self.axes[a].limits[1]:
                min_max_dict['max_val'] = self.axes[a].units_to_volts(self.axes[a].limits[1])
            self.ao_motion_task.ao_channels.add_ao_voltage_chan(self.axes[a].ch, 
                                    name_to_assign_to_channel=a,
                                    **min_max_dict)
                                    
        #device_name = list(self.axes.items())[0][1].ch.split('/')[0]
        
        #dev_channel = device_name + '/' + APD_ch
        '''
        Shivam: Think that this is not needed if we manually call new_ctr_task in the main code
        self.collect_task = nidaqmx.Task('heat shock task')
        self.collect_task.ci_channels.add_ci_count_edges_chan(
                        self.ctr_ch,                                                     #dev_channel,
                        edge=nidaqmx.constants.Edge.RISING,
                        initial_count=0,
                        count_direction=nidaqmx.constants.CountDirection.COUNT_UP
        )
        '''

    def finalize(self):
        self.ao_motion_task.close()
        # self.collect_task.close()
        for t in self.counter_tasks:
            t.close()
    '''
    def new_ctr_task(self, ctr_ch):
        self.current_counter_task = nidaqmx.Task('NIDAQMotionController_CTR_{}'.format(np.random.randint(2**31)))
        self.current_counter_task.ci_channels.add_ci_count_edges_chan(ctr_ch)
        self.counter_tasks.append(self.current_counter_task)
    ''' 
    def new_ctr_task(self, ctr_ch):
        self.current_counter_task = nidaqmx.Task('NIDAQMotionController_CTR_{}'.format(np.random.randint(2**31)))
        self.current_counter_task.ci_channels.add_ci_count_edges_chan(ctr_ch,
                                                    edge=nidaqmx.constants.Edge.RISING,
                                                    initial_count=0,
                                                    count_direction=nidaqmx.constants.CountDirection.COUNT_UP)
        self.counter_tasks.append(self.current_counter_task)
    def enforce_point_units(self, point):
        """ 

        e.g.
        (if x.units and y.units = 'um')
        self.enforce_point_units(x=Q_(0.5, 'mm'), y=Q_(1.5, 'um')) ->
            {x: Q_(500.0, 'um'), y: Q_(1.5, 'um')}"""
        new_point = {}
        for axis in point:
            new_point[axis] = self.axes[axis].enforce_units(point[axis])
        return new_point

    def move(self, point, repeats = 40, num_steps_min = 3):
        """Move to a target location using a smooth s-curve-like interpolation
        point: dictionary containing axis names mapped to target values e.g.
        {'x': Q_(0.5, 'um'), 'y': Q_(1.5, 'um')}
        """
        #import pdb; pdb.set_trace()
        #print("start move")
        target = self.enforce_point_units(point)
        ## must add a range in for 40
        #import pdb; pdb.set_trace()
        #print('where i end up', target)
        range_list = []
        #print('i go to', target, 'from', self.position)
        for i in ['x', 'y', 'z']:
            range_list.append(abs((target[i] - self.position[i]).to('um').m))
        #print(range_list)
        #print(max(range_list))
        #print(self.position)
        #print(**self.position)
        num_steps = num_steps_min + int(round(max(range_list)))
        step_voltages = self.linear_func(self.position, target, num_steps)
        step_voltages = np.repeat(step_voltages, repeats, axis=0)

        #print(2 + int(max(range_list)/2))
        #print ('I am moving')
        #print(step_voltages)
        #print(type(step_voltages))
        if step_voltages.size:
            self.ao_motion_task.timing.cfg_samp_clk_timing(
                self.acq_rate.to('Hz').m,
                sample_mode=nidaqmx.constants.AcquisitionType.FINITE,
                samps_per_chan=step_voltages.shape[0]
            )
            #print("working on line 135")
            self.ao_motion_task.triggers.start_trigger.disable_start_trig()
            sample_writer_stream = AnalogMultiChannelWriter(self.ao_motion_task.out_stream,
                                                                auto_start=False)
            #print("working on line 139")
            # must use array with contiguous memory region because NI uses C arrays under the hood
            ni_sample_buffer = np.ascontiguousarray(step_voltages.transpose(), dtype=float)
            #print("buffer made")
            # TODO timeout
            sample_writer_stream.write_many_sample(ni_sample_buffer, timeout=10)
            #print("samples written")
            
            #print('self.sleep_factor in move():', self.sleep_factor)
            self.ao_motion_task.start()
            self.ao_motion_task.wait_until_done()
            self.ao_motion_task.stop()
        #print("end move")
        self.position = target

    def line_scan(self, init_point, final_point, steps, pts_per_step=1):
        """1-axis line scan while acquiring counter data"""
        #print(init_point)
        #print(final_point)
        init_point = self.enforce_point_units(init_point)
        final_point = self.enforce_point_units(final_point)
        #print(init_point)
        #print('self.sleep_factor in line scan right before calling move():', self.sleep_factor)
        self.move(init_point)
        #print("start line_scan")
        step_voltages = self.linear_func(init_point, final_point, steps)
        step_voltages = np.repeat(step_voltages, pts_per_step + 1, axis=0)
        # configure analog output task
        self.ao_motion_task.timing.cfg_samp_clk_timing(
            self.acq_rate.to('Hz').m,
            sample_mode=nidaqmx.constants.AcquisitionType.FINITE,
            samps_per_chan=step_voltages.shape[0]
        )
        #print('line_scan acq rate:', self.acq_rate)
        #self.ao_motion_task.triggers.start_trigger.disable_start_trig()
        # Shivam: This is the line which writes the voltage values into the ao_motion_task
        # and starts when we write self.ao_motion_task.start() below.
        sample_writer_stream = AnalogMultiChannelWriter(self.ao_motion_task.out_stream,
                                                            auto_start=False)
        # must use array with contiguous memory region because NI uses C arrays under the hood
        # Shivam: This is the section where voltage values are made contiguous and encoded
        ni_ao_sample_buffer = np.ascontiguousarray(step_voltages.transpose(), dtype=np.float)
        # TODO timeout
        sample_writer_stream.write_many_sample(ni_ao_sample_buffer, timeout=60)
        
        # e.g. "Dev1"
        device_name = list(self.axes.items())[0][1].ch.split('/')[0]
        
        # configure counter input task
        self.current_counter_task.timing.cfg_samp_clk_timing(
            self.acq_rate.to('Hz').m,
            source='/{}/ao/SampleClock'.format(device_name),
            sample_mode=nidaqmx.constants.AcquisitionType.FINITE,
            samps_per_chan=step_voltages.shape[0]
        )
        
        # set the counter input to trigger / start acquisition when the AO starts
        self.current_counter_task.triggers.arm_start_trigger.dig_edge_src = '/{}/ao/StartTrigger'.format(device_name)
        self.current_counter_task.triggers.arm_start_trigger.trig_type = nidaqmx.constants.TriggerType.DIGITAL_EDGE
        #self.ao_motion_task.triggers.start_trigger.disable_start_trig()
        
        # create counter stream object
        sample_reader_stream = CounterReader(self.current_counter_task.in_stream)
        
        # must use array with contiguous memory region because NI uses C arrays under the hood
        ni_ctr_sample_buffer = np.ascontiguousarray(np.zeros(step_voltages.shape[0]), dtype=np.uint32)
        
        # start the move
        self.current_counter_task.start()
        self.ao_motion_task.start()
        # TODO timeout
        sample_reader_stream.read_many_sample_uint32(ni_ctr_sample_buffer,
                                        number_of_samples_per_channel=nidaqmx.constants.READ_ALL_AVAILABLE,
                                        timeout=60)
        
        # wait for motion to complete
        #time.sleep((1.1*step_voltages.shape[0] / self.acq_rate).to('s').m)
        
        self.current_counter_task.stop()
        self.ao_motion_task.stop()
        scanned = ni_ctr_sample_buffer.reshape((steps, pts_per_step+1))
        averaged = np.diff(scanned).mean(axis=1)
        self.position = final_point
        print('what is my final point', final_point, self.position)
        return averaged*self.acq_rate.to('Hz').m
    

    def hs_no_move(self, ctr_buffer_size, trigger_ch, timeout):
        """No moving of stage, only collecting temperature measurement data at a single point"""

        
        
        self.counter_buffer = np.ascontiguousarray(np.zeros(ctr_buffer_size), dtype = np.uint32)

        self.current_counter_task.timing.cfg_samp_clk_timing(
                        self.acq_rate.to('Hz').m, # must be equal or larger than max rate expected by PS
                        source= trigger_ch,
                        sample_mode=nidaqmx.constants.AcquisitionType.FINITE, #CONTINUOUS, # can also limit the number of points-
                        samps_per_chan= len(self.counter_buffer)
        )

        self.current_counter_task.start()

        self.sample_reader_stream = CounterReader(self.current_counter_task.in_stream)


        self.sample_reader_stream.read_many_sample_uint32(self.counter_buffer,
                                        number_of_samples_per_channel=nidaqmx.constants.READ_ALL_AVAILABLE,
                                        timeout = timeout)
        
        self.current_counter_task.stop()

        self.current_counter_task.clear()

        return self.counter_buffer



        

    def hs_prepare(self, ctr_buffer_size, buffer_allocation, trigger_ch, init_point, final_point, steps):
        """1-axis line scan while acquiring counter data"""
        #import pdb; pdb.set_trace()
        init_point = self.enforce_point_units(init_point)
        final_point = self.enforce_point_units(final_point)
        #moving to initial point
        self.move(init_point)
        step_voltages, remaining_buffer = self.linear_func_hs(init_point, final_point, steps, buffer_allocation, ctr_buffer_size)
        print(len(step_voltages), ': analog voltage output buffer length')
        print(ctr_buffer_size, ': read counter buffer length')
        # e.g. "Dev1"
        
        
        self.counter_buffer = np.ascontiguousarray(np.zeros(ctr_buffer_size), dtype = np.uint32)

        
        self.current_counter_task.timing.cfg_samp_clk_timing(
                        self.acq_rate.to('Hz').m, # must be equal or larger than max rate expected by PS
                        source= trigger_ch,
                        sample_mode=nidaqmx.constants.AcquisitionType.FINITE, #CONTINUOUS, # can also limit the number of points-
                        samps_per_chan= len(self.counter_buffer)
        )
        
        # configure analog output task
        self.ao_motion_task.timing.cfg_samp_clk_timing(
                        self.acq_rate.to('Hz').m, #step_voltages.shape[0] / time_per_scan.to('s').m, '''careful here'''#,
                        source = trigger_ch,
                        sample_mode=nidaqmx.constants.AcquisitionType.FINITE,
                        samps_per_chan=step_voltages.shape[0]
        )
        #print('line_scan acq rate:', self.acq_rate)
        # Shivam: This is the line which writes the voltage values into the ao_motion_task
        #self.ao_motion_task.triggers.start_trigger.disable_start_trig()
        sample_writer_stream = AnalogMultiChannelWriter(self.ao_motion_task.out_stream,
                                                            auto_start=False)
        # must use array with contiguous memory region because NI uses C arrays under the hood
        # Shivam: This is the section where voltage values are made contiguous and encoded
        ni_ao_sample_buffer = np.ascontiguousarray(step_voltages.transpose(), dtype=np.float)
        self.num_points = step_voltages.shape[0]
        # TODO timeout
        sample_writer_stream.write_many_sample(ni_ao_sample_buffer, timeout=60)
        
        # create counter stream object
        self.sample_reader_stream = CounterReader(self.current_counter_task.in_stream)
        
        # must use array with contiguous memory region because NI uses C arrays under the hood
        #ni_ctr_sample_buffer = np.ascontiguousarray(np.zeros(step_voltages.shape[0]), dtype=np.uint32)
        
        self.current_counter_task.start()
        self.ao_motion_task.start()
        print('finish hs_prepare')
        return remaining_buffer
        
    def hs_linescan(self, timeout):        
        # start the move
        #import pdb; pdb.set_trace()
        # TODO timeout
        self.sample_reader_stream.read_many_sample_uint32(self.counter_buffer,
                                        number_of_samples_per_channel=nidaqmx.constants.READ_ALL_AVAILABLE,
                                        timeout = timeout)
        
        # wait for motion to complete
        #time.sleep((1.1*step_voltages.shape[0] / self.acq_rate).to('s').m)
        # Shivam: Is this wait_until_done() needed? It is not in linescan()
        self.ao_motion_task.wait_until_done()   
        
        self.current_counter_task.stop()
        self.ao_motion_task.stop()
        #scanned = buffer.reshape((steps, pts_per_step+1))
        #averaged = np.diff(scanned).mean(axis=1)
        # counter_data = self.counter_buffer[1:] - self.counter_buffer[:-1]
        
        return self.counter_buffer

            
        
    def raster_scan(self, start, end_of_line, steps, pts_per_step=1):
        """1-axis line scan while acquiring counter data"""
        start = self.enforce_point_units(start)
        end_of_line = self.enforce_point_units(end_of_line)
        self.move(start)
        step_voltages = self.linear_func(start, end_of_line, steps)
        step_voltages = np.repeat(step_voltages, pts_per_step + 1, axis=0)
        
        # configure analog output task
        self.ao_motion_task.timing.cfg_samp_clk_timing(
            self.acq_rate.to('Hz').m,
            sample_mode=nidaqmx.constants.AcquisitionType.FINITE,
            samps_per_chan=step_voltages.shape[0]
        )
        sample_writer_stream = AnalogMultiChannelWriter(self.ao_motion_task.out_stream,
                                                            auto_start=False)
                                                            
        # must use array with contiguous memory region because NI uses C arrays under the hood
        ni_ao_sample_buffer = np.ascontiguousarray(step_voltages.transpose(), dtype=np.float)
        
        # TODO timeout
        sample_writer_stream.write_many_sample(ni_ao_sample_buffer, timeout=60)
        
        # e.g. "Dev1"
        device_name = list(self.axes.items())[0][1].ch.split('/')[0]
        
        # configure counter input task
        self.current_counter_task.timing.cfg_samp_clk_timing(
            self.acq_rate.to('Hz').m,
            source='/{}/ao/SampleClock'.format(device_name),
            sample_mode=nidaqmx.constants.AcquisitionType.FINITE,
            samps_per_chan=step_voltages.shape[0]
        )
        
        # set the counter input to trigger / start acquisition when the AO starts
        self.current_counter_task.triggers.arm_start_trigger.dig_edge_src = '/{}/ao/StartTrigger'.format(device_name)
        self.current_counter_task.triggers.arm_start_trigger.trig_type = nidaqmx.constants.TriggerType.DIGITAL_EDGE
        
        # create counter stream object
        sample_reader_stream = CounterReader(self.current_counter_task.in_stream)
        
        # must use array with contiguous memory region because NI uses C arrays under the hood
        ni_ctr_sample_buffer = np.ascontiguousarray(np.zeros(step_voltages.shape[0]), dtype=np.uint32)
        
        # start the move
        self.current_counter_task.start()
        self.ao_motion_task.start()
        
        # TODO timeout
        sample_reader_stream.read_many_sample_uint32(ni_ctr_sample_buffer,
                                        number_of_samples_per_channel=nidaqmx.constants.READ_ALL_AVAILABLE,
                                        timeout=60)
        
        self.current_counter_task.stop()
        self.ao_motion_task.stop()
        scanned = ni_ctr_sample_buffer.reshape((steps, pts_per_step+1))
        averaged = np.diff(scanned).mean(axis=1)
        self.position = end_of_line
        print('what is my final point', end_of_line, self.position)
        return averaged*(self.acq_rate.to('Hz').m)
        
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
    

    def linear_func_hs(self, start_pt, stop_pt, steps, buffer_allocation, ctr_buffer_size):
        """Generate a set of linearly spaced points between the start and stop point
        return value is in volts. Shivam: Each voltage value is repeated buffer_allocation time 
        for temperature sensing."""
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
        linear_volt = np.outer(np.ones(steps), start_volts) + np.outer(linear_steps, stop_volts-start_volts)
        print("Length of linear_volt is " + str(len(linear_volt)))
        print("Linear volt is " + str(linear_volt))
        
        repeated_linear_volt = np.repeat(linear_volt, buffer_allocation, axis=0)

       
        
        remaining_buffer = ctr_buffer_size - repeated_linear_volt.shape[0]
        
        # Shivam: If the remaining buffer is greater than 0, then repeat the last voltage value (each voltage value is an array of 3 elements for xyz)
        if remaining_buffer > 0:
            print(linear_volt[-1])
            repeated_linear_volt = np.vstack((repeated_linear_volt, np.tile(linear_volt[-1], (remaining_buffer, 1))))
      
        return repeated_linear_volt, remaining_buffer

    def smooth_func(self, start_pt, stop_pt):
        """Generate a set of smooth sinusoidally spaced points between the 
        start and stop point
        return value is in volts"""
        # convert start_pt and stop_pt dictionaries into arrays that contain
        # the corresponding point values in volts
        #import pdb; pdb.set_trace()
        start_volts = np.array([])
        stop_volts = np.array([])
        for axis in self.axes:
            start_volts = np.append(start_volts, self.axes[axis].units_to_volts(start_pt[axis]))
            stop_volts = np.append(stop_volts, self.axes[axis].units_to_volts(stop_pt[axis]))
        # print(start_volts, "are our  start voltages")
        # print(stop_volts, "are our stop voltages")
        steps = int(np.ceil(max(abs(stop_volts - start_volts)) * self.ao_smooth_steps.to('1/V').m))
        # generate a cosine function from 0->pi
        versine_steps = (1.0 - np.cos(np.linspace(0.0, np.pi, steps))) / 2.0
        return np.outer(np.ones(steps), start_volts) + np.outer(versine_steps, stop_volts - start_volts)
