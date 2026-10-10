# -*- coding: utf-8 -*-
"""重建宝钛股份（600456）研报模块 3「股东结构」。

设计：
  · 左：股权性质占比环形图（红=国企 / 蓝=其他），**环心放公司 logo**
  · 右：关键持股指标 + 股权特点解读
  · 中：前十大股东明细（数据沿用原稿，未改动）
  · 下：股权结构树状图（陕西省人民政府 → 陕西有色集团 → 宝钛集团 → 宝鸡钛业 → 8 家子公司）

数据来源（不编造，逐项可追溯）：
  · 股东明细 / 总市值 / 国企外流通市值 → 原模块 3 稿（取自 2026-08 宝钛股份研究报告 PPTX 幻灯片 4）
  · 股权链 100% / 93.36% → 同 PPTX 幻灯片 5
  · 宝钛集团→上市公司 49.40% → 幻灯片 4 的十大股东表（236,018,951 股 ÷ 总股本 4.7777 亿股，
    与「前十大合计 266,204,953 股 = 55.72%」自洽）。幻灯片 5 图上写的 47.77% 与两处口径冲突，判为旧值，不采用。
  · 子公司名单与持股 → 同 PPTX 幻灯片 5 / 幻灯片 6
用法： python mkmod3.py
"""
import io, os, json, base64

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SEEDP = os.path.join(HERE, 'seed', 'report_600456.json')
LOGOP = os.path.join(HERE, '_logo_out', 'bt_mark_q.png')

logo_b64 = base64.b64encode(open(LOGOP, 'rb').read()).decode('ascii')
print('logo b64 = %d chars' % len(logo_b64))

# ------------------------------------------------------------------ 环形图
C = 2 * 3.141592653589793 * 70.0          # 周长 439.82
RED = C * 0.55
BLUE = C * 0.45
GAP = 2.0
red_dash = '%.2f %.2f' % (RED - GAP, C - RED + GAP)
blue_dash = '%.2f %.2f' % (BLUE - GAP, C - BLUE + GAP)
blue_off = '%.2f' % (-RED)

DONUT = """<div class="sh3-donut">
      <svg viewBox="0 0 240 240" role="img" aria-label="股东性质占比：国企约55%，其他约45%">
        <defs>
          <linearGradient id="sh3dR" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stop-color="#e04051"/><stop offset="1" stop-color="#b80e26"/>
          </linearGradient>
          <linearGradient id="sh3dB" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stop-color="#4a90d9"/><stop offset="1" stop-color="#215f9e"/>
          </linearGradient>
        </defs>
        <circle cx="120" cy="120" r="70" fill="none" stroke="#f5ebed" stroke-width="54"/>
        <g transform="rotate(-90 120 120)">
          <circle cx="120" cy="120" r="70" fill="none" stroke="url(#sh3dR)" stroke-width="54"
                  stroke-dasharray="__RED__"/>
          <circle cx="120" cy="120" r="70" fill="none" stroke="url(#sh3dB)" stroke-width="54"
                  stroke-dasharray="__BLUE__" stroke-dashoffset="__OFF__"/>
        </g>
        <text x="190" y="112" text-anchor="middle" fill="#ffffff" font-size="14.5" font-weight="700">国企</text>
        <text x="190" y="131" text-anchor="middle" fill="#ffffff" font-size="14.5" font-weight="700">55%</text>
        <text x="50" y="112" text-anchor="middle" fill="#ffffff" font-size="14.5" font-weight="700">其他</text>
        <text x="50" y="131" text-anchor="middle" fill="#ffffff" font-size="14.5" font-weight="700">45%</text>
      </svg>
      <div class="sh3-hole">
        <img src="data:image/png;base64,__LOGO__" alt="宝钛股份 logo">
        <div class="nm">宝钛股份</div>
        <div class="cd">600456.SH</div>
      </div>
    </div>"""
DONUT = (DONUT.replace('__RED__', red_dash).replace('__BLUE__', blue_dash)
              .replace('__OFF__', blue_off).replace('__LOGO__', logo_b64))

# ------------------------------------------------------------------ 股权树
TW, TH = 1000, 550
GRAD = """<defs>
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
        </defs>"""


def tspan_text(cx, top, text, lh, boxh, color='#ffffff', fs=14, weight=700):
    """竖排文字：每个字一行，整块在盒子内垂直居中。"""
    block = len(text) * lh
    y0 = top + (boxh - block) / 2.0 + lh * 0.78
    out = []
    for i, ch in enumerate(text):
        out.append('<tspan x="%.1f" y="%.1f">%s</tspan>' % (cx, y0 + i * lh, ch))
    return ('<text text-anchor="middle" fill="%s" font-size="%.1f" font-weight="%d" '
            'letter-spacing="0">%s</text>' % (color, fs, weight, ''.join(out)))


def hbox(x, y, w, h, label, fill, fs=15, weight=700, rx=8, shadow=False, color='#ffffff'):
    return ('<rect x="%d" y="%d" width="%d" height="%d" rx="%d" fill="%s"%s/>\n        '
            '<text x="%.1f" y="%.1f" text-anchor="middle" fill="%s" font-size="%d" '
            'font-weight="%d">%s</text>'
            % (x, y, w, h, rx, fill, ' filter="url(#sh3sh)"' if shadow else '',
               x + w / 2.0, y + h / 2.0 + fs * 0.36, color, fs, weight, label))


SUBS = [('宝钛华神钛业有限公司', '66.67%'),
        ('宝钛精密锻造有限公司', '40%'),
        ('宝太新金属开发有限公司', '51%'),
        ('宝钛合金材料有限公司', '51%'),
        ('宝钛航空材料有限公司', '100%'),
        ('宝钛久立钛焊管科技有限公司', '34%'),
        ('宝钛(沈阳)销售有限公司', '100%'),
        ('宝钛新材料科技有限公司', '100%')]

# 关键：父条与 8 个子盒使用**同一栅格**（都由 MARGIN 推导），箭头才能垂直对齐。
# 旧版父条固定 120..880 而子盒跨 22..978，最左/最右两支箭头正上方没有父条 → 悬空。
MARGIN = 40
BW = 100
BGAP = (TW - 2.0 * MARGIN - 8 * BW) / 7.0          # 8 盒 + 7 间隙正好铺满 40..960
BY, BH = 308, 212                                   # 子盒顶/底：308..520
centers = [MARGIN + BW / 2.0 + i * (BW + BGAP) for i in range(8)]
BAR_X, BAR_W = MARGIN, TW - 2.0 * MARGIN            # 父条 40..960，与子盒组等宽
DROP_Y0 = 242                                       # 父条底边
PILL_CY = 271                                       # 百分比药丸中心
ARR = 10                                            # 箭头高

parts = [GRAD]
# 主链
parts.append(hbox(125, 14, 250, 46, '陕西省人民政府', 'url(#sh3g1)'))
parts.append('<line x1="250" y1="60" x2="250" y2="84" stroke="#c8102e" stroke-width="2"/>'
             '<path d="M245,82 L255,82 L250,90 Z" fill="#c8102e"/>'
             '<text x="262" y="79" fill="#8c0a20" font-size="12.5" font-weight="700">100%</text>')
parts.append(hbox(125, 90, 250, 46, '陕西有色金属集团', 'url(#sh3g1)'))
# 横向：陕西有色集团 -> 宝钛集团
parts.append('<line x1="375" y1="113" x2="562" y2="113" stroke="#c8102e" stroke-width="2"/>'
             '<path d="M560,108 L560,118 L570,113 Z" fill="#c8102e"/>'
             '<rect x="430" y="96" width="82" height="18" rx="9" fill="#ffffff"/>'
             '<text x="471" y="109" text-anchor="middle" fill="#8c0a20" font-size="12.5" '
             'font-weight="700">93.36%</text>')
parts.append(hbox(570, 90, 300, 46, '宝钛集团有限公司', 'url(#sh3g1)'))
# 竖向：宝钛集团 -> 上市公司
parts.append('<line x1="720" y1="136" x2="720" y2="180" stroke="#c8102e" stroke-width="2"/>'
             '<path d="M715,178 L725,178 L720,186 Z" fill="#c8102e"/>'
             '<rect x="731" y="152" width="76" height="18" rx="9" fill="#ffffff"/>'
             '<text x="769" y="165" text-anchor="middle" fill="#8c0a20" font-size="12.5" '
             'font-weight="700">49.40%</text>')
parts.append(hbox(BAR_X, 186, BAR_W, 56, '宝鸡钛业股份有限公司（600456.SH）', 'url(#sh3g2)',
                  fs=17, weight=800, shadow=True))
for cx, (nm, pc) in zip(centers, SUBS):
    # 上段：父条底边 → 药丸上沿
    parts.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="#c8102e" '
                 'stroke-width="2"/>' % (cx, DROP_Y0, cx, PILL_CY - 9))
    # 下段：药丸下沿 → 箭头上沿
    parts.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="#c8102e" '
                 'stroke-width="2"/>' % (cx, PILL_CY + 9, cx, BY - ARR))
    # 箭头：尖端正好落在子盒顶边
    parts.append('<path d="M%.1f,%d L%.1f,%d L%.1f,%d Z" fill="#c8102e"/>'
                 % (cx - 5.5, BY - ARR, cx + 5.5, BY - ARR, cx, BY))
    parts.append('<rect x="%.1f" y="%d" width="56" height="18" rx="9" fill="#ffffff" '
                 'stroke="#f0dfe2" stroke-width="1"/>' % (cx - 28, PILL_CY - 9))
    parts.append('<text x="%.1f" y="%d" text-anchor="middle" fill="#8c0a20" font-size="11.5" '
                 'font-weight="700">%s</text>' % (cx, PILL_CY + 4.5, pc))
    parts.append('<rect x="%.1f" y="%d" width="%d" height="%d" rx="8" fill="url(#sh3g3)"/>'
                 % (cx - BW / 2.0, BY, BW, BH))
    parts.append(tspan_text(cx, BY, nm, 15.2, BH))

TREE = ('<div class="sh3-tree">\n      '
        '<svg viewBox="0 0 __TW__ __TH__" role="img" aria-label="宝钛股份股权结构图">\n        __PARTS__\n      '
        '</svg>\n      <p class="cap">股权控制链：陕西省人民政府 <b>100%</b> → 陕西有色金属集团 '
        '<b>93.36%</b> → 宝钛集团有限公司 <b>49.40%</b> → 宝鸡钛业股份有限公司<br>'
        '宝钛集团直接持股 236,018,951 股（总股本 4.7777 亿股）；'
        '宝钛久立钛焊管科技（34%）为联营企业，其余为控股子公司</p>\n    </div>')
TREE = (TREE.replace('__TW__', str(TW)).replace('__TH__', str(TH))
            .replace('__PARTS__', '\n        '.join(parts)))

# ------------------------------------------------------------------ 前十大股东
TOP10 = [('宝钛集团有限公司', '国有法人', '236,018,951', '49.40%'),
         ('香港中央结算有限公司', '其他', '15,198,391', '3.18%'),
         ('富国中证军工龙头ETF', '其他', '4,064,741', '0.85%'),
         ('国泰中证军工ETF', '其他', '1,703,022', '0.36%'),
         ('华夏中证细分有色ETF', '其他', '1,633,582', '0.34%'),
         ('洪娟儿', '其他', '1,616,000', '0.34%'),
         ('长信国防军工量化混合', '其他', '1,596,500', '0.33%'),
         ('王美兰', '其他', '1,521,000', '0.32%'),
         ('邹瀚枢', '其他', '1,470,000', '0.31%'),
         ('嘉实中证稀有金属ETF', '其他', '1,382,766', '0.29%')]
rows = '\n          '.join('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % r
                          for r in TOP10)
TBL = ('<table>\n          <tr><th>股东名称</th><th>性质</th><th>持股(股)</th><th>占比</th></tr>\n'
       '          %s\n          <tr><td><strong>合计</strong></td><td>—</td>'
       '<td><strong>266,204,953</strong></td><td><strong>55.72%%</strong></td></tr>\n'
       '        </table>' % rows)

# ------------------------------------------------------------------ 组装
HTML = """<div class="sh3-top">
      <div>
        <h3>股东性质占比</h3>
        %s
        <div class="sh3-leg">
          <div class="it">
            <div class="hd"><span class="dot" style="background:#c8102e"></span>国企（宝钛集团等）</div>
            <div class="big">约 55%%<small>· 71 亿元</small></div>
            <div class="sub">国有法人 · 宝钛集团直接持股 49.40%%</div>
          </div>
          <div class="it">
            <div class="hd"><span class="dot" style="background:#2f6fb5"></span>其他流通股东</div>
            <div class="big">约 45%%<small>· 58 亿元</small></div>
            <div class="sub">军工/有色 ETF、港股通、自然人等</div>
          </div>
        </div>
      </div>
      <div>
        <h3>关键持股指标</h3>
        <div class="sh3-stats">
          <div class="it"><div class="k">总市值</div><div class="v">129<small>亿元</small></div></div>
          <div class="it"><div class="k">国企外流通市值</div><div class="v">58<small>亿元</small></div></div>
          <div class="it gold"><div class="k">宝钛集团直接持股</div><div class="v">49.40<small>%%</small></div></div>
          <div class="it"><div class="k">前十大股东合计</div><div class="v">55.72<small>%%</small></div></div>
        </div>
        <h3>股权特点解读</h3>
        <ul class="sh3-ul">
          <li><strong>国资绝对控股</strong>：宝钛集团 49.40%% 为控股股东，陕西省国资委为最终实控人，控制权极其稳固；</li>
          <li><strong>军工 ETF 扎堆</strong>：前十大流通股东中 4 只为军工/有色金属 ETF，反映市场对公司的军工+有色双重属性认知；</li>
          <li><strong>港股通参与</strong>：香港中央结算持股 3.18%%，为第二大股东，反映北向资金关注。</li>
        </ul>
      </div>
    </div>
    <h3>前十大股东明细</h3>
    %s
    <h3>股权结构图</h3>
    %s
    <p class="src"><b>来源：</b>宝钛股份 2026 年半年报「股东情况」；宝钛股份研究报告 PPTX 幻灯片 4、5（2026-08，股东结构/股权结构）；公司 logo 取自该 PPTX 母版。</p>""" % (
    DONUT, TBL, TREE)

io.open(os.path.join(HERE, '_mod3_new.html'), 'w', encoding='utf-8').write(HTML)

d = json.load(io.open(SEEDP, encoding='utf-8'))
hit = 0
for m in d['mods']:
    if str(m.get('no')) == '3':
        m['html'] = HTML
        hit += 1
assert hit == 1, '模块 3 命中 %d 次' % hit
io.open(SEEDP, 'w', encoding='utf-8').write(json.dumps(d, ensure_ascii=False, indent=1))
print('模块 3 已写入 %s（%d 字符）' % (os.path.basename(SEEDP), len(HTML)))
print('DONE')
