import argparse
import logging
import signal
import sys
import os

# Add 'src' directory to sys.path to ensure modules can be found correctly
src_dir = os.path.dirname(os.path.abspath(__file__))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from PyQt5.QtCore import QSharedMemory
from PyQt5.QtWidgets import QApplication

from app import OCRTranslateApp, create_system_tray
from utils.logger import setup_terminal_logging, clear_console_log
from i18n import _

# Initial basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("OCR-TRANSLATE")


def main() -> None:
    # Setup advanced logging (terminal.log)
    setup_terminal_logging()

    # Clear console log for new session
    clear_console_log()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # Instance lock
    shared_mem = QSharedMemory("OCR_TRANSLATE_LOCK")
    if not shared_mem.create(1):
        shared_mem.attach()
        shared_mem.detach()
        if not shared_mem.create(1):
            logger.warning(_("already_running_msg"))
            sys.exit(0)

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=None)
    parser.add_argument("--interval", type=int, default=None)
    parser.add_argument("--fullscreen", action="store_true")
    args = parser.parse_args()

    ocr_app = OCRTranslateApp(args.model, args.interval, args.fullscreen)
    ocr_app._shared_mem = shared_mem
    ocr_app.run()

    tray = create_system_tray(app, ocr_app)
    tray.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
