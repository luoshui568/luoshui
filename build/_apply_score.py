# -*- coding: utf-8 -*-
"""把存量研报的槽 29 从「空分 / 旧分」升级为「母本 A 形 · 自动评分」。

【背景】2026-09-22 用户指令：
    「m29以后都用母本形态，帮我按照母本给的评分标准自动评分，全部补全」

【四层分工 —— 算法不进渲染器】
    · score_lock.py    冻结表 + 渲染（唯一真源；「不每次都改」靠它）
    · score_engine.py  十项判据（纯规则，分数可复算、评级由此换算）
    · _score_run.py    从线上报告抽原料 → 调引擎 → _score_out.json
    · 本脚本           把结果落回线上库与本地 seed（**只动槽 29**）

【不动谁】宝钛 600456 —— 它是母本：已有分（70.5，与本引擎回放**逐项一致**），
  且 KPI 卡保留「参考买入价 / 目标价 / 盈利空间」三格（其余 9 家 2026-09-21
  统一成客观财务格）。动它等于改尺子 ⇒ 默认跳过，须显式 --all 才含。

【只改什么】整块替换槽 29 的 html；KPI 8 格**从线上原文抽出后原样回填**
  （score_lock.kpi_from_fin 的 score.kpi 优先级即为此而设）⇒ 取值零漂移。
  其余 30 个模块、页面壳、图表一律不碰。

自检（缺一即停）：
  ① 幂等：同参数连渲两次字节相同
  ② 结构：sc-line 恰 10；加分项恰 3 处；无字面 `pos`；项名/权重逐字相符
  ③ 有分：sc-val 全为 0~10 的数字；sc-bar 内有 <i>；环形百分比 == 总分
  ④ 可复算：SL.total_of(scores) == total == 环形读数 == sc-total 读数
  ⑤ notes：每条非空说明都出现在 html 里（按 _esc 后比对）
  ⑥ 不泄漏：无 None / %.2f / {ind} / [MISSING]
  ⑦ 漂移闸：PATCH 前重读线上，必须与本次读到的原文逐字节相同
  ⑧ 写后回读：线上 html == 新值

用法：
    python _apply_score.py                 # 干跑（除母本外的 9 家）
    python _apply_score.py --go            # 备份 + PATCH 线上 + 写回 seed
    python _apply_score.py 600459 002237   # 只处理指定几家
    python _apply_score.py --go --all      # 连母本一起（一般不这么用）
"""
import io
import json
import os
import re
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import score_lock as SL               # noqa: E402

BAK = os.path.join(HERE, '_bak_m29')
SRC = os.path.join(HERE, '_score_src')
CFG = json.load(io.open(os.path.join(HERE, 'cloud.json'), encoding='utf-8'))
BASE = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']
HDR = {'apikey': CFG['key'], 'Authorization': 'Bearer ' + CFG['key'],
       'Accept': 'application/json', 'Content-Type': 'application/json'}
NO = '29'
MOTHER = '600456'                     # 母本宝钛 —— 默认不动

#: render() 的收尾锚点 = 说明段 <p class="src">…</p>。锚点**之后**的是
#: deep 正文（各模块自己的分析文字），必须原样保留 —— 600459 就带着
#: 「十项原则对贵研的适用性说明」+ 四维财务质量评分，共 2509 字节。
SRC_ANCHOR = re.compile(r'<p class="src"[^>]*>.*?</p>', re.S)

#: deep 正文里因「本轮留空」而写下的过时话 —— 有分之后必须同步修正，
#: 否则页面上会出现「评分待填写」与上方 70.2 分自相矛盾。
#: ⚠️ 文案**不写死分数**，避免下次重跑时又过时。
TAIL_FIX = {
    '600459': [(
        '<b>本报告的评分待填写</b>，原因是这套原则里有若干条'
        '对贵研的商业模式不构成有效判据，强行打分会产生「看似精确的误导」。',
        '<b>本报告已按同一把尺自动评分</b>（见上方环形卡与十项明细）；'
        '但仍需注意：这套原则里有若干条对贵研的商业模式不构成有效判据，'
        '分数含义须结合下表一并读。',
    )],
}

#: 个别公司的 KPI 格取不到值、但**公开财报里有** —— 记在这里，保持单一落库口。
#: 格式 {code: {kpi 键: 展示值}}；值必须来自公开披露，**不得推算**。
#: 起因：000731 / 000830 原始槽 29 的 KPI 第 5 格是「营收」而非「归母净利」，
#: 统一到冻结 8 格后 EPS 位空缺（其余 7 家本就有值）。
#: 来源：同花顺 iFinD，2026-06-30 每股收益 EPS-基本。
KPI_EXTRA = {
    '000731': {'eps': '-0.10 元'},   # iFinD 基本 EPS −0.0974
    '000830': {'eps': '0.51 元'},    # iFinD 基本 EPS 0.512
}


def req(path, method='GET', body=None, prefer=None):
    """打 PostgREST。

    `prefer='return=representation'` 时，PATCH 会把**受影响的行**回显出来 ——
    这是「UPDATE 真的命中了真实行（而不是 204 空转）」的判据：
    返回 `[]` = 一行没匹配上（RLS 的 USING 把它滤掉了）；返回 1 行 = 真的更新到了。
    """
    hdr = dict(HDR)
    if prefer:
        hdr['Prefer'] = prefer
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
    rq = urllib.request.Request(BASE + path, data=data, headers=hdr, method=method)
    with urllib.request.urlopen(rq, timeout=120) as r:
        raw = r.read().decode('utf-8')
    return json.loads(raw) if raw.strip() else None


def get_live(code):
    rows = req('wb_report_mods?report_id=eq.%s&no=eq.%s&select=no,title,html' % (code, NO))
    return rows[0] if rows else None


def parse_kpi(h):
    """从线上槽 29 的 KPI 卡里抽 8 格 → render() 的键。取不到就不给（显示「—」）。"""
    pairs = re.findall(r'<div class="k">([^<]*)</div>\s*<div class="v"[^>]*>([^<]*)</div>', h)
    out = {}
    for k, v in pairs:
        k, v = k.strip(), v.strip()
        if not v or v == SL.BLANK:
            continue
        if k == '总市值（亿元）':
            out['mktcap'] = v
        elif k.startswith('PE（'):
            out['pe'] = v
        elif k.startswith('PB（'):
            out['pb'] = v
        elif k == '当前价格（元）':
            out['price'] = v
        elif k.endswith('归母净利'):
            out['np'] = v
        elif k.endswith('扣非净利'):
            out['npdx'] = v
        elif k.endswith('EPS'):
            out['eps'] = v
        elif k == '报告日期':
            out['date'] = v
    return out


def parse_period(h, kpi):
    """从「2026H1归母净利」这类标签里回推报告期前缀。"""
    m = re.search(r'<div class="k">([^<]*?)\s*(?:归母净利|扣非净利|EPS)</div>', h)
    if m:
        p = m.group(1).strip()
        if p and len(p) <= 8:
            return p
    return ''


def build(code, out, live_html):
    """渲染新槽 29 = render() 输出 + 原有 deep 正文（tail）。

    ★ tail 必须逐字节保留 —— 那是各公司自己的分析文字，不属于渲染器职权。
      幂等判据：新 html 已以 head 开头 ⇒ tail 原样接在后面（不再走切分，
      避免 tail 内部若有 <p class="src"> 被误当锚点）。
    """
    r = out[code]['result']
    kpi = parse_kpi(live_html)
    kpi.update(KPI_EXTRA.get(code) or {})    # 缺格补值（见 KPI_EXTRA 注释）
    head = SL.render(kpi=kpi, period=parse_period(live_html, kpi),
                     notes=r['notes'], scores=r['scores'],
                     total=r['total'], rating=r['rating'])
    if live_html.startswith(head):
        tail = live_html[len(head):]
    else:
        tail = split_old(live_html)[1]
    tail = fix_tail(code, tail)
    return head + tail, kpi, tail


def split_old(old):
    """按说明段锚点把旧 html 切成 (render 输出, deep 正文)。"""
    ms = list(SRC_ANCHOR.finditer(old))
    if not ms:
        return old, ''
    last = ms[-1]
    return old[:last.end()], old[last.end():]


def fix_tail(code, tail):
    for a, b in TAIL_FIX.get(code, []):
        tail = tail.replace(a, b)
    return tail


def num_s(v):
    return ('%.1f' % v).rstrip('0').rstrip('.')


def audit(h, r, kpi, tag):
    """②③④⑤⑥ 结构 / 有分 / 可复算 / notes / 泄漏。任一项不过即列出。"""
    bad = []
    scores = r['scores']
    n_pos = sum(1 for _, p, _ in SL.ITEMS if p)

    # ② 结构
    if h.count('class="sc-line"') != 10:
        bad.append('sc-line %d 条' % h.count('class="sc-line"'))
    if h.count('<em class="pos-em">加分项</em>') != n_pos:
        bad.append('加分项 %d 处（应 %d）' % (h.count('<em class="pos-em">加分项</em>'), n_pos))
    if re.search(r'>\s*pos\s*<', h):
        bad.append('仍有字面 `pos`')
    unesc = lambda s: (s.replace('&gt;', '>').replace('&lt;', '<').replace('&amp;', '&'))
    names = [unesc(re.sub(r'<[^>]+>', '', x)).replace('加分项', '').strip()
             for x in re.findall(r'<div class="sc-name">(.*?)</div>', h, re.S)]
    wts = re.findall(r'<div class="sc-w">(\d+)%</div>', h)
    for k, (nm, _p, w) in enumerate(SL.ITEMS):
        if k < len(names) and names[k] != nm:
            bad.append('第%d项项名 %r ≠ %r' % (k + 1, names[k], nm))
        if k < len(wts) and wts[k] != str(w):
            bad.append('第%d项权重 %s%% ≠ %d%%' % (k + 1, wts[k], w))

    # ③ 有分形态
    vals = [v.strip() for v in re.findall(r'<div class="sc-val">(.*?)</div>', h, re.S)]
    if len(vals) != 10:
        bad.append('sc-val %d 个' % len(vals))
    else:
        for k, v in enumerate(vals):
            if not re.fullmatch(r'\d{1,2}(?:\.\d+)?', v):
                bad.append('第%d项分数 %r 非数字' % (k + 1, v))
                break
        else:
            if [float(v) for v in vals] != [float(s) for s in scores]:
                bad.append('sc-val 与 scores 不一致：%s vs %s' % (vals, scores))
    bars = re.findall(r'<div class="sc-bar">(.*?)</div>', h, re.S)
    if len(bars) != 10 or any('<i' not in b for b in bars):
        bad.append('sc-bar 未全部出条（%d 个）' % sum(1 for b in bars if '<i' in b))

    # ④ 可复算 / 环形 / sc-total
    tot = SL.total_of(scores)
    if r['total'] is not None and abs(float(r['total']) - tot) > 1e-9:
        bad.append('total %s ≠ total_of(scores) %s' % (r['total'], tot))
    if tot > 100 or tot < 0:
        bad.append('总分越界 %s' % tot)
    if SL.grade_of(tot) != r['rating']:
        bad.append('评级 %r ≠ grade_of(%s) %r' % (r['rating'], tot, SL.grade_of(tot)))
    if ('conic-gradient(#c8102e 0 %s%%' % num_s(tot)) not in h:
        bad.append('环形刻度未按 %s 渲染' % num_s(tot))
    tns = re.findall(r'<span class="tn">([^<]*)</span>', h)
    if tns != [num_s(tot)]:
        bad.append('sc-total 读数 %r ≠ %s' % (tns, num_s(tot)))

    # ⑤ notes 逐条落地
    for k, n in enumerate(r['notes'] or []):
        if n and SL._esc(n) not in h:
            bad.append('第%d项说明未出现在 html' % (k + 1))
            break

    # ⑥ 不泄漏
    for tok in ('None', '%.2f', '{ind}', '[MISSING]', 'nan'):
        if tok in h:
            bad.append('泄漏 %s' % tok)

    if bad:
        print('   ✗ %s：%s' % (tag, '；'.join(bad[:6])))
    return not bad


def write_seed(code, r, kpi, period):
    """把评分结果写回 data_v31_<code>.json 的 score 字段（缓存不过期）。"""
    sp = os.path.join(HERE, 'seed', 'data_v31_%s.json' % code)
    if not os.path.exists(sp):
        return None
    d = json.loads(io.open(sp, encoding='utf-8').read())
    sc = d.get('score')
    if not isinstance(sc, dict):
        sc = {}
    sc.pop('items', None)                       # 已作废的覆写口子，顺手清掉
    sc.update({'period': period or sc.get('period') or '',
               'date': kpi.get('date') or sc.get('date') or '',
               'kpi': kpi,
               'notes': r['notes'],
               'scores': r['scores'],
               'total': r['total'],
               'rating': r['rating']})
    d['score'] = sc
    io.open(sp, 'w', encoding='utf-8').write(json.dumps(d, ensure_ascii=False, indent=1))
    return sp


def main(argv):
    go = '--go' in argv
    with_all = '--all' in argv
    out = json.load(io.open(os.path.join(HERE, '_score_out.json'), encoding='utf-8'))
    order = list(out)
    codes = [a for a in argv if re.fullmatch(r'\d{6}', a)]
    if not codes:
        codes = order if with_all else [c for c in order if c != MOTHER]

    SL.check_rubric()
    os.makedirs(BAK, exist_ok=True)
    print('冻结契约 %s ｜ 目标 %d 家 ｜ %s' % (SL.LOCK_VERSION, len(codes),
                                              '落盘' if go else '干跑'))
    if MOTHER not in codes:
        print('（母本 %s 保持原样：已是母本形态且分数与本引擎回放逐项一致）' % MOTHER)
    print()

    ok_all = True
    for code in codes:
        if code not in out:
            print('%s ✗ _score_out.json 里没有这家的评分结果' % code)
            ok_all = False
            continue
        row = get_live(code)
        if not row:
            print('%s ✗ 线上找不到槽%s' % (code, NO))
            ok_all = False
            continue
        old = row.get('html') or ''
        r = out[code]['result']
        new, kpi, tail = build(code, out, old)

        same = (new == old)
        print('%s %s 槽%s %d → %d 字节 ｜ %s 分 / %s ｜ deep %d 字节%s' % (
            code, (row.get('title') or '')[:20], row.get('no'), len(old), len(new),
            num_s(r['total']), r['rating'], len(tail),
            '（已是自动评分形态，无需改动）' if same else ''))

        # ⑨ deep 正文（各公司自己的分析）必须原样保留，绝不能因重渲染被删
        if not new.endswith(tail):
            print('   ✗ deep 正文未原样保留'); ok_all = False; continue

        # ① 幂等
        if build(code, out, old)[0] != new:
            print('   ✗ 幂等自检失败'); ok_all = False; continue
        # ②~⑥
        if not audit(new, r, kpi, '结构/有分/说明'):
            ok_all = False
            continue
        print('   KPI=%s' % {k: kpi.get(k) for k in ('mktcap', 'pe', 'pb', 'price')})
        if same:
            continue
        if not go:
            continue
        # ⑦ 漂移闸
        again = get_live(code)
        if (again.get('html') or '') != old:
            print('   ✗ 漂移闸：线上在这一瞬间被改过了，跳过'); ok_all = False; continue
        b = os.path.join(BAK, 'm29_%s_%s.html' % (code, time.strftime('%Y%m%d_%H%M%S')))
        io.open(b, 'w', encoding='utf-8').write(old)
        req('wb_report_mods?report_id=eq.%s&no=eq.%s' % (code, NO), 'PATCH', {'html': new})
        # ⑧ 写后回读
        back = get_live(code)
        if (back.get('html') or '') != new:
            print('   ✗ 写后回读不一致！备份在 %s' % b); ok_all = False; continue
        # 本地：seed 缓存 + _score_src 基线（后者用于下次「已是新形态」的幂等判定）
        write_seed(code, r, kpi, parse_period(old, kpi))
        sp = os.path.join(SRC, '%s.json' % code)
        if os.path.exists(sp):
            sd = json.loads(io.open(sp, encoding='utf-8').read())
            for m in sd.get('mods', []):
                if str(m.get('no')) == NO:
                    m['html'] = new
            io.open(sp, 'w', encoding='utf-8').write(json.dumps(sd, ensure_ascii=False))
        print('   ✅ 已 PATCH + 回读一致 ｜ seed 已写 ｜ 备份 %s' % os.path.basename(b))

    print()
    print('结论：%s' % ('全部通过' if ok_all else '有未通过项，见上'))
    return 0 if ok_all else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
