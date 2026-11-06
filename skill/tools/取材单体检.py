#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""取材单体检.py —— 取材单没填完，不许进糅合。

用法：
  python 取材单体检.py                 # 查 03_图纸_大纲与细纲/取材单_*.md（全部）
  python 取材单体检.py --file 取材单_第001段.md
  python 取材单体检.py --selftest

判据：
  1. 文件存在，且至少 3 行有效取材（--min-rows 可调）。
  2. 每行必须有：用途、来源库、编号、取的是什么。
  3. 双源：结构/拍点/桥段/母题/主线 这几类里，至少出现 2 个不同来源库。
  4. 桥段行必须写冷却结论（不许空、不许写“—”）。
退出码：0 通过；1 不过；--selftest 失败 1。
"""
import argparse
import glob
import io
import os
import sys
import tempfile

CORE_KINDS = ('结构', '拍点', '桥段', '母题', '主线', '副线')
BRIDGE = ('桥段',)


def find_root(start=None):
    d = os.path.abspath(start or os.getcwd())
    for _ in range(8):
        if os.path.isfile(os.path.join(d, '项目配置.json')):
            return d
        nd = os.path.dirname(d)
        if nd == d:
            break
        d = nd
    return None


def read(p):
    try:
        return io.open(p, encoding='utf-8').read()
    except FileNotFoundError:
        return ''


def rows_of(text):
    rows = []
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith('|'):
            continue
        cells = [c.strip() for c in s.strip('|').split('|')]
        if len(cells) < 6:
            continue
        if cells[0] in ('#', '') or set(cells[0]) <= set('-: '):
            continue
        rows.append(cells)
    return rows


def check_file(path, min_rows):
    text = read(path)
    name = os.path.basename(path)
    if not text.strip():
        print(f'[停] 读不到取材单：{path}')
        return 1
    rows = rows_of(text)
    problems = []
    if len(rows) < min_rows:
        problems.append(f'有效取材只有 {len(rows)} 行，至少 {min_rows} 行')
    libs = set()
    for i, c in enumerate(rows, 1):
        kind, lib, code, what, where, cool = c[1], c[2], c[3], c[4], c[5], (c[6] if len(c) > 6 else '')
        if not (kind and lib and code and what):
            problems.append(f'第 {i} 行缺列（用途/来源库/编号/取什么）')
            continue
        if kind in CORE_KINDS:
            libs.add(lib)
        if any(b in kind for b in BRIDGE):
            if not cool or cool in ('—', '-', '–'):
                problems.append(f'第 {i} 行是桥段，没写冷却结论')
    if len(libs) < 2:
        problems.append(f'双源不足：核心取材只来自 {len(libs)} 个来源库')
    print(f'{name}: 有效 {len(rows)} 行，来源库 {len(libs)} 个')
    if problems:
        print('FAIL：')
        for p in problems:
            print('  -', p)
        return 1
    print('PASS')
    return 0


def check(paths, min_rows):
    if not paths:
        print('[停] 没有取材单。先按模板填 `03_图纸_大纲与细纲/取材单_第NNN段.md`。')
        return 1
    rc = 0
    for p in paths:
        rc = check_file(p, min_rows) or rc
    return rc


def selftest():
    d = tempfile.mkdtemp(prefix='jipu-sheet-')
    good = '''# 取材单
| # | 用途 | 来源库 | 编号 | 取的是什么 | 用在拍/章 | 冷却检查 | 备注 |
|---|---|---|---|---|---|---|---|
| 1 | 结构 | 结构层库 | S-201 | 七级地图链 | 全段 | — | 借结构 |
| 2 | 拍点 | 剧情模板库 | P-103 | 开局三拍 | 拍 1—3 | 上次 012 章，已过 60 章 | 换变体 |
| 3 | 桥段 | 类目桥段库 | Q-207 | 当众定价 | 拍 4 | 上次 003 章，已过 12 章 | 换类目 |
| 4 | 母题 | 主题灵感库 | 01 | 旧秩序的债 | 全段 | — | 不点破 |
'''
    p1 = os.path.join(d, '取材单_第001段.md')
    io.open(p1, 'w', encoding='utf-8').write(good)
    rc_ok = check([p1], 3)

    bad = good.replace('| 3 | 桥段 | 类目桥段库 | Q-207 | 当众定价 | 拍 4 | 上次 003 章，已过 12 章 | 换类目 |',
                       '| 3 | 桥段 | 类目桥段库 | Q-207 | 当众定价 | 拍 4 |  | 换类目 |')
    io.open(p1, 'w', encoding='utf-8').write(bad)
    rc_bad = check([p1], 3)

    fewer = '''# 取材单
| # | 用途 | 来源库 | 编号 | 取的是什么 | 用在拍/章 | 冷却检查 | 备注 |
|---|---|---|---|---|---|---|---|
| 1 | 结构 | 结构层库 | S-201 | 七级地图链 | 全段 | — | 借结构 |
'''
    io.open(p1, 'w', encoding='utf-8').write(fewer)
    rc_few = check([p1], 3)

    import shutil
    shutil.rmtree(d, ignore_errors=True)
    ok = rc_ok == 0 and rc_bad == 1 and rc_few == 1
    print(f'\n自检：{"通过" if ok else "失败"}（合规 {rc_ok}／缺冷却 {rc_bad}／行数不足 {rc_few}）')
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description='取材单体检')
    ap.add_argument('--file', action='append', default=[])
    ap.add_argument('--min-rows', type=int, default=3)
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()

    if a.selftest:
        sys.exit(selftest())

    paths = a.file
    if not paths:
        root = find_root()
        if root:
            paths = sorted(glob.glob(os.path.join(root, '03_图纸_大纲与细纲', '取材单_*.md')))
    sys.exit(check(paths, max(1, a.min_rows)))


if __name__ == '__main__':
    main()
