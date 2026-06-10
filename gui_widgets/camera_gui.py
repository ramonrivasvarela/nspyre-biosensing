from PyQt6.QtWidgets import QLineEdit, QWidget, QFrame, QGridLayout, QPushButton, QLabel, QComboBox, QSpinBox
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QTimer
from nspyre import InstrumentManager
from special_widgets.unit_widgets import SecLineEdit, TemperatureLineEdit
from pyqtgraph import SpinBox
import time
import numpy as np
from gui_widgets.picture_exp_gui import PicturesWidget

class CameraWidget(QWidget):
    """
    Camera control widget for managing Andor camera settings and operations.
    Provides controls for power, temperature, cooling, exposure, trigger modes,
    and various acquisition parameters.
    """
    def __init__(self, font: str = "Arial"):
        """
        Initialize the camera widget.
        
        Args:
            font: Font family to use for the UI (default: "Arial")
        """
        super().__init__()
        self.font = font
        self.camera_on = False
        self.cooling_timer = None
        
        try:
            self.camera = InstrumentManager().Camera
        except Exception as e:
            self.camera = None
            print(f"Could not get camera. Error: {e}")

        self.init_widgets()
        self.create_layout()

    # ==================== Initialization Methods ====================
    
    def init_widgets(self):
        """
        Initialize all UI widgets for camera control.
        Creates buttons, labels, combo boxes, and input fields.
        """
        # Power button
        self.power_button = QPushButton("Power")
        self.power_button.setFixedHeight(30)
        self.power_button.clicked.connect(self.power_button_clicked)

        # Trigger mode
        self.trigger_label = QLabel("Trigger Modes:")
        self.trigger_label.setFixedHeight(20)
        self.trigger_label.setStyleSheet("font-weight: bold")
        self.trigger_combo = QComboBox()
        self.trigger_combo.addItems(["Internal", "External", "External Exposure (Bulb)"])
        self.trigger_combo.setCurrentText("Internal")
        self.trigger_combo.setStyleSheet("QComboBox { background-color: #2b2b2b; color: white; }")
        self.trigger_combo.setFixedHeight(30)
        self.trigger_combo.setFont(QFont(self.font, 12))
        self.trigger_combo.currentTextChanged.connect(lambda t: self.change_settings(self.trigger_combo, self.camera.set_trigger_mode, t))

        # Exposure time
        self.exp_label = QLabel("Exposure Time:")
        self.exp_label.setFixedHeight(20)
        self.exp_label.setStyleSheet("font-weight: bold")
        self.exp_input=SpinBox(
            value=75e-3,
            suffix='s',
            siPrefix=True,
            dec=True,
        )
        self.exp_input.editingFinished.connect(lambda: self.change_settings(self.exp_input, self.camera.set_exposure_time, self.exp_input.secvalue))

        # Shutter
        self.shutter_label = QLabel("Shutter:")
        self.shutter_label.setFixedHeight(20)
        self.shutter_label.setStyleSheet("font-weight: bold")
        self.shutter_combo = QComboBox()
        self.shutter_combo.addItems(["Closed", "Open", "Automatic"])
        self.shutter_combo.setCurrentText("Automatic")
        self.shutter_combo.setStyleSheet("QComboBox { background-color: #2b2b2b; color: white; }")
        self.shutter_combo.setFixedHeight(30)
        self.shutter_combo.setFont(QFont(self.font, 12))
        self.shutter_combo.currentTextChanged.connect(lambda s: self.change_settings(self.shutter_combo, self.camera.set_shutter, s))

        # Frame Transfer Mode
        self.frame_transfer_label = QLabel("Frame Transfer Mode:")
        self.frame_transfer_label.setFixedHeight(20)
        self.frame_transfer_label.setStyleSheet("font-weight: bold")
        self.frame_transfer_combo = QComboBox()
        self.frame_transfer_combo.addItems(["ON", "OFF"])
        self.frame_transfer_combo.setCurrentText("OFF")
        self.frame_transfer_combo.setStyleSheet("QComboBox { background-color: #2b2b2b; color: white; }")
        self.frame_transfer_combo.setFixedHeight(30)
        self.frame_transfer_combo.setFont(QFont(self.font, 12))
        self.frame_transfer_combo.currentTextChanged.connect(lambda mode: self.change_settings(self.frame_transfer_combo, self.camera.set_frame_transfer_mode, mode))

        # Gain
        self.gain_label = QLabel("Gain:")
        self.gain_label.setFixedHeight(20)
        self.gain_label.setStyleSheet("font-weight: bold")
        self.gain_sb = QSpinBox()
        self.gain_sb.setRange(1, 255)
        self.gain_sb.setValue(2)
        self.gain_sb.editingFinished.connect(lambda : self.change_settings(self.gain_sb, self.camera.set_emccdgain, self.gain_sb.value()))

        # Temperature
        self.temp_label = QLabel("Temperature:")
        self.temp_label.setFixedHeight(20)
        self.temp_label.setStyleSheet("font-weight: bold")
        self.temp_output=QLineEdit()
        self.temp_output.editingFinished.connect(lambda: self.check_temperature_status())

        # Cooling controls
        self.cool_input=QSpinBox()
        self.cool_input.setRange(-100, 20)
        self.cool_input.setValue(18)
        self.cool_input.setSuffix(" °C")
        self.cool_button = QPushButton("Cool To:")
        self.cool_button.clicked.connect(lambda: self.cool_button_clicked())
        
        self.stop_cooling_button = QPushButton("Stop Cooling")
        self.stop_cooling_button.clicked.connect(lambda: self.stop_cooling_clicked())

        # Read mode
        self.read_mode_label = QLabel("Read Mode:")
        self.read_mode_label.setFixedHeight(20)
        self.read_mode_label.setStyleSheet("font-weight: bold")
        self.read_mode_combo = QComboBox()
        self.read_mode_combo.addItems([
            "Full Vertical Binning",
            "Multi-Track",
            "Random-Track",
            "Single-Track",
            "Image"
        ])
        self.read_mode_combo.setCurrentText('Image')
        self.read_mode_combo.currentTextChanged.connect(lambda m: self.change_settings(self.read_mode_combo, self.camera.set_read_mode, m))

        # Acquisition mode
        self.acq_mode_label = QLabel("Acquisition Mode:")
        self.acq_mode_label.setFixedHeight(20)
        self.acq_mode_label.setStyleSheet("font-weight: bold")
        self.acq_mode_combo = QComboBox()
        self.acq_mode_combo.addItems([
            "Single Scan",
            "Accumulate",
            "Kinetics",
            "Fast Kinetics",
            "Run till Abort"
        ])
        self.acq_mode_combo.setCurrentText('Kinetics')
        self.acq_mode_combo.currentTextChanged.connect(lambda m: self.change_settings(self.acq_mode_combo, self.camera.set_acquisition_mode, m))

        # Number of accumulations
        self.acc_label = QLabel("Num. Accumulations:")
        self.acc_label.setFixedHeight(20)
        self.acc_label.setStyleSheet("font-weight: bold")
        self.acc_sb = QSpinBox()
        self.acc_sb.setRange(1, 1000)
        self.acc_sb.setValue(1)
        self.acc_sb.editingFinished.connect(lambda : self.change_settings(self.acc_sb, self.camera.set_number_accumulations, self.acc_sb.value()))

        # Number of kinetics
        self.kinetics_label = QLabel("Num. Kinetics:")
        self.kinetics_label.setFixedHeight(20)
        self.kinetics_label.setStyleSheet("font-weight: bold")
        self.kinetics_sb = QSpinBox()
        self.kinetics_sb.setRange(1, 1000)
        self.kinetics_sb.setValue(1)
        self.kinetics_sb.editingFinished.connect(lambda : self.change_settings(self.kinetics_sb, self.camera.set_number_kinetics, self.kinetics_sb.value()))

        # Action buttons
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(lambda: self.refresh_camera_settings())
        
        # self.set_button = QPushButton("Set")
        # self.set_button.clicked.connect(lambda: self.set_button_clicked())
        
        self.cooler_status_button = QPushButton("Stop Cooling")
        self.cooler_status_button.clicked.connect(lambda: self.cooler_status_button_clicked())

        # Pictures widget (show below camera controls)
        try:
            self.pictures_widget = PicturesWidget()
        except Exception as e:
            self.pictures_widget = None
            print(f"Failed to create PicturesWidget: {e}")

    def create_layout(self):
        """
        Create and arrange the widget layout.
        Organizes all controls in a grid layout.
        """
        frame = QFrame(self)
        frame.setStyleSheet("background-color: #454545")
        layout = QGridLayout(frame)
        layout.setSpacing(10)

        # Power and trigger
        layout.addWidget(self.power_button, 1, 1, 1, 1)
        layout.addWidget(self.trigger_label, 2, 1, 1, 1)
        layout.addWidget(self.trigger_combo, 2, 2, 1, 1)
        
        # Exposure and shutter
        layout.addWidget(self.exp_label, 3, 1, 1, 1)
        layout.addWidget(self.exp_input, 3, 2, 1, 1)
        layout.addWidget(self.shutter_label, 4, 1, 1, 1)
        layout.addWidget(self.shutter_combo, 4, 2, 1, 1)
        
        # Gain
        layout.addWidget(self.gain_label, 5, 1, 1, 1)
        layout.addWidget(self.gain_sb, 5, 2, 1, 1)
        
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

        # Frame transfer
        layout.addWidget(self.frame_transfer_label, 10, 1, 1, 1)
        layout.addWidget(self.frame_transfer_combo, 10, 2, 1, 1)
        
        # Temperature and cooling
        layout.addWidget(self.temp_output, 11, 1, 1, 1)
        layout.addWidget(self.cool_button, 12, 1, 1, 1)
        layout.addWidget(self.cool_input, 12, 2, 1, 1)
        layout.addWidget(self.stop_cooling_button, 11, 2, 1, 1)
        # Action buttons
        layout.addWidget(self.refresh_button, 13, 1, 1, 1)
        # layout.addWidget(self.set_button, 12, 2, 1, 1)
        

        main_layout = QGridLayout(self)
        main_layout.addWidget(frame, 0, 0, 1, 1)
        # add the pictures widget below the camera controls if available
        if getattr(self, 'pictures_widget', None) is not None:
            main_layout.addWidget(self.pictures_widget, 1, 0, 1, 1)
        self.setLayout(main_layout)

    # ==================== Utility Methods ====================

    def set_button_color(self, widget, color):
        """
        Set the background color of a button widget.
        
        Args:
            widget: The QPushButton to style
            color: Color name or hex code for the background
        """
        widget.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                border: 2px solid #888;
            }}
            QPushButton:pressed {{
                background-color: #555;
            }}
        """)

    # ==================== Power Control Methods ====================

    def power_button_clicked(self):
        """
        Handle power button clicks to initialize or shutdown the camera.
        Attempts to connect if no camera exists, or toggles power state.
        Updates button color to reflect connection status.
        """
        if self.camera and self.camera_on:
            print("Turning camera off...")
            ret = self.camera.shutdown()
            color = 'black' if ret == 20002 else 'red'
            self.camera_on = False if ret == 20002 else True
            self.set_button_color(self.power_button, color)
            return

        if not self.camera:
            try:
                self.camera = InstrumentManager().Camera
            except Exception as e:
                print(f"Failed to get camera from InstrumentManager: {e}")
                self.set_button_color(self.power_button, 'red')
                return

        # Initialize camera directly
        try:
            print("Initializing camera...")
            ret = self.camera.initialize()
            if ret == 20002:
                self.camera_on = True
                self.set_button_color(self.power_button, 'green')
                self.refresh_camera_settings()
                print("Camera initialized successfully.")
            else:
                print(f"Camera initialize failed with code {ret}")
                self.set_button_color(self.power_button, 'red')
                self.camera_on = False
        except Exception as e:
            print(f"Failed to initialize camera: {e}")
            self.set_button_color(self.power_button, 'red')
            self.camera_on = False

    def check_power_status(self):
        """
        Check the current power/connection status of the camera.
        Updates the power button color based on status.
        
        Returns:
            int: Andor status code (20002 indicates successful connection)
        """
        if not self.camera:
            print("No camera connected.")
            return
        
        status, _ = self.camera.get_status()
        color = 'green' if status == 20002 else 'black'
        self.set_button_color(self.power_button, color)
        self.camera_on = (status == 20002)
        print("Camera is connected." if self.camera_on else "Camera is not connected.")
        return status

    # ==================== Setting Change Methods ====================

    def change_settings(self, button, setting_func, value):
        """
        General method to change a camera setting and update button color.
        
        Args:
            button: The QPushButton associated with the setting
            setting_func: The function to call to change the setting
            value: The value to set for the setting
        """
        ret=setting_func(value)
        if ret == 20002:
            self.refresh_camera_settings()
            self.set_button_color(button, 'grey')
        else:
            self.refresh_camera_settings()
            self.set_button_color(button, 'red')
        
        

    # ==================== Temperature and Cooling Methods ====================

    def check_temperature_status(self):
        """
        Check the current temperature and status of the camera.
        Updates the temperature display with color coding:
        - Green: Temperature stabilized
        - Blue: Cooling in progress (not reached or not stabilized)
        - Yellow: Temperature drift detected
        - Red: Cooler off or error
        
        Returns:
            int: Andor temperature status code
        """
        if not self.camera:
            print("No camera connected.")
            return
        
        status, temp = self.camera.get_temperature_status()
        
        if status == 20036:  # DRV_TEMP_STABILIZED
            color = 'green'
            self.temp_output.setText(f"{temp:.2f} °C")
        elif status in (20037, 20035):  # NOT_REACHED or NOT_STABILIZED
            color = 'blue'
            self.temp_output.setText(f"{temp:.2f} °C")
        elif status == 20040:  # DRV_TEMP_DRIFT
            color = 'yellow'
            self.temp_output.setText(f"{temp:.2f} °C")
        elif status == 20034:  # DRV_TEMP_OFF
            color = 'red'
            self.temp_output.setText(f"{temp:.2f} °C")
        else:
            color = "red"
            self.temp_output.setText("Not available")
        
        self.temp_output.setStyleSheet(f"background-color: {color}")
        print(f"Temperature status {status}, temp {temp:.2f} °C")
        return status

    def cool_button_clicked(self):
        """
        Start cooling the camera to the target temperature.
        Initiates a QTimer to monitor temperature status every 5 seconds
        until the temperature stabilizes.
        """
        if not self.camera:
            print("No camera connected.")
            return
        
        # Stop any existing monitoring timer
        if self.cooling_timer:
            self.cooling_timer.stop()
        
        goal = self.cool_input.value()
        print(f"Cooling to {goal} °C")
        ret = self.camera.cool_old(int(goal))
        self.check_temperature_status()
        # Start monitoring with QTimer
        self.cooling_timer = QTimer()
        self.cooling_timer.timeout.connect(self.monitor_cooling)
        self.cooling_timer.start(5000)  # Check every 5 seconds
        
        self.check_cooler_status()

    def monitor_cooling(self):
        """
        Monitor temperature status during cooling process.
        Called every 5 seconds by QTimer. Continues monitoring while
        temperature is not stabilized (status codes 20037, 20035, 20040).
        Stops automatically when temperature reaches target or stabilizes.
        """
        if not self.camera:
            if self.cooling_timer:
                self.cooling_timer.stop()
            return
        
        status = self.check_temperature_status()
        
        # Stop monitoring if temperature is stabilized or off
        # 20037: NOT_REACHED, 20035: NOT_STABILIZED, 20040: DRIFT
        if status not in (20037, 20035, 20040):
            print("Cooling monitoring finished")
            if self.cooling_timer:
                self.cooling_timer.stop()
            self.check_cooler_status()

    def stop_cooling_clicked(self):
        """
        Stop the camera cooling process and monitoring.
        Turns off the cooler and stops the temperature monitoring timer.
        """
        if not self.camera:
            print("No camera connected.")
            return
        
        # Stop monitoring timer
        if self.cooling_timer:
            self.cooling_timer.stop()
        
        self.camera.cooler_off()
        print("Cooler turned off.")
        self.check_cooler_status()
        self.check_temperature_status()

    def check_cooler_status(self):
        """
        Check if the camera cooler is on or off.
        Shows/hides the "Stop Cooling" button based on cooler state.
        """
        if not self.camera:
            print("No camera connected.")
            return
        
        ret = self.camera.is_cooler_on()
        if ret == 1:
            self.stop_cooling_button.setVisible(True)
            print("Cooler status: ON")
        else:
            self.stop_cooling_button.setVisible(False)
            print("Cooler status: OFF")

    def cooler_status_button_clicked(self):
        """
        Handle clicks on the cooler status button.
        Turns off the cooler if it's currently on.
        (Deprecated: Use stop_cooling_clicked instead)
        """
        if not self.camera:
            print("No camera connected.")
            return
        
        ret = self.camera.is_cooler_on()
        if ret == 1:
            self.camera.cooler_off()
            print("Cooler turned off.")
        else:
            print("Cooler is already off.")
        
        self.check_cooler_status()
        self.check_temperature_status()

    # ==================== Settings Management Methods ====================

    def refresh_camera_settings(self):
        """
        Refresh all camera settings from the camera hardware.
        Updates all UI controls to reflect current camera state including:
        - Power status
        - Temperature and cooling status
        - Exposure time, trigger mode, shutter
        - Gain, read mode, acquisition mode
        - Number of accumulations and kinetics
        - Frame transfer mode
        """
        if not self.camera:
            print("No camera connected.")
            return
        
        print("Refreshing camera settings...")
        status = self.check_power_status()
        self.check_cooler_status()
        self.check_temperature_status()
        
        if self.camera.temperature_goal is not None:
            self.cool_input.setValue(self.camera.temperature_goal)
        
        self.exp_input.setValue(self.camera.exposure_time)
        self.trigger_combo.setCurrentText(self.camera.trigger_mode)
        self.shutter_combo.setCurrentText(self.camera.shutter)
        self.gain_sb.setValue(self.camera.emccdgain)
        self.read_mode_combo.setCurrentText(self.camera.read_mode)
        self.acq_mode_combo.setCurrentText(self.camera.acquisition_mode)
        self.acc_sb.setValue(self.camera.number_accumulations)
        self.kinetics_sb.setValue(self.camera.number_kinetics)
        self.frame_transfer_combo.setCurrentText(self.camera.frame_transfer_mode)
