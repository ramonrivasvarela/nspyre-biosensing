from lantz import Driver, Q_
from lantz.core.feat import Feat
import nidaqmx
import numpy as np
from nidaqmx.stream_writers import AnalogMultiChannelWriter
from collections import OrderedDict


class NIDAQAxis:
    def __init__(self, ao_ch, units, cal, limits=(None, None)):
        self.ch = ao_ch
        self.units = units
        self.cal = cal
        self.limits = limits

    def enforce_units(self, val):
        #checks that val is an instance of Q_, and then converts it to the correct units
        if not isinstance(val, Q_):
            val = Q_(val, self.units)
        else:
            val = val.to(self.units)
        return val

    def units_to_volts(self, pos):
        #converts positions in uits to volts using the calibration factor
        return (self.enforce_units(pos) * self.cal).to('V').m


class NIDAQMotionController(Driver):
    def __init__(self, ctr_ch, acq_rate, axes):
        self.axes = OrderedDict(axes)
        self.position = {a: Q_(0.0, self.axes[a].units) for a in self.axes}
        self.acq_rate = acq_rate
        self.ctr_ch = ctr_ch

    def initialize(self):
        self.ao_motion_task = nidaqmx.Task('AO_Task')
        for a in self.axes:
            limits = {}
            if self.axes[a].limits[0]:
                limits['min_val'] = self.axes[a].units_to_volts(self.axes[a].limits[0])
            if self.axes[a].limits[1]:
                limits['max_val'] = self.axes[a].units_to_volts(self.axes[a].limits[1])
            self.ao_motion_task.ao_channels.add_ao_voltage_chan(self.axes[a].ch, name_to_assign_to_channel=a, **limits)

    def finalize(self):
        self.ao_motion_task.close()

    def enforce_point_units(self, point):
        return {axis: self.axes[axis].enforce_units(point[axis]) for axis in point}

    def move(self, point):
        target = self.enforce_point_units(point)
        steps = 10  # smooth motion with 10 steps
        start_volts = np.array([self.axes[a].units_to_volts(self.position[a]) for a in self.axes])
        stop_volts = np.array([self.axes[a].units_to_volts(target[a]) for a in self.axes])
        voltages = np.linspace(start_volts, stop_volts, steps).T

        self.ao_motion_task.timing.cfg_samp_clk_timing(
            self.acq_rate.to('Hz').m,
            sample_mode=nidaqmx.constants.AcquisitionType.FINITE,
            samps_per_chan=steps
        )

        writer = AnalogMultiChannelWriter(self.ao_motion_task.out_stream, auto_start=False)
        writer.write_many_sample(voltages)
        self.ao_motion_task.start()
        self.ao_motion_task.wait_until_done()
        self.ao_motion_task.stop()

        self.position = target


class UriSetup(Driver):
    def __init__(self, x_ch, y_ch, z_ch, ctr_ch):
        #conversion from voltage to micrometers 
        x = NIDAQAxis(x_ch, 'um', Q_(0.73 / 11.42, 'V/um'), limits=(Q_(-114.2 / 0.73, 'um'), Q_(114.2 / 0.73, 'um')))
        y = NIDAQAxis(y_ch, 'um', Q_(1 / 11.42, 'V/um'), limits=(Q_(-114.2, 'um'), Q_(114.2, 'um')))
        z = NIDAQAxis(z_ch, 'um', Q_(1 / 25, 'V/um'), limits=(Q_(0, 'um'), Q_(250, 'um')))
        self.daq_controller = NIDAQMotionController(ctr_ch, Q_(15, 'kHz'), {'x': x, 'y': y, 'z': z})

    def initialize(self):
        self.daq_controller.initialize()

    def finalize(self):
        self.daq_controller.finalize()

    @Feat(units='um')
    def x(self):
        return self.daq_controller.position['x']

    @x.setter
    def x(self, val):
        self.daq_controller.move({'x': val, 'y': self.y, 'z': self.z})

    @Feat(units='um')
    def y(self):
        return self.daq_controller.position['y']

    @y.setter
    def y(self, val):
        self.daq_controller.move({'x': self.x, 'y': val, 'z': self.z})

    @Feat(units='um')
    def z(self):
        return self.daq_controller.position['z']

    @z.setter
    def z(self, val):
        self.daq_controller.move({'x': self.x, 'y': self.y, 'z': val})
