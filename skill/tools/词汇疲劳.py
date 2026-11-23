#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""词汇疲劳.py —— 同一句形在一章里重复到读者能背出来。

只数「连续 6—10 字的原样重复」：短词重复是人名和物件的正常复用，长串重复
才是作者的手癖（同一个动作描写、同一个转折句式、同一句判断）。

用法：
  python 词汇疲劳.py                       # 项目根下全部正文
  python 词汇疲劳.py --file 第012章_*.md
  python 词汇疲劳.py --min 3 --write       # 6 字以上、出现 ≥3 次报 FAIL
  python 词汇疲劳.py --selftest

判据（默认值）：
  · 6—10 字的串出现 ≥3 次 → FAIL（列前 10 条，带出现次数）
  · 句首 6 字相同 ≥4 次 → WARN（同一段起手式）
退出码：0 通过（可带 WARN）；1 有重复串；--selftest 失败 1。
"""
import argparse
import collections
import glob
import io
import os
import re
import sys
import tempfile

MIN_LEN = 6
MAX_LEN = 10
HIT = 3
CJK = re.compile(r'^[\u4e00-\u9fa5]+$')


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
        return io.open(p, encoding='utf-8').read()
    except FileNotFoundError:
        return ''


def body_text(text):
    """去掉标题行和引用行，只留正文。"""
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith('#') or s.startswith('>') or s.startswith('---'):
            continue
        out.append(s)
    return '\n'.join(out)


def repeated(text, n, min_count):
    counts = collections.Counter()
    for m in re.finditer(r'[\u4e00-\u9fa5]+', text):
        s = m.group(0)
        for i in range(len(s) - n + 1):
            gram = s[i:i + n]
            if CJK.match(gram):
                counts[gram] += 1
    return [(g, c) for g, c in counts.items() if c >= min_count]


def check(path, min_count=HIT, out=None):
    text = body_text(read(path))
    name = os.path.basename(path)
    if not text.strip():
        print('[停] 读不到正文：%s' % path)
        return 1, []
    print('\n%s（%d 字）' % (name, len(re.sub(r'\s', '', text))))
    hits = []
    # 长串优先：能命中的最长串最像手癖
    for n in range(MAX_LEN, MIN_LEN - 1, -1):
        for gram, c in repeated(text, n, min_count):
            hits.append((gram, c, n))
    # 去掉被更长串完全覆盖的短串，以及只差一个字的错位串（同一个手癖的两种切法）
    kept = []
    for gram, c, n in sorted(hits, key=lambda x: (-x[2], -x[1])):
        dup = False
        for g, _, _ in kept:
            if gram == g or gram in g or g in gram:
                dup = True
                break
            if gram[1:] in g or g[1:] in gram or gram[:-1] in g or g[:-1] in gram:
                dup = True
                break
        if not dup:
            kept.append((gram, c, n))
    lines = []
    if kept:
        print('重复串：')
        for gram, c, n in kept[:10]:
            print('  ×%d  %s' % (c, gram))
            lines.append('- ×%d `%s`' % (c, gram))
    else:
        print('无 %d 字以上重复 ≥%d 次的串' % (MIN_LEN, min_count))
    # 句首起手式
    heads = collections.Counter()
    for line in text.splitlines():
        s = line.strip()
        if len(s) >= MIN_LEN:
            heads[s[:MIN_LEN]] += 1
    bad_heads = [(h, c) for h, c in heads.items() if c >= 4]
    if bad_heads:
        for h, c in sorted(bad_heads, key=lambda x: -x[1])[:5]:
            print('WARN 句首 ×%d  %s…' % (c, h))
    rc = 1 if kept else 0
    print('FAIL —— %d 条重复串' % len(kept) if kept else 'PASS')
    if out is not None:
        out.extend(lines)
    return rc, kept


def write_log(root, lines):
    d = os.path.join(root, '05_质检_审计评审节奏', '审计')
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, '词汇疲劳_全.md')
    io.open(p, 'w', encoding='utf-8').write('# 词汇疲劳\n\n' + ('\n'.join(lines) if lines else '无重复串。') + '\n')
    print('\n[写] %s' % p)


def selftest():
    ok = True
    tmp = tempfile.mkdtemp(prefix='fatigue_')
    p1 = os.path.join(tmp, '第001章_重复.md')
    io.open(p1, 'w', encoding='utf-8').write(
        '他低头看着自己冻裂的双手，没说话。\n'
        '屋里很冷。他低头看着自己冻裂的双手，还是没说话。\n'
        '格雷站在门口。他又低头看着自己冻裂的双手，忽然笑了一下。\n')
    rc1, hits1 = check(p1)
    if rc1 != 1 or not any('冻裂' in g for g, _, _ in hits1):
        print('!! 用例一没报出来：rc=%s hits=%r' % (rc1, hits1))
        ok = False

    p2 = os.path.join(tmp, '第002章_干净.md')
    io.open(p2, 'w', encoding='utf-8').write(
        '他把石头塞进怀里，手指冻得发白。\n'
        '格雷敲了三下门，隔着楼板缝叫他的名字。\n'
        '灯灭之后，车底下传来一声很轻的响。\n')
    rc2, hits2 = check(p2)
    if rc2 != 0 or hits2:
        print('!! 用例二应通过：rc=%s hits=%r' % (rc2, hits2))
        ok = False
    print('\n自检：%s' % ('通过' if ok else '失败'))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--file', default=None)
    ap.add_argument('--root', default=None)
    ap.add_argument('--min', type=int, default=HIT)
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.file:
        files = [a.file]
        root = find_root(os.path.dirname(os.path.abspath(a.file)))
    else:
        root = find_root(a.root)
        files = sorted(glob.glob(os.path.join(root, '04_正文_成品', '第*章_*.md')))
    if not files:
        print('[停] 没找到正文（04_正文_成品/第NNN章_*.md）')
        return 1
    lines = []
    rc = 0
    for f in files:
        r, _ = check(f, max(2, a.min), lines)
        rc = max(rc, r)
    if a.write:
        write_log(root, lines)
    return rc


if __name__ == '__main__':
    sys.exit(main())
