"""
OCR-TRANSLATE — Ekran Yakalama Modülü

Wayland (KDE):  spectacle CLI ile tam ekran yakala + bölge kırp
Wayland (wlr):  grim ile bölge yakala
X11:            mss kütüphanesi ile bölge yakala
"""

import logging
import os
import shutil
import subprocess
import tempfile
from typing import TypedDict

import cv2
import mss
import numpy as np
from PIL import Image

import config

logger = logging.getLogger(__name__)


class Region(TypedDict):
    top: int
    left: int
    width: int
    height: int


def _is_wayland() -> bool:
    """Wayland oturumunda mıyız?"""
    return "wayland" in os.environ.get("XDG_SESSION_TYPE", "").lower()


def _has_command(cmd: str) -> bool:
    """Komut PATH'te var mı?"""
    return shutil.which(cmd) is not None


# region Wayland — spectacle (KDE Plasma)


def _capture_full_spectacle() -> np.ndarray:
    """spectacle ile tam ekran görüntüsü alır (KDE Wayland)."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            ["spectacle", "-b", "-n", "-f", "-o", tmp_path],
            capture_output=True,
            timeout=10,
        )
        if result.returncode != 0:
            error_msg = result.stderr.decode().strip()
            raise RuntimeError(f"spectacle hatası: {error_msg}")

        img = Image.open(tmp_path).convert("RGB")
        return np.array(img)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _get_device_pixel_ratio() -> float:
    """Ekran ölçeklendirme katsayısını (DPI) döner."""
    try:
        from PyQt5.QtWidgets import QApplication

        app = QApplication.instance()
        if app:
            screen = app.primaryScreen()
            if screen:
                return screen.devicePixelRatio()
    except Exception:
        pass
    return 1.0


def _capture_region_spectacle(region: Region) -> np.ndarray:
    """spectacle ile tam ekran yakala, sonra DPI'a göre bölgeyi kırp."""
    full = _capture_full_spectacle()
    ratio = _get_device_pixel_ratio()

    full_h, full_w = full.shape[:2]

    # Koordinatları fiziksel piksel boyutuna ölçekle
    left = int(region["left"] * ratio)
    top = int(region["top"] * ratio)
    width = int(region["width"] * ratio)
    height = int(region["height"] * ratio)

    right = left + width
    bottom = top + height

    # Sınır kontrolü
    left = max(0, min(left, full_w))
    top = max(0, min(top, full_h))
    right = max(left + 2, min(right, full_w))
    bottom = max(top + 2, min(bottom, full_h))

    cropped = full[top:bottom, left:right]
    ch, cw = cropped.shape[:2]

    logger.info(
        "Spectacle capture: fullscreen=%dx%d, ratio=%.1f, "
        "region=[%d,%d,%d,%d], cropped=%dx%d",
        full_w,
        full_h,
        ratio,
        left,
        top,
        right,
        bottom,
        cw,
        ch,
    )

    if cw < 10 or ch < 10:
        logger.warning(
            "Kırpılan görüntü çok küçük (%dx%d). "
            "Bölge koordinatları ekran sınırları dışında olabilir.",
            cw,
            ch,
        )

    return cropped


# endregion


# region Wayland — grim (wlroots: Sway, Hyprland vb.)


def _capture_region_grim(region: Region) -> np.ndarray:
    """grim ile belirli bölgenin ekran görüntüsünü alır."""
    geometry = f"{region['left']},{region['top']} {region['width']}x{region['height']}"

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            ["grim", "-g", geometry, tmp_path],
            capture_output=True,
            timeout=5,
        )
        if result.returncode != 0:
            error_msg = result.stderr.decode().strip()
            raise RuntimeError(f"grim hatası: {error_msg}")

        img = Image.open(tmp_path).convert("RGB")
        return np.array(img)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _capture_full_grim() -> np.ndarray:
    """grim ile tam ekran görüntüsü alır."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            ["grim", tmp_path],
            capture_output=True,
            timeout=5,
        )
        if result.returncode != 0:
            error_msg = result.stderr.decode().strip()
            raise RuntimeError(f"grim hatası: {error_msg}")

        img = Image.open(tmp_path).convert("RGB")
        return np.array(img)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# endregion


# region X11 (mss)


def _capture_region_x11(region: Region) -> np.ndarray:
    """mss ile belirli bölgenin ekran görüntüsünü alır."""
    with mss.mss() as sct:
        screenshot = sct.grab(region)
        frame = np.array(screenshot)
    return cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)


def _capture_full_screen_x11() -> np.ndarray:
    """mss ile tam ekran görüntüsü alır."""
    with mss.mss() as sct:
        monitor = sct.monitors[0]
        screenshot = sct.grab(monitor)
        frame = np.array(screenshot)
    return cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)


def _capture_region_kwin_6(uuid: str) -> np.ndarray:
    """KDE 6 ScreenShot2 API kullanarak pencereyi sızdırmaz yakalar. (Sovereign Engine)."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # AAA Implementation: KWin 6 ScreenShot2 (Direct)
        # Not: CaptureWindow metodu bir dosya yolu veya handle bekler. 
        # En basit ve stabil yol spectacle üzerinden bu API'yi tetiklemektir.
        cmd = ["spectacle", "-b", "-n", "-o", tmp_path, "--window", uuid]
        result = subprocess.run(cmd, capture_output=True, timeout=10)
        
        if result.returncode != 0:
            # Fallback: UUID ile başarısız olursa normal pencere yakalama dene
            cmd = ["spectacle", "-b", "-n", "-o", tmp_path, "-w"]
            subprocess.run(cmd, capture_output=True, timeout=10)

        img = Image.open(tmp_path).convert("RGB")
        return np.array(img)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


# endregion


# region Backend Seçimi


def _select_backend() -> str:
    """Uygun ekran yakalama backend'ini seçer."""
    if not _is_wayland():
        return "x11"

    # Wayland: önce grim dene (wlroots/KDE), sonra spectacle (KDE)
    if _has_command("grim"):
        return "grim"

    if _has_command("spectacle"):
        return "spectacle"

    logger.warning(
        "Wayland'de ekran yakalama aracı bulunamadı. "
        "KDE: 'spectacle' (genellikle kurulu), wlroots: 'grim' gerekli."
    )
    return "x11"  # Fallback (muhtemelen çalışmaz)


# Backend'i modül yüklenirken bir kez belirle
_BACKEND: str = ""


def _get_backend() -> str:
    """Lazy-init backend seçimi."""
    global _BACKEND
    if not _BACKEND:
        _BACKEND = _select_backend()
        logger.info("Ekran yakalama backend: %s", _BACKEND)
    return _BACKEND


# endregion


def _capture_region_aura(node_id: int) -> np.ndarray:
    """GStreamer + Pipewire kullanarak pencerenin buffer'ından doğrudan yakalama yapar. (Aura Engine)."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # AAA Command: Zero-Overlap & Alt-Tab Safe
        cmd = [
            "gst-launch-1.0",
            "pipewiresrc", f"target-object={node_id}", "num-buffers=1", "!",
            "videoconvert", "!",
            "pngenc", "!",
            "filesink", f"location={tmp_path}"
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=5)
        
        if result.returncode != 0:
            raise RuntimeError(f"GStreamer hatası: {result.stderr.decode()}")

        img = Image.open(tmp_path).convert("RGB")
        return np.array(img)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


# region Public API


_WORKING_BACKEND: str = ""


def capture_region(region: Region, node_id: Optional[int] = None, uuid: Optional[str] = None) -> np.ndarray:
    """Belirtilen ekran bölgesinin görüntüsünü numpy array (RGB) olarak döner."""
    global _WORKING_BACKEND
    
    method = getattr(config, "CAPTURE_METHOD", "auto")

    # 1. Aura Pipewire Önceliği (Sovereign Mode)
    if (method == "auto" or method == "aura") and node_id:
        try:
            return _capture_region_aura(node_id)
        except Exception as e:
            logger.warning(f"Aura (Pipewire) yakalama başarısız, standart yönteme dönülüyor: {e}")

    # 2. KDE 6 ScreenShot2 Önceliği (Sovereign Mode)
    if (method == "auto" or method == "kde") and uuid:
        try:
            return _capture_region_kwin_6(uuid)
        except Exception as e:
            logger.warning(f"KDE 6 (ScreenShot2) yakalama başarısız, standart yönteme dönülüyor: {e}")

    # 3. Önceden çalışan bir backend varsa onu kullan

    # 2. Önceden çalışan bir backend varsa onu kullan
    if _WORKING_BACKEND:
        try:
            if _WORKING_BACKEND == "grim":
                return _capture_region_grim(region)
            if _WORKING_BACKEND == "spectacle":
                return _capture_region_spectacle(region)
            return _capture_region_x11(region)
        except Exception as e:
            logger.warning(
                f"Backend {_WORKING_BACKEND} çalışırken hata verdi, sıfırlanıyor: {e}"
            )
            _WORKING_BACKEND = ""

    # 2. Backend bul ve dene
    backend = _get_backend()
    try:
        if backend == "grim":
            res = _capture_region_grim(region)
            _WORKING_BACKEND = "grim"
            return res
    except Exception as e:
        logger.error(f"Grim başarısız, spectacle'a düşülüyor: {e}")
        # Grim başarısızsa spectacle'ı zorla (fallback)
        if _has_command("spectacle"):
            _WORKING_BACKEND = "spectacle"
            return _capture_region_spectacle(region)

    if backend == "spectacle":
        _WORKING_BACKEND = "spectacle"
        return _capture_region_spectacle(region)

    _WORKING_BACKEND = "x11"
    return _capture_region_x11(region)


def capture_full_screen() -> np.ndarray:
    """Tüm ekranın görüntüsünü numpy array (RGB) olarak döner."""
    backend = _get_backend()
    if backend == "grim":
        return _capture_full_grim()
    if backend == "spectacle":
        return _capture_full_spectacle()
    return _capture_full_screen_x11()


def get_full_screen_region() -> Region:
    """Tüm ekranı kapsayan Region dict'i döner."""
    if _is_wayland():
        try:
            from PyQt5.QtWidgets import QApplication

            app = QApplication.instance()
            if app:
                screen = app.primaryScreen()
                if screen:
                    geom = screen.virtualGeometry()
                    return Region(
                        top=geom.y(),
                        left=geom.x(),
                        width=geom.width(),
                        height=geom.height(),
                    )
        except Exception:
            pass

    with mss.mss() as sct:
        monitor = sct.monitors[0]
        return Region(
            top=monitor["top"],
            left=monitor["left"],
            width=monitor["width"],
            height=monitor["height"],
        )


# endregion
