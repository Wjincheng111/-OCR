from pathlib import Path

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.errors import DocumentProcessingError


def load_image(path: Path, *, max_pixels: int) -> np.ndarray:
    """读取图片、修正 EXIF 方向并统一为 RGB ndarray。"""

    try:
        with Image.open(path) as source:
            width, height = source.size
            if width <= 0 or height <= 0 or width * height > max_pixels:
                raise DocumentProcessingError(
                    f"图片像素数超过限制（最多 {max_pixels} 像素）。"
                )
            source.load()
            image = ImageOps.exif_transpose(source).convert("RGB")
            return np.asarray(image)
    except DocumentProcessingError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise DocumentProcessingError("无法读取图片，请确认文件未损坏。") from exc
