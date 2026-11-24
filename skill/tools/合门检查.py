# -*- coding: utf-8 -*-
"""
合门检查.py —— 合门前的"最后一问"：这一章的读数是不是改完以后的读数

`references/14-岗位能力模型.md` §十 早就点名要它（原本一直标着「待装」）：
    合门 | 拿豁免当通行证、改完不重跑 | 比对 §六 回路表与最近一次跑数时间 | 需 合门检查.py

它查的是**时间与痕迹**，不是文本质量——质量归 章体检／章检／文风靶：

  硬项（FAIL，exit 1）：
    H1 正文存在，且有对应审计
    H2 审计比正文新（正文改完必须重跑审计；这一条专治"改完不重跑"）
    H3 审计末尾有「回改：句级 N／场景级 M／细纲级 K」那一行（§六 回路表的落点）
    H4 有节奏/评审文件时，它们也不许比正文旧（T1/T2 才要求，T0 只查审计）

  CHECK（只报数，不进合门）：
    C1 审计里出现「豁免」，但同一行没写理由（拿豁免当通行证）
    C2 审计里出现「local／structural」回路判定，但没有对应的返工记录行
    C3 审计比最近一次 章体检 的输出旧（若项目里留了 `06_追踪_状态记录/体检时间.json`）
    C4 本章是 T2 档却缺 `盲评_第NNN章_*.md`（档位从 项目配置.json 的 gate.tier 读，缺省 T1）

用法：
    python 合门检查.py 001
    python 合门检查.py 001 --tier T2
    python 合门检查.py --all          # 全书画一遍，列出所有"改完没重跑"的章
    python 合门检查.py --selftest
退出码：硬项全过 0，否则 1。
"""

import argparse
import glob
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(__file__).resolve().parent

AUDIT_TAG = re.compile(r"回改[:：]\s*句级\s*(\d+)\s*[/／]\s*场景级\s*(\d+)\s*[/／]\s*细纲级\s*(\d+)")
EXEMPT = re.compile(r"豁免")
EXEMPT_WHY = re.compile(r"豁免[^\n]{0,60}(理由|因为|原因|重跑|复核)")
LOOP_TAG = re.compile(r"\b(local|structural)\b", re.I)


def find_root() -> Path:
    env = os.environ.get("JIPU_ROOT")
    if env and (Path(env) / "项目配置.json").exists():
        return Path(env)
    cur = Path.cwd().resolve()
    for base in [cur] + list(cur.parents):
        if (base / "项目配置.json").exists():
            return base
    return cur


def load_cfg(root: Path) -> dict:
    p = root / "项目配置.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def locate_chapter(root: Path, chapter: str):
    hits = glob.glob(str(root / "04_正文_成品" / f"第{chapter}章_*.md"))
    if not hits and chapter.isdigit():
        hits = glob.glob(str(root / "04_正文_成品" / f"第{int(chapter):03d}章_*.md"))
    return Path(hits[0]) if hits else None


def locate_audit(root: Path, chapter: str):
    base = root / "05_质检_审计评审节奏" / "审计"
    num = f"{int(chapter):03d}" if chapter.isdigit() else chapter
    for c in (base / f"第{num}章_审计.md", base / f"第{chapter}章_审计.md"):
        if c.exists():
            return c
    hits = glob.glob(str(base / f"*{chapter}*审计*.md"))
    return Path(hits[0]) if hits else None


def locate_aux(root: Path, chapter: str, sub: str, word: str):
    base = root / "05_质检_审计评审节奏" / sub
    num = f"{int(chapter):03d}" if chapter.isdigit() else chapter
    for name in (f"第{num}章_{word}.md", f"第{chapter}章_{word}.md"):
        p = base / name
        if p.exists():
            return p
    hits = glob.glob(str(base / f"*{chapter}*{word}*.md"))
    return Path(hits[0]) if hits else None


def card_exists(root: Path, chapter: str) -> bool:
    hits = glob.glob(str(root / "05_质检_审计评审节奏" / f"盲评_第{chapter}章_*.md"))
    if not hits and chapter.isdigit():
        hits = glob.glob(str(root / "05_质检_审计评审节奏" / f"盲评_第{int(chapter):03d}章_*.md"))
    return bool(hits)


def mtime(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except Exception:
        return 0.0


def fmt(m: float) -> str:
    if not m:
        return "—"
    return datetime.fromtimestamp(m).strftime("%m-%d %H:%M")


def health_stamp(root: Path):
    """章体检留下的一次跑数时间（可选文件）。没有就返回 None。"""
    p = root / "06_追踪_状态记录" / "体检时间.json"
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else None
    except Exception:
        return None


def check_one(root: Path, chapter: str, tier: str = "T1"):
    """返回 (rows, checks)。rows 是硬项 [(名称, ok, note)]。"""
    rows, checks = [], []
    chap = locate_chapter(root, chapter)
    if chap is None:
        rows.append((f"第{chapter}章正文", False, "04_正文_成品 里没有这一章"))
        return rows, checks
    audit = locate_audit(root, chapter)
    if audit is None:
        rows.append(("审计在", False, f"没有 05_质检_审计评审节奏/审计/第{chapter}章_审计.md"))
        return rows, checks
    rows.append(("审计在", True, str(audit.relative_to(root))))

    t_chap, t_audit = mtime(chap), mtime(audit)
    ok_new = t_audit >= t_chap
    rows.append(("审计比正文新（改完必须重跑）", ok_new,
                 f"正文 {fmt(t_chap)}／审计 {fmt(t_audit)}" if ok_new
                 else f"正文 {fmt(t_chap)} 比审计 {fmt(t_audit)} 新——改完没重跑"))

    body = audit.read_text(encoding="utf-8", errors="replace")
    m = AUDIT_TAG.search(body)
    rows.append(("返工记录行（回改：句级 N／场景级 M／细纲级 K）", bool(m),
                 m.group(0) if m else "审计末尾缺这一行 → 回路表没有落点"))

    if tier != "T0":
        for sub, word in (("节奏", "节奏"), ("评审", "评审")):
            p = locate_aux(root, chapter, sub, word)
            if p is None:
                continue
            ok_aux = mtime(p) >= t_chap
            rows.append((f"{word}文件不比正文旧", ok_aux,
                         f"{word} {fmt(mtime(p))}" if ok_aux
                         else f"{word} {fmt(mtime(p))} 比正文 {fmt(t_chap)} 旧"))

    # ---- CHECK（只报数）
    lines = body.splitlines()
    bad_exempt = [i for i, ln in enumerate(lines, 1) if EXEMPT.search(ln) and not EXEMPT_WHY.search(ln)]
    if bad_exempt:
        checks.append(f"审计里有 {len(bad_exempt)} 处「豁免」没写理由（行 {', '.join(map(str, bad_exempt[:5]))}）——豁免不是通行证，写清为什么可以不管")

    loop_hits = [ln for ln in lines if LOOP_TAG.search(ln)]
    if loop_hits and not m:
        checks.append("审计里判了 local／structural 回路，但没有「回改：句级 N／场景级 M／细纲级 K」落点")

    stamp = health_stamp(root)
    if stamp:
        t_stamp = 0.0
        key = str(int(chapter)) if chapter.isdigit() else chapter
        raw = stamp.get(key) or stamp.get(f"{int(chapter):03d}" if chapter.isdigit() else key)
        if raw:
            try:
                t_stamp = datetime.fromisoformat(str(raw)).timestamp()
            except Exception:
                t_stamp = 0.0
        if t_stamp and t_stamp < t_chap:
            checks.append(f"章体检跑在 {fmt(t_stamp)}，比正文 {fmt(t_chap)} 旧——改完没重跑体检")

    if tier == "T2" and not card_exists(root, chapter):
        checks.append("T2 章没有盲评卡（`成对盲评.py NNN` 出三张）——T2 必须过成对盲评")

    return rows, checks


def print_one(root: Path, chapter: str, tier: str):
    rows, checks = check_one(root, chapter, tier)
    print(f"\n=== 合门检查 · 第{chapter}章（{tier}）===")
    print("硬项：")
    fails = 0
    for name, ok, note in rows:
        fails += (not ok)
        print(f"  {'PASS' if ok else 'FAIL'}  {name}  {note}")
    print(f"硬项 {len(rows) - fails}/{len(rows)} 通过")
    if checks:
        print("CHECK（不进合门，命中即改）：")
        for c in checks:
            print(f"  CHECK  {c}")
    else:
        print("CHECK（不进合门，命中即改）：无")
    print(f"合门检查：{'PASS' if fails == 0 else 'FAIL'}")
    return fails


def main():
    ap = argparse.ArgumentParser(description="合门检查：改完重跑了吗、豁免有理由吗")
    ap.add_argument("chapter", nargs="?", help="章号，如 001")
    ap.add_argument("--tier", default=None, choices=["T0", "T1", "T2"])
    ap.add_argument("--all", action="store_true", help="全书扫一遍")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        sys.exit(selftest())

    root = find_root()
    cfg = load_cfg(root)
    tier = args.tier or (cfg.get("gate") or {}).get("tier") or "T1"

    if args.all:
        nums = []
        for p in sorted((root / "04_正文_成品").glob("第*章_*.md")):
            m = re.search(r"第(\d+)章", p.name)
            if m:
                nums.append(m.group(1))
        if not nums:
            print("04_正文_成品 里还没有正文")
            sys.exit(1)
        bad = 0
        for n in nums:
            bad += print_one(root, n, tier)
        print(f"\n全书 {len(nums)} 章，{bad} 项硬项没过")
        sys.exit(1 if bad else 0)

    if not args.chapter:
        print("用法：合门检查.py 001 ｜ --all ｜ --selftest")
        sys.exit(2)
    sys.exit(1 if print_one(root, args.chapter, tier) else 0)


def selftest():
    import shutil
    import tempfile
    import time

    root = Path(tempfile.mkdtemp())
    (root / "04_正文_成品" / "_候选").mkdir(parents=True)
    (root / "05_质检_审计评审节奏" / "审计").mkdir(parents=True)
    (root / "06_追踪_状态记录").mkdir(parents=True)
    (root / "项目配置.json").write_text(json.dumps({"gate": {"tier": "T1"}}, ensure_ascii=False), encoding="utf-8")

    chap = root / "04_正文_成品" / "第001章_雨夜.md"
    chap.write_text("雨下了一夜。\n", encoding="utf-8")
    audit = root / "05_质检_审计评审节奏" / "审计" / "第001章_审计.md"
    audit.write_text("### 读数\n- 1200 字／30 段\n\n回改：句级 2／场景级 0／细纲级 0\n", encoding="utf-8")
    os.utime(audit, (time.time() + 10, time.time() + 10))  # 审计比正文新

    rowsA, chkA = check_one(root, "001", "T1")
    okA = all(ok for _, ok, _ in rowsA) and not chkA
    print(f"自检 A（审计比正文新、有回改行）：{'通过' if okA else '不通过'}")

    # B：正文改在审计之后 → 应 FAIL
    os.utime(chap, (time.time() + 60, time.time() + 60))
    rowsB, _ = check_one(root, "001", "T1")
    okB = not all(ok for _, ok, _ in rowsB)
    print(f"自检 B（正文比审计新 → FAIL）：{'通过' if okB else '不通过'}")

    # C：缺回改行 + 豁免没理由 → 硬项失败 + CHECK
    os.utime(audit, (time.time() + 120, time.time() + 120))
    audit.write_text("### 读数\n- 豁免：这一章先不管。\n", encoding="utf-8")
    os.utime(audit, (time.time() + 120, time.time() + 120))
    rowsC, chkC = check_one(root, "001", "T1")
    okC = (not all(ok for _, ok, _ in rowsC)) and any("豁免" in c for c in chkC)
    print(f"自检 C（缺回改行＋豁免无理由）：{'通过' if okC else '不通过'}")

    # D：T2 缺盲评卡 → CHECK
    audit.write_text("回改：句级 1／场景级 0／细纲级 0\n", encoding="utf-8")
    os.utime(audit, (time.time() + 300, time.time() + 300))
    rowsD, chkD = check_one(root, "001", "T2")
    okD = all(ok for _, ok, _ in rowsD) and any("盲评卡" in c for c in chkD)
    print(f"自检 D（T2 缺盲评卡 → CHECK）：{'通过' if okD else '不通过'}")

    shutil.rmtree(root, ignore_errors=True)
    good = all([okA, okB, okC, okD])
    print(f"\n自检结果：{'通过' if good else '失败'}")
    return 0 if good else 1


if __name__ == "__main__":
    main()
