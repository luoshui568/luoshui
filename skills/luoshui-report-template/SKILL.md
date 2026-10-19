---
# ===== 平台必填字段（WorkBuddy 开放平台 / SkillHub 上架用）=====
name: luoshui-report-template
display_name: 洛水研报模版
display_name_en: Luoshui Report Template
description: 洛水研报模版 —— 按「宝钛股份 600456」母本生产 31 模块 / 十节的深度研究报告（单文件离线 HTML），并推送到线上研报库。当用户说「用洛水研报模版帮我写一个 XX 的深度研究报告」「用洛水研报模版做 XX 的研报」「按洛水研报模版写新研报」「补全某只股票的研报」「改研报的某个模块」「改研报图表 / 表格样式」时使用。覆盖取数（iFinD + 发现研报 + 通达信）、组装、渲染、模块级版式统一、写库、上线与验收全流程。需配合随包分发的项目仓库（构建脚本 / 模板 / 种子数据），非独立工具。
description_zh: 洛水研报模版。把一家 A 股公司做成 31 模块 / 十节的单文件离线深度研究报告（母本＝宝钛股份 600456 的线上版，结构逐字复刻）：取数口径 → 组装 → 渲染 → 模块级版式统一 → 数据形状契约 → 写库 → 上线 → 探针验收。触发：「用洛水研报模版帮我写一个 XX 的深度研究报告」「按洛水研报模版写新研报」「用宝钛的模板做 XX 的研报」「补全某只股票的研报」「改研报的某个模块 / 图表 / 表格样式」「把某个模块统一成宝钛那样」。不适用于：非 A 股标的、只想要一段文字结论、没有项目仓库的环境。
description_en: Luoshui Report Template. Produce a 31-module, ten-section single-file offline deep-dive research report on an A-share company, mirroring the reference build (Baoti 600456) structure word for word, end to end — data sourcing, assembly, rendering, per-module layout standards, data-shape contracts, database write-back, deployment and probe-based acceptance. Triggers on phrasings like "write a deep-dive research report with the Luoshui template". Not for non-A-share targets or snippets of prose. Requires the companion project repository (build scripts, templates, seed data); it is not a standalone tool.
version: 1.0.0
author: 洛水
category: 数据分析

# ===== 本地 / 可选字段（平台会忽略，不影响上架）=====
agent_created: true
compatibility: 需配合项目仓库（`build/` 构建脚本 + `deploy/` 模板 + `seed/` 种子数据 + CloudBase 凭据）；Python 3.13+ / Node 20+；上线需 CloudBase CLI；入口见包内 INSTALL.md
---

# 洛水研报模版 · 31 模块深度研究报告生产流水线（宝钛母本）

> 中文名 **洛水研报模版** ｜ 技术标识 `luoshui-report-template` ｜ 用户级 skill，跨项目可用
> 用法：说「**用洛水研报模版帮我写一个 XX 的深度研究报告**」即可启动
> ★ **第一次拿到这个 skill（换机器 / 别人使用）**：先读 **`INSTALL.md`**（安装 + 首次配置），
> 再把下面「★ 环境配置」的变量换成自己机器的；跑一次 `python3 scripts/check_env.py` 可自动体检。

## 用途

生产**洛水研报模版**格式的深度研究报告：**单文件离线 HTML**，**31 个模块**分属**十节**，
结构、标题、目录一律以**宝钛股份 600456 的线上版为母本逐字复刻**，交付到
`https://liuchaowang.cn/report.html?code=<code>`（数据落 CloudBase PostgreSQL）。

## ★ 当前视觉定稿（2026-10-19 · 改样式前先看这 8 行）

线上 `report.html` md5 `74e16065`。**只记结论，细节以 `frontend-style.md` 为准**（§1.1 / §1.4 / §1.5）。

| 项 | 定稿 | 细节 |
|---|---|---|
| 底色 | **暖纸 `#f5f1e8`**（不是白、不是冷蓝）+ 淡红网格 + 26 颗尘粒 | §1.1 背景四层 |
| 表头 | **深酒红四段渐变** `#751111→#a82020→#8b1a1a→#6e1414` + `<th>` 金色发丝线 `rgba(201,162,39,.55)` + 米白字 `#f7efe1` | §1.1 |
| 表身 | 宣纸首列 `700` + 半透明米纸斑马 + 暖灰分隔线；**格内文字横竖都居中** | §1.1 / §1.5 |
| 字体 | **阿里巴巴普惠体 3.0**（子集 base64 内嵌 `rpt-fontface`，1.67 MB，`*` + `!important`） | §1.4 |
| 加粗 | `<b>/<strong>` → **亮朱砂 `#c0392b`**；深底（`#hero` / 表头行）`inherit` | §1.5 |
| 数字 | 表内**两位小数**，整数不加 `.00`；脚注 `.src` 不圆 | §1.5 / #72 |
| 正文 | 暖墨灰 `#4a423e`，深字 `#14100e`（**别再用冷蓝灰 `#4d5f6d`**） | §1.1 |

⚠️ 三条别踩：`fixGold` 换色器**默认已关**（`RETINT=false`，金色是主色）· 金线只能写 `<th>` 的
`border-bottom`（`<tr>` 的 box-shadow 跨不了单元格）· 换配色必须同步换正文字色。

## ★ 按任务找文档（先看这张表，**只读你要的那一份**）

| 我要做什么 | 读哪份 | 关键节 |
|---|---|---|
| **第一次装 / 环境不通 / 换机器** | **`INSTALL.md`**（给人看） | §3 安装 · §4 配置 · §5 自检 · §6 常见问题 |
| **环境体检**（变量 + 项目文件 + 运行时） | **`scripts/check_env.py`** | 直接跑：`python3 scripts/check_env.py` |
| **改完文档后自检**（文件引用 / `§N` 节引用是否失效） | **`scripts/check_refs.py`** | 直接跑：`python3 scripts/check_refs.py` |
| **写一份新研报**（全流程） | **`pipeline.md`** | §1 取数 → §2 组装 → §3 渲染 → §4 版式统一 → §5 写库 → §6 上线 |
| 查「用户的硬性要求」 | **`hard-rules.md`** | 开头**「定稿速查」表** → 七个分组（**71 条**） |
| 31 模块 / 十节的结构、编号契约 | **`modules-31.md`** | 全部（很短） |
| **改某个模块的版式**（m3 股东 / m11 双环 / m22 产业链 / m25 地图 / m29 评分 / verdict / 解读块 / 注解） | **`module-standards.md`** | 见各节标题 |
| **往 `data_v31_*.json` 里填数据**（防版式崩） | **`module-standards.md`** | **§9 形状契约（必读）** |
| **改图表**（opt / 渲染层 / 双轴 / 面积 / 时间轴 / **区间按钮**） | **`chart-specs.md`** | §1 渲染层补丁 · §3 模块29 双轴图范式 · **§5 区间按钮组** |
| ★★ **修「图是空白」/「图画错了」** | **`chart-specs.md`** | **§6 空图 vs 错图 · 两道语义闸 · 摘槽位 `drop_chart_slot.py`** |
| ★★ **seed 与库不同步 / 担心「一 push 就退化」** | **`pipeline.md`** | **§5 的「seed ↔ 库 双向纪律」**（含两道自动防线 + 哪些脚本只写库） |
| ★ **定期体检全库 13 份** | **`build/audit_reports.py`** | 直接跑：`python3 audit_reports.py`（一次查 8 类问题） |
| **改表格 / 文字 / 配色 / 字体 / 加粗 / 小数 / 居中** | **`frontend-style.md`** | §1.1 宣纸墨金表格 · §1.4 阿里普惠体内嵌 · §1.5 加粗朱砂 + 横竖居中 + 两位小数 · §7 表格溢出 |
| ★ **换机器后页面字体变成系统字体 / 页面突然变小 1.67 MB** | **`frontend-style.md`** | **§1.4**（`build/font/` 与 `block_font.css` 是 `.gitignore` 派生物 ⇒ 先跑 `build/make_font_css.py --fetch`） |
| **改研报列表页 / 公司资料库** | **`frontend-style.md`** | §3 / §4 |
| **样式改了却不生效** | **`frontend-style.md`** | §5 样式表腰斩 · §2 注入顺序 |
| **发 `report.html`**（★ **必读**，直发 `build.py` 产物会删掉线上样式块） | **`deploy-verify.md`** | **§3 `_patch_blockstyle.py` 那一段** |
| **部署 / 上线 / 防被并发会话覆盖** | **`deploy-verify.md`** | §2 并发防护 · **§3 严格超集** · §6 验收清单 |
| **写 / 改探针** | **`deploy-verify.md`** | §4 探针清单 · §5 无头浏览器纪律 |

> 七份 references 是按**改动场景**拆开的：模块版式 / 图表 / 前端样式 / 要求清单 / 流程与部署 / 结构蓝图。
> 别一次全读 —— 按上表挑，省上下文。

## 何时使用

- **「用洛水研报模版帮我写一个 XX 的深度研究报告」**（标准说法）
- 「按洛水研报模版写新研报」「用我宝钛股份的模板做 XX 的深度研究报告」「按 31 模块模板建档」
- 「给 XX 补全研报数据」「研报的某某模块要改」「把某个模块统一成宝钛那样」
- 「把这张图铺到其他研报」「研报的图表 / 表格样式要改」

## ★ 环境配置（换机器 / 别人首次使用：先改这里）

skill 里**所有命令都用变量写**。把下表几个值换成你自己机器的，后面每个 `bash` 块就能直接照抄；
不改文件、在对话里直接把这几个值告诉我也行。跑 `python3 scripts/check_env.py` 可自动体检并告出缺口。

| 变量 | 含义 | 本机（作者）当前值 |
|---|---|---|
| `PROJ` | 项目根（含 `build/` `deploy/` `deliver/`） | `/Users/luoshui/WorkBuddy/2026-10-10-22-59-27/luoshui` |
| `PY` | 主 Python（跑构建脚本） | `/Users/luoshui/.workbuddy/binaries/python/envs/default/bin/python`（3.9.6）<br>⚠️ **不要用** versions/3.13.12/bin/python3.13 —— 二进制被截成 **0 字节**，跑它**静默返回空输出（rc=0）** |
| `PYV` | 隔离 venv Python（跑探针 / PIL 出图 / fonttools 子集化） | `/Users/luoshui/.workbuddy/binaries/python/envs/default/bin/python`（与 PY 同一个，Pillow / requests / fonttools 都装在这） |
| `TCB` | CloudBase CLI（部署用，需先 `tcb login`） | `/Users/luoshui/.workbuddy/binaries/node/cli-connector-packages/bin/tcb` |
| `ENVID` | 你的 CloudBase 环境 ID | `fdels568-d7g1d8o3y90a80cd7` |
| `DOM` | 你的访问域名 | `liuchaowang.cn` |

> 作者环境的 node：`/Users/luoshui/.workbuddy/binaries/node/versions/22.22.2-6/bin/node`（`node --check` 用）。

### 项目坐标（相对 `$PROJ`）

| 项 | 路径 |
|---|---|
| 构建/生成脚本 | `build/`（**只读复用，不要复制到别处**） |
| 蓝图（唯一真源） | `build/report_template_v31.py` |
| 渲染器 | `build/report_build_v31.py` |
| 种子数据 | `build/seed/{data_v31_<code>.json, report_<code>.json}` |
| 研报页模板 | `deploy/report.template.html` → 产物 `deploy/report.html` |
| **表格/装饰样式源** | **`build/block_style.css`** ＋ **`build/block_style.js`**（注入器 `build/_patch_blockstyle.py`）<br>⚠️ 这是**表格配色 / 观感 / 字体 / 加粗 / 居中 / 小数 / 星号 / essence 分块 / 背景层**的唯一源。`build/report_theme.css` 仍是注入源之一（承载 `rpt-txtstyle` 等），但**它会被并发会话整份重写 ⇒ 别把自己的块放进去** |
| **字体资源**（★ 派生物，`.gitignore`） | `build/font/{apht-regular,apht-bold}.woff2` + `charset.txt` → 生成 `build/block_font.css`（1.67 MB base64）<br>生成器 `build/make_font_css.py`；**新机器 / 目录被清** ⇒ 先 `$PY build/make_font_css.py --fetch` 再注入 |
| 交付物 | `deliver/`（**不要写桌面**） |

## 标准流程（骨架，细节见 `pipeline.md`）

```bash
cd "$PROJ/build"          # $PROJ 见上方「★ 环境配置」

# 0) 换机器 / 首次：字体派生物是 .gitignore 的，缺了会渲染成系统字体
[ -f block_font.css ] || $PY make_font_css.py --fetch   # 下 4.85+5.09 MB 原字体 → 子集 → base64

# 1) 取数落盘：iFinD + 发现研报 MCP → seed/_raw_b1/<code>.<key>.json
#    组装成模板数据源（财务 / 可比 / 行业 / 预测）
$PY batch_assemble.py <code> <名称> <行业> <省份>

# 2) 找齐定性内容（行业 / 下游 / 管理层 / 护城河 / 多空），填进 data_v31_<code>.json
#    取不到的一律 [MISSING]，绝不编造

# 3) 从零渲染 31 模块 → seed/report_<code>.json（自带编号连续 + 图槽配对断言）
$PY report_build_v31.py <code>
#    ★ 重跑 build 会把模块 3 与模块 22 覆盖回默认渲染 —— 所以第 4 步的 --write 必须在它之后

# 4) 模块级版式统一（每份新研报都要逐一过）
$PY mkmod3_std.py <code> --check      # 股东结构（宝钛冻结范例）
$PY mkchain_std.py <code> --check     # 产业链全景图
$PY mkmod11_ring.py --check           # 收入 / 毛利结构 = 左右两个环
$PY verdict_std.py --dry              # 核心结论版式（文字零丢失断言）

# 4b) 线上真字节探针（mac 版）。★ 先拿 600456 跑一遍当基准，确认探针本身没问题，再测新报告：
$PY probe_report_mac.py 600456        # 基准：cards=31 / chartmiss=0 / card-overflow=0
$PY probe_report_mac.py <code>        # 新报告：card-overflow 必须为 0、chartmiss 必须为 0

# 5) 备份 + 写库 + 回读核对
$PY push_reports_v31.py <code>
```

`report_build_v31.py` 末尾的 `assert` 会拦住编号不连续、图槽无图数据、壳字段缺失
——**红了就是没写完，不要绕过**。

## 五条最容易被忽略的硬性要求

1. **31 模块与十节目录一律照抄宝钛，不可乱改**（模块顺序、标题、目录逐字）。
2. **数字只来自 `data_v31_<code>.json`；取不到写 `[MISSING]`，模型推算标 `[模型输出]`，绝不编造**；
   往 json 里填数据前先读 `module-standards.md` **§9 形状契约**（填错形状会把表撑到几千像素宽）。
3. **"研报上线" = 写库**（`wb_reports` / `wb_report_mods` / `wb_report_charts`），不是传 HTML；
   上线顺序**先发 report.html 再写库**，部署**绝不带 `--prune`**。
   ⚠️ 改**核心结论**要写 `shell.verdict`，**不是** `conclusion.verdict`（死字段）——
   推完必须单独回读 `wb_reports.verdict_html` 断言特征词。
4. ★ **发 `build.py` 产物前必须走「严格超集」五步**（`deploy-verify.md` §3）：
   抓线上基线 → 逐 `<script>` 块比 md5（含 `window.RPT_SEED`）→ **CSS 规则级**（线上有·产物没有
   **必须 = 0**）→ 逐元素 computed style（差异全为预期）→ 才发、发完回读 md5 逐字节一致。
   **通过即可直接部署**（「以后都直接上线」已授权加强）。
5. ★ **壳＝三个自有块，缺一个就整块退版**：`rpt-fontface`（阿里普惠体 1.67 MB）+ `rpt-blockstyle`
   （宣纸墨金 / 加粗 / 居中 / 小数）+ `rpt-blockscript`（渲染层）。它们**都不在模板里**，只有
   `build/_patch_blockstyle.py` 会补；发完 `curl` 回读 md5 与产物**逐字节比对**，
   上一版 md5 一变就说明被并发会话盖了（`frontend-style.md` §2）。

## 交付纪律

- 单文件 HTML、离线可用、落 `deliver/`。
- 构建 → 语法检查（`node --check`）→ `check_raw_tags.py` → 探针全绿 → **严格超集** → 直接上线
  （用户已长期授权）；上线后逐个 URL 验 HTTP 200 + md5 **逐字节一致**；
  抓**线上真字节**回跑探针（`RPT_SRC=/tmp/live.html`）。
- **只改图 / 只改模块 HTML（都在库里）⇒ 不必部署**；只有改**渲染器 / CSS / 模板**才发壳。
- 涉及并发风险时，先读 `deploy-verify.md` §2「并发会话防护」。
