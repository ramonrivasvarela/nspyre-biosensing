###########################
# imports
###########################

# std
import numpy as np
import time
from itertools import cycle
from itertools import count
import logging
import scipy.optimize as sciOP
import scipy.interpolate as sciIP
try:
    import cPickle as pickle
except ImportError:
    import pickle

# nidaqmx
import nidaqmx
from nidaqmx.constants import (AcquisitionType, CountDirection, Edge,
    READ_ALL_AVAILABLE, TaskMode, TriggerType)
from nidaqmx._task_modules.channels.ci_channel import CIChannel
#from nidaqmx.stream_readers import CounterReader

# nspyre
from nspyre.gui.widgets.views import Plot1D, Plot2D, PlotFormatInit, PlotFormatUpdate
from nspyre.spyrelet.spyrelet import Spyrelet
from nspyre.gui.widgets.plotting import LinePlotWidget
from nspyre.gui.colors import colors
from nspyre.definitions import Q_

COLORS = cycle(colors.keys())

###########################
# setup classes
###########################

class TaskVsTimeSpyrelet(Spyrelet):
    REQUIRED_DEVICES = [
        'pulses'
    ]
    PARAMS = {
        'device':{
            'type': str,
            'default': 'Dev1',
        },
        'channel':{
            'type':list,
            'items':list(['ctr0','ctr1','ctr2','ctr3']),
            'default': 'ctr1'
            },
        'time_per_point':{
            'type':float,
            'units': 's',
            'default': 0.1
            },
    }

    def main(self, device, channel, time_per_point, iterations=0):
        start_t = time.time()
        iterator = count() if iterations == 0 else range(iterations)
        for i in self.progress(iterator):
            val = self.read(time_per_point.to('s').m)

            self.acquire({
                't': time.time()-start_t,
                'val': val,
            })
            
    def initialize(self, device, channel, time_per_point, iterations=0):
        
        self.pulses.Pulser.constant(([7],0.0,0.0))
        dev_channel = device + '/' + channel
        self.read_task = nidaqmx.Task()
        self.read_task.ci_channels.add_ci_count_edges_chan(
                                dev_channel,
                                edge=Edge.RISING,
                                initial_count=0,
                                count_direction=CountDirection.COUNT_UP
        )
        self.read_task.start()
        self.read_task.read()

        
    def finalize(self, device, channel, time_per_point, iterations=0):
        self.read_task.stop()
        self.read_task.close()
        
    def read(self, time_per_point):
        ctrs_start = self.read_task.read()
        time.sleep(time_per_point)
        ctrs_end = self.read_task.read()
        dctrs = ctrs_end - ctrs_start
        ctrs_rate = dctrs / time_per_point
        return ctrs_rate
    @PlotFormatUpdate(LinePlotWidget, ['no_trace_all'])#['latest', 'avg'])        
    def update_format(p, df, cache):
        for item in p.plot_item.listDataItems():
            item.setPen(color=(0,0,0,0), width=5)
    @Plot1D
    def no_trace_all(df, cache):
        return {'signal':[df.t.values, df.val.values]}
        
    @Plot1D
    def all(df, cache):
        return {'signal':[df.t.values, df.val.values]}

    @Plot1D
    def latest(df, cache):
        return {'signal':[df.t.tail(100).values, df.val.tail(100).values]}

# class TempVsTimeSpyrelet(Spyrelet):
    
#     REQUIRED_DEVICES = [
#         'ls332',
#     ]

#     PARAMS = {
#         'samples': {
#             'type': int,
#             'default': 100,
#             'positive': True},
#         # 'interpoint_delay': {
#         #     'type': float,
#         #     'default': 0.1,
#         #     'nonnegative': True},

#         # ('heater range', {
#         #     'type': str,
#         #     'default': 3,
#         #     'nonnegative': True,
#         # }),
#         'heater_limit': {
#             'type': float,
#             'default': 25,
#             'nonnegative': True}
#     }

#     def main(self,samples,heater_limit, iterations=0):
#         start_t = time.time()
#         iterator = count() if iterations == 0 else range(iterations)
#         for i in self.progress(iterator):
#             current = [float(self.ls332.query('KRDG?0')) for i in range(samples)]
#             current_avg = np.mean(current)
#             heater = [float(self.ls332.heater_output_1) for i in range(samples)]
#             heater_avg = np.mean(heater)
#             if heater_avg > heater_limit:
#                 self.ls332.write('RANGE 0') #turn off the heater if something goes wrong the PID runs away
#                 print('something has gone wrong. the heater has been turned off.')
#             self.acquire({
#                 'idx': i,
#                 't': time.time() - start_t,
#                 'y': Q_(current_avg,'A'),
#                 'p': Q_(heater_avg,'K'),
#             })

#     def initialize(self,samples,heater_limit, iterations=0):
#         return
    
#     def finalize(self,samples,heater_limit, iterations=0):
#         return
    
#     @Plot1D
#     def temperature(df, cache):
#         return {'signal':[df.t.values, df.y.values]}

#     @Plot1D
#     def temperature_latest(df, cache):
#         return {'signal':[df.t.tail(100).values, df.y.tail(100).values]}

#     @Plot1D
#     def heater(df, cache):
#         return {'signal':[df.t.values, df.p.values]}

#     @Plot1D
#     def heater_latest(df, cache):
#         return {'signal':[df.t.tail(100).values, df.p.tail(100).values]}


# class GoToFieldVXMSpyrelet(Spyrelet):
#     REQUIRED_DEVICES = [
#         'vxm'
#     ]

#     REQUIRED_SPYRELETS = {
#     }

#     PARAMS = {
#         ('velocity', {
#             'type': int,
#             'units': None,
#             'default': 2000},
#         ),
#         ('calibration_date', {
#             'type': str,
#             'default': '20190618'},
#         ),
#         ('directory', {
#             'type': str,
#             'default': 'Y:/projects/magnetcalibration/'
#         },
#         ),
#         ('wait_time', { #(ms)
#             'type': int,
#             'default': 6500,
#             'positive': True,},
#         ),
#         ('field', { #(G)
#             'type': float,
#             'default': '0',
#             'positive': True},
#         ),
#         ('reset_origin', {
#             'type': bool,
#             'default': False,},
#         ),
#         ('range', {
#             'type': int,
#             'units': None,
#             'default': 83800,
#             'positive': True},
#         )
#     }

#     def main(self):
#         self.vxm.abs_position = self.pos

#     def initialize(self,directory,calibration_date,reset_origin,field):
#         file = directory + 'magnet_calibration' + calibration_date + '.pkl'
#         with open(file, 'rb') as f:
#             interpfn = pickle.load(f)
#             if reset_origin == True:
#                 print('resetting origin')
#                 self.vxm.goneg()
#                 time.sleep(reset_origin.time)
#                 self.vxm.setzero()
#             self.pos = round(interpfn(field)[()],2)

###########################
# navigation classes
###########################

# class FlipLightsSpyrelet(Spyrelet):
    

# class TaskVsFSMSpyrelet(Spyrelet):
#     REQUIRED_DEVICES = [
#         'fsm'
#     ]

#     PARAMS = {
#         'xs':               {'type': range, 'units':'um'},
#         'ys':               {'type': range, 'units':'um'},
#         'daq_ch':           {'type': list, 'items':list(self.daq.counter_input_channels)},
#         'sweeps':           {'type': int, 'positive': True},
#         'acq_rate':         {'type': float, 'nonnegative': True, 'units':'Hz'},
#         'pts_per_pixel':    {'type': int, 'positive': True},
#     }

#     def main(self, xs, ys, daq_ch, sweeps, acq_rate, pts_per_pixel):
#         for sweep in self.progress(range(sweeps)):
#             backward = False
#             for column_idx, y in enumerate(self.progress(ys.to('um').m)):
#                 pt0, pt1 = (xs[0].to('um').m, y), (xs[-1].to('um').m, y)
#                 if backward:
#                     pt0, pt1 = pt1, pt0
#                 row_data = self.fsm.line_scan(init_point=pt0, final_point=pt1, steps=len(xs), acq_rate=acq_rate, pts_per_pos=pts_per_pixel)
#                 if backward:
#                     row_data = np.flip(row_data)
#                 self.acquire({
#                     'sweep_idx': sweep,
#                     'column_idx': column_idx,
#                     'row_data': row_data,
#                     'y':y,
#                     'x_vals': xs.to('um').m
#                 })
#                 backward = not backward

        
#     def initialize(self, xs, ys, daq_ch, sweeps, acq_rate, pts_per_pixel):
#         self.fsm.new_input_task([daq_ch])
        
#     def finalize(self, xs, ys, daq_ch, sweeps, acq_rate, pts_per_pixel):
#         pass

#     @PlotFormatInit(HeatmapPlotWidget, ['latest', 'avg'])
#     def init_format(p):
#         p.xlabel = 'X (um)'
#         p.ylabel = 'Y (um)'

#     @PlotFormatUpdate(HeatmapPlotWidget, ['latest', 'avg'])
#     def update_format(p, df, cache):
#         xs, ys     = df.x_vals[0],    df.y.unique()
#         diff       = [xs[-1]-xs[0] , ys[-1]-ys[0]]
#         p.im_pos   = [np.mean(xs) - diff[0]/2 , np.mean(ys) - diff[1]/2]
#         p.im_scale = [diff[0]/len(xs) , diff[1]/len(ys)]
#         p.set(p.w.image) #We have to redraw for the scaling to take effect

#     @Plot2D
#     def latest(df, cache):
#         latest = df[df.sweep_idx == df.sweep_idx.max()]
#         im = np.vstack(latest.sort_values('column_idx')['row_data'])
#         max_rows = len(df.x_vals[0])
#         return np.pad(im, (0, max_rows - im.shape[1]), mode='constant', constant_values=0)

#     @Plot2D
#     def avg(df, cache):
#         grouped = df.groupby('column_idx')['row_data']
#         averaged = grouped.apply(lambda column: np.mean(np.vstack(column), axis=0))
#         im = np.vstack(averaged)
#         max_rows = len(df.x_vals[0])
#         return np.pad(im, (0, max_rows - im.shape[1]), mode='constant', constant_values=0)

# class TaskVsFSMMW2fsSpyrelet(Spyrelet):
#     REQUIRED_DEVICES = [
#         'daq',
#         'fsm',
#         'sg',
#         'pulses'
#     ]

#     REQUIRED_SPYRELETS = {
#         'taskvsfsm': TaskVsFSMSpyrelet
#     }

#     PARAMS = {
#         'xs':               {'type': range, 'units':'um'},
#         'ys':               {'type': range, 'units':'um'},
#         'daq_ch':           {'type': list, 'items':list(self.daq.counter_input_channels), 'default': 'Dev5/ctr1'},
#         'sweeps':           {'type': int, 'positive': True},
#         'acq_rate':         {'type': float, 'nonnegative': True, 'units':'Hz'},
#         'pts_per_pixel':    {'type': int, 'positive': True},
#         'f1':               {'type': float, 'units':GHz},
#         'f2':               {'type': float, 'units':GHz},
#         'rf_amplitude':     {'type':float, 'default': -20},
#         'fnumber':          {'type':list, 'items':list([1,2])}
#     }

#     def main(self,xs,ys,daq_ch,sweeps,acq_rate,pts_per_pixel,f1,f2):
#         self.pulses.Pulser.constant((1,[0,2,4,5],0,0))
#         for sweep in range(sweeps):
#             for i in range(fnumber+1):
#                 if i == 0:
#                     self.pulses.Pulser.constant((1,[0,4,5], 0, 0))
#                     fhere = 0
#                 elif i == 1:
#                     self.pulses.Pulser.constant((1,[0,2,4,5], 0, 0))
#                     fhere = f1
#                     self.sg.frequency = f1
#                 elif i == 2:
#                     self.pulses.Pulser.constant((1,[0,2,4,5], 0, 0))
#                     fhere = f2
#                     self.sg.frequency = f2
#                 self.TaskVsFSMSpyrelet(self,xs,ys,daq_ch,1,acq_rate,pts_per_pixel)
#                 scan = TaskVsFSMSpyrelet.data.tail(1) #?????????????
#                 self.acquire({
#                     'sweep_idx':    sweep,
#                     'scan_data':    scan,
#                     'MWs':          i,
#                     'f':            fhere,
#                 })

#     def initialize(self,rf_amplitude,daq_ch):
#         self.sg.rf_amplitude = rf_amplitude
#         self.sg.mod_type = 'Phase'
#         self.sg.rf_toggle = True
#         self.sg.mod_toggle = False

#         if daq_ch in self.daq.counter_input_channels:
#             self.task = CounterInputTask('TaskVsFSM_CI')
#             channel = CountEdgesChannel(inp_ch)
#             self.task.add_channel(channel)
#             self.diff_task = CounterInputTask('TaskVsFSM_CI_differential')
#         elif daq_ch in self.daq.analog_input_channels:
#             self.task = AnalogInputTask('TaskVsFSM_AI')
#             channel = VoltageInputChannel(inp_ch)
#             self.task.add_channel(channel)
#         else:
#             # should never get here
#             pass

#     def finalize(self):
#         self.fsm.abs_position = (0.0, 0.0)
#         self.task.clear()
#         self.diff_task.clear()
#         self.pulses.Pulser.reser()
#         self.sg.rf_toggle = False

##plotting to finish once I know how data is coming through
    # @Plot2D
    # def latest(df, cache):
    #     latest = df[df.sweep_idx == df.sweep_idx.max()]
    #     im = np.vstack(latest.sort_values('column_idx')['row_data'])
    #     max_rows = len(df.x_vals[0])
    #     return np.pad(im, (0, max_rows - im.shape[1]), mode='constant', constant_values=0)

    # @Plot2D
    # def avg(df, cache):
    #     grouped = df.groupby('column_idx')['row_data']
    #     averaged = grouped.apply(lambda column: np.mean(np.vstack(column), axis=0))
    #     im = np.vstack(averaged)
    #     max_rows = len(df.x_vals[0])
    #     return np.pad(im, (0, max_rows - im.shape[1]), mode='constant', constant_values=0)

# class ManyFSMscanwithXPSSpyrelet(Spyrelet):

# class SpatialFeedbackXYZSpyrelet(Spyrelet):

#     REQUIRED_DEVICES = [
#         'sg',
#         'daq',
#         'pulses',
#         'fsm',
#         'xps'
#     ]

#     PARAMS = {
#             ('acquisition_channel', {
#                 'type': list,
#                 'items': list(self.daq.counter_input_channels), # + list(self.daq.analog_input_channels),
#                 'default': 'Dev5/ctr3',
#             }),
#             ('x_initial', {
#                 'units': 'um',
#                 'type': float,
#                 'default': 0.0,
#             }),
#             ('y_initial', {
#                 'units': 'um',
#                 'type': float,
#                 'default': 0.0,
#             }),
#             ('x_range', {
#                 'units': 'um',
#                 'type': float,
#                 'default': 0.6e-6,
#                 'nonnegative': True,
#             }),
#             ('y_range', {
#                 'units': 'um',
#                 'type': float,
#                 'default': 0.6e-6,
#                 'nonnegative': True,
#             }),
#             ('xy_max_drift', {
#                 'units': 'um',
#                 'type': float,
#                 'default': .3e-6,
#                 'nonnegative': True,
#             }),
#             ('z_range', {
#                 'units': 'um',
#                 'type': float,
#                 'default': 1.0e-6,
#                 'nonnegative': True,
#                 'bounds': [0.0, 10.0e-6],
#             }),
#             ('z_max_drift', {
#                 'units': 'um',
#                 'type': float,
#                 'default': 1.0e-6,
#                 'nonnegative': True,
#             }),
#             ('fsm_scan_steps', {
#                 'type': int,
#                 'default': 25,
#                 'positive': True,
#             }),
#             ('fsm_scan_points', {
#                 'type': int,
#                 'default': 300,
#                 'positive': True,
#             }),
#             ('xps_scan_steps', {
#                 'type': int,
#                 'default': 10,
#                 'positive': True,
#             }),
#             ('xps_interpoint_delay', {
#                 'type': float,
#                 'default': 0.02,
#                 'positive': True,
#             }),
#             ('xyz_iterations', {
#                 'type': int,
#                 'default': 1,
#                 'nonnegative': True,
#             }),
#             ('do_z', {
#                 'type': bool,
#                 'default': True,
#             }),
#             ('contrast_z', {
#                 'type': bool,
#                 'default': False,
#             }),
#             ('odmr_contrast', {
#                 'type': bool,
#                 'default': False,
#             }),
#             ('odmr_f1', {
#                 'type': float,
#                 'default': 2.72e9,
#                 'units':'GHz',
#             }),
#             ('odmr_f2', {
#                 'type': float,
#                 'default': 2.78e9,
#                 'units':'GHz',
#             }),
#             ('odmr_f3', {
#                 'type': float,
#                 'default': 2.78e9,
#                 'units':'GHz',
#             }),
#             ('mw_amplitude', {
#                 'type': float,
#                 'default': -7,
#             }),
#             ('move_to_z_optimum', {
#                 'type': bool,
#                 'default': True,
#             }),
#             ('update_xy_initial_values', {
#                 'type': bool,
#                 'default': True,
#             }),
#             ('gaussian_or_with_parabola', {
#                 'type': bool,
#                 'default': False,
#             }),
#             # ('z feedback enabled', {
#             #     'type': bool,
#             #     'default': True,
#             # })
#         }

#     def main(self, xyz_iterations,x_initial,y_initial,x_range,y_range,initial_z_pos,z_range,xps_scan_steps \
#         xy_max_drift,z_max_drift,do_z):
#         iterations = xyz_iterations
#         # xy parameters
#         init_x = x_initial.to('um').m
#         init_y = y_initial.to('um').m
#         search_x = x_range.to('um').m
#         search_y = y_range.to('um').m
#         x_center = init_x
#         y_center = init_y
#         # z parameters
#         z_center = self.initial_z_pos
#         search_z = z_range.to('mm').m
#         z_scan_steps = xps_scan_steps
#         xps_settle_time = 10e-3
#         max_x_drift = xy_max_drift.to('um').m # 10 um
#         max_y_drift = max_x_drift 
#         max_z_drift = z_max_drift.to('um').m # 50 um
#         x_drift_data = list()
#         y_drift_data = list()
#         z_drift_data = list()
#         amp_drift_data = list()
#         iteration_data = list()

#         for iteration in self.feedback.progress(range(iterations)):
#             #z scan
            
#             z_steps = np.linspace(z_center - search_z, z_center + search_z, z_scan_steps)
#             z_scan_data = list()
#             if do_z:
#                 for z_step in z_steps:
#                     self.xps.abs_position[self.z_positioner_name] = z_step
#                     time.sleep(xps_settle_time)
#                     #x scan
#                     x_steps = np.linspace(x_center - search_x, x_center + search_x, fsm_scan_steps)
#                     x_scan_config = {
#                         'init_point': (y_center, x_steps[0]),
#                         'final_point': (y_center, x_steps[-1]),
#                         'steps': fsm_scan_steps,
#                         'acq_task': self.task,
#                         'acq_rate': Q_(20, 'kHz'),
#                         'pts_per_pos': fsm_scan_points,
#                     }
#                     x_scan_data = self.fsm.line_scan(**x_scan_config)
#                     if self.usegaussian:
#                         p0 = [np.max(x_scan_data), x_steps[np.argmax(x_scan_data)], .4, np.min(x_scan_data)]
#                         try:
#                             popt, pcov = optimize.curve_fit(gaussian, x_steps, x_scan_data, p0=p0)
#                             x_fitted = gaussian(x_steps, *popt)
#                             x_center_fit = popt[1]
#                             xbackground = gaussian(x_steps[0], *popt)
#                             xpeak = gaussian(x_center_fit,*popt)
#                             #print('x peak, background, SBR:' + str(xpeak) +','+ str(xbackground)+','+str(xpeak/xbackground - 1))
#                             if np.min(x_steps) < x_center_fit < np.max(x_steps):
#                                 if popt[0] < 0:
#                                     print("negative fit")
#                                 elif np.abs(x_center_fit - x_center) < max_x_drift:
#                                     x_center = x_center_fit
#                                 else:
#                                     print("X drift limit reached. Setting to previous value.")
#                             else:
#                                 print('Optimum X out of scan range. Setting to previous value.')
#                         except RuntimeError:
#                             print('no x fit')
#                             x_fitted = gaussian(x_steps, *p0)
#                             x_center = x_center
                        
#                     else:
#                         p0 = [np.max(x_scan_data), x_center, x_center, .4, 0, np.max(x_scan_data), 0]
#                         try:
#                             popt, pcov = optimize.curve_fit(gaussparab, x_steps, x_scan_data, p0=p0)
#                             x_fitted = gaussparab(x_steps, *popt)
#                             x_center_fit = popt[1]
#                             if np.min(x_steps) < x_center_fit < np.max(x_steps):
#                                 if popt[0] < 0:
#                                     print("negative fit")
#                                 elif np.abs(x_center_fit - x_center) < max_x_drift:
#                                     x_center = x_center_fit
#                                     #print('x_center from fit:', x_center)
#                                 else:
#                                     print("X drift limit reached. Setting to previous value.")
#                             else:
#                                 print('Optimum X out of scan range. Setting to previous value.')
#                         except RuntimeError:
#                             print('no x fit')
#                             x_fitted = gaussparab(x_steps, *p0)
#                             x_center = p0[1]
#                     self.fsm.abs_position = y_center, x_center #or flipped???
#                     # y scan
#                     y_steps = np.linspace(y_center - search_y, y_center + search_y, fsm_scan_steps)
#                     y_scan_config = {
#                         'init_point': (y_steps[0], x_center),
#                         'final_point': (y_steps[-1], x_center),
#                         'steps': fsm_scan_steps,
#                         'acq_task': self.task,
#                         'acq_rate': Q_(20, 'kHz'),
#                         'pts_per_pos': fsm_scan_points,
#                     }
#                     y_scan_data = self.fsm.line_scan(**y_scan_config)
#                     if self.usegaussian:
#                         p0 = [np.max(y_scan_data), y_steps[np.argmax(y_scan_data)], .4, np.min(y_scan_data)]
#                         try:
#                             popt, pcov = optimize.curve_fit(gaussian, y_steps, y_scan_data, p0=p0)
#                             y_fitted = gaussian(y_steps, *popt)
#                             y_center_fit = popt[1]
#                             ybackground = gaussian(y_steps[0], *popt)
#                             ypeak = gaussian(y_center_fit,*popt)
#                             #print('y peak, background, SBR:' + str(ypeak) +','+ str(ybackground)+','+str(ypeak/ybackground - 1))
#                             if np.min(y_steps) < y_center_fit < np.max(y_steps):
#                                 if np.abs(y_center_fit - y_center) < max_y_drift:
#                                     y_center = y_center_fit
#                                 else:
#                                     print("Y drift limit reached. Setting to previous value.")
#                             else:
#                                 print('Optimum Y out of scan range. Setting to previous value.')
#                         except RuntimeError:
#                             print('no y fit')
#                             y_fitted = gaussian(y_steps, *p0)
#                             y_center = y_center
                        
#                     else:
#                         p0 = [np.max(y_scan_data), y_center, y_center, .4, 0, np.max(y_scan_data), 0]
#                         try:
#                             popt, pcov = optimize.curve_fit(gaussparab, y_steps, y_scan_data, p0=p0)
#                             y_fitted = gaussparab(y_steps, *popt)
#                             y_center_fit = popt[1]
#                             if np.min(y_steps) < y_center_fit < np.max(y_steps):
#                                 if np.abs(y_center_fit - y_center) < max_y_drift:
#                                     y_center = y_center_fit
#                                 else:
#                                     print("Y drift limit reached. Setting to previous value.")
#                             else:
#                                 print('Optimum Y out of scan range. Setting to previous value.')
#                         except RuntimeError:
#                             print('no y fit')
#                             y_fitted = gaussparab(y_steps, *p0)
#                             y_center = y_center
            
#                     self.fsm.abs_position = y_center, x_center
#                     self.task.clear()
#                     self.task = CounterInputTask('Feedback3D_CI')
#                     channel = CountEdgesChannel(self.inp_ch)
#                     self.task.add_channel(channel)
#                     self.task.start()               
#                     if self.z_contrast:
#                         if self.odmr_contrast:
#                             self.sg.frequency = self.f1
#                             self.sg.rf_toggle = True
#                             self.pulses.Pulser.constant((1,[0,2,4], 0, 0))
#                             f1PL = self.read()
#                             print(f1PL)
#                             self.sg.frequency = self.f2
#                             f2PL = self.read()
#                             self.sg.frequency = self.f3
#                             f3PL = self.read()
#                             self.sg.rf_toggle = False
#                             self.pulses.Pulser.constant((1,[0,4], 0, 0))
#                             contrast = np.abs(f2PL - f1PL) / f3PL
#                         else:
#                             contrast = (np.max(y_scan_data) - np.min(y_scan_data)) / np.min(y_scan_data)
#                         z_scan_datum = contrast

#                     else:
#                         z_scan_datum = self.read()
#                     self.task.stop()
#                     z_scan_data.append(z_scan_datum)
                
                
#                 self.task.stop()
#                 z_scan_data = np.array(z_scan_data)
#                 p0 = [np.max(z_scan_data), z_steps[np.argmax(z_scan_data)], 1e-3, np.min(z_scan_data)]
#                 try:
#                     popt_z, pcov_z = optimize.curve_fit(gaussian, z_steps, z_scan_data, p0=p0)
#                     z_fitted = gaussian(z_steps, *popt_z)
#                     z_center_fit = popt_z[1]
#                 except RuntimeError:
#                     z_center_fit = z_center
#                     pass
                
#                 if move_to_z_optimum:
#                     if np.min(z_steps) < z_center_fit < np.max(z_steps):
#                         if np.abs(z_center_fit - z_center) < max_z_drift:
#                         # print('New optimum, delta_z={} um'.format((z_center_fit-z_center)*1e3))
#                             z_center = z_center_fit
#                             print('changed to fit')
#                         else:
#                             print('Z drift limit reached. Setting to previous value.')
#                     else:
#                         print('Optimum Z out of scan range. Setting to previous value.')
            
#                 self.xps.abs_position[self.z_positioner_name] = z_center
#                 time.sleep(xps_settle_time)
#                 x_center = init_x
#                 y_center = init_y
#             #x scan
#             x_steps = np.linspace(x_center - search_x, x_center + search_x, fsm_scan_steps)
#             x_scan_config = {
#                 'init_point': (y_center, x_steps[0]),
#                 'final_point': (y_center, x_steps[-1]),
#                 'steps': fsm_scan_steps,
#                 'acq_task': self.task,
#                 'acq_rate': Q_(20, 'kHz'),
#                 'pts_per_pos': fsm_scan_points,
#             }
#             x_scan_data = self.fsm.line_scan(**x_scan_config)
#             if self.usegaussian:
#                 p0 = [np.max(x_scan_data), x_steps[np.argmax(x_scan_data)], .4, np.min(x_scan_data)]
#                 try:
#                     popt, pcov = optimize.curve_fit(gaussian, x_steps, x_scan_data, p0=p0)
#                     x_fitted = gaussian(x_steps, *popt)
#                     x_center_fit = popt[1]
#                     xbackground = gaussian(x_steps[0], *popt)
#                     xpeak = gaussian(x_center_fit,*popt)
#                     print('x peak, background, SBR:' + str(xpeak) +','+ str(xbackground)+','+str(xpeak/xbackground - 1))
#                     if np.min(x_steps) < x_center_fit < np.max(x_steps):
#                         if popt[0] < 0:
#                             print("negative fit")
#                         elif np.abs(x_center_fit - x_center) < max_x_drift:
#                             x_center = x_center_fit
#                         else:
#                             print("X drift limit reached. Setting to previous value.")
#                     else:
#                         print('Optimum X out of scan range. Setting to previous value.')
#                 except RuntimeError:
#                     print('no x fit')
#                     x_fitted = gaussian(x_steps, *p0)
#                     x_center = x_center
                
#             else:
#                 p0 = [np.max(x_scan_data), x_center, x_center, .4, 0, np.max(x_scan_data), 0]
#                 try:
#                     popt, pcov = optimize.curve_fit(gaussparab, x_steps, x_scan_data, p0=p0)
#                     x_fitted = gaussparab(x_steps, *popt)
#                     x_center_fit = popt[1]
#                     if np.min(x_steps) < x_center_fit < np.max(x_steps):
#                         if popt[0] < 0:
#                             print("negative fit")
#                         elif np.abs(x_center_fit - x_center) < max_x_drift:
#                             x_center = x_center_fit
#                             print('x_center from fit:', x_center)
#                         else:
#                             print("X drift limit reached. Setting to previous value.")
#                     else:
#                         print('Optimum X out of scan range. Setting to previous value.')
#                 except RuntimeError:
#                     print('no x fit')
#                     x_fitted = gaussparab(x_steps, *p0)
#                     x_center = p0[1]
#             self.fsm.abs_position = y_center, x_center #or flipped???
#             # y scan
#             y_steps = np.linspace(y_center - search_y, y_center + search_y, fsm_scan_steps)
#             y_scan_config = {
#                 'init_point': (y_steps[0], x_center),
#                 'final_point': (y_steps[-1], x_center),
#                 'steps': fsm_scan_steps,
#                 'acq_task': self.task,
#                 'acq_rate': Q_(20, 'kHz'),
#                 'pts_per_pos': fsm_scan_points,
#             }
#             y_scan_data = self.fsm.line_scan(**y_scan_config)
#             if self.usegaussian:
#                 p0 = [np.max(y_scan_data), y_steps[np.argmax(y_scan_data)], .4, np.min(y_scan_data)]
#                 try:
#                     popt, pcov = optimize.curve_fit(gaussian, y_steps, y_scan_data, p0=p0)
#                     y_fitted = gaussian(y_steps, *popt)
#                     y_center_fit = popt[1]
#                     ybackground = gaussian(y_steps[0], *popt)
#                     ypeak = gaussian(y_center_fit,*popt)
#                     print('y peak, background, SBR:' + str(ypeak) +','+ str(ybackground)+','+str(ypeak/ybackground - 1))
#                     if np.min(y_steps) < y_center_fit < np.max(y_steps):
#                         if np.abs(y_center_fit - y_center) < max_y_drift:
#                             y_center = y_center_fit
#                         else:
#                             print("Y drift limit reached. Setting to previous value.")
#                     else:
#                         print('Optimum Y out of scan range. Setting to previous value.')
#                 except RuntimeError:
#                     print('no y fit')
#                     y_fitted = gaussian(y_steps, *p0)
#                     y_center = y_center
                
#             else:
#                 p0 = [np.max(y_scan_data), y_center, y_center, .4, 0, np.max(y_scan_data), 0]
#                 try:
#                     popt, pcov = optimize.curve_fit(gaussparab, y_steps, y_scan_data, p0=p0)
#                     y_fitted = gaussparab(y_steps, *popt)
#                     y_center_fit = popt[1]
#                     if np.min(y_steps) < y_center_fit < np.max(y_steps):
#                         if np.abs(y_center_fit - y_center) < max_y_drift:
#                             y_center = y_center_fit
#                         else:
#                             print("Y drift limit reached. Setting to previous value.")
#                     else:
#                         print('Optimum Y out of scan range. Setting to previous value.')
#                 except RuntimeError:
#                     print('no y fit')
#                     y_fitted = gaussparab(y_steps, *p0)
#                     y_center = y_center
      
#             self.fsm.abs_position = y_center, x_center #or flipped???

#             if do_z:
#                 x_drift_data.append(x_center - init_x)
#                 y_drift_data.append(y_center - init_y)
#                 z_drift_data.append(1000*(z_center - self.initial_z_pos))
#                 amp_drift_data.append(np.max(y_scan_data))
#                 iteration_data.append(iteration)
#                 values = {
#                 'iteration': iteration,
#                 'x_scan_range': x_steps,
#                 'y_scan_range': y_steps,
#                 'x_data': x_scan_data,
#                 'y_data': y_scan_data,
#                 'x_fitted': x_fitted,
#                 'y_fitted': y_fitted,
#                 'x_center': x_center,
#                 'y_center': y_center,
#                 'amp_drift_data': np.array(amp_drift_data),
#                 'z_scan_range': z_steps,
#                 'z_data': z_scan_data,
#                 'z_fitted': z_fitted,
#                 'z_center': z_center,
#                 'x_drift_data': np.array(x_drift_data),
#                 'y_drift_data': np.array(y_drift_data),
#                 'z_drift_data': np.array(z_drift_data),
#                 'iteration_data': np.array(iteration_data),
#                 }
#             else:
#                 x_drift_data.append(x_center - init_x)
#                 y_drift_data.append(y_center - init_y)
#                 iteration_data.append(iteration)
#                 amp_drift_data.append(np.max(y_scan_data))
#                 values = {
#                     'iteration': iteration,
#                     'x_scan_range': x_steps,
#                     'y_scan_range': y_steps,
#                     'x_data': x_scan_data,
#                     'y_data': y_scan_data,
#                     'x_fitted': x_fitted,
#                     'y_fitted': y_fitted,
#                     'x_center': x_center,
#                     'y_center': y_center,
#                     'amp_drift_data': np.array(amp_drift_data),
#                     'x_drift_data': np.array(x_drift_data),
#                     'y_drift_data': np.array(y_drift_data),
#                     'iteration_data': np.array(iteration_data),
#                     }
#             # print("initial_z_pos:", self.initial_z_pos, "z_center:", z_center, "xps.z:", self.xps.abs_position[self.z_positioner_name].to('mm').m)
            
#             # drift data


#             self.pos = [Q_(x_center,'um'), Q_(y_center,'um'), z_center]
#             self.feedback.acquire(values)

#     def initialize(self, contrast_z,odmr_contrast,odmr_f1,odmr_f2,odmr_f3,mw_amplitude,gaussian_or_with_parabola \
#         xps_interpoint_delay, acquisition_channel):
#         self.z_positioner_name = 'Group3.Pos'
#         self.z_contrast = contrast_z
#         self.odmr_contrast = odmr_contrast
#         self.f1 = odmr_f1
#         self.f2 = odmr_f2
#         self.f3 = odmr_f3

#         if self.odmr_contrast:
#             self.sg.rf_amplitude = mw_amplitude
#             self.sg.mod_type = 'Phase'
#             self.sg.rf_toggle = False
#             self.sg.mod_toggle = False

#         self.usegaussian = gaussian_or_with_parabola
#         self.initial_z_pos = self.xps.abs_position[self.z_positioner_name]
#         print(self.initial_z_pos)
#         self.delay = xps_interpoint_delay
#         inp_ch = acquisition_channel
#         self.inp_ch = inp_ch
#         if inp_ch in self.daq.counter_input_channels:
#             self.task = CounterInputTask('Feedback3D_CI')
#             channel = CountEdgesChannel(inp_ch)
#             self.task.add_channel(channel)
#             self.read = self.ci_read
#         elif inp_ch in self.daq.analog_input_channels:
#             self.task = AnalogInputTask('Feedback3D_AI')
#             channel = VoltageInputChannel(inp_ch)
#             self.task.add_channel(channel)
#         else:
#             pass
#         self.pos = [x_initial,y_initial, self.initial_z_pos]
#         return

#     @feedback.finalizer
#     def finalize(self),update_xy_initial_values: ##note about setting
#         if update_xy_initial_values:
#             kwargs = {'x initial': self.pos[0],
#                       'y initial': self.pos[1],
#                      }
#             self.PARAMS.set(**kwargs)
#         self.task.clear()
#         return

#     def ci_read(self):
#         ctr_start = self.task.read(samples_per_channel=1)[0]
#         t0 = time.time()
#         time.sleep(self.delay)
#         ctr_end = self.task.read(samples_per_channel=1)[0]
#         tf = time.time()
#         ct_rate = (ctr_end - ctr_start) / (tf - t0)
#         return ct_rate

#     def gaussian(xs, a=1, x=0, width=1, b=0):
#         return a * np.exp(-np.square((xs - x) / width)) + b
#     def parabola(xs, ap=1, x0=0, bp=0):
#         return ap * np.square(xs - x0) + bp
#     def gaussparab(xs, a=1, x0g=0, x0p=0, width=1, b=0, ap=1, bp=0):
#         return gaussian(xs,a,x0g,width,b) + parabola(xs,ap,x0p,bp)

#     @Plot1D
#     def x_scan(df,cache):
#         latest_data = df.tail(1)
#         return {'x-scan':[list(latest_data.x_scan_range)[0], list(latest_data.x_data)[0]],
#                 'x_scan fit':[list(latest_data.x_scan_range)[0], list(latest_data.x_fitted)[0]]
#         }

#     @Plot1D
#     def y_scan(df,cache):
#         latest_data = df.tail(1)
#         return {'y-scan':[list(latest_data.y_scan_range)[0], list(latest_data.y_data)[0]],
#                 'y_scan fit':[list(latest_data.y_scan_range)[0], list(latest_data.y_fitted)[0]]
#         }

#     @Plot1D
#     def z_scan(df,cache):
#         latest_data = df.tail(1)
#         return {'z-scan':[list(latest_data.z_scan_range)[0], list(latest_data.z_data)[0]],
#                 'z_scan fit':[list(latest_data.z_scan_range)[0], list(latest_data.z_fitted)[0]]
#         }

#     @Plot1D
#     def drift(df,cache):
#         latest_data = df.tail(1)
#         if do_z:
#             return {
#                 'X': [list(latest_data.iteration_data)[0], list(latest_data.x_drift_data)[0]],
#                 'Y': [list(latest_data.iteration_data)[0], list(latest_data.y_drift_data)[0]],
#                 'Z': [list(latest_data.iteration_data)[0], list(latest_data.z_drift_data)[0]]
#             }
#         else:
#             return {
#                 'X': [list(latest_data.iteration_data)[0], list(latest_data.x_drift_data)[0]],
#                 'Y': [list(latest_data.iteration_data)[0], list(latest_data.y_drift_data)[0]],
#             }


###########################
# calibration classes
###########################

# class AOMLagSpyrelet(Spyrelet):
#     REQUIRED_DEVICES = [
#         'daq',
#         'pulses',
#     ]

#     REQUIRED_SPYRELETS = {
#     }

#     PARAMS = {
#         ('counter_1', {
#             'type': list,
#             'items': list(self.daq.counter_input_channels),
#             'default': 'Dev5/ctr3',
#         }),
#         ('counter_2', {
#             'type': list,
#             'items': list(self.daq.counter_input_channels),
#             'default': 'Dev5/ctr2',
#         }),
#         ('interpoint_delay', {
#             'type': float,
#             'default': 1,
#             'nonnegative': True,
#         }),
#         ('sweeps', {
#             'type': int,
#             'default': 100,
#             'positive': True,
#         }),
#         ('gate_start', {
#             'type': range,
#             'units': "us",
#             'default': {'func': 'linspace',
#                         'start': 100e-9,
#                         'stop': 10e-6,
#                         'num': 51},
#         }),
#         ("probe_time", {
#             'type': float,
#             'default': 3.5e-6,
#             'suffix': ' s',
#             'units': "s"
#         }),
#         ("gate time", {
#             'type': float,
#             'default': 10e-9,
#             'suffix': ' s',
#             'units': "s"
#         }),
#         ("laser_start", {
#             'type': float,
#             'default': 2e-6,
#             'suffix': ' s',
#             'units': "s"
#         }),
#     }

#     def main(self,sweeps,gate_time):
#         for sweep in self.progress(range(sweeps)):
#             for i, t in enumerate(gate_start.array):
#                 sw_time = int(round(t.to("ns").magnitude))*1e-3
#                 self.pulses.stream(self.seqs[i])
#                 ctrs_start = np.array([(task.read(samples_per_channel=1)[-1], time.time()) for task in self.ctr_tasks])
#                 time.sleep(interpoint_delay)
#                 ctrs_end = np.array([(task.read(samples_per_channel=1)[-1], time.time()) for task in self.ctr_tasks])
#                 dctrs = ctrs_end - ctrs_start
#                 ctrs_rates = dctrs[:,0] / dctrs[:,1]
#                 self.acquire({
#                     'sweep_idx': sweep,
#                     't': sw_time,
#                     'x': ctrs_rates[0]*self.ratio,
#                     'y': ctrs_rates[1]*self.ratio,
#                     'diff': (ctrs_rates[0] - ctrs_rates[1])*self.ratio
#                 })

#     def initialize(self,counter_1,counter_2):
#         self.ctrs = [counter_1, counter_2]
#         if len(set(self.ctrs)) != len(self.ctrs):
#             raise RuntimeError('counter channels 1 and 2 must be different')
#         self.ctr_tasks = list()
#         for idx, ctr in enumerate(self.ctrs):
#             task = CounterInputTask('counter ch {}'.format(idx))
#             ch = CountEdgesChannel(ctr)
#             task.add_channel(ch)
#             task.start()
#             self.ctr_tasks.append(task)
#         self.setup_pulses(self,probe_time,gate_time,laser_start,gate_start)
#         return

#     def finalize(self):
#         for ctr_task in self.ctr_tasks:
#             ctr_task.clear()
#         self.sg.rf_toggle = False
#         self.pulses.Pulser.reset()
#         return

#     def setup_pulses(self,probe_time,gate_time,laser_start,gate_start):
#         self.pulses.laser_time = int(probe_time.to("ns").magnitude)
#         self.pulses.gate_time = int(gate_time.to("ns").magnitude)
#         self.pulses.laser_start = int(laser_start.to("ns").magnitude)
#         self.seqs = self.pulses.AOM_lag(gate_start)
#         self.ratio = self.pulses.total_time / (2 * self.pulses.readout_time)

# class MagnetCalibrationSpyrelet(Spyrelet):

#     REQUIRED_DEVICES = [
#         'vxm',
#         'gaussm'
#     ]

#     PARAMS = {
#         ('velocity', {
#                 'type': int,
#                 'units': None,
#                 'default': 2000},
#             ),
#             ('position', {
#                 'type': range,
#                 'units': None,
#                 'default': {'func': 'linspace',
#                             'start': 0,
#                             'stop': 82500,
#                             'num': 100},
#             }),
#             ('B_pts', {
#                 'type': int,
#                 'default': 10,
#                 'positive': True,
#             }),
#             ('sweeps', {
#                 'type': int,
#                 'default': 10, #l.field
#                 'positive': True,
#             }),
#             ('wait_time', { #(ms)
#                 'type': int,
#                 'default': 2000,
#                 'positive': True,
#             }),
#             ('reset', {
#                 'type': bool,
#                 'default': False,
#             }),
#             ('step_max', {
#                 'type': int,
#                 'default': 83800,
#             }),
#             ('save_interpolation_function', {
#                 'type': bool,
#                 'default': True,
#             }),
#             ('directory', {
#                 'type': str,
#                 'default': 'W:/projects/magnetcalibration/'
#             },
#             ),
#             ('date', {
#                 'type': str,
#                 'default': '20190606'},
#             ),
#     }

#     def main(self,position,sweeps,velocity,wait_time,save_interpolation_function,directory,date):
#         pos = position.array
#         step = (pos[-1]-pos[0])/(pos.size-1)
#         for sweep in self.sweep.progress(range(sweeps)):
#             for pi,p in enumerate(pos):
#                 if pi == 0:
#                     if sweep == 0:
#                         p_prev = 0
#                     else:
#                         p_prev = pos[-1]
#                 else:
#                     p_prev = pos[pi-1]
#                 dist = abs(p_prev - p)
#                 moving = dist/velocity
#                 self.vxm.abs_position = p
#                 time.sleep(moving)
#                 time.sleep(wait_time)
#                 Bs = [self.gaussm.field.m for _ in range(B_pts)] #collect B_pts data
#                 self.acquire({
#                     'sweep_idx': sweep,
#                     'pos': p,
#                     'B': np.mean(Bs), #average collected B
#                 })
            
#             #self.vxm.gozero()
#             #time.sleep(reset_time) #time to move back to start
#             #print('moved back')
#             #time.sleep(wait_time) #wait for field read to equilibrate
#             #print('waited')
#         #now make interpolation function
#         grouped = data.groupby('pos')
#         xs = grouped.B
#         xs_averaged = xs.mean()
#         if save_interpolation_function == True:
#             file = directory+'magnet_calibration'+date+'.pkl'
#             interpfn = sciIP.InterpolatedUnivariateSpline(xs_averaged,xs_averaged.index)
#             with open(file, 'wb') as f:
#                 pickle.dump(interpfn, f)

#     def initialize(self,wait_time,full_range,velocity):
#         wait_time = Q_(str(wait_time)+' ms').to('s').m
#         if reset:
#             reset_time = full_range/velocity
#             self.vxm.goneg()
#             self.vxm.setzero()
#             time.sleep(reset_time)
#             time.sleep(wait_time)

#     def finalize(self):
#         self.vxm.write('D')
#         self.vxm.gozero()


# class ReadoutCalibrationSpyrelet(Spyrelet):
#     REQUIRED_DEVICES = [
#         'sg',
#         'daq',
#         'pulses',
#     ]

#     REQUIRED_SPYRELETS = {
#     }

#     PARAMS = {
#         ('counter_1', {
#             'type': list,
#             'items': list(self.daq.counter_input_channels),
#             'default': 'Dev5/ctr3',
#         }),
#         ('counter_2', {
#             'type': list,
#             'items': list(self.daq.counter_input_channels),
#             'default': 'Dev5/ctr2',
#         }),
#         ('interpoint_delay', {
#             'type': float,
#             'default': 1,
#             'nonnegative': True,
#         }),
#         ('sweeps', {
#             'type': int,
#             'default': 100,
#             'positive': True,
#         }),
#         ('frequency', {
#             'type': float,
#             'units':'GHz',
#         }),
#         ('rf_amplitude', {
#             'type': float,
#             'default': -20,
#         }),
#         ("pi_time", {
#             'type': float,
#             'default': 100e-9,
#             'suffix': ' s',
#             'units': "s"
#         }),
#         ('sequence', {
#             'type': list,
#             'items': list(['readout','init','initMWinit']),
#         }),
#         ('vary_time', {
#             'type': range,
#             'units': "ns",
#             'default': {'func': 'linspace',
#                         'start': 5e-9,
#                         'stop': 500e-9,
#                         'num': 101},
#         }),
#         ("other_time", {
#             'type': float,
#             'default': 3.5e-6,
#             'suffix': ' s',
#             'units': "s"
#         }),
#         ("aom_lag", {
#             'type': float,
#             'default': .730e-6,
#             'suffix': ' s',
#             'units': "s"
#         }),
#         ("buffer_time", {
#             'type': float,
#             'default': .2e-6,
#             'suffix': ' s',
#             'units': "s"
#         }),
#     }

#     def main(self,sweeps,mw_time,feedback,xy_feedback_sweeps,z_feedback_sweeps,x_initial,y_initial,frequency):
#         for sweep in self.progress(range(sweeps)):
#             if feedback:
#                 self.run_feedback(self,sweep,xy_feedback_sweeps,z_feedback_sweeps)
#             for i, t in enumerate(mw_time.array):
#                 self.pulses.stream(self.seqs[i])
#                 ctrs_start = np.array([(task.read(samples_per_channel=1)[-1], time.time()) for task in self.ctr_tasks])
#                 time.sleep(interpoint_delay)
#                 ctrs_end = np.array([(task.read(samples_per_channel=1)[-1], time.time()) for task in self.ctr_tasks])
#                 dctrs = ctrs_end - ctrs_start
#                 ctrs_rates = dctrs[:,0] / dctrs[:,1]
#                 self.acquire({
#                     'sweep_idx': sweep,
#                     't': t,
#                     'f': frequency,
#                     'power': rf_amplitude,
#                     'x': ctrs_rates[0]*self.ratio,
#                     'y': ctrs_rates[1]*self.ratio,
#                     'diff': (ctrs_rates[0] - ctrs_rates[1])*self.ratio
#                 })

#     def initialize(self,rf_amplitude,frequency,counter_1,counter_2,sequence,pi_time,other_time,vary_time,aom_lag,buffer_time):

#         self.sg.rf_amplitude = rf_amplitude
#         self.sg.frequency = frequency
#         self.sg.mod_type = 'QAM'
#         self.sg.rf_toggle = True
#         self.sg.mod_toggle = True
#         self.sg.mod_function = 'external'

#         self.ctrs = [params['counter 1'], params['counter 2']]
#         if len(set(self.ctrs)) != len(self.ctrs):
#             raise RuntimeError('counter channels 1 and 2 must be different')
#         self.ctr_tasks = list()
#         for idx, ctr in enumerate(self.ctrs):
#             task = CounterInputTask('counter ch {}'.format(idx))
#             ch = CountEdgesChannel(ctr)
#             task.add_channel(ch)
#             task.start()
#             self.ctr_tasks.append(task)

#         self.setup_pulses(self,sequence,pi_time,other_time,vary_time,aom_lag,buffer_time)
#         return

#     def finalize(self):
#         for ctr_task in self.ctr_tasks:
#             ctr_task.clear()
#         self.sg.rf_toggle = False
#         self.pulses.Pulser.reset()
#         return

#     def setup_pulses(self,sequence,pi_time,other_time,vary_time,aom_lag,buffer_time):
#         if sequence = initMWinit:
#             self.pulses.laser_time = int(params["pi time"].to("ns").magnitude)
#             self.pulses.readout_time = int(params["other time"].to("ns").magnitude)
#             self.seqs = self.pulses.MWoverlapinit(params["vary time"])
#             self.ratio = self.pulses.total_time / (2 * self.pulses.readout_time)
#         elif sequence = init:
#             self.pulses.aom_lag = int(params["aom lag"].to("ns").magnitude)
#             self.pulses.readout_time = int(params["other time"].to("ns").magnitude)
#             self.pulses.laser_buf = int(params["buffer time"].to("ns").magnitude)
#             self.seqs = self.pulses.initcal(params["vary time"],params["pi time"])
#             self.ratio = self.pulses.total_time / (2 * self.pulses.readout_time)
#         else:
#             self.pulses.laser_time = int(params["other time"].to("ns").magnitude)
#             self.pulses.aom_lag = int(params["aom lag"].to("ns").magnitude)
#             #self.pulses.readout_time = int(params["readout time"].to("ns").magnitude)
#             self.pulses.laser_buf = int(params["buffer time"].to("ns").magnitude)
#             self.seqs = self.pulses.readout(params["vary time"],params["pi time"])
#             self.ratio = self.pulses.total_time / (2 * self.pulses.readout_time)
