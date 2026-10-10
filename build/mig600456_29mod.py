# -*- coding: utf-8 -*-
"""600456 宝钛股份：31 模块 → 29 模块 迁移。

做四件事（用户 2026-09-17 确认，全选推荐方案）：
  1. 删除 m27（估值敏感性）、m28（公司股价表现）+ 图表 chartSens
  2. 编号整位重排：m29→m27、m30→m28、m31→m29（id/ no / seq 全改）
  3. m25（盈利预测模型）三档情景表增加 PE / PB 两列
  4. chart_eps（EPS 与股价）挪到新 m27（企业评分）评分卡上方，并改造：
     EPS → 蓝色柱状图，收盘价 → 红色面积图

默认 dry-run；加 --go 才写库。
"""
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
    return time.strftime('%Y-%m-%dT%H:%M:%S')


# --------------------------------------------------------------- 读现状
mods = {str(m['no']): m for m in get('wb_report_mods?report_id=eq.%s&select=*' % CODE)}
charts = {c['id'].replace(CODE + '_', ''): c
          for c in get('wb_report_charts?report_id=eq.%s&select=*' % CODE)}
rep = get('wb_reports?id=eq.%s&select=*' % CODE)[0]

print('现网 600456：模块 %d 个 · 图表 %d 张' % (len(mods), len(charts)))

# --------------------------------------------------------------- 漂移闸
assert len(mods) == 31, '模块数应为 31，实际 %d —— 线上状态已漂移，中止' % len(mods)
assert len(charts) == 23, '图表数应为 23，实际 %d —— 线上状态已漂移，中止' % len(charts)
assert '企业评分' in mods['29']['title'], 'm29 应是「企业评分」，实际 %s' % mods['29']['title']
assert '多空论点' in mods['30']['title'], 'm30 应是「多空论点对照」，实际 %s' % mods['30']['title']
assert '投资结论' in mods['31']['title'], 'm31 应是「投资结论」，实际 %s' % mods['31']['title']
assert '估值敏感性' in mods['27']['title'], 'm27 应是「估值敏感性」，实际 %s' % mods['27']['title']
assert '股价表现' in mods['28']['title'], 'm28 应是「公司股价表现」，实际 %s' % mods['28']['title']
assert 'chart_eps' in charts and 'chartSens' in charts, 'chart_eps / chartSens 缺失'
assert '三档情景假设' in mods['25']['html'], 'm25 正文结构不符（缺「三档情景假设」）'
assert 'chart_eps' in mods['28']['html'], 'm28 正文里应含 chart_eps 引用'
assert '技术解读' in mods['28']['html'], 'm28 正文里应含「技术解读」'
print('漂移闸：全部通过 ✅')

# --------------------------------------------------------------- 1) m25 加 PE / PB 两列
m25 = mods['25']['html']
pairs = [
    ('<th>2026E 归母净利</th>', '<th>2026E 归母净利</th><th>PE（倍）</th><th>PB（倍）</th>'),
    ('<td>55~58 亿</td><td>2.5~3.0 亿</td>', '<td>55~58 亿</td><td>2.5~3.0 亿</td><td>43~52</td><td>1.73</td>'),
    ('<td>61~64 亿</td><td>4.0~4.5 亿</td>', '<td>61~64 亿</td><td>4.0~4.5 亿</td><td>29~33</td><td>1.70</td>'),
    ('<td>68~72 亿</td><td>5.5~6.5 亿</td>', '<td>68~72 亿</td><td>5.5~6.5 亿</td><td>20~24</td><td>1.66</td>'),
]
for a, b in pairs:
    assert m25.count(a) == 1, 'm25 里「%s」出现 %d 次（应为 1）' % (a, m25.count(a))
    m25 = m25.replace(a, b)

NOTE = ('<div class="logic"><div class="lt">估值口径</div><div class="lv">'
        'PE = 当前总市值 130 亿元 ÷ 2026E 归母净利；PB = 当前股价 27.35 元 ÷ 2026E 期末每股净资产'
        '（按 2026 年利润全额留存测算，总股本 4.75 亿股）。三档差异全部来自盈利预测，'
        '股价与市值按 2026-08-24 收盘固定，与模块 27 的评分卡取数一致。</div></div>')
ANCH = '</table>\n    <div data-chart="chartEstimate"'
assert m25.count(ANCH) == 1, 'm25 里表格-图表衔接处不唯一（%d）' % m25.count(ANCH)
m25 = m25.replace(ANCH, '</table>\n    ' + NOTE + '\n    <div data-chart="chartEstimate"')
new_m25 = m25

# --------------------------------------------------------------- 2) 新 m27 = 图表 + 技术解读 + 原企业评分
old29 = mods['29']['html']
old28 = mods['28']['html']

# 从 m28 里抠出「技术解读」那一段
i = old28.find('<h3>技术解读</h3>')
j = old28.find('</p>', old28.find('<p style="font-size:13.5px;">', i)) + len('</p>')
assert i > 0 and j > len('<h3>技术解读</h3>'), '未能从 m28 抠出技术解读段'
tech = old28[i:j]
tech = tech.replace('<p style="font-size:13.5px;">', '<p>')   # 全宽了，恢复正文字号

HEAD = ('<h3>EPS 与股价历史</h3>\n'
        '    <div data-chart="chart_eps" class="chart-box"></div>\n'
        '    <p class="src"><b>来源：</b>宝钛股份研究报告 PPTX 幻灯片 49（2026-08，市值）；'
        'EPS(TTM) 与收盘价历史走势。</p>\n'
        '    ')
new_m27 = HEAD + tech + '\n    ' + old29

# --------------------------------------------------------------- 3) chart_eps 改造
oldopt = charts['chart_eps']['opt']
if isinstance(oldopt, str):
    oldopt = json.loads(oldopt)
newopt = json.loads(json.dumps(oldopt))          # 深拷贝，保留 grid/xAxis 等原有字段
newopt['yAxis'][0]['min'] = 0
newopt['yAxis'][1]['min'] = 0
newopt['series'] = [
    {   # EPS → 柱状图 · 蓝
        'name': 'EPS(TTM)(元)', 'type': 'bar',
        'data': oldopt['series'][0]['data'],
        'itemStyle': {'color': '#2f6fb5'},
        'barWidth': '38%', 'z': 3,
    },
    {   # 收盘价 → 面积图 · 红
        'name': '收盘价(元)', 'type': 'line', 'smooth': True, 'yAxisIndex': 1,
        'data': oldopt['series'][1]['data'],
        'itemStyle': {'color': '#c8102e'},
        'areaStyle': {'color': 'rgba(200,16,46,0.15)'},
        'z': 2,
    },
]

# --------------------------------------------------------------- 4) 研报头 toc
toc = rep['toc']
if isinstance(toc, str):
    toc = json.loads(toc)
newtoc = []
for t in toc:
    t = dict(t)
    if t.get('anchor') == 'm29':
        t['anchor'] = 'm27'
    newtoc.append(t)
assert any(t['anchor'] == 'm27' for t in newtoc), 'toc 里没找到 m29 项'
assert not any(t['anchor'] == 'm29' for t in newtoc), 'toc 里仍有 m29'

# --------------------------------------------------------------- 汇总计划
print()
print('=' * 74)
print('变更计划')
print('=' * 74)
print('1) 删除模块  : m27 估值敏感性 · m28 公司股价表现')
print('2) 删除图表  : chartSens（估值敏感性热力图）')
print('3) 重排编号  : m29→m27 · m30→m28 · m31→m29（id/no/seq 同步）')
print('4) 改写 m25  : 三档情景表 + PE/PB 两列（+1 行估值口径注脚）')
print('   %d → %d 字节' % (len(mods['25']['html']), len(new_m25)))
print('5) 改写新 m27: 图表 chart_eps + 技术解读 插到评分卡上方')
print('   %d → %d 字节' % (len(old29), len(new_m27)))
print('6) 改造 chart_eps:')
print('   EPS(TTM)(元)  line #c8102e → bar #2f6fb5（38% 宽, z=3）')
print('   收盘价(元)    line #c0392b → line+area #c8102e（填充 rgba(200,16,46,0.15), z=2）')
print('   双 Y 轴均设 min=0（面积图必须从 0 起，否则失真）')
print('7) 研报头 toc : 企业评分 anchor m29 → m27')

if not GO:
    print()
    print('★ DRY-RUN —— 未写库。确认无误后加 --go 执行。')
    sys.exit(0)

print()
print('=' * 74)
print('执行')
print('=' * 74)


def do(label, method, path, body=None, expect=(200, 201, 204)):
    s, r = req(method, path, body)
    ok = s in expect
    print('%s %-52s %s %s' % ('✅' if ok else '❌', label, s, '' if ok else r))
    if not ok:
        raise SystemExit('中止：%s' % label)
    return r


# 4-1 先删，腾出编号
do('DELETE m27', 'DELETE', 'wb_report_mods?id=eq.%s_m27' % CODE)
do('DELETE m28', 'DELETE', 'wb_report_mods?id=eq.%s_m28' % CODE)
do('DELETE chartSens', 'DELETE', 'wb_report_charts?id=eq.%s_chartSens' % CODE)

# 4-2 升序改 id（29→27 先释放 29，再 30→28，最后 31→29）—— 不会撞主键
do('PATCH m29 → m27 (id/no/seq/html)', 'PATCH', 'wb_report_mods?id=eq.%s_m29' % CODE,
   {'id': '%s_m27' % CODE, 'no': '27', 'seq': 27, 'html': new_m27, 'up': nowts()})
do('PATCH m30 → m28 (id/no/seq)', 'PATCH', 'wb_report_mods?id=eq.%s_m30' % CODE,
   {'id': '%s_m28' % CODE, 'no': '28', 'seq': 28, 'up': nowts()})
do('PATCH m31 → m29 (id/no/seq)', 'PATCH', 'wb_report_mods?id=eq.%s_m31' % CODE,
   {'id': '%s_m29' % CODE, 'no': '29', 'seq': 29, 'up': nowts()})

# 4-3 其余改写
do('PATCH m25 html（+PE/PB）', 'PATCH', 'wb_report_mods?id=eq.%s_m25' % CODE,
   {'html': new_m25, 'up': nowts()})
do('PATCH chart_eps opt（柱+面积）', 'PATCH', 'wb_report_charts?id=eq.%s_chart_eps' % CODE,
   {'opt': newopt, 'up': nowts()})
do('PATCH 研报头 toc', 'PATCH', 'wb_reports?id=eq.%s' % CODE,
   {'toc': newtoc, 'up': nowts()})

print()
print('写库完成，开始回读核对…')
