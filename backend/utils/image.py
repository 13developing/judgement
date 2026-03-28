"""Image processing utilities."""

from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image, ImageOps

_RESAMPLING = Image.Resampling.LANCZOS


def encode_image_to_base64(file_path: str) -> str:
    """Read an image file and return its base64-encoded string."""
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def compress_and_encode(
    file_path: str,
    max_size: tuple[int, int] = (1920, 1080),
    quality: int = 85,
) -> str:
    """Compress image, then return base64 string.

    This keeps the payload small when sending to the LLM API.
    """
    img = Image.open(file_path)
    img = ImageOps.exif_transpose(img)
    img.thumbnail(max_size, _RESAMPLING)

    buf = io.BytesIO()
    fmt = "JPEG" if file_path.lower().endswith((".jpg", ".jpeg")) else "PNG"
    if fmt == "JPEG":
        img.save(buf, format=fmt, quality=quality)
    else:
        img.save(buf, format=fmt)

    return base64.b64encode(buf.getvalue()).decode("utf-8")


def normalize_exam_sheet_image(file_path: str) -> None:
    """Normalize exam sheet orientation in-place for portrait viewing."""
    path = Path(file_path)
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)

    if img.width > img.height:
        img = img.rotate(90, expand=True)

    fmt: str = "JPEG" if path.suffix.lower() in {".jpg", ".jpeg"} else "PNG"
    if fmt == "JPEG":
        img.save(path, format=fmt, quality=92)
    else:
        img.save(path, format=fmt)


def crop_top_region_and_encode(
    file_path: str,
    *,
    top_ratio: float = 0.3,
    max_size: tuple[int, int] = (1800, 900),
) -> str:
    """Crop the upper region of a portrait exam sheet and encode it."""
    img = Image.open(file_path)
    img = ImageOps.exif_transpose(img)
    if img.width > img.height:
        img = img.rotate(90, expand=True)

    crop_height = max(1, int(img.height * top_ratio))
    cropped = img.crop((0, 0, img.width, crop_height))
    cropped.thumbnail(max_size, _RESAMPLING)

    buf = io.BytesIO()
    fmt: str = "JPEG" if file_path.lower().endswith((".jpg", ".jpeg")) else "PNG"
    if fmt == "JPEG":
        cropped.save(buf, format=fmt, quality=90)
    else:
        cropped.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode("utf-8")
