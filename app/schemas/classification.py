from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class DocumentType(str, Enum):
    PROJECT_BASIC_INFO = "project_basic_info"
    INSURANCE_APPLICATION = "insurance_application"
    PV_MODULE_DATASHEET = "pv_module_datasheet"
    PV_MODULE_NAMEPLATE = "pv_module_nameplate"
    INVERTER_DATASHEET = "inverter_datasheet"
    INVERTER_NAMEPLATE = "inverter_nameplate"
    EQUIPMENT_LIST = "equipment_list"
    PURCHASE_CONTRACT = "purchase_contract"
    EPC_CONTRACT = "epc_contract"
    CONSTRUCTION_CONTRACT = "construction_contract"
    INSPECTION_REPORT = "inspection_report"
    ACCEPTANCE_DOCUMENT = "acceptance_document"
    OTHER = "other"


class ClassificationStatus(str, Enum):
    CLASSIFIED = "classified"
    AMBIGUOUS = "ambiguous"
    OTHER = "other"


class ClassificationCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    document_type: DocumentType
    score: float = Field(ge=0.0)
    matched_keywords: list[str] = Field(default_factory=list)


class PageClassification(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    page_number: int = Field(ge=1)
    document_type: DocumentType
    status: ClassificationStatus
    confidence: float = Field(ge=0.0, le=1.0)
    matched_keywords: list[str] = Field(default_factory=list)


class DocumentClassification(BaseModel):
    """规则分类结果；matched_keywords 用于解释分类依据。"""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    document_type: DocumentType
    status: ClassificationStatus = ClassificationStatus.CLASSIFIED
    confidence: float = Field(ge=0.0, le=1.0)
    matched_keywords: list[str] = Field(default_factory=list)
    candidates: list[ClassificationCandidate] = Field(default_factory=list)
    page_classifications: list[PageClassification] = Field(default_factory=list)
    mixed_document: bool = False
    classifier_version: str = "rules-1.0"
