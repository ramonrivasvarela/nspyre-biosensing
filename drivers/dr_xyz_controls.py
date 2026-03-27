import nidaqmx
import numpy as np
from collections import OrderedDict
from nidaqmx.stream_writers import AnalogMultiChannelWriter
from nidaqmx.stream_readers import CounterReader

#from lantz import Driver          # nspyre ≥ 2.0
'''
DEPRECATED!!!!!!!
'''

# ---------- low-level helpers ----------
class NIDAQAxis:
    def __init__(self, ao_ch, cal, limits=(None, None)):
        self.ch      = ao_ch
        #self.units   = units
        self.cal     = cal           # V / unit
        self.limits  = limits        # (min, max) in <units>

    # ---- unit handling ----
    # def _as_quantity(self, val):
    #     if not isinstance(val, Q_):
    #         val = Q_(val, self.units)
    #     else:
    #         val = val.to(self.units)
    #     return val

    def units_to_volts(self, pos):
        return (pos * self.cal)


class NIDAQMotionController():
    def __init__(self, ctr_ch, acq_rate, axes: dict[str, NIDAQAxis]):
        # super().__init__()                       # <- important
        self.axes      = OrderedDict(axes)
        self.position  = {name: 0 for name in axes}
        self.acq_rate  = acq_rate
        self.ctr_ch    = ctr_ch
        self.ao_motion_task = None
        self.current_counter_task = None
        self.counter_tasks = []


    # ---- nspyre life-cycle ----
    def initialize(self):
        if self.ao_motion_task is not None:
            self.finalize()
        self.ao_motion_task = nidaqmx.Task('AO_Task')
        for name, ax in self.axes.items():
            kw = {}
            if ax.limits[0] is not None:
                kw['min_val'] = ax.units_to_volts(ax.limits[0])
            if ax.limits[1] is not None:
                kw['max_val'] = ax.units_to_volts(ax.limits[1])
            self.ao_motion_task.ao_channels.add_ao_voltage_chan(
                ax.ch, name_to_assign_to_channel=name, **kw
            )

    def finalize(self):
        # if self.ao_motion_task:
        #     self.ao_motion_task.close()
        if self.ao_motion_task:
            try:
                self.ao_motion_task.stop()
            except nidaqmx.errors.DaqError:
                pass
            self.ao_motion_task.close()
        self.ao_motion_task = None
        for t in self.counter_tasks:
            try:
                t.close()
            except Exception:
                # you might log this if you want visibility into failures
                pass

        # 2) Now clear the list and reset the pointer
        self.counter_tasks.clear()
        self.current_counter_task = None

    def new_ctr_task(self, ctr_ch):
        self.current_counter_task = nidaqmx.Task('NIDAQMotionController_CTR_{}'.format(np.random.randint(2**31)))
        self.current_counter_task.ci_channels.add_ci_count_edges_chan(ctr_ch)
        self.counter_tasks.append(self.current_counter_task)

    def end_ctr_task(self):
        """End the current counter task and remove it from the list of tasks."""
        if self.current_counter_task:
            try:
                self.current_counter_task.stop()
            except nidaqmx.errors.DaqError:
                pass
            self.current_counter_task.close()
            self.current_counter_task = None
        # Remove the task from the list of counter tasks
        self.counter_tasks = [t for t in self.counter_tasks if t is not None]

    # ---- motion ----
    # def _normalize_point(self, point):
    #     return {axis: self.axes[axis]._as_quantity(val) for axis, val in point.items()}

    def move(self, target: dict):
        for name, axis in self.axes.items():
            if target[name] < axis.limits[0] or target[name] > axis.limits[1]:
                raise ValueError(f"{name} position {target[name]} is out of bounds {axis.limits}")
        steps = 10
        start_v = np.array([
            axis.units_to_volts(self.position[name])
            for name, axis in self.axes.items()
        ])
        stop_v = np.array([
            axis.units_to_volts(target[name])
            for name, axis in self.axes.items()
        ])
        voltages = np.linspace(start_v, stop_v, steps).T

        # Ensure voltages array is C-contiguous
        voltages = np.ascontiguousarray(voltages)

        self.ao_motion_task.timing.cfg_samp_clk_timing(
            self.acq_rate,
            sample_mode=nidaqmx.constants.AcquisitionType.FINITE,
            samps_per_chan=steps,
        )

        writer = AnalogMultiChannelWriter(self.ao_motion_task.out_stream, auto_start=False)
        writer.write_many_sample(voltages)
        self.ao_motion_task.start()
        self.ao_motion_task.wait_until_done()
        self.ao_motion_task.stop()

        self.position = target

    def line_scan(self, init_point, final_point, steps, pts_per_step=1):
        """1-axis line scan while acquiring counter data"""
        #print(init_point)
        #print('self.sleep_factor in line scan right before calling move():', self.sleep_factor)
        self.move(init_point)
        #print("start line_scan")
        step_voltages = self.linear_func(init_point, final_point, steps)
        step_voltages = np.repeat(step_voltages, pts_per_step + 1, axis=0)
        # configure analog output task
        self.ao_motion_task.timing.cfg_samp_clk_timing(
            self.acq_rate,
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
        ni_ao_sample_buffer = np.ascontiguousarray(step_voltages.transpose(), dtype=float)
        # TODO timeout
        sample_writer_stream.write_many_sample(ni_ao_sample_buffer, timeout=60)
        
        # e.g. "Dev1"
        device_name = list(self.axes.items())[0][1].ch.split('/')[0]
        
        # configure counter input task
        self.current_counter_task.timing.cfg_samp_clk_timing(
            self.acq_rate,
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
        # print('what is my final point', final_point, self.position)
        return averaged*self.acq_rate
    
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
    
    
    
    
  

# ---------- high-level XYZ driver ----------
class XYZSetup(NIDAQMotionController):
    def __init__(self, x_ch, y_ch, z_ch, ctr_ch, acq_rate=15000):
        # Initialize the parent class (NIDAQMotionController)
        super().__init__(ctr_ch, acq_rate, {
            'x': NIDAQAxis(x_ch, 0.73 / 11.42, limits=(-114.2 / 0.73, 114.2 / 0.73)),  # Calibration: V/um
            'y': NIDAQAxis(y_ch, 1 / 11.42, limits=(-114.2, 114.2)),  # Calibration: V/um
            'z': NIDAQAxis(z_ch, 1 / 25, limits=(0, 250))  # Calibration: V/um
        })

    # nspyre life-cycle proxies
    def initialize(self):
        super().initialize()

    # getters
    def get_x(self): return self.position['x']
    def get_y(self): return self.position['y']
    def get_z(self): return self.position['z']

    def get_position(self):

        return {'x':self.position['x'], 'y':self.position['y'], 'z':self.position['z']}

    # single-axis moves
    def move_x(self, val): super().move({'x': val, 'y': self.get_y(), 'z': self.get_z()})
    def move_y(self, val): super().move({'x': self.get_x(), 'y': val, 'z': self.get_z()})
    def move_z(self, val): super().move({'x': self.get_x(), 'y': self.get_y(), 'z': val})

    # 3-axis move
    def move_to(self, x=None, y=None, z=None):
        super().move({
            'x': x if x is not None else self.get_x(),
            'y': y if y is not None else self.get_y(),
            'z': z if z is not None else self.get_z()
        })
    
    def move_to_dict(self, pos_dict):
        """Move to a position specified by a dictionary with keys 'x', 'y', and 'z'."""
        self.move_to(pos_dict['x'], pos_dict['y'], pos_dict['z'])

    def reset_and_finalize(self):
        self.move_to(0, 0, 0)  # Move to home position
        super().finalize()



    
