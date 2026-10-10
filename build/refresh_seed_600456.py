# -*- coding: utf-8 -*-
"""用线上库重刷 600456 的离线兜底 seed（build/seed/report_600456.json）。

seed 的用途：file:// 打开（桌面副本双击）或云端不可用时，研报页拿它兜底。
格式必须与旧文件逐字节同构：indent=1、无末尾换行、charts 用**短 id**。

旧文件先备份到 build/backup/。
"""
import io
import json
import os
import shutil
import time
import urllib.request

B = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
CFG = json.load(io.open(os.path.join(B, 'build', 'cloud.json'), encoding='utf-8'))
BASE = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']
CODE = '600456'
SEED = os.path.join(B, 'build', 'seed', 'report_%s.json' % CODE)


def get(path):
    r = urllib.request.Request(BASE + path)
    r.add_header('Authorization', 'Bearer ' + CFG['key'])
    with urllib.request.urlopen(r, timeout=90) as f:
        return json.loads(f.read().decode('utf-8'))


# 旧文件现状（用于确认键集合与格式）
old = json.load(io.open(SEED, encoding='utf-8')) if os.path.exists(SEED) else None
old_raw = io.open(SEED, encoding='utf-8').read() if os.path.exists(SEED) else ''
print('旧 seed：%d 模块 / %d 图表 · %d 字节' % (
    len(old['mods']) if old else 0, len(old['charts']) if old else 0, len(old_raw)))
if old:
    print('  report 键序:', list(old['report'].keys()))
    print('  mods[0] 键序:', list(old['mods'][0].keys()))
    print('  charts[0] 键序:', list(old['charts'][0].keys()))
    print('  charts[0].id 样例:', old['charts'][0]['id'], '（应为短 id）')
    print('  末尾有换行:', old_raw.endswith('\n'))

# ---------------------------------------------------------------- 取线上
rep = get('wb_reports?id=eq.%s&select=*' % CODE)[0]
mods = get('wb_report_mods?report_id=eq.%s&select=*&order=seq.asc' % CODE)
charts = get('wb_report_charts?report_id=eq.%s&select=*&order=seq.asc' % CODE)

REP_KEYS = list(old['report'].keys()) if old else [
    'code', 'name', 'kicker', 'title', 'subtitle', 'badges', 'verdict_title',
    'verdict_html', 'kpis', 'kpi_note', 'toc', 'essence_html', 'footer_html', 'theme']

report = {}
for k in REP_KEYS:
    v = rep.get(k)
    if isinstance(v, str) and k in ('badges', 'kpis', 'toc'):
        try:
            v = json.loads(v)
        except Exception:
            pass
    report[k] = v

new_mods = [{'seq': m['seq'], 'no': m['no'], 'title': m['title'], 'html': m['html']} for m in mods]
new_charts = []
for c in charts:
    o = c['opt']
    if isinstance(o, str):
        o = json.loads(o)
    new_charts.append({'seq': c['seq'], 'id': c['id'].replace(CODE + '_', ''), 'name': c['name'], 'opt': o})

out = {'report': report, 'mods': new_mods, 'charts': new_charts}
txt = json.dumps(out, ensure_ascii=False, indent=1)
if old_raw and not old_raw.endswith('\n'):
    txt = txt.rstrip('\n')

# 格式自检：重解析回来必须一致
assert json.loads(txt) == out, 'seed 序列化自检失败'

# 备份旧文件
d = os.path.join(B, 'build', 'backup')
os.makedirs(d, exist_ok=True)
if os.path.exists(SEED):
    bp = os.path.join(d, 'seed_report_%s_pre_29mod_%s.json' % (CODE, time.strftime('%Y%m%d-%H%M%S')))
    shutil.copy2(SEED, bp)
    print('旧 seed 已备份 ->', os.path.basename(bp))

io.open(SEED, 'w', encoding='utf-8').write(txt)
print()
print('新 seed：%d 模块 / %d 图表 · %d 字节' % (len(new_mods), len(new_charts), len(txt.encode('utf-8'))))
print('  模块编号:', ','.join(str(m['no']) for m in new_mods))
print('  图表短 id:', ','.join(c['id'] for c in new_charts))
print('  toc 锚点:', [t['anchor'] for t in report['toc']])
