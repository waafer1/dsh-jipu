#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""种子台账.py —— 把用过的主题种子记进桥段账本，防重复。

用法：
  python 种子台账.py --list --genre 01 [--role 主线]
  python 种子台账.py --check "试丹"
  python 种子台账.py --seed "他靠替人试丹活着" --chapter 012 [--role 主线]
  python 种子台账.py --selftest

口径：
  - 项目根靠向上找 项目配置.json；也可 --project 指定。
  - 记录写进 `06_追踪_状态账本/桥段账本.md` 的「种子使用记录」一节；没有就新建。
  - 重复判定：规范化后前 12 字相同即视为同一条；也查 04_正文_成品 里是否已出现。
退出码：0 正常；1 出错或被判重复；--selftest 失败 1。
"""
import argparse
import glob
import io
import os
import re
import sys
import tempfile
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(os.path.dirname(HERE), "assets", "主题灵感库")
SECTION = "## 种子使用记录"
HEADER = "| 日期 | 章 | 种子 | 类型 |\n|---|---|---|---|\n"


def find_root(start=None):
    d = os.path.abspath(start or os.getcwd())
    for _ in range(8):
        if os.path.isfile(os.path.join(d, "项目配置.json")):
            return d
        nd = os.path.dirname(d)
        if nd == d:
            break
        d = nd
    return None


def norm(s):
    return re.sub(r"[\s，。！？、；：“”‘’（）()\-—…]", "", s)


def read(p):
    try:
        return io.open(p, encoding="utf-8").read()
    except FileNotFoundError:
        return ""


def write(p, s):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)


def ledger_path(root):
    return os.path.join(root, "06_追踪_状态账本", "桥段账本.md")


def in_ledger(root, seed):
    text = norm(read(ledger_path(root)))
    key = norm(seed)[:12]
    return key and key in text


def in_manuscript(root, seed):
    key = norm(seed)[:12]
    if not key:
        return None
    for p in glob.glob(os.path.join(root, "04_正文_成品", "第*章_*.md")):
        if key in norm(read(p)):
            return os.path.basename(p)
    return None


def append(root, seed, chapter, role):
    p = ledger_path(root)
    text = read(p)
    d = date.today().isoformat()
    row = f"| {d} | {chapter} | {seed} | {role} |\n"
    if SECTION not in text:
        text = text.rstrip() + f"\n\n{SECTION}\n\n{HEADER}"
    idx = text.index(SECTION)
    head = text[:idx]
    body = text[idx:]
    # 插到本节表格的最后一行之后
    lines = body.splitlines(keepends=True)
    last = 0
    for i, line in enumerate(lines):
        if line.strip().startswith("|"):
            last = i
    lines.insert(last + 1, row)
    write(p, head + "".join(lines))
    return p


def list_seeds(genre=None, role=None):
    files = sorted(glob.glob(os.path.join(ASSETS, "[0-9][0-9]-*.md")))
    out = []
    for f in files:
        name = os.path.basename(f)
        gid = name[:2]
        if genre and gid != str(genre).zfill(2):
            continue
        for line in read(f).splitlines():
            s = line.strip()
            if not s.startswith("|"):
                continue
            cells = [c.strip() for c in s.strip("|").split("|")]
            if len(cells) != 4 or cells[0] in ("一句钩子", "钩子") or set(cells[0]) <= set("-: "):
                continue
            if role and cells[3] != role:
                continue
            out.append((gid, name, cells))
    return out


def selftest():
    root = tempfile.mkdtemp(prefix="jipu-seed-")
    write(os.path.join(root, "项目配置.json"), '{"title":"t"}')
    write(ledger_path(root), "# 桥段账本\n\n| 桥段 | 怎么用的 | 冷却到 | 备注 |\n|---|---|---|---|\n")
    seed = "他靠替人试丹活着"
    assert not in_ledger(root, seed)
    p = append(root, seed, "012", "主线")
    assert in_ledger(root, seed), "append failed"
    assert in_ledger(root, "替人试丹活着"), "partial match failed"
    text = read(p)
    assert SECTION in text and "| 012 |" in text
    # 正文命中
    write(os.path.join(root, "04_正文_成品", "第012章_试丹.md"), "他靠替人试丹活着，直到试出问题。")
    assert in_manuscript(root, seed) == "第012章_试丹.md"
    seeds = list_seeds("01", "主线")
    assert len(seeds) >= 1, "list failed"
    print("自检通过：追加、去重、正文命中、列种子四项 OK")
    return 0


def main():
    ap = argparse.ArgumentParser(description="种子台账：记录用过的主题种子")
    ap.add_argument("--project")
    ap.add_argument("--seed")
    ap.add_argument("--chapter", default="")
    ap.add_argument("--role")
    ap.add_argument("--check")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--genre")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        sys.exit(selftest())

    if a.list:
        rows = list_seeds(a.genre, a.role)
        for gid, name, cells in rows:
            print(f"{gid} | {cells[3]} | {cells[0]}")
        print(f"\n共 {len(rows)} 条")
        return

    root = find_root(a.project)
    if not root:
        print("[停] 找不到项目根（需要 项目配置.json）")
        sys.exit(1)

    if a.check:
        hit_ch = in_manuscript(root, a.check)
        if in_ledger(root, a.check):
            print(f"[已用] 账本里有：{a.check}")
            sys.exit(1)
        if hit_ch:
            print(f"[已用] 正文 {hit_ch} 已出现：{a.check}")
            sys.exit(1)
        print(f"[未用] {a.check}")
        return

    if not a.seed:
        ap.print_help()
        sys.exit(1)
    if in_ledger(root, a.seed) or in_manuscript(root, a.seed):
        print(f"[重复] 已用过：{a.seed}")
        sys.exit(1)
    p = append(root, a.seed, a.chapter or "-", a.role or "两用")
    print(f"[写入] {p}")
    print(f"  {a.chapter or '-'} | {a.role or '两用'} | {a.seed}")


if __name__ == "__main__":
    main()
