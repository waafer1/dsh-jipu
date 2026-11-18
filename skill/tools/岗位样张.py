# -*- coding: utf-8 -*-
"""岗位样张.py —— 把拆书产物（章级玩法卡）摆成岗位能对照的形状。

为什么单独一个脚本：拆书出的是「章级零件」（一章一张玩法卡），岗位要的是「样张」——
卷纲岗要回合表（第几章兑现、什么型、隔几章），细纲岗要九行样本，审计岗要兑现分布。
零件再多，不摆成岗位能对照的形状，那几个岗位照样是空的。

用法：
    python 岗位样张.py --cards _书库/某书_新卡.json --out _书库/某书/岗位样张
    python 岗位样张.py --cards x.json --window 5 --volume 30
    python 岗位样张.py --selftest

输入：拆书产生的 JSON（{"cards": [{"名","类目","兑现物","源":"第N章"}, ...]}）
输出三个文件：
    兑现表.md    章｜类目｜玩法｜兑现物（逐章，一行一章）
    回合表.md    回合｜卷｜章段｜兑现章｜兑现类型｜玩法（给卷纲岗对照）
    样张报告.md  回合长度、兑现间隔、类目分布（给审计岗当尺子）

退出码：0 正常；1 读不到卡／没有可用章号。
"""

import argparse
import io
import json
import os
import re
import sys
from collections import Counter

# 一回合的收口：这几种玩法本身带着"兑现"（拿到／打脸／揭穿／突破）
SEG_END = ('资源与争夺', '打脸与立威', '揭秘与反转', '成长与突破')
# 一回合的开头：这几种是"压上去"
SEG_OPEN = ('压力与危机', '开局与入局')


def chapter_of(card):
    """从「源」里取章号：'第12章' / '兽血沸腾·第012章' 都吃。"""
    m = re.search(r'第\s*(\d+)\s*章', str(card.get('源') or ''))
    return int(m.group(1)) if m else None


def norm(cards):
    """章号 → 卡列表（同名章只留第一张，重复的记数）。"""
    by_ch, dup = {}, 0
    for c in cards:
        ch = chapter_of(c)
        if ch is None:
            continue
        if ch in by_ch:
            dup += 1
            continue
        by_ch[ch] = c
    return by_ch, dup


def segment(by_ch, window=5):
    """把逐章玩法切成回合。

    规则（可调）：章节按序进回合；回合在「兑现型玩法」处收口，且不得短于 3 章；
    到 window 章还没兑现，就硬切并标「无兑现」——这就是要标出来的毛病。
    """
    rows, cur = [], []
    for ch in sorted(by_ch):
        cur.append(ch)
        cat = by_ch[ch].get('类目', '')
        hit = cat in SEG_END
        if (hit and len(cur) >= 3) or len(cur) >= window:
            rows.append(make_row(cur, by_ch, hit))
            cur = []
    if cur:
        rows.append(make_row(cur, by_ch, False))
    return rows


def make_row(cur, by_ch, hit):
    first, last = cur[0], cur[-1]
    cats = [by_ch[c].get('类目', '') for c in cur]
    names = [by_ch[c].get('名', '') for c in cur]
    end_cat = by_ch[last].get('类目', '') if hit else ''
    return {
        '章段': (first, last),
        '长度': len(cur),
        '兑现章': last if hit else None,
        '兑现类型': end_cat if hit else '（无兑现）',
        '玩法': '；'.join(names),
        '兑现物': (by_ch[last].get('兑现物', '') if hit else ''),
        '压': sum(1 for c in cats if c in SEG_OPEN),
    }


def render(rows, by_ch, volume=30, title=''):
    out = []
    out.append('# 回合表（拆书样张）\n')
    out.append('> 从章级玩法卡切出来的回合，不是作者原卷纲，只当**对照样本**用：看别人怎么排「压—兑现」，'
               '看兑现隔几章。不可照抄剧情，抄了会撞 20 字线。\n')
    out.append('| 回合 | 卷 | 章段 | 长度 | 兑现章 | 兑现类型 | 玩法 |')
    out.append('|---|---|---|---|---|---|---|')
    for i, r in enumerate(rows, 1):
        a, b = r['章段']
        vol = (a - 1) // volume + 1
        seg = f'{a}—{b}' if b > a else str(a)
        end = f'第{r["兑现章"]}章' if r['兑现章'] else '—'
        names = r['玩法']
        if len(names) > 60:
            names = names[:58] + '…'
        names = names.replace('|', '／')
        out.append(f'| {i} | {vol} | {seg} | {r["长度"]} | {end} | {r["兑现类型"]} | {names} |')
    out.append('')
    return '\n'.join(out)


def render_goods(by_ch):
    out = ['# 兑现表（拆书样张）\n',
           '> 逐章一行：这一章读者拿到了什么。审计岗拿它当尺子——自己在写的书，隔几章兑现一次，对照着看。\n',
           '| 章 | 类目 | 玩法 | 兑现物 |', '|---|---|---|---|']
    for ch in sorted(by_ch):
        c = by_ch[ch]
        goods = str(c.get('兑现物') or '').replace('\n', ' ').replace('|', '／')
        if len(goods) > 70:
            goods = goods[:68] + '…'
        out.append(f'| {ch} | {c.get("类目","")} | {str(c.get("名","")).replace("|","／")} | {goods} |')
    out.append('')
    return '\n'.join(out)


def render_report(rows, by_ch, dup):
    lens = [r['长度'] for r in rows]
    ends = [r['兑现章'] for r in rows if r['兑现章']]
    gaps = [b - a for a, b in zip(ends, ends[1:])]
    cats = Counter(c.get('类目', '') for c in by_ch.values())
    no_end = sum(1 for r in rows if not r['兑现章'])
    out = ['# 样张报告（拆书）\n',
           f'- 章数：{len(by_ch)}｜回合数：{len(rows)}｜同名章丢弃：{dup}',
           f'- 回合长度：平均 {sum(lens)/max(len(lens),1):.1f} 章，最短 {min(lens)}，最长 {max(lens)}',
           f'- 兑现回合：{len(ends)}｜无兑现回合：{no_end}',
           f'- 兑现间隔：平均 {sum(gaps)/max(len(gaps),1):.1f} 章，最长 {max(gaps) if gaps else 0} 章',
           '', '## 类目分布', '', '| 类目 | 章数 | 占比 |', '|---|---|---|']
    total = max(sum(cats.values()), 1)
    for k, v in cats.most_common():
        out.append(f'| {k or "（空）"} | {v} | {v/total:.1%} |')
    out.append('')
    return '\n'.join(out)


def write_all(by_ch, dup, outdir, window=5, volume=30):
    rows = segment(by_ch, window)
    os.makedirs(outdir, exist_ok=True)
    parts = {
        '兑现表.md': render_goods(by_ch),
        '回合表.md': render(rows, by_ch, volume),
        '样张报告.md': render_report(rows, by_ch, dup),
    }
    for name, text in parts.items():
        io.open(os.path.join(outdir, name), 'w', encoding='utf-8').write(text)
    return rows, list(parts)


def selftest():
    cards = []
    # 回合 1：压 1、2 → 兑现 3（资源）；回合 2：压 4、5 → 兑现 6（打脸）；回合 3：4 章无兑现，硬切
    plan = [(1, '压力与危机'), (2, '审视与试探' if False else '揭秘与反转'), (3, '资源与争夺'),
            (4, '压力与危机'), (5, '压力与危机'), (6, '打脸与立威'),
            (7, '组织与人心'), (8, '组织与人心'), (9, '组织与人心'), (10, '组织与人心')]
    for ch, cat in plan:
        cards.append({'名': f'玩法{ch}', '类目': cat, '兑现物': f'物{ch}', '源': f'第{ch}章'})
    by_ch, dup = norm(cards)
    rows = segment(by_ch, window=5)
    lens = [r['长度'] for r in rows]
    ok = (len(rows) == 3
          and lens == [3, 3, 4]
          and rows[0]['兑现章'] == 3 and rows[1]['兑现类型'] == '打脸与立威'
          and rows[2]['兑现章'] is None)
    print('回合：', [(r['章段'], r['长度'], r['兑现类型']) for r in rows])
    print('自检：' + ('通过' if ok else '失败'))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description='拆书产物 → 岗位样张（兑现表／回合表／报告）')
    ap.add_argument('--cards', help='拆书产生的 JSON')
    ap.add_argument('--out', help='输出目录（默认与 JSON 同级 /岗位样张）')
    ap.add_argument('--window', type=int, default=5, help='回合最长章数（默认 5）')
    ap.add_argument('--volume', type=int, default=30, help='一卷多少章（默认 30）')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    if not a.cards:
        print('[停] 要给 --cards')
        sys.exit(1)
    if not os.path.exists(a.cards):
        print(f'[停] 读不到 {a.cards}')
        sys.exit(1)
    data = json.load(io.open(a.cards, encoding='utf-8'))
    cards = data.get('cards') if isinstance(data, dict) else data
    by_ch, dup = norm(cards or [])
    if not by_ch:
        print('[停] 没有可用章号（「源」里要有「第N章」）')
        sys.exit(1)
    outdir = a.out or os.path.join(os.path.dirname(os.path.abspath(a.cards)), '岗位样张')
    rows, files = write_all(by_ch, dup, outdir, a.window, a.volume)
    print(f'章 {len(by_ch)}｜回合 {len(rows)}｜输出 {outdir}')
    for f in files:
        print('  -', f)


if __name__ == '__main__':
    main()
