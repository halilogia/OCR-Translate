"""
OCR-TRANSLATE — Dashboard Settings Panel
Uygulama ayarları: Model seçimi, interval, OCR motoru, yakalama yöntemi vb.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QFrame,
    QHBoxLayout,
    QComboBox,
    QSpinBox,
    QCheckBox,
)

from i18n import _
from .widgets import PremiumButton


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
        self.engine_combo.addItem(_("method_auto"), "auto")
        self.engine_combo.addItems(
            ["easyocr", "tesseract", "vision", "manga", "paddle"]
        )
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
        self.method_combo.addItem("Qt Screen", "qt")
        self.method_combo.addItem("Spectacle", "spectacle")
        self.method_combo.addItem("Grim", "grim")
        self.method_combo.addItem("X11 (mss)", "x11")
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

        # Bubble Detection Toggle
        self.bubble_check = QCheckBox(_("enable_bubble_detection"))
        self.bubble_check.setStyleSheet(
            "color: white; font-weight: bold; margin-top: 5px;"
        )
        self.bubble_check.setToolTip(_("bubble_detection_tooltip"))
        sl.addWidget(self.bubble_check)

        # UI Filter Toggle
        self.ui_filter_check = QCheckBox(_("enable_ui_filter"))
        self.ui_filter_check.setStyleSheet(
            "color: white; font-weight: bold; margin-top: 5px;"
        )
        self.ui_filter_check.setToolTip(_("ui_filter_tooltip"))
        self.ui_filter_check.setChecked(True)
        sl.addWidget(self.ui_filter_check)

        # Show Source Text Toggle
        self.show_source_check = QCheckBox(_("enable_show_source_text"))
        self.show_source_check.setStyleSheet(
            "color: white; font-weight: bold; margin-top: 5px;"
        )
        self.show_source_check.setToolTip(_("show_source_text_tooltip"))
        sl.addWidget(self.show_source_check)

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
