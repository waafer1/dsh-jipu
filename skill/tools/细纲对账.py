#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""细纲对账.py —— 细纲上写下的承诺，正文里到底兑现了没有。

细纲体检.py 管「写之前有没有想清楚」；本工具管「写完之后，答应的三件事落没落地」。
对应 InkOS 的第 33 维「章节备忘偏离」，但只取三样能机器对的承诺：

  事件      这一章要发生的那件事（谁做了什么），正文里得有它的专名与物件
  改势      这一章要动的势（缺／怕／信…），正文里得出现那条势
  章末未决  读者合上这一章时在等什么，正文末尾得把这件事摆出来

用法：
  python 细纲对账.py                  # 对 last_committed_chapter 那一章
  python 细纲对账.py --chapter 12
  python 细纲对账.py --write          # 另把对账单写到 05_质检_审计评审节奏/审计/细纲对账_章NNN.md
  python 细纲对账.py --selftest

判定（宁可少报，不制造误报）：
  有落点  承诺里的可指认词 ≥1 条出现在正文（章末未决要求出现在正文末尾 30%）
  弱      只命中 1 条，且该章承诺词覆盖率 < 0.4 —— 只提示，不拦
  无落点  一条都没命中 —— FAIL，这一条承诺正文没写

口径限制（写清楚，免得当成万能）：
  - 只认字面，改写成同义词会判成「无落点」，所以 FAIL 之后要人看一眼再改；
  - 不判顺序、不判强度，只判「有没有」；
  - 项目配置.json 的 playloop.audit_dimensions 若填了清单且不含「章节备忘偏离」，本工具自动跳过。

退出码：0 全有落点（含弱）；1 有无落点；--selftest 失败 1。
"""
import argparse
import glob
import io
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime

OUTLINE_DIR = '03_图纸_大纲与细纲'
TEXT_DIR = '04_正文_成品'
AUDIT_DIR = os.path.join('05_质检_审计评审节奏', '审计')
COMMITS = ('事件', '改势', '章末未决')
DIM_NAME = '章节备忘偏离'

# 虚词与高频功能字：含这些字的 2—3 字片段不当承诺词
STOP = set('的了是在和就也不与他她它们我你您这那哪个些很还又去来到说要会把被给对从向上下里外后前中为以及但而且所以如果因为虽然可以没有一样已经自己什么怎么时候一个两个不是就是还有再最更都才只儿之其于而所')

TAIL_RATIO = 0.30


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
    except Exception:
        return ''


def load_cfg(root):
    cfg = {}
    if root:
        p = os.path.join(root, '项目配置.json')
        if os.path.isfile(p):
            try:
                cfg = json.loads(io.open(p, encoding='utf-8-sig').read())
            except Exception:
                cfg = {}
    return cfg


def get_playloop(cfg):
    pl = cfg.get('playloop') or {}
    return pl if isinstance(pl, dict) else {}


def pick_outline(root, n):
    d = os.path.join(root, OUTLINE_DIR)
    cands = [os.path.join(d, '细纲_第%03d章.md' % n),
             os.path.join(d, '细纲_第%d章.md' % n),
             os.path.join(d, '章纲_第%03d章.md' % n),
             os.path.join(d, '章纲_第%d章.md' % n)]
    for p in cands:
        if os.path.isfile(p):
            return p
    hits = sorted(glob.glob(os.path.join(d, '细纲_第*d章.md' % ())) +
                  glob.glob(os.path.join(d, '细纲_第%d章*.md' % n)))
    for p in hits:
        if re.search(r'第\s*0*%d\s*章' % n, os.path.basename(p)):
            return p
    return None


def pick_text(root, n):
    d = os.path.join(root, TEXT_DIR)
    for pat in ('第%03d章_*.md' % n, '第%d章_*.md' % n):
        hits = sorted(glob.glob(os.path.join(d, pat)))
        if hits:
            return hits[0]
    hits = sorted(glob.glob(os.path.join(d, '第*章*.md')))
    for p in hits:
        if re.search(r'第\s*0*%d\s*章' % n, os.path.basename(p)):
            return p
    return None


def parse_fields(text):
    got = {}
    for line in text.splitlines():
        m = re.match(r'^\s*([\u4e00-\u9fa5]{1,6})[：:]\s*(.*)$', line)
        if m and m.group(1) in COMMITS:
            got[m.group(1)] = m.group(2).strip()
    return got


def names_of(fields_text, cfg):
    """出场人物 + 专名表：这些词一定算「可指认」。"""
    names = []
    m = re.search(r'^\s*出场人物[：:]\s*(.+)$', fields_text, re.M)
    if m:
        for part in re.split(r'[、，,／/\s]+', m.group(1)):
            part = part.strip().strip('（）()')
            if len(part) >= 2:
                names.append(part)
    for p in ((cfg.get('lexicon') or {}).get('proper_names') or []):
        if isinstance(p, str) and len(p) >= 2:
            names.append(p)
    out = []
    for x in names:
        if x not in out:
            out.append(x)
    return out


def match_phrases(field_text, text, names):
    """在正文里找承诺句的连续命中片段：≥2 字、不含虚词、不是人名本身。

    用 SequenceMatcher 而不是分词：中文没有空格，n-gram 会切出「人敲门」「块石头」这种碎片，
    连续匹配拿到的才是「寒石」「三枚铜币」这种能给人看的证据。
    """
    from difflib import SequenceMatcher
    if not field_text or not text:
        return []
    sm = SequenceMatcher(None, field_text, text, autojunk=False)
    raw = [field_text[a:a + n] for a, _b, n in sm.get_matching_blocks() if n >= 2]
    out = []
    for blk in raw:
        if not re.fullmatch(r'[\u4e00-\u9fa5]+', blk):
            continue
        # 长出的一段里夹着虚词（「车底那块石头」夹了「那」）：切掉虚词，留下实词段
        for piece in re.split('[%s]' % ''.join(STOP), blk):
            p = piece.strip()
            if len(p) < 2:
                continue
            if any(p == nm or (len(p) <= 3 and nm in p) for nm in names):
                continue
            if any(p in k or k in p for k in out):
                continue
            out.append(p)
    out.sort(key=len, reverse=True)
    return out


def judge(commit, field_text, hit_names, text):
    """returns (level, hits)。人名命中只算「弱」；物件／动作的连续命中才算「有落点」。

    章末未决只在正文末尾 30% 找；末尾找不到再看全文——全文有、末尾没有，也是「弱」。
    """
    if commit == '章末未决' and text:
        tail = text[int(len(text) * (1 - TAIL_RATIO)):]
        hits = match_phrases(field_text, tail, hit_names)
        if any(len(h) >= 3 for h in hits) or len(hits) >= 2:
            return '有落点', hits
        if hits:
            return '弱', hits
        whole = match_phrases(field_text, text, hit_names)
        if whole:
            return '弱', whole          # 写了，但没摆到章末
        named = [nm for nm in hit_names if nm in tail]
        return ('弱', named) if named else ('无落点', [])
    hits = match_phrases(field_text, text, hit_names)
    if any(len(h) >= 3 for h in hits):
        return '有落点', hits
    if hits:
        matched = sum(len(h) for h in hits)
        if len(field_text) and matched / float(len(field_text)) >= 0.30:
            return '有落点', hits
        return '弱', hits
    named = [nm for nm in hit_names if nm in text]
    if named:
        return '弱', named
    return '无落点', []


def reconcile(root, n, write=False):
    cfg = load_cfg(root)
    pl = get_playloop(cfg)
    dims = pl.get('audit_dimensions') or []
    if dims and DIM_NAME not in dims:
        print('[跳] 项目配置的 playloop.audit_dimensions 不含「%s」，这本不跑这一维' % DIM_NAME)
        return 0
    op = pick_outline(root, n)
    tp = pick_text(root, n)
    if not op:
        print('[停] 找不到第 %d 章细纲（%s/细纲_第%03d章.md）' % (n, OUTLINE_DIR, n))
        return 1
    if not tp:
        print('[停] 找不到第 %d 章正文（%s/第%03d章_*.md）' % (n, TEXT_DIR, n))
        return 1
    otext = read(op)
    ttext = read(tp)
    got = parse_fields(otext)
    names = names_of(otext, cfg)
    lines = []
    lines.append('对账 第%03d章' % n)
    lines.append('细纲 %s' % os.path.basename(op))
    lines.append('正文 %s（%d 字）' % (os.path.basename(tp), len(re.sub(r'\s', '', ttext))))
    bad = 0
    warn = 0
    for c in COMMITS:
        val = got.get(c, '')
        if not val:
            lines.append('%-6s 缺这一行（旧格式或没写；先跑 细纲体检.py 补齐）' % c)
            bad += 1
            continue
        hit_names = [nm for nm in names if nm in val]
        level, hits = judge(c, val, hit_names, ttext)
        if level == '无落点':
            bad += 1
            lines.append('%-6s 无落点 —— 等：%s' % (c, val[:44]))
            if hit_names:
                lines.append('       出场人物在正文里：%s' % '、'.join(hit_names))
        elif level == '弱':
            warn += 1
            lines.append('%-6s 弱（命中 %s）—— 承诺 %s' % (c, '、'.join(hits), val[:32]))
        else:
            lines.append('%-6s 有落点（%s）' % (c, '、'.join(hits[:4])))
    verdict = 'FAIL —— %d 条承诺正文没兑现' % bad if bad else (
        'PASS（%d 条弱，看一眼）' % warn if warn else 'PASS')
    lines.append('')
    lines.append(verdict)
    body = '\n'.join(lines)
    print(body)
    if write:
        d = os.path.join(root, AUDIT_DIR)
        if os.path.isdir(d):
            p = os.path.join(d, '细纲对账_章%03d.md' % n)
            io.open(p, 'w', encoding='utf-8').write(
                '# 细纲对账 · 第%03d章\n\n> %s\n\n```\n%s\n```\n'
                % (n, datetime.now().strftime('%Y-%m-%d %H:%M'), body))
            print('[写] %s' % p)
    return 1 if bad else 0


def selftest():
    d = tempfile.mkdtemp(prefix='jipu-outline-recon-')
    os.makedirs(os.path.join(d, OUTLINE_DIR))
    os.makedirs(os.path.join(d, TEXT_DIR))
    os.makedirs(os.path.join(d, AUDIT_DIR))
    io.open(os.path.join(d, '项目配置.json'), 'w', encoding='utf-8').write(
        json.dumps({'book': {'title': 't'}, 'playloop': {'main': '结算型', 'audit_dimensions': []}},
                   ensure_ascii=False))
    outline = '''爽点类型：得物
档：T1
图：他蹲在车尾撬冻在板缝里的东西
话：“这车没货。”
轴：钱
出场人物：元歌、格雷、霍尔
地点：骨料场
事件：元歌想结工钱买炭，格雷验车说这车没货扣了三枚铜币；收工后元歌撬下冻在车缝里的寒石藏进怀里
追卡：主角卡·他想要（一筐炭）
改势：欠——格雷把这车记成没货，元歌欠他一次话柄
桥段：Q-112＋Q-121
章末未决：楼下有人敲门，格雷问车底那块石头
'''
    good = ('元歌把弯头铁钩伸进车缝，撬了三下才把那块寒石弄下来，塞进怀里。'
            '格雷验车时只说了一句这车没货，三枚铜币就没了。'
            '夜里雪下起来，寒石吸着他手上的寒气，冻裂的口子不疼了。\n\n'
            '后半夜有人在楼下敲门。是格雷的声音：元歌，车底那块石头呢？')
    io.open(os.path.join(d, OUTLINE_DIR, '细纲_第001章.md'), 'w', encoding='utf-8').write(outline)
    tp = os.path.join(d, TEXT_DIR, '第001章_车底的石头.md')
    io.open(tp, 'w', encoding='utf-8').write(good)
    rc_ok = reconcile(d, 1)
    # 章末没兑现：把结尾换成别的
    io.open(tp, 'w', encoding='utf-8').write(good.split('后半夜')[0])
    rc_tail = reconcile(d, 1)
    # 整章写跑偏：只有背景
    io.open(tp, 'w', encoding='utf-8').write('风从骨头缝里过，街上没有人，灯一盏一盏灭下去。' * 8)
    rc_off = reconcile(d, 1)
    # 维度清单不含本维：该跳过
    io.open(os.path.join(d, '项目配置.json'), 'w', encoding='utf-8').write(
        json.dumps({'playloop': {'main': '探索型', 'audit_dimensions': ['节奏', '视角一致性']}},
                   ensure_ascii=False))
    rc_skip = reconcile(d, 1)
    shutil.rmtree(d, ignore_errors=True)
    ok = (rc_ok == 0 and rc_tail == 1 and rc_off == 1 and rc_skip == 0)
    print('\n自检：%s（齐 %d／章末没兑现 %d／整章跑偏 %d／维度不含本维 %d）'
          % ('通过' if ok else '失败', rc_ok, rc_tail, rc_off, rc_skip))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description='细纲对账（事件／改势／章末未决 在正文里有没有落点）')
    ap.add_argument('--chapter', type=int, default=0)
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--root', default='')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    root = os.path.abspath(a.root) if a.root else find_root()
    if not root:
        print('[停] 找不到 项目配置.json（用 --root 指定项目根）')
        sys.exit(1)
    n = a.chapter
    if not n:
        sd = os.path.join(root, '06_追踪_状态记录')
        if not os.path.isdir(sd):
            sd = os.path.join(root, '06_追踪_状态账本')
        sp = os.path.join(sd, '_tracking-state.json')
        if os.path.isfile(sp):
            try:
                n = int(json.loads(io.open(sp, encoding='utf-8-sig').read())
                        .get('last_committed_chapter') or 0)
            except Exception:
                n = 0
        if not n:
            nums = [int(x) for x in re.findall(r'第\s*(\d+)\s*章',
                                               ' '.join(os.path.basename(p) for p in
                                                        glob.glob(os.path.join(root, TEXT_DIR, '*.md'))))]
            n = max(nums) if nums else 1
    sys.exit(reconcile(root, n, a.write))


if __name__ == '__main__':
    main()
