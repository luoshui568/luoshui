# -*- coding: utf-8 -*-
"""「产业链全景图」统一生成器 —— 全站研报唯一的制作通道。

为什么有这个文件
----------------
用户 2026-10-14 要求：宝钛股份的「产业链结构」要加一张**上中下游全景流程图**
（比 PPT 里那张更详细，且要把上中下游的**详细比例**标出来），定稿后同步到所有研报。

照 `mkmod3_std.py` 的老办法，把「版式」与「数据」彻底分开：

    规格 JSON（只装数据）  →  mkchain_std.py（只管版式）  →  产业链图 HTML

骨架（顺序与类名都不可改）
--------------------------
  `<h3>产业链全景图（上中下游）</h3>`
  → `.iflow`        自适应 SVG：三条**泳道横幅**（上游/中游/下游）+ 环节节点 + 比例徽章 + 正交箭头
  → `.ifbars`       三段比例尺面板（上游·资源集中度 / 中游·中国占全球 / 下游·消费结构）
  → `<p class="if-note">`  图注（口径与来源）

插入位置：模块 22 正文里 `.logic`（产业链卡点识别）之前，原有「概览卡片」原样保留。

CSS 在 `build/report_theme.css` 的「产业链全景图」标记块里（由 `mkchain_css.py` 幂等写入）；
本文件只产 HTML，不碰 CSS。

用法
----
    python3 mkchain_std.py --list                # 列出现有规格
    python3 mkchain_std.py 600456                # 生成组件并报字符数
    python3 mkchain_std.py 600456 --dump /tmp/x.html
    python3 mkchain_std.py 600456 --write        # 备份后写进 seed/report_600456.json 的模块 22
    python3 mkchain_std.py 600456 --push         # dry-run
    python3 mkchain_std.py 600456 --push --go    # 写库 + 备份 + 回读核对

规格文件：`build/seed/chainstd/chain_<code>.json`
"""
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
SEEDD = os.path.join(HERE, 'seed')
STDD = os.path.join(SEEDD, 'chainstd')
BAKD = os.path.join(HERE, 'backup')

MOD_NO = '22'            # 产业链结构 = 模块 22
MK_S = '<!--CHAIN-IFLOW-START-->'
MK_E = '<!--CHAIN-IFLOW-END-->'

# ---------------------------------------------------------------- 版式常量（勿改）
VB_W = 1040              # SVG 坐标宽（实际按容器等比缩放）
VB_H = 376               # SVG 坐标高（可用规格 h 覆盖）
LANE_Y, LANE_H = 12, 40  # 泳道横幅
NOTCH = 20               # 横幅燕尾深度
NODE_RX = 10
BADGE_H = 19
BADGE_DY = 9             # 徽章顶 = 节点底 + 9
FS_T, FS_S = 13.5, 9.6   # 节点主标题 / 副行字号
FS_B, FS_C = 11, 10.5    # 徽章 / 下游条字号

# 色板（深红体系，与全站一致）
C_MAIN = '#c8102e'
C_MID = '#d0202f'
C_DEEP = '#4a0a15'
C_LINE = '#f0dfe2'
C_TXT = '#8c0a20'


# ================================================================ 小工具
def _tw(s, fs):
    """粗略估算文本宽度：汉字按 1.0em，其余按 0.55em。"""
    return sum(fs * (1.0 if ord(ch) > 0x2E80 else 0.55) for ch in str(s))


def _esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _lane_path(x, y, w, h, first, last):
    """泳道横幅：非首条左端凹进（燕尾），非末条右端凸出。"""
    r = x + w
    sx = x if first else x + NOTCH
    rx = r if last else r - NOTCH
    d = [(sx, y), (rx, y)]
    if last:
        d.append((r, y + h))
    else:
        d += [(r, y + h / 2.0), (rx, y + h)]
    d.append((sx, y + h))
    if not first:
        d.append((x, y + h / 2.0))
    return 'M' + ' L'.join('%.1f,%.1f' % p for p in d) + ' Z'


def _lane(l, first, last):
    cx = l['x'] + l['w'] / 2.0
    out = ['<path d="%s" fill="url(#cflg)" stroke="rgba(255,255,255,.30)" stroke-width="1"/>'
           % _lane_path(l['x'], LANE_Y, l['w'], LANE_H, first, last),
           '<text x="%.1f" y="%.1f" text-anchor="middle" fill="#fff" font-size="15" '
           'font-weight="800" letter-spacing="1.6">%s</text>'
           % (cx, LANE_Y + LANE_H / 2.0 + (1.0 if l.get('sub') else 5.5), _esc(l['label']))]
    if l.get('sub'):
        out.append('<text x="%.1f" y="%.1f" text-anchor="middle" fill="rgba(255,255,255,.80)" '
                   'font-size="10" font-weight="600" letter-spacing=".6">%s</text>'
                   % (cx, LANE_Y + LANE_H - 7.0, _esc(l['sub'])))
    return ''.join(out)


def _node(n):
    """环节节点：红底圆角块（标题 + 关键数据），下面挂比例徽章。"""
    x, y, w, h = n['x'], n['y'], n['w'], n['h']
    cx = x + w / 2.0
    has_sub = bool(n.get('s'))
    ty = y + h / 2.0 + (4.0 if not has_sub else -5.5)
    out = ['<rect x="%d" y="%d" width="%d" height="%d" rx="%d" fill="url(#cfill)" '
           'stroke="rgba(255,255,255,.30)" stroke-width="1"/>' % (x, y, w, h, NODE_RX),
           '<text x="%.1f" y="%.1f" text-anchor="middle" fill="#fff" font-size="%.1f" '
           'font-weight="800" letter-spacing=".3">%s</text>' % (cx, ty, FS_T, _esc(n['t']))]
    if has_sub:
        out.append('<text x="%.1f" y="%.1f" text-anchor="middle" fill="rgba(255,255,255,.84)" '
                   'font-size="%.1f" font-weight="500">%s</text>'
                   % (cx, y + h / 2.0 + 11.5, FS_S, _esc(n['s'])))
    if n.get('v'):
        bw = max(58.0, _tw(n['v'], FS_B) + 20)
        by = y + h + BADGE_DY
        out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%d" rx="%.1f" fill="#fff" '
                   'stroke="%s" stroke-width="1"/>' % (cx - bw / 2.0, by, bw, BADGE_H, BADGE_H / 2.0, C_LINE))
        out.append('<text x="%.1f" y="%.1f" text-anchor="middle" fill="%s" font-size="%.1f" '
                   'font-weight="800">%s</text>' % (cx, by + BADGE_H / 2.0 + 4.0, C_TXT, FS_B, _esc(n['v'])))
    return ''.join(out)


def _chip(c):
    """下游应用小条：左侧红色短竖线 + 名称 + 右侧占比。"""
    x, y, w, h = c['x'], c['y'], c['w'], c['h']
    out = ['<rect x="%d" y="%d" width="%d" height="%d" rx="6" fill="#fff" stroke="%s" '
           'stroke-width="1"/>' % (x, y, w, h, C_LINE),
           '<rect x="%d" y="%d" width="3.5" height="%d" rx="1.75" fill="%s"/>'
           % (x, y + 3, h - 6, C_MAIN),
           '<text x="%.1f" y="%.1f" fill="#3d3a33" font-size="%.1f" font-weight="600">%s</text>'
           % (x + 11, y + h / 2.0 + 4.0, FS_C, _esc(c['t']))]
    if c.get('v'):
        out.append('<text x="%.1f" y="%.1f" text-anchor="end" fill="%s" font-size="11.5" '
                   'font-weight="800">%s</text>' % (x + w - 9, y + h / 2.0 + 4.0, C_TXT, _esc(c['v'])))
    return ''.join(out)


def _head(x2, y, dashed):
    return ('<path d="M%.1f,%d L%.1f,%d L%.1f,%d Z" fill="%s"/>'
            % (x2 - 8, y - 4.3, x2 - 8, y + 4.3, x2, y, C_MAIN))


def _arrow_h(x1, x2, y, dashed=False):
    d = ' stroke-dasharray="4 3"' if dashed else ''
    return ('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s" stroke-width="1.8"%s/>%s'
            % (x1, y, x2 - 7, y, C_MAIN, d, _head(x2, y, dashed)))


def _arrow_poly(pts, dashed=False):
    """折线箭头：pts 为 [(x,y), ...]，末端带箭头。"""
    d = ' stroke-dasharray="4 3"' if dashed else ''
    body = 'M%.1f,%.1f' % pts[0] + ''.join(' L%.1f,%.1f' % p for p in pts[1:-1])
    body += ' L%.1f,%.1f' % (pts[-1][0] - 7, pts[-1][1])
    return '<path d="%s" fill="none" stroke="%s" stroke-width="1.8"%s/>%s' \
           % (body, C_MAIN, d, _head(pts[-1][0], pts[-1][1], dashed))


def _edges(spec):
    by = {n['id']: n for n in spec['nodes']}
    for c in spec.get('chips', []):
        by[c['id']] = c
    out = []
    for e in spec.get('edges', []):
        a = by.get(e['from'])
        if a is None:
            raise SystemExit('边引用了不存在的起点：%s' % e.get('from'))
        k, dash = e.get('kind', 'h'), bool(e.get('dashed'))
        if k == 'fan':
            a = a
        else:
            b = by.get(e.get('to'))
            if b is None:
                raise SystemExit('边引用了不存在的终点：%s' % e.get('to'))
        axm, aym = a['x'] + a['w'] / 2.0, a['y'] + a['h'] / 2.0
        if k == 'h':
            out.append(_arrow_h(a['x'] + a['w'], b['x'], aym, dash))
        elif k == 'v':
            out.append(_arrow_poly([(axm, a['y'] + a['h']), (axm, b['y'])], dash))
        elif k == 't':      # 右侧横出 → 中点 → 竖走 → 汇入目标左侧
            xm = e.get('xm', (a['x'] + a['w'] + b['x']) / 2.0)
            out.append(_arrow_poly([(a['x'] + a['w'], aym), (xm, aym), (xm, b['y'] + b['h'] / 2.0),
                                    (b['x'], b['y'] + b['h'] / 2.0)], dash))
        elif k == 'e':      # 底部下走 → ym → 右行汇入目标左侧（x 可指定起点，避开徽章）
            x0 = e.get('x', axm)
            ym = e['ym']
            out.append(_arrow_poly([(x0, a['y'] + a['h']), (x0, ym), (b['x'], ym)], dash))
        elif k == 'fan':    # 分组括线：横出 → 竖括 → 每个下游条各一小横线
            ids = e['ids']
            ps = [by[i] for i in ids]
            xb = min(p['x'] for p in ps) - 14.0
            ymid = a['y'] + a['h'] / 2.0
            ytop = min(p['y'] + p['h'] / 2.0 for p in ps)
            ybot = max(p['y'] + p['h'] / 2.0 for p in ps)
            out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1.8"/>%s'
                       % (a['x'] + a['w'], ymid, xb - 7, ymid, C_MAIN, _head(xb, ymid, dash)))
            out.append('<path d="M%.1f,%.1f L%.1f,%.1f L%.1f,%.1f" fill="none" stroke="%s" '
                       'stroke-width="1.8" stroke-linejoin="round"/>'
                       % (xb, ytop, xb, ybot, xb, ybot, C_MAIN))
            for p in ps:
                out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1.8"/>'
                           % (xb, p['y'] + p['h'] / 2.0, p['x'], p['y'] + p['h'] / 2.0, C_MAIN))
        else:
            raise SystemExit('未知的边类型：%s' % k)
    return ''.join(out)


def build_svg(spec):
    h = spec.get('h', VB_H)
    lanes = spec['lanes']
    parts = ['<defs>',
             '<linearGradient id="cfill" x1="0" y1="0" x2="0" y2="1">'
             '<stop offset="0" stop-color="%s"/><stop offset="1" stop-color="%s"/></linearGradient>' % (C_MID, C_MAIN),
             '<linearGradient id="cflg" x1="0" y1="0" x2="1" y2="0">'
             '<stop offset="0" stop-color="%s"/><stop offset="1" stop-color="#e33a4d"/></linearGradient>' % C_DEEP,
             '</defs>']
    for i, l in enumerate(lanes):
        parts.append('<g class="ln ln-%s">%s</g>' % (l.get('key', i), _lane(l, i == 0, i == len(lanes) - 1)))
    parts.append('<g class="ed">%s</g>' % _edges(spec))
    for n in spec['nodes']:
        tip = n.get('tip') or (n['t'] + ('·' + n['s'] if n.get('s') else ''))
        parts.append('<g class="nd nd-%s" data-id="%s"><title>%s</title>%s</g>'
                     % (n.get('lane', ''), n['id'], _esc(tip), _node(n)))
    for c in spec.get('chips', []):
        parts.append('<g class="cp cp-%s" data-id="%s"><title>%s</title>%s</g>'
                     % (c.get('lane', ''), c['id'], _esc(c.get('tip') or c['t']), _chip(c)))
    return ('<svg class="if-svg" viewBox="0 0 %d %d" role="img" aria-label="%s" '
            'xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">%s</svg>'
            % (VB_W, h, _esc(spec.get('aria', '产业链全景图')), ''.join(parts)))


def build_bars(spec):
    out = ['<div class="ifbars">']
    for g in spec.get('bars', []):
        out.append('<div class="ifb ifb-%s">' % g.get('key', ''))
        out.append('<div class="ifb-h">%s</div>' % g['h'])
        out.append('<div class="ifb-rows">')
        for r in g['rows']:
            out.append('<div class="ifb-r">'
                       '<span class="ifb-l">%s</span>'
                       '<span class="ifb-t"><i style="width:%.1f%%"></i></span>'
                       '<span class="ifb-v">%s</span></div>' % (_esc(r[0]), float(r[2]), _esc(r[1])))
        out.append('</div></div>')
    out.append('</div>')
    return ''.join(out)


def build(spec):
    t = spec.get('titles') or {}
    lg = ''.join('<span class="if-lg if-lg-%s"><b>%s</b>%s</span>'
                 % (l.get('key', ''), _esc(l['label']), _esc(l.get('legend') or l.get('sub') or ''))
                 for l in spec['lanes'])
    return '\n'.join([
        MK_S,
        '<h3>%s</h3>' % t.get('flow', '产业链全景图（上中下游）'),
        '<div class="iflow">',
        '      <div class="if-legend">%s<span class="if-lg if-lg-hint">悬停任一环节可高亮其所在段</span></div>' % lg,
        '      <div class="if-scroll">%s</div>' % build_svg(spec),
        '    </div>',
        build_bars(spec),
        '    <p class="if-note"><b>读图：</b>%s</p>' % spec['note'],
        MK_E,
    ])


# ================================================================ 排版自检
def lint(spec):
    """检查文本溢出 / 徽章相撞 / 节点越出泳道 —— 同步到其他研报前必跑。"""
    bad = []
    nodes = {n['id']: n for n in spec['nodes']}
    chips = spec.get('chips', [])

    for n in spec['nodes']:
        if _tw(n['t'], FS_T) > n['w'] - 10:
            bad.append('节点标题溢出 [%s] %s（%.0f > %d）' % (n['id'], n['t'], _tw(n['t'], FS_T), n['w'] - 10))
        if n.get('s') and _tw(n['s'], FS_S) > n['w'] - 6:
            bad.append('节点副行溢出 [%s] %s（%.0f > %d）' % (n['id'], n['s'], _tw(n['s'], FS_S), n['w'] - 6))

    for c in chips:
        inner = c['w'] - 20
        need = _tw(c['t'], FS_C) + (14 if c.get('v') else 0) + (_tw(c['v'], 11.5) if c.get('v') else 0)
        if need > inner:
            bad.append('下游条溢出 [%s] %s + %s（%.0f > %d）'
                       % (c['id'], c['t'], c.get('v') or '—', need, inner))

    # 徽章相撞（同一水平带内）
    badges = []
    for n in spec['nodes']:
        if n.get('v'):
            bw = max(58.0, _tw(n['v'], FS_B) + 20)
            badges.append((n['x'] + n['w'] / 2.0 - bw / 2.0, n['x'] + n['w'] / 2.0 + bw / 2.0,
                           n['y'] + n['h'] + BADGE_DY, n['id']))
    for i in range(len(badges)):
        for j in range(i + 1, len(badges)):
            a, b = badges[i], badges[j]
            if abs(a[2] - b[2]) < BADGE_H and a[0] < b[1] and b[0] < a[1]:
                bad.append('徽章相撞 [%s] 与 [%s]' % (a[3], b[3]))

    # 节点是否落在所属泳道内
    lanes = {l.get('key'): l for l in spec['lanes']}
    for n in spec['nodes']:
        l = lanes.get(n.get('lane'))
        if l and not (n['x'] >= l['x'] - 2 and n['x'] + n['w'] <= l['x'] + l['w'] + 2):
            bad.append('节点越出泳道 [%s] %s：%d..%d 不在 %d..%d'
                       % (n['id'], n.get('lane'), n['x'], n['x'] + n['w'], l['x'], l['x'] + l['w']))
    for c in chips:
        l = lanes.get(c.get('lane'))
        if l and not (c['x'] >= l['x'] - 2 and c['x'] + c['w'] <= l['x'] + l['w'] + 2):
            bad.append('下游条越出泳道 [%s]' % c['id'])

    # 底部是否被裁
    h = spec.get('h', VB_H)
    for n in spec['nodes'] + chips:
        bot = n['y'] + n['h'] + (BADGE_H + BADGE_DY if n.get('v') else 0)
        if bot > h - 2:
            bad.append('超出画布高 [%s] 底 %d > h %d' % (n['id'], bot, h))
    return bad


# ================================================================ 规格 / 落盘
def spec_path(code):
    return os.path.join(STDD, 'chain_%s.json' % code)


def load_spec(code):
    p = spec_path(code)
    assert os.path.exists(p), '规格不存在：%s' % p
    return json.load(io.open(p, encoding='utf-8'))


def seed_mod_html(code):
    p = os.path.join(SEEDD, 'report_%s.json' % code)
    if not os.path.exists(p):
        return None, None
    d = json.load(io.open(p, encoding='utf-8'))
    for m in d.get('mods', []):
        if str(m.get('no')) == MOD_NO:
            return d, m.get('html') or ''
    return d, None


def wrap_for_seed(code, section):
    """保留模块 22 原有内容，把带标记的全景图块插到 `.logic` 之前（幂等）。"""
    d, cur = seed_mod_html(code)
    if cur is None:
        raise SystemExit('seed/report_%s.json 里没有模块 %s' % (code, MOD_NO))
    cur = re.sub(re.escape(MK_S) + r'.*?' + re.escape(MK_E) + r'\s*', '', cur, flags=re.S)
    for anchor in ('<div class="logic">', '<p class="src">'):
        if anchor in cur:
            return cur.replace(anchor, section + '\n    ' + anchor, 1)
    return cur + '\n' + section


def write_seed(code, html):
    d, _ = seed_mod_html(code)
    os.makedirs(BAKD, exist_ok=True)
    ts = time.strftime('%Y%m%d-%H%M%S')
    bp = os.path.join(BAKD, 'seed_%s_m%s_%s.json' % (code, MOD_NO, ts))
    io.open(bp, 'w', encoding='utf-8').write(json.dumps(
        {'ts': ts, 'code': code, 'mod': [m for m in d['mods'] if str(m['no']) == MOD_NO][0]},
        ensure_ascii=False))
    hit = 0
    for m in d['mods']:
        if str(m['no']) == MOD_NO:
            m['html'] = html
            hit += 1
    assert hit == 1, '模块 %s 命中 %d 次' % (MOD_NO, hit)
    io.open(os.path.join(SEEDD, 'report_%s.json' % code), 'w', encoding='utf-8').write(
        json.dumps(d, ensure_ascii=False, indent=1))
    print('  已写 seed/report_%s.json 模块 %s（旧稿备份 %s）'
          % (code, MOD_NO, os.path.basename(bp)))


# ================================================================ 写库
_REST = {}
HDR = {}


def _init_rest():
    if _REST:
        return
    cfg = json.load(io.open(os.path.join(HERE, 'cloud.json'), encoding='utf-8'))
    _REST['url'] = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % cfg['envId']
    HDR.update({'Authorization': 'Bearer ' + cfg['key'],
                'Content-Type': 'application/json',
                'Prefer': 'resolution=merge-duplicates,return=minimal'})


def _req(path, method='GET', body=None, timeout=120):
    _init_rest()
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
    r = urllib.request.Request(_REST['url'] + path, data=data, headers=HDR, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            raw = resp.read().decode('utf-8', 'replace')
            return resp.status, (json.loads(raw) if raw.strip() else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')[:600]
    except Exception as e:
        return 0, str(e)


def push(code, go=False):
    new_html = wrap_for_seed(code, build(load_spec(code)))
    modid = '%s_m%s' % (code, MOD_NO)

    print('=== 1) 读线上现状 ===')
    st, live = _req('wb_report_mods?id=eq.%s&select=id,no,title,html,up' % modid)
    if st != 200 or not isinstance(live, list) or len(live) != 1:
        print('  读模块失败 %s %s' % (st, live))
        return False
    live_html = live[0]['html'] or ''
    print('  线上模块 %s《%s》%d 字符  up=%s'
          % (live[0]['no'], live[0]['title'], len(live_html), live[0].get('up')))

    print('=== 2) 待写入 ===')
    print('  新正文 %d 字符（线上 %d，%+d）' % (len(new_html), len(live_html), len(new_html) - len(live_html)))
    for k, v in [('泳道横幅 iflow', 'class="iflow"' in new_html),
                 ('比例尺 ifbars', 'class="ifbars"' in new_html),
                 ('原概览卡片 .chain 保留', 'class="chain"' in new_html),
                 ('原卡点识别 .logic 保留', 'class="logic"' in new_html),
                 ('标记块唯一', new_html.count(MK_S) == 1 and new_html.count(MK_E) == 1)]:
        print('    %-24s %s' % (k, v))
    if live_html == new_html:
        print('  线上已与本规格一致，无需写入 ✓')
        return True
    if not go:
        print('\n[dry-run] 未写库。加 --go 执行。')
        return True

    os.makedirs(BAKD, exist_ok=True)
    ts = time.strftime('%Y%m%d-%H%M%S')
    bp = os.path.join(BAKD, 'live_%s_m%s_%s.json' % (code, MOD_NO, ts))
    io.open(bp, 'w', encoding='utf-8').write(json.dumps({'ts': ts, 'code': code, 'mod': live},
                                                        ensure_ascii=False))
    print('=== 3) 备份线上现状 → %s ===' % os.path.basename(bp))

    st, r = _req('wb_report_mods?id=eq.%s' % modid, 'PATCH',
                 {'html': new_html, 'up': int(time.time() * 1000)})
    print('=== 4) PATCH：%s %s' % (st, '' if st < 400 else r))
    if st >= 400:
        return False
    print('=== 5) 回读核对 ===')
    st, rb = _req('wb_report_mods?id=eq.%s&select=html' % modid)
    print('  正文逐字节一致：%s' % (st == 200 and rb[0]['html'] == new_html))
    st, cnt = _req('wb_report_mods?report_id=eq.%s&select=id' % code)
    print('  模块总数：%d %s' % (len(cnt), '✓' if len(cnt) == 31 else '⚠ 应为 31'))
    return st == 200


# ================================================================ CLI
def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    flags = [a for a in sys.argv[1:] if a.startswith('--')]

    if '--list' in flags or not args:
        print('规格目录 %s：' % STDD)
        if os.path.isdir(STDD):
            for fn in sorted(os.listdir(STDD)):
                m = re.match(r'chain_(\w+)\.json$', fn)
                if m:
                    sp = load_spec(m.group(1))
                    print('  %-8s %-6s %d 节点 / %d 下游条 / %d 比例组'
                          % (m.group(1), sp['name'], len(sp['nodes']),
                             len(sp.get('chips', [])), len(sp.get('bars', []))))
        return

    code = args[0]
    sp = load_spec(code)
    bad = lint(sp)
    print('自检：%s' % ('全部通过 ✓' if not bad else '%d 项待修 ⚠' % len(bad)))
    for b in bad:
        print('  · %s' % b)
    section = build(sp)
    if '--dump' in flags:
        p = args[1] if len(args) > 1 else '/tmp/chain_%s.html' % code
        io.open(p, 'w', encoding='utf-8').write(section)
        print('  已输出 %s' % p)
    print('组件 %d 字符' % len(section))

    if '--write' in flags:
        write_seed(code, wrap_for_seed(code, section))
    if '--push' in flags:
        print('\n%s' % ('完成 ✓' if push(code, go=('--go' in flags)) else '失败 ⚠'))


if __name__ == '__main__':
    main()
