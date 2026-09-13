# -*- coding: utf-8 -*-
"""第二轮探测：总资产 / 行业PE，并重试 push2（换完整浏览器头）"""
import json
import urllib.request
import urllib.parse

OUT = []

FULL = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Accept': '*/*',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Accept-Encoding': 'identity',
    'Connection': 'close',
}


def get(url, headers=None, enc='utf-8'):
    h = dict(FULL)
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=25) as r:
        raw = r.read()
        hdr = dict(r.headers)
    return raw.decode(enc, 'replace'), hdr


def sec(label, url, headers=None, enc='utf-8', keep=2200):
    OUT.append('\n' + '=' * 72)
    OUT.append('[%s]' % label)
    OUT.append(url[:200])
    try:
        txt, hdr = get(url, headers, enc)
        OUT.append('--- len=%d  CORS=%s' % (len(txt), hdr.get('Access-Control-Allow-Origin', '无')))
        OUT.append(txt[:keep])
    except Exception as e:
        OUT.append('!! 失败: %s' % e)


Q = urllib.parse.quote

# ---- A. push2 重试（完整头） ----
sec('push2 stock/get（完整头重试）',
    'https://push2.eastmoney.com/api/qt/stock/get?secid=1.600459'
    '&fields=f57,f58,f84,f85,f116,f117,f127,f128,f162,f163,f164,f167,f173,f183,f184',
    headers={'Referer': 'https://quote.eastmoney.com/'})

# ---- B. 东财 datacenter 资产负债表（总资产） ----
sec('东财 资产负债表 RPT_DMSK_FN_BALANCE',
    'https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_DMSK_FN_BALANCE'
    '&columns=ALL&filter=' + Q('(SECURITY_CODE="600459")')
    + '&pageNumber=1&pageSize=2&sortColumns=REPORT_DATE&sortTypes=-1&source=WEB&client=WEB')

sec('东财 资产负债表 RPT_F10_FINANCE_GBALANCE',
    'https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_F10_FINANCE_GBALANCE'
    '&columns=ALL&filter=' + Q('(SECUCODE="600459.SH")')
    + '&pageNumber=1&pageSize=2&sortColumns=REPORT_DATE&sortTypes=-1&source=HSF10&client=PC')

# ---- C. 东财 业绩报表（含总资产？） ----
sec('东财 业绩报表 RPT_LICO_FN_CPD',
    'https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_LICO_FN_CPD'
    '&columns=ALL&filter=' + Q('(SECURITY_CODE="600459")')
    + '&pageNumber=1&pageSize=1&sortColumns=REPORTDATE&sortTypes=-1')

# ---- D. 东财 F10 主要指标 ----
sec('东财 F10 主要指标 MainTarget',
    'https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/MainTargetAjax'
    '?type=0&code=SH600459')

# ---- E. 腾讯板块排行（行业PE 候选） ----
sec('腾讯 板块排行 hy',
    'https://proxy.finance.qq.com/cgi/cgi-bin/rank/pt/getRank'
    '?board_type=hy&sort_type=price&direct=down&offset=0&count=8',
    headers={'Referer': 'https://gu.qq.com/'})

# ---- F. 新浪行业分类（行业PE 候选） ----
sec('新浪 行业分类 newSinaHy',
    'https://vip.stock.finance.sina.com.cn/q/view/newSinaHy.php',
    headers={'Referer': 'https://finance.sina.com.cn/'}, enc='gbk')

# ---- G. 雪球（行业/地区/总资产 候选） ----
sec('雪球 quote detail',
    'https://stock.xueqiu.com/v5/stock/quote.json?symbol=SH600459&extend=detail',
    headers={'Referer': 'https://xueqiu.com/'})

# ---- H. 同花顺 个股概况 ----
sec('同花顺 个股概况',
    'https://basic.10jqka.com.cn/600459/company.html',
    headers={'Referer': 'https://basic.10jqka.com.cn/'}, enc='gbk')

open(r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38\build\_src_probe2.txt', 'w',
     encoding='utf-8').write('\n'.join(OUT))
print('OK')
