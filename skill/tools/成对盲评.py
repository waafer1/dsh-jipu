# -*- coding: utf-8 -*-
"""
成对盲评.py —— 两份候选，换两次位置，判三次，只让评审说"哪份更好"

为什么有它：一次成稿、自己打分、五项各 20/20——这不是评审，这是盖章。
研究报告 §2.2 的读数：旧项目第 1 章四项满分，评审零区分力；而学界最好的开箱评审
与人类偏好的一致率也只有 73%（LitBench，EACL 2026），训练过的成对模型能到 78%。
**绝对分不可信，成对比较可信。**

1.37.0 补四件事（都是 1.36.0 的实测缺陷，见研究报告 §F4／§F5）：
  1. **双向卡**：同一对候选出两张卡——`_正序.md`（A 在 X 位）与 `_反序.md`（B 在 X 位）。
     1.36.0 只随机一次顺序、且永远先印 X，等于每章吃一次位置偏差（短提示下 70—100%
     选第二位，见文献）。双向至少能把"位置压过内容"的情况暴露出来。
  2. **三次判读取多数**：正序、反序、加赛（正序）各判一次，按落到文件的大多数定稿；
     三次里同一份全胜才算稳。单次判决的准确率只有 0.73，三次多数可到约 0.82。
  3. **长度控制**：两份字数差 >10% 就警告（长稿胜率 68.0%，z=18.3，LitBench 65.25%
     选更长）；选中的恰好是长稿时在偏好对里标 `长稿胜出`，让人回头看是不是被长度骗了。
  4. **人类锚点**：卡尾附 `00_底座_语文能力/文风基准.md §一` 的第一段锚（只读），
     要求评审判完再读一遍锚，回一句"更接近锚的是哪一份"——锚点是学界单项增益最大的
     手段（+0.29 QWK），而 1.36.0 的卡里一个锚都没有。

用法：
    python 成对盲评.py 006                                   # 出两张卡（正序／反序）
    python 成对盲评.py 006 --pick X --pass 正序 --why "…"     # 第一轮
    python 成对盲评.py 006 --pick Y --pass 反序 --why "…"     # 第二轮
    python 成对盲评.py 006 --pick X --pass 加赛 --why "…"     # 第三轮（可选）
    python 成对盲评.py 006 --finalize --apply                 # 取多数、落成正式正文
    python 成对盲评.py --selftest

退出码：0 正常；1 候选不齐／参数错／票数打平且没加赛／--selftest 用。
"""

import argparse
import glob
import json
import random
import re
import shutil
import statistics
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(__file__).resolve().parent

PASSES = ("正序", "反序", "加赛")
LEN_GAP_WARN = 0.10


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


def find_candidates(root: Path, chapter: str):
    num = int(chapter)
    body = root / "04_正文_成品"
    hits = []
    for pat in (f"第{num:03d}章_*.md", f"第{num}章_*.md"):
        hits += glob.glob(str(body / "_候选" / pat))
    hits = sorted(set(hits))
    if len(hits) < 2:
        alt = []
        for pat in (f"第{num:03d}章_*_A.md", f"第{num:03d}章_*_B.md",
                    f"第{num}章_*_A.md", f"第{num}章_*_B.md"):
            alt += glob.glob(str(body / pat))
        alt = sorted(set(alt))
        if len(alt) >= 2:
            hits = alt
    return hits


def han_count(s: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", s))


def strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        m = re.match(r"^---\s*\n.*?\n---\s*\n", text, re.S)
        if m:
            return text[m.end():]
    return text


def chapter_title(path: Path, root: Path = None, chapter: str = None) -> str:
    """取文件名里的章名（第006章_雨夜 → 雨夜），用于 --apply 落盘。

    候选稿常常只叫「第001章_A.md」，剥完就剩一个 A——那不是章名。
    这时退回项目里已有的正式稿名，再不行才叫未命名。
    **落盘文件名不许是 第001章_A.md。**
    """
    stem = path.stem
    m = re.search(r"第\d+章[_-]?(.*)", stem)
    name = (m.group(1) if m else stem)
    name = re.sub(r"^[_-]+", "", name)
    name = re.sub(r"[_-](候选|定稿|A|B|甲|乙)$", "", name).strip("_- ")
    if name in {"", "A", "B", "候选", "定稿", "甲", "乙"}:
        if root is not None and chapter is not None:
            for p in sorted((root / "04_正文_成品").glob(f"第{int(chapter):03d}章_*.md")):
                if "_候选" in str(p):
                    continue
                t = chapter_title(p)
                if t not in {"", "A", "B", "未命名"}:
                    return t
        return "未命名"
    return name


def mapping_path(root: Path) -> Path:
    return root / "06_追踪_状态记录" / "盲评映射.jsonl"


def pref_path(root: Path) -> Path:
    return root / "06_追踪_状态记录" / "偏好对.jsonl"


def card_path(root: Path, chapter: str, order: str) -> Path:
    return root / "05_质检_审计评审节奏" / f"盲评_第{int(chapter):03d}章_{order}.md"


def anchor_text(root: Path, limit_hz: int = 700):
    """文风基准 §一 的第一段锚（≥300 汉字的 ```text 块）。只读用。"""
    p = root / "00_底座_语文能力" / "文风基准.md"
    if not p.exists():
        return None
    blocks = re.findall(r"```text\s*\n(.*?)```", p.read_text(encoding="utf-8"), re.S)
    for b in blocks:
        if han_count(b) >= 300:
            return b.strip()
    return None


def _card_lines(chapter: str, order: str, texts: dict, lengths: dict, anchor, gap):
    lines = [
        f"# 第{int(chapter):03d}章 · 成对盲评卡（{order}）",
        "",
        f"> 这是**第 {PASSES.index(order) + 1} 轮**（共 3 轮：正序／反序／加赛）。",
        "> 每次只判这一张卡；判完合上，**不要**回头翻上一轮自己的答案，也不要看下一张卡。",
        "> **不许**看 `04_正文_成品/_候选/` 的文件名，也不许打开 `06_追踪_状态记录/盲评映射.jsonl`——",
        "> 看一眼文件名，这次盲评就作废了（近因偏差与来源偏差是稳定存在的）。",
        "",
        "## 判读规矩（先读，再看稿）",
        "",
        "1. **不给绝对分。** 五分制、百分制、「很打动人」这类结论都不要——绝对分没有校准，成对判断才有信号。",
        "2. **必须选一份。** 允许说「两份都烂」，但烂也得说哪份更不烂；真判不出就写「平」，不算逃。",
        "3. **指位置。** 每一份都要指名「我差点在哪一段划走」，抄那一句的头几个字。",
        "4. **只判四件事**：想不想读下一章／有没有哪一句要回头看／有没有「只有这本书会有的东西」／哪一份更像人写的。",
        "5. **不要替写手改。** 你写「这一句我读了两遍才懂」，不写替换句。",
        "6. **长度不算优点。** 两份字数差了 %.0f%%，长的那份更容易显得「信息多」——只比密度，不比字数。"
        % (gap * 100),
        "",
        "## 四问（答完才算交）",
        "",
        "1. 我更想读哪一份的下一章？为什么（指一处）？",
        "2. 各指一处我差点划走的地方（抄开头几个字＋为什么）。",
        "3. 哪一份里有「只有这个世界才会有」的具体物／动作／行话？举两处。",
        "4. 必须选一份：**X 还是 Y**（或「平」）？一句话理由。",
        "",
        "---",
        "",
    ]
    for tag in ("X", "Y"):
        body = texts[tag]
        lines += [
            f"## 候选 {tag}（{lengths[tag]} 字）",
            "",
            body.strip(),
            "",
            "---",
            "",
        ]
    if anchor:
        lines += [
            "## 人类锚点（只读，不参与比较）",
            "",
            "> 判完上面四问再读这一段。读的时候问自己：刚才那两份，**哪一份的密度更像这一段**？",
            "> 把答案写在卡末「锚点对照」一行——这一句是校准，不是结论。",
            "",
            anchor,
            "",
            "**锚点对照**：更接近这段锚的是 ______（X／Y／都不像）；差在哪 ______",
            "",
        ]
    return lines


def build_cards(root: Path, chapter: str, a: Path, b: Path, seed: int):
    """出三张卡：正序（A→X）／反序（B→X）／加赛（再随机一次）。"""
    ta = strip_frontmatter(a.read_text(encoding="utf-8"))
    tb = strip_frontmatter(b.read_text(encoding="utf-8"))
    la, lb = han_count(ta), han_count(tb)
    gap = abs(la - lb) / max(la, lb, 1)
    anchor = anchor_text(root)
    rng = random.Random(seed)
    third = (a, ta, b, tb) if rng.random() < 0.5 else (b, tb, a, ta)

    orders = [
        ("正序", (a, ta, b, tb)),
        ("反序", (b, tb, a, ta)),
        ("加赛", third),
    ]
    cards = []
    for order, (x_path, x_text, y_path, y_text) in orders:
        card = card_path(root, chapter, order)
        card.parent.mkdir(parents=True, exist_ok=True)
        texts = {"X": x_text, "Y": y_text}
        lengths = {"X": han_count(x_text), "Y": han_count(y_text)}
        card.write_text("\n".join(_card_lines(chapter, order, texts, lengths, anchor, gap)),
                        encoding="utf-8")
        cards.append((order, card, x_path, y_path))

    mp = mapping_path(root)
    mp.parent.mkdir(parents=True, exist_ok=True)
    with mp.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "kind": "setup",
            "章": int(chapter),
            "顺序": {order: {
                "X": str(xp.relative_to(root)).replace("\\", "/"),
                "Y": str(yp.relative_to(root)).replace("\\", "/"),
            } for order, _c, xp, yp in cards},
            "长度": {str(a.relative_to(root)).replace("\\", "/"): la,
                     str(b.relative_to(root)).replace("\\", "/"): lb},
            "长度差": round(gap, 3),
            "seed": seed,
            "时间": time.strftime("%Y-%m-%d %H:%M:%S"),
        }, ensure_ascii=False) + "\n")
    return cards, gap


def _records(root: Path, chapter: str):
    mp = mapping_path(root)
    if not mp.exists():
        return []
    out = []
    for line in mp.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if int(rec.get("章", -1)) == int(chapter):
            out.append(rec)
    return out


def latest_setup(root: Path, chapter: str):
    for rec in reversed(_records(root, chapter)):
        if rec.get("kind") == "setup":
            return rec
    return None


def record_pass(root: Path, chapter: str, pick: str, pass_name: str, why: str) -> int:
    setup = latest_setup(root, chapter)
    if not setup:
        print(f"[停] 没有第 {chapter} 章的盲评映射，先跑一次 `python 成对盲评.py {chapter}`")
        return 1
    pick = pick.upper()
    if pick not in ("X", "Y", "平"):
        print("[停] --pick 只能是 X、Y 或 平")
        return 1
    if pass_name not in PASSES:
        print(f"[停] --pass 只能是 {'／'.join(PASSES)}")
        return 1
    order = (setup.get("顺序") or {}).get(pass_name)
    if not order:
        print(f"[停] 没有「{pass_name}」这张卡的映射")
        return 1
    mapped = order.get(pick) if pick != "平" else None
    mp = mapping_path(root)
    with mp.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "kind": "pass",
            "章": int(chapter),
            "pass": pass_name,
            "选": pick,
            "对应": mapped,
            "理由": why.strip(),
            "时间": time.strftime("%Y-%m-%d %H:%M:%S"),
        }, ensure_ascii=False) + "\n")
    print(f"已记第 {pass_name} 轮：{pick}"
          + (f"（＝{Path(mapped).name}）" if mapped else "（平）"))
    if why.strip():
        print(f"  理由：{why.strip()}")
    done = [r for r in _records(root, chapter) if r.get("kind") == "pass"]
    print(f"  已完成 {len(done)}/3 轮：{[r.get('pass') for r in done]}")
    if len(done) < 2:
        print("  下一步：判另一张卡，然后 --pick … --pass "
              + ("反序" if done[0].get("pass") == "正序" else "正序"))
    else:
        print(f"  下一步：python 08_工具_脚本/成对盲评.py {chapter} --finalize（可加 --apply）")
    return 0


def tally(root: Path, chapter: str):
    """按落到文件计票。返回 (票数 dict, 是否有平票, 记录列表)。"""
    votes = {}
    passes = [r for r in _records(root, chapter) if r.get("kind") == "pass"]
    for r in passes:
        f = r.get("对应")
        if not f:
            continue
        votes[f] = votes.get(f, 0) + 1
    top = max(votes.values()) if votes else 0
    leaders = [f for f, v in votes.items() if v == top]
    return votes, (len(leaders) > 1 or top == 0), passes


def finalize(root: Path, chapter: str, apply: bool) -> int:
    setup = latest_setup(root, chapter)
    if not setup:
        print(f"[停] 没有第 {chapter} 章的盲评映射")
        return 1
    votes, tie, passes = tally(root, chapter)
    if not votes:
        print("[停] 还没有任何一轮判读，先 --pick")
        return 1
    print(f"\n=== 第 {int(chapter):03d} 章 · 计票 ===")
    for f, v in sorted(votes.items(), key=lambda kv: -kv[1]):
        print(f"  {Path(f).name}：{v} 票")
    for r in passes:
        print(f"    {r.get('pass')}：{r.get('选')}"
              + (f"（{Path(r['对应']).name}）" if r.get("对应") else "（平）")
              + (f" — {r['理由']}" if r.get("理由") else ""))

    if tie:
        tops = [f for f, v in votes.items() if v == max(votes.values())]
        if len(tops) > 1 and len(passes) < 3:
            print("\n[停] 票数打平——再判一轮加赛（--pick … --pass 加赛 --why \"…\"）")
            return 1
        chosen = tops[0]
        print("\n  NOTE  三轮仍打平，按候选文件名顺序取第一份；这份稿子建议人工终判")
    else:
        chosen = max(votes.items(), key=lambda kv: kv[1])[0]

    lengths = setup.get("长度") or {}
    gap = setup.get("长度差") or 0
    chosen_len = lengths.get(chosen, 0)
    other = [k for k in lengths if k != chosen]
    longer = bool(other) and chosen_len > lengths.get(other[0], 0)
    flag = bool(longer and gap >= LEN_GAP_WARN)

    labels = sorted(set(r.get("选") for r in passes if r.get("对应") == chosen))
    entry = {
        "章": int(chapter),
        "选中": "/".join(labels) if labels else "多数",
        "稿": chosen,
        "得票": votes.get(chosen, 0),
        "轮次": [{"pass": r.get("pass"), "选": r.get("选"), "理由": r.get("理由")} for r in passes],
        "长度": {k: v for k, v in lengths.items()},
        "长稿胜出": flag,
        "理由": "；".join(r.get("理由", "") for r in passes if r.get("理由")),
        "时间": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    pf = pref_path(root)
    pf.parent.mkdir(parents=True, exist_ok=True)
    with pf.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"\n定稿：{Path(chosen).name}（{votes.get(chosen, 0)} 票／共 {len(passes)} 轮）")
    if flag:
        print(f"  NOTE  胜出的这份比另一份长 {gap:.0%}（≥{LEN_GAP_WARN:.0%}）——长稿胜率 68%，"
              "回头确认不是被长度骗的（文风靶的长句项能帮忙）")
    print(f"  偏好对：{pf.relative_to(root)}")

    if apply:
        src = root / chosen
        if not src.exists():
            print(f"[停] 候选稿不见了：{src}")
            return 1
        dst = root / "04_正文_成品" / f"第{int(chapter):03d}章_{chapter_title(src, root, chapter)}.md"
        shutil.copy2(src, dst)
        print(f"已落成正式正文：{dst.relative_to(root)}")
    else:
        print("  加 --apply 可落成正式正文")
    return 0


def selftest():
    import tempfile
    root = Path(tempfile.mkdtemp())
    (root / "04_正文_成品" / "_候选").mkdir(parents=True)
    (root / "06_追踪_状态记录").mkdir(parents=True)
    (root / "00_底座_语文能力").mkdir(parents=True)
    (root / "项目配置.json").write_text("{}", encoding="utf-8")

    a = root / "04_正文_成品" / "_候选" / "第001章_雨夜_A.md"
    b = root / "04_正文_成品" / "_候选" / "第001章_雨夜_B.md"
    a.write_text("---\n章: 001\n---\n" + "他把门板推倒，雨灌进来。" * 20 + "\n", encoding="utf-8")
    b.write_text("---\n章: 001\n---\n" + "他站在门口，觉得很难过。" * 21 + "\n", encoding="utf-8")

    print("自检 A：两张卡（正序／反序），都不许出现文件名")
    cards, gap = build_cards(root, "001", a, b, seed=7)
    leaks = []
    for order, card, _x, _y in cards:
        text = card.read_text(encoding="utf-8")
        if ("雨夜_A" in text) or ("雨夜_B" in text) or ("_候选/第001章" in text):
            leaks.append(order)
    print(f"  卡片：{[c.name for _o, c, _x, _y in cards]}；泄漏：{leaks}")

    print("\n自检 B：三轮判读 → 多数定稿 → 落成正式正文")
    r1 = record_pass(root, "001", "X", "正序", "正序里 X 有具体物")
    r2 = record_pass(root, "001", "Y", "反序", "反序里 Y 有具体物")
    r3 = record_pass(root, "001", "X", "加赛", "加赛仍选先给的那份")
    votes, tie, passes = tally(root, "001")
    rf = finalize(root, "001", apply=True)
    pf = pref_path(root)
    pref_text = pf.read_text(encoding="utf-8") if pf.exists() else ""
    landed = list((root / "04_正文_成品").glob("第001章_*.md"))
    landed_name_ok = len(landed) == 1 and landed[0].stem not in {"第001章_A", "第001章_B"}

    print("\n自检 C：没映射就 --pick 应 exit 1")
    rc2 = record_pass(root, "009", "X", "正序", "无")

    shutil.rmtree(root, ignore_errors=True)
    ok = (not leaks and len(cards) == 3 and r1 == 0 and r2 == 0 and r3 == 0
          and rf == 0 and len(passes) == 3 and bool(pref_text) and landed_name_ok and rc2 == 1)
    print(f"\n自检结果：{'通过' if ok else '失败'}"
          f"（泄漏 {leaks} / 卡 {len(cards)} / 三轮 {len(passes)} / 定稿 {rf} / 偏好 {bool(pref_text)}"
          f" / 文件名 {landed_name_ok} / 无映射 {rc2}）")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="成对盲评：两份候选，双向卡，三次判读取多数")
    ap.add_argument("chapter", nargs="?")
    ap.add_argument("--pick", help="X／Y／平")
    ap.add_argument("--pass", dest="pass_name", default=None, help="正序／反序／加赛")
    ap.add_argument("--why", default="", help="一句话理由（写进偏好对）")
    ap.add_argument("--finalize", action="store_true", help="按多数定稿，写偏好对")
    ap.add_argument("--apply", action="store_true", help="定稿后落成正式正文")
    ap.add_argument("--seed", type=int, default=None, help="随机种子（默认按时间）")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(selftest())
    if not args.chapter:
        ap.print_help()
        sys.exit(1)

    root = find_root()

    if args.pick:
        pn = args.pass_name or "正序"
        sys.exit(record_pass(root, args.chapter, args.pick, pn, args.why))
    if args.finalize:
        sys.exit(finalize(root, args.chapter, args.apply))

    cands = find_candidates(root, args.chapter)
    if len(cands) < 2:
        print(f"[停] 第 {args.chapter} 章候选不足两份（找到 {len(cands)} 份）")
        print("  约定目录：04_正文_成品/_候选/第NNN章_*.md（两份），或 04_正文_成品/第NNN章_*_A.md 与 _B.md")
        print("  双候选不是可选项：一次成稿＝没有比较，没有比较就只能盖章（研究报告 §2.6）")
        sys.exit(1)
    if len(cands) > 2:
        print(f"[警告] 找到 {len(cands)} 份候选，只取前两份：{[Path(c).name for c in cands[:2]]}")

    seed = args.seed if args.seed is not None else random.randrange(1, 10 ** 6)
    a, b = Path(cands[0]), Path(cands[1])
    cards, gap = build_cards(root, args.chapter, a, b, seed)
    print(f"盲评卡（{len(cards)} 张）：{[c.name for _o, c, _x, _y in cards]}")
    print(f"  正序：A 在 X 位；反序：B 在 X 位（seed {seed}）")
    if gap >= LEN_GAP_WARN:
        print(f"  NOTE  两份字数差 {gap:.0%}（≥{LEN_GAP_WARN:.0%}）——长稿胜率 68%，判读时只比密度")
    print(f"  映射：{mapping_path(root).relative_to(root)}（评审不许打开）")
    print(f"  下一步：柳直读判「正序」→ python 08_工具_脚本/成对盲评.py {args.chapter} "
          f"--pick X --pass 正序 --why \"…\"")
    sys.exit(0)


if __name__ == "__main__":
    main()
