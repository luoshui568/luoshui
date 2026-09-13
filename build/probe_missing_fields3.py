# -*- coding: utf-8 -*-
"""第三轮探测：专攻「行业PE」，顺带试 push2 的编号域名变体"""
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


def sec(label, url, headers=None, enc='utf-8', keep=1400):
    OUT.append('\n' + '=' * 72)
    OUT.append('[%s]' % label)
    try:
        h = dict(FULL)
        if headers:
            h.update(headers)
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=20) as r:
            raw, hdr = r.read(), dict(r.headers)
        txt = raw.decode(enc, 'replace')
        OUT.append('--- len=%d CORS=%s' % (len(txt), hdr.get('Access-Control-Allow-Origin', '无')))
        OUT.append(txt[:keep])
    except Exception as e:
        OUT.append('!! 失败: %s' % e)


# ---- push2 编号域名变体（东财负载均衡） ----
for n in ['', '1.', '7.', '82.']:
    sec('push2 变体 %s' % (n or 'bare'),
        'https://%spush2.eastmoney.com/api/qt/stock/get?secid=1.600459'
        '&fields=f57,f58,f127,f100,f102' % n,
        headers={'Referer': 'https://quote.eastmoney.com/'})

sec('push2his', 'https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=1.600459'
                '&fields1=f1&fields2=f51,f53&klt=101&fqt=1&end=20500101&lmt=2')

# ---- 东财 datacenter 行业板块估值（猜测 reportName） ----
for rn in ['RPT_VALUEBOARD', 'RPT_BOARD_VALUATION', 'RPT_INDUSTRY_VALUATION',
           'RPT_VALUEANALYSIS_DET']:
    sec('datacenter %s' % rn,
        'https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=%s'
        '&columns=ALL&pageNumber=1&pageSize=1' % rn)

# ---- 东财 F10 行业对比 / 同行比较 ----
sec('东财 F10 行业对比 IndustryAnalysis',
    'https://emweb.securities.eastmoney.com/PC_HSF10/IndustryAnalysis/PageAjax?code=SH600459')

# ---- 同花顺 行业指数（带 PE） ----
sec('同花顺 行业板块列表 ajax',
    'https://q.10jqka.com.cn/thshy/detail/field/199112/order/desc/page/1/ajax/1/',
    headers={'Referer': 'https://q.10jqka.com.cn/thshy/'}, enc='gbk')

sec('同花顺 F10 行业对比 api',
    'https://basic.10jqka.com.cn/api/stock/hangye/600459/',
    headers={'Referer': 'https://basic.10jqka.com.cn/'}, enc='gbk')

# ---- 腾讯：板块参数换个 sort_type 找 PE ----
sec('腾讯板块 sort_type=zdf',
    'https://proxy.finance.qq.com/cgi/cgi-bin/rank/pt/getRank'
    '?board_type=hy&sort_type=zdf&direct=down&offset=0&count=3',
    headers={'Referer': 'https://gu.qq.com/'})

# ---- 中证指数 / 申万 行业 PE ----
sec('中证指数 行业市盈率',
    'https://www.csindex.com.cn/csindex-home/exportExcel/indices-pe-pb')

open(r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38\build\_src_probe3.txt', 'w',
     encoding='utf-8').write('\n'.join(OUT))
print('OK')
