#!/usr/bin/env python3
"""生成技术/商务偏离表：一条原子要求对应一行，泛化响应直接阻断。"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


LOCAL_SCRIPTS = Path(__file__).resolve().parent
if str(LOCAL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(LOCAL_SCRIPTS))

from deviation_atomic import build_deviation_rows, load_json, summarize_rows  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="生成原子化技术/商务偏离表")
    parser.add_argument("--requirements", required=True, help="tender_analysis.json 或偏离要求 JSON")
    parser.add_argument("--responses", default="", help="投标响应 JSON；缺失响应将作为 P0 阻断")
    parser.add_argument("--output", default="/tmp/deviation_tables.json", help="结构化偏离表 JSON")
    args = parser.parse_args()

    requirements = load_json(args.requirements)
    responses = load_json(args.responses)
    rows = build_deviation_rows(requirements, responses)
    summary = summarize_rows(rows)
    blockers = [
        {
            "id": row.get("id"),
            "category": row.get("category"),
            "requirement": row.get("requirement_text"),
            "reason": (row.get("check") or {}).get("reason"),
            "action": "补充包含具体参数、数值、单位、期限及起算条件的逐条响应",
        }
        for row in rows if not (row.get("check") or {}).get("passed")
    ]
    if not rows:
        blockers.append({
            "id": "NO_REQUIREMENTS",
            "category": "all",
            "requirement": "",
            "reason": "未提取到技术或商务偏离要求",
            "action": "补充 deviation_requirements.technical/commercial 后重新生成",
        })
    result = {
        "schema_version": "1.0",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "requirements_source": str(Path(args.requirements).expanduser().resolve()),
        "responses_source": str(Path(args.responses).expanduser().resolve()) if args.responses else None,
        "summary": summary,
        "rows": rows,
        "blockers": blockers,
        "ok": bool(rows) and not blockers,
    }
    output = Path(args.output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": result["ok"], "summary": summary, "output": str(output)}, ensure_ascii=False))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
