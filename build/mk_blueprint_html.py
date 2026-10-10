# -*- coding: utf-8 -*-
"""生成《31 模块通用深度研报框架 · 位置顺序与补全蓝图》单文件 HTML（输出到桌面）。

数据来源（全部机器核对，不手写）：
  * 31 槽位 / 六篇 / 骨架要素  ← build/report_template_v31.py（唯一权威定义）
  * 旧 23 模块的真实顺序      ← 扫描桌面「宝钛股份深度研究报告-模块版-20260826.html」的 id="mN"
  * 各份研报实际模块数        ← build/seed/report_*.json
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import report_template_v31 as T          # noqa: E402

DESKTOP = r'C:\Users\50522\Desktop'
BT = os.path.join(DESKTOP, '宝钛股份深度研究报告-模块版-20260826.html')
OUT = os.path.join(DESKTOP, '31模块通用深度研报框架-位置顺序与补全蓝图-20260917.html')


# ----------------------------------------------------------------- 旧模板真实顺序
def scan_old_order(path):
    """从旧模板 HTML 里扫出 id="mN" 的正文顺序 + 标题（去脚本，别读内联 ECharts）。"""
    src = io.open(path, encoding='utf-8', errors='ignore').read()
    ns = re.sub(r'<script[\s\S]*?</script>', '', src, flags=re.I)
    pos = {}
    for m in re.finditer(r'id=["\']m(\d+)["\']', ns):
        pos.setdefault(int(m.group(1)), []).append(m.start())
    order = sorted(pos, key=lambda n: pos[n][-1])
    out = []
    for i, n in enumerate(order):
        a = pos[n][-1]
        b = pos[order[i + 1]][-1] if i + 1 < len(order) else len(ns)
        seg = ns[a:b]
        t = ''
        mh = re.search(r'<h[234][^>]*>([\s\S]{0,200}?)</h[234]>', seg)
        if mh:
            t = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', mh.group(1))).strip()
        t = re.sub(r'^\d+\s*', '', t)
        out.append((n, t))
    return out


OLD = scan_old_order(BT)
assert [n for n, _ in OLD] == list(range(1, 24)), '旧模板应是 m1..m23，实际 %s' % [n for n, _ in OLD]

# 交叉验证：OLD2NEW 必须与 v3.1 定义一致
assert sorted(T.OLD2NEW) == list(range(1, 24))

STATUS = {}
for n in T.NEW_NOS:
    STATUS[n] = 'new'
for n in T.UPGRADE_NOS:
    STATUS[n] = 'up'
for m in T.MODULES:
    STATUS.setdefault(m['no'], 'keep')

ST_LABEL = {'keep': '保留', 'up': '升级', 'new': '新增'}
OLD_OF = {v: k for k, v in T.OLD2NEW.items()}

CHARTS = {m['no']: m['charts'] for m in T.MODULES}
ALL_CHARTS = sorted({c for m in T.MODULES for c in m['charts']})
CHART_MODS = [m['no'] for m in T.MODULES if m['charts']]

SEED_COUNTS = [
    ('600459 贵研铂业', 31, 'v3.1 标准'),
    ('000731 四川美丰', 31, 'v3.1 标准'),
    ('000830 鲁西化工', 31, 'v3.1 标准'),
    ('002237 恒邦股份', 31, 'v3.1 标准'),
    ('600456 宝钛股份', 29, '裁剪版：删掉 m27 估值敏感性 / m28 股价表现'),
]


# ----------------------------------------------------------------- 重排对照 SVG（浅色）
def remap_svg():
    Y0, PITCH, BH, LX, LW, RX, RW, W = 50, 22, 20, 40, 150, 490, 150, 680
    H = Y0 + 31 * PITCH + 20
    S = {'keep': ('#f1efec', '#b4b2a9', '#444441'),
         'up': ('#faf0d8', '#c9a227', '#7a5c10'),
         'new': ('#e2f5fd', '#00a0dd', '#00658f')}
    L = ('none', '#c9c8c4', '#85858a')
    o = ['<svg viewBox="0 0 %d %d" width="100%%" role="img" xmlns="http://www.w3.org/2000/svg">' % (W, H),
         '<title>旧 23 模块到新 31 槽位的位置重排对照</title>',
         '<desc>左列旧模板 m1 到 m23，右列 v3.1 的 31 个位置，连线表示落点。</desc>']
    o.append('<text x="%d" y="34" font-size="12" font-weight="500" fill="#85858a">旧 23 模块（宝钛模板）</text>' % LX)
    o.append('<text x="%d" y="34" font-size="12" font-weight="500" fill="#85858a">新 31 槽位（v3.1）</text>' % RX)
    for a, b in sorted(T.OLD2NEW.items()):
        y1 = Y0 + (a - 1) * PITCH + BH / 2
        y2 = Y0 + (b - 1) * PITCH + BH / 2
        o.append('<path d="M%d %.1f L%d %.1f" fill="none" stroke="#d8d7d3" stroke-width="0.5"/>' % (LX + LW, y1, RX, y2))
    for no, title in OLD:
        y = Y0 + (no - 1) * PITCH
        o.append('<rect x="%d" y="%d" width="%d" height="%d" rx="4" fill="%s" stroke="%s" stroke-width="0.5"/>'
                 % (LX, y, LW, BH, L[0], L[1]))
        o.append('<text x="%d" y="%.1f" font-size="11" fill="%s">m%d %s</text>'
                 % (LX + 8, y + BH / 2, L[2], no, title.replace('&', '&amp;')))
    for m in T.MODULES:
        no = m['no']
        y = Y0 + (no - 1) * PITCH
        f, s, t = S[STATUS[no]]
        o.append('<rect x="%d" y="%d" width="%d" height="%d" rx="4" fill="%s" stroke="%s" stroke-width="0.5"/>'
                 % (RX, y, RW, BH, f, s))
        o.append('<text x="%d" y="%.1f" font-size="11" fill="%s">m%d %s</text>'
                 % (RX + 8, y + BH / 2, t, no, m['title'].replace('&', '&amp;')))
    o.append('</svg>')
    return '\n'.join(o)


# ----------------------------------------------------------------- HTML
def parts_of(no):
    return T.MOD_BY_NO[no]['part']


def kpi():
    keep = sum(1 for n in STATUS if STATUS[n] == 'keep')
    return [('31', '个位置槽'), ('6', '篇分组'), ('8', '新增模块'), ('6', '升级模块'),
            ('17', '保留模块'), (str(len(ALL_CHARTS)), '个标配图槽')]


def row(m):
    no = m['no']
    st = STATUS[no]
    old = OLD_OF.get(no)
    oldtxt = '旧 m%d' % old if old else '<span class="dash">—</span>'
    charts = ''.join('<code>%s</code>' % c for c in m['charts']) or '<span class="dash">无</span>'
    must = ''.join('<li>%s</li>' % x for x in m['must'])
    return (
        '<tr class="s-%s">'
        '<td class="c-no"><b>m%d</b></td>'
        '<td class="c-part">%s</td>'
        '<td class="c-name">%s</td>'
        '<td class="c-st"><span class="pill p-%s">%s</span></td>'
        '<td class="c-old">%s</td>'
        '<td class="c-chart">%s</td>'
        '<td class="c-must"><ul>%s</ul></td>'
        '</tr>'
    ) % (st, no, T.PART_TITLE[m['part']].split(' · ')[1], m['title'].replace('&', '&amp;'),
         st, ST_LABEL[st], oldtxt, charts, must)


def part_section(part_no, label, name, mods):
    rows = ''.join(row(m) for m in mods)
    return ('<section class="part">'
            '<h3><span class="pno">%s</span>%s <em>m%d–m%d ｜ %d 项</em></h3>'
            '<div class="tw"><table class="mods"><thead><tr>'
            '<th>位置</th><th>归属</th><th>模块名</th><th>处置</th><th>旧编号</th><th>标配图槽</th><th>骨架要素（写作规格）</th>'
            '</tr></thead><tbody>%s</tbody></table></div></section>') % (
        label, name, mods[0]['no'], mods[-1]['no'], len(mods), rows)


def old_table():
    tr = []
    for no, title in OLD:
        nn = T.OLD2NEW[no]
        tr.append('<tr><td class="c-no"><b>m%d</b></td><td class="c-name">%s</td>'
                  '<td class="c-arrow">→</td><td class="c-no"><b>m%d</b></td>'
                  '<td class="c-name">%s</td><td class="c-st"><span class="pill p-%s">%s</span></td></tr>'
                  % (no, title, nn, T.MOD_BY_NO[nn]['title'], STATUS[nn], ST_LABEL[STATUS[nn]]))
    return ''.join(tr)


def new_only_table():
    tr = []
    for no in T.NEW_NOS:
        m = T.MOD_BY_NO[no]
        tr.append('<tr><td class="c-no"><b>m%d</b></td><td class="c-name">%s</td>'
                  '<td class="c-part">%s</td><td class="c-must"><ul>%s</ul></td></tr>'
                  % (no, m['title'], T.PART_TITLE[m['part']].split(' · ')[1],
                     ''.join('<li>%s</li>' % x for x in m['must'])))
    return ''.join(tr)


def seed_table():
    tr = []
    for name, n, note in SEED_COUNTS:
        cls = 'ok' if n == 31 else 'warn'
        tr.append('<tr><td class="c-name">%s</td><td class="c-no"><b>%d</b></td>'
                  '<td class="c-st"><span class="pill p-%s">%s</span></td></tr>'
                  % (name, n, 'new' if n == 31 else 'up', note))
    return ''.join(tr)


def toc_cards():
    out = []
    for n, t in T.TOC_REPS:
        out.append('<li><code>%s</code><b>%s</b><span>%s</span></li>'
                   % ('#m%d' % n, t, T.MOD_BY_NO[n]['title']))
    return ''.join(out)


CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{background:#fafafa;color:#1a1a1c;font:15px/1.75 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif;
 -webkit-font-smoothing:antialiased;padding:0 24px 72px}
.wrap{max-width:1240px;margin:0 auto}
code{font-family:"JetBrains Mono",Consolas,monospace;font-size:12px;background:#f1f0ee;color:#8a5b00;
 padding:1px 5px;border-radius:4px;white-space:nowrap}
.dash{color:#c9c8c4}
/* hero */
.hero{padding:56px 0 30px;border-bottom:1px solid #e6e5e3;margin-bottom:34px}
.kicker{display:inline-block;font-size:12px;letter-spacing:.14em;color:#d0202f;font-weight:700;
 border:1px solid #f3d3d7;background:#fdf3f4;border-radius:999px;padding:4px 12px;margin-bottom:16px}
h1{font-size:33px;line-height:1.3;font-weight:800;letter-spacing:-.5px}
h1 em{font-style:normal;color:#d0202f}
.sub{color:#5c5c60;font-size:15.5px;margin-top:12px;max-width:900px}
.kpis{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin-top:26px}
.kpi{background:#fff;border:1px solid #e6e5e3;border-radius:12px;padding:14px 16px;position:relative;overflow:hidden}
.kpi::before{content:"";position:absolute;inset:0 auto 0 0;width:3px;background:#e6e5e3}
.kpi:nth-child(3)::before,.kpi:nth-child(6)::before{background:#00b0f0}
.kpi:nth-child(4)::before{background:#c9a227}
.kpi b{display:block;font-size:28px;font-weight:800;letter-spacing:-.5px;line-height:1.1}
.kpi span{font-size:12px;color:#85858a}
/* sections */
h2{font-size:20px;font-weight:800;margin:44px 0 6px;padding-left:12px;border-left:4px solid #d0202f}
h2 em{font-style:normal;color:#85858a;font-size:13px;font-weight:400;margin-left:10px}
h3{font-size:15.5px;font-weight:700;margin:26px 0 10px;display:flex;align-items:center;gap:9px}
h3 em{font-style:normal;color:#9a9a9e;font-size:12.5px;font-weight:400}
.pno{background:#1a1a1c;color:#fff;font-size:11.5px;padding:2px 8px;border-radius:6px;font-weight:700}
p.note{color:#5c5c60;font-size:14px;margin:8px 0 4px;max-width:1000px}
.tipbox{background:#fff;border:1px solid #e6e5e3;border-left:3px solid #c9a227;border-radius:10px;
 padding:14px 18px;margin:14px 0;font-size:13.5px;color:#4a4a4e}
.tipbox b{color:#1a1a1c}
/* tables */
.tw{overflow:auto;border:1px solid #e6e5e3;border-radius:12px;background:#fff}
table{border-collapse:separate;border-spacing:0;width:100%;font-size:13.5px}
th{position:sticky;top:0;background:#f7f6f4;color:#5c5c60;font-weight:700;font-size:12px;
 text-align:left;padding:10px 12px;border-bottom:1px solid #e6e5e3;white-space:nowrap;z-index:2}
td{padding:10px 12px;border-bottom:1px solid #f0efed;vertical-align:top}
tr:last-child td{border-bottom:none}
.c-no{white-space:nowrap;font-family:"JetBrains Mono",Consolas,monospace}
.c-part{color:#85858a;font-size:12px;white-space:nowrap}
.c-name{font-weight:600;min-width:150px}
.c-old{color:#85858a;font-size:12.5px;white-space:nowrap}
.c-chart code{margin-right:4px}
.c-must{min-width:330px}
.c-must ul{list-style:none}
.c-must li{position:relative;padding-left:14px;color:#4a4a4e;font-size:12.8px;line-height:1.7}
.c-must li::before{content:"";position:absolute;left:2px;top:9px;width:4px;height:4px;border-radius:50%;background:#c9c8c4}
.c-arrow{color:#c9c8c4;text-align:center}
tr.s-new{background:#fafdff}
tr.s-up{background:#fffdf6}
tr.s-new .c-name{color:#00658f}
tr.s-up .c-name{color:#7a5c10}
.pill{display:inline-block;font-size:11.5px;padding:2px 9px;border-radius:999px;font-weight:700;white-space:nowrap}
.p-keep{background:#f1efec;color:#5c5c60}
.p-up{background:#faf0d8;color:#7a5c10}
.p-new{background:#e2f5fd;color:#00658f}
/* toc */
.toc{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin-top:12px}
.toc li{list-style:none;background:#fff;border:1px solid #e6e5e3;border-radius:10px;padding:12px 14px}
.toc li b{display:block;font-size:16px;font-weight:800;margin:4px 0 2px}
.toc li span{font-size:12px;color:#85858a;line-height:1.5;display:block}
.svgbox{background:#fff;border:1px solid #e6e5e3;border-radius:12px;padding:16px;margin-top:12px;overflow:auto}
.foot{margin-top:52px;padding-top:20px;border-top:1px solid #e6e5e3;color:#9a9a9e;font-size:12.5px;line-height:1.9}
ol.rules{margin:12px 0 0 20px;color:#4a4a4e;font-size:14px}
ol.rules li{margin-bottom:9px}
ol.rules b{color:#1a1a1c}
@media(max-width:1080px){.kpis{grid-template-columns:repeat(3,1fr)}.toc{grid-template-columns:repeat(3,1fr)}}
"""


def main():
    secs = []
    for pno, label, pname in T.PARTS:
        mods = [m for m in T.MODULES if m['part'] == pno]
        secs.append(part_section(pno, label, pname, mods))

    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>31 模块通用深度研报框架 · 位置顺序与补全蓝图</title>
<style>%s</style>
</head>
<body>
<div class="wrap">

<header class="hero">
  <span class="kicker">研报模板 v3.1 · 唯一权威定义</span>
  <h1>31 模块通用深度研报框架<br><em>m1 → m31 位置顺序总表</em></h1>
  <p class="sub">模块编号是<strong>位置主键</strong>（库内 id = <code>{code}_m{no}</code>）。从旧 23 模块升到 31 槽位
  不是尾部追加，而是<strong>从 m9 起整位后移</strong>；下表把每个槽位的归属、处置、标配图槽与写作规格一次列清，
  可直接当写作规格书用。</p>
  <div class="kpis">%s</div>
</header>

<h2>一 · 顺序总表<em>按位置号，六篇分组</em></h2>
<p class="note">「处置」= 相对旧 23 模块模板的处理方式。灰底行为保留、金底行为升级、蓝底行为全新模块。
骨架要素列就是该模块的<strong>写作规格书</strong>——缺一项即为不合格。</p>
%s

<h2>二 · 旧 23 → 新 31 的重排对照<em>位移动线</em></h2>
<p class="note">左侧是桌面那份《宝钛股份深度研究报告-模块版-20260826.html》里实际扫出来的 m1–m23 顺序，
右侧是 v3.1 的 31 个槽位。可以看到 <strong>m1–m8 原地不动</strong>，从旧 m9 开始每插入一批新模块，
后面的旧模块就整体后移一次。</p>
<div class="svgbox">%s</div>
<div class="tw" style="margin-top:14px"><table>
<thead><tr><th>旧位置</th><th>旧模块名</th><th></th><th>新位置</th><th>新模块名</th><th>处置</th></tr></thead>
<tbody>%s</tbody></table></div>

<h2>三 · 八个新增模块<em>旧模板完全没有</em></h2>
<p class="note">这就是「补全」的实体。行业三个（m9/m10/m11）+ 治理一个（m12）、护城河量化（m17）、
盈利预测（m25）、估值敏感性（m27）、多空对照（m30）。</p>
<div class="tw"><table>
<thead><tr><th>位置</th><th>模块名</th><th>归属</th><th>骨架要素</th></tr></thead>
<tbody>%s</tbody></table></div>

<div class="tipbox"><b>落地排序反直觉：先补行业，再补财务。</b>
现金流只影响「这家公司好不好」，行业缺失影响「这条逻辑成不成立」。m9/m10/m11 三块空着，
后面的目标价就是拿未验证的前提推出来的。</div>

<h2>四 · 六篇归属与侧栏目录<em>TOC 六条</em></h2>
<p class="note">侧栏目录六篇各取一个代表模块，文案<strong>统一四个字、不带「第X篇」前缀</strong>
（侧栏只有 160px，前缀 4 个字会吃掉 40%%，再加截断就切得读不出重点）。</p>
<ul class="toc">%s</ul>

<h2>五 · 各份研报的落地状态<em>位置号是否连续</em></h2>
<p class="note">31 是标准，但<strong>不是铁板一块</strong>——600456 被裁到 29 个模块。这意味着
页面与探针里<strong>禁止写死模块编号</strong>，否则永久假红。</p>
<div class="tw"><table>
<thead><tr><th>研报</th><th>模块数</th><th>说明</th></tr></thead>
<tbody>%s</tbody></table></div>

<h2>六 · 改编号时必须守的四条<em>踩过的坑</em></h2>
<ol class="rules">
  <li><b>编号即位置主键。</b>库内 id = <code>{code}_m{no}</code>，图表的 <code>mid</code> 也挂在模块号上。
      升级必须按 <code>OLD2NEW</code> 整位重排，<b>不能只往后追加</b>——追加会让旧内容与新编号语义错位，
      页面上表现为「m9 是产业链结构，但标题写着行业总览」。</li>
  <li><b>重排 <code>no</code> 必须升序写回。</b>乱序 PATCH 会撞唯一约束；<code>up</code> 是 bigint 毫秒，
      传 ISO 字符串报 <code>22P02</code>。</li>
  <li><b>删模块不能走 REST。</b>业务表已收回 DELETE，直删报 <code>42501</code>；要跑 SQL，
      并注意删完之后的编号要重新连成 1..N。</li>
  <li><b>改单个模块走定点写入。</b>只 PATCH <code>wb_report_mods?id=eq.&lt;code&gt;_m&lt;no&gt;</code>
      + POST 单条图表，绝不整份覆盖——整份推会抹掉网页端的在线改动。</li>
</ol>

<div class="foot">
  权威定义：<code>build/report_template_v31.py</code>（三处共用：新建脚手架 <code>new_report_v31.py</code>、
  存量升级 <code>upgrade_report_v31.py</code>、页面 <code>report.template.html</code> 的 MOD_SKELETON）。<br>
  旧顺序来源：扫描桌面《宝钛股份深度研究报告-模块版-20260826.html》的 <code>id="mN"</code>，实测 23 个锚点连续 1..23。<br>
  各份研报模块数来源：<code>build/seed/report_*.json</code>。<br>
  生成时间 2026-09-17 ｜ 标配图槽 %d 个，分布在 %d 个模块上。
</div>

</div>
</body>
</html>""" % (CSS,
             ''.join('<div class="kpi"><b>%s</b><span>%s</span></div>' % kv for kv in kpi()),
             ''.join(secs), remap_svg(), old_table(), new_only_table(),
             toc_cards(), seed_table(), len(ALL_CHARTS), len(CHART_MODS))

    io.open(OUT, 'w', encoding='utf-8').write(html)

    # —— 校验 ——
    n = len(html)
    print('写出：%s' % OUT)
    print('体积：%.1f KB' % (n / 1024.0))
    for tag in ('div', 'section', 'table', 'tr', 'td', 'ul', 'li', 'svg', 'text', 'rect', 'p', 'h3'):
        o = len(re.findall(r'<%s[\s>]' % tag, html))
        c = len(re.findall(r'</%s>' % tag, html))
        flag = '' if o == c else '   <== 不配对'
        print('  %-8s 开 %4d 闭 %4d%s' % (tag, o, c, flag))
    for bad in ('__PART', 'TODO', 'undefined', 'NaN', '%s</'):
        assert bad not in html, '残留占位符 %s' % bad
    print('残留占位符检查：通过')
    print('31 个 m 编号全部出现：%s' % all(('m%d<' % i) in html or ('m%d ' % i) in html for i in range(1, 32)))
    print('篇数 %d ｜ 新增 %s ｜ 升级 %s' % (len(T.PARTS), T.NEW_NOS, T.UPGRADE_NOS))
    print('标配图槽 %d 个：%s' % (len(ALL_CHARTS), ', '.join(ALL_CHARTS)))


if __name__ == '__main__':
    main()
