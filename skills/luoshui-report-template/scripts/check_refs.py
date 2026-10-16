# -*- coding: utf-8 -*-
"""扫 skill 内所有 md，校验两类引用可达：
  ① `xxx.md` 形式的文件名引用 → 文件必须存在（references/ 或包根）
  ② `§N` / `§N.M` 形式的节引用 → 该文件里必须有对应节标题
同时校验：每个 md 内部的「节标题」编号连续、无重号。
用法：python3 scripts/check_refs.py
"""
import io
import os
import re
import sys

# 从脚本自身位置推导包根 ⇒ 换机器 / 分发到别人那儿也能跑
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

md_files = []
for dp, dn, fn in os.walk(ROOT):
    dn[:] = [d for d in dn if d not in ('__pycache__',)]
    for f in fn:
        if f.endswith('.md'):
            md_files.append(os.path.join(dp, f))
md_files.sort()

# ── 每份 md 的节标题集合 ──
secs = {}       # 文件名 → set('1','3.2', ...)
titles = {}     # 文件名 → {'1.2': 标题}
dup = []
for p in md_files:
    name = os.path.basename(p)
    t = io.open(p, encoding='utf-8', errors='replace').read()
    s = set()
    tt = {}
    for line in t.split('\n'):
        m = re.match(r'^(#{2,4})\s+(\d+(?:\.\d+)*)[.、\s]', line)
        if m:
            num = m.group(2)
            if num in s:
                dup.append('%s §%s' % (name, num))
            s.add(num)
            tt[num] = line.strip('# ').strip()
    secs[name] = s
    titles[name] = tt

allnames = set(secs) | {'SKILL.md', 'INSTALL.md'}

# ── 扫引用 ──
bad_file, bad_sec, n_file, n_sec = [], [], 0, 0
# `a.md` §1.2    或   `a.md` 的 §1.2      或  a.md §1
rx = re.compile(r'`([A-Za-z0-9_\-]+\.md)`[^\n]{0,14}?§\s*(\d+(?:\.\d+)*)')
rx2 = re.compile(r'`([A-Za-z0-9_\-]+\.md)`')
for p in md_files:
    me = os.path.basename(p)
    t = io.open(p, encoding='utf-8', errors='replace').read()
    for m in rx.finditer(t):
        f, sec = m.group(1), m.group(2)
        n_file += 1
        n_sec += 1
        if f not in allnames:
            bad_file.append('%s → `%s`（文件不存在）' % (me, f))
            continue
        if sec not in secs.get(f, set()):
            bad_sec.append('%s → `%s` §%s（该节不存在；它有 %s）'
                           % (me, f, sec, ','.join(sorted(secs.get(f, set()),
                                                          key=lambda x: [int(y) for y in x.split('.')])[:40])))
    for m in rx2.finditer(t):
        f = m.group(1)
        # 已经算过的（带 §）会重复计一次，无所谓 —— 只要文件存在
        if f not in allnames:
            bad_file.append('%s → `%s`（文件不存在）' % (me, f))
        n_file += 1

print('扫了 %d 份 md\n' % len(md_files))
print('%-34s %6s %7s  %s' % ('文件', '字节', '节数', '最大节号'))
print('-' * 72)
for p in md_files:
    name = os.path.basename(p)
    sz = os.path.getsize(p)
    ks = sorted(secs[name], key=lambda x: [int(y) for y in x.split('.')])
    print('%-34s %6d %7d  %s' % (name, sz, len(ks), ks[-1] if ks else '-'))

print()
print('文件名引用 %d 处 ｜ 带 § 的节引用 %d 处' % (n_file, n_sec))
print('文件不存在 = %d %s' % (len(bad_file), bad_file or '✓'))
print('节号不存在 = %d' % len(bad_sec))
for b in bad_sec:
    print('   ✗', b)
print('节号重号 = %d %s' % (len(dup), dup or '✓'))
