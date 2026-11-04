# -*- coding: utf-8 -*-
"""
数字体检.py —— 每个"数＋单位"都要在账上（0 处待核）

判据：查无漏的信条"数字对不上就是没写完"。正文里出现的每个数量，
必须在 `06_追踪_状态账本/数字登记.md` 里有过登记；没登记的就是"待核"，
要么补登记，要么正文删掉这个数。

口径（重要，不然会误报）：
  · 只抽"数字＋单位"（三株、七枚、两天、五百一十一文），不抽序数与成语
  · 数值比对，不比单位写法（枚/个 视为同一个数）
  · 登记表里的数字全部收进白名单（含乘法结果，如 3×7=21）
  · **这是粗核**：它只能告诉你"这个数没在账上"，不能告诉你"这个数错了"。
    对不对仍要人核——脚本是下限。

用法：
    python 数字体检.py 04_正文_成品/第001章_*.md
    python 数字体检.py --lenient <文件>     # 只报数，不返回 1
    python 数字体检.py --selftest
"""

import argparse
import glob
import re
import sys
from pathlib import Path

UNITS = ("枚|个|只|头|条|张|件|把|支|根|株|颗|块|片|斤|两|钱|步|里|天|夜|年|月|日|时|刻|"
         "人|口|户|家|次|回|成|分|寸|尺|丈|桶|袋|包|瓶|碗|盏|层|间|座|文|铜|银|金")
RE_NUM_UNIT = re.compile(r"([0-9]+(?:\.[0-9]+)?|[一二三四五六七八九十百千万零两半]+)(" + UNITS + r")")
RE_AR = re.compile(r"[0-9]+(?:\.[0-9]+)?")
RE_CN = re.compile(r"[一二三四五六七八九十百千万零两]+")

CN_DIGIT = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
            "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CN_UNIT = {"十": 10, "百": 100, "千": 1000, "万": 10000}


def cn2num(s):
    """中文数字转数值（支持到万，够用）。认不出返回 None。"""
    if not s:
        return None
    if s in ("半",):
        return 0.5
    total = 0
    section = 0
    num = 0
    for ch in s:
        if ch in CN_DIGIT:
            num = CN_DIGIT[ch]
        elif ch in CN_UNIT:
            unit = CN_UNIT[ch]
            if unit == 10000:
                section = (section + (num or 1)) * 10000
                total += section
                section = 0
            else:
                section += (num or 1) * unit
            num = 0
        else:
            return None
    return total + section + num


def load_ledger(project_root=None):
    """从数字登记表收集已登记数值（含简单乘法结果）。"""
    known = set()
    roots = []
    if project_root:
        roots.append(Path(project_root))
    roots.append(Path.cwd())
    for base in roots:
        f = base / "06_追踪_状态账本" / "数字登记.md"
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8")
        for m in RE_AR.finditer(text):
            try:
                known.add(float(m.group()))
            except ValueError:
                pass
        for m in RE_CN.finditer(text):
            v = cn2num(m.group())
            if v is not None:
                known.add(float(v))
        # 乘法回代：3×7、3*7、三乘七
        for a, b in re.findall(r"(\d+)\s*[×xX*]\s*(\d+)", text):
            known.add(float(int(a) * int(b)))
        for line in text.split("\n"):
            nums = [float(x) for x in RE_AR.findall(line)]
            if len(nums) >= 2:
                try:
                    known.add(round(nums[0] * nums[1], 4))
                except Exception:
                    pass
        return known, f
    return known, None


def strip_frontmatter(text):
    if text.startswith("---"):
        end = text.find("\n---", 1)
        if end != -1:
            return text[end + 4:]
    return text


def check(path, known, strict_one=False):
    text = strip_frontmatter(Path(path).read_text(encoding="utf-8"))
    lines = text.split("\n")
    pending = []
    skipped_one = 0
    for i, line in enumerate(lines, 1):
        for m in RE_NUM_UNIT.finditer(line):
            raw, unit = m.group(1), m.group(2)
            val = float(raw) if re.match(r"^[0-9.]+$", raw) else cn2num(raw)
            if val is None:
                continue
            # 「一株」「一枚」多半是泛指，不是账。除非要严核，否则放过。
            if val == 1 and not strict_one:
                skipped_one += 1
                continue
            if val in known:
                continue
            pending.append((i, raw + unit, val, unit, line.strip()[:40]))

    print(f"\n=== {path} ===")
    if skipped_one:
        print(f"（「一＋量词」泛指 {skipped_one} 处已放过；要严核加 --strict-one）")
    if not pending:
        print("待核 0 处")
    for ln, token, val, unit, excerpt in pending:
        print(f"  [待核] L{ln} 「{token}」 {excerpt}")
    print(f"合计 {len(pending)} 处待核")
    return len(pending)


def selftest():
    import tempfile, os
    tmp = Path(tempfile.mkdtemp())
    (tmp / "06_追踪_状态账本").mkdir(parents=True)
    (tmp / "06_追踪_状态账本" / "数字登记.md").write_text(
        "# 数字登记\n\n| 3 | 株 | 001 | 银叶草 |\n| 7 | 枚 | 001 | 铜板 |\n| 500 | 文 | 001 | 余钱 |\n",
        encoding="utf-8",
    )
    body = "他手里有三株草，揣着七枚铜板，还差五百文。\n老板又报了十二文，他没要。\n"
    fd, p = tempfile.mkstemp(suffix=".md", dir=str(tmp))
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(body)
    known, led = load_ledger(tmp)
    print("自检：账上 3/7/500 应通过，十二文 应待核（1 处）")
    n = check(p, known)
    shutil_rm(tmp)
    ok = n == 1
    print(f"自检结果：{'通过' if ok else '失败'}（待核 {n}，应为 1）")
    return 0 if ok else 1


def shutil_rm(p):
    import shutil
    shutil.rmtree(p, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description="数字待核体检")
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--lenient", action="store_true", help="只报数，不返 1")
    ap.add_argument("--strict-one", action="store_true", help="「一＋量词」也严核")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(selftest())
    if not args.paths:
        ap.print_help()
        sys.exit(1)

    known, ledger = load_ledger()
    if ledger is None:
        print("[警告] 没找到 06_追踪_状态账本/数字登记.md —— 全部数量都会算待核")
    else:
        print(f"账上已登记 {len(known)} 个数（{ledger}）")

    files = []
    for p in args.paths:
        hits = glob.glob(p)
        files.extend(hits if hits else [p])
    total = 0
    for f in files:
        try:
            total += check(f, known, args.strict_one)
        except FileNotFoundError:
            print(f"[跳过] 不存在：{f}")
    print(f"\n数字体检：{'PASS（0 处待核）' if total == 0 else f'FAIL（{total} 处待核）'}")
    sys.exit(0 if (total == 0 or args.lenient) else 1)


if __name__ == "__main__":
    main()
