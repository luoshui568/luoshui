# 洛水 · 矿产战略执行工作台

单文件 HTML 工作台 —— 从「资本套利」到「产业赋能」再到「价值链整合」的战略执行看板，  
数据落在腾讯云 CloudBase PostgreSQL，前端通过 PostgREST 直连，无需自建后端。

> 这是一个**纯静态页面 + 云数据库**的项目：两份 HTML 就是整个前端，云函数只做收盘后的行情兜底。

---

## 在线地址

| 页面  | 地址                                                                                        |
| --- | ----------------------------------------------------------------------------------------- |
| 工作台 | `https://fdels568-d7g1d8o3y90a80cd7-1483776268.tcloudbaseapp.com/index.html`              |
| 研报页 | `https://fdels568-d7g1d8o3y90a80cd7-1483776268.tcloudbaseapp.com/report.html?code=600456` |

---

## 目录结构

```
deploy/                     上线产物 + 模板源（改模板，构建出产物）
  app.template.html           工作台模板（约 3,000 行，含 /*__SEED__*/ 注入点）
  report.template.html        研报页模板
  index.html                  构建产物 → 上传这个
  report.html                 构建产物 → 上传这个

build/                      构建脚本、数据源探测、E2E 探针、seed 数据
  build.py                    构建入口：注入 seed + cloud.json，一次产出两页
  lib/echarts.min.js          内联用的 ECharts 5.5.1（离线可用）
  seed/*.json                 各表初始数据（tasks / permits / milestones / …）
  seed/report_600456.json     研报三表 seed（壳 + 23 模块 + 16 张图的 option）
  cloud.json                  云端环境 ID 与匿名可发布密钥（供构建注入）
  extract_report.py           从模块版 HTML 研报抽取内容 → seed
  rpt_dump.js                 Node 打桩 echarts，导出 16 张图的 option
  push_report.py              研报三表重推工具（数据事故恢复用）
  verify_report_db.py         库 ↔ seed 逐字段比对（159 项）
  probe_*_e2e.py              Edge headless 真机 E2E 探针
  verify_stock_v2.py          投资标的模块静态校验（54 项）
  check_static.py             script 块语法 + 标签开闭配对
  live_check_v4.py            线上三方 md5 + 特征串核对
  mkshot*.py                  截图脚本（目视验收）

cloudbase/                  云端资源
  migrations/*.sql            PostgreSQL 迁移（建表 / 权限 / 管理员认证 RPC）
  functions/wb_sync_quotes/   每日收盘行情同步云函数（Nodejs 18）
```

---

## 本地构建

```bash
# 1) 构建（注入 seed 与云配置，产出 deploy/index.html + deploy/report.html）
python build/build.py

# 2) 静态校验（两页都要过）
python build/check_static.py
python build/verify_stock_v2.py

# 3) 未定义引用扫描（防「按钮点了没反应」）—— 脚本在技能目录里
python ~/.workbuddy/skills/cloudbase-singlefile-workbench/scripts/scan_undefined.py deploy/index.html
python ~/.workbuddy/skills/cloudbase-singlefile-workbench/scripts/scan_undefined.py deploy/report.html

# 4) 真机 E2E（需本机 Edge，headless）
python build/probe_report_e2e.py      # 研报页 85 项

# 5) 上线（走 CloudBase MCP 的 manageHosting(upload)）
#    上传后核对线上 md5 与特征串：
python build/live_check_v4.py
```

改版只改 `deploy/*.template.html`，**不要直接改产物** —— 产物每次构建都会被覆盖。

---

## 数据模型

13 张表，全部启用 RLS：

- **业务 8 张**：`wb_tasks` `wb_permits` `wb_milestones` `wb_watchlist` `wb_contacts` `wb_logs` `wb_works` `wb_stocks`
- **研报 3 张**：`wb_reports`（壳）/ `wb_report_mods`（23 个模块的 HTML）/ `wb_report_charts`（16 张图的 option，jsonb）
- **认证 2 张**：`wb_admins` `wb_admin_sessions`（对匿名访问完全封闭，只能通过服务端函数访问）

几条设计约定：

- **删除统一走服务端函数**，浏览器端对业务表没有 `DELETE` 权限；删除需要管理员密码。
- **管理员密码以 bcrypt 存储**，前端不持有任何密码；服务端函数均为 `SECURITY DEFINER`。
- **排序由服务端保证**（PostgREST 不保证返回顺序），新表必须带排序列。
- **研报图表即数据**：图表的 option 存 jsonb，页面只负责渲染。

---

## 开发环境注意

- 本机 git 为便携版，未加入 `PATH`。推送需显式指定代理（沙箱代理只放行 API 域名）：
  ```bash
  git -c http.proxy=http://127.0.0.1:7892 -c https.proxy=http://127.0.0.1:7892 push origin main
  ```
- 页面里的云数据库地址与匿名密钥是**前端可发布凭据**，本就内嵌在公开页面中；  
  真正的管理凭据只存在于服务端函数与本地记忆中，不入库。

---

## 许可

私有项目，未开源。
