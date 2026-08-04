import logging
import queue
from functools import partial
from importlib import reload
from multiprocessing import Queue
from types import ModuleType
from typing import Optional

from pyqtgraph.Qt import QtWidgets, QtCore

from nspyre.misc.misc_updated import EXPERIMENT_STATUS_MESSAGE
from nspyre.misc.misc_updated import ProcessRunner
from nspyre.misc.misc_updated import run_experiment
from nspyre.gui.widgets.params import ParamsWidget


class ExperimentWidget(QtWidgets.QWidget):
    """Qt widget for automatically generating a GUI for a simple experiment.
    Parameters can be entered by the user in a
    :py:class:`~nspyre.gui.widgets.params.ParamsWidget`. Buttons are
    generated for the user to run, stop, and kill the experiment process.
    """

    #### STYLES
    RUNNING_STYLE = (
        'QPushButton {'
        ' background-color: #2e7d32;'
        ' color: white;'
        ' font-weight: bold;'
        '}'
    )
    ERROR_STYLE = (
        'QPushButton {'
        ' background-color: #c62828;'
        ' color: white;'
        ' font-weight: bold;'
        '}'
    )


    def __init__(
        self,
        params_config: dict,
        module: ModuleType,
        cls: str,
        fun_name: str,
        constructor_args: Optional[list] = None,
        constructor_kwargs: Optional[dict] = None,
        fun_args: Optional[list] = None,
        fun_kwargs: Optional[dict] = None,
        title: Optional[str] = None,
        kill: bool = False,
        queue: bool = False,
        layout: QtWidgets.QLayout = None,
    ):
        """
        Args:
            params_config: Dictionary that is passed to the constructor of
                :py:class:`~nspyre.gui.widgets.params.ParamsWidget`.
            module: Python module that contains cls.
            cls: Python class name as a string. An instance of this class will
                be created in a subprocess when the user presses the 'Run' button.
                The :code:`__enter__` and :code:`__exit__` methods will be called
                if implemented. In addition, if the class constructor takes
                keyword arguments :code:`queue_to_exp` and/or :code:`queue_from_exp`,
                multiprocessing :code:`Queue` objects will be passed in that can
                be used to communicate with the GUI.
            fun_name: Name of function within cls to run. All of the values from
                the ParamsWidget will be passed as keyword arguments to this function.
            constructor_args: Args to pass to cls.
            constructor_kwargs: Keyword arguments to pass to cls.
            fun_args: Args to pass to :code:`cls.fun`.
            fun_kwargs: Keyword arguments to pass to :code:`cls.fun`.
            title: Window title.
            kill: Add a kill button to allow the user to forcibly kill the subprocess
                running the experiment function.
            queue: Add a queue button to allow the user to queue the experiment function
                to run after the current experiment function finishes.
            layout: Additional Qt layout to place between the parameters and
                run/stop/kill buttons.
        """
        super().__init__()

        if title is not None:
            self.setWindowTitle(title)

        self.module = module
        self.cls = cls
        self.fun_name = fun_name
        if constructor_args is not None:
            self.constructor_args = constructor_args
        else:
            self.constructor_args = []

        if constructor_kwargs is not None:
            self.constructor_kwargs = constructor_kwargs
        else:
            self.constructor_kwargs = {}

        if fun_args is not None:
            self.fun_args = fun_args
        else:
            self.fun_args = []

        if fun_kwargs is not None:
            self.fun_kwargs = fun_kwargs
        else:
            self.fun_kwargs = {}

        self.params_widget = ParamsWidget(params_config)

        # run button
        self.run_button = QtWidgets.QPushButton('Run')
        self._run_button_default_style = self.run_button.styleSheet()
        self.run_proc = ProcessRunner()
        self.run_button.clicked.connect(self.run)

        self.queue_to_exp: Queue = Queue()
        """multiprocessing Queue to pass to the experiment subprocess and use
        for sending messages to the subprocess."""
        self.queue_from_exp: Queue = Queue()
        """multiprocessing Queue to pass to the experiment subprocess and use
        for receiving messages from the subprocess."""

        # stop button
        stop_button = QtWidgets.QPushButton('Stop')
        stop_button.clicked.connect(self.stop)
        # use a partial because the stop function may already be destroyed by the time
        # this is called
        self.destroyed.connect(partial(self.stop, log=False))

        # kill button
        if kill:
            kill_button = QtWidgets.QPushButton('Kill')
            kill_button.clicked.connect(self.kill)

        # Queue button
        if queue:
            queue_button = QtWidgets.QPushButton('Queue')
            queue_button.clicked.connect(self.queue)

        # Qt layout that arranges the params and button vertically
        params_layout = QtWidgets.QVBoxLayout()
        params_layout.addWidget(self.params_widget)
        if layout is not None:
            params_layout.addLayout(layout)
        # add stretch element to take up any extra space below the spinboxes
        params_layout.addStretch()
        if queue:
            params_layout.addWidget(queue_button)
        params_layout.addWidget(self.run_button)
        params_layout.addWidget(stop_button)
        if kill:
            params_layout.addWidget(kill_button)
        self.setLayout(params_layout)

        # Create a timer for updating the GUI
        self._status_timer = QtCore.QTimer(self)
        self._status_timer.setInterval(333)
        self._status_timer.timeout.connect(self._check_experiment_status) # Check experiment status every 333 ms

        self._terminal_status_received = False
        self._stop_requested = False

    def _set_run_button_state(self, state: str):
        """Set the Run button to normal, running (green), or error (red)."""
        if state == 'running':
            self.run_button.setStyleSheet(self.RUNNING_STYLE)
        elif state == 'error':
            self.run_button.setStyleSheet(self.ERROR_STYLE)
        else:
            self.run_button.setStyleSheet(self._run_button_default_style)

    @staticmethod
    def _drain_queue(msg_queue: Queue):
        """Discard stale messages left over from a previous run."""
        while True:
            try:
                msg_queue.get_nowait()
            except queue.Empty:
                return

        
    def run(self):
        """Run the experiment function in a subprocess."""

        if self.run_proc.running():
            logging.info(
                'Not starting the experiment process because it is still running.'
            )
            return

        # A stale stop or terminal status must not affect the next run.
        self._drain_queue(self.queue_to_exp)
        self._drain_queue(self.queue_from_exp)
        self._terminal_status_received = False
        self._stop_requested = False
        self._set_run_button_state('running')

        try:
            # reload the module at runtime in case any changes were made to the code
            reload(self.module)
            # get the experiment class
            exp_cls = getattr(self.module, self.cls)
            # make a new dict that contains the function kwargs as well as the
            # user-entered parameters
            fun_kwargs = dict(self.fun_kwargs, **self.params_widget.all_params())
            # call the function in a new process
            self.run_proc.run(
                run_experiment,
                exp_cls=exp_cls,
                fun_name=self.fun_name,
                constructor_args=self.constructor_args,
                constructor_kwargs=self.constructor_kwargs,
                queue_to_exp=self.queue_to_exp,
                queue_from_exp=self.queue_from_exp,
                fun_args=self.fun_args,
                fun_kwargs=fun_kwargs,
            )
        except BaseException:
            # This catches launch/reload/parameter errors that occur in the GUI
            # process before the worker can report through queue_from_exp.
            self._set_run_button_state('error')
            logging.exception('Failed to start experiment process.')
            return
        self._status_timer.start()  # Start the timer to check experiment status

    def _check_experiment_status(self):
        """Process all pending worker messages and detect unexpected exits."""
        while True:
            try:
                message = self.queue_from_exp.get_nowait()
            except queue.Empty:
                break

            if (
                isinstance(message, dict)
                and message.get('type') == EXPERIMENT_STATUS_MESSAGE
            ):
                status = message.get('status')
                if status == 'started':
                    self._set_run_button_state('running')
                elif status == 'finished':
                    self._terminal_status_received = True
                    self._finish_monitoring(error=False)
                    return
                elif status == 'error':
                    self._terminal_status_received = True
                    logging.error(
                        'Experiment failed with %s: %s\n%s',
                        message.get('error_type', 'Exception'),
                        message.get('error', ''),
                        message.get('traceback', ''),
                    )
                    self._finish_monitoring(error=True)
                    return
            else:
                self.handle_experiment_message(message)

        # Queue messages are the primary signal. The process state is a fallback
        # for hard crashes, termination, or legacy experiment runners.
        proc = self.run_proc.proc
        if proc is not None and not proc.is_alive():
            proc.join(timeout=0)
            exitcode = proc.exitcode

            if self._stop_requested or exitcode == 0:
                self._finish_monitoring(error=False)
            else:
                logging.error(
                    'Experiment process exited without a terminal status '
                    '(exit code %s).',
                    exitcode,
                )
                self._finish_monitoring(error=True)

    def _finish_monitoring(self, error: bool):
        self._status_timer.stop()
        self._set_run_button_state('error' if error else 'normal')

        proc = self.run_proc.proc
        if proc is not None and not proc.is_alive():
            proc.join(timeout=0)

    def handle_experiment_message(self, message):
        """Hook for subclasses that also use queue_from_exp for custom messages."""
        logging.debug('Unhandled experiment message: %r', message)

    def stop(self, log: bool = True):
        """Request the experiment subprocess to stop by sending the string :code:`stop`
        to :code:`queue_to_exp`.

        Args:
            log: if True, log when stop is called but the process isn't running.
        """
        if self.run_proc.running():
            self.queue_to_exp.put('stop')
        else:
            if log:
                logging.info(
                    'Not stopping the experiment process because it is not running.'
                )

    def kill(self):
        """Kill the experiment subprocess."""
        if self.run_proc.running():
            self.run_proc.kill()
        else:
            logging.info(
                'Not killing the experiment process because it is not running.'
            )

    def pause(self):
        """Pause the experiment subprocess."""
        print("Pause is a W.I.P.")

    def queue(self):
        """ """
        print("Queue is a W.I.P.")


def experiment_widget_process_queue(msg_queue) -> Optional[str]:
    """Return one pending message from a multiprocessing Queue, if available."""
    if msg_queue is not None:
        try:
            return msg_queue.get_nowait()
        except queue.Empty:
            return None
    return None
