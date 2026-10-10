# -*- coding: utf-8 -*-
"""推演「同图多系列色相去重」改后效果（复刻 JS 的 btRetint + btDistinct）。
只对线上在册的 5 份研报 seed 跑（排除 _v23 历史备份）。"""
import json, glob, os

ROOT = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
BT_MAP = {
    '#d0202f': '#d0202f', '#a30f24': '#a30f24', '#c81a33': '#c81a33',
    '#b80e26': '#a30f24', '#bb0f28': '#a30f24', '#c2112c': '#d0202f', '#d92b40': '#d0202f',
    '#dc3048': '#e43644', '#e04051': '#d0202f', '#e43644': '#e43644', '#921019': '#921019',
    '#00b0f0': '#00b0f0', '#4a90d9': '#00b0f0', '#215f9e': '#0091cc', '#3f6b85': '#3f6b85',
}
BT_PAL = ['#d0202f', '#00b0f0', '#c9a227', '#0b8a5c', '#7a5bb5', '#e0803a']
BT_SER = ['#d0202f', '#00b0f0', '#c9a227', '#0b8a5c', '#7a5bb5', '#e0803a', '#5a8fd6', '#a30f24']


def rgb(c):
    c = str(c or '')
    if len(c) == 7 and c[0] == '#':
        try:
            n = int(c[1:], 16)
            return ((n >> 16) & 255, (n >> 8) & 255, n & 255)
        except ValueError:
            return None
    return None


def gray(L):
    return '#%02x%02x%02x' % (max(0, min(255, int(round(L * 255)))),) * 1 if False else '#' + '%02x' % max(0, min(255, int(round(L * 255)))) * 3


def hsl(c):
    v = rgb(c)
    if not v:
        return None
    r, g, b = [x / 255.0 for x in v]
    mx, mn = max(r, g, b), min(r, g, b)
    d = mx - mn
    L = (mx + mn) / 2
    S = 0 if d == 0 else d / (1 - abs(2 * L - 1))
    H = 0.0
    if d:
        if mx == r:
            H = ((g - b) / d) % 6
        elif mx == g:
            H = (b - r) / d + 2
        else:
            H = (r - g) / d + 4
        H *= 60
        if H < 0:
            H += 360
    return (H, S, L)


def retint(c):
    v = rgb(c)
    if not v:
        return c
    h = '#%02x%02x%02x' % v
    if h in BT_MAP:
        return BT_MAP[h]
    H, S, L = hsl(h)
    if S < 0.26 and (H <= 40 or H >= 315):
        g = max(0, min(255, int(round(L * 255))))
        return '#%02x%02x%02x' % (g, g, g)
    if H <= 30 or H >= 335:
        return '#e0505c' if L >= .62 else ('#d0202f' if L >= .42 else ('#a30f24' if L >= .28 else '#4a0a15'))
    if 185 <= H <= 265 and S >= .20:
        return '#7fd8f7' if L >= .62 else ('#00b0f0' if L >= .42 else '#0089bd')
    return h


def fam(c):
    x = hsl(c)
    if not x:
        return 'x'
    H, S, L = x
    if S < 0.22:
        return 'gray'
    if H <= 30 or H >= 335:
        return 'red'
    if 185 <= H <= 265:
        return 'blue'
    if 36 <= H <= 60:
        return 'gold'
    if 60 < H <= 175:
        return 'green'
    if 265 < H < 335:
        return 'purple'
    return 'warm'


def name_color(name):
    n = str(name or '').upper()
    if 'PB' in n:
        return '#d0202f'
    if 'PE' in n:
        return '#00b0f0'
    return None


def clash(a, b):
    if not a or not b:
        return False
    ga, gb = a[1] < .22, b[1] < .22
    if ga and gb:
        return True
    if ga or gb:
        return False
    dh = abs(a[0] - b[0])
    if dh > 180:
        dh = 360 - dh
    return dh < 30 and abs(a[2] - b[2]) < .26


def distinct(lst):
    out, used = [], []
    for c in lst:
        x = hsl(c)
        if any(clash(x, u) for u in used):
            for pc in BT_SER:
                px = hsl(pc)
                if not any(clash(px, u) for u in used):
                    c, x = pc, px
                    break
        out.append(c)
        if x:
            used.append(x)
    return out


def ser_color(s, i):
    fb = BT_PAL[i % len(BT_PAL)]
    c = None
    ls = s.get('lineStyle') or {}
    if isinstance(ls.get('color'), str):
        c = ls['color']
    it = s.get('itemStyle') or {}
    if not c and isinstance(it.get('color'), str):
        c = it['color']
    if not c and isinstance(it.get('color'), dict) and it['color'].get('colorStops'):
        c = it['color']['colorStops'][0].get('color')
    if not c and isinstance(s.get('color'), str):
        c = s['color']
    if not c and isinstance(s.get('color'), list) and s['color'] and isinstance(s['color'][0], str):
        c = s['color'][i % len(s['color'])]
    if not c:
        ar = s.get('areaStyle') or {}
        if isinstance(ar.get('color'), dict) and ar['color'].get('colorStops'):
            c = ar['color']['colorStops'][0].get('color')
    return retint(c) if c else fb


print('=== 改后推演（线上 5 份研报）===')
nchg = 0
nch = 0
for p in sorted(glob.glob(os.path.join(ROOT, 'build', 'seed', '*.json'))):
    code = os.path.basename(p)[len('report_'):-len('.json')]
    if code.endswith('_v23'):
        continue
    d = json.load(open(p, encoding='utf-8'))
    charts = (d.get('charts') if isinstance(d, dict) else d) or []
    for ch in charts:
        ser = (ch.get('opt') or {}).get('series') or []
        if len(ser) < 2:
            continue
        nch += 1
        before = [ser_color(s, i) for i, s in enumerate(ser)]
        base = [name_color(s.get('name')) or before[i] for i, s in enumerate(ser)]
        after = distinct(base)
        if before != after:
            nchg += 1
            print('\n[%s] %s 「%s」' % (code, ch.get('id'), ch.get('name') or ''))
            for i, s in enumerate(ser):
                mark = '  ←换' if before[i] != after[i] else '    '
                print('   %-26s %s → %s%s' % (str(s.get('name'))[:26], before[i], after[i], mark))
print('\n多系列图表 %d 张，其中 %d 张会被改写色。' % (nch, nchg))
