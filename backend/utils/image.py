"""Image processing utilities."""

from __future__ import annotations

import base64
import io

from PIL import Image


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
    img.thumbnail(max_size, Image.LANCZOS)

    buf = io.BytesIO()
    fmt = "JPEG" if file_path.lower().endswith((".jpg", ".jpeg")) else "PNG"
    save_kwargs: dict = {"format": fmt}
    if fmt == "JPEG":
        save_kwargs["quality"] = quality
    img.save(buf, **save_kwargs)

    return base64.b64encode(buf.getvalue()).decode("utf-8")
