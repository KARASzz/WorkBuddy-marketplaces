#!/usr/bin/env python3
"""
从招标文件原文中提取合规检查所需的关键要求。

本脚本是 投标文件合规检查 的降级入口：当用户未提供
tender_analysis.json 但提供了招标文件原件时，输出与 tender_analysis.json
关键字段兼容的 requirements JSON，供 D1-D5 检查脚本复用。
"""
import argparse
import json
import re
import sys
from pathlib import Path


def read_text(path: str) -> str:
    p = Path(path)
    if not p.exists():
        print(f"[error] 找不到招标文件：{path}", file=sys.stderr)
        sys.exit(1)
    suffix = p.suffix.lower()
    if suffix == ".docx":
        try:
            from docx import Document
            return "\n".join(para.text for para in Document(str(p)).paragraphs)
        except Exception as exc:
            print(f"[warn] docx 读取失败，尝试按文本读取：{exc}", file=sys.stderr)
    if suffix == ".pdf":
        try:
            import pdfplumber
            chunks = []
            with pdfplumber.open(str(p)) as pdf:
                for page in pdf.pages:
                    chunks.append(page.extract_text() or "")
            return "\n".join(chunks)
        except Exception as exc:
            print(f"[warn] PDF 读取失败，尝试按文本读取：{exc}", file=sys.stderr)
    return p.read_text(encoding="utf-8", errors="replace")


def first_match(patterns: list[str], text: str, default: str = "文件未载明") -> str:
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            return next((g for g in m.groups() if g), m.group(0)).strip()
    return default


def nearby(text: str, keywords: list[str], width: int = 120) -> str:
    for kw in keywords:
        idx = text.find(kw)
        if idx >= 0:
            start = max(0, idx - width)
            end = min(len(text), idx + width)
            return text[start:end].replace("\n", " ")
    return ""


def extract_project_overview(text: str) -> dict:
    project_name = first_match([
        r"项目名称[：:\s]+([^\n。；;]{2,80})",
        r"采购项目名称[：:\s]+([^\n。；;]{2,80})",
    ], text)
    buyer = first_match([
        r"(?:采购人|招标人)[：:\s]+([^\n。；;]{2,80})",
    ], text)
    return {
        "project_name": project_name,
        "buyer": buyer,
        "budget": first_match([r"(?:预算金额|最高限价|控制价)[：:\s]*([人民币¥￥\d,.]+ ?[万亿元]*)"], text),
        "duration": first_match([r"(?:服务期|合同期限|交付周期)[：:\s]*([^\n。；;]{2,50})"], text),
        "location": first_match([r"(?:实施地点|交付地点|服务地点)[：:\s]*([^\n。；;]{2,80})"], text),
        "contact": first_match([r"(?:联系人|联系方式)[：:\s]*([^\n。；;]{2,80})"], text),
        "background": nearby(text, ["项目背景", "建设目标", "采购需求"], width=80) or "文件未载明",
    }


def extract_commercial(text: str) -> dict:
    max_price = first_match([
        r"(?:最高限价|控制价|预算金额)[：:\s]*([人民币¥￥\d,.]+ ?[万亿元]*)",
        r"不得超过\s*([人民币¥￥\d,.]+ ?[万亿元]*)",
    ], text)
    validity = first_match([
        r"投标有效期[：:\s]*(\d+\s*(?:日历天|天|日))",
        r"有效期[^\d]{0,10}(\d+\s*(?:日历天|天|日))",
    ], text)
    bond_amount = first_match([
        r"投标保证金[：:\s]*(?:金额)?[：:\s]*([人民币¥￥\d,.]+ ?[万亿元]*)",
        r"保证金[^\d]{0,10}([人民币¥￥\d,.]+ ?[万亿元]*)",
    ], text, default="")
    bond_form = first_match([
        r"投标保证金[^\n。；;]*(银行保函|电汇|转账|现金|支票|保险保函)",
    ], text, default="文件未载明")
    return {
        "bid_bond": {"amount": bond_amount or "文件未载明", "form": bond_form, "validity": validity},
        "performance_bond": first_match([r"履约保证金[：:\s]*([^\n。；;]{2,80})"], text),
        "max_price": max_price,
        "validity_period": validity,
        "payment_terms": nearby(text, ["付款方式", "付款条件", "付款节点"], width=100) or "文件未载明",
        "warranty_period": first_match([r"(?:质保期|免费维护期)[：:\s]*([^\n。；;]{2,50})"], text),
        "acceptance_criteria": nearby(text, ["验收标准", "验收要求"], width=100) or "文件未载明",
        "subcontracting": nearby(text, ["分包", "转包"], width=100) or "文件未载明",
    }


def extract_qualifications(text: str) -> dict:
    mandatory = []
    candidates = [
        ("企业资质", "系统集成商资质", "资质证书复印件"),
        ("信息安全", "ISO 27001 信息安全管理体系认证", "认证证书复印件"),
        ("人员资质", "项目经理须持 PMP 或软考高级证书", "证书复印件及社保证明"),
        ("业绩要求", "近三年同类项目业绩", "合同复印件或中标通知书"),
        ("财务能力", "最近一年度营业收入或财务状况要求", "审计报告或完税证明"),
    ]
    for category, requirement, document in candidates:
        if any(part in text for part in re.split(r"\s|或", requirement) if len(part) >= 2):
            mandatory.append({
                "category": category,
                "requirement": requirement,
                "document": document,
                "source": "自动提取，需人工复核",
            })
    return {"mandatory": mandatory, "bonus": []}


def extract_risks(text: str, commercial: dict) -> list[dict]:
    risks = []
    if commercial.get("max_price") != "文件未载明":
        risks.append({
            "risk": f"投标报价超过{commercial['max_price']}最高限价",
            "source": "自动提取，需人工复核",
            "level": "高",
            "avoidance": f"含税总价须不超过{commercial['max_price']}",
        })
    if commercial.get("validity_period") != "文件未载明":
        risks.append({
            "risk": f"投标有效期不足{commercial['validity_period']}",
            "source": "自动提取，需人工复核",
            "level": "高",
            "avoidance": f"在投标函中承诺有效期{commercial['validity_period']}",
        })
    if "盖章" in text or "签字" in text:
        risks.append({
            "risk": "投标文件签字或盖章不符合要求",
            "source": "自动提取，需人工复核",
            "level": "高",
            "avoidance": "关键文件按要求签字并加盖公章",
        })
    return risks


def extract_scoring(text: str) -> dict:
    return {
        "technical_score": {"total": 0, "items": [], "checksum_pass": True},
        "commercial_score": {"total": 0, "items": []},
        "price_score": {"total": 0, "formula": nearby(text, ["价格分", "报价得分", "评标基准价"], width=120)},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="从招标文件提取合规检查 requirements JSON")
    parser.add_argument("file", help="招标文件路径（.docx/.pdf/.txt）")
    parser.add_argument("--output", default="/tmp/requirements.json", help="输出 JSON 路径")
    args = parser.parse_args()

    text = read_text(args.file)
    commercial = extract_commercial(text)
    data = {
        "project_overview": extract_project_overview(text),
        "commercial": commercial,
        "qualifications": extract_qualifications(text),
        "risks": extract_risks(text, commercial),
        "scoring": extract_scoring(text),
        "_meta": {
            "source_file": str(Path(args.file).resolve()),
            "extraction_mode": "rule_fallback",
            "requires_human_review": True,
        },
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] requirements 已提取 → {out}")


if __name__ == "__main__":
    main()
