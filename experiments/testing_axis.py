#### BASIC IMPORTS
from nspyre import nspyre_init_logger
import logging
from pathlib import Path
from nspyre import DataSource, StreamingList # FOR SAVING
from nspyre import experiment_widget_process_queue # FOR LIVE GUI CONTROL
from nspyre import InstrumentManager # FOR OPERATING INSTRUMENTS
#### GENERAL IMPORTS
import time
import numpy as np
import rpyc.utils.classic
####

_HERE = Path(__file__).parent
_logger = logging.getLogger(__name__)



class TestingAxis:
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
        _logger.info('Created Experiment instance.')

    def __exit__(self):
        """Perform experiment teardown."""
        _logger.info('Destroyed Experiment instance.')

    def main(self, runs, starting_point, scan_distance, n_steps, time_per_point, points_per_step, dataset):
        params={
            'runs': runs,
            'starting_point': starting_point,
            'scan_distance': scan_distance,
            'n_steps': n_steps,
            'time_per_point': time_per_point,
            'points_per_step': points_per_step
        }
        self.ns_probe_time=int(time_per_point*1e9)
        print("ns_probe_time", self.ns_probe_time)
        time_per_point=self.ns_probe_time*1e-9
        print("time_per_point", time_per_point)
        self.n_points=points_per_step
        scan_distance=eval(scan_distance)
        
        with InstrumentManager() as mgr, DataSource(dataset) as ds:
            self.initial=rpyc.utils.classic.obtain(mgr.DAQcontrol.position)
            starting_point=[self.initial['x'], self.initial['y'], self.initial['z']]
            self.initialize(mgr, time_per_point)
            counting_seq=self.create_sequence(mgr)
            axis=['x', 'y', 'z']
            x_line_scan=StreamingList()
            y_line_scan=StreamingList() 
            z_line_scan=StreamingList()
            x_counting=StreamingList()
            y_counting=StreamingList()
            z_counting=StreamingList()
            x_position=starting_point[0]+np.linspace(-scan_distance[0]/2, scan_distance[0]/2, n_steps)
            y_position=starting_point[1]+np.linspace(-scan_distance[1]/2, scan_distance[1]/2, n_steps)
            z_position=starting_point[2]+np.linspace(-scan_distance[2]/2, scan_distance[2]/2, n_steps)

            for run in range(runs):
                # X-axis line scan
                mgr.DAQcontrol.create_counter()
                mgr.DAQcontrol.acq_rate=1/time_per_point
                line_data=mgr.DAQcontrol.line_scan({'x': starting_point[0]-scan_distance[0]/2,
                                                   'y': starting_point[1],
                                                   'z': starting_point[2]},
                                                   {'x': starting_point[0]+scan_distance[0]/2,
                                                    'y': starting_point[1],
                                                    'z': starting_point[2]},
                                                    n_steps, points_per_step)
                line_data=rpyc.utils.classic.obtain(line_data)
                mgr.DAQcontrol.finalize_counter()
                x_line_scan.append(np.stack([x_position, line_data]))
                x_line_scan.updated_item(-1)
                
                # Y-axis line scan
                mgr.DAQcontrol.create_counter()
                mgr.DAQcontrol.acq_rate=1/time_per_point
                line_data=mgr.DAQcontrol.line_scan({'x': starting_point[0],
                                                   'y': starting_point[1]-scan_distance[1]/2,
                                                   'z': starting_point[2]},
                                                   {'x': starting_point[0],
                                                    'y': starting_point[1]+scan_distance[1]/2,
                                                    'z': starting_point[2]},
                                                    n_steps, points_per_step)
                
                line_data=rpyc.utils.classic.obtain(line_data)
                mgr.DAQcontrol.finalize_counter()
                y_line_scan.append(np.stack([y_position, line_data]))
                y_line_scan.updated_item(-1)

                # Z-axis line scan
                mgr.DAQcontrol.create_counter()
                mgr.DAQcontrol.acq_rate=1/time_per_point
                line_data=mgr.DAQcontrol.line_scan({'x': starting_point[0],
                                                   'y': starting_point[1],
                                                   'z': starting_point[2]-scan_distance[2]/2},
                                                   {'x': starting_point[0],
                                                    'y': starting_point[1],
                                                    'z': starting_point[2]+scan_distance[2]/2},
                                                    n_steps, points_per_step)
                
                line_data=rpyc.utils.classic.obtain(line_data)
                mgr.DAQcontrol.finalize_counter()
                z_line_scan.append(np.stack([z_position, line_data]))
                z_line_scan.updated_item(-1)
                
                # Y-axis counting
                
                y_data=np.empty(len(y_position))
                for i, y_pos in enumerate(y_position):
                    mgr.DAQcontrol.move({'x': starting_point[0], 'y': y_pos, 'z': starting_point[2]})
                    mgr.DAQcontrol.create_counter()
                    mgr.DAQcontrol.prepare_counting(2/time_per_point, points_per_step)
                    mgr.DAQcontrol.start_counter()
                    time.sleep(0.01)
                    mgr.Pulser.stream_sequence(counting_seq, 1)
                    data=mgr.DAQcontrol.read_to_data(timeout=20.0)
                    mgr.DAQcontrol.finalize_counter()
                    y_data[i]=data
                y_counting.append(np.stack([y_position, y_data]))
                y_counting.updated_item(-1)
                
                
                # X-axis counting
                
                print('buffer', mgr.DAQcontrol.ctr_buffer)
                x_data=np.empty(len(x_position))
                for i, x_pos in enumerate(x_position):
                    mgr.DAQcontrol.move({'x': x_pos, 'y': starting_point[1], 'z': starting_point[2]})
                    mgr.DAQcontrol.create_counter()
                    mgr.DAQcontrol.prepare_counting(2/time_per_point, points_per_step)
                    mgr.DAQcontrol.start_counter()
                    time.sleep(0.01)
                    mgr.Pulser.stream_sequence(counting_seq, 1)
                    data=mgr.DAQcontrol.read_to_data(timeout=20.0)
                    mgr.DAQcontrol.finalize_counter()
                    x_data[i]=data
                x_counting.append(np.stack([x_position, x_data]))
                x_counting.updated_item(-1)
                
                
                
                
                # Z-axis counting
                
                z_data=np.empty(len(z_position))
                for i, z_pos in enumerate(z_position):
                    mgr.DAQcontrol.move({'x': starting_point[0], 'y': starting_point[1], 'z': z_pos})
                    mgr.DAQcontrol.create_counter()
                    mgr.DAQcontrol.prepare_counting(2/time_per_point, points_per_step)
                    mgr.DAQcontrol.start_counter()
                    time.sleep(0.01)
                    mgr.Pulser.stream_sequence(counting_seq, 1)
                    data=mgr.DAQcontrol.read_to_data(timeout=20.0)
                    mgr.DAQcontrol.finalize_counter()
                    z_data[i]=data
                z_counting.append(np.stack([z_position, z_data]))
                z_counting.updated_item(-1)
                
                ds.push({'params': params,
                         'datasets': 
                         {'x_line_scan': x_line_scan,
                          'x_counting': x_counting,
                          'y_line_scan': y_line_scan,
                          'y_counting': y_counting,
                          'z_line_scan': z_line_scan,
                          'z_counting': z_counting,}})
                    
            
                if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                    return self.finalize(mgr)
            return self.finalize(mgr)
        
    def initialize(self, mgr, time_per_point):
        mgr.Pulser.set_state([7],0.0,0.0)
        mgr.DAQcontrol.create_counter()
        mgr.DAQcontrol.acq_rate=1/time_per_point
        return
    
    def create_sequence(self, mgr):
        self.ns_clock_time=10
        seq = mgr.Pulser.create_sequence()
        clock_pulse = [(self.ns_clock_time,1),(self.ns_probe_time-self.ns_clock_time,0)] ##ensure clock_time in nanoseconds
        laser=[((self.n_points+1)*self.ns_probe_time,1)]
        clock = clock_pulse * (self.n_points+1)
        print("Clock sequence:", clock)
        seq.setDigital(mgr.Pulser.channel_dict['clock'], clock)
        seq.setDigital(mgr.Pulser.channel_dict['laser'], laser)
        return seq
    
    def finalize(self,mgr):
        mgr.Pulser.set_state_off()
        mgr.DAQcontrol.finalize_counter()
        mgr.DAQcontrol.move(self.initial)
        return