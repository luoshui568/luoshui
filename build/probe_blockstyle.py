# -*- coding: utf-8 -*-
"""「模块堆叠文本分块 + 表格色块」线上体检（第四版「浅蓝」口径）。

量的是**真实渲染结果**，不是字符串存在性：
  A. `<style id="rpt-blockstyle">` 是否真的上了线、`rpt-txtstyle` 有没有被顺带动过
  B. `.card > ul` 是否变成了 grid、行距是否 10px
  C. `.card > ul > li` 是否拿到了「4px 渐变左柱 + 浅蓝渐变底 + 右侧 13px 圆角」
  D. 表格五层装饰：表头行渐变 + 主蓝底线、容器 15px 圆角 + 浅蓝描边、
     首列渐变 + 600 字重 + 主蓝小柱、斑马纹 #f1f6f9 ↔ #fff、行分隔线 #e2e9ee
  E. 渲染层：`**` 星号是否已清零、数字列是否右对齐

⚠️ 换配色就要换期望值常量区 + JS 采集段 + 断言，三处必须一起改，
   否则跑出来全红（改过四轮，每次都是这三处同步）。

用法：
    python3 build/probe_blockstyle.py 002408                 # 默认 m1 + m6（列表 + 表格）
    python3 build/probe_blockstyle.py 002408 --mod 1
    python3 build/probe_blockstyle.py 601958 --mod 24        # 长条目列表
    RPT_SRC=/tmp/x.html python3 build/probe_blockstyle.py 002408   # 指到本地字节（未上线时自测）
"""
import http.server
import json
import os
import re
import socketserver
import subprocess
import sys
import threading

EDGE = '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'
LIVE = 'https://liuchaowang.cn/report.html'
PROF = '/tmp/edgeprof_blkprobe'
SERVE = '/tmp/blkprobe_serve'
PORT = 9011

_srv_lock = {}
_srv = [None]


class _H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=SERVE, **kw)

    def log_message(self, *a):
        pass


def _server():
    return _srv[0]

# 期望值（与 build/block_style.css 的 ③ 段一一对应 · 2026-10-15 第四版「浅蓝」）
# ★★ 用户最终确认要这一版（2026-10-15 12:02）：
#   表头行整行浅蓝渐变 `#ecf3f9→#d6e6f0→#ccdfea→#c3d8e4` + 底部 3px 主蓝实线 `#2d81be`；
#   容器 `#d0dde7` + 圆角 **15px**；斑马纹 `#f1f6f9 ↔ #fff`（回归，但只差 3 个色阶）；
#   首列浅蓝渐变 + 600 字重 + 左侧 3px 主蓝小柱；行分隔线 `#e2e9ee`。
#   ⚠️ 与第二版的关键差别：圆角 14px→15px、**斑马纹回归**、表头行多一层装饰。
# ⚠️ 读数纪律（写断言时必须知道）：
#   ① 渐变底色下 getComputedStyle().backgroundColor 返回**透明**（渐变在
#      background-image 上）⇒ 判底色必须看 background-image，判 background-color 会误报。
#   ② 半透明阴影（rgba(45,129,190,.55)）取不到纯 rgb 字符串
#      ⇒ 断言匹配 rgb **前三通道**（'45, 129, 190' in shadow）。
#   ③ 表头是**裸 <tr><th>**（没有 <thead>），底色画在 `tr:first-child` 上、
#      `th` 自身必须透明 ⇒ 断言 `th` 的 background-color 为透明。
EXP_TH_COLOR = 'rgb(255, 255, 255)'        # 表头字色：红底白字（第一版原值）
EXP_TH_ROW_SHADOW_RGB = '200, 26, 51'      # 表头行底部暗红实线 #c81a33
EXP_TH_BG = 'rgba(0, 0, 0, 0)'             # th 自身必须透明（底色由 tr 承担）
EXP_TD_BB = 'rgb(226, 233, 238)'           # #e2e9ee 冷蓝行分隔线
EXP_TBL_BORDER = 'rgb(208, 221, 231)'      # #d0dde7 浅蓝容器边框
EXP_RADIUS = '15px'
EXP_ROW1_BG = 'rgb(241, 246, 249)'         # #f1f6f9 奇数行极淡蓝
EXP_ROW2_BG = 'rgb(255, 255, 255)'         # 偶数行纯白
EXP_FIRSTCOL_SHADOW_RGB = '45, 129, 190'   # 首列左侧主蓝小柱
EXP_FIRSTCOL_FW = '600'
# 斑马纹色阶差上限（实测 #f1f6f9 ↔ #fff 三通道最大差 = 14；设 8 会误报）
# 下限恒为 >0：差 0 等于没上色
EXP_ROW_DELTA_MAX = 14
# 表头渐变必须是**红色系**（红表头 + 浅蓝身双系）；先验字面量，改配色时同步更新
EXP_TH_GRAD_RED = ('rgb(208, 32, 47)', 'rgb(228, 54, 68)')   # #d0202f / #e43644

JS = r"""
setTimeout(function(){
  function cs(el, p){ return getComputedStyle(el).getPropertyValue(p).trim(); }
  function rgb(el){ return cs(el, 'background-color'); }
  var out = {code: CODE, mod: MOD};

  out.has_block = !!document.getElementById('rpt-blockstyle');
  out.txtstyle   = document.querySelectorAll('#rpt-txtstyle').length;

  var card = document.getElementById('m' + MOD);
  out.card_found = !!card;

  /* ---- 列表 ---- */
  var ul = card ? card.querySelector(':scope > ul') : null;
  out.has_top_ul = !!ul;
  if(ul){
    var lis = ul.querySelectorAll(':scope > li');
    out.li_count   = lis.length;
    out.ul_display = cs(ul, 'display');
    out.ul_rowgap  = cs(ul, 'row-gap');
    out.ul_padding = cs(ul, 'padding-left');
    var l0 = lis[0];
    /* 第四版浅蓝：左条**不是** border-left，而是 4px 渐变伪元素
       （渐变色柱 border-left 做不出来）⇒ border-left 必须是 0 */
    out.li_border_left_w = cs(l0, 'border-left-width');
    out.li_pad_left      = cs(l0, 'padding-left');
    out.li_radius_r      = cs(l0, 'border-top-right-radius');
    out.li_radius_l      = cs(l0, 'border-top-left-radius');
    out.li_bg_image      = cs(l0, 'background-image').slice(0, 60);
    out.li_bgcolor       = rgb(l0);
    out.li_border_c      = cs(l0, 'border-top-color');
    out.li_line_height   = cs(l0, 'line-height');
    var pf = getComputedStyle(l0, '::before');
    out.li_pf_content = pf.content;
    out.li_pf_bgimage = (pf.backgroundImage || '').slice(0, 46);
    out.li_pf_width   = pf.width;
    out.li_pf_pos     = pf.position;
    if(lis.length > 1){
      var r0 = lis[0].getBoundingClientRect(), r1 = lis[1].getBoundingClientRect();
      out.li_gap_px = Math.round((r1.top - r0.bottom) * 100) / 100;
      out.li_heights = [Math.round(r0.height), Math.round(r1.height)];
    }
    /* 列表后紧跟的那一段 = 小结块？ */
    var sib = ul.nextElementSibling;
    out.after_ul_tag = sib ? sib.tagName : '';
    if(sib && sib.tagName === 'P'){
      out.summary_border_left_w = cs(sib, 'border-left-width');
      out.summary_bg_image = cs(sib, 'background-image').slice(0, 60);
      var spf = getComputedStyle(sib, '::before');
      out.summary_pf_bgimage = (spf.backgroundImage || '').slice(0, 46);
      out.summary_pf_width   = spf.width;
    }
  }

  /* ---- 表格 ---- */
  var tb = card ? card.querySelector('table') : null;
  out.has_table = !!tb;
  if(tb){
    var th = tb.querySelector('th');
    out.th_bg    = th ? rgb(th) : '';
    out.th_color = th ? cs(th, 'color') : '';
    /* ★ 表头**行**：底色与底部主蓝实线都画在 tr:first-child 上（本站是裸 <tr><th>） */
    var thr = tb.querySelector('tr');
    out.throw_bg      = thr ? rgb(thr) : '';
    out.throw_bgimg   = thr ? cs(thr, 'background-image').slice(0, 90) : '';
    out.throw_shadow  = thr ? cs(thr, 'box-shadow') : '';
    out.tbl_bb   = cs(tb, 'border-top-color') + ' ' + cs(tb, 'border-top-width');
    out.tbl_rad  = cs(tb, 'border-top-left-radius');
    var td0 = tb.querySelector('tbody td');
    out.td_bb   = td0 ? cs(td0, 'border-bottom-color') + ' ' + cs(td0, 'border-bottom-width') : '';
    out.td_bg   = td0 ? rgb(td0) : '';
    out.td_fw   = td0 ? cs(td0, 'font-weight') : '';
    out.td_color = td0 ? cs(td0, 'color') : '';
    /* 首列：渐变在 background-image 上，background-color 必为透明；
       左侧主蓝小柱走 inset box-shadow ⇒ 只能匹配 rgb 前三通道。 */
    out.firstcol_bg      = td0 ? rgb(td0) : '';
    out.firstcol_bgimg   = td0 ? cs(td0, 'background-image').slice(0, 90) : '';
    out.firstcol_shadow  = td0 ? cs(td0, 'box-shadow') : '';
    /* 斑马纹：取「奇数行」与「偶数行」各自的非首列单元格
       ⚠️ 表头那一行也是 tbody 第 1 个子元素，但里面是 th 不是 td，
          所以 :not(:first-child) 天然把它排除，不会取错。 */
    var cOdd  = tb.querySelector('tbody tr:nth-child(odd) > td:not(:first-child)');
    var cEven = tb.querySelector('tbody tr:nth-child(even) > td:not(:first-child)');
    out.row1_bg   = cOdd  ? rgb(cOdd)  : '';
    out.row1_bgimg= cOdd  ? cs(cOdd, 'background-image').slice(0, 30) : '';
    out.row2_bg   = cEven ? rgb(cEven) : '';
    out.row2_bgimg= cEven ? cs(cEven, 'background-image').slice(0, 30) : '';
    /* 数字列：必须有 is-num 且右对齐 */
    var nums = tb.querySelectorAll('td.is-num');
    out.num_count = nums.length;
    out.num_align = nums.length ? cs(nums[0], 'text-align') : '';
    out.num_tnum  = nums.length ? cs(nums[0], 'font-variant-numeric') : '';
    out.stars = card.innerHTML.split('**').length - 1;
  }
  var pre = document.createElement('pre');
  pre.id = 'WB_PROBE';
  pre.textContent = JSON.stringify(out);
  document.body.appendChild(pre);
  document.title = 'PROBE_READY';
}, 9000);
"""


def run(src, code, mod, w=1100, h=2400):
    """★ 一律「线上字节 → 注入探针 → 本地 127.0.0.1 服务」：
       file:// 的 Origin 是 null，网关直接 403（踩过），所以必须走 http。"""
    js = JS.replace('CODE', json.dumps(code)).replace('MOD', json.dumps(str(mod)))
    if src.startswith('http'):
        os.makedirs(SERVE, exist_ok=True)
        raw = os.path.join(SERVE, '__live_raw.html')
        subprocess.run(['curl', '-sS', '-L', '-H', 'Cache-Control: no-cache',
                        '-o', raw, src + ('&' if '?' in src else '?') + 'nc=%d' % os.getpid()],
                       check=True, capture_output=True)
        html = open(raw, encoding='utf-8', errors='replace').read()
    else:
        with open(src, encoding='utf-8', errors='replace') as f:
            html = f.read()
    i = html.rfind('</body>')
    page = html[:i] + '<script>' + js + '<' + '/script>' + html[i:]
    os.makedirs(SERVE, exist_ok=True)
    with open(os.path.join(SERVE, 'probe.html'), 'w', encoding='utf-8') as f:
        f.write(page)

    srv = None
    if _server() is None:
        socketserver.TCPServer.allow_reuse_address = True
        srv = socketserver.TCPServer(('127.0.0.1', PORT), _H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
    cmd = [EDGE, '--headless=new', '--no-sandbox', '--disable-gpu', '--no-proxy-server',
           '--user-data-dir=' + PROF, '--window-size=%d,%d' % (w, h),
           '--virtual-time-budget=40000', '--dump-dom',
           'http://127.0.0.1:%d/probe.html?code=%s' % (PORT, code)]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    finally:
        if srv is not None:
            srv.shutdown()
    m = re.search(r'<pre id="WB_PROBE">(.*?)</pre>', p.stdout, re.S)
    if not m:
        print('探针没回数据。stdout 长度 %d' % len(p.stdout))
        print(p.stdout[-800:])
        return None
    return json.loads(m.group(1).replace('&quot;', '"').replace('&amp;', '&')
                      .replace('&lt;', '<').replace('&gt;', '>'))


EXP_LI_PF_W = '4px'                    # 列表左条 = 4px 渐变伪元素
EXP_LI_RADIUS_R = '13px'                # 右侧圆角（左上贴色柱所以是 0）
EXP_LI_RADIUS_L = '0px'


def check_list(d):
    """第四版「浅蓝」口径：分块卡片 = 浅蓝渐变底 + 4px 渐变伪元素左柱。"""
    red = []
    if not d.get('card_found'):
        return ['#m%s 不存在（数据没拉到？）' % d['mod']]
    if not d.get('has_top_ul'):
        return []
    if d['ul_display'] != 'grid':
        red.append('ul display=%s（期望 grid）' % d['ul_display'])
    if d.get('ul_rowgap') not in ('10px',):
        red.append('ul row-gap=%s（期望 10px）' % d.get('ul_rowgap'))
    # ★ 第四版左柱是伪元素 ⇒ border-left 必须是 0（渐变做不出 border 渐变）
    if d.get('li_border_left_w') != '0px':
        red.append('li border-left=%s（期望 0px，左柱走伪元素）' % d.get('li_border_left_w'))
    if not d.get('li_bg_image', '').startswith('linear-gradient'):
        red.append('li 底=%s（期望 linear-gradient 浅蓝）' % d.get('li_bg_image'))
    if d.get('li_radius_r') != EXP_LI_RADIUS_R:
        red.append('li 右上圆角=%s（期望 %s）' % (d.get('li_radius_r'), EXP_LI_RADIUS_R))
    if d.get('li_radius_l') not in ('0px', ''):
        red.append('li 左上圆角=%s（期望 0px，左边贴色柱）' % d.get('li_radius_l'))
    if d.get('li_pf_pos') != 'absolute':
        red.append('li 伪元素 position=%s（期望 absolute）' % d.get('li_pf_pos'))
    if d.get('li_pf_width') != EXP_LI_PF_W:
        red.append('li 左柱宽=%s（期望 %s）' % (d.get('li_pf_width'), EXP_LI_PF_W))
    if 'linear-gradient' not in (d.get('li_pf_bgimage') or ''):
        red.append('li 左柱=%s（期望 linear-gradient 蓝色柱）' % d.get('li_pf_bgimage'))
    if d.get('li_count', 0) > 1:
        g = d.get('li_gap_px')
        if g is None or not (9.5 <= g <= 10.5):
            red.append('相邻 li 实空间隙=%s（期望 ~10px）' % g)
    return red


def _px(s):
    m = re.match(r'rgba?\((\d+),\s*(\d+),\s*(\d+)', s or '')
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def check_table(d):
    """第四版「浅蓝」口径：
       表头行整行浅蓝渐变 + 底部 3px 主蓝实线；容器 #d0dde7 + 15px 圆角；
       斑马纹 #f1f6f9 <-> #fff（回归）；首列浅蓝渐变 + 600 + 左侧主蓝小柱；
       行分隔线 #e2e9ee。
    三条读数纪律（踩过，断言必须照此写）：
       (1) 渐变底色下 background-color 返回**透明**（渐变在 background-image 上）
           => 表头行/首列的底色判 background-image，判 background-color 必误报。
       (2) 半透明阴影读数是 rgba(45,129,190,.55) => 匹配 rgb **前三通道**。
       (3) 本站表格是裸 <tr><th>（无 thead）=> 表头只能靠 tr:first-child，
           且 th 自身必须透明、底色与底线都在 tr 上。
    """
    red = []
    if not d.get('card_found'):
        return ['#m%s 不存在（数据没拉到？）' % d['mod']]
    if not d.get('has_table'):
        return []
    # --- 表头单元格：自身透明 + 冷调深墨字 ---
    if d.get('th_bg') != EXP_TH_BG:
        red.append('表头 th 底色=%s（期望 %s => 底色必须由 tr 承担）'
                   % (d.get('th_bg'), EXP_TH_BG))
    if d.get('th_color') != EXP_TH_COLOR:
        red.append('表头字色=%s（期望 %s）' % (d.get('th_color'), EXP_TH_COLOR))
    # --- 表头行：红渐变 + 底部暗红实线（「红表头 + 浅蓝身」双系） ---
    bgimg = d.get('throw_bgimg') or ''
    if 'linear-gradient' not in bgimg:
        red.append('表头行底=%s（期望 linear-gradient 红）' % (bgimg or 'none'))
    else:
        miss = [c for c in EXP_TH_GRAD_RED if c not in bgimg]
        if miss:
            red.append('表头渐变缺红色分量 %s（实际 %s）⇒ 表头必须回红，不能变蓝'
                       % (miss, bgimg[:70]))
    if EXP_TH_ROW_SHADOW_RGB not in (d.get('throw_shadow') or ''):
        red.append('表头行底线=%s（期望含暗红 %s）'
                   % ((d.get('throw_shadow') or '')[:60], EXP_TH_ROW_SHADOW_RGB))
    # --- 容器 ---
    if d.get('tbl_bb') != EXP_TBL_BORDER + ' 1px':
        red.append('容器边框=%s（期望 %s 1px）' % (d.get('tbl_bb'), EXP_TBL_BORDER))
    if d.get('tbl_rad') != EXP_RADIUS:
        red.append('容器圆角=%s（期望 %s）' % (d.get('tbl_rad'), EXP_RADIUS))
    # --- 行分隔线 ---
    if d.get('td_bb') != EXP_TD_BB + ' 1px':
        red.append('行分隔线=%s（期望 %s 1px）' % (d.get('td_bb'), EXP_TD_BB))
    # --- 首列：渐变 + 600 + 主蓝小柱
    #     ★ 特异度错就会「隔行颠倒」（首列底色时有时无）=> 这三条一起红即是那个 bug ---
    if 'linear-gradient' not in (d.get('firstcol_bgimg') or ''):
        red.append('首列底=%s（期望 linear-gradient 浅蓝）' % (d.get('firstcol_bgimg')))
    if EXP_FIRSTCOL_SHADOW_RGB not in (d.get('firstcol_shadow') or ''):
        red.append('首列左柱=%s（期望含主蓝 %s）'
                   % ((d.get('firstcol_shadow') or '')[:60], EXP_FIRSTCOL_SHADOW_RGB))
    if d.get('td_fw') != EXP_FIRSTCOL_FW:
        red.append('首列字重=%s（期望 %s）' % (d.get('td_fw'), EXP_FIRSTCOL_FW))
    # --- 斑马纹：奇数行极淡蓝 <-> 偶数行纯白，色阶差 0 < d <= 8 ---
    if d.get('row1_bg') != EXP_ROW1_BG:
        red.append('奇数行底色=%s（期望 %s）' % (d.get('row1_bg'), EXP_ROW1_BG))
    if d.get('row2_bg') != EXP_ROW2_BG:
        red.append('偶数行底色=%s（期望 %s）' % (d.get('row2_bg'), EXP_ROW2_BG))
    p1, p2 = _px(d.get('row1_bg')), _px(d.get('row2_bg'))
    if p1 and p2:
        delta = max(abs(p1[i] - p2[i]) for i in range(3))
        if not (0 < delta <= EXP_ROW_DELTA_MAX):
            red.append('斑马纹色阶差=%d（期望 1~%d：太大就吵、太小等于没上）'
                       % (delta, EXP_ROW_DELTA_MAX))
    for k in ('row1_bgimg', 'row2_bgimg'):
        if (d.get(k) or 'none') != 'none':
            red.append('%s 残留渐变底图：%s' % (k, d.get(k)))
    if d.get('num_count', 0) > 0:
        if d.get('num_align') != 'right':
            red.append('数字列未右对齐（text-align=%s）' % d.get('num_align'))
    if d.get('stars', 0) != 0:
        red.append('模块内仍有 %s 个未渲染的 ** 星号' % d['stars'])
    return red


def main():
    a = sys.argv[1:]
    code = next((x for x in a if not x.startswith('--') and x.isdigit()), '002408')
    src = os.environ.get('RPT_SRC', LIVE)
    mods = []
    if '--mod' in a and a.index('--mod') + 1 < len(a):
        mods = [a[a.index('--mod') + 1]]
    else:
        mods = ['1', '6']
    print('源 %s | code=%s | 模块 %s' % (src, code, ','.join(mods)))
    total_red = []
    for mod in mods:
        d = run(src, code, mod)
        if d is None:
            total_red.append('m%s 无数据' % mod)
            continue
        print('\n--- m%s ---' % mod)
        print('  rpt-blockstyle=%s  rpt-txtstyle=%d'
              % (d.get('has_block'), d.get('txtstyle', 0)))
        if not d.get('has_block'):
            total_red.append('m%s rpt-blockstyle 不在线上' % mod)
        red = check_list(d) + check_table(d)
        if d.get('has_top_ul'):
            print('  列表: %d 条  display=%s  row-gap=%s  border-left=%s  左柱=%s/%s  %s'
                  % (d.get('li_count'), d.get('ul_display'), d.get('ul_rowgap'),
                     d.get('li_border_left_w'), d.get('li_pf_width'),
                     (d.get('li_pf_bgimage') or 'none')[:30],
                     '渐变' if (d.get('li_bg_image') or '').startswith('linear-gradient') else d.get('li_bg_image')))
            print('        圆角 左%s/右%s  边框色=%s  行高=%s'
                  % (d.get('li_radius_l'), d.get('li_radius_r'),
                     d.get('li_border_c'), d.get('li_line_height')))
            if d.get('li_gap_px') is not None:
                print('  相邻条目实空间隙 %spx   条目高 %s' % (d['li_gap_px'], d.get('li_heights')))
            if d.get('after_ul_tag') == 'P' and 'summary_pf_bgimage' in d:
                print('  列表后小结段: border-left=%s 左柱=%s/%s  底=%s'
                      % (d.get('summary_border_left_w'), d.get('summary_pf_width'),
                         (d.get('summary_pf_bgimage') or 'none')[:30],
                         (d.get('summary_bg_image') or '')[:32]))
        if d.get('has_table'):
            print('  表格: 表头 th 底=%s 字色=%s' % (d.get('th_bg'), d.get('th_color')))
            print('        表头行 底=%s' % ((d.get('throw_bgimg') or 'none')[:76]))
            print('        表头行 底线=%s' % ((d.get('throw_shadow') or 'none')[:66]))
            print('        容器 圆角=%s 边框=%s' % (d.get('tbl_rad'), d.get('tbl_bb')))
            print('        行分隔=%s' % d.get('td_bb'))
            print('        首列 底=%s' % ((d.get('firstcol_bgimg') or 'none')[:70]))
            print('        首列 左柱=%s 字重=%s 字色=%s'
                  % ((d.get('firstcol_shadow') or 'none')[:56],
                     d.get('td_fw'), d.get('td_color')))
            print('        斑马 奇行=%s(%s) 偶行=%s(%s)'
                  % (d.get('row1_bg'), d.get('row1_bgimg') or 'none',
                     d.get('row2_bg'), d.get('row2_bgimg') or 'none'))
            print('        数字列 %s 个 右对齐=%s 等宽数字=%s | 残余 ** 星号=%s'
                  % (d.get('num_count'), d.get('num_align'), d.get('num_tnum'),
                     d.get('stars')))
        if red:
            for x in red:
                print('  ✗ ' + x)
            total_red += ['m%s: %s' % (mod, x) for x in red]
        else:
            print('  ✓ 全绿')
    print('\n总分：' + ('全绿 ✓' if not total_red else '有失败 %d 项' % len(total_red)))
    return 0 if not total_red else 2


if __name__ == '__main__':
    sys.exit(main())
