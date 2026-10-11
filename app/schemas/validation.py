from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ValidationSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    severity: ValidationSeverity
    message: str = Field(min_length=1)
    field_names: list[str] = Field(default_factory=list)


class ReviewPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ReviewRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required: bool
    priority: ReviewPriority = ReviewPriority.LOW
    reasons: list[str] = Field(default_factory=list)


class BatchValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    severity: ValidationSeverity
    message: str = Field(min_length=1)
    field_name: str | None = None
    document_ids: list[str] = Field(default_factory=list)
    observed_values: dict[str, str] = Field(default_factory=dict)
