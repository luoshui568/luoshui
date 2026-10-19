# 洛水研报模版 · 前端样式与页面

> **改表格 / 文字 / 配色 / 列表页 / 资料库，以及排查「样式不生效」时读这份。**
>
> - 表格与装饰样式源：**`build/block_style.css`** ＋ **`build/block_style.js`**
>   （注入器 `build/_patch_blockstyle.py`）；⚠️ `build/report_theme.css` 会被并发会话整份重写。
> - 相关：`hard-rules.md` §三（版式要求）· `deploy-verify.md`（上线纪律）

---

## 1. 纯文字模块版式（分块 + 表格色块 + 正文字色）


**三块独立标签**（不是 `report_theme.css`，2026-10-15 起注入器同时管 style + script 两块）：

| 块 | id | 生成器 | 顺序 |
|---|---|---|---|
| 堆叠文本分块 + **宣纸墨金表格** + 宣纸背景层 | `rpt-blockstyle` | `build/_patch_blockstyle.py`（CSS 源 = **`build/block_style.css`**，⚠️ **不要放回 `report_theme.css`**，会被并发会话整个重写） | ⚠️ **必须排在「可读性版式」之前** |
| **`**`→`<b>` + 数字列右对齐 + essence 分块 + 背景层注入**（⭐ 会整块被删，发完必复查 md5） | `rpt-blockscript` | `build/block_style.js` | 同一份注入产物，紧随 style |
| 正文可读性版式 | `rpt-txtstyle` | `build/_patch_txtstyle.py`（支持"已有该块 ⇒ 整体替换"） | 在后 |

### 1.1 表格终版：**宣纸 · 墨金**（2026-10-19 用户令「学习这个样式改研报的背景和表格，不要动内容」，已上线 md5 `c25d3272`）

⚠️ **版式演进史（别走回头路）**：
`大红金块` → `现代细线·无斑马纹`（曾上线 `3359af5d`，用户观感「跟没上样式一样」）
→ `品牌装饰·斑马纹回归`（`112bcca2`）→ `全浅蓝`（`b602084c`）→ `红表头 + 浅蓝身`（`be6b41e9`）
→ **`宣纸 · 墨金`（`c25d3272`，当前线上）**。曾短暂试过粉色，未采用。

**设计依据**：用户指定参考稿 `capital-table.html`（中式复古「宣纸 · 墨金」）。
整站底色由**冷蓝**转为**暖纸**（`#f5f1e8`），表头因此**不能再亮红** ——
亮红 `#e43644` 压在米纸上会「跳」出纸面；改为**深酒红四段渐变 + 金色发丝线**，
与纸面构成「朱砂印 + 金线」的关系，同时保留「表头是唯一定位锚点」的功能色地位。

**整站色板（参考稿实测）**：

| 组 | 值 |
|---|---|
| 墨（正/次/辅） | `#14100e` / `#2a2422` / `#4a423e` / `#6b6259` |
| 纸（底/次/卡） | `#f5f1e8` / `#efe9dc` / `#fbf8f2` |
| 朱砂（主/亮/深） | `#8b1a1a` / `#a82020` / `#c0392b` |
| 金（主/亮） | `#a8862c` / `#c9a227` |
| 线（浅/深） | `#d8d0bf` / `#c4b9a3` |
| 涨 / 跌 | `#a82020`（红） / `#2e7d5b`（绿） —— **中式口径：涨红跌绿** |
| 字体 | 标题 serif `"Songti SC","SimSun"`；表头/正文 sans `"PingFang SC"` |

**保留的现代骨架七条**（从第二版继承）：只留横线去竖线 / 圆角收在容器靠 `overflow:hidden` 裁 /
`padding:12px 16px` + `line-height:1.72` / 表头字 11.4px + `letter-spacing:.12em` / `white-space:nowrap` /
hover 只改底色不动阴影 / 品牌红交给模块标题条与结论块。

**当前五层装饰**：

| 层 | 内容 | 色值 |
|---|---|---|
| D1 | 表头**行**整行**深酒红四段渐变** + `<th>` 底部**金色发丝线** + 米白字 | `linear-gradient(100deg,#751111 0%,#a82020 42%,#8b1a1a 74%,#6e1414)` / `th` 上 `border-bottom:1px solid rgba(201,162,39,.55)` / 字 `#f7efe1` |
| D2 | 表格容器暖灰描边 + 12px 圆角 + 暖调双层投影 | 边框 `rgba(196,185,163,.7)`，圆角 **12px**，底 `rgba(251,248,242,.94)` |
| D3 | 首列宣纸渐变 + `700` 墨色 + 左侧 3px 淡朱砂小柱 | `linear-gradient(100deg,rgba(245,241,232,.98),rgba(239,233,220,.88) 62%,rgba(245,241,232,.7))` / `inset 3px 0 0 0 rgba(139,26,26,.3)` / 字 `#14100e` |
| D4 | 斑马纹（半透明米纸 ↔ 纸白） | `rgba(245,241,232,.62)` ↔ `rgba(255,253,248,.92)` |
| D5 | 行分隔线 | `rgba(216,208,191,.65)` |

**列表**：`.card > ul` 变 grid（`gap:10px`），`li` = 宣纸渐变底（`#fdfbf6 → #f9f4e9 52% → #f2ebdb`）
+ 边框 `#ded4bf` + **4px 金→朱砂渐变伪元素左柱**（`#d9b45c → #c9a227 44% → #a82020`）；
渐变做不出 `border` 渐变 ⇒ `border-left:0`、右上圆角 13px、左上 0px；
列表后那段 `p` 变「小结块」（更深一档底 + 红柱 `#a82020 → #8b1a1a → #c9a227`）。

**背景＝四层叠加**（CSS 只能画出两层，另两层在渲染层）：

| 层 | 实现 | 要点 |
|---|---|---|
| ① 底色 + 三团径向柔光 | `body{background-image: radial-gradient(...)×3, linear-gradient(...)}` | `background-attachment: fixed,fixed,fixed,scroll`；**`html` 也要刷 `#f5f1e8`**（`body` 带 `overflow-x:hidden`，滚到底会露 html 底色） |
| ② 网格 | `#rpt-paper .rp-grid`：56px 双线 + 径向遮罩淡出 + `rptGridPulse` 18s | 线色 `rgba(139,26,26,.062)`；遮罩 `-webkit-mask-image` |
| ③ 光球漂移 | 复用页面已有的 `.bg-orbs`，**只换色不改定位** | 四球必须全部换：`#8b1a1a/.055` · `#c9a227/.13` · `#8b1a1a/.045` · `#a8862c/.11`；⚠️ 第 4 颗原是冷蓝 `#00b0f0`，**漏改就是满页唯一的冷色** |
| ④ 尘粒 | 渲染层 `makePaperBg()` 注入 26 颗 `.rp-pt`，随机尺寸/时长/负延迟，`rptRise` 上升 | `#rpt-paper{position:fixed;inset:0;z-index:0;pointer-events:none;contain:layout style paint}` |

⚠️ **`contain:strict` 不能用** —— 它含 size 约束，`fixed + inset:0` 在部分 WebKit 会退化成 0 高度 ⇒ 用 `layout style paint`。

**整站换色器改为可关**：③ 段 `fixGold`（HSL 判定金色 → 保持 L/S 搬到 205° 蓝）在宣纸风里**必须停用** ——
金色此时是主色，搬走会毁掉整个配色。JS 顶部加 `var RETINT = false;`，调用点写
`if (RETINT) fixGold(document.body);`（函数体与 HSL 工具完整保留，将来要换色改回 `true`）。

⚠️⚠️ **每条都要 `background-image:none`**：老规则是 `background:linear-gradient(...)` 简写，
只写 `background:<颜色>` 的话**旧渐变图会留着**（渐变优先级高于底色）—— 漏这条就会看到「改了没生效」。

⚠️⚠️ **三个必踩的坑**：
- **多层 `background-size:100% 3px,100% 100%` 在 `<tr>` 上不按预期生效**（第一层被当 100% 100% 铺满整行）
  ⇒ `<tr>` 上**只画一层背景**最稳，底线走 `inset box-shadow`（box-shadow 不吃渐变）。
  **表头渐变必须画在 `tr:first-child` 上、`<th>` 自身透明** —— 红底若每个 `<th>` 各画一遍
  100° 渐变，四列表会变成四段深浅不一。
- ★★ **金色下边框只能写在 `<th>` 的 `border-bottom`，不能写 `<tr>` 的 `inset box-shadow`**：
  本版 `border-collapse:separate` + `border-spacing:0`，box-shadow 无法跨单元格连成整条线
  ⇒ 每格各画一截，格间留 0.5px 缝，放大看是「虚线」。全表的盒子阴影用来做容器投影即可。
- ★★ **半透明斑马 + 半透明分隔线时，探针必须逐字比整串 `rgba(r, g, b, a)`**：
  本版每个色值都带 alpha，只比前三通道会漏掉「透明度被改」这种回归。
- **任何行级配色叠加前先比特异度**：斑马纹若写 `tr:nth-child(even) > td`（0,2,4）
  会盖掉首列的 `tbody td:first-child`（0,2,3）⇒ 现象是**「隔行颠倒」**（首列底色时有时无）。
  修法：斑马纹写 `td:not(:first-child)` 排除首列，首列升到 `tbody tr > td:first-child`。
- ★★★ **未闭合的 `<style>` 会连带吞掉后面所有 CSS（含本块）**：
  线上曾出现 `<style` 3 个 / `</style>` 1 个，病根是别的块在注释里写了
  `<style id="rpt-txtstyle">` **字面量**而没闭合 ⇒ 浏览器按「第一个 `</style>` 收尾」，
  从那里往后 8.8 万字符（含本块）全被当成第一张表的 CSS。
  症状：`getElementById('rpt-txtstyle')` 返 null **且本块样式永远不生效**。
  `_patch_blockstyle.py` 的 `heal_unclosed_style()` 只在**缺口恰为 1 且能找到
  `rpt-txtstyle` 界标**时补闭合，否则不动（交还对方会话）。

### 1.2 ★★ `**` 星号：渲染层修，**零写库**（2026-10-15）
全库曾有 **1,693 处未渲染的 Markdown 粗体 `**`**（`000762` 1,449 / `600392` 244 / 共 56 个模块；
`002408` 另有 2208 处）—— 页面上**直接显示星号**，是「土」的头号来源。
`build/block_style.js` 在渲染层把 `**文字**` 换成真 `<b>` ⇒ **研报数据一个字不动**。
效果：`<b>` 121 → 837，`**` 残留 0。附带：纯数字单元格打 `is-num` → 右对齐 + `tabular-nums`。
**写新研报时**：内容里的强调直接写 `<b>`，别写 `**`。

★★ **白名单 `SKIP` 绝不能含 `B` / `STRONG`**（2026-10-15 踩死一次）：
研报数据里粗体是**嵌套包裹**的（`<b><p>**…**</p></b>`、整张表被裹进 `<b>`），
`badParent()` 一旦在祖先链上遇到 `<b>` 就整节点跳过 ⇒ **002408 m6 的 104 个星号一个都没换掉**
（此前误判成「数据固有现象」，其实是 bug）。
**诊断法**：遍历含 `**` 的文本节点，打印**祖先链**（`P > B > DIV.card`），一眼看出是谁挡的。
**修法**：`SKIP` 去掉 `B/STRONG` + `convert(txt, plain)` 加参数 ——
父节点已是 `<b>/<strong>` 时 `plain=1`，**只去星号留纯文本**（粗体由外层提供，不再套一层 `<b>`）。

### 1.3 ★ 一句话本质（`.essence`）：长段 → 分块卡片（2026-10-15，已上线 md5 `8f85f2b9`）

用户给两张图：图1 `.essence`「看着太乱」、图2 `.verdict` 是目标版式。
⇒ **通则：遇到「A 太乱，要 B 那种」先判断病根是配色还是结构** —— 这次是**结构**
（一整块 19px/700 白字长段，700+ 字零层次），解法不是调色，是**抄 `.verdict` 的骨架**。

**最终版式**：白底 `#fffdf9` + 顶部 3px 红→金渐变压条（与 `.verdict::before` 同一条）
+ 左侧 4px `#c8102e` 柱 + 14px 圆角；`.et` 13px 红字 + 红小方柱；
`.ec` 从 **19px/700 白字降到 14.6px/500 深墨 + lh1.98**（长段可读的前提）；
`.ebk:first-child` = 浅粉导语块 + 左红柱（对应 `.vlead`）；
`.ebk + .ebk` = 米底卡片 + **红色圆形序号**（对应 `.vlist>li::before`）。

**渲染层 `splitEssence()`（零写库）**：把 `.ec` 顶层 inline 序列切成 `.ebk`。
- ★ 切点 = **顶层 `<strong>`/`<b>` 的起始位置**。强标记是数据作者自己标的**语义转折点**
  （「而 2025 年…」「这个反差就是…」「可证伪命题是：」「本报告已能回答…」）⇒ 天然边界。
  **绝不按句号硬切** —— 会把「…的央企资源公司：扎布耶盐湖独占 298.5 km²」这类固定搭配拦腰截断。
- ★ **短段合并**（MIN=26 字）：连续强标记会产出碎片段（「西藏矿业是」5 字、「——」），
  规则 = 不足 MIN 且非末段 ⇒ **并入下一段**；末段不足 ⇒ 回并上一段。
  **只拼 DOM 节点，文字必须逐字守恒**（探针要量 `全文字数 == 各块字数之和`）。
- 守卫三条：`data-ebk="1"` 幂等 / 总长 ≥180 字 / 顶层强标记 ≥2 且**顶层只有 inline 标签**
  ⇒ 没容器的**裸 `<b>` 形态**（002408 / 603599 的 essence 没有 `.essence` 容器）自动跳过，不越界。
- ★ **调度顺序**：`fixBold` → `markNum` → `splitEssence` → `fixGold`
  （`**`→`<b>` 必须先落地，否则找不到切点）。

⚠️ **深色 banner 改浅色卡要关三样**：`background-image:none`（老规则是渐变简写，
只写 `background:<色>` 会残留渐变图）、`animation:none`（底色漂移）、
`::after{content:none}`（白色高光扫过）。打印需 `print-color-adjust:exact`。

**实测切分**（`shell.essence` 全长守恒）：000762 → 5 块（104/40/114/306/133）、
600392 → 5 块、601958 → 4 块、603977 / 601118 → 各 2 块。
修后 m6 星号 104 → 0。

**正文字色终版 `#4a423e`（暖墨灰）**（宣纸版，落在 `.card > p:not(.src):not(.muted)`、
`.card > ul > li`、`.logic .lv`），深字 `#14100e`（首列 / 时间轴标题）。
⚠️ 上一版是冷蓝灰 `#4d5f6d`（`#243642` 深字）—— 换宣纸风时**必须一起换**，
否则暖纸底上会浮一层冷色字，整页像拼贴。小标题也是同理：`.card > h3` 由蓝改
`color:#8a5a12` + 米金底 `linear-gradient(120deg,rgba(201,162,39,.13),rgba(201,162,39,.025))`
+ `border-left:3px solid #a8862c`。

选择器边界：
- 列表一律 `.card > ul`（**直接子代**，28 处）；`.grid2` 内 10 处 / `m3 .sh3-ul` 11 处**不碰**
- 表格 `.card table`（后代）；全站 547 张表 / 38 处 `<ul style>` 内联 ⇒ **全要 `!important`**
- 导语块选择器**只能** `.card > .rpt-ops + p`（`p:first-child` 匹配不上）+ 必须 `:not(.muted):not(.src)`
- ★ 覆盖并发会话的硬编码色时**靠重复选择器抬特异度**（`.card.card > h3` = 0,0,2,1）

工具：选色 `_preview_bodycolor.py`（**必须给克隆节点套 `.pv0` 包裹层**，漏了 = 假绿）、
对比出图 `_shot_gray_ba.py` / `_shot_list_ba.py` / `_sheet_list_ba.py` / `_shot_block_ba.py`、
普查 `_scan_lists.py` / `_dump_near_black.py` / `_scan_text_colors.py --paths`。
验收：`probe_blockstyle.py` / `probe_txtstyle.py`（量**计算样式**）。
⚠️ **`probe_blockstyle.py` 要跑 PIL 的脚本请用 venv**：
`$PYV`（系统 `python3` 没 PIL；`$PYV` 见 `SKILL.md` ★ 环境配置）。

★★ **`probe_blockstyle.py` 换配色版要同时改三处**：**期望值常量区 + JS 采集段 + 断言/输出**，
只改常量区 ⇒ 跑出来全红（还会因引用已删常量直接 `NameError`）。

⚠️ 探针**等待时间要 9s**（不是 5s）：模块是**异步**渲染的，
`DOMContentLoaded` 时 `#mods` 已存在但**还是空的**，实测首屏要 3~4 秒才灌进 341 个模块。

⚠️ **三条读数纪律**（写断言前必须知道，否则必误报）：
- **渐变底色下 `getComputedStyle().backgroundColor` 返回透明**（渐变在 `background-image` 上）
  ⇒ 判底色必须看 `background-image`。表头行与首列都是这个情况；
- 半透明阴影读数是 `rgba(45,129,190,.55)` 而非纯 rgb ⇒ 断言匹配 rgb **前三通道**；
- 本站表格是**裸 `<tr><th>`（没有 `<thead>`）** ⇒ 表头只能靠 `tr:first-child`，
  且 `th` 自身必须透明（底色与底线都画在 `tr` 上）⇒ 断言 `th` 的 `background-color` 为透明。
  取「第二列」用 `tb.querySelectorAll('tbody td')[1]`，
  **不能**用 `tbody tr:first-child td` —— 表头那行是 `<tbody>` 第 1 个子元素且用 `<th>`。

⚠️ **环境噪声（不是 bug，别去越界修）**：线上 `<style` 3 个但 `</style>` **只有 2 个** ——
模板自带那个无 id 的 `<style>` 未闭合，把 `rpt-txtstyle` 整块当 CSS 文本吞了
⇒ `getElementById('rpt-txtstyle')` 返回 **null**（探针里 `rpt-txtstyle=0` 属正常），
但样式**仍生效**（被解析进同一张表）。属并发会话的地盘。
★ 但若本块样式也因此**不生效**，就不是噪声了 —— 用 `heal_unclosed_style()` 补上闭合。

★★ **并发会话会整块删掉已上线的 `<style>`/`<script>`**（本项目发生过多次，
最狠一次把 `rpt-blockstyle` + `rpt-blockscript` 全删 ⇒ 页面所有装饰与 `**` 修复一起失效）。
**诊断抓手**：量 `window.__rptBlockApi` —— `undefined` 就说明脚本块不存在或没执行，
**别去查 CSS**（那时 CSS 也是一起没的）。
**每次部署后 / 下次开工第一步都要 `curl` 复查 md5**，光看探针「全绿」不够
（探针只查本块在不在，查不出「谁把它删了」）。

---

## 2. 样式注入顺序（改 CSS 前必须知道）


`report_theme.css` 由 `/*__REPORTCSS__*/` 占位符注入，**位置在模板自带样式之前**：

```
/*__REPORTCSS__*/   ← build/report_theme.css 注入在这里（最前）
…模板自带的 .rpt-* 规则…   ← 在后面
⇒ 同特异性时，模板自带的规则赢
```

**要覆盖模板自带样式，`report_theme.css` 里的规则必须更高特异性或加 `!important`。**

### ★★ 两块「不进模板、只能靠 patch 存在」的东西（2026-10-16 固化）

线上 `report.html` 里叠着两块**模板里没有**的内容 —— 只有 `build/_patch_blockstyle.py` 会写：

| 块 | 来源文件 | 内容 |
|---|---|---|
| `<style id="rpt-blockstyle">` | `build/block_style.css` | 模块堆叠文本分块 + 表格「**宣纸 · 墨金**」+ 宣纸背景层 |
| `<script id="rpt-blockscript">` | `build/block_style.js` | Markdown 粗体 / 数字列右对齐 / 长文块分拆 |

⚠️ **直发未补的 `build.py` 产物 ⇒ 两块一起消失**（少 **39 753 字符 / 928 行**），
**12 份研报的表格样式与粗体渲染同时失效，而且页面不报错**（只是全体「没样式」）。

★ 自 **2026-10-16** 起 `build.py` 末尾**自动补**（`patch_blockstyle()`，紧跟 `build_report()`）——
看它打印的「已补 rpt-blockstyle + rpt-blockscript：… md5=64e6ad9a…」；
出现「! blockstyle 注入失败」⇒ **别发布**。手工兜底与「为什么严格超集查不出来」见 `deploy-verify.md` §3。

---

## 3. 研报列表页（`research.html`）的评分块


用户令：「这种显示帮我改成研报里评分那套，加简单介绍包括当年营业收入净利润这些」。

- 卡片底部原来是「verdict 摘要文字」（`.sum`，3 行截断），现换成**评分块 `.scard`**：
  左＝环形总分（`conic-gradient` 外圈 + `::before` 白内圆遮罩，与研报内 `.gauge` 同源）、
  右＝评级胶囊 `.srate`（按档位换色）+ 三行关键财务（营收 / 归母净利 + 同比 / 毛利率·ROE）
- **无评分数据时回落**成原来的摘要文字 ⇒ 老研报不受影响
- ★★ **2026-10-15 三处修正**（用户报「右边两个评分显示不全 / 左边这个不规范」，
  **两个问题两个完全不同的根因，都不是 CSS**）：
  1. **「显示不全」= 关键词精确匹配整格落空**。`kpiOf(r,'营业收入')` 走
     `label.indexOf(...)` 精确匹配，但各研报 label 口径不统一 ——
     老研报写「营业收入（2025）」、**000731 / 000830 写「2026H1 营收」**（只有「营收」两字）
     ⇒ 整格消失（出来 2 格 / 1 格，混在一排 4 格里就是"显示不全"）。
     ⚠️ 顺带发现 **600456（母本）也缺毛利率 / ROE 两格**，只是没人提。
     **修法**：`KPI_KW` **同义词表**（rev / npf / gm / roe 各一组词，**长词必须排前面**）
     + `canonLabel()` 把磁贴标签**强制归一**成四个标准名
     （否则一排卡片上并存三种写法，数值起始位置对不齐）
     + 指标格**恒定 4 格**，缺项渲染 `.kv.na`（虚线浅底 + 淡「—」）⇒ 位置永远对齐。
  2. **「不规范」= 该研报根本没评分，被当成"解析失败"**。m29 **存在 ≠ 已评分** ——
     000762 的 m29 内容里是 `<span class="tn">—</span>` / `<span class="tt">待评分</span>`，
     `parseScoreHtml` 的正则要求数字 ⇒ 匹配不上 ⇒ `return null` ⇒ 卡片回落到 `.sum` 长摘要
     ⇒ **被 `-webkit-line-clamp:3` 拦腰截断**（末行只露上半截）。
     **修法**：识别「无数字但写着待评分」⇒ 返回 `{total:0, rating:'待评分', pending:true}`，
     出**灰环骨架**（`conic-gradient(#e6d5d9 0 100%)` + `—/100` + 「尚未评分」），
     `.scard.pend` 降饱和。★ **不改库、不伪造分数** —— 它确实没评分，那是数据的真实状态。
  3. 两者叠加才像"显示不全"：格数不足 + 长摘要被截 + 灰环退场。
- ★ 探针 `build/probe_research_score.py`（**46 项**，量真实 DOM；`SRC=` 换被测文件）。
  判据：① 有评分卡的格数分布必须是 `{4: N}`；② 四格标签严格等于
  `['营业收入','归母净利','毛利率','ROE']`；③ 值是「—」的格必须带 `na` 类；
  ④ 待评分卡必须 `hasSum=False` + 灰环 + 4 格；⑤ 已评分卡红刻度必须在（防改过头）；
  ⑥ 无 m29 的仍走摘要回落（向后兼容）。
  **正反对照**：修复前字节 → `格数分布 {4:8, 2:1, 1:2}`、**恰好 4 项红**；修复后 → `{4:12}` 全绿。
- ★ **评分不存库、不加冗余列**：前端**并行补拉 m29** 解析
  `fetch(REST + 'wb_report_mods?select=report_id,html&no=eq.29')`，
  用 `parseScoreHtml()` 取 `sc-total` 块里的 `.tn` / `.tt`。
  失败不拖垮列表（内部 catch 成空数组）。**加冗余列必然与 m29 打架。**
- ⚠️ **改 `research.html` 必须同步 `deploy/research.template.html`**；
  `build_research()` 会覆盖产物，**批量替换前先另存 `/tmp`**。

---

## 4. 研报页「📂 公司资料库」（上传 / 查看 / 下载 / 删除）


- 前端入口：`Rpt.files()`
- 对象存储：pgstore 桶 `company-files`（公开读、匿名可写）
- 元数据：`public.wb_company_files`（**只授 SELECT/INSERT/UPDATE，删一律软删**，
  走 RPC `wb_del_company_file`）
- 上传流程：大文件预检（`F_MAX` 80MB）→ 密码门 → **串行**传（才有逐项进度）
- **CSS / DOM / JS 全在模板里**（`deploy/report.template.html`，**不在 `report_theme.css`**）

⚠️ **改这块必须同时发 `report.html`**（`.vpdf/.vhint` 与 `Rpt.closeView/closeFiles` 都在页面里）。
⚠️ 空柜时 `fStat('')` 会剩一圈空红边 ⇒ 靠 `.rpt-fbox .hd .stat:empty{display:none}` 整枚收掉。
⚠️ pgstore 对象**已存在时 POST 返 409，用 PUT 覆盖**；匿名 key **删不掉**对象（DELETE→403）。
⚠️ 验「匿名能不能删对象」不能拿一个**不存在的** key 试（网关先查存在性回 404，走不到 RLS）；
要先传一个一次性对象再拿匿名身份删。
⚠️ 素材规格 `FILES` 是 **Python 单一来源**，注入成 `__FILES__` 给页内 JS，断言读同一份。
⚠️ 探针 `probe_comfiles.py`（86 项；`WB_PW=xxx --full`），截图 `_comfiles_shots.py`。

---

## 5. ★★★ 样式表「腰斩」——一个不报错、只能靠实测才发现的坑（2026-10-15 已上线修）


### 现象
解读块（`.logic`）**点标题展不开**：胶囊从「展开 ▾」变成「收起 ▴」，但正文不出来。
`getComputedStyle(lv).display` 恒为 `none`。**页面不报任何错**，控制台干净。

### 根因
`build/report_theme.css`（**唯一整份注入页面样式表块的源文件**）里一句**注释**写了
带尖括号的标签名：

```css
/* ⚠️ 这里故意不写 color —— 正文色统一由 report.html 里那支独立的
   `<style id="rpt-txtstyle">` 的 `.logic .lv{color:…}` 定 */
```

这段注释被原样注入样式表块后，浏览器处于 RAWTEXT 状态，遇到游离的收表标记
就**提前结束这张样式表**；注释与紧随其后的

```css
.logic.on .lv{ display:block; ... }
```

被当作「表外文本」，**该条规则连同声明块被解析器整体丢弃**（下一条规则起恢复正常）。
巧合的是被丢的正好是「展开态」那一条 ⇒ 表现成「只有折叠块坏、别处都正常」。

### ★★ 最容易走错的一步：别按行数估损害
我一度按「腰斩点之后剩 1080 行 / 占全文 73%」推断**386 条规则全失效**，**是错的**。
CSSOM 实测（`build/probe_cssom_diff.py`）：线上实际解析到 **803** 条、
修复后 **810** 条 ⇒ **真实伤害只有 1 条**。
原因：被截断的 CSS 文本会**另起一张样式表重新解析**，规则并没有整段丢失。
⇒ **受损条数只能用 CSSOM 实测，「行数 / 字节占比」不是判据。**

### 修法 + 守门
1. 该注释改写成**不带尖括号**的说法：「文本色样式块（id=rpt-txtstyle）」。
2. 守门工具 `python3 build/check_raw_tags.py` —— 扫 `report_theme.css` 与各
   `*.template.html` **注释里**的裸 `style` / `script` 标签名（正常开闭标签成对，放过）。
   **正反都验过**：故意写回裸标签 → 报红并指出行号；改回 → 绿。
3. 铁律：**这个文件里绝不允许出现裸的 style / script 标签名**。

### 顺带记牢：`_patch_txtstyle.py` 的取材范围
它只从 `report_theme.css` 的 MARK「模块正文「可读性」版式」**抽到文件末尾**。
⇒ **写在 MARK 之前的 CSS 永远不注入线上**（`build.py` 的产物里有、线上没有）。
本次 `is-txt` 规则我第一次就写在了 MARK 之前（第 1400 行，MARK 在 1452 行），
探针量到「打标成功但 `align` 还是 `start`」才发现，已搬到 `build/block_style.css`。
**判定口诀：改动要上线，先问「这段在不在取材范围内」。**

---

## 6. ★★ 三条「观感类」需求的处置（2026-10-15 用户令，均已上线）


| 用户原话 | 真实情况 | 做法 |
|---|---|---|
| 「这里右边溢出了，一行的文字太多了就还行居中」 | 表**没溢出**（`scrollWidth == clientWidth`）。是长文本折行后**顶到列边缘**的观感 | 渲染层给「中文 ≥14 字」且非数字的格打 `is-txt` → `text-align:center`（`block_style.js` 的 `markTxt`）。**数字格保持右对齐**（要对齐小数点），实测 57 格居中 / 576 格不变 |
| 「1 位置重复了」 | **不是 bug**。模块 23 用 `grid2` 并排两张图（chart4 海绵钛价格 / chart8 全球海绵钛产量），点数都 ≥5 ⇒ 各插一组「3年/5年/10年/全部」；窄屏塌成单列后上下紧贴 | 只加**视觉分隔**：`border-bottom` 淡线 + 组间距。判据：`chart4@N` 与 `chart8@N` 的 toolbar top 完全相同、`St.slots` 无重复 key ⇒ 两组都该在 |
| 「收起展开不显示了」 | 见 §5 样式表腰斩 | 修注释 |

**教训：用户的「观感描述」不等于「技术事实」**。「溢出了」要先量
`scrollWidth/clientWidth`、「重复了」要先查是不是两个真控件 ——
量完再决定「修 bug」还是「改观感」，别照着描述直接改代码。

### 相关探针（可复跑）
`build/probe_three.py`（表溢出 + 长文本居中 + 工具栏重复）·
`build/probe_logic.py`（折叠块 22 项，含打印模式）·
`build/probe_istxt.py`（`markTxt` 判据分流）·
`build/probe_toolbar_dup.py`（工具栏归属）·
`build/probe_cssom_diff.py`（CSSOM 级 A/B）·
`build/probe_style_diff.py`（逐元素 computed style A/B）·
`build/check_raw_tags.py`（裸标签守门）。

---

## 7. ★★★ 表格「右边溢出 + 行高虚高」——判据与修法（2026-10-15 已上线）


### 现象（用户原话）
「这个溢出还是没有解决，而且这个表格行高太高了，**选择换行显示**」
（模块 17「三大募投项目详细对照表」：4 列宽表，标签列逐字竖排、整表顶出卡片右侧）

### ★★ 教训 1：先确认真溢出，别信直觉也不要信旧判据
**旧判据 `t.scrollWidth > t.clientWidth` 会静默漏报。**
表格 box 被容器约束到 1058、内容 min-content 1070 时它能报；
但 box 本身就是 1070（容器 1030）时 `scrollWidth == clientWidth == 1070` ⇒ 报 0。
**正确判据 = 表右边界 vs 含块内容框右边界**（`getBoundingClientRect().right` 减去父级 `paddingRight`）。
工具：**`build/probe_table_fit.py`**（一次量：全表真实溢出 / 格内被裁 / 列宽 / 行高 /
真实文本行数 / 卡片级溢出真凶 / 竖排检测）。

本次实测：表宽 **1003** / 容器 **889** ⇒ **右溢 115px**；表 min-content **979** > 889。

### ★★ 教训 2：行高虚高常常与「内容多」无关
本案 12 行行高 = **(标签字数 + 1) × 24px**，完全线性（9 字 235px / 6 字 165px / 4 字 119px / 3 字 95px）。
根因是 auto 布局按 min-content 分配列宽，把**标签列压到 59px**（作者写的 `.mi-dim{width:150px}` 不生效），
净宽 27px ⇒ 一个汉字一行 ⇒ 标签竖排把行高顶起来。
⇒ **先量「哪一列被压扁 / 哪一格在逐字竖排」，再谈缩字号减 padding**；否则一定治错方向。
判据：`t.querySelectorAll('td')` 用 **Range 的 `getClientRects()` 去重行框**数真实行数
（`td.getBoundingClientRect().height / lineHeight` 量到的是**行高**，不是文本行数，会误报一片）。

### ★★ 教训 3：溢出的推手往往是**表头不能换行**
全局「现代细线风」规则 `.card table th{…white-space:nowrap;}` 特异性 **(0,1,2)**，
压过模块自带的 `.mi-card th{white-space:normal}` **(0,1,1)**
⇒ 长表头各锁一行，单格 max-content 达 278/387/278px ⇒ 表 min-content 979 > 容器 889。
**用户说的「选择换行显示」就是让表头换行**（不是让表格缩字号，也不是改成横向滚动）。

### 修法（4 条，全在 `build/block_style.css`，只 scoped 到 `.mi-card` ⇒ 零副作用）
```css
.card .mi-card > table{table-layout:fixed !important;width:100% !important;max-width:100% !important;}
.card .mi-card > table > thead th:first-child{width:160px !important;}   /* 标签列一行放得下 */
.card .mi-card > table > thead th{white-space:normal !important;line-height:1.45;}  /* 放开表头换行 */
.card .mi-card > table > tbody td{padding-top:9px;padding-bottom:9px;}    /* 12 行省 72px */
@media(max-width:860px){ .card .mi-card > table > thead th:first-child{width:104px !important;} }
```
- `table-layout:fixed` + `width:100%` ⇒ 表宽恒等于容器宽，**没有 min-content 地板**，物理上不可能溢出。
- ⚠️ **固定布局下只有第一行（thead）的宽度生效** ⇒ 列宽必须写在 `th` 上。
  `.mi-dim{width:150px}` 写在 tbody 的 `td` 上，固定布局**不认**——这就是它一直没生效的原因。
- ⚠️ 表头换行**只放开 `.mi-card` 内的表**：其余表格表头（年份「2025E」）靠 nowrap 保持单行是**对的**。
- ⚠️ 只改 `.mi-card > table`（直接子表），不碰 `.mi-sum-box` 里嵌套的表。

### 验收基线（可复跑）
`T-bad=0/43` · 行高合计 **835px**（修前 1702px）· 右溢 **−1px**（修前 115）
· 首列行数 **全 1** · 列宽 **160/242/242/242**（修前 59/278/387/278）
· `is-txt 57 / is-num 576` 不变 · 全量探针零回退 · 000762 换标的 `T-bad=0/46`。

---

## 8. ★ 探针自身的三个坑（写新探针必查，2026-10-15 全踩过）


1. **`?code=` 必须带在「浏览器 URL」上**，不能只带在抓字节的 `urlopen` 上。
   漏了 ⇒ 页面回落硬编码的 `window.RPT_SEED`（600456 母本），600456/000762/600459
   三份测出来**数字一模一样**——看着像"全库一致"，其实是"全是同一份"。
   （`probe_report_mac.py` 是对的，可照抄：`http://127.0.0.1:<port>/report.html?code=<code>`）
2. **headless `--screenshot` 不吃 scroll**：滚到目标再截 = **白图 5888B**。
3. **截图不能 `document.body.innerHTML = 目标`**：目标会**失去 `.card` 祖先**，
   `.card xxx` 这类后代选择器全部不匹配 ⇒ 「修复前 / 修复后」两张图**一模一样**（假象，尺寸 md5 都相同）。
   正解：**沿祖先链向上逐层删掉链外的兄弟节点**（类名层级全保留，目标自然落到页面顶部）。
   ⚠️ 前提：要保留的样式块在 `<head>`（`rpt-blockstyle`/`rpt-blockscript` 都是注入 `</head>` 前的，
   所以安全；若哪天改成注入 body 就会跟着被删）。

### 伴生工具
- **`build/probe_table_fit.py`**（新）：表格溢出/行高/竖排/卡片级溢出真凶，支持
  `RPT_SRC=<file>`、`--win=W,H`、`--shot=<png>`、`--all`、`--key=<标题关键词>`。
- `probe_three.py` 的 `P1-table-overflow` **判据已过时**（见 §7 教训 1），
  量溢出请用 `probe_table_fit.py`。
- `card-overflow`（`probe_report_mac.py`）量的是「卡片 scrollWidth > clientWidth」：
  本案遗留的 `card-overflow=1` 真凶是同模块**时间轴装饰色带**
  `div.mi-tl-era.mi-tl-era-climb`（`left:96.7% + width:10% = 106.7%`），越界 ~6px、肉眼不可见、
  **改动前就在** —— 不是表格问题，别误判。
