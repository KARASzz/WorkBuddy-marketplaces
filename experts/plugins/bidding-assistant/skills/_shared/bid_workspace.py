#!/usr/bin/env python3
"""Lightweight bid workspace archive and resume helper.

The helper preserves the existing /tmp contracts by copying selected artifacts
into bid_workspace/<project_name>/ and maintaining a small state.json.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime
from pathlib import Path


DEFAULT_ROOT = "bid_workspace"
STATE_FILE = "state.json"


def safe_name(name: str) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", (name or "未命名项目").strip())
    return cleaned.strip("_") or "未命名项目"


def workspace_dir(project_name: str, root: str | Path = DEFAULT_ROOT) -> Path:
    return Path(root).expanduser().resolve() / safe_name(project_name)


def load_state(project_dir: Path, project_name: str) -> dict:
    state_path = project_dir / STATE_FILE
    if not state_path.exists():
        return {
            "project_name": project_name,
            "stages": {},
            "artifacts": {},
            "updated_at": "",
        }
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "project_name": project_name,
            "stages": {},
            "artifacts": {},
            "updated_at": "",
            "warning": "state.json 无法解析，已重建状态骨架",
        }


def save_state(project_dir: Path, state: dict) -> None:
    project_dir.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = datetime.now().isoformat(timespec="seconds")
    (project_dir / STATE_FILE).write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def copy_artifact(src: Path, dest_dir: Path) -> Path:
    src = src.expanduser().resolve()
    if not src.exists():
        raise FileNotFoundError(str(src))
    dest = dest_dir / src.name
    if src.is_dir():
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    return dest


def update_workspace(project_name: str, root: str, stages: list[str], artifacts: list[str]) -> dict:
    project_dir = workspace_dir(project_name, root)
    state = load_state(project_dir, project_name)
    state["project_name"] = project_name

    for item in stages:
        if "=" not in item:
            raise ValueError(f"阶段参数格式应为 name=status: {item}")
        name, status = item.split("=", 1)
        state.setdefault("stages", {})[name.strip()] = status.strip()

    artifact_dir = project_dir / "artifacts"
    for item in artifacts:
        if "=" not in item:
            raise ValueError(f"产物参数格式应为 name=path: {item}")
        name, path = item.split("=", 1)
        copied = copy_artifact(Path(path), artifact_dir)
        state.setdefault("artifacts", {})[name.strip()] = str(copied)

    save_state(project_dir, state)
    return state


def render_status(state: dict) -> str:
    lines = [
        f"项目：{state.get('project_name', '')}",
        f"最近更新：{state.get('updated_at', '')}",
        "",
        "阶段：",
    ]
    stages = state.get("stages", {})
    if stages:
        lines.extend([f"  - {name}: {status}" for name, status in stages.items()])
    else:
        lines.append("  - 尚无阶段记录")
    lines.extend(["", "产物："])
    artifacts = state.get("artifacts", {})
    if artifacts:
        lines.extend([f"  - {name}: {path}" for name, path in artifacts.items()])
    else:
        lines.append("  - 尚无归档产物")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Archive bid artifacts and show resumable workspace status.")
    parser.add_argument("--project-name", required=True, help="项目名称")
    parser.add_argument("--root", default=DEFAULT_ROOT, help="工作区根目录，默认 bid_workspace")
    parser.add_argument("--stage", action="append", default=[], help="阶段状态，格式 name=status，可重复")
    parser.add_argument("--artifact", action="append", default=[], help="归档产物，格式 name=path，可重复")
    parser.add_argument("--status", action="store_true", help="仅显示当前工作区状态")
    args = parser.parse_args()

    project_dir = workspace_dir(args.project_name, args.root)
    if args.status:
        state = load_state(project_dir, args.project_name)
        print(render_status(state))
        return 0

    state = update_workspace(args.project_name, args.root, args.stage, args.artifact)
    print(render_status(state))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
