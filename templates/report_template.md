# 分布式光伏财产险AI智能核保评估报告

| 项目 | 内容 |
| --- | --- |
| 报告编号 | {{ report_no | md_cell }} |
| 生成时间 | {{ generated_at | md_cell }} |
| 风险等级总评 | {{ risk_level_label | md_cell }} |

> 本报告由 AI 智能核保系统自动生成，供核保人员参考。

## 项目基本信息

| 项目 | 内容 |
| --- | --- |
| 项目名称 | {{ (project_info.project_name or "—") | md_cell }} |
| 被保险人 | {{ (project_info.insured or "—") | md_cell }} |
| 项目地点 | {{ (project_info.location or "—") | md_cell }} |
| 安装类型 | {{ (project_info.installation_type or "—") | md_cell }} |

## 材料审核结果

| 材料名称 | 审核结果 | 风险等级 | 说明 |
| --- | --- | --- | --- |
{% for item in material_results %}
| {{ (item.material or "—") | md_cell }} | {{ (item.result or "—") | md_cell }} | {{ (item.risk_level or "—") | md_cell }} | {{ ((item.description or "—") ~ ("（位置：" ~ item.location ~ "）" if item.location else "")) | md_cell }} |
{% else %}
| 暂无材料审核数据 | — | — | — |
{% endfor %}

## 风险清单

| 风险类型 | 风险等级 | 来源 | 风险定位 | 描述 |
| --- | --- | --- | --- | --- |
{% for item in risk_items %}
| {{ (item.risk_type or "—") | md_cell }} | {{ (item.level or "—") | md_cell }} | {{ (item.source or "—") | md_cell }} | {{ (item.location or "—") | md_cell }} | {{ (item.description or "—") | md_cell }} |
{% else %}
| 暂无风险点 | — | — | — | — |
{% endfor %}

## 自然灾害风险

| 项目 | 内容 |
| --- | --- |
| 组件型号 | {{ (equipment_analysis.component_model or "—") | md_cell }} |
| 抗冰雹能力 | {{ (equipment_analysis.hail_rating or "—") | md_cell }} |
| 抗风等级 | {{ (equipment_analysis.wind_rating or "—") | md_cell }} |
| 雪荷载等级 | {{ (equipment_analysis.snow_rating or "—") | md_cell }} |
| 综合风险 | {{ (equipment_analysis.risk_level or "—") | md_cell }} |

## 核保规则结果

{% if rule_results %}
{% for item in rule_results %}
- **{{ (item.rule or "未命名规则") | single_line }}**：{{ (item.result or "—") | single_line }}{{ ("（建议：" ~ item.suggestion ~ "）") | single_line if item.suggestion else "" }}
{% endfor %}
{% else %}
（暂无核保规则结果）
{% endif %}

## 综合核保意见

- 核保决策：**{{ decision }}**
- 整体风险等级：{{ risk_level_label }}
- 风险点统计：高风险 {{ risk_summary.high_count }} 项、中风险 {{ risk_summary.medium_count }} 项、低风险 {{ risk_summary.low_count }} 项
- 主要风险：{{ risk_summary.main_risk | single_line }}

## 风险建议

{% if rule_results %}
{% for item in rule_results %}
{% if item.suggestion %}
- [{{ (item.rule or "规则") | single_line }}] {{ item.suggestion | single_line }}
{% endif %}
{% endfor %}
{% else %}
（暂无风险建议）
{% endif %}

---

> 核保建议：由AI辅助生成，最终承保决定需人工核保确认。
