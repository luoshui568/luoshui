# -*- coding: utf-8 -*-
"""把线上库某一家研报的全量内容同步进本地 seed（report / mods / charts）。

为什么必须做：`build/build.py` 会把 **600456 的** `seed/report_600456.json` 注入成页面里的
`window.RPT_SEED`（离线/无 envId 时的兜底数据源）。库改了而 seed 没跟，就会出现
「线上库 31 模块、壳内 seed 29 模块」的错位 —— 三方核对里
「线上库 == 壳内 RPT_SEED == 本地 seed」这条就会红。
⚠️ 只有当 **600456** 的 seed 变了才需要重跑 `build.py` 并重传壳；
其余 9 家的 seed 只是本地缓存（不内嵌），同步是为了防止后续脚本拿旧快照把改动盖回去。

shape（与历史 seed 完全一致，勿改）：
  report: code,name,kicker,title,subtitle,badges,verdict_title,verdict_html,
          kpis,kpi_note,toc,essence_html,footer_html,theme
  mods  : [{seq, no, title, html}]
  charts: [{seq, id, name, opt}]        # ⚠️ seed 里的图表 id **不带** `<code>_` 前缀

用法：
  python build/sync_seed_full.py                # 干跑 600456，只比对
  python build/sync_seed_full.py --go           # 写盘 600456
  python build/sync_seed_full.py 002408         # 干跑指定一家（2026-09-22 新增）
  python build/sync_seed_full.py --all --go     # 全部 10 家写盘
"""
import io
import json
import os
import re
import sys
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
B = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(io.open(os.path.join(B, 'cloud.json'), encoding='utf-8'))
BASE = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']
HDR = {'apikey': CFG['key'], 'Authorization': 'Bearer ' + CFG['key'], 'Accept': 'application/json'}
ALL = ['600456', '600459', '002237', '000731', '000830',
       '603977', '601118', '601958', '603599', '002408']
GO = '--go' in sys.argv
#: 位置参数里的 6 位数字 = 指定公司；`--all` = 全部 10 家；缺省只做母本 600456
_ARG = [a for a in sys.argv[1:] if len(a) == 6 and a.isdigit()]
CODES = ALL if '--all' in sys.argv else (_ARG or ['600456'])

REPORT_KEYS = ['code', 'name', 'kicker', 'title', 'subtitle', 'badges', 'verdict_title',
               'verdict_html', 'kpis', 'kpi_note', 'toc', 'essence_html', 'footer_html', 'theme']


def get(path):
    rq = urllib.request.Request(BASE + path, headers=HDR)
    with urllib.request.urlopen(rq, timeout=90) as r:
        return json.loads(r.read().decode('utf-8'))


def fetch(code):
    rows, off = [], 0
    while True:
        b = get('wb_report_mods?select=no,seq,title,html&report_id=eq.%s'
                '&order=seq.asc&limit=1000&offset=%d' % (code, off))
        rows += b
        if len(b) < 1000:
            break
        off += 1000
    rows.sort(key=lambda x: int(x.get('no') or 0))       # no 是文本，必须按整数重排
    rep = get('wb_reports?select=*&id=eq.%s' % code)[0]
    charts = get('wb_report_charts?select=seq,id,name,opt&report_id=eq.%s'
                 '&order=seq.asc&limit=1000' % code)
    return rep, rows, charts


def do_code(code):
    """同步一家；返回 (是否写盘成功, 相同模块数, 模块总数)。"""
    sp = os.path.join(B, 'seed', 'report_%s.json' % code)
    rep, mods, charts = fetch(code)
    report = {k: rep.get(k) for k in REPORT_KEYS}
    seed = {
        'report': report,
        'mods': [{'seq': m['seq'], 'no': m['no'], 'title': m['title'], 'html': m['html']}
                 for m in mods],
        'charts': [{'seq': c['seq'], 'id': c['id'].replace(code + '_', '', 1),
                    'name': c['name'],
                    'opt': json.loads(c['opt']) if isinstance(c['opt'], str) else c['opt']}
                   for c in charts],
    }

    print('=== 读库 ===')
    print('  报告：%s（%s） ｜ %d 模块 ｜ %d 图 ｜ toc %d 条'
          % (rep.get('name'), code, len(mods), len(charts), len(report['toc'] or [])))

    # ---- 自检 1：编号连续 + id 与 no 一致
    nos = [int(m['no']) for m in mods]
    assert nos == list(range(1, len(mods) + 1)), '模块编号不连续：%s' % nos
    print('  编号 1..%d 连续 ✅' % len(mods))

    # ---- 自检 2：正文引用的图表键 ⊆ 图表表（图槽必须都有数据）
    used = set()
    for m in mods:
        used |= set(re.findall(r'data-chart="([^"]+)"', m['html'] or ''))
    have = {c['id'] for c in seed['charts']}
    missing = sorted(used - have)
    orphan = sorted(have - used)
    print('  正文引用图槽 %d 个 ｜ 图表行 %d 个' % (len(used), len(have)))
    print('  引用但无数据：%s' % (missing or '无 ✅'))
    print('  有数据但未引用：%s' % (orphan or '无 ✅'))
    assert not missing, '有图槽取不到数据：%s' % missing

    # ---- 自检 3：toc 锚点都能对上一个模块
    anchors = [x['anchor'] for x in (report['toc'] or [])]
    ids = {'m%d' % n for n in nos}
    bad = [a for a in anchors if a != 'verdict' and a not in ids]
    print('  目录锚点 %d 个，失效锚点：%s' % (len(anchors), bad or '无 ✅'))
    assert not bad, '目录锚点对不上模块：%s' % bad

    old = json.load(io.open(sp, encoding='utf-8')) if os.path.exists(sp) else {
        'mods': [], 'charts': [], 'report': {}}
    print()
    print('=== 与本地 seed 比对 ===')
    print('  seed 旧：%d 模块 / %d 图 ｜ 新：%d 模块 / %d 图'
          % (len(old['mods']), len(old.get('charts') or []), len(seed['mods']), len(seed['charts'])))
    same_mods = sum(1 for a, b in zip(old['mods'], seed['mods'])
                    if a['title'] == b['title'] and a['html'] == b['html'])
    print('  标题+正文完全相同的模块：%d / %d' % (same_mods, len(seed['mods'])))
    print('  toc 旧 %d 条 → 新 %d 条' % (len(old['report'].get('toc') or []), len(anchors)))

    if not GO:
        print()
        print('（干跑结束，加 --go 才写盘）')
        return False, same_mods, len(seed['mods'])

    io.open(sp, 'w', encoding='utf-8').write(
        json.dumps(seed, ensure_ascii=False, separators=(',', ':')))

    back = json.load(io.open(sp, encoding='utf-8'))
    assert [m['no'] for m in back['mods']] == [m['no'] for m in seed['mods']]
    assert [c['id'] for c in back['charts']] == [c['id'] for c in seed['charts']]
    assert back['report']['toc'] == report['toc']
    print()
    print('写盘完成：%s（%d 字节）' % (os.path.relpath(sp, B), os.path.getsize(sp)))
    print('  回读校验通过 ✅')
    print('  mods %d ｜ charts %d ｜ toc %d ｜ [MISSING] 合计 %d 处'
          % (len(back['mods']), len(back['charts']), len(back['report']['toc']),
             sum(x['html'].count('[MISSING]') for x in back['mods'])))
    return True, same_mods, len(seed['mods'])


def main():
    stat = []
    for i, code in enumerate(CODES):
        if i:
            print('\n' + '─' * 72 + '\n')
        try:
            stat.append((code,) + do_code(code))
        except Exception as e:                                        # noqa: BLE001
            print('  ❌ %s 失败：%s' % (code, e))
            stat.append((code, None, -1, -1))
    if len(CODES) > 1:
        print('\n' + '=' * 72)
        print('汇总（%s）：' % ('写盘' if GO else '干跑'))
        for code, ok, same, tot in stat:
            print('  %-8s %s  相同 %s/%s'
                  % (code, {True: '✅ 已写盘', False: '— 干跑', None: '❌ 失败'}[ok], same, tot))


if __name__ == '__main__':
    main()
