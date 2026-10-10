# -*- coding: utf-8 -*-
"""600456 结构性重排：十段式目录 + 29 → 31 模块。

用户诉求（2026-09-20）：
  目录「公司简介」上面加「投资核心」（指向页面顶部核心结论区，非模块）
  公司简介 = m1-m4；下面新增「公司业务」= m5-m8 + m12
  「营业收入」改名「公司营收」并下移到公司业务之后
  「在建工程」改名「公司投资」放在公司营收之后
  「产业链条」改名「公司链条」放在公司投资之后 = m9-m11 + m13-m15
  公司链条下面新增「行业分析」「供需分析」两个模块（素材取自发现报告）
  盈利预测 / 企业评分不动，整体顺延

新老编号映射（旧 → 新）：
  1-8   → 1-8      （不变）
  12    → 9        管理层与治理 → 公司业务
  19-24 → 10-15    财务六项 → 公司营收
  16-18 → 16-18    （不变）在建工程等 → 公司投资
  9-11  → 19-21    行业/需求/竞争 → 公司链条
  13-15 → 22-24    产业链/原料/价格 → 公司链条
  (25,26 空出)     → 新增 行业分析 / 供需分析
  25-29 → 27-31    盈利预测 / 估值 / 评分 / 多空 / 结论

⚠️ 三条铁律
  ① `id` 与 `no` 都必须改（id = `600456_m{N}` 是位置主键），且必须**两段式**：
     先把全部行改成临时值，再落到终值 —— 否则 m9 与 m19 互撞主键。
  ② 正文里的「模块 N」交叉引用必须**单遍同时**替换（正则回调），
     顺序替换会级联错位（把 25→27 之后又被 27→29 再改一次）。
  ③ 只动 wb_report_mods 与 wb_reports.toc，**不碰图表表**（图表靠 data-chart 键名挂载）。

用法：
  python build/restructure_600456.py           # 干跑，只打印计划
  python build/restructure_600456.py --go      # 真正写库

⚠️⚠️ 本脚本已于 2026-09-20 执行完毕（一次性，勿重跑）：
  库里现在已是 31 模块 / 十段目录，阶段 0 的 `len(mods) == 29` 断言会直接拦住它；
  别为了「跑通」去改断言。后续再做模块移位，请用 build/move_mod_600456.py
  （`--from N --after M`，通用、自带干跑与两段式改号）。
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

# ---------------------------------------------------------------- 映射
OLD2NEW = {
    1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8,          # 公司简介 / 公司业务前段
    12: 9,                                                    # 管理层与治理 → 公司业务
    19: 10, 20: 11, 21: 12, 22: 13, 23: 14, 24: 15,           # 财务六项 → 公司营收
    16: 16, 17: 17, 18: 18,                                   # 在建工程等 → 公司投资
    9: 19, 10: 20, 11: 21,                                    # 行业/需求/竞争 → 公司链条
    13: 22, 14: 23, 15: 24,                                   # 产业链/原料/价格 → 公司链条
    25: 27, 26: 28, 27: 29, 28: 30, 29: 31,                   # 盈利预测 / 估值 / 评分 / 多空 / 结论
}
NEW_SLOTS = [25, 26]          # 留给两个新模块

SECTIONS = [
    ('投资核心', 'verdict', None),
    ('公司简介', 'm1', [1, 2, 3, 4]),
    ('公司业务', 'm5', [5, 6, 7, 8, 9]),
    ('公司营收', 'm10', [10, 11, 12, 13, 14, 15]),
    ('公司投资', 'm16', [16, 17, 18]),
    ('公司链条', 'm19', [19, 20, 21, 22, 23, 24]),
    ('行业分析', 'm25', [25]),
    ('供需分析', 'm26', [26]),
    ('盈利预测', 'm27', [27, 28]),
    ('企业评分', 'm29', [29, 30, 31]),
]

EXPECT_TITLES = [
    '公司简介', '公司历史沿革', '股东结构', '实控人与集团背景', '业务及产品',
    '主要产品产能与技术', '主要产品产量与销量（量价拆分）', '主要子公司与基地',
    '管理层与治理', '公司营业收入与利润', '公司产品收入与毛利结构', '盈利能力与杜邦分解',
    '费用结构', '现金流与资产负债三表', '历年分红与股东回报',
    '在建工程与新项目', '护城河与竞争优势量化', '风险矩阵',
    '行业总览与市场空间', '下游需求结构拆解', '竞争格局与市场份额',
    '产业链结构', '上游原料价格', '产品价格与成本',
    '钛行业介绍与市场规模', '供需格局与平衡表',
    '盈利预测模型', '估值分析', '企业评分（选股原则 10 项 · 满分 100）',
    '多空论点对照', '投资结论与跟踪清单',
]

NEW_MODS = [
    (25, '钛行业介绍与市场规模', '_new_m25.html'),
    (26, '供需格局与平衡表', '_new_m26.html'),
]

TOC = [{'anchor': a, 'text': t} for t, a, _ in SECTIONS]


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


def get(path):
    return req(path)


def fetch_mods():
    rows, off = [], 0
    while True:
        b = get('wb_report_mods?select=id,no,seq,title,html&report_id=eq.%s'
                '&order=seq.asc&limit=1000&offset=%d' % (CODE, off))
        rows += b
        if len(b) < 1000:
            break
        off += 1000
    rows.sort(key=lambda x: int(x.get('no') or 0))   # ⚠️ no 是文本，字典序不可信
    return rows


def fix_xref(html, mapping):
    """单遍同时替换正文里的「模块 N」。"""
    def rep(m):
        n = int(m.group(2))
        return '%s%d' % (m.group(1), mapping.get(n, n))
    return re.sub(r'(模块\s*)(\d+)', rep, html or '')


def main():
    now = int(time.time() * 1000)
    mods = fetch_mods()
    print('=== 阶段 0 · 读库 ===')
    print('  现有模块 %d 个（id %s .. %s）' % (len(mods), mods[0]['id'], mods[-1]['id']))
    assert len(mods) == 29, '预期 29 个模块，实际 %d' % len(mods)

    olds = sorted(int(m['no']) for m in mods)
    assert olds == list(range(1, 30)), '现有编号不是 1..29：%s' % olds
    assert sorted(OLD2NEW) == olds, '映射源与现有编号不一致'
    tgt = sorted(OLD2NEW.values())
    assert tgt == [n for n in range(1, 32) if n not in NEW_SLOTS], \
        '映射目标应恰好覆盖 1..31 去掉 %s，实际 %s' % (NEW_SLOTS, tgt)

    print()
    print('=== 阶段 1 · 新老编号对照 ===')
    byold = {int(m['no']): m for m in mods}
    for n in range(1, 32):
        if n in NEW_SLOTS:
            print('  %2d  ← 新增：%s' % (n, next(t for no, t, _ in NEW_MODS if no == n)))
            continue
        src = [o for o, v in OLD2NEW.items() if v == n][0]
        mark = '' if src == n else '   ← 旧 m%d' % src
        print('  %2d  %s%s' % (n, byold[src]['title'], mark))

    print()
    print('=== 阶段 2 · 交叉引用改写 ===')
    plan = {}
    for m in mods:
        o = int(m['no'])
        new = fix_xref(m.get('html'), OLD2NEW)
        n_ref = len(re.findall(r'模块\s*\d+', m.get('html') or ''))
        if new != m.get('html'):
            print('  旧 m%-2d → 新 m%-2d  改写 %d 处「模块 N」' % (o, OLD2NEW[o], n_ref))
        plan[o] = new

    print()
    print('=== 阶段 3 · 目录（%d 条）===' % len(TOC))
    for x in TOC:
        print('  %-8s %s' % (x['anchor'], x['text']))
    assert all(len(t) == 4 for t, _, _ in SECTIONS), '目录文案必须 4 字'

    # 篇幅与覆盖自检
    covered = sorted(n for _, _, nos in SECTIONS if nos for n in nos)
    assert covered == sorted(OLD2NEW.values()) or covered == list(range(1, 32)), \
        '目录分段的模块覆盖有遗漏：%s' % covered

    if not GO:
        print()
        print('（干跑结束，加 --go 才真正写库）')
        return

    print()
    print('=== 阶段 4 · 两段式改号 ===')
    # 4.1 全部改成临时值（
    for m in mods:
        tmp = {'id': '%s_z%02d' % (CODE, int(m['no'])),
               'no': 'z%02d' % int(m['no']), 'seq': str(900 + int(m['no'])), 'up': now}
        req('wb_report_mods?id=eq.%s' % m['id'], 'PATCH', tmp)
    print('  第一段：%d 行 → 临时编号' % len(mods))
    state = os.path.join(B, '_restruct_state.json')
    io.open(state, 'w', encoding='utf-8').write(json.dumps(
        {'code': CODE, 'old2new': {str(k): v for k, v in OLD2NEW.items()}, 'at': now},
        ensure_ascii=False, indent=1))

    # 4.2 落到终值（含正文改写）
    for m in mods:
        o = int(m['no'])
        n = OLD2NEW[o]
        body = {'id': '%s_m%d' % (CODE, n), 'no': str(n), 'seq': str(n),
                'html': plan[o], 'up': now}
        req('wb_report_mods?id=eq.%s_z%02d' % (CODE, o), 'PATCH', body)
    print('  第二段：%d 行 → 终值（并入正文改写）' % len(mods))

    print()
    print('=== 阶段 5 · 写入两个新模块 ===')
    rows = []
    for no, title, fn in NEW_MODS:
        html = io.open(os.path.join(B, fn), encoding='utf-8').read().strip()
        rows.append({'id': '%s_m%d' % (CODE, no), 'report_id': CODE, 'code': CODE,
                     'seq': str(no), 'no': str(no), 'title': title, 'html': html, 'up': now})
        print('  m%-2d %-18s %6d 字符' % (no, title, len(html)))
    req('wb_report_mods', 'POST', rows, prefer='return=representation')

    print()
    print('=== 阶段 6 · 重写目录 ===')
    req('wb_reports?id=eq.%s' % CODE, 'PATCH', {'toc': TOC, 'up': now})
    print('  toc 已写入 %d 条' % len(TOC))

    print()
    print('=== 复核 · 回读全量 ===')
    back = fetch_mods()
    ok = True
    print('  模块数 %d（期望 31）' % len(back))
    if len(back) != 31:
        ok = False
    for i, m in enumerate(back):
        exp_no = i + 1
        exp_id = '%s_m%d' % (CODE, exp_no)
        bad = (int(m['no']) != exp_no or m['id'] != exp_id or int(m['seq']) != exp_no or
               m['title'] != EXPECT_TITLES[i])
        if bad:
            ok = False
        print('  %2s %-12s %-30s %s' % (m['no'], m['id'],
                                        m['title'][:28], '❌' if bad else ''))
    r = get('wb_reports?select=toc&id=eq.%s' % CODE)[0]
    got = [(x['anchor'], x['text']) for x in (r['toc'] or [])]
    exp = [(x['anchor'], x['text']) for x in TOC]
    print('  toc %d 条，与期望一致：%s' % (len(got), got == exp))
    if got != exp:
        ok = False
        print('    实际：%s' % got)
    print()
    print('结论：%s' % ('全部通过 ✅' if ok else '存在不一致 ❌'))
    if not ok:
        sys.exit(1)


if __name__ == '__main__':
    main()
