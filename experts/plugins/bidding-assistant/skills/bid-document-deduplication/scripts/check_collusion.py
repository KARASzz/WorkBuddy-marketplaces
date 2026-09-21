#!/usr/bin/env python3
"""
围标串标深度分析脚本（P0 阶段）。

在 L1/L2/L3 文本相似度查重基础上，新增三类行为信号：

  L4 同错性分析  — 检测多份投标文件在相同位置出现相同错误（重字/异常标点/空格）
                   同一团队制作的串标文件往往共享低概率错误
  L5 报价规律检测 — 提取各投标方报价，检测等差/等比规律（CV 变异系数）
                   人为协商报价呈现异常规律性
  L6 文件元数据分析 — 读取 Word core_properties（作者/修改者/模板/创建时间）
                    同一作者或相同模板是强串标信号

输出 JSON 结构供 word-document-processing 生成围串标风险报告使用。
无第三方依赖（python-docx 除外）。
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

# 引入 simhash_engine 的 normalize（去噪）
sys.path.insert(0, str(Path(__file__).parent))
from simhash_engine import normalize

# ──────────────────────────────────────────────────────────────
# 文本提取（.docx）
# ──────────────────────────────────────────────────────────────

def extract_text_from_docx(path: str) -> str:
    """提取 .docx 全文（段落拼接，保留换行）。"""
    try:
        from docx import Document
        doc = Document(path)
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception as e:
        print(f"[warn] 文本提取失败 {path}: {e}", file=sys.stderr)
        return ""


def extract_text_from_txt(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        print(f"[warn] 文本读取失败 {path}: {e}", file=sys.stderr)
        return ""


def get_text(path: str) -> str:
    p = Path(path)
    if p.suffix.lower() == ".docx":
        return extract_text_from_docx(path)
    return extract_text_from_txt(path)


# ──────────────────────────────────────────────────────────────
# L4 同错性分析
# ──────────────────────────────────────────────────────────────

# 重字错误：连续相同的 1-3 个汉字
_DOUBLE_CHAR_RE = re.compile(r'([一-鿿]{1,3})\1')

# 全角/半角标点混用：同句中出现中文逗号和英文逗号
_MIXED_COMMA_RE = re.compile(r'(?:[，][^，。\n]{0,30}[,]|[,][^,。\n]{0,30}[，])')
_MIXED_PERIOD_RE = re.compile(r'(?:[。][^。\n]{0,30}[.]|[.][^.\n]{0,30}[。])')

# 中文字符间夹杂半角空格
_MID_SPACE_RE = re.compile(r'[一-鿿] [一-鿿]')

# 常见错别字对（source → error_tag）
_TYPO_PAIRS = [
    (re.compile(r'在座'), "在座（应为「在坐」）"),
    (re.compile(r'再接再砺'), "再接再砺（应为「再接再厉」）"),
    (re.compile(r'一愁莫展'), "一愁莫展（应为「一筹莫展」）"),
    (re.compile(r'震撼人心|振撼'), "振撼（应为「震撼」）"),
    (re.compile(r'防患未燃'), "防患未燃（应为「防患未然」）"),
]


def extract_errors(text: str) -> set:
    """从文本中提取所有异常错误标记（返回错误字符串集合）。"""
    errors = set()

    # 重字错误
    for m in _DOUBLE_CHAR_RE.finditer(text):
        errors.add(f"重字:{m.group(0)}")

    # 标点混用
    for m in _MIXED_COMMA_RE.finditer(text):
        errors.add(f"混用标点:逗号({m.group(0)[:10]})")
    for m in _MIXED_PERIOD_RE.finditer(text):
        errors.add(f"混用标点:句号({m.group(0)[:10]})")

    # 中文间空格
    for m in _MID_SPACE_RE.finditer(text):
        errors.add(f"异常空格:{m.group(0)}")

    # 错别字
    for pattern, tag in _TYPO_PAIRS:
        if pattern.search(text):
            errors.add(f"错别字:{tag}")

    return errors


def analyze_common_errors(bid_texts: dict) -> dict:
    """
    L4 同错性分析主函数。
    bid_texts: {filename: full_text}
    """
    if len(bid_texts) < 2:
        return {
            "triggered": False,
            "signals": [],
            "summary": "投标文件不足2份，无法进行同错性比对"
        }

    file_errors = {fn: extract_errors(text) for fn, text in bid_texts.items()}

    signals = []
    for (fn_a, errs_a), (fn_b, errs_b) in combinations(file_errors.items(), 2):
        if not errs_a or not errs_b:
            continue
        common = errs_a & errs_b
        if not common:
            continue
        union = errs_a | errs_b
        jaccard = len(common) / len(union) if union else 0
        # 阈值：共同错误 ≥ 2 个 或 Jaccard > 0.25
        if len(common) >= 2 or jaccard > 0.25:
            confidence = min(0.99, 0.5 + jaccard)
            signals.append({
                "files": [Path(fn_a).name, Path(fn_b).name],
                "common_errors": sorted(common)[:8],
                "common_count": len(common),
                "jaccard": round(jaccard, 4),
                "confidence": round(confidence, 2),
                "description": f"发现 {len(common)} 处相同错误，Jaccard={jaccard:.3f}"
            })

    triggered = bool(signals)
    if triggered:
        max_conf = max(s["confidence"] for s in signals)
        summary = (f"共检测到 {len(signals)} 对文件存在同错性，"
                   f"最高置信度 {max_conf:.0%}，疑似同一团队制作")
    else:
        summary = "未发现跨文档共同错误，同错性分析通过"

    return {
        "triggered": triggered,
        "signals": signals,
        "file_error_counts": {Path(fn).name: len(errs) for fn, errs in file_errors.items()},
        "summary": summary
    }


# ──────────────────────────────────────────────────────────────
# L5 报价规律检测
# ──────────────────────────────────────────────────────────────

# 复用 check_price.py 的报价提取逻辑（内联，避免跨目录依赖）
_NUM_RE = re.compile(
    r'[¥￥RMB人民币]*\s*([\d,，]+(?:\.\d+)?)\s*(亿|百万|万)?\s*(?:元|元整|元人民币)?'
)
_UPPER_MAP = {
    '零': 0, '壹': 1, '贰': 2, '叁': 3, '肆': 4, '伍': 5,
    '陆': 6, '柒': 7, '捌': 8, '玖': 9, '拾': 10,
    '佰': 100, '仟': 1000, '万': 10000, '亿': 100000000,
}
_UPPER_RE = re.compile(r'人民币\s*([零壹贰叁肆伍陆柒捌玖拾佰仟万亿元整角分]+)')


def _parse_amount(text: str):
    m = _NUM_RE.search(text)
    if not m:
        return None
    raw = m.group(1).replace(',', '').replace('，', '')
    try:
        val = float(raw)
    except ValueError:
        return None
    unit = m.group(2) or ''
    if unit == '亿':    val *= 1e8
    elif unit == '百万': val *= 1e6
    elif unit == '万':   val *= 1e4
    return val


def _extract_total_price(text: str):
    anchors = ['投标总价', '报价合计', '总报价', '投标报价', '总价（含税）', '含税总价', '投标价格']
    for anchor in anchors:
        idx = text.find(anchor)
        if idx < 0:
            continue
        snippet = text[idx: idx + 150]
        val = _parse_amount(snippet)
        if val and val > 0:
            return val, snippet.replace('\n', ' ')[:80]
    return None, ""


def _cv(values: list) -> float:
    """变异系数 = std / mean（仅对 ≥2 个差值有意义）。"""
    import statistics as _st
    if len(values) < 2:
        return 0.0
    mean = _st.mean(values)
    if mean == 0:
        return 0.0
    return _st.stdev(values) / abs(mean)


def detect_price_pattern(prices: dict) -> dict:
    """
    L5 报价规律检测主函数。
    prices: {filename: amount_float}
    """
    valid = {fn: v for fn, v in prices.items() if v is not None and v > 0}

    if len(valid) < 3:
        return {
            "triggered": False,
            "prices": {Path(k).name: v for k, v in prices.items()},
            "reason": f"有效报价仅 {len(valid)} 个，需 ≥3 个才能检测规律",
            "summary": f"有效报价数量不足（{len(valid)}/3），跳过规律检测"
        }

    sorted_items = sorted(valid.items(), key=lambda x: x[1])
    sorted_prices = {Path(k).name: v for k, v in sorted_items}
    vals = [v for _, v in sorted_items]
    diffs = [b - a for a, b in zip(vals, vals[1:])]

    # 等差检测
    cv_diff = _cv(diffs)
    if cv_diff < 0.10:
        triggered = True
        pattern_type = "等差"
        risk_desc = f"相邻差值 CV={cv_diff:.3f} < 0.10，报价等差规律显著"
    else:
        # 等比检测
        ratios = [b / a for a, b in zip(vals, vals[1:]) if a > 0]
        cv_ratio = _cv(ratios) if ratios else 1.0
        if cv_ratio < 0.05:
            triggered = True
            pattern_type = "等比"
            cv_diff = cv_ratio
            risk_desc = f"相邻比值 CV={cv_ratio:.3f} < 0.05，报价等比规律显著"
        else:
            triggered = False
            pattern_type = "无规律"
            risk_desc = f"差值 CV={cv_diff:.3f}，比值 CV={cv_ratio:.3f}，报价分布正常"

    return {
        "triggered": triggered,
        "prices": sorted_prices,
        "cv": round(cv_diff, 4),
        "pattern_type": pattern_type,
        "diff_values": [round(d, 2) for d in diffs],
        "summary": risk_desc
    }


# ──────────────────────────────────────────────────────────────
# L6 Word 文件元数据分析
# ──────────────────────────────────────────────────────────────

def _iso(dt) -> str:
    if dt is None:
        return ""
    # python-docx 返回 naive datetime（UTC），统一格式化
    try:
        return dt.strftime("%Y-%m-%dT%H:%M:%S")
    except Exception:
        return str(dt)


def extract_metadata(docx_path: str) -> dict:
    """提取 Word 文件的 core_properties 元数据。"""
    meta = {
        "file": Path(docx_path).name,
        "author": "",
        "last_modified_by": "",
        "created": "",
        "modified": "",
        "revision": "",
        "template": "",
    }
    try:
        from docx import Document
        doc = Document(docx_path)
        cp = doc.core_properties
        meta["author"]           = (cp.author or "").strip()
        meta["last_modified_by"] = (cp.last_modified_by or "").strip()
        meta["created"]          = _iso(cp.created)
        meta["modified"]         = _iso(cp.modified)
        meta["revision"]         = str(cp.revision or "")
        meta["template"]         = _extract_template_name(doc)
    except Exception as e:
        meta["_error"] = str(e)
    return meta


def _extract_template_name(doc) -> str:
    """尝试从 word/settings.xml 读取关联模板文件名。"""
    try:
        # doc.settings.element 是 lxml element
        settings = doc.settings.element
        W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
        att = settings.find(f"{{{W}}}attachedTemplate")
        if att is None:
            # 有些 Word 版本不写 namespace
            att = settings.find("attachedTemplate")
        if att is not None:
            rid = att.get(f"{{{R}}}id") or att.get("r:id") or ""
            # 尝试从 relationships 中解析实际模板路径
            try:
                rels = doc.settings.part.rels
                if rid in rels:
                    target = rels[rid].target_ref
                    return Path(target).name
            except Exception:
                return rid
    except Exception:
        pass
    return ""


def _find_shared_field(metas: list, field: str) -> list:
    """找出在多份文件中共享同一非空字段值的文件组。"""
    from collections import defaultdict
    groups = defaultdict(list)
    for m in metas:
        val = m.get(field, "").strip()
        if val:
            groups[val].append(m["file"])
    # 返回出现在 ≥2 份文件中的共享值及其文件列表
    return [(val, files) for val, files in groups.items() if len(files) >= 2]


def _find_close_timestamps(metas: list, field: str, gap_seconds: int = 300) -> list:
    """找出创建/修改时间相差 gap_seconds 秒以内的文件对。"""
    results = []
    valid = []
    for m in metas:
        ts_str = m.get(field, "")
        if not ts_str:
            continue
        try:
            ts = datetime.fromisoformat(ts_str)
            valid.append((m["file"], ts))
        except Exception:
            pass

    for (fa, ta), (fb, tb) in combinations(valid, 2):
        diff = abs((ta - tb).total_seconds())
        if diff <= gap_seconds:
            results.append((fa, fb, int(diff)))
    return results


def analyze_metadata(docx_files: list) -> dict:
    """
    L6 元数据分析主函数。
    docx_files: docx 路径列表（非 .docx 文件跳过）
    """
    metas = []
    for f in docx_files:
        if Path(f).suffix.lower() == ".docx":
            metas.append(extract_metadata(f))
        else:
            metas.append({"file": Path(f).name, "_skip": "非 .docx 文件"})

    anomalies = []

    # 规则1：相同作者
    for val, files in _find_shared_field(metas, "author"):
        anomalies.append({
            "type": "same_author",
            "severity": "高",
            "detail": f"{'、'.join(files)} 的作者均为「{val}」",
        })

    # 规则2：相同模板
    for val, files in _find_shared_field(metas, "template"):
        if val:  # 排除空模板
            anomalies.append({
                "type": "same_template",
                "severity": "高",
                "detail": f"{'、'.join(files)} 使用相同模板「{val}」",
            })

    # 规则3：相同最后修改者
    for val, files in _find_shared_field(metas, "last_modified_by"):
        anomalies.append({
            "type": "same_modifier",
            "severity": "中",
            "detail": f"{'、'.join(files)} 的最后修改者均为「{val}」",
        })

    # 规则4：创建时间相近（5分钟内）
    for fa, fb, diff_sec in _find_close_timestamps(metas, "created", gap_seconds=300):
        anomalies.append({
            "type": "close_created",
            "severity": "中",
            "detail": f"{fa} 与 {fb} 的创建时间相差仅 {diff_sec} 秒",
        })

    triggered = bool(anomalies)
    high_count = sum(1 for a in anomalies if a["severity"] == "高")
    if triggered:
        summary = (f"发现 {len(anomalies)} 个元数据异常"
                   f"（{high_count} 个高风险），疑似同源文件")
    else:
        summary = "元数据无异常，各文件作者/模板/时间正常"

    return {
        "triggered": triggered,
        "records": metas,
        "anomalies": anomalies,
        "summary": summary
    }


# ──────────────────────────────────────────────────────────────
# 风险等级综合判定
# ──────────────────────────────────────────────────────────────

def calc_risk(l4: dict, l5: dict, l6: dict) -> tuple:
    """
    综合三层信号计算风险得分和等级。
    权重：L4 同错性（最强）50分，L5 报价规律 30分，L6 元数据 20分（上限）
    """
    score = 0

    if l4.get("triggered"):
        max_conf = max((s.get("confidence", 0) for s in l4.get("signals", [])), default=0.5)
        score += int(50 * max_conf)

    if l5.get("triggered"):
        cv = l5.get("cv", 0)
        # CV 越小规律越明显，得分越高
        score += int(30 * (1 - min(cv, 0.10) / 0.10))

    if l6.get("triggered"):
        n = len(l6.get("anomalies", []))
        high = sum(1 for a in l6.get("anomalies", []) if a.get("severity") == "高")
        score += min(20, high * 10 + (n - high) * 5)

    if score >= 60:
        level = "高"
    elif score >= 25:
        level = "中"
    else:
        level = "低"

    return level, score


# ──────────────────────────────────────────────────────────────
# 主入口
# ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="围标串标深度分析：L4同错性 + L5报价规律 + L6元数据"
    )
    parser.add_argument(
        "--files", nargs="+", required=True,
        help="投标文件路径列表（.docx 或 .txt），至少1个"
    )
    parser.add_argument(
        "--output", default="/tmp/collusion_result.json",
        help="输出 JSON 路径（默认 /tmp/collusion_result.json）"
    )
    args = parser.parse_args()

    files = args.files
    print(f"[info] 分析 {len(files)} 份投标文件：{[Path(f).name for f in files]}")

    # 文本提取：用 "序号:文件名" 作 key，避免同路径合并
    bid_texts = {}
    for i, f in enumerate(files):
        display_name = f"{Path(f).stem}" if len(set(files)) == len(files) else f"{Path(f).stem}_{i+1}"
        bid_texts[display_name] = get_text(f)

    # L4 同错性分析
    print("[info] L4 同错性分析中...")
    l4 = analyze_common_errors(bid_texts)
    print(f"       → triggered={l4['triggered']}，{l4['summary']}")

    # L5 报价规律检测（使用带序号的 key 对应原始文件）
    print("[info] L5 报价规律检测中...")
    prices = {}
    for key, text in bid_texts.items():
        val, _ = _extract_total_price(text)
        prices[key] = val
    l5 = detect_price_pattern(prices)
    print(f"       → triggered={l5['triggered']}，{l5['summary']}")

    # L6 元数据分析
    print("[info] L6 文件元数据分析中...")
    docx_files = [f for f in files if Path(f).suffix.lower() == ".docx"]
    if docx_files:
        l6 = analyze_metadata(files)
    else:
        l6 = {
            "triggered": False,
            "records": [],
            "anomalies": [],
            "summary": "无 .docx 文件，跳过元数据分析"
        }
    print(f"       → triggered={l6['triggered']}，{l6['summary']}")

    # 综合风险判定
    risk_level, risk_score = calc_risk(l4, l5, l6)
    print(f"[info] 综合风险等级：{risk_level}（得分 {risk_score}/100）")

    # 输出 JSON
    result = {
        "bid_files":       [Path(f).name for f in files],
        "bid_file_paths":  files,
        "analyzed_at":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "risk_level":      risk_level,
        "risk_score":      risk_score,
        "l4_common_errors": l4,
        "l5_price_pattern": l5,
        "l6_metadata":      l6,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[done] 结果已写入 {out_path}")


if __name__ == "__main__":
    main()
