"""OpenCV preprocessing for the AI Lost and Found Matcher (Member 3)."""
from __future__ import annotations
import os
from pathlib import Path
from typing import Tuple, Union
import cv2
import numpy as np
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
PathLike = Union[str, os.PathLike]
def _as_path(image_path: PathLike) -> Path:
    if image_path is None:
        raise FileNotFoundError("Image path is None. Pass a valid file path.")
    return Path(str(image_path).strip().strip('"').strip("'"))
def is_supported_image(path: PathLike) -> bool:
    return _as_path(path).suffix.lower() in SUPPORTED_EXTENSIONS
def load_image_bgr(image_path: PathLike):
    """Load image with OpenCV (BGR uint8) with helpful errors."""
    path = _as_path(image_path)
    if not str(path):
        raise FileNotFoundError("Empty image path provided.")
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(
            f"Image not found: {path}\nTip: check spelling, e.g. test_images/lost.jpg")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported extension '{path.suffix}' for: {path}\n"
            f"Supported: {sorted(SUPPORTED_EXTENSIONS)}")
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(
            f"Unable to read image (corrupt/unsupported codec): {path}\n"
            f"Tip: open it in Photos/Paint. If that fails, re-save as JPG/PNG.")
    return image
def load_image(image_path: PathLike):
    """Backwards-compatible alias of load_image_bgr."""
    return load_image_bgr(image_path)
def load_image_rgb(image_path: PathLike):
    """Load image and convert BGR -> RGB (uint8)."""
    return cv2.cvtColor(load_image_bgr(image_path), cv2.COLOR_BGR2RGB)
def resize_with_aspect(image_bgr, size: Tuple[int, int] = (224, 224)):
    """Resize with aspect ratio kept (letterbox). For display/colour, not CLIP."""
    if image_bgr is None or not isinstance(image_bgr, np.ndarray) or image_bgr.size == 0:
        raise ValueError("resize_with_aspect got an empty/invalid image array.")
    tw, th = int(size[0]), int(size[1])
    h, w = image_bgr.shape[:2]
    scale = min(tw / max(w, 1), th / max(h, 1))
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    resized = cv2.resize(image_bgr, (nw, nh), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((th, tw, 3), dtype=np.uint8)
    yo, xo = (th - nh) // 2, (tw - nw) // 2
    canvas[yo:yo + nh, xo:xo + nw] = resized
    return canvas


def preprocess_image(image_path, size=(224, 224)):
    """Load -> BGR-to-RGB -> resize -> float32 [0,1]. Same signature as starter."""
    rgb = load_image_rgb(image_path)
    resized = cv2.resize(rgb, (int(size[0]), int(size[1])))
    return (resized.astype(np.float32) / 255.0).astype(np.float32)


def _to_uint8_bgr(image):
    """Accept path or array; return uint8 BGR for histograms/colour."""
    if isinstance(image, (str, os.PathLike)):
        return load_image_bgr(image)
    if not isinstance(image, np.ndarray) or image.size == 0:
        raise ValueError("Expected non-empty numpy array or file path.")
    arr = image
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0.0, 1.0)
        arr = (arr * 255.0).round().astype(np.uint8)
        if arr.ndim == 3 and arr.shape[2] == 3:  # float RGB -> BGR
            arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    if arr.ndim != 3 or arr.shape[2] != 3:
        raise ValueError(f"Expected 3-channel colour image, got {arr.shape}.")
    return arr


def get_color_histogram(image, bins=(8, 8, 8)):
    """Normalised BGR histogram (L2 unit length). Accepts path or array."""
    bgr = _to_uint8_bgr(image)
    hist = cv2.calcHist([bgr], [0, 1, 2], None,
                        [int(bins[0]), int(bins[1]), int(bins[2])],
                        [0, 256, 0, 256, 0, 256])
    return cv2.normalize(hist, hist).flatten().astype(np.float32)


def compare_histograms(hist1, hist2):
    """Correlation [-1,1] mapped to 0-100 colour similarity."""
    h1 = np.asarray(hist1, dtype=np.float32).flatten()
    h2 = np.asarray(hist2, dtype=np.float32).flatten()
    if h1.shape != h2.shape:
        raise ValueError(f"Histogram shapes differ: {h1.shape} vs {h2.shape}.")
    if np.all(h1 == 0) or np.all(h2 == 0):
        return 0.0
    corr = float(cv2.compareHist(h1, h2, cv2.HISTCMP_CORREL))
    corr = max(-1.0, min(1.0, corr))
    return (corr + 1.0) / 2.0 * 100.0


def _basic_name(rgb):
    r, g, b = int(rgb[0]), int(rgb[1]), int(rgb[2])
    mx, mn = max(r, g, b), min(r, g, b)
    if mx < 40:
        return "black"
    if mn > 200:
        return "white"
    if mx - mn < 30:
        return "gray"
    hsv = cv2.cvtColor(np.uint8([[[b, g, r]]]), cv2.COLOR_BGR2HSV)[0][0]
    h, s, v = int(hsv[0]), int(hsv[1]), int(hsv[2])
    if s < 40 or v < 60:
        return "gray" if v >= 60 else "black"
    if h < 5 or h >= 170:
        return "red"
    if h < 15:
        return "orange"
    if h < 35:
        return "yellow"
    if h < 75:
        return "green"
    if h < 100:
        return "teal"
    if h < 130:
        return "blue"
    if h < 150:
        return "purple"
    return "pink"


def estimate_dominant_color(image, k=3):
    """K-means dominant colour (robust vs plain averaging)."""
    bgr = _to_uint8_bgr(image)
    small = cv2.resize(bgr, (64, 64), interpolation=cv2.INTER_AREA)
    pixels = small.reshape(-1, 3).astype(np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    k = max(1, min(int(k), 8))
    try:
        _, labels, centers = cv2.kmeans(
            pixels, k, None, criteria, 3, cv2.KMEANS_PP_CENTERS)
    except cv2.error as exc:
        raise ValueError(f"Could not estimate dominant colour: {exc}") from exc
    counts = np.bincount(labels.flatten(), minlength=k)
    win = int(np.argmax(counts))
    b, g, r = (max(0, min(255, int(round(float(c))))) for c in centers[win])
    return {"rgb": (r, g, b), "bgr": (b, g, r),
            "hex": f"#{r:02x}{g:02x}{b:02x}", "name": _basic_name((r, g, b))}