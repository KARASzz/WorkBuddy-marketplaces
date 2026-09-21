#!/usr/bin/env python3
"""
评标办法路由与评分/排序引擎。

读取 bidders_manifest.json（多家投标人的 D1~D5 检查结果路径），
结合招标分析 JSON 中的 evaluation_method，执行：

  1. 废标判定（D1/D3/D4/D5 废标条件逐一检查）
  2. 综合评分法：技术分、商务分、价格分和总分
  3. 经评审最低投标价法：按经评审价格升序
  4. 合理低价法：仅在结构化基准价和排序规则齐备时排序
  5. 未知/其他办法或关键参数不足：阻断自动排名

输出 evaluation_scores.json，供 word-document-processing 生成评标报告使用。
无第三方依赖，仅标准库。
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


SUPPORTED_METHODS = {
    "comprehensive_scoring",
    "lowest_evaluated_price",
    "reasonable_low_price",
    "other",
    "unknown",
}


# ── JSON 加载 ─────────────────────────────────────────────────

def load_json(path: str) -> dict:
    p = Path(path)
    if not path or not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[warn] 读取 {path} 失败：{e}", file=sys.stderr)
        return {}


def load_manifest(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        print(f"[error] 找不到 manifest：{path}", file=sys.stderr)
        sys.exit(1)
    return json.loads(p.read_text(encoding="utf-8"))


# ── 废标判定 ──────────────────────────────────────────────────

def check_disqualification(d1: dict, d3: dict, d4: dict, d5: dict) -> list:
    """
    返回废标原因列表；空列表 = 有效投标。
    """
    reasons = []

    # D1：格式废标项
    for item in d1.get("items", []):
        if item.get("severity") == "废标":
            reasons.append(f"D1格式: {item.get('name', item.get('description', ''))[:30]}")

    # D3：未规避的废标风险
    for item in d3.get("items", []):
        if item.get("avoidance_status") == "未规避":
            reasons.append(f"D3风险: 未规避「{item.get('risk', '')[:30]}」")

    # D4：报价超最高限价（P001）
    for item in d4.get("items", []):
        if item.get("check_id") == "P001" and item.get("passed") is False:
            detected = item.get("detected", "")
            required = item.get("required", "")
            reasons.append(f"D4报价: {detected} 超出限价 {required}")

    # D5：必要资质未声明
    for item in d5.get("items", []):
        if not item.get("is_bonus", False) and item.get("status") == "未声明":
            reasons.append(f"D5资质: 未声明「{item.get('requirement', '')[:25]}」")

    return reasons


# ── 报价提取（从 D4 结果）────────────────────────────────────

_PRICE_RE = re.compile(r'[¥￥]?\s*([\d,]+(?:\.\d+)?)')


def extract_price_from_d4(d4: dict) -> Optional[float]:
    """从 D4 结果中提取投标总价（元）。"""
    for item in d4.get("items", []):
        if item.get("check_id") in ("P001", "P002"):
            detected = item.get("detected", "")
            if detected and detected != "未找到投标总价":
                m = _PRICE_RE.search(detected.replace(",", ""))
                if m:
                    try:
                        return float(m.group(1).replace(",", ""))
                    except ValueError:
                        pass
    # 备用：从 stats
    stats = d4.get("stats", {})
    if isinstance(stats, dict):
        raw = stats.get("bid_price") or stats.get("total_price")
        if raw:
            m = _PRICE_RE.search(str(raw).replace(",", ""))
            if m:
                try:
                    return float(m.group(1))
                except ValueError:
                    pass
    return None


def _positive_float(value) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def extract_evaluated_price(bidder: dict, d4: dict) -> Optional[float]:
    """读取结构化经评审/调整后价格，不从自由文本猜测。"""
    for value in (
        bidder.get("evaluated_price"),
        bidder.get("adjusted_price"),
        (d4.get("stats") or {}).get("evaluated_price"),
        (d4.get("stats") or {}).get("adjusted_price"),
    ):
        number = _positive_float(value)
        if number is not None:
            return number
    return None


def resolve_evaluation_method(scoring: dict) -> str:
    method = str(scoring.get("evaluation_method") or "unknown").strip().lower()
    return method if method in SUPPORTED_METHODS else "unknown"


def _score_total(scoring: dict, key: str) -> Optional[float]:
    value = scoring.get(key)
    if not isinstance(value, dict):
        return None
    total = value.get("total")
    try:
        return float(total)
    except (TypeError, ValueError):
        return None


def _has_price_adjustments(scoring: dict) -> bool:
    return any(scoring.get(key) not in (None, "", [], {}) for key in (
        "price_adjustments", "price_adjustment_rules"
    ))


# ── 维度评分 ──────────────────────────────────────────────────

def _avg_hit_rate(d2_items: list, dimension: str) -> float:
    """计算 D2 结果中指定维度的平均命中率。"""
    filtered = [it for it in d2_items if it.get("dimension") == dimension]
    if not filtered:
        return 0.0
    return sum(it.get("hit_rate", 0) for it in filtered) / len(filtered)


def calc_technical_score(d2: dict, technical_total: float) -> float:
    """技术分 = technical_total × avg(D2技术类命中率)"""
    avg = _avg_hit_rate(d2.get("items", []), "技术")
    return round(technical_total * avg, 2)


def calc_commercial_score(d2: dict, d5: dict, commercial_total: float) -> float:
    """
    商务分 = min(commercial_total,
                 commercial_total × 0.6 × avg(D2商务类命中率)
                 + D5加分项已声明的 bonus_points 之和)
    """
    avg = _avg_hit_rate(d2.get("items", []), "商务")
    base = commercial_total * 0.6 * avg

    bonus = sum(
        it.get("bonus_points", 0)
        for it in d5.get("items", [])
        if it.get("is_bonus") and it.get("status") == "已声明"
    )
    return round(min(commercial_total, base + bonus), 2)


def calc_price_score(bid_price: Optional[float],
                     base_price: Optional[float],
                     price_total: float) -> float:
    """
    价格分 = min(price_total, price_total × base_price / bid_price)
    base_price 为有效投标人报价均值（由调用方传入）。
    """
    if not bid_price or not base_price or bid_price <= 0:
        return 0.0
    raw = price_total * (base_price / bid_price)
    return round(min(price_total, raw), 2)


# ── 各投标人统计摘要 ─────────────────────────────────────────

def make_bidder_stats(d1, d2, d3, d4, d5) -> dict:
    d1_items = d1.get("items", [])
    d2_items = d2.get("items", [])
    d3_items = d3.get("items", [])
    d5_items = d5.get("items", [])
    d4_items = d4.get("items", [])

    return {
        "d1_fatal":       sum(1 for it in d1_items if it.get("severity") == "废标"),
        "d1_warn":        sum(1 for it in d1_items if it.get("severity") == "扣分"),
        "d1_pass":        sum(1 for it in d1_items if it.get("severity") == "通过"),
        "d2_full":        sum(1 for it in d2_items if it.get("response_level") == "完全响应"),
        "d2_partial":     sum(1 for it in d2_items if it.get("response_level") == "部分响应"),
        "d2_none":        sum(1 for it in d2_items if it.get("response_level") == "未响应"),
        "d3_avoided":     sum(1 for it in d3_items if it.get("avoidance_status") == "已规避"),
        "d3_partial":     sum(1 for it in d3_items if it.get("avoidance_status") == "疑似规避"),
        "d3_not_avoided": sum(1 for it in d3_items if it.get("avoidance_status") == "未规避"),
        "d4_price":       extract_price_from_d4(d4),
        "d4_fatal":       sum(1 for it in d4_items if it.get("severity") == "废标"),
        "d5_declared":    sum(1 for it in d5_items if not it.get("is_bonus") and it.get("status") == "已声明"),
        "d5_uncertain":   sum(1 for it in d5_items if not it.get("is_bonus") and it.get("status") == "不确定"),
        "d5_missing":     sum(1 for it in d5_items if not it.get("is_bonus") and it.get("status") == "未声明"),
        "d5_bonus_hit":   sum(1 for it in d5_items if it.get("is_bonus") and it.get("status") == "已声明"),
        # 原始数据备用
        "d1_items": d1_items,
        "d2_items": d2_items,
        "d3_items": d3_items,
        "d4_items": d4_items,
        "d5_items": d5_items,
    }


# ── 主流程 ────────────────────────────────────────────────────

def evaluate(manifest: dict) -> dict:
    # 读取招标分析
    analysis = load_json(manifest.get("tender_analysis", ""))
    scoring  = analysis.get("scoring", {})
    overview = analysis.get("project_overview", {})

    method = resolve_evaluation_method(scoring)
    method_text = str(scoring.get("evaluation_method_text") or method)
    technical_total = _score_total(scoring, "technical_score")
    commercial_total = _score_total(scoring, "commercial_score")
    price_total = _score_total(scoring, "price_score")

    # 读取围串标结果
    collusion = load_json(manifest.get("collusion_result", ""))
    collusion_risk = collusion.get("risk_level", "—")

    # 第一轮：收集各投标人数据 + 废标判定
    bidder_records = []
    seen_bidder_ids = set()
    for index, bdr in enumerate(manifest.get("bidders", []), 1):
        bidder_id = str(bdr.get("bidder_id") or f"bidder-{index:03d}").strip()
        if bidder_id in seen_bidder_ids:
            raise ValueError(f"duplicate bidder_id: {bidder_id}")
        seen_bidder_ids.add(bidder_id)
        name = bdr.get("name", "未知投标人")
        d1 = load_json(bdr.get("d1", ""))
        d2 = load_json(bdr.get("d2", ""))
        d3 = load_json(bdr.get("d3", ""))
        d4 = load_json(bdr.get("d4", ""))
        d5 = load_json(bdr.get("d5", ""))

        reasons = check_disqualification(d1, d3, d4, d5)
        stats   = make_bidder_stats(d1, d2, d3, d4, d5)

        bidder_records.append({
            "bidder_id": bidder_id,
            "name":      name,
            "is_valid":  len(reasons) == 0,
            "disqualify_reasons": reasons,
            "stats":     stats,
            "evaluated_price": extract_evaluated_price(bdr, d4),
        })

    # 第二轮：按评标办法准备基准值与安全阻断条件
    valid_prices = [
        r["stats"]["d4_price"]
        for r in bidder_records
        if r["is_valid"] and r["stats"]["d4_price"]
    ]
    base_price = None
    ranking_basis = ""
    calculation_status = "completed"
    calculation_warnings = []

    if method == "comprehensive_scoring":
        totals = (technical_total, commercial_total, price_total)
        if any(value is None or value < 0 for value in totals):
            calculation_status = "blocked"
            calculation_warnings.append("综合评分法缺少结构化技术/商务/价格满分，已阻断自动评分。")
        elif not valid_prices:
            calculation_status = "blocked"
            calculation_warnings.append("有效投标人缺少可用报价，无法计算综合评分价格分。")
        else:
            explicit_base = _positive_float(scoring.get("benchmark_price"))
            base_price = explicit_base or (sum(valid_prices) / len(valid_prices))
            ranking_basis = "综合总分降序"
    elif method == "lowest_evaluated_price":
        ranking_basis = "经评审价格升序"
        has_adjustments = _has_price_adjustments(scoring)
        for rec in bidder_records:
            if not rec["is_valid"]:
                continue
            if rec["evaluated_price"] is None and not has_adjustments:
                rec["evaluated_price"] = rec["stats"]["d4_price"]
            if rec["evaluated_price"] is None:
                calculation_status = "blocked"
                calculation_warnings.append(
                    f"{rec['name']} 缺少经评审价格；当前办法含价格调整规则，不得直接用投标报价替代。"
                )
        if not any(rec["is_valid"] for rec in bidder_records):
            calculation_status = "completed"
    elif method == "reasonable_low_price":
        ranking_basis = "与基准价绝对偏差升序"
        base_price = _positive_float(scoring.get("benchmark_price"))
        ranking_rule = str(scoring.get("ranking_rule") or "").strip()
        if base_price is None or ranking_rule != "closest_to_benchmark":
            calculation_status = "blocked"
            calculation_warnings.append(
                "合理低价法须提供 benchmark_price 和 ranking_rule=closest_to_benchmark；未满足时不得猜测排序公式。"
            )
        for rec in bidder_records:
            if rec["is_valid"] and rec["evaluated_price"] is None:
                rec["evaluated_price"] = rec["stats"]["d4_price"]
                if rec["evaluated_price"] is None:
                    calculation_status = "blocked"
                    calculation_warnings.append(f"{rec['name']} 缺少可用于合理低价排序的价格。")
        if not any(rec["is_valid"] for rec in bidder_records):
            calculation_status = "completed"
    else:
        calculation_status = "blocked"
        calculation_warnings.append(
            f"评标办法为 {method_text}（{method}），缺少受支持的结构化评分/排序规则，已阻断自动排名。"
        )

    if not any(rec["is_valid"] for rec in bidder_records):
        calculation_status = "completed"
        calculation_warnings = []
        ranking_basis = "无有效投标人，不执行排名"

    # 第三轮：计算得分
    ranked = []
    result_bidders = []
    for rec in bidder_records:
        stats = rec["stats"]
        if rec["is_valid"] and calculation_status == "completed" and method == "comprehensive_scoring":
            t_score = calc_technical_score({"items": stats["d2_items"]}, technical_total)
            c_score = calc_commercial_score(
                {"items": stats["d2_items"]}, {"items": stats["d5_items"]}, commercial_total
            )
            p_score = calc_price_score(stats["d4_price"], base_price, price_total)
            total = round(t_score + c_score + p_score, 2)
            scores = {"technical": t_score, "commercial": c_score, "price": p_score, "total": total}
            ranked.append({
                "bidder_id": rec["bidder_id"], "name": rec["name"], "total": total,
                "ranking_value": total, "scores": scores,
            })
        elif rec["is_valid"] and calculation_status == "completed" and method == "lowest_evaluated_price":
            value = rec["evaluated_price"]
            scores = {"technical": None, "commercial": None, "price": None, "total": None}
            ranked.append({
                "bidder_id": rec["bidder_id"], "name": rec["name"], "total": None,
                "ranking_value": value, "evaluated_price": value, "scores": scores,
            })
        elif rec["is_valid"] and calculation_status == "completed" and method == "reasonable_low_price":
            value = rec["evaluated_price"]
            deviation = abs(value - base_price)
            scores = {"technical": None, "commercial": None, "price": None, "total": None}
            ranked.append({
                "bidder_id": rec["bidder_id"], "name": rec["name"], "total": None,
                "ranking_value": deviation, "evaluated_price": value,
                "deviation_from_benchmark": deviation, "scores": scores,
            })
        else:
            scores = {"technical": None, "commercial": None, "price": None, "total": None}

        # 清理 items 列表（不写入输出 JSON，减小体积）
        clean_stats = {k: v for k, v in stats.items()
                       if not k.endswith("_items")}

        result_bidders.append({
            "bidder_id":           rec["bidder_id"],
            "name":               rec["name"],
            "is_valid":           rec["is_valid"],
            "disqualify_reasons": rec["disqualify_reasons"],
            "scores":             scores,
            "rank":               None,
            "evaluated_price":    rec["evaluated_price"],
            **clean_stats,
        })

    # 排名
    ranked.sort(
        key=lambda x: x["ranking_value"],
        reverse=(method == "comprehensive_scoring"),
    )
    ranking = []
    bidders_by_id = {item["bidder_id"]: item for item in result_bidders}
    for i, r in enumerate(ranked, start=1):
        ranking.append({**r, "rank": i})
        bidders_by_id[r["bidder_id"]]["rank"] = i

    return {
        "project_name":    overview.get("project_name", "—"),
        "buyer":           overview.get("buyer", "—"),
        "evaluated_at":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "evaluation_method": method,
        "evaluation_method_text": method_text,
        "ranking_basis": ranking_basis,
        "calculation_status": calculation_status,
        "calculation_warnings": calculation_warnings,
        "scoring_weights": {
            "technical":  technical_total,
            "commercial": commercial_total,
            "price":      price_total,
        },
        "base_price":      base_price,
        "collusion_risk":  collusion_risk,
        "collusion_result": collusion,
        "tender_analysis": analysis,
        "bidders":         result_bidders,
        "ranking":         ranking,
        "valid_count":     sum(1 for rec in bidder_records if rec["is_valid"]),
        "total_count":     len(result_bidders),
    }


def main():
    parser = argparse.ArgumentParser(description="招投标综合评分引擎")
    parser.add_argument("--manifest", required=True,
                        help="bidders_manifest.json 路径")
    parser.add_argument("--output",   default="/tmp/evaluation_scores.json",
                        help="输出 JSON 路径（默认 /tmp/evaluation_scores.json）")
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    result   = evaluate(manifest)

    total   = result["total_count"]
    valid   = result["valid_count"]
    invalid = total - valid
    print(f"[info] 共 {total} 家投标人：有效 {valid} 家 / 废标 {invalid} 家")
    if result["calculation_status"] == "blocked":
        print("[warn] 自动排名已阻断：", file=sys.stderr)
        for warning in result["calculation_warnings"]:
            print(f"       - {warning}", file=sys.stderr)
    elif result["ranking"]:
        winner = result["ranking"][0]
        if result["evaluation_method"] == "comprehensive_scoring":
            print(f"[info] 暂定第一名：{winner['name']} ({winner['total']:.2f}分)")
        else:
            print(f"[info] 暂定第一名：{winner['name']}（依据：{result['ranking_basis']}）")
    else:
        print("[info] 无有效投标人，建议废标重招")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[done] 评分结果已写入 {out}")


if __name__ == "__main__":
    main()
