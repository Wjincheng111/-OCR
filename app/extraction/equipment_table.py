import re
from collections import defaultdict
from dataclasses import dataclass

from app.extraction.normalizers import NORMALIZERS
from app.schemas.classification import DocumentClassification, DocumentType
from app.schemas.extraction import EquipmentLineItem, ExtractedField, FieldEvidence
from app.schemas.ocr import OCRDocumentResult, OCRTextBlock


@dataclass(frozen=True)
class _Column:
    name: str
    display_name: str
    normalizer: str
    header: OCRTextBlock


_HEADER_ALIASES: dict[str, tuple[str, str, str]] = {
    "设备名称": ("equipment_type", "设备名称", "string"),
    "设备类型": ("equipment_type", "设备类型", "string"),
    "名称": ("equipment_type", "设备名称", "string"),
    "生产厂家": ("manufacturer", "生产厂家", "string"),
    "制造商": ("manufacturer", "制造商", "string"),
    "品牌": ("brand", "品牌", "string"),
    "型号": ("model", "型号", "identifier"),
    "规格型号": ("model", "规格型号", "identifier"),
    "规格": ("specification", "规格", "string"),
    "数量": ("quantity", "数量", "integer"),
    "单台功率": ("unit_power_w", "单台功率", "power_w"),
    "单块功率": ("unit_power_w", "单块功率", "power_w"),
    "额定功率": ("unit_power_w", "额定功率", "power_w"),
    "总功率": ("total_power_kw", "总功率", "capacity_kw"),
    "合计功率": ("total_power_kw", "合计功率", "capacity_kw"),
}


class EquipmentTableExtractor:
    """使用 OCR 坐标识别简单设备清单表格，并保留每个单元格证据。"""

    def extract(
        self,
        ocr_result: OCRDocumentResult,
        classification: DocumentClassification,
    ) -> list[EquipmentLineItem]:
        page_types = {
            page.page_number: page.document_type
            for page in classification.page_classifications
        }
        items: list[EquipmentLineItem] = []
        for page in ocr_result.pages:
            if (
                classification.document_type != DocumentType.EQUIPMENT_LIST
                and page_types.get(page.page_number) != DocumentType.EQUIPMENT_LIST
            ):
                continue
            page_items = self._extract_page(page.text_blocks)
            for item in page_items:
                items.append(item.model_copy(update={"item_index": len(items) + 1}))
        return items

    def _extract_page(self, blocks: list[OCRTextBlock]) -> list[EquipmentLineItem]:
        columns = self._find_columns(blocks)
        if len(columns) < 2:
            return []
        header_bottom = max(self._bounds(column.header)[3] for column in columns)
        body = [
            block
            for block in blocks
            if self._center(block)[1] > header_bottom
            and self._normalize_header(block.text) not in _HEADER_ALIASES
        ]
        if not body:
            return []

        row_tolerance = max(
            12.0,
            sum(max(1.0, self._bounds(block)[3] - self._bounds(block)[1]) for block in body)
            / len(body)
            * 0.8,
        )
        rows = self._group_rows(body, row_tolerance)
        results: list[EquipmentLineItem] = []
        for row in rows:
            item = self._build_item(len(results) + 1, row, columns)
            if item is not None:
                results.append(item)
        return results

    def _find_columns(self, blocks: list[OCRTextBlock]) -> list[_Column]:
        header_blocks = [
            block
            for block in blocks
            if self._normalize_header(block.text) in _HEADER_ALIASES
        ]
        if len(header_blocks) < 2:
            return []

        groups = self._group_rows(header_blocks, 30.0)
        best_group = max(groups, key=len)
        columns: list[_Column] = []
        seen: set[str] = set()
        for block in sorted(best_group, key=lambda item: self._center(item)[0]):
            name, display_name, normalizer = _HEADER_ALIASES[
                self._normalize_header(block.text)
            ]
            if name in seen:
                continue
            seen.add(name)
            columns.append(_Column(name, display_name, normalizer, block))
        return columns

    def _build_item(
        self,
        item_index: int,
        row: list[OCRTextBlock],
        columns: list[_Column],
    ) -> EquipmentLineItem | None:
        by_column: dict[str, list[OCRTextBlock]] = defaultdict(list)
        for block in row:
            nearest = min(
                columns,
                key=lambda column: abs(
                    self._center(column.header)[0] - self._center(block)[0]
                ),
            )
            by_column[nearest.name].append(block)

        fields: dict[str, ExtractedField] = {}
        for column in columns:
            cell_blocks = sorted(
                by_column.get(column.name, []), key=lambda block: self._center(block)[0]
            )
            if not cell_blocks:
                continue
            raw_value = " ".join(block.text.strip() for block in cell_blocks).strip()
            normalized = NORMALIZERS[column.normalizer](raw_value)
            if normalized is None:
                continue
            confidence = sum(block.confidence for block in cell_blocks) / len(cell_blocks)
            fields[column.name] = ExtractedField(
                field_name=column.name,
                display_name=column.display_name,
                raw_value=raw_value,
                normalized_value=normalized.value,
                unit=normalized.unit,
                confidence=round(confidence * 0.85, 4),
                extraction_method="equipment_table_layout",
                evidence=FieldEvidence(
                    page_number=cell_blocks[0].page_number,
                    source_text=raw_value,
                    ocr_confidence=round(confidence, 4),
                    bounding_box=self._union_box(cell_blocks),
                ),
            )

        if len(fields) < 2 or fields.get("quantity") is None:
            return None
        equipment_type = fields.get("equipment_type")
        if equipment_type and re.search(
            r"^(合计|总计|小计|备注|说明|经办人|制表人)", equipment_type.raw_value
        ):
            return None
        confidence = sum(field.confidence for field in fields.values()) / len(fields)
        page_number = next(iter(fields.values())).evidence.page_number
        return EquipmentLineItem(
            item_index=item_index,
            page_number=page_number,
            confidence=round(confidence, 4),
            **fields,
        )

    @staticmethod
    def _group_rows(
        blocks: list[OCRTextBlock], tolerance: float
    ) -> list[list[OCRTextBlock]]:
        ordered = sorted(blocks, key=lambda block: EquipmentTableExtractor._center(block)[1])
        rows: list[list[OCRTextBlock]] = []
        centers: list[float] = []
        for block in ordered:
            y_center = EquipmentTableExtractor._center(block)[1]
            if not rows or abs(y_center - centers[-1]) > tolerance:
                rows.append([block])
                centers.append(y_center)
            else:
                rows[-1].append(block)
                centers[-1] = sum(
                    EquipmentTableExtractor._center(item)[1] for item in rows[-1]
                ) / len(rows[-1])
        return rows

    @staticmethod
    def _normalize_header(value: str) -> str:
        return re.sub(r"[\s:：()（）]", "", value)

    @staticmethod
    def _center(block: OCRTextBlock) -> tuple[float, float]:
        x_min, y_min, x_max, y_max = EquipmentTableExtractor._bounds(block)
        return (x_min + x_max) / 2, (y_min + y_max) / 2

    @staticmethod
    def _bounds(block: OCRTextBlock) -> tuple[float, float, float, float]:
        xs = [point[0] for point in block.bounding_box]
        ys = [point[1] for point in block.bounding_box]
        return min(xs), min(ys), max(xs), max(ys)

    @staticmethod
    def _union_box(blocks: list[OCRTextBlock]) -> list[list[float]]:
        bounds = [EquipmentTableExtractor._bounds(block) for block in blocks]
        x_min = min(item[0] for item in bounds)
        y_min = min(item[1] for item in bounds)
        x_max = max(item[2] for item in bounds)
        y_max = max(item[3] for item in bounds)
        return [[x_min, y_min], [x_max, y_min], [x_max, y_max], [x_min, y_max]]
