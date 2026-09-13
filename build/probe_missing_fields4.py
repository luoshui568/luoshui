# -*- coding: utf-8 -*-
"""第四轮：push2his / push2delay 能否查板块 PE 与个股扩展字段"""
import urllib.request

OUT = []
FULL = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Accept': '*/*', 'Accept-Language': 'zh-CN,zh;q=0.9',
    'Accept-Encoding': 'identity', 'Connection': 'close',
    'Referer': 'https://quote.eastmoney.com/',
}


def sec(label, url, keep=1500):
    OUT.append('\n' + '=' * 72)
    OUT.append('[%s] %s' % (label, url[:170]))
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=FULL), timeout=20) as r:
            raw, hdr = r.read(), dict(r.headers)
        txt = raw.decode('utf-8', 'replace')
        OUT.append('--- len=%d CORS=%s' % (len(txt), hdr.get('Access-Control-Allow-Origin', '无')))
        OUT.append(txt[:keep])
    except Exception as e:
        OUT.append('!! 失败: %s' % e)


# 个股在 push2his 上能否取扩展字段
sec('push2his stock/get 个股',
    'https://push2his.eastmoney.com/api/qt/stock/get?secid=1.600459'
    '&fields=f57,f58,f100,f102,f127,f128,f9,f23,f162,f164,f167')

# 板块自身行情（secid=90.BKxxxx，f9=市盈率 f23=市净率）
sec('push2his stock/get 板块 BK1027',
    'https://push2his.eastmoney.com/api/qt/stock/get?secid=90.BK1027'
    '&fields=f57,f58,f9,f23,f43,f104,f105,f106,f114,f115,f162,f164,f167,f168')

# 板块成分（fs=b:BK1027）
sec('push2his clist 板块成分',
    'https://push2his.eastmoney.com/api/qt/clist/get?pn=1&pz=3&po=1&np=1&fltt=2&invt=2'
    '&fid=f3&fs=b:BK1027&fields=f12,f14,f9,f23,f2,f3')

# 行业板块列表（找 PE）
sec('push2his clist 行业板块列表',
    'https://push2his.eastmoney.com/api/qt/clist/get?pn=1&pz=5&po=1&np=1&fltt=2&invt=2'
    '&fid=f3&fs=m:90+t:2+f:!50&fields=f12,f14,f9,f23,f3')

# 延迟行情域名
sec('push2delay stock/get',
    'https://push2delay.eastmoney.com/api/qt/stock/get?secid=1.600459'
    '&fields=f57,f58,f100,f102,f127,f9,f23')

sec('push2delay 板块',
    'https://push2delay.eastmoney.com/api/qt/stock/get?secid=90.BK1027&fields=f57,f58,f9,f23')

open(r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38\build\_src_probe4.txt', 'w',
     encoding='utf-8').write('\n'.join(OUT))
print('OK')
