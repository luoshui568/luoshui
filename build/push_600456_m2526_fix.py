# -*- coding: utf-8 -*-
"""600456 · 2026-09-17 第二轮：模块 25/26 预测数据对齐 + 模块 26 图表整行居中美化 + PE 改蓝

用户原话：
  「模块25和模块26的预测数据保持严谨一致」
  「模块26 这个图表都居中单独一行，样式花里胡哨一点，PE和PB不要都是红色一个改成蓝色」

------------------------------------------------------------------
★ 口径裁定：以**预测模型图 chartEstimate** 为唯一权威（它在模块 25 内部）
    chartEstimate 中性：2023/2024/2025/2026E/2027E/2028E
      营业收入（中性） 69.27 / 66.57 / 61.24 / [62.5] / 65.0 / 68.5
      归母净利（中性）  5.44 /  5.76 /  4.01 / [ 4.3] /  4.8 /  5.5
    ⇒ 模块 25 中性「61~64 亿 / 4.0~4.5 亿」正好覆盖 62.5 / 4.3  ✅ 保留
    ⇒ 模块 26 中性「4.5-5.0 亿」明显高于模型 4.3 亿      ❌ 改
  另外模块 25 的 PE / PB 自查全部自洽（130÷2.5~3.0=43~52；27.35÷15.77=1.73…），
  所以**只改模块 26，不动模块 25 的数值**，只把模块 25 的两个列名说清口径。

★ 两处口径必须显式区分（否则看起来像互相矛盾）：
    模块 25  PE（当前价）  = 当前总市值 ÷ 该情景 2026E 归母净利
    模块 26  参考 PE 区间  = 目标估值倍数（用来推目标市值/股价）
  同一张报告里出现两种 PE 是合理的，但**必须标清楚**，所以列名与注脚都改了。

★ 顺带对齐的两处（属于同一处「不严谨」的延伸，一并说明）：
    ① 模块 27 技术解读里写「盈利回升至 6-7 亿」超出模块 25 乐观上限 6.5 亿
       → 改成「5.5~6.5 亿（模块 25 乐观情景）… PE 回落至 20~24 倍」
    ② 模块 25 「关键敏感变量」段的 Markdown ** 星号（sanitizeHtml 不认）→ <b>

数据源：线上当前状态（带漂移闸：先 GET 回来核对锚点，不一致就拒绝执行）。
用法：python build/push_600456_m2526_fix.py          # dry-run
      python build/push_600456_m2526_fix.py --go     # 真写库
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
    """⚠️ up 列是 bigint（毫秒），传 ISO 串会 22P02。"""
    return int(time.time() * 1000)


# =====================================================================
# 0. 取线上现状（漂移闸）
# =====================================================================
print('=' * 76)
print('0. 读线上现状')
print('=' * 76)
mods = get('wb_report_mods?report_id=eq.%s&select=id,no,title,html' % CODE)
byid = {m['id']: m for m in mods}
print('  模块数 =', len(mods))
for k in ('%s_m25' % CODE, '%s_m26' % CODE, '%s_m27' % CODE):
    m = byid.get(k)
    assert m, '线上缺少 %s' % k
    print('  %-12s no=%-3s %-16s html=%d 字符' % (k, m['no'], m['title'], len(m['html'])))

cur_m25 = byid['%s_m25' % CODE]['html']
cur_m26 = byid['%s_m26' % CODE]['html']
cur_m27 = byid['%s_m27' % CODE]['html']

charts = get('wb_report_charts?report_id=eq.%s&select=id,name,opt' % CODE)
cbyid = {c['id']: c for c in charts}
ck = '%s_chart_pbpe' % CODE
assert ck in cbyid, '线上缺少图表 %s（现有：%s）' % (ck, sorted(cbyid)[:6])
print('  图表数 =', len(charts), ' · 目标图表', ck)
old_opt = cbyid[ck]['opt']
if isinstance(old_opt, str):
    old_opt = json.loads(old_opt)

# =====================================================================
# 1. 模块 25 —— 数值不动，只把列名 / 假设 / 注脚 / 星号改清楚
# =====================================================================
print()
print('=' * 76)
print('1. 模块 25')
print('=' * 76)

m25 = cur_m25
REP25 = [
    # (旧, 新, 次数)
    ('<th>PE（倍）</th><th>PB（倍）</th>',
     '<th>PE（当前价）</th><th>PB（当前价）</th>', 1),
    ('<tr><td>悲观</td><td>化工需求继续下行、航空订单不及预期；钛价再跌 5%</td>',
     '<tr><td><span class="tag neg">悲观</span></td>'
     '<td>钛价再跌 5%、化工需求下行、航空订单不及预期；可转债项目延后</td>', 1),
    ('<tr><td>中性</td><td>营收企稳、产品结构向航空倾斜；毛利率维持 20% 附近</td>',
     '<tr><td><span class="tag info">中性</span></td>'
     '<td>钛价企稳、C919 量产推进、产能逐步释放；毛利率维持 20% 附近</td>', 1),
    ('<tr><td>乐观</td><td>C919 放量 + 化工复苏；航空级占比提升带动毛利率回升至 23%</td>',
     '<tr><td><span class="tag pos">乐观</span></td>'
     '<td>钛价回升 + C919 放量 + 化工复苏；毛利率回升至 23%</td>', 1),
    # ★ Markdown ** 残留 → <b>（sanitizeHtml 不认 Markdown，页面上会原样显示星号）
    ('最敏感的变量是**航空级产品占比**与**海绵钛价格**：',
     '最敏感的变量是<b>航空级产品占比</b>与<b>海绵钛价格</b>：', 1),
]
for a, b, n in REP25:
    c = m25.count(a)
    assert c == n, 'm25 锚点「%s」出现 %d 次（期望 %d）' % (a[:32], c, n)
    m25 = m25.replace(a, b)
    print('  ✅ 替换', a[:40].replace('\n', ' '))
NOTE25 = (
    '<div class="logic"><div class="lt">口径与一致性</div><div class="lv">'
    '三档营业收入与归母净利和 <b>模块 26「情景推演」逐格一致</b>（同一套假设、同一份模型，'
    '中性 2026E 营收 62.5 亿 / 归母净利 4.3 亿即本表 61~64 亿 / 4.0~4.5 亿的中值）。'
    'PE = 当前总市值 130 亿元 ÷ 该情景 2026E 归母净利（<b>当前股价口径</b>）；'
    'PB = 当前股价 27.35 元 ÷ 该情景 2026E 期末每股净资产'
    '（按利润全额留存测算，基数 15.19 元/股、总股本 4.75 亿股）。'
    '股价与市值按 2026-08-24 收盘固定，与模块 26 / 模块 27 评分卡同源。'
    '<b>模块 26 的「参考 PE 区间」是目标估值倍数，与本表口径不同，不可直接相减。</b>'
    '</div></div>')
OLD_NOTE25 = ('<div class="logic"><div class="lt">估值口径</div><div class="lv">'
              'PE = 当前总市值 130 亿元 ÷ 2026E 归母净利；'
              'PB = 当前股价 27.35 元 ÷ 2026E 期末每股净资产'
              '（按 2026 年利润全额留存测算，总股本 4.75 亿股）。'
              '三档差异全部来自盈利预测，股价与市值按 2026-08-24 收盘固定，'
              '与模块 27 评分卡取数一致。</div></div>')
assert m25.count(OLD_NOTE25) == 1, 'm25 旧注脚锚点不唯一'
m25 = m25.replace(OLD_NOTE25, NOTE25)
print('  ✅ 注脚 估值口径 → 口径与一致性（补 PE 两种口径的区分说明）')
new_m25 = m25

# =====================================================================
# 2. 模块 26 —— 数据对齐 + 图表整行居中 + 可比公司整行居中
# =====================================================================
print()
print('=' * 76)
print('2. 模块 26')
print('=' * 76)

ASSUM = {
    'neg': '钛价再跌 5%、化工需求下行、航空订单不及预期；可转债项目延后',
    'info': '钛价企稳、C919 量产推进、产能逐步释放；毛利率维持 20% 附近',
    'pos': '钛价回升 + C919 放量 + 化工复苏；毛利率回升至 23%',
}
# 归母净利：悲观 2.5~3.0 / 中性 4.0~4.5 / 乐观 5.5~6.5（= 模块 25，逐格一致）
# 对应市值/股价 = 净利 × 参考 PE ÷ 4.75 亿股
SIM = [
    ('neg', '30×', '75~90 亿 / 15.8~18.9 元'),
    ('info', '30~35×', '120~158 亿 / 25.3~33.2 元'),
    ('pos', '35~40×', '193~260 亿 / 40.5~54.7 元'),
]
NP = {'neg': ('55~58 亿', '2.5~3.0 亿'), 'info': ('61~64 亿', '4.0~4.5 亿'),
      'pos': ('68~72 亿', '5.5~6.5 亿')}
rows = ''
for k, pe, mv in SIM:
    rev, prof = NP[k]
    rows += ('      <tr><td><span class="tag %s">%s</span></td><td>%s</td>'
             '<td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>\n'
             % (k, {'neg': '悲观', 'info': '中性', 'pos': '乐观'}[k],
                ASSUM[k], rev, prof, pe, mv))

new_m26 = '''<div class="grid3">
      <div class="stat"><div class="label">PB（MRQ）</div><div class="val">1.80 <small>倍</small></div><div class="label" style="margin-top:4px;">高于破净线</div></div>
      <div class="stat"><div class="label">PE（TTM）</div><div class="val">34 <small>倍</small></div><div class="label" style="margin-top:4px;">盈利低位估值偏高</div></div>
      <div class="stat"><div class="label">EPS（TTM）</div><div class="val">≈0.80 <small>元</small></div><div class="label" style="margin-top:4px;">2025 年归母 4.0 亿 / 4.78 亿股</div></div>
    </div>
    <div class="val-hero" style="max-width:1000px;margin:18px auto 8px;padding:14px 18px 10px;">
      <div class="vh-head" style="display:flex;flex-wrap:wrap;align-items:center;gap:9px;padding-bottom:9px;border-bottom:1px dashed #f0dcdf;">
        <span class="vh-t" style="font-size:16px;font-weight:800;color:#4a0710;">PB / PE 历史走势</span>
        <span class="vh-legend" style="margin-left:auto;display:flex;gap:14px;font-size:12px;color:#7c5c62;font-weight:600;">
          <span><i style="display:inline-block;width:16px;height:4px;border-radius:2px;margin-right:5px;vertical-align:4px;background:#c8102e;"></i>PB（左轴）</span>
          <span><i style="display:inline-block;width:16px;height:4px;border-radius:2px;margin-right:5px;vertical-align:4px;background:#2f6fb5;"></i>PE(TTM)（右轴）</span>
        </span>
      </div>
      <div data-chart="chart_pbpe" class="chart-box"></div>
      <p class="src"><b>来源：</b>宝钛股份研究报告 PPTX 幻灯片 48（2026-08，估值）。PB 历史区间约 1.2–5.7 倍，当前 1.80 倍处于中低位（红色面积即 PB 估值底）；PE(TTM) 波动显著大于 PB，当前 34 倍处于近年偏高水平。</p>
    </div>
    <div class="peer-wrap" style="max-width:1000px;margin:16px auto 8px;padding:14px 18px 12px;">
      <h3>可比公司</h3>
      <table class="peer-table">
        <tr><th>公司</th><th>定位</th><th>对比说明</th></tr>
        <tr><td>宝钛股份（600456）</td><td>钛加工材龙头</td><td>全产业链，国企</td></tr>
        <tr><td>西部材料（002149）</td><td>钛加工材</td><td>2023 年产量 8473 吨，占比 7%</td></tr>
        <tr><td>西部超导（688122）</td><td>钛合金/超导</td><td>2023 年产量 10695 吨，占比 8.3%</td></tr>
      </table>
      <p class="muted" style="font-size:12.5px;">三家公司合计占全国钛加工材产量约 40%，宝钛股份占约 24% 为绝对龙头。</p>
    </div>
    <h3>情景推演（与模块 25 同一套假设）</h3>
    <table>
      <tr><th>情景</th><th>核心假设</th><th>2026E 营收</th><th>2026E 归母净利</th><th>参考 PE 区间</th><th>对应市值 / 股价</th></tr>
''' + rows + '''    </table>
    <div class="logic"><div class="lt">估值口径</div><div class="lv">营业收入与归母净利<b>直接取模块 25 的三档情景</b>（同一套假设，逐格一致）；市值 = 该情景归母净利 × 参考 PE 区间，股价 = 市值 ÷ 总股本 4.75 亿股。参考 PE 是<b>目标估值倍数</b>，与模块 25 的「当前价 PE」口径不同、不可直接比较。对照模块 27 评分卡：参考买入价 17–19 元对应悲观情形估值区间（15.8–18.9 元），目标价 40 元贴近乐观情形下沿（40.5 元），取值偏保守。</div></div>'''

# 漂移闸：m26 里应能找到旧的 5 列情景推演表
assert '情景推演（分析框架，非目标价预测）' in cur_m26, 'm26 漂移：找不到旧的情景推演标题'
assert '≈3.5亿' in cur_m26, 'm26 漂移：找不到旧净利 ≈3.5亿'
print('  ✅ 漂移闸通过（旧表 5 列 / 净利 ≈3.5亿 均在）')
print('  · 情景推演表 5 列 → 6 列，净利改 2.5~3.0 / 4.0~4.5 / 5.5~6.5')
print('  · 市值/股价 重算：75~90 / 120~158 / 193~260 亿')
print('  · chart_pbpe 由 .grid2 两栏 → .val-hero 整行居中（400px）')
print('  · 可比公司 → .peer-wrap 整行居中卡片')

# =====================================================================
# 3. 模块 27 —— 技术解读里的「6-7 亿」对齐到模块 25 乐观区间
# =====================================================================
print()
print('=' * 76)
print('3. 模块 27（技术解读口径对齐）')
print('=' * 76)
A27 = '盈利回升至6-7亿可推动PE回归20-25倍合理区间'
B27 = '盈利回升至 5.5~6.5 亿（模块 25 乐观情景）可推动 PE 回落至 20~24 倍（按当前股价计）'
assert cur_m27.count(A27) == 1, 'm27 锚点出现 %d 次' % cur_m27.count(A27)
new_m27 = cur_m27.replace(A27, B27)
print('  ✅', A27, '→', B27)

# =====================================================================
# 4. chart_pbpe —— PE 改蓝 + 美化
# =====================================================================
print()
print('=' * 76)
print('4. chart_pbpe')
print('=' * 76)
PB_D = old_opt['series'][0]['data']
PE_D = old_opt['series'][1]['data']
RED, BLUE = '#c8102e', '#2f6fb5'
new_opt = {
    'grid': {'top': 58, 'left': 62, 'right': 66, 'bottom': 34, 'containLabel': False},
    'xAxis': {
        'data': old_opt['xAxis']['data'],
        'type': 'category',
        'boundaryGap': False,
        'axisTick': {'show': False},
        'axisLine': {'lineStyle': {'color': '#f0dcdf'}},
        'axisLabel': {'rotate': 0, 'fontSize': 10, 'interval': 0, 'color': '#9a7d82'},
    },
    'yAxis': [
        {'name': 'PB(倍)', 'type': 'value', 'min': 0,
         'nameTextStyle': {'color': RED, 'fontWeight': 'bold', 'fontSize': 12},
         'axisLabel': {'color': RED, 'fontSize': 11},
         'axisLine': {'show': True, 'lineStyle': {'color': 'rgba(200,16,46,.35)'}},
         'splitLine': {'lineStyle': {'color': 'rgba(200,16,46,.09)', 'type': 'dashed'}}},
        {'name': 'PE(倍)', 'type': 'value', 'min': 0,
         'nameTextStyle': {'color': BLUE, 'fontWeight': 'bold', 'fontSize': 12},
         'axisLabel': {'color': BLUE, 'fontSize': 11},
         'axisLine': {'show': True, 'lineStyle': {'color': 'rgba(47,111,181,.35)'}},
         'splitLine': {'show': False}},
    ],
    'legend': {
        'data': ['PB', 'PE(TTM)'], 'top': 4, 'right': 8,
        'icon': 'roundRect', 'itemWidth': 16, 'itemHeight': 8, 'itemGap': 18,
        'textStyle': {'color': '#7c5c62', 'fontSize': 12, 'fontWeight': 'bold'},
    },
    'series': [
        {'name': 'PB', 'type': 'line', 'data': PB_D, 'smooth': True,
         'symbol': 'circle', 'symbolSize': 7, 'showSymbol': True, 'z': 3,
         'itemStyle': {'color': RED, 'borderColor': '#fff', 'borderWidth': 1.5},
         'lineStyle': {'width': 3, 'color': RED, 'shadowColor': 'rgba(200,16,46,.35)',
                       'shadowBlur': 12, 'shadowOffsetY': 6},
         'areaStyle': {'color': {
             'type': 'linear', 'x': 0, 'y': 0, 'x2': 0, 'y2': 1,
             'colorStops': [{'offset': 0, 'color': 'rgba(200,16,46,.30)'},
                            {'offset': 1, 'color': 'rgba(200,16,46,.02)'}]}},
         'markLine': {
             'silent': True, 'symbol': 'none',
             'lineStyle': {'color': 'rgba(200,16,46,.55)', 'type': 'dashed', 'width': 1.4},
             'label': {'formatter': '当前 {c}×', 'color': RED, 'fontSize': 11,
                       'fontWeight': 'bold', 'position': 'insideEndTop'},
             'data': [{'yAxis': 1.8}]}},
        {'name': 'PE(TTM)', 'type': 'line', 'data': PE_D, 'smooth': True,
         'symbol': 'circle', 'symbolSize': 7, 'showSymbol': True, 'yAxisIndex': 1, 'z': 2,
         'itemStyle': {'color': BLUE, 'borderColor': '#fff', 'borderWidth': 1.5},
         'lineStyle': {'width': 3, 'color': BLUE, 'shadowColor': 'rgba(47,111,181,.30)',
                       'shadowBlur': 12, 'shadowOffsetY': 6},
         'markLine': {
             'silent': True, 'symbol': 'none',
             'lineStyle': {'color': 'rgba(47,111,181,.50)', 'type': 'dashed', 'width': 1.4},
             'label': {'formatter': '当前 {c}×', 'color': BLUE, 'fontSize': 11,
                       'fontWeight': 'bold', 'position': 'insideEndTop'},
             'data': [{'yAxis': 34}]}},
    ],
    'tooltip': {
        'trigger': 'axis',
        'axisPointer': {'type': 'cross', 'crossStyle': {'color': '#d8b6bb'},
                        'label': {'backgroundColor': '#8c0a20'}},
        'backgroundColor': 'rgba(255,255,255,.97)',
        'borderColor': '#f0dcdf', 'borderWidth': 1,
        'textStyle': {'color': '#4a0710', 'fontSize': 12.5},
        'extraCssText': 'box-shadow:0 8px 22px rgba(82,18,26,.14);border-radius:10px;'
                        'padding:8px 12px;',
    },
}
assert new_opt['series'][0]['itemStyle']['color'] == RED
assert new_opt['series'][1]['itemStyle']['color'] == BLUE
print('  ✅ PB = %s（红，左轴，带渐变面积 + 当前值参考线）' % RED)
print('  ✅ PE(TTM) = %s（蓝，右轴，带当前值参考线）  ← 原来也是红色，已改' % BLUE)
print('  ✅ 两条线：lineWidth 3 + 阴影发光 + 圆点；双轴 min=0；轴色与系列同色')

# =====================================================================
# 执行
# =====================================================================
print()
print('=' * 76)
print('变更计划')
print('=' * 76)
print('  A. m25  %5d → %5d 字符' % (len(cur_m25), len(new_m25)))
print('  B. m26  %5d → %5d 字符' % (len(cur_m26), len(new_m26)))
print('  C. m27  %5d → %5d 字符（仅技术解读一句）' % (len(cur_m27), len(new_m27)))
print('  D. chart_pbpe opt 重写（series 2 条 / yAxis 2 条 / +markLine/legend/tooltip）')
print('  E. 其他 28 个模块、21 张图表、其余 4 份研报：一律不动')

if not GO:
    print()
    print('★ DRY-RUN —— 未写库。加 --go 执行。')
    sys.exit(0)

print()
print('=' * 76)
print('执行')
print('=' * 76)


def do(label, method, path, body):
    s, r = req(method, path, body)
    ok = s in (200, 201, 204)
    print('%s %-44s %s %s' % ('✅' if ok else '❌', label, s, '' if ok else r))
    if not ok:
        raise SystemExit('中止：%s' % label)


do('PATCH m25 html', 'PATCH', 'wb_report_mods?id=eq.%s_m25' % CODE,
   {'html': new_m25, 'up': nowts()})
do('PATCH m26 html', 'PATCH', 'wb_report_mods?id=eq.%s_m26' % CODE,
   {'html': new_m26, 'up': nowts()})
do('PATCH m27 html', 'PATCH', 'wb_report_mods?id=eq.%s_m27' % CODE,
   {'html': new_m27, 'up': nowts()})
do('PATCH chart_pbpe opt', 'PATCH', 'wb_report_charts?id=eq.%s' % ck,
   {'opt': new_opt, 'up': nowts()})
print()
print('写入完成 → 接着跑 build/refresh_seed_600456.py 重刷兜底 seed。')
