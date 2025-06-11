import nidaqmx
import numpy as np
from collections import OrderedDict
from nidaqmx.stream_writers import AnalogMultiChannelWriter

#from lantz import Driver          # nspyre ≥ 2.0


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
        super().__init__()                       # <- important
        self.axes      = OrderedDict(axes)
        self.position  = {name: 0 for name in axes}
        self.acq_rate  = acq_rate
        self.ctr_ch    = ctr_ch
        self.ao_motion_task = None

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
        if self.ao_motion_task:
            self.ao_motion_task.close()

    # ---- motion ----
    # def _normalize_point(self, point):
    #     return {axis: self.axes[axis]._as_quantity(val) for axis, val in point.items()}

    def move(self, target: dict):
        steps       = 10
        start_v = np.array([
            axis.units_to_volts(self.position[name])
            for name, axis in self.axes.items()
        ])
        stop_v = np.array([
            axis.units_to_volts(target[name])
            for name, axis in self.axes.items()
        ])
        voltages    = np.linspace(start_v, stop_v, steps).T

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


# ---------- high-level XYZ driver ----------
class XYZSetup():
    def __init__(self, x_ch, y_ch, z_ch, ctr_ch):
        super().__init__()                       # <- important

        x = NIDAQAxis(x_ch, 0.73/11.42 ,
                      limits=(-114.2/0.73, 114.2/0.73))
        y = NIDAQAxis(y_ch,  1/11.42,
                      limits=(-114.2,  114.2    ))
        z = NIDAQAxis(z_ch, 1/25,
                      limits=(0, 250      ))

        self.ctrl = NIDAQMotionController(ctr_ch, 15000,
                                          {'x': x, 'y': y, 'z': z})

    # nspyre life-cycle proxies
    def initialize(self):
        self.ctrl.initialize()

    

    # getters
    def get_x(self): return self.ctrl.position['x']
    def get_y(self): return self.ctrl.position['y']
    def get_z(self): return self.ctrl.position['z']

    # single-axis moves
    def move_x(self, val): self.ctrl.move({'x': val, 'y': self.get_y(), 'z': self.get_z()})
    def move_y(self, val): self.ctrl.move({'x': self.get_x(), 'y': val, 'z': self.get_z()})
    def move_z(self, val): self.ctrl.move({'x': self.get_x(), 'y': self.get_y(), 'z': val})

    # 3-axis move
    def move_to(self, x=None, y=None, z=None):
        self.ctrl.move({
            'x': x if x is not None else self.get_x(),
            'y': y if y is not None else self.get_y(),
            'z': z if z is not None else self.get_z()
        })

    def finalize(self):
        self.move_to(0, 0, 0)  # Move to home position
        self.ctrl.finalize()
