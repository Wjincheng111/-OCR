import math
from typing import TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.ocr import BoundingBox


NormalizedValue: TypeAlias = str | int | float | bool


class FieldEvidence(BaseModel):
    """字段值对应的 OCR 原文和坐标，供追溯及人工复核。"""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    page_number: int = Field(ge=1)
    source_text: str = Field(min_length=1)
    ocr_confidence: float = Field(ge=0.0, le=1.0)
    bounding_box: BoundingBox

    @field_validator("bounding_box")
    @classmethod
    def validate_bounding_box(cls, value: BoundingBox) -> BoundingBox:
        if len(value) != 4 or any(len(point) != 2 for point in value):
            raise ValueError("bounding_box 必须由四个二维坐标点组成")
        normalized = [[float(coordinate) for coordinate in point] for point in value]
        if any(not math.isfinite(coordinate) for point in normalized for coordinate in point):
            raise ValueError("bounding_box 坐标必须是有限数值")
        return normalized


class ExtractedField(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    field_name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    display_name: str = Field(min_length=1)
    raw_value: str = Field(min_length=1)
    normalized_value: NormalizedValue
    unit: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    extraction_method: str = "rule"
    evidence: FieldEvidence


class EquipmentLineItem(BaseModel):
    """设备清单中的一行；每个单元格继续保留独立 OCR 证据。"""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    item_index: int = Field(ge=1)
    page_number: int = Field(ge=1)
    equipment_type: ExtractedField | None = None
    manufacturer: ExtractedField | None = None
    brand: ExtractedField | None = None
    model: ExtractedField | None = None
    specification: ExtractedField | None = None
    quantity: ExtractedField | None = None
    unit_power_w: ExtractedField | None = None
    total_power_kw: ExtractedField | None = None
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_cells(self) -> "EquipmentLineItem":
        cell_names = (
            "equipment_type",
            "manufacturer",
            "brand",
            "model",
            "specification",
            "quantity",
            "unit_power_w",
            "total_power_kw",
        )
        cells = [getattr(self, name) for name in cell_names]
        if sum(cell is not None for cell in cells) < 2:
            raise ValueError("设备清单行至少需要两个有效单元格")
        if any(cell is not None and cell.evidence.page_number != self.page_number for cell in cells):
            raise ValueError("设备行单元格页码必须一致")
        return self
