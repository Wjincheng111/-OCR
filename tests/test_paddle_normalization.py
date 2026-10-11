import pytest

from app.core.errors import OCREngineError
from app.ocr.paddle_engine import PaddleOCREngine


def test_paddle_v3_result_is_normalized_without_loading_model() -> None:
    engine = object.__new__(PaddleOCREngine)
    blocks = engine._normalize_v3(
        [
            {
                "res": {
                    "rec_texts": ["型号 A"],
                    "rec_scores": [0.97],
                    "rec_polys": [[[1, 2], [8, 2], [8, 5], [1, 5]]],
                }
            }
        ],
        page_number=2,
    )
    assert blocks[0].text == "型号 A"
    assert blocks[0].confidence == 0.97
    assert blocks[0].page_number == 2


def test_paddle_v2_result_is_normalized_without_loading_model() -> None:
    engine = object.__new__(PaddleOCREngine)
    blocks = engine._normalize_v2(
        [[[[[1, 2], [8, 2], [8, 5], [1, 5]], ("旧接口", 0.88)]]],
        page_number=1,
    )
    assert blocks[0].text == "旧接口"
    assert blocks[0].bounding_box[2] == [8.0, 5.0]


def test_paddle_v3_mismatched_arrays_are_rejected() -> None:
    engine = object.__new__(PaddleOCREngine)
    with pytest.raises(OCREngineError):
        engine._normalize_v3(
            [
                {
                    "res": {
                        "rec_texts": ["A", "B"],
                        "rec_scores": [0.9],
                        "rec_polys": [[[0, 0], [1, 0], [1, 1], [0, 1]]],
                    }
                }
            ],
            page_number=1,
        )
