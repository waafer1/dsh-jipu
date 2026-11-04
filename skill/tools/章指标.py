# -*- coding: utf-8 -*-
"""
章指标.py —— 一章的硬读数（不判好坏，只给数）

给谁用：查无漏写审计时的"读数"栏、钟有拍判节奏、柳直读判可读性，都从这里取，
不许各人自己估。

出九个数：
  1 字数（去空白）
  2 段数
  3 对白占比（引号内字数 ÷ 总字数）
  4 平均段长 / p90 段长
  5 最长纯叙段（不含引号的段落里字数最多的那段）
  6 最长单句
  7 段首"他/她"占比
  8 连续纯引号段最长串（≥3 要人工判"孤岛"）
  9 空段数（排版）

用法：
    python 章指标.py 04_正文_成品/第001章_*.md
    python 章指标.py --json 第001章.md      # 出 JSON，供别的脚本吃
    python 章指标.py --selftest
"""

import argparse
import glob
import json
import re
import sys
from pathlib import Path

RE_QUOTE_BLOCK = re.compile(r"“[^”]*”")
RE_SENT = re.compile(r"[^。！？…]+[。！？…]?")
RE_HEAD_PRONOUN = re.compile(r"^[他她]")


def strip_frontmatter(text):
    if text.startswith("---"):
        end = text.find("\n---", 1)
        if end != -1:
            return text[end + 4:]
    return text


def cjk_len(s):
    return len(re.sub(r"\s", "", s))


def metrics(path):
    raw = strip_frontmatter(Path(path).read_text(encoding="utf-8"))
    lines = raw.split("\n")
    paras = [l.strip() for l in lines if l.strip()]
    if not paras:
        return {"file": str(path), "chars": 0, "paras": 0}

    total = cjk_len(raw)
    dialogue_chars = sum(cjk_len(m) for m in RE_QUOTE_BLOCK.findall(raw))
    lengths = [cjk_len(p) for p in paras]
    lengths_sorted = sorted(lengths)
    p90 = lengths_sorted[min(len(lengths_sorted) - 1, int(len(lengths_sorted) * 0.9))]

    narration = [cjk_len(RE_QUOTE_BLOCK.sub("", p)) for p in paras]
    longest_narration = max(narration) if narration else 0

    sents = [s.strip() for s in RE_SENT.findall(raw) if s.strip()]
    longest_sent = max((cjk_len(s) for s in sents), default=0)

    head_pron = sum(1 for p in paras if RE_HEAD_PRONOUN.match(p))

    # 连续纯引号段最长串：整段就是一个引号块的段落，连续计数
    best = cur = 0
    for p in paras:
        if len(RE_QUOTE_BLOCK.findall(p)) == 1 and RE_QUOTE_BLOCK.sub("", p).strip() == "":
            cur += 1
            best = max(best, cur)
        else:
            cur = 0

    return {
        "file": str(path),
        "chars": total,
        "paras": len(paras),
        "dialogue_ratio": round(dialogue_chars / total, 4) if total else 0.0,
        "para_mean": round(sum(lengths) / len(lengths), 1),
        "para_p90": p90,
        "longest_narration": longest_narration,
        "longest_sentence": longest_sent,
        "head_pronoun_ratio": round(head_pron / len(paras), 4),
        "quote_run_max": best,
    }


def show(m):
    print(f"\n=== {m['file']} ===")
    print(f"字数 {m['chars']}　段数 {m['paras']}")
    print(f"对白占比 {m['dialogue_ratio']:.2%}")
    print(f"段长 mean {m['para_mean']} ／ p90 {m['para_p90']}")
    print(f"最长纯叙段 {m['longest_narration']} 字　最长单句 {m['longest_sentence']} 字")
    print(f"段首他她 {m['head_pronoun_ratio']:.1%}　连续纯引号段最长 {m['quote_run_max']}")


def selftest():
    import tempfile, os
    sample = """---
t: 1
---

“走吧。”他说。

他站着没动。风把门吹得一开一合。

“走。”

“不走。”

“那就留下。”
"""
    fd, p = tempfile.mkstemp(suffix=".md")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(sample)
    m = metrics(p)
    show(m)
    os.remove(p)
    ok = (m["paras"] == 5 and 0 < m["dialogue_ratio"] < 1
          and m["head_pronoun_ratio"] > 0 and m["quote_run_max"] >= 3)
    print(f"\n自检结果：{'通过' if ok else '失败'}")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="章节硬读数")
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--json", action="store_true", help="只出 JSON")
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
    out = []
    for f in files:
        try:
            m = metrics(f)
            out.append(m)
            if not args.json:
                show(m)
        except FileNotFoundError:
            print(f"[跳过] 不存在：{f}")
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
