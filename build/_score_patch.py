# -*- coding: utf-8 -*-
"""槽 29「企业评分」—— 分值手术（唯一实现，Python 侧真源）

────────────────────────────────────────────────────────────────────────
【为什么要有这个文件】
用户令 2026-09-22：「这个数据改完要提交到数据库里去」。
槽 29 的十项分数原先只在报告页的浏览器内存/localStorage 里（不落库）。
现在要落库，就必须把「改了哪些字节」定义成**一个纯函数**，让两条路径产出完全相同的 HTML：

    报告页（JS）  scBuildHtml()  ┐
                                 ├─→ apply_scores(html, scores)  ─→ 写回 wb_report_mods.html
    落库脚本（PY） _score_commit ┘

【为什么不重跑 score_lock.render()】
`render()` 会**从零重建**整段 HTML：KPI 8 格要靠 `kpi_from_fin()` 重算（存量 10 家取自线上
原文，重算必漂移）、逐项 `sc-note` 要重新喂、母本 600456 还有手写的「来源/口径说明」段会被抹掉。
⇒ 落库只用**定点替换**：只动「分数/条宽/总分/环形/徽标/评级/评分说明段」，其余字节原样搬运。
这样 KPI、逐项说明、母本额外段落天然不动，也不存在「重渲染掉 40%」的风险。

【只动这 7 类（其余一个字节都不许变）】
  1) 10 条 `.sc-bar` 里的 `<i class hi|mid|low style width>`（空分态则该 tag 不存在／需插入）
  2) 10 个 `.sc-val` 的文本
  3) `.gauge` 的 style（conic-gradient 刻度）
  4) `.gauge-num`（`{总分}<small>/100</small>`）
  5) `.gauge-badge`（`评级 · X`）
  6) `.g-sub`（`参照选股原则 10 项 · 报告日 Y`，报告日从原文里抠，不重算）
  7) `.sc-total` 的 `.tn` / `.tt`，以及「评分说明／填写说明」那个 `p.src`

【★ 母本 600456 的既存笔误（2026-09-22 已修）】
线上母本第 10 项 `.sc-val` 文本曾是 `5`，但它的条宽是 `60%`、`.tn` 是 `70.5`、
`score_engine` 回放也是 `70.5` —— 三比一，判定 `.sc-val` 那格是手写笔误。
⇒ `parse_scores()` 遇到「按 .sc-val 算出的总分 ≠ 存储总分」时**改按条宽读**并给出 warn。
  该笔误已在那批写库时修正，现线上十项 = 条宽 = 总分 70.5，三者自洽；
  含笔误的旧快照留在 `_m29/600456.html.before_val5`，便于日后复查。

【★ 点名句「自洽即保留」规则（2026-09-22 定，Python / JS 两侧同源）】
评分说明段里「主要得分项为…。主要扣分项为…。」这一句，**不是无条件重写**：
  · 句中每处 `（第 N 项，S 分）` 都与当前该项分数相等 ⇒ 这句此刻就是准确的 ⇒ **一字不动**；
  · 有一处对不上（或压根没点名）⇒ 整句换成 `_eval_note` 的规范版。
为什么：母本 600456 那句是**手写**的 —— 点了 4 个得分项、项名写成人话
（「主营集中度（钛产品 86%）」），比机械版（点 3 项、项名是 rubric 判据原文
「主营集中 > 75%」、还漏掉第 6 项）更准确。无条件重写＝把好东西换成差东西。
⇒ 有了这条规则，10 家「按原分数再套一遍」全部**逐字节幂等**（不再有母本例外）。

【口径真源】总分 / 评级一律从 `score_lock` 取（`total_of` / `grade_of` / `GRADES` / `NEUTRAL`），
本文件**不许**再写第二份算法。
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import score_lock as SL               # noqa: E402

#: 评分说明段的开头标记（有分态）；空分态用的是「填写说明」
NOTE_MARK = '评分说明：</b>'
FILL_MARK = '填写说明：</b>'


# --------------------------------------------------------------------------- 取值

def f1(x):
    """总分/刻度的数字写法 —— 与 score_lock.render() 的 `('%.1f'%x).rstrip('0').rstrip('.')` 等价。"""
    x = float(x)
    return str(int(x)) if x == int(x) else '%.1f' % x


#: 点名句里每一项都写成「（第 N 项，S 分）」—— 用它核验这句是否与当前分数自洽
_PT = re.compile(r'（第\s*(\d+)\s*项[，,]\s*(-?\d+)\s*分）')


def note_consistent(body, scores):
    """点名句里点到的每一项，(项号, 分) 是否都等于当前分数。

    对得上 ⇒ 这句此刻就是准确的，**保留**（母本手写那句比机械版更准确）；
    对不上 / 一处都没点名 ⇒ False，交回规范版重算。
    """
    pts = _PT.findall(body)
    if not pts:
        return False
    for n, s in pts:
        i = int(n) - 1
        if not (0 <= i < 10) or int(s) != int(scores[i]):
            return False
    return True


def _txt(s):
    return re.sub(r'\s+', '', re.sub(r'<[^>]+>', '', s))


def parse_stored_total(html):
    """读 `.sc-total .tn` 的静态总分（页面没接管时用户看到的那个数）。取不到给 None。"""
    m = re.search(r'<span class="tn">(.*?)</span>', html, re.S)
    if not m:
        return None
    t = _txt(m.group(1))
    return float(t) if re.fullmatch(r'\d+(\.\d+)?', t) else None


def parse_scores(html, want_total=None):
    """从模块 HTML 反解十项分数。

    返回 (scores, source, warn)：
      source = 'val'  —— 按 `.sc-val` 文本（页面输入框看到的就是它）
      source = 'bar'  —— 按条宽（`width:N%` → N/10 分）
      source = None   —— 两边都读不出来
    ★ 判据：先按 `.sc-val` 算；若与存储总分对不上，再按条宽算；哪边对得上用哪边。
      两边都能读出但都跟存储总分对不上 ⇒ 仍用条宽，并 warn（宁可报出来也不静默）。
    """
    want_total = parse_stored_total(html) if want_total is None else want_total
    vals = re.findall(r'<div class="sc-val">(.*?)</div>', html, re.S)
    bars = re.findall(r'<div class="sc-bar">(.*?)</div>', html, re.S)

    v_scores = []
    for v in vals:
        t = _txt(v)
        v_scores.append(int(float(t)) if re.fullmatch(r'\d+(\.\d+)?', t) else None)
    b_scores = []
    for b in bars:
        m = re.search(r'width:\s*(\d+(?:\.\d+)?)%', b)
        b_scores.append(int(round(float(m.group(1)) / 10)) if m else None)

    ok_v = len(v_scores) == 10 and all(s is not None for s in v_scores)
    ok_b = len(b_scores) == 10 and all(s is not None for s in b_scores)
    warn = []

    def total_of(ss):
        return SL.total_of(ss)

    if ok_v and (want_total is None or abs(total_of(v_scores) - want_total) < 0.05):
        return v_scores, 'val', warn
    if ok_b and (want_total is None or abs(total_of(b_scores) - want_total) < 0.05):
        if ok_v:
            warn.append('`.sc-val` 算出的总分 %s ≠ 存储总分 %s ⇒ 改按条宽读（%s）'
                        % (total_of(v_scores), want_total, b_scores))
        return b_scores, 'bar', warn
    if ok_b:
        warn.append('`.sc-val` 与条宽都与存储总分 %s 对不上（val %s / bar %s）⇒ 按条宽读'
                    % (want_total, total_of(v_scores) if ok_v else '—',
                       total_of(b_scores)))
        return b_scores, 'bar', warn
    if ok_v:
        return v_scores, 'val', warn
    return None, None, warn


# --------------------------------------------------------------------------- 手术

def _bar_tag(s):
    cls = 'hi' if s >= 8 else ('mid' if s >= 5 else 'low')
    return '<i class="%s" style="width:%d%%;"></i>' % (cls, int(round(s * 10)))


def apply_scores(html, scores, total=None, rating=None):
    """把十项分数写进模块 HTML。返回 (新 html, 摘要 dict)。

    只动上面列的 7 类；KPI、逐项 sc-note、母本额外的「来源/口径说明」段一律原样保留。
    `data-w` 也不动（有就保留、没有也不补 —— 补了会改变线上存量 10 家的字节）。
    """
    assert len(scores) == 10, scores
    SL.check_rubric()
    total = SL.total_of(scores) if total is None else total
    rating = SL.grade_of(total) if not rating else rating
    num = f1(total)

    n_done = {'bar': 0, 'val': 0, 'note': 0}

    # 1) 10 条 .sc-bar：有 <i> 就原地换（保留它周围的空白），没有就插在开标签后
    it = iter(scores)

    def _bar(m):
        inner = m.group(2)
        tag = _bar_tag(next(it))
        if re.search(r'<i\b[^>]*>\s*</i>', inner):
            new_inner = re.sub(r'<i\b[^>]*>\s*</i>', tag, inner, count=1)
        else:
            new_inner = tag + inner
        n_done['bar'] += 1
        return m.group(1) + new_inner + m.group(3)

    html = re.sub(r'(<div class="sc-bar">)(.*?)(</div>)', _bar, html, flags=re.S)

    # 2) 10 个 .sc-val
    it = iter(str(s) for s in scores)

    def _val(m):
        n_done['val'] += 1
        return m.group(1) + next(it) + m.group(3)

    html = re.sub(r'(<div class="sc-val">)(.*?)(</div>)', _val, html, flags=re.S)

    # 3) 环形刻度
    html = re.sub(r'(<div class="gauge" style=")[^"]*(">)',
                  lambda m: m.group(1) + 'background:conic-gradient(#c8102e 0 %s%%, #f6e6e9 %s%% 100%%);'
                  % (num, num) + m.group(2), html, count=1)
    # 4) 环内数字
    html = re.sub(r'(<div class="gauge-num">).*?(<small>)',
                  lambda m: m.group(1) + num + m.group(2), html, count=1, flags=re.S)
    # 5) 徽标
    html = re.sub(r'(<div class="gauge-badge">).*?(</div>)',
                  lambda m: m.group(1) + '评级 · ' + rating + m.group(2), html, count=1, flags=re.S)
    # 6) 副标题：报告日从原文抠，不重算
    gs = re.search(r'<div class="g-sub">(.*?)</div>', html, re.S)
    if gs:
        d = re.search(r'报告日\s*(.+?)\s*$', re.sub(r'<[^>]+>', '', gs.group(1)))
        new_sub = ('参照选股原则 10 项 · 报告日 ' + d.group(1)) if d else '参照选股原则 10 项'
        html = re.sub(r'(<div class="g-sub">).*?(</div>)',
                      lambda m: m.group(1) + new_sub + m.group(2), html, count=1, flags=re.S)
    # 7) 底部总分 / 评级
    html = re.sub(r'(<span class="tn">).*?(</span>)',
                  lambda m: m.group(1) + num + m.group(2), html, count=1, flags=re.S)
    html = re.sub(r'(<span class="tt">).*?(</span>)',
                  lambda m: m.group(1) + '评级：' + rating + m.group(2), html, count=1, flags=re.S)

    # 8) 评分说明段 —— 刻意**不整段重写**（母本 600456 那段是手写措辞，重写等于偷换别人的话）：
    #    · 「填写说明」段（空分态）⇒ 分数已填，整段作废，换规范版；
    #    · 「评分说明」段（有分态）⇒ 分三种：
    #        ① 点名句与当前分数**自洽** ⇒ 一字不动（母本手写那句比机械版更准确）；
    #        ② 点名句存在但对不上 ⇒ 只换「主要得分项…。」这一句为规范版；
    #        ③ 没有点名句 ⇒ 在第一个句号后补一句规范版。
    #    ⇒ 因 ①，10 家按原分数复跑全部逐字节幂等；改了分则自动走 ② 重算。
    canon_inner = SL._eval_note(scores, total, rating)
    canon_inner = canon_inner[canon_inner.index('>') + 1:canon_inner.rindex('</p>')]
    sent_m = re.search(r'主要得分项为.*?。', canon_inner, re.S)
    sent = sent_m.group(0) if sent_m else ''

    def _note(m):
        n_done['note'] += 1
        open_tag, body = m.group('open'), m.group('body')
        if FILL_MARK in body:
            return open_tag + canon_inner + '</p>'
        if NOTE_MARK in body:
            if note_consistent(body, scores):
                return open_tag + body + '</p>'        # ① 自洽 ⇒ 原样保留
            if '主要得分项为' in body:
                body = re.sub(r'主要得分项为.*?。', lambda _m: sent or _m.group(0),
                              body, count=1, flags=re.S)   # ② 重算
            elif sent:
                body = re.sub(r'。', '。' + sent, body, count=1)   # ③ 补一句
            return open_tag + body + '</p>'
        return m.group(0)

    html = re.sub(r'(?P<open><p class="src"[^>]*>)(?P<body>.*?)</p>', _note, html, flags=re.S)
    if not n_done['note']:      # 没有 src 段（罕见形态）→ 追加一段，保证分数来源可追溯
        html = html + SL._eval_note(scores, total, rating)
        n_done['note'] = -1

    return html, {'total': total, 'rating': rating, 'num': num, 'counts': n_done}


# --------------------------------------------------------------------------- 自测

def selfcheck():
    """干跑自测：以线上 10 家原文为准（`_m29/`，由 _dump_m29.py 从线上抓）。

    ★ 幂等判据（本文件的核心正确性主张）：
      用「原文自己的分数」再过一遍手术 ⇒ 10 家必须**全部逐字节不变**。
      （2026-09-22 起母本 600456 也走这条 —— 见 note_consistent 的注释。）

    ★ 变分控制组（防「不动」退化成「什么都不做」）：
      把 600456 第 6 项 9 → 7 再跑，必须：
        · 第 6 条 sc-val / 条宽 / 总分 / 环形 / 徽标都跟着变；
        · 点名句被重算（原句说「第 6 项，9 分」，已不自洽 ⇒ 换成规范版）；
        · 新句自身自洽；对产出再套一次同分 ⇒ 逐字节幂等。
      没有这组，「什么都没做」也能拿满分。
    """
    here = os.path.dirname(os.path.abspath(__file__))
    d = os.path.join(here, '_m29')
    bad, warns = [], []
    print('%-8s %-6s %-8s %-8s %s' % ('code', '源', '存储总分', '复算总分', '幂等'))
    for code in ('600456', '600459', '002237', '000731', '000830',
                 '603977', '601118', '601958', '603599', '002408'):
        p = os.path.join(d, '%s.html' % code)
        if not os.path.exists(p):
            print('%-8s （缺 _m29/%s.html，先跑 _dump_m29.py）' % (code, code))
            continue
        h = io.open(p, encoding='utf-8').read()
        sc, src, w = parse_scores(h)
        for x in w:
            warns.append('%s: %s' % (code, x))
        if not sc:
            bad.append('%s 读不出十项分数' % code)
            print('%-8s RX     ❌ 读不出分数' % code)
            continue
        st = parse_stored_total(h)
        if st is not None and abs(SL.total_of(sc) - st) > 0.05:
            bad.append('%s 复算总分 %s ≠ 存储总分 %s' % (code, SL.total_of(sc), st))
        new, meta = apply_scores(h, sc)
        same = (new == h)
        if not same:
            diff = first_diff(h, new)
            bad.append('%s 幂等失败（首个差异偏移 %d）' % (code, diff))
            _show_diff(h, new, diff)
        print('%-8s %-6s %-8s %-8s %s'
              % (code, src, st, meta['total'], '✅ 逐字节不变' if same else '❌ 有意料之外的差异'))

    print()
    print('—— 变分控制组：600456 第 6 项 9 → 7（必须真改，且改完幂等）——')
    p = os.path.join(d, '600456.html')
    if os.path.exists(p):
        h = io.open(p, encoding='utf-8').read()
        sc0, _, _ = parse_scores(h)
        sc2 = list(sc0)
        sc2[5] = 7
        n2, m2 = apply_scores(h, sc2)
        v2 = re.findall(r'<div class="sc-val">(.*?)</div>', n2, re.S)
        b2 = re.findall(r'width:\s*(\d+(?:\.\d+)?)%', n2)
        sent2 = re.search(r'主要得分项为.*?。', n2, re.S)
        ck = [
            ('确实改动了', n2 != h),
            ('第 6 项 .sc-val 变成 7', len(v2) == 10 and _txt(v2[5]) == '7'),
            ('第 6 条条宽变成 70%', len(b2) >= 6 and b2[5] == '70'),
            ('总分重算为 %s' % m2['total'], abs(parse_stored_total(n2) - m2['total']) < 1e-9),
            ('点名句被重算（原句对不上）', bool(sent2) and '全产业链独一无二' not in n2),
            ('新点名句自身自洽', bool(sent2) and note_consistent(sent2.group(0), sc2)),
            ('产出再套同分幂等', apply_scores(n2, sc2)[0] == n2),
        ]
        for name, okc in ck:
            print('   %s %s' % ('✅' if okc else '❌', name))
            if not okc:
                bad.append('控制组：%s' % name)

    print()
    for x in warns:
        print('  ⚠ %s' % x)
    print('幂等 / 读数自检：%s' % ('通过' if not bad else '失败'))
    for x in bad:
        print('  ✗ %s' % x)
    return not bad


def first_diff(a, b):
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            return i
    return min(len(a), len(b))


def _show_diff(a, b, at, pad=54):
    """打印首个差异的上下文 —— 失败时必须看到「到底改了哪几个字节」，别靠猜。"""
    lo = max(0, at - pad)
    print('        旧 …%s…' % a[lo:at + pad].replace('\n', '⏎'))
    print('        新 …%s…' % b[lo:at + pad].replace('\n', '⏎'))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    ok = selfcheck()
    sys.exit(0 if ok else 1)
