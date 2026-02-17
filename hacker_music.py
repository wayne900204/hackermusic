import asyncio
import socket
import sys
import threading
import webbrowser
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QFrame, QMessageBox, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QPixmap, QFont, QCursor, QImage, QIcon

try:
    import qrcode
    from PIL import Image

    HAS_QR = True
except ImportError:
    HAS_QR = False

# 現代化深色主題
DARK_STYLESHEET = """
QMainWindow, QWidget { background-color: #0f0f1a; color: #ffffff; }
QLabel#subtitle { color: #6b7280; }
QLabel#url { color: #00d4ff; font-weight: bold; }
QFrame#qr_card { background-color: #1a1a2e; border: 1px solid #2d2d44; border-radius: 20px; }
QComboBox, QLineEdit { 
    background-color: #1a1a2e; color: #ffffff; border: 1px solid #2d2d44; 
    border-radius: 10px; padding: 10px; min-height: 20px; 
}
QPushButton#start_btn { 
    background-color: #3b82f6; color: #ffffff; border-radius: 15px; 
    font-size: 16px; font-weight: bold; padding: 15px; 
}
QPushButton#stop_btn { background-color: #ef4444; color: #ffffff; border-radius: 15px; font-weight: bold; padding: 15px; }
"""


class SignalEmitter(QObject):
    update_status = pyqtSignal(str, str)
    server_started = pyqtSignal()
    server_error = pyqtSignal(str)


class AudioStreamApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hacker Music Pro")
        self.setFixedSize(450, 820)
        self.server_running = False
        self.uvicorn_server = None
        self.device_map = {}

        self.signals = SignalEmitter()
        self.signals.update_status.connect(self._update_status_slot)
        self.signals.server_started.connect(self._on_server_started)
        self.signals.server_error.connect(self._on_server_error)

        self._setup_ui()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        self.setWindowIcon(QIcon("hacker.jpg"))
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(30, 30, 30, 30)

        # Header
        title = QLabel("Hacker Music")
        title.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        title.setStyleSheet("color: #00d4ff;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)

        subtitle = QLabel("WebSocket + Loopback Audio")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(subtitle)

        # QR Card
        self.qr_card = QFrame()
        self.qr_card.setObjectName("qr_card")
        qr_layout = QVBoxLayout(self.qr_card)
        self.qr_label = QLabel("Start server to generate QR")
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setMinimumHeight(200)
        qr_layout.addWidget(self.qr_label)
        main_layout.addWidget(self.qr_card)

        # URL
        self.url_label = QLabel("")
        self.url_label.setObjectName("url")
        self.url_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.url_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.url_label.mousePressEvent = self._open_url
        main_layout.addWidget(self.url_label)

        # Port Setting
        port_layout = QHBoxLayout()
        port_label = QLabel("Server Port:")
        port_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.port_input = QLineEdit()
        self.port_input.setText("8080")
        self.port_input.setPlaceholderText("e.g. 8080")
        port_layout.addWidget(port_label)
        port_layout.addWidget(self.port_input)
        main_layout.addLayout(port_layout)

        # Device Combo
        self.device_combo = QComboBox()
        main_layout.addWidget(self.device_combo)
        self._populate_devices()

        # Status
        status_layout = QHBoxLayout()
        status_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_dot = QLabel("●")
        status_layout.addWidget(self.status_dot)
        self.status_label = QLabel("Ready")
        status_layout.addWidget(self.status_label)
        main_layout.addLayout(status_layout)

        # Button
        self.btn = QPushButton("▶  Start Server")
        self.btn.setObjectName("start_btn")
        self.btn.clicked.connect(self._toggle_server)
        main_layout.addWidget(self.btn)
        main_layout.addStretch()

    def _populate_devices(self):
        import pyaudiowpatch as pyaudio
        self.device_map.clear()
        self.device_combo.clear()
        p = pyaudio.PyAudio()
        try:
            items = ["⭐ [預設] 系統主聲道"]
            self.device_map[items[0]] = "default"
            for loopback in p.get_loopback_device_info_generator():
                name = f"🔊 [喇叭擷取] {loopback['name']}"
                items.append(name)
                self.device_map[name] = loopback["index"]
            self.device_combo.addItems(items)
        finally:
            p.terminate()

    def _get_local_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        except:
            return "127.0.0.1"
        finally:
            s.close()

    def _is_port_available(self, port):
        """檢查指定 Port 是否被佔用"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('0.0.0.0', port))
                return True
        except OSError:
            return False

    def _update_qr_display(self, url):
        if HAS_QR:
            qr = qrcode.make(url).convert("RGB").resize((180, 180), Image.Resampling.LANCZOS)
            data = qr.tobytes("raw", "RGB")
            qi = QImage(data, qr.width, qr.height, QImage.Format.Format_RGB888)
            self.qr_label.setPixmap(QPixmap.fromImage(qi))
        self.url_label.setText(url)

    def _open_url(self, event):
        webbrowser.open(self.url_label.text())

    def _run_server(self, device_id, port):
        try:
            asyncio.set_event_loop(asyncio.new_event_loop())
            import server, uvicorn
            server.TARGET_DEVICE_ID = device_id
            config = uvicorn.Config(server.app, host="0.0.0.0", port=port, log_level="warning", log_config=None)
            self.uvicorn_server = uvicorn.Server(config)
            self.signals.server_started.emit()
            self.uvicorn_server.run()
        except Exception as e:
            self.signals.server_error.emit(str(e))

    def _on_server_started(self):
        self.status_label.setText("Server running")
        self.status_dot.setStyleSheet("color: #22c55e;")
        self.btn.setText("⬛  Stop Server")
        self.btn.setObjectName("stop_btn")
        self.btn.setStyle(self.btn.style())
        self.port_input.setEnabled(False)  # 運行中禁止修改 Port

    def _on_server_error(self, err):
        QMessageBox.warning(self, "Error", err)
        self._stop_server()

    def _update_status_slot(self, text, color):
        self.status_label.setText(text)
        self.status_dot.setStyleSheet(f"color: {color};")

    def _toggle_server(self):
        if self.server_running:
            self._stop_server()
        else:
            self._start_server()

    def _start_server(self):
        # 取得並檢查 Port
        try:
            port = int(self.port_input.text())
        except ValueError:
            QMessageBox.warning(self, "Port Error", "Please enter a valid port number.")
            return

        if not self._is_port_available(port):
            QMessageBox.warning(self, "Port In Use",
                                f"Port {port} is already in use by another application. Please try a different port.")
            return

        self.server_running = True
        device_id = self.device_map.get(self.device_combo.currentText())
        url = f"http://{self._get_local_ip()}:{port}"
        self._update_qr_display(url)
        threading.Thread(target=self._run_server, args=(device_id, port), daemon=True).start()

    def _stop_server(self):
        if self.uvicorn_server: self.uvicorn_server.should_exit = True
        self.server_running = False
        self.btn.setText("▶  Start Server")
        self.btn.setObjectName("start_btn")
        self.btn.setStyle(self.btn.style())
        self.status_label.setText("Ready")
        self.status_dot.setStyleSheet("color: #6b7280;")
        self.url_label.setText("")
        self.qr_label.clear()
        self.qr_label.setText("Start server to generate QR")
        self.port_input.setEnabled(True)

    def closeEvent(self, event):
        self._stop_server()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLESHEET)
    window = AudioStreamApp()
    window.show()
    sys.exit(app.exec())