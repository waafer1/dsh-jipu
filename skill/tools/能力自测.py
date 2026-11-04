# -*- coding: utf-8 -*-
"""
能力自测.py —— 这个项目离"能开工"还差什么（九环节）

用途：新书开张第一次跑，三个月后回来再跑一次。它回答的是
"我现在缺的是设定、是图纸、还是工具"，而不是"这章写得好不好"。

九环节：
  1 选型卡 12 行填满
  2 主角 A 卡（五项硬字段齐）
  3 卷纲
  4 章纲（至少前 15 章）
  5 人物层库
  6 桥段账本（有过回写）
  7 素材底座（≥3 条）
  8 工具齐（14 个脚本）
  9 状态账本（结构完整）

用法：
    python 能力自测.py
    python 能力自测.py --selftest
退出码：恒 0（只是体检，不卡门；缺项会列出）。
"""

import argparse
import json
import sys
from pathlib import Path

TOOLS = ["开项目.py", "选型体检.py", "召回.py", "句检.py", "句病检.py", "对白归属.py",
         "章指标.py", "画面检.py", "数字体检.py", "章体检.py", "章检.py", "读者判定.py",
         "账本体检.py", "能力自测.py"]
HARD_FIELDS = ("一句话", "干的活", "想要", "怕", "账")


def find_root() -> Path:
    import os
    env = os.environ.get("JIPU_ROOT")
    if env and (Path(env) / "项目配置.json").exists():
        return Path(env)
    cur = Path.cwd().resolve()
    for b in [cur] + list(cur.parents):
        if (b / "项目配置.json").exists():
            return b
    return cur


def filled_card(root: Path):
    f = root / "02_设定_世界与角色" / "题材定位.md"
    if not f.exists():
        return 0
    n = 0
    for line in f.read_text(encoding="utf-8").split("\n"):
        if line.strip().startswith("|") and line.count("|") >= 3:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if cells and cells[0].isdigit() and cells[-1] and cells[-1] not in ("—", "-"):
                n += 1
    return n


def lead_card_fields(root: Path):
    d = root / "02_设定_世界与角色" / "角色"
    if not d.is_dir():
        return None
    for f in sorted(d.glob("*.md")):
        t = f.read_text(encoding="utf-8")
        hit = sum(1 for k in HARD_FIELDS if k in t)
        return (f.name, hit)
    return None


def check(root: Path):
    rows = []
    n_card = filled_card(root)
    rows.append(("1 选型卡 12 行", n_card >= 12, f"{n_card}/12"))

    lc = lead_card_fields(root)
    rows.append(("2 主角 A 卡五项", bool(lc and lc[1] >= 5), f"{lc[0]}（{lc[1]}/5）" if lc else "没有角色卡"))

    d3 = root / "03_图纸_大纲与细纲"
    vol = list(d3.glob("卷纲*")) if d3.is_dir() else []
    rows.append(("3 卷纲", bool(vol), f"{len(vol)} 份"))

    chap = list(d3.glob("章纲*")) if d3.is_dir() else []
    rows.append(("4 章纲", bool(chap), f"{len(chap)} 份"))

    d7 = root / "07_模板_复用件"
    rows.append(("5 人物层库", (d7 / "人物层库").is_dir(), "在" if (d7 / "人物层库").is_dir() else "缺"))

    ledger = root / "06_追踪_状态账本" / "桥段账本.md"
    used = False
    if ledger.exists():
        used = len([l for l in ledger.read_text(encoding="utf-8").split("\n")
                    if l.strip().startswith("|") and not l.strip().startswith("|---")]) > 2
    rows.append(("6 桥段账本有回写", used, "有记录" if used else "空表"))

    mat = root / "02_设定_世界与角色" / "素材"
    n_mat = len(list(mat.glob("*.md"))) if mat.is_dir() else 0
    rows.append(("7 素材底座 ≥3 条", n_mat >= 3, f"{n_mat} 条"))

    tool_dir = root / "08_工具_脚本"
    have = [t for t in TOOLS if (tool_dir / t).exists()]
    rows.append(("8 工具齐 14 个", len(have) == len(TOOLS), f"{len(have)}/{len(TOOLS)}"))

    st = root / "06_追踪_状态账本" / "_tracking-state.json"
    ok_st = False
    if st.exists():
        try:
            d = json.loads(st.read_text(encoding="utf-8"))
            ok_st = all(k in d for k in ("state_revision", "threads", "foreshadows", "beats"))
        except Exception:
            ok_st = False
    rows.append(("9 状态账本结构", ok_st, "正常" if ok_st else "缺字段或读不了"))

    print(f"\n=== 能力自测 · {root} ===")
    done = 0
    for name, ok, note in rows:
        print(f"  {'[x]' if ok else '[ ]'} {name:<18} {note}")
        done += ok
    print(f"\n{done}/9 环节就位（{done / 9:.0%}）")
    if done < 9:
        first = next(n for n, ok, _ in rows if not ok)
        print(f"先补这一项：{first}")
    return done


def selftest():
    import tempfile, shutil
    tmp = Path(tempfile.mkdtemp())
    (tmp / "项目配置.json").write_text("{}", encoding="utf-8")
    (tmp / "02_设定_世界与角色" / "角色").mkdir(parents=True)
    (tmp / "02_设定_世界与角色" / "素材").mkdir(parents=True)
    (tmp / "03_图纸_大纲与细纲").mkdir(parents=True)
    (tmp / "06_追踪_状态账本").mkdir(parents=True)
    (tmp / "07_模板_复用件" / "人物层库").mkdir(parents=True)
    (tmp / "08_工具_脚本").mkdir(parents=True)
    print("自检：空项目应只过 1—2 项（人物层库／工具可能不齐）")
    n = check(tmp)
    shutil.rmtree(tmp, ignore_errors=True)
    ok = n <= 2
    print(f"\n自检结果：{'通过' if ok else '失败'}（空项目 {n}/9，应 ≤2）")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="九环节能力自测")
    ap.add_argument("--root")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        sys.exit(selftest())
    root = Path(args.root).resolve() if args.root else find_root()
    check(root)


if __name__ == "__main__":
    main()
