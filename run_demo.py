"""
Demo 运行脚本

依次读取 examples/case_A.json、case_B.json、case_C.json，
模拟真实光伏财产险核保场景，分别生成 Markdown 报告与 PDF 报告。
"""

import json

import config
import report_export
from generator import ReportGenerator
from schemas import ReportInput
from utils import risk_summary

# 案例文件名、输出基名、预期核保决策
CASES = [
    ("case_A.json", "report_A", "正常承保"),
    ("case_B.json", "report_B", "拒保"),
    ("case_C.json", "report_C", "加费/附加条件承保"),
]


def run() -> None:
    """运行 Demo：生成三份核保评估报告"""
    generator = ReportGenerator()

    for filename, base, expected in CASES:
        raw = json.loads((config.EXAMPLES_DIR / filename).read_text(encoding="utf-8"))
        report = ReportInput(**raw)

        decision = risk_summary.make_decision(
            report.rule_results, report.risk_items, report.equipment_analysis, report.material_results
        )
        risk_level = risk_summary.overall_risk_level(
            report.risk_items, report.equipment_analysis, report.material_results
        )

        markdown = generator.generate_report(report)

        md_path = config.BASE_DIR / "{}.md".format(base)
        md_path.write_text(markdown, encoding="utf-8")

        print("=" * 70)
        print("案例 {} | 预期: {} | 实际 decision: {} | risk_level: {}".format(
            filename, expected, decision, risk_level
        ))
        print("Markdown: {}".format(md_path.name))

        # 导出 PDF（若环境支持）
        try:
            pdf_path = report_export.markdown_to_pdf(
                markdown, config.BASE_DIR / "{}.pdf".format(base)
            )
            print("PDF: {}".format(pdf_path.name))
        except Exception as exc:
            print("PDF 导出跳过: {}".format(exc))


if __name__ == "__main__":
    run()