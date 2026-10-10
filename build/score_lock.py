# -*- coding: utf-8 -*-
"""槽 29「企业评分」—— **冻结模块（LOCKED）**

────────────────────────────────────────────────────────────────────────
【用户指令】2026-09-22
    「企业评分的模块锁死，不要每次都改」

【为什么要这个文件】
  槽 29 此前**每做一家就重写一次**，线上留下了三种形态：
    · 母本 A 形（宝钛 600456，有分：环形卡 + 8 格 KPI + 十项带权重 + 逐项说明）
    · 母本 A 形 · 空分（贵研/恒邦/美丰/鲁西，由 _m29_unify.py 于 2026-09-21 统一）
    · 渲染器默认简表（2026-09-22 新建的五家，四列表 + 7 处 [MISSING]）← 偏离母本
  ⇒ 本文件是槽 29 的**唯一真源**。`report_build_v31.m29()` 只准调它，不准再自己拼。

【锁什么 / 不锁什么】
  ★ 锁死（改一个字都算破坏契约）：
      · 模块结构与 CSS 类名（score-hero / gauge / kv-grid / criteria / sc-line / sc-total）
      · 十项**项名**、**权重**、**加分项标记**（= 母本宝钛那套，权重合计恒为 100）
      · **空分形态**：环形卡灰环 + 「—/100」+ 徽标「待评分」；sc-val 恒为「—」；sc-bar 无 <i>
      · 「填写说明」整段文案
  ★ 不锁（由数据文件给，各家公司本就不同）：
      · KPI 卡 8 格的**取值**（市值 / PE / PB / 价格 / 最近报告期归母 · 扣非 · EPS / 报告日期）
      · 十项的逐项 `sc-note` **实测说明**（不给则整格省略，与恒邦一致）

【历史缺陷（本文件已修，勿带回）】
  `_m29_unify.py` 当年把加分项标记写成了**字面 `pos`**（`<em class="pos-em">pos</em>`），
  4 家存量页面上直接显示「pos」。母本用的是「加分项」⇒ 本文件固定为「加分项」。

【契约校验】`build/_probe_lock29.py`：sc-line == 10 条、项名+权重逐字相符、
  加分项文本 == 「加分项」、sc-val 全为「—」、pos-em 无 `pos` 字面。

【2026-09-22 追加：报告页的「动态调整」】用户令
  「模块29这里做成动态调整，改右边评分整个总评分要加权改动，以后所有的做的新研报也要都这样」。
  ⇒ 本文件依旧只管**渲染**，交互全在报告壳（`deploy/report.template.html` 的 `scoreLive` 段）：
     · `.sc-line[data-w]` 是本文件给壳读权重用的（旧渲染没有 ⇒ 壳退化成解析 `.sc-w` 文本）；
     · 总分 / 评级算法在壳里是**照抄**本文件的 `total_of` / `GRADES`
       ⇒ 改任一处必须同步另一处，否则页面与库对不上；
     · 壳里的调整只落浏览器 localStorage、不写库 ⇒ 不影响上面这份冻结契约。
"""
import io
import os
import re
import sys

LOCK_VERSION = 'exp-score-lock-v2'

#: 模块标题 —— 与 report_template_v31.py 第 131 行的 M(29, …) 必须逐字一致
TITLE = '企业评分（选股原则 10 项 · 满分 100）'

#: 十项选股原则 —— 冻结表（项名, 是否加分项, 权重%）。权重合计必须 == 100。
#: ★ 项名与加分项标记**逐字照抄母本宝钛 600456**（线上实测 2026-09-22）：
#:   · 加分项恰为 #1 股东 / #2 独一无二 / #5 主营集中 三项；
#:   · 归一家（贵研/恒邦/美丰/鲁西）当年把标记写错位（恒邦 #6–#10 全标），
#:     且「加分项」误写成字面 `pos` —— 现统一回母本。
ITEMS = [
    ('股东，央企或省国资委',            True,  10),
    ('独一无二，资本别无选择',          True,  14),
    ('产品持续大涨 > 100%',            False, 13),
    ('扣非净利润持续大涨 > 60%',        False, 14),
    ('主营集中 > 75%',                 True,   9),
    ('盈利模式简单清晰',               False,  8),
    ('总市值 < 200 亿',                False,  8),
    ('股价盘整 2-3 年充分吸收',          False,  9),
    ('股价位于月线底部区域',            False,  9),
    ('底部成交量开始显著放大',          False,  6),
]

#: KPI 卡 8 格 —— (键, 标签模板)。`{p}` = 报告期前缀（如 `2026H1`），空则省略前缀。
KPI = [
    ('mktcap', '总市值（亿元）'),
    ('pe',     'PE（TTM，倍）'),
    ('pb',     'PB（MRQ，倍）'),
    ('price',  '当前价格（元）'),
    ('np',     '{p}归母净利'),
    ('npdx',   '{p}扣非净利'),
    ('eps',    '{p} EPS'),
    ('date',   '报告日期'),
]

BLANK = '—'
BADGE = '待评分'

#: 未评分项参与总分的基准分 —— 与 `score_engine.NEUTRAL`、报告壳的 `SC_NEUTRAL`
#: （deploy/report.template.html 的 scoreLive 段）三处**必须同值**，否则
#: 「页面动态调整算出来的总分」与「后端引擎算出来的」会不是一回事。
NEUTRAL = 6

#: 评级档位 —— 按母本单点校准（母本 70.5 分 ⇒ 「观察」）。
#: ★ 本表是**唯一真源**，`score_engine` 从这里 import 使用。
GRADES = [
    (85, '重点看好'),
    (75, '看好'),
    (65, '观察'),
    (55, '谨慎'),
    (0,  '回避'),
]


def grade_of(total):
    """加权总分 → 评级档位。"""
    for lo, name in GRADES:
        if total >= lo:
            return name
    return GRADES[-1][1]


def total_of(scores):
    """母本公式：总分 = Σ（单项评分 × 权重）× 10。"""
    assert len(scores) == 10, scores
    return round(sum(s * w for s, (_, _, w) in zip(scores, ITEMS)) * 10 / 100, 1)


FILL_SRC = (
    '<p class="src" style="margin-top:12px;">'
    '<b>填写说明：</b>本项为企业评分（十项选股原则 · 单项满分 10 分 · 满分 100）。'
    '<b>本轮分数留空、待填写</b>。计算口径：总分 = Σ（单项评分 × 权重）× 10 —— '
    '把十项得分填入后，环形卡刻度与「加权总分」同步更新。'
    '<b>项名与权重按母本（宝钛股份 600456）固定，请勿改动</b>；'
    '客观指标见上方指标卡，财务与行情口径见对应模块。'
    '评分属定性判断，仅供参考，<b>不构成投资建议</b>。</p>'
)


def check_rubric():
    """冻结表自检。任何一项不满足即抛错 —— 让「被改坏了」在构建期就炸掉。"""
    errs = []
    if len(ITEMS) != 10:
        errs.append('十项原则应为 10 条，实为 %d 条' % len(ITEMS))
    tot = sum(w for _, _, w in ITEMS)
    if tot != 100:
        errs.append('权重合计应为 100，实为 %d' % tot)
    if len(KPI) != 8:
        errs.append('KPI 卡应为 8 格，实为 %d 格' % len(KPI))
    if any(t == 'pos' for _, t, _ in ITEMS):
        errs.append('项名里混进了历史缺陷 `pos`')
    if errs:
        raise AssertionError('[score-lock] 冻结表被破坏：' + '；'.join(errs))
    return True


def _esc(s):
    return (str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def _val(v):
    """空值统一成「—」；数字去掉多余的 .0。"""
    if v is None or v == '':
        return BLANK
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _eval_note(scores, total, rating):
    """母本形态的「评分说明」段 —— 自动点名主要得分项与扣分项。"""
    idx = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
    best = [i for i in idx if scores[i] >= 8][:3] or idx[:3]
    worst = [i for i in idx[::-1] if scores[i] <= 5][:2]

    def fmt(lst):
        return '、'.join('%s（第 %d 项，%d 分）' % (ITEMS[i][0], i + 1, scores[i])
                        for i in lst)
    s1 = ('主要得分项为<strong>%s</strong>' % fmt(best)) if best else ''
    s2 = ('；主要扣分项为<strong>%s</strong>' % fmt(worst)) if worst else ''
    return ('<p class="src" style="margin-top:12px;">'
            '<b>评分说明：</b>总分 = Σ（单项评分 × 权重）× 10，满分 100。'
            '%s%s。'
            '本表由<b>规则化评分引擎</b>依公开数据自动生成（判据见各项括注与图表口径），'
            '分数可复算、可追溯；评分属定性判断，'
            '<b>仅供参考，不构成投资建议</b>。</p>' % (s1, s2))


def render(kpi=None, period='', notes=None, scores=None, total=None, rating=None):
    """输出槽 29 的完整 html（母本 A 形）。

    kpi    : dict，键见 KPI（mktcap/pe/pb/price/np/npdx/eps/date）；缺项显示「—」
    period : 报告期前缀，如 '2026H1'；给则 KPI 标签变成「2026H1归母净利」
    notes  : 长度 10 的列表（可短，缺位视为空）—— 逐项实测说明，空串则该格省略
    scores : 长度 10 的列表；**不给即「空分」**（sc-val = `—`、进度条留空）。
             给数字则按母本规则出进度条（≥8 → hi、5–7 → mid、≤4 → low，宽度 = 分×10%）。
    total  : 加权总分；不给则由 scores 按母本公式算
    rating : 评级；不给则按母本档位表换算
    """
    check_rubric()
    kpi = kpi or {}
    notes = list(notes or [])
    scores = list(scores or [])

    graded = (len(scores) == 10
              and all(isinstance(s, (int, float)) for s in scores))
    if graded and total is None:
        total = total_of(scores)
    if graded and not rating:
        rating = grade_of(total)
    if not graded:
        total = None

    # —— KPI 卡 8 格 ——
    kvs = []
    for key, tmpl in KPI:
        label = tmpl.replace('{p}', period) if (period and '{p}' in tmpl) else \
            tmpl.replace('{p}', '').lstrip()
        kvs.append('        <div class="kv">\n'
                   '<div class="k">%s</div>\n'
                   '<div class="v">%s</div>\n'
                   '</div>' % (_esc(label), _esc(_val(kpi.get(key)))))
    kv_grid = '\n'.join(kvs)

    # —— 十项 sc-line ——
    # ⚠️ 无实测说明时**整格省略** sc-note（母本空分版就是这样）。
    #    .sc-line 是显式 grid-column/grid-row 定位，缺一个子元素不会散架 ——
    #    sc-w/sc-bar/sc-val 都是 grid-row:1/3 跨两行，照样居中。
    # ★ `data-w`（2026-09-22 加）：给报告壳的「动态调整」读权重用（见该文件 scoreLive 段）。
    #   旧渲染没有它，那边会退化成解析 `.sc-w` 的「10%」文本 —— 两条路都留着，
    #   是为了让线上已发布的 10 家（未重渲染）与新渲染的行为完全一致。
    lines = []
    for idx, (name, pos, wt) in enumerate(ITEMS):
        badge = '<em class="pos-em">加分项</em>' if pos else ''
        note = notes[idx] if idx < len(notes) else ''
        note_html = '\n<div class="sc-note">%s</div>' % _esc(note) if note else ''
        sc = scores[idx] if idx < len(scores) else None
        if graded and isinstance(sc, (int, float)):
            cls = 'hi' if sc >= 8 else ('mid' if sc >= 5 else 'low')
            bar = '<i class="%s" style="width:%d%%;"></i>' % (cls, int(round(sc * 10)))
            val = _val(sc)
        else:
            bar, val = '', BLANK
        lines.append(
            '      <div class="sc-line" data-w="%d">\n'
            '<div class="sc-no">%d</div>\n'
            '<div class="sc-name">%s%s</div>%s\n'
            '<div class="sc-w">%d%%</div>\n'
            '<div class="sc-bar">%s\n</div>\n'
            '<div class="sc-val">%s</div>\n'
            '</div>' % (wt, idx + 1, _esc(name), badge, note_html, wt, bar, val))
    sc_lines = '\n'.join(lines)

    # —— 环形卡 / 总分 / 徽标 / 说明段：空分与有分两态 ——
    date = _esc(_val(kpi.get('date')))
    if graded:
        pct = max(0.0, min(100.0, float(total)))
        pct_s = ('%.1f' % pct).rstrip('0').rstrip('.')
        gauge_bg = ('conic-gradient(#c8102e 0 %s%%, #f6e6e9 %s%% 100%%)' % (pct_s, pct_s))
        num = ('%.1f' % total).rstrip('0').rstrip('.')
        g_badge, g_sub = '评级 · %s' % _esc(rating or ''), \
            '参照选股原则 10 项 · 报告日 %s' % date
        tn, tt = num, '评级：%s' % _esc(rating or '')
        src = _eval_note(scores, total, rating)
    else:
        gauge_bg = 'conic-gradient(#e6e5e3 0 100%)'
        num = BLANK
        g_badge, g_sub = BADGE, '评分待填写 · 参照选股原则 10 项 · 报告日 %s' % date
        tn, tt = BLANK, BADGE
        src = FILL_SRC

    return (
        '<div class="score-hero">\n'
        '      <div class="gauge-wrap">\n'
        f'        <div class="gauge" style="background:{gauge_bg};">\n'
        '          <div class="gauge-in">\n'
        f'            <div class="gauge-num">{num}<small>/100</small></div>\n'
        '            <div class="gauge-label">加权总分</div>\n'
        f'            <div class="gauge-badge">{g_badge}</div>\n'
        '          </div>\n'
        '        </div>\n'
        f'        <div class="g-sub">{g_sub}</div>\n'
        '      </div>\n'
        f'      <div class="kv-grid">\n{kv_grid}\n      </div>\n'
        '    </div>\n'
        '    <div class="criteria">\n'
        '      <div class="criteria-head">十项选股原则评分'
        '<span>单项满分 10 分 · 按权重加权</span></div>\n'
        f'{sc_lines}\n'
        '      <div class="sc-total">\n'
        '<span class="tl">加权总分</span>\n'
        f'<span class="tn">{tn}</span>\n'
        '<span class="tu">/ 100</span>\n'
        f'<span class="tt">{tt}</span>\n'
        '</div>\n'
        '    </div>\n'
        f'    {src}'
    )


def kpi_from_fin(fin, sc=None):
    """从 fin / score 里凑出 KPI 卡 8 格。取不到就是「—」，绝不猜。

    ★ 取值优先级：``score.kpi``（数据侧显式给定，**线上已核实**）> fin / score.h1 推算。
      存量 9 家的 8 格取自线上原文，重算会引入漂移 ⇒ 必须让显式值覆盖推算值。
    """
    fin = fin or {}
    sc = sc or {}
    h1 = sc.get('h1') or {}
    base = {
        'mktcap': fin.get('mktcap'),
        'pe': fin.get('pe'),
        'pb': fin.get('pb'),
        'price': fin.get('price'),
        'np': h1.get('np'),
        'npdx': h1.get('npdx'),
        'eps': h1.get('eps'),
        'date': sc.get('date') or fin.get('asof'),
    }
    for k, v in (sc.get('kpi') or {}).items():
        if v not in (None, ''):
            base[k] = v
    return base


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    check_rubric()
    print('LOCK_VERSION =', LOCK_VERSION)
    print('冻结表自检：通过（10 项 · 权重合计 %d · KPI 8 格 · 加分项 %d 处）'
          % (sum(w for _, _, w in ITEMS), sum(1 for _, p, _ in ITEMS if p)))
    h = render(kpi={'mktcap': 152.98, 'pe': -31.79, 'pb': 1.37, 'price': 5.38,
                    'np': '1.16亿（+402.8%）', 'npdx': '1.06亿', 'eps': '0.04 元',
                    'date': '2026-09-22'},
               period='2026H1')
    print('空分样例 %d 字节' % len(h.encode('utf-8')))
    assert h.count('class="sc-line"') == 10
    assert h.count('pos-em') == sum(1 for _, p, _ in ITEMS if p) and '>pos<' not in h
    assert h.count('<div class="sc-val">—</div>') == 10
    # 有分形态（仅母本那种用法）
    h2 = render(scores=[9, 9, 5, 5, 10, 9, 6, 6, 7, 4], period='2026H1')
    assert '<i class="hi" style="width:90%;"></i>' in h2
    assert '<i class="mid" style="width:50%;"></i>' in h2
    assert '<i class="low" style="width:40%;"></i>' in h2
    assert '<div class="sc-val">10</div>' in h2
    # 幂等
    assert render(kpi={'mktcap': 152.98}, period='2026H1') == \
        render(kpi={'mktcap': 152.98}, period='2026H1')
    # ★ data-w：报告壳的「动态调整」靠它拿权重（线上旧渲染没有它时，
    #   那边退化成解析 `.sc-w` 的「10%」文本 —— 两条路都要对得上同一张冻结表）
    wts = [int(x) for x in re.findall(r'class="sc-line" data-w="(\d+)"', h)]
    assert wts == [w for _, _, w in ITEMS], wts
    assert h.count('data-w=') == 10 and h2.count('data-w=') == 10
    print('空分 / 有分 / 幂等 / 结构自检：通过（data-w %s）'
          % '/'.join(str(x) for x in wts))
