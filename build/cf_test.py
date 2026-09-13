# -*- coding: utf-8 -*-
"""云函数 wb_sync_quotes 的落库验证：insert -> (调函数) -> check -> clean"""
import os
import sys
import json
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, 'cloud.json'), encoding='utf-8'))
REST = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']
KEY = CFG['key']

TESTS = [
    {'id': 'st_600459', 'code': '600459', 'exchange': 'sh', 'name': '', 'sort': 99},
    {'id': 'st_601600', 'code': '601600', 'exchange': 'sh', 'name': '', 'sort': 99},
    {'id': 'st_000807', 'code': '000807', 'exchange': 'sz', 'name': '', 'sort': 99},
]
CODES = '600459,601600,000807'


def call(path, method='GET', body=None, prefer=None):
    h = {'Authorization': 'Bearer ' + KEY}
    data = None
    if body is not None:
        data = json.dumps(body).encode('utf-8')
        h['Content-Type'] = 'application/json'
    if prefer:
        h['Prefer'] = prefer
    req = urllib.request.Request(REST + path, data=data, headers=h, method=method)
    with urllib.request.urlopen(req, timeout=30) as r:
        t = r.read().decode('utf-8', 'ignore')
        return (json.loads(t) if t.strip() else None)


cmd = sys.argv[1] if len(sys.argv) > 1 else 'check'

if cmd == 'insert':
    call('wb_stocks?on_conflict=code', 'POST', TESTS, 'resolution=merge-duplicates,return=minimal')
    print('已插入测试标的：' + CODES)

elif cmd == 'check':
    rows = call('wb_stocks?select=*&code=in.(%s)&order=code.asc' % CODES)
    print('=' * 74)
    print('云函数落库检查 · %d 条' % len(rows or []))
    print('=' * 74)
    need = ['name', 'chg_pct', 'price', 'amount', 'pe_fwd', 'pe_ttm', 'pb',
            'div_yield', 'mkt_cap', 'chg_ytd', 'chg_10d', 'chg_20d', 'chg_60d', 'quote_date']
    allok = True
    for r in (rows or []):
        filled = [k for k in need if r.get(k) not in (None, '')]
        if len(filled) != len(need):
            allok = False
        print('\n[%s] %s %s  已填 %d/%d' % ('OK ' if len(filled) == len(need) else 'BAD',
                                            r.get('code'), r.get('name'), len(filled), len(need)))
        print('     现价=%s  涨幅=%s  成交额=%s  总市值=%s' % (r.get('price'), r.get('chg_pct'),
                                                          r.get('amount'), r.get('mkt_cap')))
        print('     PE动=%s  PE-TTM=%s  PB=%s  股息率=%s' % (r.get('pe_fwd'), r.get('pe_ttm'),
                                                        r.get('pb'), r.get('div_yield')))
        print('     年初至今=%s  10/20/60日=%s / %s / %s  行情日=%s' % (
            r.get('chg_ytd'), r.get('chg_10d'), r.get('chg_20d'), r.get('chg_60d'), r.get('quote_date')))
        if len(filled) != len(need):
            print('     缺失：%s' % [k for k in need if r.get(k) in (None, '')])
    print('\n结论：' + ('云函数已成功把行情写入数据库 ✓' if allok and rows else '尚未落库或字段不全 ✗'))

elif cmd == 'clean':
    print('（anon 无 DELETE 权限，请用 SQL 清理）剩余：%d' % len(call('wb_stocks?select=code&code=in.(%s)' % CODES) or []))
