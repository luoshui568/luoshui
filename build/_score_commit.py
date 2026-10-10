# -*- coding: utf-8 -*-
"""槽 29「企业评分」评分落库 —— 命令行侧入口（与页面上的「💾 提交到数据库」同一件事）

────────────────────────────────────────────────────────────────────────
【为什么要有两条入口】
  · 页面入口：你一边拖一边看分，满意了点按钮 → 立刻写库（走 RGATE 管理员密码门）。
  · 本脚本  ：批量 / 事后回补 / 无人值守 / 需要详细 diff 的场景。
  两条路**必须产出完全相同的 HTML** —— 用的都是同一套定点替换：
      本脚本 → build/_score_patch.apply_scores()
      页面   → deploy/report.template.html 的 scBuildHtml()
  `_sc_test.py` 用例 D 对每个 code 做**逐字节相等**断言，保证不会两边各写一套。

用法：
    python _score_commit.py 002408                          # 干跑（只读线上 + 打印改动，不写库）
    python _score_commit.py 002408 --scores 9,10,6,5,7,9,6,9,9,6
    python _score_commit.py 002408 --scores ... --go         # 真写库
    python _score_commit.py 600456 --go                      # 用「线上现有分数」提交一次
                                                             #   ⇒ 顺带修正第 10 项 .sc-val 的笔误

【安全栅栏】顺序固定，任何一关不过就中止，**绝不半途写入**：
    ① 读线上 → ② 算出目标 HTML → ③ 与原文字节相同则早退（幂等）
    ④ 结构自检（十行 / 8 格 KPI / 10 条 sc-note / 说明段）→ ⑤ 漂移闸（写前重读，必须与刚才一致）
    ⑥ 备份原文到 _bak_m29/ → ⑦ PATCH → ⑧ 写后回读比对 → ⑨ 同步 seed 与 _score_src 基线
"""
import io
import json
import os
import re
import sys
import time
import hashlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import score_lock as SL                                     # noqa: E402
import _score_patch as SP                                   # noqa: E402
from _apply_score import (req, get_live, write_seed, parse_kpi,   # noqa: E402
                          parse_period, BAK, SRC, NO)

ALL = ['600456', '600459', '002237', '000731', '000830',
       '603977', '601118', '601958', '603599', '002408']


def md5(s):
    return hashlib.md5(s.encode('utf-8')).hexdigest()


def audit(new, old, scores):
    """落库前的结构自检 —— 只卡「必须原样保留」的东西，一票否决。"""
    bad = []
    if new.count('class="sc-line"') != 10:
        bad.append('sc-line %d 条（应 10）' % new.count('class="sc-line"'))
    if new.count('class="sc-val"') != 10:
        bad.append('sc-val %d 个（应 10）' % new.count('class="sc-val"'))
    for cls in ('score-hero', 'gauge-wrap', 'kv-grid', 'criteria', 'sc-total'):
        if ('class="%s"' % cls) not in new:
            bad.append('缺结构 %s' % cls)
    if new.count('class="kv"') != old.count('class="kv"'):
        bad.append('KPI 格数变了（%d → %d）' % (old.count('class="kv"'), new.count('class="kv"')))
    if new.count('class="sc-note"') != old.count('class="sc-note"'):
        bad.append('逐项说明格数变了（%d → %d）'
                   % (old.count('class="sc-note"'), new.count('class="sc-note"')))
    if new.count('data-w=') != old.count('data-w='):
        bad.append('`data-w` 数量变了（%d → %d）'
                   % (old.count('data-w='), new.count('data-w=')))
    if '主要得分项为' not in new and '评分说明' in new:
        bad.append('评分说明段缺少得分/扣分点名')
    # 说明段之外的部分必须除「七类定点」以外原样 —— 用「去掉被替换位后比对」太重，这里改为
    # 反查：把 new 再套一次同样的分数，必须逐字节稳定（幂等）
    again, _ = SP.apply_scores(new, scores)
    if again != new:
        bad.append('对自己的产出不幂等')
    return bad


def fmt_scores(ss):
    return '[' + ' '.join('%2s' % ('—' if s is None else s) for s in ss) + ']'


def main(argv):
    codes = [a for a in argv if re.fullmatch(r'\d{6}', a)] or (
        ALL if '--all' in argv else ['002408'])
    go = '--go' in argv
    raw = None
    if '--scores' in argv:
        raw = argv[argv.index('--scores') + 1]

    print('槽 29 评分落库 ｜ 模式：%s ｜ 目标 %s'
          % ('真写库 --go' if go else '干跑（不写库）', ' '.join(codes)))
    print('定点替换实现：_score_patch.apply_scores()（与页面 scBuildHtml 逐字同源）\n')

    ok_all = True
    for code in codes:
        SL.check_rubric()
        row = get_live(code)
        if not row:
            print('%s ✗ 线上没有槽 %s' % (code, NO))
            ok_all = False
            continue
        old = row.get('html') or ''
        old_scores, src, warn = SP.parse_scores(old)
        for w in warn:
            print('   ⚠ %s' % w)
        if raw:
            try:
                scores = [int(x) for x in re.split(r'[,\s]+', raw.strip()) if x != '']
            except Exception:
                print('%s ✗ --scores 解析失败：%r' % (code, raw))
                ok_all = False
                continue
            if len(scores) != 10 or any(not (0 <= s <= 10) for s in scores):
                print('%s ✗ --scores 必须是 10 个 0-10 的整数：%r' % (code, scores))
                ok_all = False
                continue
        else:
            if not old_scores:
                print('%s ✗ 线上读不出十项分数（非有分形态）' % code)
                ok_all = False
                continue
            scores = old_scores

        new, meta = SP.apply_scores(old, scores)
        t_old = SP.parse_stored_total(old)
        print('%s %s' % (code, (row.get('title') or '')[:26]))
        print('   %d → %d 字节 ｜ 总分 %s → %s ｜ 评级 %s'
              % (len(old), len(new), t_old, meta['total'], meta['rating']))
        if old_scores:
            diff = [('第 %d 项' % (i + 1), old_scores[i], scores[i])
                    for i in range(10) if old_scores[i] != scores[i]]
            print('   十项：%s → %s' % (fmt_scores(old_scores), fmt_scores(scores)))
            print('   分项变化：%s' % ('、'.join('%s %s→%s' % d for d in diff) if diff else '无'))
        if meta['counts']['note'] == -1:
            print('   ⚠ 原文没有评分说明段，已追加一段')

        if new == old:
            print('   ✓ 与线上逐字节相同 —— 已是目标形态，无需改动\n')
            continue

        bad = audit(new, old, scores)
        if bad:
            print('   ✗ 结构自检未过：%s\n' % '；'.join(bad))
            ok_all = False
            continue
        print('   ✓ 结构自检通过（十行 / 8 格 KPI / %d 条说明 / data-w 数量不变 / 自幂等）'
              % new.count('class="sc-note"'))

        if not go:
            print('   · 干跑：未写库（加 --go 才会 PATCH）\n')
            continue

        # ⑤ 漂移闸
        again = get_live(code)
        if (again.get('html') or '') != old:
            print('   ✗ 漂移闸：线上在这一瞬间被改过，已中止（未写入）\n')
            ok_all = False
            continue
        b = os.path.join(BAK, 'm29_%s_%s.html' % (code, time.strftime('%Y%m%d_%H%M%S')))
        if not os.path.isdir(BAK):
            os.makedirs(BAK)
        io.open(b, 'w', encoding='utf-8', newline='').write(old)
        # ⑦ PATCH（写库脚本绝不带管道）
        req('wb_report_mods?report_id=eq.%s&no=eq.%s' % (code, NO), 'PATCH', {'html': new})
        # ⑧ 写后回读
        back = get_live(code)
        if (back.get('html') or '') != new:
            print('   ✗ 写后回读不一致！原文已备份在 %s\n' % b)
            ok_all = False
            continue
        # ⑨ 同步 seed 缓存与 _score_src 基线
        try:
            kpi = parse_kpi(old)
            write_seed(code, {'total': meta['total'], 'rating': meta['rating'],
                              'scores': scores}, kpi, parse_period(old, kpi))
            sp = os.path.join(SRC, '%s.json' % code)
            if os.path.exists(sp):
                sd = json.loads(io.open(sp, encoding='utf-8').read())
                for m in sd.get('mods', []):
                    if str(m.get('no')) == NO:
                        m['html'] = new
                io.open(sp, 'w', encoding='utf-8').write(json.dumps(sd, ensure_ascii=False))
            seed_ok = 'seed 已写'
        except Exception as e:
            seed_ok = 'seed 同步失败：%s' % e
        print('   ✅ 已 PATCH + 回读一致 ｜ md5 %s ｜ 备份 %s ｜ %s\n'
              % (md5(new)[:12], os.path.basename(b), seed_ok))

    print('结论：%s' % ('全部通过' if ok_all else '有未通过项，见上'))
    return 0 if ok_all else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
