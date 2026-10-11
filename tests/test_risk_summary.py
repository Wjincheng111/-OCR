import unittest

from utils.risk_summary import make_decision, normalize_level, overall_risk_level


class RiskSummaryTests(unittest.TestCase):
    def test_normalize_level_accepts_common_labels(self):
        self.assertEqual(normalize_level("高风险"), "高")
        self.assertEqual(normalize_level(" 中 "), "中")
        self.assertEqual(normalize_level("unknown"), "")

    def test_reject_rule_has_highest_priority(self):
        rules = [{"result": "条件承保"}, {"result": "拒保"}]
        self.assertEqual(make_decision(rules), "拒保")

    def test_conditional_rule_is_not_downgraded_to_normal(self):
        rules = [{"result": "加费承保"}]
        equipment = {"risk_level": "低"}
        self.assertEqual(
            make_decision(rules, equipment_analysis=equipment),
            "加费/附加条件承保",
        )

    def test_negated_keywords_do_not_trigger_restrictions(self):
        rules = [
            {"result": "不属于拒保范围"},
            {"result": "无需加费，无条件承保"},
        ]
        equipment = {"risk_level": "低"}
        self.assertEqual(make_decision(rules, equipment_analysis=equipment), "正常承保")

    def test_high_risk_without_rule_requires_conditions(self):
        risks = [{"level": "高"}]
        self.assertEqual(make_decision([], risk_items=risks), "加费/附加条件承保")
        self.assertEqual(overall_risk_level(risk_items=risks), "高")


if __name__ == "__main__":
    unittest.main()
