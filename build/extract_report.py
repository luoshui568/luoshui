# -*- coding: utf-8 -*-
"""把桌面上的模块化研报 HTML 拆成「可入库的结构化数据」+「红色主题 CSS」。

产出：
  build/report_theme.css        红色主题样式（由原蓝色体系映射而来，可重复生成）
  build/seed/report_600456.json 研报结构化数据（hero / 核心结论 / KPI / 目录 / 模块 / 图表 / 页脚）

图表由 rpt_dump.js（Node 打桩 echarts）导出，函数已转成 {{fn:源码}} 标记，
这里再映射成具名标记，运行时由前端的 reviver 还原。
"""
import io, json, os, re, sys, colorsys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def _parse_args():
    """默认 = 600456 宝钛股份（保持原有行为不变）。

    其他研报用命令行覆盖，例如：
      python extract_report.py --code 002237 --name 恒邦股份 \\
        --src "%USERPROFILE%/Desktop/恒邦股份半年报追踪研究报告-模块版-20260826.html" \\
        --opts build/_rpt_opts_002237.json --seed build/seed/report_002237.json
    """
    a = sys.argv[1:]
    get = lambda k, d: (a[a.index(k) + 1] if k in a and a.index(k) + 1 < len(a) else d)
    code = get('--code', '600456')
    return {
        'code': code,
        'name': get('--name', '宝钛股份'),
        'src': get('--src', os.path.join(os.path.expanduser("~"), "Desktop",
                                        "宝钛股份深度研究报告-模块版-20260826.html")),
        'opts': get('--opts', os.path.join(HERE, "_rpt_opts.json")),
        'css_out': get('--css', os.path.join(HERE, "report_theme.css")),
        'seed_out': get('--seed', os.path.join(HERE, "seed", "report_%s.json" % code)),
        'theme': get('--theme', 'red'),
    }


ARGS = _parse_args()
SRC = ARGS['src']
OPT = ARGS['opts']
CSS_OUT = ARGS['css_out']
SEED_OUT = ARGS['seed_out']

# ---------------------------------------------------------------- 红色主题映射
# 原研报是「蓝 + 金」体系，这里整体映射到「正红 + 金」体系，
# 与工作台视觉规范保持一致：#c8102e 正红 / #8c0a20 深红 / #e63946 亮红 / #c9a227 金
COLOR_MAP = {
    # —— 主色：蓝 → 红 ——
    "#1f5fd6": "#c8102e", "#1F5FD6": "#C8102E",
    "#1f4e78": "#8c0a20", "#1F4E78": "#8C0A20",
    "#0f1d3a": "#4a0710", "#0F1D3A": "#4A0710",
    "#174a9e": "#a3122a", "#174A9E": "#A3122A",
    "#3d7cf0": "#e63946", "#3D7CF0": "#E63946",
    "#2f6fe0": "#d92638", "#2F6FE0": "#D92638",
    "#2e6da4": "#c8102e", "#2E6DA4": "#C8102E",
    # —— 蓝色浅底 → 红色浅底 ——
    "#e9f0fd": "#fdecee", "#E9F0FD": "#FDECEE",
    "#f0f6fd": "#fdf2f3", "#F0F6FD": "#FDF2F3",
    "#f8faff": "#fffafb", "#F8FAFF": "#FFFAFB",
    "#f8fafd": "#fffbfb", "#F8FAFD": "#FFFBFB",
    "#edf1f8": "#faf0f1", "#EDF1F8": "#FAF0F1",
    "#f0f4f9": "#fdf4f5", "#F0F4F9": "#FDF4F5",
    "#cfd9f0": "#f2dcdf", "#CFD9F0": "#F2DCDF",
    "#c9dcf0": "#f6dfe2", "#C9DCF0": "#F6DFE2",
    "#dde3ee": "#f1dee1", "#DDE3EE": "#F1DEE1",
    "#eaedf4": "#f7eaec", "#EAEDF4": "#F7EAEC",
    # —— 图表里的蓝/青灰 → 红/暖灰 ——
    "#8fa8e0": "#e8939c", "#8FA8E0": "#E8939C",
    "#8aa3cc": "#caa2a8", "#8AA3CC": "#CAA2A8",
    "#9fb6cc": "#dcaab0", "#9FB6CC": "#DCAAB0",
    "#b7cce0": "#f1bdc3", "#B7CCE0": "#F1BDC3",
    "#3b82f6": "#e63946", "#3B82F6": "#E63946",
    "#06b6d4": "#c9a227", "#06B6D4": "#C9A227",
    "#8b5cf6": "#a3122a", "#8B5CF6": "#A3122A",
    "#a855f7": "#8c0a20", "#A855F7": "#8C0A20",
    # —— 中性文字/描边：冷灰 → 暖灰 ——
    "#2b3a4a": "#3a2024", "#2B3A4A": "#3A2024",
    "#3b4358": "#4a2a2f", "#3B4358": "#4A2A2F",
    "#1f2430": "#2b161a", "#1F2430": "#2B161A",
    "#20242e": "#26161a", "#20242E": "#26161A",
    "#44506a": "#5b3a40", "#44506A": "#5B3A40",
    "#7c8398": "#9a7d82", "#7C8398": "#9A7D82",
    "#7a8a99": "#a0888d", "#7A8A99": "#A0888D",
    "#9aa4b5": "#b09a9e", "#9AA4B5": "#B09A9E",
    "#8b95a7": "#a88f94", "#8B95A7": "#A88F94",
    "#b8c0cc": "#dcb9be", "#B8C0CC": "#DCB9BE",
    "#cfd5e0": "#eed6d9", "#CFD5E0": "#EED6D9",
    "#e8ecf4": "#f6e6e9", "#E8ECF4": "#F6E6E9",
    "#e8e4d6": "#efe0dd", "#E8E4D6": "#EFE0DD",
    # —— 背景 ——
    "#f6f6f2": "#fdf7f8", "#f6f6f2": "#fdf7f8",
    "#fbfbf8": "#fffafb", "#FBFBF8": "#FFFAFB",
    "#f4f4ee": "#fbedee", "#F4F4EE": "#FBEDEE",
}


def _hue_remap(r, g, b, a=None):
    """把「蓝调」色相整体转到正红，保留原有的明度与饱和度。
    这样那批没被显式映射覆盖的浅蓝底（#f5f9ff / #e0e9f7 …）与 rgba(31,95,214,.12)
    之类也能一起转过来，底色不会残留冷色。"""
    h, l, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
    deg = h * 360
    if not (185 <= deg <= 265):
        return None
    nr, ng, nb = colorsys.hls_to_rgb(352 / 360.0, l, min(1.0, s * 1.08))
    return (round(nr * 255), round(ng * 255), round(nb * 255), a)


_HEX_RE = re.compile(r"#([0-9a-fA-F]{6})\b")
_RGBA_RE = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)")


def _sweep(t):
    def fh(m):
        out = _hue_remap(int(m.group(1)[0:2], 16), int(m.group(1)[2:4], 16), int(m.group(1)[4:6], 16))
        return "#%02x%02x%02x" % out[:3] if out else m.group(0)

    def fr(m):
        out = _hue_remap(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                         m.group(4) if m.group(4) else None)
        if not out:
            return m.group(0)
        rgb = "rgba(%d,%d,%d" % out[:3] if out[3] is not None else "rgb(%d,%d,%d" % out[:3]
        return rgb + ("," + out[3] if out[3] is not None else "") + ")"

    return _RGBA_RE.sub(fr, _HEX_RE.sub(fh, t))


def recolor(t):
    for a, b in COLOR_MAP.items():
        t = t.replace(a, b)
    return _sweep(t)


# ---------------------------------------------------------------- 函数具名标记
def fn_token(src, chart_id):
    """把 JS 函数源码映射成可被前端 reviver 还原的具名标记。"""
    s = re.sub(r"\s+", " ", src).strip()
    s = s.replace("\\n", "\n")
    if "split(' ').join(" in s:
        return "catBreak"                       # 类目名换行（「项目一 熔铸扩能」→ 两行）
    if "p.value==null" in s:
        return "nullDash"                       # null 显示为 —
    m = re.search(r"return v\+'(.*?)';", s)
    if m:
        return "unit:" + m.group(1)             # 数值 + 单位
    m = re.search(r"return p\.value\+'(.*?)';", s)
    if m:
        return "valUnit:" + m.group(1)
    # 指定数据点覆盖标签：p.dataIndex===N ? '-23.4%' : '{c}'
    # （贵研铂业底稿用过：某个年份实际是负值/含同比，标签要写成特例）
    m = re.search(r"p\.dataIndex\s*===?\s*(\d+)\s*\?\s*'([^']*)'\s*:\s*'([^']*)'", s)
    if m:
        if m.group(3).replace(" ", "") != "{c}":
            return None                         # 兜底不是 '{c}' 的形态，宁可不还原
        # ⚠️ 标记内部不能出现花括号：_scan_fn 按「无嵌套花括号」配对，
        #    后面的 fail-closed 自检也按 [^{}]+ 判「规范形态」。
        #    所以把 {c} 写成 @c@ 占位，前端再还原。
        return "idxText:%s:%s" % (m.group(1), m.group(2).replace("{c}", "@c@"))
    if "cs[p.dataIndex]" in s:
        # 原脚本里的具名常量，这里直接展开成显式色值（红色系）
        return "idxColorList:#e8909a,#c8102e,#c9a227,#8c0a20"
    m = re.search(r"return \[(.*?)\]\[p\.dataIndex\]", s)
    if m:
        return "idxColorList:" + m.group(1).replace("'", "").replace(" ", "")
    m = re.search(r"p\.dataIndex<(\d+) \? '(#[0-9a-fA-F]{3,6})' : '(#[0-9a-fA-F]{3,6})'", s)
    if m:
        return "idxColorBreak:%s:%s:%s" % (m.group(1), m.group(2), m.group(3))
    if "revStackBase[p.dataIndex]+revStackAdd[p.dataIndex]" in s:
        return "stackSum:rev"
    if "netStackBase[p.dataIndex]+netStackAdd[p.dataIndex]" in s:
        return "stackSum:net"
    if "var y = allYears[idx]" in s:
        return "forecastTip"
    return None


def _scan_fn(s):
    """扫出字符串里所有 {{fn:…}} 标记，返回 [(start, end, src), …]。

    ⚠️ 绝对不能用 `re.sub(r'\\{\\{fn:([\\s\\S]*?)\\}\\}', …)`：非贪婪会在**函数体的第一个 `}}`**
    处收尾，而 `function(v){return v+' 亿元';}` 的结尾正好就是 `}}` —— 于是匹配只吃掉
    前两个花括号，剩下一个 `}` 留在原地，存库的标记变成 `{{fn:unit: 亿元}}}`。
    前端 reviver 按**整串**匹配 `/^\\{\\{fn:(.*)\\}\\}$/`，多一个 `}` 就还原失败：
      * `catBreak` / `nullDash` / `forecastTip` 这类**无参数**标记：名字变成 `catBreak}` →
        查不到 → 标记原样留在 option 里（tooltip 直接显示 `{{fn:forecastTip}}` 文字）
      * `unit: 亿元}` → 单位后多一个花括号；`idxColorList:…#8c0a20}` → 最后一个颜色非法
    所以这里用**配对大括号**的方式扫描，函数体里嵌套 `{}` 也不会错。"""
    out = []
    i = 0
    while True:
        j = s.find("{{fn:", i)
        if j < 0:
            return out
        k = j + 5
        depth = 0
        while k < len(s):
            c = s[k]
            if c == '{':
                depth += 1
            elif c == '}':
                if depth == 0:
                    break
                depth -= 1
            k += 1
        if k < len(s) and s[k:k + 2] == '}}':
            end, src = k + 2, s[j + 5:k]
        else:                                   # 畸形标记：整段丢弃，避免把残渣写进库
            end, src = min(k + 1, len(s)), s[j + 5:k]
        out.append((j, end, src))
        i = end


def conv_fns(node, chart_id, unknown):
    if isinstance(node, str):
        marks = _scan_fn(node)
        if not marks:
            return node
        buf, pos = [], 0
        for a, b, src in marks:
            buf.append(node[pos:a])
            tok = fn_token(src, chart_id)
            if tok is None:
                unknown.append(src[:110])       # 认不出的函数直接去掉（不能带着源码入库）
            else:
                buf.append("{{fn:" + tok + "}}")
            pos = b
        buf.append(node[pos:])
        return "".join(buf)
    if isinstance(node, list):
        return [conv_fns(x, chart_id, unknown) for x in node]
    if isinstance(node, dict):
        return {k: conv_fns(v, chart_id, unknown) for k, v in node.items()}
    return node


# ---------------------------------------------------------------- HTML 切分
def blk(s, start, tag):
    """从 start（该标签 '<' 的位置）起，做标签配对，返回闭合后的结束下标（不含）。"""
    open_re = re.compile(r"<" + tag + r"(?=[\s>/])", re.I)
    close_re = re.compile(r"</" + tag + r"\s*>", re.I)
    depth, i = 0, start
    while i < len(s):
        o = open_re.search(s, i)
        c = close_re.search(s, i)
        if c is None:
            return len(s)
        if o is not None and o.start() < c.start():
            depth += 1
            i = o.end()
        else:
            depth -= 1
            i = c.end()
            if depth == 0:
                return i
    return len(s)


def take(s, needle, tag, frm=0):
    i = s.find(needle, frm)
    if i < 0:
        return None, frm
    j = blk(s, i, tag)
    return s[i:j], j


def main():
    html = io.open(SRC, encoding="utf-8").read()
    os.makedirs(os.path.dirname(SEED_OUT), exist_ok=True)

    # ---------- CSS ----------
    cs = html.index("<style>") + len("<style>")
    ce = html.index("</style>", cs)
    css_raw = html[cs:ce]

    # ---------- body（</style> 到其后的第一个 <script>） ----------
    bs = ce + len("</style>")
    be = html.index("<script>", bs)
    body = html[bs:be]

    # ---------- hero ----------
    hero, _ = take(body, '<header class="hero">', "header")
    kicker = re.search(r'<div class="kicker">(.*?)</div>', hero, re.S).group(1).strip()
    title = re.search(r"<h1>(.*?)</h1>", hero, re.S).group(1).strip()
    sub = re.search(r'<div class="sub">(.*?)</div>', hero, re.S).group(1).strip()
    badges = [x.strip() for x in re.findall(r'<span class="badge">(.*?)</span>', hero, re.S)]

    # ---------- 核心结论 ----------
    ver, _ = take(body, '<div class="verdict">', "div")
    vt = re.search(r'<div class="vt">(.*?)</div>', ver, re.S).group(1).strip()
    vc = re.search(r'<div class="vc">([\s\S]*?)</div>\s*</div>\s*$', ver.strip(), re.S)
    if vc is None:
        vc = re.search(r'<div class="vc">([\s\S]*)', ver, re.S)
    verdict_html = vc.group(1).strip()

    # ---------- 8 项 KPI ----------
    kpi, _ = take(body, '<div class="grid4">', "div")
    kpis = []
    for st in re.finditer(r'<div class="stat">([\s\S]*?)</div></div>', kpi):
        seg = st.group(1) + "</div>"
        lm = re.search(r'<div class="label">(.*?)</div>', seg, re.S)
        vm = re.search(r'<div class="val([^"]*)"([^>]*)>([\s\S]*?)</div>\s*$', seg, re.S)
        if not lm or not vm:
            continue
        valhtml = vm.group(3)
        sm = re.search(r"<small>(.*?)</small>", valhtml, re.S)
        num = re.sub(r"<small>.*?</small>", "", valhtml, flags=re.S).strip()
        num = re.sub(r"<[^>]+>", "", num).strip()
        sm2 = re.search(r'style="([^"]*)"', vm.group(2) or "")
        kpis.append({
            "label": re.sub(r"<[^>]+>", "", lm.group(1)).strip(),
            "val": num,
            "unit": sm.group(1).strip() if sm else "",
            "cls": vm.group(1).strip(),
            "style": sm2.group(1).strip() if sm2 else "",
        })
    kn = re.search(r'<p class="muted" style="margin:-6px[^"]*">([\s\S]*?)</p>', body)
    kpi_note = kn.group(1).strip() if kn else ""

    # ---------- 目录 ----------
    toc_html, _ = take(body, '<nav class="toc">', "nav")
    toc = []
    for a in re.finditer(r'<a href="#([^"]+)">(.*?)</a>', toc_html):
        toc.append({"anchor": a.group(1), "text": a.group(2).strip()})

    # ---------- 模块（card + essence） ----------
    mods, charts_html = [], []
    i = body.find('<footer')
    head = body[:i] if i > 0 else body
    footer_html = ""
    if i > 0:
        footer_html = body[i:blk(body, i, "footer")]

    # 先抓 essence（一句话本质）；它占用了 m23 锚点，这里改名为 essence，
    # m23 锚点交还给它下面那张「投资结论」卡片
    es_i = head.find('<div class="essence" id="m23"')
    essence_html = ""
    if es_i >= 0:
        es_end = blk(head, es_i, "div")
        essence_html = head[es_i:es_end].replace('id="m23"', 'id="essence"', 1)
        head = head[:es_i] + head[es_end:]

    # 全部卡片：注意 23 号卡片没有 id，所以只能靠 <h2><span class="no"> 取编号
    mods = []
    pos = 0
    while True:
        m = re.search(r'<div class="card"', head[pos:])
        if not m:
            break
        st = pos + m.start()
        en = blk(head, st, "div")
        seg = head[st:en]
        no = re.search(r'<span class="no">(\d+)</span>', seg)
        h2 = re.search(r'<h2><span class="no">\d+</span>([\s\S]*?)</h2>', seg)
        if not no or not h2:
            pos = en
            continue
        inner = seg[h2.end():]
        inner = inner.rsplit("</div>", 1)[0]        # 去掉卡片自身的收尾 </div>
        mods.append({"no": no.group(1), "title": h2.group(1).strip(), "html": inner.strip()})
        pos = en

    # ---------- 图表 ----------
    i = body.find('<footer')
    scope = body[:i] if i > 0 else body
    seen = []
    for m in re.finditer(r'<div id="(chart[A-Za-z_0-9]*)"([^>]*)></div>', scope):
        seen.append((m.group(1), m.group(2)))

    dup = json.load(io.open(OPT, encoding="utf-8"))
    unknown = []
    opts = {}
    for cid, opt in dup["opts"].items():
        opts[cid] = conv_fns(opt, cid, unknown)

    CHART_NAMES = {
        "chart1": "公司营业收入与归母净利润（2010-2025）",
        "chart2": "产品收入结构（2025）",
        "chart3": "毛利率 / 净利率 / ROE（2014-2025）",
        "chart4": "海绵钛价格走势（2015-2025）",
        "chart5": "钛产品销售均价与成本均价（2016-2025）",
        "chart6": "费用结构（2018-2025）",
        "chart7": "钛产品产量与销量（2016-2025）",
        "chart8": "全球海绵钛产量（2015-2025）",
        "chart_pbpe": "PB / PE(TTM) 历史走势",
        "chart_eps": "EPS(TTM) 与股价",
        "chartInvest": "三大募投项目投资规模对比",
        "chartProfit": "达产经济效益对比",
        "chartIRR": "税后 IRR 与投资回收期",
        "chartForecast": "上市以来营收/净利 + 募投投产后预测（2002-2033E）",
        "chartCapacity": "募投新增产能构成",
        "chartSales": "产能 vs 产销对比",
    }
    def derive_name(cid):
        """图表名：优先取同一模块里紧邻容器之前的 <h3> 小标题，否则用模块标题。
        （宝钛那份有手工整理的 CHART_NAMES 覆盖，其他研报自动推导即可。）"""
        for m in mods:
            key = 'id="%s"' % cid
            if key not in m["html"]:
                continue
            seg = m["html"][:m["html"].index(key)]
            last = None
            for mm in re.finditer(r"<h3[^>]*>([\s\S]*?)</h3>", seg):
                last = mm
            if last is not None and len(seg) - last.end() < 1600:
                t = re.sub(r"<[^>]+>", "", last.group(1)).strip()
                if t:
                    return t
            return m["title"]
        return cid

    charts = []
    for n, (cid, _attrs) in enumerate(seen, 1):
        if cid not in opts:
            print("  !! 图表 %s 有容器但没抓到 option" % cid)
            continue
        charts.append({"id": cid, "seq": n,
                       "name": CHART_NAMES.get(cid) or derive_name(cid),
                       "opt": opts[cid]})

    # 模块 HTML 里把图表容器改成 data-chart 占位（去掉 id，避免重复 id）
    for mod in mods:
        def rep(mm):
            return '<div data-chart="%s"%s></div>' % (mm.group(1), mm.group(2))
        mod["html"] = re.sub(r'<div id="(chart[A-Za-z_0-9]*)"([^>]*)></div>', rep, mod["html"])

    seed = {
        "report": {
            "code": ARGS['code'], "name": ARGS['name'],
            "kicker": kicker, "title": title, "subtitle": sub, "badges": badges,
            "verdict_title": vt, "verdict_html": verdict_html,
            "kpis": kpis, "kpi_note": kpi_note,
            "toc": toc, "essence_html": essence_html, "footer_html": footer_html,
            "theme": ARGS['theme'],
        },
        "mods": [dict(m, seq=n) for n, m in enumerate(mods, 1)],
        "charts": charts,
    }

    # ---------- 输出 ----------
    # ⚠️ 主题 CSS 只在**显式传 --css** 时才写。
    # 原因：网上那份 report_theme.css 是从宝钛底稿生成的「超集」（135 个类），
    # 而恒邦/贵研底稿只有 76 个类；直接按底稿覆盖会把宝钛研报用到的 59 个类抹掉，
    # 已有研报立刻掉样式。所以默认**只读不写**。
    css = recolor(css_raw)
    if '--css' in sys.argv:
        io.open(CSS_OUT, "w", encoding="utf-8").write(css)
        print("主题 CSS       已写出 %s（%d 字符）" % (os.path.basename(CSS_OUT), len(css)))
    else:
        print("主题 CSS       跳过（未传 --css；现有 %s 是超集，不能覆盖）" % os.path.basename(CSS_OUT))

    # ECharts 库本体单独落一份，供 build.py 注入研报页（保证离线可用）
    blk1 = re.search(r"<script[^>]*>([\s\S]*?)</script>", html).group(1)
    libdir = os.path.join(HERE, "lib")
    os.makedirs(libdir, exist_ok=True)
    ech = os.path.join(libdir, "echarts.min.js")
    if not os.path.exists(ech):
        io.open(ech, "w", encoding="utf-8").write(blk1)
        print("ECharts 库      已写出 %.0f KB" % (os.path.getsize(ech) / 1024))
    else:
        print("ECharts 库      已存在，跳过")

    seed_txt = recolor(json.dumps(seed, ensure_ascii=False, separators=(",", ":")))
    io.open(SEED_OUT, "w", encoding="utf-8").write(seed_txt)

    print("源文件        %s（%.0f KB）" % (os.path.basename(SRC), os.path.getsize(SRC) / 1024))
    print("CSS 原始/映射 %d → %d 字符" % (len(css_raw), len(css)))
    print("ECharts 库    %.0f KB" % (os.path.getsize(os.path.join(libdir, "echarts.min.js")) / 1024))
    print("模块          %d 个：%s" % (len(mods), " ".join(m["no"] for m in mods)))
    print("标题          %s" % " / ".join(m["title"][:12] for m in mods[:6]))
    print("图表          %d 张（容器 %d 个）" % (len(charts), len(seen)))
    print("KPI           %d 项 / 徽标 %d 个 / 目录 %d 条" % (len(kpis), len(badges), len(toc)))
    print("seed          %.0f KB" % (len(seed_txt.encode("utf-8")) / 1024))
    if unknown:
        print("未映射的函数  %d 种：" % len(set(unknown)))
        for u in sorted(set(unknown)):
            print("   ", u)

    def bluish(t):
        n = 0
        for m in _HEX_RE.finditer(t):
            r, g, b = int(m.group(1)[0:2], 16), int(m.group(1)[2:4], 16), int(m.group(1)[4:6], 16)
            h = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)[0] * 360
            if 185 <= h <= 265 and max(r, g, b) - min(r, g, b) > 8:
                n += 1
        return n

    print("残留蓝调      CSS %d 处 / 数据 %d 处" % (bluish(css), bluish(seed_txt)))

    # ---------- 具名标记自检（fail-closed） ----------
    # 历史事故：非贪婪正则让每个标记多出一个 `}`，前端 reviver 整串匹配失败 →
    # 图表 tooltip 直接显示 `{{fn:forecastTip}}` 文字、单位后面多个花括号。
    # 这里硬性卡住，避免以后重建时悄悄回退。
    opt_txt = json.dumps([c["opt"] for c in charts], ensure_ascii=False)
    opened = opt_txt.count("{{fn:")
    well = len(re.findall(r"\{\{fn:[^{}]+\}\}", opt_txt))     # 规范形态
    extra = len(re.findall(r"\{\{fn:[^{}]+\}\}\}", opt_txt))  # 标记后多一个右花括号
    print("具名标记      %d 处（规范 %d · 多花括号 %d）" % (opened, well, extra))
    # 注意：不是每份研报都有 {{fn:}} 标记（恒邦/贵研底稿的函数已内联成色值，标记数为 0），
    # 所以只校验「形式合法」，不强制存在。
    assert opened == well, \
        "{{fn:}} 标记形式不合法：出现 %d 处，其中规范 %d 处" % (opened, well)
    assert extra == 0, "标记多写了右花括号（reviver 会整串匹配失败）：%d 处" % extra

    missing = [c["id"] for c in charts if c["id"] not in "".join(x["html"] for x in mods)]
    if missing:
        print("未被任何模块引用的图表：%s" % missing)


if __name__ == "__main__":
    main()
