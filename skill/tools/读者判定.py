# -*- coding: utf-8 -*-
"""
读者判定.py —— 以读者身份过一遍，出 WARN 与位置

它和章体检的分工：章体检查"对不对"，本脚本查"读不读得下去"。
**只出 WARN，不卡门**——但每条 WARN 必须带三样：位置、原因、一个"如果改成这样我会继续读"的空位。

七条规则（都是能数的）：
  R1 开篇前三段没有具体物／位置（读者不知道自己在哪）
  R2 章末停在决心（"发誓／一定要／必须"）——读者知道下一章要干什么，就不想看了
  R4 最长纯叙段 > 600 字（一大片没有人在说话）
  R5 段首"他／她" > 25%（句式起头单一，读着闷）
  R6 连续纯引号段 ≥ 3（对白悬空，不知道谁在说）
  R7 全章没有一个问句、没有一处对白（没有心跳）
  R8 苦词 ≥4 且得词 0（苦多无得，读者看不到翻身）

出读数，不打分（1.37.0 起）：开篇交没交底／句检 warn 条数／段首他她占比／
最长连续叙述／对白占比。**不给 20 分制绝对分**——实测同一章机器四项全 20/20、
人判 86/100，绝对分没有区分力（研究报告 §F6）。要比哪一稿更想读下一章，用
`成对盲评.py`。

用法：
    python 读者判定.py 001
    python 读者判定.py --selftest
退出码恒 0（WARN 不卡门）。
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
KU = ("哭", "痛", "惨", "穷", "病", "死", "血", "跪", "求", "冻", "饿", "挨打", "受气", "屈辱")
DE = ("得", "赚", "赢", "拿到", "升", "笑", "松", "放心", "抢到", "省下", "多出", "第一")


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


def run(script, args, cwd):
    r = subprocess.run([sys.executable, str(HERE / script)] + args,
                       capture_output=True, text=True, encoding="utf-8",
                       timeout=120, cwd=str(cwd))
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def strip_fm(t):
    if t.startswith("---"):
        e = t.find("\n---", 1)
        if e != -1:
            return t[e + 4:]
    return t


def judge(path, root):
    text = strip_fm(path.read_text(encoding="utf-8"))
    paras = [p.strip() for p in text.split("\n") if p.strip()]
    rc, out = run("章指标.py", ["--json", str(path)], root)
    m = {}
    try:
        m = json.loads(out[out.index("["):])[0]
    except Exception:
        pass
    _, out_s = run("句检.py", [str(path)], root)
    warn_n = re.search(r"warn (\d+)", out_s)
    warn_n = int(warn_n.group(1)) if warn_n else 0

    warns = []

    head = "".join(paras[:3])
    if not (re.search(CONCRETE, head) or re.search(PLACE, head)):
        warns.append(("R1 开篇不知道在哪", "前 3 段", "三段全在写状态，没有一件东西、一个地方",
                      None))
    tail = paras[-1] if paras else ""
    if any(w in tail for w in RESOLVE):
        warns.append(("R2 章末停在决心", f"末段（{len(tail)} 字）",
                      f"「{tail[:30]}」——他要干什么我一猜就知道，那我还等下一章干什么", None))
    if m.get("longest_narration", 0) > 600:
        warns.append(("R4 一大片没人说话", "最长纯叙段",
                      f"{m['longest_narration']} 字没有对白，我会开始跳行", None))
    ku = sum(text.count(w) for w in KU)
    de = sum(text.count(w) for w in DE)
    if ku >= 4 and de == 0:
        warns.append(("R8 苦多无得", "全章", f"苦词 {ku} 次、得词 0 次——读者看不到翻身", None))
    if m.get("head_pronoun_ratio", 0) > 0.25:
        warns.append(("R5 段首单调", "全章", f"{m['head_pronoun_ratio']:.0%} 的段落以他/她开头", None))
    if m.get("quote_run_max", 0) >= 3:
        warns.append(("R6 对白悬空", f"连续 {m['quote_run_max']} 段", "连着几段只有引号，谁在说不知道", None))
    if not re.search(r"[？?]", text) and m.get("dialogue_ratio", 0) == 0:
        warns.append(("R7 没有心跳", "全章", "没有一个问句、没有一句对白", None))

    print(f"\n=== 读者判定 · {path.name} ===")
    if not warns:
        print("  没有触发 WARN。但『我读得下去』这句话要人来说，脚本只负责拦明显的。")
    for tag, where, why, _ in warns:
        print(f"  [WARN] {tag}")
        print(f"         位置：{where}")
        print(f"         原因：{why}")
        print(f"         如果改成这样我会继续读：______（柳直读填）")

    # 1.37.0：删掉五项各 20 分的绝对分（研究报告 §F6）。
    # 理由：`s_cont = 20` 是恒满分、`s_lang = 20 - warn*2` 是线性平移，
    # 实测四章一律 20/20，零区分力；而学界最好的开箱评审与人类偏好一致率只有 73%，
    # 绝对分还要玩家自己校准——所以这里只出"有据可查的几项读数"，判断交给成对盲评。
    print("\n--- 读数（有据可查，不是分数；判断交给 成对盲评.py）---")
    print(f"  开篇是否交底：{'是' if (re.search(CONCRETE, head) or re.search(PLACE, head)) else '否'}"
          f"（章首 200 字里找具体物／地点）")
    print(f"  句检 warn：{warn_n} 条　段落以他/她开头：{m.get('head_pronoun_ratio', 0):.0%}")
    print(f"  最长连续叙述：{m.get('longest_narration', 0)} 字"
          f"　对白占比：{m.get('dialogue_ratio', 0):.1%}（只报数，不设线）")
    print("  以上都不进合门。要判两份稿子谁更好 → 成对盲评.py（三次判读取多数）")
    return len(warns)


def selftest():
    import tempfile, shutil
    root = Path(tempfile.mkdtemp())
    (root / "04_正文_成品").mkdir(parents=True)
    (root / "06_追踪_状态记录").mkdir(parents=True)
    (root / "06_追踪_状态记录" / "数字登记.md").write_text("| 3 | 株 |\n", encoding="utf-8")
    (root / "项目配置.json").write_text(json.dumps({"gate": {}, "lexicon": {"banned_words": []}}, ensure_ascii=False), encoding="utf-8")
    bad = "他很难过。\n他很失望。\n他在心里发誓，一定要赢。\n"
    (root / "04_正文_成品" / "第001章_发誓.md").write_text(bad, encoding="utf-8")
    good = "柜台上摆着三株草。\n“两株。”老板说。\n他把草收回来，塞进怀里。\n"
    (root / "04_正文_成品" / "第002章_收回.md").write_text(good, encoding="utf-8")
    print("自检：坏章应触发 R1/R2/R3/R7，好章 WARN 应少于坏章")
    n_bad = judge(root / "04_正文_成品" / "第001章_发誓.md", root)
    n_good = judge(root / "04_正文_成品" / "第002章_收回.md", root)
    shutil.rmtree(root, ignore_errors=True)
    ok = n_bad >= 3 and n_good < n_bad
    print(f"\n自检结果：{'通过' if ok else '失败'}（坏 {n_bad} / 好 {n_good}）")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="读者判定（只出 WARN）")
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
    if args.file:
        p = Path(args.file)
    else:
        hits = glob.glob(str(root / "04_正文_成品" / f"第{args.chapter}章_*.md"))
        p = Path(hits[0]) if hits else None
    if p is None or not p.exists():
        print(f"[停] 找不到正文（章号 {args.chapter}）")
        sys.exit(1)
    judge(p, root)


if __name__ == "__main__":
    main()
