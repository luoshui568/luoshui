#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""组装《大宗商品百年周期全景》单文件离线页面 + 生成逐页签验证变体。"""
import os, re

BASE = os.path.dirname(os.path.abspath(__file__))
DEST = '/Users/luoshui/WorkBuddy/2026-10-10-22-59-27/luoshui/deliver'
OUTNAME = '大宗商品百年周期全景-1900-2025.html'

tpl = open(os.path.join(BASE, 'template.html'), encoding='utf-8').read()
chartjs = open(os.path.join(BASE, 'data/chart.umd.js'), encoding='utf-8').read()
data = open(os.path.join(BASE, 'data/page_data.json'), encoding='utf-8').read()

out = tpl.replace('/*__CHARTJS__*/', chartjs).replace('/*__DATA__*/', data)
assert '/*__CHARTJS__*/' not in out and '/*__DATA__*/' not in out, '占位符未全部替换'

os.makedirs(DEST, exist_ok=True)
dest = os.path.join(DEST, OUTNAME)
open(dest, 'w', encoding='utf-8').write(out)
print('built:', dest, len(out), 'chars')

PANE_RE = re.compile(r'<section class="pane[^"]*"[^>]*?\bid="p-(\w+)">')


def variant(pid):
    s = out.replace('<nav class="tabs" id="tabs">',
                    '<nav class="tabs" id="tabs" style="display:none">', 1)
    def rep(m):
        p = m.group(1)
        cls = 'pane on' if p == pid else 'pane'
        style = '' if p == pid else ' style="display:none"'
        return f'<section class="{cls}"{style} id="p-{p}">'
    s = PANE_RE.sub(rep, s)
    return s


for pid in ['panorama', 'prices', 'index', 'cycle', 'method']:
    p = os.path.join(BASE, f'v_{pid}.html')
    open(p, 'w', encoding='utf-8').write(variant(pid))
    print('variant:', p)
