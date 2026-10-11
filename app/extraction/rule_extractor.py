import re
import unicodedata
from collections.abc import Iterable

from app.extraction.catalog import FIELD_RULES, FieldRule
from app.extraction.normalizers import NORMALIZERS, NormalizedResult
from app.schemas.classification import DocumentClassification, DocumentType
from app.schemas.extraction import ExtractedField, FieldEvidence
from app.schemas.ocr import OCRDocumentResult, OCRTextBlock


class RuleBasedExtractor:
    """从 OCR 文本块中提取字段，并保留每个字段的原文与坐标证据。"""

    def __init__(self) -> None:
        self._compiled = {
            rule.field_name: tuple(re.compile(pattern, re.IGNORECASE) for pattern in rule.patterns)
            for rule in FIELD_RULES
        }
        self._known_labels = {
            self._normalize_label(label) for rule in FIELD_RULES for label in rule.labels
        }
        self._raw_labels = tuple(
            sorted(
                {label for rule in FIELD_RULES for label in rule.labels},
                key=len,
                reverse=True,
            )
        )

    def extract(
        self,
        ocr_result: OCRDocumentResult,
        classification: DocumentClassification,
    ) -> list[ExtractedField]:
        blocks = list(self._ordered_blocks(ocr_result))
        extracted: list[ExtractedField] = []

        for block in blocks:
            for rule in FIELD_RULES:
                if not self._applies(rule, classification.document_type):
                    continue
                field = self._extract_from_same_block(rule, block)
                if field is not None:
                    extracted.append(field)

        for index, block in enumerate(blocks):
            normalized_label = self._normalize_label(block.text)
            for rule in FIELD_RULES:
                if not self._applies(rule, classification.document_type):
                    continue
                if normalized_label not in {self._normalize_label(label) for label in rule.labels}:
                    continue
                neighbor = self._nearest_value_block(block, blocks[index + 1 :])
                if neighbor is None:
                    continue
                normalized = NORMALIZERS[rule.normalizer](neighbor.text)
                if normalized is not None:
                    extracted.append(
                        self._build_field(
                            rule,
                            raw_value=neighbor.text,
                            normalized=normalized,
                            evidence_block=neighbor,
                            source_text=f"{block.text} {neighbor.text}",
                            confidence=min(block.confidence, neighbor.confidence) * 0.80,
                            method="adjacent_block_rule",
                        )
                    )

        return self._deduplicate(extracted)

    def _extract_from_same_block(
        self, rule: FieldRule, block: OCRTextBlock
    ) -> ExtractedField | None:
        for pattern in self._compiled[rule.field_name]:
            match = pattern.search(block.text)
            if not match:
                continue
            raw_value = self._trim_at_next_label(match.group("value").strip())
            normalized = NORMALIZERS[rule.normalizer](raw_value)
            if normalized is None:
                continue
            return self._build_field(
                rule,
                raw_value=raw_value,
                normalized=normalized,
                evidence_block=block,
                source_text=block.text,
                confidence=block.confidence * 0.95,
                method="same_block_rule",
            )
        return None

    def _trim_at_next_label(self, value: str) -> str:
        """防止一个 OCR 块含多个“标签：值”时，前一字段吞掉后续字段。"""

        cut_at = len(value)
        for label in self._raw_labels:
            match = re.search(rf"{re.escape(label)}\s*[:：]", value, re.IGNORECASE)
            if match:
                cut_at = min(cut_at, match.start())
        return value[:cut_at].strip(" \t:：;；,，")

    @staticmethod
    def _build_field(
        rule: FieldRule,
        *,
        raw_value: str,
        normalized: NormalizedResult,
        evidence_block: OCRTextBlock,
        source_text: str,
        confidence: float,
        method: str,
    ) -> ExtractedField:
        return ExtractedField(
            field_name=rule.field_name,
            display_name=rule.display_name,
            raw_value=raw_value.strip(),
            normalized_value=normalized.value,
            unit=normalized.unit,
            confidence=round(max(0.0, min(1.0, confidence)), 4),
            extraction_method=method,
            evidence=FieldEvidence(
                page_number=evidence_block.page_number,
                source_text=source_text.strip(),
                ocr_confidence=evidence_block.confidence,
                bounding_box=evidence_block.bounding_box,
            ),
        )

    @staticmethod
    def _applies(rule: FieldRule, document_type: DocumentType) -> bool:
        return rule.allowed_types is None or document_type in rule.allowed_types

    @staticmethod
    def _ordered_blocks(ocr_result: OCRDocumentResult) -> Iterable[OCRTextBlock]:
        for page in sorted(ocr_result.pages, key=lambda item: item.page_number):
            yield from sorted(
                page.text_blocks,
                key=lambda block: (
                    min(point[1] for point in block.bounding_box),
                    min(point[0] for point in block.bounding_box),
                ),
            )

    def _nearest_value_block(
        self, label: OCRTextBlock, later_blocks: list[OCRTextBlock]
    ) -> OCRTextBlock | None:
        label_x_min, label_y_min, label_x_max, label_y_max = self._bounds(label)
        label_height = max(1.0, label_y_max - label_y_min)
        candidates: list[tuple[float, OCRTextBlock]] = []

        for candidate in later_blocks:
            if candidate.page_number != label.page_number:
                break
            if self._normalize_label(candidate.text) in self._known_labels:
                continue
            x_min, y_min, _x_max, y_max = self._bounds(candidate)
            vertical_overlap = min(label_y_max, y_max) - max(label_y_min, y_min)
            if x_min >= label_x_max - 5 and vertical_overlap >= -label_height * 0.5:
                distance = max(0.0, x_min - label_x_max) + abs(y_min - label_y_min) * 2
                candidates.append((distance, candidate))
                continue
            vertical_gap = y_min - label_y_max
            if -5 <= vertical_gap <= max(80.0, label_height * 4):
                horizontal_gap = abs(x_min - label_x_min)
                candidates.append((vertical_gap * 2 + horizontal_gap, candidate))

        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0])
        return candidates[0][1]

    @staticmethod
    def _bounds(block: OCRTextBlock) -> tuple[float, float, float, float]:
        xs = [point[0] for point in block.bounding_box]
        ys = [point[1] for point in block.bounding_box]
        return min(xs), min(ys), max(xs), max(ys)

    @staticmethod
    def _normalize_label(value: str) -> str:
        value = unicodedata.normalize("NFKC", value)
        return re.sub(r"[\s:：()（）]", "", value).casefold()

    @staticmethod
    def _deduplicate(fields: list[ExtractedField]) -> list[ExtractedField]:
        best: dict[tuple[str, str, str | None], ExtractedField] = {}
        for field in fields:
            value_key = str(field.normalized_value).strip().casefold()
            key = (field.field_name, value_key, field.unit)
            current = best.get(key)
            if current is None or field.confidence > current.confidence:
                best[key] = field
        return sorted(
            best.values(),
            key=lambda field: (
                field.evidence.page_number,
                min(point[1] for point in field.evidence.bounding_box),
                field.field_name,
            ),
        )
