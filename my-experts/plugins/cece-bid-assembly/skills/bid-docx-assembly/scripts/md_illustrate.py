#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
md_illustrate.py — 按"标题→图片"映射，把图片标记批量插入 Markdown 对应章节。

用途：把从样板/历史标书提取的图片素材，按原文章节关系定点插回新建标书 Markdown，
避免人工逐张挑图（省 token、不遗漏、位置可复现）。

输入：
  1) sequence.json  —— 由 docx_parse.py 生成
  2) 映射表 JSON    —— 形如：
     {
       "目标.md": [
         ["样板中的标题名", "目标md中的锚点标题", "图注前缀"],
         ...
       ]
     }
  3) 图片目录 —— 存放 media 原号图片（如 image1.jpeg）

输出：直接在目标 Markdown 中插入 ![图注](绝对路径) 标记块，插在该锚点章节末尾
     （即下一个同级/更高级标题之前）。

用法：
  python3 md_illustrate.py --seq seq.json --map map.json --media-dir /path/media [--base-dir /workspace/项目]

安全：默认 dry-run（只报告不写入），加 --apply 才真正修改文件。
      修改前自动备份为 .bak。
"""
import argparse
import difflib
import json
import os
import shutil
import sys


def build_sec_imgs(seq):
    """sequence.json -> {标题: [图片文件名(去media/前缀, 去重保序)]}"""
    sec = {}
    for x in seq:
        if x.get('type') == 'IMG':
            m = x.get('media', '').replace('media/', '')
            sec.setdefault(x.get('section'), [])
            if m not in sec[x['section']]:
                sec[x['section']].append(m)
    return sec


def heading_index(lines):
    """建立锚点索引：支持 ## / ### 标题，以及 **粗体** 锚点（如 **维度①：xxx**）"""
    idx = {}
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith('### ') or s.startswith('## '):
            t = s.lstrip('#').strip()
            idx.setdefault(t, i)
        elif s.startswith('**') and s.endswith('**') and len(s) > 4:
            t = s.strip('*').strip()
            idx.setdefault(t, i)
    return idx


def is_boundary(s):
    return (s.startswith('### ') or s.startswith('## ')
            or (s.startswith('**') and s.endswith('**') and len(s) > 4))


def process(md_path, mapping, sec_imgs, media_dir, apply=False, backup=True):
    if not os.path.exists(md_path):
        print(f'  [错误] 文件不存在: {md_path}')
        return 0
    with open(md_path, encoding='utf-8') as f:
        lines = f.read().split('\n')

    idx = heading_index(lines)
    ops = []  # (插入行号, 块内容)
    missing_anchor = []

    for sec_title, anchor, caption in mapping:
        imgs = sec_imgs.get(sec_title, [])
        if not imgs:
            # 模糊匹配：渐进降低阈值，尽量给出候选
            near = []
            for co in (0.6, 0.45, 0.3, 0.15):
                near = difflib.get_close_matches(sec_title, list(sec_imgs.keys()), n=3, cutoff=co)
                if near:
                    break
            print(f'  [警告] 样板标题无图片: {sec_title[:40]}')
            if near:
                print('          最相近的候选（含图数）：')
                for c in near:
                    print(f'            - {c[:60]}  ({len(sec_imgs[c])} 图)')
            else:
                print('          （无相近候选，请用 --list-sections 核对 section 名）')
            continue
        if anchor not in idx:
            # 锚点也做模糊匹配提示
            near_a = difflib.get_close_matches(anchor, list(idx.keys()), n=3, cutoff=0.4)
            missing_anchor.append(anchor)
            if near_a:
                print(f'  [提示] 锚点"{anchor[:30]}"未找到，相近候选:')
                for c in near_a:
                    print(f'            - {c[:60]}')
            continue
        a_i = idx[anchor]
        # 找该章节的结束位置（下一个边界之前）
        next_i = len(lines)
        for j in range(a_i + 1, len(lines)):
            if is_boundary(lines[j].strip()):
                next_i = j
                break
        block = ['', '<!-- 图片素材：原位插入（由 md_illustrate.py 生成） -->']
        for j, fn in enumerate(imgs):
            abs_path = os.path.join(media_dir, fn)
            block.append(f'![{caption} {j+1}/{len(imgs)}]({abs_path})')
        block.append('')
        ops.append((next_i, block, len(imgs)))

    if missing_anchor:
        print(f'  [错误] 以下锚点未找到（共{len(missing_anchor)}个），请核对映射表：')
        for a in missing_anchor:
            print(f'      - {a[:70]}')

    total = sum(n for _, _, n in ops)
    if not ops:
        print(f'  {os.path.basename(md_path)}: 无插图（0 张）')
        return 0

    if not apply:
        print(f'  [dry-run] {os.path.basename(md_path)}: 将插入 {len(ops)} 个块 / {total} 张图')
        return total

    if backup and not os.path.exists(md_path + '.bak'):
        shutil.copy2(md_path, md_path + '.bak')

    # 按行号降序插入，避免偏移
    for pos, block, _ in sorted(ops, key=lambda x: -x[0]):
        lines[pos:pos] = block

    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f'  {os.path.basename(md_path)}: 已插入 {len(ops)} 个块 / {total} 张图')
    return total


def main():
    ap = argparse.ArgumentParser(description='按映射表把图片标记批量插入 Markdown 章节')
    ap.add_argument('--seq', required=True, help='docx_parse.py 生成的 sequence.json')
    ap.add_argument('--map', required=True, help='映射表 JSON')
    ap.add_argument('--media-dir', required=True, help='图片目录（含 media 原号文件）')
    ap.add_argument('--base-dir', default=None, help='Markdown 所在根目录（映射表中的相对路径基准）')
    ap.add_argument('--apply', action='store_true', help='真正写入（默认 dry-run）')
    ap.add_argument('--no-backup', action='store_true', help='不备份原文件')
    ap.add_argument('--list-sections', action='store_true',
                    help='只列出 sequence.json 中的 section 清单（含图数），用于编写映射表')
    args = ap.parse_args()

    with open(args.seq, encoding='utf-8') as f:
        seq = json.load(f)

    if args.list_sections:
        sec_imgs = build_sec_imgs(seq)
        print(f'== 样板 section 清单（共 {len(sec_imgs)} 个，按图数降序）==\n')
        for s, imgs in sorted(sec_imgs.items(), key=lambda x: -len(x[1])):
            print(f'{len(imgs):4d} 图 | {s[:70]}')
        print(f'\n合计图片引用: {sum(len(v) for v in sec_imgs.values())}')
        return

    with open(args.map, encoding='utf-8') as f:
        mapping = json.load(f)

    sec_imgs = build_sec_imgs(seq)

    # 仅列出 section 清单（写映射表前先看这个）
    if args.list_sections:
        print(f'== 样板 section 清单（共 {len(sec_imgs)} 个，按图数降序）==\n')
        for s, imgs in sorted(sec_imgs.items(), key=lambda x: -len(x[1])):
            print(f'{len(imgs):4d} 图 | {s[:70]}')
        print(f'\n合计图片引用: {sum(len(v) for v in sec_imgs.values())}')
        return

    base = args.base_dir or '.'
    total = 0
    for md_rel, m in mapping.items():
        md_path = md_rel if os.path.isabs(md_rel) else os.path.join(base, md_rel)
        total += process(md_path, m, sec_imgs, args.media_dir,
                         apply=args.apply, backup=not args.no_backup)
    mode = '（已写入）' if args.apply else '（dry-run，未写入；加 --apply 生效）'
    print(f'\n合计图片 {total} 张 {mode}')


if __name__ == '__main__':
    main()
