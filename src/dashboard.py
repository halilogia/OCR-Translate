"""
OCR-TRANSLATE — Ana Kontrol Paneli (Dashboard)
Uygulamanın ana yönetim arayüzü. 
AAA standartlarında, modern ve elit tasarım.
"""

import json
import logging
import os
import subprocess
from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal, QThread, pyqtSlot, QPropertyAnimation, QRect, QEasingCurve
from PyQt5.QtGui import QColor, QFont, QPixmap, QPainter, QLinearGradient, QIcon
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QGraphicsDropShadowEffect,
    QComboBox, QSpinBox, QMessageBox, QSizeGrip
)

import config

logger = logging.getLogger(__name__)

# region Temalar
T = config.THEME
# endregion

# region Yardımcı Sınıflar

class OllamaChecker(QThread):
    finished = pyqtSignal(bool, list)

    def run(self) -> None:
        try:
            import requests
            base_url = config.OLLAMA_URL.rsplit("/api", 1)[0]
            resp = requests.get(f"{base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
            self.finished.emit(True, models)
        except Exception:
            self.finished.emit(False, [])

class ModelTester(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(self, model: str) -> None:
        super().__init__()
        self._model = model

    def run(self) -> None:
        from translator import test_model_response
        success, message = test_model_response(self._model)
        self.finished.emit(success, message)

class PremiumButton(QPushButton):
    """Gradiyent geçişli, elit görünümlü buton."""
    def __init__(self, text: str, primary: bool = False, color_name: str = "accent_blue"):
        super().__init__(text)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(46)
        self._primary = primary
        self._color = T[color_name]
        self._apply_style()

    def _apply_style(self):
        if self._primary:
            style = f"""
                QPushButton {{
                    background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, 
                        stop:0 {self._color}, stop:1 {T['accent_cyan']});
                    color: white;
                    border-radius: 10px;
                    font-size: 14px;
                    font-weight: 800;
                    border: none;
                }}
                QPushButton:hover {{
                    background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, 
                        stop:0 {T['accent_cyan']}, stop:1 {self._color});
                }}
            """
        else:
            style = f"""
                QPushButton {{
                    background-color: {T['bg_card']};
                    color: {T['text_primary']};
                    border-radius: 10px;
                    font-size: 13px;
                    font-weight: 600;
                    border: 1px solid {T['border']};
                }}
                QPushButton:hover {{
                    border-color: {self._color};
                    background-color: #1A1A1C;
                }}
            """
        self.setStyleSheet(style + "QPushButton:pressed { background-color: #000; } QPushButton:disabled { color: #444; background: #111; border: 1px solid #222; }")

# endregion

class MainDashboard(QMainWindow):
    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    region_change_requested = pyqtSignal()
    model_changed = pyqtSignal(str)
    interval_changed = pyqtSignal(int)

    def __init__(self, model_name: str = config.OLLAMA_MODEL) -> None:
        super().__init__()
        self._model_name = model_name
        self._is_running = False
        self._setup_ui()
        self.refresh_ollama_status()

    def _setup_ui(self) -> None:
        self.setWindowTitle("OCR-TRANSLATE")
        self.setFixedSize(440, 720)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window) # Custom title bar for premium look
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Ana Konteyner (Glass Effect)
        self.container = QFrame(self)
        self.container.setGeometry(10, 10, 420, 700)
        self.container.setStyleSheet(f"""
            QFrame {{
                background-color: {T['bg_dark']};
                border-radius: 20px;
                border: 1px solid {T['border']};
            }}
        """)
        
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 200))
        shadow.setOffset(0, 10)
        self.container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(30, 20, 30, 30)
        layout.setSpacing(15)

        # Title Bar (Drag & Close)
        title_bar = QHBoxLayout()
        title_lbl = QLabel("OCR-TRANSLATE PRO")
        title_lbl.setStyleSheet(f"color: {T['text_secondary']}; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        
        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(24, 24)
        self.btn_close.clicked.connect(self.close)
        self.btn_close.setStyleSheet("QPushButton { border: none; color: #555; } QPushButton:hover { color: #FF5252; }")
        
        title_bar.addWidget(title_lbl)
        title_bar.addStretch()
        title_bar.addWidget(self.btn_close)
        layout.addLayout(title_bar)

        # Header
        logo_container = QVBoxLayout()
        logo_container.setAlignment(Qt.AlignCenter)
        
        self.logo = QLabel()
        logo_path = os.path.join(os.getcwd(), "assets/logo.png")
        if os.path.exists(logo_path):
            pix = QPixmap(logo_path).scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.logo.setPixmap(pix)
        self.logo.setContentsMargins(0, 10, 0, 10)
        logo_container.addWidget(self.logo)
        
        title = QLabel("AI SCREEN TRANSLATE")
        title.setFont(QFont("Sans", 18, QFont.Black))
        title.setStyleSheet(f"color: {T['text_primary']}; margin-bottom: 0px;")
        logo_container.addWidget(title, alignment=Qt.AlignCenter)
        
        badge = QLabel("CACHYOS ELITE EDITION")
        badge.setStyleSheet(f"background: {T['accent_blue']}22; color: {T['accent_blue']}; border-radius: 4px; padding: 2px 8px; font-size: 8px; font-weight: bold;")
        logo_container.addWidget(badge, alignment=Qt.AlignCenter)
        
        layout.addLayout(logo_container)
        layout.addSpacing(10)

        # Ollama Card
        self.ollama_card = self._create_card("🤖 OLLAMA ENGINE")
        cl = QVBoxLayout(self.ollama_card)
        cl.setContentsMargins(20, 20, 20, 20)
        
        st_row = QHBoxLayout()
        st_row.addWidget(QLabel("Service Status:"))
        st_row.addStretch()
        self.ollama_status = QLabel("Checking...")
        self.ollama_status.setStyleSheet(f"color: {T['warning']}; font-weight: bold;")
        st_row.addWidget(self.ollama_status)
        cl.addLayout(st_row)

        self.model_combo = QComboBox()
        self.model_combo.setFixedHeight(40)
        self.model_combo.setStyleSheet(self._combo_style())
        cl.addWidget(self.model_combo)

        btn_row = QHBoxLayout()
        self.btn_refresh = PremiumButton("Refresh")
        self.btn_refresh.setFixedHeight(34)
        self.btn_refresh.clicked.connect(self.refresh_ollama_status)
        
        self.btn_ollama_start = PremiumButton("Start Service", color_name="success")
        self.btn_ollama_start.setFixedHeight(34)
        self.btn_ollama_start.clicked.connect(self._start_ollama_service)
        
        btn_row.addWidget(self.btn_refresh)
        btn_row.addWidget(self.btn_ollama_start)
        cl.addLayout(btn_row)
        
        self.btn_model_test = PremiumButton("🧪 Test Model", color_name="accent_purple")
        self.btn_model_test.setFixedHeight(34)
        self.btn_model_test.clicked.connect(self._test_model)
        cl.addWidget(self.btn_model_test)
        
        self.model_test_status = QLabel("")
        self.model_test_status.setWordWrap(True)
        self.model_test_status.setStyleSheet(f"color: {T['text_secondary']}; font-size: 10px; font-style: italic;")
        cl.addWidget(self.model_test_status)
        
        layout.addWidget(self.ollama_card)

        # Settings Card
        self.settings_card = self._create_card("⚙️ SESSION SETTINGS")
        sl = QVBoxLayout(self.settings_card)
        sl.setContentsMargins(20, 20, 20, 20)
        
        ir = QHBoxLayout()
        ir.addWidget(QLabel("Scan Interval:"))
        ir.addStretch()
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(300, 5000)
        self.interval_spin.setSuffix(" ms")
        self.interval_spin.setValue(config.CAPTURE_INTERVAL_MS)
        self.interval_spin.setStyleSheet(self._spin_style())
        self.interval_spin.valueChanged.connect(self.interval_changed.emit)
        ir.addWidget(self.interval_spin)
        sl.addLayout(ir)
        
        sr = QHBoxLayout()
        sr.addWidget(QLabel("Live Status:"))
        sr.addStretch()
        self.run_status = QLabel("● Ready")
        self.run_status.setStyleSheet(f"color: {T['text_secondary']}; font-weight: bold;")
        sr.addWidget(self.run_status)
        sl.addLayout(sr)
        
        layout.addWidget(self.settings_card)

        # Main Actions
        self.btn_toggle = PremiumButton("▶ START TRANSLATION", primary=True)
        self.btn_toggle.clicked.connect(self._on_toggle)
        layout.addWidget(self.btn_toggle)

        self.btn_region = PremiumButton("🔲 SELECT REGION")
        self.btn_region.clicked.connect(self.region_change_requested.emit)
        layout.addWidget(self.btn_region)

        layout.addStretch()

    # region UI Helpers
    def _create_card(self, title: str):
        card = QFrame()
        card.setStyleSheet(f"background: {T['bg_card']}; border-radius: 12px; border: 1px solid {T['border']};")
        return card

    def _combo_style(self):
        return f"""
            QComboBox {{
                background: {T['bg_dark']}; color: {T['text_primary']};
                border: 1px solid {T['border']}; border-radius: 8px; padding: 5px 15px;
            }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox QAbstractItemView {{ background: {T['bg_card']}; selection-background-color: {T['accent_blue']}; }}
        """

    def _spin_style(self):
        return f"QSpinBox {{ background: {T['bg_dark']}; color: {T['text_primary']}; border: 1px solid {T['border']}; border-radius: 6px; padding: 4px; }}"

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.oldPos = event.globalPos()

    def mouseMoveEvent(self, event):
        if hasattr(self, 'oldPos'):
            delta = event.globalPos() - self.oldPos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.oldPos = event.globalPos()

    # endregion

    # region Logic (Ollama & Sessions)
    def refresh_ollama_status(self):
        self.ollama_status.setText("Checking Engine...")
        self.ollama_status.setStyleSheet(f"color: {T['warning']};")
        self.btn_refresh.setEnabled(False)
        self._checker = OllamaChecker()
        self._checker.finished.connect(self._on_ollama_checked)
        self._checker.start()

    @pyqtSlot(bool, list)
    def _on_ollama_checked(self, connected, models):
        self.btn_refresh.setEnabled(True)
        if connected:
            self.ollama_status.setText("ONLINE")
            self.ollama_status.setStyleSheet(f"color: {T['success']};")
            self.btn_ollama_start.setEnabled(False)
            self.btn_ollama_start.setText("Connected")
            
            curr = self.model_combo.currentText()
            self.model_combo.blockSignals(True)
            self.model_combo.clear()
            for m in sorted(models): self.model_combo.addItem(m)
            idx = self.model_combo.findText(curr)
            if idx >= 0: self.model_combo.setCurrentIndex(idx)
            self.model_combo.blockSignals(False)
            
            new_m = self.model_combo.currentText()
            if new_m and new_m != self._model_name:
                self._model_name = new_m
                self.model_changed.emit(new_m)
        else:
            self.ollama_status.setText("OFFLINE")
            self.ollama_status.setStyleSheet(f"color: {T['error']};")
            self.btn_ollama_start.setEnabled(True)
            self.btn_ollama_start.setText("Start Service")

    def _start_ollama_service(self):
        subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        self.btn_ollama_start.setText("Launching...")
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(4000, self.refresh_ollama_status)

    def _test_model(self):
        m = self.model_combo.currentText()
        if not m: return
        self.btn_model_test.setEnabled(False)
        self.model_test_status.setText("Pinging model...")
        self._tester = ModelTester(m)
        self._tester.finished.connect(self._on_model_tested)
        self._tester.start()

    @pyqtSlot(bool, str)
    def _on_model_tested(self, ok, msg):
        self.btn_model_test.setEnabled(True)
        if ok:
            self.model_test_status.setText(f"Success: {msg}")
            self.model_test_status.setStyleSheet(f"color: {T['success']}; font-size: 10px;")
        else:
            self.model_test_status.setText(f"Error: {msg}")
            self.model_test_status.setStyleSheet(f"color: {T['error']}; font-size: 10px;")

    def _on_model_changed(self, text):
        if text != self._model_name:
            self._model_name = text
            self.model_changed.emit(text)
            self.model_test_status.setText("")

    def _on_toggle(self):
        if self._is_running: self.stop_requested.emit()
        else: self.start_requested.emit()

    def set_running_state(self, is_running):
        self._is_running = is_running
        if is_running:
            self.btn_toggle.setText("⏸ STOP TRANSLATION")
            self.btn_toggle.set_color(T['error'], T['error'])
            self.run_status.setText("● TRANSLATING")
            self.run_status.setStyleSheet(f"color: {T['success']}; font-weight: bold;")
        else:
            self.btn_toggle.setText("▶ START TRANSLATION")
            self.btn_toggle._apply_style() # Back to blue gradient
            self.run_status.setText("● Ready")
            self.run_status.setStyleSheet(f"color: {T['text_secondary']};")
    # endregion
