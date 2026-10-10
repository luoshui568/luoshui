# -*- coding: utf-8 -*-
"""导出宝钛 600456 的深度模块 HTML（m3/m6/m7/m16/m24/m25/m26/m28）作为深度标尺"""
import json, io, re, sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
p = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38\build\seed\report_600456.json'
j = json.load(io.open(p, encoding='utf-8'))
want = [3, 16, 24, 28]
out = []
for m in j['mods']:
    no = int(m['no'])
    if no in want:
        out.append('=' * 78)
        out.append('m%d  %s   [%d chars]' % (no, m['title'], len(m['html'])))
        out.append('=' * 78)
        out.append(m['html'])
        out.append('')
io.open(r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38\build\_bt_deep.txt', 'w',
        encoding='utf-8').write('\n'.join(out))
print('ok')
