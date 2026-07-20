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
from nspyre import InstrumentManager, StreamingList, DataSource
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
        _logger.info('Created SpatialFeedback instance.')
    def __exit__(self):
        """Perform experiment teardown."""
        _logger.info('Destroyed SpatialFeedback instance.')

        
    ## MAIN EXPERIMENT METHOD ##########################################################
    def spatial_feedback(self, do_z=True, xyz_step=0.05, shrink_every_x_iter=1, 
                         starting_point='default', probe_time=0.40, initial_position="(0,0,50)", 
                         n_points=1, counter_already_exists=False, total_fb_time=0.0, dataset='feedback'):
        ## PREPARE PARAMS DICT
        params={'do_z':do_z,
                    'xyz_step':xyz_step,
                    'shrink_every_x_iter': shrink_every_x_iter,
                    'starting_point': starting_point,
                    'probe_time':probe_time,
                    'initial_position': initial_position,
                    'n_points': n_points,
                    'counter_already_exists' : counter_already_exists,
                    'total_fb_time': total_fb_time
                    }
        self.verbose = True # add as param
        
        with InstrumentManager() as mgr, DataSource(dataset) as ds:
            ## INITIALIZE | self.
            self.initialize(mgr, initial_position, starting_point, counter_already_exists, n_points, probe_time)
            ## Prepare tracking variables
            center = mgr.DAQcontrol.get_position()
            print('starting point:', center['x'], center['y'], center['z'])
            
            counter = 0
            #import pdb; pdb.set_trace()
            time_initial=time.time()
            X_pos=StreamingList()
            Y_pos=StreamingList()
            Z_pos=StreamingList()
            fluorescence=StreamingList()

            while xyz_step >= 0.01 or total_fb_time != 0.0:
                if self.verbose: print('\n scanning z, x, y, with step size:', xyz_step)
                #print('search_x:', search_x, 'search_y:', search_y, 'search_z:', search_z)
                
                ######################################################################################
                #####  new version: iterate across z with current x and y. z travels furthest.  ######
                #####                               z scan                                      ######
                ######################################################################################
                ## in z, I add a hidden 20 nm to the step, becaue it has a different sensitivity
                ## than x and y, thanks to the rayleigh length.
                if do_z:
                    self.track_1D(mgr, 'z', center, probe_time * n_points, xyz_step, X_pos, Y_pos, Z_pos, fluorescence, time_initial, params, ds, total_fb_time, counter_already_exists)
                    if self.verbose: print('\n z scanned:', center['x'], center['y'], center['z'])
                #######################################################################################
                #####                                  x scan                                    ######
                #######################################################################################
                self.track_1D(mgr, 'x', center, probe_time * n_points, xyz_step, X_pos, Y_pos, Z_pos, fluorescence, time_initial, params, ds, total_fb_time, counter_already_exists)
                if self.verbose: print('\n x scanned:', center['x'], center['y'], center['z'])
                #######################################################################################
                #####                                  y scan                                    ######
                #######################################################################################
                self.track_1D(mgr, 'y', center, probe_time * n_points, xyz_step, X_pos, Y_pos, Z_pos, fluorescence, time_initial, params, ds, total_fb_time, counter_already_exists)
                if self.verbose: print('\n y scanned:', center['x'], center['y'], center['z'])
                counter += 1
                if counter % shrink_every_x_iter == 0:
                    xyz_step = xyz_step / 2
                if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                    # the GUI has asked us nicely to exit
                    self.finalize(mgr, counter_already_exists)
                    return
                
            
            print("final position:", mgr.DAQcontrol.get_position())
            self.finalize(mgr, counter_already_exists)

    def track_1D(self, mgr, var, center, integration_time, xyz_step, X_pos, Y_pos, Z_pos, fluorescence, time_initial, params, ds, total_fb_time, counter_already_exists, integrated = False):
        '''
        in 1D along var {'x', 'y', 'z'}, move in positive and negative directions until the 
        signal decreases, then return to the maximum position.

        for integrated scheme, returns quit_fb, quit_exp. This determines whether to quit current fb, quit experiment, or continue
        '''
        for e in [1, -1]:
            dataBefore = self.read(mgr, self.pulse_sequence, integration_time)
            if self.verbose: print(f'\n Data {var} Before:', dataBefore)
            keepGoing = True
            while keepGoing:
                next_x = center['x'] + e * xyz_step if var == 'x' else center['x']
                next_y = center['y'] + e * xyz_step if var == 'y' else center['y']
                next_z = center['z'] + e * (xyz_step + 0.02) if var == 'z' else center['z'] # add 20 nm to z step because of different sensitivity
                mgr.DAQcontrol.move({'x': next_x, 'y': next_y, 'z': next_z})
                dataAfter = self.read(mgr, self.pulse_sequence, integration_time)
                time_current = time.time() - time_initial
                if self.verbose: print(f'\n Data {var} After:', dataAfter)
                if dataAfter < dataBefore:
                    keepGoing = False
                    mgr.DAQcontrol.move({'x': center['x'], 'y': center['y'], 'z': center['z']})
                else:
                    center[var] = next_x if var == 'x' else next_y if var == 'y' else next_z
                    dataBefore = dataAfter
                self.data_update(X_pos, Y_pos, Z_pos, fluorescence, time_current, center, dataAfter, params, ds)
                if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                    # the GUI has asked us nicely to exit
                    if not integrated: self.finalize(mgr, counter_already_exists)
                    return True, True # used in integrated mode 
                elif (total_fb_time > 0 and time.time() - time_initial >= total_fb_time):
                    if not integrated: self.finalize(mgr, counter_already_exists) # a note on inheritance: if this is called from within another spyrelet, this will use the spyrelet's finalize method. 
                    return True, False # used in integrated mode 
        return False, False # used in integrated mode 
                
    def data_update(self, X_pos, Y_pos, Z_pos, fluorescence, time_current, center, dataAfter, params, ds):
        X_pos.append(np.array([np.array([time_current]), np.array([center['x']])]))
        Y_pos.append(np.array([np.array([time_current]), np.array([center['y']])]))
        Z_pos.append(np.array([np.array([time_current]), np.array([center['z']])]))
        fluorescence.append(np.array([np.array([time_current]), np.array([dataAfter])]))
        X_pos.updated_item(-1)
        Y_pos.updated_item(-1)
        Z_pos.updated_item(-1)
        fluorescence.updated_item(-1)
        ds.push({
            'params': params,
            'title': 'Spatial Feedback Tracking',
            'xlabel': 'Time (s)',
            'datasets': {'x_pos': X_pos,
                         'y_pos': Y_pos,
                         'z_pos': Z_pos,
                         'total_fluor': fluorescence,
                        }})

    def read(self, mgr, seq, integration_time = 1):
        mgr.DAQcontrol.start_counter()
        time.sleep(0.01)
        mgr.Pulser.stream_sequence(seq, 1)
        # mgr.DAQcontrol.read()
        data = mgr.DAQcontrol.read_to_data()/integration_time
        return data
    

    ## INITIALIZATION ##########################################################################
    def initialize(self, mgr, initial_position, starting_point, counter_already_exists, n_points, probe_time):
        ## initialize timing and routines
        ns_clock_time = 10
        self.ns_laser_lag = 80 #laser lag hard coded to 80ns
        ns_probe_time = int(round(probe_time * 1e9))
        ## init DAQ
        if not counter_already_exists:
            mgr.DAQcontrol.create_counter()
        mgr.DAQcontrol.prepare_counting(sampling_rate = 2/probe_time, n_points=n_points)
        ## init xyz
        if starting_point == 'user_input':
            initial_position = eval(initial_position)            
            mgr.DAQcontrol.move({'x': initial_position[0], 'y': initial_position[1], 'z': initial_position[2]})
        ## init seq
        self.pulse_sequence = mgr.Pulser.count_confocal(ns_probe_time, ns_clock_time, self.ns_laser_lag, n_points)
        return
    ## FINALIZATION ##########################################################################
    def finalize(self, mgr, counter_already_exists):
        if not counter_already_exists:
            mgr.DAQcontrol.finalize_counter()
        mgr.Pulser.set_state_off()
    
        return
    
    # def create_sequence(self, mgr):
    #     seq = mgr.Pulser.create_sequence()
    #     clock_pulse = [(self.ns_clock_time,1),(self.ns_probe_time-self.ns_clock_time,0)] ##ensure clock_time in nanoseconds
    #     laser=[((self.n_points+1)*self.ns_probe_time,1)]
    #     clock = clock_pulse * (self.n_points+1)
    #     print("Clock sequence:", clock)
    #     seq.setDigital(mgr.Pulser.channel_dict['clock'], clock)
    #     seq.setDigital(mgr.Pulser.channel_dict['laser'], laser)
    #     return seq


    #### Running spatial feedback within another Spyrelet:
    def spatial_feedback_integrated(self, 
                        X_pos, Y_pos, Z_pos, fluorescence, mgr, ds, # Note that dataset is an arg, pass in a DataSource.
                        do_z=True, xyz_step=0.05, shrink_every_x_iter=1, 
                         starting_point='default', probe_time=0.40, initial_position="(0,0,50)", 
                         n_points=1, counter_already_exists=False, total_fb_time=0.0, dataset = 'feedback'):
        '''
        Runs a spatial fb, but does not initialize or finalize, and appends to a previously made dataset.
        '''
        
        ## PREPARE PARAMS DICT
        params={'do_z':do_z,
                    'xyz_step':xyz_step,
                    'shrink_every_x_iter': shrink_every_x_iter,
                    'starting_point': starting_point,
                    'probe_time':probe_time,
                    'initial_position': initial_position,
                    'n_points': n_points,
                    'counter_already_exists' : counter_already_exists,
                    'total_fb_time': total_fb_time
                    }
        
        ## Prepare tracking variables
        center = mgr.DAQcontrol.get_position()
        print('starting point:', center['x'], center['y'], center['z'])
        
        counter = 0
        #import pdb; pdb.set_trace()
        time_initial=time.time()

        ## These should be passed in
        # X_pos=StreamingList()
        # Y_pos=StreamingList()
        # Z_pos=StreamingList()
        # fluorescence=StreamingList()

        
        while xyz_step >= 0.01 or total_fb_time != 0.0:
            if self.verbose: print('\n scanning z, x, y, with step size:', xyz_step)
            #print('search_x:', search_x, 'search_y:', search_y, 'search_z:', search_z)
            
            ######################################################################################
            #####  new version: iterate across z with current x and y. z travels furthest.  ######
            #####                               z scan                                      ######
            ######################################################################################
            ## in z, I add a hidden 20 nm to the step, becaue it has a different sensitivity
            ## than x and y, thanks to the rayleigh length.
            if do_z:
                quit_fb, quit_exp = self.track_1D(mgr, 'z', center, probe_time * n_points, xyz_step, X_pos, Y_pos, Z_pos, fluorescence, time_initial, params, ds, total_fb_time, counter_already_exists, integrated = True)
                if self.verbose: print('\n z scanned:', center['x'], center['y'], center['z'])
                if quit_fb or quit_exp: return quit_exp
            #######################################################################################
            #####                                  x scan                                    ######
            #######################################################################################
            quit_fb, quit_exp = self.track_1D(mgr, 'x', center, probe_time * n_points, xyz_step, X_pos, Y_pos, Z_pos, fluorescence, time_initial, params, ds, total_fb_time, counter_already_exists, integrated = True)
            if self.verbose: print('\n x scanned:', center['x'], center['y'], center['z'])
            if quit_fb or quit_exp: return quit_exp
            #######################################################################################
            #####                                  y scan                                    ######
            #######################################################################################
            quit_fb, quit_exp = self.track_1D(mgr, 'y', center, probe_time * n_points, xyz_step, X_pos, Y_pos, Z_pos, fluorescence, time_initial, params, ds, total_fb_time, counter_already_exists, integrated = True)
            if self.verbose: print('\n y scanned:', center['x'], center['y'], center['z'])
            if quit_fb or quit_exp: return quit_exp
            counter += 1
            if counter % shrink_every_x_iter == 0:
                xyz_step = xyz_step / 2
            if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                # the GUI has asked us nicely to exit
                self.finalize(mgr)
                return True # quit_exp
                
            return False

