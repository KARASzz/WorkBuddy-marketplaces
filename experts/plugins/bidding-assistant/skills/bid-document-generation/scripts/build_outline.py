#!/usr/bin/env python3
"""
三级目录解析器。
读取目录 JSON（/tmp/bid_outline.json），拆解为叶子节点任务队列，
输出 /tmp/bid_task_queue.json，供 SKILL.md Step 3 逐节调用。

叶子节点 = 无子节点（children 为空）的最末级章节。

输出结构（每条任务）：
{
  "id":           "1.1.2",
  "title":        "核心技术架构",
  "description":  "详述系统整体技术路线...",
  "scored_item":  "技术方案（20分）",
  "parent_title": "技术方案与实施",
  "sibling_ids":  ["1.1.1", "1.1.3"],
  "level":        3,
  "output_file":  "/tmp/bid_sections/1.1.2.txt"
}

无第三方依赖。
"""
import argparse
import json
from pathlib import Path


def _walk(nodes: list, parent_title: str, tasks: list):
    """
    深度优先遍历目录树，找出所有叶子节点并记录上下文信息。
    非叶子节点同时加入「章节引言」任务。
    """
    # 收集同级 id，用于同级去重提示
    sibling_ids = [n["id"] for n in nodes]

    for node in nodes:
        children = node.get("children") or []
        node_id  = node["id"]
        level    = node_id.count(".") + 1

        if not children:
            # 叶子节点 → 正文任务
            tasks.append({
                "type":         "section",
                "id":           node_id,
                "title":        node.get("title", ""),
                "description":  node.get("description", ""),
                "scored_item":  node.get("scored_item", ""),
                "parent_title": parent_title,
                "sibling_ids":  [s for s in sibling_ids if s != node_id],
                "level":        level,
                "source_heading": node.get("source_heading") or node.get("display_title", ""),
                "heading_style": node.get("heading_style", ""),
                "output_file":  f"/tmp/bid_sections/{node_id}.txt"
            })
        else:
            # 非叶子节点 → 先递归子节点，再追加引言任务
            _walk(children, node.get("title", ""), tasks)
            # 引言字数参考：一级 100-150 字，二级 50-100 字
            intro_words = "100-150" if level == 1 else "50-100"
            tasks.append({
                "type":         "intro",
                "id":           node_id,
                "title":        node.get("title", ""),
                "description":  node.get("description", ""),
                "scored_item":  node.get("scored_item", ""),  # OPT-S3-01：继承评分项，LLM 可据此感知该章节覆盖哪个评分维度
                "parent_title": parent_title,
                "sibling_ids":  [],
                "level":        level,
                "source_heading": node.get("source_heading") or node.get("display_title", ""),
                "heading_style": node.get("heading_style", ""),
                "intro_words":  intro_words,
                "output_file":  f"/tmp/bid_sections/{node_id}_intro.txt"
            })


def build_task_queue(outline_path: str, output_path: str):
    outline_data = json.loads(Path(outline_path).read_text(encoding="utf-8"))
    nodes        = outline_data.get("outline") or outline_data.get("chapters") or []

    tasks = []
    _walk(nodes, "", tasks)

    # 统计
    section_count = sum(1 for t in tasks if t["type"] == "section")
    intro_count   = sum(1 for t in tasks if t["type"] == "intro")
    scored_count  = sum(1 for t in tasks if t["type"] == "section" and t.get("scored_item"))

    result = {
        "total":         len(tasks),
        "section_count": section_count,
        "intro_count":   intro_count,
        "scored_count":  scored_count,
        "tasks":         tasks
    }

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(
        f"[OK] 任务队列生成完成：共 {len(tasks)} 个任务"
        f"（正文 {section_count} 节 | 引言 {intro_count} 节"
        f" | 关联评分项 {scored_count} 节）→ {output_path}"
    )


def main():
    parser = argparse.ArgumentParser(description="三级目录 → 任务队列")
    parser.add_argument("--outline", default="/tmp/bid_outline.json", help="目录 JSON 路径")
    parser.add_argument("--output",  default="/tmp/bid_task_queue.json", help="输出任务队列路径")
    args = parser.parse_args()
    build_task_queue(args.outline, args.output)


if __name__ == "__main__":
    main()
