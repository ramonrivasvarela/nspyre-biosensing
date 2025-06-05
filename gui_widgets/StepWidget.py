from PyQt6.QtWidgets import QLabel, QHBoxLayout, QWidget
from pyqtgraph import SpinBox


class StepWidget(QWidget):
    def __init__(self, parent=None, **spinbox_kwargs):
        """
        A widget that combines a SpinBox with a dynamically adjustable step size.

        :param parent: Parent widget.
        :param spinbox_kwargs: Parameters to configure the main SpinBox.
        """
        super().__init__(parent)

        # Create the main SpinBox
        self.main_spinbox = SpinBox(**spinbox_kwargs)
        self.main_spinbox.setFixedWidth(150)

        # Create the step label
        self.step_label = QLabel("Step:")
        self.step_label.setFixedWidth(50)

        # Create the step SpinBox
        self.step_spinbox = SpinBox(
            value=spinbox_kwargs.get("step", 1),
            suffix=spinbox_kwargs.get("suffix", ''),
            siPrefix=spinbox_kwargs.get("siPrefix", True),
            bounds=(1e-9, 1e9),
            dec=True
        )
        self.step_spinbox.setFixedWidth(80)
        # self.step_spinbox.setMaximumWidth(80)
        # self.step_spinbox.setMinimumWidth(80)

        # Layout for the widget
        self.layout = QHBoxLayout()
        self.layout.addWidget(self.step_label)
        self.layout.addWidget(self.step_spinbox)
        self.layout.addWidget(self.main_spinbox)
        self.setLayout(self.layout)

        # Connect the step SpinBox to update the main SpinBox step size
        self.step_spinbox.valueChanged.connect(self.update_step)

    def update_step(self):
        """Update the step size of the main SpinBox."""
        step_value = self.step_spinbox.value()
        self.main_spinbox.setSingleStep(step_value)
        print('ping')

    def value(self):
        """Return the current value of the main SpinBox."""
        return self.main_spinbox.value()