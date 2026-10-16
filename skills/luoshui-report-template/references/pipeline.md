# 洛水研报模版 · 流水线：取数 → 组装 → 渲染 → 写库 → 上线

所有命令都在 `cd "$PROJ/build"` 下执行，主 Python 用 `$PY`，跑探针用隔离 venv `$PYV`。
> **`$PROJ / $PY / $PYV / $TCB / $ENVID / $DOM` 见 `SKILL.md` 的「★ 环境配置」** ——
> 换机器 / 别人使用时先改那几个变量（或直接告诉 AI 你的值）。

---

## 0. 前置：确认环境

```bash
ls cloud.json                          # envId + 匿名可发布 key（构建注入用）
ls report_template_v31.py report_build_v31.py push_reports_v31.py
ls deploy/report.template.html build/report_theme.css
```

线上（作者环境）：`https://liuchaowang.cn/report.html?code=<code>`
环境（作者环境）：envId `fdels568-d7g1d8o3y90a80cd7` —— **换成你自己的 `$ENVID` / `$DOM`**。

---

## 1. 取数（MCP）

按需选用已连接的连接器：

| 需要什么 | 工具 |
|---|---|
| 财务序列（营收/净利/毛利率/ROE/现金流/分红/每股指标） | `mcp__hexin-ifind-ds-stock-mcp__get_stock_financials` |
| 股本与股东 | `mcp__hexin-ifind-ds-stock-mcp__get_stock_shareholders` |
| 行情与估值 | `mcp__hexin-ifind-ds-stock-mcp__get_stock_performance` / `stock_highfreq_quotes` |
| 公司事件 / 风险 | `get_stock_events` / `get_risk_indicators` |
| 公告 | `mcp__hexin-ifind-ds-news-mcp__search_notice` |
| 新闻 | `mcp__hexin-ifind-ds-news-mcp__search_news` |
| 宏观 / 行业数据 | `mcp__hexin-ifind-ds-edb-mcp__search_edb` + `get_edb_data` |
| **券商研报 / 行业报告原文**（定性内容的来源） | `mcp__fxbaogao__search_reports` → `get_paragraphs` / `get_pdf_url` |
| 备用行情 / 板块 | `mcp__westock-mcp__data_*`、`mcp__tdx-connector__*` |

**落盘**：原始数据存 `seed/_raw_b1/<code>.<key>.json`，
`key ∈ rev / np / gm / nm / ocf / roe / lev / dps / eps`（见 `batch_assemble.py::SERIES`）。

★ **分产品口子的最快来源 = iFinD「主营构成-按产品」**：一次调用给出 N 年 × 前五档的
收入 / 成本 / 毛利 / 毛利率（m11、m22、m5 都吃它）。**写进研报前必做口径校验**：
分档合计 vs 合并营收（差应 < 1 万元量级）、分档毛利反算毛利率 vs 库内毛利率。
⚠️ **口径断点**：同一控制下企业合并会**追溯调整上年同期报表** ⇒ iFinD 年度值与公司公告同比**不可混用**；
中报分母问题见 detail §16.3。
⚠️ **`data_finance` 只给 `start` 不给 `end` 时 `num` 默认 1 ⇒ 只回 1 期**；要区间必须 `start`+`end` 都给。

### ★ 日线「上市以来全量」的正确取法（2026-10-15 实测，四层坑）

用户要求图表「数据要上市以来的所有数据」时走这条；**别用 iFinD 拿日线**。

| 环节 | 结论 |
|---|---|
| ❌ iFinD `get_stock_performance` | 只能拿逐日**前复权**收盘，且**按自然日填充 + 截断 ~100 行（无翻页 / 无 csv）** ⇒ 覆盖不了 5,897 个交易日，弃用 |
| ❌ 通达信 `tdx_kline` **`tqFlag=1`（前复权）** | ★★ **该数据已损坏**：24 年跨度下 2002—2005 年价格被调成**负数**（最低 −2.61）、日涨跌幅放大到 **+35% / −14%**。**弃用** |
| ⚠️ `tqFlag=0`（不复权） | 数值干净，但**除权日会被误读成暴跌**（600456 十送日 **−46.21%**） |
| ✅ **`tqFlag=2`（后复权）** | **正确答案**，是**正确的乘性复权**（同一除权日仅 **−3.14%**） |
| ★ 换算到「前复权」 | `前复权(t) = 后复权(t) × 不复权最新收盘 / 后复权最新值`（600456 因子 0.35298）⇒ 右端落在真实盘口价 |
| ★ **分页** | **每页固定只给 700 根**（`wantNum` 给 1000 也一样）⇒ 按 `startxh` 步长 **700** 递增翻页再合并去重；结果超 token 会**自动落盘**到 `tool-results/mcp-tdx-connector-tdx_kline-*.txt`，不占上下文 |

**EPS(TTM) 这类「阶跃」指标**：iFinD `get_stock_financials` 也是**按自然日填充 + 截断 ~100 行**，
且 `TTM基准日 ＝ 报表公告日期` ⇒ 序列**按公告日阶跃**。做法：**取「值发生变化」的日期当披露生效日**；
问不全就**按 5 年一段分批**要（600456 得 87 期）。

**换算工具**：`build/_merge_tdx.py` / `_merge_tdx2.py` / `_merge_tdx_hfq.py`（合并 + 后复权换算）。

---

## 2. 组装数据源

```bash
python3 batch_assemble.py <code> <名称> <行业> <省份>
# 例：python3 batch_assemble.py 000519 中兵红箭 地面装备 河南
python3 batch_assemble.py --batch 0 5      # 批量（按 seed/_todo_96.json 切片）
```

产出 `seed/data_v31_<code>.json` —— **这就是 31 个渲染器的入参**，字段即数据契约。

组装规则（`batch_assemble.py` 设计要点）：
1. 财务序列按**全部年份**输出（10 年口径）。
2. 可比公司从**板块内同 sub_industry** 自动生成，不足 3 家回退全板块。
3. **定性内容（行业 / 下游 / 管理层 / 护城河 / 多空）无一手来源的一律 `[MISSING]` + 获取路径，绝不编造**；
   能从财务推的（ROIC-WACC 利差、三档情景）由代码算。
4. 图表槽只有数据齐了才在 HTML 里放 `data-chart`。

**接下来人工补全** `data_v31_<code>.json` 里的定性块 —— 数据来自发现研报 + iFinD。
这一步是本流水线里**最花时间、最不能偷懒**的一步。

---

## 3. 渲染 31 模块

```bash
python3 report_build_v31.py <code>
# 批量：python3 report_build_v31.py --batch 0 30
```

- 输入 `seed/data_v31_<code>.json` → 输出 `seed/report_<code>.json`
- 逐槽取 `RENDER[no]`（由 `POS2RENDER` 决定），壳由 `build_shell()` 生成
- 收尾打印：`OK <code> <名称> 模块 31 · 图 N · 正文 M 字符 · [MISSING] K 处`
- **`assert` 红了就停下修数据，不要绕过**

`[MISSING]` 计数是质量指标：**定性内容没补完时它会很高**，要一路压下去。

---

## 4. 模块级版式统一（每份新研报都要过）

```bash
python3 mkmod3_std.py <code> --check       # 模块 3 股东结构
python3 mkchain_std.py <code> --check      # 模块 22 产业链全景图
python3 mkmod11_ring.py --check            # 模块 11 收入/毛利双环
python3 verdict_std.py --dry               # 核心结论版式（零丢失 + 幂等）
#    ★ 模块 25 的两张地图（世界 + 中国）也是**必配**（2026-10-14 锁死）：
#      在 data_v31_<code>.json 的 resource.world_map / resource.cn_map 里给数据，
#      report_build_v31.py 会自动出图（矿企储量 + 产量都要；化工农企用产量分布）
```

各自的规格文件：

| 模块 | 规格 JSON | 生成器 | 写库命令 |
|---|---|---|---|
| 3 股东结构 | `seed/m3std/m3_<code>.json` | `mkmod3_std.py` | `--write`（写 seed）/ `--push --go`（单模块补写库） |
| 22 产业链全景图 | `seed/chainstd/chain_<code>.json` | `mkchain_std.py` | 同上风格 |
| 11 收入/毛利 | 直接从 `data_v31` / seed 取 | `mkmod11_ring.py` | `--emit` 出图 / `--dry` 校验 |
| 核心结论 | `verdict_std.py::NEW[<code>]` | `verdict_std.py` | 默认写库 + 同步 seed |

**新研报的做法**：复制一份**最接近的**规格 JSON → 改数据 → `--check` → 目视 →
`--write`（随报告一起入库）/ `--push --go`（单模块补写）。

> 骨架与顺序**不要改**（见 `module-standards.md`），否则宝钛冻结范例就不再逐字节一致。

### ★★ 新研报的完整入库链路（2026-10-16 雪峰科技 603227 走通，照抄这套）

```bash
cd build
python3 report_build_v31.py <code>       # 1) 渲染 31 模块 → seed/report_<code>.json
python3 mkmod3_std.py   <code> --write   # 2) 模块 3  股东结构   ← 规格 seed/m3std/m3_<code>.json
python3 mkchain_std.py  <code> --write   # 3) 模块 22 产业链全景图 ← 规格 seed/chainstd/chain_<code>.json
python3 push_reports_v31.py <code>       # 4) 写库 + 备份 + 回读核对
python3 mkmod11_ring.py --only <code>    # 5) 模块 11 收入/毛利双环（先往 SPEC 里加条目）
python3 apply_eps_to_11.py --go <code>   # 6) 模块 29 头部插「EPS 与股价历史」双轴图 + 摘掉 m28 的 chartPrice2
python3 _norm_bold.py <code> --go        # 7) ★ `**` → <b> 归一（不跑＝页面上到处是字面星号）
python3 sync_seed_full.py <code> --go    # 8) ★ 收尾必跑：库 → seed
python3 build_report_single.py <code>    # 9) 离线单文件 → deliver/<名>-<code>-深度研究报告.html
```

**顺序铁律**

| 铁律 | 说明 |
|---|---|
| build 在前 | `report_build_v31.py` 会把 m3 / m22 覆盖回默认渲染 ⇒ 必须 **build → m3 → chain** |
| ★★ **重跑 build 会丢 `chart_eps`** | 那张图由 `apply_eps_to_11.py` 单独挂上去，**不在 `chart_opts()` 的产出里** ⇒ 任何一次 `report_build_v31.py <code>` 之后**都必须重跑 apply_eps**，否则 m29「EPS 与股价历史」整块消失，而且 `[MISSING]` 计数**不会**提醒你（2026-10-16 改 000762 时实踩）。同理 `mkmod11_ring.py` 的双环也一样。 |
| ★★ **`mkmod11_ring` 必须在 `push` 之后** | 该脚本**只 PATCH 库、从不写 seed**（已 grep 确认）。它在 push 之前跑，会被 push 用 seed 里的**单环** chartMix 覆盖掉。2026-10-16 修正了本文档早前写反的顺序 |
| ★★ **`apply_eps_to_11` 也在 push 之后** | 同理：它改的是库里的 m28/m29 HTML 与 `wb_report_charts` 行，跑在 push 之前会被覆盖。<br>★ 该脚本 2026-10-16 已加**幂等保护**（m29 已有 `chart_eps` 槽就跳过前插），所以可以安全重复跑 |

**四条收尾纪律**

| 事项 | 说明 |
|---|---|
| ★★ **第 7 步不能省（`_norm_bold`）** | 渲染器把正文按 markdown 习惯写成 `**加粗**`，而**壳里没有任何 `**` → `<b>` 的转换**（已 grep 确认）⇒ 不跑这一步，页面上**每一处强调都显示成字面星号**。603227 曾漏跑，线上残留 **1971 处**（其余 10 份为 0）。<br>★ 该脚本自带自检：换完必须**行内标签全配对 + 零残留 `**`**，任一处不过就整家跳过不写。<br>★ **可机检的收尾判据**（比事后看图快）：回读 `wb_report_mods` 的 31 个模块，`**` 计数必须 = **0** —— 2026-10-16 改 000762 时漏跑过这一步，线上残留 **1544 处**，直到看图才发现。<br>⚠️ `_norm_bold.py` 的 `ALL` 白名单只列了最早 10 家 ⇒ **新研报必须显式传 `<code>`**，否则静默不动。 |
| ★★ **第 8 步不能省** | `mkmod11_ring.py` 的 `data-ringnote`、`apply_eps_to_11.py` 的 m28/m29 改动、`_norm_bold.py` 的 `<b>` 全部**只写库**。不同步 seed ⇒ 下次 push 会把它们全刷掉 |
| ★★ **第 5 步要带 `--only`** | `mkmod11_ring.py` 原本每次都遍历全部 SPEC ⇒ 给新研报加条目后会**顺带重写其他 8 份**。已加 `--only <code[,code]>` 开关（**不加 = 原有全量行为**，向后兼容） |
| ★ 第 6 步的前置数据 | 需要 `seed/_eps_steps_<code>.json`（westock `data_finance` type=income 的 `EPSTTM` + `InfoPublDate`）、`seed/_tdx_<code>_hfq.json`（**日线必须止于 `<code>` 报告的数据截止日，不要把当天的盘中活口算进去**）、`seed/_raw_last.json` 里的 `<code>`。再跑 `_eps_opt.py <code>` 出 opt |

**`verdict_std.py` 通常不用跑**：新研报的核心结论直接按标准块手写即可
（`.vlead` 导语 / `.vkey` 判读 / `.vlist` 分点 / `.vrisk` 风险 / `.vtrack` 核心跟踪，按内容取用）。
`verdict_std.py` 的 `NEW[<code>]` 只服务于**存量研报里「一大坨纯文本」**的版式重排（带文字零丢失断言）。

---

### ★★ 喂给图表的数据块必须「列＝数值」（2026-10-16 雪峰 603227 踩过，一次踩五处）

**病根**：渲染器是**一份数据同时喂表格与图**（`table(head, rows)` + `chart(...)`），
`chart_opts` 再用 `numcol(rows, 列号)` 取数。作者若把某个数据块写成「讲人话的文字表」，
表格好看、**图却是空的**——而且 **`report_build_v31.py` 自检的「槽位 ↔ 图数据」是查不出来的**
（图在、数据在、只是每格都是 `None`）。

**唯一可靠的体检方法**：构建后统计每个 series 的 `None` 个数，**「整条 series 全 None」＝画了张空图**。

```python
# 全空系列体检（构建后必跑）
for c in seed['charts']:
    for s in c['opt']['series']:
        d = s['data']; n = sum(1 for v in d if v is None)
        if d and n == len(d):
            print('❌ 全空', c['id'], s['name'])
```

| 数据块 | 契约（列位固定） | 写错的后果 |
|---|---|---|
| `valuation.rows` | `[时点, PE, PB, 备注]` —— **列 1 数值 = PE、列 2 数值 = PB** | 写成「指标 / 数值 / 来源」三列文字表 ⇒ <br>① chartValuation **整图空白**；② m28「估值区间」表头硬编码 4 列 ⇒ 表也错位 |
| `pricecost` | 图用 `chart_rows`（**新键，2026-10-16 加**），表用 `rows`；格式 `[期间·品种, 均价, 单位成本, 单位毛利]` | 全写文字 ⇒ chartPrice **整图空白**。★ 渲染器已加 `numeric_rows()` 闸：三列里有一列取不出数就**整图不出**（连槽都不挂） |
| `resource.rows` | `[标签, 左轴值, …, 右轴值]` —— **列 1 = 左轴、列 3 = 右轴**；轴名走 `resource.axis_names` | 多插一列（如「英文名」）⇒ 数值列**整体右移**，chartResDist 左轴全 None、表格头行也错位 |
| `sdbalance.bal_rows` | `[标签, 数值, 占比, 说明]` —— **列 1、列 2 必须数值**（图表直接取这两列） | 写 `'**615.48 万吨**'` ⇒ chartSDBalance **整图空白** |
| `capacity.rows` | `[产品线, 产能, 产能利用率]`；★ 利用率**一个数值都没有**时渲染器会自动**不挂利用率轴与折线** | 7 行里只给 1 行数值 ⇒ 折线上出现**一个孤点**，看着像坏了。要么全给、要么全 `'—'` |

**通用规矩**

1. **凡是「图表要吃的列」，一律写纯数值**（可带 `**` 加粗标记 —— 渲染器已支持，见下）；
   单位写进表头（`产量（千吨氮含量）`），**不要写进单元格**（`'42,060 千吨'` ⇒ `numcol` 转 None）。
2. ★ **`numcol` 会剥掉的修饰**：`%`、千分位 `,`、`x`/`X` 倍数后缀、`**` 加粗标记。
   剥不掉的（`万吨` / `亿元` / `元/吨` / `—` / 中文词组）⇒ None。文字列请放**末尾**或**另外的键**。
3. ★ **「表格的列」和「图的列」需求不同时，就分键**（既有先例：`volprice.price_rows` / `pricecost.chart_rows`）。
   用 `xxx_rows` 专供图、`rows` 专供表，**并在 `chart_opts` 与模块渲染器两处用同一个判据**（否则一处建图一处不挂槽 ⇒ 页面留灰框）。
4. ★ **`resource.rows` 那一类「5 列」的母本口径**（600456）是 `[国家, 储量, 储量占比, 产量, 产量占比]`——
   **奇数列是数值、偶数列是给人看的百分比**，别把顺序调换。

---

### ★ 模块 22「产业链结构」的形状契约（`industry_note`，2026-10-16 踩过）

| 字段 | 正确形状 | 写错的后果 |
|---|---|---|
| `chain` | **字符串**（一段「上游→中游→下游」的定性描述） | 传 **list** ⇒ 页面里直接显示 **Python 列表字面量** `['天然气…', '合成氨…']` |
| `chain_head` | **4 列**：`环节 / 内容 / 公司参与度 / 备注` | 写 3 列 ⇒ 与「产业链定位」行的 4 个 `<td>` 错位、表格多出一列 |
| `chain_rows` | 每行 **4 格**（同上四列） | 写 3 格 ⇒ 同上错位 |

口径照 `seed/data_v31_603977.json` / `601958`。⚠️ **西藏矿业 000762 带同一缺陷（已上线，未修）**。

### ★ 产业链全景图（`chainstd`）的 `lint()` —— 新规格必跑

`python3 mkchain_std.py <code>`（**没有 `--check` 参数**，直接跑＝生成 + 报字数 + 与 seed 比对）
会跑 `lint()`，七项判据：

| 判据 | 阈值 |
|---|---|
| 节点标题溢出 | `汉字×13.5 + 其余×0.55×13.5 ≤ 宽−10` |
| 节点副行溢出 | 同式、字号 9.6，`≤ 宽−6` |
| 下游条溢出 | `≤ 宽−20` |
| 徽章相撞 | 同水平带内（`|Δy| < 19`）矩形相交 |
| 节点越出泳道 | 必须落在 `lane.x−2 .. lane.x+lane.w+2` |
| 超画布高 | `y+h+(带徽章 28) ≤ h−2` |

**画布与栅格（1040 × h，勿改）**：泳道横幅 `LANE_Y=12 / LANE_H=40`；上游 `x=19 w=366` ·
中游 `x=395 w=372` · 下游 `x=777 w=243`。节点 `104×48`，x 栅格 **19 / 147 / 275**（上游）、
**403 / 531 / 659**（中游）；y 常用 **94 / 125 / 156 / 176 / 228**；下游条 `213×24`，
`x=807`、y 自 96 起步长 31。徽章顶＝节点底 **+9**、高 19。

**边的语义**（`kind`）：`h` 右出直达目标左边；`v` 底中直下到目标顶；`t` 右出→到 `xm` 竖走→
汇入目标左侧（跨行用，`xm` 要给在空白列上）；`e` 从 `x0` 下走→到 `ym` 右行汇入目标左侧
（`x0` 用来避开自己的徽章；`ym` 必须落在目标节点的 y 区间内）；`fan` 分组括线到 `chips`。
**改坐标后要人工核位**（lint 只管溢出/越界，不管箭头有没有穿框）。

---

## 5. 写库

```bash
python3 push_reports_v31.py --all --dry    # 只备份 + 体检，不写库
python3 push_reports_v31.py <code>         # 备份 + 写库 + 回读核对
python3 push_reports_v31.py --all          # 全部
```

流程（脚本自动）：
1. 把线上现有研报整份导出到 `build/backup/report_<code>_pre_v31_<ts>.json`（三张表）
2. 逐份 upsert（`on_conflict=id` → `merge-duplicates`）
   - `wb_reports` 1 行（壳）
   - `wb_report_mods` 分批 6 条/次
   - `wb_report_charts` 分批 4 条/次
3. **回读核对**：模块编号必须 1..31 连续、图表 id 集合与 seed 一致 → 打 `✓` / `⚠`

三张表的关键字段：

| 表 | 主键 | 关键列 |
|---|---|---|
| `wb_reports` | `id`(=code) | `code name kicker title subtitle badges verdict_title verdict_html notice_html kpis kpi_note toc essence_html footer_html theme sort up` |
| `wb_report_mods` | `id` = `{code}_m{no}` | `report_id code seq no title html up` |
| `wb_report_charts` | `id` = `{code}_{chartKey}` | `report_id code seq name opt(jsonb) up` |

### ★★ seed ↔ 库 的双向纪律（2026-10-16 全库排查后固化）

**一句话：`push` 是「以 seed 为准、整份覆盖」的单向写入 —— 它从不回读库。**
⇒ seed 一旦落后于库，**任何一次 push 都会把线上的成果静默刷回旧版**（终端还打满 ✓）。
2026-10-16 全库体检：**13 份里 9 份都处于这个状态**（库里已有 m3 结构树 / m22 流程图 /
m29 EPS，seed 全都没有），000731 一度只差一次 push 就退化成「12 图旧版」。

**哪些脚本只写库、不写 seed**（跑完**必须**接一手 `sync_seed_full`）：

| 脚本 | 写什么 | 相对 push 的位置 |
|---|---|---|
| `mkmod3_std.py --write` | m3 股东结构树（`sh3-top`） | **之前** |
| `mkchain_std.py --write` | m22 产业链流程图（`iflow`） | **之前** |
| `apply_eps_to_11.py --go` | m29 EPS 段 + `chart_eps` 图行 | **之后** |
| `mkmod11_ring.py` | m11 双环 opt + 说明 | **之后** |
| `_norm_bold.py --go` | 模块正文 `**` → `<b>` | **之后** |
| `drop_chart_slot.py` | 摘掉模块里的图表槽 | 随时 |

```bash
python3 sync_seed_full.py <code> --go        # 写完库必须收回 seed
python3 sync_seed_full.py --all --go
```

⚠️ **`sync_seed_full.py` 的 `ALL` 是硬编码白名单** —— 新增研报**必须**同步往 `ALL` 里加 code，
否则 `--all` 会**静默漏掉它**（2026-10-16 已补上 `000762 / 600392 / 603227`）。

**★ 两道自动防线（2026-10-16 焊进脚本）**：

1. **`push_reports_v31.py` 的「seed 落后体检」**（1.5 步，自动执行）——
   若「库里有 `sh3-top` / `iflow`，而 seed 里**完全没有**」⇒ **拒绝 push**，
   并打印 `sync_seed_full.py <code> --go`。确认无误要强推时加 `--force`。
   ★ 口径：`**` 与 `chart_eps` **只作提示、不阻断** —— 前者在「重跑 build 后推送」时
   **必然**出现（build 产出 `**`、库里已被 `_norm_bold` 转成 `<b>`），
   后者在链路里本就晚于 push；拿它们当判据会「狼来了」，把真信号淹没。
2. **`report_build_v31.py` 的「data 完整性闸」** ——
   `data_v31_<code>.json` 顶层键 < 30（或缺 ≥3 个必需块）⇒ **拒绝运行**。
   因为该脚本结尾会**覆写** `seed/report_<code>.json`，用薄 data 重建会让
   m6/m7/m11/m12/m15/m26/m28 的表与图**一起消失、且不报错**。
   实测薄文件：**000731（25 键）/ 000830（24 键）/ 600456（12 键）** ——
   这三份**只能「改库 + sync」**，不要重跑 build。确认 data 已补全时加 `--force-thin`。

**★ 定期体检**：`python3 audit_reports.py`（13 份一次跑完，也可 `audit_reports.py 000731`）——
一次查出 8 类问题：seed↔库差异（并区分「只差 `**`」与「内容真不同」）、data 键数、
全空 series（并标注是「显示中」还是「孤儿」）、`[MISSING]`、槽位↔图对账、结构要件、`**` 残留。
**改完一批就该跑一次。**

### ★ `[MISSING]` 有三个来源，别一律当缺口

| 来源 | 位置 | 处置 |
|---|---|---|
| **真缺口** | 表格单元格 / 数据区 | 保留（这是设计意图） |
| **壳静态文案** | `#foot` / `#printNotes` / `notesModel()` | 探针另计为 `MISSING-shell`，**不算正文缺口** |
| **★ 正文文案里"提到"这个词** | 免责声明「未取到的字段一律标 [MISSING] 并…」、评分说明「标记为 [MISSING]」 | **改掉**（换「MISSING 占位」这种不带方括号的说法）—— 否则探针会把展示性文案计成数据缺口 |

★ 渲染器 `report_build_v31.py` 里的免责声明**早已**改成不带方括号；早先渲染的 7 份库里
留的是旧句。修法用 `build/fix_missing_wording.py`（`--go` 写库，随后接 `sync_seed_full`）。

### ★ 单改一张图 / 一个模块的做法（2026-10-15 范式）

| 要点 | 说明 |
|---|---|
| ★ **jsonb 会重排键序** | 回读核对必须**比「解析后的 dict」**，**比 md5 必假红**（`opt` 是 jsonb） |
| ★★ **图行删不掉** | `wb_report_charts` **无 `is_del` 列**、也不在硬删 RPC 白名单 ⇒ 写坏只能**改对** ⇒ **每次必先留快照** 到 `build/backup/<id>_pre_<ts>.json` |
| ★ **别用 `update` 怼整行** | 参考 `build/set_600456_chart_eps.py`：**干跑比对 → 快照 → PATCH → 回读比 dict**，四步一次做齐 |
| ★ **发布顺序防「新数据配旧壳」** | 渲染器/壳有改动时：**先发 `report.html`（新壳 + 旧 opt ⇒ 零可见变化），再写库新 opt** |
| ★ **顺序别搞反** | `report_build_v31.py` 重跑会**把 m3 / m22 覆盖回默认渲染** ⇒ 顺序必须是 **build → mkmod3 --write → mkchain --write → push** |

### ★ 只改图不改壳 ⇒ 不必部署

图表 opt 与模块 HTML 都只在库里（`wb_report_charts` / `wb_report_mods`），
**页面按 slot 名引用** ⇒ **改库即时生效，不需要部署 `report.html`**。
只有**改渲染器 / CSS / 模板**才要发壳。

---

## 6. 上线

研报**样式/模板**改动的上线（`report.html`）：

```bash
# ① 抓线上字节做基线（并发会话防护，见 deploy-verify.md）
curl -s https://liuchaowang.cn/report.html -o /tmp/base.html

# ② 构建 report.html（build.py 注入 WB_CFG，并在末尾**自动补 blockstyle**）
python3 build.py            # 或 build.py::build_report() 单独构建
# ⚠️ build.py 一跑会把 5 个产物全部重写 ⇒ 之后只发你真正改的那一个文件

# ③ ★★★ 确认报告页那两块「**不经模板生成**」的东西在（2026-10-16 固化）
#    线上 report.html = 模板渲染结果 **+** _patch_blockstyle.py 注入的：
#      <style  id="rpt-blockstyle">   模块堆叠文本分块 + 表格「红表头 + 浅蓝身」
#      <script id="rpt-blockscript">  配套渲染层（Markdown 粗体 / 数字列标注）
#    ⚠️ 这两块**不在模板里**。直发未补的 build 产物 ⇒ 产物少 39 753 字符，
#       **12 份研报的表格样式与粗体渲染同时失效，而且页面不报错**（只是全体「没样式」）。
#    ★ 好消息：build.py 末尾已自动补（patch_blockstyle()），会打印
#       「已补 rpt-blockstyle + rpt-blockscript：… md5=64e6ad9a…」
#       看到「! blockstyle 注入失败」⇒ **停手，别发**。
#    手工兜底（build.py 跑不了 / 想从线上字节重打）：
#       python3 _patch_blockstyle.py --base ../deploy/report.html --out /tmp/blk/report.html

# ③b ★★「严格超集」五步验证（2026-10-15 固化，防覆盖并发会话成果）
python3 probe_cssom_diff.py   # CSS 规则级 A/B：线上有·产物没有 必须 = 0
python3 probe_style_diff.py   # 逐元素 computed style：差异必须全是预期
# 还要逐 <script> 块比 md5（含 window.RPT_SEED 逐字节）—— 只允许本次改的那一块不同
# ★ 特征词表必须钉死 rpt-blockstyle / rpt-blockscript / rpt-txtstyle ——
#   上面两步量的是「规则 / 计算样式」，**整块标签消失**它们看不出来（2026-10-16 的教训）。

# ④ 核对待发文件
#    ⚠️ 产物**不要**拷进 deploy_site/ —— 那个目录会被并发会话静默回退（见 deploy-verify.md §2）
md5 -q ../deploy/report.html

# ⑤ 部署（★ 绝不带 --prune；★ 只发自己改的那一个文件，别整站发）
"$TCB" hosting deploy ../deploy/report.html /report.html --env-id "$ENVID" --verify
# 发完回读 md5，断言与待发逐字节一致（CDN 加 no-cache）：
#   curl -s -H "Cache-Control: no-cache" https://$DOM/report.html | md5
# 再抓线上真字节回跑探针：probe_report_mac.py <code>

# ⑥ 逐个 URL 验 200
for f in index.html report.html research.html datalib.html; do
  echo "$f $(curl -s -o /dev/null -w '%{http_code}' "https://$DOM/$f")"
done
```

**只改研报内容（写库）时不需要部署** —— 直接 `push_reports_v31.py`，
或跑 `verdict_std.py` / `mkmod3_std.py --push --go` 这类"只 PATCH 一行"的工具。

---

## 常见故障对照

| 症状 | 原因 | 处理 |
|---|---|---|
| 页面空白 / 数据没了 | `file://` 打开 ⇒ `Origin: null` 被网关 403，退化成内置副本 | 起本地 http（`http://127.0.0.1:<port>`）再验 |
| **多标的测出来数字一模一样** | **浏览器 URL 漏了 `?code=<code>`** ⇒ 回落硬编码的 600456 母本 seed | 抓字节和浏览器**两处**都要带 `?code=` |
| **折叠块点了展不开 / 某条 CSS 规则不生效** | CSS/模板**注释里写了裸的 `style`/`script` 标签名** ⇒ 解析器在 RAWTEXT 状态提前收表，该条规则被整块丢弃 | 改成不带尖括号的说法；跑 `python3 check_raw_tags.py` 守门 |
| **结论写库了、push 也 ✓，但页面没变** | 改的是 `conclusion.verdict`（**死字段**） | 改 **`shell.verdict`**，推完回读 `wb_reports.verdict_html` |
| **表格右边溢出 / 行高虚高** | 表头被 `white-space:nowrap` 锁死 ⇒ min-content 撑破容器、标签列被压成竖排 | 见 `frontend-style.md` §7；量溢出用 `probe_table_fit.py` |
| **改了样式但没生效** | 改动**不在取材范围内**：`_patch_txtstyle.py` 是「从自己 MARK 抽到**文件尾**」；`_patch_blockstyle.py` 则读**整份** `block_style.css` 并带裸标签断言 | 先问「这段在不在取材范围内」；**表格 / 装饰类一律走 `block_style.css`** |
| **页面里星号 `**` 清不掉** | 清除器 `SKIP` 白名单含 `B/STRONG`，而数据里粗体是嵌套包裹的 | 见 `frontend-style.md` §1.2 |
| 表格不换行 / 溢出（通用） | flex 子项 `min-width:auto` | 等分 N 列写 `flex:1 1 0;min-width:0` |
| 改了模块但页面没变 | 改的是产物不是种子 | 改 `data_v31_<code>.json` / 生成器，重跑 `report_build_v31.py` |
| 改了库又被刷回 | seed 没同步 | 两处都要改（见上） |
| 图表 tooltip 报错 | 只发了几何图没发 `report.html` | 环图/时间轴改了必须**同时发 report.html** |
| **改动上线后几小时又变回去了** | **并发会话用旧基线整块回退** | 见 `deploy-verify.md` §2：产物别写 `deploy_site/`、发前重 `curl`、发后立刻复验 |
| **撤不回原来的线上版本** | 想「改回渲染器 + 重建 seed + 推库」 | ⛔ **绝对不行** —— 线上模块 HTML 早已与 seed 脱钩。只能用 `build/rollback_from_backup.py` 从写库前备份回滚 |
