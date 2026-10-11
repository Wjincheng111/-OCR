from collections.abc import Sequence

from app.schemas.document import Document
from app.schemas.ocr import (
    OCRDocumentResult,
    OCRPageResult,
    OCRTextBlock,
    ProcessingStatus,
)


def make_ocr_result(
    pages: Sequence[Sequence[str]],
    *,
    filename: str = "document.pdf",
    document_id: str = "doc-1",
    confidence: float = 0.98,
) -> OCRDocumentResult:
    page_results: list[OCRPageResult] = []
    all_text: list[str] = []
    for page_number, lines in enumerate(pages, start=1):
        blocks: list[OCRTextBlock] = []
        for index, line in enumerate(lines):
            y_min = 10 + index * 30
            y_max = y_min + 20
            blocks.append(
                OCRTextBlock(
                    text=line,
                    confidence=confidence,
                    bounding_box=[
                        [20, y_min],
                        [900, y_min],
                        [900, y_max],
                        [20, y_max],
                    ],
                    page_number=page_number,
                )
            )
            all_text.append(line)
        page_results.append(
            OCRPageResult(
                page_number=page_number,
                width=1000,
                height=max(200, 50 + len(lines) * 30),
                text_blocks=blocks,
            )
        )
    file_type = filename.rsplit(".", 1)[-1].lower()
    return OCRDocumentResult(
        document=Document(
            document_id=document_id,
            original_filename=filename,
            file_type=file_type,
            file_size=1024,
            total_pages=len(page_results),
        ),
        pages=page_results,
        full_text="\n".join(all_text),
        processing_status=ProcessingStatus.SUCCESS,
        processing_time_ms=10,
    )
