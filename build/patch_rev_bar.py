# -*- coding: utf-8 -*-
"""研报「营业收入与净利润」图统一改成「左右双轴 + 双柱」。

背景（2026-10-14 用户口径，附 600392 截图）：
    「研报所有的营业收入与净利润都改成柱状图，都用左右两个坐标轴」。
    原来净利是叠在营收**同一根轴**上的金色折线 —— 量级差 ~10 倍（营收百亿级 / 净利个位数），
    折线被压在 x 轴上贴着地走，看不出高低。改为：左轴＝营业收入、右轴＝净利，两根都是柱。

本脚本只动 wb_report_charts.opt（以及可选地 build/seed/report_*.json），**不动页面**：
    · yAxis 至少 2 项：[0]=营业收入轴、[1]=净利轴
    · 名字含「净利」的系列：type→'bar'、yAxisIndex→1，去掉 smooth/lineStyle/symbol/areaStyle
    · 名字含「营业收入 / 营业总收入 / 营收」的系列：type→'bar'、yAxisIndex→0
    · 净利系列**只在营收系列带数据标签时**才补 label（没有就都不补 —— 尊重各图原有的疏密决策，
      21 年的老图补上 42 个标签会糊成一片）
    · grid.right ≥ 68（给右轴刻度留位）；轴名统一 左「营业收入（亿元）」右「归母净利（亿元）」
      （右轴挂多条净利系列时写「净利（亿元）」）

⚠️ 页面 report.html 的 beauty() 在渲染时会按系列色重绘柱色 / 轴色 / 标签色并自动隐藏重叠标签，
   所以这里只管**结构与数据**，颜色写了也会被接管（金色 #c9a227 系会被保留）。

用法：
    python3 patch_rev_bar.py                # 体检：打印每张图将发生什么，不写库
    python3 patch_rev_bar.py --go           # 备份 → 写库 → 回读逐张校验
    python3 patch_rev_bar.py --go --seed    # 同时改写 build/seed/report_*.json
"""
import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
SEED = os.path.join(HERE, 'seed')
BAK = os.path.join(HERE, 'backup')

CFG = json.load(io.open(os.path.join(HERE, 'cloud.json'), encoding='utf-8'))
REST = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']
HDR = {'Authorization': 'Bearer ' + CFG['key'], 'Content-Type': 'application/json',
       'Prefer': 'return=minimal'}

# 目标图：所有 *_chartRev ＋ 宝钛母本那张 chart1（不叫 chartRev 但语义相同）
TARGET_EXTRA = {'600456_chart1'}


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


def is_target(cid):
    return cid.endswith('_chartRev') or cid in TARGET_EXTRA


def _is_rev(n):
    return any(k in n for k in ('营业收入', '营业总收入', '营收'))


def _is_np(n):
    if '率' in n:                      # 「净利率」不是净利额，别误伤
        return False
    return ('净利' in n) or ('归母利润' in n)


def _as_opt(o):
    if isinstance(o, str):
        try:
            return json.loads(o)
        except ValueError:
            return None
    return o


def transform(opt):
    """返回 (新 opt, 说明字符串)；不是「营收 + 净利」结构的图返回 (None, 原因)。"""
    if not isinstance(opt, dict):
        return None, 'opt 不是对象'
    ser = opt.get('series') or []
    if not isinstance(ser, list):
        return None, 'series 不是数组'
    rev = [s for s in ser if isinstance(s, dict) and _is_rev(str(s.get('name') or ''))]
    nps = [s for s in ser if isinstance(s, dict) and _is_np(str(s.get('name') or ''))]
    if not rev or not nps:
        return None, '没有同时出现「营收」与「净利」系列'

    ya = opt.get('yAxis')
    if isinstance(ya, dict):
        ya = [dict(ya)]
    ya = [dict(a) for a in (ya or [])]
    while len(ya) < 2:
        ya.append({'type': 'value'})
    ya = ya[:2]
    ya[0]['type'] = 'value'
    ya[1]['type'] = 'value'
    ya[0]['name'] = '营业收入（亿元）'
    ya[1]['name'] = '归母净利（亿元）' if len(nps) == 1 else '净利（亿元）'
    opt['yAxis'] = ya

    grid = dict(opt.get('grid') or {})
    grid['left'] = max(int(grid.get('left') or 0), 64)
    grid['right'] = max(int(grid.get('right') or 0), 68)
    grid.setdefault('top', 30)
    grid.setdefault('bottom', 44)
    opt['grid'] = grid

    want_label = any((s.get('label') or {}).get('show') for s in rev)
    for s in nps:
        s['type'] = 'bar'
        s['yAxisIndex'] = 1
        for k in ('smooth', 'lineStyle', 'symbol', 'showSymbol', 'areaStyle', 'markLine', 'z'):
            s.pop(k, None)
        if want_label:
            lb = dict(s.get('label') or {})
            lb.update({'show': True, 'position': 'top', 'fontSize': 10, 'color': '#9a7d82'})
            s['label'] = lb
    for s in rev:
        s['type'] = 'bar'
        s['yAxisIndex'] = 0
        for k in ('smooth', 'lineStyle', 'symbol', 'showSymbol', 'areaStyle'):
            s.pop(k, None)

    note = '营收轴 0（%d 条）· 净利轴 1（%d 条：%s）· 标签%s' % (
        len(rev), len(nps), '/'.join(str(s.get('name')) for s in nps),
        '补' if want_label else '不补（原图也没标签）')
    return opt, note


def main():
    a = sys.argv[1:]
    go = '--go' in a
    to_seed = '--seed' in a
    ts = time.strftime('%Y%m%d-%H%M%S')
    now = int(time.time() * 1000)

    st, rows = req('wb_report_charts?select=id,name,opt&order=id.asc')
    if st != 200 or not isinstance(rows, list):
        print('!! 拉取失败 %s %s' % (st, rows))
        return 1

    targets, skip = [], []
    for x in rows:
        cid = x['id']
        if not is_target(cid):
            continue
        opt = _as_opt(x['opt'])
        new, note = transform(json.loads(json.dumps(opt)) if isinstance(opt, dict) else opt)
        if new is None:
            skip.append((cid, note))
            continue
        targets.append((cid, x['name'], opt, new, note))

    print('『营收 / 净利』目标图 %d 张（另有 %d 张结构不符被跳过）\n' % (len(targets), len(skip)))
    for cid, name, old, new, note in targets:
        oldt = ','.join(str(s.get('type')) for s in (old.get('series') or []))
        newt = ','.join(str(s.get('type')) for s in (new.get('series') or []))
        print('  %-22s %-14s 系列 %s → %s' % (cid, name, oldt, newt))
        print('  %-22s %s' % ('', note))
    for cid, why in skip:
        print('  -- %-19s 跳过：%s' % (cid, why))

    if not go:
        print('\n[dry] 未写库。加 --go 执行（会先备份到 build/backup/）。')
        return 0

    os.makedirs(BAK, exist_ok=True)
    bk = os.path.join(BAK, 'rev_bar_%s.json' % ts)
    io.open(bk, 'w', encoding='utf-8').write(json.dumps(
        {'ts': ts, 'rows': [{'id': c, 'name': n, 'opt': o} for c, n, o, _, _ in targets]},
        ensure_ascii=False, indent=1))
    print('\n已备份 → %s' % os.path.relpath(bk, os.path.dirname(HERE)))

    ok = 0
    for cid, name, old, new, note in targets:
        st, r = req('wb_report_charts?id=eq.%s' % urllib.parse.quote(cid), 'PATCH',
                    {'opt': new, 'up': now})
        flag = '✓' if st in (200, 204) else 'X'
        if st in (200, 204):
            ok += 1
        print('  %s PATCH %-22s %s %s' % (flag, cid, st, '' if st in (200, 204) else r))
    print('\n写库 %d/%d' % (ok, len(targets)))

    # ---- 回读校验 ----
    print('\n回读校验：')
    bad = 0
    for cid, name, old, new, note in targets:
        st, r = req('wb_report_charts?id=eq.%s&select=opt' % urllib.parse.quote(cid))
        cur = _as_opt(r[0]['opt']) if (st == 200 and isinstance(r, list) and r) else None
        if cur is None:
            print('  X %s 读不到' % cid)
            bad += 1
            continue
        ya = cur.get('yAxis')
        naxis = len(ya) if isinstance(ya, list) else 1
        ser = cur.get('series') or []
        barok = all(str(s.get('type')) == 'bar' for s in ser)
        rootok = all(int(s.get('yAxisIndex') or 0) == (0 if _is_rev(str(s.get('name'))) else 1)
                     for s in ser)
        same = json.dumps(cur, ensure_ascii=False, sort_keys=True) == \
            json.dumps(new, ensure_ascii=False, sort_keys=True)
        good = (naxis == 2 and barok and rootok and same)
        if not good:
            bad += 1
        print('  %s %-22s 轴 %d · 全柱 %s · 轴位对 %s · 逐字节一致 %s'
              % ('✓' if good else 'X', cid, naxis, barok, rootok, same))
    print('\n回读不合格 %d 张' % bad)

    # ---- 可选：同步 seed ----
    # ⚠️ seed 里的图表 id 是**裸键**（`chartRev` / `chart1`），不带 `<code>_` 前缀，
    #    所以不能复用 is_target() —— 否则一个都匹配不上（而 push_reports_v31.py 是从
    #    seed 推库的，seed 不同步 = 下次推库把线上刚改好的双轴柱又刷回折线）。
    if to_seed:
        print('\n同步 seed/report_*.json：')
        for fn in sorted(os.listdir(SEED)):
            if not (fn.startswith('report_') and fn.endswith('.json')):
                continue
            p = os.path.join(SEED, fn)
            d = json.load(io.open(p, encoding='utf-8'))
            chs = d.get('charts')
            if not isinstance(chs, list):
                continue
            rcode = str((d.get('report') or {}).get('code') or
                        fn[len('report_'):-len('.json')])
            touched = []
            for c in chs:
                cid = str(c.get('id') or '')
                if not (cid == 'chartRev' or (rcode == '600456' and cid == 'chart1')):
                    continue
                new, note2 = transform(_as_opt(c.get('opt')))
                if new is None:
                    continue
                c['opt'] = new
                touched.append('%s(%s)' % (cid, note2.split('·')[0].strip()))
            if touched:
                io.open(p, 'w', encoding='utf-8').write(
                    json.dumps(d, ensure_ascii=False, separators=(',', ':')))
                print('  ✓ %-22s %s' % (fn, ' '.join(touched)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
