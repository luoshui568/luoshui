# 储量地图批量出图 —— 快速使用手册

> 面向「以后再做个 XX 公司的资源储量分布图」的场景。
> 用 `build/chartmap.py`，一份数据 → 一张图，不需要碰 ECharts 配置细节。

---

## 一、最小用法

```python
import sys; sys.path.insert(0, r"<repo>/build")
import chartmap as CM

cm = CM.MapKit(r"<repo>/build/lib", mode="world")   # 或 mode="china"
opt = cm.option([
    ("China",         "中国",       21000),
    ("Australia",     "澳大利亚",   18000),
    ("India",         "印度",        8500),
    # ... 只列**有数据**的；其余区域自动补成「无数据可悬浮」
])
```

`opt` 就是一个普通 dict，直接 `json.dumps` 后写进 `wb_report_charts.opt` 即可。

- **world 模式**：`name` 必须是底图里的**英文国名**（`China` / `United States`…）
- **china 模式**：`name` 必须是**省简称**（`四川` / `内蒙古` / `中国香港`…）
  —— 底图里的全称已在构建期归一化成简称，别写「四川省」

想确认某个名字对不对：

```python
print(CM.load_region_names(r"<repo>/build/lib", "world")[:10])
```

---

## 二、换一套数据（最常见的批量场景）

### 换矿种（改文案）

```python
cm = CM.MapKit(LIB, mode="world")
cm.tooltip_label = "锂资源储量"          # tooltip 里那行指标名（世界图）
cm.tooltip_unit  = "万吨 LCE"            # 单位后缀
cm.tooltip_total = "占全球"              # 占比词
cm.tooltip_dec   = 1                     # 占比小数位
cm.tooltip_base  = 69000.0               # ★ 占比**分母**；<=0 ⇒ 改用「各值之和」
cm.tooltip_nodata = "USGS 2023 年统计未单独列示"   # 无数据时的第二行小字
cm.tooltip_short  = "锂资源储量"          # 中国图专有：无数据时那句「暂无××数据」的短名
```

> ✅ **2026-09-21 起已参数化**（原先这五样是**写死在壳的 JS 里**的，换矿种就会串口径：
> 黄金图的悬浮框会显示「钛铁矿储量 万吨 占全球 91.3%」）。现在这些值随 option 里的
> `{{fn:mapTip:…}}` 令牌一起下发：
> `指标名~单位~占比词~分母~无数据提示|英文名=中文名|…`（`~` 分段；含 `=` 的段进对照表，
> 不含 `=` 的段当元信息）。中国图是 `指标名~单位~无数据短名`。
>
> 📌 **向后兼容**：旧令牌（母本 600456 那两张图，只有 `A=甲|B=乙`）里一个 `~` 都没有
> ⇒ 壳自动落回钛铁矿默认值。已实测 216 个世界区域 + 35 个中国区域**逐字节零差异**。
>
> ⚠️⚠️ **改了令牌协议就必须同步重编并上传壳**（`report.html`）。壳的 `FNS.mapTip`
> /`mapCnTip` 是解析方，只改数据不改壳 ⇒ 新图在线上仍按钛铁矿口径显示。
> 这条没有「只改数据的绕法」，已实测两条死路：`value` 传字符串后 `{c}` 输出 `NaN`；
> `{@字段}` 模板变量不被 map series 支持（悬浮框为空）。

### 换分档阈值（不同矿种的量级差别很大）

```python
cm.tiers = [(8000, "#a30f24"),   # 极大
            (2000, "#d0202f"),   # 大
            (300,  "#e06670"),   # 中
            (0,    "#eea3aa")]   # 小
```

> ★ 阈值必须按**本次数据的实际分布**定，不能从别的矿种照抄。
> 抄错的表现：所有区域塌进同一档，一片同色。
> `selfcheck()` 会断言「至少用到 2 档」，能挡住这个错。

怎么定阈值：把数据排序，看自然断点。

```python
vals = sorted((r[2] for r in rows), reverse=True)
print(vals)          # 找断崖处当下限，一般取 4 档
```

### 换配色

```python
cm.accent     = "#0b7285"      # 主色（悬浮描边 + tooltip 数值色）
cm.hover_fill = "#d3f0f5"      # 悬浮填充
cm.nodata_fill= "#e6e5e2"      # 无数据区域填充
```

> ⚠️ 分档色**明度必须 < 0.78**。渲染层的 `beauty()` 对 < 0.78 的色会归一到主红系
> （就是「主题红铺满」的效果）；≥ 0.78 的浅色会被另一套逻辑接管，视觉会飘。
> 保持红色系是最稳的（也符合 A 股报告语境）。

---

## 三、调版面 / 标签

```python
cm.zoom_max      = 14           # 最大放大倍数
cm.layout_center = ["50%", "42%"]# 底图中心（中国图含九段线，包围盒高，必须上移）
cm.layout_size   = "118%"       # 底图缩放（中国图 118% 才不浪费下半部留白）
cm.pos           = {"China": "right", "Canada": "top"}   # 标签朝向，整体覆盖
cm.no_label      = {"甘肃", "河南"}                       # 完全不显示标签的区域
cm.small         = {"陕西", "广西"}                       # 字号降一号的区域
```

- **`no_label`**：真的放不下的区域（会压住邻省/叠字），直接关掉标签。
  数值仍能从 tooltip 和旁边的表格读到，不算信息丢失。
- **`small`**：只降字号，**仍然显示**。别把够放的中游区域塞进 `no_label`，
  否则图上只剩三四个标签，信息量断崖下跌。

### ★★★ `no_label` / `small` **必须按本次数据重定**（别继承默认值）

默认值是为「钛铁矿那一份地理」调的：世界图默认关掉挪威/南部非洲一带五个小国；
**中国图默认 `no_label = {甘肃, 河南}`** —— 换矿种直接继承就会把**最大的那个省**
的标签关掉（实测：贵研的甘肃占全国 69.6%、恒邦的甘肃是全国第二大省，都会被关）。
⇒ 新数据的 `no_label` / `small` 一律重定，`pos` 只在默认表上**增量覆盖**。

### ★★★ 标签被「吃」掉 —— 用 `moveOverlap` 而不是关掉 `hideOverlap`

只写 `labelLayout.hideOverlap:true` 时，ECharts 会把**挤在一起就干脆不画**
（实测：恒邦黄金世界图 13 国被吃掉 3 个 —— 哈萨克斯坦/秘鲁/乌兹别克斯坦；
中国图 26 省只画出 20~21 个）。改 `pos` 朝向**救不回来**（实测仍是 10/13）。

正解：`{"hideOverlap": true, "moveOverlap": "shiftY"}` —— 重叠改为**上下错开**，
`hideOverlap` 仍然保留 ⇒ `selfcheck` 坑2 照过。实测世界图 13/13 全显示。
（`hideOverlap:false` 虽然也能全显示，但那是**叠字**，`selfcheck` 会直接拦下。）

密度实在压不下来时（如 26 省的中国图，`shiftY` 后仍有 4~5 个省名放不下）
**不要**硬撑：把「标签密集处会自动错开、个别省名可能未静态显示、悬停/见下表」
写进那段口径说明里 —— 表里有全部数值，比塞满叠字强。

---

## 四、做完必跑 `selfcheck()`

```python
info = cm.selfcheck(rows)      # 不通过直接 raise
print(info)
# {'series': 1, 'rows': 216, 'valued': 12, 'nodata': 204, 'labels': 7, 'tiers_used': 4}
```

它把历史上踩过的**五个坑**写成了断言：

| 断言 | 挡住的坑 |
|---|---|
| `series` 里没有 `geoIndex`、`option` 里没有 `geo` | 区域填充权被 geo 夺走 ⇒ 全图变灰（且 `getOption` 还会回显正确色，极难发现） |
| `series` 恰好 1 条、`roam` 在 series 上、有 `labelLayout.hideOverlap` | 标签另起坐标系 ⇒ **一放大就错位** |
| 每个有值 data 项都内联 `label` | 同上（正解是标签挂在区域自己的 data 项上） |
| label 上没有 `backgroundColor`/`borderRadius` | 变成白色方块胶囊，丑 |
| `tooltip.formatter` 是 `{{fn:map*}}` 令牌 | map 的 `{c}` 不吃 `valueFormatter` ⇒ 出裸数/NaN |
| 全部区域名都进了 `data` | 无数据区域是「死的」，悬浮没反应 |
| 用到 ≥2 档色 | 阈值抄错口径 ⇒ 一片同色 |

---

## 五、渲染层必须配套（否则 tooltip 会乱）

`option()` 产出的 tooltip 是 `{{fn:mapTip:...}}` / `{{fn:mapCnTip:...}}` 令牌，
需要页面壳里的 `FNS` 表存在同名函数。把下面这段贴进 `FNS`：

```python
print(CM.render_snippet())
```

（幂等：重复贴无害，但请只保留一份。）

另有一条**独立于本工具**的渲染层铁律：

> `revive()` 遇到认不出的 `{{fn:...}}` 令牌**必须返回空串**，绝不能原样返回。
> 否则 ECharts 会把整串令牌当文字画出来，横贯整张地图。

---

## 六、完整批量流程（多份报告）

假设要给 N 份报告各加一张储量图：

```
① 准备 N 份数据 JSON（每份 = [[name, cn, value], ...]）
② 逐份生成 opt：
       for f in data/*.json:
           python build/chartmap.py --mode world --data <f> --out <f>.opt.json
   （命令行会顺带跑 selfcheck，不通过就报错停下）
③ 把 <f>.opt.json 写进对应报告的 wb_report_charts.opt
④ sync_seed_full → build.py → check → 上线
```

命令行用法：

```bash
python build/chartmap.py \
    --lib build/lib \
    --mode world \
    --data 'data/li_reserves.json' \
    --out  build/_li_opt.json \
    --indent 1
```

`--data` 既接受文件路径，也接受内联 JSON 字符串。

---

## 七、验证「放大不错位」（改完建议跑一次）

```bash
python build/_zoom_align_check.py 25 chartTiWorldMap 3
python build/_zoom_align_check.py 25 chartTiCNMap 2.5
```

判定：`ratio_spread` 应 = `1.0`（各区域同比缩放 ⇒ 单坐标系）。
如果 > 1.05，说明又退回了多坐标系写法。

原理：取若干有值区域的几何中心（`cs.getRegion(name)._center` →
`cs.dataToPoint`），缩放前后算两两屏幕距离之比。
单坐标系下所有比值都等于缩放倍数；多坐标系下会发散。

---

## 八、已知边界

- **底图只有两份**：`worldcn`（216 国 + 合法国界）和 `china`（35 省级 + 九段线），
  都由 `build/make_worldmap.py` 生成在 `build/lib/world-cn.js` 里。
  **不要用 ECharts 官方 world**（中国画法不合国标）。
- **标签锚点是区域几何中心**，不能按任意经纬度摆放。
  需要精确定位时得改回 `scatter` 锚点 —— 但那会重新引入错位问题，
  两者不可兼得（见第七节的判定）。
- **量级差过大的数据**（如最大/最小差 1000 倍）不适合区域铺色，
  优先考虑气泡图或直接上表格；区域铺色只适合「同一量纲内比大小」。

---

## 九、headless 取证的两个坑（都踩过）

1. ★★★ **测量坐标与截图必须同视口宽度**：`--dump-dom` 不给 `--window-size` 时
   视口是默认 800 宽，而截图常给 1300 —— 坐标整体错位，裁出来的图看着像
   「世界地图只剩美洲、右边被切」。两次调用**必须用同一个宽度**。
2. ★★★ **「标签到底画了几个」不能靠肉眼数**：缩小图上很容易漏看。
   正解是进 ZRender 的 display list 数文本元素（`build/_probe_maplabel.py`）：
   ```js
   inst.getZr().storage.getDisplayList(true).forEach(function(e){
     var s = String((e.style||{}).text||''); ... });
   ```
   `labelLayout.hideOverlap` 是把标签**从 display list 里摘掉**（不是 `ignore`），
   所以只能这样验。
3. ★ 两种「离线取证」脚本：
   - `_shot_maps_new.py` —— 把本地 seed 的槽 25 换成新渲染结果 + 注入新图 option，
     跑**线上同壳**出图（`solo(m25)` 只显示一个模块，否则整页 5 万像素）。
   - `_maps_dump.py` / `_maps_apply.py` —— **算/写分离**：前者只读对账并落盘，
     后者纯 REST（出网间歇性不可用，写库阶段失败重跑要 ~2 秒而不是 1 分钟）。
