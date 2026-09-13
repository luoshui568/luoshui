# -*- coding: utf-8 -*-
"""探测东财个股接口能否补齐「细分行业 / 地区 / 总资产 / 净资产 / 行业PE」"""
import json
import urllib.request
import contextlib
import io

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
FIELDS = ('f57,f58,f43,f116,f117,f162,f163,f164,f167,f168,f169,f170,f173,'
          'f183,f184,f185,f186,f187,f188,f189,f190,f191,f192,f193,f194,f195,'
          'f127,f128,f102,f103,f92,f105,f55,f9,f23,f20,f21,f22,f25,f62,f66')


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode('utf-8', 'ignore')


def one(secid, label):
    url = 'https://push2.eastmoney.com/api/qt/stock/get?secid=%s&fields=%s' % (secid, FIELDS)
    try:
        j = json.loads(get(url))
        d = (j.get('data') or {})
        out.append('--- %s  secid=%s  返回 %d 个字段 ---' % (label, secid, len(d)))
        for k in sorted(d.keys(), key=lambda x: int(x[1:])):
            v = d[k]
            if v not in (None, 0, '', '-'):
                out.append('   %-6s = %s' % (k, v))
    except Exception as e:
        out.append('--- %s 失败: %s' % (label, e))
    out.append('')


out = []
out.append('=' * 70)
out.append('[A] 东财个股接口')
out.append('=' * 70)
one('1.600459', '贵研铂业(沪)')
one('0.000807', '云铝股份(深)')
one('0.002317', '众生药业(深)')

out.append('=' * 70)
out.append('[B] 东财行业板块列表（找行业PE）')
out.append('=' * 70)
try:
    url = ('https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=6&po=1&np=1'
           '&fs=m:90+t:2&fields=f12,f14,f3,f9,f23,f20,f102,f103,f104,f105')
    j = json.loads(get(url))
    diff = ((j.get('data') or {}).get('diff') or {})
    for k in diff:
        out.append('   ' + json.dumps(diff[k], ensure_ascii=False))
except Exception as e:
    out.append('   失败: %s' % e)
out.append('')

txt = '\n'.join(out)
with open('_em_out.txt', 'w', encoding='utf-8') as f:
    f.write(txt)
print('written', len(txt))
