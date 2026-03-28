import os
import subprocess
import time
import logging
import re
from typing import Optional, Dict

from PyQt5.QtDBus import QDBusInterface, QDBusReply, QDBusConnection, QDBusMessage
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

logger = logging.getLogger("AuraEngine")

class AuraPipewireEngine(QObject):
    """
    KDE/Wayland üzerinde Pipewire Portallarını kullanarak arka plan pencere yakalama motoru.
    (Sovereign Quality - Elite Engine).
    """
    node_ready = pyqtSignal(int)  # Pipewire Node ID
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.portal_dest = "org.freedesktop.portal.Desktop"
        self.portal_path = "/org/freedesktop/portal/desktop"
        self.portal_iface = "org.freedesktop.portal.ScreenCast"
        
        self.session_handle = ""
        self.bus = QDBusConnection.sessionBus()
        
        # Portal yanıtlarını (signals) dinle
        self.bus.connect(
            "org.freedesktop.portal.Desktop",
            "",
            "org.freedesktop.portal.Response",
            "Response",
            self._on_portal_response
        )

    def start_aura(self):
        """Aura Engine handshake sürecini başlatır."""
        logger.info("Aura: Portal Handshake (CreateSession) başlatılıyor...")
        self._call_portal("CreateSession", {"session_handle_token": "aura_session"})

    def _call_portal(self, method: str, options: dict, extra_args: list = []):
        msg = QDBusMessage.createMethodCall(
            self.portal_dest, self.portal_path, self.portal_iface, method
        )
        args = extra_args + [options]
        msg.setArguments(args)
        self.bus.send(msg)

    @pyqtSlot(int, 'QVariantMap')
    def _on_portal_response(self, response_code: int, results: dict):
        """Portal'dan gelen asenkron yanıtları işler."""
        if response_code != 0:
            self.error_occurred.emit(f"Portal hatası (Kod: {response_code})")
            return

        # 1. CreateSession Yanıtı
        if "session_handle" in results and not self.session_handle:
            self.session_handle = results["session_handle"]
            logger.info(f"Aura: Oturum oluşturuldu -> {self.session_handle}")
            # 2. SelectSources
            self._call_portal("SelectSources", {
                "types": 2, # 2 = Window (Sovereign Choice)
                "multiple": False,
                "cursor_mode": 1 # 1 = Hidden (AAA Visuals)
            }, [self.session_handle])
            return

        # 2. SelectSources Yanıtı (Boş döner, Start çağırmalıyız)
        if self.session_handle and "streams" not in results:
            logger.info("Aura: Kaynak seçildi, başlatılıyor...")
            self._call_portal("Start", {}, [self.session_handle, ""])
            return

        # 3. Start Yanıtı (Streams içerir)
        if "streams" in results:
            streams = results["streams"]
            if streams:
                node_id = streams[0][0] # İlk stream'in Node ID'si
                logger.info(f"Aura: Pipewire Akışı Hazır! Node ID: {node_id}")
                self.node_ready.emit(node_id)
            else:
                self.error_occurred.emit("Pipewire akışı bulunamadı.")

    def capture_frame(self, node_id: str, output_path: str) -> bool:
        """GStreamer kullanarak Pipewire akışından tek bir kare yakalar."""
        # Sovereign Command: Zero-Overlap & Alt-Tab Safe Capture
        cmd = [
            "gst-launch-1.0",
            "pipewiresrc", f"target-object={node_id}", "num-buffers=1", "!",
            "videoconvert", "!",
            "pngenc", "!",
            "filesink", f"location={output_path}"
        ]
        try:
            # Not: Background pencere ise hızlıca yakalar.
            subprocess.run(cmd, check=True, capture_output=True, timeout=5)
            return True
        except Exception as e:
            logger.error(f"Aura Capture Hatası: {e}")
            return False

# region Gelişmiş Portal Mantığı (Gelecekte genişletilebilir)
# Not: Tam portal handshake (Request sinyallerini dinleme) PyQt'de 
# Event Loop ile entegre çalışmalıdır.
# endregion
