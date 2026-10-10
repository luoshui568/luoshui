# -*- coding: utf-8 -*-
"""把 4 家「搬家」存量报告的槽 29 十项明细**定点重建**为冻结表。

【为什么要重建】
  _probe_lock29.py 实测（线上库）暴露三类漂移：
    · 加分项标记错位：恒邦标在 #6–#10（应 #1/#2/#5）；鲁西只标 #1；贵研缺 #5
    · 「加分项」误写成**字面 `pos`**（贵研 2 / 恒邦 2 / 美丰 5 / 鲁西 1 处）——
      这是 _m29_unify.py 当年的缺陷，页面上真的显示「pos」
    · 美丰第 7 项项名被截断成「总市值」（丢了「< 200 亿」）
  ⇒ 用 build/score_lock.py 的冻结表重建这 10 行。**只换 sc-line 块**，
    环形卡 / KPI 卡 / sc-total / 填写说明 / 以及 600456 之外的其余内容**一字不动**。

【不改谁】宝钛 600456 —— 它是母本，冻结表就是照它抄的，本就合格。

自检（缺一即停）：
  ① 幂等：build(build(x)) == build(x)
  ② 结构：sc-line 恰 10 条；pos-em 恰 3 处；无字面 `pos`
  ③ 缺分断言：sc-val 全为 `—`；sc-bar 内无 <i>
  ④ 漂移闸：PATCH 前重读线上，必须与本次读到的原文逐字节相同
  ⑤ 写后回读：线上 html == 新值
  ⑥ 其余部分不变：把新值的 sc-line 块换成原文的，应与原文整体相同

用法：
    python _lock29_fix.py            # 干跑
    python _lock29_fix.py --go       # 备份 + PATCH 线上 + 写回本地 seed
    python _lock29_fix.py 002237     # 只处理指定几家
"""
import io
import json
import os
import re
import shutil
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import score_lock as SL               # noqa: E402

BAK = os.path.join(HERE, 'backup')
CFG = json.load(io.open(os.path.join(HERE, 'cloud.json'), encoding='utf-8'))
BASE = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']
HDR = {'apikey': CFG['key'], 'Authorization': 'Bearer ' + CFG['key'],
       'Accept': 'application/json', 'Content-Type': 'application/json'}
NO = '29'
DEFAULT = ['600459', '002237', '000731', '000830']
HEAD_END = '</div>'


def req(path, method='GET', body=None):
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
    rq = urllib.request.Request(BASE + path, data=data, headers=HDR, method=method)
    with urllib.request.urlopen(rq, timeout=120) as r:
        raw = r.read().decode('utf-8')
    return json.loads(raw) if raw.strip() else None


def get_live(code):
    rows = req('wb_report_mods?report_id=eq.%s&no=eq.%s&select=no,title,html' % (code, NO))
    return rows[0] if rows else None


def frozenset_lines():
    """只取冻结表生成的 10 行 sc-line（空分、无 sc-note）。"""
    h = SL.render()
    i = h.index('      <div class="sc-line">')
    j = h.index('      <div class="sc-total">')
    return h[i:j]


def rebuild(old):
    """把 criteria 里第一个 sc-line 到 sc-total 之间整块换成冻结的 10 行。"""
    i = old.index('<div class="sc-line">')
    # 退到该行行首的缩进
    ls = old.rfind('\n', 0, i) + 1
    j = old.index('<div class="sc-total">')
    js = old.rfind('\n', 0, j) + 1
    return old[:ls] + frozenset_lines() + old[js:]


def audit(h, tag):
    bad = []
    if h.count('class="sc-line"') != 10:
        bad.append('sc-line %d 条' % h.count('class="sc-line"'))
    n_pos = sum(1 for _, p, _ in SL.ITEMS if p)
    if h.count('<em class="pos-em">加分项</em>') != n_pos:
        bad.append('加分项 %d 处（应 %d）' % (h.count('<em class="pos-em">加分项</em>'), n_pos))
    if re.search(r'>\s*pos\s*<', h):
        bad.append('仍有字面 `pos`')
    vals = re.findall(r'<div class="sc-val">(.*?)</div>', h, re.S)
    if len(vals) != 10 or any(v.strip() != SL.BLANK for v in vals):
        bad.append('sc-val 非全空：%r' % vals[:12])
    bars = re.findall(r'<div class="sc-bar">(.*?)</div>', h, re.S)
    if any('<i' in b for b in bars):
        bad.append('sc-bar 里有残留 <i>')
    # 项名与权重（★ 必须解转义：冻结名里的 `>`/`<` 会被 _esc 写成 &gt;/&lt;）
    unesc = lambda s: (s.replace('&gt;', '>').replace('&lt;', '<')
                       .replace('&amp;', '&').replace('&nbsp;', ' '))
    names = [unesc(re.sub(r'<[^>]+>', '', x)).replace('加分项', '').strip()
             for x in re.findall(r'<div class="sc-name">(.*?)</div>', h, re.S)]
    wts = re.findall(r'<div class="sc-w">(\d+)%</div>', h)
    for k, (nm, _p, w) in enumerate(SL.ITEMS):
        if k < len(names) and names[k] != nm:
            bad.append('第%d项项名 %r ≠ %r' % (k + 1, names[k], nm))
        if k < len(wts) and wts[k] != str(w):
            bad.append('第%d项权重 %s%% ≠ %d%%' % (k + 1, wts[k], w))
    if bad:
        print('   ✗ %s：%s' % (tag, '；'.join(bad)))
    return not bad


def main(argv):
    go = '--go' in argv
    codes = [a for a in argv if re.fullmatch(r'\d{6}', a)] or DEFAULT
    SL.check_rubric()
    os.makedirs(BAK, exist_ok=True)
    print('冻结契约 %s ｜ 目标 %s ｜ %s\n' % (SL.LOCK_VERSION, ' '.join(codes),
                                            '落盘' if go else '干跑'))
    ok_all = True
    for code in codes:
        row = get_live(code)
        if not row:
            print('%s ✗ 线上找不到槽 29' % code)
            ok_all = False
            continue
        old = row.get('html') or ''
        new = rebuild(old)
        same = (new == old)
        print('%s %s 槽%s 长 %d → %d 字节%s' % (
            code, row.get('title', '')[:22], row.get('no'), len(old), len(new),
            '（已是冻结形态，无需改动）' if same else ''))
        # ① 幂等
        if rebuild(new) != new:
            print('   ✗ 幂等自检失败'); ok_all = False; continue
        # ②③ 结构
        if not audit(new, '结构'):
            ok_all = False
            continue
        # ⑥ 其余部分不变：把新值的 sc-line 块还原成原文的，应与原文整体相同
        li = new.index('<div class="sc-line">'); ls = new.rfind('\n', 0, li) + 1
        lj = new.index('<div class="sc-total">'); ljs = new.rfind('\n', 0, lj) + 1
        oi = old.index('<div class="sc-line">'); ols = old.rfind('\n', 0, oi) + 1
        oj = old.index('<div class="sc-total">'); ojs = old.rfind('\n', 0, oj) + 1
        if (new[:ls] + old[ols:ojs] + new[ljs:]) != old:
            print('   ✗ 自检⑥失败：改动溢出了 sc-line 块'); ok_all = False; continue
        if same:
            continue
        if not go:
            continue
        # ④ 漂移闸：重读线上，必须与本次读到的原文一致
        again = get_live(code)
        if (again.get('html') or '') != old:
            print('   ✗ 漂移闸：线上在这一瞬间被改过了，跳过'); ok_all = False; continue
        b = os.path.join(BAK, 'lock29_%s_%s.html' % (code, time.strftime('%Y%m%d_%H%M%S')))
        io.open(b, 'w', encoding='utf-8').write(old)
        req('wb_report_mods?report_id=eq.%s&no=eq.%s' % (code, NO), 'PATCH', {'html': new})
        back = get_live(code)
        if (back.get('html') or '') != new:
            print('   ✗ 写后回读不一致！备份在 %s' % b); ok_all = False; continue
        # 写回本地 seed（保持缓存不过期）
        sp = os.path.join(HERE, 'seed', 'report_%s.json' % code)
        if os.path.exists(sp):
            rep = json.loads(io.open(sp, encoding='utf-8').read())
            for m in rep.get('mods', []):
                if str(m.get('no')) == NO:
                    m['html'] = new
            io.open(sp, 'w', encoding='utf-8').write(
                json.dumps(rep, ensure_ascii=False, indent=1))
        print('   ✅ 已 PATCH + 回读一致（备份 %s）' % os.path.basename(b))
    print()
    print('结论：%s' % ('全部通过' if ok_all else '有未通过项，见上'))
    return 0 if ok_all else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
