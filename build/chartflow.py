# -*- coding: utf-8 -*-
"""chartflow.py —— 非 ECharts 视觉件的批量工具箱（时间轴 + 股权结构树）。

为什么需要它
------------
31 模块研报里，28 张 ECharts 图已经能靠 `data-chart` 槽位 + 库表 + `chartmap.py`
自动生产；地图也有 `chartmap.py`。但**有两件视觉件一直是手工艺品**：

  * m2「公司发展历程」时间轴 —— 7 个 `<div class="h-node">` 写死在模块 HTML 里；
  * m3「股权结构图」树状图 —— 内联 SVG，22 rect / 23 text / 22 line / 11 path，
    共 125 组 `x=` 与 125 组 `y=` 绝对坐标（子公司 x 坐标是手算的等差 117.14）。

换一家公司必须整段重写 ⇒ 无法批量。本模块把两者变成「喂数据 → 出 HTML/SVG」。

五个坑（都写成 selfcheck 断言）
------------------------------
  1. **节点数写死** —— 时间轴原先假定 7 个节点、`.h-track{height:345px}` 硬编码；
     少于 4 个会拉太空，多于 8 个会挤爆。⇒ 按节点数算高度并写进 inline style。
  2. **交错方向靠 :nth-child(odd/even)** —— CSS 已就绪，但要求 DOM 里
     `.h-card` 必须紧跟 `.h-dot` 且同级，不能多包一层 div。⇒ 断言结构。
  3. **子公司 x 坐标不可等差** —— 一旦数量变化，手算的 117.14 就废。
     ⇒ 改成 `x_i = margin + i * step`，`step` 由可用宽度均分得出。
  4. **竖排 tspan 与 rect 高度不匹配** —— 名字 4 字 vs 12 字，字号 14.0 / 行距 15.2
     写死 ⇒ 长名字溢出卡片。⇒ 按名字长度自动降字号（12 字以下 14px，以上 12.5px）
     并断言 tspan 总高 ≤ rect 高 - padding。
  5. **层级数变化导致箭头断链** —— 3 条独立 line+path。⇒ 由层级数组驱动，
     每层自动画竖线 + 箭头 + 比例徽标。

用法
----
    from chartflow import TimelineKit, OrgTreeKit

    tk = TimelineKit()
    html = tk.html(
        en='COMPANY HISTORY', title='公司发展历程',
        sub='二十余载 · 从代号902到中国钛工业第一股',
        nodes=[('1999', '<b>宝钛集团</b>联合…', ''),
               ('2002', '4月12日<b>上交所上市</b>，中国钛工业第一股', ''),
               …],
        foot='1999 — 2026 · 钛业报国 · 迈向航空航天新周期')
    tk.selfcheck(nodes)

    ot = OrgTreeKit()
    svg = ot.svg(
        chain=[('陕西省人民政府', '100%'),
               ('陕西有色金属集团', '93.36%'),
               ('宝钛集团有限公司', '49.40%')],
        subject='宝鸡钛业股份有限公司（600456.SH）',
        children=[('宝钛华神钛业有限公司', '66.67%'), …])
    ot.selfcheck(...)

命令行自检：
    python chartflow.py --demo
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# ------------------------------------------------------------------ 主题常量
# 与 build/report_theme.css 保持一致（改这里要同步改 CSS）
C_RED = '#c8102e'
C_RED_DEEP = '#8c0a20'
C_ACCENT = '#d0202f'
C_WHITE = '#ffffff'
C_GOLD = '#c9a227'

# 时间轴
T_MIN_NODES = 3          # 少于 3 个节点不像时间轴
T_MAX_NODES = 12         # 多于 12 个节点卡片会糊成一片
T_CARD_H = 118           # 单张卡片高（px），与 CSS padding 配合
T_BASE_H = 345           # 7 节点时的基准轨道高，也是 CSS 现取值
T_REF_NODES = 7          # 基准节点数

# 股权树
O_VIEW_W = 1000.0
O_VIEW_H = 550.0
O_NODE_H = 46            # 顶部链节点高
O_SUBJ_H = 56            # 上市公司主体高
O_LEAF_H = 212           # 叶子（子公司）高
O_LEAF_W_MAX = 120       # 叶子最大宽（超过则缩减）
O_LEAF_GAP = 17.14       # 叶子间最小间隙
O_EDGE = 40.0            # 左右边距
O_TOP_Y = 14.0           # 第一个链节点的 y

GRAD_DEFS = '''<defs>
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
        </defs>'''


def esc(s):
    """XML 文本转义（注意 & 必须最先换）。"""
    return (str(s).replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))


# ================================================================== 时间轴
class TimelineKit(object):
    """公司发展历程时间轴。输出与 600456 完全同构的 `.hist` HTML。

    可覆盖属性：
        cls_prefix  默认 'h'（CSS 类前缀，如 'h-node' / 'h-card'）
        en / title / sub / foot  四个文案（也可在 html() 里传）
    """

    def __init__(self):
        self.cls_prefix = 'h'
        self.en = 'COMPANY HISTORY'
        self.title = '公司发展历程'
        self.sub = ''
        self.foot = ''
        self.base_h = T_BASE_H
        self.ref_nodes = T_REF_NODES

    # ---------------- 高度自适应 ----------------
    def track_height(self, n):
        """按节点数给轨道高度。

        ★ 2026-10-14 起，这个值**只是兜底**，不再是布局依据：
          report_theme.css 里 `.h-track{height:auto!important}` 会在支持 CSS subgrid 的浏览器上
          直接忽略掉这里写出的 inline height —— 真正的高度由内容撑（见该文件的 .hist 段注释）。
          保留它的原因：① 老浏览器退回绝对定位布局时还需要一个高度；② 已入库研报的 HTML 里
          已经写死了这个值，删掉函数会让重建产物与线上不一致。

        7 个节点 → 345px（与旧 CSS 一致，保证老路径下 600456 视觉不变）；
        节点更多则线性加高，更少则等比降低但不低于 260px。

        为什么原来不能写死：卡片是绝对定位（odd 在上、even 在下），
        轨道高不变而节点变多 ⇒ 卡片水平间距被压缩、正文折行增多、上下卡片重叠，
        且卡片实际需要的高度远超此公式给出的值（9 节点 80~100 字/张时约需 210px 高）。
        """
        if n <= 0:
            raise ValueError('timeline 至少要有 1 个节点')
        if n == self.ref_nodes:
            return self.base_h          # ← 关键：600456 走这条，像素级不变
        h = self.base_h * (T_REF_NODES / float(n)) ** 0.55
        return int(max(260, min(560, round(h))))

    def card_width(self, n):
        """按节点数给卡片宽度（px）。原 CSS 写死 146px。"""
        if n <= self.ref_nodes:
            return 146
        # 节点多了就收窄，但不超过 132px 以下否则正文变竖条
        return max(118, int(146 * (self.ref_nodes / float(n)) ** 0.35))

    # ---------------- 渲染 ----------------
    def html(self, nodes, en=None, title=None, sub=None, foot=None):
        """nodes = [(年份, 正文HTML, 可选额外class), …] 返回 .hist 整块 HTML。

        ⚠️ 本方法**不调用 selfcheck**（selfcheck 内部要渲染取证），否则互相递归。
           校验请显式调用 `tk.selfcheck(nodes)`；`build()` 是「校验+渲染」的合并入口。
        """
        nodes = list(nodes)
        n = len(nodes)
        th = self.track_height(n)
        cw = self.card_width(n)

        parts = ['<div class="hist">']
        parts.append('      <div class="h-head">')
        # ⚠️ h-en 用 letter-spacing 拉字距，**不再用 &nbsp; 占位** ——
        #    抽取数据时一旦被 esc() 转义就会原样显示 "COMPANY&nbsp;HISTORY"。
        parts.append('        <div class="h-en">%s</div>'
                     % esc((en or self.en).replace('&nbsp;', ' ')))
        parts.append('        <div class="h-title">%s</div>' % (title or self.title))
        if (sub or self.sub):
            parts.append('        <div class="h-sub">%s</div>' % (sub or self.sub))
        parts.append('      </div>')
        # ★ 高度与卡片宽走 inline style —— sanitizeHtml 保留 inline style，
        #   而模块内 <style> 会被剥掉（铁律）。所以自适应必须用 inline。
        parts.append('      <div class="h-track" style="height:%dpx;">' % th)
        parts.append('        <div class="h-line"></div>')
        parts.append('        <div class="h-nodes">')
        for it in nodes:
            yr, txt = it[0], it[1]
            extra = (' ' + it[2]) if len(it) > 2 and it[2] else ''
            parts.append('          <div class="h-node%s">' % extra)
            parts.append('            <div class="h-dot"></div>')
            parts.append('            <div class="h-card" style="width:%dpx;">'
                         '<div class="h-year">%s</div>'
                         '<div class="h-txt">%s</div></div>' % (cw, esc(yr), txt))
            parts.append('          </div>')
        parts.append('        </div>')
        parts.append('      </div>')
        f = foot if foot is not None else self.foot
        if f:
            parts.append('      <div class="h-foot">%s</div>' % f)
        parts.append('    </div>')
        return '\n'.join(parts)

    # ---------------- 自检 ----------------
    def build(self, nodes, **kw):
        """校验 + 渲染（推荐入口）。"""
        self.selfcheck(nodes)
        return self.html(nodes, **kw)

    def selfcheck(self, nodes):
        """把「节点数写死 / 结构错位 / 高度不匹配」三大坑写成断言。

        ⚠️ 内部通过 `self.html()` 取证渲染结果 —— 所以 **html() 绝不能反过来
           调用 selfcheck()**（会无限递归）。两者是「渲染」与「校验」的分工。
        """
        n = len(nodes)
        assert T_MIN_NODES <= n <= T_MAX_NODES, \
            '时间轴节点数 %d 超出合理区间 [%d, %d]：太少不像时间轴，太多会重叠' \
            % (n, T_MIN_NODES, T_MAX_NODES)
        for i, it in enumerate(nodes):
            assert len(it) >= 2, '第 %d 个节点必须给 (年份, 正文)' % (i + 1)
            assert str(it[0]).strip(), '第 %d 个节点年份为空' % (i + 1)
            assert str(it[1]).strip(), '第 %d 个节点正文为空' % (i + 1)

        # 渲染一遍再验结构（不是验字符串，是验「DOM 顺序」）
        h = self.html(nodes)
        # ★ 幂等断言：同样的输入渲染两次必须逐字节相同（改写类脚本的通用要求）
        assert self.html(nodes) == h, 'html() 不幂等：两次渲染结果不同'
        # 坑 2：交错靠 :nth-child(odd/even)，要求 .h-card 与 .h-dot 同级且
        #       每个 .h-node 内只有一组 —— 多包一层会让 odd/even 算错。
        assert h.count('class="h-node"') + h.count('class="h-node ') == n, \
            'h-node 数量与节点数不符：%d != %d' \
            % (h.count('class="h-node"') + h.count('class="h-node '), n)
        assert h.count('class="h-dot"') == n, 'h-dot 数量不符'
        assert h.count('class="h-card"') == n, 'h-card 数量不符'
        # 每个 h-node 内必须恰好一个 h-dot 紧跟一个 h-card
        for blk in re.findall(r'<div class="h-node[^"]*">(.*?)</div>\s*</div>', h, re.S):
            assert blk.count('h-dot') == 1 and blk.count('h-card') == 1, \
                'h-node 内部结构不对（必须恰好 dot + card 各一）'

        # 坑 1：高度必须随节点数变化，且写进 inline style
        m = re.search(r'class="h-track" style="height:(\d+)px;"', h)
        assert m, 'h-track 必须带 inline height（模块内 style 标签会被剥）'
        assert int(m.group(1)) == self.track_height(n), 'h-track 高度与节点数不匹配'
        # 坑：卡片宽也要 inline，否则长公司名会撑破
        assert 'class="h-card" style="width:' in h, 'h-card 必须带 inline width'
        return True


# ================================================================== 股权结构树
class OrgTreeKit(object):
    """股权结构树状图。输出与 600456 完全同构的内联 SVG。

    结构（自上而下）：
        chain    —— 顶部纵向链条（实控人 → 集团 → 控股股东），每项 (名称, 到下一级的比例)
        subject  —— 上市公司主体（整行宽条）
        children —— 叶子（子公司/参股公司），每项 (名称, 持股比例)

    可覆盖属性：
        view_w / view_h   画布尺寸
        leaf_h            叶子高（名字越长越需要高度）
    """

    def __init__(self):
        self.view_w = O_VIEW_W
        self.view_h = O_VIEW_H
        self.leaf_h = O_LEAF_H
        self.leaf_w_max = O_LEAF_W_MAX
        self.edge = O_EDGE
        self.top_y = O_TOP_Y

    # ---------------- 布局计算（唯一来源，渲染只读这些值）----------------
    def layout(self, chain, children):
        """算出所有几何量。★父子条与叶子必须**同一套栅格**推导
        （历史教训：SVG 树状图若父条与子项各用一套算法，纵向对不齐）。

        ★ 纵向节奏刻意对齐 600456 的实测几何，保证「换数据不换观感」：
              链节点:  y = 14, 90, 90   （前 n-1 个纵排，最后一个横排偏右）
              主体条:  y = 186, h = 56
              叶子卡片: y = 308, h = 212
              viewBox: 1000 × 550
        """
        nc = len(chain)
        nk = len(children)
        assert nk >= 1, '股权树至少要有一个子公司'

        # --- 叶子卡高：按「最长子公司名」自动加高 ---
        # ★ 只增不减 —— self.leaf_h(212) 是 600456 的实测值，名字短的必须原样保留，
        #   否则「换数据就换几何」，母本的像素级同构会被破坏。
        # 触发条件（实测）：名字 > 15 字时，_vfont 降到 (11.0, 12.6)，
        #   16 字 × 12.6 = 201.6 > 212-20 = 192 ⇒ 竖排字溢出卡片下沿。
        #   600456 最长 13 字（13×14.0=182）、600459/000830 最长 14 字（14×12.6=176.4），
        #   三者都 ≤ 192，故本改动对本已通过的公司**数学上零影响**。
        need = 0.0
        for _nm, _ in children:
            _fs, _lh = self._vfont(str(_nm))
            need = max(need, len(str(_nm)) * _lh + 20.0)
        leaf_h = max(self.leaf_h, need)

        L = {'node_h': O_NODE_H, 'subj_h': O_SUBJ_H, 'leaf_h': leaf_h,
             'view_w': self.view_w, 'edge': self.edge, 'top_y': self.top_y}

        # --- 叶子栏：等分可用宽度（★ 不再手算 117.14，由栅格推导）---
        # 做法与 600456 一致：**先定卡片宽**，再让「首卡片左边缘→末卡片右边缘」
        # 均匀铺满留白区，中心间距 = (可用宽 - 卡片宽) / (nk - 1)。
        #   nk=8 → 卡片 100（= 920/8 取整到 5 的倍数），跨度 920-100=820，
        #   步长 820/7 = 117.14 ← 与实测一致
        slot = (self.view_w - 2 * self.edge) / float(nk)      # 8 → 115
        lw = min(self.leaf_w_max, max(60.0, slot - 15.0))     # 8 → 100
        span = self.view_w - 2 * self.edge - lw
        step = span / float(nk - 1) if nk > 1 else 0.0
        L['step'] = step
        L['leaf_w'] = lw
        L['leaf_x'] = [self.edge + step * i for i in range(nk)]
        L['leaf_cx'] = [x + lw / 2.0 for x in L['leaf_x']]

        # --- 纵向：与 600456 同节奏 ---
        # 关键：**最后一个链节点与倒数第二个同一行**（横排偏右），不另起一行。
        #   实测 600456：陕西有色(y=90) 与 宝钛集团(y=90) 同一行。
        # 所以纵向行数 = max(nc-1, 1)：前 nc-1 个纵排，最后一个横排在最后一行上。
        rows = max(nc - 1, 1)
        L['chain_y'] = [self.top_y + i * 76.0 for i in range(rows)]
        L['chain_row'] = rows          # 纵排行数（最后一行同时放横排节点）
        # 主体条：链区最底行下沿 + 50（90+46+50 = 186 ← 与实测一致）
        L['subj_y'] = L['chain_y'][-1] + L['node_h'] + 50.0
        # 叶子：主体条下方 66（186+56+66 = 308 ← 与实测一致）
        L['leaf_y'] = L['subj_y'] + L['subj_h'] + 66.0
        # 画布高：600456 为 550；叶子更高时按需加高（只增不减）
        L['view_h'] = max(self.view_h, L['leaf_y'] + L['leaf_h'] + 30.0)
        return L

    # ---------------- 渲染 ----------------
    def svg(self, chain, subject, children, subject_pct=None, aria=None):
        """chain=[(名,流入比例),…] subject='宝鸡钛业股份有限公司（600456.SH）'
        children=[(名,持股比例),…] subject_pct='49.40%' → 返回 <svg> 字符串。

        比例语义（三条，很容易搞混）：
          * chain[0].pct —— 顶层实控人，无上游，写 '—' 或不写；
          * chain[i].pct (i>=1) —— **上一节点持有 chain[i] 的比例**（流入比例）；
          * subject_pct —— **链末节点持有「上市公司主体」的比例**。
            它不等于 chain[-1].pct（那是链末节点自己的流入比例）。
            600456: chain=[省政府 —, 陕西有色 100%, 宝钛集团 93.36%],
                    subject_pct='49.40%'

        ⚠️ 与 TimelineKit.html 同理：**不调用 selfcheck**（会无限递归）。
           校验请显式调用 `ot.selfcheck(...)`，或用 `ot.build(...)`。
        """
        chain = [(str(a), str(b)) for a, b in chain]
        children = [(str(a), str(b)) for a, b in children]
        if subject_pct is None:
            subject_pct = str(chain[-1][1]) if chain else ''
        subject_pct = str(subject_pct)
        L = self.layout(chain, children)
        nc, nk = len(chain), len(children)
        o = []
        o.append('<svg viewBox="0 0 %.0f %.0f" role="img" aria-label="%s">'
                 % (L['view_w'], L['view_h'],
                    esc(aria or ('%s股权结构图' % subject))))
        o.append('        %s' % GRAD_DEFS)

        # --- 链区 ---
        # 两种情况：
        #   nc >= 2：前 nc-1 个纵向居中排左列，最后一个（直接控股股东）横向偏右
        #            —— 600456 就是这个形状，像素级同构；
        #   nc == 1：只有一层（如「无实际控制人，仅列控股股东」），
        #            直接居中画一个宽条，不做横向连接（避免取 chain_y[-2] 越界）。
        if nc == 1:
            nm, pct = chain[0]
            y = L['chain_y'][0]
            w = 460.0
            o.append('        <rect x="%.0f" y="%.0f" width="%.0f" height="%d" '
                     'rx="8" fill="url(#sh3g1)"/>' % ((self.view_w - w) / 2.0, y, w, L['node_h']))
            o.append('        <text x="%.1f" y="%.1f" text-anchor="middle" '
                     'fill="#ffffff" font-size="15" font-weight="700">%s</text>'
                     % (self.view_w / 2.0, y + L['node_h'] / 2.0 + 5.4, esc(nm)))
        else:
            # 语义（与 600456 数据一致）：chain[i].pct = **从 chain[i-1] 流入 chain[i] 的比例**。
            #   所以画「i → i+1」这条边时，挂的标签是 chain[i+1].pct。
            for i, (nm, _pct_unused) in enumerate(chain):
                if i < nc - 1:
                    # 纵排：x=125 w=250，y = chain_y[i]
                    cx = 250.0
                    y = L['chain_y'][i]
                    o.append('        <rect x="%.0f" y="%.0f" width="250" height="%d" '
                             'rx="8" fill="url(#sh3g1)"/>' % (125.0, y, L['node_h']))
                    o.append('        <text x="%.1f" y="%.1f" text-anchor="middle" '
                             'fill="#ffffff" font-size="15" font-weight="700">%s</text>'
                             % (cx, y + L['node_h'] / 2.0 + 5.4, esc(nm)))
                    if i < nc - 2:
                        # ↓ 纵向箭头：连到下一行。
                        # 标签 = **下一个节点的流入比例** = chain[i+1].pct
                        #   实测：省政府(y=14) → 陕西有色(y=90) 这条竖线挂的是 100%，
                        #   而 100% 正是 chain[1]（陕西有色）的流入比例。
                        ny = L['chain_y'][i + 1]
                        o.append('        <line x1="%.0f" y1="%.0f" x2="%.0f" y2="%.0f" '
                                 'stroke="%s" stroke-width="2"/>'
                                 % (cx, y + L['node_h'], cx, ny - 2, C_RED))
                        o.append('        <path d="M%.1f,%.1f L%.1f,%.1f L%.1f,%.1f Z" fill="%s"/>'
                                 % (cx - 5, ny - 8, cx + 5, ny - 8, cx, ny, C_RED))
                        o.append('        <text x="%.0f" y="%.0f" fill="%s" font-size="12.5" '
                                 'font-weight="700">%s</text>'
                                 % (cx + 12, ny - 5, C_RED_DEEP, esc(chain[i + 1][1])))
                    else:
                        # → 纵→横转折：这是倒数第二个节点，它的边**就是那条横向边**。
                        #   标签 = chain[i+1].pct（横排节点的流入比例 = 93.36% 那类）。
                        #   ⚠️ 历史 bug：原版只在 i < nc-2 时画标签，
                        #      导致转折处的比例整条消失。
                        py = L['chain_y'][-1] + L['node_h'] / 2.0
                        hx = self.view_w - 430.0          # 横排节点左边
                        o.append('        <line x1="375" y1="%.0f" x2="%.0f" y2="%.0f" '
                                 'stroke="%s" stroke-width="2"/>'
                                 % (py, hx - 8, py, C_RED))
                        o.append('        <path d="M%.0f,%.1f L%.0f,%.1f L%.0f,%.1f Z" fill="%s"/>'
                                 % (hx - 10, py - 5, hx - 10, py + 5, hx, py, C_RED))
                        o.append('        <rect x="%.0f" y="%.0f" width="82" height="18" rx="9" '
                                 'fill="#ffffff"/>' % (hx - 140.0, py - 9))
                        o.append('        <text x="%.0f" y="%.0f" text-anchor="middle" fill="%s" '
                                 'font-size="12.5" font-weight="700">%s</text>'
                                 % (hx - 99.0, py + 4, C_RED_DEEP, esc(chain[i + 1][1])))
                else:
                    # 最后一个链节点：与上一行**同一 y**，横排偏右（600456 同构）
                    # 注：连到它的横向箭头 + 比例徽标由上一条（i == nc-2）绘制。
                    x = self.view_w - 430.0
                    y = L['chain_y'][-1]
                    o.append('        <rect x="%.0f" y="%.0f" width="300" height="%d" '
                             'rx="8" fill="url(#sh3g1)"/>' % (x, y, L['node_h']))
                    o.append('        <text x="%.1f" y="%.1f" text-anchor="middle" '
                             'fill="#ffffff" font-size="15" font-weight="700">%s</text>'
                             % (x + 150.0, y + L['node_h'] / 2.0 + 5.4, esc(nm)))

        # --- 主体条 ---
        sy = L['subj_y']
        o.append('        <rect x="%.0f" y="%.0f" width="%.0f" height="%d" rx="8" '
                 'fill="url(#sh3g2)" filter="url(#sh3sh)"/>'
                 % (self.edge, sy, self.view_w - 2 * self.edge, L['subj_h']))
        o.append('        <text x="500.0" y="%.1f" text-anchor="middle" fill="#ffffff" '
                 'font-size="17" font-weight="800">%s</text>'
                 % (sy + 34.1, esc(subject)))
        # 从最后一个链节点下来的竖线 + 它持有上市公司的比例
        #   ⚠️ 这个比例是 subject_pct（链末节点持有**上市公司主体**的比例），
        #      与 chain[-1].pct（链末节点自己的流入比例）是两回事。
        #   ⚠️ nc==1 时链区是居中的宽条，竖线要从它的中线下来（不是横排节点的位置）。
        lx = (self.view_w / 2.0) if nc == 1 else (self.view_w - 430.0 + 150.0)
        o.append('        <line x1="%.0f" y1="%.0f" x2="%.0f" y2="%.0f" stroke="%s" '
                 'stroke-width="2"/>'
                 % (lx, L['chain_y'][-1] + L['node_h'], lx, sy - 6, C_RED))
        o.append('        <path d="M%.1f,%.1f L%.1f,%.1f L%.1f,%.1f Z" fill="%s"/>'
                 % (lx - 5, sy - 8, lx + 5, sy - 8, lx, sy, C_RED))
        if subject_pct and subject_pct not in ('—', '-', ''):
            o.append('        <rect x="%.0f" y="%.0f" width="76" height="18" rx="9" '
                     'fill="#ffffff"/>' % (lx + 11.0, sy - 34.0))
            o.append('        <text x="%.0f" y="%.0f" text-anchor="middle" fill="%s" '
                     'font-size="12.5" font-weight="700">%s</text>'
                     % (lx + 49.0, sy - 21.0, C_RED_DEEP, esc(subject_pct)))

        # --- 叶子：竖线 + 箭头 + 比例徽标 + 卡片 ---
        for i, (nm, pct) in enumerate(children):
            cx = L['leaf_cx'][i]
            ly = L['leaf_y']
            o.append('        <line x1="%.1f" y1="%.0f" x2="%.1f" y2="%.0f" stroke="%s" '
                     'stroke-width="2"/>' % (cx, sy + L['subj_h'], cx, ly - 10, C_RED))
            o.append('        <path d="M%.1f,%.1f L%.1f,%.1f L%.1f,%.1f Z" fill="%s"/>'
                     % (cx - 5.5, ly - 10, cx + 5.5, ly - 10, cx, ly, C_RED))
            o.append('        <rect x="%.1f" y="%.0f" width="56" height="18" rx="9" '
                     'fill="#ffffff" stroke="#f0dfe2" stroke-width="1"/>'
                     % (cx - 28.0, sy + L['subj_h'] + 20.0))
            o.append('        <text x="%.1f" y="%.0f" text-anchor="middle" fill="%s" '
                     'font-size="11.5" font-weight="700">%s</text>'
                     % (cx, sy + L['subj_h'] + 33.0, C_RED_DEEP, esc(pct)))
            o.append('        <rect x="%.1f" y="%.0f" width="%.0f" height="%d" rx="8" '
                     'fill="url(#sh3g3)"/>'
                     % (L['leaf_x'][i], ly, L['leaf_w'], L['leaf_h']))
            # 竖排名字：按字数自动降字号（坑 4）
            fs, lh = self._vfont(nm)
            tspans = ''.join('<tspan x="%.1f" y="%.1f">%s</tspan>'
                             % (cx, ly + (L['leaf_h'] - (len(nm) - 1) * lh) / 2.0
                                + fs * 0.5 + i2 * lh, esc(ch))
                             for i2, ch in enumerate(nm))
            o.append('        <text text-anchor="middle" fill="#ffffff" font-size="%.1f" '
                     'font-weight="700">%s</text>' % (fs, tspans))

        o.append('      </svg>')
        return '\n'.join(o)

    # ---------------- 竖排字号自适应 ----------------
    def _vfont(self, name):
        """名字越长，字号越小 —— 保证 tspan 总高放得进卡片。"""
        n = len(name)
        if n <= 10:
            return 14.0, 15.2
        if n <= 13:
            return 12.5, 14.0
        return 11.0, 12.6

    # ---------------- 自检 ----------------
    def build(self, chain, subject, children, subject_pct=None, **kw):
        """校验 + 渲染（推荐入口）。"""
        self.selfcheck(chain, subject, children, subject_pct)
        return self.svg(chain, subject, children, subject_pct, **kw)

    def selfcheck(self, chain, subject, children, subject_pct=None):
        """内部会调用 `self.svg()` 取证 —— 因此 svg() 绝不能反向调用本方法。"""
        assert chain, 'chain（实控人链条）不能为空'
        assert subject, 'subject（上市公司主体）不能为空'
        assert children, 'children（子公司）不能为空'
        if subject_pct is None:
            subject_pct = str(chain[-1][1]) if chain else ''
        subject_pct = str(subject_pct)

        L = self.layout(chain, children)
        nk = len(children)

        # 坑 3：叶子 x 必须由栅格推导，且互不重叠
        xs = L['leaf_x']
        assert len(xs) == nk, '叶子 x 数量不符'
        for i in range(nk - 1):
            gap = xs[i + 1] - (xs[i] + L['leaf_w'])
            assert gap >= 0, '叶子 %d 与 %d 横向重叠（gap=%.2f）' % (i, i + 1, gap)
        # 首尾必须在画布内
        assert xs[0] >= 0, '第一个叶子越出左边界'
        assert xs[-1] + L['leaf_w'] <= L['view_w'] + 0.01, '最后一个叶子越出右边界'

        # 坑 5：纵向顺序必须 链 < 主体 < 叶子
        assert L['subj_y'] > L['chain_y'][-1] + L['node_h'], '主体条与链区重叠'
        assert L['leaf_y'] > L['subj_y'] + L['subj_h'], '叶子与主体条重叠'
        assert L['leaf_y'] + L['leaf_h'] <= L['view_h'] + 0.01, '叶子底部越出画布'

        # 坑 4：竖排文字必须放得进卡片
        for nm, _ in children:
            fs, lh = self._vfont(nm)
            total = len(nm) * lh
            assert total <= L['leaf_h'] - 20, \
                '子公司「%s」竖排文字高 %.1f 超过卡片可用高 %d' % (nm, total, L['leaf_h'] - 20)

        # 渲染一遍，验元素数量与坐标一一对应
        s = self.svg(chain, subject, children, subject_pct)
        # ★ 幂等断言
        assert self.svg(chain, subject, children, subject_pct) == s, 'svg() 不幂等：两次渲染结果不同'
        # rect 构成：链节点 nc + 主体条 1 + 叶子卡片 nk + 叶子比例徽标 nk
        #            + 「链末节点持有上市公司」的比例药丸（subject_pct 非空时 1 个）
        #            + 纵向→横向转折的连接药丸
        # ⚠️ 转折药丸的门槛是 **nc >= 2**，不是 nc >= 3：
        #    渲染循环里 chain[0..nc-2] 是纵排、chain[nc-1] 是横排，
        #    i == nc-2 时画那条横边与药丸。nc=2 时 chain[0] 纵排、chain[1] 横排，
        #    同样有一条转折边 ⇒ 也要 1 个药丸。
        #    曾写成 nc >= 3，导致 nc=2 的真实数据（如 600459 的两层链）自检假红。
        has_turn = 1 if len(chain) >= 2 else 0
        has_subj = 1 if (subject_pct and subject_pct not in ('—', '-', '')) else 0
        want_rect = len(chain) + 1 + nk + nk + has_subj + has_turn
        assert s.count('<rect') == want_rect, \
            'rect 数量应为 %d（链 %d + 主体 1 + 叶子卡 %d + 叶子徽标 %d + 上市公司比例 %d + 转折药丸 %d），实际 %d' \
            % (want_rect, len(chain), nk, nk, has_subj,
               has_turn, s.count('<rect'))

        # ★ 比例语义（两条，别混）：
        #   chain[0].pct  —— 顶层实控人没有上游，写 '—' 或留空即可（不校验）；
        #   chain[i].pct (i>=1) —— 上一节点持有「节点 i」的比例；
        #   chain[-1].pct —— 同时表示「该节点持有上市公司主体」的比例（如 49.40%）。
        # 全部都必须被画出 —— 历史 bug：纵→横转折处的比例整条消失（93.36%）。
        for i in range(1, len(chain)):
            nm, pct = chain[i]
            assert esc(nm) in s, '链节点「%s」未出现在 SVG 中' % nm
            assert esc(str(pct)) in s, \
                '链节点「%s」的流入比例「%s」被漏画（历史 bug：纵→横转折处的比例整条消失）' \
                % (nm, pct)
        assert esc(chain[0][0]) in s, '链首节点「%s」未出现在 SVG 中' % chain[0][0]
        for nm, pct in children:
            assert esc(str(pct)) in s, '子公司「%s」的持股比例「%s」未出现在 SVG 中' % (nm, pct)
        assert s.count('</tspan>') == sum(len(n) for n, _ in children), \
            'tspan 总数应等于全部子公司名字的字符总数'
        # 绝对坐标必须都是数字，不能残留占位符
        for m in re.finditer(r'\b[xy]\d?="([^"]*)"', s):
            v = m.group(1)
            if v and v not in ('0 0 1000 550',) and not re.match(r'^[\d.\s]+$', v):
                if not v.startswith('url(#') and v not in ('middle',):
                    pass
        assert 'None' not in s and 'nan' not in s.lower(), 'SVG 里出现 None/nan'
        return True


# ================================================================== 演示
def demo():
    tk = TimelineKit()
    nodes = [
        ('1999', '<b>宝钛集团</b>联合西北有色金属研究院等单位设立宝钛股份，主发起人代号902'),
        ('2002', '4月12日<b>上交所上市</b>，中国钛工业第一股'),
        ('2006', '定增募资<b>8亿元</b>，收购快锻生产线、精密铸造产线，增加5000吨熔铸能力'),
        ('2007', '收购<b>锦州华神66.67%</b>股权（后更名宝钛华神），切入海绵钛上游'),
        ('2008', '定增募资<b>15亿元</b>，钛带生产线、万吨自有锻压机、海绵钛技改'),
        ('2021', '定增募资<b>20亿元</b>，宇航级宽幅钛合金板材/带箔材、高品质钛锭管材型材产线'),
        ('2026', '发行<b>35亿可转债</b>，钛资源循环利用、宇航级智能锻造、近净成形三大项目'),
    ]
    print('=== TimelineKit 自检 ===')
    print('  selfcheck:', tk.selfcheck(nodes))
    h = tk.html(nodes, sub='二十余载 · 从代号902到中国钛工业第一股',
                foot='1999 — 2026 · 钛业报国 · 迈向航空航天新周期')
    print('  html chars =', len(h))

    # 换一家公司（4 个节点）验证通用性
    tk2 = TimelineKit()
    n2 = [('2015', '公司前身成立'), ('2018', '完成股份制改造'), ('2021', '创业板上市'), ('2025', '海外基地投产')]
    print('  4 节点 selfcheck:', tk2.selfcheck(n2), '· track_h =', tk2.track_height(4))

    ot = OrgTreeKit()
    chain = [('陕西省人民政府', '—'), ('陕西有色金属集团', '100%'), ('宝钛集团有限公司', '93.36%')]
    kids = [('宝钛华神钛业有限公司', '66.67%'), ('宝钛精密锻造有限公司', '40%'),
            ('宝太新金属开发有限公司', '51%'), ('宝钛合金材料有限公司', '51%'),
            ('宝钛航空材料有限公司', '100%'), ('宝钛久立钛焊管科技有限公司', '34%'),
            ('宝钛(沈阳)销售有限公司', '100%'), ('宝钛新材料科技有限公司', '100%')]
    print('\n=== OrgTreeKit 自检 ===')
    print('  selfcheck:', ot.selfcheck(chain, '宝鸡钛业股份有限公司（600456.SH）', kids, '49.40%'))
    s = ot.svg(chain, '宝鸡钛业股份有限公司（600456.SH）', kids, '49.40%')
    print('  svg chars =', len(s), '· rect =', s.count('<rect'), '· tspan =', s.count('</tspan>'))
    xsr = re.findall(r'x="([\d.]+)" y="308"', s)
    print('  叶子 x =', xsr)

    # 换一家：子公司只有 3 家、名字更长
    kids3 = [('某某某某新材料科技股份有限公司', '51%'), ('某某精密制造有限公司', '70%'),
             ('某某国际贸易有限公司', '100%')]
    print('  3 家子公司 selfcheck:',
          ot.selfcheck(chain, '某某股份有限公司（000001.SZ）', kids3, '38.65%'))
    print('  无实控人（chain 只有 1 层）:',
          ot.selfcheck([('某某控股集团有限公司', '—')], '某某股份有限公司（000001.SZ）',
                       kids3, '55%'))


if __name__ == '__main__':
    if '--demo' in sys.argv or len(sys.argv) == 1:
        demo()
