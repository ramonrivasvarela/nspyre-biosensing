from PyQt6.QtWidgets import QLineEdit, QWidget, QHBoxLayout, QLabel
from PyQt6.QtGui import QFont
from pyqtgraph import SpinBox
import numpy as np

class MLineEdit(QLineEdit):
    # Line Edit with flexible length units (um, nm) depending on value
    def __init__(self, value=0, prefix=''):
        super().__init__()
        self.umvalue = value
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
            if text.endswith("nm"):
                val_text = text[:-2].strip()
                self.umvalue = float(val_text) * 1e-3
            elif text.endswith("um"):
                val_text = text[:-2].strip()
                self.umvalue = float(val_text)
            else:
                self.umvalue = float(text)
        except ValueError as e:
            raise ValueError(f"Invalid input '{text}': cannot convert to float. Please enter a number with an optional unit 'nm' or 'um'.") from e

        self.update_text()

    def update_text(self):
        """Update the displayed text based on the current value."""
        if self.umvalue < 1:
            self.setText(f"{self.prefix}{self.umvalue * 1e3:.1f} nm")
        else:
            self.setText(f"{self.prefix}{self.umvalue:.3f} um")

class MSpinBox(SpinBox):
    # Spinbox with flexible length units (nm, um) depending on value
    def __init__(self, value=0, min=0, max=1000, step=1):
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
            if text[-2:] == "nm":
                val_text = text[:-2].strip()
                self.hzvalue = float(val_text) * 1e-3
            elif text[-2:] == "um":
                val_text = text[:-2].strip()
                self.hzvalue = float(val_text)
            else:
                self.hzvalue = float(text)
        except ValueError as e:
            raise ValueError(f"Invalid input '{text}': cannot convert to float. Please enter a number with an optional unit 'nm' or 'um'.") from e
        self.update_spinbox()

    def update_spinbox(self):
        if np.abs(self.hzvalue) >= 1:
            self.setDecimals(7)
            self.setValue(self.hzvalue)
            self.setSuffix("um")
            self.setMaximum(self.max)
            self.setMinimum(self.min)
            self.setSingleStep(self.step)
        else:
            self.setMaximum(self.max * 1e3)
            self.setMinimum(self.min * 1e3)
            self.setValue(self.hzvalue * 1e3)
            self.setSuffix("nm")
            self.setDecimals(5)
            self.setSingleStep(self.step* 1e3)

    def change_step(self, step):
        self.step=step
        self.update_spinbox()

class HzLineEdit(QLineEdit):
    # Line Edit with flexible frequency units (Hz, kHz, MHz, GHz) depending on value
    def __init__(self, value=0):
        super().__init__()
        self.hzvalue = value
        self.setFont(QFont("Sanserif", 15))
        self.setFixedWidth(160)
        self.update_text()  # Initialize the text based on the value
        self.editingFinished.connect(self.edit_value)  # Connect signal to update value
                
    def edit_value(self):
        """Update the value based on the text entered by the user."""
        text = self.text().strip()
        try:
            if text.endswith("Hz"):
                val_text = text[:-2].strip()
                self.hzvalue = float(val_text)
            elif text.endswith("kHz"):
                val_text = text[:-3].strip()
                self.hzvalue = float(val_text) * 1e3
            elif text.endswith("MHz"):
                val_text = text[:-3].strip()
                self.hzvalue = float(val_text) * 1e6
            elif text.endswith("GHz"):
                val_text = text[:-3].strip()
                self.hzvalue = float(val_text) * 1e9
            else:
                self.hzvalue = float(text)
        except ValueError as e:
            raise ValueError(f"Invalid input '{text}': cannot convert to float. Please enter a number with an optional unit 'nm' or 'um'.") from e

        self.update_text()

    def update_text(self):
        """Update the displayed text based on the current value."""
        if self.hzvalue >= 1e9:
            self.setText(f"{self.hzvalue*1e-9:.1f} GHz")
        elif self.hzvalue >= 1e6:
            self.setText(f"{self.hzvalue*1e-6:.1f} MHz")
        elif self.hzvalue >= 1e3:
            self.setText(f"{self.hzvalue*1e-3:.1f} kHz")
        else:
            self.setText(f"{self.hzvalue:.3f} kHz")

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
            if text[-2:] == "Hz":
                val_text = text[:-2].strip()
                self.hzvalue = float(val_text)
            elif text[-2:] == "kHz":
                val_text = text[:-3].strip()
                self.hzvalue = float(val_text) * 1e3
            elif text[-2:] == "MHz":
                val_text = text[:-3].strip()
                self.hzvalue = float(val_text) * 1e6
            elif text[-2:] == "GHz":
                val_text = text[:-3].strip()
                self.hzvalue = float(val_text) * 1e9
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
        self.editingFinished.connect(self.edit_value)  # Connect signal to update value
                
    def edit_value(self):
        """Update the value based on the text entered by the user."""
        text = self.text().strip()
        try:
            if text.endswith("s"):
                val_text = text[:-1].strip()
                self.secvalue = float(val_text)
            elif text.endswith("ms"):
                val_text = text[:-2].strip()
                self.secvalue = float(val_text) * 1e-3
            elif text.endswith("us"):
                val_text = text[:-2].strip()
                self.secvalue = float(val_text) * 1e-6
            elif text.endswith("ns"):
                val_text = text[:-2].strip()
                self.secvalue = float(val_text) * 1e-9
            else:
                self.secvalue = float(text)
        except ValueError as e:
            raise ValueError(f"Invalid input '{text}': cannot convert to float. Please enter a number with an optional unit 'nm' or 'um'.") from e
        self.nsvalue=self.secvalue*1e9
        self.update_text()

    def update_text(self):
        """Update the displayed text based on the current value."""
        if self.secvalue >= 1:
            self.setText(f"{self.secvalue:.1f} s")
        elif self.secvalue >= 1e-3:
            self.setText(f"{self.secvalue*1e3:.1f} ms")
        elif self.secvalue >= 1e-6:
            self.setText(f"{self.secvalue*1e6:.1f} us")
        else:
            self.setText(f"{self.secvalue*1e9:.3f} ns")

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
            if text[-2:] == "s":
                val_text = text[:-1].strip()
                self.secvalue = float(val_text)
            elif text[-2:] == "ms":
                val_text = text[:-2].strip()
                self.secvalue = float(val_text) * 1e-3
            elif text[-2:] == "us":
                val_text = text[:-2].strip()
                self.secvalue = float(val_text) * 1e-6
            elif text[-2:] == "ns":
                val_text = text[:-2].strip()
                self.secvalue = float(val_text) * 1e-9
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
        self.x_edit = MLineEdit(x, "X:")
        self.y_edit = MLineEdit(y, "Y:")
        self.z_edit = MLineEdit(z, "Z:")
        self.x_edit.setFixedWidth(120)
        self.y_edit.setFixedWidth(120)       
        self.z_edit.setFixedWidth(120)
        self.setMinimumWidth(400)
        
        # Create a horizontal layout and add labels and the MLineEdits
        layout = QHBoxLayout()
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
    
    def set_point(self, x, y, z):
        """Set the values for x, y, and z and update the displayed text."""
        self.x_edit.umvalue = x
        self.y_edit.umvalue = y
        self.z_edit.umvalue = z
        self.x_edit.update_text()
        self.y_edit.update_text()
        self.z_edit.update_text()

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
        self.setText(f"{self.umvalue}")
     