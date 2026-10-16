# -*- coding: utf-8 -*-
"""把 31 模块的研报 seed 推送到线上库（wb_reports / wb_report_mods / wb_report_charts）。

⚠️ 这是**写线上数据**的操作。流程：
     1) 先把线上现有 5 份研报整份导出到 build/backup/report_<code>_pre_v31_<ts>.json
     2) 再逐份 upsert（on_conflict=id → merge-duplicates）
     3) 回读核对：模块编号必须 1..31 连续、图表 id 集合与 seed 一致

用法：
    python push_reports_v31.py --all              # 备份 + 推送全部 5 份
    python push_reports_v31.py 600456             # 只推一份
    python push_reports_v31.py --all --dry        # 只备份与体检，不写库
"""
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
SEED = os.path.join(HERE, 'seed')
BAK = os.path.join(HERE, 'backup')

CFG = json.load(io.open(os.path.join(HERE, 'cloud.json'), encoding='utf-8'))
REST = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']
HDR = {'Authorization': 'Bearer ' + CFG['key'], 'Content-Type': 'application/json',
       'Prefer': 'resolution=merge-duplicates,return=minimal'}


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


def chunk(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def backup(codes, ts):
    os.makedirs(BAK, exist_ok=True)
    ok = True
    for code in codes:
        pack = {'ts': ts, 'code': code}
        for tbl, q in [('wb_reports', 'id=eq.%s' % code),
                       ('wb_report_mods', 'report_id=eq.%s&order=seq.asc' % code),
                       ('wb_report_charts', 'report_id=eq.%s&order=seq.asc' % code)]:
            st, r = req('%s?%s' % (tbl, q))
            if st != 200:
                print('  !! 备份 %s 失败 %s %s' % (tbl, st, r))
                ok = False
                continue
            pack[tbl] = r
        p = os.path.join(BAK, 'report_%s_pre_v31_%s.json' % (code, ts))
        io.open(p, 'w', encoding='utf-8').write(json.dumps(pack, ensure_ascii=False))
        print('  备份 %s：mods %d · charts %d → %s'
              % (code, len(pack.get('wb_report_mods') or []),
                 len(pack.get('wb_report_charts') or []), os.path.basename(p)))
    return ok


def push_one(code, dry=False):
    seed = json.load(io.open(os.path.join(SEED, 'report_%s.json' % code), encoding='utf-8'))
    rep = seed['report']
    rid = rep['code']
    now = int(time.time() * 1000)
    row = {'id': rid, 'code': rep['code'], 'name': rep['name'], 'kicker': rep['kicker'],
           'title': rep['title'], 'subtitle': rep['subtitle'], 'badges': rep['badges'],
           'verdict_title': rep['verdict_title'], 'verdict_html': rep['verdict_html'],
           'notice_html': rep.get('notice_html', ''),
           'kpis': rep['kpis'], 'kpi_note': rep['kpi_note'], 'toc': rep['toc'],
           'essence_html': rep['essence_html'], 'footer_html': rep.get('footer_html', ''),
           'theme': rep.get('theme', 'red'), 'sort': 1, 'up': now}
    mods = [{'id': '%s_m%s' % (rid, m['no']), 'report_id': rid, 'code': rid,
             'seq': m['seq'], 'no': str(m['no']), 'title': m['title'], 'html': m['html'], 'up': now}
            for m in seed['mods']]
    charts = [{'id': '%s_%s' % (rid, c['id']), 'report_id': rid, 'code': rid,
               'seq': c['seq'], 'name': c['name'], 'opt': c['opt'], 'up': now}
              for c in seed['charts']]
    if dry:
        print('  [dry] %s：壳 1 · 模块 %d · 图表 %d' % (code, len(mods), len(charts)))
        return True

    st, r = req('wb_reports?on_conflict=id', 'POST', [row])
    if st >= 400:
        print('  !! wb_reports %s %s' % (st, r))
        return False
    nm = 0
    for part in chunk(mods, 6):
        st, r = req('wb_report_mods?on_conflict=id', 'POST', part)
        if st < 400:
            nm += len(part)
        else:
            print('  !! 模块批次 %s %s' % (st, r))
    nc = 0
    for part in chunk(charts, 4):
        st, r = req('wb_report_charts?on_conflict=id', 'POST', part)
        if st < 400:
            nc += len(part)
        else:
            print('  !! 图表批次 %s %s' % (st, r))

    # ---- 回读核对 ----
    st, r = req('wb_report_mods?report_id=eq.%s&select=no,title&order=seq.asc' % rid)
    got = [x['no'] for x in r] if isinstance(r, list) else []
    want = [str(i) for i in range(1, 32)]
    cont = (got == want)
    st2, r2 = req('wb_report_charts?report_id=eq.%s&select=id&order=seq.asc' % rid)
    gotc = sorted(x['id'] for x in r2) if isinstance(r2, list) else []
    wantc = sorted('%s_%s' % (rid, c['id']) for c in seed['charts'])
    flag = '✓' if (cont and gotc == wantc and nm == len(mods) and nc == len(charts)) else '⚠'
    print('  %s %s  模块 %d/%d（编号连续：%s）· 图表 %d/%d（集合一致：%s）'
          % (flag, code, nm, len(mods), '是' if cont else '否 %s' % got[:6],
             nc, len(charts), '是' if gotc == wantc else '否'))
    return flag == '✓'


def all_codes():
    """现行 seed = seed/report_<code>.json（v23 归档件以 _v23.json 结尾，排除）。"""
    return sorted({f[len('report_'):-len('.json')] for f in os.listdir(SEED)
                   if f.startswith('report_') and f.endswith('.json')
                   and not f.endswith('_v23.json')})


def stale_check(code, seed):
    """★ 2026-10-16：push 前体检 —— 判断 seed 是否**落后于线上库**。

    背景：`apply_eps_to_11` / `mkmod3_std` / `mkchain_std` / `mkmod11_ring` / `_norm_bold`
    这类脚本**只写库、从不写 seed**。跑完若不 `sync_seed_full`，seed 就停在改造之前；
    此后**任何一次 push 都会拿这份旧 seed 把线上的成果整份盖掉**（不报错、终端全 ✓）。
    2026-10-16 实测：13 份里 9 份都处于这个状态，其中 000731 一度只差一次 push 就退化成 12 图。

    判据（命中任一即判落后；三条都是「库里有新东西、seed 里没有」的确定性特征）：
      ① seed 的 `**` 字面量 > 0 而库为 0   → 库跑过 _norm_bold，seed 没跑
      ② 库里某模块有 sh3-top / iflow，seed 全都没有 → seed 停在 m3 / m22 改造前
      ③ 库里有 chart_eps 图表行而 seed 没有        → seed 停在 m29 改造前

    返回 (是否落后, 原因列表)
    """
    st, lmods = req('wb_report_mods?report_id=eq.%s&select=no,html' % code)
    st2, lcharts = req('wb_report_charts?report_id=eq.%s&select=id' % code)
    if not isinstance(lmods, list) or not lmods:
        return False, []                      # 库里还没有 → 首次推送，无退化风险
    sm = {int(m['no']): (m['html'] or '') for m in seed['mods']}
    lm = {int(m['no']): (m['html'] or '') for m in lmods}
    why = []
    # ★ 只把「库里有、seed 里完全没有」的**结构改造特征**当阻断依据。
    #   这两项在正常链路（build → m3 → chain → push）里**不会误报**，
    #   因为 mkmod3 / mkchain 都跑在 push 之前，seed 里自然带着它们。
    for key, name in [('sh3-top', 'm3 股东结构树'), ('iflow', 'm22 产业链流程图')]:
        if any(key in v for v in lm.values()) and not any(key in v for v in sm.values()):
            why.append('库里有 %s，seed 里完全没有' % name)
    # ⚠️ 下面两条**不作阻断依据**（只报事实，交给调用方判断）：
    #   `**` —— 「重跑 build 后推送」时必然出现：build 产出的是 `**`，而库里已被
    #          _norm_bold 转成 <b>，于是「seed 有、库为 0」是**正常状态**；
    #   chart_eps —— 链路里 apply_eps_to_11 本就跑在 push **之后**。
    #   当作提示保留，避免「狼来了」把真正的拦截信号淹没。
    s_star = sum(v.count('**') for v in sm.values())
    l_star = sum(v.count('**') for v in lm.values())
    if l_star == 0 and s_star > 0:
        why.append('（提示）seed 有 `**` %d 处、库为 0 —— 推送后记得跑 _norm_bold' % s_star)
    lids = {c['id'] for c in lcharts} if isinstance(lcharts, list) else set()
    sids = {'%s_%s' % (code, c['id']) for c in seed['charts']}
    if ('%s_chart_eps' % code) in lids and ('%s_chart_eps' % code) not in sids:
        why.append('（提示）库有 chart_eps 而 seed 没有 —— 推送后记得重跑 apply_eps_to_11')
    return (any(not w.startswith('（提示）') for w in why)), why


def main():
    args = sys.argv[1:]
    dry = '--dry' in args
    force = '--force' in args
    ts = time.strftime('%Y%m%d-%H%M%S')
    if '--all' in args:
        codes = all_codes()
    elif '--batch' in args:
        # 只推第 1 批 30 家（_todo_96.json 的 0..N 切片），不动已升级的 5 份存量研报
        i = args.index('--batch')
        todo = json.load(io.open(os.path.join(SEED, '_todo_96.json'), encoding='utf-8'))['todo']
        codes = [m['code'] for m in todo[int(args[i + 1]):int(args[i + 2])]]
    else:
        codes = [a for a in args if not a.startswith('--')]
    print('=== 待推送 %d 份：%s ... %s ===' % (len(codes), codes[0], codes[-1]))
    print('=== 1) 备份线上现状 ===')
    backup(codes, ts)

    # ★ 1.5) seed 落后体检 —— 拦住「拿旧 seed 覆盖线上新成果」这一类事故
    print('\n=== 1.5) seed 落后体检 ===')
    stale = []
    for code in codes:
        sp = os.path.join(SEED, 'report_%s.json' % code)
        try:
            sd = json.load(io.open(sp, encoding='utf-8'))
        except Exception as e:                                        # noqa: BLE001
            print('  !! %s seed 读不出：%s' % (code, e))
            continue
        bad, why = stale_check(code, sd)
        if bad:
            stale.append(code)
            print('  ⚠️ %s 的 seed **落后于线上库**：' % code)
            for w in why:
                print('       - %s' % w)
    if stale and not force:
        print('\n  ⛔ 以上 %d 份的 seed 落后，现在 push 会把线上刷回旧版（且不报错）。' % len(stale))
        print('     先跑： python3 sync_seed_full.py %s --go' % ' '.join(stale))
        print('     确认 seed 确为最新后，加 --force 可强行推送。')
        return
    if stale:
        print('\n  （--force 已指定，仍继续推送 %d 份落后的）' % len(stale))
    else:
        print('  全部 seed 与线上一致 ✅')

    print('\n=== 2) 推送 31 模块版%s ===' % ('（dry-run）' if dry else ''))
    allok = True
    for code in codes:
        allok &= push_one(code, dry)
    print('\n%s' % ('全部完成 ✓' if allok else '存在未通过项 ⚠'))


if __name__ == '__main__':
    main()
