"""
Custom notification widget for the Voice Typing System.
Provides an OS-independent, non-interfering pop-up message.
"""

from PyQt6.QtWidgets import QWidget, QLabel, QApplication, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer

class NotificationWidget(QWidget):
    """A simple, borderless pop-up widget for notifications."""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |    # No window border
            Qt.WindowType.ToolTip |                # Stays on top
            Qt.WindowType.WindowDoesNotAcceptFocus # Prevents stealing focus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        # Use a layout to properly contain the label
        layout = QVBoxLayout(self)
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setWordWrap(True)
        layout.addWidget(self.label)

        # Updated styling for a visible box with a border
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(30, 30, 30, 220);
                color: white;
                border-radius: 8px;
                border: 1px solid #444;
            }
        """)
        self.label.setStyleSheet("background: transparent; border: none; padding: 15px;")

        # Timer to auto-hide the notification
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def show_message(self, text: str, duration: int = 5000):
        """
        Displays the notification with the given text and duration.
        
        Args:
            text: The message to display.
            duration: How long to show the message in milliseconds.
        """
        # Stop any existing timer to reset the hide countdown
        if self._hide_timer.isActive():
            self._hide_timer.stop()

        self.label.setText(text)
        
        # Have the widget calculate its own best size
        self.adjustSize()
        
        self._position_widget()
        
        self.show()
        self.raise_() # Ensure it's on top
        self._hide_timer.start(duration)

    def _position_widget(self):
        """Positions the widget in the bottom-right corner, avoiding the taskbar."""
        # Use availableGeometry to not overlap with the system taskbar
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        
        # Margin from the screen edges
        margin = 15

        x = screen_geometry.right() - self.width() - margin
        y = screen_geometry.bottom() - self.height() - margin

        self.move(x, y) 