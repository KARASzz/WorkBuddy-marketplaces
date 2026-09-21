#!/usr/bin/env python3
"""
D3 废标风险规避检查脚本。

支持 --mode rule（默认，关键词命中率）和 --mode llm（语义评审）。

读取招标分析 JSON 中的 risks[] 列表，对每条废标风险逐一检测
投标文件是否已按 avoidance 建议规避，输出 d3_result.json。

格式供合规报告 Word 任务的 D3 载荷使用：
  items[]:
    risk            风险描述
    source          来源条款
    original_level  原风险等级（高/中/低）
    avoidance_status 已规避 / 疑似规避 / 未规避
    evidence        在投标文件中找到的规避证据片段
    suggestion      整改建议

规避判定：对"avoidance"建议文本提取关键词，在投标全文检索。
命中率 ≥ 0.60 → 已规避
命中率 0.25~0.60 → 疑似规避
命中率 < 0.25 → 未规避

无第三方依赖（python-docx 可选，用于读取 .docx）。
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
    "需", "应", "须", "的", "了", "是", "在", "进行", "实现",
    "完成", "建立", "制定", "并", "且", "或", "提供", "附上",
    "交叉", "核查", "确保", "重新", "更换", "补齐", "随",
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


AVOID_FULL    = 0.60
AVOID_PARTIAL = 0.25


def compact(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def money_tokens(text: str) -> list:
    return re.findall(r"\d+(?:\.\d+)?\s*(?:万元|万|元)", text or "")


def day_tokens(text: str) -> list:
    return re.findall(r"\d+\s*(?:日历天|天|日)", text or "")


def special_risk_status(risk_desc: str, avoidance: str, bid_text: str):
    """Handle common tender-risk semantics that plain keyword ratios miss."""
    hay = compact(bid_text)
    risk = compact(risk_desc + avoidance)

    if "最高限价" in risk or "超过" in risk:
        amounts = money_tokens(risk_desc + avoidance)
        has_amount = any(compact(a) in hay for a in amounts) if amounts else True
        has_safe_word = any(w in hay for w in ["不超过", "低于", "小于", "未超过", "控制在", "≤", "<", "以内"])
        has_price_word = any(w in hay for w in ["投标总价", "报价", "含税总价", "最高限价"])
        if has_amount and has_price_word and has_safe_word:
            return "已规避", "检测到报价未超过最高限价的明确表述"

    if "有效期" in risk:
        days = day_tokens(risk_desc + avoidance)
        has_day = any(compact(d) in hay for d in days) if days else True
        if has_day and "有效" in hay:
            return "已规避", "检测到投标有效期承诺"

    if "大写金额" in risk and ("数字金额" in risk or "金额一致" in risk):
        has_upper = "大写金额" in hay or re.search(r"人民币[零壹贰叁肆伍陆柒捌玖拾佰仟万亿]+元", hay)
        has_number = re.search(r"[¥￥]?\s*\d[\d,]*(?:\.\d+)?\s*(?:万元|万|元)", bid_text or "")
        has_consistency = any(w in hay for w in ["一致", "相符", "完全一致"])
        if has_upper and has_number and has_consistency:
            return "已规避", "检测到大小写金额及一致性说明"

    if "系统集成商资质" in risk:
        if "系统集成商资质" in hay and any(w in hay for w in ["证书", "扫描件", "复印件", "随附", "附"]):
            return "已规避", "检测到系统集成商资质证书材料"

    if "项目经理" in risk and ("PMP" in bid_text or "软考" in bid_text):
        if any(w in hay for w in ["项目经理", "证书", "社保"]):
            return "已规避", "检测到项目经理证书/社保相关材料"

    return None


def check_one_risk(risk_item: dict, bid_text: str) -> dict:
    """对单条废标风险检查规避状态。"""
    risk_desc   = risk_item.get("risk", "")
    source      = risk_item.get("source", "")
    level       = risk_item.get("level", "中")
    avoidance   = risk_item.get("avoidance", "")

    # 同时用风险描述 + 规避方法提取关键词
    kws_risk = extract_keywords(risk_desc)
    kws_avoid = extract_keywords(avoidance)
    # 合并，规避方法关键词权重更高（放在前面）
    all_kws = list(dict.fromkeys(kws_avoid + kws_risk))  # 去重保序

    if not all_kws:
        return _make_result(risk_desc, source, level, "疑似规避",
                            "（无法提取检查关键词）", [], "人工核查")

    special = special_risk_status(risk_desc, avoidance, bid_text)
    if special:
        status, evidence = special
        return _make_result(risk_desc, source, level, status, evidence, [], "")

    hit  = [kw for kw in all_kws if kw in bid_text]
    miss = [kw for kw in all_kws if kw not in bid_text]
    rate = len(hit) / len(all_kws)
    evidence = best_window(bid_text, hit, window=200)

    if rate >= AVOID_FULL:
        status     = "已规避"
        suggestion = ""
    elif rate >= AVOID_PARTIAL:
        status     = "疑似规避"
        suggestion = f"请确认以下要素是否已明确体现：{'、'.join(miss[:3])}"
    else:
        status     = "未规避"
        suggestion = f"投标文件未见规避说明，建议补充：{avoidance[:60]}"

    return _make_result(
        risk_desc, source, level, status,
        evidence[:100] if evidence else "（未找到对应内容）",
        [f"未见「{kw}」" for kw in miss[:4]],
        suggestion
    )


def _make_result(risk, source, level, status, evidence, deviations, suggestion):
    return {
        "risk":             risk,
        "source":           source,
        "original_level":   level,
        "avoidance_status": status,
        "evidence":         evidence,
        "deviations":       deviations,
        "suggestion":       suggestion,
        # 合规报告汇总载荷使用 severity 字段
        "severity":         "废标" if status == "未规避" else (
                             "部分满足" if status == "疑似规避" else "通过"),
    }


# ── LLM 语义模式（--mode llm）────────────────────────────────

_LLM_D3_SYSTEM = (
    "你是政府采购评标委员会专家，负责审查投标文件是否有效规避了废标风险。"
    "请严格基于所提供的投标文件节选内容作出判断，不得推断未出现的内容。"
)

_LLM_D3_USER_TPL = """\
【废标风险项】
风险描述：{risk_desc}
来源条款：{source}
原风险等级：{level}
规避建议：{avoidance}

【投标文件节选（最相关段落，约500字）】
{bid_context}

请判断投标文件是否已规避上述废标风险，以 JSON 格式输出，不要添加任何额外说明：
{{
  "avoidance_status": "已规避|疑似规避|未规避",
  "evidence": "投标文件中规避说明的原文引用（不超过80字，若无则为空字符串）",
  "deviations": ["未见要素1", "未见要素2"],
  "suggestion": "整改建议（若已规避则为空字符串）",
  "reason": "判断依据（1-2句话）"
}}"""


def check_one_risk_llm(risk_item: dict, bid_text: str) -> dict:
    """LLM 语义模式检查单条废标风险。失败时降级到规则模式。"""
    if not _LLM_AVAILABLE:
        return check_one_risk(risk_item, bid_text)

    risk_desc = risk_item.get("risk", "")
    source    = risk_item.get("source", "")
    level     = risk_item.get("level", "中")
    avoidance = risk_item.get("avoidance", "")

    kws = list(dict.fromkeys(
        extract_keywords(avoidance) + extract_keywords(risk_desc)
    ))
    bid_context = best_window(bid_text, kws, window=500) or bid_text[:500]

    messages = [
        {"role": "system", "content": _LLM_D3_SYSTEM},
        {"role": "user",   "content": _LLM_D3_USER_TPL.format(
            risk_desc=risk_desc, source=source,
            level=level, avoidance=avoidance,
            bid_context=bid_context,
        )},
    ]

    resp = chat_completion(messages, temperature=0.1, max_tokens=500)
    if not resp.get("success"):
        print(f"[llm] D3 API 失败，降级规则模式: {resp.get('error')}", file=sys.stderr)
        return check_one_risk(risk_item, bid_text)

    data = extract_json_from_llm(resp["content"])
    if not data:
        return check_one_risk(risk_item, bid_text)

    status = data.get("avoidance_status", "未规避")
    severity_map = {"已规避": "通过", "疑似规避": "部分满足", "未规避": "废标"}
    return {
        "risk":             risk_desc,
        "source":           source,
        "original_level":   level,
        "avoidance_status": status,
        "evidence":         str(data.get("evidence", ""))[:100],
        "deviations":       list(data.get("deviations", [])),
        "suggestion":       str(data.get("suggestion", "")),
        "severity":         severity_map.get(status, "废标"),
        "mode":             "llm",
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
            print(f"[warn] .docx 读取失败，尝试纯文本：{e}", file=sys.stderr)
    return p.read_text(encoding="utf-8", errors="replace")


def load_analysis(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        print(f"[error] 找不到招标分析文件：{path}", file=sys.stderr)
        sys.exit(1)
    return json.loads(p.read_text(encoding="utf-8"))


def build_summary(items: list) -> dict:
    total   = len(items)
    avoided = sum(1 for it in items if it["avoidance_status"] == "已规避")
    partial = sum(1 for it in items if it["avoidance_status"] == "疑似规避")
    not_avoided = sum(1 for it in items if it["avoidance_status"] == "未规避")
    return {
        "total":       total,
        "已规避":       avoided,
        "疑似规避":     partial,
        "未规避":       not_avoided,
        "avoid_rate":  f"{avoided / total:.0%}" if total else "0%",
    }


def main():
    parser = argparse.ArgumentParser(
        description="D3 废标风险规避检查（rule=规则模式 / llm=语义模式）"
    )
    parser.add_argument("--bid",      required=True, help="投标文件路径（.docx 或 .txt）")
    parser.add_argument("--analysis", required=True, help="招标分析 JSON 路径（含 risks 字段）")
    parser.add_argument("--output",   default="/tmp/d3_result.json",
                        help="输出 JSON 路径（默认 /tmp/d3_result.json）")
    parser.add_argument("--mode",     choices=["rule", "llm"], default="rule",
                        help="评审模式：rule=关键词规则（默认）/ llm=语义评审（需 RICHEEAI_TOKEN）")
    args = parser.parse_args()

    if args.mode == "llm" and not _LLM_AVAILABLE:
        print("[warn] llm_client 不可用，自动切换到 rule 模式", file=sys.stderr)
        args.mode = "rule"

    print(f"[info] 投标文件：{args.bid}")
    print(f"[info] 招标分析：{args.analysis}")
    print(f"[info] 评审模式：{args.mode}")

    bid_text = get_bid_text(args.bid)
    analysis = load_analysis(args.analysis)
    risks    = analysis.get("risks", [])

    if not risks:
        print("[warn] 招标分析中无废标风险条目（risks 为空）")
        result = {"items": [], "summary": build_summary([])}
    else:
        print(f"[info] 共 {len(risks)} 条废标风险，逐项检查...")
        items = []
        for r in risks:
            checked = (check_one_risk_llm(r, bid_text)
                       if args.mode == "llm" else check_one_risk(r, bid_text))
            items.append(checked)
            print(f"  [{checked['avoidance_status']}] {checked['risk'][:35]}")

        summary = build_summary(items)
        result  = {"items": items, "summary": summary}
        print(f"[info] 已规避 {summary['已规避']} / "
              f"疑似规避 {summary['疑似规避']} / "
              f"未规避 {summary['未规避']}")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[done] D3 结果已写入 {out}")


if __name__ == "__main__":
    main()
