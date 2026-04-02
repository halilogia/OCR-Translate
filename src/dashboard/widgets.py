"""
OCR-TRANSLATE — Dashboard Widgets
Modern ve stilize edilmiş UI bileşenleri: PremiumButton ve NavButton.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QPushButton, QLabel

import config

T = config.THEME

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
