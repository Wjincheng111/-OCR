"""
风险汇总与核保决策模块

对风险点清单进行统计汇总，并基于风险结果生成综合核保意见。
本阶段提供：
- 风险等级数量统计（高/中/低）
- 主要风险描述
- 综合核保决策（拒保 / 加费/附加条件承保 / 正常承保）
- 整体风险等级
"""

from typing import Any, Dict, List

# 判定为“拒保”的关键词（出现在核保规则结论中）
REJECT_KEYWORDS = ("拒保", "拒绝", "不承保", "不予承保", "不可承保")
REJECT_NEGATIONS = ("不拒保", "无需拒保", "不属于拒保", "非拒保")

# 判定为“加费/附加条件承保”的关键词（出现在核保规则结论中）
CONDITIONAL_KEYWORDS = ("加费", "条件承保", "附加条件", "限制承保")
CONDITIONAL_NEGATIONS = (
    "无条件承保",
    "无需加费",
    "不加费",
    "无附加条件",
    "无需附加条件",
    "不限制承保",
)

# 风险等级常量
LEVEL_HIGH = "高"
LEVEL_MEDIUM = "中"
LEVEL_LOW = "低"


def _field(item: Any, name: str, default: str = "") -> str:
    """兼容对象属性与字典两种取值方式，安全读取字段值"""
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def normalize_level(text: str) -> str:
    """将风险等级文本归一化为 高/中/低，无法识别时返回空字符串"""
    text = str(text or "").strip()
    if LEVEL_HIGH in text:
        return LEVEL_HIGH
    if LEVEL_MEDIUM in text:
        return LEVEL_MEDIUM
    if LEVEL_LOW in text:
        return LEVEL_LOW
    return ""


def summarize_risk(risk_items: List[Any]) -> Dict[str, Any]:
    """
    汇总风险清单。

    返回：
        high_count: 高风险数量
        medium_count: 中风险数量
        low_count: 低风险数量
        main_risk: 主要风险描述（按 高 > 中 > 低 优先级汇总）
    """
    high, medium, low = 0, 0, 0
    high_desc, medium_desc, low_desc = [], [], []

    for item in risk_items or []:
        level = normalize_level(_field(item, "level", ""))
        desc = str(_field(item, "description", "")).strip()
        if level == LEVEL_HIGH:
            high += 1
            if desc:
                high_desc.append(desc)
        elif level == LEVEL_MEDIUM:
            medium += 1
            if desc:
                medium_desc.append(desc)
        elif level == LEVEL_LOW:
            low += 1
            if desc:
                low_desc.append(desc)

    if high_desc:
        main_risk = "；".join(high_desc)
    elif medium_desc:
        main_risk = "；".join(medium_desc)
    elif low_desc:
        main_risk = "；".join(low_desc)
    else:
        main_risk = "无"

    return {
        "high_count": high,
        "medium_count": medium,
        "low_count": low,
        "main_risk": main_risk,
    }


def _contains_reject(rule_results: List[Any]) -> bool:
    """判断核保规则结论中是否存在拒保类结论"""
    for rule in rule_results or []:
        result = str(_field(rule, "result", "")).strip()
        normalized = result
        for phrase in REJECT_NEGATIONS:
            normalized = normalized.replace(phrase, "")
        if any(kw in normalized for kw in REJECT_KEYWORDS):
            return True
    return False


def _contains_conditional(rule_results: List[Any]) -> bool:
    """判断核保规则结论中是否存在加费或附加条件类结论。"""
    for rule in rule_results or []:
        result = str(_field(rule, "result", "")).strip()
        normalized = result
        for phrase in CONDITIONAL_NEGATIONS:
            normalized = normalized.replace(phrase, "")
        if any(kw in normalized for kw in CONDITIONAL_KEYWORDS):
            return True
    return False


def _iter_levels(items: List[Any], attr: str) -> List[str]:
    """提取对象列表中指定等级字段，并归一化为 高/中/低"""
    return [normalize_level(_field(item, attr, "")) for item in (items or [])]


def _collect_levels(risk_items, equipment_analysis, material_results) -> List[str]:
    """汇总各风险来源的归一化风险等级"""
    levels = _iter_levels(risk_items, "level")
    levels += _iter_levels(material_results, "risk_level")
    if equipment_analysis is not None:
        levels.append(normalize_level(_field(equipment_analysis, "risk_level", "")))
    return levels


def make_decision(
    rule_results: List[Any],
    risk_items: List[Any] = None,
    equipment_analysis: Any = None,
    material_results: List[Any] = None,
) -> str:
    """
    根据风险结果生成综合核保决策。

    判断规则：
        1. 核保规则结论中存在拒保类结论 -> 拒保
        2. 规则结论中存在加费或条件承保类结论 -> 加费/附加条件承保
        3. 否则，存在高风险（风险点/材料/组件任一） -> 加费/附加条件承保
        4. 否则 -> 正常承保
    """
    if _contains_reject(rule_results):
        return "拒保"
    if _contains_conditional(rule_results):
        return "加费/附加条件承保"
    if LEVEL_HIGH in _collect_levels(risk_items, equipment_analysis, material_results):
        return "加费/附加条件承保"
    return "正常承保"


def overall_risk_level(
    risk_items: List[Any] = None,
    equipment_analysis: Any = None,
    material_results: List[Any] = None,
) -> str:
    """
    计算整体风险等级（高/中/低）。

    判断规则：
        - 存在高风险 -> 高
        - 否则存在中风险 -> 中
        - 否则 -> 低
    """
    levels = _collect_levels(risk_items, equipment_analysis, material_results)
    if LEVEL_HIGH in levels:
        return LEVEL_HIGH
    if LEVEL_MEDIUM in levels:
        return LEVEL_MEDIUM
    return LEVEL_LOW
