# -*- coding: utf-8 -*-
"""把 600456 的 m13「费用结构」图（chart6）从柱状图改为折线图，并把配色统一到全库系列色序。

改动只有两处（数据一个字节不动）：
  ① series[].type           : 'bar' -> 'line'   4 个系列全部
  ② series[].itemStyle.color: 归一为 BT_SER 前四色 红 / 青蓝 / 金 / 绿
  另加两处「与同报告 chart3 对齐」的样式项：
  ③ xAxis.axisLabel : {interval:0, fontSize:11}    8 个年份全显示，字号与 chart3 一致
  ④ grid.bottom     : 30 -> 36                     x 标签行留白与其它折线图一致

为什么要显式写色（而不是交给渲染层归一）：
  库里现在是 #caa2a8(玫瑰灰) / #c8102e / #c0392b / #b7791f。
  · 两个红(#c8102e, #c0392b)同族且明度差 0.04 < 0.26 → 渲染层 btDistinct 会改掉其中一个，
    但改完落到哪个色由「先到先得」决定，不可控；
  · 玫瑰灰 #caa2a8 虽然会被 btRetint 归到红系，但具体落到哪一档明度不可控。
  显式写 BT_SER 前四色后，btSerColor(归一) + btDistinct(去重) 全程幂等
  —— 已用 build/_try_chart6_colors.js 载入线上真实色板函数预演验证。

预演（默认，不写库）：python build/fix_600456_m13_line.py
生效：            python build/fix_600456_m13_line.py --go
"""
import copy
import io
import json
import os
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GO = '--go' in sys.argv

CFG = json.load(io.open(os.path.join(ROOT, 'build', 'cloud.json'), encoding='utf-8'))
BASE = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']
CHART_ID = '600456_chart6'

# BT_SER 前四位（全库系列色序：红 → 青蓝 → 金 → 绿）
COLORS = ['#d0202f', '#00b0f0', '#c9a227', '#0b8a5c']


def req(method, path, body=None):
    data = json.dumps(body).encode('utf-8') if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method)
    r.add_header('Authorization', 'Bearer ' + CFG['key'])
    r.add_header('Content-Type', 'application/json')
    r.add_header('Prefer', 'return=representation')
    with urllib.request.urlopen(r, timeout=90) as f:
        raw = f.read().decode('utf-8')
    return json.loads(raw) if raw.strip() else None


def md5(o):
    import hashlib
    return hashlib.md5(json.dumps(o, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


# ---------------- 1. 读线上现状 ----------------
live = req('GET', 'wb_report_charts?select=id,name,seq,opt,up&id=eq.' + CHART_ID)[0]
cur = live['opt']
if isinstance(cur, str):
    cur = json.loads(cur)

base_path = os.path.join(ROOT, 'build', '_out_chart6_live.json')
assert os.path.exists(base_path), '缺少基线文件 %s（应存放本会话开始前读到的 opt）' % base_path
baseline = json.load(io.open(base_path, encoding='utf-8'))

print('线上 %s  seq=%s  up=%s' % (live['id'], live['seq'], live.get('up')))
print('  基线 md5 %s' % md5(baseline)[:12])
print('  现况 md5 %s' % md5(cur)[:12])

# ---------------- 2. 漂移闸 ----------------
if md5(cur) != md5(baseline):
    print('\n★ 拒绝执行：线上 opt 已与本会话基线不一致（可能有并发会话改过）。')
    print('  请重新拉基线再决定，不要盲目覆盖。')
    sys.exit(2)

types = [s.get('type') for s in cur.get('series', [])]
assert types == ['bar'] * 4, '预期 4 个系列都是 bar，实际 %s —— 可能已改过，终止' % types
assert len(cur['series']) == 4, '预期 4 个系列'
datas = [list(s['data']) for s in cur['series']]
print('  4 个系列均为 bar ✓  数据点 %s' % [len(d) for d in datas])

# ---------------- 3. 构造新 opt（数据原样保留） ----------------
new = copy.deepcopy(cur)
for s, col in zip(new['series'], COLORS):
    s['type'] = 'line'
    s['smooth'] = True                      # 与同报告 chart3 写法一致（渲染层也会强制）
    s.setdefault('itemStyle', {})['color'] = col
new['xAxis'] = dict(new.get('xAxis') or {})
new['xAxis']['axisLabel'] = {'interval': 0, 'fontSize': 11}
new['grid'] = dict(new.get('grid') or {})
new['grid']['bottom'] = 36

# 数据完整性硬断言：改完的数据必须与改前逐值相等
for i, s in enumerate(new['series']):
    assert list(s['data']) == datas[i], '系列 %d 数据被改动，终止' % i
assert new['xAxis']['data'] == cur['xAxis']['data'], 'x 轴数据被改动，终止'
assert [s['name'] for s in new['series']] == [s['name'] for s in cur['series']], '系列名被改动'

print('\n--- 变更预览 ---')
for o, n in zip(cur['series'], new['series']):
    print('  %-6s  %s %-9s ->  %s %-9s' % (
        o['name'], o.get('type'), o['itemStyle'].get('color'),
        n.get('type'), n['itemStyle'].get('color')))
print('  xAxis.axisLabel  + %s' % new['xAxis']['axisLabel'])
print('  grid.bottom        %s -> %s' % ((cur.get('grid') or {}).get('bottom'), new['grid']['bottom']))
print('  4 条折线 · 数据 8 点 × 4 系列 全部原样保留 ✓')

if not GO:
    print('\n（预演模式，未写库。加 --go 生效）')
    sys.exit(0)

# ---------------- 4. 备份 + 写库 ----------------
bkdir = os.path.join(ROOT, 'build', 'backup')
if not os.path.isdir(bkdir):
    os.makedirs(bkdir)
stamp = time.strftime('%Y%m%d-%H%M%S')
bk = os.path.join(bkdir, 'chart6_pre_line_%s.json' % stamp)
io.open(bk, 'w', encoding='utf-8').write(json.dumps(cur, ensure_ascii=False, indent=1))
print('\n已备份原 opt -> %s' % os.path.relpath(bk, ROOT))

up = int(time.time() * 1000)
res = req('PATCH', 'wb_report_charts?id=eq.' + CHART_ID, {'opt': new, 'up': up})
assert isinstance(res, list) and len(res) == 1, 'PATCH 返回异常：%s' % res
print('PATCH %s  HTTP 200  返回 %d 行' % (CHART_ID, len(res)))

# ---------------- 5. 回读逐字节核对 ----------------
back = req('GET', 'wb_report_charts?select=opt&id=eq.' + CHART_ID)[0]['opt']
if isinstance(back, str):
    back = json.loads(back)
assert md5(back) == md5(new), '★ 回读与写入不一致！'
print('回读逐字节一致 ✓  md5 %s' % md5(back)[:12])
for s in back['series']:
    print('   %-6s %-5s %s' % (s['name'], s['type'], s['itemStyle']['color']))
print('\n完成。下一步：同步本地 seed -> build/sync_seed_600456_from_db.py')
