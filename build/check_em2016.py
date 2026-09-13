# -*- coding: utf-8 -*-
"""核对 EM2016 取值与「铝」板块"""
import gzip
import json
import urllib.parse
import urllib.request
import zlib

FULL = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Accept': '*/*', 'Accept-Encoding': 'gzip, deflate', 'Connection': 'close',
}
OUT = []


def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=FULL), timeout=30) as r:
        raw = r.read()
        ce = r.headers.get('Content-Encoding')
        if ce == 'gzip':
            raw = gzip.decompress(raw)
        elif ce == 'deflate':
            try:
                raw = zlib.decompress(raw)
            except Exception:
                raw = zlib.decompress(raw, -zlib.MAX_WBITS)
        return raw.decode('utf-8', 'replace')


codes = ['600459', '601600', '000807', '601958', '600547', '603993', '000831',
         '000970', '002378', '000630', '601168', '002532']
f = '(SECURITY_CODE in ("' + '","'.join(codes) + '"))'
url = ('https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_F10_BASIC_ORGINFO'
       '&columns=SECURITY_CODE,SECURITY_NAME_ABBR,EM2016,PROVINCE'
       '&filter=' + urllib.parse.quote(f) + '&pageNumber=1&pageSize=200&source=HSF10&client=PC')
OUT.append('== EM2016（含第三段=细分行业）==')
for x in (json.loads(fetch(url)).get('result') or {}).get('data', []):
    seg = str(x.get('EM2016') or '').split('-')
    OUT.append('  %s %-8s EM2016=%-34s 第三段=%-12s 省=%s'
               % (x['SECURITY_CODE'], x['SECURITY_NAME_ABBR'], x.get('EM2016'),
                  seg[-1], x.get('PROVINCE')))

# 全部板块里找「铝」相关
boards = {}
for pn in range(1, 6):
    u = ('https://push2delay.eastmoney.com/api/qt/clist/get?po=1&np=1&fltt=2&invt=2&fid=f3'
         '&pn=%d&pz=100&fs=m:90+t:2+f:!50&fields=f12,f14,f9' % pn)
    d = (json.loads(fetch(u)).get('data') or {})
    for x in (d.get('diff') or []):
        boards[x['f12']] = x
OUT.append('\n== 板块总数 %d ==' % len(boards))
OUT.append('-- 名称含「铝 / 铜 / 锌 / 铅 / 磁」的板块 --')
for c, b in sorted(boards.items()):
    if any(k in (b.get('f14') or '') for k in ['铝', '铜', '锌', '铅', '磁']):
        OUT.append('  %s %-14s PE=%s' % (c, b['f14'], b.get('f9')))

open(r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38\build\_exist_check.txt', 'w',
     encoding='utf-8').write('\n'.join(OUT))
print('OK')
