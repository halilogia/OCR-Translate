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


def _capture_region_spectacle(region: Region) -> np.ndarray:
    """spectacle ile tam ekran yakala, sonra bölgeyi kırp."""
    full = _capture_full_spectacle()

    left = region["left"]
    top = region["top"]
    right = left + region["width"]
    bottom = top + region["height"]

    # Sınır kontrolü
    h, w = full.shape[:2]
    left = max(0, min(left, w))
    top = max(0, min(top, h))
    right = max(left + 1, min(right, w))
    bottom = max(top + 1, min(bottom, h))

    return full[top:bottom, left:right]


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


# endregion


# region Backend Seçimi


def _select_backend() -> str:
    """Uygun ekran yakalama backend'ini seçer."""
    if not _is_wayland():
        return "x11"

    # Wayland: önce grim dene (wlroots), sonra spectacle (KDE)
    if _has_command("grim"):
        # grim var ama compositor destekliyor mu test et
        try:
            result = subprocess.run(
                ["grim", "-g", "0,0 1x1", "/dev/null"],
                capture_output=True,
                timeout=3,
            )
            if result.returncode == 0:
                return "grim"
        except Exception:
            pass

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


# region Public API


def capture_region(region: Region) -> np.ndarray:
    """Belirtilen ekran bölgesinin görüntüsünü numpy array (RGB) olarak döner."""
    backend = _get_backend()
    if backend == "grim":
        return _capture_region_grim(region)
    if backend == "spectacle":
        return _capture_region_spectacle(region)
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
