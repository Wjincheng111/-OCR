from abc import ABC, abstractmethod

import numpy as np

from app.schemas.ocr import OCRTextBlock


class BaseOCREngine(ABC):
    """所有本地或远程 OCR 实现必须遵守的最小接口。"""

    @abstractmethod
    def recognize(self, image: np.ndarray, page_number: int) -> list[OCRTextBlock]:
        """识别一张 RGB 图片并返回标准文本块。"""

