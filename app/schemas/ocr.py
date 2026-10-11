import math
from enum import Enum
from typing import TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.document import Document


Point: TypeAlias = list[float]
BoundingBox: TypeAlias = list[Point]


class ProcessingStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"


class OCRTextBlock(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    text: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    bounding_box: BoundingBox
    page_number: int = Field(ge=1)

    @field_validator("bounding_box")
    @classmethod
    def validate_bounding_box(cls, value: BoundingBox) -> BoundingBox:
        if len(value) != 4 or any(len(point) != 2 for point in value):
            raise ValueError("bounding_box 必须由四个二维坐标点组成")
        normalized = [[float(coordinate) for coordinate in point] for point in value]
        if any(not math.isfinite(coordinate) for point in normalized for coordinate in point):
            raise ValueError("bounding_box 坐标必须是有限数值")
        return normalized


class OCRPageResult(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    page_number: int = Field(ge=1)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    text_blocks: list[OCRTextBlock] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_blocks(self) -> "OCRPageResult":
        x_tolerance = max(2.0, self.width * 0.02)
        y_tolerance = max(2.0, self.height * 0.02)
        for block in self.text_blocks:
            if block.page_number != self.page_number:
                raise ValueError("文本块页码必须与所在页面一致")
            for x, y in block.bounding_box:
                if not (-x_tolerance <= x <= self.width + x_tolerance):
                    raise ValueError("文本块横坐标超出页面范围")
                if not (-y_tolerance <= y <= self.height + y_tolerance):
                    raise ValueError("文本块纵坐标超出页面范围")
        return self


class OCRDocumentResult(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    document: Document
    pages: list[OCRPageResult] = Field(default_factory=list)
    full_text: str = ""
    processing_status: ProcessingStatus
    processing_time_ms: int = Field(ge=0)
    error_message: str | None = None

    @model_validator(mode="after")
    def validate_status_and_error(self) -> "OCRDocumentResult":
        if self.processing_status == ProcessingStatus.SUCCESS and self.error_message is not None:
            raise ValueError("成功结果不应包含 error_message")
        if self.processing_status == ProcessingStatus.FAILED and not self.error_message:
            raise ValueError("失败结果必须包含 error_message")
        page_numbers = [page.page_number for page in self.pages]
        if page_numbers != sorted(set(page_numbers)):
            raise ValueError("页面必须按页码升序排列且不能重复")
        if any(number > self.document.total_pages for number in page_numbers):
            raise ValueError("页面页码不能超过文档总页数")
        if self.processing_status == ProcessingStatus.SUCCESS:
            if not self.full_text.strip():
                raise ValueError("成功结果必须包含 full_text")
            if len(self.pages) != self.document.total_pages:
                raise ValueError("成功结果的页面数量必须与文档总页数一致")
        return self
