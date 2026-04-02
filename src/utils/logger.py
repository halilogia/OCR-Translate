import logging
import os
import sys
import time
import config

logger = logging.getLogger("OCR-TRANSLATE")


def global_log_to_console(
    tag: str, content: str, engine: str = "N/A", model: str = "N/A"
):
    """Merkezi loglama fonksiyonu. (AAA Global)."""
    log_path = os.path.join(os.getcwd(), config.CONSOLE_LOG_FILE)
    timestamp = time.strftime("%H:%M:%S")
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            if tag == "PIPELINE":
                f.write(f"\n{'=' * 20} {timestamp} [PIPELINE] {'=' * 20}\n")
                f.write(f"[Engine: {engine.upper()}] | [Model: {model}]\n")
                f.write(content + "\n")  # Content already formatted
                f.write("-" * 50 + "\n")
            else:
                f.write(f"\n{'=' * 20} {timestamp} [{tag}] {'=' * 20}\n")
                f.write(f"[Engine: {engine.upper()}] | [Model: {model}]\n")
                f.write(content.strip() + "\n")
                f.write("-" * 50 + "\n")
    except Exception as e:
        logger.error(f"Global Log hatası: {e}")


class TeeOutput:
    def __init__(self, original, file):
        self.original = original
        self.file = file

    def write(self, text):
        self.original.write(text)
        self.original.flush()
        try:
            self.file.write(text)
            self.file.flush()
        except:
            pass

    def flush(self):
        self.original.flush()
        try:
            self.file.flush()
        except:
            pass


def setup_terminal_logging():
    """Terminal loglarını dosyaya yönlendirir."""
    terminal_log_path = os.path.join(os.getcwd(), "terminal.log")
    try:
        # Dosyayı sıfırla
        with open(terminal_log_path, "w", encoding="utf-8") as f:
            f.write(
                f"=== {time.strftime('%Y-%m-%d %H:%M:%S')} TERMINAL LOG BAŞLADI ===\n\n"
            )

        # Tüm logging çıktısını dosyaya yönlendir
        file_handler = logging.FileHandler(terminal_log_path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S"
            )
        )

        # Root logger'a ekle
        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)

        log_file = open(terminal_log_path, "a", encoding="utf-8")
        sys.stdout = TeeOutput(sys.__stdout__, log_file)
        sys.stderr = TeeOutput(sys.__stderr__, log_file)

    except Exception as e:
        print(f"Terminal log oluşturulamadı: {e}")


def clear_console_log():
    """Uygulama başlangıcında konsol log dosyasını temizler."""
    log_path = os.path.join(os.getcwd(), config.CONSOLE_LOG_FILE)
    try:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(
                f"=== {time.strftime('%Y-%m-%d %H:%M:%S')} OCR-TRANSLATE LOG BAŞLADI ===\n"
            )
    except Exception:
        pass
