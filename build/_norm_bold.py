# -*- coding: utf-8 -*-
"""正文里残留的 markdown 加粗 `**…**` → `<b>…</b>` 归一（含未闭合行内标签的收尾修复）

────────────────────────────────────────────────────────────────────────
【问题（2026-09-22 全链探头顺带发现）】
新建那批研报的正文是按 markdown 习惯写的，`**加粗**` 写进了 HTML 正文，
而壳里**没有任何 `**` → `<b>` 的转换**（已 grep 确认）⇒ 页面上直接显示成
`**身份一：世界最大的碳四深加工基地**` 这个样子。10 家里共 10702 处。

还有一处更严重的连带伤害：002408 的 m1 里，一处 `<b>` 的收尾被写成了残留的 `**`，
于是那个 `<b>` 一直没闭合 —— 浏览器会把**它后面的全部内容**都当成它的子节点，
整份报告从此全变粗；更要命的是 m29 的 `.criteria` 也被套进去了，
`crit.parentNode` 拿不到 `data-mod` ⇒ 「💾 提交到数据库」按钮永远报「拿不到模块原文」
（壳侧已改成「向上找最近的 [data-mod]」兜住，但正文本身也该修）。

【本工具做什么】
  · 把每个模块正文里的 `**x**` 成对换成 `<b>x</b>`；
  · 若换完后还剩**落单的 `**`**，且该模块确有未闭合的 `<b>` ⇒ 把它换成 `</b>`（正是上面那种笔误）；
  · `<code>` / `<pre>` 里的内容原样不动（那里的 `**` 可能是真代码）；
  · 不跨块级边界配对（`</p> </li> </div> </td> </tr> <br>`）—— 避免出现跨段落的粗体；
  · 自检：每个改完的模块**必须**行内标签全配对 + 零残留 `**`，有一处不过就整家跳过不写。

用法：
    python _norm_bold.py                    # 全部 10 家干跑（只读，打印改动量 + 样例）
    python _norm_bold.py 002408             # 指定一家干跑
    python _norm_bold.py 002408 --show 3    # 干跑并打印 3 个样例的前后对照
    python _norm_bold.py --go               # 真写库（逐模块 PATCH，带漂移闸与回读）
"""
import hashlib
import io
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from _apply_score import req                                          # noqa: E402

ALL = ['600456', '600459', '002237', '000731', '000830',
       '603977', '601118', '601958', '603599', '002408']
TAGS = ('b', 'strong', 'i', 'em', 'u', 'code', 'small')
BAK = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_bak_bold')

#: 成对加粗：不跨块级边界、不吞进下一个 `**`
PAIR = re.compile(r'\*\*((?:(?!\*\*|</?p[ >]|</?li[ >]|</?div[ >]|</?td[ >]|'
                  r'</?tr[ >]|</?h[1-6][ >]|<br\s*/?>)[\s\S])+?)\*\*')
#: `<code>` / `<pre>` 区段（里面的 `**` 不动）
SKIP = re.compile(r'(?is)<(code|pre)([ >]).*?</\1>')


def md5(s):
    return hashlib.md5(s.encode('utf-8')).hexdigest()[:12]


def count_tag(h, t):
    return len(re.findall(r'<%s[ >]' % t, h)), h.count('</%s>' % t)


def balance(h):
    """返回不平衡的行内标签清单。"""
    bad = []
    for t in TAGS:
        o, c = count_tag(h, t)
        if o != c:
            bad.append('%s %d/%d' % (t, o, c))
    return bad


def convert(h):
    """把 `**x**` 换成 `<b>x</b>`；`<code>/<pre>` 跳过；返回 (新 html, 统计)。

    残留的孤立 `**` 分两种（都有实据，不是猜的）：
      ① 该模块存在未闭合的 `<b>` ⇒ 用它收尾 —— 002408 m1 就是把 `</b>` 写成了 `**`；
      ② 其余是作者 `**A**：**B**` 这种相邻写法留下的碎片 ⇒ **删掉**。
         不能拿它去开/闭一个粗体：那是凭空造作者的强调，宁可不加。
    """
    n_sub = [0]

    def _on_text(seg):
        def _r(m):
            n_sub[0] += 1
            return '<b>' + m.group(1) + '</b>'
        return PAIR.sub(_r, seg)

    out, pos = [], 0
    for m in SKIP.finditer(h):
        out.append(_on_text(h[pos:m.start()]))
        out.append(m.group(0))
        pos = m.end()
    out.append(_on_text(h[pos:]))
    new = ''.join(out)
    n_pair = n_sub[0]

    n_close = n_drop = 0
    while '**' in new:
        o, c = count_tag(new, 'b')
        if o > c:
            new = new.replace('**', '</b>', 1)
            n_close += 1
        else:
            new = new.replace('**', '', 1)
            n_drop += 1
    return new, {'pair': n_pair, 'lone': n_close, 'drop': n_drop, 'left': new.count('**')}


def main(argv):
    codes = [a for a in argv if a.isdigit() and len(a) == 6] or ALL
    go = '--go' in argv
    show = 0
    if '--show' in argv:
        try:
            show = int(argv[argv.index('--show') + 1])
        except Exception:                                          # noqa: BLE001
            show = 2

    print('正文 `**` 归一 ｜ 模式：%s ｜ 目标 %s\n'
          % ('真写库 --go' if go else '干跑（只读）', ' '.join(codes)))
    if go and not os.path.isdir(BAK):
        os.makedirs(BAK)

    tot_pair = tot_lone = tot_drop = tot_mod = tot_skip = 0
    skipped = []
    for code in codes:
        rows = req('wb_report_mods?report_id=eq.%s&select=id,no,title,html&order=seq.asc' % code)
        n_pair = n_lone = n_drop = n_mod = 0
        for r in rows:
            h = r.get('html') or ''
            if '**' not in h:
                continue
            new, st = convert(h)
            n_pair += st['pair']
            n_lone += st['lone']
            n_drop += st['drop']
            if new == h:
                continue
            bad = balance(new)
            if bad or st['left']:
                skipped.append('%s no=%s（自检未过：%s%s）'
                               % (code, r['no'], ' '.join(bad),
                                  ('｜残留 ** ×%d' % st['left']) if st['left'] else ''))
                tot_skip += 1
                continue
            n_mod += 1
            if show and n_mod <= show:
                i = next((k for k in range(min(len(h), len(new))) if h[k] != new[k]), 0)
                print('  [样例 %s no=%s]' % (code, r['no']))
                print('    改前 …%s…' % h[max(0, i - 70):i + 90].replace('\n', '⏎'))
                print('    改后 …%s…' % new[max(0, i - 70):i + 90].replace('\n', '⏎'))
            if go:
                # 漂移闸 → 备份 → PATCH → 回读
                cur = req('wb_report_mods?report_id=eq.%s&no=eq.%s&select=html' % (code, r['no']))
                if not cur or (cur[0].get('html') or '') != h:
                    skipped.append('%s no=%s（漂移闸：期间被改过）' % (code, r['no']))
                    tot_skip += 1
                    continue
                io.open(os.path.join(BAK, '%s_%s_%s.html'
                                     % (code, r['no'], time.strftime('%Y%m%d_%H%M%S'))),
                        'w', encoding='utf-8', newline='').write(h)
                req('wb_report_mods?report_id=eq.%s&no=eq.%s' % (code, r['no']),
                    'PATCH', {'html': new})
                back = req('wb_report_mods?report_id=eq.%s&no=eq.%s&select=html'
                           % (code, r['no']))
                if not back or (back[0].get('html') or '') != new:
                    skipped.append('%s no=%s（写后回读不一致！）' % (code, r['no']))
                    tot_skip += 1
        print('%-8s 需改模块 %2d ｜ 成对加粗 %5d ｜ 未闭合收尾 %d ｜ 碎片删除 %d'
              % (code, n_mod, n_pair, n_lone, n_drop))
        tot_pair += n_pair
        tot_lone += n_lone
        tot_drop += n_drop
        tot_mod += n_mod

    print('\n合计：需改模块 %d ｜ 成对 `**x**` → <b> %d 处 ｜ 未闭合 `<b>` 收尾 %d 处'
          ' ｜ 碎片 `**` 删除 %d 处'
          % (tot_mod, tot_pair, tot_lone, tot_drop))
    if skipped:
        print('自检未过 / 跳过 %d 处（一家有跳过就不写那一个模块）：' % tot_skip)
        for x in skipped[:20]:
            print('  ⚠ %s' % x)
    if not go:
        print('\n（干跑：未写库。加 --go 才真写；写完还要跑 sync_seed_full.py 同步本地缓存）')
    return 0 if not skipped else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
