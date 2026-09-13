# -*- coding: utf-8 -*-
"""核对 wb_stocks 的基本面字段落库情况"""
import json
import urllib.request

BASE = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
cfg = json.load(open(BASE + r'\build\cloud.json', encoding='utf-8'))
env = cfg.get('envId') or cfg.get('env_id')
key = cfg.get('key') or cfg.get('publishableKey') or cfg.get('apiKey')
REST = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % env
H = {'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'}

cols = ('code,name,ind_pe,sub_industry,total_assets,net_assets,region,'
        'pe_ttm,pe_fwd,pb,price,chg_pct,mkt_cap,quote_date,info_at,lock_fields')
req = urllib.request.Request(REST + 'wb_stocks?select=' + cols + '&order=code.asc', headers=H)
rows = json.load(urllib.request.urlopen(req, timeout=30))

out = ['共 %d 条' % len(rows), '']
hdr = ['字段', '贵研铂业', '中国铝业', '云铝股份', '其他']
keys = ['code', 'name', 'ind_pe', 'sub_industry', 'total_assets', 'net_assets',
        'region', 'pe_ttm', 'pe_fwd', 'pb', 'price', 'chg_pct', 'mkt_cap',
        'quote_date', 'info_at', 'lock_fields']
byname = {r['code']: r for r in rows}
order = ['600459', '601600', '000807'] + [c for c in byname if c not in ('600459', '601600', '000807')]

for k in keys:
    vals = []
    for c in order:
        r = byname.get(c)
        v = '—' if r is None else r.get(k)
        if isinstance(v, str) and len(v) > 22:
            v = v[:22] + '…'
        vals.append(v)
    out.append('%-14s | %-14s | %-14s | %-14s | %s' % (k, vals[0], vals[1], vals[2],
                                                        vals[3] if len(vals) > 3 else ''))

out.append('')
out.append('—— 逐条明细 ——')
for r in rows:
    out.append(json.dumps(r, ensure_ascii=False))

open(BASE + r'\build\_stock_check.txt', 'w', encoding='utf-8').write('\n'.join(out))
print('OK %d rows' % len(rows))
