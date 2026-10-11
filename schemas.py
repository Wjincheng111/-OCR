"""
数据模型模块

定义报告生成模块接收的核保分析结果结构化数据模型。
输入为一份结构化 JSON，包含项目信息、材料审核结果、风险点清单、
组件抗灾能力分析与核保规则匹配结果。
"""

from typing import Annotated, List, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator


NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
OptionalText = Annotated[str, StringConstraints(strip_whitespace=True)]
RiskLevel = Literal["高", "中", "低"]
UnderwritingDecision = Literal["拒保", "加费/附加条件承保", "正常承保"]


def _normalize_risk_level(value):
    """允许“高风险”等常见写法，并统一为高/中/低。"""
    if isinstance(value, str):
        value = value.strip()
        aliases = {"高风险": "高", "中风险": "中", "低风险": "低"}
        return aliases.get(value, value)
    return value


class InputModel(BaseModel):
    """输入模型基类：拒绝未知字段，尽早发现上游字段拼写错误。"""

    model_config = ConfigDict(extra="forbid")


class ProjectInfo(InputModel):
    """项目基本信息"""

    project_name: NonEmptyText = Field(description="项目名称")
    insured: NonEmptyText = Field(description="被保险人")
    location: NonEmptyText = Field(description="项目地点")
    installation_type: NonEmptyText = Field(description="安装类型")


class MaterialResult(InputModel):
    """投保材料审核结果（单项）"""

    material: NonEmptyText = Field(description="材料名称")
    result: NonEmptyText = Field(description="审核结果")
    risk_level: RiskLevel = Field(description="风险等级")
    description: NonEmptyText = Field(description="说明")
    location: OptionalText = Field(default="", description="位置")

    _normalize_level = field_validator("risk_level", mode="before")(_normalize_risk_level)


class RiskItem(InputModel):
    """风险点清单（单项）"""

    risk_type: NonEmptyText = Field(description="风险类型")
    level: RiskLevel = Field(description="风险等级")
    description: NonEmptyText = Field(description="描述")
    source: NonEmptyText = Field(description="来源")
    location: OptionalText = Field(default="", description="风险定位")

    _normalize_level = field_validator("level", mode="before")(_normalize_risk_level)


class EquipmentAnalysis(InputModel):
    """组件抗灾能力分析结果（自然灾害风险）"""

    component_model: NonEmptyText = Field(description="组件型号")
    hail_rating: NonEmptyText = Field(description="抗冰雹能力")
    wind_rating: NonEmptyText = Field(description="抗风等级")
    snow_rating: NonEmptyText = Field(description="雪荷载等级")
    risk_level: RiskLevel = Field(description="综合风险")

    _normalize_level = field_validator("risk_level", mode="before")(_normalize_risk_level)


class RuleResult(InputModel):
    """核保规则匹配结果（单项）"""

    rule: NonEmptyText = Field(description="规则")
    result: NonEmptyText = Field(description="规则结果")
    suggestion: OptionalText = Field(default="", description="建议")


class ReportInput(InputModel):
    """报告生成模块的完整输入结构（顶层入口模型）"""

    project_info: ProjectInfo = Field(description="项目基本信息")
    material_results: List[MaterialResult] = Field(default_factory=list, description="材料审核结果")
    risk_items: List[RiskItem] = Field(default_factory=list, description="风险点清单")
    equipment_analysis: EquipmentAnalysis = Field(description="组件抗灾能力分析")
    rule_results: List[RuleResult] = Field(default_factory=list, description="核保规则匹配结果")


class ReportResponse(BaseModel):
    """报告生成接口响应结构。"""

    status: Literal["success"] = "success"
    decision: UnderwritingDecision
    risk_level: RiskLevel
    report_no: str
    generated_at: str
    report_markdown: str
