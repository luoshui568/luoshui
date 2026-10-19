# 洛水研报模版 · 安装与使用说明

> **给第一次拿到这个 skill 的人。** 装好之后，在对话里说
> 「**用洛水研报模版帮我写一个 XX 的深度研究报告**」即可启动。

---

## 1. 这是什么

一套把一家公司做成 **31 模块 / 十节的单文件离线深度研究报告**的工作流：
取数口径 → 组装 → 渲染 → 模块级版式统一 → 写库 → 上线 → 验收，全部有明确的命令与判据。

| 文件 | 给谁看 | 说明 |
|---|---|---|
| `SKILL.md` | **AI（也建议人扫一眼）** | 主入口：**按任务找文档**路由表 + **★ 环境配置** + 骨架流程 + 四条最易忽略的硬性要求 |
| `INSTALL.md` | **人** | 本文件：安装 + 首次配置 + 自检 + 常见问题 |
| `scripts/check_env.py` | 人 / AI | 环境体检：变量是否就位、项目关键文件是否齐全 |
| `references/hard-rules.md` | AI | **用户硬性要求 71 条**（分七组，逐条带出处）+ 开头「定稿速查」表 |
| `references/modules-31.md` | AI | 31 模块 / 十节蓝图（逐字） |
| `references/module-standards.md` | AI | 各模块版式标准（含 **§9 数据形状契约**，往 json 填数据前必读） |
| `references/chart-specs.md` | AI | 图表专项（渲染层补丁 / 双轴图范式 / 面积置顶 / 地图合规） |
| `references/frontend-style.md` | AI | 表格 / 文字 / 配色 / 列表页 / 资料库 + 「样式不生效」排查 |
| `references/pipeline.md` | AI | 完整命令链（取数 → 组装 → 渲染 → 写库 → 上线） |
| `references/deploy-verify.md` | AI | 部署与验收纪律（并发防护 / **严格超集** / 探针清单 / 无头浏览器） |

---

## 2. 前置条件

| 依赖 | 必需 | 说明 |
|---|---|---|
| **项目仓库** | ★ 必需 | 本 skill **只含规范与流程，不含构建脚本** —— 脚本要跟着仓库走。仓库：`luoshui568/luoshui`（私有，找作者开权限）。skill 里所有路径都相对项目根 `$PROJ`。 |
| Python **3.9+** | ★ 必需 | 跑 `build/` 下的生成器。<br>⚠️ 作者本机 `versions/3.13.12/bin/python3.13` **二进制已被截成 0 字节**，跑它**静默返回空输出（rc=0）**、不报错 ⇒ 一律用 `envs/default/bin/python`（3.9.6） |
| Python `fonttools` + `brotli` | ★ 要改字体才要 | 阿里巴巴普惠体子集化（`build/make_font_css.py`）；`pip install fonttools brotli` |
| Python `PIL` | 出图才要 | 截图 / 拼图类探针需要，建议装在**隔离 venv** 里（作者与 `PY` 同一个） |
| Node.js **20+** | 建议 | `node --check` 语法检查 |
| CloudBase CLI `tcb` | 要上线才需要 | 部署静态托管，需 `tcb login` 一次 |
| MCP 连接器 | 取数才需要 | iFinD 系（`hexin-ifind-ds-*`）· `westock` · `tdx-connector` |

**不用装的东西**：ECharts、xlsx 库等前端依赖全部随页面走，无 npm 安装步骤。

### ★ 字体资源（派生物，`.gitignore` 掉的，换机器必做）

页面里那 **1.67 MB** 的阿里巴巴普惠体是 `build/font/*.woff2` 子集化后 base64 内嵌的。
原字体和生成物**都没进仓库**（原始 Regular 4.85 MB + Bold 5.09 MB，进 git 会撑爆），
所以新机器 / 清过目录之后：

```bash
cd "$PROJ/build"
$PY make_font_css.py --fetch     # 下原字体 → 裁 4,191 字 → 生成 block_font.css
```

跑完 `block_font.css` 约 1.67 MB。**不跑**的话研报页会掉回系统字体（PingFang / 微软雅黑），
样式没错但看起来"不像洛水研报"。`--fetch` 走 `api.github.com` 的 raw 头
（`raw.githubusercontent.com` 在国内常被墙）；下到的 woff2 若被截断会报 `brotli: decoder failed`，
生成器已内置字节数重试。

---

## 3. 安装

### 方式一（推荐）：在 WorkBuddy 里直接上传 —— 点三下搞定

| 步 | 操作 |
|---|---|
| 1 | 左侧边栏点 **「专家 · 技能 · 连接器」** → 切到 **「技能」** 标签 |
| 2 | 右上角 **「添加技能」** → 选 **「上传技能」** |
| 3 | 把 **`luoshui-report-template.zip`** 拖进去（或点「选择文件」） |

**导入后系统会自动完成配置，无需额外操作。**（WorkBuddy 官方文档原文）
同一个包把扩展名换成 `.skill` 也一样 —— 客户端两种都认。

> 上传走的是客户端的**云端技能库**通道（代码里带 `cloudUid` / 云端配额校验），
> 所以更省事的做法是：**上传一次，同一账号的其他设备就不必再传包了**。
> （这一点以客户端实际表现为准 —— 我无法在这里点 UI 实测。）

### 方式二：手动解压到技能目录

```bash
mkdir -p ~/.workbuddy/skills
unzip luoshui-report-template.zip -d ~/.workbuddy/skills/
```

解压后必须得到这个路径（**目录名要保持 `luoshui-report-template`**，skill 靠它识别）：

```
~/.workbuddy/skills/luoshui-report-template/SKILL.md
```

然后重启 / 刷新会话，让它重新扫描 skills。

### 装好后怎么用

说触发词即可：

> 「**用洛水研报模版帮我写一个 XX 的深度研究报告**」

也可以直接说「按洛水研报模版写新研报」「改研报的图表样式」「补全某只股票的研报」。

### 包格式说明（想自己改包的人看）

客户端接受 **`.zip` / `.tar.gz` / `.tgz` / `.skill`**；`SKILL.md` 放在包**根目录或任意子目录**都行；
上传时会校验 `SKILL.md` 的 frontmatter **能不能被 YAML 解析** ——
值里出现「**英文冒号 + 空格**」是最常见的雷。
打包后跑一遍 `build/verify_skill_package.py`，它复刻了客户端这三条规则，会直接告诉你包能不能被导入。

---

## 4. 首次配置（改 6 个变量）

打开 `SKILL.md` 的 **「★ 环境配置」** 一节，把表里的值换成你自己的：

| 变量 | 是什么 | 怎么找 |
|---|---|---|
| `PROJ` | **项目根**（含 `build/` `deploy/` `deliver/`） | 你克隆仓库的位置 |
| `PY` | 主 Python（跑构建脚本；**别用被截断的 3.13 二进制**） | `which python3` → 换成实际能跑的那个 |
| `PYV` | 隔离 venv 的 Python（跑探针 / PIL 出图 / fonttools 子集化） | 见下方「建 venv」 |
| `TCB` | CloudBase CLI | `which tcb` |
| `ENVID` | 你的 CloudBase 环境 ID | CloudBase 控制台 |
| `DOM` | 你的访问域名 | CloudBase 静态托管配置 |

**建 venv（放 PIL / requests / fonttools）**：

```bash
"$PY" -m venv ~/.workbuddy/binaries/python/envs/default
~/.workbuddy/binaries/python/envs/default/bin/pip install pillow requests fonttools brotli
```

> **也可以完全不改文件** —— 在对话里直接把 `PROJ / PY / PYV / TCB / ENVID / DOM`
> 六个值告诉 AI 即可。skill 里所有命令都写成变量形式，AI 会按你的值替换。
> 改文件的好处是**跨会话持久**。

---

## 5. 自检

```bash
python3 scripts/check_env.py
```

常用参数：

```bash
python3 scripts/check_env.py --proj /path/to/luoshui     # 只覆盖项目根
python3 scripts/check_env.py --py /usr/bin/python3 --pyv .venv/bin/python --tcb tcb
```

脚本会做三件事：

1. 从 `SKILL.md` 的「★ 环境配置」表读出变量（**命令行参数 > 环境变量 > SKILL.md > 内置默认**）
2. 逐个检查：路径是否存在 / 可执行 / 版本是否达标（`PY` ≥ 3.9、`PYV` 能否 `import PIL`、`$TCB` 能否跑起来、`node` 是否在 PATH）
3. 检查 `$PROJ` 下写研报必需的文件，并**列出还差什么**

判据：**没有 `✗ FAIL` 就能开工**（`· WARN` 只影响少数环节）。
退出码 `0` = 全绿，`1` = 有 FAIL。

---

## 6. 常见问题

| 症状 | 原因 | 处理 |
|---|---|---|
| 说触发词没反应 | skill 没被扫到 | 确认路径正是 `~/.workbuddy/skills/luoshui-report-template/SKILL.md`（**目录名不能改**），然后重启会话 |
| 命令全报「找不到文件」 | `$PROJ` 没配 / 仓库没克隆 | 跑 `check_env.py` 看缺什么 |
| 探针报 `No module named PIL` | 用了系统 `python3` | 改用 `$PYV`（venv 里装了 pillow） |
| 页面打开是**白屏** | 用 `file://` 打开 ⇒ `Origin: null` 被网关拒 | 起本地 http（`http://127.0.0.1:<port>`）再访问 |
| 部署报未登录 | `tcb` 没登录 | `tcb login` |
| 改了样式却不生效 | 改的**不在取材范围内** | 见 `references/frontend-style.md` §2 / §5 |
| **页面字体变成 PingFang / 微软雅黑** | `build/block_font.css` 不存在（派生物没跟着走） | `$PY build/make_font_css.py --fetch`，再重新注入 |
| **脚本"跑成功了"但一个字都没输出** | 用了被截断的 `versions/3.13.12/bin/python3.13` | 改用 `envs/default/bin/python`（见 §2 依赖表） |
| 页面比预期小 1.67 MB | 同上，字体块没注进去 | 注入产物应含 `<style id="rpt-fontface">`，发前 `grep -c rpt-fontface` 应为 1 |
| 图表 tooltip 报错 | 只发了数据没发渲染器 | 环图 / 时间轴 / 渲染层改了 ⇒ **必须同时发 `report.html`** |

---

## 7. 边界（先说清，免得踩空）

- **skill 不含数据**：财务数据来自 MCP 连接器，研报内容存在 CloudBase 里，底图在仓库的 `build/lib/`。
  所以**别人拿到 skill 之前，得先拿到仓库**。
- **部署目标是各人自己的**：envId / 域名 / 密钥都以你的为准，skill 里出现的示例值只作参照。
- **底图有合规要求**：世界地图必须用**国标画法**（台湾 / 藏南 / 港澳 / 九段线）；
  当前底图数据源授权口径是「仅供学习交流」，**商用或正式对外发布前必须换有授权的底图源**。
  `build/check_map_compliance.py` 可随时复跑自检。
- **不要复制 `build/` 里的脚本到别处** —— 它们持续迭代，skill 只做「索引 + 纪律 + 流程入口」，
  脚本一律按 `$PROJ` 调用，避免出现两份互相漂移的副本。

---

## 8. 想让别人在「技能市场」里搜到并一键安装？

**WorkBuddy 内置的技能市场（SkillHub）没有自助发布入口。** 市场里的技能来自 ClawHub 平台
（技能包带 `_meta.json` 的 `ownerId / slug / version` 与 `_skillhub_meta.json` 的 `namespace`），
要发布得走那边的流程；WorkBuddy **企业版**另有**团队技能库**（管理员后台上传、按部门开放权限）。

**⇒ 个人版上，分发就是两步：把包给人 → 对方「添加技能 → 上传技能」。** 没有更短的路径。

> 顺带一提：对话里说「安装 skill」走的是**市场搜索**通道（只能装市场里已有的），
> 对自建包无效 —— 自建包只能走「上传技能」。

---

*本说明随 skill 一起分发。有问题先跑 `scripts/check_env.py`，它会把缺口列出来。*
