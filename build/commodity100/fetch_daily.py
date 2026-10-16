#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抓取商品日线序列（新浪财经期货接口）。

产出：data/daily/<code>.json  形如 {"code","name","market","unit","src","points":[[date,close],...]}
"""
import json, os, re, time, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, 'data', 'daily')
os.makedirs(OUT, exist_ok=True)

UA = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
      'Referer': 'https://finance.sina.com.cn/'}

# (code, 中文名, 市场标签, 单位, symbol, inner?)
SPEC = [
    # ---- 国内期货主力连续（上期所/能源中心/大商所/郑商所）----
    ('gold',     '黄金',   '沪金主连',  '元/克',     'AU0', True),
    ('silver',   '白银',   '沪银主连',  '元/千克',   'AG0', True),
    ('copper',   '铜',     '沪铜主连',  '元/吨',     'CU0', True),
    ('aluminum', '铝',     '沪铝主连',  '元/吨',     'AL0', True),
    ('zinc',     '锌',     '沪锌主连',  '元/吨',     'ZN0', True),
    ('lead',     '铅',     '沪铅主连',  '元/吨',     'PB0', True),
    ('tin',      '锡',     '沪锡主连',  '元/吨',     'SN0', True),
    ('nickel',   '镍',     '沪镍主连',  '元/吨',     'NI0', True),
    ('rubber',   '天然橡胶', '沪胶主连', '元/吨',    'RU0', True),
    ('crude',    '原油',   'SC原油主连', '元/桶',    'SC0', True),
    ('maize',    '玉米',   '连玉米主连', '元/吨',    'C0',  True),
    ('soybean',  '大豆',   '连豆一主连', '元/吨',    'A0',  True),
    ('cotton',   '棉花',   '郑棉主连',  '元/吨',     'CF0', True),
    ('sugar',    '白糖',   '郑糖主连',  '元/吨',     'SR0', True),
    ('urea',     '尿素',   '郑尿素主连', '元/吨',    'UR0', True),
    ('wheat',    '小麦',   '郑强麦主连', '元/吨',    'WH0', True),
    # ---- 国际期货连续（美元计价）----
    ('gold_i',   '黄金(COMEX)', 'COMEX金', '美元/盎司', 'GC',  False),
    ('silver_i', '白银(COMEX)', 'COMEX银', '美元/盎司', 'SI',  False),
    ('copper_i', '铜(COMEX)',   'COMEX铜', '美元/磅',   'HG',  False),
    ('crude_i',  '原油(WTI)',   'NYMEX',   '美元/桶',   'CL',  False),
    ('gas_i',    '天然气',      'NYMEX',   '美元/MMBtu','NG',  False),
    ('cotton_i', '棉花(ICE)',   'ICE',     '美分/磅',   'CT',  False),
    ('coffee_i', '咖啡(ICE)',   'ICE',     '美分/磅',   'KC',  False),
    ('aluminum_i','铝(LME)',    'LME',     '美元/吨',   'AHD', False),
    ('zinc_i',   '锌(LME)',     'LME',     '美元/吨',   'ZSD', False),
    ('lead_i',   '铅(LME)',     'LME',     '美元/吨',   'PBD', False),
    ('tin_i',    '锡(LME)',     'LME',     '美元/吨',   'SND', False),
    ('nickel_i', '镍(LME)',     'LME',     '美元/吨',   'NID', False),
]


def fetch(symbol, inner):
    svc = 'InnerFuturesNewService' if inner else 'GlobalFuturesService'
    url = (f'https://stock2.finance.sina.com.cn/futures/api/jsonp.php/'
           f'var%20t=/{svc}.getDailyKLine?symbol={symbol}')
    raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25)\
        .read().decode('utf-8', 'ignore')
    m = re.search(r'var t=\((\[.*\])\)', raw, re.S)
    if not m:
        return []
    arr = json.loads(m.group(1))
    if not arr:
        return []
    dk = 'date' if 'date' in arr[0] else 'd'
    ck = 'close' if 'close' in arr[0] else 'c'
    out = []
    for r in arr:
        try:
            out.append([r[dk], round(float(r[ck]), 4)])
        except (TypeError, ValueError):
            pass
    out.sort(key=lambda x: x[0])
    return out


summary = []
for code, name, market, unit, symbol, inner in SPEC:
    try:
        pts = fetch(symbol, inner)
        if not pts:
            print(f'  ✗ {code:11s} {symbol:5s} 无数据')
            continue
        rec = {'code': code, 'name': name, 'market': market, 'unit': unit,
               'src': '新浪财经·期货日线', 'symbol': symbol, 'points': pts}
        with open(os.path.join(OUT, code + '.json'), 'w', encoding='utf-8') as f:
            json.dump(rec, f, ensure_ascii=False, separators=(',', ':'))
        summary.append((code, name, len(pts), pts[0][0], pts[-1][0], market))
        print(f'  ✓ {code:11s} {symbol:5s} n={len(pts):5d}  {pts[0][0]} ~ {pts[-1][0]}')
    except Exception as e:
        print(f'  ✗ {code:11s} {symbol:5s} ERR {str(e)[:50]}')
    time.sleep(0.7)

print('\n=== 汇总 ===')
for s in summary:
    print(f'{s[0]:11s} {s[1]:14s} n={s[2]:5d} {s[3]}~{s[4]}  [{s[5]}]')
print(f'成功 {len(summary)}/{len(SPEC)}')
