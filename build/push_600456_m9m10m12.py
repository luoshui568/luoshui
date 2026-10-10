# -*- coding: utf-8 -*-
"""600456 宝钛股份：把补好的 m9 / m10 / m12 定点写回云端库。

为什么走定点 PATCH 而不是重跑 report_build_v31.py：
  · 600456 已裁成 29 模块，而 report_build_v31.py 的主流程断言编号 1..31 → 必崩；
  · 整份覆盖还会抹掉网页端的在线改动。

两道闸：
  ① 写作前用**基线快照**（build/_out_bt_mods.json，本会话读的库内原值）比对线上现况，
     不一致就拒绝执行（说明期间有人在网页端改过）；
  ② 写作后回读，逐字节比对。
"""
import io, json, os, sys, time, urllib.error, urllib.request, importlib.util

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
GO = '--go' in sys.argv
B = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(B)
CFG = json.load(io.open(os.path.join(B, 'cloud.json'), encoding='utf-8'))
BASE = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']
CODE = '600456'
TARGETS = ['%s_m9' % CODE, '%s_m10' % CODE, '%s_m12' % CODE]


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


# ------------------------------------------------------------- 1. 渲染新 HTML
spec = importlib.util.spec_from_file_location('rb31', os.path.join(B, 'report_build_v31.py'))
rb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rb)

d = json.load(io.open(os.path.join(B, 'seed', 'data_v31_600456.json'), encoding='utf-8'))
d.setdefault('code', CODE)
NEW = {'%s_m9' % CODE: rb.m9(d), '%s_m10' % CODE: rb.m10(d), '%s_m12' % CODE: rb.m12(d)}

print('=' * 74)
print('新 HTML（渲染自 build/seed/data_v31_600456.json）')
print('=' * 74)
for k in TARGETS:
    h = NEW[k]
    print('  %-12s %5d 字符   [MISSING] %d 处' % (k, len(h), h.count('[MISSING]')))
assert not any('[MISSING]' in NEW[k] for k in TARGETS), '仍有 [MISSING]，先补完再写'

# ------------------------------------------------------------- 2. 漂移闸
snap = json.load(io.open(os.path.join(B, '_out_bt_mods.json'), encoding='utf-8'))
snap = {r['id']: r['html'] for r in snap if r['id'] in TARGETS}
assert set(snap) == set(TARGETS), '基线快照不完整：%s' % sorted(snap)

print()
print('漂移闸（线上现况 vs 本会话基线）')
live = get('wb_report_mods?select=id,html,no,seq&id=in.(%s)&order=seq.asc' % ','.join(TARGETS))
live = {r['id']: r['html'] for r in live}
drift = []
for k in TARGETS:
    same = live.get(k) == snap.get(k)
    print('  %-12s %s' % (k, '一致 ✓' if same else '★ 已被改动，差异 %d 字符'
                          % (len(live.get(k) or '') - len(snap.get(k) or ''))))
    if not same:
        drift.append(k)
if drift:
    raise SystemExit('★ %s 在本次会话期间被改动过 —— 拒绝覆盖，请人工确认' % drift)

# ------------------------------------------------------------- 3. 写库
if not GO:
    print()
    print('（预演模式，未写库。加 --go 生效）')
    raise SystemExit(0)

print()
ts = int(time.time() * 1000)
for k in TARGETS:
    st, res = req('PATCH', 'wb_report_mods?id=eq.%s' % k,
                  {'html': NEW[k], 'up': ts})
    n = len(res) if isinstance(res, list) else 0
    print('  PATCH %-12s HTTP %s  返回 %d 行' % (k, st, n))
    assert st in (200, 204), 'PATCH 失败：%s %s' % (st, res)
    assert n == 1, '受影响行数应为 1，实为 %d' % n

# ------------------------------------------------------------- 4. 回读校验
print()
print('回读校验')
back = get('wb_report_mods?select=id,html,up&id=in.(%s)&order=seq.asc' % ','.join(TARGETS))
ok = True
for r in back:
    k = r['id']
    same = r['html'] == NEW[k]
    ok = ok and same
    print('  %-12s %5d 字符  [MISSING] %d 处  逐字节一致 %s'
          % (k, len(r['html']), r['html'].count('[MISSING]'), '✓' if same else '★ 否'))
assert ok, '回读不一致'

# 顺带确认另外 26 个模块没被碰到
allm = get('wb_report_mods?select=id,html&id=like.%s_m*&order=seq.asc&limit=200' % CODE)
tot = sum(x['html'].count('[MISSING]') for x in allm)
print()
print('  600456 全部 %d 个模块，[MISSING] 合计 %d 处' % (len(allm), tot))
print('  （补前基线：m9=3 / m10=2 / m12=2，合计 7 处 → 现应为 0 处）')
