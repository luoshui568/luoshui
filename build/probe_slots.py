# -*- coding: utf-8 -*-
"""探针：用**线上库**的数据比对「模块里的 data-chart 槽位」与「图表行」，
找出会渲染成空框的孤儿槽位。只读。

用法：python build/_probe_slots.py [code]
"""
import io
import json
import os
import re
import sys
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
B = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(io.open(os.path.join(B, 'cloud.json'), encoding='utf-8'))
BASE = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']
HDR = {'apikey': CFG['key'], 'Authorization': 'Bearer ' + CFG['key'], 'Accept': 'application/json'}
CODE = sys.argv[1] if len(sys.argv) > 1 else '600456'


def page(path):
    rows, off = [], 0
    while True:
        rq = urllib.request.Request(BASE + path + '&limit=1000&offset=%d' % off, headers=HDR)
        with urllib.request.urlopen(rq, timeout=90) as r:
            b = json.loads(r.read().decode('utf-8'))
        if not b:
            break
        rows += b
        if len(b) < 1000:
            break
        off += 1000
    return rows


mods = page('wb_report_mods?report_id=eq.%s&select=id,no,title,html' % CODE)
charts = page('wb_report_charts?report_id=eq.%s&select=id,name,opt' % CODE)

keys = set()
for c in charts:
    k = str(c['id'])
    if k.startswith(CODE + '_'):
        k = k[len(CODE) + 1:]
    keys.add(k)

print('线上库 %s ：模块 %d 个 / 图表 %d 张' % (CODE, len(mods), len(charts)))
print()
used = {}
for m in mods:
    html = m.get('html') or ''
    for mm in re.finditer(r'data-chart\s*=\s*["\']([^"\']*)["\']', html):
        v = mm.group(1)
        used.setdefault(v, []).append(str(m.get('no')))
print('== 模块里的槽位（共 %d 处，去重 %d 个键）==' % (sum(len(v) for v in used.values()), len(used)))
for k in sorted(used):
    mark = '' if k in keys else '   <<<< 库中无此图表 ⇒ 会渲染空框！'
    odd = '   <<<< 键名有异常字符 %r' % k if k != k.strip() else ''
    print('  %-24s 模块 %-12s%s%s' % (repr(k), ','.join(used[k]), mark, odd))
print()
print('== 库里有图但模块里没有槽位 ==', sorted([k for k in keys if k not in used]))
print()
print('== 模块槽位但库里没有图 ==', sorted([k for k in used if k not in keys]))

# 与本地 seed 的差异
p = os.path.join(B, 'seed', 'report_%s.json' % CODE)
if os.path.exists(p):
    d = json.load(io.open(p, encoding='utf-8'))
    sm = {str(m.get('no')): (m.get('html') or '') for m in d['mods']}
    lm = {str(m.get('no')): (m.get('html') or '') for m in mods}
    print()
    print('== 线上库 vs 本地 seed 的模块正文差异 ==')
    for no in sorted(set(list(sm) + list(lm)), key=lambda x: int(x) if x.isdigit() else 0):
        a, b = sm.get(no), lm.get(no)
        if a is None:
            print('  m%-4s 只在线上有 (len=%d)' % (no, len(b)))
        elif b is None:
            print('  m%-4s 只在本地有 (len=%d)' % (no, len(a)))
        elif a != b:
            print('  m%-4s 不一致：本地 %d 字符 / 线上 %d 字符' % (no, len(a), len(b)))
    sk = set(str(c['id']) for c in d['charts'])
    if sk != keys:
        print('  图表键差异：只在本地 %s / 只在线上 %s' % (sorted(sk - keys), sorted(keys - sk)))
