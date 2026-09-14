# -*- coding: utf-8 -*-
"""拉腾讯行情，补齐流通市值 / 股本等研报需要的字段"""
import urllib.request, json, io, os

QI = {
    'name': 1, 'code': 2, 'price': 3, 'quote_time': 30, 'change': 31, 'chg_pct': 32,
    'amount_wan': 37, 'pe_ttm': 39, 'float_cap_yi': 44, 'mkt_cap_yi': 45, 'pb': 46,
    'pe_fwd': 52, 'pe_lyr': 53, 'chg_ytd': 62, 'chg_5d': 63, 'div_yield': 64,
    'high_52w': 67, 'low_52w': 68, 'chg_10d': 69, 'chg_20d': 70, 'chg_60d': 71,
    'float_shares': 72, 'total_shares': 73,
}
CODES = [('sz', '000830'), ('sz', '000731'), ('sz', '002237'), ('sh', '600459')]
url = 'https://qt.gtimg.cn/q=' + ','.join(p + c for p, c in CODES)

req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
op = None
try:
    txt = urllib.request.urlopen(req, timeout=25).read().decode('gbk', 'replace')
    via = '直连'
except Exception as e:
    px = urllib.request.build_opener(urllib.request.ProxyHandler(
        {'https': 'http://127.0.0.1:7892', 'http': 'http://127.0.0.1:7892'}))
    txt = px.open(req, timeout=25).read().decode('gbk', 'replace')
    via = '代理7892'
print('数据源: 腾讯行情 qt.gtimg.cn（%s）' % via)
print()

out = {}
for line in txt.split('\n'):
    i = line.find('="')
    if i < 0:
        continue
    vals = line[i + 2:].rstrip('";\r\n ').split('~')
    if len(vals) < 45 or not vals[QI['name']]:
        continue

    def n(k):
        try:
            return float(vals[QI[k]])
        except Exception:
            return None

    d = {k: n(k) for k in QI if k not in ('name', 'code', 'quote_time')}
    d['name'] = vals[QI['name']]
    d['code'] = vals[QI['code']]
    qt = vals[QI['quote_time']]
    d['quote_date'] = '%s-%s-%s' % (qt[0:4], qt[4:6], qt[6:8])
    out[d['code']] = d
    print('%-8s %-10s 现价=%-7s 涨跌=%-7s%% 总市值=%-9s 流通市值=%-9s PE=%-7s PB=%-6s 股息=%-5s%%'
          % (d['code'], d['name'], d['price'], d['chg_pct'], d['mkt_cap_yi'],
             d['float_cap_yi'], d['pe_ttm'], d['pb'], d['div_yield']))
    print('         年初=%s%%  10/20/60日=%s/%s/%s%%  总股本=%s亿  流通股本=%s亿  行情日=%s'
          % (d['chg_ytd'], d['chg_10d'], d['chg_20d'], d['chg_60d'],
             d['total_shares'], d['float_shares'], d['quote_date']))

p = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38\build\seed\quotes_latest.json'
io.open(p, 'w', encoding='utf-8').write(json.dumps(out, ensure_ascii=False, indent=1))
print()
print('已写出', p)
