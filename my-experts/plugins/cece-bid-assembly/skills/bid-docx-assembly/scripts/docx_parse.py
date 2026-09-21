#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
docx_parse.py — 把 docx 解析成"正文序列 JSON"，保留 段落/标题/图片 的原位关系。

用途：从历史标书/样板 docx 中提取文字与图片素材，并保留"每张图挂在哪个标题下"的
原位关系，供后续按章节定点插图使用。

输出 JSON 为列表，每项：
  {"type":"TXT", "text":"...", "section":"所属标题"}
  {"type":"IMG", "rid":"rId8", "media":"media/image1.jpeg", "section":"所属标题"}

用法：
  python3 docx_parse.py <input.docx> [-o output.json] [--media-dir /path/to/media]

说明：
- 自动解压 docx 到临时目录，读取 word/document.xml + word/_rels/document.xml.rels
- section 字段 = 图片/文字出现时"最近的一个标题段落"（按 ## / 编号标题 启发式判定）
- 若无 -o，默认输出到 <input>.sequence.json
"""
import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile
from collections import OrderedDict
from xml.etree import ElementTree as ET

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
WP = '{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}'
PIC = '{http://schemas.openxmlformats.org/drawingml/2006/picture}'


def unzip_docx(docx_path, out_dir):
    """解压 docx 到目录，返回 document.xml 路径"""
    os.makedirs(out_dir, exist_ok=True)
    with zipfile.ZipFile(docx_path) as z:
        z.extractall(out_dir)
    return os.path.join(out_dir, 'word', 'document.xml')


def load_rid_map(rels_path):
    """rId -> media 相对路径"""
    rid_map = {}
    if not os.path.exists(rels_path):
        return rid_map
    tree = ET.parse(rels_path)
    for rel in tree.getroot():
        rid = rel.get('Id')
        target = rel.get('Target')
        if target and 'media/' in target:
            rid_map[rid] = target.replace('word/', '')
    return rid_map


def para_text(p):
    """提取段落纯文本"""
    parts = []
    for t in p.iter(W + 't'):
        parts.append(t.text or '')
    for t in p.iter(W + 'tab'):
        parts.append('\t')
    return ''.join(parts).strip()


def para_images(p):
    """提取段落中图片的 rId 列表（按顺序）"""
    rids = []
    for blip in p.iter(A + 'blip'):
        rid = blip.get(R + 'embed')
        if rid:
            rids.append(rid)
    if not rids:
        # 兼容 VML 老式图片
        for im in p.iter('{urn:schemas-microsoft-com:vml}imagedata'):
            rid = im.get(R + 'id') or im.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
            if rid:
                rids.append(rid)
    return rids


def is_heading(p, text, mode='legacy'):
    """判定是否为标题。两种模式，解决"长句当标题"与"正文短句像标题"的矛盾。

    mode='legacy'（默认，推荐用于投标样板/历史标书）：
      宽松模式。长句也算标题（因为这类文档常把完整长句作为小节标题，例如
      "（5）资料归档留存：将供应商原厂质保书、本厂检测报告……"）。
      代价：可能把少量正文短句误判为标题 → section 数偏多，但不丢关键 section。

    mode='strict'（推荐用于排版规范的文档）：
      严格模式。只认 styleId 明确的标题样式 + 简短编号标题（≤45字、不以冒号/句号结尾）。
      section 数少而准；但对"长句当标题"的文档会漏标题。

    选择建议：先跑 legacy 看 section 数；若明显过多（如 >100），再试 strict。
    也可两者都跑，用 legacy 的 section 做插图映射（保证不漏），strict 仅作交叉核对。
    """
    if not text:
        return False

    pPr = p.find(W + 'pPr')
    # 1) 明确标题样式（两种模式都认，最可靠）
    if pPr is not None:
        pStyle = pPr.find(W + 'pStyle')
        if pStyle is not None:
            sid = (pStyle.get(W + 'val') or '').lower()
            if 'heading' in sid or sid in ('1', '2', '3', '4') or '标题' in sid:
                return True

    if mode == 'strict':
        # 严格：排除正文特征（冒号/句号结尾、超长）
        if text.rstrip()[-1:] in (':', '：', '。', '；', ';', '，', ','):
            return False
        if len(text) > 45:
            return False
        if re.match(r'^\s*[（(]?\s*[0-9一二三四五六七八九十]{1,3}\s*[）)、.．]\s*\S', text):
            return True
        if re.match(r'^\s*[一二三四五六七八九十]{1,3}\s*[-－]\s*[0-9]{1,2}\s*[、.．]\s*\S', text):
            return True
        if pPr is not None:
            rPr = pPr.find(W + 'rPr')
            if rPr is not None and rPr.find(W + 'b') is not None and 0 < len(text) <= 30:
                if text.rstrip()[-1:] not in (':', '：', '。', '；'):
                    return True
        return False

    # legacy：宽松
    # 编号标题：1、xxx / （1）xxx / 一、xxx / 1.1 xxx（不限长度）
    if re.match(r'^\s*[（(]?\s*[0-9一二三四五六七八九十]{1,3}\s*[）)、.．]\s*\S', text):
        return True
    # 中文分节编号：三-2、xxx
    if re.match(r'^\s*[一二三四五六七八九十]{1,3}\s*[-－]\s*[0-9]{1,2}\s*[、.．]\s*\S', text):
        return True
    # 圆圈编号：①内控手册 / ②检验规程
    if re.match(r'^\s*[①②③④⑤⑥⑦⑧⑨⑩]\s*\S', text):
        return True
    # 加粗文本（不限长度，保证长标题不丢）
    if pPr is not None:
        rPr = pPr.find(W + 'rPr')
        if rPr is not None and rPr.find(W + 'b') is not None and 0 < len(text) <= 80:
            return True
    return False


def parse(docx_path, out_json=None, media_dir=None, mode='legacy'):
    tmp = tempfile.mkdtemp(prefix='docx_parse_')
    try:
        doc_xml = unzip_docx(docx_path, tmp)
        rels_path = os.path.join(tmp, 'word', '_rels', 'document.xml.rels')
        rid_map = load_rid_map(rels_path)

        tree = ET.parse(doc_xml)
        body = tree.getroot().find(W + 'body')

        seq = []
        cur_section = '（开头）'

        def walk(container):
            nonlocal cur_section
            for child in container:
                tag = child.tag
                if tag == W + 'p':
                    text = para_text(child)
                    imgs = para_images(child)
                    if is_heading(child, text, mode) and text:
                        cur_section = text
                        seq.append({'type': 'TXT', 'text': text, 'section': cur_section})
                    if imgs:
                        for rid in imgs:
                            media = rid_map.get(rid, f'未解析:{rid}')
                            seq.append({'type': 'IMG', 'rid': rid, 'media': media, 'section': cur_section})
                    elif text:
                        seq.append({'type': 'TXT', 'text': text, 'section': cur_section})
                elif tag == W + 'tbl':
                    # 表格内也遍历段落/图片
                    for tr in child.findall(W + 'tr'):
                        for tc in tr.findall(W + 'tc'):
                            walk(tc)

        walk(body)

        if out_json is None:
            out_json = os.path.splitext(docx_path)[0] + '.sequence.json'
        with open(out_json, 'w', encoding='utf-8') as f:
            json.dump(seq, f, ensure_ascii=False, indent=1)

        n_txt = sum(1 for x in seq if x['type'] == 'TXT')
        n_img = sum(1 for x in seq if x['type'] == 'IMG')
        uniq_media = len({x['media'] for x in seq if x['type'] == 'IMG'})
        n_sec = len({x['section'] for x in seq if x['type'] == 'IMG'})
        print(f'已解析: {docx_path}  [mode={mode}]')
        print(f'  文字段: {n_txt}   图片引用: {n_img}   唯一图片: {uniq_media}   图片所属section: {n_sec}')
        print(f'  输出: {out_json}')
        return seq
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description='解析 docx 为正文序列 JSON（保留标题→图片原位关系）')
    ap.add_argument('docx', help='输入 docx 路径')
    ap.add_argument('-o', '--out', default=None, help='输出 JSON 路径')
    ap.add_argument('--media-dir', default=None, help='（可选）图片目录，仅用于提示')
    ap.add_argument('--mode', default='legacy', choices=['legacy', 'strict'],
                    help='标题判定模式：legacy=宽松(长句也算标题，投标样板默认); '
                         'strict=严格(只认样式标题+短编号标题)')
    args = ap.parse_args()
    if not os.path.exists(args.docx):
        print(f'错误: 文件不存在 {args.docx}', file=sys.stderr)
        sys.exit(1)
    parse(args.docx, args.out, args.media_dir, args.mode)


if __name__ == '__main__':
    main()
