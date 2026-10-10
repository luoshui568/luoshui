# -*- coding: utf-8 -*-
"""600456 宝钛股份 · 模块 11「公司产品收入与毛利结构」—— 补一张「毛利构成」图。

背景（2026-09-20 用户要求）：
    「帮我在同一行的位置再加一个图，毛利润构成比例」
原本模块 11 只有一张 `chart2`（产品收入构成环形图）独占整行，右侧/下方是两张表。
本次把「收入构成」与「毛利构成」放到**同一行并排**，并把表格里空着的毛利率补全。

★ 为什么并排不需要动渲染层：
   `stackWide()` 早有分支（2026-09-20 加的）——`.grid2` 的**两个子块全是图、
   无文字子块、无表格** ⇒ 加 `.gr-pair`（两栏、图高 340px、≤860px 回落单列）。
   所以模块 11 拆成**两个 `.grid2`**：
     ① 两个子块各含一个图槽  → 命中 gr-pair ⇒ 并排
     ② 一个子块含表格        → 走 gr-stack ⇒ 整行卡片
   零 CSS 新增、零 JS 改动。

★ 数据来源（2025 年报，报告期 2025-12-31）：
   东方财富 F9「主营构成（按产品）」与同花顺 iFinD「主营构成」**交叉核对逐项一致**：
       钛产品       收入 52.66 亿(85.99%)  成本 40.25 亿  毛利 12.41 亿  毛利率 23.56%  毛利占比 102.00%
       其他金属产品  收入  4.81 亿( 7.85%)  成本  5.06 亿  毛利 -0.26 亿  毛利率 -5.36%  毛利占比  -2.12%
       其他业务      收入  3.78 亿( 6.17%)  成本  3.77 亿  毛利  0.01 亿  毛利率  0.24%  毛利占比   0.07%
       合计         收入 61.24 亿(100%  )  成本 49.08 亿  毛利 12.16 亿  毛利率 19.85%  毛利占比 100%
   ⚠️ 毛利占比合计 100% 而钛产品单项 102% —— **不是笔误**，是因为其他金属产品
      亏毛利把分母拉低了。图上与表格里都保留原值并写明口径，不做归一化处理
      （若强行按绝对值归一，会让人误以为其他金属产品贡献正毛利 —— 那是失真）。

★ 为什么毛利构成图用**横向条形**而不是第二个环形：
   环形/饼图无法表达负值。其他金属产品毛利占比 -2.12%，若按绝对值画进环里，
   读者会以为它贡献了正毛利。横向条形能同时显示正负，并且把
   「收入占比 vs 毛利占比」并列，一眼看出「有收入、没利润」。

用法：
    python build/mkmod11_bstn.py                  # 干跑：只体检 + 打印对比，不写任何地方
    python build/mkmod11_bstn.py --go             # 只写本地 seed（先渲染验证再推库）
    python build/mkmod11_bstn.py --go --push      # 写本地 seed + 推云端（模块 PATCH / 图表 upsert）
"""
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
BASE = os.path.dirname(os.path.abspath(__file__))
SEED = os.path.join(BASE, 'seed', 'report_600456.json')
BAK = os.path.join(BASE, 'backup')

RID = '600456'
MODID = '%s_m11' % RID
CHART_ID = 'chartGrossMix'
CHART_SEQ = 22          # 线上 seq 1..21 + 23，22 正好是空位
CHART_NAME = '毛利构成 vs 收入构成（2025）'
# 漂移闸的基准 = **第一次跑时**线上 m11 的内容（自动落盘，之后不再改写）。
# ⚠️ 不能拿「当前本地 seed」当基准：本地一旦改成新版，第二次跑必然报漂移、把自己挡住
#    （2026-09-20 踩过）。
BASELINE = os.path.join(BAK, 'mod11_%s_baseline.html' % RID)

CFG = json.load(io.open(os.path.join(BASE, 'cloud.json'), encoding='utf-8'))
REST = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']
HDR = {'Authorization': 'Bearer ' + CFG['key'], 'Content-Type': 'application/json',
       'Prefer': 'resolution=merge-duplicates,return=minimal'}

# ---------------------------------------------------------------- 数据（单位：%）
GROSS = [   # 名称, 收入占比, 毛利率, 毛利占比
    ('钛产品',       85.99, 23.56, 102.00),
    ('其他金属产品',  7.85, -5.36,  -2.12),
    ('其他业务',      6.17,  0.24,   0.07),
]


def _num(v):
    """-5.36 → -5.36 ；102.0 → 102.00（保留两位，负号用 ASCII 连字符）"""
    return ('%.2f' % v)


def build_table():
    out = ['        <table>',
           '          <tr><th>板块</th><th>收入占比</th><th>毛利率</th><th>毛利占比</th></tr>']
    for name, rev, gm, gp in GROSS:
        out.append('          <tr><td>%s</td><td>%s%%</td><td>%s%%</td><td>%s%%</td></tr>'
                   % (name, _num(rev), _num(gm), _num(gp)))
    out.append('          <tr><td><b>合计</b></td><td>100.00%%</td><td>19.85%%</td><td>100.00%%</td></tr>')
    out.append('        </table>')
    return '\n'.join(out)


MOD_HTML = '''<div class="grid2">
      <div>
        <h3>产品收入构成（2025）</h3>
        <div data-chart="chart2" class="chart-box short"></div>
      </div>
      <div>
        <h3>毛利构成（2025）</h3>
        <div data-chart="%s" class="chart-box short"></div>
      </div>
    </div>
    <div class="grid2">
      <div>
        <h3>分板块收入与毛利结构（2025）</h3>
%s
        <p class="muted" style="font-size:12.5px;">毛利几乎全部来自钛产品：其毛利占比 102.00%%，高于 100%% 是因为其他金属产品亏损、把合并毛利的分母拉低了；其他金属产品毛利率 -5.36%%、毛利占比 -2.12%%，其他业务毛利率 0.24%%、毛利占比 0.07%%，均基本不贡献利润。收入口径的集中度（钛产品 85.99%%）明显低于毛利口径（102.00%%），说明非钛业务目前仍处「有收入、少利润」阶段。钛产品含金属复合材、海绵锆等在内的其他产品线尚未形成第二增长曲线。2025 年钛产品单吨毛利约 4.21 万元。</p>
        <h3 style="margin-top:14px;">钛产品收入与成本（2025）</h3>
        <table>
          <tr><th>指标</th><th>数值</th></tr>
          <tr><td>钛产品销售收入</td><td>52.70 亿元</td></tr>
          <tr><td>钛产品销售成本</td><td>40.30 亿元</td></tr>
          <tr><td>钛产品销量</td><td>29,466 吨</td></tr>
          <tr><td>销售均价</td><td>17.89 万元/吨</td></tr>
          <tr><td>成本均价</td><td>13.68 万元/吨</td></tr>
        </table>
        <p class="src"><b>来源：</b>东方财富 F9「主营构成（按产品）」（2025 年报，报告期 2025-12-31），经同花顺 iFinD 同口径交叉核对，逐项一致；收入占比 / 毛利率 / 毛利占比均为定期报告分产品口径，合计行为分产品加总。收入结构另见宝钛股份研究报告 PPTX 幻灯片16（2026-08）。</p>
      </div>
    </div>''' % (CHART_ID, build_table())

# 收入构成图（chart2）里写的是「其他产品 7.8%」，年报分产品口径叫「其他金属产品 7.85%」，
# 名称沿用年报口径、数值取年报精度，图上两者并列时以本表为准。

CHART_OPT = {
    'legend': {'bottom': 0},
    # left=104：y 轴类目名最长「其他金属产品」6 字，12px 下约 76px，再留一点间距，
    # 否则在半栏宽度里会贴到卡片左边框（首版 left=90 就是这样）。
    # top=58 与 pairTopPad() 给并排窄栏定的值一致，写成一样是让函数幂等、不再二次抬高。
    'grid': {'left': 104, 'right': 62, 'top': 58, 'bottom': 46},
    # min/max 取 -20/120 而非 -14/112：后者会让 ECharts 排出 -14/0/30/60/90/112 这种
    # 参差刻度；取整十后是 -20/0/20/…/120，整齐且 0 轴位置更居中。
    'xAxis': {'type': 'value', 'min': -20, 'max': 120,
              'axisLabel': {'formatter': '{value}%'}},
    'yAxis': {'type': 'category', 'data': ['其他业务', '其他金属产品', '钛产品']},
    'series': [
        {'name': '收入占比', 'type': 'bar', 'barWidth': 15, 'barGap': '26%',
         'itemStyle': {'color': '#00b0f0'},
         'label': {'show': True, 'position': 'right', 'formatter': '{c}%'},
         'data': [6.17, 7.85, 85.99]},
        {'name': '毛利占比', 'type': 'bar', 'barWidth': 15, 'barGap': '26%',
         'itemStyle': {'color': '#d0202f'},
         'label': {'show': True, 'position': 'right', 'formatter': '{c}%'},
         # 负值：柱子与标签都用「跌绿」，且标签挪到柱子左侧，避免压住 0 轴
         'data': [0.07,
                  {'value': -2.12, 'itemStyle': {'color': '#0b8a5c'},
                   'label': {'position': 'left', 'color': '#0b8a5c'}},
                  102.0]},
    ],
    'tooltip': {'trigger': 'axis'},
}

WANT_MOD = MOD_HTML
WANT_CHART = {'seq': CHART_SEQ, 'id': CHART_ID, 'name': CHART_NAME, 'opt': CHART_OPT}


def req(path, method='GET', body=None, timeout=120):
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
    r = urllib.request.Request(REST + path, data=data, headers=HDR, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            raw = resp.read().decode('utf-8', 'replace')
            return resp.status, (json.loads(raw) if raw.strip() else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')[:600]
    except Exception as e:
        return 0, str(e)


def main():
    go = '--go' in sys.argv
    seed = json.load(io.open(SEED, encoding='utf-8'))
    old_mod = [m for m in seed['mods'] if str(m['no']) == '11'][0]['html']
    old_ch = [c for c in seed['charts'] if c.get('id') == CHART_ID]
    ids = [c.get('id') for c in seed['charts']]

    print('=== 1) 本地现状 ===')
    print('模块 11 旧正文 %d 字符；图表 %d 张；%s 已存在：%s'
          % (len(old_mod), len(seed['charts']), CHART_ID, bool(old_ch)))
    print('待写入模块 11 %d 字符（%+d）' % (len(WANT_MOD), len(WANT_MOD) - len(old_mod)))

    print('\n=== 2) 结构自检 ===')
    chk = [
        ('两个图槽', WANT_MOD.count('data-chart=') == 2),
        ('收入构成 chart2', 'data-chart="chart2"' in WANT_MOD),
        ('毛利构成 %s' % CHART_ID, 'data-chart="%s"' % CHART_ID in WANT_MOD),
        ('两个 grid2 容器', WANT_MOD.count('class="grid2"') == 2),
        ('表格补全毛利率', '23.56%' in WANT_MOD and '-5.36%' in WANT_MOD),
        ('毛利占比列', '102.00%' in WANT_MOD and '-2.12%' in WANT_MOD),
        ('数据源标注', '东方财富' in WANT_MOD and '同花顺' in WANT_MOD),
        ('图表 id 不重复', ids.count(CHART_ID) <= 1),
        ('seq %d 未被占用' % CHART_SEQ,
         all(c.get('seq') != CHART_SEQ for c in seed['charts'] if c.get('id') != CHART_ID)),
        ('负值项带独立色', CHART_OPT['series'][1]['data'][1]['itemStyle']['color'] == '#0b8a5c'),
        ('口径注脚（>100% 说明）', '分母拉低' in WANT_MOD),
    ]
    for k, v in chk:
        print('    %-26s %s' % (k, '✓' if v else '❌'))
    assert all(v for _, v in chk), '结构自检未通过，中止'

    print('\n=== 3) 读线上现状 ===')
    st, live_mod = req('wb_report_mods?id=eq.%s&select=id,no,title,html,up' % MODID)
    assert st == 200 and isinstance(live_mod, list) and live_mod, '读模块失败 %s %s' % (st, live_mod)
    live_html = live_mod[0]['html']
    up = live_mod[0].get('up')
    print('线上 m11《%s》%d 字符  up=%s'
          % (live_mod[0]['title'], len(live_html),
             time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(up) / 1000)) if up else '-'))
    os.makedirs(BAK, exist_ok=True)
    if not os.path.exists(BASELINE):
        io.open(BASELINE, 'w', encoding='utf-8').write(live_html)
        print('  首次运行 → 记录基线（改动前的线上内容）：%s' % os.path.basename(BASELINE))
    base = io.open(BASELINE, encoding='utf-8').read()
    if live_html == WANT_MOD:
        print('  线上已是本次要写入的版本（无需再推）。')
    drift = (live_html != base)
    print('线上 m11 == 基线（首次运行时的线上内容）：%s%s'
          % (not drift, '  ← ⚠ 线上被别处改过！' if drift else ''))
    if drift and '--force' not in sys.argv:
        print('\n[中止] 线上模块与基线不符（可能有并发会话），确认后加 --force。')
        return

    st, live_ch = req('wb_report_charts?id=eq.%s&select=id,seq,name' % ('%s_%s' % (RID, CHART_ID)))
    print('线上 %s 行：%s' % (CHART_ID, live_ch or '（无，将新增）'))

    if not go:
        print('\n[dry-run] 未写任何地方。加 --go 执行。')
        return
    push = '--push' in sys.argv

    ts = time.strftime('%Y%m%d-%H%M%S')
    os.makedirs(BAK, exist_ok=True)
    bp = os.path.join(BAK, 'mod11_%s_pre_grossmix_%s.json' % (RID, ts))
    io.open(bp, 'w', encoding='utf-8').write(json.dumps(
        {'ts': ts, 'rid': RID, 'mod': live_mod, 'chart': live_ch}, ensure_ascii=False))
    print('\n=== 4) 备份线上现状 → %s ===' % os.path.basename(bp))

    print('=== 5) 写本地 seed ===')
    for m in seed['mods']:
        if str(m['no']) == '11':
            m['html'] = WANT_MOD
    seed['charts'] = [c for c in seed['charts'] if c.get('id') != CHART_ID]
    seed['charts'].append(dict(WANT_CHART))
    seed['charts'].sort(key=lambda c: c.get('seq') or 0)
    io.open(SEED, 'w', encoding='utf-8').write(json.dumps(seed, ensure_ascii=False, indent=1))
    print('  已写 %s（模块 %d 个 / 图表 %d 张）' % (os.path.basename(SEED), len(seed['mods']), len(seed['charts'])))

    print('=== 6) 推云端 ===')
    if not push:
        print('  [未推库] 本地 seed 已就绪，确认渲染无误后再加 --push。')
        return
    now = int(time.time() * 1000)
    st, r = req('wb_report_mods?id=eq.%s' % MODID, 'PATCH', {'html': WANT_MOD, 'up': now})
    print('  PATCH 模块 11：%s %s' % (st, '' if st < 400 else r))
    assert st < 400, '模块写入失败'

    row = {'id': '%s_%s' % (RID, CHART_ID), 'report_id': RID, 'code': RID,
           'seq': CHART_SEQ, 'name': CHART_NAME, 'opt': CHART_OPT, 'up': now}
    st, r = req('wb_report_charts', 'POST', [row])
    print('  UPSERT 图表 %s：%s %s' % (CHART_ID, st, '' if st < 400 else r))
    assert st < 400, '图表写入失败'

    print('=== 7) 回读核对 ===')
    st, rb = req('wb_report_mods?id=eq.%s&select=html' % MODID)
    ok_mod = (st == 200 and rb[0]['html'] == WANT_MOD)
    print('  模块 11 正文逐字节一致：%s' % ok_mod)
    st, rc = req('wb_report_charts?id=eq.%s_%s&select=opt,seq,name' % (RID, CHART_ID))
    ok_ch = (st == 200 and rc and rc[0]['opt'] == CHART_OPT)
    print('  图表 %s 配置一致：%s  seq=%s' % (CHART_ID, ok_ch, rc[0].get('seq') if rc else '-'))
    st, cnt = req('wb_report_charts?report_id=eq.%s&select=id' % RID)
    print('  600456 图表总数：%d（本地 seed %d 张）%s'
          % (len(cnt), len(seed['charts']), '✓' if len(cnt) == len(seed['charts']) else '⚠'))
    st, cnt2 = req('wb_report_mods?report_id=eq.%s&select=id' % RID)
    # ⚠️ 模块数**不要写死**：2026-09-20 有并发会话把 600456 从 31 模块重排成 30，
    #    写死 31 会让每次推库都报「未通过」假红。以本地 seed 为基准比对。
    print('  600456 模块总数：%d（本地 seed %d 个）%s'
          % (len(cnt2), len(seed['mods']), '✓' if len(cnt2) == len(seed['mods']) else '⚠'))
    st, mm = req('wb_report_charts?id=eq.600456_chart2&select=opt')
    print('  老图 chart2 未被波及：%s' % ('钛产品' in json.dumps(mm[0]['opt'], ensure_ascii=False)))
    ok = (ok_mod and ok_ch and len(cnt) == len(seed['charts']) and len(cnt2) == len(seed['mods']))
    print('\n%s' % ('全部通过 ✓' if ok else '⚠ 存在未通过项'))


if __name__ == '__main__':
    main()
