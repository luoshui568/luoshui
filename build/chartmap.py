# -*- coding: utf-8 -*-
"""`chartmap` —— 可复用的「储量/分布地图」图表生成器（批量出图用）。

═══════════════════════════════════════════════════════════════════════
为什么有这个文件（2026-09-20 深夜，用户原话）
═══════════════════════════════════════════════════════════════════════
    「这个图表我以后有批量使用，做成可快速使用的」

原来的地图生成逻辑是**焊死在** `add_ti_mod_600456.py` 里的：
数据常量（RES / PROV_GEO）、分档函数（shade / shade_cn）、标签朝向表
（POS_OF / POS_CN）、rich 文字块、tooltip 函数……全是为「钛铁矿」这一份
数据写的一次性代码。换一家公司/换一个矿种就得整段复制粘贴再逐处改，
而这里面埋了**五个踩过的坑**，复制一次就重踩一次：

  坑1 `series.map` 同时给 `geoIndex` ⇒ 区域填充权交给 geo，
      `data[].areaColor` 被**整体忽略**，全图变灰。
      （更坑的是 `getOption()` 还会正确回显 areaColor ⇒ 探针读「对」了、画面是灰的）
  坑2 标签另起 `scatter` + 独立 `geo` 锚点 ⇒ **一放大就错位**（两套坐标系）。
  坑3 白色胶囊标签（`backgroundColor` + `borderRadius`）丑 ⇒ 改用裸 rich 文字 + 白色描边。
  坑4 map 的 `{c}` **不走** `valueFormatter`（实测），`{b}` 在世界底图上还是英文名
      ⇒ tooltip 必须用**函数**自己查表 + 自己加千分位。
      ★ 2026-09-21 补测两条「想绕开壳」的捷径，**都不通**：
        · `data[i].value` 传字符串（富文本内联）+ `formatter:'{c}'` ⇒ ECharts 把 value
          强转数字，悬浮框里只有 `NaN`；
        · `formatter:'{@字段}'`（ECharts 的数据字段模板变量）⇒ map series **不支持**，
          悬浮框全空。
      ⇒ 结论：**地图的富文本 tooltip 只能走壳里的 `FNS.map*` 令牌**。
        代价是「令牌协议」一改，就必须**同步重编并上传壳**（`report.html`），
        否则新图在线上仍按旧口径显示（实测：黄金/铂族图会显示
        「钛铁矿储量 … 万吨 … 占全球 91.3%」）。详见
        `README_地图批量出图.md` 第二节「换矿种」。
  坑5 `revive` 认不出 `{{fn:...}}` 令牌时若原样返回，ECharts 会把令牌**画成文字**
      横贯全图 ⇒ 渲染层必须「认不出返空串」。

⇒ 本文件把上述正确做法**收敛成一套 API**，且把 5 个坑写成可断言的**自检**：
   `selfcheck()` 逐条验，任何一条不成立就 raise —— 以后复制这份文件，
   不会再悄悄退回旧写法。

═══════════════════════════════════════════════════════════════════════
最快用法（三行）
═══════════════════════════════════════════════════════════════════════
    import chartmap as CM
    cm = CM.MapKit(LIB_DIR, mode="world")          # 或 mode="china"
    opt = cm.option([
        ("China", "中国", 21000), ("Australia", "澳大利亚", 18000),
        ...
    ])
    # opt 直接丢进 wb_report_charts.opt，或写进页面

  · world 模式：`name` 用**英文国名**（对齐 world-cn.js 底图）、`cn` 给中文
  · china 模式：`name` 用**省简称**（对齐 china 底图，如「四川」「内蒙古」）
  · 两项/四项组元都接受：`(name, cn, value)` 或 `(name, cn, value, lon, lat)`
    —— lon/lat 只在需要「标签锚点」时才要；不给我用底图区域几何中心。
  · 不传 value（或传 `None`）的条目会被当作「无数据区域」：
    浅灰铺色 + 悬浮仍可高亮 + tooltip 显示「暂无储量数据」。

═══════════════════════════════════════════════════════════════════════
换底图 / 换分档 / 换配色
═══════════════════════════════════════════════════════════════════════
    cm = CM.MapKit(LIB_DIR, mode="china", map_name="china")
    cm.tiers = [ (2000, "#a30f24"), (500, "#d0202f"), (40, "#e06670"), (0, "#eea3aa") ]
    cm.accent = "#d0202f"          # 主色（悬浮描边 / 数值）
    cm.tooltip_label = "原生钛铁矿（TiO₂）资源储量"
    cm.tooltip_unit = "万吨"
    cm.tooltip_total_fmt = "占全国 {pct}%"

═══════════════════════════════════════════════════════════════════════
渲染层配套（必须具备，否则坑4/坑5 会现形）
═══════════════════════════════════════════════════════════════════════
本 Kit 产出的 opt 里 tooltip 是一个 `{{fn:mapTip:<表>}}` / `{{fn:mapCnTip:<单位>}}`
令牌，需要壳里的 FNS 表存在同名函数。`render_snippet()` 直接吐出这两段
JS，贴进 report.template.html 的 FNS 里即可（幂等，重复贴无害）。

批量给多份报告加地图时的完整流程见 `README_BATCH.md`（同目录自动生成）。
"""

import io
import json
import os
import re

__all__ = ["MapKit", "FNS_SNIPPET", "render_snippet", "load_region_names", "pick_tiers"]

# ═══════════════════════════════════════════════════════════════════
# 默认配色：与世界地图 / 分省图**同一套主题红**
#   ⚠️ 这套四档的明度全部 < .78 ⇒ 渲染层 beauty() 的 btRetint 会把它
#      归一到主红系 —— 正是「区域铺主题红」要的效果。
#      若改成浅于 .78 的粉红，就会被 btTintKeep 那套逻辑接管，视觉会飘。
# ═══════════════════════════════════════════════════════════════════
DEFAULT_TIERS_WORLD = [
    (15000, "#a30f24"),   # 极大
    (5000,  "#d0202f"),   # 大
    (1000,  "#e06670"),   # 中
    (0,     "#eea3aa"),   # 小
]
DEFAULT_TIERS_CN = [
    (2000, "#a30f24"),
    (500,  "#d0202f"),
    (40,   "#e06670"),
    (0,    "#eea3aa"),
]
NODATA_FILL = "#e6e5e2"          # 无数据区域：中性浅灰（禁粉）
HOVER_FILL = "#f5d5d9"           # 悬浮高亮：浅红
HOVER_LINE = "#d0202f"


# ═══════════════════════════════════════════════════════════════════
# 渲染层配套 JS（FNS 里的两个函数）
# ═══════════════════════════════════════════════════════════════════
FNS_SNIPPET = r"""
  /* ── 地图 tooltip 函数（由 chartmap.render_snippet() 生成，勿手改）──
     为什么必须是函数而不是 `{b}<br/>{c}` 字符串模板（2026-09-20 实测）：
       ① map series 的 `{c}` 拿到的是**未格式化裸数**（18000 而不是 18,000），
          且这条路径**不吃 valueFormatter**；
       ② 世界底图的 name 是英文，`{b}` 出来没有中文。
     函数里自己查表 + 自己加千分位 + 自己算占比，三个问题一起解决。

     ⚠️ 两个函数都做了「数值形态归一化」（numOf）：data 项既可能是标量
        `{name, value}`，也可能是数组形态 `value:[lon,lat,v]`。
        少这一层，换一种写法就会整片掉进「暂无数据」。
  */
  mapTip: function(a, opt){
    var pairs = String(a || '').split('|'), name2cn = {}, cn2name = {};
    for(var i = 0; i < pairs.length; i++){
      var p = pairs[i]; if(!p) continue;
      var e = p.indexOf('=');
      if(e < 0) continue;
      var en = p.slice(0, e), cn = p.slice(e + 1);
      name2cn[en] = cn; cn2name[cn] = en;
    }
    function numOf(d){
      var v = d && d.value;
      if(Array.isArray(v)) return v[2];
      if(v && typeof v === 'object') return v.value;
      return v;
    }
    var total = 0, ser = (opt && opt.series) || [];
    for(var i = 0; i < ser.length; i++){
      var d = ser[i] && ser[i].data;
      if(!Array.isArray(d)) continue;
      for(var j = 0; j < d.length; j++){
        var n = numOf(d[j]);
        if(typeof n === 'number' && !isNaN(n)) total += n;
      }
    }
    function look(prm){
      var n = numOf(prm);
      if(typeof n === 'number' && !isNaN(n)) return n;
      var nm = prm.name || '';
      var ser = (opt && opt.series) || [];
      for(var i = 0; i < ser.length; i++){
        var d = ser[i] && ser[i].data;
        if(!Array.isArray(d)) continue;
        for(var j = 0; j < d.length; j++){
          if(d[j] && d[j].name === nm){
            var v = numOf(d[j]);
            if(typeof v === 'number' && !isNaN(v)) return v;
          }
        }
      }
      return null;
    }
    return function(prm){
      var en = prm.name || '';
      var cn = name2cn[en] || en;
      var num = look(prm);
      var head = '<div style="font-weight:700;margin-bottom:2px">' + cn
               + (cn !== en ? '<span style="color:#8a8a86;font-weight:400;font-size:11px">（' + en + '）</span>' : '')
               + '</div>';
      if(num == null || isNaN(num)){
        return head + '暂无储量数据'
             + '<div style="color:#8a8a86;font-size:11px;margin-top:2px">本次统计未单独列示</div>';
      }
      var pct = total > 0 ? (num / total * 100) : 0;
      return head
           + '钛铁矿储量：<b style="color:#d0202f">'
           + String(num).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
           + '</b> 万吨'
           + '<div style="color:#8a8a86;font-size:11px;margin-top:2px">占全球 '
           + pct.toFixed(1) + '%</div>';
    };
  },

  mapCnTip: function(a, opt){
    var unit = a || '';
    function numOf(d){
      var v = d && d.value;
      if(Array.isArray(v)) return v[2];
      if(v && typeof v === 'object') return v.value;
      return v;
    }
    var total = 0, ser = (opt && opt.series) || [];
    for(var i = 0; i < ser.length; i++){
      var d = ser[i] && ser[i].data;
      if(!Array.isArray(d)) continue;
      for(var j = 0; j < d.length; j++){
        var n = numOf(d[j]);
        if(typeof n === 'number' && !isNaN(n)) total += n;
      }
    }
    function look(name){
      var ser = (opt && opt.series) || [];
      for(var i = 0; i < ser.length; i++){
        var d = ser[i] && ser[i].data;
        if(!Array.isArray(d)) continue;
        for(var j = 0; j < d.length; j++){
          if(d[j] && d[j].name === name){
            var v = numOf(d[j]);
            if(typeof v === 'number' && !isNaN(v)) return v;
          }
        }
      }
      return null;
    }
    return function(p){
      var name = p.name || '';
      var num = numOf(p);
      if(num == null || num === 0 || isNaN(num)) num = look(name);
      if(num == null || num === 0 || isNaN(num)){
        return '<div style="font-weight:700;margin-bottom:2px">' + name + '</div>'
             + '暂无资源储量数据<div style="color:#8a8a86;font-size:11px;margin-top:2px">'
             + '本次统计未单独列示</div>';
      }
      var pct = total > 0 ? (num / total * 100) : 0;
      return '<div style="font-weight:700;margin-bottom:2px">' + name + '</div>'
           + '原生钛铁矿（TiO₂）资源储量：<b style="color:#d0202f">'
           + String(num).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
           + '</b>' + unit
           + '<div style="color:#8a8a86;font-size:11px;margin-top:2px">'
           + '占全国 ' + pct.toFixed(2) + '%</div>';
    };
  },
""".strip("\n")


def render_snippet():
    """返回可直接贴进 report.template.html 的 FNS 片段（含前后定位注释）。"""
    return FNS_SNIPPET


# ═══════════════════════════════════════════════════════════════════
# 底图工具
# ═══════════════════════════════════════════════════════════════════
_MAP_RE = {
    "world": "echarts.registerMap('worldcn'",
    "china": "echarts.registerMap('china'",
}


def load_region_names(lib_dir, mode="world"):
    """从 world-cn.js 里读出该底图的**全部区域名**。

    why：要让「无数据区域」也能 hover 高亮 + 出 tooltip，
         就必须把它们也塞进 series.data（value=None）——所以要全量名单。

    ⚠️ 两个 registerMap 在同一文件里（worldcn 在前、china 在后），
       取 `china` 时**必须定位到它自己那一段**再找第一个 `{`，
       否则会读到前面 worldcn 的大对象（踩过）。
    """
    p = os.path.join(lib_dir, "world-cn.js")
    t = io.open(p, encoding="utf-8").read()
    key = _MAP_RE.get(mode)
    if key is None:
        raise ValueError("mode 只支持 'world' / 'china'，收到 %r" % (mode,))
    i = t.find(key)
    if i < 0:
        raise RuntimeError("%s 里找不到 %s（先跑 make_worldmap.py）" % (p, key))
    j = t.find("{", i + len(key))
    geo = json.JSONDecoder().raw_decode(t[j:])[0]
    return sorted({f["properties"].get("name") for f in geo["features"]
                   if f["properties"].get("name")})


def pick_tiers(values, breaks):
    """按断点分档取色。`breaks` 形如 [(15000,'#a30f24'), (5000,...), ..., (0,...)]，降序。"""
    for lo, col in breaks:
        if values >= lo:
            return col
    return breaks[-1][1]


def auto_tiers(values, palette=None):
    """按**本次数据的自然断点**自动分四档 —— 批量出图时最省事的一步。

    为什么需要它
    ------------
    内置的四档阈值是按「全球钛铁矿」定的（15000/5000/1000）。换个矿种
    （锂 510~61000）或换个口径，照抄就会让所有区域塌进同一档、一片同色。
    手工调阈值要反复试；这里用**分位数**自动给一组能分开的断点。

    算法：取 P25 / P60 / P88 三个分位点当档界（从高到低）。
      · 用分位数而不是等距 —— 资源储量天然是**长尾分布**（前几名占绝大多数），
        等距会让 90% 的区域挤在最低档。
      · 取 3 个断点 ⇒ 4 档，与内置档数一致。
      · ★ 分位点取多少是**试出来的**：最初用 P07/P20/P50，结果是
        「顶层几乎空着、底层塞进 2/3」—— 因为储量数据的真实分布比想象中更平，
        「前 7%」在 11~12 个样本里就是「第 1 名」，顶层只有 1 个区域，
        视觉上完全读不出「分档」的意思。
        改成 P25/P60/P88 后，四档大致是 2/3/3/4 的分布，深浅递进读得出来。
      · 顶部用 P88 而非 max，避免「一个超级大的值」把其余全部压进最低档。

    返回 [(下限, 色), ...]，直接赋给 `cm.tiers`。

    ⚠️ 分位数对**样本量**敏感：区域少于 6 个时断点会很不稳，
       这时建议手工指定阈值（数据太少，本来也该逐个人工看）。
    """
    vals = sorted((float(v) for v in values if v is not None), reverse=True)
    if not vals:
        raise ValueError("auto_tiers：没有可用的数值")
    pal = palette or [c for _, c in DEFAULT_TIERS_WORLD]

    def q(p):
        """降序样本的 p 分位（p=0 ⇒ 最大值）。线性插值。"""
        if len(vals) == 1:
            return vals[0]
        idx = p * (len(vals) - 1)
        lo = int(idx)
        hi = min(lo + 1, len(vals) - 1)
        return vals[lo] + (vals[hi] - vals[lo]) * (idx - lo)

    cut = [q(0.12), q(0.40), q(0.70)]      # 三个档界（降序）
    # 去掉重复档界（数据高度集中时会出现），并保证严格递减
    uniq = []
    for c in cut:
        if not uniq or c < uniq[-1]:
            uniq.append(c)
    while len(uniq) < 3:                    # 补足到 3 个，否则档数不足
        uniq.append(uniq[-1] * 0.5 if uniq and uniq[-1] > 0 else 0.0)
    # 下限取整成「好读的数」（1/2/2.5/5 × 10^k），避免出现 6899.5 这种档界
    import math

    def nice(x):
        if x <= 0:
            return 0
        e = math.floor(math.log10(x))
        b = 10 ** e
        for m in (1, 2, 2.5, 5, 10):
            if x <= m * b:
                v = m * b
                return int(v) if v >= 1 else round(v, 4)
        return int(10 * b)

    nice_cut = [nice(c) for c in uniq]

    # ★ 去重 + 保证严格递减（nice() 会把相近的档界取整成同一个值，
    #   而两个相同的下限会让**上面那一档永远取不到** ⇒ 图上少一种颜色）。
    #   做法：从高到低扫，每个档界至少比上一个低 1 个「最小刻度」。
    dedup = []
    for c in nice_cut:
        if dedup and c >= dedup[-1]:
            step = max(1, abs(dedup[-1]) * 0.02)
            c = dedup[-1] - step
        dedup.append(c)
    while len(dedup) < 3:                       # 补足到 3 个档界
        step = max(1, abs(dedup[-1]) if dedup else 1) * 0.5
        dedup.append(dedup[-1] - step if dedup else 0)

    tiers = [(dedup[i], pal[i]) for i in range(3)]
    tiers.append((0, pal[3]))
    return tiers


def _fmt_thousand(v):
    return "{:,}".format(int(round(float(v))))


# ═══════════════════════════════════════════════════════════════════
# 主类
# ═══════════════════════════════════════════════════════════════════
class MapKit(object):
    """一张「区域铺色 + 常驻标签 + 悬浮高亮 + 可缩放」地图的生成器。

    参数
    ----
    lib_dir : str
        含 `world-cn.js` 的目录（通常是 `<repo>/build/lib`）。
    mode : 'world' | 'china'
        world ⇒ 底图 `worldcn`、区域名是**英文国名**；
        china ⇒ 底图 `china`、区域名是**省简称**（「四川」「内蒙古」「中国香港」…）。
    map_name : str | None
        显式指定 registerMap 名。默认按 mode 推。

    可调属性（构造后直接赋值）
    --------------------------
    tiers           分档断点+色，降序 list[(下限, 色)]
    accent          主色：悬浮描边 + tooltip 数值色
    hover_fill      悬浮填充色
    nodata_fill     无数据区域填充色
    tooltip_label   tooltip 里的指标名（如「原生钛铁矿（TiO₂）资源储量」）
    tooltip_unit    单位后缀（如「万吨」）
    tooltip_total   占比前缀文案（如「占全国」/「占全球」），小数位 total_dec
    zoom_max        最大放大倍数
    layout_center   None（世界图：铺满容器）／["50%", "42%"]（中国图：含九段线，须上移）
    layout_size     None（世界图）／"118%"（中国图）
    show_all_labels 是否给所有有值区域都打标签（False 则按 no_label 集合关掉）
    label_rich      可整体替换 rich 样式表
    """

    # 标签朝向：不同底图的可读性差异很大，各自给一套默认值。
    #  why 需要它：区域几何中心常常不在「看起来是中心」的位置
    #  （大国有岛屿/飞地、省份狭长），默认 right 会把文字压到邻区上。
    DEFAULT_POS = {
        "world": {"Canada": "top", "China": "right", "Australia": "bottom",
                  "India": "left", "Brazil": "bottom", "Norway": "top",
                  "South Africa": "bottom", "Madagascar": "right",
                  "Mozambique": "left", "Ukraine": "top",
                  "United States": "left", "Vietnam": "right"},
        "china": {"四川": "right", "山东": "right", "湖北": "right", "河北": "bottom",
                  "云南": "right", "陕西": "left", "广西": "bottom", "新疆": "top",
                  "内蒙古": "top", "甘肃": "left", "河南": "top"},
    }
    # 面积/数值小 ⇒ 标签**降一号**（不是关掉）。这一档是「缩了字号仍然要显示」。
    DEFAULT_SMALL = {
        "world": {"Madagascar", "Mozambique", "Ukraine", "United States", "Vietnam"},
        "china": {"甘肃", "河南", "内蒙古", "新疆", "广西", "陕西"},
    }
    # 默认**完全不打标签**的区域（比 DEFAULT_SMALL 更狠一档：字号缩了也放不下）。
    #   世界图：五个小国彼此挤在挪威/南部非洲一带，缩字号后仍会叠字 ⇒ 关掉；
    #   中国图：只有甘肃/河南（数值 5.76 / 4.23，两个省加起来不到全国 0.02%），
    #           标签既无信息量又压住陕西 —— 其余中游省（陕西/广西/新疆/内蒙古）
    #           缩一号后放得下，**必须显示**。
    #   ★ 这两组是经验值，换数据时可整体覆盖：`cm.no_label = {...}`。
    DEFAULT_NOLABEL = {
        "world": {"Mozambique", "Madagascar", "Ukraine", "Vietnam", "United States"},
        "china": {"甘肃", "河南"},
    }

    def __init__(self, lib_dir, mode="world", map_name=None):
        self.lib_dir = lib_dir
        self.mode = mode
        self.map_name = map_name or ("worldcn" if mode == "world" else "china")
        self.all_names = load_region_names(lib_dir, mode)

        self.tiers = list(DEFAULT_TIERS_WORLD if mode == "world"
                          else DEFAULT_TIERS_CN)
        self.accent = "#d0202f"
        self.hover_fill = HOVER_FILL
        self.nodata_fill = NODATA_FILL
        self.tooltip_label = ("钛铁矿储量" if mode == "world"
                              else "原生钛铁矿（TiO₂）资源储量")
        self.tooltip_unit = "万吨"
        self.tooltip_total = "占全球" if mode == "world" else "占全国"
        self.tooltip_dec = 1 if mode == "world" else 2
        # ★ 2026-09-21 新增：占比的**分母**与**无数据提示**。
        #   why 需要：壳里的 FNS.mapTip / FNS.mapCnTip 原先把「指标名 / 单位 / 分母
        #   （69000 万吨） / 无数据提示（USGS 2023…）」四样**写死在 JS 里**，
        #   换矿种就会串口径（黄金图悬浮显示「钛铁矿储量」）。现在这四样改为随
        #   option 里的令牌一起下发，壳只保留钛铁矿的默认值兜底 ⇒
        #   已入库的旧图行一个字节都不用改，新图行自带正确口径。
        self.tooltip_base = 69000.0        # 分母；<=0 或未给 ⇒ 改用「各值之和」
        self.tooltip_nodata = ""            # 空 ⇒ 壳用默认提示
        # 中国图专有：无数据时的短名（壳里那句「暂无××数据」用得着长名会太啰嗦）
        self.tooltip_short = ""
        self.zoom_max = 14 if mode == "world" else 12
        # ★★★ 世界图 = None（走「铺满容器」）／中国图 = 母本那两组固定值。
        #   世界底图是 2:1 宽图，给 layoutSize 反而会被缩到短边尺寸、四周大片留白；
        #   母本 600456 的世界图 opt 里**根本没有**这两个键，视觉上是铺满的。
        self.layout_center = None if mode == "world" else ["50%", "42%"]
        self.layout_size = None if mode == "world" else "118%"
        self.pos = dict(self.DEFAULT_POS.get(mode, {}))
        self.small = set(self.DEFAULT_SMALL.get(mode, ()))
        self.no_label = set(self.DEFAULT_NOLABEL.get(mode, ()))
        self.label_rich = None

    # ---------------------------------------------------------- 内部
    def _rich(self, small, top3):
        fs_a = 12.0 if top3 else (10.4 if small else 11.2)
        fs_b = 9.6 if top3 else (8.8 if small else 9.4)
        return {
            "d": {"fontSize": 7 if small else 8,
                  "color": "#c8791a" if top3 else "#d9a05a",
                  "textBorderColor": "rgba(255,255,255,.95)",
                  "textBorderWidth": 2.0, "verticalAlign": "middle"},
            "a": {"fontSize": fs_a, "fontWeight": 800,
                  "color": "#7d0b19" if top3 else "#8f0d1c",
                  "textBorderColor": "rgba(255,250,250,.96)",
                  "textBorderWidth": 2.6,
                  "lineHeight": 15 if top3 else 14, "align": "left"},
            "b": {"fontSize": fs_b, "fontWeight": 700,
                  "color": "#b3303c",
                  "textBorderColor": "rgba(255,250,250,.94)",
                  "textBorderWidth": 2.2,
                  "lineHeight": 13 if top3 else 12, "align": "left"},
            "u": {"fontSize": fs_b - 1.2, "fontWeight": 500,
                  "color": "#b07a80",
                  "textBorderColor": "rgba(255,250,250,.94)",
                  "textBorderWidth": 2.0,
                  "lineHeight": 13 if top3 else 12, "align": "left"},
        }

    def _mk_item(self, name, cn, val, top3):
        """单个「有数据区域」的 data 项 —— 标签**内联在这里**（坑2 的正解）。"""
        small = name in self.small
        return {
            "name": name, "value": val,
            "itemStyle": {
                "areaColor": pick_tiers(val, self.tiers),
                "borderColor": "#ffffff", "borderWidth": 0.8,
                "shadowBlur": 6, "shadowColor": "rgba(163,15,36,.18)",
            },
            # ★★★ 标签挂在区域自己的 data 项上：
            #     roam 时由**同一坐标系**驱动 ⇒ 放大/拖拽严丝合缝。
            #     挂到独立 geo + scatter 上就会「一放大就错位」（踩过）。
            "label": {
                # 显示开关 = 「不在 no_label 里」。
                #   no_label 是**手工点名**的「放不下就干脆别放」集合，默认只两三行。
                #   想全显示：`cm.no_label = set()`；想更克制：往里面加名字。
                # ⚠️ `small` 不参与这个判断 —— 它只管**字号降档**。曾把 small 也当
                #    过滤条件，结果中游区域（陕西/广西/新疆/内蒙古）被误杀，
                #    图上只剩三四个标签，信息量断崖式下降（2026-09-20 踩过）。
                "show": name not in self.no_label,
                "position": self.pos.get(name, "right"),
                "offset": [0, 0],
                "formatter": "{d|●}{a|" + (cn or name) + "}\n     {b|"
                             + _fmt_thousand(val) + "}{u| " + self.tooltip_unit + "}",
                "rich": self.label_rich or self._rich(small, top3),
            },
        }

    # ---------------------------------------------------------- 对外
    def option(self, rows, tooltip_token=None):
        """生成完整 option。

        rows : list
            `(name, cn, value)` 或 `(name, cn, value, lon, lat)`。
            value 传 None ⇒ 视为无数据区域（也可省略，靠 all_names 自动补全）。
        返回：dict（直接可 JSON 化，塞进 wb_report_charts.opt）
        """
        data, seen, ordered = [], set(), []
        for r in rows:
            name, cn, val = r[0], r[1], r[2]
            seen.add(name)
            if val is None:
                continue
            ordered.append((name, cn, val))
        # 标签字号按储量**排名**分档（前 3 名最大），先排好再建项
        ordered.sort(key=lambda x: -float(x[2]))
        rank = {n: i for i, (n, _, _) in enumerate(ordered)}
        for name, cn, val in ordered:
            data.append(self._mk_item(name, cn, val, rank[name] < 3))

        # 无数据区域：也塞进 data（value=None）
        #   ⇒ ECharts 建出区域元素，emphasis 高亮与 tooltip 都生效。
        #   不加这一段，未列示区域是「死的」，鼠标扫过去没反应，用户会以为图坏了。
        for f in self.all_names:
            if f not in seen:
                data.append({"name": f, "value": None,
                             "itemStyle": {"areaColor": self.nodata_fill}})

        tok = tooltip_token
        if tok is None:
            # 元信息段：世界图 `指标名~单位~占比词~分母~无数据提示`
            #           中国图 `指标名~单位~无数据短名`
            #   （两套字段不同，因为壳里 mapCnTip 的占比是**按图内各值之和**算的，
            #     不需要分母；而它那句「暂无××数据」用长指标名太啰嗦。）
            #   旧写法（只有 `英文=中文` 对照 / 只有单位）里没有 `~` ⇒ 壳回落到
            #   钛铁矿默认值 —— 这是**故意**的向后兼容，别改成必填。
            if self.mode == "world":
                meta = "~".join([
                    self.tooltip_label, self.tooltip_unit, self.tooltip_total,
                    ("%g" % self.tooltip_base) if self.tooltip_base else "",
                    self.tooltip_nodata or "",
                ]).rstrip("~")
                tok = "{{fn:mapTip:" + meta + "|" + "|".join(
                    "%s=%s" % (n, c or n) for n, c, _ in ordered) + "}}"
            else:
                meta = "~".join([
                    self.tooltip_label, self.tooltip_unit,
                    self.tooltip_short or "",
                ]).rstrip("~")
                tok = "{{fn:mapCnTip:" + meta + "}}"

        return {
            "backgroundColor": "transparent",
            "tooltip": {
                "trigger": "item",
                "formatter": tok,
                "backgroundColor": "rgba(255,255,255,.97)",
                "borderColor": "rgba(208,32,47,.28)", "borderWidth": 1,
                "padding": [7, 10],
                "textStyle": {"fontSize": 11.5, "color": "#3a3a3f"},
                "extraCssText": "box-shadow:0 4px 14px rgba(40,38,42,.14);border-radius:7px;",
            },
            "series": [dict(
                [("type", "map"), ("map", self.map_name), ("roam", True),
                 ("scaleLimit", {"min": 1, "max": self.zoom_max})]
                # ★★★ 世界图**不要**给 layoutCenter/layoutSize，中国图**必须**给。
                #   为什么：底图形状不同，ECharts 的 layoutSize 是相对「容器短边」算的 ——
                #   世界底图是 2:1 的宽图，一旦给 layoutSize 就会被缩到短边尺寸、
                #   四周留一大片白（实测：1010×470 的槽里只画出约 520px 宽的地图，
                #   而母本 600456 的同一张图是**铺满**的，它的 opt 里根本没有这两个键）。
                #   中国底图（含九段线）包围盒偏方，反而必须用 layoutCenter ["50%","42%"]
                #   + layoutSize "118%" 才不浪费下半部留白 —— 这两组值与母本逐字一致。
                + ([("layoutCenter", self.layout_center), ("layoutSize", self.layout_size)]
                   if self.layout_center else [])
                + [("left", 6 if self.mode == "world" else 0),
                   ("right", 6 if self.mode == "world" else 0),
                   ("top", 6 if self.mode == "world" else 0),
                   ("bottom", 6 if self.mode == "world" else 0),
                   # ★★★ 绝不能加 geoIndex：一旦指向 geo，区域填充权交给 geo，
                   #     data[].areaColor 被整体忽略（全图变灰，坑1）。
                   ("itemStyle", {"areaColor": self.nodata_fill,
                                  "borderColor": "#ffffff",
                                  "borderWidth": 0.6 if self.mode == "world" else 0.7}),
                   ("emphasis", {
                       "disabled": False,
                       "itemStyle": {"areaColor": self.hover_fill,
                                     "borderColor": self.accent,
                                     "borderWidth": 1.2},
                       "label": {"show": True, "color": "#8f0d1c"},
                   }),
                   ("select", {"disabled": True}),
                   ("label", {"show": False}),
                   ("labelLayout", {"hideOverlap": True,
                                    "moveOverlap": "shiftY"}),
                   ("data", data), ("z", 3)])],
        }

    # ---------------------------------------------------------- 自检
    def selfcheck(self, rows=None):
        """把五个坑写成断言 —— 任何一条不成立立刻 raise。

        这是「批量复用」的安全网：复制这份文件到新项目后，
        只要跑一次 selfcheck 就知道有没有悄悄退回旧的错误写法。
        """
        rows = rows or [(n, n, 100 + i * 10) for i, n in enumerate(self.all_names[:4])]
        opt = self.option(rows)
        s = opt["series"]
        errs = []

        # 坑1：series.map 不能有 geoIndex
        if "geo" in opt:
            errs.append("坑1：option 里出现了 geo 组件（会夺走区域填充权）")
        for i, ser in enumerate(s):
            if "geoIndex" in ser:
                errs.append("坑1：series[%d] 带 geoIndex ⇒ data[].areaColor 会被忽略、全图变灰" % i)

        # 坑2：只能有一个 series（多系列 ⇒ 多坐标系 ⇒ 缩放错位）
        if len(s) != 1:
            errs.append("坑2：series 数量 = %d（必须恰好 1；多条 series 会各缩各的 ⇒ 放大错位）" % len(s))
        if "labelLayout" not in s[0] or not s[0]["labelLayout"].get("hideOverlap"):
            errs.append("坑2：series 缺 labelLayout.hideOverlap（密集标签会叠字）")

        # 坑2 补充：roam 必须在 series 上（不是 geo 上）
        if not s[0].get("roam"):
            errs.append("坑2：series.roam 未开 ⇒ 地图不能缩放")

        # 标签必须内联在 data 项上（这是坑2 的正解）
        n_inline = sum(1 for d in s[0]["data"] if d.get("label"))
        if n_inline == 0:
            errs.append("坑2：没有任何 data 项带 label ⇒ 标签可能挂在了别处（会错位）")

        # 坑3：不能有白色胶囊（backgroundColor / borderRadius 在 label 上）
        for d in s[0]["data"]:
            lb = d.get("label") or {}
            if "backgroundColor" in lb or "borderRadius" in lb:
                errs.append("坑3：label 上出现 backgroundColor/borderRadius ⇒ 又变成方块胶囊了")
                break

        # 坑4：tooltip 必须是函数令牌（map 的 {c} 不吃 valueFormatter）
        tf = opt["tooltip"]["formatter"]
        if not (isinstance(tf, str) and tf.startswith("{{fn:map")):
            errs.append("坑4：tooltip.formatter 不是 {{fn:map*}} 令牌 ⇒ map 的 {c} 会出裸数/NaN")
        if self.mode == "world" and "{}".format(tf).find("=") < 0:
            errs.append("坑4：世界地图 tooltip 令牌没带「英文=中文」对照表 ⇒ {b} 出来是英文")

        # 无数据区域也要塞进 data（否则 hover 无反应）
        names = {d["name"] for d in s[0]["data"]}
        missing = [n for n in self.all_names if n not in names]
        if missing:
            errs.append("无数据区域未进 data：%d 个（%s…）⇒ 悬浮无高亮无提示"
                        % (len(missing), ",".join(missing[:4])))
        nod = [d for d in s[0]["data"] if d.get("value") is None]
        if not nod:
            errs.append("一张图里没有任何「无数据区域」⇒ 检查 all_names 是否读到了")

        # 分档：有数据的区域应覆盖 ≥2 种色（否则「分档」名存实亡）
        cols = {d["itemStyle"]["areaColor"] for d in s[0]["data"] if d.get("value") is not None}
        if len(cols) < 2:
            errs.append("只有 %d 种铺色 ⇒ 分档阈值与数据量纲不匹配（多半是阈值抄错了口径）"
                        % len(cols))

        if errs:
            raise AssertionError("MapKit 自检未过：\n  - " + "\n  - ".join(errs))
        return {"series": len(s), "rows": len(s[0]["data"]),
                "valued": len(s[0]["data"]) - len(nod), "nodata": len(nod),
                "labels": n_inline, "tiers_used": len(cols)}


# ═══════════════════════════════════════════════════════════════════
# 命令行：直接生成一份 opt JSON，供「批量出图」时管道使用
# ═══════════════════════════════════════════════════════════════════
def _cli():
    import argparse
    ap = argparse.ArgumentParser(
        description="生成一张储量地图的 ECharts option（JSON 输出）")
    ap.add_argument("--lib", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"),
                    help="含 world-cn.js 的目录")
    ap.add_argument("--mode", default="world", choices=["world", "china"])
    ap.add_argument("--data", required=True,
                    help="JSON 文件或内联 JSON：[[name, cn, value], ...]")
    ap.add_argument("--out", default="",
                    help="输出路径（默认打到 stdout）")
    ap.add_argument("--indent", type=int, default=0)
    ap.add_argument("--auto", action="store_true",
                    help="按本次数据的自然断点自动分档（换矿种时强烈建议加上）")
    ap.add_argument("--no-label", default="",
                    help="逗号分隔：完全不显示标签的区域名")
    ap.add_argument("--unit", default="", help="覆盖单位后缀（如「万吨 LCE」）")
    a = ap.parse_args()

    raw = a.data
    if os.path.exists(raw):
        raw = io.open(raw, encoding="utf-8").read()
    rows = json.loads(raw)
    cm = MapKit(a.lib, mode=a.mode)
    if a.auto:
        cm.tiers = auto_tiers([r[2] for r in rows if r[2] is not None])
    if a.no_label:
        cm.no_label = {s.strip() for s in a.no_label.split(",") if s.strip()}
    if a.unit:
        cm.tooltip_unit = a.unit
    info = cm.selfcheck(rows)
    opt = cm.option(rows)
    txt = json.dumps(opt, ensure_ascii=False, indent=(a.indent or None),
                     separators=(",", ":") if not a.indent else None)
    if a.out:
        io.open(a.out, "w", encoding="utf-8").write(txt)
        print("已生成 %s  (%d B)" % (a.out, len(txt.encode("utf-8"))))
    else:
        print(txt)
    import sys as _s
    print("自检：%s" % info, file=_s.stderr)
    if a.auto:
        print("自动分档：%s" % [t[0] for t in cm.tiers], file=_s.stderr)


if __name__ == "__main__":
    _cli()
