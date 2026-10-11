import json
import logging
import os
import threading
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np

from app.core.config import get_settings
from app.core.errors import OCREngineError
from app.ocr.base import BaseOCREngine
from app.schemas.ocr import OCRTextBlock


logger = logging.getLogger(__name__)
_engine_init_lock = threading.Lock()
_engine_instance: BaseOCREngine | None = None


class PaddleOCREngine(BaseOCREngine):
    """PaddleOCR 适配器；优先使用 3.x predict，同时兼容 2.x 结果。"""

    def __init__(
        self,
        *,
        language: str = "ch",
        device: str = "cpu",
        enable_mkldnn: bool = False,
        model_cache_dir: Path | None = None,
    ) -> None:
        try:
            if model_cache_dir is not None:
                model_cache_dir.mkdir(parents=True, exist_ok=True)
                os.environ["PADDLE_PDX_CACHE_HOME"] = str(model_cache_dir)
            from paddleocr import PaddleOCR

            self._ocr = PaddleOCR(
                lang=language,
                device=device,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                enable_mkldnn=enable_mkldnn,
            )
        except Exception as exc:
            logger.exception("PaddleOCR 初始化失败")
            raise OCREngineError("OCR 引擎初始化失败，请检查 PaddleOCR 安装和模型下载。") from exc
        self._inference_lock = threading.RLock()

    def recognize(self, image: np.ndarray, page_number: int) -> list[OCRTextBlock]:
        try:
            with self._inference_lock:
                if hasattr(self._ocr, "predict"):
                    raw_result = self._ocr.predict(image)
                    return self._normalize_v3(raw_result, page_number)
                raw_result = self._ocr.ocr(image, cls=False)
                return self._normalize_v2(raw_result, page_number)
        except OCREngineError:
            raise
        except Exception as exc:
            logger.exception("PaddleOCR 推理失败")
            raise OCREngineError("OCR 执行失败。") from exc

    def _normalize_v3(self, results: Iterable[Any], page_number: int) -> list[OCRTextBlock]:
        blocks: list[OCRTextBlock] = []
        for result in results:
            payload = self._result_payload(result)
            texts = self._as_list(payload.get("rec_texts"))
            scores = self._as_list(payload.get("rec_scores"))
            polygons_value = payload.get("rec_polys")
            if polygons_value is None:
                polygons_value = payload.get("dt_polys")
            polygons = self._as_list(polygons_value)

            if not (len(texts) == len(scores) == len(polygons)):
                raise OCREngineError("OCR 引擎返回的文字、置信度和坐标数量不一致。")

            for text, score, polygon in zip(texts, scores, polygons, strict=True):
                normalized_text = str(text).strip()
                if not normalized_text:
                    continue
                blocks.append(
                    OCRTextBlock(
                        text=normalized_text,
                        confidence=float(score),
                        bounding_box=self._normalize_polygon(polygon),
                        page_number=page_number,
                    )
                )
        return blocks

    def _normalize_v2(self, results: Any, page_number: int) -> list[OCRTextBlock]:
        blocks: list[OCRTextBlock] = []
        if not results:
            return blocks
        lines = results[0] if len(results) == 1 and isinstance(results[0], list) else results
        for line in lines or []:
            if not line or len(line) < 2:
                continue
            polygon, recognition = line[0], line[1]
            if not recognition or len(recognition) < 2:
                continue
            text, score = recognition[0], recognition[1]
            normalized_text = str(text).strip()
            if normalized_text:
                blocks.append(
                    OCRTextBlock(
                        text=normalized_text,
                        confidence=float(score),
                        bounding_box=self._normalize_polygon(polygon),
                        page_number=page_number,
                    )
                )
        return blocks

    @staticmethod
    def _result_payload(result: Any) -> dict[str, Any]:
        if isinstance(result, dict):
            data: Any = result
        else:
            json_value = getattr(result, "json", None)
            data = json_value() if callable(json_value) else json_value
        if isinstance(data, str):
            data = json.loads(data)
        if not isinstance(data, dict):
            raise OCREngineError("OCR 引擎返回了无法解析的结果。")
        payload = data.get("res", data)
        if not isinstance(payload, dict):
            raise OCREngineError("OCR 引擎返回了无法解析的结果。")
        return payload

    @staticmethod
    def _as_list(value: Any) -> list[Any]:
        if value is None:
            return []
        if hasattr(value, "tolist"):
            value = value.tolist()
        return list(value)

    @staticmethod
    def _normalize_polygon(value: Any) -> list[list[float]]:
        if hasattr(value, "tolist"):
            value = value.tolist()
        points = list(value)
        if len(points) != 4 or any(len(point) != 2 for point in points):
            raise OCREngineError("OCR 坐标格式不正确。")
        return [[float(point[0]), float(point[1])] for point in points]


def get_ocr_engine() -> BaseOCREngine:
    """进程内只初始化一次大模型，避免每个请求重复加载。"""

    global _engine_instance
    if _engine_instance is not None:
        return _engine_instance
    with _engine_init_lock:
        if _engine_instance is None:
            settings = get_settings()
            _engine_instance = PaddleOCREngine(
                language=settings.ocr_language,
                device=settings.ocr_device,
                enable_mkldnn=settings.ocr_enable_mkldnn,
                model_cache_dir=settings.resolved_ocr_model_cache_dir,
            )
    return _engine_instance
