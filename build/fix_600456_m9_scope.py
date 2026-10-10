# -*- coding: utf-8 -*-
"""600456 m9：把「市场规模」表拆成「产量 / 消费量」两种口径（消除读数歧义）。

问题（本轮目视发现）：原表 4 列，把 钛加工材产量 与 钛材消费量 混在同一个「市场规模」列里，
且有两行都叫 2025；读者顺着列往下比会得出「2024 比 2023 还小 = 负增长」的错结论。

改法：加一列「口径」，按口径分组排列，并在表下写明「不可跨口径相减」。
数据一个都不改（全部来自上一轮已核实的协会/券商口径）。

两道闸：① 写前比对线上 m9 与本地 seed 的 m9（漂移闸）
        ② 写后回读逐字节比对；成功后再同步本地 seed
用法：python build/fix_600456_m9_scope.py [--go]
"""
import io, json, os, sys, time, urllib.error, urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
GO = '--go' in sys.argv
B = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(io.open(os.path.join(B, 'cloud.json'), encoding='utf-8'))
BASE = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']
CODE = '600456'
MID = '%s_m9' % CODE
SEEDP = os.path.join(B, 'seed', 'report_600456.json')

NEW_TABLE = '''<table>
      <tr><th>年份</th><th>口径</th><th>规模</th><th>同比</th><th>数据来源</th></tr>
      <tr><td>2015</td><td>钛加工材产量</td><td>4.86 万吨</td><td>—</td><td>东吴证券《宝钛转债：钛材一体化加工领军企业》2026-06-24</td></tr>
      <tr><td>2023</td><td>钛加工材产量</td><td>15.91 万吨</td><td>—</td><td>同口径 2015–2023 CAGR 15.97%（《中国钛工业发展报告》）</td></tr>
      <tr><td>2025</td><td>钛材产量</td><td>18.3 万吨</td><td>+6.4%</td><td>中国有色金属工业协会钛锆铪分会（经金天钛业 2026 半年报引述）</td></tr>
      <tr><td>2018</td><td>钛材消费量</td><td>5.7 万吨</td><td>—</td><td>《中国钛工业发展报告》</td></tr>
      <tr><td>2024</td><td>钛材消费量</td><td>15.1 万吨</td><td>—</td><td>同口径 2018–2024 CAGR 17.63%（《中国钛工业发展报告》）</td></tr>
      <tr><td>2025</td><td>钛材消费量</td><td>16.2 万吨</td><td>+7.3%</td><td>国泰海通证券《大型钛材企业，高端产品逐步发力》2026-07-30</td></tr>
    </table>
    <p class="muted" style="font-size:12.5px;">注：上表按「产量 / 消费量」两种口径分组排列，<b>同一列不可跨口径直接比较</b>——2024 年消费量（15.1 万吨）低于 2023 年产量（15.91 万吨）只因口径不同，并非负增长；同口径内 2025 年为最新披露年度。</p>'''


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


def swap(old):
    i, j = old.index('<table>'), old.index('</table>') + len('</table>')
    return old[:i] + NEW_TABLE + old[j:]


# ---------------------------------------------------------- 1. 取线上现值 + 漂移闸
live = get('wb_report_mods?select=id,html,no,seq&id=eq.%s' % MID)
assert len(live) == 1, '没取到 %s' % MID
cur = live[0]['html']
seed = json.load(io.open(SEEDP, encoding='utf-8'))
seed9 = [m for m in seed['mods'] if str(m.get('no')) == '9'][0]['html']

print('=' * 74)
print('漂移闸')
print('=' * 74)
print('  线上 m9  %d 字符' % len(cur))
print('  本地 seed m9 %d 字符' % len(seed9))
assert cur == seed9, '★ 线上 m9 与本地 seed 不一致 —— 期间有人在网页端改过，拒绝覆盖'
print('  两者逐字节一致 ✓')
assert '市场规模' in cur, '★ 线上 m9 里找不到旧表头，结构已变，拒绝盲改'

new = swap(cur)
print()
print('=' * 74)
print('改动预览')
print('=' * 74)
print('  旧：%d 字符 · 表头 年份|市场规模|同比增速|备注' % len(cur))
print('  新：%d 字符 · 表头 年份|口径|规模|同比|数据来源' % len(new))
assert new.count('<tr>') == 7, '新表应有 1 表头 + 6 数据行 = 7 个 tr，实为 %d' % new.count('<tr>')
assert '[MISSING]' not in new and '**' not in new, '新 HTML 含占位符或未渲染的 Markdown'
assert new != cur, '没变化'
# 数据必须原样保留（只加列、不改数）
for v in ('4.86 万吨', '5.7 万吨', '15.91 万吨', '15.1 万吨', '18.3 万吨', '16.2 万吨',
          '+6.4%', '+7.3%'):
    assert v in new, '丢了原有数据：%s' % v
print('  原有 6 个规模值与 2 个同比全部保留 ✓')
print('  新增：口径列 + 表下口径注脚')
for ln in new.split('\n')[1:7]:
    print('    ' + ln.strip()[:96])

if not GO:
    print()
    print('（预演模式，未写库。加 --go 生效）')
    raise SystemExit(0)

# ---------------------------------------------------------- 2. 写库
print()
ts = int(time.time() * 1000)
st, res = req('PATCH', 'wb_report_mods?id=eq.%s' % MID, {'html': new, 'up': ts})
n = len(res) if isinstance(res, list) else 0
print('  PATCH %-12s HTTP %s  返回 %d 行' % (MID, st, n))
assert st in (200, 204) and n == 1, 'PATCH 失败：%s %s' % (st, res)

# ---------------------------------------------------------- 3. 回读 + 同步 seed
back = get('wb_report_mods?select=id,html,up&id=eq.%s' % MID)[0]
same = back['html'] == new
print('  回读 %d 字符  逐字节一致 %s' % (len(back['html']), '✓' if same else '★ 否'))
assert same, '回读不一致'

for m in seed['mods']:
    if str(m.get('no')) == '9':
        m['html'] = new
io.open(SEEDP, 'w', encoding='utf-8').write(
    json.dumps(seed, ensure_ascii=False, separators=(',', ':')))
seed2 = json.load(io.open(SEEDP, encoding='utf-8'))
s9 = [m for m in seed2['mods'] if str(m.get('no')) == '9'][0]['html']
assert s9 == new, '本地 seed 同步失败'
print('  本地 seed 已同步 %d 字节 · 模块数 %d · [MISSING] %d 处'
      % (os.path.getsize(SEEDP), len(seed2['mods']),
         sum(1 for m in seed2['mods'] if '[MISSING]' in (m.get('html') or ''))))
