import time
from functools import partial
from typing import Any
from typing import Dict
from typing import List
from typing import Tuple

from pyqtgraph import ImageView
from pyqtgraph import PlotItem
from pyqtgraph import InfiniteLine
from pyqtgraph.colormap import getFromMatplotlib
from pyqtgraph.Qt import QtCore
from pyqtgraph.Qt import QtGui
from pyqtgraph.Qt import QtWidgets

from nspyre import nspyre_font
from nspyre.gui.widgets.update_loop import UpdateLoop


class CrosshairManager(QtWidgets.QWidget):
    """Widget for managing multiple crosshairs."""
    
    delete_crosshair = QtCore.Signal(int)  # Signal emitted when crosshair should be deleted
    update_crosshair = QtCore.Signal(int, float, float)  # Signal emitted when crosshair position should be updated
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QtWidgets.QVBoxLayout()
        
        # Title
        title_label = QtWidgets.QLabel("Crosshairs")
        title_label.setStyleSheet("font-weight: bold;")
        self.layout.addWidget(title_label)
        
        # Scrollable list area
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_widget = QtWidgets.QWidget()
        self.scroll_layout = QtWidgets.QVBoxLayout(self.scroll_widget)
        self.scroll_layout.addStretch()
        self.scroll_area.setWidget(self.scroll_widget)
        
        self.layout.addWidget(self.scroll_area)
        self.setLayout(self.layout)
        
        # Store crosshair item widgets and their line edits
        self.crosshair_items: Dict[int, QtWidgets.QWidget] = {}
        self.crosshair_edits: Dict[int, Tuple[QtWidgets.QLineEdit, QtWidgets.QLineEdit]] = {}
        
    def add_crosshair(self, crosshair_id: int, x: float, y: float):
        """Add a crosshair entry to the list."""
        item_widget = QtWidgets.QWidget()
        item_layout = QtWidgets.QHBoxLayout()
        item_layout.setContentsMargins(2, 2, 2, 2)
        
        # ID label
        id_label = QtWidgets.QLabel(f"#{crosshair_id}:")
        id_label.setMaximumWidth(30)
        item_layout.addWidget(id_label)
        
        # X coordinate edit
        x_label = QtWidgets.QLabel("X:")
        x_label.setMaximumWidth(15)
        item_layout.addWidget(x_label)
        
        x_edit = QtWidgets.QLineEdit(f"{x:.3f}")
        x_edit.setMinimumWidth(60)
        x_edit.setValidator(QtGui.QDoubleValidator())
        x_edit.editingFinished.connect(
            lambda: self._on_coordinate_changed(crosshair_id, x_edit, y_edit)
        )
        item_layout.addWidget(x_edit)
        
        # Y coordinate edit
        y_label = QtWidgets.QLabel("Y:")
        y_label.setMaximumWidth(15)
        item_layout.addWidget(y_label)
        
        y_edit = QtWidgets.QLineEdit(f"{y:.3f}")
        y_edit.setMinimumWidth(60)
        y_edit.setValidator(QtGui.QDoubleValidator())
        y_edit.editingFinished.connect(
            lambda: self._on_coordinate_changed(crosshair_id, x_edit, y_edit)
        )
        item_layout.addWidget(y_edit)
        
        # Delete button
        delete_btn = QtWidgets.QPushButton("Del")
        delete_btn.setMaximumWidth(40)
        delete_btn.clicked.connect(lambda: self.delete_crosshair.emit(crosshair_id))
        item_layout.addWidget(delete_btn)
        
        item_widget.setLayout(item_layout)
        
        # Insert before the stretch
        self.scroll_layout.insertWidget(self.scroll_layout.count() - 1, item_widget)
        self.crosshair_items[crosshair_id] = item_widget
        self.crosshair_edits[crosshair_id] = (x_edit, y_edit)
    
    def _on_coordinate_changed(self, crosshair_id: int, x_edit: QtWidgets.QLineEdit, y_edit: QtWidgets.QLineEdit):
        """Handle coordinate changes from line edits."""
        try:
            x = float(x_edit.text())
            y = float(y_edit.text())
            self.update_crosshair.emit(crosshair_id, x, y)
        except ValueError:
            # Invalid input, revert to previous values
            if crosshair_id in self.crosshair_edits:
                # Just keep the invalid text for now - it will be updated when the crosshair is updated
                pass
    
    def update_crosshair_display(self, crosshair_id: int, x: float, y: float):
        """Update the displayed coordinates for a crosshair."""
        if crosshair_id in self.crosshair_edits:
            x_edit, y_edit = self.crosshair_edits[crosshair_id]
            # Block signals to avoid triggering editingFinished during programmatic update
            x_edit.blockSignals(True)
            y_edit.blockSignals(True)
            x_edit.setText(f"{x:.3f}")
            y_edit.setText(f"{y:.3f}")
            x_edit.blockSignals(False)
            y_edit.blockSignals(False)
        
    def remove_crosshair(self, crosshair_id: int):
        """Remove a crosshair entry from the list."""
        if crosshair_id in self.crosshair_items:
            widget = self.crosshair_items[crosshair_id]
            self.scroll_layout.removeWidget(widget)
            widget.deleteLater()
            del self.crosshair_items[crosshair_id]
            del self.crosshair_edits[crosshair_id]
    
    def clear_all(self):
        """Remove all crosshair entries."""
        for crosshair_id in list(self.crosshair_items.keys()):
            self.remove_crosshair(crosshair_id)


class HeatMapWidget(QtWidgets.QWidget):
    """Qt widget for displaying 2D data using pyqtgraph ImageView."""

    new_data = QtCore.Signal()
    """Qt Signal emitted when new data is available."""

    def __init__(
        self,
        *args,
        title: str = '',
        btm_label: str = '',
        lft_label: str = '',
        colormap=None,
        font: QtGui.QFont = nspyre_font,
        crosshair_func=None,
        **kwargs,
    ):
        """
        Args:
            title: Plot title.
            btm_label: Plot bottom axis label.
            lft_label: Plot left axis label.
            colormap: pyqtgraph `ColorMap <https://pyqtgraph.readthedocs.io/en/\
                latest/api_reference/colormap.html#pyqtgraph.ColorMap>`__ object.
            font: Font to use in the plot title, axis labels, etc., although
                the font type may not be fully honored.
            crosshair_func: Optional function to call when the user clicks
        """
        super().__init__(*args, **kwargs)
        self.crosshair_func = crosshair_func

        if colormap is None:
            colormap = getFromMatplotlib('magma')
        
        # Main horizontal layout (plot on left, manager on right)
        self.main_layout = QtWidgets.QHBoxLayout()
        
        # Left side: plot and controls
        self.left_widget = QtWidgets.QWidget()
        self.layout = QtWidgets.QVBoxLayout(self.left_widget)
        
        # button layout for controls
        self.button_layout = QtWidgets.QHBoxLayout()
        
        # crosshair toggle button
        self.crosshair_button = QtWidgets.QPushButton("Enable Crosshair")
        self.crosshair_button.setCheckable(True)
        self.crosshair_button.clicked.connect(self._toggle_crosshair)
        self.button_layout.addWidget(self.crosshair_button)
        
        # Clear all crosshairs button
        self.clear_all_button = QtWidgets.QPushButton("Clear All")
        self.clear_all_button.clicked.connect(self._clear_all_crosshairs)
        self.button_layout.addWidget(self.clear_all_button)
        
        # Live position label (shown when placing crosshair)
        self.position_label = QtWidgets.QLabel("")
        self.position_label.setStyleSheet("background-color: rgba(255, 255, 255, 200); padding: 5px; border-radius: 3px;")
        self.position_label.hide()
        self.button_layout.addWidget(self.position_label)
        
        self.button_layout.addStretch()  # push buttons to the left
        
        self.layout.addLayout(self.button_layout)

        # pyqtgraph widget for displaying an Image (2d or 3d plot) and related
        # items like axes, legends, etc.
        self.plot_item = PlotItem()
        self.image_view = ImageView(view=self.plot_item)
        self.layout.addWidget(self.image_view)
        
        # plot settings
        self.plot_item.setTitle(title, size=f'{font.pointSize()}pt')
        self.plot_item.enableAutoRange(True)
        self.plot_item.setAspectLocked(False)
        self.plot_item.invertY(False)  # Set y-axis to non-inverted by default

        # colormap
        self.image_view.setColorMap(colormap)

        # axes
        self.btm_axis = self.plot_item.getAxis('bottom')
        self.btm_axis.setLabel(text=btm_label)
        self.btm_axis.label.setFont(font)
        self.btm_axis.setTickFont(font)
        self.btm_axis.enableAutoSIPrefix(False)
        self.lft_axis = self.plot_item.getAxis('left')
        self.lft_axis.setLabel(text=lft_label)
        self.lft_axis.label.setFont(font)
        self.lft_axis.setTickFont(font)
        self.lft_axis.enableAutoSIPrefix(False)
        
        # we keep a dict containing the x-axis, y-axis, z-axis (optional, only
        # for 3D images), data, semaphore, and pyqtgraph PlotDataItem
        # associated with each line plot
        self.image: Dict[str, Any] = {
            'x': [],
            'y': [],
            'z': None,
            'data': [],
            'sem': QtCore.QSemaphore(n=1),
        }
        
        # Crosshair management
        self.crosshair_enabled = False

        self.crosshairs: Dict[int, Tuple[InfiniteLine, InfiniteLine]] = {}
        self.next_crosshair_id = 0
        
        # Temporary crosshair lines (shown during mouse movement)
        self.crosshair_v = InfiniteLine(angle=90, movable=False, pen='y')
        self.crosshair_h = InfiniteLine(angle=0, movable=False, pen='y')
        
        # Dragging state
        self.dragging_enabled=False
        self.dragging_crosshair_id = None
        self.drag_start_pos = None
        
        # Right side: crosshair manager panel
        self.crosshair_manager = CrosshairManager()
        self.crosshair_manager.delete_crosshair.connect(self._delete_crosshair)
        self.crosshair_manager.update_crosshair.connect(self._update_crosshair_position)
        self.crosshair_manager.setMaximumWidth(250)
        
        # Add left and right widgets to main layout
        self.main_layout.addWidget(self.left_widget, stretch=3)
        self.main_layout.addWidget(self.crosshair_manager, stretch=1)
        
        self.setLayout(self.main_layout)
        
        # Enable keyboard focus to capture key events
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)

        # Always connect mouse events for dragging (outside of crosshair placement mode)
        self.plot_item.scene().sigMouseClicked.connect(self._on_click_drag)
        self.plot_item.scene().sigMouseMoved.connect(self._on_mouse_move_drag)

        # TODO
        self.destroyed.connect(partial(self._stop))

        # Plot setup code
        self.setup()

        # thread for updating the plot data
        self.update_loop = UpdateLoop(self.update)
        # process new data when a signal is generated by the update thread
        self.new_data.connect(self._process_data)
        # start the thread
        self.update_loop.start()

    def _stop(self):
        """ """
        self.update_loop.stop()
        self.teardown()

    def _process_data(self):
        """Update the color map triggered by set_data."""
        try:
            if self.image['z'] is None:
                axes = {'x': 1, 'y': 0}
            else:
                axes = {'x': 1, 'y': 0, 't': 2}
            z_index = self.image_view.currentIndex
            xs, ys = self.image['x'], self.image['y']
            x_mx, x_mn, y_mx, y_mn = max(xs), min(xs), max(ys), min(ys)
            x_rng, y_rng = x_mx - x_mn, y_mx - y_mn
            self.image_view.setImage(
                self.image['data'],
                pos=[x_mn, y_mn],
                scale=[x_rng / len(xs), y_rng / len(ys)],
                autoRange=False,
                autoLevels=True,
                autoHistogramRange=False,
                axes=axes,
                levelMode='mono',
                xvals=self.image['z'],
            )

            if z_index:
                self.image_view.setCurrentIndex(z_index)
        except Exception as exc:
            raise exc
        finally:
            self.image['sem'].release()

    def setup(self):
        """Subclasses should override this function to perform any setup code."""
        pass

    def update(self):
        """Subclasses should override this function to update the plot. This
        function will be run in a separate Thread."""
        time.sleep(1)

    def teardown(self):
        """Subclasses should override this function to perform any teardown code."""
        pass

    def set_data(self, xs, ys, data, zs=None):
        """Queue up x,y,z and data to update the color map. Threadsafe.

        Args:
            name: Name of the plot.
            xs: Array-like of data for the x-axis.
            ys: Array-like of data for the y-axis.
            data: 2D or 3D array with the data to be plotted. For a 2D imge,
                data's rows should correspond to the y-axis and the columns
                should correspond to the x-axis. Moreover, xs should be the
                same length as the number of columns of data, and ys should
                be the same length as the number of rows of data. This way,
                when the widget attempts to display the pixel at index (i, j),
                it looks for it in data[j][i]. In the case of a 3D array, the
                z-axis information should be in the last index, so that the
                pixel at (x, y, z) is stored in data[y][x][z].
            zs: Optional array-like of data for the z-axis.
        Raises:
            ValueError: An error with the supplied arguments.
        """
        # block until any previous calls to set_data have been fully processed
        self.image['sem'].acquire()
        # set the new x and y data
        self.image['x'] = xs
        self.image['y'] = ys
        if zs is not None:
            self.image['z'] = zs
        self.image['data'] = data
        # notify the watcher
        try:
            self.parent()
        except RuntimeError:
            # this Qt object has already been deleted
            return
        else:
            # notify that new data is available
            self.new_data.emit()

    def _toggle_crosshair(self, checked):
        """Toggle crosshair mode on/off."""
        if checked:
            self.crosshair_button.setText("Disable Crosshair")
            self.crosshair_enabled = True
            # Show live position label
            self.position_label.show()
            # Add temporary crosshair lines to the plot
            self.plot_item.addItem(self.crosshair_v)
            self.plot_item.addItem(self.crosshair_h)
            # Connect mouse move and click events
            self.plot_item.scene().sigMouseMoved.connect(self._on_mouse_move)
            self.plot_item.scene().sigMouseClicked.connect(self._on_click)
        else:
            self.crosshair_button.setText("Enable Crosshair")
            self.crosshair_enabled = False
            # Hide live position label
            self.position_label.hide()
            # Remove temporary crosshair lines from the plot
            self.plot_item.removeItem(self.crosshair_v)
            self.plot_item.removeItem(self.crosshair_h)
            # Disconnect mouse events
            try:
                self.plot_item.scene().sigMouseMoved.disconnect(self._on_mouse_move)
                self.plot_item.scene().sigMouseClicked.disconnect(self._on_click)
            except TypeError:
                pass  # Already disconnected
    
    def _on_mouse_move(self, pos):
        """Update crosshair position when mouse moves."""
        if not self.crosshair_enabled:
            return
            
        # Convert scene coordinates to data coordinates
        if self.plot_item.sceneBoundingRect().contains(pos):
            mouse_point = self.plot_item.vb.mapSceneToView(pos)
            x, y = mouse_point.x(), mouse_point.y()
            # Update temporary crosshair positions
            self.crosshair_v.setPos(x)
            self.crosshair_h.setPos(y)
            # Update live position label
            self.position_label.setText(f"Position: X={x:.3f}, Y={y:.3f}")
    
    def _find_nearest_crosshair(self, x: float, y: float, threshold: float = 0.05) -> int:
        """Find the nearest crosshair to the given position.
        
        Args:
            x: X coordinate in data space
            y: Y coordinate in data space
            threshold: Maximum distance (as fraction of axis range) to consider a crosshair as "near"
            
        Returns:
            Crosshair ID if found within threshold, None otherwise
        """
        if not self.crosshairs:
            return None
            
        # Get axis ranges for normalized distance calculation
        x_range = self.plot_item.viewRange()[0]
        y_range = self.plot_item.viewRange()[1]
        x_span = x_range[1] - x_range[0]
        y_span = y_range[1] - y_range[0]
        
        min_distance = float('inf')
        nearest_id = None
        
        for crosshair_id, (v_line, h_line) in self.crosshairs.items():
            cx = v_line.value()
            cy = h_line.value()
            
            # Normalized distance
            dx = (x - cx) / x_span if x_span != 0 else 0
            dy = (y - cy) / y_span if y_span != 0 else 0
            distance = (dx**2 + dy**2)**0.5
            
            if distance < min_distance and distance < threshold:
                min_distance = distance
                nearest_id = crosshair_id
        
        return nearest_id
    
    def _on_click_drag(self, event):
        """Handle mouse clicks for dragging crosshairs (when not in placement mode)."""
        if self.crosshair_enabled:
            return  # Let the placement handler deal with it
            
        if event.double():
            return  # Ignore double clicks
            
        # Get the click position
        scene_pos = event.scenePos()
        if self.plot_item.sceneBoundingRect().contains(scene_pos):
            mouse_point = self.plot_item.vb.mapSceneToView(scene_pos)
            x, y = mouse_point.x(), mouse_point.y()
            
            if event.button() == QtCore.Qt.MouseButton.LeftButton:
                # If already dragging, stop dragging on next click
                if self.dragging_crosshair_id is not None:
                    print(f"Stopped dragging crosshair #{self.dragging_crosshair_id}")
                    self.dragging_crosshair_id = None
                    self.drag_start_pos = None
                else:
                    # Not dragging, check if clicked near a crosshair to start dragging
                    nearest_id = self._find_nearest_crosshair(x, y)
                    
                    if nearest_id is not None:
                        # Start dragging this crosshair
                        self.dragging_crosshair_id = nearest_id
                        self.drag_start_pos = (x, y)
                        print(f"Started dragging crosshair #{nearest_id}")
            elif event.button() == QtCore.Qt.MouseButton.RightButton:
                # Right click always stops dragging
                if self.dragging_crosshair_id is not None:
                    print(f"Cancelled dragging crosshair #{self.dragging_crosshair_id}")
                self.dragging_crosshair_id = None
                self.drag_start_pos = None
    
    def _on_mouse_move_drag(self, pos):
        """Handle mouse movement for dragging crosshairs."""
        if self.crosshair_enabled or self.dragging_crosshair_id is None:
            return  # Not dragging or in placement mode
            
        # Convert scene coordinates to data coordinates
        if self.plot_item.sceneBoundingRect().contains(pos):
            mouse_point = self.plot_item.vb.mapSceneToView(pos)
            x, y = mouse_point.x(), mouse_point.y()
            
            # Update the crosshair position
            self._update_crosshair_position(self.dragging_crosshair_id, x, y)
    
    def _on_click(self, event):
        """Handle mouse click events on the plot."""
        if not self.crosshair_enabled or event.double():
            return  # Ignore if crosshair disabled or double clicks
            
        # Get the click position in the scene
        scene_pos = event.scenePos()
        # Convert scene coordinates to data coordinates
        if self.plot_item.sceneBoundingRect().contains(scene_pos):
            mouse_point = self.plot_item.vb.mapSceneToView(scene_pos)
            x, y = mouse_point.x(), mouse_point.y()
            
            # Add a permanent crosshair at this position
            self._add_permanent_crosshair(x, y)
            
            print(f"Added crosshair at x: {x:.3f}, y: {y:.3f}")
            
            # Call the optional callback function if provided
            if self.crosshair_func is not None:
                try:
                    self.crosshair_func(x, y)
                except Exception as e:
                    print(f"Error calling crosshair callback function: {e}")
    
    def _add_permanent_crosshair(self, x: float, y: float):
        """Add a permanent crosshair at the specified position."""
        crosshair_id = self.next_crosshair_id
        self.next_crosshair_id += 1
        
        # Create new crosshair lines with a different color for each
        colors = ['r', 'g', 'b', 'c', 'm', 'w']
        color = colors[crosshair_id % len(colors)]
        
        v_line = InfiniteLine(angle=90, movable=False, pen=color)
        h_line = InfiniteLine(angle=0, movable=False, pen=color)
        
        v_line.setPos(x)
        h_line.setPos(y)
        
        # Add to plot
        self.plot_item.addItem(v_line)
        self.plot_item.addItem(h_line)
        
        # Store crosshair
        self.crosshairs[crosshair_id] = (v_line, h_line)
        
        # Add to manager panel
        self.crosshair_manager.add_crosshair(crosshair_id, x, y)
        self._toggle_crosshair(False)
        self.crosshair_button.setChecked(False)
    
    def _update_crosshair_position(self, crosshair_id: int, x: float, y: float):
        """Update the position of an existing crosshair."""
        if crosshair_id in self.crosshairs:
            v_line, h_line = self.crosshairs[crosshair_id]
            
            # Update line positions
            v_line.setPos(x)
            h_line.setPos(y)
            
            # Update display in manager (in case it was changed programmatically)
            self.crosshair_manager.update_crosshair_display(crosshair_id, x, y)
            
            # Only print when not dragging (to avoid spam)
            if self.dragging_crosshair_id != crosshair_id:
                print(f"Updated crosshair #{crosshair_id} to ({x:.3f}, {y:.3f})")
            
            # Call the optional callback function if provided
            if self.crosshair_func is not None:
                try:
                    self.crosshair_func(x, y)
                except Exception as e:
                    print(f"Error calling crosshair callback function: {e}")
    
    def _delete_crosshair(self, crosshair_id: int):
        """Delete a specific crosshair."""
        if crosshair_id in self.crosshairs:
            v_line, h_line = self.crosshairs[crosshair_id]
            
            # Remove from plot
            self.plot_item.removeItem(v_line)
            self.plot_item.removeItem(h_line)
            
            # Remove from storage
            del self.crosshairs[crosshair_id]
            
            # Remove from manager panel
            self.crosshair_manager.remove_crosshair(crosshair_id)
            
            print(f"Deleted crosshair #{crosshair_id}")
    
    def _clear_all_crosshairs(self):
        """Clear all permanent crosshairs."""
        for crosshair_id in list(self.crosshairs.keys()):
            self._delete_crosshair(crosshair_id)
        print("Cleared all crosshairs")

    def keyPressEvent(self, event):
        """Handle key press events."""
        if event.key() == QtCore.Qt.Key.Key_Escape and self.crosshair_enabled:
            # Exit crosshair mode when Escape is pressed
            self.crosshair_button.setChecked(False)
            self._toggle_crosshair(False)
        elif event.key() == QtCore.Qt.Key.Key_Escape and self.dragging_crosshair_id is not None:
            # Cancel dragging when Escape is pressed
            print(f"Cancelled dragging crosshair #{self.dragging_crosshair_id}")
            self.dragging_crosshair_id = None
            self.drag_start_pos = None
        elif event.key() == QtCore.Qt.Key.Key_C:
            # Toggle crosshair mode when C is pressed
            self.crosshair_button.setChecked(not self.crosshair_enabled)
            self._toggle_crosshair(not self.crosshair_enabled)
        else:
            super().keyPressEvent(event)
