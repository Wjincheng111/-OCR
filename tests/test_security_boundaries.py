import math

import pytest
from pydantic import ValidationError

from app.schemas.document import Document
from app.schemas.ocr import OCRPageResult, OCRTextBlock
from app.utils.result_writer import save_result
from tests.helpers import make_ocr_result


def test_non_finite_coordinates_are_rejected() -> None:
    with pytest.raises(ValidationError):
        OCRTextBlock(
            text="bad",
            confidence=0.9,
            bounding_box=[[0, 0], [math.nan, 0], [1, 1], [0, 1]],
            page_number=1,
        )


def test_page_rejects_block_with_different_page_number() -> None:
    block = OCRTextBlock(
        text="wrong page",
        confidence=0.9,
        bounding_box=[[0, 0], [10, 0], [10, 10], [0, 10]],
        page_number=2,
    )
    with pytest.raises(ValidationError):
        OCRPageResult(page_number=1, width=20, height=20, text_blocks=[block])


def test_document_id_rejects_path_traversal() -> None:
    with pytest.raises(ValidationError):
        Document(
            document_id="../outside",
            original_filename="a.png",
            file_type="png",
            file_size=1,
            total_pages=1,
        )


def test_result_writer_uses_atomic_temp_file(tmp_path: object) -> None:
    result = make_ocr_result([["测试"]], document_id="safe-id")
    destination = save_result(result, tmp_path)  # type: ignore[arg-type]
    assert destination.exists()
    assert not list(destination.parent.glob("*.tmp"))
