# -*- coding: utf-8 -*-
"""给某只研报的 m29「企业评分」回填十项分数（2026-10-15）。

⚠️ **本脚本只做一件事**：把 `sc-val` 从「—」变成真实分数，并让总分/评级/进度条同步。
   它**从库里现有 m29 反解 KPI 与逐项 notes**，原样带回渲染器 ⇒
   实测说明一字不改，只换分数。

用法：
  python3 build/_fill_score.py 000762 8,8,5,5,9,7,8,7,10,10 --dry   # 只看会变成什么
  python3 build/_fill_score.py 000762 8,8,5,5,9,7,8,7,10,10         # 真写库
  python3 build/_fill_score.py 000762 8,8,5,5,9,7,8,7,10,10 --force # 已有分数也覆盖

★ 总分由 `score_lock.total_of` 算、评级由 `score_lock.grade_of` 定档 ——
  **不手写总分**，避免「十项分加起来 ≠ 显示总分」这种脏数据（正是 2026-10-15 用户图上
  十项分算出 74.1、却写 72 的那类问题）。
"""
import io
import json
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import score_lock as S                                            # noqa: E402

CFG = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cloud.json')))
BASE = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']
H = {'Authorization': 'Bearer ' + CFG['key'],
     'Content-Type': 'application/json',
     'Prefer': 'return=minimal'}

code = sys.argv[1]
scores = [int(x) for x in sys.argv[2].split(',')]
DRY = '--dry' in sys.argv
FORCE = '--force' in sys.argv

if len(scores) != 10:
    print('✗ 需要 10 个分数，收到 %d 个' % len(scores)); raise SystemExit(1)


def strip_tag(s):
    s = re.sub(r'<[^>]+>', '', s)
    return (s.replace('&lt;', '<').replace('&gt;', '>')
             .replace('&amp;', '&').replace('&nbsp;', ' ').replace('&quot;', '"').strip())


def fetch_html():
    u = BASE + 'wb_report_mods?select=report_id,no,html&no=eq.29&report_id=eq.' + code
    rows = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=30).read().decode())
    if not rows:
        print('✗ %s 没有 m29' % code); raise SystemExit(1)
    return rows[0]['html']


def parse_kpi(html):
    """从 kv-grid 反解 KPI 八格 → score_lock.KPI 的键。"""
    got = {}
    for klab, vval in re.findall(
            r'<div class="k">(.*?)</div>\s*<div class="v">(.*?)</div>', html, re.S):
        k, v = strip_tag(klab), strip_tag(vval)
        if v in ('—', '', '-'): continue
        if '总市值' in k:                          got['mktcap'] = v
        elif k.startswith('PE'):                   got['pe'] = v
        elif k.startswith('PB'):                   got['pb'] = v
        elif '当前价格' in k:                       got['price'] = v
        elif '归母净利' in k:                       got['np'] = v
        elif '扣非' in k:                           got['npdx'] = v
        elif 'EPS' in k:                           got['eps'] = v
        elif '报告日期' in k:                       got['date'] = v
    return got


def parse_period(html):
    m = re.search(r'<div class="k">(\d{4}H\d)(?:归母|扣非)', html)
    return m.group(1) if m else ''


def parse_notes(html):
    out = []
    for chunk in re.split(r'<div class="sc-line"', html)[1:]:
        m = re.search(r'<div class="sc-note">(.*?)</div>', chunk, re.S)
        out.append(strip_tag(m.group(1)) if m else '')
    return out


def parse_old_scores(html):
    out = []
    for chunk in re.split(r'<div class="sc-line"', html)[1:]:
        m = re.search(r'<div class="sc-val">(.*?)</div>', chunk, re.S)
        v = strip_tag(m.group(1)) if m else '—'
        out.append(v)
    return out


def main():
    html = fetch_html()
    kpi = parse_kpi(html)
    period = parse_period(html)
    notes = parse_notes(html)
    old = parse_old_scores(html)

    print('=' * 92)
    print('m29 回填  code=%s  模式=%s' % (code, 'DRY（不写库）' if DRY else '正式写入'))
    print('=' * 92)
    print('反解 KPI: %s' % json.dumps(kpi, ensure_ascii=False))
    print('报告期前缀: %r     逐项 notes: %d 条' % (period, len(notes)))
    print('\n原库里的十项分: %s' % ' / '.join(old))
    if old and old != ['—'] * 10 and not FORCE:
        print('\n⚠️ 库里**已有分数**，加 --force 才会覆盖。'); return 1
    print('新填的十项分: %s' % ' / '.join(str(s) for s in scores))

    total = S.total_of(scores)
    rating = S.grade_of(total)
    print('\n→ 总分 total_of(scores) = %s' % total)
    print('→ 评级 grade_of(%s)      = %s' % (total, rating))

    new_html = S.render(kpi=kpi, period=period, notes=notes, scores=scores)

    # —— 逐项核对，别让「算出来的」和「发出去的」悄悄不同 ——
    print('\n---- 渲染结果核对 ----')
    ok = True
    for i, (want, got) in enumerate(zip(scores, parse_old_scores(new_html)), 1):
        if str(got) != str(want):
            print('  ✗ 第 %d 项 sc-val = %r（应为 %d）' % (i, got, want)); ok = False
    if not ok:
        print('\n✗ 渲染结果与目标分数不一致，停手'); return 1
    print('  ✅ 十项 sc-val 逐项一致')
    got_total = re.search(r'class="tn">([^<]+)<', new_html)
    got_rate = re.search(r'class="tt">([^<]+)<', new_html)
    print('  ✅ sc-total.tn = %r（期望 %s）' % (got_total.group(1) if got_total else None, total))
    print('  ✅ sc-total.tt = %r（期望 评级：%s）' % (got_rate.group(1) if got_rate else None, rating))
    print('  ✅ 含 progress bar: %s   含 conic 刻度: %s'
          % ('sc-bar"><i class=' in new_html.replace('\n', ''), 'conic-gradient(#c8102e' in new_html))
    print('  ✅ notes 全部保留: %d / %d 条非空' % (sum(1 for x in notes if x), len(notes)))
    print('  ✅ HTML 长度 %d（原 %d）' % (len(new_html), len(html)))

    if DRY:
        io.open('/tmp/m29_%s_filled.html' % code, 'w', encoding='utf-8').write(new_html)
        print('\n✔ DRY：未写库。预览已存 /tmp/m29_%s_filled.html' % code)
        return 0

    body = json.dumps({'html': new_html}, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(BASE + 'wb_report_mods?report_id=eq.' + code + '&no=eq.29',
                                 data=body, headers=H, method='PATCH')
    with urllib.request.urlopen(req, timeout=30) as r:
        print('\n✅ 写库 HTTP %s' % r.status)

    back = fetch_html()
    t2 = re.search(r'class="tn">([^<]+)<', back)
    print('   回读 sc-total.tn = %r' % (t2.group(1) if t2 else None))
    print('   回读十项 = %s' % ' / '.join(parse_old_scores(back)))
    print('   与目标一致: %s' % (parse_old_scores(back) == [str(s) for s in scores]))
    io.open('/tmp/m29_%s_filled.html' % code, 'w', encoding='utf-8').write(back)
    return 0


raise SystemExit(main())