#!/usr/bin/env python3
"""Validate BQ01-BQ15 review and repair-plan JSON artifacts.

This validator is intentionally document-format agnostic: it neither reads nor writes DOCX.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


RULE_IDS = [f"BQ{i:02d}" for i in range(1, 16)]
STATUSES = {"pass", "fail", "insufficient_evidence"}
RISK_LEVELS = {"none", "P0", "P1", "P2", "manual_review"}
OWNERS = {"bid-document-generation", "word-document-processing", "manual"}


def _present(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return value is not None


def _load(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} 顶层必须是 JSON 对象")
    return data


def validate_artifacts(
    review: dict[str, Any],
    repair_plan: dict[str, Any],
    rules: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    rule_rows = rules.get("rules", [])
    rule_map = {row.get("rule_id"): row for row in rule_rows if isinstance(row, dict)}
    if sorted(rule_map) != RULE_IDS:
        errors.append("规则库必须且仅包含 BQ01-BQ15")

    bid_version = review.get("bid_version", {})
    document_hash = bid_version.get("document_sha256")
    if not _present(bid_version.get("document_path")) or not _present(document_hash):
        errors.append("bid_version 必须包含当前文件路径和 SHA256")

    final_layout = review.get("final_layout", {})
    physical_available = final_layout.get("physical_pages_available") is True
    if physical_available:
        if not _present(final_layout.get("rendered_pdf_path")):
            errors.append("已取得物理页码时必须记录 rendered_pdf_path")
        if not _present(final_layout.get("rendered_pdf_sha256")):
            errors.append("已取得物理页码时必须记录 rendered_pdf_sha256")
        if not isinstance(final_layout.get("page_count"), int) or final_layout.get("page_count", 0) <= 0:
            errors.append("已取得物理页码时 page_count 必须为正整数")

    checks = review.get("checks", [])
    if not isinstance(checks, list):
        return errors + ["checks 必须是数组"]
    check_map: dict[str, dict[str, Any]] = {}
    for check in checks:
        if not isinstance(check, dict):
            errors.append("checks 中每项必须是对象")
            continue
        rule_id = check.get("rule_id")
        if rule_id in check_map:
            errors.append(f"{rule_id}: 规则重复")
        check_map[rule_id] = check
    if sorted(check_map) != RULE_IDS:
        errors.append("审查结果必须且仅包含 BQ01-BQ15")

    non_pass: set[str] = set()
    for rule_id in RULE_IDS:
        check = check_map.get(rule_id)
        if not check:
            continue
        status = check.get("status")
        if status not in STATUSES:
            errors.append(f"{rule_id}: status 非法")
            continue
        if not physical_available and status == "pass":
            errors.append(f"{rule_id}: 无最终物理页码时不得判定通过")
        if not _present(check.get("evidence")):
            errors.append(f"{rule_id}: 缺少 evidence")

        if status == "pass":
            if check.get("risk_level") != "none":
                errors.append(f"{rule_id}: pass 的 risk_level 必须为 none")
            if physical_available and not _present(check.get("physical_pdf_pages")):
                errors.append(f"{rule_id}: pass 缺少物理 PDF 页证据")
            continue

        non_pass.add(rule_id)
        risk_level = check.get("risk_level")
        if risk_level not in RISK_LEVELS - {"none"}:
            errors.append(f"{rule_id}: 未通过项 risk_level 非法")
        for field in ("section", "anchor", "expected", "fix_instruction", "retest_condition", "repair_owner"):
            if not _present(check.get(field)):
                errors.append(f"{rule_id}: 未通过项缺少 {field}")
        owner = check.get("repair_owner")
        if owner not in OWNERS:
            errors.append(f"{rule_id}: repair_owner 非法")
        if status == "fail":
            pages = check.get("physical_pdf_pages")
            displayed = check.get("displayed_page_numbers")
            if not isinstance(pages, list) or not pages or not all(isinstance(page, int) and page > 0 for page in pages):
                errors.append(f"{rule_id}: fail 必须给出正整数物理 PDF 页")
            if not isinstance(displayed, list) or not displayed or not all(_present(page) for page in displayed):
                errors.append(f"{rule_id}: fail 必须给出显示页码，页面无页码时写“无”")
            allowed = set(rule_map.get(rule_id, {}).get("allowed_owners", []))
            if owner not in allowed:
                errors.append(f"{rule_id}: {owner} 不在允许的整改责任方中")
        elif risk_level != "manual_review":
            errors.append(f"{rule_id}: insufficient_evidence 必须标记 manual_review")

    if repair_plan.get("source_document_sha256") != document_hash:
        errors.append("整改计划与审查结果的源文件 SHA256 不一致")
    if repair_plan.get("max_auto_rounds") != 2:
        errors.append("max_auto_rounds 必须为 2")
    current_round = repair_plan.get("current_round")
    if not isinstance(current_round, int) or current_round < 0 or current_round > 2:
        errors.append("current_round 必须为 0-2 的整数")

    items = repair_plan.get("items", [])
    if not isinstance(items, list):
        return errors + ["整改计划 items 必须是数组"]
    item_rules: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            errors.append("整改计划 items 中每项必须是对象")
            continue
        rule_id = item.get("rule_id")
        item_rules.add(rule_id)
        if rule_id not in non_pass:
            errors.append(f"{rule_id}: 通过项不得进入整改计划")
        if item.get("owner") not in OWNERS:
            errors.append(f"{rule_id}: 整改责任方非法")
        for field in ("action", "retest_condition"):
            if not _present(item.get(field)):
                errors.append(f"{rule_id}: 整改计划缺少 {field}")
    if item_rules != non_pass:
        errors.append("整改计划必须覆盖且仅覆盖所有未通过/证据不足规则")

    target = repair_plan.get("target_document_path", "")
    if non_pass:
        if isinstance(current_round, int) and current_round < 2:
            match = re.search(r"_优化V(\d+)\.docx$", str(target))
            if not match:
                errors.append("整改目标文件名必须使用 _优化Vn.docx")
            elif int(match.group(1)) != current_round + 1:
                errors.append("整改目标版本号必须等于 current_round + 1")
            if target == bid_version.get("document_path"):
                errors.append("整改不得覆盖原文件")
            if repair_plan.get("requires_manual") is True:
                errors.append("未达到两轮上限时不应强制标记 requires_manual")
        elif current_round == 2:
            if _present(target):
                errors.append("已完成两轮自动整改后不得再生成自动整改目标")
            if repair_plan.get("requires_manual") is not True:
                errors.append("已完成两轮仍有未关闭项时必须转人工")
            if any(item.get("owner") != "manual" for item in items if isinstance(item, dict)):
                errors.append("两轮后未关闭事项的责任方必须转为 manual")

    state = review.get("document_state")
    if non_pass and state == "ready_for_manual_signing":
        errors.append("存在未通过项时不得标记 ready_for_manual_signing")
    if not non_pass and state != "ready_for_manual_signing":
        errors.append("十五项均通过时 document_state 应为 ready_for_manual_signing")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 BQ01-BQ15 评审与整改 JSON 契约")
    parser.add_argument("--review", required=True, type=Path)
    parser.add_argument("--repair-plan", required=True, type=Path)
    parser.add_argument("--rules", type=Path, default=Path(__file__).resolve().parent.parent / "resources" / "bid_quality_rules.json")
    args = parser.parse_args()
    try:
        errors = validate_artifacts(_load(args.review), _load(args.repair_plan), _load(args.rules))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"INVALID: {exc}")
        return 2
    if errors:
        print("INVALID")
        for error in errors:
            print(f"- {error}")
        return 2
    print("VALID: BQ01-BQ15 评审与整改制品契约通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
