#!/usr/bin/env python3
"""
三层查重主控脚本。

L1 — 跨文档查重：SimHash 全文指纹 + 高相似文档的段落精细比对
L2 — 内部段落查重：文档自身段落两两 MinHash/Jaccard 比对
L3 — 模板套话扫描：匹配 boilerplate_phrases.json 中的常见套话

输出 /tmp/dedup_result.json，供 word-document-processing 生成查重报告使用。
无第三方依赖。
"""
import argparse
import json
import os
import sys
from pathlib import Path

# 将脚本目录加入路径，引入 simhash_engine
sys.path.insert(0, str(Path(__file__).parent))
from simhash_engine import (
    simhash, hamming_distance, hamming_level,
    minhash_signature, minhash_similarity,
    jaccard_similarity, similarity_level, normalize
)


# ── 配置默认值 ────────────────────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "simhash_high_threshold":    10,   # Hamming 距离 ≤ 此值 → 高相似，触发段落精细比对
    "jaccard_dup_threshold":     0.60, # Jaccard ≥ 此值 → 重复
    "jaccard_similar_threshold": 0.30, # Jaccard ≥ 此值 → 相似
    "minhash_threshold":         0.40, # MinHash 估计 ≥ 此值 → 候选对，触发精细比对
    "min_para_chars":            50,   # 段落最小字符数（过短跳过）
    "max_para_pairs":            5000, # 内部段落两两比对上限（防止超时）
    "boilerplate_density_threshold": 0.40,  # 连续 200 字内套话占比 ≥ 此值 → 高密度区域
    "boilerplate_window":        200,  # 套话密度检测滑动窗口大小（字符）
    "ignore_section_keywords":   ["目录", "附件", "封面", "页眉", "资质证书"],
    # OPT-S4-01：对全语料库做段落级扫描，捕获「全文差异大但局部段落雷同」的情形
    "para_scan_all":             True, # True → 对所有语料库文件做段落扫描（不受 simhash_high_threshold 限制）
    "para_scan_max_corpus":      50    # 全量段落扫描的语料库文件上限（防止大语料库超时）
}


def load_config(path: str) -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if path and Path(path).exists():
        user_cfg = json.loads(Path(path).read_text(encoding="utf-8"))
        cfg.update(user_cfg)
    return cfg


def load_json(path: str) -> dict:
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def load_text(path: str) -> str:
    p = Path(path)
    return p.read_text(encoding="utf-8") if p.exists() else ""


# ── L1：跨文档查重 ────────────────────────────────────────────────────────────

def l1_cross_doc(main_text: str, main_struct: dict, corpus_dir: str, cfg: dict) -> dict:
    """
    跨文档查重。
    1. 计算主文档全文 SimHash
    2. 与语料库每份文档比对 Hamming 距离
    3. 对高相似文档（Hamming ≤ threshold）做段落精细比对
    4. OPT-S4-01：当 para_scan_all=True 时，对全部语料库文件（上限 para_scan_max_corpus）
       同步做段落级 MinHash 扫描，捕获「全文差异大但局部段落雷同」的情形
    """
    corpus_path = Path(corpus_dir)
    if not corpus_path.exists():
        return {"enabled": False, "reason": "未提供对比库，跳过跨文档查重",
                "matches": [], "stats": {"total_corpus": 0, "high_sim_count": 0}}

    # 主文档指纹
    main_fp    = simhash(main_text)
    main_paras = main_struct.get("paragraphs") or []

    # 预计算主文档段落 MinHash 签名（OPT-S4-01 复用）
    main_sigs_cache = None  # 延迟计算，仅在需要时初始化

    # 读取语料库索引
    index_path = corpus_path / "_index.json"
    if index_path.exists():
        corpus_index = json.loads(index_path.read_text(encoding="utf-8"))
    else:
        # 无索引时自动扫描
        corpus_index = [
            {"file": f.name, "stem": f.stem, "chars": 0, "paras": 0}
            for f in corpus_path.glob("*.txt")
            if not f.name.startswith("_")
        ]

    para_scan_all     = cfg.get("para_scan_all", True)
    para_scan_max     = cfg.get("para_scan_max_corpus", 50)
    matches           = []
    high_sim          = 0
    para_scanned      = 0    # 已做段落扫描的文档数（用于 para_scan_all 限额）

    for entry in corpus_index:
        stem     = entry.get("stem", "")
        txt_path = corpus_path / f"{stem}.txt"
        if not txt_path.exists():
            continue

        corpus_text = txt_path.read_text(encoding="utf-8")
        corpus_fp   = simhash(corpus_text)
        dist        = hamming_distance(main_fp, corpus_fp)
        level       = hamming_level(dist)
        sim_score   = round(1.0 - dist / 64, 3)

        match_entry = {
            "source_file":        entry.get("file", stem),
            "hamming_dist":       dist,
            "sim_score":          sim_score,
            "level":              level,
            "para_matches":       [],
            "para_scan_applied":  False
        }

        # ① 高相似文档（全文 SimHash 命中）→ 必做段落精细比对
        do_para_scan = dist <= cfg["simhash_high_threshold"]

        # ② OPT-S4-01：para_scan_all 模式下，对全语料库也做段落扫描（有上限）
        if not do_para_scan and para_scan_all and para_scanned < para_scan_max:
            do_para_scan = True

        if do_para_scan:
            if dist <= cfg["simhash_high_threshold"]:
                high_sim += 1

            struct_path  = corpus_path / f"{stem}_structure.json"
            corpus_paras = []
            if struct_path.exists():
                corpus_paras = json.loads(
                    struct_path.read_text(encoding="utf-8")
                ).get("paragraphs") or []

            if corpus_paras and main_paras:
                # 延迟初始化主文档段落签名缓存
                if main_sigs_cache is None:
                    main_sigs_cache = [(p, minhash_signature(p["text"])) for p in main_paras]

                para_matches = _para_cross_match_with_cache(
                    main_sigs_cache, corpus_paras,
                    cfg["minhash_threshold"], cfg["jaccard_dup_threshold"]
                )
                match_entry["para_matches"]      = para_matches
                match_entry["para_scan_applied"] = True
                para_scanned += 1

        matches.append(match_entry)

    # 按相似度降序排列
    matches.sort(key=lambda x: x["sim_score"], reverse=True)

    # 统计最高雷同字数
    total_dup_chars = sum(
        len(pm.get("main_text", ""))
        for m in matches
        for pm in m.get("para_matches", [])
        if pm.get("jaccard", 0) >= cfg["jaccard_dup_threshold"]
    )

    return {
        "enabled":          True,
        "total_corpus":     len(corpus_index),
        "high_sim_count":   high_sim,
        "para_scanned":     para_scanned,
        "dup_chars":        total_dup_chars,
        "matches":          matches[:20],     # 最多返回前 20 个
        "top_match":        matches[0] if matches else None,
        "stats": {
            "total_corpus":   len(corpus_index),
            "high_sim_count": high_sim,
            "para_scanned":   para_scanned,
            "dup_chars":      total_dup_chars
        }
    }


def _para_cross_match_with_cache(main_sigs: list, corpus_paras: list,
                                  mh_thresh: float, jac_thresh: float) -> list:
    """
    主文档段落（已预计算 MinHash 签名）与语料库段落精细比对。
    OPT-S4-01：接受缓存签名，避免对同一主文档重复计算 MinHash。
    """
    if not main_sigs or not corpus_paras:
        return []

    corpus_sigs = [(p, minhash_signature(p["text"])) for p in corpus_paras]

    results = []
    for mp, msig in main_sigs:
        for cp, csig in corpus_sigs:
            mh = minhash_similarity(msig, csig)
            if mh < mh_thresh:
                continue
            # 精细 Jaccard
            jac = jaccard_similarity(mp["text"], cp["text"])
            if jac >= jac_thresh * 0.8:   # 稍宽松，让报告显示更多候选
                results.append({
                    "main_para_id":   mp["id"],
                    "main_text":      mp["text"][:200],
                    "corpus_para_id": cp["id"],
                    "corpus_text":    cp["text"][:200],
                    "minhash":        round(mh, 3),
                    "jaccard":        round(jac, 3),
                    "level":          similarity_level(jac)
                })

    results.sort(key=lambda x: x["jaccard"], reverse=True)
    return results[:30]   # 最多 30 对


def _para_cross_match(main_paras: list, corpus_paras: list,
                       mh_thresh: float, jac_thresh: float) -> list:
    """主文档段落与语料库段落精细比对（兼容旧调用方式）。"""
    if not main_paras or not corpus_paras:
        return []
    main_sigs = [(p, minhash_signature(p["text"])) for p in main_paras]
    return _para_cross_match_with_cache(main_sigs, corpus_paras, mh_thresh, jac_thresh)


# ── L2：内部段落查重 ──────────────────────────────────────────────────────────

def l2_internal(main_struct: dict, cfg: dict) -> dict:
    """
    文档内部段落两两相似度比对。
    使用 MinHash 快速筛选候选对，再用 Jaccard 精确计算。
    """
    paragraphs = main_struct.get("paragraphs") or []
    paragraphs = [p for p in paragraphs if p.get("char_count", 0) >= cfg["min_para_chars"]]

    n = len(paragraphs)
    if n < 2:
        return {"enabled": True, "dup_pairs": [], "dup_chars": 0,
                "dup_ratio": 0.0, "stats": {"para_count": n, "pair_count": 0}}

    # 预计算 MinHash 签名
    sigs = [(p, minhash_signature(p["text"])) for p in paragraphs]

    pairs      = []
    pair_count = 0
    max_pairs  = cfg["max_para_pairs"]
    mh_thresh  = cfg["minhash_threshold"]
    jac_thresh = cfg["jaccard_similar_threshold"]

    for i in range(n):
        for j in range(i + 1, n):
            if pair_count >= max_pairs:
                break
            pair_count += 1
            pi, si = sigs[i]
            pj, sj = sigs[j]
            mh = minhash_similarity(si, sj)
            if mh < mh_thresh:
                continue
            jac = jaccard_similarity(pi["text"], pj["text"])
            if jac >= jac_thresh:
                pairs.append({
                    "para_a_id":    pi["id"],
                    "para_a_text":  pi["text"][:300],
                    "para_b_id":    pj["id"],
                    "para_b_text":  pj["text"][:300],
                    "minhash":      round(mh, 3),
                    "jaccard":      round(jac, 3),
                    "level":        similarity_level(jac)
                })
        if pair_count >= max_pairs:
            break

    pairs.sort(key=lambda x: x["jaccard"], reverse=True)

    # 统计重复字数（去重段落，避免重复计数）
    dup_para_ids = set()
    dup_thresh   = cfg["jaccard_dup_threshold"]
    for pair in pairs:
        if pair["jaccard"] >= dup_thresh:
            dup_para_ids.add(pair["para_b_id"])   # 把重复段落标为重复
    dup_chars   = sum(paragraphs[i]["char_count"] for i in dup_para_ids
                      if i < len(paragraphs))
    total_chars = sum(p["char_count"] for p in paragraphs)
    dup_ratio   = round(dup_chars / total_chars, 4) if total_chars else 0.0

    return {
        "enabled":    True,
        "dup_pairs":  pairs[:50],    # 最多 50 对
        "dup_chars":  dup_chars,
        "dup_ratio":  dup_ratio,
        "stats": {
            "para_count":   n,
            "pair_count":   pair_count,
            "dup_pair_count": len([p for p in pairs if p["jaccard"] >= dup_thresh]),
            "dup_chars":    dup_chars,
            "dup_ratio":    dup_ratio
        }
    }


# ── L3：模板套话扫描 ──────────────────────────────────────────────────────────

def l3_boilerplate(main_text: str, boilerplate_path: str, cfg: dict) -> dict:
    """
    扫描文档中的常见模板套话，计算套话覆盖率。
    """
    phrases = []
    if boilerplate_path and Path(boilerplate_path).exists():
        data    = json.loads(Path(boilerplate_path).read_text(encoding="utf-8"))
        phrases = data.get("phrases") or []

    if not phrases:
        return {"enabled": False, "reason": "未加载套话库",
                "hits": [], "boilerplate_chars": 0, "boilerplate_ratio": 0.0,
                "hot_zones": [], "stats": {}}

    total_chars    = len(normalize(main_text))
    hit_chars      = 0
    hits           = []
    hit_positions  = []   # [(start, end)] 用于计算热区

    for phrase_entry in phrases:
        phrase = phrase_entry if isinstance(phrase_entry, str) else phrase_entry.get("text", "")
        if not phrase or len(phrase) < 8:
            continue
        idx = 0
        while True:
            pos = main_text.find(phrase, idx)
            if pos < 0:
                break
            hits.append({
                "phrase":   phrase,
                "position": pos,
                "category": phrase_entry.get("category", "") if isinstance(phrase_entry, dict) else "",
                "snippet":  main_text[max(0, pos-20): pos+len(phrase)+20].replace("\n", " ")
            })
            hit_chars += len(phrase)
            hit_positions.append((pos, pos + len(phrase)))
            idx = pos + len(phrase)

    boilerplate_ratio = round(hit_chars / total_chars, 4) if total_chars else 0.0

    # 热区检测（滑动窗口）
    window   = cfg["boilerplate_window"]
    density  = cfg["boilerplate_density_threshold"]
    hot_zones = []
    if hit_positions and len(main_text) > window:
        i = 0
        while i < len(main_text) - window:
            window_text  = main_text[i: i + window]
            window_norm  = len(normalize(window_text))
            covered_chars = sum(
                min(end, i + window) - max(start, i)
                for start, end in hit_positions
                if start < i + window and end > i
            )
            if window_norm > 0 and covered_chars / window_norm >= density:
                # 合并相邻热区
                if hot_zones and i - hot_zones[-1]["end"] < 100:
                    hot_zones[-1]["end"] = i + window
                    hot_zones[-1]["density"] = round(
                        max(hot_zones[-1]["density"], covered_chars / window_norm), 3
                    )
                else:
                    hot_zones.append({
                        "start":   i,
                        "end":     i + window,
                        "density": round(covered_chars / window_norm, 3),
                        "snippet": window_text[:100].replace("\n", " ")
                    })
            i += window // 2

    hits.sort(key=lambda x: x["position"])

    return {
        "enabled":          True,
        "hits":             hits[:100],
        "boilerplate_chars": hit_chars,
        "boilerplate_ratio": boilerplate_ratio,
        "hot_zones":        hot_zones[:10],
        "stats": {
            "phrase_count":      len(phrases),
            "hit_count":         len(hits),
            "boilerplate_chars": hit_chars,
            "boilerplate_ratio": boilerplate_ratio,
            "hot_zone_count":    len(hot_zones)
        }
    }


# ── 综合查重率 ────────────────────────────────────────────────────────────────

def calc_overall(l1: dict, l2: dict, l3: dict, total_chars: int) -> dict:
    """综合三层数据，计算综合查重率和风险等级。"""
    l1_chars  = l1.get("dup_chars", 0)
    l2_chars  = l2.get("dup_chars", 0)
    l3_chars  = l3.get("boilerplate_chars", 0)

    # 去重后的重复字数（三层取最大，避免重复计数）
    combined_dup = max(l1_chars, l2_chars) + l3_chars * 0.5
    overall_ratio = round(combined_dup / total_chars, 4) if total_chars else 0.0

    if overall_ratio >= 0.40:
        risk_level = "高风险"
    elif overall_ratio >= 0.20:
        risk_level = "中风险"
    else:
        risk_level = "低风险"

    return {
        "overall_ratio": overall_ratio,
        "overall_pct":   f"{overall_ratio*100:.1f}%",
        "risk_level":    risk_level,
        "l1_dup_chars":  l1_chars,
        "l2_dup_chars":  l2_chars,
        "l3_bp_chars":   l3_chars
    }


# ── 入口 ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="三层查重主控")
    parser.add_argument("--main",        required=True, help="主文档全文路径（.txt）")
    parser.add_argument("--structure",   required=True, help="主文档结构 JSON 路径")
    parser.add_argument("--corpus",      default="",    help="对比库目录（可选）")
    parser.add_argument("--config",      default="",    help="查重配置 JSON（可选）")
    parser.add_argument("--boilerplate", default="",    help="套话库 JSON（可选）")
    parser.add_argument("--output",      required=True, help="输出结果 JSON 路径")
    args = parser.parse_args()

    cfg         = load_config(args.config)
    main_text   = load_text(args.main)
    main_struct = load_json(args.structure)
    total_chars = len(main_text)

    print(f"[INFO] 主文档：{total_chars} 字，{len(main_struct.get('paragraphs',[])) } 个段落")

    print("[L1] 跨文档查重…")
    l1 = l1_cross_doc(main_text, main_struct, args.corpus, cfg)
    corpus_count = l1.get("total_corpus", 0)
    print(f"     对比库：{corpus_count} 份 | 高相似：{l1.get('high_sim_count', 0)} 份")

    print("[L2] 内部段落查重…")
    l2 = l2_internal(main_struct, cfg)
    print(f"     段落对比：{l2['stats'].get('pair_count', 0)} 对 "
          f"| 重复段落对：{l2['stats'].get('dup_pair_count', 0)} 对 "
          f"| 重复字数：{l2.get('dup_chars', 0)}")

    print("[L3] 模板套话扫描…")
    l3 = l3_boilerplate(main_text, args.boilerplate, cfg)
    print(f"     套话命中：{l3['stats'].get('hit_count', 0)} 处 "
          f"| 套话覆盖率：{l3.get('boilerplate_ratio', 0)*100:.1f}% "
          f"| 热区：{l3['stats'].get('hot_zone_count', 0)} 处")

    overall = calc_overall(l1, l2, l3, total_chars)
    print(f"[综合] 查重率：{overall['overall_pct']}  风险：{overall['risk_level']}")

    result = {
        "source_file": main_struct.get("source_file", ""),
        "total_chars": total_chars,
        "overall":     overall,
        "l1":          l1,
        "l2":          l2,
        "l3":          l3,
        "config":      cfg
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[OK] 查重结果已保存 → {args.output}")


if __name__ == "__main__":
    main()
