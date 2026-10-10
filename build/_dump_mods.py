# -*- coding: utf-8 -*-
"""把某公司线上模块的原始 html 导出成文本，便于人眼核对结构与 data-chart 用法。

用法： python build/_dump_mods.py 000731 1 9 24 26 28 29
        python build/_dump_mods.py 000731            # 顺带列出图表行 id
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
HDR = {'apikey': CFG['key'], 'Authorization': 'Bearer ' + CFG['key'],
       'Accept': 'application/json'}


def get(path):
    rq = urllib.request.Request(BASE + path, headers=HDR)
    with urllib.request.urlopen(rq, timeout=90) as r:
        return json.loads(r.read().decode('utf-8'))


code = sys.argv[1]
want = [int(x) for x in sys.argv[2:]]
rows, off = [], 0
while True:
    b = get('wb_report_mods?select=no,seq,title,html&report_id=eq.%s'
            '&order=seq.asc&limit=1000&offset=%d' % (code, off))
    rows += b
    if len(b) < 1000:
        break
    off += 1000
rows.sort(key=lambda x: int(x.get('no') or 0))

if not want:
    for m in rows:
        h = m.get('html') or ''
        print('%2s %-34s %6d 字  charts=%s' % (
            m['no'], (m.get('title') or '')[:34], len(h),
            re.findall(r'data-chart="([^"]+)"', h)))
    print()
    ch = get('wb_report_charts?select=id,name&report_id=eq.%s&order=seq.asc&limit=1000' % code)
    print('图表行 %d 个：' % len(ch))
    for c in ch:
        print('  %-24s %s' % (c['id'], c.get('name')))
else:
    for m in rows:
        if int(m['no']) in want:
            print('#' * 78)
            print('# m%s  %s  (%d 字)' % (m['no'], m.get('title'), len(m.get('html') or '')))
            print('#' * 78)
            print(m.get('html') or '')
            print()
