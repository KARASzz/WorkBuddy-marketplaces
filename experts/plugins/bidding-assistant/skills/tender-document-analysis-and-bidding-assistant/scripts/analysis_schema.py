#!/usr/bin/env python3
"""Tender analysis schema normalization and completeness checks."""

from __future__ import annotations

import copy
import sys


EMPTY_TEXT = {"", "文件未载明", "未载明", "暂无", "无", "-", "—", "N/A", "n/a", "null", "None"}


FIELD_ALIASES = {
    "project_overview": ["project_overview", "overview", "project", "project_info"],
    "dates": ["dates", "key_dates", "timeline"],
    "qualifications": ["qualifications", "qualification_requirements"],
    "scoring": ["scoring", "scoring_criteria", "evaluation_criteria"],
    "risks": ["risks", "disqualification_risks", "fatal_risks"],
    "star_clauses": ["star_clauses", "star_clause_list", "mandatory_clauses", "key_clauses"],
    "commercial": ["commercial", "commercial_requirements", "business_requirements"],
    "strategy": ["strategy", "bid_strategy_notes", "strategy_notes"],
}

STRATEGY_KEY_ALIASES = {
    "differentiation": [
        "differentiation", "key_points", "strengths", "competitive_advantages",
        "differentiators", "差异化竞争点", "竞争点", "核心优势", "优势",
    ],
    "pricing": [
        "pricing", "price_strategy", "pricing_strategy", "quotation_strategy",
        "价格策略", "报价策略",
    ],
    "risks": [
        "risks", "weaknesses", "risk_alerts", "risk_tips", "main_risks",
        "风险提示", "主要风险", "风险",
    ],
    "document_focus": [
        "document_focus", "actions", "priorities", "compilation_focus",
        "response_focus", "编制重点", "文件要求", "行动项", "优先事项",
    ],
}

EVALUATION_METHOD_LABELS = {
    "comprehensive_scoring": "综合评分法",
    "lowest_evaluated_price": "经评审的最低投标价法",
    "reasonable_low_price": "合理低价法",
    "other": "其他评标办法",
    "unknown": "评标办法待确认",
}

STAR_CLAUSE_TYPES = {"★", "▲", "否决", "强制"}
STAR_CLAUSE_TYPE_ALIASES = {
    "★": "★",
    "★条款": "★",
    "星号": "★",
    "星号条款": "★",
    "star": "★",
    "▲": "▲",
    "▲条款": "▲",
    "三角": "▲",
    "重要": "▲",
    "重要条款": "▲",
    "否决": "否决",
    "否决条款": "否决",
    "无效投标": "否决",
    "废标": "否决",
    "强制": "强制",
    "强制条款": "强制",
    "实质性要求": "强制",
}

LEGACY_ALIASES = {
    "project_overview": "overview",
    "dates": "key_dates",
    "scoring": "scoring_criteria",
    "risks": "disqualification_risks",
    "star_clauses": "star_clause_list",
    "commercial": "commercial_requirements",
    "strategy": "bid_strategy_notes",
}


def is_blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() in EMPTY_TEXT
    if isinstance(value, (list, tuple, set)):
        return len(value) == 0
    if isinstance(value, dict):
        return not any(not is_blank(v) for v in value.values())
    return False


def first_non_blank(data: dict, keys: list) -> tuple:
    for key in keys:
        if key in data and not is_blank(data.get(key)):
            return key, data.get(key)
    return "", None


def _display_text(value) -> str:
    """Turn common LLM list/dict shapes into deterministic plain text."""
    if is_blank(value):
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple, set)):
        parts = [_display_text(item) for item in value]
        return "\n".join(f"- {part}" for part in parts if part)
    if isinstance(value, dict):
        preferred = _first_text(value, ["text", "content", "description", "advice", "suggestion"])
        if preferred:
            return preferred
        parts = []
        for key, item in value.items():
            text = _display_text(item)
            if text:
                parts.append(f"{key}：{text}")
        return "\n".join(parts)
    return str(value).strip()


def normalize_strategy(value, repairs=None) -> dict:
    if isinstance(value, dict):
        normalized = {}
        for target_key, aliases in STRATEGY_KEY_ALIASES.items():
            source_key, source_value = first_non_blank(value, aliases)
            if not source_key:
                continue
            text = _display_text(source_value)
            if text:
                normalized[target_key] = text
                if repairs is not None and source_key != target_key:
                    repairs.append({
                        "canonical": f"strategy.{target_key}",
                        "source": f"strategy.{source_key}",
                        "message": (
                            f"检测到策略字段键名不匹配，已将 strategy.{source_key} "
                            f"映射为 strategy.{target_key}"
                        ),
                    })
        return normalized
    if isinstance(value, list):
        text = _display_text(value)
        return {"document_focus": text} if text else {}
    if isinstance(value, str) and value.strip():
        return {"document_focus": value.strip()}
    return {}


def _evaluation_method_code(value) -> tuple[str, str]:
    """Return a stable method code and the original human-readable description."""
    if isinstance(value, dict):
        code = _first_text(value, ["code", "type", "method_code"])
        text = _first_text(value, ["name", "method", "label", "description", "rule"])
        value = code or text
    text = _display_text(value)
    lowered = text.lower().replace("-", "_").replace(" ", "_")
    if lowered in EVALUATION_METHOD_LABELS:
        return lowered, text or EVALUATION_METHOD_LABELS[lowered]
    if "经评审的最低投标价" in text or "最低评标价" in text or "lowest_evaluated" in lowered:
        return "lowest_evaluated_price", text
    if "合理低价" in text or "reasonable_low" in lowered:
        return "reasonable_low_price", text
    if any(token in text for token in ("综合评分", "综合评估", "综合评价")) or "comprehensive" in lowered:
        return "comprehensive_scoring", text
    if text:
        return "other", text
    return "unknown", ""


def normalize_scoring(value, top_level_method=None, repairs=None) -> dict:
    """Normalize scoring while preserving method-specific fields for template routing."""
    if isinstance(value, dict):
        scoring = copy.deepcopy(value)
    elif not is_blank(value):
        scoring = {"evaluation_method_text": _display_text(value)}
    else:
        scoring = {}

    method_value = first_non_blank(
        scoring,
        ["evaluation_method", "evaluation_method_type", "method", "method_name", "评标办法"],
    )[1]
    if is_blank(method_value):
        method_value = top_level_method

    code, original_text = _evaluation_method_code(method_value)
    tech_items = ((scoring.get("technical_score") or {}).get("items") or [])
    comm_items = ((scoring.get("commercial_score") or {}).get("items") or [])
    price_score = scoring.get("price_score") or {}
    if code == "unknown" and (tech_items or comm_items or not is_blank(price_score)):
        code = "comprehensive_scoring"
        original_text = EVALUATION_METHOD_LABELS[code]

    previous = scoring.get("evaluation_method")
    scoring["evaluation_method"] = code
    scoring["evaluation_method_text"] = (
        _display_text(scoring.get("evaluation_method_text"))
        or original_text
        or EVALUATION_METHOD_LABELS[code]
    )
    if repairs is not None and not is_blank(previous) and previous != code:
        repairs.append({
            "canonical": "scoring.evaluation_method",
            "source": "scoring.evaluation_method",
            "message": f"已将评标办法“{_display_text(previous)}”归一化为 {code}",
        })
    return scoring


def _first_text(item: dict, keys: list[str], default: str = "") -> str:
    for key in keys:
        value = item.get(key)
        if not is_blank(value):
            return str(value).strip()
    return default


def _infer_star_clause_type(clause_text: str) -> str | None:
    if "★" in clause_text:
        return "★"
    if "▲" in clause_text:
        return "▲"
    if any(word in clause_text for word in ("否决", "无效投标", "废标", "不予通过", "作无效处理")):
        return "否决"
    if any(word in clause_text for word in ("必须", "不得", "应当", "须", "不接受", "不得偏离", "实质性响应")):
        return "强制"
    return None


def normalize_star_clauses(value, repairs=None, issues=None) -> list:
    """Normalize ★/▲/否决条款 from common LLM output shapes."""
    if isinstance(value, dict):
        if isinstance(value.get("items"), list):
            value = value["items"]
        elif isinstance(value.get("clauses"), list):
            value = value["clauses"]
        else:
            value = list(value.values())
    if not isinstance(value, list):
        return []

    normalized = []
    for idx, raw in enumerate(value, 1):
        if isinstance(raw, str):
            raw = {"clause_text": raw}
        if not isinstance(raw, dict):
            continue
        clause_text = _first_text(raw, ["clause_text", "clause", "requirement", "text", "content"])
        if is_blank(clause_text):
            continue
        raw_type = _first_text(raw, ["type", "mark", "level", "tag"], "")
        clause_type = STAR_CLAUSE_TYPE_ALIASES.get(raw_type.lower()) if raw_type else None
        inferred_type = _infer_star_clause_type(clause_text)
        if clause_type is None and inferred_type is not None:
            clause_type = inferred_type
            if repairs is not None:
                repairs.append({
                    "canonical": f"star_clauses[{idx - 1}].type",
                    "source": raw_type or "clause_text",
                    "message": f"已根据条款原文将类型“{raw_type or '未填写'}”归一化为 {clause_type}",
                })
        if clause_type not in STAR_CLAUSE_TYPES:
            if issues is not None:
                issues.append({
                    "section": "★/▲/否决条款",
                    "field": f"star_clauses[{idx - 1}].type",
                    "severity": "critical",
                    "message": (
                        f"条款类型“{raw_type or '未填写'}”不在 ★/▲/否决/强制 白名单，"
                        "且无法从原文可靠识别；该条款未进入强制风险，请人工复核。"
                    ),
                })
            continue

        normalized.append({
            "id": _first_text(raw, ["id", "编号"], f"S{idx}"),
            "type": clause_type,
            "category": _first_text(raw, ["category", "类别"], "其他"),
            "clause_text": clause_text,
            "source": _first_text(raw, ["source", "出处", "location"], "文件未载明"),
            "response_requirement": _first_text(
                raw, ["response_requirement", "响应要求", "response"], "须在投标文件中明确响应"
            ),
            "evidence_required": _first_text(
                raw, ["evidence_required", "证明材料", "evidence", "document"], "按招标文件要求提供证明材料"
            ),
        })
    return normalized


def sync_star_clauses_to_risks(data: dict) -> None:
    """Write ★/否决/强制条款 into risks[] so downstream checks can reuse them."""
    risks = data.get("risks")
    if not isinstance(risks, list):
        risks = []
    existing_keys = {
        str(r.get("star_clause_id") or r.get("risk") or "") for r in risks if isinstance(r, dict)
    }

    for clause in data.get("star_clauses", []) or []:
        clause_type = str(clause.get("type", ""))
        if clause_type not in STAR_CLAUSE_TYPES:
            continue
        if clause_type == "▲":
            continue
        source_label = {"★": "★条款", "否决": "否决条款", "强制": "强制条款"}[clause_type]
        key = str(clause.get("id") or clause.get("clause_text"))
        if key in existing_keys:
            continue
        text = str(clause.get("clause_text", ""))
        summary = text[:60] + ("..." if len(text) > 60 else "")
        risks.append({
            "risk": f"{source_label}未响应：{summary}",
            "source": source_label,
            "level": "高",
            "avoidance": "在投标文件中逐条响应，写明完全满足，并提供对应证明材料或承诺函",
            "star_clause_id": clause.get("id", ""),
            "source_clause": clause.get("source", ""),
        })
        existing_keys.add(key)
    data["risks"] = risks


def normalize_analysis(raw: dict, include_aliases: bool = True) -> tuple:
    """Return (normalized_data, audit). Repairs known key-name drift in-place on a copy."""
    data = copy.deepcopy(raw or {})
    repairs = []

    for canonical, aliases in FIELD_ALIASES.items():
        found_key, found_value = first_non_blank(data, aliases)
        if found_key and found_key != canonical and is_blank(data.get(canonical)):
            data[canonical] = found_value
            repairs.append({
                "canonical": canonical,
                "source": found_key,
                "message": f"检测到字段键名不匹配，已将 {found_key} 映射为 {canonical}",
            })
        elif canonical not in data:
            default = [] if canonical in {"dates", "risks", "star_clauses"} else {}
            data[canonical] = default

    data["strategy"] = normalize_strategy(data.get("strategy"), repairs)
    data["scoring"] = normalize_scoring(data.get("scoring"), data.get("evaluation_method"), repairs)
    schema_issues = []
    data["star_clauses"] = normalize_star_clauses(
        data.get("star_clauses"), repairs=repairs, issues=schema_issues
    )
    sync_star_clauses_to_risks(data)

    if include_aliases:
        for canonical, alias in LEGACY_ALIASES.items():
            if not is_blank(data.get(canonical)) and is_blank(data.get(alias)):
                data[alias] = data[canonical]

    missing = schema_issues + analyze_completeness(data)
    audit = {"repairs": repairs, "missing": missing}
    return data, audit


def analyze_completeness(data: dict) -> list:
    issues = []

    def add(section: str, field: str, message: str, severity: str = "warning"):
        issues.append({
            "section": section,
            "field": field,
            "severity": severity,
            "message": message,
        })

    ov = data.get("project_overview") or {}
    if is_blank(ov.get("project_name")):
        add("项目概况", "project_name", "未识别项目名称，请确认招标文件首页/公告中是否包含项目名称。", "critical")
    if is_blank(ov.get("buyer")):
        add("项目概况", "buyer", "未识别招标人/采购人，请确认输入文件是否包含采购人信息。")

    if is_blank(data.get("dates")):
        add("时间节点", "dates", "未提取到关键时间节点，请确认招标公告、投标人须知或开标安排是否完整。", "critical")

    qualifications = data.get("qualifications") or {}
    if is_blank(qualifications.get("mandatory")) and is_blank(qualifications.get("bonus")):
        add("资质要求", "qualifications", "未提取到资质要求，请确认资格条件章节是否已输入。")

    scoring = data.get("scoring") or {}
    method = scoring.get("evaluation_method", "unknown")
    tech_items = ((scoring.get("technical_score") or {}).get("items") or [])
    comm_items = ((scoring.get("commercial_score") or {}).get("items") or [])
    price_score = scoring.get("price_score") or {}
    method_specific = any(not is_blank(scoring.get(key)) for key in (
        "award_rule", "initial_review", "preliminary_review", "detailed_review",
        "price_adjustments", "price_adjustment_rules", "benchmark_formula",
    ))
    if method == "comprehensive_scoring" and is_blank(tech_items) and is_blank(comm_items) and is_blank(price_score):
        add("评分标准", "scoring", "未提取到评分标准，请确认评标办法/评分细则章节是否已输入。", "critical")
    elif method in {"lowest_evaluated_price", "reasonable_low_price"} and not method_specific:
        add(
            "评标办法",
            "scoring.method_details",
            "已识别价格型评标办法，但未提取中标规则、评审阶段或价格调整规则；工作台将使用资格条件兜底展示，请人工复核评标办法原文。",
        )
    elif method in {"unknown", "other"} and is_blank(tech_items) and is_blank(comm_items) and is_blank(price_score):
        add("评标办法", "scoring.evaluation_method", "未能确认评标办法类型，请重新解析评标办法章节。", "critical")

    if is_blank(data.get("risks")):
        add("废标风险", "risks", "未提取到废标风险；若招标文件确无废标条款，请人工确认，否则需重新解析投标人须知。")

    if is_blank(data.get("star_clauses")):
        add("★/▲/否决条款", "star_clauses", "未提取到★/▲/否决条款；若招标文件确无此类条款，请人工确认。")

    commercial = data.get("commercial") or {}
    if is_blank(commercial):
        add("商务条款", "commercial", "未提取到商务条款，请确认合同条款、限价、保证金或付款方式章节是否已输入。")

    return issues


def audit_lines(audit: dict) -> list:
    lines = []
    for repair in audit.get("repairs", []):
        lines.append("[FIX] " + repair["message"])
    for issue in audit.get("missing", []):
        prefix = "[WARN]" if issue.get("severity") != "critical" else "[WARN][需确认]"
        lines.append(f"{prefix} {issue['section']}：{issue['message']}")
    return lines


def print_audit(audit: dict) -> None:
    for line in audit_lines(audit):
        print(line, file=sys.stderr)
