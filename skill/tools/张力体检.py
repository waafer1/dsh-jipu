# -*- coding: utf-8 -*-
"""
张力体检.py —— 让"张力账本"真的有人读

为什么有它：1.36.0 铺了 `06_追踪_状态记录/张力账本.md`，但全库没有任何脚本读它
（研究报告 §F7）：文件在、无人强制，跟"文风基准从来没有文件"是同一种失败。

它量四件事（都只报数，出 CHECK 不进合门）：
  1. **这一章记没记**：账本里有没有第 N 章那一行；没记＝这一章没人回答"读者在等什么"。
  2. **中间压了几次**：0 次＝一路顺水，读者没有"要不要看下去"的选择；1 次＝压得太薄。
  3. **结尾多知道了什么**：空着＝章末没有信息增量，读者拿到的是"又过了一天"。
  4. **劲从哪儿来**（人／物／钱／时间／怕）：单一来源占比 >60%，或同一来源连着 ≥3 章
     ＝这本书只有一个引擎（研究报告 §F9 说的"骨架同构"在动力层的表现）。

账本格式（`开项目.py` 铺的模板就是这个表头）：
    | 章 | 开章读者想知道什么 | 中间压了几次 | 结尾多知道了什么 | 劲从哪儿来（人／物／钱／时间／怕） |
    | 001 | 门板钉不住，他赔得起吗 | 2 | 他身上的纹是真的 | 钱 |

用法：
    python 张力体检.py 006        # 只查这一章 + 全书分布
    python 张力体检.py            # 全书分布
    python 张力体检.py --selftest

退出码：0 正常（CHECK 不拦）；--strict 有 CHECK 则 1。
"""

import argparse
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

KEYS = ("人", "物", "钱", "时间", "怕")
SINGLE_SOURCE_MAX = 0.60
RUN_SAME_MAX = 3


def find_root() -> Path:
    import os
    env = os.environ.get("JIPU_ROOT")
    if env and (Path(env) / "项目配置.json").exists():
        return Path(env)
    cur = Path.cwd().resolve()
    for base in [cur] + list(cur.parents):
        if (base / "项目配置.json").exists():
            return base
    return cur


def sheet_path(root: Path) -> Path:
    return root / "06_追踪_状态记录" / "张力账本.md"


def _cells(line: str):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse(root: Path):
    """返回 {章号: {想知, 压, 多知, 劲}}。认不出的行跳过。"""
    p = sheet_path(root)
    if not p.exists():
        return None
    rows = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = _cells(line)
        if len(cells) < 5:
            continue
        num = re.fullmatch(r"\**(\d{1,4})\**", cells[0])
        if not num:
            continue
        n = int(num.group(1))
        rows[n] = {
            "想知": cells[1],
            "压": cells[2],
            "多知": cells[3],
            "劲": cells[4],
        }
    return rows


def _num(s: str):
    m = re.search(r"\d+", s or "")
    return int(m.group(0)) if m else None


def _source(s: str):
    for k in KEYS:
        if k in (s or ""):
            return k
    return (s or "").strip() or None


def judge(root: Path, chapter=None, strict=False) -> int:
    rows = parse(root)
    print("\n=== 张力体检 ===")
    if rows is None:
        print("  CHECK  没有 `06_追踪_状态记录/张力账本.md`——这本书没人记过张力")
        return 1 if strict else 0
    if not rows:
        print("  CHECK  张力账本是空的（表头之外一行没填）——登记要从第 1 章开始")
        return 1 if strict else 0

    nums = sorted(rows)
    checks = []

    if chapter is not None:
        n = int(chapter)
        if n not in rows:
            checks.append(f"第 {n:03d} 章没登记张力（账本里最新是第 {max(nums):03d} 章）")
        else:
            r = rows[n]
            print(f"第 {n:03d} 章：想知「{r['想知'] or '（空）'}」／压 {r['压'] or '（空）'} 次"
                  f"／多知「{r['多知'] or '（空）'}」／劲 {r['劲'] or '（空）'}")
            p = _num(r["压"])
            if p is None:
                checks.append(f"第 {n:03d} 章「中间压了几次」没填数字")
            elif p <= 0:
                checks.append(f"第 {n:03d} 章压 0 次——一路顺水，读者没有「要不要看下去」的选择")
            elif p == 1:
                checks.append(f"第 {n:03d} 章只压 1 次——薄；一章至少两次才有起伏")
            if not r["多知"]:
                checks.append(f"第 {n:03d} 章「结尾多知道了什么」空着——章末没有信息增量")
            if not r["想知"]:
                checks.append(f"第 {n:03d} 章「开章读者想知道什么」空着——读者没有等的理由")

    # 全书分布
    srcs = [_source(rows[n]["劲"]) for n in nums]
    known = [s for s in srcs if s]
    if known:
        from collections import Counter
        c = Counter(known)
        top, cnt = c.most_common(1)[0]
        ratio = cnt / len(known)
        print(f"驱动力分布：{dict(c)}（{len(known)} 章）")
        if ratio > SINGLE_SOURCE_MAX and len(known) >= 5:
            checks.append(f"「{top}」占了 {ratio:.0%} 的章（>{SINGLE_SOURCE_MAX:.0%}）——这本书只有一个引擎")
    # 同一驱动力连续 ≥3 章
    run, run_src, worst = 0, None, (0, None)
    for s in srcs:
        if s and s == run_src:
            run += 1
        else:
            run, run_src = 1, s
        if run > worst[0]:
            worst = (run, run_src)
    if worst[0] >= RUN_SAME_MAX and worst[1]:
        checks.append(f"「{worst[1]}」连着 {worst[0]} 章当驱动力（≥{RUN_SAME_MAX}）——换个引擎")

    # 压的次数分布
    press = [(n, _num(rows[n]["压"])) for n in nums]
    thin = [n for n, p in press if p is not None and p <= 1]
    if len(thin) >= 3:
        checks.append(f"{len(thin)} 章压 ≤1 次（{', '.join(f'{n:03d}' for n in thin[:6])}…）"
                      "——整本书的张力都靠别的章在扛")

    if checks:
        print("CHECK（不进合门，命中即改）：")
        for c in checks:
            print(f"  CHECK  {c}")
    else:
        print("PASS  这一章的张力记全了，全书驱动力也有变化")
    return 1 if (checks and strict) else 0


def selftest():
    import tempfile
    import shutil
    root = Path(tempfile.mkdtemp())
    (root / "06_追踪_状态记录").mkdir(parents=True)
    (root / "项目配置.json").write_text("{}", encoding="utf-8")
    head = ("| 章 | 开章读者想知道什么 | 中间压了几次 | 结尾多知道了什么 | 劲从哪儿来（人／物／钱／时间／怕） |\n"
            "|---|---|---|---|---|\n")
    good = head + "".join(
        f"| {i:03d} | 他想不想还债 | {2 + i % 2} | 又多知道一件事 | {KEYS[i % 5]} |\n"
        for i in range(1, 6))
    sheet_path(root).write_text(good, encoding="utf-8")
    print("自检 A：五章记全、驱动力有变化 → 应 0 CHECK")
    rcA = judge(root, 3, strict=True)

    bad = head + "".join(f"| {i:03d} |  | 0 |  | 钱 |\n" for i in range(1, 7))
    sheet_path(root).write_text(bad, encoding="utf-8")
    print("\n自检 B：没想知／压 0 次／单一驱动力 → 应 CHECK（strict 1）")
    rcB = judge(root, 2, strict=True)

    sheet_path(root).unlink()
    print("\n自检 C：没有账本 → 应 CHECK（strict 1）")
    rcC = judge(root, None, strict=True)

    shutil.rmtree(root, ignore_errors=True)
    ok = (rcA == 0) and (rcB == 1) and (rcC == 1)
    print(f"\n自检结果：{'通过' if ok else '失败'}（A {rcA} / B {rcB} / C {rcC}）")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="张力体检：让人读张力账本")
    ap.add_argument("chapter", nargs="?")
    ap.add_argument("--strict", action="store_true", help="有 CHECK 就 exit 1")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        sys.exit(selftest())
    root = find_root()
    sys.exit(judge(root, args.chapter, args.strict))


if __name__ == "__main__":
    main()
