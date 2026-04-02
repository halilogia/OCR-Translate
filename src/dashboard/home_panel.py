"""
OCR-TRANSLATE — Dashboard Home Panel
Ana kontrol ekranı, başlat/durdur ve bölge/pencere seçimi.
"""

import os
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap, QFont
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QHBoxLayout, QPushButton

from i18n import _
from .widgets import PremiumButton

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

        self.target_icon = QLabel("\U0001f3af")
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
        self.btn_toggle = PremiumButton("\u25b6 " + _("start_translate"), primary=True)
        layout.addWidget(self.btn_toggle)

        self.btn_region = PremiumButton("\U0001f532 " + _("select_area"))
        layout.addWidget(self.btn_region)

        self.btn_window = PremiumButton(
            "\U0001fa9f " + _("select_window"), color_name="accent_cyan"
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
