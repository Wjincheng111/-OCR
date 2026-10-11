"""
报告生成模块

读取结构化核保分析结果（JSON/Pydantic），加载 Markdown 模板，
填充数据并生成标准化《分布式光伏财产险AI智能核保评估报告》。
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union
from uuid import uuid4

from jinja2 import Environment, FileSystemLoader, StrictUndefined

import config
from schemas import ReportInput
from utils import risk_summary

def generate_report_no(now: Optional[datetime] = None) -> str:
    """生成跨进程低碰撞报告编号，形如 UW-20261011-135501-A1B2C3。"""
    now = now or datetime.now()
    return "{}-{}-{}-{}".format(
        config.REPORT_NO_PREFIX,
        now.strftime("%Y%m%d"),
        now.strftime("%H%M%S"),
        uuid4().hex[:6].upper(),
    )


def _to_dict(model: Any) -> Dict[str, Any]:
    """兼容 Pydantic v1/v2，将模型转换为字典"""
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _single_line(value: Any) -> str:
    """将用户输入转换为适合 Markdown 单行位置的文本。"""
    return " ".join(str(value or "").split()).strip()


def _markdown_cell(value: Any) -> str:
    """转义 Markdown 表格分隔符，避免输入破坏表格结构。"""
    return _single_line(value).replace("|", r"\|")


class ReportGenerator:
    """核保评估报告生成器：加载模板并渲染 Markdown 报告"""

    def __init__(
        self,
        template_dir: Optional[Union[str, Path]] = None,
        template_name: Optional[str] = None,
    ):
        # 使用默认配置，或在调用时覆盖
        self.template_dir = Path(template_dir) if template_dir else config.TEMPLATE_DIR
        self.template_name = template_name or config.REPORT_TEMPLATE_NAME

        # 创建 Jinja2 环境；Markdown 无需 HTML 转义，故关闭 autoescape
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=False,
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.env.filters["md_cell"] = _markdown_cell
        self.env.filters["single_line"] = _single_line

    def _build_context(
        self,
        data: ReportInput,
        report_no: Optional[str] = None,
        generated_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """将输入转换为模板渲染上下文，并附加风险汇总、核保决策与报告元信息"""
        context = _to_dict(data)

        decision = risk_summary.make_decision(
            data.rule_results, data.risk_items, data.equipment_analysis, data.material_results
        )
        risk_level = risk_summary.overall_risk_level(
            data.risk_items, data.equipment_analysis, data.material_results
        )

        context["risk_summary"] = risk_summary.summarize_risk(data.risk_items)
        context["decision"] = decision
        context["risk_level"] = risk_level
        # 风险等级总评：低风险 / 中风险 / 高风险
        context["risk_level_label"] = "{}风险".format(risk_level)
        # 报告编号与生成时间
        context["report_no"] = report_no or generate_report_no()
        context["generated_at"] = generated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return context

    def generate_report(
        self,
        data: Union[ReportInput, Dict[str, Any]],
        report_no: Optional[str] = None,
        generated_at: Optional[str] = None,
    ) -> str:
        """
        根据输入数据生成并返回完整 Markdown 报告字符串。

        data 可为 ReportInput 实例或与输入结构一致的字典（JSON）。
        """
        if not isinstance(data, ReportInput):
            data = ReportInput(**data)
        template = self.env.get_template(self.template_name)
        return template.render(
            **self._build_context(data, report_no=report_no, generated_at=generated_at)
        )

    def generate(
        self,
        data: Union[ReportInput, Dict[str, Any]],
        output_path: Optional[Union[str, Path]] = None,
        report_no: Optional[str] = None,
        generated_at: Optional[str] = None,
    ) -> str:
        """生成报告；若指定 output_path 则同时保存到文件，返回 Markdown 文本"""
        markdown = self.generate_report(data, report_no=report_no, generated_at=generated_at)
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(markdown, encoding="utf-8")
        return markdown


def main() -> None:
    """命令行演示：读取示例数据，生成 example_report.md"""
    import json

    demo_path = config.EXAMPLES_DIR / "demo_input.json"
    input_data = json.loads(demo_path.read_text(encoding="utf-8"))

    generator = ReportGenerator()
    markdown = generator.generate_report(input_data)

    output_path = config.BASE_DIR / "example_report.md"
    output_path.write_text(markdown, encoding="utf-8")

    print("报告已生成：{}".format(output_path))
    print("=" * 60)
    print(markdown)


if __name__ == "__main__":
    main()
