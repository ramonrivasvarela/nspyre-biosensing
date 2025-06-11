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

import logging


logger = logging.getLogger(__name__)

class InstWidget(QWidget):
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

        self.init_DLnsec_widgets()
        self.init_pulse_control()
        
        
  


        self.layouts()

   

    '''
    CREATE WIDGETS -----------------------------------------------------------------------------------------------------------------------------------------------
    '''

    def init_DLnsec_widgets(self):
        self.DLnsec_label = QLabel("DLnsec")
        self.DLnsec_label.setFixedHeight(20)
        self.DLnsec_label.setStyleSheet("font-weight: bold")

        self.DLnsec_b1 = QRadioButton("ON")
        self.DLnsec_b1.toggled.connect(lambda:self.toggle_DLnsec(self.DLnsec_b1))
            
        self.DLnsec_b2 = QRadioButton("OFF")
        self.DLnsec_b2.setChecked(True)
        self.DLnsec_b2.toggled.connect(lambda:self.toggle_DLnsec(self.DLnsec_b2))

        self.LAS_button = QPushButton("LAS") # CW mode operation
        self.LAS_button.clicked.connect(lambda:self.DLnsec_mode("LAS"))

        

        self.EXT_button = QPushButton("EXT") # External trigger operation
        self.EXT_button.clicked.connect(lambda:self.DLnsec_mode("EXT"))

        self.RBT_button = QPushButton("Reboot") # External trigger operation
        self.RBT_button.clicked.connect(lambda:self.DLnsec_reboot())

    
        self.DLnsec_pwr_slider = QSlider()
        self.DLnsec_pwr_slider.setOrientation(Qt.Orientation.Horizontal)
        self.DLnsec_pwr_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.DLnsec_pwr_slider.setTickInterval(1)
        self.DLnsec_pwr_slider.setMinimum(0)
        self.DLnsec_pwr_slider.setMaximum(100)
        self.DLnsec_pwr_slider.sliderReleased.connect(lambda: self.DLnsec_pwr_changed())
        self.DLnsec_pwr_slider.setValue(0)
        self.DLnsec_pwr_slider.setFixedWidth(320)
        # VALUE of laser power (in units of % diode current)
        self.DLnsec_pwr = self.DLnsec_pwr_slider.value()

        self.DLnsec_pwr_label = QLineEdit("0%")
        self.DLnsec_pwr_label.setFont(QFont("Sanserif", 15))
        self.DLnsec_pwr_label.setFixedWidth(80)
        self.DLnsec_pwr_label.editingFinished.connect(lambda: self.DLnsec_pwr_text_changed())
        self.DLnsec_pwr_label.setStyleSheet("""
            QLineEdit:hover {
                background-color: powderblue; /* Background color when hovered */
            }
        """)

        self.DLnsec_status_label = QLabel("")
        self.DLnsec_status_label.setStyleSheet("color: white; background-color: black; border: 4px solid black;")
        self.DLnsec_status_label.setFixedHeight(40)
        try:
            self.DLnsec_mode("EXT")
        except:
            print('could not set DLnsec mode to EXT')
    
    def init_pulse_control(self):
        self.green_laser_label = QLabel("Green Laser Control")
        self.green_laser_label.setFixedHeight(20)
        self.green_laser_label.setStyleSheet("font-weight: bold")

        self.green_laser_on = QRadioButton("ON")
        #self.green_laser_on.toggled.connect(lambda:self.green_laser_toggle(self.green_laser_on))
            
        self.green_laser_off = QRadioButton("OFF")
        self.green_laser_off.setChecked(True)
        #self.green_laser_off.toggled.connect(lambda:self.blue_laser_toggle(self.green_laser_off))

        self.blue_laser_label = QLabel("488nm Laser Control")
        self.blue_laser_label.setFixedHeight(20)
        self.blue_laser_label.setStyleSheet("font-weight: bold")

        self.blue_laser_on = QRadioButton("ON")
            
        self.blue_laser_off = QRadioButton("OFF")


        self.green_laser_group = QButtonGroup(self)
        self.green_laser_group.addButton(self.green_laser_on)   # ON
        self.green_laser_group.addButton(self.green_laser_off)  # OFF
        self.green_laser_off.setChecked(True)  # Default OFF state

        # Blue Laser Group (ON and OFF are exclusive)
        self.blue_laser_group = QButtonGroup(self)
        self.blue_laser_group.addButton(self.blue_laser_on)   # ON
        self.blue_laser_group.addButton(self.blue_laser_off)  # OFF
        self.blue_laser_off.setChecked(True)

        self.green_laser_on.toggled.connect(lambda:self.change_experiment_state())
        self.blue_laser_on.toggled.connect(lambda:self.change_experiment_state())

        self.label= QLabel("Analog Control")
        self.label.setFixedHeight(20)
        self.label.setStyleSheet("font-weight: bold")

        with InstrumentManager() as mgr:
            mgr.dr_ps.set_state_off()

        # with InstrumentManager() as mgr:
        #     mgr.dr_ps.set_state_off()
        #ANALOG SLIDERS
        class Analogs:
            def __init__(self, analog_name):
                self.slider = QSlider()
                self.slider.setOrientation(Qt.Orientation.Horizontal)
                self.slider.setTickPosition(QSlider.TickPosition.TicksBelow)
                self.slider.setTickInterval(1)
                self.slider.setMinimum(0)
                self.slider.setMaximum(100)
                #self.slider.valueChanged.connect(lambda: self.value_changed())
                #self.slider.sliderReleased.connect(lambda: self.change_experiment_state())
                self.slider.setValue(50)
                self.slider.setFixedWidth(320)
        # VALUE of laser power (in units of % diode current)
                self.value = 0
                self.label = QLineEdit("0.00")
                self.label.setFont(QFont("Sanserif", 15))
                self.label.setFixedWidth(80)
                #self.label.editingFinished.connect(lambda: self.value_text_changed())
                self.label.setStyleSheet("""
                    QLineEdit:hover {
                        background-color: powderblue; /* Background color when hovered */
                    }
                """)

            def value_changed(self):
                self.value = (self.slider.value()-50)/50
                self.label.setText(str(self.value))
                    #with InstrumentManager() as mgr:
                    #    mgr.DLnsec.power_settings(self.DLnsec_pwr)
                
            def text_changed(self): # Makes sure text is valid, then sends off the value to the slider
                text = self.label.text()
                val=float(text)
                if -1 <= val <= 1:
                    self.label.setText(f"{val:.2f}")
                    self.slider.setValue(int((val+1)*50))
                elif text == "":
                    self.label.setText("0.00")
                    self.slider.setValue(0)
                else:
                    self.label.setText(f"{self.value:.2f}")
                    print("Invalid input, please enter a number from -1 to 1")
                self.value = self.slider.value()

        self.q_analog = Analogs("Q")
        self.i_analog = Analogs("I")

        self.q_analog.slider.valueChanged.connect(lambda: self.q_analog.value_changed())
        self.q_analog.slider.sliderReleased.connect(lambda: self.change_experiment_state())
        self.q_analog.label.editingFinished.connect(lambda: self.q_analog.text_changed())
        self.q_analog.label.editingFinished.connect(lambda: self.change_experiment_state())
        self.i_analog.slider.valueChanged.connect(lambda: self.i_analog.value_changed())
        self.i_analog.slider.sliderReleased.connect(lambda: self.change_experiment_state())
        self.i_analog.label.editingFinished.connect(lambda: self.i_analog.text_changed())
        self.i_analog.label.editingFinished.connect(lambda: self.change_experiment_state())
        self.reset_button=QPushButton("Stop")
        self.reset_button.clicked.connect(lambda:self.reset_function())


    
        
        self.mirror_label = QLabel("Mirror Control")
        self.mirror_label.setFixedHeight(20)
        self.mirror_label.setStyleSheet("font-weight: bold")

        self.mirror_button = QPushButton("Down")
        #self.mirror_button.setCheckable(True)
        self.mirror_style_boolean=False
        self.mirror_button.setStyleSheet("color: red; background-color: lightgray;")
        self.mirror_button.clicked.connect(lambda:self.flip_mirror_leave_laser_on())

        self.switch_button = QPushButton("Switch")
        self.switch_button.clicked.connect(lambda:self.change_button_style())

        self.mirror_boolean=False
        self.blue_laser_boolean=False
        self.green_laser_boolean=False

    

    


        
    '''
    LAYOUT -----------------------------------------------------------------------------------------------------------------------------------------------
    '''

    def layouts(self):
        '''
        GUI Layout Structure
        '''
        self.gui_layout = QVBoxLayout()

        
        self.DLnsec_frame = QFrame(self)
        self.DLnsec_frame.setStyleSheet("background-color: #454545")
        self.DLnsec_layout = QGridLayout(self.DLnsec_frame)
        self.DLnsec_layout.setSpacing(10)
        self.DLnsec_layout.addWidget(self.DLnsec_label,1,1,1,1)
        self.DLnsec_layout.addWidget(self.DLnsec_b1,2,1,1,1)
        self.DLnsec_layout.addWidget(self.DLnsec_b2,2,2,1,1)
        self.DLnsec_layout.addWidget(self.LAS_button,4,1,1,1)
        self.DLnsec_layout.addWidget(self.EXT_button,5,1,1,1)
        self.DLnsec_layout.addWidget(self.DLnsec_pwr_slider,3,2,1,2)
        self.DLnsec_layout.addWidget(self.DLnsec_pwr_label,3,1,1,1)
        self.DLnsec_layout.addWidget(self.DLnsec_status_label,6,1,1,1)
        self.DLnsec_layout.addWidget(self.RBT_button,7,1,1,1)

        
        


        self.pulse_frame = QFrame(self)
        self.pulse_frame.setStyleSheet("background-color: #454545")
        self.pulse_layout = QGridLayout(self.pulse_frame)
        self.pulse_layout.setSpacing(10)

        self.pulse_layout.addWidget(self.green_laser_label,1,1,1,1)
        self.pulse_layout.addWidget(self.green_laser_on,2,1,1,1)
        self.pulse_layout.addWidget(self.green_laser_off,2,2,1,1)
        self.pulse_layout.addWidget(self.blue_laser_label,3,1,1,1)
        self.pulse_layout.addWidget(self.blue_laser_on,4,1,1,1)
        self.pulse_layout.addWidget(self.blue_laser_off,4,2,1,1)

        self.pulse_layout.addWidget(self.mirror_label,5,1,1,1)
        self.pulse_layout.addWidget(self.mirror_button,6,1,1,1)
        self.pulse_layout.addWidget(self.switch_button,6,2,1,1) 
        self.pulse_layout.addWidget(self.label,7,1,1,1)      

        self.pulse_layout.addWidget(self.i_analog.slider,8,2,1,2)
        self.pulse_layout.addWidget(self.i_analog.label,8,1,1,1) 
        self.pulse_layout.addWidget(self.q_analog.slider,9,2,1,2)
        self.pulse_layout.addWidget(self.q_analog.label,9,1,1,1) 
        self.pulse_layout.addWidget(self.reset_button,10,1,1,1)
        

        self.sig_gens_layout = QGridLayout()
        self.sig_gens_layout.setSpacing(0)

        self.sig_gens_layout.addWidget(self.pulse_frame,1,1,1,1)

        


       

        self.other_widgets_layout = QHBoxLayout()
        self.other_widgets_layout.addWidget(self.DLnsec_frame)
        self.gui_layout.addLayout(self.other_widgets_layout)

        # self.gui_layout.addLayout(self.DLnsec_layout)

        self.setLayout(self.gui_layout)
        self.gui_layout.addLayout(self.sig_gens_layout)
    

    '''
    INTERACTIVE WIDGET FUNCTIONS
    '''
    def toggle_DLnsec(self, b):
        with InstrumentManager() as mgr:

            match b.text():
                case 'ON':
                    if b.isChecked() == True:
                        mgr.DLnsec.on()
                    else:
                        mgr.DLnsec.off()
                case 'OFF':
                    if b.isChecked() == True:
                       mgr.DLnsec.off()
                    else:
                        mgr.DLnsec.on()

    def DLnsec_mode(self, mode):
        with InstrumentManager() as mgr:
            if mode == "LAS":
                mgr.DLnsec.LAS()
                self.DLnsec_status_label.setText("Trigger: LAS")
            elif mode == "EXT":
                mgr.DLnsec.EXT()
                self.DLnsec_status_label.setText("Trigger: EXT")
    
    def DLnsec_pwr_changed(self):
        self.DLnsec_pwr = self.DLnsec_pwr_slider.value()
        self.DLnsec_pwr_label.setText(str(self.DLnsec_pwr) + "%")
        with InstrumentManager() as mgr:
            mgr.DLnsec.power_settings(self.DLnsec_pwr)

    def DLnsec_pwr_text_changed(self): # Makes sure text is valid, then sends off the value to the slider
        text = self.DLnsec_pwr_label.text()
        if text[-1] == '%':
            text = text[:-1] #text is purely the numeric value now
        if text.isnumeric():
            self.DLnsec_pwr_label.setText(text + "%")
            self.DLnsec_pwr_slider.setValue(int(text))
        elif text == "":
            self.DLnsec_pwr_label.setText("0%")
            self.DLnsec_pwr_slider.setValue(0)
        else:
            self.DLnsec_pwr_label.setText(f"{self.DLnsec_pwr}%")
            print("Invalid input, please enter a number")
        
        self.DLnsec_pwr = self.DLnsec_pwr_slider.value()
        with InstrumentManager() as mgr:
            mgr.DLnsec.power_settings(self.DLnsec_pwr)
        
    
    def DLnsec_reboot(self):
        with InstrumentManager() as mgr:
            mgr.DLnsec.reboot()



    def get_combobox_val(self, combobox):
        return str(combobox.value())
    


    

    def change_experiment_state(self): 
        with InstrumentManager() as mgr:
            dig_chan=[]
            if self.green_laser_on.isChecked():
                dig_chan.append(7)
            if self.blue_laser_on.isChecked():
                dig_chan.append(3)
            mgr.dr_ps.set_state(dig_chan, self.i_analog.value, self.q_analog.value)
    
    
    

        
    
    def change_button_style(self):
        self.mirror_style_boolean = not self.mirror_style_boolean
        if self.mirror_style_boolean:
            self.mirror_button.setStyleSheet("color: green; background-color: lightgray;")
            self.mirror_button.setText("Up")
        else:
            self.mirror_button.setStyleSheet("color: red; background-color: lightgray;")
            self.mirror_button.setText("Down")
    
    def flip_mirror(self):
        self.mirror_boolean=not self.mirror_boolean
        with InstrumentManager() as mgr:
            mgr.dr_ps.flip_mirror()
        self.change_button_style()
        self.green_laser_off.setChecked(True)
        self.blue_laser_off.setChecked(True)

    def flip_mirror_leave_laser_on(self):
        self.change_button_style()
        dig_chan=[]
        if self.green_laser_on.isChecked():
            dig_chan.append(7)
        if self.blue_laser_on.isChecked():
            dig_chan.append(3)
        with InstrumentManager() as mgr:
            mgr.dr_ps.flip_mirror(dig_chan, self.i_analog.value, self.q_analog.value)

            
    

    def reset_function(self):
        with InstrumentManager() as mgr:
            self.q_analog.slider.setValue(50)
            self.i_analog.slider.setValue(50)
            self.green_laser_off.setChecked(True)
            self.blue_laser_off.setChecked(True)
            # self.q_analog.label.setText("0.00")
            # self.i_analog.label.setText("0.00")
            # mgr.dr_ps.set_state_off()
            
    def closeEvent(self, event):
        with InstrumentManager() as mgr:
            self.reset_function()
        if event:
            event.accept()
    
    


        


    #def init_laser_widgets(self):
    #     self.laser_label = QLabel("Laser")
    #     self.laser_label.setFixedHeight(20)
    #     self.laser_label.setStyleSheet("font-weight: bold")

    #     self.laser_b1 = QRadioButton("CW ON")
    #     self.laser_b1.toggled.connect(lambda:self.toggle_laser(self.laser_b1))
            
    #     self.laser_b2 = QRadioButton("CW OFF")
    #     self.laser_b2.setChecked(True)
    #     self.laser_b2.toggled.connect(lambda:self.toggle_laser(self.laser_b2))
    
    #     self.laser_power_slider = QSlider()
    #     self.laser_power_slider.setOrientation(Qt.Orientation.Horizontal)
    #     # self.laser_power_slider.setTickPosition(QSlider.TicksBelow)
    #     self.laser_power_slider.setTickInterval(1)
    #     self.laser_power_slider.setMinimum(0)
    #     self.laser_power_slider.setMaximum(110)
    #     self.laser_power_slider.valueChanged.connect(lambda: self.laser_power_changed())
    #     self.laser_power_slider.setValue(0)
    #     # VALUE of laser power (in units of % diode current)
    #     self.laser_power = self.laser_power_slider.value()

    #     self.laser_power_label = QLabel("")
    #     self.laser_power_label.setFont(QFont("Sanserif", 15))

    #     self.laser_shutter_button = QPushButton("Open laser shutter")
    #     self.laser_shutter_button.clicked.connect(lambda: self.laser_shutter_status_changed())

    #     self.pickoff_shutter_button = QPushButton("Open laser pickoff shutter")
    #     self.pickoff_shutter_button.clicked.connect(lambda: self.pickoff_shutter_status_changed())

    #     self.laser_status_label = QLabel("Laser status")
    #     self.laser_status_label.setStyleSheet("color: white; background-color: black; border: 4px solid black;")
    #     self.laser_status_label.setFixedHeight(40)

    #     self.pickoff_status_label = QLabel("Laser pickoff status")
    #     self.pickoff_status_label.setStyleSheet("color: white; background-color: black; border: 4px solid black;")
    #     self.pickoff_status_label.setFixedHeight(40)

    # def init_flipper_widgets(self):
    #     self.flipper_label = QLabel("Flip Mirror")
    #     self.flipper_label.setFixedHeight(20)
    #     self.flipper_label.setStyleSheet("font-weight: bold")

    #     self.flipper_b1 = QRadioButton("APD")
    #     self.flipper_b1.toggled.connect(lambda:self.toggle_flipper(self.flipper_b1))

    #     self.flipper_b2 = QRadioButton("BPD")
    #     self.flipper_b2.toggled.connect(lambda:self.toggle_flipper(self.flipper_b2))

    #     self.flipper_b3 = QRadioButton("PMT")
    #     self.flipper_b3.toggled.connect(lambda:self.toggle_flipper(self.flipper_b3))

    # def init_nd_filter_widgets(self):
    #     self.nd_filter_label = QLabel("BPD ND Filter")
    #     self.nd_filter_label.setFixedHeight(20)
    #     self.nd_filter_label.setStyleSheet("font-weight: bold")
        
    #     self.nd_filter_opts = QComboBox()
    #     self.nd_filter_opts.addItems(["None", "0.5", "1", "2", "3", "4"])
    #     self.nd_filter_opts.currentIndexChanged.connect(lambda: self.nd_filter_changed())

    # def init_pmt_shutter_widgets(self):
    #     self.pmt_shutter_label = QLabel("PMT Shutter")
    #     self.pmt_shutter_label.setFixedHeight(20)
    #     self.pmt_shutter_label.setStyleSheet("font-weight: bold")

    #     self.pmt_shutter_button = QPushButton("Open PMT shutter")
    #     self.pmt_shutter_button.clicked.connect(lambda: self.pmt_shutter_status_changed())

    
    
    


