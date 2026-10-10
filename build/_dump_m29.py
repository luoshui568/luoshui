# -*- coding: utf-8 -*-
"""抓 10 家线上槽 29 原文，比对「数值手术」要面对的形态差异。

产出 build/_m29/ 下每家一个 html + 一份结构摘要，供 _score_patch.py 设计边界。
"""
import io, json, os, re, sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _probe_lock29 as P            # noqa: E402  复用 fetch_live

OUT = os.path.join(HERE, '_m29')
os.makedirs(OUT, exist_ok=True)


def summarize(code, h):
    """把一个模块 HTML 的关键标记摸清楚。"""
    d = {}
    d['len'] = len(h)
    d['data_w'] = len(re.findall(r'class="sc-line" data-w="(\d+)"', h))
    d['sc_line'] = h.count('class="sc-line"')
    # sc-bar 的内部（原样保留空白，看是不是 <i> 紧跟开标签）
    bars = re.findall(r'(<div class="sc-bar">)(.*?)(</div>)', h, re.S)
    d['bar_n'] = len(bars)
    d['bar_shapes'] = sorted(set(repr(b) for _, b, _ in bars))[:3]
    # sc-val
    vals = re.findall(r'(<div class="sc-val">)(.*?)(</div>)', h, re.S)
    d['val_raw'] = [v for _, v, _ in vals]
    # p.src 出现次数与各自前 46 字
    srcs = re.findall(r'<p class="src"[^>]*>(.{0,46})', h, re.S)
    d['src_n'] = len(srcs)
    d['src_heads'] = srcs
    # 环形
    g = re.search(r'<div class="gauge" style="([^"]*)">', h)
    d['gauge_style'] = g.group(1) if g else None
    gn = re.search(r'<div class="gauge-num">(.*?)</div>', h, re.S)
    d['gauge_num'] = gn.group(1) if gn else None
    gb = re.search(r'<div class="gauge-badge">(.*?)</div>', h, re.S)
    d['gauge_badge'] = gb.group(1) if gb else None
    gs = re.search(r'<div class="g-sub">(.*?)</div>', h, re.S)
    d['g_sub'] = gs.group(1) if gs else None
    tt = re.search(r'<span class="tt">(.*?)</span>', h, re.S)
    d['tt'] = tt.group(1) if tt else None
    tn = re.search(r'<span class="tn">(.*?)</span>', h, re.S)
    d['tn'] = tn.group(1) if tn else None
    # sc-note 数量（逐项说明）
    d['sc_note'] = h.count('class="sc-note"')
    d['kv'] = h.count('class="kv"')
    return d


def main():
    mods = P.fetch_live(P.ALL)
    rep = {}
    for code in P.ALL:
        m = mods.get(code)
        if not m:
            print('%s 无模块' % code)
            continue
        h = m.get('html') or ''
        io.open(os.path.join(OUT, '%s.html' % code), 'w', encoding='utf-8', newline='').write(h)
        rep[code] = summarize(code, h)
    io.open(os.path.join(OUT, '_summary.json'), 'w', encoding='utf-8').write(
        json.dumps(rep, ensure_ascii=False, indent=1))

    print('%-8s %6s %5s %5s %4s %4s %-9s %-7s %-6s' %
          ('code', 'len', 'dataW', 'line', 'note', 'src', 'form', 'badge', 'tn'))
    for code in P.ALL:
        d = rep.get(code)
        if not d:
            continue
        blank = sum(1 for v in d['val_raw'] if v.strip() == '—')
        form = '空分' if blank == 10 else ('有分' if blank == 0 else '混合')
        print('%-8s %6d %5d %5d %4d %4d %-9s %-7s %-6s' %
              (code, d['len'], d['data_w'], d['sc_line'], d['sc_note'], d['src_n'],
               form, (d['gauge_badge'] or '')[:6], (d['tn'] or '')[:5]))
    print()
    print('bar 内部形状（前 3 种）：')
    for code in P.ALL:
        d = rep.get(code)
        if d:
            print('  %s  %s' % (code, ' | '.join(d['bar_shapes'])))
    print()
    print('src 段抬头：')
    for code in P.ALL:
        d = rep.get(code)
        if d:
            print('  %s  n=%d  %s' % (code, d['src_n'], ' // '.join(x.replace('\n', ' ')[:34] for x in d['src_heads'])))


if __name__ == '__main__':
    main()
