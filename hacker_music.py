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

DARK_STYLESHEET = """
QMainWindow, QWidget { background-color: #0f0f1a; color: #ffffff; }
QLabel#subtitle { color: #6b7280; }
QLabel#url { color: #00d4ff; font-weight: bold; }
QFrame#qr_card { background-color: #1a1a2e; border: 1px solid #2d2d44; border-radius: 20px; }
QComboBox, QLineEdit { 
    background-color: #1a1a2e; color: #ffffff; border: 1px solid #2d2d44; 
    border-radius: 10px; padding: 10px; min-height: 20px; 
}
QPushButton#start_btn { background-color: #3b82f6; color: #ffffff; border-radius: 15px; font-size: 16px; font-weight: bold; padding: 15px; }
QPushButton#stop_btn { background-color: #ef4444; color: #ffffff; border-radius: 15px; font-weight: bold; padding: 15px; }
QPushButton#refresh_btn { background-color: #2d2d44; color: #ffffff; border-radius: 8px; font-size: 16px; }
QPushButton#refresh_btn:hover { background-color: #4b4b66; }
QFrame#io_panel { background-color: #131320; border: 1px solid #2d2d44; border-radius: 15px; }
"""


class SignalEmitter(QObject):
    update_status = pyqtSignal(str, str)
    server_started = pyqtSignal()
    server_error = pyqtSignal(str)


class AudioStreamApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hacker Music Pro")
        # 稍微拉高視窗，給放大的 QR Code 更多空間
        self.setFixedSize(450, 800)
        self.server_running = False
        self.uvicorn_server = None

        self.input_map = {}

        self.signals = SignalEmitter()
        self.signals.update_status.connect(self._update_status_slot)
        self.signals.server_started.connect(self._on_server_started)
        self.signals.server_error.connect(self._on_server_error)

        self._setup_ui()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        try:
            self.setWindowIcon(QIcon("hacker.jpg"))
        except:
            pass

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(30, 30, 30, 30)

        title = QLabel("Hacker Music")
        title.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        title.setStyleSheet("color: #00d4ff;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)

        self.qr_card = QFrame()
        self.qr_card.setObjectName("qr_card")
        qr_layout = QVBoxLayout(self.qr_card)
        self.qr_label = QLabel("Start server to generate QR")
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # 拉高預留區域，適應更大的 QR Code
        self.qr_label.setMinimumHeight(300)
        qr_layout.addWidget(self.qr_label)
        main_layout.addWidget(self.qr_card)

        self.url_label = QLabel("")
        self.url_label.setObjectName("url")
        self.url_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.url_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.url_label.mousePressEvent = self._open_url
        main_layout.addWidget(self.url_label)
        main_layout.addSpacing(10)

        # 網路 IP 與 Port 設定
        network_layout = QHBoxLayout()
        self.refresh_ip_btn = QPushButton("🔄")
        self.refresh_ip_btn.setObjectName("refresh_btn")
        self.refresh_ip_btn.setFixedSize(38, 38)
        self.refresh_ip_btn.clicked.connect(self._populate_ips)

        self.ip_combo = QComboBox()
        self.port_input = QLineEdit()
        self.port_input.setText("8080")
        self.port_input.setFixedWidth(65)

        network_layout.addWidget(QLabel("IP:"))
        network_layout.addWidget(self.ip_combo, stretch=1)
        network_layout.addWidget(self.refresh_ip_btn)
        network_layout.addWidget(QLabel("Port:"))
        network_layout.addWidget(self.port_input)
        main_layout.addLayout(network_layout)
        self._populate_ips()
        main_layout.addSpacing(5)

        # 音源設定面板
        io_frame = QFrame()
        io_frame.setObjectName("io_panel")
        io_layout = QVBoxLayout(io_frame)
        io_layout.setContentsMargins(15, 15, 15, 15)

        in_layout = QHBoxLayout()
        in_label = QLabel("🎤 擷取音源:")
        in_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.input_combo = QComboBox()
        in_layout.addWidget(in_label)
        in_layout.addWidget(self.input_combo, stretch=1)

        io_layout.addLayout(in_layout)
        main_layout.addWidget(io_frame)

        self._populate_devices()

        # Status & Button
        status_layout = QHBoxLayout()
        status_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_dot = QLabel("●")
        self.status_label = QLabel("Ready")
        status_layout.addWidget(self.status_dot)
        status_layout.addWidget(self.status_label)
        main_layout.addLayout(status_layout)

        self.btn = QPushButton("▶  Start Server")
        self.btn.setObjectName("start_btn")
        self.btn.clicked.connect(self._toggle_server)
        main_layout.addWidget(self.btn)

    def _populate_ips(self):
        self.ip_combo.clear()
        ips = []
        default_ip = "127.0.0.1"
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                default_ip = s.getsockname()[0]
        except Exception:
            pass
        ips.append(f"⭐ [預設] {default_ip}")

        try:
            host_name = socket.gethostname()
            _, _, host_ips = socket.gethostbyname_ex(host_name)
            for ip in host_ips:
                if ip != default_ip and not ip.startswith("127."):
                    ips.append(f"🌐 {ip}")
        except Exception:
            pass
        ips.append("🏠 127.0.0.1 (本機測試)")
        self.ip_combo.addItems(ips)

    def _populate_devices(self):
        import pyaudiowpatch as pyaudio
        self.input_map.clear()
        self.input_combo.clear()

        p = pyaudio.PyAudio()
        try:
            wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)

            in_items = ["⭐ [預設] 系統主聲道"]
            self.input_map[in_items[0]] = "default"
            for loopback in p.get_loopback_device_info_generator():
                name = f"🔊 [擷取] {loopback['name']}"
                in_items.append(name)
                self.input_map[name] = loopback["index"]
            self.input_combo.addItems(in_items)
        finally:
            p.terminate()

    def _is_port_available(self, port):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('0.0.0.0', port))
                return True
        except OSError:
            return False

    def _update_qr_display(self, url):
        if HAS_QR:
            # 1. 建立高容錯率 (ERROR_CORRECT_H) 的 QR Code，確保中間遮擋後仍可掃描
            qr = qrcode.QRCode(
                version=5,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=10,
                border=2,
            )
            qr.add_data(url)
            qr.make(fit=True)

            # 2. 生成 QR Code 圖片
            img_qr = qr.make_image(fill_color="black", back_color="white").convert("RGB")

            # 3. 嘗試嵌入 hacker.png
            try:
                # 載入 icon 並確保支援透明度 (RGBA)
                icon = Image.open("hacker.png").convert("RGBA")

                # 計算 icon 大小 (約為 QR Code 尺寸的 1/4)
                icon_size = (img_qr.size[0] // 4, img_qr.size[1] // 4)
                icon = icon.resize(icon_size, Image.Resampling.LANCZOS)

                # 計算置中的座標位置
                pos = (
                    (img_qr.size[0] - icon_size[0]) // 2,
                    (img_qr.size[1] - icon_size[1]) // 2
                )

                # 把 icon 貼到 QR Code 中央 (使用 icon 作為 mask 處理透明邊緣)
                img_qr.paste(icon, pos, icon)
            except Exception as e:
                print(f"⚠️ 無法載入或嵌入 hacker.png (將顯示一般 QR Code): {e}")

            # 4. 將完成的 QR Code 放大顯示 (從原本的 180 改為 280)
            img_qr = img_qr.resize((280, 280), Image.Resampling.LANCZOS)
            data = img_qr.tobytes("raw", "RGB")
            qi = QImage(data, img_qr.width, img_qr.height, QImage.Format.Format_RGB888)
            self.qr_label.setPixmap(QPixmap.fromImage(qi))

        self.url_label.setText(url)

    def _open_url(self, event):
        webbrowser.open(self.url_label.text())

    def _run_server(self, in_dev_id, port):
        try:
            asyncio.set_event_loop(asyncio.new_event_loop())
            import server, uvicorn
            server.TARGET_DEVICE_ID = in_dev_id

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
        self.port_input.setEnabled(False)
        self.ip_combo.setEnabled(False)
        self.refresh_ip_btn.setEnabled(False)
        self.input_combo.setEnabled(False)

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
        try:
            port = int(self.port_input.text())
        except ValueError:
            return
        if not self._is_port_available(port):
            QMessageBox.warning(self, "Port In Use", f"Port {port} 已被佔用。")
            return

        self.server_running = True
        clean_ip = self.ip_combo.currentText().split()[-1]
        in_dev_id = self.input_map.get(self.input_combo.currentText())
        url = f"http://{clean_ip}:{port}"

        self._update_qr_display(url)
        threading.Thread(target=self._run_server, args=(in_dev_id, port), daemon=True).start()

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
        self.ip_combo.setEnabled(True)
        self.refresh_ip_btn.setEnabled(True)
        self.input_combo.setEnabled(True)

    def closeEvent(self, event):
        self._stop_server()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLESHEET)
    window = AudioStreamApp()
    window.show()
    sys.exit(app.exec())