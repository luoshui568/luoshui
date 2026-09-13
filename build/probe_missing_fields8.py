# -*- coding: utf-8 -*-
"""第八轮：push2delay 能否给总资产 + 云函数能否被前端 HTTP 触发"""
import gzip
import json
import urllib.request
import zlib

OUT = []
FULL = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Accept': '*/*', 'Accept-Language': 'zh-CN,zh;q=0.9',
    'Accept-Encoding': 'gzip, deflate', 'Connection': 'close',
}


def fetch(url, headers=None):
    h = dict(FULL)
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        ce = r.headers.get('Content-Encoding')
        if ce == 'gzip':
            raw = gzip.decompress(raw)
        elif ce == 'deflate':
            try:
                raw = zlib.decompress(raw)
            except Exception:
                raw = zlib.decompress(raw, -zlib.MAX_WBITS)
        return raw.decode('utf-8', 'replace'), dict(r.headers)


# 1. push2delay 全字段扫描，找总资产
flds = ','.join('f%d' % i for i in range(1, 210))
try:
    txt, hdr = fetch('https://push2delay.eastmoney.com/api/qt/stock/get?secid=1.600459&fields=' + flds)
    OUT.append('[push2delay 全字段] len=%d CORS=%s' % (len(txt), hdr.get('Access-Control-Allow-Origin')))
    try:
        d = json.loads(txt).get('data') or {}
        OUT.append('返回字段 %d 个:' % len(d))
        for k in sorted(d.keys(), key=lambda x: int(x[1:])):
            OUT.append('   %s = %s' % (k, d[k]))
    except Exception as e:
        OUT.append('解析失败 %s: %s' % (e, txt[:500]))
except Exception as e:
    OUT.append('[push2delay 全字段] !! %s' % e)

# 2. 多只股票确认 f127（行业）/ f128（地域）粒度
OUT.append('\n---- f127 / f128 粒度确认 ----')
for secid, nm in [('1.600459', '贵研铂业'), ('1.600547', '山东黄金'), ('1.601600', '中国铝业'),
                  ('0.000807', '云铝股份'), ('1.603993', '洛阳钼业'), ('0.000831', '中国稀土'),
                  ('0.000970', '中科三环'), ('1.601958', '金钼股份'), ('0.002378', '章源钨业'),
                  ('0.000630', '铜陵有色')]:
    try:
        txt, _ = fetch('https://push2delay.eastmoney.com/api/qt/stock/get?secid=%s'
                       '&fields=f57,f58,f127,f128,f9,f20,f23' % secid)
        d = json.loads(txt).get('data') or {}
        OUT.append('  %-8s %-10s 行业(f127)=%-12s 地域(f128)=%-14s PE(f9)=%s'
                   % (secid, nm, d.get('f127'), d.get('f128'), d.get('f9')))
    except Exception as e:
        OUT.append('  %s !! %s' % (nm, e))

# 3. 云函数能否被 HTTP 触发（用发布密钥）
OUT.append('\n---- 云函数 HTTP 触发测试 ----')
try:
    cfg = json.load(open(r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38\build\cloud.json',
                         encoding='utf-8'))
    env = cfg.get('envId') or cfg.get('env_id')
    key = cfg.get('key') or cfg.get('publishableKey') or cfg.get('apiKey')
    OUT.append('envId=%s keyLen=%s' % (env, len(key or '')))
    for u in ['https://%s.api.tcloudbasegateway.com/v1/functions/wb_sync_quotes' % env,
              'https://%s.service.tcloudbase.com/wb_sync_quotes' % env,
              'https://%s.service.tcloudbase.com/v1/functions/wb_sync_quotes' % env]:
        try:
            txt, hdr = fetch(u, headers={'Authorization': 'Bearer ' + key,
                                         'Content-Type': 'application/json'})
            OUT.append('  OK  %s\n      CORS=%s\n      %s'
                       % (u, hdr.get('Access-Control-Allow-Origin'), txt[:300]))
        except Exception as e:
            OUT.append('  !!  %s -> %s' % (u, e))
except Exception as e:
    OUT.append('读 cloud.json 失败: %s' % e)

open(r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38\build\_src_probe8.txt', 'w',
     encoding='utf-8').write('\n'.join(OUT))
print('OK')
