#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""仿写合规.py —— 对来源文本查重：连续 N 字雷同即打回。

用法：
  python 仿写合规.py --source 来源文本/某书.txt
  python 仿写合规.py --source 来源文本/          # 目录，递归读 .txt/.md
  python 仿写合规.py --file 04_正文_成品/第012章_*.md --min 20
  python 仿写合规.py --selftest

口径：
  - 归一化：去空白与标点、统一小写，再比连续 N 字（默认 20）。
  - 来源默认 `06_追踪_状态账本/来源文本/`；没有就只报“未配置来源”。
  - 只比“结构来源文本”，不比计谱 assets 里的摘要（摘要本就不是原文）。
  - 命中即 exit 1；命中片段打印归一化后的 20 字，便于回改。
"""
import argparse
import glob
import io
import os
import re
import sys
import tempfile

PUNCT = re.compile(r'[\s，。！？、；：“”‘’（）()\[\]【】《》<>…—\-.,!?;:\'"`~·]+')


def norm(s):
    return PUNCT.sub('', s).lower()


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
        return io.open(p, encoding='utf-8', errors='ignore').read()
    except FileNotFoundError:
        return ''


def gather_sources(specs, root):
    files = []
    if not specs:
        d = os.path.join(root or '.', '06_追踪_状态账本', '来源文本')
        if os.path.isdir(d):
            specs = [d]
    for s in specs:
        if os.path.isdir(s):
            for ext in ('*.txt', '*.md'):
                files.extend(sorted(glob.glob(os.path.join(s, '**', ext), recursive=True)))
        elif os.path.isfile(s):
            files.append(s)
    return files


def build_index(files, n):
    idx = {}
    for f in files:
        t = norm(read(f))
        for i in range(len(t) - n + 1):
            g = t[i:i + n]
            if g not in idx:
                idx[g] = os.path.basename(f)
    return idx


def scan(file_path, idx, n):
    hits = []
    for ln, line in enumerate(read(file_path).splitlines(), 1):
        t = norm(line)
        for i in range(len(t) - n + 1):
            g = t[i:i + n]
            if g in idx:
                hits.append((ln, g, idx[g]))
                break
    return hits


def check(specs, file_paths, n, root):
    files = gather_sources(specs, root)
    if not files:
        print('[停] 没有来源文本。把来源放到 `06_追踪_状态账本/来源文本/`，或用 --source 指定。')
        return 1
    print(f'来源 {len(files)} 个，阈值 {n} 字')
    idx = build_index(files, n)
    print(f'索引 {len(idx)} 条 {n}-gram')
    total = 0
    for fp in file_paths:
        hits = scan(fp, idx, n)
        if hits:
            print(f'\n[雷同] {os.path.basename(fp)}：{len(hits)} 处')
            for ln, g, src in hits[:10]:
                print(f'  行 {ln}｜来源 {src}｜{g}')
        total += len(hits)
    if total:
        print(f'\nFAIL：共 {total} 处连续 {n} 字雷同。改法：换名、换物、换关系，或整句重写。')
        return 1
    print('\nPASS：无连续雷同。')
    return 0


def selftest():
    d = tempfile.mkdtemp(prefix='jipu-plag-')
    src = os.path.join(d, 'source.txt')
    io.open(src, 'w', encoding='utf-8').write(
        '他站在炭棚口，把湿炭捏碎，粉末从指缝里漏下去，风一吹就散。\n'
        '掌柜报了价，他没有还，只问了一句：这价能挂几天。\n')
    man = os.path.join(d, 'manuscript.md')
    io.open(man, 'w', encoding='utf-8').write(
        '他站在炭棚口，把湿炭捏碎，粉末从指缝里漏下去，风一吹就散。\n')
    rc_bad = check([src], [man], 20, d)
    io.open(man, 'w', encoding='utf-8').write(
        '炭棚门口，他捏了一把湿炭，捻开，黑粉顺着指头缝往下掉。\n')
    rc_ok = check([src], [man], 20, d)
    import shutil
    shutil.rmtree(d, ignore_errors=True)
    ok = rc_bad == 1 and rc_ok == 0
    print(f'\n自检：{"通过" if ok else "失败"}（雷同 {rc_bad}／改写 {rc_ok}）')
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description='对来源文本查重（连续 N 字）')
    ap.add_argument('--source', action='append', default=[], help='来源文件或目录，可重复')
    ap.add_argument('--file', action='append', default=[], help='待查正文，可重复；默认全部 04_正文_成品')
    ap.add_argument('--min', type=int, default=20)
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()

    if a.selftest:
        sys.exit(selftest())

    root = find_root()
    files = a.file
    if not files and root:
        files = sorted(glob.glob(os.path.join(root, '04_正文_成品', '第*章_*.md')))
    if not files:
        print('[停] 没有待查正文')
        sys.exit(1)
    sys.exit(check(a.source, files, max(8, a.min), root))


if __name__ == '__main__':
    main()
