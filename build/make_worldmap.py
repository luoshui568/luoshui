# -*- coding: utf-8 -*-
"""生成研报用的**合规世界地图**数据（离线、单文件内联）。

为什么需要这个脚本
------------------
ECharts 官方 world 地图（Natural Earth 1:110m）在**中国领土画法上不符合国家标准**：
  ✗ 台湾未并入中国版图（是空白/异色块，且没有独立可识别的 name）；
  ✗ 藏南（阿鲁纳恰尔）被划给印度；
  ✗ 南海诸岛与九段线缺失。
研报里出现这种地图是不可接受的，所以这里做一次「修补」：

  1. 把 ECharts 的压缩世界地图（UTF8Encoding）**解码**成明文 GeoJSON；
  2. 对每个 feature 做 RDP 简化 + 坐标降精度（显示用，无损观感）；
  3. 用**国家标准数据**（阿里 DataV areas_v3 / 100000_full，含 34 省级 + 台湾省 +
     香港 + 澳门 + 九段线）重建 `China` 这一个 feature —— 把 35 个省级面片合并进
     同一个 MultiPolygon（同色无边界 ⇒ 视觉上就是一个完整的中国）；
  4. 追加「南海诸岛九段线」feature；
  5. 把 `China` 挪到 features **末尾**（最后绘制 ⇒ 压住印度在藏南的着色）。

输出 `build/lib/world-cn.js`：一行 `echarts.registerMap('worldcn', {...})`，
由 build.py 注入 report.template.html 的 /*__WORLDMAP__*/ 占位符。

⚠️ 数据源不可随意更换：换掉 DataV 那份就等于放弃合规性。
⚠️ 九段线必须画 —— 它在这个 feature 里叫 adchar='JD' / adcode='100000_JD'。

用法： python build/make_worldmap.py
"""
import io, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_WORLD = os.path.join(HERE, "_dl", "world.js")          # ECharts 4.9 world（压缩）
SRC_CN = os.path.join(HERE, "_dl", "datav_cn_full.json")   # 国家标准中国（明文）
DST = os.path.join(HERE, "lib", "world-cn.js")

EPS_WORLD = 0.18    # 世界其余国家简化容差（度）≈ 20km —— 全球视角看不出
EPS_CN = 0.03       # 中国简化容差（度）≈ 3km —— 中国是主角，保形优先
NDIGIT = 2          # 坐标保留小数位（0.01° ≈ 1.1km，远超 1060px 宽的显示需要）

# DataV 用**全称**，业务数据用**简称** ⇒ 建一份映射再注册省级地图。
# ⚠️ 台湾/香港/澳门保留全称是不行的：ECharts 的 name 是数据挂载主键，
#    业务侧写「台湾」就挂不上 —— 所以这里统一成本表里的简称。
CN_SHORT = {
    "北京市": "北京", "天津市": "天津", "河北省": "河北", "山西省": "山西",
    "内蒙古自治区": "内蒙古", "辽宁省": "辽宁", "吉林省": "吉林", "黑龙江省": "黑龙江",
    "上海市": "上海", "江苏省": "江苏", "浙江省": "浙江", "安徽省": "安徽",
    "福建省": "福建", "江西省": "江西", "山东省": "山东", "河南省": "河南",
    "湖北省": "湖北", "湖南省": "湖南", "广东省": "广东", "广西壮族自治区": "广西",
    "海南省": "海南", "重庆市": "重庆", "四川省": "四川", "贵州省": "贵州",
    "云南省": "云南", "西藏自治区": "西藏", "陕西省": "陕西", "甘肃省": "甘肃",
    "青海省": "青海", "宁夏回族自治区": "宁夏", "新疆维吾尔自治区": "新疆",
    "台湾省": "台湾", "香港特别行政区": "中国香港", "澳门特别行政区": "中国澳门",
}


# ---------------------------------------------------------------- 读 + 解码
def load_world_json():
    """从 world.js 里抠出 registerMap 的那个 GeoJSON 对象（括号配平，不靠正则）。"""
    s = io.open(SRC_WORLD, encoding="utf-8").read()
    i = s.find('"type":"FeatureCollection"')
    if i < 0:
        sys.exit("world.js 里找不到 FeatureCollection")
    j = s.rfind("{", 0, i)
    depth, k, instr, esc = 0, j, False, False
    while k < len(s):
        c = s[k]
        if instr:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                instr = False
        else:
            if c == '"':
                instr = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    break
        k += 1
    return json.loads(s[j:k + 1])


def decode_polygon(coords, offsets, scale):
    """复刻 ECharts 的 decodePolygon：zigzag 差分 + 偏移还原。

    JS 原式： x = (x >> 1) ^ -(x & 1);  x += prevX;
    Python 的 >> 对非负有同样语义，^ -1 同样等于 ~x，所以逐位对齐。
    """
    out = []
    px, py = offsets[0], offsets[1]
    for i in range(0, len(coords), 2):
        x = ord(coords[i]) - 64
        y = ord(coords[i + 1]) - 64
        x = (x >> 1) ^ (-(x & 1))
        y = (y >> 1) ^ (-(y & 1))
        x += px
        y += py
        px, py = x, y
        out.append([x / scale, y / scale])
    return out


def decode_geojson(gj):
    """把 UTF8Encoding 压缩坐标解成明文。"""
    scale = gj.get("UTF8Scale") or 1024
    if not gj.get("UTF8Encoding"):
        return gj
    for f in gj["features"]:
        g = f["geometry"]
        co = g["coordinates"]
        offs = g.get("encodeOffsets")
        if offs is None:
            continue                      # 已经明文的 feature，别重复解
        # ⚠️ 压缩态的坐标是**字符串**：Polygon 是 [环串]，MultiPolygon 是 [[环串]]，
        #    每个环串对应 encodeOffsets 里的一组起点。逐个字符串解码。
        if g["type"] == "Polygon":
            g["coordinates"] = [decode_polygon(co[c], offs[c], scale)
                                for c in range(len(co))]
        elif g["type"] == "MultiPolygon":
            for c in range(len(co)):
                for c2 in range(len(co[c])):
                    co[c][c2] = decode_polygon(co[c][c2], offs[c][c2], scale)
        g.pop("encodeOffsets", None)
    gj["UTF8Encoding"] = False
    return gj


# ---------------------------------------------------------------- 简化
def _seg_dist(p, a, b):
    """点到线段的距离（平面近似；纬度跨度大时误差可忽略，仅用于挑冗余点）。"""
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
    t = ((px - ax) * dx + (py - ay) * dy) / float(dx * dx + dy * dy)
    t = 0.0 if t < 0 else (1.0 if t > 1 else t)
    cx, cy = ax + t * dx, ay + t * dy
    return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5


def rdp(pts, eps):
    """Ramer–Douglas–Peucker，迭代实现（世界地图里有上万点的环，递归会爆栈）。"""
    n = len(pts)
    if n < 3:
        return pts
    keep = [False] * n
    keep[0] = keep[n - 1] = True
    stack = [(0, n - 1)]
    while stack:
        s, e = stack.pop()
        if e <= s + 1:
            continue
        dmax, idx = 0.0, -1
        for i in range(s + 1, e):
            d = _seg_dist(pts[i], pts[s], pts[e])
            if d > dmax:
                dmax, idx = d, i
        if dmax > eps and idx > 0:
            keep[idx] = True
            stack.append((s, idx))
            stack.append((idx, e))
    return [p for i, p in enumerate(pts) if keep[i]]


def simp_ring(ring, eps):
    """闭合环要拆成两段简化 —— 首尾同点时单段 RDP 会把整个环压成一条线。"""
    if len(ring) < 5:
        return ring
    closed = ring[0] == ring[-1]
    if not closed:
        return rdp(ring, eps)
    a = rdp(ring[:len(ring) // 2 + 1], eps)
    b = rdp(ring[len(ring) // 2:], eps)
    out = a[:-1] + b
    if out[0] != out[-1]:
        out.append(out[0])
    return out


def simp_geom(g, eps):
    def ring(r):
        r = simp_ring(r, eps)
        return [[round(x, NDIGIT), round(y, NDIGIT)] for x, y in r]
    if g["type"] == "Polygon":
        g["coordinates"] = [ring(r) for r in g["coordinates"]]
    elif g["type"] == "MultiPolygon":
        g["coordinates"] = [[ring(r) for r in poly] for poly in g["coordinates"]]
    return g


def count_pts(g):
    n = 0
    def walk(x):
        nonlocal n
        if isinstance(x, list):
            if x and isinstance(x[0], (int, float)):
                n += 1
            else:
                for y in x:
                    walk(y)
    walk(g["coordinates"])
    return n


# ---------------------------------------------------------------- 主流程
def main():
    if not os.path.exists(SRC_WORLD):        sys.exit("缺少 %s —— 先跑一次下载（见文件头注释）" % SRC_WORLD)
    if not os.path.exists(SRC_CN):
        sys.exit("缺少 %s —— 国家标准中国地图数据，不能省" % SRC_CN)

    world = decode_geojson(load_world_json())
    print("世界地图：%d 个 feature（已解码）" % len(world["features"]))

    cn = json.load(io.open(SRC_CN, encoding="utf-8"))
    prov, nineline = [], None
    for f in cn["features"]:
        nm = f["properties"].get("name")
        if f["properties"].get("adchar") == "JD":
            nineline = f
        elif nm:
            prov.append(f)
    print("国标中国：%d 个省级面片" % len(prov))
    if nineline is None:
        sys.exit("国标数据里找不到九段线（adchar='JD'）—— 缺它不合规")
    b = count_pts(nineline["geometry"])
    print("九段线：1 个 feature，%d 点" % b)

    # ---- 1) 简化世界其余国家，并把原 China 先摘出来
    feats, dropped_china = [], 0
    for f in world["features"]:
        nm = f["properties"].get("name") or ""
        if nm == "China":
            dropped_china += 1
            continue
        # 南极洲没人看，压狠一点
        eps = 0.8 if nm == "Antarctica" else EPS_WORLD
        f["geometry"] = simp_geom(f["geometry"], eps)
        feats.append({"type": "Feature",
                      "properties": {"name": nm or "UNKNOWN"},
                      "geometry": f["geometry"]})
    print("原 China feature 已摘除：%d 个" % dropped_china)
    if dropped_china != 1:
        print("  ⚠️ 预期恰好 1 个，实际 %d —— 先确认再继续" % dropped_china)

    # ---- 2) 用国标面片重建 China
    #      ⚠️ 直接把这 35 个面片堆进一个 MultiPolygon 是不行的：各省边界被**独立**简化
    #         之后会互相错开，红底上会浮出一层细白网（2026-09-20 实测）。所以走 shapely
    #         的 unary_union —— 省界被真正消掉，只剩一条外轮廓，顺带体积也更小。
    from shapely.geometry import shape, mapping
    from shapely.ops import unary_union
    from shapely.validation import make_valid

    geoms = []
    for f in prov:
        geoms.append(make_valid(shape(f["geometry"])))
    if nineline is not None:
        geoms.append(make_valid(shape(nineline["geometry"])))
    print("待合并面片：%d 个" % len(geoms))

    u = unary_union(geoms)
    # 保留拓扑的简化：不会让小岛自交、不会把台湾那样的碎岛抹平
    u = u.simplify(EPS_CN, preserve_topology=True)
    print("合并后：%s" % u.geom_type)

    mpg = mapping(u)
    def clean(geom):
        co = geom["coordinates"]
        def r(rr):
            return [[round(x, NDIGIT), round(y, NDIGIT)] for x, y in rr]
        if geom["type"] == "Polygon":
            return {"type": "Polygon", "coordinates": [r(x) for x in co]}
        return {"type": "MultiPolygon",
                "coordinates": [[r(x) for x in poly] for poly in co]}
    cng = clean(mpg)
    feats.append({"type": "Feature",
                  "properties": {"name": "China", "cp": [104.0, 35.0]},
                  "geometry": cng})
    chn = count_pts(cng)
    npoly = len(cng["coordinates"]) if cng["type"] == "MultiPolygon" else 1
    print("国标中国重建：%d 个多边形 / %d 点（含台湾、藏南、南海诸岛九段线）" % (npoly, chn))

    gj = {"type": "FeatureCollection", "features": feats}

    # 体积体检
    txt = json.dumps(gj, ensure_ascii=False, separators=(",", ":"))
    print("明文体积：%.1f KB（%d 个 feature）" % (len(txt) / 1024.0, len(feats)))
    if len(txt) > 420 * 1024:
        print("  ⚠️ 偏大，考虑调大 EPS_WORLD 或 NDIGIT")

    os.makedirs(os.path.dirname(DST), exist_ok=True)
    head = ("/* 合规世界地图（build/make_worldmap.py 生成，勿手改）\n"
            "   ECharts 官方 world 数据的中国画法不合国标（缺台湾、藏南归印度、无九段线），\n"
            "   这里已用国家标准数据（DataV 100000_full：34 省级 + 台湾省 + 香港 + 澳门 + 九段线）\n"
            "   重建 China feature，并挪到 features 末尾（最后绘制，压住印度在藏南的着色）。\n"
            "   同文件末尾另注册了 'china'（省级，供中国分省/气泡图使用）。 */\n")
    parts = [head, "echarts.registerMap('worldcn'," + txt + ");\n"]

    # ---- 3) 另注册一份**省级**中国地图（供分省图 / 气泡图用）----
    #  ⚠️ 三处必须处理，否则数据挂不上：
    #    ① 名称：DataV 用全称（「四川省」「内蒙古自治区」），业务数据用简称 ⇒ 归一化；
    #    ② 台湾/香港/澳门 保留全称 —— 简称会把「香港特别行政区」截成「香港」，
    #       而这在语义上没问题，但统一走 CN_SHORT 更好读；
    #    ③ 九段线也并进来：省级图同样要看南海，缺它不合规。
    prov_feats = []
    for f in prov:
        nm = f["properties"].get("name") or ""
        short = CN_SHORT.get(nm, nm)
        g = simp_geom(f["geometry"], EPS_CN)
        prov_feats.append({"type": "Feature",
                           "properties": {"name": short, "fullname": nm,
                                          "adcode": f["properties"].get("adcode")},
                           "geometry": g})
    prov_feats.append({"type": "Feature",
                       "properties": {"name": "南海诸岛", "fullname": "南海诸岛",
                                      "adcode": "100000_JD"},
                       "geometry": simp_geom(nineline["geometry"], EPS_CN)})
    cntxt = json.dumps({"type": "FeatureCollection", "features": prov_feats},
                       ensure_ascii=False, separators=(",", ":"))
    parts.append("echarts.registerMap('china'," + cntxt + ");\n")
    print("中国省级地图：%d 个 feature（含台湾/香港/澳门/南海诸岛）· %.1f KB"
          % (len(prov_feats), len(cntxt) / 1024.0))

    io.open(DST, "w", encoding="utf-8").write("".join(parts))
    print("已生成 %s  %.1f KB" % (DST, os.path.getsize(DST) / 1024.0))


if __name__ == "__main__":
    main()
