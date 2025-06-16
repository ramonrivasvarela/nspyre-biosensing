"""
Copyright (c) 2021, Jacob Feder
All rights reserved.

This work is licensed under the terms of the 3-Clause BSD license.
For a copy, see <https://opensource.org/licenses/BSD-3-Clause>.
"""

"""
Based on code by Evan Villafranca - 2022 
David Ovetsky - 2025
"""

from functools import partial
from importlib import reload

import numpy as np

from nspyre import DataSink
from nspyre import LinePlotWidget
from nspyre import ParamsWidget
from nspyre import ProcessRunner
from nspyre import InstrumentManager

from pyqtgraph import SpinBox, ComboBox

from multiprocessing import Queue
from nspyre import SaveWidget
from PyQt6.QtWidgets import QLabel, QPushButton, QCheckBox, QComboBox, QLineEdit, QInputDialog, QRadioButton, QSlider, QDoubleSpinBox, QButtonGroup
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout
from PyQt6.QtWidgets import QWidget, QGraphicsOpacityEffect
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QTimer

#from lantz import Driver, Q_

import logging

from instrument_activation import xyz_activation_boolean


logger = logging.getLogger(__name__)

class InstWidgetV2(QWidget):
    """
    Qt widget subclass that generates an interface.
    """

    QUEUE_CHECK_TIME = 50 # ms

    def __init__(self):
        super().__init__()

        self.setWindowTitle('Instrument Manager')

        # self.updateTimer = QTimer() #create a timer that will try to update that widget with messages from the from_exp_queue
        # self.updateTimer.timeout.connect(lambda: self.check_queue_from_mag())
        # self.updateTimer.start(self.QUEUE_CHECK_TIME)

        self.white_border = "border: 1px solid white"
        self.font = "Arial"
        
        # self.q = Queue()

        self.init_sg396_widgets()
        self.init_xyz_control()
  


        self.layouts()

   

    '''
    CREATE WIDGETS -----------------------------------------------------------------------------------------------------------------------------------------------
    '''

    def init_sg396_widgets(self):
        # magnet stage widgets
        self.sg396_label = QLabel("Signal Generator Control")
        self.sg396_label.setFixedHeight(30)
        # self.sg396_label.setStyleSheet("color: white; background-color:  #2b2b2b; border: 1px solid black;")
        self.sg396_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sg396_label.setFont(QFont(self.font, 20))

        self.sg396_checkbox = QCheckBox("Enable SG394 output")
        self.sg396_checkbox.setChecked(False)
        self.sg396_checkbox.setStyleSheet("QCheckBox::indicator:hover" "{""background-color : powderblue;""}"
                                            "QCheckBox::indicator:pressed" "{""background-color : lightgreen;""}")
        self.sg396_checkbox.stateChanged.connect(lambda:self.sg396_checked(self.sg396_checkbox))

        self.sg396_params_widget_1 = ParamsWidget({ 
                ## LF Mode not yet implemented 

                # 'lf_toggle': {'display_text': 'Toggle LF',
                #                         'widget': QCheckBox('lf_toggle')},
                # 'lf_amplitude': {
                #     'display_text': 'LF Amplitude: ',
                #     'widget': SpinBox(
                #         value = -45,
                #         suffix = 'dBm',
                #         bounds = (-45, 10),
                #         step = 1,
                #     ),
                # },
                # 'lf_offset': {
                #     'display_text': 'LF Offset: ',
                #     'widget': SpinBox(
                #         value = 0,
                #         suffix = 'V',
                #         siPrefix = True,
                #         bounds = (-1.5, 1.5),
                #         dec = True,
                #     ),
                # },

                ## Handled With Emit
                # 'rf_toggle': {'display_text': 'Toggle MW',
                #                         'widget': QCheckBox('rf_toggle')},
                'rf_amplitude': {
                    'display_text': 'MW Amplitude: ',
                    'widget': SpinBox(
                        value = -20,
                        suffix = 'dBm',
                        bounds = (-110, 10),
                        step = 1,
                    ),
                },
                'rf_frequency': {
                    'display_text': 'MW Frequency: ',
                    'widget': SpinBox(
                        value = 2.87e9,
                        suffix = 'Hz',
                        siPrefix = True,
                        bounds = (950e3, 4.05e9),
                        dec = True,
                    ),
                },
                'phase': {
                    'display_text': 'phase: ',
                    'widget': SpinBox(
                        value = 0,
                        suffix = 'deg',
                        dec = True,
                    ),
                },
            },
            get_param_value_funs = {}
        )

        self.sg396_opacity_effects = []
        for i in range(5):
            self.sg396_opacity_effects.append(QGraphicsOpacityEffect())
            self.sg396_opacity_effects[i].setOpacity(0.3)

        self.modulation_opts = ["AM", "FM", "Phase",
                                 #"Sweep", "Pulse", "Blank", 
                                 "QAM"
                                 #, "CPM", "VSB"
                                 ]
        self.modulation_functions = ["sine", "ramp", "triangle", "square", "noise","external"]


        self.sg396_params_widget_2 = ParamsWidget(
            {
                'mod_toggle': {'display_text': 'mod_toggle: ',
                                        'widget': QCheckBox('mod_toggle')},
                
                'mod_type': {'display_text': 'mod_type: ',
                                        'widget': ComboBox(items = self.modulation_opts)},
                
                'mod_func': {'display_text': 'mod_func: ',
                                        'widget': ComboBox(items = self.modulation_functions)},
                
                'mod_rate': {'display_text': 'mod_rate: ',
                                        'widget': SpinBox(value = 1000, suffix = 'Hz', bounds = (1e-6, 50e3), siPrefix = True)},
                
                'AM_mod': {'display_text': 'AM_mod: ',
                                        'widget': SpinBox(value = 100,  suffix = '%')},
                'FM_mod': {'display_text': 'FM_mod: ',
                                        'widget': SpinBox(value = 6e6,  suffix = 'Hz', siPrefix = True, dec = True)},

            },
            get_param_value_funs = {ComboBox: self.get_combobox_val}
        )

        # Set the default value for 'mod_func' to "external"
        mod_func_combobox = self.sg396_params_widget_2.widgets['mod_func']
        mod_func_combobox.setCurrentText("external")
        mod_func_combobox = self.sg396_params_widget_2.widgets['mod_type']
        mod_func_combobox.setCurrentText("QAM")

        self.sg396_status_label = QLabel(f"SRS SG396 status: ")
        self.sg396_status_label.setStyleSheet("color: white; background-color: black; border: 4px solid black;")
        self.sg396_status_label.setFixedHeight(40)

        self.sg396_emit_button = QPushButton("Emit")
        self.sg396_emit_button.clicked.connect(lambda:self.sg396_emit_button_clicked())

        self.sg396_stop_button = QPushButton("Stop")
        self.sg396_stop_button.clicked.connect(lambda:self.sg396_stop_button_clicked())
        
        self.sg396_params_widget_1.setEnabled(False)
        self.sg396_params_widget_2.setEnabled(False)
        self.sg396_status_label.setEnabled(False)
        self.sg396_emit_button.setEnabled(False)
        self.sg396_stop_button.setEnabled(False)

        self.sg396_params_widget_1.setGraphicsEffect(self.sg396_opacity_effects[0])
        self.sg396_params_widget_2.setGraphicsEffect(self.sg396_opacity_effects[1])
        self.sg396_status_label.setGraphicsEffect(self.sg396_opacity_effects[2])
        self.sg396_emit_button.setGraphicsEffect(self.sg396_opacity_effects[3])
        self.sg396_stop_button.setGraphicsEffect(self.sg396_opacity_effects[4])


    def init_xyz_control(self):

        self.xyz_label= QLabel("XYZ Control")
        self.xyz_label.setFixedHeight(20)
        self.xyz_label.setStyleSheet("font-weight: bold") 
        class AxisControl:
            def __init__(self, name):
                self.name = name  # either 'x' or 'y'
                #NEEDS CHANGE
                if xyz_activation_boolean:
                    with InstrumentManager() as mgr:
                        self.name = name.lower()
                        self.value = mgr.XYZcontrols.axes[name].position
                else: 
                    self.value=0
                self.step = 1
                self.suffix="nm"
                
                if xyz_activation_boolean:
                    with InstrumentManager() as mgr:
                        self.min = mgr.XYZcontrols.axes[name].limits[0]
                        self.max = mgr.XYZcontrols.axes[name].limits[1]
                else: 
                    self.max=1000
                    self.min=0

                
                # Create and configure title label
                self.title = QLabel(f"{name.upper()}:")
                self.title.setFixedHeight(20)
                self.title.setStyleSheet("font-weight: bold")
                
                # Create the spinbox for this axis
                self.spinbox = SpinBox()
                self.spinbox.setFont(QFont("Sanserif", 15))
                self.spinbox.setFixedWidth(160)
                self.spinbox.setRange(0, 1e6)
                self.update_spinbox()
                self.spinbox.editingFinished.connect(lambda: self.update_value())
                #self.spinbox.editingFinished.connect(lambda: self.update_value())
                
                # Create the change label (QLineEdit)
                self.step_label = QLineEdit("0")
                self.step_label.setFont(QFont("Sanserif", 15))
                self.step_label.setFixedWidth(160)
                self.edit_step_label()
                self.step_label.editingFinished.connect(lambda: self.edit_step_value())

                
                

            def update_value(self):
                text= self.spinbox.text().strip()
                try:
                    if text[-2:] == "nm":
                        val_text = text[:-2].strip()
                        self.value = float(val_text) * 1e-3
                    elif text[-2:] == "um":
                        val_text = text[:-2].strip()
                        self.value = float(val_text)
                    else:
                        # In this branch, if converting to float fails, we raise an error.
                        self.value = float(text)
                
                    self.update_spinbox()
                except ValueError as e:
                    raise ValueError(f"Invalid input '{text}': cannot convert to float. Please enter a number with an optional unit 'nm' or 'um'.") from e
                # if self.spinbox.text == "nm":
                #     self.value= self.spinbox.value() * 1e-3
                # else:
                #     self.value= self.spinbox.value()
                # self.update_spinbox()
                # Update the real value label when the spinbox value changes
            
            def update_spinbox(self, change=False):

                if self.value >= 1:# Show 3 decimal places
                    self.spinbox.setDecimals(7)
                    self.spinbox.setValue(self.value)
                    self.spinbox.setSuffix("um")
                    self.spinbox.setSingleStep(self.step)
                    self.spinbox.setMaximum(self.max)
                    self.spinbox.setMinimum(self.min)
                
                else:
                    self.spinbox.setMaximum(self.max * 1e3)
                    self.spinbox.setMinimum(self.min * 1e3)
                    self.spinbox.setValue(self.value * 1e3)
                    self.spinbox.setSuffix("nm")
                    self.spinbox.setSingleStep(self.step * 1e3)
                    self.spinbox.setDecimals(5)
            


            def edit_step_value(self):
                text = self.step_label.text().strip()
                try:
                    if text[-2:] == "nm":
                        val_text = text[:-2].strip()
                        self.step = float(val_text) * 1e-3
                    elif text[-2:] == "um":
                        val_text = text[:-2].strip()
                        self.step = float(val_text)
                    else:
                        # In this branch, if converting to float fails, we raise an error.
                        self.step = float(text)
                except ValueError as e:
                    raise ValueError(f"Invalid input '{text}': cannot convert to float. Please enter a number with an optional unit 'nm' or 'um'.") from e

                self.update_spinbox()
                self.edit_step_label()

            ### interval for the change value
            def edit_step_label(self):
                if self.step < 1:
                    self.step_label.setText(f"{self.step * 1e3:.1f} nm")
                else:
                    self.step_label.setText(f"{self.step:.3f} um")
            ###

            def change_unit_function(self):
                self.update_spinbox(True)


            
            

                

        self.x_control = AxisControl("X")
        self.y_control = AxisControl("Y")
        self.z_control = AxisControl("Z")
        if xyz_activation_boolean:
            with InstrumentManager() as mgr:
                self.x_control.spinbox.editingFinished.connect(lambda: mgr.XYZcontrol.move_x(self.x_control.value))
                self.y_control.spinbox.editingFinished.connect(lambda: mgr.XYZcontrol.move_y(self.y_control.value))
                self.z_control.spinbox.editingFinished.connect(lambda: mgr.XYZcontrol.move_z(self.z_control.value))

        # with InstrumentManager() as mgr:
        #     mgr.XYZcontrols.initialize()
        #     self.x_control.spinbox.valueChanged.valueChanged(lambda:mgr.XYZcontrols.x_move(self.x_control.value))
        #     self.y_control.spinbox.valueChanged.valueChanged(lambda:mgr.XYZcontrols.y_move(self.y_control.value))
        #     self.z_control.spinbox.valueChanged.valueChanged(lambda:mgr.XYZcontrols.z_move(self.z_control.value))    



        
    '''
    LAYOUT -----------------------------------------------------------------------------------------------------------------------------------------------
    '''

    def layouts(self):
        '''
       
         GUI Layout Structure
        '''

        
        
        self.sg396_frame = QFrame(self)
        self.sg396_frame.setStyleSheet("background-color: #2b2b2b")
        self.sg396_layout = QGridLayout(self.sg396_frame)
        self.sg396_layout.setSpacing(0)
        self.sg396_layout.addWidget(self.sg396_label,1,1,1,2)
        self.sg396_layout.addWidget(self.sg396_checkbox,2,1,1,2)
        self.sg396_layout.addWidget(self.sg396_params_widget_1,3,1,1,1)
        self.sg396_layout.addWidget(self.sg396_params_widget_2,3,2,1,1)
        self.sg396_layout.addWidget(self.sg396_status_label,4,1,1,2)
        self.sg396_layout.addWidget(self.sg396_emit_button,5,1,1,1)
        self.sg396_layout.addWidget(self.sg396_stop_button,5,2,1,1)


        self.pulse_grid_layout = QGridLayout()
        self.pulse_grid_layout.setSpacing(0)


        self.xyz_frame = QFrame(self)
        self.xyz_frame.setStyleSheet("background-color: #454545")
        self.xyz_layout = QGridLayout(self.xyz_frame)
        self.xyz_layout.setSpacing(10)
        self.xyz_layout.addWidget(self.xyz_label,1,1,1,1)
        self.xyz_layout.addWidget(self.x_control.title,2,1,1,1)
        self.xyz_layout.addWidget(self.x_control.spinbox,2,2,1,1)
        self.xyz_layout.addWidget(self.x_control.step_label,2,3,1,1)

        self.xyz_layout.addWidget(self.y_control.title,4,1,1,1)
        self.xyz_layout.addWidget(self.y_control.spinbox,4,2,1,1)
        self.xyz_layout.addWidget(self.y_control.step_label,4,3,1,1)

        self.xyz_layout.addWidget(self.z_control.title,6,1,1,1)
        self.xyz_layout.addWidget(self.z_control.spinbox,6,2,1,1)
        self.xyz_layout.addWidget(self.z_control.step_label,6,3,1,1)




       


        # self.gui_layout.addLayout(self.DLnsec_layout)

        self.main_grid_layout = QGridLayout()  
        self.main_grid_layout.addWidget(self.sg396_frame, 0, 0)  # Row 0, Column 0  
        self.main_grid_layout.addWidget(self.xyz_frame, 1, 0)    # Row 1, Column 0 (below pulse_frame)  
        self.setLayout(self.main_grid_layout)  
    

    '''
    INTERACTIVE WIDGET FUNCTIONS
    '''
    

    def get_combobox_val(self, combobox):
        return str(combobox.value())
    
    
    '''
    INTERACTIVE WIDGET FUNCTIONS
    '''

    # output sg396 frequency without sideband modulation
    # def sg396_emit_button_clicked(self):
    #     with InstrumentManager() as mgr:
    #         fun_kwargs = dict(**self.sg396_params_widget_1.all_params(), **self.sg396_params_widget_2.all_params())
    #         # print("power to emit:", fun_kwargs['RF_Power'])
    #         # print("freq to emit: ", fun_kwargs['RF_Frequency'])
    #         mgr.sg.set_frequency(fun_kwargs['RF_Frequency'])
    #         mgr.sg.set_rf_amplitude(fun_kwargs['RF_Power'])
    #         mgr.sg.set_mod_type('QAM')
    #         mgr.sg.set_mod_toggle(1)
    #         mgr.sg.set_rf_toggle(1)
    #         mgr.sg.set_mod_function('external')

    def sg396_checked(self, box):
        if box.isChecked() == True:
            self.sg396_params_widget_1.setEnabled(True)
            self.sg396_params_widget_2.setEnabled(True)
            self.sg396_status_label.setEnabled(True)
            self.sg396_emit_button.setEnabled(True)
            self.sg396_stop_button.setEnabled(True)
            [self.sg396_opacity_effects[i].setEnabled(False) for i in range(5)]
        


        else:
            self.sg396_params_widget_1.setEnabled(False)
            self.sg396_params_widget_2.setEnabled(False)
            self.sg396_status_label.setEnabled(False)
            self.sg396_emit_button.setEnabled(False)
            self.sg396_stop_button.setEnabled(False)
            [self.sg396_opacity_effects[i].setEnabled(True) for i in range(5)]


    
    def sg396_emit_button_clicked(self):
        with InstrumentManager() as mgr:
            sig_gen = mgr.sg

            fun_kwargs = dict(**self.sg396_params_widget_1.all_params(), **self.sg396_params_widget_2.all_params())

            sig_gen.set_frequency(fun_kwargs['rf_frequency'])
            sig_gen.set_rf_amplitude(fun_kwargs['rf_amplitude'])
            pwr = float(sig_gen.get_rf_amplitude())
            freq = float(sig_gen.get_frequency())

            sig_gen.set_phase(fun_kwargs['phase'])
            sig_gen.set_mod_toggle(fun_kwargs['mod_toggle'])
            if fun_kwargs['mod_toggle']:
                sig_gen.set_mod_type(fun_kwargs['mod_type'])
                sig_gen.set_mod_function(fun_kwargs['mod_type'],fun_kwargs['mod_func'])
                sig_gen.set_mod_rate(fun_kwargs['mod_rate'])
                sig_gen.set_AM_mod_depth(fun_kwargs['AM_mod'])
                sig_gen.set_FM_mod_dev(fun_kwargs['FM_mod'])

                sig_gen.set_mod_coupling(1) # Assuming DC input
            
            sig_gen.set_rf_toggle(1) 
            print('rf_toggle: ',sig_gen.get_rf_toggle())
            print('mod_type: ',sig_gen.get_mod_type())
            print('mod_func: ',sig_gen.get_mod_function())
            print('AM_depth: ',sig_gen.get_AM_mod_depth())
            print('FM_dev: ',sig_gen.get_FM_mod_dev())
            
            self.sg396_status_label.setStyleSheet("color: black; background-color: gold; border: 4px solid black;")
            self.sg396_status_label.setText(f"SRS SG396 Status: ON ({freq*1e-9} GHz at {pwr} dBm)")
            
    def sg396_stop_button_clicked(self):
        with InstrumentManager() as mgr:
            mgr.sg.set_rf_toggle(0)
            mgr.sg.set_mod_toggle(0)

            self.sg396_status_label.setStyleSheet("color: white; background-color: black; border: 4px solid black;")
            self.sg396_status_label.setText("SRS SG396 Status: OFF")
    




    # def kill_process(self):
    #     """Stop the run process."""
    #     self.run_proc.kill()

