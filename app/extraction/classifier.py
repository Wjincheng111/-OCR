import unicodedata

from app.extraction.catalog import CLASSIFICATION_RULES
from app.schemas.classification import (
    ClassificationCandidate,
    ClassificationStatus,
    DocumentClassification,
    DocumentType,
    PageClassification,
)
from app.schemas.ocr import OCRDocumentResult


class DocumentClassifier:
    """基于可解释关键词权重的文档分类器。"""

    MIN_CLASSIFICATION_SCORE = 6.0
    AMBIGUITY_MARGIN = 2.0

    def classify(self, ocr_result: OCRDocumentResult) -> DocumentClassification:
        scored = self._score_text(
            ocr_result.full_text,
            filename=ocr_result.document.original_filename,
        )
        page_classifications = [
            self._classify_page(
                page.page_number,
                "\n".join(block.text for block in page.text_blocks),
            )
            for page in ocr_result.pages
        ]
        specific_page_types = {
            page.document_type
            for page in page_classifications
            if page.document_type != DocumentType.OTHER
        }
        top_score, document_type, matched = scored[0]
        second_score = scored[1][0] if len(scored) > 1 else 0.0
        status, selected_type, confidence = self._decision(
            top_score, second_score, document_type
        )
        candidates = [
            ClassificationCandidate(
                document_type=candidate_type,
                score=round(score, 3),
                matched_keywords=keywords,
            )
            for score, candidate_type, keywords in scored[:3]
            if score > 0
        ]
        return DocumentClassification(
            document_type=selected_type,
            status=status,
            confidence=confidence,
            matched_keywords=matched,
            candidates=candidates,
            page_classifications=page_classifications,
            mixed_document=len(specific_page_types) > 1,
        )

    def _score_text(
        self, text: str, *, filename: str | None = None
    ) -> list[tuple[float, DocumentType, list[str]]]:
        haystack = unicodedata.normalize("NFKC", text).casefold()
        filename_haystack = unicodedata.normalize("NFKC", filename or "").casefold()
        scored: list[tuple[float, DocumentType, list[str]]] = []

        for rule in CLASSIFICATION_RULES:
            matched: list[str] = []
            score = 0.0
            for keyword, weight in rule.keywords:
                normalized_keyword = keyword.casefold()
                in_body = normalized_keyword in haystack
                in_filename = normalized_keyword in filename_haystack
                if in_body or in_filename:
                    matched.append(keyword)
                    score += weight if in_body else 0.0
                    score += weight * 1.4 if in_filename else 0.0
            scored.append((score, rule.document_type, matched))

        scored.sort(key=lambda item: item[0], reverse=True)
        return scored

    def _decision(
        self,
        top_score: float,
        second_score: float,
        document_type: DocumentType,
    ) -> tuple[ClassificationStatus, DocumentType, float]:
        if top_score < self.MIN_CLASSIFICATION_SCORE:
            confidence = 0.0 if top_score == 0 else min(0.49, top_score / 12.0)
            return ClassificationStatus.OTHER, DocumentType.OTHER, round(confidence, 4)

        difference = top_score - second_score
        status = (
            ClassificationStatus.AMBIGUOUS
            if difference < self.AMBIGUITY_MARGIN
            else ClassificationStatus.CLASSIFIED
        )
        strength = min(top_score / 12.0, 1.0)
        separation = min(max(0.0, difference) / 6.0, 1.0)
        confidence = 0.7 * strength + 0.3 * separation
        return status, document_type, round(min(0.99, confidence), 4)

    def _classify_page(self, page_number: int, text: str) -> PageClassification:
        scored = self._score_text(text)
        top_score, document_type, matched = scored[0]
        second_score = scored[1][0] if len(scored) > 1 else 0.0
        status, selected_type, confidence = self._decision(
            top_score, second_score, document_type
        )
        return PageClassification(
            page_number=page_number,
            document_type=selected_type,
            status=status,
            confidence=confidence,
            matched_keywords=matched,
        )
