# -*- coding: utf-8 -*-
"""600456 内容变更（承接 SQL 结构迁移之后执行）。

前置：mig600456_29mod.py 报 DELETE 无权限 → 结构变更（删 2 模块 + 删 1 图表 +
重排 id/no/seq）改由 MCP managePgDatabase(execute) 跑 SQL 完成。
本脚本只做**内容**改写，全部走 PostgREST PATCH（有权限）：

  A. m25 三档情景表 → 加 PE / PB 两列 + 估值口径注脚
  B. 新 m27（企业评分）→ 顶部插入 chart_eps 图 + 技术解读（取自原 m28）
  C. chart_eps → EPS 改蓝色柱状图、收盘价改红色面积图，双轴 min=0
  D. wb_reports.toc → 企业评分锚点 m29 → m27

数据源用**备份快照**（build/backup/report_600456_pre_29mod_*.json），
所以不依赖线上当前状态，可重复执行。
"""
import glob
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request

GO = '--go' in sys.argv
B = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
CFG = json.load(io.open(os.path.join(B, 'build', 'cloud.json'), encoding='utf-8'))
BASE = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']
CODE = '600456'


def req(method, path, body=None):
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method)
    r.add_header('Authorization', 'Bearer ' + CFG['key'])
    r.add_header('Content-Type', 'application/json')
    if method in ('POST', 'PATCH'):
        r.add_header('Prefer', 'return=representation')
    try:
        with urllib.request.urlopen(r, timeout=90) as f:
            raw = f.read()
            return f.status, (json.loads(raw.decode('utf-8')) if raw else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')[:400]


def get(path):
    s, r = req('GET', path)
    assert s == 200, 'GET %s 失败 %s %s' % (path, s, r)
    return r


def nowts():
    """up 列是 bigint（毫秒时间戳），不是 ISO 字符串 —— 传错会 22P02。"""
    return int(time.time() * 1000)


# ------------------------------------------------------- 数据源：备份快照
cands = sorted(glob.glob(os.path.join(B, 'build', 'backup', 'report_%s_pre_29mod_*.json' % CODE)))
assert cands, '找不到备份快照，拒绝执行'
BK = json.load(io.open(cands[-1], encoding='utf-8'))
print('数据源：', os.path.basename(cands[-1]))
src_mods = {str(m['no']): m for m in BK['mods']}
src_charts = {c['id'].replace(CODE + '_', ''): c for c in BK['charts']}
src_rep = BK['report']
assert len(src_mods) == 31 and len(src_charts) == 23, '备份快照不完整'
print('  快照：31 模块 / 23 图表 · 拍摄于', BK['captured'])

# ------------------------------------------------------- A. m25 加 PE / PB
m25 = src_mods['25']['html']
for a, b in [
    ('<th>2026E 归母净利</th>', '<th>2026E 归母净利</th><th>PE（倍）</th><th>PB（倍）</th>'),
    ('<td>55~58 亿</td><td>2.5~3.0 亿</td>', '<td>55~58 亿</td><td>2.5~3.0 亿</td><td>43~52</td><td>1.73</td>'),
    ('<td>61~64 亿</td><td>4.0~4.5 亿</td>', '<td>61~64 亿</td><td>4.0~4.5 亿</td><td>29~33</td><td>1.70</td>'),
    ('<td>68~72 亿</td><td>5.5~6.5 亿</td>', '<td>68~72 亿</td><td>5.5~6.5 亿</td><td>20~24</td><td>1.66</td>'),
]:
    assert m25.count(a) == 1, 'm25 里「%s」出现 %d 次' % (a, m25.count(a))
    m25 = m25.replace(a, b)
NOTE = ('<div class="logic"><div class="lt">估值口径</div><div class="lv">'
        'PE = 当前总市值 130 亿元 ÷ 2026E 归母净利；PB = 当前股价 27.35 元 ÷ 2026E 期末每股净资产'
        '（按 2026 年利润全额留存测算，总股本 4.75 亿股）。三档差异全部来自盈利预测，'
        '股价与市值按 2026-08-24 收盘固定，与模块 27 评分卡取数一致。</div></div>')
ANCH = '</table>\n    <div data-chart="chartEstimate"'
assert m25.count(ANCH) == 1, 'm25 表格-图表衔接处不唯一'
new_m25 = m25.replace(ANCH, '</table>\n    ' + NOTE + '\n    <div data-chart="chartEstimate"')

# ------------------------------------------------------- B. 新 m27 正文
old28, old29 = src_mods['28']['html'], src_mods['29']['html']
i = old28.find('<h3>技术解读</h3>')
j = old28.find('</p>', old28.find('<p style="font-size:13.5px;">', i)) + len('</p>')
assert i > 0 and j > len('<h3>技术解读</h3>'), '未能从 m28 抠出技术解读段'
tech = old28[i:j].replace('<p style="font-size:13.5px;">', '<p>')   # 全宽了，恢复正文字号
HEAD = ('<h3>EPS 与股价历史</h3>\n'
        '    <div data-chart="chart_eps" class="chart-box"></div>\n'
        '    <p class="src"><b>来源：</b>宝钛股份研究报告 PPTX 幻灯片 49（2026-08，市值）；'
        'EPS(TTM) 与收盘价历史走势。</p>\n'
        '    ')
new_m27 = HEAD + tech + '\n    ' + old29

# ------------------------------------------------------- C. chart_eps 改造
oldopt = src_charts['chart_eps']['opt']
if isinstance(oldopt, str):
    oldopt = json.loads(oldopt)
newopt = json.loads(json.dumps(oldopt))
newopt['yAxis'][0]['min'] = 0
newopt['yAxis'][1]['min'] = 0
newopt['series'] = [
    {'name': 'EPS(TTM)(元)', 'type': 'bar', 'data': oldopt['series'][0]['data'],
     'itemStyle': {'color': '#2f6fb5'}, 'barWidth': '38%', 'z': 3},
    {'name': '收盘价(元)', 'type': 'line', 'smooth': True, 'yAxisIndex': 1,
     'data': oldopt['series'][1]['data'],
     'itemStyle': {'color': '#c8102e'},
     'areaStyle': {'color': 'rgba(200,16,46,0.15)'}, 'z': 2},
]

# ------------------------------------------------------- D. toc
toc = src_rep['toc']
if isinstance(toc, str):
    toc = json.loads(toc)
newtoc = []
for t in toc:
    t = dict(t)
    if t.get('anchor') == 'm29':
        t['anchor'] = 'm27'
    newtoc.append(t)
assert sum(1 for t in newtoc if t['anchor'] == 'm27') == 1, 'toc 锚点替换异常'

# ------------------------------------------------------- 前置检查：SQL 已跑？
cur = get('wb_report_mods?report_id=eq.%s&select=id,no,title' % CODE)
ids = set(m['id'] for m in cur)
nos = sorted(int(m['no']) for m in cur)
print()
print('线上当前：%d 个模块 · 编号 %s' % (len(cur), nos[:4] + ['…'] + nos[-4:]))
if CODE + '_m27' in ids and CODE + '_m31' not in ids and len(cur) == 29:
    print('  → 结构迁移已完成 ✅')
else:
    print('  → ⚠️ 结构迁移尚未完成（还看不到 m27 / 仍有 m31）。')
    print('     请先用 managePgDatabase(execute) 跑结构 SQL，再执行本脚本。')
    if not GO:
        pass
    else:
        raise SystemExit('中止：请先完成结构迁移')

print()
print('=' * 74)
print('内容变更计划')
print('=' * 74)
print('  A. m25  : %d → %d 字节（+PE/PB 两列 +估值口径）' % (len(src_mods['25']['html']), len(new_m25)))
print('  B. m27  : %d → %d 字节（+图表 chart_eps +技术解读）' % (len(old29), len(new_m27)))
print('  C. chart_eps: series[0] bar #2f6fb5 / series[1] line+area #c8102e；双轴 min=0')
print('  D. toc  : 企业评分 m29 → m27  →', json.dumps(newtoc, ensure_ascii=False))

if not GO:
    print()
    print('★ DRY-RUN —— 未写库。加 --go 执行。')
    sys.exit(0)

print()
print('=' * 74)
print('执行')
print('=' * 74)


def do(label, method, path, body):
    s, r = req(method, path, body)
    ok = s in (200, 201, 204)
    print('%s %-46s %s %s' % ('✅' if ok else '❌', label, s, '' if ok else r))
    if not ok:
        raise SystemExit('中止：%s' % label)


do('PATCH m25 html', 'PATCH', 'wb_report_mods?id=eq.%s_m25' % CODE, {'html': new_m25, 'up': nowts()})
do('PATCH m27 html', 'PATCH', 'wb_report_mods?id=eq.%s_m27' % CODE, {'html': new_m27, 'up': nowts()})
do('PATCH chart_eps opt', 'PATCH', 'wb_report_charts?id=eq.%s_chart_eps' % CODE, {'opt': newopt, 'up': nowts()})
do('PATCH wb_reports toc', 'PATCH', 'wb_reports?id=eq.%s' % CODE, {'toc': newtoc, 'up': nowts()})
print()
print('内容写入完成。')
