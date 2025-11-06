from PyQt6.QtWidgets import QLineEdit, QWidget, QHBoxLayout, QLabel, QVBoxLayout
from PyQt6.QtGui import QFont
from pyqtgraph import SpinBox
import numpy as np
from PyQt6.QtCore import Qt

class MLineEdit(QLineEdit):
    # Line Edit with flexible length units (um, nm) depending on value
    def __init__(self, value=0, prefix='', conversion=True):
        super().__init__()
        self.umvalue = value
        self.setFont(QFont("Sanserif", 15))
        self.setFixedWidth(160)
        self.prefix=prefix 
        self.conversion=conversion
        self.update_text()  # Initialize the text based on the value
        self.editingFinished.connect(self.edit_value)
         # Connect signal to update value
                
    def edit_value(self):
        """Update the value based on the text entered by the user."""
        text = self.text().strip()
        try:
            if text.lower().endswith("nm"):
                val_text = text[:-2].strip()
                self.umvalue = float(val_text) * 1e-3
            elif text.lower().endswith("um"):
                val_text = text[:-2].strip()
                self.umvalue = float(val_text)
            else:
                self.umvalue = float(text)
        except ValueError as e:
            raise ValueError(f"Invalid input '{text}': cannot convert to float. Please enter a number with an optional unit 'nm' or 'um'.") from e

        self.update_text()

    def update_text(self):
        """Update the displayed text based on the current value."""

        if abs(self.umvalue) < 1 and self.conversion:
            self.setText(f"{self.prefix}{self.umvalue * 1e3:.1f} nm")
        else:
            self.setText(f"{self.prefix}{self.umvalue:.3f} um")

class MSpinBox(SpinBox):
    # Spinbox with flexible length units (nm, um) depending on value
    def __init__(self, value=0, min=0, max=1000, step=1):
        super().__init__()
        self.umvalue = value
        self.setFont(QFont("Sanserif", 15))
        self.setFixedWidth(160)
        self.min=min
        self.max=max
        self.step=step
        self.update_spinbox()
        self.editingFinished.connect(self.update_value)

    def update_value(self):
        text = self.text().strip()
        try:
            if text[-2:] == "nm":
                val_text = text[:-2].strip()
                self.umvalue = float(val_text) * 1e-3
            elif text[-2:] == "um":
                val_text = text[:-2].strip()
                self.umvalue = float(val_text)
            else:
                self.umvalue = float(text)
        except ValueError as e:
            raise ValueError(f"Invalid input '{text}': cannot convert to float. Please enter a number with an optional unit 'nm' or 'um'.") from e
        self.update_spinbox()

    def update_spinbox(self):
        if np.abs(self.umvalue) >= 1:
            self.setDecimals(7)
            self.setValue(self.umvalue)
            self.setSuffix("um")
            self.setMaximum(self.max)
            self.setMinimum(self.min)
            self.setSingleStep(self.step)
        else:
            self.setMaximum(self.max * 1e3)
            self.setMinimum(self.min * 1e3)
            self.setValue(self.umvalue * 1e3)
            self.setSuffix("nm")
            self.setDecimals(5)
            self.setSingleStep(self.step* 1e3)

    def change_step(self, step):
        self.step=step
        self.update_spinbox()

    def set_value(self, value):
        self.umvalue=value
        self.update_spinbox()

class HzLineEdit(QLineEdit):
    # Line Edit with flexible frequency units (Hz, kHz, MHz, GHz) depending on value
    def __init__(self, value=0):
        super().__init__()
        self.hzvalue = value
        self.setFont(QFont("Sanserif", 15))
        self.setFixedWidth(160)
        self.update_text()  # Initialize the text based on the value
        self.editingFinished.connect(self.edit_value)  
        # Connect signal to update value
                
    def edit_value(self):
        """Update the value based on the text entered by the user."""
        text = self.text().strip()
        try:

            if text.lower().endswith("khz"):
                val_text = text[:-3].strip()
                self.hzvalue = float(val_text) * 1e3
            elif text.lower().endswith("mhz"):
                val_text = text[:-3].strip()
                self.hzvalue = float(val_text) * 1e6
            elif text.lower().endswith("ghz"):
                val_text = text[:-3].strip()
                self.hzvalue = float(val_text) * 1e9
            elif text.lower().endswith("hz"):
                val_text = text[:-2].strip()
                self.hzvalue = float(val_text)
            else:
                self.hzvalue = float(text)
        except ValueError as e:
            raise ValueError(f"Invalid input '{text}': cannot convert to float. Please enter a number with an optional unit.") from e

        self.update_text()

    def update_text(self):
        """Update the displayed text based on the current value."""
        if self.hzvalue >= 1e9:
            self.setText(f"{self.hzvalue*1e-9:.3f} GHz")
        elif self.hzvalue >= 1e6:
            self.setText(f"{self.hzvalue*1e-6:.3f} MHz")
        elif self.hzvalue >= 1e3:
            self.setText(f"{self.hzvalue*1e-3:.3f} kHz")
        else:
            self.setText(f"{self.hzvalue:.1f} Hz")

class HzSpinBox(SpinBox):
    # Spin Box with flexible frequency units (Hz, kHz, MHz, GHz) depending on value
    def __init__(self, value=0, min=1, max=1e12, step=1):
        super().__init__()
        self.hzvalue = value
        self.setFont(QFont("Sanserif", 15))
        self.setFixedWidth(160)
        self.min=min
        self.max=max
        self.step=step
        self.update_spinbox()
        self.editingFinished.connect(self.update_value)

    def update_value(self):
        text = self.text().strip()
        try:

            if text.lower().endswith("khz"):
                val_text = text[:-3].strip()
                self.hzvalue = float(val_text) * 1e3
            elif text.lower().endswith("mhz"):
                val_text = text[:-3].strip()
                self.hzvalue = float(val_text) * 1e6
            elif text.lower().endswith("ghz"):
                val_text = text[:-3].strip()
                self.hzvalue = float(val_text) * 1e9
            elif text.lower().endswith("hz"):
                val_text = text[:-2].strip()
                self.hzvalue = float(val_text)
            else:
                self.hzvalue = float(text)
        except ValueError as e:
            raise ValueError(f"Invalid input '{text}': cannot convert to float. Please enter a number with an optional unit 'Hz' or 'kHz'.") from e
        self.update_spinbox()

    def update_spinbox(self):
        if np.abs(self.hzvalue) >= 1e9:
            self.setDecimals(7)
            self.setValue(self.hzvalue*1e-9)
            self.setSuffix("GHz")
            self.setMaximum(self.max* 1e-9)
            self.setMinimum(self.min * 1e-9)
            self.setSingleStep(self.step * 1e-9)
        elif np.abs(self.hzvalue) >= 1e6:
            self.setDecimals(7)
            self.setValue(self.hzvalue*1e-6)
            self.setSuffix("MHz")
            self.setMaximum(self.max * 1e-6)
            self.setMinimum(self.min * 1e-6)
            self.setSingleStep(self.step * 1e-6)
        elif np.abs(self.hzvalue) >= 1e3:
            self.setDecimals(7)
            self.setValue(self.hzvalue*1e-3)
            self.setSuffix("kHz")
            self.setMaximum(self.max * 1e-3)
            self.setMinimum(self.min * 1e-3)
            self.setSingleStep(self.step * 1e-3)
        else:
            self.setMaximum(self.max)
            self.setMinimum(self.min )
            self.setValue(self.hzvalue)
            self.setSuffix("Hz")
            self.setDecimals(5)
            self.setSingleStep(self.step)

    def change_step(self, step):
        self.step=step
        self.update_spinbox()

class SecLineEdit(QLineEdit):
    def __init__(self, value=0):
        super().__init__()
        self.secvalue = value
        self.nsvalue=self.secvalue*1e9
        self.setFont(QFont("Sanserif", 15))
        self.setFixedWidth(160)
        self.update_text()  # Initialize the text based on the value
        self.editingFinished.connect(lambda: self.edit_value())  # Connect signal to update value

    def edit_value(self):
        """Update the value based on the text entered by the user."""
        text = self.text().strip()
        try:
            if text.lower().endswith("ms"):
                val_text = text[:-2].strip()
                self.secvalue = float(val_text) * 1e-3
            elif text.lower().endswith("us"):
                val_text = text[:-2].strip()
                self.secvalue = float(val_text) * 1e-6
            elif text.lower().endswith("ns"):
                val_text = text[:-2].strip()
                self.secvalue = float(val_text) * 1e-9
            elif text.lower().endswith("s"):
                val_text = text[:-1].strip()
                self.secvalue = float(val_text)
            else:
                self.secvalue = float(text)
        except ValueError as e:
            raise ValueError(f"Invalid input '{text}': cannot convert to float. Please enter a number with an optional unit 'nm' or 'um'.") from e
        self.nsvalue=self.secvalue*1e9
        self.update_text()

    def update_text(self):
        """Update the displayed text based on the current value."""
        if self.secvalue >= 1:
            self.setText(f"{self.secvalue:.3f} s")
        elif self.secvalue >= 1e-3:
            self.setText(f"{self.secvalue*1e3:.3f} ms")
        elif self.secvalue >= 1e-6:
            self.setText(f"{self.secvalue*1e6:.3f} us")
        else:
            self.setText(f"{self.secvalue*1e9:.1f} ns")
    
    def set_value(self, value):
        """Set the value and update the text."""
        self.secvalue = value
        self.nsvalue = self.secvalue * 1e9
        self.update_text()

class SecSpinBox(SpinBox):
    
    def __init__(self, value=0, min=0, max=1000, step=1):
        super().__init__()
        self.secvalue = value
        self.nsvalue=self.secvalue*1e9
        self.setFont(QFont("Sanserif", 15))
        self.setFixedWidth(160)
        self.min=min
        self.max=max
        self.step=step
        self.update_spinbox()
        self.editingFinished.connect(self.update_value)

    def update_value(self):
        text = self.text().strip()
        try:
            
            if text.lower().endswith("ms"):
                val_text = text[:-2].strip()
                self.secvalue = float(val_text) * 1e-3
            elif text.lower().endswith("us"):
                val_text = text[:-2].strip()
                self.secvalue = float(val_text) * 1e-6
            elif text.lower().endswith("ns"):
                val_text = text[:-2].strip()
                self.secvalue = float(val_text) * 1e-9
            elif text.lower().endswith("s"):
                val_text = text[:-1].strip()
                self.secvalue = float(val_text)
            else:
                self.secvalue = float(text)
        except ValueError as e:
            raise ValueError(f"Invalid input '{text}': cannot convert to float. Please enter a number with an optional unit 'Hz' or 'kHz'.") from e
        self.nsvalue=self.value*1e9
        self.update_spinbox()

    def update_spinbox(self):
        if np.abs(self.secvalue) >= 1:
            self.setDecimals(7)
            self.setValue(self.secvalue*1)
            self.setSuffix("s")
            self.setMaximum(self.max)
            self.setMinimum(self.min )
            self.setSingleStep(self.step )
        elif np.abs(self.secvalue) >= 1e-3:
            self.setDecimals(7)
            self.setValue(self.secvalue*1e3)
            self.setSuffix("ms")
            self.setMaximum(self.max * 1e3)
            self.setMinimum(self.min * 1e3)
            self.setSingleStep(self.step * 1e3)
        elif np.abs(self.secvalue) >= 1e-6:
            self.setDecimals(7)
            self.setValue(self.secvalue*1e6)
            self.setSuffix("us")
            self.setMaximum(self.max * 1e6)
            self.setMinimum(self.min * 1e6)
            self.setSingleStep(self.step * 1e6)
        else:
            self.setMaximum(self.max*1e9)
            self.setMinimum(self.min * 1e9)
            self.setValue(self.secvalue*1e9)
            self.setSuffix("ns")
            self.setDecimals(5)
            self.setSingleStep(self.step * 1e9)

    def change_step(self, step):
        self.step=step
        self.update_spinbox()

class NSLineEdit(SecLineEdit):
    def __init__(self, value=0):    
        super().__init__(value)

class PointWidget(QWidget):
    def __init__(self, x=0, y=0, z=0):
        super().__init__()
        
        # Create three MLineEdit fields initialized with given values
        self.x_edit = MLineEdit(x, "", conversion=False)  # No conversion for x
        self.y_edit = MLineEdit(y, "", conversion=False)  # No conversion for y
        self.z_edit = MLineEdit(z, "", conversion=False)  # No conversion for z
        self.x_edit.setFixedWidth(120)
        self.y_edit.setFixedWidth(120)       
        self.z_edit.setFixedWidth(120)
        
        # Create a horizontal layout and add labels and the MLineEdits
        layout = QHBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.x_edit)
        layout.addWidget(self.y_edit)
        layout.addWidget(self.z_edit)
        self.setLayout(layout)

    
    def get_point(self):
        """Return a dictionary of the current values for x, y, and z."""
        return {
            "x": self.x_edit.umvalue,
            "y": self.y_edit.umvalue,
            "z": self.z_edit.umvalue
        }

    def get_position(self):
        return (self.x_edit.umvalue, self.y_edit.umvalue, self.z_edit.umvalue)

    def set_point(self, x, y, z):
        """Set the values for x, y, and z and update the displayed text."""
        self.x_edit.umvalue = x
        self.y_edit.umvalue = y
        self.z_edit.umvalue = z
        self.x_edit.update_text()
        self.y_edit.update_text()
        self.z_edit.update_text()

    def get_position_as_tuple(self):
        """Return the position as a tuple (x, y, z)."""
        return (self.x_edit.umvalue, self.y_edit.umvalue, self.z_edit.umvalue)

class HzIntervalWidget(QWidget):
    def __init__(self, start, end=0, interval=0):
        super().__init__()
        
        # Create three MLineEdit fields initialized with given values
        self.start_edit = HzLineEdit(start)  # No conversion for start
        self.end_edit = HzLineEdit(end)  # No conversion for end
        self.interval_edit = HzLineEdit(interval)  # No conversion for interval
        self.start_edit.setFixedWidth(120)
        self.end_edit.setFixedWidth(120)       
        self.interval_edit.setFixedWidth(120)
        self.setMinimumWidth(400)
        
        # Create a horizontal layout and add labels and the MLineEdits
        layout = QHBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.start_edit)
        layout.addWidget(self.end_edit)
        layout.addWidget(self.interval_edit)

        self.setLayout(layout)
    
    def get_range(self):
        """Return a dictionary of the current values for start, end, and interval."""
        return (
            self.start_edit.hzvalue,
            self.end_edit.hzvalue,
            self.interval_edit.hzvalue
        )

    def set_range(self, start, end, interval):
        """Set the values for start, end, and interval and update the displayed text."""
        self.start_edit.hzvalue = start
        self.end_edit.hzvalue = end
        self.interval_edit.hzvalue = interval
        self.start_edit.update_text()
        self.end_edit.update_text()
        self.interval_edit.update_text()

class FloatLineEdit(QLineEdit):
    def __init__(self, value=0, prefix=''):
        super().__init__()
        self.value = value
        self.setFont(QFont("Sanserif", 15))
        self.setFixedWidth(160)
        self.prefix=prefix 
        self.update_text()  # Initialize the text based on the value
        self.editingFinished.connect(self.edit_value)
         # Connect signal to update value
                
    def edit_value(self):
        """Update the value based on the text entered by the user."""
        text = self.text().strip()
        try:
            self.value = float(text)
        except ValueError as e:
            raise ValueError(f"Invalid input '{text}': cannot convert to float. Please enter a number with an optional unit 'nm' or 'um'.") from e

        self.update_text()

    def update_text(self):
        """Update the displayed text based on the current value."""
        self.setText(f"{self.value}")

    def set_value(self, value):
        """Set the value and update the text."""
        self.value = value
        self.update_text()
     
class TemperatureLineEdit(QLineEdit):
    def __init__(self, value=20, prefix='', max=100, min=-100, asinteger=False):
        super().__init__()
        self.max=max
        self.min=min
        self.asinteger=asinteger
        if value < self.min or value > self.max:
            self.value=20
        else:
            self.value = value
        if self.asinteger:
            self.value = int(self.value)
        self.setFont(QFont("Sanserif", 15))
        self.setFixedWidth(160)
        self.prefix=prefix 
        self.update_text()  # Initialize the text based on the value
        self.editingFinished.connect(self.edit_value)
        
    
         # Connect signal to update value
                
    def edit_value(self):
        """Update the value based on the text entered by the user."""
        if self.text()[-2:]=="°C":
            text = self.text()[:-2].strip()
        else:
            text = self.text().strip()
        try:
            value = float(text)
        
        except ValueError as e:
            raise ValueError(f"Invalid input '{text}': cannot convert to float. Please enter a number.") from e
        if value < self.min or value > self.max:
            raise ValueError(f"Temperature value must be between {self.min} and {self.max} °C.")
        if self.asinteger:
            value = int(value)
        self.value = value
        self.update_text()

    def update_text(self):
        """Update the displayed text based on the current value."""
        if self.asinteger:
            self.setText(f"{self.prefix} {self.value} °C")
        else:
            self.setText(f"{self.prefix} {self.value:.2f} °C")

    def set_value(self, value):
        """Set the value and update the displayed text."""
        if value < self.min or value > self.max:
            raise ValueError(f"Temperature value must be between {self.min} and {self.max} °C.")
        else:
            if self.asinteger:
                self.value = int(value)
            else:
                self.value = value
            self.update_text()

class ThreeValueWidget(QWidget):
    def __init__(self, value1=0, value2=0, value3=0, prefix1='', prefix2='', prefix3=''):
        super().__init__()
        
        # Create three FloatLineEdit fields initialized with given values
        self.value1_edit = FloatLineEdit(value1, prefix1)
        self.value2_edit = FloatLineEdit(value2, prefix2)
        self.value3_edit = FloatLineEdit(value3, prefix3)
        self.value1_edit.setFixedWidth(50)
        self.value2_edit.setFixedWidth(50)       
        self.value3_edit.setFixedWidth(50)
        self.setMinimumWidth(400)
        
        # Create a horizontal layout and add labels and the FloatLineEdits
        layout = QHBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.value1_edit)
        layout.addWidget(self.value2_edit)
        layout.addWidget(self.value3_edit)
        
        self.setLayout(layout)

    def get_values(self):
        """Return a dictionary of the current values for start, end, and interval."""
        return (
            self.value1_edit.value,
            self.value2_edit.value,
            self.value3_edit.value
        )

    def set_values(self, value1, value2, value3):
        """Set the values for start, end, and interval and update the displayed text."""
        self.value1_edit.value = value1
        self.value2_edit.value = value2
        self.value3_edit.value = value3
        self.value1_edit.update_text()
        self.value2_edit.update_text()
        self.value3_edit.update_text()

class WLineEdit(QLineEdit):
        # Line Edit with flexible length units (um, nm) depending on value
    def __init__(self, value=0, prefix='', conversion=True):
        super().__init__()
        self.value = value
        self.setFont(QFont("Sanserif", 15))
        self.setFixedWidth(160)
        self.prefix=prefix 
        self.conversion=conversion
        self.update_text()  # Initialize the text based on the value
        self.editingFinished.connect(self.edit_value)
         # Connect signal to update value
                
    def edit_value(self):
        """Update the value based on the text entered by the user."""
        text = self.text().strip()
        try:
            if text.lower().endswith("mW"):
                val_text = text[:-2].strip()
                self.value = float(val_text) * 1e-3
            elif text.lower().endswith("W"):
                val_text = text[:-1].strip()
                self.value = float(val_text)
            else:
                self.value = float(text)
        except ValueError as e:
            raise ValueError(f"Invalid input '{text}': cannot convert to float. Please enter a number with an optional unit 'mW' or 'W'.") from e

        self.update_text()

    def update_text(self):
        """Update the displayed text based on the current value."""

        if abs(self.value) < 1 and self.conversion:
            self.setText(f"{self.prefix}{self.value * 1e3:.1f} nW")
        else:
            self.setText(f"{self.prefix}{self.value:.3f} W")