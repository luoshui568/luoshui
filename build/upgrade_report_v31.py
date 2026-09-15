# -*- coding: utf-8 -*-
"""把 23 模块的研报 seed 升级到 31 模块（模板 v3.1）。

用法：
    python upgrade_report_v31.py 600456            # 生成 seed/report_600456_v31.json
    python upgrade_report_v31.py --all              # 批量

输入：
    build/seed/report_<code>.json       旧研报（23 模块）
    build/seed/data_v31_<code>.json     新增模块的数据（人工/取数生成）
输出：
    build/seed/report_<code>_v31.json   新研报（31 模块）

铁律：
  * 旧内容**零丢失** —— 每个旧模块的 HTML 都进到 OLD2NEW 指定的新槽位，字符数守恒校验。
  * 新增模块的数据一律来自 data_v31_<code>.json；取不到的字段写 [MISSING]，**不编造**。
"""
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from report_template_v31 import (MODULES, MOD_BY_NO, OLD2NEW, NEW_NOS,
                                 TEMPLATE_VERSION, new_toc)

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = os.path.join(HERE, 'seed')


# ------------------------------------------------------------------ 取数辅助
def g(d, *keys, default=None):
    """安全取值：g(d,'fin','rev') → d['fin']['rev']"""
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def fnum(v, nd=2, unit=''):
    """数字格式化；None/空 → [MISSING]"""
    if v is None or v == '':
        return '<span style="color:#a3122a">[MISSING]</span>'
    try:
        x = float(v)
    except (TypeError, ValueError):
        return str(v)
    s = ('%.*f' % (nd, x)).rstrip('0').rstrip('.') if nd else str(int(x))
    return s + unit


def table(headers, rows, cls=''):
    th = ''.join('<th>%s</th>' % h for h in headers)
    trs = '\n      '.join('<tr>' + ''.join('<td>%s</td>' % c for c in r) + '</tr>' for r in rows)
    return ('<table%s>\n      <tr>%s</tr>\n      %s\n    </table>'
            % ((' class="%s"' % cls) if cls else '', th, trs))


def src(t):
    return '<p class="src"><b>来源：</b>%s</p>' % t


def h3(t):
    return '<h3>%s</h3>' % t


def ul(items_, fs=13.5):
    return ('<ul style="margin-left:18px;font-size:%spx;">%s</ul>'
            % (fs, ''.join('<li>%s</li>' % x for x in items_)))


# ------------------------------------------------------------------ 新增模块渲染
def m9_industry(d):
    """M9 行业总览与市场空间"""
    ind = g(d, 'industry', default={}) or {}
    rows = ind.get('rows') or []
    out = ['<p>%s</p>' % (ind.get('overview') or '[MISSING] 行业定义与边界待补。')]
    if rows:
        out.append(h3('市场规模与增速'))
        out.append(table(['年份', '市场规模', '同比增速', '备注'], rows))
    else:
        out.append('<p style="color:#a3122a">[MISSING] 行业规模序列待补 —— 建议取行业协会年报 / 券商行业深度。</p>')
    if ind.get('cagr'):
        out.append('<p><b>未来三年 CAGR：</b>%s</p>' % ind['cagr'])
    if ind.get('drivers'):
        out.append(h3('增长驱动因素'))
        out.append(ul(ind['drivers']))
    # 只有拿到规模序列才出图槽 —— 否则页面上会留一个灰色「暂无数据」框
    if ind.get('size'):
        out.append('<div data-chart="chartIndustrySize" class="chart-box"></div>')
    out.append(src(ind.get('source') or '[MISSING] 数据来源待补'))
    return '\n    '.join(out)


def m10_demand(d):
    """M10 下游需求结构拆解"""
    de = g(d, 'demand', default={}) or {}
    rows = de.get('rows') or []
    out = ['<p>%s</p>' % (de.get('overview') or '[MISSING] 下游结构概述待补。')]
    if rows:
        out.append(h3('下游应用占比'))
        out.append(table(['下游领域', '占比', '增速', '景气判断'], rows))
    else:
        out.append('<p style="color:#a3122a">[MISSING] 下游占比待补 —— 可从年报「分行业收入」+ 行业协会数据交叉验证。</p>')
    if de.get('pie'):
        out.append('<div data-chart="chartDemandMix" class="chart-box"></div>')
    if de.get('note'):
        out.append('<div class="logic"><div class="lt">结构性变化</div><div class="lv">%s</div></div>' % de['note'])
    out.append(src(de.get('source') or '[MISSING] 数据来源待补'))
    return '\n    '.join(out)


def m11_peers(d):
    """M11 竞争格局与市场份额"""
    pe = g(d, 'peers', default={}) or {}
    rows = pe.get('rows') or []
    out = ['<p>%s</p>' % (pe.get('overview') or '[MISSING] 竞争格局概述待补。')]
    if rows:
        out.append(h3('可比公司对比'))
        out.append(table(['公司（代码）', '营业收入', '毛利率', '总市值', 'PE', '定位'], rows))
    else:
        out.append('<p style="color:#a3122a">[MISSING] 可比公司表待补。</p>')
    out.append('<div data-chart="chartShare" class="chart-box"></div>')
    if pe.get('position'):
        out.append('<div class="logic"><div class="lt">公司相对定位</div><div class="lv">%s</div></div>' % pe['position'])
    out.append(src(pe.get('source') or '[MISSING] 数据来源待补'))
    return '\n    '.join(out)


def m12_mgmt(d):
    """M12 管理层与治理"""
    mg = g(d, 'mgmt', default={}) or {}
    rows = mg.get('rows') or []
    out = ['<p>%s</p>' % (mg.get('overview') or '[MISSING] 管理层概述待补。')]
    if rows:
        out.append(h3('核心管理层'))
        out.append(table(['姓名', '职务', '任期', '背景'], rows))
    else:
        out.append('<p style="color:#a3122a">[MISSING] 管理层名单待补 —— 取最新年报「董事、监事、高级管理人员」章节。</p>')
    if mg.get('incentive'):
        out.append(h3('股权激励与考核'))
        out.append('<p>%s</p>' % mg['incentive'])
    if mg.get('governance'):
        out.append('<div class="logic"><div class="lt">治理结构特征</div><div class="lv">%s</div></div>' % mg['governance'])
    out.append(src(mg.get('source') or '[MISSING] 数据来源待补'))
    return '\n    '.join(out)


def m17_moat(d):
    """M17 护城河与竞争优势量化"""
    fin = g(d, 'fin', default={}) or {}
    years = fin.get('years') or []
    roic = fin.get('roic') or []
    wacc = fin.get('wacc')
    rows = [[y, fnum(v if v is not None else None, 2, '%'),
             (fnum(wacc, 2, '%') if wacc is not None else '[MISSING]'),
             ('<b style="color:#0b8a5c">+%.2f pct</b>' % (v - wacc) if (v is not None and wacc is not None and v - wacc >= 0)
              else ('<b style="color:#c8102e">%.2f pct</b>' % (v - wacc) if (v is not None and wacc is not None) else '[MISSING]'))]
            for y, v in zip(years, roic)]
    out = ['<p>护城河的可量化代理指标是「投入资本回报率 ROIC 与加权平均资本成本 WACC 的利差」：'
           '持续为正说明公司在为股东创造价值，持续为负说明资本回报不足以覆盖资金成本。</p>']
    out.append(h3('ROIC 与 WACC 利差'))
    out.append(table(['年份', 'ROIC', 'WACC（假设）', '利差'], rows))
    if fin.get('wacc_note'):
        out.append('<p class="src"><b>WACC 口径：</b>%s</p>' % fin['wacc_note'])
    if g(d, 'moat', 'items'):
        out.append(h3('壁垒来源分项'))
        out.append(table(['壁垒维度', '强度', '依据'], g(d, 'moat', 'items')))
    out.append('<div data-chart="chartRoic" class="chart-box"></div>')
    if g(d, 'moat', 'verdict'):
        out.append('<div class="logic"><div class="lt">结论</div><div class="lv">%s</div></div>' % g(d, 'moat', 'verdict'))
    return '\n    '.join(out)


def m25_forecast(d):
    """M25 盈利预测模型"""
    fc = g(d, 'forecast', default={}) or {}
    cases = fc.get('cases') or {}
    out = ['<p>以下为三档情景假设，<b>假设显式列出、可被证伪</b>。预测不构成业绩承诺。</p>']
    if cases:
        rows = [[k, v.get('assume', ''), v.get('rev', ''), v.get('np', '')] for k, v in cases.items()]
        out.append(h3('三档情景假设'))
        out.append(table(['情景', '核心假设', '2026E 营收', '2026E 归母净利'], rows))
    else:
        out.append('<p style="color:#a3122a">[MISSING] 三档假设待补。</p>')
    out.append('<div data-chart="chartEstimate" class="chart-box"></div>')
    if fc.get('note'):
        out.append('<div class="logic"><div class="lt">关键敏感变量</div><div class="lv">%s</div></div>' % fc['note'])
    return '\n    '.join(out)


def m27_sens(d):
    """M27 估值敏感性"""
    se = g(d, 'sens', default={}) or {}
    mat = se.get('matrix') or {}
    out = ['<p>%s</p>' % (se.get('overview') or '以 PE 估值法对关键变量做敏感性测试，观察目标价区间。')]
    if mat.get('cols') and mat.get('rows'):
        head = ['变量 \\ 情景'] + list(mat['cols'])
        body = [[r[0]] + list(r[1:]) for r in mat['rows']]
        out.append(h3(mat.get('title') or '敏感性矩阵'))
        out.append(table(head, body))
    else:
        out.append('<p style="color:#a3122a">[MISSING] 敏感性矩阵待补。</p>')
    out.append('<div data-chart="chartSens" class="chart-box"></div>')
    if se.get('margin'):
        out.append('<div class="logic"><div class="lt">安全边际</div><div class="lv">%s</div></div>' % se['margin'])
    return '\n    '.join(out)


def m30_bullbear(d):
    """M30 多空论点对照"""
    bb = g(d, 'bullbear', default={}) or {}
    bull = bb.get('bull') or []
    bear = bb.get('bear') or []
    out = ['<p>把多空双方的论点与验证指标并排列出：<b>多方论点给出验证指标，空方论点给出证伪信号</b>。</p>']
    if bull:
        out.append(h3('多方论点（Bull）'))
        out.append(table(['论点', '验证指标', '当前状态'], bull))
    if bear:
        out.append(h3('空方论点（Bear）'))
        out.append(table(['论点', '证伪信号', '当前状态'], bear))
    if bb.get('tilt'):
        out.append('<div class="logic"><div class="lt">当前天平倾向</div><div class="lv">%s</div></div>' % bb['tilt'])
    return '\n    '.join(out)


NEW_RENDER = {9: m9_industry, 10: m10_demand, 11: m11_peers, 12: m12_mgmt,
              17: m17_moat, 25: m25_forecast, 27: m27_sens, 30: m30_bullbear}


# ------------------------------------------------------------------ 升级模块追加
def upgrade_tail(no, d):
    """给升级类模块追加新小节（原内容保留在前面）。"""
    fin = g(d, 'fin', default={}) or {}
    years = fin.get('years') or []

    if no == 6:      # 产能与技术 → 追加产能利用率趋势
        cap = g(d, 'capacity', default={}) or {}
        if not cap.get('rows'):
            return ''
        return (h3('产能利用率趋势') + table(['年份', '设计产能', '实际产量', '产能利用率'], cap['rows'])
                + '<div data-chart="chartCap" class="chart-box"></div>')

    if no == 7:      # 产销量 → 追加量价拆分
        vp = g(d, 'volprice', default={}) or {}
        if not vp.get('rows'):
            return ''
        return (h3('量价拆分') + table(['年份', '销量', '均价', '单位成本', '单位毛利'], vp['rows'])
                + ('<p>%s</p>' % vp['note'] if vp.get('note') else ''))

    if no == 21:     # 盈利能力 → 追加杜邦分解
        if not (fin.get('roe') and fin.get('nm')):
            return ''
        rows = []
        for i, y in enumerate(years):
            roe = fin['roe'][i] if i < len(fin['roe']) else None
            nm = fin['nm'][i] if i < len(fin['nm']) else None
            lev = fin['lev'][i] if i < len(fin['lev']) else None
            rows.append([y, fnum(roe, 2, '%'), fnum(nm, 2, '%'),
                         fnum(lev, 2, '%'),
                         ('%.2f 倍' % (1 / (1 - lev / 100)) if lev not in (None, '') and lev < 100 else '[MISSING]')])
        return (h3('杜邦分解（ROE = 净利率 × 资产周转 × 权益乘数）')
                + table(['年份', 'ROE', '销售净利率', '资产负债率', '权益乘数'], rows)
                + '<p class="src"><b>口径：</b>权益乘数 = 1 /（1 − 资产负债率）；'
                  'ROE 下滑时，用它拆出到底是「赚得少」还是「杠杆降」。</p>')

    if no == 23:     # 现金流 → 追加三表与净现比
        if not (fin.get('ocf') and fin.get('np')):
            return ''
        rows = []
        for i, y in enumerate(years):
            ocf, np_ = fin['ocf'][i], fin['np'][i]
            ratio = ('%.2f' % (ocf / np_) if (ocf is not None and np_ not in (None, 0)) else '[MISSING]')
            rows.append([y, fnum(fin['np'][i], 2, ' 亿'), fnum(ocf, 2, ' 亿'), ratio,
                         fnum(fin['lev'][i] if i < len(fin.get('lev') or []) else None, 2, '%')])
        return (h3('经营现金流与净现比')
                + table(['年份', '归母净利', '经营活动现金流净额', '净现比', '资产负债率'], rows)
                + '<div data-chart="chartCashflow" class="chart-box"></div>'
                + '<p class="src"><b>净现比 =</b> 经营现金流净额 ÷ 归母净利润，长期低于 1 说明利润没有变成现金。</p>')

    if no == 24:     # 分红 → 追加明细表
        if not fin.get('dps'):
            return ''
        rows = []
        for i, y in enumerate(years):
            dps = fin['dps'][i]
            eps = fin.get('eps', [None] * len(years))[i] if fin.get('eps') else None
            payout = ('%.1f%%' % (dps / eps * 100) if (dps is not None and eps not in (None, 0)) else '[MISSING]')
            rows.append([y, fnum(dps, 3, ' 元'), fnum(eps, 3, ' 元'), payout,
                         fnum(fin.get('divyield', [None] * len(years))[i] if fin.get('divyield') else None, 2, '%')])
        return (h3('历年分红明细')
                + table(['年份', '每股股利', '每股收益', '分红率', '当期股息率'], rows)
                + '<div data-chart="chartDividend" class="chart-box"></div>'
                + (('<p>%s</p>' % fin['dividend_note']) if fin.get('dividend_note') else ''))

    if no == 26:     # 估值 → 追加目标价推导
        va = g(d, 'valuation', default={}) or {}
        if not va.get('method'):
            return ''
        rows = va.get('rows') or []
        out = [h3('估值方法与目标价推导'), '<p>%s</p>' % va['method']]
        if rows:
            out.append(table(['方法', '关键假设', '隐含目标价'], rows))
        if va.get('target'):
            out.append('<div class="logic"><div class="lt">目标价区间</div><div class="lv">%s</div></div>' % va['target'])
        return '\n    '.join(out)

    return ''


# ------------------------------------------------------------------ 图表
def new_chart_opts(code, d):
    """新增图表的 ECharts option（纯数据，不含函数）。"""
    fin = g(d, 'fin', default={}) or {}
    ch = {}
    yrs = fin.get('years') or []

    # 行业规模
    ind = g(d, 'industry', default={}) or {}
    if ind.get('size'):
        ch['chartIndustrySize'] = {
            'tooltip': {'trigger': 'axis'}, 'legend': {'bottom': 0},
            'grid': {'left': 60, 'right': 40, 'top': 30, 'bottom': 40},
            'xAxis': {'type': 'category', 'data': ind.get('sizeYears') or []},
            'yAxis': [{'type': 'value', 'name': ind.get('sizeUnit') or ''},
                      {'type': 'value', 'name': '增速 %'}],
            'series': [
                {'name': '市场规模', 'type': 'bar', 'data': ind['size'], 'itemStyle': {'color': '#e8939c'}},
                {'name': '同比增速', 'type': 'line', 'yAxisIndex': 1, 'smooth': True,
                 'data': ind.get('sizeGrow') or [], 'itemStyle': {'color': '#c8102e'}},
            ]}

    # 下游结构
    dm = g(d, 'demand', default={}) or {}
    if dm.get('pie'):
        ch['chartDemandMix'] = {
            'tooltip': {'trigger': 'item', 'formatter': '{b}: {d}%'},
            'legend': {'bottom': 0},
            'series': [{'type': 'pie', 'radius': ['42%', '68%'], 'center': ['50%', '44%'],
                        'color': ['#c8102e', '#c9a227', '#e8939c', '#8c0a20', '#dcb9be', '#a5762a'],
                        'data': [{'name': k, 'value': v} for k, v in dm['pie']],
                        'label': {'formatter': '{b} {d}%'}}]}

    # 竞争份额
    pe = g(d, 'peers', default={}) or {}
    if pe.get('share'):
        ch['chartShare'] = {
            'tooltip': {'trigger': 'axis'}, 'legend': {'bottom': 0},
            'grid': {'left': 60, 'right': 40, 'top': 30, 'bottom': 40},
            'xAxis': {'type': 'category', 'data': [x[0] for x in pe['share']],
                      'axisLabel': {'interval': 0, 'rotate': 20, 'fontSize': 11}},
            'yAxis': {'type': 'value', 'name': '营收（亿元）'},
            'series': [{'name': '营业收入', 'type': 'bar', 'data': [x[1] for x in pe['share']],
                        'itemStyle': {'color': '#c8102e'},
                        'label': {'show': True, 'position': 'top', 'fontSize': 11, 'color': '#9a7d82'}}]}

    # ROIC vs WACC
    if fin.get('roic'):
        wacc = fin.get('wacc')
        ch['chartRoic'] = {
            'tooltip': {'trigger': 'axis'}, 'legend': {'bottom': 0},
            'grid': {'left': 56, 'right': 40, 'top': 30, 'bottom': 40},
            'xAxis': {'type': 'category', 'data': yrs},
            'yAxis': {'type': 'value', 'name': '%'},
            'series': [{'name': 'ROIC', 'type': 'bar', 'data': fin['roic'],
                        'itemStyle': {'color': '#c8102e'},
                        'label': {'show': True, 'position': 'top', 'fontSize': 11, 'color': '#9a7d82', 'formatter': '{c}'}},
                       {'name': 'WACC（假设）', 'type': 'line', 'smooth': False,
                        'data': [wacc] * len(yrs), 'itemStyle': {'color': '#c9a227'},
                        'lineStyle': {'type': 'dashed'}}]}

    # 现金流
    if fin.get('ocf'):
        ch['chartCashflow'] = {
            'tooltip': {'trigger': 'axis'}, 'legend': {'bottom': 0},
            'grid': {'left': 60, 'right': 50, 'top': 30, 'bottom': 40},
            'xAxis': {'type': 'category', 'data': yrs},
            'yAxis': [{'type': 'value', 'name': '亿元'}, {'type': 'value', 'name': '资产负债率 %'}],
            'series': [{'name': '归母净利', 'type': 'bar', 'data': fin['np'], 'itemStyle': {'color': '#e8939c'}},
                       {'name': '经营现金流净额', 'type': 'bar', 'data': fin['ocf'], 'itemStyle': {'color': '#c8102e'}},
                       {'name': '资产负债率', 'type': 'line', 'yAxisIndex': 1, 'smooth': True,
                        'data': fin.get('lev') or [], 'itemStyle': {'color': '#c9a227'}}]}

    # 分红
    if fin.get('dps'):
        ch['chartDividend'] = {
            'tooltip': {'trigger': 'axis'}, 'legend': {'bottom': 0},
            'grid': {'left': 56, 'right': 50, 'top': 30, 'bottom': 40},
            'xAxis': {'type': 'category', 'data': yrs},
            'yAxis': [{'type': 'value', 'name': '元/股'}, {'type': 'value', 'name': '元'}],
            'series': [{'name': '每股股利', 'type': 'bar', 'data': fin['dps'], 'itemStyle': {'color': '#c9a227'},
                        'label': {'show': True, 'position': 'top', 'fontSize': 11, 'color': '#9a7d82'}},
                       {'name': '每股收益', 'type': 'line', 'yAxisIndex': 1, 'smooth': True,
                        'data': fin.get('eps') or [], 'itemStyle': {'color': '#c8102e'}}]}

    # 盈利预测
    fc = g(d, 'forecast', default={}) or {}
    if fc.get('series'):
        ch['chartEstimate'] = {
            'tooltip': {'trigger': 'axis'}, 'legend': {'bottom': 0},
            'grid': {'left': 60, 'right': 40, 'top': 30, 'bottom': 40},
            'xAxis': {'type': 'category', 'data': fc.get('years') or []},
            'yAxis': {'type': 'value', 'name': '亿元'},
            'series': [{'name': s['name'], 'type': 'line', 'smooth': True, 'data': s['data'],
                        'itemStyle': {'color': s.get('color') or '#c8102e'},
                        'lineStyle': {'type': 'dashed' if s.get('dashed') else 'solid'}}
                       for s in fc['series']]}

    # 敏感性
    se = g(d, 'sens', default={}) or {}
    if se.get('heat'):
        ch['chartSens'] = {
            'tooltip': {'trigger': 'item'},
            'grid': {'left': 70, 'right': 60, 'top': 40, 'bottom': 60},
            'xAxis': {'type': 'category', 'data': se['heat']['cols'], 'name': se['heat'].get('xname') or ''},
            'yAxis': {'type': 'category', 'data': se['heat']['rows'], 'name': se['heat'].get('yname') or ''},
            'visualMap': {'min': se['heat'].get('min'), 'max': se['heat'].get('max'),
                          'calculable': True, 'orient': 'vertical', 'right': 0, 'top': 'middle',
                          'inRange': {'color': ['#0b8a5c', '#f6e6e9', '#c8102e']}},
            'series': [{'type': 'heatmap', 'data': se['heat']['data'],
                        'label': {'show': True, 'fontSize': 11}}]}
    return ch


# ------------------------------------------------------------------ 主流程
def build(code):
    # 源：优先取归档的 23 模块版（seed/report_<code>_v23.json），
    # 否则回退到 seed/report_<code>.json（对尚未升级过的研报）。
    old_p = os.path.join(SEED, 'report_%s_v23.json' % code)
    if not os.path.exists(old_p):
        old_p = os.path.join(SEED, 'report_%s.json' % code)
    data_p = os.path.join(SEED, 'data_v31_%s.json' % code)
    old = json.load(io.open(old_p, encoding='utf-8'))
    d = json.load(io.open(data_p, encoding='utf-8')) if os.path.exists(data_p) else {}
    d.setdefault('code', code)

    old_by_no = {str(m['no']): m for m in old['mods']}
    assert len(old_by_no) == 23, '旧研报应有 23 个模块，实际 %d' % len(old_by_no)

    # ---- 逐槽位组装 ----
    mods, used, added = [], set(), 0
    for spec in MODULES:
        no = spec['no']
        src_no = None
        for o, n in OLD2NEW.items():
            if n == no:
                src_no = str(o)
                break
        if src_no is not None:
            om = old_by_no[src_no]
            html = om['html']
            used.add(src_no)
            tail = upgrade_tail(no, d)
            if tail:
                html = html + '\n    ' + tail
                added += 1 if tail else 0
        else:
            fn = NEW_RENDER.get(no)
            assert fn, '新增模块 %d 无渲染器' % no
            html = fn(d)
        mods.append({'seq': no, 'no': str(no), 'title': spec['title'], 'html': html})

    assert len(used) == 23, '旧模块未全部使用：缺 %s' % (set(old_by_no) - used)

    # ---- 图表：旧图全留 + 新图 ----
    charts = []
    seen = set()
    for c in old['charts']:
        cid = c['id']
        if cid in seen:
            continue
        seen.add(cid)
        charts.append({'seq': len(charts) + 1, 'id': cid, 'name': c.get('name') or cid, 'opt': c['opt']})
    newch = new_chart_opts(code, d)
    for cid, opt in newch.items():
        if cid in seen:
            continue
        seen.add(cid)
        charts.append({'seq': len(charts) + 1, 'id': cid, 'name': g(d, 'chartNames', cid) or cid, 'opt': opt})

    # ---- 壳 ----
    rep = dict(old['report'])
    rep['toc'] = new_toc()
    rep['theme'] = rep.get('theme') or 'red'
    olen = sum(len(m['html']) for m in old['mods'])
    nlen = sum(len(m['html']) for m in mods)
    return {'report': rep, 'mods': mods, 'charts': charts}, olen, nlen, added


def main():
    args = sys.argv[1:]
    if '--all' in args:
        codes = sorted({f[len('report_'):-len('_v23.json')] for f in os.listdir(SEED)
                        if f.startswith('report_') and f.endswith('_v23.json')})
    else:
        codes = [a for a in args if not a.startswith('--')] or ['600456']
    for code in codes:
        seed, olen, nlen, added = build(code)
        # 输出即现行标准：seed/report_<code>.json（v23 版已归档为 _v23.json）
        out = os.path.join(SEED, 'report_%s.json' % code)
        io.open(out, 'w', encoding='utf-8').write(
            json.dumps(seed, ensure_ascii=False, separators=(',', ':')))
        # 校验
        nos = [m['no'] for m in seed['mods']]
        assert nos == [str(i) for i in range(1, 32)], '编号不连续'
        ids_used = set()
        for m in seed['mods']:
            ids_used |= set(re.findall(r'data-chart="([^"]+)"', m['html']))
        missing = ids_used - {c['id'] for c in seed['charts']}
        print('%s %-6s  模块 %d · 图表 %d · 正文 %d→%d 字符（+%d）· 追加小节 %d 个%s'
              % ('✓' if not missing else '⚠', code, len(seed['mods']), len(seed['charts']),
                 olen, nlen, nlen - olen, added,
                 '' if not missing else '  缺图: %s' % sorted(missing)))


if __name__ == '__main__':
    main()
