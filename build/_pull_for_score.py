# -*- coding: utf-8 -*-
"""把线上 10 家报告的模块全量拉到本地 _score_src/，供评分引擎抽取原料。

★ 为什么不用本地 seed：存量 5 家的 seed 是陈旧残片
  （600456 仅 11 个顶层键、name=None）——线上库才是真身。
"""
import io
import json
import os
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '_score_src')
os.makedirs(OUT, exist_ok=True)

CODES = ['600456', '600459', '002237', '000731', '000830',
         '603977', '601118', '601958', '603599', '002408']

c = json.loads(io.open(os.path.join(HERE, 'cloud.json'), encoding='utf-8').read())
REST = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % c['envId']
H = {'Authorization': 'Bearer ' + c['key']}


def get(q, tries=4):
    last = None
    for i in range(tries):
        try:
            r = urllib.request.Request(REST + q, headers=H)
            with urllib.request.urlopen(r, timeout=90) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except Exception as e:                       # 出网间歇不可用 ⇒ 退避重试
            last = e
            if hasattr(e, 'code') and 400 <= e.code < 500:
                raise                                # 4xx 立即失败，不重试
            time.sleep(3 * (i + 1))
    raise last


total = 0
for code in CODES:
    rows, off = [], 0
    while True:
        b = get('wb_report_mods?report_id=eq.%s&select=no,title,html'
                '&order=no.asc&limit=200&offset=%d' % (code, off))
        rows += b
        if len(b) < 200:
            break
        off += 200
    charts = get('wb_report_charts?report_id=eq.%s&select=id' % code)
    io.open(os.path.join(OUT, '%s.json' % code), 'w', encoding='utf-8').write(
        json.dumps({'code': code, 'mods': rows, 'charts': charts},
                   ensure_ascii=False))
    n_miss = sum((m.get('html') or '').count('[MISSING]') for m in rows)
    print('%s  mods %2d  图表 %2d  字符 %7d  [MISSING] %d'
          % (code, len(rows), len(charts),
             sum(len(m.get('html') or '') for m in rows), n_miss))
    total += 1

print('\n已拉取 %d 家 → _score_src/' % total)
