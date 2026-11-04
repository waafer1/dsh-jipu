# -*- coding: utf-8 -*-
"""
章检.py —— 合门三项（这一章算不算写完）

三项全 PASS 才算定稿，少一项不许开下一章：
  ① 句检 blocking = 0
  ② 审计报告里有那一行「宾语盘点：N 条」——没有这行等于没盘点
  ③ N 等于句检当场数出来的条数——**数字对不上就是没写完**

为什么单列成一个脚本：审计报告是人写的，人可以少写一条；这三个数是机器算的，
两边对不上立刻暴露。这是"数出来的才算数"的最后一道闸。

用法：
    python 章检.py 001
    python 章检.py 001 --audit 路径/审计.md
    python 章检.py --selftest
退出码：三项全过 0，否则 1。
"""

import argparse
import glob
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


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


def locate_chapter(root: Path, chapter: str):
    hits = glob.glob(str(root / "04_正文_成品" / f"第{chapter}章_*.md"))
    if not hits:
        hits = glob.glob(str(root / "04_正文_成品" / f"第0*{int(chapter)}章_*.md"))
    return Path(hits[0]) if hits else None


def locate_audit(root: Path, chapter: str, given=None):
    if given:
        return Path(given)
    num = f"{int(chapter):03d}"
    cands = [
        root / "05_质检_审计评审节奏" / "审计" / f"第{num}章_审计.md",
        root / "05_质检_审计评审节奏" / "审计" / f"第{chapter}章_审计.md",
    ]
    for c in cands:
        if c.exists():
            return c
    hits = glob.glob(str(root / "05_质检_审计评审节奏" / "审计" / f"*{int(chapter)}*审计*.md"))
    return Path(hits[0]) if hits else None


def run(script, args, cwd):
    r = subprocess.run([sys.executable, str(HERE / script)] + args,
                       capture_output=True, text=True, encoding="utf-8",
                       timeout=120, cwd=str(cwd))
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main_check(chapter, chapter_file, audit_file, root):
    rows = []

    rc, out = run("句检.py", [str(chapter_file)], root)
    rows.append(("① 句检 blocking=0", rc == 0, _g(out, r"合计 blocking (\d+)") + " 条"))

    rc2, out2 = run("句检.py", ["--count-object", str(chapter_file)], root)
    actual = _g(out2, r"宾语盘点：(\d+) 条")

    if audit_file is None or not audit_file.exists():
        rows.append(("② 审计有「宾语盘点：N 条」", False, "审计文件找不到"))
        rows.append(("③ 条数与句检相等", False, "无从比对"))
    else:
        text = audit_file.read_text(encoding="utf-8")
        m = re.search(r"宾语盘点\*{0,2}\s*[：:]\s*(\d+)\s*条", text)
        if not m:
            rows.append(("② 审计有「宾语盘点：N 条」", False, f"{audit_file.name} 缺这一行"))
            rows.append(("③ 条数与句检相等", False, "无从比对"))
        else:
            declared = m.group(1)
            rows.append(("② 审计有「宾语盘点：N 条」", True, f"{declared} 条（{audit_file.name}）"))
            rows.append(("③ 条数与句检相等", declared == actual, f"审计 {declared} ／句检 {actual}"))

    print(f"\n=== 章检 · 第 {chapter} 章 ===")
    fails = 0
    for name, ok, note in rows:
        print(f"  {'PASS' if ok else 'FAIL'}  {name:<24} {note}")
        fails += (not ok)
    print("\n章检：三项全 PASS，这章算写完" if fails == 0 else f"章检：FAIL（{fails} 项）—— 不许开下一章")
    return 0 if fails == 0 else 1


def _g(text, pattern):
    m = re.search(pattern, text)
    return m.group(1) if m else "?"


def selftest():
    import tempfile, json, shutil
    root = Path(tempfile.mkdtemp())
    (root / "04_正文_成品").mkdir(parents=True)
    (root / "05_质检_审计评审节奏" / "审计").mkdir(parents=True)
    (root / "06_追踪_状态账本").mkdir(parents=True)
    (root / "06_追踪_状态账本" / "数字登记.md").write_text("| 3 | 株 |\n", encoding="utf-8")
    (root / "项目配置.json").write_text(json.dumps({"gate": {}, "lexicon": {"banned_words": []}}, ensure_ascii=False), encoding="utf-8")
    body = "他把三株草塞进怀里。草被风吹得响。\n“走吧。”老板说。\n"
    (root / "04_正文_成品" / "第001章_塞草.md").write_text(body, encoding="utf-8")

    audit_ok = (root / "05_质检_审计评审节奏" / "审计" / "第001章_审计.md")
    audit_ok.write_text("## 读数\n- **宾语盘点**：2 条，逐条看过，改 0 处。\n", encoding="utf-8")
    print("自检 A：审计写 2 条（实际 2）应 PASS")
    rcA = main_check("001", root / "04_正文_成品" / "第001章_塞草.md", audit_ok, root)

    audit_bad = (root / "05_质检_审计评审节奏" / "审计" / "第001章_审计_bad.md")
    audit_bad.write_text("## 读数\n- **宾语盘点**：5 条\n", encoding="utf-8")
    print("\n自检 B：审计写 5 条（实际 2）应 FAIL")
    rcB = main_check("001", root / "04_正文_成品" / "第001章_塞草.md", audit_bad, root)

    audit_none = (root / "05_质检_审计评审节奏" / "审计" / "第001章_审计_none.md")
    audit_none.write_text("## 读数\n- 都挺好\n", encoding="utf-8")
    print("\n自检 C：审计没写那一行 应 FAIL")
    rcC = main_check("001", root / "04_正文_成品" / "第001章_塞草.md", audit_none, root)

    shutil.rmtree(root, ignore_errors=True)
    ok = rcA == 0 and rcB == 1 and rcC == 1
    print(f"\n自检结果：{'通过' if ok else '失败'}（A {rcA} / B {rcB} / C {rcC}）")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="合门三项")
    ap.add_argument("chapter", nargs="?")
    ap.add_argument("--audit")
    ap.add_argument("--file")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(selftest())
    if not args.chapter:
        ap.print_help()
        sys.exit(1)

    root = find_root()
    cf = Path(args.file) if args.file else locate_chapter(root, args.chapter)
    if cf is None or not cf.exists():
        print(f"[停] 找不到第 {args.chapter} 章正文")
        sys.exit(1)
    af = locate_audit(root, args.chapter, args.audit)
    sys.exit(main_check(args.chapter, cf, af, root))


if __name__ == "__main__":
    main()
