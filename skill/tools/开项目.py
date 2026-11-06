# -*- coding: utf-8 -*-
"""
开项目.py —— 一键铺一个新书项目（计谱 1.2.2 收编进包）

做什么：
  1. 建九层目录（空项目结构）
  2. 复制底座：assets 里的库与通用件 → 00_底座 / 07_模板_复用件
  3. 复制工具：本目录 tools/*.py → 08_工具_脚本/
  4. 生成起始文件：项目配置.json、_tracking-state.json、00-索引.md、题材定位.md 骨架、五份派生视图空壳

它不做：不复制任何一本书的 canon／角色／正文／审计——那些是新书自己的资产。
目标目录已存在直接退出，不覆盖。

用法：
    python 开项目.py 书名
    python 开项目.py 书名 --root <你的作品目录>
    python 开项目.py --selftest
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

LAYERS = [
    "00_底座_语文能力",
    "01_法则_章法节奏爽点",
    "02_设定_世界与角色",
    "03_图纸_大纲与细纲",
    "04_正文_成品",
    "05_质检_审计评审节奏",
    "06_追踪_状态账本",
    "07_模板_复用件",
    "08_工具_脚本",
]
SUBDIRS = [
    "02_设定_世界与角色/canon",
    "02_设定_世界与角色/角色",
    "02_设定_世界与角色/素材",
    "05_质检_审计评审节奏/审计",
    "05_质检_审计评审节奏/节奏",
    "05_质检_审计评审节奏/评审",
]

# assets 里哪些去底座、哪些去模板库
BASE_FILES = ["画面例句库.md", "剧情拆解库.md", "表情图.md", "表现方法学习册.md"]
TPL_FILES = ["00-引导式选型.md"]
TPL_DIRS = ["类目模板库", "剧情模板库", "类目桥段库", "结构层库", "人物层库", "素材层库", "对白层库"]

DEFAULT_CONFIG = {
    "book": {"title": "", "genre": "", "style_ruler": "通俗直给", "target_words": 0},
    "gate": {
        "sentence_blocking_max": 0,
        "dialogue_ratio_min": 0.0,
        "dialogue_ratio_max": 1.0,
        "paragraph_head_pronoun_max": 0.20,
        "longest_narration_max": 600,
        "long_sentence_chars": 60,
    },
    "lexicon": {"banned_words": [], "proper_names": [], "appellations": {}},
    "hook": {"baseline": "high"},
    "coolpoint": {"density": "high"},
    "pacing": {"slow_streak_max": 3},
}

STATE_SKELETON = {
    "state_revision": 0,
    "last_committed_chapter": 0,
    "committed_at": "",
    "commit_note": "",
    "threads": [],
    "foreshadows": [],
    "characters": {},
    "facts": {"prices_used": [], "rules_established": [], "goods": [], "chapter_numbers": {}},
    "beats": [],
}

CARD_SKELETON = """# 题材定位 · 选型卡

> 12 行填满才允许写第一章。填不满就回去问，不许留空当默认。
> 判据：`07_模板_复用件/00-引导式选型.md`

| # | 项 | 填什么 |
|---|---|---|
| 1 | 类目 | |
| 2 | 读者点开看什么（一句话） | |
| 3 | 主角开局处境 | |
| 4 | 他要的具体东西 | |
| 5 | 谁挡着他 | |
| 6 | 金手指／核心手段 | |
| 7 | 代价（能计量的） | |
| 8 | 这一卷要拿到什么 | |
| 9 | 读者画像 | |
| 10 | 不许出现什么（逐条当硬门） | |
| 11 | 文风尺 | |
| 12 | 章节节奏预期（快／中／慢） | |
"""

SETTING_CARD = """# 设定卡（12 行，缺一行不许动笔）

> 作者填。计谱只问不猜；填完跑 `python 08_工具_脚本/设定卡体检.py`。

| # | 字段 | 内容 |
|---|---|---|
| 1 | 书名 |  |
| 2 | 类目 |  |
| 3 | 频道/读者 |  |
| 4 | 主角 |  |
| 5 | 金手指 |  |
| 6 | 对手 |  |
| 7 | 本卷目标 |  |
| 8 | 代价（可选） |  |
| 9 | 世界铁律 |  |
| 10 | 禁忌 |  |
| 11 | 母题 |  |
| 12 | 结局方向 |  |
"""

DRAW_SHEET = """# 取材单（第001段）

> 检索完必须填；单没填完不许进糅合。模板见 `07_模板_复用件/取材单模板.md`。

| # | 用途 | 来源库 | 编号 | 取的是什么 | 用在拍/章 | 冷却检查 | 备注 |
|---|---|---|---|---|---|---|---|
| 1 |  |  |  |  |  |  |  |
| 2 |  |  |  |  |  |  |  |
| 3 |  |  |  |  |  |  |  |
"""

VIEWS = {
    "上下文.md": "# 上下文（派生视图，勿手改）\n\n> 由 `08_工具_脚本/召回.py` 重渲染。\n",
    "事实词典.md": "# 事实词典（派生视图，勿手改）\n",
    "伏笔.md": "# 伏笔账（派生视图，勿手改）\n",
    "数字登记.md": "# 数字登记（派生视图，勿手改）\n\n| 数字 | 单位 | 出处章 | 含义 |\n|---|---|---|---|\n",
    "桥段账本.md": "# 桥段账本（派生视图，勿手改）\n\n| 模板号 | 章 | 变体 | 冷却到 |\n|---|---|---|---|\n",
}


def skill_root() -> Path:
    return Path(__file__).resolve().parent.parent


def scaffold(target: Path, title: str) -> dict:
    report = {"dirs": 0, "base": [], "tpl": [], "tools": 0, "missing": []}
    target.mkdir(parents=True)
    for d in LAYERS + SUBDIRS:
        (target / d).mkdir(parents=True, exist_ok=True)
        report["dirs"] += 1

    root = skill_root()
    assets = root / "assets"

    for name in BASE_FILES:
        src = assets / name
        if src.exists():
            shutil.copy2(src, target / "00_底座_语文能力" / name)
            report["base"].append(name)
        else:
            report["missing"].append(f"assets/{name}")

    for name in TPL_FILES:
        src = assets / name
        if src.exists():
            shutil.copy2(src, target / "07_模板_复用件" / name)
            report["tpl"].append(name)
        else:
            report["missing"].append(f"assets/{name}")

    for name in TPL_DIRS:
        src = assets / name
        if src.is_dir():
            shutil.copytree(src, target / "07_模板_复用件" / name, dirs_exist_ok=True)
            report["tpl"].append(name + "/")
        else:
            report["missing"].append(f"assets/{name}")

    tools_dir = root / "tools"
    if tools_dir.is_dir():
        for py in sorted(tools_dir.glob("*.py")):
            shutil.copy2(py, target / "08_工具_脚本" / py.name)
            report["tools"] += 1

    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    cfg["book"]["title"] = title
    (target / "项目配置.json").write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (target / "06_追踪_状态账本" / "_tracking-state.json").write_text(
        json.dumps(STATE_SKELETON, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for name, body in VIEWS.items():
        (target / "06_追踪_状态账本" / name).write_text(body, encoding="utf-8")
    (target / "02_设定_世界与角色" / "题材定位.md").write_text(CARD_SKELETON, encoding="utf-8")
    (target / "02_设定_世界与角色" / "设定卡.md").write_text(SETTING_CARD, encoding="utf-8")
    sheet = assets / "取材单模板.md"
    if sheet.exists():
        body = sheet.read_text(encoding="utf-8").replace("第NNN段", "第001段")
    else:
        body = DRAW_SHEET
    (target / "03_图纸_大纲与细纲" / "取材单_第001段.md").write_text(body, encoding="utf-8")
    (target / "00-索引.md").write_text(
        f"# {title}\n\n> 进度只看 `06_追踪_状态账本/_tracking-state.json`，本文件不作数。\n\n"
        "## 现在该做什么\n\n- [ ] 填 `02_设定_世界与角色/题材定位.md` 的 12 行选型卡\n"
        "- [ ] 建 1 张主角 A 卡（`07_模板_复用件/人物层库/01-人物卡预设.md`）\n"
        "- [ ] 出第一卷卷纲与前 15 章章纲\n",
        encoding="utf-8",
    )
    return report


def card_done(target: Path) -> bool:
    p = target / "02_设定_世界与角色" / "设定卡.md"
    if not p.exists():
        return False
    n = 0
    for line in p.read_text(encoding="utf-8").split("\n"):
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and cells[1] != "字段" and cells[2] and not set(cells[2]) <= set("-: "):
            n += 1
    return n >= 11


def check_nine(target: Path) -> list:
    """九环节自检：缺哪一环报哪一环。"""
    checks = [
        ("选型卡填满", len([l for l in (target / "02_设定_世界与角色" / "题材定位.md")
                            .read_text(encoding="utf-8").split("\n") if l.count("|") >= 3 and l.strip().endswith("|")
                            and l.split("|")[-2].strip()]) >= 12),
        ("设定卡 12 行齐", card_done(target)),
        ("主角 A 卡", any((target / "02_设定_世界与角色" / "角色").glob("*.md"))),
        ("卷纲", any((target / "03_图纸_大纲与细纲").glob("卷纲*"))),
        ("章纲", any((target / "03_图纸_大纲与细纲").glob("章纲*"))),
        ("人物层库", (target / "07_模板_复用件" / "人物层库").is_dir()),
        ("桥段账本", (target / "06_追踪_状态账本" / "桥段账本.md").exists()),
        ("素材底座", any((target / "02_设定_世界与角色" / "素材").glob("*.md"))),
        ("工具齐", len(list((target / "08_工具_脚本").glob("*.py"))) >= 8),
        ("状态账本", (target / "06_追踪_状态账本" / "_tracking-state.json").exists()),
    ]
    return checks


def selftest():
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    tgt = tmp / "自检书"
    rep = scaffold(tgt, "自检书")
    print("自检：目录", rep["dirs"], "／底座", len(rep["base"]), "／模板库", len(rep["tpl"]), "／工具", rep["tools"])
    if rep["missing"]:
        print("  缺件：", rep["missing"])
    checks = check_nine(tgt)
    for name, ok in checks:
        print(f"  {'OK ' if ok else 'MISS'} {name}")
    # 二次运行必须拒绝覆盖
    try:
        scaffold(tgt, "自检书")
        print("  失败：已存在目录竟然没被拒绝")
    except FileExistsError:
        print("  OK  已存在目录被拒绝（不覆盖）")
    shutil.rmtree(tmp)
    return 0


def main():
    ap = argparse.ArgumentParser(description="铺一个新书项目")
    ap.add_argument("title", nargs="?", help="书名")
    ap.add_argument("--root", default=".", help="父目录（默认当前目录）")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(selftest())
    if not args.title:
        ap.print_help()
        sys.exit(1)

    target = Path(args.root).resolve() / args.title
    if target.exists():
        print(f"[停] 目标已存在，不覆盖：{target}")
        sys.exit(1)

    rep = scaffold(target, args.title)
    print(f"建好：{target}")
    print(f"  目录 {rep['dirs']} ／底座 {len(rep['base'])} ／模板库 {len(rep['tpl'])} ／工具 {rep['tools']}")
    if rep["missing"]:
        print(f"  [缺] {rep['missing']}")
    print("\n九环节自检：")
    done = 0
    for name, ok in check_nine(target):
        print(f"  {'[x]' if ok else '[ ]'} {name}")
        done += ok
    print(f"  {done}/9 —— 后四项随写作自然补齐，前三项（选型卡／A 卡／卷纲）没齐不许写第一章。")
    print("自检结果：通过（脚手架可建、不覆盖已有目录、九环节可读）")


if __name__ == "__main__":
    main()
