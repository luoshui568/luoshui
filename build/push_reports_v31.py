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


def main():
    args = sys.argv[1:]
    dry = '--dry' in args
    codes = all_codes() if '--all' in args else [a for a in args if not a.startswith('--')]
    ts = time.strftime('%Y%m%d-%H%M%S')
    print('=== 1) 备份线上现状 ===' % ())
    backup(codes, ts)
    print('\n=== 2) 推送 31 模块版%s ===' % ('（dry-run）' if dry else ''))
    allok = True
    for code in codes:
        allok &= push_one(code, dry)
    print('\n%s' % ('全部完成 ✓' if allok else '存在未通过项 ⚠'))


if __name__ == '__main__':
    main()
