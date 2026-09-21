#!/usr/bin/env python3
"""
基于 JSON 解析数据生成交互式 HTML 投标工作台。
单文件自包含（内联 CSS + JS），无外部依赖，支持 localStorage 状态持久化。
无第三方 Python 依赖，仅使用标准库。

用法：
  python scripts/generate_html_workbench.py \
      --data /tmp/tender_analysis.json \
      --output "/mnt/user-data/outputs/项目名_投标工作台_20260513.html"
"""
import argparse
import json
import re
import sys
from datetime import datetime
from html import escape, unescape
from pathlib import Path

from analysis_schema import normalize_analysis, print_audit


# ──────────────────────────────────────────────
# 数据预处理
# ──────────────────────────────────────────────

def get(d, *keys, default=""):
    """安全取嵌套字段，任意层不存在返回 default。"""
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k, default)
    return cur if cur is not None else default


def to_number(value, default=0):
    """Convert common score strings such as '70分' to numbers."""
    if value is None:
        return default
    try:
        return float(str(value).replace("分", "").strip())
    except Exception:
        return default


def sop_tasks(deadline_str: str) -> list:
    """根据投标截止时间反推 SOP 任务节点。deadline_str 为 ISO 日期或空串。"""
    tasks = [
        (-21, "启动招标文件深度研读，明确投标策略"),
        (-14, "完成技术方案初稿编制"),
        (-10, "完成商务报价初稿，内部讨论定价"),
        (-7,  "完成投标文件全稿，启动内审"),
        (-3,  "完成所有文件签字、盖章、公证"),
        (-1,  "装订打印，逐项核查废标风险清单"),
        (0,   "截止前 2 小时送达，现场递交"),
    ]
    result = []
    try:
        deadline = datetime.fromisoformat(deadline_str)
        for offset, label in tasks:
            from datetime import timedelta
            d = deadline + timedelta(days=offset)
            result.append({"date": d.strftime("%Y-%m-%d"), "label": label, "offset": offset})
    except Exception:
        for offset, label in tasks:
            result.append({"date": f"截止前 {abs(offset)} 天" if offset != 0 else "截止当天",
                           "label": label, "offset": offset})
    return result


def find_bid_deadline(dates: list) -> str:
    """从时间节点列表中找投标截止时间，返回日期字符串或空串。"""
    keywords = ["投标", "递交", "开标", "截止"]
    for d in dates:
        event = d.get("event", "")
        if d.get("is_deadline") and any(k in event for k in keywords):
            dt = d.get("datetime", "")
            # 尝试截取 ISO 前缀
            return dt[:10] if len(dt) >= 10 else ""
    return ""


def quality_notice_html(audit: dict) -> str:
    """Build a visible data-quality notice for missing fields and repaired aliases."""
    repairs = audit.get("repairs", []) if audit else []
    missing = audit.get("missing", []) if audit else []
    if not repairs and not missing:
        return ""

    repair_rows = "".join(
        f"<li>已修复字段键名：<code>{escape(r.get('source', ''))}</code> → "
        f"<code>{escape(r.get('canonical', ''))}</code></li>"
        for r in repairs
    )
    missing_rows = "".join(
        f"<li><strong>{escape(i.get('section', ''))}</strong>："
        f"{escape(i.get('message', ''))}</li>"
        for i in missing
    )

    repair_block = f"<ul>{repair_rows}</ul>" if repair_rows else ""
    missing_block = ""
    if missing_rows:
        missing_block = (
            "<p>以下信息在输入材料或解析结果中为空，请确认原始招标文件是否包含相关内容；"
            "如原文已包含，建议重新解析对应章节。</p>"
            f"<ul>{missing_rows}</ul>"
        )

    return f"""
  <div class="notice-card">
    <div class="notice-title">解析质量提示</div>
    {repair_block}
    {missing_block}
  </div>
"""


def display_text(value, default="") -> str:
    """Flatten common LLM output shapes for safe human-readable rendering."""
    if value is None or value == "" or value == [] or value == {}:
        return default
    if isinstance(value, str):
        return value.strip() or default
    if isinstance(value, (list, tuple)):
        parts = [display_text(item) for item in value]
        return "\n".join(part for part in parts if part) or default
    if isinstance(value, dict):
        for key in ("text", "content", "description", "rule", "requirement", "name"):
            if value.get(key):
                return display_text(value[key], default)
        parts = []
        for key, item in value.items():
            text = display_text(item)
            if text:
                parts.append(f"{key}：{text}")
        return "\n".join(parts) or default
    return str(value)


def safe_rich_text(value, default="暂无建议，请在解析阶段补充。") -> str:
    """Safely render strategy/rule text as paragraphs or a list, never raw LLM HTML."""
    text = display_text(value, default)
    text = re.sub(r"<\s*(script|style)\b[^>]*>.*?<\s*/\s*\1\s*>", "", text, flags=re.I | re.S)
    text = re.sub(r"<\s*br\s*/?\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<\s*/\s*li\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<\s*li\b[^>]*>", "- ", text, flags=re.I)
    text = unescape(re.sub(r"<[^>]+>", "", text))
    lines = [re.sub(r"^\s*(?:[-*•·]|\d+[.)、])\s*", "", line).strip()
             for line in text.splitlines()]
    lines = [line for line in lines if line]
    if len(lines) > 1:
        return "<ul>" + "".join(f"<li>{escape(line)}</li>" for line in lines) + "</ul>"
    return f"<p>{escape(lines[0] if lines else default)}</p>"


def review_summary(value, default) -> str:
    return safe_rich_text(value, default)


def price_method_panel(scoring: dict, mandatory: list, method: str) -> str:
    """Render method-aware content for lowest-price and reasonable-low-price tenders."""
    is_lowest = method == "lowest_evaluated_price"
    method_name = display_text(
        scoring.get("evaluation_method_text"),
        "经评审的最低投标价法" if is_lowest else "合理低价法",
    )
    award_default = (
        "通过初步评审后，按招标文件载明的价格调整方法确定经评审价格，并依其排序推荐中标候选人。"
        if is_lowest else
        "通过初步评审后，按招标文件载明的基准价、有效报价区间及扣分或排序规则推荐中标候选人。"
    )
    award_rule = scoring.get("award_rule") or scoring.get("winning_rule") or award_default
    initial = scoring.get("initial_review") or scoring.get("preliminary_review")
    detailed = scoring.get("detailed_review") or scoring.get("price_review")
    adjustment = (
        scoring.get("price_adjustments") or scoring.get("price_adjustment_rules")
        or scoring.get("benchmark_formula")
    )
    source = display_text(scoring.get("method_source") or scoring.get("source"), "出处待核实")
    stage_two_title = "详细评审（价格调整与排序）" if is_lowest else "价格评审（基准价与报价排序）"
    strategy_tip = scoring.get("strategy_tip") or (
        "先确保资格、形式与响应性审查全部通过，并尽量实现技术商务零偏差；再结合成本底线控制经评审价格。"
        if is_lowest else
        "先确保资格、形式与响应性审查全部通过；报价应围绕有效报价区间和基准价规则测算，不得把“最低价”误当作必然最优。"
    )

    return f"""
<div class="tab-panel" id="panel-2">
  <div class="card">
    <div class="card-header">
      <h2>评标办法：{escape(method_name)}</h2>
      <span class="method-source">来源：{escape(source)}</span>
    </div>
    <div class="card-body">
      <div class="award-rule"><strong>中标规则：</strong>{safe_rich_text(award_rule, award_default)}</div>
      <div class="evaluation-grid">
        <section class="evaluation-stage stage-initial">
          <h3>第一阶段：初步评审</h3>
          {review_summary(initial, "核验资格、形式与响应性要求；任一否决条件不满足，通常不得进入后续评审。")}
        </section>
        <section class="evaluation-stage stage-detail">
          <h3>第二阶段：{stage_two_title}</h3>
          {review_summary(detailed, "按招标文件载明的价格调整、基准价、有效报价或排序规则进行评审。")}
        </section>
      </div>
      <h3 class="section-title">初步评审资格条件（{len(mandatory)} 项）</h3>
      <p class="section-help">逐项勾选确认；该清单复用“资质自查”数据，不能替代招标文件中的完整形式与响应性审查。</p>
      <table>
        <thead><tr><th style="width:52px">序号</th><th>资格条件</th><th>证明材料</th><th style="width:72px">状态</th></tr></thead>
        <tbody id="qual-pass-tbody"></tbody>
      </table>
      <div class="price-rule"><strong>价格规则：</strong>{safe_rich_text(adjustment, "文件未完整载明或尚未提取，请人工复核评标办法原文。")}</div>
      <div class="strategy-tip"><strong>策略提示：</strong>{safe_rich_text(strategy_tip)}</div>
    </div>
  </div>
</div>
"""


def comprehensive_scoring_panel(scoring: dict, tech_total, comm_total, price_total,
                                total_score, comm_items: list) -> str:
    commercial_table = ""
    if comm_items:
        commercial_table = """
      <h3 class="section-title">商务评分项</h3>
      <table><thead><tr><th>评分项</th><th>分值</th><th>评分标准</th><th>预估得分</th></tr></thead>
        <tbody id="comm-tbody"></tbody></table>
"""
    formula = escape(display_text((scoring.get("price_score") or {}).get("formula"), "文件未载明"))
    return f"""
<div class="tab-panel" id="panel-2">
  <div class="card">
    <div class="card-header">
      <h2>评分拆解器</h2>
      <span class="method-source">填入预估得分，实时合计</span>
    </div>
    <div class="card-body">
      <div class="score-summary">
        <div>技术分满分：<strong>{tech_total:g}</strong> 分</div>
        <div>商务分满分：<strong>{comm_total:g}</strong> 分</div>
        <div>价格分满分：<strong>{price_total:g}</strong> 分</div>
        <div>预估总分：<strong class="score-total" id="total-score">0</strong> / <strong>{total_score:g}</strong></div>
      </div>
      <h3 class="section-title">技术评分项</h3>
      <table>
        <thead><tr><th>评分项</th><th>分值</th><th>评分标准</th><th>所需材料</th><th>预估得分</th></tr></thead>
        <tbody id="tech-tbody"></tbody>
      </table>
      {commercial_table}
      <div class="formula-note">价格分公式：{formula}</div>
    </div>
  </div>
</div>
"""


# ──────────────────────────────────────────────
# JSON → HTML
# ──────────────────────────────────────────────

def build_html(data: dict, audit: dict = None) -> str:
    if audit is None:
        data, audit = normalize_analysis(data, include_aliases=True)

    ov       = data.get("project_overview", {})
    dates    = data.get("dates", [])
    quals    = data.get("qualifications", {})
    scoring  = data.get("scoring", {})
    risks    = data.get("risks", [])
    star_clauses = data.get("star_clauses", [])
    comm     = data.get("commercial", {})
    strategy = data.get("strategy", {})

    project_name  = get(ov, "project_name", default="未命名项目")
    buyer         = get(ov, "buyer", default="")
    budget        = get(ov, "budget", default="文件未载明")
    duration      = get(ov, "duration", default="")

    tech_total  = to_number(get(scoring, "technical_score",  "total", default=0))
    comm_total  = to_number(get(scoring, "commercial_score", "total", default=0))
    price_total = to_number(get(scoring, "price_score",      "total", default=0))
    total_score = tech_total + comm_total + price_total
    tech_items  = get(scoring, "technical_score",  "items", default=[])
    comm_items  = get(scoring, "commercial_score", "items", default=[])
    evaluation_method = get(scoring, "evaluation_method", default="unknown")

    mandatory = quals.get("mandatory", [])
    bonus     = quals.get("bonus", [])

    high_risks = [r for r in risks if r.get("level") == "高"]
    bid_deadline_str = find_bid_deadline(dates)
    sop = sop_tasks(bid_deadline_str)

    # 将数据序列化后嵌入 JS
    def js(obj):
        return json.dumps(obj, ensure_ascii=False)

    today_iso = datetime.now().strftime("%Y-%m-%d")
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    quality_notice = quality_notice_html(audit)
    if evaluation_method in {"lowest_evaluated_price", "reasonable_low_price"}:
        scoring_panel = price_method_panel(scoring, mandatory, evaluation_method)
    else:
        scoring_panel = comprehensive_scoring_panel(
            scoring, tech_total, comm_total, price_total, total_score, comm_items
        )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>投标工作台 — {project_name}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei","Helvetica Neue",sans-serif;background:#f1f5f9;color:#1e293b;font-size:14px;line-height:1.6;-webkit-font-smoothing:antialiased}}
:root{{--blue:#1d4ed8;--blue-dark:#1e3a8a;--blue-light:#dbeafe;--orange:#ea580c;--orange-light:#fff7ed;--green:#15803d;--green-light:#f0fdf4;--red:#b91c1c;--red-light:#fef2f2;--gray:#64748b;--gray-light:#f1f5f9;--border:#e2e8f0;--dark:#0f172a}}

/* 顶栏 */
header{{background:linear-gradient(135deg,#1e3a8a 0%,#1d4ed8 100%);color:#fff;padding:20px 28px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100;box-shadow:0 4px 16px rgba(30,58,138,.25)}}
header h1{{font-size:18px;font-weight:700;letter-spacing:.3px}}
header .meta{{font-size:12px;opacity:.85;text-align:right;line-height:1.7}}

/* Tab 导航 */
nav{{background:#fff;display:flex;overflow-x:auto;position:sticky;top:68px;z-index:99;box-shadow:0 2px 8px rgba(0,0,0,.06);padding:0 8px}}
nav button{{padding:13px 20px;border:none;background:none;cursor:pointer;font-size:13px;color:var(--gray);white-space:nowrap;border-bottom:3px solid transparent;transition:all .2s;position:relative}}
nav button.active{{color:var(--blue);border-bottom-color:var(--blue);font-weight:600}}
nav button:hover{{background:#f8fafc;color:var(--dark)}}

/* 主内容 */
main{{max-width:1120px;margin:0 auto;padding:24px 16px 40px}}
.tab-panel{{display:none}}.tab-panel.active{{display:block;animation:fadeIn .25s ease}}
@keyframes fadeIn{{from{{opacity:0;transform:translateY(6px)}}to{{opacity:1;transform:translateY(0)}}}}
.card{{background:#fff;border-radius:12px;box-shadow:0 1px 3px rgba(0,0,0,.06),0 1px 2px rgba(0,0,0,.04);margin-bottom:18px;overflow:hidden;border:1px solid var(--border);transition:box-shadow .2s}}
.card:hover{{box-shadow:0 4px 12px rgba(0,0,0,.08)}}
.card-header{{padding:15px 20px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:10px;background:#fafbfc}}
.card-header h2{{font-size:15px;font-weight:600;color:var(--dark)}}
.card-body{{padding:20px}}

/* KPI 卡片 */
.kpi-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px;margin-bottom:18px}}
.kpi{{background:#fff;border-radius:12px;padding:20px 16px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,.06),0 1px 2px rgba(0,0,0,.04);border:1px solid var(--border);transition:transform .15s}}
.kpi:hover{{transform:translateY(-2px)}}
.kpi .val{{font-size:30px;font-weight:700;color:var(--blue);line-height:1.2}}
.kpi .lbl{{font-size:12px;color:var(--gray);margin-top:6px;font-weight:500}}
.kpi.warn .val{{color:var(--orange)}}.kpi.warn{{border-left:3px solid var(--orange)}}
.kpi.danger .val{{color:var(--red)}}.kpi.danger{{border-left:3px solid var(--red)}}
.kpi.ok .val{{color:var(--green)}}.kpi.ok{{border-left:3px solid var(--green)}}

/* 倒计时 */
#countdown{{font-size:24px;font-weight:700;color:var(--orange);margin-top:6px}}

/* 表格 */
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{background:#f8fafc;padding:10px 14px;text-align:left;font-weight:600;color:#475569;border-bottom:2px solid var(--border);font-size:12px}}
td{{padding:10px 14px;border-bottom:1px solid var(--border);vertical-align:top;line-height:1.55}}
tr:nth-child(even) td{{background:#fafbfd}}
tr:last-child td{{border-bottom:none}}
tr:hover td{{background:#f1f5f9}}

/* 风险徽章 */
.badge{{display:inline-block;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700}}
.badge-high{{background:var(--red-light);color:var(--red);border:1px solid #fecaca}}
.badge-mid{{background:var(--orange-light);color:var(--orange);border:1px solid #fed7aa}}
.badge-low{{background:var(--green-light);color:var(--green);border:1px solid #bbf7d0}}

/* 进度条 */
.progress-wrap{{background:#e2e8f0;border-radius:10px;height:10px;margin-top:8px;overflow:hidden}}
.progress-bar{{height:10px;border-radius:10px;background:var(--blue);transition:width .5s ease}}

/* 评分输入 */
.score-input{{width:64px;padding:5px 8px;border:1px solid var(--border);border-radius:8px;text-align:center;font-size:13px;transition:border-color .2s}}
.score-total{{font-weight:700;color:var(--blue);font-size:16px}}

/* 复选框行 */
.check-row{{display:flex;align-items:flex-start;gap:10px;padding:10px 0;border-bottom:1px solid var(--border)}}
.check-row:last-child{{border-bottom:none}}
.check-row input[type=checkbox]{{margin-top:2px;accent-color:var(--blue);width:16px;height:16px;flex-shrink:0}}
.check-row.done label{{text-decoration:line-through;color:var(--gray)}}
.note-input{{width:100%;border:1px solid var(--border);border-radius:6px;padding:4px 8px;font-size:12px;color:var(--gray);margin-top:4px}}

/* 甘特 */
.gantt-row{{display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid var(--border)}}
.gantt-row:last-child{{border-bottom:none}}
.gantt-date{{width:100px;font-size:12px;color:var(--gray);flex-shrink:0}}
.gantt-label{{flex:1;line-height:1.4}}
.gantt-done{{text-decoration:line-through;color:var(--gray)}}

/* 策略备忘 */
.strategy-section{{margin-bottom:22px}}
.strategy-section h3{{font-size:14px;font-weight:700;color:var(--dark);margin-bottom:10px;display:flex;align-items:center;gap:8px}}
.strategy-section h3::before{{content:"";display:inline-block;width:4px;height:16px;background:var(--blue);border-radius:2px}}
.strategy-content{{background:var(--gray-light);border-left:3px solid var(--blue);padding:14px 18px;border-radius:0 8px 8px 0;line-height:1.85;font-size:13px;color:#334155}}
.strategy-content ul,.award-rule ul,.price-rule ul,.strategy-tip ul,.evaluation-stage ul{{margin:0;padding-left:18px;list-style:none}}
.strategy-content li,.award-rule li,.price-rule li,.strategy-tip li,.evaluation-stage li{{position:relative;padding:5px 0 5px 16px;border-bottom:1px dashed var(--border)}}
.strategy-content li:last-child,.award-rule li:last-child,.price-rule li:last-child,.strategy-tip li:last-child,.evaluation-stage li:last-child{{border-bottom:none}}
.strategy-content li::before,.award-rule li::before,.price-rule li::before,.strategy-tip li::before,.evaluation-stage li::before{{content:"";position:absolute;left:0;top:13px;width:6px;height:6px;background:var(--blue);border-radius:50%}}
textarea.custom-note{{width:100%;min-height:90px;padding:12px;border:1px solid var(--border);border-radius:10px;font-size:13px;resize:vertical;font-family:inherit;line-height:1.6;transition:border-color .2s}}
textarea.custom-note:focus,.score-input:focus,.note-input:focus{{border-color:var(--blue);outline:none;box-shadow:0 0 0 3px rgba(29,78,216,.1)}}

/* 按钮 */
.btn{{display:inline-flex;align-items:center;gap:6px;padding:9px 18px;border-radius:10px;border:none;cursor:pointer;font-size:13px;font-weight:600;transition:all .2s}}
.btn-primary{{background:var(--blue);color:#fff}}.btn-primary:hover{{background:var(--blue-dark);box-shadow:0 2px 8px rgba(29,78,216,.3)}}
.btn-danger{{background:var(--red-light);color:var(--red)}}.btn-danger:hover{{background:#fecaca}}
.btn-sm{{padding:6px 14px;font-size:12px}}

/* 评标办法 */
.method-source{{margin-left:auto;font-size:12px;color:var(--gray);font-weight:600}}
.score-summary{{margin-bottom:16px;padding:13px;background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;display:flex;gap:32px;flex-wrap:wrap}}
.section-title{{margin:16px 0 8px;font-size:14px;color:var(--blue)}}
.section-help,.formula-note{{font-size:12px;color:var(--gray);margin-bottom:10px}}
.evaluation-grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px}}
.evaluation-stage{{border-radius:10px;padding:16px;line-height:1.75}}
.evaluation-stage h3{{margin-bottom:10px;font-size:14px}}
.stage-initial{{background:#eff6ff;border:1px solid #bfdbfe}}.stage-initial h3{{color:#1e40af}}
.stage-detail{{background:#fef3c7;border:1px solid #fde68a}}.stage-detail h3{{color:#92400e}}
.award-rule{{background:var(--green-light);border:1px solid #86efac;border-left:4px solid var(--green);border-radius:10px;padding:14px 16px;margin-bottom:20px;line-height:1.8}}
.award-rule>strong{{color:#166534}}
.price-rule{{margin-top:16px;padding:12px 14px;background:#f8fafc;border-radius:8px;color:var(--gray);line-height:1.8}}
.strategy-tip{{margin-top:12px;padding:12px 14px;background:var(--orange-light);border:1px solid #fed7aa;border-radius:8px;color:#7c2d12;line-height:1.7}}
.disclaimer{{max-width:1120px;margin:16px auto 0;padding:10px 16px;color:#475569;font-size:12px;line-height:1.7;background:#fff;border:1px solid var(--border);border-left:4px solid var(--blue);border-radius:8px}}

/* 数据质量提示 */
.notice-card{{background:#fff7ed;border:1px solid #fed7aa;border-left:4px solid var(--orange);border-radius:8px;padding:12px 14px;margin-bottom:16px;line-height:1.7;color:#7c2d12}}
.notice-title{{font-weight:700;margin-bottom:4px;color:#9a3412}}
.notice-card ul{{margin-left:18px}}
.notice-card code{{background:#ffedd5;border-radius:4px;padding:1px 4px}}
.empty-state{{padding:14px;border:1px dashed var(--border);border-radius:8px;background:#f8fafc;color:var(--gray);font-size:13px;line-height:1.7}}

/* 底栏 */
footer{{text-align:center;padding:20px;font-size:11px;color:#94a3b8;margin-top:8px}}

/* 响应式 */
@media(max-width:700px){{
  header{{flex-direction:column;gap:8px;text-align:center;padding:16px 20px}}
  header .meta{{text-align:center}}
  nav button{{padding:10px 12px;font-size:12px}}
  .kpi .val{{font-size:22px}}
  th,td{{padding:7px 8px}}
  .evaluation-grid{{grid-template-columns:1fr}}
}}
</style>
</head>
<body>

<header>
  <h1>投标工作台 — {project_name}</h1>
  <div class="meta">
    <div>{buyer}</div>
    <div>生成于 {generated_at}</div>
  </div>
</header>

<nav id="tabs">
  <button class="active" data-tab="0" onclick="switchTab(0)">总览</button>
  <button data-tab="1" onclick="switchTab(1)">时间轴</button>
  <button data-tab="2" onclick="switchTab(2)">评分拆解</button>
  <button data-tab="3" onclick="switchTab(3)">废标风险</button>
  <button data-tab="7" onclick="switchTab(7)">★条款</button>
  <button data-tab="4" onclick="switchTab(4)">资质自查</button>
  <button data-tab="5" onclick="switchTab(5)">投标 SOP</button>
  <button data-tab="6" onclick="switchTab(6)">策略备忘</button>
</nav>

<div class="disclaimer">本文档由 AI 辅助生成，仅供内部参考，不构成正式法律意见、投标决策意见或评标委员会最终意见，不能替代具有执业资格的律师、招投标专业人员或评审专家的独立判断。</div>

<main>

<!-- ① 总览 -->
<div class="tab-panel active" id="panel-0">
  {quality_notice}
  <div class="kpi-grid">
    <div class="kpi">
      <div class="val" id="countdown-val">--</div>
      <div class="lbl">距投标截止（天）</div>
    </div>
    <div class="kpi">
      <div class="val">{int(total_score)}</div>
      <div class="lbl">评分满分</div>
    </div>
    <div class="kpi {'danger' if len(high_risks) >= 3 else 'warn' if len(high_risks) >= 1 else 'ok'}">
      <div class="val">{len(risks)}</div>
      <div class="lbl">废标风险点（其中高风险 {len(high_risks)} 个）</div>
    </div>
    <div class="kpi">
      <div class="val">{len(mandatory)}</div>
      <div class="lbl">强制资质要求</div>
    </div>
    <div class="kpi {'danger' if any(c.get('type') in ('★', '否决', '强制') for c in star_clauses) else 'warn' if star_clauses else 'ok'}">
      <div class="val">{len(star_clauses)}</div>
      <div class="lbl">★/▲/否决条款</div>
    </div>
  </div>

  <div class="card">
    <div class="card-header"><h2>项目信息</h2></div>
    <div class="card-body">
      <table>
        <tr><th style="width:130px">项目名称</th><td>{project_name}</td></tr>
        <tr><th>招标人</th><td>{buyer}</td></tr>
        <tr><th>预算规模</th><td>{budget}</td></tr>
        <tr><th>合同周期</th><td>{duration}</td></tr>
        <tr><th>实施地点</th><td>{get(ov, "location", default="文件未载明")}</td></tr>
        <tr><th>联系方式</th><td>{get(ov, "contact", default="文件未载明")}</td></tr>
        <tr><th>投标截止</th><td id="deadline-display">{bid_deadline_str or "见时间轴"}</td></tr>
      </table>
    </div>
  </div>

  <div class="card">
    <div class="card-header"><h2>项目背景</h2></div>
    <div class="card-body" style="line-height:1.8">{get(ov, "background", default="文件未载明")}</div>
  </div>

  <div class="card">
    <div class="card-header"><h2>整体进度</h2></div>
    <div class="card-body">
      <div style="display:flex;gap:24px;flex-wrap:wrap">
        <div style="flex:1;min-width:180px">
          <div style="display:flex;justify-content:space-between;margin-bottom:4px">
            <span>废标风险规避</span><span id="risk-pct">0%</span>
          </div>
          <div class="progress-wrap"><div class="progress-bar" id="risk-bar" style="width:0%"></div></div>
        </div>
        <div style="flex:1;min-width:180px">
          <div style="display:flex;justify-content:space-between;margin-bottom:4px">
            <span>资质材料备齐</span><span id="qual-pct">0%</span>
          </div>
          <div class="progress-wrap"><div class="progress-bar" id="qual-bar" style="width:0%"></div></div>
        </div>
        <div style="flex:1;min-width:180px">
          <div style="display:flex;justify-content:space-between;margin-bottom:4px">
            <span>SOP 任务完成</span><span id="sop-pct">0%</span>
          </div>
          <div class="progress-wrap"><div class="progress-bar" id="sop-bar" style="width:0%"></div></div>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- ② 时间轴 -->
<div class="tab-panel" id="panel-1">
  <div class="card">
    <div class="card-header"><h2>关键时间节点</h2></div>
    <div class="card-body">
      <table>
        <thead><tr><th>事件</th><th>日期 / 时间</th><th>截止日</th><th>状态</th><th>备注</th></tr></thead>
        <tbody id="dates-tbody"></tbody>
      </table>
    </div>
  </div>
</div>

<!-- ③ 评标办法 / 评分拆解 -->
{scoring_panel}

<!-- ④ 废标风险 -->
<div class="tab-panel" id="panel-3">
  <div class="card">
    <div class="card-header">
      <h2>废标风险雷达</h2>
      <span id="risk-done-label" style="margin-left:auto;font-size:12px;color:var(--gray)"></span>
    </div>
    <div class="card-body">
      <div class="progress-wrap" style="margin-bottom:16px">
        <div class="progress-bar" id="risk-bar2" style="width:0%;background:var(--green)"></div>
      </div>
      <div id="risks-list"></div>
    </div>
  </div>
</div>

<!-- ④b ★条款 -->
<div class="tab-panel" id="panel-7">
  <div class="card">
    <div class="card-header"><h2>★/▲/否决条款清单</h2></div>
    <div class="card-body">
      <table>
        <thead><tr><th>编号</th><th>类型</th><th>类别</th><th>条款原文</th><th>出处</th><th>响应要求</th><th>证明材料</th></tr></thead>
        <tbody id="star-tbody"></tbody>
      </table>
    </div>
  </div>
</div>

<!-- ⑤ 资质自查 -->
<div class="tab-panel" id="panel-4">
  <div class="card">
    <div class="card-header">
      <h2>强制资质自查清单</h2>
      <button class="btn btn-sm btn-primary" style="margin-left:auto" onclick="exportMissing()">导出未备齐项</button>
    </div>
    <div class="card-body">
      <div id="quals-list"></div>
    </div>
  </div>
  {'<div class="card"><div class="card-header"><h2>加分项资质</h2></div><div class="card-body"><table><thead><tr><th>类别</th><th>要求</th><th>加分</th></tr></thead><tbody id="bonus-tbody"></tbody></table></div></div>' if bonus else ''}
</div>

<!-- ⑥ 投标 SOP -->
<div class="tab-panel" id="panel-5">
  <div class="card">
    <div class="card-header">
      <h2>投标 SOP 甘特图</h2>
      <span id="sop-done-label" style="margin-left:auto;font-size:12px;color:var(--gray)"></span>
    </div>
    <div class="card-body">
      <div class="progress-wrap" style="margin-bottom:16px">
        <div class="progress-bar" id="sop-bar2" style="width:0%;background:var(--green)"></div>
      </div>
      <div id="sop-list"></div>
    </div>
  </div>
</div>

<!-- ⑦ 策略备忘 -->
<div class="tab-panel" id="panel-6">
  <div class="card">
    <div class="card-header"><h2>投标策略建议</h2></div>
    <div class="card-body">
      <div class="strategy-section">
        <h3>差异化竞争点</h3>
        <div class="strategy-content">{safe_rich_text(strategy.get("differentiation"))}</div>
      </div>
      <div class="strategy-section">
        <h3>价格策略参考</h3>
        <div class="strategy-content">{safe_rich_text(strategy.get("pricing"), "暂无价格策略，请结合评标办法和成本底线补充。")}</div>
      </div>
      <div class="strategy-section">
        <h3>主要风险提示</h3>
        <div class="strategy-content">{safe_rich_text(strategy.get("risks"), "暂无风险提示，请结合否决条款和高风险项补充。")}</div>
      </div>
      <div class="strategy-section">
        <h3>文件编制重点</h3>
        <div class="strategy-content">{safe_rich_text(strategy.get("document_focus"), "暂无编制重点，请结合资格、响应与证明材料补充。")}</div>
      </div>
    </div>
  </div>
  <div class="card">
    <div class="card-header"><h2>自定义备注</h2></div>
    <div class="card-body">
      <textarea class="custom-note" id="custom-note" placeholder="在此记录投标团队的额外备注…" oninput="saveNote()"></textarea>
    </div>
  </div>
  <div style="text-align:right;margin-top:8px">
    <button class="btn btn-danger btn-sm" onclick="resetAll()">重置所有状态</button>
  </div>
</div>

</main>

<footer>
  本工作台由 AI 辅助生成，仅供内部使用。数据仅存储于本地浏览器，不上传至任何服务器。
</footer>

<script>
// ── 数据 ──────────────────────────────────────
const DATA = {{
  dates:    {js(dates)},
  techItems:{js(tech_items)},
  commItems:{js(comm_items)},
  risks:    {js(risks)},
  starClauses: {js(star_clauses)},
  mandatory:{js(mandatory)},
  bonus:    {js(bonus)},
  sop:      {js(sop)},
  evaluationMethod: {js(evaluation_method)},
  deadline: "{bid_deadline_str}",
  projectKey: {js(project_name)}.replace(/\\s+/g,"_")
}};

// ── localStorage 工具 ─────────────────────────
const KEY = "tender_wb_" + DATA.projectKey;
function load() {{
  try {{ return JSON.parse(localStorage.getItem(KEY)) || {{}}; }} catch {{ return {{}}; }}
}}
function save(state) {{
  localStorage.setItem(KEY, JSON.stringify(state));
}}
let STATE = load();

function getChecked(group, idx) {{
  return (STATE[group] || {{}})[idx] || false;
}}
function setChecked(group, idx, val) {{
  if (!STATE[group]) STATE[group] = {{}};
  STATE[group][idx] = val;
  save(STATE);
  updateProgress();
}}
function getNote(group, idx) {{
  return (STATE["note_" + group] || {{}})[idx] || "";
}}
function setNote(group, idx, val) {{
  if (!STATE["note_" + group]) STATE["note_" + group] = {{}};
  STATE["note_" + group][idx] = val;
  save(STATE);
}}
function getScore(idx) {{
  return (STATE["scores"] || {{}})[idx] || "";
}}
function setScore(idx, val) {{
  if (!STATE["scores"]) STATE["scores"] = {{}};
  STATE["scores"][idx] = val;
  save(STATE);
  recalcScore();
}}
function saveNote() {{
  STATE["custom_note"] = document.getElementById("custom-note").value;
  save(STATE);
}}
function resetAll() {{
  if (!confirm("确认清除所有勾选、得分和备注记录？此操作不可恢复。")) return;
  localStorage.removeItem(KEY);
  location.reload();
}}

function renderEmpty(container, text) {{
  if (!container) return;
  const div = document.createElement("div");
  div.className = "empty-state";
  div.textContent = text;
  container.appendChild(div);
}}

function renderEmptyRow(tbody, colspan, text) {{
  if (!tbody) return;
  const tr = document.createElement("tr");
  tr.innerHTML = `<td colspan="${{colspan}}" class="empty-state">${{text}}</td>`;
  tbody.appendChild(tr);
}}

// ── Tab 切换 ──────────────────────────────────
function switchTab(idx) {{
  const targetId = "panel-" + idx;
  document.querySelectorAll(".tab-panel").forEach(p => p.classList.toggle("active", p.id === targetId));
  document.querySelectorAll("nav button[data-tab]").forEach(b =>
    b.classList.toggle("active", b.dataset.tab === String(idx))
  );
}}

// ── 倒计时 ────────────────────────────────────
function updateCountdown() {{
  const el = document.getElementById("countdown-val");
  if (!DATA.deadline) {{ el.textContent = "—"; return; }}
  const now = new Date();
  const dl = new Date(DATA.deadline + "T23:59:59");
  const days = Math.ceil((dl - now) / 86400000);
  el.textContent = days > 0 ? days : (days === 0 ? "今天截止" : "已截止");
  el.style.color = days <= 3 ? "var(--red)" : days <= 7 ? "var(--orange)" : "var(--blue)";
}}
updateCountdown();
setInterval(updateCountdown, 60000);

// ── 时间轴渲染 ────────────────────────────────
(function renderDates() {{
  const tbody = document.getElementById("dates-tbody");
  if (!DATA.dates.length) {{
    renderEmptyRow(tbody, 5, "未提取到关键时间节点。请确认招标公告、投标人须知或开标安排是否已包含在输入文件中；若原文包含，请重新解析对应章节。");
    return;
  }}
  const today = new Date().toISOString().slice(0,10);
  DATA.dates.forEach((d,i) => {{
    const passed = d.datetime && d.datetime.slice(0,10) < today;
    const near   = d.datetime && d.datetime.slice(0,10) >= today &&
                   (new Date(d.datetime.slice(0,10)) - new Date(today)) / 86400000 <= 7;
    const done   = getChecked("dates", i);
    const tr = document.createElement("tr");
    tr.style.opacity = (passed && done) ? "0.5" : "1";
    tr.innerHTML = `
      <td>${{d.event || ""}}</td>
      <td style="white-space:nowrap;color:${{near?"var(--red)":passed?"var(--gray)":"inherit"}}">${{d.datetime || ""}}</td>
      <td>${{d.is_deadline ? "是" : ""}}</td>
      <td>
        <label style="display:flex;align-items:center;gap:6px;cursor:pointer">
          <input type="checkbox" ${{done?"checked":""}} onchange="setChecked('dates',${{i}},this.checked);this.closest('tr').style.opacity=this.checked&&'${{passed}}'?'0.5':'1'">
          <span style="font-size:12px">${{done?"已完成":"待处理"}}</span>
        </label>
      </td>
      <td style="color:var(--gray);font-size:12px">${{d.note || ""}}</td>`;
    tbody.appendChild(tr);
  }});
}})();

// ── 评分拆解渲染 ──────────────────────────────
(function renderScoring() {{
  if (["lowest_evaluated_price", "reasonable_low_price"].includes(DATA.evaluationMethod)) {{
    const tbody = document.getElementById("qual-pass-tbody");
    if (!DATA.mandatory.length) {{
      renderEmptyRow(tbody, 4, "未提取到资格条件。请重新解析资格审查、形式评审和响应性评审章节。");
      return;
    }}
    DATA.mandatory.forEach((item, i) => {{
      const done = getChecked("quals", i);
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${{i + 1}}</td>
        <td><strong>${{item.category || "未分类"}}</strong>：${{item.requirement || ""}}</td>
        <td>${{item.document || "文件未载明"}}</td>
        <td><label style="display:flex;align-items:center;gap:6px;cursor:pointer">
          <input type="checkbox" ${{done ? "checked" : ""}}
            onchange="setChecked('quals',${{i}},this.checked)">
          <span>${{done ? "已确认" : "待确认"}}</span>
        </label></td>`;
      tbody.appendChild(tr);
    }});
    return;
  }}

  function makeRow(tbody, item, idx, hasEvidence) {{
    const w = Number(item.weight) || 0;
    const score = getScore(idx);
    const high = w >= 10;
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td style="font-weight:${{high?700:400}};color:${{high?"var(--blue)":"inherit"}}">
        ${{item.name || ""}}${{high?' <span style="font-size:11px;color:var(--orange)">[优先攻克]</span>':''}}
      </td>
      <td style="text-align:center">${{w}}</td>
      <td style="font-size:12px;color:var(--gray)">${{item.criteria || ""}}</td>
      ${{hasEvidence ? `<td style="font-size:12px">${{item.evidence || ""}}</td>` : ''}}
      <td style="text-align:center">
        <input class="score-input" type="number" min="0" max="${{w}}" value="${{score}}"
          oninput="setScore('${{idx}}',this.value)" placeholder="0">
      </td>`;
    tbody.appendChild(tr);
  }}

  const techTbody = document.getElementById("tech-tbody");
  if (!DATA.techItems.length) {{
    renderEmptyRow(techTbody, 5, "未提取到技术评分项。请确认评标办法/评分细则章节是否完整；若原文包含，请重新解析评分标准。");
  }} else {{
    DATA.techItems.forEach((item, i) => makeRow(techTbody, item, "t"+i, true));
  }}

  const commTbody = document.getElementById("comm-tbody");
  if (commTbody) DATA.commItems.forEach((item, i) => makeRow(commTbody, item, "c"+i, false));

  recalcScore();
}})();

function recalcScore() {{
  const totalEl = document.getElementById("total-score");
  if (!totalEl) return;
  let total = 0;
  document.querySelectorAll(".score-input").forEach(inp => {{
    total += parseFloat(inp.value) || 0;
  }});
  totalEl.textContent = total.toFixed(1);
}}

// ── 废标风险渲染 ──────────────────────────────
(function renderRisks() {{
  const container = document.getElementById("risks-list");
  if (!DATA.risks.length) {{
    renderEmpty(container, "未提取到废标风险。若招标文件确无废标条款，请人工确认；若原文包含，请重新解析投标人须知/废标条款章节。");
    return;
  }}
  const byLevel = ["高","中","低"];
  const sorted = [...DATA.risks].sort((a,b) => byLevel.indexOf(a.level) - byLevel.indexOf(b.level));
  sorted.forEach((r, i) => {{
    const done = getChecked("risks", i);
    const badgeCls = r.level==="高"?"badge-high":r.level==="中"?"badge-mid":"badge-low";
    const row = document.createElement("div");
    row.className = "check-row" + (done?" done":"");
    row.innerHTML = `
      <input type="checkbox" id="risk${{i}}" ${{done?"checked":""}}
        onchange="setChecked('risks',${{i}},this.checked);this.closest('.check-row').classList.toggle('done',this.checked)">
      <div style="flex:1">
        <label for="risk${{i}}" style="cursor:pointer;display:flex;align-items:center;gap:8px;flex-wrap:wrap">
          <span class="badge ${{badgeCls}}">${{r.level}}风险</span>
          <strong>${{r.risk || ""}}</strong>
        </label>
        <div style="font-size:12px;color:var(--gray);margin-top:4px">来源：${{r.source || ""}}</div>
        <div style="font-size:12px;margin-top:2px">规避：${{r.avoidance || ""}}</div>
        <input class="note-input" placeholder="备注…" value="${{getNote('risks',i)}}"
          oninput="setNote('risks',${{i}},this.value)">
      </div>`;
    container.appendChild(row);
  }});
}})();

// ── ★/▲/否决条款渲染 ─────────────────────────
(function renderStarClauses() {{
  const tbody = document.getElementById("star-tbody");
  if (!DATA.starClauses.length) {{
    renderEmptyRow(tbody, 7, "未提取到★/▲/否决条款。若招标文件包含此类要求，请重新解析前附表、投标人须知、评标办法和技术规范章节。");
    return;
  }}
  DATA.starClauses.forEach(c => {{
    const type = c.type || "";
    const cls = type === "▲" ? "badge-mid" : "badge-high";
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${{c.id || ""}}</td>
      <td><span class="badge ${{cls}}">${{type}}</span></td>
      <td>${{c.category || ""}}</td>
      <td>${{c.clause_text || ""}}</td>
      <td>${{c.source || ""}}</td>
      <td>${{c.response_requirement || ""}}</td>
      <td>${{c.evidence_required || ""}}</td>`;
    tbody.appendChild(tr);
  }});
}})();

// ── 资质自查渲染 ──────────────────────────────
(function renderQuals() {{
  const container = document.getElementById("quals-list");
  if (!DATA.mandatory.length) {{
    renderEmpty(container, "未提取到强制资质要求。请确认资格条件章节是否完整；若原文包含，请重新解析资质要求。");
    return;
  }}
  DATA.mandatory.forEach((q, i) => {{
    const done = getChecked("quals", i);
    const row = document.createElement("div");
    row.className = "check-row" + (done?" done":"");
    row.innerHTML = `
      <input type="checkbox" id="qual${{i}}" ${{done?"checked":""}}
        onchange="setChecked('quals',${{i}},this.checked);this.closest('.check-row').classList.toggle('done',this.checked)">
      <div style="flex:1">
        <label for="qual${{i}}" style="cursor:pointer">
          <strong>${{q.category || ""}}</strong>：${{q.requirement || ""}}
        </label>
        <div style="font-size:12px;color:var(--gray);margin-top:4px">
          所需文件：${{q.document || "未载明"}} &nbsp;|&nbsp; 来源：${{q.source || ""}}
        </div>
        <input class="note-input" placeholder="负责人 / 备注…" value="${{getNote('quals',i)}}"
          oninput="setNote('quals',${{i}},this.value)">
      </div>`;
    container.appendChild(row);
  }});

  const bonusTbody = document.getElementById("bonus-tbody");
  if (bonusTbody) {{
    DATA.bonus.forEach(b => {{
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${{b.category||""}}</td><td>${{b.requirement||""}}</td><td>${{b.points||""}}</td>`;
      bonusTbody.appendChild(tr);
    }});
  }}
}})();

// ── SOP 甘特图渲染 ────────────────────────────
(function renderSop() {{
  const container = document.getElementById("sop-list");
  DATA.sop.forEach((task, i) => {{
    const done = getChecked("sop", i);
    const row = document.createElement("div");
    row.className = "gantt-row";
    row.innerHTML = `
      <div class="gantt-date">${{task.date}}</div>
      <div class="gantt-label ${{done?"gantt-done":""}}">
        <input type="checkbox" ${{done?"checked":""}}
          onchange="setChecked('sop',${{i}},this.checked);this.nextElementSibling.classList.toggle('gantt-done',this.checked)"
          style="accent-color:var(--blue);margin-right:8px">
        <span>${{task.label}}</span>
      </div>`;
    container.appendChild(row);
  }});
}})();

// ── 导出未备齐资质 ────────────────────────────
function exportMissing() {{
  const lines = ["未备齐资质清单", "=".repeat(40)];
  DATA.mandatory.forEach((q, i) => {{
    if (!getChecked("quals", i)) {{
      lines.push(`\\n[${{q.category || "未分类"}}]`);
      lines.push(`要求：${{q.requirement || ""}}`);
      lines.push(`文件：${{q.document || "未载明"}}`);
      const note = getNote("quals", i);
      if (note) lines.push(`备注：${{note}}`);
    }}
  }});
  const blob = new Blob([lines.join("\\n")], {{type:"text/plain;charset=utf-8"}});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "未备齐资质清单.txt";
  a.click();
}}

// ── 进度统计 ──────────────────────────────────
function updateProgress() {{
  function pct(group, total) {{
    if (!total) return 0;
    let done = 0;
    for (let i=0; i<total; i++) if (getChecked(group, i)) done++;
    return Math.round(done / total * 100);
  }}
  const rp = pct("risks", DATA.risks.length);
  const qp = pct("quals", DATA.mandatory.length);
  const sp = pct("sop",   DATA.sop.length);

  // 总览进度条
  ["risk","qual","sop"].forEach((g,i) => {{
    const v = [rp,qp,sp][i];
    document.getElementById(g+"-bar").style.width = v+"%";
    document.getElementById(g+"-pct").textContent = v+"%";
  }});
  // 各 tab 内进度条
  document.getElementById("risk-bar2").style.width = rp+"%";
  document.getElementById("sop-bar2").style.width  = sp+"%";

  const rTotal = DATA.risks.length;
  const rDone  = rTotal ? Math.round(rp/100*rTotal) : 0;
  document.getElementById("risk-done-label").textContent = `已规避 ${{rDone}} / ${{rTotal}}`;

  const sTotal = DATA.sop.length;
  const sDone  = sTotal ? Math.round(sp/100*sTotal) : 0;
  document.getElementById("sop-done-label").textContent = `已完成 ${{sDone}} / ${{sTotal}}`;
}}
updateProgress();

// ── 恢复自定义备注 ────────────────────────────
(function restoreNote() {{
  const el = document.getElementById("custom-note");
  if (el) el.value = STATE["custom_note"] || "";
}})();
</script>
</body>
</html>"""
    return html


# ──────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="生成 HTML 投标工作台")
    parser.add_argument("--data",    required=True, help="tender_analysis.json 路径")
    parser.add_argument("--output",  required=True, help="输出 .html 文件路径")
    args = parser.parse_args()

    with open(args.data, encoding="utf-8") as f:
        raw_data = json.load(f)

    data, audit = normalize_analysis(raw_data, include_aliases=True)
    print_audit(audit)
    html = build_html(data, audit)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")

    size_kb = out.stat().st_size / 1024
    print(f"[OK] HTML 工作台已生成 → {args.output}（{size_kb:.1f} KB）")
    if audit.get("missing"):
        print(f"[WARN][需确认] HTML 工作台已生成，但存在 {len(audit['missing'])} 项解析信息缺口，已在总览页明示。", file=sys.stderr)
    if size_kb > 5120:
        print("[WARN] 文件超过 5MB，建议精简内容", file=sys.stderr)


if __name__ == "__main__":
    main()
