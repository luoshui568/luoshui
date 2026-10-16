# -*- coding: utf-8 -*-
"""把 600456 模块 29 的「来源」行换成新图表的数据出处（iFinD EPS + 通达信日线）。

为什么要动模块正文（本轮唯一一处正文改动）：
  图表的数据源从「研究报告 PPTX 幻灯片 49」换成了 iFinD + 通达信，
  来源行若还写着 PPTX，就是**在报告里留下一处失实引用**。
  所以只做这一处**定点替换** —— 技术解读段、评分块、KPI 一个字节都不动。

用法：
  python build/set_600456_m29_src.py         # 干跑
  python build/set_600456_m29_src.py --go    # 写库 + 回读
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
CFG = json.loads(io.open(os.path.join(HERE, 'cloud.json'), encoding='utf-8').read())
REST = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']
H = {'Authorization': 'Bearer ' + CFG['key'], 'Content-Type': 'application/json'}
MOD_ID = '600456_m29'
BAKDIR = os.path.join(HERE, 'backup')

OLD_KEY = '宝钛股份研究报告 PPTX 幻灯片 49'
NEW_SRC = ('<p class="src"><b>来源：</b>同花顺 iFinD（每股收益 EPS(TTM)，'
           'TTM 基准日＝报表公告日期，2002 年以来 87 个报告期，按披露生效日逐期取点）；'
           '通达信日线（收盘价前复权，上市以来 5,897 个交易日，'
           '2002-04-12 ~ 2026-10-15；最新前复权价 23.48 元）。</p>')


def req(q, method='GET', body=None):
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
    r = urllib.request.Request(REST + q, data=data, method=method, headers=H)
    with urllib.request.urlopen(r, timeout=90) as resp:
        t = resp.read().decode('utf-8')
        return json.loads(t) if t.strip() else None


def main():
    go = '--go' in sys.argv
    rows = req('wb_report_mods?id=eq.%s&select=id,no,title,html' % MOD_ID)
    if not rows:
        print('★ 模块不存在：%s' % MOD_ID)
        return 1
    row = rows[0]
    html = row['html']
    print('模块 %s「%s」  html %d 字符' % (row['id'], row['title'], len(html)))

    assert html.count('<p class="src">') == 1, '模块 29 里的 .src 段不是恰好 1 个：%d' % html.count('<p class="src">')
    assert OLD_KEY in html, '找不到旧来源字样，先人工确认'
    i = html.find('<p class="src">')
    j = html.find('</p>', i) + len('</p>')
    old_src = html[i:j]
    print('旧来源行 %d 字符：\n  %s' % (len(old_src), old_src))
    new_html = html[:i] + NEW_SRC + html[j:]
    print('\n新来源行 %d 字符：\n  %s' % (len(NEW_SRC), NEW_SRC))
    print('\n正文其余部分逐字节不变：%s' % (new_html[:i] == html[:i] and new_html[i + len(NEW_SRC):] == html[j:]))
    print('长度 %d → %d（Δ%+d）' % (len(html), len(new_html), len(new_html) - len(html)))
    assert 'chart_eps' in new_html, 'chart_eps 槽位丢了'

    if not go:
        print('\n[干跑] 未写库。加 --go 执行。')
        return 0

    os.makedirs(BAKDIR, exist_ok=True)
    ts = time.strftime('%Y%m%d-%H%M%S')
    bak = os.path.join(BAKDIR, '600456_m29_pre_src_%s.json' % ts)
    io.open(bak, 'w', encoding='utf-8').write(
        json.dumps({'at': int(time.time() * 1000), 'row': row}, ensure_ascii=False))
    print('\n快照 → %s（%d B）' % (os.path.basename(bak), os.path.getsize(bak)))

    now = int(time.time() * 1000)
    try:
        req('wb_report_mods?id=eq.%s' % MOD_ID, 'PATCH', {'html': new_html, 'up': now})
        print('  ✔ PATCH %s  up=%d' % (MOD_ID, now))
    except urllib.error.HTTPError as e:
        print('  ✖ PATCH 失败：HTTP %s %s' % (e.code, e.read()[:400]))
        return 1

    time.sleep(1.5)
    got = req('wb_report_mods?id=eq.%s&select=html,up' % MOD_ID)[0]
    same = got['html'] == new_html
    print('\n回读复核：%s  up=%s' % ('逐字节一致 ✅' if same else '★ 不一致 ❌', got['up']))
    if not same:
        print('  期望 %d 字符 / 实际 %d 字符' % (len(new_html), len(got['html'])))
        return 1
    k = got['html'].find('<p class="src">')
    print('  来源行回读：%s' % got['html'][k:k + 60])
    return 0


if __name__ == '__main__':
    sys.exit(main())
