# -*- coding: utf-8 -*-
"""600456 单模块移位：把某个模块整体挪到另一个模块的下面（后一个位置）。

用户诉求（2026-09-20 下午）：
  「帮我把 m24 移到目录公司营收的 m11 下面」
  ⇒ 身份 = 产品价格与成本（当前 m24，在「公司链条」段尾）
     目标 = 「公司营收」段内、m11（公司产品收入与毛利结构）之后

═══════════════════════════════════════════════════════════════════
⚠️ 三条铁律（与 restructure_600456.py 同源，理由见该文件头）
  ① `id` 与 `no` 必须同改，且**两段式**（先全量临时值 `z{old}`，再落终值）
     —— 直接改会在旧 m12 ↔ 新 m12 之间撞主键。
  ② 正文「模块 N」交叉引用必须**单遍同时**替换（正则回调），顺序替换会级联错位。
  ③ `seq` 跟 `no` 一起改；**图表完全不参与**（靠 `data-chart` 键名挂载，移位零风险）。
═══════════════════════════════════════════════════════════════════

分段（当前编号）—— 移位后各段成员按新位置重排，锚点 = 段内新位置最小的那个模块：
  投资核心(verdict) / 公司简介 1-4 / 公司业务 5-9 / 公司营收 10-15 /
  公司投资 16-18 / 公司链条 19-24 / 行业分析 25 / 供需分析 26 /
  盈利预测 27-28 / 企业评分 29-31

用法：
  python build/move_mod_600456.py                 # 干跑（默认 --from 24 --after 11）
  python build/move_mod_600456.py --from 24 --after 11 --go
"""
import io
import json
import os
import re
import sys
import time
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


MOVE_FROM = arg('--from', 24)      # 被移动的身份（按当前编号）
MOVE_AFTER = arg('--after', 11)    # 移到这个身份之后

# 当前分段（成员用**当前编号**标识；顺序即目录顺序）
SEC_CUR = [
    ('投资核心', 'verdict', []),
    ('公司简介', None, [1, 2, 3, 4]),
    ('公司业务', None, [5, 6, 7, 8, 9]),
    ('公司营收', None, [10, 11, 12, 13, 14, 15]),
    ('公司投资', None, [16, 17, 18]),
    ('公司链条', None, [19, 20, 21, 22, 23, 24]),
    ('行业分析', None, [25]),
    ('供需分析', None, [26]),
    ('盈利预测', None, [27, 28]),
    ('企业评分', None, [29, 30, 31]),
]

TOTAL = sum(len(nos) for _, _, nos in SEC_CUR)


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


def main():
    now = int(time.time() * 1000)
    ts = time.strftime('%Y%m%d-%H%M%S')

    # ---------------------------------------------------------- 阶段 0
    print('=== 阶段 0 · 读库 ===')
    mods = fetch_mods()
    assert len(mods) == TOTAL, '预期 %d 个模块，实际 %d' % (TOTAL, len(mods))
    olds = sorted(int(m['no']) for m in mods)
    assert olds == list(range(1, TOTAL + 1)), '现有编号不是 1..%d：%s' % (TOTAL, olds)
    byold = {int(m['no']): m for m in mods}
    print('  模块 %d 个，编号 1..%d 连续 ✅' % (len(mods), TOTAL))
    print('  源  m%d = %s' % (MOVE_FROM, byold[MOVE_FROM]['title']))
    print('  目标 m%d = %s 之后' % (MOVE_AFTER, byold[MOVE_AFTER]['title']))

    # 快照（写库前必备份）
    snap = os.path.join(B, 'backup', '%s_pre_move_m%d_%s.json' % (CODE, MOVE_FROM, ts))
    os.makedirs(os.path.dirname(snap), exist_ok=True)
    rep0 = req('wb_reports?select=code,title,toc&code=eq.%s' % CODE)[0]
    io.open(snap, 'w', encoding='utf-8').write(json.dumps(
        {'code': CODE, 'at': now, 'report': rep0, 'mods': mods},
        ensure_ascii=False, indent=1))
    print('  快照 %s  %d B' % (os.path.basename(snap), os.path.getsize(snap)))

    # ---------------------------------------------------------- 阶段 1
    order = list(range(1, TOTAL + 1))
    order.remove(MOVE_FROM)
    order.insert(order.index(MOVE_AFTER) + 1, MOVE_FROM)
    OLD2NEW = {o: i + 1 for i, o in enumerate(order)}
    NEW2OLD = {v: k for k, v in OLD2NEW.items()}
    tgt = sorted(OLD2NEW.values())
    assert tgt == list(range(1, TOTAL + 1)), '映射目标未覆盖 1..%d' % TOTAL

    print()
    print('=== 阶段 1 · 新老编号对照 ===')
    for n in range(1, TOTAL + 1):
        src = NEW2OLD[n]
        mark = '' if src == n else '   ← 旧 m%d' % src
        print('  %2d  %-34s%s' % (n, byold[src]['title'], mark))

    # ---------------------------------------------------------- 阶段 2
    print()
    print('=== 阶段 2 · 交叉引用改写（预览）===')
    plan, nchg = {}, 0
    for m in mods:
        o = int(m['no'])
        new = fix_xref(m.get('html'), OLD2NEW)
        plan[o] = new
        if new != (m.get('html') or ''):
            nchg += 1
            print('  旧 m%-2d → 新 m%-2d  %s' % (
                o, OLD2NEW[o], ' '.join(re.findall(r'模块\s*\d+', m.get('html') or ''))))
    print('  需改写正文的模块：%d 个' % nchg)
    if not nchg:
        print('  （本次移动不影响任何被引用的模块号 → 正文零改动）')

    # ---------------------------------------------------------- 阶段 3
    print()
    print('=== 阶段 3 · 目录分段（%d 条）===' % len(SEC_CUR))
    secs = []
    for key, anchor, nos in SEC_CUR:
        mem = [x for x in nos if x != MOVE_FROM]
        if MOVE_AFTER in mem:
            mem = mem[:mem.index(MOVE_AFTER) + 1] + [MOVE_FROM] + mem[mem.index(MOVE_AFTER) + 1:]
        if not mem:
            if anchor:                   # 「投资核心」锚在页面顶部核心结论区，本就不含模块
                secs.append((key, anchor, mem))
                continue
            raise SystemExit('段「%s」被掏空，拒绝执行' % key)
        mem.sort(key=lambda x: OLD2NEW[x])          # 按新位置重排
        secs.append((key, anchor, mem))
    for key, anchor, mem in secs:
        if not mem:                      # 「投资核心」不含模块，跳过连续性检查
            continue
        newnos = [OLD2NEW[x] for x in mem]
        # 段内新编号必须连续
        assert newnos == list(range(newnos[0], newnos[-1] + 1)), \
            '段「%s」新编号不连续：%s' % (key, newnos)
    # 全段拼接必须恰好覆盖 1..TOTAL
    allnew = sorted(n for _, _, mem in secs for n in [OLD2NEW[x] for x in mem])
    assert allnew == list(range(1, TOTAL + 1)), '分段覆盖有误：%s' % allnew

    TOC = []
    for key, anchor, mem in secs:
        a = anchor if anchor else 'm%d' % OLD2NEW[mem[0]]
        TOC.append({'anchor': a, 'text': key})
        print('  %-8s %-6s %s' % (a, key,
              '[%s]' % ', '.join('m%d' % OLD2NEW[x] for x in mem)))
    assert all(len(t) == 4 for _, t in [(x['anchor'], x['text']) for x in TOC]), '目录文案必须 4 字'

    oldtoc = [(x['anchor'], x['text']) for x in (rep0.get('toc') or [])]
    newtoc = [(x['anchor'], x['text']) for x in TOC]
    if oldtoc != newtoc:
        print('  toc 变化：')
        for i, (a, b) in enumerate(zip(oldtoc, newtoc)):
            if a != b:
                print('    #%d  %-8s %s   →   %-8s %s' % (i + 1, a[0], a[1], b[0], b[1]))
    else:
        print('  toc 无变化')

    if not GO:
        print()
        print('（干跑结束，加 --go 才真正写库）')
        return

    # ---------------------------------------------------------- 阶段 4
    print()
    print('=== 阶段 4 · 两段式改号 ===')
    for m in mods:
        o = int(m['no'])
        req('wb_report_mods?id=eq.%s' % m['id'], 'PATCH',
            {'id': '%s_z%02d' % (CODE, o), 'no': 'z%02d' % o,
             'seq': str(900 + o), 'up': now})
    print('  第一段：%d 行 → 临时编号 z01..z%02d' % (len(mods), TOTAL))

    for m in mods:
        o = int(m['no'])
        n = OLD2NEW[o]
        req('wb_report_mods?id=eq.%s_z%02d' % (CODE, o), 'PATCH',
            {'id': '%s_m%d' % (CODE, n), 'no': str(n), 'seq': str(n),
             'html': plan[o], 'up': now})
    print('  第二段：%d 行 → 终值（并入正文改写）' % len(mods))

    # ---------------------------------------------------------- 阶段 5
    print()
    print('=== 阶段 5 · 重写目录 ===')
    req('wb_reports?id=eq.%s' % CODE, 'PATCH', {'toc': TOC, 'up': now})
    print('  toc 已写入 %d 条' % len(TOC))

    # ---------------------------------------------------------- 阶段 6
    print()
    print('=== 复核 · 回读全量 ===')
    back = fetch_mods()
    ok = len(back) == TOTAL
    print('  模块数 %d（期望 %d）%s' % (len(back), TOTAL, '' if ok else '  ❌'))
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
    # 位置断言：源模块必须正好落在目标之后
    adj = (OLD2NEW[MOVE_FROM] == OLD2NEW[MOVE_AFTER] + 1)
    print('  m%d（%s）现位于 #%d，紧随 m%d（#%d）之后：%s' % (
        MOVE_FROM, byold[MOVE_FROM]['title'], OLD2NEW[MOVE_FROM],
        MOVE_AFTER, OLD2NEW[MOVE_AFTER], adj))
    if not adj:
        ok = False
    print()
    print('结论：%s' % ('全部通过 ✅' if ok else '存在不一致 ❌'))
    if not ok:
        sys.exit(1)


if __name__ == '__main__':
    main()
