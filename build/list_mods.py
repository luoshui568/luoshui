# -*- coding: utf-8 -*-
"""只读：拉某份研报的模块清单（no + title）与六篇目录，供排位用。"""
import io, json, os, sys, urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
B = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(io.open(os.path.join(B, 'cloud.json'), encoding='utf-8'))
BASE = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']
HDR = {'apikey': CFG['key'], 'Authorization': 'Bearer ' + CFG['key'], 'Accept': 'application/json'}

CODE = sys.argv[1] if len(sys.argv) > 1 else '600456'


def get(path):
    rq = urllib.request.Request(BASE + path, headers=HDR)
    with urllib.request.urlopen(rq, timeout=60) as r:
        return json.loads(r.read().decode('utf-8'))


rep = get('wb_reports?select=*&code=eq.%s' % CODE)
if not rep:
    print('库里没有 code=%s 的研报' % CODE); raise SystemExit(1)
r = rep[0]
print('=== 研报 %s | %s ===' % (r.get('code'), r.get('name')))
toc = r.get('toc')
if isinstance(toc, str):
    toc = json.loads(toc)
print('目录（%d 条）:' % len(toc or []))
for t in (toc or []):
    print('   %-8s %s' % (t.get('anchor'), t.get('text')))

mods = get('wb_report_mods?select=id,no,seq,title&id=like.%s_m*&order=no.asc&limit=500' % CODE)
mods.sort(key=lambda x: int(x.get('no') or 0))   # ⚠️ 库里 no 是文本 → order=no.asc 是字典序，必须在本地按整数重排
print()
print('模块（%d 个）:' % len(mods))
anch = {t.get('anchor'): t.get('text') for t in (toc or [])}
for m in mods:
    key = 'm%s' % m.get('no')
    mark = ('  <<< 篇首：' + anch[key]) if key in anch else ''
    print('  %-4s seq=%-4s %s%s' % (m.get('no'), m.get('seq'), m.get('title'), mark))

print()
print('=== 换行分隔（便于复制） ===')
print('\n'.join('%s. %s' % (m.get('no'), m.get('title')) for m in mods))
