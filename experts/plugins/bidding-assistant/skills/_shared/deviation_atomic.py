#!/usr/bin/env python3
"""技术/商务偏离表的原子化与响应充分性规则。"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


TEXT_KEYS = (
    "requirement_text", "clause_text", "requirement", "criteria", "content",
    "parameter", "text", "name", "description",
)
RESPONSE_KEYS = ("response_text", "response", "bid_response", "offered_value", "answer")
PLACEHOLDER_RE = re.compile(r"(?:待填写|待补充|待确认|此处填写|P__|\$\{[^}]+\}|<[^<>]+>)", re.I)
GENERIC_CORE = {
    "响应", "完全响应", "全部响应", "完全满足", "全部满足", "满足", "符合",
    "无偏离", "无差异", "同意", "接受", "遵守", "按招标文件执行",
    "按招标文件要求执行", "严格按招标文件执行", "详见投标文件", "详见技术方案",
}
DOMAIN_TERMS = (
    "投标有效期", "提交投标文件截止", "交付期", "交货期", "服务期", "质保期",
    "付款条件", "付款方式", "验收标准", "验收要求", "税率", "投标保证金",
    "履约保证金", "合同期限", "交付地点", "交货地点", "违约责任", "发票",
    "量程", "精度", "分辨率", "检出限", "重复性", "线性", "防护等级",
    "工作温度", "工作湿度", "响应时间", "测量范围", "输出信号", "通信协议",
)
ANCHOR_PATTERNS = (
    re.compile(r"自[^，。；;]{2,40}?(?:之日起|之日|日起)"),
    re.compile(r"以[^，。；;]{2,40}?(?:为准|起算)"),
    re.compile(r"(?:不迟于|不得晚于|不少于|不低于|不高于|不超过)[^，。；;]{1,30}"),
)
FACT_RE = re.compile(
    r"(?:[≤≥<>±]?\s*\d+(?:\.\d+)?(?:\s*[-~～—至]\s*\d+(?:\.\d+)?)?\s*"
    r"(?:%|％|天|日|日历天|年|个月|月|小时|分钟|秒|元|万元|亿元|V|kV|mV|A|mA|"
    r"W|kW|Hz|kHz|MHz|GHz|mm|cm|m|km|mg|g|kg|μg|ug|ppm|ppb|℃|°C|"
    r"mg/m3|mg/m³|m3/h|m³/h|MPa|kPa|Pa))"
    r"|(?:[A-Za-z]{1,8}[-/]?\d{1,8}(?:[-/.][A-Za-z0-9]+)*)",
    re.I,
)


def load_json(path: str | Path | None) -> dict:
    if not path:
        return {}
    target = Path(path).expanduser()
    if not target.is_file():
        return {}
    return json.loads(target.read_text(encoding="utf-8"))


def normalize_text(value: Any) -> str:
    text = str(value or "").lower()
    return re.sub(r"[\s\u3000，。；、：:（）()【】\[\]《》<>“”‘’\"'·,.;!?！？_-]+", "", text)


def first_text(item: Any, keys: tuple[str, ...] = TEXT_KEYS) -> str:
    if isinstance(item, str):
        return item.strip()
    if not isinstance(item, dict):
        return ""
    for key in keys:
        value = item.get(key)
        if value not in (None, "", [], {}):
            if isinstance(value, (dict, list)):
                return json.dumps(value, ensure_ascii=False)
            return str(value).strip()
    return ""


def _strip_list_prefix(text: str) -> str:
    return re.sub(
        r"^\s*(?:[-•●▪◆★▲]+|\d{1,4}[.、．]|[（(]\d{1,4}[)）]|"
        r"[一二三四五六七八九十百]+[、.．])\s*", "", text,
    ).strip()


def _has_concrete_fact(text: str) -> bool:
    return bool(FACT_RE.search(text) or any(term in text for term in DOMAIN_TERMS))


def split_atomic_text(text: str, category: str) -> list[str]:
    """按强分隔符拆分；技术参数逗号两侧均有具体要素时继续拆分。"""
    source = re.sub(r"。\s*(?=(?:\d{1,4}[.、．]|[（(]\d+[)）]))", "；", str(text or ""))
    coarse = re.split(r"[\r\n；;]+", source)
    parts: list[str] = []
    for chunk in coarse:
        numbered = re.split(
            r"(?=(?:\d{1,4}[.、．]|[（(]\d{1,4}[)）])\s*)", chunk.strip()
        )
        for item in numbered:
            cleaned = _strip_list_prefix(item)
            if cleaned:
                parts.append(cleaned.rstrip("。；;"))

    if category == "technical":
        refined: list[str] = []
        for part in parts:
            candidates = [_strip_list_prefix(x) for x in re.split(r"[，,]+", part) if x.strip()]
            if len(candidates) > 1 and sum(_has_concrete_fact(x) for x in candidates) >= 2:
                refined.extend(candidates)
            else:
                refined.append(part)
        parts = refined

    result, seen = [], set()
    for part in parts:
        key = normalize_text(part)
        if len(key) < 2 or key in seen:
            continue
        seen.add(key)
        result.append(part.strip())
    return result


def _iter_values(value: Any) -> list[Any]:
    if value in (None, "", [], {}):
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        if isinstance(value.get("items"), list):
            return value["items"]
        return [value]
    return [value]


def _get_nested(data: dict, path: tuple[str, ...]) -> Any:
    value: Any = data
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _source_specs(category: str) -> list[tuple[str, tuple[str, ...]]]:
    if category == "technical":
        return [
            ("deviation_requirements.technical", ("deviation_requirements", "technical")),
            ("technical_requirements", ("technical_requirements",)),
            ("technical_parameters", ("technical_parameters",)),
            ("requirements.technical", ("requirements", "technical")),
            ("scoring.technical_score.items", ("scoring", "technical_score", "items")),
        ]
    return [
        ("deviation_requirements.commercial", ("deviation_requirements", "commercial")),
        ("commercial_requirements", ("commercial_requirements",)),
        ("requirements.commercial", ("requirements", "commercial")),
        ("scoring.commercial_score.items", ("scoring", "commercial_score", "items")),
    ]


def collect_atomic_requirements(data: dict) -> list[dict]:
    """从显式偏离要求及兼容字段收集原子要求；显式字段优先。"""
    atoms: list[dict] = []
    seen: set[tuple[str, str]] = set()
    counters = {"technical": 0, "commercial": 0}

    for category in ("technical", "commercial"):
        collected: list[tuple[str, Any]] = []
        for source_name, path in _source_specs(category):
            for item in _iter_values(_get_nested(data, path)):
                collected.append((source_name, item))

        if category == "commercial" and not collected:
            commercial = data.get("commercial") or {}
            if isinstance(commercial, dict):
                for key, value in commercial.items():
                    if value not in (None, "", [], {}, "文件未载明"):
                        collected.append((f"commercial.{key}", {
                            "id": key,
                            "requirement_text": f"{key}：{first_text(value) or value}",
                        }))

        for source_name, raw in collected:
            raw_dict = raw if isinstance(raw, dict) else {}
            explicit_atoms = raw_dict.get("atomic_requirements") if raw_dict else None
            texts = [first_text(x) for x in _iter_values(explicit_atoms)] if explicit_atoms else []
            if not texts:
                base_text = first_text(raw)
                texts = split_atomic_text(base_text, category) if base_text else []
            texts = [text for text in texts if text]
            if not texts:
                continue

            counters[category] += 1
            prefix = "T" if category == "technical" else "B"
            parent_id = str(raw_dict.get("id") or raw_dict.get("requirement_id") or f"{prefix}{counters[category]:03d}")
            for index, text in enumerate(texts, 1):
                key = (category, normalize_text(text))
                if key in seen:
                    continue
                seen.add(key)
                atom_id = parent_id if len(texts) == 1 else f"{parent_id}.{index}"
                atoms.append({
                    "id": atom_id,
                    "parent_id": parent_id,
                    "atom_index": index,
                    "atom_count": len(texts),
                    "category": category,
                    "requirement_text": text,
                    "source": str(raw_dict.get("source") or source_name),
                    "risk_level": str(raw_dict.get("risk_level") or raw_dict.get("level") or ""),
                    "mandatory": bool(raw_dict.get("mandatory") or raw_dict.get("type") in {"★", "否决", "强制"}),
                    "evidence_required": first_text(raw_dict, ("evidence_required", "evidence", "document")),
                    "embedded_response": first_text(raw_dict, RESPONSE_KEYS),
                })

    for clause in data.get("star_clauses") or []:
        if not isinstance(clause, dict):
            continue
        category_text = str(clause.get("category") or "")
        category = "technical" if "技术" in category_text else "commercial" if "商务" in category_text else ""
        if not category:
            continue
        text = first_text(clause)
        for part in split_atomic_text(text, category):
            key = (category, normalize_text(part))
            if key in seen:
                continue
            seen.add(key)
            counters[category] += 1
            prefix = "T" if category == "technical" else "B"
            atoms.append({
                "id": str(clause.get("id") or f"{prefix}{counters[category]:03d}"),
                "parent_id": str(clause.get("id") or f"{prefix}{counters[category]:03d}"),
                "atom_index": 1,
                "atom_count": 1,
                "category": category,
                "requirement_text": part,
                "source": str(clause.get("source") or "star_clauses"),
                "risk_level": "废标" if clause.get("type") in {"★", "否决", "强制"} else "",
                "mandatory": clause.get("type") in {"★", "否决", "强制"},
                "evidence_required": first_text(clause, ("evidence_required",)),
                "embedded_response": "",
            })
    return atoms


def response_mapping(data: dict) -> dict[str, Any]:
    result: dict[str, Any] = {}
    raw = data.get("responses") if isinstance(data, dict) else None
    if isinstance(raw, dict):
        result.update({str(key): value for key, value in raw.items()})
    for category in ("technical", "commercial"):
        for item in _iter_values(data.get(category) if isinstance(data, dict) else None):
            if not isinstance(item, dict):
                continue
            item_id = item.get("id") or item.get("requirement_id")
            if item_id:
                result[str(item_id)] = item
    return result


def _response_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    return first_text(value, RESPONSE_KEYS)


def resolve_response(atom: dict, responses: dict[str, Any]) -> tuple[str, dict]:
    exact = responses.get(atom["id"])
    parent = responses.get(atom["parent_id"])
    value = exact if exact is not None else parent
    metadata = value if isinstance(value, dict) else {}
    if isinstance(value, list):
        index = atom["atom_index"] - 1
        value = value[index] if index < len(value) else ""
        metadata = value if isinstance(value, dict) else {}
    text = _response_text(value)
    if not text and atom.get("embedded_response"):
        text = str(atom["embedded_response"])
    return text, metadata


def is_generic_response(response: str) -> bool:
    normalized = normalize_text(response)
    if not normalized:
        return False
    reduced = normalized
    prefixes = ("我方", "本公司", "投标人", "现确认", "确认", "承诺", "答复")
    changed = True
    while changed:
        changed = False
        for prefix in prefixes:
            if reduced.startswith(prefix):
                reduced = reduced[len(prefix):]
                changed = True
                break
    generic_parts = sorted({normalize_text(item) for item in GENERIC_CORE}, key=len, reverse=True)
    remainder = reduced
    for part in generic_parts:
        remainder = remainder.replace(part, "")
    return reduced in set(generic_parts) or not remainder


def extract_facts(text: str) -> list[str]:
    facts, seen = [], set()
    for match in FACT_RE.finditer(text or ""):
        value = normalize_text(match.group(0))
        if value and value not in seen:
            seen.add(value)
            facts.append(value)
    return facts


def extract_anchors(text: str) -> list[str]:
    anchors, seen = [], set()
    for pattern in ANCHOR_PATTERNS:
        for match in pattern.finditer(text or ""):
            value = normalize_text(match.group(0))
            if value and value not in seen:
                seen.add(value)
                anchors.append(value)
    return anchors


def _bigrams(text: str) -> set[str]:
    normalized = normalize_text(text)
    return {normalized[index:index + 2] for index in range(max(0, len(normalized) - 1))}


def evaluate_response(requirement: str, response: str, category: str) -> dict:
    response = str(response or "").strip()
    if not response or PLACEHOLDER_RE.search(response):
        return {
            "status": "missing", "passed": False, "generic": False,
            "coverage": 0.0, "missing_facts": [], "missing_anchors": [],
            "missing_terms": [], "reason": "未填写具体投标响应或仍为占位内容",
        }
    if is_generic_response(response):
        return {
            "status": "generic", "passed": False, "generic": True,
            "coverage": 0.0, "missing_facts": extract_facts(requirement),
            "missing_anchors": extract_anchors(requirement), "missing_terms": [],
            "reason": "响应仅为“完全响应/完全满足/无偏离”等泛化表述",
        }

    requirement_norm = normalize_text(requirement)
    response_norm = normalize_text(response)
    facts = extract_facts(requirement)
    anchors = extract_anchors(requirement)
    terms = [normalize_text(term) for term in DOMAIN_TERMS if term in requirement]
    missing_facts = [fact for fact in facts if fact not in response_norm]
    missing_anchors = [anchor for anchor in anchors if anchor not in response_norm]
    missing_terms = [term for term in terms if term not in response_norm]
    required_bigrams = _bigrams(requirement)
    response_bigrams = _bigrams(response)
    coverage = (
        len(required_bigrams & response_bigrams) / len(required_bigrams)
        if required_bigrams else 0.0
    )
    threshold = 0.55 if category == "technical" else 0.75
    exact_mirror = bool(requirement_norm and requirement_norm in response_norm)
    passed = exact_mirror or (
        not missing_facts and not missing_anchors and not missing_terms and coverage >= threshold
    )
    reasons = []
    if missing_facts:
        reasons.append("缺少参数/数值/单位：" + "、".join(missing_facts[:5]))
    if missing_anchors:
        reasons.append("缺少起算点或限制条件：" + "、".join(missing_anchors[:3]))
    if missing_terms:
        reasons.append("缺少条款要素：" + "、".join(missing_terms[:5]))
    if coverage < threshold and not exact_mirror:
        reasons.append(f"要求原文要素覆盖率 {coverage:.0%}，低于 {threshold:.0%}")
    return {
        "status": "pass" if passed else "partial",
        "passed": passed,
        "generic": False,
        "coverage": round(coverage, 4),
        "missing_facts": missing_facts,
        "missing_anchors": missing_anchors,
        "missing_terms": missing_terms,
        "reason": "；".join(reasons) if reasons else "响应包含具体参数、数值、条件及原文要素",
    }


def build_deviation_rows(requirements: dict, response_data: dict) -> list[dict]:
    mapping = response_mapping(response_data)
    rows = []
    for atom in collect_atomic_requirements(requirements):
        response, metadata = resolve_response(atom, mapping)
        check = evaluate_response(atom["requirement_text"], response, atom["category"])
        row = dict(atom)
        row.update({
            "response_text": response,
            "deviation": str(metadata.get("deviation") or ("无偏离" if check["passed"] else "待整改")),
            "evidence": first_text(metadata, ("evidence", "proof", "page", "location")),
            "check": check,
            "priority": "P0" if not check["passed"] else "",
        })
        rows.append(row)
    return rows


def summarize_rows(rows: list[dict]) -> dict:
    failed = [row for row in rows if not (row.get("check") or {}).get("passed")]
    return {
        "total": len(rows),
        "technical": sum(row.get("category") == "technical" for row in rows),
        "commercial": sum(row.get("category") == "commercial" for row in rows),
        "passed": len(rows) - len(failed),
        "failed": len(failed),
        "generic": sum((row.get("check") or {}).get("generic") is True for row in rows),
        "ok": bool(rows) and not failed,
    }
