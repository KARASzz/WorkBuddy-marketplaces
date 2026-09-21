#!/usr/bin/env python3
"""
D1 格式合规规则引擎。
读取 bid_format_rules.json，对投标文件全文和章节结构逐条匹配，
输出 /tmp/d1_result.json。
无第三方依赖，仅使用标准库。
"""
import argparse, json, re, sys
from pathlib import Path


def load(path: str) -> object:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def match_rule(rule: dict, text: str, sections: list) -> dict:
    """对单条规则执行匹配，返回检查结果 dict。"""
    keywords   = rule.get("keywords", [])
    match_type = rule.get("match_type", "content")
    found      = False
    evidence   = ""

    if match_type in ("content", "title_or_content"):
        for kw in keywords:
            # 全文搜索（忽略大小写）
            idx = text.find(kw)
            if idx >= 0:
                start = max(0, idx - 20)
                end   = min(len(text), idx + len(kw) + 40)
                evidence = "…" + text[start:end].replace("\n", " ") + "…"
                found = True
                break

    if not found and match_type in ("title_or_content", "structure"):
        titles = [s["title"] for s in sections]
        for kw in keywords:
            for title in titles:
                if kw in title:
                    evidence = f"章节标题：「{title}」"
                    found = True
                    break
            if found:
                break

    # status / severity 均反映实际检查结果：通过=通过，失败=规则固有等级
    actual = "通过" if found else rule["severity"]

    return {
        "rule_id":     rule.get("id", ""),
        "category":    rule.get("category", ""),
        "name":        rule.get("name", ""),
        "description": rule.get("description", rule.get("name", "")),
        "status":      actual,           # 实际结论（通过 / 废标 / 扣分 / 提醒）
        "severity":    actual,           # 与 status 保持一致，供报告着色/计数使用
        "rule_severity": rule["severity"],  # 保留规则固有等级，供需要的场景参考
        "evidence":    evidence if found else "",
        "suggestion":  "" if found else rule.get("suggestion", ""),
    }


def inject_tender_rules(rules: list, requirements: dict) -> list:
    """将招标文件的特殊格式要求注入规则列表（动态补充）。"""
    extra = []

    # 有效期要求
    validity = (requirements.get("commercial") or {}).get("validity_period", "")
    if validity:
        extra.append({
            "id": "F_DYN_001",
            "category": "有效期",
            "name": "投标有效期符合招标要求",
            "description": f"招标要求投标有效期为 {validity}",
            "keywords": [validity.replace("天", "").replace("日历天", "").strip(),
                         validity, "有效期"],
            "match_type": "content",
            "severity": "废标",
            "suggestion": f"在投标函中明确写明投标有效期为「{validity}」"
        })

    # 保证金要求
    bid_bond = (requirements.get("commercial") or {}).get("bid_bond", {})
    if isinstance(bid_bond, dict) and bid_bond.get("amount"):
        extra.append({
            "id": "F_DYN_002",
            "category": "保证金",
            "name": "投标保证金附件",
            "description": f"招标要求投标保证金 {bid_bond.get('amount')}",
            "keywords": ["保证金", "保函", "银行保函", bid_bond.get("amount", "")],
            "match_type": "content",
            "severity": "废标",
            "suggestion": f"附上 {bid_bond.get('amount')} 投标保证金（{bid_bond.get('form','银行保函或现金')}）相关文件"
        })

    return rules + extra


def main():
    parser = argparse.ArgumentParser(description="D1 格式合规规则引擎")
    parser.add_argument("--bid",        required=True, help="投标文件全文路径（.txt）")
    parser.add_argument("--structure",  required=True, help="投标文件结构 JSON 路径")
    parser.add_argument("--rules",      required=True, help="规则库路径（bid_format_rules.json）")
    parser.add_argument("--requirements", default="",  help="招标要求 JSON（可选，用于动态注入规则）")
    parser.add_argument("--output",     required=True, help="输出结果 JSON 路径")
    args = parser.parse_args()

    text       = Path(args.bid).read_text(encoding="utf-8")
    structure  = load(args.structure)
    rules_db   = load(args.rules)
    sections   = structure.get("sections", [])
    rules      = rules_db.get("rules", [])

    # 动态注入招标文件特殊要求
    if args.requirements and Path(args.requirements).exists():
        requirements = load(args.requirements)
        rules = inject_tender_rules(rules, requirements)

    results = []
    stats   = {"废标": 0, "扣分": 0, "提醒": 0, "通过": 0}

    for rule in rules:
        r = match_rule(rule, text, sections)
        results.append(r)
        stats[r["status"]] = stats.get(r["status"], 0) + 1

    # 废标项置顶
    severity_order = {"废标": 0, "扣分": 1, "提醒": 2, "通过": 3}
    results.sort(key=lambda x: severity_order.get(x["status"], 9))

    output = {
        "dimension": "D1",
        "name": "格式合规检查",
        "stats": stats,
        "total_rules": len(results),
        "items": results
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] D1 完成：废标 {stats['废标']} 项 | 扣分 {stats['扣分']} 项 | 提醒 {stats['提醒']} 项 | 通过 {stats['通过']} 项 → {args.output}")


if __name__ == "__main__":
    main()
