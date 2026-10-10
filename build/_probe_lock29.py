# -*- coding: utf-8 -*-
"""槽 29「企业评分」锁定契约校验。

【判据】模块结构 / 十项项名 / 权重 / 加分项标记 / 空分形态 —— 与 build/score_lock.py
        的冻结表逐字相符。**得分位允许两种合法态**：
          · 空分（`—`）—— 9 家的常态
          · 有分（数字）—— 仅母本宝钛 600456 一份保留的示范
        其余任何差异都算破坏契约。

【读哪边】默认读线上库（线上才是真身）；`--local` 读本地 seed。
⚠️ 存量 5 家的本地 seed 可能陈旧（搬家产物），别拿本地结论当线上结论。

用法：
    python _probe_lock29.py                 # 线上 · 全部 10 家
    python _probe_lock29.py 002408 603977    # 线上 · 指定几家
    python _probe_lock29.py --local          # 本地 seed
"""
import io
import json
import os
import re
import sys
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import score_lock as SL               # noqa: E402

ALL = ['600456', '600459', '002237', '000731', '000830',
       '603977', '601118', '601958', '603599', '002408']


def unesc(s):
    return (s.replace('&gt;', '>').replace('&lt;', '<').replace('&amp;', '&')
            .replace('&nbsp;', ' '))


def norm(s):
    """项名归一：去标签 / 解转义 / 去「加分项·pos」/ 去全部空白。"""
    s = re.sub(r'<[^>]+>', '', s)
    s = unesc(s)
    s = s.replace('加分项', '').replace('pos', '')
    return re.sub(r'\s+', '', s)


def strip_tags(s):
    return unesc(re.sub(r'<[^>]+>', '', s)).strip()


def fetch_live(codes):
    cfg = json.loads(io.open(os.path.join(HERE, 'cloud.json'), encoding='utf-8').read())
    base = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % cfg['envId']
    hdr = {'Authorization': 'Bearer ' + cfg['key']}
    out = {}
    for code in codes:
        rows, off = [], 0
        while True:
            q = ('wb_report_mods?report_id=eq.%s&select=no,title,html&order=no.asc'
                 '&limit=1000&offset=%d' % (code, off))
            rq = urllib.request.Request(base + q, headers=hdr)
            with urllib.request.urlopen(rq, timeout=90) as r:
                b = json.loads(r.read().decode('utf-8'))
            rows += b
            if len(b) < 1000:
                break
            off += 1000
        hit = [m for m in rows if m.get('no') == '29'] or \
              [m for m in rows if '评分' in (m.get('title') or '')]
        out[code] = hit[0] if hit else None
    return out


def fetch_local(codes):
    out = {}
    p = os.path.join(HERE, 'seed', 'report_%s.json')
    for code in codes:
        f = p % code
        if not os.path.exists(f):
            out[code] = None
            continue
        rep = json.loads(io.open(f, encoding='utf-8').read())
        hit = [m for m in rep['mods'] if str(m.get('no')) == '29']
        out[code] = hit[0] if hit else None
    return out


def check(code, mod):
    """返回 (问题列表, 摘要素)"""
    bad = []
    if not mod:
        return ['线上没有槽 29'], None
    h = mod.get('html') or ''
    title = mod.get('title') or ''

    for cls in ('score-hero', 'gauge-wrap', 'kv-grid', 'criteria', 'sc-total'):
        if ('class="%s"' % cls) not in h:
            bad.append('缺结构 %s' % cls)

    n_line = h.count('class="sc-line"')
    if n_line != 10:
        bad.append('sc-line %d 条（应 10）' % n_line)

    # 项名 + 权重
    names = re.findall(r'<div class="sc-name">(.*?)</div>', h, re.S)
    wts = re.findall(r'<div class="sc-w">(\d+)%</div>', h)
    want = [(norm(n), str(w)) for n, _, w in SL.ITEMS]
    got = [(norm(n), w) for n, w in zip(names, wts)]
    for i, (w, g) in enumerate(zip(want, got)):
        if w[0] != g[0]:
            bad.append('第%d项项名不符：冻结 %r ≠ 线上 %r' % (i + 1, w[0], g[0]))
        if w[1] != g[1]:
            bad.append('第%d项权重不符：冻结 %s%% ≠ 线上 %s%%' % (i + 1, w[1], g[1]))
    if len(names) != 10 or len(wts) != 10:
        bad.append('项名 %d / 权重 %d（应各 10）' % (len(names), len(wts)))

    # ★ `data-w`（2026-09-22 起 score_lock 渲染会带）：报告壳的「动态调整」靠它拿权重。
    #   旧渲染没有它 ⇒ 壳退化成解析 `.sc-w` 的「10%」文本，行为一致，**不算失败**；
    #   但一旦写了就必须与冻结表逐字相符（写错会让页面总分悄悄算歪，比缺更危险）。
    dws = re.findall(r'class="sc-line" data-w="(\d+)"', h)
    dw_want = [str(w) for _, _, w in SL.ITEMS]
    info = []
    if not dws:
        info.append('data-w 无（旧渲染 → 壳走 .sc-w 文本兜底）')
    elif dws == dw_want:
        info.append('data-w ✅ 与冻结表相符')
    else:
        bad.append('data-w 与冻结表不符：%r ≠ %r' % (dws, dw_want))

    # 加分项标记
    n_pos = h.count('<em class="pos-em">加分项</em>')
    n_want = sum(1 for _, p, _ in SL.ITEMS if p)
    if n_pos != n_want:
        bad.append('加分项标记 %d 处（应 %d）' % (n_pos, n_want))
    n_leak = len(re.findall(r'>\s*pos\s*<', h))
    if n_leak:
        bad.append('⚠️ 历史缺陷复发：字面 `pos` %d 处' % n_leak)

    # 标题
    if title.strip() != SL.TITLE:
        bad.append('标题不符：%r ≠ %r' % (title.strip(), SL.TITLE))

    # 得分位：空分 or 有分，二选一
    vals = [strip_tags(x) for x in re.findall(r'<div class="sc-val">(.*?)</div>', h)]
    blank = sum(1 for v in vals if v == SL.BLANK)
    num = sum(1 for v in vals if re.fullmatch(r'\d+(\.\d+)?', v))
    if blank + num != len(vals) or len(vals) != 10:
        bad.append('得分位异常：%r' % vals)
    form = '空分' if blank == 10 else ('有分' if num == 10 else '混合?')
    if n_line == 10 and len(vals) != 10:
        bad.append('sc-val %d 个（应 10）' % len(vals))
    if not (blank == 10 or num == 10):
        bad.append('得分位不是「全空」或「全数字」')

    gate = re.search(r'<div class="gauge-num">(.*?)<', h, re.S)
    badge = re.search(r'<div class="gauge-badge">(.*?)</div>', h, re.S)
    # ★ KPI 卡：格数锁死 8；标签文案允许既定变体（见下 warn）
    n_kv = h.count('class="kv"')
    if n_kv != 8:
        bad.append('KPI 卡 %d 格（应 8）' % n_kv)
    kv = re.findall(r'<div class="k">(.*?)</div>\s*<div class="v[^"]*"[^>]*>(.*?)</div>',
                    h, re.S)
    labs = [strip_tags(a) for a, _ in kv]
    warns = []
    if kv:
        if not labs[0].startswith('总市值'):
            warns.append('KPI 第 1 格标签 %r' % labs[0])
        if not any('PE' in x for x in labs):
            warns.append('KPI 缺 PE 格')
        if not any('PB' in x for x in labs):
            warns.append('KPI 缺 PB 格')
        if not any(x.startswith('当前价格') for x in labs):
            warns.append('KPI 缺「当前价格」格')
        if labs[-1] != '报告日期':
            warns.append('KPI 末格不是「报告日期」（%r）' % labs[-1])
    return bad, {
        'len': len(h),
        'form': form,
        'gauge': strip_tags(gate.group(1)) if gate else '?',
        'badge': strip_tags(badge.group(1)) if badge else '?',
        'kv': n_kv,
        'warn': warns,
        'info': info,
        'kvi': [(strip_tags(a), strip_tags(b)) for a, b in kv],
    }


def main(argv):
    local = '--local' in argv
    codes = [a for a in argv if re.fullmatch(r'\d{6}', a)] or ALL
    SL.check_rubric()
    print('冻结契约 %s · 十项权重 %s · 合计 %d'
          % (SL.LOCK_VERSION, '/'.join(str(w) for _, _, w in SL.ITEMS),
             sum(w for _, _, w in SL.ITEMS)))
    print('数据源：%s\n' % ('本地 seed（可能陈旧）' if local else '线上库（真身）'))

    mods = fetch_local(codes) if local else fetch_live(codes)
    fails, warns = [], []
    for code in codes:
        bad, s = check(code, mods.get(code))
        flag = '✅' if not bad else '❌'
        if s:
            print('%s %-7s %-4s 长%5d | KV %d 格 | 仪表 %-6s %-6s'
                  % (flag, code, s['form'], s['len'], s['kv'], s['gauge'], s['badge']))
            if code == '600456':
                print('      KV: %s' % ' | '.join('%s=%s' % x for x in s['kvi']))
        else:
            print('%s %-7s（无模块）' % (flag, code))
        for b in bad:
            print('      ✗ %s' % b)
        for w in (s or {}).get('warn') or []:
            print('      ⚠ %s' % w)
            warns.append(code)
        for f in (s or {}).get('info') or []:
            print('      · %s' % f)
        if bad:
            fails.append(code)

    print()
    print('通过 %d / %d' % (len(codes) - len(fails), len(codes)))
    if warns:
        print('KPI 卡标签告警：%s（格数与槽位语义合格，仅文案变体 —— 见报告）'
              % ' '.join(sorted(set(warns))))
    if fails:
        print('未通过：%s' % ' '.join(fails))
        return 1
    print('槽 29 锁定契约完整 —— 结构与冻结表一致。')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
