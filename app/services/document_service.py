import logging
import tempfile
import threading
import time
from collections.abc import Iterable
from pathlib import Path
from uuid import uuid4

import numpy as np
from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings
from app.core.errors import DocumentProcessingError, OCREngineError
from app.ocr.base import BaseOCREngine
from app.ocr.paddle_engine import get_ocr_engine
from app.preprocessing.image_processor import load_image
from app.preprocessing.pdf_processor import get_pdf_page_count, iter_pdf_pages
from app.schemas.document import Document
from app.schemas.ocr import OCRDocumentResult, OCRPageResult, ProcessingStatus
from app.utils.file_utils import save_upload_to_temp, validate_upload_metadata
from app.utils.result_writer import save_result


logger = logging.getLogger(__name__)
_limiter_lock = threading.Lock()
_processing_limiters: dict[int, threading.BoundedSemaphore] = {}


def _get_processing_limiter(limit: int) -> threading.BoundedSemaphore:
    with _limiter_lock:
        return _processing_limiters.setdefault(limit, threading.BoundedSemaphore(limit))


class DocumentService:
    def __init__(self, settings: Settings, engine: BaseOCREngine | None = None) -> None:
        self.engine = engine
        self.settings = settings
        self._processing_limiter = _get_processing_limiter(settings.max_concurrent_ocr)

    async def process_upload(self, upload: UploadFile) -> OCRDocumentResult:
        started_at = time.perf_counter()
        document_id = str(uuid4())
        metadata = validate_upload_metadata(upload)
        logger.info("开始处理文件 document_id=%s file_type=%s", document_id, metadata.file_type)

        with tempfile.TemporaryDirectory(prefix=f"ocr_{document_id}_") as temp_dir:
            temp_path = Path(temp_dir) / f"upload.{metadata.file_type}"
            file_size = await save_upload_to_temp(
                upload,
                temp_path,
                file_type=metadata.file_type,
                max_size_bytes=self.settings.max_file_size_bytes,
                max_size_mb=self.settings.max_file_size_mb,
            )
            document = Document(
                document_id=document_id,
                original_filename=metadata.original_filename,
                file_type=metadata.file_type,
                file_size=file_size,
                total_pages=0,
            )

            try:
                total_pages, pages = await run_in_threadpool(
                    self._process_path, temp_path, metadata.file_type
                )
                document = document.model_copy(update={"total_pages": total_pages})
            except (DocumentProcessingError, OCREngineError) as exc:
                logger.warning("文件处理失败 document_id=%s reason=%s", document_id, str(exc))
                return self._finish_failed(document, started_at, str(exc))
            except Exception:
                logger.exception("文件处理发生未预期异常 document_id=%s", document_id)
                return self._finish_failed(
                    document,
                    started_at,
                    "文件处理失败，请检查文件是否损坏或稍后重试。",
                )

        full_text = "\n".join(
            block.text for page in pages for block in page.text_blocks if block.text
        )
        if not full_text:
            result = self._finish_failed(
                document,
                started_at,
                "未识别到文字，请确认文件清晰且包含可识别文本。",
                pages=pages,
            )
        else:
            result = OCRDocumentResult(
                document=document,
                pages=pages,
                full_text=full_text,
                processing_status=ProcessingStatus.SUCCESS,
                processing_time_ms=self._elapsed_ms(started_at),
                error_message=None,
            )

        self._optionally_save(result)
        logger.info(
            "文件处理完成 document_id=%s status=%s elapsed_ms=%s",
            document_id,
            result.processing_status.value,
            result.processing_time_ms,
        )
        return result

    def _process_path(
        self, path: Path, file_type: str
    ) -> tuple[int, list[OCRPageResult]]:
        """在线程池内执行文件解码、PDF 渲染及 OCR，避免阻塞事件循环。"""

        with self._processing_limiter:
            total_pages, page_images = self._prepare_pages(path, file_type)
            return total_pages, self._recognize_pages(page_images)

    def _prepare_pages(
        self, path: Path, file_type: str
    ) -> tuple[int, Iterable[tuple[int, np.ndarray]]]:
        if file_type == "pdf":
            page_count = get_pdf_page_count(path, max_pages=self.settings.max_pdf_pages)
            logger.info("PDF 页数=%s", page_count)
            return page_count, iter_pdf_pages(
                path,
                dpi=self.settings.pdf_dpi,
                max_page_pixels=self.settings.max_image_pixels,
                max_total_pixels=self.settings.max_pdf_total_pixels,
            )
        image = load_image(path, max_pixels=self.settings.max_image_pixels)
        return 1, [(1, image)]

    def _recognize_pages(
        self, page_images: Iterable[tuple[int, np.ndarray]]
    ) -> list[OCRPageResult]:
        pages: list[OCRPageResult] = []
        for page_number, image in page_images:
            ocr_started = time.perf_counter()
            engine = self.engine or get_ocr_engine()
            text_blocks = engine.recognize(image, page_number)
            logger.info(
                "OCR 页面完成 page_number=%s elapsed_ms=%s blocks=%s",
                page_number,
                self._elapsed_ms(ocr_started),
                len(text_blocks),
            )
            height, width = image.shape[:2]
            pages.append(
                OCRPageResult(
                    page_number=page_number,
                    width=int(width),
                    height=int(height),
                    text_blocks=text_blocks,
                )
            )
        return pages

    def _finish_failed(
        self,
        document: Document,
        started_at: float,
        message: str,
        *,
        pages: list[OCRPageResult] | None = None,
    ) -> OCRDocumentResult:
        result = OCRDocumentResult(
            document=document,
            pages=pages or [],
            full_text="",
            processing_status=ProcessingStatus.FAILED,
            processing_time_ms=self._elapsed_ms(started_at),
            error_message=message,
        )
        self._optionally_save(result)
        return result

    def _optionally_save(self, result: OCRDocumentResult) -> None:
        if not self.settings.save_results:
            return
        try:
            save_result(result, self.settings.resolved_output_dir)
        except OSError:
            logger.exception("调试结果保存失败 document_id=%s", result.document.document_id)

    @staticmethod
    def _elapsed_ms(started_at: float) -> int:
        return max(0, round((time.perf_counter() - started_at) * 1000))
