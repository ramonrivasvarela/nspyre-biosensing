from PyQt6.QtWidgets import QWidget, QFrame, QGridLayout, QPushButton, QLabel, QComboBox, QSpinBox
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt
from nspyre import InstrumentManager
from special_widgets.unit_widgets import SecLineEdit, TemperatureLineEdit
import time
import numpy as np

class CameraWidget(QWidget):
    """
    Camera control widget extracted from Instrument GUI.
    """
    def __init__(self, font: str = "Arial"):
        super().__init__()
        self.font = font
        self.camera_on = False
        self.camera = InstrumentManager().Camera

        self.init_widgets()
        self.create_layout()

        # self.check_power_status()
        # self.check_temperature_status()
        # self.check_cooler_status()

        self.refresh_camera_settings()

    def init_widgets(self):
        # Power button
        self.power_button = QPushButton("Power")
        self.power_button.setFixedHeight(30)
        self.power_button.clicked.connect(self.power_button_clicked)

        # Trigger mode
        self.trigger_label = QLabel("Trigger Modes:")
        self.trigger_label.setFixedHeight(20)
        self.trigger_label.setStyleSheet("font-weight: bold")
        self.trigger_combo = QComboBox()
        self.trigger_combo.addItems(["internal", "external", "external exposure bulb"])
        self.trigger_combo.setCurrentText("internal")
        self.trigger_combo.setStyleSheet("QComboBox { background-color: #2b2b2b; color: white; }")
        self.trigger_combo.setFixedHeight(30)
        self.trigger_combo.setFont(QFont(self.font, 12))
        self.trigger_combo.currentTextChanged.connect(lambda t: self.camera.set_trigger_mode(t))

        # Exposure time
        self.exp_label = QLabel("Exposure Time:")
        self.exp_label.setFixedHeight(20)
        self.exp_label.setStyleSheet("font-weight: bold")
        self.exp_input = SecLineEdit(75e-3)
        self.exp_input.editingFinished.connect(lambda: self.camera.set_exposure_time(self.exp_input.secvalue))

        # Shutter
        self.shutter_label = QLabel("Shutter:")
        self.shutter_label.setFixedHeight(20)
        self.shutter_label.setStyleSheet("font-weight: bold")
        self.shutter_combo = QComboBox()
        self.shutter_combo.addItems(["closed", "open", "auto"])
        self.shutter_combo.setCurrentText("auto")
        self.shutter_combo.setStyleSheet("QComboBox { background-color: #2b2b2b; color: white; }")
        self.shutter_combo.setFixedHeight(30)
        self.shutter_combo.setFont(QFont(self.font, 12))
        self.shutter_combo.currentTextChanged.connect(lambda s: self.camera.set_shutter(s))

        # Frame Transfer Mode
        self.frame_transfer_label = QLabel("Frame Transfer Mode:")
        self.frame_transfer_label.setFixedHeight(20)
        self.frame_transfer_label.setStyleSheet("font-weight: bold")
        self.frame_transfer_combo = QComboBox()
        self.frame_transfer_combo.addItems(["frame transfer", "conventional"])
        self.frame_transfer_combo.setCurrentText(self.camera.frame_transfer_mode)
        self.frame_transfer_combo.setStyleSheet("QComboBox { background-color: #2b2b2b; color: white; }")
        self.frame_transfer_combo.setFixedHeight(30)
        self.frame_transfer_combo.setFont(QFont(self.font, 12))
        self.frame_transfer_combo.currentTextChanged.connect(lambda mode: self.camera.set_frame_transfer_mode(mode))

        #Gain
        self.gain_label = QLabel("Gain:")
        self.gain_label.setFixedHeight(20)
        self.gain_label.setStyleSheet("font-weight: bold")
        self.gain_sb=QSpinBox()
        self.gain_sb.setRange(0, 255)  # Example range, adjust as needed
        self.gain_sb.editingFinished.connect(lambda: self.camera.set_emccdgain(self.gain_sb.value()))
        

        # Temperature
        self.temp_label = QLabel("Temperature:")
        self.temp_label.setFixedHeight(20)
        self.temp_label.setStyleSheet("font-weight: bold")
        self.temp_input = TemperatureLineEdit(value=0, max=100, min=-100)
        self.temp_input.editingFinished.connect(lambda: self.check_temperature_status())

        # Cooling
        self.cool_input = TemperatureLineEdit(18, max=20, min=-100, asinteger=True)
        self.cool_button = QPushButton("Cool To:")
        self.cool_button.clicked.connect(lambda:self.cool_button_clicked())

        # Read mode
        self.read_mode_label = QLabel("Read Mode:")
        self.read_mode_label.setFixedHeight(20)
        self.read_mode_label.setStyleSheet("font-weight: bold")
        self.read_mode_combo = QComboBox()
        self.read_mode_combo.addItems([
            "full vertical binning",
            "multi track",
            "random track",
            "single track",
            "image"
        ])
        self.read_mode_combo.setCurrentText(self.camera.read_mode)
        self.read_mode_combo.currentTextChanged.connect(lambda m: self.camera.set_read_mode(m))

        # Acquisition mode
        self.acq_mode_label = QLabel("Acquisition Mode:")
        self.acq_mode_label.setFixedHeight(20)
        self.acq_mode_label.setStyleSheet("font-weight: bold")
        self.acq_mode_combo = QComboBox()
        self.acq_mode_combo.addItems([
            "single scan",
            "accumulate",
            "kinetics",
            "fast kinetics",
            "run till abort"
        ])
        self.acq_mode_combo.setCurrentText(self.camera.acquisition_mode)
        self.acq_mode_combo.currentTextChanged.connect(lambda m: self.camera.set_acquisition_mode(m))

        # Number of accumulations
        self.acc_label = QLabel("Num. Accumulations:")
        self.acc_label.setFixedHeight(20)
        self.acc_label.setStyleSheet("font-weight: bold")
        self.acc_sb = QSpinBox()
        self.acc_sb.setRange(1, 1000)
        self.acc_sb.setValue(self.camera.number_accumulations)
        self.acc_sb.editingFinished.connect(lambda: self.camera.set_number_accumulations(self.acc_sb.value()))

        # Number of kinetics
        self.kinetics_label = QLabel("Num. Kinetics:")
        self.kinetics_label.setFixedHeight(20)
        self.kinetics_label.setStyleSheet("font-weight: bold")
        self.kinetics_sb = QSpinBox()
        self.kinetics_sb.setRange(1, 1000)
        self.kinetics_sb.setValue(self.camera.number_kinetics)
        self.kinetics_sb.editingFinished.connect(lambda: self.camera.set_number_kinetics(self.kinetics_sb.value()))

        # Refresh
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(lambda: self.refresh_camera_settings())
        self.set_button = QPushButton("Set")
        self.set_button.clicked.connect(lambda: self.set_button_clicked())
        self.cooler_status_button = QPushButton("Cooler OFF")
        self.cooler_status_button.clicked.connect(lambda: self.cooler_status_button_clicked())
    def create_layout(self):
        frame = QFrame(self)
        frame.setStyleSheet("background-color: #454545")
        layout = QGridLayout(frame)
        layout.setSpacing(10)

        layout.addWidget(self.power_button, 1, 1, 1, 1)
        layout.addWidget(self.trigger_label, 2, 1, 1, 1)
        layout.addWidget(self.trigger_combo, 2, 2, 1, 1)
        layout.addWidget(self.exp_label, 3, 1, 1, 1)
        layout.addWidget(self.exp_input, 3, 2, 1, 1)
        layout.addWidget(self.shutter_label, 4, 1, 1, 1)
        layout.addWidget(self.shutter_combo, 4, 2, 1, 1)
        layout.addWidget(self.gain_label, 5, 1, 1, 1)
        layout.addWidget(self.gain_sb, 5, 2, 1, 1)
        #layout.addWidget(self.optimize_gain_button, 5, 3, 1, 1)
        # Read and acquisition modes
        layout.addWidget(self.read_mode_label, 6, 1, 1, 1)
        layout.addWidget(self.read_mode_combo, 6, 2, 1, 1)
        layout.addWidget(self.acq_mode_label, 7, 1, 1, 1)
        layout.addWidget(self.acq_mode_combo, 7, 2, 1, 1)
        # Number controls
        layout.addWidget(self.acc_label, 8, 1, 1, 1)
        layout.addWidget(self.acc_sb, 8, 2, 1, 1)
        layout.addWidget(self.kinetics_label, 9, 1, 1, 1)
        layout.addWidget(self.kinetics_sb, 9, 2, 1, 1)

        layout.addWidget(self.frame_transfer_label, 10, 1, 1, 1)
        layout.addWidget(self.frame_transfer_combo, 10, 2, 1, 1)
        # Temperature and cooling
        # layout.addWidget(self.temp_label, 10, 1, 1, 1)
        layout.addWidget(self.temp_input, 11, 1, 1, 1)
        layout.addWidget(self.cool_input, 11, 3, 1, 1)
        layout.addWidget(self.cool_button, 11, 2, 1, 1)
        # Actions
        layout.addWidget(self.refresh_button, 12, 1, 1, 1)
        layout.addWidget(self.set_button, 12, 2, 1, 1)
        layout.addWidget(self.cooler_status_button, 12, 3, 1, 1)

        main_layout = QGridLayout(self)
        main_layout.addWidget(frame, 0, 0, 1, 1)
        self.setLayout(main_layout)

    def set_button_color(self, widget, color):
        widget.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                border: 2px solid #888;
            }}
            QPushButton:pressed {{
                background-color: #555;
            }}
        """)

    def power_button_clicked(self):
        status, _ = self.camera.get_status()
        # 20002 indicates success
        if status == 20002:
            if self.camera_on:
                # If camera is on, turn it off
                print("Turning camera off...")
                ret = self.camera.shutdown()
                color = 'black' if ret == 20002 else 'red'
                self.camera_on= False if ret == 20002 else True
            else:
                color= 'green'
                self.camera_on = True
        else:
            # attempt initialization if not connected
            if self.camera_on:
                color= 'black'
                self.camera_on = False
            else:
                ret = self.camera.initialize()
                color = 'green' if ret==20002 else 'red'
                self.camera_on = True if ret==20002 else False
            
        self.set_button_color(self.power_button, color)
        if self.camera_on:
            self.set_camera_settings()
        else: 
            self.refresh_camera_settings()

    def check_power_status(self):
        status, _ = self.camera.get_status()
        # 20002 indicates camera connected
        color = 'green' if status == 20002 else 'black'
        self.set_button_color(self.power_button, color)
        self.camera_on = (status == 20002)
        print("Camera is connected." if self.camera_on else "Camera is not connected.")
        return status

    def check_temperature_status(self):
        status, temp = self.camera.get_temperature_status()
        
        # Use raw Andor temperature status codes
        if status == 20036:  # DRV_TEMP_STABILIZED
            color = 'green'
            self.temp_input.set_value(temp)
        elif status in (20037, 20035):  # NOT_REACHED or NOT_STABILIZED
            color = 'blue'
            self.temp_input.set_value(temp)
        elif status == 20040:  # DRV_TEMP_DRIFT
            color = 'yellow'
            self.temp_input.set_value(temp)
        elif status ==20034:
            color = 'red'
            self.temp_input.set_value(temp)
        else:
            color="red"
            self.temp_input.setText("Not available")
        self.temp_input.setStyleSheet(f"background-color: {color}")
        print(f"Temperature status {status}, temp {temp} °C")
        return status

    def cool_button_clicked(self):
        goal = self.cool_input.value
        print(f"Cooling to {goal} °C")
        ret=self.camera.cool_old(int(goal))
        self.check_temperature_status()
        self.check_cooler_status()
        

    def refresh_camera_settings(self):
        print("Refreshing camera settings...")
        status=self.check_power_status()
        self.check_cooler_status()
        self.check_temperature_status()
        if self.camera.temperature_goal is not None:
            # Set the temperature goal if it exists
            self.cool_input.set_value(self.camera.temperature_goal)
        self.exp_input.set_value(self.camera.exposure_time)
        self.trigger_combo.setCurrentText(self.camera.trigger_mode)
        self.shutter_combo.setCurrentText(self.camera.shutter)
        self.gain_sb.setValue(self.camera.emccdgain)
        # Refresh new camera parameters
        self.read_mode_combo.setCurrentText(self.camera.read_mode)
        self.acq_mode_combo.setCurrentText(self.camera.acquisition_mode)
        self.acc_sb.setValue(self.camera.number_accumulations)
        self.kinetics_sb.setValue(self.camera.number_kinetics)
        self.frame_transfer_combo.setCurrentText(self.camera.frame_transfer_mode)

    
    def set_button_clicked(self):
        status=self.check_power_status()
        if status == 20002:  # Camera is connected
            self.set_camera_settings()

    def set_camera_settings(self):
        self.camera.set_read_mode(self.read_mode_combo.currentText())
        self.camera.set_frame_transfer_mode(self.frame_transfer_combo.currentText())
        self.camera.get_detector()
        self.camera.set_image()
        self.camera.set_trigger_mode(self.trigger_combo.currentText())
        
        self.camera.set_acquisition_mode(self.acq_mode_combo.currentText())
        self.camera.set_number_accumulations(self.acc_sb.value())
        self.camera.set_number_kinetics(self.kinetics_sb.value())
        self.camera.set_exposure_time(self.exp_input.secvalue)
        self.camera.set_emccdgain(self.gain_sb.value())
        self.camera.set_shutter(self.shutter_combo.currentText())
        # Apply read mode, acquisition mode, accumulations, and kinetics
        time.sleep(0.1)  # Allow time for settings to apply
        ret, exp, accum_t, kinetic_t = self.camera.get_acquisition_timings()
        print(f"Actual exposure={exp:.6f}s, accum_t={accum_t:.6f}s, kinetic_t={kinetic_t:.6f}s")

        self.check_temperature_status()
        self.check_cooler_status()


    def cooler_status_button_clicked(self):
        current_text = self.cooler_status_button.text()
        ret=self.camera.is_cooler_on()
        # if ret==1 and current_text == "Cooler OFF":
        #     self.cooler_status_button.setText("Cooler ON")
        # if ret==0 and current_text == "Cooler ON":
        #     self.cooler_status_button.setText("Cooler OFF")
        if ret==1 and current_text == "Reset Temperature":
            achieved=self.camera.cooler_off()
            # if achieved == 20002:
            #     self.cooler_status_button.setText("Cooler OFF")
            # print("Cooler turned off.")
        if ret==0 and current_text == "Cooler OFF":
            achieved=self.camera.cooler_on()
            # if achieved == 20002:
            #     self.cooler_status_button.setText("Cooler ON")
        self.check_cooler_status()  
        self.check_temperature_status()
    
    def check_cooler_status(self):
        """
        Check the cooler status and update the button text accordingly.
        """
        ret = self.camera.is_cooler_on()
        if ret == 1:
            self.cooler_status_button.setText("Reset Temperature")
        else:
            self.cooler_status_button.setText("Cooler OFF")
        print(f"Cooler status: {'ON' if ret == 1 else 'OFF'}")
    
    def optimize_gain(self, gain=1):
        with InstrumentManager() as mgr:
            print('optimizing gain...')
            mx = 0
            safety_counter = 0
            err= self.camera.set_emccdgain(gain)  # setting Electron Multiplier Gain
            if err != 20002:
                raise RuntimeError(f"SetEMCCDGain({gain}) failed (code {err})")
            while(mx<=2.0e4 or mx>=2.9e4) and safety_counter<5 and err==20002:
                safety_counter += 1
                print(f"Safety counter: {safety_counter}")
                # mgr.sg.set_frequency(2.87e9)  # Set the frequency
                mgr.Pulser.stream(1000000000, [3])
                time.sleep(0.1)  # Give time to start acquisition
                self.camera.start_acquisition()
                ret, _ = self.camera.get_status()
                print(f"Start Acquisition returned {ret}")
                if not ret == 20002:
                    print('Starting Acquisition Failed, ending process...')
                    return
                #print('Starting Acquisition', ret)
                time.sleep(0.1) #Give time to start acquisition
                #mgr.Pulser.stream_umOFF([3], 1) 
                if self.camera.trigger_mode != "Internal":

                    mgr.Pulser.stream(100000000, [1])
                timeout_counter = 0
                while(self.camera.get_total_number_images_acquired()[1]<self.camera.number_kinetics and timeout_counter<=100): #20 second hard-coded limit!
                    time.sleep(0.05)#Might want to base wait time on pulse streamer signal
                    timeout_counter+=1
                ret, data, _, _ = self.camera.get_images_16(1,1,1024**2) #cut out first image here
                #print("Number of images collected in current acquisition: ", mgr.sdk.GetTotalNumberImagesAcquired()[1])
                # temp_image = self.img_1D_to_2D(all_data[:1024**2],1024,1024) 
                temp_image = self.img_1D_to_2D(data, 1024, 1024)
                mx = np.max(temp_image)
                print(f'gain of {gain}, mx is {mx}')
                if(mx<=1.0e4):
                    print('signal really low, raising gain +3')
                    gain+=3
                elif mx<=2.0e4:
                    print('raising gain +1')
                    gain+=1
                elif mx>=3.2e4:
                    print(f'Warning, risk of saturation! Max pixel value {mx} detected')
                    gain-=5
                elif mx>=2.9e4: 
                    print(f'Warning, risk of saturation! Max pixel value {mx} detected')  
                    gain-=2
                if gain <= 0:
                    gain = 1
                err=self.camera.set_emccdgain(gain)#setting Electron Multiplier Gain
                self.camera.prepare_acquisition()
                if gain>=150:
                    print('Warning! Gain too high! Re-adjust experiment parameters, or turn off optimize_gain, or edit the limit in the spyrelet code. Aborting...')
                    return
                time.sleep(0.6)
            gain_string = f'optimum gain determined to be {gain}, giving max pixel value of roughly {mx}'
            print(gain_string)
            ret=self.camera.set_emccdgain(gain)
            self.gain_sb.setValue(self.camera.emccdgain)

    def img_1D_to_2D(self, img_1D,x_len,y_len):
        '''
        turns a singular 1D list of integers x_len*y_len long into a 2D array. Cuts and stacks, does not snake.
        '''
        arr = np.asarray(img_1D, dtype=int)
        # if arr.size != x_len * y_len:
        #     raise ValueError(f"Expected {x_len*y_len} elements, got {arr.size}")

        # Reshape into (rows=y_len, cols=x_len)
        return arr.reshape((y_len, x_len))

