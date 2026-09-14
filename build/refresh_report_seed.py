# -*- coding: utf-8 -*-
"""把研报 seed 里的「行情类数据」刷新到最新交易日。

只动行情口径的数字（价格 / 市值 / PE / PB / 涨跌幅 / 日期 / 来源），
不动 2026 半年报的财务数字、不动情景推演区间（那是分析框架，不是行情数据）。

行情来源与站点一致：腾讯行情 qt.gtimg.cn（build/fetch_quotes.py 拉取）。
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = os.path.join(HERE, 'seed')
Q = json.load(io.open(os.path.join(SEED, 'quotes_latest.json'), encoding='utf-8'))

OLD_DATE = '2026-08-26'
NEW_DATE = Q['600459']['quote_date']
SRC_OLD = '通达信'
SRC_NEW = '腾讯行情'


def fmt(v, nd=2):
    return ('%.*f' % (nd, v)) if v is not None else ''


def sign(v, nd=2):
    return ('+' if (v or 0) > 0 else '') + fmt(v, nd)


# ---------------------------------------------------------------- 每份研报的替换
def patches(code):
    q = Q[code]
    price = fmt(q['price'])
    cap = fmt(q['mkt_cap_yi'])
    fcap = fmt(q['float_cap_yi'])
    pe = fmt(q['pe_ttm'])
    pb = fmt(q['pb'])
    old = {}

    if code == '002237':
        old = {
            'badge': [
                ('行情时点 ' + OLD_DATE, '行情时点 ' + NEW_DATE),
                ('现价 14.92 元', '现价 %s 元' % price),
                ('总市值 213.35 亿元', '总市值 %s 亿元' % cap),
                ('PE(TTM) 15.86 倍', 'PE(TTM) %s 倍' % pe),
            ],
            'kpi': {'最新价（%s）' % OLD_DATE: ('最新价（%s）' % NEW_DATE, price),
                    '总市值': (None, cap), 'PE（TTM）': (None, pe), 'PB（MRQ）': (None, pb)},
            'mod': [
                # 模块 20 估值评价
                ('PE(TTM)约15.9倍，低于黄金板块可比公司均值',
                 'PE(TTM)约%s倍，仍低于黄金板块可比公司均值（约23.5倍）' % pe[:4]),
                # 模块 21
                ('关键指标（%s）' % OLD_DATE, '关键指标（%s）' % NEW_DATE),
                ('14.92 元（+0.20%）', '%s 元（%s%%）' % (price, fmt(q['chg_pct']))),
                ('213.35 / 177.9 亿元', '%s / %s 亿元' % (cap, fcap)),
                ('15.86 倍', '%s 倍' % pe),
                ('1.55 倍', '%s 倍' % pb),
                ('股价处于中低位震荡，PE约15.9倍相对便宜（冶炼型低毛利所致）；'
                 '若金价趋势延续、业绩持续兑现，估值存在修复空间。',
                 '最新价 %s 元（当日 %s%%），近 20 日 %s%%、近 60 日 %s%%、年初至今 %s%%，'
                 '整体中位震荡。<b>PE(TTM) 由 8 月末的 15.9 倍升至 %s 倍，并非股价推动'
                 '（同期股价反而下跌约 5%%），而是 TTM 口径归母净利回落所致</b> —— '
                 '与 2025 下半年减持万国黄金的一次性投资收益逐期滚出、扣非利润承压相符。'
                 'PB %s 倍处于历史中位偏低，若金价维持高位、冶炼与矿山项目陆续投产，'
                 '扣非口径的修复空间值得跟踪。'
                 % (price, fmt(q['chg_pct']), fmt(q['chg_20d']), fmt(q['chg_60d']),
                    sign(q['chg_ytd']), pe, pb)),
                ('来源：</b>%s实时行情（%s）' % (SRC_OLD, OLD_DATE),
                 '来源：</b>%s（%s）' % (SRC_NEW, NEW_DATE)),
            ],
        }
    else:   # 600459
        old = {
            'badge': [
                ('行情时点 ' + OLD_DATE, '行情时点 ' + NEW_DATE),
                ('现价 21.13 元', '现价 %s 元' % price),
                ('总市值 173.96 亿元', '总市值 %s 亿元' % cap),
                ('PE(TTM) 24.88 倍', 'PE(TTM) %s 倍' % pe),
            ],
            'kpi': {'最新价（%s）' % OLD_DATE: ('最新价（%s）' % NEW_DATE, price),
                    '总市值': (None, cap), 'PE（TTM）': (None, pe), 'PB（MRQ）': (None, pb)},
            'mod': [
                ('PE(TTM)约24.9倍，对应全产业链龙头溢价',
                 'PE(TTM)约%s倍，对应全产业链龙头溢价' % pe[:4]),
                ('关键指标（%s）' % OLD_DATE, '关键指标（%s）' % NEW_DATE),
                ('21.13 元（+0.28%）', '%s 元（%s%%）' % (price, fmt(q['chg_pct']))),
                ('173.96 / 160.53 亿元', '%s / %s 亿元' % (cap, fcap)),
                ('24.88 倍', '%s 倍' % pe),
                ('1.93 倍', '%s 倍' % pb),
                ('+15.08%', '%s%%' % sign(q['chg_ytd'])),
                ('股价年内涨幅约15%，PE(TTM)约24.9倍处于历史中位；20日涨幅16.6%显示资金关注度提升。'
                 '若贵金属价格延续强势+回收业务放量，估值仍有提升空间。',
                 '最新价 %s 元（当日 %s%%），年初至今 %s%%，但涨幅较 8 月末的 +15.1%% 已明显回吐；'
                 '近 20 日 %s%%、近 60 日 %s%%，短期趋势偏弱。PE(TTM) %s 倍、PB %s 倍均处于历史中位，'
                 '<b>估值并不贵，回调更多来自贵金属价格波动与业务结构调整期的收入下滑'
                 '（2026H1 营收同比 −23.4%%，主动压降低毛利贸易业务）</b>。'
                 '若铂族金属价格企稳 + 回收业务放量，估值存在修复空间。'
                 % (price, fmt(q['chg_pct']), sign(q['chg_ytd']), fmt(q['chg_20d']),
                    fmt(q['chg_60d']), pe, pb)),
                ('来源：</b>%s实时行情（%s）' % (SRC_OLD, OLD_DATE),
                 '来源：</b>%s（%s）' % (SRC_NEW, NEW_DATE)),
            ],
        }
    return old


def run(code):
    p = os.path.join(SEED, 'report_%s.json' % code)
    j = json.load(io.open(p, encoding='utf-8'))
    r = j['report']
    P = patches(code)
    hits = {'badge': 0, 'kpi': 0, 'mod': 0, 'stat': 0}

    # 徽标
    new_badges = []
    for b in r.get('badges') or []:
        nb = b
        for a, c in P['badge']:
            if a in nb:
                nb = nb.replace(a, c)
                hits['badge'] += 1
        new_badges.append(nb)
    r['badges'] = new_badges

    # KPI（只前 4 项是行情）
    for k in r.get('kpis') or []:
        key = k.get('label')
        if key in P['kpi']:
            newlabel, val = P['kpi'][key]
            if newlabel:
                k['label'] = newlabel
            k['val'] = val
            hits['kpi'] += 1

    # 备注与模块
    r['kpi_note'] = (r.get('kpi_note') or '').replace(OLD_DATE, NEW_DATE).replace(SRC_OLD, SRC_NEW)

    # 模块 20 顶部「PE / PB / 总市值」三个统计块：标签与数值之间有 <div> 隔断，
    # 不能靠整串匹配，按 label 定位后替换 val。
    q = Q[code]
    want = {'PE（TTM）': fmt(q['pe_ttm']), 'PB（MRQ）': fmt(q['pb']),
            '总市值': fmt(q['mkt_cap_yi'])}
    stat_re = re.compile(r'(<div class="label">([^<]+)</div><div class="val">)([^<]*)(<small>)')

    def fix_stat(m):
        lab = m.group(2)
        if lab in want and want[lab]:
            if m.group(3) != want[lab]:
                hits['stat'] += 1
            return m.group(1) + want[lab] + m.group(4)
        return m.group(0)

    for m in j['mods']:
        m['html'] = stat_re.sub(fix_stat, m['html'])

    for m in j['mods']:
        for a, c in P['mod']:
            if a in m['html']:
                m['html'] = m['html'].replace(a, c)
                hits['mod'] += 1
    # 兜底：任何残留的旧日期都换掉
    raw = json.dumps(j, ensure_ascii=False)
    n_date = raw.count(OLD_DATE)
    raw = raw.replace(OLD_DATE, NEW_DATE)
    j = json.loads(raw)
    hits['old_date_left'] = n_date

    io.open(p, 'w', encoding='utf-8').write(json.dumps(j, ensure_ascii=False, separators=(',', ':')))
    print('=== %s %s ===' % (code, r['name']))
    print('  徽标替换 %d / KPI 替换 %d / 模块片段替换 %d / 估值统计块 %d' % (hits['badge'], hits['kpi'], hits['mod'], hits['stat']))
    print('  残留旧日期 %d 处（已兜底替换）' % n_date)
    print('  新徽标:', r['badges'])
    print('  新 KPI:', ['%s=%s' % (k['label'], k['val']) for k in (r.get('kpis') or [])[:4]])
    print()
    return hits


if __name__ == '__main__':
    codes = sys.argv[1:] or ['002237', '600459']
    for c in codes:
        run(c)
