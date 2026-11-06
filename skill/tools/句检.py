# -*- coding: utf-8 -*-
"""
句检.py —— 句层硬伤门禁（blocking 必须 0）

判据出处：references/03-门禁手册.md、00_底座_语文能力/句法基准.md。
定位：**blocking 卡门，warn 只报数**。blocking 是"读者会被绊住／排版坏了"的硬伤；
warn 是"读起来可能累"的提示，人工判。

blocking（7 条）：
  B1 长句失控：一句超过 60 字（阈值读 项目配置.json gate.long_sentence_chars）
  B2 引号不配对：一段里 “ 与 ” 数量不等
  B3 重复字：他他／的的／了了／是是／在在／不不
  B4 半角标点混中文：汉字后紧跟 , . ? ! ; :
  B5 段末逗号：段落以 ， 或 、 结尾
  B6 空行连发：连续 2 个以上空行
  B7 括号不配对：（ ）／「 」／《 》

warn（6 条）：
  W1 段首"然后"
  W2 "虽然"段内无"但/却/可是"
  W3 "因为"段内无"所以/才/因此"
  W4 同段"的"超过 4 个
  W5 同段"很"超过 3 个

宾语盘点（--count-object）：统计"把"字句与"被"字句条数，供人工逐条核——
脚本只给条数，不判对错。`章检.py` 用它和审计报告里的数对账。

用法：
    python 句检.py 04_正文_成品/第001章_*.md
    python 句检.py --count-object 04_正文_成品/第001章_*.md
    python 句检.py --selftest
退出码：有 blocking → 1，否则 0。
"""

import argparse
import glob
import json
import re
import sys
from pathlib import Path

DEFAULT_LONG = 60
RE_QUOTE_OPEN = re.compile(r"“")
RE_QUOTE_CLOSE = re.compile(r"”")
RE_DUP = re.compile(r"(他他|她她|的的|了了|是是|在在|不不|就就|都都)")
RE_HALF = re.compile(r"[\u4e00-\u9fa5][,\.\?\!;:]")
RE_END_COMMA = re.compile(r"[，、]\s*$")
RE_PARA_START_THEN = re.compile(r"^然后")
SENT_SPLIT = re.compile(r"[。！？…]+")


def load_long_threshold(project_root=None):
    for base in [project_root, Path.cwd()]:
        if not base:
            continue
        cfg = Path(base) / "项目配置.json"
        if cfg.exists():
            try:
                d = json.loads(cfg.read_text(encoding="utf-8"))
                return int(d.get("gate", {}).get("long_sentence_chars", DEFAULT_LONG))
            except Exception:
                pass
    return DEFAULT_LONG


def strip_frontmatter(text):
    if text.startswith("---"):
        end = text.find("\n---", 1)
        if end != -1:
            return text[end + 4:]
    return text


def check_file(path, long_threshold, show=5):
    text = strip_frontmatter(Path(path).read_text(encoding="utf-8"))
    lines = text.split("\n")
    blocking, warn = [], []

    blank_run = 0
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if not s:
            blank_run += 1
            if blank_run == 2:
                blocking.append(("B6 空行连发", i, "连续 2 个以上空行"))
            continue
        blank_run = 0

        if RE_QUOTE_OPEN.findall(s).__len__() != RE_QUOTE_CLOSE.findall(s).__len__():
            blocking.append(("B2 引号不配对", i, s[:40]))
        for m in RE_DUP.finditer(s):
            blocking.append(("B3 重复字", i, f"「{m.group(1)}」 {s[:40]}"))
        if RE_HALF.search(s):
            blocking.append(("B4 半角标点", i, s[:40]))
        if RE_END_COMMA.search(s):
            blocking.append(("B5 段末逗号", i, s[-20:]))
        if s.count("（") != s.count("）") and ("（" in s or "）" in s):
            blocking.append(("B7 括号不配对", i, s[:40]))

        if RE_PARA_START_THEN.match(s):
            warn.append(("W1 段首然后", i, s[:30]))
        if "虽然" in s and not any(w in s for w in ("但", "却", "可是")):
            warn.append(("W2 虽然无转折", i, s[:40]))
        if "因为" in s and not any(w in s for w in ("所以", "才", "因此")):
            warn.append(("W3 因为无所以", i, s[:40]))
        if s.count("的") > 4:
            warn.append(("W4 的过多", i, f"{s.count('的')} 个"))
        if s.count("很") > 3:
            warn.append(("W5 很过多", i, f"{s.count('很')} 个"))
        if "“" not in s:
            run = 0
            for seg in [x.strip() for x in re.split(r"[。！？]", s) if x.strip()]:
                if len(seg) <= 6:
                    run += 1
                    if run == 3:
                        warn.append(("W6 碎句连发", i, "连续 3 句 ≤6 字：" + s[:30]))
                        break
                else:
                    run = 0

    for seg in SENT_SPLIT.split(text):
        seg = seg.strip()
        if len(seg) > long_threshold:
            blocking.append(("B1 长句失控", 0, f"{len(seg)} 字：{seg[:30]}…"))

    print(f"\n=== {path} ===")
    print(f"blocking {len(blocking)} 条 ／ warn {len(warn)} 条")
    for tag, ln, body in blocking[:show]:
        print(f"  [B] {tag} L{ln} {body}" if ln else f"  [B] {tag} {body}")
    if len(blocking) > show:
        print(f"  …blocking 其余 {len(blocking) - show} 条略")
    for tag, ln, body in warn[:show]:
        print(f"  [W] {tag} L{ln} {body}")
    if len(warn) > show:
        print(f"  …warn 其余 {len(warn) - show} 条略")
    return len(blocking), len(warn)


def count_object(path):
    text = strip_frontmatter(Path(path).read_text(encoding="utf-8"))
    n_ba = len(re.findall(r"把[^，。！？]{1,20}[，。！？]", text))
    n_bei = len(re.findall(r"被[^，。！？]{1,20}[，。！？]", text))
    print(f"\n=== 宾语盘点（{path}）===")
    print(f"「把」字句 {n_ba} 条 ／「被」字句 {n_bei} 条 ／ 合计 {n_ba + n_bei} 条")
    print("逐条人工核：宾语在不在、指代找不找得到。脚本只给条数。")
    print(f"宾语盘点：{n_ba + n_bei} 条")
    return n_ba + n_bei


def selftest():
    import tempfile, os
    samples = [
        ("对话引号不配对", "他说：“走吧。\n"),
        ("的的", "这是他的的草。\n"),
        ("半角标点", "他走了,没回头。\n"),
        ("段末逗号", "他伸手去摸那株草，\n"),
        ("长句", "他" + "伸手摸草又把草放回怀里然后站起来看了看天色觉得还早于是又坐下去等老板开口说话" * 2 + "。\n"),
        ("然后把", "然后他走了。\n"),
        ("把字句", "他把草塞进怀里。草被风吹得发响。\n"),
    ]
    fd, p = tempfile.mkstemp(suffix=".md")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(strip_frontmatter("---\nt: 1\n---\n"))
        for _, s in samples:
            f.write(s + "\n")
    print("自检：应报 blocking ≥5（引号／的的／半角／段末逗号／长句），warn ≥1（段首然后）")
    b, w = check_file(p, 60)
    n = count_object(p)
    os.remove(p)
    ok = b >= 5 and w >= 1 and n >= 2
    print(f"\n自检结果：{'通过' if ok else '失败'}（blocking {b} / warn {w} / 宾语 {n}）")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="句层硬伤门禁")
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--count-object", action="store_true", help="只出宾语盘点条数")
    ap.add_argument("--show", type=int, default=5)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(selftest())
    if not args.paths:
        ap.print_help()
        sys.exit(1)

    files = []
    for p in args.paths:
        hits = glob.glob(p)
        files.extend(hits if hits else [p])

    if args.count_object:
        for f in files:
            count_object(f)
        sys.exit(0)

    threshold = load_long_threshold()
    total_b = total_w = 0
    for f in files:
        try:
            b, w = check_file(f, threshold, args.show)
            total_b += b
            total_w += w
        except FileNotFoundError:
            print(f"[跳过] 不存在：{f}")
    print(f"\n合计 blocking {total_b} ／ warn {total_w}")
    print("句检：blocking " + ("PASS（0 条）" if total_b == 0 else f"FAIL（{total_b} 条）"))
    sys.exit(0 if total_b == 0 else 1)


if __name__ == "__main__":
    main()
