# -*- coding: utf-8 -*-
"""把 600456 研报模块 8 的「宝钛华神 2014-2025 营收/净利润/净利率」表格改成
   柱线组合图（营收红柱 + 净利润蓝柱 + 净利率深灰折线，双 Y 轴），
   与用户给定的参考图表样式一致。

只改本地 seed，不改线上库（推库由 push_reports_v31.py 单独执行）。
"""
import io
import json
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
BASE = os.path.dirname(os.path.abspath(__file__))
SEED = os.path.join(BASE, 'seed', 'report_600456.json')
BAK = os.path.join(BASE, 'backup', 'seed_report_600456_pre_bstnchart.json')

YEARS = [str(y) for y in range(2014, 2026)]
REV = [3.62, 4.54, 3.89, 4.33, 5.63, 6.40, 5.49, 6.04, 11.86, 13.97, 12.67, 13.20]
NP = [0.03, 0.01, 0.03, 0.48, 0.71, 0.91, 1.33, 1.57, 2.89, 2.72, 2.11, 2.17]
MAR = [0.74, 0.29, 0.72, 11.08, 12.67, 14.18, 24.23, 26.07, 24.37, 19.49, 16.65, 16.44]

CHART_ID = 'chartBSTN'
CHART_NAME = '宝钛华神 营收/净利润/净利率（2014-2025）'

# ---- 配色取自用户给的参考图（逐像素采样）：红柱 #d7252f、蓝柱 #00b0f0、折线 #44546a ----
OPT = {
    "textStyle": {"fontFamily": "Microsoft YaHei", "color": "#3A2024"},
    "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
    "legend": {
        "bottom": 0,
        "itemWidth": 18,
        "itemHeight": 10,
        "itemGap": 20,
        "textStyle": {"fontSize": 12, "color": "#6B5560"},
    },
    "grid": {"left": 46, "right": 54, "top": 18, "bottom": 46},
    "xAxis": {
        "type": "category",
        "data": YEARS,
        "axisTick": {"show": False},
        "axisLine": {"lineStyle": {"color": "#E0DEDE"}},
        "axisLabel": {"interval": 0, "fontSize": 11, "color": "#918D8D"},
    },
    "yAxis": [
        {
            "type": "value",
            "min": 0,
            "max": 16,
            "interval": 2,
            "axisTick": {"show": False},
            "axisLine": {"show": False},
            "axisLabel": {"fontSize": 11, "color": "#918D8D"},
            "splitLine": {"show": False},
        },
        {
            "type": "value",
            "min": -5,
            "max": 30,
            "interval": 5,
            "axisTick": {"show": False},
            "axisLine": {"show": False},
            "axisLabel": {"formatter": "{value}%", "fontSize": 11, "color": "#918D8D"},
            "splitLine": {"show": False},
        },
    ],
    "series": [
        {
            "name": "营业收入 亿",
            "type": "bar",
            "data": REV,
            "itemStyle": {"color": "#D7252F"},
            "barCategoryGap": "48%",
        },
        {
            "name": "净利润 亿",
            "type": "bar",
            "data": NP,
            "itemStyle": {"color": "#00B0F0"},
            "barCategoryGap": "48%",
        },
        {
            "name": "净利率",
            "type": "line",
            "yAxisIndex": 1,
            "smooth": True,
            "symbol": "none",
            "data": MAR,
            "itemStyle": {"color": "#44546A"},
            "lineStyle": {"width": 2.4, "color": "#44546A"},
        },
    ],
}

NEW_BLOCK = (
    '    <h3>宝钛华神 2014-2025 营收 / 净利润 / 净利率</h3>\n'
    '    <div data-chart="%s" class="chart-box"></div>\n' % CHART_ID
)


def main():
    raw = io.open(SEED, encoding='utf-8').read()
    d = json.loads(raw)

    # ---------- 1) 备份 ----------
    os.makedirs(os.path.dirname(BAK), exist_ok=True)
    if not os.path.exists(BAK):
        shutil.copyfile(SEED, BAK)
        print('已备份 seed → %s' % os.path.basename(BAK))
    else:
        print('备份已存在，跳过：%s' % os.path.basename(BAK))

    # ---------- 2) 改模块 8 正文 ----------
    mod8 = None
    for m in d['mods']:
        if str(m['no']) == '8':
            mod8 = m
    assert mod8 is not None, '找不到模块 8'
    html = mod8['html']

    i = html.find('<h3>宝钛华神 2014-2025')
    assert i >= 0, '模块 8 里找不到宝钛华神数据表的标题'
    j = html.find('</table>', i)
    assert j >= 0, '找不到表格结束标签'
    j += len('</table>')
    removed = html[i:j]
    assert removed.count('<tr>') == 13, '被删除的表格行数异常：%d' % removed.count('<tr>')

    # 拆出紧跟其后的「分析备注」段落，挪到图表下方
    k = html.find('<p class="muted"', j)
    note = ''
    if k >= 0:
        k2 = html.find('</p>', k) + len('</p>')
        note = html[k:k2]
        html = html[:i] + html[k2:]          # 连标题、表格、以及表格与备注之间的空行一起删掉
    else:
        html = html[:i] + html[j:]

    # 在 grid2 之后、来源行之前插入图表
    pos = html.find('<p class="src">')
    assert pos >= 0, '找不到来源行'
    html = html[:pos] + NEW_BLOCK + ('    ' + note + '\n' if note else '') + html[pos:]

    assert 'data-chart="%s"' % CHART_ID in html
    assert '<h3>宝钛华神 2014-2025' in html
    assert '营业收入（亿）</th>' not in html, '旧表格没删干净'
    mod8['html'] = html
    print('模块 8 正文：删除 %d 字符的旧表格，插入图表槽位' % len(removed))

    # ---------- 3) 新增图表数据 ----------
    d['charts'] = [c for c in d['charts'] if c['id'] != CHART_ID]
    seq = max(c['seq'] for c in d['charts']) + 1
    d['charts'].append({'seq': seq, 'id': CHART_ID, 'name': CHART_NAME, 'opt': OPT})
    d['charts'].sort(key=lambda c: c['seq'])
    print('图表：新增 %s（seq=%d），现有 %d 张' % (CHART_ID, seq, len(d['charts'])))

    # ---------- 4) 校验：图槽 ⊆ 图数据 ----------
    ids = {c['id'] for c in d['charts']}
    slots = set()
    for m in d['mods']:
        s = m['html']
        p = 0
        while True:
            p = s.find('data-chart="', p)
            if p < 0:
                break
            p += len('data-chart="')
            q = s.find('"', p)
            slots.add(s[p:q])
            p = q
    print('模块图槽 %d 个，图表数据 %d 个' % (len(slots), len(ids)))
    missing = sorted(slots - ids)
    assert not missing, '有槽无图：%s' % missing
    print('有槽无图：无 ✓')

    # ---------- 5) 写回 ----------
    out = json.dumps(d, ensure_ascii=False, indent=1)
    assert json.loads(out) == d
    io.open(SEED, 'w', encoding='utf-8').write(out)
    print('已写回 %s（%d 字符）' % (os.path.basename(SEED), len(out)))


if __name__ == '__main__':
    main()
