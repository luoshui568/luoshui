# -*- coding: utf-8 -*-
"""只把 600456 研报的「模块 8 正文」和「新增图表 chartBSTN」写进线上库。

为什么不用 push_reports_v31.py：那个脚本会整份 upsert 31 个模块 + 23 张图表，
如果线上有通过网页编辑器做过的改动、而本地 seed 落后，就会被静默覆盖。
这里只动两行：wb_report_mods(id=600456_m8) 和 wb_report_charts(id=600456_chartBSTN)。

用法：
    python push_mod8_bstn.py            # 只体检 + 对比线上现状，不写库
    python push_mod8_bstn.py --go       # 备份 + 写库 + 回读核对
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

CFG = json.load(io.open(os.path.join(BASE, 'cloud.json'), encoding='utf-8'))
REST = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']
HDR = {'Authorization': 'Bearer ' + CFG['key'], 'Content-Type': 'application/json',
       'Prefer': 'resolution=merge-duplicates,return=minimal'}

RID = '600456'
MODID = '%s_m8' % RID
CHARTID = '%s_chartBSTN' % RID


def req(path, method='GET', body=None, headers=None, timeout=120):
    h = dict(HDR)
    if headers:
        h.update(headers)
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
    r = urllib.request.Request(REST + path, data=data, headers=h, method=method)
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
    mod8 = [m for m in seed['mods'] if str(m['no']) == '8'][0]
    chart = [c for c in seed['charts'] if c['id'] == 'chartBSTN'][0]

    print('=== 1) 读线上现状 ===')
    st, live = req('wb_report_mods?id=eq.%s&select=id,no,title,html' % MODID)
    assert st == 200, '读模块失败 %s %s' % (st, live)
    assert isinstance(live, list) and len(live) == 1, '模块行数异常：%s' % (
        len(live) if isinstance(live, list) else live)
    live_html = live[0]['html']
    print('线上模块 8 正文 %d 字符' % len(live_html))

    st, lc = req('wb_report_charts?report_id=eq.%s&select=id&order=seq.asc' % RID)
    assert st == 200, '读图表失败 %s %s' % (st, lc)
    live_ids = [x['id'] for x in lc]
    print('线上图表 %d 张，含 chartBSTN：%s' % (len(live_ids), CHARTID in live_ids))

    # 与本地「改动前」快照对比，判断线上有没有被网页端改过（防止覆盖别人/自己的在线改动）
    before = io.open(os.path.join(BAK, 'seed_report_600456_pre_bstnchart.json'), encoding='utf-8').read()
    before_html = [m for m in json.loads(before)['mods'] if str(m['no']) == '8'][0]['html']
    drift = (live_html != before_html)
    print('线上模块 8 与本地改动前快照一致：%s%s'
          % (not drift, '  ← ⚠ 线上有额外改动，请先确认！' if drift else ''))

    print('\n=== 2) 待写入内容 ===')
    print('模块 8 新正文 %d 字符（旧 %d）' % (len(mod8['html']), len(before_html)))
    print('新增图表：%s · %s · seq=%d' % (chart['id'], chart['name'], chart['seq']))
    print('  系列：%s' % ' / '.join('%s(%s)' % (s['name'], s['type']) for s in chart['opt']['series']))

    if not go:
        print('\n[dry-run] 未写库。加 --go 执行。')
        return

    ts = time.strftime('%Y%m%d-%H%M%S')
    os.makedirs(BAK, exist_ok=True)
    bp = os.path.join(BAK, 'mod8_600456_pre_bstnchart_%s.json' % ts)
    io.open(bp, 'w', encoding='utf-8').write(json.dumps(
        {'ts': ts, 'mod': live, 'chart_ids': live_ids}, ensure_ascii=False))
    print('\n=== 3) 备份线上现状 → %s ===' % os.path.basename(bp))

    now = int(time.time() * 1000)
    print('=== 4) 写库 ===')
    st, r = req('wb_report_mods?id=eq.%s' % MODID, 'PATCH', {'html': mod8['html'], 'up': now})
    print('  PATCH 模块 8：%s %s' % (st, '' if st < 400 else r))
    assert st < 400, '模块写入失败'

    st, r = req('wb_report_charts?on_conflict=id', 'POST', [{
        'id': CHARTID, 'report_id': RID, 'code': RID, 'seq': chart['seq'],
        'name': chart['name'], 'opt': chart['opt'], 'up': now}])
    print('  POST 图表：%s %s' % (st, '' if st < 400 else r))
    assert st < 400, '图表写入失败'

    print('=== 5) 回读核对 ===')
    st, rb = req('wb_report_mods?id=eq.%s&select=html' % MODID)
    ok_html = (st == 200 and rb[0]['html'] == mod8['html'])
    print('  模块 8 正文逐字节一致：%s' % ok_html)
    st, rc = req('wb_report_charts?id=eq.%s&select=id,name,opt' % CHARTID)
    ok_chart = (st == 200 and len(rc) == 1 and rc[0]['opt'] == chart['opt'])
    print('  图表存在且 opt 一致：%s' % ok_chart)
    st, rc2 = req('wb_report_charts?report_id=eq.%s&select=id&order=seq.asc' % RID)
    print('  线上图表总数：%d（写入前 %d）' % (len(rc2), len(live_ids)))
    print('\n%s' % ('全部通过 ✓' if (ok_html and ok_chart and len(rc2) == len(live_ids) + 1) else '⚠ 存在未通过项'))


if __name__ == '__main__':
    main()
