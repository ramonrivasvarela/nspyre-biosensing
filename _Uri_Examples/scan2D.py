import numpy as np
import time
# Once the __init__ is completed, this will work instead of all these big file names.
from nspyre import *
# This imports all the important stuff from __all__
from nspyre.gui.widgets.views import Plot1D, Plot2D, PlotFormatInit, PlotFormatUpdate
from nspyre.gui.widgets.plotting import HeatmapPlotWidget
from nspyre.spyrelet.spyrelet import Spyrelet
from nspyre.definitions import Q_
# import the instrument.
from lantz.drivers.ni.UriFSM import UriSetup
# making sure i save to excel
from threed.data_and_plot import save_excel


#jacob's advice for stopping hanging
import rpyc

class Scan2D(Spyrelet):
    REQUIRED_DEVICES = [
        'pulses',
        'urixyz',
    ]

    PARAMS = {
        'point_A':              {'type': str},
        'point_B':              {'type': str},
        'point_C':              {'type': str},
        'line_scan_steps':      {'type': int},
        'extent_steps':         {'type': int},
        'ctr_ch':               {'type': str},
        'repetitions':          {'type': int, 'positive': True},
        'stack_count':          {'type': int, 'positive': True},
        'stack_stepsize':       {'type': str},        
        'stack_pospref':        {'type': bool},
        'acq_rate':             {'type': float, 'nonnegative': True, 'units':'Hz'},
        'pts_per_step':         {'type': int, 'positive': True},
        'xyz_pos':              {'type': bool, 'default': True},
        'excel':                {'type': bool, 'default': False},##{'type': object},
        'snake_scan':           {'type': bool, 'default': False},
        'sleep_factor':         {'type': float, 'positive': True}
    }

    CONSTS = {}

    def main(self, point_A="Q_([0, 0, 0], 'um')",
                    point_B="Q_([50, 0, 0], 'um')",
                    point_C="Q_([50, 0, 60], 'um')",
                    line_scan_steps=100, extent_steps=100,
                    ctr_ch='Dev1/ctr1', repetitions=1, 
                    stack_count = 1, stack_stepsize = "Q_(1, 'um')", 
                    stack_pospref = False, 
                    acq_rate=Q_(15000, 'Hz'), pts_per_step=40, xyz_pos = True, 
                    excel = False, snake_scan = False, sleep_factor=1):
        # defining move() function sleep time 
        self.urixyz.daq_controller.sleep_factor = sleep_factor
        print('sleep_factor in spyrelet main:', sleep_factor)
        print('assigned sleep_factor in urixyz by main:', self.urixyz.daq_controller.sleep_factor)
        # starting point for scan
        origin = eval(point_A)
        # this point gives the direction and bound of the line scan
        scan_pt = eval(point_B)
        # this point gives the direction and extent of the "stepping" direction normal to the line scan direction
        extent_pt = eval(point_C)
        line_scan_steps = line_scan_steps + 1
        try:
            z = (e for e in origin)
            z = (e for e in scan_pt)
            z = (e for e in extent_pt)
            if len(origin) != 3 or len(scan_pt) != 3 or len(extent_pt) != 3:
                raise TypeError
            for f in origin + scan_pt + extent_pt:
                if not isinstance(f, Q_):
                    raise TypeError
        except:
            print('point should be in the form of "(x, y, z)"')
            raise
        
        # converting all input point to um
        scan_pt = np.array([scan_pt[0].to('um').m, scan_pt[1].to('um').m, scan_pt[2].to('um').m])
        origin = np.array([origin[0].to('um').m, origin[1].to('um').m, origin[2].to('um').m])
        extent_pt = np.array([extent_pt[0].to('um').m, extent_pt[1].to('um').m, extent_pt[2].to('um').m])
        
        # vector in the direction of the line scan
        scan_vector = np.array(scan_pt) - np.array(origin)
        if np.linalg.norm(scan_vector) < 0.001:
            print('scan size can\'t be 0')
            raise TypeError
            
        # vector from A to C
        vector_AC = np.array(extent_pt) - np.array(origin)
        
        # projection of vector_AC on scan_vector
        proj_vector = np.dot(scan_vector, vector_AC) * scan_vector / np.linalg.norm(scan_vector)**2
        
        # vector in the direction of stepping (normal to the line scan)
        extent_vector = vector_AC - proj_vector
        
        # normal_to_plane vector
        perp_vector = np.cross(scan_vector, extent_vector)        
        
        # z-stack vector size of step
        stack_vector = perp_vector / np.linalg.norm(perp_vector) * eval(stack_stepsize).to('um').m    
        
        #possible reorientation so that normal vector points up in z.
        if ((stack_pospref) and (stack_vector[2] < 0)):
            stack_vector = -stack_vector
        
        
            
        adjust_line = np.dot(origin, scan_vector)/np.linalg.norm(scan_vector) #returns scalar
        adjust_step = np.dot(origin, extent_vector)/np.linalg.norm(extent_vector)
        if not (xyz_pos):
            adjust_line = 0
            adjust_step = 0
            
        z_stack = np.mean(range(1, stack_count + 1))
        # we reassign the origin vector, so that it starts at the bottom of the z-stack range
        origin = origin - stack_vector * z_stack
        #print(z_stack)
        for z in self.progress(range(stack_count)):   
            # make sure the origin moves by one stack of stack_vector on each iteration of z-stacking
            origin = origin + stack_vector
            for rep in self.progress(range(repetitions)):
                for s in self.progress(range(extent_steps + 1)):
                    line_scan_start_pt = np.array(origin) + s/(extent_steps) * extent_vector
                    line_scan_stop_pt = line_scan_start_pt + scan_vector
                    
                    ## adding option for snake scan
                    if snake_scan == True and (s+1)%2 == 0:
                        print('s:', s)
                        line_scan_start_pt = line_scan_stop_pt
                        line_scan_stop_pt = np.array(origin) + s/(extent_steps) * extent_vector
                        
                    line_data = self.urixyz.line_scan({'x': Q_(line_scan_start_pt[0], 'um'),
                                                       'y': Q_(line_scan_start_pt[1], 'um'),
                                                       'z': Q_(line_scan_start_pt[2], 'um')}, 
                                                       {'x': Q_(line_scan_stop_pt[0], 'um'),
                                                       'y': Q_(line_scan_stop_pt[1], 'um'),
                                                       'z': Q_(line_scan_stop_pt[2], 'um')},
                                                        line_scan_steps, pts_per_step)
                    
                    #import pdb; pdb.set_trace()                    #print(s / extent_steps * np.linalg.norm(extent_vector))                    #print(np.linspace(0, np.linalg.norm(scan_vector), line_scan_steps))                    #print(z)                    #print(origin)                    #print(z - z_stack + 1)
                    
                    ## in case of a snake scan
                    if snake_scan == True and (s+1)%2 == 0:
                        #print('line data:', line_data, 'type:', type(line_data))
                        line_data = line_data[::-1]
                        
                    self.acquire({
                        'rep_idx': rep,
                        'step_idx': s,      
                        'line_data': rpyc.utils.classic.obtain(line_data),
                        'step_val': s / extent_steps * np.linalg.norm(extent_vector) + adjust_step,
                        'scan_vals': np.linspace(adjust_line, np.linalg.norm(scan_vector) + adjust_line, line_scan_steps),      
                        
                        #here are the ones for my gui                  
                        'stack_idx': z,
                        'stack_pos': (z - z_stack + 1) * np.linalg.norm(stack_vector),
                        'scan_vector': scan_vector,
                        'extent_vector': extent_vector,
                        'stack_vector': stack_vector,
                        'scan_cts': line_scan_steps,
                        'steps_cts': extent_steps + 1,
                        'start_pt': line_scan_start_pt,
                        'stop_pt': line_scan_stop_pt
                    })
            
        
        
                
    def initialize(self, point_A="Q_([0, 0, 0], 'um')",
                    point_B="Q_([50, 0, 0], 'um')",
                    point_C="Q_([50, 0, 60], 'um')",
                    line_scan_steps=100, extent_steps=100,
                    ctr_ch='Dev1/ctr1', repetitions=1, 
                    stack_count = 1, stack_stepsize = "Q_(1, 'um')", 
                    stack_pospref = False, 
                    acq_rate=Q_(15000, 'Hz'), pts_per_step=40, xyz_pos = True, 
                    excel = False, snake_scan = False, sleep_factor=1):
        self.urixyz.new_ctr_task(ctr_ch)
        self.urixyz.daq_controller.acq_rate = acq_rate
        
        self.pulses.Pulser.constant(([7],0.0,0.0))
        print('proof i turned on the laser')
        # print("if error, then I know 'self' does not have attribute 'name'")
        # print("spyrelet name is", self.name)
        
    def finalize(self, point_A="Q_([0, 0, 0], 'um')",
                    point_B="Q_([50, 0, 0], 'um')",
                    point_C="Q_([50, 0, 60], 'um')",
                    line_scan_steps=100, extent_steps=100,
                    ctr_ch='Dev1/ctr1', repetitions=1, 
                    stack_count = 1, stack_stepsize = "Q_(1, 'um')", 
                    stack_pospref = False, 
                    acq_rate=Q_(15000, 'Hz'), pts_per_step=40, xyz_pos = True, 
                    excel = False, snake_scan = False, sleep_factor=1):
        
        if excel:
            save_excel(self.name)

    @PlotFormatInit(HeatmapPlotWidget, ['latest', 'avg', 'stack1', 'stack2', 'stack3', 'total'])#['latest', 'avg'])
    def init_format(p):
        p.xlabel = 'X (um)'
        p.ylabel = 'Y (um)'

    @PlotFormatUpdate(HeatmapPlotWidget, ['latest', 'avg', 'stack1', 'stack2', 'stack3', 'total'])#['latest', 'avg'])
    def update_format(p, df, cache):
        xs, ys     = df.scan_vals[0],    df.step_val.unique()
        diff       = [xs[-1]-xs[0] , ys[-1]-ys[0]]
        p.im_pos   = [np.mean(xs) - diff[0]/2, np.mean(ys) - diff[1]/2]
        p.im_scale = [diff[0]/len(xs) , diff[1]/len(ys)]
        p.set(p.w.image) #We have to redraw for the scaling to take effect

    @Plot2D
    def latest(df, cache):
        latest = df[df.rep_idx == df.rep_idx.max()]
        #print(df)
        im = np.vstack(latest.sort_values('step_idx')['line_data'])
        #print(im)
        max_rows = len(df.line_data[0])
        #print(df.line_data[0])
        #print(max_rows - im.shape[1])
        #print("latest")
        return np.pad(im, (max_rows - im.shape[1]), mode='constant', constant_values=0)

    @Plot2D
    def avg(df, cache):
        grouped = df.groupby('step_idx')['line_data']
        averaged = grouped.apply(lambda column: np.mean(np.vstack(column), axis=0))
        im = np.vstack(averaged)
        max_rows = len(df.scan_vals[0])
        #print("avg")
        return np.pad(im, (0, max_rows - im.shape[1]), mode='constant', constant_values=0)
        
    # # # # # # # @Plot2D
    # # # # # # # def not_adjusted(df, cache):
        # # # # # # # xyz = df[df.rep_idx == df.rep_idx.max()]
        # # # # # # # #print(df)
        # # # # # # # im = np.vstack(xyz.sort_values('step_idx')['line_data'])
        # # # # # # # #print(im)
        # # # # # # # max_rows = len(df.line_data[0])
        # # # # # # # #print(max_rows)
        # # # # # # # #print(im.shape)
        # # # # # # # #print(df.line_data[0])
        # # # # # # # #print(max_rows - im.shape[1])
        # # # # # # # #print("latest")
        # # # # # # # return np.pad(im, (max_rows - im.shape[1]), mode='constant', constant_values=0)
    
    # @PlotFormatInit(StackPlotWidget, ['opengl'])
    # def init_format(p):
        # gaxis = gl.Custom3DAxis(self.w, neg_extent = [-20, -20, -20], pos_extent = [20, 20, 20], color=(100,100,.200, .6))
        # return gaxis
        
    
    # @Plot2D
    # def total(df, cache):
        # #print("Here is the data frame")
        # #print(df)
        # #print("Here I sort the values")
        # grouped = (df.sort_values(by=['stack_idx', 'step_idx'])['line_data'])
        # #print(grouped)
        # #print(grouped.axes)
        # #print("Here I construct the image")
        # im = np.vstack(grouped)
        # max_rows = len(df.scan_vals[0])
        # #print(np.pad(im, (0, max_rows - im.shape[1]), mode='constant', constant_values=0))
        # return np.pad(im, (0, max_rows - im.shape[1]), mode='constant', constant_values=0)
        
    """
    i want to figure out a way to iterate these stacks. 
    might not be able to do such a thing in the viewmanager
    """
    @Plot2D
    def stack1(df, cache):
        stack = df[df.stack_idx == 1]
        #print(df)
        #print(df.items())
        im = np.vstack(stack.sort_values('step_idx')['line_data'])
        max_rows = len(df.line_data[0])
        return np.pad(im, (0, max_rows - im.shape[1]), mode='constant', constant_values=0)
    
    # @Plot2D
    # def stack2(df, cache):
        # stack = df[df.stack_idx == 2]
        # im = np.vstack(stack.sort_values('step_idx')['line_data'])
        # max_rows = len(df.line_data[0])
        # return np.pad(im, (0, max_rows - im.shape[1]), mode='constant', constant_values=0)
        
    # @Plot2D
    # def stack3(df, cache):
        # stack = df[df.stack_idx == 3]
        # im = np.vstack(stack.sort_values('step_idx')['line_data'])
        # max_rows = len(df.line_data[0])
        # return np.pad(im, (0, max_rows - im.shape[1]), mode='constant', constant_values=0)