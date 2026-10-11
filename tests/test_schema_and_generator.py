import unittest

from pydantic import ValidationError

from datetime import datetime

from generator import ReportGenerator, generate_report_no
from report_export import _parse_table
from schemas import ReportInput


def valid_payload():
    return {
        "project_info": {
            "project_name": "测试项目",
            "insured": "测试公司",
            "location": "测试地点",
            "installation_type": "屋顶分布式",
        },
        "material_results": [],
        "risk_items": [
            {
                "risk_type": "遮挡|积灰",
                "level": "中风险",
                "description": "存在遮挡\n需复核",
                "source": "现场查勘",
                "location": "东侧",
            }
        ],
        "equipment_analysis": {
            "component_model": "TEST-550",
            "hail_rating": "合格",
            "wind_rating": "合格",
            "snow_rating": "合格",
            "risk_level": "低风险",
        },
        "rule_results": [],
    }


class SchemaAndGeneratorTests(unittest.TestCase):
    def test_report_numbers_are_unique_across_calls(self):
        fixed_time = datetime(2026, 10, 11, 12, 0, 0)
        first = generate_report_no(fixed_time)
        second = generate_report_no(fixed_time)
        self.assertRegex(first, r"^UW-20261011-120000-[0-9A-F]{6}$")
        self.assertNotEqual(first, second)

    def test_common_risk_labels_are_normalized(self):
        report = ReportInput(**valid_payload())
        self.assertEqual(report.risk_items[0].level, "中")
        self.assertEqual(report.equipment_analysis.risk_level, "低")

    def test_missing_required_sections_are_rejected(self):
        with self.assertRaises(ValidationError):
            ReportInput()

    def test_unknown_fields_are_rejected(self):
        payload = valid_payload()
        payload["unexpected"] = True
        with self.assertRaises(ValidationError):
            ReportInput(**payload)

    def test_unknown_risk_level_is_rejected(self):
        payload = valid_payload()
        payload["risk_items"][0]["level"] = "严重"
        with self.assertRaises(ValidationError):
            ReportInput(**payload)

    def test_table_content_is_escaped_and_remains_one_cell(self):
        markdown = ReportGenerator().generate_report(
            valid_payload(),
            report_no="UW-TEST-001",
            generated_at="2026-10-11 12:00:00",
        )
        matching_line = next(line for line in markdown.splitlines() if "遮挡" in line)
        self.assertIn(r"遮挡\|积灰", matching_line)
        self.assertIn("存在遮挡 需复核", matching_line)
        cells = _parse_table([matching_line])
        self.assertEqual(len(cells), 1)
        self.assertEqual(len(cells[0]), 5)
        self.assertEqual(cells[0][0], "遮挡|积灰")


if __name__ == "__main__":
    unittest.main()
