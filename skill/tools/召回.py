# -*- coding: utf-8 -*-
"""
召回.py —— 写下一章之前，把旧账打成一份注射包

为什么要它：长篇写到三十章以后，人记不住"他现在有多少钱、欠谁的、哪条线到期了"。
这份包把这些从 `_tracking-state.json` 里读出来，和上一章末尾原文拼在一起，
作家只读这一份就能动笔。

产出 `06_追踪_状态账本/召回_第NNN章.md`（`--write` 时落盘）：
  1 主角此刻（钱／身份／代价／位置）
  2 开口的线（按 due 排序，标"到期"）
  3 未付的伏笔（A 类＝来源未解释／B 类＝方法未兑现）
  4 最近三章的拍点
  5 已定价的钱（不许第二章改价）
  6 上一章末 800 字

用法：
    python 召回.py 12                # 打印到屏幕
    python 召回.py 12 --write        # 落盘 召回_第012章.md
    python 召回.py 12 --chars 1200   # 多取一点上章末文
    python 召回.py --selftest
"""

import argparse
import json
import re
import sys
from pathlib import Path


def find_project_root() -> Path:
    """四级判定：当前目录→向上找 _tracking-state.json；JIPU_ROOT；停下报错。"""
    import os
    env = os.environ.get("JIPU_ROOT")
    if env and (Path(env) / "06_追踪_状态账本" / "_tracking-state.json").exists():
        return Path(env)
    cur = Path.cwd().resolve()
    for base in [cur] + list(cur.parents):
        if (base / "06_追踪_状态账本" / "_tracking-state.json").exists():
            return base
    return cur


def load_state(root: Path):
    f = root / "06_追踪_状态账本" / "_tracking-state.json"
    if not f.exists():
        print(f"[停] 找不到 {f}\n    先确认项目根（或设 JIPU_ROOT），计谱不猜路径。")
        sys.exit(1)
    return json.loads(f.read_text(encoding="utf-8"))


def last_chars(root: Path, n: int, upto: int):
    d = root / "04_正文_成品"
    if not d.is_dir():
        return None, ""
    files = []
    for f in d.glob("第*章_*.md"):
        m = re.match(r"第0*(\d+)章", f.name)
        if m and int(m.group(1)) < upto:
            files.append((int(m.group(1)), f))
    if not files:
        return None, ""
    files.sort()
    num, path = files[-1]
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        end = text.find("\n---", 1)
        if end != -1:
            text = text[end + 4:]
    text = text.strip()
    return num, text[-n:]


def build(root: Path, chap: int, n_chars: int) -> str:
    st = load_state(root)
    L = [f"# 召回 · 第 {chap} 章\n",
         f"> 事实源：`06_追踪_状态账本/_tracking-state.json`（rev {st.get('state_revision', 0)}，"
         f"已提交到第 {st.get('last_committed_chapter', 0)} 章）\n"]

    L.append("## 一、主角此刻\n")
    chars = st.get("characters", {})
    lead = [v for v in chars.values() if v.get("role") in ("主角", "lead")] or list(chars.values())[:1]
    if lead:
        c = lead[0]
        L.append(f"- 钱：{c.get('cash_copper', '未记录')}")
        L.append(f"- 状态：{c.get('status', '未记录')}")
        L.append(f"- 关系：{c.get('relation', '未记录')}")
        L.append(f"- 备注：{c.get('note', '—')}\n")
    else:
        L.append("- 账上还没有主角记录——第一次提交时补\n")

    L.append("## 二、开口的线\n")
    threads = [t for t in st.get("threads", []) if t.get("status", "open") == "open"]
    threads.sort(key=lambda t: t.get("due", 9999))
    if threads:
        for t in threads:
            due = t.get("due")
            flag = " **←到期**" if isinstance(due, int) and due <= chap else ""
            L.append(f"- [{t.get('id', '?')}] {t.get('name', '')}（due {due}）{t.get('note', '')}{flag}")
    else:
        L.append("- 无")
    L.append("")

    L.append("## 三、未付的伏笔\n")
    fs = [f for f in st.get("foreshadows", []) if f.get("status", "open") == "open"]
    if fs:
        for f in fs:
            L.append(f"- ({f.get('tier', '?')}) {f.get('summary', '')} —— 进度：{f.get('progress', '未动')}")
    else:
        L.append("- 无")
    L.append("")

    L.append("## 四、最近三章的拍点\n")
    beats = st.get("beats", [])[-3:]
    if beats:
        for b in beats:
            if isinstance(b, dict):
                L.append(f"- 第{b.get('chapter', '?')}章：" + "／".join(b.get("beats", []) or []))
            else:
                L.append(f"- {b}")
    else:
        L.append("- 无")
    L.append("")

    L.append("## 五、已定价的钱（不许改价）\n")
    prices = st.get("facts", {}).get("prices_used", [])
    L.append("- " + ("；".join(str(p) for p in prices) if prices else "还没有定价记录"))
    L.append("")

    prev_no, tail = last_chars(root, n_chars, chap)
    L.append(f"## 六、上一章末 {n_chars} 字（第 {prev_no} 章）\n" if prev_no else "## 六、上一章末文\n")
    L.append(tail if tail else "（还没有已提交的正文）")
    return "\n".join(L)


def selftest():
    import tempfile
    root = Path(tempfile.mkdtemp())
    (root / "06_追踪_状态账本").mkdir(parents=True)
    (root / "04_正文_成品").mkdir(parents=True)
    state = {
        "state_revision": 4, "last_committed_chapter": 2,
        "characters": {"主角": {"role": "主角", "cash_copper": 511, "status": "伤在左肋", "relation": "欠药铺一副药", "note": ""}},
        "threads": [{"id": "T1", "name": "银叶草的来路", "status": "open", "due": 3, "note": "孩子给了位置"},
                    {"id": "T2", "name": "旧债", "status": "closed", "due": 9, "note": ""}],
        "foreshadows": [{"tier": "A", "summary": "核心摸着发暖", "progress": "未解释", "status": "open"}],
        "beats": [{"chapter": 2, "beats": ["送药", "被关门", "守夜"]}],
        "facts": {"prices_used": ["一副药 7 枚铜板"]},
    }
    (root / "06_追踪_状态账本" / "_tracking-state.json").write_text(
        json.dumps(state, ensure_ascii=False), encoding="utf-8")
    (root / "04_正文_成品" / "第002章_松手.md").write_text("他坐着，等下一口气。", encoding="utf-8")
    out = build(root, 3, 800)
    print(out)
    ok = ("到期" in out and "银叶草的来路" in out and "旧债" not in out
          and "511" in out and "等下一口气" in out and "核心摸着发暖" in out)
    print(f"\n自检结果：{'通过' if ok else '失败'}")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="旧账注射包")
    ap.add_argument("chapter", nargs="?", type=int)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--chars", type=int, default=800)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(selftest())
    if not args.chapter:
        ap.print_help()
        sys.exit(1)

    root = find_project_root()
    text = build(root, args.chapter, args.chars)
    if args.write:
        out = root / "06_追踪_状态账本" / f"召回_第{args.chapter:03d}章.md"
        out.write_text(text, encoding="utf-8")
        print(f"已写：{out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
