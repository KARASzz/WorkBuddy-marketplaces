import copy
import importlib.util
import json
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = SKILL_DIR / "scripts" / "validate_bid_quality_artifacts.py"
SPEC = importlib.util.spec_from_file_location("bid_quality_validator", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)
RULES = json.loads((SKILL_DIR / "resources" / "bid_quality_rules.json").read_text(encoding="utf-8"))


def pass_check(rule_id):
    return {
        "rule_id": rule_id,
        "status": "pass",
        "risk_level": "none",
        "physical_pdf_pages": [1],
        "displayed_page_numbers": ["1"],
        "section": "第一章",
        "anchor": "示例锚点",
        "evidence": ["当前版本证据"],
    }


def base_review():
    return {
        "schema_version": "1.0",
        "bid_version": {"document_path": "/tmp/标书.docx", "document_sha256": "abc123"},
        "final_layout": {
            "physical_pages_available": True,
            "rendered_pdf_path": "/tmp/标书.pdf",
            "rendered_pdf_sha256": "pdf123",
            "page_count": 20,
        },
        "document_state": "ready_for_manual_signing",
        "checks": [pass_check(rule_id) for rule_id in MODULE.RULE_IDS],
    }


def base_plan():
    return {
        "schema_version": "1.0",
        "source_document_sha256": "abc123",
        "current_round": 0,
        "max_auto_rounds": 2,
        "requires_manual": False,
        "target_document_path": "",
        "items": [],
    }


class BidQualityContractTests(unittest.TestCase):
    def test_each_rule_supports_pass_fail_and_insufficient_evidence(self):
        rule_map = {row["rule_id"]: row for row in RULES["rules"]}
        for rule_id in MODULE.RULE_IDS:
            for status in ("pass", "fail", "insufficient_evidence"):
                with self.subTest(rule_id=rule_id, status=status):
                    review = base_review()
                    plan = base_plan()
                    check = next(row for row in review["checks"] if row["rule_id"] == rule_id)
                    if status != "pass":
                        owner = rule_map[rule_id]["default_owner"] if status == "fail" else "manual"
                        check.update({
                            "status": status,
                            "risk_level": "P1" if status == "fail" else "manual_review",
                            "expected": "达到规则要求",
                            "fix_instruction": "按锚点定点整改",
                            "retest_condition": "新版本重新检查",
                            "repair_owner": owner,
                        })
                        if status == "insufficient_evidence":
                            check["physical_pdf_pages"] = []
                            check["displayed_page_numbers"] = []
                        review["document_state"] = "draft_blocked"
                        plan["target_document_path"] = "/tmp/标书_优化V1.docx"
                        plan["items"] = [{
                            "rule_id": rule_id,
                            "owner": owner,
                            "action": "按锚点定点整改",
                            "retest_condition": "新版本重新检查",
                        }]
                    self.assertEqual([], MODULE.validate_artifacts(review, plan, RULES))

    def test_no_physical_pages_cannot_pass(self):
        review = base_review()
        review["final_layout"] = {"physical_pages_available": False}
        errors = MODULE.validate_artifacts(review, base_plan(), RULES)
        self.assertTrue(any("无最终物理页码时不得判定通过" in error for error in errors))

    def test_failed_item_requires_both_page_coordinates(self):
        review = base_review()
        check = review["checks"][0]
        check.update({
            "status": "fail",
            "risk_level": "P1",
            "physical_pdf_pages": [],
            "displayed_page_numbers": [],
            "expected": "达到规则要求",
            "fix_instruction": "定点整改",
            "retest_condition": "新版本复验",
            "repair_owner": "bid-document-generation",
        })
        review["document_state"] = "draft_blocked"
        plan = base_plan()
        plan["target_document_path"] = "/tmp/标书_优化V1.docx"
        plan["items"] = [{"rule_id": "BQ01", "owner": "bid-document-generation", "action": "整改", "retest_condition": "复验"}]
        errors = MODULE.validate_artifacts(review, plan, RULES)
        self.assertTrue(any("物理 PDF 页" in error for error in errors))
        self.assertTrue(any("显示页码" in error for error in errors))

    def test_repair_target_must_not_overwrite_source(self):
        review = base_review()
        check = review["checks"][4]
        check.update({
            "status": "fail",
            "risk_level": "P1",
            "expected": "编号连续",
            "fix_instruction": "修复编号",
            "retest_condition": "重新渲染",
            "repair_owner": "word-document-processing",
        })
        review["document_state"] = "draft_blocked"
        plan = base_plan()
        plan["target_document_path"] = "/tmp/标书.docx"
        plan["items"] = [{"rule_id": "BQ05", "owner": "word-document-processing", "action": "修复编号", "retest_condition": "重新渲染"}]
        errors = MODULE.validate_artifacts(review, plan, RULES)
        self.assertTrue(any("不得覆盖原文件" in error for error in errors))

    def test_second_round_targets_v2_and_then_stops(self):
        review = base_review()
        check = review["checks"][4]
        check.update({
            "status": "fail",
            "risk_level": "P1",
            "expected": "编号连续",
            "fix_instruction": "修复编号",
            "retest_condition": "重新渲染",
            "repair_owner": "word-document-processing",
        })
        review["document_state"] = "draft_blocked"
        plan = base_plan()
        plan.update({
            "current_round": 1,
            "target_document_path": "/tmp/标书_优化V2.docx",
            "items": [{"rule_id": "BQ05", "owner": "word-document-processing", "action": "修复编号", "retest_condition": "重新渲染"}],
        })
        self.assertEqual([], MODULE.validate_artifacts(review, plan, RULES))

        plan.update({
            "current_round": 2,
            "requires_manual": True,
            "target_document_path": "",
            "items": [{"rule_id": "BQ05", "owner": "manual", "action": "人工处理", "retest_condition": "人工处理后复验"}],
        })
        self.assertEqual([], MODULE.validate_artifacts(review, plan, RULES))


if __name__ == "__main__":
    unittest.main()
