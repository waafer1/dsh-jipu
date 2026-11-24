# -*- coding: utf-8 -*-
"""
语汇漂移体检.py —— 查通用层里有没有混进"某一本书"的词

为什么有它：1.36.0 清过一轮 `references/02-正文口径.md` 的串味，但 1.37.0 复查时
另外 12 处还在（`references/01-细纲施工.md:163`、`04-爽点与节奏.md:76/111`、
`05-状态与追踪.md:42`、`agents/jipu-writer.md:50/67`、`jipu-auditor.md:56`、
`jipu-memory.md:61`、`jipu-pacer.md:46`、`jipu-worldbuilder.md:51/77`）——
通用口径里带着上一本书的词法，新书就被强行套用上一本的词，这是"所有书一个声音"的
直接来源（研究报告 §F8）。

它干一件事：拿黑名单去扫通用层（`SKILL.md`、`references/`、`agents/`、`tools/` 的
注释与文档串），报告"哪个文件第几行出现了哪个词"。黑名单默认取
`assets/语汇黑名单_历史泄漏.md`（历史上真泄漏过的词，逐个记着出处）；也可以
`--words` 指向自己的清单，或从 `项目配置.json` 的 `lexicon.book_only_words` 取。

用法（维护通用层时跑，不参与写章）：
    python 语汇漂移体检.py                    # 扫插件 skill 目录
    python 语汇漂移体检.py --skill-root 路径
    python 语汇漂移体检.py --words 我的词表.txt
    python 语汇漂移体检.py --strict           # 有命中就 exit 1
    python 语汇漂移体检.py --selftest

退出码：0 无命中（或默认只报数）；--strict 有命中则 1。
"""

import argparse
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
SKILL_DIR = HERE.parent
DEFAULT_WORDS = SKILL_DIR / "assets" / "语汇黑名单_历史泄漏.md"

SCAN_GLOBS = ("SKILL.md", "references/*.md", "agents/*.md", "tools/*.py")


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


def load_words(path: Path, root: Path = None):
    """返回 [(词, 备注)]。md 里按 `- 词｜备注` 或纯词一行。"""
    words = []
    if path and path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or s.startswith(">"):
                continue
            s = re.sub(r"^[-*+]\s*", "", s)
            if "｜" in s or "|" in s:
                parts = re.split(r"[｜|]", s, maxsplit=1)
                w, note = parts[0].strip(), parts[1].strip()
            else:
                w, note = s, ""
            w = w.strip("` 　*")
            if w and len(w) <= 12:
                words.append((w, note))
    if root is not None:
        cfgp = root / "项目配置.json"
        if cfgp.exists():
            try:
                cfg = json.loads(cfgp.read_text(encoding="utf-8"))
                for w in (cfg.get("lexicon") or {}).get("book_only_words") or []:
                    w = str(w).strip()
                    if w:
                        words.append((w, "项目配置 lexicon.book_only_words"))
            except Exception:
                pass
    # 去重保序
    seen, out = set(), []
    for w, n in words:
        if w not in seen:
            seen.add(w)
            out.append((w, n))
    return out


def scan(skill_root: Path, words):
    hits = []
    files = []
    for g in SCAN_GLOBS:
        files += sorted(skill_root.glob(g))
    me = Path(__file__).resolve()
    for f in files:
        # 黑名单自己、本脚本的 selftest 字符串都不算漂移
        if f.name.startswith("语汇黑名单") or f.resolve() == me:
            continue
        try:
            lines = f.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        for i, line in enumerate(lines, 1):
            for w, _note in words:
                if w in line:
                    hits.append((f, i, w, line.strip()))
    return hits, files


def report(skill_root: Path, words, strict: bool) -> int:
    print("\n=== 语汇漂移体检 ===")
    if not words:
        print("  CHECK  没有词表——`assets/语汇黑名单_历史泄漏.md` 不存在，也没有 lexicon.book_only_words")
        return 1 if strict else 0
    hits, files = scan(skill_root, words)
    print(f"词表 {len(words)} 条／扫了 {len(files)} 个文件")
    if not hits:
        print("  PASS  通用层没有出现黑名单里的词")
        return 0
    print("CHECK（通用层混进了单书词，命中即改）：")
    by_file = {}
    for f, i, w, line in hits:
        by_file.setdefault(f, []).append((i, w, line))
    for f, items in sorted(by_file.items(), key=lambda kv: -len(kv[1])):
        rel = f.relative_to(skill_root)
        print(f"  {rel}（{len(items)} 处）")
        for i, w, line in items[:4]:
            print(f"    :{i}  「{w}」  {line[:70]}")
        if len(items) > 4:
            print(f"    ……另 {len(items) - 4} 处")
    print(f"\n合计 {len(hits)} 处命中／{len(by_file)} 个文件"
          "——通用口径只写机制，具体物名归 `00_底座_语文能力/文风基准.md` §四")
    return 1 if strict else 0


def selftest():
    import tempfile
    import shutil
    root = Path(tempfile.mkdtemp())
    (root / "assets").mkdir(parents=True)
    (root / "references").mkdir(parents=True)
    wl = root / "assets" / "语汇黑名单_历史泄漏.md"
    wl.write_text("# 黑名单\n- 池子｜旧书的能量单位\n- 军需单｜旧书的单据名\n", encoding="utf-8")
    (root / "references" / "a.md").write_text("他说池子里还有三成。\n", encoding="utf-8")
    (root / "references" / "b.md").write_text("干干净净的一句话。\n", encoding="utf-8")

    words = load_words(wl)
    print("自检 A：一个文件命中 → 应报 1 处、strict 退出 1")
    rcA = report(root, words, strict=True)

    (root / "references" / "a.md").unlink()
    print("\n自检 B：没有命中 → 应退出 0")
    rcB = report(root, words, strict=True)

    print("\n自检 C：词表不存在 → 应 CHECK（strict 退出 1）")
    rcC = report(root, load_words(root / "nope.md"), strict=True)

    shutil.rmtree(root, ignore_errors=True)
    ok = (rcA == 1) and (rcB == 0) and (rcC == 1)
    print(f"\n自检结果：{'通过' if ok else '失败'}（A {rcA} / B {rcB} / C {rcC}）")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="语汇漂移体检：通用层不许带单书词")
    ap.add_argument("--skill-root", default=str(SKILL_DIR))
    ap.add_argument("--words", default=None, help="词表（默认 assets/语汇黑名单_历史泄漏.md）")
    ap.add_argument("--strict", action="store_true", help="有命中就 exit 1")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        sys.exit(selftest())
    wl = Path(args.words) if args.words else DEFAULT_WORDS
    words = load_words(wl, find_root())
    sys.exit(report(Path(args.skill_root), words, args.strict))


if __name__ == "__main__":
    main()
