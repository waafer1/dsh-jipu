# -*- coding: utf-8 -*-
"""
选型体检.py —— 12 行选型卡填满了没有（新书第一道门）

为什么卡这一道：空着的格子会被"默认值"悄悄填上——类目没定就开写，写到第三章
才发现读者点开看的不是这个。**填不满就回去问，不许留空当默认。**

查 `02_设定_世界与角色/题材定位.md` 的三列表（# / 项 / 填什么）：
第三列（或最后一列）为空的，逐行报缺。

用法：
    python 选型体检.py
    python 选型体检.py --file 路径/题材定位.md
    python 选型体检.py --selftest
退出码：缺行 → 1。
"""

import argparse
import re
import sys
from pathlib import Path

NEED = 12


def find_card():
    import os
    bases = []
    env = os.environ.get("JIPU_ROOT")
    if env:
        bases.append(Path(env))
    cur = Path.cwd().resolve()
    bases += [cur] + list(cur.parents)
    for b in bases:
        f = b / "02_设定_世界与角色" / "题材定位.md"
        if f.exists():
            return f
    return None


def check(path):
    text = path.read_text(encoding="utf-8")
    rows = []
    for line in text.split("\n"):
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        if set(cells[0]) <= set("-: "):     # 分隔行
            continue
        if cells[0] in ("#", "序", "项"):
            continue
        rows.append((cells[0], cells[1] if len(cells) > 1 else "", cells[-1]))

    missing = [(no, item) for no, item, val in rows if not val or val in ("", "—", "-")]
    print(f"\n=== 选型体检 · {path.name} ===")
    print(f"读到 {len(rows)} 行，需要 {NEED} 行")
    if len(rows) < NEED:
        print(f"  [缺] 表格只有 {len(rows)} 行，模板应为 {NEED} 行")
    for no, item in missing:
        print(f"  [空] 第 {no} 行「{item}」还没填")
    ok = len(rows) >= NEED and not missing
    print("\n选型体检：" + ("PASS，可以开写第一章" if ok else "FAIL —— 回去问，不许留空当默认"))
    return 0 if ok else 1


def selftest():
    import tempfile, shutil
    tmp = Path(tempfile.mkdtemp())
    d = tmp / "02_设定_世界与角色"
    d.mkdir(parents=True)
    head = "# 选型卡\n\n| # | 项 | 填什么 |\n|---|---|---|\n"
    full = head + "".join(f"| {i} | 项{i} | 值{i} |\n" for i in range(1, 13))
    (d / "题材定位.md").write_text(full, encoding="utf-8")
    print("自检 A：12 行填满应 PASS")
    rcA = check(d / "题材定位.md")

    (d / "题材定位.md").write_text(full.replace("| 值7 |", "|  |"), encoding="utf-8")
    print("\n自检 B：第 7 行空着应 FAIL")
    rcB = check(d / "题材定位.md")
    shutil.rmtree(tmp, ignore_errors=True)
    ok = rcA == 0 and rcB == 1
    print(f"\n自检结果：{'通过' if ok else '失败'}（A {rcA} / B {rcB}）")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="选型卡完整性检查")
    ap.add_argument("--file")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(selftest())
    p = Path(args.file) if args.file else find_card()
    if p is None or not p.exists():
        print("[停] 找不到 02_设定_世界与角色/题材定位.md —— 先确认项目根")
        sys.exit(1)
    sys.exit(check(p))


if __name__ == "__main__":
    main()
