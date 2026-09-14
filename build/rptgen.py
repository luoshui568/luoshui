# -*- coding: utf-8 -*-
"""研报 seed 生成公共库。

用途：把 PPTX 研究报告底稿（build/src/pptx_XXXXXX.json）里的**原生图表数据**
直接转成站点研报页（report.html）可用的 ECharts option + 23 模块 HTML。

与 extract_report.py（HTML 底稿 → seed）并行，但适用于只有 PPTX 的研究报告。

关键约定（与站点一致，勿改）：
  * 图表 option 里**不允许出现 Python/JS 函数**，只允许数据；若需格式化函数，
    由 extract_report.py 的 fn_token() 转具名标记。本模块只产出纯数据 option。
  * 模块 HTML 里图位占位写成 <div data-chart="chartXxx" class="chart-box"></div>。
  * 只使用 report_theme.css 里已存在的类名。
  * 行情类数字统一由 build/fetch_quotes.py 提供，禁止手写。
"""
import datetime
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# ----------------------------------------------------------------- 主题色
C = {
    'bar':   '#e8939c',   # 浅红柱（体量类）
    'bar2':  '#caa2a8',   # 灰粉柱（次要）
    'main':  '#c8102e',   # 正红（主序列）
    'line':  '#c0392b',   # 朱红（趋势线）
    'gold':  '#c9a227',   # 金（对比序列）
    'gold2': '#e6c558',
    'deep':  '#8c0a20',   # 深红
    'pie':   ['#c8102e', '#c9a227', '#e8939c', '#8c0a20', '#dcb9be', '#a5762a', '#caa2a8'],
}

CHART_KEYS = ['chartProd', 'chartCap', 'chartRaw', 'chartPrice', 'chartRev',
              'chartMix', 'chartMargin', 'chartExp', 'chartValuation', 'chartPrice2']


# ----------------------------------------------------------------- PPTX 读取
def load_pptx(code):
    p = os.path.join(HERE, 'src', 'pptx_%s.json' % code)
    return json.load(io.open(p, encoding='utf-8'))


def items(page_items, page):
    """取第 page 页（1 基）的 items。"""
    for sl in page_items:
        if sl['page'] == page:
            return sl['items']
    raise KeyError('no page %s' % page)


def _charts(sl_items):
    return [it['chart'] for it in sl_items if it.get('chart')]


def charts(j, page):
    return _charts(items(j['slides'], page))


def chart(j, page, name_sub=None, idx=0):
    """按页取图；name_sub 给定时，取第一条序列名包含它的图。"""
    cs = charts(j, page)
    if name_sub is None:
        return cs[idx]
    for c in cs:
        for s in c.get('series') or []:
            if name_sub in (s.get('name') or ''):
                return c
    raise KeyError('p%s 无含 %r 的图' % (page, name_sub))


def texts(j, page):
    out = []
    for it in items(j['slides'], page):
        if it.get('type') == 'text' and it.get('text'):
            out.append(it['text'])
    return out


def tables(j, page):
    out = []
    for it in items(j['slides'], page):
        if it.get('table') is not None:
            out.append(it['table'])
    return out


def pick(c, sub):
    """取序列（名字含 sub）的 values。"""
    for s in c.get('series') or []:
        if sub in (s.get('name') or ''):
            return s['values']
    raise KeyError('无序列 %r（有：%s）' % (sub, [s['name'] for s in c.get('series') or []]))


def pickn(c, sub):
    return (c.get('categories') or []), pick(c, sub)


# ----------------------------------------------------------------- 日期折算
EPOCH = datetime.date(1899, 12, 30)


def ser2date(v):
    """Excel 序列号（如 46227）→ date；'2025' 这类直接返回 None。"""
    try:
        n = int(float(v))
    except (TypeError, ValueError):
        return None
    if 20000 < n < 80000:
        return EPOCH + datetime.timedelta(days=n)
    return None


def by_year(cats, vals, agg='mean', nd=2, minn=1):
    """逐日序列 → 年度聚合（仅保留有效值足够的年份），返回 [(year, val)] 升序。
    agg: 'mean' 年度均值 / 'max' 年内最高 / 'min' 年内最低。"""
    bucket = {}
    for cv, v in zip(cats, vals):
        d = ser2date(cv)
        if d is None or v is None:
            continue
        bucket.setdefault(d.year, []).append(float(v))
    out = []
    for y in sorted(bucket):
        arr = bucket[y]
        if len(arr) < minn:
            continue
        if agg == 'max':
            m = max(arr)
        elif agg == 'min':
            m = min(arr)
        else:
            m = sum(arr) / len(arr)
        out.append((str(y), round(m, nd)))
    return out


def label_years(cats):
    """类目本身就是 '2025' 这种年份字符串时按原样升序返回 [(year,idx)]。"""
    out = []
    for i, c in enumerate(cats):
        s = str(c).strip()
        if len(s) == 4 and s.isdigit():
            out.append((s, i))
    out.sort()
    return out


def asc_years(c, sub, nd=2):
    """年度类目 + 序列 → [(year, val)] 升序（PPTX 里多为倒序，这里统一）。"""
    cats = c.get('categories') or []
    vals = pick(c, sub)
    m = dict(label_years(cats))
    out = []
    for y, i in sorted(m.items()):
        v = vals[i] if i < len(vals) else None
        out.append((y, None if v is None else round(float(v), nd)))
    return out


# ----------------------------------------------------------------- option 装配
def axis(xcats, yname='', right=None, xrot=0):
    o = {
        'tooltip': {'trigger': 'axis'},
        'legend': {'bottom': 0},
        'grid': {'left': 56, 'right': 50 if right else 40, 'top': 30, 'bottom': 44},
        'xAxis': {'type': 'category', 'data': list(xcats)},
        'yAxis': {'type': 'value', 'name': yname},
        'series': [],
    }
    if xrot:
        o['xAxis']['axisLabel'] = {'rotate': xrot}
    if right:
        o['yAxis'] = [{'type': 'value', 'name': yname},
                      {'type': 'value', 'name': right}]
    return o


def bar(o, name, data, color=None, yidx=None):
    s = {'name': name, 'type': 'bar', 'data': list(data),
         'itemStyle': {'color': color or C['bar']}}
    if yidx is not None:
        s['yAxisIndex'] = yidx
    o['series'].append(s)
    return s


def line(o, name, data, color=None, yidx=None, area=False, smooth=True):
    s = {'name': name, 'type': 'line', 'data': list(data),
         'itemStyle': {'color': color or C['line']}, 'smooth': smooth}
    if yidx is not None:
        s['yAxisIndex'] = yidx
    if area:
        s['areaStyle'] = {'opacity': 0.08}
    o['series'].append(s)
    return s


def pie(o, pairs, inner='42%', outer='68%'):
    o['tooltip'] = {'trigger': 'item', 'formatter': '{b}: {d}%'}
    o['series'] = [{
        'type': 'pie',
        'radius': [inner, outer],
        'center': ['50%', '44%'],
        'color': C['pie'],
        'data': [{'name': k, 'value': round(float(v), 2)} for k, v in pairs],
        'label': {'formatter': '{b} {d}%'},
    }]
    return o


def stack(o, name, data, color=None):
    s = {'name': name, 'type': 'bar', 'stack': 'total', 'data': list(data),
         'itemStyle': {'color': color or C['main']}}
    o['series'].append(s)
    return s


# ----------------------------------------------------------------- HTML 片段
def stat3(pairs, small_size=19):
    """三个统计块：pairs = [(label, val_html)]"""
    cells = ''.join(
        '<div class="stat"><div class="label">%s</div>'
        '<div class="val" style="font-size:%dpx;">%s</div></div>' % (a, small_size, b)
        for a, b in pairs)
    return '<div class="grid3">\n      %s\n    </div>' % cells


def table(headers, rows, cls=''):
    th = ''.join('<th>%s</th>' % h for h in headers)
    trs = []
    for r in rows:
        trs.append('<tr>' + ''.join('<td>%s</td>' % x for x in r) + '</tr>')
    return ('<table%s>\n      <tr>%s</tr>\n      %s\n    </table>'
            % ((' class="%s"' % cls) if cls else '', th, '\n      '.join(trs)))


def src(text):
    return '<p class="src"><b>来源：</b>%s</p>' % text


def chartbox(key, cls='chart-box'):
    return '<div data-chart="%s" class="%s"></div>' % (key, cls)


def risk(no, title, body):
    return ('<div class="risk-item"><div class="rt">%s %s</div>'
            '<div class="rc">%s</div></div>' % (no, title, body))


def ul(items_, fs=13.5):
    return ('<ul style="margin-left:18px;font-size:%spx;">%s</ul>'
            % (fs, ''.join('<li>%s</li>' % x for x in items_)))


def h3(t):
    return '<h3>%s</h3>' % t


def grid2(a, b, extra=''):
    return '<div class="grid2"%s>\n      <div>\n        %s\n      </div>\n      <div>\n        %s\n      </div>\n    </div>' % (
        extra, a, b)


def node(t1, t2):
    return '<div class="node"><div class="t1">%s</div><div class="t2">%s</div></div>' % (t1, t2)


def arrow(t):
    return '<div class="arrow" style="justify-content:center;">↓ %s</div>' % t


# ----------------------------------------------------------------- 评分（M22）
PRINCIPLES = [
    ('股东，央企或省国资委', 10),
    ('独一无二，资本别无选择', 14),
    ('产品持续大涨 > 100%', 13),
    ('扣非净利润持续大涨 > 60%', 14),
    ('主营集中 > 75%', 9),
    ('盈利模式简单清晰', 8),
    ('总市值 < 200亿', 8),
    ('股价盘整时间2-3年充分吸收', 9),
    ('股价位于月线底部区域', 9),
    ('底部成交量开始显著放大', 6),
]


def score_module(scores, kv_pairs, grade, date, note, remark=''):
    """scores: 10 个 0-10 的单项分（顺序同 PRINCIPLES）。"""
    total = sum(s * w for s, (_, w) in zip(scores, PRINCIPLES)) / 10.0
    total = round(total, 1)
    lines = []
    for i, ((nm, w), sc) in enumerate(zip(PRINCIPLES, scores), 1):
        if sc >= 8:
            bar_cls, pct = 'hi', 90 if sc > 8 else 80
        elif sc >= 6:
            bar_cls, pct = 'mid', 60
        else:
            bar_cls, pct = 'mid', 50
        em = '<em class="pos-em">pos</em>' if sc >= 9 else ''
        lines.append(
            '<div class="sc-line"><div class="sc-no">%d</div>'
            '<div class="sc-name">%s%s</div><div class="sc-w">%d%%</div>'
            '<div class="sc-bar"><i class="%s" style="width:%d%%;"></i></div>'
            '<div class="sc-val">%s</div></div>' % (i, nm, em, w, bar_cls, pct, sc))
    deg = total / 100.0
    gauge = ('<div class="score-hero">\n      <div class="gauge-wrap">\n'
             '        <div class="gauge" style="background:conic-gradient(#c8102e 0 %.1f%%, #f6e6e9 %.1f%% 100%%);">\n'
             '          <div class="gauge-in">\n'
             '            <div class="gauge-num">%s<small>/100</small></div>\n'
             '            <div class="gauge-label">加权总分</div>\n'
             '            <div class="gauge-badge">评级 · %s</div>\n'
             '          </div>\n        </div>\n'
             '        <div class="g-sub">参照选股原则 10 项 · 报告日 %s</div>\n'
             '      </div>\n      <div class="kv-grid">\n        %s\n      </div>\n    </div>'
             % (deg * 100, deg * 100, total, grade, date,
                ''.join('<div class="kv"><div class="k">%s</div><div class="v">%s</div></div>' % (a, b)
                        for a, b in kv_pairs)))
    crit = ('<div class="criteria">\n      <div class="criteria-head">十项选股原则评分'
            '<span>单项满分 10 分 · 按权重加权</span></div>\n      %s\n'
            '      <div class="sc-total"><span class="tl">加权总分</span>'
            '<span class="tn">%s</span><span class="tu">/ 100</span>'
            '<span class="tt">评级 · %s</span></div>\n    </div>'
            % ('\n      '.join(lines), total, grade))
    tail = '<p class="src" style="margin-top:12px;"><b>评分说明：</b>%s</p>' % note
    if remark:
        tail = ('<div class="logic"><div class="lt">评级口径与操作框架</div>'
                '<div class="lv">%s</div></div>\n    ' % remark) + tail
    return gauge + '\n    ' + crit + '\n    ' + tail


# ----------------------------------------------------------------- 壳
def toc(*pairs):
    return [{'anchor': a, 'text': t} for a, t in pairs]


def kpi(label, val, unit='', cls='', style=''):
    return {'label': label, 'val': val, 'unit': unit, 'cls': cls, 'style': style}


def essence(text):
    return ('<div class="essence" id="essence">\n'
            '    <div class="et">THE ESSENCE · 一句话本质（可证伪命题）</div>\n'
            '    <div class="ec">%s</div>\n  </div>' % text)


def footer(name, code, mkt, date, data_src, struct):
    return ('<footer>\n    <div class="disclaimer">\n'
            '      <strong>免责声明</strong>：以上内容基于公开数据和量化分析，仅供参考，不构成投资建议。'
            '市场有风险，投资需谨慎。任何投资决策应结合个人风险承受能力、资金状况和投资目标独立判断，'
            '必要时咨询持牌专业机构。过往表现不预示未来收益。\n    </div>\n'
            '    <p style="margin-top:12px;">数据来源：%s。报告生成时间：%s。</p>\n'
            '    <p>%s（%s）%s · 结构参照：%s · 仅供研究参考</p>\n  </footer>'
            % (data_src, date, name, code, mkt, struct))


def write_seed(code, report, mods, charts_):
    """产出 seed 并与 push_report.py 的入参格式一致。"""
    p = os.path.join(HERE, 'seed', 'report_%s.json' % code)
    out = {'report': report, 'mods': mods, 'charts': charts_}
    io.open(p, 'w', encoding='utf-8').write(
        json.dumps(out, ensure_ascii=False, separators=(',', ':')))
    print('  写出 %s（report 1 / mods %d / charts %d，%d 字符）'
          % (os.path.basename(p), len(mods), len(charts_),
             len(json.dumps(out, ensure_ascii=False))))
    return p


def mod(seq, title, html):
    return {'seq': seq, 'no': seq, 'title': title, 'html': html}


def chart_rec(seq, key, name, opt):
    return {'seq': seq, 'id': key, 'name': name, 'opt': opt}
