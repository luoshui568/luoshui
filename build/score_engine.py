# -*- coding: utf-8 -*-
"""槽 29「企业评分」—— **自动评分引擎（唯一真源）**

────────────────────────────────────────────────────────────────────────
【用户指令】2026-09-22
    「m29 以后都用母本形态，帮我按照母本给的评分标准自动评分，全部补全」

【母本标准（宝钛 600456，线上实测原文）】
  总分 = Σ（单项评分 × 权重）× 10，满分 100。
  单项满分 10 分。母本实测 [9,9,5,5,10,9,6,6,6,6] → 7.05 × 10 = **70.5** ✅
  分数分布透露的隐含刻度（本引擎照此校准）：
      · 条件「强满足」            → 9~10
      · 条件「满足」              → 7~8
      · 「不满足但无重大缺陷」/中性 → **6**（母本 4 项给了 6）
      · 明确不利                  → 5（母本 #3/#4 均为 5）
      · 严重不利                  → 4（母本未用到，留作下限）
  母本 #3 产品价格同比 −9.4% ⇒ 5；#4 连续两期负增长 ⇒ 5 ——
  **母本不给人极低分，最低 5**，本引擎遵守这条刻度。

【设计原则】
  ① **可追溯**：每一项分数都由一个可核的客观量推出，判据写在 `judge_*` 里，
     实测值写进 `sc-note`（母本形态：分数 + 实测说明）。
  ② **不编造**：取不到数据 ⇒ 该项给中性分 6，并在 note 里显式写「未取到」，
     绝不猜一个好看的数。
  ③ **算法不进渲染器**：本文件在构建数据时被 `_score_run.py` 调用，
     结果**落成字面量**写进数据文件；`score_lock.render()` 仍只负责渲染。
     ⇒ 「锁死」与「自动评分」互不侵蚀。

【冻结表来源】项名 / 权重 / 加分项一律 `from score_lock import ITEMS`，
  本文件不得自带第二份。
"""
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score_lock import ITEMS  # noqa: E402  —— 项名/权重/加分项的唯一真源

ENGINE_VERSION = 'exp-score-engine-v1'

#: 评级档位（母本 70.5 → 「观察」，此处按母本单点校准）
GRADES = [
    (85, '重点看好'),
    (75, '看好'),
    (65, '观察'),
    (55, '谨慎'),
    (0,  '回避'),
]

NEUTRAL = 6          # 中性基准 —— 取不到数据时用它，并在 note 里说明
FLOOR = 4            # 分数下限


def grade_of(total):
    for lo, name in GRADES:
        if total >= lo:
            return name
    return GRADES[-1][1]


def total_of(scores):
    """母本公式：Σ(分×权重)×10。权重为百分数。"""
    assert len(scores) == 10, scores
    return round(sum(s * w for s, (_, _, w) in zip(scores, ITEMS)) * 10 / 100, 1)


def _f(v):
    """宽松转 float；失败返回 None。"""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(',', '').replace('%', '').replace('，', '')
    s = s.replace('−', '-').replace('＋', '+')          # 全角符号
    m = re.search(r'[-+]?\d+(?:\.\d+)?', s)
    return float(m.group(0)) if m else None


def _fmt(v, nd=2):
    """数值 → 千分位串。**必须过这道** —— 源数据里偶有 `1.442e+04` 这类
    科学计数法（12,000+ 的报价一多就会撞上），直接上页面读者无法读。
    非数值或空值原样/破折号返回。"""
    x = _f(v)
    if x is None:
        return str(v) if v not in (None, '') else '—'
    s = format(x, ',.%df' % nd)
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    return s


# ─────────────────────────────────────────────────────────── 逐项判据
# 每个 judge_* 返回 (分数, note)。note 为 sc-note 的正文（母本形态）。
# ---------------------------------------------------------------------

def judge1_owner(own):
    """#1 股东，央企或省国资委 —— 央企 10 / 省国资 9 / 市国资 7 / 参股 6 / 无 4。"""
    kind = (own or {}).get('kind') or ''
    desc = (own or {}).get('desc') or ''
    # ★ 括号只在 kind 本身没写明层级时才加 —— 否则会出现「省属国资（省属国资）」。
    def _tag(base):
        return kind if kind.endswith('国资') else '%s（%s）' % (kind, base)
    if '国务院' in kind or '中央' in kind:
        sc, tag = 10, '国务院国资委（中央企业）'
    elif '省' in kind:
        sc, tag = 9, _tag('省属国资')
    elif '市' in kind or '县' in kind:
        sc, tag = 7, _tag('地方国资')
    elif '自然人' in kind or '民营' in kind:
        sc, tag = 4, '自然人（非国资）'
    elif '国资' in kind or '国有' in kind:
        sc, tag = 6, '%s（国资参股/非控股）' % kind
    elif kind and kind != '未知':
        sc, tag = 4, '%s' % kind
    else:
        sc, tag = NEUTRAL, '未取到'
    if desc:
        return sc, '最终控制人为%s：%s' % (tag, desc)
    return sc, '最终控制人为%s；%s' % (tag, '（股权链条未取到）' if not desc else desc)


def judge2_moat(moat):
    """#2 独一无二，资本别无选择 —— 按壁垒「强」的条数与唯一性表述。"""
    strong = int((moat or {}).get('n_strong') or 0)
    weak = int((moat or {}).get('n_weak') or 0)
    uniq = (moat or {}).get('unique_words') or []
    ev = (moat or {}).get('evidence') or ''
    if strong >= 2:
        sc = 9
    elif strong == 1:
        sc = 8
    elif weak >= 2:
        sc = 5
    else:
        sc = 6
    tail = ''
    if uniq:
        tail = ('具备「%s」类地位表述' % '、'.join(uniq[:3]))
    if ev:
        return sc, '%s%s' % (ev, ('；' + tail) if tail else '')
    return sc, '壁垒强度：强 %d 项、弱 %d 项%s' % (strong, weak,
                                              ('；' + tail) if tail else '')


def judge3_price(pr):
    """#3 产品持续大涨 >100% —— 核心产品价格同比。"""
    yoy = _f((pr or {}).get('yoy'))
    name = (pr or {}).get('name') or '核心产品'
    lo = (pr or {}).get('last') or ''
    hi = (pr or {}).get('prev') or ''
    if yoy is None:
        return NEUTRAL, ('%s价格同比未取到（缺少可比两期报价），'
                         '本项给中性基准 %d 分。' % (name, NEUTRAL))
    if yoy > 100:
        sc = 10
    elif yoy > 50:
        sc = 8
    elif yoy > 20:
        sc = 7
    elif yoy >= 0:
        sc = 6
    else:
        sc = 5
    if yoy < 0:
        verdict = '方向向下，未出现 100% 级涨价'
    elif yoy < 20:
        verdict = '小幅上涨，未达 100% 级'
    elif yoy < 100:
        verdict = '涨幅显著但未达 100% 级'
    else:
        verdict = '出现 100% 级以上持续涨价'
    # ⚠️ `prev` 已是带月份/口径的文字串（如「2025 年（全年均价） 7,092」），
    #    **不能再过一遍 _fmt** —— 那会把开头的 2025 当成数字压成「2,025」。
    txt = '%s最新 %s、上期 %s' % (name, _fmt(lo), hi or '—')
    cal = (pr or {}).get('caliber') or ''
    # ★ 措辞跟着口径走：`ex_price` 只在**退化成首末值比较**时才给 caliber
    #   ⇒ 有 caliber = 不是严格同比，写「变化」；无 caliber = 精确同月同比。
    word = '变化' if cal else '同比'
    return sc, '%s，%s %+.1f%%——%s。%s' % (
        txt, word, yoy, verdict, ('（%s）' % cal) if cal else '')


def judge4_profit(pf):
    """#4 扣非净利润持续大涨 >60%。pf: {'series':[{y,val,yoy}], 'basis':'扣非'|'归母'}"""
    ser = [x for x in ((pf or {}).get('series') or []) if x.get('yoy') is not None]
    basis = (pf or {}).get('basis') or '归母'
    if not ser:
        return NEUTRAL, ('净利润同比序列未取到，本项给中性基准 %d 分（口径：%s净利）。'
                         % (NEUTRAL, basis))
    last2 = ser[-2:]
    big = [x for x in last2 if x['yoy'] > 60]
    if len(big) == 2:
        sc = 10
    elif len(big) == 1:
        sc = 8
    elif ser[-1]['yoy'] > 10:
        sc = 7
    elif ser[-1]['yoy'] >= 0:
        sc = 6
    else:
        sc = 5
    parts = []
    for x in last2:
        if x.get('val') is None:
            continue
        vy = x['yoy']
        if vy is None:
            parts.append('%s %s 亿元' % (x['y'], x['val']))
        elif abs(vy) > 200:      # 由盈转亏/扭亏：百分比失去意义，改自然表述
            parts.append('%s %s 亿元（%s）'
                         % (x['y'], x['val'], '由盈转亏' if x['val'] < 0 else '扭亏为盈'))
        else:
            parts.append('%s %s 亿元（%+.1f%%）' % (x['y'], x['val'], vy))
    neg = sum(1 for x in last2 if x['yoy'] < 0)
    if sc == 5:
        verdict = ('连续两期负增长，拐点未现' if neg == 2 else '当期负增长')
    elif sc == 6:
        verdict = '微增，未达 60% 级'
    elif sc == 7:
        verdict = '正增长但未达 60% 级'
    else:
        # ★ 必须点名是哪一期达标 —— 只写「达到 60% 级增长」会在另一期
        #   大幅下滑时（如鲁西 2024 +147.7% / 2025 −55.3%）产生误导。
        # ⚠️ 串里的 `60%` 必须写成 `60%%`，否则 `%` 会被当成格式符。
        yrs = [x['y'] for x in big]
        if len(big) == 2:
            verdict = '%s 连续两期达到 60%% 级增长' % '、'.join(yrs)
        else:
            verdict = '%s 达到 60%% 级增长，最近一期未达' % yrs[0]
    return sc, '%s净利 %s；%s。' % (basis, '、'.join(parts) or '—', verdict)


def judge5_focus(bz):
    """#5 主营集中 >75% —— 第一大板块收入占比。"""
    pct = _f((bz or {}).get('top_pct'))
    name = (bz or {}).get('top_name') or '第一大板块'
    if pct is None:
        return NEUTRAL, ('第一大板块收入占比未取到，本项给中性基准 %d 分。' % NEUTRAL)
    if pct >= 85:
        sc = 10
    elif pct >= 75:
        sc = 9
    elif pct >= 60:
        sc = 7
    elif pct >= 45:
        sc = 6
    else:
        sc = 5
    verdict = ('高度集中' if pct >= 85 else
               '超过 75% 门槛' if pct >= 75 else
               '未达 75% 门槛' if pct >= 45 else '较为分散')
    extra = (bz or {}).get('extra') or ''
    return sc, '%s收入占营业收入 %s，%s%s' % (
        name, ('%.2f%%' % pct), verdict, ('；' + extra) if extra else '。')


def judge6_model(bz):
    """#6 盈利模式简单清晰 —— 板块数与主导度。"""
    n = int((bz or {}).get('n_seg') or 0)
    pct = _f((bz or {}).get('top_pct'))
    if not n:
        return NEUTRAL, ('业务板块构成未取到，本项给中性基准 %d 分。' % NEUTRAL)
    if n <= 2 or (pct is not None and pct >= 70):
        sc = 9
    elif n == 3:
        sc = 8
    elif n == 4:
        sc = 7
    else:
        sc = 6
    note = (bz or {}).get('model_note') or ''
    head = '主营由 %d 个板块构成' % n
    if pct is not None and pct >= 70:
        head += '，第一大板块占收入 %.0f%%、主导性强' % pct
    return sc, '%s%s' % (head, ('；' + note) if note else '。')


def judge7_mktcap(fin):
    """#7 总市值 < 200 亿。"""
    mv = _f((fin or {}).get('mktcap'))
    date = (fin or {}).get('date') or ''
    if mv is None:
        return NEUTRAL, ('总市值未取到，本项给中性基准 %d 分。' % NEUTRAL)
    if mv < 50:
        sc = 8
    elif mv < 100:
        sc = 7
    elif mv < 200:
        sc = 6
    elif mv < 500:
        sc = 5
    else:
        sc = 4
    verdict = ('低于 200 亿元门槛' if mv < 200 else
               '超过 200 亿元门槛（%.0f 亿）' % mv)
    return sc, '总市值 %.2f 亿元（%s）——%s。' % (mv, date or '报告口径', verdict)


def judge8_range(mk):
    """#8 股价盘整 2-3 年充分吸收 —— 近 4 个完整年度：趋势 + 振幅 + 当前位置。

    ★ 母本刻度（宝钛）：箱体 24.19~35.62、振幅 47%，但 2025-12~2026-02 曾冲高
      45.40 元后单边回落，「上沿突破失败后筹码需重新沉淀」⇒ 母本给 **6**，不是 9。
      ⇒ 「有方向的长趋势」不是盘整 ⇒ 单调上行/下行一律降为 6。
      ⚠️ 年线粒度不足以判断「突破失败」，故不纳入判据（月线源恢复后可加）。
    """
    m = mk or {}
    amp = _f(m.get('amp36'))         # 近 4 个完整年度（高-低）/低
    pos = _f(m.get('pos36'))         # 现价在该区间的位置 0~1
    hi, lo = m.get('hi36'), m.get('lo36')
    trend = m.get('trend36') or 'flat'
    hi12 = _f(m.get('hi12_max'))     # 近 12 个月最高价（**只有月线源才给得出**）
    cal = m.get('caliber') or ''
    if amp is None or pos is None:
        return NEUTRAL, ('区间数据未取到，本项给中性基准 %d 分。' % NEUTRAL)
    broke = bool(hi and hi12 and hi12 > hi * 1.1)   # 上破箱体后回落 = 突破失败
    if broke:
        sc = 6
    elif trend in ('up', 'down'):
        sc = 6
    elif amp <= 0.5 and 0.15 <= pos <= 0.85:
        sc = 9
    elif amp <= 0.5:
        sc = 7
    elif amp <= 1.0:
        sc = 6
    else:
        sc = 5
    box = ('近 4 个完整年度收盘区间 %.2f~%.2f 元、振幅 %.0f%%'
           % (lo, hi, amp * 100)) if (hi and lo) else '近 4 年振幅 %.0f%%' % (amp * 100)
    tail = '当前价处区间 %.0f%% 分位' % (pos * 100)
    if broke:
        verdict = ('期间一度冲高至 %.2f 元、上沿突破失败后单边回落，'
                   '筹码需重新沉淀' % hi12)
    elif trend == 'down':
        verdict = '期间为单边下行趋势，尚未形成有效横盘'
    elif trend == 'up':
        verdict = '期间为单边上行趋势，谈不上盘整吸收'
    elif sc >= 9:
        verdict = '区间横向震荡、筹码吸收较充分'
    elif sc >= 6:
        verdict = '有震荡消化，但振幅偏大'
    else:
        verdict = '区间大起大落，未形成有效盘整'
    txt = '%s，%s——%s。' % (box, tail, verdict)
    return sc, (txt + '（%s）' % cal) if cal else txt


def judge9_bottom(mk):
    """#9 股价位于月线底部区域 —— 现价在近 6 个完整年度区间的位置。

    ★ 母本刻度（宝钛）：现价 25.25 元处 48 月区间 20.70~45.40 的约 22% 分位，
      PB 1.678 倍；母本判「属底部区域，未到绝对低位」⇒ **6**。
      ⇒ 只有真正贴近区间下缘（<15%）才给 9。
    """
    m = mk or {}
    pos = _f(m.get('pos48'))
    hi, lo = m.get('hi48'), m.get('lo48')
    pb = _f(m.get('pb'))
    cal = m.get('caliber') or ''
    if pos is None:
        return NEUTRAL, ('区间数据未取到，本项给中性基准 %d 分。' % NEUTRAL)
    if pos < 0.15:
        sc = 9
        verdict = '贴近区间下缘，属月线底部区域'
    elif pos < 0.55:
        sc = 6
        verdict = '属底部区域，未到绝对低位'
    elif pos < 0.75:
        sc = 5
        verdict = '处中位区间，底部特征不明显'
    else:
        sc = 4
        verdict = '仍在相对高位，距底部较远'
    seg = ('现价处近 6 个完整年度区间 %.2f~%.2f 元的 %.0f%% 分位'
           % (lo, hi, pos * 100)) if (hi and lo) else ('现价处近 6 年 %.0f%% 分位' % (pos * 100))
    pbtxt = ('，PB %.2f 倍' % pb) if pb is not None else ''
    txt = '%s%s——%s。' % (seg, pbtxt, verdict)
    return sc, (txt + '（%s）' % cal) if cal else txt


def judge10_volume(mk):
    """#10 底部成交量开始显著放大 —— 近 3 月均额 ÷ 此前 12 月均额。

    ★ 母本刻度（宝钛）：近 20 日 4.72 万手 vs 此前 20 日 6.10 万手（−22.6%），
      母本判「尚未放量」⇒ **6**（中性，不是扣分）。
      ⇒ 「没放大」= 6；只有真的放量才加分；极度萎缩才 5。
    """
    m = mk or {}
    ratio = _f(m.get('vol_ratio'))
    recent, base = m.get('vol_recent'), m.get('vol_base')
    cal = m.get('caliber') or ''
    if ratio is None:
        return NEUTRAL, ('量能数据未取到，本项给中性基准 %d 分。' % NEUTRAL)
    if ratio >= 1.8:
        sc = 9
    elif ratio >= 1.3:
        sc = 7
    elif ratio >= 0.5:
        sc = 6
    else:
        sc = 5
    # ⚠️ 单位是「亿元」且口径为**年度成交额**（年度末收盘序列的 fallback 口径）——
    #    写「最近一期」会被读成单日成交，故把口径写进文案。
    tail = ('最近一个完整年度成交额 %s 亿元、此前各年度均值 %s 亿元'
            % (_fmt(recent), _fmt(base))) if (recent is not None and base is not None) else \
        ('量能比 %.2f' % ratio)
    if ratio >= 1.3:
        verdict = '底部量能已开始显著放大'
    elif ratio >= 0.5:
        verdict = '尚未放量'
    else:
        verdict = '量能极度萎缩，底部换手信号未出现'
    txt = '%s，量能比 %.2f——%s。' % (tail, ratio, verdict)
    return sc, (txt + '（%s）' % cal) if cal else txt


# ───────────────────────────────────────────────────────── 主入口

def score(ctx):
    """ctx 见 _score_run.py 的抽取器；返回 dict(scores, notes, total, rating)。

    ctx = {
      'owner': {...}, 'moat': {...}, 'price': {...}, 'profit': {...},
      'focus': {...}, 'mktcap': {...}, 'market': {...},
    }
    """
    checks = [
        judge1_owner(ctx.get('owner')),
        judge2_moat(ctx.get('moat')),
        judge3_price(ctx.get('price')),
        judge4_profit(ctx.get('profit')),
        judge5_focus(ctx.get('focus')),
        judge6_model(ctx.get('focus')),
        judge7_mktcap(ctx.get('mktcap')),
        judge8_range(ctx.get('market')),
        judge9_bottom(ctx.get('market')),
        judge10_volume(ctx.get('market')),
    ]
    scores = [c[0] for c in checks]
    notes = [c[1] for c in checks]
    scores = [max(FLOOR, min(10, int(s))) for s in scores]
    tot = total_of(scores)
    return {'scores': scores, 'notes': notes, 'total': tot,
            'rating': grade_of(tot)}


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    # 用母本的实测输入回放，验证引擎能复现 70.5
    demo = {
        'owner': {'kind': '陕西省人民政府',
                  'desc': '陕西有色金属集团持宝钛集团 93.36%，宝钛集团持本公司 49.40%'},
        'moat': {'n_strong': 2, 'n_weak': 1, 'unique_words': ['唯一'],
                 'evidence': '壁垒强度：强 2 项、弱 1 项'},
        'price': {'name': '海绵钛(1#)', 'yoy': -9.4, 'last': '4.35 万元/吨',
                  'prev': '（上年同期）'},
        'profit': {'basis': '扣非', 'series': [
            {'y': '2024', 'val': 4.99, 'yoy': 5.1},
            {'y': '2025', 'val': 3.17, 'yoy': -36.6}]},
        'focus': {'top_name': '钛产品', 'top_pct': 85.99, 'n_seg': 3,
                  'extra': '其他金属产品占 7.85%'},
        'mktcap': {'mktcap': 123.5533, 'date': '2026-09-18'},
        'market': {'amp36': 0.47, 'pos36': 0.22, 'hi36': 35.62, 'lo36': 24.19,
                   'trend36': 'flat', 'hi12_max': 45.40,
                   'pos48': 0.22, 'hi48': 45.40, 'lo48': 20.70, 'pb': 1.68,
                   'vol_ratio': 0.77, 'vol_recent': 3.1, 'vol_base': 4.0},
    }
    r = score(demo)
    print('ENGINE_VERSION =', ENGINE_VERSION)
    for i, (s, n) in enumerate(zip(r['scores'], r['notes'])):
        print('  %2d %-22s %2d  %s' % (i + 1, ITEMS[i][0], s, n[:96]))
    print('加权总分 %.1f  评级 %s   （母本基准 70.5 / 观察）' % (r['total'], r['rating']))
