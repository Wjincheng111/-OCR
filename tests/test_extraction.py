import pytest

from app.core.config import Settings
from app.extraction import DocumentClassifier, EquipmentTableExtractor, RuleBasedExtractor
from app.extraction.normalizers import normalize_capacity_kw
from app.schemas.classification import (
    ClassificationStatus,
    DocumentClassification,
    DocumentType,
)
from app.schemas.document import Document
from app.schemas.ocr import OCRDocumentResult, OCRPageResult, OCRTextBlock, ProcessingStatus
from app.services.analysis_service import AnalysisService
from app.validation import BatchConsistencyValidator, DocumentDataValidator
from app.schemas.analysis import BatchValidationRequest

from tests.helpers import make_ocr_result


def _field_map(result: object) -> dict[str, object]:
    return {
        field.field_name: field.normalized_value
        for field in result.extracted_fields  # type: ignore[attr-defined]
    }


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("项目基本情况", DocumentType.PROJECT_BASIC_INFO),
        ("财产险投保单", DocumentType.INSURANCE_APPLICATION),
        ("光伏组件规格书", DocumentType.PV_MODULE_DATASHEET),
        ("组件铭牌", DocumentType.PV_MODULE_NAMEPLATE),
        ("逆变器规格书", DocumentType.INVERTER_DATASHEET),
        ("逆变器铭牌", DocumentType.INVERTER_NAMEPLATE),
        ("主要设备表", DocumentType.EQUIPMENT_LIST),
        ("设备买卖合同", DocumentType.PURCHASE_CONTRACT),
        ("EPC总承包合同", DocumentType.EPC_CONTRACT),
        ("建设工程施工合同", DocumentType.CONSTRUCTION_CONTRACT),
        ("型式试验报告", DocumentType.INSPECTION_REPORT),
        ("并网验收报告", DocumentType.ACCEPTANCE_DOCUMENT),
        ("普通往来函", DocumentType.OTHER),
    ],
)
def test_supported_document_taxonomy(title: str, expected: DocumentType) -> None:
    classification = DocumentClassifier().classify(make_ocr_result([[title]]))
    assert classification.document_type == expected


def test_full_width_power_unit_is_normalized() -> None:
    normalized = normalize_capacity_kw("1.5ＭＷ")
    assert normalized is not None
    assert normalized.value == 1500
    assert normalized.unit == "kW"


def test_insurance_application_is_classified_extracted_and_normalized() -> None:
    ocr_result = make_ocr_result(
        [[
            "财产险投保单",
            "项目名称：屋顶分布式光伏项目",
            "投保人：甲能源有限公司",
            "被保险人：乙科技有限公司",
            "保险标的地址：江苏省某市工业园",
            "保险金额：1,250.50万元",
            "保险期间自：2026年1月2日",
            "保险止期：2027-01-01",
        ]],
        filename="投保单.pdf",
    )
    result = AnalysisService(Settings(save_results=False)).analyze_ocr(ocr_result)

    assert result.classification is not None
    assert result.classification.document_type == DocumentType.INSURANCE_APPLICATION
    assert result.classification.status == ClassificationStatus.CLASSIFIED
    fields = _field_map(result)
    assert fields["project_name"] == "屋顶分布式光伏项目"
    assert fields["insurance_amount_cny"] == 12_505_000
    assert fields["insurance_period_start"] == "2026-01-02"
    assert fields["insurance_period_end"] == "2027-01-01"
    assert all(field.evidence.page_number == 1 for field in result.extracted_fields)


def test_close_classification_scores_are_marked_ambiguous() -> None:
    ocr_result = make_ocr_result([["购销合同", "施工合同"]])
    classification = DocumentClassifier().classify(ocr_result)
    assert classification.status == ClassificationStatus.AMBIGUOUS


def test_page_classification_marks_mixed_pdf() -> None:
    ocr_result = make_ocr_result(
        [
            ["项目基本资料", "项目名称：甲项目", "装机容量：1MW"],
            ["竣工验收报告", "验收结论：验收通过", "验收日期：2026年5月1日"],
        ]
    )
    classification = DocumentClassifier().classify(ocr_result)
    assert classification.mixed_document is True
    assert [item.document_type for item in classification.page_classifications] == [
        DocumentType.PROJECT_BASIC_INFO,
        DocumentType.ACCEPTANCE_DOCUMENT,
    ]


def test_adjacent_block_extraction_uses_coordinates() -> None:
    blocks = [
        OCRTextBlock(
            text="项目名称",
            confidence=0.99,
            bounding_box=[[10, 10], [100, 10], [100, 30], [10, 30]],
            page_number=1,
        ),
        OCRTextBlock(
            text="甲屋顶光伏项目",
            confidence=0.97,
            bounding_box=[[130, 10], [350, 10], [350, 30], [130, 30]],
            page_number=1,
        ),
    ]
    ocr_result = OCRDocumentResult(
        document=Document(
            document_id="adjacent-1",
            original_filename="项目基本资料.png",
            file_type="png",
            file_size=100,
            total_pages=1,
        ),
        pages=[OCRPageResult(page_number=1, width=400, height=100, text_blocks=blocks)],
        full_text="项目名称\n甲屋顶光伏项目",
        processing_status=ProcessingStatus.SUCCESS,
        processing_time_ms=1,
    )
    classification = DocumentClassification(
        document_type=DocumentType.PROJECT_BASIC_INFO,
        confidence=0.9,
    )
    fields = RuleBasedExtractor().extract(ocr_result, classification)
    project_name = next(field for field in fields if field.field_name == "project_name")
    assert project_name.normalized_value == "甲屋顶光伏项目"
    assert project_name.extraction_method == "adjacent_block_rule"


def test_multiple_label_values_in_one_ocr_block_do_not_swallow_each_other() -> None:
    ocr_result = make_ocr_result(
        [["财产险投保单", "投保人：甲公司被保险人：乙公司项目名称：屋顶光伏"]]
    )
    classification = DocumentClassifier().classify(ocr_result)
    fields = RuleBasedExtractor().extract(ocr_result, classification)
    values = {field.field_name: field.normalized_value for field in fields}
    assert values["applicant_name"] == "甲公司"
    assert values["insured_name"] == "乙公司"
    assert values["project_name"] == "屋顶光伏"


def _cell(text: str, x: int, y: int) -> OCRTextBlock:
    return OCRTextBlock(
        text=text,
        confidence=0.98,
        bounding_box=[[x, y], [x + 100, y], [x + 100, y + 20], [x, y + 20]],
        page_number=1,
    )


def test_equipment_table_preserves_two_independent_rows() -> None:
    blocks = [
        _cell("设备名称", 10, 10),
        _cell("品牌", 180, 10),
        _cell("型号", 340, 10),
        _cell("数量", 520, 10),
        _cell("单块功率", 680, 10),
        _cell("总功率", 850, 10),
        _cell("光伏组件", 10, 60),
        _cell("LONGi", 180, 60),
        _cell("LR5-585M", 340, 60),
        _cell("100块", 520, 60),
        _cell("585W", 680, 60),
        _cell("58.5kW", 850, 60),
        _cell("逆变器", 10, 100),
        _cell("Sungrow", 180, 100),
        _cell("SG50CX", 340, 100),
        _cell("2台", 520, 100),
        _cell("50kW", 680, 100),
        _cell("100kW", 850, 100),
    ]
    ocr_result = OCRDocumentResult(
        document=Document(
            document_id="equipment-1",
            original_filename="设备清单.png",
            file_type="png",
            file_size=100,
            total_pages=1,
        ),
        pages=[OCRPageResult(page_number=1, width=1000, height=200, text_blocks=blocks)],
        full_text="\n".join(block.text for block in blocks),
        processing_status=ProcessingStatus.SUCCESS,
        processing_time_ms=1,
    )
    classification = DocumentClassifier().classify(ocr_result)
    items = EquipmentTableExtractor().extract(ocr_result, classification)

    assert len(items) == 2
    assert items[0].model is not None
    assert items[0].model.normalized_value == "LR5-585M"
    assert items[0].quantity is not None
    assert items[0].quantity.normalized_value == 100
    assert items[1].unit_power_w is not None
    assert items[1].unit_power_w.normalized_value == 50_000
    issues = DocumentDataValidator().validate(
        ocr_result, classification, [], items
    )
    assert not any(issue.code == "arithmetic_mismatch" for issue in issues)


def test_batch_validation_detects_capacity_conflict() -> None:
    service = AnalysisService(Settings(save_results=False))
    first = service.analyze_ocr(
        make_ocr_result(
            [["项目基本资料", "项目名称：甲项目", "装机容量：1MW"]],
            document_id="batch-1",
        )
    )
    second = service.analyze_ocr(
        make_ocr_result(
            [["项目基本资料", "项目名称：甲项目", "装机容量：1.2MW"]],
            document_id="batch-2",
        )
    )
    result = BatchConsistencyValidator().validate(
        BatchValidationRequest(project_group_id="project-a", documents=[first, second])
    )
    assert result.consistent is False
    assert any(issue.code == "cross_document_capacity_conflict" for issue in result.issues)


def test_invalid_insurance_date_range_requires_review() -> None:
    result = AnalysisService(Settings(save_results=False)).analyze_ocr(
        make_ocr_result(
            [[
                "财产险投保单",
                "项目名称：甲项目",
                "投保人：甲公司",
                "被保险人：乙公司",
                "保险标的地址：地址甲",
                "保险金额：100万元",
                "保险期间自：2027年1月1日",
                "保险止期：2026年1月1日",
            ]]
        )
    )
    assert any(issue.code == "invalid_date_range" for issue in result.validation_issues)
    assert result.review.required is True
    assert result.review.priority.value == "high"


def test_batch_compares_project_location_with_insurance_risk_location() -> None:
    service = AnalysisService(Settings(save_results=False))
    project = service.analyze_ocr(
        make_ocr_result(
            [[
                "项目基本资料",
                "项目名称：甲项目",
                "项目地点：地址甲",
                "建设单位：甲公司",
                "装机容量：1MW",
            ]],
            document_id="location-1",
        )
    )
    application = service.analyze_ocr(
        make_ocr_result(
            [[
                "财产险投保单",
                "项目名称：甲项目",
                "投保人：甲公司",
                "被保险人：甲公司",
                "保险标的地址：地址乙",
                "保险金额：100万元",
                "保险期间自：2026年1月1日",
                "保险止期：2027年1月1日",
            ]],
            document_id="location-2",
        )
    )
    result = BatchConsistencyValidator().validate(
        BatchValidationRequest(documents=[project, application])
    )
    issue = next(
        issue
        for issue in result.issues
        if issue.code == "cross_document_conflict"
        and issue.field_name == "project_location"
    )
    assert issue.observed_values == {"location-1": "地址甲", "location-2": "地址乙"}
