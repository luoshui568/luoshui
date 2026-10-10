# -*- coding: utf-8 -*-
"""把「产量储量分布及价格分析」模块改版：地图美化 + 新增中国储量分布图 + 可自由缩放。

背景（2026-09-20 第二轮）
------------------------
第一批已把该模块作为 m25 插进库（4 张图表）。用户看后提了三条：
  ① 地图「样式做好看一点」—— 原来 12 国满涂四种红，整片大陆被色块糊住；
  ② **下面再加一张中国的储量分布图**；
  ③ 两张地图都要**可自由缩放**。
所以本脚本不再做「插入 + 顺延」，而是**就地改版**：只 PATCH 600456_m25 的正文
+ 新增 1 条图表行（chartTiCNMap）。**模块编号一个字都不动。**

为什么把「插入」和「改版」写成同一个脚本
----------------------------------------
插入阶段（原 m25..m30 → m26..m31、toc 锚点重算、交叉引用单遍替换）已经执行完并在线上，
重跑那套逻辑会二次顺延、把库改坏。脚本的 SHIFT 只在**首次**执行时生效；
现在库已是 31 模块，`rest == sorted(SHIFT.keys())` 的断言必然失败 ⇒ 天然拦住误跑。
改版走 MODE=replace 分支，只认「m25 的 title 是不是目标模块」这一个判据。

用法：
  python build/add_ti_mod_600456.py          # 干跑（打印将要做的改动）
  python build/add_ti_mod_600456.py --go     # 写库
"""
import io, json, os, re, sys, time, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CODE = "600456"
NEW_NO = 25                      # 新模块插在这里（原 m25 起顺延）
SHIFT = {25: 26, 26: 27, 27: 28, 28: 29, 29: 30, 30: 31}
NEW_TITLE = "产量储量分布及价格分析"
BODY = os.path.join(HERE, "_new_m25_ti.html")
# 改版模式下要**就地替换**的模块号（不是插入、不顺延）
REPLACE_NO = 25

CFG = json.load(io.open(os.path.join(HERE, "cloud.json"), encoding="utf-8"))
BASE = "https://%s.api.tcloudbasegateway.com/v1/rdb/rest/" % CFG["envId"]
KEY = CFG["key"]
HDR = {"apikey": KEY, "Authorization": "Bearer " + KEY,
       "Content-Type": "application/json", "Accept": "application/json"}


def req(path, method="GET", body=None):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, headers=HDR, method=method)
    raw = urllib.request.urlopen(r, timeout=90).read().decode("utf-8")
    return json.loads(raw) if raw.strip() else None


def now_ms():
    return int(time.time() * 1000)


# --------------------------------------------------------------- 图表定义
MONTHS = ["2024-09", "2024-10", "2024-11", "2024-12", "2025-01", "2025-02", "2025-03",
          "2025-04", "2025-05", "2025-06", "2025-07", "2025-08", "2025-09", "2025-10",
          "2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04", "2026-05",
          "2026-06", "2026-07", "2026-08", "2026-09"]
PRICE = [1575, 1525, 1390, 1425, 1425, 1475, 1490, 1325, 1215, 1185, 1185, 1150, 1185,
         1185, 1075, 1025, 1085, 1085, 990, 990, 980, 980, 865, 825, 825]

# 2023 年钛铁矿：储量（万吨）与产量（万吨），USGS（经 iFinD 复核）
RES = [("China", "中国", 21000), ("Australia", "澳大利亚", 18000), ("India", "印度", 8500),
       ("Canada", "加拿大", 5200), ("Brazil", "巴西", 4300), ("Norway", "挪威", 3700),
       ("South Africa", "南非", 2800), ("Madagascar", "马达加斯加", 2700),
       ("Mozambique", "莫桑比克", 2200), ("Ukraine", "乌克兰", 590),
       ("United States", "美国", 200), ("Vietnam", "越南", 160)]
# 地图上不给标签的国家（面积太小，标签会溢出；数值在表里）
NOLABEL = {"Mozambique", "Madagascar", "Ukraine", "Vietnam", "United States"}
OUT = [("China", "中国", 325.0), ("Mozambique", "莫桑比克", 186.0), ("South Africa", "南非", 126.0),
       ("Australia", "澳大利亚", 40.0), ("Norway", "挪威", 36.0), ("Canada", "加拿大", 35.0),
       ("Madagascar", "马达加斯加", 30.0), ("India", "印度", 21.0), ("Vietnam", "越南", 14.0),
       ("Ukraine", "乌克兰", 13.0), ("United States", "美国", 10.0), ("Brazil", "巴西", 5.4)]
PROV = [("四川", 7535.49), ("山东", 669.26), ("湖北", 654.39), ("河北", 253.08), ("云南", 133.56),
        ("陕西", 98.62), ("广西", 79.36), ("新疆", 69.62), ("内蒙古", 48.45), ("甘肃", 5.76),
        ("河南", 4.23)]

TOTAL_RES, TOTAL_OUT = 69000.0, 884.0

# 英文名 → 中文名（tooltip 里 map data 只带英文 name，要补中文）
EN2CN = {en: cn for en, cn, _ in RES}

# 世界底图里全部国家名（217 个里除 China 外都是英文名）。
# 用途：把「无储量的国家」也塞进 map series 的 data，才能让它们响应 hover 高亮。
# ★ 运行期由 build 阶段生成的字面量注入（见 main() 里的 _worldAllNames()）。
_WORLD_ALL = []
_RES_NAMES = {en for en, _, _ in RES}


def _world_all_names():
    """从 build/lib/world-cn.js 里读出全部国家名（构建期一次性，运行时用常量）。"""
    import io as _io, json as _json, os as _os
    p = _os.path.join(HERE, "lib", "world-cn.js")
    t = _io.open(p, encoding="utf-8").read()
    i = t.find("echarts.registerMap('worldcn'")
    j = t.find("{", t.find(",", i))
    geo = _json.JSONDecoder().raw_decode(t[j:])[0]
    return sorted({f["properties"].get("name") for f in geo["features"]
                   if f["properties"].get("name")})


_WORLD_ALL = _world_all_names()


def shade(v):
    """按储量分四档取**主题红**（全球口径）—— 越红越大，比单一色更有信息量。

    ⚠️ 与 `opt_worldmap()` 里的四档必须**同源**：两处各写一套阈值，改一边忘另一边，
       就会出现「同一份数据在两张图上深浅档位对不上」的隐性错误。
       这里统一由 shade() 出，世界地图直接调它。
    ★ 阈值是**按全球口径**定的（12 国 160~21000 万吨，量级差约 130 倍），
      分省数据（4.23~7535 万吨）量级完全不同，必须走 shade_cn()，不能混用 ——
      混用会让除四川外的 10 省全部塌进最浅一档，看上去「只有四川有矿」。
    """
    if v >= 15000:
        return "#a30f24"
    if v >= 5000:
        return "#d0202f"
    if v >= 1000:
        return "#e06670"
    return "#eea3aa"


def shade_cn(v):
    """分省口径的四档主题红（四川 7535 → 河南 4.23，量级差 1700 倍）。

    阈值按**分省分布的实际断点**取，不照抄全球口径：
      第一档 四川一档独大（≥2000）；第二档 山东/湖北 第二梯队（≥500）；
      第三档 河北/云南/陕西/广西/新疆/内蒙古 中部（≥40）；
      第四档 甘肃/河南 微量（<40）。
    ⇒ 四档色与世界地图**同一套色板**，深浅语义也一致（越红越大），
      但各自在自己的量纲里分得开 —— 数据形态不同，分档就不能硬抄。
    """
    if v >= 2000:
        return "#a30f24"
    if v >= 500:
        return "#d0202f"
    if v >= 40:
        return "#e06670"
    return "#eea3aa"


def fmt_wan(v):
    """数值 + 千分位（标签里「储量 21,000 万吨」比 21000 好读）。"""
    return "{:,}".format(int(round(v)))


# ---- 世界地图：12 个有储量国家的**标注锚点**（经度, 纬度）与标签朝向 ----
# 锚点刻意**偏离国名质心**：直接压在国家中间会被标签盖住图形本身，
# 也让相邻国（如挪威/乌克兰）标签叠在一起。朝外挪一点、朝向定好，可读性最好。
# ⚠️ 2026-09-20 起改为**12 个国家全部给标签**（用户：「把储量数据的 12 个国家都显示上去」）。
#    小国用小字号 + 更贴边的锚点，免得标签互相压住；hideOverlap 再兜一层。
CHART_LABEL_POS = {
    "China": (103.0, 35.0),        "Australia": (134.0, -25.0),
    "India": (78.0, 22.0),         "Canada": (-100.0, 56.0),
    "Brazil": (-52.0, -11.0),      "Norway": (9.5, 61.5),
    "South Africa": (24.0, -29.0), "Madagascar": (47.5, -19.0),
    "Mozambique": (35.5, -18.5),   "Ukraine": (31.0, 49.0),
    "United States": (-98.0, 39.0), "Vietnam": (106.5, 16.5),
}
POS_OF = {"Canada": "top", "China": "right", "Australia": "bottom",
          "India": "left", "Brazil": "bottom", "Norway": "top",
          "South Africa": "bottom", "Madagascar": "right",
          "Mozambique": "left", "Ukraine": "top",
          "United States": "left", "Vietnam": "right"}
# 面积小、标签必须缩一号的国家（与大国同字号会互相压住）
SMALL_LABEL = {"Madagascar", "Mozambique", "Ukraine", "United States", "Vietnam"}


# ---- 中国分省储量的地理坐标（省会，用于气泡图定位）----
PROV_GEO = [
    ("四川", 104.07, 30.67, 7535.49), ("山东", 117.00, 36.65, 669.26),
    ("湖北", 114.30, 30.60, 654.39),  ("河北", 114.50, 38.05, 253.08),
    ("云南", 102.71, 25.05, 133.56),  ("陕西", 108.95, 34.27, 98.62),
    ("广西", 108.32, 22.82, 79.36),   ("新疆", 87.62, 43.82, 69.62),
    ("内蒙古", 111.65, 40.82, 48.45), ("甘肃", 103.82, 36.06, 5.76),
    ("河南", 113.65, 34.76, 4.23),
]
# 地名标注用「省名 + 储量」，但小省标签会打架 ⇒ 让 ECharts 的 hideOverlap 兜底
NOLABEL_CN = {"甘肃", "河南"}


def _cn_all_names():
    """从 build/lib/world-cn.js 里的 `registerMap('china', ...)` 读出全部省级名。

    ⚠️ 别去找 `lib/_geo_china.js` —— 那个文件不存在（2026-09-20 深夜踩过）。
       省级底图是 `make_worldmap.py` 顺手在 **world-cn.js 末尾**多注册的一份
       （它同时注册 `worldcn` 世界图 + `china` 省级图），所以来源是同一个文件。
    ★ 取法是**先定位 `'china'` 那个 registerMap**、再往下找第一个 `{`：
       不能像世界图那样找「第一个 {」，否则会读到前面的 `worldcn` 大对象。
    """
    import io as _io, json as _json, os as _os
    p = _os.path.join(HERE, "lib", "world-cn.js")
    t = _io.open(p, encoding="utf-8").read()
    i = t.find("echarts.registerMap('china'")
    if i < 0:
        raise RuntimeError("world-cn.js 里找不到 registerMap('china')，请先跑 make_worldmap.py")
    j = t.find("{", i + len("echarts.registerMap('china'"))
    geo = _json.JSONDecoder().raw_decode(t[j:])[0]
    return sorted({f["properties"].get("name") for f in geo["features"]
                   if f["properties"].get("name")})


_CN_ALL = _cn_all_names()
_CN_RES = {n for n, _, _, _ in PROV_GEO}
# 标签锚点方向（与世界地图同款 POS_OF 机制）：避免标签压住省份本身或互相重叠。
# ★ 密集区微调（2026-09-20 晚）：中部「陕西/湖北/河南」三省紧邻，若都用 right 会叠成一团。
#   按各自在省域中的方位分散：陕西→left（往西让）、湖北→right（往东让）、
#   河南→top（往上让，且本来就不显示标签）、河北→bottom（往南让开北京圈）。
POS_CN = {"四川": "right", "山东": "right", "湖北": "right", "河北": "bottom",
          "云南": "right", "陕西": "left", "广西": "bottom", "新疆": "top",
          "内蒙古": "top", "甘肃": "left", "河南": "top"}
# 面积小 / 数值小、标签必须缩一号的省
SMALL_CN = {"甘肃", "河南", "内蒙古", "新疆", "广西", "陕西"}


def opt_cnmap():
    """中国原生钛铁矿储量分布图（可缩放）。

    ── 第四次改版（2026-09-20 傍晚，用户截图4）──
    用户原话：「中国地图还是这种点点要改了，鼠标悬浮在这个有储量数据的点点上还是数据乱码，
              中国地图的样式也更世界地图显示的样式要一样」

    三项改动
    --------
    ① **点点 → 区域铺色**（与世界地图统一）：改成 `series.type = 'map'` 按**省名**上色，
       不再是 scatter 气泡。世界地图是「国家区域铺红」，中国地图就该是「省份区域铺红」——
       用户要的是**同一套视觉语言**，这里以「区域铺色」为准。
       ⚠️ 这时 `{@[2]}` 那套 scatter 取值语法彻底不需要了，tooltip 直接读标量 value。
    ② 修 tooltip 乱码：上一版走 `{{fn:mapCnTip: 万吨}}` 令牌，一旦渲染层还没部署上
       对应函数，令牌会**被 ECharts 原样画成标签文字**。这里改成 ECharts 原生
       `valueFormatter` + `formatter` 字符串——不依赖任何自定义函数，**不可能再乱码**。
    ③ 视觉对齐世界地图：同一底色 `#e6e5e2` / 白描边、同一四档主题红、同样的
       `emphasis` 浅红悬浮高亮、同样的「地图可自由缩放」。

    关于「量级差 1700 倍、区域铺色会不会塌成一色」
    --------------------------------------------
    上一版因此改用气泡。现在既然要求与世界地图统一（区域铺色），就**用分档阈值解决**：
    `shade_cn()` 的断点（≥2000 / ≥500 / ≥40 / 其余）是按分省分布实际断点定的，
    而不是照抄全球口径 ⇒ 四档各自都有人落在里面（四川 / 山东+湖北 / 六个中游省 /
    甘肃+河南），既保住了「与世界地图同一色板」的一致性，又没有塌成一色。
    """
    data = []
    for idx, (n, x, y, v) in enumerate(PROV_GEO):
        small = n in SMALL_CN
        # 与世界地图同一套美化规则（见 opt_worldmap 的 data 注释）
        top3 = idx < 3
        fs_a = 12.0 if top3 else (10.4 if small else 11.2)
        fs_b = 9.6 if top3 else (8.8 if small else 9.4)
        data.append({
            "name": n, "value": v,
            "itemStyle": {
                # 分省口径四档主题红（shade_cn）——与世界地图**同一套色板**。
                # ⚠️ 正是因为这里会出现 ≥2 种 areaColor，beauty 的 map 分支会识别出
                #   「作者在用颜色编码数据」并整段跳过归一，四档才不会被压成同色。
                "areaColor": shade_cn(v),
                "borderColor": "#ffffff", "borderWidth": 0.8,
                "shadowBlur": 6, "shadowColor": "rgba(163,15,36,.18)",
            },
            # ★★★ 标签挂在区域 data 项上（2026-09-20 深夜，与世界地图同因）：
            #    原来用 geo + scatter 锚点，缩放时 scatter 不跟 map 走 ⇒ 一放大就错位。
            #    并入 map series 的 data[].label 后由同一坐标系驱动，roam 时严丝合缝。
            "label": {
                "show": n not in NOLABEL_CN, "position": POS_CN.get(n, "right"),
                "formatter": "{d|●}{a|" + n + "}\n     {b|" + fmt_wan(v) + "}{u| 万吨}",
                "rich": {
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
                },
            },
        })
    # ★★★ 无数据省份也要能 hover 高亮 + 悬浮出提示（与世界地图同款做法）★
    # 把 `_CN_ALL` 里没储量的省也塞进 data，value=None：
    #   ECharts 不给 None 的省上色（落到 series 的浅灰 `#e6e5e2`），
    #   但会**建出对应区域元素** ⇒ emphasis 高亮与 tooltip 都生效，
    #   悬浮显示「暂无资源储量数据／本次统计未单独列示」（mapCnTip 里已兜底）。
    # ⚠️ 不加这一段，未列示省份是「死的」—— 鼠标扫过去没有高亮也没有提示，
    #   用户会以为地图坏了；世界地图早就这么做了，两张图行为要一致。
    for f in _CN_ALL:
        if f not in _CN_RES:
            data.append({
                "name": f, "value": None,
                "itemStyle": {"areaColor": "#e6e5e2"},
            })
    return {
        "backgroundColor": "transparent",
        "tooltip": {
            "trigger": "item",
            # ★★ 走 FNS.mapCnTip 函数（2026-09-20 晚第三版）：
            #    三段式「省名／原生钛铁矿（TiO₂）资源储量：7,535 万吨／占全国 78.9%」。
            #    为什么放弃 `{b}<br/>…{c}` 字符串模板：`{c}` 给的是**未格式化裸数**
            #    （7535.49 而不是 7,535），且 map 的 `{c}` 路径不吃 valueFormatter（实测）。
            #    函数里自己加千分位 + 算占全国比，一步到位。
            #    参数是**单位后缀**；函数内部做标量/数组两种 data 形态归一化。
            "formatter": "{{fn:mapCnTip: 万吨}}",
            "backgroundColor": "rgba(255,255,255,.97)",
            "borderColor": "rgba(208,32,47,.28)", "borderWidth": 1,
            "padding": [7, 10],
            "textStyle": {"fontSize": 11.5, "color": "#3a3a3f"},
            "extraCssText": "box-shadow:0 4px 14px rgba(40,38,42,.14);border-radius:7px;",
        },
        "series": [
            # ★★★ 只有一层（2026-09-20 深夜，用户：「我一放大他就错位了」）。
            #
            # 曾经的结构是「map 铺色 + geo 透明锚点 + scatter 标注层」，两个坐标系。
            # 致命点：`roam` 是 **series 级**配置，scatter 那条 series 绑的是**独立的
            # geo 组件**，它收不到 map series 的缩放/拖拽事件 ⇒ 地图在放大、标签原地不动，
            # 错位量随缩放倍数线性放大。
            #
            # 为什么不能「同步两个组件」：ECharts 只在 georoam 事件里给出变换结果，
            # 即便监听后手动 setOption 平移 geo，也要等下一帧才生效 —— 拖拽过程中每帧
            # 都会错开一点，观感是标签在「追着地图跑」。**跨坐标系做帧级同步本质上做不到。**
            #
            # 正解：标签不另起坐标系，直接写进 **map series 自己的 data[].label**
            # （见上方 data 构建处）。同一坐标系 ⇒ roam 时严丝合缝，零同步、零延迟。
            # 顺带 `geo` 组件也不需要了（它原先只为 scatter 提供坐标）。
            {"type": "map", "map": "china", "roam": True,
             "scaleLimit": {"min": 1, "max": 12},
             # ★ 版面（2026-09-20 晚微调）：中国底图包围盒很高（含九段线，纬度下探 3.4°N），
             #   在 470px 高的框里按 100% 适配 ⇒ 大陆偏小、下方大片留白。
             #   layoutSize 放大到 118% 并把 center 上移到 42%，让大陆占满上半部、
             #   九段线落在下半部 —— 两者都在框内（合规要求：九段线不可裁）。
             "layoutCenter": ["50%", "42%"], "layoutSize": "118%",
             "left": 0, "right": 0, "top": 0, "bottom": 0,
             "itemStyle": {"areaColor": "#e6e5e2", "borderColor": "#ffffff", "borderWidth": 0.7},
             "emphasis": {
                 "disabled": False,
                 "itemStyle": {"areaColor": "#f5d5d9", "borderColor": "#d0202f", "borderWidth": 1},
                 # 悬浮时把省名标签提亮成深红（与世界地图同款）
                 "label": {"show": True, "color": "#8f0d1c"},
             },
             "select": {"disabled": True},
             # 系列级默认不显示（真正的显示开关在各 data 项的 label.show 上），
             # hideOverlap 防止小省（甘肃/河南）标签叠字。
             "label": {"show": False},
             "labelLayout": {"hideOverlap": True},
             "data": data, "z": 3},
        ],
    }


def opt_worldmap():
    """全球钛铁矿储量分布（可缩放）。

    ── 第三次改版（2026-09-20 傍晚，用户给了四张截图）──
    ① 「中英文名字都悬浮显示」：气泡旁的标签从「只显示数字」改成**常驻的中文名 + 数值**，
       不再需要悬停才看得到国名。
    ② 「不要这种点点要主题红色铺满」：去掉气泡圆点，改成有储量的 12 个国家**区域整体铺主题红**
       （按储量分四档深浅，量级照样读得出来）。
    ③ 「没有储量数据的地区要悬浮高亮」+「12 个国家都显示上去」：
       全部 217 个国家都给 emphasis（hover 时浅红高亮 + 国名 tooltip）；
       12 国有数值，其余显示「暂无储量数据」。
    ④ 修 tooltip 里 `{c}` 解析不出导致的 **NaN**（map series 的 data 是
       `{name, value}` 形式，`{c}` 拿不到值 ⇒ 显式用 valueFormatter 处理）。
    """
    # ── 主图：有储量的 12 国铺主题红（四档深浅），其余国家浅灰 ──
    data = []
    for idx, (en, cn, v) in enumerate(RES):
        small = en in SMALL_LABEL
        top3 = idx < 3
        fs_a = 12.0 if top3 else (10.4 if small else 11.2)
        fs_b = 9.6 if top3 else (8.8 if small else 9.4)
        data.append({
            "name": en, "value": v,
            "itemStyle": {
                # 四档主题红，统一由 shade() 出（与分省图、占比图同源）。
                # 这四档明度 L 全部 < .78 ⇒ 渲染层 btRetint 会把它归一到主红系，
                # 正是「主题红铺满」要的效果；不用再叠 btTintKeep。
                "areaColor": shade(v),
                "borderColor": "#ffffff", "borderWidth": 0.8,
                "shadowBlur": 6, "shadowColor": "rgba(163,15,36,.18)",
            },
            # ★★★ 标签**挂在区域自身的 data 项上**（2026-09-20 深夜，用户：
            #     「我一放大他就错位了」）—— 见下方「为什么删掉原来的 scatter 标注层」。
            "label": {
                "show": en not in NOLABEL,
                "position": POS_OF.get(en, "right"),
                # 标签锚在区域几何中心，再按 position 向外挪，避免压住轮廓线。
                "offset": [0, 0],
                "formatter": "{d|●}{a|" + cn + "}\n     {b|" + fmt_wan(v) + "}{u| 万吨}",
                "rich": {
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
                },
            },
        })
    # ── 全部国家都要能 hover 高亮（含无数据的）──
    # 做法：把「无数据国家」也塞进 map series 的 data，value 给 None。
    #      ECharts 不会给 None 的国家上色（areaColor 仍取下面的浅灰），
    #      但会**建出对应的区域元素** ⇒ emphasis / tooltip 都生效。
    for f in _WORLD_ALL:
        if f not in _RES_NAMES:
            data.append({
                "name": f, "value": None,
                "itemStyle": {"areaColor": "#e6e5e2"},
            })

    # ── 标注层：标签已并入上面每个 data 项（不再单独开 scatter）──
    #
    # ★★★ 为什么删掉原来的 scatter 标注层（2026-09-20 深夜，用户：「我一放大他就错位了」）
    #
    #   旧架构：map series 负责铺色，另开一条 scatter 挂标签，坐标靠 geo 锚点换算。
    #   致命问题：**缩放只作用在 map series 上**（roam 是系列级配置），
    #   scatter 用的是**另一个 geo 组件**的坐标系，它收到不 roam 事件 ⇒
    #   放大/平移时地图动了、标签纹丝不动，越放大错位越离谱（用户截图就是这个）。
    #   有没有救？把 roam 也开给 geo 看似能同步，但两个组件各自维护 zoom/center，
    #   靠鼠标事件驱动**永远不可能逐帧严格对齐**（浮点舍入 + 事件顺序），
    #   而且 map series 与 geo 一旦各自缩放，`silent` 的 geo 还会吞掉鼠标事件。
    #
    #   ⇒ 正解：标签直接写进 **map series 的 data[].label**。
    #     map series 的标签天然挂在区域多边形上，由**同一个坐标系**驱动缩放，
    #     无论怎么 roam 都跟得死死的。这才是 ECharts 地图标注的标准做法。
    #   ⇒ 代价：标签锚点是**区域几何中心**，不像原来能按经纬度任意摆。
    #     对「一个大国一个标签」的场景完全够用；挤在一起的小国用 show=False 关掉
    #     （NOLABEL），数值仍可从 tooltip 与右侧表格取。
    #   ⇒ 同时删掉 geo 与 scatter 标注层：少一个组件，就少一层
    #     「谁跟着谁缩放」的对齐风险，也少一次绘制开销。

    # ── tooltip：**纯 ECharts 原生占位符**，不依赖任何自定义函数 ──
    # ★ 2026-09-20 傍晚第三次修（用户截图1：「悬浮显示有点乱码」）
    #   前两版都走 `{{fn:mapTip:...}}` 令牌 —— 令牌要靠渲染层 FNS 表里**同名函数**还原，
    #   一旦壳还是旧版（函数没部署上），revive 认不出就把整串令牌原样交给 ECharts，
    #   于是地图上出现一条横贯全图的 `{{fn:mapTip:China=中国|…}}` 乱码。
    #   ⇒ 改用原生 `{b}`（国名）+ 分级 valueFormatter，**不引入任何自定义函数**，
    #     任何壳版本下都不可能乱码。中文名已常驻在图上标签里，tooltip 给英文名+数值即可。
    #
    #   ⚠️ `{c}` 的 NaN 问题（用户截图3 的 Mali）：
    #     map series 的 data 是 `{name, value}` 标量形式时 `{c}` 能正常取值；
    #     无数据国家是 `value: null`，ECharts 对此渲染 `-`（不是 NaN）。
    #     再用 valueFormatter 把 null 显式换成「暂无数据」，双保险。
    return {
        "backgroundColor": "transparent",
        "tooltip": {
            "trigger": "item",
            # ★★ 走 FNS.mapTip 函数（2026-09-20 晚第三版）：文案是
            #    「中文名（English）／钛铁矿储量：21,000 万吨／占全球 30.4%」三段，
            #    带中文名翻译 + 占比。之前用 `{b}<br/>…{c}` 字符串模板有两个毛病：
            #    ① `{c}` 取到的是**未格式化**的裸数（18000 而不是 18,000），
            #       valueFormatter 在 map 的 `{c}` 路径上不生效（实测）；
            #    ② 底图 name 是英文，`{b}` 出来没有中文。
            #    函数里自己查表 + 自己加千分位，两个问题一起解决。
            "formatter": "{{fn:mapTip:" + "|".join(
                en + "=" + cn for en, cn, _ in RES) + "}}",
            "backgroundColor": "rgba(255,255,255,.97)",
            "borderColor": "rgba(208,32,47,.28)", "borderWidth": 1,
            "padding": [7, 10],
            "textStyle": {"fontSize": 11.5, "color": "#3a3a3f"},
            "extraCssText": "box-shadow:0 4px 14px rgba(40,38,42,.14);border-radius:7px;",
        },
        "series": [
            # ① 区域铺色层（**唯一的系列**，标签也挂在它自己的 data 项上）
            #    ★★★ 绝不能给 geoIndex（2026-09-20 晚，「12 国全是灰」的根因）：
            #       一旦 series.map 指向 geo（geoIndex:0），**区域填充权交给 geo**，
            #       data[].itemStyle.areaColor 被整体忽略 —— geo 的灰色会把所有国家刷平。
            #    ★★★ 也不再需要「透明 geo 锚点」（2026-09-20 深夜，「一放大就错位」）：
            #       标签已并入本系列 data[].label，天然跟同一坐标系缩放，锚点组件整个删掉。
            {"type": "map", "map": "worldcn", "roam": True,
             "scaleLimit": {"min": 1, "max": 14},
             "left": 6, "right": 6, "top": 6, "bottom": 6,
             "itemStyle": {"areaColor": "#e6e5e2", "borderColor": "#ffffff", "borderWidth": 0.6},
             "emphasis": {
                 "disabled": False,
                 "itemStyle": {"areaColor": "#f5d5d9", "borderColor": "#d0202f", "borderWidth": 1.2},
                 # 悬浮时把标签提亮一档，帮助确认「这个色块是哪个国家」
                 "label": {"show": True, "color": "#8f0d1c"},
             },
             "select": {"disabled": True},
             # 系列级 label 默认关：只有 data 项里显式 show 的才画
             "label": {"show": False},
             # ★ 防重叠：大国标签之间一般不会撞，但缩小后中美洲/东南亚会挤在一起；
             #   交给 ECharts 自动挪位，比手工调 offset 稳。
             "labelLayout": {"hideOverlap": True},
             "data": data, "z": 3},
        ],
    }


def opt_share():
    """各国储量占比 vs 产量占比（2023，%）。"""
    cats = [cn for _, cn, _ in RES]
    res_pct = [round(v / TOTAL_RES * 100, 1) for _, _, v in RES]
    out_map = {en: v for en, _, v in OUT}
    out_pct = [round(out_map.get(en, 0) / TOTAL_OUT * 100, 1) for en, _, _ in RES]
    return {
        "grid": {"left": 52, "right": 26, "top": 50, "bottom": 64},
        "legend": {"data": ["储量占全球比重", "产量占全球比重"], "top": 8,
                   "itemWidth": 14, "itemHeight": 9, "itemGap": 18, "textStyle": {"fontSize": 11.5}},
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"},
                    "valueFormatter": None},
        "xAxis": {"type": "category", "data": cats,
                  "axisLabel": {"interval": 0, "fontSize": 10.5, "rotate": 28,
                                "color": "#5c5c5c"},
                  "axisTick": {"show": False},
                  "axisLine": {"lineStyle": {"color": "#e0e0de"}}},
        "yAxis": {"type": "value", "name": "占全球比重（%）",
                  "nameTextStyle": {"fontSize": 11, "color": "#8a8a86"},
                  "axisLabel": {"fontSize": 10.5, "color": "#8a8a86", "formatter": "{value}"},
                  "splitLine": {"lineStyle": {"color": "#f3f3f1"}}},
        "series": [
            {"name": "储量占全球比重", "type": "bar", "barWidth": "30%", "barGap": "14%",
             "itemStyle": {"color": "#d0202f", "borderRadius": [3, 3, 0, 0]},
             "label": {"show": True, "position": "top", "fontSize": 9.5, "color": "#8a1620",
                       "formatter": "{c}%"},
             "data": res_pct},
            {"name": "产量占全球比重", "type": "bar", "barWidth": "30%",
             "itemStyle": {"color": "#00b0f0", "borderRadius": [3, 3, 0, 0]},
             "label": {"show": True, "position": "top", "fontSize": 9.5, "color": "#00739e",
                       "formatter": "{c}%"},
             "data": out_pct},
        ],
    }


def opt_prov():
    names = [n for n, _ in PROV]
    vals = [v for _, v in PROV]
    data = []
    for i, (n, v) in enumerate(PROV):
        c = "#b81c29" if i == 0 else ("#d0202f" if i < 3 else "#e5707a")
        data.append({"value": v, "itemStyle": {"color": c}})
    return {
        "grid": {"left": 74, "right": 96, "top": 26, "bottom": 30},
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"},
                    "formatter": "{b}<br/>储量：{c} 万吨"},
        "xAxis": {"type": "value", "name": "万吨",
                  "nameTextStyle": {"fontSize": 10.5, "color": "#8a8a86"},
                  "axisLabel": {"fontSize": 10.5, "color": "#8a8a86"},
                  "splitLine": {"lineStyle": {"color": "#f3f3f1"}}},
        "yAxis": {"type": "category", "inverse": True, "data": names,
                  "axisLabel": {"fontSize": 11.5, "color": "#4a4a48"},
                  "axisTick": {"show": False},
                  "axisLine": {"lineStyle": {"color": "#e0e0de"}}},
        "series": [{
            "type": "bar", "barWidth": "56%", "data": data,
            "itemStyle": {"borderRadius": [0, 4, 4, 0]},
            "label": {"show": True, "position": "right", "fontSize": 10, "color": "#6a6a66",
                      "formatter": "{c}"},
        }],
    }


def opt_price():
    return {
        "grid": {"left": 66, "right": 34, "top": 44, "bottom": 46},
        "tooltip": {"trigger": "axis", "valueFormatter": None},
        "xAxis": {"type": "category", "data": MONTHS, "boundaryGap": False,
                  "axisLabel": {"interval": 3, "fontSize": 10.5, "color": "#8a8a86"},
                  "axisTick": {"show": False},
                  "axisLine": {"lineStyle": {"color": "#e0e0de"}}},
        "yAxis": {"type": "value", "name": "元/吨", "min": 700, "max": 1700,
                  "nameTextStyle": {"fontSize": 10.5, "color": "#8a8a86"},
                  "axisLabel": {"fontSize": 10.5, "color": "#8a8a86"},
                  "splitLine": {"lineStyle": {"color": "#f3f3f1"}}},
        "series": [{
            "name": "攀枝花钛矿（TiO₂≥38-42%）均价", "type": "line",
            "smooth": True, "symbolSize": 5,
            "lineStyle": {"width": 2.4, "color": "#d0202f"},
            "itemStyle": {"color": "#d0202f", "borderColor": "#ffffff", "borderWidth": 1.4},
            "areaStyle": {"color": "rgba(208,32,47,.16)"},
            "data": PRICE,
            "markPoint": {"symbolSize": 46,
                          "label": {"fontSize": 10, "color": "#fff", "formatter": "{c}"},
                          "data": [{"type": "max", "name": "区间高点"},
                                   {"type": "min", "name": "区间低点"}]},
        }],
    }


CHARTS = [
    ("chartTiWorldMap", "全球钛铁矿储量分布（2023，万吨）", opt_worldmap, 24),
    ("chartTiCNMap", "中国原生钛铁矿储量分布（2022，万吨）", opt_cnmap, 25),
    ("chartTiShare", "各国储量占比 vs 产量占比（2023）", opt_share, 26),
    ("chartTiCNProv", "中国原生钛铁矿储量分省（2022，万吨）", opt_prov, 27),
    ("chartTiPrice", "攀枝花钛矿价格走势（2024-09 ~ 2026-09）", opt_price, 28),
]


# --------------------------------------------------------------- 主流程
def main():
    go = "--go" in sys.argv
    now = now_ms()
    out = []

    mods = req("wb_report_mods?code=eq.%s&select=id,no,seq,title,html&limit=500" % CODE)
    mods.sort(key=lambda m: int(m["no"]))
    rep = req("wb_reports?code=eq.%s&select=code,toc&limit=5" % CODE)[0]
    charts = req("wb_report_charts?code=eq.%s&select=id,seq,name&limit=500" % CODE)

    out.append("=== 当前：%d 个模块 / %d 张图表 / toc %d 条 ==="
               % (len(mods), len(charts), len(rep["toc"])))
    byold = {int(m["no"]): m for m in mods}
    exist = {c["id"] for c in charts}

    # ---- 模式判定（2026-09-20 第二轮新增）----
    #   本脚本原本只负责「插入 m25 + 顺延后段」。第一批已执行完并在线上，
    #   第二轮用户要的是「改版」：地图美化 + 再加一张中国储量图 + 可缩放。
    #   判据 = m25 的 title 是不是目标模块 —— 是 ⇒ 改版；不是 ⇒ 走首插。
    cur25 = byold.get(NEW_NO)
    REPLACE = bool(cur25) and (cur25.get("title") or "") == NEW_TITLE
    out.append("")
    out.append("模式：%s" % ("改版（就地替换 m25 正文 + 增图表，不动编号）" if REPLACE else "首插（插入 m25 并顺延后段）"))
    if cur25:
        out.append("  库内 m%-3d 标题 = 「%s」" % (NEW_NO, cur25.get("title")))
        out.append("  库内 m%-3d 正文 %d B" % (NEW_NO, len((cur25.get("html") or "").encode("utf-8"))))

    # ---- [核对] 目标编号的标题（2026-09-20 并错对象的教训）----
    out.append("")
    out.append("[核对] 目标位置前后的模块标题：")
    for n in (23, 24, 25, 26, 31):
        if n in byold:
            out.append("  m%-3d %s" % (n, byold[n]["title"]))

    # ---- [2] 图表
    out.append("")
    out.append("[2] 图表行（wb_report_charts）")
    plan_charts = [c for c in CHARTS if CODE + "_" + c[0] not in exist]
    for sid, name, _, seq in CHARTS:
        out.append("  %-22s seq=%-3d %s%s" % (sid, seq, name,
                   "（已存在，跳过）" if CODE + "_" + sid in exist else "  ← 待插入"))
    out.append("  待插入 %d 行" % len(plan_charts))

    # ---- [3] 新模块正文
    body_html = io.open(BODY, encoding="utf-8").read().strip()
    used = re.findall(r'data-chart="([^"]+)"', body_html)
    out.append("")
    out.append("[3] 模块 m%d「%s」正文 %d 字符，图槽 %d 个：%s"
               % (REPLACE_NO, NEW_TITLE, len(body_html), len(used), used))
    assert len(used) == len(set(used)), "图槽有重复：%s" % used
    slotset = set(used)
    chartset = set(c[0] for c in CHARTS)
    assert slotset == chartset, \
        "图槽与图表定义不一致：有槽无图 %s，有图无槽 %s" % (slotset - chartset, chartset - slotset)
    assert len(used) == len(CHARTS), "图槽数 %d ≠ 图表数 %d" % (len(used), len(CHARTS))

    # 原地替换 vs 首插
    plan_shift = []
    newtoc = rep["toc"]
    if not REPLACE:
        # 保护：SHIFT 必须正好覆盖现存所有 ≥NEW_NO 的模块 —— 少一个会撞主键
        rest = sorted(int(m["no"]) for m in mods if int(m["no"]) >= NEW_NO)
        assert rest == sorted(SHIFT.keys()), \
            "顺延映射与现存模块对不上：现存 %s，映射 %s" % (rest, sorted(SHIFT.keys()))
        out.append("")
        out.append("[3b] 模块顺延（新模块占 m%d，原 %d..%d → +1）"
                   % (NEW_NO, min(SHIFT), max(SHIFT)))
        for o, n in sorted(SHIFT.items(), reverse=True):
            if o not in byold:
                out.append("  ⚠️ m%d 不存在，跳过" % o)
                continue
            body = byold[o]["html"] or ""

            def rep_x(m, _m=SHIFT):
                k = int(m.group(2))
                return "%s%d" % (m.group(1), _m.get(k, k))
            nb = re.sub(r"(模块\s*)(\d+)", rep_x, body)
            nref = len(re.findall(r"模块\s*\d+", body))
            plan_shift.append((o, n, byold[o], nb))
            out.append("  m%-3d → m%-3d  %-24s 交叉引用 %d 处%s"
                       % (o, n, byold[o]["title"], nref,
                          "（已改写）" if nb != body else ""))
        nt = []
        for t in rep["toc"]:
            a = t["anchor"]
            mt = re.match(r"^m(\d+)$", a or "")
            na = "m%d" % SHIFT[int(mt.group(1))] if (mt and int(mt.group(1)) in SHIFT) else a
            nt.append({"text": t["text"], "anchor": na})
        newtoc = nt
        out.append("")
        out.append("[3c] toc 锚点变化：")
        for a, b in zip(rep["toc"], newtoc):
            if a["anchor"] != b["anchor"]:
                out.append("  %-8s %-10s → %s" % (a["anchor"], a["text"], b["anchor"]))
    else:
        assert len(mods) == 31, "改版模式下应当已是 31 个模块，实际 %d —— 先核对再跑" % len(mods)
        body_md5_old = cur25["html"] or ""
        out.append("")
        out.append("[3b] 就地替换：m%d %d B → %d B（%+d B）"
                   % (NEW_NO, len(body_md5_old.encode("utf-8")),
                      len(body_html.encode("utf-8")),
                      len(body_html.encode("utf-8")) - len(body_md5_old.encode("utf-8"))))
        out.append("     编号、seq、toc 全部不动")

    if not go:
        out.append("")
        out.append("（干跑结束。确认无误后加 --go 写库）")
        io.open(os.path.join(HERE, "_o_ti_plan.txt"), "w", encoding="utf-8").write("\n".join(out))
        print("\n".join(out))
        return

    # ---------------- 写库 ----------------
    ts = time.strftime("%Y%m%d-%H%M%S")
    bk = os.path.join(HERE, "backup", "%s_pre_add_ti_%s.json" % (CODE, ts))
    os.makedirs(os.path.dirname(bk), exist_ok=True)
    io.open(bk, "w", encoding="utf-8").write(json.dumps(
        {"code": CODE, "at": now, "report": rep, "mods": mods, "charts": charts},
        ensure_ascii=False))
    out.append("")
    out.append("快照 → %s（%d B）" % (os.path.basename(bk), os.path.getsize(bk)))

    # [2] 图表
    for sid, name, fn, seq in plan_charts:
        rec = {"id": CODE + "_" + sid, "report_id": CODE, "code": CODE,
               "seq": seq, "name": name, "opt": fn(), "up": now}
        try:
            req("wb_report_charts", "POST", [rec])
            out.append("  ✔ 图表已插入 %-22s %s" % (sid, name))
        except urllib.error.HTTPError as e:
            out.append("  ✖ 图表插入失败 %s：HTTP %s %s" % (sid, e.code, e.read()[:200]))
            out.append("     → 用 MCP managePgDatabase(execute) 手工 INSERT，再重跑本脚本")
            io.open(os.path.join(HERE, "_o_ti_go.txt"), "w", encoding="utf-8").write("\n".join(out))
            print("\n".join(out))
            return

    # [3] 顺延：两段式（仅首插模式）
    if not REPLACE:
        out.append("")
        out.append("[3] 顺延写库（两段式）")
        for o, n, m, _ in plan_shift:
            tmp = {"id": "%s_z%02d" % (CODE, o), "no": "z%02d" % o,
                   "seq": str(900 + o), "up": now}
            req("wb_report_mods?id=eq.%s" % m["id"], "PATCH", tmp)
        out.append("  第一段：%d 行 → 临时号" % len(plan_shift))
        for o, n, m, newbody in plan_shift:
            body = {"id": "%s_m%d" % (CODE, n), "no": str(n), "seq": str(n),
                    "html": newbody, "up": now}
            req("wb_report_mods?id=eq.%s_z%02d" % (CODE, o), "PATCH", body)
        out.append("  第二段：落终号 m26..m31（含交叉引用改写）")

    # [4] 模块正文：首插 = POST 新行；改版 = PATCH 现有行
    out.append("")
    if REPLACE:
        req("wb_report_mods?id=eq.%s_m%d" % (CODE, REPLACE_NO), "PATCH",
            {"html": body_html, "up": now})
        out.append("  ✔ 已就地替换 m%d 正文（编号未动）" % REPLACE_NO)
    else:
        nrec = {"id": "%s_m%d" % (CODE, NEW_NO), "report_id": CODE, "code": CODE,
                "no": str(NEW_NO), "seq": str(NEW_NO),
                "title": NEW_TITLE, "html": body_html, "up": now}
        req("wb_report_mods", "POST", [nrec])
        out.append("  ✔ 新模块已插入 m%d「%s」" % (NEW_NO, NEW_TITLE))
        req("wb_reports?id=eq.%s" % CODE, "PATCH", {"toc": newtoc, "up": now + 1})
        out.append("  ✔ toc 已更新（%d 条）" % len(newtoc))

    # ---- 回读复核（改版模式复核的是**逐字节**是否落地）
    time.sleep(1.2)
    if REPLACE:
        rb = req("wb_report_mods?id=eq.%s_m%d&select=html,title" % (CODE, REPLACE_NO))[0]
        import hashlib
        h_want = hashlib.md5(body_html.encode("utf-8")).hexdigest()
        h_got = hashlib.md5((rb["html"] or "").encode("utf-8")).hexdigest()
        ch2 = req("wb_report_charts?code=eq.%s&select=id&limit=500" % CODE)
        out.append("")
        out.append("=== 回读复核 ===")
        out.append("  m%d html  %d B  md5 %s" % (REPLACE_NO, len((rb["html"] or "").encode("utf-8")), h_got[:12]))
        out.append("  本地预期     %d B  md5 %s" % (len(body_html.encode("utf-8")), h_want[:12]))
        out.append("  逐字节一致  %s" % ("✅" if h_want == h_got else "❌"))
        out.append("  图表 %d 张（原 %d + %d）%s"
                   % (len(ch2), len(charts), len(plan_charts),
                      "✅" if len(ch2) == len(charts) + len(plan_charts) else "❌"))
        out.append("  m25 标题仍为「%s」%s" % (rb.get("title"),
                   "✅" if rb.get("title") == NEW_TITLE else "❌"))
    else:
        m2 = req("wb_report_mods?code=eq.%s&select=no,title&limit=500" % CODE)
        m2.sort(key=lambda x: int(x["no"]))
        ch2 = req("wb_report_charts?code=eq.%s&select=id&limit=500" % CODE)
        t2 = req("wb_reports?code=eq.%s&select=toc&limit=5" % CODE)[0]["toc"]
        nos = [int(x["no"]) for x in m2]
        out.append("")
        out.append("=== 回读复核 ===")
        out.append("  模块 %d 个，编号 %d..%d %s"
                   % (len(m2), nos[0], nos[-1],
                      "连续 ✅" if nos == list(range(1, len(nos) + 1)) else "不连续 ❌"))
        out.append("  图表 %d 张（原 %d + %d）%s" % (len(ch2), len(charts), len(plan_charts),
                   "✅" if len(ch2) == len(charts) + len(plan_charts) else "❌"))
        out.append("  toc %d 条：%s" % (len(t2), " ".join("%s=%s" % (x["anchor"], x["text"]) for x in t2)))
        out.append("  m25 = %s" % [x["title"] for x in m2 if int(x["no"]) == 25])

    io.open(os.path.join(HERE, "_o_ti_go.txt"), "w", encoding="utf-8").write("\n".join(out))
    print("\n".join(out))


if __name__ == "__main__":
    main()
