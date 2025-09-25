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

    def spatial_feedback(self, do_z, xyz_step,
            shrink_every_x_iter, starting_point, probe_time=0.04, initial_position={'x': 0, 'y': 0, 'z': 10}, n_points=10, counter_already_exists=False):
        self.n_points=n_points
        self.ns_clock_time = 10

        self.probe_time = probe_time
        self.ns_probe_time = int(round(self.probe_time * 1e9))
        with InstrumentManager() as mgr:
            
            self.initialize(mgr, initial_position, starting_point, counter_already_exists)
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
                        dataZBefore = self.read(mgr)
                        print('\n DataZBefore:', dataZBefore)
                        while(keepGoing):
                            mgr.DAQcontrol.move({'x': x_center, 'y': y_center, 'z': z_center + e * (xyz_step + .02)})
                            #print('\n before next read')
                            dataZAfter = self.read(mgr)
                            print('\n DataZAfter:', dataZAfter)
                            if dataZAfter < dataZBefore:
                                keepGoing = False
                                mgr.DAQcontrol.move({'x': x_center, 'y': y_center, 'z': z_center})
                            else:
                                z_center = z_center + e * (xyz_step + .02)
                                dataZBefore = dataZAfter
                            if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                                # the GUI has asked us nicely to exit
                                self.finalize(mgr, counter_already_exists)
                                return
                    print('\n z scanned:', x_center, y_center, z_center)
                        
                #######################################################################################
                #####                                  x scan                                    ######
                #######################################################################################
                for e in [1, -1]:
                    keepGoing = True
                    #print('\n before first read')
                    dataXBefore = self.read(mgr)
                    print('\n DataXBefore:', dataXBefore)
                    while(keepGoing):
                        mgr.DAQcontrol.move({'x': x_center + e * xyz_step, 'y': y_center, 'z': z_center})
                        #print('\n before next read')
                        dataXAfter = self.read(mgr)
                        print('\n DataXAfter:', dataXAfter)
                        if dataXAfter < dataXBefore:
                            keepGoing = False
                            mgr.DAQcontrol.move({'x': x_center, 'y': y_center, 'z': z_center})
                        else:
                            x_center = x_center + e * xyz_step
                            dataXBefore = dataXAfter
                        if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                            # the GUI has asked us nicely to exit
                            self.finalize(mgr, counter_already_exists)
                            return
                print('\n x scanned:', x_center, y_center, z_center)
                #######################################################################################
                #####                                  y scan                                    ######
                #######################################################################################
                for e in [1, -1]:
                    keepGoing = True
                    dataYBefore = self.read(mgr)
                    print('\n DataYBefore:', dataYBefore)
                    while(keepGoing):
                        # Move via XYZcontrol
                        mgr.DAQcontrol.move({'x': x_center, 'y': y_center + e * xyz_step, 'z': z_center})
                        dataYAfter = self.read(mgr)
                        print('\n DataYAfter:', dataYAfter)
                        if dataYAfter < dataYBefore:
                            keepGoing = False
                            # Move back via XYZcontrol
                            mgr.DAQcontrol.move({'x': x_center, 'y': y_center, 'z': z_center})
                        else:
                            y_center = y_center + e * xyz_step
                            dataYBefore = dataYAfter
                        if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                            # the GUI has asked us nicely to exit
                            self.finalize(mgr, counter_already_exists)
                            return
                print('\n y scanned:', x_center, y_center, z_center)
                counter += 1
                if counter >= shrink_every_x_iter:
                    counter = 0
                    xyz_step = xyz_step / 2
                if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                    # the GUI has asked us nicely to exit
                    self.finalize(mgr, counter_already_exists)
                    return
                
            
            print("final position:", mgr.DAQcontrol.get_position())
            self.finalize(mgr, counter_already_exists)


    def read(self, mgr):
        mgr.DAQcontrol.start_counter()
        time.sleep(0.01)
        mgr.Pulser.stream_sequence(self.pulse_sequence, 1)
        # mgr.DAQcontrol.read()
        data = mgr.DAQcontrol.read_to_data(self.probe_time)
        return data
        
        
    def initialize(self, mgr, initial_position, starting_point, counter_already_exists):
        
        if starting_point == 'user_input':            
            mgr.DAQcontrol.move(initial_position)
        current_position = mgr.DAQcontrol.get_position()
        self.init_x = current_position['x']
        self.init_y = current_position['y']
        self.init_z = current_position['z'] 
        # mgr.DAQcontrol.set_sampling_rate(2/self.probe_time) 
        # mgr.DAQcontrol.create_buffer(self.n_points+1) # +1 to account for signal being a difference of counts
        if not counter_already_exists:
            mgr.DAQcontrol.create_counter()
        mgr.DAQcontrol.prepare_counting(2/self.probe_time, self.n_points)
        self.pulse_sequence = self.create_sequence(mgr)
        # mgr.XYZcontrol.current_counter_task.start()
        return

    def finalize(self, mgr, counter_already_exists):
        if not counter_already_exists:
            mgr.DAQcontrol.finalize_counter()
        mgr.Pulser.set_state_off()
    
        return
    
    def create_sequence(self, mgr):
        seq = mgr.Pulser.create_sequence()
        clock_pulse = [(self.ns_clock_time,1),(self.ns_probe_time-self.ns_clock_time,0)] ##ensure clock_time in nanoseconds
        laser=[((self.n_points+1)*self.ns_probe_time,1)]
        clock = clock_pulse * (self.n_points+1)
        print("Clock sequence:", clock)
        seq.setDigital(mgr.Pulser.channel_dict['clock'], clock)
        seq.setDigital(mgr.Pulser.channel_dict['laser'], laser)
        return seq

    def gaussian(self,xs, a=1, x=0, width=1, b=0):
        return a * np.exp(-np.square((xs - x) / width)) + b
    def parabola(self,xs, ap=1, x0=0, bp=0):
        return ap * np.square(xs - x0) + bp
    def gaussparab(self,xs, a=1, x0g=0, x0p=0, width=1, b=0, ap=1, bp=0):
        return self.gaussian(xs,a,x0g,width,b) + self.parabola(xs,ap,x0p,bp)

