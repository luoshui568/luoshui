# -*- coding: utf-8 -*-
"""恢复 600456 丢失的 chartDividend（每股股利与每股收益）。

背景：2026-09-20 11:50 有一次「600456 重排为 31 模块」的批量写库，之后
      m15「历年分红与股东回报」的图槽 <div data-chart="chartDividend"> 还在引用它，
      但 wb_report_charts 里的那一行没了（库里 21 张图 / 22 个图槽）——
      页面上这张图会渲染成「图表暂无数据」。
      本地 seed 里定义完好（含 2026-09-19 补的 EPS 序列），直接用它恢复。

幂等：若库里已存在 600456_chartDividend，只做一致性比对，不重复插入。

预演：python build/restore_600456_chartDividend.py
生效：python build/restore_600456_chartDividend.py --go
"""
import io
import json
import os
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
B = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(B)
CFG = json.load(io.open(os.path.join(B, 'cloud.json'), encoding='utf-8'))
BASE = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']
GO = '--go' in sys.argv
CODE = '600456'
CHART_ID = CODE + '_chartDividend'


def req(method, path, body=None):
    data = json.dumps(body).encode('utf-8') if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method)
    r.add_header('Authorization', 'Bearer ' + CFG['key'])
    r.add_header('Content-Type', 'application/json')
    r.add_header('Prefer', 'return=representation')
    with urllib.request.urlopen(r, timeout=90) as f:
        raw = f.read().decode('utf-8')
    return json.loads(raw) if raw.strip() else None


def norm(o):
    return json.dumps(o, ensure_ascii=False, sort_keys=True)


# ---------------- 1. seed 里的定义 ----------------
seed = json.load(io.open(os.path.join(B, 'seed', 'report_%s.json' % CODE), encoding='utf-8'))
c = [x for x in seed['charts'] if x['id'] == 'chartDividend']
assert c, 'seed 里没有 chartDividend'
c = c[0]
MISSING_KEYS = [k for k in ('seq', 'name', 'opt') if k not in c]
assert not MISSING_KEYS, 'seed 定义缺字段 %s' % MISSING_KEYS
print('seed 定义：%s  seq=%s  name=%s' % (c['id'], c.get('seq'), c.get('name')))
for s in c['opt']['series']:
    print('   %-8s %-5s %s' % (s['name'], s.get('type'), s.get('data')))

# 图槽挂在哪个模块
holder = None
for m in seed['mods']:
    if 'data-chart="chartDividend"' in (m.get('html') or ''):
        holder = m
        break
print('图槽所在模块：m%s %s' % (holder['no'], holder['title']) if holder else '★ 没找到引用它的模块')

# ---------------- 2. 库里现状 ----------------
exist = req('GET', 'wb_report_charts?select=id,name,seq,opt&id=eq.' + CHART_ID)
if exist:
    row = exist[0]
    same = norm(row['opt']) == norm(c['opt'])
    print('\n库里已存在该图（不重复插入）。opt 与 seed %s' % ('一致 ✓' if same else '不一致 ★'))
    if same:
        print('无需修复。')
        raise SystemExit(0)
    print('需要更新的字段：opt')
    newopt = c['opt']
else:
    print('\n库里确认缺失 → 需要插入')

# ---------------- 3. 预览 ----------------
row = {
    'id': CHART_ID,
    'report_id': CODE,
    'code': CODE,
    'seq': c.get('seq', 20),
    'name': c.get('name') or '每股股利与每股收益',
    'opt': c['opt'],
    'up': int(time.time() * 1000),
}
print('\n--- 待写入 ---')
for k, v in row.items():
    s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
    print('   %-10s = %s' % (k, s[:80]))

if not GO:
    print('\n（预演模式，未写库。加 --go 生效）')
    raise SystemExit(0)

# ---------------- 4. 写入 ----------------
if exist:
    res = req('PATCH', 'wb_report_charts?id=eq.' + CHART_ID, {'opt': row['opt'], 'up': row['up']})
    print('\nPATCH %s 返回 %d 行' % (CHART_ID, len(res)))
else:
    res = req('POST', 'wb_report_charts', [row])
    print('\nPOST 插入返回 %d 行' % len(res))
    assert len(res) == 1 and res[0]['id'] == CHART_ID, '插入返回异常：%s' % res

# ---------------- 5. 回读 ----------------
after = req('GET', 'wb_report_charts?select=id,report_id,code,seq,name,opt,up&id=eq.' + CHART_ID)[0]
assert after['report_id'] == CODE and after['code'] == CODE, 'report_id/code 不对'
assert norm(after['opt']) == norm(c['opt']), '★ 回读 opt 与 seed 不一致'
print('回读逐字节一致 ✓  seq=%s  name=%s' % (after['seq'], after['name']))
for s in after['opt']['series']:
    print('   %-8s %-5s %s' % (s['name'], s.get('type'), s.get('data')))

# 全库图槽自检
mods = req('GET', 'wb_report_mods?select=no,title,html&report_id=eq.%s&limit=200' % CODE)
chs = req('GET', 'wb_report_charts?select=id&report_id=eq.%s&limit=200' % CODE)
live = {x['id'].replace(CODE + '_', '') for x in chs}
import re
bad = []
for m in mods:
    for k in re.findall(r'data-chart\s*=\s*["\']([^"\']+)', m['html'] or ''):
        if k not in live:
            bad.append((m['no'], m['title'], k))
print('\n[自检] 模块 %d 个 · 库里图 %d 张 · 挂不上的图槽 %s'
      % (len(mods), len(live), bad or '无 ✓'))
