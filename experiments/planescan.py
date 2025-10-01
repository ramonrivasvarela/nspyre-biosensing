"""
experiment to get a wide-field scan of a sample

Written by Ramon Rivas
Written on 6/12/2025

"""

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



class PlaneScan:
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

    def planescan(self, dataset: str, point_A : dict ={'x': 0, 'y': 0, 'z': 0},
                    point_B : dict ={'x': 50, 'y': 0, 'z': 0},
                    point_C : dict ={'x': 50, 'y': 0, 'z': 60},
                    line_scan_steps: int=100, extent_steps: int=100,
                     repetitions: int =1,
                    stack_count: int = 1, stack_stepsize: int = 1,
                    stack_pospref: bool = False,
                    acq_rate: int =15000, pts_per_step: int =40, xyz_pos: bool = True, snake_scan :bool = False, sleep_factor : float=1):
        with InstrumentManager() as mgr, DataSource(dataset) as planescan_data:
            # mgr.XYZcontrol.daq_controller.sleep_factor = sleep_factor
            current_position = mgr.DAQcontrol.get_position()
            # starting point for scan
            origin = (point_A['x'], point_A['y'], point_A['z'])
            # this point gives the direction and bound of the line scan
            scan_pt = (point_B['x'], point_B['y'], point_B['z'])
            # this point gives the direction and extent of the "stepping" direction normal to the line scan direction
            extent_pt = (point_C['x'], point_C['y'], point_C['z'])
            line_scan_steps = line_scan_steps + 1

            try:
                if len(origin) != 3 or len(scan_pt) != 3 or len(extent_pt) != 3:
                    raise TypeError("Each point must have three elements: x, y, and z.")
                for f in origin + scan_pt + extent_pt:
                    if not isinstance(f, (int, float)):
                        raise TypeError("Each coordinate must be a numeric value.")
            except Exception as e:
                print('Point should be in the form of a dictionary with keys "x", "y", "z" and numeric values.')
                raise

            # converting points to numpy arrays (if needed, you could also scale these values)
            origin = np.array(origin)
            scan_pt = np.array(scan_pt)
            extent_pt = np.array(extent_pt)
            
            # vector in the direction of the line scan
            scan_vector = np.array(scan_pt) - np.array(origin)
            if np.linalg.norm(scan_vector) < 0.001:
                print('scan size can\'t be 0')
                raise ValueError("Scan size can't be 0")

            # vector from A to C
            vector_AC = np.array(extent_pt) - np.array(origin)
            
            # projection of vector_AC on scan_vector
            proj_vector = np.dot(scan_vector, vector_AC) * scan_vector / np.linalg.norm(scan_vector)**2
            
            # vector in the direction of stepping (normal to the line scan)
            extent_vector = vector_AC - proj_vector
            
            # normal_to_plane vector
            perp_vector = np.cross(scan_vector, extent_vector)        
            
            # z-stack vector size of step
            stack_vector = perp_vector / np.linalg.norm(perp_vector) * stack_stepsize  
            
            #possible reorientation so that normal vector points up in z.
            if ((stack_pospref) and (stack_vector[2] < 0)):
                stack_vector = -stack_vector
            
            
                
            adjust_line = np.dot(origin, scan_vector)/np.linalg.norm(scan_vector) #returns scalar
            adjust_step = np.dot(origin, extent_vector)/np.linalg.norm(extent_vector)
            # if not (xyz_pos):
            #     adjust_line = 0
            #     adjust_step = 0
                
            z_stack = (1 + stack_count) / 2
            # we reassign the origin vector, so that it starts at the bottom of the z-stack range
            
            #print(z_stack)
            # heatmap = np.zeros((extent_steps + 1, line_scan_steps))
            # if snake_scan:
            #     heatmap= np.zeros((extent_steps + 1, line_scan_steps))
            # _logger.info(f"heatmap shape: {heatmap.shape}")
            # heatmap_dataset = StreamingList()
            # heatmap_dataset.append(heatmap.copy())
            scan_vals = np.linspace(
                            adjust_line,
                            np.linalg.norm(scan_vector) + adjust_line,
                            line_scan_steps
                        )
            step_vals = np.linspace(
                adjust_step,                                # start offset
                np.linalg.norm(extent_vector) + adjust_step,# end offset
                extent_steps + 1                            # rows = extent_steps+1
            )
            if stack_count>1:
                self.check_limit(mgr, origin-stack_vector*(z_stack-1), 'origin-stack_vector*(z_stack-1)')
                self.check_limit(mgr, origin+stack_vector*(z_stack-1), 'origin+stack_vector*(z_stack-1)')
                self.check_limit(mgr, origin+scan_vector-stack_vector*(z_stack-1), 'origin+scan_vector-stack_vector*(z_stack-1)')
                self.check_limit(mgr, origin+extent_vector-stack_vector*(z_stack-1), 'origin+extent_vector-stack_vector*(z_stack-1)')
                self.check_limit(mgr, origin+scan_vector+extent_vector-stack_vector*(z_stack-1), 'origin+scan_vector+extent_vector-stack_vector*(z_stack-1)')
                self.check_limit(mgr, origin+scan_vector+stack_vector*(z_stack-1), 'origin+scan_vector+stack_vector*(z_stack-1)')
                self.check_limit(mgr, origin+extent_vector+stack_vector*(z_stack-1), 'origin+extent_vector+stack_vector*(z_stack-1)')
                self.check_limit(mgr, origin+scan_vector+extent_vector+stack_vector*(z_stack-1), 'origin+scan_vector+extent_vector+stack_vector*(z_stack-1)')
            else:
                self.check_limit(mgr, origin, 'origin')
                self.check_limit(mgr, origin+scan_vector, 'origin+scan_vector')
                self.check_limit(mgr, origin+extent_vector, 'origin+extent_vector')
                self.check_limit(mgr, origin+scan_vector+extent_vector, 'origin+scan_vector+extent_vector')
            if snake_scan:
                scan_vals=scan_vals
            self.initialize(mgr,  acq_rate)
            origin = origin - stack_vector * z_stack
            datasets={}
            for z in range(stack_count):
                datasets[f"stack_{z+1}"]= StreamingList(np.zeros((extent_steps + 1, line_scan_steps)))
                origin = origin + stack_vector
                for rep in range(repetitions):
                    print(origin)
                    for s in range(extent_steps + 1):
                        # step_vals.append(adjust_step + s/(extent_steps) * np.linalg.norm(extent_vector))
                        
                        line_scan_start_pt = origin + s/(extent_steps) * extent_vector
                        line_scan_stop_pt = line_scan_start_pt + scan_vector 
                        
                        ## adding option for snake scan
                        if snake_scan == True and (s+1)%2 == 0:
                            print('s:', s)
                            line_scan_start_pt = line_scan_stop_pt#-scan_vector/(line_scan_steps)
                            line_scan_stop_pt = origin + s/(extent_steps) * extent_vector#-scan_vector/(line_scan_steps)

                        line_data = mgr.DAQcontrol.line_scan({'x': line_scan_start_pt[0],
                                                                'y': line_scan_start_pt[1],
                                                                'z': line_scan_start_pt[2]},
                                                                {'x': line_scan_stop_pt[0],
                                                                'y': line_scan_stop_pt[1],
                                                                'z': line_scan_stop_pt[2]},
                                                            line_scan_steps, pts_per_step)
                        print("running well.")
                        #import pdb; pdb.set_trace()                    #print(s / extent_steps * np.linalg.norm(extent_vector))                    #print(np.linspace(0, np.linalg.norm(scan_vector), line_scan_steps))                    #print(z)                    #print(origin)                    #print(z - z_stack + 1)

                        ## in case of a snake scan
                        if snake_scan == True:
                            
                            if (s+1)%2 == 0:
                            #print('line data:', line_data, 'type:', type(line_data))
                                line_data = line_data[::-1]
                            
                            
                        counts = rpyc.utils.classic.obtain(line_data)

                        datasets[f"stack_{z+1}"][s]+=counts
                        datasets[f"stack_{z+1}"].updated_item(s)
                        ## scan_vals contains the x values corresponding to the line scan data
                        
                        #stack_pos= (z - z_stack + 1) * np.linalg.norm(stack_vector) + adjust_step

                        # Append to streaming list and notify update
                        # Push data for live plotting: use StreamingList objects, not raw numpy arrays
                        planescan_data.push({
                            'params': {
                                'point_A': point_A,
                                'point_B': point_B,
                                'point_C': point_C,
                                'line_scan_steps': line_scan_steps,
                                'extent_steps': extent_steps,
                                'repetitions': repetitions,
                                'stack_count': stack_count,
                                'stack_stepsize': stack_stepsize,
                                'stack_pospref': stack_pospref,
                                'acq_rate': acq_rate,
                                'pts_per_step': pts_per_step,
                                'xyz_pos': xyz_pos,
                                'snake_scan': snake_scan,
                                'sleep_factor': sleep_factor
                            },
                            'name': 'Heatmap',
                            'xs': scan_vals,
                            'ys': step_vals,
                            'datasets': datasets
                        })




                        if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                            # the GUI has asked us nicely to exit
                            mgr.DAQcontrol.move(current_position)
                            self.finalize(mgr)
                            return
            mgr.DAQcontrol.move(current_position)
            self.finalize(mgr)
            

    def initialize(self, mgr, acq_rate=15000):
        #create control task, action task already created in app initizalization
        #mgr.XYZcontrol.initialize()   
        # mgr.DAQcontrol.n_samples=line_scan_steps+1        # (calls finalize internally if needed)
        mgr.DAQcontrol.create_counter()  # (calls finalize internally if needed)
        mgr.DAQcontrol.acq_rate = acq_rate

        mgr.Pulser.set_state([7],0.0,0.0)
        #mgr.DAQcontrol.initialize()

    def finalize(self,mgr):
        mgr.Pulser.set_state_off()
        mgr.DAQcontrol.finalize_counter()  # End the counter task
        #mgr.XYZcontrol.finalize()
        #mgr.DAQcontrol.finalize()
    
    
    def check_limit(self, mgr, point, str=""):
        """Check if the point is within the limits of the XYZ control."""
        if point[0]<mgr.DAQcontrol.axes['x'].limits[0] or point[0]>mgr.DAQcontrol.axes['x'].limits[1]:
            raise ValueError(f"x position {point[0]} of point {str} is out of bounds {mgr.DAQcontrol.axes['x'].limits}")
        if point[1]<mgr.DAQcontrol.axes['y'].limits[0] or point[1]>mgr.DAQcontrol.axes['y'].limits[1]:
            raise ValueError(f"y position {point[1]} of point {str} is out of bounds {mgr.DAQcontrol.axes['y'].limits}")
        if point[2]<mgr.DAQcontrol.axes['z'].limits[0] or point[2]>mgr.DAQcontrol.axes['z'].limits[1]:
            raise ValueError(f"z position {point[2]} of point {str} is out of bounds {mgr.DAQcontrol.axes['z'].limits}")
