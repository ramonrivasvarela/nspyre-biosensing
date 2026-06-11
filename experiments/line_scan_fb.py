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
from scipy import optimize

_HERE = Path(__file__).parent
_logger = logging.getLogger(__name__)



class LineScanFB:
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

    def main(self, runs, scan_distance, n_steps, time_per_point, points_per_step, spot_size, convergence_threshold, dataset):
        params={
            'runs': runs,
            'scan_distance': scan_distance,
            'n_steps': n_steps,
            'time_per_point': time_per_point,
            'points_per_step': points_per_step,
            'spot_size': spot_size,
            'convergence_threshold': convergence_threshold,
        }
        self.ns_probe_time=int(time_per_point*1e9)
        print("ns_probe_time", self.ns_probe_time)
        time_per_point=self.ns_probe_time*1e-9
        print("time_per_point", time_per_point)
        self.n_points=points_per_step
        scan_distance=eval(scan_distance)
        self.convergence_threshold=convergence_threshold
        self.spot_size=spot_size
        
        
        with InstrumentManager() as mgr, DataSource(dataset) as ds:
            # might need rpyc.utils.classic.obtain for some of these, if they are not automatically retrieved as proxy objects
            self.initial=mgr.DAQcontrol.position
            self.XYZ_center=[self.initial[index] for index in ['x', 'y', 'z']]
            self.drift=[0, 0, 0]
            self.initialize(mgr, time_per_point)
            axis=['x', 'y', 'z']
            positions=[StreamingList(), StreamingList(), StreamingList()]
            fluorescence = StreamingList()
            mgr.DAQcontrol.create_counter()
            mgr.DAQcontrol.acq_rate=1/time_per_point
            self.found=[False, False, False]
            time_initial = time.time()

            

            for _ in range(runs):
                if all(self.found):
                    print('Axis scan complete')
                    break

                for index in range(3):
                    positions, line_data = self.scan_axis(
                        mgr=mgr,
                        index=index,
                        scan_distance=scan_distance,
                        n_steps=n_steps,
                        points_per_step=points_per_step,
                    )

                    current_time = time.time() - time_initial
                    self.fit_line_scan(index, line_data, positions)
                    positions[index].append(np.array([[current_time], [self.XYZ_center[index]]]))

                    positions[index].updated_item(-1)
                    # fluorescence is the average of the line scan data
                    fluorescence.append(np.array([[current_time], [np.average(line_data)]]))
                    fluorescence.updated_item(-1)

                    ds.push({'params': params, 'x_label': 'Frequency (Hz)', 
                    'datasets':{
                        'x_pos': positions[0],
                        'y_pos': positions[1],
                        'z_pos': positions[2],
                        'total_fluor': fluorescence,
                    }})



                

                    
            
                if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                    return self.finalize(mgr)
            return self.finalize(mgr)
        
    def initialize(self, mgr, time_per_point):
        mgr.Pulser.set_state([7],0.0,0.0)
        mgr.DAQcontrol.create_counter()
        mgr.DAQcontrol.acq_rate=1/time_per_point
        return

    def scan_axis(self, mgr, index, scan_distance, n_steps, points_per_step):
        axis_key = ['x', 'y', 'z'][index]
        start = dict(self.initial)
        end = dict(self.initial)
        start[axis_key] = self.XYZ_center[index] - scan_distance[index] / 2
        end[axis_key] = self.XYZ_center[index] + scan_distance[index] / 2

        line_data = mgr.DAQcontrol.line_scan(start, end, n_steps, points_per_step)
        line_data = rpyc.utils.classic.obtain(line_data)

        positions = np.linspace(
            self.XYZ_center[index] - scan_distance[index] / 2,
            self.XYZ_center[index] + scan_distance[index] / 2,
            n_steps * points_per_step,
        )
        return positions, line_data

    def fit_line_scan(self, index, tracking_data, tracking_steps):
        p0 = [np.max(tracking_data), tracking_steps[np.argmax(tracking_data)], self.spot_size, np.min(tracking_data)]
        try:
            popt, _ = optimize.curve_fit(self.gaussian, tracking_steps, tracking_data, p0=p0)
            plot_center_fit = popt[1]
            if np.min(tracking_steps) <= plot_center_fit <= np.max(tracking_steps):
                if popt[0] < 0:
                    pass
                else:
                    new_position = plot_center_fit
            else:
                new_position = tracking_steps[np.argmax(tracking_data)]
        except:
            new_position = tracking_steps[np.argmax(tracking_data)]
        self.drift[index] = new_position - self.XYZ_center[index]
        if self.drift[index] < self.convergence_threshold:
            self.found[index] = True
        self.XYZ_center[index] = new_position

    def finalize(self,mgr):
        mgr.Pulser.set_state_off()
        mgr.DAQcontrol.finalize_counter()
        mgr.DAQcontrol.move(self.initial)
        return