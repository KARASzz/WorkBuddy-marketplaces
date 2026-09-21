#!/usr/bin/env python3
"""
D4 报价合规算术校验。
从投标文件文本中提取金额、税率，与招标要求核对，
输出 /tmp/d4_result.json。
无第三方依赖，仅使用标准库。
"""
import argparse, json, re, sys
from pathlib import Path


# ── 金额提取工具 ──────────────────────────────

# 阿拉伯数字金额：支持 1,234,567.89 / 1234567.89 / 123万 / 1.23亿
_NUM_RE = re.compile(
    r'[¥￥RMB人民币]*\s*'
    r'([\d,，]+(?:\.\d+)?)\s*'
    r'(亿|百万|万)?'
    r'\s*(?:元|元整|元人民币)?'
)

# 大写金额
_UPPER_RE = re.compile(
    r'人民币\s*([零壹贰叁肆伍陆柒捌玖拾佰仟万亿元整角分]+)'
)

_UPPER_MAP = {
    '零':0,'壹':1,'贰':2,'叁':3,'肆':4,'伍':5,
    '陆':6,'柒':7,'捌':8,'玖':9,'拾':10,
    '佰':100,'仟':1000,'万':10000,'亿':100000000,
}


def upper_to_num(s: str) -> float:
    """
    将大写金额字符串转为数值，支持「亿/万」分节格式。
    修复：遇到万/亿时，该节内的数字须乘以节单位再累加到总额。
    例：陆佰玖拾万 → 690 × 10000 = 6,900,000
    """
    s = s.replace('元整', '').replace('整', '').replace('元', '').replace('角', '').replace('分', '')
    total        = 0        # 已完成各节的累计
    section      = 0        # 当前节内的小计
    unit         = 1        # 当前节内的位权（1/10/100/1000）
    section_mult = 1        # 当前节的节权（1 / 万 / 亿）
    for ch in reversed(s):
        v = _UPPER_MAP.get(ch)
        if v is None:
            continue
        if v == 100000000:          # 亿
            total        += section * section_mult
            section       = 0
            unit          = 1
            section_mult  = 100000000
        elif v == 10000:            # 万
            total        += section * section_mult
            section       = 0
            unit          = 1
            section_mult  = 10000
        elif v >= 10:               # 拾/佰/仟 —— 节内位权
            unit = v
        else:                       # 零-玖 —— 数字
            section += v * unit
            unit     = 1
    total += section * section_mult  # 最后一节（个位节/亿位节前半段）
    return float(total)


def parse_amount(text: str) -> object:
    """从文本片段提取最可能的金额数值（元）。"""
    m = _NUM_RE.search(text)
    if not m:
        return None
    raw = m.group(1).replace(',', '').replace('，', '')
    try:
        val = float(raw)
    except ValueError:
        return None
    unit = m.group(2) or ''
    if unit == '亿':   val *= 1e8
    elif unit == '百万': val *= 1e6
    elif unit == '万':  val *= 1e4
    return val


def extract_total_price(text: str) -> tuple:
    """
    从投标文件全文提取投标总价。
    优先找「投标总价」「报价合计」「总报价」附近的金额。
    返回 (数值, 原文片段)。
    """
    anchors = ['投标总价', '报价合计', '总报价', '投标报价', '总价（含税）', '含税总价', '投标价格']
    for anchor in anchors:
        idx = text.find(anchor)
        if idx < 0:
            continue
        snippet = text[idx: idx + 120]
        val = parse_amount(snippet)
        if val and val > 0:
            return val, snippet.replace('\n', ' ')[:80]
    return None, ""


def extract_tax_rate(text: str) -> tuple:
    """提取税率百分比，返回 (小数形式, 原文)。"""
    patterns = [
        r'增值税[税率]*[:：]?\s*(\d+(?:\.\d+)?)\s*%',
        r'税率[:：]?\s*(\d+(?:\.\d+)?)\s*%',
        r'含税.*?(\d+(?:\.\d+)?)\s*%',
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return float(m.group(1)) / 100, m.group(0)
    return None, ""


def extract_uppercase_amount(text: str) -> tuple:
    """提取大写金额并转为数值。"""
    m = _UPPER_RE.search(text)
    if m:
        try:
            val = upper_to_num(m.group(1))
            return val, m.group(0)
        except Exception:
            pass
    return None, ""


def parse_max_price(price_str: str) -> object:
    """从限价字符串（如'800万元'）解析数值。"""
    if not price_str:
        return None
    cleaned = price_str.replace('（含税）', '').replace('(含税)', '').strip()
    return parse_amount(cleaned)


# ── 校验逻辑 ──────────────────────────────────

def run_checks(text: str, requirements: dict) -> list:
    results = []
    commercial = requirements.get("commercial", {})

    # ① 报价是否超过最高限价
    max_price_str = commercial.get("max_price", "")
    max_price_val = parse_max_price(max_price_str)
    total_price, total_snippet = extract_total_price(text)

    if max_price_val and total_price:
        passed = total_price <= max_price_val
        results.append({
            "check_id": "P001",
            "name": "报价不超过最高限价",
            "detected": f"¥{total_price:,.2f}（原文：{total_snippet}）",
            "required": f"≤ {max_price_str}（¥{max_price_val:,.2f}）",
            "passed": passed,
            "severity": "废标" if not passed else "通过",
            "suggestion": "" if passed else f"投标总价 ¥{total_price:,.2f} 超出最高限价 ¥{max_price_val:,.2f}，必须重新报价"
        })
    elif max_price_val and not total_price:
        results.append({
            "check_id": "P001",
            "name": "报价不超过最高限价",
            "detected": "未识别到明确投标总价",
            "required": f"≤ {max_price_str}",
            "passed": None,
            "severity": "提醒",
            "suggestion": "未能自动提取投标总价，请人工核对报价是否超过最高限价"
        })

    # ② 大小写金额一致性
    upper_val, upper_snippet = extract_uppercase_amount(text)
    if upper_val and total_price:
        diff = abs(upper_val - total_price)
        passed = diff <= 1.0
        results.append({
            "check_id": "P002",
            "name": "大小写金额一致性",
            "detected": f"大写 ¥{upper_val:,.2f}（{upper_snippet}）/ 数字 ¥{total_price:,.2f}",
            "required": "大写与数字金额误差 ≤ 1 元",
            "passed": passed,
            "severity": "废标" if not passed else "通过",
            "suggestion": "" if passed else f"大写金额 ¥{upper_val:,.2f} 与数字金额 ¥{total_price:,.2f} 不一致（差额 ¥{diff:.2f}），请核实并修正"
        })
    elif not upper_val:
        results.append({
            "check_id": "P002",
            "name": "大小写金额一致性",
            "detected": "未找到大写金额",
            "required": "投标函中应同时写明大写和阿拉伯数字金额",
            "passed": None,
            "severity": "废标",
            "suggestion": "在投标函中补充大写金额，格式示例：人民币壹佰万元整（¥1,000,000.00）"
        })

    # ③ 含税/不含税声明
    tax_rate, tax_snippet = extract_tax_rate(text)
    if tax_rate is not None:
        results.append({
            "check_id": "P003",
            "name": "税率声明",
            "detected": f"税率 {tax_rate*100:.1f}%（原文：{tax_snippet}）",
            "required": "报价需明确含税/不含税及税率",
            "passed": True,
            "severity": "通过",
            "suggestion": ""
        })
    else:
        results.append({
            "check_id": "P003",
            "name": "税率声明",
            "detected": "未检测到明确税率声明",
            "required": "报价需明确含税/不含税及税率",
            "passed": False,
            "severity": "扣分",
            "suggestion": "在报价表备注中补充「以上报价含增值税 X%」或「以上报价不含税，税率 X%」"
        })

    # ④ 投标有效期
    validity_req = commercial.get("validity_period", "")
    if validity_req:
        days_match = re.search(r'(\d+)', validity_req)
        req_days = int(days_match.group(1)) if days_match else None

        bid_validity_pattern = re.compile(r'有效期[^，。\n]{0,10}?(\d+)\s*(?:日历天|天|个工作日)')
        m = bid_validity_pattern.search(text)
        if m:
            bid_days = int(m.group(1))
            passed = (req_days is None) or (bid_days >= req_days)
            results.append({
                "check_id": "P004",
                "name": "投标有效期",
                "detected": f"{bid_days} 天（原文：{m.group(0)}）",
                "required": validity_req,
                "passed": passed,
                "severity": "废标" if not passed else "通过",
                "suggestion": "" if passed else f"投标有效期 {bid_days} 天不足，招标要求 {validity_req}，请修改投标函中的有效期承诺"
            })
        else:
            results.append({
                "check_id": "P004",
                "name": "投标有效期",
                "detected": "未检测到有效期声明",
                "required": validity_req,
                "passed": False,
                "severity": "扣分",
                "suggestion": f"在投标函中补充「本投标文件自开标之日起 {validity_req} 内有效」"
            })

    # ⑤ 分项合计一致性（OPT-S2-01：改为组合条件，三项同时存在才算完整明细）
    # 单项出现可能只是说明文字，三项同时出现才说明存在真实报价明细表格
    has_unit_price = bool(re.search(r'单价', text))
    has_quantity   = bool(re.search(r'数量|工程量', text))
    has_subtotal   = bool(re.search(r'合计|小计', text))
    has_detail     = has_unit_price and has_quantity and has_subtotal

    present = [p for p, v in [("单价", has_unit_price), ("数量", has_quantity), ("合计/小计", has_subtotal)] if v]
    missing = [p for p, v in [("单价", has_unit_price), ("数量", has_quantity), ("合计/小计", has_subtotal)] if not v]
    detected_desc = (
        f"检测到明细字段：{'、'.join(present)}" if present else "未检测到任何明细字段"
    ) + (f"；缺失：{'、'.join(missing)}" if missing else "")

    results.append({
        "check_id": "P005",
        "name": "报价明细完整性",
        "detected": detected_desc,
        "required": "报价表应同时包含单价、数量、合计三类字段",
        "passed": has_detail,
        "severity": "扣分" if not has_detail else "通过",
        "suggestion": "" if has_detail else (
            f"报价表中补充缺失字段（{'、'.join(missing)}），"
            "三类字段同时具备方视为明细完整，避免因报价不透明被质疑"
        )
    })

    return results


def main():
    parser = argparse.ArgumentParser(description="D4 报价合规校验")
    parser.add_argument("--bid",          required=True, help="投标文件全文路径（.txt）")
    parser.add_argument("--requirements", required=True, help="招标要求 JSON 路径")
    parser.add_argument("--output",       required=True, help="输出结果 JSON 路径")
    args = parser.parse_args()

    text         = Path(args.bid).read_text(encoding="utf-8")
    requirements = json.loads(Path(args.requirements).read_text(encoding="utf-8"))
    items        = run_checks(text, requirements)

    stats = {"废标": 0, "扣分": 0, "提醒": 0, "通过": 0}
    for item in items:
        stats[item["severity"]] = stats.get(item["severity"], 0) + 1

    output = {
        "dimension": "D4",
        "name": "报价合规校验",
        "stats": stats,
        "items": items
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] D4 完成：废标 {stats['废标']} 项 | 扣分 {stats['扣分']} 项 | 通过 {stats['通过']} 项 → {args.output}")


if __name__ == "__main__":
    main()
