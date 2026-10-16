# -*- coding: utf-8 -*-
"""把「EPS(TTM)×收盘价」双轴图铺到其余 11 份研报（用户令 2026-10-15：
「全部11份都加，并且把成交额加收盘价那块全部去掉」）

做两件事：
  ① 各研报 m29（企业评分）开头插入 <h3>EPS 与股价历史</h3> + chart_eps 槽 + 来源注
     —— 位置与 600456（宝钛）完全同款；
  ② 各研报 m28（估值分析）里删掉「收盘价 + 成交额」图槽 chartPrice2。

⚠️ 全部是**改库**（wb_report_mods.html / wb_report_charts.opt），不需要重新部署
   —— report.html 的 renderCharts 按槽位 data-chart 拉库渲染，槽是通用的。
⚠️ wb_report_charts **删不掉行**（REST DELETE 实测 401 DATABASE_42501，RPC 白名单里也没有）
   ⇒ chartPrice2 行只能留成**孤儿行**（槽位没了 → 页面不再渲染它）。
⚠️ 写库前必备份：本脚本把 11 份 × 3 张表整份导出到 build/backup/report_<code>_pre_eps11_<ts>.json

用法：
  python build/apply_eps_to_11.py            # 干跑（打印将要做的改动，不写库）
  python build/apply_eps_to_11.py --go       # 备份 + 写库 + 回读复核
  python build/apply_eps_to_11.py --go 000731 000762   # 只做指定标的
"""
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
SEED = os.path.join(HERE, 'seed')
BAK = os.path.join(HERE, 'backup')
CFG = json.loads(io.open(os.path.join(HERE, 'cloud.json'), encoding='utf-8').read())
REST = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']
HDR = {'Authorization': 'Bearer ' + CFG['key'], 'Content-Type': 'application/json'}

CODES = ['000731', '000762', '000830', '002237', '002408', '600392',
         '600459', '601118', '601958', '603227', '603599', '603977']

CHART_NAME = 'EPS(TTM) 与股价'

M29_HEAD = (
    '<h3>EPS 与股价历史</h3>\n'
    '    <div data-chart="chart_eps" class="chart-box"></div>\n'
    '    <p class="src"><b>来源：</b>每股收益 EPS(TTM)：上市公司定期报告披露值'
    '（TTM 基准日＝报表公告日期，%(e0)s ~ %(e1)s 共 %(en)d 个报告期，按披露生效日逐期取点）；'
    '收盘价：通达信日线（后复权序列按最新不复权收盘价等比归一出「前复权」，'
    '上市以来 %(pn)d 个交易日，%(p0)s ~ %(p1)s；最新收盘价 %(last).2f 元）。</p>\n    '
)


def req(path, method='GET', body=None, timeout=120):
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
    r = urllib.request.Request(REST + path, data=data, method=method, headers=HDR)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            raw = resp.read().decode('utf-8', 'replace')
            return resp.status, (json.loads(raw) if raw.strip() else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')[:400]
    except Exception as e:
        return 0, str(e)


def fmt(d):
    return '%s-%s-%s' % (d[:4], d[4:6], d[6:])


def build_m29_html(code):
    eps = json.load(io.open(os.path.join(SEED, '_eps_steps_%s.json' % code), encoding='utf-8'))
    px = json.load(io.open(os.path.join(SEED, '_tdx_%s_hfq.json' % code), encoding='utf-8'))['rows']
    raw = json.load(io.open(os.path.join(SEED, '_raw_last.json'), encoding='utf-8'))['raw_last']
    head = M29_HEAD % dict(e0=eps['steps'][0][0], e1=eps['steps'][-1][0], en=eps['n'],
                           pn=len(px), p0=fmt(px[0][0]), p1=fmt(px[-1][0]),
                           last=raw[code])
    return head


def strip_chart(html, cid):
    pat = re.compile(r'[ \t]*<div[^>]*data-chart="%s"[^>]*>\s*</div>\s*' % re.escape(cid))
    n = len(pat.findall(html))
    return pat.sub('', html), n


def main():
    args = sys.argv[1:]
    go = '--go' in args
    codes = [a for a in args if not a.startswith('--')] or CODES
    ts = time.strftime('%Y%m%d-%H%M%S')
    os.makedirs(BAK, exist_ok=True)

    plan = []
    print('=== 备份线上现状 ===')
    for code in codes:
        pack = {'ts': ts, 'code': code, 'kind': 'pre_eps11'}
        for tbl, q in [('wb_reports', 'id=eq.%s' % code),
                       ('wb_report_mods', 'report_id=eq.%s&order=seq.asc' % code),
                       ('wb_report_charts', 'report_id=eq.%s&order=seq.asc' % code)]:
            st, r = req('%s?%s' % (tbl, q))
            if st != 200:
                print('  !! 备份 %s 失败 %s %s' % (tbl, st, r))
                return 1
            pack[tbl] = r
        p = os.path.join(BAK, 'report_%s_pre_eps11_%s.json' % (code, ts))
        io.open(p, 'w', encoding='utf-8').write(json.dumps(pack, ensure_ascii=False))
        print('  %s  mods %2d · charts %2d → %s'
              % (code, len(pack['wb_report_mods']), len(pack['wb_report_charts']),
                 os.path.basename(p)))
        plan.append(pack)

    print('\n=== 改动清单 ===')
    ops = []
    for pack in plan:
        code = pack['code']
        mods = {int(m['no']): m for m in pack['wb_report_mods']}
        charts = pack['wb_report_charts']
        m28, m29 = mods.get(28), mods.get(29)
        if not m28 or not m29:
            print('  !! %s 缺 m28/m29，跳过' % code)
            continue
        h29_old = m29['html'] or ''
        # ★ 2026-10-16：幂等保护 —— 本脚本原本「不可重跑」（m29 是**前插**，重跑会叠一份）。
        #   现在先查特征串，已有就跳过前插，只做图行的 upsert。
        if 'data-chart="chart_eps"' in h29_old:
            h29_new = h29_old
            print('  %s  m29 已有 chart_eps 槽 ⇒ 跳过前插（幂等）' % code)
        else:
            h29_new = build_m29_html(code) + h29_old
        h28_new, hit = strip_chart((m28['html'] or ''), 'chartPrice2')
        epsopt = json.load(io.open(os.path.join(SEED, '_eps_opt_%s.json' % code),
                                   encoding='utf-8'))
        seq = max([c['seq'] or 0 for c in charts] + [0]) + 1
        cid = '%s_chart_eps' % code
        old = [c for c in charts if c['id'] == cid]
        np = len(epsopt['series'][0]['data'])
        npx = len(epsopt['series'][1]['data'])
        axL, axR = epsopt['yAxis'][0], epsopt['yAxis'][1]
        p0 = round((0 - axL['min']) / (axL['max'] - axL['min']) * 100)
        p1 = round((0 - axR['min']) / (axR['max'] - axR['min']) * 100)
        print('  %s  m29 %d→%d B（+槽 chart_eps）· m28 chipPrice2 命中 %d 处 · '
              'chart_eps seq=%d %s' % (code, len(m29['html'] or ''), len(h29_new), hit,
                                       seq, '【已存在→原地更新】' if old else '【新增】'))
        print('        左轴[%.2f,%.2f]/%.4f  右轴[%.2f,%.2f]/%.4f  0位 %d%% vs %d%%  '
              'EPS %d 点 · 价 %d 点'
              % (axL['min'], axL['max'], axL['interval'], axR['min'], axR['max'],
                 axR['interval'], p0, p1, np, npx))
        if hit != 1:
            print('        ⚠ chartPrice2 命中 %d 处（期望 1）' % hit)
        ops.append((code, m28['id'], h28_new, m29['id'], h29_new, cid, seq, epsopt))

    if not go:
        print('\n[干跑] 未写库。加 --go 执行。')
        return 0

    print('\n=== 写库 ===')
    now = int(time.time() * 1000)
    ok = True
    for code, mid28, h28, mid29, h29, cid, seq, opt in ops:
        for mid, h, what in [(mid28, h28, 'm28 -chartPrice2'), (mid29, h29, 'm29 +chart_eps')]:
            st, r = req('wb_report_mods?id=eq.%s' % mid, 'PATCH', {'html': h, 'up': now})
            print('  %s %-22s → %s %s' % ('✔' if st < 400 else '✖', mid, st,
                                          '' if st < 400 else r))
            ok &= st < 400
        st, r = req('wb_report_charts?on_conflict=id', 'POST',
                    [{'id': cid, 'report_id': code, 'code': code, 'seq': seq,
                      'name': CHART_NAME, 'opt': opt, 'up': now}],
                    )
        print('  %s %-22s → %s %s' % ('✔' if st < 400 else '✖', cid, st,
                                      '' if st < 400 else r))
        ok &= st < 400

    # ---------------- 回读复核 ----------------
    print('\n=== 回读复核 ===')
    time.sleep(2)
    for code, mid28, h28, mid29, h29, cid, seq, opt in ops:
        stm, r = req('wb_report_mods?report_id=eq.%s&select=id,no,html&order=seq.asc' % code)
        mm = {int(x['no']): x for x in r}
        g28, g29 = mm[28]['html'] or '', mm[29]['html'] or ''
        a1 = (g29 == h29)
        a2 = (g28 == h28)
        a3 = ('data-chart="chart_eps"' in g29)
        a4 = ('data-chart="chartPrice2"' not in g28)
        stc, rc = req('wb_report_charts?id=eq.%s&select=opt,seq,name' % cid)
        c = rc[0] if rc else None
        o = c['opt'] if c else None
        if isinstance(o, str):
            o = json.loads(o)
        a5 = (json.dumps(o, ensure_ascii=False, sort_keys=True)
              == json.dumps(opt, ensure_ascii=False, sort_keys=True))
        print('  %s  m29 一致 %s · m28 一致 %s · 槽在 %s · 旧槽已删 %s · opt 一致 %s'
              % (code, a1, a2, a3, a4, a5))
        ok &= a1 and a2 and a3 and a4 and a5
    print('\n%s' % ('全部通过 ✓' if ok else '存在未通过项 ⚠'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
