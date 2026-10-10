# -*- coding: utf-8 -*-
"""
配色重构：去粉 + 红改参考图鲜红 + 蓝改参考图青蓝 + 金色/绿色保留。

参考色（从用户给的两张图逐像素采样）：
  红  #cd1631 -> #d82437 -> #e43644   （横向渐变，主色取 #d0202f）
  蓝  #00b0f0                          （纯青蓝）

设计原则：
  1. 红族「同族归一」：保持原有明暗层次，只把色相/饱和度拉到新红系
     —— 主红 #d0202f / 亮红 #e43644 / 深红 #a30f24 / 极深 #4a0a15
  2. 暖棕、暖灰粉、灰粉文字 → 按原明度映射到**中性灰**（这才是「太粉」的根源）
  3. 粉底 / 粉边 → 中性浅灰
  4. 红调投影（box-shadow/text-shadow）→ 中性投影（粉红阴影会让整页发粉）
  5. rgba 红底若 alpha ≤ .09（视觉上就是粉）→ 转中性
  6. 金色 #c9a227 系、绿色 #0b8a5c 系、紫 #8b5cf6 系 → **一律保留**

用法：
  python build/retint.py            # 干跑，只报告
  python build/retint.py --go       # 写盘
"""
import io, os, re, shutil, sys, time
from collections import Counter

ROOT = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
FILES = [
    os.path.join(ROOT, 'build', 'report_theme.css'),
    os.path.join(ROOT, 'deploy', 'app.template.html'),
    os.path.join(ROOT, 'deploy', 'report.template.html'),
]
GO = '--go' in sys.argv

# ============================================================
# 1. hex 精确映射
# ============================================================
HEXMAP = {
    # ---------- 红族：统一到参考图鲜红 ----------
    '#c0392b': '#d0202f',   # 旧砖红（研报页 --red，出现最多）
    '#c8102e': '#d0202f',   # 旧主红（--accent / --brand / --red）
    '#8c0a20': '#a30f24',   # 深红（--brand-deep / --red-deep）
    '#a3122a': '#b8122c',
    '#a30b23': '#b8122c',
    '#b81530': '#c81a33',
    '#b01129': '#c01a30',
    '#b8122c': '#c81a33',
    '#9c0b23': '#a30f24',
    '#9c0c24': '#a30f24',
    '#7a0a1c': '#8f0f22',
    '#87091d': '#8f0f22',
    '#831221': '#8f0f22',
    '#6d0819': '#7a0d1c',
    '#ae0e23': '#b8122c',
    '#a02626': '#b81f2c',
    '#a83228': '#b81f2c',
    '#a63a46': '#c04a56',
    '#d14b3c': '#e43644',
    '#d9342b': '#e43644',
    '#d92638': '#e43644',
    '#e63946': '#e43644',
    '#d81f38': '#e43644',
    '#dd1832': '#d0202f',
    '#d4172f': '#d0202f',
    '#b91d1c': '#d0202f',
    '#b3122e': '#d0202f',
    '#f04b58': '#e43644',
    '#e6445a': '#e43644',
    '#e05a4a': '#dd3543',
    '#d96a5c': '#dd5560',
    '#c2185b': '#d0202f',
    '#8b1a0e': '#921019',
    '#5c1a0a': '#4a2019',
    '#7c1b28': '#8f0f22',
    '#5e0715': '#5c0c18',
    '#5a0612': '#560a16',

    # ---------- 深棕红 / 暖黑 → 中性深 ----------
    '#4a0710': '#4a0a15',   # 研报页 --navy：保留极深红（权威底色）
    '#460a14': '#3a3336',
    '#3b1219': '#232326',   # 工作台 --tx
    '#26161a': '#211f22',   # 研报页 --text
    '#2b161a': '#232326',
    '#3c0d13': '#2a2a2e',
    '#3f2a30': '#333338',
    '#52121a': '#2e2e33',
    '#50282d': '#3c3c41',
    '#5b3a40': '#46464b',
    '#4c2026': '#3a3a3f',
    '#452b2e': '#3a3a3f',
    '#5a3b3b': '#46464b',
    '#52282e': '#38383d',
    '#782832': '#5c5c61',
    '#4a3f1f': '#3d3a33',

    # ---------- 暖灰粉（文字/副文字）→ 中性灰（同明度） ----------
    '#9a7d82': '#85858a',   # 研报页 --sub：全站副文字
    '#a0888d': '#8a8a8f',
    '#a88f94': '#909095',
    '#b09a9e': '#9c9ca1',
    '#b9bfc7': '#b0b0b5',
    '#aeb6bf': '#a8a8ad',
    '#c0a8ac': '#b4b4b8',
    '#c0a9b0': '#b4b4b8',
    '#d8b6bb': '#c6c6ca',
    '#dcc0c4': '#cccccf',
    '#a9868c': '#8e8e93',
    '#9a8a91': '#8a8a8f',
    '#7b5057': '#66666b',
    '#7b6770': '#6a6a6f',
    '#8a6a70': '#707075',
    '#7d5b60': '#6a6a6f',
    '#74484e': '#5f5f64',
    '#915960': '#7a7a7f',
    '#6a4a50': '#5a5a5f',
    '#64748b': '#7a7a80',

    # ---------- 粉底 / 粉边 → 中性浅灰 ----------
    '#fdf7f8': '#fafafa',   # 研报页 --bg
    '#efe0dd': '#e6e5e3',   # 研报页 --line
    '#f2dcdf': '#e6e5e3',
    '#f2dfe2': '#e8e7e5',
    '#f0dcdf': '#e6e5e3',
    '#edd6da': '#e2e1df',
    '#f0dde0': '#e6e5e3',
    '#f6dfe2': '#efecea',
    '#f6e6e9': '#efeeec',
    '#f6e7e8': '#f0efed',
    '#f4e4e7': '#efeeec',
    '#f4d4d8': '#e4e3e1',
    '#f0c7cc': '#dedddb',
    '#f6c4cb': '#dcdbd9',
    '#f6d5da': '#e4e3e1',
    '#f8c4c8': '#dedddb',
    '#fdecee': '#f1f0ee',   # --accent-soft / --brand-soft
    '#fbedee': '#f0efed',
    '#fcedef': '#f4f3f1',
    '#fdecea': '#f5f4f2',
    '#fdeaea': '#f5f4f2',
    '#fde8ea': '#f2f1ef',
    '#fdf4f5': '#f7f7f6',
    '#fff3f1': '#f8f8f7',
    '#ffe6de': '#f0efee',
    '#fff3f0': '#f7f7f6',
    '#ffe9e3': '#f0f0ee',
    '#ffddd3': '#e8e7e5',
    '#fff0f3': '#f5f5f4',
    '#fff2ee': '#f7f7f6',
    '#ffe8e2': '#f2f2f0',
    '#ffdfd6': '#ececea',
    '#ffeef0': '#f5f5f4',
    '#fff0eb': '#f5f5f4',
    '#ffe3da': '#eeedeb',
    '#ffd6c9': '#e8e7e5',
    '#eec4c4': '#dfdfdd',

    # ---------- 亮粉红 → 淡红（保留红语义，去掉粉感） ----------
    '#ffb3b3': '#e8b0b6',
    '#ff8383': '#f08a92',
    '#f4726f': '#e8696f',
    '#ff696e': '#e8696f',
    '#ff8c78': '#e87a84',
    '#f5a3a8': '#e8a6ac',
    '#f3b0b0': '#e8aeb4',
    '#d99aa3': '#c2c2c6',
    '#f3a6b0': '#e8a6ac',
    '#eb5569': '#dd4a56',
    '#f47586': '#e0606c',
    '#e9a9b3': '#e0a4ab',
    '#d97070': '#c98a90',
    '#e8939c': '#d89098',
    '#e8909a': '#d89098',
    '#dcaab0': '#c9c9cd',
    '#dcb9be': '#cbcbcf',
    '#caa2a8': '#b6b6ba',
    '#dfcacd': '#d4d4d6',
    '#f1bdc3': '#dcdcde',
    '#f5c6c0': '#dcdcde',

    # ---------- 蓝族 → 参考图青蓝 ----------
    '#2f6fb5': '#00b0f0',
    '#1d4ed8': '#00b0f0',
    '#44546a': '#3f6b85',
}

# ============================================================
# 2. rgba 前缀映射（红调 rgb 三元组 → 新三元组）
# ============================================================
RGBA_RED = {
    (200, 16, 46): (208, 32, 47),    # 工作台主红
    (192, 57, 43): (208, 32, 47),    # 研报页旧砖红
    (221, 24, 50): (208, 32, 47),    # 研报页背景红晕
    (140, 10, 32): (163, 15, 36),    # 深红
    (168, 50, 40): (176, 26, 38),
    (124, 27, 40): (143, 13, 32),
    (82, 18, 26): (58, 48, 52),      # 深棕投影 → 中性
    (120, 40, 50): (70, 68, 72),     # 粉棕
    (60, 13, 19): (34, 32, 36),
    (74, 7, 16): (74, 10, 21),       # --navy 的 rgba
    (90, 6, 18): (92, 8, 22),
    (253, 236, 238): (244, 244, 243),  # 淡粉水印 → 中性
    (255, 240, 243): (248, 248, 247),
    (255, 105, 110): (208, 32, 47),  # 珊瑚红粉光晕 → 正红
}

# 明确要压 alpha 的红晕（视觉上就是「粉」）
ALPHA_CUT = {
    'rgba(221,24,50,.12)': 'rgba(208,32,47,.028)',   # body 左上大面积红晕（粉感主犯）
    'rgba(208,32,47,.06)': 'rgba(208,32,47,.028)',   # 兼容已替换过一轮的文件
    'rgba(221,24,50,.08)': 'rgba(208,32,47,.022)',
    'rgba(221,24,50,.18)': 'rgba(208,32,47,.09)',
    'rgba(221,24,50,.28)': 'rgba(208,32,47,.14)',
    'rgba(221,24,50,.35)': 'rgba(208,32,47,.18)',
}

RGA = re.compile(r'rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*([\d.]+)\s*\)')
HEXR = re.compile(r'#[0-9a-fA-F]{6}\b')


def shadow_ctx(t, pos):
    """判断该位置是否在 shadow 声明里。"""
    seg = t[max(0, pos - 90):pos]
    return ('shadow' in seg.lower())


def hex2rgb(h):
    return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)


def hue(r, g, b):
    mx, mn = max(r, g, b), min(r, g, b)
    d = mx - mn
    if d == 0:
        return 0.0
    if mx == r:
        h = ((g - b) / d) % 6
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    return h * 60


def bt_gray_py(L):
    """同明度中性灰（与前端 btGray 同逻辑）。"""
    v = int(round(L * 255))
    v = max(0, min(255, v))
    return '#%02x%02x%02x' % (v, v, v)


def pale_neutral(h):
    """
    极淡暖白 / 粉白 → 中性。
    判据：明度 L ≥ .945 且色相落在红粉区（H ≤ 30° 或 ≥ 335°）。
    ⚠️ 刻意跳过 31°–60°：那是**金白**（#fdf8ec 一类），属金色体系要保留。
    """
    r, g, b = hex2rgb(h)
    mx, mn = max(r, g, b), min(r, g, b)
    if mx == mn:
        return None
    L = (mx + mn) / 2 / 255
    if L < 0.945:
        return None
    H = hue(r, g, b)
    if not (H <= 30 or H >= 335):
        return None
    v = int(round(L * 255))
    return '#%02x%02x%02x' % (v, v, v)


def main():
    ts = time.strftime('%Y%m%d-%H%M%S')
    bkdir = os.path.join(ROOT, 'build', 'backup', 'retint_pre_' + ts)
    if GO:
        os.makedirs(bkdir, exist_ok=True)

    total = Counter()
    for p in FILES:
        t0 = io.open(p, encoding='utf-8').read()
        t = t0
        n_hex = 0
        detail = Counter()

        # --- 阶段1：hex ---
        for k, v in HEXMAP.items():
            pat = re.compile(re.escape(k), re.I)
            c = len(pat.findall(t))
            if c:
                t = pat.sub(v, t)
                n_hex += c
                detail['hex %s→%s' % (k, v)] = c

        # --- 阶段2：精确 rgba 串（含 alpha 压降）---
        n_rgba_fix = 0
        for k, v in ALPHA_CUT.items():
            if k in t:
                c = t.count(k)
                t = t.replace(k, v)
                n_rgba_fix += c
                detail['rgba %s→%s' % (k, v)] = c

        # --- 阶段3：rgba 前缀 ---
        n_rgba = 0

        def repl(m):
            nonlocal n_rgba
            r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
            a = m.group(4)
            key = (r, g, b)
            if key not in RGBA_RED:
                return m.group(0)
            nr, ng, nb = RGBA_RED[key]
            # 红调投影 → 中性（粉红阴影是「整页发粉」的元凶）
            if shadow_ctx(t, m.start()):
                lum = int(0.299 * r + 0.587 * g + 0.114 * b)
                lum = max(40, min(150, lum))
                nr, ng, nb = lum, lum - 2, lum + 2
            # 极淡红底（alpha≤.09）视觉上就是粉 → 转中性
            elif float(a) <= 0.09 and r > 150:
                nr, ng, nb = 92, 92, 96
            n_rgba += 1
            return 'rgba(%d,%d,%d,%s)' % (nr, ng, nb, a)

        t = RGA.sub(repl, t)

        # --- 阶段4：极淡暖白/粉白 → 中性（金白自动跳过）---
        n_pale = 0

        def repl_pale(m):
            nonlocal n_pale
            nv = pale_neutral(m.group(0).lower())
            if nv is None:
                return m.group(0)
            n_pale += 1
            return nv

        t = HEXR.sub(repl_pale, t)
        n_hex += n_pale

        # --- 阶段5：浅粉/暖粉兜底（算法，覆盖低频漏网色）---
        # 只按频次列精确表会漏掉只出现一两次的浅粉边框
        # （#f4d8d8 / #efdfdd / #f8dfe2 / #f7e5e8 就是这么漏的）。
        # 判据：明度 ≥ .82 且色相落在红粉区 → 中性灰（保明度）。
        # ⚠️ 刻意跳过 36°–62°：那是金色区，必须留住。
        n_dust = 0

        def repl_dust(m):
            nonlocal n_dust
            h = m.group(0).lower()
            r, g, b = hex2rgb(h)
            mx, mn = max(r, g, b), min(r, g, b)
            if mx == mn:
                return m.group(0)
            L = (mx + mn) / 2 / 255
            if L < 0.82:
                return m.group(0)
            H = hue(r, g, b)
            if not (H <= 35 or H >= 330):
                return m.group(0)
            n_dust += 1
            return bt_gray_py(L)

        t = HEXR.sub(repl_dust, t)
        n_hex += n_dust
        total['hex'] += n_hex
        total['rgba'] += n_rgba + n_rgba_fix
        name = os.path.basename(p)
        print('=' * 72)
        print('%s   %d → %d 字符' % (name, len(t0), len(t)))
        print('  hex 替换 %d 处（极淡粉白 %d + 浅粉兜底 %d）/ rgba 替换 %d 处'
              % (n_hex, n_pale, n_dust, n_rgba + n_rgba_fix))

        # 残留粉调扫描
        left = Counter()
        for m in HEXR.finditer(t):
            h = m.group(0).lower()
            r, g, b = int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)
            mx, mn = max(r, g, b), min(r, g, b)
            if mx == mn:
                continue
            L = (mx + mn) / 2 / 255
            # 粉：R 最高、GB 接近、明度偏高
            if r >= g >= b and (r - b) < 60 and L > 0.80:
                left[h] += 1
        if left:
            print('  ⚠️ 残留浅粉 %d 种: %s' % (len(left), ' '.join('%s×%d' % kv for kv in left.most_common(12))))
        else:
            print('  ✅ 无残留浅粉')

        if GO:
            dst = os.path.join(bkdir, name)
            io.open(dst, 'w', encoding='utf-8', newline='').write(t0)
            io.open(p, 'w', encoding='utf-8', newline='').write(t)
            print('  已备份 → %s' % dst)

    print()
    print('=' * 72)
    print('合计：hex %d 处 / rgba %d 处' % (total['hex'], total['rgba']))
    if not GO:
        print('（干跑模式，未写盘。加 --go 执行）')


main()
