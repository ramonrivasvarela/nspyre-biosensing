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
from math import ceil
from nspyre import InstrumentManager
from pathlib import Path
from nspyre import nspyre_init_logger
from nspyre import experiment_widget_process_queue


# nidaqmx
import nidaqmx
from nidaqmx.constants import (AcquisitionType, CountDirection, Edge,
    READ_ALL_AVAILABLE, TaskMode, TriggerType)
from nidaqmx.stream_readers import CounterReader


# nspyre


#from lantz.drivers.ni.ni_motion_controller import NIDAQMotionController

_HERE = Path(__file__).parent
_logger = logging.getLogger(__name__)

#Jacob's advice
import rpyc

class SpatialFeedback():
    def __init__(self, queue_to_exp=None, queue_from_exp=None):
        """
        Args:
            queue_to_exp: A multiprocessing Queue object used to send messages
                to the experiment from the GUI.
            queue_from_exp: A multiprocessing Queue object used to send messages
                to the GUI from the experiment.
        """
        self.queue_to_exp = queue_to_exp
        self.queue_from_exp = queue_from_exp
    def __enter__(self):
        """Perform experiment setup."""
        # config logging messages
        # if running a method from the GUI, it will be run in a new process
        # this logging call is necessary in order to separate log messages
        # originating in the GUI from those in the new experiment subprocess
        nspyre_init_logger(
            log_level=logging.INFO,
            log_path=_HERE / '../logs',
            log_path_level=logging.DEBUG,
            prefix=Path(__file__).stem,
            file_size=10_000_000,
        )
        _logger.info('Created PlaneScan instance.')

    def __exit__(self):
        """Perform experiment teardown."""
        _logger.info('Destroyed PlaneScan instance.')

    def spatial_feedback(self, ctr_ch, initial_position, do_z, sleep_time, xyz_step,
            shrink_every_x_iter, starting_point):
        with InstrumentManager() as mgr:
            self.initialize(mgr, ctr_ch, initial_position, starting_point)
            x_center = self.init_x
            y_center = self.init_y
            z_center = self.init_z
            dataXAfter=0
            dataYAfter=0
            dataZAfter=0
            
            print('starting point:', x_center, y_center, z_center)
            xyz_step = xyz_step
            
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
                        dataZBefore = self.read(mgr, sleep_time)
                        print('\n DataZBefore:', dataZBefore)
                        while(keepGoing):
                            mgr.XYZcontrol.move_to(x_center, y_center, z_center + e * (xyz_step + .02))
                            #print('\n before next read')
                            dataZAfter = self.read(mgr, sleep_time)
                            print('\n DataZAfter:', dataZAfter)
                            if dataZAfter < dataZBefore:
                                keepGoing = False
                                mgr.XYZcontrol.move_to(x_center, y_center, z_center)
                            else:
                                z_center = z_center + e * (xyz_step + .02)
                                dataZBefore = dataZAfter
                            if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                                # the GUI has asked us nicely to exit
                                self.finalize(mgr)
                                return
                    print('\n z scanned:', x_center, y_center, z_center)
                        
                #######################################################################################
                #####                                  x scan                                    ######
                #######################################################################################
                for e in [1, -1]:
                    keepGoing = True
                    #print('\n before first read')
                    dataXBefore = self.read(mgr, sleep_time)
                    print('\n DataXBefore:', dataXBefore)
                    while(keepGoing):
                        mgr.XYZcontrol.move_to(x_center + e * xyz_step, y_center, z_center)
                        #print('\n before next read')
                        dataXAfter = self.read(mgr, sleep_time)
                        print('\n DataXAfter:', dataXAfter)
                        if dataXAfter < dataXBefore:
                            keepGoing = False
                            mgr.XYZcontrol.move_to(x_center, y_center, z_center)
                        else:
                            x_center = x_center + e * xyz_step
                            dataXBefore = dataXAfter
                        if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                            # the GUI has asked us nicely to exit
                            self.finalize(mgr)
                            return
                print('\n x scanned:', x_center, y_center, z_center)
                #######################################################################################
                #####                                  y scan                                    ######
                #######################################################################################
                for e in [1, -1]:
                    keepGoing = True
                    dataYBefore = self.read(mgr, sleep_time)
                    print('\n DataYBefore:', dataYBefore)
                    while(keepGoing):
                        # Move via XYZcontrol
                        mgr.XYZcontrol.move_to(x_center, y_center + e * xyz_step, z_center)
                        dataYAfter = self.read(mgr, sleep_time)
                        print('\n DataYAfter:', dataYAfter)
                        if dataYAfter < dataYBefore:
                            keepGoing = False
                            # Move back via XYZcontrol
                            mgr.XYZcontrol.move_to(x_center, y_center, z_center)
                        else:
                            y_center = y_center + e * xyz_step
                            dataYBefore = dataYAfter
                        if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                            # the GUI has asked us nicely to exit
                            self.finalize(mgr)
                            return
                print('\n y scanned:', x_center, y_center, z_center)
                counter += 1
                if counter >= shrink_every_x_iter:
                    counter = 0
                    xyz_step = xyz_step / 2
                if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                    # the GUI has asked us nicely to exit
                    self.finalize(mgr)
                    return
                
            
            print("final position:", mgr.XYZcontrol.position)
            self.finalize(mgr)


    def read(self, mgr, deltaT):
        #import pdb; pdb.set_trace()
        #print(self.urixyz.daq_controller.counter_tasks[0])
        ctrs_start = rpyc.utils.classic.obtain(mgr.XYZcontrol.current_counter_task.read(1)[0])#()
        print(ctrs_start)
        time.sleep(deltaT)
        print('\n sleep finishes')
        ctrs_end = rpyc.utils.classic.obtain(mgr.XYZcontrol.current_counter_task.read(1)[0])#()
        print(ctrs_end)
        dctrs = ctrs_end - ctrs_start
        ctrs_rate = dctrs / deltaT
        # print("dctrs", dctrs)
        # print("deltaT", deltaT)
        # # ctrs_rate = self.urixyz.daq_controller.counter_tasks[-1].read()
        return ctrs_rate
        
        
    def initialize(self, mgr, ctr_ch, initial_position, starting_point):
        
        if starting_point == 'user_input':            
            mgr.XYZcontrol.move(initial_position)
        self.init_x = mgr.XYZcontrol.get_x()
        self.init_y = mgr.XYZcontrol.get_y()
        self.init_z = mgr.XYZcontrol.get_z()
        mgr.Pulser.set_state([7],0.0,0.0)   
        print('ctr ch:' + ctr_ch)
        mgr.XYZcontrol.new_ctr_task(ctr_ch)
        mgr.XYZcontrol.current_counter_task.start()
        print('\n ctr_ch should be added')
        return

    def finalize(self, mgr):
        mgr.XYZcontrol.end_ctr_task()
        mgr.Pulser.set_state_off()
    
        return

    def gaussian(self,xs, a=1, x=0, width=1, b=0):
        return a * np.exp(-np.square((xs - x) / width)) + b
    def parabola(self,xs, ap=1, x0=0, bp=0):
        return ap * np.square(xs - x0) + bp
    def gaussparab(self,xs, a=1, x0g=0, x0p=0, width=1, b=0, ap=1, bp=0):
        return self.gaussian(xs,a,x0g,width,b) + self.parabola(xs,ap,x0p,bp)

