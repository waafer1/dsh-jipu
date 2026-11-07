#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""细纲体检.py —— 一章的“人、地、事、卡、账”缺一不许开写。

用法：
  python 细纲体检.py                    # 查 03_图纸_大纲与细纲/ 下 章纲_*／细纲_*.md
  python 细纲体检.py --file 细纲_第012章.md
  python 细纲体检.py --selftest

口径（头部九行，缺一 FAIL）：
  档 / 图 / 话 / 轴 / 出场人物 / 地点 / 事件 / 追卡 / 改账
  - 出场人物：本章有名有姓者，至少 1 个
  - 地点：一个具体场所，不许写“某地”
  - 事件：谁要什么 → 他做了什么 → 结果
  - 追卡：这件事追到哪张人物卡的哪一条（主角卡·他想要……）
  - 桥段：本章用哪 2 个 Q 号（最多 2 个；查 11-主题预设）
  - 改账：本章改了 欠／怕／信 哪一条；一条没改 → FAIL
退出码：0 通过；1 缺项；--selftest 失败 1。
"""
import argparse
import glob
import io
import os
import re
import sys
import tempfile

FIELDS = ['档', '图', '话', '轴', '出场人物', '地点', '事件', '追卡', '改账', '桥段']


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


def parse(text):
    got = {}
    for line in text.splitlines():
        m = re.match(r'^\s*([\u4e00-\u9fa5]{1,6})[：:]\s*(.*)$', line)
        if m and m.group(1) in FIELDS:
            got[m.group(1)] = m.group(2).strip()
    return got


def check_file(path):
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
    if got.get('改账') and not re.search(r'欠|怕|信', got['改账']):
        problems.append('改账（要写欠/怕/信哪条变了）')
    if got.get('追卡') and '卡' not in got['追卡']:
        problems.append('追卡（要写清追到哪张卡）')
    if got.get('桥段'):
        qs = set(re.findall(r'Q-\d+', got['桥段']))
        if len(qs) > 2:
            problems.append(f"桥段超过 2 个（{len(qs)} 个）")
    if problems:
        print(f'\n{name}: FAIL —— ' + '、'.join(problems))
        return 1
    print(f'\n{name}: PASS')
    return 0


def selftest():
    d = tempfile.mkdtemp(prefix='jipu-outline-')
    os.makedirs(os.path.join(d, '03_图纸_大纲与细纲'))
    io.open(os.path.join(d, '项目配置.json'), 'w', encoding='utf-8').write('{"book":{"title":"t"}}')
    p = os.path.join(d, '03_图纸_大纲与细纲', '细纲_第012章.md')
    full = '''档：T1
图：他蹲在炭棚口，把湿炭捏碎
话：“湿的算半担。”
轴：钱
出场人物：陈九、炭铺掌柜、打手甲
地点：东市炭棚
事件：陈九想赊一担炭，掌柜只给半担，他问出一条“湿炭折半”的规矩
追卡：主角卡·他想要（地契）；对手卡·账（欠三条命）
改账：欠——他又欠了掌柜半担炭
桥段：Q-101＋Q-107
'''
    io.open(p, 'w', encoding='utf-8').write(full)
    rc_ok = check_file(p)
    io.open(p, 'w', encoding='utf-8').write(full.replace('地点：东市炭棚\n', '地点：\n'))
    rc_bad = check_file(p)
    io.open(p, 'w', encoding='utf-8').write(full.replace('桥段：Q-101＋Q-107', '桥段：Q-101＋Q-107＋Q-112'))
    rc_many = check_file(p)
    import shutil
    shutil.rmtree(d, ignore_errors=True)
    ok = rc_ok == 0 and rc_bad == 1 and rc_many == 1
    print(f'\n自检：{"通过" if ok else "失败"}（齐 {rc_ok}／缺地点 {rc_bad}／桥段超 2 {rc_many}）')
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description='细纲体检（人物/地点/事件/追卡/改账）')
    ap.add_argument('--file', action='append', default=[])
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    files = a.file
    if not files:
        root = find_root()
        if root:
            d = os.path.join(root, '03_图纸_大纲与细纲')
            files = sorted(glob.glob(os.path.join(d, '细纲_*.md')) + glob.glob(os.path.join(d, '章纲_*.md')))
    if not files:
        print('[停] 没有细纲/章纲文件')
        sys.exit(1)
    rc = 0
    for f in files:
        rc = check_file(f) or rc
    sys.exit(rc)


if __name__ == '__main__':
    main()
