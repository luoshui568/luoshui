#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全库研报体检 —— 一次跑出所有「会出事的隐患」。

用法：
    python3 audit_reports.py              # 全部 13 份
    python3 audit_reports.py 000731       # 只查一份
    python3 audit_reports.py --brief      # 只打问题行

检查维度（每条都对应一次实踩事故）：
  ① seed ↔ 库 模块逐字节一致      ← 不同步 ⇒ 下次 push 会把线上刷回旧版
  ② seed ↔ 库 图表集合 / opt 一致  ← 同上
  ③ data_v31_*.json 顶层键数       ← < 30 ⇒ 不能重跑 build（会抹掉若干模块的表与图）
  ④ 全空 series                    ← 有图无数据（画出来空白，不报错）
  ⑤ [MISSING] 数                   ← 数据缺口
  ⑥ 槽位 ↔ 图 双向对账             ← 孤儿图（有图无槽）/ 空槽（有槽无图）
  ⑦ 结构要件：m25 地图 / m11 双环 / m29 EPS / m3 sh3-top / m22 iflow
  ⑧ `**` 字面量残留                ← 漏跑 _norm_bold
"""
import io, json, os, re, sys, glob, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = os.path.join(HERE, 'seed')

cfg = json.load(io.open(os.path.join(HERE, 'cloud.json'), encoding='utf-8'))
REST = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % cfg['envId']
HDR = {'Authorization': 'Bearer ' + cfg['key']}


def q(path):
    req = urllib.request.Request(REST + path, headers=HDR)
    return json.loads(urllib.request.urlopen(req, timeout=180).read().decode('utf-8', 'replace'))


def codes(only=None):
    """现行 seed = report_<code>.json；v23 归档件（_v23.json）必须排除，
       否则同一 code 会出现两次、且报出一堆假隐患（push_reports_v31.all_codes 同款）。"""
    out = []
    for f in sorted(glob.glob(os.path.join(SEED, 'report_*.json'))):
        if f.endswith('_v23.json'):
            continue
        c = os.path.basename(f)[7:13]
        if c.isdigit():
            out.append(c)
    out = sorted(set(out))
    return [c for c in out if not only or c in only]


def norm_bold(s):
    """模拟 _norm_bold：成对 ** 转 <b>、再删碎片。
       用它区分「只是没跑 _norm_bold」与「内容真的不同」——两者修法完全不同。"""
    s = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', s or '', flags=re.S)
    return s.replace('**', '')


def slots_of(mods):
    """{chart_key: [mod_no, ...]}"""
    out = {}
    for m in mods:
        for k in re.findall(r'data-chart="([^"]+)"', m.get('html') or ''):
            out.setdefault(k, []).append(int(m['no']))
    return out


def empties(charts):
    """全空 series 清单 [(chart_id, series_name, n)]"""
    bad = []
    for c in charts:
        for s in (c['opt'].get('series') or []):
            if not isinstance(s, dict):
                continue
            d = s.get('data') or []
            if d and all(v is None for v in d):
                bad.append((c['id'], s.get('name') or '?', len(d)))
    return bad


def audit(code, verbose=True):
    P = []
    note = []

    sp = os.path.join(SEED, 'report_%s.json' % code)
    dp = os.path.join(SEED, 'data_v31_%s.json' % code)
    seed = json.load(io.open(sp, encoding='utf-8')) if os.path.exists(sp) else None
    data = json.load(io.open(dp, encoding='utf-8')) if os.path.exists(dp) else None

    lmods = q('wb_report_mods?report_id=eq.%s&select=no,title,html' % code)
    lchs = q('wb_report_charts?report_id=eq.%s&select=id,name,opt' % code)

    if seed is None:
        return ['%s  ✗ 无 seed/report_*.json' % code], {}

    # ① 模块逐字节 —— 关键：区分「只是没跑 _norm_bold」与「内容真的不同」
    sm = {int(m['no']): (m['html'] or '') for m in seed['mods']}
    lm = {int(m['no']): (m['html'] or '') for m in lmods}
    diffs = [n for n in sorted(set(sm) | set(lm)) if sm.get(n) != lm.get(n)]
    only_bold = [n for n in diffs if norm_bold(sm.get(n)) == lm.get(n)]
    real = [n for n in diffs if n not in only_bold]
    if real:
        P.append('① seed↔库 内容真不同 %d 个：m%s ⇒ **库更新，一 push 就退化**'
                 % (len(real), ','.join(str(x) for x in real[:14])))
    if only_bold:
        P.append('① seed 未跑 _norm_bold %d 个：m%s'
                 % (len(only_bold), ','.join(str(x) for x in only_bold[:14])))
    if len(sm) != 31:
        P.append('① seed 模块数 %d（应 31）' % len(sm))

    # ② 图表集合 / opt
    sc = {c['id']: c['opt'] for c in seed['charts']}
    lc = {c['id'].replace(code + '_', ''): c['opt'] for c in lchs}
    only_s = sorted(set(sc) - set(lc))
    only_l = sorted(set(lc) - set(sc))
    if only_s:
        P.append('② seed 有·库无 %d 张：%s' % (len(only_s), ', '.join(only_s)))
    if only_l:
        note.append('② 库有·seed 无 %d 张（孤儿行，不显示）：%s' % (len(only_l), ', '.join(only_l)))
    optbad = [k for k in sorted(set(sc) & set(lc))
              if json.dumps(sc[k], sort_keys=True) != json.dumps(lc[k], sort_keys=True)]
    if optbad:
        P.append('② opt 不一致 %d 张：%s' % (len(optbad), ', '.join(optbad)))

    # ③ data 顶层键
    if data is None:
        P.append('③ 无 seed/data_v31_%s.json ⇒ 绝不能重跑 build' % code)
    else:
        nk = len(data)
        if nk < 30:
            miss = sorted(set(['valuation', 'capacity', 'production', 'pricecost', 'expense',
                               'sdbalance', 'bizmix', 'resource', 'fin', 'industry_note']) - set(data))
            P.append('③ data 顶层键仅 %d（应 ≥30）缺：%s ⇒ 不能重跑 build' % (nk, ', '.join(miss) or '—'))

    # ④ 全空 series
    eb = empties(seed['charts'])
    if eb:
        note.append('④ 全空 series %d 条：%s' % (len(eb), ', '.join('%s/%s' % (a, b) for a, b, _ in eb[:6])))

    # ⑤ MISSING
    ms = sum((m['html'] or '').count('[MISSING]') for m in seed['mods'])
    if ms:
        where = ['m%d×%d' % (int(m['no']), (m['html'] or '').count('[MISSING]'))
                 for m in seed['mods'] if '[MISSING]' in (m['html'] or '')]
        note.append('⑤ MISSING %d 处（%s）' % (ms, ' '.join(where)))

    # ⑥ 槽位 ↔ 图
    sl = slots_of(seed['mods'])
    ids = {c['id'] for c in seed['charts']}
    orphan = sorted(ids - set(sl))
    noslot = sorted(set(sl) - ids)
    if orphan:
        note.append('⑥ 孤儿图 %d 张（有图无槽·不显示）：%s' % (len(orphan), ', '.join(orphan)))
    if noslot:
        P.append('⑥ 空槽 %d 个（有槽无图·页面出灰框）：%s' % (len(noslot), ', '.join(noslot)))

    # ⑦ 结构要件 —— 分清「seed 缺但库里有」（sync 即解）与「两边都缺」（真·内容缺口）
    hs = {int(m['no']): (m['html'] or '') for m in seed['mods']}
    hl = {int(m['no']): (m['html'] or '') for m in lmods}
    sl_l = slots_of(lmods)
    for name, fn in [
        ('m3 sh3-top（股东结构树）', lambda H, S: 'sh3-top' in H.get(3, '')),
        ('m22 iflow（产业链流程图）', lambda H, S: 'iflow' in H.get(22, '')),
        ('m29 EPS 槽位（chart_eps）', lambda H, S: 'chart_eps' in S),
    ]:
        if not fn(hs, sl):
            if fn(hl, sl_l):
                P.append('⑦ seed 缺 %s（库里已有 ⇒ sync 即解）' % name)
            else:
                note.append('⑦ 两边都缺 %s —— 真·内容缺口' % name)

    # 双环：在**图表 opt** 里（两个 pie series），不在模块 html 里 —— sh3-donut 只是壳里的 CSS
    def npie(chs):
        for c in chs:
            k = c['id'][len(code) + 1:] if c['id'].startswith(code + '_') else c['id']
            if k == 'chartMix':
                return sum(1 for s in (c['opt'].get('series') or [])
                           if isinstance(s, dict) and s.get('type') == 'pie')
        return None
    ps, pl = npie(seed['charts']), npie(lchs)
    if ps is None:
        note.append('⑦ seed 无 chartMix（另一套图形体系）')
    elif pl is None or pl < 2:
        note.append('⑦ chartMix 非双环（seed %d 环 / 库 %s）—— 真·内容缺口'
                    % (ps, pl if pl is not None else '无'))
    elif ps < 2:
        P.append('⑦ seed 的 chartMix 非双环（seed %d / 库 %d ⇒ sync 即解）' % (ps, pl))

    n_maps = lambda H: len(re.findall(r'data-chart="([^"]*(?:Map|map)[^"]*)"', H.get(25, '')))
    if n_maps(hl) < 2:
        note.append('⑦ m25 地图 %d 张（应 2）—— 真·内容缺口' % n_maps(hl))
    elif n_maps(hs) < 2:
        P.append('⑦ seed 缺 m25 地图（库里已有 %d 张 ⇒ sync 即解）' % n_maps(hl))
    if 'score-hero' not in hs.get(29, ''):
        note.append('⑦ m29 无评分环（未评分 ⇒ 待评分灰环，属正常态）')

    # ⑧ `**` 字面量残留 —— seed 侧的会随 sync 一起消掉；库侧的才是线上真问题
    star = sum((m['html'] or '').count('**') for m in seed['mods'])
    lstar = sum((m['html'] or '').count('**') for m in lmods)
    if lstar:
        P.append('⑧ 库里 `**` 字面量 %d 处 ⇒ 线上会显示成星号' % lstar)
    elif star:
        note.append('⑧ seed 里 `**` %d 处（库已转 <b> ⇒ sync 即解）' % star)

    if verbose:
        print('%-8s 模块 %2d/31 ｜ 图 %2d（库 %2d）｜ data %2s 键' % (
            code, len(sm), len(seed['charts']), len(lchs),
            len(data) if data is not None else '—'))
        for x in P:
            print('        ✗ %s' % x)
        for x in note:
            print('        · %s' % x)
        if not P and not note:
            print('        ✓ 无隐患')
    return P, {'note': note, 'charts': len(seed['charts']), 'mods': len(sm)}


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith('--')]
    brief = '--brief' in sys.argv
    cs = codes(set(argv) if argv else None)
    print('=' * 78)
    print('全库体检：%d 份' % len(cs))
    print('=' * 78)
    hard = {}
    for c in cs:
        P, _ = audit(c, verbose=not brief)
        if P:
            hard[c] = P
    print()
    print('=' * 78)
    if hard:
        print('★ 硬隐患 %d 份：' % len(hard))
        for c, P in hard.items():
            print('  %s：%d 条' % (c, len(P)))
            for x in P:
                print('     - %s' % x)
    else:
        print('★ 硬隐患 0 份 ✓')
    print('=' * 78)


if __name__ == '__main__':
    main()
