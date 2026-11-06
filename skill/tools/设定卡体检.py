#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""设定卡体检.py —— 12 行设定卡缺行即停（缺一行不许动笔）。

用法：
  python 设定卡体检.py                 # 体检当前项目（向上找 项目配置.json）
  python 设定卡体检.py --file 设定卡.md
  python 设定卡体检.py --init          # 在 02_设定_世界与角色/ 下生成空白卡
  python 设定卡体检.py --selftest

口径：
  - 卡的位置：`02_设定_世界与角色/设定卡.md`（--file 可指定）。
  - 卡是一张 12 行表：| # | 字段 | 内容 |；字段名固定（见 FIELDS）。
  - 缺行、内容为空、类目不在 12 类目内 → FAIL（exit 1）。
  - 「结局方向」允许写“未定”，但会给 WARN。
退出码：0 全齐；1 缺行/不合法；--selftest 失败 1。
"""
import argparse
import io
import os
import sys
import tempfile

FIELDS = [
    ('书名', ('书名', '暂定名')),
    ('类目', ('类目', '分类')),
    ('频道/读者', ('频道/读者', '频道', '读者')),
    ('主角', ('主角',)),
    ('金手指', ('金手指', '能力')),
    ('对手', ('对手',)),
    ('本卷目标', ('本卷目标', '目标')),
    ('代价', ('代价',)),
    ('世界铁律', ('世界铁律', '世界')),
    ('禁忌', ('禁忌', '不许出现')),
    ('母题', ('母题',)),
    ('结局方向', ('结局方向', '结局')),
]
GENRES = ['东方玄幻', '西方玄幻', '仙侠修真', '都市异能', '都市日常与职场',
          '历史架空', '科幻末世', '星际机甲', '悬疑灵异', '游戏竞技与无限流',
          '女频古言', '女频现言']

TEMPLATE = '''# 设定卡（12 行，缺一行不许动笔）

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
| 8 | 代价 |  |
| 9 | 世界铁律 |  |
| 10 | 禁忌 |  |
| 11 | 母题 |  |
| 12 | 结局方向 |  |
'''


def find_root(start=None):
    d = os.path.abspath(start or os.getcwd())
    for _ in range(8):
        if os.path.isfile(os.path.join(d, '项目配置.json')):
            return d
        nd = os.path.dirname(d)
        if nd == d:
            break
        d = nd
    return None


def read(p):
    try:
        return io.open(p, encoding='utf-8').read()
    except FileNotFoundError:
        return ''


def parse_card(text):
    got = {}
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith('|'):
            continue
        cells = [c.strip() for c in s.strip('|').split('|')]
        if len(cells) < 3:
            continue
        field = cells[1]
        content = cells[2] if len(cells) > 2 else ''
        for canon, aliases in FIELDS:
            if field in aliases:
                got[canon] = content
                break
    return got


def check(path):
    text = read(path)
    if not text.strip():
        print(f'[停] 读不到设定卡：{path}')
        print('先跑 --init 生成模板，或把卡放到 02_设定_世界与角色/设定卡.md')
        return 1
    got = parse_card(text)
    problems = []
    warns = []
    for canon, _ in FIELDS:
        val = got.get(canon, '').strip()
        status = 'OK' if val else 'MISSING'
        if not val:
            problems.append(canon)
        print(f'{status:8} {canon}: {val[:40]}')

    genre = got.get('类目', '').strip()
    if genre and not any(g in genre for g in GENRES):
        problems.append(f'类目不在 12 类目内：{genre}')

    taboo = got.get('禁忌', '').strip()
    if taboo in ('', '无', '没有', '暂无'):
        problems.append('禁忌（至少写 1 条，建议 5 条）')

    ending = got.get('结局方向', '').strip()
    if ending in ('未定', '待定'):
        warns.append('结局方向未定（上架前必须回填）')

    for w in warns:
        print('WARN   ', w)
    if problems:
        print('\nFAIL：缺 ' + str(len(problems)) + ' 项 —— ' + '、'.join(problems))
        print('卡不齐，不许进下一步（问设定 → 建检索 → 糅合 → 风格填充）。')
        return 1
    print('\nPASS：12 行齐，可以进下一步。')
    return 0


def selftest():
    root = tempfile.mkdtemp(prefix='jipu-card-')
    io.open(os.path.join(root, '项目配置.json'), 'w', encoding='utf-8').write('{"title":"t"}')
    os.makedirs(os.path.join(root, '02_设定_世界与角色'))
    card = os.path.join(root, '02_设定_世界与角色', '设定卡.md')
    full = TEMPLATE
    fills = {
        '书名': '测试书', '类目': '东方玄幻', '频道/读者': '男生｜想翻身的短工',
        '主角': '一个替人试丹的学徒', '金手指': '能听见丹方里的杂音，代价是折寿',
        '对手': '丹房执事', '本卷目标': '拿到一张自己的丹方',
        '代价': '每听一次少一年寿', '世界铁律': '丹方归宗门，私方是死罪',
        '禁忌': '不许出现系统面板', '母题': '力气从哪来', '结局方向': '未定',
    }
    for k, v in fills.items():
        full = full.replace(f'| {k} |  |', f'| {k} | {v} |')
    io.open(card, 'w', encoding='utf-8').write(full)
    rc_ok = check(card)

    missing = full.replace('| 金手指 | 能听见丹方里的杂音，代价是折寿 |', '| 金手指 |  |')
    io.open(card, 'w', encoding='utf-8').write(missing)
    rc_bad = check(card)

    bad_genre = full.replace('| 类目 | 东方玄幻 |', '| 类目 | 太空歌剧 |')
    io.open(card, 'w', encoding='utf-8').write(bad_genre)
    rc_genre = check(card)

    import shutil
    shutil.rmtree(root, ignore_errors=True)
    ok = rc_ok == 0 and rc_bad == 1 and rc_genre == 1
    print(f'\n自检：{"通过" if ok else "失败"}（齐 {rc_ok}／缺项 {rc_bad}／错类目 {rc_genre}）')
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description='12 行设定卡体检')
    ap.add_argument('--file')
    ap.add_argument('--init', action='store_true')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()

    if a.selftest:
        sys.exit(selftest())

    root = find_root()
    if a.init:
        if not root:
            print('[停] 找不到项目根（需要 项目配置.json）；先跑 开项目.py')
            sys.exit(1)
        d = os.path.join(root, '02_设定_世界与角色')
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, '设定卡.md')
        if os.path.exists(p):
            print(f'[有] {p} 已存在，不覆盖')
            sys.exit(0)
        io.open(p, 'w', encoding='utf-8', newline='\n').write(TEMPLATE)
        print(f'[建] {p}')
        sys.exit(0)

    path = a.file or (os.path.join(root, '02_设定_世界与角色', '设定卡.md') if root else None)
    if not path:
        print('[停] 找不到项目根，也没有 --file')
        sys.exit(1)
    sys.exit(check(path))


if __name__ == '__main__':
    main()
