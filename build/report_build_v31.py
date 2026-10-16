# -*- coding: utf-8 -*-
"""纯新建通路：没有 23 模块旧版的公司，直接从 data_v31_<code>.json 生成 31 模块研报。

与 upgrade_report_v31.py 的区别：
  * upgrade 是「旧 23 模块 → 新 31 模块」的**整位重排**，靠 assert len(old_by_no)==23 守卫；
  * 本脚本是「从零建 31 模块」，全部 31 个模块都由渲染器生成，**没有旧内容可丢**。

数据铁律（与整套流水线一致）：
  * 数字一律来自 data_v31_<code>.json（该文件由 batch_assemble.py 从 iFinD 原始落盘组装）；
  * 取不到的一律写 [MISSING]，**绝不编造**；
  * 模型推算（情景/敏感性/ROIC 近似）一律标 [模型输出]。

用法：
    python report_build_v31.py 000519
    python report_build_v31.py --batch 0 30
输出：
    build/seed/report_<code>.json    31 模块现行版（可直接被 push_reports_v31.py 推库）
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = os.path.join(HERE, 'seed')
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from report_template_v31 import (MODULES, MOD_BY_NO, TEMPLATE_VERSION, new_toc,
                                 POS2RENDER, title_of)
import chartmap                       # 储量地图工具（build/chartmap.py）
import score_lock as SL                 # ★ 槽 29 冻结模块（唯一真源）

RED = '#c8102e'
MISS = '<span style="color:#a3122a">[MISSING]</span>'
LIB_DIR = os.path.join(HERE, 'lib')   # echarts / world-cn.js（自建国标中国版图）

# 全 28 张图的名称表（库内 wb_report_charts.name，页面按 key 取用）
CHART_NAMES = {
    'chartCap': '产能与产能利用率',
    'chartProd': '产销量与产销率',
    'chartIndustrySize': '行业市场规模与增速',
    'chartDemandMix': '下游需求结构',
    'chartShare': '同行业营收对比',
    'chartRaw': '原料价格走势',
    'chartPrice': '产品价格与成本',
    'chartPrice2': '股价走势',
    'chartRoic': 'ROIC 与 WACC 利差',
    'chartRev': '营业收入与归母净利',
    'chartMix': '收入结构',
    'chartMargin': '毛利率、净利率与 ROE',
    'chartExp': '费用率结构',
    'chartCashflow': '经营现金流与资产负债率',
    'chartDividend': '每股股利与每股收益',
    'chartEstimate': '盈利预测（三档情景）',
    'chartValuation': '估值区间',
    'chartSens': '目标价敏感性热力图',
    # ★ 2026-09-21 宝钛母本新增（第 25 / 26 槽「行业篇」用）
    'chartResDist': '资源储量与产量分布',
    'chartResPrice': '资源价格走势',
    'chartSDBalance': '供需平衡（供给 vs 需求）',
}


# ------------------------------------------------------------------ 基础工具
def fnum(v, nd=2, unit=''):
    """数字格式化；None/空 → [MISSING]"""
    if v is None or v == '':
        return MISS
    try:
        x = float(v)
    except (TypeError, ValueError):
        return str(v)
    if nd:
        s = ('%.*f' % (nd, x)).rstrip('0').rstrip('.')
    else:
        s = str(int(round(x)))
    return (s if s not in ('', '-0') else '0') + unit


def unit_ax(d, dflt):
    """坐标轴单位名（**必须短**）。

    ★★ 2026-09-22 血案：`capacity` / `production` / `pricecost` 的 `unit` 一职两用 ——
      既是「坐标轴单位」，又是模块底部的「口径：…」说明段。于是当作者把一整段口径说明
      写进 `unit` 时，**整段文字被当成 y 轴名渲染**（竖排几十个字，图被挤扁）。
      历史发生面：603977 / 601118 / 601958 / 603599 / 002408 **五份全中，共 10 处**。
    ⇒ 分离职责：`axis_unit` 只给轴（短），`unit_note` 只给「口径：…」段落（可长）。
       `unit` 保留为兼容回退。
    """
    d = d or {}
    return d.get('axis_unit') or d.get('unit') or dflt


def unit_note_html(d, unit=''):
    """生成「口径：…」说明段。

    ★ 2026-10-16：除 `unit_note`（表格口径，可长）外，再认一个 **`chart_note`** ——
      「**图上取的是哪一期 / 哪一列 / 为什么少一条系列**」这类**只与图有关**的口径说明。
      起因：000762 的表格是「2025 全年 vs 2026H1」两期对照，而图统一取 2026H1
      （否则会把 2026H1 产量当销量画）——这种差异必须写在读者能看见的地方。
      两者**同时存在时都输出**（它们是两件事）；都没有则不出这一段。
      ★ 存量报告只有 `unit_note` ⇒ 输出逐字节不变。
    """
    d = d or {}
    parts = []
    if d.get('unit_note'):
        parts.append(d['unit_note'])
    if d.get('chart_note'):
        parts.append(d['chart_note'])
    if not parts:
        return ''
    return '<p class="src">口径：%s</p>' % ' '.join(parts)


def numcol(rows, i, n):
    """取表格第 i 列转 float；空/非数字 → None（ECharts 断开，不编造 0）。

    ★ 2026-09-21：补 `x` 后缀剥离。原实现只剥 `%` 与千分位 `,`，
      于是 PE/PB 列写成 `"39.88x"`（表格里带倍数符号更规范）时 **float() 抛错 → 静默 None**
      ⇒ 600459/002237 的 chartValuation 成了「只有坐标轴、没有柱子」的空白图。
      实测影响面：仅这两家的 valuation.rows 的 PE/PB 列；
      其它列里的字母要么是年份标签（`2026E`，走 category 轴、不经本函数），
      要么在 deep 表格里（直接渲染成文本）。⇒ 对其它图是 no-op。
    """
    out = []
    for r in rows[:n]:
        v = r[i] if i < len(r) else None
        try:
            out.append(float(str(v).replace('%', '').replace(',', '')
                             .replace('x', '').replace('X', ''))
                       if v not in (None, '', '—', '-') else None)
        except (TypeError, ValueError):
            out.append(None)
    return out


def numeric_rows(rows, idx=(1, 2, 3), need=None):
    """这几列是不是「真的能画图」——至少有一列全部转不出数值就判否。

    ★ 2026-10-16：给 `pricecost` 补的闸。新研报把 `pricecost.rows` 写成
      **产品维度的文字表**（列＝参考市场价 / 公司口径 / 毛利率，全是带单位的散文），
      `numcol` 三列全 None ⇒ 画出一张「有坐标轴、图例有点、线上无点」的**空图**，
      而构建器自己的自检（槽位 ↔ 图数据一一对应）**查不出**这种「图在、数据空」。
      `need=None` ⇒ 要求所列各列都至少有一个数值。存量研报的 rows 本就是数值表，判据恒真。
    """
    if not rows:
        return False
    cols = [i for i in idx if i < len(rows[0])]
    if not cols:
        return False
    have = [any(v is not None for v in numcol(rows, i, len(rows))) for i in cols]
    return all(have) if need is None else (sum(have) >= need)


def table(headers, rows, cls=''):
    th = ''.join('<th>%s</th>' % h for h in headers)

    def cell(c):
        # None → MISS（真·缺失）；空串 → **留白**（有意为「公司未披露该口径」，
        # 由各模块的「产销解读 / 缺口说明」统一解释，不再逐格刷 [MISSING] 污染版面）。
        if c is None:
            return MISS
        if isinstance(c, str) and c.strip() == '':
            return '<span class="na">—</span>'
        return c
    trs = '\n      '.join('<tr>' + ''.join('<td>%s</td>' % cell(c) for c in r) + '</tr>' for r in rows)
    return ('<table%s>\n      <tr>%s</tr>\n      %s\n    </table>'
            % ((' class="%s"' % cls) if cls else '', th, trs))


def src(t):
    return '<p class="src"><b>来源：</b>%s</p>' % t


def deep(d, key):
    """取出 data_v31 里的**深度自由块**，渲染成 HTML 片段列表。

    ★ 2026-09-20 新增：这是「把模块做厚」的统一通路。
      背景 —— 宝钛（600456）的若干模块厚度达到 6K~19K 字符，靠的是**编辑器里手写的
      自定义视觉件**（关键持股指标卡 / 项目卡片组 / 十项评分卡）。这类内容有两个特点：
        ① 每个公司长得都不一样，写进渲染器就会变成 if-company-A-else-company-B 的泥潭；
        ② 内容本身是**数据**（数字 + 文案），不是逻辑。
      所以把它放进 data_v31_<code>.json 的 <key>.deep 里：渲染器只负责挂载，
      内容随公司走。换公司零改代码 —— 与 timeline / equity_tree 同一思路。

    格式（每一项任选 type，也可只给 html 直接透传）：
        "deep": [
          {"t": "h3",  "x": "标题"},
          {"t": "h4",  "x": "小标题"},
          {"t": "p",   "x": "段落（允许内联标签）"},
          {"t": "ul",  "x": ["条目1", "条目2"]},
          {"t": "table", "head": [...], "rows": [[...], ...]},
          {"t": "logic", "k": "小标题", "x": "解读"},
          {"t": "cards", "x": [{"v": "49.40", "u": "%", "l": "持股比例"}, ...]},
          {"t": "html", "x": "<div>…</div>"},        # 逃生口：自定义视觉件
        ]
    """
    blk = g(d, key, default={}) or {}
    items = blk.get('deep') if isinstance(blk, dict) else None
    if not items:
        return []
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        t = (it.get('t') or 'p').lower()
        x = it.get('x')
        if t == 'h3':
            out.append(h3(x or ''))
        elif t == 'h4':
            out.append(h4(x or ''))
        elif t == 'ul':
            out.append(ul(x or []))
        elif t == 'table':
            out.append(table(it.get('head') or [], it.get('rows') or []))
        elif t == 'logic':
            out.append(logic(it.get('k') or '', x or ''))
        elif t == 'cards':
            cs = []
            for c in (x or []):
                cs.append('<div class="dcard"><div class="dv">%s<small>%s</small></div>'
                          '<div class="dl">%s</div></div>'
                          % (c.get('v', ''), c.get('u', ''), c.get('l', '')))
            out.append('<div class="dcards">%s</div>' % ''.join(cs))
        elif t == 'html':
            out.append(x or '')
        else:
            out.append('<p>%s</p>' % (x or ''))
    return out


def h3(t):
    return '<h3>%s</h3>' % t


def h4(t):
    return '<h4 style="margin:14px 0 6px;font-size:14px;">%s</h4>' % t


def ul(items_, fs=13.5):
    return ('<ul style="margin-left:18px;font-size:%spx;">%s</ul>'
            % (fs, ''.join('<li>%s</li>' % x for x in items_)))


def logic(title, body):
    return '<div class="logic"><div class="lt">%s</div><div class="lv">%s</div></div>' % (title, body)


def chart(key, height=None):
    """图槽。`height` 给 px 高度（行内 style）—— 地图类需要 470px 才铺得开，
    默认高度只有 320px 左右，区域名会挤在一起。"""
    st = ' style="height:%dpx;"' % int(height) if height else ''
    return '<div data-chart="%s" class="chart-box"%s></div>' % (key, st)




def g(d, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def pct(v, nd=2):
    """涨跌染色：涨红跌绿（A 股口径）"""
    if v is None:
        return MISS
    c = RED if v >= 0 else '#0b8a5c'
    return '<b style="color:%s">%+.2f%%</b>' % (c, v)


def yoy(cur, prev):
    if cur is None or prev in (None, 0):
        return None
    try:
        return (float(cur) / float(prev) - 1) * 100
    except (TypeError, ValueError, ZeroDivisionError):
        return None


# ★ 2026-10-14：年份数**一律从 years 列表实测**，不再写死。
#   起因：徽标写死「（10 年）」而 iFinD 序列只有 2021~2025 共 5 个年度，
#   用户一眼看出「数据区间 2021~2025（10 年）」不对（截图指出）。
#   凡是「N 年」的表述都走这里，改数据源就不会再出现口径打架。
_CN_NUM = {1: '一', 2: '二', 3: '三', 4: '四', 5: '五', 6: '六', 7: '七',
           8: '八', 9: '九', 10: '十', 11: '十一', 12: '十二', 13: '十三',
           14: '十四', 15: '十五', 16: '十六', 20: '二十'}


def span_n(years):
    """真实年数；years 为空返回 0"""
    return len(years or [])


def span_cn(n):
    """年数的中文写法（5 → 五）；超出词表退回阿拉伯数字"""
    return _CN_NUM.get(n, str(n))


# ------------------------------------------------------------------ 三表（通用）
def fin3(d):
    """营收/归母净利/毛利率/净利率 三表 —— 第一篇与第四篇共用。"""
    fin = g(d, 'fin', default={}) or {}
    years = fin.get('years') or []
    rev, np_ = fin.get('rev') or [], fin.get('np') or []
    gm, nm = fin.get('gm') or [], fin.get('nm') or []
    # ★ 2026-09-20：支持**序列首年的同比**。序列从 2021 开始，首年同比需要 2020 基数 ——
    #   数据里给了 fin.prev = {'year':'2020','rev':…,'np':…} 就用它，否则首年同比留空
    #   （这才是「真的取不到」，而不是渲染器不肯算）。
    pv = fin.get('prev') or {}
    rows = []
    for i, y in enumerate(years):
        r = rev[i] if i < len(rev) else None
        n = np_[i] if i < len(np_) else None
        if i >= 1:
            p = rev[i - 1] if i - 1 < len(rev) else None
            pn = np_[i - 1] if i - 1 < len(np_) else None
            rt, nt = pct(yoy(r, p)), pct(yoy(n, pn))
        elif pv:
            rt, nt = pct(yoy(r, pv.get('rev'))), pct(yoy(n, pv.get('np')))
        else:
            rt, nt = MISS, MISS
        rows.append([y, fnum(r, 2, ' 亿'), rt,
                     fnum(n, 2, ' 亿'), nt,
                     fnum(gm[i] if i < len(gm) else None, 2, '%'),
                     fnum(nm[i] if i < len(nm) else None, 2, '%')])
    return (table(['年份', '营业收入', '同比', '归母净利', '同比', '毛利率', '净利率'], rows),
            years, rev, np_)


# ------------------------------------------------------------------ 31 个模块渲染
def m1(d):
    """1 公司简介"""
    fin = g(d, 'fin', default={}) or {}
    name = d.get('name') or ''
    code = d.get('code') or ''
    ind = g(d, 'industry', default={}) or {}
    ind_name = ''
    if isinstance(ind, str):
        ind_name = ind
    else:
        ind_name = d.get('industry_name') or g(d, 'industryName', default='') or ''
    rows = [
        ['证券简称', name, '证券代码', '%s.SZ' % code if code[:1] in '0123' else '%s.SH' % code],
        ['所属细分行业', ind_name or MISS, '所属板块', g(d, 'grp', default='寒武纪投资2026') or '寒武纪投资2026'],
        ['最新股价', fnum(fin.get('price'), 2, ' 元'), '总市值', fnum(fin.get('mktcap'), 2, ' 亿元')],
        ['PE（TTM）', fnum(fin.get('pe'), 2, ' 倍'), 'PB（MRQ）', fnum(fin.get('pb'), 2, ' 倍')],
    ]
    out = ['<p>%s（%s）为「寒武纪投资2026」板块成分股，细分行业归属「%s」。本节为标准化建档信息，'
           '所有字段均取自 iFinD 与板块成员表。</p>' % (name, code, ind_name or MISS),
           table(['项目', '内容', '项目', '内容'], rows)]
    # 深度自由块（建档信息 / 行业地位 / 员工与研发等一手字段）
    out += deep(d, 'profile')
    # ★ 2026-09-20：source 改为数据可覆写 —— 原来把「成立日期/上市日期/实控人/员工数：[MISSING]」
    #   写死在这里，一旦 profile 补齐，这段自述就变成假话。
    pf = g(d, 'profile', default={}) or {}
    out.append(src(pf.get('source')
                   or 'iFinD（财务与估值）· 板块成员表（行业归属）；行情时点见文首徽标。'))
    return '\n    '.join(out)


def m2(d):
    """2 公司历史沿革

    ★ 2026-09-20 升级：若 data_v31 里给了 `timeline`（结构化节点），
      就走 TimelineKit 渲染成**时间轴**（与 600456 同构）；
      否则退回原来的表格形态（不编造视觉件）。

    时间轴数据格式：
        "timeline": {
            "en": "COMPANY HISTORY", "title": "公司发展历程",
            "sub": "一句话副标题", "foot": "底部一句话",
            "source": "可选：本时间轴的来源（不给则回落 business.source）",
            "nodes": [["1999", "<b>…</b>…"], ["2002", "…"]]
        }
    """
    name = d.get('name') or ''
    pf = g(d, 'profile', default={}) or {}
    rows = d.get('history') or []
    out = []
    if pf.get('full_name') or pf.get('legal_rep') or pf.get('reg_addr'):
        info = [
            ['公司全称', pf.get('full_name') or MISS, '法定代表人', pf.get('legal_rep') or MISS],
            ['注册地址', pf.get('reg_addr') or MISS, '上市地', pf.get('listing') or MISS],
        ]
        if pf.get('reg_capital'):
            info.append(['注册资本/信用代码', pf.get('reg_capital'), '公司网址', pf.get('website') or MISS])
        out.append(table(['项目', '内容', '项目', '内容'], info))

    tl = g(d, 'timeline', default=None)
    tl_src = ''
    if isinstance(tl, dict) and tl.get('nodes'):
        # ★ 时间轴路径：数据驱动，换公司零改代码
        from chartflow import TimelineKit
        nodes = [(n[0], n[1]) for n in tl['nodes']]
        tk = TimelineKit()
        tk.selfcheck(nodes)          # 出厂体检：节点数/结构/高度三关
        tl_src = tl.get('source') or ''
        out.append(tk.html(nodes,
                           en=tl.get('en') or 'COMPANY HISTORY',
                           title=tl.get('title') or '公司发展历程',
                           sub=tl.get('sub') or '',
                           foot=tl.get('foot') or ''))
    else:
        out.append('<p>下表为公司沿革的**关键时间轴**：改制、重组、更名、重要资产注入等节点，'
                   '及其对当前业务结构的影响。</p>')
        if rows:
            out.append(table(['时间', '事件', '影响/说明', '来源'], rows))
        else:
            out.append('<p style="color:#a3122a">%s 关键时间轴待补 —— 取公司官网「发展历程」+ '
                       '年报「公司历史沿革」章节，逐条列出「年份 / 事件 / 对当前业务结构的影响」。</p>' % MISS)
    # 来源：时间轴自带 > business.source > 兜底（母本无 tl['source'] ⇒ 行为不变）
    out.append(src(tl_src or (d.get('business') or {}).get('source')
                   or '%s —— 待取：最新年报「公司简介和主要财务指标」及「重大资产重组」附注。' % MISS))
    return '\n    '.join(out)


def m3(d):
    """3 股东结构

    ★ 2026-09-20 升级：若 data_v31 里给了 `equity_tree`，就走 OrgTreeKit
      渲染成**股权结构树状图**（与 600456 同构）；否则只出表格。

    树数据格式（⚠️ 三个比例语义不同，见 chartflow.py 的 svg() docstring）：
        "equity_tree": {
            "chain":    [["陕西省人民政府","—"],          # 顶层，无上游
                         ["陕西有色金属集团","100%"],      # 上一节点持有它 100%
                         ["宝钛集团有限公司","93.36%"]],   # 上一节点持有它 93.36%
            "subject":  "宝鸡钛业股份有限公司（600456.SH）",
            "subject_pct": "49.40%",                     # ★ 链末持有「上市公司」的比例
            "children": [["宝钛华神钛业有限公司","66.67%"], …]
        }
    """
    fin = g(d, 'fin', default={}) or {}
    sh = g(d, 'shareholder', default={}) or {}
    rows = [['总市值', fnum(fin.get('mktcap'), 2, ' 亿元'), 'iFinD，行情时点见文首徽标'],
            ['PB（MRQ）', fnum(fin.get('pb'), 2, ' 倍'), 'iFinD']]
    if sh.get('hub_count'):
        rows.append(['股东户数', sh['hub_count'], '取最新定期报告；户数下降通常意味着筹码集中'])
    if sh.get('controlling'):
        rows.append(['直接控股股东', sh['controlling'], '最新年报「股东情况」'])
    if sh.get('chain'):
        rows.append(['主要股东持股', sh['chain'], '最新年报「股东情况」'])
    if not sh.get('chain'):
        rows.append(['前十大股东及持股比例', MISS, '取最新定期报告「股东情况」章节'])
    # ★ 2026-09-20：原来这里无条件 `rows.append(['限售解禁时间表', MISS, ...])`。
    #   若数据里给了 lockup_note（实证结论或缺口说明），就整行替换掉，避免假红。
    if sh.get('lockup_note'):
        rows.append(['限售解禁时间表', '见下方说明', '本轮已核实：无待解禁限售股'])
    else:
        rows.append(['限售解禁时间表', MISS, '取最新公告「限售股上市流通」'])
    out = ['<p>股本与市值结构、股东明细如下。</p>',
           table(['项目', '数值', '说明'], rows)]

    et = g(d, 'equity_tree', default=None)
    if isinstance(et, dict) and et.get('children'):
        # ★ 树状图路径：数据驱动，换公司零改代码
        from chartflow import OrgTreeKit
        chain = [tuple(x) for x in et.get('chain') or []]
        kids = [tuple(x) for x in et['children']]
        subj = et.get('subject') or ('%s（%s）' % (d.get('name') or '', d.get('code') or ''))
        # ⚠️ subject_pct 必须显式取：它是「链末节点持有上市公司的比例」，
        #    与 chain[-1].pct（链末节点自己的流入比例）不是一个数。
        #    600456: chain[-1].pct=93.36% 而 subject_pct=49.40%。
        spct = et.get('subject_pct') or None
        ot = OrgTreeKit()
        ot.selfcheck(chain, subj, kids, spct)   # 出厂体检：坐标/重叠/字号/比例四关
        out.append(h3('股权结构图'))
        out.append('<div class="sh3-tree">')
        out.append(ot.svg(chain, subj, kids, subject_pct=spct))
        if et.get('cap'):
            out.append('<p class="cap">%s</p>' % et['cap'])
        out.append('</div>')

    if sh.get('siblings'):
        out.append(logic('集团股东背景', sh['siblings']))
    # 前十大股东明细（有数据才出表；没有就不铺空表）
    t10 = sh.get('top10') or []
    if t10:
        out.append(h3('前十大股东明细'))
        body = [[r[1], r[3]] if len(r) == 2 else list(r) for r in t10]
        out.append(table(sh.get('top10_head') or ['股东名称', '性质', '持股(股)', '占比'], body))
        if sh.get('top10_sum'):
            out.append('<p style="font-size:13.5px;"><b>前十大合计：</b>%s</p>' % sh['top10_sum'])
    if sh.get('note'):
        out.append(logic('股权特点解读', sh['note']))
    out += deep(d, 'shareholder')
    out.append(src(sh.get('source') or '股本/市值：iFinD；股东明细：%s' % MISS))
    return '\n    '.join(out)


def m4(d):
    """4 实控人与集团背景"""
    name = d.get('name') or ''
    sh = g(d, 'shareholder', default={}) or {}
    if sh.get('controller'):
        rows = [
            ['实际控制人', sh.get('controller') or MISS, '性质', sh.get('controller_type') or MISS],
            ['直接控股股东', sh.get('controlling') or MISS, '股东户数', sh.get('hub_count') or MISS],
        ]
        out = ['<p>%s 的股权控制链与集团背景如下。实际控制人性质决定了公司在融资、'
               '订单与同业竞争方面的资源约束。</p>' % name,
               table(['项目', '内容', '项目', '内容'], rows)]
        if sh.get('chain'):
            out.append(h4('股权控制链'))
            out.append('<p style="font-size:13.5px;">%s</p>' % sh['chain'])
        if sh.get('siblings'):
            out.append(h4('同一实际控制人下的其他上市公司'))
            out.append('<p style="font-size:13.5px;">%s</p>' % sh['siblings'])
            out.append(logic('同业竞争与资产注入', '同一集团下存在多家上市公司时，需关注：'
                             '① 是否存在同类业务形成同业竞争；② 集团是否有未上市同类资产可注入；'
                             '③ 集团是否提供订单/原料/融资担保等协同。'))
        out.append(src(sh.get('source') or '%s —— 待取：最新年报「控股股东和实际控制人」章节。' % MISS))
        # ★ 2026-09-20：全报告的真缺口集中在这里列一次，替代散落的 [MISSING] 说明。
        gp = g(d, 'controller', default={}).get('gaps') or {}
        if gp.get('rows'):
            out.append(h3(gp.get('title') or '外部数据缺口'))
            out.append(table(gp.get('head') or ['缺口', '已确认部分', '待取路径'], gp['rows']))
            if gp.get('note'):
                out.append(logic('为什么这些缺口不填估算值', gp['note']))
        out += deep(d, 'controller')
        return '\n    '.join(out)
    return '\n    '.join([
        '<p>%s 的实际控制人性质（央企 / 地方国资委 / 民营 / 无实控人）与所属集团资产协同关系，'
        '是需要一手核实的**定性字段**，本批次不填猜测值。</p>' % name,
        '<p style="color:#a3122a">%s 实控人性质与集团背景 —— 取最新年报「控股股东情况」章节 + 企查查股权穿透。'
        '重点回答三问：① 实控人是国资还是民营；② 集团是否有同类资产存在同业竞争；'
        '③ 集团是否为公司提供订单、原料或融资担保。</p>' % MISS,
        src('%s —— 待取：最新年报「控股股东和实际控制人」章节。' % MISS),
    ])


def m5(d):
    """5 业务及产品"""
    name = d.get('name') or ''
    ind = d.get('industry_name') or (d.get('industry') if isinstance(d.get('industry'), str) else '') or MISS
    bu = g(d, 'business', default={}) or {}
    segs = bu.get('segments') or []
    if segs:
        rows = []
        for s in segs:
            if len(s) >= 5:
                rows.append([s[0], fnum(s[1], 2, ' 亿') if s[1] else MISS,
                             fnum(s[2], 1, '%') if s[2] else MISS, s[4]])
            else:
                rows.append([s[0], MISS, MISS, s[3] if len(s) > 3 else MISS])
        out = ['<p>%s 的业务与产品矩阵如下。收入占比与毛利率需以年报「主营业务分行业、分产品」'
               '附注为准，本批次片段未给出金额时如实标注。</p>' % name,
               h3('业务板块与产品'),
               table(['业务板块', '收入', '毛利率', '产品与定位'], rows)]
        if bu.get('products'):
            out.append(h4('主要产品'))
            out.append('<p style="font-size:13.5px;">%s</p>' % bu['products'])
        if bu.get('markets'):
            out.append(h4('销售区域与客户'))
            out.append('<p style="font-size:13.5px;">%s</p>' % bu['markets'])
        out.append('<p><b>行业归属：</b>%s（据板块成员表）。</p>' % ind)
        out.append(src(bu.get('source') or '%s —— 待取：最新年报主营业务分产品附注。' % MISS))
        return '\n    '.join(out)
    return '\n    '.join([
        '<p>%s 的业务与产品矩阵概述（产品线、收入占比、应用领域）需要以年报「分产品收入」'
        '附注为准，本批次未取一手数据，故不编造产品名称与占比。</p>' % name,
        '<p style="color:#a3122a">%s 产品矩阵表（产品名称 / 收入 / 收入占比 / 毛利率 / 应用领域）—— '
        '取最新年报「主营业务分行业、分产品、分地区情况」附注。</p>' % MISS,
        '<p><b>行业归属：</b>%s（据板块成员表）。</p>' % ind,
        src('%s —— 待取：最新年报主营业务分产品附注。' % MISS),
    ])


def m6(d):
    """6 主要产品产能与技术（+利用率趋势）"""
    cap = g(d, 'capacity', default={}) or {}
    out = []
    if cap.get('rows'):
        out.append('<p>产能与产能利用率是判断「增长是否有物理上限」的第一步：'
                   '产能利用率长期接近 100% 意味着增量必须靠新建产能（资本开支周期），'
                   '长期低于 70% 则说明需求不足或产线切换频繁。</p>')
        if cap.get('overview'):
            out.append('<p>%s</p>' % cap['overview'])
        out.append(h3('产能利用率趋势'))
        out.append(table(cap.get('head') or ['年份', '设计产能', '实际产量', '产能利用率'],
                         cap['rows']))
        # ★ 2026-10-16：与 chart_opts 里的判据**必须一致**（那里建图、这里挂槽）。
        #   混合单位的文字产能表（002237）在那边不建图 ⇒ 这里也不能挂槽，
        #   否则槽位会去取库里**上一版的空 opt**，页面留一张「只有坐标轴」的图。
        if numeric_rows(cap.get('chart_rows') or cap.get('rows') or [], idx=(1, 2), need=1):
            out.append(chart('chartCap'))
        _un = unit_note_html(cap)
        if _un:
            out.append(_un)
        if cap.get('note'):
            out.append(logic('产能解读', cap['note']))
    else:
        out.append('<p>产能、产能利用率与技术壁垒属于**公司披露信息**。'
                   '若后续录入产能数据，本节的「产能利用率趋势」表与图会自动填充。</p>')
        out.append('<p style="color:#a3122a">%s 产能表（品种 × 产能 × 产能利用率）—— '
                   '取最新年报「生产能力」章节与「主要产品产能产量」附注。</p>' % MISS)
    tb = g(d, 'tech', default={}) or {}
    if tb.get('items'):
        out.append(h3('技术壁垒'))
        out.append(table(['壁垒维度', '公司现状', '强度'], tb['items']))
        if tb.get('note'):
            out.append(logic('技术壁垒判读', tb['note']))
    else:
        out.append(logic('技术壁垒', '%s —— 需回答：① 核心工艺是自研还是引进；'
                         '② 是否掌握关键牌号/配方；③ 是否承担国家/行业标准制定；'
                         '④ 认证周期多长（客户切换成本）。' % MISS))
    out.append(src(cap.get('source') or tb.get('source')
                   or '%s —— 待取：最新年报「生产能力」章节。' % MISS))
    return '\n    '.join(out)


def m7(d):
    """7 主要产品产量与销量（量价拆分）"""
    vp = g(d, 'volprice', default={}) or {}
    pr = g(d, 'production', default={}) or {}
    out = ['<p>量价拆分（均价 × 销量 = 收入）是判断增长质量的**核心工具**：'
           '量增价稳好于价增量稳，量价齐跌最差。</p>']
    if vp.get('rows'):
        out.append(h3('量价拆分'))
        out.append(table(['年度', '销量/产量', '均价', '收入', '产销率'], vp['rows']))
        if vp.get('note'):
            out.append(logic('量价解读', vp['note']))
    elif not pr.get('rows'):
        out.append('<p style="color:#a3122a">%s 产销量表与量价拆分 —— 取最新年报「主要经营情况」'
                   '与「产销量情况」附注。</p>' % MISS)
    if pr.get('rows'):
        # 只保留有真实数据的列 —— 全是留白的列（如未披露的产销量绝对数）不进表格，
        # 改为在「产销解读」里说明缺口，避免铺一屏 [MISSING]。
        keep = [i for i in range(len(pr['rows'][0]))
                if any(str(r[i]).strip() not in ('', '[MISSING]') for r in pr['rows'])]
        if len(keep) >= 2:
            head = pr.get('head') or ['品种', '产量', '销量', '产销率']
            out.append(h3(pr.get('title') or '产销存情况'))
            out.append(table([head[i] for i in keep],
                             [[r[i] for i in keep] for r in pr['rows']]))
            # ★ 只有**绝对量口径**才出产销量图；百分比口径出图会把 +42.87% 画成 42.87 吨。
            # ★★ 2026-10-16：与 chart_opts 的判据**必须逐字一致**（那里建图、这里挂槽）——
            #   仅有 `absolute` 挡不住「口径对照表」：601118 的三行是互斥口径（自产/加工/贸易），
            #   601958 的列 2 是「权益产量」。两边同步加「表头含销量 + 至少一行产量销量成对」。
            _prows = pr.get('chart_rows') or pr.get('rows') or []
            _phead = ' '.join(str(x) for x in (pr.get('head') or []))
            _q1, _q2 = numcol(_prows, 1, len(_prows)), numcol(_prows, 2, len(_prows))
            _paired = any(a is not None and b is not None for a, b in zip(_q1, _q2))
            if len(keep) >= 3 and pr.get('absolute') and '销量' in _phead and _paired:
                out.append(chart('chartProd'))
        _un = unit_note_html(pr)
        if not _un and pr.get('unit'):
            _un = '<p class="src">口径：%s</p>' % pr['unit']
        if _un:
            out.append(_un)
        if pr.get('recycle'):
            rc = pr['recycle']
            out.append(h3('回收网络与产出（护城河的实证）'))
            out.append(table(['维度', '数值'],
                             [[k, str(v)] for k, v in rc.items()]))
        if pr.get('note'):
            out.append(logic('产销解读', pr['note']))
    # ★ 2026-10-11：来源优先级改为 production 在前。槽 7 的主表是产销存表（production），
    #   而 `volprice` 同时被槽 7 / 槽 28 共用、其 source 多为**股价**口径 ——
    #   原来 vp 优先会让本槽的来源行显示成「iFinD 日频行情（不复权）」这类股价说明。
    #   存量数据只有 vp.source 时仍回落，行为不变。
    out.append(src(pr.get('source') or vp.get('source')
                   or '%s —— 待取：最新年报产销量附注。' % MISS))
    return '\n    '.join(out)


def m8(d):
    """8 主要子公司与基地"""
    # ★ 2026-09-21：`subsidiaries` 允许两种形态 ——
    #   ① list  ：直接是行列表（老写法）；
    #   ② dict  ：{"rows": [...], "deep": [...], "source": "…"}（新写法，与其它模块一致）。
    #   历史坑：上面第 633 行用 `g(d,'subsidiaries',default={}).get('source')`，
    #   要求它是 dict；但下面这里又 `for s in subs` 要求它是 list。两者同时存在时，
    #   dict 形态会被 `for s in subs` 迭代成**键名**（'rows'/'deep'/'source'），
    #   于是渲染出一张由 'd'、's' 字母组成的乱码表 —— 存量 002237 的 M8 就中了这个坑。
    #   ⇒ 这里统一在入口判形，两种写法都支持，且不再产生乱码行。
    _subs = d.get('subsidiaries')
    if isinstance(_subs, dict):
        subs = _subs.get('rows') or []
    else:
        subs = _subs or []
    if subs:
        # 子公司在库里有两种行式，列数不同 —— 必须先判形，不能一律按 7 列补 [MISSING]：
        #   7 列：名称 / 基地类型 / 持股 / 定位说明 / 注册资本 / 总资产 / 净资产（定性为主）
        #   8 列：名称 / 类型 / 持股 / 主营 / 注册资本 / 总资产 / 净资产 / 净利润（含财务数）
        # 判据：第 3 列（索引 3）能转成数字 ⇒ 视为财务数列，否则视为定位说明文本列。
        norm, all_rows = [], []
        for s in subs:
            s = list(s)
            v3 = s[3] if len(s) > 3 else ''
            try:
                float(str(v3).replace('%', '').replace(',', '').strip())
                is_fin = True
            except (TypeError, ValueError):
                is_fin = False
            if len(s) >= 8 and is_fin:
                all_rows.append([s[0], s[2]] + [fnum(s[i], 2, ' 亿') for i in range(4, 8)])
            else:
                # 7 列定性行的真实布局： [0]=名称 [1]=基地类型 [2]=（持股，常为空）
                #                        [3]=定位说明 [4..6]=（财务数，常为空）
                # ⇒ 合并策略：拿 [1] 与 [3]（及 [4..] 若有值），组成「基地类型 —— 定位说明」，
                #    而不是只取其中一列、把另一列的信息丢掉。
                parts = []
                for i in (1, 3):
                    v = str(s[i]).strip() if len(s) > i and s[i] not in (None, '') else ''
                    if v and v != '—':
                        parts.append(v)
                for i in range(4, len(s)):
                    v = str(s[i]).strip() if s[i] not in (None, '') else ''
                    if v and v != '—':
                        parts.append(v)
                desc = ' —— '.join(parts) if parts else '—'
                all_rows.append([s[0], desc] + ['' for _ in range(5)])
        # 全列留白的列（如未披露的注册资本/总资产/净资产/营收/净利）不进表格 ——
        # 留着只会铺一屏空白，缺口在下方 subsidiary_note 统一说明。
        base_head = ['主体', '主营业务与定位', '注册资本', '总资产', '净资产', '营业收入', '净利润']
        keep = [0, 1] + [i for i in range(2, 7)
                         if any(str(r[i]).strip() not in ('', '[MISSING]', '—')
                                for r in all_rows)]
        if len(keep) > 2:
            norm = [[r[i] for i in keep] for r in all_rows]
            head = [base_head[i] for i in keep]
        else:
            norm = [[r[0], r[1]] for r in all_rows]
            head = [base_head[0], base_head[1]]
        out = ['<p>主要子公司与基地分布取自年报「主要控股参股公司分析」章节。'
               '判读要点：① 净利润是否由少数子公司贡献（利润集中度）；'
               '② 是否存在亏损拖累的子公司；③ 基地是否与原料/客户地理接近。</p>',
               table(head, norm)]
        if d.get('subsidiary_note'):
            out.append('<p class="muted" style="font-size:12.5px;">%s</p>' % d['subsidiary_note'])
        out += deep(d, 'subsidiaries')
        # ★ 2026-09-20：source 改为数据可覆写（原来写死「基地分布与员工数：[MISSING]」）
        out.append(src(g(d, 'subsidiaries', default={}).get('source')
                       or '最新年报「主要控股参股公司分析」章节。'))
        if d.get('subsidiaries_note') and d['subsidiaries_note'] != d.get('subsidiary_note'):
            out.append('<p class="muted" style="font-size:12.5px;">%s</p>'
                       % d['subsidiaries_note'])
        return '\n    '.join(out)
    return '\n    '.join([
        '<p>主要子公司（名称 / 持股比例 / 主营 / 净利润）与生产基地分布，取自年报'
        '「主要控股参股公司分析」章节。本批次未取，不做推测。</p>',
        '<p style="color:#a3122a">%s 子公司表与基地分布 —— 取最新年报「主要控股参股公司分析」。'
        '判读要点：① 净利润是否由少数子公司贡献（利润集中度）；② 是否存在亏损拖累的子公司；'
        '③ 基地是否与原料/客户地理接近。</p>' % MISS,
        src('%s —— 待取：最新年报「主要控股参股公司分析」章节。' % MISS),
    ])


def m9(d):
    """9 行业总览与市场空间"""
    ind = g(d, 'industry', default={}) or {}
    if isinstance(ind, str):
        ind = {'overview': '', 'rows': [], 'source': ''}
    note = g(d, 'industry_note', default={}) or {}
    rows = ind.get('rows') or []
    has_note = bool(note.get('position') or note.get('domestic')
                    or note.get('pattern') or note.get('industry_data'))
    out = []
    ov = ind.get('overview') or ''
    # 若模板兜底 overview 里只有 [MISSING] 占位，而一手数据已到，就不要让矛盾文案出现
    show_ov = bool(ov) and ('[MISSING]' not in ov or not has_note)
    if show_ov:
        out.append('<p>%s</p>' % ov)
    if has_note:
        out.append('<p>行业介绍与市场规模：本节以公司最新年报「所处行业情况」章节披露的'
                   '行业地位、竞争格局与运行数据为准。</p>')
    elif not show_ov:
        # ⚠️ 原实现这里无条件再输出一次 ov → overview 重复两遍（2026-09-19 修）
        out.append('<p>%s</p>' % (ov or '[MISSING] 行业定义与边界待补。'))
    if note.get('position'):
        out.append(h3('公司行业地位'))
        out.append('<p style="font-size:13.5px;">%s</p>' % note['position'])
    if note.get('pattern'):
        out.append(h3('全球格局'))
        out.append('<p style="font-size:13.5px;">%s</p>' % note['pattern'])
    if note.get('domestic'):
        out.append(h3('国内竞争格局'))
        out.append('<p style="font-size:13.5px;">%s</p>' % note['domestic'])
    if note.get('industry_data'):
        out.append(h3('行业运行数据'))
        out.append('<p style="font-size:13.5px;">%s</p>' % note['industry_data'])
    if note.get('price_env'):
        out.append(h3('价格与政策环境'))
        out.append('<p style="font-size:13.5px;">%s</p>' % note['price_env'])
    if rows:
        out.append(h3('市场规模与增速'))
        out.append(table(['年份', '市场规模', '同比增速', '备注'], rows))
    elif not has_note:
        out.append('<p style="color:#a3122a">[MISSING] 行业规模序列待补 —— '
                   '建议取行业协会年报 / 券商行业深度报告。</p>')
    if ind.get('cagr'):
        out.append('<p><b>未来三年 CAGR：</b>%s</p>' % ind['cagr'])
    if ind.get('drivers'):
        out.append(h3('增长驱动因素'))
        out.append(ul(ind['drivers']))
    if ind.get('size'):
        out.append(chart('chartIndustrySize'))
    out += deep(d, 'industry')
    out.append(src(note.get('source') or ind.get('source') or '[MISSING] 数据来源待补'))
    return '\n    '.join(out)


def m10(d):
    """10 下游需求结构拆解"""
    de = g(d, 'demand', default={}) or {}
    rows = de.get('rows') or []
    out = ['<p>%s</p>' % (de.get('overview') or '[MISSING] 下游结构概述待补。')]
    if rows:
        out.append(h3('下游应用占比'))
        out.append(table(['下游领域', '占比', '增速', '景气判断'], rows))
    else:
        out.append('<p style="color:#a3122a">[MISSING] 下游占比待补 —— '
                   '可从年报「分行业收入」+ 行业协会数据交叉验证。</p>')
    if de.get('pie'):
        out.append(chart('chartDemandMix'))
    if de.get('note'):
        out.append(logic('结构性变化', de['note']))
    out += deep(d, 'demand')
    out.append(src(de.get('source') or '[MISSING] 数据来源待补'))
    return '\n    '.join(out)


def m11(d):
    """11 竞争格局与市场份额"""
    pe = g(d, 'peers', default={}) or {}
    rows = pe.get('rows') or []
    out = ['<p>%s</p>' % (pe.get('overview') or '[MISSING] 竞争格局概述待补。')]
    if rows:
        out.append(h3('可比公司对比'))
        out.append(table(['公司（代码）', '营业收入', '毛利率', '总市值', 'PE', '定位'], rows))
    else:
        out.append('<p style="color:#a3122a">[MISSING] 可比公司表待补。</p>')
    if rows or pe.get('share'):
        out.append(chart('chartShare'))
    if pe.get('position'):
        out.append(logic('公司相对定位', pe['position']))
    out += deep(d, 'peers')
    out.append(src(pe.get('source') or '[MISSING] 数据来源待补'))
    return '\n    '.join(out)


def m12(d):
    """12 管理层与治理"""
    mg = g(d, 'mgmt', default={}) or {}
    rows = mg.get('rows') or []
    out = ['<p>%s</p>' % (mg.get('overview') or '[MISSING] 管理层概述待补。')]
    if rows:
        out.append(h3('核心管理层'))
        out.append(table(['姓名', '职务', '任期', '背景'], rows))
    else:
        out.append('<p style="color:#a3122a">[MISSING] 管理层名单待补 —— '
                   '取最新年报「董事、监事、高级管理人员」章节。</p>')
    if mg.get('incentive'):
        out.append(h3('股权激励与考核'))
        out.append('<p>%s</p>' % mg['incentive'])
    if mg.get('governance'):
        out.append(logic('治理结构特征', mg['governance']))
    out += deep(d, 'mgmt')
    out.append(src(mg.get('source') or '[MISSING] 数据来源待补'))
    return '\n    '.join(out)


def m13(d):
    """13 产业链结构"""
    name = d.get('name') or ''
    note = g(d, 'industry_note', default={}) or {}
    # chain_rows 到位就用一手链条；否则退回「缺口骨架」（只写一处说明，不铺 MISSING 网格）
    rows = note.get('chain_rows')
    out = ['<p>%s 所处产业链的上中下游位置、关键原料自给率与一体化程度。</p>' % name]
    head = note.get('chain_head') or ['环节', '内容', '公司参与度', '备注']
    if rows:
        if note.get('chain'):
            out.append(table(head, [['产业链定位', note['chain'], '—',
                                     '据公司年报「所处行业情况」']] + rows))
        else:
            out.append(table(head, rows))
    else:
        if note.get('chain'):
            out.append(table(head, [['产业链定位', note['chain'], '—',
                                     '据公司年报「所处行业情况」']]))
        out.append('<p style="color:#a3122a">%s 上中下游明细（上游原料/能源、下游客户行业、'
                   '关键原料自给率、纵向一体化程度）—— 取最新年报「经营情况讨论与分析」'
                   '产业链部分与「主要原材料」章节。</p>' % MISS)
    if note.get('position'):
        out.append(logic('行业地位', note['position']))
    out += deep(d, 'industry_note')
    out.append(src(note.get('source') or '%s —— 待取：最新年报「经营情况讨论与分析」产业链部分。' % MISS))
    return '\n    '.join(out)


def m14(d):
    """14 上游原料价格"""
    raw = g(d, 'raw', default={}) or {}
    out = ['<p>原料价格走势、供需平衡与成本传导机制是成本端分析的核心：'
           '对冶炼/加工类企业，**原料与产品的价差**比原料绝对价格更重要。</p>']
    if raw.get('rows'):
        out.append(h3('原料价格与原料格局'))
        out.append(table(raw.get('head') or ['期间'] + (raw.get('series') or ['价格']),
                         raw['rows']))
        # ★ 只有**数值序列（≥3 个点）**才出图。文字口径或两点值出图＝误导性直线。
        if raw.get('numeric'):
            out.append(chart('chartRaw'))
        _un = unit_note_html(raw)
        if _un:
            out.append(_un)
        if raw.get('note'):
            out.append(logic('原料解读', raw['note']))
    else:
        out.append('<p style="color:#a3122a">%s 原料价格走势图与供需平衡表 —— 建议取 iFinD 商品价格、'
                   'Wind 现货价或行业协会报价，并换算成与公司成本口径一致的单位。</p>' % MISS)
    if raw.get('balance'):
        out.append(h3('供需平衡'))
        out.append(table(['品种', '供给', '需求', '缺口', '备注'], raw['balance']))
    if raw.get('transmit'):
        out.append(logic('成本传导', raw['transmit']))
    else:
        out.append(logic('成本传导', '%s —— 需回答：原料涨价能否顺价（定价机制是长协/月度调价/现货）；'
                         '传导滞后期多长；历史上顺价成功率如何（用毛利率与原料价格的错位验证）。'
                         % MISS))
    out.append(src(raw.get('source') or '%s —— 待取：商品价格数据源 + 公司年报成本构成附注。' % MISS))
    out += deep(d, 'raw')
    return '\n    '.join(out)


def m15(d):
    """15 产品价格与成本"""
    pz = g(d, 'pricecost', default={}) or {}
    out = ['<p>产品售价与成本均价构成「剪刀差」，是盈利弹性的直接来源。</p>']
    if pz.get('rows'):
        out.append(h3('售价与成本'))
        out.append(table(pz.get('head') or ['期间', '产品均价', '单位成本', '单位毛利'],
                         pz['rows']))
        # ★ 2026-10-16：与 chart_opts 里的判据**必须一致**（那里建图、这里挂槽）——
        #   表格可以是文字表，但只有真能画才挂槽，否则页面上留一个灰「暂无数据」框。
        #   ★★ 闸也同步放宽成 `need=1`：只有「均价」一列有值的图（000762 就是）在 chart_opts
        #      那边会建出来，这里若仍要求三列齐备就**不挂槽** ⇒ 图建了没人引用 ⇒ 孤儿。
        if numeric_rows(pz.get('chart_rows') or pz.get('rows'), need=1):
            out.append(chart('chartPrice'))
        _un = unit_note_html(pz)
        if _un:
            out.append(_un)
        if pz.get('note'):
            out.append(logic('剪刀差解读', pz['note']))
    elif not (d.get('pricecost') or {}).get('deep'):
        # ★ 2026-10-11：与 m23/m24 保持同一模式 —— 已有 `pricecost.deep` 覆盖该缺口时
        #   不再重复铺一句 [MISSING]，避免「明明有数据还刷缺口」。
        out.append('<p style="color:#a3122a">%s 产品售价-成本均价剪刀差 —— 取公司主要产品的市场报价'
                   '（或年报分产品收入/销量倒算均价）与成本构成。</p>' % MISS)
    if pz.get('elastic'):
        out.append(logic('盈利弹性', pz['elastic']))
    else:
        out.append(logic('盈利弹性', '%s —— 在拿到量价数据后，可测算「产品价格 ±5%% 对净利的弹性倍数」，'
                         '这是判断业绩弹性最直接的指标。' % MISS))
    out.append(src(pz.get('source') or '%s —— 待取。' % MISS))
    out += deep(d, 'pricecost')
    return '\n    '.join(out)


def m16(d):
    """16 在建工程与新项目"""
    name = d.get('name') or ''
    cip = g(d, 'capex', default={}) or {}
    out = ['<p>在建项目（投资额 / 进度 / 投产时间 / 达产效益 / 资金来源）是判断未来增长兑现的关键，'
           '需以年报与公告为准。</p>']
    if cip.get('rows'):
        if cip.get('overview'):
            out.append('<p>%s</p>' % cip['overview'])
        out.append(h3(cip.get('title') or '重大在建项目'))
        base = cip.get('head') or ['项目名称', '投资额', '进度', '预计投产', '达产效益', '资金来源']
        crows = cip['rows']
        # 只保留有真实值的列（投资额/进度等未披露的列不进表格），缺口由 capex.note 统一说明
        keep = [i for i in range(len(base))
                if i == 0 or any(str(r[i]).strip() not in ('', '[MISSING]', '—')
                                 for r in crows if i < len(r))]
        out.append(table([base[i] for i in keep],
                         [[r[i] if i < len(r) else '' for i in keep] for r in crows]))
        if cip.get('note'):
            out.append(logic('项目解读', cip['note']))
    else:
        out.append('<p style="color:#a3122a">%s 在建项目表 —— 取最新年报「重大在建工程」附注 +'
                   '「募集资金使用情况」+ 相关投资公告。</p>' % MISS)
    out.append('<p><b>跟踪方法：</b>把在建工程期末余额的同比变化与「转固节奏」对照 —— '
               '余额上升但迟迟不转固，通常意味着项目延期，需要警惕。</p>')
    out += deep(d, 'capex')
    out.append(src(cip.get('source') or '%s —— 待取：最新年报重大在建工程附注。' % MISS))
    return '\n    '.join(out)


def m17(d):
    """17 护城河与竞争优势量化"""
    fin = g(d, 'fin', default={}) or {}
    years = fin.get('years') or []
    roic = fin.get('roic') or []
    wacc = fin.get('wacc')
    rows = []
    for i, y in enumerate(years):
        v = roic[i] if i < len(roic) else None
        if v is None or wacc is None:
            rows.append([y, fnum(v, 2, '%'), fnum(wacc, 2, '%'), MISS])
        else:
            sp = v - wacc
            c = '#0b8a5c' if sp >= 0 else RED
            rows.append([y, fnum(v, 2, '%'), fnum(wacc, 2, '%'),
                         '<b style="color:%s">%+.2f pct</b>' % (c, sp)])
    out = ['<p>护城河的可量化代理指标是「投入资本回报率 ROIC 与加权平均资本成本 WACC 的利差」：'
           '持续为正说明公司在为股东创造价值，持续为负说明资本回报不足以覆盖资金成本。</p>',
           h3('ROIC 与 WACC 利差'),
           table(['年份', 'ROIC', 'WACC（假设）', '利差'], rows)]
    if fin.get('wacc_note'):
        out.append('<p class="src"><b>WACC 口径：</b>%s</p>' % fin['wacc_note'])
    # ★★ 2026-09-22 修正：`fin['roic_note']` 原本**从未被渲染** —— 各公司手写的
    #   ROIC 口径说明（含「哪一年是 iFinD 披露值、哪一年是模型补算」的关键交代）
    #   全部是死内容。现改为：有 roic_note 就用它，没有才回退到通用近似式说明。
    if fin.get('roic_note'):
        out.append('<p class="src"><b>ROIC 口径：</b>%s</p>' % fin['roic_note'])
    else:
        out.append('<p class="src"><b>ROIC 口径：</b>[模型输出] '
                   'ROIC ≈ ROE ×（1 − 资产负债率）。这是**方向性近似**，'
                   '严格 ROIC = EBIT×(1−t) ÷（有息负债 + 权益），需利息费用与有效税率；'
                   '本批次未取这两项，故用近似值判断趋势而非绝对值。</p>')
    if g(d, 'moat', 'items'):
        out.append(h3('壁垒来源分项'))
        out.append(table(['壁垒维度', '强度', '依据'], g(d, 'moat', 'items')))
    out.append(chart('chartRoic'))
    if g(d, 'moat', 'verdict'):
        out.append(logic('结论', g(d, 'moat', 'verdict')))
    return '\n    '.join(out)


def m18(d):
    """18 风险矩阵"""
    name = d.get('name') or ''
    rk = g(d, 'risk', default={}) or {}
    rows = rk.get('rows') or [
        ['行业景气下行', '中', '高', '营收连续两季同比为负、毛利率环比下滑'],
        ['成本/原料涨价且无法顺价', '中', '高', '毛利率与原料价格背离（原料涨、毛利降）'],
        ['客户集中度风险', MISS, MISS, '前五大客户收入占比（取年报附注）'],
        ['产能投放不及预期', MISS, MISS, '在建工程余额停滞、转固延期'],
        ['环保与安全监管', MISS, MISS, '取年报「环境和社会责任」章节披露的处罚记录'],
        ['估值风险（PE 高企）', '中' if (g(d, 'fin', 'pe') or 0) > 40 else '低', '中',
         '当前 PE(TTM) %s 倍，需业绩兑现消化估值' % fnum(g(d, 'fin', 'pe'), 1, '')],
    ]
    out = ['<p>%s 的风险矩阵。概率与影响为**研判打分**（非披露值），预警信号为可观测的量化阈值 —— '
           '当信号触发即需复核投资逻辑。</p>' % name,
           table(['风险类别', '概率', '影响', '预警信号（可观测）'], rows)]
    if rk.get('events'):
        out.append(h3('已发生风险事件 / 监管记录'))
        out.append(table(['时间', '事件', '性质', '影响与状态'], rk['events']))
    elif rk.get('events_note'):
        out.append(logic('已发生风险事件', rk['events_note']))
    else:
        out.append('<p style="color:#a3122a">%s 已发生风险事件清单 —— 取交易所问询函、'
                   '监管处罚、诉讼公告与年报「重大诉讼」附注。</p>' % MISS)
    out.append(src(rk.get('source') or '风险框架：本模型构建；具体阈值：%s' % MISS))
    return '\n    '.join(out)


def m19(d):
    """19 公司营业收入与利润"""
    t, years, rev, np_ = fin3(d)
    if not years:
        return '<p style="color:#a3122a">[MISSING] 财务序列缺失，无法生成本节。</p>'
    lr = next((v for v in reversed(rev) if v is not None), None)
    ln = next((v for v in reversed(np_) if v is not None), None)
    first_y, last_y = years[0], years[-1]
    out = ['<p>%s~%s 年共 %d 个完整会计年度的营业收入与归母净利如下。'
           '数据全部取自 iFinD 年度口径，单位为亿元。</p>' % (first_y, last_y, len(years)),
           h3('营业收入与归母净利历年表'),
           t]
    if any(v is not None for v in rev):
        out.append(chart('chartRev'))
    if lr is not None and ln is not None:
        # ★ 2026-09-20：归因文本可来自顶层 attribution.text（旧位）或 fin.attribution（新位），
        #   两处都认；都缺才退回那句带 [MISSING] 的模板。
        at = g(d, 'attribution', default={}) or {}
        fa = g(d, 'fin', default={}).get('attribution') or {}
        at_text = at.get('text') or fa.get('x') or ''
        if at_text:
            out.append(logic(fa.get('k') or '业绩归因', at_text))
        else:
            out.append(logic('业绩归因', '最近一个完整年度（%s）营业收入 %s 亿元、归母净利 %s 亿元。'
                             '归因需回答：增长（或下滑）来自量、价、还是并表？'
                             '—— %s 取年报「经营情况讨论与分析」。'
                             % (last_y, fnum(lr, 2), fnum(ln, 2), MISS)))
    out.append(src('iFinD 年度财务报表（合并口径，单位：亿元）。'))
    out += deep(d, 'fin')
    return '\n    '.join(out)


def m20(d):
    """20 公司产品收入与毛利结构"""
    fin = g(d, 'fin', default={}) or {}
    years = fin.get('years') or []
    gm = fin.get('gm') or []
    nm = fin.get('nm') or []
    rows = [[y, fnum(gm[i] if i < len(gm) else None, 2, '%'),
             fnum(nm[i] if i < len(nm) else None, 2, '%')] for i, y in enumerate(years)]
    bz = g(d, 'bizmix', default={}) or {}
    out = []
    if bz.get('rows'):
        out.append('<p>分产品/分板块收入与毛利结构直接决定盈利质量：'
                   '高毛利业务占比提升＝结构优化，低毛利业务放量＝规模虚胖。</p>')
        out.append(h3(bz.get('title') or '分产品收入与毛利结构'))
        out.append(table(bz.get('head') or ['板块', '收入', '占比', '毛利率', '毛利贡献'],
                         bz['rows']))
        # ★ 2026-09-22 修复：「有图无人引用」的孤儿图。
        #   chart_opts 一直在条件化产出 chartMix（收入结构：柱=收入 / 线=毛利率双轴），
        #   但**从没有任何渲染器调用 chart('chartMix')** ⇒ 它会被 push_reports_v31.py
        #   作为孤儿图写进 wb_report_charts（603977 的本轮产物已存在该孤儿行）。
        #   本槽位的语义正是「产品收入与毛利结构」，chartMix 就是它的图，故在此挂载。
        #   无 bizmix 数据时不产出该 option，chart() 只留一个空 div，由壳的
        #   .rpt-slotgone / sweepGoneSlots() 整块隐藏 —— 与其它图槽行为一致。
        out.append(chart('chartMix'))
        if bz.get('note'):
            out.append(logic('结构解读', bz['note']))
    out.append(h3('整体毛利率与净利率'))
    out.append(table(['年份', '销售毛利率', '销售净利率'], rows))
    if any(v is not None for v in gm) or any(v is not None for v in nm):
        out.append(chart('chartMargin'))
    if not bz.get('rows'):
        out.append('<p style="color:#a3122a">%s 分产品收入结构与毛利构成 —— '
                   '取最新年报「主营业务分行业、分产品、分地区情况」附注。'
                   '判读要点：高毛利产品占比是否提升（结构优化）vs 低毛利业务放量（规模虚胖）。</p>'
                   % MISS)
    out.append(src(bz.get('source') or 'iFinD 年度财务指标；分产品结构：%s' % MISS))
    out += deep(d, 'bizmix')
    return '\n    '.join(out)


def m21(d):
    """21 盈利能力与杜邦分解"""
    fin = g(d, 'fin', default={}) or {}
    years = fin.get('years') or []
    roe, nm, lev = fin.get('roe') or [], fin.get('nm') or [], fin.get('lev') or []
    rows = []
    for i, y in enumerate(years):
        r = roe[i] if i < len(roe) else None
        n = nm[i] if i < len(nm) else None
        l = lev[i] if i < len(lev) else None
        if n is None or l is None or l >= 100:
            rows.append([y, fnum(n, 2, '%'), MISS, fnum(l, 2, '%'), fnum(r, 2, '%')])
        else:
            eq = 1.0 / (1 - l / 100.0)      # 权益乘数
            turn = None                     # 资产周转需营收/总资产，本批次无总资产
            rows.append([y, fnum(n, 2, '%'), '—', fnum(eq, 2, 'x'), fnum(r, 2, '%')])
    out = ['<p><b>杜邦分解</b>把 ROE 拆成三个来源：净利率（赚钱效率）× 资产周转（资产效率）× '
           '权益乘数（杠杆）。三者之中杠杆抬升最不可持续 —— 若 ROE 上升完全由权益乘数贡献，'
           '质量最差。</p>',
           h3('ROE 与杜邦三因子'),
           table(['年份', '销售净利率', '总资产周转率', '权益乘数', 'ROE（加权）'], rows),
           '<p class="src">权益乘数 = 1 ÷（1 − 资产负债率），由 iFinD 资产负债率反算。'
           '总资产周转率 = 营业收入 ÷ 总资产，本批次未取总资产余额，故留「—」；'
           '补入总资产后可完整计算。</p>',
           ]
    if any(v is not None for v in (nm or [])):
        out.append(chart('chartMargin'))
    out.append(logic('盈利质量判读', '需回答：① ROE 的变化主要由净利率还是杠杆驱动；'
                     '② 权益乘数若持续上行，说明回报靠加杠杆而非经营改善；'
                     '③ 与同业对比 ROE 的绝对水平与稳定性。'))
    out.append(src('iFinD 年度财务指标（ROE 为加权口径；资产负债率用于反算权益乘数）。'))
    out += deep(d, 'dupont')
    return '\n    '.join(out)


def m22(d):
    """22 费用结构"""
    ex = g(d, 'expense', default={}) or {}

    def filled(rows, i):
        """第 i 列是否有任何一个真实值（空串＝有意留白，不算数据）。"""
        return any(len(r) > i and str(r[i]).strip() not in ('', '[MISSING]') for r in rows)

    rows = ex.get('rows') or []
    has_data = bool(rows) and any(filled(rows, i) for i in (1, 2, 3, 4))
    out = ['<p>四费率（销售 / 管理 / 研发 / 财务）趋势是判断公司经营效率与投入方向的抓手。</p>']
    if has_data:
        out.append(h3('四费率趋势'))
        out.append(table(ex.get('head') or ['年份', '销售费用率', '管理费用率',
                                           '研发费用率', '财务费用率'], rows))
        out.append(chart('chartExp'))
        if ex.get('note'):
            out.append(logic('费用率异动解释', ex['note']))
    else:
        # 未取到就**只写一处缺口说明**，绝不铺一张全是 [MISSING] 的空表
        out.append('<p style="color:#a3122a">%s 四费率趋势表 —— 取 iFinD 或年报三表：'
                   '销售费用率、管理费用率、研发费用率、财务费用率（各自 ÷ 营业收入）。</p>'
                   % MISS)
        if ex.get('note'):
            out.append(logic('为什么这一节值得补', ex['note']))
    out.append(src(ex.get('source') or '%s —— 待取：iFinD 利润表费用科目 + 年报费用附注。' % MISS))
    out += deep(d, 'expense')
    return '\n    '.join(out)


def m23(d):
    """23 现金流与资产负债三表"""
    fin = g(d, 'fin', default={}) or {}
    years = fin.get('years') or []
    np_, ocf, lev = fin.get('np') or [], fin.get('ocf') or [], fin.get('lev') or []
    rows = []
    for i, y in enumerate(years):
        n = np_[i] if i < len(np_) else None
        o = ocf[i] if i < len(ocf) else None
        l = lev[i] if i < len(lev) else None
        if n in (None, 0) or o is None:
            ratio = MISS
        else:
            r = o / n
            c = RED if r >= 1 else '#0b8a5c' if r < 0 else '#8c6b1f'
            ratio = '<b style="color:%s">%.2f</b>' % (c, r)
        rows.append([y, fnum(n, 2, ' 亿'), fnum(o, 2, ' 亿'), ratio, fnum(l, 2, '%')])
    out = ['<p><b>净现比 = 经营现金流净额 ÷ 归母净利润</b>，长期低于 1 说明利润没有变成现金 '
           '（可能是应收账款或存货占用）。本表同时给出资产负债率，用于观察扩张是否靠加杠杆支撑。</p>',
           h3('经营现金流与净现比'),
           table(['年份', '归母净利', '经营活动现金流净额', '净现比', '资产负债率'], rows)]
    if any(v is not None for v in ocf):
        out.append(chart('chartCashflow'))
    # ★ 2026-09-20：原来这里无条件铺一段 [MISSING]（投资/筹资明细）。
    #   现在改成数据驱动：给了 cashflow.flows 就出三表明细表，给了 deep 就挂深度块，
    #   都没有才退回那一句缺口说明 —— 避免「明明有数据还刷 MISSING」。
    cf = g(d, 'cashflow', default={}) or {}
    if cf.get('flows'):
        out.append(h3(cf.get('title') or '投资 / 筹资现金流与营运资本'))
        out.append(table(cf.get('head') or ['年份', '投资活动现金流净额', '筹资活动现金流净额',
                                            '有息负债', '存货', '应收账款'],
                         cf['flows']))
        if cf.get('note'):
            out.append(logic('三表联动解读', cf['note']))
    elif not (d.get('cashflow') or {}).get('deep'):
        # ⚠️ 只有在 deep 块也没覆盖这个缺口时才铺那句话 —— 否则同一缺口会被说两遍。
        out.append('<p style="color:#a3122a">[MISSING] 投资/筹资现金流明细与有息负债、存货、应收账款周转 —— '
                   '取 iFinD 现金流量表全表 + 资产负债表「有息负债」「存货」「应收账款」科目。'
                   '判读要点：经营现金流为负而投资现金流大额流出 = 靠筹资输血扩张，需警惕。</p>')
    cf_deep = deep(d, 'cashflow')
    if cf_deep:
        out.append(h3('三表明细与营运资本：缺口与补齐')) if not cf.get('flows') else None
        out += cf_deep
    out.append(src(cf.get('source') or 'iFinD 年度现金流量表与资产负债率；明细科目：%s' % MISS))
    return '\n    '.join(out)


def m24(d):
    """24 历年分红与股东回报"""
    fin = g(d, 'fin', default={}) or {}
    years = fin.get('years') or []
    dps, eps = fin.get('dps') or [], fin.get('eps') or []
    rows = []
    for i, y in enumerate(years):
        dp = dps[i] if i < len(dps) else None
        ep = eps[i] if i < len(eps) else None
        if dp is None or ep in (None, 0):
            po = MISS
        else:
            po = fnum(dp / ep * 100, 2, '%')
        rows.append([y, fnum(dp, 3, ' 元'), fnum(ep, 3, ' 元'), po])
    out = [h3('历年分红明细'),
           table(['年份', '每股股利', '每股收益', '分红率'], rows)]
    if any(v is not None for v in dps):
        out.insert(0, '<p>公司历年每股股利与每股收益如下；分红率 = 每股股利 ÷ 每股收益。</p>')
        out.append(chart('chartDividend'))
    else:
        out.insert(0, '<p style="color:#a3122a">[MISSING] 历年股利数据缺失 —— '
                      '取 iFinD 分红送转数据或年报「利润分配」章节。</p>')
    dv_deep = deep(d, 'dividend')
    if not dv_deep:
        out.append('<p style="color:#a3122a">[MISSING] 分红政策与累计回报 —— 取最新年报'
                   '「利润分配政策」+ 上市以来累计分红额与累计融资额对比'
                   '（累计分红/累计融资 &gt; 1 才算真正回报股东）。</p>')
    out.append(src('iFinD 每股股利与基本每股收益（年度口径）。'))
    out += dv_deep
    return '\n    '.join(out)


def m25(d):
    """25 盈利预测模型"""
    fc = g(d, 'forecast', default={}) or {}
    cases = fc.get('cases') or {}
    out = ['<p>以下为三档情景假设，<b>假设显式列出、可被证伪</b>。'
           '所有预测均为<b>[模型输出]</b>：由最近一个完整年度的实际营收/净利按固定比例机械外推，'
           '<b>并非基于订单或产能的自下而上测算</b>，不构成业绩承诺。</p>']
    if cases:
        rows = [[k, v.get('assume', ''), v.get('rev', ''), v.get('np', '')] for k, v in cases.items()]
        out.append(h3('三档情景假设'))
        out.append(table(['情景', '核心假设', '次年营收', '次年归母净利'], rows))
    else:
        out.append('<p style="color:#a3122a">[MISSING] 三档假设待补。</p>')
    out.append(chart('chartEstimate'))
    if fc.get('note'):
        out.append(logic('关键敏感变量', fc['note']))
    out.append(src('基准数据：iFinD 年度财报；情景比例为[模型输出]；'
                   '下一轮应以公司公告的产能、订单与价格校准。'))
    return '\n    '.join(out)


def m26(d):
    """26 估值分析"""
    fin = g(d, 'fin', default={}) or {}
    yv = g(d, 'valuation', default={}) or {}
    rows = [
        ['最新股价', fnum(fin.get('price'), 2, ' 元'), 'iFinD（时点见文首徽标）'],
        ['总市值', fnum(fin.get('mktcap'), 2, ' 亿元'), 'iFinD'],
        ['PE（TTM）', fnum(fin.get('pe'), 2, ' 倍'), 'iFinD，TTM 口径'],
        ['PB（MRQ）', fnum(fin.get('pb'), 2, ' 倍'), 'iFinD'],
    ]
    out = ['<p>本节给出当前估值快照。PE 采用 <b>TTM 口径</b>（滚动 12 个月），'
           '与部分数据源的「上年年报口径」不同，比较时需注意口径一致。</p>',
           h3('当前估值快照'),
           table(['指标', '数值', '口径/来源'], rows)]
    if yv.get('rows'):
        out.append(h3(yv.get('section') or '估值区间'))
        # ★ 2026-10-16：表头不能再写死 —— `valuation.rows` 有两种口径：
        #   ① **估值速览表**（指标 | 数值 | 来源，如 000762）—— 不是时间序列；
        #   ② **PE/PB 时间序列**（时点 | PE | PB | 备注，如 603227）。
        #   写死「年份 | PE | PB | 备注」会把 ① 挂在 PE/PB 的表头下面（张冠李戴）。
        #   ⇒ 优先用 seed 自带的 `valuation.head`，没有才回落原表头（存量报告行为不变）。
        out.append(table(yv.get('head') or ['年份', 'PE', 'PB', '备注'], yv['rows']))
        out.append(chart('chartValuation'))
        if yv.get('chart_rows_note'):
            out.append(logic('估值区间口径', yv['chart_rows_note']))
    else:
        out.append('<p style="color:#a3122a">[MISSING] 历史 PE/PB 区间序列 —— '
                   '取 iFinD 或 Wind 估值分位数据（建议给近 5 年分位数）。'
                   '有了历史区间才能判断当前估值处于什么位置。</p>')
    out.append(logic('估值方法选择与目标价推导',
                     '[模型输出] 对周期/制造业公司，PE 法需配合盈利中枢使用，'
                     '单独看单年 PE 容易被利润波动误导。目标价推导需同时锚定'
                     '「盈利中枢」与「合理倍数」两个假设，任一假设变化都会显著改变结果，'
                     '故本报告只给出估值区间判断，不给出单一目标价。'))
    # ★ 2026-09-20：给了 valuation.hist（日频精确序列 + 分位数）就出一张实测表，
    #   替代原先「有行无源」的近似区间说明。
    hv = yv.get('hist') or {}
    if hv.get('rows'):
        out.append(h3('历史估值分位（iFinD 日频精确序列）'))
        out.append(table(hv.get('head') or ['时点', 'PE(TTM)', 'PB(MRQ)'], hv['rows']))
        st = hv.get('stats') or {}
        if st:
            out.append(table(['统计量', '数值'],
                             [[k, str(v)] for k, v in st.items()]))
        if hv.get('note'):
            out.append(logic('分位数告诉我们什么', hv['note']))
    out += deep(d, 'valuation')
    out.append(src(yv.get('source') or 'iFinD 估值指标（PE 为 TTM 口径）历史区间：%s' % MISS))
    return '\n    '.join(out)


def m27(d):
    """27 估值敏感性"""
    se = g(d, 'sens', default={}) or {}
    mat = se.get('matrix') or {}
    out = ['<p>%s</p>' % (se.get('overview') or
                          '[模型输出] 以近一年 EPS 与当前 PE 为基准做敏感性测试。')]
    if mat.get('cols') and mat.get('rows'):
        head = ['目标 PE \\ 净利偏离'] + list(mat['cols'])
        body = [[r[0]] + list(r[1:]) for r in mat['rows']]
        out.append(h3(mat.get('title') or '敏感性矩阵'))
        out.append(table(head, body))
    else:
        out.append('<p style="color:#a3122a">[MISSING] 敏感性矩阵待补 —— '
                   '需至少拿到 EPS 与当前 PE。</p>')
    # ⚠️ 条件化：没有热力图数据就不放槽位，否则页面上会留一个灰色「暂无数据」框
    if (se.get('heat') or {}).get('data'):
        out.append(chart('chartSens'))
    if se.get('margin'):
        out.append(logic('安全边际', se['margin']))
    out.append(src('[模型输出] 基准 EPS 取自 iFinD 基本每股收益，'
                   'PE 倍数区间以当前 PE 为中枢上下浮动；矩阵为机械计算，非目标价推荐。'))
    return '\n    '.join(out)


def m28(d):
    """28 公司股价表现"""
    fin = g(d, 'fin', default={}) or {}
    vp = g(d, 'volprice', default={}) or {}
    # ★ 同 chartPrice2：股价口径优先取 `price_rows`（存量研报无此键 ⇒ 回落 rows，行为不变）
    prow = vp.get('price_rows') or vp.get('rows')
    out = []
    if prow:
        out.append('<p>股价表现与估值快照一起看：估值是「贵不贵」，股价位置是「市场已经走了多远」。'
                   '下表区间为 %s。</p>' % (vp.get('span') or '近一年'))
        out.append(chart('chartPrice2'))
        out.append(table(vp.get('price_head') or vp.get('head')
                         or ['期间', '收盘价（元）', '成交额（亿元）', '区间涨跌'], prow))
        # ★ 2026-10-16：新增可选键 `price_note` / `price_source` 专供本槽。
        #   起因：本槽与槽 7（量价拆分）共用 `note` / `source`，而两者的**解读对象不同**
        #   —— 槽 7 讲「量价」，本槽讲「股价」。603227 曾因此把「硝酸铵价格解读」挂在
        #   「行情解读」标题下（标题与内容不符）。给了新键就用新键，没给仍回落旧键 ⇒ 存量行为不变。
        if vp.get('price_note') or vp.get('note'):
            out.append(logic('行情解读', vp.get('price_note') or vp['note']))
    else:
        out.append('<p>本节需日频股价序列（用于计算区间涨跌幅与技术位置）。'
                   '本批次只取了估值快照，未取 K 线序列。</p>')
    out.append(table(['指标', '数值', '来源'],
                     [['最新价', fnum(fin.get('price'), 2, ' 元'), 'iFinD'],
                      ['总市值', fnum(fin.get('mktcap'), 2, ' 亿元'), 'iFinD'],
                      ['PE（TTM）', fnum(fin.get('pe'), 2, ' 倍'), 'iFinD'],
                      ['PB（MRQ）', fnum(fin.get('pb'), 2, ' 倍'), 'iFinD']]))
    if not prow:
        # ★ 2026-10-11：判据与上面的 `prow = vp.get('price_rows') or vp.get('rows')` 对齐。
        #   原来只查 `rows`，导致「只提供 price_rows」的新报告在股价表与图都已渲染的情况下
        #   仍多刷一句缺口说明。
        out.append('<p style="color:#a3122a">%s 股价走势图与区间涨跌 —— '
                   '取 iFinD 或腾讯行情日频数据（前复权）。</p>' % MISS)
    out.append(src(vp.get('price_source') or vp.get('source')
                   or 'iFinD 估值快照；日频行情：%s' % MISS))
    return '\n    '.join(out)


def m29(d):
    """29 企业评分（选股原则 10 项 · 满分 100）

    ★★★ 本模块**已锁死**（2026-09-22 用户指令：「企业评分的模块锁死，不要每次都改」）。
        模块结构与文案的唯一真源 = ``build/score_lock.py``；本函数只负责把数据喂进去。
        **禁止**在这里重新拼表格、改项名 / 权重、或另起一套评分规则。
        数据侧只认 ``score.kpi``（KPI 卡 8 格）/ ``score.h1``（报告期三格）/
        ``score.date`` / ``score.period`` / ``score.notes``（逐项实测说明，可选）/
        ``score.scores`` + ``score.total`` + ``score.rating``（自动评分结果，可选）。
        ``scores`` 给满 10 个数字即出「有分」形态；不给则保持「空分」等填形态。
        ⚠️ 历史遗留的 ``score.items`` 覆写口子**已作废** —— 那正是「每次都改」的成因；
        数据里出现即告警（不报错，避免打断别人的构建）。
    """
    sc = g(d, 'score', default={}) or {}
    if sc.get('items'):
        sys.stderr.write(
            '[score-lock] 告警：%s 仍带 score.items（已作废、被忽略）。'
            '槽 29 已锁死，项名与权重只能来自 build/score_lock.py。\n' % d.get('code'))
    fin = g(d, 'fin', default={}) or {}
    kpi = SL.kpi_from_fin(fin, sc)
    out = [SL.render(kpi=kpi, period=sc.get('period') or '',
                     notes=sc.get('notes'), scores=sc.get('scores'),
                     total=sc.get('total'), rating=sc.get('rating'))]
    out += deep(d, 'score')
    return '\n    '.join(out)


def m30(d):
    """30 多空论点对照"""
    bb = g(d, 'bullbear', default={}) or {}
    bull = bb.get('bull') or []
    bear = bb.get('bear') or []
    out = ['<p>把多空双方的论点与验证指标并排列出：<b>多方论点给出验证指标，'
           '空方论点给出证伪信号</b>。</p>']
    if bull:
        out.append(h3('多方论点（Bull）'))
        out.append(table(['论点', '验证指标', '当前状态'], bull))
    if bear:
        out.append(h3('空方论点（Bear）'))
        out.append(table(['论点', '证伪信号', '当前状态'], bear))
    if bb.get('tilt'):
        out.append(logic('当前天平倾向', bb['tilt']))
    out += deep(d, 'bullbear')
    return '\n    '.join(out)


def m31(d):
    """31 投资结论与跟踪清单"""
    fin = g(d, 'fin', default={}) or {}
    name = d.get('name') or ''
    code = d.get('code') or ''
    years = fin.get('years') or []
    rev = fin.get('rev') or []
    np_ = fin.get('np') or []
    lr = next((v for v in reversed(rev) if v is not None), None)
    ln = next((v for v in reversed(np_) if v is not None), None)
    pe = fin.get('pe')
    # 结论方向只能从客观数据推，不下买卖建议
    tilt = ''
    if pe is not None and ln is not None:
        if pe > 60:
            tilt = '估值处于高位（PE TTM %s 倍），需要业绩高增长才能消化——' % fnum(pe, 1, '')
        elif pe > 0:
            tilt = '估值处于中性区间（PE TTM %s 倍）——' % fnum(pe, 1, '')
        else:
            tilt = 'PE 为负（公司当前处于亏损状态，TTM PE %s 倍）——' % fnum(pe, 1, '')
    ccl = g(d, 'conclusion', default={}) or {}
    deep_html = '\n    '.join(deep(d, 'conclusion'))
    return '\n    '.join([
        '<p><b>一句话结论：</b>%s%s 最近一个完整年度（%s）营业收入 %s 亿元、归母净利 %s 亿元。'
        '%s</p>'
        % (tilt, name, years[-1] if years else MISS,
           fnum(lr, 2), fnum(ln, 2),
           ccl.get('verdict') or
           '本节给出**跟踪清单与复核触发条件**；因本报告尚未完成行业规模、管理层、'
           '竞争优势等一手资料补充，故**不给出评级与目标价**。'),
        h3('跟踪清单（下一轮必须补齐）'),
        table(['优先级', '待补内容', '获取路径'],
              ccl.get('todo') or
              [['高', '行业规模与增速序列（M24）', '行业协会年报 / 券商行业深度'],
               ['高', '可比公司营收与毛利率（M21）', 'iFinD 同业对比 / 年报'],
               ['高', '分产品收入结构（M5/M11）', '年报「分产品」附注'],
               ['高', '管理层名单与治理（M9）', '年报「董监高」章节'],
               ['中', '产能利用率与在建项目（M6/M17）', '年报「生产能力」「在建工程」附注'],
               ['中', '四费率趋势（M14）', 'iFinD 利润表费用科目'],
               ['中', '历史 PE/PB 分位（M28）', 'iFinD / Wind 估值分位'],
               ['低', '下游需求结构与份额演变（M20/M21）', '行业协会 + 公司公告']]),
        h3('复核触发条件（命中任一即需重估）'),
        ul(ccl.get('triggers') or
           ['单季营业收入同比连续两期为负',
            '毛利率同比下滑超过 3 个百分点',
            '净现比连续两年低于 0.5（利润未变现）',
            '资产负债率同比上升超过 10 个百分点（加杠杆扩张）',
            'PE(TTM) 突破历史 80 分位而盈利未见加速']),
        h3('第一优先级观测指标'),
        table(['指标', '最近值', '阈值/方向'],
              ccl.get('watch') or
              [['营业收入（最近年度）', fnum(lr, 2, ' 亿元'), '同比增速转负即预警'],
               ['归母净利（最近年度）', fnum(ln, 2, ' 亿元'), '同比增速转负即预警'],
               ['销售毛利率', fnum(next((v for v in reversed(fin.get('gm') or []) if v is not None), None), 2, '%'), '同比下降 3pct 即复核'],
               ['资产负债率', fnum(next((v for v in reversed(fin.get('lev') or []) if v is not None), None), 2, '%'), '同比 +10pct 即复核'],
               ['PE（TTM）', fnum(pe, 2, ' 倍'), '突破历史 80 分位即复核']]),
        deep_html or '',
        # ★ 2026-10-15：原文在此处**字面写出「[MISSING]」三个字**。
        #   它是给人读的说明文案，不是真正的数据缺口 ——
        #   但探针/构建器按 `html.count('[MISSING]')` 统计缺口数，
        #   于是**任何报告都永远不可能降到 0**（西藏矿业补齐后仍剩 1 处即此）。
        #   改用「MISSING 标记」这一中文说法，语义不变，计数归零。
        '<p class="src"><b>免责声明</b>：本报告由数据流水线自动生成，'
        '所有数字均标注来源；未取到的字段一律标注为 MISSING 占位并在跟踪清单中列出补齐路径。'
        '本报告仅供研究参考，<b>不构成个人投资建议</b>。</p>',
    ])


# ------------------------------------------------- 宝钛母本新增的三个槽位（2026-09-21）
def m_res(d):
    """25 产量储量分布及价格分析（宝钛母本「行业篇」第二块）。

    数据块 `resource`（字段全部可选；缺哪块只缺哪块，绝不编造）：
        {
          "overview":   "一句话结论",
          "title":      "资源储量与产量分布",
          "head":       ["国家/地区", "储量", "储量占比", "产量", "产量占比"],
          "rows":       [["中国", "21,000", "23.5%", "325.0", "约 30%"], ...],
          "price_title":"资源价格走势",
          "price_head": ["时点", "价格"],
          "price_rows": [["2026-08", 825], ...],
          "price_unit": "元/克",
          "note":       "禀赋与产出错配的解读",
          "price_note": "价格与成本传导的解读",
          "note_title": "禀赋与产出的错配（默认；化肥/化工类无矿产禀赋，改写成本题）",
          "miss_hint":   "数据缺失时给出的『去哪取』提示（默认按矿产资源写）",
          "source":     "USGS / 行业协会年报 / iFinD"
        }
    另有**两个地图块（2026-10-14 起为「必配」，不再是可选）**：母本 600456 m25 的
    第一屏就是世界地图。★ 用户令：「这个里面的世界地图和中国地图的分布图**必须每份研报都要**，
    有储量比如矿企的**储量和产量分布图都要**，没有储量的比如化工或者农产品企业**就用产量分布图**」
    ⇒ 有储量的：储量走地图、产量走对比（chartResDist 双轴）；无储量的（化工/农产品）：
    两张地图直接换主题为「产量 / 产能的地理分布」（按国家 / 按省的真实产量或产能，
    **不是**"工艺路线"——旧注释那句「不要硬套地图」已作废）：
        "world_map": {"slot","title","label","unit","total","total_word","nodata",
                      "values":[["South Africa","南非",63000],…],"tiers":[…],
                      "pos":{…},"small":[…],"no_label":[…],"note":"口径说明"}
        "cn_map":    同 world_map，多三个排版字段：
                      "head"/"rows"（分省表）、"table_note"（表下口径提示）、
                      "reading"（这张图最该注意的一件事）
    ★ 判据（写数据时照此）：储量与产量必须给**同一份国家名单**，才能看出「谁有矿」与
      「谁在挖」是两份不同的名单 —— 这正是宝钛母本 m25 的核心论点。
    ⚠️ 化肥/化工这类**没有矿产禀赋**的行业：标题、地图 `label` 与 `miss_hint` 都要改写成本行业的
      「产量 / 产能分布 + 价格分析」，**地图照画**（按国家 / 按省的真实产量或产能）——
      既避免误导读者去找一份并不存在的储量表，也不漏掉必配的两张地图。
    """
    rs = g(d, 'resource', default={}) or {}
    hint = rs.get('miss_hint') or (
        '取 USGS Mineral Commodity Summaries 或行业协会年报，'
        '按「国家 / 储量 / 储量占比 / 产量 / 产量占比」逐行列出。'
        '判读要点：储量大国是否等于产量大国（错配处即定价权所在）。')
    out = []
    if rs.get('overview'):
        out.append('<p>%s</p>' % rs['overview'])
    # ★★★ 储量地图（世界 / 中国）—— 母本 m25 的**第一屏就是世界地图**，让读者先看见
    #     分布、再读表格。数据契约见 res_map_charts()；没有该数据块就整段不出现
    #     （不写占位、不留空框）。
    #     ★ 地图**不单独起标题**：与下面的表格共用同一个 h3 —— 这正是母本 600456 的
    #       样子（上图下表一个标题）。各自起标题会并排出现两个几乎一样的小标题。
    wm = rs.get('world_map') or {}
    has_wm = bool(wm.get('slot') and wm.get('values'))
    if rs.get('rows') or has_wm:
        out.append(h3(rs.get('title') or wm.get('title') or '资源储量与产量分布'))
        if has_wm:
            out.append(chart(wm['slot'], height=470))
            if wm.get('note'):
                out.append('<p class="muted" style="font-size:12.5px;">%s</p>' % wm['note'])
        if rs.get('rows'):
            out.append(table(rs.get('head')
                             or ['国家/地区', '储量', '储量占比', '产量', '产量占比'], rs['rows']))
            out.append(chart('chartResDist'))
            if rs.get('note'):
                out.append(logic(rs.get('note_title') or '禀赋与产出的错配', rs['note']))
    else:
        out.append('<p style="color:#a3122a">%s 产量与价格分布 —— %s</p>' % (MISS, hint))
    # 中国分省储量分布（母本在「错配」之后、价格之前放这一节）
    cmm = rs.get('cn_map') or {}
    if cmm.get('slot') and cmm.get('values'):
        if cmm.get('title'):
            out.append(h3(cmm['title']))
        out.append(chart(cmm['slot'], height=470))
        if cmm.get('note'):
            out.append('<p class="muted" style="font-size:12.5px;">%s</p>' % cmm['note'])
        if cmm.get('head') and cmm.get('rows'):
            out.append(table(cmm['head'], cmm['rows']))
        if cmm.get('table_note'):
            out.append('<p class="muted" style="font-size:12.5px;">%s</p>' % cmm['table_note'])
        if cmm.get('reading'):
            out.append('<p>%s</p>' % cmm['reading'])
    if rs.get('price_rows'):
        out.append(h3(rs.get('price_title') or '资源价格走势'))
        out.append(table(rs.get('price_head') or ['时点', '价格'], rs['price_rows']))
        out.append(chart('chartResPrice'))
        if rs.get('price_note'):
            out.append(logic('价格与成本传导', rs['price_note']))
    else:
        out.append('<p style="color:#a3122a">%s 资源价格序列 —— '
                   '取 iFinD 商品价格或行业协会挂牌价，给月度/年度序列。</p>' % MISS)
    out += deep(d, 'resource')
    out.append(src(rs.get('source') or 'USGS / 行业协会年报 / iFinD；%s' % MISS))
    return '\n    '.join(out)


def m_sdbalance(d):
    """26 供需格局与平衡表（宝钛母本「行业篇」第三块）。

    数据块 `sdbalance`（字段全部可选）：
        {
          "overview":     "一句话结论",
          "supply_head":  ["环节", "产能/产量", "集中度"], "supply_rows": [...],
          "demand_head":  ["下游", "需求占比", "增速"],    "demand_rows": [...],
          "bal_head":     ["年份", "供给", "需求", "缺口/过剩"], "bal_rows": [...],
          "note":         "平衡表解读",
          "miss_hint":    "数据缺失时的『去哪取』提示",
          "source":       "来源"
        }
    ★ 判据：平衡表那一格必须能用一句话概括（宝钛母本是「低端化工级过剩、高端航空级紧缺」），
      否则这张表没有信息量，就是在凑页数。
    """
    sb = g(d, 'sdbalance', default={}) or {}
    out = []
    if sb.get('overview'):
        out.append('<p>%s</p>' % sb['overview'])
    if sb.get('supply_rows'):
        out.append(h3(sb.get('supply_title') or '供给侧结构'))
        out.append(table(sb.get('supply_head') or ['环节', '产能/产量', '集中度'],
                         sb['supply_rows']))
    if sb.get('demand_rows'):
        out.append(h3(sb.get('demand_title') or '需求侧结构'))
        out.append(table(sb.get('demand_head') or ['下游', '需求占比', '增速'],
                         sb['demand_rows']))
    if sb.get('bal_rows'):
        out.append(h3(sb.get('bal_title') or '供需平衡表'))
        out.append(table(sb.get('bal_head') or ['年份', '供给', '需求', '缺口/过剩'],
                         sb['bal_rows']))
        out.append(chart('chartSDBalance'))
        # ★ 2026-10-16：把**定性**的说明从数值表里挪出来（原来混在 bal_rows 里 ⇒
        #   列 1 是区间文字、列 2 是「100%」字符串 ⇒ 图一行也取不到）。
        if sb.get('bal_note'):
            out.append('<p class="src">口径：%s</p>' % sb['bal_note'])
        if sb.get('note'):
            out.append(logic('平衡表告诉我们什么', sb['note']))
    if not (sb.get('supply_rows') or sb.get('demand_rows') or sb.get('bal_rows')):
        out.append('<p style="color:#a3122a">%s 供需格局与平衡表 —— %s</p>'
                   % (MISS, sb.get('miss_hint')
                      or '取行业协会年报（产能/产量/表观消费量）+ 海关进出口数据库，'
                         '做成「年份 / 供给 / 需求 / 缺口或过剩」四列表。'
                         '判据：这一格必须能用一句话概括（如「低端过剩、高端紧缺」），'
                         '否则没有信息量。'))
    out += deep(d, 'sdbalance')
    out.append(src(sb.get('source') or '行业协会年报 + 海关进出口数据；%s' % MISS))
    return '\n    '.join(out)


def m_val(d):
    """28 估值分析 —— 宝钛母本把「估值 + 股价表现」合成**一节**。

    组成：渲染器 m26（估值快照 / 历史区间 / 分位 / 目标价推导）
        + m28（区间股价表现）。
    两块各自条件化：没数据的块自己回落成 [MISSING] 并给出补齐路径。
    ⚠️ m26 内部已经挂载了 deep(d,'valuation')，这里**不要**再挂一次（会重复）。

    ★ 2026-09-21：按用户要求**摘除「估值敏感性」小节**（原 m27 那一整块：
      敏感性矩阵表 + chartSens 热力图 + 安全边际 + 其 source 段）。
      m27 函数体保留但**不再被任何槽调用**（POS2RENDER 里 28→m_val，不含 m27），
      chartSens 的 option 也一并在 chart_opts 里停用 —— 三处必须同时改，
      只删调用会让库里留下没人引用的孤儿图。
    """
    out = [m26(d)]
    body = (m28(d) or '').strip()
    if body:
        out.append(h3('区间股价表现'))
        out.append(body)
    return '\n    '.join(x for x in out if x)


# ★ 2026-09-21：槽位→渲染器改由模板的 POS2RENDER 驱动（宝钛母本顺序），不再手写 1:1。
#   第 9 槽→m12、10-16 槽→m19/m20/m15/m21/m22/m23/m24、20-23 槽→m10/m11/m13/m14、
#   24 槽→m9、25/26 槽→m_res/m_sdbalance、27 槽→m25、28 槽→m_val（合并三个渲染器）。
RENDER = {}
for _no, _fn in sorted(POS2RENDER.items()):
    _f = globals().get(_fn)
    assert callable(_f), 'POS2RENDER[%d] 指向的渲染器 %s 不存在' % (_no, _fn)
    RENDER[_no] = _f
assert sorted(RENDER) == list(range(1, 32)), '渲染器必须覆盖 1..31'


# ------------------------------------------------------------------ 图表 option
def num(n):
    return round(float(n), 4)


def res_map_charts(d):
    """25 槽的两张地图（**世界储量分布** / **中国分省储量分布**）的 option。

    ★ 为什么要走 `chartmap.MapKit`：底图（自建国标中国版图 + 九段线）、分档铺色、
      标签避让、tooltip 令牌这几个坑都在那个模块里被断言过一遍
      （见 `build/README_地图批量出图.md`）。这里只负责把**数据翻译成入参**，
      **不写第二份 option 逻辑** —— 抄一份就多一个会漂的地方。

    数据契约（挂在 `resource` 下；缺哪张就不出哪张，绝不编造）：
        resource.world_map = {
            "slot":  "chartPgmWorldMap",       # 图槽名（必填，必须与 m_res 里引用的一致）
            "label": "铂族金属（PGM）储量",      # tooltip 指标名（下发到壳，换矿种不用改壳）
            "unit":  "吨",
            "total": 76200,                    # 占比分母；不给 ⇒ 用各值之和
            "total_word": "占全球",
            "nodata": "USGS 2025 年统计未单独列示",
            "values": [["South Africa", "南非", 63000], ...],  # 英文名 / 中文名 / 值
            "tiers":  [[20000, "#a30f24"], ...],               # 降序 [下限, 色]
            "pos":    {"Zimbabwe": "right"},                   # 可选：标签朝向覆盖
            "small":  [...], "no_label": [...],                # 可选：字号 / 完全关标签
            "zoom_max": 14, "layout_size": "100%",
        }
        resource.cn_map = { ...同上，但 values = [["甘肃", "甘肃", 56.31], ...] }

    ⚠️ 分母（`total`）与 `values` 之和**允许不等**（世界图常有「其他国家和地区」），
       但要写进 note 说清口径 —— 否则占比看着像算错了。
    """
    ch = {}
    rs = g(d, 'resource', default={}) or {}
    for blk, mode in (('world_map', 'world'), ('cn_map', 'china')):
        mm = rs.get(blk) or {}
        slot = mm.get('slot')
        vals = mm.get('values') or []
        if not (slot and vals):
            continue
        rows = []
        for v in vals:
            if len(v) >= 3 and v[2] is not None:
                rows.append((v[0], v[1] if len(v) > 1 else v[0], v[2]))
        if not rows:
            continue
        cm = chartmap.MapKit(LIB_DIR, mode=mode)
        if mm.get('tiers'):
            cm.tiers = [tuple(t) for t in mm['tiers']]
        cm.tooltip_label = mm.get('label') or cm.tooltip_label
        cm.tooltip_unit = mm.get('unit') or cm.tooltip_unit
        cm.tooltip_total = mm.get('total_word') or cm.tooltip_total
        cm.tooltip_base = float(mm.get('total') or 0)      # 0 ⇒ 壳用各值之和当分母
        cm.tooltip_nodata = mm.get('nodata') or ''
        if mm.get('short'):
            cm.tooltip_short = mm['short']
        if mm.get('zoom_max'):
            cm.zoom_max = mm['zoom_max']
        if mm.get('layout_size'):
            cm.layout_size = mm['layout_size']
        if mm.get('layout_center'):
            cm.layout_center = mm['layout_center']
        # ★★★ 母本默认为**钛铁矿的地理**调过（世界图的 no_label 里关掉了五个小国、
        #     中国图的 no_label 里是「甘肃/河南」）—— 换矿种直接继承会**把最大的那个省
        #     关掉标签**（贵研的甘肃占全国 69.6%、恒邦的甘肃储量全国第二，都会被关）。
        #     所以 no_label / small 必须按本次数据重定；pos 只在默认表上**增量覆盖**。
        cm.no_label = set(mm.get('no_label') or ())
        cm.small = set(mm.get('small') or ())
        cm.pos.update(mm.get('pos') or {})
        ch[slot] = cm.option(rows)
    return ch


def res_sd_charts(d):
    """25/26 两槽的三个图：chartResDist / chartResPrice / chartSDBalance。

    ⚠️ 为什么单独抽出来：**补数脚本需要「只重渲染 25/26 两槽」**。
    存量公司（000731/000830）的 seed 是搬家来的、data_v31 是薄文件，
    整份 `build()` 会得到一份变薄的报告 ⇒ 补数只能「算两槽 html + 取这三个图」，
    不能重跑 build。把这段从 chart_opts 里抽出来，补数脚本就能 `import` 复用，
    不必把 option 逻辑抄第二份（抄一份就多一个会漂的地方）。

    图表命名契约（★ 非矿产行业必须显式给，否则轴名会错标成「储量/产量」）：
        resource.axis_names      = ["<轴1名>", "<轴2名>"]  → chartResDist 的双 xAxis 与系列名
        sdbalance.bal_series_names = ["<供给名>", "<需求名>"] → chartSDBalance 系列名
    默认值保持母本口径（储量/产量、供给/需求）。
    """
    ch = {}
    # 25 资源/产能分布 + 价格走势（渲染器 m_res）
    # ★ 条件化：没有数值列就不放槽，避免页面上留灰色「暂无数据」框。
    rs = g(d, 'resource', default={}) or {}
    ch.update(res_map_charts(d))       # 25 槽的两张储量地图（有 world_map/cn_map 才出）
    if rs.get('rows'):
        an = list(rs.get('axis_names') or ['储量', '产量'])
        while len(an) < 2:
            an.append('—')
        ch['chartResDist'] = {
            'tooltip': {'trigger': 'axis'},
            'legend': {'bottom': 0},
            'grid': {'left': 90, 'right': 70, 'top': 30, 'bottom': 40},
            'xAxis': [{'type': 'value', 'name': an[0]},
                      {'type': 'value', 'name': an[1]}],
            'yAxis': {'type': 'category', 'inverse': True,
                      'data': [r[0] for r in rs['rows']]},
            'series': [
                {'name': an[0], 'type': 'bar', 'xAxisIndex': 0,
                 'data': numcol(rs['rows'], 1, len(rs['rows'])),
                 'itemStyle': {'color': RED}},
                {'name': an[1], 'type': 'bar', 'xAxisIndex': 1,
                 'data': numcol(rs['rows'], 3, len(rs['rows'])),
                 'itemStyle': {'color': '#00b0f0'}}]}
    if rs.get('price_rows'):
        ch['chartResPrice'] = {
            'tooltip': {'trigger': 'axis'}, 'legend': {'bottom': 0},
            'grid': {'left': 66, 'right': 40, 'top': 30, 'bottom': 46},
            'xAxis': {'type': 'category', 'data': [str(r[0]) for r in rs['price_rows']],
                      'axisLabel': {'interval': 0, 'rotate': 30, 'fontSize': 10}},
            'yAxis': {'type': 'value', 'name': rs.get('price_unit') or ''},
            'series': [{'name': rs.get('price_title') or '价格', 'type': 'line',
                        'smooth': True,
                        'data': numcol(rs['price_rows'], 1, len(rs['price_rows'])),
                        'itemStyle': {'color': RED}, 'lineStyle': {'width': 3},
                        'areaStyle': {'opacity': 0.10}}]}

    # 26 供需 / 价差（渲染器 m_sdbalance）
    sb = g(d, 'sdbalance', default={}) or {}
    if sb.get('bal_rows'):
        sn = list(sb.get('bal_series_names') or ['供给', '需求'])
        while len(sn) < 2:
            sn.append('—')
        ch['chartSDBalance'] = {
            'tooltip': {'trigger': 'axis'}, 'legend': {'bottom': 0},
            'grid': {'left': 70, 'right': 50, 'top': 30, 'bottom': 44},
            'xAxis': {'type': 'category', 'data': [str(r[0]) for r in sb['bal_rows']]},
            'yAxis': {'type': 'value'},
            'series': [
                {'name': sn[0], 'type': 'bar',
                 'data': numcol(sb['bal_rows'], 1, len(sb['bal_rows'])),
                 'itemStyle': {'color': '#00b0f0'}},
                {'name': sn[1], 'type': 'bar',
                 'data': numcol(sb['bal_rows'], 2, len(sb['bal_rows'])),
                 'itemStyle': {'color': RED}}]}
    return ch


def chart_opts(d):
    """按可用数据条件化生成图表 option —— 没数据的图**不放**（避免页面灰框）。"""
    ch = {}
    fin = g(d, 'fin', default={}) or {}
    yrs = fin.get('years') or []
    code = d.get('code') or ''
    name = d.get('name') or ''

    # 1 营收与归母净利
    # ★ 2026-10-14 用户口径：**营收与净利都画柱状图，各占左右一个坐标轴**
    #   （原来净利是叠加在同一根轴上的金色折线，量级差 ~10 倍、被压在 x 轴上几乎看不出高低）。
    #   左轴＝营业收入，右轴＝归母净利，两者都是柱；轴名/轴色/网格线由页面 beauty() 按系列色自动接管。
    if fin.get('rev'):
        ch['chartRev'] = {
            'tooltip': {'trigger': 'axis'}, 'legend': {'bottom': 0},
            'grid': {'left': 64, 'right': 68, 'top': 34, 'bottom': 40},
            'xAxis': {'type': 'category', 'data': yrs},
            'yAxis': [{'type': 'value', 'name': '营业收入（亿元）'},
                      {'type': 'value', 'name': '归母净利（亿元）'}],
            'series': [
                {'name': '营业收入', 'type': 'bar', 'yAxisIndex': 0, 'data': fin['rev'],
                 'itemStyle': {'color': RED},
                 'label': {'show': True, 'position': 'top', 'fontSize': 10, 'color': '#9a7d82'}},
                {'name': '归母净利', 'type': 'bar', 'yAxisIndex': 1,
                 'data': fin.get('np') or [], 'itemStyle': {'color': '#c9a227'},
                 'label': {'show': True, 'position': 'top', 'fontSize': 10, 'color': '#9a7d82'}}]}

    # 2 毛利率/净利率/ROE
    if fin.get('gm') or fin.get('nm'):
        ser = []
        if fin.get('gm'):
            ser.append({'name': '销售毛利率', 'type': 'line', 'smooth': True, 'data': fin['gm'],
                        'itemStyle': {'color': RED}})
        if fin.get('nm'):
            ser.append({'name': '销售净利率', 'type': 'line', 'smooth': True, 'data': fin['nm'],
                        'itemStyle': {'color': '#e8939c'}})
        if fin.get('roe'):
            ser.append({'name': 'ROE（加权）', 'type': 'line', 'smooth': True, 'data': fin['roe'],
                        'itemStyle': {'color': '#c9a227'}})
        ch['chartMargin'] = {
            'tooltip': {'trigger': 'axis'}, 'legend': {'bottom': 0},
            'grid': {'left': 56, 'right': 40, 'top': 30, 'bottom': 40},
            'xAxis': {'type': 'category', 'data': yrs},
            'yAxis': {'type': 'value', 'name': '%'}, 'series': ser}

    # 3 现金流与资产负债率
    if fin.get('ocf'):
        ch['chartCashflow'] = {
            'tooltip': {'trigger': 'axis'}, 'legend': {'bottom': 0},
            'grid': {'left': 60, 'right': 50, 'top': 30, 'bottom': 40},
            'xAxis': {'type': 'category', 'data': yrs},
            'yAxis': [{'type': 'value', 'name': '亿元'}, {'type': 'value', 'name': '资产负债率 %'}],
            'series': [
                {'name': '归母净利', 'type': 'bar', 'data': fin.get('np') or [],
                 'itemStyle': {'color': '#e8939c'}},
                {'name': '经营现金流净额', 'type': 'bar', 'data': fin['ocf'],
                 'itemStyle': {'color': RED}},
                {'name': '资产负债率', 'type': 'line', 'yAxisIndex': 1, 'smooth': True,
                 'data': fin.get('lev') or [], 'itemStyle': {'color': '#c9a227'}}]}

    # 4 分红
    if fin.get('dps') and any(v is not None for v in fin['dps']):
        ch['chartDividend'] = {
            'tooltip': {'trigger': 'axis'}, 'legend': {'bottom': 0},
            'grid': {'left': 56, 'right': 50, 'top': 30, 'bottom': 40},
            'xAxis': {'type': 'category', 'data': yrs},
            'yAxis': [{'type': 'value', 'name': '元/股'}, {'type': 'value', 'name': '元'}],
            'series': [
                {'name': '每股股利', 'type': 'bar', 'data': fin['dps'],
                 'itemStyle': {'color': '#c9a227'},
                 'label': {'show': True, 'position': 'top', 'fontSize': 10, 'color': '#9a7d82'}},
                {'name': '每股收益', 'type': 'line', 'yAxisIndex': 1, 'smooth': True,
                 'data': fin.get('eps') or [], 'itemStyle': {'color': RED}}]}

    # 5 ROIC vs WACC
    if fin.get('roic'):
        wacc = fin.get('wacc')
        ch['chartRoic'] = {
            'tooltip': {'trigger': 'axis'}, 'legend': {'bottom': 0},
            'grid': {'left': 56, 'right': 40, 'top': 30, 'bottom': 40},
            'xAxis': {'type': 'category', 'data': yrs},
            'yAxis': {'type': 'value', 'name': '%'},
            'series': [
                {'name': 'ROIC（近似）', 'type': 'bar', 'data': fin['roic'],
                 'itemStyle': {'color': RED},
                 'label': {'show': True, 'position': 'top', 'fontSize': 10, 'color': '#9a7d82'}},
                {'name': 'WACC（假设 %s%%）' % wacc, 'type': 'line', 'smooth': False,
                 'data': [wacc] * len(yrs), 'itemStyle': {'color': '#c9a227'},
                 'lineStyle': {'type': 'dashed', 'width': 2}}]}

    # 6 同行业营收对比
    pe = g(d, 'peers', default={}) or {}
    if pe.get('share'):
        ch['chartShare'] = {
            'tooltip': {'trigger': 'axis'}, 'legend': {'bottom': 0},
            'grid': {'left': 70, 'right': 40, 'top': 30, 'bottom': 70},
            'xAxis': {'type': 'category', 'data': [x[0] for x in pe['share']],
                      'axisLabel': {'interval': 0, 'rotate': 25, 'fontSize': 10}},
            'yAxis': {'type': 'value', 'name': '营收（亿元）'},
            'series': [{'name': '营业收入（最近年度）', 'type': 'bar',
                        'data': [x[1] for x in pe['share']],
                        'itemStyle': {'color': RED},
                        'label': {'show': True, 'position': 'top', 'fontSize': 10,
                                  'color': '#9a7d82'}}]}

    # 7 行业规模
    ind = g(d, 'industry', default={}) or {}
    if not isinstance(ind, dict):
        ind = {}
    if ind.get('size'):
        # ⚠️ sizeYears / size 大多是**不同品类的横截面**（单位不同、不是时间序列），
        # 所以只画横向条形对比，绝不叠加「同比增速」折线 —— 那会把不同量纲硬当时间序列。
        ch['chartIndustrySize'] = {
            'tooltip': {'trigger': 'axis'},
            'grid': {'left': 150, 'right': 70, 'top': 24, 'bottom': 30},
            'xAxis': {'type': 'value', 'name': ind.get('sizeUnit') or ''},
            'yAxis': {'type': 'category', 'data': list(reversed(ind.get('sizeYears') or [])),
                      'axisLabel': {'fontSize': 10.5}},
            'series': [{'name': ind.get('sizeName') or '关键指标',
                        'type': 'bar', 'data': list(reversed(ind['size'])),
                        'itemStyle': {'color': RED},
                        'label': {'show': True, 'position': 'right', 'fontSize': 10,
                                  'color': '#9a7d82'}}]}

    # 8 下游结构
    dm = g(d, 'demand', default={}) or {}
    if dm.get('pie'):
        ch['chartDemandMix'] = {
            'tooltip': {'trigger': 'item', 'formatter': '{b}: {d}%'},
            'legend': {'bottom': 0},
            'series': [{'type': 'pie', 'radius': ['42%', '68%'], 'center': ['50%', '44%'],
                        'color': [RED, '#c9a227', '#e8939c', '#8c0a20', '#dcb9be', '#a5762a'],
                        'data': [{'name': k, 'value': v} for k, v in dm['pie']],
                        'label': {'formatter': '{b} {d}%'}}]}

    # 9 盈利预测
    fc = g(d, 'forecast', default={}) or {}
    if fc.get('series'):
        ch['chartEstimate'] = {
            'tooltip': {'trigger': 'axis'}, 'legend': {'bottom': 0},
            'grid': {'left': 60, 'right': 40, 'top': 30, 'bottom': 40},
            'xAxis': {'type': 'category', 'data': fc.get('years') or []},
            'yAxis': {'type': 'value', 'name': '亿元'},
            'series': [{'name': s['name'], 'type': 'line', 'smooth': True, 'data': s['data'],
                        'itemStyle': {'color': s.get('color') or RED},
                        'lineStyle': {'type': 'dashed' if s.get('dashed') else 'solid'}}
                       for s in fc['series']]}

    # ★ 2026-09-21 停用 chartSens（目标价敏感性热力图）——
    #   用户要求摘除「估值敏感性」小节，本图不再被任何槽引用；继续产出会让
    #   线上库留下「有图行、页面无引用」的孤儿图（四家已从库里删除该行）。
    #   原实现见 backup/report_build_v31_pre_dropsens_*.py（取 sens.heat.data 画 heatmap）。
    # ⚠️ 顺带：`sens` 数据块本身在 data_v31_*.json 里**保留未删**（不可逆操作不做无谓的），
    #   只是不再有任何渲染路径读它。

    # 11 估值区间（历史 PE / PB）
    yv = g(d, 'valuation', default={}) or {}
    # ★ 2026-10-16：存量报告的 `valuation.rows` 常是「估值速览表」
    #   （收盘价 / 市值 / PE / PB / BPS / 换手率 …，列义＝指标名 | 数值 | 来源）——
    #   拿它画 PE/PB 时间序列会**一行也取不到**（000762 的这张图 13 行全空）。
    #   新增可选键 `chart_rows`（列＝时点 | PE | PB | 说明），有就优先用它；
    #   没提供时行为逐字节不变（603227 的 rows 本来就是 PE/PB 序列，照旧走 rows）。
    rows = yv.get('chart_rows') or yv.get('rows') or []
    if rows and len(rows[0]) >= 3:
        ch['chartValuation'] = {
            'tooltip': {'trigger': 'axis'}, 'legend': {'bottom': 0},
            'grid': {'left': 56, 'right': 56, 'top': 30, 'bottom': 40},
            'xAxis': {'type': 'category', 'data': [r[0] for r in rows]},
            'yAxis': [{'type': 'value', 'name': 'PE（倍）'},
                      {'type': 'value', 'name': 'PB（倍）'}],
            'series': [
                {'name': 'PE', 'type': 'bar', 'data': numcol(rows, 1, len(rows)),
                 'itemStyle': {'color': RED},
                 'label': {'show': True, 'position': 'top', 'fontSize': 10, 'color': '#9a7d82'}},
                {'name': 'PB', 'type': 'line', 'yAxisIndex': 1, 'smooth': True,
                 'data': numcol(rows, 2, len(rows)), 'itemStyle': {'color': '#c9a227'}}]}

    # 11b 收入结构（分产品/分板块）—— 与 chartShare 同款横向对比
    bz = g(d, 'bizmix', default={}) or {}
    # ★★ 2026-10-16：`bizmix` 的**列口径有两套**，不能再按列号硬取 —— `rows` 的列义随 `head` 变：
    #     新口径（603227 / 000762，7 列）= 产品 | 收入(元) | **毛利率** | 收入(万元) | 收入占比 | 毛利占比 | 排名变化
    #     旧口径（603977 等，5 列）     = 板块 | 收入(亿元) | 收入占比 | **毛利率** | 定位
    #   毛利率一个在**列 2**、一个在**列 3** ⇒ 原来固定 `numcol(rows, 3)`，在新口径上取到的是
    #   **收入（万元）**，于是图把「万元」当「毛利率 %」画（000762 一直在画这张错图；
    #   603227 同样错，只因它的 m11 后来被 `mkmod11_ring.py` 的双环覆盖，才没人看见）。
    #   新口径的 seed 本来就备好了专用字段 `mix / income / margin`（income 单位＝万元）⇒ 有就用，
    #   没有才回落列号（旧口径走原路径，逐字节不变）。
    bzm, bzi, bzg = bz.get('mix'), bz.get('income'), bz.get('margin')
    if bzm and bzi and bzg:
        names = list(bzm)
        revs = list(bzi)
        gms = list(bzg)
        yunit = bz.get('chart_unit') or '万元'
    elif bz.get('rows'):
        names = [r[0] for r in bz['rows']]
        revs = numcol(bz['rows'], 1, len(bz['rows']))
        gms = numcol(bz['rows'], 3, len(bz['rows']))
        yunit = unit_ax(bz, '亿元')
    else:
        names = None
    if names and any(v is not None for v in revs):
        ch['chartMix'] = {
            'tooltip': {'trigger': 'axis'}, 'legend': {'bottom': 0},
            'grid': {'left': 76, 'right': 56, 'top': 30, 'bottom': 60},
            'xAxis': {'type': 'category', 'data': names,
                      'axisLabel': {'interval': 0, 'rotate': 20, 'fontSize': 10}},
            'yAxis': [{'type': 'value', 'name': yunit},
                      {'type': 'value', 'name': '毛利率 %', 'max': 100}],
            'series': [
                {'name': '收入', 'type': 'bar', 'data': revs,
                 'itemStyle': {'color': RED},
                 'label': {'show': True, 'position': 'top', 'fontSize': 10, 'color': '#9a7d82'}},
                {'name': '毛利率', 'type': 'line', 'yAxisIndex': 1, 'smooth': True,
                 'data': gms, 'itemStyle': {'color': '#c9a227'}}]}

    # 11c 费用率结构（四费率）
    ex = g(d, 'expense', default={}) or {}
    if ex.get('rows'):
        cols = ex.get('series') or ['销售费用率', '管理费用率', '研发费用率', '财务费用率']
        ch['chartExp'] = {
            'tooltip': {'trigger': 'axis'}, 'legend': {'bottom': 0},
            'grid': {'left': 56, 'right': 40, 'top': 30, 'bottom': 40},
            'xAxis': {'type': 'category', 'data': [r[0] for r in ex['rows']]},
            'yAxis': {'type': 'value', 'name': '%'},
            'series': [{'name': c, 'type': 'line', 'smooth': True,
                        'data': numcol(ex['rows'], i + 1, len(ex['rows'])),
                        'itemStyle': {'color': col}, 'connectNulls': True}
                       for i, (c, col) in enumerate(zip(
                           cols, [RED, '#c9a227', '#00b0f0', '#8c0a20']))]}

    # 6 产能与产能利用率（渲染器 m6）
    cap = g(d, 'capacity', default={}) or {}
    # ★ 2026-10-16：`capacity.rows` 常是**混合单位的文字表**
    #   （000762：碳酸锂「1.2 万吨/年」、锂精矿「298.5 km²」、铬铁矿「15 万吨/年」+ 「约 5.5%」；
    #    002237：黄金「109.817 吨」/ 白银「1,200 吨」/ 电解铜「33.5 万吨」/ 硫酸「168 万吨」，
    #    后者单位既不同、量级还差 15 万倍）⇒ 列 1 / 列 2 全被 numcol 转 None ⇒ 图空白。
    #   ① 有 `chart_rows`（**只放单位可比的那几行、纯数值**）+ `chart_unit` 就用它画；
    #   ② 连 `chart_rows` 都没有、且 rows 里一个数值都没有 ⇒ **不建图**（`numeric_rows` 闸），
    #      m6 端同步不挂槽 —— 利用率信息留在表格里，比一张空图有用。
    cp = cap.get('chart_rows') or cap.get('rows') or []
    # ★★ 闸要卡**图真正用到的那两列**（列 1 = 产能柱、列 2 = 利用率线），不能卡任意列：
    #   002237 的利用率在**列 3**（「68.31%」能转成 68.31），若用 `need=1` 判任意列就会放行，
    #   结果图照样建出来、列 1/列 2 全是 None ⇒ 又一张「只有坐标轴」的空图。
    if numeric_rows(cp, idx=(1, 2), need=1):
        _util = numcol(cp, 2, len(cp))
        _has_util = any(v is not None for v in _util)
        ch['chartCap'] = {
            'tooltip': {'trigger': 'axis'}, 'legend': {'bottom': 0},
            'grid': {'left': 64, 'right': 56, 'top': 30, 'bottom': 70},
            'xAxis': {'type': 'category', 'data': [r[0] for r in cp],
                      'axisLabel': {'interval': 0, 'rotate': 25, 'fontSize': 10}},
            'yAxis': [{'type': 'value', 'name': cap.get('chart_unit') or unit_ax(cap, '吨')}]
                     + ([{'type': 'value', 'name': '产能利用率 %', 'max': 100}]
                        if _has_util else []),
            'series': [
                {'name': '产能', 'type': 'bar', 'data': numcol(cp, 1, len(cp)),
                 'itemStyle': {'color': RED},
                 'label': {'show': True, 'position': 'top', 'fontSize': 10, 'color': '#9a7d82'}}]
                + ([{'name': '产能利用率', 'type': 'line', 'yAxisIndex': 1, 'smooth': True,
                     'data': _util, 'itemStyle': {'color': '#c9a227'}}]
                   if _has_util else [])}

    # 7 产销量量价拆分（渲染器 m7）
    # ★ 2026-09-20：production 可能是**百分比口径**（公司只披露同比增减，如「+42.87%」），
    #   此时画「产量/销量绝对值 + 产销率」是错的（会把 +42.87 当成 42.87 吨）。
    #   故只有为绝对量口径（absolute=True）时才出图。
    pr = g(d, 'production', default={}) or {}
    # ★ 2026-10-16：`production.rows` 的列义往往是**「2025 全年 / 2026H1」两期对照**
    #   （如 000762：产品 | 2025 产量 | 2026H1 产量 | 2026H1 销量 | 产量同比 | 销量同比）——
    #   而本图的三条系列固定读「列 1 = 产量 / 列 2 = 销量 / 列 3 = 产销率」，
    #   于是把「2026H1 产量」当销量、「2026H1 销量」当产销率画出去 —— **不是空图，是错图**。
    #   新增可选键 `chart_rows`（列＝产品 | 产量 | 销量 | 产销率 %，同一期间、同一单位），
    #   有就用它；没有时逐字节回落 rows。
    prows = pr.get('chart_rows') or pr.get('rows') or []
    # ★★ 2026-10-16：原来只卡 `absolute`，挡不住「**口径对照表**被画成产量-销量图」——
    #   601118 的 3 行是「自产橡胶 10.42 / 加工量 131 / 贸易量 337」，三个**互不重叠**的口径
    #   各占一列；601958 的列 2 是「权益产量」而非销量。
    #   两者画出来都**不是空图、而是错图**（把不同口径并排成「产量 vs 销量」）。
    #   ⇒ 再加两道语义闸：
    #     ① 表头必须出现「销量」字样（否则列 2 根本不是销量）；
    #     ② 至少有一行**同时**有列 1 与列 2 的值（否则各行是互斥口径，无法成对比较）。
    #   已全库对比：对本来正常的 8 份逐字节无影响。
    _phead = ' '.join(str(x) for x in (pr.get('head') or []))
    _p1, _p2 = numcol(prows, 1, len(prows)), numcol(prows, 2, len(prows))
    _paired = any(a is not None and b is not None for a, b in zip(_p1, _p2))
    if prows and pr.get('absolute') and '销量' in _phead and _paired:
        ch['chartProd'] = {
            'tooltip': {'trigger': 'axis'}, 'legend': {'bottom': 0},
            'grid': {'left': 64, 'right': 56, 'top': 30, 'bottom': 70},
            'xAxis': {'type': 'category', 'data': [r[0] for r in prows],
                      'axisLabel': {'interval': 0, 'rotate': 25, 'fontSize': 10}},
            'yAxis': [{'type': 'value', 'name': pr.get('chart_unit') or pr.get('unit') or '吨'},
                      {'type': 'value', 'name': '产销率 %'}],
            'series': [
                {'name': '产量', 'type': 'bar', 'data': numcol(prows, 1, len(prows)),
                 'itemStyle': {'color': RED}},
                {'name': '销量', 'type': 'bar', 'data': numcol(prows, 2, len(prows)),
                 'itemStyle': {'color': '#c9a227'}},
                {'name': '产销率', 'type': 'line', 'yAxisIndex': 1, 'smooth': True,
                 'data': numcol(prows, 3, len(prows)),
                 'itemStyle': {'color': '#00b0f0'}}]}

    # 23 上游原料价格（渲染器 m14）
    # ★ 2026-09-20：原料表可能是**文字口径**（如「4,508 → 7,850 美元/盎司」「价格大幅上涨」），
    #   此时 numcol 会全为 None，画出来是一张空图 —— 必须先用「至少一列有 ≥2 个数字」把关。
    raw = g(d, 'raw', default={}) or {}
    if raw.get('rows') and raw.get('numeric'):
        rcols = raw.get('series') or ['价格']
        ch['chartRaw'] = {
            'tooltip': {'trigger': 'axis'}, 'legend': {'bottom': 0},
            'grid': {'left': 60, 'right': 40, 'top': 30, 'bottom': 40},
            'xAxis': {'type': 'category', 'data': [r[0] for r in raw['rows']]},
            'yAxis': {'type': 'value', 'name': unit_ax(raw, '元/吨')},
            'series': [{'name': s, 'type': 'line', 'smooth': True,
                        'data': numcol(raw['rows'], i + 1, len(raw['rows'])),
                        'itemStyle': {'color': col}, 'connectNulls': True}
                       for i, (s, col) in enumerate(zip(
                           rcols, [RED, '#c9a227', '#00b0f0', '#8c0a20']))]}

    # 12 产品价格与成本剪刀差（渲染器 m15）
    # ★ 2026-10-16：`chart_rows` 专供本图（与表格用的 `rows` 解耦，同 `price_rows` 的做法）。
    #   表格可以是「产品维度文字表」，图必须是「期间/品种 × 均价/成本/毛利」的数值表。
    #   两者都没有数值 ⇒ **整图不出**（`numeric_rows` 闸），m15 端同步判据，免留灰框。
    pz = g(d, 'pricecost', default={}) or {}
    pzr = pz.get('chart_rows') or pz.get('rows')
    # ★ 2026-10-16：闸从「三列都要有值」放宽成 **`need=1`（至少一列有值）** ——
    #   因为下面已经把系列**按列条件化**了：只有「均价」一列有值也应当出图
    #   （000762 就是这种：公司只披露现货价、不披露成本与毛利）。
    #   存量研报的三列本就有值 ⇒ 判据恒真，行为不变。
    if numeric_rows(pzr, need=1):
        # ★ 2026-10-16：**哪一列有值就出哪条系列**。原来三条系列写死，而有的公司只披露「均价」
        #   （如 000762：碳酸锂三时点现货价 196,150 / 162,000 / 107,750 元/吨，成本与毛利均未披露）
        #   ⇒ 写死会多出两条「图例有点、线上无点」的空系列。列全空时不挂那条。
        #   ★ 空白基线未变：三列都有值时，产出的三条系列与顺序与原来逐字节一致。
        _p1 = numcol(pzr, 1, len(pzr))
        _p2 = numcol(pzr, 2, len(pzr))
        _p3 = numcol(pzr, 3, len(pzr))
        _pser = []
        if any(v is not None for v in _p1):
            _pser.append({'name': pz.get('s1') or '产品均价', 'type': 'bar', 'data': _p1,
                          'itemStyle': {'color': RED}})
        if any(v is not None for v in _p2):
            _pser.append({'name': pz.get('s2') or '单位成本', 'type': 'bar', 'data': _p2,
                          'itemStyle': {'color': '#00b0f0'}})
        if any(v is not None for v in _p3):
            _pser.append({'name': pz.get('s3') or '单位毛利', 'type': 'line', 'smooth': True,
                          'data': _p3,
                          'itemStyle': {'color': '#c9a227'}, 'lineStyle': {'width': 3}})
        ch['chartPrice'] = {
            'tooltip': {'trigger': 'axis'}, 'legend': {'bottom': 0},
            'grid': {'left': 60, 'right': 40, 'top': 30, 'bottom': 40},
            'xAxis': {'type': 'category', 'data': [r[0] for r in pzr]},
            'yAxis': {'type': 'value', 'name': pz.get('chart_unit') or unit_ax(pz, '元/吨')},
            'series': _pser}

    # 28 股价走势（渲染器 m28，并入「估值分析」）
    # ★ 2026-09-22：`volprice` 这个键被两个槽共用 —— 槽 7（量价拆分，列＝
    #   年度/销量/均价/收入/产销率）与槽 28（股价走势，列＝时点/收盘价/成交额）。
    #   两者列义不兼容：把量价行喂给本图会画出「销量当收盘价」的错图，
    #   反过来把股价行喂给 m7 会让量价表的表头与内容不符。
    #   ⇒ 新增可选键 `price_rows` 专供本图；**不提供时仍回落 `rows`**
    #     （存量研报没这个键，行为逐字节不变）。
    vp = g(d, 'volprice', default={}) or {}
    prow = vp.get('price_rows') or vp.get('rows')
    if prow:
        ch['chartPrice2'] = {
            'tooltip': {'trigger': 'axis'}, 'legend': {'bottom': 0},
            'grid': {'left': 60, 'right': 60, 'top': 30, 'bottom': 40},
            'xAxis': {'type': 'category', 'data': [r[0] for r in prow],
                      'axisLabel': {'interval': 0, 'rotate': 25, 'fontSize': 10}},
            'yAxis': [{'type': 'value', 'name': '元'},
                      {'type': 'value', 'name': '成交额 亿元'}],
            'series': [
                {'name': '收盘价', 'type': 'line', 'smooth': True,
                 'data': numcol(prow, 1, len(prow)),
                 'itemStyle': {'color': RED}, 'lineStyle': {'width': 3},
                 'areaStyle': {'opacity': 0.10}},
                {'name': '成交额', 'type': 'bar', 'yAxisIndex': 1,
                 'data': numcol(prow, 2, len(prow)),
                 'itemStyle': {'color': '#e8939c'}}]}

    # 25/26 资源与供需（渲染器 m_res / m_sdbalance）—— 见 res_sd_charts()，
    # 抽出去是为了让「只补 25/26 两槽」的脚本能单独取这三个图。
    ch.update(res_sd_charts(d))
    return ch


# ------------------------------------------------------------------ 壳
def build_shell(d):
    fin = g(d, 'fin', default={}) or {}
    name = d.get('name') or ''
    code = d.get('code') or ''
    ind = d.get('industry_name') or ''
    suffix = 'SZ' if code[:1] in '0123' else 'SH'
    years = fin.get('years') or []
    rev = [v for v in (fin.get('rev') or []) if v is not None]
    np_ = [v for v in (fin.get('np') or []) if v is not None]
    lr = rev[-1] if rev else None
    ln = np_[-1] if np_ else None
    prev_n = np_[-2] if len(np_) >= 2 else None
    growth = yoy(ln, prev_n)
    pe, price, mktcap = fin.get('pe'), fin.get('price'), fin.get('mktcap')
    y_last = years[-1] if years else ''

    kicker = 'EQUITY RESEARCH · %s · %s深度研究报告' % (ind or 'A股', name)
    title = '%s（%s.%s）深度研究报告' % (name, code, suffix)
    subtitle = ('「寒武纪投资2026」板块成分股 · %s年营业收入 %s 亿元 · 归母净利 %s 亿元%s · '
                'PE(TTM) %s 倍 · 总市值 %s 亿元'
                % (y_last, fnum(lr, 2), fnum(ln, 2),
                   ('（%s）' % ('%+.2f%%' % growth) if growth is not None else ''),
                   fnum(pe, 2), fnum(mktcap, 2)))
    badges = ['A股 · %s' % (ind or '未分类'),
              '数据区间 %s~%s（%d 年）' % (years[0], years[-1], span_n(years))
              if years else '数据区间待补',
              '现价 %s 元' % fnum(price, 2),
              '总市值 %s 亿元' % fnum(mktcap, 2),
              'PE(TTM) %s 倍' % fnum(pe, 2)]

    # KPI：仅客观可得的
    kpis = [
        {'label': '营业收入（%s）' % (y_last or '—'), 'val': fnum(lr, 2), 'unit': '亿元',
         'cls': '', 'style': ''},
        {'label': '归母净利（%s）' % (y_last or '—'), 'val': fnum(ln, 2), 'unit': '亿元',
         'cls': ('up' if (growth or 0) > 0 else 'down' if (growth or 0) < 0 else ''),
         'style': ''},
        {'label': '销售毛利率', 'val': fnum(next((v for v in reversed(fin.get('gm') or [])
                                              if v is not None), None), 2),
         'unit': '%', 'cls': '', 'style': ''},
        {'label': 'ROE（加权）', 'val': fnum(next((v for v in reversed(fin.get('roe') or [])
                                               if v is not None), None), 2),
         'unit': '%', 'cls': '', 'style': ''},
        {'label': '资产负债率', 'val': fnum(next((v for v in reversed(fin.get('lev') or [])
                                              if v is not None), None), 2),
         'unit': '%', 'cls': '', 'style': ''},
        {'label': 'PE（TTM）', 'val': fnum(pe, 2), 'unit': '倍', 'cls': '', 'style': ''},
        {'label': 'PB（MRQ）', 'val': fnum(fin.get('pb'), 2), 'unit': '倍', 'cls': '', 'style': ''},
        {'label': '总市值', 'val': fnum(mktcap, 2), 'unit': '亿元', 'cls': '', 'style': ''},
    ]
    kpi_note = ('财务数据：iFinD 年度财报（%s~%s，合并口径，单位亿元）；'
                '估值数据：iFinD，PE 为 TTM 口径；行情时点见文首徽标。%s'
                % (years[0] if years else '—', years[-1] if years else '—',
                   '未能取到的字段已在正文标 [MISSING] 并注明补齐路径。'))

    verdict_title = '核心结论'
    # ★ 2026-09-20：核心结论 / 一句话本质改为**数据可覆写**。
    #   原来把「行业规模、管理层、护城河等需一手来源的模块暂标 [MISSING]」写死在壳里，
    #   一旦某家公司把这些模块补齐了，这段自述就变成假话。
    shell = g(d, 'shell', default={}) or {}
    verdict_html = shell.get('verdict') or (
        '<strong>%s（%s）</strong>为「寒武纪投资2026」板块成分股（细分行业：%s）。'
        '%s 年营业收入 <strong>%s 亿元</strong>、归母净利 <strong>%s 亿元</strong>%s。'
        % (name, code, ind or '未分类', y_last or '最近一个完整年度',
           fnum(lr, 2), fnum(ln, 2),
           ('（同比 %+.2f%%）' % growth) if growth is not None else ''))

    # ★ 2026-10-14：建档说明 / 口径注解从核心结论里拆出来，单独存 notice_html，
    #   由研报页页头「ⓘ 报告说明」弹窗展示（用户口径：「研报里不要有这种注解，
    #   在头部做一个点击弹窗，注解之类的全部归到一起」）。核心结论只留结论本身。
    notice_html = shell.get('notice') or (
        '<p>本报告按 31 模块标准模板建档：<strong>财务数据为 %d 年序列（%s~%s，取自 iFinD）</strong>，'
        '模型可推算的指标（ROIC 近似、三档情景）已给出并标注 [模型输出]；'
        '<strong>行业规模、下游结构、管理层、护城河分项等需要一手来源的模块暂标 [MISSING]，'
        '并已在 M31 跟踪清单中列明补齐路径。</strong>'
        '基于当前资料深度，<strong>不给出评级与目标价</strong>。</p>'
        % (span_n(years), years[0] if years else '—', years[-1] if years else '—'))

    essence_html = shell.get('essence') or (
        '<div class="essence" id="essence">\n'
        '    <div class="et">THE ESSENCE · 一句话本质（可证伪命题）</div>\n'
        '    <div class="ec">%s 属于「%s」，%s 年营收 %s 亿元、归母净利 %s 亿元。'
        '<strong>本报告当前只能回答「这家公司过去%s年赚了多少钱、赚钱质量如何」</strong>'
        '（营收/净利/毛利率/净现比/ROIC−WACC 利差均为 %d 年实测），'
        '<strong>还不能回答「未来三年能赚多少」</strong>——前者是一手数据，后者需要产能、订单与'
        '价格假设，属于下一轮补齐项。</div>\n</div>'
        % (name, ind or '未分类行业', y_last or '最近年度',
           fnum(lr, 2), fnum(ln, 2), span_cn(span_n(years)), span_n(years)))

    footer = ('<footer>\n    <div class="disclaimer">\n      <strong>免责声明</strong>：'
              '以上内容基于公开数据和量化分析，仅供参考，不构成投资建议。市场有风险，投资需谨慎。'
              '任何投资决策应结合个人风险承受能力、资金状况和投资目标独立判断，'
              '必要时咨询持牌专业机构。过往表现不预示未来收益。\n    </div>\n'
              '    <p style="margin-top:12px;">数据来源：iFinD（财务与估值）、'
              '东方财富妙想（板块成员与行情）、公司公告。'
              '标 [MISSING] 的字段为未取到的一手资料，已在正文注明补齐路径，未做任何推断性填充。</p>\n'
              '</footer>')

    return {'code': code, 'name': name, 'kicker': kicker, 'title': title,
            'subtitle': subtitle, 'badges': badges, 'verdict_title': verdict_title,
            'verdict_html': verdict_html, 'notice_html': notice_html,
            'kpis': kpis, 'kpi_note': kpi_note,
            'toc': new_toc(), 'essence_html': essence_html, 'footer_html': footer,
            'theme': 'red', 'version': TEMPLATE_VERSION}


# ------------------------------------------------------------------ 主流程
# 本地重建时，data_v31_<code>.json 里通常没有 name（名称只存在于线上 wb_reports 行）。
# 缺名会让标题渲染成「（600459.SH）深度研究报告」、正文里公司名位置全空 ——
# 所以这里用 seed 里的代码→名称映射兜底（quotes_latest / watchlist），并保留显式覆盖能力。
_NAME_CACHE = None


def _name_map():
    """构建 {6 位代码: 公司名}。优先 quotes_latest.json，其次 watchlist.json。"""
    global _NAME_CACHE
    if _NAME_CACHE is not None:
        return _NAME_CACHE
    m = {}
    qp = os.path.join(SEED, 'quotes_latest.json')
    if os.path.exists(qp):
        try:
            q = json.load(io.open(qp, encoding='utf-8'))
        except Exception:
            q = {}
        for k, v in (q or {}).items():
            if isinstance(v, dict) and v.get('name'):
                m[str(v.get('code') or k).strip()[:6]] = str(v['name']).strip()
    wp = os.path.join(SEED, 'watchlist.json')
    if os.path.exists(wp):
        try:
            w = json.load(io.open(wp, encoding='utf-8'))
        except Exception:
            w = []
        for it in (w or []):
            if not isinstance(it, dict):
                continue
            c = str(it.get('code') or '').strip()[:6]
            if c and it.get('name'):
                m.setdefault(c, str(it['name']).strip())
    _NAME_CACHE = m
    return m


def resolve_name(d, code):
    nm = d.get('name')
    if nm:
        return nm
    return _name_map().get(str(code).strip()[:6]) or ''


def build(code):
    dp = os.path.join(SEED, 'data_v31_%s.json' % code)
    d = json.load(io.open(dp, encoding='utf-8'))
    d.setdefault('code', code)
    if not d.get('name'):
        d['name'] = resolve_name(d, code)

    # ★★★ 2026-10-16 完整性闸（已实踩：000731 / 000830 / 600456）
    #   本函数在 main() 里会**覆写** seed/report_<code>.json。若 data 是「薄文件」
    #   （顶层键缺若干块），重渲染出来的模块会残缺，一写盘就把 seed 里完整的内容
    #   换成残缺版 —— **不报错**，只表现为「图少了、表没了」。
    #   实测：000731 25 键 / 000830 24 键 / 600456 12 键（正常 40+）。
    #   ⇒ 判据用顶层键数（实测 <30 必然缺块），并列出缺的必需块便于定位。
    _need = ['bizmix', 'capacity', 'production', 'pricecost', 'expense',
             'sdbalance', 'valuation', 'resource', 'industry_note', 'fin']
    _miss = [k for k in _need if k not in d]
    _nk = len([k for k in d if k != 'code'])
    if (_nk < 30 or len(_miss) >= 3) and '--force-thin' not in sys.argv:
        raise SystemExit(
            '\n[已阻止] seed/data_v31_%s.json 只有 %d 个顶层键（正常 ≥ 30），缺块：%s\n'
            '  本脚本会用这份 data 重新渲染并 **覆写** seed/report_%s.json，\n'
            '  缺块对应的模块表与图会**一起消失**，且不报错。\n'
            '  ⇒ 这份标的请用「改库 + sync_seed_full.py %s --go」维护，不要重跑 build。\n'
            '  ⇒ 若 data 确已补全，加 --force-thin 强制继续。\n'
            % (code, _nk, ', '.join(_miss) or '—', code, code))

    # 行业名（batch_assemble 里 industry 被 dict 覆盖，行业名另存 industry_name）
    ind_name = d.get('industry_name') or d.get('subIndustry') or ''
    if not ind_name:
        # _todo_96.json 是历史批次清单，已不在工作区；有则兼容读取，无则跳过。
        tp = os.path.join(SEED, '_todo_96.json')
        if os.path.exists(tp):
            todo = json.load(io.open(tp, encoding='utf-8'))['todo']
            for m in todo:
                if m['code'] == code:
                    ind_name = m.get('sub_industry') or ''
                    d['grp'] = m.get('grp') or d.get('grp')
                    break
    d['industry_name'] = ind_name

    # ★ 第 24 槽标题带 {ind} 占位符（宝钛母本是「钛行业介绍与市场规模」）。
    #   用 industry_short（短名）而不是 industry_name —— 后者常带申万/证监会括号注释，
    #   直接塞进标题会变成「黄金（申万：贵金属 / 证监会：C32…）行业介绍与市场规模」。
    ind_short = (d.get('industry_short')
                 or (ind_name or '').split('（')[0].split('(')[0].strip())

    mods = []
    for spec in MODULES:
        no = spec['no']
        mods.append({'seq': no, 'no': str(no),
                     'title': title_of(spec, ind_short),
                     'html': RENDER[no](d)})

    charts = []
    for cid, opt in chart_opts(d).items():
        charts.append({'seq': len(charts) + 1, 'id': cid,
                       'name': CHART_NAMES.get(cid, cid), 'opt': opt})

    return {'report': build_shell(d), 'mods': mods, 'charts': charts}


def main():
    a = sys.argv[1:]
    if '--batch' in a:
        tp = os.path.join(SEED, '_todo_96.json')
        todo = json.load(io.open(tp, encoding='utf-8'))['todo']
        i = a.index('--batch')
        codes = [m['code'] for m in todo[int(a[i + 1]):int(a[i + 2])]]
    else:
        codes = [x for x in a if not x.startswith('--')]
    bad = 0
    for code in codes:
        seed = build(code)
        # 自检：编号连续、图槽与图数据一一对应
        nos = [m['no'] for m in seed['mods']]
        assert nos == [str(x) for x in range(1, 32)], '%s 编号不连续' % code
        used = set()
        for m in seed['mods']:
            used |= set(re.findall(r'data-chart="([^"]+)"', m['html']))
        have = {c['id'] for c in seed['charts']}
        miss = used - have
        assert not miss, '%s 有图槽但无图数据：%s' % (code, miss)
        rep = seed['report']
        assert rep['kpis'] and rep['toc'] and rep['verdict_html'] and rep['essence_html']
        out = os.path.join(SEED, 'report_%s.json' % code)
        io.open(out, 'w', encoding='utf-8').write(
            json.dumps(seed, ensure_ascii=False, separators=(',', ':')))
        body = sum(len(m['html']) for m in seed['mods'])
        nmiss = sum(m['html'].count('[MISSING]') for m in seed['mods'])
        print('%s %s %-8s 模块 31 · 图 %2d · 正文 %6d 字符 · [MISSING] %3d 处'
              % ('OK' if not miss else 'X ', code, rep['name'], len(seed['charts']), body, nmiss))
        if miss:
            bad += 1
    print('\n共 %d 份 → seed/report_<code>.json；异常 %d' % (len(codes), bad))


if __name__ == '__main__':
    main()
