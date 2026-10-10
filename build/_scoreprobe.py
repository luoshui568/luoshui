# -*- coding: utf-8 -*-
"""评分原料探针：把 10 份 seed 里可用于自动评分的字段摊成一张表。

目的：在设计评分规则前，先确认每项原则的数据**是否存在**——
      缺哪项就补哪项，别让规则去猜。
用法：python _scoreprobe.py > _scorep.txt
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = os.path.join(HERE, 'seed')

CODES = ['600456', '600459', '002237', '000731', '000830',
         '603977', '601118', '601958', '603599', '002408']

FIN_KEYS = ['mktcap', 'pe', 'pb', 'price', 'rev', 'gm', 'nm', 'roe', 'roic',
            'lev', 'eps', 'ocf', 'asof']


def strip(x):
    return re.sub(r'<[^>]+>', '', str(x or ''))


for code in CODES:
    p = os.path.join(SEED, 'data_v31_%s.json' % code)
    if not os.path.exists(p):
        print('%-7s 缺 seed' % code)
        continue
    d = json.loads(io.open(p, encoding='utf-8').read())
    print('#' * 70)
    print('### %s  %s  grp=%s  行业=%s' % (code, d.get('name'),
                                        d.get('grp'), d.get('industry_name')))
    print('顶层键 %d 个: %s' % (len(d), ' '.join(sorted(d.keys()))))

    # ---- ① 股东背景 ----
    ctl = d.get('controller') or {}
    print('-- ① 股东/实控人:')
    if isinstance(ctl, dict):
        for k in ('controller', '_type', 'controlling', 'hub_count', 'siblings'):
            v = ctl.get(k)
            if v not in (None, '', [], {}):
                print('     %-12s = %s' % (k, strip(v)[:110]))
    sh = d.get('shareholder') or {}
    if isinstance(sh, dict):
        print('     shareholder.chain = %s' % strip(sh.get('chain'))[:140])

    # ---- ② 护城河 / 行业地位 ----
    print('-- ② 护城河/地位(用于「独一无二」):')
    for k in ('moat',):
        v = d.get(k)
        if isinstance(v, dict):
            for kk in v:
                print('     moat.%-10s = %s' % (kk, strip(v[kk])[:100]))
        elif v:
            print('     moat = %s' % strip(v)[:160])
    biz = d.get('business') or {}
    segs = biz.get('segments') or []
    txt_all = ' '.join(strip(x) for row in segs for x in row)
    hits = [w for w in ('唯一', '最大', '龙头', '第一', '领先', '垄断', '全球',
                        '国内首家', '独家') if w in txt_all]
    print('     business.segments %d 段 | 地位关键词: %s' % (len(segs), hits or '无'))

    # ---- ③ 产品价格 ----
    print('-- ③ 产品价格(用于「产品持续大涨」):')
    for k in ('raw', 'pricecost'):
        v = d.get(k) or {}
        if isinstance(v, dict) and v.get('rows'):
            print('     %s.series = %s' % (k, v.get('series') or v.get('series_names')))
            for r in v['rows'][:2]:
                print('        %s' % (r,))
            print('        ...共 %d 行' % len(v['rows']))

    # ---- ④ 扣非/归母 ----
    fin = d.get('fin') or {}
    print('-- ④ 财务(用于「扣非持续大涨」「市值」「PB」):')
    for k in FIN_KEYS:
        v = fin.get(k)
        if isinstance(v, list):
            print('     %-7s = %s' % (k, v))
        elif v not in (None, '', [], {}):
            print('     %-7s = %s' % (k, strip(v)[:90]))
    print('     years = %s | prev = %s' % (fin.get('years'), fin.get('prev')))

    # ---- ⑤ 主营集中 ----
    bz = d.get('bizmix') or {}
    print('-- ⑤ 主营集中(bizmix):')
    for r in (bz.get('rows') or [])[:4]:
        print('        %s' % (r,))

    # ---- ⑧⑨⑩ 量价 ----
    vp = d.get('volprice') or {}
    print('-- ⑧⑨⑩ 量价(volprice):')
    if isinstance(vp, dict):
        for k in ('price_rows', 'rows'):
            if vp.get(k):
                print('     %s: %d 行' % (k, len(vp[k])))
                for r in vp[k][:3]:
                    print('        %s' % (r,))
    elif isinstance(vp, list):
        print('     list %d 行, 首行 %s' % (len(vp), vp[0] if vp else None))

    # ---- score 现状 ----
    sc = d.get('score') or {}
    print('-- 现有 score: %s' % (list(sc.keys()) if isinstance(sc, dict) else sc))
    if isinstance(sc, dict) and sc.get('notes'):
        for i, n in enumerate(sc['notes']):
            print('     note%02d: %s' % (i + 1, strip(n)[:90]))
    print()
