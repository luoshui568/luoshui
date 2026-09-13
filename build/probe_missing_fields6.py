# -*- coding: utf-8 -*-
"""第六轮：确认能否「批量」拿到 96 只的 行业/地区/总资产/行业PE"""
import gzip
import json
import urllib.request
import urllib.parse

OUT = []
FULL = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Accept': '*/*', 'Accept-Language': 'zh-CN,zh;q=0.9',
    'Accept-Encoding': 'gzip, deflate', 'Connection': 'close',
}
Q = urllib.parse.quote
CODES = ['600459', '601600', '000807', '600547', '603993', '000831', '000970',
         '002532', '601958', '002378', '000630']


def fetch(url, headers=None):
    h = dict(FULL)
    if headers:
        h.update(headers)
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=30) as r:
        raw = r.read()
        if r.headers.get('Content-Encoding') == 'gzip':
            raw = gzip.decompress(raw)
        elif r.headers.get('Content-Encoding') == 'deflate':
            raw = zlib_decompress(raw)
        return raw.decode('utf-8', 'replace')


def zlib_decompress(b):
    import zlib
    try:
        return zlib.decompress(b)
    except Exception:
        return zlib.decompress(b, -zlib.MAX_WBITS)


def sec(label, url, headers=None, keep=2000):
    OUT.append('\n' + '=' * 72)
    OUT.append('[%s]' % label)
    try:
        txt = fetch(url, headers)
        OUT.append('--- len=%d' % len(txt))
        OUT.append(txt[:keep])
    except Exception as e:
        OUT.append('!! 失败: %s' % e)


# 1. push2delay 批量（ulist.np）
secids = ','.join(('1.' if c[0] == '6' else '0.') + c for c in CODES)
sec('push2delay ulist.np 批量个股',
    'https://push2delay.eastmoney.com/api/qt/ulist.np/get?secids=' + secids
    + '&fields=f12,f13,f14,f127,f128,f162,f164,f167,f9,f20,f23,f173')

# 2. datacenter 公司概况 —— 能否 in 批量
sec('datacenter BASIC_ORGINFO in 批量',
    'https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_F10_BASIC_ORGINFO'
    '&columns=SECURITY_CODE,SECURITY_NAME_ABBR,EM2016,PROVINCE,REG_ADDRESS'
    '&filter=' + Q('(SECURITY_CODE in ("600459","601600","000807"))')
    + '&pageNumber=1&pageSize=10&source=HSF10&client=PC')

# 3. datacenter 资产负债表 —— in 批量 + 最新报告期
sec('datacenter BALANCE in 批量',
    'https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_DMSK_FN_BALANCE'
    '&columns=SECURITY_CODE,SECURITY_NAME_ABBR,INDUSTRY_CODE,INDUSTRY_NAME,REPORT_DATE,TOTAL_ASSETS'
    '&filter=' + Q('(SECURITY_CODE in ("600459","601600","000807"))(REPORT_DATE=\'2026-06-30\')')
    + '&pageNumber=1&pageSize=10&source=WEB&client=WEB')

# 4. 行业板块列表（一次性拿全部板块 PE）—— 找 BK1027
txt = fetch('https://push2delay.eastmoney.com/api/qt/clist/get?pn=1&pz=600&po=1&np=1'
            '&fltt=2&invt=2&fid=f3&fs=m:90+t:2+f:!50&fields=f12,f14,f9,f20,f3')
OUT.append('\n' + '=' * 72)
OUT.append('[行业板块列表 pz=600]')
try:
    d = json.loads(txt)['data']
    OUT.append('--- 板块总数 total=%s  实际返回=%d' % (d.get('total'), len(d.get('diff') or [])))
    hit = [x for x in (d.get('diff') or []) if x.get('f12') == 'BK1027']
    OUT.append('BK1027 命中: %s' % json.dumps(hit, ensure_ascii=False))
    for kw in ['贵金属', '铝', '黄金', '稀土', '钨', '钼', '铜', '小金属']:
        m = [x for x in (d.get('diff') or []) if x.get('f14') == kw]
        OUT.append('  板块「%s」→ %s' % (kw, json.dumps(m, ensure_ascii=False)))
except Exception as e:
    OUT.append('!! 解析失败 %s / %s' % (e, txt[:400]))

open(r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38\build\_src_probe6.txt', 'w',
     encoding='utf-8').write('\n'.join(OUT))
print('OK')
