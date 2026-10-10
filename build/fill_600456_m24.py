# -*- coding: utf-8 -*-
"""600456 宝钛股份：补 m24（历年分红与股东回报）的 15 处 [MISSING]，
并给 chartDividend 补上「每股收益」空序列。

数据链（每一步都可复算）：
  归母净利 fin.np        → 来自 iFinD（已在 data_v31_600456.json）
  每股股利 fin.dps       → 同上，与库内 m24 表一致
  总股本 477,777,539 股  → 《2025年年度报告》p47「利润分配」（2024/2025 两次分红均以此基数）
  年末收盘价             → 通达信月线（不复权）
  交叉验证：DPS × 总股本 是否等于年报披露的分红总额
      2024 年度：0.39 × 4.77777539 亿股 = 1.8633 亿  ←→ 年报 186,333,240.21 元 ✓
      2025 年度：0.30 × 4.77777539 亿股 = 1.4333 亿  ←→ 年报 143,333,261.70 元 ✓
"""
import io, json, os, sys, time, urllib.error, urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
GO = '--go' in sys.argv
B = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(io.open(os.path.join(B, 'cloud.json'), encoding='utf-8'))
BASE = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']

SHARES = 477777539          # 股
SH = SHARES / 1e8           # 亿股 = 4.77777539
YEARS = ['2021', '2022', '2023', '2024', '2025']
DPS = [0.85, 0.45, 0.35, 0.39, 0.30]                    # fin.dps
NP = [5.6028, 5.5716, 5.4422, 5.7645, 4.009]            # fin.np（亿元）
CLOSE = [71.78, 40.86, 31.39, 28.45, 39.45]             # 通达信月线，各年末收盘价（不复权）

EPS = [round(n / SH, 3) for n in NP]
PAYOUT = [d / e * 100 for d, e in zip(DPS, EPS)]
YIELD = [d / c * 100 for d, c in zip(DPS, CLOSE)]
AMT = [d * SH for d in DPS]                              # 现金分红总额（亿元）

print('=' * 78)
print('600456 m24 分红明细重算（总股本 %s 股）' % format(SHARES, ','))
print('=' * 78)
print('%-6s %-9s %-9s %-9s %-9s %-9s' % ('年份', '每股股利', '每股收益', '分红率', '股息率', '分红总额'))
for i, y in enumerate(YEARS):
    print('%-6s %-9s %-9s %-9s %-9s %-9s' % (
        y, '%.2f 元' % DPS[i], '%.3f 元' % EPS[i],
        '%.2f%%' % PAYOUT[i], '%.2f%%' % YIELD[i], '%.4f 亿' % AMT[i]))
print()
print('交叉验证（DPS × 总股本 应等于年报披露的分红总额）：')
print('  2024 年度  算出 %.4f 亿  vs  年报 1.8633 亿（186,333,240.21 元）  %s'
      % (AMT[3], '✓' if abs(AMT[3] - 1.8633) < 5e-4 else '★'))
print('  2025 年度  算出 %.4f 亿  vs  年报 1.4333 亿（143,333,261.70 元）  %s'
      % (AMT[4], '✓' if abs(AMT[4] - 1.4333) < 5e-4 else '★'))
assert abs(AMT[3] - 1.8633) < 5e-4 and abs(AMT[4] - 1.4333) < 5e-4, '交叉验证失败，拒绝写入'

# ------------------------------------------------------------------ 新 m24 HTML
trs = '\n      '.join(
    '<tr><td>%s</td><td>%.2f 元</td><td>%.3f 元</td><td>%.2f%%</td><td>%.2f%%</td></tr>'
    % (y, DPS[i], EPS[i], PAYOUT[i], YIELD[i]) for i, y in enumerate(YEARS))

M24 = '''<p class="muted" style="font-size:13px;">注：公司为国企控股，股东回报意识较强，上市以来持续现金分红。下表为 2021–2025 年分红明细实证数据。</p>
    <div class="grid2">
      <div>
        <h3>分红特征</h3>
        <ul style="margin-left:18px;font-size:13.5px;">
          <li>国企控股，分红意愿与制度保障较强；《公司章程》规定最近三年现金分红累计不少于年均可分配利润的 30%；</li>
          <li>2021 年盈利高峰时分红率高达 72.48%，2022–2024 年回落并稳定在 30%~39% 区间；</li>
          <li>2025 年归母净利 4.01 亿元、分红率 35.75%，每股派现 0.30 元，绝对额随盈利同步收敛；</li>
          <li>2026 年可转债发行后进入资本开支高峰期，分红率上行空间受限。</li>
        </ul>
      </div>
      <div>
        <h3>股东回报对比</h3>
        <table>
          <tr><th>维度</th><th>宝钛股份</th><th>对比</th></tr>
          <tr><td>累计募资</td><td>≈78 亿元</td><td>持续资本开支型</td></tr>
          <tr><td>2025年归母净利</td><td>4.01 亿元</td><td>同比 -30.5%</td></tr>
          <tr><td>2025年度分红总额</td><td>1.4333 亿元</td><td>每股 0.30 元（含税）</td></tr>
          <tr><td>当前PB</td><td>1.72 倍</td><td>高于破净线</td></tr>
          <tr><td>当前PE</td><td>36.2 倍</td><td>盈利低位估值偏高</td></tr>
        </table>
      </div>
    </div>
    <p class="src"><b>来源：</b>每股股利与归母净利取自 iFinD；总股本 477,777,539 股取自《2025 年年度报告》第 47 页「利润分配」（2024、2025 两个年度分红均以此为基数）。每股收益 = 归母净利 ÷ 总股本；分红率 = 每股股利 ÷ 每股收益；股息率 = 每股股利 ÷ 当年末收盘价（通达信月线，不复权）。交叉验证：每股股利 × 总股本 得到的 2024 / 2025 年度分红总额 1.8633 / 1.4333 亿元与年报披露值（186,333,240.21 / 143,333,261.70 元）一致。⚠️ 每股收益为按期末总股本折算值，与年报「基本每股收益」（加权平均股本口径）可能存在小数级差异。</p>
    <h3>历年分红明细</h3><table>
      <tr><th>年份</th><th>每股股利</th><th>每股收益</th><th>分红率</th><th>当期股息率</th></tr>
      __TRS__
    </table><div data-chart="chartDividend" class="chart-box"></div>'''

# ⚠️ 不能用 % 格式化：模板正文里有「30%」这类字面百分号 → ValueError: unsupported format character
M24 = M24.replace('__TRS__', trs)

print()
print('新 m24：%d 字符，[MISSING] %d 处（原 15 处）'
      % (len(M24), M24.count('[MISSING]')))
assert '[MISSING]' not in M24

# ------------------------------------------------------------------ 网络
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


# 漂移闸：线上现状必须与本轮读取的基线一致
live_m = get('wb_report_mods?select=html&id=eq.600456_m24')[0]['html']
live_c = get('wb_report_charts?select=opt&id=eq.600456_chartDividend')[0]['opt']
if isinstance(live_c, str):
    live_c = json.loads(live_c)
n_miss = live_m.count('[MISSING]')
print()
print('漂移闸：线上 m24 共 %d 处 [MISSING]（本会话读到的是 15 处）' % n_miss)
assert n_miss == 15, '线上 m24 已变动（%d 处），拒绝覆盖' % n_miss
assert live_c['series'][1]['name'] == '每股收益' and live_c['series'][1]['data'] == [], \
    'chartDividend 的每股收益序列已非空，拒绝覆盖'

NEWC = json.loads(json.dumps(live_c))
NEWC['series'][1]['data'] = EPS
NEWC['series'][1]['label'] = {'show': True, 'position': 'top', 'fontSize': 11, 'color': '#a3122a'}

if not GO:
    print()
    print('（预演模式，未写盘。加 --go 生效）')
    raise SystemExit(0)

ts = int(time.time() * 1000)
print()
st, res = req('PATCH', 'wb_report_mods?id=eq.600456_m24', {'html': M24, 'up': ts})
print('  PATCH 600456_m24            HTTP %s  返回 %d 行'
      % (st, len(res) if isinstance(res, list) else 0))
assert st == 200 and len(res) == 1
st, res = req('PATCH', 'wb_report_charts?id=eq.600456_chartDividend',
              {'opt': json.dumps(NEWC, ensure_ascii=False), 'up': ts})
print('  PATCH 600456_chartDividend  HTTP %s  返回 %d 行'
      % (st, len(res) if isinstance(res, list) else 0))
assert st == 200 and len(res) == 1

# 回读
back = get('wb_report_mods?select=html&id=eq.600456_m24')[0]['html']
bc = get('wb_report_charts?select=opt&id=eq.600456_chartDividend')[0]['opt']
if isinstance(bc, str):
    bc = json.loads(bc)
print()
print('回读校验')
print('  m24 逐字节一致 %s，[MISSING] %d 处' % ('✓' if back == M24 else '★', back.count('[MISSING]')))
print('  每股收益序列 = %s  %s' % (bc['series'][1]['data'],
                                 '✓' if bc['series'][1]['data'] == EPS else '★'))
assert back == M24 and bc['series'][1]['data'] == EPS
print()
allm = get('wb_report_mods?select=id,html&id=like.600456_m*&order=seq.asc&limit=200')
print('  600456 全部 %d 个模块，[MISSING] 合计 %d 处 → 应为 0' %
      (len(allm), sum(x['html'].count('[MISSING]') for x in allm)))
