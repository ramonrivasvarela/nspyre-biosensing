# std
import numpy as np
import time
import logging
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

# Other Spyrelets to Use
from experiments.spatialfb import SpatialFeedback

_HERE = Path(__file__).parent
_logger = logging.getLogger(__name__)

class MultiBlast(SpatialFeedback):
    """
    A class for moving to several locations and blasting using a controlled power (%) for a specified
    duration (s). The locations are specified in a list of tuples, where each tuple contains the x, and y
    coordinates of the location to blast. 
    """
    ## STANDARD DEFINITIONS #############################################################

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

    def multi_blast(self, locations, blast_power, duration, feedback, do_z, xyz_step, shrink_every_x_iter, 
                   probe_time, n_points,  total_fb_time, dataset):
        """
        Move to several locations and blast using a controlled power (%) for a specified duration (s).
        The locations are specified in a list of tuples, where each tuple contains the x, and y
        coordinates of the location to blast. 

        Args:
            locations: A list of tuples containing the x and y coordinates of the locations to blast.
              If None, blasts at the current location.
            power: The power (%) to use for blasting.
            duration: The duration (s) to blast at each location.
            feedback: Whether to use feedback during blasting.
            feedback_cap: The maximum number of feedback iterations to perform.
            do_z: Whether to perform z feedback during blasting.
            xyz_step: The step size (um) for xyz feedback.
            shrink_every_x_iter: How often to shrink the step size during feedback.
            starting_point: The starting point for feedback ('default' or 'current').
            probe_time: The time (s) to probe at each location before blasting.
            initial_position: The initial position (x,y,z) to move to before starting the experiment.
            n_points: The number of points to blast at each location.
            total_fb_time: The total time (s) to perform feedback before blasting (default 0.0).
        """
        params={'locations': locations,
                    'blast_power': blast_power,
                    'duration': duration,
                    'feedback': feedback,
                    'do_z':do_z,
                    'xyz_step':xyz_step,
                    'shrink_every_x_iter': shrink_every_x_iter,
                    'probe_time':probe_time,
                    'n_points': n_points,
                    'total_fb_time': total_fb_time
                    }
        
        X_pos=StreamingList()
        Y_pos=StreamingList()
        Z_pos=StreamingList()
        fluorescence=StreamingList()
        

        with InstrumentManager() as mgr, DataSource(dataset) as ds:
            base_power = mgr.DLnsec.get_power()
            _logger.info(f"Base power: {base_power}%")
            cur_loc = mgr.XYZcontrol.get_position()
            if locations is None or len(locations) == 0:
                locations = [(cur_loc['x'], cur_loc['y'])]
            loc_0 = {'x': locations[0][0], 'y': locations[0][1], 'z': cur_loc['z']}
            self.initialize(mgr, initial_position=loc_0, starting_point=loc_0, n_points=n_points, probe_time=probe_time, duration=duration)
            for i,loc in enumerate(locations):
                x, y = loc
                mgr.XYZcontrol.move({'x': x, 'y': y, 'z': mgr.XYZcontrol.get_position()['z']})
                if feedback:
                    _logger.info(f"Performing feedback at location ({x}, {y})...")
                self.spatial_feedback(mgr, params, ds, X_pos, Y_pos, Z_pos, fluorescence, do_z=do_z, xyz_step=xyz_step, shrink_every_x_iter=shrink_every_x_iter, probe_time=probe_time, n_points=n_points, total_fb_time=total_fb_time)
                self.data_update(X_pos, Y_pos, Z_pos, fluorescence, 0, mgr.XYZcontrol.get_position(), 0, params, ds) # Add (0,0) to create a break for processing
                _logger.info(f"Blasting at location ({x}, {y}) with power {blast_power}% for {duration}s...")
                mgr.DLnsec.set_power(blast_power)
                mgr.Pulser.stream(self.blast_seq)
                mgr.DLnsec.set_power(base_power) 
            self.finalize(mgr)

    def spatial_feedback(self,mgr, params, ds, X_pos, Y_pos, Z_pos, fluorescence, do_z=True, xyz_step=0.05, shrink_every_x_iter=1, starting_point='default', probe_time=0.4, initial_position="(0,0,50)", n_points=1, counter_already_exists=False, total_fb_time=0):
        '''
        spatial_feedback, changed to skip initialization, and to allow for datasets to combine
        '''
        center = self.init_position.copy()
        # print('starting point:', center['x'], center['y'], center['z'])
        
        counter = 0
        #import pdb; pdb.set_trace()
        time_initial=time.time()

        while xyz_step >= 0.01 or total_fb_time != 0.0:
            ## Z
            if do_z:
                self.track_1D(mgr, 'z', center, probe_time * n_points, xyz_step,
                               X_pos, Y_pos, Z_pos, fluorescence, time_initial,
                                 params, ds, total_fb_time, counter_already_exists)
            ## X
            self.track_1D(mgr, 'x', center, probe_time * n_points, xyz_step,
                           X_pos, Y_pos, Z_pos, fluorescence, time_initial,
                             params, ds, total_fb_time, counter_already_exists)
            ## Y
            self.track_1D(mgr, 'y', center, probe_time * n_points, xyz_step,
                           X_pos, Y_pos, Z_pos, fluorescence, time_initial,
                             params, ds, total_fb_time, counter_already_exists)
            # print('\n y scanned:', center['x'], center['y'], center['z'])
            counter += 1
            if counter % shrink_every_x_iter == 0:
                xyz_step = xyz_step / 2
            if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                # the GUI has asked us nicely to exit
                self.finalize(mgr)
                return

    
    def track_1D(self, mgr, var, center, integration_time, xyz_step, X_pos, Y_pos, Z_pos, fluorescence, time_initial, params, ds, total_fb_time, counter_already_exists):
        '''
        in 1D along var {'x', 'y', 'z'}, move in positive and negative directions until the 
        signal decreases, then return to the maximum position.

        Changed to redefine exit sequence.
        '''
        full_break = False
        if not (total_fb_time > 0 and time.time() - time_initial >= total_fb_time):
            for e in [1, -1]:
                dataBefore = self.read(mgr, integration_time)
                print(f'\n Data {var} Before:', dataBefore)
                keepGoing = True
                while keepGoing:
                    next_x = center['x'] + e * xyz_step if var == 'x' else center['x']
                    next_y = center['y'] + e * xyz_step if var == 'y' else center['y']
                    next_z = center['z'] + e * (xyz_step + 0.02) if var == 'z' else center['z'] # add 20 nm to z step because of different sensitivity
                    mgr.DAQcontrol.move({'x': next_x, 'y': next_y, 'z': next_z})
                    dataAfter = self.read(mgr, integration_time)
                    time_current = time.time() - time_initial
                    print(f'\n Data {var} After:', dataAfter)
                    if dataAfter < dataBefore:
                        keepGoing = False
                        mgr.DAQcontrol.move({'x': center['x'], 'y': center['y'], 'z': center['z']})
                    else:
                        center[var] = next_x if var == 'x' else next_y if var == 'y' else next_z
                        dataBefore = dataAfter
                    self.data_update(X_pos, Y_pos, Z_pos, fluorescence, time_current, center, dataAfter, params, ds)
                    if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                                # the GUI has asked us nicely to exit
                                self.finalize(mgr, counter_already_exists)
                                return
                    elif (total_fb_time > 0 and time.time() - time_initial >= total_fb_time):
                        full_break = True
                        break
                if full_break:
                    break


    ## INITIALIZATION AND FINALIZATION
    def initialize(self,  mgr, initial_position, starting_point, n_points, probe_time, duration):
        #Define self.init_position, self.pulse_sequence
        super.initialize(mgr, initial_position, starting_point, False, n_points, probe_time)
        self.blast_seq = mgr.Pulser.laser_blast(duration*1e9)  # Convert duration from seconds to nanoseconds

    def finalize(self, mgr):
        super.finalize(mgr, False)

    

    

