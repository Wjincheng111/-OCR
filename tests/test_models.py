import pytest
from pydantic import ValidationError

from app.schemas.document import Document
from app.schemas.ocr import OCRDocumentResult, OCRPageResult, OCRTextBlock, ProcessingStatus


def test_models_can_create_standard_result() -> None:
    document = Document(
        document_id="doc-1",
        original_filename="sample.jpg",
        file_type="jpg",
        file_size=100,
        total_pages=1,
    )
    block = OCRTextBlock(
        text="LONGi",
        confidence=0.98,
        bounding_box=[[1, 2], [3, 2], [3, 4], [1, 4]],
        page_number=1,
    )
    result = OCRDocumentResult(
        document=document,
        pages=[OCRPageResult(page_number=1, width=10, height=10, text_blocks=[block])],
        full_text="LONGi",
        processing_status=ProcessingStatus.SUCCESS,
        processing_time_ms=12,
    )
    assert result.pages[0].text_blocks[0].bounding_box[0] == [1.0, 2.0]


def test_invalid_bounding_box_is_rejected() -> None:
    with pytest.raises(ValidationError):
        OCRTextBlock(
            text="bad",
            confidence=0.5,
            bounding_box=[[1, 2], [3, 4]],
            page_number=1,
        )


def test_failed_result_requires_error_message() -> None:
    document = Document(
        document_id="doc-2",
        original_filename="sample.png",
        file_type="png",
        file_size=20,
        total_pages=1,
    )
    with pytest.raises(ValidationError):
        OCRDocumentResult(
            document=document,
            processing_status=ProcessingStatus.FAILED,
            processing_time_ms=1,
        )

