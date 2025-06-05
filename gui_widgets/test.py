import sys
from PyQt6.QtWidgets import QApplication, QMainWindow
from StepWidget import StepWidget


class TestApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("StepWidget Test")
        self.setGeometry(100, 100, 300, 100)

        # Add StepWidget to the main window
        self.step_widget = StepWidget(
            value =  0, step = 1, suffix = "U"
        )
        self.setCentralWidget(self.step_widget)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestApp()
    window.show()
    sys.exit(app.exec())
