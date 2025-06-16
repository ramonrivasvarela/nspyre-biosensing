###########################
# imports
###########################

# std
import numpy as np
from scipy import optimize
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
from math import ceil

# nidaqmx
import nidaqmx
from nidaqmx.constants import (AcquisitionType, CountDirection, Edge,
    READ_ALL_AVAILABLE, TaskMode, TriggerType)
from nidaqmx._task_modules.channels.ci_channel import CIChannel
from nidaqmx.stream_readers import CounterReader


# nspyre
from nspyre.gui.widgets.views import Plot1D, Plot2D, PlotFormatInit, PlotFormatUpdate
from nspyre.spyrelet.spyrelet import Spyrelet
from nspyre.gui.widgets.plotting import LinePlotWidget, HeatmapPlotWidget
from nspyre.gui.colors import colors
from nspyre.definitions import Q_

COLORS = cycle(colors.keys())

from lantz.drivers.ni.UriFSM import UriSetup
#from lantz.drivers.ni.ni_motion_controller import NIDAQMotionController



#Jacob's advice
import rpyc

class SpatialFeedbackXYZSpyrelet(Spyrelet):

    REQUIRED_DEVICES = [
        'pulses',
        'urixyz',
    ]

    PARAMS = {
            'ctr_ch': {
                'type': str,
                'default': 'Dev1/ctr1',
            },   
            'x_initial': {
                'type': float,
                'units': 'um',
            },
            'y_initial': {
                'type': float,
                'units': 'um',
            },
            'z_initial': {
                'type': float,
                'units': 'um',
            },
            'do_z': {
                'type': bool,
                'default': True,
            },
            'sleep_time': {
                'type': float,
                'units': 's',
                'suffix': ' s',
                'default': 0.4
            },
            'xyz_step':{
                'type': float,
                'units': 'm',
                'default': 0.5e-7,
            },
            ## this value scales the search window along z, since it is less sensitive.
            ## this can be changed to a factor instead of percentage.
            'shrink_every_x_iter':{
                'type': int,
                'positive': True,
                'default': 1,
            },
            'starting_point': {
                'type': list,
                'items': list(['user_input','current_position (ignore input)']),
                'default': 'current_position (ignore input)',
            },
        }

    def main(self, ctr_ch, x_initial, y_initial, z_initial, do_z, sleep_time, xyz_step,\
            shrink_every_x_iter, starting_point):
        
        x_center = self.init_x
        y_center = self.init_y
        z_center = self.init_z
        dataXAfter=0;
        dataYAfter=0;
        dataZAfter=0;
        
        print('starting point:', x_center, y_center, z_center)
        xyz_step = xyz_step.to('um').m
        
        '''we define step size instead of a linspace'''
        counter = 0
        #import pdb; pdb.set_trace()
        while xyz_step >= 0.01:
            print('\n scanning z, x, y, with step size:', xyz_step)
            #print('search_x:', search_x, 'search_y:', search_y, 'search_z:', search_z)
            
            ######################################################################################
            #####  new version: iterate across z with current x and y. z travels furthest.  ######
            #####                               z scan                                      ######
            ######################################################################################
            ## in z, I add a hidden 20 nm to the step, becaue it has a different sensitivity
            ## than x and y, thanks to the rayleigh length.
            if do_z:
                for e in [1, -1]:
                    keepGoing = True
                    #print('\n before first read')
                    dataZBefore = self.read(sleep_time)
                    print('\n DataZBefore:', dataZBefore)
                    while(keepGoing):
                        self.urixyz.daq_controller.move({'x': Q_(x_center,'um'), 'y': Q_(y_center,'um'), 'z': Q_(z_center + e * (xyz_step + .02), 'um')})
                        #print('\n before next read')
                        dataZAfter = self.read(sleep_time)
                        print('\n DataZAfter:', dataZAfter)
                        if dataZAfter < dataZBefore:
                            keepGoing = False
                            self.urixyz.daq_controller.move({'x': Q_(x_center,'um'), 'y': Q_(y_center,'um'), 'z': Q_(z_center, 'um')})
                        else:
                            z_center = z_center + e * (xyz_step + .02)
                            dataZBefore = dataZAfter
                print('\n z scanned:', x_center, y_center, z_center)
                    
            #######################################################################################
            #####                                  x scan                                    ######
            #######################################################################################
            for e in [1, -1]:
                keepGoing = True
                #print('\n before first read')
                dataXBefore = self.read(sleep_time)
                print('\n DataXBefore:', dataXBefore)
                while(keepGoing):
                    self.urixyz.daq_controller.move({'x': Q_(x_center + e * xyz_step,'um'), 'y': Q_(y_center,'um'), 'z': Q_(z_center, 'um')})
                    #print('\n before next read')
                    dataXAfter = self.read(sleep_time)
                    print('\n DataXAfter:', dataXAfter)
                    if dataXAfter < dataXBefore:
                        keepGoing = False
                        self.urixyz.daq_controller.move({'x': Q_(x_center,'um'), 'y': Q_(y_center,'um'), 'z': Q_(z_center, 'um')})
                    else:
                        x_center = x_center + e * xyz_step
                        dataXBefore = dataXAfter
            print('\n x scanned:', x_center, y_center, z_center)
            #######################################################################################
            #####                                  y scan                                    ######
            #######################################################################################
            for e in [1, -1]:
                keepGoing = True
                dataYBefore = self.read(sleep_time)
                print('\n DataYBefore:', dataYBefore)
                while(keepGoing):
                    self.urixyz.daq_controller.move({'x': Q_(x_center,'um'), 'y': Q_(y_center + e * xyz_step,'um'), 'z': Q_(z_center, 'um')})
                    dataYAfter = self.read(sleep_time)
                    print('\n DataYAfter:', dataYAfter)
                    if dataYAfter < dataYBefore:
                        keepGoing = False
                        self.urixyz.daq_controller.move({'x': Q_(x_center,'um'), 'y': Q_(y_center,'um'), 'z': Q_(z_center, 'um')})
                    else:
                        y_center = y_center + e * xyz_step
                        dataYBefore = dataYAfter
            print('\n y scanned:', x_center, y_center, z_center)
            counter += 1
            if counter >= shrink_every_x_iter:
                counter = 0
                xyz_step = xyz_step / 2
            
        if do_z:
            self.acquire({
                    'x_center': x_center,
                    'y_center': y_center,
                    'z_center': z_center,
                    'dataXAfter': dataXAfter,
                    'dataYAfter': dataYAfter,
                    'dataZAfter': dataZAfter,
                })
        else:
            self.acquire({
                    'x_center': x_center,
                    'y_center': y_center,
                    'dataXAfter': dataXAfter,
                    'dataYAfter': dataYAfter, 
                    })
        print("final position:", self.urixyz.daq_controller.position)

    def read(self, deltaT):
        #import pdb; pdb.set_trace()
        #print(self.urixyz.daq_controller.counter_tasks[0])
        ctrs_start = rpyc.utils.classic.obtain(self.urixyz.daq_controller.counter_tasks[-1].read(1)[0])#()
        print(ctrs_start)
        time.sleep(deltaT.to('s').m)
        print('\n sleep finishes')
        ctrs_end = rpyc.utils.classic.obtain(self.urixyz.daq_controller.counter_tasks[-1].read(1)[0])#()
        print(ctrs_end)
        dctrs = ctrs_end - ctrs_start
        ctrs_rate = dctrs / deltaT.to('s').m
        # # ctrs_rate = self.urixyz.daq_controller.counter_tasks[-1].read()
        return ctrs_rate
        
        
    def initialize(self, ctr_ch, x_initial, y_initial, z_initial, do_z, sleep_time, xyz_step,\
            shrink_every_x_iter, starting_point):
        
        if starting_point == 'user_input':            
            self.urixyz.daq_controller.position = {'x': x_initial, 'y': y_initial, 'z': z_initial}
            
        self.init_x = self.urixyz.daq_controller.position['x'].to('um').m
        self.init_y = self.urixyz.daq_controller.position['y'].to('um').m
        self.init_z = self.urixyz.daq_controller.position['z'].to('um').m
        
        self.pulses.Pulser.constant(([7],0.0,0.0))   
        print('ctr ch:' + ctr_ch)
        # import pdb; pdb.set_trace()
        self.urixyz.new_ctr_task(ctr_ch)
        print('\n ctr_ch should be added')
        self.urixyz.daq_controller.counter_tasks[-1].start()
        
        #print(self.urixyz.daq_controller.counter_tasks)
        #self.urixyz.daq_controller.counter_tasks[-1].start()
        
        
        
        return

    def finalize(self, ctr_ch, x_initial, y_initial, z_initial, do_z, sleep_time, xyz_step,\
                shrink_every_x_iter, starting_point):
        self.urixyz.daq_controller.counter_tasks[-1].stop()
        return

    def gaussian(self,xs, a=1, x=0, width=1, b=0):
        return a * np.exp(-np.square((xs - x) / width)) + b
    def parabola(self,xs, ap=1, x0=0, bp=0):
        return ap * np.square(xs - x0) + bp
    def gaussparab(self,xs, a=1, x0g=0, x0p=0, width=1, b=0, ap=1, bp=0):
        return self.gaussian(xs,a,x0g,width,b) + self.parabola(xs,ap,x0p,bp)


    @PlotFormatInit(LinePlotWidget, ['x_scan', 'y_scan'])
    def init_format(p):
        p.xlabel = 'position (um)'
        p.ylabel = 'PL (cts/s)'

    # # # @Plot1D
    # # # def x_scan(df,cache):
        # # # latest_data = df.tail(1)
        # # # return {'x-scan':[list(latest_data.x_scan_range)[0], list(latest_data.x_data)[0]],
                # # # 'x_scan fit':[list(latest_data.x_scan_range)[0], list(latest_data.x_fitted)[0]]
        # # # }

    # # # @Plot1D
    # # # def y_scan(df,cache):
        # # # latest_data = df.tail(1)
        # # # return {'y-scan':[list(latest_data.y_scan_range)[0], list(latest_data.y_data)[0]],
                # # # 'y_scan fit':[list(latest_data.y_scan_range)[0], list(latest_data.y_fitted)[0]]
        # # # }

    # # # @Plot1D
    # # # def z_scan(df,cache):
        # # # latest_data = df.tail(1)
        # # # return {'z-scan':[list(latest_data.z_scan_range)[0], list(latest_data.z_data)[0]],
                # # # 'z_scan fit':[list(latest_data.z_scan_range)[0], list(latest_data.z_fitted)[0]]
        # # # }

    # # # @Plot1D
    # # # def drift(df,cache):
        # # # latest_data = df.tail(1)
        # # # # if do_z:
        # # # #     return {
        # # # #         'X': [list(latest_data.iteration_data)[0], list(latest_data.x_drift_data)[0]],
        # # # #         'Y': [list(latest_data.iteration_data)[0], list(latest_data.y_drift_data)[0]],
        # # # #         'Z': [list(latest_data.iteration_data)[0], list(latest_data.z_drift_data)[0]]
        # # # #     }
        # # # # else:
        # # # return {
            # # # 'X': [list(latest_data.iteration_data)[0], list(latest_data.x_drift_data)[0]],
            # # # 'Y': [list(latest_data.iteration_data)[0], list(latest_data.y_drift_data)[0]],
        # # # }