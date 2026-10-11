import json
import unittest
from pathlib import Path

from main import app, generate_report, root
from schemas import ReportInput, ReportResponse


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.case_a = json.loads(
            (PROJECT_ROOT / "examples" / "case_A.json").read_text(encoding="utf-8")
        )

    def test_health_check(self):
        self.assertEqual(root()["status"], "running")

    def test_generate_endpoint_contract(self):
        response = generate_report(ReportInput(**self.case_a))
        self.assertIsInstance(response, ReportResponse)
        self.assertEqual(response.status, "success")
        self.assertEqual(response.decision, "正常承保")
        self.assertEqual(response.risk_level, "低")
        self.assertTrue(response.report_no.startswith("UW-"))
        self.assertRegex(response.generated_at, r"^\d{4}-\d{2}-\d{2} ")
        self.assertIn(response.report_no, response.report_markdown)
        self.assertIn("核保评估报告", response.report_markdown)

    def test_openapi_includes_report_endpoint(self):
        schema = app.openapi()
        self.assertIn("/api/report/generate", schema["paths"])


if __name__ == "__main__":
    unittest.main()
