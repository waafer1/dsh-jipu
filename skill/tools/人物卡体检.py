#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""人物卡体检.py —— 人物卡先出，主角卡五项硬字段缺一不许动笔。

用法：
  python 人物卡体检.py                 # 查 02_设定_世界与角色/角色/*.md
  python 人物卡体检.py --file 主角卡.md
  python 人物卡体检.py --selftest

判据（A 卡）：
  硬字段：一句话／在故事里干的活／他想要／他怕／他和主角的账
  软字段：他坚信但错的／说话方式／可见件（缺了只 WARN）
  至少一张卡；所有卡都按上面的字段核。
退出码：0 通过；1 硬字段缺；--selftest 失败 1。
"""
import argparse
import glob
import io
import os
import re
import sys
import tempfile

HARD = [
    ('一句话', r'一句话[：:][ \t　]*(.+?)(?:\n|$)'),
    ('在故事里干的活', r'在故事里干的活[：:][ \t　]*(.+?)(?:\n|$)'),
    ('他想要', r'他想要[：:][ \t　]*(.+?)(?=[ \t　]*他怕[：:]|\n|$)'),
    ('他怕', r'他怕[：:][ \t　]*(.+?)(?=[ \t　]*他和主角的账[：:]|\n|$)'),
    ('他和主角的账', r'他和主角的账[：:][ \t　]*(.+?)(?:\n|$)'),
    ('底气', r'底气[^：:\n]*[：:][ \t　]*(.+?)(?:\n|$)'),
]
SOFT = [
    ('他坚信但错的', r'他坚信但错的[：:][ \t　]*(.+?)(?:\n|$)'),
    ('说话方式', r'说话方式[：:][ \t　]*(.+?)(?:\n|$)'),
    ('可见件', r'可见件[：:][ \t　]*(.+?)(?:\n|$)'),
]


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


def check_file(path):
    text = read(path)
    name = os.path.basename(path)
    if not text.strip():
        print(f'[停] 读不到人物卡：{path}')
        return 1
    problems, warns = [], []
    for label, pat in HARD:
        m = re.search(pat, text)
        val = (m.group(1).strip() if m else '')
        if not val or val in ('—', '-', '空'):
            problems.append(label)
            print(f'MISSING  {label}')
        else:
            print(f'OK       {label}: {val[:36]}')
    for label, pat in SOFT:
        m = re.search(pat, text)
        val = (m.group(1).strip() if m else '')
        if not val:
            warns.append(label)
    if warns:
        print('WARN     软字段缺：' + '、'.join(warns) + '（可后补）')
    if problems:
        print(f'\n{name}: FAIL 硬字段缺 {len(problems)} 项 —— ' + '、'.join(problems))
        return 1
    print(f'\n{name}: PASS')
    return 0


def selftest():
    d = tempfile.mkdtemp(prefix='jipu-char-')
    os.makedirs(os.path.join(d, '02_设定_世界与角色', '角色'))
    io.open(os.path.join(d, '项目配置.json'), 'w', encoding='utf-8').write('{"book":{"title":"t"}}')
    card = os.path.join(d, '02_设定_世界与角色', '角色', '主角卡.md')
    full = '''### 陈九（第 1 章 · A 卡）
一句话：一个替人试丹的学徒，想凑够一副药钱
在故事里干的活：主角
他想要：镇东那间铺子的地契
他怕：人知道他弟弟是逃兵
他和主角的账：欠师父三条命
他坚信但错的：只要规矩守得死，就没人能动他
说话方式：短句，从不用“请”
可见件：左手小指少半截
底气（凭什么还手）：他手里攥着掌柜私账的一页
'''
    io.open(card, 'w', encoding='utf-8').write(full)
    rc_ok = check_file(card)
    io.open(card, 'w', encoding='utf-8').write(full.replace('他怕：人知道他弟弟是逃兵', '他怕：'))
    rc_bad = check_file(card)
    import shutil
    shutil.rmtree(d, ignore_errors=True)
    ok = rc_ok == 0 and rc_bad == 1
    print(f'\n自检：{"通过" if ok else "失败"}（齐 {rc_ok}／缺他怕 {rc_bad}）')
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description='人物卡体检')
    ap.add_argument('--file', action='append', default=[])
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    files = a.file
    if not files:
        root = find_root()
        if root:
            files = sorted(glob.glob(os.path.join(root, '02_设定_世界与角色', '角色', '*.md')))
    if not files:
        print('[停] 没有人物卡。先出主角卡：02_设定_世界与角色/角色/主角卡.md')
        sys.exit(1)
    rc = 0
    for f in files:
        rc = check_file(f) or rc
    sys.exit(rc)


if __name__ == '__main__':
    main()
