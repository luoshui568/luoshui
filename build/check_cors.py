# -*- coding: utf-8 -*-
"""带 Origin 头重测 CORS：很多服务端只在有 Origin 时才回 ACAO"""
import gzip
import urllib.parse
import urllib.request
import zlib

ORIGINS = ['https://fdels568-d7g1d8o3y90a80cd7-1483776268.tcloudbaseapp.com',
           'http://127.0.0.1:8901', 'null']
URLS = {
    'datacenter': 'https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_F10_BASIC_ORGINFO'
                  '&columns=SECURITY_CODE,EM2016,PROVINCE&filter='
                  + urllib.parse.quote('(SECURITY_CODE in ("600459","601600"))')
                  + '&pageNumber=1&pageSize=10&source=HSF10&client=PC',
    'push2delay': 'https://push2delay.eastmoney.com/api/qt/stock/get?secid=1.600459&fields=f57,f58,f127,f128,f198',
}
OUT = []


def probe(label, url, origin):
    h = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Accept': '*/*', 'Accept-Encoding': 'gzip, deflate', 'Connection': 'close',
        'Origin': origin,
    }
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=25) as r:
            hd = dict(r.headers)
        acao = hd.get('Access-Control-Allow-Origin', '无')
        acac = hd.get('Access-Control-Allow-Credentials', '-')
        acam = hd.get('Access-Control-Allow-Methods', '-')
        vary = hd.get('Vary', '-')
        OUT.append('  [%s] Origin=%s' % (label, origin))
        OUT.append('        ACAO=%s | Credentials=%s | Methods=%s | Vary=%s' % (acao, acac, acam, vary))
    except Exception as e:
        OUT.append('  [%s] Origin=%s  !! %s' % (label, origin, e))


for label, url in URLS.items():
    OUT.append('\n===== %s =====' % label)
    for o in ORIGINS:
        probe(label, url, o)
    probe(label, url, '')          # 不带 Origin 对照

open(r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38\build\_cors_check.txt', 'w',
     encoding='utf-8').write('\n'.join(OUT))
print('OK')
