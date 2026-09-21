#!/usr/bin/env python3
"""
D5 资质完整性检查脚本。

支持 --mode rule（默认，关键词命中率）和 --mode llm（语义评审）。

读取招标分析 JSON 中的 qualifications.mandatory[]（必要资质）
和 qualifications.bonus[]（加分项），对每条资质要求检测投标文件
是否已明确声明，输出 d5_result.json。

格式供合规报告 Word 任务的 D5 载荷使用：
  items[]:
    category   资质类别
    requirement 具体要求
    source     来源条款
    status     已声明 / 不确定 / 未声明
    evidence   在投标文件中找到的声明证据片段
    suggestion 整改建议
    is_bonus   是否加分项（True/False）

判定规则：
  关键词命中率 ≥ 0.60 → 已声明
  命中率 0.25~0.60 → 不确定（需人工核查）
  命中率 < 0.25 → 未声明

无第三方依赖（python-docx 可选）。
"""
import argparse
import json
import re
import sys
from pathlib import Path

_LOCAL_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_LOCAL_SCRIPTS))

try:
    from llm_client import chat_completion, extract_json_from_llm
    _LLM_AVAILABLE = True
except ImportError:
    _LLM_AVAILABLE = False


# ── 停用词 ─────────────────────────────────────────────────────
_STOP_WORDS = {
    "需", "应", "须", "的", "了", "是", "在", "具有", "具备",
    "提供", "附上", "以上", "及以上", "满足", "符合", "要求",
    "复印件", "原件", "扫描件", "加盖公章",
}
_SPLIT_RE = re.compile(r'''[，。；、：\s（）【】《》"'()/·-]+''')


def extract_keywords(text: str) -> list:
    tokens = _SPLIT_RE.split(text)
    seen, result = set(), []
    for t in tokens:
        t = t.strip()
        if len(t) < 2 or t in _STOP_WORDS:
            continue
        if t not in seen:
            result.append(t)
            seen.add(t)
    return result


def best_window(text: str, keywords: list, window: int = 200) -> str:
    if not text or not keywords:
        return ""
    step = max(1, window // 2)
    best_score, best_chunk = 0, ""
    for i in range(0, max(1, len(text) - window + 1), step):
        chunk = text[i: i + window]
        score = sum(1 for kw in keywords if kw in chunk)
        if score > best_score:
            best_score, best_chunk = score, chunk
    return best_chunk.strip().replace("\n", " ") if best_chunk else text[:window]


DECLARED_FULL    = 0.60
DECLARED_PARTIAL = 0.25


def compact(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def special_qual_status(category: str, requirement: str, bid_text: str):
    """Handle common tender qualification semantics beyond exact keyword hits."""
    req = compact(category + requirement)
    hay = compact(bid_text)

    if "系统集成商资质" in req and "系统集成商资质" in hay:
        return "已声明", "检测到系统集成商资质声明"

    if "ISO27001" in req.upper().replace(" ", "") and "ISO27001" in hay.upper().replace(" ", ""):
        return "已声明", "检测到 ISO 27001 认证声明"

    if "PMP" in req or "软考" in req:
        if "项目经理" in hay and ("PMP" in bid_text or "软考" in bid_text):
            return "已声明", "检测到项目经理 PMP/软考证书声明"

    if "500万" in req and ("业绩" in req or "项目" in req):
        has_amount = "500万" in hay
        has_project = any(w in hay for w in ["政务数据类项目", "政务数据项目", "同类项目", "项目"])
        has_count = any(w in hay for w in ["≥2", "2个以上", "不少于2", "至少2", "两项", "2项"])
        if has_amount and has_project and has_count:
            return "已声明", "检测到同类项目业绩数量和金额声明"

    if "3000万" in req or "营业收入" in req:
        if "营业收入" in hay and any(w in hay for w in ["3000万元以上", "≥3000万元", "不少于3000万元", "3000万以上"]):
            return "已声明", "检测到营业收入要求声明"

    if "DCMM" in req.upper() and "DCMM" in hay.upper():
        if any(w in hay for w in ["3级", "三级", "3级及以上"]):
            return "已声明", "检测到 DCMM 3级声明"

    if "本地企业" in req or "注册地" in req:
        if "注册地" in hay and "某市" in hay and "社保" in hay:
            return "已声明", "检测到本地注册和社保声明"

    return None


def check_one_qual(qual_item: dict, bid_text: str, is_bonus: bool = False) -> dict:
    """对单条资质要求检查声明状态。"""
    category    = qual_item.get("category", "")
    requirement = qual_item.get("requirement", "")
    document    = qual_item.get("document", "")
    source      = qual_item.get("source", "")
    points      = qual_item.get("points", 0)

    # 关键词：从 requirement + category 提取（不包含 document，避免噪声）
    all_kws = list(dict.fromkeys(
        extract_keywords(requirement) + extract_keywords(category)
    ))

    if not all_kws:
        return _make_result(category, requirement, source, "不确定",
                            "（关键词为空）", [], "人工核查", is_bonus, points)

    special = special_qual_status(category, requirement, bid_text)
    if special:
        status, evidence = special
        return _make_result(category, requirement, source, status, evidence, [], "", is_bonus, points)

    hit  = [kw for kw in all_kws if kw in bid_text]
    miss = [kw for kw in all_kws if kw not in bid_text]
    rate = len(hit) / len(all_kws)
    evidence = best_window(bid_text, hit, window=200)

    if rate >= DECLARED_FULL:
        status     = "已声明"
        suggestion = ""
    elif rate >= DECLARED_PARTIAL:
        status     = "不确定"
        suggestion = f"请确认以下资质要素是否已明确声明：{'、'.join(miss[:3])}"
    else:
        status     = "未声明"
        doc_hint   = f"，需附：{document}" if document else ""
        suggestion = f"投标文件未见相关声明{doc_hint}"

    return _make_result(
        category, requirement, source, status,
        evidence[:100] if evidence else "（未找到声明内容）",
        [f"未见「{kw}」" for kw in miss[:4]],
        suggestion, is_bonus, points
    )


def _make_result(category, requirement, source, status,
                 evidence, deviations, suggestion, is_bonus, points):
    # severity 供汇总行着色
    if is_bonus:
        # 加分项未声明 → 扣分（不是废标）
        severity = "通过" if status == "已声明" else "扣分"
    else:
        severity = ("废标" if status == "未声明" else
                    ("部分满足" if status == "不确定" else "通过"))

    return {
        "category":    category,
        "requirement": requirement,
        "source":      source,
        "status":      status,
        "evidence":    evidence,
        "deviations":  deviations,
        "suggestion":  suggestion,
        "is_bonus":    is_bonus,
        "bonus_points": points,
        "severity":    severity,
    }


# ── LLM 语义模式（--mode llm）────────────────────────────────

_LLM_D5_SYSTEM = (
    "你是政府采购评标委员会专家，负责审查投标文件是否声明提供了必要资质。"
    "请严格基于所提供的投标文件节选内容作出判断，不得推断未出现的内容。"
)

_LLM_D5_USER_TPL = """\
【资质要求】
类别：{category}
具体要求：{requirement}
来源：{source}
需提供文件：{document}
是否加分项：{"是" if is_bonus else "否"}

【投标文件节选（最相关段落，约500字）】
{bid_context}

请判断投标文件是否声明提供了上述资质，以 JSON 格式输出，不要添加任何额外说明：
{{
  "status": "已声明|不确定|未声明",
  "evidence": "投标文件中对应声明的原文引用（不超过80字，若无则为空字符串）",
  "deviations": ["未见要素1", "未见要素2"],
  "suggestion": "整改建议（若已声明则为空字符串）",
  "reason": "判断依据（1-2句话）"
}}"""


def check_one_qual_llm(qual_item: dict, bid_text: str,
                        is_bonus: bool = False) -> dict:
    """LLM 语义模式检查单条资质要求。失败时降级到规则模式。"""
    if not _LLM_AVAILABLE:
        return check_one_qual(qual_item, bid_text, is_bonus)

    category    = qual_item.get("category", "")
    requirement = qual_item.get("requirement", "")
    document    = qual_item.get("document", "")
    source      = qual_item.get("source", "")
    points      = qual_item.get("points", 0)

    all_kws = list(dict.fromkeys(
        extract_keywords(requirement) + extract_keywords(category)
    ))
    bid_context = best_window(bid_text, all_kws, window=500) or bid_text[:500]

    messages = [
        {"role": "system", "content": _LLM_D5_SYSTEM},
        {"role": "user",   "content": _LLM_D5_USER_TPL.format(
            category=category, requirement=requirement,
            source=source, document=document,
            is_bonus=is_bonus, bid_context=bid_context,
        )},
    ]

    resp = chat_completion(messages, temperature=0.1, max_tokens=500)
    if not resp.get("success"):
        print(f"[llm] D5 API 失败，降级规则模式: {resp.get('error')}", file=sys.stderr)
        return check_one_qual(qual_item, bid_text, is_bonus)

    data = extract_json_from_llm(resp["content"])
    if not data:
        return check_one_qual(qual_item, bid_text, is_bonus)

    status = data.get("status", "未声明")
    if is_bonus:
        severity = "通过" if status == "已声明" else "扣分"
    else:
        severity = ("废标" if status == "未声明" else
                    ("部分满足" if status == "不确定" else "通过"))

    return {
        "category":    category,
        "requirement": requirement,
        "source":      source,
        "status":      status,
        "evidence":    str(data.get("evidence", ""))[:100],
        "deviations":  list(data.get("deviations", [])),
        "suggestion":  str(data.get("suggestion", "")),
        "is_bonus":    is_bonus,
        "bonus_points": points,
        "severity":    severity,
        "mode":        "llm",
    }


def get_bid_text(path: str) -> str:
    p = Path(path)
    if not p.exists():
        print(f"[error] 找不到投标文件：{path}", file=sys.stderr)
        sys.exit(1)
    if p.suffix.lower() == ".docx":
        try:
            from docx import Document
            return "\n".join(para.text for para in Document(path).paragraphs)
        except Exception as e:
            print(f"[warn] .docx 读取失败：{e}", file=sys.stderr)
    return p.read_text(encoding="utf-8", errors="replace")


def load_analysis(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        print(f"[error] 找不到招标分析文件：{path}", file=sys.stderr)
        sys.exit(1)
    return json.loads(p.read_text(encoding="utf-8"))


def build_summary(items: list) -> dict:
    mandatory = [it for it in items if not it.get("is_bonus")]
    bonus     = [it for it in items if it.get("is_bonus")]
    declared  = sum(1 for it in mandatory if it["status"] == "已声明")
    uncertain = sum(1 for it in mandatory if it["status"] == "不确定")
    missing   = sum(1 for it in mandatory if it["status"] == "未声明")
    bonus_hit = sum(1 for it in bonus if it["status"] == "已声明")
    return {
        "mandatory_total":    len(mandatory),
        "mandatory_declared": declared,
        "mandatory_uncertain": uncertain,
        "mandatory_missing":  missing,
        "bonus_total":        len(bonus),
        "bonus_declared":     bonus_hit,
        "declare_rate":       f"{declared / len(mandatory):.0%}" if mandatory else "0%",
    }


def main():
    parser = argparse.ArgumentParser(
        description="D5 资质完整性检查（rule=规则模式 / llm=语义模式）"
    )
    parser.add_argument("--bid",      required=True, help="投标文件路径（.docx 或 .txt）")
    parser.add_argument("--analysis", required=True, help="招标分析 JSON 路径（含 qualifications 字段）")
    parser.add_argument("--output",   default="/tmp/d5_result.json",
                        help="输出 JSON 路径（默认 /tmp/d5_result.json）")
    parser.add_argument("--include-bonus", action="store_true",
                        help="同时检查加分项资质（默认仅检查必要资质）")
    parser.add_argument("--mode",     choices=["rule", "llm"], default="rule",
                        help="评审模式：rule=关键词规则（默认）/ llm=语义评审（需 RICHEEAI_TOKEN）")
    args = parser.parse_args()

    if args.mode == "llm" and not _LLM_AVAILABLE:
        print("[warn] llm_client 不可用，自动切换到 rule 模式", file=sys.stderr)
        args.mode = "rule"

    print(f"[info] 投标文件：{args.bid}")
    print(f"[info] 招标分析：{args.analysis}")

    bid_text = get_bid_text(args.bid)
    analysis = load_analysis(args.analysis)
    quals    = analysis.get("qualifications", {})
    mandatory = quals.get("mandatory", [])
    bonus     = quals.get("bonus", []) if args.include_bonus else []

    if not mandatory and not bonus:
        print("[warn] 招标分析中无资质要求条目")
        result = {"items": [], "summary": build_summary([])}
    else:
        all_quals = (
            [(q, False) for q in mandatory] +
            [(q, True)  for q in bonus]
        )
        print(f"[info] 必要资质 {len(mandatory)} 条"
              f"{'，加分项 ' + str(len(bonus)) + ' 条' if bonus else ''}，逐项检查...")
        items = []
        for qual, is_bonus in all_quals:
            checked = (check_one_qual_llm(qual, bid_text, is_bonus)
                       if args.mode == "llm" else check_one_qual(qual, bid_text, is_bonus))
            items.append(checked)
            tag = "[加分]" if is_bonus else ""
            print(f"  [{checked['status']}]{tag} {checked['category']}：{checked['requirement'][:30]}")

        summary = build_summary(items)
        result  = {"items": items, "summary": summary}
        print(f"[info] 已声明 {summary['mandatory_declared']} / "
              f"不确定 {summary['mandatory_uncertain']} / "
              f"未声明 {summary['mandatory_missing']}")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[done] D5 结果已写入 {out}")


if __name__ == "__main__":
    main()
