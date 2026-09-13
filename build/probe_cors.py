# -*- coding: utf-8 -*-
"""探测行情接口的 CORS 响应头 —— 决定前端能否直连刷新"""
import urllib.request
import contextlib
import io

UA = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Origin': 'https://fdels568-d7g1d8o3y90a80cd7-1483776268.tcloudbaseapp.com',
}


def head(url, label):
    out.append('=' * 66)
    out.append('[%s] %s' % (label, url))
    out.append('=' * 66)
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=12) as r:
            hdrs = dict(r.headers)
            for k in ('Access-Control-Allow-Origin', 'Access-Control-Allow-Methods',
                      'Access-Control-Allow-Headers', 'Content-Type',
                      'Content-Encoding', 'Server', 'Content-Length'):
                out.append('  %-32s : %s' % (k, hdrs.get(k, '(缺失)')))
            body = r.read(120)
            out.append('  前 120 字节: %r' % body[:120])
    except Exception as e:
        out.append('  请求失败: %s' % e)
    out.append('')


out = []
head('https://qt.gtimg.cn/q=sh600459,sz000833', '腾讯行情快照')
head('https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh600459,day,,,10,qfq', '腾讯日K')
head('https://hq.sinajs.cn/list=sh600459', '新浪行情(已知要 Referer)')
head('https://push2.eastmoney.com/api/qt/stock/get?secid=1.600459&fields=f43,f57,f58,f169,f170,f116,f117,f162,f167,f173', '东财单股快照')
head('https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=5&fs=m:1+t:2&fields=f12,f13,f14,f2,f3', '东财列表')

txt = '\n'.join(out)
with open('_cors_out.txt', 'w', encoding='utf-8') as f:
    f.write(txt)
print('written', len(txt))
