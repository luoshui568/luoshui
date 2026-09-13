# -*- coding: utf-8 -*-
"""探测「行业PE / 细分行业 / 总资产 / 地区」的可用数据源（只输出结论）"""
import json
import urllib.request
import urllib.parse

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
      'Referer': 'https://quote.eastmoney.com/'}
OUT = []


def get(url, headers=None, enc='utf-8'):
    req = urllib.request.Request(url, headers=headers or UA)
    with urllib.request.urlopen(req, timeout=25) as r:
        raw = r.read()
        hdr = dict(r.headers)
    txt = raw.decode(enc, 'replace')
    return txt, hdr


def sec(label, url, headers=None, enc='utf-8'):
    OUT.append('\n' + '=' * 70)
    OUT.append('[%s] %s' % (label, url[:150]))
    try:
        txt, hdr = get(url, headers, enc)
        OUT.append('--- len=%d  CORS=%s  CT=%s' % (
            len(txt), hdr.get('Access-Control-Allow-Origin', '无'),
            hdr.get('Content-Type', '')[:40]))
        OUT.append(txt[:2600])
    except Exception as e:
        OUT.append('!! 失败: %s' % e)


# ---------- 1. 东财 stock/get：全字段扫描，看哪些键有值 ----------
flds = ','.join('f%d' % i for i in list(range(1, 130)) + list(range(130, 300)))
sec('东财 stock/get 全字段',
    'https://push2.eastmoney.com/api/qt/stock/get?secid=1.600459&fields=' + flds)

# ---------- 2. 东财 F10 公司概况（行业 / 地区 / 注册地址） ----------
sec('东财 F10 CompanySurvey',
    'https://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/PageAjax?code=SH600459')

sec('东财 datacenter BASIC_ORGINFO',
    'https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_F10_BASIC_ORGINFO'
    '&columns=ALL&filter=' + urllib.parse.quote('(SECUCODE="600459.SH")')
    + '&pageNumber=1&pageSize=1&source=HSF10&client=PC')

# ---------- 3. 东财 行业板块列表（含板块 PE） ----------
sec('东财 行业板块列表(含PE)',
    'https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=100&po=1&np=1'
    '&fltt=2&invt=2&fid=f3&fs=m:90+t:2+f:!50'
    '&fields=f12,f14,f3,f9,f23,f104,f105,f128')

# ---------- 4. 东财 地域板块列表 ----------
sec('东财 地域板块列表',
    'https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=5&po=1&np=1'
    '&fltt=2&invt=2&fid=f3&fs=m:90+t:1+f:!50&fields=f12,f14')

# ---------- 5. 东财 个股所属板块（f100 行业 / f102 地域） ----------
sec('东财 个股板块归属 f100/f102',
    'https://push2.eastmoney.com/api/qt/stock/get?secid=1.600459'
    '&fields=f57,f58,f100,f101,f102,f103,f127,f128,f129')

# ---------- 6. 新浪 公司资料（行业 / 地区 / 总资产） ----------
sec('新浪 F10 公司资料页', 'https://vip.stock.finance.sina.com.cn/corp/go.php/vCI_CorpInfo/stockid/600459.phtml',
    headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.sina.com.cn/'}, enc='gbk')

# ---------- 7. 新浪 财务摘要 ----------
sec('新浪 F10 财务摘要',
    'https://money.finance.sina.com.cn/corp/go.php/vFD_FinanceSummary/stockid/600459.phtml',
    headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.sina.com.cn/'}, enc='gbk')

open(r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38\build\_src_probe.txt', 'w',
     encoding='utf-8').write('\n'.join(OUT))
print('已写入 build/_src_probe.txt，共 %d 段' % (len(OUT) // 3))
