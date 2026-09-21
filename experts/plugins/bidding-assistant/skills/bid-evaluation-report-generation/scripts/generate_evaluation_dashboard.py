#!/usr/bin/env python3
"""
评标结果可视化大屏生成器（P2-B）。

读取 evaluation_scores.json，生成自包含 HTML 文件，实现"评审结果一屏展示"：
  - 项目概况 + 围串标风险等级卡片
  - 综合评分排名横向条形图
  - 技术 / 商务 / 价格分项对比图
  - 详细评分表格
  - 废标投标人信息
  - 围串标三层检测摘要

依赖：标准库（无第三方包）+ Chart.js CDN（需网络，离线环境可替换为本地 JS）

用法：
    python generate_evaluation_dashboard.py \
        --scores /tmp/evaluation_scores.json \
        --output /mnt/user-data/outputs/某市政务数据中台建设项目_评标大屏.html
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


# ── HTML 模板 ─────────────────────────────────────────────────

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>评标结果一屏展示 — {project_name}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --red:    #D93025;
    --orange: #E8711A;
    --green:  #1A7A4A;
    --blue:   #1565C0;
    --gold:   #C07800;
    --bg:     #F5F6FA;
    --card:   #FFFFFF;
    --border: #E0E0E6;
    --text:   #1C1C2E;
    --sub:    #6B7280;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
    background: var(--bg);
    color: var(--text);
    font-size: 14px;
  }}

  /* ── 顶部标题栏 ── */
  .header {{
    background: linear-gradient(135deg, #0D47A1 0%, #1565C0 100%);
    color: #fff;
    padding: 18px 28px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 2px 8px rgba(0,0,0,.18);
  }}
  .header h1 {{ font-size: 20px; font-weight: 700; letter-spacing: .5px; }}
  .header .meta {{ font-size: 12px; opacity: .85; line-height: 1.8; text-align: right; }}
  .risk-badge {{
    display: inline-block;
    padding: 4px 14px;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 700;
    margin-left: 12px;
    vertical-align: middle;
  }}
  .risk-high   {{ background: #FFEBEE; color: var(--red); }}
  .risk-mid    {{ background: #FFF3E0; color: var(--orange); }}
  .risk-low    {{ background: #E8F5E9; color: var(--green); }}
  .risk-none   {{ background: #E3F2FD; color: var(--blue); }}

  /* ── 布局 ── */
  .container {{ padding: 16px 20px; }}
  .row {{ display: grid; gap: 14px; margin-bottom: 14px; }}
  .row-4 {{ grid-template-columns: repeat(4, 1fr); }}
  .row-2 {{ grid-template-columns: 3fr 2fr; }}
  .row-2b {{ grid-template-columns: 1fr 1fr; }}
  .row-3 {{ grid-template-columns: 2fr 1fr 1fr; }}

  /* ── 卡片 ── */
  .card {{
    background: var(--card);
    border-radius: 10px;
    border: 1px solid var(--border);
    padding: 16px 18px;
    box-shadow: 0 1px 4px rgba(0,0,0,.06);
  }}
  .card-title {{
    font-size: 12px;
    color: var(--sub);
    margin-bottom: 8px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: .5px;
  }}
  .stat-num {{
    font-size: 32px;
    font-weight: 800;
    line-height: 1;
  }}
  .stat-sub {{ font-size: 12px; color: var(--sub); margin-top: 4px; }}
  .num-total  {{ color: var(--blue); }}
  .num-valid  {{ color: var(--green); }}
  .num-invalid{{ color: var(--red); }}
  .num-winner {{ color: var(--gold); }}

  /* ── 图表容器 ── */
  .chart-wrap {{ position: relative; }}
  .chart-wrap canvas {{ width: 100% !important; }}
  .section-title {{
    font-size: 13px;
    font-weight: 700;
    color: var(--text);
    margin-bottom: 12px;
    padding-bottom: 6px;
    border-bottom: 2px solid var(--border);
  }}

  /* ── 评分表格 ── */
  .score-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  .score-table th {{
    background: #EEF2FB;
    padding: 8px 10px;
    text-align: left;
    font-weight: 600;
    color: var(--blue);
    border-bottom: 2px solid #C5D2EF;
  }}
  .score-table td {{
    padding: 8px 10px;
    border-bottom: 1px solid var(--border);
    vertical-align: middle;
  }}
  .score-table tr:hover td {{ background: #F8F9FF; }}
  .rank-1 td {{ background: #FFFDE7; font-weight: 700; }}
  .rank-2 td {{ background: #F8F8F8; }}
  .invalid-row td {{ background: #FFF5F5; color: #999; }}

  /* 分数条 */
  .score-bar-wrap {{ display: flex; align-items: center; gap: 8px; }}
  .score-bar {{
    height: 8px; border-radius: 4px; background: #E0E0E6;
    flex: 1; overflow: hidden;
  }}
  .score-bar-fill {{ height: 100%; border-radius: 4px; }}
  .bar-tech  {{ background: var(--blue); }}
  .bar-comm  {{ background: var(--green); }}
  .bar-price {{ background: var(--gold); }}
  .bar-total {{ background: linear-gradient(90deg, var(--blue), var(--gold)); }}
  .score-val {{ font-size: 13px; font-weight: 700; width: 38px; text-align: right; }}

  /* 废标原因 */
  .disq-list {{ list-style: none; }}
  .disq-list li {{
    padding: 6px 0;
    border-bottom: 1px solid var(--border);
    font-size: 12px;
  }}
  .disq-list li:last-child {{ border-bottom: none; }}
  .disq-name {{ font-weight: 700; color: var(--red); }}
  .disq-reason {{ color: var(--sub); margin-top: 2px; }}

  /* 围串标面板 */
  .collusion-item {{
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 10px 0;
    border-bottom: 1px solid var(--border);
  }}
  .collusion-item:last-child {{ border-bottom: none; }}
  .c-label {{
    font-weight: 700;
    font-size: 12px;
    min-width: 60px;
    padding: 3px 8px;
    border-radius: 4px;
    text-align: center;
  }}
  .c-high {{ background: #FFEBEE; color: var(--red); }}
  .c-mid  {{ background: #FFF3E0; color: var(--orange); }}
  .c-low  {{ background: #E8F5E9; color: var(--green); }}
  .c-none {{ background: #E3F2FD; color: var(--blue); }}
  .c-text {{ font-size: 12px; line-height: 1.6; }}
  .c-text strong {{ color: var(--text); font-size: 13px; }}

  /* 底部 */
  .footer {{
    text-align: center;
    font-size: 11px;
    color: var(--sub);
    padding: 12px;
    margin-top: 8px;
  }}
</style>
</head>
<body>

<!-- ── 顶部标题栏 ─────────────────────────────────────── -->
<div class="header">
  <div>
    <h1>{project_name} — 评标结果一屏展示</h1>
    <div style="font-size:13px;opacity:.9;margin-top:4px;">
      采购单位：{buyer}
      <span class="risk-badge {risk_class}">围串标风险：{collusion_risk}</span>
    </div>
  </div>
  <div class="meta">
    评标日期：{evaluated_at}<br>
    {method_meta}
  </div>
</div>

<div class="container">

<!-- ── 第一行：概况卡片 ──────────────────────────────── -->
<div class="row row-4">
  <div class="card">
    <div class="card-title">参与投标</div>
    <div class="stat-num num-total">{total_count}</div>
    <div class="stat-sub">家投标人</div>
  </div>
  <div class="card">
    <div class="card-title">有效投标</div>
    <div class="stat-num num-valid">{valid_count}</div>
    <div class="stat-sub">通过资格 &amp; 符合性审查</div>
  </div>
  <div class="card">
    <div class="card-title">废标投标</div>
    <div class="stat-num num-invalid">{invalid_count}</div>
    <div class="stat-sub">未通过审查</div>
  </div>
  <div class="card">
    <div class="card-title">暂定第一名</div>
    <div class="stat-num num-winner" style="font-size:20px;line-height:1.3">{winner_name}</div>
    <div class="stat-sub">{winner_detail}</div>
  </div>
</div>

<!-- ── 第二行：排名表 + 分项图 ──────────────────────── -->
<div class="row row-2">
  <!-- 左：排名表 -->
  <div class="card">
    <div class="section-title">{ranking_title}</div>
    <table class="score-table">
      <thead>
        <tr>
          {ranking_headers}
        </tr>
      </thead>
      <tbody>
        {ranking_rows}
        {invalid_rows}
      </tbody>
    </table>
  </div>
  <!-- 右：分项条形图 -->
  <div class="card">
    <div class="section-title">{chart_title}</div>
    <div class="chart-wrap" style="height:260px">
      <canvas id="scoreChart"></canvas>
    </div>
  </div>
</div>

<!-- ── 第三行：废标原因 + 围串标 ───────────────────── -->
<div class="row row-2b">
  <!-- 废标原因 -->
  <div class="card">
    <div class="section-title">废标投标人详情</div>
    {disq_panel}
  </div>
  <!-- 围串标 -->
  <div class="card">
    <div class="section-title">围串标风险检测（L4 / L5 / L6）</div>
    {collusion_panel}
  </div>
</div>

</div><!-- .container -->

<div class="footer">
  本大屏由 RicheeAI 评标报告智能生成系统自动生成 · 仅供评标委员会内部参考 · 不作为最终法律依据
</div>

<!-- ── Chart.js 数据注入 ──────────────────────────────── -->
<script>
const CHART_DATA = {chart_data_json};

// 分项得分对比横向柱状图
(function() {{
  const labels  = CHART_DATA.labels;
  const ctx = document.getElementById('scoreChart');
  if (!ctx) return;
  new Chart(ctx, {{
    type: 'bar',
    data: {{
      labels: labels,
      datasets: CHART_DATA.datasets,
    }},
    options: {{
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{
        legend: {{ position: 'bottom', labels: {{ font: {{ size: 12 }} }} }},
        tooltip: {{
          callbacks: {{
            label: ctx => ` ${{ctx.dataset.label}}: ${{ctx.raw.toFixed(2)}} ${{CHART_DATA.unit}}`,
          }},
        }},
      }},
      scales: {{
        x: {{
          stacked: false,
          suggestedMax: CHART_DATA.suggestedMax,
          ticks: {{ font: {{ size: 11 }} }},
          grid: {{ color: '#EEE' }},
        }},
        y: {{ ticks: {{ font: {{ size: 12 }} }} }},
      }},
    }},
  }});
}})();
</script>
</body>
</html>
"""


# ── 数据处理 ─────────────────────────────────────────────────

def fmt_price(val) -> str:
    if val is None:
        return "—"
    if isinstance(val, (int, float)):
        if val >= 1e8:
            return f"{val/1e8:.2f} 亿元"
        if val >= 1e4:
            return f"{val/1e4:.2f} 万元"
        return f"{val:.2f} 元"
    return str(val)


def score_bar(value: float, max_val: float, css_class: str) -> str:
    pct = min(100, round(value / max_val * 100, 1)) if max_val > 0 else 0
    return (
        f'<div class="score-bar-wrap">'
        f'<div class="score-bar">'
        f'<div class="score-bar-fill {css_class}" style="width:{pct}%"></div>'
        f'</div>'
        f'<span class="score-val">{value:.1f}</span>'
        f'</div>'
    )


def build_ranking_rows(ranking: list, weights: dict, method: str) -> str:
    wt = weights.get("technical", 70)
    wc = weights.get("commercial", 10)
    wp = weights.get("price", 20)
    rows = []
    for item in ranking:
        rank  = item.get("rank", "—")
        name  = item.get("name", "—")
        sc    = item.get("scores", {})
        row_cls = "rank-1" if rank == 1 else ("rank-2" if rank == 2 else "")
        prefix = (
            f'<tr class="{row_cls}">'
            f'<td style="text-align:center;font-weight:700;color:{"#C07800" if rank==1 else "#666"}">'
            f'{"第1" if rank==1 else rank}</td><td>{name}</td>'
        )
        if method == "comprehensive_scoring":
            total = sc.get("total", 0)
            cells = (
                f'<td>{score_bar(sc.get("technical", 0), wt, "bar-tech")}</td>'
                f'<td>{score_bar(sc.get("commercial", 0), wc, "bar-comm")}</td>'
                f'<td>{score_bar(sc.get("price", 0), wp, "bar-price")}</td>'
                f'<td>{score_bar(total, wt + wc + wp, "bar-total")}</td>'
            )
        else:
            evaluated = item.get("evaluated_price")
            basis = item.get("ranking_value")
            basis_label = "经评审价升序" if method == "lowest_evaluated_price" else "距基准价偏差升序"
            cells = (
                f'<td>{fmt_price(evaluated)}</td>'
                f'<td>{fmt_price(basis)}</td>'
                f'<td>{basis_label}</td>'
            )
        rows.append(prefix + cells + '</tr>')
    return "\n".join(rows)


def build_invalid_rows(bidders: list, total_columns: int = 6) -> str:
    invalids = [b for b in bidders if not b.get("is_valid", True)]
    rows = []
    for b in invalids:
        name    = b.get("name", "—")
        reasons = b.get("disqualify_reasons", [])
        reason1 = reasons[0] if reasons else "废标"
        rows.append(
            f'<tr class="invalid-row">'
            f'<td style="text-align:center">废标</td>'
            f'<td>{name}</td>'
            f'<td colspan="{total_columns - 2}" style="color:#D93025;font-size:12px">'
            f'{reason1}{"等" if len(reasons)>1 else ""}'
            f'（共 {len(reasons)} 条废标原因）</td>'
            f'</tr>'
        )
    return "\n".join(rows)


def build_disq_panel(bidders: list) -> str:
    invalids = [b for b in bidders if not b.get("is_valid", True)]
    if not invalids:
        return '<p style="color:#6B7280;font-size:13px">无废标投标人，所有参与者均通过审查。</p>'
    items = []
    for b in invalids:
        name    = b.get("name", "—")
        reasons = b.get("disqualify_reasons", [])
        reason_html = "".join(
            f'<div class="disq-reason">• {r}</div>' for r in reasons[:4]
        )
        if len(reasons) > 4:
            reason_html += f'<div class="disq-reason" style="color:#999">…另 {len(reasons)-4} 条</div>'
        items.append(
            f'<li><span class="disq-name">{name}</span>{reason_html}</li>'
        )
    return f'<ul class="disq-list">{"".join(items)}</ul>'


def _c_level(val, high_thr=60, mid_thr=25) -> str:
    """根据数值返回风险等级 CSS 类和文字。"""
    if isinstance(val, str):
        return ("c-high", "高风险") if "高" in val else (
               ("c-mid", "中风险") if "中" in val else ("c-low", "低风险"))
    if val >= high_thr:
        return "c-high", "高风险"
    if val >= mid_thr:
        return "c-mid", "中风险"
    return "c-low", "低风险"


def build_collusion_panel(collusion: dict) -> str:
    if not collusion:
        return '<p style="color:#6B7280;font-size:13px">未提供围串标检测数据。</p>'

    risk_level = collusion.get("risk_level", "—")
    total_score = collusion.get("total_score", None)
    l4 = collusion.get("l4_same_error", {})
    l5 = collusion.get("l5_price_pattern", {})
    l6 = collusion.get("l6_metadata", {})

    items = []

    # 总览
    r_cls, r_label = _c_level(risk_level)
    score_txt = f"综合风险分 {total_score}" if total_score is not None else ""
    items.append(
        f'<div class="collusion-item">'
        f'<span class="c-label {r_cls}">总体</span>'
        f'<div class="c-text"><strong>风险等级：{risk_level}</strong> {score_txt}</div>'
        f'</div>'
    )

    # L4
    if l4:
        detected = l4.get("detected", False)
        cls = "c-high" if detected else "c-low"
        detail = l4.get("summary", l4.get("detail", ""))
        label = "L4 同错"
        desc = f"同错性{'已检出' if detected else '未检出'}" + (f"：{detail}" if detail else "")
        items.append(
            f'<div class="collusion-item">'
            f'<span class="c-label {cls}">{label}</span>'
            f'<div class="c-text">{desc}</div>'
            f'</div>'
        )

    # L5
    if l5:
        detected = l5.get("detected", False)
        cls = "c-high" if detected else "c-low"
        cv = l5.get("cv", None)
        pattern = l5.get("pattern", "")
        cv_txt = f"  CV={cv:.3f}" if isinstance(cv, float) else ""
        desc = f"报价规律{'已检出（' + pattern + '）' if detected else '未检出'}{cv_txt}"
        items.append(
            f'<div class="collusion-item">'
            f'<span class="c-label {cls}">L5 报价</span>'
            f'<div class="c-text">{desc}</div>'
            f'</div>'
        )

    # L6
    if l6:
        signals = l6.get("signals", [])
        high_cnt = sum(1 for s in signals if s.get("level") == "高风险")
        cls = "c-high" if high_cnt > 0 else ("c-mid" if signals else "c-low")
        desc = f"元数据异常信号 {len(signals)} 条" + (f"（高风险 {high_cnt} 条）" if high_cnt else "")
        if not signals:
            desc = "元数据未发现异常"
        items.append(
            f'<div class="collusion-item">'
            f'<span class="c-label {cls}">L6 元数据</span>'
            f'<div class="c-text">{desc}</div>'
            f'</div>'
        )

    return "\n".join(items)


def build_chart_data(ranking: list, method: str, weights: dict) -> dict:
    """构建与评标办法一致的 Chart.js 数据集。"""
    labels = [item.get("name", "—") for item in ranking]
    colors = [
        "rgba(21,101,192,0.75)",
        "rgba(26,122,74,0.75)",
        "rgba(192,120,0,0.75)",
    ]
    if method == "comprehensive_scoring":
        specs = (("技术分", "technical"), ("商务分", "commercial"), ("价格分", "price"))
        datasets = []
        for (label, key), color in zip(specs, colors):
            datasets.append({
                "label": label,
                "data": [round((item.get("scores") or {}).get(key, 0), 2) for item in ranking],
                "backgroundColor": color,
                "borderRadius": 4,
            })
        suggested_max = sum(float(weights.get(key, 0) or 0) for key in ("technical", "commercial", "price"))
        return {"labels": labels, "datasets": datasets, "unit": "分", "suggestedMax": suggested_max or 100}

    values = [round(float(item.get("evaluated_price") or 0), 2) for item in ranking]
    return {
        "labels": labels,
        "datasets": [{
            "label": "经评审/排序价格",
            "data": values,
            "backgroundColor": colors[2],
            "borderRadius": 4,
        }],
        "unit": "元",
        "suggestedMax": max(values, default=0) * 1.1 or 1,
    }


def risk_css(level: str) -> str:
    if not level or level == "—":
        return "risk-none"
    if "高" in level:
        return "risk-high"
    if "中" in level:
        return "risk-mid"
    return "risk-low"


# ── 主函数 ────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="评标结果可视化大屏生成器")
    parser.add_argument("--scores", required=True,
                        help="evaluation_scores.json 路径")
    parser.add_argument("--output", default="/tmp/评标大屏.html",
                        help="输出 HTML 路径（默认 /tmp/评标大屏.html）")
    args = parser.parse_args()

    p = Path(args.scores)
    if not p.exists():
        print(f"[error] 找不到评分文件：{args.scores}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(p.read_text(encoding="utf-8"))

    project_name = data.get("project_name", "未命名项目")
    buyer        = data.get("buyer", "—")
    evaluated_at = data.get("evaluated_at",
                            datetime.now().strftime("%Y-%m-%d %H:%M"))
    weights      = data.get("scoring_weights", {"technical": 70, "commercial": 10, "price": 20})
    base_price   = fmt_price(data.get("base_price"))
    method       = data.get("evaluation_method", "comprehensive_scoring")
    method_text  = data.get("evaluation_method_text", method)
    calculation_status = data.get("calculation_status", "completed")
    bidders      = data.get("bidders", [])
    ranking      = data.get("ranking", [])
    collusion    = data.get("collusion_result", {})
    collusion_risk = data.get("collusion_risk", "—")

    total_count  = data.get("total_count", len(bidders))
    valid_count  = data.get("valid_count", len(ranking))
    invalid_count = total_count - valid_count

    if calculation_status == "blocked":
        winner_name = "自动排序已阻断"
        winner_detail = "；".join(data.get("calculation_warnings", [])) or "评标参数不足"
    elif ranking:
        winner = ranking[0]
        winner_name  = winner.get("name", "—")
        if method == "comprehensive_scoring":
            winner_detail = f"{winner.get('total', 0):.2f} 分"
        else:
            winner_detail = f"依据：{data.get('ranking_basis', '—')}"
    else:
        winner_name  = "无有效投标人"
        winner_detail = "—"

    wt = float(weights.get("technical") or 0)
    wc = float(weights.get("commercial") or 0)
    wp = float(weights.get("price") or 0)

    is_comprehensive = method == "comprehensive_scoring"
    if is_comprehensive:
        method_meta = (
            f"评标办法：{method_text}<br>"
            f"评分权重：技术 {wt}分 / 商务 {wc}分 / 价格 {wp}分<br>"
            f"评标基准价：{base_price}"
        )
        ranking_title = "综合评分排名"
        ranking_headers = (
            '<th style="width:36px">排名</th><th>投标人</th>'
            f'<th style="width:80px">技术分<br><small style="color:#888;font-weight:400">/{wt}</small></th>'
            f'<th style="width:80px">商务分<br><small style="color:#888;font-weight:400">/{wc}</small></th>'
            f'<th style="width:80px">价格分<br><small style="color:#888;font-weight:400">/{wp}</small></th>'
            '<th style="width:130px">综合总分</th>'
        )
        chart_title = "分项得分对比"
        total_columns = 6
    else:
        method_meta = (
            f"评标办法：{method_text}<br>"
            f"排序依据：{data.get('ranking_basis', '未生成')}<br>"
            f"结构化基准价：{base_price}"
        )
        ranking_title = "价格型评审排序"
        ranking_headers = (
            '<th style="width:50px">排名</th><th>投标人</th>'
            '<th>经评审/排序价格</th><th>排序值</th><th>排序依据</th>'
        )
        chart_title = "经评审/排序价格对比"
        total_columns = 5

    chart_data = build_chart_data(ranking, method, weights)
    ranking_rows = build_ranking_rows(ranking, weights, method)
    if calculation_status == "blocked":
        warning_text = "；".join(data.get("calculation_warnings", [])) or "关键参数不足"
        ranking_rows = f'<tr><td colspan="{total_columns}" style="color:#D93025">自动排序已阻断：{warning_text}</td></tr>'
    invalid_rows  = build_invalid_rows(bidders, total_columns)
    disq_panel    = build_disq_panel(bidders)
    collusion_panel = build_collusion_panel(collusion)

    html = _HTML_TEMPLATE.format(
        project_name    = project_name,
        buyer           = buyer,
        evaluated_at    = evaluated_at,
        method_meta     = method_meta,
        risk_class      = risk_css(collusion_risk),
        collusion_risk  = collusion_risk,
        ranking_title   = ranking_title,
        ranking_headers = ranking_headers,
        chart_title     = chart_title,
        total_count     = total_count,
        valid_count     = valid_count,
        invalid_count   = invalid_count,
        winner_name     = winner_name,
        winner_detail   = winner_detail,
        ranking_rows    = ranking_rows,
        invalid_rows    = invalid_rows,
        disq_panel      = disq_panel,
        collusion_panel = collusion_panel,
        chart_data_json = json.dumps(chart_data, ensure_ascii=False),
    )

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    size_kb = out.stat().st_size // 1024
    print(f"[done] 评标大屏已生成：{out}（{size_kb} KB）")
    print(f"       投标人：{total_count} 家  有效：{valid_count}  废标：{invalid_count}")
    if calculation_status == "blocked":
        print("       自动排序已阻断")
    elif ranking:
        print(f"       暂定第一名：{winner_name}（{winner_detail}）")
    else:
        print("       无有效投标人，建议废标重招")


if __name__ == "__main__":
    main()
