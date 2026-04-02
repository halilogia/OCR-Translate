"""
OCR-TRANSLATE — Dashboard Shortcuts Panel
Klavye kısayolları ve kullanım ipuçları ekranı.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QHBoxLayout

from i18n import _

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
