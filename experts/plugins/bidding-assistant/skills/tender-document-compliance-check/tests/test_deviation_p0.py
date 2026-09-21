from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
SHARED_DIR = SKILL_DIR.parent / "_shared"
if not (SHARED_DIR / "deviation_atomic.py").exists():
    SHARED_DIR = SKILL_DIR / "scripts"
sys.path.insert(0, str(SHARED_DIR))

from deviation_atomic import (  # noqa: E402
    build_deviation_rows,
    collect_atomic_requirements,
    evaluate_response,
    is_generic_response,
)


class DeviationP0Tests(unittest.TestCase):
    def setUp(self):
        self.requirements = {
            "deviation_requirements": {
                "technical": [{
                    "id": "T1",
                    "requirement_text": "量程0-100 mg/m³；精度±2%；防护等级IP65",
                }],
                "commercial": [{
                    "id": "B1",
                    "requirement_text": "投标有效期：自提交投标文件截止之日起90天",
                }],
            }
        }

    def test_atomic_requirement_count(self):
        atoms = collect_atomic_requirements(self.requirements)
        self.assertEqual(4, len(atoms))
        self.assertEqual(3, sum(item["category"] == "technical" for item in atoms))

    def test_generic_response_is_blocked(self):
        for text in ("完全响应", "我方承诺完全满足", "无偏离", "按招标文件要求执行"):
            self.assertTrue(is_generic_response(text), text)
            self.assertFalse(evaluate_response("精度±2%", text, "technical")["passed"])

    def test_commercial_response_must_keep_starting_point(self):
        result = evaluate_response(
            "投标有效期：自提交投标文件截止之日起90天",
            "完全响应：承诺投标有效期90天",
            "commercial",
        )
        self.assertFalse(result["passed"])
        self.assertTrue(result["missing_anchors"])

    def test_complete_rows_pass(self):
        responses = {"responses": {
            "T1.1": "投标产品量程为0-100 mg/m³",
            "T1.2": "投标产品精度为±2%",
            "T1.3": "投标产品防护等级为IP65",
            "B1": "投标有效期：自提交投标文件截止之日起90天",
        }}
        rows = build_deviation_rows(self.requirements, responses)
        self.assertTrue(all(row["check"]["passed"] for row in rows))

    def test_empty_keywords_do_not_default_pass(self):
        path = SKILL_DIR / "scripts" / "check_response.py"
        spec = importlib.util.spec_from_file_location("check_response_under_test", path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        result = module.score_item("X1", "技术", "需", "任意内容")
        self.assertEqual("待人工核查", result["response_level"])
        self.assertFalse(result["evidence_declared"])


if __name__ == "__main__":
    unittest.main()
