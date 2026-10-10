# -*- coding: utf-8 -*-
"""把所有研报的图表 opt 从线上拉下来，供 beauty() 单测使用。
   为什么：beauty() 是渲染层全局改造，对**全部研报**生效，只测 600456 不够。
   顺带输出图型分布，确认覆盖面。"""
import io, json, os, urllib.request
from collections import Counter, defaultdict

B = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
CFG = json.load(io.open(os.path.join(B, 'build', 'cloud.json'), encoding='utf-8'))
BASE = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']


def get(path):
    r = urllib.request.Request(BASE + path)
    r.add_header('Authorization', 'Bearer ' + CFG['key'])
    with urllib.request.urlopen(r, timeout=90) as f:
        return json.loads(f.read().decode('utf-8'))


rows = []
off = 0
while True:
    p = 'wb_report_charts?select=id,report_id,seq,name,opt&order=id.asc&limit=1000&offset=%d' % off
    b = get(p)
    rows += b
    if len(b) < 1000:
        break
    off += 1000

print('线上图表总数 =', len(rows))

codes = defaultdict(list)
for c in rows:
    opt = c['opt']
    if isinstance(opt, str):
        try:
            opt = json.loads(opt)
        except Exception:
            opt = None
    if not opt or not opt.get('series'):
        continue
    rid = c['report_id']
    codes[rid].append({'id': c['id'], 'seq': c['seq'], 'name': c['name'], 'opt': opt})

print()
print('%-12s %-6s %s' % ('研报', '图表', '图型分布'))
tot = 0
for k in sorted(codes):
    lst = codes[k]
    tot += len(lst)
    kinds = Counter()
    for c in lst:
        kinds['+'.join(sorted(set(str(s.get('type') or 'line') for s in c['opt']['series'])))] += 1
    print('%-12s %-6d %s' % (k, len(lst), '  '.join('%s×%d' % (a, b) for a, b in sorted(kinds.items()))))
print('%-12s %-6d' % ('合计', tot))

flat = [c for k in sorted(codes) for c in codes[k]]
io.open(os.path.join(B, 'build', '_all_charts.json'), 'w', encoding='utf-8').write(
    json.dumps({'charts': flat}, ensure_ascii=False))
print()
print('已写 build/_all_charts.json ，共', len(flat), '张图（含全部研报）')
