# -*- coding: utf-8 -*-
"""
账本体检.py —— 纪长存的上岗检查（state 结构对不对）

查 `06_追踪_状态账本/_tracking-state.json`：
  S1 八个字段全在（少一个，后面的视图渲染就会缺）
  S2 state_revision / last_committed_chapter 是整数且一致推进
  S3 threads 每条有 id／status／due
  S4 foreshadows 每条有 tier（A／B）与 status
  S5 beats 章号不重复、连续
  S6 facts.prices_used 是列表（已定价的钱不许散着写）
  S7 五份派生视图文件都在
  S8 视图比 state 旧（mtime 早于 state）→ 忘渲染了

只判结构，不判内容对错。

用法：
    python 账本体检.py
    python 账本体检.py --selftest
退出码：有错 → 1。
"""

import argparse
import json
import sys
from pathlib import Path

REQUIRED = ["state_revision", "last_committed_chapter", "committed_at", "commit_note",
            "threads", "foreshadows", "characters", "facts", "beats"]
VIEWS = ["上下文.md", "事实词典.md", "伏笔.md", "数字登记.md", "桥段账本.md"]


def find_state():
    import os
    bases = []
    env = os.environ.get("JIPU_ROOT")
    if env:
        bases.append(Path(env))
    cur = Path.cwd().resolve()
    bases += [cur] + list(cur.parents)
    for b in bases:
        f = b / "06_追踪_状态账本" / "_tracking-state.json"
        if f.exists():
            return f
    return None


def check(state_path):
    errs, warns = [], []
    try:
        st = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[停] 读不了 JSON：{e}")
        return 1

    for k in REQUIRED:
        if k not in st:
            errs.append(f"S1 缺字段 `{k}`")

    rev = st.get("state_revision")
    last = st.get("last_committed_chapter")
    if not isinstance(rev, int):
        errs.append("S2 state_revision 不是整数")
    if not isinstance(last, int):
        errs.append("S2 last_committed_chapter 不是整数")
    if isinstance(rev, int) and isinstance(last, int) and rev < last:
        warns.append(f"S2 rev {rev} 小于已提交章数 {last}——提交时漏了 +1？")

    for t in st.get("threads", []) or []:
        miss = [k for k in ("id", "status", "due") if k not in t]
        if miss:
            errs.append(f"S3 线「{t.get('name', '?')}」缺 {miss}")
    for f in st.get("foreshadows", []) or []:
        if f.get("tier") not in ("A", "B"):
            errs.append(f"S4 伏笔「{f.get('summary', '?')[:16]}」tier 不是 A/B")
        if "status" not in f:
            errs.append(f"S4 伏笔缺 status")

    nums = [b.get("chapter") for b in st.get("beats", []) or [] if isinstance(b, dict)]
    if len(nums) != len(set(nums)):
        errs.append("S5 beats 章号重复")
    if nums and nums != sorted(nums):
        warns.append("S5 beats 章号不是升序")

    if not isinstance(st.get("facts", {}).get("prices_used", []), list):
        errs.append("S6 facts.prices_used 不是列表")

    d = state_path.parent
    existing = [v for v in VIEWS if (d / v).exists()]
    for v in VIEWS:
        if v not in existing:
            errs.append(f"S7 派生视图缺 `{v}`")
    if isinstance(last, int) and last > 0:
        st_mtime = state_path.stat().st_mtime
        stale = [v for v in existing if (d / v).stat().st_mtime < st_mtime]
        if stale:
            warns.append(f"S8 视图比 state 旧（{len(stale)} 份）：{stale} → 重渲染")

    print(f"\n=== 账本体检 · {state_path} ===")
    print(f"rev {rev} ／ 已提交到第 {last} 章 ／ 线 {len(st.get('threads', []))} 条 ／ 伏笔 {len(st.get('foreshadows', []))}")
    for e in errs:
        print(f"  [错] {e}")
    for w in warns:
        print(f"  [警] {w}")
    if not errs and not warns:
        print("  结构完整。")
    print("\n账本体检：" + ("PASS" if not errs else f"FAIL（{len(errs)} 项）"))
    return 0 if not errs else 1


def selftest():
    import tempfile, shutil, time
    tmp = Path(tempfile.mkdtemp())
    d = tmp / "06_追踪_状态账本"
    d.mkdir(parents=True)
    st = {"state_revision": 4, "last_committed_chapter": 3, "committed_at": "2026-11-04",
          "commit_note": "003 提交", "threads": [{"id": "T1", "name": "草", "status": "open", "due": 5}],
          "foreshadows": [{"tier": "A", "summary": "核心发暖", "status": "open"}],
          "characters": {}, "facts": {"prices_used": []},
          "beats": [{"chapter": 1, "beats": []}, {"chapter": 2, "beats": []}]}
    (d / "_tracking-state.json").write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
    for v in VIEWS:
        (d / v).write_text("x", encoding="utf-8")
    time.sleep(0.01)
    (d / "_tracking-state.json").write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")

    print("自检 A：结构完整应 PASS（可能带 S8 陈旧警告）")
    rcA = check(d / "_tracking-state.json")

    bad = dict(st)
    del bad["threads"]
    bad["foreshadows"] = [{"summary": "没 tier", "status": "open"}]
    (d / "_tracking-state.json").write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
    print("\n自检 B：缺 threads＋tier 错 应 FAIL")
    rcB = check(d / "_tracking-state.json")
    shutil.rmtree(tmp, ignore_errors=True)
    ok = rcA == 0 and rcB == 1
    print(f"\n自检结果：{'通过' if ok else '失败'}（A {rcA} / B {rcB}）")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="state 结构体检")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        sys.exit(selftest())
    p = find_state()
    if p is None:
        print("[停] 找不到 06_追踪_状态账本/_tracking-state.json —— 先确认项目根")
        sys.exit(1)
    sys.exit(check(p))


if __name__ == "__main__":
    main()
