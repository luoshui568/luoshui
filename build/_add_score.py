# -*- coding: utf-8 -*-
"""给 5 家新报告的 _mk_*.py 注入 `D['score']`（槽 29 冻结模块的数据入口）。

【为什么】
  m29 已锁死为 build/score_lock.py 的薄壳，它只认 score.kpi / score.h1 /
  score.period / score.date / score.notes。这里把数据补上。

【逐项实测说明怎么来】
  槽 29 原来的简表有一列「实测值」（ROE / 毛利率 / 净现比 / 负债率 / 营收比 /
  每股股利 / ROIC−WACC），那是我按 fin 算的。锁成 A 形后这一列没了位置，
  会把信息丢掉 ⇒ 把这 7 条实测值写成 `sc-note`（母本 A 形本来就有这个位置）。
  ★ 说明是**数据**（每家不同），不是**模块**（结构/项名/权重锁死）。
  ★ 全部由 fin 现算后落成**字面量**注入脚本，渲染器里不留计算逻辑。

自检（缺一即停）：
  ① 幂等：脚本里已有 `D['score']` 即跳过
  ② notes 长度 == 10，且 ⑦⑧⑩（索引 6/7/9）必须为空串
  ③ 注入后 py_compile 通过
  ④ 注入点必须在 `dump(D)` 之前

用法：
    python _add_score.py          # 干跑
    python _add_score.py --go     # 落盘
"""
import io
import json
import os
import py_compile
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
SEED = os.path.join(HERE, 'seed')
DATE = '2026-09-22'

# 2026H1（iFinD 2026-06-30，合并报表 · 最新一期 MRQ）
H1 = {
    '603977': {'np': '0.98亿（-19.2%）', 'npdx': '0.90亿', 'eps': '0.16 元'},
    '601118': {'np': '-1.30亿（+25.9%）', 'npdx': '-2.89亿', 'eps': '-0.03 元'},
    '601958': {'np': '17.41亿（+25.9%）', 'npdx': '17.68亿', 'eps': '0.54 元'},
    '603599': {'np': '3.57亿（+1.8%）', 'npdx': '2.50亿', 'eps': '0.39 元'},
    '002408': {'np': '1.16亿（+402.8%）', 'npdx': '1.06亿', 'eps': '0.04 元'},
}
PERIOD = '2026H1'


def notes_from_fin(fin):
    """把原简表的「实测值」列改写成 10 条 sc-note（⑦⑧⑩ 无客观指标 ⇒ 留空）。"""
    y = fin.get('years') or ['2021', '2022', '2023', '2024', '2025']
    y0, yN = y[0], y[-1]
    f = lambda v, nd=2: ('%.*f' % (nd, v)) if isinstance(v, (int, float)) else '—'

    def last(lst):
        return next((v for v in reversed(lst or []) if v is not None), None)

    def avg(lst):
        vs = [v for v in (lst or []) if v is not None]
        return sum(vs) / len(vs) if vs else None

    rev, np_, ocf = fin.get('rev') or [], fin.get('np') or [], fin.get('ocf') or []
    roe, gm, lev = fin.get('roe') or [], fin.get('gm') or [], fin.get('lev') or []
    dps, roic = fin.get('dps') or [], fin.get('roic') or []
    wacc = fin.get('wacc')

    nc = None
    for i in range(len(np_) - 1, -1, -1):
        if np_[i] not in (None, 0) and i < len(ocf) and ocf[i] is not None:
            nc = ocf[i] / np_[i]
            break
    ratio = (rev[-1] / rev[0]) if (len(rev) >= 2 and rev[0]) else None
    roic_l, wacc_v = last(roic), wacc
    spread = (roic_l - wacc_v) if (roic_l is not None and wacc_v is not None) else None
    dps_l = last(dps)

    return [
        'ROE 加权 %s%%（%s 年）' % (f(last(roe)), yN),
        '近五年毛利率均值 %s%%（%s 年单年 %s%%；数据窗口 %s–%s）'
        % (f(avg(gm)), yN, f(last(gm)), y0, yN),
        '净现比 %s（%s 年：经营现金流 %s 亿 ÷ 归母 %s 亿）'
        % (f(nc), yN, f(ocf[-1] if ocf else None), f(np_[-1] if np_ else None)),
        '资产负债率 %s%%（%s 年末）' % (f(last(lev)), yN),
        '%s 年营收 %s 亿 → %s 年 %s 亿，比率 %sx'
        % (y0, f(rev[0] if rev else None), yN, f(rev[-1] if rev else None), f(ratio)),
        ('每股股利 %s 元（%s 年）' % (f(dps_l, 3), yN)) if dps_l not in (None, 0)
        else '近年未派现（%s 年每股股利 0 元）' % yN,
        '',   # ⑦ 行业地位 —— 需一手来源，留空
        '',   # ⑧ 管理层与治理 —— 需一手来源，留空
        '最近一年利差 %s pct（ROIC %s%% − WACC %s%%）'
        % (f(spread), f(roic_l), f(wacc_v, 1)),
        '',   # ⑩ 估值吸引力 —— 需历史 PE 分位，留空
    ]


def py_lit(s):
    return "'" + str(s).replace('\\', '\\\\').replace("'", "\\'") + "'"


def block_for(code):
    d = json.loads(io.open(os.path.join(SEED, 'data_v31_%s.json' % code),
                           encoding='utf-8').read())
    h1 = H1[code]
    notes = notes_from_fin(d.get('fin') or {})
    assert len(notes) == 10, code
    assert notes[6] == '' and notes[7] == '' and notes[9] == '', code
    L = ['# ---------------------------------------------------------------- 槽 29（冻结模块）数据',
         "# ★ 模块本身锁死在 build/score_lock.py：结构 / 十项项名 / 权重恒不变，得分留空。",
         "#   这里只给「数据」——KPI 卡 8 格取值 + 逐项实测说明（sc-note）。",
         "D['score'] = {",
         "    'period': %s," % py_lit(PERIOD),
         "    'date': %s," % py_lit(DATE),
         "    'h1': {'np': %s, 'npdx': %s, 'eps': %s}," % (
             py_lit(h1['np']), py_lit(h1['npdx']), py_lit(h1['eps'])),
         "    'notes': ["]
    for n in notes:
        L.append('        %s,' % py_lit(n))
    L += ['    ],', '}', '']
    return '\n'.join(L), notes


def main(go):
    rc = 0
    for code in ['603977', '601118', '601958', '603599', '002408']:
        p = os.path.join(HERE, '_mk_%s.py' % code)
        s = io.open(p, encoding='utf-8').read()
        if "D['score']" in s:
            print('%-7s 已有 D[score] —— 跳过（幂等）' % code)
            continue
        blk, notes = block_for(code)
        i = s.rfind('\ndump(D)')
        if i < 0:
            print('%-7s ✗ 找不到 dump(D) 注入点' % code)
            rc = 1
            continue
        new = s[:i + 1] + blk + s[i + 1:]
        print('%-7s 注入 %d 字节 | notes 10 条（留空 3 条：⑦⑧⑩）' % (code, len(blk.encode('utf-8'))))
        for k, n in enumerate(notes):
            if n:
                print('        %2d. %s' % (k + 1, n))
        if go:
            io.open(p, 'w', encoding='utf-8').write(new)
            py_compile.compile(p, doraise=True)
            print('        → 已落盘 + 编译通过 ✅')
    if not go:
        print('\n干跑结束（未落盘）。加 --go 落盘。')
    return rc


if __name__ == '__main__':
    sys.exit(main('--go' in sys.argv))
