# -*- coding: utf-8 -*-
"""
对白归属.py —— 找"孤岛对白"（连续纯引号段 ≥ 3）

病灶：连着三段以上只有引号、没有归属（谁在说、什么动作），读者会迷失在谁跟谁说话里。
判据：`references/02-正文口径.md`（连续纯引号段 ≤2）。

**但"≥3 段"不等于病**：内心独白、自言自语、街上的吆喝，本身不需要归属。
所以脚本只负责把每一串揪出来、给位置，判"孤岛（改）"还是"例外（过）"由人写。

用法：
    python 对白归属.py 04_正文_成品/第001章_*.md
    python 对白归属.py --min 3 <文件>      # 阈值默认 3
    python 对白归属.py --selftest
退出码恒 0（只报串，不判）。
"""

import argparse
import glob
import re
import sys
from pathlib import Path

RE_BLOCK = re.compile(r"“[^”]*”")


def strip_fm(t):
    if t.startswith("---"):
        e = t.find("\n---", 1)
        if e != -1:
            return t[e + 4:]
    return t


def is_pure_dialogue(p):
    blocks = RE_BLOCK.findall(p)
    return len(blocks) == 1 and RE_BLOCK.sub("", p).strip() == ""


def scan(path, min_run=3):
    text = strip_fm(Path(path).read_text(encoding="utf-8"))
    lines = text.split("\n")
    runs, cur = [], []
    for i, line in enumerate(lines, 1):
        p = line.strip()
        if not p:
            continue
        if is_pure_dialogue(p):
            cur.append((i, p))
        else:
            if len(cur) >= min_run:
                runs.append(cur)
            cur = []
    if len(cur) >= min_run:
        runs.append(cur)

    print(f"\n=== 对白归属 · {path} ===")
    print(f"连续纯引号段 ≥{min_run} 的串：{len(runs)} 串")
    for idx, run in enumerate(runs, 1):
        print(f"\n  串 {idx}：L{run[0][0]} 起，共 {len(run)} 段")
        for ln, s in run:
            print(f"    L{ln} {s[:40]}")
        print("    判定：______（孤岛改／例外过：内心独白·自言自语·街上吆喝）")
    if not runs:
        print("  没有孤岛串。")
    return len(runs)


def selftest():
    import tempfile, os
    sample = ("他推门进来。\n\n“走吧。”\n\n“去哪儿。”\n\n“随便。”\n\n他没动。\n\n“你怕。”\n\n“不怕。”\n")
    fd, p = tempfile.mkstemp(suffix=".md")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(sample)
    print("自检：应报 2 串（3 段＋2 段，阈值 3 时只报 1 串；用 min 2 应报 2 串）")
    n3 = scan(p, 3)
    n2 = scan(p, 2)
    os.remove(p)
    ok = n3 == 1 and n2 == 2
    print(f"\n自检结果：{'通过' if ok else '失败'}（min3={n3} / min2={n2}）")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="孤岛对白定位")
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--min", type=int, default=3)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(selftest())
    if not args.paths:
        ap.print_help()
        sys.exit(1)
    files = []
    for p in args.paths:
        hits = glob.glob(p)
        files.extend(hits if hits else [p])
    for f in files:
        try:
            scan(f, args.min)
        except FileNotFoundError:
            print(f"[跳过] 不存在：{f}")


if __name__ == "__main__":
    main()
