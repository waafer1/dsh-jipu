#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""细纲体检.py —— 一章的“人、地、事、卡、势”缺一不许开写。

用法：
  python 细纲体检.py                    # 查 03_图纸_大纲与细纲/ 下 章纲_*／细纲_*.md
  python 细纲体检.py --file 细纲_第012章.md
  python 细纲体检.py --selftest

口径（头部十一行，缺一 FAIL）：
  档 / 图 / 话 / 轴 / 出场人物 / 地点 / 事件 / 追卡 / 改势 / 桥段 / 章末未决
  - 出场人物：本章有名有姓者，至少 1 个
  - 地点：一个具体场所，不许写“某地”
  - 事件：谁要什么 → 他做了什么 → 结果
  - 追卡：这件事追到哪张人物卡的哪一条（主角卡·他想要……）
  - 桥段：本章用哪 2 个 Q 号（最多 2 个；查 11-主题预设）
  - 章末未决：这一章结束时读者等什么（一句话，≤40 字；写"无／待定"＝没钩子 → FAIL）
  - 改势：本章改了 欠／怕／信 哪一条；一条没改 → FAIL

玩法（读 项目配置.json 的 playloop，缺省为结算型）：
  - beats：拍数下限，细纲「拍点／逐拍」段编号条目少于这个数 → FAIL
  - types：本章爽点类型必须落在玩法卡的型表里（空表＝不校验）
  - momentum_terms：改势可用的词（默认 缺|欠|怕|信）
退出码：0 通过；1 缺项；--selftest 失败 1。
"""
import argparse
import glob
import io
import json
import os
import re
import sys
import tempfile

FIELDS = ['档', '图', '话', '轴', '出场人物', '地点', '事件', '追卡', '改势', '桥段', '章末未决']

DEFAULT_PLAYLOOP = {
    'main': '结算型',
    'sub': '',
    'beats': 7,
    'types': [],
    'momentum_terms': '缺|欠|怕|信',
}


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


def load_playloop(root):
    cfg = {}
    if root:
        p = os.path.join(root, '项目配置.json')
        if os.path.isfile(p):
            try:
                cfg = json.loads(io.open(p, encoding='utf-8-sig').read())
            except Exception:
                cfg = {}
    pl = dict(DEFAULT_PLAYLOOP)
    got = cfg.get('playloop') or {}
    if isinstance(got, dict):
        pl.update(got)
    return pl


def read(p):
    try:
        return io.open(p, encoding='utf-8').read()
    except FileNotFoundError:
        return ''


def parse(text):
    got = {}
    for line in text.splitlines():
        m = re.match(r'^\s*([\u4e00-\u9fa5]{1,6})[：:]\s*(.*)$', line)
        if m and m.group(1) in FIELDS:
            got[m.group(1)] = m.group(2).strip()
    return got


def count_beats(text):
    """「拍点／逐拍／八拍／七拍」段下的编号条目数；找不到小节就数全文编号行。"""
    m = re.search(r'^#+\s*[^\n]*(拍点|逐拍|八拍|七拍)[^\n]*\n(.*?)(?=^#+\s|\Z)',
                  text, re.S | re.M)
    body = m.group(2) if m else ''
    n = len(re.findall(r'^\s*\d+\s*[.、)]', body, re.M))
    if n == 0:
        n = len(re.findall(r'^\s*\d+\s*[.、)]\s+\S', text, re.M))
    return n


def get_type_line(text):
    m = re.search(r'^\s*(?:爽点类型|类型|母题)[：:]\s*(.+)$', text, re.M)
    return m.group(1).strip() if m else ''


def check_file(path, pl=None):
    pl = pl or dict(DEFAULT_PLAYLOOP)
    text = read(path)
    name = os.path.basename(path)
    if not text.strip():
        print(f'[停] 读不到细纲：{path}')
        return 1
    got = parse(text)
    problems = []
    for f in FIELDS:
        val = got.get(f, '')
        if not val:
            problems.append(f)
            print(f'MISSING  {f}')
        else:
            print(f'OK       {f}: {val[:38]}')
    terms = pl.get('momentum_terms') or DEFAULT_PLAYLOOP['momentum_terms']
    if got.get('改势') and not re.search(terms, got['改势']):
        problems.append(f'改势（要写 {terms} 哪条变了）')
    if got.get('追卡') and '卡' not in got['追卡']:
        problems.append('追卡（要写清追到哪张卡）')
    # 岗位自测·细纲岗：事件必须是一件事（专名＋物＋动作），不是一段状态
    ev = got.get('事件', '')
    if ev:
        state_words = re.findall(r'意识到|明白了|开始|决定|感觉到|感觉|成长|觉醒|蜕变|命运', ev)
        if state_words:
            problems.append('事件写成状态（命中：' + '、'.join(sorted(set(state_words))) + '）——要写成谁做了什么')
        if len(ev) < 10:
            problems.append('事件太短，写不出"专名＋物＋动作"')
        if not re.search(r'(把|给|塞|递|砸|卖|买|换|抢|藏|查|问|喊|推|拉|砸|烧|埋|记|认|借|还)', ev):
            problems.append('事件里没有可指认的动作')
    if got.get('桥段'):
        qs = set(re.findall(r'Q-\d+', got['桥段']))
        if len(qs) > 2:
            problems.append(f"桥段超过 2 个（{len(qs)} 个）")
    # 章末未决：读者这一章结束时等什么。空／「无」＝这章没有钩子
    hook = got.get('章末未决', '')
    if hook:
        if hook.strip() in ('无', '暂无', '待定', '没有', '—', '-', '略'):
            problems.append('章末未决写成"无"——这章结束读者没有等的')
        elif len(hook) > 40:
            problems.append(f'章末未决过长（{len(hook)} 字 > 40），要一句话')
    beats = int(pl.get('beats') or 0)
    got_beats = count_beats(text)
    if beats and got_beats and got_beats < beats:
        problems.append(f"拍数不足（{got_beats} 拍 < 玩法卡 {pl.get('main')} 的 {beats} 拍）")
    types = [t for t in (pl.get('types') or []) if t]
    if types:
        tl = get_type_line(text)
        if tl and not any(t in tl for t in types):
            problems.append(f"爽点类型不在 {pl.get('main')} 的型表里（{tl}）")
    if problems:
        print(f'\n{name}: FAIL —— ' + '、'.join(problems))
        return 1
    print(f'\n{name}: PASS')
    return 0


def selftest():
    d = tempfile.mkdtemp(prefix='jipu-outline-')
    os.makedirs(os.path.join(d, '03_图纸_大纲与细纲'))
    cfg = {'book': {'title': 't'},
           'playloop': {'main': '结算型', 'beats': 4, 'types': ['破局', '得物']}}
    io.open(os.path.join(d, '项目配置.json'), 'w', encoding='utf-8').write(
        json.dumps(cfg, ensure_ascii=False))
    pl = load_playloop(d)
    p = os.path.join(d, '03_图纸_大纲与细纲', '细纲_第012章.md')
    head = '''爽点类型：破局（先给力量）
档：T1
图：他蹲在炭棚口，把湿炭捏碎
话：“湿的算半担。”
轴：钱
出场人物：陈九、炭铺掌柜、打手甲
地点：东市炭棚
事件：陈九想赊一担炭，掌柜只给半担，他问出一条“湿炭折半”的规矩
追卡：主角卡·他想要（地契）；对手卡·牵扯（欠三条命）
改势：欠——他又欠了掌柜半担炭
桥段：Q-101＋Q-107
章末未决：半担湿炭撑不到明早，他拿什么交？
'''
    body4 = '\n## 拍点四条\n\n1. 起\n2. 承\n3. 转\n4. 合\n'
    io.open(p, 'w', encoding='utf-8').write(head + body4)
    rc_ok = check_file(p, pl)
    io.open(p, 'w', encoding='utf-8').write(head + '\n## 拍点三条\n\n1. 起\n2. 承\n3. 转\n')
    rc_few = check_file(p, pl)
    io.open(p, 'w', encoding='utf-8').write(
        head.replace('爽点类型：破局（先给力量）', '爽点类型：发糖') + body4)
    rc_type = check_file(p, pl)
    io.open(p, 'w', encoding='utf-8').write((head + body4).replace('地点：东市炭棚\n', '地点：\n'))
    rc_missing = check_file(p, pl)
    io.open(p, 'w', encoding='utf-8').write(
        (head + body4).replace('事件：陈九想赊一担炭，掌柜只给半担，他问出一条“湿炭折半”的规矩',
                               '事件：陈九意识到自己该走了，心里开始明白这里的规矩'))
    rc_state = check_file(p, pl)
    io.open(p, 'w', encoding='utf-8').write(
        (head + body4).replace('章末未决：半担湿炭撑不到明早，他拿什么交？', '章末未决：无'))
    rc_hook = check_file(p, pl)
    import shutil
    shutil.rmtree(d, ignore_errors=True)
    ok = (rc_ok == 0 and rc_few == 1 and rc_type == 1 and rc_missing == 1
          and rc_state == 1 and rc_hook == 1)
    print(f'\n自检：{"通过" if ok else "失败"}'
          f'（齐 {rc_ok}／拍少 {rc_few}／型不对 {rc_type}／缺地点 {rc_missing}'
          f'／事件写成状态 {rc_state}／章末未决写无 {rc_hook}）')
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description='细纲体检（人物/地点/事件/追卡/改势/拍数）')
    ap.add_argument('--file', action='append', default=[])
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    files = a.file
    root = find_root()
    if not files:
        if root:
            d = os.path.join(root, '03_图纸_大纲与细纲')
            files = sorted(glob.glob(os.path.join(d, '细纲_*.md')) + glob.glob(os.path.join(d, '章纲_*.md')))
    if not files:
        print('[停] 没有细纲/章纲文件')
        sys.exit(1)
    pl = load_playloop(root)
    rc = 0
    for f in files:
        rc = check_file(f, pl) or rc
    sys.exit(rc)


if __name__ == '__main__':
    main()
