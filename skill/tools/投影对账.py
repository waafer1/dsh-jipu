#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""投影对账.py —— 一次提交派生出五份视图，对一遍：哪一路没同步。

状态体检.py 只判「五份视图文件在不在、比 state 新不新」；
本工具判内容：state 里该投到视图上的东西，视图里到底有没有。

用法：
  python 投影对账.py                 # 对当前项目
  python 投影对账.py --write         # 另把日志写到 05_质检_审计评审节奏/审计/投影日志_章NNN.md
  python 投影对账.py --selftest

口径（只核「一定能投过去」的东西，避免误报）：
  上下文.md   ← 进度段里要出现「第 00N 章」（N＝last_committed_chapter）
  事实词典.md ← characters 的每个人名都要在专名表里
  伏笔.md     ← foreshadows 每条 summary 前 8 字
  数字登记.md ← facts.prices_used 每条里的数字；文件不在＝这份视图没渲染
  桥段记录.md ← 不核内容（state 无 Q 号来源），只报行数提醒手看

退出码：0 全对；1 有缺；--selftest 失败 1。
"""
import argparse
import io
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime

STATE_DIRS = ['06_追踪_状态记录', '06_追踪_状态账本']
VIEWS = ['上下文.md', '事实词典.md', '伏笔.md', '数字登记.md', '桥段记录.md']
ALIAS = {'桥段记录.md': ['桥段记录.md', '桥段账本.md']}


def find_root(start=None):
    d = os.path.abspath(start or os.getcwd())
    for _ in range(8):
        for sub in STATE_DIRS:
            if os.path.isfile(os.path.join(d, sub, '_tracking-state.json')):
                return d
        nd = os.path.dirname(d)
        if nd == d:
            break
        d = nd
    return None


def state_dir(root):
    for sub in STATE_DIRS:
        d = os.path.join(root, sub)
        if os.path.isfile(os.path.join(d, '_tracking-state.json')):
            return d
    return os.path.join(root, STATE_DIRS[0])


def read(p):
    try:
        return io.open(p, encoding='utf-8').read()
    except Exception:
        return ''


def pick_file(sd, view):
    for name in ALIAS.get(view, [view]):
        p = os.path.join(sd, name)
        if os.path.isfile(p):
            return p
    return os.path.join(sd, view)


def reconcile(root):
    sd = state_dir(root)
    st = json.loads(io.open(os.path.join(sd, '_tracking-state.json'), encoding='utf-8-sig').read())
    n = int(st.get('last_committed_chapter') or 0)
    chars = list((st.get('characters') or {}).keys())
    fsh = [(f.get('summary') or '').strip()[:8] for f in (st.get('foreshadows') or [])]
    prices = [str(p) for p in ((st.get('facts') or {}).get('prices_used') or [])]

    rows = []
    # 上下文：进度段要出现章号（两种写法都认）
    p = pick_file(sd, '上下文.md')
    body = read(p)
    toks = [f'第 {n:03d} 章', f'第{n:03d}章', f'第 {n} 章'] if n else []
    rows.append(dict(view='上下文.md', exists=bool(body), need=len(toks),
                     missing=[t for t in toks[:1] if body and t not in body] if toks else []))

    # 事实词典：人名必在专名表
    body = read(pick_file(sd, '事实词典.md'))
    rows.append(dict(view='事实词典.md', exists=bool(body), need=len(chars),
                     missing=[c for c in chars if c not in body]))

    # 伏笔：summary 前 8 字
    body = read(pick_file(sd, '伏笔.md'))
    rows.append(dict(view='伏笔.md', exists=bool(body), need=len(fsh),
                     missing=[t for t in fsh if t and t not in body]))

    # 数字登记：每条价目里的数字
    body = read(pick_file(sd, '数字登记.md'))
    nums = []
    for s in prices:
        for m in re.findall(r'\d+', s):
            if m not in nums:
                nums.append(m)
    rows.append(dict(view='数字登记.md', exists=bool(body), need=len(nums),
                     missing=[x for x in nums if x not in body]))

    # 桥段记录：只报行数
    body = read(pick_file(sd, '桥段记录.md'))
    rows.append(dict(view='桥段记录.md', exists=bool(body), need=0, missing=[],
                     rows=len(re.findall(r'^\|', body, re.M))))
    return st, rows


def show(rows):
    bad = 0
    print(f'{"视图":<12}{"文件":<6}{"应有":>4}{"命中":>4}   缺')
    for r in rows:
        exists = '在' if r['exists'] else '缺'
        miss = r['missing']
        if not r['exists']:
            bad += 1
            note = '视图文件不在，这份投影没渲染'
        elif miss:
            bad += 1
            note = '、'.join(miss[:4]) + ('…' if len(miss) > 4 else '')
        else:
            note = f'表体 {r["rows"]} 行' if r['view'] == '桥段记录.md' else ''
        print(f'{r["view"]:<12}{exists:<6}{r["need"]:>4}{r["need"] - len(miss):>4}   {"MISS" if miss or not r["exists"] else "OK"} {note}')
    return bad


def write_log(root, st, rows, bad):
    d = os.path.join(root, '05_质检_审计评审节奏', '审计')
    os.makedirs(d, exist_ok=True)
    n = int(st.get('last_committed_chapter') or 0)
    p = os.path.join(d, f'投影日志_章{n:03d}.md')
    lines = [f'# 投影日志 · 第 {n:03d} 章', '',
             f'- 时间：{datetime.now().strftime("%Y-%m-%d %H:%M")}',
             f'- state_revision：{st.get("state_revision")}',
             f'- 结论：{"五视图全部同步" if not bad else f"{bad} 份视图有问题"}', '',
             '| 视图 | 文件 | 应有 | 命中 | 缺 |', '|---|---|---|---|---|']
    for r in rows:
        lines.append(f'| {r["view"]} | {"在" if r["exists"] else "缺"} | {r["need"]} | '
                     f'{r["need"] - len(r["missing"])} | {"、".join(r["missing"]) or "—"} |')
    lines += ['', '> 缺＝state 里有、视图里找不到。改视图，别改 state 去凑。', '']
    io.open(p, 'w', encoding='utf-8').write('\n'.join(lines))
    return p


def selftest():
    d = tempfile.mkdtemp(prefix='jipu-proj-')
    sd = os.path.join(d, STATE_DIRS[0])
    os.makedirs(sd)
    st = {
        'state_revision': 3, 'last_committed_chapter': 3,
        'threads': [{'id': 'T1', 'name': '三个月内把蛋孵出来', 'status': 'open', 'due': 18}],
        'foreshadows': [{'tier': 'A', 'summary': '车底那块石头——格雷已在门外追问', 'status': 'open'}],
        'characters': {'元歌': {'role': '主角'}, '格雷': {'role': '压迫'}},
        'facts': {'prices_used': ['淘渣工一天工钱 9 枚铜', '一筐炭 10 枚铜'],
                  'goods': ['弯头铁钩'], 'rules_established': [{'rule': '淘渣工按车计钱'}]},
        'beats': [{'chapter': 1, 'beats': []}],
    }
    io.open(os.path.join(sd, '_tracking-state.json'), 'w', encoding='utf-8').write(
        json.dumps(st, ensure_ascii=False))
    views = {
        '上下文.md': '已提交：第 003 章《门》。',
        '事实词典.md': '| 元歌 | 主角 |\n| 格雷 | 压迫 |',
        '伏笔.md': '车底那块石头——格雷已在门外追问',
        '数字登记.md': '工钱 9 枚铜；一筐炭 10 枚铜',
        '桥段记录.md': '\n| 模板号 | 章 |\n|---|---|\n| Q-101 | 1 |\n',
    }
    for k, v in views.items():
        io.open(os.path.join(sd, k), 'w', encoding='utf-8').write(v)
    _, rows = reconcile(d)
    rc_ok = show(rows)
    # 弄坏两份：伏笔清空、数字登记删掉
    io.open(os.path.join(sd, '伏笔.md'), 'w', encoding='utf-8').write('（还没写）')
    os.remove(os.path.join(sd, '数字登记.md'))
    _, rows2 = reconcile(d)
    rc_bad = show(rows2)
    ok = (rc_ok == 0 and rc_bad == 2
          and rows2[2]['missing'] == ['车底那块石头——']
          and not rows2[3]['exists'])
    print(f'\n自检：{"通过" if ok else "失败"}（齐 {rc_ok} 处问题／坏 2 份 → {rc_bad} 处）')
    shutil.rmtree(d, ignore_errors=True)
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description='五视图投影对账')
    ap.add_argument('--write', action='store_true', help='写 投影日志_章NNN.md')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    root = find_root()
    if not root:
        print('[停] 找不到 06_追踪_状态记录/_tracking-state.json')
        sys.exit(1)
    st, rows = reconcile(root)
    bad = show(rows)
    if a.write:
        print(f'\n日志：{write_log(root, st, rows, bad)}')
    print(f'\n{"PASS" if not bad else "FAIL"} —— {len(rows) - bad}/{len(rows)} 份视图同步')
    sys.exit(0 if not bad else 1)


if __name__ == '__main__':
    main()
