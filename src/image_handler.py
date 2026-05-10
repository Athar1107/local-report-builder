"""
image_handler.py
----------------
Image validation, base64 encoding, and batch folder discovery.
No auto-describe here — the user provides text descriptions.
"""

import base64
from pathlib import Path

from PIL import Image as PILImage

from .config import SUPPORTED_IMAGE_FORMATS, MAX_IMAGE_SIZE_MB


def validate_image(image_path: str) -> Path:
    path = Path(image_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")
    if path.suffix.lower() not in SUPPORTED_IMAGE_FORMATS:
        raise ValueError(
            f"Unsupported format '{path.suffix}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_IMAGE_FORMATS))}"
        )
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > MAX_IMAGE_SIZE_MB:
        raise ValueError(f"Image {size_mb:.1f} MB exceeds {MAX_IMAGE_SIZE_MB} MB limit.")
    return path


def get_image_info(image_path: str) -> dict:
    path = validate_image(image_path)
    img  = PILImage.open(path)
    return {
        "path":     str(path),
        "filename": path.name,
        "stem":     path.stem,
        "width":    img.width,
        "height":   img.height,
        "size_kb":  round(path.stat().st_size / 1024, 1),
    }


def encode_image_b64(image_path: str) -> str:
    """Return base64-encoded image string for Ollama multimodal input."""
    path = validate_image(image_path)
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def discover_images(folder: str) -> list[Path]:
    """Return sorted list of all supported images in a folder."""
    folder_path = Path(folder)
    if not folder_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {folder}")
    return sorted(
        p for p in folder_path.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_IMAGE_FORMATS
    )
