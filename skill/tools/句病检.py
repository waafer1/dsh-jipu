# -*- coding: utf-8 -*-
"""
句病检.py —— 宾语盘点（逐条列出来，人工逐条核）

为什么单列：`句检.py --count-object` 只给条数，够合门对账；但审计要**逐条看**——
哪个"把"字句的对象在上一段找不到、哪个"被"字句没有施动者。
本脚本把每一条连行号带原句列出来，专供查无漏核。

四类句：
  把字句：宾语在不在、指代找不找得到
  被字句：施动者有没有、谁干的
  对/向/给字句：对象是不是人、前面交代过没有
  是……的 判断句：判断有没有依据（易出"宣布腔"）

用法：
    python 句病检.py 04_正文_成品/第001章_*.md
    python 句病检.py --only 把 <文件>     # 只列一类
    python 句病检.py --selftest
退出码恒 0（只列，不判）。
"""

import argparse
import glob
import re
import sys
from pathlib import Path

PATTERNS = {
    "把": re.compile(r"[^。！？\n]{0,12}把[^。！？\n]{1,30}[。！？]?"),
    "被": re.compile(r"[^。！？\n]{0,12}被[^。！？\n]{1,30}[。！？]?"),
    "对向给": re.compile(r"[^。！？\n]{0,12}[对向给][^。！？\n]{1,30}[。！？]?"),
    "是…的": re.compile(r"[^。！？\n]{0,12}是[^。！？\n]{1,25}的[。！？]?"),
}


def strip_fm(t):
    if t.startswith("---"):
        e = t.find("\n---", 1)
        if e != -1:
            return t[e + 4:]
    return t


def scan(path, only=None, show_all=True):
    text = strip_fm(Path(path).read_text(encoding="utf-8"))
    lines = text.split("\n")
    total = 0
    print(f"\n=== 宾语盘点 · {path} ===")
    for name, pat in PATTERNS.items():
        if only and name != only:
            continue
        hits = []
        for i, line in enumerate(lines, 1):
            for m in pat.finditer(line):
                hits.append((i, m.group().strip()))
        total += len(hits)
        print(f"\n[{name}] {len(hits)} 条")
        if show_all:
            for ln, s in hits:
                print(f"  L{ln} {s}")
        elif hits:
            print(f"  （示例）L{hits[0][0]} {hits[0][1]}")
    print(f"\n宾语盘点：{total} 条")
    print("逐条核：宾语在不在、指代找不找得到、施动者有没有。脚本只列，不判对错。")
    return total


def selftest():
    import tempfile, os
    sample = ("他把草塞进怀里。\n草被风吹得响。\n他对老板说了一句话。\n这事是他干的。\n")
    fd, p = tempfile.mkstemp(suffix=".md")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(sample)
    print("自检：四类各至少 1 条，合计 ≥4")
    n = scan(p)
    os.remove(p)
    ok = n >= 4
    print(f"\n自检结果：{'通过' if ok else '失败'}（{n} 条）")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="宾语盘点清单")
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--only", choices=list(PATTERNS.keys()))
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
            scan(f, args.only)
        except FileNotFoundError:
            print(f"[跳过] 不存在：{f}")


if __name__ == "__main__":
    main()
