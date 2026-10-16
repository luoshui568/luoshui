#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 31 条商品日线序列写入云数据库 public.wb_data_series。

  python3 push_series.py            # 真实写入 + 回读核对
  python3 push_series.py --dry      # 只体检，不写库

数据源：build/commodity100/data/daily_data.json（页面内联的同一份数据）
入库口径：pts 存 [[dayNo, price]]，price 已由「分」还原为真实价格（源数据是整数分）。
写库姿势：PostgREST 直连 + Bearer 匿名可发布 key，不带 Origin（不受网关白名单限制）。
"""
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(io.open(os.path.join(HERE, '..', 'cloud.json'), encoding='utf-8'))
REST = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']
KEY = CFG['key']
BATCH = 4                                   # 每次 POST 几条序列（控制请求体体积）


def api(path, method='GET', body=None, prefer=None):
    h = {'Authorization': 'Bearer ' + KEY, 'apikey': KEY}
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode('utf-8')
        h['Content-Type'] = 'application/json'
    if prefer:
        h['Prefer'] = prefer
    req = urllib.request.Request(REST + path, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            txt = r.read().decode('utf-8')
            return r.status, (json.loads(txt) if txt.strip() else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'ignore')[:400]


def rows_from_seed():
    d = json.load(io.open(os.path.join(HERE, 'data', 'daily_data.json'), encoding='utf-8'))
    out = []
    for g in d['groups']:
        for s in g['series']:
            pts = [[int(p[0]), round(p[1] / 100.0, 4)] for p in s['d']]
            out.append({
                'id': s['c'], 'name': s['n'], 'market': s['m'], 'unit': s['u'],
                'cat': g['name'], 'color': s['col'],
                't0': pts[0][0], 't1': pts[-1][0], 'n': len(pts),
                'pts': pts, 'note': s.get('src', '') + ' · ' + s.get('sym', ''),
                't': d.get('built', '') or None,
            })
    return out


def main():
    dry = '--dry' in sys.argv
    rows = rows_from_seed()
    tot = sum(r['n'] for r in rows)
    print('待写入：%d 条序列 · %s 个数据点 · 体积约 %.2f MB'
          % (len(rows), format(tot, ','),
             len(json.dumps(rows, ensure_ascii=False).encode('utf-8')) / 1048576.0))
    for r in rows:
        print('  %-12s %-16s %6d 点  %s ~ %s' %
              (r['id'], r['name'], r['n'], r['t0'], r['t1']))
    if dry:
        print('\n--dry：未写库。')
        return 0

    ok = 0
    for i in range(0, len(rows), BATCH):
        chunk = rows[i:i + BATCH]
        st, resp = api('wb_data_series?on_conflict=id', 'POST', chunk,
                       'resolution=merge-duplicates,return=minimal')
        if st not in (200, 201, 204):
            print('  ✗ 第 %d 批失败 HTTP %s %s' % (i // BATCH + 1, st, resp))
            return 1
        ok += len(chunk)
        print('  ✓ 第 %d 批已写入 %d 条（累计 %d/%d）' % (i // BATCH + 1, len(chunk), ok, len(rows)))
        time.sleep(0.4)

    # ---------- 回读核对 ----------
    time.sleep(0.8)
    st, back = api('wb_data_series?select=id,name,cat,n,t0,t1,pts&order=id.asc')
    if st != 200:
        print('✗ 回读失败 HTTP %s %s' % (st, back))
        return 1
    src = {r['id']: r for r in rows}
    print('\n回读：库中 %d 条' % len(back))
    bad = []
    for b in back:
        s = src.get(b['id'])
        if not s:
            bad.append('%s 不在源数据里' % b['id']); continue
        if int(b['n']) != s['n'] or int(b['t0']) != s['t0'] or int(b['t1']) != s['t1']:
            bad.append('%s 元信息不一致：库 %s/%s/%s，源 %s/%s/%s'
                       % (b['id'], b['n'], b['t0'], b['t1'], s['n'], s['t0'], s['t1']))
            continue
        pts = b['pts']
        if isinstance(pts, str):
            pts = json.loads(pts)
        if len(pts) != s['n'] or abs(pts[0][1] - s['pts'][0][1]) > 1e-6 \
           or abs(pts[-1][1] - s['pts'][-1][1]) > 1e-6:
            bad.append('%s 点位不一致：库 %d 点，首末 %s/%s' % (b['id'], len(pts), pts[0], pts[-1]))
    miss = [i for i in src if i not in {b['id'] for b in back}]
    if miss:
        bad.append('缺失序列：' + ','.join(miss))
    if bad:
        print('✗ 核对发现 %d 个问题：' % len(bad))
        for x in bad:
            print('   - ' + x)
        return 1
    lib_tot = sum(int(b['n']) for b in back)
    print('✓ 逐条核对通过：%d 条序列 · %s 个数据点（源 %s）'
          % (len(back), format(lib_tot, ','), format(tot, ',')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
