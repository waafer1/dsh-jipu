# -*- coding: utf-8 -*-
"""
骨架体检.py —— 让"骨架序列"有人比对

为什么有它：1.36.0 铺了 `06_追踪_状态记录/骨架序列.json`，但全库没有人读它（研究报告 §F7）。
而 §F9 的结论是：两本不同题材的书第 1 章**专名密度正常、句子指标正常**，读起来却"一个模子"，
原因是五拍骨架同构——被压亏钱 → 身体异变 → 藏／救 → 异象兑现 → 权威到场追问。
专名与句子查不出来，只有把每章的拍序列写下来、拿去比，才看得见。

登记格式（`06_追踪_状态记录/骨架序列.json`）：
    {
      "note": "每章登记一串「拍」，用词随项目自己的类目桥段库",
      "chapters": [
        {"章": 1, "拍": ["被压亏钱", "身体异变", "藏", "异象兑现", "权威到场追问"]},
        {"章": 2, "拍": ["换场地", "试手", "第三方插手"]}
      ]
    }

它查六件事（只报数，出 CHECK 不进合门）：
  1. 这一章登记了没有；拍数 <3 ＝ 这一章没有形状。
  2. 与前面任何一章拍序列**完全相同**（顺序也相同）＝ 复制粘贴的骨架。
  3. 相邻两章共享同一串 ≥3 拍＝连着走同一条路。
  4. 全书开章前两拍重复率 >60% ＝ 每次都这么开场。
  5. 全书拍种类 <8 ＝ 这本书只会几招。
  6. `--compare 另一本的骨架序列.json`：跨书共享 ≥3 拍的连续段＝跨书同构（最贵的那种问题）。

用法：
    python 骨架体检.py 006
    python 骨架体检.py                      # 全书
    python 骨架体检.py --compare ../../另一本书/06_追踪_状态记录/骨架序列.json
    python 骨架体检.py --selftest

退出码：0 正常（CHECK 不拦）；--strict 有 CHECK 则 1。
"""

import argparse
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

MIN_BEATS = 3
OPEN_PAIR_REPEAT_MAX = 0.60
MIN_KINDS = 8


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


def seq_path(root: Path) -> Path:
    return root / "06_追踪_状态记录" / "骨架序列.json"


def load_seq(p: Path):
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  CHECK  骨架序列.json 解析失败：{e}")
        return None
    chapters = data.get("chapters") or []
    out = {}
    for rec in chapters:
        try:
            n = int(rec.get("章"))
        except Exception:
            continue
        beats = [str(b).strip() for b in (rec.get("拍") or []) if str(b).strip()]
        out[n] = beats
    return out


def ngrams(seq, k):
    return [tuple(seq[i:i + k]) for i in range(len(seq) - k + 1)]


def judge(root: Path, chapter=None, strict=False, compare: str = None) -> int:
    print("\n=== 骨架体检 ===")
    seqs = load_seq(seq_path(root))
    if seqs is None:
        print("  CHECK  没有 `06_追踪_状态记录/骨架序列.json`（或解析失败）——这本书的骨架没登记过")
        return 1 if strict else 0
    if not seqs:
        print("  CHECK  骨架序列是空的——从第 1 章开始登记「拍」")
        return 1 if strict else 0

    nums = sorted(seqs)
    checks = []

    if chapter is not None:
        n = int(chapter)
        if n not in seqs:
            checks.append(f"第 {n:03d} 章没登记骨架（最新是第 {max(nums):03d} 章）")
        else:
            beats = seqs[n]
            print(f"第 {n:03d} 章：{len(beats)} 拍 → {' → '.join(beats) or '（空）'}")
            if len(beats) < MIN_BEATS:
                checks.append(f"第 {n:03d} 章只有 {len(beats)} 拍（<{MIN_BEATS}）——这一章没有形状")
            for m in nums:
                if m != n and seqs[m] == beats and beats:
                    checks.append(f"第 {n:03d} 章的拍序列与第 {m:03d} 章**完全相同**——骨架复制")
                    break
            prev = [m for m in nums if m < n]
            if prev:
                m = prev[-1]
                shared = set(ngrams(seqs[m], 3)) & set(ngrams(beats, 3))
                if shared:
                    checks.append(f"第 {m:03d} 章与第 {n:03d} 章共享连续三拍「{'→'.join(sorted(shared)[0])}」"
                                  "——相邻两章走了同一条路")

    # 全书
    open_pairs = [tuple(seqs[n][:2]) for n in nums if len(seqs[n]) >= 2]
    if len(open_pairs) >= 3:
        from collections import Counter
        c = Counter(open_pairs)
        top, cnt = c.most_common(1)[0]
        ratio = cnt / len(open_pairs)
        if ratio > OPEN_PAIR_REPEAT_MAX:
            checks.append(f"{ratio:.0%} 的章以同一组前两拍开场（{'→'.join(top)}）——每次都这么起手")

    kinds = {b for n in nums for b in seqs[n]}
    print(f"全书：{len(nums)} 章登记／{len(kinds)} 种拍／共 {sum(len(seqs[n]) for n in nums)} 拍")
    if len(kinds) < MIN_KINDS:
        checks.append(f"全书只有 {len(kinds)} 种拍（<{MIN_KINDS}）——这本书只会这几招")

    dup = 0
    seen = {}
    for n in nums:
        key = tuple(seqs[n])
        if key and key in seen:
            dup += 1
        else:
            seen[key] = n
    if dup:
        checks.append(f"{dup} 章的拍序列与前面某章一模一样——换个骨架再写")

    if compare:
        other = load_seq(Path(compare))
        if other is None:
            checks.append(f"跨书对照失败：读不到 `{compare}`")
        else:
            theirs = set()
            for n in other:
                theirs |= set(ngrams(other[n], 3))
            mine = set()
            for n in nums:
                mine |= set(ngrams(seqs[n], 3))
            shared = mine & theirs
            set_a = {b for n in nums for b in seqs[n]}
            set_b = {b for n in other for b in other[n]}
            jac = len(set_a & set_b) / max(len(set_a | set_b), 1)
            print(f"跨书：拍集合 Jaccard {jac:.2f}／共享连续三拍 {len(shared)} 段")
            if len(shared) >= 2:
                sample = "；".join("→".join(s) for s in list(shared)[:3])
                checks.append(f"跨书共享 {len(shared)} 段连续三拍（{sample}）——同一个模子")
            elif jac >= 0.5:
                checks.append(f"跨书拍集合重合 {jac:.0%}——用词不同，形状相同")

    if checks:
        print("CHECK（不进合门，命中即改）：")
        for c in checks:
            print(f"  CHECK  {c}")
    else:
        print("PASS  这一章有形状，也没有跟前面的章撞骨架")
    return 1 if (checks and strict) else 0


def selftest():
    import tempfile
    import shutil
    root = Path(tempfile.mkdtemp())
    (root / "06_追踪_状态记录").mkdir(parents=True)
    (root / "项目配置.json").write_text("{}", encoding="utf-8")

    var = {"note": "t", "chapters": [
        {"章": 1, "拍": ["被压亏钱", "身体异变", "藏", "异象兑现", "权威到场追问"]},
        {"章": 2, "拍": ["换场地", "试手", "第三方插手", "收摊"]},
        {"章": 3, "拍": ["旧账上门", "当众比试", "露底", "旁观者误读", "反手"]},
        {"章": 4, "拍": ["误传", "追债", "夜间出城", "遇到同行"]},
        {"章": 5, "拍": ["借势", "讨价还价", "被识破", "换条件"]},
    ]}
    seq_path(root).write_text(json.dumps(var, ensure_ascii=False), encoding="utf-8")
    print("自检 A：五章各自不同 → 应 0 CHECK")
    rcA = judge(root, 3, strict=True)

    same = {"note": "t", "chapters": [
        {"章": 1, "拍": ["被压亏钱", "身体异变", "藏", "异象兑现", "权威到场追问"]},
        {"章": 2, "拍": ["被压亏钱", "身体异变", "藏", "异象兑现", "权威到场追问"]},
        {"章": 3, "拍": ["被压亏钱", "身体异变", "藏", "异象兑现", "权威到场追问"]},
        {"章": 4, "拍": ["被压亏钱", "身体异变", "藏"]},
    ]}
    seq_path(root).write_text(json.dumps(same, ensure_ascii=False), encoding="utf-8")
    print("\n自检 B：四章同骨架 → 应 CHECK（strict 1）")
    rcB = judge(root, 2, strict=True)

    seq_path(root).unlink()
    print("\n自检 C：没有骨架序列 → 应 CHECK（strict 1）")
    rcC = judge(root, None, strict=True)

    seq_path(root).write_text(json.dumps(same, ensure_ascii=False), encoding="utf-8")
    other = root / "另一本.json"
    other.write_text(json.dumps({"note": "o", "chapters": [
        {"章": 1, "拍": ["开局赔钱", "身体异变", "藏", "异象兑现", "长辈到场追问"]},
        {"章": 2, "拍": ["身体异变", "藏", "异象兑现"]},
    ]}, ensure_ascii=False), encoding="utf-8")
    print("\n自检 D：跨书共享连续三拍 → 应 CHECK（strict 1）")
    rcD = judge(root, None, strict=True, compare=str(other))

    shutil.rmtree(root, ignore_errors=True)
    ok = (rcA == 0) and (rcB == 1) and (rcC == 1) and (rcD == 1)
    print(f"\n自检结果：{'通过' if ok else '失败'}（A {rcA} / B {rcB} / C {rcC} / D {rcD}）")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="骨架体检：把每章的拍序列表拿来比")
    ap.add_argument("chapter", nargs="?")
    ap.add_argument("--compare", default=None, help="另一本书的 骨架序列.json（跨书同构检查）")
    ap.add_argument("--strict", action="store_true", help="有 CHECK 就 exit 1")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        sys.exit(selftest())
    root = find_root()
    sys.exit(judge(root, args.chapter, args.strict, args.compare))


if __name__ == "__main__":
    main()
