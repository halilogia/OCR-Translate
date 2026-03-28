"""
OCR-TRANSLATE — Ana Kontrol Paneli (Dashboard)
Uygulamanın ana yönetim arayüzü.
ULTRA-MODULAR sidebar Edition — AAA Tasarım ve Modüler Mimari.
"""

import os
import subprocess
import logging
import time
from typing import Optional, List
from PyQt5.QtCore import Qt, pyqtSignal, QThread, pyqtSlot, QTimer, QSize
from PyQt5.QtGui import (
    QColor,
    QFont,
    QPixmap,
    QPainter,
    QLinearGradient,
    QRadialGradient,
    QIcon,
)
from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFrame,
    QGraphicsDropShadowEffect,
    QComboBox,
    QSpinBox,
    QMenu,
    QAction,
    QStackedWidget,
    QCheckBox,
    QApplication,
)

import config
import storage
from i18n import _

logger = logging.getLogger(__name__)
T = config.THEME


# region Styled Components
class PremiumButton(QPushButton):
    """Modern ve temiz bir buton stili."""

    def __init__(
        self, text: str, primary: bool = False, color_name: str = "accent_blue"
    ):
        super().__init__(text)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(50)
        self._primary = primary
        self._color = T[color_name]
        self._apply_style()

    def _apply_style(self):
        if self._primary:
            style = f"""
                QPushButton {{
                    background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, 
                        stop:0 {T["accent_cyan"]}, stop:1 {T["accent_blue"]});
                    color: white; border-radius: 12px; font-size: 14px; font-weight: 800; border: none;
                }}
                QPushButton:hover {{
                    background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, 
                        stop:0 {T["accent_blue"]}, stop:1 {T["accent_cyan"]});
                }}
            """
        else:
            style = f"""
                QPushButton {{
                    background-color: #1c1c21;
                    color: #d1d1d1; border-radius: 12px; font-size: 13px; font-weight: 600;
                    border: 1px solid #333;
                }}
                QPushButton:hover {{
                    background-color: #25252b;
                    border-color: {self._color};
                    color: white;
                }}
            """
        self.setStyleSheet(style + "QPushButton:pressed { background: #000; }")


class NavButton(QPushButton):
    """Sidebar navigasyon butonu."""

    def __init__(self, icon_text: str, label: str, active: bool = False):
        super().__init__()
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(65, 65)

        self.icon_label = QLabel(icon_text, self)
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setFixedSize(65, 45)
        self.icon_label.setStyleSheet(
            "font-size: 20px; color: #888; background: transparent; border: none;"
        )

        self.text_label = QLabel(label, self)
        self.text_label.setAlignment(Qt.AlignCenter)
        self.text_label.setFixedSize(65, 20)
        self.text_label.move(0, 40)
        self.text_label.setStyleSheet(
            "font-size: 8px; font-weight: 800; color: #555; background: transparent; border: none;"
        )

        self._active = active
        self._update_style()

    def _update_style(self):
        color = "#00e5ff" if self.isChecked() else "transparent"
        border = f"3px solid {color}" if self.isChecked() else "none"
        self.setStyleSheet(f"""
            QPushButton {{ 
                background: {color if self.isChecked() else "transparent"}; 
                border-left: {border}; 
                border-radius: 0px; 
            }}
            QPushButton:hover {{ background: rgba(0, 229, 255, 0.1); }}
        """)
        icon_color = "white" if self.isChecked() else "#888"
        text_color = "white" if self.isChecked() else "#555"
        self.icon_label.setStyleSheet(
            f"font-size: 20px; color: {icon_color}; background: transparent; border: none;"
        )
        self.text_label.setStyleSheet(
            f"font-size: 8px; font-weight: 800; color: {text_color}; background: transparent; border: none;"
        )

    def setChecked(self, checked: bool):
        super().setChecked(checked)
        self._update_style()


# endregion


# region Panels
class HomePanel(QWidget):
    """Ana Kontrol Paneli."""

    output_mode_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Logo & Title
        self.logo = QLabel()
        logo_path = os.path.join(os.getcwd(), "assets/logo.png")
        if os.path.exists(logo_path):
            pix = QPixmap(logo_path).scaled(
                80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.logo.setPixmap(pix)
        self.logo.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self.logo, alignment=Qt.AlignCenter)

        title = QLabel(_("dashboard_title"))
        title.setFont(QFont("Outfit", 18, QFont.Black))
        title.setStyleSheet("color: white; border: none; background: transparent;")
        layout.addWidget(title, alignment=Qt.AlignCenter)

        # Engine Status Card
        self.status_card = QFrame()
        self.status_card.setStyleSheet(
            "QFrame { background: #12121a; border-radius: 18px; border: 1px solid #252530; }"
        )
        sl = QVBoxLayout(self.status_card)
        sl.setContentsMargins(20, 15, 20, 15)

        st_row = QHBoxLayout()
        st_label = QLabel(_("engine_status_label"))
        st_label.setStyleSheet(
            "color: #888; font-size: 11px; font-weight: bold; border: none; background: transparent;"
        )
        st_row.addWidget(st_label)
        st_row.addStretch()
        self.ollama_status = QLabel(_("ready"))
        self.ollama_status.setStyleSheet(
            "color: #4CAF50; font-weight: 900; border: none; background: transparent;"
        )
        st_row.addWidget(self.ollama_status)
        sl.addLayout(st_row)

        layout.addWidget(self.status_card)

        # Target Window Status (NEW)
        self.target_card = QFrame()
        self.target_card.setStyleSheet(
            "QFrame { background: #1a1a25; border-radius: 12px; border: 1px dashed #353545; }"
        )
        tl = QHBoxLayout(self.target_card)
        tl.setContentsMargins(15, 8, 15, 8)

        self.target_icon = QLabel("🎯")
        self.target_icon.setStyleSheet(
            "font-size: 14px; background: transparent; border: none;"
        )
        tl.addWidget(self.target_icon)

        self.target_label = QLabel(_("no_target_selected"))
        self.target_label.setStyleSheet(
            "color: #aaa; font-size: 11px; font-weight: bold; background: transparent; border: none;"
        )
        self.target_label.setWordWrap(True)
        tl.addWidget(self.target_label, 1)

        layout.addWidget(self.target_card)

        # Main Actions
        self.btn_toggle = PremiumButton("▶ " + _("start_translate"), primary=True)
        layout.addWidget(self.btn_toggle)

        self.btn_region = PremiumButton("🔲 " + _("select_area"))
        layout.addWidget(self.btn_region)

        self.btn_window = PremiumButton(
            "🪟 " + _("select_window"), color_name="accent_cyan"
        )
        layout.addWidget(self.btn_window)

        # Output Mode Selector
        mode_card = QFrame()
        mode_card.setStyleSheet(
            "QFrame { background: #12121a; border-radius: 12px; border: 1px solid #252530; }"
        )
        mc = QVBoxLayout(mode_card)
        mc.setContentsMargins(15, 10, 15, 10)
        mc.setSpacing(8)

        mode_title = QLabel(_("output_mode_label"))
        mode_title.setStyleSheet(
            "color: #888; font-size: 10px; font-weight: bold; border: none; background: transparent;"
        )
        mc.addWidget(mode_title)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.btn_mode_inplace = QPushButton(_("output_mode_inplace"))
        self.btn_mode_inplace.setCheckable(True)
        self.btn_mode_inplace.setCursor(Qt.PointingHandCursor)
        self.btn_mode_inplace.setFixedHeight(36)
        self.btn_mode_inplace.setStyleSheet(self._mode_btn_style(True))
        self.btn_mode_inplace.clicked.connect(
            lambda: self._on_output_mode_changed("inplace")
        )
        btn_row.addWidget(self.btn_mode_inplace)

        self.btn_mode_below = QPushButton(_("output_mode_below"))
        self.btn_mode_below.setCheckable(True)
        self.btn_mode_below.setCursor(Qt.PointingHandCursor)
        self.btn_mode_below.setFixedHeight(36)
        self.btn_mode_below.setStyleSheet(self._mode_btn_style(False))
        self.btn_mode_below.clicked.connect(
            lambda: self._on_output_mode_changed("bottom")
        )
        btn_row.addWidget(self.btn_mode_below)

        mc.addLayout(btn_row)

        self.mode_desc = QLabel(_("output_mode_inplace_desc"))
        self.mode_desc.setStyleSheet(
            "color: #555; font-size: 10px; border: none; background: transparent;"
        )
        self.mode_desc.setWordWrap(True)
        mc.addWidget(self.mode_desc)

        layout.addWidget(mode_card)

        layout.addStretch()

    def _mode_btn_style(self, active: bool) -> str:
        if active:
            return """
                QPushButton {
                    background: rgba(0,229,255,0.15); color: #00e5ff;
                    border-radius: 8px; font-size: 11px; font-weight: 800;
                    border: 1px solid rgba(0,229,255,0.4);
                }
                QPushButton:hover { background: rgba(0,229,255,0.25); }
            """
        return """
            QPushButton {
                background: #1c1c21; color: #666;
                border-radius: 8px; font-size: 11px; font-weight: 800;
                border: 1px solid #333;
            }
            QPushButton:hover { background: #25252b; color: #aaa; }
        """

    def _on_output_mode_changed(self, mode: str, silent: bool = False):
        self.btn_mode_inplace.setChecked(mode == "inplace")
        self.btn_mode_inplace.setStyleSheet(self._mode_btn_style(mode == "inplace"))
        self.btn_mode_below.setChecked(mode == "bottom")
        self.btn_mode_below.setStyleSheet(self._mode_btn_style(mode == "bottom"))
        if mode == "inplace":
            self.mode_desc.setText(_("output_mode_inplace_desc"))
        else:
            self.mode_desc.setText(_("output_mode_below_desc"))
        if not silent:
            self.output_mode_changed.emit(mode)


class SettingsPanel(QWidget):
    """Ayarlar Paneli."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel(_("nav_settings"))
        title.setFont(QFont("Outfit", 16, QFont.Bold))
        title.setStyleSheet(
            "color: #00e5ff; border: none; background: transparent; margin-bottom: 10px;"
        )
        layout.addWidget(title)

        # Settings Card
        self.card = QFrame()
        self.card.setStyleSheet(
            "QFrame { background: #12121a; border-radius: 18px; border: 1px solid #252530; }"
        )
        sl = QVBoxLayout(self.card)
        sl.setContentsMargins(20, 20, 20, 20)
        sl.setSpacing(12)

        # Translation Model
        sl.addWidget(
            QLabel(
                _("model_label"),
                self,
                styleSheet="color: #888; font-size: 10px; font-weight: bold;",
            )
        )
        self.model_combo = QComboBox()
        self.model_combo.setFixedHeight(40)
        self.model_combo.setStyleSheet(self._combo_style())
        sl.addWidget(self.model_combo)

        # Interval
        ir = QHBoxLayout()
        ir.addWidget(
            QLabel(
                _("interval_label"),
                self,
                styleSheet="color: #888; font-size: 10px; font-weight: bold;",
            )
        )
        ir.addStretch()
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(10, 5000)
        self.interval_spin.setSuffix(" ms")
        self.interval_spin.setStyleSheet(self._spin_style())
        ir.addWidget(self.interval_spin)
        sl.addLayout(ir)

        # OCR Engine
        er = QHBoxLayout()
        er.addWidget(
            QLabel(
                _("ocr_engine_label"),
                self,
                styleSheet="color: #888; font-size: 10px; font-weight: bold;",
            )
        )
        er.addStretch()
        self.engine_combo = QComboBox()
        self.engine_combo.setFixedWidth(120)
        self.engine_combo.addItems(["easyocr", "tesseract", "vision"])
        self.engine_combo.setStyleSheet(self._combo_style())
        er.addWidget(self.engine_combo)
        sl.addLayout(er)

        # Capture Method
        cmr = QHBoxLayout()
        cmr.addWidget(
            QLabel(
                _("capture_method_label"),
                self,
                styleSheet="color: #888; font-size: 10px; font-weight: bold;",
            )
        )
        cmr.addStretch()
        self.method_combo = QComboBox()
        self.method_combo.setFixedWidth(120)
        self.method_combo.setStyleSheet(self._combo_style())
        self.method_combo.addItem(_("method_auto"), "auto")
        self.method_combo.addItem(_("method_aura"), "aura")
        self.method_combo.addItem(_("method_kde"), "kde")
        cmr.addWidget(self.method_combo)
        sl.addLayout(cmr)

        # Overlay Style
        osr = QHBoxLayout()
        osr.addWidget(
            QLabel(
                _("overlay_style_label"),
                self,
                styleSheet="color: #888; font-size: 10px; font-weight: bold;",
            )
        )
        osr.addStretch()
        self.overlay_combo = QComboBox()
        self.overlay_combo.setFixedWidth(120)
        self.overlay_combo.addItems(["bottom", "inplace"])
        self.overlay_combo.setStyleSheet(self._combo_style())
        osr.addWidget(self.overlay_combo)
        sl.addLayout(osr)

        # Vision Model (Ultra Mode)
        vrl = QHBoxLayout()
        vrl.addWidget(
            QLabel(
                _("vision_model_label"),
                self,
                styleSheet="color: #888; font-size: 10px; font-weight: bold;",
            )
        )
        vrl.addStretch()
        self.vision_combo = QComboBox()
        self.vision_combo.setFixedWidth(120)
        self.vision_combo.setStyleSheet(self._combo_style())
        vrl.addWidget(self.vision_combo)
        sl.addLayout(vrl)

        # AI Refiner Toggle
        self.refiner_check = QCheckBox(_("enable_refiner"))
        self.refiner_check.setStyleSheet(
            "color: white; font-weight: bold; margin-top: 10px;"
        )
        sl.addWidget(self.refiner_check)

        layout.addWidget(self.card)

        # Diagnostics Panel
        self.btn_refresh = PremiumButton(_("refresh_status"), color_name="accent_blue")
        self.btn_refresh.setFixedHeight(40)
        self.btn_ollama_start = PremiumButton(_("start_ollama"), color_name="success")
        self.btn_ollama_start.setFixedHeight(40)
        self.btn_model_test = PremiumButton(
            _("test_diagnostic"), color_name="accent_purple"
        )
        self.btn_model_test.setFixedHeight(40)

        layout.addWidget(self.btn_refresh)
        layout.addWidget(self.btn_ollama_start)
        layout.addWidget(self.btn_model_test)

        layout.addStretch()

    def _combo_style(self):
        return """
            QComboBox { background: #0a0a10; color: white; border-radius: 10px; padding: 5px 15px; border: 1px solid #333; }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView { background: #12121a; color: white; selection-background-color: #0078d4; outline: none; }
        """

    def _spin_style(self):
        return "QSpinBox { background: #0a0a10; color: white; border-radius: 8px; padding: 5px 10px; border: 1px solid #333; font-weight: bold; }"


class ShortcutsPanel(QWidget):
    """Kısayollar ve İpuçları Paneli."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel(_("shortcuts_title"))
        title.setFont(QFont("Outfit", 16, QFont.Bold))
        title.setStyleSheet(
            "color: #00e5ff; border: none; background: transparent; margin-bottom: 5px;"
        )
        layout.addWidget(title)

        # Shortcuts Card
        card = QFrame()
        card.setStyleSheet(
            "QFrame { background: #12121a; border-radius: 18px; border: 1px solid #252530; }"
        )
        sl = QVBoxLayout(card)
        sl.setContentsMargins(20, 15, 20, 15)
        sl.setSpacing(10)

        shortcuts = [
            ("F5", _("shortcut_start_stop"), _("shortcut_start_stop_desc")),
            ("F6", _("shortcut_select_area"), _("shortcut_select_area_desc")),
            ("F7", _("shortcut_select_window"), _("shortcut_select_window_desc")),
            ("F8", _("shortcut_toggle_dashboard"), _("shortcut_toggle_dashboard_desc")),
            ("Esc", _("shortcut_stop"), _("shortcut_stop_desc")),
        ]

        for key, name, desc in shortcuts:
            row = QHBoxLayout()
            row.setSpacing(12)

            key_lbl = QLabel(key)
            key_lbl.setFixedSize(44, 30)
            key_lbl.setAlignment(Qt.AlignCenter)
            key_lbl.setStyleSheet(
                "font-size: 11px; font-weight: 900; color: #00e5ff; background: #1c1c21; border-radius: 8px; border: 1px solid #333;"
            )
            row.addWidget(key_lbl)

            text_col = QVBoxLayout()
            text_col.setSpacing(1)
            name_lbl = QLabel(name)
            name_lbl.setStyleSheet(
                "color: #e0e0e0; font-size: 12px; font-weight: 800; border: none; background: transparent;"
            )
            text_col.addWidget(name_lbl)
            desc_lbl = QLabel(desc)
            desc_lbl.setStyleSheet(
                "color: #666; font-size: 10px; border: none; background: transparent;"
            )
            desc_lbl.setWordWrap(True)
            text_col.addWidget(desc_lbl)
            row.addLayout(text_col, 1)

            sl.addLayout(row)

        layout.addWidget(card)

        # Overlay Modes Card
        overlay_card = QFrame()
        overlay_card.setStyleSheet(
            "QFrame { background: #12121a; border-radius: 18px; border: 1px solid #252530; }"
        )
        ol = QVBoxLayout(overlay_card)
        ol.setContentsMargins(20, 15, 20, 15)
        ol.setSpacing(8)

        ol_title = QLabel(_("shortcut_overlay_modes"))
        ol_title.setStyleSheet(
            "color: #888; font-size: 10px; font-weight: bold; border: none; background: transparent;"
        )
        ol.addWidget(ol_title)

        modes = [
            ("BOTTOM", _("shortcut_overlay_bottom_desc")),
            ("INPLACE", _("shortcut_overlay_inplace_desc")),
        ]
        for mode_name, mode_desc in modes:
            row = QHBoxLayout()
            row.setSpacing(10)
            badge = QLabel(mode_name)
            badge.setFixedSize(60, 24)
            badge.setAlignment(Qt.AlignCenter)
            badge.setStyleSheet(
                "font-size: 9px; font-weight: 900; color: #00e5ff; background: rgba(0,229,255,0.1); border-radius: 6px; border: 1px solid rgba(0,229,255,0.3);"
            )
            row.addWidget(badge)
            desc_lbl = QLabel(mode_desc)
            desc_lbl.setStyleSheet(
                "color: #888; font-size: 11px; border: none; background: transparent;"
            )
            desc_lbl.setWordWrap(True)
            row.addWidget(desc_lbl, 1)
            ol.addLayout(row)

        layout.addWidget(overlay_card)

        # Tips Card
        tips_card = QFrame()
        tips_card.setStyleSheet(
            "QFrame { background: #12121a; border-radius: 18px; border: 1px solid #252530; }"
        )
        tl = QVBoxLayout(tips_card)
        tl.setContentsMargins(20, 15, 20, 15)
        tl.setSpacing(8)

        tl_title = QLabel(_("shortcut_tips"))
        tl_title.setStyleSheet(
            "color: #888; font-size: 10px; font-weight: bold; border: none; background: transparent;"
        )
        tl.addWidget(tl_title)

        tips = [
            _("shortcut_tip_1"),
            _("shortcut_tip_2"),
            _("shortcut_tip_3"),
        ]
        for tip in tips:
            tip_lbl = QLabel(f"💡 {tip}")
            tip_lbl.setStyleSheet(
                "color: #aaa; font-size: 11px; border: none; background: transparent;"
            )
            tip_lbl.setWordWrap(True)
            tl.addWidget(tip_lbl)

        layout.addWidget(tips_card)

        layout.addStretch()


# endregion


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

        # region UI Nesneleri (Hızlı Erişim)
        self._is_running = False
        self._setup_ui()
        self._connect_signals()

        self.refresh_ollama_status()

    def _setup_ui(self) -> None:
        self.setWindowTitle("OCR-TRANSLATE")
        self.setFixedSize(580, 750)  # Sidebar ile daha geniş, ama daha kısa (Modüler)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.central_widget.setStyleSheet(
            f"QWidget {{ background-color: #0f0f1a; border-radius: 20px; border: 1px solid #2a2a3a; }}"
        )

        # Shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(0, 0, 0, 200))
        shadow.setOffset(0, 5)
        self.central_widget.setGraphicsEffect(shadow)

        self.layout = QHBoxLayout(self.central_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # region Sidebar
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

        self.sidebar_layout.addWidget(self.nav_home)
        self.sidebar_layout.addWidget(self.nav_settings)
        self.sidebar_layout.addWidget(self.nav_shortcuts)
        self.sidebar_layout.addStretch()

        self.btn_quit = QPushButton("✕")
        self.btn_quit.setFixedSize(30, 30)
        self.btn_quit.setCursor(Qt.PointingHandCursor)
        self.btn_quit.setStyleSheet(
            "QPushButton { border: none; color: #444; font-size: 18px; } QPushButton:hover { color: #ff5252; }"
        )
        self.btn_quit.clicked.connect(self.hide)
        self.sidebar_layout.addWidget(self.btn_quit, alignment=Qt.AlignCenter)

        self.layout.addWidget(self.sidebar)
        # endregion

        # region Content Area
        self.stack = QStackedWidget()
        self.home_page = HomePanel()
        self.settings_page = SettingsPanel()
        self.shortcuts_page = ShortcutsPanel()

        self.stack.addWidget(self.home_page)
        self.stack.addWidget(self.settings_page)
        self.stack.addWidget(self.shortcuts_page)
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
        self.ollama_status = self.home_page.ollama_status
        self.target_label = self.home_page.target_label
        self.btn_toggle = self.home_page.btn_toggle
        self.btn_region = self.home_page.btn_region
        self.btn_window = self.home_page.btn_window

        # Initial Values (Sync with Storage)
        self.interval_spin.setValue(self._interval)

        idx_e = self.engine_combo.findText(self._ocr_engine)
        if idx_e >= 0:
            self.engine_combo.setCurrentIndex(idx_e)

        idx_o = self.overlay_combo.findText(self._overlay_mode)
        if idx_o >= 0:
            self.overlay_combo.setCurrentIndex(idx_o)

        # HomePanel butonlarını da senkronize et
        self.home_page._on_output_mode_changed(self._overlay_mode, silent=True)

        idx_c = self.method_combo.findData(self._capture_method)
        if idx_c >= 0:
            self.method_combo.setCurrentIndex(idx_c)

        self.refiner_check.setChecked(self._enable_refiner)
        # endregion

    def _connect_signals(self) -> None:
        self.nav_home.clicked.connect(lambda: self._switch_page(0))
        self.nav_settings.clicked.connect(lambda: self._switch_page(1))
        self.nav_shortcuts.clicked.connect(lambda: self._switch_page(2))

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
        self.interval_spin.valueChanged.connect(self._on_spin_changed)

        self.btn_refresh.clicked.connect(self.refresh_ollama_status)
        self.btn_ollama_start.clicked.connect(self._start_ollama_service)
        self.btn_model_test.clicked.connect(self._test_model)

    def _switch_page(self, index: int):
        self.stack.setCurrentIndex(index)
        self.nav_home.setChecked(index == 0)
        self.nav_settings.setChecked(index == 1)
        self.nav_shortcuts.setChecked(index == 2)

    def _on_toggle(self):
        if self._is_running:
            self.stop_requested.emit()
        else:
            self.start_requested.emit()

    def set_running_state(self, is_running):
        self._is_running = is_running
        if is_running:
            self.btn_toggle.setText("⏸ " + _("stop_translate"))
            self.btn_toggle.setStyleSheet(
                self.btn_toggle.styleSheet()
                .replace("#00e5ff", "#f44336")
                .replace("#0078d4", "#d32f2f")
            )
        else:
            self.btn_toggle.setText("▶ " + _("start_translate"))
            self.btn_toggle._apply_style()

    # region Logic (Ollama, Test, Storage)
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
        self.ollama_status.setText("OFFLINE")
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
            self.ollama_status.setText("STARTING...")
            self.ollama_status.setStyleSheet(
                "color: #FFC107; font-weight: 900; background: transparent; border: none;"
            )
        except Exception as e:
            logger.error(f"Ollama başlatılamadı: {e}")

    def _on_model_changed(self, text):
        self._model_name = text
        storage.update_setting("model", text)
        self.model_changed.emit(text)

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
        # HomePanel butonlarını senkronize et (silent: döngüye girmemesi için)
        self.home_page._on_output_mode_changed(text, silent=True)

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
        logger.info(
            "[UI] AI Metin Düzeltme (Refiner): %s", "AÇIK" if checked else "KAPALI"
        )

    def set_target_name(self, name: str):
        """Hedef uygulama adını UI'da günceller."""
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
        """Yakalama sırasında dashboard'u gizler. capture_finished'da tekrar gösterilmez; kullanıcı tray'den açar."""
        if active:
            if self.isVisible():
                self.hide()
                QApplication.processEvents()

    def _on_spin_changed(self, val):
        self._interval = val
        storage.update_setting("interval", val)
        self.interval_changed.emit(val)

    def _test_model(self):
        model = self.model_combo.currentText()
        if not model:
            return
        self.btn_model_test.setEnabled(False)
        self.btn_model_test.setText("⌛ TESTING...")
        start_time = time.time()

        def run_test():
            try:
                import requests

                response = requests.post(
                    "http://localhost:11434/api/generate",
                    json={"model": model, "prompt": "hi", "stream": False},
                    timeout=20,
                )
                elapsed = time.time() - start_time
                if response.status_code == 200:
                    self.btn_model_test.setText(f"✅ SUCCESS ({elapsed:.1f}s)")
                else:
                    self.btn_model_test.setText(f"❌ FAILED ({elapsed:.1f}s)")
            except Exception as e:
                self.btn_model_test.setText("❌ OFFLINE")
            self.btn_model_test.setEnabled(True)

        QTimer.singleShot(100, run_test)

    # endregion

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
