# -*- coding: utf-8 -*-
"""卷纲体检.py —— 查卷纲回合表（行格式见 assets/结构层库/08-卷纲回合表.md）。

为什么单列一个脚本：整卷塌掉，多半不是文笔，是这张表排坏了——
连着两个回合同型兑现、兑现隔了十几章、章段断开留空洞、一回合拖到八章。
这些在写第一章之前就能判，等写到第 40 章才发现，已经欠了读者三十章的债。

判四条硬规矩：
  ① 章段连续（上一回合止＋1 = 下一回合起，不留空洞）
  ② 回合长度 3—5 章
  ③ 兑现在本章段内，且相邻回合兑现类型不同
  ④ 兑现间隔 ≤ 8 章

用法：
    python 卷纲体检.py                     # 查 03_图纸_大纲与细纲/卷纲_*.md
    python 卷纲体检.py --file 卷纲_第1卷.md
    python 卷纲体检.py --min-rounds 3 --max-len 5 --max-gap 8
    python 卷纲体检.py --selftest

退出码：0 全过；1 有问题／读不到表。
"""

import argparse
import glob
import io
import os
import re
import sys
import tempfile


def find_root(start=None):
    d = os.path.abspath(start or os.getcwd())
    while True:
        if os.path.exists(os.path.join(d, '项目配置.json')):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def read(p):
    try:
        return io.open(p, encoding='utf-8').read()
    except UnicodeDecodeError:
        return io.open(p, encoding='utf-8-sig').read()


def parse_rows(text):
    """抓第一个「回合」表头的 markdown 表，返回 [dict]。"""
    lines = [l.rstrip() for l in text.splitlines()]
    start = None
    for i, l in enumerate(lines):
        if l.startswith('|') and '回合' in l and '章段' in l:
            start = i
            break
    if start is None:
        return []
    header = [c.strip() for c in lines[start].strip('|').split('|')]
    idx = {name: n for n, name in enumerate(header)}
    rows = []
    for l in lines[start + 1:]:
        if not l.startswith('|'):
            break
        cells = [c.strip() for c in l.strip('|').split('|')]
        if not cells or set(''.join(cells)) <= set('-: '):
            continue
        def cell(*names):
            for nm in names:
                for key, n in idx.items():
                    if nm in key and n < len(cells):
                        return cells[n]
            return ''
        rows.append({
            '回合': cell('回合'),
            '章段': cell('章段'),
            '兑现章': cell('兑现章'),
            '兑现类型': cell('兑现类型'),
            '玩法': cell('玩法', '事件'),
            '未决': cell('章末未决', '未决'),
        })
    return rows


def span(s):
    m = re.search(r'(\d+)\s*[—\-–~至]\s*(\d+)', s)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r'(\d+)', s)
    if m:
        n = int(m.group(1))
        return n, n
    return None


def chap(s):
    m = re.search(r'(\d+)', str(s))
    return int(m.group(1)) if m else None


def check_rows(rows, max_len=5, max_gap=8, min_rounds=3):
    problems, checks = [], []
    if not rows:
        return ['没有回合表（表头要含「回合」「章段」）'], []
    if len(rows) < min_rounds:
        problems.append(f'回合太少（{len(rows)} < {min_rounds}）—— 一卷至少三个回合')
    prev_end = None
    prev_type = None
    prev_end_ch = None
    for i, r in enumerate(rows, 1):
        sp = span(r['章段'])
        if not sp:
            problems.append(f'第{i}回合 章段读不出（要「起—止」）')
            continue
        a, b = sp
        if b < a:
            problems.append(f'第{i}回合 章段颠倒（{a}—{b}）')
        length = b - a + 1
        if not (3 <= length <= max_len):
            problems.append(f'第{i}回合 长度 {length} 章（要 3—{max_len}）')
        if prev_end is not None and a != prev_end + 1:
            problems.append(f'第{i}回合 章段断开：上一回合止于 {prev_end}，这里从 {a} 起')
        end_ch = chap(r['兑现章'])
        if end_ch is None or r['兑现章'] in ('—', '-', ''):
            problems.append(f'第{i}回合 没写兑现章')
        else:
            if not (a <= end_ch <= b):
                problems.append(f'第{i}回合 兑现章 {end_ch} 不在 {a}—{b} 内')
            if prev_end_ch is not None and end_ch - prev_end_ch > max_gap:
                problems.append(f'第{i}回合 兑现间隔 {end_ch - prev_end_ch} 章（> {max_gap}）')
            prev_end_ch = end_ch
        t = r['兑现类型']
        if t and t not in ('—', '-', '无兑现') and prev_type and t == prev_type:
            problems.append(f'第{i}回合 兑现类型与上一回合相同（{t}）—— 连着两次同型，读者会觉得重复')
        if t and t not in ('—', '-', '无兑现'):
            prev_type = t
        if not r['未决']:
            checks.append(f'第{i}回合 章末未决为空（提示项）')
        prev_end = b
    return problems, checks


def check_file(path, **kw):
    text = read(path)
    rows = parse_rows(text)
    problems, checks = check_rows(rows, **kw)
    name = os.path.basename(path)
    for c in checks:
        print(f'CHECK  {c}')
    if problems:
        print(f'\n{name}: FAIL（{len(rows)} 回合）')
        for p in problems:
            print('  -', p)
        return 1
    print(f'\n{name}: PASS（{len(rows)} 回合）')
    return 0


HEAD = '''# 第 1 卷 · 卷名

## 回合表

| 回合 | 章段 | 兑现章 | 兑现类型 | 玩法／事件 | 章末未决 |
|---|---|---|---|---|---|
'''


def selftest():
    d = tempfile.mkdtemp(prefix='jipu-vol-')
    good = HEAD + '| 1 | 1—4 | 第4章 | 资源 | 拿到骨矛 | 追兵进山 |\n' \
                  '| 2 | 5—8 | 第8章 | 打脸 | 当众验货逼出规矩 | 规矩只保三天 |\n' \
                  '| 3 | 9—12 | 第12章 | 揭秘 | 铜牌旧印对上死人 | 死人姓什么 |\n'
    gaps = HEAD + '| 1 | 1—4 | 第4章 | 资源 | a | x |\n' \
                  '| 2 | 6—9 | 第9章 | 打脸 | b | y |\n' \
                  '| 3 | 10—13 | 第13章 | 揭秘 | c | z |\n'
    same = HEAD + '| 1 | 1—4 | 第4章 | 打脸 | a | x |\n' \
                  '| 2 | 5—8 | 第8章 | 打脸 | b | y |\n' \
                  '| 3 | 9—12 | 第12章 | 揭秘 | c | z |\n'
    far = HEAD + '| 1 | 1—4 | 第4章 | 资源 | a | x |\n' \
                 '| 2 | 5—8 | 第8章 | 打脸 | b | y |\n' \
                 '| 3 | 9—12 | 第12章 | 揭秘 | c | z |\n' \
                 '| 4 | 13—26 | 第26章 | 成长 | d | w |\n'
    res = {}
    for name, txt in [('good', good), ('gaps', gaps), ('same', same), ('far', far)]:
        p = os.path.join(d, f'卷纲_{name}.md')
        io.open(p, 'w', encoding='utf-8').write(txt)
        res[name] = check_file(p)
    import shutil
    shutil.rmtree(d, ignore_errors=True)
    ok = res['good'] == 0 and res['gaps'] == 1 and res['same'] == 1 and res['far'] == 1
    print(f'\n自检：{"通过" if ok else "失败"}（齐 {res["good"]}／断段 {res["gaps"]}／同型 {res["same"]}／间隔远 {res["far"]}）')
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description='卷纲体检（回合表：连续／长度／兑现／同型）')
    ap.add_argument('--file', action='append', default=[])
    ap.add_argument('--max-len', type=int, default=5)
    ap.add_argument('--max-gap', type=int, default=8)
    ap.add_argument('--min-rounds', type=int, default=3)
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    kw = dict(max_len=a.max_len, max_gap=a.max_gap, min_rounds=a.min_rounds)
    files = a.file
    if not files:
        root = find_root()
        if root:
            pat = os.path.join(root, '03_图纸_大纲与细纲', '卷纲_*.md')
            files = sorted(glob.glob(pat))
    if not files:
        print('[停] 没有 卷纲_*.md')
        sys.exit(1)
    rc = 0
    for f in files:
        rc = check_file(f, **kw) or rc
    sys.exit(rc)


if __name__ == '__main__':
    main()
