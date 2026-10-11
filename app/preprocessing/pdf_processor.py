import logging
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pymupdf

from app.core.errors import DocumentProcessingError


logger = logging.getLogger(__name__)


def get_pdf_page_count(path: Path, *, max_pages: int) -> int:
    try:
        with pymupdf.open(path) as document:
            if document.needs_pass:
                raise DocumentProcessingError("暂不支持加密 PDF。")
            page_count = document.page_count
    except DocumentProcessingError:
        raise
    except (pymupdf.FileDataError, RuntimeError, ValueError) as exc:
        raise DocumentProcessingError("无法读取 PDF，请确认文件未损坏。") from exc

    if page_count <= 0:
        raise DocumentProcessingError("PDF 不包含可处理的页面。")
    if page_count > max_pages:
        raise DocumentProcessingError(f"PDF 页数超过限制（最多 {max_pages} 页）。")
    return page_count


def iter_pdf_pages(
    path: Path, *, dpi: int, max_page_pixels: int, max_total_pixels: int
) -> Iterator[tuple[int, np.ndarray]]:
    """逐页渲染 PDF，避免一次把所有页面留在内存中。"""

    scale = dpi / 72
    matrix = pymupdf.Matrix(scale, scale)
    total_pixels = 0
    try:
        with pymupdf.open(path) as document:
            for index, page in enumerate(document, start=1):
                estimated_width = max(1, round(page.rect.width * scale))
                estimated_height = max(1, round(page.rect.height * scale))
                if estimated_width * estimated_height > max_page_pixels:
                    raise DocumentProcessingError(
                        f"PDF 第 {index} 页渲染像素数超过限制。"
                    )
                total_pixels += estimated_width * estimated_height
                if total_pixels > max_total_pixels:
                    raise DocumentProcessingError("PDF 全部页面的渲染像素总量超过限制。")
                pixmap = page.get_pixmap(
                    matrix=matrix, colorspace=pymupdf.csRGB, alpha=False
                )
                image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
                    pixmap.height, pixmap.width, 3
                )
                yield index, image.copy()
    except DocumentProcessingError:
        raise
    except (pymupdf.FileDataError, RuntimeError, ValueError) as exc:
        logger.exception("PDF 页面渲染失败")
        raise DocumentProcessingError("PDF 页面转换失败。") from exc
