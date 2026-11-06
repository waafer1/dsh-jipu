#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""设定一致性.py —— 正文有没有冒出设定卡以外的设定。

用法：
  python 设定一致性.py                  # 项目根下：设定卡 vs 全部正文
  python 设定一致性.py --file 第012章_*.md
  python 设定一致性.py --names          # 额外报“疑似未入卡专名”（较吵）
  python 设定一致性.py --selftest

判据：
  1. 禁忌：设定卡“禁忌”里逐条拆词，正文出现即 FAIL（这是硬门）。
  2. 金手指写“无”时，正文出现 系统/面板/属性栏/金手指 → WARN。
  3. 主角：从设定卡“主角”抽名字，正文一次没出现 → WARN。
  4. --names：正文高频 2—4 字词，不在设定卡/事实词典/数字登记里 → WARN（最多 10 条）。
退出码：0 通过（可带 WARN）；1 禁忌命中；--selftest 失败 1。
"""
import argparse
import collections
import glob
import io
import os
import re
import sys
import tempfile

STOP = set('''我们 他们 她们 你们 自己 什么 没有 一个 这个 那个 时候 知道 看见 起来 出来 进去
这里 那里 现在 已经 还是 就是 因为 所以 但是 如果 可以 不能 不是 这样 那样 一定 真的
东西 地方 事情 问题 办法 眼睛 手里 身上 心里 头里 嘴里 脚下 脸上 一边 一边 之后 之前
忽然 突然 慢慢 轻轻 终于 只是 还有 而且 然后 于是 虽然 不过 其实 应该 可能 觉得 认为
'''.split())


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
        if len(cells) >= 3:
            got[cells[1]] = cells[2]
    return got


def split_items(s):
    parts = re.split(r'[、，,；;/\s]+', s or '')
    out = []
    for p in parts:
        p = p.strip()
        p = re.sub(r'^(不许|禁止|不要|不可|不能|别|不得)', '', p)
        if len(p) >= 2:
            out.append(p)
    return out


def chapter_files(specs, root):
    if specs:
        return specs
    if root:
        return sorted(glob.glob(os.path.join(root, '04_正文_成品', '第*章_*.md')))
    return []


def check(root, files, names=False):
    card_path = os.path.join(root, '02_设定_世界与角色', '设定卡.md') if root else None
    card = parse_card(read(card_path)) if card_path else {}
    if not card:
        print('[停] 读不到设定卡：02_设定_世界与角色/设定卡.md')
        return 1
    body = '\n'.join(read(f) for f in files)
    hard = 0

    taboos = split_items(card.get('禁忌', ''))
    hit = [t for t in taboos if t in body]
    if hit:
        hard = 1
        print('FAIL 禁忌命中：' + '、'.join(hit))
    else:
        print(f'PASS 禁忌：{len(taboos)} 条，未出现')

    gold = card.get('金手指', '')
    if gold.strip() in ('无', '没有', '无金手指', '—'):
        bad = [w for w in ('系统', '面板', '属性栏', '金手指', '任务栏') if w in body]
        if bad:
            print('WARN 金手指写“无”，正文出现：' + '、'.join(bad))
        else:
            print('PASS 金手指：写“无”，正文无系统类词')

    hero = card.get('主角', '')
    cand = [w for w in re.findall(r'[\u4e00-\u9fa5]{2,4}', hero) if w not in STOP]
    if cand:
        found = [c for c in cand if c in body]
        if not found:
            print(f'WARN 主角名未在正文出现（卡上：{cand[:3]}）')
        else:
            print(f'PASS 主角：{found[0]}')

    if names:
        corpus = body + read(card_path)
        for f in ('事实词典.md', '数字登记.md'):
            corpus += read(os.path.join(root, '06_追踪_状态账本', f))
        cnt = collections.Counter(re.findall(r'[\u4e00-\u9fa5]{2,4}', body))
        sus = []
        for w, n in cnt.most_common(300):
            if n >= 8 and w not in STOP and w not in corpus:
                sus.append(f'{w}×{n}')
            if len(sus) >= 10:
                break
        print('WARN 疑似未入卡专名：' + ('、'.join(sus) if sus else '无'))

    print('\n结论：' + ('FAIL（禁忌命中）' if hard else 'PASS'))
    return hard


def selftest():
    d = tempfile.mkdtemp(prefix='jipu-cons-')
    os.makedirs(os.path.join(d, '02_设定_世界与角色'))
    os.makedirs(os.path.join(d, '04_正文_成品'))
    card = '''# 设定卡
| # | 字段 | 内容 |
|---|---|---|
| 1 | 书名 | 测试 |
| 2 | 类目 | 都市异能 |
| 3 | 频道/读者 | 男生 |
| 4 | 主角 | 陈九 |
| 5 | 金手指 | 无 |
| 6 | 对手 | 债主 |
| 7 | 本卷目标 | 还钱 |
| 8 | 代价 | 折寿 |
| 9 | 世界铁律 | 借钱要还 |
| 10 | 禁忌 | 系统面板、异能等级表 |
| 11 | 母题 | 能力即负债 |
| 12 | 结局方向 | 未定 |
'''
    io.open(os.path.join(d, '02_设定_世界与角色', '设定卡.md'), 'w', encoding='utf-8').write(card)
    good = os.path.join(d, '04_正文_成品', '第001章_借钱.md')
    io.open(good, 'w', encoding='utf-8').write('陈九借了钱，债主上门。他低头认账。\n')
    rc_ok = check(d, [good], False)
    io.open(good, 'w', encoding='utf-8').write('陈九眼前浮起系统面板，属性栏写着等级。\n')
    rc_bad = check(d, [good], False)
    import shutil
    shutil.rmtree(d, ignore_errors=True)
    ok = rc_ok == 0 and rc_bad == 1
    print(f'\n自检：{"通过" if ok else "失败"}（干净 {rc_ok}／禁忌 {rc_bad}）')
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description='设定一致性检查')
    ap.add_argument('--file', action='append', default=[])
    ap.add_argument('--names', action='store_true')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()

    if a.selftest:
        sys.exit(selftest())
    root = find_root()
    if not root:
        print('[停] 找不到项目根（需要 项目配置.json）')
        sys.exit(1)
    files = chapter_files(a.file, root)
    if not files:
        print('[停] 没有正文')
        sys.exit(1)
    sys.exit(check(root, files, a.names))


if __name__ == '__main__':
    main()
