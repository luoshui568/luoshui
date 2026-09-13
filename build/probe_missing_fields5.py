# -*- coding: utf-8 -*-
"""第五轮：push2delay 的 clist + 东财行业成分，确定「行业PE」算法可行性"""
import json
import urllib.request
import urllib.parse

OUT = []
FULL = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Accept': '*/*', 'Accept-Language': 'zh-CN,zh;q=0.9',
    'Accept-Encoding': 'identity', 'Connection': 'close',
}
Q = urllib.parse.quote


def fetch(url, headers=None, enc='utf-8'):
    h = dict(FULL)
    if headers:
        h.update(headers)
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=25) as r:
        return r.read().decode(enc, 'replace')


def sec(label, url, headers=None, enc='utf-8', keep=1600):
    OUT.append('\n' + '=' * 72)
    OUT.append('[%s]' % label)
    try:
        txt = fetch(url, headers, enc)
        OUT.append('--- len=%d' % len(txt))
        OUT.append(txt[:keep])
    except Exception as e:
        OUT.append('!! 失败: %s' % e)


# 1. push2delay clist 板块成分（含 PE f9 / 总市值 f20 / PB f23）
sec('push2delay clist 小金属成分',
    'https://push2delay.eastmoney.com/api/qt/clist/get?pn=1&pz=5&po=1&np=1&fltt=2&invt=2'
    '&fid=f3&fs=b:BK1027&fields=f12,f14,f2,f3,f9,f20,f23')

# 2. push2delay clist 行业板块列表（板块自身 PE）
sec('push2delay clist 行业板块',
    'https://push2delay.eastmoney.com/api/qt/clist/get?pn=1&pz=5&po=1&np=1&fltt=2&invt=2'
    '&fid=f3&fs=m:90+t:2+f:!50&fields=f12,f14,f2,f3,f9,f20,f23')

# 3. push2delay 板块行情（f9=PE f20=总市值）
sec('push2delay 板块明细',
    'https://push2delay.eastmoney.com/api/qt/stock/get?secid=90.BK1027'
    '&fields=f57,f58,f9,f20,f23,f114,f115,f173')

# 4. push2delay 个股全字段
sec('push2delay 个股全字段',
    'https://push2delay.eastmoney.com/api/qt/stock/get?secid=1.600459'
    '&fields=f57,f58,f100,f101,f102,f103,f127,f128,f129,f9,f20,f23,f162,f164,f167,f173')

# 5. 东财 datacenter 按行业代码查成分股
sec('datacenter 按 INDUSTRY_CODE 查成分',
    'https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_DMSK_FN_BALANCE'
    '&columns=SECURITY_CODE,SECURITY_NAME_ABBR,INDUSTRY_NAME,TOTAL_ASSETS'
    '&filter=' + Q('(INDUSTRY_CODE="1027")(REPORT_DATE=\'2026-06-30\')')
    + '&pageNumber=1&pageSize=8&source=WEB&client=WEB')

# 6. 多只股票的公司概况，确认 INDUSTRY_NAME / EM2016 / PROVINCE 粒度
codes = [('601600', 'SH'), ('600547', 'SH'), ('603993', 'SH'), ('000831', 'SZ'),
         ('601958', 'SH'), ('000807', 'SZ'), ('000970', 'SZ'), ('002532', 'SZ')]
for c, mk in codes:
    sec('公司概况 %s%s' % (mk, c),
        'https://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/PageAjax?code=%s%s' % (mk, c),
        keep=700)

open(r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38\build\_src_probe5.txt', 'w',
     encoding='utf-8').write('\n'.join(OUT))
print('OK')
