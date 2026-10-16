# -*- coding: utf-8 -*-
"""模块 3「股东结构」统一生成器 —— 全站研报唯一的制作通道。

为什么有这个文件
----------------
用户 2026-10-14 定稿：**以后所有研报的「股东结构」必须与宝钛股份（600456）的样式一致，
这块不可随意制作**。此前每个研报的模块 3 各写各的（有的自造「项目/数值/说明」小表，
有的没有股权结构图），风格无法收敛。本文件把宝钛那版**冻结成模板**：
规格 JSON（只装数据）→ 本生成器（只管版式）→ 模块 3 HTML。

骨架（顺序与类名都不可改）
--------------------------
  ① `.sh3-top`
       ├ 左：<h3>股东性质占比</h3> → `.sh3-donut`（环形占比 SVG + 环心 logo）+ `.sh3-leg`（2 张图例卡）
       └ 右：<h3>关键持股指标</h3> → `.sh3-stats`（4 格，第 3 格 .gold）
             <h3>股权特点解读</h3> → `.sh3-ul`（要点列表）
  ② `<h3>前十大股东明细</h3>` → 4 列表格（股东名称/性质/持股(股)/占比）+ 合计行
  ③ `<h3>股权结构图</h3>` → `.sh3-tree`（SVG：红底方框 + 白底比例药丸 + 箭头 + 竖排子公司名）+ `.cap`
  ④ `<p class="src">` 来源行

CSS 在 `build/report_theme.css` 的「模块3 · 股东结构（环形占比 + 股权树）」标记块里
（由 `mkmod3_css.py` 幂等写入）；本文件只产 HTML，不碰 CSS。

用法
----
    python3 mkmod3_std.py --list                  # 列出已有规格 + 与 seed 现状是否一致
    python3 mkmod3_std.py 600456 --check          # 生成并与 seed 里的现状比对（不写盘）
    python3 mkmod3_std.py 600392 --check --dump /tmp/x.html
    python3 mkmod3_std.py 600392 --write          # 备份后写进 seed/report_<code>.json
    python3 mkmod3_std.py 600392 --push           # 写库（只 PATCH <code>_m3 一行；默认 dry-run）
    python3 mkmod3_std.py 600392 --push --go      # 真写库 + 备份 + 回读核对

规格文件：`build/seed/m3std/m3_<code>.json`（字段说明见 build/README_模块3_股东结构标准.md）
"""
import io
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
SEEDD = os.path.join(HERE, 'seed')
STDD = os.path.join(SEEDD, 'm3std')
BAKD = os.path.join(HERE, 'backup')

PI = 3.141592653589793

# ---------------------------------------------------------------- 版式常量（与宝钛冻结版一致，勿改）
DONUT_VB = 240
DONUT_R = 70.0
DONUT_GAP = 2.0          # 两段弧之间的视觉缝隙（弧长）
DONUT_PT_Y = 112         # 占比文字行 y（第二行 = +19）

TW = 1000                # 股权树 SVG 宽
MARGIN = 40              # 子公司区左右外边距
BOX_W, BOX_H = 250, 46   # 主链左列小方块
ROW_GAP = 76             # 左列相邻方块 y 间距
TOP_Y = 14
RGHT_X, RGHT_W = 570, 300  # 主链最后一个方块（右侧、更宽）
BAR_H = 56
BAR_DY = 96              # 公司主条 y = 左列最后一个方块 y + 96
CHILD_W, CHILD_H = 100, 212
CHILD_DROP = 66          # 子公司盒顶 y = 主条底 + 66
CHILD_PILL_CY = 29       # 比例药丸中心 = 主条底 + 29
ARR = 10                 # 箭头高
BOTTOM_PAD = 30          # SVG 底部留白


# ================================================================ 小工具
def _tspan_text(cx, top, text, lh, boxh, color='#ffffff', fs=14, weight=700):
    """竖排文字：每字一行，整块在盒子内垂直居中（子公司名用）。"""
    block = len(text) * lh
    y0 = top + (boxh - block) / 2.0 + lh * 0.78
    out = ['<tspan x="%.1f" y="%.1f">%s</tspan>' % (cx, y0 + i * lh, ch)
           for i, ch in enumerate(text)]
    return ('<text text-anchor="middle" fill="%s" font-size="%.1f" font-weight="%d" '
            'letter-spacing="0">%s</text>' % (color, fs, weight, ''.join(out)))


def _hbox(x, y, w, h, label, fill, fs=15, weight=700, rx=8, shadow=False, color='#ffffff'):
    """横向方框 + 居中文字（主链方块 / 公司主条用）。"""
    return ('<rect x="%d" y="%d" width="%d" height="%d" rx="%d" fill="%s"%s/>\n        '
            '<text x="%.1f" y="%.1f" text-anchor="middle" fill="%s" font-size="%d" '
            'font-weight="%d">%s</text>'
            % (x, y, w, h, rx, fill, ' filter="url(#sh3sh)"' if shadow else '',
               x + w / 2.0, y + h / 2.0 + fs * 0.36, color, fs, weight, label))


def _varrow(cx, y_from, y_to, pct, pill):
    """竖向箭头：y_from（上方块底）→ y_to（下方块顶）。pill=True 时带白底药丸。"""
    out = ['<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#c8102e" stroke-width="2"/>'
           % (cx, y_from, cx, y_to - 6),
           '<path d="M%d,%d L%d,%d L%d,%d Z" fill="#c8102e"/>'
           % (cx - 5, y_to - 8, cx + 5, y_to - 8, cx, y_to)]
    if not pct:
        return ''.join(out)
    if pill:
        w = max(76, 9 * len(pct) + 22)
        cy = (y_from + y_to) // 2
        out.append('<rect x="%d" y="%d" width="%d" height="18" rx="9" fill="#ffffff"/>'
                   '<text x="%d" y="%d" text-anchor="middle" fill="#8c0a20" font-size="12.5" '
                   'font-weight="700">%s</text>' % (cx + 11, cy - 9, w, cx + 11 + w // 2, cy + 4, pct))
    else:
        out.append('<text x="%d" y="%d" fill="#8c0a20" font-size="12.5" font-weight="700">%s</text>'
                   % (cx + 12, y_to - 11, pct))
    return ''.join(out)


# ================================================================ ① 环形占比
def _donut(spec):
    b = spec['donut']['buckets']
    assert len(b) == 2, '标准环形图固定两个筐（国企 / 其他），当前 %d 个' % len(b)
    a0, a1 = b[0]['pct'], b[1]['pct']
    assert abs(a0 + a1 - 100) < 0.51, '两筐占比合计须为 100%%，当前 %s + %s' % (a0, a1)
    C = 2 * PI * DONUT_R
    L0, L1 = C * a0 / 100.0, C * a1 / 100.0
    d0 = '%.2f %.2f' % (L0 - DONUT_GAP, C - L0 + DONUT_GAP)
    d1 = '%.2f %.2f' % (L1 - DONUT_GAP, C - L1 + DONUT_GAP)
    off = '%.2f' % (-L0)

    def lab(i):
        """标签默认落在该扇形的角平分线上（半径 70 的弧形带正中），保证小占比的标签
        不会跑到另一段弧上；`lx`/`ly` 可显式覆写 —— 宝钛范例（近似五五分）用的就是
        对称硬编码 (190,112)/(50,112)，属冻结参数，勿改。"""
        bb = b[i]
        mid = (sum(x['pct'] for x in b[:i]) + bb['pct'] / 2.0) * 3.6   # 12 点起顺时针
        rad = math.radians(mid)
        ax = 120 + DONUT_R * math.sin(rad)
        ay = 120 - DONUT_R * math.cos(rad)
        return int(bb.get('lx', round(ax))), int(bb.get('ly', round(ay)))

    (x0, y0), (x1, y1) = lab(0), lab(1)

    def txt(x, y, s):
        return ('        <text x="%d" y="%d" text-anchor="middle" fill="#ffffff" '
                'font-size="14.5" font-weight="700">%s</text>' % (x, y, s))

    aria = spec['donut'].get('aria') or ('股东性质占比：%s约%s%%，%s约%s%%'
                                         % (b[0]['label'], a0, b[1]['label'], a1))
    out = ['        <div class="sh3-donut">',
           '      <svg viewBox="0 0 %d %d" role="img" aria-label="%s">' % (DONUT_VB, DONUT_VB, aria),
           '        <defs>',
           '          <linearGradient id="sh3dR" x1="0" y1="0" x2="1" y2="1">',
           '            <stop offset="0" stop-color="%s"/><stop offset="1" stop-color="%s"/>'
           % tuple(b[0].get('grad', ['#e04051', '#b80e26'])),
           '          </linearGradient>',
           '          <linearGradient id="sh3dB" x1="0" y1="0" x2="1" y2="1">',
           '            <stop offset="0" stop-color="%s"/><stop offset="1" stop-color="%s"/>'
           % tuple(b[1].get('grad', ['#4a90d9', '#215f9e'])),
           '          </linearGradient>',
           '        </defs>',
           '        <circle cx="120" cy="120" r="70" fill="none" stroke="#f5ebed" stroke-width="54"/>',
           '        <g transform="rotate(-90 120 120)">',
           '          <circle cx="120" cy="120" r="70" fill="none" stroke="url(#sh3dR)" stroke-width="54"',
           '                  stroke-dasharray="%s"/>' % d0,
           '          <circle cx="120" cy="120" r="70" fill="none" stroke="url(#sh3dB)" stroke-width="54"',
           '                  stroke-dasharray="%s" stroke-dashoffset="%s"/>' % (d1, off),
           '        </g>',
           txt(x0, y0, b[0]['label']),
           txt(x0, y0 + 19, '%s%%' % a0),
           txt(x1, y1, b[1]['label']),
           txt(x1, y1 + 19, '%s%%' % a1),
           '      </svg>',
           '      <div class="sh3-hole">']
    if spec.get('logo_b64'):
        out.append('        <img src="data:image/png;base64,%s" alt="%s logo">'
                   % (spec['logo_b64'], spec['name']))
    out += ['        <div class="nm">%s</div>' % spec['name'],
            '        <div class="cd">%s.%s</div>' % (spec['code'], spec.get('exch', 'SH')),
            '      </div>',
            '    </div>']
    return '\n'.join(out)


# ================================================================ ② 图例 / 指标 / 解读
def _legend(items):
    out = ['        <div class="sh3-leg">']
    for it in items:
        out += ['          <div class="it">',
                '            <div class="hd"><span class="dot" style="background:%s"></span>%s</div>'
                % (it['color'], it['hd']),
                '            <div class="big">%s<small>%s</small></div>' % (it['big'], it.get('unit', '')),
                '            <div class="sub">%s</div>' % it.get('sub', ''),
                '          </div>']
    out.append('        </div>')
    return '\n'.join(out)


def _stats(items):
    out = ['        <div class="sh3-stats">']
    for it in items:
        out.append('          <div class="it%s"><div class="k">%s</div>'
                   '<div class="v">%s<small>%s</small></div></div>'
                   % (' gold' if it.get('gold') else '', it['k'], it['v'], it.get('u', '')))
    out.append('        </div>')
    return '\n'.join(out)


def _ul(items):
    return '\n'.join(['        <ul class="sh3-ul">']
                     + ['          <li>%s</li>' % s for s in items]
                     + ['        </ul>'])


# ================================================================ ③ 前十大股东表
def _table(t):
    head = t.get('head') or ['股东名称', '性质', '持股(股)', '占比']
    rows = ['          <tr>' + ''.join('<th>%s</th>' % h for h in head) + '</tr>']
    for r in t['rows']:
        rows.append('          <tr>' + ''.join('<td>%s</td>' % c for c in r) + '</tr>')
    if t.get('sum'):
        # ★★ 2026-10-16 血案：规格里把 sum 写成**字符串**（而不是列表）时，
        #    `for c in t['sum']` 会**逐字符**迭代 ⇒ 合计行变成几十个单字格，
        #    表格被撑到 1400+px、横向溢出卡片（探针报 card-overflow=1）。
        #    实测 000707：sum 写成 "前十大股东合计 17,811.61 万股 · 占 30.46%"
        #    ⇒ 31 个 <td>、表格 1467px > 卡片 1058px。此处显式拦住。
        assert isinstance(t['sum'], (list, tuple)), \
            'top10.sum 必须是列表（与 head 同列数），当前是 %s' % type(t['sum']).__name__
        assert len(t['sum']) == len(head), \
            'top10.sum 有 %d 列、head 有 %d 列，对不齐' % (len(t['sum']), len(head))
        rows.append('          <tr>%s</tr>'
                    % ''.join('<td>%s</td>' % (c if c == '—' else '<strong>%s</strong>' % c)
                              for c in t['sum']))
    return '<table>\n%s\n        </table>' % '\n'.join(rows)


# ================================================================ ④ 股权结构树
def _tree(t, svg_hint):
    chain = t['chain']
    bar = t['bar']
    kids = t.get('children') or []
    assert len(chain) >= 2, '主链至少两级'

    left, last = chain[:-1], chain[-1]
    ys = [TOP_Y + i * ROW_GAP for i in range(len(left))]
    y_last = ys[-1]
    bar_y = y_last + BAR_DY
    bar_bot = bar_y + BAR_H
    th = (bar_bot + CHILD_DROP + CHILD_H + BOTTOM_PAD) if kids else (bar_bot + 24)

    parts = ["""<defs>
          <linearGradient id="sh3g1" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stop-color="#d92b40"/><stop offset="1" stop-color="#bb0f28"/>
          </linearGradient>
          <linearGradient id="sh3g2" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stop-color="#c8102e"/><stop offset="1" stop-color="#8c0a20"/>
          </linearGradient>
          <linearGradient id="sh3g3" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="#dc3048"/><stop offset="1" stop-color="#c2112c"/>
          </linearGradient>
          <filter id="sh3sh" x="-25%" y="-25%" width="150%" height="150%">
            <feDropShadow dx="0" dy="2.5" stdDeviation="3.2" flood-color="#8c0a20" flood-opacity="0.26"/>
          </filter>
        </defs>"""]

    # 左列方块 + 竖向短箭头（比例标注取自**下一级**节点；除最后一跳外不带药丸）
    for i, nm in enumerate(left):
        parts.append(_hbox(125, ys[i], BOX_W, BOX_H, nm['label'], 'url(#sh3g1)'))
        if i < len(left) - 1:
            parts.append(_varrow(125 + BOX_W / 2.0, ys[i] + BOX_H, ys[i + 1],
                                 left[i + 1].get('pct') or '', False))
    # 横向箭头：左列最后一个 → 右侧方块（白底药丸居中于连线）
    cx_last = RGHT_X + RGHT_W / 2.0
    hy = y_last + BOX_H / 2.0
    hx0, hx1 = 125 + BOX_W, RGHT_X - 8
    hpct = last.get('pct') or ''
    hw = max(82, 9 * len(hpct) + 28)
    hcx = last.get('pill_x') or ((hx0 + RGHT_X) // 2)
    hline = ('<line x1="%d" y1="%.0f" x2="%d" y2="%.0f" stroke="#c8102e" stroke-width="2"/>'
             '<path d="M%d,%.0f L%d,%.0f L%d,%.0f Z" fill="#c8102e"/>'
             % (hx0, hy, hx1, hy, hx1 - 2, hy - 5, hx1 - 2, hy + 5, RGHT_X, hy))
    if hpct:   # 非持股关系（如行政隶属）不画比例药丸
        hline += ('<rect x="%d" y="%.0f" width="%d" height="18" rx="9" fill="#ffffff"/>'
                  '<text x="%d" y="%.0f" text-anchor="middle" fill="#8c0a20" font-size="12.5" '
                  'font-weight="700">%s</text>' % (hcx - hw // 2, hy - 17, hw, hcx, hy - 4, hpct))
    parts.append(hline)
    parts.append(_hbox(RGHT_X, y_last, RGHT_W, BOX_H, last['label'], 'url(#sh3g1)'))
    # 竖向箭头：右侧方块 → 公司主条（带白底药丸）
    parts.append(_varrow(cx_last, y_last + BOX_H, bar_y, bar.get('pct') or '', True))
    # 公司主条
    parts.append(_hbox(MARGIN, bar_y, TW - 2 * MARGIN, BAR_H, bar['label'],
                       'url(#sh3g2)', fs=17, weight=800, shadow=True))
    # 子公司一排
    if kids:
        n = len(kids)
        if n == 1:
            centers = [TW / 2.0]
        else:
            bgap = (TW - 2.0 * MARGIN - n * CHILD_W) / (n - 1.0)
            centers = [MARGIN + CHILD_W / 2.0 + i * (CHILD_W + bgap) for i in range(n)]
        for cx, k in zip(centers, kids):
            by = bar_bot + CHILD_DROP
            # pct 为 None / '' → 比例未披露：只画一根完整竖线，药丸处留空（不编造、不写「未披露」字样）
            if k.get('pct'):
                pw = k.get('pct_w', 56)
                parts.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="#c8102e" stroke-width="2"/>'
                             % (cx, bar_bot, cx, bar_bot + CHILD_PILL_CY - 9))
                parts.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="#c8102e" stroke-width="2"/>'
                             % (cx, bar_bot + CHILD_PILL_CY + 9, cx, bar_bot + CHILD_DROP - ARR))
                parts.append('<path d="M%.1f,%d L%.1f,%d L%.1f,%d Z" fill="#c8102e"/>'
                             % (cx - 5.5, by - ARR, cx + 5.5, by - ARR, cx, by))
                parts.append('<rect x="%.1f" y="%d" width="%d" height="18" rx="9" fill="#ffffff" '
                             'stroke="#f0dfe2" stroke-width="1"/>'
                             % (cx - pw / 2.0, bar_bot + CHILD_PILL_CY - 9, pw))
                parts.append('<text x="%.1f" y="%d" text-anchor="middle" fill="#8c0a20" '
                             'font-size="11.5" font-weight="700">%s</text>'
                             % (cx, bar_bot + CHILD_PILL_CY + 4.5, k['pct']))
            else:
                parts.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="#c8102e" '
                             'stroke-width="2" stroke-dasharray="4 3"/>'
                             % (cx, bar_bot, cx, bar_bot + CHILD_DROP - ARR))
                parts.append('<path d="M%.1f,%d L%.1f,%d L%.1f,%d Z" fill="#c8102e"/>'
                             % (cx - 5.5, by - ARR, cx + 5.5, by - ARR, cx, by))
            parts.append('<rect x="%.1f" y="%d" width="%d" height="%d" rx="8" fill="url(#sh3g3)"/>'
                         % (cx - CHILD_W / 2.0, by, CHILD_W, CHILD_H))
            parts.append(_tspan_text(cx, by, k['label'], 15.2, CHILD_H))

    return ('<div class="sh3-tree">\n      '
            '<svg viewBox="0 0 %d %d" role="img" aria-label="%s">\n        %s\n      '
            '</svg>\n      <p class="cap">%s</p>\n    </div>'
            % (TW, th, t.get('aria') or (svg_hint + '股权结构图'),
               '\n        '.join(parts), t['cap']))


# ================================================================ 组装
def build(spec):
    t = spec.get('titles') or {}
    return '\n'.join([
        '<div class="sh3-top">',
        '      <div>',
        '        <h3>%s</h3>' % t.get('donut', '股东性质占比'),
        _donut(spec),
        _legend(spec['legend']),
        '      </div>',
        '      <div>',
        '        <h3>%s</h3>' % t.get('stats', '关键持股指标'),
        _stats(spec['stats']),
        '        <h3>%s</h3>' % t.get('read', '股权特点解读'),
        _ul(spec['read']),
        '      </div>',
        '    </div>',
        '    <h3>%s</h3>' % t.get('top10', '前十大股东明细'),
        '    %s' % _table(spec['top10']),
        '    <h3>%s</h3>' % t.get('tree', '股权结构图'),
        '    %s' % _tree(spec['tree'], spec['name']),
        '    <p class="src"><b>来源：</b>%s</p>' % spec['src'],
    ])


# ================================================================ 规格 / 落盘
def spec_path(code):
    return os.path.join(STDD, 'm3_%s.json' % code)


def load_spec(code):
    p = spec_path(code)
    assert os.path.exists(p), '规格不存在：%s' % p
    spec = json.load(io.open(p, encoding='utf-8'))
    lg = os.path.join(STDD, 'logo_%s.b64' % code)
    if spec.get('logo') and os.path.exists(lg):
        spec['logo_b64'] = io.open(lg).read().strip()
    return spec


def seed_mod_html(code):
    p = os.path.join(SEEDD, 'report_%s.json' % code)
    if not os.path.exists(p):
        return None, None
    d = json.load(io.open(p, encoding='utf-8'))
    for m in d.get('mods', []):
        if str(m.get('no')) == '3':
            return d, m.get('html') or ''
    return d, None


def write_seed(code, html):
    d, _ = seed_mod_html(code)
    assert d is not None, 'seed 不存在：seed/report_%s.json' % code
    os.makedirs(BAKD, exist_ok=True)
    ts = time.strftime('%Y%m%d-%H%M%S')
    bp = os.path.join(BAKD, 'seed_%s_m3_%s.json' % (code, ts))
    io.open(bp, 'w', encoding='utf-8').write(json.dumps(
        {'ts': ts, 'code': code, 'mod': [m for m in d['mods'] if str(m['no']) == '3'][0]},
        ensure_ascii=False))
    hit = 0
    for m in d['mods']:
        if str(m['no']) == '3':
            m['html'] = html
            hit += 1
    assert hit == 1, '模块 3 命中 %d 次' % hit
    io.open(os.path.join(SEEDD, 'report_%s.json' % code), 'w', encoding='utf-8').write(
        json.dumps(d, ensure_ascii=False, indent=1))
    print('  已写 seed/report_%s.json（旧稿备份 %s）' % (code, os.path.basename(bp)))


# ================================================================ 写库
def push(code, go=False):
    cfg = json.load(io.open(os.path.join(HERE, 'cloud.json'), encoding='utf-8'))
    rest = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % cfg['envId']
    hdr = {'Authorization': 'Bearer ' + cfg['key'], 'Content-Type': 'application/json',
           'Prefer': 'resolution=merge-duplicates,return=minimal'}

    def req(path, method='GET', body=None, timeout=120):
        data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
        r = urllib.request.Request(rest + path, data=data, headers=hdr, method=method)
        try:
            with urllib.request.urlopen(r, timeout=timeout) as resp:
                raw = resp.read().decode('utf-8', 'replace')
                return resp.status, (json.loads(raw) if raw.strip() else None)
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode('utf-8', 'replace')[:600]
        except Exception as e:
            return 0, str(e)

    html = build(load_spec(code))
    modid = '%s_m3' % code

    print('=== 1) 读线上现状 ===')
    st, live = req('wb_report_mods?id=eq.%s&select=id,no,title,html,up' % modid)
    if st != 200 or not isinstance(live, list):
        print('  读模块失败 %s %s' % (st, live))
        return False
    if len(live) != 1:
        print('  模块行数异常：%s（线上还没这篇研报？先跑 push_reports_v31.py %s）'
              % (len(live) if isinstance(live, list) else live, code))
        return False
    live_html = live[0]['html'] or ''
    print('  线上模块 3《%s》%d 字符  up=%s' % (live[0]['title'], len(live_html), live[0].get('up')))

    print('=== 2) 待写入 ===')
    print('  新正文 %d 字符（线上 %d，%+d）' % (len(html), len(live_html), len(html) - len(live_html)))
    for k, v in [('环形占比 sh3-donut', 'sh3-donut' in html),
                 ('关键指标 sh3-stats', 'sh3-stats' in html),
                 ('股权结构树 sh3-tree', 'sh3-tree' in html),
                 ('前十大股东表', '前十大股东明细' in html)]:
        print('    %-20s %s' % (k, v))
    if live_html == html:
        print('  线上已与本规格一致，无需写入 ✓')
        return True
    if not go:
        print('\n[dry-run] 未写库。加 --go 执行。')
        return True

    os.makedirs(BAKD, exist_ok=True)
    ts = time.strftime('%Y%m%d-%H%M%S')
    bp = os.path.join(BAKD, 'live_%s_m3_%s.json' % (code, ts))
    io.open(bp, 'w', encoding='utf-8').write(json.dumps({'ts': ts, 'code': code, 'mod': live},
                                                        ensure_ascii=False))
    print('=== 3) 备份线上现状 → %s ===' % os.path.basename(bp))

    now = int(time.time() * 1000)
    st, r = req('wb_report_mods?id=eq.%s' % modid, 'PATCH', {'html': html, 'up': now})
    print('=== 4) PATCH：%s %s' % (st, '' if st < 400 else r))
    if st >= 400:
        return False
    print('=== 5) 回读核对 ===')
    st, rb = req('wb_report_mods?id=eq.%s&select=html' % modid)
    ok = st == 200 and rb[0]['html'] == html
    print('  正文逐字节一致：%s' % ok)
    st, cnt = req('wb_report_mods?report_id=eq.%s&select=id' % code)
    print('  模块总数：%d %s' % (len(cnt), '✓' if len(cnt) == 31 else '⚠ 应为 31'))
    return ok


# ================================================================ CLI
def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    flags = [a for a in sys.argv[1:] if a.startswith('--')]

    if '--list' in flags or not args:
        print('规格目录 %s：' % STDD)
        if os.path.isdir(STDD):
            for fn in sorted(os.listdir(STDD)):
                m = re.match(r'm3_(\w+)\.json$', fn)
                if not m:
                    continue
                code = m.group(1)
                try:
                    html = build(load_spec(code))
                except Exception as e:
                    print('  %-8s 规格有误：%s' % (code, e))
                    continue
                _, cur = seed_mod_html(code)
                print('  %-8s seed=%-7s 生成=%-7s 一致=%s'
                      % (code, len(cur) if cur is not None else '-', len(html), cur == html))
        return

    code = args[0]
    html = build(load_spec(code))
    if '--dump' in flags:
        p = args[1] if len(args) > 1 else '/tmp/m3_%s_new.html' % code
        io.open(p, 'w', encoding='utf-8').write(html)
        print('  已输出 %s（%d 字符）' % (p, len(html)))

    _, cur = seed_mod_html(code)
    same = (cur == html)
    print('生成 %d 字符；seed 现状 %s；一致=%s'
          % (len(html), ('%d 字符' % len(cur)) if cur is not None else '（无模块3）', same))

    if '--write' in flags:
        if same:
            print('  与 seed 现状一致，未改动')
        else:
            write_seed(code, html)
    if '--push' in flags:
        ok = push(code, go=('--go' in flags))
        print('\n%s' % ('完成 ✓' if ok else '失败 ⚠'))


if __name__ == '__main__':
    main()
