"""
OCR-TRANSLATE — Main Dashboard Window
Uygulamanın ana penceresi ve panel orkestrasyonu.
"""

import logging
import subprocess
import time
from typing import Optional, List

from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QColor, QPainter, QLinearGradient, QRadialGradient
from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QGraphicsDropShadowEffect,
    QStackedWidget,
    QPushButton,
    QApplication,
    QMenu,
    QAction,
)

import config
import storage
from i18n import _

from .widgets import NavButton
from .home_panel import HomePanel
from .settings_panel import SettingsPanel
from .shortcuts_panel import ShortcutsPanel
from .about_panel import AboutPanel

logger = logging.getLogger(__name__)


class MainDashboard(QMainWindow):
    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    region_change_requested = pyqtSignal()
    window_selection_requested = pyqtSignal()
    model_changed = pyqtSignal(str)
    engine_changed = pyqtSignal(str)
    overlay_mode_changed = pyqtSignal(str)
    capture_method_changed = pyqtSignal(str)
    interval_changed = pyqtSignal(int)
    show_source_changed = pyqtSignal(bool)
    exit_requested = pyqtSignal()

    def __init__(
        self, model_name: Optional[str] = None, interval: Optional[int] = None
    ) -> None:
        super().__init__()
        # Ayarları yükle
        settings = storage.load_settings()
        self._model_name = (
            model_name if model_name else settings.get("model", config.OLLAMA_MODEL)
        )
        self._vision_model = settings.get("vision_model", config.VISION_MODEL)
        self._interval = (
            interval
            if interval
            else settings.get("interval", config.CAPTURE_INTERVAL_MS)
        )
        self._ocr_engine = settings.get("ocr_engine_type", config.OCR_ENGINE_TYPE)
        self._overlay_mode = settings.get("overlay_mode", config.OVERLAY_MODE)
        self._capture_method = settings.get("capture_method", config.CAPTURE_METHOD)
        self._enable_refiner = settings.get("enable_refiner", config.ENABLE_REFINER)
        self._show_source_text = settings.get(
            "show_source_text", config.SHOW_SOURCE_TEXT
        )

        self._is_running = False
        self._setup_ui()
        self._connect_signals()

        self.refresh_ollama_status()

    def _setup_ui(self) -> None:
        self.setWindowTitle("OCR-TRANSLATE")
        self.setFixedSize(580, 750)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.central_widget.setStyleSheet(
            f"QWidget {{ background-color: #0f0f1a; border-radius: 20px; border: 1px solid #2a2a3a; }}"
        )

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(0, 0, 0, 200))
        shadow.setOffset(0, 5)
        self.central_widget.setGraphicsEffect(shadow)

        self.layout = QHBoxLayout(self.central_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # Sidebar
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(75)
        self.sidebar.setStyleSheet(
            "QFrame { background: #0a0a14; border-right: 1px solid #222; border-top-left-radius: 20px; border-bottom-left-radius: 20px; }"
        )
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(0, 20, 0, 20)
        self.sidebar_layout.setSpacing(5)

        self.nav_home = NavButton("🏠", _("nav_home"), active=True)
        self.nav_settings = NavButton("⚙️", _("nav_settings"))
        self.nav_shortcuts = NavButton("⌨️", _("nav_shortcuts"))
        self.nav_about = NavButton("ℹ️", _("nav_about"))

        self.sidebar_layout.addWidget(self.nav_home)
        self.sidebar_layout.addWidget(self.nav_settings)
        self.sidebar_layout.addWidget(self.nav_shortcuts)
        self.sidebar_layout.addWidget(self.nav_about)
        self.sidebar_layout.addStretch()

        self.btn_quit = QPushButton("\u2715")
        self.btn_quit.setFixedSize(30, 30)
        self.btn_quit.setCursor(Qt.PointingHandCursor)
        self.btn_quit.setStyleSheet(
            "QPushButton { border: none; color: #444; font-size: 18px; } QPushButton:hover { color: #ff5252; }"
        )
        self.btn_quit.clicked.connect(self.hide)
        self.sidebar_layout.addWidget(self.btn_quit, alignment=Qt.AlignCenter)

        self.layout.addWidget(self.sidebar)

        # Content Area
        self.stack = QStackedWidget()
        self.home_page = HomePanel()
        self.settings_page = SettingsPanel()
        self.shortcuts_page = ShortcutsPanel()
        self.about_page = AboutPanel()

        self.stack.addWidget(self.home_page)
        self.stack.addWidget(self.settings_page)
        self.stack.addWidget(self.shortcuts_page)
        self.stack.addWidget(self.about_page)
        self.layout.addWidget(self.stack)

        # Expose widgets for easy access
        self.model_combo = self.settings_page.model_combo
        self.engine_combo = self.settings_page.engine_combo
        self.overlay_combo = self.settings_page.overlay_combo
        self.method_combo = self.settings_page.method_combo
        self.interval_spin = self.settings_page.interval_spin
        self.btn_refresh = self.settings_page.btn_refresh
        self.btn_ollama_start = self.settings_page.btn_ollama_start
        self.btn_model_test = self.settings_page.btn_model_test
        self.vision_combo = self.settings_page.vision_combo
        self.refiner_check = self.settings_page.refiner_check
        self.bubble_check = self.settings_page.bubble_check
        self.ui_filter_check = self.settings_page.ui_filter_check
        self.show_source_check = self.settings_page.show_source_check
        self.ollama_status = self.home_page.ollama_status
        self.target_label = self.home_page.target_label
        self.btn_toggle = self.home_page.btn_toggle
        self.btn_region = self.home_page.btn_region
        self.btn_window = self.home_page.btn_window

        # Initial Values
        self.interval_spin.setValue(self._interval)
        self.show_source_check.setChecked(self._show_source_text)

        idx_e = self.engine_combo.findText(self._ocr_engine)
        if idx_e >= 0:
            self.engine_combo.setCurrentIndex(idx_e)

        idx_o = self.overlay_combo.findText(self._overlay_mode)
        if idx_o >= 0:
            self.overlay_combo.setCurrentIndex(idx_o)

        self.home_page._on_output_mode_changed(self._overlay_mode, silent=True)

        idx_c = self.method_combo.findData(self._capture_method)
        if idx_c >= 0:
            self.method_combo.setCurrentIndex(idx_c)

        self.refiner_check.setChecked(self._enable_refiner)
        self.bubble_check.setChecked(getattr(config, "ENABLE_BUBBLE_DETECTION", False))
        self.ui_filter_check.setChecked(getattr(config, "ENABLE_UI_FILTER", True))

    def _connect_signals(self) -> None:
        self.nav_home.clicked.connect(lambda: self._switch_page(0))
        self.nav_settings.clicked.connect(lambda: self._switch_page(1))
        self.nav_shortcuts.clicked.connect(lambda: self._switch_page(2))
        self.nav_about.clicked.connect(lambda: self._switch_page(3))

        self.btn_toggle.clicked.connect(self._on_toggle)
        self.btn_region.clicked.connect(self.region_change_requested.emit)
        self.btn_window.clicked.connect(self.window_selection_requested.emit)

        self.model_combo.currentTextChanged.connect(self._on_model_changed)
        self.vision_combo.currentTextChanged.connect(self._on_vision_model_changed)
        self.engine_combo.currentTextChanged.connect(self._on_engine_changed)
        self.overlay_combo.currentTextChanged.connect(self._on_overlay_mode_changed)
        self.home_page.output_mode_changed.connect(self._on_overlay_mode_changed)
        self.method_combo.currentIndexChanged.connect(self._on_capture_method_changed)
        self.refiner_check.toggled.connect(self._on_refiner_toggled)
        self.bubble_check.toggled.connect(self._on_bubble_detection_toggled)
        self.ui_filter_check.toggled.connect(self._on_ui_filter_toggled)
        self.interval_spin.valueChanged.connect(self.interval_changed.emit)
        self.show_source_check.toggled.connect(self.show_source_changed.emit)

        self.btn_refresh.clicked.connect(self.refresh_ollama_status)
        self.btn_ollama_start.clicked.connect(self._start_ollama_service)
        # self.btn_model_test.clicked.connect(self._test_model) # Removed due to missing method

    def _switch_page(self, index: int):
        self.stack.setCurrentIndex(index)
        self.nav_home.setChecked(index == 0)
        self.nav_settings.setChecked(index == 1)
        self.nav_shortcuts.setChecked(index == 2)
        self.nav_about.setChecked(index == 3)

    def _on_toggle(self):
        if self._is_running:
            self.stop_requested.emit()
        else:
            self.start_requested.emit()

    def set_running_state(self, is_running):
        self._is_running = is_running
        if is_running:
            self.btn_toggle.setText("\u23f8 " + _("stop_translate"))
            self.btn_toggle.setStyleSheet(
                self.btn_toggle.styleSheet()
                .replace("#00e5ff", "#f44336")
                .replace("#0078d4", "#d32f2f")
            )
        else:
            self.btn_toggle.setText("\u25b6 " + _("start_translate"))
            self.btn_toggle._apply_style()

    def refresh_ollama_status(self):
        try:
            result = subprocess.run(
                ["ollama", "list"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                self.ollama_status.setText(_("ready"))
                self.ollama_status.setStyleSheet(
                    "color: #4CAF50; font-weight: 900; background: transparent; border: none;"
                )
                self.btn_ollama_start.hide()

                models = []
                lines = result.stdout.strip().split("\n")
                if len(lines) > 1:
                    for line in lines[1:]:
                        parts = line.split()
                        if parts:
                            models.append(parts[0])

                self.model_combo.blockSignals(True)
                self.model_combo.clear()
                self.model_combo.addItem(
                    "Google Translate", "google"
                )  # Google seçeneğini en başa ekle
                self.model_combo.addItems(models)
                self.vision_combo.clear()
                self.vision_combo.addItems(models)

                idx_m = self.model_combo.findText(self._model_name)
                if idx_m >= 0:
                    self.model_combo.setCurrentIndex(idx_m)

                idx_v = self.vision_combo.findText(self._vision_model)
                if idx_v >= 0:
                    self.vision_combo.setCurrentIndex(idx_v)

                self.model_combo.blockSignals(False)
                self.vision_combo.blockSignals(False)
            else:
                self._set_offline_status()
        except Exception:
            self._set_offline_status()

    def _set_offline_status(self):
        self.ollama_status.setText(_("offline"))
        self.ollama_status.setStyleSheet(
            "color: #f44336; font-weight: 900; background: transparent; border: none;"
        )
        self.model_combo.clear()
        self.btn_ollama_start.show()

    def _start_ollama_service(self):
        try:
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.ollama_status.setText(_("starting"))
            self.ollama_status.setStyleSheet(
                "color: #FFC107; font-weight: 900; background: transparent; border: none;"
            )
        except Exception as e:
            logger.error(f"Ollama başlatılamadı: {e}")

    def _on_model_changed(self, text):
        # ComboBox verisinden gerçek değeri al (eğer "Google Translate" seçiliyse "google" döner)
        model_data = self.model_combo.currentData()
        actual_model = model_data if model_data else text

        self._model_name = actual_model
        storage.update_setting("model", actual_model)
        self.model_changed.emit(actual_model)

    def _on_vision_model_changed(self, text):
        self._vision_model = text
        config.VISION_MODEL = text
        storage.update_setting("vision_model", text)

    def _on_engine_changed(self, text):
        config.OCR_ENGINE_TYPE = text
        storage.update_setting("ocr_engine_type", text)
        self.engine_changed.emit(text)

    def _on_overlay_mode_changed(self, text):
        config.OVERLAY_MODE = text
        storage.update_setting("overlay_mode", text)
        self.overlay_mode_changed.emit(text)
        self.home_page._on_output_mode_changed(text, silent=True)
        idx = self.overlay_combo.findText(text)
        if idx >= 0 and self.overlay_combo.currentIndex() != idx:
            self.overlay_combo.blockSignals(True)
            self.overlay_combo.setCurrentIndex(idx)
            self.overlay_combo.blockSignals(False)

    def _on_capture_method_changed(self, index):
        method = self.method_combo.itemData(index)
        self._capture_method = method
        config.CAPTURE_METHOD = method
        storage.update_setting("capture_method", method)
        self.capture_method_changed.emit(method)

    def _on_refiner_toggled(self, checked):
        self._enable_refiner = checked
        config.ENABLE_REFINER = checked
        storage.update_setting("enable_refiner", checked)

    def _on_bubble_detection_toggled(self, checked):
        config.ENABLE_BUBBLE_DETECTION = checked
        storage.update_setting("enable_bubble_detection", checked)

    def _on_ui_filter_toggled(self, checked):
        config.ENABLE_UI_FILTER = checked
        storage.update_setting("enable_ui_filter", checked)

    def set_target_name(self, name: str):
        if name:
            self.target_label.setText(name)
            self.target_label.setStyleSheet(
                "color: #00e5ff; font-size: 11px; font-weight: bold; background: transparent; border: none;"
            )
        else:
            self.target_label.setText(_("no_target_selected"))
            self.target_label.setStyleSheet(
                "color: #aaa; font-size: 11px; font-weight: bold; background: transparent; border: none;"
            )

    def set_capture_mode(self, active: bool):
        if active:
            if self.isVisible():
                self.hide()
                QApplication.processEvents()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.oldPos = event.globalPos()

    def mouseMoveEvent(self, event):
        if hasattr(self, "oldPos"):
            delta = event.globalPos() - self.oldPos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.oldPos = event.globalPos()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #1a1a2e; color: white; border: 1px solid #333; padding: 5px; } QMenu::item:selected { background: #0078d4; }"
        )
        quit_act = QAction(_("tray_exit"), self)
        quit_act.triggered.connect(self.exit_requested.emit)
        menu.addAction(quit_act)
        menu.exec_(event.globalPos())
