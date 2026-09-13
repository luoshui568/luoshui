# -*- coding: utf-8 -*-
"""第七轮：翻页取全部行业板块 PE，确认能命中 BK1027 / BK1287"""
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
BASE = ('https://push2delay.eastmoney.com/api/qt/clist/get?po=1&np=1&fltt=2&invt=2'
        '&fs=m:90+t:2+f:!50&fields=f12,f14,f9,f20,f3')


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


boards = {}
pages = 0
for pn in range(1, 8):
    url = BASE + '&fid=f3&pn=%d&pz=100' % pn
    try:
        d = json.loads(fetch(url)).get('data') or {}
    except Exception as e:
        OUT.append('第 %d 页失败: %s' % (pn, e))
        break
    diff = d.get('diff') or []
    pages += 1
    for x in diff:
        boards[x.get('f12')] = x
    OUT.append('第 %d 页: total=%s 本页=%d 累计=%d' % (pn, d.get('total'), len(diff), len(boards)))
    if len(diff) < 100:
        break

OUT.append('\n板块总数（去重后）=%d  共翻 %d 页' % (len(boards), pages))

# 用户可能用到的板块
for code in ['BK1027', 'BK1287', 'BK1033', 'BK1032', 'BK1028', 'BK1036', 'BK0478',
             'BK1015', 'BK1029', 'BK0736', 'BK0538', 'BK0459']:
    b = boards.get(code)
    OUT.append('  %s → %s' % (code, json.dumps(b, ensure_ascii=False) if b else '未命中'))

OUT.append('\n—— 名字含「金属/贵金属/黄金/铝/稀土/钨/钼/铜」的板块 ——')
for c, b in sorted(boards.items()):
    nm = b.get('f14') or ''
    if any(k in nm for k in ['金属', '贵金属', '黄金', '稀土', '钨', '钼', '铜', '锌', '铅']):
        OUT.append('  %s %-14s PE(f9)=%-10s 总市值(f20)=%s' % (c, nm, b.get('f9'), b.get('f20')))

open(r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38\build\_src_probe7.txt', 'w',
     encoding='utf-8').write('\n'.join(OUT))
print('OK')
