# -*- coding: utf-8 -*-
"""
画面检.py —— 画面感报数工具（计谱 1.1.8 新增，底座通用件）

出处：assets/画面例句库.md（总判据两关 + §五·六滤镜词 + §四尸检）。
定位：**只报数、不判分**——脚本是下限，不是上限；读数贴进审计，人工按例句库判读。

查四类（都是语法层可数的"画面感症状"）：

1. 滤镜词（视角病，例句库 §五·六）：
   视觉类：看见 看到 瞧见 望见 观察
   听嗅类：听到 听见 闻到 嗅到
   心类：  注意到 感觉到 感到 意识到
   口径：滤镜词删掉，直接给事件（"她看见花园荒了"→"花园荒了"）。
   注意：情绪直给是通俗尺的合法动作（"我很痛"不算病）；但"感到＋名词"
   （感到一阵寒意）多半是状态不成像，要人工看。

2. 宣布词（例句库 §〇 宣布＋证据法则）：
   神秘 诡异 恐怖 可怕 美丽 漂亮 英俊 丑陋 奇怪 古怪
   口径：宣布词必须连着证据（"容颜无双"＋"黑发如瀑"）；
   只有宣布没有证据＝空洞。逐个人工核：这个词旁边有没有图。

3. 氛围状态词（尸检 4"状态不成像"）：
   气氛 氛围 显得
   口径：气氛、氛围词读者脑子里不成像；"显得漂亮"是评价不是图。

4. 段首"他/她"（文风基准：段首不用"他"起句）：
   口径：用动作、物件、对白、时间起句。占比报出来人工判。

用法：
    python 画面检.py 04_正文_成品/第001章_*.md
    python 画面检.py <文件1> <文件2> ...
    python 画面检.py --top 5 <文件>     # 每类最多摘 5 处例句
    python 画面检.py --selftest         # 自检

退出码恒为 0（只报数，不卡门）。
"""

import argparse
import glob
import re
import sys

FILTER_VIS = ["看见", "看到", "瞧见", "望见", "观察到"]
FILTER_AUD = ["听到", "听见", "闻到", "嗅到"]
FILTER_MENT = ["注意到", "感觉到", "感到", "意识到"]
LABEL_WORDS = ["神秘", "诡异", "恐怖", "可怕", "美丽", "漂亮", "英俊", "丑陋", "奇怪", "古怪"]
ATMOS_WORDS = ["气氛", "氛围", "显得"]


def build_regex(words):
    return re.compile("(" + "|".join(words) + ")")


RE_FILTER_VIS = build_regex(FILTER_VIS)
RE_FILTER_AUD = build_regex(FILTER_AUD)
RE_FILTER_MENT = build_regex(FILTER_MENT)
RE_LABEL = build_regex(LABEL_WORDS)
RE_ATMOS = build_regex(ATMOS_WORDS)
RE_HEI_START = re.compile(r"^[他她]")


def strip_frontmatter(text):
    """去掉 frontmatter（--- 包头的头部），避免元数据里命中词。"""
    if text.startswith("---"):
        end = text.find("\n---", 1)
        if end != -1:
            return text[end + 4:]
    return text


def scan_file(path, top):
    with open(path, encoding="utf-8") as f:
        text = strip_frontmatter(f.read())

    lines = text.split("\n")
    paras = [ln for ln in lines if ln.strip()]
    findings = {
        "滤镜·视觉": [],
        "滤镜·听嗅": [],
        "滤镜·心理": [],
        "宣布词": [],
        "氛围状态词": [],
        "段首他她": [],
    }

    for idx, line in enumerate(lines, 1):
        for m in RE_FILTER_VIS.finditer(line):
            findings["滤镜·视觉"].append((idx, m.group(1), line.strip()[:60]))
        for m in RE_FILTER_AUD.finditer(line):
            findings["滤镜·听嗅"].append((idx, m.group(1), line.strip()[:60]))
        for m in RE_FILTER_MENT.finditer(line):
            findings["滤镜·心理"].append((idx, m.group(1), line.strip()[:60]))
        for m in RE_LABEL.finditer(line):
            findings["宣布词"].append((idx, m.group(1), line.strip()[:60]))
        for m in RE_ATMOS.finditer(line):
            findings["氛围状态词"].append((idx, m.group(1), line.strip()[:60]))
        if RE_HEI_START.match(line.strip()):
            findings["段首他她"].append((idx, line.strip()[0], line.strip()[:60]))

    n_para = max(len(paras), 1)
    print(f"\n=== {path} ===")
    print(f"段落行数：{len(paras)}")
    total = 0
    for name, hits in findings.items():
        total += len(hits)
        extra = ""
        if name == "段首他她":
            extra = f"（占比 {len(hits) / n_para:.0%}，参考：越低越好，>20% 先查段首）"
        print(f"[{name}] {len(hits)} 处{extra}")
        for ln, word, excerpt in hits[:top]:
            print(f"    L{ln} 「{word}」 {excerpt}")
        if len(hits) > top:
            print(f"    …其余 {len(hits) - top} 处略")
    print(f"合计命中：{total} 处（读数贴进审计，人工按例句库判读；本脚本不判 PASS/FAIL）")
    return total


def selftest():
    sample = """---
title: 测试
---

花园荒了。
她看见花园荒了，感到一阵神秘的氛围。
他注意到身后有脚步声。
他听见门响，闻到焦味。
她显得很漂亮。
他看到远处有火光。"""
    import tempfile, os
    fd, p = tempfile.mkstemp(suffix=".md")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(sample)
    print("自检：样文应命中 视觉2／心理2／听嗅2／宣布1／氛围2／段首他3（frontmatter 不计）")
    total = scan_file(p, top=3)
    os.remove(p)
    print("自检结果：通过" if total >= 10 else "自检结果：失败（命中过少）")
    return 0


def main():
    ap = argparse.ArgumentParser(description="画面感报数工具（只报数不判分）")
    ap.add_argument("paths", nargs="*", help="章节文件或通配符")
    ap.add_argument("--top", type=int, default=3, help="每类最多摘几处例句（默认 3）")
    ap.add_argument("--selftest", action="store_true", help="跑自检样文")
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
    grand = 0
    for f in files:
        try:
            grand += scan_file(f, args.top)
        except FileNotFoundError:
            print(f"[跳过] 文件不存在：{f}")
        except UnicodeDecodeError:
            print(f"[跳过] 非 UTF-8：{f}")
    print(f"\n总命中：{grand} 处 / {len(files)} 个文件")


if __name__ == "__main__":
    main()
