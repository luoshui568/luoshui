# -*- coding: utf-8 -*-
"""补拉线上 10 家的图表 option（含股价年线 / 量价序列），存 _score_src/<code>_charts.json。

评分第 8/9/10 项（盘整 / 底部 / 放量）需要股价与量能序列，
报告的图槽里已有现成且已核实的数据，优先用它，避免再造一轮取数。
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
        except Exception as e:
            last = e
            if hasattr(e, 'code') and 400 <= e.code < 500:
                raise
            time.sleep(3 * (i + 1))
    raise last


for code in CODES:
    rows, off = [], 0
    while True:
        b = get('wb_report_charts?report_id=eq.%s&select=id,opt'
                '&order=id.asc&limit=100&offset=%d' % (code, off))
        rows += b
        if len(b) < 100:
            break
        off += 100
    io.open(os.path.join(OUT, '%s_charts.json' % code), 'w', encoding='utf-8').write(
        json.dumps(rows, ensure_ascii=False))
    print('%-7s 图表 %2d  id 前缀样例 %s' % (code, len(rows),
                                          [x['id'] for x in rows[:3]]))

print('\n完成 → _score_src/*_charts.json')
