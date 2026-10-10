# -*- coding: utf-8 -*-
"""把 600456 研报的「模块 3 股东结构（新版）」写进线上库。

为什么不用 push_reports_v31.py：那个脚本会整份 upsert 31 个模块 + 23 张图表，
若线上有网页编辑器做过的改动、而本地 seed 落后，会被静默覆盖。
这里只动一行：wb_report_mods(id=600456_m3)。

用法：
    python push_mod3_bstn.py            # 体检 + 对比线上现状，不写库
    python push_mod3_bstn.py --go       # 备份 + 写库 + 回读核对
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
V23 = os.path.join(BASE, 'seed', 'report_600456_v23.json')
BAK = os.path.join(BASE, 'backup')

CFG = json.load(io.open(os.path.join(BASE, 'cloud.json'), encoding='utf-8'))
REST = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']
HDR = {'Authorization': 'Bearer ' + CFG['key'], 'Content-Type': 'application/json',
       'Prefer': 'resolution=merge-duplicates,return=minimal'}

RID = '600456'
MODID = '%s_m3' % RID


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
    m3new = [m for m in seed['mods'] if str(m['no']) == '3'][0]['html']

    print('=== 1) 读线上现状 ===')
    st, live = req('wb_report_mods?id=eq.%s&select=id,no,title,html,up' % MODID)
    assert st == 200, '读模块失败 %s %s' % (st, live)
    assert isinstance(live, list) and len(live) == 1, '模块行数异常：%s' % (
        len(live) if isinstance(live, list) else live)
    live_html = live[0]['html']
    print('线上模块 3《%s》%d 字符  up=%s' % (live[0]['title'], len(live_html), live[0].get('up')))

    # 漂移检测：线上应与「改动前快照」一致；不一致说明线上被网页端编辑过
    v23 = json.load(io.open(V23, encoding='utf-8'))
    ref = [m for m in v23['mods'] if str(m['no']) == '3'][0]['html']
    drift = (live_html != ref)
    print('线上 m3 与改动前快照一致：%s%s'
          % (not drift, '  ← ⚠ 线上有额外改动，需人工确认！' if drift else ''))
    if drift and '--force' not in sys.argv:
        print('\n[中止] 线上模块 3 与本地快照不符，拒绝覆盖。确认无误后加 --force。')
        return

    print('\n=== 2) 待写入内容 ===')
    print('模块 3 新正文 %d 字符（旧 %d，+%d）' % (len(m3new), len(live_html), len(m3new) - len(live_html)))
    for k, v in [('新树 1000x550', 'viewBox="0 0 1000 550"' in m3new),
                 ('环形图 sh3-donut', 'sh3-donut' in m3new),
                 ('股权树 sh3-tree', 'sh3-tree' in m3new),
                 ('logo 内联 base64', 'data:image/png;base64' in m3new)]:
        print('    %-18s %s' % (k, v))
    print('已写入 31 模块之 3 / 图表 %d 张不动' % len(seed['charts']))

    if not go:
        print('\n[dry-run] 未写库。加 --go 执行。')
        return

    ts = time.strftime('%Y%m%d-%H%M%S')
    os.makedirs(BAK, exist_ok=True)
    bp = os.path.join(BAK, 'mod3_%s_pre_redesign_%s.json' % (RID, ts))
    io.open(bp, 'w', encoding='utf-8').write(json.dumps(
        {'ts': ts, 'rid': RID, 'mod': live}, ensure_ascii=False))
    print('\n=== 3) 备份线上现状 → %s ===' % os.path.basename(bp))

    now = int(time.time() * 1000)
    print('=== 4) 写库 ===')
    st, r = req('wb_report_mods?id=eq.%s' % MODID, 'PATCH', {'html': m3new, 'up': now})
    print('  PATCH 模块 3：%s %s' % (st, '' if st < 400 else r))
    assert st < 400, '模块写入失败'

    print('=== 5) 回读核对 ===')
    st, rb = req('wb_report_mods?id=eq.%s&select=html' % MODID)
    ok_html = (st == 200 and rb[0]['html'] == m3new)
    print('  模块 3 正文逐字节一致：%s' % ok_html)
    st, cnt = req('wb_report_mods?report_id=eq.%s&select=id' % RID)
    print('  600456 模块总数：%d（应为 31）%s' % (len(cnt), '✓' if len(cnt) == 31 else '⚠'))
    st, mm = req('wb_report_mods?id=eq.600456_m8&select=html')
    print('  模块 8（另一会话的 chartBSTN 版）未被波及：%s' % ('chartBSTN' in mm[0]['html']))
    print('\n%s' % ('全部通过 ✓' if ok_html and len(cnt) == 31 else '⚠ 存在未通过项'))


if __name__ == '__main__':
    main()
