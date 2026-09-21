#!/usr/bin/env python3
"""
D2 实质性响应自动评分脚本。

支持两种评审模式（--mode 参数）：
  rule（默认）：纯规则，关键词命中率，无需 API，速度快
  llm          ：LLM 语义理解，准确率更高，需要 RICHEEAI_TOKEN

读取招标文件评分标准 JSON（--criteria）或招标分析 JSON（--analysis）
与投标文件全文，逐条评分，输出 d2_result.json。

格式供合规报告 Word 任务的 D2 载荷使用。

无第三方依赖（python-docx 仅用于读取 .docx，可选）。
"""
import argparse
import json
import re
import sys
from pathlib import Path

# ── 本技能内置辅助脚本路径（llm_client / proxy_utils）────────────
_LOCAL_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_LOCAL_SCRIPTS))

try:
    from llm_client import chat_completion, extract_json_from_llm
    _LLM_AVAILABLE = True
except ImportError:
    _LLM_AVAILABLE = False


# ── 停用词表 ──────────────────────────────────────────────────
_STOP_WORDS = {
    "需", "应", "须", "并", "且", "或", "的", "了", "是", "在",
    "包含", "包括", "提供", "具有", "具备", "满足", "符合", "要求",
    "进行", "实现", "完成", "建立", "制定", "配置", "设置",
    "以及", "同时", "其中", "均", "各", "按", "对", "等",
    "一", "二", "三", "四", "五", "上", "下",
    "需提供", "应提供", "须提供",
}

# 分词分隔符：按标点、动词前缀和空格切分
_SPLIT_RE = re.compile(r'[，。；、：\s（）【】《》""'']+')
# 二次切分：从较长的短语中提取实质词组
_VERB_PREFIX_RE = re.compile(r'^(?:需|应|须|要|应当|必须|需要)(?:提供|配备|具备|具有|包含|包括|出具|附上)?')


# ── 关键词提取 ────────────────────────────────────────────────

def _split_phrase(phrase: str) -> list:
    """
    将一个短语拆分为更短的实质词组。
    例："需提供完整实施方案" → ["完整实施方案", "实施方案"]
    """
    # 去掉动词前缀
    core = _VERB_PREFIX_RE.sub('', phrase).strip()
    results = []
    if len(core) >= 2:
        results.append(core)
    # 如果 core 仍然 ≥6 字，再取后半段（通常是名词核心）
    if len(core) >= 6:
        # 取后 N 个字符（2-4字的名词核心），步长2
        for n in range(4, 1, -1):
            sub = core[-n:]
            if len(sub) >= 2 and sub not in results:
                results.append(sub)
    return results


def extract_keywords(requirement: str) -> list:
    """
    从评分要求文本中提取关键词（去停用词，保留2字以上实词）。
    对较长短语进行二次拆分，提取名词核心词。
    """
    tokens = _SPLIT_RE.split(requirement)
    keywords = []
    seen = set()

    for t in tokens:
        t = t.strip()
        if len(t) < 2:
            continue
        if t in _STOP_WORDS:
            continue
        # 短词（≤4字）直接加入
        if len(t) <= 4:
            if t not in seen:
                keywords.append(t)
                seen.add(t)
        else:
            # 长短语：拆出核心词
            for sub in _split_phrase(t):
                if sub and sub not in seen and sub not in _STOP_WORDS:
                    keywords.append(sub)
                    seen.add(sub)

    return keywords


# ── 证据定位（最佳滑窗）────────────────────────────────────────

def best_window(text: str, keywords: list, window: int = 200) -> str:
    """
    滑窗检索：找到关键词命中最密集的 window 字文本段作为证据。
    步长 = window // 2（50% 重叠）。
    """
    if not text or not keywords:
        return ""
    step = max(1, window // 2)
    best_score = 0
    best_chunk = ""
    for i in range(0, max(1, len(text) - window + 1), step):
        chunk = text[i: i + window]
        score = sum(1 for kw in keywords if kw in chunk)
        if score > best_score:
            best_score = score
            best_chunk = chunk
    # 如果全文很短，直接返回全文
    if not best_chunk and text:
        best_chunk = text[:window]
    return best_chunk.strip().replace("\n", " ")


# ── 单条评分 ──────────────────────────────────────────────────

FULL_THRESHOLD    = 0.80   # 命中率 ≥ 80% → 完全响应
PARTIAL_THRESHOLD = 0.30   # 命中率 ≥ 30% → 部分响应


def score_item(item_id: str, dimension: str, requirement: str,
               bid_full_text: str,
               full_thresh: float = FULL_THRESHOLD,
               partial_thresh: float = PARTIAL_THRESHOLD) -> dict:
    """
    对单条评分要求打分。
    返回合规报告 D2 结构化载荷。
    """
    keywords = extract_keywords(requirement)
    item_name = f"{item_id} {requirement[:20]}{'…' if len(requirement) > 20 else ''}"

    if not keywords:
        # 无可验证关键词时不得默认通过，转人工复核。
        return {
            "item_name":        item_name,
            "dimension":        dimension,
            "requirement":      requirement,
            "response_level":   "待人工核查",
            "severity":         "提醒",
            "hit_rate":         0.0,
            "keywords":         [],
            "evidence_declared": False,
            "evidence":         "未提取到可验证关键词，不能自动判定通过",
            "deviations":       ["规则模式无法形成可验证证据链"],
            "suggestion":       "标记为待人工核查；补充结构化要求或切换 --mode llm 后复验"
        }

    hit = [kw for kw in keywords if kw in bid_full_text]
    miss = [kw for kw in keywords if kw not in bid_full_text]
    hit_rate = len(hit) / len(keywords)

    evidence = best_window(bid_full_text, hit, window=200)
    evidence_short = evidence[:100] if evidence else "（未找到相关内容）"

    if hit_rate >= full_thresh:
        response_level = "完全响应"
        severity       = "通过"
        suggestion     = ""
    elif hit_rate >= partial_thresh:
        response_level = "部分响应"
        severity       = "部分满足"
        miss_str = "、".join(miss[:4])
        suggestion = f"以下要素未见明确响应：{miss_str}"
    else:
        response_level = "未响应"
        severity       = "废标"
        kw_str = "、".join(keywords[:4])
        suggestion = f"投标文件未响应该评分项，建议补充：{kw_str}"

    # evidence_declared: 合规报告 D2 列使用的布尔字段
    #   True  = 找到相关证据文本
    #   False = 未在投标文件中定位到对应内容
    evidence_declared = bool(evidence and hit)

    # deviations: 未响应的关键词列表，供报告"偏离说明"列展示
    deviations = [f"未见「{kw}」" for kw in miss[:4]] if miss else []

    return {
        "item_name":         item_name,
        "dimension":         dimension,
        "requirement":       requirement,
        "response_level":    response_level,
        "severity":          severity,
        "hit_rate":          round(hit_rate, 4),
        "keywords":          keywords,
        "keywords_hit":      hit,
        "keywords_miss":     miss,
        "evidence_declared": evidence_declared,
        "evidence":          evidence_short,
        "deviations":        deviations,
        "suggestion":        suggestion
    }


# ── LLM 语义评分（--mode llm）────────────────────────────────

_LLM_SYSTEM = (
    "你是政府采购评标委员会专家，负责审查投标文件是否实质性响应招标要求。"
    "请严格基于所提供的投标文件节选内容作出判断，不得推断或假设文件中未出现的内容。"
)

_LLM_USER_TPL = """\
【评分项信息】
序号：{item_id}
维度：{dimension}（技术 / 商务）
评分要求：{requirement}

【投标文件节选（最相关段落，约500字）】
{bid_context}

请判断投标文件对上述评分项的响应情况，以 JSON 格式输出，不要添加任何额外说明：
{{
  "response_level": "完全响应|部分响应|未响应",
  "hit_rate": 0到1之间的浮点数（响应程度量化估算）,
  "evidence": "投标文件中对应的原文引用（不超过80字，若无则为空字符串）",
  "evidence_declared": true或false（是否有证明材料声明）,
  "deviations": ["不足或偏离点1", "不足或偏离点2"],
  "suggestion": "整改建议（若完全响应则为空字符串）"
}}"""


def score_item_llm(item_id: str, dimension: str, requirement: str,
                   bid_full_text: str) -> dict:
    """LLM 语义模式评分。失败时自动降级到规则模式。"""
    if not _LLM_AVAILABLE:
        print("[llm] llm_client 未加载，降级到规则模式", file=sys.stderr)
        return score_item(item_id, dimension, requirement, bid_full_text)

    item_name = f"{item_id} {requirement[:20]}{'…' if len(requirement) > 20 else ''}"

    # 用规则方法定位最相关的上下文窗口（供 LLM 使用，不超过 500 字）
    kws = extract_keywords(requirement)
    bid_context = best_window(bid_full_text, kws, window=500) or bid_full_text[:500]

    messages = [
        {"role": "system", "content": _LLM_SYSTEM},
        {"role": "user",   "content": _LLM_USER_TPL.format(
            item_id=item_id or "—",
            dimension=dimension,
            requirement=requirement,
            bid_context=bid_context,
        )},
    ]

    resp = chat_completion(messages, temperature=0.1, max_tokens=600)
    if not resp.get("success"):
        print(f"[llm] API 失败（{resp.get('error')}），降级规则模式", file=sys.stderr)
        return score_item(item_id, dimension, requirement, bid_full_text)

    data = extract_json_from_llm(resp["content"])
    if not data:
        print("[llm] 响应解析失败，降级规则模式", file=sys.stderr)
        return score_item(item_id, dimension, requirement, bid_full_text)

    rl = data.get("response_level", "未响应")
    severity_map = {"完全响应": "通过", "部分响应": "部分满足", "未响应": "废标"}
    severity = severity_map.get(rl, "废标")

    return {
        "item_name":         item_name,
        "dimension":         dimension,
        "requirement":       requirement,
        "response_level":    rl,
        "severity":          severity,
        "hit_rate":          float(data.get("hit_rate", 0.0)),
        "keywords":          kws,
        "evidence_declared": bool(data.get("evidence_declared", False)),
        "evidence":          str(data.get("evidence", ""))[:100],
        "deviations":        list(data.get("deviations", [])),
        "suggestion":        str(data.get("suggestion", "")),
        "mode":              "llm",
    }


# ── 文本提取 ──────────────────────────────────────────────────

def get_bid_text(path: str) -> str:
    p = Path(path)
    if not p.exists():
        print(f"[error] 找不到投标文件：{path}", file=sys.stderr)
        sys.exit(1)

    if p.suffix.lower() == ".docx":
        try:
            from docx import Document
            doc = Document(path)
            return "\n".join(para.text for para in doc.paragraphs)
        except Exception as e:
            print(f"[warn] .docx 读取失败，尝试纯文本：{e}", file=sys.stderr)

    return p.read_text(encoding="utf-8", errors="replace")


def load_criteria(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        print(f"[error] 找不到评分标准文件：{path}", file=sys.stderr)
        sys.exit(1)
    data = json.loads(p.read_text(encoding="utf-8"))
    # 支持两种格式：{"scoring_items": [...]} 或直接 [...]
    if isinstance(data, list):
        return {"scoring_items": data}
    return data


def load_analysis(path: str) -> list:
    """
    从 tender_analysis.json 的 scoring 字段提取评分项列表。
    每项统一为 {"id": ..., "dimension": ..., "requirement": ...} 格式。
    """
    p = Path(path)
    if not p.exists():
        print(f"[error] 找不到招标分析文件：{path}", file=sys.stderr)
        sys.exit(1)
    data = json.loads(p.read_text(encoding="utf-8"))
    scoring = data.get("scoring", {})
    items = []
    for dim_key, dim_label in [("technical_score", "技术"), ("commercial_score", "商务")]:
        dim = scoring.get(dim_key, {})
        for it in dim.get("items", []):
            requirement = (it.get("criteria") or it.get("requirement") or
                           it.get("name") or "")
            if requirement:
                items.append({
                    "id":          it.get("id", ""),
                    "dimension":   dim_label,
                    "requirement": requirement,
                })
    return items


# ── 汇总统计 ──────────────────────────────────────────────────

def build_summary(items: list) -> dict:
    total   = len(items)
    full    = sum(1 for it in items if it["response_level"] == "完全响应")
    partial = sum(1 for it in items if it["response_level"] == "部分响应")
    none_   = sum(1 for it in items if it["response_level"] == "未响应")
    manual  = sum(1 for it in items if it["response_level"] == "待人工核查")
    废标    = sum(1 for it in items if it["severity"] == "废标")
    pass_rate = f"{full / total:.0%}" if total else "0%"

    return {
        "total":       total,
        "full":        full,
        "partial":     partial,
        "none":        none_,
        "manual_review": manual,
        "废标项数":     废标,
        "pass_rate":   pass_rate,
        "avg_hit_rate": round(
            sum(it.get("hit_rate", 0) for it in items) / total, 4
        ) if total else 0.0
    }


# ── 主入口 ────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="D2 实质性响应评分（rule=规则模式 / llm=语义模式）"
    )
    parser.add_argument("--bid",      required=True, help="投标文件路径（.docx 或 .txt）")
    parser.add_argument("--analysis", default="",   help="招标分析 JSON 路径（tender_analysis.json，优先）")
    parser.add_argument("--criteria", default="",   help="评分标准 JSON 路径（备用）")
    parser.add_argument("--output",   default="/tmp/d2_result.json",
                        help="输出 JSON 路径（默认 /tmp/d2_result.json）")
    parser.add_argument("--mode",     choices=["rule", "llm"], default="rule",
                        help="评审模式：rule=关键词规则（默认）/ llm=语义评审（需 RICHEEAI_TOKEN）")
    parser.add_argument("--hit-threshold-full",    type=float, default=FULL_THRESHOLD,
                        help=f"完全响应命中率阈值（默认 {FULL_THRESHOLD}，rule 模式有效）")
    parser.add_argument("--hit-threshold-partial", type=float, default=PARTIAL_THRESHOLD,
                        help=f"部分响应命中率阈值（默认 {PARTIAL_THRESHOLD}，rule 模式有效）")
    args = parser.parse_args()

    if args.mode == "llm" and not _LLM_AVAILABLE:
        print("[warn] llm_client 不可用，自动切换到 rule 模式", file=sys.stderr)
        args.mode = "rule"

    full_thresh    = args.hit_threshold_full
    partial_thresh = args.hit_threshold_partial

    print(f"[info] 投标文件：{args.bid}")
    print(f"[info] 评审模式：{args.mode}")

    bid_text = get_bid_text(args.bid)

    # 加载评分项：--analysis 优先，其次 --criteria
    if args.analysis:
        print(f"[info] 招标分析：{args.analysis}")
        scoring_items = load_analysis(args.analysis)
    elif args.criteria:
        print(f"[info] 评分标准：{args.criteria}")
        criteria = load_criteria(args.criteria)
        scoring_items = criteria.get("scoring_items", [])
    else:
        print("[error] 请提供 --analysis 或 --criteria 参数", file=sys.stderr)
        sys.exit(1)

    if not scoring_items:
        print("[warn] 评分标准为空，输出空 D2 结果")
        result = {"items": [], "summary": build_summary([])}
    else:
        print(f"[info] 共 {len(scoring_items)} 条评分要求，开始逐项评分...")
        items = []
        for raw in scoring_items:
            item_id     = raw.get("id", "")
            dimension   = raw.get("dimension", "")
            requirement = raw.get("requirement", "")
            if not requirement:
                continue
            if args.mode == "llm":
                scored = score_item_llm(item_id, dimension, requirement, bid_text)
            else:
                scored = score_item(item_id, dimension, requirement, bid_text,
                                    full_thresh=full_thresh, partial_thresh=partial_thresh)
            items.append(scored)
            print(f"  [{scored['response_level']}] {scored['item_name']} "
                  f"(命中率 {scored['hit_rate']:.0%})")

        summary = build_summary(items)
        result = {"items": items, "summary": summary, "mode": args.mode}
        print(f"[info] 完全响应 {summary['full']} / "
              f"部分响应 {summary['partial']} / "
              f"未响应 {summary['none']} / "
              f"待人工核查 {summary['manual_review']} / "
              f"废标项 {summary['废标项数']}")

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"[done] D2 结果已写入 {out_path}")


if __name__ == "__main__":
    main()
