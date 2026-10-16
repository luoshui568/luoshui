# 洛水研报模版 · 部署与验收纪律

---

## 1. 部署通道

| 项 | 值（**作者环境；换成你自己的** `$ENVID` / `$DOM` / `$TCB`） |
|---|---|
| envId | `fdels568-d7g1d8o3y90a80cd7` |
| 主域名 | `https://liuchaowang.cn/` |
| 托管方式 | **静态托管**（**别切 manageApps**，会换 URL） |
| CLI | `$TCB`（**需先 `tcb login`**；作者机上的路径见 `SKILL.md` ★ 环境配置） |

```bash
# 整站部署（★ 绝不带 --prune）
cd "$PROJ"
"$TCB" hosting deploy ./deploy_site --env-id "$ENVID" --safe --verify

# 单文件部署
"$TCB" hosting deploy <file> <cloudPath> --env-id "$ENVID" --verify
```

构建：`build/build.py`（把 `WB_CFG={envId,key}` 注入模板占位符，key 在 `build/cloud.json`）。
运行时 REST：`https://<envId>.api.tcloudbasegateway.com/v1/rdb/rest/`，
请求头**只带** `Authorization: Bearer <key>`，**不带 apikey**。

---

## 2. ★★ 并发会话防护（同一仓库会被两个会话同时改）

**这一步不做，你的改动可能被静默抹掉。**

### 判据：线上有没有我的标记

```bash
curl -s https://liuchaowang.cn/report.html -o /tmp/base.html
grep -c "<我的特征词>" /tmp/base.html     # 0 ⇒ 线上还没有我的功能
```

### 两种情况，两种通道

| 情况 | 通道 |
|---|---|
| **线上还没有我的功能** | **夹块重注入**：`python3 build/_patch_report.py --base /tmp/base.html --built deploy/report.html --out <产物> --mine <我的特征词> --exclude <别人独有的特征词>`。**必须白名单**（判据 `is_mine = 含 --mine 且不含 --exclude`） |
| **线上已有我的功能、只改一两行** | **最小定点补丁**：在当前线上字节上以「改动点的**前后完整原文**」为锚点做**单处 `str.replace(…,1)`**，再双向校验 |

⚠️ `--exclude` 只能用别人**独有**的词；用「模块正文」这种两边都有的词会把自己的 hunk 一起丢掉。
⚠️ **混合 hunk**（我的删除与别人新增交错在同一个 replace 块）⇒ **整块丢弃**再用定点脚本补，
**绝不能整块采用**（会带上别人未上线的代码）。
⚠️ 与别人的 hunk 缠在同一处 ⇒ 白名单也没用，改**锚点定点注入**（`build/_patch_comfiles.py`），
双向校验 = 我的标记数 == 模板数、**别人的标记数必须与基线逐项相等**、顶层命名无冲突、
差集只能是「纯插入 0 删除」。
⚠️ 结束标记要**排他**；换基线后**锚点要重验**。
⚠️ 标记词表**必须避开插入内容里出现的词**（`fStat` 曾因插入的注释里写着 `fStat('')` 而假报警）。
⚠️ `_patch_*.py` 自检打印的「字节数」其实是**字符数**（text mode），别跟 `wc -c` 对不上就以为出错。

### ★★ 会被静默回退

并发会话也用 `--out deploy_site/report.html`（**同一往返文件名**），基线是我上线**之前**的旧字节
⇒ 产物 = 旧基线 + 它的 hunk，**把我加的整段抹掉**再原样 deploy。

**取证**：`ls -l deploy_site/report.html` 的 mtime + `md5` 若等于你之前抓过的旧基线即坐实。

**应对**：
1. 自己的产物**别写 `deploy_site/`**，写 `/tmp/<唯一名>.html`；
2. **每次上线前重新 `curl`**，`grep -c <自己的特征词>` == 0 ⇒ 已被回退；
3. 发完**立刻复验**，被盖补发一次，再被盖就**停止循环**、
   **如实告诉用户"另一会话在抢同一个文件"**。

---

## 3. ★★ 上线前的「严格超集」验证法（2026-10-15 固化，**每次发 `build.py` 产物都要走**）

**为什么需要**：`python3 build/build.py` 会**重写全部 5 个产物**（含 `report.html`）。
直接把它发上去 = 用**我本地的旧基线**覆盖线上 —— 并发会话在这期间叠上去的东西**全没**。

### 五步（顺序不可换）

| 步 | 动作 | 通过判据 |
|---|---|---|
| ① | `curl` 抓**线上真字节**做基线（`curl -s https://liuchaowang.cn/report.html -o /tmp/base.html`） | 文件大小 / md5 记下来 |
| ② | **逐 `<script>` 块比 md5** | 除**本次要改的那一块**外，其余（含 `window.RPT_SEED`）**逐字节一致** |
| ③ | **CSS 规则级 A/B**（`build/probe_cssom_diff.py`） | **线上有·产物没有 = 0 条**；产物新增条数 = 本次预期 |
| ④ | **逐元素 computed style A/B**（`build/probe_style_diff.py`） | 差异**全是预期项**（逐个说得出理由） |
| ⑤ | 才发。发完**回读 md5** 断言**逐字节一致** | `md5(线上) == md5(待发)` |

### 实测样例（2026-10-15 两次）

```
13:44 三问题修复：script 块 6/6 只有 #3 rpt-blockscript 不同（新加 markTxt），
                 其余含 RPT_SEED 37276 字符逐字节一致
                 CSS：线上有·产物没有 = 0；产物新增 6 条（本次修复）
                 逐元素 computed style 差异 7 处，全是预期
                 ⇒ 发。产物 c3d9d8dc…，线上回读逐字节一致

14:35 表格溢出修复：script 块 6/6 全部逐字节一致（含 RPT_SEED 37614 字符）
                 CSS：线上有·产物没有 = 0；产物新增 6 条
                 ⇒ 发
```

### ★★★ 发 `report.html` 前必须补一步：`_patch_blockstyle.py`（2026-10-16 差点踩掉）

**线上 `report.html` ≠ `build.py` 产物。** 线上还叠着两块**不经模板生成**的东西：

| 块 | 内容 | 谁注入 |
|---|---|---|
| `<style id="rpt-blockstyle">` | 模块堆叠文本分块 + 表格「**红表头 + 浅蓝身**」全套餐（20 KB） | `build/_patch_blockstyle.py` |
| `<script id="rpt-blockscript">` | 配套渲染层（Markdown 粗体 / 数字列标注 / 长文块分拆，19 KB） | 同上 |

⇒ **正确发布链**：

```bash
python3 build/build.py                     # ① 重写 5 个产物；★ 末尾会自动补那两块
tcb hosting deploy deploy/report.html /report.html --env-id <env> --verify   # ② 发
```

★ **`build.py` 从 2026-10-16 起已把注入焊进流程**（`patch_blockstyle()`，紧跟 `build_report()`）——
跑完会打印 `已补 rpt-blockstyle + rpt-blockscript：… md5=…`。
看到这一行才算 OK；若出现 `! blockstyle 注入失败` ⇒ **别发布**（那个 `report.html` 是残缺的）。

手工兜底（`build.py` 跑不了、或想从线上字节重新打）：

```bash
python3 build/_patch_blockstyle.py --base deploy/report.html --out /tmp/blk/report.html
tcb hosting deploy /tmp/blk/report.html /report.html --env-id <env> --verify
```

**直发 `deploy/report.html` 的后果**（2026-10-16 实测，diff 一眼看出）：产物比线上**少 39 753 字符 /
928 行**，`rpt-blockstyle` 与 `rpt-blockscript` 双双消失 ⇒ **12 份研报的表格样式与粗体渲染同时失效**
（页面不报错，只是全体「没样式」）。

★ **为什么「严格超集」五步查不出来**：那五步比的是 `<script>` 块 md5 与 CSS 规则，
而这个缺口表现为**整块标签消失** —— 所以特征词表里**必须钉死** `rpt-blockstyle` /
`rpt-blockscript` / `rpt-txtstyle` / `is-num` / `tl-nav` / `btAlignZero` 这几项「线上有 · 产物必须有」。

★ 顺带：`_patch_blockstyle.py` 自己会打印「回退后与线上逐字节一致: True」，并给特征词对照表
（`线上 N → 产物 M`）—— **这就是最省事的一次严格超集自检**，跑完直接看那几行。

### ★ 反过来的收获：产物里的「多出来」可能正是别人漏发的修复

2026-10-16 那次 diff 里，产物比线上多一行 `nullDash`（`FNS` 注册表的新条目）。
查库发现**线上 `600456_chartProfit` 已经在用 `{{fn:nullDash}}`**，而线上壳里没有这个函数 ⇒
那个图的标签 formatter 还原不出来（实测 `formatterType === 'string'`，页面显示字面量 `{{fn:nullDash}}`）。
⇒ 产物「多出来」的那一行**不是脏数据，是别人写好、甚至已经落库、但忘了发布 report.html 的修复**。
**判定法**：把差异项拿去 grep 线上库（`wb_report_charts.opt` / `wb_report_mods.html`），
库里有引用 ⇒ **带上它**（顺手把 bug 修了）；库里查无引用 ⇒ 可以不带。

### 配套：`build.py` 的「只发自己改的那个」纪律

`build.py` 一跑，`report.html` / `research.html` / `index.html` / `datalib.html` / `app.html`
**全部被重写**（本地会被刷成与线上不同的版本）。
⇒ **只 `tcb hosting deploy` 你真正改的那一个文件**，别整站发、别把 `build.py` 的顺带产物发上去。

### 判定标准（一句话）

**产物必须是「线上字节」的严格超集** —— 线上有的，产物必须有（一个字节都不能少）；
产物多的，必须**逐条说得出为什么**。

---

## 4. 探针清单（mac 版）

★ **先拿 600456 跑一遍当基准**（`cards=31` / `chartmiss=0` / `card-overflow=0`），再测新报告
—— 这是「判据要正反都验」的落地。

| 探针 | 覆盖 | 用法 / 判据 |
|---|---|---|
| ★ **`probe_report_mac.py`** | **线上真字节基准探针**（最常用） | `python3 probe_report_mac.py <code>`；`RPT_SRC=<file>` 换被测文件 |
| ★ **`probe_table_fit.py`** | 表格**真溢出 / 行高 / 竖排 / 卡片级溢出真凶** | `RPT_SRC=` / `--win=W,H` / `--shot=<png>` / `--all` / `--key=<标题关键词>`。判据 = **表右边界 vs 含块内容框右边界** |
| ★ **`probe_cssom_diff.py`** | **CSSOM 级 A/B**（改动丢没丢规则） | 比「逐元素 computed style」更早暴露**规则级**丢失 |
| ★ **`check_raw_tags.py`** | **裸标签守门**（CSS/模板**注释里**的裸 `style`/`script` 标签名） | 已接入构建前检查；正反都验过（能红能绿） |
| `probe_style_diff.py` | 逐元素 computed style A/B | 严格超集第 ④ 步 |
| `probe_report_e2e.py` | 研报页 85 项 | 本机 http |
| `probe_reports_all_e2e.py` | 全部研报批量 | — |
| `probe_three.py` | 表溢出 + 长文本居中 + 工具栏重复 | ⚠️ 其 `P1-table-overflow` **判据已过时**，量溢出请用 `probe_table_fit.py` |
| ★ **`audit_reports.py`** | **全库体检：一次查完 8 类问题**（seed↔库差异 / data 键数 / 全空 series / `[MISSING]` / 槽位↔图对账 / 结构要件 / `**` 残留） | `python3 audit_reports.py`；单份加 code。**改完一批就该跑一次** |
| ★ **`drop_chart_slot.py`** | **摘掉模块里的图表槽**（判据拦住错图后，收拾库里旧模块的残留槽位） | `drop_chart_slot.py 600459:6:chartCap 601958:7:chartProd`；`--go` 写库，随后接 `sync_seed_full` |
| `fix_missing_wording.py` | 清掉 m31 里「**提到** `[MISSING]` 这个词」的展示性文案（探针会误计成缺口） | `--go` 写库，随后接 `sync_seed_full`；真缺口与 `MISSING-shell` 不动 |
| `probe_istxt.py` | `markTxt` 判据分流（`is-txt 57 / is-num 576`） | — |
| `probe_toolbar_dup.py` | 工具栏归属 / 是否重复 | — |
| ★ **`_probe_toolbar.py`** | **图表「区间按钮组」**（3年/5年/10年/全部）三项：**归属**（落在哪个模块 / 管哪张图）、**有无重复**、**点后是否真生效** | `--src <html>` / `--code <code>`；判据与踩坑见 `chart-specs.md` **§5** |
| `probe_logic.py` | 解读块折叠 22 项（含打印模式） | — |
| `probe_m29_dom.py` | 研报页 **m29 真实 DOM** 13 项 | ⚠️ 必须**打掉壳里硬编码的 `window.RPT_SEED`** + 带 `?code=` |
| `probe_research_score.py` | 研报**列表页**评分块 46 项 | 判据：格数分布 `{4:N}`、四格标签严格等于 4 个标准名、`—` 格带 `na` 类 |
| `probe_hist_modal.py` | 时间轴 11 项 | 改前必读 detail 第二节 |
| `probe_tlnav.py` | 时间轴箭头 / 两端点击 | — |
| `probe_verdict.py` | 核心结论版式 | — |
| `probe_ring_m11.py` | 收入/毛利双环 | — |
| `probe_axis_zero.py` | 双轴 0 刻度对齐 | — |
| `probe_negr.py` | 负值柱圆角 | — |
| `probe_blockstyle.py` / `probe_txtstyle.py` | 纯文字版式（量**计算样式**） | ⚠️ 换配色要**同步改三处**：期望值常量区 + JS 采集段 + 断言 |
| `probe_report_notes.py` | 注解弹窗 8 项 × 11 份 | `RPT_SRC=/tmp/live.html` 可跑线上字节 |
| `probe_comfiles.py` | 公司资料库 86 项 | `WB_PW=xxx --full` |
| `_probe_lock29.py` | 企业评分契约 | — |

### 截图类

| 脚本 | 说明 |
|---|---|
| ★ **`_shot_chart_slot.py`** | **截图表槽的真渲染结果**（canvas 专用）。`--override <刚curl的线上字节>` / `--opt <本地json>`（**不写库**就能看渲染） |
| ★ **`_shot_eps_ba.py`** | 改前 / 改后对照图（**改前不写库**：用线上字节渲染后换回快照里的旧 opt 重渲一次） |
| `probe_shot3~6.py` | 通用截图（含滚动裁切） |
| `shot_logic_fold.py` | 折叠块截图范例（**MutationObserver 等 DOM，不靠 setTimeout**） |
| `_m3std_shot.py` / `_comfiles_shots.py` | 模块 3 / 公司资料库专用 |

---

## 5. 无头浏览器纪律

```
Edge --headless=new
  --user-data-dir=/tmp/edgeprofN     # 必带
  --no-sandbox                       # 不加直接崩
  --no-proxy-server                  # 不加会把 127.0.0.1 当外网
  --window-size=W,H                  # 显式
```

- 页面走 **`http://127.0.0.1:<port>`**（`file://` 的 `Origin: null` 被网关 403，会退化成内置副本）
- 注入位置用 **`html.rfind('</body>')`**（报告页有 2 个 `</body>`）
- 一律 `.click()` 真实按钮、派真实 `KeyboardEvent`，**绝不直接调函数**
- 探针**不许写生产表**
- 验 `@media print` 不用改文件：
  `sed 's/@media print/@media all/g' deploy/report.html > /tmp/x.html` +
  `RPT_SRC=/tmp/x.html python3 build/probe_xxxx.py <code>`

### 判据纪律

- ⚠️ 判**伪元素是否隐藏**看 `getComputedStyle(el,'::after').display`，**不能看 `.content`**（假失败）。
- ★ 判 CSS 收没收掉元素**量 `getComputedStyle(el).display`，别量 `offsetWidth`**；
  **判据要正反都验**，并拿旧字节跑一遍确认它**真会红**（鉴别力证明）。
- ⚠️ **headless 渲染不了 PDF**（`<iframe>` 永远一片深灰）⇒ PDF 验收**不看截图**：
  验 `src` 以 `#view=FitH` 结尾 + `.vhint` 提示条 + 对象 `HEAD 200 & application/pdf`。
- ⚠️ 二进制素材塞给 `File` **必须传 `Uint8Array`**（`new File([atob(b64)])` 按 UTF-8 编码会静默损坏图片）。
- ⚠️ 验「匿名能不能删对象」**不能用不存在的 key**（网关先查存在性，回 404，走不到 RLS）。
- ★ **给 SPA 截图：注入脚本里绝不能有 setTimeout 轮询**（`--virtual-time-budget` 的虚拟时钟被飞速耗尽
  ⇒ 出纯白图）。正解：**MutationObserver 等 DOM 长出来**，然后**同步**把目标卡以外全 `display:none`，
  **不要靠 `scrollTo`**。范例 `build/shot_logic_fold.py`。
- ★ 探针里的 `(async function(){ … }, 1200);` 是**逗号表达式，函数根本不会被调用**（零输出零报错）。
- 探针结果用 `POST` 回传本地 server（真实轮询等待后 kill）。
- ⚠️ **`--dump-dom` 在本机 Edge 不吐输出**（返回空）⇒ 必须走 `fetch POST` 回本地 server 取结果。

### ★★ 三个「测出来全是同一份」的假象（2026-10-15 全踩过）

1. **`?code=<code>` 必须带在「浏览器 URL」上**，不能只带在抓字节的 `urlopen` 上。
   漏了 ⇒ 页面回落**硬编码的 `window.RPT_SEED`（600456 母本）**，
   600456 / 000762 / 600459 三份测出来**数字一模一样** —— 看着像"全库一致"，其实是"全是同一份"。
   正确写法：`http://127.0.0.1:<port>/report.html?code=<code>`（照抄 `probe_report_mac.py`）。
2. **headless `--screenshot` 不吃 scroll**：滚到目标再截 = **白图 5888B**。
3. **截图不能 `document.body.innerHTML = 目标`**：目标会**失去 `.card` 祖先**，
   `.card xxx` 这类后代选择器全部不匹配 ⇒ 「修复前 / 修复后」两张图**一模一样**（假象，md5 都相同）。
   正解：**沿祖先链向上逐层删掉链外的兄弟节点**（类名层级全保留，目标自然落到页面顶部）。

⚠️ **SPA / 动态注入模块（研报页 m29、`rptSlide`）根本不能靠截图验**：
静态 HTML 连 `data-no` 都没有，`--screenshot` 出 **9516 字节纯白** ⇒ **量 DOM**。
（量 m29 还要先**打掉壳里硬编码的 `window.RPT_SEED`**，并注意 `.sc-val` 的真实分数在
`input.value` 而不是 `textContent` —— `scoreLive` 会把文字换成 `<input>`。）

### ★★ canvas 图截图：两个真坑（2026-10-15 踩过）

1. **图表是 canvas，`cloneNode` 不复制位图** ⇒「改前 / 改后」两张图会一模一样（假象）。
   正解：**让原页渲完，再把兄弟模块全隐藏**，只留目标模块的 `h3 / [data-chart] / .src`。
2. ★★ **收容器时的循环条件写错会把整份报告隐藏掉**：按文案找「返回工作台」再向上收时若写成
   `e.parentElement !== document.body`，`e` 正好停在 `#wrap` ⇒ **整份报告 `display:none`**，
   现象是「**截图纯白 + `slot.clientWidth===0`**」，而 canvas 其实**早渲染好了**（980×336）。
   **正解：只走到 `#wrap` 的**直接子节点**为止，且绝不隐藏含 `#mods` 的节点。**

### ★★ 用 PIL 拼对照图时

- 画中文**必须指定字体**（`Songti.ttc` / `PingFang.ttc`），否则方框。
- **`os.chdir()` 之后写相对输出路径会落进临时目录** ⇒ 输出路径一律先 `abspath`
  （本轮真踩：文件写进了 `/tmp/epsba_serve/deliver/`）。

---

## 6. 上线验收清单（每次部署都走）

- [ ] `deliver/` → `deploy_site/` 已同步，**md5 逐个比对一致**
- [ ] 内联 `<script>` 全部通过 `node --check`（语法检查）
- [ ] `python3 build/check_raw_tags.py` 通过（注释里没有裸标签）
- [ ] 相关探针全绿，**零 JS 错误**
- [ ] ★ **「严格超集」五步**已走（§3）：线上有·产物没有 = 0 / 差异全是预期
- [ ] 部署命令**没有 `--prune`**，且**只发自己改的那一个文件**
- [ ] 部署后逐个 URL：**HTTP 200 + md5 与本地一致**（**回读逐字节一致**）
- [ ] 抓**线上真实字节**回跑探针（`RPT_SRC=/tmp/live.html ...`）
- [ ] 内容抽查：新记号**在**、旧记号**不在**
- [ ] 若改了图表/环图/时间轴 ⇒ **确认 report.html 也发了**
- [ ] 若写了库 ⇒ **seed 与库已同步**；改结论 ⇒ **单独回读 `wb_reports.verdict_html` 断言特征词**
