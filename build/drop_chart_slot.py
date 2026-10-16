#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""摘掉某个模块里的**图表槽位**（`<div data-chart="KEY" class="chart-box"></div>`）。

用途：当某张图的**图型与数据表语义不匹配**时（不是"缺数据"，是"画出来是错的"），
      渲染器判据已经拦住了新构建，但**库里旧模块里的槽位还在** —— 页面会照旧去取
      那张（可能全空或口径错位的）opt 渲染出来，留下一个空框或一张错图。
      `wb_report_charts` 的行删不掉（无 is_del、不在硬删 RPC 白名单），
      所以唯一能做的就是**把槽位摘掉**：图变孤儿 ⇒ 页面不再引用 ⇒ 不显示。

⚠️ 只删**图槽 div**，不动表格、说明、logic 块。删完会检查模块里是否已无该 key 的引用。

用法：
    python3 drop_chart_slot.py 600459:6:chartCap 600459:12:chartPrice 601958:7:chartProd
    python3 drop_chart_slot.py ... --go        # 写库（不写则只干跑）
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
HDR = {'Authorization': 'Bearer ' + CFG['key'], 'Content-Type': 'application/json',
       'Prefer': 'return=minimal'}
GO = '--go' in sys.argv


def get(path):
    rq = urllib.request.Request(BASE + path, headers=HDR)
    with urllib.request.urlopen(rq, timeout=120) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def patch_mod(code, no, html):
    body = json.dumps({'html': html}, ensure_ascii=False).encode('utf-8')
    rq = urllib.request.Request(BASE + 'wb_report_mods?id=eq.%s_m%s' % (code, no),
                                data=body, headers=HDR, method='PATCH')
    with urllib.request.urlopen(rq, timeout=120) as r:
        return r.status


def drop(html, key):
    """删掉该 key 的图槽 div（保留其余一切）。返回 (新 html, 删掉的片段)"""
    pat = re.compile(r'\s*<div data-chart="%s"[^>]*>\s*</div>' % re.escape(key))
    m = pat.search(html)
    if not m:
        return html, None
    return html[:m.start()] + html[m.end():], m.group(0).strip()


def main():
    specs = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not specs:
        print(__doc__)
        return
    jobs = []
    for s in specs:
        code, no, key = s.split(':')
        jobs.append((code, no, key))

    by_code = {}
    for code, no, key in jobs:
        by_code.setdefault(code, []).append((no, key))

    for code, items in by_code.items():
        print('=' * 76)
        print('%s' % code)
        for no, key in items:
            rows = get('wb_report_mods?report_id=eq.%s&no=eq.%s&select=title,html' % (code, no))
            if not rows:
                print('  ✗ 库里找不到 m%s' % no)
                continue
            title, h = rows[0]['title'], rows[0]['html'] or ''
            new, frag = drop(h, key)
            print('  m%-3s %-28s 槽位 %s' % (no, (title or '')[:26], key))
            if frag is None:
                print('        · 已经没有这个槽位（可能已处理过）')
                continue
            print('        · 待删片段：%s' % frag)
            print('        · 长度 %d → %d（-%d）' % (len(h), len(new), len(h) - len(new)))
            if ('data-chart="%s"' % key) in new:
                print('        ✗ 删完仍有引用，跳过')
                continue
            if GO:
                st = patch_mod(code, no, new)
                back = get('wb_report_mods?report_id=eq.%s&no=eq.%s&select=html' % (code, no))[0]['html']
                ok = ('data-chart="%s"' % key) not in back
                print('        ✓ 写库 HTTP %s ｜ 回读校验 %s' % (st, '✅' if ok else '❌'))
    print()
    print('%s' % ('已写库' if GO else '干跑（加 --go 写库）'))


if __name__ == '__main__':
    main()
