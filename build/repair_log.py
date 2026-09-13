# -*- coding: utf-8 -*-
"""修复被 shell 反引号破坏的日志：截断到第一轮末尾，重新追加第二轮内容"""
import io

P = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38\.workbuddy\memory\2026-09-13.md'
s = io.open(P, encoding='utf-8').read()
i = s.find('# 【第二轮】')
if i < 0:
    print('未找到第二轮标记，放弃')
    raise SystemExit(1)
head = s[:i].rstrip()
print('截断前 %d 字 → 保留 %d 字' % (len(s), len(head)))

block = """

---

# 【第二轮】超级管理员迁移到服务端 + 设置页退出按钮（20:00–20:35）

## 一、用户需求
1. 设置页标题栏（截图红框处）加一个「退出」功能
2. 「把超级管理员得放到服务端做，账户密码添加到数据库里去」

## 二、数据库改造（3 个迁移）
| 版本 | 名称 | 内容 |
|---|---|---|
| 20260913200000 | create_admin_auth | wb_admins / wb_admin_sessions 两表 + 9 个函数 + 种子 luoshui |
| 20260913201000 | admin_delete_via_rpc | wb_admin_delete_row 加 p_pass；REVOKE DELETE ON 7 张业务表 FROM anon |
| 20260913202000 | admin_verify_fn | wb_admin_verify(p_token,p_pass) 删除前预检 |

函数清单：login / check / logout / change_pass / list / create / set_status / delete / delete_row / verify。
全部 SECURITY DEFINER + SET search_path，GRANT EXECUTE TO anon。

关键验证（Python 直连 REST 实测）：
- anon 直读 wb_admins → HTTP 401，DATABASE_42501 permission denied ✓
- anon 直删 wb_works → HTTP 401 42501，记录未删 ✓
- RPC 登录 / 校验 / 列表 / 改密 / 增删管理员 全部 200 且语义正确 ✓
- 错密码、空密码删除 → ok=false（BADPASS / NOPASS）✓；正确密码 → deleted=1 ✓
- 结论：CloudBase 网关完整支持 PostgREST /rpc/ 路由（本次最关键的可行性验证）

## 三、前端改造
- 12.5 节整体重写：删除 djb2 passHash / AUTH_PASS_KEY / checkAdminPass / isDefaultPass / setAuthed / clearAuthed，
  新增 Auth 对象 + authPersist / authRestore / authClear / rpc / escq / forceRelogin
- 登录门按钮加 loading 态；App.login 改异步调 wb_admin_login
- 设置页 head 加右上角「退出登录」（.setLogout 绝对定位，窄屏降级为静态）+ renderAdminPanel() 异步渲染管理员列表
- 新增 App.openAdmCreate / saveAdmCreate / admToggle / admDelete（多管理员管理）
- boot() 重构：file:// 直接放行（并置 Cloud.state=off + 显示 .localBar）；
  线上必须 wb_admin_check 通过才 bootCloud()
- deleteRow(kind,id,pass) 改走 RPC，失败回滚本地记录；flushQueue() 丢弃遗留 DELETE 项
- 5 个 delXxx 回调签名改 function(pass)；confirmDelete 先 verify 再 fn(pass)

## 四、踩的坑（三条都值得记）
1. 同一条消息里并行发多个 Edit 到同一文件会竞态 —— 5 个 delXxx 的修改只落地 2 个（delTask / delLog），
   另外 3 个（delWork / delPermit / delRes）工具报 success 但内容实际回退了。
   表现：UI 删除时 deleteRow 收到的 pass 是 undefined → 服务端 NOPASS → 回滚 → 「删不掉」。
   排查方式：给 rpc 和 deleteRow 打桩记日志，一眼看到 call: ["works", id, "undefined"]。
   铁律：同一文件的多个 Edit 必须顺序执行，一次一个。
2. 探针里用 S.works[S.works.length-1] 取目标记录差点删掉用户真实数据 ——
   库里已有用户自己录的 1 条计划，insertRow 是 unshift 且排序后位置不确定。
   改用 insertRow() 的返回值取 id。已确认用户数据 w_mtzo2mgqv3mgg 完好。
3. Bash 内联 Python 字符串里出现反引号会被 shell 当命令替换，把写入内容吃成空白 ——
   写含 Markdown 反引号的长文本一律用 Write 工具写脚本文件，不要用 python -c 内联。

## 五、验证
- 端到端（本地 http + headless Edge + 真实云端）全绿：
  未登录拦门 → 登录成功 → 删除弹窗 → 错密码不关窗不删 → 正确密码删除成功 → 新增/删除管理员 → 退出登录回门
- 四张界面截图：登录门 / 删除验证弹窗 / 设置页（含右上角退出按钮）/ 本机离线模式
- node --check 两个 script 块 OK；标签 2/2 · 7/7 · 340/340；App 52 个方法零悬空；scan_undefined ✅
- 构建产物里 passHash 出现 0 次、明文 981208 出现 0 次 ✓
- 本机 / 桌面 / 线上三方 md5 一致 6fa0450f3b6443dac515d737f67b2bde，401,948 B
- 测试数据全部清理，wb_works 仅剩用户那 1 条，wb_admins 仅剩 luoshui

## 六、语义变更（需向用户说明）
- 桌面 file:// 打开不再显示登录门（没有云端就无法做服务端认证），改为顶部黄条提示「本机离线模式」
- 「恢复初始密码」按钮已移除（服务端做不到），改用多管理员账号互相重置
"""

io.open(P, 'w', encoding='utf-8').write(head + block)
print('修复完成，现 %d 字 / %d 行' % (len(head + block), (head + block).count('\n') + 1))
