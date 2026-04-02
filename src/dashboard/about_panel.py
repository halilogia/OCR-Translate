"""
OCR-TRANSLATE — Dashboard About Panel
Uygulamanın çalışma mantığını ve hakkımda bilgilerini içeren panel.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QFrame,
    QHBoxLayout,
    QScrollArea,
)

from i18n import _


class AboutPanel(QWidget):
    """Hakkında Paneli."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel(_("nav_about"))
        title.setFont(QFont("Outfit", 16, QFont.Bold))
        title.setStyleSheet(
            "color: #00e5ff; border: none; background: transparent; margin-bottom: 10px;"
        )
        layout.addWidget(title)

        # Scroll Area for longer content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        cl = QVBoxLayout(container)
        cl.setContentsMargins(0, 0, 10, 0)
        cl.setSpacing(15)

        # Description Card
        desc_card = QFrame()
        desc_card.setStyleSheet(
            "QFrame { background: #12121a; border-radius: 18px; border: 1px solid #252530; }"
        )
        dl = QVBoxLayout(desc_card)

        desc_title = QLabel(_("about_title"))
        desc_title.setFont(QFont("Outfit", 12, QFont.Bold))
        desc_title.setStyleSheet("color: #fff; border: none;")
        dl.addWidget(desc_title)

        desc_text = QLabel(_("about_desc"))
        desc_text.setWordWrap(True)
        desc_text.setStyleSheet(
            "color: #aaa; border: none; font-size: 11px; line-height: 1.4;"
        )
        dl.addWidget(desc_text)

        cl.addWidget(desc_card)

        # How it Works Card
        how_card = QFrame()
        how_card.setStyleSheet(
            "QFrame { background: #12121a; border-radius: 18px; border: 1px solid #252530; }"
        )
        hl = QVBoxLayout(how_card)

        how_title = QLabel(_("how_it_works"))
        how_title.setFont(QFont("Outfit", 12, QFont.Bold))
        how_title.setStyleSheet("color: #00e5ff; border: none;")
        hl.addWidget(how_title)

        for i in range(1, 5):
            step = QLabel(_(f"step_{i}"))
            step.setWordWrap(True)
            step.setStyleSheet(
                "color: #ccc; border: none; font-size: 10px; margin-top: 5px;"
            )
            hl.addWidget(step)

        cl.addWidget(how_card)

        # Info Card
        info_card = QFrame()
        info_card.setStyleSheet(
            "QFrame { background: #0a0a14; border-radius: 18px; border: 1px solid #1a1a25; }"
        )
        il = QVBoxLayout(info_card)

        version = QLabel(_("about_version"))
        version.setStyleSheet("color: #555; font-size: 10px; border: none;")
        il.addWidget(version)

        author = QLabel(_("about_author"))
        author.setStyleSheet("color: #555; font-size: 10px; border: none;")
        il.addWidget(author)

        cl.addWidget(info_card)
        cl.addStretch()

        scroll.setWidget(container)
        layout.addWidget(scroll)
