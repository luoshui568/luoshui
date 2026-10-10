# -*- coding: utf-8 -*-
"""600456 模块合并：把 A 的正文并入 B 的下方，然后**删除 A 行**、A 之后的编号整体前移。

用户诉求（2026-09-20 傍晚）：
  「把 m19 并入 m25，直接在 m25 里面的下方加入」
  ⇒ 源 m19 = 风险矩阵（5 条 .risk-item，纯文字、无图、无交叉引用）
     目标 m25 = 钛行业介绍与市场规模
     结果：31 → 30 个模块；m20..m31 全部 -1

插入点：目标正文里 `<p class="src">` 来源注脚**之前** —— 各模块的 src 惯例是收尾，
        所以「并入下方」= 正文内容区的最下方，而不是把脚注挤到中间。

═══════════════════════════════════════════════════════════════════
⚠️ 与移位（move_mod_600456.py）不同的两点
  ① **要删行**：`wb_report_mods` 的 DELETE 走 REST 会被拒（42501，权限），
     必须用 MCP `managePgDatabase(action='execute', sql='DELETE FROM ...', confirm=True)`。
     本脚本会先试 REST，被拒则打印现成的 MCP 调用，**并停在改号之前**（保证可重入）：
       · 第一次跑 --go：REST 删除被拒 → 打印 MCP 语句 → 退出（未动任何编号）
       · 用 MCP 删完后再跑 --go：检测到源行已不在 → 跳过删除 → 直接改号 ✅
  ② **升序改号即可**（这次是整体**下移**）：删掉源行后，`m20 → m19` 时 19 已空，
     `m21 → m20` 时 20 刚腾空 …… 逐个升序不会撞主键，**无需两段式**。
     （升序也有利于中断后从断点续跑。）
═══════════════════════════════════════════════════════════════════
其余铁律与 restructure_600456.py 一致：
  · 正文「模块 N」交叉引用必须**单遍同时**替换（顺序替换会级联错位）
  · `seq` 跟 `no` 一起改、`up` 刷 ms
  · **图表完全不参与**（靠正文里的 `data-chart="键名"` 挂载，与模块号无关）

分段（当前编号）—— 合并后各段成员按新位置重排，段锚点 = 段内新位置最小的模块：
  投资核心(verdict) / 公司简介 1-4 / 公司业务 5-9 / 公司营收 10-16 /
  公司投资 17-19 / 公司链条 20-24 / 行业分析 25 / 供需分析 26 /
  盈利预测 27-28 / 企业评分 29-31

用法：
  python build/merge_mod_600456.py            # 干跑（默认 --src 19 --dst 25）
  python build/merge_mod_600456.py --go
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
B = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(io.open(os.path.join(B, 'cloud.json'), encoding='utf-8'))
BASE = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']
HDR = {'apikey': CFG['key'], 'Authorization': 'Bearer ' + CFG['key'],
       'Content-Type': 'application/json', 'Accept': 'application/json'}
CODE = '600456'
GO = '--go' in sys.argv


def arg(name, dflt):
    if name in sys.argv:
        i = sys.argv.index(name)
        if i + 1 < len(sys.argv):
            return int(sys.argv[i + 1])
    return dflt


SRC = arg('--src', 19)      # 被并入的（跑完删除）
DST = arg('--dst', 25)      # 接收的（保留）
H3 = arg('--h3', 0) or '风险矩阵'   # 源正文那个模块的标题，作为小节 h3

# 当前分段（成员用**当前编号**标识；顺序即目录顺序）
SEC_CUR = [
    ('投资核心', 'verdict', []),
    ('公司简介', None, [1, 2, 3, 4]),
    ('公司业务', None, [5, 6, 7, 8, 9]),
    ('公司营收', None, [10, 11, 12, 13, 14, 15, 16]),
    ('公司投资', None, [17, 18, 19]),
    ('公司链条', None, [20, 21, 22, 23, 24]),
    ('行业分析', None, [25]),
    ('供需分析', None, [26]),
    ('盈利预测', None, [27, 28]),
    ('企业评分', None, [29, 30, 31]),
]

TOTAL = sum(len(nos) for _, _, nos in SEC_CUR)
TOTAL_NEW = TOTAL - 1


def req(path, method='GET', body=None, prefer=None):
    h = dict(HDR)
    if prefer:
        h['Prefer'] = prefer
    r = urllib.request.Request(BASE + path, method=method, headers=h)
    if body is not None:
        r.data = json.dumps(body).encode('utf-8')
    with urllib.request.urlopen(r, timeout=90) as f:
        t = f.read().decode('utf-8')
    return json.loads(t) if t.strip() else None


def fetch_mods():
    rows, off = [], 0
    while True:
        b = req('wb_report_mods?select=id,no,seq,title,html&code=eq.%s'
                '&order=seq.asc&limit=1000&offset=%d' % (CODE, off))
        rows += b
        if len(b) < 1000:
            break
        off += 1000
    rows.sort(key=lambda x: int(x.get('no') or 0))   # ⚠️ no 是文本，字典序不可信
    return rows


def fix_xref(html, mapping):
    """单遍同时替换正文里的「模块 N」（顺序替换会级联错位）。"""
    def rep(m):
        n = int(m.group(2))
        return '%s%d' % (m.group(1), mapping.get(n, n))
    return re.sub(r'(模块\s*)(\d+)', rep, html or '')


def build_merged(dst_html, src_html, title):
    """把源正文规整后接到目标正文里 <p class="src"> 之前。"""
    parts = [p.strip() for p in re.split(r'\n\s*', (src_html or '').strip())
             if p.strip()]
    if not parts:
        raise SystemExit('源正文为空，拒绝执行')
    block = '<h3>%s</h3>\n    %s' % (title, '\n    '.join(parts))
    d = dst_html or ''
    i = d.find('<p class="src">')
    if i < 0:
        raise SystemExit('目标正文里找不到 <p class="src">，无法自动确定插入点')
    return d[:i].rstrip() + '\n    ' + block + '\n    ' + d[i:]


def main():
    now = int(time.time() * 1000)
    ts = time.strftime('%Y%m%d-%H%M%S')

    # ---------------------------------------------------------- 阶段 0
    print('=== 阶段 0 · 读库 ===')
    mods = fetch_mods()
    no_set = sorted(int(m['no']) for m in mods)
    src_row = next((m for m in mods if int(m['no']) == SRC), None)
    if len(mods) == TOTAL:
        assert no_set == list(range(1, TOTAL + 1)), '现有编号不是 1..%d' % TOTAL
        state = '源行仍在（首跑）'
    elif len(mods) == TOTAL_NEW:
        exp = [x for x in range(1, TOTAL + 1) if x != SRC]
        assert no_set == exp, '编号既不是 %d 个也未删源行：%s' % (TOTAL_NEW, no_set)
        state = '源行已删除（MCP 已执行，续跑）'
    else:
        raise SystemExit('模块数异常：%d（期望 %d 或 %d）' % (len(mods), TOTAL, TOTAL_NEW))
    byold = {int(m['no']): m for m in mods}
    assert DST in byold, '找不到目标模块 m%d' % DST
    print('  模块 %d 个 —— %s' % (len(mods), state))
    print('  源  m%d = %s  （%d 字符，图：%s）' % (
        SRC, src_row['title'] if src_row else '(已删)',
        len(src_row['html'] or '') if src_row else 0,
        ','.join(sorted(set(re.findall(r'data-chart="([^"]+)"',
                                       (src_row or {}).get('html') or '')))) or '无'))
    print('  目标 m%d = %s  （%d 字符）' % (
        DST, byold[DST]['title'], len(byold[DST]['html'] or '')))
    if src_row and H3 != src_row['title']:
        print('  ⚠️ 小节标题「%s」与源模块标题「%s」不同' % (H3, src_row['title']))

    # 快照（写库前必备份）
    rep0 = req('wb_reports?select=code,title,toc&code=eq.%s' % CODE)[0]
    snap = os.path.join(B, 'backup', '%s_pre_merge_m%d_into_m%d_%s.json'
                        % (CODE, SRC, DST, ts))
    os.makedirs(os.path.dirname(snap), exist_ok=True)
    io.open(snap, 'w', encoding='utf-8').write(json.dumps(
        {'code': CODE, 'at': now, 'report': rep0, 'mods': mods},
        ensure_ascii=False, indent=1))
    print('  快照 %s  %d B' % (os.path.basename(snap), os.path.getsize(snap)))

    # ---------------------------------------------------------- 阶段 1
    order = [x for x in range(1, TOTAL + 1) if x != SRC]
    OLD2NEW = {o: i + 1 for i, o in enumerate(order)}
    NEW2OLD = {v: k for k, v in OLD2NEW.items()}
    assert sorted(OLD2NEW.values()) == list(range(1, TOTAL_NEW + 1)), '映射未覆盖'
    assert OLD2NEW[DST] == DST - 1, '目标应恰好前移一位（m%d→m%d）' % (DST, DST - 1)

    print()
    print('=== 阶段 1 · 新老编号对照 ===')
    print('  %-4s %-6s %-4s %s' % ('新', '旧', '变化', '标题'))
    for n in range(1, TOTAL_NEW + 1):
        src = NEW2OLD[n]
        mark = '—' if src == n else '−%d' % (src - n)
        star = ''
        if src == DST:
            star = '   ★ 接收方（正文 = 原有 + 并入的「%s」）' % H3
        elif src == SRC:
            star = '   ✖ 已被并入 m%d'
        print('  %-4d %-6d %-4s %s%s' % (n, src, mark, byold[src]['title'], star))

    # ---------------------------------------------------------- 阶段 2
    print()
    print('=== 阶段 2 · 合并正文 ===')
    dst_html = byold[DST]['html'] or ''
    merged = build_merged(dst_html, (src_row or {}).get('html') or '', H3) \
        if src_row else None
    if merged:
        print('  目标 %d → %d 字符（+%d）' % (
            len(dst_html), len(merged), len(merged) - len(dst_html)))
        # 结构自检：h3 小节数、表格数、图槽数都不许减少
        for label, pat in (('h3 小节', r'<h3>'), ('表格', r'<table\b'),
                           ('图槽', r'data-chart='), ('风险卡', r'risk-item')):
            a = len(re.findall(pat, dst_html))
            b = len(re.findall(pat, merged))
            flag = '' if b >= a else '   ❌ 减少'
            print('    %-8s %d → %d%s' % (label, a, b, flag))
            assert b >= a, '%s 数量减少，拒绝执行' % label
    else:
        print('  （已跑过合并，正文无需再构造）')

    # ---------------------------------------------------------- 阶段 3
    print()
    print('=== 阶段 3 · 交叉引用改写 ===')
    plan, nchg = {}, 0
    for m in mods:
        o = int(m['no'])
        if o == SRC:
            continue
        base = merged if (o == DST and merged) else (m.get('html') or '')
        new = fix_xref(base, OLD2NEW)
        plan[o] = new
        if new != (m.get('html') or ''):
            nchg += 1
            print('  旧 m%-2d → 新 m%-2d  %s' % (
                o, OLD2NEW[o], ' '.join(re.findall(r'模块\s*\d+', m.get('html') or ''))
                or '(换正文)'))
    print('  需改写正文的模块：%d 个' % nchg)

    # ---------------------------------------------------------- 阶段 4
    print()
    print('=== 阶段 4 · 目录分段（%d 条）===' % len(SEC_CUR))
    secs = []
    for key, anchor, nos in SEC_CUR:
        mem = [x for x in nos if x != SRC]
        if not mem:
            if anchor:                   # 「投资核心」锚在页面顶部核心结论区，本就不含模块
                secs.append((key, anchor, mem))
                continue
            raise SystemExit('段「%s」被掏空，拒绝执行' % key)
        mem.sort(key=lambda x: OLD2NEW[x])
        newnos = [OLD2NEW[x] for x in mem]
        assert newnos == list(range(newnos[0], newnos[-1] + 1)), \
            '段「%s」新编号不连续：%s' % (key, newnos)
        secs.append((key, anchor, mem))
    allnew = sorted(n for _, _, mem in secs for n in [OLD2NEW[x] for x in mem])
    assert allnew == list(range(1, TOTAL_NEW + 1)), '分段覆盖有误：%s' % allnew

    TOC = []
    for key, anchor, mem in secs:
        a = anchor if anchor else 'm%d' % OLD2NEW[mem[0]]
        TOC.append({'anchor': a, 'text': key})
        print('  %-8s %-6s %s' % (a, key,
              '[%s]' % ', '.join('m%d' % OLD2NEW[x] for x in mem)))
    assert all(len(t) == 4 for t in [x['text'] for x in TOC]), '目录文案必须 4 字'

    oldtoc = [(x['anchor'], x['text']) for x in (rep0.get('toc') or [])]
    newtoc = [(x['anchor'], x['text']) for x in TOC]
    if oldtoc != newtoc:
        print('  toc 变化：')
        for i in range(max(len(oldtoc), len(newtoc))):
            a = oldtoc[i] if i < len(oldtoc) else ('-', '-')
            b = newtoc[i] if i < len(newtoc) else ('-', '-')
            if a != b:
                print('    #%d  %-8s %-6s   →   %-8s %s' % (i + 1, a[0], a[1], b[0], b[1]))
    else:
        print('  toc 无变化')

    if not GO:
        print()
        print('（干跑结束，加 --go 才真正写库）')
        return

    # ---------------------------------------------------------- 阶段 5
    print()
    print('=== 阶段 5 · 先落合并正文到目标模块 ===')
    if merged:
        req('wb_report_mods?id=eq.%s' % byold[DST]['id'], 'PATCH',
            {'html': merged, 'up': now})
        print('  %s 正文已更新（%d 字符）' % (byold[DST]['id'], len(merged)))
    else:
        print('  （跳过，之前已落）')

    # ---------------------------------------------------------- 阶段 6
    print()
    print('=== 阶段 6 · 删除源行 ===')
    if src_row is None:
        print('  源行已不存在 → 跳过 ✅')
    else:
        try:
            req('wb_report_mods?id=eq.%s' % src_row['id'], 'DELETE')
            print('  已删除 %s ✅' % src_row['id'])
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', 'replace')[:200]
            print('  ⚠️ REST 删除被拒：HTTP %s  %s' % (e.code, body))
            print()
            print('  ➜ 请用 MCP 删除这一行（把上面那条正文改动留在了库里，重入安全）：')
            print("     managePgDatabase(action='execute', confirm=true,")
            print("       sql=\"DELETE FROM public.wb_report_mods WHERE id = '%s'\")"
                  % src_row['id'])
            print()
            print('  删完后再跑一次本脚本 --go（会跳过删除、直接改号）。')
            sys.exit(2)

    # ---------------------------------------------------------- 阶段 7
    print()
    print('=== 阶段 7 · 升序改号（下移，天然不撞主键）===')
    done = 0
    for o in [x for x in order if x > SRC]:
        n = OLD2NEW[o]
        req('wb_report_mods?id=eq.%s_m%d' % (CODE, o), 'PATCH',
            {'id': '%s_m%d' % (CODE, n), 'no': str(n), 'seq': str(n),
             'html': plan[o], 'up': now})
        done += 1
        print('  m%-2d → m%-2d   %s' % (o, n, byold[o]['title']))
    print('  共改 %d 行' % done)

    # ---------------------------------------------------------- 阶段 8
    print()
    print('=== 阶段 8 · 重写目录 ===')
    req('wb_reports?id=eq.%s' % CODE, 'PATCH', {'toc': TOC, 'up': now})
    print('  toc 已写入 %d 条' % len(TOC))

    # ---------------------------------------------------------- 复核
    print()
    print('=== 复核 · 回读全量 ===')
    back = fetch_mods()
    ok = len(back) == TOTAL_NEW
    print('  模块数 %d（期望 %d）%s' % (len(back), TOTAL_NEW, '' if ok else '  ❌'))
    for i, m in enumerate(back):
        exp_no = i + 1
        src = NEW2OLD[exp_no]
        good = (int(m['no']) == exp_no and m['id'] == '%s_m%d' % (CODE, exp_no)
                and int(m['seq']) == exp_no and m['title'] == byold[src]['title'])
        if not good:
            ok = False
        print('  %2s %-12s %-34s %s' % (m['no'], m['id'], m['title'],
                                        '' if good else '❌'))
    got = [(x['anchor'], x['text']) for x in
           (req('wb_reports?select=toc&id=eq.%s' % CODE)[0]['toc'] or [])]
    print('  toc %d 条，与期望一致：%s' % (len(got), got == newtoc))
    if got != newtoc:
        ok = False
        print('    实际：%s' % got)
    # 合并断言：新 m{DST-1} 里必须同时含源内容与目标内容
    tgt = byold[DST]
    m_now = next(m for m in back if int(m['no']) == OLD2NEW[DST])
    has_src = 'risk-item' in (m_now['html'] or '') and H3 in (m_now['html'] or '')
    print('  新 m%-2d（%s）含并入内容（%s + %d 张风险卡）：%s' % (
        OLD2NEW[DST], m_now['title'], H3,
        len(re.findall(r'risk-item', m_now['html'] or '')), has_src))
    if not has_src:
        ok = False
    print()
    print('结论：%s' % ('全部通过 ✅' if ok else '存在不一致 ❌'))
    if not ok:
        sys.exit(1)


if __name__ == '__main__':
    main()
