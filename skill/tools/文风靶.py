# -*- coding: utf-8 -*-
"""
文风靶.py —— 把"文风"变成可测的数（本书自己的靶，不是通用阈值）

为什么有它：1.35 之前，句子立不立得住有脚本查（句检），但"读起来像不像这本书"全凭感觉。
结果正文全部合格、全部一个声音。这个脚本干一件事：拿 `00_底座_语文能力/文风基准.md`
当锚，量出这一章离锚多远。

1.37.0 改了三处（都是 1.36.0 的实测缺陷）：
  1. **切句口径**：1.36.0 把 `；` 和换行也当句末，长句被切成中句——人工锚点「画面例句库」
     的长句占比因此被低估 1.7 倍（0.391 → 0.224）。现在默认只按 `。！？!?…` 断句，
     `--split=loose` 保留旧口径（只为对照旧数据）。
  另有一项只报数：**疑似砍词**（可以→可／已经→已…），`02-正文口径.md` §十六。\n\n  2. **靶值来自基准段落**：`--calibrate` 真的去量那三段 500—800 字的锚，把结果写进
     `项目配置.json` 的 `style`（并记 `style_source`）。1.36.0 的 `--baseline` 只查
     "填没填"，靶值永远是全局常数——那是换了个地方继续装饰。
  3. **判据换成分布形状**：长句占比 0.10（T1）／0.15（T2）／0.06（T0）＋`p90 ≥ 30`＋
     `≤10 字句 ≤ 0.30`。1.36.0 那条 `8—20 字句 ≤0.42` 在修正切句后对人类锚点也会误报，
     降级为"只报数"（它描述的是分布众数，不是 AI 味）。

量的项（"密度与起伏"，不是"好坏"）：
  sentence_cv_min      句长变异系数下限（人类参考 0.449，AI 约 0.376；阈值 0.42 落在噪声内）
  long_sent_ratio_min  ≥30 字长句占比下限 —— 低＝没有铺陈
  short_sent_ratio_max ≤10 字短句占比上限 —— 高＝全是断句
  p90_len_min          句长 90 分位下限 —— 右尾有多长
  four_char_seg_max    四字落点段占比上限
  connective_per_k_min 显性连接词每千字下限
  metaphor_per_k_min/max 比喻每千字区间
  paragraph_cv_min     段长变异系数下限
  mid_len_ratio_max    8—20 字句占比（1.37.0 起**只报数**，不进判定）

弱信号（四项里至少命中两项才提示，单项不判）：破折号 >5/千字、`不是…而是` >0.2/千字、
关联词完整式（因为…所以／虽然…但是／不但…而且）>1.0/千字、短句占比 >0.30。

**对白占比永远只报数**（作者 2026-11-06 令：对白只报数，不设上下限）。脚本会拿它和
"本书最近三章均值"作对比，只提示，不进 PASS／FAIL。

用法：
    python 文风靶.py 006                      # 量第 6 章（默认 T1 靶）
    python 文风靶.py 006 --tier T2            # 按 T2 靶（长句要求更高）
    python 文风靶.py --calibrate              # 量基准段落，把靶值写进项目配置
    python 文风靶.py --baseline               # 只查基准填没填、靶值从哪来
    python 文风靶.py 006 --strict             # 有 CHECK 就 exit 1
    python 文风靶.py 006 --split=loose        # 旧切句口径（只为对照 1.36.0 数据）
    python 文风靶.py --selftest

退出码：0 正常（默认无论 CHECK 都 0）；--strict 下有 CHECK 则 1；--baseline／--calibrate
不合格则 1。
"""

import argparse
import glob
import json
import os
import re
import statistics
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(__file__).resolve().parent

CONNECTIVES = ["于是", "然而", "只是", "但是", "可是", "接着", "随即", "与此同时",
               "半晌", "忽然", "猛地", "骤然", "然后", "而", "便", "就"]
METAPHOR_WORDS = ["像", "仿佛", "好像", "似的", "一样", "一般", "如同"]
ABSTRACT_WORDS = ["气氛", "情绪", "感觉", "氛围", "状态", "力量", "气势", "气息",
                  "意志", "精神"]
SENSE_WORDS = ["冷", "热", "烫", "凉", "疼", "痛", "麻", "痒", "硬", "软",
               "涩", "腥", "苦", "甜", "呛", "酸"]
NEG_PARALLEL = re.compile(r"不是[^，。！？!?…]{1,20}?[，,]?\s*而是")
CONJ_PAIRS = [(re.compile(r"因为[^。！？!?]{2,60}所以"), ),
              (re.compile(r"虽然[^。！？!?]{2,60}但是"), ),
              (re.compile(r"不但[^。！？!?]{2,60}而且"), )]

# 档位对长句的要求（过渡章不需要大铺陈）
TIER_LONG_SENT = {"T0": 0.06, "T1": 0.10, "T2": 0.15}

STYLE_KEYS = [
    ("sentence_cv_min", 0.42),
    ("long_sent_ratio_min", 0.10),
    ("short_sent_ratio_max", 0.30),
    ("p90_len_min", 30),
    ("four_char_seg_max", 0.16),
    ("connective_per_k_min", 1.2),
    ("metaphor_per_k_min", 1.5),
    ("metaphor_per_k_max", 9.0),
    ("paragraph_cv_min", 0.45),
    ("mid_len_ratio_max", 0.42),   # 只报数（1.37.0），留着是为了报告里能对照
]

JUDGED = [k for k, _ in STYLE_KEYS if k != "mid_len_ratio_max"]

# 基准段落"像 AI 稿"的判据（研究报告 §F3 的实测区间）。
# 一道都没踩：正常人类段落。踩两项及以上：不许拿它当尺——否则校准等于把 AI 特征锁成合法区间。
BASELINE_SMELL = (
    ("sent_cv", "<", 0.40, "句长起伏 CV {v:.2f} < 0.40（人类参考 0.449，AI 常见 0.376）"),
    ("long_sent_ratio", "<", 0.05, "≥30 字长句 {v:.1%} < 5%（人类范例句 39.1%）"),
    ("short_sent_ratio", ">", 0.45, "≤10 字短句 {v:.1%} > 45%（AI 爱把句子切碎）"),
    ("four_char_seg", ">", 0.22, "四字整段 {v:.1%} > 22%（人类范例句 9.9%）"),
    ("mid_len_ratio", ">", 0.52, "8—20 字句占 {v:.1%} > 52%（人类范例句 22—35%；句子整齐是 AI 最稳的标记）"),
)

PLACEHOLDER = re.compile(r"<待填[^>]*>")


# ---------- 基础 ----------

def find_root() -> Path:
    env = os.environ.get("JIPU_ROOT")
    if env and (Path(env) / "项目配置.json").exists():
        return Path(env)
    cur = Path.cwd().resolve()
    for base in [cur] + list(cur.parents):
        if (base / "项目配置.json").exists():
            return base
    return cur


def load_cfg(root: Path) -> dict:
    p = root / "项目配置.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[警告] 项目配置.json 解析失败：{e}（按空配置处理）")
        return {}


def han_count(s: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", s))


def strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        m = re.match(r"^---\s*\n.*?\n---\s*\n", text, re.S)
        if m:
            return text[m.end():]
    return text


def paragraphs(body: str):
    out = []
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        out.append(line)
    return out


SPLIT_STRICT = re.compile(r"[。！？!?…]+[”’\"']?")
SPLIT_LOOSE = re.compile(r"(?<=[。！？!?…；])|\n+")


def split_sentences(body: str, mode: str = "strict"):
    """切句。

    1.37.0 默认 strict：只按 `。！？!?…`（含右引号收尾）断句。
    `；` 是分句号、换行不是句末——1.36.0 把它们当句末，长句被切成中句，
    人工锚点的长句占比因此少算 1.7 倍（见研究报告 §F1）。
    """
    if mode == "loose":
        parts = SPLIT_LOOSE.split(body)
    else:
        parts = SPLIT_STRICT.split(body)
    return [p.strip() for p in parts if p and han_count(p) > 0]


def dialogue_chars(body: str) -> int:
    total = 0
    for m in re.finditer(r"“([^”]{0,2000})”|\"([^\"]{0,2000})\"", body):
        seg = m.group(1) or m.group(2) or ""
        total += han_count(seg)
    return total


def cv(vals):
    if len(vals) < 2:
        return 0.0
    mean = statistics.fmean(vals)
    if mean <= 0:
        return 0.0
    return statistics.pstdev(vals) / mean


def pct(vals, q):
    if not vals:
        return 0
    s = sorted(vals)
    idx = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
    return s[idx]


def per_k(count, hz):
    return round(count * 1000.0 / hz, 2) if hz else 0.0


# ---------- 测量 ----------

def measure(body: str, mode: str = "strict") -> dict:
    hz = han_count(body)
    sents = split_sentences(body, mode)
    lens = [han_count(s) for s in sents] or [0]
    paras = paragraphs(body)
    plens = [han_count(p) for p in paras] or [0]

    dash = len(re.findall(r"——|—", body))
    neg = len(NEG_PARALLEL.findall(body))
    conj = sum(1 for pat in CONJ_PAIRS for _ in pat[0].finditer(body))

    m = {
        "chars": hz,
        "paras": len(paras),
        "sents": len(sents),
        "sent_mean": round(statistics.fmean(lens), 1),
        "sent_cv": round(cv(lens), 3),
        "sent_max": max(lens),
        "p90_len": pct(lens, 0.9),
        "mid_len_ratio": round(sum(1 for x in lens if 8 <= x <= 20) / len(lens), 3),
        "long_sent_ratio": round(sum(1 for x in lens if x >= 30) / len(lens), 3),
        "short_sent_ratio": round(sum(1 for x in lens if x <= 10) / len(lens), 3),
        "para_mean": round(statistics.fmean(plens), 1),
        "para_cv": round(cv(plens), 3),
        "four_char_seg": round(sum(1 for x in plens if x == 4) / len(plens), 3),
        "dialogue_ratio": round(dialogue_chars(body) / hz, 3) if hz else 0.0,
        "connective_per_k": per_k(sum(body.count(w) for w in CONNECTIVES), hz),
        "metaphor_per_k": per_k(sum(body.count(w) for w in METAPHOR_WORDS), hz),
        "abstract_per_k": per_k(sum(body.count(w) for w in ABSTRACT_WORDS), hz),
        "sense_per_k": per_k(sum(body.count(w) for w in SENSE_WORDS), hz),
        "dash_per_k": per_k(dash, hz),
        "neg_parallel_per_k": per_k(neg, hz),
        "conj_pair_per_k": per_k(conj, hz),
        "head_pronoun": round(
            sum(1 for p in paras if p[:1] in ("他", "她", "它")) / max(len(paras), 1), 3),
    }
    return m


# ---------- 判 ----------

def targets_for(style: dict, tier: str = "T1") -> dict:
    t = dict(STYLE_KEYS)
    t.update({k: style[k] for k in style if k in t})
    # 档位只调长句下限（T0 过渡章不需要大铺陈；T2 卷首尾要）
    if tier in TIER_LONG_SENT:
        t["long_sent_ratio_min"] = max(t["long_sent_ratio_min"], TIER_LONG_SENT[tier])
    return t


def judge(m: dict, style: dict, tier: str = "T1"):
    rows = []  # (键, 含义, 靶, 实测, ok, 说明)
    t = targets_for(style, tier)

    def add(key, meaning, target, got, ok, note):
        rows.append((key, meaning, target, got, ok, note))

    add("sentence_cv", "句长起伏", f"≥{t['sentence_cv_min']}", m["sent_cv"],
        m["sent_cv"] >= t["sentence_cv_min"], "句长太均匀，读者读到中段会走神")
    add("long_sent_ratio", "≥30 字长句占比", f"≥{t['long_sent_ratio_min']}", m["long_sent_ratio"],
        m["long_sent_ratio"] >= t["long_sent_ratio_min"], "没有铺陈，全章短促，缺肉")
    add("short_sent_ratio", "≤10 字短句占比", f"≤{t['short_sent_ratio_max']}", m["short_sent_ratio"],
        m["short_sent_ratio"] <= t["short_sent_ratio_max"], "全是一口气断句，读起来在打拍子")
    add("p90_len", "句长 90 分位", f"≥{t['p90_len_min']}", m["p90_len"],
        m["p90_len"] >= t["p90_len_min"], "最长的句子也不长——右尾塌了")
    add("four_char_seg", "四字落点段占比", f"≤{t['four_char_seg_max']}", m["four_char_seg"],
        m["four_char_seg"] <= t["four_char_seg_max"], "满篇四字句，读三页就腻")
    add("connective_per_k", "连接词每千字", f"≥{t['connective_per_k_min']}", m["connective_per_k"],
        m["connective_per_k"] >= t["connective_per_k_min"], "因果没说明，读者自己补")
    add("metaphor_per_k", "比喻每千字", f"{t['metaphor_per_k_min']}—{t['metaphor_per_k_max']}",
        m["metaphor_per_k"],
        t["metaphor_per_k_min"] <= m["metaphor_per_k"] <= t["metaphor_per_k_max"],
        "零比喻干瘪／过密是修辞堆")
    add("paragraph_cv", "段长起伏", f"≥{t['paragraph_cv_min']}", m["para_cv"],
        m["para_cv"] >= t["paragraph_cv_min"], "段段一样长，版式平")
    return rows


def weak_signals(m: dict):
    """弱信号：四项里命中 ≥2 才提示（单项不判决——这些标记个体差异大）。"""
    hits = []
    if m["dash_per_k"] > 5.0:
        hits.append(f"破折号 {m['dash_per_k']}/千字 >5（人类散文约 3.2/千词）")
    if m["neg_parallel_per_k"] > 0.2:
        hits.append(f"「不是…而是」 {m['neg_parallel_per_k']}/千字 >0.2")
    if m["conj_pair_per_k"] > 1.0:
        hits.append(f"关联词完整式 {m['conj_pair_per_k']}/千字 >1.0")
    if m["short_sent_ratio"] > 0.30:
        hits.append(f"≤10 字短句 {m['short_sent_ratio']:.1%} >30%")
    return hits


# ---------- 基准 / 校准 ----------

def baseline_blocks(text: str):
    return [b for b in re.findall(r"```text\s*\n(.*?)```", text, re.S) if han_count(b) >= 500]


def baseline_check(root: Path, cfg: dict):
    """查文风基准填没填、靶值从哪来。exit 1 = 不许开写。"""
    print("\n=== 文风基准体检 ===")
    problems = []

    p = root / "00_底座_语文能力" / "文风基准.md"
    if not p.exists():
        problems.append("`00_底座_语文能力/文风基准.md` 不存在（新项目请用 开项目.py 铺模板）")
        text = ""
    else:
        text = p.read_text(encoding="utf-8")
        holes = PLACEHOLDER.findall(text)
        if holes:
            problems.append(f"文风基准还有 {len(holes)} 处 `<待填>` 没填")
        blocks = re.findall(r"```text\s*\n(.*?)```", text, re.S)
        ok_blocks = [han_count(b) for b in blocks if han_count(b) >= 500]
        if len(ok_blocks) < 3:
            problems.append(f"基准段落不足三段≥500 字（现 {len(ok_blocks)} 段：{[han_count(b) for b in blocks]}）")

    style = (cfg.get("style") or {})
    missing = [k for k in JUDGED if k not in style]
    if missing:
        problems.append("项目配置.json 缺 style 键：" + "、".join(missing))

    if problems:
        print("  未完成：")
        for x in problems:
            print(f"    - {x}")
        print("\n文风基准：未完成 —— 不许出第一章正文（这是 P0 门，不是建议）")
        return 1

    src = cfg.get("style_source") or ""
    print("  PASS  三段基准段落齐／无待填／判定项靶值齐")
    if not src:
        print("  NOTE  靶值是**默认值**，不是这本书的——跑 `文风靶.py --calibrate` 让基准段落自己产生靶值")
    else:
        print(f"  靶值来源：{src}")
    print("\n文风基准：可开写")
    return 0


def smell(m: dict):
    """一个基准段落的 AI 味判据，返回命中的理由列表。"""
    hits = []
    for key, op, th, fmt in BASELINE_SMELL:
        v = float(m.get(key, 0.0))
        if (op == "<" and v < th) or (op == ">" and v > th):
            hits.append(fmt.format(v=v))
    return hits


def calibrate(root: Path, force: bool = False) -> int:
    """量三段基准段落，把靶值写进 项目配置.json 的 style（并记 style_source）。

    基准段落是这本书的尺子：拿 AI 稿当尺，等于把「句短、均匀、四字多」写成合法区间。
    所以先查基准自己像不像 AI 稿——踩两项及以上就拒绝，除非 --force。
    """
    print("\n=== 文风靶 · 校准（靶值从基准段落反推） ===")
    p = root / "00_底座_语文能力" / "文风基准.md"
    if not p.exists():
        print("[停] 没有 `00_底座_语文能力/文风基准.md`")
        return 1
    text = p.read_text(encoding="utf-8")
    holes = PLACEHOLDER.findall(text)
    if holes:
        print(f"[停] 文风基准还有 {len(holes)} 处 `<待填>` 没填，先填完再校准")
        return 1
    blocks = baseline_blocks(text)
    if len(blocks) < 3:
        print(f"[停] 基准段落不足三段≥500 字（现 {len(blocks)} 段）")
        return 1

    ms = [measure(b) for b in blocks]
    avg = {k: statistics.fmean([m[k] for m in ms]) for k in ms[0]}

    # 基准自检：像 AI 稿就不许当尺（这是 1.37.1 加的防线）
    dirty = [(i + 1, smell(m)) for i, m in enumerate(ms)]
    dirty = [(i, h) for i, h in dirty if len(h) >= 2]
    if dirty:
        print("[停] 基准段落自己落在 AI 常用区间，不许拿它当尺：")
        for i, hits in dirty:
            print(f"    第 {i} 段：")
            for h in hits:
                print(f"      - {h}")
        print("\n    为什么拦：这三段会被 --calibrate 直接翻译成九项靶值。")
        print("    用 AI 稿当基准，等于把「句短、均匀、四字多」锁成这本书的合法区间，")
        print("    以后 `章体检` 就再也查不出这个问题——尺子被测量对象定义了。")
        print("    改法：换成人写的段落（已过读者关的成品、你自己手写、出版稿都行）。")
        if force:
            print("\n    （--force：按你的判断继续，style_source 会标 forced）")
        else:
            print("    如果确认这三段真是人写的，加 `--force` 再来一次。")
            return 1

    def clamp(v, lo, hi):
        return round(min(hi, max(lo, v)), 3)

    style = {
        # 锚点的 0.92 倍起步，但不低于 0.40（人类参考 0.449，AI 0.376）
        "sentence_cv_min": clamp(max(0.40, avg["sent_cv"] * 0.92), 0.40, 0.75),
        # 长句取锚点的 30%——锚点每 3 句 1 句长句，正文每 10 句 1 句是现实的起点
        "long_sent_ratio_min": clamp(avg["long_sent_ratio"] * 0.30, 0.06, 0.30),
        "short_sent_ratio_max": clamp(avg["short_sent_ratio"] * 2.0 + 0.05, 0.18, 0.38),
        "p90_len_min": clamp(max(24, avg["p90_len"] * 0.70), 24, 90),
        "four_char_seg_max": clamp(avg["four_char_seg"] * 1.5 + 0.02, 0.02, 0.20),
        "connective_per_k_min": clamp(avg["connective_per_k"] * 0.35, 0.6, 6.0),
        "metaphor_per_k_min": clamp(avg["metaphor_per_k"] * 0.40, 0.8, 6.0),
        "metaphor_per_k_max": clamp(avg["metaphor_per_k"] * 2.00, 4.0, 14.0),
        "paragraph_cv_min": clamp(max(0.40, avg["para_cv"] * 0.85), 0.40, 0.95),
        "mid_len_ratio_max": clamp(avg["mid_len_ratio"] * 1.15, 0.30, 0.65),
    }

    print(f"{'指标':<22}{'锚点实测':<12}{'反推靶值':<12}")
    for k, v in style.items():
        key = {"sentence_cv_min": "sent_cv", "long_sent_ratio_min": "long_sent_ratio",
               "short_sent_ratio_max": "short_sent_ratio", "p90_len_min": "p90_len",
               "four_char_seg_max": "four_char_seg",
               "connective_per_k_min": "connective_per_k",
               "metaphor_per_k_min": "metaphor_per_k", "metaphor_per_k_max": "metaphor_per_k",
               "paragraph_cv_min": "para_cv", "mid_len_ratio_max": "mid_len_ratio"}[k]
        print(f"{k:<22}{float(avg[key]):<12.3f}{float(v):<12.3f}")

    cfgp = root / "项目配置.json"
    cfg = load_cfg(root)
    cfg["style"] = style
    fp = (f"锚：句长 CV {avg['sent_cv']:.2f}／长句 {avg['long_sent_ratio']:.1%}／"
          f"短句 {avg['short_sent_ratio']:.1%}／四字 {avg['four_char_seg']:.1%}")
    src = "calibrated：由 00_底座_语文能力/文风基准.md §一 三段锚实测反推"
    cfg["style_source"] = (src + "（" + fp + "）" +
                           ("［forced：基准被判可能有 AI 味］" if force and dirty else ""))
    cfgp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n已写入 {cfgp.name}（style 十项 + style_source）")
    print("靶值现在来自这本书自己的锚——基准段落改了要重跑 --calibrate")
    return 0


# ---------- 砍词检测（把词吃成半个字） ----------

# 现代叙事里这些字几乎只出现在双音节词里。单独出现、且左右都不构成常见词，
# 就是被砍了（可以→可／现在→现／知道→知／觉得→觉）。只收这四个：其他虚词的单用\n#   在现代汉语里本来就合法（早已、但我不走、X 时），收进来只会误报。
# 只报数：读者能接受少量文言腔，机器不该替作者判死。硬例（后面直接跟"了着过的"或标点）
# 一定拦，软例攒够数才提示。
CLIP_CHARS = {
    "现": (set("在成如役款状实现下金货钱场象身"), set("表发出实呈体展显兑变涌浮闪再现")),
    "知": (set("道觉情名悉会足音遇己底识"), set("感认通告须无良深自相")),
    "觉": (set("得察醒着悟"), set("知错感发触视听自觉警察幻痛味睡梦")),
}

# 紧跟这些字跟在单字后面，双音节词就没写成：「知他」「觉我」「现这」。
CLIP_AFTER_BAD = set("了着过的地得，。！？…；：、他我你她它这那谁")


def solo_func(text: str):
    """返回 [(硬/软, 字, 上下文)]：疑似被砍成单字的词。"""
    hits = []
    for ch, (nxt_ok, prv_ok) in CLIP_CHARS.items():
        for m in re.finditer(ch, text):
            i = m.start()
            nxt = text[i + 1] if i + 1 < len(text) else ""
            prv = text[i - 1] if i > 0 else ""
            if nxt in nxt_ok or prv in prv_ok:
                continue
            ctx = text[max(0, i - 12):i + 13].replace("\n", "⏎")
            kind = "硬" if nxt in CLIP_AFTER_BAD else "软"
            hits.append((kind, ch, ctx))
    return hits


# ---------- 找文件 ----------

def resolve_chapter(arg: str, root: Path):
    p = Path(arg)
    if p.exists() and p.suffix == ".md":
        return p
    if p.suffix == ".md":
        hits = glob.glob(str(root / "04_正文_成品" / p.name))
        if hits:
            return Path(hits[0])
    m = re.fullmatch(r"\d{1,4}", arg or "")
    if m:
        num = int(m.group(0))
        for pat in (f"第{num:03d}章_*.md", f"第{num}章_*.md", f"*{num:03d}*.md"):
            hits = sorted(glob.glob(str(root / "04_正文_成品" / pat)))
            hits = [h for h in hits if "_候选" not in h and not re.search(r"_[AB]\.md$", h)]
            if hits:
                return Path(hits[0])
    return None


def recent_dialogue_baseline(root: Path, this_file: Path, n: int = 3, mode: str = "strict"):
    """本书最近 n 章（不含本章）的对白占比均值。只报数用。"""
    files = sorted(glob.glob(str(root / "04_正文_成品" / "第*章_*.md")))
    files = [f for f in files if "_候选" not in f and not re.search(r"_[AB]\.md$", f)
             and Path(f).resolve() != this_file.resolve()]
    vals = []
    for f in files[-n:]:
        body = strip_frontmatter(Path(f).read_text(encoding="utf-8"))
        m = measure(body, mode)
        if m["chars"]:
            vals.append(m["dialogue_ratio"])
    return vals


# ---------- 主流程 ----------

def main_report(chapter_arg, root: Path, strict: bool, tier: str = "T1",
                mode: str = "strict") -> int:
    cfg = load_cfg(root)
    f = resolve_chapter(chapter_arg, root)
    if f is None or not f.exists():
        print(f"[停] 找不到正文：{chapter_arg}（在 {root / '04_正文_成品'} 下没匹配到）")
        return 1
    body = strip_frontmatter(f.read_text(encoding="utf-8"))
    m = measure(body, mode)
    style = cfg.get("style") or {}

    print(f"\n=== 文风靶 · {f.name} ===")
    print(f"读数：{m['chars']} 字／{m['paras']} 段／{m['sents']} 句；"
          f"句长 mean {m['sent_mean']}（max {m['sent_max']}／p90 {m['p90_len']}）／"
          f"段长 mean {m['para_mean']}")
    if mode == "loose":
        print("  切句：loose（旧口径，`；` 与换行当句末——只为对照 1.36.0 数据）")

    rows = judge(m, style, tier)
    checks = 0
    print(f"\n{'判':<6}{'指标':<18}{'靶':<12}{'实测':<9}说明")
    for key, meaning, target, got, ok, note in rows:
        flag = "PASS" if ok else "CHECK"
        checks += (not ok)
        tail = "" if ok else f"  ← {note}"
        print(f"{flag:<6}{meaning:<18}{target:<12}{str(got):<9}{tail}")

    # 只报数
    print(f"\n报数（不进判定）：8—20 字句 {m['mid_len_ratio']:.3f}｜"
          f"抽象名词 {m['abstract_per_k']}/千字｜感官词 {m['sense_per_k']}/千字｜"
          f"段首他她 {m['head_pronoun']:.1%}")

    vals = recent_dialogue_baseline(root, f, mode=mode)
    if vals:
        avg = round(statistics.fmean(vals), 3)
        diff = round(m["dialogue_ratio"] - avg, 3)
        print(f"报数（不进判定）：对白占比 {m['dialogue_ratio']:.1%}"
              f"｜本书前 {len(vals)} 章均值 {avg:.1%}｜差 {diff:+.1%}")
        if avg > 0 and m["dialogue_ratio"] < avg * 0.5:
            print("  NOTE  对白掉到均值一半以下——对白只报数不设线（作者 2026-11-06 令），"
                  "但连掉三章要人看一眼")
    else:
        print(f"报数（不进判定）：对白占比 {m['dialogue_ratio']:.1%}（暂无前章可对比）")

    clip = solo_func(body)
    hard = [h for h in clip if h[0] == "硬"]
    per_k = len(clip) / max(m["chars"], 1) * 1000
    print(f"报数（不进判定）：疑似砍词 {len(clip)} 处（{per_k:.1f}/千字，硬例 {len(hard)}）")
    if hard or (len(clip) >= 3 and per_k >= 2.0):
        print("CHECK 疑似把词砍成字（可以→可、已经→已、现在→现、时候→时）——"
              "不是「简洁」，是缺字；能补回双音节的补回去（`02-正文口径.md` §十六）")
        for kind, ch, ctx in (hard or clip)[:5]:
            print(f"        {kind}「{ch}」…{ctx}…")
        checks += 1

    hits = weak_signals(m)
    if len(hits) >= 2:
        print("\n弱信号（≥2 项才提示，单项不判）：")
        for h in hits:
            print(f"  CHECK  {h}")
        checks += 1

    if checks == 0:
        print(f"\n文风靶：全部落靶（{len(rows)} 项，按 {tier}）——可以进停 3")
        return 0
    print(f"\n文风靶：{checks} 项 CHECK（按 {tier}）—— "
          + ("按 §C1 命中即改，改完重跑这一章" if strict else "报数项，先看是不是真的偏（--strict 才拦）"))
    return 1 if strict else 0


def selftest():
    import tempfile
    import shutil
    root = Path(tempfile.mkdtemp())
    (root / "04_正文_成品").mkdir(parents=True)
    (root / "00_底座_语文能力").mkdir(parents=True)
    style = {k: v for k, v in STYLE_KEYS}
    style["long_sent_ratio_min"] = 0.06   # 自检用 T0 级
    (root / "项目配置.json").write_text(
        json.dumps({"style": style}, ensure_ascii=False), encoding="utf-8")

    good = (
        "雨从檐口斜进来，打在门板上，把昨夜糊的那层纸泡成了软泥。他蹲下去摸了一把，指头陷进去半个，"
        "心里就有了数：这一块门板钉不住了，得换，换一块要两吊钱，而他现在只剩十一枚铜板，"
        "连半块都买不起，只好先把泡软的那层纸揭下来晾着，等天晴再说。\n"
        "“你倒是想个法子。”刘二靠在门框上，嘴里嚼着干饼，饼渣掉在门槛上，又用鞋底蹭开。\n"
        "他没回头，只把手按在门板上，那声音闷闷的，像有人隔着几层湿布在里头敲。"
        "雨声忽然大了一阵，街上的水已经漫过石阶，顺着门缝往里灌。\n"
        "于是他把袖子撸到胳膊肘，弯下腰，一捧一捧地往外淘。淘到第七捧，他停住了——"
        "水面上浮着一层灰，灰底下压着一枚铜板，崭新，边缘还没磨圆。\n"
        "他捡起来，对着光看了一会儿，又放回水里，看着它沉下去。\n"
        "雨小了。\n"
        "他没说话，只把那块泡软的纸揭下来，卷成一团塞进袖子，起身去后院翻那块备用的旧门板——"
        "翻到一半才想起来，那门板去年冬天就当柴烧了，剩下的只有一截楔子和两根弯钉。\n"
    )
    (root / "04_正文_成品" / "第001章_门板钉不住.md").write_text(good, encoding="utf-8")
    print("自检 A：有长句有起伏的一章 应 PASS")
    rcA = main_report("001", root, strict=True, tier="T0")

    bad = "他站起来。\n他推开门。\n雨落下来。\n他缩回手。\n门板湿了。\n他转身走。\n" * 6
    (root / "04_正文_成品" / "第002章_坏章.md").write_text(bad, encoding="utf-8")
    print("\n自检 B：等长短句一章 应 CHECK（strict 退出 1）")
    rcB = main_report("002", root, strict=True, tier="T1")

    # 校准：三段 600 字锚 → 应写出 style_source
    anchor = ("雨打在瓦上，声音先是稀，后来密，最后连成一片，像有人在屋顶上筛豆子。"
              "他坐在门槛上，把草鞋脱了，脚底板全是泥，泥里嵌着碎瓦片，"
              "他一片一片抠出来，抠到最后一处时，指头被划破了，血珠冒出来，他也没擦，就看着它被雨水冲淡。"
              "屋里没有点灯，只有灶膛里一点红，红光照着墙上挂的那把锯，锯条上的锈在光里像一层干了的血。") * 5
    blocks = []
    for _ in range(3):
        blocks.append("```text\n" + anchor[:1800] + "\n```\n")
    (root / "00_底座_语文能力" / "文风基准.md").write_text(
        "# 文风基准\n\n" + "\n".join(blocks), encoding="utf-8")
    print("\n自检 C：三段锚齐 应 calibrate 成功")
    rcC = calibrate(root)
    src = load_cfg(root).get("style_source") or ""
    print("\n自检 D：基准未填 应 exit 1")
    (root / "00_底座_语文能力" / "文风基准.md").write_text(
        "# 文风基准\n```text\n短\n```\n`<待填 0.45>`\n", encoding="utf-8")
    rcD = baseline_check(root, load_cfg(root))

    print("\n自检 E：基准是等长短句（AI 味）应拒绝校准 exit 1")
    flat = ("他站起来。他推开门。雨落下来。他缩回手。门板湿了。他转身走。\n") * 40
    eb = []
    for _ in range(3):
        eb.append("```text\n" + flat + "\n```\n")
    (root / "00_底座_语文能力" / "文风基准.md").write_text(
        "# 文风基准\n\n" + "\n".join(eb), encoding="utf-8")
    rcE = calibrate(root)
    print("\n自检 F：同一份 AI 味基准加 --force 应放行 exit 0")
    rcF = calibrate(root, force=True)

    print("\n自检 G：砍词检测（现在→现／知道→知／觉得→觉）")
    chopped = ("现他在屋里坐着，知这事的人不多。觉他说得对，"
               "觉他走的时候没回头，现外头雨还没停。")
    clip_chopped = solo_func(chopped)
    clip_good = solo_func(good)
    n_hard = len([h for h in clip_chopped if h[0] == "硬"])
    rcG = 0 if (len(clip_chopped) >= 3 and n_hard >= 1 and len(clip_good) == 0) else 1
    print(f"  正常章命中 {len(clip_good)} 处（应 0）；砍词章命中 {len(clip_chopped)} 处（硬 {n_hard}，应 ≥3／≥1）")

    shutil.rmtree(root, ignore_errors=True)
    ok = ((rcA == 0) and (rcB == 1) and (rcC == 0) and bool(src) and (rcD == 1)
          and (rcE == 1) and (rcF == 0) and (rcG == 0))
    print(f"\n自检结果：{'通过' if ok else '失败'}"
          f"（A {rcA} / B {rcB} / C {rcC} / 来源 {bool(src)} / D {rcD} / E {rcE} / F {rcF} / G {rcG}）")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="文风靶：把文风变成可测的数")
    ap.add_argument("chapter", nargs="?")
    ap.add_argument("--baseline", action="store_true", help="只查文风基准填没填、靶值从哪来")
    ap.add_argument("--calibrate", action="store_true", help="量基准段落，反推靶值写进项目配置")
    ap.add_argument("--force", action="store_true", help="校准前不拦「基准像 AI 稿」（慎用）")
    ap.add_argument("--tier", default="T1", choices=["T0", "T1", "T2"], help="档位（影响长句下限）")
    ap.add_argument("--strict", action="store_true", help="有 CHECK 就 exit 1")
    ap.add_argument("--split", default="strict", choices=["strict", "loose"], help="切句口径")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(selftest())

    root = find_root()
    if args.baseline:
        sys.exit(baseline_check(root, load_cfg(root)))
    if args.calibrate:
        sys.exit(calibrate(root, force=args.force))
    if not args.chapter:
        ap.print_help()
        sys.exit(1)
    sys.exit(main_report(args.chapter, root, args.strict, args.tier, args.split))


if __name__ == "__main__":
    main()
