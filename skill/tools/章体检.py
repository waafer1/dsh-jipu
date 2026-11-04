# -*- coding: utf-8 -*-
"""
章体检.py —— 一章的硬项总检（九条）

它不重复造轮子：句检／画面检／数字体检／章指标都是独立脚本，本脚本只负责
**把它们跑一遍 + 加上工具查不出的剧情四查**，最后出一张 PASS/FAIL 表。

九条硬项：
  H1 句检 blocking = 0
  H2 数字待核 = 0
  H3 章名落地：章名里的字在正文出现过
  H4 章首交底：前三段里有一段给了具体物或位置
  H5 章末不停在决心：末段不含"发誓／一定要／必须／下定决心"
  H6 无禁词（读 项目配置.json lexicon.banned_words）
  H7 连续纯引号段 < 3
  H8 字数达线（默认 1500，读 gate.min_words）
  H9 段首"他/她" ≤ 25%

用法：
    python 章体检.py 001                       # 按章号找 04_正文_成品/第001章_*.md
    python 章体检.py 001 --file 路径.md
    python 章体检.py --selftest
退出码：有 FAIL → 1。
"""

import argparse
import glob
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONCRETE = ("枚|文|斤|两|袋|瓶|碗|把|根|株|块|张|只|条|件|寸|尺|一步|一里")
PLACE = ("门口|台阶|屋里|屋外|院里|街上|巷|窗口|床|桌|柜|墙角|檐下|灶|井|路边|树下|柜台")
RESOLVE = ("发誓", "一定要", "必须", "下定决心", "心里暗暗", "他在心里")


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


def load_cfg(root: Path):
    f = root / "项目配置.json"
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def locate(chapter: str, given: str = None, root: Path = None):
    if given:
        return Path(given)
    root = root or find_root()
    hits = glob.glob(str(root / "04_正文_成品" / f"第{chapter}章_*.md"))
    if not hits:
        hits = glob.glob(str(root / "04_正文_成品" / f"第0*{int(chapter)}章_*.md"))
    return Path(hits[0]) if hits else None


def run(script, args, cwd=None):
    try:
        r = subprocess.run([sys.executable, str(HERE / script)] + args,
                           capture_output=True, text=True, encoding="utf-8",
                           timeout=120, cwd=str(cwd) if cwd else None)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return 99, f"[脚本失败] {script}: {e}"


def strip_fm(t):
    if t.startswith("---"):
        e = t.find("\n---", 1)
        if e != -1:
            return t[e + 4:]
    return t


def main_check(chapter, path, root):
    cfg = load_cfg(root)
    gate = cfg.get("gate", {})
    text = strip_fm(path.read_text(encoding="utf-8"))
    paras = [p.strip() for p in text.split("\n") if p.strip()]
    rows = []

    # 机器四件
    rc_s, out_s = run("句检.py", [str(path)], cwd=root)
    rows.append(("H1 句检 blocking=0", rc_s == 0, _grab(out_s, r"合计 blocking (\d+)")))

    known_args = [str(path), "--lenient"]
    rc_n, out_n = run("数字体检.py", known_args, cwd=root)
    pend = _grab(out_n, r"合计 (\d+) 处待核")
    rows.append(("H2 数字待核=0", pend == "0", f"待核 {pend} 处"))

    rc_m, out_m = run("章指标.py", ["--json", str(path)], cwd=root)
    m = {}
    try:
        m = json.loads(out_m[out_m.index("["):])[0]
    except Exception:
        pass

    # H3 章名落地
    name = path.stem.split("_", 1)[1] if "_" in path.stem else path.stem
    name_chars = [c for c in re.sub(r"[^\u4e00-\u9fa5]", "", name)]
    landed = any(c in text for c in name_chars) if name_chars else False
    rows.append(("H3 章名落地", landed, f"章名「{name}」"))

    # H4 章首交底
    head = "".join(paras[:3])
    has_concrete = re.search(CONCRETE, head) or re.search(PLACE, head)
    rows.append(("H4 章首交底（具体物或位置）", bool(has_concrete), "前三段有物/有地方" if has_concrete else "前三段全是状态"))

    # H5 章末不停决心
    tail = paras[-1] if paras else ""
    bad_tail = [w for w in RESOLVE if w in tail]
    rows.append(("H5 章末不停在决心", not bad_tail, f"末段「{tail[:24]}」" + (f" 命中{bad_tail}" if bad_tail else "")))

    # H6 禁词
    banned = cfg.get("lexicon", {}).get("banned_words", []) or []
    hits = [w for w in banned if w and w in text]
    rows.append(("H6 无禁词", not hits, f"命中 {hits}" if hits else f"禁词表 {len(banned)} 条"))

    # H7 连续纯引号
    run_max = m.get("quote_run_max", 0)
    rows.append(("H7 连续纯引号段<3", run_max < 3, f"最长 {run_max}"))

    # H8 字数
    min_words = int(gate.get("min_words", 1500))
    chars = m.get("chars", len(re.sub(r"\s", "", text)))
    rows.append((f"H8 字数≥{min_words}", chars >= min_words, f"{chars} 字"))

    # H9 段首他她
    hp = m.get("head_pronoun_ratio", 0)
    limit = float(gate.get("paragraph_head_pronoun_max", 0.25))
    rows.append((f"H9 段首他她≤{limit:.0%}", hp <= limit, f"{hp:.1%}"))

    print(f"\n=== 章体检 · {path.name} ===")
    fails = 0
    for name_, ok, note in rows:
        print(f"  {'PASS' if ok else 'FAIL'}  {name_:<26} {note}")
        fails += (not ok)
    print(f"\n硬项 {len(rows) - fails}/{len(rows)} 通过")
    print("章体检：PASS" if fails == 0 else f"章体检：FAIL（{fails} 项）—— 按回路重来，别在正文里圆")

    # 读数附在后面，供审计直接抄
    print("\n--- 读数（抄进审计）---")
    print(f"字数 {chars}／段 {m.get('paras', '?')}／对白占比 {m.get('dialogue_ratio', 0):.2%}／"
          f"最长纯叙 {m.get('longest_narration', '?')}／段首他她 {hp:.1%}／连续纯引号 {run_max}")
    return 0 if fails == 0 else 1


def _grab(text, pattern):
    m = re.search(pattern, text)
    return m.group(1) if m else "?"


def selftest():
    import tempfile
    root = Path(tempfile.mkdtemp())
    (root / "04_正文_成品").mkdir(parents=True)
    (root / "06_追踪_状态账本").mkdir(parents=True)
    (root / "06_追踪_状态账本" / "数字登记.md").write_text("| 3 | 株 |\n| 7 | 枚 |\n", encoding="utf-8")
    (root / "项目配置.json").write_text(json.dumps(
        {"gate": {"min_words": 50}, "lexicon": {"banned_words": ["系统"]}}, ensure_ascii=False), encoding="utf-8")
    good = ("柜台上摆着三株草，土还湿着。\n"
            "老板捏起一株看过，报了个价。\n"
            "他把七枚铜板摊在台面上，一枚一枚推过去。\n"
            "“行。”老板说。\n"
            "临走那株草他带走了，压在袖口里。\n") * 4
    (root / "04_正文_成品" / "第001章_摊手.md").write_text(good, encoding="utf-8")
    bad = "他很难过。\n他很失望。\n他在心里发誓，一定要赢。\n"
    (root / "04_正文_成品" / "第002章_发誓.md").write_text(bad, encoding="utf-8")

    print("自检：第 1 章应大体 PASS（H8 除外按字数算），第 2 章应多项 FAIL")
    rc1 = main_check("001", root / "04_正文_成品" / "第001章_摊手.md", root)
    rc2 = main_check("002", root / "04_正文_成品" / "第002章_发誓.md", root)
    import shutil
    shutil.rmtree(root, ignore_errors=True)
    ok = rc1 == 0 and rc2 == 1
    print(f"\n自检结果：{'通过' if ok else '失败'}（好章 {rc1}，坏章 {rc2}）")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="章体检九硬项")
    ap.add_argument("chapter", nargs="?")
    ap.add_argument("--file")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(selftest())
    if not args.chapter and not args.file:
        ap.print_help()
        sys.exit(1)

    root = find_root()
    p = locate(args.chapter, args.file, root)
    if p is None or not p.exists():
        print(f"[停] 找不到正文（章号 {args.chapter}）——先确认项目根与 04_正文_成品/")
        sys.exit(1)
    sys.exit(main_check(args.chapter, p, root))


if __name__ == "__main__":
    main()
