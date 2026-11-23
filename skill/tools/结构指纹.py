#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""结构指纹.py —— 这一段是不是「一章写三遍」。

签名只取三项，都在细纲的必填字段里，不靠文笔判断：
  兑现型      细纲「爽点类型／类型」的第一个词
  换没换到    细纲「改势」写了东西（不是「无／没有／—」）
  章末未决    细纲「章末未决」写了东西（不是「无／没有／待定」）

相邻 N 章（默认 3）签名完全相同 → FAIL「一章写三遍」：读者读到的是同一场戏的
第三遍，哪怕每章的字都不一样。

用法：
  python 结构指纹.py                     # 项目根下全部细纲
  python 结构指纹.py --run 4             # 连续 4 章同签名才算
  python 结构指纹.py --write             # 落 05_质检_审计评审节奏/审计/结构指纹_全.md
  python 结构指纹.py --selftest

退出码：0 通过；1 有连续同签名；--selftest 失败 1。
"""
import argparse
import glob
import io
import os
import re
import sys
import tempfile

RUN_DEFAULT = 3
EMPTY_WORDS = ('无', '没有', '暂无', '待定', '—', '-', '略', '空')


def find_root(start=None):
    d = os.path.abspath(start or os.getcwd())
    for _ in range(8):
        if os.path.isfile(os.path.join(d, '项目配置.json')):
            return d
        nd = os.path.dirname(d)
        if nd == d:
            break
        d = nd
    return os.path.abspath(start or os.getcwd())


def read(p):
    try:
        return io.open(p, encoding='utf-8-sig').read()
    except FileNotFoundError:
        return ''


def field(text, names):
    for n in names:
        m = re.search(r'^\s*%s[：:]\s*(.+)$' % n, text, re.M)
        if m:
            return m.group(1).strip()
    return ''


def has_content(val):
    v = (val or '').strip()
    if not v:
        return False
    for w in EMPTY_WORDS:
        if v == w or v.startswith(w):
            return False
    return True


def signature(text):
    kind = field(text, ('爽点类型', '类型', '玩法定型', '母题'))
    kind = re.split(r'[／/、,，\s]', kind)[0] if kind else ''
    change = field(text, ('改势',))
    hook = field(text, ('章末未决',))
    return (kind or '?', has_content(change), has_content(hook))


def chapter_no(name):
    base = os.path.basename(name)
    m = re.search(r'第\s*(\d+)\s*章', base) or re.search(r'第\s*(\d+)', base)
    return int(m.group(1)) if m else 0


def volume_types(root):
    """从 卷纲_第N卷.md 的回合表取「章号 → 兑现类型」，细纲没写类型时用它兜底。"""
    got = {}
    for p in glob.glob(os.path.join(root, '03_图纸_大纲与细纲', '卷纲_第*卷.md')):
        text = read(p)
        lines = [l.rstrip() for l in text.splitlines()]
        start = None
        for i, l in enumerate(lines):
            if l.startswith('|') and '回合' in l and '章段' in l:
                start = i
                break
        if start is None:
            continue
        header = [c.strip() for c in lines[start].strip('|').split('|')]
        try:
            i_span = next(n for n, h in enumerate(header) if '章段' in h)
            i_type = next(n for n, h in enumerate(header) if '兑现类型' in h)
        except StopIteration:
            continue
        for l in lines[start + 1:]:
            if not l.startswith('|'):
                break
            cells = [c.strip() for c in l.strip('|').split('|')]
            if not cells or set(''.join(cells)) <= set('-: '):
                continue
            if max(i_span, i_type) >= len(cells):
                continue
            m = re.search(r'(\d+)\s*[—\-–~至]\s*(\d+)', cells[i_span])
            if not m:
                m = re.search(r'(\d+)', cells[i_span])
            if not m:
                continue
            a = int(m.group(1))
            b = int(m.group(2)) if m.lastindex and m.lastindex >= 2 else a
            for n in range(a, b + 1):
                got[n] = cells[i_type]
    return got


def collect(root):
    d = os.path.join(root, '03_图纸_大纲与细纲')
    files = glob.glob(os.path.join(d, '细纲_第*章.md'))
    if not files:                      # 老项目常写成 细纲_第001.md，也认
        files = glob.glob(os.path.join(d, '细纲_第*.md'))
    types = volume_types(root)
    rows = []
    for p in files:
        no = chapter_no(p)
        sig = signature(read(p))
        if sig[0] == '?' and no in types:
            sig = (types[no], sig[1], sig[2])
        rows.append((no, p, sig))
    rows.sort(key=lambda x: x[0])
    return rows


def find_runs(rows, run_len):
    runs = []
    i = 0
    while i < len(rows):
        j = i + 1
        while j < len(rows) and rows[j][2] == rows[i][2]:
            j += 1
        if j - i >= run_len:
            runs.append((i, j))
        i = j
    return runs


def fmt(sig):
    kind, change, hook = sig
    return '%s／%s／%s' % (kind, '换到' if change else '没换', '有钩' if hook else '没钩')


def report(rows, run_len):
    if not rows:
        print('[停] 没找到细纲（03_图纸_大纲与细纲/细纲_第NNN章.md）')
        return 1, ''
    lines = []
    for no, _, sig in rows:
        lines.append('第%03d章  %s' % (no, fmt(sig)))
    print('\n'.join(lines))
    runs = find_runs(rows, run_len)
    body = []
    if not runs:
        print('\nPASS —— %d 章签名各不相同或未连成 %d 章' % (len(rows), run_len))
    else:
        for i, j in runs:
            a, b = rows[i][0], rows[j - 1][0]
            print('\nFAIL —— 一章写三遍：第 %d—%d 章连着 %d 章同签名（%s）'
                  % (a, b, j - i, fmt(rows[i][2])))
            body.append('- 第 %d—%d 章同签名：%s' % (a, b, fmt(rows[i][2])))
        print('\n改法：换兑现型／换改势的兑现物／把章末的钩子从「等下一章」改成「这一章没解决」')
    return (1 if runs else 0), '\n'.join(body)


def write_log(root, rows, body):
    d = os.path.join(root, '05_质检_审计评审节奏', '审计')
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, '结构指纹_全.md')
    out = ['# 结构指纹（全）', '', '| 章 | 兑现型 | 换没换到 | 章末未决 |', '|---|---|---|---|']
    for no, _, (kind, change, hook) in rows:
        out.append('| %03d | %s | %s | %s |' % (no, kind, '换到' if change else '没换', '有' if hook else '无'))
    out.append('')
    out.append(body if body else '无连续同签名。')
    io.open(p, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    print('\n[写] %s' % p)


def selftest():
    ok = True
    tmp = tempfile.mkdtemp(prefix='fingerprint_')
    d = os.path.join(tmp, '03_图纸_大纲与细纲')
    os.makedirs(d)
    io.open(os.path.join(tmp, '项目配置.json'), 'w', encoding='utf-8').write('{}')

    def put(no, kind, change, hook):
        t = '爽点类型：%s\n改势：%s\n章末未决：%s\n' % (kind, change, hook)
        io.open(os.path.join(d, '细纲_第%03d章.md' % no), 'w', encoding='utf-8').write(t)

    for no in (1, 2, 3):
        put(no, '打脸', '换到一笔钱', '有人还在门外')
    put(4, '揭秘', '换到一张纸条', '纸条上是谁的字')
    for no in (5, 6, 7):
        put(no, '打脸', '换到一笔钱', '有人还在门外')
    rc, body = report_collect(tmp, 3)
    if rc != 1 or not body.startswith('- 第 1—3 章'):
        print('!! 用例一没报出来：rc=%s body=%r' % (rc, body))
        ok = False

    tmp2 = tempfile.mkdtemp(prefix='fingerprint_ok_')
    d2 = os.path.join(tmp2, '03_图纸_大纲与细纲')
    os.makedirs(d2)
    io.open(os.path.join(tmp2, '项目配置.json'), 'w', encoding='utf-8').write('{}')
    for i, (k, c, h) in enumerate([('打脸', '换到钱', '有人敲门'), ('揭秘', '无', '纸条'), ('压力', '换到伤', '追赶')], 1):
        t = '爽点类型：%s\n改势：%s\n章末未决：%s\n' % (k, c, h)
        io.open(os.path.join(d2, '细纲_第%03d章.md' % i), 'w', encoding='utf-8').write(t)
    rc2, _ = report_collect(tmp2, 3)
    if rc2 != 0:
        print('!! 用例二应通过：rc=%s' % rc2)
        ok = False

    print('\n自检：%s' % ('通过' if ok else '失败'))
    return 0 if ok else 1


def report_collect(root, run_len):
    rows = collect(root)
    rc, body = report(rows, run_len)
    return rc, body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=None)
    ap.add_argument('--run', type=int, default=RUN_DEFAULT)
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    root = find_root(a.root)
    rows = collect(root)
    rc, body = report(rows, max(2, a.run))
    if a.write and rows:
        write_log(root, rows, body)
    return rc


if __name__ == '__main__':
    sys.exit(main())
