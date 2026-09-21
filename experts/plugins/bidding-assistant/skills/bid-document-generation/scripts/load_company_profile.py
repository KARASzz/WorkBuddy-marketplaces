#!/usr/bin/env python3
"""
企业资料库管理工具。
支持：加载、保存、检查企业资料，持久化到用户主目录。

用法：
  --check             检查本地资料库是否存在，输出摘要
  --save <json_path>  从临时文件保存到正式资料库
  --store             执行持久化写入（与 --save 联用）
  --load              从本地资料库加载到 /tmp
  --output <path>     输出路径（默认 /tmp/company_profile.json）

无第三方依赖。
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# 本地持久化路径（存入用户主目录，不随系统重启丢失）
STORE_DIR  = Path.home() / ".bid_toolkit"
STORE_PATH = STORE_DIR / "company_profile.json"

# 必填字段（用于完整性检查）
REQUIRED_FIELDS = [
    ("basic.company_name",             "公司全称"),
    ("basic.unified_social_credit_code", "统一社会信用代码"),
    ("basic.legal_representative",     "法定代表人"),
    ("basic.authorized_representative.name", "授权代表姓名"),
    ("basic.registered_capital",       "注册资本"),
    ("basic.contact.address",          "联系地址"),
    ("basic.contact.phone",            "联系电话"),
]


def get_nested(d: dict, dotted_key: str):
    """按点分路径取嵌套字段值。"""
    keys = dotted_key.split(".")
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def check_completeness(profile: dict) -> list:
    """返回缺失必填字段列表，格式：[(dotted_key, label), ...]。"""
    missing = []
    for key, label in REQUIRED_FIELDS:
        val = get_nested(profile, key)
        if not val:
            missing.append((key, label))
    return missing


def format_summary(profile: dict) -> str:
    """生成单行摘要文本。"""
    basic     = profile.get("basic", {})
    meta      = profile.get("_meta", {})
    name      = basic.get("company_name", "未知")
    updated   = meta.get("last_updated", "未知日期")
    qual_cnt  = len(profile.get("qualifications", []))
    perf_cnt  = len(profile.get("performance", []))
    return (
        f"企业：{name} | 资质：{qual_cnt} 项 | 业绩：{perf_cnt} 条 | "
        f"上次更新：{updated}"
    )


def load_from_store(output_path: str) -> dict:
    """从持久化路径加载，写入 output_path，返回 profile dict。"""
    if not STORE_PATH.exists():
        return {}
    profile = json.loads(STORE_PATH.read_text(encoding="utf-8"))
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(
        json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return profile


def save_to_store(tmp_path: str) -> dict:
    """从临时路径读取，更新时间戳，写入持久化路径，返回 profile dict。"""
    profile = json.loads(Path(tmp_path).read_text(encoding="utf-8"))
    if "_meta" not in profile:
        profile["_meta"] = {}
    profile["_meta"]["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    profile["_meta"]["store_path"]   = str(STORE_PATH)

    STORE_DIR.mkdir(parents=True, exist_ok=True)
    STORE_PATH.write_text(
        json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return profile


def cmd_check(output_path: str):
    """检查本地资料库状态，输出结构化 JSON 结果。"""
    if not STORE_PATH.exists():
        result = {
            "exists":   False,
            "complete": False,
            "summary":  "",
            "missing":  [],
            "message":  "本地企业资料库不存在，需要收集企业信息"
        }
    else:
        profile = load_from_store(output_path)
        missing = check_completeness(profile)
        result  = {
            "exists":   True,
            "complete": len(missing) == 0,
            "summary":  format_summary(profile),
            "missing":  [label for _, label in missing],
            "message":  (
                "企业资料完整，可直接使用" if not missing
                else f"企业资料不完整，缺少：{', '.join(l for _, l in missing)}"
            )
        }

    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_save(tmp_path: str, output_path: str):
    """保存企业资料到持久化路径。"""
    profile = save_to_store(tmp_path)
    # 同时更新 output_path（保证 /tmp 与持久化一致）
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(
        json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    missing = check_completeness(profile)
    print(json.dumps({
        "saved":    True,
        "path":     str(STORE_PATH),
        "summary":  format_summary(profile),
        "complete": len(missing) == 0,
        "missing":  [label for _, label in missing]
    }, ensure_ascii=False, indent=2))


def cmd_load(output_path: str):
    """从持久化路径加载到 output_path。"""
    if not STORE_PATH.exists():
        print(json.dumps({"loaded": False, "message": "本地资料库不存在"}, ensure_ascii=False))
        sys.exit(1)
    profile = load_from_store(output_path)
    print(json.dumps({
        "loaded":  True,
        "path":    output_path,
        "summary": format_summary(profile)
    }, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="企业资料库管理工具")
    parser.add_argument("--check",  action="store_true", help="检查本地资料库状态")
    parser.add_argument("--save",   metavar="TMP_PATH",  help="从临时文件保存到资料库")
    parser.add_argument("--store",  action="store_true", help="执行持久化写入（与 --save 联用）")
    parser.add_argument("--load",   action="store_true", help="从本地资料库加载到 /tmp")
    parser.add_argument("--output", default="/tmp/company_profile.json", help="输出路径")
    args = parser.parse_args()

    if args.check:
        cmd_check(args.output)
    elif args.save and args.store:
        cmd_save(args.save, args.output)
    elif args.load:
        cmd_load(args.output)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
