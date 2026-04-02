import os
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QAction
from i18n import _


def create_system_tray(app: QApplication, ocr_app) -> QSystemTrayIcon:
    tray = QSystemTrayIcon()
    logo_path = os.path.join(os.getcwd(), "assets/logo.png")
    if os.path.exists(logo_path):
        tray.setIcon(QIcon(logo_path))
    else:
        pix = QPixmap(64, 64)
        pix.fill(Qt.transparent)
        tray.setIcon(QIcon(pix))

    menu = QMenu()
    menu.setStyleSheet(
        "QMenu { background: #16161B; color: white; border: 1px solid #333; }"
    )
    act_dash = QAction("🏠 " + _("tray_restore"), menu)
    act_dash.triggered.connect(
        lambda: ocr_app._dashboard.show() or ocr_app._dashboard.raise_()
    )
    act_pause = QAction("⏸ " + _("tray_pause"), menu)
    act_pause.triggered.connect(ocr_app.stop)
    act_resume = QAction("▶ " + _("tray_resume"), menu)
    act_resume.triggered.connect(ocr_app.resume)
    act_quit = QAction("❌ " + _("tray_exit"), menu)
    act_quit.triggered.connect(ocr_app.quit_app)
    menu.addAction(act_dash)
    menu.addSeparator()
    menu.addAction(act_pause)
    menu.addAction(act_resume)
    menu.addSeparator()
    menu.addAction(act_quit)
    tray.setContextMenu(menu)
    tray.activated.connect(
        lambda r: ocr_app._dashboard.show() if r == QSystemTrayIcon.Trigger else None
    )
    return tray
