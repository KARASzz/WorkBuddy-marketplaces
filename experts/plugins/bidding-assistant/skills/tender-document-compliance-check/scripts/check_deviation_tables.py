#!/usr/bin/env python3
"""检查技术/商务偏离表是否逐条、具体、完整响应。"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


LOCAL_SCRIPTS = Path(__file__).resolve().parent
if str(LOCAL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(LOCAL_SCRIPTS))

from deviation_atomic import (  # noqa: E402
    collect_atomic_requirements,
    evaluate_response,
    load_json,
    normalize_text,
)


def _find_column(headers: list[str], candidates: tuple[str, ...]) -> int | None:
    for index, header in enumerate(headers):
        if any(candidate in header for candidate in candidates):
            return index
    return None


def extract_docx_rows(path: Path) -> list[dict]:
    from docx import Document

    document = Document(path)
    results = []
    for table_index, table in enumerate(document.tables, 1):
        if not table.rows:
            continue
        headers = [cell.text.strip() for cell in table.rows[0].cells]
        requirement_col = _find_column(headers, (
            "招标要求", "采购要求", "技术参数", "商务条款", "要求原文", "条款内容",
        ))
        response_col = _find_column(headers, ("投标响应", "响应内容", "我方响应", "响应说明"))
        if requirement_col is None or response_col is None:
            continue
        deviation_col = _find_column(headers, ("偏离情况", "偏离说明", "偏差"))
        evidence_col = _find_column(headers, ("证明材料", "证明文件", "页码", "依据", "证据"))
        for row_index, row in enumerate(table.rows[1:], 2):
            cells = [cell.text.strip() for cell in row.cells]
            results.append({
                "row_key": f"table-{table_index}-row-{row_index}",
                "table": table_index,
                "row": row_index,
                "requirement_text": cells[requirement_col] if requirement_col < len(cells) else "",
                "response_text": cells[response_col] if response_col < len(cells) else "",
                "deviation": cells[deviation_col] if deviation_col is not None and deviation_col < len(cells) else "",
                "evidence": cells[evidence_col] if evidence_col is not None and evidence_col < len(cells) else "",
            })
    return results


def extract_json_rows(path: Path) -> list[dict]:
    data = load_json(path)
    rows = data.get("rows") or []
    results = []
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            continue
        copied = dict(row)
        copied["row_key"] = f"json-row-{index}"
        copied["table"] = copied.get("category") or "json"
        copied["row"] = index
        results.append(copied)
    return results


def match_rows(atoms: list[dict], rows: list[dict]) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for atom in atoms:
        requirement = normalize_text(atom["requirement_text"])
        exact_id = [row for row in rows if str(row.get("id") or "") == atom["id"]]
        if exact_id:
            result[atom["id"]] = exact_id
            continue
        result[atom["id"]] = [
            row for row in rows
            if requirement and (
                requirement == normalize_text(row.get("requirement_text"))
                or requirement in normalize_text(row.get("requirement_text"))
            )
        ]
    return result


def make_review_item(atom: dict, matches: list[dict], merged: bool) -> dict:
    rule_id = "E05" if atom["category"] == "technical" else "E06"
    rule = (
        "技术参数必须拆为一条原子要求一行，响应写明具体参数、数值、单位和条件"
        if atom["category"] == "technical"
        else "商务条款必须逐条完整应答，保留期限、起算点、金额、地点和限制条件"
    )
    severity = "废标" if atom.get("mandatory") else "扣分"
    if not matches:
        return {
            "rule_id": rule_id,
            "check_item": f"{atom['id']} 原子要求逐条响应",
            "rule": rule,
            "status": "未响应",
            "severity": severity,
            "priority": "P0",
            "evidence": atom["requirement_text"],
            "location": atom.get("source") or "招标要求",
            "risk": "偏离表未找到该原子要求的独立响应行",
            "suggestion": "新增独立表格行，逐字保留招标要求并填写具体投标响应",
            "verification": "该要求仅匹配一行，响应列包含全部具体要素",
            "requirement_id": atom["id"],
        }
    if len(matches) > 1:
        locations = "、".join(row["row_key"] for row in matches[:5])
        return {
            "rule_id": rule_id,
            "check_item": f"{atom['id']} 原子要求唯一响应",
            "rule": rule,
            "status": "重复响应",
            "severity": severity,
            "priority": "P0",
            "evidence": atom["requirement_text"],
            "location": locations,
            "risk": "同一原子要求出现多行，可能造成响应口径冲突",
            "suggestion": "合并重复行并保留一条完整、可核验的投标响应",
            "verification": "每个 requirement_id 仅存在一条响应行",
            "requirement_id": atom["id"],
        }

    row = matches[0]
    if merged:
        return {
            "rule_id": rule_id,
            "check_item": f"{atom['id']} 一条参数一行",
            "rule": rule,
            "status": "合并响应",
            "severity": severity,
            "priority": "P0",
            "evidence": row.get("requirement_text") or atom["requirement_text"],
            "location": row["row_key"],
            "risk": "多个原子要求合并在同一表格行，无法逐项评审",
            "suggestion": "将该行拆分，每一行只保留一个招标参数或商务条款",
            "verification": "原子要求数与独立响应行数一致，任何行只映射一个 requirement_id",
            "requirement_id": atom["id"],
        }

    check = evaluate_response(atom["requirement_text"], row.get("response_text") or "", atom["category"])
    passed = check["passed"]
    return {
        "rule_id": rule_id,
        "check_item": f"{atom['id']} 响应内容充分性",
        "rule": rule,
        "status": "通过" if passed else ("泛化响应" if check["generic"] else "部分响应"),
        "severity": "通过" if passed else severity,
        "priority": "" if passed else "P0",
        "evidence": f"要求：{atom['requirement_text']}；响应：{row.get('response_text') or '空'}",
        "location": row["row_key"],
        "risk": "响应具体完整" if passed else check["reason"],
        "suggestion": "无需整改" if passed else "按要求原文补全具体参数、数值、单位、期限、起算点和限制条件；不得只写泛化结论",
        "verification": "响应非泛化表述，所有参数事实和条件均通过逐项比对",
        "requirement_id": atom["id"],
        "response_check": check,
    }


def review(requirements: dict, rows: list[dict]) -> dict:
    atoms = collect_atomic_requirements(requirements)
    matches = match_rows(atoms, rows)
    row_to_atoms: dict[str, list[str]] = defaultdict(list)
    for atom_id, matched_rows in matches.items():
        if len(matched_rows) == 1:
            row_to_atoms[matched_rows[0]["row_key"]].append(atom_id)
    items = [
        make_review_item(
            atom,
            matches.get(atom["id"], []),
            bool(matches.get(atom["id"]) and len(row_to_atoms[matches[atom["id"]][0]["row_key"]]) > 1),
        )
        for atom in atoms
    ]
    if not atoms:
        items.append({
            "rule_id": "E05/E06",
            "check_item": "偏离要求原子清单",
            "rule": "必须先取得技术/商务原子要求清单再审查偏离表",
            "status": "未执行",
            "severity": "提醒",
            "priority": "P0",
            "evidence": "未从 requirements 中提取到偏离要求",
            "location": "输入材料",
            "risk": "无法确认技术和商务条款是否逐项应答",
            "suggestion": "补充 deviation_requirements.technical/commercial 后重新审查",
            "verification": "原子要求清单非空并与偏离表逐行匹配",
        })
    blockers = [item for item in items if item.get("priority") == "P0"]
    return {
        "schema_version": "1.0",
        "summary": {
            "requirements": len(atoms),
            "table_rows": len(rows),
            "passed": sum(item.get("status") == "通过" for item in items),
            "failed": len(blockers),
            "ok": bool(atoms) and not blockers,
        },
        "items": items,
        "blockers": blockers,
        "ok": bool(atoms) and not blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="检查技术/商务偏离表逐条有效应答")
    parser.add_argument("--requirements", required=True, help="tender_analysis.json 或偏离要求 JSON")
    parser.add_argument("--bid", default="", help="最终投标 DOCX")
    parser.add_argument("--deviation-json", default="", help="结构化偏离表 JSON")
    parser.add_argument("--output", default="/tmp/deviation_review_result.json")
    args = parser.parse_args()
    if not args.bid and not args.deviation_json:
        parser.error("--bid 与 --deviation-json 至少提供一个")
    if args.bid:
        bid_path = Path(args.bid).expanduser()
        if bid_path.suffix.lower() != ".docx" or not bid_path.is_file():
            parser.error("--bid 必须是存在的 DOCX 文件")
        rows = extract_docx_rows(bid_path)
    else:
        deviation_path = Path(args.deviation_json).expanduser()
        if not deviation_path.is_file():
            parser.error(f"偏离表 JSON 不存在: {deviation_path}")
        rows = extract_json_rows(deviation_path)
    result = review(load_json(args.requirements), rows)
    output = Path(args.output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": result["ok"], "summary": result["summary"], "output": str(output)}, ensure_ascii=False))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
