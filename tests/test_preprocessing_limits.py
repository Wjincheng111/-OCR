from pathlib import Path

import pymupdf
import pytest
from PIL import Image

from app.core.errors import DocumentProcessingError
from app.preprocessing.image_processor import load_image
from app.preprocessing.pdf_processor import iter_pdf_pages


def test_image_pixel_limit_is_enforced_before_decode(tmp_path: Path) -> None:
    path = tmp_path / "large.png"
    Image.new("RGB", (20, 20), "white").save(path)
    with pytest.raises(DocumentProcessingError, match="像素数超过限制"):
        load_image(path, max_pixels=399)


def test_pdf_total_render_pixel_limit_is_enforced(tmp_path: Path) -> None:
    path = tmp_path / "two-pages.pdf"
    document = pymupdf.open()
    document.new_page(width=100, height=100)
    document.new_page(width=100, height=100)
    document.save(path)
    document.close()

    with pytest.raises(DocumentProcessingError, match="像素总量超过限制"):
        list(
            iter_pdf_pages(
                path,
                dpi=72,
                max_page_pixels=20_000,
                max_total_pixels=15_000,
            )
        )
