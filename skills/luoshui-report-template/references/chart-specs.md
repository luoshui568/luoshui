# 洛水研报模版 · 图表专项规范

> **改任何图表（ECharts opt / 渲染层 / 地图 / 时间轴）前读这份。**
>
> - 图表 opt 存在库里（`wb_report_charts`）⇒ **改图 = 改库，不必部署**；
>   只有改**渲染层 / 模板**才发 `report.html`。
> - 渲染层统一美化入口 `beauty()`（§1）；模块 25 地图的**出图通道**在 `module-standards.md` §8。

---

## 1. 图表渲染层补丁（挨着 `beauty()`，全在 `deploy/report.template.html`）


| 函数 / 口子 | 作用 | 触发条件 / 用法 | 探针 |
|---|---|---|---|
| `btAlignZero(inst, opt)` | 双轴 **0 刻度对齐**（自动） | ⚠️ **只认 `{value:…}` 与**纯数字 **，认不出 `[x, y]` 数组** —— `if(v && typeof v==='object') v = v.value` ⇒ 数组取到 `undefined` ⇒ `dmax` 停在 `-Infinity` ⇒ 在 `if(!isFinite(dmax)) return;` 处**提前放弃，一个字段都没改**。**`type:'time'` 的图必然中招** ⇒ 见 §3.2 自己写 | `probe_axis_zero.py` |
| `btFixNegBar(s, opt)` | 负值柱**圆角朝向** | **只有逐项 `data[i].itemStyle.borderRadius` 生效**（系列级 / 写函数都被忽略）；横向条形图跳过 | `probe_negr.py` |
| `ringTip` | 环图 tooltip | 环图专用 | `probe_ring_m11.py` |
| ★ **`{{fn:hideNeg}}`（FNS 新增）** | **吞掉「假负刻度」** | 为对齐 0 而被迫下探到负数的轴上，写 `"formatter": "{{fn:hideNeg}}"` 把负刻度藏掉（与 `btAlignZero` 内部 `btHideNeg` **同口径**） | — |
| ★ **`areaStyle.__keep`（渲染器新开的口子）** | **保留作者写的面积样式** | `beauty()` 对折线**无条件**写死 `s.areaStyle = {color: btGrad(c,.30,.02)}`（**只给整图第一条折线**），且 `btA()` 是**纯替换 alpha** ⇒ 在 opt 里调色调不出来。要实色面积必须打 **`areaStyle.__keep: true`** | — |
| ★★ **`type:'time'` 轴必须自己写 `dataZoom`** | 时间轴的**自动缩放进不去** | ECharts 时间轴的 `catCount` **恒为 0** ⇒ `dataZoom` 的自动计算拿不到数量、**内置缩放条等于不存在**。要能缩放（或要按区间只显示近 N 年）必须**在 opt 里手写 `dataZoom`**（`type:'inside'` + `startValue/endValue` 或 `start/end` 百分比） | — |

均在 `setOption` 之后调用。

⚠️ **`__keep` 只能精确判 `__keep`，绝不能放宽成「作者写过就尊重」** —— 全库扫出 **25 张图**
第一条折线自带 areaStyle，绝大多数是 `{"opacity": 0.06}` 老写法 ⇒ 一放宽会集体从
`.30→.02` 渐变**塌成 6% 平铺**，是**全站级回归事故**。

---

## 2. 模块 2「时间轴」与模块 10「营收/净利图」


- **m2 时间轴**：`build/chartflow.py` TimelineKit。**只落 CSS + JS** ⇒ 11 份已入库研报**全体生效**。
  **改前必读** `.workbuddy/memory/MEMORY-detail.md` 第二节。探针 `build/probe_tlnav.py`。
- **m10 营收/净利**：`chart_opts()` 的 `chartRev` = **左右双轴双柱**。
  存量 11 张已由 `build/patch_rev_bar.py` 改写。
  ⚠️ seed 里图表 id 是**裸键**，只改库不改 seed 会被 `push_reports_v31.py` 刷回。

---

## 3. ★★ 模块 29「EPS 与股价历史」双轴图（2026-10-15 重做 · 可复用的范式）


用户令原话（**就是验收标准**）：
> 「帮我改一个这个，从 iFinD mcp 里面获取宝钛股份的收盘价日线和单季度的每股收益 eps（ttm），
> 收盘价做面积图，每股收益做柱状图，**要双轴，数据要上市以来的所有数据**，样式要好看」
> ＋「这个 0 轴两边对其」＋「**面积图太透明了，面积图要在最上面一层**」

### 3.1 取数口径（★ 数据源分真假，别信 API 名字）

| 需要 | 用什么 | 关键口径 |
|---|---|---|
| 日线收盘（**上市以来全量**） | **通达信 `tdx_kline` `tqFlag=2`（后复权）** | ⚠️ **`tqFlag=1`「前复权」已损坏**：24 年跨度下早年价格被调成**负数**（最低 −2.61）、日涨跌幅放大到 **+35% / −14%**。**后复权才是正确的乘性复权**（600456 十送除权日 2006-09-20 仅 **−3.14%**，不复权则 **−46.21%**） |
| 复权换算 | `前复权(t) = 后复权(t) × 不复权最新收盘 / 后复权最新值` | 600456 因子 **0.35298**（＝累计复权 2.8330）；右端落在真实盘口价 **23.48** |
| 分页 | **每页固定只给 700 根**（`wantNum` 给 1000 也一样） | 按 `startxh` 步长 **700** 递增翻页（0/700/…/5600）；结果超 token 会**自动落盘**到 `tool-results/mcp-tdx-connector-tdx_kline-*.txt`，不占上下文 |
| EPS(TTM) | iFinD `get_stock_financials` | **按自然日填充 + 答案截断 ~100 行（无翻页 / 无 csv）**；`TTM基准日＝报表公告日期` ⇒ 序列**按公告日阶跃**。取「**值发生变化**」的日期当**披露生效日**；问不全就**按 5 年一段分批**（600456 得 **87 期**） |
| EPS(TTM) 批量（**11 份铺开时的正解**，见 §4） | **westock `data_finance`**（`type=income`） | 直接给 **`EPSTTM`**（与 iFinD 同值，抽验 600456 逐期对上）+ **`InfoPublDate`**（公告日）⇒ 一次问到底、天然阶跃。⚠️ **只给 `start` 不给 `end` 时 `num` 默认 1 ⇒ 只回 1 期**；必须 `start`+`end` 成对 |
| ❌ 弃用 | iFinD `get_stock_performance` 取日线 | 只能拿逐日前复权、按自然日填充、截断 ~100 行 ⇒ 覆盖不了 5,897 个交易日 |

★★ **翻页终止判据：看「最后一页是不是满页（700 行）」，不是「跑了几页」。**
点名的坑：601958 金钼股份按 sx=0/700/…/3500 拉了 **6 页全满**，当时误判到底，
结果**首日变成 2009-06-23**（真实上市日 2008-04-17）⇒ 整整漏掉 **284 根**（sx=4200）。
判据：**满页 ⇒ 后面一定还有**，必须继续翻；只有「明显不满页」才是终页。
（落盘字节数也是旁证：满页约 295k~307k 字符，200~600 行的终页会骤降到 87k~287k。）

### 3.2 双轴 0 对齐：**自己在 opt 里写死**（别指望 `btAlignZero`，那是结构性失效）

- `type:'time'` 的图 `btAlignZero` **必然提前 return**（见 §1）⇒ 必须自己定 min/max。
- 口径：0 刻度的相对高度 **`p = e/(e+f)`**，**两轴 p 相等才齐平**；等价说法 =「**同格数、0 落同一格**」。
- 600456 实测：左轴 EPS（数据 `[−0.5280, 1.3761]`）取 `min −0.6 / max 1.8 / itv 0.6`；
  右轴股价（`[2.59, 70.68]`）取 `min −25 / max 75 / itv 25` ⇒ **两轴都 4 格、0 都在自底第 1 格（25%）**，网格线水平贯通。
- ⚠️ **含负值的轴一旦定了 0 的位置，非负的那条就必须下探到负数** ——
  **下方留白比例只由 p 决定，躲不掉**（右轴 max 必须 ≥ 70.68 ⇒ 取 75；min 由 p 反推 = 25）。
- **假负刻度**（右轴 −25 纯粹是为对齐让位的）用 `{{fn:hideNeg}}` 吞掉
  ⇒ 实测轴标签左 `-0.6|0|0.6|1.2|1.8`、右 `|0|25|50|75`（**−25 被吞**）。

★★ **刻度结构有一个极易写错的 off-by-one**（2026-10-15 铺开 11 份时踩到）：
「4 格」= **5 条刻度**，`interval = s` 时两端是 **`lo = −s`、`hi = 3s`**（刻度 −s / 0 / s / 2s / 3s），
0 才落在 **25%**。写成 `hi = 4s` 就变成 **20%**，虽然两轴仍齐平、但右侧白边少了一格、
且 `interval` 被算成非整数（2.5/4 = 0.625 ⇒ 刻度 0.125 / 0.75 这种丑数）。
**通用公式**：`hi = lo + N·s`；含负值取 `lo=−s`（⇒ hi 由 `s ≥ emax/(N−1)` 约束）；
全正取 `lo=0`（⇒ hi 由 `s ≥ emax/N` 约束）。

★★★ **`min` / `max` / `interval` 落库前必须 `round(·, 6)`**（同上，血案）：
`−1.2 + 4×1.2 = 3.5999999999999996`（浮点）。ECharts 的**端刻度取 `extent[1]` 原值**、
不走 interval 精度归一（中间刻度 1.2000000000000002 / 2.4000000000000004 反而会被它自己抹平）
⇒ 左轴顶端标签渲染成 **`3.5999999999999996`**，17 个字宽超出 `grid.left: 64px`
⇒ 屏幕上看只剩尾巴 **「99999996」**。修法：三个字段统一 `round(x, 6)`。

### 3.3 面积层：实色 + 置顶

- opt 里自带 `rgba(208,32,47,0.58) → rgba(208,32,47,0.10)` 竖向渐变 + **`areaStyle.__keep: true`**（见 §1）。
- **层级**：`series[line].z` 取 **5** > `series[bar].z` **4** ⇒ 面积与线一起压住柱子。
- ⚠️ **副作用**：被面积盖住的柱子会**叠成灰紫**（红 α0.58 压在蓝上）。
  嫌柱子发灰就把 `_eps_opt_600456.py` 里面积顶部 alpha 从 0.58 降下来**重跑 opt**
  ⇒ **只改库、不用再发壳**。

### 3.4 写库（图行删不掉 ⇒ 先留快照）

- 目标行 `wb_report_charts.id = 600456_chart_eps`（`seq=16`）；旧 opt 只有 8 个年度点，新 opt **134 KB**。
- 工具：**`build/set_600456_chart_eps.py`**（干跑比对 → 快照 → PATCH → **回读比解析后的 dict**）·
  opt 构建器 **`build/_eps_opt_600456.py`**（EPS 87 期阶跃点写死在脚本里，口径注释齐全）。
- ⚠️ **jsonb 会重排键序 ⇒ 回读必须比「解析后的 dict」，比 md5 必假红**。
- 快照落在 `build/backup/600456_chart_eps_pre_<ts>.json`。
- ⚠️ 顺带：模块里的「技术解读」段可能还留着**旧价格 / 旧估值**（如「当前 27.35 元 / PB 1.80 / PE 34 倍」）
  —— 更新图后要**一并检查这处**，否则与新图右端价不一致。

### 3.5 发布顺序（★ 防「新数据配旧壳」）

**先发 `report.html`（新壳 + 旧 opt ⇒ 零可见变化），再写库新 opt** ⇒ 中间没有窗口期。
渲染器改动用 **`build/_patch_eps_area.py`** 定点注入**刚 curl 的线上字节**，
自带**锚点唯一性断言**与**逆向还原自检**（还原 == 基线才放行）。

### 3.6 验证注入：**别写 `St.charts[k].opt = …`**

★ `St.charts` 的键是 **`chart.id.slice(code.length+1)`**，与槽位 `data-chart` **未必同名**
（实测 600456 时 `St.charts` 里没有 `chart_eps`、`St.inst` 里有）⇒ **静默落空**，
表现为「改前 / 改后」两张图一模一样。**正解**：`revive → beauty → St.inst.setOption(o, true)`；
诊断可把 `Object.keys(...)` 塞进 `document.title`。

### 3.7 截图工具（canvas 图专用，两个坑）

- **`build/_shot_chart_slot.py`** —— 截**图表槽的真渲染结果**。
  ★ 图表是 canvas，**不能 `cloneNode`**（不复制位图）⇒ 让原页渲完，再把**兄弟模块全隐藏**、
  只留目标模块的 `h3 / [data-chart] / .src`。`--override` 喂刚 curl 的线上字节、`--opt` 喂本地 opt
  （**不写库**就能看渲染）。
  ★★ **踩过的坑**：按文案找「返回工作台」再向上收容器时，循环条件写成
  `e.parentElement !== document.body` ⇒ e 正好停在 `#wrap`、把**整份报告 display:none**，
  现象是「**截图纯白 + `slot.clientWidth===0`**」，而 canvas 其实早渲染好了（980×336）。
  **正解：只走到 `#wrap` 的直接子节点为止，绝不隐藏含 `#mods` 的节点。**
- **`build/_shot_eps_ba.py`** —— 改前 / 改后对照图。
  ★ **改前不写库**：用线上字节渲染后把 opt 换回快照里的旧 opt、重渲一次即可。
  ★ PIL 画中文要**指定字体**（`Songti.ttc` / `PingFang.ttc`）。
  ★★ **`os.chdir()` 之后写相对输出路径会落进临时目录** ⇒ 输出路径一律先 `abspath`。

---

## 4. ★★ 把这张图铺到其余 11 份研报 + 摘掉 m28 的「收盘价+成交额」图（2026-10-15 已完成）


用户令原话：
> 「**全部 11 份都加，并且把成交额加收盘价那块全部去掉**」

### A. 涉及面（先摸清再动手，别猜）

- 12 份研报（含 600456 母本）：`000731 000762 000830 002237 002408 600392 600459 601118 601958 603599 603977` + 600456。
- **其余 11 份的 m29 一个图表槽都没有**（只有宝钛有 `chart_eps`）⇒ 12 份全部要在 m29 顶部**前插**。
- 旧的「收盘价+成交额」图是 **`chartPrice2`，挂在 m28「区间股价表现」小节**（000731/000830 的 h3 叫「股价解读」）。
  ⚠️ **11 份里只有 8 份真的是「收盘价 line + 成交额 bar」**：
  `000762 002237 002408 600392 600459 601118 601958 603599 603977`（9 份）；
  例外 **000731 = 年内最高/收盘价(年均)/年内最低**、**000830 = 收盘价 + EPS(TTM)**。
  虽然名字不符，但同槽同用途 ⇒ 按「全部」一并摘掉。

### B. 取数：一次成型，别按老路 55 次

| 环节 | 正解 | 坑 |
|---|---|---|
| 日线 | 11 份 × 分页 `tdx_kline(tqFlag="2", period="4")` | ★ 终页判据见 §3.1「满页 ⇒ 还有」（601958 漏了 284 根） |
| 归一因子 | 每份再拉一次 `tqFlag="0" wantNum=5` 取 `rows[-1].Close` ⇒ 落 `seed/_raw_last.json` | `AttachInfo.Close` 是**昨收**、`AttachInfo.Now` 才是当日，别混 |
| EPS(TTM) | **westock `data_finance`，`codes=` 多代码合并 + `start`/`end` 成对** ⇒ 结果必然超 10 万字符、**自动落盘**，不占上下文 | 3 批就拉完 11 份全历史（906 个报告期）；单份 `num=100` 只回 42 期、且 90 KB 卡在阈值下**不会落盘**，白烧上下文 |

工具链（全部可复跑）：
`build/_scan_tdx.py`（按末日期排序扫描落盘页）· `build/_merge_tdx.py --code X --prefix '…*'`（合并去重 + 工作日缺口检测）
· `build/_build_eps_steps.py`（westock 落盘 → `seed/_eps_steps_<code>.json`，缺失公告日按 A 股披露规则反推）
· **`build/_eps_opt.py`**（参数化 opt 构建器，产物 `seed/_eps_opt_<code>.json`）
· **`build/apply_eps_to_11.py`**（备份 → 改库 → 回读）· `build/_update_eps_opts.py`（**只**刷 opt，不动 HTML）
· `build/probe_eps11.py`（渲染 + 0 轴像素对齐验收）· `build/_compose_eps11.py` / `build/_shot_m28_before.py`（交付图）

### C. 「图表行删不掉」已二次坐实

`wb_report_charts` 的 **REST `DELETE` 实测 `401 DATABASE_42501 permission denied for table wb_report_charts`**
（安全探针用的是匹配空集的过滤条件，不会误删）。
⇒ **摘图只能摘槽位**：把模块 HTML 里的 `<div data-chart="chartPrice2" …></div>` 正则删掉，
**行留成孤儿**（`St.charts` 里还有它、页面不再渲染，可用浏览器内注入临时插回来做「改动前」对照）。

### D. 改库的做法（两条 SQL 语义不同，别混）

- **m29 是「前插」**：`newHtml = M29_HEAD + oldHtml`。★ **脚本不可重跑**，重跑会插两遍 ⇒ 刷 opt 要用单独的 `_update_eps_opts.py`。
- **m28 是「摘槽」**：`re.sub(r'[ \t]*<div[^>]*data-chart="chartPrice2"[^>]*>\s*</div>\s*', '', html)`，并断言**命中恰好 1 处**。
- ★ **纯库内改动（模块 HTML / 图表 opt）不需要部署** —— `renderCharts` 按槽位 `data-chart` 拉库渲染，槽是通用的。
  本次**没动 `report.html` 一个字**。
- 回读要逐项断言 5 件事：`m29 一致` / `m28 一致` / `槽在` / `旧槽已删` / `opt 一致`。

### E. 验收判据（`probe_eps11.py`，12 份逐份）

`m29slot=1 · epsinst=1 · p2slot=0 · chartmiss=0 · slotgone=0 · card-overflow=0`，
并且 **`convertToPixel({yAxisIndex:0},0)` 与 `({yAxisIndex:1},0)` 的像素 y 完全相等**
（实测 4 格图 223=223、0 落底边图 282=282）＋ 折线末点 == `_raw_last.json` 里的不复权最新收盘价。
通用回归另跑 `probe_report_mac.py`（`cards=31 / chartmiss=0 / slotgone=0 / logic-open=0`）。

### F. 顺手记两个坑

- ★ 表结构：`#mods .card` 里**一个模块可能有多个 `h3`**（000731 的 m28 有 6 个）
  ⇒ 定位小节必须 `querySelectorAll('h3')` **全扫**，只取 `querySelector('h3')` 永远匹配不到「区间股价表现」。
- ★ `socketserver.TCPServer.allow_reuse_address` 是**类属性**，在 `server_bind` 里读
  ⇒ 必须**构造前**设在子类上；构造后再赋值没用，连跑多个端口会撞 `Errno 48 Address already in use`。
- ★ 多个 headless Edge 连跑会偶发卡死（`subprocess` 240s 超时）⇒ 加 `sleep 3~4` 间隔，必要时 `pkill -f "Microsoft Edge.*--headless"`。
- ★ PIL 画中文：本机**没有 `PingFang.ttc`**，用 `/System/Library/Fonts/Hiragino Sans GB.ttc`（正文）
  + `/System/Library/Fonts/STHeiti Medium.ttc`（粗体）。

---

## 5. ★★ 图表的「时间范围」按钮组（3年 / 5年 / 10年 / 全部）

> 2026-10-16 用户反馈「**m29 少了一个时间选择按钮**」+「**m13 这里又多了一个**」——
> 同一段代码里的**两个独立缺陷**。两处都在 `deploy/report.template.html`（纯壳，**不写库**）。
> 专属探针：`build/_probe_toolbar.py`（`--src <html>` / `--code <code>`）。

### 5.1 机制（改动前先看懂）

`renderCharts()` 逐个图槽算 `var zoom = (n >= 5 && !NO_ZOOM[key])`（`n = catCount(opt)`），
`zoom` 为真 ⇒ ① 给 opt 挂 `dataZoom`（`inside` + `slider`）；② `St.slots.push({... zoom:true})`。
随后 `renderToolbars()` 遍历 `St.slots`，**在每个 zoom 槽位前插一组 `.rpt-toolbar`**。

### 5.2 ★★ 缺陷一：按钮插错位置（「m13 多一个」）

**根因**：`renderToolbars()` 原来写

```js
var inst = St.inst[s.key]; if(!inst) return;
var dom  = inst.getDom();
```

而 **同一个 key 可以挂多处槽位**（`chartMargin` 在 **m11 与 m13 各一块**，`St.inst[key]` 只留最后
初始化的那个）⇒ 两次循环都拿到**同一个实例的 DOM** ⇒ 两组按钮**全堆在 m13 前面、m11 一个都没有**。

**修法**：`St.slots.push({... inst:inst, dom:slot})` —— **按钮归属按槽位取**，不再按 key 查；
同时另开 `St.insts = []` 收全部实例，`resize` 遍历它（原来遍历 `St.inst` 会漏掉其中一块图）。

★ 判据：**一个模块出现 2 组按钮不一定是 bug** —— 000762 的 m11 本来就有 `chartMix` + `chartMargin`
两张图（各一组，正确）。要查的是「**同一张图对应的槽位**有没有拿到别人的按钮」：
`_probe_toolbar.py` 会按 `bar.nextElementSibling.getAttribute('data-chart')` 列出归属，
看每个 key 是否只有一条、且 `moveOn 3年` 生效。

### 5.3 ★★ 缺陷二：time 轴永远拿不到按钮（「m29 少一个」）

**根因**：m29 的「EPS 与股价历史」用 `xAxis.type = 'time'`，**没有 `xAxis.data`**
⇒ `catCount` 恒为 **0** ⇒ 既没有按钮组，也进不了 dataZoom 分支。

**修法**（两处）：

```js
var isTime = (axisKind(opt) === 'time');            // 新增 axisKind()
var cnt = isTime ? seriesCount(opt) : n;            // time 轴改看**数据点数**
var zoom = (cnt >= 5 && !NO_ZOOM[key]);
var tspan = (zoom && isTime) ? timeSpan(opt)   : null;   // 数据的时间跨度 [最早, 最晚]
var axspan = tspan ? axisExtentMs(opt, tspan) : null;    // **轴**的范围 [左, 右]（含显式 min/max）
```

- `seriesCount()` = 各 `series[].data` 长度取最大（EPS 图 = 50 期柱 vs 2715 个交易日 ⇒ 2715）。
- ★ **time 图库里自带 `dataZoom` 时一律不覆盖**（`_eps_opt.py` 调的 `fillerColor` / `brushSelect` /
  `handleStyle` 会被上面那两条 category 默认值盖掉，整条缩放条走样）。

### 5.4 ★★ 为什么「近 3 年」不能沿用按索引的百分比

`dataZoom` 的百分比是**相对轴的 extent**，而 EPS 图的 `xAxis.min/max` 被**显式钉在
`2015-01-01 ~ 2027-04-03`（12.25 年）**，数据却只铺到 2026-10-15：

- 用按索引那套 → 算出来「3 年」实际窗口是 **3.7 年**，肉眼可见地不对；
- 且右边界若取 `100%`，窗口会跑到 2027-04 ⇒ **右侧多出 5 个月空白**。

⇒ `yearWindow(tspan, axspan, yrs)`：左边界 = **数据末端往前 `yrs` 年**、右边界 = **数据末端**
（不是轴末端），再统一换算成百分比，**仍然走 `dispatchAction({start, end})` 的老通道**。

★ 实测（603227）：点「3 年」得 `[71.709…, 96.201…]` ⇒ 宽度 `24.49% × 12.25 年 = 3.00 年` ✓；
右边界 `96.20%` 正是「2026-10-15 落在轴上」的位置，不是 100%。

### 5.5 ★★ 为什么不给 dataZoom 传 `startValue / endValue`（走了弯路，记牢）

ECharts 文档写明「**如果设置了 `start` 则 `startValue` 失效**」，而：
- 库里 EPS 图的 `dataZoom` 本来就带 `start:0 / end:100`；
- `setOption` 的普通 merge **清不掉** `start`（传 `null` = 不修改）；
- 于是 `startValue` 静默失效 ⇒ **按钮点了没反应**，且**不报错**。

也能用 `{replaceMerge:['dataZoom']}` 整组替换，但那要自己把原条目的样式字段逐个搬过去（易漏）。
**结论：继续用百分比，只把「算百分比」这一步换成按真实时间算** —— 改动最小、风险最低。

### 5.6 验收（`_probe_toolbar.py`，两处都正反验）

```
603227  按钮组 13 ≈ 覆盖 13 槽位 ｜ 每模块 1 组 ｜ 无重复模块 ｜ 13/13 「3年」真实生效
        m29 chart_eps [0,100] → [71.709, 96.201]    ← 修复前这一行**根本不存在**
        m11 = 1 组（chartMix 是饼图、无 xAxis ⇒ 正确地不给按钮）
        m13 = 1 组                                  ← 修复前是 2 组
000762  16 组 / m11 = 2 组（chartMix + chartMargin，**两张不同的图，正常**）/ m13 = 1 组
```

配套回归：`probe_report_mac.py`（603227 / 000762 / 600456 全绿）、
`probe_blockstyle.py`（表格样式未被波及）、`probe_research_score.py`（44 项）。

---

## 6. ★★ 图型与数据表不匹配 —— 「空图」与「错图」是两类问题

> 2026-10-16 修 000762 / 002237 / 600459 / 601118 / 601958 时固化。

### 6.1 先分清是哪一类

| | 表现 | 根因 | 处置 |
|---|---|---|---|
| **空图** | 只有坐标轴、图例在但线是空的 | `numcol(rows, i)` 取到的是**文字**（「超 2,000 吨」「约 5.5%」「—」）⇒ 全 None | 补 `chart_rows`（列＝纯数值）**或**判据拦住 |
| **错图**（更危险） | 照常渲染、图例齐全、**不报错** | 列义错位：表格换了口径，渲染器仍按**写死的列号**取数 | **先改判据**，再决定补数还是摘槽 |

★ 判据永远**只卡「图真正用到的那几列」**（`numeric_rows(rows, idx=(1,2), need=1)`），
不能卡「任意列有值」—— 002237 的产能利用率在**列 3**，用 `need=1` 判任意列就会放行，
结果列 1/列 2 全空却照样建图。**建图侧（`chart_opts`）与挂槽侧（模块渲染器）的判据必须逐字一致**，
否则出孤儿图（有数据、不显示、不报错）。

### 6.2 ★★ 「口径对照表」不能当「产量/销量」画（601118 / 601958）

`chartProd` 画的是「产量(列1) / 销量(列2) / 产销率(列3)」，但 `production.rows` 经常是
**互斥口径的对照表**：

- **601118**：自产橡胶 10.42 万吨 / 天然橡胶加工量 131.0 / 橡胶销售贸易量 337.0
  —— 三个数字量纲相同但业务性质不同，各占一列，**没有任何一行同时有产量与销量**；
- **601958**：列 2 是「权益产量」而不是销量。

⇒ 原来只卡 `absolute` 挡不住，画出来**不是空图、是错图**。**新增两道语义闸**
（已写进 `report_build_v31.py` 的 `chart_opts` 与 m7 挂槽处，两处逐字一致）：

```python
_phead  = ' '.join(str(x) for x in (pr.get('head') or []))
_p1, _p2 = numcol(prows, 1, len(prows)), numcol(prows, 2, len(prows))
_paired  = any(a is not None and b is not None for a, b in zip(_p1, _p2))
if prows and pr.get('absolute') and '销量' in _phead and _paired:
    ...
```

① 表头必须出现「销量」字样；② 至少要有一行**同时**有列 1 与列 2 的值。
全库验证：只有 601118 / 601958 被拦下，**其余 6 份逐字节无影响**。

### 6.3 判据拦住之后，库里旧模块的槽位要**单独摘掉**

判据只管**新构建**；库里旧模块里的 `<div data-chart="…">` 还在 ⇒ 页面照样去取那张
（空或错的）opt 渲染出来。图表行删不掉（无 `is_del`、不在硬删白名单），
**唯一能做的是摘槽位**：

```bash
python3 build/drop_chart_slot.py 600459:6:chartCap 600459:12:chartPrice 601958:7:chartProd
python3 build/drop_chart_slot.py ... --go          # 写库
python3 sync_seed_full.py 600459 601958 --go       # ★ 记得收回 seed
```

摘完这张图变**孤儿**（有数据、无槽位）⇒ 页面不引用、不显示 ⇒ 无害。

### 6.4 ★ 「该不该补数」的判断顺序

1. **公司确实披露了** ⇒ 取数补 `chart_rows`、图留住。例：601118 的 `chartExp` 原本写
   「本报告唯一填不出来的模块」，实际 iFinD 直接给了「××费用／营业总收入」的五年序列，
   四条线一次补齐。
2. **公司没披露**（600459 的单价/单位成本、002237 的碳酸锂成本）⇒ 判据拦住 + 摘槽，
   **绝不倒推估算**。
3. **表结构天然不可比**（单位混杂、口径互斥）⇒ 判据拦住 + 摘槽，表格本身已经说清。

★ 还有一种「**不该动**」：**模块本来就用另一套设计**。600459 的 m11 是「表格版」
（分板块收入与毛利表 + 整体毛利率趋势表，图槽只有 `chartMargin`），**刻意不给它上双环** ——
强上会把 2025 年报（分产品）与模块里的 2026H1（分板块）两个口径并排，读者会以为图与表同源。
`mkmod11_ring.py` 的 SPEC 里已就地留注释与数据留档。
